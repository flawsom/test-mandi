"""
MandiIQ — Shared design-system theme (Layer 2 of the design system).

Single source of truth for all injected CSS consumed by the dashboard pages.
Every page calls inject_theme() once at the top of its render() function.

Visual Aesthetic: Stark, immersive monochrome with chartreuse/lime highlights
inspired by Alche Studio (alche.studio).
"""

from pathlib import Path
import json
import os
import streamlit as st

# ── Resilient API base resolution ──
_DEFAULT_API_BASE = "https://p01--mandiiq--zbvjrztgjqgw.code.run"  # hosted API; override via MANDIIQ_API_URL env/secret for local dev

def get_api_base() -> str:
    """Resolve the FastAPI base URL."""
    candidates = ["MANDIQ_API_URL", "MANDIIQ_API_URL"]
    try:
        for key in candidates:
            val = st.secrets.get(key)
            if val:
                return str(val)
        for section in st.secrets:
            try:
                blob = st.secrets[section]
            except Exception:
                continue
            if not isinstance(blob, dict):
                continue
            for key in candidates:
                if key in blob and blob[key]:
                    return str(blob[key])
    except Exception:
        pass

    for env_key in candidates:
        val = os.environ.get(env_key)
        if val:
            return val

    return _DEFAULT_API_BASE

# ── Resolve paths relative to this file ──
_THEME_DIR = Path(__file__).resolve().parent
_DESIGN_CSS = Path(__file__).resolve().parent.parent / "styles" / "design.css"

# ── Commodity color lookup ──
COMMODITY_COLORS = {
    "Onion":  "#8B6BC4",
    "Tomato": "#D9663B",
    "Wheat":  "#D4A94E",
    "Potato": "#B98354",
}

# Palette shorthand (Alche Studio aesthetic: monochrome-lime)
INK      = "#000000"      # Alche Pure Black
SLATE    = "#111111"      # Alche Dark Charcoal Card
PAPER    = "#FFFFFF"      # Stark White Text
MUTED    = "#bababa"      # High Muted Grey
FAINT    = "#7e7e7e"      # Medium Muted Grey
TURMERIC = "#d7ff00"      # Alche Lime Accent
RUST     = "#D9663B"      # Deficit Alert
SAGE     = "#8FAE89"      # healthy NDVI

# ── Public API ──
# Static type checkers and linters resolve these from __all__.
__all__ = [
    "get_api_base",
    "inject_theme",
    "inject_flowing_dots_and_cursor",
    "inject_gsap_splittext",
    "inject_lenis_scroll",
    "inject_page_loader",
    "inject_scroll_progress",
    "inject_sound_toggle",
    "inject_scroll_to_top",
    "inject_card_stagger",
    "inject_scroll_trigger_factory",
    "inject_atmosphere",
    "inject_webgl_hero",
    "inject_countup_js",
    "countup_card",
    "commodity_color",
    "render_ledger_table",
    "COMMODITY_COLORS",
    "INK", "SLATE", "PAPER", "MUTED", "FAINT", "TURMERIC", "RUST", "SAGE",
]



