// /node/philstar/scrape-philstar.js
const fs = require('fs-extra');
const path = require('path');
const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
const UserAgent = require('user-agents');
const minimist = require('minimist');
const markdownDocx = require('markdown-docx');
const { Packer } = require('markdown-docx');

puppeteer.use(StealthPlugin());

const argv = minimist(process.argv.slice(2));
const urlArg = argv.url || argv.u || '';
const discover = argv.discover || (!urlArg);

const repoRoot = path.resolve(__dirname, '..', '..');
const configPath = path.join(repoRoot, 'config.json');

let config = {};
try {
  if (!fs.existsSync(configPath)) {
    console.error(`config.json not found at ${configPath}`);
    process.exit(2);
  }
  config = fs.readJSONSync(configPath);
} catch (err) {
  console.error('Failed reading config.json:', err && err.message ? err.message : err);
  process.exit(2);
}

const siteCfg = (config.sites && config.sites['philstar']) || {};

const LOG_DIR = path.join(repoRoot, 'logs');
const OUT_DIR = path.join(repoRoot, 'articles', 'md', 'Philstar');
const D_OUT_DIR = path.join(repoRoot, 'articles', 'docx', 'Philstar');

try {
  fs.ensureDirSync(LOG_DIR);
  fs.ensureDirSync(OUT_DIR);
  fs.ensureDirSync(D_OUT_DIR);
} catch (err) {
  console.error('Failed creating output directories:', err && err.message ? err.message : err);
  process.exit(2);
}

function nowTs() { return new Date().toISOString(); }
function appendLog(line) {
  const entry = `[${nowTs()}] ${line}\n`;
  try {
    fs.appendFileSync(path.join(LOG_DIR, 'scrape-log.txt'), entry, 'utf8');
  } catch (e) {
    console.error('Failed to append log:', e && e.message ? e.message : e);
  }
}

