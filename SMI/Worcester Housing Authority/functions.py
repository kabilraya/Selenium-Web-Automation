#this is the global presets for storing commonly used functions
import os 
import re
import time
import zipfile
from urllib.parse import unquote
from datetime import datetime
import shutil
import sys
import requests
from pydub import AudioSegment
from urllib.parse import urlparse
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from kabil_utils.file_splitter import split_pdf
import speech_recognition as sr
import inflect
from typing import Tuple, Dict, Optional
from io import BytesIO
import pyautogui
from pyautogui import ImageNotFoundException
from kabil_utils.iconverter import get_iconverted_value
from seleniumbase.common.exceptions import ElementNotVisibleException
COCO_CLASSES = {
    1: "person",
    2: "bicycle",
    3: "car",
    4: "motorcycle",
    5: "airplane",
    6: "bus",
    7: "train",
    8: "truck",
    9: "boat",
    10: "traffic light",
    11: "fire hydrant",
    13: "stop sign",
    14: "parking meter",
    15: "bench",
    16: "bird",
    17: "cat",
    18: "dog",
    19: "horse",
    20: "sheep",
    21: "cow",
    22: "elephant",
    23: "bear",
    24: "zebra",
    25: "giraffe",
    27: "backpack",
    28: "umbrella",
    31: "handbag",
    32: "tie",
    33: "suitcase",
    34: "frisbee",
    35: "skis",
    36: "snowboard",
    37: "sports ball",
    38: "kite",
    39: "baseball bat",
    40: "baseball glove",
    41: "skateboard",
    42: "surfboard",
    43: "tennis racket",
    44: "bottle",
    46: "wine glass",
    47: "cup",
    48: "fork",
    49: "knife",
    50: "spoon",
    51: "bowl",
    52: "banana",
    53: "apple",
    54: "sandwich",
    55: "orange",
    56: "broccoli",
    57: "carrot",
    58: "hot dog",
    59: "pizza",
    60: "donut",
    61: "cake",
    62: "chair",
    63: "couch",
    64: "potted plant",
    65: "bed",
    67: "dining table",
    70: "toilet",
    72: "tv",
    73: "laptop",
    74: "mouse",
    75: "remote",
    76: "keyboard",
    77: "cell phone",
    78: "microwave",
    79: "oven",
    80: "toaster",
    81: "sink",
    82: "refrigerator",
    84: "book",
    85: "clock",
    86: "vase",
    87: "scissors",
    88: "teddy bear",
    89: "hair drier",
    90: "toothbrush",
}

engine = inflect.engine() 
CAPTCHA_TIMEOUT = 7
IMAGE_FOLDER = "images"
CAPTCHA_API_URL = "http://127.0.0.1:8000"

def is_direct_download_link(url:str):
    parsed_url = urlparse(url) # Parse the url into a dictionary having "domain", "protocol", "path", "query-params"
    path = parsed_url.path #Gets the path
    extension = os.path.splitext(path)[1].lower()

    return extension != ""

def get_label_and_grid_size(sb) -> Tuple[str, Tuple[int, int], bool]:
    """Extracts target label and grid configuration from reCAPTCHA."""
    sb.sleep(2)
    raw_instructions = sb.get_text(
        selector=".rc-imageselect-desc",
        by="css selector",
        timeout=CAPTCHA_TIMEOUT,
    )
    instructions = raw_instructions.split("\n")
    raw_label = instructions[-1] if len(instructions) == 2 else instructions[-2]
    if raw_label == "a fire hydrant":
        target_label = "fire hydrant"
    elif raw_label == "bus":
        target_label = "bus"
    else:
        target_label = engine.singular_noun(raw_label) or raw_label
    grid_size = (
        (4, 4) if "select all squares with" in raw_instructions.lower() else (3, 3)
    )
    solve_again = any(
        phrase in raw_instructions.lower()
        for phrase in [
            "if there are none, click skip",
            "click verify once there are none left",
        ]
    )
    return target_label, grid_size, solve_again

def get_image_data(sb) -> BytesIO:
    """Captures captcha image as BytesIO."""
    xpath_for_image = "fdsfdsf" #Here goes the xpath for the div containing the entire image.
    
    image = sb.find_element(
        xpath_for_image, timeout=CAPTCHA_TIMEOUT
    )
    png_bytes = image.screenshot_as_png

    with open("captcha_screenshot.png", "wb") as f:
        f.write(png_bytes)

    return BytesIO(png_bytes)

def detect_objects_in_captcha(
    image_data: BytesIO, target_label: str, grid_size: Tuple[int, int]
) -> Dict:
    """Sends image to detection API and returns results."""
    response = requests.post(
        f"{CAPTCHA_API_URL}/detect",
        files={"image": ("image.jpg", image_data, "image/jpeg")},
        data={
            "target_label": target_label,
            "grid_rows": grid_size[0],
            "grid_cols": grid_size[1],
        },
    )

    return response.json()

