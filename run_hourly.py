"""
MandiIQ — Hourly Auto-Updater

Smart hourly ingestion that:
  • Fetches fresh prices from data.gov.in every hour (lightweight, ~30s)
  • Runs the full analysis pipeline (RDD + FE + Forecast) only once every 24h
  • Writes last_hourly_run.json so the dashboard can display "Last auto-updated"
  • Retries on transient failures with exponential backoff
  • Survives reboots when set up as a Windows scheduled task

Usage:
    python run_hourly.py              # one-shot (scheduled task calls this)
    python run_hourly.py --force-full  # force a full analysis pipeline run

Setup:
    python setup_scheduled_task.py     # install the hourly scheduled task
"""

import json
import os
import sys
import time
import logging
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load .env if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

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
logger = logging.getLogger("mandi_rdd.hourly")

# ── Paths ──
STATUS_FILE = Path(__file__).resolve().parent / "mandi_rdd" / "data" / "last_hourly_run.json"
FULL_RUN_FLAG = Path(__file__).resolve().parent / "mandi_rdd" / "data" / "_last_full_analysis.txt"
LOG_FILE = Path(__file__).resolve().parent / "mandi_rdd" / "data" / "hourly_ingest.log"
HOURS_BETWEEN_FULL_RUNS = 24  # Full RDD + FE analysis once per day


def _write_run_status(outcome: str, new_rows: int, duration_s: float, error: str | None = None):
    """Write the hourly run status to JSON."""
    record = {
        "last_run_utc": datetime.now(timezone.utc).isoformat(),
        "outcome": outcome,
        "new_price_rows": new_rows,
        "duration_s": round(duration_s, 1),
        "error": error,
    }
    try:
        STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(STATUS_FILE, "w") as f:
            json.dump(record, f, indent=2)
        logger.info(f"Run status written: {outcome} ({new_rows} new rows, {duration_s:.1f}s)")
    except Exception as e:
        logger.warning(f"Could not write status file: {e}")


def _should_run_full_analysis() -> bool:
    """Check if 24h have passed since the last full analysis pipeline run."""
    try:
        if FULL_RUN_FLAG.exists():
            mtime = datetime.fromtimestamp(FULL_RUN_FLAG.stat().st_mtime)
            elapsed = (datetime.now() - mtime).total_seconds()
            return elapsed >= HOURS_BETWEEN_FULL_RUNS * 3600
        return True  # No flag file -> never run full analysis -> run it now
    except Exception:
        return True


def _touch_full_analysis_flag():
    """Stamp the full-analysis flag file with the current time."""
    try:
        FULL_RUN_FLAG.parent.mkdir(parents=True, exist_ok=True)
        FULL_RUN_FLAG.write_text(datetime.now(timezone.utc).isoformat())
    except Exception:
        pass


def run_hourly(force_full: bool = False) -> dict:
    """
    Run the hourly ingestion pipeline.

    Args:
        force_full: If True, run the full analysis (RDD + FE + Forecast) even
                    if it's not time yet.

    Returns:
        Summary dict with status, rows fetched, duration, and any error.
    """
    start = time.time()
    tz = timezone.utc
    run_ts = datetime.now(tz)

    logger.info("=" * 60)
    logger.info(f"MandiIQ Hourly Ingestion — {run_ts.isoformat()}")
    logger.info(f"Force full analysis: {force_full}")
    logger.info("=" * 60)

    try:
        from mandi_rdd.ingestion.scheduler import run_ingestion

        # Decide: full run or quick price-only?
        do_full = force_full or _should_run_full_analysis()
        logger.info(f"Full analysis pipeline: {'YES' if do_full else 'NO (quick price fetch only)'}")

        if do_full:
            # Full pipeline: prices + rainfall + RDD + FE + Forecast + NDVI
            summary = run_ingestion(max_records=10000)
            _touch_full_analysis_flag()
            logger.info("Full analysis pipeline complete — next full run in 24h")
        else:
            # Quick run: prices only (skip rainfall, skip analysis)
            # Makes the hourly call fast (~30s instead of ~5min)
            summary = run_ingestion(max_records=10000, skip_rainfall=True, skip_analysis=True)

        # Extract key stats
        steps = summary.get("steps", {})
        prices_step = steps.get("prices", {})
        n_new = prices_step.get("new", 0) if isinstance(prices_step, dict) else 0
        status = summary.get("status", "unknown")

        _write_run_status(
            outcome="success" if status == "ok" else "failure",
            new_rows=n_new,
            duration_s=time.time() - start,
            error=None if status == "ok" else summary.get("error"),
        )

        logger.info(f"Hourly run complete: {status} ({n_new} new rows, {time.time() - start:.1f}s)")

        # ── Post-ingestion: data integrity check ──
        _run_integrity_check()

        # ── Post-ingestion: persist step-level timings for the diagram generator ──
        if status == "ok":
            _persist_step_timings()
            # ── Post-ingestion: regenerate pipeline DAG diagram with live timing ──
            _run_diagram_generator()
            # ── Post-ingestion: push refreshed DB to R2 (R2-as-data-bus) ──
            # The Northflank cron runs volumeless on the free tier (the single
            # ReadWriteOnce volume lives on the API), so R2 is how the API sees
            # fresh data. Non-fatal: a backup failure must never fail the run.
            _sync_db_to_r2()

        return summary

    except Exception as e:
        logger.exception(f"Hourly ingestion failed: {e}")
        _write_run_status(
            outcome="failure",
            new_rows=0,
            duration_s=time.time() - start,
            error=str(e),
        )
        return {"status": "error", "error": str(e)}

