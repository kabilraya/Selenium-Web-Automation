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
from utils.file_splitter import split_pdf
from utils.iconverter import get_iconverted_value

def regex_date_filter(raw_due_date:str) -> str:
    try:
        match = re.search(r'([a-zA-Z]+)\s+(\d{1,2}),\s*(\d{4})',raw_due_date)

        if match:
            date_str = match.group(0) #groups the matches into a single string
            parsed_date = datetime.strptime(date_str,"%B %d, %Y")
            due_date = f"{parsed_date.month}/{parsed_date.day}/{parsed_date.year}"
        else:
            due_date = None

        return due_date
    except Exception as e:
        print("error during parsing the date")


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
                    "file_size" : size_in_mb,
                    "md5_hash" : file_hash,
                    "iconverted" : iconverted
                }
                file_index += 1

        else:
            file[file_index] = {
                "file_name" : file_name_from_path,
                "sanitized_file_name" : file_name_from_path,
                "file_url" : file_url,
                "file_size" : mb_size,
                "md5_hash" : file_hash,
                "iconverted" : iconverted
            }
            file_index += 1 

    decoded_url = unquote(file_url)
    print(decoded_url)

    filename = os.path.basename(decoded_url.split("?")[0].strip()) or f"file_{file_index}"
    print(filename)

    new_file_name = santitize_file_name(filename)
    print(new_file_name)

    #we take the current window handle id to return to this handle
    #Here "main_window" is the main tab we open at the beginning of the scraping
    main_window =  sb.driver.current_window_handle
    # Seleniumbase automatically creates a directory named "downloaded_files" to keep the downloaded files
    sb.execute_script("window.open(arguments[0], '_blank');",file_url)
    sb.sleep(1)
    sb.switch_to_window(sb.driver.window_handles[-1])
    
    #try downloading the file
    try:
        sb.assert_downloaded_file(filename, timeout = 180, browser = False)
    except Exception as e:
        print("Dowloading failed")

        try:
            sb.close()
        except Exception as e:
            pass
        sb.switch_to_window(main_window)
        return {}

    #close the download tab and return to the main window
    try:
        sb.close()
    except Exception as e:
        pass

    sb.switch_to_window(main_window)



    source_path = os.path.join(script_directory,"downloaded_files",new_file_name)

    if not os.path.exists(source_path):
        source_path = os.path.join(script_directory,"downloaded_files",filename)

    if not os.path.exists(source_path):
        #ask the seleniumbase session to tell what file you got (name of the file in the downloaded files)

        print(f"{filename} was not found in the downloaded_files")
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
                               

