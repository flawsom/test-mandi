"""MandiIQ — Automated Data Integrity Check.

Runs every hour after ingestion to verify:
  1. DuckDB row counts grew (not stagnant or dropped)
  2. No NaN/Inf crept into forecast MAPEs
  3. RDD causal estimates are within expected bounds
  4. Alert if anything drifted

Results are written to mandi_rdd/data/last_integrity_check.json
for the dashboard auto-update strip to surface.
"""

from __future__ import annotations

import json
import logging
import math
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("mandi_rdd.data_integrity")

# ── Paths ──
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DATA_DIR = _PROJECT_ROOT / "mandi_rdd" / "data"
_INTEGRITY_OUT = _DATA_DIR / "last_integrity_check.json"
_HISTORY_OUT = _DATA_DIR / "_integrity_history.json"

# ── Thresholds ──
ROW_COUNT_DROP_THRESHOLD_PCT = 10.0   # Alert if row count drops more than 10%
RDD_EFFECT_MAX_ABS = 2_000.0           # Alert if |RDD effect| exceeds this (₹)
MAPE_MAX_FOR_VALID = 500.0             # Flag as "noisy" if MAPE > 500% (not an error)
MIN_COMMODITIES = 5                    # Alert if fewer than N commodities
MIN_DISTRICTS = 10                     # Alert if fewer than N districts
MAX_FUTURE_DAYS = 2                    # Alert if data date is more than N days in the future


class IntegrityResult:
    """Structured result of an integrity check run."""

    def __init__(self) -> None:
        self.ts: float = time.time()
        self.overall: str = "pass"
        self.checks: dict[str, Any] = {}
        self.alerts: list[str] = []
        self.summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_utc": datetime.fromtimestamp(self.ts, tz=timezone.utc).isoformat(),
            "overall": self.overall,
            "checks": self.checks,
            "alerts": self.alerts,
            "summary": self.summary,
        }

    def fail(self, check: str, message: str) -> None:
        self.checks[check] = {"status": "fail", "message": message}
        self.alerts.append(f"[FAIL] {check}: {message}")
        if self.overall == "pass":
            self.overall = "fail"

    def warn(self, check: str, message: str) -> None:
        self.checks[check] = {"status": "warn", "message": message}
        self.alerts.append(f"[WARN] {check}: {message}")
        if self.overall == "pass":
            self.overall = "warn"

    def ok(self, check: str, message: str) -> None:
        self.checks[check] = {"status": "ok", "message": message}


