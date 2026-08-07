"""Vercel serverless entrypoint for MandiIQ FastAPI.

Vercel auto-detects the FastAPI app in ``mandi_rdd.api.main`` and serves its
``app`` object. The live-data proxy wrapper is applied inside ``main.py``
itself (gated on Vercel's ``VERCEL`` env), so this file simply re-exports the
already-wrapped app for any path that imports it.

Northflank (render.yaml) starts ``uvicorn mandi_rdd.api.main:app`` directly
and never loads this file — no proxy loop.
"""

import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from mandi_rdd.api.main import app  # noqa: E402,F401  (already wrapped in main)
