#!/usr/bin/env python3
import os
import requests
from bs4 import BeautifulSoup
import pypandoc
import logging
import traceback
from datetime import datetime
from requests.adapters import HTTPAdapter, Retry
from typing import Tuple

LOG_DIR = "logs"
ERROR_DIR = "errors"
MD_DIR = "articles/md/Philstar"
DOCX_DIR = "articles/docx/Philstar"

os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(ERROR_DIR, exist_ok=True)
os.makedirs(MD_DIR, exist_ok=True)
os.makedirs(DOCX_DIR, exist_ok=True)

logging.basicConfig(
    filename=os.path.join(LOG_DIR, "scrape_philstar.log"),
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

class QuerySelectorNotFound(Exception):
    pass

def requests_session_with_retries(total_retries=3, backoff=0.3):
    s = requests.Session()
    retries = Retry(total=total_retries, backoff_factor=backoff,
                    status_forcelist=[429, 500, 502, 503, 504],
                    allowed_methods=["GET", "POST"])
    adapter = HTTPAdapter(max_retries=retries)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s

session = requests_session_with_retries()

philstar_url = "https://philstar.com/opinion"
HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible)'}

def write_error_file(name_prefix: str, exc: Exception, extra: str = ""):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"{ERROR_DIR}/{name_prefix}_{ts}.txt"
    with open(fname, "w", encoding="utf-8") as ef:
        ef.write(f"Time: {datetime.now().isoformat()}\n")
        ef.write(f"Exception: {repr(exc)}\n\n")
        ef.write("Traceback:\n")
        ef.write(traceback.format_exc())
        if extra:
            ef.write("\n\nExtra:\n")
            ef.write(extra)
    logging.error("Wrote error file: %s", fname)
    print(f"### WROTE ERROR: {fname}")
    return fname

def extract_philstar_content(article_url: str) -> Tuple[str, str]:
    try:
        resp = session.get(article_url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        logging.exception("Network error fetching Philstar article")
        write_error_file("network_error_philstar_article", e, extra=f"url={article_url}")
        return None, None

    soup = BeautifulSoup(resp.content, 'html.parser')
    title_tag = soup.title
    title = title_tag.string.strip() if title_tag and title_tag.string else "Untitled"

    content_container = soup.find('div', class_='article__content')
    if content_container is None:
        msg = "Could not find div.article__content on Philstar article"
        logging.error(msg)
        write_error_file("querySelector_not_found_philstar_article", QuerySelectorNotFound(msg),
                         extra=f"url={article_url}\n$title={title}")
        return title, None

    paragraphs = content_container.find_all('p')
    if not paragraphs:
        msg = "No <p> tags found inside div.article__content"
        logging.error(msg)
        write_error_file("no_paragraphs_philstar", QuerySelectorNotFound(msg),
                         extra=f"url={article_url}\n$title={title}")
        return title, None

    content = "\n\n".join([tag.get_text(strip=True) for tag in paragraphs])
    return title, content

def save_article(url: str, title: str, content: str, md_save_path: str, docx_save_path: str):
    try:
        date_prefix = datetime.now().strftime("%Y%m%d")
        safe_title = title.replace('/', '_').replace('\\', '_')
        os.makedirs(md_save_path, exist_ok=True)
        os.makedirs(docx_save_path, exist_ok=True)

        md_file_path = os.path.join(md_save_path, f"[{date_prefix}] {safe_title}.md")
        with open(md_file_path, 'w', encoding='utf-8') as file:
            file.write(f"# {title}\n\n[Read more here]({url})\n\n{content}")
        logging.info("Saved md: %s", md_file_path)
        print(f"!!! Markdown content saved as {md_file_path}.")
    except Exception as e:
        logging.exception("Failed to save markdown")
        write_error_file("save_md_philstar", e, extra=f"url={url}\n$title={title}")
        return

    # Convert Markdown to DOCX
    try:
        docx_file_path = os.path.join(docx_save_path, f"[{date_prefix}] {safe_title}.docx")
        pypandoc.convert_file(md_file_path, 'docx', outputfile=docx_file_path)
        logging.info("Converted to docx: %s", docx_file_path)
        print(f"!!! Converted {md_file_path} to {docx_file_path}.")
    except Exception as e:
        logging.exception("Failed to convert MD to DOCX")
        write_error_file("pypandoc_philstar", e, extra=f"md_file={md_file_path}")

def get_latest_philstar_article(url: str):
    logging.info("Fetching latest article from %s", url)
    print(f"!!! Fetching latest article from {url}...")
    try:
        resp = session.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        logging.exception("Network error fetching Philstar listing")
        write_error_file("network_error_philstar_listing", e, extra=f"url={url}")
        return

    soup = BeautifulSoup(resp.content, 'html.parser')

    latest_article = None
    for item in soup.find_all('div', class_='carousel__item'):
        time_element = item.find('div', class_='carousel__item__time')
        if time_element:
            time_text = time_element.get_text(strip=True)
            # keep more robust matching; only skip those that obviously say "days" (older)
            if "day" not in time_text.lower():
                latest_article = item.find('a', href=True)
                if latest_article:
                    break

    if latest_article:
        article_url = latest_article['href']
        if article_url.startswith('/'):
            article_url = "https://philstar.com" + article_url
        logging.info("Found Philstar latest article: %s", article_url)
        title, content = extract_philstar_content(article_url)
        if title and content:
            save_article(article_url, title, content, MD_DIR, DOCX_DIR)
        else:
            logging.warning("Title or content was empty for %s", article_url)
    else:
        logging.warning("No recent article found on Philstar listing")

if __name__ == "__main__":
    try:
        get_latest_philstar_article(philstar_url)
    except Exception as e:
        logging.exception("Unhandled exception in Philstar scraper")
        write_error_file("unhandled_philstar", e)
        print("### Unhandled exception occurred; see errors/ for details.")