def inject_theme():
    """Inject the full Layer 2 stylesheet into the Streamlit page.

    Only injects once per session — subsequent calls are no-ops.
    Call once at the top of each page render for safety; the gate
    prevents duplicate ~35KB CSS injections.
    """
    if st.session_state.get("_mandiiq_theme_injected"):
        return
    st.session_state._mandiiq_theme_injected = True

    token_css = ""
    if _DESIGN_CSS.exists():
        token_css = _DESIGN_CSS.read_text(encoding="utf-8")

    st.markdown(
        f"""<style>
/* ── Google Font imports ── */
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@300;400;500;600&family=Space+Grotesk:wght@300;400;500;600;700&family=Barlow:wght@300;400;500;600;700&family=Inter:wght@300;400;500;600&display=swap');

/* ── Design tokens from design.css ── */
{token_css}

/* ── Typography overrides ── */
h1, h2, h3, h4, h5, h6 {{
    font-family: var(--font-display, "Space Grotesk", system-ui, sans-serif) !important;
    color: var(--color-paper, #ffffff) !important;
    font-weight: 400 !important;
    letter-spacing: 0.08em !important;
}}

.stApp p, .stApp span, .stApp li, .stApp td, .stApp th,
.stApp label, .stApp div[data-testid="stMetricLabel"],
.stApp div[data-testid="stSidebar"] p,
.stApp div[data-testid="stSidebar"] span {{
    font-family: var(--font-body, "IBM Plex Sans", system-ui, sans-serif) !important;
}}

div[data-testid="stMetricValue"] {{
    font-family: var(--font-numeric, "Barlow", "IBM Plex Mono", monospace) !important;
    color: var(--color-primary, #d7ff00) !important;
    font-weight: 500 !important;
    font-variant-numeric: tabular-nums !important;
    letter-spacing: 0.02em !important;
}}

/* Heading scale */
h1 {{ font-size: 1.6rem !important; font-weight: 500 !important; text-transform: uppercase; }}
h2 {{ font-size: 1.15rem !important; font-weight: 500 !important;
      border-bottom: 1px solid var(--hairline-strong, rgba(255,255,255,0.15));
      padding-bottom: 0.4rem; margin-bottom: 1rem; text-transform: uppercase; }}
h3 {{ font-size: 0.82rem !important; font-weight: 500 !important;
      color: var(--color-muted, #bababa) !important;
      text-transform: uppercase; letter-spacing: 0.1em; }}

/* ── Tab reskin ── */
.stTabs [data-baseweb="tab-list"] {{
    gap: 0;
    background: rgba(255,255,255,0.02);
    border-radius: 4px;
    padding: 3px;
    border: 1px solid var(--hairline);
}}
.stTabs [data-baseweb="tab"] {{
    border-radius: 2px;
    padding: 0.5rem 1.1rem;
    transition: all 0.2s ease-out;
    font-weight: 400;
    font-family: var(--font-body, "IBM Plex Sans", system-ui, sans-serif);
    color: var(--color-muted);
    font-size: 0.85rem;
}}
.stTabs [data-baseweb="tab"][aria-selected="true"] {{
    background: var(--color-primary, #d7ff00) !important;
    color: var(--color-ink, #000000) !important;
    font-weight: 600 !important;
}}
.stTabs [data-baseweb="tab"]:hover:not([aria-selected="true"]) {{
    color: var(--color-paper);
    background: rgba(255,255,255,0.04);
}}

/* ── Button reskin ── */
.stButton > button[kind="primary"],
.stButton > button {{
    background: transparent !important;
    color: var(--color-paper, #ffffff) !important;
    font-weight: 500 !important;
    border: 1px solid var(--hairline) !important;
    border-radius: 999px !important;
    padding: 0.5rem 1.5rem !important;
    transition: all 0.3s cubic-bezier(0.25, 0.46, 0.45, 0.94) !important;
}}
.stButton > button:hover {{
    background: var(--color-primary, #d7ff00) !important;
    color: var(--color-ink, #000000) !important;
    border-color: var(--color-primary, #d7ff00) !important;
}}

/* ── Sidebar adjustments ── */
div[data-testid="stSidebar"] {{
    background: var(--color-ink, #000000) !important;
    border-right: 1px solid var(--hairline) !important;
}}
div[data-testid="stSidebar"] h1,
div[data-testid="stSidebar"] h2 {{
    font-family: var(--font-display, "Space Grotesk", sans-serif) !important;
    color: var(--color-paper, #ffffff) !important;
}}

/* ── Interpretation boxes ── */
.interpretation-box {{
    background: rgba(255, 255, 255, 0.02);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-left: 3px solid var(--color-primary, #d7ff00);
    border-radius: 4px;
    padding: 1rem 1.2rem;
    margin: 1rem 0;
    font-size: 0.92rem;
    line-height: 1.6;
    color: var(--color-muted, #bababa);
}}

.insig-box {{
    border-color: rgba(255, 255, 255, 0.08);
    border-left-color: var(--color-faint, #7e7e7e);
}}

*:focus-visible {{
    outline: 2px solid var(--color-primary, #d7ff00) !important;
    outline-offset: 2px !important;
}}

@media (prefers-reduced-motion: reduce) {{
    .atmosphere-flash,
    .atmosphere-cloud {{
        animation: none !important;
    }}
}}

/* Suppress Streamlit branding */
footer {{ display: none; }}

/* Thinner Sidebar on Desktop, Responsive overrides */
@media (max-width: 1024px) {{
    div[data-testid="stSidebar"] {{
        width: 200px !important;
        min-width: 180px !important;
    }}
}}

/* ═══ RESPONSIVE OVERRIDES ═══ */

/* Touch-friendly targets */
@media (hover: none) and (pointer: coarse) {{
    .mandiq-btn, .mandiq-btn-primary, .mandiq-btn-secondary,
    .mandiq-btn-ghost, .mandiq-btn-danger,
    button, .stButton button {{
        min-height: 44px;
    }}
    select, input, textarea, .stSelectbox, .stMultiSelect {{
        font-size: 16px !important;
    }}
}}

/* Mobile (< 640px) */
@media screen and (max-width: 640px) {{
    h1, .stTitle h1 {{ font-size: 1.4rem !important; }}
    h2, .stSubHeader h2 {{ font-size: 1.15rem !important; }}
    h3 {{ font-size: 1rem !important; }}
    p, li, .stMarkdown p {{ font-size: 0.9rem !important; }}

    .stButton button {{ width: 100%; }}

    div[data-testid="metric-container"] {{ padding: 0.4rem !important; }}
    div[data-testid="metric-container"] label {{ font-size: 0.7rem !important; }}
    div[data-testid="metric-container"] div[data-testid="metric-value"] {{ font-size: 1rem !important; }}

    section[data-testid="stSidebar"] .stMarkdown {{ font-size: 0.85rem !important; }}

    .stTabs [data-baseweb="tab-list"] {{ flex-wrap: wrap !important; gap: 0.25rem !important; }}
    .stTabs [data-baseweb="tab"] {{ font-size: 0.8rem !important; padding: 0.4rem 0.6rem !important; }}

    .row-widget.stHorizontal {{ flex-direction: column !important; }}
    .row-widget.stHorizontal > div {{
        width: 100% !important;
        flex: 0 0 100% !important;
        min-width: 0 !important;
    }}
}}

/* Tablet (641px – 1024px) */
@media screen and (min-width: 641px) and (max-width: 1024px) {{
    h1 {{ font-size: 1.6rem !important; }}
    h2 {{ font-size: 1.3rem !important; }}

    .stTabs [data-baseweb="tab"] {{ font-size: 0.85rem !important; padding: 0.5rem 0.8rem !important; }}

    .row-widget.stHorizontal > div {{ min-width: 0 !important; }}
}}

/* Print */
@media print {{
    .stApp header, section[data-testid="stSidebar"],
    .stButton, button, .mandiq-toast-container,
    .mandiq-modal-overlay {{ display: none !important; }}
    .main .block-container {{ max-width: 100% !important; padding: 0 !important; }}
}}



/* ═══ ANIMATIONS ═══ */

@keyframes fadeInUp {{
    from {{ opacity: 0; transform: translateY(12px); }}
    to   {{ opacity: 1; transform: translateY(0); }}
}}

@keyframes pulseGlow {{
    0%, 100% {{ box-shadow: 0 0 4px rgba(232, 177, 77, 0.2); }}
    50%      {{ box-shadow: 0 0 12px rgba(232, 177, 77, 0.5); }}
}}

@keyframes shimmer {{
    0%   {{ background-position: -200% 0; }}
    100% {{ background-position: 200% 0; }}
}}

@keyframes floatCard {{
    0%, 100% {{ transform: translateY(0); }}
    50%      {{ transform: translateY(-3px); }}
}}

@keyframes statusPulse {{
    0%, 100% {{ opacity: 1; }}
    50%      {{ opacity: 0.4; }}
}}

.animate-fade-in  {{ animation: fadeInUp 0.4s ease-out both; }}
.animate-pulse    {{ animation: pulseGlow 2s ease-in-out infinite; }}
.animate-shimmer  {{ background: linear-gradient(90deg, rgba(255,255,255,0.04) 25%, rgba(255,255,255,0.08) 50%, rgba(255,255,255,0.04) 75%); background-size: 200% 100%; animation: shimmer 1.5s infinite; }}
.animate-float    {{ animation: floatCard 4s ease-in-out infinite; }}
.animate-status   {{ animation: statusPulse 2s ease-in-out infinite; }}

@media (prefers-reduced-motion: reduce) {{
    *, *::before, *::after {{
        animation-duration: 0.01ms !important;
        animation-iteration-count: 1 !important;
        transition-duration: 0.01ms !important;
    }}
}}

.mandiq-kpi.live {{
    animation: pulseGlow 2s ease-in-out infinite;
    border-color: rgba(232, 177, 77, 0.3);
}}

.status-dot {{ display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 4px; }}
.status-dot.green  {{ background: #6BBF8A; }}
.status-dot.amber  {{ background: #E8B14D; }}
.status-dot.red    {{ background: #C84B4B; }}


/* ── Seamless quantum-glow hover language (matches landing hover-language) ── */
.stApp .stButton > button, .stApp .stDownloadButton button {{
    transition: transform .32s cubic-bezier(.2,.9,.2,1), box-shadow .32s ease,
        border-color .3s ease, color .3s ease, background-color .3s ease;
    will-change: transform;
}}
.stApp .stButton > button:hover, .stApp .stDownloadButton button:hover,
.stApp .stButton > button:focus-visible {{
    transform: translateY(-3px);
    box-shadow: 0 0 0 1px var(--color-glow, rgba(95,242,255,.18)) inset,
        0 18px 40px rgba(95,242,255,.22), var(--color-lift, rgba(95,242,255,.18));
}}
/* sidebar nav links: underline sweep + glow on hover */
.stApp div[data-testid="stSidebarNav"] a,
.stApp div[data-testid="stSidebarNav"] a[data-testid="stSidebarNavLink"] {{
    position: relative;
    transition: color .3s ease, transform .32s ease, text-shadow .3s ease;
}}
.stApp div[data-testid="stSidebarNav"] a::after {{
    content: "";
    position: absolute; left: 0.4em; bottom: .4em; height: 2px; width: 0;
    background: linear-gradient(90deg, var(--color-primary,#d7ff00),
        var(--glow-mag,#ff5fe0));
    border-radius: 2px; transition: width .4s cubic-bezier(.2,.9,.2,1);
}}
.stApp div[data-testid="stSidebarNav"] a:hover {{
    transform: translateX(4px) translateY(-1px);
    text-shadow: 0 0 16px rgba(215,255,0,.4);
}}
.stApp div[data-testid="stSidebarNav"] a:hover::after {{ width: 100%; }}
/* live tabs: glow underline on active/hover */
.stApp div[data-testid="stTabs"] button[data-baseweb="tab"] {{
    transition: color .3s ease, text-shadow .3s ease, transform .3s ease;
}}
.stApp div[data-testid="stTabs"] button[data-baseweb="tab"]:hover {{
    transform: translateY(-2px);
    text-shadow: 0 0 16px rgba(215,255,0,.55);
}}
/* metric cards: magnetic lift + inner glow */
.stApp div[data-testid="stMetric"] {{
    transition: transform .32s cubic-bezier(.2,.9,.2,1), box-shadow .34s ease,
        border-color .3s ease;
}}
.stApp div[data-testid="stMetric"]:hover {{
    transform: translateY(-4px);
    border-color: var(--m-glow-dim, rgba(215,255,0,.4)) !important;
    box-shadow: 0 22px 46px rgba(0,0,0,.5), 0 0 28px rgba(215,255,0,.16);
}}
@media (prefers-reduced-motion: reduce) {{
    .stApp .stButton > button, .stApp div[data-testid="stMetric"],
    .stApp div[data-testid="stSidebarNav"] a {{
        transition: none !important;
    }}
}}
</style>""",
        unsafe_allow_html=True,
    )    # Inject flowing dots + cursor trail (via inject_flowing_dots_and_cursor in app.py)
    # Inject debug badge (only when ?debug=1 is in the URL)
    inject_debug_badge()
    # Inject scroll-to-top floating button
    inject_scroll_to_top()


def inject_gsap_splittext(selector: str = ".hero-title", stagger: float = 0.02):
    """Inject GSAP + SplitText for character-level text reveal.

    Matches the alche.studio WorksItemController character stagger:
    - Each character animates from y:30, opacity:0 → y:0, opacity:1
    - 0.02s stagger between characters (configurable)
    - 0.6s duration per character, power2.out easing
    - Respects prefers-reduced-motion

    Args:
        selector: CSS selector for the target heading element.
        stagger: Stagger delay between each character in seconds.
    """
    key = "_mandiiq_splittext_injected"
    if st.session_state.get(key):
        return
    st.session_state[key] = True

    html = f"""
<script>
(function() {{
    'use strict';

    // Respect reduced motion
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

    // ── Load GSAP + SplitText from CDN ──
    function loadScript(src) {{
        return new Promise(function(resolve, reject) {{
            var s = document.createElement('script');
            s.src = src;
            s.onload = resolve;
            s.onerror = reject;
            s.crossOrigin = 'anonymous';
            s.referrerPolicy = 'no-referrer';
            document.head.appendChild(s);
        }});
    }}

    var gsapUrl = 'https://cdn.jsdelivr.net/npm/gsap@3.12.5/dist/gsap.min.js';
    var splitTextUrl = 'https://cdn.jsdelivr.net/npm/gsap@3.12.5/dist/SplitText.min.js';

    function initReveal() {{
        if (typeof gsap === 'undefined' || typeof SplitText === 'undefined') return;

        var targets = document.querySelectorAll('{selector}');
        if (!targets.length) return;

        targets.forEach(function(el) {{
            // Guard: skip if already processed
            if (el.dataset.splittextDone === 'true') return;
            el.dataset.splittextDone = 'true';

            // Wrap characters in spans, set initial state
            var split = new SplitText(el, {{ type: 'chars' }});

            // Set initial state: invisible, shifted down
            gsap.set(split.chars, {{
                y: 30,
                opacity: 0,
                willChange: 'transform, opacity'
            }});

            // Animate in: slide up + fade, staggered
            gsap.to(split.chars, {{
                y: 0,
                opacity: 1,
                duration: 0.6,
                ease: 'power2.out',
                stagger: {stagger},
                delay: 0.3
            }});
        }});
    }}

    // Load GSAP first, then SplitText, then run
    var isGsapLoaded = typeof gsap !== 'undefined';
    var isSplitLoaded = typeof SplitText !== 'undefined';

    if (isGsapLoaded && isSplitLoaded) {{
        initReveal();
    }} else {{
        Promise.all([
            isGsapLoaded ? Promise.resolve() : loadScript(gsapUrl).catch(function(e) {{
                console.warn('MandiIQ: GSAP load failed', e);
            }}),
            isSplitLoaded ? Promise.resolve() : loadScript(splitTextUrl).catch(function(e) {{
                console.warn('MandiIQ: SplitText load failed', e);
            }})
        ]).then(function() {{
            // Wait a tick for registration
            setTimeout(initReveal, 100);
        }});
    }}

    // Re-run on Streamlit rerender events
    document.addEventListener('streamlit:render', function() {{
        setTimeout(initReveal, 300);
    }});
}})();
</script>
"""
    st.markdown(html, unsafe_allow_html=True)


