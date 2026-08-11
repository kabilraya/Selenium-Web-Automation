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
[   ecgains,
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

    
    project_nodes = tree.xpath("//h2[normalize-space()='Project Information']/following::div[1]//details")

    #Creating a top level directory which consists the top level infomation common for all the bids in one websites
    bid_details = {
    "ecgains": ecgains,
    "module_name": module_name,
    "base_url" : main_url,
    "download_path" : download_path,
    
    }

    for node_idx, node in enumerate(project_nodes,start=1):
        summary = node.xpath("./summary")[0]

        id = str(summary.xpath("./text()[1]")[0].strip())
        institution_name = summary.xpath("./text()[2]")[0].strip()
        bid_title = summary.xpath("./text()[3]")[0].strip()

        # to extract the file content
        bid_details[node_idx] = {
        "bid_no": id,
        "bid_title": bid_title,          
        "bid_due_date": "None",        
        "agency_name": institution_name,
        "files_info": {}
    }
        file_links = node.xpath(".//a")
        if not file_links:
            continue
        for file_idx, file_url in enumerate(file_links,start = 1):
            file_title = file_url.text_content().strip()
            url = file_url.get("href","").strip() 
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
                    continue
            except Exception as e:
                print(f"Session creation failed {e}")
                continue
            
            new_file_index = len(bid_details[node_idx]["files_info"]) + 1

            url = urljoin("https://ardot.gov",url)

            file = download_files(sb = sb,
                                  file_url=url,
                                  script_directory=script_directory,
                                  download_path=download_path,
                                  file_index=new_file_index,
                                  file_hash=file_hash)
            bid_details[node_idx]["files_info"].update(file)

    json_path = os.path.join(download_path, "projects.json")

    with open(json_path, "w", encoding="utf-8") as json_file:
        json.dump(bid_details, json_file, indent=4, ensure_ascii=False)

    print(f"JSON saved to: {json_path}") 

    #insertion into database using ORM mapping       
    bid_counts = extract_from_json_and_insert(json_path=json_path, db_url=database_url)

    print(bid_counts)

