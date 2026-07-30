/**
 * test_animation_screenshots.mjs
 *
 * Opens the hyper-real repo-structure page, toggles .pulsing on each
 * animated ETL card, waits for CSS @keyframes to play, and captures
 * element screenshots at before/mid/after states.
 *
 * Uses page.screenshot({ clip }) to bypass Playwright's element-stability
 * check (which fails when rAF loops continuously update CSS custom properties).
 *
 * Usage:
 *   node scripts/test_animation_screenshots.mjs
 */

import { chromium } from 'playwright';
import { mkdirSync, existsSync, statSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const OUT = resolve(__dirname, '..', 'test_output');
mkdirSync(OUT, { recursive: true });

const URL = 'http://127.0.0.1:12934/repo-structure-hyperreal.html';

const ANIMATED_CARDS = [
  { label: 'magnifying-glass', dataAnimate: 'tilt',     selector: '#etlGrid .card[data-stage="2"]' },
  { label: 'bar-chart',        dataAnimate: 'bar-grow', selector: '#etlGrid .card[data-stage="3"]' },
  { label: 'floppy-disk',      dataAnimate: 'slide',    selector: '#etlGrid .card[data-stage="4"]' },
];

async function snapCard(page, selector, path) {
  // Use evaluate to get bounding box, then page.screenshot with clip
  // This avoids Playwright's element-stability check
  const bbox = await page.evaluate((sel) => {
    const el = document.querySelector(sel);
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return { x: r.x, y: r.y, width: r.width, height: r.height };
  }, selector);

  if (!bbox) {
    console.error(`  ✗  Element not found: ${selector}`);
    return false;
  }

  await page.screenshot({ path, clip: bbox });
  return existsSync(path) && statSync(path).size > 100;
}

async function run() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  const errors = [];
  page.on('pageerror', (err) => errors.push(err.message));
  page.on('console', (msg) => {
    if (msg.type() === 'error') errors.push(`console.error: ${msg.text()}`);
  });

  console.log(`Opening ${URL}...`);
  await page.goto(URL, { waitUntil: 'domcontentloaded', timeout: 15000 });
  await page.waitForSelector('#etlGrid .card', { timeout: 10000 });
  console.log('  ✓  Page loaded, cards found');

  let allPassed = true;

  for (const card of ANIMATED_CARDS) {
    console.log(`\n--- ${card.label} (data-animate="${card.dataAnimate}") ---`);

    // Verify SVG with matching data-animate exists
    const svgCount = await page.locator(`svg[data-animate="${card.dataAnimate}"]`).count();
    console.log(`  SVG data-animate matches: ${svgCount}`);
    if (svgCount === 0) { allPassed = false; continue; }

    // BEFORE screenshot (no .pulsing)
    const beforeOk = await snapCard(page, card.selector, resolve(OUT, `${card.label}-before.png`));
    console.log(`  before.png: ${beforeOk ? '✓' : '✗'}`);

    // Toggle .pulsing on the card
    await page.evaluate((sel) => {
      const el = document.querySelector(sel);
      if (el) el.classList.add('pulsing');
    }, card.selector);

    const hasPulse = await page.evaluate((sel) => {
      const el = document.querySelector(sel);
      return el && el.classList.contains('pulsing');
    }, card.selector);
    console.log(`  .pulsing active: ${hasPulse}`);

    // Wait 600ms — CSS @keyframes play on compositor thread
    await page.waitForTimeout(600);

    // MID screenshot (animation in progress or finished)
    const midOk = await snapCard(page, card.selector, resolve(OUT, `${card.label}-mid.png`));
    console.log(`  mid.png: ${midOk ? '✓' : '✗'}`);

    // Remove .pulsing and wait for reset
    await page.evaluate((sel) => {
      const el = document.querySelector(sel);
      if (el) el.classList.remove('pulsing');
    }, card.selector);
    await page.waitForTimeout(100);

    // AFTER screenshot (returned to rest)
    const afterOk = await snapCard(page, card.selector, resolve(OUT, `${card.label}-after.png`));
    console.log(`  after.png: ${afterOk ? '✓' : '✗'}`);

    if (!(beforeOk && midOk && afterOk)) allPassed = false;
  }

  // Summary
  console.log(`\n═══════════════════════════════════════`);
  if (errors.length > 0) {
    console.log(`❌  ${errors.length} console error(s):`);
    errors.forEach(e => console.log(`     ${e}`));
    allPassed = false;
  } else {
    console.log(`✅  No console errors`);
  }

  for (const card of ANIMATED_CARDS) {
    for (const phase of ['before', 'mid', 'after']) {
      const p = resolve(OUT, `${card.label}-${phase}.png`);
      if (existsSync(p)) {
        const kb = (statSync(p).size / 1024).toFixed(1);
        console.log(`  📄  ${card.label}-${phase}.png  (${kb} KB)`);
      } else {
        console.error(`  ✗  MISSING: ${card.label}-${phase}.png`);
        allPassed = false;
      }
    }
  }

  console.log(`\n${allPassed ? '✅ All passed' : '❌ Some failed'}`);
  await browser.close();
  process.exit(allPassed ? 0 : 1);
}

run().catch((err) => {
  console.error('Fatal:', err.message);
  process.exit(1);
});
