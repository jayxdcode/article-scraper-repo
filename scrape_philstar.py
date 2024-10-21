import requests
from bs4 import BeautifulSoup
import os

def extract_philstar_content(article_url):
    # Dummy implementation; replace with your actual content extraction logic
    response = requests.get(article_url)
    if response.status_code == 200:
        soup = BeautifulSoup(response.content, 'html.parser')
        title = soup.find('h1').get_text(strip=True)  # Adjust this according to the actual title tag
        content = soup.find('div', class_='article-content').get_text(strip=True)  # Adjust according to the actual content tag
        return title, content
    return None, None

def save_article(url, title, save_path):
    # Ensure the directory exists
    os.makedirs(save_path, exist_ok=True)

    # Save title and URL to a markdown file
    title_filename = title.replace(' ', '_').replace('/', '_') + '.md'
    with open(os.path.join(save_path, title_filename), 'w') as file:
        file.write(f"# {title}\n\n[Read more here]({url})\n")

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
                print(f"!!! Latest top article found on Philstar: {latest_top_article['href']}")
                title, content = extract_philstar_content(latest_top_article['href'])  # Get the title and content
                if title and content:
                    save_article(latest_top_article['href'], title, 'articles/tps-top/md')  # Save to articles/tps-top/md
                    save_article(latest_top_article['href'], title, 'articles/tps-top/docx')  # Save to articles/tps-top/docx
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
                if "day" not in time_text:
                    latest_article = item.find('a', href=True)
                    break

        if latest_article:
            print(f"!!! Latest article found on Philstar: {latest_article['href']}")
            return latest_article['href']
        else:
            print("### No recent article found on Philstar.")
            return "### No article found"
    else:
        print(f"### Failed to fetch Philstar page. Status code: {response.status_code}")
        return "### Failed to fetch"