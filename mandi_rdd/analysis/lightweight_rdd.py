"""Lightweight RDD — pure numpy, no scipy.

Replaces the scipy-guarded run_rdd() in rdd_engine.py for the Vercel
serverless bundle (which excludes scipy, scikit-learn, xgboost, openai
due to the 500 MB cap).  Provides the same interface but with p_value
set to None instead of blocking entirely.

The actual RDD computation (local_linear_rdd, bandwidth_sensitivity,
placebo_test, mccrary_density_test, covariate_balance) is already pure
numpy — the only scipy dependency is stats.t.cdf() for the p-value.
This module calls those same functions directly, skipping the scipy
availability guard in run_rdd().
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def run_rdd_lightweight(
    conn,
    commodity: str = "Onion",
    state: Optional[str] = None,
    bandwidths: list[float] = None,
    cutoff: float = -19.0,
) -> dict:
    """Full RDD pipeline — same as rdd_engine.run_rdd but no scipy guard.

    Args:
        conn: DuckDB connection
        commodity: Commodity to analyze
        state: Optional state filter
        bandwidths: Bandwidths to test for sensitivity
        cutoff: RDD cutoff (IMD's deficient rainfall threshold = -19%)

    Returns:
        Dict with main RDD result + robustness checks, same shape as
        rdd_engine.run_rdd() but with p_value=None when scipy is absent.
    """
    # Import the pure-numpy functions directly from rdd_engine.
    # These don't import scipy at module level — only local_linear_rdd
    # touches scipy inside the function body, and it's guarded there.
    from mandi_rdd.analysis.rdd_engine import (
        local_linear_rdd,
        bandwidth_sensitivity,
        placebo_test,
        mccrary_density_test,
        covariate_balance,
    )
    from mandi_rdd.storage.duckdb_store import get_monthly_avg_prices
    from mandi_rdd.ingestion.fetch_rainfall import load_district_subdivision_map

    if bandwidths is None:
        bandwidths = [15, 20, 25, 30]

    # 1. Get monthly average prices for this commodity
    if state is None:
        price_df = conn.execute(
            """
            SELECT
                EXTRACT(YEAR FROM arrival_date)  AS year,
                EXTRACT(MONTH FROM arrival_date) AS month,
                AVG(modal_price)                 AS avg_modal_price,
                COUNT(*)                        AS n_observations
            FROM prices
            WHERE commodity = ? AND modal_price IS NOT NULL
            GROUP BY 1, 2
            HAVING COUNT(*) >= 1
            ORDER BY 1, 2
            """,
            [commodity],
        ).fetchdf()
        price_df["state"] = "All-India"
        price_df["district"] = "All-India"
    else:
        price_df = get_monthly_avg_prices(conn, commodity=commodity, state=state)

    if len(price_df) < 1:
        return {
            "commodity": commodity,
            "effect": None,
            "std_error": None,
            "p_value": None,
            "bandwidth_sensitivity": None,
            "error": f"Insufficient price data: {len(price_df)} monthly observations",
        }

    # 2. Load district → sub-division mapping
    district_map = load_district_subdivision_map()

    # 3. Map each district to its sub-division
    if state is not None:
        def _map_subdiv(r):
            return district_map.get((r["state"], r["district"]), None)
        price_df["sub_division"] = price_df.apply(_map_subdiv, axis=1)
        price_df = price_df.dropna(subset=["sub_division"])

    if len(price_df) < 1:
        return {
            "commodity": commodity,
            "effect": None,
            "bandwidth_sensitivity": None,
            "error": f"Insufficient district-subdivision mappings: {len(price_df)} rows",
        }

    # 4. Load rainfall
    rainfall_df = conn.execute(
        """
        SELECT sub_division, month,
               rainfall_mm, normal_mm, departure_pct
        FROM rainfall
        """
    ).fetchdf()

    # Normalise departure scale defensively (ratio -> percentage) if needed.
    _maxabs = float(rainfall_df["departure_pct"].abs().max())
    if _maxabs < 1.0:
        rainfall_df["departure_pct"] = rainfall_df["departure_pct"] * 100.0

    if state is None:
        # Each national price (year-month) row is joined to EVERY daily
        # rainfall departure observation for that month -> a panel with real
        # spread in the running variable around the 0% deficiency cutoff.
        price_df = price_df.merge(
            rainfall_df[["month", "sub_division", "departure_pct",
                         "rainfall_mm", "normal_mm"]],
            on="month", how="left",
        )

    if len(rainfall_df) < 5:
        return {
            "commodity": commodity,
            "effect": None,
            "bandwidth_sensitivity": None,
            "error": f"Insufficient rainfall data: {len(rainfall_df)} records",
        }

    # Merge on sub_division, month (climatological rainfall signal)
    if state is None:
        # National path already carries sub_division + departure_pct from above
        merged = price_df
    else:
        merged = price_df.merge(
            rainfall_df,
            on=["sub_division", "month"],
            how="inner",
        )

    if len(merged) < 5:
        return {
            "commodity": commodity,
            "effect": None,
            "bandwidth_sensitivity": None,
            "error": f"Insufficient matched data: {len(merged)} observations",
        }

    # 5. Drop NaN departure values
    merged = merged.dropna(subset=["departure_pct", "avg_modal_price"])

    if len(merged) < 5:
        return {
            "commodity": commodity,
            "effect": None,
            "bandwidth_sensitivity": None,
            "error": "Too few non-null observations after merge",
        }

    x = merged["departure_pct"].values
    y = merged["avg_modal_price"].values

    # 6. Run main RDD
    main_result = local_linear_rdd(x, y, cutoff, bandwidth=20)

    # 7. Bandwidth sensitivity
    sensitivity = bandwidth_sensitivity(x, y, cutoff, bandwidths)

    # 8. Placebo tests
    placebos = placebo_test(x, y, cutoff)

    # 9. McCrary density test
    density = mccrary_density_test(x, cutoff)

    # 10. Covariate balance
    covariates = {"n_observations": merged["n_observations"].values}
    if "avg_modal_price" in merged.columns:
        covariates["log_n_obs"] = np.log(merged["n_observations"].values + 1)
    balance = covariate_balance(x, covariates, cutoff)

    # 11. Compile full result
    effect = main_result.get("effect")
    p_value = main_result.get("p_value")

    result = {
        "commodity": commodity,
        "state": state or "All",
        "effect": effect,
        "std_error": main_result.get("std_error"),
        "p_value": p_value,
        "t_stat": main_result.get("t_stat"),
        "n_left": main_result.get("n_left"),
        "n_right": main_result.get("n_right"),
        "n_total": main_result.get("n_total"),
        "bandwidth": main_result.get("bandwidth"),
        "bandwidth_absolute": main_result.get("bandwidth_absolute"),
        "gamma_0": main_result.get("gamma_0"),
        "beta_0": main_result.get("beta_0"),
        "x_range": main_result.get("x_range"),
        "n_observations": len(merged),
        "n_districts": merged["district"].nunique(),
        "n_months": merged["year"].nunique() * 12,
        "bandwidth_sensitivity": sensitivity,
        "placebo_tests": placebos,
        "density_test": density,
        "covariate_balance": balance,
        "data_sample": merged.head(100).to_dict("records"),
        "error": main_result.get("error"),
        "engine": "lightweight",
    }

    # Interpret the result (p_value may be None without scipy)
    if effect is not None and p_value is not None:
        if p_value < 0.05:
            result["interpretation"] = (
                f"Statistically significant discontinuity at cutoff (p={p_value:.4f}). "
                f"Price changes by ₹{effect:.2f} ({(effect / (result.get('gamma_0', 1) or 1)) * 100:.1f}%) "
                f"at the -19% rainfall deficiency threshold."
            )
        elif p_value < 0.1:
            result["interpretation"] = (
                f"Marginally significant discontinuity (p={p_value:.4f}). "
                f"Effect of ₹{effect:.2f} at cutoff — suggestive but not definitive."
            )
        else:
            result["interpretation"] = (
                f"No statistically significant discontinuity detected (p={p_value:.4f}). "
                f"Estimated effect: ₹{effect:.2f} at cutoff. "
                "Rainfall deficiency alone may not drive price jumps for this commodity."
            )
    elif effect is not None:
        result["interpretation"] = (
            f"Estimated discontinuity effect: ₹{effect:.2f} at the -19% rainfall "
            f"deficiency threshold. P-value not available (scipy not bundled on "
            f"this deployment — use the Northflank API for full significance testing)."
        )

    return result