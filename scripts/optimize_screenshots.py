#!/usr/bin/env python3
"""Optimize raw full-page captures into the committed README gallery PNGs.

Reads the raw captures written by scripts/_capture_screenshots.mjs into
.browser_shots/ and writes the optimized images that README.md references
under screenshots/: downscaled to a max width of 1280px (the README renders
them at 80% width), MEDIANCUT-quantized to 256 colors, optimize=True.

Mirrors the one-time optimization that first replaced the placeholder
images, as a repeatable CI step (refresh-screenshots.yml). Exits non-zero
if any source capture is missing.
"""

from __future__ import annotations

import os
import sys

from PIL import Image

MAX_WIDTH = 1280

# Guard against committing a 200-with-error-body capture: a legitimate
# full-page capture of these dense pages is always well above 100KB, so
# anything under this is almost certainly a blank/error/partial page.
MIN_BYTES = 50_000

MAPPING = [
    (".browser_shots/landing-live.png", "screenshots/landing.png"),
    (".browser_shots/dashboard-live.png", "screenshots/dashboard_home.png"),
    (".browser_shots/api-docs-live.png", "screenshots/api_docs.png"),
]


def main() -> int:
    failures = 0
    for src, dst in MAPPING:
        if not os.path.exists(src):
            print(f"MISSING {src} — cannot optimize {dst}")
            failures += 1
            continue
        im = Image.open(src).convert("RGB")
        w, h = im.size
        if w > MAX_WIDTH:
            nh = int(h * MAX_WIDTH / w)
            im = im.resize((MAX_WIDTH, nh), Image.LANCZOS)
        im = im.quantize(colors=256, method=Image.MEDIANCUT)
        im.save(dst, optimize=True)
        size = os.path.getsize(dst)
        print(f"OK {dst}: {im.size[0]}x{im.size[1]} -> {size // 1024}KB")
        if size < MIN_BYTES:
            print(f"SUSPICIOUS {dst}: only {size // 1024}KB — looks like a blank/error page, failing")
            failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
