"""RDD parity gate — Vercel (lightweight) vs Northflank (full scipy).

Curls /robustness/{commodity} on both surfaces for ~10 high-volume
commodities and compares the main_effect point estimates.  The two
engines share the identical numpy WLS/HC2 math, so their effect sizes
must agree to far better than 1% — a divergence means one surface is
serving a different DB or a broken engine.

Semantics:
  - PASS        both surfaces return an effect and rel_diff <= threshold
  - FAIL        effects diverge beyond threshold AND the absolute gap
                exceeds --abs-floor (guards near-zero effects where a
                tiny absolute gap looks like a huge relative one)
  - SKIP        BOTH surfaces return no effect (agreement — thin panel
                on both sides is not a parity failure)
  - NO-EFFECT   only ONE surface has an effect (drift — a real failure)
  - ERROR       a probe failed (HTTP error / non-JSON / timeout), retried
                for transient 5xx before being counted as failure

Exit codes:
    0 — every commodity passes (or is skipped)
    1 — one or more commodities FAIL / NO-EFFECT / ERROR

Stdlib-only so it runs on the ubuntu runner with no pip install.

Usage:
    python scripts/check_rdd_parity.py [--threshold 0.01] [--abs-floor 0.5] [--json-out PATH]
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

SURFACES = {
    "Vercel": "https://test-mandi.vercel.app",
    "Northflank": "https://p01--mandiiq--zbvjrztgjqgw.code.run",
}

# High-volume, rain-sensitive commodities with enough panel data for a
# stable RDD.  Kept to ~10 so a parity run stays well under CI timeouts
# (each /robustness call re-computes the full RDD, ~1-3 s warm).
COMMODITIES = [
    "Wheat",
    "Onion",
    "Brinjal",
    "Green Chilli",
    "Mustard",
    "Cauliflower",
    "Cabbage",
    "Soyabean",
    "Ginger(Green)",
    "Apple",
]

TIMEOUT_S = 120          # cold starts on Vercel may take ~35s for the R2 download
MAX_ATTEMPTS = 3         # transient 5xx (502/503/504) retries before ERROR
RETRY_WAIT_S = 5


def _fetch_effect(base: str, commodity: str, timeout: int = TIMEOUT_S) -> dict:
    """Fetch /robustness/{commodity}, retrying transient 5xx.

    Returns {effect, p_value, http_status, error}.
    """
    url = base + "/robustness/" + urllib.parse.quote(commodity, safe="")
    result = {"effect": None, "p_value": None, "http_status": None, "error": None}

    for attempt in range(1, MAX_ATTEMPTS + 1):
        req = urllib.request.Request(url, headers={"User-Agent": "MandiIQ/rdd-parity"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                result["http_status"] = resp.status
                body = resp.read().decode("utf-8", errors="replace")
            break
        except urllib.error.HTTPError as e:
            result["http_status"] = e.code
            if e.code in (502, 503, 504) and attempt < MAX_ATTEMPTS:
                time.sleep(RETRY_WAIT_S * attempt)
                continue
            result["error"] = f"HTTP {e.code}: {e.reason}"
            return result
        except urllib.error.URLError as e:
            result["error"] = f"URLError: {e.reason}"
            return result
        except OSError as e:
            result["error"] = f"OSError: {e}"
            return result

    try:
        data = json.loads(body)
    except (json.JSONDecodeError, ValueError):
        result["error"] = f"HTTP 200 but non-JSON body ({len(body)} bytes)"
        return result

    result["effect"] = data.get("main_effect")
    result["p_value"] = data.get("p_value")
    if result["effect"] is None and data.get("detail"):
        result["error"] = str(data["detail"])[:200]
    return result


def _rel_diff(a: float, b: float) -> float:
    """Symmetric relative difference: |a-b| / max(|a|,|b|, eps)."""
    denom = max(abs(a), abs(b), 1e-9)
    return abs(a - b) / denom


def run_check(threshold: float, abs_floor: float) -> tuple[bool, dict]:
    """Run the parity check across all commodities.  Returns (all_ok, report)."""
    all_ok = True
    rows = []
    for commodity in COMMODITIES:
        v = _fetch_effect(SURFACES["Vercel"], commodity)
        n = _fetch_effect(SURFACES["Northflank"], commodity)

        row = {
            "commodity": commodity,
            "vercel_effect": v["effect"],
            "vercel_p_value": v["p_value"],
            "vercel_error": v["error"],
            "northflank_effect": n["effect"],
            "northflank_p_value": n["p_value"],
            "northflank_error": n["error"],
            "rel_diff": None,
            "abs_diff": None,
            "verdict": None,
            "note": "",
        }

        if v["error"]:
            row["verdict"] = "ERROR"
            row["note"] = f"Vercel: {v['error']}"
            all_ok = False
        elif n["error"]:
            row["verdict"] = "ERROR"
            row["note"] = f"Northflank: {n['error']}"
            all_ok = False
        elif v["effect"] is None and n["effect"] is None:
            # Both surfaces agree there is no estimable effect (thin panel
            # on both sides) — that is parity, not a failure.
            row["verdict"] = "SKIP"
            row["note"] = "no effect on either surface (agreement)"
        elif v["effect"] is None or n["effect"] is None:
            # One surface has an effect, the other doesn't — real drift.
            row["verdict"] = "NO-EFFECT"
            row["note"] = "effect missing on one surface only"
            all_ok = False
        else:
            diff = _rel_diff(v["effect"], n["effect"])
            abs_diff = abs(v["effect"] - n["effect"])
            row["rel_diff"] = round(diff, 6)
            row["abs_diff"] = round(abs_diff, 4)
            if diff <= threshold or abs_diff <= abs_floor:
                # Within the relative threshold, OR the absolute gap is
                # below the floor (near-zero effects: 2.77 vs 2.80 is 1.07%
                # relative but only ₹0.03 — noise, not drift).
                row["verdict"] = "PASS"
            else:
                row["verdict"] = "FAIL"
                row["note"] = (
                    f"rel_diff {diff*100:.3f}% > {threshold*100:.1f}% and "
                    f"abs_diff Rs.{abs_diff:.2f} > Rs.{abs_floor:.2f} "
                    f"(vercel={v['effect']:.4f}, northflank={n['effect']:.4f})"
                )
                all_ok = False

        rows.append(row)

    # Human table
    lines = []
    lines.append(f"  {'Commodity':<16} | {'Verdict':<9} | {'Vercel':>10} | {'Northflank':>10} | {'RelDiff':>8} | Notes")
    lines.append("  " + "-" * 16 + "-+-" + "-" * 9 + "-+-" + "-" * 10 + "-+-" + "-" * 10 + "-+-" + "-" * 8 + "-+-" + "-" * 50)
    for r in rows:
        v = f"{r['vercel_effect']:.4f}" if r["vercel_effect"] is not None else "-"
        n = f"{r['northflank_effect']:.4f}" if r["northflank_effect"] is not None else "-"
        d = f"{r['rel_diff']*100:.3f}%" if r["rel_diff"] is not None else "-"
        lines.append(f"  {r['commodity']:<16} | {r['verdict']:<9} | {v:>10} | {n:>10} | {d:>8} | {r['note']}")
    print("\n".join(lines))

    report = {
        "schema": 1,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "threshold": threshold,
        "abs_floor": abs_floor,
        "overall": "parity-ok" if all_ok else "parity-mismatch",
        "exit_code": 0 if all_ok else 1,
        "commodities": rows,
    }
    return all_ok, report


def main() -> int:
    parser = argparse.ArgumentParser(description="MandiIQ RDD parity gate")
    parser.add_argument("--threshold", type=float, default=0.01,
                        help="max relative difference in main_effect (default 0.01 = 1%%)")
    parser.add_argument("--abs-floor", type=float, default=0.5,
                        help="absolute gap (in INR) below which divergence is treated as noise (default 0.5)")
    parser.add_argument("--json-out", default=None,
                        help="optional path to write the machine-readable parity JSON")
    parser.add_argument("--no-json", action="store_true", help="table only")
    args = parser.parse_args()

    # ASCII-only output: the em dash and rupee glyphs crash on cp1252
    # consoles (Windows), even though the ubuntu runner is UTF-8.
    print("MandiIQ RDD parity gate - Vercel (lightweight) vs Northflank (full scipy)")
    print(f"  threshold={args.threshold*100:.1f}%  abs_floor=Rs.{args.abs_floor:.2f}  "
          f"commodities={len(COMMODITIES)}  timeout={TIMEOUT_S}s")
    print()
    all_ok, report = run_check(args.threshold, args.abs_floor)
    print()
    if all_ok:
        print("All commodities in parity - effect sizes agree across surfaces.")
    else:
        print("Parity mismatch detected - one or more surfaces diverge!")

    if not args.no_json and args.json_out:
        try:
            with open(args.json_out, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2)
                f.write("\n")
            print(f"\nParity JSON written to {args.json_out}")
        except OSError as e:
            print(f"\n::warning::Could not write parity JSON to {args.json_out}: {e}")

    return report["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
