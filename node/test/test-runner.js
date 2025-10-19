#!/usr/bin/env node
/**
 * Test runner for article-scraper-repo selectors.
 *
 * Usage: node node/test/test-runner.js
 *
 * This script will:
 * - run per-site tests
 * - print detailed logs including PASS/FAIL per selector
 * - always continue on errors (collect failures)
 * - write a TEST RESULTS summary block at the end
 *
 * Expected interface for each scraper module (node/{site}/index.js or similar):
 *  - export async function testSelectors(logger) { ... }
 *    - logger is an object with log(pass/fail/info,error)
 *    - testSelectors should return an object: { site: 'INQ', results: [ { selector, pass, foundCount, preview, error } ] }
 *
 * If your existing scrapers don't export testSelectors, this runner will attempt to call `run()` and infer selectors.
 */

const fs = require('fs');
const fse = require('fs-extra');
const path = require('path');

// puppeteer imports (used only by embedded scrapers)
let puppeteerExtra;
try {
  puppeteerExtra = require('puppeteer-extra');
} catch (e) {
  // not fatal here — the embedded scrapers will report an error if puppeteer isn't available
  puppeteerExtra = null;
}
let StealthPlugin, UserAgent;
try {
  StealthPlugin = require('puppeteer-extra-plugin-stealth');
  UserAgent = require('user-agents');
} catch (e) {
  StealthPlugin = null;
  UserAgent = null;
}

if (puppeteerExtra && StealthPlugin) puppeteerExtra.use(StealthPlugin());

const minimist = require('minimist');
const argv = minimist(process.argv.slice(2));

// Simple logger util
function makeLogger(site) {
  return {
    info: (...args) => console.log(`[${site}] INFO:`, ...args),
    pass: (msg) => console.log(`[${site}] PASS:`, msg),
    fail: (msg) => console.error(`[${site}] FAIL:`, msg),
    error: (err) => {
      if (err && err.stack) console.error(`[${site}] ERROR:`, err.stack);
      else console.error(`[${site}] ERROR:`, err);
    }
  };
}

// helper: 4-char base36 random
function randBase36(len = 4) {
  let s = '';
  for (let i = 0; i < len; i++) {
    s += Math.floor(Math.random() * 36).toString(36);
  }
  return s;
}

// ---------- Embedded scraper-test helpers for known sites ----------
const repoRoot = path.resolve(__dirname, '..'); // node/

function loadConfig() {
  const configPath = path.join(repoRoot, '..', 'config.json');
  try {
    if (!fs.existsSync(configPath)) return {};
    return JSON.parse(fs.readFileSync(configPath, 'utf8'));
  } catch (e) {
    return {};
  }
}

async function runInquirerTest(siteFolder, logger) {
  const config = loadConfig();
  const siteCfg = (config.sites && config.sites['inquirer']) || {};
  const urlArg = argv.url || argv.u || '';
  const discover = argv.discover || (!urlArg);

  if (!puppeteerExtra || !StealthPlugin) {
    return { site: siteFolder, results: [], error: 'puppeteer-extra and stealth plugin required' };
  }

  const puppeteer = puppeteerExtra;
  const UserAgentCtor = UserAgent;

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

  // find puppeteer executable path (same heuristic as your inquirer ref)
  const defaultChrome = path.join(repoRoot, '..', 'chrome', 'linux-121.0.6167.85', 'chrome-linux64', 'chrome');
  const executablePath = process.env.PUPPETEER_EXECUTABLE_PATH || (fs.existsSync(defaultChrome) ? defaultChrome : undefined);
  if (!executablePath) {
    return { site: siteFolder, results: [], error: `No puppeteer executablePath found. Set PUPPETEER_EXECUTABLE_PATH or commit chrome binary to ${defaultChrome}` };
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
    return { site: siteFolder, results: [], error: `Failed to launch browser: ${String(err)}` };
  }

  const page = await browser.newPage();
  await page.setUserAgent(new UserAgentCtor().toString());
  await page.setExtraHTTPHeaders({ 'accept-language': 'en-US,en;q=0.9' });

  try {
    let targetUrl = urlArg;
    if (discover) {
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
      if (found && found.ok) {
        targetUrl = found.articleUrl;
        logger.info(`Inquirer discovered: ${targetUrl}`);
      } else if (siteCfg.test_urls && siteCfg.test_urls.length) {
        targetUrl = siteCfg.test_urls[0];
        logger.info(`Inquirer discovery fallback to test_url: ${targetUrl}`);
      } else {
        await browser.close();
        return { site: siteFolder, results: [], error: `Inquirer discovery failed: ${found.reason || 'unknown'}` };
      }
    }

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
      const contentString = contentParts.join('\\n\\n');
      const h1 = articleWrapper.querySelector('h1');
      const title = h1 ? h1.textContent.trim() : (document.title || '').trim();
      return { ok: true, title, creationInfo, contentString, paragraphsCount: contentParts.length };
    });

    if (!articleData.ok) {
      await browser.close();
      return { site: siteFolder, results: [], error: 'Article extraction failed: ' + (articleData.reason || 'unknown') };
    }

    let featuredImage = null;
    try {
      featuredImage = await page.evaluate(FIND_FEATURED_IMAGE_SNIPPET);
    } catch (e) { /* ignore */ }

    const results = [];
    results.push({
      selector: 'article h1 (title)',
      pass: !!(articleData.title),
      foundCount: articleData.title ? 1 : 0,
      preview: articleData.title || ''
    });
    results.push({
      selector: 'article body paragraphs (inferred content)',
      pass: !!(articleData.paragraphsCount && articleData.paragraphsCount > 0),
      foundCount: articleData.paragraphsCount || 0,
      preview: String((articleData.contentString || '').slice(0, 120))
    });
    results.push({
      selector: 'featured image (comment snippet)',
      pass: !!featuredImage,
      foundCount: featuredImage ? 1 : 0,
      preview: featuredImage || ''
    });

    await browser.close();
    return { site: siteFolder, results };
  } catch (err) {
    try { await browser.close(); } catch (e) {}
    return { site: siteFolder, results: [], error: String(err) };
  }
}

