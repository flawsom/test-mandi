/* ═══════════════════════════════════════════════════════════
   SURFACE HEALTH BADGES — shared renderer
   (published by the Multi-Surface Health Check workflow)

   Loaded by BOTH landing/index.html and docs/index.html so the
   live verdicts + history sparklines render on every Pages
   surface without duplicating JS.  The status JSON path is read
   from the container element's data-status-json attribute, which
   each page sets relative to itself (e.g. "docs/health-status.json"
   from the landing root, "health-status.json" from docs/).
   ═══════════════════════════════════════════════════════════ */
(function() {
  var box = document.getElementById('surface-status');
  var grid = document.getElementById('surface-status-grid');
  var tsEl = document.getElementById('surface-status-ts');
  if (!box || !grid) return;

  // Per-page JSON path — set via data-status-json on the container.
  var STATUS_JSON = box.getAttribute('data-status-json') || 'health-status.json';

  var VERDICT_META = {
    LATEST:      { cls: 'latest', label: 'LATEST' },
    STALE:       { cls: 'stale',  label: 'STALE' },
    BROKEN:      { cls: 'broken', label: 'BROKEN' },
    DOWN:        { cls: 'down',   label: 'DOWN' },
    'UP (auth)':   { cls: 'up',  label: 'AUTH' },
    'UP (static)': { cls: 'up',  label: 'STATIC' },
  };

  function fmtAgo(iso) {
    if (!iso) return 'unknown';
    var diff = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
    if (diff < 60) return 'just now';
    if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
    return Math.floor(diff / 3600) + 'h ago';
  }

  function render(data) {
    // Sort: LATEST first, then DOWN/BROKEN, then the rest.
    var order = { LATEST: 0, DOWN: 1, BROKEN: 2, STALE: 3 };
    var names = Object.keys(data.surfaces || {});
    names.sort(function(a, b) {
      var va = data.surfaces[a].verdict, vb = data.surfaces[b].verdict;
      return (order[va] !== undefined ? order[va] : 9) - (order[vb] !== undefined ? order[vb] : 9);
    });

    grid.innerHTML = '';
    var hist = data.history || [];
    var INCIDENTS = { STALE: 1, DOWN: 1, BROKEN: 1 };
    names.forEach(function(name) {
      var s = data.surfaces[name];
      var meta = VERDICT_META[s.verdict] || { cls: 'up', label: s.verdict };
      var chip = document.createElement('div');
      chip.className = 'surface-chip';
      var nStr = (s.n_prices != null) ? ' · ' + Number(s.n_prices).toLocaleString() : '';

      // Sparkline: one segment per history entry, colored by that surface's verdict.
      var spark = '';
      var incidents = 0, lastIncident = null;
      if (hist.length) {
        for (var i = 0; i < hist.length; i++) {
          var v = (hist[i].verdicts || {})[name] || null;
          var cls = v === 'LATEST' ? 'l' : (v === 'STALE' ? 's' : (v === 'DOWN' || v === 'BROKEN' ? 'd' : (v ? 'u' : '')));
          spark += '<i class="' + cls + '" title="' + (hist[i].generated_at || '') + ' — ' + (v || 'n/a') + '"></i>';
          if (INCIDENTS[v]) { incidents++; lastIncident = hist[i].generated_at || lastIncident; }
        }
      }
      var metaTxt = hist.length
        ? (incidents ? incidents + ' incident' + (incidents !== 1 ? 's' : '') + (lastIncident ? ' · last ' + fmtAgo(lastIncident) : '') : 'stable · no incidents')
        : 'history not published yet';

      chip.innerHTML =
        '<div class="surface-chip-top">' +
          '<span class="dot ' + meta.cls + '"></span>' +
          '<span class="sname">' + name.replace(/ /g, '\u00A0') + '</span>' +
          '<span class="sverdict ' + meta.cls + '">' + meta.label + '</span>' +
          '<span class="sn">' + nStr + '</span>' +
        '</div>' +
        '<div class="surface-spark">' + (spark || '<span class="spark-empty">—</span>') + '</div>' +
        '<div class="surface-meta">' + metaTxt + '</div>';
      chip.title = s.note || s.verdict;
      grid.appendChild(chip);
    });

    tsEl.textContent = 'Checked ' + fmtAgo(data.generated_at) + (data.latest_db_reference ? ' · ref ' + Number(data.latest_db_reference).toLocaleString() + ' rows' : '');
    box.classList.add('visible');
    box.classList.remove('empty');
  }

  function onFail() {
    // status.json not published yet (first deploy) or offline — show the
    // muted empty state so the section is visibly present, not hidden.
    box.classList.add('empty', 'visible');
    tsEl.textContent = 'status not published yet';
  }

  function refresh() {
    fetch(STATUS_JSON + '?t=' + Date.now(), { cache: 'no-store' })
      .then(function(r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(render)
      .catch(onFail);
  }

  refresh();
  setInterval(refresh, 60000); // re-check every 60s alongside the KPIs
})();
