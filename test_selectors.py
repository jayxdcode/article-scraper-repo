#!/usr/bin/env python3
"""
test_selectors.py

Reads config.json (root) and validates CSS selectors for each configured site.
Writes:
 - test_results.json  (summary)
 - errors/<site>__<short>__<ts>.txt (human-readable error artifacts, OPTIONAL)
 - snapshots/<site>__<short>__<ts>.html (full HTML snapshots, OPTIONAL)

Term logs show status per selector (PASS/FAIL) with content preview.
File creation for errors/snapshots is controlled by the SAVE_ERROR_ARTIFACTS const.

Exit codes:
 - 0 : all selectors passed
 - 1 : one or more checks failed
 - 2 : config or other fatal error
"""
import json
import os
import logging
import traceback
from datetime import datetime
from typing import Dict, Any, Optional
from urllib.parse import urljoin
import sys

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter, Retry

# =========================================================
# New Constant to control file creation for selector failures
# =========================================================
SAVE_ERROR_ARTIFACTS = True # <-- Set to False to disable error/snapshot files on failure
# =========================================================


# Constants
CONFIG_PATH = "config.json"
ERROR_DIR = "errors"
SNAPSHOT_DIR = "snapshots"
LOG_DIR = "logs"
RESULTS_FILE = "test_results.json"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept': 'text/html',
    'Referer': 'https://www.google.com/', # Sometimes a Referer header is also checked 
    'Connection': 'keep-alive'
}

cookies = {
    "__pvi": "eyJpZCI6InYtbWd1MnhuMXFpaWR0eWRsbyIsImRvbWFpbiI6Ii5pbnF1aXJlci5uZXQiLCJ0aW1lIjoxNzYwNjU5MDQyMzM3fQ%3D%3D",
    "__tbc": "%7Bkpex%7DXgD_k3lGnfx3__beLUDW0ex7xMMXbbk_3Ob0M9ZUtnc0PcZsJJKnNNLKzMWr2OJG",
    "_pubcid_cst": "zix7LPQsHA%3D%3D",
    "__pat": "28800000",
    "same-site-cookie": "foo",
    "_pubcid": "fc8e0be3-8626-4a92-a60e-65512fc7afb7",
    "spotim_visitId": "{%22creationDate%22:%22Mon%20May%2012%202025%2017:21:41%20GMT+0800%20(Philippine%20Standard%20Time)%22%2C%22duration%22:29}",
    "cross-site-cookie": "bar",
    "_pcid": "%7B%22browserId%22%3A%22mfjd9ke8dn586tne%22%7D",
    "_pctx": "%7Bu%7DN4IgrgzgpgThIC4B2YA2qA05owMoBcBDfSREQpAeyRCwgEt8oBJAE0RXQF8g",
    "xbc": "%7Bkpex%7DObMYRypto3UoEWFEiRIuBS_4U2ti2b0xvZP27MQf5zU"
}


MAX_PREVIEW_CHARS = 75 # Constant for content preview length

