"""End-to-end HTTP tests for the OMEGA (QVE / AAS / EIC / Core) endpoints.

Uses a seeded in-memory DuckDB injected via ``get_connection`` monkeypatching,
so no on-disk data is required.
"""

from __future__ import annotations

import pytest


def _client():
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    import mandi_rdd.api.main as m

    return TestClient(m.app), m


def _patch_conn(monkeypatch):
    from test_omega_helpers import seed_omega_db

    import mandi_rdd.api.main as m

    monkeypatch.setattr(m, "get_connection", lambda: seed_omega_db())


def test_qve_placement_endpoint_ok(monkeypatch):
    client, _ = _client()
    _patch_conn(monkeypatch)
    r = client.get("/qve/placement", params={"limit": 10, "n_iter": 400, "seed": 42})
    assert r.status_code == 200
    body = r.json()
    assert body["engine"] == "simulated-annealing"
    assert body["n_particles"] > 0
    assert len(body["particles"]) == body["n_particles"]


def test_qve_placement_bad_type_returns_422(monkeypatch):
    client, _ = _client()
    _patch_conn(monkeypatch)
    r = client.get("/qve/placement?limit=abc")
    assert r.status_code == 422


def test_omega_status_endpoint(monkeypatch):
    client, _ = _client()
    r = client.get("/omega/status")
    assert r.status_code == 200
    body = r.json()
    assert body["protocol"] == "OMEGA"
    for mod in ("qve", "aas", "eic", "crsm"):
        assert body["modules"][mod]["available"] is True


def test_omega_pipeline_endpoint(monkeypatch):
    client, _ = _client()
    _patch_conn(monkeypatch)
    r = client.post(
        "/omega/pipeline",
        params={"limit": 8, "n_iter": 400, "n_agents": 300, "max_lag": 1, "top_k": 5},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["degraded"] is False
    assert body["stages"]["qve"]["n_particles"] > 0
    assert body["stages"]["eic"]["n_insights"] >= 0 or "insights" in body["stages"]["eic"]
    assert "state_mesh" in body


def test_aas_endpoints(monkeypatch):
    client, _ = _client()
    _patch_conn(monkeypatch)
    r1 = client.get("/aas/status")
    assert r1.status_code == 200
    assert r1.json()["engine"] == "aas-bdi-swarm"

    r2 = client.post("/aas/run", params={"n_agents": 300, "seed": 1})
    assert r2.status_code == 200
    assert r2.json()["n_agents"] == 300


def test_eic_endpoints(monkeypatch):
    client, _ = _client()
    r1 = client.get("/eic/status")
    assert r1.status_code == 200
    assert r1.json()["engine"] == "eic-causal-ensemble"

    _patch_conn(monkeypatch)
    r2 = client.get("/eic/insights", params={"max_lag": 1, "top_k": 5})
    assert r2.status_code == 200
    assert "insights" in r2.json()
    assert "market_drivers" in r2.json()