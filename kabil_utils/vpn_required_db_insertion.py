import json
import os
import sys
import time
from urllib.parse import quote
from pathlib import Path
from datetime import datetime


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from kabil_utils.md5_generator import generate_md5_hash
from kabil_utils.session_creator import create_database_session
from kabil_utils.db_duplicate_hash_checker import check_for_duplicate_hash

from kabil_utils.extract_and_insertion import extract_from_json_and_insert
from kabil_utils.record_data_insertion import insert_into_record_db
from kabil_utils.db_value_updater import update_value
from kabil_utils.file_remover import delete_files_in_directory
from kabil_utils.get_env import get_env
from kabil_utils.db_duplicate_bid_checker import check_duplicate_bids
from kabil_utils.boto_client import boto_client_insertion
from kabil_utils.insert_into_db import insert_into_db






def extract_from_json_and_add_to_db(
    json_path,
    db_url,
    region_name,
    endpoint_url,
    aws_access_key_id,
    aws_secret_access_key
) -> dict:
    """
    Extracts data from a JSON file and adds it to a database.

    Args:
        path_to_json (str): The path to the JSON file.
        db_url (str): The URL of the database.
        region_name (str): The name of the AWS region.
        endpoint_url (str): The endpoint URL for the AWS service.
        aws_access_key_id (str): The AWS access key ID.
        aws_secret_access_key (str): The AWS secret access key.

    Returns:
        dict: A dictionary containing the total number of bids, total number of new bids, and total number of new bid files.
    """
    keys_to_skip = {"ecgains", "module_name", "base_url", "download_path"}

    try:
        with open(json_path, "r") as f:
            json_data = json.load(f)
        session,_ = create_database_session(database_url=db_url)

        ecgains = json_data["ecgains"]
        module_name = json_data["module_name"]
        base_url = json_data["base_url"]
        download_path = json_data["download_path"]
        server_path = json_data["server_path"]

        total_bid = 0
        total_new_bid = 0
        total_new_bid_file = 0
        for key, value in json_data.items():
            if key not in keys_to_skip and key.isdigit():
                total_bid += 1
                    
                is_bid_duplicate = check_duplicate_bids(session=session, bid_no=value["bid_no"])

                
                for index in range(1, len(value["files_info"]) + 1):

                    
                    is_duplicate = check_for_duplicate_hash(
                        session=session, hash=value["files_info"][str(index)]["md5_hash"]
                    )
                    if is_duplicate:
                        print(
                            "Hash Duplication Fount"
                        )
                        continue
                    
                    boto_client_insertion(
                        bid_no=value["bid_no"],
                        download_dir=download_path,
                        filename=value["files_info"][str(index)]["sanitized_file_name"],
                        server_path=server_path,
                        region_name=region_name,
                        endpoint_url=endpoint_url,
                        aws_access_key_id=aws_access_key_id,
                        aws_secret_access_key=aws_secret_access_key
                    )
                    
                    insert_into_db(session=session,
                                   ecgains=ecgains,
                                   file_hash=value["files_info"][str(index)]["md5_hash"],
                                   bid_no=value["bid_no"],
                                   title = value["bid_title"],
                                   due_date= value["bid_due_date"],
                                   base_url= base_url,
                                   file_url= value["files_info"][str(index)]["file_url"],
                                   module_name=module_name,
                                   file_name = value["files_info"][str(index)]["file_name"],
                                   cloud_url=os.path.join(server_path, quote(str(value["bid_no"])[:25]), value["files_info"][str(index)]["sanitized_file_name"]).replace("\\", "/"),
                                   iconverted= value["files_info"][str(index)]["iconverted"],
                                   file_size=value["files_info"][str(index)]["file_size"]
                                    )
                    
                    if not is_bid_duplicate:
                        total_new_bid_file += 1

                if not is_bid_duplicate:
                    total_new_bid += 1

        return {
            "total_bid": total_bid,
            "total_new_bid": total_new_bid,
            "total_new_bid_file": total_new_bid_file
        }
    finally:
        session.close()

    