async function runPhilstarTest(siteFolder, logger) {
  const config = loadConfig();
  const siteCfg = (config.sites && config.sites['philstar']) || {};
  const urlArg = argv.url || argv.u || '';
  const discover = argv.discover || (!urlArg);

  if (!puppeteerExtra || !StealthPlugin) {
    return { site: siteFolder, results: [], error: 'puppeteer-extra and stealth plugin required' };
  }

  const puppeteer = puppeteerExtra;
  const UserAgentCtor = UserAgent;

  const defaultChrome = path.join(repoRoot, '..', 'chrome', 'linux-121.0.6167.85', 'chrome-linux64', 'chrome');
  const executablePath = process.env.PUPPETEER_EXECUTABLE_PATH || (fs.existsSync(defaultChrome) ? defaultChrome : undefined);
  if (!executablePath) {
    return { site: siteFolder, results: [], error: `No puppeteer executablePath found. Set PUPPETEER_EXECUTABLE_PATH or commit chrome binary to ${defaultChrome}` };
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
    return { site: siteFolder, results: [], error: `Failed to launch browser: ${String(err)}` };
  }

  const page = await browser.newPage();
  await page.setUserAgent(new UserAgentCtor().toString());
  await page.setExtraHTTPHeaders({ 'accept-language': 'en-US,en;q=0.9' });

  try {
    let targetUrl = urlArg;

    if (discover) {
      const indexUrl = siteCfg.index_url || 'https://www.philstar.com/opinion';
      await page.goto(indexUrl, { waitUntil: 'networkidle2', timeout: config.puppeteer?.defaultTimeout || 60000 });
      try {
        const hrefs = await page.$$eval(siteCfg.link_selector || '.article__teaser a', (els, attr) =>
          els.map(e => e.getAttribute(attr) || e.href || '').filter(Boolean),
          siteCfg.link_attr || 'href'
        );
        const unique = Array.from(new Set(hrefs)).slice(0, siteCfg.link_limit || 5);
        if (unique.length) {
          const abs = unique.map(h => {
            try { return new URL(h, indexUrl).toString(); } catch (e) { return h; }
          });
          targetUrl = abs[0];
        } else if (siteCfg.test_urls && siteCfg.test_urls.length) {
          targetUrl = siteCfg.test_urls[0];
        } else {
          await browser.close();
          return { site: siteFolder, results: [], error: 'Philstar discovery returned no links and no fallback test_urls' };
        }
      } catch (e) {
        if (siteCfg.test_urls && siteCfg.test_urls.length) {
          targetUrl = siteCfg.test_urls[0];
        } else {
          await browser.close();
          return { site: siteFolder, results: [], error: `Philstar discovery failed: ${String(e)}` };
        }
      }
    }

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

      return { title, author, date, feature, paragraphs, paragraphsCount: paragraphs.length };
    }, siteCfg.content, siteCfg.feature_image_selector);

    if (!data || !data.paragraphs || data.paragraphs.length === 0) {
      await browser.close();
      return { site: siteFolder, results: [], error: 'Philstar: no paragraphs extracted' };
    }

    const results = [];
    results.push({
      selector: 'h1.article__title (title)',
      pass: !!(data.title),
      foundCount: data.title ? 1 : 0,
      preview: data.title || ''
    });
    results.push({
      selector: siteCfg.content || 'article content (paragraphs)',
      pass: !!(data.paragraphsCount && data.paragraphsCount > 0),
      foundCount: data.paragraphsCount || 0,
      preview: String((data.paragraphs && data.paragraphs[0]) || '').slice(0, 120)
    });
    results.push({
      selector: 'feature image',
      pass: !!data.feature,
      foundCount: data.feature ? 1 : 0,
      preview: data.feature || ''
    });

    await browser.close();
    return { site: siteFolder, results };
  } catch (err) {
    try { await browser.close(); } catch (e) {}
    return { site: siteFolder, results: [], error: String(err) };
  }
}

