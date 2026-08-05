# Progress Log — MandiIQ Omega Roadmap

## Session: 2026-08-04

### Phase 1: Requirements & Discovery

- **Status:** complete
- **Started:** 2026-08-04
- **Actions taken:**
  - Marked task `019fcc12-cc62-77d1-b4ad-0a1c5db496f6` in_progress
  - Audited repo: README, HANDOFF, technical-writeup, requirements.txt, module tree, tests, 25 GH workflows
  - Verified: FastAPI / Streamlit 1.59.2 / DuckDB (~1.33M rows) / XGBoost+SHAP / Prophet / RDD engine / OpenRouter AI
  - Confirmed no existing Omega spec or planning files in repo
- **Files created/modified:** none (audit only)

### Phase 2: Roadmap Authoring

- **Status:** complete
- **Started:** 2026-08-04
- **Actions taken:**
  - Authored Omega layer architecture (QVE/AAS/EIC/HRP/CRSM/SMCL/NIL) with working definitions
  - Built module dependency graph (ASCII + mermaid) + adjacency table
  - Set 5-wave sequencing (core → AAS/EIC → QVE/HRP/CRSM → SMCL → NIL)
  - Set priority tiers: Tier 1 (core/AAS/EIC) → Tier 4 (NIL emulated)
  - Assigned DoD global + per-module; ownership mapped to team slots
- **Files created/modified:**
  - `planning/task_plan.md` (created, 189 lines)
  - `planning/findings.md` (created)
  - `planning/progress.md` (created, this file)

### Phase 3: Review & Handoff

- **Status:** complete
- Reported roadmap paths + wave-2 dependency graph to leader; leader confirmed wave-2 underway (Core building omega/core+AAS+EIC; QVE live, 39 routes, `/qve/placement` returns real particles).

### Phase 4: Test Suite Expansion — prep (task 019fcc12-ee5f-7662-b231-0e0062924d08)

- **Status:** complete (drafting; execution gated on AAS/EIC landing)
- **Actions taken:**
  - Marked test task in_progress
  - Identified pytest layout: `mandi_rdd/tests/` package, `test_<name>.py`, importorskip/_require_module guards, `skipif(not DB_PATH)` for DB tests, TestClient for API, `routes.py` inventory
  - Identified CI: `ci.yml` (full pytest+cov+ruff), `mandi_rdd_ci.yml` (test_verification), `dashboard-integration.yml` (Playwright E2E scrolling `routes.py`)
  - Drafted integration test plan: QVE/AAS/EIC + `/qve/placement` data contract skeleton (status/seed/objective/particles/best/elapsed_ms/config), feasibility+determinism+best-tracking contract cases, AAS/EIC/core pending-module tests, integration gate + wave-2 gating rule
  - Verified `/qve/placement` route present in `mandi_rdd/api/main.py:2349` (tag Omega); omega modules not yet in this checkout
- **Files created/modified:**
  - `planning/integration_test_plan.md` (created, 131 lines)
  - `planning/progress.md` (updated, this file)
- **Next:** reconcile contract [TBD] fields with live `qve.py` (leader/engineers), add omega routes to `tests/routes.py`, verify CI `paths:` include `mandi_rdd/omega/**`, run full suite once AAS/EIC land.

### Phase 4b: Contract Reconciliation (leader feedback)

- **Status:** complete
- **Actions taken:**
  - Confirmed checkout IS current: `mandi_rdd/omega/{qve.py,__init__.py}` present (my earlier Glob missed them), real DB `mandi_rdd/data/mandi_iq.duckdb` present
  - Read live implementation: `omega/qve.py` (`compute_placement`, `solve_placement_simulated_annealing`, `build_particles_from_db`, `build_qubo`) + `api/main.py:2349` handler + `main.py:60` import
  - **Replaced draft contract with LIVE schema**: `{engine, n_particles, energy, schedule{iterations,t_start,t_end}, wall_time_s, particles[{id,commodity,region,date,prediction,confidence,significance,shap_values,model_version,position[3],energy,color[3],glow,size}]}`; params `commodity/limit(60)/n_iter(4000)/seed`; errors → `500 {"error":str}`; empty → 200 + `warning`
  - Wrote 9 contract test cases + 4 unit-test groups for `omega/qve.py` into `planning/integration_test_plan.md` (v2, 152 lines)
  - **Layer-name correction:** `omega/__init__.py` defines CRSM = **Cross-Reality State Mesh** (CRDT/yjs), not Causal Risk Scenario Model; EIC = "Explainable Intelligence" (causal discovery + meta-learning) — roadmap Key Question #1 resolved
