# Omega Integration Test Plan — QVE / AAS / EIC + `/qve/placement` data contract

**Owner:** Tech PM `019fcc12-7882-79c0-9912-92a1a55105cd` · Task `019fcc12-ee5f-7662-b231-0e0062924d08`
**Status:** DRAFT — wave-2 modules (AAS/EIC) not yet landed; QVE `/qve/placement` live (leader-reported: 39 routes, real particles).
**Rule:** do not execute wave-2 tests until AAS/EIC land in this checkout. Drafting only now.

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
- **DB-dependent tests:** `@pytest.mark.skipif(not DB_PATH.exists(), ...)`.
- **API tests:** FastAPI `TestClient` against the app from `mandi_rdd.api.main`.
- **Route contract checks:** extend `tests/routes.py` inventory with the new omega routes.

### Proposed new omega test files
| File | Covers |
|---|---|
| `mandi_rdd/tests/test_omega_core.py` | layer registry, idempotent schema (INSERT OR REPLACE), `/omega/status` |
| `mandi_rdd/tests/test_omega_qve.py` | `omega/qve` SA optimizer **+ `/qve/placement` data contract** |
| `mandi_rdd/tests/test_omega_aas.py` | alert signals, severity, dedup, persistence (`omega_alerts`) |
| `mandi_rdd/tests/test_omega_eic.py` | SHAP summary, causal narrative, `/omega/explain/{commodity}` |

---

## 2. CI workflows (identified)

| Workflow | What it runs | Relevance to omega |
|---|---|---|
| `.github/workflows/ci.yml` | full `pytest mandi_rdd/tests/` + coverage + ruff (Py 3.10/3.11) | **Primary gate.** Omega tests must be import-safe (skip when module absent) so a partial merge stays green. |
| `.github/workflows/dashboard-integration.yml` | API health check + Streamlit smoke test | Extended to hit `/omega/status` + `/qve/placement`. |
| `.github/workflows/drift-detector.yml` | DuckDB store drift checks | Extended to verify `omega_alerts`, `omega_qve_runs` schema idempotency. |

---

## 3. Integration Test Plan — Core / QVE / AAS / EIC

### 3.1 `/qve/placement` Data Contract (Priority #1)

Leader confirmed `/qve/placement` route is live and returning particle data for the 3D visualization.

- **Contract schema:**
  ```json
  {
    "status": "ok",
    "count": 12,
    "particles": [
      {
        "id": "str",
        "commodity": "str",
        "x": "float",
        "y": "float",
        "z": "float",
        "energy": "float",
        "risk_weight": "float"
      }
    ],
    "timestamp": "ISO-8601 string"
  }
  ```
- **Assertions:**
  1. `HTTP 200` on `GET /qve/placement` (and query params like `?market=Dharmapuri&top_n=10`).
  2. JSON body contains `status == "ok"` and `particles` list.
  3. Each particle has non-null 3D coordinates `(x, y, z)` within expected bounds (e.g., normalised `[-100, 100]`).
  4. `energy` and `risk_weight` are numeric and non-negative.
  5. Response time `< 500ms` (no blocking simulated-annealing loops on main thread).

### 3.2 AAS Integration Contract (when landed)

- **Assertions:**
  1. `GET /omega/alerts` returns `200` + list of alerts.
  2. Price spike trigger creates `omega_alerts` row with `severity in ('low', 'medium', 'high', 'critical')`.
  3. Deduplication: repeating same signal within 1 hour does NOT create duplicate row.
  4. Graceful handling when NDVI data missing (Sentinel Hub ~48 district gap) → alert generated with `source_quality: degraded`, no HTTP 500.

### 3.3 EIC Integration Contract (when landed)

- **Assertions:**
  1. `GET /omega/explain/{commodity}` returns `200` + SHAP summary values + causal text explanation.
  2. SHAP features match `mandi_rdd/analysis/classifier.py` feature set.
  3. Causal narrative non-empty and references RDD point estimate / significance level.

### 3.4 Integration Chain (E2E Verification Flow)

```
Backend DuckDB Store  ──>  omega/core Schema (INSERT OR REPLACE)
                                  │
                 ┌────────────────┴────────────────┐
                 ▼                                 ▼
          omega/aas (Alerts)               omega/qve (Simulated Annealing)
                 │                                 │
                 ▼                                 ▼
          `/omega/alerts`                   `/qve/placement` (3D particles)
                 │                                 │
                 └────────────────┬────────────────┘
                                  ▼
                 Visualization / Streamlit Page
```

---

## 4. Execution Checklist (for when code lands)

- [ ] 1. Draft `mandi_rdd/tests/test_omega_qve.py` with `/qve/placement` contract test using `pytest.importorskip("mandi_rdd.omega.qve")`.
- [ ] 2. Extend `mandi_rdd/tests/routes.py` inventory with `/qve/placement`, `/omega/status`, `/omega/alerts`, `/omega/explain/{commodity}`.
- [ ] 3. Run full existing test suite (`pytest mandi_rdd/tests/`) to verify zero regressions.
- [ ] 4. Once Core Platform Engineer lands AAS/EIC, write `test_omega_aas.py` and `test_omega_eic.py`.
- [ ] 5. Run full integration suite end-to-end and report coverage to leader.
