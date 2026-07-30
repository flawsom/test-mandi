"""
MandiIQ — Executive Overview page.

Headline finding, KPI panel, price trend by district/commodity.
Includes "Ask MandiIQ" AI chat panel (Phase 11 — OpenRouter multi-model routing).

Alche Studio Design: glass cards, interpretation boxes, crosshair panels,
section labels, and consistent monochrome-lime palette.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

import datetime as _dt
import json
import math
import os
import threading
import time as _time
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from mandi_rdd.dashboard.theme import inject_theme, inject_countup_js, commodity_color, get_api_base, INK, SLATE, PAPER, MUTED, FAINT, TURMERIC, RUST, SAGE
from mandi_rdd.dashboard.flip_board import flip_board
from mandi_rdd.dashboard.plotly_theme import make_themed_figure
from mandi_rdd.storage.duckdb_store import (
    get_connection, get_latest_rdd, get_prices, get_distinct_commodities,
    get_avg_price_and_districts, get_latest_forecast_metrics,
)
from mandi_rdd.analysis.forecast import train_forecast


# ── AI Chat API destination ──
API_BASE = get_api_base()

# ── Paths for ingestion progress tracking ──
_INGEST_PROGRESS_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "_ingestion_progress.json"
_INGEST_LOCK = threading.Lock()


def _run_ingestion_async(max_retries: int = 3):
    """Run run_ingestion() in a background thread, writing progress to a JSON file.

    Auto-retries up to `max_retries` times with exponential backoff (2s, 4s, 8s)
    on transient failures like DuckDB lock contention. The dashboard polls this
    file to show live step-by-step status.
    """
    _BACKOFF = [2, 4, 8]  # seconds between retries

    def _write_progress(
        step: str, status: str, detail: str = "",
        _start_ts: float | None = None,
        _retry_attempt: int | None = None,
        _retry_max: int | None = None,
        _retry_delay: float | None = None,
    ):
        try:
            _INGEST_PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
            obj: dict = {
                "step": step,
                "status": status,
                "detail": detail,
                "ts": _time.time(),
            }
            if _start_ts is not None:
                obj["start_ts"] = _start_ts
            if _retry_attempt is not None:
                obj["retry_attempt"] = _retry_attempt
            if _retry_max is not None:
                obj["retry_max"] = _retry_max
            if _retry_delay is not None:
                obj["retry_delay"] = _retry_delay
            with _INGEST_LOCK:
                with open(_INGEST_PROGRESS_PATH, "w") as f:
                    json.dump(obj, f)
        except Exception:
            pass

    def _run():
        _ingestion_start_ts = _time.time()
        _write_progress("initializing", "running", "Starting pipeline...",
                        _start_ts=_ingestion_start_ts)

        for attempt in range(1, max_retries + 1):
            try:
                from mandi_rdd.ingestion.scheduler import run_ingestion
                summary = run_ingestion(max_records=10000)

                steps = summary.get("steps", {})
                prices_step = steps.get("prices", {})
                n_new = prices_step.get("new", 0) if isinstance(prices_step, dict) else 0
                n_fetched = prices_step.get("fetched", 0) if isinstance(prices_step, dict) else 0

                # Also update the hourly status file so the auto-update strip picks it up
                status_out = Path(__file__).resolve().parent.parent.parent / "data" / "last_hourly_run.json"
                try:
                    with open(status_out, "w") as f:
                        json.dump({
                            "last_run_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(),
                            "outcome": "success" if summary.get("status") == "ok" else "failure",
                            "new_price_rows": n_new,
                            "duration_s": summary.get("duration_seconds", 0),
                            "error": None if summary.get("status") == "ok" else summary.get("error"),
                        }, f)
                except Exception:
                    pass

                _write_progress("complete", "success",
                    f"Fetched {n_fetched} records ({n_new} new) in {summary.get('duration_seconds', 0):.1f}s",
                    _start_ts=_ingestion_start_ts)
                return  # success — exit early

            except Exception as e:
                if attempt < max_retries:
                    delay = _BACKOFF[min(attempt - 1, len(_BACKOFF) - 1)]
                    _TICK = 0.25
                    remaining = float(delay)
                    while remaining > 0:
                        display_secs = math.ceil(remaining)
                        _write_progress(
                            "retrying",
                            "running",
                            f"Retry {attempt}/{max_retries} in {display_secs}s ({e!s:.80})",
                            _start_ts=_ingestion_start_ts,
                            _retry_attempt=attempt,
                            _retry_max=max_retries,
                            _retry_delay=delay,
                        )
                        _time.sleep(_TICK)
                        remaining -= _TICK
                    _write_progress(
                        "retrying",
                        "running",
                        f"Retry {attempt}/{max_retries} — retrying now ({e!s:.80})",
                        _start_ts=_ingestion_start_ts,
                        _retry_attempt=attempt,
                        _retry_max=max_retries,
                        _retry_delay=0,
                    )
                else:
                    _write_progress("error", "error",
                        f"Failed after {max_retries} attempts. Last error: {e!s}",
                        _start_ts=_ingestion_start_ts)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return t


def _read_ingestion_progress() -> dict | None:
    """Read the current ingestion progress from the JSON file."""
    try:
        if _INGEST_PROGRESS_PATH.exists():
            with _INGEST_LOCK:
                with open(_INGEST_PROGRESS_PATH) as f:
                    return json.load(f)
    except Exception:
        return None
    return None


def _pre_request_notification_permission() -> None:
    """Pre-request browser Notification permission on page load.

    Fires an inline <script> that requests permission if not already
    granted or denied. This way the browser's permission prompt appears
    at a natural moment (page load) rather than surprising the user when
    an ingestion completes.
    """
    st.markdown(
        "<script>"
        "(function(){try{"
        'if("Notification"in window&&Notification.permission==="default"){'
        "Notification.requestPermission();"
        "}"
        "}catch(e){}"
        "})();"
        "</script>",
        unsafe_allow_html=True,
    )


def _fire_completion_notification(outcome: str, detail: str) -> None:
    """Inject a browser Notification API popup when ingestion completes.

    Streamlit renders this as inline JS so it survives reruns without
    requiring a custom component. Respects the user's Notification
    permission choice per the Web API spec.
    Uses a data-uri icon (wheat emoji SVG) for the notification badge.
    """
    # Escape backslash, double-quote, and single-quote for JS string safety
    safe_detail = detail[:80].replace("\\", "\\\\").replace(chr(34), "\\" + chr(34)).replace(chr(39), "\\" + chr(39))
    safe_title = "MandiIQ \u2014 Ingestion " + outcome.title()
    icon_svg = (
        "data:image/svg+xml,%3Csvg xmlns=%27http://www.w3.org/2000/svg%27"
        " viewBox=%270 0 100 100%27%3E%3Ctext y=%27.9em%27 font-size=%2790%27%3E%F0%9F%8C%BE%3C/text%3E%3C/svg%3E"
    )
    js = (
        "<script>"
        "(function(){try{"
        'if(!("Notification"in window))return;'
        'if(Notification.permission==="granted"){'
        "new Notification("
        + "\"" + safe_title.replace("\"", "\\\"") + "\""
        + ',{body:"'
        + safe_detail.replace("'", "\\'")
        + '",icon:"'
        + icon_svg
        + '"});'
        '}else if(Notification.permission!=="denied"){'
        "Notification.requestPermission();"
        "}"
        "}catch(e){}"
        "})();"
        "</script>"
    )
    st.markdown(js, unsafe_allow_html=True)


def _play_completion_chime(success: bool = True) -> None:
    """Play a short two-tone chime via Web Audio API on ingestion completion.

    On success: ascending C5->E5 (bright, satisfying).
    On failure: descending E5->C5 (softer, lower urgency).
    Both at low volume with short decay. Gracefully silent if AudioContext
    is unavailable or blocked.
    """
    if success:
        t1, t2 = 523, 659  # C5 -> E5 (ascending)
    else:
        t1, t2 = 659, 523  # E5 -> C5 (descending)
    chime_js = (
        '<script>'
        '(function(){try{'
        'var a=new(window.AudioContext||window.webkitAudioContext)();'
        'var g=a.createGain();g.connect(a.destination);g.gain.value=0.1;'
        f'var o=a.createOscillator();o.connect(g);o.frequency.value={t1};'
        'o.start(0);g.gain.exponentialRampToValueAtTime(.001,a.currentTime+.15);'
        'o.stop(a.currentTime+.15);'
        'setTimeout(function(){'
        f'var g2=a.createGain();g2.connect(a.destination);g2.gain.value=0.08;'
        f'var o2=a.createOscillator();o2.connect(g2);o2.frequency.value={t2};'
        'o2.start(0);g2.gain.exponentialRampToValueAtTime(.001,a.currentTime+.3);'
        'o2.stop(a.currentTime+.3);'
        '},120);'
        '}catch(e){}'
        '})();'
        '</script>'
    )
    st.markdown(chime_js, unsafe_allow_html=True)


def _render_ingestion_trigger():
    """Render the 'Run Ingestion Now' button with live progress and
    completion notifications (toast + browser popup + chime + balloons)."""
    progress = _read_ingestion_progress()
    is_running = progress and progress.get("status") == "running"

    # ── Session state for ingestion lifecycle ──
    if "ingestion_triggered" not in st.session_state:
        st.session_state.ingestion_triggered = False
    if "_prev_ingest_status" not in st.session_state:
        st.session_state._prev_ingest_status = None
    if "_ingest_notified" not in st.session_state:
        st.session_state._ingest_notified = False

    # ── Completion transition detection ──
    # When we transition from "running" → "success" / "error", fire notifications
    if is_running:
        st.session_state._prev_ingest_status = "running"
        st.session_state._ingest_notified = False  # reset for next completion
    elif st.session_state.ingestion_triggered and progress:
        new_status = progress.get("status")
        if (st.session_state._prev_ingest_status == "running"
                and new_status in ("success", "error")
                and not st.session_state._ingest_notified):
            st.session_state._ingest_notified = True
            st.session_state._prev_ingest_status = None

            if new_status == "success":
                detail = progress.get("detail", "Ingestion complete")
                st.toast(f"✅ Ingestion complete — {detail}", icon="🎉")
                st.balloons()
                _play_completion_chime(success=True)
                _fire_completion_notification("success", detail)
            else:
                detail = progress.get("detail", "Ingestion failed")
                st.toast(f"❌ Ingestion failed — {detail[:60]}", icon="⚠️")
                _play_completion_chime(success=False)
                _fire_completion_notification("error", detail)

    col_b, col_s = st.columns([1, 5])

    with col_b:
        button_disabled = is_running or st.session_state.ingestion_triggered
        clicked = st.button(
            "\u25b6 Run Ingestion Now",
            type="primary",
            disabled=button_disabled,
            use_container_width=True,
        )

    with col_s:
        if clicked and not button_disabled:
            # Clear old progress and start a new run
            st.session_state.ingestion_triggered = True
            st.session_state._ingest_notified = False
            _run_ingestion_async()
            st.rerun()

        elif is_running:
            progress_ts = progress.get("ts", _time.time())
            start_ts = progress.get("start_ts", progress_ts)
            elapsed = _time.time() - start_ts
            step = progress.get("step", "working")
            detail = progress.get("detail", "")

            # Embed structured timing data for the client-side countdown JS
            ra_attrs = progress.get("retry_attempt")
            rm_attrs = progress.get("retry_max")
            rd_attrs = progress.get("retry_delay")
            retry_json = (
                f'data-ra="{ra_attrs}" data-rm="{rm_attrs}" data-rd="{rd_attrs}"'
                if ra_attrs is not None else ""
            )
            st.markdown(
                f'<div id="mandiiq-ib"'
                f' data-ts="{start_ts}" data-step="{step}" {retry_json}'
                f' style="display:flex;align-items:center;gap:8px;padding:0.4rem 0.8rem;'
                f'border-radius:6px;background:rgba(107,191,138,0.06);'
                f'border:1px solid rgba(107,191,138,0.25);font-family:IBM Plex Mono,monospace;font-size:0.75rem;">'
                f'<span style="color:#6BBF8A;">\u25cf Running</span>'
                f'<span id="mandiiq-ib-step" style="color:#7e7e7e;">{step}</span>'
                f'<span id="mandiiq-ib-elapsed" style="color:#7e7e7e;">\u00b7 {elapsed:.0f}s</span>'
                f'<span id="mandiiq-ib-detail" style="color:#bababa;font-size:0.7rem;">{detail[:60]}</span>'
                f'</div>'
                + '</div><script>(function(){try{'
                + 'var el=document.getElementById("mandiiq-ib");'
                + 'if(!el)return;'
                + 'var thisRa=el.getAttribute("data-ra");'
                + 'if(thisRa===window.__mandiiq_ib_ra&&window.__mandiiq_ib)return;'
                + 'window.__mandiiq_ib_ra=thisRa;'
                + 'window.__mandiiq_ib=true;'
                + 'function tick(){'
                + 'var el2=document.getElementById("mandiiq-ib");'
                + 'if(!el2){window.__mandiiq_ib=false;return;}'
                + 'var now=Date.now()/1000;'
                + 'var secs=Math.max(0,Math.floor(now-parseFloat(el2.getAttribute("data-ts"))));'
                + 'var es=document.getElementById("mandiiq-ib-elapsed");'
                + 'if(es)es.textContent="\u00b7 "+secs+"s";'
                + 'var ra=el2.getAttribute("data-ra"),rm=el2.getAttribute("data-rm"),rd=parseFloat(el2.getAttribute("data-rd"))||0;'
                + 'var ed=document.getElementById("mandiiq-ib-detail");'
                + 'if(ra!==null&&rm!==null&&ed){'
                + 'var rs=window.__mandiiq_ib_rs||0;'
                + 'if(!rs){rs=now;window.__mandiiq_ib_rs=rs;}'
                + 'var left=Math.max(0,Math.ceil(rd-(now-rs)));'
                + 'ed.textContent="Retry "+ra+"/"+rm+" in "+left+"s";'
                + '}'
                + 'requestAnimationFrame(tick);'
                + '}'
                + 'requestAnimationFrame(tick);'
                + '}catch(e){}'
                + '})();'
                + '</script>',
                unsafe_allow_html=True,
            )
            # Auto-refresh every cycle while running
            _time.sleep(0.05)
            st.rerun()

        elif st.session_state.ingestion_triggered:
            if not progress:
                # Progress file was cleaned up or thread failed before writing
                st.session_state.ingestion_triggered = False
                st.rerun()
                return
            # Run completed — show result
            if progress:
                status = progress.get("status")
                detail = progress.get("detail", "")
                if status == "success":
                    st.markdown(
                        f'<div style="display:flex;align-items:center;gap:8px;padding:0.4rem 0.8rem;'
                        f'border-radius:6px;background:rgba(107,191,138,0.06);'
                        f'border:1px solid rgba(107,191,138,0.25);font-family:IBM Plex Mono,monospace;font-size:0.75rem;">'
                        f'<span style="color:#6BBF8A;font-weight:500;">\u2713 Complete</span>'
                        f'<span style="color:#7e7e7e;">{detail}</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                elif status == "error":
                    st.markdown(
                        f'<div style="display:flex;align-items:center;gap:8px;padding:0.4rem 0.8rem;'
                        f'border-radius:6px;background:rgba(217,102,59,0.06);'
                        f'border:1px solid rgba(217,102,59,0.25);font-family:IBM Plex Mono,monospace;font-size:0.75rem;">'
                        f'<span style="color:#D9663B;font-weight:500;">\u2717 Failed</span>'
                        f'<span style="color:#7e7e7e;">{detail[:80]}</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                # Reset after showing result
                if st.button("Clear", key="clear_ingest_status"):
                    st.session_state.ingestion_triggered = False
                    try:
                        _INGEST_PROGRESS_PATH.unlink(missing_ok=True)
                    except Exception:
                        pass
                    st.rerun()


# ── Cached data loaders ──
@st.cache_data(ttl=300, show_spinner=False)
def _cached_prices(limit: int = 5):
    try:
        conn = get_connection(read_only=True)
        try:
            return get_prices(conn, limit=limit)
        finally:
            conn.close()
    except Exception:
        return None


@st.cache_data(ttl=300, show_spinner=False)
def _cached_rdd(commodity: str):
    # Try local DuckDB first
    try:
        conn = get_connection(read_only=True)
        try:
            result = get_latest_rdd(conn, commodity)
            if result and result.get("effect") is not None:
                return result
        finally:
            conn.close()
    except Exception:
        pass
    # Fallback to API if local data is empty/missing
    try:
        import requests
        api_base = get_api_base()
        resp = requests.get(f"{api_base}/rdd-result/{commodity}", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("effect") is not None:
                return {
                    "commodity": commodity,
                    "effect": data["effect"],
                    "p_value": data.get("p_value"),
                    "std_error": data.get("std_error"),
                    "n_left": data.get("n_left"),
                    "n_right": data.get("n_right"),
                    "bandwidth": 20,
                    "cutoff": -19,
                    "interpretation": data.get("interpretation", ""),
                    "fe_effect": "N/A",
                }
    except Exception:
        pass
    return None


@st.cache_data(ttl=300, show_spinner=False)
def _cached_avg_price(commodity: str):
    try:
        conn = get_connection(read_only=True)
        try:
            avg, ndist = get_avg_price_and_districts(conn, commodity)
        finally:
            conn.close()
        return avg, ndist
    except Exception:
        return None, None


@st.cache_data(ttl=600, show_spinner=False)
def _cached_forecast_mape(commodity: str, h: int = 12):
    try:
        conn = get_connection(read_only=True)
        try:
            stored = get_latest_forecast_metrics(conn, commodity)
            if stored and stored.get("test_mape") is not None:
                return float(stored["test_mape"])
            fc = train_forecast(conn, commodity=commodity, periods=h)
            if fc and fc.get("metrics") and fc["metrics"].get("mape") is not None:
                return float(fc["metrics"]["mape"])
        finally:
            conn.close()
    except Exception:
        return None
    return None


@st.cache_data(ttl=60, show_spinner=False)
def _read_auto_update_status():
    """Read the last_hourly_run.json status file.

    Cached with 60s TTL to avoid filesystem I/O on every Streamlit rerun
    while staying fresh enough for the auto-update status display.
    """
    import json
    from pathlib import Path
    try:
        status_path = Path(__file__).resolve().parent.parent.parent / "data" / "last_hourly_run.json"
        if not status_path.exists():
            return None
        with open(status_path) as f:
            return json.load(f)
    except Exception:
        return None


@st.cache_data(ttl=3600, show_spinner=False)
def _cached_all_india_monsoon():
    try:
        from mandi_rdd.ingestion.fetch_rainfall import fetch_all_india_monsoon
        rid = ""
        api_key = ""
        try:
            rid = st.secrets.get("ALL_INDIA_RAINFALL_RESOURCE_ID", "")
        except Exception:
            pass
        if not rid:
            rid = os.environ.get("ALL_INDIA_RAINFALL_RESOURCE_ID", "")
        try:
            api_key = st.secrets.get("ALL_INDIA_RAINFALL_API_KEY", "")
        except Exception:
            pass
        if not api_key:
            api_key = os.environ.get("ALL_INDIA_RAINFALL_API_KEY", "")
        if rid and api_key:
            return fetch_all_india_monsoon(rid, api_key)
    except Exception:
        pass
    return []


def _read_integrity_status():
    """Read the last_integrity_check.json status file."""
    try:
        path = Path(__file__).resolve().parent.parent.parent / "data" / "last_integrity_check.json"
        if not path.exists():
            return None
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None


def _render_auto_update_strip():
    """Render a subtle auto-update status strip below the hero,
    including data integrity warnings if any checks failed."""
    status = _read_auto_update_status()
    if not status:
        # No status file yet - show a suggestion
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:1.5rem;padding:0.5rem 0.8rem;border-radius:6px;background:rgba(217,102,59,0.08);border:1px solid rgba(217,102,59,0.2);font-size:0.8rem;">'
            f'<span style="color:#D9663B;font-weight:500;">\u26a0\ufe0f Auto-update not configured</span>'
            f'<span style="color:#7e7e7e;">-- run <code style="font-family:IBM Plex Mono,monospace;font-size:0.75rem;">python setup_scheduled_task.py</code> to enable hourly ingestion</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
        return

    import datetime as _dt

    run_ts = status.get("last_run_utc", "")
    outcome = status.get("outcome", "unknown")
    new_rows = status.get("new_price_rows", 0)
    duration = status.get("duration_s", 0)
    err = status.get("error")

    # Compute how long ago
    try:
        run_dt = _dt.datetime.fromisoformat(run_ts.replace("Z", "+00:00"))
        now = _dt.datetime.now(_dt.timezone.utc)
        delta = now - run_dt
        mins_ago = int(delta.total_seconds() // 60)
        if mins_ago < 1:
            ago_str = "just now"
        elif mins_ago < 60:
            ago_str = f"{mins_ago}m ago"
        else:
            hrs = mins_ago // 60
            ago_str = f"{hrs}h {mins_ago % 60}m ago"
    except Exception:
        ago_str = run_ts[:19] if run_ts else "unknown"

    if outcome == "success":
        dot_color = "#6BBF8A"
        dot_label = "Auto-updated"
        border_color = "rgba(107,191,138,0.25)"
        bg = "rgba(107,191,138,0.06)"
        extra = f"{new_rows} new rows . {duration:.1f}s" if new_rows > 0 else f"{duration:.1f}s"
        msg = f"<span style='color:#6BBF8A;font-weight:500;'>.</span> <span style='color:#7e7e7e;'><span id='mandiiq-auto-ago'>{ago_str}</span> . {extra}</span>"
    elif outcome == "failure":
        dot_color = "#D9663B"
        dot_label = "Last update failed"
        border_color = "rgba(217,102,59,0.25)"
        bg = "rgba(217,102,59,0.06)"
        err_msg = f" . <span style='color:#D9663B;'>{err[:80]}</span>" if err else ""
        msg = f"<span style='color:#D9663B;font-weight:500;'>!</span> <span style='color:#7e7e7e;'><span id='mandiiq-auto-ago'>{ago_str}</span>{err_msg}</span>"
    else:
        dot_color = "#7e7e7e"
        dot_label = "Status unknown"
        border_color = "rgba(255,255,255,0.1)"
        bg = "rgba(255,255,255,0.02)"
        msg = f"<span style='color:#7e7e7e;'>{dot_label}</span>"

    # Check integrity status and append a warning banner if checks failed
    integrity = _read_integrity_status()
    integrity_html = ""
    if integrity and integrity.get("overall") in ("fail", "warn"):
        integ_summary = integrity.get("summary", "Integrity alerts")
        n_alerts = len(integrity.get("alerts", []))
        is_fail = integrity["overall"] == "fail"
        integ_color = "#D9663B" if is_fail else "#E8B14D"
        integ_bg = "rgba(217,102,59,0.06)" if is_fail else "rgba(232,177,77,0.06)"
        integ_border = "rgba(217,102,59,0.25)" if is_fail else "rgba(232,177,77,0.25)"
        icon = "!!" if is_fail else "!"
        integrity_html = (
            f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:0.5rem;margin-top:0.5rem;'
            f'padding:0.4rem 0.8rem;border-radius:6px;background:{integ_bg};border:1px solid {integ_border};'
            f'font-family:IBM Plex Mono,monospace;font-size:0.75rem;">'
            f'<span style="color:{integ_color};font-weight:500;">{icon} Data Integrity</span>'
            f'<span style="color:#7e7e7e;">{integ_summary} ({n_alerts} alerts)</span>'
            f'</div>'
        )

    # Serialize run_ts for JS: store in data attribute for rAF animation
    _auto_ts = run_ts
    st.markdown(
        f'<div id="mandiiq-auto-status" style="display:flex;flex-direction:column;margin-bottom:1.5rem;">'
        f'<div style="display:flex;align-items:center;gap:8px;'
        f'padding:0.4rem 0.8rem;border-radius:6px;background:{bg};border:1px solid {border_color};'
        f'font-family:IBM Plex Mono,monospace;font-size:0.75rem;" data-last-run-ts="{_auto_ts}">{msg}</div>'
        f'{integrity_html}'
        + '</div><script>(function(){try{'
        + 'if(window.__mandiiq_auto)return;window.__mandiiq_auto=true;'
        + 'var el=document.getElementById("mandiiq-auto-ago");'
        + 'if(!el)return;'
        + 'var parent=el.closest("[data-last-run-ts]");'
        + 'if(!parent)return;'
        + 'var runTs=parent.getAttribute("data-last-run-ts");'
        + 'function fmt(m){if(m<1)return"just now";if(m<60)return m+"m ago";var h=Math.floor(m/60);return h+"h "+(m%60)+"m ago";}'
        + 'function tick(){var p=document.getElementById("mandiiq-auto-status");'
        + 'if(!p){window.__mandiiq_auto=false;return;}'
        + 'var e=document.getElementById("mandiiq-auto-ago");if(!e){window.__mandiiq_auto=false;return;}'
        + 'var r=e.closest("[data-last-run-ts]");var t=r?r.getAttribute("data-last-run-ts"):runTs;'
        + 'var now=new Date();var run=new Date(t);'
        + 'if(isNaN(run.getTime())){requestAnimationFrame(tick);return;}'
        + 'var ms=now-run;var mins=Math.max(0,Math.floor(ms/60000));e.textContent=fmt(mins);'
        + 'requestAnimationFrame(tick);'
        + '}'
        + 'requestAnimationFrame(tick);'
        + '}catch(e){}'
        + '})();'
        + '</script>',
        unsafe_allow_html=True,
    )


def render(**kwargs):
    # Streamlit 1.59 calls render() with no args; compute data internally.
    selected_commodity = "Onion"

    # Pre-request browser Notification permission on page load so the
    # permission prompt comes at a natural time, not mid-workflow.
    _pre_request_notification_permission()

    try:
        _rows = _cached_prices(limit=5)
        data_summary = {"rows": _rows, "count": len(_rows)} if _rows is not None else {"rows": [], "count": 0}
    except Exception:
        data_summary = {"rows": [], "count": 0}
    try:
        rdd_result = _cached_rdd(selected_commodity) or {}
    except Exception:
        rdd_result = {}
    inject_theme()

    # ── Hero Header ──
    st.markdown(
        """
        <div class="page-hero" style="position: relative; overflow: hidden; margin-bottom: 2rem; min-height: 280px;">
          <div style="position: relative; z-index: 1;">
            <div style="font-family:'IBM Plex Mono',monospace;font-size:0.75rem;color:#d7ff00;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:0.5rem;">
              Operational Dashboard
            </div>
            <h1 class="hero-title" style="font-family:'Space Grotesk',system-ui,sans-serif;font-weight:300;font-size:clamp(1.8rem,3.5vw,2.8rem);color:#ffffff;letter-spacing:0.03em;text-transform:uppercase;margin-bottom:0.5rem;">
              Executive Overview
            </h1>
            <p style="color:#7e7e7e;max-width:680px;line-height:1.7;font-size:0.95rem;">
              Real-time RDD causal estimate, live market KPIs, and the AI procurement chat.
            </p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Auto-update status strip ──
    _render_auto_update_strip()

    # ── Manual ingestion trigger ──
    _render_ingestion_trigger()

    # ── Phase 11: Ask MandiIQ AI Chat Panel ──
    _render_ask_panel(selected_commodity)

    # ── Headline finding (interpretation box) ──
    effect = rdd_result.get("effect")
    p_val = rdd_result.get("p_value")
    fe_val = rdd_result.get("fe_effect")
    try:
        fe_display = f"₹{fe_val:.2f}" if __import__('math').isfinite(float(fe_val)) else "N/A"
    except (TypeError, ValueError):
        fe_display = "N/A"
    if effect is not None:
        sig = "ROBUST" if (p_val is not None and p_val < 0.05) else "exploratory"
        st.markdown(
            f"""
            <div class="interpretation-box">
                <strong style="color:#d7ff00;">⬡ {sig}:</strong> Crossing the −19% rainfall deficiency threshold is associated
                with a <strong>₹{effect:.2f}</strong> change in {selected_commodity} modal prices
                (p={'{:.4f}'.format(p_val) if p_val else 'N/A'}).
                Fixed-effects cross-check: <span style="font-family:'IBM Plex Mono',monospace;">{fe_display}</span>.
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="interpretation-box insig-box">Run the pipeline to see RDD results for Onion.</div>',
            unsafe_allow_html=True,
        )

    # ── KPI row — flip-board hero ──
    try:
        import math

        avg_price, n_districts = _cached_avg_price(selected_commodity)
        spike_n = int(n_districts) if n_districts else None
        _mape = _cached_forecast_mape(selected_commodity)

        def is_valid_num(x):
            if x is None:
                return False
            try:
                return math.isfinite(float(x))
            except (TypeError, ValueError):
                return False

        # Show "Insufficient data" when MAPE is missing or exceeds 100%
        # (Prophet routinely produced 5000%+ MAPEs on noisy agri data;
        #  the new seasonal naive model produces realistic 15-40% MAPEs)
        def mape_display(x):
            if not is_valid_num(x):
                return "Insufficient data"
            val = float(x)
            if val > 100:
                return "Insufficient data"
            return f"{val:.1f}"

        flip_board(
            effect=(f"{effect:,.0f}" if is_valid_num(effect) else "—"),
            effect_raw=(float(effect) if is_valid_num(effect) else None),
            avg_price=(f"{avg_price:,.0f}" if is_valid_num(avg_price) else "—"),
            avg_price_raw=(float(avg_price) if is_valid_num(avg_price) else None),
            districts=(f"{spike_n:,}" if is_valid_num(spike_n) else "—"),
            districts_raw=(float(spike_n) if is_valid_num(spike_n) else None),
            mape=mape_display(_mape),
            mape_raw=(float(_mape) if is_valid_num(_mape) else None),
        )
    except Exception:
        # Fallback: flat metrics (graceful degradation)
        _mape_display = f"{_mape:.1f}%" if (isinstance(_mape, (int, float)) and _mape <= 100) else "Insufficient data"
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Price Effect (₹)", f"₹{effect:,.0f}" if effect is not None else "—")
        with col2:
            st.metric("Avg Modal Price", f"₹{avg_price:,.0f}" if avg_price else "—")
        with col3:
            st.metric("Districts Flagged", f"{spike_n:,}" if spike_n else "—")
        with col4:
            st.metric("Forecast MAPE", _mape_display)

    # ── Data Freshness Widget ──
    _render_freshness_widget()

    # ── National Monsoon Context strip ──
    _render_national_monsoon_strip()

    # ── Price trend chart in glass card ──
    st.markdown(
        """
        <div style="margin-top:2rem;">
          <div style="font-family:'IBM Plex Mono',monospace;font-size:0.75rem;color:#d7ff00;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:0.5rem;">
            02 / Price Trend
          </div>
          <h2 style="font-family:'Space Grotesk',system-ui,sans-serif;font-weight:400;font-size:1.4rem;color:#ffffff;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:1rem;">
            Daily Price Trend
          </h2>
        </div>
        """,
        unsafe_allow_html=True,
    )
    try:
        from mandi_rdd.storage.duckdb_store import get_connection
        conn = get_connection(read_only=True)

        # Find the commodity variant with the best date coverage
        # (exact match first, then LIKE variants, then fallback to exact)
        best_comm = selected_commodity
        try:
            # Check if exact match has enough dates
            has_enough = conn.execute(
                "SELECT COUNT(DISTINCT arrival_date) > 5 FROM prices WHERE commodity = ?",
                [selected_commodity],
            ).fetchone()[0]
            if not has_enough:
                # Try exact match first, then LIKE prefix (e.g. Onion→Onions)
                row = conn.execute("""
                    SELECT commodity, COUNT(DISTINCT arrival_date) AS n_dates
                    FROM prices
                    WHERE LOWER(commodity) LIKE LOWER(?) || '%'
                    GROUP BY commodity
                    ORDER BY n_dates DESC
                    LIMIT 1
                """, [selected_commodity]).fetchone()
                if row and row[0] and row[1] > 5:
                    best_comm = row[0]
        except Exception:
            best_comm = selected_commodity

        df = conn.execute(
            "SELECT arrival_date, AVG(modal_price) as avg_price, MIN(modal_price) as min_price, MAX(modal_price) as max_price FROM prices WHERE commodity = ? GROUP BY arrival_date ORDER BY arrival_date",
            [best_comm],
        ).fetchdf()
        conn.close()
        if len(df) > 5:
            color = commodity_color(best_comm)
            fig = make_themed_figure()
            fig.add_trace(go.Scatter(x=df["arrival_date"], y=df["avg_price"], mode="lines", name="Avg", line=dict(color=color, width=2)))
            fig.add_trace(go.Scatter(x=df["arrival_date"], y=df["max_price"], mode="lines", name="Max", line=dict(color=color, width=1, dash="dash", opacity=0.6)))
            fig.add_trace(go.Scatter(x=df["arrival_date"], y=df["min_price"], mode="lines", name="Min", line=dict(color="#7e7e7e", width=1, dash="dash", opacity=0.5)))
            fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=350)
            st.markdown('<div class="glass" style="padding:1.2rem;">', unsafe_allow_html=True)
            st.plotly_chart(fig, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.markdown(
                '<div class="interpretation-box insig-box">Insufficient price data to plot a trend. '
                'Run the ingestion pipeline first.</div>',
                unsafe_allow_html=True,
            )
    except Exception:
        st.markdown(
            '<div class="interpretation-box insig-box">Price trend unavailable — run ingestion first.</div>',
            unsafe_allow_html=True,
        )


def _render_freshness_widget():
    """Render a Data Freshness widget using GET /freshness API data.

    Shows per-commodity last-updated dates, row counts, district/state coverage,
    and data source (api/csv/ashoka/rainfall). Falls back gracefully if the API
    is unreachable.
    """
    st.markdown(
        """
        <div style="margin-top:2.5rem;">
          <div style="font-family:'IBM Plex Mono',monospace;font-size:0.75rem;color:#d7ff00;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:0.5rem;">
            01 / Data Freshness
          </div>
          <h2 style="font-family:'Space Grotesk',system-ui,sans-serif;font-weight:400;font-size:1.4rem;color:#ffffff;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:1rem;">
            Commodity Freshness <span style="font-size:1.2rem;">\u23f3</span>
          </h2>
          <p style="color:#7e7e7e;font-size:0.85rem;margin-bottom:1rem;">
            Per-commodity data freshness: latest record date, row count, district coverage,
            and ingestion source. Data flows from data.gov.in API, CSV backfill, Ashoka CEDA
            archive, and rainfall feeds. Rows tagged with missing commodities are grouped under
            "Other / Uncategorized".
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Fetch freshness data
    freshness_data = _cached_freshness()

    # ── Pagination for freshness table ──
    # ── Rows per page (persisted in session state) ──
    if "freshness_page_size" not in st.session_state:
        st.session_state.freshness_page_size = 20
    _FRESH_PAGE_SIZE = st.session_state.freshness_page_size
    _TOTAL_FRESH_PAGES = max(1, (len(freshness_data) + _FRESH_PAGE_SIZE - 1) // _FRESH_PAGE_SIZE)

    if "freshness_page" not in st.session_state:
        st.session_state.freshness_page = 0
    if st.session_state.freshness_page >= _TOTAL_FRESH_PAGES:
        st.session_state.freshness_page = max(0, _TOTAL_FRESH_PAGES - 1)

    _fresh_page = st.session_state.freshness_page
    _fresh_start = _fresh_page * _FRESH_PAGE_SIZE
    _fresh_end = _fresh_start + _FRESH_PAGE_SIZE
    _page_freshness_data = freshness_data[_fresh_start:_fresh_end]

    if not freshness_data or (isinstance(freshness_data, dict) and "error" in freshness_data):
        st.markdown(
            f'<div class="interpretation-box insig-box">\u26a0\ufe0f Freshness data unavailable. '
            f'Run the ingestion pipeline to populate commodity freshness.</div>',
            unsafe_allow_html=True,
        )
        return

    if isinstance(freshness_data, list) and len(freshness_data) == 0:
        st.markdown(
            '<div class="interpretation-box insig-box">No freshness data yet. '
            'The first ingestion run will populate these metrics.</div>',
            unsafe_allow_html=True,
        )
        return

    # Build a summary row at the top
    total_rows = sum(r.get("row_count", 0) for r in freshness_data if isinstance(r, dict))
    total_commodities = len([r for r in freshness_data if isinstance(r, dict) and r.get("commodity")])
    # Count how many commodities have data in the last 7 days
    import datetime
    _seven_days_ago = datetime.datetime.utcnow() - datetime.timedelta(days=7)
    recent_count = 0
    for r in freshness_data:
        if not isinstance(r, dict):
            continue
        latest = r.get("latest_date")
        if latest is None:
            continue
        if isinstance(latest, str):
            try:
                latest = datetime.datetime.strptime(latest[:10], "%Y-%m-%d")
            except (ValueError, IndexError):
                continue
        if isinstance(latest, (datetime.datetime, datetime.date)) and latest >= _seven_days_ago:
            recent_count += 1

    # ── Inject shared count-up JS before KPI cards ──
    inject_countup_js()

    # ── KPI micro-row with rAF count-up + pulse dots ──
    c1, c2, c3, c4 = st.columns(4)
    # ── Staggered entry delays (sync with flip-board: 80ms each) ──
    _CARD_STAGGER_MS = 80

    with c1:
        st.markdown(
            f'<div class="fresh-card" data-fkey="c1" data-ftarget="{total_commodities}" style="animation:freshEntry 400ms cubic-bezier(0.16,1,0.3,1) {0*_CARD_STAGGER_MS}ms both">'
            f'<div class="fresh-label"><span class="fresh-dot"></span>Commodities tracked</div>'
            f'<div class="fresh-val">0</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f'<div class="fresh-card" data-fkey="c2" data-ftarget="{total_rows}" data-ffmt="us" style="animation:freshEntry 400ms cubic-bezier(0.16,1,0.3,1) {1*_CARD_STAGGER_MS}ms both">'
            f'<div class="fresh-label"><span class="fresh-dot"></span>Total price rows</div>'
            f'<div class="fresh-val">0</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            f'<div class="fresh-card" data-fkey="c3" data-ftarget="{recent_count}" style="animation:freshEntry 400ms cubic-bezier(0.16,1,0.3,1) {2*_CARD_STAGGER_MS}ms both">'
            f'<div class="fresh-label"><span class="fresh-dot"></span>Updated last 7d</div>'
            f'<div class="fresh-val">0</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with c4:
        # Show source breakdown with counts
        source_counts = {}
        source_labels = {
            "api": "API",
            "csv": "CSV",
            "ashoka": "Ashoka",
            "rainfall": "Rainfall",
            "varietywise": "Variety Archive",
            "historical_backfill": "Historical",
            "prices_table": "Historical",
        }
        for r in freshness_data:
            if isinstance(r, dict):
                stype_raw = r.get("source_type")
                # Normalize: map NULL/empty/unknown to 'prices_table'
                if not stype_raw or str(stype_raw).strip().lower() in ("", "unknown", "null", "none", "other"):
                    stype_normalized = "prices_table"
                else:
                    stype_normalized = str(stype_raw).strip().lower()
                source_counts[stype_normalized] = source_counts.get(stype_normalized, 0) + 1
        if source_counts:
            parts = []
            for stype in sorted(source_counts.keys()):
                label = source_labels.get(stype, stype.capitalize())
                parts.append(f"{label} ({source_counts[stype]})")
            sources_text = ", ".join(parts)
            st.markdown(
                f'<div class="fresh-card" style="animation:freshEntry 400ms cubic-bezier(0.16,1,0.3,1) {3*_CARD_STAGGER_MS}ms both">'
                f'<div class="fresh-label"><span class="fresh-dot"></span>Data sources</div>'
                f'<div class="fresh-txt">{sources_text}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'<div class="fresh-card" style="animation:freshEntry 400ms cubic-bezier(0.16,1,0.3,1) {3*_CARD_STAGGER_MS}ms both">'
                f'<div class="fresh-label"><span class="fresh-dot"></span>Data sources</div>'
                f'<div class="fresh-txt">—</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    # ── Inject shared CSS + eased count-up rAF loop (matching flip-board style) ──
    st.markdown(
        '<style>'
        '.fresh-card{background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.07);border-radius:8px;padding:0.8rem 1rem;text-align:center;position:relative;overflow:hidden;transition:transform .35s cubic-bezier(0.16,1,0.3,1),border-color .35s ease}'
        '.fresh-card::before,.fresh-card::after{content:\"\";position:absolute;width:10px;height:10px;opacity:0;transition:opacity .35s ease;pointer-events:none}'
        '.fresh-card::before{top:-1px;left:-1px;border-top:1.5px solid #d7ff00;border-left:1.5px solid #d7ff00}'
        '.fresh-card::after{bottom:-1px;right:-1px;border-bottom:1.5px solid #d7ff00;border-right:1.5px solid #d7ff00}'
        '.fresh-card:hover{border-color:rgba(215,255,0,0.15);transform:translateY(-2px)}'
        '.fresh-card:hover::before,.fresh-card:hover::after{opacity:1;box-shadow:0 0 4px 2px rgba(215,255,0,0.25)}'
        '.fresh-label{font-size:0.7rem;color:#7e7e7e;font-family:IBM Plex Mono,monospace;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:0.3rem}'
        '.fresh-dot{display:inline-block;width:6px;height:6px;border-radius:50%;background:#8FAE89;margin-right:4px;vertical-align:middle;animation:fresh-pulse 2s ease-in-out infinite}'
        '.fresh-val{font-size:2rem;font-family:Barlow,IBM Plex Mono,monospace;font-weight:500;color:#ffffff;line-height:1.1}'
        '.fresh-txt{font-size:0.8rem;font-family:IBM Plex Mono,monospace;color:#bababa;line-height:1.1}'
        '@keyframes fresh-pulse{0%,100%{box-shadow:0 0 0 0 rgba(143,174,137,0.6)}50%{box-shadow:0 0 0 6px rgba(143,174,137,0)}}'
        '@keyframes freshEntry{0%{opacity:0;transform:translateY(20px)}100%{opacity:1;transform:translateY(0)}}'

        '</style>',
        unsafe_allow_html=True,
    )

    # ── Freshness Table CSS ──

    # Render the freshness table as styled HTML
    _FRESHNESS_TABLE_CSS = f"""
    <style>
    .freshness-table {{
        width: 100%; border-collapse: collapse;
        font-family: "IBM Plex Sans", system-ui, sans-serif;
        font-size: 0.82rem;
    }}
    .freshness-table th {
        text-align: left; padding: 0.6rem 0.75rem;
        color: #7e7e7e; font-weight: 500; font-size: 0.7rem;
        text-transform: uppercase; letter-spacing: 0.05em;
        border-bottom: 1px solid rgba(255,255,255,0.1);
        white-space: nowrap;
        cursor: pointer;
        user-select: none;
    }
    .freshness-table th .sort-arrow {
        display: inline-block;
        margin-left: 4px;
        font-size: 0.6rem;
        color: #555555;
        transition: color 0.2s ease;
    }
    .freshness-table th .sort-arrow.is-active {
        color: #d7ff00;
    }
    .freshness-table th:hover .sort-arrow {
        color: #7e7e7e;
    }
    .freshness-table td {{
        padding: 0.55rem 0.75rem;
        color: #ffffff;
        border-bottom: 1px solid rgba(255,255,255,0.04);
        white-space: nowrap;
    }}
    .freshness-table tbody tr {{
        transition: transform 0.25s ease;
        transform: scale(1);
        transform-origin: center left;
        backface-visibility: hidden;
    }}
    .freshness-table tbody tr:hover {{
        transform: scale(1.02);
        position: relative;
        z-index: 1;
    }}
    .freshness-table tr:hover td {{
        background: rgba(255,255,255,0.06);
    }}
    .freshness-table .mono {{
        font-family: "IBM Plex Mono", monospace;
        font-variant-numeric: tabular-nums;
    }}
    .freshness-table .num {{
        font-family: "IBM Plex Mono", monospace;
        text-align: right;
        font-variant-numeric: tabular-nums;
    }}
    .freshness-table .source-badge {{
        display: inline-block;
        padding: 0.1rem 0.45rem;
        border-radius: 3px;
        font-size: 0.7rem;
        font-family: "IBM Plex Mono", monospace;
        font-weight: 500;
    }}
    .source-badge-api {{
        background: rgba(215, 255, 0, 0.12);
        color: #d7ff00;
    }}
    .source-badge-csv {{
        background: rgba(139, 107, 196, 0.12);
        color: #8B6BC4;
    }}
    .source-badge-ashoka {{
        background: rgba(217, 102, 59, 0.12);
        color: #D9663B;
    }}
    .source-badge-rainfall {{
        background: rgba(143, 174, 137, 0.12);
        color: #8FAE89;
    }}
    .source-badge-varietywise {{
        background: rgba(180, 131, 84, 0.12);
        color: #B48354;
    }}
    .source-badge-other {{
        background: rgba(186, 186, 186, 0.12);
        color: #bababa;
    }}
    .freshness-table .fresh-dot {{
        display: inline-block;
        width: 7px; height: 7px;
        border-radius: 50%;
        margin-right: 4px;
    }}
    .fresh-dot-recent {{ background: #6BBF8A; }}
    .fresh-dot-stale {{ background: #E8B14D; }}
    .fresh-dot-old   {{ background: #C84B4B; }}
    @keyframes freshRowSlide {{
        0% {{ opacity: 0; transform: translateX(-16px); }}
        100% {{ opacity: 1; transform: translateX(0); }}
    }}
    @keyframes freshHighlight {{
        0% {{ background: rgba(215,255,0,0); box-shadow: inset 4px 0 0 rgba(215,255,0,0); }}
        25% {{ background: rgba(215,255,0,0.05); box-shadow: inset 4px 0 0 rgba(215,255,0,0.4); }}
        100% {{ background: rgba(215,255,0,0); box-shadow: inset 4px 0 0 rgba(215,255,0,0); }}
    }}
    .freshness-table tbody tr.district-expanded {{
        /* Subtle indicator that this row is expanded */
        border-left: 1.5px solid rgba(215,255,0,0.3);
    }}
    .freshness-subrow td {{
        padding: 0 !important;
        border-bottom: none;
    }}
    .freshness-subrow-inner {{
        max-height: 0;
        overflow: hidden;
        transition: max-height 0.3s cubic-bezier(0.16,1,0.3,1);
    }}
    .freshness-subrow-inner.open {{
        max-height: 600px;
    }}
    .district-mini-table {{
        width: 100%;
        border-collapse: collapse;
        font-size: 0.72rem;
        font-family: "IBM Plex Mono", monospace;
        background: rgba(255,255,255,0.02);
    }}
    .district-mini-table th {{
        text-align: left; padding: 0.4rem 0.6rem;
        color: #7e7e7e; font-weight: 500;
        border-bottom: 1px solid rgba(255,255,255,0.06);
    }}
    .district-mini-table td {{
        padding: 0.3rem 0.6rem;
        color: #bababa;
        border-bottom: 1px solid rgba(255,255,255,0.03);
    }}
    .district-mini-table td.num {{
        text-align: right;
        color: #ffffff;
        font-variant-numeric: tabular-nums;
    }}
    </style>
    """
    st.markdown(_FRESHNESS_TABLE_CSS, unsafe_allow_html=True)

    now = datetime.datetime.utcnow()
    _cutoff_recent = now - datetime.timedelta(days=7)
    _cutoff_stale = now - datetime.timedelta(days=30)

    def _to_dt(val):
        """Convert date value (str, Timestamp, date) to datetime, or None."""
        if val is None or val == "—":
            return None
        if isinstance(val, datetime.datetime):
            return val
        if isinstance(val, datetime.date):
            return datetime.datetime.combine(val, datetime.time())
        if isinstance(val, str):
            try:
                return datetime.datetime.strptime(val[:10], "%Y-%m-%d")
            except (ValueError, IndexError):
                return None
        # Pandas Timestamp (subclass of datetime)
        try:
            return datetime.datetime.fromisoformat(str(val)[:10])
        except (ValueError, TypeError):
            return None

    def _fmt(val):
        """Format any date-like value as YYYY-MM-DD string."""
        if val is None or val == "—":
            return "—"
        return str(val)[:10]

    # ── Slide-right entry for table rows ──
    # Fresh-card entry (0–240ms staggered) + count-up (800ms) + landBounce (500ms)
    # ≈ 1300ms total. Rows start sliding in 100ms after the last card bounce lands.
    _ROW_BASE_DELAY_MS = 1400
    _ROW_STAGGER_MS = 30
    _ROW_DURATION_MS = 400

    # ── Pre-fetch district summaries for click-to-expand ──
    _district_map = {}
    for _r in freshness_data:
        if not isinstance(_r, dict):
            continue
        _comm = (_r.get("commodity") or "Other / Uncategorized").title()
        _district_map[_comm] = _cached_district_summary(_comm)
    # ── Find the most recently updated row ──
    # Use a dict-only counter (matching _ROW_IDX in the loop below)
    # so the highlight fires on the correct row even if non-dict
    # entries are present in freshness_data.
    _best_date = None
    _freshest_idx = -1
    _dict_idx = 0
    for _r in freshness_data:
        if not isinstance(_r, dict):
            continue
        _d = _to_dt(_r.get("latest_date"))
        if _d is not None and (_best_date is None or _d > _best_date):
            _best_date = _d
            _freshest_idx = _dict_idx
        _dict_idx += 1

    _ROW_IDX = 0

    rows_html = ""
    for r in _page_freshness_data:
        if not isinstance(r, dict):
            continue
        commodity = (r.get("commodity") or "Other / Uncategorized").title()
        latest_raw = r.get("latest_date")
        earliest_raw = r.get("earliest_date")
        latest_dt = _to_dt(latest_raw)
        latest_str = _fmt(latest_raw)
        earliest_str = _fmt(earliest_raw)
        row_count = r.get("row_count", 0)
        n_districts = r.get("n_districts", 0)
        n_states = r.get("n_states", 0)
        source_type_raw = r.get("source_type")
        source_name = r.get("source_name") or ""

        # Normalize source_type: map NULL/empty/unknown to a standard label
        if not source_type_raw or str(source_type_raw).strip().lower() in ("", "unknown", "null", "none", "other"):
            source_type = "prices_table"
        else:
            source_type = str(source_type_raw).strip().lower()

        # Determine freshness status dot using datetime comparison
        if latest_dt is not None and latest_dt >= _cutoff_recent:
            dot_class = "fresh-dot-recent"
            dot_title = "Updated in last 7 days"
        elif latest_dt is not None and latest_dt >= _cutoff_stale:
            dot_class = "fresh-dot-stale"
            dot_title = "7–30 days old"
        else:
            dot_class = "fresh-dot-old"
            dot_title = "Over 30 days old"

        # Source badge class
        if source_type == "api":
            badge_class = "source-badge-api"
            badge_label = "API"
        elif source_type == "csv":
            badge_class = "source-badge-csv"
            badge_label = "CSV"
        elif source_type == "ashoka":
            badge_class = "source-badge-ashoka"
            badge_label = "Ashoka"
        elif source_type == "rainfall":
            badge_class = "source-badge-rainfall"
            badge_label = "Rainfall"
        elif source_type in ("prices_table", "historical_backfill"):
            badge_class = "source-badge-other"
            badge_label = "HISTORICAL"
        elif source_type == "varietywise":
            badge_class = "source-badge-varietywise"
            badge_label = "Variety"
        else:
            badge_class = "source-badge-other"
            badge_label = source_type[:8].upper()

        # Tooltip for source
        title_attr = f' title="{source_name}"' if source_name else ""

        # Mark the most recently updated row with a subtle highlight
        _is_freshest = _ROW_IDX == _freshest_idx

        row_delay = _ROW_BASE_DELAY_MS + _ROW_IDX * _ROW_STAGGER_MS
        # For the freshest row, add a second animation that pulses lime on the left edge
        # after the slide-in completes. The highlight delay is computed relative to
        # the row's staggered slide delay so it always fires after the row is visible.
        if _is_freshest:
            _hl_delay = row_delay + _ROW_DURATION_MS + 200  # 200ms grace after slide finishes
            _tr_anim = (
                f"freshRowSlide {_ROW_DURATION_MS}ms cubic-bezier(0.16,1,0.3,1) {row_delay}ms both, "
                f"freshHighlight 1.6s ease-out {_hl_delay}ms"
            )
        else:
            _tr_anim = f"freshRowSlide {_ROW_DURATION_MS}ms cubic-bezier(0.16,1,0.3,1) {row_delay}ms both"

        rows_html += (
            f'<tr data-commodity="{commodity}" style="animation:{_tr_anim};">'
            f'<td><span class="fresh-dot {dot_class}" title="{dot_title}"></span>{commodity}</td>'
            f'<td class="mono">{latest_str}</td>'
            f'<td class="mono">{earliest_str}</td>'
            f'<td class="num">{row_count:,}</td>'
            f'<td class="num">{n_districts}</td>'
            f'<td class="num">{n_states}</td>'
            f'<td><span class="source-badge {badge_class}"{title_attr}>{badge_label}</span></td>'
            f"</tr>"
        )
        _ROW_IDX += 1

    table_html = (
        '<div class="glass" style="padding:1rem;overflow-x:auto;">'
        '<table class="freshness-table">'
        "<thead><tr>"
        "<th data-sort-type=\"text\">Commodity <span class=\"sort-arrow\"></span></th>"
        "<th data-sort-type=\"date\">Latest Date <span class=\"sort-arrow\"></span></th>"
        "<th data-sort-type=\"date\">Earliest Date <span class=\"sort-arrow\"></span></th>"
        "<th data-sort-type=\"number\" style=\"text-align:right;\">Rows <span class=\"sort-arrow\"></span></th>"
        "<th data-sort-type=\"number\" style=\"text-align:right;\">Districts <span class=\"sort-arrow\"></span></th>"
        "<th data-sort-type=\"number\" style=\"text-align:right;\">States <span class=\"sort-arrow\"></span></th>"
        "<th data-sort-type=\"text\">Source <span class=\"sort-arrow\"></span></th>"
        "</tr></thead><tbody>"
        f"{rows_html}"
        "</tbody></table></div>"
    )
    st.markdown(table_html, unsafe_allow_html=True)

    # ── Embed district data as JSON for client-side expand ──
    try:
        _district_json = json.dumps(_district_map)
        st.markdown(
            f'<script id="mandiiq-district-data" type="application/json">{_district_json}</script>',
            unsafe_allow_html=True,
        )
    except Exception:
        pass

    # ── Column sorting JavaScript ──
    _inject_freshness_sorting()
    _inject_freshness_expand()

    # ── Rows per page selector (always visible when there's data) ──
    _rp1, _rp2 = st.columns([2, 4])
    with _rp1:
        _new_size = st.selectbox(
            "Rows per page",
            [10, 20, 50, 100],
            index=[10, 20, 50, 100].index(st.session_state.freshness_page_size),
            key="freshness_rpp",
            label_visibility="collapsed",
        )
        if _new_size != st.session_state.freshness_page_size:
            st.session_state.freshness_page_size = _new_size
            st.session_state.freshness_page = 0
            st.rerun()
    with _rp2:
        st.markdown(
            f'<div style="text-align:right;padding-top:0.3rem;">'
            f'<span style="color:{MUTED};font-size:0.8rem;font-family:IBM Plex Mono,monospace;">'
            f'Page {_fresh_page + 1} of {_TOTAL_FRESH_PAGES}'
            f'<span style="color:#555555;margin-left:8px;">({len(freshness_data):,} commodities)</span>'
            f'</span></div>',
            unsafe_allow_html=True,
        )

    # ── Pagination navigation buttons ──
    if _TOTAL_FRESH_PAGES > 1:
        _pc = st.columns([1, 1, 2, 1, 1])
        with _pc[0]:
            if st.button("⏮ First", disabled=(_fresh_page == 0), key="fresh_pg_first", use_container_width=True):
                st.session_state.freshness_page = 0
                st.rerun()
        with _pc[1]:
            if st.button("← Prev", disabled=(_fresh_page == 0), key="fresh_pg_prev", use_container_width=True):
                st.session_state.freshness_page = max(0, _fresh_page - 1)
                st.rerun()
        with _pc[2]:
            _jump_to = st.number_input(
                "Jump to page",
                min_value=1,
                max_value=_TOTAL_FRESH_PAGES,
                value=_fresh_page + 1,
                step=1,
                label_visibility="collapsed",
                key="freshness_page_input",
            )
            if _jump_to != _fresh_page + 1:
                st.session_state.freshness_page = _jump_to - 1
                st.rerun()
        with _pc[3]:
            if st.button("Next →", disabled=(_fresh_page >= _TOTAL_FRESH_PAGES - 1), key="fresh_pg_next", use_container_width=True):
                st.session_state.freshness_page = min(_TOTAL_FRESH_PAGES - 1, _fresh_page + 1)
                st.rerun()
        with _pc[4]:
            if st.button("⏭ Last", disabled=(_fresh_page >= _TOTAL_FRESH_PAGES - 1), key="fresh_pg_last", use_container_width=True):
                st.session_state.freshness_page = _TOTAL_FRESH_PAGES - 1
                st.rerun()


def _inject_freshness_sorting():
    """Inject client-side column sorting for the freshness table.

    Adds click handlers to all `<th data-sort-type>` elements in the
    freshness table. Clicking a header sorts ascending first, then
    toggles descending on subsequent clicks. Uses DOM row re-ordering
    (no redraw from Streamlit).
    """
    js = """<script>
(function() {
  'use strict';
  if (window.__mandiiqFreshSort) return;
  window.__mandiiqFreshSort = true;

  function findTable() {
    return document.querySelector('.freshness-table');
  }

  function getCellText(row, idx) {
    var cells = row.querySelectorAll('td');
    if (idx >= cells.length) return '';
    return cells[idx].textContent.trim();
  }

  function parseSortVal(text, type) {
    if (type === 'number') {
      // Remove commas and parse
      var num = parseFloat(text.replace(/,/g, ''));
      return isNaN(num) ? -Infinity : num;
    }
    if (type === 'date') {
      // Parse YYYY-MM-DD: valid → timestamp (number), invalid → -Infinity
      var d = Date.parse(text);
      return isNaN(d) ? -Infinity : d;
    }
    // text type
    return text.toLowerCase();
  }

  function updateArrows(th, dir) {
    var table = findTable();
    if (!table) return;
    var allTh = table.querySelectorAll('thead th');
    allTh.forEach(function(h) {
      var arrow = h.querySelector('.sort-arrow');
      if (arrow) {
        arrow.classList.remove('is-active');
        arrow.textContent = '';
      }
    });
    var arrow = th.querySelector('.sort-arrow');
    if (arrow) {
      arrow.classList.add('is-active');
      arrow.textContent = dir === 'asc' ? '\u25b2' : '\u25bc';
    }
  }

  document.addEventListener('click', function(e) {
    var th = e.target.closest('.freshness-table thead th[data-sort-type]');
    if (!th) return;

    var table = findTable();
    if (!table) return;
    var tbody = table.querySelector('tbody');
    if (!tbody) return;

    // Determine column index from th position in thead row
    var headers = Array.from(table.querySelectorAll('thead th'));
    var idx = headers.indexOf(th);
    if (idx === -1) return;

    var sortType = th.getAttribute('data-sort-type') || 'text';

    // Toggle direction: if this th is already active, flip; else asc
    var arrow = th.querySelector('.sort-arrow');
    var isActive = arrow && arrow.classList.contains('is-active');
    var dir = (isActive && arrow.textContent === '\u25b2') ? 'desc' : 'asc';

    // Exclude sub-rows (freshness-subrow) from sort so expand-then-sort
    // keeps district breakdowns correctly positioned.
    var rows = Array.from(tbody.querySelectorAll('tr[data-commodity]'));

    rows.sort(function(a, b) {
      var va = parseSortVal(getCellText(a, idx), sortType);
      var vb = parseSortVal(getCellText(b, idx), sortType);
      if (va < vb) return dir === 'asc' ? -1 : 1;
      if (va > vb) return dir === 'asc' ? 1 : -1;
      return 0;
    });

    // Re-append in sorted order (removes animation inline styles for clean state)
    rows.forEach(function(row) {
      row.style.animation = '';
      row.style.opacity = '1';
      row.style.transform = '';
      tbody.appendChild(row);
    });

    updateArrows(th, dir);
  });
})();
</script>"""
    import streamlit as st
    st.markdown(js, unsafe_allow_html=True)


def _inject_freshness_expand():
    """Inject click-to-expand row detail for the freshness table.

    Clicking any `<tr data-commodity="...">` inserts a sub-row beneath
    it with a per-district price breakdown. Toggle click collapses it.
    """
    js = """<script>
(function() {
  'use strict';
  if (window.__mandiiqFreshExpand) return;
  window.__mandiiqFreshExpand = true;

  var dataScript = document.getElementById('mandiiq-district-data');
  if (!dataScript) return;
  var districtData = {};
  try { districtData = JSON.parse(dataScript.textContent); } catch(e) { return; }

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#039;');
  }

  function fmtPrice(v) {
    if (v === null || v === undefined) return '\u2014';
    return '\u20b9' + Number(v).toLocaleString('en-IN', {maximumFractionDigits:0});
  }

  function buildSubrow(commodity) {
    var districts = districtData[commodity];
    if (!districts || districts.length === 0) {
      return '<tr class="freshness-subrow"><td colspan="7" style="padding:0.6rem 0.75rem;color:#7e7e7e;font-size:0.75rem;text-align:center;">No district-level data available</td></tr>';
    }

    var rows = districts.map(function(d) {
      return '<tr>'
        + '<td>' + escapeHtml(d.district) + '</td>'
        + '<td style="color:#7e7e7e;">' + escapeHtml(d.state) + '</td>'
        + '<td class="num">' + (d.obs || 0).toLocaleString('en-IN') + '</td>'
        + '<td class="num">' + fmtPrice(d.avg_price) + '</td>'
        + '<td class="num">' + fmtPrice(d.min_price) + '</td>'
        + '<td class="num">' + fmtPrice(d.max_price) + '</td>'
        + '<td style="color:#7e7e7e;font-size:0.7rem;">' + (d.last_date || '\u2014') + '</td>'
        + '</tr>';
    }).join('');

    return '<tr class="freshness-subrow"><td colspan="7" style="padding:0;">'
      + '<div class="freshness-subrow-inner">'
      + '<table class="district-mini-table">'
      + '<thead><tr>'
      + '<th>District</th><th>State</th><th style="text-align:right;">Obs</th>'
      + '<th style="text-align:right;">Avg \u20b9</th><th style="text-align:right;">Min</th>'
      + '<th style="text-align:right;">Max</th><th>Latest</th>'
      + '</tr></thead><tbody>'
      + rows
      + '</tbody></table>'
      + '</div></td></tr>';
  }

  var tbody = document.querySelector('.freshness-table tbody');
  if (!tbody) return;

  tbody.addEventListener('click', function(e) {
    // Ignore clicks on the sorting header
    if (e.target.closest('th')) return;

    var tr = e.target.closest('tr[data-commodity]');
    if (!tr) return;

    var commodity = tr.getAttribute('data-commodity');
    if (!commodity) return;

    // Check if already expanded (next sibling is a sub-row)
    var next = tr.nextElementSibling;
    if (next && next.classList.contains('freshness-subrow')) {
      // Collapse
      var inner = next.querySelector('.freshness-subrow-inner');
      if (inner) inner.classList.remove('open');
      setTimeout(function() { if (next.parentNode) next.parentNode.removeChild(next); }, 300);
      tr.classList.remove('district-expanded');
      return;
    }

    // Remove any existing expanded sub-rows (in case sorting changed the DOM)
    tbody.querySelectorAll('.freshness-subrow').forEach(function(sr) { sr.parentNode.removeChild(sr); });
    tbody.querySelectorAll('.district-expanded').forEach(function(r) { r.classList.remove('district-expanded'); });

    // Insert new sub-row right after the clicked row
    var subrowHtml = buildSubrow(commodity);
    var temp = document.createElement('tbody');
    temp.innerHTML = subrowHtml;
    var subrow = temp.firstElementChild;
    tr.parentNode.insertBefore(subrow, tr.nextElementSibling);
    tr.classList.add('district-expanded');

    // Animate the inner height
    requestAnimationFrame(function() {
      var inner = subrow.querySelector('.freshness-subrow-inner');
      if (inner) inner.classList.add('open');
    });
  });
})();
</script>"""
    import streamlit as st
    st.markdown(js, unsafe_allow_html=True)


@st.cache_data(ttl=120, show_spinner=False)
def _cached_freshness():
    """Cached freshness data from the API. TTL=120s."""
    try:
        from mandi_rdd.dashboard.data_access import get_freshness
        return get_freshness()
    except Exception:
        return []


@st.cache_data(ttl=600, show_spinner=False)
def _cached_district_summary(commodity: str) -> list[dict]:
    """Return per-district price summary for a commodity (top 15 districts)."""
    try:
        conn = get_connection(read_only=True)
        try:
            rows = conn.execute("""
                SELECT district, state, COUNT(*) AS obs,
                       AVG(modal_price) AS avg_price,
                       MIN(modal_price) AS min_price,
                       MAX(modal_price) AS max_price,
                       MIN(arrival_date) AS first_date,
                       MAX(arrival_date) AS last_date
                FROM prices
                WHERE LOWER(commodity) = LOWER(?) AND modal_price IS NOT NULL
                GROUP BY district, state
                ORDER BY COUNT(*) DESC
                LIMIT 15
            """, [commodity]).fetchall()
            results = []
            for r in rows:
                results.append({
                    "district": r[0],
                    "state": r[1],
                    "obs": int(r[2]) if r[2] else 0,
                    "avg_price": round(float(r[3]), 2) if r[3] else None,
                    "min_price": round(float(r[4]), 2) if r[4] else None,
                    "max_price": round(float(r[5]), 2) if r[5] else None,
                    "first_date": str(r[6])[:10] if r[6] else None,
                    "last_date": str(r[7])[:10] if r[7] else None,
                })
            return results
        finally:
            conn.close()
    except Exception:
        return []


def _render_ask_panel(default_commodity: str):
    """
    Render the 'Ask MandiIQ' AI chat panel with Alche-styled components.
    """
    st.markdown(
        """
        <div style="margin-top:2.5rem;">
          <div style="font-family:'IBM Plex Mono',monospace;font-size:0.75rem;color:#d7ff00;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:0.5rem;">
            03 / AI Procurement
          </div>
          <h2 style="font-family:'Space Grotesk',system-ui,sans-serif;font-weight:400;font-size:1.4rem;color:#ffffff;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:1rem;">
            Ask MandiIQ <span style="font-size:1.2rem;">🧠</span>
          </h2>
          <p style="color:#7e7e7e;font-size:0.85rem;margin-bottom:1rem;">
            Ask a procurement question in plain English. Answers are grounded in live
            tool-call results. Powered by <strong style="color:#bababa;">free-tier multi-model routing</strong>
            (Gemini direct or OpenRouter) with circuit-breaker fallback.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Check API availability ──
    api_available = False
    api_error = None
    try:
        import requests
        resp = requests.get(f"{API_BASE}/health", timeout=3)
        if resp.status_code == 200:
            api_available = True
        else:
            api_error = f"API server returned status {resp.status_code}"
    except ImportError:
        api_error = (
            "<code>requests</code> library not installed. "
            "Run: <code>pip install requests</code>"
        )
    except requests.exceptions.ConnectionError:
        api_error = (
            f"Cannot reach the API server at <code>{API_BASE}</code>. "
            "Start it with: <code>uvicorn mandi_rdd.api.main:app --reload</code>"
        )
    except requests.exceptions.Timeout:
        api_error = f"API server at <code>{API_BASE}</code> timed out."
    except Exception as e:
        api_error = f"Cannot connect to API: {e}"

    if not api_available:
        st.markdown(
            f'<div class="interpretation-box insig-box">⚠️ API server is not available. {api_error}</div>',
            unsafe_allow_html=True,
        )
        return

    # ── Chat UI ──
    if "ask_history" not in st.session_state:
        st.session_state.ask_history = []
    if "ask_input_key" not in st.session_state:
        st.session_state.ask_input_key = 0

    query = st.text_area(
        "Your question",
        placeholder=(
            f'e.g. "Should I lock in {default_commodity} procurement in Nashik next month?"'
        ),
        height=80,
        label_visibility="collapsed",
        key=f"ask_input_{st.session_state.ask_input_key}",
    )

    col_q1, col_q2, _ = st.columns([1, 1, 6])
    with col_q1:
        asked = st.button("🔍 Ask MandiIQ", type="primary", use_container_width=True)
    with col_q2:
        clear = st.button("Clear", use_container_width=True)

    if clear:
        st.session_state.ask_history = []
        st.session_state.ask_input_key += 1
        st.rerun()

    # ── Submit — POST /ask to the API ──
    if asked and query.strip():
        with st.spinner("Routing through OpenRouter fallback chain..."):
            try:
                resp = requests.post(
                    f"{API_BASE}/ask",
                    json={
                        "query": query.strip(),
                        "commodity": default_commodity,
                    },
                    timeout=30,
                )
                if resp.status_code == 200:
                    result = resp.json()
                else:
                    try:
                        detail = resp.json()
                    except Exception:
                        detail = {"error": f"HTTP {resp.status_code}"}
                    result = {
                        "query": query.strip(),
                        "commodity": default_commodity,
                        "district": "All",
                        "answer": f"API returned an error (HTTP {resp.status_code}).",
                        "model_used": None,
                        "endpoints_used": [],
                        "error": detail.get("detail", detail.get("error", str(resp.status_code))),
                    }

                err = result.get("error") or ""
                if ("API_KEY" in err or "provider" in err.lower()
                        or "openrouter" in err.lower() or "gemini" in err.lower()):
                    result["answer"] = (
                        "⚠️ **AI chat is not configured.** No LLM provider key is set "
                        "on the API server. Set **GEMINI_API_KEY** (free — get one at "
                        "[aistudio.google.com/apikey](https://aistudio.google.com/apikey)) "
                        "or **OPENROUTER_API_KEY** (free — "
                        "[openrouter.ai/keys](https://openrouter.ai/keys)) to enable the "
                        "Ask MandiIQ feature. No credit card required for either."
                    )

                st.session_state.ask_history.append(result)
            except requests.exceptions.Timeout:
                st.session_state.ask_history.append({
                    "query": query.strip(),
                    "commodity": default_commodity,
                    "district": "All",
                    "answer": "The request timed out. The orchestrator may be slow to respond (free-tier model latency varies). Try again or simplify your question.",
                    "model_used": None,
                    "endpoints_used": [],
                    "error": "Request timed out after 30 seconds",
                })
            except requests.exceptions.RequestException as e:
                st.session_state.ask_history.append({
                    "query": query.strip(),
                    "commodity": default_commodity,
                    "district": "All",
                    "answer": f"Could not reach the API server: {e}",
                    "model_used": None,
                    "endpoints_used": [],
                    "error": str(e),
                })
            except Exception as e:
                st.session_state.ask_history.append({
                    "query": query.strip(),
                    "commodity": default_commodity,
                    "district": "All",
                    "answer": f"Unexpected error: {e}",
                    "model_used": None,
                    "endpoints_used": [],
                    "error": str(e),
                })

    # Display chat history using interpretation boxes
    for i, entry in enumerate(reversed(st.session_state.ask_history)):
        _render_chat_entry(entry, i)


def _render_chat_entry(entry: dict, idx: int):
    """Render a single chat entry using Alche interpretation box styling."""
    answer = entry.get("answer", "No answer generated.")
    model_used = entry.get("model_used")
    endpoints_used = entry.get("endpoints_used", [])
    error = entry.get("error")
    query = entry.get("query", "")
    commodity = entry.get("commodity", "")
    district = entry.get("district", "")

    # Answer box
    st.markdown(
        f"""
        <div class="interpretation-box" style="margin:0.8rem 0;">
            <div style="font-size:0.75rem;color:#7e7e7e;margin-bottom:0.5rem;">
                📝 <strong style="color:#bababa;">{query}</strong>
            </div>
            {answer}
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Collapsible metadata
    if model_used or endpoints_used or error:
        with st.expander("⚙️ Response metadata", expanded=False):
            if model_used:
                st.markdown(
                    f'<span style="color:#7e7e7e;font-size:0.8rem;">Served by:</span> '
                    f'<span style="font-family:IBM Plex Mono;color:#d7ff00;font-size:0.8rem;">{model_used}</span>',
                    unsafe_allow_html=True,
                )
            if endpoints_used:
                eps = ", ".join(endpoints_used)
                st.markdown(
                    f'<span style="color:#7e7e7e;font-size:0.8rem;">Endpoints cited:</span> '
                    f'<span style="font-family:IBM Plex Mono;color:#d7ff00;font-size:0.8rem;">{eps}</span>',
                    unsafe_allow_html=True,
                )
            if commodity or district:
                st.markdown(
                    f'<span style="color:#7e7e7e;font-size:0.8rem;">Context:</span> '
                    f'<span style="color:#ffffff;font-size:0.8rem;">{commodity} — {district}</span>',
                    unsafe_allow_html=True,
                )
            if error:
                st.markdown(
                    f'<span style="color:#D9663B;font-size:0.8rem;">⚠️ {error}</span>',
                    unsafe_allow_html=True,
                )


def _render_national_monsoon_strip():
    """Compact glass strip: national monsoon baseline 1901-2019 + sparkline."""
    data = _cached_all_india_monsoon()
    if not data:
        return
    try:
        df = pd.DataFrame(data)
        mean_total = float(df["jun_sep"].mean())
        worst = df.loc[df["jun_sep"].idxmin()]
        best = df.loc[df["jun_sep"].idxmax()]
        last = float(df.iloc[-1]["jun_sep"])

        st.markdown(
            """
            <div style="margin-top:1.5rem;">
              <div style="font-family:'IBM Plex Mono',monospace;font-size:0.75rem;color:#d7ff00;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:0.5rem;">
                CENTURY-SCALE CONTEXT
              </div>
              <h2 style="font-family:'Space Grotesk',system-ui,sans-serif;font-weight:400;font-size:1.2rem;color:#ffffff;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:0.8rem;">
                National Monsoon Baseline · 1901–2019
              </h2>
              <p style="color:#7e7e7e;font-size:0.85rem;max-width:700px;line-height:1.7;margin-bottom:1.2rem;">
                The long IMD series — a national reference frame for the district-level
                rainfall-deficit threshold that drives the causal analysis.
              </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Glass card for monsoon metrics
        st.markdown('<div class="glass" style="padding:1.2rem;">', unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns([1, 1, 1, 2.2])
        with c1:
            st.metric("Avg monsoon", f"{mean_total:.0f} mm", help="Mean Jun–Sep total, 1901–2019")
        with c2:
            st.metric("Driest", f"{float(worst['jun_sep']):.0f} mm", f"{int(worst['year'])}")
        with c3:
            st.metric("Wettest", f"{float(best['jun_sep']):.0f} mm", f"{int(best['year'])}")
        with c4:
            fig = make_themed_figure()
            fig.add_trace(go.Scatter(
                x=df["year"], y=df["jun_sep"], mode="lines",
                line=dict(color="#d7ff00", width=2), fill="tozeroy",
                fillcolor="rgba(234,179,8,0.10)", showlegend=False,
            ))
            fig.add_hline(y=mean_total * 0.81, line_color="#A85A42", line_dash="dash",
                          line_width=1, annotation_text="−19%", annotation_position="top left")
            fig.update_layout(margin=dict(l=0, r=0, t=4, b=0), height=90,
                              xaxis=dict(visible=False), yaxis=dict(visible=False))
            st.plotly_chart(fig, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
    except Exception:
        return
