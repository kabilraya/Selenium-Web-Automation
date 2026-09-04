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
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from urllib.parse import urljoin
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet


def extract_parts(node, parts):
    """Recursively walk a node's children in document order, building markup parts."""
    if node.text and node.text.strip():
        parts.append(node.text.strip())

    for child in node.iterchildren():
        if child.tag in ("script", "style"):
            if child.tail and child.tail.strip():
                parts.append(child.tail.strip())
            continue

        if child.tag == "a":
            href = child.get("href", "").strip()
            href = urljoin("https://www.luzernecounty.org/", href) if href else ""
            if href:
                parts.append(f'<link href="{href}" color="blue"><u>{href}</u></link>')
            else:
                link_text = "".join(
                    child.xpath(".//text()[not(ancestor::script) and not(ancestor::style)]")
                ).strip()
                link_text = re.sub(
                    r"For security reasons,?\s*you must enable JavaScript to view this E-?mail address\.?",
                    "",
                    link_text,
                    flags=re.IGNORECASE
                ).strip()
                if link_text:
                    parts.append(link_text)
        else:
            # recurse into this child in case it wraps an <a> deeper inside (e.g. <p><a>...</a></p>)
            extract_parts(child, parts)

        if child.tail and child.tail.strip():
            parts.append(child.tail.strip())


def save_bid_tables_as_pdf(tree, xpath: str, output_path: str) -> None:
    styles = getSampleStyleSheet()
    body_style = styles["Normal"]
    bid_tables = tree.xpath(xpath)
    if not bid_tables:
        print("No tables found for the given xpath — nothing to save")
        return

    story = []
    for table_idx, table in enumerate(bid_tables):
        rows_data = []
        for tr in table.xpath(".//tr"):
            cells = tr.xpath("./td")
            if not cells:
                continue

            cell_texts = []
            for td in cells:
                parts = []
                extract_parts(td, parts)
                cell_texts.append(" ".join(p for p in parts if p))

            if not any(cell_texts):
                continue

            row = [Paragraph(text.replace("\n", "<br/>"), body_style) for text in cell_texts]
            rows_data.append(row)

        if not rows_data:
            continue

        max_cols = max(len(r) for r in rows_data)
        for r in rows_data:
            while len(r) < max_cols:
                r.append(Paragraph("", body_style))

        col_widths = [150] + [370] * (max_cols - 1) if max_cols >= 2 else None

        pdf_table = Table(rows_data, colWidths=col_widths)
        pdf_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ]))

        story.append(pdf_table)
        if table_idx < len(bid_tables) - 1:
            story.append(Spacer(1, 20))

    if not story:
        print("No rows extracted — nothing to save")
        return

    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=40,
        rightMargin=40,
        topMargin=40,
        bottomMargin=40,
    )
    doc.build(story)

def regex_date_filter(raw_due_date: str) -> str | None:
    try:
        match = re.search(
            r'(\d{1,2}/\d{1,2}/\d{4})',
            raw_due_date
        )

        if match:
            return match.group(1)

        return None

    except Exception as e:
        print(f"Error during parsing the date: {e}")
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
    before_files = set(os.listdir(downloaded_files_dir))
    sb.execute_script("window.open(arguments[0], '_blank');",file_url)
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
                               

