import json
import os
from .db_duplicate_bid_checker import check_duplicate_bids
from .session_creator import create_database_session
from .insert_into_db import insert_into_db
def extract_from_json_and_insert(json_path,db_url):
    keys_to_skip = ["ecgains","module_name","base_url","download_path"]

    try:
        with open(json_path,"r") as f:
            json_data = json.load(f)

        session, _ = create_database_session(database_url=db_url)

        ecgains = json_data["ecgains"]
        module_name = json_data["module_name"]
        base_url = json_data["base_url"]
        download_path = json_data["download_path"]
        total_bid = 0
        total_new_bid = 0
        total_new_bid_files = 0
        for key, value in json_data.items():
            if key not in keys_to_skip and key.isdigit():
                total_bid += 1
                is_bid_duplicate = check_duplicate_bids(session=session, bid_no=value["bid_no"])

                for index in range(1,len(value["files_info"])+1):
                    # insert_into_db()
                    insert_into_db(session=session,
                                   ecgains=ecgains,
                                   file_hash=value["files_info"][str(index)]["md5_hash"],
                                   bid_no=value["bid_no"],
                                   title = value["bid_title"],
                                   due_date= value["bid_due_date"],
                                   base_url= base_url,
                                   file_url= value["files_info"][str(index)]["file_url"],
                                   module_name=module_name,
                                   file_name = value["files_info"][str(index)]["sanitized_file_name"],
                                   iconverted= value["files_info"][str(index)]["iconverted"],
                                   file_size=value["files_info"][str(index)]["file_size"]
                                   )
                    if not is_bid_duplicate:
                        total_new_bid_files += 1
                if not is_bid_duplicate:
                    total_new_bid += 1
        return{
        "total_bid": total_bid,
        "total_new_bid": total_new_bid,
        "total_new_bid_file": total_new_bid_files
        }
    finally:
        session.close()

                                
                    