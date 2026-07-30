"""
MandiIQ — Shared Plotly theming helper (PRD §6).

All 5 pages that render Plotly charts should call make_themed_figure()
instead of hand-declaring layout properties inline. This is the single
source of truth for: transparent backgrounds, on-palette fonts,
grid colors, and margin defaults.
"""

import plotly.graph_objects as go

# Palette shorthand (duplicated from theme.py to avoid circular imports
# if theme.py ever grows heavy — these are tiny constants).
INK   = "#000000"
PAPER = "#ffffff"
MUTED = "#bababa"


def make_themed_figure(
    height: int | None = None,
    show_legend: bool = True,
    margin: dict | None = None,
) -> go.Figure:
    """Return a plotly.graph_objects.Figure with the MandiIQ theme applied.

    Use as the base figure, then add_traces() on top. Or call
    fig.update_layout(make_themed_layout(...)) on an existing fig.

    Args:
        height: chart height in px. None = Plotly auto.
        show_legend: whether to show the legend.
        margin: override default margins. Defaults to compact.
    """
    fig = go.Figure()
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(
            family="IBM Plex Mono, monospace",
            color=PAPER,
            size=12,
        ),
        showlegend=show_legend,
        height=height,
        margin=margin or dict(l=40, r=20, t=30, b=40),
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor="rgba(0, 0, 0, 0.85)",
            bordercolor="rgba(215, 255, 0, 0.2)",
            font=dict(
                family="IBM Plex Mono, monospace",
                color=MUTED,
                size=11,
            ),
        ),
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            font=dict(color=MUTED, size=11),
        ),
        xaxis=dict(
            gridcolor="rgba(255,255,255,0.05)",
            zerolinecolor="rgba(255,255,255,0.1)",
        ),
        yaxis=dict(
            gridcolor="rgba(255,255,255,0.05)",
            zerolinecolor="rgba(255,255,255,0.1)",
        ),
    )
    return fig


def make_themed_layout(
    height: int | None = None,
    show_legend: bool = True,
    margin: dict | None = None,
) -> dict:
    """Return a layout dict for fig.update_layout() on an existing figure.

    Same args as make_themed_figure(). Use when you already have a fig
    (e.g. from px.line) and want to apply the theme.
    """
    return dict(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(
            family="IBM Plex Mono, monospace",
            color=PAPER,
            size=12,
        ),
        showlegend=show_legend,
        height=height,
        margin=margin or dict(l=40, r=20, t=30, b=40),
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor="rgba(0, 0, 0, 0.85)",
            bordercolor="rgba(215, 255, 0, 0.2)",
            font=dict(
                family="IBM Plex Mono, monospace",
                color=MUTED,
                size=11,
            ),
        ),
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            font=dict(color=MUTED, size=11),
        ),
        xaxis=dict(
            gridcolor="rgba(255,255,255,0.05)",
            zerolinecolor="rgba(255,255,255,0.1)",
        ),
        yaxis=dict(
            gridcolor="rgba(255,255,255,0.05)",
            zerolinecolor="rgba(255,255,255,0.1)",
        ),
    )


def inject_chart_theme():
    """Inject CSS + IntersectionObserver for Plotly chart animations.

    IDEMPOTENT: safe to call multiple times — JS flags prevent duplicate
    injection of the IntersectionObserver.  CSS is harmless duplicated.

    Applies:
    - .chart-frame (lighter glass card — transparent bg, hairline border, hovers to green)
    - .chart-reveal (clip-path inset transition on viewport entry)
    - .chart-hover-glow (gradient lime box-shadow on hover)
    - .chart-crosshair (lime corner markers on chart containers)

    Call once per session from the shell layout or each page render.
    """
    import streamlit as st

    key = "_mandiiq_chart_theme_injected"
    if st.session_state.get(key):
        return
    st.session_state[key] = True

    html = """<script>
(function() {
    'use strict';
    if (window.__mandiiqChartTheme) return;
    window.__mandiiqChartTheme = true;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

    // ── Shared IntersectionObserver for per-chart scroll reveal ──
    // Charts below the fold only get .is-visible when the user scrolls
    // to them, creating a sequential reveal instead of all-at-once.
    var OBSERVER_CONFIG = { threshold: 0.08, rootMargin: '0px 0px -5% 0px' };

    function getObserver() {
        if (!window.__mandiiqChartObserver) {
            window.__mandiiqChartObserver = new IntersectionObserver(function(entries) {
                entries.forEach(function(entry) {
                    if (entry.isIntersecting) {
                        entry.target.classList.add('is-visible');
                        window.__mandiiqChartObserver.unobserve(entry.target);
                    }
                });
            }, OBSERVER_CONFIG);
        }
        return window.__mandiiqChartObserver;
    }

    function init() {
        var observer = getObserver();
        var charts = document.querySelectorAll('.js-plotly-plot, .stPlotlyChart');
        charts.forEach(function(el) {
            // Find the outermost chart container
            var container = el.closest('.element-container, [data-testid="stBlock"]') || el.parentElement;
            if (!container) return;

            // Skip already-processed containers
            if (container.dataset.mandiqChartDone === 'true') return;
            container.dataset.mandiqChartDone = 'true';

            // Add chart frame + animation classes and watch for scroll reveal
            container.classList.add('chart-frame', 'chart-reveal', 'chart-hover-glow', 'chart-crosshair');
            observer.observe(container);
        });
    }

    // Run on load and Streamlit rerender
    if (document.readyState === 'complete' || document.readyState === 'interactive') {
        setTimeout(init, 300);
    } else {
        document.addEventListener('DOMContentLoaded', function() { setTimeout(init, 300); });
    }
    document.addEventListener('streamlit:render', function() {
        // Re-init catches charts rendered dynamically by Streamlit widgets
        // (tabs, selectboxes, etc.) without re-creating the observer
        setTimeout(init, 500);
    });
})();
</script>"""
    st.markdown(html, unsafe_allow_html=True)
