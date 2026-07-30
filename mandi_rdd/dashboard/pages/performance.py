"""
MandiIQ — Performance Audit (Hidden Debug Route)
───────────────────────────────────────────────────

Measures real-time browser performance metrics:
  • FPS (instant + 1s rolling average + 60-bin history)
  • Cumulative Layout Shift (CLS) via PerformanceObserver
  • Long Tasks (>50ms) via PerformanceObserver
  • Lenis scroll frame duration
  • GSAP tick timing
  • Three.js WebGL frame timing

All metrics are collected by an inline performance monitor script and
displayed in live-updating glass cards. The monitor persists across
Streamlit reruns (stored in window.__mandiiqPerfMonitor).

Accessible at /performance — not listed in the sidebar nav.
"""

import streamlit as st
from pathlib import Path
from mandi_rdd.dashboard.theme import inject_theme, TURMERIC, RUST, SAGE, SLATE, MUTED, FAINT, INK

# ── The performance monitor JavaScript — bundled inline ──
_PERF_MONITOR_JS = """
<script>
(function() {
  'use strict';
  if (window.__mandiiqPerfInit) return;
  window.__mandiiqPerfInit = true;

  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

  // ═══════════════════════════════════════════════════════════════
  // Performance Monitor — collects FPS, CLS, Lenis, GSAP, WebGL
  // ═══════════════════════════════════════════════════════════════

  var PM = window.__mandiiqPerfMonitor || {
    fps: { instant: 0, avg1s: 0, history: [] },
    cls: { value: 0, rawEntries: [], history: [] },
    lenis: { frameDuration: 0, avgDuration: 0, history: [] },
    gsap: { frameDuration: 0, avgDuration: 0, history: [] },
    webgl: { frameDuration: 0, avgDuration: 0, fps: 0, history: [] },
    longTasks: [],
    memory: { jsHeapSize: null, jsHeapLimit: null },
    startedAt: Date.now(),
    isRunning: true,
  };

  // ── FPS Tracking ──
  var frameTimes = [];
  var fpsHistory = [];           // 1-second binned FPS, last 60 entries
  var lastFPSTime = performance.now();
  var frameCount = 0;

  function trackFPS(now) {
    frameCount++;
    var elapsed = now - lastFPSTime;
    if (elapsed >= 1000) {
      var currentFPS = Math.round(frameCount / (elapsed / 1000));
      PM.fps.instant = currentFPS;
      fpsHistory.push(currentFPS);
      if (fpsHistory.length > 60) fpsHistory.shift();
      PM.fps.history = fpsHistory;
      // Rolling 1s average (last 5 bins ≈ 5s window)
      var recent = fpsHistory.slice(-5);
      PM.fps.avg1s = recent.length > 0
        ? Math.round(recent.reduce(function(a, b) { return a + b; }, 0) / recent.length)
        : 0;
      frameCount = 0;
      lastFPSTime = now;
    }
  }

  // RAF loop for FPS tracking
  function rafLoop(time) {
    if (!PM.isRunning) return;
    trackFPS(time);
    requestAnimationFrame(rafLoop);
  }
  requestAnimationFrame(rafLoop);

  // ── Cumulative Layout Shift (CLS) ──
  try {
    var clsObserver = new PerformanceObserver(function(list) {
      var entries = list.getEntries();
      entries.forEach(function(entry) {
        if (!entry.hadRecentInput) {
          PM.cls.value += entry.value;
          PM.cls.rawEntries.push({
            value: entry.value,
            time: Date.now() - PM.startedAt,
          });
          // Keep 1-minute history
          var cutoff = Date.now() - 60000;
          PM.cls.rawEntries = PM.cls.rawEntries.filter(function(e) {
            return (PM.startedAt + e.time) > cutoff;
          });
        }
      });
      // Bin CLS into 1-second buckets for history
      PM.cls.history = binClsHistory(PM.cls.rawEntries);
    });
    clsObserver.observe({ type: 'layout-shift', buffered: true });
  } catch(e) {}

  function binClsHistory(rawEntries) {
    if (!rawEntries.length) return [];
    var bins = {};
    rawEntries.forEach(function(e) {
      var sec = Math.floor(e.time / 1000);
      bins[sec] = (bins[sec] || 0) + e.value;
    });
    var result = [];
    var maxSec = Math.max.apply(null, Object.keys(bins).map(Number));
    var minSec = Math.max(0, maxSec - 59);
    for (var s = minSec; s <= maxSec; s++) {
      result.push(bins[s] || 0);
    }
    return result.slice(-60);
  }

  // ── Long Tasks (>50ms) ──
  try {
    var longTaskObserver = new PerformanceObserver(function(list) {
      list.getEntries().forEach(function(entry) {
        PM.longTasks.push({
          duration: entry.duration,
          startTime: entry.startTime,
          name: entry.name || 'unknown',
        });
        if (PM.longTasks.length > 100) PM.longTasks.shift();
      });
    });
    longTaskObserver.observe({ type: 'longtask', buffered: true });
  } catch(e) {}

  // ── Memory Usage ──
  function sampleMemory() {
    try {
      if (performance.memory) {
        PM.memory.jsHeapSize = performance.memory.usedJSHeapSize;
        PM.memory.jsHeapLimit = performance.memory.jsHeapSizeLimit;
      }
    } catch(e) {}
  }
  setInterval(sampleMemory, 5000);
  sampleMemory();

  // ── Lenis Scroll Timing ──
  // Hook into Lenis by patching the on('scroll') registration
  // and measuring the time between scroll events.
  var lenisFrameCount = 0;
  var lenisFrameTotal = 0;
  var lenisHistory = [];
  var lastLenisTime = null;

  // Poll for Lenis and hook into its scroll event
  function tryHookLenis() {
    if (PM.lenis._hooked) return true;
    var lenis = window.__mandiiqLenis;
    if (lenis && typeof lenis.on === 'function') {
      PM.lenis._hooked = true;
      // Wrap the existing scroll handler if any — but we just listen separately
      lenis.on('scroll', function(pos) {
        if (!PM.isRunning) return;
        var now = performance.now();
        if (lastLenisTime !== null) {
          var dt = now - lastLenisTime;
          PM.lenis.frameDuration = Math.round(dt * 10) / 10;
          lenisFrameCount++;
          lenisFrameTotal += dt;
          PM.lenis.avgDuration = Math.round((lenisFrameTotal / lenisFrameCount) * 10) / 10;
          lenisHistory.push(dt);
          if (lenisHistory.length > 120) lenisHistory.shift();
          PM.lenis.history = lenisHistory;
        }
        lastLenisTime = now;
      });
      return true;
    }
    return false;
  }

  // Try immediately, then poll for up to 5s
  if (!tryHookLenis()) {
    var lenisPoll = 0;
    var lenisTimer = setInterval(function() {
      lenisPoll++;
      if (tryHookLenis() || lenisPoll > 50) clearInterval(lenisTimer);
    }, 100);
  }

  // ── GSAP Tick Timing ──
  var gsapFrameCount = 0;
  var gsapFrameTotal = 0;
  var gsapHistory = [];
  var gsapLastTime = null;

  function tryHookGsap() {
    if (PM.gsap._hooked) return true;
    if (typeof gsap !== 'undefined' && gsap.ticker) {
      PM.gsap._hooked = true;
      gsap.ticker.add(function() {
        if (!PM.isRunning) return;
        var now = performance.now();
        if (gsapLastTime !== null) {
          var dt = now - gsapLastTime;
          PM.gsap.frameDuration = Math.round(dt * 10) / 10;
          gsapFrameCount++;
          gsapFrameTotal += dt;
          PM.gsap.avgDuration = Math.round((gsapFrameTotal / gsapFrameCount) * 10) / 10;
          gsapHistory.push(dt);
          if (gsapHistory.length > 120) gsapHistory.shift();
          PM.gsap.history = gsapHistory;
        }
        gsapLastTime = now;
      });
      return true;
    }
    return false;
  }

  if (!tryHookGsap()) {
    var gsapPoll = 0;
    var gsapTimer = setInterval(function() {
      gsapPoll++;
      if (tryHookGsap() || gsapPoll > 50) clearInterval(gsapTimer);
    }, 100);
  }

  // ── Three.js WebGL Timing ──
  // Monitor by instrumenting requestAnimationFrame inside WebGL render loops.
  // We patch the renderer's setAnimationLoop or wrap requestAnimationFrame
  // for Three.js canvases.
  var webglFrameCount = 0;
  var webglFrameTotal = 0;
  var webglHistory = [];
  var webglLastTime = null;

  // Monkey-patch rAF to detect Three.js render calls
  // We tag rAF callbacks from Three.js canvases by checking if a callback
  // originates from a WebGL context (canvas.getContext('webgl') or 'webgl2')
  var origRAF = window.requestAnimationFrame;
  // We can't easily tell which rAF calls are from Three.js, so we measure
  // ALL rAF callback durations and assume the most frequent callback is
  // the render loop. Store timing of last 100 callbacks.
  var rafCallbackTimings = [];

  // Instead, poll the Three.js canvas performance: if a <canvas> with a
  // WebGL context exists, check its FPS by tracking rAF callbacks that
  // happen near vsync (~16.6ms intervals)
  function sampleWebGL() {
    var canvases = document.querySelectorAll('canvas');
    for (var i = 0; i < canvases.length; i++) {
      var gl = canvases[i].getContext('webgl2') || canvases[i].getContext('webgl');
      if (gl) {
        // Found a WebGL canvas — track frame timing using RAF delta
        var now = performance.now();
        if (webglLastTime !== null) {
          var dt = now - webglLastTime;
          if (dt > 5 && dt < 100) {  // Likely a render frame (5-100ms)
            PM.webgl.frameDuration = Math.round(dt * 10) / 10;
            PM.webgl.fps = Math.round(1000 / dt);
            webglFrameCount++;
            webglFrameTotal += dt;
            PM.webgl.avgDuration = Math.round((webglFrameTotal / webglFrameCount) * 10) / 10;
            webglHistory.push(dt);
            if (webglHistory.length > 120) webglHistory.shift();
            PM.webgl.history = webglHistory;
          }
        }
        webglLastTime = now;
        break; // Only track one canvas
      }
    }
  }

  // Sample WebGL frames at ~60fps via rAF
  function webglRAFLoop(time) {
    if (!PM.isRunning) return;
    sampleWebGL();
    requestAnimationFrame(webglRAFLoop);
  }

  // Only start WebGL monitoring if we detect a WebGL canvas within 5s
  var checkCanvasTimer = setInterval(function() {
    var canvases = document.querySelectorAll('canvas');
    var hasWebGL = false;
    for (var i = 0; i < canvases.length; i++) {
      var gl = canvases[i].getContext('webgl2') || canvases[i].getContext('webgl');
      if (gl) { hasWebGL = true; break; }
    }
    if (hasWebGL) {
      requestAnimationFrame(webglRAFLoop);
      clearInterval(checkCanvasTimer);
    }
  }, 500);

  // Timeout after 10s
  setTimeout(function() {
    clearInterval(checkCanvasTimer);
  }, 10000);

  // ── DOM Update Loop (polls every 200ms, writes to DOM elements) ──
  function updateDOM() {
    if (!PM.isRunning) return;

    // Update FPS
    var fpsEl = document.getElementById('perf-fps-value');
    if (fpsEl) {
      fpsEl.textContent = PM.fps.avg1s;
      var fpsColor = PM.fps.avg1s >= 55 ? '#8FAE89' : (PM.fps.avg1s >= 30 ? '#d7ff00' : '#D9663B');
      fpsEl.style.color = fpsColor;
    }
    var fpsDetail = document.getElementById('perf-fps-detail');
    if (fpsDetail) {
      fpsDetail.textContent = PM.fps.instant + ' fps (instant)';
    }

    // Update CLS
    var clsEl = document.getElementById('perf-cls-value');
    if (clsEl) {
      var clsDisplay = PM.cls.value.toFixed(4);
      clsEl.textContent = clsDisplay;
      var clsColor = PM.cls.value < 0.1 ? '#8FAE89' : (PM.cls.value < 0.25 ? '#d7ff00' : '#D9663B');
      clsEl.style.color = clsColor;
    }
    var clsDetail = document.getElementById('perf-cls-detail');
    if (clsDetail) {
      var clsEntries = PM.cls.rawEntries.length;
      clsDetail.textContent = clsEntries + ' shifts tracked';
    }

    // Update Lenis
    var lenisEl = document.getElementById('perf-lenis-value');
    if (lenisEl) {
      var lenisVal = PM.lenis.avgDuration || 0;
      lenisEl.textContent = lenisVal.toFixed(1) + 'ms';
      var lenisColor = lenisVal < 20 ? '#8FAE89' : (lenisVal < 50 ? '#d7ff00' : '#D9663B');
      lenisEl.style.color = lenisColor;
    }
    var lenisDetail = document.getElementById('perf-lenis-detail');
    if (lenisDetail) {
      lenisDetail.textContent = (PM.lenis.frameDuration || 0).toFixed(1) + 'ms (last)';
    }

    // Update GSAP
    var gsapEl = document.getElementById('perf-gsap-value');
    if (gsapEl) {
      var gsapVal = PM.gsap.avgDuration || 0;
      gsapEl.textContent = gsapVal.toFixed(1) + 'ms';
      var gsapColor = gsapVal < 20 ? '#8FAE89' : (gsapVal < 50 ? '#d7ff00' : '#D9663B');
      gsapEl.style.color = gsapColor;
    }
    var gsapDetail = document.getElementById('perf-gsap-detail');
    if (gsapDetail) {
      gsapDetail.textContent = (PM.gsap.frameDuration || 0).toFixed(1) + 'ms (last)';
    }

    // Update WebGL
    var webglEl = document.getElementById('perf-webgl-value');
    if (webglEl) {
      var webglVal = PM.webgl.fps || 0;
      webglEl.textContent = webglVal;
      var webglColor = webglVal >= 55 ? '#8FAE89' : (webglVal >= 30 ? '#d7ff00' : '#D9663B');
      webglEl.style.color = webglColor;
    }
    var webglDetail = document.getElementById('perf-webgl-detail');
    if (webglDetail) {
      webglDetail.textContent = (PM.webgl.frameDuration || 0).toFixed(1) + 'ms (frame)';
    }

    // Update Long Tasks
    var ltEl = document.getElementById('perf-longtasks-value');
    if (ltEl) {
      var recentLT = PM.longTasks.filter(function(t) {
        return t.startTime > performance.now() - 60000;
      });
      ltEl.textContent = recentLT.length;
      var ltColor = recentLT.length === 0 ? '#8FAE89' : (recentLT.length < 5 ? '#d7ff00' : '#D9663B');
      ltEl.style.color = ltColor;
    }
    var ltDetail = document.getElementById('perf-longtasks-detail');
    if (ltDetail) {
      var worstLT = PM.longTasks.slice(-20).reduce(function(max, t) {
        return t.duration > max ? t.duration : max;
      }, 0);
      ltDetail.textContent = 'Worst: ' + (worstLT ? worstLT.toFixed(0) + 'ms' : 'none');
    }

    // Update Uptime
    var uptimeEl = document.getElementById('perf-uptime-value');
    if (uptimeEl) {
      var elapsed = Math.floor((Date.now() - PM.startedAt) / 1000);
      var mins = Math.floor(elapsed / 60);
      var secs = elapsed % 60;
      uptimeEl.textContent = mins + 'm ' + secs + 's';
    }

    // Update Memory
    var memEl = document.getElementById('perf-memory-value');
    if (memEl) {
      if (PM.memory.jsHeapSize) {
        memEl.textContent = formatBytes(PM.memory.jsHeapSize);
      } else {
        memEl.textContent = 'N/A';
      }
    }

    // ── Update Sparklines ──
    drawSparkline('perf-fps-sparkline', PM.fps.history, 0, 60);
    drawSparkline('perf-lenis-sparkline', PM.lenis.history.slice(-60), 0, 100);
    drawSparkline('perf-gsap-sparkline', PM.gsap.history.slice(-60), 0, 100);
    drawSparkline('perf-webgl-sparkline', PM.webgl.history.slice(-60), 0, 100);
    drawSparkline('perf-cls-sparkline', PM.cls.history, 0);

    requestAnimationFrame(function() { setTimeout(updateDOM, 200); });
  }

  function drawSparkline(canvasId, data, min, max) {
    var canvas = document.getElementById(canvasId);
    if (!canvas || !data || data.length < 2) return;
    var ctx = canvas.getContext('2d');
    var w = canvas.width, h = canvas.height;
    ctx.clearRect(0, 0, w, h);

    var mn = min != null ? min : Math.min.apply(null, data);
    var mx = max != null ? max : Math.max.apply(null, data);
    var range = mx - mn || 1;

    ctx.beginPath();
    ctx.strokeStyle = '#d7ff00';
    ctx.lineWidth = 1.5;
    var stepX = w / (data.length - 1);
    data.forEach(function(val, i) {
      var x = i * stepX;
      var y = h - ((val - mn) / range) * (h - 4) - 2;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();

    // Fill area under curve
    ctx.lineTo(w, h);
    ctx.lineTo(0, h);
    ctx.closePath();
    ctx.fillStyle = 'rgba(215,255,0,0.06)';
    ctx.fill();
  }

  function formatBytes(bytes) {
    if (!bytes) return '0 B';
    var units = ['B', 'KB', 'MB', 'GB'];
    var i = 0;
    var val = bytes;
    while (val >= 1024 && i < units.length - 1) {
      val /= 1024;
      i++;
    }
    return val.toFixed(1) + ' ' + units[i];
  }

  // ── Expose controls ──
  PM.toggle = function() {
    PM.isRunning = !PM.isRunning;
    if (PM.isRunning) {
      lastFPSTime = performance.now();
      frameCount = 0;
      requestAnimationFrame(rafLoop);
    }
    return PM.isRunning;
  };

  PM.reset = function() {
    var now = Date.now();
    PM.fps.instant = 0;
    PM.fps.avg1s = 0;
    PM.fps.history = [];
    PM.cls.value = 0;
    PM.cls.rawEntries = [];
    PM.cls.history = [];
    PM.lenis.frameDuration = 0;
    PM.lenis.avgDuration = 0;
    PM.lenis.history = [];
    PM.gsap.frameDuration = 0;
    PM.gsap.avgDuration = 0;
    PM.gsap.history = [];
    PM.webgl.frameDuration = 0;
    PM.webgl.avgDuration = 0;
    PM.webgl.fps = 0;
    PM.webgl.history = [];
    PM.longTasks = [];
    PM.startedAt = now;
    fpsHistory = [];
    lastFPSTime = performance.now();
    frameCount = 0;
    lenisFrameCount = 0;
    lenisFrameTotal = 0;
    lenisHistory = [];
    gsapFrameCount = 0;
    gsapFrameTotal = 0;
    gsapHistory = [];
    webglFrameCount = 0;
    webglFrameTotal = 0;
    webglHistory = [];
  };

  PM.exportJSON = function() {
    var snapshot = {
      timestamp: new Date().toISOString(),
      uptime: Date.now() - PM.startedAt,
      fps: { avg1s: PM.fps.avg1s, history: PM.fps.history.slice(-60) },
      cls: { total: PM.cls.value, history: PM.cls.history.slice(-60) },
      lenis: { avgDuration: PM.lenis.avgDuration, history: PM.lenis.history.slice(-60) },
      gsap: { avgDuration: PM.gsap.avgDuration, history: PM.gsap.history.slice(-60) },
      webgl: { fps: PM.webgl.fps, history: PM.webgl.history.slice(-60) },
      longTasks: PM.longTasks.slice(-20),
      memory: PM.memory,
    };
    return JSON.stringify(snapshot, null, 2);
  };

  // Store on window
  window.__mandiiqPerfMonitor = PM;

  // ── Start DOM update loop ──
  setTimeout(updateDOM, 500);

  // ── Pause monitoring when tab is hidden, resume when visible ──
  // Prevents the setInterval(sampleMemory, 5000) and rAF loops from
  // consuming resources on background tabs after navigating away.
  document.addEventListener('visibilitychange', function() {
    if (document.hidden) {
      PM.isRunning = false;
    } else {
      PM.isRunning = true;
      lastFPSTime = performance.now();
      frameCount = 0;
      requestAnimationFrame(rafLoop);
    }
  });

  // ── Keyboard shortcut: Ctrl+Shift+P to export ──
  document.addEventListener('keydown', function(e) {
    if (e.ctrlKey && e.shiftKey && e.key === 'P') {
      e.preventDefault();
      var json = PM.exportJSON();
      try {
        navigator.clipboard.writeText(json);
      } catch(e2) {
        console.log('[PerfMonitor] Export:', json);
      }
    }
  });
})();
</script>
"""