function sanitizeFileName(s) {
  return String(s || 'article')
    .replace(/[\\/]/g, '_')
    .replace(/[<>:\\"|?*\x00-\x1F]/g, '')
    .replace(/[\u201C\u201D\u201E\u2033]/g, '-')
    .replace(/[\u2018\u2019\u2032]/g, " ")
    .slice(0,200)
    .trim();
}

async function md2docx(markdownFilePath, outputFilePath) {
  try {
    const markdown = await fs.readFile(markdownFilePath, 'utf-8');
    const doc = await markdownDocx(markdown);
    const buffer = await Packer.toBuffer(doc);
    await fs.writeFile(outputFilePath, buffer);
    console.log(`Conversion completed: ${outputFilePath}`);
  } catch (error) {
    appendLog('Error during conversion: ' + error.message);
    console.error('Error during conversion:', error);
  }
}

const NAV_TIMEOUT = config.puppeteer?.defaultTimeout ?? 45000;

async function discoverLinks(page) {
  const indexUrl = siteCfg.index_url || 'https://www.philstar.com/opinion';
  appendLog('Discovering links at: ' + indexUrl);
  
  // Use domcontentloaded for speed; networkidle2 often fails on news sites
  await page.goto(indexUrl, { waitUntil: 'domcontentloaded', timeout: NAV_TIMEOUT });
  
  const itemSelector = siteCfg.items_selector || '.carousel__item';
  try {
    // Wait specifically for the items to appear
    await page.waitForSelector(itemSelector, { timeout: 10000 });

    const links = await page.$$eval(
      itemSelector, 
      (els, cfg) => {
        const recentRegex = /second|minute|hour|day/i; // Added 'day' as a fallback

        return els
          .filter(e => {
            const timeEl = e.querySelector(cfg.pub_time); 
            const timeStr = timeEl ? timeEl.innerText.toLowerCase() : '';
            return recentRegex.test(timeStr);
          })
          .map(e => {
            const attr = e.getAttribute(cfg.link_attr || 'href');
            // Check nested anchor if the item itself isn't the link
            if (!attr) {
              const anchor = e.querySelector('a');
              return anchor ? anchor.getAttribute('href') : null;
            }
            return attr;
          })
          .filter(link => link && link.trim().length > 0);
      },
      { link_attr: siteCfg.link_attr, pub_time: siteCfg.pub_time || '.article__date' }
    );

    const unique = Array.from(new Set(links)).slice(0, siteCfg.link_limit || 1);
    const abs = unique.map(h => {
      try { return new URL(h, indexUrl).toString(); } catch (e) { return h; }
    });
    
    console.log(`[DEBUG] Discovered: ${abs.length} links`);
    return abs;
  } catch (e) {
    appendLog('Philstar discovery failed/timed out: ' + String(e));
    return [];
  }
}

async function tryRawFetchAndSet(page, url, uaString) {
  try {
    appendLog('Attempting raw fetch fallback for: ' + url);
    const raw = await page.evaluate(async (url, ua) => {
      try {
        const resp = await fetch(url, { headers: { 'User-Agent': ua, 'Accept-Language': 'en-US,en;q=0.9' } });
        const text = await resp.text();
        return { ok: true, text };
      } catch (err) {
        return { ok: false, err: String(err) };
      }
    }, url, uaString);

    if (!raw || !raw.ok) return false;
    await page.setContent(raw.text, { waitUntil: 'domcontentloaded' });
    return true;
  } catch (e) {
    appendLog('Raw fetch failed: ' + String(e));
    return false;
  }
}

async function run() {
  const today = new Date();
  const fmtDate = today.toISOString().split('T')[0];
  const R = () => Math.random().toString(36).substring(2, 7);

  console.log(`\nRun ID PHS_${fmtDate}_${R()}\n`);

  const defaultChrome = path.join(repoRoot, 'chrome', 'linux-121.0.6167.85', 'chrome-linux64', 'chrome');
  const executablePath = process.env.PUPPETEER_EXECUTABLE_PATH || (fs.existsSync(defaultChrome) ? defaultChrome : undefined);

  if (!executablePath) {
    console.error('No chrome binary found.');
    process.exit(2);
  }

  const browser = await puppeteer.launch({
    headless: 'new', // Use 'new' headless mode for better compatibility
    args: ['--no-sandbox','--disable-setuid-sandbox', '--disable-dev-shm-usage'],
    defaultViewport: { width: 1200, height: 900 },
    executablePath
  });

  const page = await browser.newPage();
  const ua = new UserAgent().toString();
  await page.setUserAgent(ua);

  try {
    let targetUrl = urlArg;

    if (discover) {
      const links = await discoverLinks(page);
      if (!links || !links.length) {
        throw new Error('No philstar links discovered.');
      }
      targetUrl = links[0];
    }

    appendLog('Philstar loading: ' + targetUrl);

    try {
      await page.goto(targetUrl, { waitUntil: 'domcontentloaded', timeout: NAV_TIMEOUT });
      // Ensure the article writeup is present before continuing
      await page.waitForSelector('.article__writeup, h1.article__title', { timeout: 15000 });
    } catch (err) {
      appendLog('Initial navigation failed, trying fallback...');
      const ok = await tryRawFetchAndSet(page, targetUrl, ua);
      if (!ok) throw new Error('Navigation and fallback both failed');
    }

    const data = await page.evaluate((contentSelector, featureSelector) => {
      const url = window.location.toString();
      const titleEl = document.querySelector('h1.article__title') || document.querySelector('h1');
      const title = titleEl ? titleEl.textContent.trim() : (document.title || '').trim();

      const authorNode = document.querySelector('div.article__credits-author-pub') || document.querySelector('.article__author');
      const author = authorNode ? authorNode.textContent.trim() : '';

      const dateNode = document.querySelector('div.article__date-published') || document.querySelector('.article__date');
      const date = dateNode ? dateNode.textContent.trim() : '';

      let feature = null;
      if (featureSelector) {
        const f = document.querySelector(featureSelector);
        if (f && f.src) feature = f.src;
        else if (f) {
          const img = f.querySelector('img');
          if (img && img.src) feature = img.src;
        }
      } 
      
      if (!feature) {
        const img = document.querySelector('div#sports_header_image img, figure img, .article__main-image img');
        if (img && img.src) feature = img.src;
      }

      const contentContainer = document.querySelector(contentSelector) || document.querySelector('div.article__writeup');
      let paragraphs = [];
      if (contentContainer) {
        const ps = contentContainer.querySelectorAll('p');
        paragraphs = Array.from(ps).map(p => p.textContent.trim()).filter(p => (p.length > 13 && p !== "ADVERTISEMENT")); 
      } else {
        const ps = document.querySelectorAll('article p');
        paragraphs = Array.from(ps).map(p => p.textContent.trim()).filter(p => (p.length > 13 && p !== "ADVERTISEMENT")); 
      }

      return { url, title, author, date, feature, paragraphs };
    }, siteCfg.content, siteCfg.feature_image_selector);

    if (!data || !data.paragraphs || data.paragraphs.length === 0) {
      throw new Error('No content found in article');
    }

    const md = [
      '### Opinion',
      `# ${data.title}`,
      data.author ? `#### ${data.author}` : '',
      data.date ? `#### ${data.date}` : '',
      data.feature ? `![featured](${data.feature})` : '',
      data.url ? `[${data.url}](${data.url})` : '',
      '---',
      '',
      data.paragraphs.join('\n\n')
    ].filter(Boolean).join('\n\n');

    const filename = `${fmtDate} ${sanitizeFileName(data.title)}`;
    const outPath = path.join(OUT_DIR, `${filename}.md`);
    const docxOut = path.join(D_OUT_DIR, `${filename}.docx`);

    fs.writeFileSync(outPath, md, 'utf8');
    console.log('Saved Markdown:', outPath);

    await md2docx(outPath, docxOut);

    await browser.close();
    process.exit(0);
  } catch (err) {
    appendLog('Philstar fatal: ' + String(err));
    console.error('Fatal Error:', err.message);
    if (browser) await browser.close();
    process.exit(2);
  }
}

run();
