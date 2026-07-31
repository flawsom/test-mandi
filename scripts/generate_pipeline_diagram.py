#!/usr/bin/env python3
"""
generate_pipeline_diagram.py -- MandiIQ Live Pipeline DAG Generator

Queries the DuckDB for current row counts, forecast-model status, RDD results,
and reads persisted timing files (last_hourly_run.json, last_step_timings.json,
last_ingest_status.json, last_integrity_check.json) to generate a Mermaid
flowchart that shows exactly which steps ran and how long each took in the
*last successful cycle*.

Usage:
    python scripts/generate_pipeline_diagram.py          # write to diagrams/pipeline-flow-live.mmd
    python scripts/generate_pipeline_diagram.py --stdout  # print to terminal
    python scripts/generate_pipeline_diagram.py --help    # show options

Output:
    diagrams/pipeline-flow-live.mmd  (or stdout with --stdout)
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# -- Project paths --
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "mandi_rdd" / "data"
DIAGRAMS_DIR = PROJECT_ROOT / "diagrams"

sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("MANDIIQ_DB_PATH", str(DATA_DIR / "mandi_iq.duckdb"))


# ---------------------------------------------------------------------------
# Formatting helpers (all return ASCII-only strings -- safe for cp1252/Mermaid)
# ---------------------------------------------------------------------------

def fmt_num(n):
    """1,333,993"""
    if n is None:
        return "-"
    return f"{n:,}"


def fmt_duration(s):
    """12.5 -> '12.5s',  125 -> '2m 5s'"""
    if s is None or s == 0:
        return "-"
    s = float(s)
    if s < 60:
        return f"{s:.1f}s"
    m, sec = divmod(s, 60)
    return f"{int(m)}m {sec:.0f}s"


def fmt_mape(v):
    """8.4 -> '8.4%'"""
    if v is None:
        return "-"
    return f"{float(v):.1f}%"


def esc(txt):
    """Escape text for Mermaid node labels (quotes, pipes, brackets).

    Only strips characters that actually break Mermaid syntax.  Keeps all
    UTF-8 printable characters (middle-dot, em-dash, etc.) since modern
    Mermaid renderers (GitHub, mermaid-cli) handle them fine.
    """
    if txt is None:
        return "--"
    txt = str(txt)
    txt = txt.replace('"', "'")
    txt = txt.replace("{", "(")
    txt = txt.replace("}", ")")
    txt = txt.replace("`", "'")
    return txt


# ---------------------------------------------------------------------------
# Data collectors
# ---------------------------------------------------------------------------

def query_duckdb():
    """Query the DuckDB for current state.  Returns a dict of facts."""
    facts = {
        "n_prices": None,
        "n_commodities": None,
        "n_states": None,
        "n_districts": None,
        "n_rainfall": None,
        "n_rainfall_subs": None,
        "rainfall_year_min": None,
        "rainfall_year_max": None,
        "n_ndvi": None,
        "n_ndvi_districts": None,
        "n_district_map": None,
        "n_backfill_updated": None,
        "n_backfill_empty": None,
        "n_rdd": None,
        "n_fe_effects": None,
        "n_forecast": None,
        "forecast_summary": [],
        "forecast_valid": 0,
        "forecast_noisy": 0,
        "forecast_noisy_list": [],
        "n_lineage": None,
        "n_lineage_sources": None,
        "n_narratives": None,
        "earliest_date": None,
        "latest_date": None,
    }
    try:
        from mandi_rdd.storage.duckdb_store import get_connection
        conn = get_connection(read_only=True)

        row = conn.execute("SELECT count(*) FROM prices").fetchone()
        facts["n_prices"] = row[0] if row else 0

        row = conn.execute("SELECT count(DISTINCT commodity) FROM prices").fetchone()
        facts["n_commodities"] = row[0] if row else 0

        row = conn.execute(
            "SELECT count(DISTINCT state) FROM prices WHERE state IS NOT NULL AND state != ''"
        ).fetchone()
        facts["n_states"] = row[0] if row else 0

        row = conn.execute(
            "SELECT count(DISTINCT district) FROM prices WHERE district IS NOT NULL AND district != ''"
        ).fetchone()
        facts["n_districts"] = row[0] if row else 0

        row = conn.execute("SELECT min(arrival_date), max(arrival_date) FROM prices").fetchone()
        facts["earliest_date"] = str(row[0]) if row and row[0] else None
        facts["latest_date"] = str(row[1]) if row and row[1] else None

        # Rainfall
        try:
            row = conn.execute("SELECT count(*) FROM rainfall").fetchone()
            facts["n_rainfall"] = row[0] if row else 0
            row = conn.execute("SELECT count(DISTINCT sub_division) FROM rainfall").fetchone()
            facts["n_rainfall_subs"] = row[0] if row else 0
            row = conn.execute("SELECT min(year), max(year) FROM rainfall").fetchone()
            if row:
                facts["rainfall_year_min"] = row[0]
                facts["rainfall_year_max"] = row[1]
        except Exception:
            pass

        # NDVI
        try:
            row = conn.execute("SELECT count(*) FROM ndvi").fetchone()
            facts["n_ndvi"] = row[0] if row else 0
            row = conn.execute("SELECT count(DISTINCT district) FROM ndvi").fetchone()
            facts["n_ndvi_districts"] = row[0] if row else 0
        except Exception:
            pass

        # District map
        try:
            row = conn.execute("SELECT count(*) FROM district_map").fetchone()
            facts["n_district_map"] = row[0] if row else 0
        except Exception:
            pass

        # Backfill state: rows still with empty state
        try:
            row = conn.execute(
                "SELECT count(*) FROM prices WHERE state IS NULL OR state = ''"
            ).fetchone()
            facts["n_backfill_empty"] = row[0] if row else 0
            row = conn.execute(
                "SELECT count(*) FROM prices WHERE state IS NOT NULL AND state != ''"
            ).fetchone()
            facts["n_backfill_updated"] = row[0] if row else 0
        except Exception:
            pass

        # RDD results
        try:
            row = conn.execute("SELECT count(*) FROM rdd_results").fetchone()
            facts["n_rdd"] = row[0] if row else 0
        except Exception:
            pass

        # Fixed-effects cross-check results
        try:
            row = conn.execute(
                "SELECT count(*) FROM rdd_results WHERE fe_effect IS NOT NULL"
            ).fetchone()
            facts["n_fe_effects"] = row[0] if row else 0
        except Exception:
            pass

        # Forecast metrics
        try:
            rows = conn.execute(
                "SELECT commodity, test_mape, n_training_months, model, is_valid "
                "FROM forecast_metrics WHERE test_mape IS NOT NULL "
                "ORDER BY test_mape"
            ).fetchall()
            facts["n_forecast"] = len(rows)
            valid = 0
            noisy = 0
            noisy_list = []
            for r in rows:
                commodity, mape, months, model, is_valid = r
                facts["forecast_summary"].append({
                    "commodity": commodity,
                    "mape": mape,
                    "months": months,
                    "model": model,
                    "valid": is_valid,
                })
                if (is_valid == 1) or (mape is not None and mape <= 500):
                    valid += 1
                if mape is not None and mape > 500:
                    noisy += 1
                    noisy_list.append(commodity)
            facts["forecast_valid"] = valid
            facts["forecast_noisy"] = noisy
            facts["forecast_noisy_list"] = noisy_list
        except Exception as e:
            print(f"  [diagram] forecast query warning: {e}", file=sys.stderr)

        # Narratives
        try:
            row = conn.execute("SELECT count(*) FROM narratives").fetchone()
            facts["n_narratives"] = row[0] if row else 0
        except Exception:
            pass

        # Data lineage
        try:
            row = conn.execute("SELECT count(*) FROM data_lineage").fetchone()
            facts["n_lineage"] = row[0] if row else 0
            row = conn.execute(
                "SELECT count(DISTINCT source_type) FROM data_lineage"
            ).fetchone()
            facts["n_lineage_sources"] = row[0] if row else 0
        except Exception:
            pass

        conn.close()
    except Exception as e:
        print(f"  [diagram] DuckDB query failed: {e}", file=sys.stderr)

    return facts


def read_json(path):
    """Read a JSON file safely, return None on failure."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


