"""
Convert Animated-Fluent-Emojis CDN <img> tags in markdown files to inline
Lucide-style SVG icons (matching the repo's established design language:
24x24 viewBox, stroke=currentColor, stroke-width 2, round caps/joins).

Two modes of replacement:
  1. REDUNDANT PAIR REMOVAL — when a CDN <img> immediately follows an existing
     inline <svg> on the same line (e.g. `<svg ...></svg> <img CDN .../> Heading`),
     the img is simply removed (the svg already provides the icon).
  2. DIRECT REPLACEMENT — otherwise the CDN <img> is replaced with an inline
     Lucide-style SVG sized to match the img's width/height (default 20).

Usage:
    python scripts/convert_cdn_emojis_to_svg.py [file.md ...]
    # no args => auto-scan all .md files for CDN references
"""

import re
import sys
import urllib.parse
from pathlib import Path

# ── CDN detection (case-insensitive; tolerates hyphens/spaces variants) ──
IMG_RE = re.compile(
    r'<img\b[^>]*?src="https://raw\.githubusercontent\.com/[^"]*?/Emojis/([^"]+)"[^>]*?/?>',
    re.IGNORECASE,
)
PAIR_RE = re.compile(
    r'</svg>\s*<img\b[^>]*?src="https://raw\.githubusercontent\.com/[^"]*?/Emojis/([^"]*)"[^>]*?/?>',
    re.IGNORECASE,
)
WIDTH_RE = re.compile(r'width="(\d+)"', re.IGNORECASE)
HEIGHT_RE = re.compile(r'height="(\d+)"', re.IGNORECASE)

SVG_OPEN = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
    'viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
    'stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle">'
)
SVG_CLOSE = "</svg>"

