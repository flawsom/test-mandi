/* Live verification of the portal navigation on deployed GitHub Pages. */
import { chromium } from 'playwright';
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const errors = [];
page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
page.on('pageerror', e => errors.push(String(e)));
await page.goto('https://flawsom.github.io/test-mandi/', { waitUntil: 'networkidle', timeout: 90000 });
await page.waitForTimeout(5000);
await page.evaluate(() => document.querySelector('.mandiq-nav').scrollIntoView({ block: 'center' }));
await page.waitForTimeout(1500);
const r = await page.evaluate(() => {
  const portals = [...document.querySelectorAll('.mandiq-portal')].map(a => ({
    type: a.getAttribute('data-type'), href: a.getAttribute('href'),
    canvasLit: (() => {
      const cv = a.querySelector('canvas'); const ctx = cv && cv.getContext('2d');
      if (!ctx) return -1;
      const d = ctx.getImageData(0, 0, cv.width, cv.height).data;
      let lit = 0; for (let i = 3; i < d.length; i += 4) if (d[i] > 30) lit++;
      return lit;
    })(),
  }));
  return {
    count: portals.length,
    portals,
    mermaidSvg: document.querySelectorAll('.mermaid-wrapper svg').length,
    kpi: document.querySelector('[data-countup="n_prices"]') ? document.querySelector('[data-countup="n_prices"]').textContent : null,
  };
});
console.log(JSON.stringify(r, null, 2));
console.log('console errors:', errors.length ? errors.slice(0,3) : 'none');
const pass = r.count === 4 && r.portals.every(p => p.canvasLit > 300) && r.mermaidSvg >= 1 && errors.length === 0;
console.log(pass ? '\nLIVE PORTALS CHECK PASS' : '\nLIVE PORTALS CHECK FAIL');
await browser.close();
process.exit(pass ? 0 : 1);
