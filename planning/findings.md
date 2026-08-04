# Findings & Decisions — MandiIQ Omega Roadmap

## Requirements (from leader kickoff)

- Create the **Omega implementation roadmap** using file-based planning method.
- Audit the repo first: deployed **FastAPI / Streamlit / DuckDB** platform.
- Write `task_plan.md`, `findings.md`, `progress.md` into the repo (root or `/planning`).
- Define **module dependency graph** for Omega layers: **QVE / AAS / EIC / HRP / CRSM / SMCL / NIL**.
- Prioritize **achievable vs aspirational**: EEG / D-Wave / holograms unavailable → **emulate** (simulated annealing, 3D web / Streamlit fallbacks).
- **Definition-of-done per module + ownership.**
- Report back when files are in place (paths + wave-2 dependency graph for AAS/EIC sequencing).

## Research Findings — Repo Audit (2026-08-04)

### Tech stack (verified from repo)

| Area | Technology | Evidence |
|---|---|---|
| Backend API | FastAPI | `mandi_rdd/api/main.py` (~1,100 lines), `api/index.py` |
| Dashboard | Streamlit 1.59.2 | `mandi_rdd/dashboard/app.py`, 14 routes, `pages/` |
| Storage | DuckDB | `storage/duckdb_store.py` (~1.33M price rows, 117 RDD estimates, 144 forecast models) |
| ML | XGBoost + SHAP | `analysis/classifier.py`; `analysis/static_proof.py` |
| Forecasting | Prophet + seasonal-naive + LSTM | `analysis/forecast.py`, `lightweight_forecast.py`, `lstm_forecast.py` |
| Causal engine | RDD (regression discontinuity) | `analysis/rdd_engine.py`, `lightweight_rdd.py`, `fixed_effects.py`, `robustness.py` |
| AI layer | OpenRouter-based orchestrator | `ai/orchestrator.py`, `ai/router.py` (Ask page) |
| Prescriptive | Procurement advisor | `analysis/prescriptive.py` |
| Ingestion | Scheduled fetchers | `ingestion/fetch_prices.py`, `fetch_ndvi.py`, `fetch_rainfall.py`, `scheduler.py`, `backfill_state.py` |
| Ops | GitHub Actions ×25, R2 backup, Grafana | `.github/workflows/` (`daily-full-analysis`, `hourly-duckdb-sync`, `ci`, `deploy-vercel`, `check-health`, …) |

### Module map (`mandi_rdd/`)

`ai/ analysis/ api/ core/ dashboard/ ingestion/ storage/ scripts/ tests/` — plus `run_nightly.py`.

### Test suite (existing)

`mandi_rdd/tests/`: `conftest.py`, `test_dashboard_smoke.py`, `test_db_fallback.py`, `test_screenshots.py`, `test_backfill_lifecycle.py`, `test_verification.py`, `data_integrity.py`, `routes.py` + root `test_ensemble.py`, `test_forecast_model.py`.

### Deployment / CI

- Vercel (FastAPI), Streamlit Cloud (dashboard), GitHub Actions ×25 incl. CI, health checks, drift detector, dashboard heartbeat/sync.

### Constraints & known issues (from HANDOFF)

1. **No Omega spec exists in the repo** — layer definitions authored in this roadmap; needs leader confirmation (see task_plan Key Questions).
2. **LSTM requires PyTorch** — not in prod images; treat as optional/emulated-path dependency.
3. **Sentinel Hub missing ~48 districts** — NDVI coverage gap; AAS must degrade gracefully.
4. **DuckDB DELETE+INSERT corruption pattern** (HANDOFF §14.2) — omega schema mandates **INSERT OR REPLACE**.
5. **Freshness/health checkers exist** (`check_freshness.py`, `verify_live_data.py`) — AAS can reuse these signals.
6. Existing frontend already includes **Three.js** (3D web) — NIL hologram-emulation can build on it.

## Technical Decisions

| Decision | Rationale |
|---|---|
| Deliverables at `planning/` in repo root | Leader allowed root or `/planning`; keeps root tidy |
| New `mandi_rdd/omega/` package for all 7 layers | Separable from legacy `analysis/`; clean dependency graph |
| Wave 2 = AAS + EIC, parallel-safe | Leader needs wave-2 graph now; AAS and EIC have zero interdependency |
| QVE = simulated annealing (classical analog of D-Wave annealing) | Hardware unavailable; SA is the canonical classical stand-in |
| NIL = emulated neural layer (attention/LSTM) + 3D web w/ Streamlit fallback | EEG/holograms unavailable; reuse Three.js + existing `/ask` NL surface |
| INSERT OR REPLACE for all omega DuckDB tables | Avoids known corruption pattern |

## Resources

- Repo root: `C:\Users\sibap\Downloads\MandiIQ-fda91857aaccd6f0b44bc9a0fc770a9e5ddb22e0`
- Handoff: `HANDOFF.md` (architecture, ingestion, storage, deployment, known issues)
- Writeup: `technical-writeup.md` (RDD methodology)
- Requirements: `requirements.txt`
- Tests: `mandi_rdd/tests/`; CI: `.github/workflows/` (25 workflows)

## Visual/Browser Findings

- None (no browser ops performed; audit was file-based).
