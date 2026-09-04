#this is the global presets for storing commonly used functions
import os 
import re
import time
import zipfile
from urllib.parse import unquote, urlsplit
from datetime import datetime
import shutil
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from kabil_utils.file_splitter import split_pdf
from kabil_utils.iconverter import get_iconverted_value
import requests
from urllib.parse import urlsplit
import re
from urllib.parse import unquote
import json
def extract_asset_urn(viewer_url: str) -> str | None:
    m = re.search(r"urn:aaid:sc:[A-Za-z0-9]+:[a-f0-9-]+", viewer_url)
    return m.group(0) if m else None


def extract_filename_from_response(response, fallback="downloaded_file.pdf"):
    cd = response.headers.get("content-disposition", "")
    match = re.search(r'filename\*?=["\']?([^"\';]+)', cd)
    if not match:
        return fallback
    return unquote(match.group(1)).strip()


def _write_response_to_disk(r, download_path, fallback_stub):
    """Streams a requests.Response to disk and verifies size against
    Content-Length. Returns (final_path, filename) or (None, None)."""
    expected_size = int(r.headers.get("content-length", 0))
    filename = extract_filename_from_response(r, fallback=f"{fallback_stub}.pdf")
    sanitized = santitize_file_name(filename)  # existing helper in functions.py
    final_path = os.path.join(download_path, sanitized)

    os.makedirs(download_path, exist_ok=True)

    try:
        with open(final_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 16):
                if chunk:
                    f.write(chunk)
    except requests.exceptions.RequestException as e:
        print(f"Error while streaming response body: {e}")
        if os.path.exists(final_path):
            os.remove(final_path)
        return None, None

    actual_size = os.path.getsize(final_path)
    if expected_size and actual_size != expected_size:
        print(f"WARNING: size mismatch — expected {expected_size}, got {actual_size}. Discarding file.")
        os.remove(final_path)
        return None, None

    return final_path, filename


