"""Omega AAS — tests for mandi_rdd/omega/aas.py (Adaptive Alert System).

The AAS runs a BDI agent swarm over serialised QVE particles to emit risk alerts.
This file tests the swarm contract, determinism, empty-input handling, and the
severity label mapping.

Import-safe: skips if mandi_rdd.omega.aas is unavailable.
"""
from __future__ import annotations

import pytest

aas = pytest.importorskip("mandi_rdd.omega.aas")

SEVERITY_ORDER = ("low", "medium", "high", "critical")


def _fake_particle(significance=0.9, commodity="onion") -> dict:
    return {
        "id": f"px:{commodity}:ALL",
        "commodity": commodity,
        "region": "ALL",
        "date": "",
        "prediction": 10.0,
        "confidence": 0.9,
        "significance": significance,
        "model_version": "prices-snapshot",
        "position": [0.1, 0.2, 0.3],
        "energy": 0.5,
    }


def test_aas_engine_status() -> None:
    status = aas.engine_status()
    assert isinstance(status, dict)
    assert status.get("engine") == "aas-bdi-swarm"
    assert "roles" in status


def test_aas_severity_label_monotonic() -> None:
    sev = getattr(aas, "_severity_label", None)
    if sev is None:
        pytest.skip("aas._severity_label not present")
    labels = [sev(s) for s in (0.1, 0.3, 0.6, 0.9)]
    assert all(l in SEVERITY_ORDER for l in labels)
    pos = [SEVERITY_ORDER.index(l) for l in labels]
    assert pos == sorted(pos), "severity label must be non-decreasing with severity"


def test_aas_empty_swarm() -> None:
    out = aas.run_agent_swarm([], n_agents=50, seed=1)
    assert out.get("engine") == "aas-bdi-swarm"
    assert out.get("n_alerts", 0) == 0
    assert out.get("alerts", []) == []
    roles = out.get("roles", {})
    assert all(count == 0 for count in roles.values())


def test_aas_swarm_structure() -> None:
    out = aas.run_agent_swarm([_fake_particle()], n_agents=50, seed=7)
    assert isinstance(out, dict)
    assert out.get("engine") == "aas-bdi-swarm"
    assert isinstance(out.get("roles"), dict)
    assert isinstance(out.get("alerts"), list)
    assert out.get("n_agents", 50) <= 10000, "n_agents must be clamped"


def test_aas_determinism_seed() -> None:
    particles = [_fake_particle(significance=s) for s in (0.9, 0.8, 0.99, 0.7)]
    a = aas.run_agent_swarm(particles, n_agents=100, seed=42)
    b = aas.run_agent_swarm(particles, n_agents=100, seed=42)
    a.pop("wall_time_s", None)
    b.pop("wall_time_s", None)
    assert a == b, "same seed must produce identical swarm output (excl. wall_time_s)"