- **Files created/modified:** `planning/integration_test_plan.md` (rewritten v2), `planning/progress.md` (this entry)
- **Next:** draft `test_omega_qve.py` (+ import-safe stubs for aas/eic/core), update `tests/routes.py`, verify CI `paths:`, run suite when AAS/EIC land.

### Phase 4c: Test files drafted (leader greenlight)

- **Status:** complete (files drafted + syntax-checked; full-suite run HOLDING per leader gate)
- **Actions taken:**
  - Confirmed ALL omega modules present in checkout: `omega/{core,aas,eic,qve}.py` + `__init__.py`; endpoints `/qve/placement` (main.py:2349), `/omega/status`, `/omega/pipeline` exist
  - Mapped interfaces: `Particle` dataclass, `build_qubo`, `solve_placement_simulated_annealing`, `build_particles_from_db`, `compute_placement` (qve); `OmegaCore.module_status/run_pipeline/snapshot` (core); `run_agent_swarm`/`engine_status` (aas); `causal_discovery`/`generate_insights`/`engine_status` (eic)
  - Leader confirmed canonical names (CRSM=Cross-Reality State Mesh, EIC=Explainable Intelligence, QVE=Quantum Valuation Engine, AAS=Adaptive Alert System) — no relabel
  - Wrote 4 test files + routes.py update (below); all `python -m py_compile` OK
- **Files created/modified:**
  - `mandi_rdd/tests/test_omega_qve.py` (205 lines — 14 tests: unit + DB + API contract)
  - `mandi_rdd/tests/test_omega_core.py` (65 lines — registry/pipeline/snapshot)
  - `mandi_rdd/tests/test_omega_aas.py` (74 lines — swarm/severity/determinism)
  - `mandi_rdd/tests/test_omega_eic.py` (70 lines — engine/causal discovery/insights)
  - `mandi_rdd/tests/routes.py` (added `OMEGA_API_PATHS` — API-only inventory, kept out of Streamlit ROUTES)
- **Determinism note:** comparisons exclude `wall_time_s` (non-deterministic by nature); placement/positions/energy are seed-reproducible.
- **Next:** verify CI `paths:` include `mandi_rdd/omega/**`; when leader lifts gate → run full pytest suite + E2E → consolidated status report.

### Phase 5: FINAL — Integration Verification + Consolidated Build Report

- **Status:** complete ✅ (task `019fcc12-ee5f-7662-b231-0e0062924d08` deliverable)
- **Actions taken:** full suite run, endpoint probes, repo audit for Northflank/3D status.

---

# CONSOLIDATED OMEGA WAVE-2 BUILD REPORT (2026-08-04)

## 1. Test results — FULL SUITE GREEN ✅
Command: `python -m pytest -q --ignore=scripts --ignore=mandi_rdd/tests/test_screenshots.py` (screenshots = Playwright E2E, environment-gated)
**Result: 60 passed in 6.40s — 0 failed, 0 skipped.** Matches leader-reported 60. No regressions.