# ── Lucide-style icon paths, keyed by normalized emoji filename ──
# (normalized = URL-decoded, lowercased, e.g. "symbols/check mark button.png")
ICONS: dict[str, str] = {
    "symbols/check mark button.png": '<circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/>',
    "symbols/hourglass with flowing sand.png": (
        '<path d="M5 22h14"/><path d="M5 2h14"/>'
        '<path d="M17 22v-4.172a2 2 0 0 0-.586-1.414L12 12l-4.414 4.414A2 2 0 0 0 7 17.828V22"/>'
        '<path d="M7 2v4.172a2 2 0 0 0 .586 1.414L12 12l4.414-4.414A2 2 0 0 0 17 6.172V2"/>'
    ),
    "symbols/cross mark.png": '<circle cx="12" cy="12" r="10"/><path d="m15 9-6 6"/><path d="m9 9 6 6"/>',
    "objects/bar chart.png": '<path d="M3 3v16a2 2 0 0 0 2 2h16"/><path d="M18 17V9"/><path d="M13 17V5"/><path d="M8 17v-3"/>',
    "symbols/warning.png": '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
    "objects/memo.png": '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M16 13H8"/><path d="M16 17H8"/><path d="M10 9H8"/>',
    "objects/speech balloon.png": '<path d="M7.9 20A9 9 0 1 0 4 16.1L2 22Z"/>',
    "objects/loudspeaker.png": '<path d="m3 11 18-5v12L3 14v-3z"/><path d="M11.6 16.8a3 3 0 1 1-5.8-1.6"/>',
    "objects/locked with key.png": '<circle cx="12" cy="16" r="1"/><rect x="3" y="10" width="18" height="12" rx="2"/><path d="M7 10V7a5 5 0 0 1 10 0v3"/>',
    "objects/chart with upwards trend.png": '<polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/>',
    "symbols/green circle.png": '<circle cx="12" cy="12" r="10"/>',
    "animals and nature/bug.png": (
        '<path d="m8 2 1.88 1.88"/><path d="M14.12 3.88 16 2"/>'
        '<path d="M9 7.13v-1a3.003 3.003 0 1 1 6 0v1"/>'
        '<path d="M12 20c-3.3 0-6-2.7-6-6v-3a4 4 0 0 1 4-4h4a4 4 0 0 1 4 4v3c0 3.3-2.7 6-6 6"/>'
        '<path d="M12 20v-9"/><path d="M6.53 9C4.6 8.8 3 7.1 3 5"/><path d="M6 13H2"/>'
        '<path d="M3 21c0-2.1 1.7-3.9 3.8-4"/><path d="M20.97 5c0 2.1-1.6 3.8-3.5 4"/>'
        '<path d="M22 13h-4"/><path d="M17.2 17c2.1.1 3.8 1.9 3.8 4"/>'
    ),
    "activities/sparkles.png": (
        '<path d="M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z"/>'
        '<path d="M20 3v4"/><path d="M22 5h-4"/><path d="M4 17v2"/><path d="M5 18H3"/>'
    ),
    "smileys/frowning face with open mouth.png": '<path d="M2 12a10 10 0 1 0 20 0A10 10 0 0 0 2 12Z"/><path d="M16 16s-1.5-2-4-2-4 2-4 2"/><line x1="9" x2="9.01" y1="9" y2="9"/><line x1="15" x2="15.01" y1="9" y2="9"/>',
    "objects/robot.png": '<path d="M12 8V4H8"/><rect width="16" height="12" x="4" y="8" rx="2"/><path d="M2 14h2"/><path d="M20 14h2"/><path d="M15 13v2"/><path d="M9 13v2"/>',
    "objects/locked.png": '<rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
    "objects/repeat button.png": '<path d="m17 2 4 4-4 4"/><path d="M3 11v-1a4 4 0 0 1 4-4h14"/><path d="m7 22-4-4 4-4"/><path d="M21 13v1a4 4 0 0 1-4 4H3"/>',
    "objects/clipboard.png": '<rect width="8" height="4" x="8" y="2" rx="1" ry="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><path d="M12 11h4"/><path d="M12 16h4"/><path d="M8 11h.01"/><path d="M8 16h.01"/>',
    "travel and places/globe with meridians.png": '<circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/><path d="M2 12h20"/>',
    "objects/telephone receiver.png": '<path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/>',
    "travel and places/construction.png": '<rect x="2" y="6" width="14" height="8" rx="2"/><path d="M22 9v6"/><path d="M8 20v-2"/><path d="M14 20v-2"/><path d="M6 14h.01"/><path d="M10 14h.01"/>',
    "objects/artist palette.png": (
        '<circle cx="13.5" cy="6.5" r=".5" fill="currentColor"/><circle cx="17.5" cy="10.5" r=".5" fill="currentColor"/>'
        '<circle cx="8.5" cy="7.5" r=".5" fill="currentColor"/><circle cx="6.5" cy="12.5" r=".5" fill="currentColor"/>'
        '<path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10c.926 0 1.648-.746 1.648-1.688 0-.437-.18-.835-.437-1.125-.29-.289-.438-.652-.438-1.125a1.64 1.64 0 0 1 1.668-1.668h1.996c3.051 0 5.555-2.503 5.555-5.554C21.965 6.012 17.461 2 12 2z"/>'
    ),
    "activities/direct hit.png": '<circle cx="12" cy="12" r="10"/><line x1="22" x2="18" y1="12" y2="12"/><line x1="6" x2="2" y1="12" y2="12"/><line x1="12" x2="12" y1="6" y2="2"/><line x1="12" x2="12" y1="22" y2="18"/>',
    "travel and places/rocket.png": '<path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z"/><path d="m12 15-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z"/><path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0"/><path d="M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5"/>',
    "symbols/recycling symbol.png": (
        '<path d="M7 19H4.815a1.83 1.83 0 0 1-1.57-.881 1.785 1.785 0 0 1-.004-1.784L7.196 9.5"/>'
        '<path d="M11 19h8.203a1.83 1.83 0 0 0 1.556-.89 1.784 1.784 0 0 0 0-1.775l-1.226-2.12"/>'
        '<path d="m14 16-3 3 3 3"/><path d="M8.293 13.596 7.196 9.5 3.1 10.598"/>'
        '<path d="m9.344 5.811 1.093-1.892A1.83 1.83 0 0 1 11.985 3a1.784 1.784 0 0 1 1.546.888l3.943 6.843"/>'
        '<path d="m13.378 9.633 4.096 1.098 1.097-4.096"/>'
    ),
    "smileys/waving hand.png": '<path d="M18 11V6a2 2 0 0 0-4 0v5"/><path d="M14 10V4a2 2 0 0 0-4 0v2"/><path d="M10 10.5V6a2 2 0 0 0-4 0v8"/><path d="M18 8a2 2 0 1 1 4 0v6a8 8 0 0 1-8 8h-2c-2.8 0-4.5-.86-5.99-2.34l-3.6-3.6a2 2 0 0 1 2.83-2.82L7 15"/>',
    "objects/light bulb.png": '<path d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5"/><path d="M9 18h6"/><path d="M10 22h4"/>',
    "objects/package.png": '<path d="M11 21.73a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73z"/><path d="M12 22V12"/><polyline points="3.29 7 12 12 20.71 7"/><path d="m7.5 4.27 9 5.15"/>',
    "objects/shield.png": '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/>',
    "objects/wrench.png": '<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>',
    "activities/party popper.png": (
        '<path d="M5.8 11.3 2 22l10.7-3.79"/><path d="M4 3h.01"/><path d="M22 8h.01"/><path d="M15 2h.01"/><path d="M22 20h.01"/>'
        '<path d="m22 2-2.24.75a2.9 2.9 0 0 0-1.96 3.12c.1.86-.57 1.63-1.45 1.63h-.38c-.86 0-1.6.6-1.76 1.44L14 10"/>'
        '<path d="m22 13-.82-.33c-.86-.34-1.82.2-1.98 1.11c-.11.7-.72 1.22-1.43 1.22H17"/>'
        '<path d="m11 2 .33.82c.34.86-.2 1.82-1.11 1.98C9.52 4.9 9 5.52 9 6.23V7"/>'
        '<path d="M11 13c1.93 1.93 2.83 4.17 2 5-.83.83-3.07-.07-5-2-1.93-1.93-2.83-4.17-2-5 .83-.83 3.07.07 5 2Z"/>'
    ),
    "travel and places/traffic light.png": '<path d="M9.5 2h5L17 22H7z"/><path d="M7.9 10.9h8.2"/><path d="M6.9 16.9h10.2"/>',
    "objects/microscope.png": '<path d="M6 18h8"/><path d="M3 22h18"/><path d="M14 22a7 7 0 1 0 0-14h-1"/><path d="M9 14h2"/><path d="M9 12a2 2 0 0 1-2-2V6h6v4a2 2 0 0 1-2 2Z"/><path d="M12 6V3a1 1 0 0 0-1-1H9a1 1 0 0 0-1 1v3"/>',
    "objects/test tube.png": '<path d="M14 2v6a2 2 0 0 0 .245.96l5.51 10.08A2 2 0 0 1 18 22H6a2 2 0 0 1-1.755-2.96l5.51-10.08A2 2 0 0 0 10 8V2"/><path d="M6.453 15h11.094"/><path d="M8.5 2h7"/>',
    "objects/satellite antenna.png": '<path d="M4 10a7.31 7.31 0 0 0 10 10Z"/><path d="m9 15 3-3"/><path d="M17 13a6 6 0 0 0-6-6"/><path d="M21 13A10 10 0 0 0 11 3"/>',
    "objects/brain.png": '<path d="M12 5a3 3 0 1 0-5.997.125 4 4 0 0 0-2.526 5.77 4 4 0 0 0 .556 6.588A4 4 0 1 0 12 18Z"/><path d="M12 5a3 3 0 1 1 5.997.125 4 4 0 0 1 2.526 5.77 4 4 0 0 1-.556 6.588A4 4 0 1 1 12 18Z"/><path d="M12 5v14"/>',
    "animals and nature/spouting whale.png": '<path d="M8 22a5 5 0 0 1-5-5c0-5 3.5-7 8-7s8 2 8 7a5 5 0 0 1-5 5Z"/><path d="m3 11 2-3"/><path d="m13 12 4-3"/>',
    "objects/broom.png": '<path d="m9.06 11.9 8.07-8.06a2.85 2.85 0 1 1 4.03 4.03l-8.06 8.08"/><path d="M7.07 14.94c-1.66 0-3 1.35-3 3.02 0 1.33-2.5 1.52-2 2.02 1.08 1.1 2.49 2.02 4 2.02 2.2 0 4-1.8 4-4.04a3.01 3.01 0 0 0-3-3.02z"/>',
    "objects/link.png": '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>',
    "objects/document.png": '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/>',
    "objects/crystal ball.png": '<path d="M6 3h12l4 6-10 13L2 9Z"/><path d="M11 3 8 9l4 13 4-13-3-6"/><path d="M2 9h20"/>',
    "travel and places/world map.png": '<path d="M14.106 5.553a2 2 0 0 0 1.788 0l3.659-1.83A1 1 0 0 1 21 4.619v12.764a1 1 0 0 1-.553.894l-4.553 2.277a2 2 0 0 1-1.788 0l-4.212-2.106a2 2 0 0 0-1.788 0l-3.659 1.83A1 1 0 0 1 3 19.381V6.618a1 1 0 0 1 .553-.894l4.553-2.277a2 2 0 0 1 1.788 0z"/><path d="M15 5.764v15"/><path d="M9 3.236v15"/>',
    "objects/newspaper.png": '<path d="M4 22h16a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2H8a2 2 0 0 0-2 2v16a2 2 0 0 1-2 2Zm0 0a2 2 0 0 1-2-2v-9c0-1.1.9-2 2-2h2"/><path d="M18 14h-8"/><path d="M15 18h-5"/><path d="M10 6h8v4h-8V6Z"/>',
    "objects/money bag.png": '<rect width="20" height="12" x="2" y="6" rx="2"/><circle cx="12" cy="12" r="2"/><path d="M6 12h.01M18 12h.01"/>',
    "objects/gear.png": (
        '<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/>'
        '<circle cx="12" cy="12" r="3"/>'
    ),
    "activities/folded hands.png": '<path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z"/><path d="M12 5 9.04 7.96a2.17 2.17 0 0 0 0 3.08c.82.82 2.13.85 3 .07l2.07-1.9a2.82 2.82 0 0 1 3.79 0l2.96 2.66"/><path d="m18 15-2-2"/><path d="m15 18-2-2"/>',
}


