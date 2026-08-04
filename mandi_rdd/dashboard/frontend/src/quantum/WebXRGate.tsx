/**
 * MandiIQ Omega — WebXR scaffold gate.
 *
 * WebXR-ready groundwork for the "holographic commodity field" experience.
 * Fully feature-detected:
 *   • If WebXR (immersive-vr) is unavailable, nothing renders — classic 2D
 *     dashboard is untouched.
 *   • If available, a small glass button appears; clicking it requests an
 *     immersive session on the nearest <canvas> and hands the render loop to
 *     three's WebXRManager.
 *
 * The scene itself is XR-ready: additive-blended glow, no DOM-coupled controls
 * inside the session, camera rig replaced by the XR pose. When the session
 * ends the button re-appears.
 *
 * This keeps the bundle dependency-light (no @react-three/xr) while leaving a
 * clear seam to upgrade to full hand/controller tracking later.
 */

import React, { useEffect, useRef, useState } from "react";

type XRSystemLike = {
  isSessionSupported: (mode: string) => Promise<boolean>;
  requestSession: (
    mode: string,
    options?: { optionalFeatures?: string[] },
  ) => Promise<unknown>;
};

type XRManagerLike = {
  enabled: boolean;
  setReferenceSpaceType: (t: string) => void;
  setSession: (s: unknown) => Promise<void>;
  isPresenting: boolean;
};

interface RendererWithXR {
  xr: XRManagerLike;
  domElement: HTMLCanvasElement;
}

function getXrGlobals(): {
  xr?: XRSystemLike;
  navigatorLike: Navigator;
} {
  const nav = window.navigator as Navigator & { xr?: XRSystemLike };
  return { xr: nav.xr, navigatorLike: nav };
}

/** Find the R3F canvas inside the widget root (the WebGL renderer's DOM). */
function findRenderer(): RendererWithXR | null {
  const canvases = document.querySelectorAll<HTMLCanvasElement>(
    "#mandiq-quantum-field-root canvas",
  );
  for (const canvas of canvases) {
    // three sets __r3f on the canvas via fiber's store; fall back to property
    const maybe = (canvas as HTMLCanvasElement & {
      __r3f?: { gl?: RendererWithXR };
    }).__r3f;
    if (maybe?.gl?.xr) return maybe.gl;
  }
  return null;
}

const BTN_STYLE: React.CSSProperties = {
  position: "absolute",
  top: 14,
  right: 14,
  zIndex: 3,
  fontFamily: "IBM Plex Mono, monospace",
  fontSize: 11,
  letterSpacing: "0.12em",
  textTransform: "uppercase",
  color: "#d7ff00",
  background: "rgba(5, 4, 10, 0.72)",
  border: "1px solid rgba(215, 255, 0, 0.4)",
  borderRadius: 2,
  padding: "6px 12px",
  cursor: "pointer",
  backdropFilter: "blur(6px)",
  transition: "opacity 0.25s ease",
};

export function WebXRGate() {
  const [supported, setSupported] = useState(false);
  const [entering, setEntering] = useState(false);
  const [presenting, setPresenting] = useState(false);
  const sessionRef = useRef<unknown>(null);
  const sessionEndHandler = useRef<(() => void) | null>(null);

  // Feature-detect once per mount.
  useEffect(() => {
    const { xr } = getXrGlobals();
    if (!xr) return;
    let alive = true;
    xr.isSessionSupported("immersive-vr")
      .then((ok) => {
        if (alive) setSupported(Boolean(ok));
      })
      .catch(() => {
        if (alive) setSupported(false);
      });
    return () => {
      alive = false;
    };
  }, []);

  // Cleanup session end listener on unmount.
  useEffect(() => {
    return () => {
      if (sessionEndHandler.current) {
        const s = sessionRef.current as { removeEventListener?: (t: string, h: () => void) => void } | null;
        s?.removeEventListener?.("end", sessionEndHandler.current);
      }
    };
  }, []);

  const enterXR = async () => {
    const { xr } = getXrGlobals();
    const renderer = findRenderer();
    if (!xr || !renderer) return;
    setEntering(true);
    try {
      const session = await xr.requestSession("immersive-vr", {
        optionalFeatures: ["local-floor", "bounded-floor"],
      });
      sessionRef.current = session;
      renderer.xr.enabled = true;
      renderer.xr.setReferenceSpaceType("local-floor");
      const end = () => {
        setPresenting(false);
        sessionEndHandler.current = null;
      };
      sessionEndHandler.current = end;
      (session as { addEventListener?: (t: string, h: () => void) => void })
        .addEventListener?.("end", end);
      await renderer.xr.setSession(session);
      setPresenting(true);
    } catch {
      // user cancelled or request failed → stay on 2D
    } finally {
      setEntering(false);
    }
  };

  if (!supported) return null;

  return (
    <button
      type="button"
      style={BTN_STYLE}
      onClick={enterXR}
      disabled={entering}
      aria-label="Enter virtual reality"
    >
      {entering ? "ENTERING…" : presenting ? "IN VR" : "ENTER VR"}
    </button>
  );
}