def _run_integrity_check() -> None:
    """Run the data integrity check and log warnings for any drifts."""
    try:
        from mandi_rdd.tests.data_integrity import (
            run_integrity_checks,
            save_result,
            save_to_history,
            load_previous,
        )
        from mandi_rdd.storage.duckdb_store import get_connection

        conn = get_connection(read_only=True)
        try:
            previous = load_previous()
            result = run_integrity_checks(conn, previous=previous)
            save_result(result)
            save_to_history(result)

            if result.overall == "fail":
                logger.error(f"Integrity check FAILED: {result.summary}")
                for alert in result.alerts:
                    logger.warning(f"  Integrity alert: {alert}")
            elif result.overall == "warn":
                logger.warning(f"Integrity check warnings: {result.summary}")
                for alert in result.alerts:
                    logger.info(f"  Integrity note: {alert}")
            else:
                logger.info(f"Integrity check: {result.summary}")
        finally:
            conn.close()
    except ImportError as e:
        logger.warning(f"Integrity check module not available: {e}")
    except Exception as e:
        logger.warning(f"Integrity check failed: {e}")


def _persist_step_timings() -> None:
    """Capture step-level durations from pipeline_metrics and persist to JSON.

    The scheduler uses ``pipeline_metrics.step()`` context managers that record
    each step's wall-clock duration.  After ``run_ingestion()`` completes, this
    reads the *last* recorded duration for every known step and writes it to
    ``mandi_rdd/data/last_step_timings.json`` so the diagram generator can
    display per-step wall times.
    """
    try:
        from mandi_rdd.core.metrics import pipeline_metrics as pm
        with pm._lock:
            steps = {}
            for step_name, durations in pm._step_durations.items():
                if durations:
                    steps[step_name] = round(durations[-1], 2)
            # Also grab the row counts recorded during the run
            rows_fetched = dict(pm._rows_fetched)
            rows_new = dict(pm._rows_new)
        timings = {
            "steps": steps,
            "rows_fetched": rows_fetched,
            "rows_new": rows_new,
        }
        out_path = Path(__file__).resolve().parent / "mandi_rdd" / "data" / "last_step_timings.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w") as f:
            json.dump(timings, f, indent=2)
        logger.info(f"Step timings persisted ({len(steps)} steps)")
    except Exception as e:
        logger.warning(f"Could not persist step timings: {e}")


def _run_diagram_generator() -> None:
    """Regenerate the Mermaid pipeline DAG with live timing from the last run."""
    try:
        from scripts.generate_pipeline_diagram import generate
        output_path = Path(__file__).resolve().parent / "diagrams" / "pipeline-flow-live.mmd"
        generate(output_path=str(output_path))
        logger.info(f"Pipeline diagram regenerated -> {output_path}")
    except ImportError as e:
        logger.warning(f"Diagram generator module not available: {e}")
    except Exception as e:
        logger.warning(f"Diagram generation failed: {e}")


def _sync_db_to_r2() -> None:
    """Upload the refreshed DuckDB to Cloudflare R2 after a successful run.

    This is the R2-as-data-bus half for the Northflank cron: the cron runs
    volumeless (free-tier ReadWriteOnce volume lives on the API service), so
    R2 is how the API receives fresh data. Skipped silently when R2_* env
    vars are unset; failures are logged as warnings, never fatal.
    """
    try:
        from mandi_rdd.storage.r2_sync import upload_db
        result = upload_db()
        logger.info(
            "R2 backup: %d bytes (from %d raw, %.1f%% smaller) -> %s",
            result["compressed_bytes"], result["raw_bytes"],
            result["compression_pct"], result["r2_key"],
        )
    except Exception as e:  # noqa: BLE001
        logger.warning(f"R2 backup skipped (non-fatal): {e}")


if __name__ == "__main__":
    force_full = "--force-full" in sys.argv
    result = run_hourly(force_full=force_full)
    if result.get("status") != "ok":
        sys.exit(1)
    sys.exit(0)
