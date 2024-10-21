import requests
from datetime import datetime, timezone, timedelta  # Import timezone and timedelta
from bs4 import BeautifulSoup
import pypandoc
import os

# Verify timezone
print(f"STARTING... CURRENT TIME: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# URLs of the websites to scrape
urls = {
    "Philstar": "https://www.philstar.com/opinion",
    "Inquirer": "https://opinion.inquirer.net"
}

# Other functions...

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
    pypandoc.convert_text(markdown_content, 'docx', format='md', outputfile=output_filename