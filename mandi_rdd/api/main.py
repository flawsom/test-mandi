"""
MandiRDD — FastAPI serving layer.

Endpoints:
- GET /health — liveness check
- GET /prices — query stored prices with filters
- GET /rdd-result/{commodity} — latest RDD estimate
- GET /rdd-plot/{commodity} — binned scatter plot data
- GET /robustness/{commodity} — robustness check bundle
- GET /forecast/{commodity} — Prophet forecast
- GET /risk-score/{commodity} — XGBoost risk score
- GET /recommendation/{commodity} — procurement recommendation
- POST /ask — AI orchestrator (OpenRouter multi-model routing)
- POST /refresh — manual pipeline re-run
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
import os
import json
import logging
import time

import hashlib
import gzip
import shutil
import hmac
import datetime
import urllib.error
import urllib.request
from typing import Optional
from contextlib import asynccontextmanager

import uvicorn
import threading
import duckdb
import re
from fastapi import FastAPI, Header, HTTPException, Query, Request, Response, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from mandi_rdd.storage.duckdb_store import (
    get_connection,
    init_schema,
    get_prices,
    get_latest_rdd,
    get_monthly_avg_prices,
)
from mandi_rdd.ai.router import (
    clear_cool_down,
    get_llm_fallback_count,
    reset_llm_fallback_count,
)
from mandi_rdd.api import metrics_push
from mandi_rdd.api.svg_compositor import composite_kpi_svg as _composite_kpi_svg

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ── Pydantic schemas ──

class HealthResponse(BaseModel):
    status: str
    llm_fallback_count: int = 0
    n_prices: int
    n_commodities: int
    n_states: int
    n_districts: int
    n_rainfall: int
    n_rainfall_filtered: int
    rainfall_below_threshold: int
    n_rdd_results: int
    n_ndvi: Optional[int] = None
    n_ndvi_districts: Optional[int] = None
    n_tests: int = 71
    last_run_utc: Optional[str] = None
    last_outcome: Optional[str] = None
    commodities_analyzed: list[str]
    # ── Hourly ingestion status (from last_hourly_run.json) ──
    last_hourly_run_utc: Optional[str] = None
    last_hourly_outcome: Optional[str] = None
    last_hourly_new_rows: Optional[int] = None
    last_hourly_duration_s: Optional[float] = None
    # ── Forecast model status ──
    n_forecast_models: int = 0
    n_forecast_valid: int = 0
    forecast_avg_mape: Optional[float] = None
    forecast_commodities: list[dict] = []


class PriceRecord(BaseModel):
    state: str
    district: str
    market: str
    commodity: str
    variety: Optional[str] = None
    arrival_date: str
    modal_price: Optional[float] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None


class RDDResult(BaseModel):
    commodity: str
    effect: Optional[float]
    p_value: Optional[float]
    std_error: Optional[float]
    n_left: Optional[int]
    n_right: Optional[int]
    interpretation: Optional[str]
    error: Optional[str]


class RDDPlotData(BaseModel):
    raw_x: list
    raw_y: list
    bin_centers: list
    bin_means: list
    bin_stds: list
    left_x: list
    left_y: list
    right_x: list
    right_y: list
    cutoff: float


class ForecastResponse(BaseModel):
    commodity: str
    forecast: list
    metrics: dict
    n_training_months: int


class RefreshResponse(BaseModel):
    status: str
    message: str
    duration_seconds: Optional[float] = None


# ── Phase 11: AI Orchestrator schemas ──

class AskRequest(BaseModel):
    query: str
    commodity: Optional[str] = None
    district: Optional[str] = None


class AskResponse(BaseModel):
    query: str
    commodity: str
    district: str
    answer: str
    model_used: Optional[str] = None
    endpoints_used: list[str] = []
    error: Optional[str] = None


# ── App state ──

class HealthStats:
    """Simple state for /metrics endpoint tracking."""
    def __init__(self):
        self.start_time = time.time()
        self.health_count = 0
        self.cold_start = 1  # resets on each server start
health_stats = HealthStats()
# ── Deploy endpoint state ──
_last_deploy_ts: float = 0.0
_DEPLOY_COOLDOWN_S: float = 60.0
# Load Grafana dashboard template
_dashboard_path = os.path.join(os.path.dirname(__file__), "..", "..", "dashboards", "mandiiq-pipeline.json")
_dashboard_path = os.path.abspath(_dashboard_path)
if os.path.exists(_dashboard_path):
    with open(_dashboard_path, "r") as f: _raw = json.load(f)
    dashboard_json = _raw.get("dashboard", _raw)
    _dashboard_export = _raw
else:
    dashboard_json = None
    _dashboard_export = None
_dashboard_last_refresh: float = 0.0
_dashboard_file_mtime: float = 0.0

class AppState:
    def __init__(self):
        self.commodities = []


state = AppState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load state on startup."""
    logger.info("Starting MandiRDD API...")
    conn = get_connection()
    init_schema(conn)
    
    # Check data freshness and auto-trigger pipeline if needed
    try:
        df = conn.execute("SELECT DISTINCT commodity FROM prices ORDER BY commodity").fetchdf()
        state.commodities = df["commodity"].tolist() if len(df) > 0 else []
        n_prices = conn.execute("SELECT COUNT(*) FROM prices").fetchone()[0]
        n_rainfall = conn.execute("SELECT COUNT(*) FROM rainfall").fetchone()[0]
        n_rdd = conn.execute("SELECT COUNT(*) FROM rdd_results").fetchone()[0]
        
        logger.info(f"Startup data check: {n_prices} prices, {n_rainfall} rainfall, {n_rdd} RDD results")

        # ── R2-as-data-bus: on a fresh/empty volume, restore the last-known-good ──
        # DuckDB from Cloudflare R2 instead of re-ingesting from scratch.
        if n_prices < 100:
            try:
                from mandi_rdd.storage.r2_sync import restore_db
                logger.info("DB is empty — attempting restore from R2 backup...")
                conn.close()  # release the DB file lock (Windows) before replacing it
                result = restore_db()
                logger.info(
                    "R2 restore: %d bytes -> %s",
                    result["bytes_decompressed"], result["db_path"],
                )
                conn = get_connection()
                init_schema(conn)
                df = conn.execute("SELECT DISTINCT commodity FROM prices ORDER BY commodity").fetchdf()
                state.commodities = df["commodity"].tolist() if len(df) > 0 else []
                n_prices = conn.execute("SELECT COUNT(*) FROM prices").fetchone()[0]
                n_rainfall = conn.execute("SELECT COUNT(*) FROM rainfall").fetchone()[0]
                n_rdd = conn.execute("SELECT COUNT(*) FROM rdd_results").fetchone()[0]
                logger.info(
                    "After R2 restore: %d prices, %d rainfall, %d RDD results",
                    n_prices, n_rainfall, n_rdd,
                )
            except Exception as e:
                logger.warning(f"R2 restore skipped (non-fatal): {e}")
                try:
                    conn = get_connection()
                    init_schema(conn)
                except Exception:
                    pass

        
        # Auto-trigger pipeline if data is missing or stale
        if n_prices < 100 or n_rainfall < 10 or n_rdd < 1:
            logger.warning("Data is stale or missing - triggering auto-pipeline in background...")
            
            def _auto_pipeline():
                import time as _t
                _start = _t.time()
                try:
                    from mandi_rdd.ingestion.scheduler import run_ingestion
                    logger.info("Auto-pipeline starting...")
                    summary = run_ingestion()
                    duration = round(_t.time() - _start, 1)
                    logger.info(f"Auto-pipeline finished in {duration}s: {summary.get('status')}")
                except Exception as e:
                    logger.error(f"Auto-pipeline failed: {e}")
            
            threading.Thread(target=_auto_pipeline, daemon=True).start()
    except Exception:
        state.commodities = []
    
    conn.close()
    metrics_push.start_push_thread()
    # Warm the in-memory dashboard cache so heartbeat shows Fresh on boot
    global _dashboard_last_refresh, _dashboard_file_mtime
    if dashboard_json is not None:
        _dashboard_last_refresh = time.time()
        _dashboard_file_mtime = os.path.getmtime(_dashboard_path)
        _get_patched_dashboard("Grafana")
        logger.info("Dashboard cache warmed: %d entries", _dashboard_patch_count)
    
    # Start hourly auto-refresh scheduler
    def _hourly_refresh():
        """Run pipeline every hour to keep data fresh."""
        import time as _t
        while True:
            _t.sleep(3600)  # 1 hour
            try:
                from mandi_rdd.ingestion.scheduler import run_ingestion
                logger.info("Hourly auto-refresh starting...")
                summary = run_ingestion()
                logger.info(f"Hourly auto-refresh finished: {summary.get('status')}")
            except Exception as e:
                logger.error(f"Hourly auto-refresh failed: {e}")
    
    threading.Thread(target=_hourly_refresh, daemon=True).start()
    logger.info("Hourly auto-refresh scheduler started")

    # Pre-render the pipeline SVG so cold-start requests don't wait for mmdc
    try:
        logger.info("Pre-rendering pipeline SVG...")
        _render_pipeline_svg(force=True)
        logger.info("Pipeline SVG pre-rendered successfully")
    except Exception as e:
        logger.warning(f"Pipeline SVG pre-render failed (non-fatal): {e}")

    yield


