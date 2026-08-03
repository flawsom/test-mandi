/* Verify bloom visibly bursts on ALL portal types (review bug #2 fix).
 * A radial burst is symmetric, so the particle CENTROID stays put — the
 * correct signal is SPREAD: mean distance of lit pixels from canvas center.
 * Loads a fresh page per type to avoid navigation-roundtrip flakiness.
 */
import { chromium } from 'playwright';
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const PORT = 18767;
const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png', '.md': 'text/markdown' };
const server = http.createServer((req, res) => {
  if (req.url === '/health') {
    res.writeHead(200, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' });
    res.end(JSON.stringify({ n_prices: 1335093, n_commodities: 304, n_districts: 614, n_ndvi: 3663, n_rainfall: 2278, n_rdd_results: 327 }));
    return;
  }
  let p = decodeURIComponent(req.url.split('?')[0]);
  if (p === '/') p = '/landing/index.html';
  const f = path.join(ROOT, p);
  fs.readFile(f, (e, d) => { if (e) { res.writeHead(404); res.end(); return; } res.writeHead(200, { 'Content-Type': MIME[path.extname(f)] || 'application/octet-stream' }); res.end(d); });
});
await new Promise(r => server.listen(PORT, r));

const browser = await chromium.launch();
let allOk = true;

async function snap(page, type) {
  return page.evaluate((t) => {
    const cv = document.querySelector('.mandiq-portal[data-type="' + t + '"] .mandiq-portal__canvas');
    const ctx = cv.getContext('2d');
    const d = ctx.getImageData(0, 0, cv.width, cv.height).data;
    const ccx = cv.width / 2, ccy = cv.height / 2;
    let lit = 0, spread = 0, n = 0;
    for (let i = 3; i < d.length; i += 4) {
      if (d[i] > 30) {
        lit++;
        const px = (i / 4) % cv.width, py = Math.floor((i / 4) / cv.width);
        spread += Math.sqrt((px - ccx) * (px - ccx) + (py - ccy) * (py - ccy));
        n++;
      }
    }
    return { lit, spread: n ? spread / n : 0 };
  }, type);
}

for (const t of ['pipeline', 'dashboard']) {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await page.goto('http://127.0.0.1:' + PORT + '/', { waitUntil: 'networkidle', timeout: 60000 });
  await page.waitForTimeout(3000);
  await page.evaluate(() => document.querySelector('.mandiq-nav').scrollIntoView({ block: 'center' }));
  await page.waitForTimeout(1200);

  const before = await snap(page, t);
  const box = await page.locator('.mandiq-portal[data-type="' + t + '"]').boundingBox();
  // Block the 320ms navigation so we stay on-page to observe the burst
  await page.evaluate(() => {
    try {
      Object.defineProperty(window, 'location', {
        configurable: true,
        get: () => document.location,
        set: (v) => { window.__navBlocked = String(v); },
      });
    } catch (e) { /* location non-configurable — click may navigate; snapshot still lands first */ }
  });
  await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
  await page.waitForTimeout(120); // mid-bloom, well before the 320ms navigation
  const mid = await snap(page, t);

  const spreadGain = mid.spread - before.spread;
  const burst = mid.lit > before.lit * 1.2;
  const ok = spreadGain > 4 || burst;
  console.log(t + ': before spread=' + before.spread.toFixed(1) + ' lit=' + before.lit +
    ' | mid-bloom spread=' + mid.spread.toFixed(1) + ' lit=' + mid.lit +
    ' | spread +' + spreadGain.toFixed(1) + 'px | lit burst=' + burst + ' => ' + (ok ? 'PASS' : 'FAIL'));
  if (!ok) allOk = false;
  await page.close();
}

console.log(allOk ? 'BLOOM VISIBILITY PASS (all types burst visibly)' : 'BLOOM VISIBILITY FAIL');
await browser.close();
server.close();
process.exit(allOk ? 0 : 1);
