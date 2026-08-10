from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from seleniumbase import SB
import sys
import os 
import json
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

    project_nodes = tree.xpath("//h2[normalize-space()='Project Information']/following::div[1]//details")


    for node_idx, node in enumerate(project_nodes,start=1):
        summary = node.xpath("./summary")[0]

        number = summary.xpath("./text()[1]")[0].strip()
        institution_name = summary.xpath("./text()[2]")[0].strip()

        # to extract the file content
        project = {}
        project[node_idx] = {
            "bid_number" : number,
            "institution_name" : institution_name,
            "files_info" : {} 
        }
        file_links = node.xpath(".//a")

        for file_idx, file_url in enumerate(file_links,start = 1):
            file_title = file_url.text_content().strip()
            url = file_url.get("href","").strip() 
            if not url:
                continue

            new_file_index = len(project[node_idx]["files_info"]) + 1

            url = urljoin("https://ardot.gov",url)

            file = download_files(sb = sb,
                                  file_url=url,
                                  script_directory=script_directory,
                                  download_path=download_path,
                                  file_index=new_file_index,
                                  bid_index=node_idx)
            project[node_idx]["files_info"].update(file)
        projects.append(project)

    
    print(len(projects))

    json_path = os.path.join(download_path, "projects.json")

    with open(json_path, "w", encoding="utf-8") as json_file:
        json.dump(projects, json_file, indent=4, ensure_ascii=False)

    print(f"JSON saved to: {json_path}")        
    

