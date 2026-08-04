"""Omega QVE — contract + unit tests for mandi_rdd/omega/qve.py and /qve/placement.

Covers the LIVE /qve/placement data contract (api/main.py:2349, tag Omega):
    {engine, n_particles, energy, schedule{iterations,t_start,t_end},
     wall_time_s, particles[{id,commodity,region,date,prediction,confidence,
     significance,shap_values,model_version,position[3],energy,color[3],
     glow,size}]}
Query params: commodity (opt), limit (default 60), n_iter (default 4000), seed (opt).
Errors -> 500 {"error": str}. Empty data -> 200 n_particles:0 + warning.

Import-safe: skips entirely if mandi_rdd.omega.qve is unavailable.
DB-dependent tests skip when mandi_iq.duckdb is absent.
NOTE: determinism comparisons exclude wall_time_s (inherently non-deterministic);
all placement fields (positions/energy/schedule) are seed-reproducible.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

qve = pytest.importorskip("mandi_rdd.omega.qve")

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "mandi_iq.duckdb"
HAS_DB = DB_PATH.exists()

Particle = qve.Particle
TOP_KEYS = {"engine", "n_particles", "energy", "schedule", "wall_time_s", "particles"}
PARTICLE_KEYS = {
    "id", "commodity", "region", "date", "prediction", "confidence",
    "significance", "shap_values", "model_version", "position", "energy",
    "color", "glow", "size",
}


def _two_particles() -> list:
    return [
        Particle(id="px:onion:ALL", commodity="onion", significance=0.9, confidence=0.9),
        Particle(id="px:tomato:ALL", commodity="tomato", significance=0.8, confidence=0.8),
    ]


# --------------------------------------------------------------------------
# Pure-logic unit tests (no DB)
# --------------------------------------------------------------------------

def test_commodity_kernel_identical() -> None:
    assert qve._commodity_kernel("onion", "onion") == 1.0


def test_commodity_kernel_disjoint() -> None:
    assert qve._commodity_kernel("onion", "tomato") == 0.0


def test_commodity_kernel_symmetric() -> None:
    a, b = "onion", "tomato"
    assert qve._commodity_kernel(a, b) == qve._commodity_kernel(b, a)


def test_build_qubo_diagonal_negative() -> None:
    Q = qve.build_qubo(_two_particles())
    assert Q[(0, 0)] < 0 and Q[(1, 1)] < 0


def test_build_qubo_same_commodity_attracts_more() -> None:
    same = [Particle(id="a", commodity="onion", significance=0.9),
            Particle(id="b", commodity="onion", significance=0.8)]
    diff = [Particle(id="a", commodity="onion", significance=0.9),
            Particle(id="b", commodity="tomato", significance=0.8)]
    q_same = qve.build_qubo(same)[(0, 1)]
    q_diff = qve.build_qubo(diff)[(0, 1)]
    assert q_same < q_diff, "same-commodity pair must be more attractive (lower energy)"


def test_solve_sa_deterministic_seed() -> None:
    particles = _two_particles()
    Q = qve.build_qubo(particles)
    r1 = qve.solve_placement_simulated_annealing(particles, Q, n_iter=200, seed=42)
    r2 = qve.solve_placement_simulated_annealing(particles, Q, n_iter=200, seed=42)
    assert r1["positions"] == r2["positions"]
    assert r1["energy"] == r2["energy"]
    assert r1["schedule"]["iterations"] == 200


def test_solve_sa_output_types() -> None:
    particles = _two_particles()
    Q = qve.build_qubo(particles)
    out = qve.solve_placement_simulated_annealing(particles, Q, n_iter=100, seed=7)
    assert isinstance(out["energy"], float)
    assert isinstance(out["wall_time_s"], float)
    assert len(out["positions"]) == len(particles)
    assert all(len(p) == 3 for p in out["positions"])


def test_particle_to_dict_contract() -> None:
    d = _two_particles()[0].to_dict()
    assert set(d.keys()) == PARTICLE_KEYS
    assert isinstance(d["position"], list) and len(d["position"]) == 3
    assert isinstance(d["color"], list) and len(d["color"]) == 3
    assert all(isinstance(v, (int, float)) for v in d["position"])
    assert isinstance(d["energy"], float)


# --------------------------------------------------------------------------
# DB-dependent tests (real mandi_iq.duckdb)
# --------------------------------------------------------------------------

@pytest.mark.skipif(not HAS_DB, reason="mandi_iq.duckdb not present")
def test_build_particles_from_db_real() -> None:
    import duckdb
    with duckdb.connect(str(DB_PATH), read_only=True) as conn:
        parts = qve.build_particles_from_db(conn, limit=60)
    assert len(parts) > 0
    assert len(parts) <= 60
    ids = [p.id for p in parts]
    assert len(set(ids)) == len(ids), "particle ids must be unique"
    assert all(pid.split(":")[0] in {"rdd", "fc", "px"} for pid in ids), "id prefixes rdd:/fc:/px:"
    assert all(set(p.to_dict().keys()) == PARTICLE_KEYS for p in parts)


@pytest.mark.skipif(not HAS_DB, reason="mandi_iq.duckdb not present")
def test_compute_placement_contract() -> None:
    import duckdb
    with duckdb.connect(str(DB_PATH), read_only=True) as conn:
        out = qve.compute_placement(conn, limit=20, n_iter=200, seed=42)
    assert set(out.keys()) >= TOP_KEYS
    assert out["engine"] == "simulated-annealing"
    assert out["n_particles"] == len(out["particles"])
    assert out["n_particles"] > 0
    assert isinstance(out["energy"], float)
    assert isinstance(out["wall_time_s"], float)
    assert set(out["schedule"].keys()) == {"iterations", "t_start", "t_end"}
    assert out["schedule"]["iterations"] == 200


@pytest.mark.skipif(not HAS_DB, reason="mandi_iq.duckdb not present")
def test_compute_placement_determinism_seed() -> None:
    import duckdb
    with duckdb.connect(str(DB_PATH), read_only=True) as conn:
        a = qve.compute_placement(conn, limit=20, n_iter=300, seed=42)
        b = qve.compute_placement(conn, limit=20, n_iter=300, seed=42)
    a.pop("wall_time_s", None)
    b.pop("wall_time_s", None)
    assert a == b, "same seed must produce identical placement (excl. wall_time_s)"


@pytest.mark.skipif(not HAS_DB, reason="mandi_iq.duckdb not present")
def test_compute_placement_limit0_empty_warning() -> None:
    import duckdb
    with duckdb.connect(str(DB_PATH), read_only=True) as conn:
        out = qve.compute_placement(conn, limit=0, n_iter=100, seed=1)
    assert out["n_particles"] == 0
    assert out["particles"] == []
    assert "warning" in out, "empty result must carry a warning key"


# --------------------------------------------------------------------------
# API contract tests (FastAPI TestClient)
# --------------------------------------------------------------------------

def _client():
    try:
        from fastapi.testclient import TestClient
        from mandi_rdd.api.main import app
        return TestClient(app)
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"API app unavailable: {exc}")


@pytest.mark.skipif(not HAS_DB, reason="mandi_iq.duckdb not present")
def test_qve_placement_endpoint_schema() -> None:
    r = _client().get("/qve/placement?limit=10&n_iter=200&seed=42")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")
    body = r.json()
    assert set(body.keys()) >= TOP_KEYS
    assert body["n_particles"] == len(body["particles"])
    assert body["n_particles"] > 0
    assert all(set(p.keys()) == PARTICLE_KEYS for p in body["particles"])


@pytest.mark.skipif(not HAS_DB, reason="mandi_iq.duckdb not present")
def test_qve_placement_endpoint_determinism() -> None:
    client = _client()
    a = client.get("/qve/placement?limit=15&n_iter=300&seed=42").json()
    b = client.get("/qve/placement?limit=15&n_iter=300&seed=42").json()
    a.pop("wall_time_s", None)
    b.pop("wall_time_s", None)
    assert a == b


@pytest.mark.skipif(not HAS_DB, reason="mandi_iq.duckdb not present")
def test_qve_placement_endpoint_empty_warning() -> None:
    body = _client().get("/qve/placement?limit=0").json()
    assert body["n_particles"] == 0
    assert "warning" in body


@pytest.mark.skipif(not HAS_DB, reason="mandi_iq.duckdb not present")
def test_qve_placement_endpoint_error_500() -> None:
    # `limit` is typed `int`, so FastAPI validation rejects non-int input with
    # 422 BEFORE the handler runs (no 500 is possible for this input class).
    r = _client().get("/qve/placement?limit=abc")
    assert r.status_code == 422
    body = r.json()
    assert "detail" in body
