
import requests
from bs4 import BeautifulSoup

# URLs of the websites to scrape
urls = {
    "Philstar": "https://www.philstar.com/opinion",
    "Inquirer": "https://opinion.inquirer.net"
}

# Function to scrape the latest article link
def get_latest_article(url, link_identifier):
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')

    # Find the first article link based on the identifier
    latest_article = soup.find('a', href=True, text=True)

    # Check if we found a link
    if latest_article:
        return latest_article['href']
    else:
        return "No article found"

# Dictionary to store the results
latest_articles = {}

# Scrape the articles from both websites
for site, url in urls.items():
    latest_articles[site] = get_latest_article(url, "opinion")

# Write the results to a text file
with open("editorials.txt", "w") as f:
    for site, link in latest_articles.items():
        f.write(f"{site}: {link}\n")
