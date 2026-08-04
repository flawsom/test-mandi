"""Omega Core — contract tests for mandi_rdd/omega/core.py.

OmegaCore orchestrates QVE -> AAS -> EIC -> CRSM. This file checks the layer
registry (module_status) and the pipeline output contract.

Import-safe: skips if mandi_rdd.omega.core is unavailable.
Pipeline/snapshot tests skip when mandi_iq.duckdb is absent.
"""
from __future__ import annotations

from pathlib import Path

import pytest

core = pytest.importorskip("mandi_rdd.omega.core")

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "mandi_iq.duckdb"
HAS_DB = DB_PATH.exists()

EXPECTED_LAYERS = {"qve", "aas", "eic", "crsm"}


def _make(conn=None):
    return core.OmegaCore(conn=conn)


def test_core_module_status_contract() -> None:
    status = _make().module_status()
    assert isinstance(status, dict)
    assert status.get("protocol") == "OMEGA"
    assert status.get("dwave_emulated") is True
    modules = status.get("modules", {})
    assert isinstance(modules, dict)
    assert EXPECTED_LAYERS.issubset(set(modules.keys())), "layer registry must list qve/aas/eic/crsm"


def test_core_pipeline_status_summary() -> None:
    summary = getattr(core, "pipeline_status_summary", None)
    if summary is None:
        pytest.skip("core.pipeline_status_summary not present")
    out = summary({})
    assert isinstance(out, dict)


@pytest.mark.skipif(not HAS_DB, reason="mandi_iq.duckdb not present")
def test_core_run_pipeline_contract() -> None:
    import duckdb
    with duckdb.connect(str(DB_PATH), read_only=True) as conn:
        result = _make(conn=conn).run_pipeline(
            limit=10, n_iter=100, n_agents=40, max_lag=2, top_k=5, seed=42,
        )
    assert isinstance(result, dict)
    assert "stages" in result, "run_pipeline must return a 'stages' dict"
    stages = result["stages"]
    for stage in ("qve", "eic"):
        assert stage in stages, f"pipeline must emit '{stage}' stage"


@pytest.mark.skipif(not HAS_DB, reason="mandi_iq.duckdb not present")
def test_core_snapshot_contract() -> None:
    import duckdb
    with duckdb.connect(str(DB_PATH), read_only=True) as conn:
        result = _make(conn=conn).run_pipeline(
            limit=8, n_iter=80, n_agents=30, max_lag=2, top_k=4, seed=1,
        )
        snap = _make(conn=conn).snapshot(result.get("stages", result))
    assert isinstance(snap, dict)