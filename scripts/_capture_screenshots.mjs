/* Capture live screenshots of the three README gallery surfaces. */
import { chromium } from 'playwright';

const SHOTS = [
  {
    name: 'landing-live',
    url: 'https://flawsom.github.io/test-mandi/',
    waitFor: async (page) => {
      await page.waitForSelector('[data-countup=n_prices]', { timeout: 20000 }).catch(() => {});
      await page.waitForTimeout(2500); // let KPIs + canvases settle
    },
  },
  {
    name: 'dashboard-live',
    url: 'https://flawsom.github.io/test-mandi/docs/',
    waitFor: async (page) => {
      await page.waitForSelector('[data-countup=n_prices]', { timeout: 20000 }).catch(() => {});
      await page.waitForTimeout(2500);
    },
  },
  {
    name: 'api-docs-live',
    url: 'https://p01--mandiiq--zbvjrztgjqgw.code.run/docs',
    waitFor: async (page) => {
      await page.waitForSelector('#swagger-ui, .swagger-ui', { timeout: 25000 }).catch(() => {});
      await page.waitForTimeout(3000);
    },
  },
];

(async () => {
  const browser = await chromium.launch({ headless: true });
  for (const shot of SHOTS) {
    const context = await browser.newContext({
      viewport: { width: 1440, height: 900 },
      deviceScaleFactor: 1,
    });
    const page = await context.newPage();
    try {
      await page.goto(shot.url, { waitUntil: 'networkidle', timeout: 45000 });
      await shot.waitFor(page);
      await page.screenshot({
        path: `.browser_shots/${shot.name}.png`,
        fullPage: true,
      });
      console.log(`OK ${shot.name} <- ${shot.url}`);
    } catch (e) {
      console.log(`ERR ${shot.name}: ${e.message.split('\n')[0]}`);
    }
    await context.close();
  }
  await browser.close();
})();
