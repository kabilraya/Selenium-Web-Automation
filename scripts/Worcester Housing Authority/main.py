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
    database_url
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
    
    bid_rows = tree.xpath("//h2[@id='heading-2026-puchasing-closed-bids']/following::table[1]/tbody/tr")

    bid_details = {
            "ecgains": ecgains,
            "module_name": module_name,
            "base_url" : main_url,
            "download_path" : download_path,    
        }
    
    for node_idx, row in enumerate(bid_rows,start=1):
        data = row.xpath("./td")

        if len(data) < 7:
            continue
        bid_no = data[0].text_content().strip()
        title = data[1].text_content().strip()
        due_date = data[5].text_content().strip()
        
        date_obj = None
        
        formatted_date = regex_date_filter(due_date)
        
        if formatted_date:
            try:
                date_obj = datetime.strptime(formatted_date,"%m/%d/%Y").date()
            except ValueError as e:
                try:
                    print("Formatting in another way")
                    date_obj = datetime.strptime(formatted_date,"%m/%d/%y").date()
                except ValueError as e:
                    continue
        if date_obj and date_obj < datetime.today().date():
            print("Due date has passed")
            continue

        #extracting all the links from a single row
        #creating a bid record for each row

        file_links = row.xpath(".//a")
        if not file_links:
            continue

        
        bid_details[node_idx] = {
            "bid_no" : bid_no,
            "bid_title" : title,
            "bid_due_date" : formatted_date,
            "agency_name" : "Worcester Housing Authority",
            "files_info" : {}
        }
        for file_index, file_url in enumerate(file_links,start=1):

            url = file_url.get("href","").strip()
            print(url)

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
            url = urljoin("https://worcesterha.org",url)
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
            db_url=database_url
        )

        print(bid_counts)       
    

