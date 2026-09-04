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
from functions import download_files, regex_date_filter,is_direct_download,form_filling
from urllib.parse import urljoin,urlsplit, quote
from datetime import datetime
from model.smi_model import SMI
from kabil_utils.vpn_required_db_insertion import extract_from_json_and_add_to_db
from kabil_utils.record_data_insertion import insert_into_record_db
from kabil_utils.db_value_updater import update_value
from kabil_utils.file_remover import delete_files_in_directory
from kabil_utils.vpn_disconnet import disconnect_vpn
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

download_path=os.path.join(script_directory, "download")
BID_NO_PATTERN = re.compile(
            r'^(?:RFQ/RFP|RFQ|RFP|Bid)\s*#?\s*[\w-]+',
            re.IGNORECASE
        )

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
    sb.sleep(3)
    page_source = sb.get_page_source()
    
    tree = html.fromstring(page_source)
    sb.sleep(3)
    
    bid_nodes = tree.xpath("//div[@class='accordion ']/div[@class='accordion-item']")

    #Creating a top level directory which consists the top level infomation common for all the bids in one websites
    bid_details = {
    "ecgains": ecgains,
    "module_name": module_name,
    "base_url" : main_url,
    "download_path" : download_path,
    "server_path" : server_path
    }
    print(len(bid_nodes))
    for node_idx, node in enumerate(bid_nodes,start=1):        
        
        bid_status = node.xpath(".//strong[contains(normalize-space(),'Status:')]/following-sibling::text()")
        if not bid_status:
            bid_status = node.xpath(".//strong[contains(normalize-space(),'Status: ')]")[0].text_content().strip()    
            bid_status = bid_status.split(":",1)[-1].strip()
        bid_status = bid_status[0].strip()
        if not bid_status.lower() == "open":
                continue
        
        bid_title = node.xpath("./h2")[0].text_content().strip()
        bid_title = bid_title.split("(",1)[0].strip()
        match = BID_NO_PATTERN.match(bid_title)
        if match:
            bid_no = match.group(0).strip()
        else:
            bid_no = bid_title[:25]
        formatted_date = "Not Specified"
        
        print(f"Bid Title: {bid_title}\nBid No.:{bid_no}\nBid Due Date: {formatted_date}")
        
        directed_links = node.xpath(".//ul//a")
        
        if not directed_links:
            continue
        bid_details[node_idx] = {
                        "bid_no": bid_no,
                        "bid_title": bid_title,          
                        "bid_due_date": formatted_date,        
                        "agency_name": module_name,
                        "files_info": {}
                    }
        file_urls = []
        for directed_link in directed_links:
            directed_url = directed_link.get("href", "").strip()
            if not directed_url:
                continue
            directed_url = urljoin("https://rsccd.edu/", directed_url)

            if is_direct_download(directed_url):
                file_urls.append(directed_url)
            else:
                # this link gates behind a form — resolve it to its real download link(s)
                main_window = sb.driver.current_window_handle
                sb.execute_script("window.open(arguments[0], '_blank');", directed_url)
                sb.sleep(2)
                sb.switch_to_window(sb.driver.window_handles[-1])
                form_filling(sb)
                sb.sleep(3)
                page_source = sb.get_page_source()
                sb.sleep(3)
                popup_tree = html.fromstring(page_source)
                file_elements = popup_tree.xpath("//div[@id='view-pageDescription']//a")
                sb.driver.close()
                sb.switch_to_window(main_window)

                resolved_urls = [
                    urljoin("https://rsccd.edu/", el.get("href", "").strip())
                    for el in file_elements
                    if el.get("href", "").strip()
                ]
                file_urls.extend(resolved_urls)

        
        seen = set()
        file_urls = [u for u in file_urls if not (u in seen or seen.add(u))]

        for file_idx, file_url in enumerate(file_urls, start=1):
            download_name = file_url.split("/")[-1]
            print(download_name)
            file_hash = generate_md5_hash(ecgain=ecgains, bidno=bid_no, filename=download_name)
            
            new_file_index = len(bid_details[node_idx]["files_info"]) + 1
            quoted_url = quote(file_url, safe=":/?&=%")
            file = download_files(
                sb=sb,
                file_url=quoted_url,
                script_directory=script_directory,
                download_path=download_path,
                file_index=new_file_index,
                file_hash=file_hash,
            )
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
                query="UPDATE tbl_smirecord SET brokenFlag = :broken_flag_value, server = :server_value, " \
                "baseURL = :baseURL_value WHERE ecgain = :ecgain_value AND moduleName = :module_name_value", 
                new_values={"broken_flag_value": 0, "server_value": "nplproductionSelenium1", "baseURL_value": main_url}, 
                condition_values={"ecgain_value": ecgains, "module_name_value": module_name.split(".")[0]},
                )
        
        delete_files_in_directory(download_path)
    
        print("Scraping Successful")

    

