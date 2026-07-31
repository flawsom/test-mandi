/* Capture live screenshots of the three README gallery surfaces.
 *
 * Deterministic for CI (refresh-screenshots.yml): each context is created
 * with reducedMotion:'reduce' so the flowing-dots / cursor-trail canvases
 * never start AND the CSS background animations (atmosphere drift, hero
 * frame draw, live-dot pulse, page loader) are disabled via the page's
 * own prefers-reduced-motion media rules — pixel output is then stable
 * between runs, so a git diff on screenshots/ only fires on REAL content
 * changes (KPI counts, layout, API spec), never on animation phase.
 *
 * Live timestamp meta-elements (kpi-freshness, surface-status-ts) are
 * removed before capture so their per-minute text drift can't churn the
 * auto-commit either.
 *
 * Exits non-zero if any surface fails (after 2 retries), so the workflow
 * never commits stale/partial captures.
 */
import { chromium } from 'playwright';

const SHOTS = [
  {
    name: 'landing-live',
    url: 'https://flawsom.github.io/test-mandi/',
    waitFor: async (page) => {
      await page.waitForSelector('[data-countup=n_prices]', { timeout: 20000 }).catch(() => {});
      await page.waitForTimeout(2500); // let KPIs settle
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
      // #swagger-ui exists as soon as the container mounts (even while the
      // loading spinner is up) — wait for actual rendered content instead.
      await page.waitForSelector('.swagger-ui .opblock, .swagger-ui .info', { timeout: 30000 }).catch(() => {});
      await page.waitForTimeout(3000);
    },
  },
];

async function stabilizeForScreenshot(page) {
  // Hide live "last updated" meta text so its per-minute drift never
  // churns the CI auto-commit. Real content changes still show up.
  await page.evaluate(() => {
    for (const id of ['kpi-freshness', 'surface-status-ts']) {
      const el = document.getElementById(id);
      if (el) el.remove();
    }
  });
  // Wait for webfonts to settle so text metrics are identical across runs
  // (a font loading late — or falling back — would otherwise create a
  // spurious pixel diff and an unwanted daily commit).
  await page.evaluate(() => document.fonts.ready).catch(() => {});
}

async function captureOne(browser, shot) {
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 1,
    reducedMotion: 'reduce', // freeze animated canvases + CSS motion -> deterministic pixels
  });
  const page = await context.newPage();
  let lastErr = null;
  for (let attempt = 1; attempt <= 2; attempt++) {
    try {
      await page.goto(shot.url, { waitUntil: 'networkidle', timeout: 45000 });
      await shot.waitFor(page);
      await stabilizeForScreenshot(page);
      await page.screenshot({
        path: `.browser_shots/${shot.name}.png`,
        fullPage: true,
      });
      console.log(`OK ${shot.name} <- ${shot.url}`);
      await context.close();
      return true;
    } catch (e) {
      lastErr = e;
      console.log(`retry ${attempt}/2 ${shot.name}: ${e.message.split('\n')[0]}`);
    }
  }
  console.log(`ERR ${shot.name}: ${(lastErr && lastErr.message ? lastErr.message.split('\n')[0] : 'unknown')}`);
  await context.close();
  return false;
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const results = [];
  for (const shot of SHOTS) results.push(await captureOne(browser, shot));
  await browser.close();
  if (results.some((r) => !r)) {
    console.error('One or more screenshots failed — refusing to emit partial captures for CI.');
    process.exit(1);
  }
})();
