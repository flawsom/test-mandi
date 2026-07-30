import React, { useRef, useEffect, useMemo, useState } from "react";
import { Streamlit } from "streamlit-component-lib";

/* ═══════════════════════════════════════════════════════════
   MandiIQ Flip-Board KPI Hero — Alche Studio Design Refined.

   Pure black canvas · Lime (#d7ff00) single accent
   Glass cards · Crosshair corner markers on hover
   Count-up on page load (800ms) · Flip-digit on value change
   ═══════════════════════════════════════════════════════════ */

export interface KpiItem {
  label: string;
  value: string;
  raw: number | null;
  prefix?: string;
  suffix?: string;
}

export interface KpiData {
  effect: KpiItem;
  avg_price: KpiItem;
  districts: KpiItem;
  mape: KpiItem;
}

// Alche-inspired palette
const COLORS = {
  bg: "#000000",
  surface: "#0a0a0a",
  glass: "rgba(255,255,255,0.03)",
  glassHover: "rgba(255,255,255,0.06)",
  primary: "#d7ff00",
  paper: "#ffffff",
  textHigh: "#bababa",
  textMed: "#7e7e7e",
  textLow: "#555555",
  rust: "#D9663B",
  sage: "#8FAE89",
  hairline: "rgba(255,255,255,0.07)",
  hairlineStrong: "rgba(255,255,255,0.14)",
};

const STAGGER_MS = 40;
const FLIP_DURATION_MS = 300;
const COUNTUP_DURATION_MS = 800;
const CARD_STAGGER_MS = 80;  // cascade each card in 80ms apart
const CARD_ENTRY_DURATION_MS = 400; // fade+slide per card

function formatDigitString(value: string): string[] {
  return value.split("");
}

function easeOutCubic(t: number): number {
  return 1 - Math.pow(1 - t, 3);
}

