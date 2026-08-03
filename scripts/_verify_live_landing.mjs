/* Live verification of the landing-page mermaid fix on GitHub Pages. */
import { chromium } from 'playwright';

(async () => {
  const url = 'https://flawsom.github.io/test-mandi/';
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const errors = [];
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  page.on('pageerror', e => errors.push(String(e)));

  await page.goto(url, { waitUntil: 'networkidle', timeout: 60000 });
  // Let mermaid.run() + fetch settle
  await page.waitForTimeout(6000);

  const result = await page.evaluate(() => {
    const wrapper = document.querySelector('.mermaid-wrapper');
    const pre = document.querySelector('pre.mermaid');
    const svg = wrapper ? wrapper.querySelector('svg') : null;
    const bodyText = document.body.innerText;
    return {
      hasWrapper: !!wrapper,
      preProcessed: pre ? pre.getAttribute('data-processed') : null,
      svgCount: wrapper ? wrapper.querySelectorAll('svg').length : 0,
      svgBytes: svg ? svg.outerHTML.length : 0,
      rawPlaceholderInBody: bodyText.includes('{{n_prices}}'),
      badgeInSvg: svg ? svg.outerHTML.includes('1,3') : false,   // locale-formatted count
      foreignObjects: svg ? svg.querySelectorAll('foreignObject').length : 0,
      kpiFirst: document.querySelector('[data-countup="n_prices"]') ?
        document.querySelector('[data-countup="n_prices"]').textContent : null,
      pageTitle: document.title,
    };
  });

  console.log('URL            :', url);
  console.log('hasWrapper     :', result.hasWrapper);
  console.log('pre processed  :', result.preProcessed, '(cleared => null expected)');
  console.log('svgCount       :', result.svgCount);
  console.log('svgBytes       :', result.svgBytes);
  console.log('raw {{n_prices}} in body :', result.rawPlaceholderInBody);
  console.log('live badge in SVG        :', result.badgeInSvg);
  console.log('foreignObjects in SVG    :', result.foreignObjects);
  console.log('KPI n_prices             :', result.kpiFirst);
  console.log('console errors           :', errors.length ? errors.slice(0, 3) : 'none');

  const pass =
    result.svgCount >= 1 &&
    result.svgBytes > 5000 &&
    !result.rawPlaceholderInBody &&
    (result.badgeInSvg || result.foreignObjects >= 1) &&
    errors.length === 0;
  console.log(pass ? '\nLIVE CHECK PASS' : '\nLIVE CHECK FAIL');
  await browser.close();
  process.exit(pass ? 0 : 1);
})();
