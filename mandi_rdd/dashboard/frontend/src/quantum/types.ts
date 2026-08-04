/**
 * MandiIQ Omega — Quantum Visualization Engine · data contracts.
 *
 * Mirrors the QVE backend contract defined in
 *   mandi_rdd/omega/qve.py  (Particle.to_dict) and
 *   mandi_rdd/api/main.py    (GET /qve/placement).
 *
 * Keep these types in lockstep with the backend so the dashboard
 * stays wired to the live API.
 */

export interface QveParticle {
  id: string;
  commodity: string;
  region: string;
  date: string;
  prediction: number;
  confidence: number;
  significance: number;
  shap_values: Record<string, number>;
  model_version: string;
  /** [x, y, z] normalized placement from the simulated-annealing solver. */
  position: [number, number, number];
  /** residual energy of the QUBO term after placement. */
  energy: number;
  /** [r, g, b] in 0..1. */
  color: [number, number, number];
  /** emissive glow intensity — drives shader bloom. */
  glow: number;
  /** point size scalar. */
  size: number;
}

export interface QvePlacementResponse {
  engine: string;
  n_particles: number;
  energy: number;
  schedule: string;
  wall_time_s: number;
  particles: QveParticle[];
}

export interface QvePlacementQuery {
  commodity?: string;
  limit?: number;
  n_iter?: number;
  seed?: number;
}

/** Normalized particle view consumed by the 3D scene. */
export interface FieldParticle {
  id: string;
  commodity: string;
  region: string;
  prediction: number;
  confidence: number;
  position: [number, number, number];
  color: [number, number, number];
  glow: number;
  size: number;
}

/** Thread linking two particles that are quantum-entangled (related commodities). */
export interface EntanglementEdge {
  source: string;
  target: string;
  correlation: number;
}