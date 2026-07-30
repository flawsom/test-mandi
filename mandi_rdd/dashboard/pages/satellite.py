"""
MandiIQ — Satellite View (NDVI) page.

District map colored by NDVI anomaly.
Side-by-side NDVI trend vs. rainfall trend — the cross-check from the system PRD.

Alche Studio Design: glass cards, interpretation boxes, glass KPI strip,
section labels, consistent monochrome-lime palette.
"""

import json as _json
import math
import numpy as np
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from mandi_rdd.dashboard.theme import (
    inject_theme, inject_webgl_hero, inject_countup_js, countup_card,
    TURMERIC, RUST, SAGE, SLATE, MUTED, FAINT, INK
)
from mandi_rdd.dashboard.plotly_theme import make_themed_figure

NDVI_JSON_PATH = Path(__file__).resolve().parent.parent.parent / 'data' / 'ndvi_latest.json'
COORDS_PATH = Path(__file__).resolve().parent.parent.parent.parent / 'data' / 'district_coords.json'


def _load_ndvi_records(district: str) -> list:
    """Load NDVI data from the git-tracked JSON export (fallback)."""
    if not NDVI_JSON_PATH.exists():
        return []
    try:
        with open(NDVI_JSON_PATH) as f:
            data = _json.load(f)
        records = data.get('records', [])
        if district:
            return [r for r in records if r.get('district') == district]
        return records
    except Exception:
        return []


def _compute_district_anomaly_map() -> tuple[pd.DataFrame, dict]:
    """Compute per-district NDVI anomaly and return (df, coords_dict).

    The anomaly is (latest_ndvi - avg_ndvi) / avg_ndvi * 100, showing
    how each district's current NDVI compares to its own historical
    average within the observed period.

    Returns an empty DataFrame if the query fails.
    """
    try:
        from mandi_rdd.storage.duckdb_store import get_connection
        conn = get_connection()
        df = conn.execute("""
            WITH district_stats AS (
                SELECT state, district,
                    AVG(ndvi) AS avg_ndvi,
                    STDDEV_SAMP(ndvi) AS std_ndvi,
                    COUNT(*) AS n_months
                FROM ndvi
                GROUP BY state, district
            ),
            latest AS (
                SELECT state, district, ndvi AS latest_ndvi
                FROM (
                    SELECT state, district, ndvi,
                        ROW_NUMBER() OVER (
                            PARTITION BY state, district ORDER BY date DESC
                        ) AS rn
                    FROM ndvi
                ) ranked
                WHERE rn = 1
            )
            SELECT ds.state, ds.district,
                ROUND(ds.avg_ndvi::FLOAT, 4) AS avg_ndvi,
                ROUND(l.latest_ndvi::FLOAT, 4) AS latest_ndvi,
                ROUND(((l.latest_ndvi - ds.avg_ndvi)
                    / NULLIF(ds.avg_ndvi, 0) * 100)::FLOAT, 1) AS anomaly_pct,
                ROUND(COALESCE(ds.std_ndvi::FLOAT, 0), 4) AS std_ndvi,
                ds.n_months
            FROM district_stats ds
            JOIN latest l
                ON LOWER(ds.state) = LOWER(l.state)
                AND LOWER(ds.district) = LOWER(l.district)
            ORDER BY ds.state, ds.district
        """).fetchdf()
        conn.close()
    except Exception:
        return pd.DataFrame(), {}

    # Load coordinates
    coords = {}
    if COORDS_PATH.exists():
        try:
            with open(COORDS_PATH) as f:
                coords = _json.load(f)
        except Exception:
            pass

    return df, coords


