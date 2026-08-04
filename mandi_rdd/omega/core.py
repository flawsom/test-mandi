"""MandiRDD — OMEGA Core: protocol orchestrator.

Coordinates the OMEGA PROTOCOL modules (QVE → AAS → EIC → CRSM-lite) into a
single pipeline, tracks each stage's availability and health, and emits a
cross-reality state-mesh snapshot (content-addressed hash of the fused state).

Pipeline (wave-2)
-----------------
1. QVE   — quantum-inspired particle placement (QUBO + simulated annealing).
2. AAS   — BDI agent swarm over the placed particle field → prioritized alerts.
3. EIC   — causal-discovery ensemble + meta-learning insights over price series.
4. CRSM  — (lite) content-addressed snapshot of the fused state mesh.

Degradation policy: a failing stage is recorded with ``error`` and the
pipeline still returns the remaining stages + ``degraded: True``.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Dict, Optional

logger = logging.getLogger(__name__)

from mandi_rdd.omega.qve import compute_placement as _qve_compute_placement
from mandi_rdd.omega.aas import engine_status as _aas_status
from mandi_rdd.omega.aas import run_agent_swarm
from mandi_rdd.omega.eic import engine_status as _eic_status
from mandi_rdd.omega.eic import generate_insights

PROTOCOL_VERSION = "wave-2"
MODULES = ("qve", "aas", "eic", "crsm")


class OmegaCore:
    """Registry + orchestrator for the OMEGA PROTOCOL modules."""

    def __init__(self, conn=None):
        self.conn = conn

    # ── Status ───────────────────────────────────────────────────────
    def module_status(self) -> dict:
        """Per-module availability + capability report."""
        status = {
            "protocol": "OMEGA",
            "version": PROTOCOL_VERSION,
            "dwave_emulated": True,  # D-Wave not available locally
            "modules": {},
            "healthy": True,
        }
        try:
            status["modules"]["qve"] = {"available": True, "engine": "simulated-annealing"}
        except Exception as e:  # pragma: no cover
            status["modules"]["qve"] = {"available": False, "error": str(e)}
            status["healthy"] = False
        for name, fn in (("aas", _aas_status), ("eic", _eic_status)):
            try:
                report = fn()
                status["modules"][name] = {"available": True, **report}
            except Exception as e:  # pragma: no cover
                status["modules"][name] = {"available": False, "error": str(e)}
                status["healthy"] = False
        status["modules"]["crsm"] = {
            "available": True,
            "engine": "cross-reality-state-mesh-lite",
            "description": "Content-addressed snapshot of the fused particle field.",
        }
        return status

    # ── Pipeline ─────────────────────────────────────────────────────
    def run_pipeline(
        self,
        limit: int = 60,
        n_iter: int = 4000,
        seed: Optional[int] = None,
        n_agents: int = 2000,
        max_lag: int = 3,
        top_k: int = 10,
    ) -> dict:
        """Run QVE → AAS → EIC and fuse the results into a state mesh."""
        start = time.time()
        if self.conn is None:
            raise ValueError("OmegaCore requires a database connection (conn).")

        stages: Dict[str, dict] = {}
        degraded = False

        # Stage 1 — QVE placement.
        try:
            stages["qve"] = _qve_compute_placement(
                self.conn, limit=int(limit), n_iter=int(n_iter), seed=seed
            )
        except Exception as e:  # pragma: no cover
            logger.exception("OMEGA pipeline: QVE stage failed")
            stages["qve"] = {"error": str(e), "n_particles": 0}
            degraded = True

        particles = stages["qve"].get("particles") or []

        # Stage 2 — AAS swarm over the placed particles.
        try:
            stages["aas"] = run_agent_swarm(particles, n_agents=int(n_agents), seed=seed)
        except Exception as e:  # pragma: no cover
            logger.exception("OMEGA pipeline: AAS stage failed")
            stages["aas"] = {"error": str(e), "n_alerts": 0}
            degraded = True

        # Stage 3 — EIC insights.
        try:
            stages["eic"] = generate_insights(
                self.conn, limit=int(limit), max_lag=int(max_lag), top_k=int(top_k)
            )
        except Exception as e:  # pragma: no cover
            logger.exception("OMEGA pipeline: EIC stage failed")
            stages["eic"] = {"error": str(e), "n_insights": 0}
            degraded = True

        # Stage 4 — CRSM-lite state mesh snapshot.
        state_mesh = self.snapshot(stages)
        result = {
            "protocol": "OMEGA",
            "version": PROTOCOL_VERSION,
            "stages": stages,
            "state_mesh": state_mesh,
            "degraded": degraded,
            "wall_time_s": round(time.time() - start, 4),
        }
        # Fuse the operator summary at top level so every caller (API, CLI,
        # dashboard, tests) sees the same headline contract.
        result.update(pipeline_status_summary(result))
        return result

    def snapshot(self, stages: Dict[str, dict]) -> dict:
        """Content-addressed state mesh snapshot (CRSM-lite)."""
        digest_src = json.dumps(
            {"qve": stages.get("qve", {}).get("n_particles", 0), "aas": stages.get("aas", {}).get("n_alerts", 0),
             "eic": stages.get("eic", {}).get("n_edges", 0)},
            sort_keys=True,
        )
        state_hash = hashlib.sha256(digest_src.encode("utf-8")).hexdigest()[:16]
        return {
            "engine": "crsm-lite",
            "hash": state_hash,
            "n_entities": stages.get("qve", {}).get("n_particles", 0),
            "n_alerts": stages.get("aas", {}).get("n_alerts", 0),
            "n_insights": stages.get("eic", {}).get("n_insights", 0),
            "converged": not stages.get("qve", {}).get("warning"),
        }


def pipeline_status_summary(result: dict) -> dict:
    """Compact health summary for operators."""
    stages = result.get("stages", {})
    return {
        "protocol": result.get("protocol"),
        "version": result.get("version"),
        "degraded": result.get("degraded", True),
        "n_particles": stages.get("qve", {}).get("n_particles", 0),
        "n_alerts": stages.get("aas", {}).get("n_alerts", 0),
        "n_edges": stages.get("eic", {}).get("n_edges", 0),
        "state_hash": result.get("state_mesh", {}).get("hash"),
        "wall_time_s": result.get("wall_time_s", 0.0),
    }