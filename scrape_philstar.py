import requests
from bs4 import BeautifulSoup
import pypandoc
import os

# URL of the Philstar opinion section
philstar_url = "https://www.philstar.com/opinion"

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

# Scrape the article from Philstar
latest_article_link, has_date_tag = get_latest_philstar_article(philstar_url)
if latest_article_link != "### No article found":
    print(f"!!! Extracting content from Philstar...")
    title, article_content = extract_philstar_content(latest_article_link)
    save_article(latest_article_link, title, has_date_tag, "Philstar")
else:
    print("NO ARTICLE FOUND: Philstar")