def _build_anomaly_map(
    df: pd.DataFrame,
    coords: dict,
) -> go.Figure:
    """Build a Plotly Scattergeo map of India with district-level NDVI anomaly.

    Each district is a marker positioned at its centroid (lat/lng from the
    coords cache), colored by anomaly percentage:
        Red (< -15%) → Yellow (0%) → Green (> +15%)
    Marker size is proportional to latest NDVI value.
    """
    if df.empty or not coords:
        fig = make_themed_figure(height=400)
        fig.add_annotation(
            text="No anomaly data available",
            showarrow=False,
            font=dict(color=MUTED, size=14),
        )
        return fig

    # Join NDVI data with coordinates — filter out any district with
    # missing/NaN coords or invalid NDVI/anomaly values that would produce
    # Plotly SVG transform errors ("Trailing garbage, NaN)" ).
    lats, lngs, labels, ndvi_vals, anomaly_vals, sizes = [], [], [], [], [], []
    for _, row in df.iterrows():
        key = f"{row['state']}|{row['district']}"
        coord = coords.get(key)
        # Strict coordinate check: must be a 2-element list/tuple with both values non-None
        if not coord or not isinstance(coord, (list, tuple)) or len(coord) != 2:
            continue
        # district_coords.json stores [lat, lng] — extract as lat_val, lng_val
        lat_val, lng_val = coord[0], coord[1]
        if lat_val is None or lng_val is None:
            continue
        if not (isinstance(lat_val, (int, float)) and isinstance(lng_val, (int, float))):
            continue
        if not (math.isfinite(float(lat_val)) and math.isfinite(float(lng_val))):
            continue

        # Skip districts with missing or NaN NDVI value
        ndvi = row.get('latest_ndvi')
        is_finite_ndvi = isinstance(ndvi, (int, float)) and math.isfinite(ndvi)
        if not is_finite_ndvi:
            continue

        # Skip districts with missing or NaN anomaly (NULL from SQL when avg_ndvi=0)
        anomaly = row.get('anomaly_pct')
        try:
            anomaly = float(anomaly)
        except (TypeError, ValueError):
            anomaly = 0.0
        else:
            if not math.isfinite(anomaly):
                anomaly = 0.0

        lngs.append(lng_val)
        lats.append(lat_val)
        ndvi_vals.append(ndvi)
        anomaly_vals.append(anomaly)
        sizes.append(max(5, min(22, 8 + ndvi * 25)))
        labels.append(
            f"<b>{row['district']}</b>, {row['state']}<br>"
            f"NDVI: {ndvi:.3f}  |  Avg: {row['avg_ndvi']:.3f}<br>"
            f"Anomaly: <b>{max(-99, min(99, anomaly)):+.1f}%</b>"
            f"  |  {int(row['n_months'])} months"
        )

    if not lats:
        fig = make_themed_figure(height=400)
        fig.add_annotation(text="No geocoded districts", showarrow=False,
                          font=dict(color=MUTED, size=14))
        return fig

    fig = go.Figure()

    fig.add_trace(go.Scattergeo(
        lon=lngs,
        lat=lats,
        mode='markers',
        marker=dict(
            size=sizes,
            color=anomaly_vals,
            colorscale=[
                [0.0, '#c0392b'],      # severe deficit - red
                [0.25, '#e67e22'],     # moderate deficit - orange
                [0.5, '#f1c40f'],      # neutral - yellow
                [0.75, '#27ae60'],     # moderate surplus - green
                [1.0, '#1a8a38'],      # strong surplus - dark green
            ],
            cmin=-30,
            cmax=30,
            colorbar=dict(
                title=dict(text="Anomaly %", font=dict(size=11, color='#bababa')),
                tickfont=dict(size=10, color='#bababa'),
                tickvals=[-30, -15, 0, 15, 30],
                ticktext=['<-30%', '-15%', '0%', '+15%', '>+30%'],
                outlinewidth=0,
                bgcolor='rgba(0,0,0,0)',
            ),
            showscale=True,
            line=dict(width=0.5, color='rgba(255,255,255,0.15)'),
            opacity=0.85,
            symbol='circle',
        ),
        text=labels,
        hoverinfo='text',
        hoverlabel=dict(
            bgcolor='#1a1d28',
            bordercolor='rgba(255,255,255,0.15)',
            font=dict(family='IBM Plex Mono', size=11, color='#ffffff'),
        ),
        name='NDVI Anomaly',
    ))

    fig.update_geos(
        projection_type='mercator',
        scope='asia',
        showland=True,
        landcolor='rgba(255,255,255,0.02)',
        showcountries=True,
        countrycolor='rgba(255,255,255,0.08)',
        showsubunits=True,
        subunitcolor='rgba(255,255,255,0.05)',
        showocean=True,
        oceancolor='rgba(0,0,0,0)',
        showframe=False,
        lataxis=dict(range=[6, 36]),
        lonaxis=dict(range=[67, 98]),
        coastlinecolor='rgba(255,255,255,0.08)',
    )

    fig.update_layout(
        template='plotly_dark',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=0, r=0, t=0, b=0),
        height=520,
        geo=dict(
            bgcolor='rgba(0,0,0,0)',
            lakecolor='rgba(0,0,0,0)',
            rivercolor='rgba(0,0,0,0)',
        ),
        dragmode='zoom',
    )

    return fig


