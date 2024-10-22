import os
import requests
from bs4 import BeautifulSoup
import pypandoc
from datetime import datetime

# URL of the Philstar opinion section
philstar_url = "https://philstar.com/opinion"

# Function to extract content from Philstar
def extract_philstar_content(article_url):
    response = requests.get(article_url)
    if response.status_code == 200:
        soup = BeautifulSoup(response.content, 'html.parser')
        title = soup.title.string.strip()  # Adjust this according to the actual title tag
        content_tags = soup.find('div', class_='article__content').find_all('p')  # Adjust according to the actual content tag
        content = "\n\n".join([tag.get_text(strip=True) for tag in content_tags])
        return title, content
    return None, None

# Function to save article as markdown and docx
def save_article(url, title, content, save_path):
    date_prefix = datetime.now().strftime("%Y%m%d")
    safe_title = title.replace('/', '_')

    # Ensure the directory exists
    os.makedirs(save_path, exist_ok=True)

    # Save title and content to a markdown file
    md_file_path = os.path.join(save_path, f"{date_prefix}_{safe_title}.md")
    with open(md_file_path, 'w', encoding='utf-8') as file:
        file.write(f"# {title}\n\n[Read more here]({url})\n\n{content}")

    print(f"!!! Markdown content saved as {md_file_path}.")

    # Convert Markdown to DOCX
    convert_md_to_docx(md_file_path, save_path, date_prefix, safe_title)

# Function to convert Markdown to DOCX
def convert_md_to_docx(md_file_path, save_path, date_prefix, safe_title):
    docx_file_path = os.path.join(save_path, f"[{date_prefix}] {safe_title}.docx")
    
    try:
        pypandoc.convert_file(md_file_path, 'docx', outputfile=docx_file_path)
        print(f"!!! Converted {md_file_path} to {docx_file_path}.")
    except Exception as e:
        print(f"### Failed to convert {md_file_path} to DOCX: {str(e)}")

# Function to get the latest article from Philstar
def get_latest_philstar_article(url):
    print(f"!!! Fetching latest article from {url}...")
    response = requests.get(url)
    if response.status_code == 200:
        print("!!! Successfully fetched Philstar page.")
        soup = BeautifulSoup(response.content, 'html.parser')

        # Fetch the top article
        try:
            latest_top_article = soup.find('div', class_='carousel__item carousel__item-0').find('a', href=True)
            if latest_top_article:
                article_url = latest_top_article['href']
                print(f"!!! Latest top article found on Philstar: {article_url}")
                title, content = extract_philstar_content(article_url)  # Get the title and content
                if title and content:
                    save_article(article_url, title, content, 'articles/tps-top/md')  # Save to markdown
                    save_article(article_url, title, content, 'articles/tps-top/docx')  # Save to docx
            else:
                print("### Top article not found.")
        except AttributeError as e:
            print("### Error fetching top article:", str(e))

        # Fetch the actual latest article with time filter
        latest_article = None
        for item in soup.find_all('div', class_='carousel__item'):
            time_element = item.find('div', class_='carousel__item__time')
            if time_element:
                time_text = time_element.get_text(strip=True)
                if "day" not in time_text:  # Check if the article is recent
                    latest_article = item.find('a', href=True)
                    break

        if latest_article:
            article_url = latest_article['href']
            print(f"!!! Latest article found on Philstar: {article_url}")
            title, content = extract_philstar_content(article_url)
            if title and content:
                save_article(article_url, title, content, 'articles/md/Philstar')
                save_article(article_url, title, content, 'articles/docx/Philstar')
        else:
            print("### No recent article found on Philstar.")
    else:
        print(f"### Failed to fetch Philstar page. Status code: {response.status_code}")


# Fetch and save the latest Philstar article
get_latest_philstar_article(philstar_url)