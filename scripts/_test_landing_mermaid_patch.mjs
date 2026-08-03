/* E2E test for the landing-page mermaid {{n_prices}} live badge.
 *
 * Stubs /health on the port landing expects from 127.0.0.1
 * (API_CONFIG.baseUrl -> http://127.0.0.1:18765), serves the repo root over
 * HTTP, intercepts the mermaid CDN <script> to serve a locally-downloaded
 * copy (deterministic, offline-friendly), loads the landing page, and asserts:
 *   1. mermaid loads (window.mermaid defined)
 *   2. The <pre class="mermaid"> renders into an <svg>
 *   3. No literal "{{n_prices}}" text remains in the SVG
 *   4. A foreignObject live badge appears with the formatted n_prices
 *   5. No unexpected console errors
 * Exits 0 on success, 1 on failure.
 */
import http from 'node:http';
import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { chromium } from 'playwright';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const API_PORT = 18765;
const SITE_PORT = 8123;
const MERMAID_CDN = 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js';
const MERMAID_LOCAL = path.join(ROOT, '.tmp_mermaid.min.js');
const HEALTH = {
  status: 'healthy',
  n_prices: 1335093,
  n_commodities: 304,
  n_districts: 614,
  n_ndvi: 3663,
  n_rainfall: 2278,
  n_rdd_results: 327,
};

const MIME = {
  '.html': 'text/html',
  '.js': 'text/javascript',
  '.css': 'text/css',
  '.svg': 'image/svg+xml',
  '.json': 'application/json',
  '.png': 'image/png',
  '.ico': 'image/x-icon',
};

// Ensure a local mermaid copy exists (download once)
if (!existsSync(MERMAID_LOCAL)) {
  console.log('downloading mermaid for offline test...');
  const resp = await fetch(MERMAID_CDN);
  if (!resp.ok) throw new Error(`mermaid download failed: HTTP ${resp.status}`);
  mkdirSync(path.dirname(MERMAID_LOCAL), { recursive: true });
  writeFileSync(MERMAID_LOCAL, Buffer.from(await resp.arrayBuffer()));
}
const MERMAID_JS = readFileSync(MERMAID_LOCAL, 'utf-8');

const api = http.createServer((req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  if (req.url.startsWith('/health')) {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(HEALTH));
  } else {
    res.writeHead(404); res.end('{}');
  }
});

const site = http.createServer((req, res) => {
  let p = decodeURIComponent(req.url.split('?')[0]);
  if (p === '/') p = '/landing/index.html';
  const file = path.join(ROOT, p);
  try {
    const data = readFileSync(file);
    res.writeHead(200, { 'Content-Type': MIME[path.extname(file)] || 'application/octet-stream' });
    res.end(data);
  } catch {
    res.writeHead(404); res.end('not found');
  }
});

const results = [];
function check(name, ok, detail) {
  results.push({ name, ok, detail });
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? ' — ' + detail : ''}`);
}

await new Promise((r) => api.listen(API_PORT, '127.0.0.1', r));
await new Promise((r) => site.listen(SITE_PORT, '127.0.0.1', r));

let browser;
try {
  browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: 'reduce' });
  // Serve mermaid from the local copy instead of the CDN
  await context.route('https://cdn.jsdelivr.net/**', (route) => {
    route.fulfill({ status: 200, contentType: 'text/javascript', body: MERMAID_JS });
  });
  const page = await context.newPage();
  const consoleAll = [];
  page.on('console', (m) => consoleAll.push(`${m.type()}: ${m.text()}`));
  page.on('pageerror', (e) => consoleAll.push(`pageerror: ${e.message}`));

  await page.goto(`http://127.0.0.1:${SITE_PORT}/`, { waitUntil: 'networkidle', timeout: 45000 });

  // Wait for mermaid to render the <pre class="mermaid"> into an SVG
  await page
    .waitForFunction(() => {
      const pre = document.querySelector('pre.mermaid');
      return pre && pre.querySelector('svg');
    }, { timeout: 20000 })
    .catch(() => {});
  await page.waitForTimeout(3000); // let /health fetch + deferred patch land

  const state = await page.evaluate(() => {
    const svg = document.querySelector('pre.mermaid svg');
    return {
      mermaidLoaded: typeof window.mermaid !== 'undefined',
      rendered: !!svg,
      hasPlaceholder: svg ? /{{\s*n_prices\s*}}/.test(svg.textContent || '') : null,
      badgeCount: svg ? svg.querySelectorAll('foreignObject').length : 0,
      hasLiveNumber: svg ? (svg.textContent || '').includes('1,335,093') : false,
      badgeText: svg
        ? Array.from(svg.querySelectorAll('foreignObject span')).map((s) => s.textContent.trim()).filter(Boolean).join(' ').slice(0, 40)
        : '',
      countup: (document.querySelector('[data-countup=n_prices]') || {}).textContent,
    };
  });

  check('mermaid script loaded', state.mermaidLoaded);
  check('mermaid rendered to SVG', state.rendered, state.mermaidLoaded ? '' : 'mermaid undefined');
  check('no literal {{n_prices}} in SVG', state.rendered && !state.hasPlaceholder);
  check('live foreignObject badge injected', state.rendered && state.badgeCount >= 1, `count=${state.badgeCount}`);
  check('badge shows live n_prices', state.rendered && state.hasLiveNumber, `badge="${state.badgeText}"`);
  check('KPI countup updated', state.countup === '1,335,093', `countup="${state.countup}"`);

  const errors = consoleAll.filter((e) => !/favicon|net::ERR|Failed to load resource|health-status.json|404/i.test(e));
  check('no unexpected console errors', errors.length === 0, errors.slice(0, 3).join(' | ') || 'clean');
} finally {
  if (browser) await browser.close();
  await new Promise((r) => api.close(r));
  await new Promise((r) => site.close(r));
}

const failed = results.filter((r) => !r.ok);
console.log(`\n${results.length - failed.length}/${results.length} checks passed`);
process.exit(failed.length ? 1 : 0);
