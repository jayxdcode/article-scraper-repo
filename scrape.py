import requests
import datetime
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
    response = requests.get(url)
    if response.status_code == 200:
        print("Successfully fetched Inquirer page.")
        soup = BeautifulSoup(response.content, 'html.parser')

        # Find the div with id 'opinion-v2-mh'
        opinion_div = soup.find('div', id='opinion-v2-mh')
        if opinion_div:
            print("Found opinion-v2-mh div.")
            # Now find the div with id 'opedv2'
            opedv2_div = opinion_div.find('div', id='opedv2')
            if opedv2_div:
                print("Found opedv2 div.")
                # Now find the div with id 'oped-lbl' to get the h1 tag and its link
                oped_lbl_div = opedv2_div.find('div', id='oped-lbl')
                if oped_lbl_div:
                    print("Found oped-lbl div.")
                    # Now find the 'h1' tag inside 'oped-lbl' to get the latest article link
                    h1_tag = oped_lbl_div.find('h1')
                    if h1_tag:
                        latest_article = h1_tag.find('a', href=True)
                        if latest_article:
                            print("Latest article found on Inquirer.")
                            return latest_article['href']
                        else:
                            print("No article link found in h1 tag on Inquirer.")
                    else:
                        print("No h1 tag found in oped-lbl div on Inquirer.")
                else:
                    print("No oped-lbl div found in opedv2 on Inquirer.")
            else:
                print("No opedv2 div found in opinion-v2-mh on Inquirer.")
        else:
            print("No opinion-v2-mh div found on Inquirer.")
    
    print("No article found on Inquirer.")
    return "No article found"

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

        # Find the div with id 'opinion-v2-mh'
        opinion_div = soup.find('div', id='opinion-v2-mh')
        if opinion_div:
            print("Found opinion-v2-mh div.")
            # Now find the div with id 'opedv2'
            opedv2_div = opinion_div.find('div', id='opedv2')
            if opedv2_div:
                print("Found opedv2 div.")
                # Now find the 'h1' tag inside 'oped-lbl' to get the latest article link
                h1_tag = opedv2_div.find('h1')
                if h1_tag:
                    latest_article = h1_tag.find('a', href=True)
                        
                    if latest_article:
                        print("Latest article found on Inquirer.")
                        return latest_article['href']
                    else:
                            print("No article link found in h1 tag on Inquirer.")
                else:
                        print("No h1 tag found in oped-lbl div on Inquirer.")
            else:
                print("No opedv2 div found in opinion-v2-mh on Inquirer.")
        else:
            print("No opinion-v2-mh div found on Inquirer.")
    
    print("No article found on Inquirer.")
    return "No article found"

# Function to extract the content of the article for Philstar
def extract_philstar_content(article_url):
    print(f"Extracting content from Philstar article: {article_url}")
    response = requests.get(article_url)
    if response.status_code == 200:
        print("Successfully fetched Philstar article.")
        soup = BeautifulSoup(response.content, 'html.parser')

        # Ensure the div exists
        article_content_div = soup.find('div', id='sports_article_writeup')
        if article_content_div:
            paragraphs = article_content_div.find_all('p')
            article_text = "\n".join([para.get_text() for para in paragraphs])
            print("Content extracted from Philstar article.")
            return article_text
        
        print("No content div found in Philstar article.")
    else:
        print(f"Failed to fetch Philstar article. Status code: {response.status_code}")

    return "No content found"
    
    
    
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

        # Extract all paragraph tags inside the article
        paragraphs = soup.find_all('p')
        article_text = "\n".join([para.get_text() for para in paragraphs])

        if article_text:
            print("Article content extracted successfully.")
            return article_text
        else:
            print("No paragraphs found in the article.")
    else:
        print("Failed to fetch article page.")

    return "No content found"

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
            article_content =  extract_inquirer_content(link)
        else:
            article_content = extract_philstar_content(link)

        # Save the article content to a text file
        with open(f"{site}-{datetime.now().strftime('%Y%m%d')}.txt", "w", encoding='utf-8') as f:
            f.write(f"{link} \n\n")
            f.write(f"{site} — Editorial \n\n")
            f.write(article_content)

        # Save the article content to a markdown file
        with open(f"{site}-{datetime.now().strftime('%Y%m%d')}.md", "w", encoding='utf-8') as f:
            f.write(f"# {site} — Editorial")
            f.write("--- \n\n")
            f.write(article_content)

        print(f"Content for {site} article saved successfully.")
    else:
        print(f"No article found for {site}")
        
         