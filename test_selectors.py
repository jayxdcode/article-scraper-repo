#!/usr/bin/env python3
"""
test_selectors.py

Reads config.json (root) and validates CSS selectors for each configured site.
Writes:
 - test_results.json  (summary)
 - errors/<site>__<short>__<ts>.txt (human-readable error artifacts)
 - snapshots/<site>__<short>__<ts>.html (full HTML snapshots when relevant)

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
from typing import Dict, Any
from urllib.parse import urljoin
import sys

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter, Retry

# Constants
CONFIG_PATH = "config.json"
ERROR_DIR = "errors"
SNAPSHOT_DIR = "snapshots"
LOG_DIR = "logs"
RESULTS_FILE = "test_results.json"
USER_AGENT = "Mozilla/5.0 (compatible; selector-tester/1.0; +https://github.com/)"

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
    s.headers.update({"User-Agent": USER_AGENT})
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
    logging.error("Wrote error file: %s", fname)
    return fname

def save_html_snapshot(site_name: str, short_title: str, html_content: str) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = safe_short(short_title)
    fname = f"{SNAPSHOT_DIR}/{site_name}__{safe}__{ts}.html"
    with open(fname, "w", encoding="utf-8") as sf:
        sf.write(html_content)
    logging.info("Saved HTML snapshot: %s", fname)
    return fname

def fetch(url: str, timeout=15):
    try:
        r = session.get(url, timeout=timeout)
        r.raise_for_status()
        return r
    except Exception as e:
        logging.exception("Network error fetching %s", url)
        return None

def snippet_html(soup: BeautifulSoup, selector: str, maxlen=800) -> str:
    try:
        found = soup.select_one(selector)
        if not found:
            # fallback - return start of page
            return soup.prettify()[:maxlen]
        return found.prettify()[:maxlen]
    except Exception:
        return "Could not produce snippet."

def test_site(site_cfg: Dict[str, Any]) -> Dict[str, Any]:
    result = {"ok": True, "errors": [], "details": {}}
    name = site_cfg.get("name", "unknown")
    listing_url = site_cfg.get("listing_url")
    listing_sel = site_cfg.get("listing_selector")
    link_sel = site_cfg.get("link_selector", "a[href]")
    article_selectors = site_cfg.get("article_selectors", {})

    logging.info("Testing site '%s' listing %s", name, listing_url)
    result["details"]["listing_url"] = listing_url

    resp = fetch(listing_url)
    if resp is None:
        msg = f"Failed to fetch listing URL: {listing_url}"
        result["ok"] = False
        result["errors"].append(msg)
        write_error_file(name, "fetch_listing_error", f"{msg}\n\nTrace:\n{traceback.format_exc()}")
        return result

    soup = BeautifulSoup(resp.content, "html.parser")

    # Check listing selector
    if listing_sel:
        found_listing = soup.select(listing_sel)
        if not found_listing:
            msg = f"Listing selector NOT found: '{listing_sel}' on {listing_url}"
            logging.error(msg)
            result["ok"] = False
            result["errors"].append(msg)
            # save snapshot of listing page for debugging
            save_html_snapshot(name, "listing_page", resp.text)
            write_error_file(name, "listing_selector_not_found", f"{msg}\n\nSaved listing snapshot.")
    else:
        logging.warning("No listing_selector provided for %s", name)

    # Determine container to search for link
    container = None
    if listing_sel and soup.select(listing_sel):
        container = soup.select(listing_sel)[0]
    else:
        container = soup  # fallback to whole page

    link_node = None
    try:
        link_node = container.select_one(link_sel)
    except Exception as e:
        logging.exception("Invalid link selector '%s' for %s", link_sel, name)
        result["ok"] = False
        msg = f"Invalid link selector '{link_sel}': {str(e)}"
        result["errors"].append(msg)
        write_error_file(name, "invalid_link_selector", f"{msg}\n\nTrace:\n{traceback.format_exc()}")
        # save listing snapshot as well
        save_html_snapshot(name, "listing_page_invalid_link", resp.text)

    if not link_node:
        msg = f"No article link found using link_selector '{link_sel}' (in listing context)."
        logging.error(msg)
        result["ok"] = False
        result["errors"].append(msg)
        # save listing snapshot for debugging
        save_html_snapshot(name, "listing_page_no_link", resp.text)
        write_error_file(name, "no_article_link", msg + "\n\nSaved listing snapshot.")
        return result

    href = link_node.get("href")
    if not href:
        msg = f"Found link node but href is empty for site {name}"
        logging.error(msg)
        result["ok"] = False
        result["errors"].append(msg)
        write_error_file(name, "empty_href", msg)
        return result

    article_url = urljoin(listing_url, href)
    result["details"]["article_url"] = article_url
    logging.info("Found article link: %s", article_url)

    ar = fetch(article_url)
    if ar is None:
        msg = f"Failed to fetch article URL: {article_url}"
        logging.error(msg)
        result["ok"] = False
        result["errors"].append(msg)
        write_error_file(name, "fetch_article_error", msg + "\n\nTrace:\n" + traceback.format_exc())
        return result

    asoup = BeautifulSoup(ar.content, "html.parser")

    sel_details = {}
    for sel_name, sel_expr in article_selectors.items():
        try:
            if sel_name.lower() in ("paragraphs", "paras", "p", "paragraph"):
                found = asoup.select(sel_expr)
                sel_details[sel_name] = {"selector": sel_expr, "count": len(found)}
                if not found:
                    msg = f"Article selector '{sel_name}' ({sel_expr}) returned 0 elements in {article_url}"
                    logging.error(msg)
                    result["ok"] = False
                    result["errors"].append(msg)
                    # save HTML snapshot of the article page for debugging
                    save_html_snapshot(name, f"article_{sel_name}_missing", ar.text)
                    snippet = snippet_html(asoup, sel_expr)
                    write_error_file(name, f"article_selector_{sel_name}_missing", f"{msg}\n\nSnippet:\n\n{snippet}")
            else:
                found = asoup.select_one(sel_expr)
                sel_details[sel_name] = {"selector": sel_expr, "found": bool(found)}
                if not found:
                    msg = f"Article selector '{sel_name}' ({sel_expr}) not found in {article_url}"
                    logging.error(msg)
                    result["ok"] = False
                    result["errors"].append(msg)
                    # save HTML snapshot of the article page for debugging
                    save_html_snapshot(name, f"article_{sel_name}_missing", ar.text)
                    snippet = snippet_html(asoup, sel_expr)
                    write_error_file(name, f"article_selector_{sel_name}_missing", f"{msg}\n\nSnippet:\n\n{snippet}")
        except Exception as e:
            logging.exception("Error applying selector %s for site %s", sel_expr, name)
            result["ok"] = False
            msg = f"Exception while applying selector '{sel_expr}': {str(e)}"
            result["errors"].append(msg)
            save_html_snapshot(name, f"article_selector_exception_{safe_short(sel_name)}", ar.text)
            write_error_file(name, "selector_exception", msg + "\n\nTrace:\n" + traceback.format_exc())

    result["details"]["article_selectors"] = sel_details
    return result

def main():
    try:
        cfg = read_config(CONFIG_PATH)
    except Exception as e:
        print(f"ERROR: Could not read config: {e}")
        logging.exception("Could not read config.json")
        sys.exit(2)

    sites = cfg.get("sites", [])
    if not sites:
        print("No sites configured in config.json")
        logging.error("No sites in config.json")
        sys.exit(2)

    overall_ok = True
    results: Dict[str, Any] = {"generated_at": datetime.now().isoformat(), "sites": {}}

    for site in sites:
        name = site.get("name", "unnamed")
        print(f"Testing site: {name} ...")
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
            write_error_file(name, "unhandled_exception", err + "\n\nTrace:\n" + traceback.format_exc())

    # Save results json
    with open(RESULTS_FILE, "w", encoding="utf-8") as rf:
        json.dump(results, rf, indent=2, ensure_ascii=False)

    print(f"Saved results to {RESULTS_FILE}")
    if overall_ok:
        print("All selectors OK")
        sys.exit(0)
    else:
        print("One or more selector checks FAILED (see errors/ and snapshots/ and test_results.json).")
        sys.exit(1)

if __name__ == "__main__":
    main()