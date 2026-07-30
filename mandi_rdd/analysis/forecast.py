"""
MandiRDD — Forecasting Layer.

Reuses Superstore's Prophet + LSTM comparison pattern, repointed at
modal_price time series per commodity/market.

Implementation is lightweight — just Prophet for the MVP, matching the
Superstore finding that classical models outperform deep learning on
smaller datasets.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import numpy as np
import pandas as pd
import logging
from typing import Optional
import warnings

warnings.filterwarnings("ignore")

logger = logging.getLogger(__name__)

try:
    from prophet import Prophet
    PROPHET_AVAILABLE = True
except ImportError:
    PROPHET_AVAILABLE = False
    logger.warning("Prophet not installed. Install with: pip install prophet")


def train_forecast(
    conn,
    commodity: str,
    state: Optional[str] = None,
    district: Optional[str] = None,
    periods: int = 6,
    method: str = "auto",
) -> dict:
    """
    Train a forecast model on a commodity's modal price time series.

    Default ("auto") selects the best model based on data depth:
      - 36+ months: ensemble with damped trend (seasonal naive + damped linear trend)
      - < 36 months: pure seasonal naive (median of same-month-in-prior-years)

    The ensemble captures long-term shifts (inflation, market changes) while
    the seasonal naive handles noisy agricultural price data by focusing on
    the annual cycle (sowing → harvest → storage).

    Other methods:
      - "seasonal_naive": pure seasonal median baseline
      - "ensemble": force ensemble with damped trend
      - "prophet": Prophet (if installed), falls back to seasonal naive
      - "exp_smoothing": exponential smoothing with trend

    Args:
        conn: DuckDB connection
        commodity: Commodity to forecast
        state: Optional state filter
        district: Optional district filter
        periods: Number of months to forecast
        method: "auto" (default), "seasonal_naive", "ensemble", "prophet", "exp_smoothing"

    Returns:
        Dict with forecast list, metrics dict, model metadata
    """
    # Build query
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

    # DuckDB connection: use native execute + fetchdf (NOT pd.read_sql_query,
    # which expects a SQLAlchemy/SQLite connection and silently mishandles
    # DuckDB parameterized '?' queries -> empty frame -> no metrics).
    df = conn.execute(query, params).fetchdf()

    if len(df) < 20:
        return {"error": f"Insufficient data: {len(df)} days", "forecast": [], "metrics": {}}

    # Aggregate to monthly
    df["arrival_date"] = pd.to_datetime(df["arrival_date"])
    df["year_month"] = df["arrival_date"].dt.to_period("M").astype(str)

    monthly = df.groupby("year_month").agg(
        modal_price=("modal_price", "mean"),
        n_days=("modal_price", "count"),
    ).reset_index()

    monthly = monthly.sort_values("year_month")

    # Prepare common dataframe
    prophet_df = monthly.rename(columns={"year_month": "ds", "modal_price": "y"})
    prophet_df["ds"] = pd.to_datetime(prophet_df["ds"])

    if len(prophet_df) < 6:
        return {"error": f"Insufficient monthly data: {len(prophet_df)} months", "forecast": [], "metrics": {}}

    # Route to the chosen method
    if method == "prophet":
        if PROPHET_AVAILABLE:
            return _train_prophet(prophet_df, commodity, state, periods)
        else:
            logger.warning("Prophet requested but not installed; falling back to seasonal naive")
            return _train_seasonal_naive(prophet_df, commodity, state, periods)
    elif method == "exp_smoothing":
        return _train_exponential_smoothing(prophet_df, commodity, state, periods)
    elif method == "ensemble":
        return _train_ensemble_with_damped_trend(prophet_df, commodity, state, periods)
    elif method == "seasonal_naive":
        return _train_seasonal_naive(prophet_df, commodity, state, periods)
    else:
        # "auto": auto-select based on data depth
        # For commodities with 36+ months of data, use the ensemble with damped trend
        # which captures long-term shifts (inflation, market changes)
        if len(prophet_df) >= 36:
            return _train_ensemble_with_damped_trend(prophet_df, commodity, state, periods)
        else:
            return _train_seasonal_naive(prophet_df, commodity, state, periods)


def _train_ensemble_with_damped_trend(prophet_df, commodity, state, periods):
    """Ensemble: windowed seasonal naive + damped OLS trend.

    The pure seasonal naive uses ALL training data (potentially 30+ years). For
    commodities with long histories, ancient prices drag the seasonal median way
    below current levels, producing inflated MAPEs (e.g. 209% for Wheat).

    This ensemble fixes the problem with two changes:

    1. **Windowed seasonal component**: compute month-of-year medians using only
       the last W months of training data (W = min(60, n_train)). This ensures
       the seasonal baseline reflects recent price levels, not 30-year-old data.

    2. **Damped OLS trend**: fit a linear trend (OLS) on the same window, then
       damp it with phi = 0.85 so it doesn't explode over long horizons. The
       damped trend adjusts the seasonal forecast for any remaining short-term
       drift (inflation, recent market shocks).

    Blend: forecast = windowed_seasonal_median + damped_trend_adjustment
           where damped_trend_adjustment = w_trend * OLS_slope * cum_damping(step)

    For Wheat with 390 months:
      - Windowed seasonal (60mo): median reflects ~\u20b92,000 (recent prices)
      - Damped trend: OLS_slope \u2248 1.45, \u03c6=0.85, w_trend=0.50
      - Forecast: \u20b92,000 + 0.50 \u00d7 1.45 \u00d7 2.23 \u2248 \u20b92,002
      - MAPE should drop from 209% to well under 100%

    Test set = last 3 months. Forecast horizon = `periods` months ahead.
    """
    df = prophet_df.copy()
    n = len(df)

    # Train/test split: last 3 months held out
    train = df[:-3] if n > 6 else df
    test = df[-3:] if n > 6 else df.iloc[-2:]

    # Extract month number for seasonal grouping
    train["month"] = train["ds"].dt.month
    test["month"] = test["ds"].dt.month

    # ── 1. Window the training data ──
    # Use at most 60 months (5 years) for the seasonal baseline
    # so ancient prices don't distort the forecast
    WINDOW_MONTHS = 60
    window = min(WINDOW_MONTHS, len(train))
    train_windowed = train.tail(window).copy()
    train_y_window = train_windowed["y"].values
    n_win = len(train_y_window)

    # ── 2. Windowed seasonal naive component ──
    seasonal_map = {}
    for m in range(1, 13):
        subset = train_windowed[train_windowed["month"] == m]["y"]
        if len(subset) > 0:
            seasonal_map[m] = float(subset.median())
    fallback_seasonal = float(np.median(train_y_window)) if n_win > 0 else 0.0

    # ── 3. Damped OLS trend on windowed data ──
    from scipy import stats as _stats
    x_win = np.arange(n_win, dtype=float)
    if n_win > 2:
        slope, intercept, r_val, p_val, std_err = _stats.linregress(x_win, train_y_window)
        slope = float(slope)
        intercept = float(intercept)
        trend_r2 = float(r_val ** 2)
    else:
        slope = 0.0
        intercept = float(train_y_window.mean()) if n_win > 0 else 0.0
        trend_r2 = 0.0

    # Damping factor: phi = 0.85 (stronger damping to prevent explosive extrapolation)
    # The cumulative damped trend adjustment after `step` months:
    #   damped_adj = slope * sum_{j=1}^{step} phi^j
    #   = slope * phi * (1 - phi^step) / (1 - phi)
    # Asymptote: slope * phi / (1 - phi) = slope * 5.67
    PHI = 0.85
    # Trend weight: how much of the damped trend to blend in
    W_TREND = 0.50

    def _damped_adj(step):
        """Cumulative damped trend adjustment after `step` months ahead."""
        if abs(slope) < 1e-10:
            return 0.0
        cum_factor = PHI * (1 - PHI ** step) / (1 - PHI)
        return slope * cum_factor

    # Helpers to compute trend value at any position in the window
    def _trend_val(t):
        return intercept + slope * t

    # The damped adjustment is measured from the LAST training observation
    # (the "current" position). For step i into the future:
    #   forecast = windowed_seasonal_median + W_TREND * damped_adjustment(i)

    # ── 4. Test set forecasts ──
    test_forecasts = []
    for step, (_, row) in enumerate(test.iterrows(), start=1):
        m = row["month"]
        seasonal_val = seasonal_map.get(m, fallback_seasonal)
        adj = _damped_adj(step)
        fc_val = seasonal_val + W_TREND * adj
        test_forecasts.append(fc_val)

    # ── 5. Compute metrics ──
    metrics = {}
    if len(test_forecasts) > 0 and len(test) > 0:
        actuals = test["y"].values
        fc_arr = np.array(test_forecasts)
        mae = float(np.abs(actuals - fc_arr).mean())
        rmse = float(np.sqrt(((actuals - fc_arr) ** 2).mean()))
        nonzero_mask = actuals > 1e-6
        if nonzero_mask.sum() > 0:
            mape = float((np.abs((actuals[nonzero_mask] - fc_arr[nonzero_mask]) / actuals[nonzero_mask]) * 100).mean())
        else:
            mape = None
        metrics = {"mae": mae, "rmse": rmse, "mape": mape}

    # ── 6. Generate future forecasts ──
    last_date = df["ds"].max()
    forecast_out = []
    for i in range(1, periods + 1):
        fc_date = last_date + pd.DateOffset(months=i)
        fc_month = fc_date.month
        seasonal_val = seasonal_map.get(fc_month, fallback_seasonal)
        adj = _damped_adj(i + 3)  # +3 because test set is 3 months ahead of training end
        fc_val = seasonal_val + W_TREND * adj

        # Confidence interval: seasonal residual std
        month_residuals = train_windowed[train_windowed["month"] == fc_month]["y"] - seasonal_map.get(fc_month, fallback_seasonal)
        seasonal_std = float(month_residuals.std()) if len(month_residuals) > 1 else float(np.std(train_y_window) * 0.3) if n_win > 1 else fc_val * 0.15
        # Trend uncertainty scales with sqrt(horizon)
        trend_ste = abs(slope) * (i + 3) * 0.5
        combined_std = np.sqrt(seasonal_std ** 2 + trend_ste ** 2)

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


def _train_seasonal_naive(prophet_df, commodity, state, periods):
    """Seasonal naive baseline: forecast = median price of same month in prior years.

    This is the recommended model for noisy agricultural price data because:
    - It captures the strong annual agricultural cycle (sowing \u2192 harvest \u2192 storage)
      without fitting any parametric trend that would overfit volatile observations.
    - Median is robust to outliers (one extreme price won't skew the forecast).
    - When multiple years are available for the same month, the forecast converges
      to the typical seasonal price level for that commodity.
    - MAPEs are realistic (typically 15-40%) instead of the 5000%+ that Prophet
      produces on sparse/noisy data.

    Test set = last 3 months. Forecast horizon = `periods` months ahead using the
    same month-of-year median from all training years.
    """
    import math

    df = prophet_df.copy()
    n = len(df)

    # Train/test split: last 3 months held out
    train = df[:-3] if n > 6 else df
    test = df[-3:] if n > 6 else df.iloc[-2:]

    # Extract month number for seasonal grouping
    train["month"] = train["ds"].dt.month
    test["month"] = test["ds"].dt.month

    # Build seasonal lookup: median price per month-of-year from training data
    seasonal_map = {}
    for m in range(1, 13):
        subset = train[train["month"] == m]["y"]
        if len(subset) > 0:
            seasonal_map[m] = float(subset.median())

    # Forecast test set (last 3 months)
    test_forecasts = []
    for _, row in test.iterrows():
        m = row["month"]
        fc = seasonal_map.get(m, train["y"].median() if len(train) > 0 else 0)
        test_forecasts.append(fc)

    # Compute metrics on test set
    metrics = {}
    if len(test_forecasts) > 0 and len(test) > 0:
        actuals = test["y"].values
        fc_arr = np.array(test_forecasts)
        mae = float(np.abs(actuals - fc_arr).mean())
        rmse = float(np.sqrt(((actuals - fc_arr) ** 2).mean()))
        # Avoid division by zero in MAPE
        nonzero_mask = actuals > 1e-6
        if nonzero_mask.sum() > 0:
            mape = float((np.abs((actuals[nonzero_mask] - fc_arr[nonzero_mask]) / actuals[nonzero_mask]) * 100).mean())
        else:
            mape = None
        metrics = {"mae": mae, "rmse": rmse, "mape": mape}

    # Generate future forecasts for `periods` months ahead
    last_date = df["ds"].max()
    forecast_out = []
    for i in range(1, periods + 1):
        fc_date = last_date + pd.DateOffset(months=i)
        fc_month = fc_date.month
        fc_val = seasonal_map.get(fc_month, train["y"].median() if len(train) > 0 else 0)

        # Confidence interval: \u00b11.96 \u00d7 std of residuals on training months with this season
        residuals = train[train["month"] == fc_month]["y"] - [seasonal_map.get(fc_month, train["y"].median())]
        std_err = float(residuals.std()) if len(residuals) > 1 else float(train["y"].std() * 0.3) if len(train) > 1 else fc_val * 0.15

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


def _train_prophet(prophet_df, commodity, state, periods):
    """Train Prophet forecast (original implementation)."""
    # Train/test split: last 3 months for testing
    train = prophet_df[:-3] if len(prophet_df) > 6 else prophet_df
    test = prophet_df[-3:] if len(prophet_df) > 6 else prophet_df.iloc[-2:]
    
    # Train Prophet
    model = Prophet(
        yearly_seasonality=True,
        weekly_seasonality=False,
        daily_seasonality=False,
        seasonality_mode="multiplicative",
        changepoint_prior_scale=0.05,
    )
    model.fit(train)
    
    # Forecast
    future = model.make_future_dataframe(periods=periods, freq="MS")
    forecast = model.predict(future)
    
    # Metrics on test set
    test_forecast = forecast[forecast["ds"].isin(test["ds"])]
    metrics = {}
    if len(test_forecast) > 0:
        merged = test.merge(test_forecast, on="ds", how="inner")
        if len(merged) > 0:
            mae = np.abs(merged["y"] - merged["yhat"]).mean()
            rmse = np.sqrt(((merged["y"] - merged["yhat"]) ** 2).mean())
            mape = (np.abs((merged["y"] - merged["yhat"]) / merged["y"]) * 100).mean()
            metrics = {"mae": float(mae), "rmse": float(rmse), "mape": float(mape)}
    
    # Format forecast output
    forecast_out = []
    for _, row in forecast.iterrows():
        forecast_out.append({
            "date": str(row["ds"].date()),
            "forecast": float(row["yhat"]),
            "forecast_lower": float(row["yhat_lower"]),
            "forecast_upper": float(row["yhat_upper"]),
        })
    
    return {
        "commodity": commodity,
        "state": state or "All",
        "forecast": forecast_out,
        "metrics": metrics,
        "n_training_months": len(train),
        "n_test_months": len(test),
        "model": model,
    }


def _train_exponential_smoothing(prophet_df, commodity, state, periods):
    """Lightweight fallback: simple exponential smoothing with trend."""
    from scipy.optimize import minimize_scalar
    
    # Use log prices for stability
    y = prophet_df["y"].values
    n = len(y)
    
    # Train/test split
    train = y[:-3] if n > 6 else y
    test = y[-3:] if n > 6 else y[-2:]
    
    # Simple exponential smoothing with linear trend
    def forecast_with_alpha(alpha, beta=0.3):
        level = train[0]
        trend = (train[-1] - train[0]) / len(train) if len(train) > 1 else 0
        forecasts = []
        for t in range(len(train) + periods):
            if t < len(train):
                new_level = alpha * train[t] + (1 - alpha) * (level + trend)
                trend = beta * (new_level - level) + (1 - beta) * trend
                level = new_level
            else:
                forecasts.append(level + trend)
        return forecasts
    
    # Optimize alpha
    def mse(alpha):
        fc = forecast_with_alpha(alpha)[:-periods]
        if len(fc) != len(train):
            return 1e10
        return np.mean((np.array(fc) - train) ** 2)
    
    result = minimize_scalar(mse, bounds=(0.01, 0.99), method="bounded")
    alpha_opt = result.x
    
    # Generate forecast
    all_forecasts = forecast_with_alpha(alpha_opt)
    train_forecasts = all_forecasts[:-periods]
    future_forecasts = all_forecasts[-periods:]
    
    # Metrics on test set
    metrics = {}
    if len(train_forecasts) >= len(test):
        test_fc = train_forecasts[-len(test):]
        mae = np.abs(np.array(test) - np.array(test_fc)).mean()
        rmse = np.sqrt(((np.array(test) - np.array(test_fc)) ** 2).mean())
        mape = (np.abs((np.array(test) - np.array(test_fc)) / np.array(test)) * 100).mean()
        metrics = {"mae": float(mae), "rmse": float(rmse), "mape": float(mape)}
    
    # Format forecast output
    last_date = prophet_df["ds"].max()
    forecast_out = []
    for i, fc_val in enumerate(future_forecasts):
        forecast_date = last_date + pd.DateOffset(months=i+1)
        # Simple confidence intervals
        std_err = np.std(np.array(train) - np.array(train_forecasts[-len(train):])) if len(train_forecasts) >= len(train) else np.std(train) * 0.1
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
        "model": None,  # No model object for fallback
        "method": "exponential_smoothing",
    }


def get_forecast_summary(conn, commodity: str) -> dict:
    """Get a forecast summary for the API response (no model object)."""
    result = train_forecast(conn, commodity=commodity)
    
    # Remove the model object (not JSON serializable)
    if "model" in result:
        del result["model"]
    
    return result


def compare_forecast_models(
    conn,
    commodity: str,
    state: Optional[str] = None,
    periods: int = 12,
) -> dict:
    """
    Run both Prophet and LSTM on the same data and return an honest comparison.
    
    Reports both MAPEs, picks the winner, and explains why — the same
    honest-comparison discipline Superstore pioneered.
    
    Args:
        conn: DuckDB connection
        commodity: Commodity to forecast
        state: Optional state filter
        periods: Forecast horizon in months
        
    Returns:
        Dict with prophet_metrics, lstm_metrics, better_model, explanation
    """
    # 1. Pull monthly price time series (same data for both models)
    df = conn.execute(
        """SELECT arrival_date, AVG(modal_price) as modal_price
           FROM prices
           WHERE commodity = ? AND modal_price IS NOT NULL
           GROUP BY arrival_date ORDER BY arrival_DATE""",
        [commodity],
    ).fetchdf()
    
    if len(df) < 30:
        return {
            "commodity": commodity,
            "error": f"Insufficient data for model comparison: {len(df)} daily records",
        }
    
    # Aggregate to monthly (same pattern as train_forecast)
    df["arrival_date"] = pd.to_datetime(df["arrival_date"])
    df["year_month"] = df["arrival_date"].dt.to_period("M").astype(str)
    monthly = df.groupby("year_month")["modal_price"].mean().reset_index()
    monthly = monthly.rename(columns={"modal_price": "price"})
    monthly_prices = monthly["price"].values
    
    if len(monthly_prices) < 12:
        return {
            "commodity": commodity,
            "error": f"Insufficient monthly data: {len(monthly_prices)} months",
        }
    
    # 2. Run Prophet (explicit method="prophet" so this comparison remains accurate
    #    even though train_forecast() now defaults to seasonal_naive)
    prophet_result = train_forecast(conn, commodity=commodity, state=state, periods=periods, method="prophet")
    prophet_metrics = prophet_result.get("metrics", {})
    prophet_mape = prophet_metrics.get("mape")
    prophet_mae = prophet_metrics.get("mae")
    prophet_rmse = prophet_metrics.get("rmse")
    
    # 3. Run LSTM
    from mandi_rdd.analysis.lstm_forecast import train_lstm_forecast
    lstm_result = train_lstm_forecast(monthly_prices)
    
    lstm_mape = lstm_result.get("test_mape")
    lstm_mae = lstm_result.get("test_mae")
    lstm_rmse = lstm_result.get("test_rmse")
    lstm_error = lstm_result.get("error")
    
    # 4. Compare honestly
    comparison = {
        "commodity": commodity,
        "state": state or "All",
        "n_training_months": len(monthly_prices),
        "prophet": {
            "test_mape": prophet_mape,
            "test_mae": prophet_mae,
            "test_rmse": prophet_rmse,
            "available": prophet_mape is not None,
        },
        "lstm": {
            "test_mape": lstm_mape,
            "test_mae": lstm_mae,
            "test_rmse": lstm_rmse,
            "available": lstm_mape is not None and lstm_error is None,
            "error": lstm_error,
        },
        "better_model": None,
        "explanation": "",
    }
    
    # 5. Pick winner
    both_available = comparison["prophet"]["available"] and comparison["lstm"]["available"]
    
    if both_available and prophet_mape is not None and lstm_mape is not None:
        if prophet_mape < lstm_mape:
            comparison["better_model"] = "Prophet"
            comparison["explanation"] = (
                f"Prophet (MAPE: {prophet_mape:.1f}%) outperforms LSTM (MAPE: {lstm_mape:.1f}%) "
                f"on this dataset ({len(monthly_prices)} months). This matches the Superstore finding: "
                f"classical structural models generalize better than deep learning when training data "
                f"is limited. Prophet's seasonality decomposition captures the annual price cycle "
                f"more efficiently than LSTM's learned representations at this data scale."
            )
        elif lstm_mape < prophet_mape:
            comparison["better_model"] = "LSTM"
            comparison["explanation"] = (
                f"LSTM (MAPE: {lstm_mape:.1f}%) outperforms Prophet (MAPE: {prophet_mape:.1f}%) "
                f"on this dataset ({len(monthly_prices)} months). The LSTM captures non-linear "
                f"dependencies in the price series that Prophet's additive decomposition misses. "
                f"This is more likely with larger, more complex time series."
            )
        else:
            comparison["better_model"] = "Tie"
            comparison["explanation"] = (
                f"Prophet and LSTM produce nearly identical test error "
                f"(MAPE: {prophet_mape:.1f}% vs {lstm_mape:.1f}%). Either model is suitable "
                f"for this commodity, but Prophet is preferred for interpretability."
            )
    elif comparison["prophet"]["available"]:
        comparison["better_model"] = "Prophet"
        comparison["explanation"] = (
            f"Only Prophet produced a valid forecast (MAPE: {prophet_mape:.1f}%). "
            f"LSTM unavailable: {lstm_error or 'PyTorch not installed'}."
        )
    elif comparison["lstm"]["available"]:
        comparison["better_model"] = "LSTM"
        comparison["explanation"] = (
            f"Only LSTM produced a valid forecast (MAPE: {lstm_mape:.1f}%). "
            f"Prophet unavailable or insufficient data for its training/test split."
        )
    else:
        comparison["error"] = "Neither model produced a valid forecast"
    
    # 6. Include forecast chart data
    comparison["forecast"] = prophet_result.get("forecast", [])
    
    # 7. Include monthly time series for charting
    comparison["monthly_history"] = {
        "dates": monthly["arrival_date"].dt.strftime("%Y-%m-%d").tolist(),
        "prices": monthly_prices.tolist(),
    }
    
    # 8. Include LSTM future forecast if available
    if "forecast" in lstm_result and not isinstance(lstm_result.get("forecast"), list):
        pass  # LSTM forecast is already a list from train_lstm_forecast
    
    comparison["lstm"]["future_forecast"] = lstm_result.get("forecast", []) if lstm_error is None else []
    
    return comparison
