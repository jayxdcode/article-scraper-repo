import requests
from datetime import datetime, timezone, timedelta  # Import timezone and timedelta
from bs4 import BeautifulSoup
import pypandoc
import os

current_datetime = datetime.now().strftime('%Y%m%d')

# Verify timezone
print(f"STARTING... CURRENT TIME: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

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
            title = extract_philstar_content(latest_top_article['href'])[0]  # Get the title
            save_article(latest_top_article['href'], title)  # Save to articles folder

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
            if tag.name == 'h2' and 'wp-block-heading' in tag.get('class', []):
                article_content.append(f"\n\n##  {tag.get_text()}\n\n")
            elif tag.name == 'p':
                article_content.append(tag.get_text())


        filtered_content = [para for para in article_content if not para.startswith("")]
        filtered_content = [para for para in filtered_content if not para.startswith("Subscribe to our daily newsletter")]
        filtered_content = [para for para in filtered_content if not para.startswith("Subscribe to our newsletter!")]
        filtered_content = [para for para in filtered_content if not para.startswith("We use cookies to enhance your experience. By continuing, you agree to our use of cookies. Learn more here.")]  
        filtered_content = [para for para in filtered_content if not para.startswith("This is an information message")]
        filtered_content = [para for para in filtered_content if not para.startswith("By providing an email address. I agree to the Terms of Use and acknowledge that I have read the Privacy Policy.")]
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
def save_article(article_url, title):  # Remove output_directory argument
    article_content = extract_philstar_content(article_url)[1]  # Get article content only

    # Combine title, link, and article content into a single Markdown string
    markdown_content = f"# {title}\n\n{article_url}\n\n\n\n{article_content}"

    # Save the article content to a markdown file in the articles folder
    markdown_filename = f"articles/{title}.md"  # Save directly to articles folder
    os.makedirs(os.path.dirname(markdown_filename), exist_ok=True)  # Ensure directory exists
    with open(markdown_filename, "w", encoding='utf-8') as f:
        f.write(markdown_content)

    print(f"!!! Markdown content saved as {title}.md successfully.")

    # Convert Markdown string to DOCX
    output_filename = f"articles/{title}.docx"  # Save directly to articles folder
    pypandoc.convert_text(markdown_content, 'docx', format='md', outputfile=output_filename)

    print(f"!!! Content saved as {title}.docx successfully.")

# Dictionary to store the results
latest_articles = {}

# Scrape the articles from both websites
latest_articles['Philstar'] = get_latest_philstar_article(urls['Philstar'])
latest_articles['Inquirer'] = get_latest_inquirer_article(urls['Inquirer'])

# Extract and convert the article content
for site, link in latest_articles.items():
    if link != "No article found":
        print(f"!!! Extracting content from {site}...")
        if site == 'Inquirer':
            title, article_content = extract_inquirer_content(link)
        else:
            title, article_content = extract_philstar_content(link)

        # Combine title, link, and article content into a single Markdown string
        markdown_content = f"# {title}\n\n{link}\n\n\n\n{article_content}"

        # Save the article content to a markdown file
        markdown_filename = f"articles/docx/{site}/[{datetime.now(timezone(timedelta(hours=8))).strftime('%Y%m%d')}] {title}.docx"  # Save directly to articles folder
        os.makedirs(os.path.dirname(markdown_filename), exist_ok=True)  # Ensure directory exists
        with open(markdown_filename, "w", encoding='utf-8') as f:
            f.write(markdown_content)

        print(f"!!! Markdown content from {site} saved successfully.")

        # Ensure the directories exist before saving DOCX
        output_filename = f"articles/docx/{site}/[{current_datetime}] {title}.docx"

        os.makedirs(os.path.dirname(output_filename), exist_ok=True)  # Ensure directory exists

        # Convert Markdown string to DOCX
        pypandoc.convert_text(markdown_content, 'docx', format='md', outputfile=output_filename)

        print(f"!!! Content for {site} article saved as DOCX successfully.")
    else:
        print(f"NO ARTICLE FOUND: {site}")