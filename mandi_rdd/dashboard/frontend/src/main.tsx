import React from "react";
import ReactDOM from "react-dom/client";
import { Streamlit } from "streamlit-component-lib";
import FlipBoard from "./FlipBoard";
import WebGLHero from "./WebGLHero";
import type { KpiData } from "./FlipBoard";

/**
 * Entry point — Streamlit custom component wiring.
 *
 * FlipBoard receives KPI data from the Python backend via Streamlit
 * render events. The React tree persists across Streamlit script reruns,
 * so useRef values survive — this is why the flip animation lives here
 * and not in injected CSS.
 *
 * WebGLHero is statically imported (not code-split) because the
 * entire bundle is injected inline via theme.py's inject_webgl_hero()
 * as <script type="module">. Inline modules can't use relative
 * dynamic imports — they'd 404. All three/fiber/drei dependencies
 * are self-contained in one chunk.
 *
 * The bundle only loads on pages that have a
 * <div id="mandiq-webgl-hero-root"> (the Python injector creates this).
 * Low-end devices get a CSS gradient fallback with zero JS cost.
 */

const root = ReactDOM.createRoot(document.getElementById("root")!);

root.render(
  <React.StrictMode>
    <FlipBoardWithStreamlit />
  </React.StrictMode>,
);

// ── WebGL Hero auto-mount ──
// The inject_webgl_hero() Python function injects this bundle
// onto the main page along with a <div id="mandiq-webgl-hero-root">.
(function autoMountWebGLHero() {
  const heroRoot = document.getElementById("mandiq-webgl-hero-root");
  if (heroRoot && !heroRoot.dataset.mandiqHeroMounted) {
    heroRoot.dataset.mandiqHeroMounted = "true";
    const heroContainer = document.createElement("div");
    heroContainer.id = "mandiq-webgl-hero-container";
    heroRoot.appendChild(heroContainer);
    const heroReactRoot = ReactDOM.createRoot(heroContainer);
    heroReactRoot.render(React.createElement(WebGLHero));
  }
})();

import { ComponentProps } from "streamlit-component-lib";

type StreamlitArgs = { kpis?: KpiData } | undefined;

function FlipBoardWithStreamlit() {
  const [kpis, setKpis] = React.useState<KpiData | null>(null);

  React.useEffect(() => {
    function onRender(event: Event) {
      const detail = (event as CustomEvent<ComponentProps>).detail as {
        args?: StreamlitArgs;
      };
      if (detail?.args?.kpis) {
        setKpis(detail.args.kpis);
      }
    }

    Streamlit.events.addEventListener(
      Streamlit.RENDER_EVENT,
      onRender as EventListener
    );

    Streamlit.setComponentReady();

    return () => {
      Streamlit.events.removeEventListener(
        Streamlit.RENDER_EVENT,
        onRender as EventListener
      );
    };
  }, []);

  React.useEffect(() => {
    Streamlit.setFrameHeight();
  });

  if (!kpis) {
    return (
      <div
        style={{
          background: "#000000",
          fontFamily: "'IBM Plex Mono', monospace",
          color: "#7e7e7e",
          padding: "1.5rem 1rem",
          display: "flex",
          alignItems: "center",
          gap: "0.75rem",
          fontSize: "0.85rem",
          letterSpacing: "0.05em",
        }}
      >
        <span
          style={{
            display: "inline-block",
            width: 6,
            height: 6,
            background: "#d7ff00",
            borderRadius: 1,
            animation: "pulse-load 1.2s ease-in-out infinite",
          }}
        />
        <span>LOADING MARKET KPIs</span>
        <style>{`
          @keyframes pulse-load {
            0%, 100% { opacity: 0.3; transform: scale(1); }
            50% { opacity: 1; transform: scale(1.3); }
          }
        `}</style>
      </div>
    );
  }

  return <FlipBoard kpis={kpis} />;
}
