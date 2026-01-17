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
    .replace(/[\u201C\u201D\u201E\u2033]/g, '-') // Double quotes
    .replace(/[\u2018\u2019\u2032]/g, " ") // Single quotes/Apostrophes
    .slice(0,200)
    .trim();
}

async function md2docx(markdownFilePath, outputFilePath) {
  try {
    // 1. Read markdown content
    // fs-extra's readFile is promisified and works with await
    const markdown = await fs.readFile(markdownFilePath, 'utf-8');

    // 2. Convert to docx document object
    const doc = await markdownDocx(markdown);

    // 3. Serialize to a buffer
    const buffer = await Packer.toBuffer(doc);

    // 4. Save to file
    // fs-extra's writeFile is also promisified and works with await
    await fs.writeFile(outputFilePath, buffer);

    console.log(`Conversion completed successfully! Output saved to ${outputFilePath}`);
  } catch (error) {
    appendLog('Error during conversion:', error);
    console.error('Error during conversion:', error);
  }
}

// Default navigation timeout: 45 seconds unless overridden in config.puppeteer.defaultTimeout
const NAV_TIMEOUT = config.puppeteer?.defaultTimeout ?? 45000;

async function discoverLinks(page) {
  const indexUrl = siteCfg.index_url || 'https://www.philstar.com/opinion';
  await page.goto(indexUrl, { waitUntil: 'domcontentloaded', timeout: NAV_TIMEOUT });
  
  try {
    const links = await page.$$eval(
      siteCfg.items_selector || '.carousel__item', 
      (els, cfg) => {
        const recentRegex = /second|minute|hour/i;

        return els
          .filter(e => {
            // FIX: Use the key name passed in the third argument (pub_time)
            const timeEl = e.querySelector(cfg.pub_time); 
            const timeStr = timeEl ? timeEl.innerText.toLowerCase() : '';
            return recentRegex.test(timeStr);
          })
          .map(e => {
            // FIX: Robust link extraction
            const attr = e.getAttribute(cfg.link_attr || 'href');
            return attr || e.href || '';
          })
          .filter(link => link.trim().length > 0);
      },
      // Ensure these keys match the usage inside the function above
      { link_attr: siteCfg.link_attr, pub_time: siteCfg.pub_time || '.article__date' }
    );

    const unique = Array.from(new Set(links)).slice(0, siteCfg.link_limit || 1);
    
    const abs = unique.map(h => {
      try { return new URL(h, indexUrl).toString(); } catch (e) { return h; }
    });
    
    console.log(`[DEBUG] list output: ${JSON.stringify(abs)}`);
    return abs;
  } catch (e) {
    appendLog('Philstar discovery failed: ' + String(e));
    return [];
  }
}

/**
 * Try to fetch the raw HTML using the page context's fetch (works in most environments).
 * If successful, set the page content so the rest of the extraction can run unchanged.
 */
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

    if (!raw || !raw.ok) {
      appendLog('Raw fetch returned error: ' + (raw && raw.err ? raw.err : 'unknown'));
      return false;
    }

    // Use setContent so subsequent DOM queries work the same way as after page.goto
    await page.setContent(raw.text, { waitUntil: 'domcontentloaded' });
    appendLog('Raw fetch and setContent succeeded');
    return true;
  } catch (e) {
    appendLog('Raw fetch failed: ' + String(e));
    return false;
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
  const ua = new UserAgent().toString();
  await page.setUserAgent(ua);
  await page.setExtraHTTPHeaders({ 'accept-language': 'en-US,en;q=0.9' });

  try {
    let targetUrl = urlArg;

    if (discover) {
      appendLog('Philstar: discovery mode');
      const links = await discoverLinks(page);
      if (!links || !links.length) {
        appendLog('Philstar discovery returned no links. Skipping...');
        throw new Error('No philstar links discovered. Either selector are incorrect or no article is uploaded yet.');
      
        /*
        if (siteCfg.test_urls && siteCfg.test_urls.length) {
          targetUrl = siteCfg.test_urls[0];
        } else {
          throw new Error('No philstar links discovered and no fallback test_urls');
        }
        */
      } else {
        targetUrl = links[0];
        appendLog('Philstar discovered: ' + targetUrl);
      }
    }

    appendLog('Philstar loading article: ' + targetUrl);

    let navigated = false;
    try {
      await page.goto(targetUrl, { waitUntil: 'networkidle2', timeout: NAV_TIMEOUT });
      navigated = true;
    } catch (err) {
      // If navigation timed out, try raw fetch fallback; otherwise rethrow
      const msg = String(err && err.message ? err.message : err);
      appendLog('Page.goto failed: ' + msg);
      if (msg.includes('Timeout') || (err && err.name === 'TimeoutError')) {
        appendLog('Navigation timed out after ' + NAV_TIMEOUT + 'ms; trying raw fetch fallback');
        const ok = await tryRawFetchAndSet(page, targetUrl, ua);
        if (!ok) throw new Error('Navigation timeout and raw fetch fallback failed');
      } else {
        throw err;
      }
    }

    // Extraction runs the same whether we navigated or used setContent from fallback
    const data = await page.evaluate((contentSelector, featureSelector) => {
      const url = window.location.toString();
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

      return { url, title, author, date, feature, paragraphs };
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
      data.url ? `[${data.url}](${data.url})` : '',
      '---',
      '',
      data.paragraphs.join('\n\n')
    ].filter(Boolean).join('\n\n');

    const filename = `${fmtDate} ${sanitizeFileName(data.title || "### No Title")}`;
    const outPath = path.join(OUT_DIR, `${filename}.md`);
    const docxOut = path.join(D_OUT_DIR, `${filename}.docx`);

    try {
      fs.writeFileSync(outPath, md, 'utf8');
      appendLog('Philstar saved: ' + outPath);
      console.log('Saved:', outPath);

      try {
        md2docx(outPath, docxOut);
        appendLog(`Philstar saved: ${outPath}`);
        console.log('Saved:', outPath);
      } catch (e) {
        appendLog(`[WARNING] Failed docx creation: ${String(e)}`);
        // warn only, dont throw
      }
      
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
