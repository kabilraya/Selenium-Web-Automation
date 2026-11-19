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
from kabil_utils.amr_duplicate_hash_checker import check_for_duplicate_amr_hash
from kabil_utils.amr_db_insert import insert_to_amr_database
from kabil_utils.extract_bid_number import extract_bid_no
from kabil_utils.extract_date_from_textblock import extract_raw_date

import atexit
from datetime import datetime
from dotenv import load_dotenv
import re



_MONTHS = (
    r'(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|'
    r'Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'
)
_TEXT_DATE = re.compile(
    rf'\b({_MONTHS})\.?\s*(\d{{1,2}})(?:st|nd|rd|th)?\s*,?\s*(\d{{4}})',
    re.IGNORECASE,
)
_NUMERIC_DATE = re.compile(r'(\d{1,2})/(\d{1,2})/(\d{4}|\d{2})(?!\d)')


def regex_date_filter(raw_due_date: str) -> str | None:
    """
    Extracts a date from text such as:
      - '9/09/2026', '8/28/26 at 10:00 am'
      - 'September 9, 2026'
      - 'Friday, May 1st, 2026 @ 3:00PM CST'
    Returns 'mm/dd/yyyy', or None if nothing matched.
    """
    if not raw_due_date:
        return None

    m = _NUMERIC_DATE.search(raw_due_date)
    if m:
        month, day, year = m.groups()
        fmt = "%m/%d/%Y" if len(year) == 4 else "%m/%d/%y"
        try:
            return datetime.strptime(f"{month}/{day}/{year}", fmt).strftime("%m/%d/%Y")
        except ValueError as e:
            print(f"Matched numeric pattern but failed to parse: {e}")

    m = _TEXT_DATE.search(raw_due_date)
    if m:
        month, day, year = m.groups()
        try:
            # first 3 letters covers "May", "Sept", "September", etc.
            return datetime.strptime(f"{month[:3].title()} {day} {year}", "%b %d %Y").strftime("%m/%d/%Y")
        except ValueError as e:
            print(f"Matched text-date pattern but failed to parse: {e}")

    return None

script_directory = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(script_directory, ".env")
load_dotenv(env_path)

ecgains = os.getenv("ECGAINS")
base_url = os.getenv("MAIN_URL")
smi_data_url = os.getenv("SMI_DATA_URL")

session, _ = create_database_session(smi_data_url)

script_path = os.path.abspath(__file__)
script_directory = os.path.dirname(script_path)



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

with SB (
    uc = True,
    test = True,
    incognito = False,
    undetectable= True,
    xvfb = False,
    guest_mode = False,
    disable_features = "ChromePDFViewer",
    external_pdf = True,
    locale = "en",
    chromium_arg = "--disable-popup-blocking"
) as sb:
    sb.uc_open_with_reconnect(base_url, reconnect_time = 6)

    sb.sleep(3)
    sb.uc_gui_handle_captcha()
    sb.sleep(5)
    sb.switch_to_default_content()
    sb.sleep(2)
    tree = html.fromstring(sb.get_page_source())
    sb.sleep(1)

    bid_nodes = tree.xpath("//table[@class='rpfbids']//table/tbody/tr[.//a]")

    print(len(bid_nodes))
    records = []
    for node_idx, node in enumerate(bid_nodes, start = 1):
        bid_title = node.xpath("./td[1]/a[contains(@href,'.php')]")[0].text_content().strip()

        bid_no = extract_bid_no(bid_title)

        bid_due_date = node.xpath("./td[3]")[0].text_content().strip()

        formatted_date = regex_date_filter(bid_due_date)

        date_obj = None
        if formatted_date:
            try:
                date_obj = datetime.strptime(formatted_date,"%m/%d/%y").date()
            except ValueError as e:
                try:
                    date_obj = datetime.strptime(formatted_date,"%m/%d/%Y").date()
                except ValueError as e:
                    print("Couldn't parse the date into object")
                    continue
        if date_obj and date_obj <= datetime.today().date():
            continue

        records.append(
            {
                "title": bid_title,
                "url": base_url,
                "status": "NA",
                "due_date": formatted_date,   
                "bid_no": bid_no,
            }
        )

    for record_idx, record in enumerate(records):
        title = record["title"].strip()
        status = record["status"]
        due_date = record["due_date"]
        url = record["url"]
        bid_no = record["bid_no"]
        id =bid_no if bid_no else title[:10].strip()

        hash_val = generate_md5_hash(ecgains, id, None)

        if not check_for_duplicate_amr_hash(session, hash_val):
            print(f"[+] Inserting hash {hash_val}...")
            print(f"ecgains: {ecgains} number: {id} title: {title}  url1: {base_url}    description: {title} hash: {hash_val}`")
            insert_to_amr_database(
                session=session,
                ecgain=ecgains,
                number=id,
                title=title,
                due_date=due_date,
                broadcast_date=None,
                hash=hash_val,
                url1=base_url,
                url2=None,
                description=title,
            )
        else:
            print(f"[!] Duplicate hash {hash_val} found. Skipping insertion.")
    session.close()

print("AMR Records sucessfully inserted... Exiting")