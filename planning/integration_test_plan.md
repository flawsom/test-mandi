# Omega Integration Test Plan — QVE / AAS / EIC + `/qve/placement` data contract

**Owner:** Tech PM `019fcc12-7882-79c0-9912-92a1a55105cd` · Task `019fcc12-ee5f-7662-b231-0e0062924d08`
**Status:** DRAFT v2 (contract reconciled with live implementation) — QVE live & verified; AAS/EIC building.
**Checkout status (confirmed 2026-08-04):** the checkout IS current — `mandi_rdd/omega/{qve.py,__init__.py}` exist, real DB `mandi_rdd/data/mandi_iq.duckdb` present. `/qve/placement` at `api/main.py:2349`, wired via `main.py:60` import.
**Rule:** do not execute wave-2 (AAS/EIC) tests until those modules land in this checkout. QVE tests can be written now against the live schema.

---

## 1. Pytest layout (identified)

Tests are a **pytest package** under `mandi_rdd/tests/` with naming `test_<name>.py`:

| Existing file | Role |
|---|---|
| `conftest.py` | shared fixtures (e.g., screenshots) |
| `routes.py` | route/market inventory used by dashboard smoke + E2E |
| `test_verification.py` | path-resolution + data-integrity (no GPU/API keys) |
| `test_db_fallback.py` | DuckDB path-resolution regressions (TestClient + storage) |
| `test_dashboard_smoke.py` | Streamlit/api smoke |
| `test_backfill_lifecycle.py`, `test_screenshots.py`, `data_integrity.py` | backfill/E2E/data contract |

**Conventions to mirror:**
- **Optional deps guard:** `_require_module("mandi_rdd.omega.aas")` → `pytest.skip` (see `test_verification.py:22`) or `pytest.importorskip`. **Critical** so CI stays green before AAS/EIC land.
- **DB-dependent tests:** `@pytest.mark.skipif(not DB_PATH.exists(), ...)` — DB present in this checkout, so QVE real-data tests run.
- **API tests:** FastAPI `TestClient` against the app from `mandi_rdd.api.main`.
- **Route contract checks:** extend `tests/routes.py` inventory with the new omega routes.

### Proposed new omega test files
| File | Covers |
|---|---|
| `mandi_rdd/tests/test_omega_core.py` | layer registry, idempotent schema (INSERT OR REPLACE), `/omega/status` |
| `mandi_rdd/tests/test_omega_qve.py` | `omega/qve` SA solver **+ `/qve/placement` data contract** (below) |
| `mandi_rdd/tests/test_omega_aas.py` | alert signals, severity, dedup, persistence (`omega_alerts`) — [pending module] |
| `mandi_rdd/tests/test_omega_eic.py` | SHAP summary, causal narrative, `/omega/explain/{commodity}` — [pending module] |

---

## 2. CI workflows (identified)

| Workflow | What it runs | Relevance to omega |
|---|---|---|
| `.github/workflows/ci.yml` | full `pytest mandi_rdd/tests/` + coverage + ruff (Py 3.10/3.11) | **Primary gate.** Omega tests must be import-safe (skip when module absent) so a partial merge stays green. |
| `.github/workflows/mandi_rdd_ci.yml` | `tests/test_verification.py` (Py 3.12) + nightly ingest | sanity gate; add omega verification checks here if lightweight |
| `.github/workflows/dashboard-integration.yml` | Playwright E2E vs Streamlit, scrolls `routes.py` (Py 3.12) | add `/qve/placement` + any omega dashboard page to the route scroll |

**Action item:** verify CI `paths:` filters include `mandi_rdd/omega/**` and `mandi_rdd/tests/test_omega_*.py` so omega PRs trigger the suite (esp. `ci.yml`, `dashboard-integration.yml`).

---

## 3. `/qve/placement` data contract (RECONCILED — live schema)

**Reference:** `mandi_rdd/api/main.py:2349` `@app.get('/qve/placement', tags=['Omega'])` → `mandi_rdd/omega/qve.py:compute_placement` (imported `main.py:60`).

