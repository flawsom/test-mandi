/**
 * MandiIQ Omega — QVE placement data provider.
 *
 * Fetches particle placement from the live backend:
 *   GET {apiBase}/qve/placement?commodity=&limit=&n_iter=&seed=
 *
 * The API base is injected into `window.__MANDIIQ_API_BASE__` by the Python
 * theme injector (theme.py → inject_quantum_field). A trusted fallback chain
 * keeps the dashboard rendering even if the backend is unreachable:
 *
 *   1. window.__MANDIIQ_API_BASE__ (injected by Python)
 *   2. a derived same-origin base
 *   3. deterministic procedural placement (offline-safe seed)
 */

import type {
  EntanglementEdge,
  FieldParticle,
  QvePlacementQuery,
  QvePlacementResponse,
} from "./types";

const TRUSTED_API_BASE =
  "https://p01--mandiiq--zbvjrztgjqgw.code.run";

/** Resolve the FastAPI base URL the same way theme.py does on the backend. */
export function resolveApiBase(): string {
  if (typeof window !== "undefined") {
    const injected =
      (window as unknown as { __MANDIIQ_API_BASE__?: string })
        .__MANDIIQ_API_BASE__;
    if (injected && injected.startsWith("http")) return injected;
  }
  return TRUSTED_API_BASE;
}

/** Build query string; only include non-default params to keep URLs slot for caching. */
function toQuery(q: QvePlacementQuery): string {
  const params = new URLSearchParams();
  if (q.commodity) params.set("commodity", q.commodity);
  if (q.limit && q.limit !== 60) params.set("limit", String(q.limit));
  if (q.n_iter && q.n_iter !== 4000) params.set("n_iter", String(q.n_iter));
  if (q.seed != null) params.set("seed", String(q.seed));
  return params.toString();
}

/** Deterministic PRNG so the offline fallback is stable across renders. */
function mulberry32(seed: number) {
  return function () {
    seed |= 0;
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const FALLBACK_COMMODITIES = [
  "Onion", "Tomato", "Wheat", "Potato", "Rice", "Pulses",
  "Soybean", "Cotton", "Maize", "Sugarcane",
];

const FALLBACK_REGIONS = [
  "Nasik", "Kurnool", "Pandharpur", "Agra", "Hapur",
  "Azadpur", "Vashi", "Indore", "Pimpalgaon", "Guntur",
];

/**
 * Deterministic procedural placement — used only when the API cannot be
 * reached, so the dashboard always has something meaningful to render.
 */
export function fallbackPlacement(query?: QvePlacementQuery): QvePlacementResponse {
  const limit = query?.limit ?? 40;
  const seed = query?.seed ?? 20240701;
  const rand = mulberry32(seed);
  const particles: FieldParticle[] = [];

  // QUBO-style radial spread: commodities pushed apart on a disc, regions vary
  // in elevation. Deterministic given seed.
  for (let i = 0; i < limit; i++) {
    const commodity = FALLBACK_COMMODITIES[i % FALLBACK_COMMODITIES.length];
    const region = FALLBACK_REGIONS[(i * 3) % FALLBACK_REGIONS.length];
    const angle = (i / limit) * Math.PI * 2 + rand() * 0.15;
    const radius = 2.5 + rand() * 2.0;
    const x = Math.cos(angle) * radius;
    const z = Math.sin(angle) * radius;
    const y = (rand() - 0.5) * 1.8;
    const confidence = 0.45 + rand() * 0.45;
    const glow = 0.6 + rand() * 0.9;
    particles.push({
      id: `${commodity.toLowerCase()}-${region.toLowerCase()}`,
      commodity,
      region,
      prediction: 1500 + rand() * 3000,
      confidence,
      position: [x, y, z],
      color: commodityColor(commodity),
      glow,
      size: 0.5 + rand() * 0.9,
    });
  }

  return {
    engine: "procedural-fallback",
    n_particles: limit,
    energy: 0,
    schedule: "none",
    wall_time_s: 0,
    particles: particles as unknown as QvePlacementResponse["particles"],
  };
}

/** Commodity-aware palette — falls back gracefully if the backend omitted a color. */
export function commodityColor(commodity: string): [number, number, number] {
  const id = commodity.toLowerCase();
  const hex = (
    id.includes("onion") || id.includes("kanda") ? "#8B6BC4" :
    id.includes("tomato") || id.includes("tamatar") ? "#D9663B" :
    id.includes("wheat") || id.includes("gehu") ? "#D4A94E" :
    id.includes("potato") || id.includes("aloo") ? "#B98354" :
    id.includes("rice") || id.includes("chawal") ? "#7BC46B" :
    id.includes("soybean") || id.includes("soya") ? "#6BBFC4" :
    id.includes("milk") ? "#4AA8C4" :
    "#d7ff00"
  );
  return [
    parseInt(hex.slice(1, 3), 16) / 255,
    parseInt(hex.slice(3, 5), 16) / 255,
    parseInt(hex.slice(5, 7), 16) / 255,
  ];
}

/**
 * Fetch QVE placement, normalising backend particles into the 3D scene's
 * FieldParticle shape. Throws on malformed payload so callers fall back.
 */
export async function fetchQvePlacement(
  query?: QvePlacementQuery,
  timeoutMs = 12000,
): Promise<QvePlacementResponse> {
  const base = resolveApiBase();
  const qs = toQuery(query ?? {});
  const url = `${base}/qve/placement${qs ? `?${qs}` : ""}`;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, { signal: controller.signal });
    if (!res.ok) throw new Error(`QVE placement ${res.status}`);
    const json: QvePlacementResponse = await res.json();
    if (!json || !Array.isArray(json.particles)) {
      throw new Error("Malformed QVE placement payload");
    }
    return json;
  } finally {
    clearTimeout(timer);
  }
}

/** Normalise a QVE placement into {particles, edges}. Entanglement edges are
 * derived from same-commodity tokens — commodities that co-occur in a cluster
 * are "related" and get a thread drawn between them by the scene.
 */
export function toField(
  response: QvePlacementResponse,
): { particles: FieldParticle[]; edges: EntanglementEdge[] } {
  const particles: FieldParticle[] = response.particles.map((p, i) => ({
    id: p.id || `${p.commodity}-${i}`,
    commodity: p.commodity,
    region: p.region,
    prediction: p.prediction,
    confidence: p.confidence,
    position: p.position ?? [0, 0, 0],
    color: p.color ?? commodityColor(p.commodity),
    glow: p.glow ?? 0.8,
    size: p.size ?? 0.6,
  }));

  // Entanglement: same commodity token across regions ⇒ related.
  const byCommodity = new Map<string, FieldParticle[]>();
  for (const p of particles) {
    const list = byCommodity.get(p.commodity) ?? [];
    list.push(p);
    byCommodity.set(p.commodity, list);
  }

  const edges: EntanglementEdge[] = [];
  for (const list of byCommodity.values()) {
    for (let i = 0; i < list.length; i++) {
      for (let j = i + 1; j < list.length; j++) {
        edges.push({
          source: list[i].id,
          target: list[j].id,
          correlation: Math.min(0.95, 0.4 + list[i].confidence * list[j].confidence),
        });
      }
    }
  }

  return { particles, edges };
}