app = FastAPI(
    title="MandiRDD API",
    description="""
    Automated Mandi Price Discontinuity Engine.
    
    Pulls daily mandi prices from data.gov.in, joins with rainfall
    departure data, and runs a Regression Discontinuity Design (RDD)
    to detect price jumps around the -19% rainfall deficiency threshold.
    
    **Endpoints:**
    * `/health` — Liveness check + data counts
    * `/prices` — Query stored prices by state/district/commodity
    * `/rdd-result/{commodity}` — Latest RDD estimate for a commodity
    * `/rdd-plot/{commodity}` — Binned scatter data for the discontinuity plot
    * `/robustness/{commodity}` — Full robustness check bundle
    * `/forecast/{commodity}` — Prophet forecast with optional LSTM comparison
    * `/risk-score/{commodity}` — XGBoost price-spike risk probability
    * `/recommendation/{commodity}` — Procurement recommendation
    * `/ask` — AI orchestrator (OpenRouter multi-model routing, circuit-breaker fallback)
    * `/refresh` — Manual re-run of the full pipeline
    """,
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount docs directory for static file serving (same-origin for live data fetches)
_docs_path = Path(__file__).resolve().parent.parent.parent / "docs"
if _docs_path.exists():
    app.mount("/docs", StaticFiles(directory=str(_docs_path), html=True), name="docs")
    logger.info(f"Static docs mounted at /docs from {_docs_path}")


# ── Endpoints ──

@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health():
    health_stats.health_count += 1
    """Liveness check with full data counts for the documentation page."""
    conn = get_connection()
    init_schema(conn)

    n_prices = conn.execute("SELECT COUNT(*) FROM prices").fetchone()[0]
    n_commodities = conn.execute("SELECT COUNT(DISTINCT commodity) FROM prices").fetchone()[0]
    n_states = conn.execute("SELECT COUNT(DISTINCT state) FROM prices").fetchone()[0]
    n_districts = conn.execute("SELECT COUNT(DISTINCT district) FROM prices").fetchone()[0]
    n_rainfall = conn.execute("SELECT COUNT(*) FROM rainfall").fetchone()[0]
    n_rainfall_filtered = conn.execute(
        "SELECT COUNT(*) FROM rainfall WHERE departure_pct BETWEEN -100 AND 200"
    ).fetchone()[0]
    rainfall_below = conn.execute(
        "SELECT COUNT(*) FROM rainfall WHERE departure_pct < -19"
    ).fetchone()[0]
    n_rdd = conn.execute("SELECT COUNT(*) FROM rdd_results").fetchone()[0]

    n_ndvi = None
    n_ndvi_districts = None
    try:
        n_ndvi = conn.execute("SELECT COUNT(*) FROM ndvi").fetchone()[0]
        n_ndvi_districts = conn.execute(
            "SELECT COUNT(DISTINCT district) FROM ndvi"
        ).fetchone()[0]
    except Exception:
        pass

    # Read last ingest status (from full pipeline runs)
    last_run_utc = None
    last_outcome = None
    try:
        status_path = (
            Path(__file__).resolve().parent.parent / "data" / "last_ingest_status.json"
        )
        if status_path.exists():
            with open(status_path) as f:
                record = json.load(f)
            last_run_utc = record.get("last_run_utc")
            last_outcome = record.get("outcome")
    except Exception:
        pass

    # ── Read hourly ingestion status (from run_hourly.py) ──
    last_hourly_run_utc = None
    last_hourly_outcome = None
    last_hourly_new_rows = None
    last_hourly_duration_s = None
    try:
        hourly_path = (
            Path(__file__).resolve().parent.parent / "data" / "last_hourly_run.json"
        )
        if hourly_path.exists():
            with open(hourly_path) as f:
                hrec = json.load(f)
            last_hourly_run_utc = hrec.get("last_run_utc")
            last_hourly_outcome = hrec.get("outcome")
            last_hourly_new_rows = hrec.get("new_price_rows")
            last_hourly_duration_s = hrec.get("duration_s")
    except Exception:
        pass

    # ── Forecast model status ──
    n_forecast_models = 0
    n_forecast_valid = 0
    forecast_avg_mape = None
    forecast_commodities = []
    try:
        fc_rows = conn.execute(
            """SELECT commodity, computed_at, model, test_mape, test_mae,
                      test_rmse, n_training_months, n_test_months, is_valid
               FROM forecast_metrics
               ORDER BY computed_at DESC"""
        ).fetchall()
        n_forecast_models = len(fc_rows)
        valid_map = [r[3] for r in fc_rows if r[3] is not None and r[8] == 1]
        n_forecast_valid = len(valid_map)
        if valid_map:
            forecast_avg_mape = round(sum(valid_map) / len(valid_map), 2)
        forecast_commodities = [
            {
                "commodity": r[0],
                "computed_at": str(r[1]) if r[1] else None,
                "model": r[2] or "unknown",
                "test_mape": r[3],
                "n_training_months": r[6],
                "is_valid": bool(r[8]),
            }
            for r in fc_rows[:20]  # top 20 most recent
        ]
    except Exception as e:
        logger.warning(f"Could not query forecast_metrics: {e}")

    conn.close()

    return HealthResponse(
        status="healthy",
        llm_fallback_count=get_llm_fallback_count(),
        n_prices=n_prices,
        n_commodities=n_commodities,
        n_states=n_states,
        n_districts=n_districts,
        n_rainfall=n_rainfall,
        n_rainfall_filtered=n_rainfall_filtered,
        rainfall_below_threshold=rainfall_below,
        n_rdd_results=n_rdd,
        n_ndvi=n_ndvi,
        n_ndvi_districts=n_ndvi_districts,
        n_tests=71,
        last_run_utc=last_run_utc,
        last_outcome=last_outcome,
        commodities_analyzed=state.commodities[:20],
        last_hourly_run_utc=last_hourly_run_utc,
        last_hourly_outcome=last_hourly_outcome,
        last_hourly_new_rows=last_hourly_new_rows,
        last_hourly_duration_s=last_hourly_duration_s,
        n_forecast_models=n_forecast_models,
        n_forecast_valid=n_forecast_valid,
        forecast_avg_mape=forecast_avg_mape,
        forecast_commodities=forecast_commodities,
    )


@app.get("/freshness", tags=["System"])
async def freshness(commodity: Optional[str] = None):
    """Per-commodity data freshness: latest date, row count, district coverage."""
    conn = get_connection()
    init_schema(conn)
    try:
        where = ""
        params = []
        if commodity:
            where = "WHERE LOWER(commodity) = LOWER(?)"
            params = [commodity]
        rows = conn.execute(f"""
            SELECT
                commodity,
                MAX(arrival_date) AS latest_date,
                MIN(arrival_date) AS earliest_date,
                COUNT(*) AS row_count,
                COUNT(DISTINCT district) AS n_districts,
                COUNT(DISTINCT state) AS n_states
            FROM prices
            {where}
            GROUP BY commodity
            ORDER BY latest_date DESC
            LIMIT 200
        """, params).fetchall()
        records = []
        cols = ["commodity", "latest_date", "earliest_date", "row_count", "n_districts", "n_states"]
        for r in rows:
            rec = dict(zip(cols, r))
            rec["source_type"] = "prices_table"
            rec["source_name"] = ""
            rec["updated_at"] = None
            records.append(rec)
        return records
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@app.get("/prices", response_model=list[PriceRecord], tags=["Data"])
async def prices(
    state: Optional[str] = Query(None),
    district: Optional[str] = Query(None),
    commodity: Optional[str] = Query(None),
    limit: int = Query(100, le=5000),
):
    """Query stored prices with optional filters."""
    conn = get_connection()
    init_schema(conn)
    
    df = get_prices(conn, state=state, district=district, commodity=commodity, limit=limit)
    conn.close()
    
    records = df.to_dict("records")
    for r in records:
        ad = r.get("arrival_date")
        if ad is not None and hasattr(ad, "strftime"):
            r["arrival_date"] = ad.strftime("%Y-%m-%d")
    return [
        PriceRecord(
            state=r["state"],
            district=r["district"],
            market=r["market"],
            commodity=r["commodity"],
            variety=r.get("variety"),
            arrival_date=r["arrival_date"],
            modal_price=r.get("modal_price"),
            min_price=r.get("min_price"),
            max_price=r.get("max_price"),
        )
        for r in records
    ]


@app.get("/rdd-result/{commodity}", response_model=RDDResult, tags=["Analysis"])
async def rdd_result(commodity: str):
    """Get the latest RDD estimate for a commodity."""
    conn = get_connection()
    init_schema(conn)
    
    # Try to get cached result first
    cached = get_latest_rdd(conn, commodity)
    
    if cached and cached.get("effect") is not None:
        conn.close()
        return RDDResult(
            commodity=commodity,
            effect=cached["effect"],
            p_value=cached["p_value"],
            std_error=cached["std_error"],
            n_left=cached["n_left"],
            n_right=cached["n_right"],
            interpretation=cached.get("interpretation", ""),
            error=None,
        )
    
    # Run fresh RDD
    try:
        from mandi_rdd.analysis.rdd_engine import run_rdd
        result = run_rdd(conn, commodity=commodity)
        conn.close()
        
        return RDDResult(
            commodity=commodity,
            effect=result.get("effect"),
            p_value=result.get("p_value"),
            std_error=result.get("std_error"),
            n_left=result.get("n_left"),
            n_right=result.get("n_right"),
            interpretation=result.get("interpretation", ""),
            error=result.get("error"),
        )
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/rdd-plot/{commodity}", tags=["Analysis"])
async def rdd_plot(commodity: str):
    """Get binned scatter plot data for the RDD discontinuity chart."""
    conn = get_connection()
    init_schema(conn)
    
    try:
        price_df = get_monthly_avg_prices(conn, commodity=commodity)
        
        if len(price_df) < 20:
            conn.close()
            return {"error": f"Insufficient data: {len(price_df)} monthly observations"}
        
        from mandi_rdd.ingestion.fetch_rainfall import load_district_subdivision_map
        district_map = load_district_subdivision_map()
        price_df["sub_division"] = price_df.apply(
            lambda r: district_map.get((r["state"], r["district"]), None),
            axis=1,
        )
        price_df = price_df.dropna(subset=["sub_division"])
        
        rainfall_df = conn.execute("SELECT * FROM rainfall").fetchdf()
        merged = price_df.merge(
            rainfall_df,
            on=["sub_division", "year", "month"],
            how="inner",
        )
        merged = merged.dropna(subset=["departure_pct", "avg_modal_price"])
        conn.close()
        
        if len(merged) < 20:
            return {"error": f"Insufficient matched data: {len(merged)} observations"}
        
        x = merged["departure_pct"].values
        y = merged["avg_modal_price"].values
        
        from mandi_rdd.analysis.rdd_engine import rdd_plot_data
        plot_data = rdd_plot_data(x, y, cutoff=-19.0)
        return plot_data
        
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/forecast/{commodity}", tags=["Forecast"])
async def forecast(
    commodity: str,
    state: Optional[str] = None,
    compare: bool = Query(False, description="If true, returns Prophet vs LSTM side-by-side comparison"),
    lightweight: bool = Query(False, description="Force pure-numpy forecast (no scipy) — used by Vercel"),
):
    """
    Get a forecast for a commodity's modal price.

    When `compare=true`, returns Prophet vs LSTM side-by-side metrics
    with an honest winner callout and explanation.

    When `lightweight=true` (or scipy is unavailable), uses the pure-numpy
    forecast engine (no scipy, no prophet, no sklearn) — suitable for Vercel
    where the 500 MB function cap excludes heavy ML deps.
    """
    conn = get_connection()
    init_schema(conn)

    # Auto-detect lightweight mode: use the pure-numpy engine when scipy is
    # not available (Vercel's trimmed bundle) or when the caller asks for it.
    _use_light = lightweight
    if not _use_light:
        try:
            import scipy  # noqa: F401
        except ImportError:
            _use_light = True

    if compare:
        if _use_light:
            conn.close()
            return {
                "status": "unavailable",
                "commodity": commodity,
                "reason": "Full model comparison (Prophet vs LSTM) requires scipy, which is "
                          "not bundled on this deployment. Use the Northflank API for the "
                          "full comparison, or call /forecast without ?compare=true for the "
                          "lightweight forecast.",
                "forecast": [],
                "metrics": {},
            }
        from mandi_rdd.analysis.forecast import compare_forecast_models
        result = compare_forecast_models(conn, commodity=commodity, state=state)
        conn.close()
        if "error" in result:
            return {"status": "unavailable", "commodity": commodity, "reason": result["error"], "forecast": [], "metrics": {}}
        return result

    if _use_light:
        from mandi_rdd.analysis.lightweight_forecast import get_forecast_summary_lightweight
        result = get_forecast_summary_lightweight(conn, commodity=commodity)
    else:
        from mandi_rdd.analysis.forecast import get_forecast_summary
        result = get_forecast_summary(conn, commodity=commodity)
    conn.close()

    if "error" in result:
        return {"status": "unavailable", "commodity": commodity, "reason": result["error"], "forecast": [], "metrics": {}}

    return result


@app.get("/robustness/{commodity}", tags=["Analysis"])
async def robustness(commodity: str):
    """Get the full robustness check bundle for a commodity."""
    conn = get_connection()
    init_schema(conn)
    
    from mandi_rdd.analysis.rdd_engine import run_rdd
    result = run_rdd(conn, commodity=commodity)
    conn.close()
    
    if result.get("error"):
        raise HTTPException(status_code=404, detail=result["error"])
    
    return {
        "commodity": commodity,
        "main_effect": result.get("effect"),
        "p_value": result.get("p_value"),
        "bandwidth_sensitivity": result.get("bandwidth_sensitivity", []),
        "placebo_tests": result.get("placebo_tests", []),
        "density_test": result.get("density_test", {}),
        "covariate_balance": result.get("covariate_balance", {}),
        "fe_effect": result.get("fe_effect"),
        "fe_p_value": result.get("fe_p_value"),
    }


@app.get("/risk-score/{commodity}", tags=["Predictions"])
async def risk_score(
    commodity: str,
    district: Optional[str] = Query(None),
):
    """Get price-spike risk score for a commodity."""
    conn = get_connection()
    init_schema(conn)
    
    try:
        from mandi_rdd.analysis.classifier import predict_spike_risk
        result = predict_spike_risk(conn, commodity=commodity, district=district)
        conn.close()
        return result
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/recommendation/{commodity}", tags=["Predictions"])
async def recommendation(
    commodity: str,
    district: Optional[str] = Query(None),
):
    """Get a procurement recommendation for a commodity."""
    conn = get_connection()
    init_schema(conn)
    
    try:
        from mandi_rdd.analysis.prescriptive import compute_recommendation
        result = compute_recommendation(conn, commodity=commodity, district=district)
        conn.close()
        return result
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))


