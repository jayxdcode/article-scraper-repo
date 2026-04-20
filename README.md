# article-scraper-repo

https://jayxdcode.github.io/article-scraper-repo/

[![Workflow status](https://github.com/jayxdcode/article-scraper-repo/actions/workflows/auto-scraper.yml/badge.svg)](https://github.com/jayxdcode/article-scraper-repo/actions/workflows/auto-scraper.yml)

A dual-implementation scraping toolkit featuring both **Node.js** and **Python** versions for extracting, structuring, and processing article content from various online platforms.

The **Node.js version is currently active and maintained**, while the **Python version is available but temporarily disabled**. Designed with modularity and flexibility in mind, this repository enables easy integration, selector customization, automated selector validation, and workflow-driven consistency checks.

*The plan is to integrate this as an API on other projects to automatically deliver specific article category to the user from many sources in one app. (Web and/or Android)*

---

## ✅ Status & Badges

### 📦 CI & Build Status

![NodeJS Workflow (Disabled)](https://img.shields.io/badge/NodeJS%20Scraper-enabled-green)
![Python Workflow (Disabled)](https://img.shields.io/badge/Python%20Scraper-disabled-lightgrey)

### Configurations
[![Run Selectors Tests & Report (Node.js)](https://github.com/jayxdcode/article-scraper-repo/actions/workflows/test.yml/badge.svg)](https://github.com/jayxdcode/article-scraper-repo/actions/workflows/test.yml)

### 📌 Project Info
![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)  
![Node.js](https://img.shields.io/badge/Powered%20by-Node.js-blue.svg)  
![Python](https://img.shields.io/badge/Available%20in-Python-yellow.svg)  

<!-- Optional for later:
![PyPI Version](https://img.shields.io/pypi/v/article-scraper.svg)
![GitHub Stars](https://img.shields.io/github/stars/jayxdcode/article-scraper-repo.svg)
-->

---

## ✨ Features

- **Markdown** & **DOCX** outputs
- **Dual-language support** – Node.js scraper active; Python version available but disabled.
- **Site-based modular architecture** – independent configurations for each source.
- **Customizable selectors** – adaptable to layout or UI changes.
- **Extracts titles, dates, authors, content, and media (where supported).**
- **Automated selector testing via CI workflows.**
- **Outputs structured JSON or Markdown for further processing.**
- **Batch processing ready** – ideal for large-scale article collection.
- **Extensible codebase** – add new sites or exporters easily.

---

## ⚙️ Setup & Installation (Node.js version - Active)

### ✅ Prerequisites
- ✅ Node.js v14+  
- ✅ npm (or pnpm/yarn)  
- ✅ Git

### 📥 Installation Steps

```bash
# 1. Clone the repository
git clone https://github.com/jayxdcode/article-scraper-repository.git
# 2. Navigate into the folder
cd article-scraper-repo

# 3. Install Node dependencies
npm install
```

> install.sh will be available in later updates.

> 📌 Python environment setup is optional at the moment, as the Python scraper workflow is currently disabled.




---

### 🧪 Optional Python Setup (Currently Disabled)

```bash
# Create virtual environment
python -m venv venv

# Activate (macOS/Linux)
source venv/bin/activate

# Activate (Windows)
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

> ⚠️ Note: The Python scraper logic is present but not currently active or tested through CI.




---

## 🖥️ Node.js Usage Example

```js
// Example usage (Node.js)
const { scrapeArticle } = require('./src/scraper');

(async () => {
  const url = 'https://example.com/sample-article';
  const result = await scrapeArticle(url);
  console.log(result);
})();
```

### 📘 Expected Output (Structure Example)

```json
{
  "title": "Sample Article Title",
  "author": "Author Name",
  "date": "2025-10-19",
  "content": "Full article content here...",
  "images": ["https://example.com/image1.jpg"]
}
```

---

## 🛠️ Technologies Used

Component
Node.js Version 20
Python Version 3.14 (Disabled)

Runtime
 - Node.js
 - Python

| Component | Node.js | Python |
|---|---|---|
| HTTP Requests | node-fetch (or similar) | requests |
| Parsing |	cheerio	| BeautifulSoup / lxml |
| Output Handling | JSON / Markdown	/ DOCX (markdown-docx) JSON / Markdown (pandoc) |
| CI/CD	| GitHub Actions | GitHub Actions (workflow disabled) |



---


## 📄 License

Licensed under the BSD 3-Clause License.
See the full details in the LICENSE file.


---

*Ideas, enhancements, or questions? Open an issue and i'll figure it out.*
