"""
MandiIQ Omega — QVE: Quantum Valuation Engine (backend).

Solves the *optimal particle placement* problem: given N particles
(commodity x region predictions), find the 3D spatial configuration that
minimizes energy while maximizing information clarity.

This is a QUBO (Quadratic Unconstrained Binary Optimization) problem —
the exact formulation a D-Wave quantum annealer would consume. Because
D-Wave hardware is not available locally, we emulate quantum annealing
with a **simulated annealing** solver over the same QUBO objective:

    H = Σᵢⱼ Jᵢⱼ sᵢ sⱼ + Σᵢ hᵢ sᵢ

where
- Jᵢⱼ encodes attraction/repulsion between particle pairs
  (commodity similarity → attract; unrelated → repel; SHAP edges → connect),
- hᵢ encodes importance (significance, recency, confidence).

Each binary variable sᵢ selects a candidate position for particle i from
a precomputed grid; pairwise terms enforce minimum spacing and clustering.
"""

from __future__ import annotations

import logging
import math
import random
import time
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# ── Optional dependency guards (mirror repo convention) ──
try:
    import pandas as pd  # noqa: F401
    PANDAS_AVAILABLE = True
except ImportError:  # pragma: no cover
    PANDAS_AVAILABLE = False


@dataclass
class Particle:
    """A single entity in the quantum particle field."""

    id: str
    commodity: str
    region: str = "ALL"
    date: str = ""
    prediction: Optional[float] = None
    confidence: float = 0.5
    significance: float = 0.5
    shap_values: Dict[str, float] = field(default_factory=dict)
    model_version: str = "unknown"

    # Computed during placement
    position: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    energy: float = 0.0
    color: Tuple[float, float, float] = (0.4, 0.6, 1.0)
    glow: float = 0.5
    size: float = 1.0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "commodity": self.commodity,
            "region": self.region,
            "date": self.date,
            "prediction": self.prediction,
            "confidence": round(float(self.confidence), 4),
            "significance": round(float(self.significance), 4),
            "shap_values": self.shap_values,
            "model_version": self.model_version,
            "position": [round(float(v), 4) for v in self.position],
            "energy": round(float(self.energy), 4),
            "color": [round(float(v), 4) for v in self.color],
            "glow": round(float(self.glow), 4),
            "size": round(float(self.size), 4),
        }


# ──────────────────────────────────────────────────────────────────────
# QUBO construction
# ──────────────────────────────────────────────────────────────────────

def _commodity_kernel(c1: str, c2: str) -> float:
    """Token-overlap similarity in [0,1]; 1.0 for identical commodities."""
    if c1 == c2:
        return 1.0
    t1 = set(c1.lower().replace("(", " ").replace(")", " ").replace("/", " ").split())
    t2 = set(c2.lower().replace("(", " ").replace(")", " ").replace("/", " ").split())
    if not t1 or not t2:
        return 0.0
    return len(t1 & t2) / max(1.0, float(len(t1 | t2)))


def _gaussian(x: float, sigma: float = 7.0) -> float:
    return math.exp(-0.5 * (x / sigma) ** 2)


def build_qubo(
    particles: Sequence[Particle],
    attraction_w: float = 0.4,
    temporal_w: float = 0.3,
    shap_w: float = 0.3,
    repulsion: float = 0.1,
) -> Dict[Tuple[int, int], float]:
    """
    Build the QUBO matrix Q[(i,j)] over particle pairs.

    Negative coupling = attractive (energy lowers when co-located);
    positive = repulsive (penalizes overlap).

    Args:
        particles: the particle list (index in list == variable id).
        attraction_w: weight of commodity-similarity coupling.
        temporal_w: weight of date-proximity coupling.
        shap_w: weight of SHAP-edge coupling.
        repulsion: baseline repulsion to prevent overlap.

    Returns:
        Dict mapping (i, j) -> coupling value (i <= j for diagonal).
    """
    Q: Dict[Tuple[int, int], float] = {}
    n = len(particles)

    dates: List[Optional[float]] = []
    for p in particles:
        d = None
        if p.date:
            try:
                d = float(_parse_date_ordinal(p.date))
            except Exception:
                d = None
        dates.append(d)

    for i in range(n):
        p1 = particles[i]
        # Linear bias: importance pulls toward origin (lower energy)
        importance = (p1.significance * 0.5 + p1.confidence * 0.3)
        recency = 0.2
        if dates[i] is not None:
            # More recent → stronger pull (front/foreground)
            recency = _gaussian(float(dates[i]) - float(_now_ordinal()), sigma=60.0) * 0.2 + 0.05
        Q[(i, i)] = -(importance + recency)

        for j in range(i + 1, n):
            p2 = particles[j]

            commodity_similarity = _commodity_kernel(p1.commodity, p2.commodity)
            temporal_proximity = 0.0
            if dates[i] is not None and dates[j] is not None:
                temporal_proximity = _gaussian(float(dates[i]) - float(dates[j]), sigma=7.0)

            shap_connection = 0.0
            if p1.shap_values:
                # Mutual feature contribution overlap
                keys = set(p1.shap_values) & set(p2.shap_values)
                if keys:
                    shap_connection = sum(
                        abs(p1.shap_values[k]) * abs(p2.shap_values[k]) for k in keys
                    ) / max(1.0, float(len(keys)))

            attraction = (
                commodity_similarity * attraction_w
                + temporal_proximity * temporal_w
                + min(1.0, shap_connection) * shap_w
            )
            Q[(i, j)] = repulsion - attraction  # negative → attract

    return Q


