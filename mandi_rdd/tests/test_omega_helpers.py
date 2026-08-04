"""Shared fixtures/seeding helpers for OMEGA (QVE / AAS / EIC / Core) tests."""

from __future__ import annotations

import duckdb
import numpy as np


def seed_omega_db() -> duckdb.DuckDBPyConnection:
    """In-memory DuckDB seeded with price/rdd/forecast data for engine tests."""
    from mandi_rdd.storage.duckdb_store import init_schema

    conn = duckdb.connect(":memory:")
    init_schema(conn)

    # Eight-month price series per commodity with a known causal structure:
    #   Rice(t) depends on Wheat(t-1); Potato is an independent random walk.
    months = [
        "2025-09", "2025-10", "2025-11", "2025-12",
        "2026-01", "2026-02", "2026-03", "2026-04",
    ]
    rng = np.random.default_rng(7)
    n = len(months)

    wheat = np.zeros(n)
    wheat[0] = 2000.0
    for i in range(1, n):
        wheat[i] = wheat[i - 1] + rng.normal(0, 25)

    rice = np.zeros(n)
    rice[0] = 3000.0
    for i in range(1, n):
        rice[i] = 3000.0 + 0.8 * (wheat[i - 1] - 2000.0) + rng.normal(0, 15)

    potato = 1400.0 + rng.normal(0, 30, size=n)

    for commodity, series in (("Wheat", wheat), ("Rice", rice), ("Potato", potato)):
        for i, m in enumerate(months):
            year, mon = m.split("-")
            conn.execute(
                "INSERT INTO prices (state, district, market, commodity, arrival_date, modal_price) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                ["KA", "D1", f"M{i}", commodity, f"{year}-{mon}-15", float(series[i])],
            )

    conn.execute(
        "INSERT INTO rdd_results (commodity, computed_at, effect, std_error, p_value) VALUES "
        "('Wheat', '2026-06-01', 14.0, 3.0, 0.008), "
        "('Rice', '2026-06-01', -6.5, 2.7, 0.03), "
        "('Potato', '2026-06-01', 2.2, 1.9, 0.41)"
    )
    conn.execute(
        "INSERT INTO forecast_metrics (commodity, computed_at, model, test_mape, test_mae, test_rmse) VALUES "
        "('Wheat', '2026-06-01', 'prophet', 6.2, 9, 11), "
        "('Rice', '2026-06-01', 'prophet', 9.4, 12, 15), "
        "('Potato', '2026-06-01', 'prophet', 14.1, 16, 19)"
    )
    return conn