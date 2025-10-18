// scrape-inquirer.js (edited)
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

const siteCfg = (config.sites && config.sites['inquirer']) || {};

const LOG_DIR = path.join(repoRoot, 'logs');
const OUT_DIR = path.join(repoRoot, 'articles', 'inquirer');

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
    .slice(0, 200)
    .trim();
}

const FIND_FEATURED_IMAGE_SNIPPET = `(function(){
  const walker = document.createTreeWalker(document, NodeFilter.SHOW_COMMENT, null, false);
  let node;
  while ((node = walker.nextNode())) {
    if (node.nodeValue && node.nodeValue.toUpperCase().includes('FEATURED IMAGE')) {
      let cur = node.nextSibling;
      for (let i=0;i<10 && cur;i++) {
        if (cur.nodeType === Node.ELEMENT_NODE) {
          const img = cur.querySelector ? cur.querySelector('img') : null;
          if (img && img.src) return img.src;
          if (cur.tagName && cur.tagName.toLowerCase() === 'img' && cur.src) return cur.src;
        }
        cur = cur.nextSibling;
      }
    }
  }
  return null;
})();`;

async function discoverLatestIndex(page) {
  const indexUrl = siteCfg.index_url || 'https://opinion.inquirer.net/';
  await page.goto(indexUrl, { waitUntil: 'networkidle2', timeout: config.puppeteer?.defaultTimeout || 60000 });
  const found = await page.evaluate(() => {
    if (window.location.hostname === 'opinion.inquirer.net' && window.location.pathname === '/') {
      const listing = document.querySelectorAll("div#opinion-v2-mh");
      const latest = listing && listing[0];
      if (!latest) return { ok: false, reason: 'listing not found' };
      const articleDateEl = latest.querySelector("div.oped-date");
      const articleDate = articleDateEl ? articleDateEl.textContent.trim() : '';
      const articleAnchor = latest.querySelector("a");
      if (!articleAnchor) return { ok: false, reason: 'anchor not found in latest' };
      const articleUrl = articleAnchor.href;
      const title = articleAnchor.textContent ? articleAnchor.textContent.trim() : '';
      return { ok: true, articleUrl, title, articleDate };
    }
    return { ok: false, reason: 'not listing root' };
  });
  return found;
}

async function run() {
  const today = new Date();
  const year = today.getFullYear();
  const month = String(today.getMonth() + 1).padStart(2, '0');
  const day = String(today.getDate()).padStart(2, '0');
  const fmtDate = `${year}-${month}-${day}`;
  const R = () => Math.random().toString(36).substring(2, 7);

  console.log(`\nRun ID INQ_${fmtDate}_${R()}\n`);

  // default chrome path inside repo (committed by deps-commit)
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
      args: ['--no-sandbox', '--disable-setuid-sandbox'],
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
      appendLog('Inquirer: discovery mode');
      const found = await discoverLatestIndex(page);
      if (!found.ok) {
        appendLog(`Inquirer discovery failed: ${found.reason}`);
        if (siteCfg.test_urls && siteCfg.test_urls.length) {
          targetUrl = siteCfg.test_urls[0];
          appendLog(`Inquirer discovery fallback to test_url: ${targetUrl}`);
        } else {
          throw new Error('No discovered article and no fallback test_urls');
        }
      } else {
        targetUrl = found.articleUrl;
        appendLog(`Inquirer discovered: ${targetUrl} (title: ${found.title || 'n/a'})`);
      }
    }

    appendLog(`Inquirer loading article ${targetUrl}`);
    await page.goto(targetUrl, { waitUntil: 'networkidle2', timeout: config.puppeteer?.defaultTimeout || 60000 });

    const articleData = await page.evaluate(() => {
      const articleWrapper = document.querySelector('article');
      if (!articleWrapper) return { ok: false, reason: 'article wrapper not found' };

      const creationNode = articleWrapper.querySelector("div#art_plat");
      const creationInfo = creationNode ? creationNode.textContent.trim() : '';

      const bodyWrapper = articleWrapper.querySelector("div#art_body_wrap div#article_content div#FOR_target_content");
      if (!bodyWrapper) return { ok: false, reason: 'body wrapper not found' };

      const contents = bodyWrapper.querySelectorAll(':scope > p, :scope > h2');
      const contentParts = Array.from(contents).map(element => {
        const tagName = element.tagName.toLowerCase();
        const textContent = element.textContent.trim();
        if (tagName === 'h2') return '## ' + textContent;
        if (tagName === 'p') return textContent;
        return textContent;
      });
      const contentString = contentParts.join('\n\n');
      const h1 = articleWrapper.querySelector('h1');
      const title = h1 ? h1.textContent.trim() : (document.title || '').trim();
      return { ok: true, title, creationInfo, contentString };
    });

    if (!articleData.ok) {
      throw new Error('Article extraction failed: ' + (articleData.reason || 'unknown'));
    }

    let featuredImage = null;
    try {
      featuredImage = await page.evaluate(FIND_FEATURED_IMAGE_SNIPPET);
    } catch (e) { /* ignore */ }

    const mdParts = [];
    mdParts.push('### Editorial');
    mdParts.push(`# ${articleData.title || targetUrl}`);
    if (articleData.creationInfo) mdParts.push(`#### ${articleData.creationInfo}`);
    mdParts.push('---');
    if (featuredImage) mdParts.push(`![featured](${featuredImage})`);
    mdParts.push('');
    mdParts.push(articleData.contentString || '');

    const md = mdParts.filter(Boolean).join('\n\n');

    const filename = `${fmtDate} ${sanitizeFileName(articleData.title || "### No Title")}.md`;
    const outPath = path.join(OUT_DIR, filename);

    try {
      fs.writeFileSync(outPath, md, 'utf8');
      appendLog(`Inquirer saved: ${outPath}`);
      console.log('Saved:', outPath);
    } catch (err) {
      appendLog(`Failed to write article file: ${String(err)}`);
      throw err;
    }

    await browser.close();
    process.exit(0);
  } catch (err) {
    appendLog(`Inquirer fatal: ${String(err)}`);
    console.error(err && err.message ? err.message : err);
    try { await browser.close(); } catch (e) {}
    process.exit(2);
  }
}

run();