| Test file | Result |
|---|---|
| `mandi_rdd/tests/test_omega_qve.py` (14) | pass |
| `mandi_rdd/tests/test_omega_core.py` (4) | pass |
| `mandi_rdd/tests/test_omega_aas.py` (5) | pass |
| `mandi_rdd/tests/test_omega_eic.py` (6) | pass |
| `test_omega_endpoints.py` (leader's, seeded in-mem DB, 6) | pass |
| root `test_omega_eic.py` (leader's EIC-fix tests, 9) | pass |
| legacy suite (test_verification, test_db_fallback, test_dashboard_smoke, test_backfill_lifecycle, data_integrity, test_ensemble, test_forecast_model, …) | pass |

Leader-fixed pre-existing bugs confirmed resolved: malformed CSS-brace regex in `test_dashboard_smoke.py`; `'module' object is not callable` Playwright importorskip in `conftest.py`; stale 500→422 contract test corrected (endpoint now typed `limit: int` → FastAPI 422 on `limit=abc`, verified live).

## 2. Omega engines — LIVE & non-degraded ✅
`mandi_rdd/omega/{core,aas,eic,qve}.py` all present; Vercel verified:
- `/qve/placement` → **n_particles 60**, engine `simulated-annealing`, real particles w/ 3D-ready fields (position[3], color[3], glow, size)
- `/omega/status` → layer registry, `dwave_emulated=True`
- `/omega/pipeline` → **degraded=False**, n_particles=60 → n_alerts=117 → n_edges=414, state_hash=635d3e663681c1fc, wall_time_s≈5.26s
- Top market drivers: Carrot (out-degree 21), Lentils-urad (16), Arhar (16), Bajra (14)
- EIC blockers resolved by leader: granger lag-alignment (`series[max_lag:]`), zero-variance mask (std>1e-12), F-stat denominator guard (rss_u<=1e-12)

## 3. Deployment — Vercel LIVE; **Northflank REDEPLOY GAP** ⚠️
- **Vercel:** OMEGA wave-2 pushed to master → deployed → endpoints verified live (non-degraded).
- **Northflank (PRIMARY prod target, per HANDOFF/DEPLOY):** `Dockerfile.northflank` (port 8080, persistent volume `/data`, includes Node.js + mmdc) — **wave-2 has NOT been redeployed there yet**. Two gaps:
  1. **Redeploy needed:** push/redeploy OMEGA wave-2 (omega modules + typed endpoint contract) to Northflank to match Vercel.
  2. **Hourly pipeline cron:** still Windows scheduled-task only; Northflank cron job not yet defined (HANDOFF:988) — should be added to `Dockerfile.northflank`/Northflank config.
- CI: no `paths:` filters in any workflow → omega changes trigger full suite automatically (verified).

## 4. Endpoint contract (reconciled, LIVE schema)
- `GET /qve/placement?commodity&limit=60&n_iter=4000&seed` →
  `{engine:"simulated-annealing", n_particles, energy, schedule{iterations,t_start,t_end}, wall_time_s, particles[{id,commodity,region,date,prediction,confidence,significance,shap_values,model_version,position[3],energy,color[3],glow,size}]}`
- Validation error (non-int limit) → **422** (typed param). Empty → 200 + `warning`. Internal errors → 500 `{"error": str}`.
- `POST /omega/pipeline` → merged `pipeline_status_summary` top-level (dashboard-friendly): `degraded`, `state_hash`, per-stage stats.

## 5. 3D field status (Wave 5 NIL) ⏳
- **Present (decorative):** Three.js/React-Three-Fiber WebGL hero particle field (2000 particles, `mandiq-webgl-hero-root`), `docs/mandiq-portals.js` canvas particle field, `mandiq-effects.js` flow-field.
- **Not yet wired:** QVE placement 3D field (render `/qve/placement` particles w/ position/color/glow/size) — no omega Streamlit page exists yet (pages list has no `omega_*.py`). Contract is 3D-ready; **frontend binding is a Wave 5 NIL deliverable** (Visualization Engineer). Current visualization = 2D/Streamlit fallback via API JSON.

## 6. DoD status (task `019fcc12-ee5f-7662-b231-0e0062924d08`)
- [x] Contract reconciled (no [TBD])
- [x] `test_omega_*.py` drafted (14+4+5+6) + leader's endpoint/EIC suites — all green
- [x] `routes.py` updated (`OMEGA_API_PATHS`; kept out of Streamlit ROUTES)
- [x] CI `paths:` verified (none exist → full suite always runs)
- [x] Full suite green, no regressions (60 passed)
- [x] Consolidated status report delivered to leader
- ⚠️ Follow-ups for leader/team: Northflank wave-2 redeploy + cron; QVE 3D field binding (Wave 5, Viz Eng.)

## Phase 6 (post-report addendum, 2026-08-04)

### Northflank gap RESOLVED + QVE performance fix (leader)

**Status:** complete

**Leader remediation of the two flagged gaps:**

1. **Northflank redeploy gap — RESOLVED.** The PM's Phase-5 report predated two leader pushes that closed this:
   - Push `1178f87..b96f061` (OMEGA wave-2, all engines + endpoints) triggered Northflank's git-repo auto-deploy ("From Git Repository" → master). **Verified live: `code.run` `/omega/status` returns OMEGA wave-2 with all 4 modules (qve/aas/eic/crsm), 39 routes.**
   - Push `9843f2e..377ec16` (QVE incremental SA + summary fusion) — verified live in deploy poll below.
2. **QVE pipeline timeout — FIXED (root cause + optimization).** On the production 305-commodity dataset, `solve_placement_simulated_annealing` re-scanned ALL O(n^2) QUBO pairs on every iteration (O(n_iter·n^2) ≈ ~185M ops → >280s timeout). Leader rewrote it with **incremental O(n) energy updates** per move (O(n_iter·n)) — verified numerically identical to canonical energy. Benchmark: n=59 → 0.18s; n=120 → 0.41s; **n=305 → 1.75s (was >280s, ~160x).**
   - Also fused `n_insights` + `market_drivers` into top-level `pipeline_status_summary` (dashboards/3D consume them directly).

**LIVE DEPLOY POLL (6 rounds, 15s apart) — both targets healthy, non-degraded:**

| Target | P50 response | degraded | particles | alerts | edges |
|---|---|---|---|---|---|
| Vercel `test-mandi.vercel.app` | **1.2s** | False | 40 | 78 | 484 |
| Northflank `code.run` | **6.2s** | False | 40 | 78 | 379 |

Both consistent across all 6 rounds. Northflank is wave-2, fast (no more >280s timeout), and non-degraded at production scale.

**Remaining (Wave 5 NIL / non-blocking):** QVE 3D field binding (render `/qve/placement` particles in the WebGL hero) — Visualization Engineer deliverable, still in_progress; optional Northflank hourly-cron (currently Windows scheduled-task).

## Test Results

| Test | Input | Expected | Actual | Status |
|---|---|---|---|---|
| full unit suite (excl. Playwright screenshots) | `pytest -q --ignore=scripts` | 60 passed, 0 fail | 60 passed in 6.40s | ✅ |
| `/qve/placement?limit=10` | TestClient | 200, n_particles>0, schema 1:1 | 200, 10 particles | ✅ |
| `/qve/placement?seed=42` ×2 | TestClient | identical (excl. wall_time_s) | identical | ✅ |
| `/qve/placement?limit=0` | TestClient | 200 + warning | 200, n_particles 0, warning | ✅ |
| `/qve/placement?limit=abc` | TestClient | 422 (typed param) | 422 | ✅ |
| `run_pipeline(limit=10,n_iter=100)` | direct call | dict w/ protocol + stages{qve,eic} | pass | ✅ |

## Error Log

---

## Session: 2026-08-05 - Live-Deployment Monitoring & Hardening (Phase 7)

- **Result:** All live deployments (Vercel, Northflank code.run, Streamlit, GitHub) audited end-to-end; two latent bugs found + fixed.
- **Bug 1 - CI red (5 runs):** mandi_rdd/api/metrics_push.py imports prometheus_client at module load but it was missing from runtime reqs. CI clean env crashed on import. **Fix:** added prometheus-client, python-dotenv, jsonschema, urllib3 to mandi_rdd/requirements.txt. Verified on fresh Py3.11 env (51 passed, 0 failures). CI now green.
- **Bug 2 - Streamlit empty shell (backend never starts):** PEP 701 f-strings (backslash / nested same-quote) in theme.py + components.py are SyntaxErrors on Python 3.11 (Cloud runtime); local 3.12 masked them. **Fix:** backported to 3.11-compatible precomputed vars. All 89 files compile clean under Py3.11.15.
- **Also added:** root streamlit_app.py entrypoint so Streamlit Cloud auto-detects the nested dashboard app; mandi_rdd/tests/live_audit.py (Playwright+Brave live monitor); README live-services correction (Vercel URL) + OMEGA wave-2 endpoints table.
- **Committed/pushed:** cc2bc0a (docs), 57ceb74 (gitignore), 52633a0 (entrypoint), 56c223d (f-string fix). CI: green on all 3 latest.


### Phase 7 addendum (final hardening pass)

- **Streamlit Cloud free-tier now LIVE.** Rebuild finished. Verified at
  https://test-mandi-keae7eruks2n4cqvumjfu8.streamlit.app : websocket
  CONNECTED, sidebar renders all 10 pages (Executive Overview, Discontinuity,
  Forecast, Risk Map, Satellite, Discount Simulator, Ask MandiIQ, Settings,
  About, Components), 200-commodity freshness table paginated, 10/10 pages
  audited via Brave (0 exceptions); Discount Simulator "Run Simulation"
  functional (graceful "Model Not Available" when classifier absent, no crash).
- **Fixed sidebar health dot** (was permanently "Degraded"): app.py imported
  nonexistent `check_health` -> always hit except -> amber. Now uses real
  `health_check_all()` and maps no-provider -> green. Live verified green +
  "All healthy".
- **Fixed `Dashboard Integration` GitHub workflow that had NEVER passed
  (16/16 red since Jul 30).** Two root causes:
  1. Boot step aborted on attempt 1 under `set -e`: curl returned nonzero
     (ECONNREFUSED) while Streamlit cold-started. Fixed to map to `000` and
     poll up to 110s with clear failure diagnostics.
  2. `pytest`/`pytest-timeout` were never installed in that workflow; and
     `test_dashboard_integration.py` did not exist. Added install of test deps
     and a real integration test (root 200 /_stcore/health ok / static bundles
     / page metadata) that skips gracefully when no dashboard is running.
- Verified final live state (all autonomous numbers):
  - Northflank `/omega/pipeline`: 60 particles, energy ~80, 117 alerts, 426+
    edges, 10 insights, 5 drivers (scipy enabled, 305 commodities).
  - Vercel `/omega/pipeline` (POST): 200, 60 particles, energy ~90 (root 404
    is expected - API-only).
  - 3D quantum field live at flawsom.github.io/test-mandi/dashboards/omega-field.html:
    60 PARTICLES, energy 69.47, 114 alerts, 426 edges, market drivers (Carrot,
    Arhar, Lentil...), full controls, no JS errors.
  - CI all green incl. the previously-red Dashboard Integration workflow.
