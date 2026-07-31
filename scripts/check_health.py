"""Multi-surface health check for MandiIQ.

Curls all 4 deployed surfaces and reports which ones serve the LATEST
database.  The freshest n_prices observed across all reachable API
surfaces is the reference: any API surface serving fewer rows is stale,
any unreachable surface is down.

In addition to the human-readable table it writes a machine-readable
status JSON (default: docs/health-status.json) containing the per-surface
verdicts and a STABLE signature — the payload hash EXCLUDING the
generated_at timestamp and the history array — so CI can gate
commits/redeploys on real status changes without a timestamp churn loop.

History: the JSON carries a `history` array (last ~30 verdict sets with
timestamps, oldest first) for the landing-page sparkline.  A new entry
is appended ONLY when the verdict state actually changed since the last
recorded entry (transition-gated), never on a plain re-run — this keeps
the stable signature deterministic between runs so the workflow's
commit/Pages-dispatch gate can't loop via its own workflow_run trigger.

Usage:
    python scripts/check_health.py [--json-out PATH] [--no-json]

Exit codes:
    0 — all surfaces up, and every API surface serves the latest DB
    1 — one or more surfaces are stale (behind the freshest DB) or down

Stdlib-only so it runs on the ubuntu runner with no pip install.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request

# name -> (url, kind) where kind is "api" (returns JSON /health) or "html".
SURFACES = {
    "Vercel": ("https://test-mandi.vercel.app/health", "api"),
    "Northflank": ("https://p01--mandiiq--zbvjrztgjqgw.code.run/health", "api"),
    "Streamlit": ("https://test-mandi-keae7eruks2n4cqvumjfu8.streamlit.app/health", "api"),
    "GitHub Pages": ("https://flawsom.github.io/test-mandi/", "html"),
}

MIN_PRICES = 1_000_000  # sanity floor: below this we assume a broken/empty DB
TIMEOUT_S = 60  # cold starts on Vercel may take ~35s for R2 download
HISTORY_MAX = 30  # keep the last ~30 verdict sets for the landing sparkline

# The Northflank API redeploys on every push to master, so a transient
# 503 "no healthy upstream" mid-redeploy is expected. Retry each surface
# up to MAX_ATTEMPTS times, RETRY_DELAY_S apart, before marking it down.
MAX_ATTEMPTS = 3
RETRY_DELAY_S = 20
RETRYABLE_HTTP = {429, 500, 502, 503, 504}  # back-off + gateway errors


def _probe(url: str, timeout: int = TIMEOUT_S) -> dict:
    """Probe a URL with retries and return parsed result dict.

    Retries up to MAX_ATTEMPTS times (RETRY_DELAY_S apart) when the fetch
    fails with a network error or a retryable HTTP status (429/5xx), which
    covers the API being mid-redeploy right after a push. A definitive
    answer (200, 303 auth redirect, 4xx client error) is returned at once.

    Returns dict with keys: url, http_status, n_prices (int or None),
    status (str or None), error (str or None), attempts (int).
    """
    result = {
        "url": url,
        "http_status": None,
        "n_prices": None,
        "status": None,
        "error": None,
        "attempts": 0,
    }
    body = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        result["attempts"] = attempt
        req = urllib.request.Request(url, headers={"User-Agent": "MandiIQ/health-check"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                result["http_status"] = resp.status
                body = resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            result["http_status"] = e.code
            # Streamlit Community Cloud private apps redirect to auth (303) —
            # the app is alive, just behind the auth wall.
            if e.code == 303:
                result["status"] = "private (auth redirect)"
                return result
            if e.code in RETRYABLE_HTTP:
                if attempt < MAX_ATTEMPTS:
                    print(f"  [retry {attempt}/{MAX_ATTEMPTS}] {url} -> HTTP {e.code} ({e.reason}); retrying in {RETRY_DELAY_S}s")
                    time.sleep(RETRY_DELAY_S)
                    continue
                result["error"] = f"HTTP {e.code}: {e.reason} (after {MAX_ATTEMPTS} attempts)"
                return result
            result["error"] = f"HTTP {e.code}: {e.reason}"
            return result
        except urllib.error.URLError as e:
            if attempt < MAX_ATTEMPTS:
                print(f"  [retry {attempt}/{MAX_ATTEMPTS}] {url} -> {e.reason}; retrying in {RETRY_DELAY_S}s")
                time.sleep(RETRY_DELAY_S)
                continue
            result["error"] = f"URLError: {e.reason} (after {MAX_ATTEMPTS} attempts)"
            return result
        except OSError as e:
            if attempt < MAX_ATTEMPTS:
                print(f"  [retry {attempt}/{MAX_ATTEMPTS}] {url} -> OSError: {e}; retrying in {RETRY_DELAY_S}s")
                time.sleep(RETRY_DELAY_S)
                continue
            result["error"] = f"OSError: {e} (after {MAX_ATTEMPTS} attempts)"
            return result

        # Reached only on a successful HTTP exchange.
        break

    # Try JSON parse — /health endpoints return JSON.
    # GitHub Pages returns HTML, so we just check HTTP 200.
    try:
        data = json.loads(body)
        result["n_prices"] = data.get("n_prices")
        result["status"] = data.get("status")
    except (json.JSONDecodeError, ValueError):
        pass  # HTML page (GitHub Pages) — check HTTP status only

    return result


def _stable_signature(report: dict) -> str:
    """SHA-256 of the status payload EXCLUDING generated_at and history.

    CI compares this across runs: a timestamp-only change must never
    trigger a commit/redeploy, but any real verdict/row-count change does.
    History is excluded because it only grows on verdict transitions (see
    run_check) — including it would make the signature churn every run and
    defeat the workflow's loop-prevention gate.
    """
    payload = {k: v for k, v in report.items() if k not in ("generated_at", "history")}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def _verdict_state_key(entry: dict) -> str:
    """Hash of the verdict-relevant fields of a history entry.

    Used for transition detection: two entries with identical overall
    status and per-surface verdicts are the same state, regardless of the
    timestamps or the DB reference row count.
    """
    key = {
        "overall": entry.get("overall"),
        "verdicts": entry.get("verdicts"),
    }
    canonical = json.dumps(key, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def _load_prev_history(path: str) -> list:
    """Load the `history` array from a previously written status JSON.

    Returns [] if the file is missing, malformed, or predates the history
    field (schema 1 files have no history).
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("history", []) or []
    except (OSError, ValueError, json.JSONDecodeError):
        return []


