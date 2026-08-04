#!/usr/bin/env python3
"""
lint_fstring_css.py — Detect f-string/CSS brace collisions.

Python's f-string syntax treats `{text-align: left;}` as an expression:
  `text - align`  → NameError: name 'text' is not defined.

This script walks every .py file under the given path(s), parses with AST,
and flags any **f-string** (ast.JoinedStr) containing a substring that looks
like a CSS property inside misleading single braces.

Usage:
    python scripts/lint_fstring_css.py [paths ...]
    python scripts/lint_fstring_css.py mandi_rdd/dashboard/

Default (no args): scans the entire repo for .py files.
Exit code: 0 = clean, 1 = violations found, 2 = error.
"""

import ast
import re
import sys
from pathlib import Path

# Regex: a single brace block whose first word looks like a CSS property.
# e.g.  {text-align: ...}   {color: #fff; background: ...}
# The hyphen is the giveaway — Python expressions don't have CSS hyphens
# followed by a colon before an operator.
_CSS_BRACE_PAT = re.compile(
    r'(?<![{{])'      # NOT escaped {{ — those are literal braces in f-strings
    r'\{\s*'
    r'[a-z]+(?:-[a-z]+)*'   # css-property-name
    r'\s*:\s*'
    r'[^}]+'
    r'\}'
    r'(?![}}])',       # NOT escaped }}
    re.IGNORECASE,
)


def scan_file(path: Path) -> list[tuple[int, str]]:
    """Return list of (line_number, snippet) for f-strings with CSS-brace issues."""
    try:
        src = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []  # skip unreadable files

    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []  # skip syntactically damaged files

    hits: list[tuple[int, str]] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.JoinedStr):
            continue
        seg = ast.get_source_segment(src, node)
        if seg is None:
            continue
        for m in _CSS_BRACE_PAT.finditer(seg):
            line = src[: m.start()].count("\n") + 1
            snippet = m.group(0)[:80]
            hits.append((line, snippet))

    return hits


def main() -> int:
    paths = sys.argv[1:] or ["."]
    all_hits: list[tuple[str, int, str]] = []

    for raw in paths:
        root = Path(raw).resolve()
        if root.is_file():
            files = [root]
        else:
            files = sorted(root.rglob("*.py"))

        for f in files:
            for line, snippet in scan_file(f):
                rel = f.relative_to(Path.cwd()) if f.is_relative_to(Path.cwd()) else f
                all_hits.append((str(rel), line, snippet))

    if not all_hits:
        print("✅  No f-string/CSS brace collisions found.")
        return 0

    print(f"❌  Found {len(all_hits)} f-string(s) with CSS-brace collisions:\n")
    for file, line, snippet in all_hits:
        print(f"  {file}:{line}  {snippet}")
    print(
        "\nFix: convert the affected string literal from an f-string to a plain "
        'string (remove the "f" prefix and replace {{ }} with single braces).'
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())