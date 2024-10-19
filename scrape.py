import requests
from datetime import datetime
from bs4 import BeautifulSoup

# URLs of the websites to scrape
urls = {
    "Philstar": "https://www.philstar.com/opinion",
    "Inquirer": "https://opinion.inquirer.net"
}

# Function to scrape the latest article link from Philstar
def get_latest_philstar_article(url):
    print(f"Fetching latest article from {url}...")
    response = requests.get(url)
    if response.status_code == 200:
        print("Successfully fetched Philstar page.")
        soup = BeautifulSoup(response.content, 'html.parser')

        # Find the first editorial link from the specified div
        latest_article = soup.find('div', class_='carousel__item carousel__item-0').find('a', href=True)

        if latest_article:
            print("Latest article found on Philstar.")
            return latest_article['href']
        else:
            print("No article found on Philstar.")
            return "No article found"
    else:
        print(f"Failed to fetch Philstar page. Status code: {response.status_code}")
        return "Failed to fetch"

# Function to scrape the latest article link from Inquirer
def get_latest_inquirer_article(url):
    print(f"Fetching latest article from {url}...")
    
    # Adding a user-agent header
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36'
    }
    
    response = requests.get(url, headers=headers)
    print(f"Response code: {response.status_code}")
    
    if response.status_code == 200:
        print("Successfully fetched Inquirer page.")
        soup = BeautifulSoup(response.content, 'html.parser')
        
        latest_article = soup.find('a', class_='entry-title', href=True)
        if latest_article:
            print("Latest article found on Inquirer.")
            return latest_article['href']
        else:
            print("No article found on Inquirer.")
    else:
        print(f"Failed to fetch Inquirer page. Status code: {response.status_code}")
    
    return "No article found"

# Function to extract the content of the article for Philstar
def extract_philstar_content(article_url):
    print(f"Extracting content from Philstar article: {article_url}")
    response = requests.get(article_url)
    if response.status_code == 200:
        print("Successfully fetched Philstar article.")
        soup = BeautifulSoup(response.content, 'html.parser')
        
        title = soup.title.string.strip()  # Extract the title of the article
        article_content_div = soup.find('div', id='sports_article_writeup')
        if article_content_div:
            paragraphs = article_content_div.find_all('p')
            article_text = "\n".join([para.get_text() for para in paragraphs])
            print("Content extracted from Philstar article.")
            return title, article_text
        
        print("No content div found in Philstar article.")
    else:
        print(f"Failed to fetch Philstar article. Status code: {response.status_code}")

    return "No title", "No content found"

# Function to extract the content of the article for Inquirer
def extract_inquirer_content(article_url):
    print(f"Fetching article content from {article_url}...")
    
    # Adding a user-agent header
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36'
    }
    
    response = requests.get(article_url, headers=headers)
    print(f"Response code: {response.status_code}")
    
    if response.status_code == 200:
        print("Successfully fetched article page.")
        soup = BeautifulSoup(response.content, 'html.parser')

        title = soup.title.string.strip()  # Extract the title of the article
        paragraphs = soup.find('section', id='inq_section').find_all('p')
        article_text = "\n\n".join([para.get_text() for para in paragraphs])

        if article_text:
            print("Article content extracted successfully.")
            return title, article_text
        else:
            print("No paragraphs found in the article.")
    else:
        print("Failed to fetch article page.")

    return "No title", "No content found"

# Dictionary to store the results
latest_articles = {}

# Scrape the articles from both websites
latest_articles['Philstar'] = get_latest_philstar_article(urls['Philstar'])
latest_articles['Inquirer'] = get_latest_inquirer_article(urls['Inquirer'])

# Extract and save the article content
for site, link in latest_articles.items():
    if link != "No article found":
        print(f"Extracting content for {site} article...")
        if site == 'Inquirer':
            title, article_content = extract_inquirer_content(link)
        else:
            title, article_content = extract_philstar_content(link)

        # Save the article content to a text file
        with open(f"articles/txt/{site}-{datetime.now().strftime('%Y%m%d')}.txt", "w", encoding='utf-8') as f:
            f.write(f"{link} \n\n")
            f.write(f"{title} \n\n")
            f.write(article_content)

        # Save the article content to a markdown file
        with open(f"articles/md/{site}-{datetime.now().strftime('%Y%m%d')}.md", "w", encoding='utf-8') as f:
            f.write(f"# {title}\n\n")
            f.write(f"{link} \n\n")
            f.write("-- \n\n")
            f.write(article_content)

        print(f"Content for {site} article saved successfully.")
    else:
        print(f"No article found for {site}")