import React, { useRef, useEffect, useMemo } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { Float } from "@react-three/drei";
import * as THREE from "three";

/* ═══════════════════════════════════════════════════════════
   MandiIQ WebGL Hero — Alche Studio-inspired 3D particle field.

   Procedural particle field with:
   - @react-three/fiber Canvas + PointsGeometry
   - Lime-green (#d7ff00) glow with AdditiveBlending
   - Slow auto-rotation (y: 0.08 rad/s, x: 0.03 rad/s)
   - Device capability detection (low-end → CSS gradient fallback)
   - IntersectionObserver lazy-load (200px margin)
   - Auto-pause on tab hide (visibilitychange)
   ═══════════════════════════════════════════════════════════ */

const LIME = "#d7ff00";
const PARTICLE_COUNT_HIGH = 2000;
const PARTICLE_COUNT_LOW = 80;

// ── Procedural particle field mesh ──

interface ParticleFieldProps {
  count: number;
  isLowEnd: boolean;
}

function ParticleField({ count, isLowEnd }: ParticleFieldProps) {
  const mesh = useRef<THREE.Points>(null!);

  // Stable random positions — generated once via useMemo
  const positions = useMemo(() => {
    const pos = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      // Scatter in a wider volume for 2000+ particles (avoids clumping)
      pos[i * 3]     = (Math.random() - 0.5) * 24;
      pos[i * 3 + 1] = (Math.random() - 0.5) * 14;
      pos[i * 3 + 2] = (Math.random() - 0.5) * 10;
    }
    return pos;
  }, [count]);

  // Slow drift rotation — runs every frame
  useFrame((_, delta) => {
    if (mesh.current) {
      mesh.current.rotation.y += delta * 0.08;
      mesh.current.rotation.x += delta * 0.03;
    }
  });

  return (
    <Float speed={0.8} floatIntensity={0.4} rotationIntensity={0.1}>
      <points ref={mesh}>
        <bufferGeometry>
          <bufferAttribute
            attach="attributes-position"
            count={count}
            array={positions}
            itemSize={3}
          />
        </bufferGeometry>
        <pointsMaterial
          size={isLowEnd ? 0.05 : 0.02}
          color={LIME}
          transparent
          opacity={0.8}
          blending={THREE.AdditiveBlending}
          sizeAttenuation
          depthWrite={false}
        />
      </points>
    </Float>
  );
}

// ── CSS gradient fallback component (for low-end devices or before load) ──

function GradientFallback() {
  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: -1,
        pointerEvents: "none",
        background:
          "radial-gradient(ellipse at 30% 30%, rgba(215,255,0,0.04) 0%, transparent 60%)," +
          "radial-gradient(ellipse at 70% 80%, rgba(215,255,0,0.02) 0%, transparent 50%)",
      }}
    />
  );
}

// ── Main WebGL Hero component ──

export default function WebGLHero() {
  // ── Device capability detection ──
  const isLowEnd = useMemo(() => {
    if (typeof navigator === "undefined") return false;
    const cores = navigator.hardwareConcurrency || 4;
    const mem = (navigator as any).deviceMemory ?? 8;
    return cores <= 2 || mem <= 2;
  }, []);

  // ── IntersectionObserver lazy-load ──
  const [shouldRender, setShouldRender] = React.useState(false);

  useEffect(() => {
    // Mount monitoring — find the root div (injected by Python on the main page)
    const rootEl = document.getElementById("mandiq-webgl-hero-root");
    if (!rootEl) {
      // No root found (component rendered without inject_webgl_hero) — still render
      setShouldRender(true);
      return;
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setShouldRender(true);
          observer.unobserve(entry.target);
        }
      },
      { rootMargin: "300px" } // Start loading 300px before visible
    );
    observer.observe(rootEl);
    return () => observer.disconnect();
  }, []);

  // ── Auto-pause on tab hide ──
  const [paused, setPaused] = React.useState(false);
  useEffect(() => {
    const handleVisibility = () => setPaused(document.hidden);
    document.addEventListener("visibilitychange", handleVisibility);
    return () => document.removeEventListener("visibilitychange", handleVisibility);
  }, []);

  // ── Render ──

  // Low-end devices: CSS gradient only
  if (isLowEnd) {
    return <GradientFallback />;
  }

  // Before IntersectionObserver fires: show gradient placeholder
  if (!shouldRender) {
    return <GradientFallback />;
  }

  // Full 3D particle field
  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: -1,
        pointerEvents: "none",
      }}
    >
      <Canvas
        camera={{ position: [0, 1, 10], fov: 65, near: 0.1, far: 100 }}
        dpr={[1, 2]}
        gl={{
          alpha: true,
          antialias: true,
          powerPreference: "low-power",
        }}
        style={{ background: "transparent", width: "100%", height: "100%" }}
      >
        {paused ? null : (
          <ParticleField count={PARTICLE_COUNT_HIGH} isLowEnd={false} />
        )}
      </Canvas>
    </div>
  );
}