def _wait_for_page_ready(sb, timeout=15):
    """Polls document.readyState instead of trusting a fixed sleep."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            state = sb.execute_script("return document.readyState")
            if state == "complete":
                return True
        except Exception:
            pass
        sb.sleep(0.5)
    return False


def _capture_access_token_and_blob(sb, poll_timeout=25):
    """Single pass over CDP performance logs. Captures whichever signal(s)
    show up:
      - access_token: fires on essentially every Adobe viewer request
        (renditions, metadata) — cheap, unconditional signal.
      - blob_url: only fires if the viewer decides to fetch the FULL file
        (large/content-dense docs feeding the AI-summary feature). Not
        guaranteed to appear for short/simple documents.

    Returns (access_token_or_None, blob_url_or_None).
    """
    access_token, blob_url = None, None
    deadline = time.time() + poll_timeout
    seen_ids = set()

    while time.time() < deadline and not (access_token and blob_url):
        try:
            logs = sb.driver.get_log("performance")
        except Exception as e:
            print(f"get_log('performance') failed: {e}")
            logs = []

        for entry in logs:
            try:
                msg = json.loads(entry["message"])["message"]
            except (KeyError, json.JSONDecodeError):
                continue

            if msg.get("method") != "Network.responseReceived":
                continue

            req_id = msg["params"]["requestId"]
            if req_id in seen_ids:
                continue
            seen_ids.add(req_id)

            resp = msg["params"].get("response", {})
            url = resp.get("url", "")

            if not access_token:
                m = re.search(r"access_token=([^&]+)", url)
                if m:
                    # Decode exactly once. The value in the network log URL
                    # is already percent-encoded (':' shows as '%3A').
                    # `requests` will percent-encode whatever we pass in
                    # params= before sending, so if we don't decode first,
                    # ':' -> '%3A' -> '%253A' on the wire -> signature
                    # mismatch -> 403.
                    access_token = unquote(m.group(1))

            if not blob_url and resp.get("mimeType") == "application/pdf" and "blobstore" in url:
                blob_url = url

        if not (access_token and blob_url):
            sb.sleep(0.5)

    return access_token, blob_url


def download_adobe_pdf(sb, viewer_url, download_path, poll_timeout=25):
    main_window = sb.driver.current_window_handle

    sb.execute_script("window.open(arguments[0], '_blank');", viewer_url)
    sb.sleep(1)

    try:
        sb.switch_to_window(sb.driver.window_handles[-1])
    except Exception as e:
        print(f"Could not switch to new tab for {viewer_url}: {e}")
        sb.switch_to_window(main_window)
        return None, None

    sb.driver.execute_cdp_cmd("Network.enable", {})

    blob_url = None
    deadline = time.time() + poll_timeout
    seen_ids = set()

    while time.time() < deadline and not blob_url:
        for entry in sb.driver.get_log("performance"):
            try:
                msg = json.loads(entry["message"])["message"]
            except (KeyError, json.JSONDecodeError):
                continue
            if msg.get("method") != "Network.responseReceived":
                continue
            req_id = msg["params"]["requestId"]
            if req_id in seen_ids:
                continue
            seen_ids.add(req_id)

            resp = msg["params"].get("response", {})
            if resp.get("mimeType") == "application/pdf" and "blobstore" in resp.get("url", ""):
                blob_url = resp["url"]
                break
        if not blob_url:
            sb.sleep(0.5)

    try:
        sb.driver.close()
    except Exception:
        pass
    sb.switch_to_window(main_window)

    if not blob_url:
        print(f"Never saw the blobstore PDF request for {viewer_url}")
        return None, None

    r = requests.get(blob_url, stream=True, timeout=120)
    r.raise_for_status()
    return _write_response_to_disk(r, download_path, "blobstore_file")

def regex_date_filter(raw_due_date: str) -> str | None:
    try:
        match = re.search(r'([a-zA-Z]+)\s+(\d{1,2})(?:st|nd|rd|th)?,\s*(\d{4})', raw_due_date, re.IGNORECASE)

        if not match:
            return None

        month, day, year = match.group(1), match.group(2), match.group(3)
        date_str = f"{month} {day}, {year}"

        try:
            parsed_date = datetime.strptime(date_str, "%B %d, %Y")
        except ValueError:
            try:
                parsed_date = datetime.strptime(date_str, "%b %d, %Y")
            except ValueError as e:
                print(f"Could not parse date: {raw_due_date!r} — {e}")
                return None

        due_date = f"{parsed_date.month}/{parsed_date.day}/{parsed_date.year}"
        return due_date

    except Exception as e:
        print(f"error during parsing the date: {e}")
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
    main_window =  sb.driver.current_window_handle
    # Seleniumbase automatically creates a directory named "downloaded_files" to keep the downloaded files
    downloaded_files_dir = os.path.join(script_directory, "downloaded_files")
    os.makedirs(downloaded_files_dir, exist_ok=True)
    if urlsplit(file_url).netloc == "acrobat.adobe.com":
        final_path, real_filename = download_adobe_pdf(sb, file_url, download_path)
        if final_path:
            process_single_file(final_path)
        return file

    before_files = set(os.listdir(downloaded_files_dir))
    sb.execute_script("window.open(arguments[0], '_blank');", file_url)
    sb.sleep(5)
    sb.switch_to_window(sb.driver.window_handles[-1])

    #try downloading the file
    partial_exts = (".crdownload", ".part", ".tmp", ".download")
    timeout = 180
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

    if actual_file_name is None:
        print("Downloading failed")
        try:
            sb.assert_downloaded_file(actual_file_name,timeout=120, browser = False)
        except Exception as e:
            print(f"Downloading Failed with the following exception: {e}")

            try:
                if len(sb.driver.window_handles) > 1:
                    sb.driver.close()
            except Exception as e:
                pass
            sb.switch_to_window(main_window)
            return {}

    print(actual_file_name)

    #close the download tab and return to the main window
    try:
        sb.close()
    except Exception as e:
        pass

    sb.switch_to_window(main_window)

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
                               

