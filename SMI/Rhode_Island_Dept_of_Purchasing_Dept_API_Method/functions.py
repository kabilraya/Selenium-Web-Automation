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
from urllib.parse import quote
from sqlalchemy import text
from kabil_utils.boto_client import boto_client_insertion

TABLE = "tbl_WebBid"

COPY_COLS = [
    "stCrawled", "stHash", "ECGAINS", "stTitle", "stBidNo", "stdtDueDate", "stCode",
    "stAgencyTag", "stURL1", "stURL2", "iView", "iTransferred", "iProblem", "iArchived",
    "bidid", "iBidNoLookupMethod", "stModuleName", "txtDescription", "txtSpiderComments",
    "iMovedOffset", "stBidType", "assigned", "isDisabled",
]


# ---------------------------------------------------------------------------
# Database helper
# ---------------------------------------------------------------------------
def save_row(session, old_url2, new_url2, file_name,
             cloud_url, file_size, iconverted,formatted_date):
    """Write one uploaded file into the database."""
    new_url2 = new_url2 or old_url2   # safety: never write NULL into stURL2

    # a) Update the existing row using its OLD stURL2.
    res = session.execute(
        text(f"""
            UPDATE {TABLE}
            SET stURL2 = :new_url,
                stFileCloudURL = :u,
                stFileName = :n,
                stFileSize = :s,
                iConverted = :c,
                stdDueDate = :d
            WHERE stURL2 = :old_url
              AND (stFileCloudURL IS NULL OR TRIM(stFileCloudURL) = '')
        """),
        {
            "old_url": old_url2,
            "new_url": new_url2,
            "u": cloud_url,
            "n": file_name,
            "s": file_size,
            "c": iconverted,
            "d" : formatted_date
        },
    )
    print(f"[save_row] updated={res.rowcount} url={new_url2} file={file_name}")

    # b) If no empty row exists, insert a new row for this file.
    if res.rowcount == 0:
        exists = session.execute(
            text(f"""
                SELECT 1
                FROM {TABLE}
                WHERE stURL2 = :url AND stFileName = :n
                LIMIT 1
            """),
            {"url": new_url2, "n": file_name},
        ).first()

        if not exists:
            cols = ", ".join(COPY_COLS)

            # Replace stURL2 in the copied columns with the corrected URL.
            select_cols = ", ".join(
                ":new_url AS stURL2" if col == "stURL2" else col
                for col in COPY_COLS
            )

            session.execute(
                text(f"""
                    INSERT INTO {TABLE}
                        ({cols}, stFileName, stFileCloudURL,
                         stFileSize, iConverted)
                    SELECT {select_cols}, :n, :u, :s, :c
                    FROM {TABLE}
                    WHERE stURL2 IN (:old_url, :new_url)
                    LIMIT 1
                """),
                {
                    "old_url": old_url2,
                    "new_url": new_url2,
                    "n": file_name,
                    "u": cloud_url,
                    "s": file_size,
                    "c": iconverted,
                },
            )
            print(f"[save_row] inserted new row for {file_name}")

    session.commit()


# ---------------------------------------------------------------------------
# Misc helpers
# ---------------------------------------------------------------------------
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
        # never the whole header: the filename can legitimately contain
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


def santitize_file_name(url: str) -> str:
    root, ext = os.path.splitext(url)
    root = re.sub("[^a-zA-Z0-9_.-]", "_", root)
    return f"{root}{ext}"


# ---------------------------------------------------------------------------
# reCAPTCHA selectors
# ---------------------------------------------------------------------------
# The page has TWO elements with id="captchaVerificationModal": a hidden one
# nested in the bid item table and the visible one with class "modal open".
# Always target the open one.
OPEN_MODAL = "//div[@id='captchaVerificationModal' and contains(@class,'open')]"

# Checkbox iframe (matched by src, which is sturdier than the title)
ANCHOR_FRAME = "//iframe[contains(@src,'recaptcha/api2/anchor')]"
# Challenge iframe, created by Google at the end of <body>, outside both modals
CHALLENGE_FRAME = "//iframe[contains(@src,'recaptcha/api2/bframe')]"

