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
from urllib.parse import urljoin
from datetime import datetime
from model.smi_model import SMI
from kabil_utils.extract_and_insertion import extract_from_json_and_insert

#make all the path 
script_path = os.path.abspath(__file__)
script_directory = os.path.dirname(script_path)
env_path = os.path.join(script_directory,".env")

#Importing all the enviroment variables
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

    bid_details = {
    "ecgains": ecgains,
    "module_name": module_name,
    "base_url" : main_url,
    "download_path" : download_path,
    "server_path" : server_path   
    }

    bid_row = tree.xpath("//h3[normalize-space()='Current Solicitations']/following::table[1]//tr[position()>1]")


    for node_idx, node in enumerate(bid_row,start=1):
        row = node.xpath("./td")
        if len(row) < 4:
            continue
        solicitation_data = row[0]
        description_data = row[1]
        issued_date_data = row[2]
        contact_data = row[3]

        
        description = description_data.text_content().strip()
        date = issued_date_data.text_content().strip()
        formatted_date = regex_date_filter(date)
        print(formatted_date)
        due_date_obj = None
        if formatted_date:
            try:
                #conversion to datetime object not string
                due_date_obj = datetime.strptime(formatted_date,"%m/%d/%Y").date()
            except ValueError as e:
                try:
                    due_date_obj = datetime.strptime(formatted_date,"%m/%d/%y").date()
                except ValueError as e:
                    print("Error parsing the date and time")
                    continue

        #check if the due date is valid on the basis of today() date
        if due_date_obj and due_date_obj < datetime.today().date():
            continue

        contact = contact_data.text_content().strip()

        # all the dates must be parsed into a proper format
        file_links = solicitation_data.xpath(".//a")

        if not file_links:
            continue
        #title of the bid per row and on the row[0] is on the first link so we strip it 
        main_title = file_links[0].text_content().strip()
        
            
         #to create a record for a row from a table    
        bid_details[node_idx] = {
            "bid_no" : main_title[:25],
            "bid_title" : description,
            "bid_due_date": formatted_date,
            "contact" : contact,
            "agency_name" : "Arlington Public Schools",
            "files_info" : {}
        }

        for file_idx, each in enumerate(file_links, start = 1):
            #extract the name for each files from one bid
            file_title = each.text_content().strip()
            url = each.get("href","").strip()
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
                    print("Duplicate Hash Found!! Skipping....")
                    continue
            except Exception as e:
                print(f"Session creation failed {e}")
                continue
            next_file_index = str(len(bid_details[node_idx]["files_info"]) + 1)

            url = urljoin("https://www.apsva.us",url)

            file = download_files(
                sb=sb,
                file_url=url,
                script_directory=script_directory,
                download_path=download_path,
                file_index=next_file_index,
                file_hash = file_hash
            )
            bid_details[node_idx]["file_info"].update(file) 

    #Checking if any files got downloaded to proceed with the JSON dumping and database works

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


           