def run_check(prev_history: list | None = None) -> tuple[bool, dict]:
    """Probe all surfaces, compute DB freshness parity, print verdicts.

    Args:
        prev_history: the `history` array from the previously written JSON
            (may be None/[] on first run).  A new entry is appended only
            when the verdict state changed since the last recorded entry.

    Returns (all_ok, report) where report is the machine-readable status
    dict (including history, a stable signature and the human table text).
    """
    # 1. Probe everything
    results = {}
    for name, (url, kind) in SURFACES.items():
        results[name] = _probe(url)
        results[name]["kind"] = kind

    # 2. Compute the freshest reference count across reachable API surfaces.
    api_counts = [
        r["n_prices"]
        for r in results.values()
        if r["kind"] == "api"
        and r["n_prices"] is not None
        and r["http_status"] == 200
    ]
    ref = max(api_counts) if api_counts else None

    # 3. Verdict per surface.
    lines = []
    lines.append(f"  {'Surface':<14} | {'Verdict':<13} | {'n_prices':>11} | Notes")
    lines.append("  " + "-" * 14 + "-+-" + "-" * 13 + "-+-" + "-" * 11 + "-+-" + "-" * 28)
    all_ok = True
    serving_latest = []
    stale = []
    down = []
    count_unavailable = []
    surfaces_out = {}

    for name, r in results.items():
        kind = r["kind"]
        status = r["http_status"]
        n = r["n_prices"]

        is_streamlit = "streamlit.app" in r["url"]

        # Determine verdict
        if status == 303 and r.get("status", "").startswith("private"):
            verdict = "UP (auth)"           # alive, count hidden behind auth wall
            note = "auth redirect — count unavailable"
            count_unavailable.append(name)
        elif status == 200 and (kind == "html" or is_streamlit):
            # Static / non-JSON surfaces: HTTP 200 is sufficient.  This covers
            # GitHub Pages (HTML) AND a public Streamlit app — a .streamlit.app
            # host always serves the app shell HTML at /health, never the FastAPI
            # JSON, so a 200 with no n_prices must not fail the check.
            verdict = "UP (static)"
            note = "HTTP 200 — no JSON count expected"
            count_unavailable.append(name)
        elif status == 200 and n is None:
            # A real API (Vercel/Northflank) returned 200 but the body was not
            # the expected /health JSON — treat as broken, not healthy.
            verdict = "BROKEN"
            note = "HTTP 200 but no n_prices in body"
            all_ok = False
            down.append(name)
        elif status == 200 and n is not None and ref is not None:
            if n >= ref and n >= MIN_PRICES:
                verdict = "LATEST"
                note = f"matches latest DB ({n:,} rows)"
                serving_latest.append(name)
            elif n < MIN_PRICES:
                verdict = "STALE"
                note = f"n_prices={n:,} below sanity floor {MIN_PRICES:,}"
                all_ok = False
                stale.append(name)
            else:
                verdict = "STALE"
                note = f"behind latest DB ({n:,} vs {ref:,})"
                all_ok = False
                stale.append(name)
        else:
            verdict = "DOWN"
            note = r.get("error") or f"HTTP {status}"
            all_ok = False
            down.append(name)

        # Surface when a surface needed retries (transient 503s mid-redeploy).
        if r.get("attempts", 1) > 1:
            note = f"{note} [retried {r['attempts']}x]"

        n_str = f"{n:,}" if n is not None else "-"
        lines.append(f"  {name:<14} | {verdict:<13} | {n_str:>11} | {note}")

        # `attempts` / `retried` surface the probe retry count (transient
        # 503s mid-redeploy) in the machine-readable JSON, not just the
        # human table, so the landing badge can show which surfaces needed
        # retries. attempts=1 means the first try succeeded.
        surfaces_out[name] = {
            "verdict": verdict,
            "n_prices": n,
            "http_status": status,
            "kind": kind,
            "note": note,
            "url": r["url"],
            "attempts": r.get("attempts", 1),
            "retried": r.get("attempts", 1) > 1,
        }

    # 4. Summary line — which surfaces serve the latest DB?
    lines.append("")
    if ref is not None:
        lines.append(f"  Latest DB reference: {ref:,} rows")
        if serving_latest:
            lines.append(f"  Serving latest DB : {', '.join(serving_latest)}")
        else:
            lines.append("  Serving latest DB : (none)")
    else:
        lines.append("  Latest DB reference: unknown — no API surface returned a count")

    if stale:
        lines.append(f"  Stale surfaces    : {', '.join(stale)}")
    if down:
        lines.append(f"  Down surfaces     : {', '.join(down)}")
    if count_unavailable:
        lines.append(f"  Count unavailable : {', '.join(count_unavailable)}")

    # 5. Build machine-readable report.
    now_iso = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    report = {
        "schema": 2,
        "generated_at": now_iso,
        "overall": "healthy" if all_ok else "unhealthy",
        "exit_code": 0 if all_ok else 1,
        "min_prices": MIN_PRICES,
        "latest_db_reference": ref,
        "serving_latest": serving_latest,
        "stale": stale,
        "down": down,
        "count_unavailable": count_unavailable,
        "surfaces": surfaces_out,
        "table": "\n".join(lines),
    }

    # 6. Transition-gated history for the landing sparkline.  Append only
    # when the verdict state differs from the last recorded entry, and cap
    # at HISTORY_MAX.  Plain re-runs with unchanged verdicts do NOT append,
    # keeping the stable signature deterministic between runs.
    history = list(prev_history or [])[-HISTORY_MAX:]
    entry = {
        "generated_at": now_iso,
        "overall": report["overall"],
        "exit_code": report["exit_code"],
        "latest_db_reference": ref,
        "verdicts": {name: s["verdict"] for name, s in surfaces_out.items()},
    }
    if not history or _verdict_state_key(history[-1]) != _verdict_state_key(entry):
        history.append(entry)
    report["history"] = history[-HISTORY_MAX:]

    report["signature"] = _stable_signature(report)

    print("\n".join(lines))
    return all_ok, report


def main() -> int:
    parser = argparse.ArgumentParser(description="MandiIQ multi-surface health check")
    parser.add_argument("--json-out", default="docs/health-status.json",
                        help="path to write the machine-readable status JSON")
    parser.add_argument("--no-json", action="store_true",
                        help="do not write the JSON file (table only)")
    args = parser.parse_args()

    print("MandiIQ multi-surface health check — latest-DB parity")
    print(f"  min_prices={MIN_PRICES}, timeout={TIMEOUT_S}s")
    print()
    prev_history = _load_prev_history(args.json_out) if not args.no_json else []
    all_ok, report = run_check(prev_history=prev_history)
    print()
    print(f"  History: {len(report.get('history', []))}/{HISTORY_MAX} entries")
    print()
    if all_ok:
        print("All surfaces healthy — every reachable API serves the latest DB.")
    else:
        print("One or more surfaces stale or down!")

    if not args.no_json:
        try:
            with open(args.json_out, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2)
                f.write("\n")
            print(f"\nStatus JSON written to {args.json_out} (signature={report['signature']})")
        except OSError as e:
            print(f"\n::warning::Could not write status JSON to {args.json_out}: {e}")

    return report["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
