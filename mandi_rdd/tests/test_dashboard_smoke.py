"""
Smoke tests for the Streamlit dashboard.

These run without a headless browser or running server:
  1. Scan all dashboard .py files for the f-string/CSS brace collision bug class
     (see commit 7b5c742 — NameError: name 'text' is not defined).
  2. Verify the _FRESHNESS_TABLE_CSS block in executive_overview.py is a plain
     string (not an f-string), so the fix cannot regress.
"""

import ast
import inspect
import sys
from pathlib import Path

import pytest

DASHBOARD_DIR = Path(__file__).resolve().parent.parent / "dashboard"


# ── 1. Global scan for f-string CSS collisions ──

def _find_all_fstring_css_hits(src: str) -> list[tuple[str, int]]:
    """Return (line_num, snippet) pairs for CSS-brace patterns in f-strings."""
    import re

    pat = re.compile(
        r'(?<!\{)'
        r'\{\s*'
        r'[a-z]+(?:-[a-z]+)*'
        r'\s*:\s+'                    # CSS: colon + whitespace before value.
        r'[^}]+'
        r'\}'
        r'(?!\})',
        re.IGNORECASE,
    )
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []

    hits: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.JoinedStr):
            continue
        seg = ast.get_source_segment(src, node)
        if seg is None:
            continue
        for m in pat.finditer(seg):
            line = src[: m.start()].count("\n") + 1
            hits.append((m.group(0)[:80], line))
    return hits


def test_no_fstring_css_braces_in_executive_overview():
    """No f-string in executive_overview.py contains a CSS-brace collision."""
    src = (DASHBOARD_DIR / "pages" / "executive_overview.py").read_text(encoding="utf-8")
    hits = _find_all_fstring_css_hits(src)
    assert not hits, (
        f"Found {len(hits)} f-string CSS-brace collision(s) in executive_overview.py. "
        "Convert the block to a plain string (remove 'f' prefix, replace {{ }} with single braces)."
    )


def test_no_fstring_css_braces_anywhere():
    """No .py file anywhere in the dashboard package contains this bug class."""
    for py_file in sorted(DASHBOARD_DIR.rglob("*.py")):
        src = py_file.read_text(encoding="utf-8", errors="replace")
        hits = _find_all_fstring_css_hits(src)
        assert not hits, (
            f"Found {len(hits)} f-string CSS-brace collision(s) in {py_file.relative_to(DASHBOARD_DIR)}. "
            "Convert the block to a plain string."
        )


# ── 2. Regression test: _FRESHNESS_TABLE_CSS is a plain string ──

def test_freshness_table_css_is_plain_string():
    """_FRESHNESS_TABLE_CSS must be a plain str, not an f-string."""
    src = (DASHBOARD_DIR / "pages" / "executive_overview.py").read_text(encoding="utf-8")
    tree = ast.parse(src)

    css_node = None
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "_FRESHNESS_TABLE_CSS":
                css_node = node.value
                break

    assert css_node is not None, "_FRESHNESS_TABLE_CSS assignment not found"
    assert isinstance(css_node, ast.Constant), (
        f"_FRESHNESS_TABLE_CSS is an {type(css_node).__name__}, expected a plain string constant. "
        "Remove the 'f' prefix so Python does not interpret CSS braces as expressions."
    )
    assert isinstance(css_node.value, str), (
        f"_FRESHNESS_TABLE_CSS value is {type(css_node.value).__name__}, expected str"
    )
    assert "text-align: left; padding: 0.6rem 0.75rem;" in css_node.value, (
        "Expected CSS rule not found in _FRESHNESS_TABLE_CSS"
    )


# ── 3. Module import smoke test ──

def test_executive_overview_module_imports():
    """executive_overview.py can be imported without syntax errors."""
    # We only test importability, not the full st.run() pipeline.
    # If the file has broken f-strings, the import will raise SyntaxError.
    with open(DASHBOARD_DIR / "pages" / "executive_overview.py", encoding="utf-8") as f:
        code = f.read()
    try:
        compile(code, "executive_overview.py", "exec")
    except SyntaxError as e:
        pytest.fail(f"executive_overview.py has a syntax error: {e}")