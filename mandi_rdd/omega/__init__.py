"""
MandiIQ Omega — post-human agricultural intelligence layer.

Implements the OMEGA PROTOCOL modules on top of the classical MandiRDD
pipeline, with hardware-aspirational features emulated in software:

- QVE  Quantum Valuation Engine  — QUBO + simulated annealing for optimal
      particle placement (emulates D-Wave quantum annealing locally).
- AAS  Adaptive Alert System      — BDI agent swarm over the particle field
      (emulates a 10k-agent autonomous swarm).
- EIC  Explainable Intelligence   — causal discovery ensemble + meta-learning
      insight generator (emulates the Emergent Intelligence Core).
- CRSM Cross-Reality State Mesh   — CRDT-style state layer (yjs-style) so
      web/VR/IoT views converge on the same particle field.

Each module is importable standalone and degrades gracefully when its
optional dependencies are absent.
"""

from mandi_rdd.omega.qve import (
    Particle,
    build_particles_from_db,
    build_qubo,
    solve_placement_simulated_annealing,
    compute_placement,
)
from mandi_rdd.omega.aas import (
    Agent,
    run_agent_swarm,
    engine_status as aas_engine_status,
)
from mandi_rdd.omega.eic import (
    load_price_matrix,
    causal_discovery,
    generate_insights,
    engine_status as eic_engine_status,
)
from mandi_rdd.omega.core import (
    OmegaCore,
    pipeline_status_summary,
)

__all__ = [
    "Particle",
    "build_particles_from_db",
    "build_qubo",
    "solve_placement_simulated_annealing",
    "compute_placement",
    "Agent",
    "run_agent_swarm",
    "aas_engine_status",
    "load_price_matrix",
    "causal_discovery",
    "generate_insights",
    "eic_engine_status",
    "OmegaCore",
    "pipeline_status_summary",
]
