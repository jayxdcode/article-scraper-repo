import requests
from bs4 import BeautifulSoup
import pypandoc
import os
from datetime import datetime

site = "Inquirer"

# URL of the Inquirer opinion section
inquirer_url = "https://opinion.inquirer.net"

# Function to scrape the latest article link from Inquirer
def get_latest_inquirer_article(url):
    print(f"!!! Fetching latest article from {url}...")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36'
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        print("!!! Successfully fetched Inquirer page.")
        soup = BeautifulSoup(response.content, 'html.parser')
        latest_article = soup.find('div', id='opinion-v2-mh').find_all('a', href=True)
        if latest_article:
            print("!!! Latest article found on Inquirer.")
            return latest_article[0]['href'], True  # Assuming it has a date tag
        else:
            print("### No article found on Inquirer.")
    else:
        print(f"### Failed to fetch Inquirer page. Status code: {response.status_code}")

    return "### No article found", False

# Function to extract content from Inquirer
def extract_inquirer_content(article_url):
    print(f"!!! Fetching article content from {article_url}...")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36'
    }
    response = requests.get(article_url, headers=headers)
    if response.status_code == 200:
        print("!!! Successfully fetched article page.")
        soup = BeautifulSoup(response.content, 'html.parser')
        title = soup.title.string.strip()
        article_section = soup.find('section', id='inq_section')
        if article_section is None:
            print("### Could not find the section with id='inq_section'.")
            return "### No title", "No content found"

        paragraphs_and_headings = article_section.find_all(['p', 'h2'])
        article_content = []
        for tag in paragraphs_and_headings:
            if tag.name == 'h2':
                article_content.append(f"\n\n##  {tag.get_text()}\n\n")
            elif tag.name == 'p':
                article_content.append(tag.get_text())

        article_text = "\n\n".join(article_content)
        return title, article_text
    else:
        print("### Failed to fetch article page.")
    return "### No title", "No content found"

# Function to save article as markdown and docx
def save_article(article_url, title, has_date_tag, site):
    article_content = extract_inquirer_content(article_url)[1]  # Get article content only
    date_prefix = datetime.now().strftime("%Y%m%d")

    # Combine title, link, and article content into a single Markdown string
    markdown_content = f"# {title}\n\n{article_url}\n\n\n\n{article_content}"

    # Determine the correct directory based on whether the article has a date tag or not
    markdown_dir = f"articles/md/{site}/"
    docx_dir = f"articles/docx/{site}/"

    # Save Markdown content with date prefix
    markdown_filename = f"{markdown_dir}[{date_prefix}] {title}.md"
    os.makedirs(os.path.dirname(markdown_filename), exist_ok=True)  # Ensure directory exists
    with open(markdown_filename, "w", encoding='utf-8') as f:
        f.write(markdown_content)

    print(f"!!! Markdown content saved as {markdown_filename} successfully.")

    # Convert Markdown string to DOCX and save
    output_filename = f"{docx_dir}[{date_prefix}] {title}.docx"
    os.makedirs(os.path.dirname(output_filename), exist_ok=True)  # Ensure directory exists
    pypandoc.convert_text(markdown_content, 'docx', format='md', outputfile=output_filename)

    print(f"!!! Content saved as {output_filename} successfully.")

# Scrape the article from Inquirer
latest_article_link, has_date_tag = get_latest_inquirer_article(inquirer_url)
if latest_article_link != "### No article found":
    print(f"!!! Extracting content from Inquirer...")
    title, article_content = extract_inquirer_content(latest_article_link)
    save_article(latest_article_link, title, has_date_tag, "Inquirer")
else:
    print("NO ARTICLE FOUND: Inquirer")