def run_integrity_checks(conn: Any, previous: dict[str, Any] | None = None) -> IntegrityResult:
    """Run all integrity checks against the live DuckDB connection.

    Args:
        conn: Open DuckDB connection (read-write or read-only).
        previous: Optional dict from a previous check (for row-count drift detection).

    Returns:
        IntegrityResult with per-check status, alerts list, and overall verdict.
    """
    result = IntegrityResult()

    # ── 1. Basic connectivity ──
    try:
        tables = conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='main'"
        ).fetchall()
        table_names = [t[0] for t in tables]
        result.ok("connectivity", f"Connected. Tables: {len(table_names)}")
    except Exception as e:
        result.fail("connectivity", f"Cannot query DuckDB schema: {e}")
        return result

    # ── 2. Row count integrity ──
    try:
        n_prices = conn.execute("SELECT COUNT(*) FROM prices").fetchone()[0]
        n_commodities = conn.execute(
            "SELECT COUNT(DISTINCT commodity) FROM prices"
        ).fetchone()[0]
        n_districts = conn.execute(
            "SELECT COUNT(DISTINCT district) FROM prices"
        ).fetchone()[0]
        n_states = conn.execute(
            "SELECT COUNT(DISTINCT state) FROM prices"
        ).fetchone()[0]

        # Check minimum thresholds
        if n_commodities < MIN_COMMODITIES:
            result.fail("min_commodities", f"Only {n_commodities} distinct commodities (min {MIN_COMMODITIES})")
        else:
            result.ok("min_commodities", f"{n_commodities} distinct commodities")

        if n_districts < MIN_DISTRICTS:
            result.fail("min_districts", f"Only {n_districts} distinct districts (min {MIN_DISTRICTS})")
        else:
            result.ok("min_districts", f"{n_districts} distinct districts")

        if n_prices == 0:
            result.fail("row_count", "prices table is empty")
        else:
            # Store raw n_prices in extras for drift detection next run
            result.ok("row_count", f"{n_prices:,} price rows across {n_commodities} commodities, {n_states} states")
            # Attach raw numeric value to the check result for the NEXT run's drift detection
            result.checks["row_count"]["extras"] = {"n_prices": n_prices}

        # Detect row-count drift from previous run.
        # Uses the raw n_prices value stored in the previous check's extras dict,
        # NOT regex parsing of the message string (which would silently break on
        # format changes).
        if previous and n_prices > 0:
            prev_extras = previous.get("checks", {}).get("row_count", {}).get("extras", {})
            prev_n = prev_extras.get("n_prices", 0)
            prev_runs = prev_extras.get("consecutive_stagnant_runs", 0)
            if prev_n > 0:
                drop_pct = (prev_n - n_prices) / prev_n * 100
                if drop_pct > ROW_COUNT_DROP_THRESHOLD_PCT:
                    result.fail("row_count_drift",
                        f"Row count dropped {drop_pct:.1f}% ({prev_n:,} -> {n_prices:,})")
                elif drop_pct > 0:
                    result.warn("row_count_drift",
                        f"Row count dropped {drop_pct:.1f}% ({prev_n:,} -> {n_prices:,})")
                elif drop_pct == 0:
                    # Stagnant: no new rows since last check
                    stagnant_runs = prev_runs + 1
                    # Persist the counter for the NEXT run's drift detection
                    result.checks["row_count"]["extras"]["consecutive_stagnant_runs"] = stagnant_runs
                    if stagnant_runs >= 3:
                        result.warn("row_count_drift",
                            f"Row count stagnant for {stagnant_runs} consecutive checks ({n_prices:,} rows, no change)")
                    else:
                        result.ok("row_count_drift",
                            f"Row count stable at {n_prices:,} (run {stagnant_runs}/3 before warning)")
                else:
                    result.ok("row_count_drift", f"Row count grew {abs(drop_pct):.1f}% ({prev_n:,} -> {n_prices:,})")
            else:
                result.ok("row_count_drift", f"Row count: {n_prices:,} (no previous data to compare)")

    except Exception as e:
        result.fail("row_count", f"Could not query row counts: {e}")

    # ── 3. Date sanity ──
    try:
        max_date = conn.execute("SELECT MAX(arrival_date) FROM prices").fetchone()[0]
        min_date = conn.execute("SELECT MIN(arrival_date) FROM prices").fetchone()[0]
        if min_date and max_date:
            from datetime import date
            today = date.today()
            future_limit = date(today.year, today.month, today.day)
            if isinstance(max_date, datetime):
                max_date_d = max_date.date()
            else:
                max_date_d = max_date
            if max_date_d > future_limit:
                days_future = (max_date_d - future_limit).days
                if days_future > MAX_FUTURE_DAYS:
                    result.fail("date_sanity",
                        f"Latest data date {max_date_d} is {days_future}d in the future")
                else:
                    result.ok("date_sanity", f"Data range: {min_date} → {max_date} (dates valid)")
            else:
                result.ok("date_sanity", f"Data range: {min_date} → {max_date} ({today - max_date_d} days old)")
        else:
            result.warn("date_sanity", "Could not determine date range (table may be empty)")
    except Exception as e:
        result.fail("date_sanity", f"Date sanity check failed: {e}")

    # ── 4. Forecast MAPE integrity ──
    try:
        fc_rows = conn.execute(
            """SELECT commodity, test_mape, is_valid
               FROM forecast_metrics
               ORDER BY computed_at DESC"""
        ).fetchall()
        if fc_rows:
            nan_count = 0
            inf_count = 0
            valid_count = 0
            noisy_commodities = []
            for r in fc_rows:
                mape = r[1]
                comm = r[0]
                valid_flag = r[2]
                if mape is None or (isinstance(mape, float) and math.isnan(mape)):
                    nan_count += 1
                elif isinstance(mape, float) and math.isinf(mape):
                    inf_count += 1
                elif valid_flag == 1 and mape > MAPE_MAX_FOR_VALID:
                    noisy_commodities.append(comm)
                elif valid_flag == 1:
                    valid_count += 1

            issues = []
            if nan_count > 0:
                issues.append(f"{nan_count} NaN MAPEs")
            if inf_count > 0:
                issues.append(f"{inf_count} Inf MAPEs")
            if noisy_commodities:
                issues.append(f"{len(noisy_commodities)} noisy (>{MAPE_MAX_FOR_VALID}%): {', '.join(noisy_commodities[:5])}")

            if nan_count > 0 or inf_count > 0:
                result.fail("forecast_mape", f"Invalid MAPEs: {', '.join(issues)}")
            elif noisy_commodities:
                result.warn("forecast_mape", f"No NaN/Inf. {valid_count} valid, {len(noisy_commodities)} noisy: {', '.join(noisy_commodities[:5])}")
            else:
                result.ok("forecast_mape", f"No NaN/Inf. All {valid_count} forecast MAPEs valid")
        else:
            result.warn("forecast_mape", "No forecast metrics recorded yet — skipping")
    except Exception as e:
        result.fail("forecast_mape", f"Could not query forecast metrics: {e}")

    # ── 5. RDD sanity bounds ──
    try:
        rdd_rows = conn.execute(
            """SELECT commodity, effect, p_value, fe_effect
               FROM rdd_results
               WHERE is_valid = 1
               ORDER BY computed_at DESC"""
        ).fetchall()
        if rdd_rows:
            out_of_bounds = []
            invalid_p = []
            for r in rdd_rows:
                comm, effect, p_val, fe = r[0], r[1], r[2], r[3]
                if effect is not None and abs(effect) > RDD_EFFECT_MAX_ABS:
                    out_of_bounds.append(f"{comm} (₹{effect:.0f})")
                if p_val is not None and (p_val < 0 or p_val > 1):
                    invalid_p.append(f"{comm} (p={p_val})")
                if fe is not None and (isinstance(fe, float) and (math.isnan(fe) or math.isinf(fe))):
                    invalid_p.append(f"{comm} FE NaN/Inf")

            if out_of_bounds:
                result.warn("rdd_sanity",
                    f"{len(out_of_bounds)} RDD effects exceed ±₹{RDD_EFFECT_MAX_ABS}: {', '.join(out_of_bounds)}")
            elif invalid_p:
                result.warn("rdd_sanity",
                    f"{len(invalid_p)} RDD results have invalid stats: {', '.join(invalid_p)}")
            else:
                result.ok("rdd_sanity",
                    f"All {len(rdd_rows)} RDD results within bounds and valid")
        else:
            result.warn("rdd_sanity", "No RDD results recorded yet")
    except Exception as e:
        result.fail("rdd_sanity", f"Could not query RDD results: {e}")

    # ── 6. Rainfall data check ──
    try:
        n_rainfall = conn.execute("SELECT COUNT(*) FROM rainfall").fetchone()[0]
        if n_rainfall > 0:
            n_subdivs = conn.execute(
                "SELECT COUNT(DISTINCT sub_division) FROM rainfall"
            ).fetchone()[0]
            min_rain_year = conn.execute(
                "SELECT MIN(year) FROM rainfall"
            ).fetchone()[0]
            max_rain_year = conn.execute(
                "SELECT MAX(year) FROM rainfall"
            ).fetchone()[0]
            result.ok("rainfall",
                f"{n_rainfall} records, {n_subdivs} sub-divisions, {min_rain_year}–{max_rain_year}")
        else:
            result.warn("rainfall", "No rainfall data recorded yet")
    except Exception as e:
        result.warn("rainfall", f"Could not query rainfall: {e}")

    # ── 7. NDVI data check (if table exists) ──
    if "ndvi" in table_names:
        try:
            n_ndvi = conn.execute("SELECT COUNT(*) FROM ndvi").fetchone()[0]
            if n_ndvi > 0:
                n_ndvi_districts = conn.execute(
                    "SELECT COUNT(DISTINCT district) FROM ndvi"
                ).fetchone()[0]
                result.ok("ndvi", f"{n_ndvi} records across {n_ndvi_districts} districts")
            else:
                result.ok("ndvi", "NDVI table exists but is empty (no credentials?)")
        except Exception as e:
            result.warn("ndvi", f"Could not query NDVI: {e}")

    # ── Build summary ──
    n_ok = sum(1 for v in result.checks.values() if v["status"] == "ok")
    n_warn = sum(1 for v in result.checks.values() if v["status"] == "warn")
    n_fail = sum(1 for v in result.checks.values() if v["status"] == "fail")
    if n_fail > 0:
        result.summary = f"{n_fail} check(s) FAILED, {n_warn} warning(s), {n_ok} passed"
    elif n_warn > 0:
        result.summary = f"All passed with {n_warn} warning(s), {n_ok} checks ok"
    else:
        result.summary = f"All {n_ok} checks passed"

    return result


