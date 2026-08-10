from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from seleniumbase import SB
import sys
import os 
from lxml import html
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
import time
from utils.get_env import get_env
from functions import download_files, regex_date_filter
from urllib.parse import urljoin
from datetime import datetime
#make all the path 
script_path = os.path.abspath(__file__)
script_directory = os.path.dirname(script_path)

env_path = os.path.join(script_directory,".env")
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

    projects = []

    project_nodes = tree.xpath("//h3/following::table//tr[position()>1]")


    for node_idx, node in enumerate(project_nodes,start=1):
        row = node.xpath("./td")
        if len(row) < 2:
            continue 
        bid_name_data = row[0]
        bid_due_date_data = row[1]
        bid_name = bid_name_data.text_content().strip()
        due_date = bid_due_date_data.text_content().strip()
        bid = {}
        
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
        bid[node_idx] = {
                    "bid_name": bid_name,
                    "due_date" : formatted_date,
                    "files_info" : {} 
                }

        if date_obj and date_obj < datetime.today().date():
            continue
        for file_idx, td in enumerate(row,start=1):
            file_links = td.xpath("./a")

            
            file_title = file_links[0].text_content().strip()
            url = file_links[0].get("href","").strip() 
            if not url:
                continue
            new_file_index = len(bid[node_idx]["files_info"]) + 1
            url = urljoin("https://www.clinton.edu",url)
            file = download_files(sb = sb,
                                  file_url=url,
                                  script_directory=script_directory,
                                  download_path=download_path,
                                  file_index=new_file_index,
                                  bid_index=node_idx)
            bid[node_idx]["files_info"].update(file)
        projects.append(bid)

    print(projects)
    print(len(projects))
    

