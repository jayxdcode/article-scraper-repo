import requests
from datetime import datetime
from bs4 import BeautifulSoup
import pypandoc
import os

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

        # Fetch the top article
        latest_top_article = soup.find('div', class_='carousel__item carousel__item-0').find('a', href=True)
        if latest_top_article:
            print(f"!!! Latest top article found on Philstar: {latest_top_article['href']}")
            save_article(latest_top_article['href'], "Philstar-Latest-Top")

        # Fetch the actual latest article with time filter
        latest_article = None
        for item in soup.find_all('div', class_='carousel__item'):
            time_text = item.find('div', class_='carousel__item__time').get_text(strip=True)
            if "day" not in time_text:
                latest_article = item.find('a', href=True)
                break

        if latest_article:
            print(f"!!! Latest article found on Philstar: {time_text}")
            return latest_article['href']
        else:
            print("### No recent article found on Philstar.")
            return "### No article found"
    else:
        print(f"### Failed to fetch Philstar page. Status code: {response.status_code}")
        return "### Failed to fetch"

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
            return latest_article[0]['href']
        else:
            print("### No article found on Inquirer.")
    else:
        print(f"### Failed to fetch Inquirer page. Status code: {response.status_code}")
    
    return "### No article found"

# Function to extract content from Philstar
def extract_philstar_content(article_url):
    print(f"!!! Extracting content from Philstar article: {article_url}")
    response = requests.get(article_url)
    if response.status_code == 200:
        print("!!! Successfully fetched Philstar article.")
        soup = BeautifulSoup(response.content, 'html.parser')
        title = f"{soup.title.string.strip()} \n\n"  # Extract the title
        article_content_div = soup.find('div', id='sports_article_writeup')
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
        title = f"{soup.title.string.strip()} \n\n"
        article_section = soup.find('section', id='inq_section')
        if article_section is None:
            print("### Could not find the section with id='inq_section'.")
            return "### No title", "No content found"

        paragraphs_and_headings = article_section.find_all(['p', 'h2'])
        article_content = []
        for tag in paragraphs_and_headings:
            if tag.name == 'h2' and 'wp-block-heading' in tag.get('class', []):
                article_content.append(f"\n\n##  {tag.get_text()}\n\n")
            elif tag.name == 'p':
                article_content.append(tag.get_text())

        filtered_content = article_content[:-2]  
        filtered_content = filtered_content[:-3] + filtered_content[-2:]
        filtered_content = [para for para in filtered_content if not para.startswith("By providing an email address.")]
        article_text = "\n\n".join(filtered_content)

        if article_text:
            print("!!! Article content extracted successfully.")
            return title, article_text
        else:
            print("### No paragraphs found in the article.")
    else:
        print("### Failed to fetch article page.")
    return "### No title", "No content found"

# Function to save article as markdown and docx
def save_article(article_url, filename_prefix, output_directory):
    title, article_content = extract_philstar_content(article_url)

    # Combine title, link, and article content into a single Markdown string
    markdown_content = f"# {title}\n\n{article_url}\n\n\n\n{article_content}"

    # Save the article content to a markdown file
    markdown_filename = f"articles/md/Philstar/{filename_prefix}.md"
    os.makedirs(os.path.dirname(markdown_filename), exist_ok=True)  # Ensure directory exists
    with open(markdown_filename, "w", encoding='utf-8') as f:
        f.write(markdown_content)

    print(f"!!! Markdown content saved as {filename_prefix}.md successfully.")

    # Convert Markdown string to DOCX

    output_filename = f"{output_directory}/{filename_prefix}.docx"
    os.makedirs(output_directory, exist_ok=True)

    pypandoc.convert_text(markdown_content, 'docx', format='md', outputfile=output_filename)

    print(f"!!! Content saved as {filename_prefix}.docx successfully.")

# Dictionary to store the results
latest_articles = {}

# Scrape the articles from both websites
latest_articles['Philstar'] = get_latest_philstar_article(urls['Philstar'])
latest_articles['Inquirer'] = get_latest_inquirer_article(urls['Inquirer'])

# Extract and convert the article content
for site, link in latest_articles.items():
    if link != "No article found":
        print(f"!!! Extracting content for {site} article...")
        if site == 'Inquirer':
            title, article_content = extract_inquirer_content(link)
        else:
            title, article_content = extract_philstar_content(link)

        # Combine title, link, and article content into a single Markdown string
        markdown_content = f"# {title}\n\n{link}\n\n\n\n{article_content}"

        # Save the article content to a markdown file
        markdown_filename = f"articles/md/{site}/{title}-{datetime.now().strftime('%Y%m%d')}.md"
        os.makedirs(os.path.dirname(markdown_filename), exist_ok=True)  # Ensure directory exists
        with open(markdown_filename, "w", encoding='utf-8') as f:
            f.write(markdown_content)

        print(f"!!! Markdown content for {site} article saved successfully.")

        # Convert Markdown string to DOCX
        output_directory = f"articles/docx/{site}"
        output_filename = f"articles/docx/{site}/{title}-{datetime.now().strftime('%Y%m%d')}.docx"
        os.makedirs(output_directory, exist_ok=True)

        pypandoc.convert_text(markdown_content, 'docx', format='md', outputfile=output_filename)

        print(f"!!! Content for {site} article saved as DOCX successfully.")
    else:
        print(f"### No article found for {site}")