def inject_lenis_scroll():
    """Inject Lenis smooth scroll + GSAP ScrollTrigger integration.

    Matches alche.studio's smooth scroll system:
    - Lenis with custom lerp easing
    - Integrates with GSAP via scrollerProxy for seamless scroll-triggered animations
    - Respects prefers-reduced-motion
    - Re-inits on streamlit:render
    """
    key = "_mandiiq_lenis_injected"
    if st.session_state.get(key):
        return
    st.session_state[key] = True

    html = """<script>
(function() {
    'use strict';
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    if (window.__mandiiqLenis) return;

    function loadLenis() {
        var s = document.createElement('script');
        s.src = 'https://cdn.jsdelivr.net/npm/lenis@1.1.18/dist/lenis.min.js';
        s.onload = function() {
            if (typeof Lenis === 'undefined') return;
            window.__mandiiqLenis = new Lenis({
                duration: 1.8,
                easing: function(t) { return Math.min(1, 1.001 - Math.pow(2, -10 * t)); },
                orientation: 'vertical',
                gestureOrientation: 'vertical',
                smoothWheel: true,
                touchMultiplier: 2,
                wheelMultiplier: 1,
                infinite: false,
            });

            // Expose scroll progress (0-1) as a CSS custom property on :root
            // Any element can use var(--scroll-progress) in calc(), animation-delay,
            // opacity, background-position, etc. — no JS needed for consumers.
            window.__mandiiqLenis.on('scroll', function(pos) {
                if (pos && typeof pos.progress === 'number') {
                    document.documentElement.style.setProperty(
                        '--scroll-progress',
                        pos.progress.toFixed(4)
                    );
                }
            });

            // Debounced ScrollTrigger.refresh() on Lenis resize
            // Lenis fires 'resize' when viewport or content dimensions change
            // (e.g. after a Streamlit rerender calls .resize()). ScrollTrigger
            // markers re-calculate their positions to stay aligned with the
            // virtual scroll space. 150ms debounce prevents cascade.
            var _refreshTimer = null;
            window.__mandiiqLenis.on('resize', function() {
                if (_refreshTimer) clearTimeout(_refreshTimer);
                _refreshTimer = setTimeout(function() {
                    if (typeof ScrollTrigger !== 'undefined') {
                        ScrollTrigger.refresh();
                    }
                }, 150);
            });

            // Connect Lenis to GSAP if available
            function connectGsap() {
                if (typeof gsap !== 'undefined') {
                    gsap.ticker.lagSmoothing(0);
                    gsap.ticker.add(function(time) {
                        if (window.__mandiiqLenis) {
                            window.__mandiiqLenis.raf(time * 1000);
                        }
                    });
                } else {
                    // Standalone raf loop
                    function raf(time) {
                        if (window.__mandiiqLenis) {
                            window.__mandiiqLenis.raf(time);
                        }
                        requestAnimationFrame(raf);
                    }
                    requestAnimationFrame(raf);
                }
            }

            // Wait a tick then connect
            setTimeout(connectGsap, 50);
        };
        s.crossOrigin = 'anonymous';
        s.referrerPolicy = 'no-referrer';
        document.head.appendChild(s);
    }

    loadLenis();

    // Re-init on Streamlit render
    document.addEventListener('streamlit:render', function() {
        if (window.__mandiiqLenis) {
            window.__mandiiqLenis.resize();
        }
    });
})();
</script>"""
    st.markdown(html, unsafe_allow_html=True)


def inject_page_loader():
    """Inject a cinematic page loader overlay.

    Matches alche.studio's loading sequence:
    - Full-viewport black overlay with contracting lime accent line
    - Fades out after DOM ready + 400ms via .is-hidden class
    - Session-state gated to prevent re-injection on Streamlit reruns
    - Respects prefers-reduced-motion
    """
    key = "_mandiiq_loader_injected"
    if st.session_state.get(key):
        return
    st.session_state[key] = True

    html = """<div id="mandiq-page-loader" class="page-loader">
  <div class="loader-line"></div>
</div>
<script>
(function() {
    'use strict';
    if (window.__mandiiqLoaderInited) return;
    window.__mandiiqLoaderInited = true;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

    var loader = document.getElementById('mandiq-page-loader');
    if (!loader) return;

    function hideLoader() {
        loader.classList.add('is-hidden');
        // Remove from DOM after transition completes (600ms)
        setTimeout(function() {
            if (loader && loader.parentNode) {
                loader.parentNode.removeChild(loader);
            }
        }, 700);
    }

    // Hide after DOM ready + 400ms grace period
    if (document.readyState === 'complete') {
        setTimeout(hideLoader, 400);
    } else {
        window.addEventListener('load', function() {
            setTimeout(hideLoader, 400);
        });
    }

    // Also hide on Streamlit rerender (in case it fires before page load)
    document.addEventListener('streamlit:render', function() {
        if (loader && !loader.classList.contains('is-hidden')) {
            hideLoader();
        }
    });
})();
</script>"""
    st.markdown(html, unsafe_allow_html=True)


def inject_scroll_progress():
    """Inject a scroll progress bar at the viewport top.

    Matches alche.studio's thin accent progress bar:
    - 2px lime bar, fixed at top, z-index just below loader
    - rAF-throttled scroll listener updates transform: scaleX()
    - Respects prefers-reduced-motion
    - Session-state gated
    """
    key = "_mandiiq_scrollprogress_injected"
    if st.session_state.get(key):
        return
    st.session_state[key] = True

    html = """<div id="mandiq-scroll-progress" class="scroll-progress"></div>
<script>
(function() {
    'use strict';
    if (window.__mandiiqScrollProgInited) return;
    window.__mandiiqScrollProgInited = true;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

    var bar = document.getElementById('mandiq-scroll-progress');
    if (!bar) return;

    function setProgress(p) {
        bar.style.transform = 'scaleX(' + Math.min(Math.max(p, 0), 1) + ')';
    }

    function onNativeScroll() {
        var scrollTop = window.scrollY || document.documentElement.scrollTop;
        var docHeight = document.documentElement.scrollHeight - window.innerHeight;
        setProgress(docHeight > 0 ? scrollTop / docHeight : 0);
    }

    // Throttled native scroll listener (fallback when Lenis not active)
    var ticking = false;
    var onScroll = function() {
        if (!ticking) {
            window.requestAnimationFrame(function() {
                onNativeScroll();
                ticking = false;
            });
            ticking = true;
        }
    };

    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', onScroll, { passive: true });

    // Initial position
    setTimeout(onScroll, 50);

    // ── Lenis integration ──
    // When Lenis is active, the native window.scrollY stays at 0 because
    // Lenis intercepts native scrolling. Listen to Lenis's custom scroll
    // event which provides the virtual scroll progress directly.
    function tryConnectLenis() {
        // Guard: already connected → tell caller to stop polling
        if (window.__mandiiqLenisProgressConnected) return true;
        if (window.__mandiiqLenis && typeof window.__mandiiqLenis.on === 'function') {
            window.__mandiiqLenisProgressConnected = true;
            window.__mandiiqLenis.on('scroll', function(pos) {
                if (pos && typeof pos.progress === 'number') {
                    setProgress(pos.progress);
                }
            });
            return true;
        }
        return false;
    }

    // Try immediately, then poll for up to 3s (Lenis may load asynchronously)
    if (!tryConnectLenis()) {
        var pollAttempts = 0;
        var pollTimer = setInterval(function() {
            pollAttempts++;
            if (tryConnectLenis() || pollAttempts > 30) {
                clearInterval(pollTimer);
            }
        }, 100);
    }

    // Re-check on Streamlit render (content height may change)
    document.addEventListener('streamlit:render', function() {
        setTimeout(onScroll, 200);
        // Re-try Lenis connection in case it wasn't ready on first attempt
        tryConnectLenis();
    });
})();
</script>"""
    st.markdown(html, unsafe_allow_html=True)


