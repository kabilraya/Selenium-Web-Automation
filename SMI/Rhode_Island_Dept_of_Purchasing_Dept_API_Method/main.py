import os
import sys
import random
from collections import OrderedDict
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs
import json
import requests
from dotenv import load_dotenv
from seleniumbase import SB
from sqlalchemy import text

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from kabil_utils.get_env import get_env
from kabil_utils.session_creator import create_database_session
from functions import download_files,regex_date_filter
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)



ECGAIN = "02-39-005-0020-000000"
FILE_API_URL = "https://webprocure.proactiscloud.com/wp-full-text-search/soldetail/{bid}?customerid=46"
bid_attachment_url = "https://webprocure.proactiscloud.com/wp-web-public/en/#/bidboard/bid/{bid}?pagenumber=1&customerid=46&oid=120002&shorBy=r"
MAX_AGE_DAYS = 20
updateStURL2 = "https://webprocure.proactiscloud.com/wp-full-text-search/soldetail/{bid}?customerid=46"
TABLE = "tbl_WebBid"              
COL_ID = "webID"            
COL_ECGAIN = "ECGAINS"
COL_BIDNO = "stBidNo"
COL_URL2 = "stURL2"
COL_CLOUD = "stFileCloudURL"       
COL_ENTRY = "stCrawled"            
COL_HASH = "stHash"

script_directory = os.path.dirname(os.path.abspath(__file__))
load_dotenv()
[
    ecgains, module_name, main_url, download_path, server_path,
    smi_data_url, smi_record_url, region_name, endpoint_url,
    aws_access_key_id, aws_secret_access_key,
] = get_env(os.path.join(script_directory, ".env"))
download_path = os.path.join(script_directory, "download")
RESPONSE_FILE = os.path.join(script_directory, "last_api_response.json")
cloud = {
    "server_path": server_path,
    "region_name": region_name,
    "endpoint_url": endpoint_url,
    "aws_access_key_id": aws_access_key_id,
    "aws_secret_access_key": aws_secret_access_key,
}

def get_failed_rows(session):
    """Rows of this ecgain with no cloud URL, entered within the last MAX_AGE_DAYS days."""
    cutoff = datetime.now() - timedelta(days=MAX_AGE_DAYS)
    q = text(f"""
        SELECT {COL_ID}, {COL_BIDNO}, {COL_URL2}, {COL_HASH}
        FROM {TABLE}
        WHERE {COL_ECGAIN} = :ecgain
          AND ({COL_CLOUD} IS NULL OR TRIM({COL_CLOUD}) = '')
          AND {COL_URL2} IS NOT NULL
          AND {COL_ENTRY} >= :cutoff
        ORDER BY {COL_BIDNO}, {COL_ID}
    """)
    result = session.execute(q, {"ecgain": ECGAIN, "cutoff": cutoff})
    return [dict(r._mapping) for r in result]
    # r._mapping creates a python dictionary for the row objects with the column name as the key and the corresponding values
    


def parse_url2(url):
    """.../MainBidBoard?ac=4&bid=146484&owner_id=120002&docid=1979202 -> ('146484', '1979202')"""
    q = {k.lower(): v[0] for k, v in parse_qs(urlparse(url or "").query).items()}
    return q.get("bid"), q.get("docid")
    #URLparse(url) parses the URL and creates different labels such as domain, protocol, query 
    # .query gives the part of the url after the ? 
    # parse_qs creates a dictionary with key and [values] -> if the key repeats it creates a list of the values


def group_by_bid_no(rows):
    groups = OrderedDict()
    for row in rows:
        groups.setdefault(row[COL_BIDNO], []).append(row)
    return groups
# OrderedDict creates a dictionary and if the key exists it acts as a simple dictionary
# But if the key doesn't exist it creates a default in this case it is [] and appends the value
# setdefault(key,default) -> if the key exists, appeand the value but if not create a default and append


