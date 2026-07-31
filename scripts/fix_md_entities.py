"""Escape raw '&' -> '&amp;' in documentation .md files, single-pass O(n).

Fixes `xmlParseEntityRef: no name` errors in XML-strict renderers (Firefox
opening rendered XHTML, LibreOffice, docx/pdf pipelines). Badge URLs like
`...?style=for-the-badge&label=Version` contain raw ampersands that are
legal in HTML but break XML parsing. Escaping to `&amp;` renders identically
in every markdown renderer.

Fenced code blocks (``` ... ```) and inline code spans (`...`) are left
untouched so shell/bash examples and code stay byte-identical.

Generated repomix-*.md bundles are skipped (tooling snapshots, not docs).
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
    """Return merged, sorted (start, end) intervals that are PROTECTED
    (fenced code blocks and inline code spans)."""
    protected = []

    # Fenced code blocks — track by line offsets
    offsets = []
    pos = 0
    lines = text.split("\n")
    for line in lines:
        offsets.append(pos)
        pos += len(line) + 1

    fence_start = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            if fence_start is None:
                fence_start = offsets[i]
            else:
                protected.append((fence_start, offsets[i] + len(line)))
                fence_start = None

    # Inline code spans (single-line backticks)
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


def fix_file(path):
    text = open(path, encoding="utf-8", errors="replace").read()
    protected = split_regions(text)
    count = 0
    out = []
    ptr = 0
    i = 0
    n = len(text)
    while i < n:
        while ptr < len(protected) and protected[ptr][1] <= i:
            ptr += 1
        in_prot = ptr < len(protected) and protected[ptr][0] <= i < protected[ptr][1]
        ch = text[i]
        if ch == "&" and not in_prot:
            rest = text[i : i + 40]
            if not ENTITY.match(rest) and not NUMERIC.match(rest):
                out.append("&amp;")
                count += 1
                i += 1
                continue
        out.append(ch)
        i += 1

    if count:
        open(path, "w", encoding="utf-8", newline="").write("".join(out))
    return count


def main():
    total = 0
    for path in sorted(glob.glob("**/*.md", recursive=True)):
        base = path.lower()
        if any(k in base for k in ("node_modules", ".git", "repomix")):
            continue
        n = fix_file(path)
        if n:
            print(f"{n:>6} & escaped in {path}")
            total += n
    print(f"\nTOTAL: {total} raw '&' escaped")


if __name__ == "__main__":
    main()
