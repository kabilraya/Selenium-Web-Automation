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
from pydub import AudioSegment
import speech_recognition as sr
import inflect
import random
def is_downloadable_file(url):
    try:
        resp = requests.head(url, allow_redirects=True, timeout=10)
        content_type = resp.headers.get('Content-Type', '').lower()
        content_disposition = resp.headers.get('Content-Disposition', '').lower()

        if resp.status_code >= 400 or not content_type:
            resp = requests.get(url, stream=True, timeout=10)
            content_type = resp.headers.get('Content-Type', '').lower()
            content_disposition = resp.headers.get('Content-Disposition', '').lower()
            resp.close()

        # Only inspect the disposition TYPE (the part before the first ';'),
        # never the whole header — the filename can legitimately contain
        # the word "attachment" (e.g. "Attachment 5-Davis-Bacon-WD.txt"),
        # which would otherwise false-positive a substring check.
        disposition_type = content_disposition.split(';')[0].strip()
        if disposition_type == 'attachment':
            return True

        INLINE_RENDERABLE = ('text/plain', 'text/html', 'image/', 'text/xml')
        if any(content_type.startswith(t) for t in INLINE_RENDERABLE):
            return False

        return True

    except requests.RequestException:
        return False



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


def santitize_file_name(url:str) -> str:
    root, ext = os.path.splitext(url)
    root = re.sub("[^a-zA-Z0-9_.-]","_",root)
    return f"{root}{ext}"


MAIN_FRAME = "//iframe[@name='webprocureframe']"
CHECKBOX_FRAME = "//iframe[@title='reCAPTCHA']"
CHALLENGE_FRAME = "//iframe[@title='recaptcha challenge expires in two minutes']"
 
 
def audio_solver(sb):
    """
    Must be called while SB is inside the challenge iframe, after the audio
    challenge has been requested. Returns the transcribed text, or "" on failure.
    """
    try:
        audio_source = sb.wait_for_element_present("audio", timeout=15)
        audio_url = audio_source.get_attribute("src")
 
        response = requests.get(audio_url, timeout=15)
        response.raise_for_status()
 
        with open("audio.mp3", "wb") as f:
            f.write(response.content)
 
        # MP3 -> WAV
        sound = AudioSegment.from_mp3("audio.mp3")
        sound.export("audio.wav", format="wav")
 
        # Speech recognition
        recognizer = sr.Recognizer()
        with sr.AudioFile("audio.wav") as source:
            audio = recognizer.record(source)
 
        text = recognizer.recognize_google(audio)
        print(text)
        return text
    except Exception as e:
        print(f"Audio solve failed: {e}")
        return ""
 
 
def solve_recaptcha(sb, attempts=3):
    """
    Starts inside webprocureframe, with the reCAPTCHA checkbox iframe present.
    Returns True if solved. Always leaves SB inside webprocureframe.
    """
 
    def back_to_main_frame():
        sb.switch_to_default_content()
        sb.sleep(1)
        sb.switch_to_frame(MAIN_FRAME)
        sb.sleep(1)
 
    try:
        # 1. Click the checkbox (inside the checkbox iframe)
        sb.switch_to_frame(CHECKBOX_FRAME)
        sb.sleep(2)
        check_button = "//span[contains(@class,'recaptcha-checkbox')]"
        sb.hover_and_click(hover_selector=check_button, click_selector=check_button)
        sb.sleep(5)
 
        # Solved straight away, no challenge was shown
        if sb.is_element_present("//span[contains(@class,'recaptcha-checkbox-checked')]"):
            back_to_main_frame()
            return True
 
        # 2. Audio challenge (the challenge iframe is a sibling of the checkbox
        #    iframe, so go back up to webprocureframe before switching to it)
        for attempt in range(1, attempts + 1):
            print(f"reCAPTCHA audio attempt {attempt}/{attempts}")
            back_to_main_frame()
            sb.switch_to_frame(CHALLENGE_FRAME)
            sb.sleep(2)
 
            # Google refuses audio challenges for this session/IP
            if sb.is_element_visible("//div[contains(@class,'rc-doscaptcha-header')]"):
                print("reCAPTCHA says 'try again later' (blocked)")
                break
 
            audio_button = "//button[@title='Get an audio challenge']"
            if sb.is_element_visible(audio_button):
                sb.hover_and_click(hover_selector=audio_button, click_selector=audio_button)
                sb.sleep(3)
 
            text = audio_solver(sb)
            if text:
                sb.type("//input[@id='audio-response']", text)
                verify = "//button[@id='recaptcha-verify-button']"
                sb.hover_and_click(hover_selector=verify, click_selector=verify)
                sb.sleep(4)
 
                # If the error message is not showing, the answer was accepted
                if not sb.is_element_visible("//div[contains(@class,'rc-audiochallenge-error-message')]"):
                    back_to_main_frame()
                    return True
 
            # Wrong answer or no audio: request a fresh challenge and retry
            reload_btn = "//button[@id='recaptcha-reload-button']"
            if sb.is_element_visible(reload_btn):
                sb.click(reload_btn)
                sb.sleep(3)
 
        back_to_main_frame()
        return False
 
    except Exception as e:
        print(f"solve_recaptcha error: {e}")
        try:
            back_to_main_frame()
        except Exception:
            pass
        return False
 
 