def save_result(result: IntegrityResult, out_path: Path | None = None) -> None:
    """Write the integrity check result to a JSON status file."""
    path = out_path or _INTEGRITY_OUT
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(result.to_dict(), f, indent=2)
        logger.info(f"Integrity result written to {path}: {result.summary}")
    except Exception as e:
        logger.warning(f"Could not write integrity result: {e}")


def load_previous() -> dict[str, Any] | None:
    """Load the previous integrity check result, if it exists."""
    try:
        if _INTEGRITY_OUT.exists():
            with open(_INTEGRITY_OUT) as f:
                return json.load(f)
    except Exception:
        pass
    return None


def load_integrity_history() -> list[dict[str, Any]]:
    """Load the integrity check history (last N runs)."""
    try:
        if _HISTORY_OUT.exists():
            with open(_HISTORY_OUT) as f:
                return json.load(f)
    except Exception:
        pass
    return []


def save_to_history(result: IntegrityResult, max_history: int = 50) -> None:
    """Append current result to rolling history file."""
    history = load_integrity_history()
    history.append(result.to_dict())
    # Trim to max_history
    if len(history) > max_history:
        history = history[-max_history:]
    try:
        _HISTORY_OUT.parent.mkdir(parents=True, exist_ok=True)
        with open(_HISTORY_OUT, "w") as f:
            json.dump(history, f, indent=2)
    except Exception:
        pass