# ── Phase 11: AI Orchestrator Endpoint ──

@app.post("/ask", response_model=AskResponse, tags=["AI Orchestrator"])
async def ask_question(request: AskRequest):
    """
    Ask a free-text procurement question to the AI orchestrator.
    
    The orchestrator:
    1. Detects the commodity and district from the query
    2. Calls the relevant internal analysis tools (RDD, forecast, risk score, etc.)
    3. Routes the question + tool results through the OpenRouter free-tier
       multi-model chain with circuit-breaker fallback
    4. Returns a grounded answer that only uses numbers from the tool calls
    
    **Example queries:**
    - "Should I lock in onion procurement in Nashik next month?"
    - "What's the price-spike risk for tomato in Maharashtra?"
    - "Summarize what changed this week for onion"
    - "How robust is the RDD finding for potato?"
    """
    try:
        from mandi_rdd.ai.orchestrator import answer_question
        
        result = answer_question(
            query=request.query,
            commodity=request.commodity,
            district=request.district,
        )
        
        return AskResponse(
            query=result.get("query", request.query),
            commodity=result.get("commodity", request.commodity or "Onion"),
            district=result.get("district", request.district or "All"),
            answer=result.get("answer", "Unable to generate an answer at this time."),
            model_used=result.get("model_used"),
            endpoints_used=result.get("endpoints_used", []),
            error=result.get("error"),
        )
    except ImportError as e:
        logger.error(f"AI orchestrator import failed: {e}")
        return AskResponse(
            query=request.query,
            commodity=request.commodity or "Onion",
            district=request.district or "All",
            answer="The AI orchestrator module is not available. "
                   "Install dependencies: pip install openai",
            model_used=None,
            endpoints_used=[],
            error=f"AI module not available: {e}",
        )
    except Exception as e:
        logger.error(f"Ask endpoint error: {e}")
        return AskResponse(
            query=request.query,
            commodity=request.commodity or "Onion",
            district=request.district or "All",
            answer="An error occurred while processing your question.",
            model_used=None,
            endpoints_used=[],
            error=str(e),
        )


@app.post("/refresh", response_model=RefreshResponse, tags=["System"])
async def refresh(commodity: Optional[str] = None):
    """Kick off a full pipeline re-run in the background.

    Because the pipeline (fetching prices, rainfall, RDD, forecast) can take
    several minutes, the task runs as a background job and this endpoint
    returns immediately. Track progress via GET /health (n_prices, last_run_utc)
    or GET /metrics.

    Args:
        commodity: Optional commodity filter to limit the pipeline run.
    """
    try:
        from mandi_rdd.ingestion.scheduler import run_ingestion

        def _run_pipeline(commodity_filter: str | None = None):
            import time as _t
            _start = _t.time()
            filters = {}
            if commodity_filter:
                filters["commodity"] = commodity_filter
            logger.info(f"Background pipeline starting (commodity={commodity_filter or 'all'})...")
            summary = run_ingestion(filters=filters if commodity_filter else None)

            # Generate nightly narrative if AI is configured
            from mandi_rdd.ai.router import get_api_key as _get_llm_key
            _llm_key = _get_llm_key()
            narrative_status = "skipped"
            if _llm_key:
                try:
                    from mandi_rdd.ai.orchestrator import generate_nightly_narrative
                    target = commodity_filter or "Onion"
                    narrative = generate_nightly_narrative(commodity=target)
                    narrative_status = "generated" if not narrative.get("error") else "failed"
                    logger.info(f"Nightly narrative for {target}: {narrative_status}")
                except Exception as e:
                    narrative_status = f"error: {e}"
                    logger.warning(f"Nightly narrative generation failed: {e}")
            duration = round(_t.time() - _start, 1)
            logger.info(f"Background pipeline finished in {duration}s: {summary}")

        threading.Thread(target=_run_pipeline, args=(commodity,), daemon=True).start()
        return RefreshResponse(
            status="ok",
            message=f"Pipeline started in background (commodity={commodity or 'all'}). Check /health or /metrics for progress.",
            duration_seconds=None,
        )
    except Exception as e:
        logger.error(f"Failed to start background pipeline: {e}")
        return RefreshResponse(
            status="error",
            message=f"Failed to start pipeline: {e}",
            duration_seconds=None,
        )


