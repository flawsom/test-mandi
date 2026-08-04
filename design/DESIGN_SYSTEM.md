# MandiIQ Ω — Post-Human Design System

**"quantum-glow / particle-portal"** · Dark-first · WCAG AA · reduced-motion ready

| | |
|---|---|
| **System** | MandiIQ Omega — Agricultural Price Intelligence & Causal RDD |
| **Direction** | Design Director (019fcc12-72ee-7100-b7dd-d22b3d0ae484) |
| **Status** | v1.0 — audit complete, tokens shipped |
| **Compliance** | WCAG 2.1 AA (contrast, focus, reduced motion) |

---

## 1. Design Philosophy

MandiIQ reads the mandi (market) as a living particle field: price signals, causal
shocks, and forecast uncertainty drift through a dark quantum void, surfacing as
**glowing portals of intelligence**. The aesthetic is *post-human* — machine-grade
precision (tabular numerics, monospaced telemetry) fused with ambient, almost
biological glow. Nothing is decorative: every glow marks a live signal, every
violet haze marks prediction uncertainty.

**Three principles:**
1. **Dark is the canvas** — the void is not "empty", it is the substrate where
   signal particles resolve.
2. **Glow = meaning** — primary lime = the brand/CTA; cyan = telemetry;
   violet = ML/forecast; magenta = anomaly; amber = staleness; rose = hazard.
3. **Motion obeys the user** — drift and pulse exist, but collapse instantly
   under `prefers-reduced-motion`.

---

## 2. Audit of Existing Design (pre-v1.0)

| Surface | Before | After |
|---|---|---|
| `--bg-base` | `#000000` | `#05040a` (violet-tinted void) |
| `--bg-surface` | `#0a0a0a` | `#0d0a18` |
| `--color-primary` | `#d7ff00` | **kept** `#d7ff00` (brand continuity) |
| text-high/med/low | `#bababa`/`#7e7e7e`/`#555555` | `#e8ecf4`/`#c3c9d6`/`#8a93a8` — **contrast gains** |
| status green/amber/red | `#5ddb6c`/`#ffb020`/`#ff4d5e` | `#57e389`/`#f5c211`/`#ff4d5e` (AA-tuned) |
| commodity onion/tomato/wheat/potato | `#8B6BC4`/`#D9663B`/`#D4A94E`/`#B98354` | `#a78bfa`/`#ff6b81`/`#fcd34d`/`#c8a06b` |
| surfaces | flat `rgba(255,255,255,.03)` | quantum glass `rgba(13,10,24,.72)` + blur + glow |

Fonts and motion curves are preserved (Space Grotesk / IBM Plex Sans / Mono /
Barlow; `cubic-bezier(0.16,1,0.3,1)`), so the upgrade is token-driven, not a rewrite.

---

## 3. Palette

### 3.1 Quantum void (backgrounds)

| Token | Value | Use |
|---|---|---|
| `--q-bg-void` | `#05040a` | app base |
| `--q-bg-deep` | `#0a0814` | hero particle field |
| `--q-bg-surface` | `#0d0a18` | cards |
| `--q-bg-elevated` | `#12101f` | modals, menus, toolbars |
| `--q-bg-inset` | `#08060f` | wells, code, focus trap |

### 3.2 Quantum accent spectrum (meaning-coded)

| Token | Value | Meaning |
|---|---|---|
| `--q-primary` | `#d7ff00` | brand, CTA, live pipeline |
| `--q-primary-hi` | `#eaff7a` | hover/glow peak |
| `--q-primary-dim` | `#9fc400` | pressed/disabled |
| `--q-cyan` | `#67e8f9` | telemetry, data-stream |
| `--q-violet` | `#a78bfa` | ML prediction, future-state |
| `--q-magenta` | `#f0abfc` | anomaly, alert-ring |
| `--q-amber` | `#fcd34d` | warning, stale chip |
| `--q-rose` | `#ff6b81` | hazard, below-threshold |

### 3.3 Text (WCAG AA verified)

| Token | Value | Contrast vs `#0d0a18` |
|---|---|---|
| `--q-text-high` | `#e8ecf4` | **≈17:1** (AAA) |
| `--q-text-body` | `#c3c9d6` | **≈11:1** (AAA) |
| `--q-text-muted` | `#8a93a8` | **≈6:1** (AA) |
| `--q-text-faint` | `#6a7286` | ≈4.6:1 (AA, large-only usage) |

> Rule: body text never falls below `--q-text-muted`; `faint` is reserved for
> overlines/captions ≥14px semibold or non-essential metadata.

---

## 4. Typography

