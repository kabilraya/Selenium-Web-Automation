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
from functions import download_files,regex_date_filter
from urllib.parse import urljoin,quote
from datetime import datetime
from model.smi_model import SMI
from kabil_utils.vpn_required_db_insertion import extract_from_json_and_add_to_db
from kabil_utils.vpn_disconnet import disconnect_vpn
from dotenv import load_dotenv
from kabil_utils.record_data_insertion import insert_into_record_db
from kabil_utils.db_value_updater import update_value
from kabil_utils.file_remover import delete_files_in_directory

import re
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
load_dotenv(env_path)
login_email = os.getenv("LOGIN_EMAIL")
login_pass = os.getenv("LOGIN_PASSWORD")
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
    sb.uc_open_with_reconnect(main_url, reconnect_time=6)

    sb.uc_gui_click_captcha()
    sb.sleep(5)
    sb.switch_to_default_content()
    sign_in_xpath = "//div[@class='ps_box-grid']/div[@class='ps_grid-div ps_grid-body']/div[contains(normalize-space(),'Sign In')]"
    sb.hover_and_click(hover_selector=sign_in_xpath, click_selector=sign_in_xpath)

    sb.sleep(3)
    sb.switch_to_frame("//iframe[@id='ptModFrame_0']")
    sb.sleep(2)
    sb.type("//input[@type='text']",login_email)
    sb.type("//input[@type='password']",login_pass)
    sb.hover_and_click(hover_selector="//span[@title='Sign In']", click_selector="//span[@title='Sign In']")
    sb.sleep(3)
    sb.switch_to_default_content()
    sb.sleep(2)
    bidding_direct_xpath = "//div[@class='ps_box-grid']/div[@class='ps_grid-div ps_grid-body']/div[contains(normalize-space(),'Bidding Opportunities')]"
    sb.hover_and_click(hover_selector=bidding_direct_xpath, click_selector=bidding_direct_xpath)
    sb.sleep(10)
    sb.switch_to_frame("//iframe[@id='ptifrmtgtframe']")
    sb.sleep(5)
    page_source = sb.get_page_source()
    sb.sleep(3)
    tree = html.fromstring(page_source)
    

    bid_nodes = tree.xpath(
        "//table[@id='tdgbrRESP_INQA_HD_VW_GR$0']/tbody/tr[contains(normalize-space(),'RFP 6M2125 Bond Underwriting Services Pool')]/preceding-sibling::tr"
    )
    print(len(bid_nodes))
    #Creating a top level directory which consists the top level infomation common for all the bids in one websites
    bid_details = {
    "ecgains": ecgains,
    "module_name": module_name,
    "base_url" : main_url,
    "download_path" : download_path,
    "server_path" : server_path
    }
    
    
    for node_idx, node in enumerate(bid_nodes,start=1):
         
        sb.switch_to_default_content()
        row_id = node.get("id")
        bid_title = node.xpath("./td[2]")[0].text_content().strip()
        
        bid_no = node.xpath("./td[1]")[0].text_content().strip()
        bid_due_date = node.xpath("./td[4]")[0].text_content().strip()
        print(bid_due_date)
        formatted_date = regex_date_filter(bid_due_date)
        date_obj = None
        if formatted_date:
            try:
                date_obj = datetime.strptime(formatted_date,"%m/%d/%y").date()
            except ValueError as e:
                try:
                    date_obj = datetime.strptime(formatted_date,"%m/%d/%Y").date()
                except ValueError as e:
                    print("Couldn't parse the given date")
                    continue
        if date_obj and date_obj <= datetime.today().date():
            continue
        print(f"Bid Title: {bid_title}\nBid No.:{bid_no}\nBid Due Date: {formatted_date}")  
    
        bid_details[node_idx] = {
                        "bid_no": bid_no,
                        "bid_title": bid_title,          
                        "bid_due_date": formatted_date,        
                        "agency_name": module_name,
                        "files_info": {}
                    }
        sb.switch_to_frame("//iframe[@id='ptifrmtgtframe']")
        sb.sleep(3)
        directed_link = f"//table[@id='tdgbrRESP_INQA_HD_VW_GR$0']/tbody/tr[contains(normalize-space(),'RFP 6M2125 Bond Underwriting Services Pool')]/preceding-sibling::tr[@id='{row_id}']/td[1]//a"
        sb.hover_and_click(hover_selector=directed_link,click_selector=directed_link)
        sb.sleep(10)

        # sb.switch_to_default_content()
        # sb.switch_to_frame("//iframe[@id='ptifrmtgtframe']")
        # sb.sleep(4)
        download_file_button = "//input[@value='Download Files']"
        sb.hover_and_click(hover_selector=download_file_button,click_selector=download_file_button)
        sb.sleep(5)
        # sb.switch_to_default_content()
        # sb.sleep(2)
        # sb.switch_to_frame("//iframe(ptifrmtgtframe)")
        # sb.sleep(3)
        page_source = sb.get_page_source()
        sb.sleep(2)
        tree = html.fromstring(page_source)
        checkbox_xpath = "//div[@id='win0divBRT_AUC_MSG_CHECKED']//input[@type='checkbox']"
        sb.sleep(2)
        sb.hover_and_click(hover_selector=checkbox_xpath,click_selector=checkbox_xpath)
        sb.sleep(3)
        
        
        #//input[@title='View Attached File']
        
        tr_nodes = tree.xpath("//table[@id='tdgbrAUC_ATTCH_HD_VW$0']/tbody/tr")
        if not tr_nodes:
            continue
        print(len(tr_nodes))
        for file_idx, tr in enumerate(tr_nodes, start = 1):
            #Get the file name first
            file_name = tr.xpath("./td[1]")[0].text_content().strip()
            
            
            file_hash = generate_md5_hash(ecgain = ecgains, bidno = bid_no, filename = file_name )
            # create a session of database to check for duplication of hash and kill the session immediately
            
            new_file_index = len(bid_details[node_idx]["files_info"]) + 1
            sb.switch_to_default_content()
            sb.sleep(1)
            sb.switch_to_frame("//iframe[@id='ptifrmtgtframe']")
            sb.sleep(1)
            file = download_files(sb = sb,
                                  file_button=f"//table[@id='tdgbrAUC_ATTCH_HD_VW$0']/tbody/tr[{file_idx}]//input[@title='View Attached File']",
                                  script_directory=script_directory,
                                  download_path=download_path,
                                  file_index=new_file_index,
                                  file_hash=file_hash,
                                  bid_no=bid_no,
                                  ecgains=ecgains)
            bid_details[node_idx]["files_info"].update(file)
        sb.switch_to_default_content()
        sb.sleep(4)
        back_button_one = "//span[normalize-space()='Search Event Details' and @class='ps-text']"
        sb.hover_and_click(hover_selector=back_button_one,click_selector=back_button_one)
        sb.sleep(10)
        back_button_two = "//span[normalize-space()='Supplier Search Events' and @class='ps-text']"
        sb.hover_and_click(hover_selector=back_button_two,click_selector=back_button_two)
        sb.sleep(10)
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
        disconnect_vpn()
        time.sleep(5)
        bid_counts = extract_from_json_and_add_to_db(
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
                    query="UPDATE tbl_smirecord SET baseURL = :baseURL_value, brokenFlag = :broken_flag_value, server = :server_value WHERE ecgain = :ecgain_value AND moduleName = :module_name_value",
                    new_values={"broken_flag_value": 0, "server_value": "nplproductionSelenium1", "baseURL_value":main_url},
                    condition_values={"ecgain_value": ecgains, "module_name_value": module_name.split(".")[0]},
                    )
        delete_files_in_directory(download_path)
    
        print("Scraping Successful")

    

