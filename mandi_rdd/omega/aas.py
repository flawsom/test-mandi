"""MandiRDD — AAS: Adaptive Alert System (autonomous agent swarm).

Emulates a large BDI (Belief–Desire–Intention) agent swarm (up to ~10k agents)
operating over the QVE particle field. Agents are belief-driven observers of
the particle field; each instantiates a role-specific *desire* (surveillance,
mispricing, risk, integration) and emits a prioritized *intention* (alert +
action). The swarm is vectorised with NumPy so thousands of agents can be
evaluated in parallel without threads/processes.

Agent roles
-----------
* scout     — flags particles with high significance / anomalous energy.
* pricer    — flags likely-mispriced commodities (prediction vs confidence).
* sentinel  — flags low-confidence / high-risk particles.
* integrator— flags densely-populated market complexes (spatial consensus).

Emergent behaviour is measured via per-particle *consensus* (fraction of the
swarm voting for the same particle) and the entropy of the attention field.
"""

from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None  # type: ignore

# ──────────────────────────────────────────────────────────────────────
# Agent model
# ──────────────────────────────────────────────────────────────────────

ROLES: Dict[str, Dict[str, float]] = {
    "scout": {"frac": 0.30, "desire": 0.55, "weight": 1.00, "action": "escalate_for_surveillance"},
    "pricer": {"frac": 0.25, "desire": 0.55, "weight": 0.90, "action": "flag_mispricing"},
    "sentinel": {"frac": 0.25, "desire": 0.50, "weight": 0.95, "action": "issue_risk_warning"},
    "integrator": {"frac": 0.20, "desire": 0.45, "weight": 0.70, "action": "tag_market_complex"},
}


@dataclass
class Agent:
    """A single BDI agent in the swarm."""

    id: int
    role: str
    belief: Dict[str, object] = field(default_factory=dict)   # particle it observed
    desire: float = 0.5                                       # interest threshold
    intention: str = ""                                       # chosen action
    vote: int = 0                                             # 1 if it acted
    severity: float = 0.0                                     # 0..1


def _severity_label(sev: float) -> str:
    sev = max(0.0, min(1.0, float(sev)))
    if sev >= 0.75:
        return "critical"
    if sev >= 0.5:
        return "high"
    if sev >= 0.25:
        return "medium"
    return "low"