def _parse_date_ordinal(date_str: str) -> float:
    """Best-effort parse of ISO-ish dates to a numeric ordinal."""
    try:
        import datetime as dt
        return dt.date.fromisoformat(date_str[:10]).toordinal()
    except Exception:
        # Fallback: numeric suffix in the string
        digits = "".join(ch for ch in date_str if ch.isdigit())
        return float(digits[:8]) if digits else 0.0


def _now_ordinal() -> float:
    import datetime as dt
    return float(dt.date.today().toordinal())


# ──────────────────────────────────────────────────────────────────────
# Simulated annealing solver (quantum-emulated)
# ──────────────────────────────────────────────────────────────────────

def solve_placement_simulated_annealing(
    particles: Sequence[Particle],
    Q: Dict[Tuple[int, int], float],
    *,
    n_iter: int = 4000,
    t_start: float = 5.0,
    t_end: float = 0.01,
    seed: Optional[int] = None,
    grid_scale: float = 8.0,
    verbose: bool = False,
) -> Dict[str, object]:
    """
    Solve the QUBO with simulated annealing.

    Each particle picks a candidate lattice site on a 3D grid (i.e., the
    binary decision is *which site*), and annealing moves particles between
    sites to minimize total pairwise + linear energy.

    Returns a dict with:
        positions: list of (x, y, z) per particle index
        energy: final objective value
        schedule: {iterations, t_start, t_end}
        wall_time_s: solver runtime
    """
    rng = random.Random(seed)
    n = len(particles)

    # Candidate grid: evenly spread lattice
    grid = _build_lattice(n, scale=grid_scale)

    # Random initial assignment
    assign = [rng.randrange(len(grid)) for _ in range(n)]
    # Force uniqueness for the first pass (helps convergence)
    _dedupe(assign, len(grid), rng)

    def energy_of(assignment: List[int]) -> float:
        total = 0.0
        for (i, j), v in Q.items():
            if i == j:
                if assignment[i] == 0:
                    total += v  # linear term applies when site==origin-ish
            else:
                # Pairwise: penalize co-location by coupling strength
                if assignment[i] == assignment[j]:
                    total += v
                else:
                    # Slight distance-based cost (cheap approximation)
                    total += _dist(grid[assignment[i]], grid[assignment[j]]) * 0.02
        return total

    cur = assign[:]
    cur_e = energy_of(cur)
    best = cur[:]
    best_e = cur_e

    t = t_start
    dt_iter = max(1, n_iter // 10)
    start = time.time()

    for it in range(n_iter):
        # Geometric cooling
        t = t_start * (t_end / t_start) ** (it / max(1, n_iter))

        i = rng.randrange(n)
        old_site = cur[i]
        new_site = rng.randrange(len(grid))
        if new_site == old_site:
            continue

        cur[i] = new_site
        new_e = energy_of(cur)

        delta = new_e - cur_e
        if delta <= 0 or rng.random() < math.exp(-delta / max(t, 1e-9)):
            cur_e = new_e
            if cur_e < best_e:
                best_e = cur_e
                best = cur[:]
        else:
            cur[i] = old_site  # revert

        if verbose and it % dt_iter == 0:
            logger.info("SA iter=%d t=%.4f E=%.4f", it, t, cur_e)

    # Assemble output positions
    positions = [tuple(grid[best[i]]) for i in range(n)]
    return {
        "positions": positions,
        "energy": float(best_e),
        "schedule": {"iterations": n_iter, "t_start": t_start, "t_end": t_end},
        "wall_time_s": round(time.time() - start, 3),
    }


def _build_lattice(n: int, scale: float) -> List[Tuple[float, float, float]]:
    """Generate ~4n candidate sites on a Fibonacci-sphere-ish lattice."""
    sites: List[Tuple[float, float, float]] = []
    k_max = max(8, int(4 * n))
    for k in range(k_max):
        # Spherical shell with radius variation for depth
        y = 1.0 - (k / max(1, k_max - 1)) * 2.0
        radius = math.sqrt(max(0.0, 1.0 - y * y))
        theta = k * 2.399963229728653  # golden angle
        r = scale * (0.5 + 0.5 * radius)
        sites.append(
            (
                round(r * radius * math.cos(theta), 4),
                round(r * y, 4),
                round(r * radius * math.sin(theta), 4),
            )
        )
    return sites


def _dedupe(assign: List[int], n_sites: int, rng: random.Random) -> None:
    """Force a valid (mostly unique) initial assignment."""
    seen: set = set()
    for idx in range(len(assign)):
        if assign[idx] in seen:
            assign[idx] = (assign[idx] + 1) % n_sites
        seen.add(assign[idx])


def _dist(a: Tuple[float, float, float], b: Tuple[float, float, float]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


# ──────────────────────────────────────────────────────────────────────
# Data wiring (DuckDB → particles)
# ──────────────────────────────────────────────────────────────────────

def build_particles_from_db(conn, commodity: Optional[str] = None, limit: int = 60) -> List[Particle]:
    """
    Build a particle list from the DuckDB tables (prices, rdd_results,
    forecast_metrics) following the same connection conventions as
    mandi_rdd.analysis modules.
    """
    particles: List[Particle] = []

    # 1) RDD results → significance particles (redistricting discontinuity)
    try:
        rdd_query = """
            SELECT commodity, effect, p_value, placebo_p_value, is_valid
            FROM rdd_results
            WHERE effect IS NOT NULL
        """
        params: List = []
        if commodity:
            rdd_query += " AND LOWER(commodity) = LOWER(?)"
            params.append(commodity)
        rdd_query += " ORDER BY ABS(effect) DESC, commodity ASC LIMIT ?"
        params.append(limit)
        rdd_df = conn.execute(rdd_query, params).fetchdf()
        for _, row in rdd_df.iterrows():
            p = row.get("p_value")
            placebo_p = row.get("placebo_p_value")
            significance = 0.5
            if p is not None:
                try:
                    significance = float(np.clip(1.0 - float(p), 0.1, 1.0))
                except Exception:
                    significance = 0.5
            # Placebo validation: valid RDD has non-significant placebo
            if placebo_p is not None:
                try:
                    if float(placebo_p) > 0.05:
                        significance = min(1.0, significance * 1.1)
                    else:
                        significance = max(0.1, significance * 0.5)
                except Exception:
                    pass
            particles.append(
                Particle(
                    id=f"rdd:{row['commodity']}:ALL",
                    commodity=row["commodity"],
                    region="ALL",
                    prediction=float(row["effect"]) if row.get("effect") is not None else None,
                    confidence=significance,
                    significance=significance,
                    shap_values={"rdd_effect": float(row["effect"] or 0.0)},
                    model_version="rdd-engine",
                )
            )
    except Exception as e:  # pragma: no cover
        logger.warning("QVE: rdd_results read failed: %s", e)

    # 2) Forecast metrics → confidence particles
    try:
        fc_query = """
            SELECT commodity, test_mape, is_valid, n_training_months
            FROM forecast_metrics
        """
        if commodity:
            fc_query += " WHERE LOWER(commodity) = LOWER(?)"
        fc_query += " ORDER BY test_mape ASC, commodity ASC LIMIT ?"
        args: List = ([commodity] if commodity else []) + [limit]
        fc_df = conn.execute(fc_query, args).fetchdf()
        for _, row in fc_df.iterrows():
            mape = row.get("test_mape")
            confidence = 0.5
            if mape is not None:
                try:
                    confidence = float(np.clip(1.0 - float(mape) / 100.0, 0.1, 1.0))
                except Exception:
                    confidence = 0.5
            particles.append(
                Particle(
                    id=f"fc:{row['commodity']}",
                    commodity=row["commodity"],
                    region="ALL",
                    prediction=confidence,
                    confidence=confidence,
                    significance=confidence * 0.8,
                    shap_values={},
                    model_version="prophet-ensemble",
                )
            )
    except Exception as e:  # pragma: no cover
        logger.warning("QVE: forecast_metrics read failed: %s", e)

    # 3) Freshness snapshot from prices → volume particles
    try:
        px_query = """
            SELECT commodity, COUNT(*) AS n_rows, COUNT(DISTINCT district) AS n_districts
            FROM prices
            GROUP BY commodity
            ORDER BY n_rows DESC, commodity ASC LIMIT ?
        """
        px_args: List = [limit]
        if commodity:
            px_query = """
                SELECT commodity, COUNT(*) AS n_rows, COUNT(DISTINCT district) AS n_districts
                FROM prices WHERE LOWER(commodity) = LOWER(?)
                GROUP BY commodity ORDER BY n_rows DESC, commodity ASC LIMIT ?
            """
            px_args = [commodity, limit]
        px_df = conn.execute(px_query, px_args).fetchdf()
        for _, row in px_df.iterrows():
            n = float(row["n_rows"] or 0)
            if n <= 0:
                continue
            particles.append(
                Particle(
                    id=f"px:{row['commodity']}",
                    commodity=row["commodity"],
                    region="ALL",
                    prediction=n,
                    confidence=0.5,
                    significance=float(np.clip(math.log10(n + 1) / 7.0, 0.05, 1.0)),
                    shap_values={},
                    model_version="prices-snapshot",
                )
            )
    except Exception as e:  # pragma: no cover
        logger.warning("QVE: prices snapshot failed: %s", e)

    # Deduplicate by id, keep first
    seen: set = set()
    uniq: List[Particle] = []
    for p in particles:
        if p.id in seen:
            continue
        seen.add(p.id)
        uniq.append(p)
    return uniq[:limit]


def compute_placement(
    conn,
    commodity: Optional[str] = None,
    limit: int = 60,
    n_iter: int = 4000,
    seed: Optional[int] = None,
) -> dict:
    """
    End-to-end QVE pipeline: build particles from DB → build QUBO → solve
    with simulated annealing → annotate particles with positions/energy.

    Returns a dict matching the QVE API contract:
        {
          "engine": "simulated-annealing",
          "n_particles": N,
          "energy": float,
          "schedule": {...},
          "wall_time_s": float,
          "particles": [particle.to_dict(), ...],
        }
    """
    particles = build_particles_from_db(conn, commodity=commodity, limit=limit)
    if not particles:
        return {
            "engine": "simulated-annealing",
            "n_particles": 0,
            "energy": 0.0,
            "schedule": {},
            "wall_time_s": 0.0,
            "particles": [],
            "warning": "No particles could be built (empty or missing tables).",
        }

    Q = build_qubo(particles)
    result = solve_placement_simulated_annealing(
        particles, Q, n_iter=n_iter, seed=seed, verbose=False
    )

    positions = result["positions"]
    total_energy = result["energy"]
    for idx, p in enumerate(particles):
        p.position = positions[idx]
        # Visual styling derived from significance & confidence
        sig = float(p.significance)
        conf = float(p.confidence)
        # Quantum glow palette: deep blue → cyan → gold by significance
        p.color = (
            round(0.15 + 0.5 * sig, 3),
            round(0.5 + 0.4 * conf, 3),
            round(1.0 - 0.3 * sig, 3),
        )
        p.glow = round(0.3 + 0.7 * sig, 3)
        p.size = round(0.6 + 1.6 * conf, 3)
        # Approximate per-particle energy share for diagnostics
        p.energy = round(total_energy * (sig + 0.1) / max(1.0, len(particles) * 0.5), 4)

    return {
        "engine": "simulated-annealing",
        "n_particles": len(particles),
        "energy": round(float(total_energy), 4),
        "schedule": result["schedule"],
        "wall_time_s": result["wall_time_s"],
        "particles": [p.to_dict() for p in particles],
    }
