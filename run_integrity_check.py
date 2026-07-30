#!/usr/bin/env python3
"""MandiIQ — Automated Data Integrity Check CLI.

Runs all integrity checks against the DuckDB and writes results
to mandi_rdd/data/last_integrity_check.json.

Usage:
    python run_integrity_check.py           # run checks, write JSON
    python run_integrity_check.py --verbose  # print detailed output
    python run_integrity_check.py --status   # show last result only

Exit codes:
    0 — all checks passed
    1 — warnings only
    2 — one or more checks failed
"""

import sys
import json
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Ensure stdout handles Unicode on cp1252 Windows consoles
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("mandi_rdd.integrity_cli")


def run():
    from mandi_rdd.storage.duckdb_store import get_connection
    from mandi_rdd.tests.data_integrity import (
        run_integrity_checks,
        save_result,
        load_previous,
        save_to_history,
    )

    verbose = "--verbose" in sys.argv
    status_only = "--status" in sys.argv

    if status_only:
        try:
            path = Path("mandi_rdd/data/last_integrity_check.json")
            if path.exists():
                with open(path) as f:
                    data = json.load(f)
                print(json.dumps(data, indent=2))
                sys.exit(0)
            else:
                print("No integrity check has been run yet.")
                sys.exit(0)
        except Exception as e:
            print(f"Could not read status: {e}")
            sys.exit(1)

    print("=" * 60)
    print("  MandiIQ — Data Integrity Check")
    print("=" * 60)

    conn = get_connection()
    try:
        previous = load_previous()
        result = run_integrity_checks(conn, previous=previous)

        # Save results
        save_result(result)
        save_to_history(result)

        # Print summary
        print()
        print(f"  Overall: {result.overall.upper()}")
        print(f"  Summary: {result.summary}")
        print()

        if verbose or result.alerts:
            if result.alerts:
                print("  Alerts:")
                for a in result.alerts:
                    print(f"    {a}")
                print()

            print("  Per-check details:")
            for name, check in result.checks.items():
                status = check["status"]
                icon = {"ok": "  [OK]", "warn": "  [!]", "fail": "  [X]"}.get(status, "  [?]")
                print(f"  {icon} {name}: {check['message']}")

            print()

        # Exit code
        if result.overall == "fail":
            sys.exit(2)
        elif result.overall == "warn":
            sys.exit(1)
        else:
            sys.exit(0)

    finally:
        conn.close()


if __name__ == "__main__":
    run()
