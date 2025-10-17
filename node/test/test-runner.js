// node/test/test-runner.js
const fs = require('fs-extra');
const path = require('path');
const { spawnSync } = require('child_process');
const minimist = require('minimist');

const argv = minimist(process.argv.slice(2));
const siteArg = argv.site || '';

const repoRoot = path.resolve(__dirname, '..', '..');
const sitesToTest = siteArg ? [siteArg] : ['inquirer', 'philstar'];
const results = [];

function runNodeScript(scriptPath, args = []) {
  const node = process.execPath;
  const full = path.join(repoRoot, scriptPath);
  const res = spawnSync(node, [full, ...args], { stdio: 'inherit', env: process.env, timeout: 120000 });
  return { status: res.status, error: res.error };
}

(async () => {
  fs.ensureDirSync(path.join(repoRoot, 'test-results'));
  for (const site of sitesToTest) {
    try {
      console.log('Testing site:', site);
      let script = '';
      if (site === 'inquirer') script = 'node/inquirer/scrape-inquirer.js';
      else if (site === 'philstar') script = 'node/philstar/scrape-philstar.js';
      else {
        results.push({ site, ok: false, reason: 'unknown site' });
        continue;
      }
      // run in discover mode (default)
      const r = runNodeScript(script, ['--discover']);
      // check for generated files
      const outDir = path.join(repoRoot, 'articles', site);
      let ok = false;
      if (fs.existsSync(outDir)) {
        const files = fs.readdirSync(outDir).filter(f => f.endsWith('.md'));
        ok = files.length > 0;
      }
      results.push({ site, scriptExit: r.status, ok });
    } catch (e) {
      results.push({ site, ok: false, error: String(e) });
    }
  }

  const outPath = path.join(repoRoot, 'test-results', `test-run-${Date.now()}.json`);
  fs.writeFileSync(outPath, JSON.stringify({ runAt: new Date().toISOString(), results }, null, 2), 'utf8');
  console.log('Test results written to', outPath);
  // fail if any site failed
  const anyFail = results.some(r => !r.ok);
  process.exit(anyFail ? 2 : 0);
})();