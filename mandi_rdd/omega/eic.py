"""MandiRDD — EIC: Emergent/Explainable Intelligence Core.

Causal-discovery ensemble over commodity price series, plus a meta-learning
insight generator that ranks discovered links by effect strength, statistical
significance and forecast confidence (learned from ``forecast_metrics``).

Discovery ensemble
------------------
* Granger causality (lagged OLS F-test) — directed cause → effect links.
* Partial-correlation skeleton (PC-style via precision matrix) — undirected
  association links that survive conditioning on all other series.

Meta-learning
-------------
Insights are ranked with ``score = strength * significance * confidence`` where
confidence is the model confidence learned per commodity from the
``forecast_metrics`` table (1 / (1 + MAPE)). Network hubs (drivers) are
detected from Granger out-degree.
"""

from __future__ import annotations

import logging
import math
import time
from typing import Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None  # type: ignore

try:
    from scipy import stats as _stats

    SCIPY_AVAILABLE = True
except ImportError:  # pragma: no cover
    _stats = None
    SCIPY_AVAILABLE = False


# ──────────────────────────────────────────────────────────────────────
# Data loading
# ──────────────────────────────────────────────────────────────────────

def load_price_matrix(
    conn, limit: int = 60, min_obs: int = 6
) -> Tuple[List[str], Optional[np.ndarray]]:
    """Load aligned monthly mean modal prices.

    Returns ``(commodities, matrix)`` where matrix is (n_months, n_commodities);
    missing months are forward-filled. Commodities with fewer than ``min_obs``
    months are dropped. Returns ``([], None)`` when no usable series exist.
    """
    if np is None:  # pragma: no cover
        raise RuntimeError("EIC requires numpy")

    rows = conn.execute(
        """
        SELECT commodity,
               strftime(date_trunc('month', CAST(arrival_date AS DATE)), '%Y-%m') AS ym,
               AVG(modal_price) AS mean_price
        FROM prices
        WHERE modal_price > 0 AND arrival_date IS NOT NULL
        GROUP BY commodity, ym
        ORDER BY ym
        """
    ).fetchall()

    by_comm: Dict[str, Dict[str, float]] = {}
    months_all: set = set()
    for commodity, ym, mean_price in rows:
        if commodity is None or ym is None or mean_price is None:
            continue
        by_comm.setdefault(str(commodity), {})[str(ym)] = float(mean_price)
        months_all.add(str(ym))
    if not by_comm:
        return [], None

    ordered_months = sorted(months_all)
    commodities = [c for c, m in by_comm.items() if len(m) >= min_obs]
    commodities = commodities[:limit] if limit and limit > 0 else commodities
    if not commodities:
        return [], None

    matrix = np.full((len(ordered_months), len(commodities)), np.nan)
    for j, c in enumerate(commodities):
        for ym, v in by_comm[c].items():
            if ym in ordered_months:
                matrix[ordered_months.index(ym), j] = v

    # Forward-fill within each commodity column.
    for j in range(matrix.shape[1]):
        col = matrix[:, j]
        prev = np.nan
        for i in range(len(col)):
            if np.isnan(col[i]):
                col[i] = prev
            else:
                prev = col[i]
        matrix[:, j] = col

    # Drop rows (months) still containing NaN anywhere.
    keep = ~np.isnan(matrix).any(axis=1)
    matrix = matrix[keep]
    if matrix.shape[0] < min_obs:
        return [], None
    return commodities, matrix


# ──────────────────────────────────────────────────────────────────────
# Causal discovery ensemble
# ──────────────────────────────────────────────────────────────────────

def _log_returns(matrix: np.ndarray) -> np.ndarray:
    """Log-returns of the price matrix (n_obs-1, n_comm)."""
    m = np.asarray(matrix, dtype=float)
    logp = np.log(np.maximum(m, 1e-9))
    return np.diff(logp, axis=0)


