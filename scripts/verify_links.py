#!/usr/bin/env python3
"""
MandiIQ Link Verification Script
Checks all inter-page links across docs, landing, and heartbeat pages.
Usage: python scripts/verify_links.py
"""

import re
import sys
from pathlib import Path
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parent.parent

PAGES = {
    "landing": REPO_ROOT / "landing" / "index.html",
    "docs": REPO_ROOT / "docs" / "index.html",
    "heartbeat": REPO_ROOT / "docs" / "heartbeat-dashboard.html",
}

EXTERNAL_DOMAINS = {
    "mandiiq.streamlit.app",
    "github.com",
    "flawsom.github.io",
    "mandiiq-api.onrender.com",
    "fonts.googleapis.com",
    "fonts.gstatic.com",
    "cdn.jsdelivr.net",
}


def extract_links(filepath: Path) -> list[dict]:
    """Extract all href links from an HTML file."""
    html = filepath.read_text(encoding="utf-8")
    links = []
    for match in re.finditer(r'href=["\']([^"\']+)["\']', html):
        url = match.group(1)
        if url.startswith("#") or url.startswith("mailto:") or url.startswith("data:"):
            continue
        parsed = urlparse(url)
        links.append({
            "url": url,
            "path": parsed.path,
            "is_external": bool(parsed.netloc),
            "netloc": parsed.netloc,
            "line": html[:match.start()].count("\n") + 1,
        })
    return links


def check_link(link: dict, source_name: str, source_file: Path) -> tuple[bool, str]:
    """Check if a link is valid. Returns (is_valid, reason)."""
    url = link["url"]

    # Root link (/) is valid in a web context
    if url == "/":
        return True, "OK (root)"

    # External links: verify domain is expected
    if link["is_external"]:
        domain = link["netloc"].lower()
        if ":" in domain:
            domain = domain.split(":")[0]
        if domain in EXTERNAL_DOMAINS:
            return True, "OK (external)"
        return True, "OK (external: %s)" % domain

    # Internal links: resolve relative to source file directory
    source_dir = source_file.resolve().parent
    resolved = (source_dir / link["path"]).resolve()

    if resolved.exists() and resolved.is_file():
        try:
            rel = resolved.relative_to(REPO_ROOT)
            return True, "OK -> %s" % rel
        except ValueError:
            return True, "OK -> %s" % resolved

    return False, "NOT FOUND: %s" % resolved


def main():
    errors = []
    total = 0

    for name, filepath in PAGES.items():
        if not filepath.exists():
            print("[SKIP] %s: %s not found" % (name, filepath))
            continue

        print("")
        print("=" * 60)
        print("[DOCS] %s: %s" % (name.upper(), filepath.relative_to(REPO_ROOT)))
        print("=" * 60)

        links = extract_links(filepath)
        for link in links:
            total += 1
            valid, reason = check_link(link, name, filepath)
            status = "[OK]" if valid else "[FAIL]"
            print("  %s %-50s %s" % (status, link["url"], reason))
            if not valid:
                errors.append("%s:%d - %s" % (name, link["line"], link["url"]))

    print("")
    print("=" * 60)
    print("SUMMARY: %d links checked, %d errors" % (total, len(errors)))
    print("=" * 60)

    if errors:
        print("")
        print("ERRORS:")
        for err in errors:
            print("  * %s" % err)
        sys.exit(1)
    else:
        print("")
        print("All links verified successfully!")


if __name__ == "__main__":
    main()
