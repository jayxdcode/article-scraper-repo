import requests
        from bs4 import BeautifulSoup
        
        # URLs of the websites to scrape
        urls = {
            "Philstar": "https://www.philstar.com/opinion",
            "Inquirer": "https://opinion.inquirer.net"
        }
        
        # Function to scrape the latest article link from Philstar
        def get_latest_philstar_article(url):
            response = requests.get(url)
            soup = BeautifulSoup(response.content, 'html.parser')
        
            # Find the first editorial link from the specified div
            latest_article = soup.find('div', class_='carousel_item_title').find('a', href=True)
        
            if latest_article:
                return latest_article['href']
            else:
                return "No article found"
        
        # Function to scrape the latest article link from Inquirer
        def get_latest_inquirer_article(url):
            response = requests.get(url)
            soup = BeautifulSoup(response.content, 'html.parser')
        
            # Find the first link in the "oped-readmore" div
            latest_article = soup.find('div', id='oped-readmore').find('a', href=True)
        
            if latest_article:
                return latest_article['href']
            else:
                return "No article found"
        
        # Function to extract the content of the article for Inquirer
        def extract_inquirer_content(article_url):
            response = requests.get(article_url)
            soup = BeautifulSoup(response.content, 'html.parser')
        
            # Extract paragraphs inside the div with id 'article_content'
            paragraphs = soup.find('div', id='article_content').find_all('p')
            article_text = "\n".join([para.get_text() for para in paragraphs])
        
            return article_text
        
        # Function to extract the content of the article for Philstar
        def extract_philstar_content(article_url):
            response = requests.get(article_url)
            soup = BeautifulSoup(response.content, 'html.parser')
        
            # Extract paragraphs inside the div with id 'sports_article_writeup'
            paragraphs = soup.find('div', id='sports_article_writeup').find_all('p')
            article_text = "\n".join([para.get_text() for para in paragraphs])
        
            return article_text
        
        # Dictionary to store the results
        latest_articles = {}
        
        # Scrape the articles from both websites
        latest_articles['Philstar'] = get_latest_philstar_article(urls['Philstar'])
        latest_articles['Inquirer'] = get_latest_inquirer_article(urls['Inquirer'])
        
        # Extract and save the article content
        for site, link in latest_articles.items():
            if link != "No article found":
                if site == 'Inquirer':
                    article_content = extract_inquirer_content(link)
                else:
                    article_content = extract_philstar_content(link)
                
                # Save the article content to a text file
                with open(f"{site}_editorial.txt", "w", encoding='utf-8') as f:
                    f.write(article_content)
                
                # Save the article content to a markdown file
                with open(f"{site}_editorial.md", "w", encoding='utf-8') as f:
                    f.write(f"# {site} Editorial\n\n")
                    f.write(article_content)
            else:
                print(f"No article found for {site}")