def granger_causality_matrix(
    series: np.ndarray, max_lag: int = 3
) -> Tuple[np.ndarray, np.ndarray]:
    """Pairwise Granger causality F-stats and p-values (cause rows → effect cols).

    Vectorised per-pair OLS. Returns ``(F, p)`` matrices with NaN on the
    diagonal; p is NaN when scipy is unavailable.
    """
    n_comm = series.shape[1]
    F = np.full((n_comm, n_comm), np.nan)
    P = np.full((n_comm, n_comm), np.nan)

    for cause in range(n_comm):
        for effect in range(n_comm):
            if cause == effect:
                continue
            x = series[max_lag:, cause]
            y = series[max_lag:, effect]
            # Build lag matrices for y only (restricted) and y+x (unrestricted).
            # Column k holds lag-(k+1) of the series, aligned so that y[t] pairs
            # with series[t-max_lag+k] → genuine historical lags (no lookahead).
            y_lags = np.column_stack([series[max_lag - k - 1 : -k - 1, effect] for k in range(max_lag)])
            x_lags = np.column_stack([series[max_lag - k - 1 : -k - 1, cause] for k in range(max_lag)])

            n_obs = y.shape[0]
            k_rest = max_lag + 1  # intercept + lags of y
            if n_obs <= k_rest + max_lag + 1:
                continue

            A_r = np.column_stack([np.ones(n_obs), y_lags])
            A_u = np.column_stack([np.ones(n_obs), y_lags, x_lags])

            # Restricted regression.
            beta_r, *_ = np.linalg.lstsq(A_r, y, rcond=None)
            rss_r = float(np.sum((y - A_r @ beta_r) ** 2))
            # Unrestricted regression.
            beta_u, *_ = np.linalg.lstsq(A_u, y, rcond=None)
            rss_u = float(np.sum((y - A_u @ beta_u) ** 2))

            df1 = max_lag
            df2 = n_obs - A_u.shape[1]

            # Guard against (near-)perfect fits: when the unrestricted model
            # explains the effect series almost exactly (rss_u ~ 0), the F-test
            # is degenerate. Skip the pair rather than emit inf/NaN downstream.
            if rss_u <= 1e-12 or rss_r <= rss_u:
                continue

            f_stat = ((rss_r - rss_u) / df1) / (rss_u / max(1.0, df2))
            if not math.isfinite(f_stat) or f_stat <= 0.0:
                continue
            F[cause, effect] = f_stat

            if SCIPY_AVAILABLE:
                P[cause, effect] = float(_stats.f.sf(f_stat, df1, df2))
            else:
                P[cause, effect] = float("nan")
    return F, P