// ---------- End embedded scraper helpers ----------

(async () => {
  const RESULTS = {}; // per-site results
  const sitesDir = path.join(__dirname, '..'); // node/
  const now = new Date();
  const dateStr = now.toISOString().slice(0,10); // 2025-10-19
  const uid = randBase36(4);
  // Example: INQ 2025-10-19_xdf3
  // We'll let each site module provide its 'site' short name.
  const headerFirstLine = `Test Run: ${dateStr}_${uid}`;
  console.log(headerFirstLine);
  console.log('');

  // Discover site folders under node/ (exclude node_modules and test)
  const candidates = fs.readdirSync(sitesDir, { withFileTypes: true })
    .filter(d => d.isDirectory() && !['node_modules','test'].includes(d.name))
    .map(d => d.name);

  // Helper: run one site
  async function runSite(siteFolder) {
    const sitePath = path.join(sitesDir, siteFolder);
    const logger = makeLogger(siteFolder);
    try {
      // try to require site module index.js or main file
      let mod = null;
      const possible = [
        path.join(sitePath, 'index.js'),
        path.join(sitePath, 'main.js'),
        path.join(sitePath, `${siteFolder}.js`)
      ];
      for (const p of possible) {
        if (fs.existsSync(p)) {
          try { mod = require(p); break; } catch (e) {
            logger.error(`Failed requiring ${p}: ${String(e)}`);
          }
        }
      }
      if (!mod) {
        // fallback: try package.json main
        const pj = path.join(sitePath, 'package.json');
        if (fs.existsSync(pj)) {
          try {
            const pkg = JSON.parse(fs.readFileSync(pj));
            if (pkg.main && fs.existsSync(path.join(sitePath, pkg.main))) {
              try { mod = require(path.join(sitePath, pkg.main)); } catch (e) {
                logger.error(`Failed requiring package main for ${siteFolder}: ${String(e)}`);
              }
            }
          } catch (e) {
            logger.error(`Failed reading package.json for ${siteFolder}: ${String(e)}`);
          }
        }
      }

      if (mod && typeof mod.testSelectors === 'function') {
        // module provides testSelectors
        const res = await mod.testSelectors(logger);
        return res;
      } else if (mod && typeof mod.run === 'function') {
        logger.info('Calling run() for compatibility mode (no explicit testSelectors).');
        try {
          const data = await mod.run({ test: true });
          const results = [];
          if (data && (data.title || data.content || data.body)) {
            results.push({
              selector: 'inferred:main',
              pass: true,
              foundCount: 1,
              preview: (data.title || data.content || data.body || '').toString().slice(0,75)
            });
          } else {
            results.push({
              selector: 'inferred:main',
              pass: false,
              foundCount: 0,
              preview: '',
              error: 'No main fields returned'
            });
          }
          return { site: siteFolder, results };
        } catch (err) {
          logger.error(err);
          return { site: siteFolder, results: [], error: err.stack || String(err) };
        }
      } else {
        // No module present. For some known site folders we have embedded logic:
        if (siteFolder.toLowerCase() === 'inquirer') {
          logger.info('Running embedded Inquirer scraper-test (no module found).');
          return await runInquirerTest(siteFolder, logger);
        } else if (siteFolder.toLowerCase() === 'philstar' || siteFolder.toLowerCase() === 'phils') {
          logger.info('Running embedded Philstar scraper-test (no module found).');
          return await runPhilstarTest(siteFolder, logger);
        } else {
          logger.error(`No module found for site folder "${siteFolder}", skipping.`);
          return { site: siteFolder, results: [], error: 'No module' };
        }
      }
    } catch (err) {
      logger.error(err);
      return { site: siteFolder, results: [], error: err.stack || String(err) };
    }
  }

  // Iterate sites and collect results
  for (const s of candidates) {
    // optional: only test specific sites? you can add filter logic here
    try {
      process.stdout.write(`---\nTesting site: ${s}\n`);
      const outcome = await runSite(s);
      RESULTS[s] = outcome;
      // Print detailed per-selector logs in the format you requested
      if (outcome && Array.isArray(outcome.results)) {
        for (const r of outcome.results) {
          if (r.pass) {
            console.log(`querySelector \`${r.selector}\`: PASS`);
            console.log(`found count: ${r.foundCount || 0}`);
            console.log(`idx0 content: ${String(r.preview || '').slice(0,75)}`);
            console.log('');
          } else {
            console.log(`querySelector \`${r.selector}\`: FAIL`);
            if (r.error) {
              console.log('Traceback:');
              console.log(`   ${String(r.error).replace(/\n/g, '\n   ')}`);
            } else {
              console.log('Traceback: <no stack available>');
            }
            console.log('');
          }
        }
      } else if (outcome && outcome.error) {
        console.log(`Site-level ERROR for ${s}:`);
        console.log(outcome.error);
      } else {
        console.log(`No selector results for ${s}`);
      }
    } catch (err) {
      console.error(`Unhandled exception while testing ${s}:`, err.stack || err);
    }
  }

  // Build summary block
  console.log('---\n');
  console.log('=========================================');
  console.log('TEST RESULTS');
  console.log('=========================================');

  // Example grouping: sites like INQ and PHS (you can define aliases)
  // We'll simply compute pass/fail counts per site
  for (const [site, out] of Object.entries(RESULTS)) {
    let pass = 0, fail = 0;
    if (out && Array.isArray(out.results)) {
      for (const r of out.results) {
        if (r.pass) pass++;
        else fail++;
      }
    } else if (out && out.error) {
      fail = 1;
    }
    console.log(`${site}:`);
    console.log(`  ${pass} PASS, ${fail} FAIL`);
  }

  // Also print a tiny totals summary
  let totalPass = 0, totalFail = 0;
  for (const out of Object.values(RESULTS)) {
    if (out && Array.isArray(out.results)) {
      for (const r of out.results) {
        if (r.pass) totalPass++;
        else totalFail++;
      }
    } else if (out && out.error) {
      totalFail++;
    }
  }
  console.log('\n---\n');
  console.log(`Totals: ${totalPass} PASS, ${totalFail} FAIL`);
  console.log('\n');

  // Also write full run log to a file in repo root logs/ with a stable name (so workflow can commit it)
  try {
    const logDir = path.resolve(path.join(__dirname, '..', 'logs'));
    if (!fs.existsSync(logDir)) fs.mkdirSync(logDir, { recursive: true });
    const ts = new Date().toISOString().replace(/[:.]/g, '-');
    const filename = `test-run-${ts}.log`;
    const filepath = path.join(logDir, filename);

    // capture everything printed to console (simple approach: reconstruct from RESULTS and write)
    let fullLog = `${headerFirstLine}\n\n`;
    for (const [site, out] of Object.entries(RESULTS)) {
      fullLog += `---\nTesting site: ${site}\n`;
      if (out && Array.isArray(out.results)) {
        for (const r of out.results) {
          if (r.pass) {
            fullLog += `querySelector \`${r.selector}\`: PASS\n`;
            fullLog += `found count: ${r.foundCount || 0}\n`;
            fullLog += `idx0 content: ${String(r.preview || '').slice(0,75)}\n\n`;
          } else {
            fullLog += `querySelector \`${r.selector}\`: FAIL\n`;
            if (r.error) {
              fullLog += 'Traceback:\n';
              fullLog += `   ${String(r.error).replace(/\n/g, '\n   ')}\n\n`;
            } else {
              fullLog += 'Traceback: <no stack available>\n\n';
            }
          }
        }
      } else if (out && out.error) {
        fullLog += `Site-level ERROR:\n${out.error}\n\n`;
      } else {
        fullLog += `No results produced.\n\n`;
      }
    }

    // Append summary block
    fullLog += '\n---\n\n';
    fullLog += '=========================================\n';
    fullLog += 'TEST RESULTS\n';
    fullLog += '=========================================\n';
    for (const [site, out] of Object.entries(RESULTS)) {
      let pass = 0, fail = 0;
      if (out && Array.isArray(out.results)) {
        for (const r of out.results) {
          if (r.pass) pass++;
          else fail++;
        }
      } else if (out && out.error) {
        fail = 1;
      }
      fullLog += `${site}:\n  ${pass} PASS, ${fail} FAIL\n`;
    }
    fullLog += '\n---\n';
    fs.writeFileSync(filepath, fullLog, 'utf8');
    console.log(`Wrote full log to ${filepath}`);
    // Also print path so workflow step can grab it
    console.log(`LOGFILE:${filepath}`);
  } catch (err) {
    console.error('Failed to write log file:', err.stack || err);
  }

  // Exit with code 0 so workflow continues; if you prefer nonzero on failures:
  // process.exit(totalFail > 0 ? 1 : 0);
  process.exit(0);
})();
