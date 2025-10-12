#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup
import pypandoc
import os
import logging
import traceback
from datetime import datetime
from requests.adapters import HTTPAdapter, Retry
import sys
from typing import Tuple

LOG_DIR = "logs"
ERROR_DIR = "errors"
ART_MD_DIR = "articles/md/Inquirer"
ART_DOCX_DIR = "articles/docx/Inquirer"

os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(ERROR_DIR, exist_ok=True)
os.makedirs(ART_MD_DIR, exist_ok=True)
os.makedirs(ART_DOCX_DIR, exist_ok=True)

logging.basicConfig(
    filename=os.path.join(LOG_DIR, "scrape_inquirer.log"),
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

class QuerySelectorNotFound(Exception):
    """Raised when an expected selector/section is missing from the page."""
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

site = "Inquirer"
inquirer_url = "https://opinion.inquirer.net"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36'
}

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

def get_latest_inquirer_article(url: str) -> Tuple[str, bool]:
    logging.info("Fetching latest article from %s", url)
    print(f"!!! Fetching latest article from {url}...")
    try:
        resp = session.get(url, headers=HEADERS, timeout=15)
    except Exception as e:
        logging.exception("Network error while fetching Inquirer listing")
        write_error_file("network_error_inquirer", e, extra=f"url={url}")
        return "### No article found", False

    if resp.status_code != 200:
        logging.error("Non-200 status %s for %s", resp.status_code, url)
        return "### No article found", False

    soup = BeautifulSoup(resp.content, 'html.parser')

    # defensive checks for missing container
    container = soup.find('div', id='opinion-v2-mh')
    if container is None:
        msg = "opinion-v2-mh container not found on Inquirer listing page"
        logging.error(msg)
        # create an error artifact so the workflow will commit/push it
        write_error_file("querySelector_not_found_inquirer_listing", QuerySelectorNotFound(msg))
        return "### No article found", False

    latest_links = container.find_all('a', href=True)
    if not latest_links:
        logging.warning("No article links found inside opinion-v2-mh")
        return "### No article found", False

    # we return the first href (could be relative)
    href = latest_links[0]['href']
    # make absolute if needed
    if href.startswith('/'):
        href = "https://opinion.inquirer.net" + href
    logging.info("Found latest href: %s", href)
    return href, True

def extract_inquirer_content(article_url: str) -> Tuple[str, str]:
    logging.info("Extracting content from %s", article_url)
    print(f"!!! Fetching article content from {article_url}...")
    try:
        resp = session.get(article_url, headers=HEADERS, timeout=15)
    except Exception as e:
        logging.exception("Network error while fetching Inquirer article")
        write_error_file("network_error_inquirer_article", e, extra=f"url={article_url}")
        return "### No title", "No content found"

    if resp.status_code != 200:
        logging.error("Non-200 status %s for %s", resp.status_code, article_url)
        return "### No title", "No content found"

    soup = BeautifulSoup(resp.content, 'html.parser')
    title_tag = soup.title
    title = title_tag.string.strip() if title_tag and title_tag.string else "Untitled"

    article_section = soup.find('section', id='inq_section')
    if article_section is None:
        msg = "Could not find section with id='inq_section'"
        logging.error(msg)
        write_error_file("querySelector_not_found_inquirer_article", QuerySelectorNotFound(msg),
                         extra=f"url={article_url}\n$page_title={title}")
        return title, "No content found"

    paragraphs_and_headings = article_section.find_all(['p', 'h2'])
    if not paragraphs_and_headings:
        msg = "No <p> or <h2> tags found inside inq_section"
        logging.error(msg)
        write_error_file("querySelector_not_found_inq_paragraphs", QuerySelectorNotFound(msg),
                         extra=f"url={article_url}\n$page_title={title}")
        return title, "No content found"

    article_content = []
    for tag in paragraphs_and_headings:
        if tag.name == 'h2':
            article_content.append(f"\n\n##  {tag.get_text()}\n\n")
        elif tag.name == 'p':
            paragraph_text = tag.get_text()
            # Filter out unwanted paragraphs
            if "Subscribe to our daily newsletter" in paragraph_text or \
               "Subscribe to our newsletter!" in paragraph_text or \
               "By providing an email address. I agree to the Terms of Use and acknowledge that I have read the Privacy Policy." in paragraph_text:
                continue
            article_content.append(paragraph_text)

    article_text = "\n\n".join(article_content).strip()
    logging.info("Extracted article content length: %d", len(article_text))
    return title, article_text

def save_article(article_url: str, title: str, has_date_tag: bool, site_name: str):
    try:
        _, article_content = extract_inquirer_content(article_url)
        date_prefix = datetime.now().strftime("%Y%m%d")
        safe_title = title.replace('/', '_').replace('\\', '_')
        markdown_content = f"# {title}\n\n{article_url}\n\n\n\n{article_content}"

        markdown_filename = f"{ART_MD_DIR}/[{date_prefix}] {safe_title}.md"
        os.makedirs(os.path.dirname(markdown_filename), exist_ok=True)
        with open(markdown_filename, "w", encoding='utf-8') as f:
            f.write(markdown_content)
        logging.info("Markdown saved: %s", markdown_filename)
        print(f"!!! Markdown content saved as {markdown_filename} successfully.")
    except Exception as e:
        logging.exception("Failed to save markdown for %s", article_url)
        write_error_file("save_md_inquirer", e, extra=f"url={article_url}\n$title={title}")
        return

    # Convert Markdown to DOCX
    try:
        output_filename = f"{ART_DOCX_DIR}/[{date_prefix}] {safe_title}.docx"
        os.makedirs(os.path.dirname(output_filename), exist_ok=True)
        pypandoc.convert_text(markdown_content, 'docx', format='md', outputfile=output_filename)
        logging.info("DOCX saved: %s", output_filename)
        print(f"!!! Content saved as {output_filename} successfully.")
    except Exception as e:
        logging.exception("Failed to convert to DOCX")
        write_error_file("pypandoc_inquirer", e, extra=f"md_length={len(markdown_content)}")

def main():
    try:
        latest_article_link, has_date_tag = get_latest_inquirer_article(inquirer_url)
        if latest_article_link != "### No article found":
            print(f"!!! Extracting content from Inquirer...")
            title, _ = extract_inquirer_content(latest_article_link)
            save_article(latest_article_link, title, has_date_tag, "Inquirer")
        else:
            print("NO ARTICLE FOUND: Inquirer")
    except Exception as e:
        logging.exception("Unhandled exception in main()")
        write_error_file("unhandled_inquirer", e)
        # do not crash the workflow — script writes an error artifact instead
        print("### Unhandled exception occurred; see errors/ for details.")

if __name__ == "__main__":
    main()