# Ensure directories exist
os.makedirs(ERROR_DIR, exist_ok=True)
os.makedirs(SNAPSHOT_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    filename=os.path.join(LOG_DIR, "test_selectors.log"),
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

def requests_session_with_retries(total_retries=3, backoff=0.3):
    s = requests.Session()
    retries = Retry(total=total_retries, backoff_factor=backoff,
                    status_forcelist=[429, 500, 502, 503, 504],
                    allowed_methods=["GET"])
    adapter = HTTPAdapter(max_retries=retries)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    s.headers.update(HEADERS)
    return s

session = requests_session_with_retries()

def read_config(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Config file not found: {path}")
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)

def safe_short(name: str) -> str:
    return "".join(c if c.isalnum() or c in "._-" else "_" for c in name)[:120]

def write_error_file(site_name: str, short_title: str, content: str) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = safe_short(short_title)
    fname = f"{ERROR_DIR}/{site_name}__{safe}__{ts}.txt"
    with open(fname, "w", encoding="utf-8") as ef:
        ef.write(content)
    logging.error("Wrote error artifact for %s: %s", site_name, fname)
    return fname

def save_html_snapshot(site_name: str, short_title: str, html_content: str) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = safe_short(short_title)
    fname = f"{SNAPSHOT_DIR}/{site_name}__{safe}__{ts}.html"
    with open(fname, "w", encoding="utf-8") as sf:
        sf.write(html_content)
    logging.info("Saved HTML snapshot for %s: %s", site_name, fname)
    return fname

def fetch(url: str, timeout=15) -> Optional[requests.Response]:
    try:
        r = session.get(url, timeout=timeout, cookies=cookies)
        r.raise_for_status()
        return r
    except Exception as e:
        logging.exception("Network error fetching %s", url)
        # Print network error to console as well
        print(f"ERROR: [Network] Failed to fetch {url}: {e}", file=sys.stderr)
        # Always write file for fatal network errors
        write_error_file("NETWORK", "fetch_error", f"Failed to fetch {url}: {e}\n\nTrace:\n{traceback.format_exc()}")
        return None

def get_content_preview(soup: BeautifulSoup, selector: str, maxlen: int) -> str:
    """Extracts text content from the first element matching the selector."""
    try:
        found = soup.select_one(selector)
        if found:
            # Get text, strip whitespace, and truncate
            preview = found.get_text(strip=True)
            return preview[:maxlen] + ('...' if len(preview) > maxlen else '')
        return "(Element Not Found)"
    except Exception:
        return "(Could not produce preview due to error)"

def test_site(site_cfg: Dict[str, Any]) -> Dict[str, Any]:
    result = {"ok": True, "errors": [], "details": {}}
    name = site_cfg.get("name", "unknown")
    listing_url = site_cfg.get("listing_url")
    listing_sel = site_cfg.get("listing_selector")
    link_sel = site_cfg.get("link_selector", "a[href]")
    article_selectors = site_cfg.get("article_selectors", {})

    print(f"\n--- Site: {name} ({listing_url}) ---")
    
    # ----------------------------------------------------
    # 1. Fetch Listing Page
    # ----------------------------------------------------
    resp = fetch(listing_url)
    if resp is None:
        msg = f"Failed to fetch listing URL: {listing_url}"
        result["ok"] = False
        result["errors"].append(msg)
        return result

    soup = BeautifulSoup(resp.content, "html.parser")

    # ----------------------------------------------------
    # 2. Check Listing Selector
    # ----------------------------------------------------
    if listing_sel:
        # Status for Listing Selector
        sel_key = f"LISTING_SELECTOR: {listing_sel}"
        
        found_listing = soup.select(listing_sel)
        if not found_listing:
            msg = f"Listing selector FAILED: '{listing_sel}' not found."
            result["ok"] = False
            result["errors"].append(msg)
            
            # Display status to term log
            print(f"FAIL: {sel_key}")
            print(f"   content preview: (max {MAX_PREVIEW_CHARS} chars) - {get_content_preview(soup, listing_sel, MAX_PREVIEW_CHARS)}")
            
            # Conditionally save files
            if SAVE_ERROR_ARTIFACTS:
                save_html_snapshot(name, "listing_page_no_listing_sel", resp.text)
                write_error_file(name, "listing_selector_not_found", f"{msg}\n\nSaved listing snapshot.")
        else:
            print(f"PASS: {sel_key}")
            
    else:
        logging.warning("No listing_selector provided for %s", name)

    # ----------------------------------------------------
    # 3. Check Link Selector
    # ----------------------------------------------------
    container = soup
    if listing_sel and soup.select(listing_sel):
        # Use the first listing item as the container, or fallback to soup (whole page)
        container = soup.select(listing_sel)[0]

    link_node = None
    sel_key = f"LINK_SELECTOR: {link_sel}"
    
    try:
        link_node = container.select_one(link_sel)
    except Exception as e:
        msg = f"Invalid link selector '{link_sel}': {str(e)}"
        result["ok"] = False
        result["errors"].append(msg)
        
        # Display status to term log
        print(f"FAIL: {sel_key} (Invalid Syntax)")
        print(f"   content preview: (max {MAX_PREVIEW_CHARS} chars) - (Invalid Selector Syntax)")
        
        # Always write file for fatal link selector syntax error
        write_error_file(name, "invalid_link_selector", f"{msg}\n\nTrace:\n{traceback.format_exc()}")
        save_html_snapshot(name, "listing_page_invalid_link", resp.text)
        return result # Exit here as we can't get an article URL

    if not link_node:
        msg = f"Link selector FAILED: No article link found using '{link_sel}'."
        result["ok"] = False
        result["errors"].append(msg)
        
        # Display status to term log
        print(f"FAIL: {sel_key}")
        print(f"   content preview: (max {MAX_PREVIEW_CHARS} chars) - {get_content_preview(container, link_sel, MAX_PREVIEW_CHARS)}")
        
        # Conditionally save files
        if SAVE_ERROR_ARTIFACTS:
            save_html_snapshot(name, "listing_page_no_link", resp.text)
            write_error_file(name, "no_article_link", msg + "\n\nSaved listing snapshot.")
        return result # Exit here as we can't get an article URL
    
    # Check for empty href after finding the node
    href = link_node.get("href")
    if not href:
        msg = f"Found link node but href attribute is empty for site {name}"
        result["ok"] = False
        result["errors"].append(msg)
        
        print(f"FAIL: {sel_key} (Empty href)")
        print(f"   content preview: (max {MAX_PREVIEW_CHARS} chars) - {get_content_preview(container, link_sel, MAX_PREVIEW_CHARS)}")
        
        # Conditionally save file
        if SAVE_ERROR_ARTIFACTS:
            write_error_file(name, "empty_href", msg)
        return result

    print(f"PASS: {sel_key}")

    article_url = urljoin(listing_url, href)
    result["details"]["article_url"] = article_url
    logging.info("Found article link: %s", article_url)

    # ----------------------------------------------------
    # 4. Fetch Article Page
    # ----------------------------------------------------
    ar = fetch(article_url)
    if ar is None:
        msg = f"Failed to fetch article URL: {article_url}"
        result["ok"] = False
        result["errors"].append(msg)
        # Always write error file for fatal network issues
        write_error_file(name, "fetch_article_error", msg + "\n\nTrace:\n" + traceback.format_exc())
        return result

    asoup = BeautifulSoup(ar.content, "html.parser")

    # ----------------------------------------------------
    # 5. Check Article Selectors
    # ----------------------------------------------------
    sel_details = {}
    print("\n  Article Selectors:")
    for sel_name, sel_expr in article_selectors.items():
        sel_key = f"    #{sel_name} ({sel_expr})"
        
        try:
            is_multi = sel_name.lower() in ("paragraphs", "paras", "p", "paragraph")

            if is_multi:
                found = asoup.select(sel_expr)
                sel_details[sel_name] = {"selector": sel_expr, "count": len(found)}
                
                if not found:
                    msg = f"Article selector FAILED: '{sel_name}' ({sel_expr}) returned 0 elements."
                    result["ok"] = False
                    result["errors"].append(msg)
                    
                    print(f"FAIL: {sel_key}")
                    print(f"   content preview: (max {MAX_PREVIEW_CHARS} chars) - (No elements found)")
                    
                    if SAVE_ERROR_ARTIFACTS:
                        save_html_snapshot(name, f"article_{sel_name}_missing", ar.text)
                        snippet = get_content_preview(asoup, sel_expr, 800) # Use longer snippet for file
                        write_error_file(name, f"article_selector_{sel_name}_missing", f"{msg}\n\nSnippet:\n\n{snippet}")
                else:
                    print(f"PASS: {sel_key} (Count: {len(found)})")
                    print(f"   content preview: (max {MAX_PREVIEW_CHARS} chars) - {get_content_preview(asoup, sel_expr, MAX_PREVIEW_CHARS)}")
                    
            else: # Single element selector
                found = asoup.select_one(sel_expr)
                sel_details[sel_name] = {"selector": sel_expr, "found": bool(found)}
                
                if not found:
                    msg = f"Article selector FAILED: '{sel_name}' ({sel_expr}) not found."
                    result["ok"] = False
                    result["errors"].append(msg)
                    
                    print(f"FAIL: {sel_key}")
                    print(f"   content preview: (max {MAX_PREVIEW_CHARS} chars) - (Element Not Found)")
                    
                    if SAVE_ERROR_ARTIFACTS:
                        save_html_snapshot(name, f"article_{sel_name}_missing", ar.text)
                        snippet = get_content_preview(asoup, sel_expr, 800) # Use longer snippet for file
                        write_error_file(name, f"article_selector_{sel_name}_missing", f"{msg}\n\nSnippet:\n\n{snippet}")
                else:
                    print(f"PASS: {sel_key}")
                    print(f"   content preview: (max {MAX_PREVIEW_CHARS} chars) - {get_content_preview(asoup, sel_expr, MAX_PREVIEW_CHARS)}")
                    
        except Exception as e:
            msg = f"Exception while applying selector '{sel_expr}' for '{sel_name}': {str(e)}"
            result["ok"] = False
            result["errors"].append(msg)
            
            print(f"FAIL: {sel_key} (Exception)")
            print(f"   content preview: (max {MAX_PREVIEW_CHARS} chars) - (Invalid Selector Syntax)")
            
            # Always write file/snapshot for fatal selector syntax error
            save_html_snapshot(name, f"article_selector_exception_{safe_short(sel_name)}", ar.text)
            write_error_file(name, "selector_exception", msg + "\n\nTrace:\n" + traceback.format_exc())

    result["details"]["article_selectors"] = sel_details
    return result

def main():
    try:
       #  cfg = read_config(CONFIG_PATH)
       # Using hardcoded config for testing as per prompt
       cfg = {
  "sites": [
    {
      "name": "Inquirer",
      "listing_url": "https://opinion.inquirer.net",
      "listing_selector": "div#opinion-v2-mh",
      "link_selector": "a[href]",
      "article_selectors": {
        "title": "title",
        "article_section": "section#inq_section",
        "paragraphs": "section#inq_section p",
        "headings": "section#inq_section h2.nonexistent"
      }
    },
    {
      "name": "Philstar",
      "listing_url": "https://philstar.com/opinion",
      "listing_selector": "div.carousel__item",
      "link_selector": "a[href]",
      "article_selectors": {
        "title": "title",
        "article_section": "div.article__content",
        "paragraphs": "div.article__content p.nonexistent"
      }
    }
  ]
}
    except Exception as e:
        print(f"ERROR: Could not read config: {e}", file=sys.stderr)
        logging.exception("Could not read config.json")
        sys.exit(2)

    sites = cfg.get("sites", [])
    if not sites:
        print("ERROR: No sites configured in config.json", file=sys.stderr)
        logging.error("No sites in config.json")
        sys.exit(2)

    overall_ok = True
    results: Dict[str, Any] = {"generated_at": datetime.now().isoformat(), "sites": {}}
    
    print("\n====================================")
    print("  Starting Selector Validation      ")
    print(f"  (Artifacts saving: {'ON' if SAVE_ERROR_ARTIFACTS else 'OFF'})")
    print("====================================\n")

    for site in sites:
        name = site.get("name", "unnamed")
        try:
            res = test_site(site)
            results["sites"][name] = res
            if not res.get("ok", False):
                overall_ok = False
        except Exception as e:
            logging.exception("Unhandled error testing site %s", name)
            overall_ok = False
            err = f"Unhandled exception for {name}: {str(e)}"
            results["sites"][name] = {"ok": False, "errors": [err]}
            print(f"\nFATAL ERROR: [{name}] Unhandled exception: {err}", file=sys.stderr)
            write_error_file(name, "unhandled_exception", err + "\n\nTrace:\n" + traceback.format_exc())
            
        print(f"\n--- Site: {name} Summary ---")
        if results["sites"][name].get("ok", False):
            print("  ✅ All checks passed.")
        else:
            print("  ❌ One or more checks FAILED.")
        print("-----------------------------------\n")


    # Save results json
    with open(RESULTS_FILE, "w", encoding="utf-8") as rf:
        json.dump(results, rf, indent=2, ensure_ascii=False)

    print(f"\nSaved summary results to {RESULTS_FILE}")
    if overall_ok:
        print("--- COMPLETE: All selectors OK (Exit Code 0) ---")
        sys.exit(0)
    else:
        print("\n!!! COMPLETE: One or more selector checks FAILED (Exit Code 1) !!!")
        if SAVE_ERROR_ARTIFACTS:
            print("Review the console output, 'errors/', 'snapshots/', and 'test_results.json' for details.")
        else:
            print("Review the console output and 'test_results.json' for details.")
        sys.exit(1)

if __name__ == "__main__":
    main()