# ---------------------------------------------------------------------------
# Per-step timing helpers
# ---------------------------------------------------------------------------

# Map step names from pipeline_metrics to display labels for the diagram nodes.
_STEP_LABEL_MAP = {
    "historical_backfill": "historical_backfill",
    "fetch_prices":         "fetch_prices",
    "upsert_prices":        "upsert_prices",
    "prices_varietywise":   "varietywise_archive",
    "backfill_state":       "backfill_state",
    "fetch_rainfall":       "fetch_rainfall",
    "fetch_ndvi":           "fetch_ndvi",
    "rdd_analysis":         "rdd_analysis",
    "forecast_training":    "forecast_training",
    "forecast_persist":     "forecast_persist",
    "classifier_training":  "classifier_training",
    "nightly_narratives":   "nightly_narratives",
}


def load_step_timings():
    """Read last_step_timings.json and return {step_label: duration_s}."""
    raw = read_json(DATA_DIR / "last_step_timings.json")
    if not raw:
        return {}
    steps = raw.get("steps", {})
    result = {}
    for key, dur in steps.items():
        label = _STEP_LABEL_MAP.get(key, key)
        result[label] = dur
    return result


def duration_tag(dur):
    """Return a small HTML snippet showing the duration, or empty string."""
    if dur is None:
        return ""
    return f"<span style='color:#7e7e7e;font-size:10px;'>[{fmt_duration(dur)}]</span>"