def _build_ndvi_rainfall_scatter() -> go.Figure:
    """Build a scatter plot of district-level NDVI vs subdivision rainfall.

    Each point is a district. X-axis = avg rainfall (mm/month) for the
    district's IMD subdivision. Y-axis = avg NDVI. A trend line (OLS)
    and Pearson r annotation show the strength of the relationship.
    """
    try:
        from mandi_rdd.storage.duckdb_store import get_connection
        conn = get_connection()
        df = conn.execute("""
            WITH ndvi_monthly AS (
                SELECT n.state, n.district,
                    YEAR(n.date) AS y, MONTH(n.date) AS m,
                    AVG(n.ndvi) AS avg_ndvi
                FROM ndvi n
                GROUP BY n.state, n.district, YEAR(n.date), MONTH(n.date)
            ),
            matched AS (
                SELECT nm.*, dm.sub_division, r.rainfall_mm, r.departure_pct
                FROM ndvi_monthly nm
                JOIN district_map dm
                    ON LOWER(nm.state) = LOWER(dm.state)
                    AND LOWER(nm.district) = LOWER(dm.district)
                LEFT JOIN rainfall r
                    ON r.sub_division = dm.sub_division
                    AND r.year = nm.y
                    AND r.month = nm.m
                WHERE r.rainfall_mm IS NOT NULL AND nm.avg_ndvi IS NOT NULL
            ),
            district_agg AS (
                SELECT state, district, sub_division,
                    ROUND(AVG(avg_ndvi)::FLOAT, 4) AS mean_ndvi,
                    ROUND(AVG(rainfall_mm)::FLOAT, 2) AS mean_rain_mm,
                    ROUND(AVG(departure_pct)::FLOAT, 1) AS mean_dep_pct,
                    COUNT(*) AS n_months
                FROM matched
                GROUP BY state, district, sub_division
            )
            SELECT * FROM district_agg
            WHERE mean_rain_mm IS NOT NULL AND n_months >= 2
            ORDER BY mean_rain_mm DESC
        """).fetchdf()
        conn.close()
    except Exception as e:
        fig = make_themed_figure(height=400)
        fig.add_annotation(text=f"Query failed: {e}", showarrow=False,
                          font=dict(color=MUTED, size=12))
        return fig

    if df.empty or len(df) < 5:
        fig = make_themed_figure(height=400)
        fig.add_annotation(text="Insufficient data for correlation plot", showarrow=False,
                          font=dict(color=MUTED, size=12))
        return fig

    # Compute Pearson r and OLS trend line using numpy
    x = df['mean_rain_mm'].values.astype(float)
    y = df['mean_ndvi'].values.astype(float)

    n = len(x)
    # Pearson r — numpy.corrcoef handles floating-point edge cases
    corr_matrix = np.corrcoef(x, y)
    r = corr_matrix[0, 1] if not np.isnan(corr_matrix[0, 1]) else 0.0

    # OLS slope + intercept — numpy.polyfit with deg=1
    if np.var(x) > 1e-15:  # guard against zero-variance
        coeffs = np.polyfit(x, y, 1)
        slope, intercept = coeffs[0], coeffs[1]
    else:
        slope, intercept = 0.0, y.mean()

    # Trend line values
    x_sorted = sorted(x)
    y_trend = [slope * xi + intercept for xi in x_sorted]

    # Color by subdivision
    unique_subdivs = df['sub_division'].unique().tolist()
    color_palette = ['#d7ff00', '#3b82f6', '#ef4444', '#8b5cf6', '#f59e0b',
                     '#10b981', '#ec4899', '#06b6d4', '#84cc16', '#f97316',
                     '#6366f1', '#14b8a6', '#a855f7', '#e11d48', '#0ea5e9',
                     '#65a30d', '#d946ef', '#0891b2', '#ca8a04', '#2563eb',
                     '#059669', '#9333ea', '#dc2626', '#0284c7', '#4d7c0f',
                     '#c026d3', '#0d9488', '#a16207', '#1d4ed8', '#65a30d']
    color_map = {s: color_palette[i % len(color_palette)] for i, s in enumerate(unique_subdivs)}

    fig = go.Figure()

    # Scatter points
    for subdiv in unique_subdivs:
        subset = df[df['sub_division'] == subdiv]
        fig.add_trace(go.Scatter(
            x=subset['mean_rain_mm'],
            y=subset['mean_ndvi'],
            mode='markers',
            name=subdiv,
            marker=dict(
                color=color_map[subdiv],
                size=7,
                opacity=0.7,
                line=dict(width=0.3, color='rgba(255,255,255,0.2)'),
            ),
            text=subset.apply(
                lambda r: (
                    f"<b>{r['district']}</b>, {r['state']}<br>"
                    f"NDVI: {r['mean_ndvi']:.3f}  |  Rain: {r['mean_rain_mm']:.0f}mm<br>"
                    f"Departure: {r['mean_dep_pct']:+.0f}%  |  Subdiv: {r['sub_division']}"
                ) if not pd.isna(r['mean_dep_pct']) else (
                    f"<b>{r['district']}</b>, {r['state']}<br>"
                    f"NDVI: {r['mean_ndvi']:.3f}  |  Rain: {r['mean_rain_mm']:.0f}mm<br>"
                    f"Departure: N/A  |  Subdiv: {r['sub_division']}"
                ),
                axis=1
            ),
            hoverinfo='text',
            hoverlabel=dict(
                bgcolor='#1a1d28',
                bordercolor='rgba(255,255,255,0.15)',
                font=dict(family='IBM Plex Mono', size=10, color='#ffffff'),
            ),
            showlegend=False,
        ))

    # Trend line
    fig.add_trace(go.Scatter(
        x=x_sorted,
        y=y_trend,
        mode='lines',
        name=f'Trend (r={r:.3f})',
        line=dict(color='rgba(255,255,255,0.5)', width=1.5, dash='dash'),
        showlegend=False,
    ))

    fig.update_layout(
        template='plotly_dark',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=0, r=0, t=10, b=0),
        height=380,
        xaxis=dict(
            title=dict(text='Avg Rainfall (mm/month)', font=dict(color=MUTED, size=11)),
            gridcolor='rgba(255,255,255,0.05)',
            zerolinecolor='rgba(255,255,255,0.1)',
            tickfont=dict(color=MUTED, size=10),
        ),
        yaxis=dict(
            title=dict(text='Avg NDVI', font=dict(color=MUTED, size=11)),
            gridcolor='rgba(255,255,255,0.05)',
            zerolinecolor='rgba(255,255,255,0.1)',
            tickfont=dict(color=MUTED, size=10),
        ),
        annotations=[
            dict(
                xref='paper', yref='paper',
                x=0.98, y=0.98,
                text=f'<b>r = {r:.3f}</b>  (n={n} districts)',
                showarrow=False,
                font=dict(family='IBM Plex Mono', size=12, color='#d7ff00'),
                bgcolor='rgba(0,0,0,0.5)',
                bordercolor='rgba(255,255,255,0.1)',
                borderwidth=1,
                borderpad=6,
            ),
            # Subdivision legend as annotation (top-left, smaller text)
            dict(
                xref='paper', yref='paper',
                x=0.02, y=0.98,
                text=f'{len(unique_subdivs)} subdivisions shown',
                showarrow=False,
                font=dict(family='IBM Plex Mono', size=9, color=MUTED),
            ),
        ],
    )

    return fig


