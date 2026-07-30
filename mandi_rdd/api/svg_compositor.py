"""
SVG compositor — overlays live KPI badges onto the pipeline diagram SVG.

Pure string manipulation (no XML parser needed) — injects a badge panel
into the top-right region of any valid SVG element.

Usage:
    from mandi_rdd.api.svg_compositor import composite_kpi_svg

    with open("diagram.svg") as f:
        svg = f.read()

    metrics = {
        "n_prices": 1333993,
        "n_commodities": 303,
        "n_states": 36,
        "n_districts": 610,
        "n_rdd_results": 26,
        "n_forecast_models": 15,
        "last_hourly_outcome": "success",
        "last_hourly_new_rows": 14230,
    }

    composited = composite_kpi_svg(svg, metrics)
"""

from __future__ import annotations

from typing import Any

__all__ = ["composite_kpi_svg"]


def _fmt(n: int | None) -> str:
    """Format a number with commas, or return a dash."""
    if n is None:
        return "\u2014"
    return f"{n:,}"


def _badge_svg(
    x: float,
    y: float,
    width: float,
    height: float,
    value: str,
    label: str,
    value_color: str = "#d7ff00",
    label_color: str = "#bababa",
) -> str:
    """Return SVG for a single KPI badge."""
    pad = 8
    val_x = x + pad
    val_font_size = 13
    lbl_x = x + pad
    lbl_y = y + height - pad
    lbl_font_size = 10
    # Background rect
    bg_rx = 5
    return (
        f'  <rect x="{x}" y="{y}" width="{width}" height="{height}" '
        f'rx="{bg_rx}" fill="rgba(0,0,0,0.65)" stroke="rgba(255,255,255,0.08)" '
        f'stroke-width="0.5"/>\n'
        f'  <text x="{val_x}" y="{y + 20}" font-family="\'Barlow\',\'IBM Plex Mono\',monospace" '
        f'font-size="{val_font_size}" font-weight="600" fill="{value_color}">'
        f'{value}</text>\n'
        f'  <text x="{lbl_x}" y="{lbl_y}" font-family="\'IBM Plex Sans\',sans-serif" '
        f'font-size="{lbl_font_size}" fill="{label_color}" opacity="0.85">'
        f'{label}</text>\n'
    )


def _build_badge_panel(metrics: dict[str, Any]) -> str:
    """Build the SVG badge panel markup.

    Returns a ``<g>`` element containing all KPI badges, positioned at
    the top-right of a 1200-wide diagram canvas.
    """
    # Determine outcome status
    outcome = metrics.get("last_hourly_outcome")
    if outcome == "success":
        status_text = "OK"
        status_color = "#2ecc71"
    elif outcome:
        status_text = "FAIL"
        status_color = "#e74c3c"
    else:
        status_text = "\u2014"
        status_color = "#555"

    # Extract values
    prices = _fmt(metrics.get("n_prices"))
    commodities = _fmt(metrics.get("n_commodities"))
    states = _fmt(metrics.get("n_states"))
    districts = _fmt(metrics.get("n_districts"))
    rdd = _fmt(metrics.get("n_rdd_results"))
    forecast = _fmt(metrics.get("n_forecast_models"))
    rainfall = _fmt(metrics.get("n_rainfall", 0))
    ndvi = _fmt(metrics.get("n_ndvi", 0))
    new_rows = _fmt(metrics.get("last_hourly_new_rows", 0))
    mape_val = metrics.get("forecast_avg_mape")
    mape_str = f"{mape_val:.0f}%" if mape_val is not None else "\u2014"

    # Build the badge elements
    badge_w = 170
    badge_h = 44
    gap = 6
    panel_x = 1200 - badge_w - 16  # right-aligned with 16px padding
    panel_y = 16
    elements: list[str] = []

    # Title
    elements.append(
        f'  <text x="{panel_x + 8}" y="{panel_y + 15}" '
        f'font-family="\'Space Grotesk\',sans-serif" font-size="10" '
        f'font-weight="500" fill="#7e7e7e" letter-spacing="0.08em" '
        f'text-transform="uppercase">LIVE METRICS</text>\n'
    )

    # Badge rows (offset by title height)
    title_h = 22

    rows = [
        (prices, "price rows"),
        (f"{commodities} . {states}", "commodities . states"),
        (f"{districts} . {rdd}", "districts . RDD results"),
        (f"{forecast} ({mape_str})", "forecast models (avg MAPE)"),
        (f"~{rainfall} . {ndvi}", "rainfall . NDVI records"),
        (f"+{new_rows}", f"last hourly ({status_text})"),
    ]

    for i, (val, lbl) in enumerate(rows):
        by = panel_y + title_h + 4 + i * (badge_h + gap)
        elems = _badge_svg(panel_x, by, badge_w, badge_h, val, lbl)
        elements.append(elems)

    # Update the status color for the last badge's value
    # Patch the last badge's value color to reflect green/red outcome
    target = f'+{new_rows}'
    for i, e in enumerate(elements):
        if target in e:
            elements[i] = e.replace(
                'fill="#d7ff00"',
                f'fill="{status_color}"',
            )
            break

    # Build the panel group with a backdrop
    panel_height = title_h + 4 + len(rows) * (badge_h + gap)
    backdrop = (
        f'<g transform="translate(0,0)">\n'
        f'  <rect x="{panel_x - 4}" y="{panel_y}" '
        f'width="{badge_w + 8}" height="{panel_height + 6}" '
        f'rx="8" fill="rgba(0,0,0,0.4)" stroke="rgba(255,255,255,0.05)" '
        f'stroke-width="0.5"/>\n'
    )
    inner = "".join(elements)
    return backdrop + inner + "</g>\n"


def composite_kpi_svg(svg_content: str, metrics: dict[str, Any]) -> str:
    """Overlay live KPI badges onto a pipeline SVG.

    Injects the badge panel before the closing ``</svg>`` tag.
    Returns the composited SVG string.

    Args:
        svg_content: The base SVG markup.
        metrics: Dict with keys like ``n_prices``, ``n_commodities``, etc.

    Returns:
        SVG string with the badge panel injected.
    """
    if "</svg>" not in svg_content:
        msg = "Input does not contain a closing </svg> tag"
        raise ValueError(msg)

    panel = _build_badge_panel(metrics)
    composited = svg_content.replace("</svg>", panel + "\n</svg>")
    return composited
