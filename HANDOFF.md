<div align="center" style="position:relative; overflow:hidden; border-radius:20px; background:linear-gradient(135deg, #0B0F1E 0%, #0F1F15 40%, #0B0F1E 100%); padding:44px 20px 36px; margin-bottom:8px; border:1px solid rgba(0,255,136,0.08);">

<div style="position:absolute; top:-120px; left:50%; transform:translateX(-50%); width:600px; height:300px; background:radial-gradient(ellipse, rgba(0,255,136,0.12) 0%, transparent 70%); pointer-events:none;"></div>
<div style="position:absolute; top:0; left:10%; right:10%; height:1px; background:linear-gradient(90deg, transparent, rgba(0,255,136,0.5), transparent);"></div>

<div style="position:relative; z-index:1;">
<h1 style="margin:0; font-size:2.2em; font-weight:700; color:#E0E0E0; letter-spacing:-0.5px;">
  <img src="docs/assets/svg/icon-f8867c21931f.svg" width="36" height="36" alt="" style="vertical-align:middle; max-width:100%;" />
  Mandiiq — Complete Codebase Handoff
</h1>
<h4 style="color:#94A3B8; font-weight:400; font-size:0.95em; margin:6px 0 0 0;">MandiIQ Documentation</h4>
</div>

</div>
<div style="background:linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%); border:1px solid rgba(255,255,255,0.06); border-radius:16px; padding:24px 28px; margin:16px 0; box-shadow:0 8px 32px rgba(0,0,0,0.4); position:relative; overflow:hidden;">
<div style="position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg, transparent, #00FF88, transparent); opacity:0.6;"></div>
<div style="position:absolute; top:-60px; right:-60px; width:120px; height:120px; background:radial-gradient(circle, rgba(0,255,136,0.15) 0%, transparent 70%);"></div>

> **Generated:** July 30, 2026  
> **Project:** Agricultural Margin Intelligence &amp; Causal RDD System  
> **Live Preview:** http://127.0.0.1:18765/docs/index.html  
> **API Server:** http://127.0.0.1:18765 (FastAPI, PID 31012)  

---

</div></div></div>
<br />
<div style="position:relative; height:60px; overflow:hidden; width:100%; margin:8px 0;">
  <img src="docs/assets/svg/icon-4fe945889b5c.svg" width="100%" height="60" alt="" style="vertical-align:middle; max-width:100%;" />
</div>
<br />
<div style="background:linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%); border:1px solid rgba(255,255,255,0.06); border-radius:16px; padding:24px 28px; margin:16px 0; box-shadow:0 8px 32px rgba(0,0,0,0.4); position:relative; overflow:hidden;">
<div style="position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg, transparent, #00FF88, transparent); opacity:0.6;"></div>
<div style="position:absolute; top:-60px; right:-60px; width:120px; height:120px; background:radial-gradient(circle, rgba(0,255,136,0.15) 0%, transparent 70%);"></div>
<a name="table-of-contents"></a>
<h2 style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif; font-size:1.5em; font-weight:600; color:#E0E0E0; display:flex; align-items:center; gap:10px; margin:0 0 16px 0; padding-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.06);">
  <img src="docs/assets/svg/icon-f862fc7823f0.svg" width="25" height="25" alt="" style="vertical-align:middle; max-width:100%;" /> Table of Contents
</h2>

