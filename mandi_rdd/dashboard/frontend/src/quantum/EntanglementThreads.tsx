/**
 * MandiIQ Omega — entanglement threads.
 *
 * Curved, additive-blended "lines of constant phase" connecting related
 * commodities that are quantum-entangled (the same commodity token across
 * regions, or correlated SHAP edges from the backend). Pulse animation keeps
 * them feeling alive; they glow brighter as correlation rises.
 */

import React, { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";

import type { EntanglementEdge, FieldParticle } from "./types";

const LIME = new THREE.Color("#d7ff00");

function buildCurve(
  a: [number, number, number],
  m: [number, number, number],
  b: [number, number, number],
  segments: number,
): THREE.BufferGeometry {
  const points: THREE.Vector3[] = [];
  for (let i = 0; i <= segments; i++) {
    const t = i / segments;
    // quadratic bezier P = (1-t)^2 A + 2(1-t)t M + t^2 B
    const x = (1 - t) * (1 - t) * a[0] + 2 * (1 - t) * t * m[0] + t * t * b[0];
    const y = (1 - t) * (1 - t) * a[1] + 2 * (1 - t) * t * m[1] + t * t * b[1];
    const z = (1 - t) * (1 - t) * a[2] + 2 * (1 - t) * t * m[2] + t * t * b[2];
    points.push(new THREE.Vector3(x, y, z));
  }
  const geo = new THREE.BufferGeometry().setFromPoints(points);
  return geo;
}

interface ThreadProps {
  from: [number, number, number];
  to: [number, number, number];
  correlation: number;
  clock: React.MutableRefObject<number>;
}

function Thread({ from, to, correlation, clock }: ThreadProps) {
  const material = useMemo(
    () =>
      new THREE.LineBasicMaterial({
        color: LIME,
        transparent: true,
        opacity: 0.5,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
      }),
    [],
  );
  const line = useMemo(() => {
    const mid: [number, number, number] = [
      (from[0] + to[0]) / 2,
      (from[1] + to[1]) / 2 + 0.4 + correlation * 0.8,
      (from[2] + to[2]) / 2,
    ];
    const geo = buildCurve(from, mid, to, 24);
    const l = new THREE.Line(geo, material);
    l.frustumCulled = false;
    return l;
  }, [from, to, correlation, material]);

  useFrame(() => {
    // gentle phase pulse — entangled threads breathe together
    material.opacity =
      0.3 + 0.3 * (0.5 + 0.5 * Math.sin(clock.current * 0.7 + correlation * 6.0));
  });

  return <primitive object={line} />;
}

interface EntanglementThreadsProps {
  particles: FieldParticle[];
  edges: EntanglementEdge[];
}

export function EntanglementThreads({ particles, edges }: EntanglementThreadsProps) {
  const byId = useMemo(() => {
    const m = new Map<string, FieldParticle>();
    for (const p of particles) m.set(p.id, p);
    return m;
  }, [particles]);

  const clock = useRef(0);

  useFrame((_, delta) => {
    clock.current += delta;
  });

  if (edges.length === 0) return null;

  return (
    <group>
      {edges.map((edge, i) => {
        const a = byId.get(edge.source);
        const b = byId.get(edge.target);
        if (!a || !b) return null;
        return (
          <Thread
            key={`${edge.source}->${edge.target}`}
            from={a.position}
            to={b.position}
            correlation={edge.correlation}
            clock={clock}
          />
        );
      })}
    </group>
  );
}