# ---------------------------------------------------------------------------
# Mermaid diagram builder
# ---------------------------------------------------------------------------


def build_mermaid(facts, hourly_status, ingest_status, integrity, step_timings):
    """Build the Mermaid flowchart string from live data."""

    # ---- Timing data from the last run ----
    last_run_utc = None
    last_duration = None
    last_outcome = "-"

    if hourly_status:
        last_run_utc = hourly_status.get("last_run_utc")
        last_duration = hourly_status.get("duration_s")
        last_outcome = hourly_status.get("outcome", "-")
    elif ingest_status:
        last_run_utc = ingest_status.get("last_run_utc")
        last_duration = ingest_status.get("duration_s")
        last_outcome = ingest_status.get("outcome", "-")

    run_ts_display = "-"
    if last_run_utc:
        try:
            dt = datetime.fromisoformat(last_run_utc.replace("Z", "+00:00"))
            run_ts_display = dt.strftime("%Y-%m-%d %H:%M UTC")
        except (ValueError, AttributeError):
            run_ts_display = str(last_run_utc)[:19]

    integrity_overall = "-"
    if integrity:
        integrity_overall = integrity.get("overall", "-")

    # ---- Pull per-step timing ----
    t_fetch    = step_timings.get("fetch_prices")
    t_variety  = step_timings.get("varietywise_archive")
    t_rain     = step_timings.get("fetch_rainfall")
    t_ndvi     = step_timings.get("fetch_ndvi")
    t_hist     = step_timings.get("historical_backfill")
    t_distmap  = None  # no separate pipeline_metrics step for district_map
    t_backfill = step_timings.get("backfill_state")
    t_rdd      = step_timings.get("rdd_analysis")
    t_fe       = None  # FE runs inside rdd_analysis step
    t_fc       = step_timings.get("forecast_training")
    t_cls      = step_timings.get("classifier_training")
    t_narr     = step_timings.get("nightly_narratives")
    t_lineage  = None  # lineage recording is inline in ingestion steps

    # ---- Build node labels ----
    np = facts["n_prices"] or 0

    s1_fetch = (
        f"fetch_prices.py<br/>data.gov.in API {duration_tag(t_fetch)}<br/>"
        f"<b>{fmt_num(np)}</b> records ingested<br/>"
        f"<i>{fmt_num(facts['n_commodities'])} commodities ~ {fmt_num(facts['n_states'])} states</i>"
    )
    s1_rain = (
        f"fetch_rainfall.py<br/>IMD Grids {duration_tag(t_rain)}<br/>"
        f"<b>{fmt_num(facts['n_rainfall'])}</b> records<br/>"
        f"<i>{fmt_num(facts['n_rainfall_subs'])} sub-divisions ~ "
        f"{facts['rainfall_year_min'] or '-'}--{facts['rainfall_year_max'] or '-'}</i>"
    )
    s1_ndvi = (
        f"fetch_ndvi.py<br/>Sentinel Hub {duration_tag(t_ndvi)}<br/>"
        f"<b>{fmt_num(facts['n_ndvi'])}</b> vegetation records<br/>"
        f"<i>{fmt_num(facts['n_ndvi_districts'])} districts</i>"
    )
    s1_hist = (
        f"ingest_historical_csv.py {duration_tag(t_hist)}<br/>"
        f"CSV backfill ~ Ashoka archive"
    )
    s1_variety = (
        f"prices_varietywise.py<br/>Archive scanner {duration_tag(t_variety)}<br/>"
        f"Supplementary 60d recent prices<br/>"
        f"<i>Resource 35985678</i>"
    )
    s1_distmap = (
        f"district_map.py<br/>Sub-division mapping {duration_tag(t_distmap)}<br/>"
        f"<b>{fmt_num(facts['n_district_map'])}</b> mappings loaded<br/>"
        f"<i>State -> District -> Sub-division</i>"
    )
    s1_backfill = (
        f"backfill_state.py {duration_tag(t_backfill)}<br/>"
        f"State name resolution<br/>"
        f"<b>{fmt_num(facts['n_backfill_updated'])}</b> rows populated<br/>"
        f"<i>{fmt_num(facts['n_backfill_empty'])} rows still empty</i>"
    )
    s1_lineage = (
        f"data_lineage.py<br/>Provenance tracking {duration_tag(t_lineage)}<br/>"
        f"<b>{fmt_num(facts['n_lineage'])}</b> records<br/>"
        f"<i>{fmt_num(facts['n_lineage_sources'])} source types: "
        f"prices, varietywise, rainfall</i>"
    )

    s2_duck = (
        f"DuckDB Warehouse<br/>mandi_iq.duckdb<br/>"
        f"<b>{fmt_num(np)}</b> prices ~ <b>{fmt_num(facts['n_rainfall'])}</b> rainfall<br/>"
        f"<b>{fmt_num(facts['n_ndvi'])}</b> NDVI ~ <b>{fmt_num(facts['n_forecast'])}</b> forecast models"
    )

    rdd_count = facts["n_rdd"] or 0
    s3_rdd = (
        f"rdd_engine.py {duration_tag(t_rdd)}<br/>"
        f"Local linear RDD<br/>"
        f"<b>{rdd_count}</b> causal estimates<br/>"
        f"Triangular kernel ~ McCrary test"
    )
    fe_count = facts["n_fe_effects"] or 0
    s3_fe = (
        f"fixed_effects.py {duration_tag(t_fe)}<br/>"
        f"FE cross-check<br/>"
        f"<b>{fe_count}</b> effects with FE<br/>"
        f"District + month fixed effects"
    )

    fc_valid = facts["forecast_valid"]
    fc_noisy = facts["forecast_noisy"]
    fc_best = ""
    if facts["forecast_summary"]:
        best_mape = min(
            (f["mape"] for f in facts["forecast_summary"] if f["mape"] is not None),
            default=None,
        )
        if best_mape is not None and best_mape < 500:
            best_comm = next(
                (f["commodity"] for f in facts["forecast_summary"] if f["mape"] == best_mape),
                "",
            )
            fc_best = f"Best: {best_comm} @ {fmt_mape(best_mape)}"
    s3_fc = (
        f"forecast.py {duration_tag(t_fc)}<br/>"
        f"Seasonal naive + ensemble<br/>"
        f"<b>{facts['n_forecast']}</b> models"
    )
    if fc_valid:
        s3_fc += f"<br/><span style='color:#8FAE89'>[OK] {fc_valid} valid</span>"
        if fc_noisy:
            s3_fc += f" <span style='color:#D9663B'>[!] {fc_noisy} noisy</span>"
    if fc_best:
        s3_fc += f"<br/>{fc_best}"

    s3_cls = (
        f"classifier.py {duration_tag(t_cls)}<br/>"
        f"XGBoost + SHAP<br/>"
        f"Price spike risk scoring<br/>"
        f"ROC-AUC tracking"
    )
    s3_presc = (
        f"prescriptive.py<br/>"
        f"Procurement recommendations<br/>"
        f"RDD-grounded ~ Confidence scoring"
    )

    narr_count = facts["n_narratives"] or 0
    s4_router = "router.py<br/>Multi-provider LLM<br/>Circuit breaker ~ Fallback chain"
    s4_orch = "orchestrator.py<br/>Tool-grounding<br/>Endpoint selection"
    s4_narr = (
        f"nightly narratives<br/>"
        f"<b>{narr_count}</b> commodity reports<br/>"
        f"AI-generated summaries"
    )

    s5_api = (
        f"FastAPI Gateway<br/>"
        f"10+ REST endpoints<br/>"
        f"/health ~ /prices ~ /forecast<br/>"
        f"/rdd-result ~ /risk-score ~ /ask"
    )
    s5_dash = (
        f"Streamlit Dashboard<br/>"
        f"5 interactive pages<br/>"
        f"Executive ~ Forecast ~ Satellite<br/>"
        f"Discontinuity ~ Risk Map"
    )

    outcome_color = "#8FAE89" if last_outcome == "success" else "#D9663B"
    title = (
        f"MandiIQ Pipeline Flow -- Last Successful Cycle<br/>"
        f"<span style='font-size:11px;color:#7e7e7e;'>"
        f"{run_ts_display} ~ {fmt_duration(last_duration)} total ~ "
        f"Outcome: <b style='color:{outcome_color}'>{last_outcome}</b>"
        f"</span>"
    )

    # ---- Assemble the Mermaid diagram ----
    # YAML front-matter title must be double-quoted: the title embeds HTML
    # with a colon-space ("Outcome: <b>...</b>") which is an illegal plain
    # scalar in YAML and makes mermaid-cli throw a YAMLException.
    yaml_title = title.replace('\\', '\\\\').replace('"', '\\"')
    mermaid = f"""---
title: "{yaml_title}"
---
%%{{init: {{
  "theme": "dark",
  "themeVariables": {{
    "primaryColor": "#1a1a2e",
    "primaryTextColor": "#ffffff",
    "primaryBorderColor": "#d7ff00",
    "lineColor": "#d7ff00",
    "secondaryColor": "#16213e",
    "tertiaryColor": "#0f3460",
    "mainBkg": "#0d0d1a",
    "nodeBorder": "#533483",
    "clusterBkg": "#0a0a12",
    "clusterBorder": "#2a2a4a",
    "titleColor": "#d7ff00",
    "edgeLabelBackground": "#0d0d1a",
    "nodeTextColor": "#ffffff",
    "fontFamily": "\\"Space Grotesk\\", \\"Inter\\", sans-serif"
  }},
  "flowchart": {{
    "useMaxWidth": true,
    "htmlLabels": true,
    "curve": "basis",
    "padding": 20
  }}
}}%%
flowchart TD
    %% Stage 1: DATA INGESTION
    subgraph S1["01 DATA INGESTION  | API + Archive + Satellite + Backfill + Provenance"]
        direction TB
        A1["{esc(s1_fetch)}"]
        A2["{esc(s1_variety)}"]
        A3["{esc(s1_rain)}"]
        A4["{esc(s1_ndvi)}"]
        A5["{esc(s1_hist)}"]
        A6["{esc(s1_distmap)}"]
        A7["{esc(s1_backfill)}"]
        A8["{esc(s1_lineage)}"]
    end

    %% Stage 2: DUCKDB WAREHOUSE
    subgraph S2["02 DUCKDB WAREHOUSE  | Persistent Volume /data"]
        B1["{esc(s2_duck)}"]
    end

    %% Stage 3: ANALYSIS & ML
    subgraph S3["03 ANALYSIS & ML  | Causal + FE + Forecast + Risk"]
        direction TB
        C1["{esc(s3_rdd)}"]
        C2["{esc(s3_fe)}"]
        C3["{esc(s3_fc)}"]
        C4["{esc(s3_cls)}"]
        C5["{esc(s3_presc)}"]
    end

    %% Stage 4: AI ORCHESTRATOR
    subgraph S4["04 AI ORCHESTRATOR  | Multi-Model Router"]
        D1["{esc(s4_router)}"]
        D2["{esc(s4_orch)}"]
        D3["{esc(s4_narr)}"]
    end

    %% Stage 5: SERVING
    subgraph S5["05 SERVING  | Live Deployment"]
        E1["{esc(s5_api)}"]
        E2["{esc(s5_dash)}"]
    end

    %% Main flow: ingestion -> warehouse
    A1 ==> B1
    A2 -.-> B1
    A3 -.-> B1
    A4 -.-> B1
    A5 -.-> B1
    A6 -.-> B1
    A7 -.-> B1

    %% Main flow: ingestion -> provenance tracking
    A1 -.-> A8
    A2 -.-> A8
    A3 -.-> A8
    A8 -.-> B1

    %% Main flow: warehouse -> analysis
    B1 ==> C1
    B1 -.-> C2
    B1 ==> C3
    B1 ==> C4

    %% Main flow: analysis -> prescriptive -> AI
    C1 ==> C5
    C2 -.-> C5
    C3 ==> C5
    C4 ==> C5

    C5 ==> D1
    D1 ==> D2
    D2 ==> D3
    D3 ==> E1

    E1 <==> E2

    %% Edge styling: thick = primary path
    linkStyle 0,11,13,14,15,17,18,19 stroke-width:4px,stroke:#d7ff00,fill:none
    linkStyle 1,2,3,4,5,6,7,8,9,10,12,16,20,21,22 stroke-width:2px,stroke:#533483,fill:none
    linkStyle 23 stroke-width:3px,stroke:#e94560,fill:none

    %% Stage classes
    classDef stage1 fill:#1a1a2e,stroke:#e94560,stroke-width:3px,color:#fff
    classDef stage1Node fill:#1f1f3a,stroke:#e94560,stroke-width:2px,color:#fff

    classDef stage2 fill:#16213e,stroke:#0f3460,stroke-width:2px,color:#fff
    classDef stage2Node fill:#1a2a4a,stroke:#0f3460,stroke-width:1px,color:#ddd

    classDef stage3 fill:#2d1b69,stroke:#d7ff00,stroke-width:3px,color:#fff
    classDef stage3Node fill:#3d1b79,stroke:#d7ff00,stroke-width:2px,color:#fff

    classDef stage4 fill:#1a0a2e,stroke:#e94560,stroke-width:2px,color:#fff
    classDef stage4Node fill:#2a0a3e,stroke:#e94560,stroke-width:2px,color:#ddd

    classDef stage5 fill:#0f1a2e,stroke:#d7ff00,stroke-width:3px,color:#fff
    classDef stage5Node fill:#1a2a4e,stroke:#d7ff00,stroke-width:2px,color:#fff

    class S1 stage1
    class A1,A2,A3,A4,A5,A6,A7,A8 stage1Node

    class S2 stage2
    class B1 stage2Node

    class S3 stage3
    class C1,C2,C3,C4,C5 stage3Node

    class S4 stage4
    class D1,D2,D3 stage4Node

    class S5 stage5
    class E1,E2 stage5Node
"""
    return mermaid


