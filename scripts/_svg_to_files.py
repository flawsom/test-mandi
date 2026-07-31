#!/usr/bin/env python3
"""Convert every inline <svg>...</svg> block in the markdown docs to a
repo-relative .svg file under docs/assets/svg/, referenced via <img> tags.

WHY: GitHub's markdown renderer strips BOTH raw inline <svg> tags AND
<img src="data:image/svg+xml;..."> (verified via the GitHub API). Repo-relative
<svg> files referenced as <img src="docs/assets/svg/xxx.svg"> are served and
rendered reliably on github.com, PyPI, VS Code previews, etc.

Also generates docs/assets/svg/mandiq-banner.svg — a self-hosted, valid-XML
replacement for the external capsule-render banner (which emits a bare `&` in
its SVG text node, causing `xmlParseEntityRef: no name`).
"""
import hashlib
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSET_DIR = ROOT / "docs" / "assets" / "svg"

# All markdown files that carry inline SVGs (skip generated repomix dumps)
MD_FILES = sorted(
    set(Path(p) for p in [
        "README.md", "DEPLOY.md", "HANDOFF.md", "HISTORY.md",
        "CONTRIBUTING.md", "CODE_OF_CONDUCT.md", "SECURITY.md", "SUPPORT.md",
        "QA_AUDIT.md", "technical-writeup.md", "mandiiq-deployment-guide.md",
        "NORTHFLANK_DEPLOY.md", "docs/system_design.md", "docs/writeup.md",
        ".github/welcome-post-draft.md", ".github/PULL_REQUEST_TEMPLATE.md",
    ])
)
MD_FILES = [p for p in MD_FILES if p.exists()]

SVG_RE = re.compile(r"<svg\b[^>]*>.*?</svg>", re.S)

# Icons using stroke="currentColor" would render black (invisible on the dark
# cards); substitute the design's light text color so they stay visible.
CURRENT_COLOR = "#E0E0E0"


def svg_for_file(svg: str) -> str:
    s = svg.replace("stroke=\"currentColor\"", f"stroke=\"{CURRENT_COLOR}\"")
    s = s.replace("fill=\"currentColor\"", f"fill=\"{CURRENT_COLOR}\"")
    return s


def normalize(svg: str) -> str:
    s = re.sub(r">\s+<", "><", svg)
    return re.sub(r"\s+", " ", s)


def write_svg_files_and_get_imgs(text: str, cache: dict, md_path: Path) -> str:
    """Replace svg blocks with <img> tags; write deduped .svg files. Returns new text.

    IMPORTANT: the img src is computed RELATIVE TO THE MARKDOWN FILE'S DIRECTORY,
    because GitHub resolves relative image paths against the rendered file's
    location, not the repo root. E.g. docs/foo.md must use assets/svg/... while
    README.md (repo root) uses docs/assets/svg/...
    """
    asset_rel = os.path.relpath(ASSET_DIR, md_path.parent).replace("\\", "/")

    def repl(m):
        svg = m.group(0)
        norm = normalize(svg)
        key = hashlib.md5(norm.encode("utf-8")).hexdigest()[:12]
        fname = cache.get(key)
        if fname is None:
            fname = f"icon-{key}.svg"
            (ASSET_DIR / fname).write_bytes(svg_for_file(svg).encode("utf-8"))
            cache[key] = fname
        wm = re.search(r'width="([^"]+)"', svg)
        hm = re.search(r'height="([^"]+)"', svg)
        width = wm.group(1) if wm else ""
        height = hm.group(1) if hm else ""
        attrs = f'src="{asset_rel}/{fname}"'
        if width:
            attrs += f' width="{width}"'
        if height:
            attrs += f' height="{height}"'
        attrs += ' alt="" style="vertical-align:middle; max-width:100%;"'
        return f"<img {attrs} />"

    return SVG_RE.sub(repl, text)


BANNER_SVG = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="280" viewBox="0 0 1280 280">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#0B0F1E"/>
      <stop offset="55%" stop-color="#0F1F15"/>
      <stop offset="100%" stop-color="#0B0F1E"/>
    </linearGradient>
    <linearGradient id="lime" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#00FF88" stop-opacity="0.35"/>
      <stop offset="50%" stop-color="#00FF88" stop-opacity="0.55"/>
      <stop offset="100%" stop-color="#00FF88" stop-opacity="0.35"/>
    </linearGradient>
  </defs>
  <rect width="1280" height="280" fill="url(#bg)"/>
  <path d="M0,210 C160,170 320,250 480,215 C640,180 800,240 960,210 C1120,180 1210,225 1280,205 L1280,280 L0,280 Z" fill="url(#lime)" opacity="0.5"/>
  <path d="M0,235 C200,205 380,265 560,232 C740,200 900,258 1100,230 C1170,220 1240,235 1280,228 L1280,280 L0,280 Z" fill="#00FF88" opacity="0.18"/>
  <text x="640" y="150" text-anchor="middle" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif" font-size="92" font-weight="700" fill="#FFFFFF">MandiIQ</text>
  <text x="640" y="205" text-anchor="middle" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif" font-size="22" font-weight="500" fill="#9FB8AA" letter-spacing="1">Agricultural Price Intelligence &amp; Causal RDD System</text>
</svg>
"""


def fix_banner_in_readme(text: str) -> str:
    """Replace the external capsule-render <img> with the self-hosted banner."""
    pattern = re.compile(r'<img\s+src="https://capsule-render\.vercel\.app/api[^"]*"[^>]*/?>')
    repl = ('<img src="docs/assets/svg/mandiq-banner.svg" width="100%" '
            'alt="MandiIQ Banner" style="border-radius:12px;" />')
    new_text, n = pattern.subn(repl, text)
    return new_text, n


def main():
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    cache = {}
    total_svg = 0
    total_files = 0
    for p in MD_FILES:
        raw = p.read_bytes().decode("utf-8")
        before = len(SVG_RE.findall(raw))
        if before == 0:
            continue
        new = write_svg_files_and_get_imgs(raw, cache, p)
        total_svg += before
        if p.name == "README.md":
            new, n = fix_banner_in_readme(new)
            if n:
                print(f"README banner img replaced: {n}")
        p.write_bytes(new.encode("utf-8"))
        print(f"{p}: {before} svg blocks converted")
    total_files = len(cache)
    # Write the self-hosted banner (always, so it exists even if README svg loop didn't cover it)
    banner_path = ASSET_DIR / "mandiq-banner.svg"
    if not banner_path.exists():
        banner_path.write_bytes(BANNER_SVG.encode("utf-8"))
        print(f"wrote {banner_path}")
    print("=" * 60)
    print(f"converted {total_svg} svg blocks -> {total_files} unique files in {ASSET_DIR}")


if __name__ == "__main__":
    main()