def inject_sound_toggle():
    """Inject sound toggle with 3-bar equalizer + Web Audio API.

    Matches alche.studio's sound toggle:
    - 3 animated bars (CSS equalizer)
    - Web Audio API synthesized sounds (no MP3 files needed)
    - localStorage persistence
    - Starts muted (autoplay policy safe)
    - Respects prefers-reduced-motion
    """
    key = "_mandiiq_sound_injected"
    if st.session_state.get(key):
        return
    st.session_state[key] = True

    html = """<script>
(function() {
    'use strict';
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

    // ── Sound toggle initialisation ──
    // The toggle button is rendered in the Streamlit topbar (app.py), which
    // may not exist yet when this script executes. We wrap everything in
    // a safe init function that retries until the element is found.
    function initSoundToggle() {
        if (window.__mandiiqSoundInited) return;
        var toggle = document.getElementById('mandiq-sound-toggle');
        if (!toggle) {
            // Retry on next tick — the topbar may not be in the DOM yet
            // (Streamlit renders the nav layout after animation injectors)
            if (!window.__mandiiqSoundPendingRetry) {
                window.__mandiiqSoundPendingRetry = true;
                setTimeout(initSoundToggle, 200);
            }
            return;
        }

        // Element-level guard: if this exact DOM node was already wired,
        // skip re-attaching listeners. Streamlit rerenders fire
        // 'streamlit:render' on every widget interaction, not just page
        // navigation. Without this guard, duplicate click listeners
        // accumulate, causing the toggle to fire N times per click.
        if (toggle._mandiiqWired) {
            window.__mandiiqSoundInited = true;
            return;
        }
        toggle._mandiiqWired = true;

        window.__mandiiqSoundInited = true;
        window.__mandiiqSoundPendingRetry = false;

    // Audio context + synth sounds
    var audioCtx = null;
    var isMuted = true;

    // Restore from localStorage
    try {
        var saved = localStorage.getItem('mandiiq_sound_muted');
        if (saved === 'false') {
            isMuted = false;
            toggle.dataset.muted = 'false';
            toggle.setAttribute('aria-label', 'Disable sound');
        }
    } catch(e) {}

    function initAudio() {
        if (audioCtx) return;
        try {
            audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        } catch(e) {}
    }

    function playTone(freq, duration, type, volume) {
        if (!audioCtx || isMuted) return;
        try {
            var osc = audioCtx.createOscillator();
            var gain = audioCtx.createGain();
            osc.type = type || 'sine';
            osc.frequency.setValueAtTime(freq, audioCtx.currentTime);
            gain.gain.setValueAtTime(volume || 0.08, audioCtx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + duration);
            osc.connect(gain);
            gain.connect(audioCtx.destination);
            osc.start(audioCtx.currentTime);
            osc.stop(audioCtx.currentTime + duration);
        } catch(e) {}
    }

    function playClick() {
        playTone(800, 0.08, 'sine', 0.06);
        setTimeout(function() { playTone(1200, 0.06, 'sine', 0.04); }, 40);
    }

    function playWhoosh() {
        if (!audioCtx || isMuted) return;
        try {
            var bufferSize = audioCtx.sampleRate * 0.3;
            var buffer = audioCtx.createBuffer(1, bufferSize, audioCtx.sampleRate);
            var data = buffer.getChannelData(0);
            for (var i = 0; i < bufferSize; i++) {
                var t = i / audioCtx.sampleRate;
                data[i] = (Math.random() * 2 - 1) * Math.pow(1 - t / 0.3, 3);
            }
            var source = audioCtx.createBufferSource();
            source.buffer = buffer;
            var gain = audioCtx.createGain();
            gain.gain.setValueAtTime(0.04, audioCtx.currentTime);
            var filter = audioCtx.createBiquadFilter();
            filter.type = 'lowpass';
            filter.frequency.setValueAtTime(500, audioCtx.currentTime);
            filter.frequency.exponentialRampToValueAtTime(50, audioCtx.currentTime + 0.3);
            source.connect(filter);
            filter.connect(gain);
            gain.connect(audioCtx.destination);
            source.start(audioCtx.currentTime);
        } catch(e) {}
    }

    // Toggle handler
    function onToggle() {
        initAudio();
        isMuted = !isMuted;
        toggle.dataset.muted = isMuted ? 'true' : 'false';
        toggle.setAttribute('aria-label', isMuted ? 'Enable sound' : 'Disable sound');
        try { localStorage.setItem('mandiiq_sound_muted', isMuted ? 'true' : 'false'); } catch(e) {}
        if (!isMuted) {
            playClick();
        }
    }

    toggle.addEventListener('click', onToggle);
    toggle.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            onToggle();
        }
    });

    // Expose helpers for section enter effects
    window.__mandiiqSoundPlayWhoosh = playWhoosh;
    window.__mandiiqSoundInit = initAudio;
    window.__mandiiqSoundPlayClick = playClick;

    // Init audio on first user interaction
    document.addEventListener('click', function() { initAudio(); }, { once: true });
    document.addEventListener('touchstart', function() { initAudio(); }, { once: true });
    }

    // ── First attempt ──
    // The toggle button may or may not be in the DOM yet. If not,
    // the initSoundToggle function retries after 200ms (the Streamlit
    // topbar is rendered in the nav layout which runs after this
    // injector). The retry-to-guard window.__mandiiqSoundPendingRetry
    // prevents infinite retry storms.
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initSoundToggle);
    } else {
        initSoundToggle();
    }

    // ── Re-init on Streamlit page transitions ──
    // When the user navigates to a new route, the topbar is
    // re-rendered. The new button element has no listeners attached.
    // This event clears the init flag so the next page load
    // re-attaches the listeners to the fresh button element.
    document.addEventListener('streamlit:render', function() {
        window.__mandiiqSoundInited = false;
        window.__mandiiqSoundPendingRetry = false;
        setTimeout(initSoundToggle, 300);
    });
})();
</script>"""
    st.markdown(html, unsafe_allow_html=True)


def inject_card_stagger():
    """Inject card stagger reveal for dashboard section items.

    Matches alche.studio's WorksItemController stagger pattern:
    - Items start hidden (opacity:0, y:20)
    - When scrolled into view, animate in with staggered delay
    - Uses GSAP if available, falls back to CSS transitions + IntersectionObserver
    - Respects prefers-reduced-motion
    """
    key = "_mandiiq_stagger_injected"
    if st.session_state.get(key):
        return
    st.session_state[key] = True

    html = """<script>
(function() {
    'use strict';
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    if (window.__mandiiqStaggerInited) return;
    window.__mandiiqStaggerInited = true;

    var SELECTOR = '.stagger-item, .glass-card, [data-stagger]';

    function initStagger() {
        var items = document.querySelectorAll(SELECTOR);
        if (!items.length) return;

        // Mark items for reveal
        items.forEach(function(el) {
            if (!el.classList.contains('stagger-ready')) {
                el.classList.add('stagger-ready');
                el.style.opacity = '0';
                el.style.transform = 'translateY(20px)';
                el.style.transition = 'opacity 0.5s cubic-bezier(0.16,1,0.3,1), transform 0.5s cubic-bezier(0.16,1,0.3,1)';
            }
        });

        // Use GSAP if available for more polished stagger
        if (typeof gsap !== 'undefined') {
            var observer = new IntersectionObserver(function(entries) {
                entries.forEach(function(entry) {
                    if (entry.isIntersecting) {
                        var children = entry.target.querySelectorAll('.stagger-ready');
                        // Merge with direct children too
                        var all = [];
                        entry.target.querySelectorAll('.stagger-ready').forEach(function(c) { all.push(c); });
                        if (all.length) {
                            gsap.to(all, {
                                y: 0,
                                opacity: 1,
                                duration: 0.5,
                                ease: 'power2.out',
                                stagger: 0.04,
                                overwrite: 'auto'
                            });
                        } else {
                            // Revert to CSS transition
                            entry.target.style.opacity = '1';
                            entry.target.style.transform = 'translateY(0)';
                        }
                        observer.unobserve(entry.target);
                    }
                });
            }, { threshold: 0.08, rootMargin: '0px 0px -5% 0px' });

            // Observe parent containers
            var containers = document.querySelectorAll('.stagger-container, [data-stagger-container]');
            containers.forEach(function(c) { observer.observe(c); });

            // Also observe individual items not in containers
            items.forEach(function(el) {
                var parent = el.parentElement;
                if (parent && !parent.matches('.stagger-container, .kpi-grid, [data-stagger-container]')) {
                    observer.observe(el);
                }
            });
        } else {
            // Fallback: CSS-only reveal via IntersectionObserver
            var io = new IntersectionObserver(function(entries) {
                entries.forEach(function(e) {
                    if (e.isIntersecting) {
                        e.target.style.opacity = '1';
                        e.target.style.transform = 'translateY(0)';
                        io.unobserve(e.target);
                    }
                });
            }, { threshold: 0.08, rootMargin: '0px 0px -5% 0px' });

            items.forEach(function(el) { io.observe(el); });
        }
    }

    // Run on load and Streamlit rerender
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() { setTimeout(initStagger, 200); });
    } else {
        setTimeout(initStagger, 200);
    }
    document.addEventListener('streamlit:render', function() { setTimeout(initStagger, 300); });
})();
</script>"""
    st.markdown(html, unsafe_allow_html=True)


