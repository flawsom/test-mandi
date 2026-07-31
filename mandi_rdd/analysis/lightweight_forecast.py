"""Lightweight forecast — pure numpy/pandas, no scipy.

Replaces the scipy-dependent parts of forecast.py for the Vercel serverless
bundle (which excludes scipy, scikit-learn, xgboost, openai due to the 500 MB
cap).  Provides the same forecast interface but with numpy-only OLS and
grid-search optimization.

All data-fetching logic is duplicated from forecast.py's train_forecast so
this module is self-contained and callers don't need to import forecast.py
(which would trigger the scipy import at _train_ensemble_with_damped_trend).
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ── numpy-only helpers ──


def _ols_slope_intercept(x: np.ndarray, y: np.ndarray) -> tuple[float, float, float]:
    """Return (slope, intercept, r_squared) using numpy least squares.

    Pure numpy, no scipy dependency.
    """
    n = len(x)
    if n < 2:
        return 0.0, float(y.mean()) if n > 0 else 0.0, 0.0
    A = np.column_stack([np.ones(n), x])
    try:
        coeffs, *_ = np.linalg.lstsq(A, y, rcond=None)
    except np.linalg.LinAlgError:  # pragma: no cover
        return 0.0, float(y.mean()), 0.0
    intercept = float(coeffs[0])
    slope = float(coeffs[1]) if len(coeffs) > 1 else 0.0
    y_pred = A @ coeffs
    ss_res = float(np.sum((y - y_pred) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 1e-12 else 0.0
    return slope, intercept, r2


def _grid_search_alpha(train: np.ndarray, alpha_vals: np.ndarray) -> float:
    """Brute-force grid search for best alpha (simple exponential smoothing).

    Replaces scipy.optimize.minimize_scalar used in _train_exponential_smoothing.
    """
    best_alpha = 0.5
    best_mse = np.inf
    for alpha in alpha_vals:
        level = train[0]
        fc = np.empty_like(train)
        fc[0] = level
        for t in range(1, len(train)):
            level = alpha * train[t] + (1 - alpha) * level
            fc[t] = level
        mse = np.mean((train - fc) ** 2)
        if mse < best_mse:
            best_mse = mse
            best_alpha = float(alpha)
    return best_alpha


# ── Public forecast functions ──


def seasonal_naive_forecast(
    monthly_df: pd.DataFrame,
    commodity: str,
    state: Optional[str] = None,
    periods: int = 6,
) -> dict:
    """Seasonal naive forecast — pure numpy, no scipy.

    Identical logic to forecast.py's _train_seasonal_naive.  Returns the same
    dict structure so callers can swap between the two transparently.
    """
    df = monthly_df.copy()
    n = len(df)

    # Train/test split: last 3 months held out
    train = df[:-3] if n > 6 else df
    test = df[-3:] if n > 6 else df.iloc[-2:]

    train["month"] = train["ds"].dt.month
    test["month"] = test["ds"].dt.month

    # Build seasonal lookup
    seasonal_map: dict[int, float] = {}
    for m in range(1, 13):
        subset = train[train["month"] == m]["y"]
        if len(subset) > 0:
            seasonal_map[m] = float(subset.median())
    fallback = float(train["y"].median()) if len(train) > 0 else 0.0

    # Test set forecasts
    test_forecasts = []
    for _, row in test.iterrows():
        m = row["month"]
        fc = seasonal_map.get(m, fallback)
        test_forecasts.append(fc)

    # Metrics
    metrics = {}
    if len(test_forecasts) > 0 and len(test) > 0:
        actuals = test["y"].values
        fc_arr = np.array(test_forecasts)
        mae = float(np.abs(actuals - fc_arr).mean())
        rmse = float(np.sqrt(((actuals - fc_arr) ** 2).mean()))
        nonzero = actuals > 1e-6
        mape = (
            float((np.abs((actuals[nonzero] - fc_arr[nonzero]) / actuals[nonzero]) * 100).mean())
            if nonzero.sum() > 0
            else None
        )
        metrics = {"mae": mae, "rmse": rmse, "mape": mape}

    # Future forecasts
    last_date = df["ds"].max()
    forecast_out = []
    for i in range(1, periods + 1):
        fc_date = last_date + pd.DateOffset(months=i)
        fc_month = fc_date.month
        fc_val = seasonal_map.get(fc_month, fallback)
        residuals = train[train["month"] == fc_month]["y"] - seasonal_map.get(fc_month, fallback)
        std_err = (
            float(residuals.std())
            if len(residuals) > 1
            else float(train["y"].std() * 0.3) if len(train) > 1
            else fc_val * 0.15
        )
        forecast_out.append({
            "date": str(fc_date.date()),
            "forecast": float(fc_val),
            "forecast_lower": float(fc_val - 1.96 * std_err),
            "forecast_upper": float(fc_val + 1.96 * std_err),
        })

    return {
        "commodity": commodity,
        "state": state or "All",
        "forecast": forecast_out,
        "metrics": metrics,
        "n_training_months": len(train),
        "n_test_months": len(test),
        "model": None,
        "method": "seasonal_naive",
        "seasonal_map": {str(k): round(v, 2) for k, v in seasonal_map.items()},
    }


def ensemble_damped_trend_forecast(
    monthly_df: pd.DataFrame,
    commodity: str,
    state: Optional[str] = None,
    periods: int = 6,
) -> dict:
    """Windowed seasonal naive + damped OLS trend — pure numpy, no scipy.

    Replaces forecast.py's _train_ensemble_with_damped_trend (which uses
    scipy.stats.linregress).  Same logic, same return dict structure.
    """
    df = monthly_df.copy()
    n = len(df)

    train = df[:-3] if n > 6 else df
    test = df[-3:] if n > 6 else df.iloc[-2:]

    train["month"] = train["ds"].dt.month
    test["month"] = test["ds"].dt.month

    WINDOW_MONTHS = 60
    window = min(WINDOW_MONTHS, len(train))
    train_windowed = train.tail(window).copy()
    train_y = train_windowed["y"].values
    n_win = len(train_y)

    # Seasonal map from windowed data
    seasonal_map: dict[int, float] = {}
    for m in range(1, 13):
        subset = train_windowed[train_windowed["month"] == m]["y"]
        if len(subset) > 0:
            seasonal_map[m] = float(subset.median())
    fallback = float(np.median(train_y)) if n_win > 0 else 0.0

    # OLS trend on windowed data (numpy, no scipy)
    x_win = np.arange(n_win, dtype=float)
    slope, intercept, trend_r2 = _ols_slope_intercept(x_win, train_y) if n_win > 2 else (0.0, float(train_y.mean()) if n_win > 0 else 0.0, 0.0)

    PHI = 0.85
    W_TREND = 0.50

    def _damped_adj(step: int) -> float:
        if abs(slope) < 1e-10:
            return 0.0
        cum_factor = PHI * (1 - PHI**step) / (1 - PHI)
        return slope * cum_factor

    # Test set forecasts
    test_forecasts = []
    for step, (_, row) in enumerate(test.iterrows(), start=1):
        m = row["month"]
        sv = seasonal_map.get(m, fallback)
        fc = sv + W_TREND * _damped_adj(step)
        test_forecasts.append(fc)

    # Metrics
    metrics = {}
    if len(test_forecasts) > 0 and len(test) > 0:
        actuals = test["y"].values
        fc_arr = np.array(test_forecasts)
        mae = float(np.abs(actuals - fc_arr).mean())
        rmse = float(np.sqrt(((actuals - fc_arr) ** 2).mean()))
        nonzero = actuals > 1e-6
        mape = (
            float((np.abs((actuals[nonzero] - fc_arr[nonzero]) / actuals[nonzero]) * 100).mean())
            if nonzero.sum() > 0
            else None
        )
        metrics = {"mae": mae, "rmse": rmse, "mape": mape}

    # Future forecasts
    last_date = df["ds"].max()
    forecast_out = []
    for i in range(1, periods + 1):
        fc_date = last_date + pd.DateOffset(months=i)
        fc_month = fc_date.month
        sv = seasonal_map.get(fc_month, fallback)
        adj = _damped_adj(i + 3)
        fc_val = sv + W_TREND * adj

        month_residuals = train_windowed[train_windowed["month"] == fc_month]["y"] - seasonal_map.get(fc_month, fallback)
        seasonal_std = (
            float(month_residuals.std())
            if len(month_residuals) > 1
            else float(np.std(train_y) * 0.3) if n_win > 1
            else fc_val * 0.15
        )
        trend_ste = abs(slope) * (i + 3) * 0.5
        combined_std = np.sqrt(seasonal_std**2 + trend_ste**2)

        forecast_out.append({
            "date": str(fc_date.date()),
            "forecast": float(fc_val),
            "forecast_lower": float(fc_val - 1.96 * combined_std),
            "forecast_upper": float(fc_val + 1.96 * combined_std),
        })

    return {
        "commodity": commodity,
        "state": state or "All",
        "forecast": forecast_out,
        "metrics": metrics,
        "n_training_months": len(train),
        "n_test_months": len(test),
        "model": None,
        "method": "ensemble_damped_trend",
        "window_size": window,
        "seasonal_map": {str(k): round(v, 2) for k, v in seasonal_map.items()},
        "trend_slope": round(slope, 2),
        "trend_intercept": round(intercept, 2),
        "trend_r2": round(trend_r2, 3),
        "damping_phi": PHI,
        "trend_weight": W_TREND,
    }


def exponential_smoothing_forecast(
    monthly_df: pd.DataFrame,
    commodity: str,
    state: Optional[str] = None,
    periods: int = 6,
) -> dict:
    """Exponential smoothing with trend — pure numpy, no scipy.

    Replaces forecast.py's _train_exponential_smoothing (which uses
    scipy.optimize.minimize_scalar).  Uses a grid search over alpha instead.
    """
    df = monthly_df.copy()
    y = df["y"].values
    n = len(y)

    train = y[:-3] if n > 6 else y
    test = y[-3:] if n > 6 else y[-2:]

    # Grid search for alpha
    alpha_vals = np.linspace(0.05, 0.95, 19)
    alpha_opt = _grid_search_alpha(train, alpha_vals)

    # Forecast with optimal alpha
    level = train[0]
    trend = (train[-1] - train[0]) / len(train) if len(train) > 1 else 0.0
    beta = 0.3
    all_forecasts: list[float] = []
    for t in range(len(train) + periods):
        if t < len(train):
            new_level = alpha_opt * train[t] + (1 - alpha_opt) * (level + trend)
            trend = beta * (new_level - level) + (1 - beta) * trend
            level = new_level
        else:
            all_forecasts.append(level + trend)

    train_forecast_vals = all_forecasts[:len(train)]
    future_forecasts = all_forecasts[len(train):]

    # Metrics
    metrics = {}
    if len(train_forecast_vals) >= len(test):
        test_fc = np.array(train_forecast_vals[-len(test):])
        mae = float(np.abs(test - test_fc).mean())
        rmse = float(np.sqrt(((test - test_fc) ** 2).mean()))
        mape = float((np.abs((test - test_fc) / test) * 100).mean())
        metrics = {"mae": mae, "rmse": rmse, "mape": mape}

    last_date = df["ds"].max()
    forecast_out = []
    train_arr = np.array(train_forecast_vals)
    train_y_arr = train[:len(train_forecast_vals)]
    std_err = float(np.std(train_y_arr - train_arr)) if len(train_arr) > 0 else float(np.std(y) * 0.1)
    for i, fc_val in enumerate(future_forecasts):
        forecast_date = last_date + pd.DateOffset(months=i + 1)
        forecast_out.append({
            "date": str(forecast_date.date()),
            "forecast": float(fc_val),
            "forecast_lower": float(fc_val - 1.96 * std_err),
            "forecast_upper": float(fc_val + 1.96 * std_err),
        })

    return {
        "commodity": commodity,
        "state": state or "All",
        "forecast": forecast_out,
        "metrics": metrics,
        "n_training_months": len(train),
        "n_test_months": len(test),
        "model": None,
        "method": "exponential_smoothing",
    }


def train_forecast_lightweight(
    conn,
    commodity: str,
    state: Optional[str] = None,
    district: Optional[str] = None,
    periods: int = 6,
    method: str = "auto",
) -> dict:
    """Lightweight forecast — no scipy, no prophet, no sklearn.

    Mirrors forecast.py's train_forecast() data-fetching and routing logic
    but only calls the pure-numpy estimators above.  Returns the same dict
    shape so callers can swap transparently.

    **Auto-select**: >= 36 months → ensemble with damped trend; else seasonal naive.
    """
    # ── Fetch data (same as forecast.py) ──
    query = """
        SELECT arrival_date, AVG(modal_price) as modal_price
        FROM prices
        WHERE commodity = ?
    """
    params = [commodity]
    if state:
        query += " AND state = ?"
        params.append(state)
    if district:
        query += " AND district = ?"
        params.append(district)
    query += " GROUP BY arrival_date ORDER BY arrival_date"

    df = conn.execute(query, params).fetchdf()
    if len(df) < 20:
        return {"error": f"Insufficient data: {len(df)} days", "forecast": [], "metrics": {}}

    df["arrival_date"] = pd.to_datetime(df["arrival_date"])
    df["year_month"] = df["arrival_date"].dt.to_period("M").astype(str)
    monthly = df.groupby("year_month").agg(
        modal_price=("modal_price", "mean"),
        n_days=("modal_price", "count"),
    ).reset_index().sort_values("year_month")

    prophet_df = monthly.rename(columns={"year_month": "ds", "modal_price": "y"})
    prophet_df["ds"] = pd.to_datetime(prophet_df["ds"])
    if len(prophet_df) < 6:
        return {"error": f"Insufficient monthly data: {len(prophet_df)} months", "forecast": [], "metrics": {}}

    # ── Route ──
    if method == "seasonal_naive":
        return seasonal_naive_forecast(prophet_df, commodity, state, periods)
    if method == "ensemble":
        return ensemble_damped_trend_forecast(prophet_df, commodity, state, periods)
    if method == "exp_smoothing":
        return exponential_smoothing_forecast(prophet_df, commodity, state, periods)

    # auto
    if len(prophet_df) >= 36:
        return ensemble_damped_trend_forecast(prophet_df, commodity, state, periods)
    return seasonal_naive_forecast(prophet_df, commodity, state, periods)


def get_forecast_summary_lightweight(conn, commodity: str) -> dict:
    """Convenience wrapper — same name pattern as forecast.py's get_forecast_summary."""
    return train_forecast_lightweight(conn, commodity=commodity)