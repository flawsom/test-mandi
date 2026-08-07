"""Vercel serverless entrypoint for MandiIQ FastAPI.

Vercel's Python runtime automatically detects a named `app` instance
in `api/index.py` and wraps it in its own ASGI handler — no uvicorn needed.

On cold start we attempt an R2 data-bus restore of the freshest hourly
DuckDB into /tmp (writable in Vercel's runtime). If R2 creds are absent or
the restore fails, we fall back to the bundled (git-LFS) DB so the read-only
subset still works within Vercel's 60s timeout. See DEPLOY.md.
"""

import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))

import os

_bundled = _root / "mandi_rdd" / "data" / "mandi_iq.duckdb"

# ── Prefer the freshest R2 data-bus DB (restored to /tmp) if possible ──
_tmp_db = Path(os.environ.get("TMPDIR", "/tmp")) / "mandi_iq.duckdb"
_have_r2 = all(os.environ.get(k) for k in (
    "R2_ACCESS_KEY_ID", "R2_ACCOUNT_ID", "R2_BUCKET", "R2_SECRET_ACCESS_KEY"))

if _have_r2 and not _tmp_db.exists():
    try:
        from mandi_rdd.storage.r2_sync import restore_db
        res = restore_db(db_path=_tmp_db)
        if res.get("status") == "ok" and _tmp_db.exists() and _tmp_db.stat().st_size > 1_000_000:
            os.environ["MANDIIQ_DB_PATH"] = str(_tmp_db)
            print(f"[bootstrap] R2 restore OK -> {_tmp_db} ({_tmp_db.stat().st_size} bytes)")
        else:
            os.environ.setdefault("MANDIIQ_DB_PATH", str(_bundled))
            print(f"[bootstrap] R2 restore incomplete ({res}), using bundled DB")
    except Exception as e:  # pragma: no cover - defensive
        os.environ.setdefault("MANDIIQ_DB_PATH", str(_bundled))
        print(f"[bootstrap] R2 restore failed ({e}); using bundled DB")
else:
    os.environ.setdefault("MANDIIQ_DB_PATH", str(_bundled))
    if not _have_r2:
        print("[bootstrap] no R2 creds; using bundled DB")

# Import the real FastAPI app — Vercel picks up the `app` name automatically
from mandi_rdd.api.main import app  # noqa: E402, F401 — import is intentional
