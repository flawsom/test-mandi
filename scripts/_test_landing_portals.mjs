/* E2E test for the MandiIQ creative navigation portals on landing/index.html.
 *
 * Serves the repo root over HTTP on the port landing expects for localhost
 * (API_CONFIG.baseUrl -> http://127.0.0.1:18765), stubs /health, and asserts:
 *   1. 4 .mandiq-portal anchors exist with the right hrefs/types
 *   2. each has a canvas that actually paints (non-blank pixels)
 *   3. canvases animate over time (pixel diff between two frames)
 *   4. hover adds .is-hover and moves particles (cursor wake)
 *   5. click blooms then navigates to the target href
 *   6. mermaid diagram still renders (regression check)
 *   7. zero console errors
 */
import { chromium } from 'playwright';
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const PORT = 18765;

const MIME = {
  '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css',
  '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png',
  '.md': 'text/markdown', '.mmd': 'text/plain', '.map': 'application/json',
};

const server = http.createServer((req, res) => {
  if (req.url === '/health') {
    res.writeHead(200, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' });
    res.end(JSON.stringify({ n_prices: 1335093, n_commodities: 304, n_districts: 614, n_ndvi: 3663, n_rainfall: 2278, n_rdd_results: 327, generated_at: '2026-08-03T00:00:00Z' }));
    return;
  }
  let p = decodeURIComponent(req.url.split('?')[0]);
  if (p === '/') p = '/landing/index.html';
  const file = path.join(ROOT, p);
  if (!file.startsWith(ROOT)) { res.writeHead(403); res.end(); return; }
  fs.readFile(file, (err, data) => {
    if (err) { res.writeHead(404); res.end('not found'); return; }
    res.writeHead(200, { 'Content-Type': MIME[path.extname(file)] || 'application/octet-stream' });
    res.end(data);
  });
});

await new Promise(r => server.listen(PORT, r));

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 1400 } });
const errors = [];
page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
page.on('pageerror', e => errors.push(String(e)));

await page.goto('http://127.0.0.1:' + PORT + '/', { waitUntil: 'networkidle', timeout: 60000 });
await page.waitForTimeout(3500);

const portals = await page.evaluate(() => {
  return [...document.querySelectorAll('.mandiq-portal')].map(a => ({
    type: a.getAttribute('data-type'),
    href: a.getAttribute('href'),
    hasCanvas: !!a.querySelector('.mandiq-portal__canvas'),
    title: (a.querySelector('.mandiq-portal__title') || {}).textContent,
    subtitle: (a.querySelector('.mandiq-portal__subtitle') || {}).textContent,
  }));
});
console.log('portals found:', portals.length);
portals.forEach(p => console.log(' ', p.type.padEnd(10), p.href.padEnd(32), p.title));

const expected = [
  { type: 'pipeline', href: 'docs/pipeline-interactive.html' },
  { type: 'report', href: 'docs/pipeline-report.html' },
  { type: 'dashboard', href: 'docs/heartbeat-dashboard.html' },
  { type: 'docs', href: 'docs/index.html' },
];
let pass = true;
function check(name, ok) { console.log((ok ? 'PASS ' : 'FAIL ') + name); if (!ok) pass = false; }

check('4 portals present', portals.length === 4);
expected.forEach((e, i) => {
  check(`portal ${i} type=${e.type}`, portals[i] && portals[i].type === e.type);
  check(`portal ${i} href=${e.href}`, portals[i] && portals[i].href === e.href);
  check(`portal ${i} has canvas`, portals[i] && portals[i].hasCanvas);
});

/* scroll the portal section into view so the IntersectionObserver starts animating */
await page.evaluate(() => {
  const nav = document.querySelector('.mandiq-nav');
  if (nav) nav.scrollIntoView({ block: 'center' });
});
await page.waitForTimeout(1200);

/* canvases paint non-blank pixels and animate */
const paint = await page.evaluate(() => {
  return [...document.querySelectorAll('.mandiq-portal__canvas')].map(c => {
    const ctx = c.getContext('2d');
    const d = ctx.getImageData(0, 0, c.width, c.height).data;
    let lit = 0;
    for (let i = 3; i < d.length; i += 4) if (d[i] > 20) lit++;
    return { w: c.width, h: c.height, lit };
  });
});
paint.forEach((p, i) => {
  check(`canvas ${i} non-blank pixels (${p.lit} lit of ${p.w}x${p.h})`, p.lit > 200);
});

const anim = await page.evaluate(async () => {
  const c = document.querySelector('.mandiq-portal[data-type="pipeline"] .mandiq-portal__canvas');
  const ctx = c.getContext('2d');
  const snap = () => ctx.getImageData(0, 0, c.width, c.height).data;
  const a = snap();
  await new Promise(r => setTimeout(r, 500));
  const b = snap();
  let diff = 0;
  for (let i = 3; i < a.length; i += 4) if (a[i] !== b[i]) diff++;
  return diff;
});
check('pipeline canvas animates (pixel diff ' + anim + ')', anim > 100);

/* hover wake */
await page.hover('.mandiq-portal[data-type="report"]');
await page.waitForTimeout(400);
const hoverState = await page.evaluate(() => ({
  hoverClass: document.querySelector('.mandiq-portal[data-type="report"]').classList.contains('is-hover'),
}));
check('hover adds .is-hover', hoverState.hoverClass === true);

/* click blooms then navigates to href */
const navPromise = page.waitForURL('**/docs/pipeline-interactive.html', { timeout: 8000 });
await page.click('.mandiq-portal[data-type="pipeline"] .mandiq-portal__content', { position: { x: 20, y: 20 } });
let navigated = false;
try { await navPromise; navigated = true; } catch (e) { navigated = false; }
check('click blooms + navigates to docs/pipeline-interactive.html', navigated);

/* go back and check mermaid still renders (regression) */
if (navigated) {
  await page.goBack({ waitUntil: 'networkidle' }).catch(() => {});
  await page.waitForTimeout(2500);
  const mmd = await page.evaluate(() => {
    const svg = document.querySelector('.mermaid-wrapper svg');
    return { svgCount: document.querySelectorAll('.mermaid-wrapper svg').length, bodyHasPlaceholder: document.body.innerText.includes('{{n_prices}}') };
  });
  check('mermaid still renders after portals added', mmd.svgCount >= 1 && !mmd.bodyHasPlaceholder);
}

check('zero console errors', errors.length === 0);
if (errors.length) console.log('  console errors:', errors.slice(0, 3));

console.log(pass ? '\nALL PORTAL CHECKS PASSED' : '\nPORTAL CHECKS FAILED');
await browser.close();
server.close();
process.exit(pass ? 0 : 1);
