import requests
from bs4 import BeautifulSoup
import pypandoc
import os
from datetime import datetime

# URLs of the websites to scrape
urls = {
    "Philstar": "https://www.philstar.com/opinion",
    "Inquirer": "https://opinion.inquirer.net"
}

# Function to scrape the latest article link from Philstar
def get_latest_philstar_article(url):
    print(f"!!! Fetching latest article from {url}...")
    response = requests.get(url)
    if response.status_code == 200:
        print("!!! Successfully fetched Philstar page.")
        soup = BeautifulSoup(response.content, 'html.parser')

        # Fetch the actual latest article with time filter
        latest_article = None
        for item in soup.find_all('div', class_='carousel__item'):
            time_text = item.find('div', class_='carousel__item__time').get_text(strip=True)
            if "day" not in time_text:
                latest_article = item.find('a', href=True)
                break

        if latest_article:
            print(f"!!! Latest article found on Philstar: {time_text}")
            return latest_article['href'], True  # Return link and date tag status
        else:
            print("### No recent article found on Philstar.")
            return "### No article found", False
    else:
        print(f"### Failed to fetch Philstar page. Status code: {response.status_code}")
        return "### Failed to fetch", False

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

# Function to extract content from Philstar
def extract_philstar_content(article_url):
    print(f"!!! Extracting content from Philstar article: {article_url}")
    response = requests.get(article_url)
    if response.status_code == 200:
        print("!!! Successfully fetched Philstar article.")
        title = BeautifulSoup(response.content, 'html.parser').title.string.strip()  # Extract the title
        article_content_div = BeautifulSoup(response.content, 'html.parser').find('div', id='sports_article_writeup')
        if article_content_div:
            paragraphs = article_content_div.find_all('p')
            article_text = "\n\n".join([para.get_text() for para in paragraphs])
            print("!!! Content extracted from Philstar article.")
            return title, article_text
        print("### No content div found in Philstar article.")
    else:
        print(f"### Failed to fetch Philstar article. Status code: {response.status_code}")
    return "### No title", "No content found"

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
    article_content = extract_philstar_content(article_url)[1]  # Get article content only

    # Combine title, link, and article content into a single Markdown string
    markdown_content = f"# {title}\n\n{article_url}\n\n\n\n{article_content}"

    # Determine the correct directory based on whether the article has a date tag or not
    if has_date_tag:
        markdown_dir = f"articles/md/{site}/"
        docx_dir = f"articles/docx/{site}/"
    else:
        markdown_dir = "articles/tps-top/md/"
        docx_dir = "articles/tps-top/docx/"

    # Save Markdown content
    markdown_filename = f"{markdown_dir}{title}.md"
    os.makedirs(os.path.dirname(markdown_filename), exist_ok=True)  # Ensure directory exists
    with open(markdown_filename, "w", encoding='utf-8') as f:
        f.write(markdown_content)

    print(f"!!! Markdown content saved as {title}.md successfully.")

    # Convert Markdown string to DOCX and save
    output_filename = f"{docx_dir}{title}.docx"
    os.makedirs(os.path.dirname(output_filename), exist_ok=True)  # Ensure directory exists
    pypandoc.convert_text(markdown_content, 'docx', format='md', outputfile=output_filename)

    print(f"!!! Content saved as {title}.docx successfully.")

# Dictionary to store the results
latest_articles = {}

# Scrape the articles from both websites
latest_articles['Philstar'], philstar_has_date_tag = get_latest_philstar_article(urls['Philstar'])
latest_articles['Inquirer'], inquirer_has_date_tag = get_latest_inquirer_article(urls['Inquirer'])

# Extract and convert the article content
for site, link in latest_articles.items():
    if link != "No article found":
        print(f"!!! Extracting content from {site}...")
        if site == 'Inquirer':
            title, article_content = extract_inquirer_content(link)
            has_date_tag = inquirer_has_date_tag
        else:
            title, article_content = extract_philstar_content(link)
            has_date_tag = philstar_has_date_tag

        # Save the article in the appropriate folder
        save_article(link, title, has_date_tag, site)
    else:
        print(f"NO ARTICLE FOUND: {site}")