def render():
    inject_theme()

    # Inject the performance monitor JS
    st.markdown(_PERF_MONITOR_JS, unsafe_allow_html=True)

    # ── Hero ──
    st.markdown(
        f"""
        <div class="page-hero" style="margin-bottom:2rem;">
          <div>
            <div style="font-family:'IBM Plex Mono',monospace;font-size:0.75rem;color:{TURMERIC};text-transform:uppercase;letter-spacing:0.1em;margin-bottom:0.5rem;">
              Hidden Debug Route
            </div>
            <h1 style="font-family:'Space Grotesk',system-ui,sans-serif;font-weight:300;font-size:clamp(1.6rem,3vw,2.4rem);color:#ffffff;letter-spacing:0.03em;text-transform:uppercase;margin-bottom:0.5rem;">
              Performance Audit
            </h1>
            <p style="color:#7e7e7e;max-width:720px;line-height:1.7;font-size:0.9rem;">
              Live browser performance metrics. Measures <strong style="color:#bababa;">FPS</strong>,
              <strong style="color:#bababa;">Cumulative Layout Shift (CLS)</strong>,
              and animation frame timing for Lenis smooth scroll, GSAP, and Three.js WebGL.
              Data is collected client-side and persisted in <code style="color:{TURMERIC};">window.__mandiiqPerfMonitor</code>
              across Streamlit reruns. Press <kbd style="background:#333;padding:2px 6px;border-radius:3px;color:#fff;border:1px solid #555;">Ctrl+Shift+P</kbd> to export JSON.
            </p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Controls ──
    col_a, col_b = st.columns([1, 6])
    with col_a:
        st.button("🔄 Refresh", key="perf_refresh", help="Re-read metrics from window.__mandiiqPerfMonitor")

    # ── KPI row: 6 glass metric cards ──
    st.markdown(
        f"""
        <div style="font-family:'IBM Plex Mono',monospace;font-size:0.7rem;color:{TURMERIC};text-transform:uppercase;letter-spacing:0.08em;margin-bottom:0.8rem;">
          Live Metrics — auto-updates every 200ms
        </div>
        """,
        unsafe_allow_html=True,
    )

    # FPS
    st.markdown(
        f"""
        <div class="crosshair-panel glass" style="padding:1rem;margin-bottom:1rem;">
          <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:16px;">
            <div>
              <div style="font-size:0.7rem;color:{FAINT};font-family:'IBM Plex Mono',monospace;text-transform:uppercase;">FPS</div>
              <div style="font-size:2rem;font-family:'Barlow','IBM Plex Mono',monospace;font-weight:500;transition:color 0.3s;">
                <span id="perf-fps-value">—</span>
              </div>
              <div style="font-size:0.7rem;color:{MUTED};" id="perf-fps-detail">waiting…</div>
              <canvas id="perf-fps-sparkline" width="180" height="40"
                style="width:100%;height:40px;margin-top:6px;border-radius:3px;background:rgba(255,255,255,0.02);"></canvas>
            </div>
            <div>
              <div style="font-size:0.7rem;color:{FAINT};font-family:'IBM Plex Mono',monospace;text-transform:uppercase;">CLS</div>
              <div style="font-size:2rem;font-family:'Barlow','IBM Plex Mono',monospace;font-weight:500;transition:color 0.3s;">
                <span id="perf-cls-value">—</span>
              </div>
              <div style="font-size:0.7rem;color:{MUTED};" id="perf-cls-detail">waiting…</div>
              <canvas id="perf-cls-sparkline" width="180" height="40"
                style="width:100%;height:40px;margin-top:6px;border-radius:3px;background:rgba(255,255,255,0.02);"></canvas>
            </div>
            <div>
              <div style="font-size:0.7rem;color:{FAINT};font-family:'IBM Plex Mono',monospace;text-transform:uppercase;">WebGL</div>
              <div style="font-size:2rem;font-family:'Barlow','IBM Plex Mono',monospace;font-weight:500;transition:color 0.3s;">
                <span id="perf-webgl-value">—</span> <span style="font-size:0.8rem;color:{MUTED};">fps</span>
              </div>
              <div style="font-size:0.7rem;color:{MUTED};" id="perf-webgl-detail">waiting…</div>
              <canvas id="perf-webgl-sparkline" width="180" height="40"
                style="width:100%;height:40px;margin-top:6px;border-radius:3px;background:rgba(255,255,255,0.02);"></canvas>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Second row: Lenis, GSAP, Long Tasks + Memory
    st.markdown(
        f"""
        <div class="crosshair-panel glass" style="padding:1rem;margin-bottom:1.2rem;">
          <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:16px;">
            <div>
              <div style="font-size:0.7rem;color:{FAINT};font-family:'IBM Plex Mono',monospace;text-transform:uppercase;">Lenis Scroll</div>
              <div style="font-size:1.4rem;font-family:'Barlow','IBM Plex Mono',monospace;font-weight:500;transition:color 0.3s;">
                <span id="perf-lenis-value">—</span>
              </div>
              <div style="font-size:0.7rem;color:{MUTED};" id="perf-lenis-detail">waiting…</div>
              <canvas id="perf-lenis-sparkline" width="180" height="30"
                style="width:100%;height:30px;margin-top:4px;border-radius:3px;background:rgba(255,255,255,0.02);"></canvas>
            </div>
            <div>
              <div style="font-size:0.7rem;color:{FAINT};font-family:'IBM Plex Mono',monospace;text-transform:uppercase;">GSAP Ticker</div>
              <div style="font-size:1.4rem;font-family:'Barlow','IBM Plex Mono',monospace;font-weight:500;transition:color 0.3s;">
                <span id="perf-gsap-value">—</span>
              </div>
              <div style="font-size:0.7rem;color:{MUTED};" id="perf-gsap-detail">waiting…</div>
              <canvas id="perf-gsap-sparkline" width="180" height="30"
                style="width:100%;height:30px;margin-top:4px;border-radius:3px;background:rgba(255,255,255,0.02);"></canvas>
            </div>
            <div>
              <div style="font-size:0.7rem;color:{FAINT};font-family:'IBM Plex Mono',monospace;text-transform:uppercase;">Long Tasks / min</div>
              <div style="font-size:1.4rem;font-family:'Barlow','IBM Plex Mono',monospace;font-weight:500;transition:color 0.3s;">
                <span id="perf-longtasks-value">—</span>
              </div>
              <div style="font-size:0.7rem;color:{MUTED};" id="perf-longtasks-detail">waiting…</div>
            </div>
            <div>
              <div style="font-size:0.7rem;color:{FAINT};font-family:'IBM Plex Mono',monospace;text-transform:uppercase;">JS Heap</div>
              <div style="font-size:1.4rem;font-family:'Barlow','IBM Plex Mono',monospace;font-weight:500;color:{MUTED};">
                <span id="perf-memory-value">—</span>
              </div>
              <div style="font-size:0.7rem;color:{MUTED};" id="perf-uptime-value">—</div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Summary interpretation ──
    st.markdown(
        f"""
        <div class="interpretation-box" style="margin-bottom:1.5rem;">
          <strong>Interpreting the metrics:</strong><br/>
          <span style="font-size:0.85rem;">
            • <strong style="color:{SAGE};">Green</strong> = healthy — no action needed.<br/>
            • <strong style="color:{TURMERIC};">Lime</strong> = degraded — investigate if persistent.<br/>
            • <strong style="color:{RUST};">Rust</strong> = poor — likely visible jank or layout shift.<br/>
            • <strong>CLS</strong> should stay below <strong style="color:#ffffff;">0.1</strong> (Google's "good" threshold).<br/>
            • <strong>Lenis</strong> frame durations above 50ms mean the smooth scroll is dropping frames.<br/>
            • <strong>GSAP</strong> tick timing above 50ms means GSAP animations are competing with other work.<br/>
            • <strong>Long tasks</strong> (>50ms) block the main thread — more than 5/min suggests excessive JS work.
          </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Detailed table ──
    st.markdown(
        f"""
        <div style="font-family:'IBM Plex Mono',monospace;font-size:0.7rem;color:{TURMERIC};text-transform:uppercase;letter-spacing:0.08em;margin-bottom:0.5rem;">
          Engine Status
        </div>
        """,
        unsafe_allow_html=True,
    )

    engine_statuses = [
        ("Lenis Smooth Scroll", "window.__mandiiqLenis", "Active" if st.session_state.get("_mandiiq_lenis_injected") else "Not loaded"),
        ("GSAP + SplitText", "typeof gsap !== 'undefined'", "Active" if st.session_state.get("_mandiiq_splittext_injected") else "Not loaded"),
        ("Three.js WebGL", "#mandiq-webgl-hero-root", "Bundle injected" if st.session_state.get("_mandiiq_animations_injected") else "Not injected"),
        ("Sound System", "window.__mandiiqSoundInited", "Active" if st.session_state.get("_mandiiq_sound_injected") else "Not loaded"),
        ("ScrollTrigger Factory", "window.__mandiiqScrollFactory", "Active" if st.session_state.get("_mandiiq_scrolltrigger_injected") else "Not loaded"),
    ]

    rows = ""
    for name, check, status in engine_statuses:
        dot = '<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:{color};margin-right:6px;"></span>'.format(
            color=SAGE if "Active" in status else MUTED
        )
        rows += (
            f'<tr><td style="padding:0.4rem 0.6rem;color:#ffffff;font-size:0.85rem;">{name}</td>'
            f'<td style="padding:0.4rem 0.6rem;color:{MUTED};font-family:\'IBM Plex Mono\',monospace;font-size:0.75rem;"><code>{check}</code></td>'
            f'<td style="padding:0.4rem 0.6rem;">{dot} {status}</td></tr>'
        )

    st.markdown(
        f"""
        <div class="glass" style="padding:0.5rem 1rem;margin-bottom:2rem;">
          <table style="width:100%;border-collapse:collapse;">
            <thead>
              <tr style="border-bottom:1px solid {SLATE};">
                <th style="padding:0.4rem 0.6rem;color:{FAINT};font-size:0.7rem;text-transform:uppercase;text-align:left;">Engine</th>
                <th style="padding:0.4rem 0.6rem;color:{FAINT};font-size:0.7rem;text-transform:uppercase;text-align:left;">Detection</th>
                <th style="padding:0.4rem 0.6rem;color:{FAINT};font-size:0.7rem;text-transform:uppercase;text-align:left;">Status</th>
              </tr>
            </thead>
            <tbody>
              {rows}
            </tbody>
          </table>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Footer ──
    st.markdown(
        f"""
        <div style="font-size:0.75rem;color:#7e7e7e;text-align:center;padding-top:1rem;border-top:1px solid rgba(255,255,255,0.06);">
          <span class="mono">Hidden debug route</span> —
          <span style="font-family:'IBM Plex Mono',monospace;">/performance</span> —
          Not indexed. Metrics reset on page reload.
        </div>
        """,
        unsafe_allow_html=True,
    )