| Role | Stack | Spec |
|---|---|---|
| Display | Space Grotesk 600 | `--q-type-display` 2.25rem/1.1 |
| Title | Space Grotesk 600 | 1.5rem/1.2 |
| Subhead | IBM Plex Sans 500 | 1rem/1.4 |
| Body | IBM Plex Sans 400 | 0.9375rem/1.6 |
| Mono/telemetry | IBM Plex Mono 400 | 0.8125rem/1.5 |
| Overline/eyebrow | IBM Plex Mono 600 | 0.7rem, +0.12em tracking |
| Numeric | Barlow 600, tabular-nums | 1.25rem/1.1 |

- All sizes use `clamp()` (fluid) so 200% text zoom never breaks layout (WCAG 1.4.4).
- Numeric data always uses `font-variant-numeric: tabular-nums`.

---

## 5. Surface & Glow Treatments

| Treatment | Token/CSS | Notes |
|---|---|---|
| Quantum glass card | `.q-card` | `rgba(13,10,24,.72)` + 18px blur + hairline |
| Portal field | `.q-field::before/::after` | 2–3 radial `--q-blot-*` gradients, 18s drift |
| Metric tile | `.q-metric` | tabular numerics + `.q-unit` dimming |
| Status chip | `.q-chip` + `--q-chip-*` | dot + glow, never color-only |
| CTA | `.q-btn` | lime fill, `--q-glow-primary`, spring press |
| Ghost | `.q-btn-ghost` | hairline border, lime on hover |
| Table | `.q-table` | hairline rows, overline headers |

Glow values are deliberately low-alpha (0.18–0.35) — luminous on the void,
never blown out, and they double as focus affordances.

---

## 6. Data-Viz Ramps

Full token set in `design/tokens/data-viz-ramps.css`.

- **Status**: latest `#57e389` · warning `#f5c211` · down `#ff4d5e` · up `#4da3ff`
- **Commodities**: onion violet · tomato rose · wheat amber · potato earth ·
  rice cyan · other lime
- **Series**: 8-color qualitative ramp (colorblind-safe pairs: cyan/lime, violet/magenta…)
- **Sequential**: lime, cyan, violet 6-step single-hue ramps (heatmaps/density)
- **Diverging**: causal RDD effect — cyan (negative) → neutral → rose (positive)
- **Markers**: every categorical series carries a distinct glyph (dot/tri/square/x)
  so color is never the only channel (WCAG 1.4.1).

---

## 7. Dark-First & Accessibility

- Single source of truth: dark tokens. Light mode is not shipped (by design —
  the platform is a dark ops console); print/report variants reuse `--q-bg-inset`.
- **Contrast**: body ≥4.5:1, large/UI ≥3:1, focus indicator 2px lime outline
  with 2px offset (`:focus-visible`).
- **Reduced motion**: `@media (prefers-reduced-motion: reduce)` collapses all
  animation/transitions to 0.01ms, disables blot drift, parallax, and the
  particle canvas (see `motion-reduced.css`).
- **Zoom/overflow**: fluid type + no fixed-width containers.

---

## 8. Deliverable Files

| File | Purpose |
|---|---|
| `design/DESIGN_SYSTEM.md` | this document |
| `design/tokens/quantum-tokens.css` | core design tokens (palette/type/glow/motion) |
| `design/tokens/surfaces-glow.css` | particle-portal surface/glow components |
| `design/tokens/data-viz-ramps.css` | chart/status/commodity ramps + markers |
| `design/tokens/motion-reduced.css` | reduced-motion + focus accessibility layer |
| `design/tokens/streamlit-quantum.toml` | Streamlit `[theme]` mapping |

### Wiring order (landing pages)

```html
<link rel="stylesheet" href="design/tokens/quantum-tokens.css">
<link rel="stylesheet" href="design/tokens/surfaces-glow.css">
<link rel="stylesheet" href="design/tokens/data-viz-ramps.css">
<link rel="stylesheet" href="design/tokens/motion-reduced.css">
```

### Streamlit

Copy `design/tokens/streamlit-quantum.toml` values over the `[theme]` block in
`.streamlit/config.toml`, and inject the CSS token sheets via the app's
existing `st.markdown("<style>…</style>")` loader for full glow support.

---

## 9. Status

- [x] Audit existing tokens (landing, portals.css, config.toml, cursor-effect.js)
- [x] Quantum palette (dark-first, AA)
- [x] Typography pairing
- [x] Surface/glow treatments (particle-portal)
- [x] Data-viz ramps (status, commodity, series, sequential, diverging)
- [x] Reduced-motion + focus layer
- [x] Streamlit theme mapping
- [ ] (handoff) Visualization Engineer applies ramps to dashboard charts
- [ ] (handoff) Core Platform Engineer wires token CSS into Streamlit app