def normalize(filename: str) -> str:
    """Decode URL-encoding and lowercase an emoji path for map lookup."""
    return urllib.parse.unquote(filename).lower()


def svg_for(filename: str, w: int, h: int) -> str | None:
    key = normalize(filename)
    inner = ICONS.get(key)
    if inner is None:
        return None
    return SVG_OPEN.format(w=w, h=h) + inner + SVG_CLOSE


def process_file(path: Path) -> tuple[int, int, set[str]]:
    """Return (replaced, removed_as_pair, unmapped_keys)."""
    text = path.read_text(encoding="utf-8")
    original = text

    removed = 0
    unmapped: set[str] = set()

    def _pair(m: re.Match) -> str:
        nonlocal removed
        # Only remove redundant pairs whose emoji is actually mapped — an
        # unmapped emoji must survive so it is reported in the unmapped set.
        if normalize(m.group(1)) not in ICONS:
            return m.group(0)
        removed += 1
        return "</svg>"

    text = PAIR_RE.sub(_pair, text)

    def _repl(m: re.Match) -> str:
        nonlocal unmapped
        tag = m.group(0)
        wm = WIDTH_RE.search(tag)
        hm = HEIGHT_RE.search(tag)
        w = int(wm.group(1)) if wm else 20
        h = int(hm.group(1)) if hm else 20
        svg = svg_for(m.group(1), w, h)
        if svg is None:
            key = normalize(m.group(1))
            unmapped.add(key)
            return tag  # leave untouched
        return svg

    text = IMG_RE.sub(_repl, text)
    # Replaced = CDN imgs in the original that have a mapped icon, minus those
    # already handled by the pair-removal pass.
    replaced = sum(1 for m in IMG_RE.finditer(original) if normalize(m.group(1)) in ICONS) - removed

    if text != original:
        path.write_text(text, encoding="utf-8")

    return replaced, removed, unmapped