# ---------------------------------------------------------------------------
# Docs variant (GitHub-safe, pre-rendered to SVG for the .md docs)
# ---------------------------------------------------------------------------


def build_docs_mermaid(facts, hourly_status, ingest_status, integrity, step_timings):
    """Build the GitHub-safe simplified pipeline diagram (docs embed variant).

    Same topology as the full diagram but a compact ``graph LR`` with live
    row counts, safe for GitHub's bundled mermaid renderer (no emoji, no "&"
    in subgraph titles, no ">" or arrow characters in labels). This is the
    source that gets pre-rendered to ``docs/assets/svg/pipeline-flow-live.svg``
    by the hourly pipeline.
    """
    np = facts["n_prices"] or 0
    n_comm = facts["n_commodities"] or 0
    n_states = facts["n_states"] or 0
    n_rain = facts["n_rainfall"] or 0
    n_rain_subs = facts["n_rainfall_subs"] or 0
    rain_years = (
        f"{facts['rainfall_year_min'] or '-'}--{facts['rainfall_year_max'] or '-'}"
    )
    n_ndvi = facts["n_ndvi"] or 0
    n_ndvi_dist = facts["n_ndvi_districts"] or 0
    n_rdd = facts["n_rdd"] or 0
    n_fc = facts["n_forecast"] or 0

    fc_valid = facts.get("forecast_valid") or 0
    fc_noisy = facts.get("forecast_noisy") or 0
    fc_best = ""
    if facts.get("forecast_summary"):
        best_mape = min(
            (f["mape"] for f in facts["forecast_summary"] if f["mape"] is not None),
            default=None,
        )
        if best_mape is not None and best_mape < 500:
            best_comm = next(
                (f["commodity"] for f in facts["forecast_summary"] if f["mape"] == best_mape),
                "",
            )
            fc_best = f"<br/>Best: {esc(best_comm)} @ {fmt_mape(best_mape)}"

    # Last-run metadata
    last_run_utc = None
    last_duration = None
    last_outcome = "-"
    if hourly_status:
        last_run_utc = hourly_status.get("last_run_utc")
        last_duration = hourly_status.get("duration_s")
        last_outcome = hourly_status.get("outcome", "-")
    elif ingest_status:
        last_run_utc = ingest_status.get("last_run_utc")
        last_duration = ingest_status.get("duration_s")
        last_outcome = ingest_status.get("outcome", "-")

    run_ts_display = "-"
    if last_run_utc:
        try:
            dt = datetime.fromisoformat(str(last_run_utc).replace("Z", "+00:00"))
            run_ts_display = dt.strftime("%Y-%m-%d %H:%M UTC")
        except (ValueError, AttributeError):
            run_ts_display = str(last_run_utc)[:19]

    gen_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    mermaid = f"""%% Auto-generated by scripts/generate_pipeline_diagram.py -- {gen_ts}
%% Last cycle: {run_ts_display} ~ {fmt_duration(last_duration)} ~ outcome {last_outcome}
graph LR
    subgraph Ingest["01 DATA INGESTION | Live API + Satellite + Archive"]
        A["data.gov.in API<br/>{fmt_num(np)} records<br/>{fmt_num(n_comm)} commodities - {fmt_num(n_states)} states"]
        B["IMD Rainfall Grids<br/>{fmt_num(n_rain)} records<br/>{fmt_num(n_rain_subs)} sub-divisions - {rain_years}"]
        C["Sentinel Hub NDVI<br/>{fmt_num(n_ndvi)} vegetation records<br/>{fmt_num(n_ndvi_dist)} districts"]
    end
    subgraph Store["02 DUCKDB WAREHOUSE | Persistent Volume /data"]
        D["mandi_iq.duckdb<br/>{fmt_num(np)} prices - {fmt_num(n_rain)} rainfall<br/>{fmt_num(n_ndvi)} NDVI - {fmt_num(n_fc)} forecast models"]
    end
    subgraph Analyze["03 ANALYSIS AND ML | Causal + Forecast + Risk"]
        E["RDD Engine<br/>{fmt_num(n_rdd)} causal estimates<br/>Triangular kernel - McCrary test"]
        F["Forecast Engine<br/>{fmt_num(n_fc)} models - {fc_valid} valid, {fc_noisy} noisy{fc_best}"]
        G["Spike Classifier<br/>XGBoost + SHAP<br/>Risk scoring"]
        H["Prescriptive<br/>Procurement recommendations"]
    end
    subgraph Serve["04 SERVING | Live Deployment"]
        I["FastAPI Gateway<br/>10+ REST endpoints"]
        J["Streamlit Dashboard<br/>5 interactive pages"]
    end
    A --> D
    B --> D
    C --> D
    D --> E
    D --> F
    D --> G
    E --> H
    F --> H
    G --> H
    H --> I
    I <--> J
"""
    return mermaid