/** Format a number for display: add commas, round for large, decimals for small. */
function formatInterpValue(raw: number): string {
  if (Math.abs(raw) >= 100) {
    return Math.round(raw).toLocaleString("en-US");
  } else if (Math.abs(raw) >= 1) {
    return raw.toLocaleString("en-US", {
      minimumFractionDigits: 1,
      maximumFractionDigits: 1,
    });
  } else {
    return raw.toLocaleString("en-US", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  }
}

// ── Single digit cell with flip animation ──

interface DigitCellProps {
  char: string;
  isFlipping: boolean;
  staggerDelay: number;
}

const DigitCell = React.memo(function DigitCell({
  char,
  isFlipping,
  staggerDelay,
}: DigitCellProps) {
  const prefersReduced = useMemo(() => {
    if (typeof window === "undefined") return false;
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }, []);

  const style: React.CSSProperties = prefersReduced
    ? {}
    : isFlipping
    ? {
        animation: `flipDigit ${FLIP_DURATION_MS}ms ease-out ${staggerDelay}ms both`,
      }
    : {};

  return (
    <span className="flip-digit" style={style}>
      {char}
    </span>
  );
});

// ── Single KPI card with Alche styling ──

interface KpiCardProps {
  item: KpiItem;
  prevValue: number | null;
  displayOverride?: string; // When set, show this instead of item.value (for count-up)
  entryDelay?: number;       // ms delay for cascade entry animation (0 = first card)
}

function KpiCard({ item, prevValue, displayOverride, entryDelay }: KpiCardProps) {
  // ── Landing bounce when count-up finishes ──
  const [isLanding, setIsLanding] = useState(false);
  const prevOverride = useRef<string | undefined>(undefined);

  useEffect(() => {
    // Detect transition: count-up (truthy) → final (undefined)
    if (prevOverride.current != null && displayOverride == null) {
      setIsLanding(true);
      const timer = setTimeout(() => setIsLanding(false), 500);
      return () => clearTimeout(timer);
    }
    prevOverride.current = displayOverride;
  }, [displayOverride]);
  const hasChanged = displayOverride ? false : item.raw !== prevValue;
  const displayValue = displayOverride != null ? displayOverride : item.value;
  const chars = formatDigitString(displayValue);

  const prefersReduced = useMemo(() => {
    if (typeof window === "undefined") return false;
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }, []);

  const entryStyle: React.CSSProperties = prefersReduced || entryDelay == null
    ? {}
    : {
        animation: `cardEntry ${CARD_ENTRY_DURATION_MS}ms cubic-bezier(0.16, 1, 0.3, 1) ${entryDelay}ms both`,
      };

  // Landing bounce style to apply to digits when count-up finishes
  const landStyle: React.CSSProperties =
    isLanding && !prefersReduced
      ? {
          animation: `landBounce 450ms cubic-bezier(0.34, 1.56, 0.64, 1) both`,
        }
      : {};

  return (
    <div className="flip-kpi-card" style={entryStyle}>
      <div className="flip-kpi-label">{item.label}</div>
      <div className="flip-kpi-value">
        {item.prefix && (
          <span className="flip-kpi-prefix">{item.prefix}</span>
        )}
        <span className="flip-kpi-digits" style={landStyle}>
          {chars.map((ch, i) => (
            <DigitCell
              key={i}
              char={ch}
              isFlipping={hasChanged}
              staggerDelay={i * STAGGER_MS}
            />
          ))}
        </span>
        {item.suffix && (
          <span className="flip-kpi-suffix">{item.suffix}</span>
        )}
      </div>
    </div>
  );
}

// ── Main FlipBoard component ──

interface FlipBoardProps {
  kpis: KpiData;
}

export default function FlipBoard({ kpis }: FlipBoardProps) {
  const prevRef = useRef<{
    effect: number | null;
    avg_price: number | null;
    districts: number | null;
    mape: number | null;
  }>({
    effect: NaN,
    avg_price: NaN,
    districts: NaN,
    mape: NaN,
  });

  const prev = prevRef.current;

  // ── Count-up animation state ──
  const countingRef = useRef(false);
  const [countUpTexts, setCountUpTexts] = useState<Record<string, string>>({});
  const hasCounted = useRef(false);

  // Detect first render — all raw values are non-null and prev is all NaN
  const isFirstRender = useMemo(() => {
    if (hasCounted.current) return false;
    const allHaveValues =
      kpis.effect.raw != null &&
      kpis.avg_price.raw != null &&
      kpis.districts.raw != null &&
      kpis.mape.raw != null;
    return allHaveValues;
  }, [kpis.effect.raw, kpis.avg_price.raw, kpis.districts.raw, kpis.mape.raw]);

  // Start count-up animation on first render
  useEffect(() => {
    if (!isFirstRender || hasCounted.current) return;
    hasCounted.current = true;
    countingRef.current = true;

    const targets = {
      effect: kpis.effect.raw!,
      avg_price: kpis.avg_price.raw!,
      districts: kpis.districts.raw!,
      mape: kpis.mape.raw!,
    };

    // Build a lookup from label → (prefix, suffix) so we can format
    const meta: Record<string, { prefix: string; suffix: string }> = {};
    [kpis.effect, kpis.avg_price, kpis.districts, kpis.mape].forEach(
      (item) => {
        meta[item.label] = {
          prefix: item.prefix || "",
          suffix: item.suffix || "",
        };
      }
    );

    const startTime = performance.now();

    function tick(now: number) {
      const elapsed = now - startTime;
      const progress = Math.min(1, elapsed / COUNTUP_DURATION_MS);
      const eased = easeOutCubic(progress);

      const next: Record<string, string> = {};

      (["effect", "avg_price", "districts", "mape"] as const).forEach(
        (key) => {
          const raw = targets[key];
          const current = raw * eased;
          const label = kpis[key].label;
          const { prefix, suffix } = meta[label];
          const display = formatInterpValue(current);
          // Show without prefix/suffix during count-up for cleaner animation
          next[key] = display;
        }
      );

      setCountUpTexts(next);

      if (progress < 1) {
        requestAnimationFrame(tick);
      } else {
        // Animation complete — update prevRef so flip doesn't trigger
        prevRef.current = {
          effect: kpis.effect.raw,
          avg_price: kpis.avg_price.raw,
          districts: kpis.districts.raw,
          mape: kpis.mape.raw,
        };
        countingRef.current = false;
        setCountUpTexts({});
      }
    }

    requestAnimationFrame(tick);
  }, [isFirstRender, kpis]);

  // Update prevRef after the flip animation would have played (for non-count-up changes)
  useEffect(() => {
    if (countingRef.current) return; // Don't override while counting
    const timer = setTimeout(() => {
      prevRef.current = {
        effect: kpis.effect.raw,
        avg_price: kpis.avg_price.raw,
        districts: kpis.districts.raw,
        mape: kpis.mape.raw,
      };
    }, STAGGER_MS * 20 + FLIP_DURATION_MS + 100);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kpis.effect.raw, kpis.avg_price.raw, kpis.districts.raw, kpis.mape.raw]);

  useEffect(() => {
    Streamlit.setFrameHeight();
  });

  const kpiList = [kpis.effect, kpis.avg_price, kpis.districts, kpis.mape];

  return (
    <div className="flip-board-root">
      <style>{`
        .flip-board-root {
          display: flex;
          flex-wrap: wrap;
          gap: 1rem;
          padding: 0.75rem 0;
          font-family: 'IBM Plex Mono', 'JetBrains Mono', 'Fira Code', monospace;
          background: ${COLORS.bg};
        }

        .flip-kpi-card {
          flex: 1 1 200px;
          background: linear-gradient(135deg, ${COLORS.glass} 0%, rgba(255,255,255,0.005) 100%);
          border: 1px solid ${COLORS.hairline};
          border-radius: 8px;
          padding: 1.2rem 1.2rem;
          min-width: 160px;
          position: relative;
          overflow: hidden;
          transition: transform 0.35s cubic-bezier(0.16, 1, 0.3, 1),
                      border-color 0.35s ease;
        }

        .flip-kpi-card::before {
          content: '';
          position: absolute;
          top: -1px;
          left: -1px;
          width: 10px;
          height: 10px;
          border-top: 1.5px solid ${COLORS.primary};
          border-left: 1.5px solid ${COLORS.primary};
          opacity: 0;
          transition: opacity 0.35s ease;
          pointer-events: none;
        }

        .flip-kpi-card::after {
          content: '';
          position: absolute;
          bottom: -1px;
          right: -1px;
          width: 10px;
          height: 10px;
          border-bottom: 1.5px solid ${COLORS.primary};
          border-right: 1.5px solid ${COLORS.primary};
          opacity: 0;
          transition: opacity 0.35s ease;
          pointer-events: none;
        }

        .flip-kpi-card:hover::before,
        .flip-kpi-card:hover::after {
          opacity: 1;
        }

        .flip-kpi-card:hover {
          border-color: rgba(215, 255, 0, 0.15);
          transform: translateY(-2px);
        }

        .flip-kpi-label {
          font-family: 'IBM Plex Sans', 'Inter', system-ui, sans-serif;
          font-size: 0.68rem;
          font-weight: 500;
          text-transform: uppercase;
          letter-spacing: 0.06em;
          color: ${COLORS.textMed};
          margin-bottom: 0.5rem;
        }

        .flip-kpi-value {
          display: flex;
          align-items: baseline;
          gap: 4px;
        }

        .flip-kpi-prefix,
        .flip-kpi-suffix {
          font-size: 0.95rem;
          color: ${COLORS.textMed};
          font-weight: 500;
        }

        .flip-kpi-digits {
          display: inline-flex;
          font-size: 1.7rem;
          font-weight: 600;
          color: ${COLORS.paper};
          line-height: 1;
        }

        .flip-digit {
          display: inline-block;
          position: relative;
          min-width: 0.6em;
          text-align: center;
        }

        @keyframes flipDigit {
          0% { transform: rotateX(0deg); opacity: 1; }
          50% { transform: rotateX(-90deg); opacity: 0.3; }
          100% { transform: rotateX(0deg); opacity: 1; }
        }

        @keyframes cardEntry {
          0% { opacity: 0; transform: translateY(20px); }
          100% { opacity: 1; transform: translateY(0); }
        }

        @keyframes landBounce {
          0% { transform: scale(1); }
          50% { transform: scale(1.07); }
          100% { transform: scale(1); }
        }

        @media (prefers-reduced-motion: reduce) {
          .flip-digit { animation: none !important; }
          .flip-kpi-card { animation: none !important; }
        }

        @media (max-width: 768px) {
          .flip-board-root { gap: 0.7rem; }
          .flip-kpi-digits { font-size: 1.3rem; }
          .flip-kpi-card { min-width: 130px; padding: 0.9rem 1rem; }
        }
      `}</style>

      {kpiList.map((item, idx) => {
        // Determine if we have a count-up override for this card
        const key =
          item.label === "RDD Effect"
            ? "effect"
            : item.label === "Avg Price"
            ? "avg_price"
            : item.label === "Districts"
            ? "districts"
            : "mape";
        const override = countUpTexts[key] || undefined;

        return (
          <KpiCard
            key={item.label}
            item={item}
            prevValue={
              prev[
                item.label === "RDD Effect"
                  ? "effect"
                  : item.label === "Avg Price"
                  ? "avg_price"
                  : item.label === "Districts"
                  ? "districts"
                  : "mape"
              ]
            }
            displayOverride={override}
            entryDelay={idx * CARD_STAGGER_MS}
          />
        );
      })}
    </div>
  );
}
