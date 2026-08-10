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

    bids = []
    sb.click('//div[normalize-space()="Request for Proposals & Bids"]/ancestor::button[1]')

    page_source = sb.get_page_source()
    time.sleep(10)
    tree = html.fromstring(page_source)
    
    bid_links = tree.xpath("//p[normalize-space()='DISTRICT BIDS BELOW ARE HANDLED THROUGH THE EDUCATION SERVICE CENTER:']/following::p[1]/a[position() < last()]")

    print(bid_links)
    for idx, bid_link in enumerate(bid_links,start=1):
        link_description = bid_link.text_content().strip()

        
        bid = {}
        bid[idx] = {
            "name" : link_description,
            "files_info" : {} 
        }
        url = bid_link.get("href","").strip()
        print(url)
        
        if not url:
            continue
        new_file_index = len(bid[idx]["files_info"]) + 1
        url = urljoin("https://aptg.co",url)
        file = download_files(sb = sb,
                              file_url=url,
                              script_directory=script_directory,
                              download_path=download_path,
                              file_index=new_file_index,
                              bid_index=idx)
        bid[idx]["files_info"].update(file)
        bids.append(bid)

    
    print(len(bids))

    json_path = os.path.join(download_path, "projects.json")

    with open(json_path, "w", encoding="utf-8") as json_file:
        json.dump(bids, json_file, indent=4, ensure_ascii=False)

    print(f"JSON saved to: {json_path}")        
    

