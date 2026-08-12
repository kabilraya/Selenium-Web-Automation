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
from utils.get_env import get_env
from utils.md5_generator import generate_md5_hash
from utils.session_creator import create_database_session
from utils.db_duplicate_hash_checker import check_for_duplicate_hash
from functions import download_files, regex_date_filter
from urllib.parse import urljoin
from datetime import datetime
from model.smi_model import SMI
from utils.extract_and_insertion import extract_from_json_and_insert

#make all the path 
script_path = os.path.abspath(__file__)
script_directory = os.path.dirname(script_path)
env_path = os.path.join(script_directory,".env")

[
    ecgains,
    module_name,
    main_url,
    download_path,
    server_path,
    database_url,
    region_name,
    endpoint_url,
    aws_access_key_id,
    aws_secret_access_key
] = get_env(env_path)

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

    

    project_nodes = tree.xpath("//h3/following::table//tr[position()>1]")

    bid_details = {
            "ecgains": ecgains,
            "module_name": module_name,
            "base_url" : main_url,
            "download_path" : download_path,
            "server_path" : server_path    
        }

    for node_idx, node in enumerate(project_nodes,start=1):
        row = node.xpath("./td")
        if len(row) < 2:
            continue 
        bid_name_data = row[0]
        bid_due_date_data = row[1]
        bid_name = bid_name_data.text_content().strip()
        due_date = bid_due_date_data.text_content().strip()
        
        
        #parse the date into a proper format
        formatted_date = regex_date_filter(due_date)
        date_obj = None
        if formatted_date:
            try:
                date_obj = datetime.strptime(formatted_date,"%m/%d/%Y").date()
            except ValueError as e:
                try:
                    date_obj = datetime.strptime(formatted_date,"%m/%d/%y").date()
                except ValueError as e:
                    print("Cannot parse the date")
                    continue
        

        if date_obj and date_obj < datetime.today().date():
            continue
        bid_details[node_idx] = {
                            "bid_no" : "Not Specified",
                            "bid_title": bid_name,
                            "bid_due_date" : formatted_date,
                            "agency_name" : "Clinton Community School",
                            "files_info" : {} 
                        }
        for file_idx, td in enumerate(row,start=1):
            file_links = td.xpath("./a")
            file_title = file_links[0].text_content().strip()
            url = file_links[0].get("href","").strip() 
            if not url:
                continue
            download_name = url.split("/")[-1]
            file_hash = generate_md5_hash(ecgain = ecgains, bidno = id, filename = download_name )
            #create a session of database to check for duplication of hash and kill the session immediately
            try:
                session, _ = create_database_session(database_url=database_url)
                is_duplicate_hash = check_for_duplicate_hash(session=session, hash=file_hash)
                session.close()
                if is_duplicate_hash:
                    print("Hash Duplication!! Skipping...")
                    continue
            except Exception as e:
                print(f"Session creation failed {e}")
                continue
            new_file_index = len(bid_details[node_idx]["files_info"]) + 1
            url = urljoin("https://www.clinton.edu",url)
            file = download_files(sb = sb,
                                  file_url=url,
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
        json_path = os.path.join(download_path, "projects.json")

        with open(json_path, "w", encoding="utf-8") as json_file:
            json.dump(bid_details, json_file, indent=4, ensure_ascii=False)

        print(f"JSON saved to: {json_path}")

        bid_counts = extract_from_json_and_insert(
            json_path=json_path,
            db_url=database_url,
            region_name=region_name,
            endpoint_url=endpoint_url,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key
        )

        print(bid_counts)
    