# Tried in order to dismiss the modal after a failure. The first one visible wins.
CLOSE_CANDIDATES = [
    # Confirmed from DevTools: <a class="modal-close pull-right pointer"><i class="fa fa-times fa-2x">
    OPEN_MODAL + "//a[contains(@class,'modal-close')]",
    OPEN_MODAL + "//*[contains(@class,'close') and not(self::button and @disabled)]",
    OPEN_MODAL + "//*[contains(@class,'fa-times')]",
    OPEN_MODAL + "//*[contains(@class,'material-icons') and normalize-space()='close']",
    OPEN_MODAL + "//a[contains(@class,'modal-close')]",
    "//button[@aria-label='Close']",
]

DEFAULT_CAPTCHA_ATTEMPTS = 5


def reset_captcha_state(sb):
    """
    Leave every iframe and try to dismiss the captcha modal so the attachment
    list is clickable again. Never raises.
    """
    try:
        sb.switch_to_default_content()
    except Exception:
        pass

    for sel in CLOSE_CANDIDATES:
        try:
            if sb.is_element_visible(sel):
                sb.click(sel)
                sb.sleep(1)
                print(f"Closed captcha modal using {sel}")
                break
        except Exception:
            continue

    try:
        sb.switch_to_default_content()
    except Exception:
        pass


def switch_to_checkbox_frame(sb):
    """
    Switch into the visible reCAPTCHA checkbox iframe. Prefers an iframe inside
    the open modal, otherwise falls back to the first displayed anchor iframe.
    """
    sb.switch_to_default_content()
    try:
        sb.wait_for_element_visible(OPEN_MODAL, timeout=15)
    except Exception:
        print("No modal with class 'open' found, falling back to visible iframe search")

    scoped = OPEN_MODAL + ANCHOR_FRAME
    if sb.is_element_present(scoped):
        sb.switch_to_frame(scoped)
        return

    # Angular rendered it in the other modal copy: pick the visible one instead
    sb.wait_for_element_present(ANCHOR_FRAME, timeout=15)
    frames = sb.find_elements(ANCHOR_FRAME)
    visible = [f for f in frames if f.is_displayed()]
    print(f"anchor iframes: {len(frames)}, visible: {len(visible)}")
    target = visible[0] if visible else frames[0]
    sb.switch_to_frame(target)


def switch_to_challenge_frame(sb, timeout=10):
    """
    Two reCAPTCHA widgets exist on the page, so Google creates two challenge
    (bframe) iframes. Only one is visible; switch into that one.
    """
    sb.switch_to_default_content()
    deadline = time.time() + timeout
    frames = []
    while time.time() < deadline:
        frames = sb.driver.find_elements("xpath", CHALLENGE_FRAME)
        visible = [f for f in frames if f.is_displayed()]
        if visible:
            sb.switch_to_frame(visible[0])
            return
        time.sleep(0.5)
    raise Exception(f"no visible challenge iframe (found {len(frames)})")


# ---------------------------------------------------------------------------
# Audio solver
# ---------------------------------------------------------------------------
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
        print(f"Audio solve failed: {type(e).__name__}: {e!r}")
        return ""


def solve_recaptcha(sb, attempts=DEFAULT_CAPTCHA_ATTEMPTS):
    """
    Starts on the bid page with the captcha modal open.
    Returns True if solved. Always leaves SB in the default content; on failure
    it also tries to close the modal so the next file's link can be found.
    """

    def back_to_main_frame():
        sb.switch_to_default_content()
        sb.sleep(1)

    try:
        # 1. Click the checkbox (inside the checkbox iframe)
        switch_to_checkbox_frame(sb)
        sb.sleep(2)
        check_button = "//span[contains(@class,'recaptcha-checkbox')]"
        sb.hover_and_click(hover_selector=check_button, click_selector=check_button)
        sb.sleep(5)

        # Solved straight away, no challenge was shown
        if sb.is_element_present("//span[contains(@class,'recaptcha-checkbox-checked')]"):
            back_to_main_frame()
            return True

        # 2. Audio challenge (its iframe is a sibling of the page content, so go
        #    back to the default content before switching into it)
        for attempt in range(1, attempts + 1):
            print(f"reCAPTCHA audio attempt {attempt}/{attempts}")
            try:
                back_to_main_frame()
                switch_to_challenge_frame(sb)
                sb.sleep(2)

                # Google refuses audio challenges for this session/IP
                if sb.is_element_visible("//div[contains(@class,'rc-doscaptcha-header')]"):
                    print("reCAPTCHA says 'try again later' (blocked)")
                    break

                audio_button = "//button[@title='Get an audio challenge']"
                if sb.is_element_visible(audio_button):
                    sb.hover_and_click(hover_selector=audio_button, click_selector=audio_button)
                    sb.sleep(3)

                answer = audio_solver(sb)
                if answer:
                    sb.type("//input[@id='audio-response']", answer)
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

            except Exception as e:
                # One bad attempt should not abort the remaining ones
                print(f"attempt {attempt} error: {type(e).__name__}: {e}")
                continue

        reset_captcha_state(sb)
        return False

    except Exception as e:
        print(f"solve_recaptcha error: {type(e).__name__}: {e}")
        reset_captcha_state(sb)
        return False