def main() -> None:
    args = sys.argv[1:]
    base = Path.cwd()

    if args:
        files = [base / a for a in args]
    else:
        # Auto-scan: only real source docs — skip node_modules, temp/backup dirs,
        # hidden dirs other than .github (which holds two target templates),
        # and generated repomix dumps.
        files = [
            p
            for p in base.rglob("*.md")
            if "node_modules" not in str(p)
            and "repomix" not in str(p)
            and not any(part.startswith(".tmp") for part in p.parts)
            and not any(part.startswith(".") and part != ".github" for part in p.parts)
        ]
        # only those that actually contain CDN refs
        files = [p for p in files if "raw.githubusercontent.com" in p.read_text(encoding="utf-8", errors="replace")]

    total_replaced = 0
    total_removed = 0
    all_unmapped: set[str] = set()

    print(f"{'File':<45} {'Replaced':>9} {'Pair-removed':>13}")
    print("-" * 72)
    for p in files:
        if not p.exists():
            print(f"{p}: NOT FOUND")
            continue
        replaced, removed, unmapped = process_file(p)
        total_replaced += replaced
        total_removed += removed
        all_unmapped |= unmapped
        print(f"{str(p).replace(chr(92), '/'):<45} {replaced:>9} {removed:>13}")

    print("-" * 72)
    print(f"TOTAL replaced with SVG: {total_replaced}")
    print(f"TOTAL removed (redundant pairs): {total_removed}")
    if all_unmapped:
        print(f"\n!! UNMAPPED EMOJIS ({len(all_unmapped)}):")
        for k in sorted(all_unmapped):
            print(f"   - {k}")
    else:
        print("All emojis mapped: OK")


if __name__ == "__main__":
    main()
