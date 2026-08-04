"""Omega EIC — tests for mandi_rdd/omega/eic.py (Explainable Intelligence).

EIC runs causal discovery (Granger + partial-correlation skeleton) over price
data and synthesises meta-learned insights. This file checks the engine status,
causal-discovery output contract, and the insights contract.

Import-safe: skips if mandi_rdd.omega.eic is unavailable.
DB-dependent tests skip when mandi_iq.duckdb is absent.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

eic = pytest.importorskip("mandi_rdd.omega.eic")

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "mandi_iq.duckdb"
HAS_DB = DB_PATH.exists()


def test_eic_engine_status() -> None:
    status = eic.engine_status()
    assert isinstance(status, dict)
    assert status.get("engine") == "eic-causal-ensemble"


def test_eic_log_returns_shape() -> None:
    mat = np.random.default_rng(0).normal(0.1, 0.05, size=(40, 4))  # 40 days x 4 commodities
    r = eic._log_returns(mat)  # noqa: SLF001 — internal helper, deterministic
    assert r.shape == (mat.shape[0] - 1, mat.shape[1])  # np.diff over axis 0
    assert not np.isnan(r).any()


def test_eic_granger_matrix_square() -> None:
    series = np.random.default_rng(1).normal(0.1, 0.05, size=(40, 4))
    F, P = eic.granger_causality_matrix(series, max_lag=2)
    assert F.shape == (4, 4) and P.shape == (4, 4)


def test_eic_partial_correlation_skeleton_shape() -> None:
    returns = np.random.default_rng(2).normal(0.1, 0.05, size=(40, 4))
    R, P = eic.partial_correlation_skeleton(returns)
    assert R.shape == (4, 4) and P.shape == (4, 4)


@pytest.mark.skipif(not HAS_DB, reason="mandi_iq.duckdb not present")
def test_eic_causal_discovery_contract() -> None:
    import duckdb
    with duckdb.connect(str(DB_PATH), read_only=True) as conn:
        discovery = eic.causal_discovery(conn, limit=20, max_lag=2, p_threshold=0.10)
    assert isinstance(discovery, dict)
    for key in ("n_commodities", "n_edges", "edges", "commodities"):
        assert key in discovery, f"causal_discovery must include '{key}'"
    assert discovery["n_edges"] == len(discovery["edges"])
    assert all({"cause", "effect"} <= set(e.keys()) for e in discovery["edges"])


@pytest.mark.skipif(not HAS_DB, reason="mandi_iq.duckdb not present")
def test_eic_generate_insights_contract() -> None:
    import duckdb
    with duckdb.connect(str(DB_PATH), read_only=True) as conn:
        out = eic.generate_insights(conn, limit=20, max_lag=2, top_k=5, p_threshold=0.10)
    assert isinstance(out, dict)
    assert "insights" in out
    assert isinstance(out["insights"], list)
    assert out.get("engine") == "eic-causal-ensemble"