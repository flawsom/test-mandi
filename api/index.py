"""Vercel serverless entrypoint for MandiIQ FastAPI.

Vercel's Python runtime automatically detects a named `app` instance
in `api/index.py` and wraps it in its own ASGI handler — no uvicorn needed.

The DuckDB is opened in read-only mode from the bundled file (via Git LFS).
For the read-only API subset that works within Vercel's 60s timeout, see the
DEPLOY.md guide.
"""

import sys
from pathlib import Path

# Ensure the repo root is on sys.path so mandi_rdd imports work
_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))

# ── Critical: tell MandiIQ to use the bundled (read-only) DuckDB ──
import os
os.environ.setdefault(
    "MANDIIQ_DB_PATH",
    str(_root / "mandi_rdd" / "data" / "mandi_iq.duckdb"),
)

# Import the real FastAPI app — Vercel picks up the `app` name automatically
from mandi_rdd.api.main import app  # noqa: E402, F401 — import is intentional
