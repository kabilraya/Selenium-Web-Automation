#this is the global presets for storing commonly used functions
import os 
import re
import time
import zipfile
from urllib.parse import unquote
from datetime import datetime
import shutil
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from kabil_utils.file_splitter import split_pdf
from kabil_utils.iconverter import get_iconverted_value
import gdown
import requests
def is_downloadable_file(url, sb=None, debug=False):
    try:
        session = requests.Session()
        headers = {"Accept": "application/pdf,text/html,*/*"}

        if sb is not None:
            headers["User-Agent"] = sb.execute_script("return navigator.userAgent;")
            headers["Referer"] = sb.get_current_url()
            for c in sb.driver.get_cookies():
                session.cookies.set(c["name"], c["value"], domain=c.get("domain"))
        else:
            headers["User-Agent"] = (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )

        # (connect_timeout, read_timeout) — bounds a stalled/trickling response too
        resp = session.get(url, headers=headers, stream=True, timeout=(5, 10), allow_redirects=True)
        content_type = resp.headers.get('Content-Type', '').lower()
        content_disposition = resp.headers.get('Content-Disposition', '').lower()

        if debug:
            print(f"URL: {url} -> {resp.url} [{resp.status_code}] ct={content_type!r} cd={content_disposition!r}")

        resp.close()

        if content_disposition.split(';')[0].strip() == 'attachment':
            return True
        if any(content_type.startswith(t) for t in ('text/plain', 'text/html', 'image/', 'text/xml')):
            return False
        return True

    except requests.RequestException as e:
        if debug:
            print(f"  -> request failed: {e}")
        return False



_MONTHS = (
    r'(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|'
    r'Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'
)
_TEXT_DATE = re.compile(
    rf'\b({_MONTHS})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(\d{{4}})',
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



def santitize_file_name(url:str) -> str:
    root, ext = os.path.splitext(url)
    root = re.sub("[^a-zA-Z0-9_.-]","_",root)
    return f"{root}{ext}"


def download_files(sb, file_url, script_directory,download_path,file_index, file_hash):
    file = {}
    def process_single_file(file_path:str):
        #Take a single file from /download
        # Gets the size of the file in MB and bytes as well
        # Checks if the file is a pdf and >50MB then if it is >50MB
        # Calls the split_file() method
        # updates the file = {} dictionary
        nonlocal file_index
        bytes_size = os.path.getsize(file_path)
        mb_size = bytes_size / (1024 * 1024) 
        file_name_from_path = os.path.splitext(os.path.basename(file_path))[0]
        file_with_ext = os.path.basename(file_path)
        iconverted = get_iconverted_value(file_with_ext)

        if mb_size > 50:
            split_files = split_pdf(file_path=file_path)

            #this return a list of tuple [(file_name, size_in_mb, path)].
            # So we iterate over and update the file = {} with proper indexing

            for file_name, size_in_mb, path in split_files:

                file[file_index] = {
                    "file_name" : file_name,
                    "sanitized_file_name" : file_name,
                    "file_url" : file_url,
                    "file_size" : f"{size_in_mb:.2f} MB",
                    "md5_hash" : file_hash,
                    "iconverted" : iconverted
                }
                file_index += 1

        else:
            file[file_index] = {
                "file_name" : os.path.basename(file_path),
                "sanitized_file_name" : os.path.basename(file_path),
                "file_url" : file_url,
                "file_size" : f"{mb_size:.2f} MB",
                "md5_hash" : file_hash,
                "iconverted" : iconverted
            }
            file_index += 1 

    #we take the current window handle id to return to this handle
    #Here "main_window" is the main tab we open at the beginning of the scraping
    
    # Seleniumbase automatically creates a directory named "downloaded_files" to keep the downloaded files
    downloaded_files_dir = os.path.join(script_directory, "downloaded_files")
    os.makedirs(downloaded_files_dir, exist_ok=True)
    before_files = set(os.listdir(downloaded_files_dir))
    # sb.hover_and_click(hover_selector = "//button[@aria-label='Download']", click_selector="//button[@aria-label='Download']")
    # sb.sleep(3)
    gdown.download(url = file_url, output = downloaded_files_dir, quiet=True)

    #try downloading the file
    partial_exts = (".crdownload", ".part", ".tmp", ".download")
    timeout = 300
    poll_interval = 0.5
    deadline = time.time() + timeout
    actual_file_name = None

    while time.time() < deadline:
        current_files = set(os.listdir(downloaded_files_dir))
        new_files = current_files - before_files
        completed = [f for f in new_files if not f.lower().endswith(partial_exts)]

        if completed:
            completed.sort(key=lambda f: os.path.getmtime(os.path.join(downloaded_files_dir, f)), reverse=True)
            candidate = completed[0]
            candidate_path = os.path.join(downloaded_files_dir, candidate)
            size1 = os.path.getsize(candidate_path)
            time.sleep(0.3)
            size2 = os.path.getsize(candidate_path)
            if size1 == size2 and size1 > 0:
                actual_file_name = candidate
                break

        time.sleep(poll_interval)

    
    print(actual_file_name)

    

    

    new_file_name = santitize_file_name(actual_file_name)
    print(new_file_name)


    source_path = os.path.join(script_directory,"downloaded_files",new_file_name)

    if not os.path.exists(source_path):
        source_path = os.path.join(script_directory,"downloaded_files",actual_file_name)

    if not os.path.exists(source_path):
        #ask the seleniumbase session to tell what file you got (name of the file in the downloaded files)

        print(f"{actual_file_name} was not found in the downloaded_files")
        print(f"SB dowloaded files as {sb.get_downloaded_files(browser = False)}")

        return{}
    

    os.makedirs(download_path,exist_ok=True)
    final_path = os.path.join(download_path,new_file_name)
    shutil.move(source_path,final_path)
    file_ext = os.path.splitext(final_path)[1].lower()
    
    if file_ext == ".zip":
        
        zip_directory = os.path.dirname(final_path) #this gives /download
        folder_name = os.path.splitext(os.path.basename(final_path))[0]
            #this just gives out the name of the zip
    
        # Temporary extraction directory:
        # /download/myfile
        extract_path = os.path.join(
            zip_directory,
            folder_name
        ) #extracted to download/myzip
    
        os.makedirs(extract_path, exist_ok=True)
    
        # Extract temporarily
        with zipfile.ZipFile(final_path, "r") as zip_reader:
            zip_reader.extractall(extract_path)
        # Walk through /download/myfile/
        for root, _, files in os.walk(extract_path):
    
            for file_name in files:
                sanitized_file_name = santitize_file_name(file_name)
                
                source_path = os.path.join(root, file_name)
                destination_path = os.path.join(
                    zip_directory,
                    sanitized_file_name
                )
                

                shutil.move(source_path, destination_path)
                process_single_file(destination_path)
        shutil.rmtree(extract_path)
        os.remove(final_path)

    else:
        process_single_file(final_path)
    return file
                               

