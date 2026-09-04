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
import re
from lxml import etree
from markdownify import markdownify as md
from urllib.parse import urljoin
import markdown as md_lib
from weasyprint import HTML, CSS

def strip_empty_elements(node):
    """Remove elements that contain no visible text/content, working bottom-up
    so a parent that becomes empty after its empty children are removed
    also gets removed."""
    EMPTY_CANDIDATE_TAGS = {"p", "ol", "ul", "div", "span"}

    for child in list(node):
        strip_empty_elements(child)

    if node.tag in EMPTY_CANDIDATE_TAGS:
        has_text = (node.text and node.text.strip()) or any(
            (child.tail and child.tail.strip()) for child in node
        )
        has_meaningful_children = len(node) > 0 
        if not has_text and not has_meaningful_children:
            parent = node.getparent()
            if parent is not None:
                if node.tail and node.tail.strip():
                    prev = node.getprevious()
                    if prev is not None:
                        prev.tail = (prev.tail or "") + node.tail
                    else:
                        parent.text = (parent.text or "") + node.tail
                parent.remove(node)


def remove_excluded_elements(node, exclude_xpaths):
    """Remove elements matching any of the given XPath expressions
    (relative to `node`) before converting to Markdown."""
    if not exclude_xpaths:
        return
    for xpath in exclude_xpaths:
        for match in node.xpath(xpath):
            parent = match.getparent()
            if parent is not None:
                parent.remove(match)


def node_to_markdown(node, base_url: str = "", exclude_xpaths=None) -> str:
    for a in node.xpath(".//a[@href]"):
        href = a.get("href", "").strip()
        if href and base_url:
            a.set("href", urljoin(base_url, href))\

    for img in node.xpath(".//img[@src]"):
        src = img.get("src", "").strip()
        if src and base_url:
            img.set("src", urljoin(base_url, src))
        
        if not img.get("alt"):
            img.set("alt", "image")

    remove_excluded_elements(node, exclude_xpaths)
    strip_empty_elements(node)

    inner_html = etree.tostring(node, encoding="unicode", method="html")
    text = md(inner_html, heading_style="ATX", bullets="-", strip=["script", "style"])
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


def save_nodes_as_pdf(tree, xpath: str, output_path: str, base_url: str = "", exclude_xpaths=None) -> None:
    nodes = tree.xpath(xpath)
    if not nodes:
        print("No nodes found — nothing to save")
        return

    md_chunks = []
    for idx, node in enumerate(nodes):
        md_chunks.append(node_to_markdown(node, base_url=base_url, exclude_xpaths=exclude_xpaths))
        if idx < len(nodes) - 1:
            md_chunks.append("\n\n---\n\n")   

    full_markdown = "\n\n".join(md_chunks)

    
    with open(output_path.replace(".pdf", ".md"), "w", encoding="utf-8") as f:
        f.write(full_markdown)

    html_body = md_lib.markdown(full_markdown, extensions=["extra", "sane_lists"])

    css = CSS(string="""
    @page { size: letter; margin: 40px; }
    body { font-family: Helvetica, Arial, sans-serif; font-size: 10.5pt; line-height: 1.4; }
    hr { border: none; border-top: 1px solid #999; margin: 12px 0; }
    p { margin: 0 0 10px 0; }
    ol, ul { margin: 4px 0 10px 1.2em; padding: 0; }
    a { color: blue; text-decoration: underline; }
    p:empty, ol:empty, ul:empty, div:empty { margin: 0; padding: 0; display: none; }
""")

    HTML(string=f"<html><body>{html_body}</body></html>").write_pdf(
        output_path, stylesheets=[css]
    )

def regex_date_filter(raw_due_date: str) -> str | None:
    """
    Extracts a date from text in either of these forms:
      - '9/09/2026' or '09/9/2026'      (numeric mm/dd/yyyy)
      - 'September 9, 2026'             (Month dd, yyyy)
    Returns a normalized 'mm/dd/yyyy' string, or None if nothing matched.
    """
    if not raw_due_date:
        return None

    
    numeric_match = re.search(r'(\d{1,2}/\d{1,2}/\d{4})', raw_due_date)
    if numeric_match:
        try:
            date_obj = datetime.strptime(numeric_match.group(1), "%m/%d/%Y")
            return date_obj.strftime("%m/%d/%Y")
        except ValueError as e:
            print(f"Matched numeric pattern but failed to parse: {e}")

    
    text_match = re.search(
        r'([A-Za-z]+\s+\d{1,2},?\s+\d{4})',
        raw_due_date
    )
    if text_match:
        raw = text_match.group(1).replace(",", "")
        for fmt in ("%B %d %Y", "%b %d %Y"):
            try:
                date_obj = datetime.strptime(raw, fmt)
                return date_obj.strftime("%m/%d/%Y")
            except ValueError:
                continue
        print(f"Matched text-date pattern but failed to parse: {raw}")

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
                               

