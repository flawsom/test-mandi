/* Capture live screenshots of the three README gallery surfaces.
 *
 * Deterministic for CI (refresh-screenshots.yml): pixel output must be
 * byte-identical between runs so a git diff on screenshots/ only fires on
 * REAL content changes (KPI counts, layout, API spec), never on
 * animation phase. Determinism is guaranteed in three layers:
 *
 *   1. reducedMotion:'reduce' on every context — the flowing-dots /
 *      cursor-trail canvases never start on pages that respect the media
 *      query, and the landing page's own reduced-motion CSS block
 *      disables its atmosphere drifters / hero frame draw / live-dot.
 *   2. stabilizeForScreenshot() freezes EVERY CSS/WAAPI animation at a
 *      deterministic end state (finite -> finish(), infinite -> cancel()
 *      back to base style). This covers pages that ship NO
 *      prefers-reduced-motion rules (docs/index.html has none — its
 *      infinite .atmosphere-* / .groovy-* / mermaid-pulse animations were
 *      churning the auto-commit by ~231 bytes per run).
 *   3. The page is scrolled through a real viewport first so every
 *      IntersectionObserver .reveal settles into its final visible state
 *      (docs unobserves elements after revealing, so this is idempotent),
 *      and live timestamp meta-elements (kpi-freshness,
 *      surface-status-ts) are removed so per-minute text drift can't
 *      churn the commit. document.fonts.ready is awaited so webfont
 *      metrics are identical across runs.
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
      // Mermaid replaces the <pre class="mermaid"> with an SVG asynchronously —
      // never capture the loading spinner state.
      await page
        .waitForFunction(() => {
          const loading = document.querySelectorAll('.mermaid-wrapper.loading').length;
          const svg = document.querySelector('.mermaid-wrapper svg') || document.querySelector('svg.mermaid');
          return loading === 0 && !!svg;
        }, { timeout: 30000 })
        .catch(() => {});
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
  // Scroll the full page through a real viewport so every
  // IntersectionObserver reveal fires and settles BEFORE the capture.
  // Below-the-fold .reveal sections start at opacity 0; if we only relied
  // on Playwright's fullPage viewport expansion, their 0.8s reveal
  // transition would still be running — or not started — at capture time,
  // which varies run-to-run. Both Pages surfaces unobserve elements once
  // revealed, so scrolling back to top leaves everything in its final
  // visible state (idempotent).
  await page.evaluate(async () => {
    const h = Math.max(document.body.scrollHeight, document.documentElement.scrollHeight);
    for (let y = 0; y < h; y += 700) {
      // behavior:'instant' — never let a page's scroll-behavior:smooth turn
      // this loop into a lagging animation that misses reveals.
      window.scrollTo({ top: y, behavior: 'instant' });
      await new Promise((r) => setTimeout(r, 35));
    }
    window.scrollTo({ top: 0, behavior: 'instant' });
  });
  await page.waitForTimeout(1200); // let reveal transitions finish

  // Freeze every CSS/WAAPI animation at a deterministic end state.
  // Finite animations (hero frame draw, reveals) jump to completion;
  // infinite ones (atmosphere drifters, groovy paths, live-dot pulse,
  // mermaid-pulse dots) are cancelled back to their base style. This is
  // what makes screenshots byte-identical between runs on pages that
  // ship NO prefers-reduced-motion rules (docs/index.html has none — the
  // landing page's own media block was the only reason IT converged).
  await page.evaluate(() => {
    if (!document.getAnimations) return;
    for (const a of document.getAnimations()) {
      try {
        a.finish();
      } catch (_) {
        try {
          a.cancel();
        } catch (_2) {
          /* element already gone */
        }
      }
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
