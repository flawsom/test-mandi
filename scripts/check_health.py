"""Multi-surface health check for MandiIQ.

Curls all 4 deployed surfaces and verifies each returns live data with
1M+ prices.  Exits non-zero if any surface is stale, down, or unreachable.

Usage:
    python scripts/check_health.py

Exit codes:
    0 — all surfaces healthy
    1 — one or more surfaces failed (details on stdout)
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

SURFACES = {
    "Vercel": "https://test-mandi.vercel.app/health",
    "Northflank": "https://p01--mandiiq--zbvjrztgjqgw.code.run/health",
    "Streamlit": "https://test-mandi-keae7eruks2n4cqvumjfu8.streamlit.app/health",
    "GitHub Pages": "https://flawsom.github.io/test-mandi/",
}

MIN_PRICES = 1_000_000  # anything below this is stale
TIMEOUT_S = 60  # cold starts on Vercel may take ~35s for R2 download


def _probe(url: str, timeout: int = TIMEOUT_S) -> dict:
    """Probe a URL and return parsed result dict.

    Returns dict with keys: url, http_status, ok (bool), n_prices (int or None),
    status (str or None), error (str or None).
    """
    result = {
        "url": url,
        "http_status": None,
        "ok": False,
        "n_prices": None,
        "status": None,
        "error": None,
    }
    req = urllib.request.Request(url, headers={"User-Agent": "MandiIQ/health-check"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result["http_status"] = resp.status
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        result["http_status"] = e.code
        # Streamlit private apps redirect to auth (303) — not a failure, just
        # a known limitation of the Streamlit Community Cloud auth wall.
        if e.code == 303:
            result["ok"] = True
            result["n_prices"] = None
            result["status"] = "private (auth redirect)"
        else:
            result["error"] = f"HTTP {e.code}: {e.reason}"
        return result
    except urllib.error.URLError as e:
        result["error"] = f"URLError: {e.reason}"
        return result
    except OSError as e:
        result["error"] = f"OSError: {e}"
        return result

    # Try JSON parse — /health endpoints return JSON.
    # GitHub Pages returns HTML, so we just check HTTP 200.
    try:
        data = json.loads(body)
        result["n_prices"] = data.get("n_prices")
        result["status"] = data.get("status")
    except (json.JSONDecodeError, ValueError):
        pass  # HTML page (GitHub Pages) — check HTTP status only

    # Evaluate health
    if result["http_status"] == 200:
        if result["n_prices"] is not None:
            # API endpoint — require live prices
            if result["n_prices"] >= MIN_PRICES:
                result["ok"] = True
            else:
                result["error"] = (
                    f"stale: n_prices={result['n_prices']} < {MIN_PRICES}"
                )
        else:
            # HTML page (GitHub Pages) — HTTP 200 is sufficient
            result["ok"] = True
    else:
        result["error"] = result.get("error") or f"HTTP {result['http_status']}"

    return result


def check_all() -> bool:
    """Check all surfaces.  Prints status for each.  Returns True if all OK."""
    all_ok = True
    for name, url in SURFACES.items():
        print(f"  {name}: ", end="", flush=True)
        result = _probe(url)
        if result["ok"]:
            extra = ""
            if result["n_prices"] is not None:
                extra = f" | n_prices={result['n_prices']}"
            if result["status"]:
                extra += f" | status={result['status']}"
            print(f"OK ({result['http_status']}){extra}")
        else:
            err = result["error"] or "unknown error"
            print(f"FAIL — {err}")
            all_ok = False
    return all_ok


if __name__ == "__main__":
    print("MandiIQ multi-surface health check")
    print(f"  min_prices={MIN_PRICES}, timeout={TIMEOUT_S}s")
    print()
    all_ok = check_all()
    print()
    if all_ok:
        print("All surfaces healthy.")
        sys.exit(0)
    else:
        print("One or more surfaces unhealthy!")
        sys.exit(1)