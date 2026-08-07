/**
 * MandiIQ Omega — 3D quantum particle field.
 *
 * A Three.js / React-Three-Fiber universe where every particle is a
 * commodity/region price prediction placed by the QVE solver (QUBO /
 * simulated annealing). Features:
 *
 *   • Superposition cloud per particle (custom GLSL Gaussian sprite)
 *   • Observer effect — hover/select collapses the cloud to a tight core
 *   • Entanglement threads between related commodities
 *   • WebXR-ready scaffold (feature-detected; safe on classic 2D)
 *   • Auto-rotation + OrbitControls for the dashboard view
 *
 * Integration: rendered by main.tsx into #mandiq-quantum-field-root (added by
 * theme.py → inject_quantum_field). Data comes from the QVE backend, with a
 * deterministic offline fallback that keeps the dashboard alive when the API
 * is unreachable.
 */

import React, { useEffect, useMemo, useRef, useState } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import * as THREE from "three";

import {
  fetchQvePlacement,
  toField,
} from "./dataProvider";
import { EntanglementThreads } from "./EntanglementThreads";
import { createSuperpositionMaterial } from "./superpositionMaterial";
import type { FieldParticle, QvePlacementResponse } from "./types";
import { WebXRGate } from "./WebXRGate";

const LIME = "#d7ff00";
const MAX_PARTICLES = 120;

/* ---------------------------------------------------------------------------
 * Particle layer: one <points> object, superposition material, per-particle
 * collapse attribute driven by hover (observer effect).
 * ------------------------------------------------------------------------- */

function SuperpositionField({ particles }: { particles: FieldParticle[] }) {
  const pointsRef = useRef<THREE.Points>(null);
  const material = useMemo(() => createSuperpositionMaterial(), []);

  const { positions, colors, glows, sizes } = useMemo(() => {
    const n = Math.min(particles.length, MAX_PARTICLES);
    const positions = new Float32Array(n * 3);
    const colors = new Float32Array(n * 3);
    const glows = new Float32Array(n);
    const sizes = new Float32Array(n);
    for (let i = 0; i < n; i++) {
      const p = particles[i];
      positions[i * 3 + 0] = p.position[0];
      positions[i * 3 + 1] = p.position[1];
      positions[i * 3 + 2] = p.position[2];
      const c = p.color;
      colors[i * 3 + 0] = c[0];
      colors[i * 3 + 1] = c[1];
      colors[i * 3 + 2] = c[2];
      glows[i] = p.glow;
      sizes[i] = p.size;
    }
    return { positions, colors, glows, sizes };
  }, [particles]);

  const collapse = useMemo(() => new Float32Array(MAX_PARTICLES), []);

  // animate collapse toward its target (breathing cloud at 0; solid at 1)
  useFrame((_, delta) => {
    material.uniforms.uTime.value += delta;
    if (!pointsRef.current) return;
    const attr = pointsRef.current.geometry
      .attributes.aCollapse as THREE.BufferAttribute;
    let needsUpdate = false;
    for (let i = 0; i < collapse.length; i++) {
      const cur = attr.array[i] as number;
      const next = cur + (collapse[i] - cur) * Math.min(1, delta * 8);
      if (Math.abs(next - cur) > 1e-4) needsUpdate = true;
      attr.array[i] = next;
    }
    if (needsUpdate) attr.needsUpdate = true;
  });

  const setCollapsed = (index: number | null) => {
    collapse.fill(0);
    if (index != null) collapse[index] = 1;
  };

  const geometry = useMemo(() => {
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    geo.setAttribute("aColor", new THREE.BufferAttribute(colors, 3));
    geo.setAttribute("aGlow", new THREE.BufferAttribute(glows, 1));
    geo.setAttribute("aSize", new THREE.BufferAttribute(sizes, 1));
    geo.setAttribute("aCollapse", new THREE.BufferAttribute(collapse, 1));
    return geo;
  }, [positions, colors, glows, sizes, collapse]);

  return (
    <group>
      <points ref={pointsRef} geometry={geometry} material={material} frustumCulled={false} />
      {/* invisible hit volumes so R3F pointer raycast can pick a particle index */}
      {particles.slice(0, MAX_PARTICLES).map((p, i) => (
        <mesh
          key={p.id}
          position={p.position}
          onPointerMove={() => setCollapsed(i)}
          onPointerOut={() => setCollapsed(null)}
        >
          <sphereGeometry args={[0.3, 6, 6]} />
          <meshBasicMaterial transparent opacity={0} depthWrite={false} />
        </mesh>
      ))}
    </group>
  );
}