# ---------------------------------------------------------------------------
# Main download routine
# ---------------------------------------------------------------------------
def download_files(sb, script_directory, download_path, file_index, file_hash,
                   download_button=None, session=None, bid_no=None, url2=None,
                   cloud=None, new_url2=None, formatted_date = None):
    file = {}

    def upload_and_save(info):
        """Upload one local file to the cloud, then write its row. Does nothing if no session."""
        if session is None:
            print(f"[{bid_no}] WARNING: no DB session passed, nothing uploaded or saved")
            return
        name = info["sanitized_file_name"]
        local = os.path.join(download_path, name)
        try:
            boto_client_insertion(
                bid_no=bid_no,
                download_dir=download_path,
                filename=name,
                **cloud,   # server_path, region_name, endpoint_url, aws_access_key_id, aws_secret_access_key
            )
            cloud_url = os.path.join(cloud["server_path"], quote(str(bid_no)[:25]), name).replace("\\", "/")
            print(cloud_url)
            save_row(
                session,
                old_url2=url2,
                new_url2=new_url2,
                file_name=info["file_name"],
                cloud_url=cloud_url,
                file_size=info["file_size"],
                iconverted=info["iconverted"],
                formatted_date= formatted_date
            )
            print(f"[{bid_no}] stored {name}")
        except Exception as e:
            session.rollback()
            print(f"[{bid_no}] upload/db failed for {name}: {e}")
        finally:
            if os.path.exists(local):
                os.remove(local)

    def process_single_file(file_path: str):
        nonlocal file_index
        bytes_size = os.path.getsize(file_path)
        mb_size = bytes_size / (1024 * 1024)
        file_with_ext = os.path.basename(file_path)
        iconverted = get_iconverted_value(file_with_ext)

        if mb_size > 50:
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
                upload_and_save(file[file_index])
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
            upload_and_save(file[file_index])
            file_index += 1

    # SeleniumBase keeps downloads in "downloaded_files"
    downloaded_files_dir = os.path.join(script_directory, "downloaded_files")
    os.makedirs(downloaded_files_dir, exist_ok=True)
    before_files = set(os.listdir(downloaded_files_dir))

    # Random pause so we don't hit the captcha in rapid succession
    sb.sleep(random.uniform(10, 25))

    # Click the attachment link (always from the default content)
    sb.switch_to_default_content()
    sb.hover_and_click(hover_selector=download_button, click_selector=download_button)
    sb.sleep(3)

    # Solve the reCAPTCHA; on any failure skip this file and return an empty dict
    if not solve_recaptcha(sb):
        print("Could not solve reCAPTCHA, skipping this file")
        reset_captcha_state(sb)
        return {}

    # Final download button: must be inside the OPEN modal and enabled.
    # The hidden duplicate modal has its own (disabled) "Download Attachment"
    # button, and an unscoped XPath matches that one first.
    sb.switch_to_default_content()
    any_button = "//button[contains(normalize-space(),'Download Attachment') and not(@disabled)]"
    scoped_button = OPEN_MODAL + any_button
    try:
        try:
            sb.wait_for_element_visible(scoped_button, timeout=20)
            final_download_button = scoped_button
        except Exception:
            # No modal carries the 'open' class on this bid: use any visible, enabled button
            print("Scoped Download Attachment button not found, trying unscoped")
            sb.wait_for_element_visible(any_button, timeout=10)
            final_download_button = any_button
        sb.hover_and_click(hover_selector=final_download_button, click_selector=final_download_button)
    except Exception as e:
        print(f"Download Attachment button not clickable: {type(e).__name__}: {e}")
        reset_captcha_state(sb)
        return {}
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
        reset_captcha_state(sb)
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