def click_captcha_grid_cells(sb, grid_indexes: list, cols: int):
    """Clicks specified grid cells in the captcha."""
    for grid_index in grid_indexes:
        row = (grid_index // cols) + 1
        col = (grid_index % cols) + 1

        element = sb.find_element(
            f"/html/body/div/div/div[2]/div[2]/div/table/tbody/tr[{row}]/td[{col}]"  
            #This is the xpath pointing to the grid indexes in the captcha from the table.
        )

        sb.hover_and_click(element,timeout = 3)

def check_captcha_error(sb) -> Optional[str]:
    """Checks for captcha error messages."""
    error_selectors = [
        "div.rc-imageselect-incorrect-response",
        "/html/body/div/div/div[2]/div[4]",
    ]

    for selector in error_selectors:
        try:
            by = "css selector" if selector.startswith("div") else "xpath"
            error_msg = sb.get_text(
                selector=selector, by=by, timeout=CAPTCHA_TIMEOUT
            ).strip()
            if error_msg:
                return error_msg
        except ElementNotVisibleException:
            continue

    return None

def solve_image_captcha(sb):
    iframe_one_xpath = "//iframe[@title='reCAPTCHA']"
    iframe_two_xpath = "//iframe[contains(@title, 'challenge')]"
    checkbox_xpath = "//span[contains(@class, 'recaptcha-checkbox')]"
    sb.switch_to_default_content()

    sb.switch_to_frame(iframe_one_xpath,timeout=3)

    try:
        checked_checkbox = "//span[@id='recaptcha-anchor' and @aria-checked='true']"
        checked = sb.wait_for_element_present(checked_checkbox,timeout = 5)
        if checked:
            print("The checkbox is checked")
            return True
                
    except Exception as e:
        return False

    sb.switch_to_frame(iframe_two_xpath,timeout = 3)

    target_label, grid_size, solve_again = get_label_and_grid_size(sb)
    first_time = True
    no_of_times_solved = 0
    xpath_close_button = ""
    xpath_verify_button = ""
    def reload_captcha():
        nonlocal first_time, target_label, grid_size, solve_again
        reload_xpath = "fdfsd" #Here the xpath for the reload button goes for each website
        sb.click(reload_xpath, timeout=3)
        first_time = True
        sb.sleep(2)
        target_label, grid_size, solve_again = get_label_and_grid_size(sb)

        while True:
            if target_label not in COCO_CLASSES.values():
                reload_captcha()
                continue

            #get the image data and store it in memory using BytesIO
            image_data = get_image_data(sb)
            response = detect_objects_in_captcha(image_data, target_label, grid_size)

            total_detections = response["total_detections"]
            grid_indexes = response["grid_indexes"]
            cols = response["grid_size"]["cols"]

            # Handle no detections on first attempt
            if first_time and not total_detections:
                reload_captcha()
                continue

            # Handle no detections on subsequent attempts
            if not first_time and not total_detections:
                # Check if captcha still visible
                try:
                    checked_checkbox = "//span[@id='recaptcha-anchor' and @aria-checked='true']"
                    checked = sb.wait_for_element_present(checked_checkbox,timeout = 5)
                    if checked:
                        print("The checkbox is checked")
                        return True
                                
                except Exception as e:
                    break
            # Click detected grid cells
            if total_detections:
                click_captcha_grid_cells(sb, grid_indexes, cols)
                no_of_times_solved += 1

            # Handle multi-round solving for 3x3 grids
            if solve_again and grid_size[0] != 4:
                first_time = False
                sb.sleep(6)
                continue

            # Verify solution
            sb.click(xpath_verify_button,timeout = 3)

            error_msg = check_captcha_error(sb)
            if error_msg:
                reload_captcha()
                continue

            try:
                checked_checkbox = "//span[@id='recaptcha-anchor' and @aria-checked='true']"
                checked = sb.wait_for_element_present(checked_checkbox,timeout = 5)
                if checked:
                    print("The checkbox is checked")
                    return True
                            
            except Exception as e:
                reload_captcha()
                break
    

def audio_solver(sb):
    #This is the function that gets the download URL of the audio
    #Pass it to some model and get the text and enter the text field with the value
    #When the function is called the state the SB is in the iframe of the audio challenge 
    #After clicking the audio challenge button 
    audio_source = sb.wait_for_element_present("audio", timeout=10)
    audio_url = audio_source.get_attribute("src")

    
    try:
        
        response = requests.get(audio_url, timeout=10)
        response.raise_for_status()

        with open("audio.mp3", "wb") as f:
            f.write(response.content)

        # Convert MP3 → WAV
        sound = AudioSegment.from_mp3("audio.mp3")
        sound.export("audio.wav", format="wav")

        # Speech recognition
        recognizer = sr.Recognizer()

        with sr.AudioFile("audio.wav") as source:
            audio = recognizer.record(source)

        text = recognizer.recognize_google(audio)
        return text
    except Exception as e:
        print("Failed to recognize the voice")
        return ""

def form_filling(sb , 
                 company_name:str = "Arlington School", 
                 email:str = "johndoe12@gmail.com", 
                 last_name = "Doe", 
                 first_name = "John", 
                 street_address = "New York", 
                 city = "New York",
                 state = "state", 
                 code:int = 44600):
    sb.type("//input[@name='input_1']",company_name)
    sb.type("//input[@name='input_3']",email)
    sb.type("//input[@name='input_4']",last_name)
    sb.type("//input[@name='input_5']",first_name)
    sb.type("//input[@name='input_6']",street_address)
    sb.type("//input[@name='input_7']",city)
    sb.type("//input[@name='input_8']",state)
    sb.type("//input[@name='input_9']",code)



def solve_captcha(sb):
    
    iframe_one_xpath = "//iframe[@title='reCAPTCHA']"
    iframe_two_xpath = "//iframe[contains(@title, 'challenge')]"
    checkbox_xpath = "//span[contains(@class, 'recaptcha-checkbox')]"
    audio_xpath = "//button[@id='recaptcha-audio-button']"
    play_button = "//button[@aria-labelledby='audio-instructions rc-response-label']"

    def is_captcha_solved():
        """This checks whether or not the Captcha is solved by checking the chekbox (Checked->True, Not Checked->False)

        Args:
            Inner helper function so can access anything (ReadOnly)
        Returns:
            _type_: _description_
        """
        try:
            checked_checkbox = "//span[@id='recaptcha-anchor' and @aria-checked='true']"
            checked = sb.wait_for_element_present(checked_checkbox,timeout = 5)
            if checked:
                print("The checkbox is checked")
                return True
            
        except Exception as e:
            return False

    # We switch to the default content outside from all the iframes

    sb.switch_to_default_content()

    #switch to the iframe with a certain timeout mentioned
    # SB automatically waits for the iframe to be available
    # In Selenium: WebdriverWait(drive,timeout).until(EC.frame_to_be_available_and_switch_to_it(By.XPATH,xpath_to_iframe))
    # In SeleniumBase

    sb.switch_to_frame(iframe_one_xpath,timeout = 5)
    sb.hover_and_click(hover_selector=checkbox_xpath, click_selector=checkbox_xpath)
    time.sleep(3)
    #Checks if the captcha is solved
    if is_captcha_solved():
        print("Captcha is solved")
        #switch to the default window
        sb.switch_to_default_content()
        return True

    time.sleep(3)
    sb.switch_to_default_content()
    #switch to the inner frame
    sb.switch_to_frame(iframe_two_xpath,timeout = 5)
    
    #Check if the element is present or not
    audio_challenge = sb.wait_for_element_present(audio_xpath,timeout = 5)

    if not audio_challenge:
        print("No audio challenge. Couldn't solve the captcha")
        return False #For now lets return we will solve by grid challenge as a fallback process

    sb.hover_and_click(hover_selector = audio_xpath,click_selector = audio_xpath, timeout = 5)

    

    #See if the play button is clickable or not
    sb.wait_for_element_clickable(play_button, timeout = 5)
    audio_text = audio_solver(sb)

    #Fill out the form with the audio text
    if audio_text:
            sb.type("//input[@id='audio-response']",audio_text)
            sb.click("//button[@id='recaptcha-verify-button']")

            sb.switch_to_default_content()
            time.sleep(3)
            sb.click("//input[@type='submit']")
            return True
    else:
        return False


def regex_date_filter(raw_due_date:str) -> str:
    try:
        match = re.search(r'(\d{1,2}/\d{1,2}/\d{4})', raw_due_date)

        if match:
            date_str = match.group(0) #groups the matches into a single string
            parsed_date = datetime.strptime(date_str, "%m/%d/%Y")
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
                "file_name" : os.path.basename(file_path),
                "sanitized_file_name" : os.path.basename(file_path),
                "file_url" : file_url,
                "file_size" : mb_size,
                "md5_hash" : file_hash,
                "iconverted" : iconverted
            }
            file_index += 1 

    #check for extension or the last part of the URL

    is_direct_download = is_direct_download_link(url=file_url)

    #we take the current window handle id to return to this handle
    #Here "main_window" is the main tab we open at the beginning of the scraping
    main_window =  sb.driver.current_window_handle
    # Seleniumbase automatically creates a directory named "downloaded_files" to keep the downloaded files
    downloaded_files_dir = os.path.join(script_directory, "downloaded_files")
    os.makedirs(downloaded_files_dir, exist_ok=True)
    before_files = set(os.listdir(downloaded_files_dir))

    sb.execute_script("window.open(arguments[0], '_blank');",file_url)
    sb.sleep(5)
    sb.switch_to_window(sb.driver.window_handles[-1])

    if not is_direct_download:
        print("Direct Download link not found")
        print("Form Filling and Captcha handling being done")

        form_filling(sb=sb)
        solved = solve_captcha(sb=sb)

        if not solved:
            try:
                sb.close()
            except Exception as e:
                pass
            sb.switch_to_window(main_window)
            return {}
            


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
                sb.close()
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
                               

