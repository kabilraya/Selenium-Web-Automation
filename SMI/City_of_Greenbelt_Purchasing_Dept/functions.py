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
from urllib.parse import urljoin
from lxml import etree
from markdownify import markdownify as md
from urllib.parse import urljoin
import markdown as md_lib
from weasyprint import HTML, CSS
import requests
def is_downloadable_file(url, sb=None, debug=False):
    if sb is not None:
        try:
            script = """
                const url = arguments[0];
                const callback = arguments[arguments.length - 1];
                fetch(url, { method: 'GET', credentials: 'include' })
                    .then(resp => {
                        callback({
                            ok: true,
                            status: resp.status,
                            url: resp.url,
                            contentType: resp.headers.get('Content-Type') || '',
                            contentDisposition: resp.headers.get('Content-Disposition') || ''
                        });
                    })
                    .catch(err => {
                        callback({ ok: false, error: String(err) });
                    });
            """
            result = sb.driver.execute_async_script(script, url)  # <- sb.driver, not sb

            if debug:
                print(f"URL: {url} -> {result}")

            if not result.get("ok"):
                return False

            content_type = result.get("contentType", "").lower()
            content_disposition = result.get("contentDisposition", "").lower()

            if content_disposition.split(';')[0].strip() == 'attachment':
                return True
            if any(content_type.startswith(t) for t in ('text/plain', 'text/html', 'image/', 'text/xml')):
                return False
            return True

        except Exception as e:
            if debug:
                print(f"  -> fetch failed: {e}")
            return False

    # fallback for when no sb is passed
    try:
        resp = requests.get(url, stream=True, timeout=(5, 10), allow_redirects=True)
        content_type = resp.headers.get('Content-Type', '').lower()
        content_disposition = resp.headers.get('Content-Disposition', '').lower()
        resp.close()
        if content_disposition.split(';')[0].strip() == 'attachment':
            return True
        if any(content_type.startswith(t) for t in ('text/plain', 'text/html', 'image/', 'text/xml')):
            return False
        return True
    except requests.RequestException:
        return False

DEFAULT_EXCLUDE_XPATHS = [
    ".//script",
    ".//noscript",
    ".//style",
    ".//iframe",
    ".//link",
    ".//meta",
    ".//svg",
    ".//button",
    ".//input",
    ".//form",
    ".//comment()",
    # hidden-via-CSS elements — common in CMS markup for tooltips, modals, etc.
    ".//*[contains(translate(@style,'DISPLAY','display'),'display:none')]",
    ".//*[contains(translate(@style,'DISPLAY','display'),'display: none')]",
    ".//*[@hidden]",
    ".//*[@aria-hidden='true']",
]


def remove_excluded_elements(node, exclude_xpaths):
    """Remove elements matching any of the given XPath expressions
    (relative to `node`) before converting to Markdown/HTML."""
    xpaths = DEFAULT_EXCLUDE_XPATHS + list(exclude_xpaths or [])
    for xpath in xpaths:
        for match in node.xpath(xpath):
            parent = match.getparent()
            if parent is not None:
                parent.remove(match)

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



def clean_node(node, base_url: str = "", exclude_xpaths=None):
    """Normalize links/images and strip dead elements. Mutates node in place."""
    for a in node.xpath(".//a[@href]"):
        href = a.get("href", "").strip()
        if href and base_url:
            a.set("href", urljoin(base_url, href))

    for img in node.xpath(".//img[@src]"):
        src = img.get("src", "").strip()
        if src and base_url:
            img.set("src", urljoin(base_url, src))
        if not img.get("alt"):
            img.set("alt", "image")

    remove_excluded_elements(node, exclude_xpaths)
    strip_empty_elements(node)
    return node


def node_to_markdown(node, base_url: str = "", exclude_xpaths=None) -> str:
    clean_node(node, base_url=base_url, exclude_xpaths=exclude_xpaths)
    inner_html = etree.tostring(node, encoding="unicode", method="html")
    text = md(inner_html, heading_style="ATX", bullets="-", strip=["script", "style"])
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


def node_to_pdf_html(node, base_url: str = "", exclude_xpaths=None) -> str:
    """Like node_to_markdown, but keeps inline styles intact for PDF rendering."""
    clean_node(node, base_url=base_url, exclude_xpaths=exclude_xpaths)
    return etree.tostring(node, encoding="unicode", method="html")

def save_nodes_as_pdf(tree, xpath: str, output_path: str, base_url: str = "", exclude_xpaths=None) -> None:
    nodes = tree.xpath(xpath)
    if not nodes:
        print("No nodes found — nothing to save")
        return

    md_chunks, html_chunks = [], []
    for idx, node in enumerate(nodes):
        # clean_node() mutates the node once; reuse it for both outputs
        clean_node(node, base_url=base_url, exclude_xpaths=exclude_xpaths)
        inner_html = etree.tostring(node, encoding="unicode", method="html")

        md_chunks.append(md(inner_html, heading_style="ATX", bullets="-", strip=["script", "style"]))
        html_chunks.append(inner_html)

        if idx < len(nodes) - 1:
            md_chunks.append("\n\n---\n\n")
            html_chunks.append("<hr>")

    full_markdown = re.sub(r"\n{3,}", "\n\n", "\n\n".join(md_chunks)).strip()
    with open(output_path.replace(".pdf", ".md"), "w", encoding="utf-8") as f:
        f.write(full_markdown)

    html_body = "".join(html_chunks)

    css = CSS(string="""
        @page { size: letter; margin: 40px; }
        body { font-family: Helvetica, Arial, sans-serif; font-size: 10.5pt; line-height: 1.4; }
        hr { border: none; border-top: 1px solid #999; margin: 12px 0; }
        p { margin: 0 0 10px 0; }
        ol, ul { margin: 4px 0 10px 1.2em; padding: 0; }
        a { color: blue; text-decoration: underline; }
    """)

    HTML(string=f"<html><body>{html_body}</body></html>").write_pdf(output_path, stylesheets=[css])

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
                               