def fetch_docs(bid):
    
    r = requests.get(
        FILE_API_URL.format(bid=bid),
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json"
        },
        timeout=30,
        verify=False,
    )

    print(f"\nAPI BID: {bid}")
    print(f"Status: {r.status_code}")
    print(f"Content-Type: {r.headers.get('Content-Type')}")
    print(f"Response Size: {len(r.content)} bytes")

    r.raise_for_status()
    data = r.json()

    response_file = os.path.join(
        script_directory,
        f"api_response_{bid}.json"
    )

    with open(response_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    records = data.get("records", [])

    print(f"Records found: {len(records)}")

    docs = {}

    for rec in records:
        for d in rec.get("bidDocs", []):
            dd = d["docAssoc"]["docDoc"]

            docs[str(dd["docid"])] = {
                "name": dd.get("name") or "",
                "upload": dd.get("uploadFileName") or "",
                "hidden": dd.get("hidden"),
            }

    print(f"Documents extracted: {len(docs)}")

    return docs

SEARCH_API_URL = (
    "https://webprocure.proactiscloud.com/"
    "wp-full-text-search/search/sols"
)
SEARCH_API_URL = (
    "https://webprocure.proactiscloud.com/"
    "wp-full-text-search/search/sols"
)
def get_bid_id(bidno):
    try:
        r = requests.get(
            SEARCH_API_URL,
            params={
                "customerid": 46,
                "q": bidno,
                "from": 0,
                "sort": "od-d",
                "f": "",
                "oids": "",
            },
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json",
            },
            timeout=30,
            verify=False,
        )

        r.raise_for_status()
        data = r.json()

        records = data.get("records", [])

        # Find the exact bid number rather than assuming
        # the first search result is the correct one.
        for record in records:
            if str(record.get("bidNumber", "")).strip().upper() == str(bidno).strip().upper():
                bid_id = record.get("bidid")

                print(f"[{bidno}] Found bid ID: {bid_id}")
                return str(bid_id) if bid_id is not None else None

        print(f"[{bidno}] No matching bid found (hits={data.get('hits', 0)})")
        return None

    except Exception as e:
        print(f"[{bidno}] Failed to retrieve bid ID: {e}")
        return None

def build_download_button(filename):
    
    return f"//ul[@class='custom-collection']/li//a[contains(normalize-space(),'{filename}')]"


def open_bid_page(sb, page_url):
    sb.uc_open_with_reconnect(page_url, reconnect_time=6)
    sb.sleep(4)
    sb.switch_to_default_content()


def main():
    
    session, _ = create_database_session(database_url=smi_data_url)
    try:
        
        rows = get_failed_rows(session)
        groups = group_by_bid_no(rows)
        print(f"{len(rows)} failed rows across {len(groups)} bid numbers")

        with SB(uc=True, test=True, headless=False, incognito=False, undetectable=True,
                xvfb=False, guest_mode=False, disable_features="ChromePDFViewer",
                external_pdf=True, locale="en") as sb:

            for bid_no, group_rows in groups.items():
                
                bid_id = get_bid_id(bidno=bid_no)
                new_url = updateStURL2.format(bid = bid_id)
                if not bid_id:
                    print(f"[{bid_no}] has no bid_id")
                    continue
                open_url = bid_attachment_url.format(bid = bid_id)
                try:
                    docs = fetch_docs(bid_id)
                    
                except Exception as e:
                    print(f"[{bid_no}] API failed: {e}")
                    continue

                open_bid_page(sb, open_url)
                sb.sleep(5)
                end_date_xpath = "//div[contains(normalize-space(),'End Date')][./div[1]/span[@class='teal-text']]/div[2]"

                # Waits for the element to be visible, then returns its text
                end_date = sb.get_text(end_date_xpath).strip()

                formatted_date = regex_date_filter(end_date)
                for row in group_rows:
                    page_url = row[COL_URL2]
                    _, docid = parse_url2(page_url)
                    doc = docs.get(str(docid))
                    if not doc:
                        print(f"[{bid_no}] docid {docid} not in API response, skipping")
                        continue

                    

                   
                    button = None
                    print(doc["name"])
                    xp = build_download_button(doc["name"])
                    print(xp)
                    if sb.is_element_present(xp):
                        button = xp
                
                    if button is None:
                        print("button not found")
                        continue

                    result = download_files(
                        sb=sb,
                        script_directory=script_directory,
                        download_path=download_path,
                        file_index=1,
                        file_hash=row.get(COL_HASH),
                        download_button=button,
                        session=session,      
                        bid_no=bid_no,        
                        url2=page_url,
                        new_url2=new_url,
                        cloud=cloud,
                        formatted_date = formatted_date
                    )
                    if not result:
                        print(f"[{bid_no}] download failed for {doc['name']!r}, will retry next run")
                        continue

                    
                    

                  

                    sb.sleep(random.uniform(3, 6))
    finally:
        session.close()


if __name__ == "__main__":
    main()