def partial_correlation_skeleton(
    returns: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    """PC-style skeleton: partial correlations via the precision matrix.

    Returns ``(R, p)`` symmetric matrices (i,j) of partial correlations and
    Fisher-z p-values; diagonal is NaN.
    """
    n_comm = returns.shape[1]
    R = np.full((n_comm, n_comm), np.nan)
    P = np.full((n_comm, n_comm), np.nan)

    # Drop zero-variance columns (constant series) - they make corrcoef NaN.
    std = np.nanstd(returns, axis=0)
    keep = np.where(std > 1e-12)[0]
    if keep.size < 2:
        return R, P
    sub = returns[:, keep]

    corr = np.corrcoef(sub.T)
    if np.any(np.isnan(corr)):
        return R, P
    try:
        prec = np.linalg.inv(corr + 1e-6 * np.eye(keep.size))
    except np.linalg.LinAlgError:  # pragma: no cover
        return R, P

    n_obs = returns.shape[0]
    for a in range(keep.size):
        for b in range(a + 1, keep.size):
            i, j = int(keep[a]), int(keep[b])
            pc = -prec[a, b] / math.sqrt(prec[a, a] * prec[b, b] + 1e-12)
            pc = max(-1.0, min(1.0, pc))
            R[i, j] = R[j, i] = pc
            # Fisher z-test for partial correlation.
            z = 0.5 * math.log((1 + pc) / (1 - pc + 1e-12))
            se = 1.0 / math.sqrt(max(1, n_obs - 3))
            p = 2.0 * (1.0 - 0.5 * (1.0 + math.erf(abs(z) / se / math.sqrt(2.0))))
            P[i, j] = P[j, i] = min(1.0, max(0.0, p))
    return R, P


# ──────────────────────────────────────────────────────────────────────
# Meta-learning & insight generation
# ──────────────────────────────────────────────────────────────────────

def _load_confidence_map(conn) -> Dict[str, float]:
    """Learned model confidence per commodity from forecast_metrics."""
    conf: Dict[str, float] = {}
    try:
        rows = conn.execute(
            """
            SELECT commodity, AVG(test_mape) AS mape
            FROM forecast_metrics
            WHERE test_mape IS NOT NULL
            GROUP BY commodity
            """
        ).fetchall()
    except Exception:  # pragma: no cover
        return conf
    for commodity, mape in rows:
        mape = float(mape or 0.0)
        conf[str(commodity)] = round(1.0 / (1.0 + mape), 4)
    return conf


def causal_discovery(conn, limit: int = 60, max_lag: int = 3, p_threshold: float = 0.10) -> dict:
    """Run the causal-discovery ensemble over the price series.

    Returns dict with edges (granger + pc), commodities and metadata.
    """
    commodities, matrix = load_price_matrix(conn, limit=limit)
    if not commodities or matrix is None:
        return {"n_commodities": 0, "n_edges": 0, "edges": [], "commodities": []}

    returns = _log_returns(matrix)
    F, Pg = granger_causality_matrix(matrix, max_lag=max_lag)
    R, Pc = partial_correlation_skeleton(returns)
    conf = _load_confidence_map(conn)

    edges: List[dict] = []
    n = len(commodities)
    for cause in range(n):
        for effect in range(n):
            if cause == effect:
                continue
            f_stat = F[cause, effect]
            if np.isnan(f_stat):
                continue
            p_val = Pg[cause, effect]
            sig_ok = (not np.isnan(p_val) and p_val < p_threshold) or (np.isnan(p_val) and f_stat > 2.0)
            if sig_ok:
                strength = float(np.tanh(f_stat / max(1.0, max_lag)))
                edges.append(
                    {
                        "kind": "granger",
                        "cause": commodities[cause],
                        "effect": commodities[effect],
                        "lag": max_lag,
                        "f_stat": round(float(f_stat), 3),
                        "p_value": None if np.isnan(p_val) else round(float(p_val), 4),
                        "strength": round(strength, 4),
                        "method": "granger",
                        "direction": "cause->effect",
                    }
                )

    for i in range(n):
        for j in range(i + 1, n):
            pc = R[i, j]
            p_val = Pc[i, j]
            if np.isnan(pc) or p_val >= p_threshold or abs(pc) < 0.25:
                continue
            edges.append(
                {
                    "kind": "partial-correlation",
                    "cause": commodities[i],
                    "effect": commodities[j],
                    "lag": 0,
                    "f_stat": None,
                    "p_value": round(float(p_val), 4),
                    "strength": round(abs(float(pc)), 4),
                    "method": "pc-skeleton",
                    "direction": "undirected",
                }
            )

    return {
        "n_commodities": n,
        "n_edges": len(edges),
        "edges": edges,
        "commodities": commodities,
        "confidence_map": conf,
    }


def generate_insights(
    conn,
    limit: int = 60,
    max_lag: int = 3,
    top_k: int = 10,
    p_threshold: float = 0.10,
) -> dict:
    """Generate meta-learning ranked insights from the discovery ensemble."""
    start = time.time()
    discovery = causal_discovery(conn, limit=limit, max_lag=max_lag, p_threshold=p_threshold)
    edges = discovery["edges"]
    conf = discovery.get("confidence_map", {})

    ranked: List[dict] = []
    for e in edges:
        cause_conf = float(conf.get(e["cause"], 0.5))
        effect_conf = float(conf.get(e["effect"], 0.5))
        p_val = e["p_value"]
        significance = 1.0 if p_val is None else float(1.0 - p_val)
        score = float(e["strength"]) * significance * (0.5 * cause_conf + 0.5 * effect_conf)
        ranked.append(
            {
                "id": f"{e['kind']}:{e['cause']}->{e['effect']}",
                "kind": e["kind"],
                "cause": e["cause"],
                "effect": e["effect"],
                "lag": e["lag"],
                "method": e["method"],
                "strength": e["strength"],
                "p_value": e["p_value"],
                "confidence": round(0.5 * cause_conf + 0.5 * effect_conf, 4),
                "score": round(score, 4),
                "narrative": _narrative(e, cause_conf, effect_conf),
            }
        )

    ranked.sort(key=lambda r: r["score"], reverse=True)
    ranked = ranked[:top_k]

    # Network hubs (Granger out-degree) = candidate market drivers.
    out_degree: Dict[str, int] = {}
    for e in edges:
        if e["method"] == "granger":
            out_degree[e["cause"]] = out_degree.get(e["cause"], 0) + 1
    hubs = sorted(
        [{"commodity": c, "out_degree": d} for c, d in out_degree.items()],
        key=lambda h: h["out_degree"],
        reverse=True,
    )[:5]

    return {
        "engine": "eic-causal-ensemble",
        "n_commodities": discovery["n_commodities"],
        "n_edges": discovery["n_edges"],
        "n_insights": len(ranked),
        "insights": ranked,
        "market_drivers": hubs,
        "scipy_available": SCIPY_AVAILABLE,
        "wall_time_s": round(time.time() - start, 4),
    }


def _narrative(e: dict, cause_conf: float, effect_conf: float) -> str:
    if e["method"] == "granger":
        p_txt = f"p={e['p_value']:.3f}" if e["p_value"] is not None else "p≈n/a"
        return (
            f"Granger causality: {e['cause']} leads {e['effect']} at lag {e['lag']} "
            f"(F={e['f_stat']}, {p_txt}); confidence {0.5 * cause_conf + 0.5 * effect_conf:.2f}."
        )
    return (
        f"Partial-correlation link: {e['cause']} ↔ {e['effect']} persists after "
        f"conditioning on all other series (p={e['p_value']:.3f}); "
        f"confidence {0.5 * cause_conf + 0.5 * effect_conf:.2f}."
    )


def engine_status() -> dict:
    """Static capability report for the EIC module."""
    return {
        "engine": "eic-causal-ensemble",
        "model": "causal discovery ensemble + meta-learning insight ranking",
        "methods": ["granger", "pc-skeleton"],
        "scipy_available": SCIPY_AVAILABLE,
        "emulated": True,
        "description": "Emergent intelligence: causal links between commodities ranked by effect, significance and confidence.",
    }