def generate_docs(output_path=None, stdout=False):
    """Generate the GitHub-safe docs-variant pipeline diagram.

    Writes to ``docs/assets/mermaid/pipeline-flow-live.mmd`` by default so the
    docs' pre-rendered SVG source stays in sync with live DuckDB counts.
    """
    facts = query_duckdb()
    hourly_status = read_json(DATA_DIR / "last_hourly_run.json")
    ingest_status = read_json(DATA_DIR / "last_ingest_status.json")
    integrity = read_json(DATA_DIR / "last_integrity_check.json")
    step_timings = load_step_timings()

    diagram = build_docs_mermaid(facts, hourly_status, ingest_status, integrity, step_timings)

    if stdout:
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
        print(diagram)

    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(diagram, encoding="utf-8")
        print(f"  [docs-diagram] Written {len(diagram):,} bytes -> {output_path}", file=sys.stderr)

    return diagram


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def generate(output_path=None, stdout=False):
    """Generate the pipeline diagram and write to file and/or stdout."""

    facts = query_duckdb()
    hourly_status = read_json(DATA_DIR / "last_hourly_run.json")
    ingest_status = read_json(DATA_DIR / "last_ingest_status.json")
    integrity = read_json(DATA_DIR / "last_integrity_check.json")
    step_timings = load_step_timings()

    diagram = build_mermaid(facts, hourly_status, ingest_status, integrity, step_timings)

    if stdout:
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
        print(diagram)

    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(diagram, encoding="utf-8")
        print(f"  [diagram] Written {len(diagram):,} bytes -> {output_path}", file=sys.stderr)

    print(file=sys.stderr)
    print(f"  [diagram] Data snapshot:", file=sys.stderr)
    print(f"    Prices: {fmt_num(facts['n_prices'])} rows, {fmt_num(facts['n_commodities'])} commodities, {fmt_num(facts['n_states'])} states", file=sys.stderr)
    print(f"    Rainfall: {fmt_num(facts['n_rainfall'])} records, {fmt_num(facts['n_rainfall_subs'])} sub-divisions", file=sys.stderr)
    print(f"    NDVI: {fmt_num(facts['n_ndvi'])} records, {fmt_num(facts['n_ndvi_districts'])} districts", file=sys.stderr)
    print(f"    RDD: {facts['n_rdd']} results", file=sys.stderr)
    print(f"    Forecast: {facts['n_forecast']} models ({facts['forecast_valid']} valid, {facts['forecast_noisy']} noisy)", file=sys.stderr)
    print(f"    Narratives: {facts['n_narratives']} reports", file=sys.stderr)
    if step_timings:
        print(f"    Step timings: {len(step_timings)} steps persisted", file=sys.stderr)
        for step, dur in sorted(step_timings.items()):
            print(f"      {step}: {fmt_duration(dur)}", file=sys.stderr)

    if facts["forecast_noisy_list"]:
        print(f"    Noisy (>500% MAPE): {', '.join(facts['forecast_noisy_list'])}", file=sys.stderr)

    if integrity:
        print(f"    Integrity: {integrity.get('overall', '-')}", file=sys.stderr)

    return diagram