/* ---------------------------------------------------------------------------
 * Auto-rotating camera rig (disabled under reduced-motion).
 * ------------------------------------------------------------------------- */

function Rig({ reducedMotion }: { reducedMotion: boolean }) {
  const { camera } = useThree();
  useFrame(({ clock }) => {
    if (reducedMotion) return;
    const t = clock.getElapsedTime() * 0.06;
    camera.position.x = Math.sin(t) * 7.5;
    camera.position.z = Math.cos(t) * 7.5;
    camera.lookAt(0, 0, 0);
  });
  return null;
}

/* ---------------------------------------------------------------------------
 * Main view
 * ------------------------------------------------------------------------- */

export interface QuantumFieldProps {
  commodity?: string;
  limit?: number;
  seed?: number;
  /** Render as full interactive dashboard view (vs. ambient background). */
  interactive?: boolean;
}

export function QuantumField({
  commodity,
  limit = 60,
  seed = 20240701,
  interactive = true,
}: QuantumFieldProps) {
  const [response, setResponse] = useState<QvePlacementResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [offline, setOffline] = useState(false);

  const reducedMotion = useMemo(
    () =>
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches,
    [],
  );

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setOffline(false);

    fetchQvePlacement({ commodity, limit, seed })
      .then((res) => {
        if (!alive) return;
        setResponse(res);
      })
      .catch(() => {
        if (!alive) return;
        // Honest degraded state: backend unreachable → no fabricated particles.
        // The field renders empty and labels the outage; the user sees live
        // data whenever the API is reachable, never invented numbers.
        setResponse(null);
        setOffline(true);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });

    return () => {
      alive = false;
    };
  }, [commodity, limit, seed]);

  const { particles, edges } = useMemo(() => {
    if (!response) return { particles: [] as FieldParticle[], edges: [] };
    return toField(response);
  }, [response]);

  return (
    <div
      className="qf-canvas-shell"
      style={{ position: "relative", width: "100%", height: "520px" }}
    >
      <Canvas
        dpr={[1, 2]}
        gl={{
          antialias: true,
          alpha: true,
          powerPreference: "high-performance",
        }}
        camera={{ position: [0, 2.5, 8.5], fov: 55, near: 0.1, far: 100 }}
        frameloop="always"
      >
        <color attach="background" args={["#05040a"]} />
        <fog attach="fog" args={["#05040a", 9, 18]} />

        {particles.length > 0 && <SuperpositionField particles={particles} />}
        <EntanglementThreads particles={particles} edges={edges} />

        <Rig reducedMotion={reducedMotion} />

        {interactive && (
          <OrbitControls
            enableDamping
            dampingFactor={0.08}
            minDistance={3}
            maxDistance={18}
            makeDefault
          />
        )}
      </Canvas>

      <WebXRGate />

      {/* HUD */}
      <div className="qf-hud" style={hudStyle}>
        <span style={{ color: LIME, fontFamily: "IBM Plex Mono, monospace", fontSize: 12 }}>
          {loading
            ? "COMPUTING…"
            : offline
              ? "QVE UNAVAILABLE"
              : `QVE ${response ? response.engine : ""}`.trim()}
        </span>
        <span style={{ color: "#9ca3af", fontFamily: "IBM Plex Mono, monospace", fontSize: 11 }}>
          {particles.length} particles · {edges.length} entanglements
        </span>
        <span style={{ color: "#9ca3af", fontFamily: "IBM Plex Mono, monospace", fontSize: 10 }}>
          hover a particle to observe · drag to orbit · scroll to zoom
        </span>
      </div>
    </div>
  );
}

const hudStyle: React.CSSProperties = {
  position: "absolute",
  left: 14,
  bottom: 14,
  display: "flex",
  flexDirection: "column",
  gap: 2,
  pointerEvents: "none",
  zIndex: 2,
};