def inject_scroll_trigger_factory():
    """Inject a custom ScrollTriggerFactory matching alche.studio's pattern.

    Provides a lightweight scroll-triggered animation system:
    - Fires 'section-enter' / 'section-leave' custom events
    - Manages IntersectionObserver-based section tracking
    - Integrates with sound system for section-triggered audio
    - Respects prefers-reduced-motion
    """
    key = "_mandiiq_scrolltrigger_injected"
    if st.session_state.get(key):
        return
    st.session_state[key] = True

    html = """<script>
(function() {
    'use strict';
    if (window.__mandiiqScrollFactory) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

    window.__mandiiqScrollFactory = true;

    // Section definitions — sections that trigger enter/leave events
    var SECTIONS = [
        { name: 'hero', selector: '.page-hero, .hero-section' },
        { name: 'kpi', selector: '.kpi-grid, .metrics-section' },
        { name: 'chart', selector: '.glass, .chart-section, [data-section]' },
    ];

    var activeSections = {};

    function init() {
        SECTIONS.forEach(function(section) {
            var els = document.querySelectorAll(section.selector);
            els.forEach(function(el) {
                var io = new IntersectionObserver(function(entries) {
                    entries.forEach(function(entry) {
                        var wasActive = activeSections[section.name];
                        if (entry.isIntersecting) {
                            if (!wasActive) {
                                activeSections[section.name] = true;
                                document.dispatchEvent(new CustomEvent('section-enter', {
                                    detail: { sectionName: section.name, element: el }
                                }));
                                // Trigger sound on section enter if available
                                if (window.__mandiiqSoundInit) {
                                    window.__mandiiqSoundInit();
                                }
                                if (window.__mandiiqSoundPlayWhoosh) {
                                    try { window.__mandiiqSoundPlayWhoosh(); } catch(e) {}
                                }
                            }
                        } else {
                            if (wasActive) {
                                activeSections[section.name] = false;
                                document.dispatchEvent(new CustomEvent('section-leave', {
                                    detail: { sectionName: section.name, element: el }
                                }));
                            }
                        }
                    });
                }, { threshold: 0.1 });
                io.observe(el);
            });
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() { setTimeout(init, 150); });
    } else {
        setTimeout(init, 150);
    }
    document.addEventListener('streamlit:render', function() { setTimeout(init, 300); });
})();
</script>"""
    st.markdown(html, unsafe_allow_html=True)

def inject_atmosphere():
    """Inject the atmosphere layer (drifting blobs + dot grid).

    Drifters respond to Lenis scroll position for vertical parallax:
    - Blobs higher on screen (--y: lower %) move more; lower blobs move less
    - Uses CSS `translate` property (separate from `transform` used in
      drifter-float animation) so the aesthetic drift animation plays
      on top of the scroll-driven parallax offset — no conflict
    - Falls back to CSS-only drifter-float animation if Lenis never loads
    - Falls back to native scroll if Lenis isn't active
    - Respects prefers-reduced-motion
    """
    st.markdown(
        """<div class="atmosphere" aria-hidden="true">
  <div class="atmosphere-flash"></div>
  <div class="atmosphere-cloud"></div>
  <div class="atmosphere-drifter" style="--x:15%;--y:20%;--s:180px;--d:25s;--hue:100;--op:0.06"></div>
  <div class="atmosphere-drifter" style="--x:75%;--y:30%;--s:140px;--d:35s;--hue:80;--op:0.05"></div>
  <div class="atmosphere-drifter" style="--x:50%;--y:70%;--s:200px;--d:40s;--hue:60;--sat:0.9;--lit:0.6;--op:0.04"></div>
  <div class="atmosphere-drifter" style="--x:8%;--y:65%;--s:100px;--d:30s;--op:0.03"></div>
  <div class="atmosphere-drifter" style="--x:88%;--y:12%;--s:130px;--d:45s;--hue:120;--op:0.035"></div>
</div>
<div class="dot-grid" aria-hidden="true"></div>
<script>
(function(){
  if (window.__mandiiqReveal) return;
  window.__mandiiqReveal = true;
  function init(){
    var sel = '.reveal, .page-hero, .stPlotlyChart, .kpi-grid, .metric-container, .glass, .flip-board-root';
    var els = document.querySelectorAll(sel);
    if (!('IntersectionObserver' in window) || !els.length){ return; }
    els.forEach(function(el){
      if (!el.classList.contains('is-visible')) el.classList.add('reveal');
    });
    var io = new IntersectionObserver(function(entries){
      entries.forEach(function(e){
        if (e.isIntersecting){ e.target.classList.add('is-visible'); io.unobserve(e.target); }
      });
    }, { threshold: 0.08, rootMargin: '0px 0px -8% 0px' });
    els.forEach(function(el){ io.observe(el); });
  }
  if (document.readyState === 'loading'){
    document.addEventListener('DOMContentLoaded', function(){ setTimeout(init, 120); });
  } else { setTimeout(init, 120); }
  document.addEventListener('streamlit:render', function(){ setTimeout(init, 200); });
})();

// ── Lenis-driven parallax for atmosphere drifters ──
(function(){
  'use strict';
  if (window.__mandiiqAtmoPara) return;
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  window.__mandiiqAtmoPara = true;

  var drifters = document.querySelectorAll('.atmosphere-drifter');
  if (!drifters.length) return;

  // Compute parallax intensity per drifter based on vertical position
  // Blobs higher on screen (--y closer to 0%) move MORE (larger factor)
  // Blobs lower (--y closer to 100%) move LESS — mimics depth
  var parallaxFactors = [];
  var MAX_PX = 120; // max pixel offset from top to bottom of page

  drifters.forEach(function(el) {
    var yStr = el.style.getPropertyValue('--y') || '50%';
    var yPct = parseFloat(yStr) || 50;
    // Map y 0-100 → 0.38-0.04 (higher = less parallax)
    var factor = 0.38 - (yPct / 100) * 0.34;
    parallaxFactors.push(Math.max(0.02, Math.min(0.4, factor)));
  });

  function applyParallax(progress) {
    // progress is 0-1; map to -1..1 so blobs move up AND down
    var p = (progress - 0.5) * 2;
    drifters.forEach(function(el, i) {
      var offset = p * MAX_PX * parallaxFactors[i];
      // CSS `translate` property is separate from `transform` used by
      // the drifter-float animation — they compose without conflict.
      el.style.translate = '0 ' + offset.toFixed(1) + 'px';
    });
  }

  // ── Connect to Lenis ──
  function tryConnectLenis() {
    if (window.__mandiiqAtmoLenis) return true;
    if (window.__mandiiqLenis && typeof window.__mandiiqLenis.on === 'function') {
      window.__mandiiqAtmoLenis = true;
      window.__mandiiqLenis.on('scroll', function(pos) {
        if (pos && typeof pos.progress === 'number') {
          applyParallax(pos.progress);
        }
      });
      // Set initial position
      applyParallax(0);
      return true;
    }
    return false;
  }

  if (!tryConnectLenis()) {
    var attempts = 0;
    var timer = setInterval(function() {
      attempts++;
      if (tryConnectLenis() || attempts > 30) {
        clearInterval(timer);
      }
    }, 100);
  }

  // Native scroll fallback (when Lenis not active, e.g. non-Lenis pages)
  window.addEventListener('scroll', function() {
    if (!window.__mandiiqAtmoLenis) {
      var st = window.scrollY || document.documentElement.scrollTop;
      var dh = document.documentElement.scrollHeight - window.innerHeight;
      applyParallax(dh > 0 ? st / dh : 0);
    }
  }, { passive: true });

  // Re-check on Streamlit render in case Lenis loads late
  document.addEventListener('streamlit:render', function() {
    setTimeout(function() {
      if (!window.__mandiiqAtmoLenis) {
        tryConnectLenis();
      }
    }, 500);
  });
})();
</script>""",
        unsafe_allow_html=True,
    )


def commodity_color(commodity: str) -> str:
    """Return the hex color for a commodity name (case-insensitive)."""
    return COMMODITY_COLORS.get(commodity.title(), MUTED)


_WEBGL_BUNDLE_CACHE: str | None = None
_WEBGL_BUNDLE_TRIED: bool = False


