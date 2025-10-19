#!/usr/bin/env node
/**
 * Test runner for article-scraper-repo selectors.
 *
 * Usage: node node/test/test.js
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
const path = require('path');

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
          mod = require(p);
          break;
        }
      }
      if (!mod) {
        // fallback: try package.json main
        const pj = path.join(sitePath, 'package.json');
        if (fs.existsSync(pj)) {
          const pkg = JSON.parse(fs.readFileSync(pj));
          if (pkg.main && fs.existsSync(path.join(sitePath, pkg.main))) {
            mod = require(path.join(sitePath, pkg.main));
          }
        }
      }
      if (!mod) {
        logger.error(`No module found for site folder "${siteFolder}", skipping.`);
        return { site: siteFolder, results: [], error: 'No module' };
      }

      // Prefer testSelectors(interface)
      if (typeof mod.testSelectors === 'function') {
        // pass a small logger API so modules can use it during tests
        const res = await mod.testSelectors(logger);
        return res;
      } else {
        // fallback: if module exports run() that returns scraped data, we can attempt to run it
        if (typeof mod.run === 'function') {
          logger.info('Calling run() for compatibility mode (no explicit testSelectors).');
          try {
            const data = await mod.run({ test: true });
            // Guess selectors tested: try to find keys like title, content
            // We'll create a single PASS result if data has main fields
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
          logger.error('Module does not export testSelectors or run; skipping.');
          return { site: siteFolder, results: [], error: 'No test entrypoints' };
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
