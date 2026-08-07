/**
 * MandiIQ Omega — QVE placement data provider.
 *
 * Fetches particle placement from the live backend:
 *   GET {apiBase}/qve/placement?commodity=&limit=&n_iter=&seed=
 *
 * The API base is injected into `window.__MANDIIQ_API_BASE__` by the Python
 * theme injector (theme.py → inject_quantum_field). A derived same-origin
 * base is a backup.
 *
 * IMPORTANT: this provider NEVER fabricates QVE data. If the backend is
 * unreachable, `fetchQvePlacement` rejects and the caller renders an honest
 * empty/degraded state. No synthetic particles are ever injected — a field
 * showing particles is always backed by live API responses.
 */

import type {
  EntanglementEdge,
  FieldParticle,
  QvePlacementQuery,
  QvePlacementResponse,
} from "./types";

const TRUSTED_API_BASE =
  "https://test-mandi.vercel.app";

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

/** Commodity-aware palette — cosmetic only; never injects numeric predictions. */
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
 * Fetch QVE placement from the live backend. Throws on any failure or a
 * malformed payload so the caller renders an honest degraded/empty state
 * rather than fabricated numbers.
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