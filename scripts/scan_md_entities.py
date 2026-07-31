"""Scan .md files for raw '&' that would break XML-strict renderers.

Diagnostic-only companion to scripts/fix_md_entities.py. Reports every raw
ampersand (one that is not part of a valid entity) outside fenced code
blocks and inline code spans, skipping generated repomix-*.md bundles.

Use `scripts/fix_md_entities.py` to actually apply the escaping.

Usage:
    python scripts/scan_md_entities.py
"""
import glob
import re

ENTITY = re.compile(
    r"&(?:amp|lt|gt|quot|apos|mdash|ndash|rarr|rArr|darr|uarr|larr|harr|"
    r"hellip|nbsp|ensp|emsp|minus|plusmn|middot|copy|reg|deg|times|divide|"
    r"micro|sup[0-9]?|frac[0-9]+|[a-zA-Z][a-zA-Z0-9]*);"
)
NUMERIC = re.compile(r"&#x[0-9a-fA-F]+;|&#[0-9]+;")


def split_regions(text):
    """Merged, sorted (start, end) intervals that are PROTECTED."""
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


def main():
    print("=== Files with raw '&' outside code spans/blocks (repomix skipped) ===")
    total = 0
    for path in sorted(glob.glob("**/*.md", recursive=True)):
        base = path.lower()
        if any(k in base for k in ("node_modules", ".git", "repomix")):
            continue
        text = open(path, encoding="utf-8", errors="replace").read()
        protected = split_regions(text)
        line_offsets = []
        pos = 0
        for line in text.split("\n"):
            line_offsets.append(pos)
            pos += len(line) + 1
        hits = []
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
            hits.append(m.start())
        if hits:
            for idx in hits[:5]:
                line_no = 0
                for li, off in enumerate(line_offsets):
                    if off <= idx:
                        line_no = li
                    else:
                        break
                ctx = text[max(0, idx - 45):idx + 12].replace("\n", " ")
                print(f"  {path}:{line_no + 1}  ...{ctx}...")
            print(f"  -> {len(hits)} raw '&' in {path}")
            total += len(hits)
    print(f"\nTOTAL raw '&': {total}")


if __name__ == "__main__":
    main()
