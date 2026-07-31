#!/usr/bin/env python3
"""Validate the inline-svg -> repo-relative-svg-file conversion.

Checks:
  1. Every generated docs/assets/svg/*.svg parses as well-formed XML.
  2. No bare & anywhere in the .svg files.
  3. Every <img src="docs/assets/svg/..."> reference in the .md files resolves.
  4. No inline <svg> tags remain in the .md files.
  5. (If gh available) GitHub's /markdown render keeps the <img> tags.
"""
import json
import re
import subprocess
import tempfile
import os
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSET = ROOT / "docs" / "assets" / "svg"
MD_FILES = sorted(
    set(list(ROOT.glob("*.md")) + list(ROOT.glob("docs/*.md")) + list(ROOT.glob(".github/*.md")))
)
MD_FILES = [p for p in MD_FILES if not p.name.startswith("repomix")]


def main():
    # 1 + 2: XML validity + bare &
    svgs = sorted(ASSET.glob("*.svg"))
    print(f"generated svg files: {len(svgs)}")
    bad = 0
    bare = 0
    for f in svgs:
        content = f.read_bytes().decode("utf-8", "replace")
        m = re.findall(r"&(?!amp;|lt;|gt;|quot;|apos;|#)", content)
        if m:
            bare += len(m)
            print(f"  BARE & in {f}: {m[:3]}")
        try:
            ET.fromstring(content)
        except Exception as e:
            bad += 1
            print(f"  XML FAIL {f}: {e}")
    print(f"xml-fail: {bad} | bare &: {bare}")
    assert bad == 0, "XML failures found"
    assert bare == 0, "bare & found in svg files"

    # 3: img srcs resolve — resolve RELATIVE TO THE MD FILE'S DIRECTORY
    # (GitHub resolves relative image paths against the rendered file's location,
    # not the repo root — so docs/foo.md must use assets/svg/..., not docs/assets/svg/...)
    missing = []
    refs = 0
    bad_relative = 0
    for p in MD_FILES:
        text = p.read_bytes().decode("utf-8", "replace")
        for m in re.finditer(r'<img\s+src="([^"]+\.svg)"', text):
            src = m.group(1)
            if "://" in src or src.startswith("/"):
                continue
            refs += 1
            resolved = (p.parent / src).resolve()
            if not resolved.exists():
                missing.append(f"{p}: {src} -> resolves to {resolved} (MISSING)")
            # also flag if docs/*.md uses the root-relative docs/assets/svg/ prefix
            if p.parent != ROOT and src.startswith("docs/"):
                bad_relative += 1
                print(f"  BAD-RELATIVE {p}: {src} (should be relative to docs/)")
    print(f"img refs to assets: {refs} | missing: {len(missing)} | root-prefix-in-subdir: {bad_relative}")
    for x in missing[:10]:
        print("  MISSING:", x)
    assert not missing, "unresolved img srcs"
    assert bad_relative == 0, "subdir md files used root-relative docs/ prefix"

    # 4: no inline svg remains
    leftover = 0
    for p in MD_FILES:
        text = p.read_bytes().decode("utf-8", "replace")
        n = len(re.findall(r"<svg\b", text))
        if n:
            leftover += n
            print(f"  LEFTOVER svg in {p}: {n}")
    print(f"leftover inline <svg> tags: {leftover}")
    assert leftover == 0, "inline svg tags remain"

    # 5: GitHub /markdown render keeps imgs
    sample = open(ROOT / "README.md", encoding="utf-8").read()[:40000]
    payload = json.dumps({"text": sample, "mode": "gfm"})
    req = os.path.join(tempfile.gettempdir(), "validate.json")
    open(req, "w", encoding="utf-8").write(payload)
    p = subprocess.run(["gh", "api", "-X", "POST", "/markdown", "--input", req],
                       capture_output=True, encoding="utf-8", errors="replace")
    html = p.stdout
    kept = len(re.findall(r'<img[^>]*src="docs/assets/svg/', html))
    print(f"github /markdown keeps {kept} repo-relative svg imgs (of ~{sample.count('docs/assets/svg')} in sample)")
    assert kept > 0, "github stripped the repo-relative imgs"

    print("\nALL VALIDATION CHECKS PASSED")


if __name__ == "__main__":
    main()