def render():
    inject_theme()
    inject_webgl_hero()
    st.markdown("""
        <div class="page-hero" style="margin-bottom:2rem;">
          <div>
            <div style="font-family:'IBM Plex Mono',monospace;font-size:0.75rem;color:#d7ff00;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:0.5rem;">
              Satellite Imagery
            </div>
            <h1 class="hero-title" style="font-family:'Space Grotesk',system-ui,sans-serif;font-weight:300;font-size:clamp(1.6rem,3vw,2.4rem);color:#ffffff;letter-spacing:0.03em;text-transform:uppercase;margin-bottom:0.5rem;">
              Satellite View — NDVI Analysis
            </h1>
            <p style="color:#7e7e7e;max-width:680px;line-height:1.7;font-size:0.9rem;">
                Vegetation health from Sentinel-2 satellite imagery. NDVI (Normalized Difference
                Vegetation Index) measures crop vigor — lower values indicate stress, potentially
                from drought or disease. Cross-check against rainfall to distinguish causes.
            </p>
          </div>
        </div>
    """, unsafe_allow_html=True)

    # ── Compute anomaly map data ──
    anomaly_df, coords = _compute_district_anomaly_map()

    # ── NDVI Anomaly Map ──
    st.markdown("""
        <div style="font-family:'IBM Plex Mono',monospace;font-size:0.75rem;color:#d7ff00;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:0.5rem;">
          MAP
        </div>
        <h2 style="font-family:'Space Grotesk',system-ui,sans-serif;font-weight:400;font-size:1.3rem;color:#ffffff;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:1rem;">
          NDVI Anomaly Map
        </h2>
    """, unsafe_allow_html=True)

    if not anomaly_df.empty:
        map_fig = _build_anomaly_map(anomaly_df, coords)
        st.markdown('<div class="glass" style="padding:1rem;">', unsafe_allow_html=True)
        st.plotly_chart(map_fig, use_container_width=True, config={
            'displayModeBar': False,
            'scrollZoom': False,
            'staticPlot': False,
        })
        st.markdown('</div>', unsafe_allow_html=True)

        # KPI strip below the map — use .dropna() on anomaly_pct to protect
        # against NULL/NaN values that would produce SVG transform errors in Plotly
        _anom_clean = anomaly_df['anomaly_pct'].dropna()
        total = len(anomaly_df)
        stressed = int((_anom_clean < -10).sum()) if len(_anom_clean) else 0
        healthy = int((_anom_clean > 10).sum()) if len(_anom_clean) else 0
        mean_anom = _anom_clean.mean()

        inject_countup_js()
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown(countup_card("Districts Tracked", total), unsafe_allow_html=True)
        with col2:
            st.markdown(countup_card("Stressed (anom < -10%)", stressed), unsafe_allow_html=True)
        with col3:
            st.markdown(countup_card("Healthy (anom > +10%)", healthy), unsafe_allow_html=True)
        with col4:
            _mean_valid = isinstance(mean_anom, float) and math.isfinite(mean_anom)
            st.markdown(countup_card("Mean Anomaly", round(mean_anom, 1) if _mean_valid else None, suffix="%"), unsafe_allow_html=True)

        stress_pct = 100 * stressed // total if total else 0
        st.markdown(f"""
            <div class="interpretation-box">
                <strong>Map interpretation:</strong> {stressed} of {total} tracked districts
                ({stress_pct}%) show NDVI anomaly below −10%, indicating vegetation stress.
                Red markers signal potential drought or crop health issues; green markers
                indicate healthy or improving vegetation. Marker intensity is proportional
                to deviation from each district's seasonal baseline.
            </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
            <div class="glass" style="padding:2rem;text-align:center;">
                <h3 style="color:#bababa;margin-top:0;font-size:1.1rem;">No NDVI data available</h3>
                <p style="color:#7e7e7e;font-size:0.85rem;">
                    Satellite imagery requires Sentinel Hub credentials.
                </p>
                <p style="color:#7e7e7e;font-size:0.75rem;">
                    Set <strong>SENTINEL_CLIENT_ID</strong> and <strong>SENTINEL_CLIENT_SECRET</strong>
                    to enable satellite data ingestion.<br/>
                    Get free tier at <a href="https://www.sentinel-hub.com/pricing/" style="color:#d7ff00;">sentinel-hub.com</a>
                </p>
            </div>
        """, unsafe_allow_html=True)

    if anomaly_df.empty:
        return

    # ── NDVI vs Rainfall Correlation Scatter ──
    st.markdown("""
        <div style="margin-top:1.5rem;">
          <div style="font-family:'IBM Plex Mono',monospace;font-size:0.75rem;color:#d7ff00;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:0.5rem;">
            02 / Correlation
          </div>
          <h2 style="font-family:'Space Grotesk',system-ui,sans-serif;font-weight:400;font-size:1.3rem;color:#ffffff;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:1rem;">
            NDVI vs. Rainfall
          </h2>
        </div>
    """, unsafe_allow_html=True)

    with st.spinner("Computing NDVI–rainfall correlation…"):
        scatter_fig = _build_ndvi_rainfall_scatter()
    st.markdown('<div class="glass" style="padding:1rem;">', unsafe_allow_html=True)
    st.plotly_chart(scatter_fig, use_container_width=True, config={
        'displayModeBar': False,
        'scrollZoom': True,
        'staticPlot': False,
    })
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("""
        <div class="interpretation-box">
            <strong>Scatter interpretation:</strong> Each dot is a district. A positive slope
            (rising trend line) means districts with more rain tend to have greener
            vegetation — the expected pattern. A flat or negative slope suggests irrigation
            or dry-season cropping dominates. The <strong>r</strong> value is the Pearson
            correlation coefficient; values near +1 or −1 indicate a strong linear
            relationship.
        </div>
    """, unsafe_allow_html=True)

    # ── District selector ──
    districts = None
    db_error = False
    try:
        from mandi_rdd.storage.duckdb_store import get_connection
        conn = get_connection()
        result = conn.execute("SELECT DISTINCT district FROM ndvi ORDER BY district").fetchall()
        if result:
            districts = [r[0] for r in result]
        conn.close()
    except Exception:
        db_error = True

    if (not districts or db_error) and not anomaly_df.empty:
        districts = sorted(anomaly_df['district'].unique().tolist())

    if not districts:
        st.markdown("""
            <div class="glass" style="padding:1.5rem;text-align:center;border-color:#D9663B;">
                <p style="color:#bababa;margin:0;font-size:0.9rem;">
                    ⚠ Data source unavailable — unable to load district list.
                </p>
            </div>
        """, unsafe_allow_html=True)
        return

    selected_district = st.selectbox("Select District", districts)

    # ── Try to load NDVI + Rainfall time series ──
    ndvi_df = None
    rainfall_df = None

    try:
        from mandi_rdd.storage.duckdb_store import get_connection
        conn = get_connection()

        try:
            ndvi_df = conn.execute("""
                SELECT date, ndvi, anomaly
                FROM ndvi
                WHERE LOWER(district) = LOWER(?)
                ORDER BY date
            """, [selected_district]).fetchdf()
        except Exception:
            ndvi_df = None

        # Rainfall: joined through district_map since rainfall table uses sub_division
        try:
            rainfall_df = conn.execute("""
                SELECT DISTINCT r.year, r.month,
                    r.rainfall_mm, r.departure_pct
                FROM rainfall r
                JOIN district_map dm ON r.sub_division = dm.sub_division
                WHERE LOWER(dm.district) = LOWER(?)
                ORDER BY r.year, r.month
            """, [selected_district]).fetchdf()
            if not rainfall_df.empty:
                # Build a synthetic date column from year+month
                rainfall_df['date'] = pd.to_datetime(
                    rainfall_df['year'].astype(str) + '-' + rainfall_df['month'].astype(str) + '-01'
                )
                rainfall_df = rainfall_df.sort_values('date')
        except Exception:
            rainfall_df = None

        conn.close()
    except Exception:
        pass

    if ndvi_df is None or len(ndvi_df) == 0:
        st.markdown(f"""
            <div class="glass" style="padding:1.5rem;text-align:center;">
                <p style="color:#7e7e7e;font-size:0.85rem;">
                    No NDVI time series available for <strong>{selected_district}</strong>.
                </p>
            </div>
        """, unsafe_allow_html=True)
        return

    # ── NDVI Summary (glass KPI strip) ──
    st.markdown("""
        <div style="margin-top:1.5rem;">
          <div style="font-family:'IBM Plex Mono',monospace;font-size:0.75rem;color:#d7ff00;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:0.8rem;">
            VEGETATION HEALTH
          </div>
        </div>
    """, unsafe_allow_html=True)
    inject_countup_js()
    st.markdown('<div class="crosshair-panel glass" style="padding:1rem;">', unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    with col1:
        latest_ndvi = ndvi_df.iloc[-1]["ndvi"] if len(ndvi_df) > 0 else None
        st.markdown(countup_card("Current NDVI", round(latest_ndvi, 2) if latest_ndvi else None), unsafe_allow_html=True)
    with col2:
        district_row = anomaly_df[
            (anomaly_df['district'].str.lower() == selected_district.lower())
        ]
        computed_anomaly = None
        if not district_row.empty:
            computed_anomaly = district_row.iloc[0]['anomaly_pct']
        st.markdown(countup_card("NDVI Anomaly", round(computed_anomaly, 1) if computed_anomaly is not None else None, suffix="%"), unsafe_allow_html=True)
    with col3:
        avg_ndvi = ndvi_df["ndvi"].mean()
        st.markdown(countup_card("Avg NDVI (Historical)", round(avg_ndvi, 2) if avg_ndvi else None), unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # ── NDVI Trend Chart ──
    st.markdown("""
        <div style="margin-top:1.5rem;">
          <div style="font-family:'IBM Plex Mono',monospace;font-size:0.75rem;color:#d7ff00;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:0.5rem;">
            03 / Trend
          </div>
          <h2 style="font-family:'Space Grotesk',system-ui,sans-serif;font-weight:400;font-size:1.3rem;color:#ffffff;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:1rem;">
            NDVI Trend
          </h2>
        </div>
    """, unsafe_allow_html=True)

    fig = make_themed_figure()
    fig.add_trace(go.Scatter(
        x=ndvi_df["date"],
        y=ndvi_df["ndvi"],
        mode="lines+markers",
        name="NDVI",
        line=dict(color=SAGE, width=2),
        marker=dict(size=5, color=SAGE),
    ))

    if "anomaly" in ndvi_df.columns:
        fig.add_hline(
            y=ndvi_df["ndvi"].mean(),
            line_dash="dash",
            line_color=MUTED,
            annotation_text="Historical mean",
            annotation_position="right",
        )

    fig.update_layout(
        yaxis_title="NDVI",
        margin=dict(l=0, r=0, t=10, b=0),
        height=300,
    )
    st.markdown('<div class="crosshair-panel glass" style="padding:1rem;">', unsafe_allow_html=True)
    st.plotly_chart(fig, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # ── Side-by-side: NDVI vs Rainfall ──
    if rainfall_df is not None and len(rainfall_df) > 0:
        st.markdown("""
            <div style="margin-top:1.5rem;">
              <div style="font-family:'IBM Plex Mono',monospace;font-size:0.75rem;color:#d7ff00;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:0.5rem;">
                04 / Cross-Check
              </div>
              <h2 style="font-family:'Space Grotesk',system-ui,sans-serif;font-weight:400;font-size:1.3rem;color:#ffffff;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:1rem;">
                NDVI vs. Rainfall Time Series
              </h2>
            </div>
        """, unsafe_allow_html=True)

        col1, col2 = st.columns(2)

        with col1:
            st.markdown('<div class="glass" style="padding:0.8rem;">', unsafe_allow_html=True)
            fig1 = make_themed_figure()
            fig1.add_trace(go.Scatter(
                x=ndvi_df["date"],
                y=ndvi_df["ndvi"],
                mode="lines",
                name="NDVI",
                line=dict(color=SAGE, width=2),
            ))
            fig1.update_layout(
                margin=dict(l=0, r=0, t=10, b=0),
                height=250,
                showlegend=False,
            )
            st.plotly_chart(fig1, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

        with col2:
            st.markdown('<div class="glass" style="padding:0.8rem;">', unsafe_allow_html=True)
            fig2 = make_themed_figure()
            fig2.add_trace(go.Scatter(
                x=rainfall_df["date"],
                y=rainfall_df["rainfall_mm"],
                mode="lines",
                name="Rainfall",
                line=dict(color="#8FAE89", width=2),
            ))
            fig2.update_layout(
                margin=dict(l=0, r=0, t=10, b=0),
                height=250,
                showlegend=False,
            )
            st.plotly_chart(fig2, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

        # Interpretation
        st.markdown("""
            <div class="interpretation-box">
                <strong>Cross-check interpretation:</strong> When NDVI declines coincide with
                rainfall deficit, the cause is likely drought stress. If NDVI drops while
                rainfall is normal, investigate other factors (pest, disease, soil).
            </div>
        """, unsafe_allow_html=True)

    # ── NDVI Anomaly Legend ──
    st.markdown("<hr style='border-color:rgba(255,255,255,0.07);margin:1.5rem 0;'>", unsafe_allow_html=True)
    st.markdown(f"""
    <div style="display:flex;gap:1.5rem;color:{MUTED};font-size:0.8rem;flex-wrap:wrap;">
        <div><span style="color:#1a8a38;">●</span> +15%+ = Strong surplus</div>
        <div><span style="color:#27ae60;">●</span> +5 to +15% = Mild surplus</div>
        <div><span style="color:#f1c40f;">●</span> −5 to +5% = Near baseline</div>
        <div><span style="color:#e67e22;">●</span> −15 to −5% = Mild deficit</div>
        <div><span style="color:#c0392b;">●</span> &lt;−15% = Severe deficit</div>
    </div>
    <p style="color:{FAINT};font-size:0.75rem;margin-top:0.5rem;">
        Anomaly = (latest NDVI − seasonal avg) ÷ seasonal avg × 100.
        Data source: Sentinel-2 / Copernicus Programme.
    </p>
    """, unsafe_allow_html=True)
