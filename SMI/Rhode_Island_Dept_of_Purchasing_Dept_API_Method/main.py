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
from urllib.parse import urljoin,quote
from datetime import datetime
from model.smi_model import SMI
from kabil_utils.extract_and_insertion import extract_from_json_and_insert
from kabil_utils.record_data_insertion import insert_into_record_db
from kabil_utils.db_value_updater import update_value
from kabil_utils.file_remover import delete_files_in_directory
from kabil_utils.extract_bid_number import extract_bid_no
from kabil_utils.extract_date_from_textblock import extract_raw_date
import re
from dotenv import load_dotenv
#make all the path 

import atexit
from datetime import datetime

class Tee:
    """Writes everything to both the terminal and a log file."""
    def __init__(self, stream, log_file):
        self.stream = stream
        self.log_file = log_file

    def write(self, data):
        self.stream.write(data)
        self.log_file.write(data)
        self.log_file.flush()   # so logs survive a crash

    def flush(self):
        self.stream.flush()
        self.log_file.flush()

    def isatty(self):
        return self.stream.isatty()

    def __getattr__(self, name):
        # fall back to the original stream for anything else (fileno, encoding, etc.)
        return getattr(self.stream, name)


log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs.txt")
log_file = open(log_path, "a", encoding="utf-8")   # "a" = append, keeps old runs

log_file.write(f"\n{'=' * 70}\n")
log_file.write(f"RUN STARTED: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
log_file.write(f"{'=' * 70}\n")
log_file.flush()

sys.stdout = Tee(sys.__stdout__, log_file)
sys.stderr = Tee(sys.__stderr__, log_file)


def _close_log():
    log_file.write(f"\nRUN ENDED: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    log_file.flush()
    # put the real streams back BEFORE closing, so late shutdown output is safe
    sys.stdout = sys.__stdout__
    sys.stderr = sys.__stderr__
    log_file.close()

atexit.register(_close_log)
start_time = time.perf_counter()

script_path = os.path.abspath(__file__)
script_directory = os.path.dirname(script_path)
env_path = os.path.join(script_directory,".env")
load_dotenv()
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

#First we get the rows from the database which whose ECGAINS = ecgains, stCloudURL is empty and the days 
#passed is less that 3 days
#Code here
#Then we group the rows by the same stBidNo value
#for each stBidNo item 
#first we get the stURL2 and get the bid from it https://webprocure.proactiscloud.com/MainBidBoard?ac=4&bid=146484&owner_id=120002&docid=1979202
#Example get the 146484 -> this should be done once as this is unique for all the rows having the same bid no 
#make the API request URL as https://webprocure.proactiscloud.com/wp-full-text-search/soldetail/146484?customerid=46
# Replace the 146484 with the bid={value} we got from stURL2
# hit the API endpoint and get the response
# get the docid from each stURL2 for that bid_no
# get the filename for the docid from the row = docid from the response body 
# create the //a xpath to click and download files
# the downloaded files should be uplaoded to the cloud
# create the cloud path -> update the db for that row
# 
    