def run_agent_swarm(
    particles: Sequence[dict],
    n_agents: int = 2000,
    seed: Optional[int] = None,
    consensus_threshold: float = 0.06,
) -> dict:
    """Run a BDI agent swarm over serialised QVE particles.

    Args:
        particles: list of particle dicts (as returned by ``compute_placement``).
        n_agents:  number of agents to emulate (clamped to max 10000).
        seed:      RNG seed for reproducible swarms.
        consensus_threshold: min fraction of a role's agents required for an alert.

    Returns:
        dict with alerts, roles, emergent attention + swarm metadata.
    """
    if np is None:  # pragma: no cover
        raise RuntimeError("AAS requires numpy")

    start = time.time()
    rng = np.random.default_rng(seed)
    n_agents = max(8, min(10000, int(n_agents)))

    if not particles:
        return {
            "engine": "aas-bdi-swarm",
            "n_agents": n_agents,
            "roles": {r: 0 for r in ROLES},
            "n_alerts": 0,
            "alerts": [],
            "attention": {},
            "emergent": {"attention_entropy": 0.0, "consensus_ratio": 0.0},
            "wall_time_s": round(time.time() - start, 4),
        }

    n = len(particles)
    sig = np.asarray([float(p.get("significance", 0.5)) for p in particles], dtype=float)
    conf = np.asarray([float(p.get("confidence", 0.5)) for p in particles], dtype=float)
    pred = np.asarray(
        [float(p.get("prediction")) if p.get("prediction") is not None else 0.0 for p in particles],
        dtype=float,
    )
    energy = np.asarray([float(p.get("energy", 0.0)) for p in particles], dtype=float)
    pos = np.asarray(
        [
            [float(x) for x in p.get("position", (0.0, 0.0, 0.0))]
            for p in particles
        ],
        dtype=float,
    )

    # Local density (integrator desire): count of neighbours within radius.
    density = np.zeros(n, dtype=float)
    if n > 1:
        diff = pos[:, None, :] - pos[None, :, :]  # (n, n, 3)
        dist2 = np.einsum("nmd,nmd->nm", diff, diff)
        np.fill_diagonal(dist2, np.inf)
        density = np.mean(np.exp(-dist2 / 2.0), axis=1)

    # Normalise mispricing signal relative to the population.
    abs_pred = np.abs(pred)
    scale = float(np.median(abs_pred) + 1e-6)
    mispricing = np.tanh(abs_pred / scale) * conf
    risk = 1.0 - conf

    # Assemble role signals -> (n,) score per particle.
    role_signal: Dict[str, np.ndarray] = {
        "scout": sig + 0.5 * np.tanh(np.abs(energy)),       # significance + energy anomaly
        "pricer": mispricing,                                # |prediction| * confidence
        "sentinel": risk + 0.3 * (1.0 - sig),                # low confidence + low sig
        "integrator": density,                               # spatial consensus density
    }

    # ── Swarm population (vectorised) ────────────────────────────────
    counts: Dict[str, int] = {}
    role_ids: List[str] = []
    for role, cfg in ROLES.items():
        c = int(round(cfg["frac"] * n_agents))
        counts[role] = c
        role_ids.extend([role] * c)
    role_ids = (role_ids[:n_agents] + ["scout"])[:n_agents]
    role_arr = np.array(role_ids)

    # Agents observe a random particle (weighted toward high baseline).
    base = sig + conf
    prob = np.clip(base, 1e-6, None)
    prob = prob / prob.sum()

    n_samples = n_agents
    observed = rng.choice(n, size=n_samples, p=prob, replace=True)
    rng_jitter = rng.random(n_samples) * 0.25          # observer noise
    rng_act = rng.random(n_samples)

    votes = np.zeros((n_agents,), dtype=int)          # whether each agent acts
    severities = np.zeros((n_agents,), dtype=float)
    role_of_agent = role_arr

    for idx in range(n_agents):
        role = role_of_agent[idx]
        cfg = ROLES[role]
        s = float(role_signal[role][observed[idx]])
        interest = float(cfg["weight"]) * s * (0.8 + rng_jitter[idx])
        if interest >= cfg["desire"]:
            votes[idx] = 1
            severities[idx] = min(1.0, interest)

    # ── Aggregation: per-particle consensus per role ─────────────────
    alert_rows: List[dict] = []
    attention: Dict[str, float] = {}
    for i in range(n):
        pid = str(particles[i].get("id", i))
        commodity = str(particles[i].get("commodity", "unknown"))
        me = np.where(observed == i)[0]
        total_attention = 0.0
        for role in ROLES:
            members = me[role_of_agent[me] == role]
            c = len(members)
            if c == 0:
                continue
            role_votes = int(votes[members].sum())
            consensus = role_votes / c
            if consensus >= consensus_threshold:
                sev = max(severities[members][votes[members] == 1].tolist() or [0.0])
                alert_rows.append(
                    {
                        "particle_id": pid,
                        "commodity": commodity,
                        "role": role,
                        "severity": round(sev, 3),
                        "level": _severity_label(sev),
                        "consensus_ratio": round(consensus, 3),
                        "message": _role_message(role, commodity, sev),
                        "action": ROLES[role]["action"],
                    }
                )
            total_attention += role_votes
        if total_attention > 0:
            attention[commodity] = round(total_attention / n_agents, 4)

    # Emergent entropy of the attention field (0 = ordered, high = disordered).
    att_vals = np.asarray([attention.get(str(p.get("commodity")), 0.0) for p in particles])
    total_att = float(att_vals.sum())
    entropy = 0.0
    if total_att > 0:
        p = att_vals[att_vals > 0] / total_att
        entropy = float(-(p * np.log(p)).sum()) / math.log(max(2, n))
    consensus_ratio = float(votes.sum()) / n_agents

    alert_rows.sort(key=lambda a: a["severity"], reverse=True)
    return {
        "engine": "aas-bdi-swarm",
        "n_agents": n_agents,
        "roles": counts,
        "n_alerts": len(alert_rows),
        "alerts": alert_rows,
        "attention": attention,
        "emergent": {
            "attention_entropy": round(entropy, 4),
            "consensus_ratio": round(consensus_ratio, 4),
        },
        "wall_time_s": round(time.time() - start, 4),
    }


def _role_message(role: str, commodity: str, severity: float) -> str:
    msgs = {
        "scout": f"Significance anomaly flagged for {commodity} (severity {severity:.2f}).",
        "pricer": f"Likely mispricing detected for {commodity}; verify valuation (severity {severity:.2f}).",
        "sentinel": f"Elevated valuation risk for {commodity} due to low confidence (severity {severity:.2f}).",
        "integrator": f"{commodity} sits in a densely-coupled market complex; monitor co-movement (severity {severity:.2f}).",
    }
    return msgs.get(role, f"Agent alert for {commodity} (severity {severity:.2f}).")


def engine_status() -> dict:
    """Static capability report for the AAS module."""
    return {
        "engine": "aas-bdi-swarm",
        "model": "BDI agent swarm (belief-desire-intention)",
        "max_agents": 10000,
        "roles": list(ROLES.keys()),
        "emulated": True,
        "threadless": True,
        "description": "Vectorised swarm over the QVE particle field producing prioritized alerts.",
    }