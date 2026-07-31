"""Validate Markdown/SVG health after entity-escape + SVG repair.

Checks:
1. Every local image reference in .md files resolves to an existing file.
2. Every inline <svg> block in .md files is well-formed XML.
3. No raw '&' remains outside fenced code blocks / inline code spans.
4. Every standalone .svg file parses as well-formed XML.
"""
import glob
import os
import re
import sys
import xml.etree.ElementTree as ET

ENTITY = re.compile(
    r"&(?:amp|lt|gt|quot|apos|mdash|ndash|rarr|rArr|darr|uarr|larr|harr|"
    r"hellip|nbsp|ensp|emsp|minus|plusmn|middot|copy|reg|deg|times|divide|"
    r"micro|sup[0-9]?|frac[0-9]+|[a-zA-Z][a-zA-Z0-9]*);"
)
NUMERIC = re.compile(r"&#x[0-9a-fA-F]+;|&#[0-9]+;")


def split_regions(text):
    protected = []
    offsets = []
    pos = 0
    for line in text.split("\n"):
        offsets.append(pos)
        pos += len(line) + 1
    fence_start = None
    for i, line in enumerate(text.split("\n")):
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            if fence_start is None:
                fence_start = offsets[i]
            else:
                protected.append((fence_start, offsets[i] + len(line)))
                fence_start = None
    for m in re.finditer(r"`[^`\n]+`", text):
        protected.append((m.start(), m.end()))
    protected.sort()
    merged = []
    for s, e in protected:
        if merged and s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    return merged


def has_raw_amp(text):
    protected = split_regions(text)
    ptr = 0
    for m in re.finditer(r"&", text):
        while ptr < len(protected) and protected[ptr][1] <= m.start():
            ptr += 1
        in_prot = ptr < len(protected) and protected[ptr][0] <= m.start() < protected[ptr][1]
        if in_prot:
            continue
        rest = text[m.start() : m.start() + 40]
        if ENTITY.match(rest) or NUMERIC.match(rest):
            continue
        return True
    return False


def main():
    errors = 0
    md_files = [
        p for p in glob.glob("**/*.md", recursive=True)
        if "repomix" not in p.lower() and "node_modules" not in p.lower()
        and ".git" not in p
    ]

    # 1 & 2 & 3
    for path in md_files:
        text = open(path, encoding="utf-8", errors="replace").read()
        # 1. local image refs
        for m in re.finditer(r"!\[[^]]*\]\(([^)]+)\)|<img[^>]+src=\"([^\"]+)\"", text):
            src = m.group(1) or m.group(2)
            if src.startswith(("http://", "https://", "data:", "#")):
                continue
            local = src.split("?")[0].split("#")[0]
            if local and not os.path.exists(local):
                print(f"ERROR {path}: missing image {src}")
                errors += 1
        # 2. inline svg well-formed
        for m in re.finditer(r"<svg[^>]*>.*?</svg>", text, re.DOTALL):
            try:
                ET.fromstring(m.group(0))
            except Exception as e:
                print(f"ERROR {path}: inline svg not XML-well-formed: {e}")
                errors += 1
        # 3. raw ampersands
        if has_raw_amp(text):
            print(f"ERROR {path}: raw '&' remains outside code spans/blocks")
            errors += 1

    # 4. standalone svg files
    for path in glob.glob("**/*.svg", recursive=True):
        if "node_modules" in path:
            continue
        try:
            ET.parse(path)
        except Exception as e:
            print(f"ERROR {path}: not XML-well-formed: {e}")
            errors += 1

    if errors:
        print(f"\n{errors} issue(s) found")
        sys.exit(1)
    print(f"ALL CLEAN — {len(md_files)} md files + {len(glob.glob('**/*.svg', recursive=True))} svg files validated")


if __name__ == "__main__":
    main()