def inject_webgl_hero():
    """Inject React Three.js WebGL particle field (built Vite bundle).

    Auto-mounts on any page by detecting the
    <div id="mandiq-webgl-hero-root"> placeholder — the React component
    uses IntersectionObserver to lazy-load when scrolled near viewport.

    The container div and bundle are injected on EVERY page load
    (no session gate). The bundle re-executes each time; browser module
    caching means deps are never re-fetched — only the wrapper script
    re-runs to mount React on the fresh container div.

    Falls back to CSS gradient on: low-end devices, bundle not built,
    or prefers-reduced-motion.
    """
    global _WEBGL_BUNDLE_CACHE, _WEBGL_BUNDLE_TRIED

    # ── Container div (re-injected every page) ──
    st.markdown(
        '<div id="mandiq-webgl-hero-root"></div>',
        unsafe_allow_html=True,
    )

    # ── Bundle (module-level cache avoids disc I/O on every page) ──
    if not _WEBGL_BUNDLE_TRIED:
        _WEBGL_BUNDLE_TRIED = True
        _FRONTEND_DIST = Path(__file__).resolve().parent / "frontend" / "dist"
        bundle_paths = sorted(_FRONTEND_DIST.glob("assets/index-*.js")) if _FRONTEND_DIST.exists() else []
        if bundle_paths:
            try:
                _WEBGL_BUNDLE_CACHE = bundle_paths[0].read_text(encoding="utf-8")
            except Exception:
                pass

    if _WEBGL_BUNDLE_CACHE is None:
        return

    st.markdown(
        '<script type="module">\n' + _WEBGL_BUNDLE_CACHE + '\n</script>',
        unsafe_allow_html=True,
    )


def inject_quantum_field(commodity: str | None = None, limit: int = 60, seed: int = 20240701):
    """Inject the interactive QVE 3D quantum particle field as a dashboard view.

    Mounts the same Vite bundle (auto-mounted by main.tsx on
    <div id="mandiq-quantum-field-root">) and feeds it the resolved API base
    so the frontend can call /qve/placement without hardcoding a host.

    Falls back gracefully: if the bundle is missing or the backend is
    unreachable, the React component renders a deterministic offline field,
    so the dashboard never breaks.
    """
    global _WEBGL_BUNDLE_CACHE, _WEBGL_BUNDLE_TRIED

    # API base handed to the bundle via a window global (same resolution the
    # rest of the dashboard uses).
    api_base = get_api_base()

    # ── Container div (re-injected every page) ──
    st.markdown(
        '<div id="mandiq-quantum-field-root"'
        f' data-commodity="{commodity or "all"}"'
        f' data-limit="{limit}"'
        f' data-seed="{seed}"'
        "></div>",
        unsafe_allow_html=True,
    )

    # ── Bundle (module-level cache avoids disc I/O on every page) ──
    if not _WEBGL_BUNDLE_TRIED:
        _WEBGL_BUNDLE_TRIED = True
        _FRONTEND_DIST = Path(__file__).resolve().parent / "frontend" / "dist"
        bundle_paths = sorted(_FRONTEND_DIST.glob("assets/index-*.js")) if _FRONTEND_DIST.exists() else []
        if bundle_paths:
            try:
                _WEBGL_BUNDLE_CACHE = bundle_paths[0].read_text(encoding="utf-8")
            except Exception:
                pass

    if _WEBGL_BUNDLE_CACHE is None:
        return

    st.markdown(
        '<script>window.__MANDIIQ_API_BASE__ = '
        + json.dumps(api_base)
        + ";</script>"
        '<script type="module">\n' + _WEBGL_BUNDLE_CACHE + '\n</script>',
        unsafe_allow_html=True,
    )


def inject_debug_badge():
    """Inject a floating diagnostics badge when ?debug=1 is in the URL.

    Shows:
    - Page load time (seconds since navigation start)
    - DOM node count (live-updated via rAF)
    - Active animation engine status (Lenis, GSAP, sound, WebGL, atmosphere)

    IDEMPOTENT: safe to call multiple times — window.__mandiiqDebugBadge gate
    prevents duplicate badge injection.
    """
    key = "_mandiiq_debug_badge_injected"
    if st.session_state.get(key):
        return
    st.session_state[key] = True

    html = """<div id="mandiq-debug-badge" style="display:none;"></div>
<script>
(function() {
    'use strict';
    if (window.__mandiiqDebugBadge) return;

    // ── Only show when ?debug=1 is in search OR hash ──
    if (!window.location.search.includes('debug=1') && !window.location.hash.includes('debug=1')) return;

    window.__mandiiqDebugBadge = true;

    var badge = document.getElementById('mandiq-debug-badge');
    if (!badge) return;
    badge.style.display = '';  // unhide

    // ── Animation engine probes ──
    function getEngineStatus() {
        var parts = [];
        parts.push(window.__mandiiqLenis ? 'Lenis' : null);
        parts.push(typeof gsap !== 'undefined' ? 'GSAP' : null);
        parts.push(window.__mandiiqSoundInited ? 'Sound' : null);
        parts.push(window.__mandiiqReveal ? 'Atmo' : null);
        parts.push(document.getElementById('mandiq-webgl-hero-root') ? 'WebGL' : null);
        return parts.filter(Boolean).join(', ') || '(none active)';
    }

    var startTime = performance.now();

    function buildContent() {
        var elapsed = ((performance.now() - startTime) / 1000).toFixed(2);
        var domNodes = document.querySelectorAll('*').length;
        var engines = getEngineStatus();
        return (
            '<div style="font-size:0.6rem;color:#7e7e7e;margin-bottom:2px;text-transform:uppercase;letter-spacing:0.06em;">Page Diagnostics</div>'
            + '<table style="font-size:0.72rem;border-collapse:collapse;">'
            + '<tr><td style="color:#bababa;padding:1px 6px 1px 0;">load</td><td style="color:#ffffff;font-family:IBM Plex Mono,monospace;font-variant-numeric:tabular-nums;">' + elapsed + 's</td></tr>'
            + '<tr><td style="color:#bababa;padding:1px 6px 1px 0;">DOM</td><td style="color:#ffffff;font-family:IBM Plex Mono,monospace;font-variant-numeric:tabular-nums;">' + domNodes.toLocaleString() + ' nodes</td></tr>'
            + '<tr><td style="color:#bababa;padding:1px 6px 1px 0;">engines</td><td style="color:#d7ff00;font-family:IBM Plex Mono,monospace;font-size:0.65rem;">' + engines + '</td></tr>'
            + '</table>'
        );
    }

    function render() {
        if (!badge || !badge.parentNode) return;
        badge.innerHTML = buildContent();
        requestAnimationFrame(render);
    }

    // Set badge position and styling
    badge.style.cssText = (
        'position:fixed;bottom:8px;right:8px;z-index:99999;'
        + 'background:rgba(0,0,0,0.85);border:1px solid rgba(215,255,0,0.2);'
        + 'border-radius:6px;padding:6px 10px;'
        + 'pointer-events:none;user-select:none;'
    );

    // Start the rAF loop
    requestAnimationFrame(render);

    // Re-check engine status on Streamlit rerender
    document.addEventListener('streamlit:render', function() {
        if (badge && badge.style.display !== 'none') {
            render();
        }
    });
})();
</script>"""
    st.markdown(html, unsafe_allow_html=True)


