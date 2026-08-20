from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from seleniumbase import SB
import sys
import os 
import json
from lxml import html
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..","..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import time
from kabil_utils.get_env import get_env
from kabil_utils.md5_generator import generate_md5_hash
from kabil_utils.session_creator import create_database_session
from kabil_utils.db_duplicate_hash_checker import check_for_duplicate_hash
from functions import download_files, regex_date_filter
from urllib.parse import urljoin,urlsplit
from datetime import datetime
from model.smi_model import SMI
from kabil_utils.extract_and_insertion import extract_from_json_and_insert
from kabil_utils.record_data_insertion import insert_into_record_db
from kabil_utils.db_value_updater import update_value
from kabil_utils.file_remover import delete_files_in_directory

#make all the path 
start_time = time.perf_counter()

script_path = os.path.abspath(__file__)
script_directory = os.path.dirname(script_path)
env_path = os.path.join(script_directory,".env")

[
    ecgains,
    module_name,
    main_url,
    download_path,
    server_path,
    smi_data_url,
    smi_record_url,
    region_name,
    endpoint_url,
    aws_access_key_id,
    aws_secret_access_key
] = get_env(env_path)

download_path=os.path.join(script_directory, "download")

with SB (
    uc = True,
    test = True,
    headless = False,
    incognito = False,
    undetectable= True,
    xvfb=False,
    guest_mode=False,
    disable_features = "ChromePDFViewer",
    external_pdf = True,
    locale = "en",
) as sb:
    sb.uc_open_with_reconnect(main_url)
    
    sb.uc_gui_click_captcha()
    sb.sleep(3)
    # print(type(sb))
    # print(hasattr(sb, "uc_open_with_reconnect"))
    page_source = sb.get_page_source()
    time.sleep(10)
    tree = html.fromstring(page_source)

    
    project_nodes = tree.xpath("//tbody/tr")

    #Creating a top level directory which consists the top level infomation common for all the bids in one websites
    bid_details = {
    "ecgains": ecgains,
    "module_name": module_name,
    "base_url" : main_url,
    "download_path" : download_path,
    "server_path" : server_path
    }

    for node_idx, node in enumerate(project_nodes,start=1):
        bid_title = node.xpath("./td[1]")[0].text_content().strip()
        
        bid_no = bid_title[:25]
        bid_due_date = node.xpath("./td[5]")[0].text_content().strip()
        
        # to extract the file content
        
        formatted_date = regex_date_filter(bid_due_date)

        date_obj = None
        if formatted_date:
            try:
                date_obj = datetime.strptime(formatted_date,"%m/%d/%Y").date()
            except ValueError as e:
                try:
                    date_obj = datetime.strptime(formatted_date,"%m/%d/%y").date()
                except ValueError as e:
                    print(f"Cannot Parse the date.. Failed due to: {e}")
                    continue

        if date_obj and date_obj < datetime.today().date():
            
            continue

        print(formatted_date)
        
        #Get all the links on that node
        file_links = node.xpath(".//a")
        # If any one link is found we make a dictionary         
        bid_details[node_idx] = {
        "bid_no": bid_no,
        "bid_title": bid_title,          
        "bid_due_date": formatted_date,        
        "agency_name": module_name,
        "files_info": {}
    }
        if not file_links:
            continue
        for file_idx, file in enumerate(file_links, start = 1):
            file_url = file.get("href","").strip()
            download_name = file_url.split("/")[-1]
            print(download_name)
            file_hash = generate_md5_hash(ecgain = ecgains, bidno = bid_no, filename = download_name )
            # create a session of database to check for duplication of hash and kill the session immediately
            try:
                session, _ = create_database_session(database_url=smi_data_url)
                is_duplicate_hash = check_for_duplicate_hash(session=session, hash=file_hash)
                session.close()
                if is_duplicate_hash:
                    print("Hash Duplication found")
                    continue
            except Exception as e:
                print(f"Session creation failed {e}")
                continue
            
            new_file_index = len(bid_details[node_idx]["files_info"]) + 1
            file_url = urljoin("https://www.nj.gov/",file_url)
            file = download_files(sb = sb,
                                  file_url=file_url,
                                  script_directory=script_directory,
                                  download_path=download_path,
                                  file_index=new_file_index,
                                  file_hash=file_hash)
            bid_details[node_idx]["files_info"].update(file)

    has_downloads = any(
        bid["files_info"]
        for key, bid in bid_details.items()
        if isinstance(key, int)
        )
    
    if not has_downloads:
        print("No new files downloaded. Skipping JSON creation and database insertion.")
    else:
        json_path = os.path.join(script_directory, "projects.json")

        with open(json_path, "w", encoding="utf-8") as json_file:
            
            json.dump(bid_details, json_file, indent=4, ensure_ascii=False)

        print(f"JSON saved to: {json_path}")

        bid_counts = extract_from_json_and_insert(
            json_path=json_path,
            db_url=smi_data_url,
            region_name=region_name,
            endpoint_url=endpoint_url,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
        )
        end_time = time.perf_counter()
        total_execution_time = round((end_time - start_time) / 60)
        total_bids = bid_counts["total_bid"]
        total_new_bid = bid_counts["total_new_bid"]
        total_new_bid_file = bid_counts["total_new_bid_file"]
        print(f"Total bids: {total_bids}")
        print(f"Total new bids: {total_new_bid}")
        print(f"Total new bid files: {total_new_bid_file}")
        print(f"Process took around {total_execution_time}")

        #Inserting the records such as total_bids, total_new_bids, total_new_bid_files and execution_time into Record DB

        session, _ = create_database_session(database_url=smi_record_url)
        insert_into_record_db(
            session = session,
            ecgain=ecgains,
            module_name=module_name.split(".")[0],
            total_bid= total_bids,
            total_new_bid=total_new_bid,
            total_new_bid_files=total_new_bid_file,
            timeelapsed=total_execution_time
        )

        update_value(
                    db_url=smi_record_url,
                    query="UPDATE tbl_smirecord SET brokenFlag = :broken_flag_value, server = :server_value WHERE ecgain = :ecgain_value AND moduleName = :module_name_value",
                    new_values={"broken_flag_value": 0, "server_value": "nplproductionSelenium1"},
                    condition_values={"ecgain_value": ecgains, "module_name_value": module_name.split(".")[0]},
                    )
        delete_files_in_directory(download_path)
    
        print("Scraping Successful")

    

