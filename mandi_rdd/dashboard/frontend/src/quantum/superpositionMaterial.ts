/**
 * MandiIQ Omega — superposition cloud ShaderMaterial.
 *
 * Renders every commodity/region prediction as a fuzzy probability cloud
 * (Gaussian falloff, additive blend) instead of a hard point. The "observer
 * effect" is a per-particle `collapse` attribute (0..1) animated by the scene:
 *   collapse 0  → wide, faint superposition cloud (uncertainty visible)
 *   collapse 1  → tight, bright core (measured / observed state)
 *
 * GLSL kept dependency-free — compiles on WebGL1/2 (GLSL ES 1.00).
 */

import * as THREE from "three";

export const superpositionVertexShader = /* glsl */ `
  attribute vec3 aColor;
  attribute float aGlow;
  attribute float aSize;
  attribute float aCollapse;
  uniform float uPixelRatio;
  uniform float uTime;
  varying vec3 vColor;
  varying float vGlow;
  varying float vCollapse;
  varying float vAlpha;

  void main() {
    vColor = aColor;
    vGlow = aGlow;
    vCollapse = aCollapse;

    // collapse = 1 sharpens the sprite → superposition collapses to a point
    float sigma = mix(1.6, 0.45, aCollapse);
    float flicker = 0.94 + 0.12 * sin(uTime * 1.4 + aCollapse * 40.0 + aGlow * 7.0);
    float size = aSize * flicker * sigma * uPixelRatio;
    vec4 mv = modelViewMatrix * vec4(position, 1.0);
    gl_PointSize = size * (300.0 / max(0.1, -mv.z));
    gl_Position = projectionMatrix * mv;

    // fades the cloud out as it collapses — the core replaces it
    vAlpha = mix(0.55, 1.0, aCollapse);
  }
`;

export const superpositionFragmentShader = /* glsl */ `
  precision mediump float;
  uniform vec3 uAccent;
  varying vec3 vColor;
  varying float vGlow;
  varying float vCollapse;
  varying float vAlpha;

  void main() {
    // Gaussian probability distribution of the particle's position
    vec2 p = gl_PointCoord - 0.5;
    float r2 = dot(p, p);
    float sigma2 = mix(0.30, 0.10, vCollapse); // cloud → core
    float prob = exp(-r2 / (2.0 * sigma2));
    prob = smoothstep(0.0, 1.0, prob);

    vec3 color = vColor * (1.0 + vGlow * 0.6) + uAccent * vGlow * 0.25;
    float intensity = prob * vAlpha * (0.6 + vGlow * 0.8);
    gl_FragColor = vec4(color * intensity, intensity);
  }
`;

export interface SuperpositionMaterialParams {
  color?: [number, number, number];
}

/**
 * Factory — builds the ShaderMaterial. Use `material.uniforms.uTime` from
 * useFrame to keep the clouds alive.
 */
export function createSuperpositionMaterial(
  params: SuperpositionMaterialParams = {},
): THREE.ShaderMaterial {
  const accent = params.color ?? [0.84, 1.0, 0.0]; // #d7ff00 lime
  return new THREE.ShaderMaterial({
    vertexShader: superpositionVertexShader,
    fragmentShader: superpositionFragmentShader,
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
    uniforms: {
      uTime: { value: 0 },
      uPixelRatio: { value: Math.min(window.devicePixelRatio || 1, 2) },
      uAccent: { value: new THREE.Color(accent[0], accent[1], accent[2]) },
    },
  });
}