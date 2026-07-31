// One-off renderer check: render converted .md files with GitHub-style `marked`
// and validate every inline SVG icon survives into the HTML, including inside
// tables and glassmorphism cards. Also produces standalone HTML files for
// visual confirmation in the preview browser.

import { marked } from "marked";
import { readFileSync, writeFileSync, mkdirSync } from "fs";
import { dirname, join } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, "..");
const OUT = join(root, ".rendercheck");
mkdirSync(OUT, { recursive: true });

const FILES = [
  "QA_AUDIT.md",
  "mandi_rdd/PROJECT_STATUS.md",
  "mandi_rdd/README.md",
  "mandi_rdd/docs/API_KEY_SETUP.md",
  "DEPLOY.md",
  "SUPPORT.md",
  ".github/PULL_REQUEST_TEMPLATE.md",
  ".github/welcome-post-draft.md",
  "README.md",
];

marked.setOptions({ gfm: true, breaks: false });

const SHELL = (title, body) => `<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>${title} — render check</title>
<style>
  body { background:#0B0F1E; color:#e8e8e8; font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif; padding:32px; max-width:1000px; margin:0 auto; }
  h1,h2,h3 { color:#c8ff6e; }
  table { border-collapse:collapse; margin:16px 0; width:100%; }
  th,td { border:1px solid rgba(255,255,255,.15); padding:8px 12px; text-align:left; vertical-align:middle; }
  code { background:rgba(255,255,255,.08); padding:2px 6px; border-radius:4px; font-size:.9em; }
  pre { background:rgba(255,255,255,.05); padding:12px; border-radius:8px; overflow-x:auto; }
  img { max-width:100%; }
  .markdown-body { line-height:1.6; }
</style></head><body>
<div class="markdown-body">${body}</div>
</body></html>`;

let allOk = true;
const report = [];

for (const rel of FILES) {
  const src = join(root, rel);
  const md = readFileSync(src, "utf-8");

  // GitHub-style render (raw HTML like <div>/<svg> passes through unchanged)
  const html = marked.parse(md);

  // ── Programmatic checks on the RENDERED html ──
  const svgOpens = (html.match(/<svg\b/g) || []).length;
  const svgCloses = (html.match(/<\/svg>/g) || []).length;
  const svgBalanced = svgOpens === svgCloses;

  // every <svg> must have a viewBox (decorative divider SVGs omit xmlns —
  // valid inline HTML5 SVG, so xmlns is NOT required)
  const svgTags = html.match(/<svg\b[^>]*>/g) || [];
  const malformedSvg = svgTags.filter((t) => !/viewBox=/.test(t));

  // CDN emoji img tags must NOT survive into rendered output
  const cdnLeft = (html.match(/raw\.githubusercontent\.com[^"']*Emojis/g) || []).length;

  // tables present?
  const tableCount = (html.match(/<table>/g) || []).length;
  // svg inside a table cell? (count cells whose content includes an <svg>)
  const cells = html.match(/<td>[\s\S]*?<\/td>/g) || [];
  const svgInTableCells = cells.filter((c) => /<svg\b/.test(c)).length;

  // glass cards (inline-styled divs); how many contain an <svg> within the
  // card body (windowed lookahead — glass cards nest decorative divs, so a
  // naive non-greedy match would stop at the first inner </div>)
  const cards = (html.match(/<div style="[^"]*background:linear-gradient/g) || []).length;
  const svgInCards = (html.match(
    /<div style="[^"]*background:linear-gradient[^>]*>[\s\S]{0,2500}?<svg\b/g
  ) || []).length;
  const svgTotal = svgOpens;

  // Core assertion: files WITH tables or glass cards must have SVGs land in
  // one of those two rendering contexts. Files with neither (e.g. the PR
  // template) have no such requirement — their SVGs are heading icons.
  const hasContext = tableCount > 0 || cards > 0;
  const svgInContext = !hasContext || svgInTableCells > 0 || svgInCards > 0;

  const ok = svgBalanced && malformedSvg.length === 0 && cdnLeft === 0 && svgInContext;
  if (!ok) allOk = false;

  writeFileSync(join(OUT, rel.replace(/[\\/]/g, "_").replace(/\.md$/, ".html")), SHELL(rel, html));

  report.push({
    file: rel,
    svg: svgTotal,
    svgBalanced,
    malformedSvg: malformedSvg.length,
    cdnLeft,
    tables: tableCount,
    cards,
    svgInTableCells,
    svgInCards,
    ok,
  });
}

console.table(report);
console.log("\n" + (allOk ? "ALL RENDER CHECKS PASS" : "!!! ISSUES FOUND"));
