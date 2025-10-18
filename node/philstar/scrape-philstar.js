// scrape-philstar.js (edited)
const fs = require('fs-extra');
const path = require('path');
const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
const UserAgent = require('user-agents');
const minimist = require('minimist');

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
const OUT_DIR = path.join(repoRoot, 'articles', 'philstar');

try {
  fs.ensureDirSync(LOG_DIR);
  fs.ensureDirSync(OUT_DIR);
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
    .replace(/[<>:\"|?*\x00-\x1F]/g, '')
    .slice(0,200)
    .trim();
}

async function discoverLinks(page) {
  const indexUrl = siteCfg.index_url || 'https://www.philstar.com/opinion';
  await page.goto(indexUrl, { waitUntil: 'networkidle2', timeout: config.puppeteer?.defaultTimeout || 60000 });
  try {
    const hrefs = await page.$$eval(siteCfg.link_selector || '.article__teaser a', (els, attr) =>
      els.map(e => e.getAttribute(attr) || e.href || '').filter(Boolean),
      siteCfg.link_attr || 'href'
    );
    const unique = Array.from(new Set(hrefs)).slice(0, siteCfg.link_limit || 5);
    const abs = unique.map(h => {
      try { return new URL(h, indexUrl).toString(); } catch (e) { return h; }
    });
    return abs;
  } catch (e) {
    appendLog('Philstar discovery failed: ' + String(e));
    return [];
  }
}

async function run() {
  const today = new Date();
  const year = today.getFullYear();
  const month = String(today.getMonth() + 1).padStart(2, '0');
  const day = String(today.getDate()).padStart(2, '0');
  const fmtDate = `${year}-${month}-${day}`;
  const R = () => Math.random().toString(36).substring(2, 7);

  console.log(`\nRun ID PHS_${fmtDate}_${R()}\n`);

  const defaultChrome = path.join(repoRoot, 'chrome', 'linux-121.0.6167.85', 'chrome-linux64', 'chrome');
  const executablePath = process.env.PUPPETEER_EXECUTABLE_PATH || (fs.existsSync(defaultChrome) ? defaultChrome : undefined);

  if (!executablePath) {
    console.error('No puppeteer executablePath found. Set PUPPETEER_EXECUTABLE_PATH or commit the chrome binary to:');
    console.error(defaultChrome);
    process.exit(2);
  }

  let browser;
  try {
    browser = await puppeteer.launch({
      headless: config.puppeteer?.headless !== false,
      args: ['--no-sandbox','--disable-setuid-sandbox'],
      defaultViewport: { width: 1200, height: 900 },
      executablePath
    });
  } catch (err) {
    console.error('Failed to launch browser:', err && err.message ? err.message : err);
    process.exit(2);
  }

  const page = await browser.newPage();
  await page.setUserAgent(new UserAgent().toString());
  await page.setExtraHTTPHeaders({ 'accept-language': 'en-US,en;q=0.9' });

  try {
    let targetUrl = urlArg;

    if (discover) {
      appendLog('Philstar: discovery mode');
      const links = await discoverLinks(page);
      if (!links || !links.length) {
        appendLog('Philstar discovery returned no links; falling back to test_urls if present');
        if (siteCfg.test_urls && siteCfg.test_urls.length) {
          targetUrl = siteCfg.test_urls[0];
        } else {
          throw new Error('No philstar links discovered and no fallback test_urls');
        }
      } else {
        targetUrl = links[0];
        appendLog('Philstar discovered: ' + targetUrl);
      }
    }

    appendLog('Philstar loading article: ' + targetUrl);
    await page.goto(targetUrl, { waitUntil: 'networkidle2', timeout: config.puppeteer?.defaultTimeout || 60000 });

    const data = await page.evaluate((contentSelector, featureSelector) => {
      const titleEl = document.querySelector('h1.article__title') || document.querySelector('h1');
      const title = titleEl ? titleEl.textContent.trim() : (document.title || '').trim();

      const authorNode = document.querySelector('div.article__credits-author-pub');
      const author = authorNode ? authorNode.textContent.trim() : '';

      const dateNode = document.querySelector('div.article__date-published');
      const date = dateNode ? dateNode.textContent.trim() : '';

      let feature = null;
      if (featureSelector) {
        const f = document.querySelector(featureSelector);
        if (f && f.src) feature = f.src;
        else if (f) {
          const img = f.querySelector('img');
          if (img && img.src) feature = img.src;
        }
      } else {
        const img = document.querySelector('div#sports_header_image img, figure img');
        if (img && img.src) feature = img.src;
      }

      const contentContainer = document.querySelector(contentSelector) || document.querySelector('div.article__writeup') || null;
      let paragraphs = [];
      if (contentContainer) {
        const ps = contentContainer.querySelectorAll(':scope > p');
        paragraphs = Array.from(ps).map(p => p.textContent.trim()).filter(Boolean);
      } else {
        const ps = document.querySelectorAll('article p');
        paragraphs = Array.from(ps).map(p => p.textContent.trim()).filter(Boolean);
      }

      return { title, author, date, feature, paragraphs };
    }, siteCfg.content, siteCfg.feature_image_selector);

    if (!data || !data.paragraphs || data.paragraphs.length === 0) {
      throw new Error('Philstar: no paragraphs extracted');
    }

    const md = [
      '### Opinion',
      `# ${data.title}`,
      data.author ? `#### ${data.author}` : '',
      data.date ? `#### ${data.date}` : '',
      data.feature ? `![featured](${data.feature})` : '',
      '---',
      '',
      data.paragraphs.join('\n\n')
    ].filter(Boolean).join('\n\n');

    const filename = `${fmtDate} ${sanitizeFileName(data.title || "### No Title")}.md`;
    const outPath = path.join(OUT_DIR, filename);

    try {
      fs.writeFileSync(outPath, md, 'utf8');
      appendLog('Philstar saved: ' + outPath);
      console.log('Saved:', outPath);
    } catch (err) {
      appendLog('Philstar failed to write file: ' + String(err));
      throw err;
    }

    await browser.close();
    process.exit(0);
  } catch (err) {
    appendLog('Philstar fatal: ' + String(err));
    console.error(err && err.message ? err.message : err);
    try { await browser.close(); } catch (e) {}
    process.exit(2);
  }
}

run();