def download_files(sb, script_directory, download_path, file_index, file_hash, download_button=None):
    file = {}
 
    def process_single_file(file_path: str):
        # Takes a single file from /download, gets its size, splits it if it is
        # a PDF over 50 MB, and updates the file = {} dictionary.
        nonlocal file_index
        bytes_size = os.path.getsize(file_path)
        mb_size = bytes_size / (1024 * 1024)
        file_with_ext = os.path.basename(file_path)
        iconverted = get_iconverted_value(file_with_ext)
 
        if mb_size > 50:
            # returns a list of tuples [(file_name, size_in_mb, path)]
            split_files = split_pdf(file_path=file_path)
            for file_name, size_in_mb, path in split_files:
                file[file_index] = {
                    "file_name": file_name,
                    "sanitized_file_name": file_name,
                    "file_url": file_name,
                    "file_size": f"{size_in_mb:.2f} MB",
                    "md5_hash": file_hash,
                    "iconverted": iconverted,
                }
                file_index += 1
        else:
            file[file_index] = {
                "file_name": file_with_ext,
                "sanitized_file_name": file_with_ext,
                "file_url": file_with_ext,
                "file_size": f"{mb_size:.2f} MB",
                "md5_hash": file_hash,
                "iconverted": iconverted,
            }
            file_index += 1
 
    # SeleniumBase keeps downloads in "downloaded_files"
    downloaded_files_dir = os.path.join(script_directory, "downloaded_files")
    os.makedirs(downloaded_files_dir, exist_ok=True)
    before_files = set(os.listdir(downloaded_files_dir))
 
    # Random pause so we don't hit the captcha in rapid succession
    sb.sleep(random.uniform(10, 25))
 
    # Click the attachment link (we are in webprocureframe)
    sb.hover_and_click(hover_selector=download_button, click_selector=download_button)
    sb.sleep(3)
 
    # Solve the reCAPTCHA; on any failure skip this file and return an empty dict
    if not solve_recaptcha(sb):
        print("Could not solve reCAPTCHA, skipping this file")
        return {}
 
    # Final download button lives in webprocureframe
    final_download_button = "//button[contains(normalize-space(),'Download Attachment')]"
    sb.hover_and_click(hover_selector=final_download_button, click_selector=final_download_button)
    sb.sleep(2)
 
    # Wait for the download to complete
    partial_exts = (".crdownload", ".part", ".tmp", ".download")
    timeout = 180
    poll_interval = 0.5
    deadline = time.time() + timeout
    actual_file_name = None
 
    while time.time() < deadline:
        current_files = set(os.listdir(downloaded_files_dir))
        new_files = current_files - before_files
        completed = [
            f for f in new_files
            if not f.lower().endswith(partial_exts) and not f.startswith(".")
        ]
 
        if completed:
            completed.sort(
                key=lambda f: os.path.getmtime(os.path.join(downloaded_files_dir, f)),
                reverse=True,
            )
            candidate = completed[0]
            candidate_path = os.path.join(downloaded_files_dir, candidate)
            size1 = os.path.getsize(candidate_path)
            time.sleep(0.3)
            size2 = os.path.getsize(candidate_path)
            if size1 == size2 and size1 > 0:
                actual_file_name = candidate
                break
 
        time.sleep(poll_interval)
 
    if not actual_file_name:
        print("Download did not finish in time, skipping this file")
        return {}
 
    print(actual_file_name)
    new_file_name = santitize_file_name(actual_file_name)
    print(new_file_name)
 
    source_path = os.path.join(downloaded_files_dir, new_file_name)
    if not os.path.exists(source_path):
        source_path = os.path.join(downloaded_files_dir, actual_file_name)
 
    if not os.path.exists(source_path):
        print(f"{actual_file_name} was not found in the downloaded_files")
        print(f"SB downloaded files as {sb.get_downloaded_files(browser=False)}")
        return {}
 
    os.makedirs(download_path, exist_ok=True)
    final_path = os.path.join(download_path, new_file_name)
    shutil.move(source_path, final_path)
    file_ext = os.path.splitext(final_path)[1].lower()
 
    if file_ext == ".zip":
        zip_directory = os.path.dirname(final_path)  # /download
        folder_name = os.path.splitext(os.path.basename(final_path))[0]
        extract_path = os.path.join(zip_directory, folder_name)  # /download/myzip
        os.makedirs(extract_path, exist_ok=True)
 
        # Extract temporarily
        with zipfile.ZipFile(final_path, "r") as zip_reader:
            zip_reader.extractall(extract_path)
 
        # Walk through /download/myzip/ and move every file up to /download
        for root, _, files in os.walk(extract_path):
            for file_name in files:
                sanitized_file_name = santitize_file_name(file_name)
                inner_source = os.path.join(root, file_name)
                destination_path = os.path.join(zip_directory, sanitized_file_name)
                shutil.move(inner_source, destination_path)
                process_single_file(destination_path)
 
        shutil.rmtree(extract_path)
        os.remove(final_path)
    else:
        process_single_file(final_path)
 
    return file
                               

