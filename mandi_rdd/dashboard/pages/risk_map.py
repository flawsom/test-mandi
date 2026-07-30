"""
MandiIQ — Risk Map page.

Full district ledger with pagination, sortable by rainfall deficit or price change.
Optional choropleth-style grid visualization.

Alche Studio Design: glass cards, interpretation boxes, section labels,
consistent monochrome-lime palette.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

import streamlit as st
import pandas as pd
from mandi_rdd.dashboard.theme import (
    inject_theme, inject_webgl_hero, inject_countup_js, countup_card,
    TURMERIC, RUST, SAGE, SLATE, MUTED, FAINT,
    render_ledger_table, commodity_color
)


@st.cache_data(ttl=120, show_spinner=False)
def _cached_district_ledger():
    """Cached DuckDB query for the risk map district ledger.

    Pagination triggers st.rerun() which re-executes render(); this cache
    prevents a full SQL GROUP BY + JOIN scan on every page click.
    Stale after 120s — fresh enough for auto-ingestion updates.
    Connection always closed via finally (matching executive_overview pattern).
    """
    from mandi_rdd.storage.duckdb_store import get_connection
    try:
        conn = get_connection()
        try:
            price_count = conn.execute("SELECT COUNT(*) FROM prices").fetchone()[0]
            if price_count <= 0:
                return None
            return conn.execute("""
                SELECT
                    p.district,
                    p.commodity,
                    AVG(p.modal_price) as avg_price,
                    AVG(r.departure_pct) as rainfall_deficit,
                    NULL as price_change
                FROM prices p
                LEFT JOIN district_map dm ON p.district = dm.district
                LEFT JOIN rainfall r ON dm.sub_division = r.sub_division
                GROUP BY p.district, p.commodity
                ORDER BY rainfall_deficit DESC NULLS LAST
            """).fetchdf()
        finally:
            conn.close()
    except Exception:
        return None


def render():
    inject_theme()
    inject_webgl_hero()
    st.markdown("""
        <div class="page-hero" style="margin-bottom:2rem;">
          <div>
            <div style="font-family:'IBM Plex Mono',monospace;font-size:0.75rem;color:#d7ff00;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:0.5rem;">
              District Intelligence
            </div>
            <h1 class="hero-title" style="font-family:'Space Grotesk',system-ui,sans-serif;font-weight:300;font-size:clamp(1.6rem,3vw,2.4rem);color:#ffffff;letter-spacing:0.03em;text-transform:uppercase;margin-bottom:0.5rem;">
              Risk Map — District Overview
            </h1>
            <p style="color:#7e7e7e;max-width:680px;line-height:1.7;font-size:0.9rem;">
              All districts with rainfall deficit or price anomalies. Sort by risk tier,
              rainfall deficiency, or price change. Click a district to drill down.
            </p>
          </div>
        </div>
    """, unsafe_allow_html=True)

    # ── Filters ──
    available_commodities = ["All"]
    try:
        from mandi_rdd.storage.duckdb_store import get_connection, get_curated_commodities
        conn = get_connection()
        result = get_curated_commodities()
        if result:
            available_commodities = ["All"] + [r.title() for r in result]
        conn.close()
    except Exception:
        pass

    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        commodity_filter = st.selectbox(
            "Commodity",
            available_commodities,
            label_visibility="collapsed",
        )
    with col2:
        sort_by = st.selectbox(
            "Sort by",
            ["Risk Tier", "Rainfall Deficit", "Price Change"],
            label_visibility="collapsed",
        )
    with col3:
        tier_filter = st.selectbox(
            "Tier",
            ["All", "High", "Medium", "Low"],
            label_visibility="collapsed",
        )

    # ── Try to load real data (cached 120s — pagination doesn't re-fetch) ──
    df = _cached_district_ledger()

    # ── Empty state (glass card) ──
    if df is None or len(df) == 0:
        st.markdown("""
            <div class="glass" style="padding:2rem;text-align:center;">
                <h3 style="color:#bababa;margin-top:0;font-size:1.1rem;">No districts in the database</h3>
                <p style="color:#7e7e7e;font-size:0.85rem;">
                    Run the ingestion pipeline to populate district data:<br/>
                    <code style="color:#d7ff00;">python -m mandi_rdd.ingestion.ingest</code>
                </p>
                <p style="color:#7e7e7e;font-size:0.75rem;">
                    Requires <strong>DATA_GOV_IN_API_KEY</strong> — get one free at
                    <a href="https://api.data.gov.in/manage" style="color:#d7ff00;">api.data.gov.in</a>
                </p>
            </div>
        """, unsafe_allow_html=True)
        return

    # ── Apply filters ──
    if commodity_filter != "All":
        df = df[df["commodity"] == commodity_filter]

    def get_tier(deficit):
        if deficit is None or (isinstance(deficit, float) and deficit != deficit):
            return "No Data"
        if deficit >= 19:
            return "High"
        elif deficit >= 10:
            return "Medium"
        else:
            return "Low"

    df["risk_tier"] = df["rainfall_deficit"].apply(get_tier)

    if tier_filter != "All":
        df = df[df["risk_tier"] == tier_filter]

    # ── Sort ──
    if sort_by == "Rainfall Deficit":
        df = df.sort_values("rainfall_deficit", ascending=False)
    elif sort_by == "Price Change":
        df = df.sort_values("price_change", ascending=False, key=abs)
    else:  # Risk Tier
        tier_order = {"High": 0, "Medium": 1, "Low": 2}
        df = df.sort_values("risk_tier", key=lambda x: x.map(tier_order))

    # ── Summary stats (glass KPI strip) ──
    inject_countup_js()
    st.markdown('<div class="crosshair-panel glass" style="padding:1rem;">', unsafe_allow_html=True)
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(countup_card("Total Districts", len(df), fmt="us"), unsafe_allow_html=True)
    with col2:
        high_risk = len(df[df["risk_tier"] == "High"])
        st.markdown(countup_card("High Risk", high_risk), unsafe_allow_html=True)
    with col3:
        avg_deficit = df["rainfall_deficit"].mean()
        if not pd.isna(avg_deficit):
            st.markdown(countup_card("Avg Rainfall Deficit", round(avg_deficit, 1), suffix="%"), unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="countup-card"><div class="countup-label">Avg Rainfall Deficit</div><div class="countup-value">—</div></div>', unsafe_allow_html=True)
    with col4:
        st.markdown(countup_card("Commodities", df['commodity'].nunique()), unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # ── Risk Tier Distribution grid ──
    st.markdown("""
        <div style="margin-top:2rem;">
          <div style="font-family:'IBM Plex Mono',monospace;font-size:0.75rem;color:#d7ff00;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:0.5rem;">
            CROSSHAIR
          </div>
          <h2 style="font-family:'Space Grotesk',system-ui,sans-serif;font-weight:400;font-size:1.3rem;color:#ffffff;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:1rem;">
            Risk Tier Distribution
          </h2>
        </div>
    """, unsafe_allow_html=True)

    # Create a simple grid view
    cols_per_row = 6
    rows = [df[i:i+cols_per_row] for i in range(0, min(len(df), 24), cols_per_row)]

    for row_df in rows:
        cols = st.columns(cols_per_row)
        for idx, (_, district) in enumerate(row_df.iterrows()):
            if idx >= len(cols):
                break
            with cols[idx]:
                tier = district["risk_tier"]
                tier_color = RUST if tier == "High" else (TURMERIC if tier == "Medium" else (MUTED if tier == "No Data" else SAGE))
                deficit = district["rainfall_deficit"]

                st.markdown(f"""
                <div style="background:rgba(10,10,10,0.85);border:1px solid {tier_color};
                            border-radius:8px;padding:0.75rem;text-align:center;">
                    <div style="color:#ffffff;font-weight:500;font-size:0.85rem;
                                white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
                        {district['district']}
                    </div>
                    <div style="color:{tier_color};font-family:'IBM Plex Mono',monospace;
                                font-size:0.9rem;margin-top:0.25rem;">
                        {'No Data' if pd.isna(deficit) else '{:.2f}%'.format(deficit)}
                    </div>
                    <div style="color:{MUTED};font-size:0.7rem;margin-top:0.25rem;">
                        {tier} Risk
                    </div>
                </div>
                """, unsafe_allow_html=True)

    # ── Full ledger table ──
    st.markdown("""
        <div style="margin-top:2rem;">
          <div style="font-family:'IBM Plex Mono',monospace;font-size:0.75rem;color:#d7ff00;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:0.5rem;">
            LEDGER
          </div>
          <h2 style="font-family:'Space Grotesk',system-ui,sans-serif;font-weight:400;font-size:1.3rem;color:#ffffff;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:1rem;">
            District Ledger
          </h2>
        </div>
    """, unsafe_allow_html=True)

    # Pagination — rows per page (persisted in session state)
    if "risk_map_page_size" not in st.session_state:
        st.session_state.risk_map_page_size = 20
    _risk_page_size = st.session_state.risk_map_page_size
    total_pages = max(1, (len(df) + _risk_page_size - 1) // _risk_page_size)

    if "risk_map_page" not in st.session_state:
        st.session_state.risk_map_page = 0
    # Clamp page when filters change (dataframe shrinks)
    if st.session_state.risk_map_page >= total_pages:
        st.session_state.risk_map_page = max(0, total_pages - 1)

    page = st.session_state.risk_map_page
    start_idx = page * _risk_page_size
    end_idx = start_idx + _risk_page_size
    page_df = df.iloc[start_idx:end_idx].copy()

    # Format for display
    page_df["rainfall_deficit"] = page_df["rainfall_deficit"].apply(lambda x: "No Data" if pd.isna(x) else f"{x:.1f}%")
    page_df["avg_price"] = page_df["avg_price"].apply(lambda x: f"₹{x:,.0f}" if pd.notna(x) else "—")
    page_df = page_df[["district", "commodity", "risk_tier", "rainfall_deficit", "avg_price"]]
    page_df.columns = ["District", "Commodity", "Risk Tier", "Rainfall Deficit", "Avg Price"]

    render_ledger_table(page_df, commodity_col="Commodity")

    # ── Rows per page selector (always visible when there's data) ──
    _rp1, _rp2 = st.columns([2, 4])
    with _rp1:
        _new_size = st.selectbox(
            "Rows per page",
            [10, 20, 50, 100],
            index=[10, 20, 50, 100].index(st.session_state.risk_map_page_size),
            key="risk_map_rpp",
            label_visibility="collapsed",
        )
        if _new_size != st.session_state.risk_map_page_size:
            st.session_state.risk_map_page_size = _new_size
            st.session_state.risk_map_page = 0
            st.rerun()
    with _rp2:
        st.markdown(
            f'<div style="text-align:right;padding-top:0.3rem;">'
            f'<span style="color:{MUTED};font-size:0.8rem;font-family:IBM Plex Mono,monospace;">'
            f'Page {page + 1} of {total_pages}'
            f'<span style="color:#555555;margin-left:8px;">({len(df):,} rows)</span>'
            f'</span></div>',
            unsafe_allow_html=True,
        )

    # Pagination navigation buttons
    if total_pages > 1:
        cols = st.columns([1, 1, 2, 1, 1])
        with cols[0]:
            if st.button("⏮ First", disabled=(page == 0), use_container_width=True):
                st.session_state.risk_map_page = 0
                st.rerun()
        with cols[1]:
            if st.button("← Prev", disabled=(page == 0), use_container_width=True):
                st.session_state.risk_map_page = max(0, page - 1)
                st.rerun()
        with cols[2]:
            # Page jump: show current page in a number input
            jump_to = st.number_input(
                "Jump to page",
                min_value=1,
                max_value=total_pages,
                value=page + 1,
                step=1,
                label_visibility="collapsed",
                key="risk_map_page_input",
            )
            if jump_to != page + 1:
                st.session_state.risk_map_page = jump_to - 1
                st.rerun()
        with cols[3]:
            if st.button("Next →", disabled=(page >= total_pages - 1), use_container_width=True):
                st.session_state.risk_map_page = min(total_pages - 1, page + 1)
                st.rerun()
        with cols[4]:
            if st.button("⏭ Last", disabled=(page >= total_pages - 1), use_container_width=True):
                st.session_state.risk_map_page = total_pages - 1
                st.rerun()

    # ── Legend ──
    st.markdown("<hr style='border-color:rgba(255,255,255,0.07);margin:1.5rem 0;'>", unsafe_allow_html=True)
    st.markdown(f"""
    <div style="display:flex;gap:1.5rem;color:{MUTED};font-size:0.8rem;">
        <div><span style="display:inline-block;width:10px;height:10px;background:{RUST};
                        border-radius:2px;margin-right:4px;"></span> High Risk (≥19% deficit)</div>
        <div><span style="display:inline-block;width:10px;height:10px;background:{TURMERIC};
                        border-radius:2px;margin-right:4px;"></span> Medium Risk (10–19% deficit)</div>
        <div><span style="display:inline-block;width:10px;height:10px;background:{SAGE};
                        border-radius:2px;margin-right:4px;"></span> Low Risk (&lt;10% deficit)</div>
        <div><span style="display:inline-block;width:10px;height:10px;background:{MUTED};
                        border-radius:2px;margin-right:4px;"></span> No Data (unmapped district)</div>
    </div>
    """, unsafe_allow_html=True)