def inject_scroll_to_top():
    """Inject a floating 'scroll to top' button.

    Appears fixed at bottom-right when the user scrolls past the hero section.
    Clicking smoothly scrolls to top — uses Lenis if active, else native.
    Fades in/out with opacity + translateY, respects prefers-reduced-motion.
    Session-state gated to prevent duplicates.
    """
    if st.session_state.get("_mandiiq_scrolltop_injected"):
        return
    st.session_state._mandiiq_scrolltop_injected = True

    html = """<div id="mandiq-scroll-top" class="scroll-top-btn" role="button" tabindex="0" aria-label="Scroll to top">
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
    <polyline points="18 15 12 9 6 15"></polyline>
  </svg>
</div>
<style>
#mandiq-scroll-top {
  position: fixed;
  bottom: 28px;
  right: 28px;
  z-index: 9999;
  width: 42px;
  height: 42px;
  border-radius: 50%;
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(215,255,0,0.25);
  color: #d7ff00;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  opacity: 0;
  transform: translateY(16px) scale(0.9);
  pointer-events: none;
  transition: opacity 0.35s ease, transform 0.35s cubic-bezier(0.16,1,0.3,1), background 0.25s ease, border-color 0.25s ease;
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
  box-shadow: 0 0 0 0 rgba(215,255,0,0);
}
#mandiq-scroll-top.is-visible {
  opacity: 1;
  transform: translateY(0) scale(1);
  pointer-events: auto;
}
#mandiq-scroll-top:hover {
  background: rgba(215,255,0,0.12);
  border-color: rgba(215,255,0,0.6);
  box-shadow: 0 0 16px rgba(215,255,0,0.15);
}
#mandiq-scroll-top:active {
  transform: translateY(0) scale(0.92);
}
@media (prefers-reduced-motion: reduce) {
  #mandiq-scroll-top {
    transition: none !important;
  }
  #mandiq-scroll-top.is-visible {
    opacity: 1;
    transform: none;
  }
}
</style>
<script>
(function() {
  'use strict';
  if (window.__mandiiqScrollTop) return;
  window.__mandiiqScrollTop = true;
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

  var btn = document.getElementById('mandiq-scroll-top');
  if (!btn) return;

  var SCROLL_THRESHOLD = 300; // px from top to show button
  var ticking = false;

  function scrollToTop() {
    if (window.__mandiiqLenis && typeof window.__mandiiqLenis.scrollTo === 'function') {
      window.__mandiiqLenis.scrollTo(0, { duration: 1.2, easing: function(t) { return 1 - Math.pow(1 - t, 3); } });
    } else {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  }

  function onScroll() {
    var st = window.scrollY || document.documentElement.scrollTop || 0;
    // Use Lenis virtual scroll if active
    if (window.__mandiiqLenis && typeof window.__mandiiqLenis.scroll === 'number') {
      st = window.__mandiiqLenis.scroll;
    }
    var show = st > SCROLL_THRESHOLD;
    btn.classList.toggle('is-visible', show);
  }

  // Throttled scroll handler
  function handleScroll() {
    if (!ticking) {
      requestAnimationFrame(function() { onScroll(); ticking = false; });
      ticking = true;
    }
  }

  // Listen to both native scroll and Lenis scroll
  window.addEventListener('scroll', handleScroll, { passive: true });
  if (window.__mandiiqLenis && typeof window.__mandiiqLenis.on === 'function') {
    window.__mandiiqLenis.on('scroll', handleScroll);
  }

  // Click / keyboard handler
  btn.addEventListener('click', scrollToTop);
  btn.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      scrollToTop();
    }
  });

  // Check initial position
  setTimeout(onScroll, 100);

  // Re-attach Lenis scroll listener if Lenis loads after this script
  var _lenisPoll = setInterval(function() {
    if (window.__mandiiqLenis && typeof window.__mandiiqLenis.on === 'function') {
      window.__mandiiqLenis.on('scroll', handleScroll);
      clearInterval(_lenisPoll);
    }
  }, 200);
  setTimeout(function() { clearInterval(_lenisPoll); }, 5000);

  // Re-check on Streamlit rerender
  document.addEventListener('streamlit:render', function() {
    setTimeout(onScroll, 200);
  });
})();
</script>"""
    st.markdown(html, unsafe_allow_html=True)


def inject_countup_js():
    """Inject shared eased count-up JavaScript (easeOutCubic, 800ms, landing bounce).

    Single source of truth for all count-up animations across dashboard pages.
    Exposes `window.__mandiiqAnimateCountup()` for manual invocation and
    auto-detects both `[data-ctarget]` and `[data-fkey]` elements on page load.

    Attributes (auto-detected):
    - `data-ctarget` or `data-ftarget`: target number (required)
    - `data-cfmt` or `data-ffmt`: 'us' for US-number formatting (commas)
    - `data-cprefix`: text before the number (e.g., "₹")
    - `data-csuffix`: text after the number (e.g., "%")

    Counts from 0 to target over 800ms with easeOutCubic easing.
    On completion, applies `landBounce` CSS animation (scale 1→1.07→1).

    Uses window.__mandiiqCU guard to inject CSS+JS only once per session.
    """
    if st.session_state.get("_mandiiq_cu_js_injected"):
        return
    st.session_state._mandiiq_cu_js_injected = True

    # ── CSS for countup cards + landing bounce keyframe ──
    st.markdown(
        '<style>'
        '.countup-card{background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.07);border-radius:8px;padding:0.8rem 1rem;text-align:center;position:relative;overflow:hidden;transition:transform .35s cubic-bezier(0.16,1,0.3,1),border-color .35s ease}'
        '.countup-card::before,.countup-card::after{content:\"\";position:absolute;width:10px;height:10px;opacity:0;transition:opacity .35s ease;pointer-events:none}'
        '.countup-card::before{top:-1px;left:-1px;border-top:1.5px solid #d7ff00;border-left:1.5px solid #d7ff00}'
        '.countup-card::after{bottom:-1px;right:-1px;border-bottom:1.5px solid #d7ff00;border-right:1.5px solid #d7ff00}'
        '.countup-card:hover{border-color:rgba(215,255,0,0.15);transform:translateY(-2px)}'
        '.countup-card:hover::before,.countup-card:hover::after{opacity:1;box-shadow:0 0 4px 2px rgba(215,255,0,0.25)}'
        '.countup-label{font-size:0.7rem;color:#7e7e7e;font-family:IBM Plex Mono,monospace;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:0.3rem}'
        '.countup-value{font-size:2rem;font-family:Barlow,IBM Plex Mono,monospace;font-weight:500;color:#ffffff;line-height:1.1}'
        '@keyframes landBounce{0%{transform:scale(1)}50%{transform:scale(1.07)}100%{transform:scale(1)}}'
        '</style>',
        unsafe_allow_html=True,
    )

    js = """<script>
(function(){
  'use strict';
  if (window.__mandiiqCU) return;
  window.__mandiiqCU = true;

  // ── Unified animate_countup() — callable by any page ──
  window.__mandiiqAnimateCountup = function __mandiiqAnimateCountup(opts) {
    opts = opts || {};
    var selector = opts.selector || '[data-ctarget], [data-fkey]';
    var duration = opts.duration || 800;
    var landBounce = opts.landBounce !== false;

    var els = [];
    document.querySelectorAll(selector).forEach(function(el) {
      var raw = parseFloat(el.getAttribute('data-ctarget') || el.getAttribute('data-ftarget'));
      if (isNaN(raw)) return;
      // For [data-fkey] cards, target the .fresh-val child
      var targetEl = el.matches('[data-fkey]') ? el.querySelector('.fresh-val') : el;
      if (el.matches('[data-fkey]') && !targetEl) return;
      els.push({
        el: targetEl || el,
        tar: raw,
        fmt: el.getAttribute('data-cfmt') || el.getAttribute('data-ffmt') || '',
        prefix: el.getAttribute('data-cprefix') || '',
        suffix: el.getAttribute('data-csuffix') || '',
      });
    });

    if (!els.length) return;

    function eoc(t) { return 1 - Math.pow(1 - t, 3); }
    var startTs = performance.now();

    (function tick() {
      var now = performance.now(), p = Math.min(1, (now - startTs) / duration), e = eoc(p), done = true;
      els.forEach(function(o) {
        var cur = o.tar * e, disp = Math.round(cur);
        var txt = o.prefix + (o.fmt === 'us' ? disp.toLocaleString('en-US') : String(disp)) + o.suffix;
        o.el.textContent = txt;
        if (p < 1 || Math.abs(cur - o.tar) > 0.5) done = false;
      });
      if (done) {
        if (landBounce) {
          els.forEach(function(o) {
            o.el.style.animation = 'landBounce 450ms cubic-bezier(0.34, 1.56, 0.64, 1) both';
            setTimeout(function() { o.el.style.animation = ''; }, 500);
          });
        }
      } else {
        requestAnimationFrame(tick);
      }
    })();
  };

  // ── Auto-detect elements on page load ──
  window.__mandiiqAnimateCountup({ selector: '[data-ctarget], [data-fkey]' });
})();
</script>"""
    st.markdown(js, unsafe_allow_html=True)


def countup_card(label: str, value_raw: float | int, prefix: str = "", suffix: str = "", fmt: str = "") -> str:
    """Return an HTML div for an eased count-up KPI card.

    The card renders with initial value '0' and animates to `value_raw`
    over 800ms via `inject_countup_js()`. Call `inject_countup_js()` once
    per page (it guards against duplicate injection).

    Args:
        label: Card label text.
        value_raw: Target numeric value to count up to.
        prefix: Text before the number (e.g., '₹').
        suffix: Text after the number (e.g., '%').
        fmt: 'us' for US-number formatting (commas).

    Returns:
        HTML string for the KPI card div.
    """
    import math
    if value_raw is None or (isinstance(value_raw, float) and (not math.isfinite(value_raw))):
        return f'<div class="countup-card"><div class="countup-label">{label}</div><div class="countup-value">—</div></div>'
    safe_prefix = prefix.replace('"', '&quot;').replace("'", "&#39;")
    safe_suffix = suffix.replace('"', '&quot;').replace("'", "&#39;")
    cfmt = f' data-cfmt="{fmt}"' if fmt else ""
    return (
        f'<div class="countup-card">'
        f'<div class="countup-label">{label}</div>'
        f'<div class="countup-value" data-ctarget="{value_raw}"'
        f' data-cprefix="{safe_prefix}" data-csuffix="{safe_suffix}"'
        f'{cfmt}>0'
        f'</div></div>'
    )