**Live contract snapshot** (verified against `compute_placement`, 2026-08-04):

```jsonc
{
  "engine": "simulated-annealing",   // constant
  "n_particles": 60,                 // int; n_particles == len(particles)
  "energy": 12.3456,                 // float (rounded 4dp) — final QUBO objective
  "schedule": {"iterations": 4000, "t_start": 5.0, "t_end": 0.01},
  "wall_time_s": 0.12,               // float (rounded 3dp)
  "particles": [
    {
      "id": "rdd:onion:ALL",         // str, unique (prefix rdd: / fc: / px:)
      "commodity": "onion",
      "region": "ALL",               // str
      "date": "",                    // str ("" for auto particles)
      "prediction": 12.5,            // float | null (RDD effect / MAPE-conf / row count)
      "confidence": 0.8333,          // float, 4dp
      "significance": 0.75,          // float, 4dp
      "shap_values": {"rdd_effect": 1.2},  // dict[str, float]
      "model_version": "rdd-engine", // str: rdd-engine | prophet-ensemble | prices-snapshot
      "position": [1.2, -0.4, 3.1],  // float[3], 4dp  ← 3D viz
      "energy": 0.5123,              // float, 4dp (per-particle share)
      "color": [0.4, 0.6, 1.0],      // float[3], 4dp  ← viz palette
      "glow": 0.8,                   // float, 4dp
      "size": 1.6                    // float, 4dp
    }
  ]
}
```

- **Query params (confirmed):** `commodity` (opt), `limit` (default 60), `n_iter` (default 4000), `seed` (opt).
- **Error contract (confirmed):** any exception → **`500 {"error": str}`** (`JSONResponse`, not HTTPException).
- **Empty-data path (confirmed):** → **200** with `n_particles:0`, `energy:0.0`, `schedule:{}`, `wall_time_s:0.0`, `particles:[]`, plus a **`warning`** key ("No particles could be built…").
- **Data sources:** `rdd_results` (significance) → `fc:…`/`prophet-ensemble`; `forecast_metrics` (confidence) → `px:…`/`prices-snapshot`; `prices` (volume) → `rdd:…`/`rdd-engine`. Particles deduped by `id`, capped at `limit`.
- **Layer-name correction:** `omega/__init__.py` defines **CRSM = Cross-Reality State Mesh** (CRDT/yjs-style state layer), not "Causal Risk Scenario Model" from the roadmap draft — roadmap Key Question resolved (canonical names live in code). Also note EIC = "Explainable Intelligence" (causal discovery ensemble + meta-learning insight generator).

### Contract test cases (`test_omega_qve.py`) — against LIVE schema
1. **Schema 1:1 / keys present:** `GET /qve/placement` → `200`, `application/json`; top-level keys exactly `{engine, n_particles, energy, schedule, wall_time_s, particles}`; every particle has exactly `{id, commodity, region, date, prediction, confidence, significance, shap_values, model_version, position, energy, color, glow, size}`.
2. **`n_particles == len(particles)`** and **`n_particles > 0`** with real DB present (skipif `DB_PATH` missing).
3. **Geometry typing:** each `position` is a list of **exactly 3 floats**; each `color` exactly **3 floats**; `glow`, `size`, `energy`, `confidence`, `significance` are floats.
4. **Determinism:** `?seed=42` called twice in the same session → byte-identical JSON (rng = `random.Random(seed)`; freeze `_now_ordinal` if run crosses midnight).
5. **Engine & schedule echo:** `engine == "simulated-annealing"`; `schedule.iterations == n_iter` requested.
6. **Empty-data path:** `?commodity=<nonexistent>` → `200`, `n_particles:0`, `warning` key present (NOT 500).
7. **Error path:** `?limit=abc` (non-int) → `500 {"error": str}`.
8. **Param bounds:** `?commodity=X&limit=N&n_iter=M&seed=S` → `schedule.iterations==M`, `n_particles<=N`, id prefixes filtered by commodity where applicable.
9. **Frontend renderability:** viz contract — every particle's `position`/`color` are finite 3-vectors and `glow`/`size` finite scalars (Three.js consumer, Visualization Eng.).