1. [Project Overview](#1-project-overview)
2. [Architecture Diagram](#2-architecture-diagram)
3. [Directory Structure](#3-directory-structure)
4. [Ingestion Pipeline](#4-ingestion-pipeline)
5. [Storage Layer](#5-storage-layer)
6. [Analysis Engine](#6-analysis-engine)
7. [API Layer](#7-api-layer)
8. [Dashboard (Streamlit)](#8-dashboard-streamlit)
9. [Frontend (React / Vite)](#9-frontend-react--vite)
10. [AI Orchestrator](#10-ai-orchestrator)
11. [Docs &amp; Landing Pages](#11-docs--landing-pages)
12. [Deployment &amp; CI/CD](#12-deployment--cicd)
13. [Live Data State](#13-live-data-state)
14. [Known Issues &amp; Pending Work](#14-known-issues--pending-work)
15. [Local Development](#15-local-development)

---

</div></div></div>
<br />
<div style="position:relative; height:60px; overflow:hidden; width:100%; margin:8px 0;">
  <img src="docs/assets/svg/icon-b5297f23fd61.svg" width="100%" height="60" alt="" style="vertical-align:middle; max-width:100%;" />
</div>
<br />
<div style="background:linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%); border:1px solid rgba(255,255,255,0.06); border-radius:16px; padding:24px 28px; margin:16px 0; box-shadow:0 8px 32px rgba(0,0,0,0.4); position:relative; overflow:hidden;">
<div style="position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg, transparent, #00FF88, transparent); opacity:0.6;"></div>
<div style="position:absolute; top:-60px; right:-60px; width:120px; height:120px; background:radial-gradient(circle, rgba(0,255,136,0.15) 0%, transparent 70%);"></div>
<a name="1-project-overview"></a>
<h2 style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif; font-size:1.5em; font-weight:600; color:#E0E0E0; display:flex; align-items:center; gap:10px; margin:0 0 16px 0; padding-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.06);">
  <img src="docs/assets/svg/icon-e22ec59e46bc.svg" width="25" height="25" alt="" style="vertical-align:middle; max-width:100%;" /> 1. Project Overview
</h2>

MandiIQ is an open-source analytical warehouse and dashboard that applies **Causal Regression Discontinuity Designs (RDD)** to test whether IMD rainfall-deficit thresholds drive structural margins in national commodity markets.

### Core Tech Stack

| Layer | Technology |
|-------|-----------|
| **Analytical Store** | DuckDB (embedded, ~1.3M price rows) |
| **API Server** | FastAPI (uvicorn, port 18765 / 8000) |
| **Dashboard** | Streamlit (14 routes, st.navigation) |
| **Frontend** | React 18 + Vite (FlipBoard, WebGL) |
| **Design System** | Alche Studio-inspired monochrome + lime |
| **Forecasting** | Python (seasonal naive, Prophet, LSTM) |
| **ML** | XGBoost + SHAP for risk classification |
| **AI** | OpenRouter multi-model routing with circuit breaker |
| **Hosting** | Northflank (primary), Render (backup), Fly.io |
| **Backup** | Cloudflare R2 (S3-compatible) |
| **Monitoring** | Grafana Cloud, Prometheus metrics |

### Key Data Sources

- **data.gov.in** (Agmarknet) — Daily mandi prices ~ API key required
- **Open-Meteo** — Free rainfall data (no API key needed)
- **Sentinel Hub** — Satellite NDVI vegetation index ~ OAuth2 credentials
- **Ashoka CEDA** — Historical price backfill archive
- **IMD Grids** — Indian Meteorological Department rainfall data

---

</div></div></div>
<br />
<div style="position:relative; height:60px; overflow:hidden; width:100%; margin:8px 0;">
  <img src="docs/assets/svg/icon-47f7f2f791a1.svg" width="100%" height="60" alt="" style="vertical-align:middle; max-width:100%;" />
</div>
<br />
<div style="background:linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%); border:1px solid rgba(255,255,255,0.06); border-radius:16px; padding:24px 28px; margin:16px 0; box-shadow:0 8px 32px rgba(0,0,0,0.4); position:relative; overflow:hidden;">
<div style="position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg, transparent, #00FF88, transparent); opacity:0.6;"></div>
<div style="position:absolute; top:-60px; right:-60px; width:120px; height:120px; background:radial-gradient(circle, rgba(0,255,136,0.15) 0%, transparent 70%);"></div>
<a name="2-architecture-diagram"></a>
<h2 style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif; font-size:1.5em; font-weight:600; color:#E0E0E0; display:flex; align-items:center; gap:10px; margin:0 0 16px 0; padding-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.06);">
  <img src="docs/assets/svg/icon-e22ec59e46bc.svg" width="25" height="25" alt="" style="vertical-align:middle; max-width:100%;" /> 2. Architecture Diagram
</h2>

```
┌─────────────────────────────────────────────────────────────────┐
│                        DATA SOURCES                             │
│  data.gov.in  │  Open-Meteo  │  Sentinel Hub  │  Ashoka CEDA    │
└───────┬───────┴──────┬───────┴───────┬────────┴───────┬─────────┘
        │              │               │                │
        ▼              ▼               ▼                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     INGESTION PIPELINE                           │
│  fetch_prices.py  │  fetch_rainfall.py  │  fetch_ndvi.py        │
│  ingest_historical_csv.py  │  backfill_state.py  │  scheduler.py │
│  ashoka_background_import.py  │  archive_scanner.py             │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                     ANALYTICAL STORE (DuckDB)                    │
│  prices (1.3M rows, 303 commodities, 36 states, 611 districts)  │
│  rainfall (2,278 records, 34 sub-divisions)                     │
│  ndvi (3,663 records, 605 districts)                            │
│  rdd_results (117 causal estimates)                             │
│  forecast_metrics (144 models)                                  │
│  data_lineage (provenance tracking)                             │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                      ANALYSIS ENGINE                             │
│  rdd_engine.py     — Local-linear RDD + triangular kernel       │
│  fixed_effects.py  — District-month FE cross-check              │
│  forecast.py       — Seasonal naive + ensemble + damped trend   │
│  classifier.py     — XGBoost price-spike risk classifier        │
│  prescriptive.py   — Combined procurement recommendations       │
│  robustness.py     — Bandwidth sensitivity, placebo, density    │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                        API LAYER (FastAPI)                       │
│  /health  /prices  /freshness  /rdd-result  /rdd-plot           │
│  /forecast  /risk-score  /recommendation  /robustness           │
│  /ask  /refresh  /backup-to-r2  /restore-from-r2               │
│  /pipeline.svg  /pipeline.mmd  /grafana-dashboard               │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                   DASHBOARD (Streamlit)                          │
│  14 pages: Executive Overview, Discontinuity, Forecast,         │
│  Risk Map, Satellite, Discount Simulator, Ask, Settings,        │
│  About, Onboarding, Loading, 404, Error pages                   │
└─────────────────────────────────────────────────────────────────┘
```

---

</div></div></div>
<br />
<div style="position:relative; height:60px; overflow:hidden; width:100%; margin:8px 0;">
  <img src="docs/assets/svg/icon-659fbdc3b394.svg" width="100%" height="60" alt="" style="vertical-align:middle; max-width:100%;" />
</div>
<br />
<div style="background:linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%); border:1px solid rgba(255,255,255,0.06); border-radius:16px; padding:24px 28px; margin:16px 0; box-shadow:0 8px 32px rgba(0,0,0,0.4); position:relative; overflow:hidden;">
<div style="position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg, transparent, #00FF88, transparent); opacity:0.6;"></div>
<div style="position:absolute; top:-60px; right:-60px; width:120px; height:120px; background:radial-gradient(circle, rgba(0,255,136,0.15) 0%, transparent 70%);"></div>
<a name="3-directory-structure"></a>
<h2 style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif; font-size:1.5em; font-weight:600; color:#E0E0E0; display:flex; align-items:center; gap:10px; margin:0 0 16px 0; padding-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.06);">
  <img src="docs/assets/svg/icon-d57309e9a53d.svg" width="25" height="25" alt="" style="vertical-align:middle; max-width:100%;" /> 3. Directory Structure
</h2>

```
MandiIQ/
├── mandi_rdd/                      # Main Python package
│   ├── ai/                         # AI Orchestrator
│   │   ├── orchestrator.py         #   Tool-calling LLM orchestrator
│   │   ├── router.py               #   OpenRouter multi-model routing
│   │   └── models.yaml             #   Model configurations
│   ├── analysis/                   # Core analysis engine
│   │   ├── rdd_engine.py           #   Regression Discontinuity Design
│   │   ├── forecast.py             #   Seasonal naive + ensemble forecast
│   │   ├── classifier.py           #   XGBoost + SHAP risk classifier
│   │   ├── fixed_effects.py        #   Fixed-effects cross-check
│   │   ├── prescriptive.py         #   Procurement recommendations
│   │   ├── robustness.py           #   Robustness checks
│   │   └── lstm_forecast.py        #   LSTM forecasting (alternative)
│   ├── api/                        # FastAPI serving layer
│   │   ├── main.py                 #   All endpoints (1100+ lines)
│   │   ├── metrics_push.py         #   Prometheus metrics push
│   │   └── svg_compositor.py       #   KPI badge SVG compositor
│   ├── core/
│   │   └── metrics.py              #   PipelineMetrics singleton
│   ├── dashboard/                  # Streamlit dashboard
│   │   ├── app.py                  #   Entry point + navigation
│   │   ├── theme.py                #   Alche studio design system
│   │   ├── components.py           #   Reusable UI components
│   │   ├── data_access.py          #   Cached data access layer
│   │   ├── icons.py                #   SVG icon library
│   │   ├── plotly_theme.py         #   Chart theme + animations
│   │   ├── seo.py                  #   SEO metadata injection
│   │   ├── pages/                  #   14 dashboard pages
│   │   │   ├── executive_overview.py
│   │   │   ├── discontinuity.py
│   │   │   ├── forecast.py
│   │   │   ├── risk_map.py
│   │   │   ├── satellite.py
│   │   │   ├── discount_simulator.py
│   │   │   ├── ask.py
│   │   │   ├── settings.py
│   │   │   ├── about.py
│   │   │   ├── onboarding.py
│   │   │   ├── loading.py
│   │   │   ├── error_404.py
│   │   │   ├── error_model_unavailable.py
│   │   │   ├── error_no_data.py
│   │   │   ├── deep_dive.py
│   │   │   ├── causal_explorer.py
│   │   │   ├── risk_forecast.py
│   │   │   ├── procurement_advisor.py
│   │   │   ├── performance.py          # Hidden debug route
│   │   │   └── components.py           # Dev component gallery
│   │   ├── frontend/               # React + Vite frontend
│   │   │   ├── src/
│   │   │   │   ├── FlipBoard.tsx   #   KPI flip-card component
│   │   │   │   ├── WebGLHero.tsx   #   Three.js particle field
│   │   │   │   └── main.tsx        #   React entry point
│   │   │   ├── dist/               #   Built output
│   │   │   ├── vite.config.ts
│   │   │   ├── tsconfig.json
│   │   │   └── package.json
│   │   ├── styles/
│   │   │   └── design.css          #   Design token CSS
│   │   └── data/                   #   Data files
│   │       ├── last_ingest_status.json
│   │       ├── last_hourly_run.json
│   │       ├── last_step_timings.json
│   │       └── ndvi_latest.json
│   ├── ingestion/                  # Data ingestion pipeline
│   │   ├── scheduler.py            #   Orchestrator for all ingest steps
│   │   ├── fetch_prices.py         #   data.gov.in price API
│   │   ├── fetch_rainfall.py       #   Open-Meteo + data.gov.in rainfall
│   │   ├── fetch_ndvi.py           #   Sentinel Hub NDVI
│   │   ├── fetch_historical.py     #   Historical price fetch
│   │   ├── fetch_historical_ashoka.py
│   │   ├── ingest_historical_csv.py
│   │   ├── ingest_kaggle.py
│   │   ├── backfill_state.py       #   State name resolution
│   │   ├── archive_scanner.py      #   Stale archive probe
│   │   ├── ashoka_background_import.py
│   │   ├── http_client.py          #   Shared HTTP utilities
│   │   └── __init__.py
│   ├── storage/
│   │   ├── duckdb_store.py         #   DuckDB interface (all CRUD)
│   │   └── database.py             #   SQLite fallback
│   ├── sql/                        # Analytical SQL queries
│   ├── tests/
│   │   ├── data_integrity.py       #   Integrity checks
│   │   └── test_verification.py
│   ├── Dockerfile
│   ├── requirements.txt
│   └── README.md
├── docs/                           # Documentation site
│   ├── index.html                  #   Consolidated single-page tabbed docs
│   ├── pipeline-report.html        #   → redirects to index.html#pipeline
│   ├── pipeline-interactive.html   #   → redirects to index.html#interactive
│   ├── system_design.md
│   ├── writeup.md
│   ├── heartbeat-dashboard.html
│   └── cursor-effect.js
├── data/
│   ├── district_coords.json        #   600+ district lat/lon coordinates
│   └── mandi_iq.duckdb (git-lfs)   #   Production database
├── diagrams/
│   ├── pipeline-flow-live.mmd      #   Live Mermaid DAG (auto-generated)
│   ├── pipeline-flow-live.svg      #   Rendered SVG
│   ├── architecture.mmd
│   └── repo-structure.mmd
├── landing/
│   ├── index.html                  #   Alche studio landing page
│   └── mandi-iq/index.html         #   MandiIQ-specific landing
├── dashboards/
│   ├── mandiiq-pipeline.json       #   Grafana dashboard JSON
│   └── grafana-provider.yml
├── scripts/
│   ├── generate_pipeline_diagram.py  #   Auto-generates pipeline-flow-live.mmd from metrics
│   ├── validate_northflank_config.py #   Pre-deploy Docker config validator
│   ├── generate_pipeline_diagram.py
│   ├── validate_render_yaml.py
│   ├── check_freshness.py
│   ├── verify_live_data.py
│   └── create_labels.py
├── worker/
│   └── worker.js                   #   Cloudflare Workers edge proxy
├── docker-compose.yml
├── Dockerfile.northflank           #   Production Docker (Northflank)
├── Dockerfile.fly                  #   Production Docker (Fly.io)
├── render.yaml                     #   Render Blueprints config
├── fly.toml                        #   Fly.io config
├── run_hourly.py                   #   Hourly auto-updater script
├── run_ingest.py                   #   Daily ingestion script
└── .streamlit/
    ├── config.toml
    └── secrets.toml                #   API keys (not committed)
```

---

</div></div></div>
<br />
<div style="position:relative; height:60px; overflow:hidden; width:100%; margin:8px 0;">
  <img src="docs/assets/svg/icon-3b0384c03533.svg" width="100%" height="60" alt="" style="vertical-align:middle; max-width:100%;" />
</div>
<br />
<div style="background:linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%); border:1px solid rgba(255,255,255,0.06); border-radius:16px; padding:24px 28px; margin:16px 0; box-shadow:0 8px 32px rgba(0,0,0,0.4); position:relative; overflow:hidden;">
<div style="position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg, transparent, #00FF88, transparent); opacity:0.6;"></div>
<div style="position:absolute; top:-60px; right:-60px; width:120px; height:120px; background:radial-gradient(circle, rgba(0,255,136,0.15) 0%, transparent 70%);"></div>
<a name="4-ingestion-pipeline"></a>
<h2 style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif; font-size:1.5em; font-weight:600; color:#E0E0E0; display:flex; align-items:center; gap:10px; margin:0 0 16px 0; padding-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.06);">
  <img src="docs/assets/svg/icon-bee2875cc587.svg" width="25" height="25" alt="" style="vertical-align:middle; max-width:100%;" /> 4. Ingestion Pipeline
</h2>

### 4.1 Scheduler (`mandi_rdd/ingestion/scheduler.py`)

The central orchestrator. Called by:
- `run_hourly.py` — every hour via scheduled task / Northflank cron
- `run_ingest.py` — daily GitHub Actions job
- FastAPI `/refresh` endpoint — manual trigger
- FastAPI startup auto-trigger (if data is stale)

**Execution flow:**
1. `fetch_prices()` — data.gov.in Agmarknet API (paginated)
2. `fetch_rainfall()` — Open-Meteo (primary), data.gov.in (fallback)
3. `fetch_ndvi()` — Sentinel Hub (if credentials configured)
4. `backfill_state()` — resolve NULL state names from district names
5. `run_rdd()` — causal analysis for rain-sensitive commodities
6. `run_fixed_effects()` — FE cross-check
7. `train_forecast()` — seasonal naive + ensemble models
8. `train_spike_classifier()` — XGBoost risk classifier
9. `compute_recommendation()` — prescriptive engine
10. `data_lineage` — provenance tracking

**Smart scheduling:** `run_hourly.py` runs full analysis only once every 24h; price-only fetch every hour (~30s).

### 4.2 Price Fetcher (`fetch_prices.py`)

- **Source:** `https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070`
- **API Key:** `DATA_GOV_IN_API_KEY` (or `DATA_GOV_API_KEY`) — fails hard if missing
- **Pagination:** 5000 per page, 0.5s delay between pages, 3 retries with exponential backoff
- **Field normalization:** Maps PascalCase (Arrival_Date) → snake_case (arrival_date)
- **Source tagging:** Each record tagged with `_source: {source_type: "api", resource_id: "..."}`

### 4.3 Rainfall Fetcher (`fetch_rainfall.py`)

- **Primary source:** Open-Meteo (free, no API key)
- **Strategy:** Map each district → IMD sub-division via `load_district_subdivision_map()` (~860 mappings)
- **Representative:** Pick one district per sub-division, fetch 5 years of daily precipitation
- **Computation:** Monthly totals → multi-year climatology → departure_pct
- **Fallback chain:** Open-Meteo → data.gov.in resources → Datameet GitHub CSV

### 4.4 NDVI Fetcher (`fetch_ndvi.py`)

- **Source:** Sentinel Hub Statistical API
- **Auth:** OAuth2 client credentials (`SENTINEL_CLIENT_ID` + `SENTINEL_CLIENT_SECRET`)
- **Evalscript:** `(B08 - B04) / (B08 + B04)` — Sentinel-2 L2A NDVI
- **Coverage:** 605/640 districts (Sentinel Hub free tier cap: ~640)
- **Features:** Exponential backoff with jitter, token refresh, progress tracking, fetch_missing_ndvi() retry

### 4.5 State Backfill (`backfill_state.py`)

- Resolves NULL `state` column in prices table by matching district names
- Uses district_coords.json + Ashoka API cross-references
- INSERT OR REPLACE pattern (avoids DuckDB index corruption from DELETE+INSERT)

### 4.6 Diagram Generator

`scripts/generate_pipeline_diagram.py` — Called by `run_hourly.py`'s `_run_diagram_generator()` after each successful pipeline run. Reads `last_step_timings.json` for per-step wall-clock durations (e.g. `[34.5s]` on `rdd_engine.py`) and commodity counts, then writes the updated `diagrams/pipeline-flow-live.mmd`. This is how the Pipeline KPI cards stay in sync with actual live data.

### 4.7 Historical Import

- `fetch_historical.py` — Bulk CSV creation from data.gov.in
- `fetch_historical_ashoka.py` — Monthly data per district/commodity via Ashoka CEDA
- `ingest_historical_csv.py` — DuckDB CSV bulk load
- `ashoka_background_import.py` — Resumable background import with checkpointing

---

</div></div></div>
<br />
<div style="position:relative; height:60px; overflow:hidden; width:100%; margin:8px 0;">
  <img src="docs/assets/svg/icon-74ecabd2462c.svg" width="100%" height="60" alt="" style="vertical-align:middle; max-width:100%;" />
</div>
<br />
<div style="background:linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%); border:1px solid rgba(255,255,255,0.06); border-radius:16px; padding:24px 28px; margin:16px 0; box-shadow:0 8px 32px rgba(0,0,0,0.4); position:relative; overflow:hidden;">
<div style="position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg, transparent, #00FF88, transparent); opacity:0.6;"></div>
<div style="position:absolute; top:-60px; right:-60px; width:120px; height:120px; background:radial-gradient(circle, rgba(0,255,136,0.15) 0%, transparent 70%);"></div>
<a name="5-storage-layer"></a>
<h2 style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif; font-size:1.5em; font-weight:600; color:#E0E0E0; display:flex; align-items:center; gap:10px; margin:0 0 16px 0; padding-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.06);">
  <img src="docs/assets/svg/icon-a0c60dd90fca.svg" width="25" height="25" alt="" style="vertical-align:middle; max-width:100%;" /> 5. Storage Layer
</h2>

### 5.1 DuckDB Store (`mandi_rdd/storage/duckdb_store.py`)

Production database (~5MB file at `mandi_rdd/data/mandi_iq.duckdb`).

**Core tables:**

```sql
prices (
  arrival_date DATE, state VARCHAR, district VARCHAR, market VARCHAR,
  commodity VARCHAR, variety VARCHAR, grade VARCHAR,
  min_price DOUBLE, max_price DOUBLE, modal_price DOUBLE
)

rainfall (
  sub_division VARCHAR, year INT, month INT,
  rainfall_mm DOUBLE, normal_mm DOUBLE, departure_pct DOUBLE
)

ndvi (
  district VARCHAR, state VARCHAR, latitude DOUBLE, longitude DOUBLE,
  ndvi_mean DOUBLE, ndvi_median DOUBLE, ndvi_min DOUBLE, ndvi_max DOUBLE,
  ndvi_std DOUBLE, data_cover_pct DOUBLE, observation_date DATE
)

rdd_results (
  commodity VARCHAR, state VARCHAR, effect DOUBLE, std_error DOUBLE,
  p_value DOUBLE, n_left INT, n_right INT, computed_at TIMESTAMP,
  bandwidth DOUBLE, bandwidth_sensitivity VARCHAR, placebo_tests VARCHAR,
  interpretation VARCHAR
)

forecast_metrics (
  commodity VARCHAR, computed_at TIMESTAMP, model VARCHAR,
  test_mape DOUBLE, test_mae DOUBLE, test_rmse DOUBLE,
  n_training_months INT, n_test_months INT, is_valid BOOLEAN
)

classification_results (
  commodity VARCHAR, roc_auc DOUBLE, n_training_rows INT,
  n_test_rows INT, top_features VARCHAR, computed_at TIMESTAMP
)
```

**Current data state (verified live):**
| Table | Rows | Notes |
|-------|------|-------|
| prices | 1,334,647 | 303 commodities, 36 states, 611 districts |
| rainfall | 2,278 | 34 sub-divisions |
| ndvi | 3,663 | 605 districts |
| rdd_results | 117 | Causal estimates |
| forecast_metrics | 144 | 144 valid models |

### 5.2 Data Access (`mandi_rdd/dashboard/data_access.py`)

Cached data-access layer for the dashboard:
- `@st.cache_data(ttl=60)` for most queries
- `get_prices()` — filtered price queries
- `get_monthly_avg_prices()` — time-series aggregation
- `get_latest_rdd()` — cached RDD results
- `init_schema()` — ensures tables exist

---

</div></div></div>
<br />
<div style="position:relative; height:60px; overflow:hidden; width:100%; margin:8px 0;">
  <img src="docs/assets/svg/icon-39164435e4b0.svg" width="100%" height="60" alt="" style="vertical-align:middle; max-width:100%;" />
</div>
<br />
<div style="background:linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%); border:1px solid rgba(255,255,255,0.06); border-radius:16px; padding:24px 28px; margin:16px 0; box-shadow:0 8px 32px rgba(0,0,0,0.4); position:relative; overflow:hidden;">
<div style="position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg, transparent, #00FF88, transparent); opacity:0.6;"></div>
<div style="position:absolute; top:-60px; right:-60px; width:120px; height:120px; background:radial-gradient(circle, rgba(0,255,136,0.15) 0%, transparent 70%);"></div>
<a name="6-analysis-engine"></a>
<h2 style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif; font-size:1.5em; font-weight:600; color:#E0E0E0; display:flex; align-items:center; gap:10px; margin:0 0 16px 0; padding-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.06);">
  <img src="docs/assets/svg/icon-f862fc7823f0.svg" width="25" height="25" alt="" style="vertical-align:middle; max-width:100%;" /> 6. Analysis Engine
</h2>

### 6.1 RDD Engine (`mandi_rdd/analysis/rdd_engine.py`)

**Methodology:** Pure-python local-linear RDD with triangular kernel (no R dependency).

**Key functions:**
- `local_linear_rdd(x, y, cutoff, bandwidth)` — Core estimator
  - Separate weighted regressions on each side of cutoff
  - HC2 sandwich estimator for standard errors
- `run_rdd(conn, commodity)` — Full pipeline: join prices + rainfall, estimate, robustness
- `bandwidth_sensitivity()` — Re-run at [10, 15, 20, 25, 30] bandwidths
- `placebo_test()` — Run at fake cutoffs (20th/40th/50th/60th/80th percentiles)
- `mccrary_density_test()` — Check manipulation of running variable
- `covariate_balance()` — Check pre-treatment covariates
- `rdd_plot_data()` — Generate binned scatter plot data

**Threshold:** -19% rainfall departure (IMD's official "deficient" cutoff)

### 6.2 Forecast Engine (`mandi_rdd/analysis/forecast.py`)

**Three model types:**
1. **Seasonal Naive (default, < 36 months):** Month-of-year median from training data
2. **Ensemble with Damped Trend (default, ≥ 36 months):** Windowed seasonal (60mo) + damped OLS trend (φ=0.85, w_trend=0.50)
3. **Prophet:** Meta's Prophet (if installed)

**Auto-selection:**
- 36+ months → ensemble with damped trend (handles inflation/long-term shifts)
- < 36 months → pure seasonal naive (robust to noisy agricultural data)

**Test split:** Last 3 months held out for MAPE calculation

### 6.3 Classifier (`mandi_rdd/analysis/classifier.py`)

- **Model:** XGBoost + SHAP
- **Target:** Price spike = top quartile of avg_modal_price
- **Features:** Lagged rainfall departures (1-3m), rolling price, volatility, month seasonality
- **Evaluation:** ROC-AUC

### 6.4 Fixed Effects (`mandi_rdd/analysis/fixed_effects.py`)

District + month fixed-effects regression as cross-check for RDD findings. Controls for unobserved district-level heterogeneity and seasonal patterns.

### 6.5 Prescriptive (`mandi_rdd/analysis/prescriptive.py`)

Combines RDD effect, risk score, and forecast into procurement recommendations:
- "Buy now" — low forecast, low risk, negative RDD effect
- "Wait" — high forecast, high risk, positive RDD effect
- "Hedged" — mixed signals

---

</div></div></div>
<br />
<div style="position:relative; height:60px; overflow:hidden; width:100%; margin:8px 0;">
  <img src="docs/assets/svg/icon-64083f9b218a.svg" width="100%" height="60" alt="" style="vertical-align:middle; max-width:100%;" />
</div>
<br />
<div style="background:linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%); border:1px solid rgba(255,255,255,0.06); border-radius:16px; padding:24px 28px; margin:16px 0; box-shadow:0 8px 32px rgba(0,0,0,0.4); position:relative; overflow:hidden;">
<div style="position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg, transparent, #00FF88, transparent); opacity:0.6;"></div>
<div style="position:absolute; top:-60px; right:-60px; width:120px; height:120px; background:radial-gradient(circle, rgba(0,255,136,0.15) 0%, transparent 70%);"></div>
<a name="7-api-layer"></a>
<h2 style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif; font-size:1.5em; font-weight:600; color:#E0E0E0; display:flex; align-items:center; gap:10px; margin:0 0 16px 0; padding-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.06);">
  <img src="docs/assets/svg/icon-e246b7163f05.svg" width="25" height="25" alt="" style="vertical-align:middle; max-width:100%;" /> 7. API Layer
</h2>

### 7.1 FastAPI Endpoints (`mandi_rdd/api/main.py`)

**Data endpoints:**
| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness + full data counts (prices, commodities, RDD, NDVI, forecast) |
| GET | `/freshness` | Per-commodity data freshness (latest date, rows, districts, states) |
| GET | `/prices` | Filtered price query (state/district/commodity, limit 5000) |

**Analysis endpoints:**
| Method | Path | Description |
|--------|------|-------------|
| GET | `/rdd-result/{commodity}` | Latest RDD estimate |
| GET | `/rdd-plot/{commodity}` | Binned scatter data for discontinuity chart |
| GET | `/robustness/{commodity}` | Full robustness bundle |
| GET | `/forecast/{commodity}` | Forecast (supports ?compare=true for Prophet vs LSTM) |
| GET | `/risk-score/{commodity}` | XGBoost price-spike risk |
| GET | `/recommendation/{commodity}` | Procurement recommendation |

**System endpoints:**
| Method | Path | Description |
|--------|------|-------------|
| POST | `/ask` | AI orchestrator (free-text procurement Q&amp;A) |
| POST | `/refresh` | Manual pipeline re-run (background) |
| POST | `/run-rainfall-rdd` | Targeted rainfall + RDD run |
| POST | `/backfill-historical` | Ashoka CEDA historical backfill |
| POST | `/admin/backup-to-r2` | Upload DuckDB to Cloudflare R2 |
| POST | `/admin/restore-from-r2` | Restore DuckDB from R2 |
| POST | `/admin/ingest-historical` | Upload CSV for bulk import |
| POST | `/admin/reset-metrics` | Reset LLM fallback counters |
| GET | `/pipeline.mmd` | Mermaid pipeline diagram source |
| GET | `/pipeline.svg` | Rendered pipeline SVG (via mmdc CLI) |
| GET | `/metrics` | Prometheus-format metrics |
| GET | `/grafana-dashboard` | Grafana dashboard JSON |

**Validation endpoints:**
| Method | Path | Description |
|--------|------|-------------|
| GET | `/debug/rainfall-test` | Test Open-Meteo connectivity diagnostics |
| GET | `/historical-import-status` | Ashoka background import progress |
| POST | `/trigger-ashoka-import` | Start Ashoka historical import |

### 7.2 Key Behaviors

- **Auto-pipeline:** On startup, if data is stale (<100 prices, <10 rainfall, <1 RDD), triggers background pipeline
- **Hourly auto-refresh:** Daemon thread runs `run_ingestion()` every 3600s
- **Pipeline SVG pre-render:** On startup, renders pipeline diagram via mmdc CLI
- **Static docs mount:** `app.mount("/docs", StaticFiles(...))` serves docs same-origin
- **R2 backup:** S3-compatible Cloudflare R2 with AWS Signature V4 auth (no extra deps)

### 7.3 CORS

Wide-open: `allow_origins=["*"]` (acceptable for data API, tighten for production)

---

</div></div></div>
<br />
<div style="position:relative; height:60px; overflow:hidden; width:100%; margin:8px 0;">
  <img src="docs/assets/svg/icon-a130f96a3d15.svg" width="100%" height="60" alt="" style="vertical-align:middle; max-width:100%;" />
</div>
<br />
<div style="background:linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%); border:1px solid rgba(255,255,255,0.06); border-radius:16px; padding:24px 28px; margin:16px 0; box-shadow:0 8px 32px rgba(0,0,0,0.4); position:relative; overflow:hidden;">
<div style="position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg, transparent, #00FF88, transparent); opacity:0.6;"></div>
<div style="position:absolute; top:-60px; right:-60px; width:120px; height:120px; background:radial-gradient(circle, rgba(0,255,136,0.15) 0%, transparent 70%);"></div>
<a name="8-dashboard-streamlit"></a>
<h2 style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif; font-size:1.5em; font-weight:600; color:#E0E0E0; display:flex; align-items:center; gap:10px; margin:0 0 16px 0; padding-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.06);">
  <img src="docs/assets/svg/icon-f862fc7823f0.svg" width="25" height="25" alt="" style="vertical-align:middle; max-width:100%;" /> 8. Dashboard (Streamlit)
</h2>

### 8.1 Architecture (`mandi_rdd/dashboard/app.py`)

- **Entry point:** `st.set_page_config()` → `st.navigation()` (14 routes)
- **Navigation:** `st.Page()` objects with explicit `url_path` for deep linking
- **Global shell:** Top bar (breadcrumb, Ask button, sound toggle, theme toggle), sidebar, footer
- **Animation injectors:** All gated behind `st.session_state._mandiiq_animations_injected`
- **Error handling:** Bare `except Exception` with `st.exception()` fallback for full traceback

**14 routes:**

| Route | Page | Description |
|-------|------|-------------|
| `/` | Executive Overview | KPI cards, freshness table, ingestion trigger |
| `/discontinuity` | Discontinuity Explorer | RDD scatter plot, bandwidth sensitivity |
| `/forecast` | Forecast Explorer | Price forecast chart, model comparison |
| `/risk-map` | Risk Map | District-level risk choropleth |
| `/satellite` | Satellite View | NDVI anomaly map + rainfall scatter |
| `/discount-simulator` | Discount Simulator | What-if discount analysis |
| `/ask` | Ask MandiIQ | AI procurement chat interface |
| `/settings` | Settings | API configuration, theme |
| `/about` | About | Project information |
| `/onboarding` | Onboarding | First-time user guide |
| `/loading` | Loading | Loading spinner |
| `/404` | 404 | Not found |
| `/error/model-unavailable` | Model Unavailable | Error state |
| `/error/no-data` | No Data | Empty state |

Hidden routes: `/performance` (debug), `/components` (dev gallery)

### 8.2 Design System (`mandi_rdd/dashboard/theme.py`)

Alche Studio-inspired monochrome + lime aesthetic:

**Color tokens:**
- `INK = "#000000"` — Pure black background
- `SLATE = "#111111"` — Dark charcoal card
- `PAPER = "#FFFFFF"` — White text
- `MUTED = "#bababa"` — Muted grey
- `FAINT = "#7e7e7e"` — Medium muted
- `TURMERIC = "#d7ff00"` — Lime accent
- `RUST = "#D9663B"` — Deficit alert
- `SAGE = "#8FAE89"` — Healthy NDVI

**Injected animations (all session-state gated):**
1. `inject_cursor_effect()` — Canvas cursor trail (touch-responsive, 20 trails)
2. `inject_gsap_splittext()` — Character reveal via GSAP SplitText
3. `inject_lenis_scroll()` — Lenis smooth scroll + GSAP ScrollTrigger
4. `inject_page_loader()` — Cinematic black overlay with lime line
5. `inject_scroll_progress()` — 2px lime progress bar at viewport top
6. `inject_sound_toggle()` — Web Audio API synthesized sounds (3-bar equalizer)
7. `inject_scroll_to_top()` — Floating scroll-to-top button
8. `inject_card_stagger()` — IntersectionObserver card stagger reveal
9. `inject_scroll_trigger_factory()` — Section enter/leave events with whoosh sounds
10. `inject_atmosphere()` — Drifting blobs + dot grid with Lenis parallax
11. `inject_debug_badge()` — Floating diagnostics panel (?debug=1)
12. `inject_webgl_hero()` — React Three.js particle field (Vite bundle)
13. `inject_chart_theme()` — Plotly chart styling + reveal animations

**Surface mode:** Toggle between pure black (INK) and dark grey (SLATE) for daytime readability. Persisted via localStorage + URL query param.

### 8.3 Plotly Theme (`mandi_rdd/dashboard/plotly_theme.py`)

Custom Plotly template with:
- Dark background, lime gridlines, white text
- Crosshair corner markers on chart containers
- Chart reveal animation (clip-path on IntersectionObserver)
- Hover effects (lime shadow on hover)
- Responsive font sizing

### 8.4 Key Dashboard Features

- **Data Freshness table:** Paginated (10/20/50/100 rows), column sortable, per-commodity stats
- **KPI flip-board:** Eased count-up animation on page load with stagger
- **Ingestion trigger button:** "▶ Run Ingestion Now" with live progress log, completion notification
- **Auto-retry:** 3 retries with exponential backoff on failure (countdown timer)
- **Live-dot pulse:** rAF-smoothed "Updated last 7d" counter

---

</div></div></div>
<br />
<div style="position:relative; height:60px; overflow:hidden; width:100%; margin:8px 0;">
  <img src="docs/assets/svg/icon-a4b3c8aa44d6.svg" width="100%" height="60" alt="" style="vertical-align:middle; max-width:100%;" />
</div>
<br />
<div style="background:linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%); border:1px solid rgba(255,255,255,0.06); border-radius:16px; padding:24px 28px; margin:16px 0; box-shadow:0 8px 32px rgba(0,0,0,0.4); position:relative; overflow:hidden;">
<div style="position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg, transparent, #00FF88, transparent); opacity:0.6;"></div>
<div style="position:absolute; top:-60px; right:-60px; width:120px; height:120px; background:radial-gradient(circle, rgba(0,255,136,0.15) 0%, transparent 70%);"></div>
<a name="9-frontend-react-vite"></a>
<h2 style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif; font-size:1.5em; font-weight:600; color:#E0E0E0; display:flex; align-items:center; gap:10px; margin:0 0 16px 0; padding-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.06);">
  <img src="docs/assets/svg/icon-f862fc7823f0.svg" width="25" height="25" alt="" style="vertical-align:middle; max-width:100%;" /> 9. Frontend (React / Vite)
</h2>

### 9.1 FlipBoard (`mandi_rdd/dashboard/frontend/src/FlipBoard.tsx`)

Custom React component for KPI flip animations. Used by Executive Overview.

### 9.2 WebGL Hero (`mandi_rdd/dashboard/frontend/src/WebGLHero.tsx`)

Three.js particle field using `@react-three/fiber` + `@react-three/drei`:
- 2000+ particles with `PointsMaterial` (GPU-based)
- Auto-rotates (30s cycle, pause on user interaction via button toggle)
- Lazy-loaded with IntersectionObserver
- Auto-pauses on tab hide (visibilitychange)
- CSS gradient fallback on low-end devices / prefers-reduced-motion
- Imported via Vite-built bundle injected by `inject_webgl_hero()`

### 9.3 Build Configuration

- **Package manager:** npm
- **Build tool:** Vite (vite.config.ts)
- **Code splitting:** drei, three, fiber → separate chunk
- **TypeScript:** strict mode
- **Output:** `frontend/dist/assets/index-*.js`

---

</div></div></div>
<br />
<div style="position:relative; height:60px; overflow:hidden; width:100%; margin:8px 0;">
  <img src="docs/assets/svg/icon-ee41fa0ceea0.svg" width="100%" height="60" alt="" style="vertical-align:middle; max-width:100%;" />
</div>
<br />
<div style="background:linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%); border:1px solid rgba(255,255,255,0.06); border-radius:16px; padding:24px 28px; margin:16px 0; box-shadow:0 8px 32px rgba(0,0,0,0.4); position:relative; overflow:hidden;">
<div style="position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg, transparent, #00FF88, transparent); opacity:0.6;"></div>
<div style="position:absolute; top:-60px; right:-60px; width:120px; height:120px; background:radial-gradient(circle, rgba(0,255,136,0.15) 0%, transparent 70%);"></div>
<a name="10-ai-orchestrator"></a>
<h2 style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif; font-size:1.5em; font-weight:600; color:#E0E0E0; display:flex; align-items:center; gap:10px; margin:0 0 16px 0; padding-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.06);">
  <img src="docs/assets/svg/icon-f862fc7823f0.svg" width="25" height="25" alt="" style="vertical-align:middle; max-width:100%;" /> 10. AI Orchestrator
</h2>

### 10.1 Router (`mandi_rdd/ai/router.py`)

Multi-model routing with circuit-breaker fallback chain:
1. Google Gemini (direct API)
2. NVIDIA NIM (DeepSeek V4 Pro)
3. OpenRouter (multi-model fallback)
4. All capped at free-tier limits with automatic cool-down on rate limit

**Environment variables:** `GEMINI_API_KEY`, `NVIDIA_API_KEY`, `OPENROUTER_API_KEY`

### 10.2 Orchestrator (`mandi_rdd/ai/orchestrator.py`)

Tool-calling AI assistant:
1. Parses query → detects commodity/district
2. Selects relevant tools (RDD, forecast, risk score, recommendation, robustness)
3. Executes tool calls → provides raw results as context to LLM
4. LLM generates grounded answer from tool results only (no hallucination)
5. Falls back to structured template answer if LLM chain exhausted

**System prompt:** Forbids stating any number not returned by a tool call. 3-5 sentence answer format.

**Nightly narrative:** Auto-generates commodity summaries after pipeline run.

### 10.3 Model Config (`mandi_rdd/ai/models.yaml`)

Defines model endpoints, rate limits, and routing rules.

---

</div></div></div>
<br />
<div style="position:relative; height:60px; overflow:hidden; width:100%; margin:8px 0;">
  <img src="docs/assets/svg/icon-9bfc8c8cc8b3.svg" width="100%" height="60" alt="" style="vertical-align:middle; max-width:100%;" />
</div>
<br />
<div style="background:linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%); border:1px solid rgba(255,255,255,0.06); border-radius:16px; padding:24px 28px; margin:16px 0; box-shadow:0 8px 32px rgba(0,0,0,0.4); position:relative; overflow:hidden;">
<div style="position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg, transparent, #00FF88, transparent); opacity:0.6;"></div>
<div style="position:absolute; top:-60px; right:-60px; width:120px; height:120px; background:radial-gradient(circle, rgba(0,255,136,0.15) 0%, transparent 70%);"></div>
<a name="11-docs-landing-pages"></a>
<h2 style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif; font-size:1.5em; font-weight:600; color:#E0E0E0; display:flex; align-items:center; gap:10px; margin:0 0 16px 0; padding-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.06);">
  <img src="docs/assets/svg/icon-f862fc7823f0.svg" width="25" height="25" alt="" style="vertical-align:middle; max-width:100%;" /> 11. Docs &amp; Landing Pages
</h2>

### 11.1 Consolidated Docs (`docs/index.html`)

Single-page tabbed documentation site with full Alche Studio design system:

**4 tabs:**
1. **Overview** — Project description, KPI cards, RDD framework, architecture, failure modes
2. **Structure** — Repository structure diagram and explanation
3. **Pipeline** — Live pipeline DAG with mermaid rendering, KPI cards, Commodity Freshness table, 60s auto-refresh
4. **Interactive** — Clickable mermaid diagram (node → GitHub source file)

**Features:**
- Hash-based routing (`#pipeline`, `#interactive`) for redirects
- 3D particle canvas background
- Atmosphere drifter blobs
- Glass cards with crosshair corners
- Text scrambler on headings
- Auto-refresh countdown (60s)
- Live data from FastAPI `/health` endpoint

### 11.2 Redirect Pages

- `docs/pipeline-report.html` → `<meta refresh>` to `index.html#pipeline`
- `docs/pipeline-interactive.html` → `<meta refresh>` to `index.html#interactive`

### 11.3 Landing Pages

- `landing/index.html` — Alche Studio cinematic landing page (Lenis, GSAP, Three.js, sound toggle)
- `landing/mandi-iq/index.html` — MandiIQ-specific landing (same animation suite)

---

</div></div></div>
<br />
<div style="position:relative; height:60px; overflow:hidden; width:100%; margin:8px 0;">
  <img src="docs/assets/svg/icon-672211b064be.svg" width="100%" height="60" alt="" style="vertical-align:middle; max-width:100%;" />
</div>
<br />
<div style="background:linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%); border:1px solid rgba(255,255,255,0.06); border-radius:16px; padding:24px 28px; margin:16px 0; box-shadow:0 8px 32px rgba(0,0,0,0.4); position:relative; overflow:hidden;">
<div style="position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg, transparent, #00FF88, transparent); opacity:0.6;"></div>
<div style="position:absolute; top:-60px; right:-60px; width:120px; height:120px; background:radial-gradient(circle, rgba(0,255,136,0.15) 0%, transparent 70%);"></div>
<a name="12-deployment-cicd"></a>
<h2 style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif; font-size:1.5em; font-weight:600; color:#E0E0E0; display:flex; align-items:center; gap:10px; margin:0 0 16px 0; padding-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.06);">
  <img src="docs/assets/svg/icon-bee2875cc587.svg" width="25" height="25" alt="" style="vertical-align:middle; max-width:100%;" /> 12. Deployment &amp; CI/CD
</h2>

### 12.1 Docker

| File | Target | Notes |
|------|--------|-------|
| `Dockerfile.northflank` | Northflank (primary) | Includes Node.js + mmdc for SVG rendering |
| `Dockerfile.fly` | Fly.io (secondary) | No mmdc (smaller image) |
| `docker-compose.yml` | Local dev | Both API + Dashboard, healthcheck, depends_on |

### 12.2 Platform Configs

- **Northflank:** `Dockerfile.northflank`, persistent volume at `/data`, port 8080
- **Render:** `render.yaml` — Free plan, Oregon region, `git lfs pull` build step
- **Fly.io:** `fly.toml` — `fly.toml` app config

### 12.3 CI/CD (GitHub Actions)

**.github/workflows/:**
| Workflow | Trigger | What it does |
|----------|---------|-------------|
| `ci.yml` | Push/PR | Build, test, lint, scan |
| `daily-ingest.yml` | Daily 03:00 UTC | Full pipeline run (prices, rainfall, NDVI, RDD, forecast) |
| `nightly-ingest.yml` | Daily | Ashoka historical import |
| `deploy-render.yml` | Push to master | Config validation |
| `deploy-pages.yml` | Push to master | Deploy docs to GitHub Pages |
| `heartbeat.yml` | Every 5min | Health check + Grafana metrics push |
| `dashboard-heartbeat.yml` | Every 10min | Streamlit dashboard health check |
| `verify-live-data.yml` | Hourly | End-to-end data verification |
| `check-freshness.yml` | Hourly | Data freshness monitoring |
| `render-pipeline-svg.yml` | Push | Render Mermaid → SVG via mmdc |

### 12.4 Environment Variables

```
MANDIIQ_DB_PATH="/data/mandi_iq.duckdb"      # DuckDB path
DATA_GOV_IN_API_KEY="..."                      # data.gov.in API key
GEMINI_API_KEY="..."                           # Google Gemini AI
NVIDIA_API_KEY="..."                           # NVIDIA NIM (DeepSeek)
OPENROUTER_API_KEY="..."                       # OpenRouter fallback
SENTINEL_CLIENT_ID="..."                       # Sentinel Hub
SENTINEL_CLIENT_SECRET="..."                   # Sentinel Hub
R2_ACCESS_KEY_ID="..."                         # Cloudflare R2 backup
R2_SECRET_ACCESS_KEY="..."
R2_ACCOUNT_ID="..."
R2_BUCKET="mandiiq-data"
GRAFANA_CLOUD_PROM_URL="..."                   # Grafana metrics
GRAFANA_CLOUD_PROM_USER="..."
GRAFANA_CLOUD_PROM_PASS="..."
```

### 12.5 Edge Proxy (`worker/worker.js`)

Cloudflare Workers script that serves SEO-friendly HTML shell to bots while proxying other requests to the main app.

---

</div></div></div>
<br />
<div style="position:relative; height:60px; overflow:hidden; width:100%; margin:8px 0;">
  <img src="docs/assets/svg/icon-dd24d242c628.svg" width="100%" height="60" alt="" style="vertical-align:middle; max-width:100%;" />
</div>
<br />
<div style="background:linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%); border:1px solid rgba(255,255,255,0.06); border-radius:16px; padding:24px 28px; margin:16px 0; box-shadow:0 8px 32px rgba(0,0,0,0.4); position:relative; overflow:hidden;">
<div style="position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg, transparent, #00FF88, transparent); opacity:0.6;"></div>
<div style="position:absolute; top:-60px; right:-60px; width:120px; height:120px; background:radial-gradient(circle, rgba(0,255,136,0.15) 0%, transparent 70%);"></div>
<a name="13-live-data-state"></a>
<h2 style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif; font-size:1.5em; font-weight:600; color:#E0E0E0; display:flex; align-items:center; gap:10px; margin:0 0 16px 0; padding-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.06);">
  <img src="docs/assets/svg/icon-a0c60dd90fca.svg" width="25" height="25" alt="" style="vertical-align:middle; max-width:100%;" /> 13. Live Data State
</h2>

### 13.1 Current Dataset (verified at 23:03 UTC, July 30, 2026)

| Metric | Value |
|--------|-------|
| Price rows | **1,334,647** |
| Commodities | **303** |
| States | **36** |
| Districts | **611** |
| Rainfall records | **2,278** |
| RDD causal estimates | **117** |
| NDVI districts | **605** (3,663 records) |
| Forecast models | **144** (144 valid) |
| Average MAPE | 702% (includes noisy sparse commodities) |
| Last pipeline run | OK (0 new rows, already up to date) |
| Auto-refresh | Hourly daemon thread running |

### 13.2 API Health (verified)

- **Server:** Running at `http://127.0.0.1:18765` (PID 31012)
- **/health** → HTTP 200, status=healthy
- **/freshness** → HTTP 200, 200 commodities
- **/pipeline.mmd** → HTTP 200, 5,793 bytes
- **/docs/index.html** → HTTP 200, 96,778 bytes

### 13.3 Browser Verification (Pipeline tab)

- All 8 KPI cards populated with live values
- Mermaid DAG rendered as `graphics-document` — all pipeline stages visible
- Commodity Freshness table showing 30+ commodities with live **30 Jul 2026** dates
- Auto-refresh countdown ticking from 60s
- **Zero console errors**

---

</div></div></div>
<br />
<div style="position:relative; height:60px; overflow:hidden; width:100%; margin:8px 0;">
  <img src="docs/assets/svg/icon-b350e4823cc5.svg" width="100%" height="60" alt="" style="vertical-align:middle; max-width:100%;" />
</div>
<br />
<div style="background:linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%); border:1px solid rgba(255,255,255,0.06); border-radius:16px; padding:24px 28px; margin:16px 0; box-shadow:0 8px 32px rgba(0,0,0,0.4); position:relative; overflow:hidden;">
<div style="position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg, transparent, #00FF88, transparent); opacity:0.6;"></div>
<div style="position:absolute; top:-60px; right:-60px; width:120px; height:120px; background:radial-gradient(circle, rgba(0,255,136,0.15) 0%, transparent 70%);"></div>
<a name="14-known-issues-pending-work"></a>
<h2 style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif; font-size:1.5em; font-weight:600; color:#E0E0E0; display:flex; align-items:center; gap:10px; margin:0 0 16px 0; padding-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.06);">
  <img src="docs/assets/svg/icon-f862fc7823f0.svg" width="25" height="25" alt="" style="vertical-align:middle; max-width:100%;" /> 14. Known Issues &amp; Pending Work
</h2>

### 14.1 Urgent

1. **Hardcoded API_BASE in docs/index.html** — Uses `http://127.0.0.1:18765` which breaks on deploy. Should be configurable via URL query param `?api=...` or use relative paths when served from FastAPI.

2. **Mermaid diagram styling doesn't render client-side** — The `linkStyle`/`classDef` directives in `pipeline-flow-live.mmd` use syntax only supported by the `mmdc` CLI tool (Puppeteer-backed). Nodes render, but custom colors don't apply client-side. Pre-rendered SVG exists at `diagrams/pipeline-flow-live.svg` — should serve that as fallback.

### 14.2 Moderate

3. **DuckDB index corruption on DELETE+UPDATE** — Previously fixed in `backfill_state.py` (switched to INSERT OR REPLACE). The `_refresh_freshness` method in `duckdb_store.py` may still use the old DELETE+INSERT pattern. Check and apply same fix.

4. **100ms setTimeout for lazy init** — Tab switching and mermaid render use `setTimeout(fn, 100)` which is fragile on slow page loads. Should use `requestAnimationFrame` in a retry loop.

5. **StaticFiles mount silently skipped** — `app.mount("/docs", ...)` is guarded by `if _docs_path.exists()`. No log message either way. Add a log line so operators know if docs are being served.

6. **Freshness API column names** — `/freshness` returns `row_count`, `n_districts`, `n_states` (not `rows`, `districts`, `states`). Some dashboard code may use old names.

### 14.3 Minor

7. **Inline script syntax — regex double-backslash** — Two bugs found and fixed: `/\\\\/+$/` (premature regex close, blocked ALL JS) and `/```mermaid\\\\n?/g` (code fence not removed, broke mermaid rendering). These are fixed but the pattern could recur — review any `.replace(regex, ...)` calls in inline JS.

8. **Freebuff proxy on port 10941** — The Freebuff Desktop proxy intercepts port 10941, returning "Freebuff Desktop" HTML instead of FastAPI responses. Use a different port (e.g., 18765) for local development.

9. **Temp files** — Files starting with `_` (e.g., `_fix_*.py`, `_audit_*.py`, `_test_*.py`) are debugging artifacts. Review and clean up periodically.

### 14.4 Features Not Yet Implemented

10. **Sentinel Hub retry for remaining 48 districts** — Free tier capped at 592/640 districts. Need `fetch_missing_ndvi()` with token refresh to mop up remaining.

11. **Northflank cron job for hourly pipeline** — Currently only Windows scheduled task exists. Add cron definition to `Dockerfile.northflank` or Northflank config.

12. **Forecast model for LSTM comparison** — LSTM code exists in `lstm_forecast.py` but requires PyTorch. Not installed in production Docker images.

---

</div></div></div>
<br />
<div style="position:relative; height:60px; overflow:hidden; width:100%; margin:8px 0;">
  <img src="docs/assets/svg/icon-f49ec25352f2.svg" width="100%" height="60" alt="" style="vertical-align:middle; max-width:100%;" />
</div>
<br />
<div style="background:linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%); border:1px solid rgba(255,255,255,0.06); border-radius:16px; padding:24px 28px; margin:16px 0; box-shadow:0 8px 32px rgba(0,0,0,0.4); position:relative; overflow:hidden;">
<div style="position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg, transparent, #00FF88, transparent); opacity:0.6;"></div>
<div style="position:absolute; top:-60px; right:-60px; width:120px; height:120px; background:radial-gradient(circle, rgba(0,255,136,0.15) 0%, transparent 70%);"></div>
<a name="15-local-development"></a>
<h2 style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif; font-size:1.5em; font-weight:600; color:#E0E0E0; display:flex; align-items:center; gap:10px; margin:0 0 16px 0; padding-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.06);">
  <img src="docs/assets/svg/icon-f862fc7823f0.svg" width="25" height="25" alt="" style="vertical-align:middle; max-width:100%;" /> 15. Local Development
</h2>

### 15.1 Quick Start

```bash
# 1. Set environment variables (copy template)
cp .streamlit/secrets_template.toml .streamlit/secrets.toml
# Edit secrets.toml with your API keys

# 2a. Install API dependencies (lighter, no streamlit/prophet)
pip install -r requirements/api.txt

# 2b. Install dashboard dependencies (includes streamlit + prophet)
pip install -r requirements/dashboard.txt

# 3. Start FastAPI server (port 18765 to avoid Freebuff proxy on 10941)
python -c "import uvicorn; uvicorn.run('mandi_rdd.api.main:app', host='127.0.0.1', port=18765)"

# 4. In another terminal, start Streamlit dashboard
streamlit run mandi_rdd/dashboard/app.py --server.port=8501

# 5. Run hourly ingestion
python run_hourly.py --force-full

# 6. Open docs
open http://127.0.0.1:18765/docs/index.html
```

### 15.2 Running Tests

```bash
# Headless API endpoint test
python _verify_endpoints.py

# Inline script syntax check
python -c "
import re, subprocess, tempfile, os
with open('docs/index.html') as f:
    content = f.read()
matches = re.findall(r'<script>(.*?)</script>', content, re.DOTALL)
for i, script in enumerate(matches):
    script = script.strip()
    if len(script) > 20:
        fname = tempfile.mktemp(suffix='.js')
        with open(fname, 'w') as f:
            f.write(script)
        result = subprocess.run(['node', '--check', fname], capture_output=True, text=True)
        os.unlink(fname)
        status = 'OK' if result.returncode == 0 else f'ERROR: {result.stderr[:100]}'
        print(f'Block {i}: {status}')
"

# Data integrity check
python -c "from mandi_rdd.storage.duckdb_store import get_connection
c = get_connection(read_only=True)
print(c.execute('PRAGMA integrity_check').fetchall())
c.close()"
```

### 15.3 Building the Frontend

```bash
cd mandi_rdd/dashboard/frontend
npm install
npm run build
# Output: dist/assets/index-*.js
```

### 15.4 Generating Pipeline Diagrams

```bash
# Install mermaid-cli
npm install -g @mermaid-js/mermaid-cli

# Render Mermaid → SVG
mmdc -i diagrams/pipeline-flow-live.mmd -o diagrams/pipeline-flow-live.svg -b transparent -w 1200
```

---

</div></div></div>
<br />
<div style="position:relative; height:60px; overflow:hidden; width:100%; margin:8px 0;">
  <img src="docs/assets/svg/icon-b53c27cb21fd.svg" width="100%" height="60" alt="" style="vertical-align:middle; max-width:100%;" />
</div>
<br />
<div style="background:linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%); border:1px solid rgba(255,255,255,0.06); border-radius:16px; padding:24px 28px; margin:16px 0; box-shadow:0 8px 32px rgba(0,0,0,0.4); position:relative; overflow:hidden;">
<div style="position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg, transparent, #00FF88, transparent); opacity:0.6;"></div>
<div style="position:absolute; top:-60px; right:-60px; width:120px; height:120px; background:radial-gradient(circle, rgba(0,255,136,0.15) 0%, transparent 70%);"></div>
<a name="recent-verifications"></a>
<h2 style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif; font-size:1.5em; font-weight:600; color:#E0E0E0; display:flex; align-items:center; gap:10px; margin:0 0 16px 0; padding-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.06);">
  <img src="docs/assets/svg/icon-5fc91c87ca3d.svg" width="25" height="25" alt="" style="vertical-align:middle; max-width:100%;" /> Recent Verifications
</h2>

### Syntax Bugs Found &amp; Fixed (July 30, 2026)

1. **Critical SyntaxError blocked all JS execution** — regex `/\\\\/+$/` had double backslash (`\\`) causing premature regex close at `/`. Hex bytes `2f 5c 5c 2f 2b 24 2f` → `2f 5c 2f 2b 24 2f`. **Fix:** Binary-safe replacement in `docs/index.html`.

2. **Mermaid cleanup regex didn't match** — `.replace(/```mermaid\\\\n?/g, '')` used `\\n` (literal backslash + n) instead of `\n` (newline). **Fix:** `\\n` → `\n` at bytes 85901 and 85932.

3. **Zero console errors** confirmed after both fixes.

### Build &amp; Test Commands

- `node --check` on the 26,045-char inline script → **PASSED**
- API endpoint headless test `/health`, `/freshness`, `/pipeline.mmd`, `/docs/index.html` → **ALL PASSED**
- Browser preview Pipeline tab → **Live KPI values, mermaid DAG rendered, zero console errors**

---

> **End of Handoff Document**  
> This document is intended to provide complete context for a new agent to understand, navigate, and extend the MandiIQ codebase.

</div></div></div>

<div align="center">
<br />
<a href="#" style="display:inline-block; padding:8px 20px; border-radius:10px; background:linear-gradient(135deg, rgba(0,255,136,0.12) 0%, rgba(0,255,136,0.04) 100%); border:1px solid rgba(0,255,136,0.2); color:#00FF88; font-weight:500; text-decoration:none; font-size:14px;">&#x2191; Back to Top</a>
<br /><br />
</div>