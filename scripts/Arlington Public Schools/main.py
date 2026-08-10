from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from seleniumbase import SB
import sys
import os 
from lxml import html
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..","..")))
import time
from utils.get_env import get_env
from functions import download_files, regex_date_filter
from urllib.parse import urljoin
from datetime import datetime

#make all the path 
script_path = os.path.abspath(__file__)
script_directory = os.path.dirname(script_path)
env_path = os.path.join(script_directory,".env")

#Importing all the enviroment variables
[
    main_url,
    download_path
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

    bids = []

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
        
            
        bid = {} #to create a record for a row from a table    
        bid[node_idx] = {
            "bid_no." : main_title[:25],
            "description" : description,
            "contact" : contact,
            "file_info" : {}
        }

        for file_idx, each in enumerate(file_links, start = 1):
            #extract the name for each files from one bid
            file_title = each.text_content().strip()
            link = each.get("href","").strip()
            if not link:
                continue
            next_file_index = str(len(bid[node_idx]["file_info"]) + 1)

            link = urljoin("https://www.apsva.us",link)

            file = download_files(
                sb=sb,
                file_url=link,
                script_directory=script_directory,
                download_path=download_path,
                file_index=next_file_index,
                bid_index=node_idx
            )
            bid[node_idx]["file_info"].update(file) 
        bids.append(bid)
    print(bids)           


           