@app.get("/debug/rainfall-test", tags=["System"])
async def debug_rainfall_test():
    """Test Open-Meteo rainfall fetch connectivity and return diagnostic info.
    
    This endpoint helps debug rainfall fetch issues by testing Open-Meteo
    connectivity from the server and returning detailed diagnostics.
    """
    import urllib.request
    import json as _json
    from pathlib import Path as _Path
    
    results = {
        "coords_file_exists": False,
        "coords_file_path": "",
        "coords_count": 0,
        "district_mapping_count": 0,
        "open_meteo_test_url": "",
        "open_meteo_response": None,
        "open_meteo_error": None,
        "sample_subdivisions": [],
    }
    
    # Test 1: Check if district_coords.json exists
    try:
        coords_path = _Path(__file__).resolve().parent.parent.parent / "data" / "district_coords.json"
        results["coords_file_path"] = str(coords_path)
        results["coords_file_exists"] = coords_path.exists()
        if coords_path.exists():
            with open(coords_path) as f:
                coords = _json.load(f)
            results["coords_count"] = len(coords)
    except Exception as e:
        results["coords_error"] = str(e)
    
    # Test 2: Check district-subdivision mapping
    try:
        from mandi_rdd.ingestion.fetch_rainfall import load_district_subdivision_map
        dmap = load_district_subdivision_map()
        results["district_mapping_count"] = len(dmap)
    except Exception as e:
        results["mapping_error"] = str(e)
    
    # Test 3: Test Open-Meteo connectivity with a single coordinate
    try:
        test_lat, test_lon = 19.0760, 72.8777  # Mumbai
        test_url = (
            f"https://archive-api.open-meteo.com/v1/archive"
            f"?latitude={test_lat}&longitude={test_lon}"
            f"&start_date=2024-01-01&end_date=2024-01-31"
            f"&daily=precipitation_sum&timezone=Asia%2FKolkata"
        )
        results["open_meteo_test_url"] = test_url
        
        req = urllib.request.Request(test_url, headers={"User-Agent": "MandiIQ/1.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = _json.loads(resp.read())
            daily = data.get("daily", {})
            times = daily.get("time", [])
            precip = daily.get("precipitation_sum", [])
            results["open_meteo_response"] = {
                "status": "success",
                "days_returned": len(times),
                "sample_dates": times[:3] if times else [],
                "sample_precip": precip[:3] if precip else [],
            }
    except Exception as e:
        results["open_meteo_error"] = str(e)
    
    # Test 4: Try a mini rainfall fetch for 3 sub-divisions
    try:
        from mandi_rdd.ingestion.fetch_rainfall import fetch_rainfall_from_open_meteo
        import logging
        logging.basicConfig(level=logging.DEBUG)
        
        # This will fetch a small sample
        records = fetch_rainfall_from_open_meteo()
        results["rainfall_fetch_result"] = {
            "total_records": len(records),
            "sample_records": records[:2] if records else [],
        }
        if records:
            subdivs = list(set(r.get("sub_division") for r in records[:10]))
            results["sample_subdivisions"] = subdivs[:5]
    except Exception as e:
        results["rainfall_fetch_error"] = str(e)
    
    return results


@app.post("/run-rainfall-rdd", tags=["System"])
async def run_rainfall_rdd():
    """Fetch rainfall data and run RDD analysis directly.
    
    This is a targeted endpoint that skips price fetch (since prices
    are already loaded) and directly fetches rainfall, stores it,
    and runs RDD analysis for rain-sensitive commodities.
    """
    import threading
    
    def _do_rainfall_rdd():
        import time as _t
        _start = _t.time()
        try:
            from mandi_rdd.ingestion.fetch_rainfall import fetch_and_store_all_rainfall
            from mandi_rdd.storage.duckdb_store import get_connection, upsert_rainfall, save_rdd_result
            from mandi_rdd.analysis.rdd_engine import run_rdd
            
            logger.info("Rainfall+RDD: Starting rainfall fetch...")
            rainfall = fetch_and_store_all_rainfall()
            logger.info(f"Rainfall+RDD: Fetched {len(rainfall)} rainfall records")
            
            if rainfall:
                conn = get_connection()
                n_new = upsert_rainfall(conn, rainfall)
                conn.commit()
                logger.info(f"Rainfall+RDD: Stored {n_new} new rainfall records")
                
                # Run RDD for rain-sensitive + high-volume commodities
                rain_sensitive = ["Onion", "Tomato", "Potato", "Cabbage", "Cauliflower"]
                high_volume = ["Wheat", "Rice", "Paddy(Common)", "Paddy(Dhan)(Common)",
                    "Maize", "Soyabean", "Mustard", "Groundnut",
                    "Banana", "Mango", "Apple", "Grapes",
                    "Garlic", "Ginger (Dry)", "Chili Red", "Turmeric",
                    "Bajra(Pearl Millet/Cumbu)", "Jowar (Sorghum)",
                    "Bengal Gram (Gram)(Whole)", "Red Gram",
                    "Green Gram (Moong)(Whole)", "Black Gram (Urad Beans)(Whole)",
                    "Sugarcane", "Cotton"]
                # Only run for commodities that exist in DB
                all_comms = set()
                try:
                    df_c = conn.execute("SELECT DISTINCT commodity FROM prices").fetchdf()
                    all_comms = set(df_c["commodity"].tolist())
                except Exception:
                    pass
                target_comms = [c for c in rain_sensitive + high_volume if c in all_comms]
                rdd_count = 0
                for commodity in target_comms:
                    try:
                        result = run_rdd(conn, commodity)
                        if result and result.get("effect") is not None:
                            save_rdd_result(conn, result)
                            rdd_count += 1
                            logger.info(f"Rainfall+RDD: {commodity} effect={result.get('effect'):.4f} p={result.get('p_value'):.4f}")
                    except Exception as e:
                        logger.warning(f"Rainfall+RDD: {commodity} failed: {e}")
                
                conn.commit()
                conn.close()
                duration = round(_t.time() - _start, 1)
                logger.info(f"Rainfall+RDD: Complete in {duration}s - {len(rainfall)} rainfall, {rdd_count} RDD results")
            else:
                logger.warning("Rainfall+RDD: No rainfall data fetched")
        except Exception as e:
            logger.error(f"Rainfall+RDD failed: {e}")
    
    threading.Thread(target=_do_rainfall_rdd, daemon=True).start()
    return {"status": "ok", "message": "Rainfall fetch + RDD analysis started in background"}


@app.post("/backfill-historical", tags=["System"])
async def backfill_historical():
    """Fetch historical monthly prices from Ashoka CEDA and store in DuckDB."""
    import threading
    
    def _do_backfill():
        import time as _t
        _start = _t.time()
        try:
            from mandi_rdd.ingestion.fetch_historical_ashoka import main as ashoka_main
            import os
            
            hist_dir = Path(__file__).resolve().parent.parent / "data" / "historical"
            hist_dir.mkdir(parents=True, exist_ok=True)
            out_path = str(hist_dir / "agmarknet_ashoka.csv")
            
            logger.info("Historical backfill: Starting Ashoka CEDA fetch...")
            ashoka_main(["--out", out_path, "--workers", "8"])
            
            if os.path.exists(out_path):
                from mandi_rdd.ingestion.ingest_historical_csv import ingest_csv
                from mandi_rdd.storage.duckdb_store import get_connection
                conn = get_connection()
                n = ingest_csv(conn, out_path)
                conn.commit()
                conn.close()
                duration = round(_t.time() - _start, 1)
                logger.info(f"Historical backfill: Done in {duration}s - {n} rows")
                try:
                    os.remove(out_path)
                except Exception:
                    pass
            else:
                logger.warning("Historical backfill: No CSV produced")
        except Exception as e:
            logger.error(f"Historical backfill failed: {e}")
    
    threading.Thread(target=_do_backfill, daemon=True).start()
    return {"status": "ok", "message": "Historical backfill started in background"}


# ── R2 restore helpers ──────────────────────────────────────────────

@app.post("/admin/restore-from-r2", tags=["Admin"])
async def admin_restore_from_r2():
    """Restore the DuckDB database from the latest Cloudflare R2 backup.

    Streamed end-to-end (download -> temp .gz file, gzip -> temp DuckDB,
    sanity gate, atomic rename) via r2_sync.restore_db(), so it fits in
    low-memory containers — the old in-memory gzip.decompress of a ~500 MB DB
    OOM-killed the 256 MB API pod. Same validated backup path used by the
    hourly cron and duckdb_store's R2 bootstrap.

    Returns:
        dict with status, message, prices, bytes, and file size.
    """
    try:
        from mandi_rdd.storage.r2_sync import restore_db
        result = restore_db()
        logger.info(
            "R2 restore: %s prices restored to %s",
            result.get("prices"), result.get("db_path"),
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("R2 restore failed: %s", e)
        return {"status": "error", "message": f"R2 restore failed: {e}"}
    # Refresh the commodity list for the health endpoint
    try:
        conn = get_connection()
        init_schema(conn)
        df = conn.execute("SELECT DISTINCT commodity FROM prices ORDER BY commodity").fetchdf()
        state.commodities = df["commodity"].tolist() if len(df) > 0 else []
        conn.close()
    except Exception as e:
        logger.warning("R2 restore: could not refresh commodity list: %s", e)
    return {
        "status": "ok",
        "message": "Database restored from R2 backup.",
        "prices": result.get("prices"),
        "bytes_downloaded": result.get("bytes_downloaded"),
        "bytes_decompressed": result.get("bytes_decompressed"),
        "db_path": result.get("db_path"),
    }


@app.post("/admin/ingest-historical", tags=["Admin"])
async def admin_ingest_historical(file: UploadFile = File(...)):
    """Upload and ingest a historical CSV file into the prices table.
    Accepts Agmarknet, data.gov.in snapshot, or WFP/FAO food price CSVs.
    Uses DuckDB's native CSV reader for fast bulk import.
    """
    import tempfile
    import shutil

    try:
        # Save uploaded file to temp location
        suffix = ".csv"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name

        # Determine CSV format and ingest
        conn = get_connection()
        try:
            # Ensure prices table exists
            conn.execute("""
                CREATE TABLE IF NOT EXISTS prices (
                    arrival_date DATE, state VARCHAR, district VARCHAR, market VARCHAR,
                    commodity VARCHAR, variety VARCHAR, grade VARCHAR,
                    min_price DOUBLE, max_price DOUBLE, modal_price DOUBLE
                )
            """)

            # Read first line to detect format
            with open(tmp_path, "r", encoding="utf-8") as f:
                header = f.readline()

            if "Price Date" in header or "District Name" in header:
                # Agmarknet historical format (date: "05 Apr 2025")
                conn.execute(f"""
                    INSERT OR IGNORE INTO prices (arrival_date, state, district, market, commodity, variety, grade,
                                       min_price, max_price, modal_price)
                    SELECT
                        COALESCE(TRY_CAST("Price Date" AS DATE), TRY_STRPTIME("Price Date", '%d %b %Y')),
                        TRIM(State), TRIM("District Name"),
                        TRIM("Market Name"), TRIM(Commodity), TRIM(Variety), TRIM(Grade),
                        TRY_CAST(REPLACE(CAST("Min Price (Rs./Quintal)" AS VARCHAR), ',', '') AS DOUBLE),
                        TRY_CAST(REPLACE(CAST("Max Price (Rs./Quintal)" AS VARCHAR), ',', '') AS DOUBLE),
                        TRY_CAST(REPLACE(CAST("Modal Price (Rs./Quintal)" AS VARCHAR), ',', '') AS DOUBLE)
                    FROM read_csv_auto('{tmp_path}', header=true, ignore_errors=true)
                    WHERE "Price Date" IS NOT NULL AND TRIM("Price Date") != '' AND Commodity IS NOT NULL
                """)
                fmt = "agmarknet_historical"
            elif "date,admin1" in header or ("admin1" in header and file.filename and "wfp" in file.filename.lower()):
                # WFP food prices format
                conn.execute(f"""
                    INSERT OR IGNORE INTO prices (arrival_date, state, district, market, commodity, variety, grade,
                                       min_price, max_price, modal_price)
                    SELECT
                        TRY_CAST(date AS DATE), TRIM(admin1), TRIM(admin2), TRIM(market),
                        TRIM(commodity), TRIM(commodity), '', NULL, NULL,
                        TRY_CAST(price AS DOUBLE)
                    FROM read_csv_auto('{tmp_path}', header=true, ignore_errors=true)
                    WHERE date IS NOT NULL AND commodity IS NOT NULL AND price IS NOT NULL
                      AND admin1 IS NOT NULL AND TRIM(admin1) != ''
                """)
                fmt = "wfp_food_prices"
            elif "Arrival_Date" in header:
                # data.gov.in snapshot format
                conn.execute(f"""
                    INSERT OR IGNORE INTO prices (arrival_date, state, district, market, commodity, variety, grade,
                                       min_price, max_price, modal_price)
                    SELECT
                        TRY_CAST(Arrival_Date AS DATE), TRIM(State), TRIM(District), TRIM(Market),
                        TRIM(Commodity), TRIM(Variety), TRIM(Grade),
                        TRY_CAST(REPLACE(CAST("Min_x0020_Price" AS VARCHAR), ',', '') AS DOUBLE),
                        TRY_CAST(REPLACE(CAST("Max_x0020_Price" AS VARCHAR), ',', '') AS DOUBLE),
                        TRY_CAST(REPLACE(CAST("Modal_x0020_Price" AS VARCHAR), ',', '') AS DOUBLE)
                    FROM read_csv_auto('{tmp_path}', header=true, ignore_errors=true)
                    WHERE Arrival_Date IS NOT NULL AND Commodity IS NOT NULL
                """)
                fmt = "data_gov_in_snapshot"
            else:
                conn.close()
                return {"status": "error", "message": f"Unrecognized CSV format. Header: {header[:100]}"}

            n_prices = conn.execute("SELECT COUNT(*) FROM prices").fetchone()[0]
            n_commodities = conn.execute("SELECT COUNT(DISTINCT commodity) FROM prices").fetchone()[0]
            conn.close()

            return {
                "status": "ok",
                "format": fmt,
                "filename": file.filename,
                "total_prices": n_prices,
                "total_commodities": n_commodities,
            }
        finally:
            conn.close()
            import os
            os.unlink(tmp_path)

    except Exception as e:
        logger.error("Historical ingestion failed: %s", e)
        return {"status": "error", "message": str(e)}


@app.post("/admin/backup-to-r2", tags=["Admin"])
async def admin_backup_to_r2():
    """Upload the current DuckDB database to Cloudflare R2 as a gzipped backup.
    Reads the local DuckDB file, compresses it, and uploads to R2 as
    mandi_iq.duckdb.gz. Requires R2 credentials configured as environment variables.
    Returns:
        dict with status, message, bytes uploaded, and compression ratio.
    """
    try:
        from mandi_rdd.storage.duckdb_store import DB_PATH
        import gzip
        import urllib.request
        import hmac
        import hashlib
        import datetime

        if not DB_PATH.exists():
            return {"status": "error", "message": f"Database file not found: {DB_PATH}"}

        # Read and compress
        raw = DB_PATH.read_bytes()
        compressed = gzip.compress(raw, compresslevel=6)

        # R2 credentials
        bucket = os.environ.get("R2_BUCKET") or os.environ.get("R2_BUCKET_NAME") or ""
        account_id = os.environ.get("R2_ACCOUNT_ID") or ""
        access_key = os.environ.get("R2_ACCESS_KEY_ID") or ""
        secret_key = os.environ.get("R2_SECRET_ACCESS_KEY") or ""

        if not all([bucket, account_id, access_key, secret_key]):
            missing = [k for k, v in [
                ("R2_BUCKET/R2_BUCKET_NAME", bucket), ("R2_ACCOUNT_ID", account_id),
                ("R2_ACCESS_KEY_ID", access_key), ("R2_SECRET_ACCESS_KEY", secret_key),
            ] if not v]
            return {"status": "error", "message": "Missing R2 credentials: " + ", ".join(missing)}

        # Build S3 request
        endpoint = f"https://{account_id}.r2.cloudflarestorage.com"
        key = "mandi_iq.duckdb.gz"
        url = f"{endpoint}/{bucket}/{key}"

        # AWS SigV4 signing
        now = datetime.datetime.utcnow()
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = now.strftime("%Y%m%d")
        region = "auto"
        service = "s3"
        algorithm = "AWS4-HMAC-SHA256"
        credential_scope = f"{date_stamp}/{region}/{service}/aws4_request"
        credential = f"{access_key}/{credential_scope}"

        signed_headers = "host;x-amz-content-sha256;x-amz-date"
        content_sha256 = hashlib.sha256(compressed).hexdigest()

        canonical_request = (
            "PUT\n"
            f"/{bucket}/{key}\n"
            "\n"
            f"host:{account_id}.r2.cloudflarestorage.com\n"
            f"x-amz-content-sha256:{content_sha256}\n"
            f"x-amz-date:{amz_date}\n"
            "\n"
            f"{signed_headers}\n"
            f"{content_sha256}"
        )

        string_to_sign = (
            f"{algorithm}\n"
            f"{amz_date}\n"
            f"{credential_scope}\n"
            f"{hashlib.sha256(canonical_request.encode()).hexdigest()}"
        )

        def sign(key, msg):
            return hmac.new(key, msg.encode(), hashlib.sha256).digest()

        k_date = sign(("AWS4" + secret_key).encode(), date_stamp)
        k_region = sign(k_date, region)
        k_service = sign(k_region, service)
        k_signing = sign(k_service, "aws4_request")
        signature = hmac.new(k_signing, string_to_sign.encode(), hashlib.sha256).hexdigest()

        auth_header = (
            f"{algorithm} Credential={credential}, SignedHeaders={signed_headers}, Signature={signature}"
        )

        headers = {
            "Host": f"{account_id}.r2.cloudflarestorage.com",
            "X-Amz-Content-Sha256": content_sha256,
            "X-Amz-Date": amz_date,
            "Authorization": auth_header,
            "Content-Type": "application/gzip",
        }

        req = urllib.request.Request(url, data=compressed, headers=headers, method="PUT")
        with urllib.request.urlopen(req, timeout=120) as resp:
            resp.read()

        logger.info("R2 backup: uploaded %d bytes (compressed from %d) to s3://%s/%s",
                    len(compressed), len(raw), bucket, key)

        return {
            "status": "ok",
            "message": "Database backed up to R2.",
            "bytes_uploaded": len(compressed),
            "bytes_original": len(raw),
            "compression_pct": round(100 * (1 - len(compressed) / len(raw)), 1),
            "r2_key": key,
        }

    except urllib.error.HTTPError as e:
        return {"status": "error", "message": "R2 upload failed (HTTP " + str(e.code) + "): " + e.reason}
    except (TimeoutError, urllib.error.URLError, OSError) as e:
        return {"status": "error", "message": "R2 upload failed: " + str(e)}
    except Exception as e:
        return {"status": "error", "message": "Backup failed: " + str(e)}


@app.post("/admin/reset-metrics", tags=["Admin"])
async def admin_reset_metrics():
    """Reset LLM fallback counter and clear all model cool-down states.

    Useful for recovering from a stuck state after a free-tier rate limit
    penalty has expired. Does not affect any other system state.
    """
    reset_llm_fallback_count()
    clear_cool_down()
    return {
        "status": "ok",
        "llm_fallback_count": get_llm_fallback_count(),
        "message": "LLM metrics reset: counter zeroed, all models taken out of cool-down.",
    }



# -- Dashboard patcher with manual hit counter --
_dashboard_patch_count: int = 0

def _get_patched_dashboard(datasource_name: str, version: str = "") -> dict:
    global _dashboard_patch_count
    _dashboard_patch_count += 1
    import copy as _copy
    source = _dashboard_export if _dashboard_export is not None else dashboard_json
    result = _copy.deepcopy(source)
    for inp in result.get("__inputs", []):
        if inp.get("type") == "datasource":
            inp["name"] = datasource_name
            inp["label"] = datasource_name
    dash = result.get("dashboard", result)
    for item in dash.get("templating", {}).get("list", []):
        if item.get("type") == "datasource":
            item["current"] = {"value": datasource_name, "text": datasource_name}
            item["query"] = datasource_name
    return result


@app.get("/grafana-dashboard", tags=["System"])
async def grafana_dashboard(
    datasource: str = Query("DS_PROMETHEUS", description="Pre-bind the datasource name."),
    v: str = Query("", description="Cache-busting version string."),
):
    if dashboard_json is None:
        raise HTTPException(status_code=404, detail="Dashboard template not found")
    if datasource != "DS_PROMETHEUS" or v:
        return _get_patched_dashboard(datasource, v)
    return dashboard_json


@app.post("/admin/refresh-dashboard-cache", tags=["Admin"])
async def admin_refresh_dashboard_cache():
    global dashboard_json, _dashboard_export, _dashboard_last_refresh, _dashboard_file_mtime
    if os.path.exists(_dashboard_path):
        with open(_dashboard_path, "r") as f:
            _raw = json.load(f)
        dashboard_json = _raw.get("dashboard", _raw)
        _dashboard_export = _raw
        _dashboard_last_refresh = time.time()
        _dashboard_file_mtime = os.path.getmtime(_dashboard_path)
        # Warm the dashboard patch counter
        _get_patched_dashboard("Grafana")
        return {"status": "ok", "message": "Dashboard cache cleared and JSON reloaded from disk."}
    return {"status": "error", "message": f"Dashboard file not found at {_dashboard_path}"}


@app.get("/admin/dashboard-status", tags=["Admin"])
async def admin_dashboard_status():
    result = {"path": _dashboard_path, "file_exists": os.path.exists(_dashboard_path), "json_loaded": dashboard_json is not None}
    result["cache_size"] = _dashboard_patch_count if dashboard_json is not None else 0
    if os.path.exists(_dashboard_path):
        try:
            s = os.stat(_dashboard_path)
            from datetime import datetime, timezone
            result["file_mtime_utc"] = datetime.fromtimestamp(s.st_mtime, tz=timezone.utc).isoformat()
            result["file_size_bytes"] = s.st_size
            with open(_dashboard_path, "rb") as f:
                result["md5_hash"] = hashlib.md5(f.read()).hexdigest()
        except OSError as e:
            result["stat_error"] = str(e)
    if _dashboard_last_refresh > 0:
        from datetime import datetime, timezone
        result["last_refresh_utc"] = datetime.fromtimestamp(_dashboard_last_refresh, tz=timezone.utc).isoformat()
    if _dashboard_file_mtime > 0:
        from datetime import datetime, timezone
        result["last_refresh_file_mtime_utc"] = datetime.fromtimestamp(_dashboard_file_mtime, tz=timezone.utc).isoformat()
        result["stale"] = os.path.getmtime(_dashboard_path) > _dashboard_file_mtime
    return result


@app.post("/webhook/grafana-dashboard-update", tags=["Webhook"])
async def webhook_grafana_dashboard_update(
    payload: dict = {},
    x_webhook_secret: str = Header(None, alias="X-Webhook-Secret"),
):
    _secret = os.environ.get("WEBHOOK_SECRET", "")
    if _secret:
        if not x_webhook_secret or x_webhook_secret != _secret:
            logger.warning("Webhook auth failed: header=%s", "***present***" if x_webhook_secret else "***missing***")
            raise HTTPException(status_code=403, detail="Forbidden: invalid or missing X-Webhook-Secret header.")
    event_name = payload.get("event", "unknown")
    logger.info("Webhook received: event=%(event)s", {"event": event_name})
    result = await admin_refresh_dashboard_cache()
    if isinstance(result, dict):
        result["event"] = event_name
    return result



@app.get("/historical-import-status", tags=["Data"])
async def historical_import_status():
    """Get the current status of the background Ashoka CEDA historical import."""
    try:
        from mandi_rdd.ingestion.ashoka_background_import import get_status
        return get_status()
    except Exception as e:
        return {"state": "error", "error": str(e)}


@app.post("/trigger-ashoka-import", tags=["Data"])
async def trigger_ashoka_import(all_commodities: bool = True, workers: int = 2):
    """Start or resume the Ashoka CEDA historical import in the background.
    
    The import fetches multi-year monthly price history for ALL commodities
    (default) or the top 40. It runs as a daemon thread on the API server
    (no timeout), saves checkpoints every 10 cells for resume, and
    automatically backfills into DuckDB when complete.
    
    Track progress via GET /historical-import-status.
    """
    try:
        from mandi_rdd.ingestion.ashoka_background_import import trigger
        result = trigger(all_commodities=all_commodities, workers=workers)
        return result
    except Exception as e:
        return {"error": str(e)}


@app.post("/trigger-backfill", tags=["Data"])
async def trigger_backfill():
    """Run historical CSV backfill on any Ashoka CSV already on disk.
    
    Use this after a restart to consume a previously-fetched CSV into DuckDB
    without re-running the full Ashoka API fetch.
    """
    try:
        from mandi_rdd.ingestion.ashoka_background_import import trigger_backfill_only
        return trigger_backfill_only()
    except Exception as e:
        return {"error": str(e)}



# ── Mermaid pipeline SVG renderer ──

# Path to the mermaid-cli renderer (installed globally via npm)
_MMDC_CMD: str = "mmdc"
_MMDC_SVG_CACHE: str | None = None
_MMDC_SVG_MTIME: float = 0.0
_MMDC_LOCK: threading.Lock = threading.Lock()

# Try to find mmdc.cmd on Windows (shutil is already imported at top of file)
_mmdc_path = shutil.which("mmdc")
if _mmdc_path:
    _MMDC_CMD = _mmdc_path


def _strip_mmd_frontmatter(content: str) -> str:
    """Remove YAML frontmatter (--- ... ---) from a .mmd string.
    mermaid-cli does not support YAML frontmatter, so we strip it.
    """
    if content.startswith("---"):
        end = content.find("---", 3)
        if end > 0:
            return content[end + 3:].strip()
    return content


def _sanitize_svg_xml(svg: str) -> str:
    """Make an mmdc-produced SVG strictly XML-well-formed.

    mermaid-cli emits two XML-invalid constructs that break strict XML
    renderers (Firefox showing `xmlParseEntityRef` / `mismatched tag`):
      1. a duplicated ``xmlns="http://www.w3.org/2000/svg"`` attribute
         (duplicate attribute is a hard XML error), and
      2. unclosed ``<br>`` void elements inside ``<foreignObject>`` label
         divs (must be ``<br/>`` for XML well-formedness).

    Returns the sanitized SVG string (idempotent — safe to call again).
    """
    import re as _re

    # 1. Drop the duplicate xmlns attribute (keep the first occurrence)
    first = svg.find('xmlns="http://www.w3.org/2000/svg"')
    if first != -1:
        second = svg.find('xmlns="http://www.w3.org/2000/svg"', first + 1)
        if second != -1:
            svg = svg[:second] + svg[second + len('xmlns="http://www.w3.org/2000/svg" '):]

    # 2. Self-close void <br> elements (not already closed)
    svg = _re.sub(r"<br(?![ /])", "<br/>", svg)

    return svg


def _render_pipeline_svg(force: bool = False) -> str:
    """Render the pipeline-flow-live.mmd to SVG via mermaid-cli.

    Caches the SVG on disk at ``diagrams/pipeline-flow-live.svg``.
    Re-renders only when the .mmd file changes (or ``force=True``).
    Thread-safe via ``_MMDC_LOCK`` — concurrent requests block on the
    lock and share the same rendered result.
    Returns the SVG content as a string.
    """
    global _MMDC_SVG_CACHE, _MMDC_SVG_MTIME

    mmd_path = Path(__file__).resolve().parent.parent.parent / "diagrams" / "pipeline-flow-live.mmd"
    svg_path = mmd_path.with_suffix(".svg")

    # Fast path: cache hit (no lock needed for reads; stale read is harmless)
    if not force and svg_path.exists():
        current_mtime = mmd_path.stat().st_mtime if mmd_path.exists() else 0
        if current_mtime <= _MMDC_SVG_MTIME and _MMDC_SVG_CACHE is not None:
            return _MMDC_SVG_CACHE

    # Slow path: re-render under lock so only one thread spawns mmdc
    with _MMDC_LOCK:
        # Double-check after acquiring lock (another thread may have rendered)
        if not force and svg_path.exists():
            current_mtime = mmd_path.stat().st_mtime if mmd_path.exists() else 0
            if current_mtime <= _MMDC_SVG_MTIME and _MMDC_SVG_CACHE is not None:
                return _MMDC_SVG_CACHE

        if not mmd_path.exists():
            raise FileNotFoundError(f"Pipeline diagram not found: {mmd_path}")

        # Read and strip frontmatter
        raw = mmd_path.read_text(encoding="utf-8")
        mermaid_content = _strip_mmd_frontmatter(raw)

        # Write to temp file (mmdc needs a file, not stdin)
        import tempfile as _tempfile
        tmp_mmd = _tempfile.NamedTemporaryFile(
            suffix=".mmd", delete=False, mode="w", encoding="utf-8"
        )
        tmp_mmd.write(mermaid_content)
        tmp_mmd.close()

        try:
            import subprocess as _subprocess
            result = _subprocess.run(
                [_MMDC_CMD, "-i", tmp_mmd.name, "-o", str(svg_path),
                 "-b", "transparent", "-w", "1200"],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode != 0:
                _stderr = (result.stderr or "")[:300]
                raise RuntimeError(
                    f"mmdc failed (rc={result.returncode}): {_stderr}"
                )
        finally:
            try:
                os.unlink(tmp_mmd.name)
            except Exception:
                pass

        if not svg_path.exists():
            raise RuntimeError("mmdc did not produce output SVG")

        # mmdc emits XML-invalid output (duplicate xmlns, unclosed <br>);
        # sanitize before caching/serving so strict XML renderers display it.
        svg_content = _sanitize_svg_xml(svg_path.read_text(encoding="utf-8"))
        svg_path.write_text(svg_content, encoding="utf-8")
        _MMDC_SVG_CACHE = svg_content
        _MMDC_SVG_MTIME = mmd_path.stat().st_mtime
        logger.info(
            f"Pipeline SVG rendered: {len(svg_content):,} bytes -> {svg_path}"
        )
        return svg_content


@app.get("/pipeline.mmd", tags=["System"])
async def pipeline_mmd():
    """Serve the pipeline DAG as raw Mermaid source for client-side rendering.

    Strips the YAML frontmatter (mermaid.js CDN doesn't support it) and
    returns the raw ``%%{init: ...}%%`` + flowchart content.
    """
    mmd_path = (
        Path(__file__).resolve().parent.parent.parent
        / "diagrams" / "pipeline-flow-live.mmd"
    )
    if not mmd_path.exists():
        raise HTTPException(status_code=404, detail="Pipeline diagram not yet generated.")
    raw = mmd_path.read_text(encoding="utf-8")
    mermaid_content = _strip_mmd_frontmatter(raw)
    # Re-wrap in mermaid code block for CDN renderer
    body = f"""```mermaid
{mermaid_content}
```"""
    return Response(content=body, media_type="text/plain; charset=utf-8")


@app.get("/pipeline.svg", tags=["System"])
async def pipeline_svg(refresh: bool = Query(False, alias="refresh")):
    """Serve the pipeline DAG as an SVG rendered by mermaid-cli.

    The SVG is cached on disk and re-rendered only when the source .mmd
    file changes.  Pass ``?refresh=1`` to force a full re-render from the
    current ``diagrams/pipeline-flow-live.mmd``.

    Requires Node.js + @mermaid-js/mermaid-cli to be installed globally
    (``npm install -g @mermaid-js/mermaid-cli``).
    """
    try:
        svg = _render_pipeline_svg(force=refresh)
        return Response(content=svg, media_type="image/svg+xml")
    except FileNotFoundError as e:
        logger.warning(f"Pipeline SVG requested but no .mmd file: {e}")
        raise HTTPException(status_code=404, detail=f"Pipeline diagram not available. {e}")
    except RuntimeError as e:
        logger.error(f"Pipeline SVG render failed: {e}")
        raise HTTPException(status_code=503, detail=f"Pipeline SVG rendering unavailable: {e}")



def _query_live_metrics() -> dict:
    """Query DuckDB for live pipeline row counts."""
    from mandi_rdd.storage.duckdb_store import get_connection
    metrics = {
        "n_prices": 0, "n_commodities": 0, "n_states": 0, "n_districts": 0,
        "n_rainfall": 0, "n_ndvi": 0, "n_ndvi_districts": 0,
        "n_forecast_models": 0, "n_rdd_results": 0, "n_fe_results": 0,
        "n_data_lineage": 0, "n_null_state": 0, "n_district_mappings": 0,
        "last_run_utc": "", "last_run_duration_s": 0.0, "last_outcome": "unknown",
    }
    try:
        conn = get_connection()
    except Exception:
        return metrics
    for q, k in [
        ("SELECT COUNT(*) FROM prices", "n_prices"),
        ("SELECT COUNT(DISTINCT commodity) FROM prices", "n_commodities"),
        ("SELECT COUNT(DISTINCT state) FROM prices", "n_states"),
        ("SELECT COUNT(DISTINCT district) FROM prices", "n_districts"),
        ("SELECT COUNT(*) FROM rainfall", "n_rainfall"),
        ("SELECT COUNT(*) FROM ndvi", "n_ndvi"),
        ("SELECT COUNT(DISTINCT district) FROM ndvi", "n_ndvi_districts"),
        ("SELECT COUNT(*) FROM forecast_metrics", "n_forecast_models"),
        ("SELECT COUNT(*) FROM rdd_results", "n_rdd_results"),
        ("SELECT COUNT(DISTINCT commodity) FROM rdd_results WHERE fe_effect IS NOT NULL", "n_fe_results"),
        ("SELECT COUNT(*) FROM data_lineage", "n_data_lineage"),
        ("SELECT COUNT(*) FROM prices WHERE state IS NULL OR state = ''", "n_null_state"),
        ("SELECT COUNT(*) FROM district_mapping", "n_district_mappings"),
    ]:
        try:
            metrics[k] = conn.execute(q).fetchone()[0]
        except Exception:
            pass
    try:
        sp = Path(__file__).resolve().parent.parent / "data" / "last_ingest_status.json"
        if sp.exists():
            with open(sp) as f:
                r = json.load(f)
            metrics["last_run_utc"] = r.get("last_run_utc", "")
            metrics["last_run_duration_s"] = r.get("duration_s", 0.0)
            metrics["last_outcome"] = r.get("outcome", "unknown")
    except Exception:
        pass
    conn.close()
    return metrics


def _build_live_mmd_content() -> str:
    """Build .mmd string with live DuckDB metrics substituted."""
    mmd_path = Path(__file__).resolve().parent.parent.parent / "diagrams" / "pipeline-flow-live.mmd"
    if not mmd_path.exists():
        raise FileNotFoundError(f"Pipeline diagram not found: {mmd_path}")
    raw = mmd_path.read_text(encoding="utf-8")
    m = _query_live_metrics()
    # Strip YAML frontmatter (mmdc does not support it)
    raw = _strip_mmd_frontmatter(raw)
    # Inject a visible title node with live timestamp
    _now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    _dur = m["last_run_duration_s"]
    _oc = m["last_outcome"] or "unknown"
    _oclr = "#8FAE89" if _oc == "success" else "#D9663B"
    _dst = f"{_dur:.1f}s" if _dur else "---"
    _title_html = (
        f"MandiIQ Pipeline Flow <br/>"
        f"<span style='font-size:11px;color:#7e7e7e;'>"
        f"{_now} ~ {_dst} total ~ "
        f"Outcome: <b style='color:{_oclr}'>{_oc}</b>"
        f"</span>"
    )
    raw = f'T0["{_title_html}"]\n' + raw

    def fnum(v):
        return f"{v:,}" if v else "0"

    subs = [
        ("<b>1,334,647</b> records ingested<br/><i>303 commodities ~ 36 states</i>",
         f"<b>{fnum(m['n_prices'])}</b> records ingested<br/>"
         f"<i>{fnum(m['n_commodities'])} commodities ~ {fnum(m['n_states'])} states</i>"),
        ("<b>2,278</b> records<br/><i>34 sub-divisions ~ 2021--2026</i>",
         f"<b>{fnum(m['n_rainfall'])}</b> records<br/><i>Live ~ Multi-year</i>"),
        ("<b>3,663</b> vegetation records<br/><i>605 districts</i>",
         f"<b>{fnum(m['n_ndvi'])}</b> vegetation records<br/><i>{fnum(m['n_ndvi_districts'])} districts</i>"),
        ("<b>860</b> mappings loaded<br/><i>State -> District -> Sub-division</i>",
         f"<b>{fnum(m['n_district_mappings'])}</b> mappings loaded<br/>"
         f"<i>State -> District -> Sub-division</i>"),
        ("<b>1,334,647</b> rows populated<br/><i>0 rows still empty</i>",
         f"<b>{fnum(m['n_prices'])}</b> rows populated<br/><i>{fnum(m['n_null_state'])} rows still empty</i>"),
        ("<b>5</b> records<br/><i>2 source types: prices, varietywise, rainfall</i>",
         f"<b>{fnum(m['n_data_lineage'])}</b> records<br/><i>3 source types: prices, varietywise, rainfall</i>"),
        ("<b>1,334,647</b> prices ~ <b>2,278</b> rainfall<br/><b>3,663</b> NDVI ~ <b>84</b> forecast models",
         f"<b>{fnum(m['n_prices'])}</b> prices ~ <b>{fnum(m['n_rainfall'])}</b> rainfall<br/>"
         f"<b>{fnum(m['n_ndvi'])}</b> NDVI ~ <b>{fnum(m['n_forecast_models'])}</b> forecast models"),
        ("<b>75</b> causal estimates<br/>Triangular kernel ~ McCrary test",
         f"<b>{fnum(m['n_rdd_results'])}</b> causal estimates<br/>Triangular kernel ~ McCrary test"),
        ("<b>52</b> effects with FE<br/>District + month fixed effects",
         f"<b>{fnum(m['n_fe_results'])}</b> effects with FE<br/>District + month fixed effects"),
        ("<b>84</b> models<br/><span style='color:#8FAE89'>[OK] 84 valid</span> <span style='color:#D9663B'>[!] 6 noisy</span><br/>Best: Maize @ 4.7%",
         f"<b>{fnum(m['n_forecast_models'])}</b> models<br/>Seasonal naive + ensemble<br/>Live accuracy metrics"),
    ]
    for old, new_text in subs:
        raw = raw.replace(old, new_text)
    return raw


def _render_mmd_to_svg(mmd_content: str) -> str:
    """Write .mmd to temp file, run mmdc, return SVG."""
    import tempfile as _tf
    tmp_mmd = _tf.NamedTemporaryFile(suffix=".mmd", delete=False, mode="w", encoding="utf-8")
    tmp_svg = _tf.NamedTemporaryFile(suffix=".svg", delete=False, mode="w", encoding="utf-8")
    tmp_mmd.write(mmd_content)
    tmp_mmd.close()
    tmp_svg.close()
    with _MMDC_LOCK:
        try:
            import subprocess as _sp
            r = _sp.run(
                [_MMDC_CMD, "-i", tmp_mmd.name, "-o", tmp_svg.name,
                 "-b", "transparent", "-w", "1200"],
                capture_output=True, text=True, timeout=30,
            )
            if r.returncode != 0:
                raise RuntimeError(f"mmdc failed (rc={r.returncode}): {(r.stderr or '')[:300]}")
            p = Path(tmp_svg.name)
            if not p.exists():
                raise RuntimeError("mmdc did not produce output SVG")
            svg = p.read_text(encoding="utf-8")
            p.unlink(missing_ok=True)
            return svg
        finally:
            try:
                os.unlink(tmp_mmd.name)
            except Exception:
                pass


@app.get("/pipeline/diagram", tags=["System"])
async def pipeline_diagram():
    """Serve pipeline DAG as SVG with live DuckDB metrics."""
    try:
        svg = _render_mmd_to_svg(_build_live_mmd_content())
        return Response(
            content=svg,
            media_type="image/svg+xml",
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
        )
    except (FileNotFoundError, RuntimeError) as e:
        logger.warning(f"Live pipeline diagram fallback: {e}")
        try:
            svg = _render_pipeline_svg()
            return Response(
                content=svg,
                media_type="image/svg+xml",
                headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
            )
        except Exception as fbe:
            raise HTTPException(status_code=503, detail=f"Pipeline diagram unavailable: {fbe}")
# ── Pipeline metrics badge SVG / JSON compositor ──
# Inject live KPI badges onto the pipeline SVG diagram.


def _query_pipeline_metrics() -> dict:
    """Query DuckDB for live pipeline metrics (same shape as /health).
    Returns a flat dict of counts used by the SVG compositor.
    """
    from mandi_rdd.storage.duckdb_store import get_connection as _get_conn
    conn = _get_conn()
    try:
        n_prices = conn.execute("SELECT COUNT(*) FROM prices").fetchone()[0]
        n_commodities = conn.execute("SELECT COUNT(DISTINCT commodity) FROM prices").fetchone()[0]
        n_states = conn.execute("SELECT COUNT(DISTINCT state) FROM prices").fetchone()[0]
        n_districts = conn.execute("SELECT COUNT(DISTINCT district) FROM prices").fetchone()[0]
        n_rdd_results = conn.execute("SELECT COUNT(*) FROM rdd_results").fetchone()[0]
        n_forecast_models = 0
        forecast_avg_mape = None
        try:
            fc_rows = conn.execute(
                "SELECT COUNT(*), AVG(test_mape) FROM forecast_metrics WHERE is_valid = 1 AND test_mape IS NOT NULL"
            ).fetchone()
            n_forecast_models = fc_rows[0] or 0
            forecast_avg_mape = round(fc_rows[1], 2) if fc_rows[1] is not None else None
        except Exception:
            pass
        n_rainfall = conn.execute("SELECT COUNT(*) FROM rainfall").fetchone()[0]
        n_ndvi = 0
        try:
            n_ndvi = conn.execute("SELECT COUNT(*) FROM ndvi").fetchone()[0]
        except Exception:
            pass
        return {
            "n_prices": n_prices,
            "n_commodities": n_commodities,
            "n_states": n_states,
            "n_districts": n_districts,
            "n_rdd_results": n_rdd_results,
            "n_forecast_models": n_forecast_models,
            "forecast_avg_mape": forecast_avg_mape,
            "n_rainfall": n_rainfall,
            "n_ndvi": n_ndvi,
        }
    finally:
        conn.close()


def _read_hourly_status() -> dict:
    """Read the last hourly ingestion status JSON."""
    p = Path(__file__).resolve().parent.parent / "data" / "last_hourly_run.json"
    if not p.exists():
        return {}
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return {}


@app.get("/pipeline/metrics.svg", tags=["System"])
async def pipeline_metrics_svg(
    fresh: bool = Query(False, alias="fresh"),
    bg: str = Query("", alias="bg"),
):
    """Serve the pipeline DAG as SVG with live KPI badge overlays.

    Composites real-time metrics (price rows, commodities, RDD results,
    forecast models, etc.) onto the pipeline diagram SVG.  The result
    can be used as a README badge, Grafana panel image, or CI status
    embed.

    Args:
        fresh: Force re-render from source (skip cache).
        bg: Optional background color override (CSS color).

    Returns:
        SVG with dimensions 1200xN (wider to accommodate badges).
    """
    try:
        base_svg = _render_pipeline_svg(force=fresh)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"Pipeline diagram not available. {e}")
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=f"Pipeline SVG rendering unavailable: {e}")

    # Gather live metrics
    metrics = _query_pipeline_metrics()
    hourly = _read_hourly_status()
    metrics["last_hourly_outcome"] = hourly.get("outcome")
    metrics["last_hourly_new_rows"] = hourly.get("new_price_rows")

    try:
        composited = _composite_kpi_svg(base_svg, metrics)
    except Exception as e:
        logger.warning(f"KPI badge compositing failed, falling back to bare SVG: {e}")
        composited = base_svg

    return Response(content=composited, media_type="image/svg+xml")


@app.get("/pipeline/metrics.json", tags=["System"])
async def pipeline_metrics_json():
    """Serve live pipeline KPIs as JSON (same data as the badge overlays).

    Useful for README badges, CI status checks, or programmatic consumers
    that want the metrics without the SVG wrapping.
    """
    metrics = _query_pipeline_metrics()
    hourly = _read_hourly_status()
    metrics["last_hourly_outcome"] = hourly.get("outcome")
    metrics["last_hourly_new_rows"] = hourly.get("new_price_rows")
    metrics["last_hourly_run_utc"] = hourly.get("last_run_utc")
    metrics["last_hourly_duration_s"] = hourly.get("duration_s")
    return metrics


# ── Prometheus /metrics endpoint ──
# Exposes lightweight service metrics in Prometheus text exposition format.
# No prometheus_client dependency required.

PROMETHEUS_METRICS_HEADER = {"Content-Type": "text/plain; version=0.0.4"}

@app.get("/metrics", tags=["System"], include_in_schema=False)
async def metrics():
    """Prometheus-compatible metrics endpoint (no prometheus_client library).

    Exposes service-level metrics in the Prometheus text exposition format
    so the service can be scraped by Prometheus, Grafana Agent, or any
    OpenMetrics-compatible collector.

    Adding new metrics:
        1. Define a gauge/counter line in the TEXT block below.
        2. Populate its value from the relevant module function.
        3. Ensure the metric name follows Prometheus naming conventions.
    """
    _uptime_sec = time.time() - health_stats.start_time
    _llm_fb = get_llm_fallback_count()

    lines = [
        "# HELP mandiiq_uptime_seconds Time since the API server started.",
        "# TYPE mandiiq_uptime_seconds gauge",
        f"mandiiq_uptime_seconds {_uptime_sec}",
        "",
        "# HELP mandiiq_llm_fallback_total Number of times call_llm() exhausted all models.",
        "# TYPE mandiiq_llm_fallback_total counter",
        f"mandiiq_llm_fallback_total {_llm_fb}",
        "",
        "# HELP mandiiq_health_checks_total Total health check requests.",
        "# TYPE mandiiq_health_checks_total counter",
        f"mandiiq_health_checks_total {health_stats.health_count}",
        "",
        "# HELP mandiiq_cold_starts_total Number of cold starts (server restarts) detected.",
        "# TYPE mandiiq_cold_starts_total counter",
        f"mandiiq_cold_starts_total {health_stats.cold_start}",
        "",
        "# HELP mandiiq_prices_count Current number of price records in the database.",
        "# TYPE mandiiq_prices_count gauge",
    ]

    # Try to read live prices count; emit -1 on failure (graceful degradation)
    try:
        conn = get_connection()
        n = conn.execute("SELECT COUNT(*) FROM prices").fetchone()[0]
        conn.close()
        lines.append(f"mandiiq_prices_count {n}")
    except Exception:
        lines.append("mandiiq_prices_count -1")

    # ---- Dashboard cache metrics ----
    lines.append("")
    lines.append("# HELP mandiiq_dashboard_cache_loaded Whether dashboard JSON is loaded (1=yes, 0=no).")
    lines.append("# TYPE mandiiq_dashboard_cache_loaded gauge")
    lines.append(f"mandiiq_dashboard_cache_loaded {1 if dashboard_json is not None else 0}")
    lines.append("# HELP mandiiq_dashboard_cache_last_refresh_timestamp_seconds Unix timestamp of last cache refresh.")
    lines.append("# TYPE mandiiq_dashboard_cache_last_refresh_timestamp_seconds gauge")
    lines.append(f"mandiiq_dashboard_cache_last_refresh_timestamp_seconds {_dashboard_last_refresh}")
    lines.append("# HELP mandiiq_dashboard_cache_file_mtime_timestamp_seconds Unix timestamp of dashboard file modification.")
    lines.append("# TYPE mandiiq_dashboard_cache_file_mtime_timestamp_seconds gauge")
    lines.append(f"mandiiq_dashboard_cache_file_mtime_timestamp_seconds {_dashboard_file_mtime}")
    lines.append("# HELP mandiiq_dashboard_cache_stale Whether file on disk is newer than loaded cache (1=stale, 0=fresh).")
    lines.append("# TYPE mandiiq_dashboard_cache_stale gauge")
    _stale = 0
    if dashboard_json is not None and _dashboard_file_mtime > 0 and os.path.exists(_dashboard_path):
        _stale = 1 if os.path.getmtime(_dashboard_path) > _dashboard_file_mtime else 0
    lines.append(f"mandiiq_dashboard_cache_stale {_stale}")
    lines.append("# HELP mandiiq_dashboard_cache_size Number of entries in the LRU dashboard cache.")
    lines.append("# TYPE mandiiq_dashboard_cache_size gauge")
    lines.append(f"mandiiq_dashboard_cache_size {_dashboard_patch_count if dashboard_json is not None else 0}")
    # ---- Disk usage metrics ----
    lines.append("")
    lines.append("# HELP mandiiq_disk_bytes Disk space usage for the mandiiq-api service filesystem.")
    lines.append("# TYPE mandiiq_disk_bytes gauge")
    try:
        _usage = shutil.disk_usage(".")
        lines.append(f'mandiiq_disk_bytes{{kind="total"}} {_usage.total}')
        lines.append(f'mandiiq_disk_bytes{{kind="used"}} {_usage.used}')
        lines.append(f'mandiiq_disk_bytes{{kind="free"}} {_usage.free}')
        _pct = round(_usage.used / _usage.total * 100, 2) if _usage.total > 0 else 0
        lines.append("# HELP mandiiq_disk_usage_percent Disk usage percentage for the mandiiq-api service.")
        lines.append("# TYPE mandiiq_disk_usage_percent gauge")
        lines.append(f"mandiiq_disk_usage_percent {_pct}")
    except Exception:
        lines.append('mandiiq_disk_bytes{kind="total"} -1')
        lines.append('mandiiq_disk_bytes{kind="used"} -1')
        lines.append('mandiiq_disk_bytes{kind="free"} -1')
        lines.append("# HELP mandiiq_disk_usage_percent Disk usage percentage for the mandiiq-api service.")
        lines.append("# TYPE mandiiq_disk_usage_percent gauge")
        lines.append("mandiiq_disk_usage_percent -1")

    # ---- R2 backup metrics ----
    lines.append("")
    lines.append("# HELP mandiiq_r2_backup_raw_bytes Size of the DuckDB before gzip compression.")
    lines.append("# TYPE mandiiq_r2_backup_raw_bytes gauge")
    lines.append("# HELP mandiiq_r2_backup_compressed_bytes Size of the gzip-compressed DuckDB backup in R2.")
    lines.append("# TYPE mandiiq_r2_backup_compressed_bytes gauge")
    lines.append("# HELP mandiiq_r2_backup_compression_pct Percentage size reduction from gzip compression.")
    lines.append("# TYPE mandiiq_r2_backup_compression_pct gauge")
    lines.append("# HELP mandiiq_r2_backup_timestamp_seconds Unix epoch of the last successful R2 backup.")
    lines.append("# TYPE mandiiq_r2_backup_timestamp_seconds gauge")
    try:
        _r2_path = Path(__file__).resolve().parent.parent / "data" / "r2_backup_metrics.json"
        if _r2_path.exists():
            with open(_r2_path) as _f:
                _r2_meta = json.load(_f)
            lines.append(f"mandiiq_r2_backup_raw_bytes {_r2_meta.get('raw_bytes', -1)}")
            lines.append(f"mandiiq_r2_backup_compressed_bytes {_r2_meta.get('compressed_bytes', -1)}")
            lines.append(f"mandiiq_r2_backup_compression_pct {_r2_meta.get('compression_pct', -1)}")
            _ts = _r2_meta.get('timestamp_epoch', -1)
            lines.append(f"mandiiq_r2_backup_timestamp_seconds {_ts}")
        else:
            lines.append("mandiiq_r2_backup_raw_bytes -1")
            lines.append("mandiiq_r2_backup_compressed_bytes -1")
            lines.append("mandiiq_r2_backup_compression_pct -1")
            lines.append("mandiiq_r2_backup_timestamp_seconds -1")
    except Exception:
        lines.append("mandiiq_r2_backup_raw_bytes -1")
        lines.append("mandiiq_r2_backup_compressed_bytes -1")
        lines.append("mandiiq_r2_backup_compression_pct -1")
        lines.append("mandiiq_r2_backup_timestamp_seconds -1")
    # ---- Pipeline Metrics (step durations, rows, API calls, runs) ----
    # These come from the in-memory pipeline_metrics singleton.
    try:
        from mandi_rdd.core.metrics import pipeline_metrics
        lines.append("")
        lines.append(pipeline_metrics.to_prometheus())
    except Exception:
        pass

    # ---- Data Growth & Forecast metrics (single DuckDB connection) ----
    lines.append("")
    try:
        conn2 = get_connection()
        n_comm = conn2.execute("SELECT COUNT(DISTINCT commodity) FROM prices").fetchone()[0]
        n_st = conn2.execute("SELECT COUNT(DISTINCT state) FROM prices WHERE state IS NOT NULL AND state != ''").fetchone()[0]
        n_dist = conn2.execute("SELECT COUNT(DISTINCT district) FROM prices WHERE district IS NOT NULL AND district != ''").fetchone()[0]
        n_rain = conn2.execute("SELECT COUNT(*) FROM rainfall").fetchone()[0]
        n_rdd_ = conn2.execute("SELECT COUNT(*) FROM rdd_results").fetchone()[0]
        # Forecast metrics
        fc_rows = conn2.execute(
            "SELECT commodity, test_mape, n_training_months, is_valid "
            "FROM forecast_metrics WHERE test_mape IS NOT NULL "
            "ORDER BY commodity"
        ).fetchall()
        n_fc = len(fc_rows)
        valid_map = [r[1] for r in fc_rows if r[3] == 1]
        n_valid = len(valid_map)
        avg_mape = round(sum(valid_map) / len(valid_map), 2) if valid_map else 0
        # NDVI
        try:
            nn = conn2.execute("SELECT COUNT(*) FROM ndvi").fetchone()[0]
            nd = conn2.execute("SELECT COUNT(DISTINCT district) FROM ndvi").fetchone()[0]
        except Exception:
            nn, nd = 0, 0
        conn2.close()

        # Data growth HELP/TYPE + values
        lines.append("# HELP mandiiq_commodities_count Number of distinct commodities in prices.")
        lines.append("# TYPE mandiiq_commodities_count gauge")
        lines.append(f"mandiiq_commodities_count {n_comm}")
        lines.append("# HELP mandiiq_states_count Number of distinct states in prices.")
        lines.append("# TYPE mandiiq_states_count gauge")
        lines.append(f"mandiiq_states_count {n_st}")
        lines.append("# HELP mandiiq_districts_count Number of distinct districts in prices.")
        lines.append("# TYPE mandiiq_districts_count gauge")
        lines.append(f"mandiiq_districts_count {n_dist}")
        lines.append("# HELP mandiiq_rainfall_count Number of rainfall records.")
        lines.append("# TYPE mandiiq_rainfall_count gauge")
        lines.append(f"mandiiq_rainfall_count {n_rain}")
        lines.append("# HELP mandiiq_rdd_results_count Number of RDD result records.")
        lines.append("# TYPE mandiiq_rdd_results_count gauge")
        lines.append(f"mandiiq_rdd_results_count {n_rdd_}")
        lines.append("# HELP mandiiq_ndvi_count Number of NDVI records.")
        lines.append("# TYPE mandiiq_ndvi_count gauge")
        lines.append(f"mandiiq_ndvi_count {nn}")
        lines.append("# HELP mandiiq_ndvi_districts_count Number of districts with NDVI data.")
        lines.append("# TYPE mandiiq_ndvi_districts_count gauge")
        lines.append(f"mandiiq_ndvi_districts_count {nd}")
        # Forecast HELP/TYPE + values
        lines.append("# HELP mandiiq_forecast_models_total Number of forecast models.")
        lines.append("# TYPE mandiiq_forecast_models_total gauge")
        lines.append(f"mandiiq_forecast_models_total {n_fc}")
        lines.append("# HELP mandiiq_forecast_valid_total Number of valid forecast models.")
        lines.append("# TYPE mandiiq_forecast_valid_total gauge")
        lines.append(f"mandiiq_forecast_valid_total {n_valid}")
        lines.append("# HELP mandiiq_forecast_avg_mape Average MAPE across valid forecast models.")
        lines.append("# TYPE mandiiq_forecast_avg_mape gauge")
        lines.append(f"mandiiq_forecast_avg_mape {avg_mape}")
        lines.append("# HELP mandiiq_forecast_mape Per-commodity forecast MAPE.")
        lines.append("# TYPE mandiiq_forecast_mape gauge")
        for r in fc_rows:
            _comm = r[0].replace('"', "'").replace("\\", "/")
            _mape = r[1] if r[1] is not None else 0
            lines.append(f'mandiiq_forecast_mape{{commodity="{_comm}"}} {_mape}')
    except Exception:
        # Fallback: emit all growth + forecast HELP/TYPE with -1 values
        for m in ["commodities_count", "states_count", "districts_count", "rainfall_count",
                  "rdd_results_count", "ndvi_count", "ndvi_districts_count",
                  "forecast_models_total", "forecast_valid_total", "forecast_avg_mape"]:
            lines.append(f"# HELP mandiiq_{m} ...")
            lines.append(f"# TYPE mandiiq_{m} gauge")
            lines.append(f"mandiiq_{m} -1")
        lines.append("# HELP mandiiq_forecast_mape ...")
        lines.append("# TYPE mandiiq_forecast_mape gauge")

    # ---- Full pipeline run status metrics (from last_ingest_status.json) ----
    lines.append("")
    lines.append("# HELP mandiiq_last_run_age_seconds Seconds since last full pipeline run.")
    lines.append("# TYPE mandiiq_last_run_age_seconds gauge")
    lines.append("# HELP mandiiq_last_run_duration_seconds Duration of last full pipeline run.")
    lines.append("# TYPE mandiiq_last_run_duration_seconds gauge")
    lines.append("# HELP mandiiq_last_run_new_rows Rows fetched in the last full pipeline run.")
    lines.append("# TYPE mandiiq_last_run_new_rows gauge")
    lines.append("# HELP mandiiq_last_run_outcome Outcome of last full pipeline run (1=success, 0=failure).")
    lines.append("# TYPE mandiiq_last_run_outcome gauge")
    try:
        ingest_path = Path(__file__).resolve().parent.parent / "data" / "last_ingest_status.json"
        if ingest_path.exists():
            with open(ingest_path) as f:
                ir = json.load(f)
            run_ts = ir.get("last_run_utc")
            age = 0
            if run_ts:
                try:
                    dt = datetime.datetime.fromisoformat(run_ts.replace("Z", "+00:00"))
                    age = time.time() - dt.timestamp()
                except Exception:
                    pass
            lines.append(f"mandiiq_last_run_age_seconds {max(0, age)}")
            lines.append(f"mandiiq_last_run_duration_seconds {ir.get('duration_s', 0)}")
            lines.append(f"mandiiq_last_run_new_rows {ir.get('new_price_rows', 0)}")
            outcome = 1 if ir.get("outcome") == "success" else 0
            lines.append(f"mandiiq_last_run_outcome {outcome}")
        else:
            lines.append("mandiiq_last_run_age_seconds -1")
            lines.append("mandiiq_last_run_duration_seconds -1")
            lines.append("mandiiq_last_run_new_rows -1")
            lines.append("mandiiq_last_run_outcome -1")
    except Exception:
        lines.append("mandiiq_last_run_age_seconds -1")
        lines.append("mandiiq_last_run_duration_seconds -1")
        lines.append("mandiiq_last_run_new_rows -1")
        lines.append("mandiiq_last_run_outcome -1")

    # ---- Hourly ingestion status metrics ----
    lines.append("")
    lines.append("# HELP mandiiq_hourly_run_age_seconds Seconds since last hourly ingestion run.")
    lines.append("# TYPE mandiiq_hourly_run_age_seconds gauge")
    lines.append("# HELP mandiiq_hourly_new_rows_total Rows fetched in the last hourly ingestion.")
    lines.append("# TYPE mandiiq_hourly_new_rows_total gauge")
    lines.append("# HELP mandiiq_hourly_duration_seconds Duration of the last hourly ingestion run.")
    lines.append("# TYPE mandiiq_hourly_duration_seconds gauge")
    lines.append("# HELP mandiiq_hourly_outcome Outcome of last hourly run (1=success, 0=failure).")
    lines.append("# TYPE mandiiq_hourly_outcome gauge")
    try:
        hourly_path = Path(__file__).resolve().parent.parent / "data" / "last_hourly_run.json"
        if hourly_path.exists():
            with open(hourly_path) as f:
                hr = json.load(f)
            run_ts = hr.get("last_run_utc")
            age = 0
            if run_ts:
                try:
                    dt = datetime.datetime.fromisoformat(run_ts.replace("Z", "+00:00"))
                    age = time.time() - dt.timestamp()
                except Exception:
                    pass
            lines.append(f"mandiiq_hourly_run_age_seconds {max(0, age)}")
            lines.append(f"mandiiq_hourly_new_rows_total {hr.get('new_price_rows', 0)}")
            lines.append(f"mandiiq_hourly_duration_seconds {hr.get('duration_s', 0)}")
            outcome = 1 if hr.get("outcome") == "success" else 0
            lines.append(f"mandiiq_hourly_outcome {outcome}")
        else:
            lines.append("mandiiq_hourly_run_age_seconds -1")
            lines.append("mandiiq_hourly_new_rows_total -1")
            lines.append("mandiiq_hourly_duration_seconds -1")
            lines.append("mandiiq_hourly_outcome -1")
    except Exception:
        lines.append("mandiiq_hourly_run_age_seconds -1")
        lines.append("mandiiq_hourly_new_rows_total -1")
        lines.append("mandiiq_hourly_duration_seconds -1")
        lines.append("mandiiq_hourly_outcome -1")

    body = "\n".join(lines) + "\n"
    return Response(content=body, media_type=PROMETHEUS_METRICS_HEADER["Content-Type"])



@app.post("/deploy", tags=["System"])
async def deploy():
    """Trigger a Render deploy via the RENDER_DEPLOY_HOOK_URL.
    POSTs to the Render deploy hook URL set in the RENDER_DEPLOY_HOOK_URL
    environment variable. This triggers a new deploy of the mandiiq-api
    service on Render, picking up the latest DuckDB from git.
    The deploy hook URL is a one-time generated secret URL from the Render
    dashboard (Settings -> Deploy Hooks). If not set, returns a warning.
    Returns:
        dict with status, message, and optional HTTP status code from Render.
    """
    global _last_deploy_ts
    now = time.time()
    if now - _last_deploy_ts < _DEPLOY_COOLDOWN_S:
        remaining = round(_DEPLOY_COOLDOWN_S - (now - _last_deploy_ts), 1)
        return {
            "status": "cooldown",
            "message": f"Deploy skipped: {remaining}s remaining in cooldown ({_DEPLOY_COOLDOWN_S}s)",
        }
    hook_url = os.environ.get("RENDER_DEPLOY_HOOK_URL", "")
    if not hook_url:
        logger.warning("Deploy requested but RENDER_DEPLOY_HOOK_URL not set")
        return {
            "status": "skipped",
            "message": "RENDER_DEPLOY_HOOK_URL not set. Generate one at "
                       "dashboard.render.com and add it as an env var.",
        }
    try:
        req = urllib.request.Request(
            hook_url,
            data=b"{}",
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            _last_deploy_ts = time.time()
            logger.info("Deploy triggered via /deploy endpoint (HTTP %s)", resp.status)
            return {
                "status": "ok",
                "message": "Render deploy triggered successfully.",
                "http_status": resp.status,
                "response": body[:500] if body else "",
            }
    except urllib.error.HTTPError as e:
        return {
            "status": "error",
            "message": f"Render returned HTTP {e.code}: {e.reason}",
            "http_status": e.code,
        }
    except (TimeoutError, urllib.error.URLError, OSError) as e:
        return {
            "status": "error",
            "message": f"Failed to reach Render deploy hook: {e}",
        }


@app.get('/proxy/github/{path:path}', tags=['Proxy'])
def proxy_github(path: str, request: Request):
    """Proxy requests to GitHub API to avoid CORS issues from browser."""
    query = request.url.query
    github_token = os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_TOKEN')
    headers = {
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': 'MandiIQ-API/1.0',
    }
    if github_token:
        headers['Authorization'] = f'Bearer {github_token}'
    url = f'https://api.github.com/{path}'
    if query:
        url += '?' + query
    try:
        req = urllib.request.Request(url, headers=headers, method='GET')
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode('utf-8')
            return JSONResponse(content=json.loads(body))
    except urllib.error.HTTPError as e:
        try:
            err_body = json.loads(e.read().decode('utf-8'))
        except Exception:
            err_body = {'error': e.reason}
        return JSONResponse(status_code=e.code, content=err_body)
    except Exception as e:
        return JSONResponse(status_code=502, content={'error': str(e)})
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("mandi_rdd.api.main:app", host="0.0.0.0", port=port, reload=True)