### Unit tests for `mandi_rdd/omega/qve.py` (pure logic, no DB)
- `build_qubo`: diagonal negative for significant particles; pair coupling sign tracks attraction/repulsion; deterministic for fixed input.
- `solve_placement_simulated_annealing`: returns `positions` len == n_particles; `energy` is float; same `seed` → identical output; `wall_time_s >= 0`; `schedule` echoes params.
- `_commodity_kernel`: symmetric; `1.0` for identical commodities; `0.0` for disjoint token sets.
- `build_particles_from_db`: id dedup (unique), source prefixes (`rdd:`/`fc:`/`px:`), capped at `limit` (uses real DB, skipif missing).

---

## 4. AAS integration tests (`test_omega_aas.py`) — [pending module land]

- **Signal detection:** distinct price-spike / rainfall-deficit / NDVI-anomaly / RDD-significance fixtures → each class fires the expected alert rule; neutral fixture does not.
- **Severity + dedup:** same signal twice within window → 1 alert, severity ordered (info<warn<critical).
- **Persistence:** `omega_alerts` uses INSERT OR REPLACE, runs twice idempotently (no dup rows, no DELETE+INSERT corruption).
- **API:** `GET /omega/alerts` + `GET /omega/alerts/active` return defined contract; `404` on unknown filters.

## 5. EIC integration tests (`test_omega_eic.py`) — [pending module land]

- **SHAP summary:** for ≥1 commodity, explanation arrays valid lengths, match classifier input dims.
- **Causal narrative:** non-empty text; references RDD point estimate; no HTML/None leakage.
- **API:** `GET /omega/explain/{commodity}` contract; `404` for unknown commodity.
- **Grounding:** reuses `ai/orchestrator` grounding — no ungrounded claims (mock the LLM).

## 6. `test_omega_core.py` — [pending core land]

- Layer registry lists all 7 layers (QVE/AAS/EIC/HRP/CRSM/SMCL/NIL) with wave+status (canonical names per `omega/__init__.py`).
- Schema apply twice → idempotent (`omega_alerts`, `omega_scenarios`, `omega_allocations`, `omega_explanations`, …).
- `GET /omega/status` returns layer health map.

---

## 7. Integration verification gate (full task)

Run after AAS/EIC land locally:
1. `python -m pytest mandi_rdd/tests/ -v` — **full suite green**, record baseline vs new test count (no regressions).
2. API boots, route count ≥ 39 (leader baseline) — `/qve/placement` present in `app.routes`.
3. **backend → API → dashboard:** call the omega function directly (unit), hit the HTTP endpoint (TestClient), confirm the Streamlit/Three.js page reflects the same output (E2E via `dashboard-integration.yml`, Playwright scroll of `/qve/placement` + omega pages).
4. Coverage: `--cov=mandi_rdd` — omega modules keep overall coverage from dropping (target: no new uncovered critical paths).
5. Consolidated status report → leader (task deliverable).

**Wave-2 gating:** steps for AAS/EIC only fire after those modules land; files use `importorskip` so partial merges stay green. QVE contract tests can run now (module + DB present).

---

## Definition of Done (this task)
- [x] `/qve/placement` contract reconciled vs live `qve.py` (schema above — no [TBD] remaining)
- [x] Layer-name correction captured (CRSM = Cross-Reality State Mesh)
- [x] Draft `test_omega_*.py` files with import-safe guards (qve 14 tests / core / aas / eic; all py_compile clean)
- [x] Update `tests/routes.py` with omega API route inventory (`OMEGA_API_PATHS`, kept out of Streamlit ROUTES)
- [x] Verify CI `paths:` include `mandi_rdd/omega/**`
- [x] Full suite green + no regressions (60 passed in 6.40s; screenshots E2E CI-gated) + dashboard E2E via dashboard-integration.yml
- [x] Consolidated status report delivered to leader