def main():
    parser = argparse.ArgumentParser(
        description="Generate MandiIQ pipeline flow diagram with live timing data."
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Print Mermaid diagram to stdout instead of writing to file",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help=(
            f"Output path for the full diagram (default: "
            f"{DIAGRAMS_DIR / 'pipeline-flow-live.mmd'} when no --docs-output "
            f"is given)"
        ),
    )
    parser.add_argument(
        "--docs-output",
        type=str,
        default=None,
        help="Write the GitHub-safe docs-variant diagram to this path (e.g. docs/assets/mermaid/pipeline-flow-live.mmd)",
    )
    args = parser.parse_args()

    # NOTE: --docs-output must NOT clobber the full diagram. The hourly
    # workflow calls `--docs-output` as a belt-and-suspenders refresh while
    # run_hourly.py already regenerates BOTH files via generate() +
    # generate_docs() in the same cycle, so the full diagram is only written
    # here when explicitly requested (--output/--stdout) or when the script is
    # run bare (backwards-compatible default). This avoids a locked/unavailable
    # DB silently overwriting diagrams/pipeline-flow-live.mmd with zeros.
    if args.stdout:
        generate(stdout=True)
    elif args.output is not None:
        generate(output_path=args.output)
    elif args.docs_output is None:
        # Bare invocation: keep the historical default behaviour.
        generate(output_path=str(DIAGRAMS_DIR / "pipeline-flow-live.mmd"))

    if args.docs_output:
        generate_docs(output_path=args.docs_output)


if __name__ == "__main__":
    main()