def render_ledger_table(df, columns=None, commodity_col=None, highlight_col=None):
    """Render a pandas DataFrame as an HTML ledger table with commodity chips."""
    if df is None or len(df) == 0:
        return

    cols = columns or list(df.columns)
    ccol = commodity_col or highlight_col

    # Build header
    ths = "".join(f"<th>{c.replace('_', ' ').upper()}</th>" for c in cols)
    html = f'<table class="ledger-table"><thead><tr>{ths}</tr></thead><tbody>'

    for _, row in df[cols].iterrows():
        html += "<tr>"
        for c in cols:
            val = row[c]
            if c == ccol and ccol in COMMODITY_COLORS:
                color = COMMODITY_COLORS.get(str(val).title(), "#bababa")
                html += (
                    f'<td><span style="display:inline-flex;align-items:center;gap:6px;">'
                    f'<span style="width:8px;height:8px;border-radius:2px;'
                    f'background:{color};flex-shrink:0;"></span>'
                    f'{val}</span></td>'
                )
            else:
                if isinstance(val, float):
                    if abs(val) < 0.01:
                        html += f"<td>{val:.4f}</td>"
                    elif abs(val) < 100:
                        html += f"<td>{val:.2f}</td>"
                    else:
                        html += f"<td>{val:,.0f}</td>"
                else:
                    html += f"<td>{val}</td>"
        html += "</tr>"

    html += "</tbody></table>"
    st.markdown(html, unsafe_allow_html=True)

def inject_flowing_dots_and_cursor():
    """Inject noise-based flowing dots canvas + spring-physics cursor trail.

    Two canvases render as fixed backgrounds:
      1. FlowingDots — grid-based particle flow field with noise, mouse proximity repulsion, DPR-aware
      2. CursorTrail — 20-trail spring physics, color cycling, touch support
    Respects prefers-reduced-motion. Hides cursor on touch-only devices.
    Uses --bg-base CSS var for background, falls back to #000000.
    """
    if st.session_state.get("_mandiiq_flowingdots_injected"):
        return
    st.session_state._mandiiq_flowingdots_injected = True

    html = """<div id="mandiq-flowing-dots" aria-hidden="true"></div>
<script>
(function(){
  'use strict';
  if(window.matchMedia('(prefers-reduced-motion:reduce)').matches) return;

  /* ── FLOWING DOTS ── */
  (function(){
    var container=document.getElementById('mandiq-flowing-dots');
    if(!container) return;
    var canvas=document.createElement('canvas');
    canvas.style.cssText='position:fixed;top:0;left:0;width:100%;height:100%;pointer-events:none;z-index:0;display:block;';
    container.appendChild(canvas);
    var ctx=canvas.getContext('2d'),W,H,pts=[],grid=16,dpr=Math.min(window.devicePixelRatio||1,2);
    var bg=getComputedStyle(document.documentElement).getPropertyValue('--bg-base').trim()||'#000000';
    function resize(){
      W=window.innerWidth;H=window.innerHeight;
      canvas.width=W*dpr;canvas.height=H*dpr;
      canvas.style.width=W+'px';canvas.style.height=H+'px';
      ctx.setTransform(dpr,0,0,dpr,0,0);
      pts=[];
      for(var x=grid/2;x<W;x+=grid)
        for(var y=grid/2;y<H;y+=grid)
          pts.push({x:x,y:y,vx:0,vy:0,ox:x,oy:y});
    }
    function noise(x,y,t){
      return(Math.sin(x*0.01+t)+Math.sin(y*0.01+t*0.8)+Math.sin((x+y)*0.005+t*1.2))/3;
    }
    var mx=-9999,my=-9999;
    document.addEventListener('mousemove',function(e){mx=e.clientX;my=e.clientY;},{passive:true});
    document.addEventListener('touchmove',function(e){if(e.touches.length){mx=e.touches[0].clientX;my=e.touches[0].clientY;}},{passive:true});
    var t=0;
    function anim(){
      t+=0.005;
      ctx.fillStyle=bg;ctx.fillRect(0,0,W,H);
      for(var i=0;i<pts.length;i++){
        var p=pts[i],nv=noise(p.x,p.y,t),ang=nv*Math.PI*4;
        var dx=mx-p.x,dy=my-p.y,dist=Math.sqrt(dx*dx+dy*dy);
        if(dist<150&&dist>0){var f=(1-dist/150)*0.5;p.vx+=dx/dist*f;p.vy+=dy/dist*f;}
        p.vx+=Math.cos(ang)*0.1;p.vy+=Math.sin(ang)*0.1;
        p.vx*=0.95;p.vy*=0.95;
        var nx=p.x+p.vx,ny=p.y+p.vy;
        var sp=Math.sqrt(p.vx*p.vx+p.vy*p.vy),al=Math.min(0.8,sp*8+0.3);
        ctx.beginPath();ctx.arc(p.x,p.y,2.5,0,Math.PI*2);
        ctx.fillStyle='rgba(215,255,0,'+al+')';ctx.fill();
        p.x=nx;p.y=ny;
        if(nx<0||nx>W)p.x=p.ox;if(ny<0||ny>H)p.y=p.oy;
        p.vx+=(p.ox-p.x)*0.01;p.vy+=(p.oy-p.y)*0.01;
      }
      requestAnimationFrame(anim);
    }
    window.addEventListener('resize',resize);resize();anim();
  })();

  /* ── CURSOR TRAIL ── */
  (function(){
    var isTouchOnly=('ontouchstart'in window)&&!window.matchMedia('(pointer:fine)').matches;
    if(isTouchOnly) return;
    var CFG={friction:0.5,trails:20,size:50,dampening:0.25,tension:0.98};
    var cvs2,ctx2,running=true,pos={x:0,y:0},lines=[];
    function Osc(c){this.phase=c.phase||0;this.offset=c.offset||0;this.frequency=c.frequency||0.001;this.amplitude=c.amplitude||1;}
    Osc.prototype.update=function(){this.phase+=this.frequency;return this.offset+Math.sin(this.phase)*this.amplitude;};
    var co=new Osc({phase:Math.random()*2*Math.PI,amplitude:85,frequency:0.0015,offset:285});
    function Node(){this.x=0;this.y=0;this.vy=0;this.vx=0;}
    function Line(s){
      this.spring=s+0.1*Math.random()-0.02;this.friction=CFG.friction+0.01*Math.random()-0.002;this.nodes=[];
      for(var i=0;i<CFG.size;i++){var n=new Node();n.x=pos.x;n.y=pos.y;this.nodes.push(n);}
    }
    Line.prototype.update=function(){
      var sp=this.spring,p=this.nodes[0];p.vx+=(pos.x-p.x)*sp;p.vy+=(pos.y-p.y)*sp;
      for(var i=0;i<this.nodes.length;i++){var n=this.nodes[i];if(i>0){var q=this.nodes[i-1];n.vx+=(q.x-n.x)*sp;n.vy+=(q.y-n.y)*sp;n.vx+=q.vx*CFG.dampening;n.vy+=q.vy*CFG.dampening;}n.vx*=this.friction;n.vy*=this.friction;n.x+=n.vx;n.y+=n.vy;sp*=CFG.tension;}
    };
    Line.prototype.draw=function(){
      ctx2.beginPath();var n0=this.nodes[0];ctx2.moveTo(n0.x,n0.y);
      for(var i=1;i<this.nodes.length-2;i++){var e=this.nodes[i],t=this.nodes[i+1];ctx2.quadraticCurveTo(e.x,e.y,(e.x+t.x)/2,(e.y+t.y)/2);}
      var l=this.nodes[this.nodes.length-2],e=this.nodes[this.nodes.length-1];ctx2.quadraticCurveTo(l.x,l.y,e.x,e.y);ctx2.stroke();ctx2.closePath();
    };
    function cl(){lines=[];for(var i=0;i<CFG.trails;i++)lines.push(new Line(0.4+(i/CFG.trails)*0.025));}
    function rd(){
      if(!running)return;
      ctx2.globalCompositeOperation='source-over';ctx2.clearRect(0,0,cvs2.width,cvs2.height);ctx2.globalCompositeOperation='lighter';
      ctx2.strokeStyle='hsla('+Math.round(co.update())+',50%,50%,0.2)';ctx2.lineWidth=1;
      for(var i=0;i<lines.length;i++){lines[i].update();lines[i].draw();}requestAnimationFrame(rd);
    }
    function rs(){cvs2.width=window.innerWidth;cvs2.height=window.innerHeight;}
    function init(){
      cvs2=document.createElement('canvas');cvs2.id='mandiq-cursor-canvas';
      cvs2.style.cssText='position:fixed;top:0;left:0;width:100%;height:100%;pointer-events:none;z-index:9999;';
      document.body.appendChild(cvs2);ctx2=cvs2.getContext('2d');rs();cl();
      document.addEventListener('mousemove',function(e){pos.x=e.clientX;pos.y=e.clientY;},{passive:true});
      document.addEventListener('touchmove',function(e){if(e.touches.length){pos.x=e.touches[0].pageX;pos.y=e.touches[0].pageY;}},{passive:true});
      document.addEventListener('touchstart',function(e){if(e.touches.length){pos.x=e.touches[0].pageX;pos.y=e.touches[0].pageY;}},{passive:true});
      window.addEventListener('resize',rs);window.addEventListener('orientationchange',rs);
      document.addEventListener('visibilitychange',function(){if(document.hidden)running=false;else{running=true;rd()}});
      rd();
    }
    if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
  })();
})();
</script>"""
    st.markdown(html, unsafe_allow_html=True)
