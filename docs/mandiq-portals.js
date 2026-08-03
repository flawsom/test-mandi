/* ═══════════════════════════════════════════════════════════════
   MANDIIQ CREATIVE NAVIGATION — particle portal buttons
   https://flawsom.github.io/test-mandi/

   Each .mandiq-portal is a real <a> (progressive enhancement: works
   with no JS). With JS, a <canvas> paints a living particle field:
     • pipeline  → blue data-flow streaming left→right
     • report    → gold clusters on both sides of the -20% cutoff
     • dashboard → green heartbeat pulse from the centre
     • docs      → purple lattice that dissolves on hover
   Hover wakes particles toward the cursor; click blooms a burst then
   navigates. Touch taps bloom+navigate too. prefers-reduced-motion
   renders a single static frame instead of animating.
   ═══════════════════════════════════════════════════════════════ */
(function () {
  'use strict';

  if (typeof window === 'undefined' || !window.requestAnimationFrame) return;

  var reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var DPR = Math.min(window.devicePixelRatio || 1, 2);

  var THEME = {
    pipeline:  { a: '#3ec6ff', b: '#1565c0' },
    report:    { a: '#ffc857', b: '#d97706' },
    dashboard: { a: '#4ade80', b: '#15803d' },
    docs:      { a: '#c084fc', b: '#7e22ce' },
    default:   { a: '#94a3b8', b: '#475569' },
  };

  /* ── Heartbeat envelope: sharp double-thump, then quiet ── */
  function heartbeat(t) {
    var period = 1400; // ms
    var ph = (t % period) / period; // 0..1
    var beat1 = Math.exp(-Math.pow((ph - 0.10) / 0.045, 2));
    var beat2 = Math.exp(-Math.pow((ph - 0.22) / 0.050, 2));
    return Math.max(beat1, beat2);
  }

  function Portal(el) {
    this.el = el;
    this.type = el.getAttribute('data-type') || 'default';
    this.canvas = el.querySelector('.mandiq-portal__canvas');
    if (!this.canvas) return;
    this.ctx = this.canvas.getContext('2d');
    this.colors = THEME[this.type] || THEME.default;
    this.count = 64;
    this.particles = [];
    this.mouse = null;
    this.blooming = false;
    this.running = false;
    this.rect = { w: 0, h: 0 };
    this._raf = null;

    this.resize();
    this.seed();

    if (reduceMotion) {
      this.drawStatic();
      /* keep the static frame crisp across resizes */
      var self = this;
      this._rmResize = function () { self.resize(); self.seed(); self.drawStatic(); };
      window.addEventListener('resize', this._rmResize);
      return;
    }

    this.bind();
    this.observe();
    this.loop(performance.now());
  }

  Portal.prototype.resize = function () {
    var r = this.el.getBoundingClientRect();
    this.rect.w = Math.max(1, r.width);
    this.rect.h = Math.max(1, r.height);
    this.canvas.width = Math.round(this.rect.w * DPR);
    this.canvas.height = Math.round(this.rect.h * DPR);
    if (this.ctx) this.ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
  };

  Portal.prototype.seed = function () {
    var w = this.rect.w, h = this.rect.h;
    var i, p;
    this.particles = [];
    for (i = 0; i < this.count; i++) {
      p = { x: 0, y: 0, vx: 0, vy: 0, size: 0, alpha: 0, phase: 0, speed: 0, baseY: 0, anchorX: 0, anchorY: 0, angle: 0, baseR: 0, cluster: '', gx: 0, gy: 0 };
      switch (this.type) {
        case 'pipeline':
          p.x = Math.random() * w;
          p.baseY = Math.random() * h;
          p.y = p.baseY;
          p.speed = 0.35 + Math.random() * 1.1;
          p.phase = Math.random() * Math.PI * 2;
          p.size = 0.8 + Math.random() * 1.6;
          break;
        case 'report':
          p.cluster = Math.random() > 0.5 ? 'left' : 'right';
          this._setReportAnchor(p);
          p.x = p.anchorX + (Math.random() - 0.5) * w * 0.22;
          p.y = Math.random() * h;
          p.size = 1 + Math.random() * 1.8;
          break;
        case 'dashboard':
          p.angle = Math.random() * Math.PI * 2;
          p.baseR = (0.22 + Math.random() * 0.55) * Math.min(w, h) / 2;
          p.phase = Math.random() * Math.PI * 2;
          p.x = w / 2 + Math.cos(p.angle) * p.baseR;
          p.y = h / 2 + Math.sin(p.angle) * p.baseR;
          p.size = 1 + Math.random() * 1.8;
          break;
        case 'docs':
          this._setDocAnchor(p);
          p.x = p.anchorX + (Math.random() - 0.5) * 14;
          p.y = p.anchorY + (Math.random() - 0.5) * 14;
          p.size = 0.9 + Math.random() * 1.4;
          break;
        default:
          p.x = Math.random() * w;
          p.y = Math.random() * h;
          p.size = 1 + Math.random() * 1.5;
      }
      p.alpha = 0.25 + Math.random() * 0.45;
      this.particles.push(p);
    }
  };

  Portal.prototype._setReportAnchor = function (p) {
    var w = this.rect.w;
    p.anchorX = p.cluster === 'left' ? w * 0.30 : w * 0.70;
    p.anchorY = this.rect.h * (0.2 + Math.random() * 0.6);
  };

  Portal.prototype._setDocAnchor = function (p) {
    var w = this.rect.w, h = this.rect.h;
    var gap = 30;
    var cols = Math.max(2, Math.floor(w / gap));
    var rows = Math.max(2, Math.floor(h / gap));
    p.gx = Math.floor(Math.random() * cols);
    p.gy = Math.floor(Math.random() * rows);
    p.anchorX = (p.gx + 0.5) * (w / cols);
    p.anchorY = (p.gy + 0.5) * (h / rows);
  };

  Portal.prototype.bind = function () {
    var self = this;
    this._move = function (e) {
      var r = self.el.getBoundingClientRect();
      self.mouse = { x: e.clientX - r.left, y: e.clientY - r.top };
      self.el.classList.add('is-hover');
    };
    this._leave = function () {
      self.mouse = null;
      self.el.classList.remove('is-hover');
    };
    this._click = function (e) {
      if (e.defaultPrevented) return;
      if (e.button !== 0) return; // primary button only (keyboard Enter fires click with button=0)
      if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return; // let browser handle
      var href = self.el.getAttribute('href');
      if (!href) return;
      e.preventDefault();
      self.bloom();
      setTimeout(function () {
        self.el.setAttribute('aria-busy', 'false');
        window.location.href = href;
      }, 320);
    };
    this.el.addEventListener('pointermove', this._move, { passive: true });
    this.el.addEventListener('pointerleave', this._leave, { passive: true });
    this.el.addEventListener('click', this._click);
    this._ro = new ResizeObserver(function () {
      self.resize();
      self.seed();
      if (reduceMotion) self.drawStatic();
    });
    this._ro.observe(this.el);
  };

  Portal.prototype.observe = function () {
    var self = this;
    this._io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) { self.start(); } else { self.stop(); }
      });
    }, { rootMargin: '80px' });
    this._io.observe(this.el);
  };

  Portal.prototype.start = function () {
    if (this.running || reduceMotion) return;
    this.running = true;
    this.loop(performance.now());
  };

  Portal.prototype.stop = function () {
    this.running = false;
    if (this._raf) { cancelAnimationFrame(this._raf); this._raf = null; }
  };

  Portal.prototype.loop = function (t) {
    if (!this.running) return;
    this.update(t);
    this.draw(t);
    this._raf = requestAnimationFrame(this.loop.bind(this));
  };

  Portal.prototype.update = function (t) {
    var w = this.rect.w, h = this.rect.h;
    var cx = w / 2, cy = h / 2;
    var m = this.mouse;
    var i, p, dx, dy, d;
    var beat = this.type === 'dashboard' ? heartbeat(t) : 0;

    for (i = 0; i < this.particles.length; i++) {
      p = this.particles[i];

      /* Bloom burst overrides every motion model so ALL types visibly explode */
      if (this.blooming) {
        p.x += p.vx;
        p.y += p.vy;
        p.vx *= 0.96;
        p.vy *= 0.96;
        continue;
      }

      switch (this.type) {
        case 'pipeline':
          p.x += p.speed;
          p.y = p.baseY + Math.sin(t * 0.0016 + p.phase) * 5;
          if (p.x > w + 4) { p.x = -4; p.baseY = Math.random() * h; }
          break;

        case 'report':
          /* anchors are fixed at seed time — only reference them here,
             re-seeding each frame would make the clusters jitter */
          dx = p.anchorX - p.x; dy = p.anchorY - p.y;
          p.vx += dx * 0.012; p.vy += dy * 0.012;
          p.vx *= 0.90; p.vy *= 0.90;
          p.x += p.vx; p.y += p.vy;
          break;

        case 'dashboard': {
          p.angle += 0.0022 + (p.phase * 0.0004);
          var r = p.baseR * (1 + beat * 0.30);
          p.x = cx + Math.cos(p.angle) * r;
          p.y = cy + Math.sin(p.angle) * r;
          p.alpha = Math.min(1, p.alpha + beat * 0.35);
          break;
        }

        case 'docs':
          dx = p.anchorX - p.x; dy = p.anchorY - p.y;
          p.vx += dx * 0.014 + Math.sin(t * 0.001 + p.phase) * 0.02;
          p.vy += dy * 0.014 + Math.cos(t * 0.0012 + p.phase) * 0.02;
          p.vx *= 0.86; p.vy *= 0.86;
          p.x += p.vx; p.y += p.vy;
          break;

        default:
          p.x += p.vx; p.y += p.vy;
          p.vx *= 0.96; p.vy *= 0.96;
      }

      /* Cursor wake — particles lean toward the pointer */
      if (m) {
        dx = m.x - p.x; dy = m.y - p.y;
        d = Math.sqrt(dx * dx + dy * dy);
        if (d < 90) {
          var f = ((90 - d) / 90) * 1.4;
          p.vx += (dx / (d || 1)) * f * 0.6;
          p.vy += (dy / (d || 1)) * f * 0.6;
          p.alpha = Math.min(1, p.alpha + 0.06);
        } else {
          p.alpha = Math.max(0.25, p.alpha - 0.008);
        }
      }

      if (this.type !== 'pipeline') {
        if (p.x < -8) p.x = w + 8; if (p.x > w + 8) p.x = -8;
        if (p.y < -8) p.y = h + 8; if (p.y > h + 8) p.y = -8;
      }
    }
  };

  Portal.prototype.draw = function (t) {
    var ctx = this.ctx, w = this.rect.w, h = this.rect.h;
    ctx.clearRect(0, 0, w, h);
    var i, p;

    /* Type decorations */
    if (this.type === 'report') {
      ctx.save();
      ctx.strokeStyle = this.colors.a;
      ctx.globalAlpha = 0.16;
      ctx.setLineDash([3, 5]);
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(w / 2, 10);
      ctx.lineTo(w / 2, h - 10);
      ctx.stroke();
      ctx.restore();
    } else if (this.type === 'docs') {
      ctx.save();
      ctx.strokeStyle = this.colors.b;
      ctx.globalAlpha = 0.10;
      ctx.lineWidth = 1;
      ctx.beginPath();
      for (var gx = 30; gx < w; gx += 30) { ctx.moveTo(gx, 0); ctx.lineTo(gx, h); }
      for (var gy = 30; gy < h; gy += 30) { ctx.moveTo(0, gy); ctx.lineTo(w, gy); }
      ctx.stroke();
      ctx.restore();
    } else if (this.type === 'dashboard') {
      var beat = heartbeat(t);
      if (beat > 0.05) {
        ctx.save();
        ctx.strokeStyle = this.colors.a;
        ctx.globalAlpha = beat * 0.28;
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.arc(w / 2, h / 2, 12 + beat * Math.min(w, h) * 0.4, 0, Math.PI * 2);
        ctx.stroke();
        ctx.restore();
      }
    }

    for (i = 0; i < this.particles.length; i++) {
      p = this.particles[i];
      var v = Math.sqrt(p.vx * p.vx + p.vy * p.vy);

      /* motion tail */
      if (v > 0.4 && this.type !== 'pipeline') {
        ctx.save();
        ctx.strokeStyle = this.colors.a;
        ctx.globalAlpha = p.alpha * 0.35;
        ctx.lineWidth = p.size * 0.6;
        ctx.lineCap = 'round';
        ctx.beginPath();
        ctx.moveTo(p.x - p.vx * 2.2, p.y - p.vy * 2.2);
        ctx.lineTo(p.x, p.y);
        ctx.stroke();
        ctx.restore();
      } else if (this.type === 'pipeline') {
        ctx.save();
        ctx.strokeStyle = this.colors.a;
        ctx.globalAlpha = p.alpha * 0.45;
        ctx.lineWidth = p.size * 0.55;
        ctx.lineCap = 'round';
        ctx.beginPath();
        ctx.moveTo(p.x - p.speed * 4, p.y);
        ctx.lineTo(p.x, p.y);
        ctx.stroke();
        ctx.restore();
      }

      /* halo */
      ctx.save();
      ctx.fillStyle = this.colors.b;
      ctx.globalAlpha = p.alpha * 0.28;
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.size * 2.4, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();

      /* core */
      ctx.save();
      ctx.fillStyle = this.colors.a;
      ctx.globalAlpha = p.alpha;
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
    }
  };

  /* Static frame for prefers-reduced-motion + no-JS fallback canvas */
  Portal.prototype.drawStatic = function () {
    this.update(0);
    this.draw(0);
  };

  Portal.prototype.bloom = function () {
    if (this.blooming) return;
    this.blooming = true;
    this.el.classList.add('is-blooming');
    this.el.setAttribute('aria-busy', 'true');
    var w = this.rect.w, h = this.rect.h;
    var cx = w / 2, cy = h / 2;
    var self = this;
    this.particles.forEach(function (p) {
      var dx = p.x - cx, dy = p.y - cy;
      var d = Math.sqrt(dx * dx + dy * dy) || 1;
      p.vx = (dx / d) * (6 + Math.random() * 8);
      p.vy = (dy / d) * (6 + Math.random() * 8);
      p.alpha = 1;
    });
    /* spark burst on top */
    for (var i = 0; i < 26; i++) {
      (function (k) {
        setTimeout(function () {
          if (!self.ctx) return;
          var a = Math.random() * Math.PI * 2;
          var sp = 3 + Math.random() * 7;
          self.ctx.save();
          self.ctx.fillStyle = self.colors.a;
          self.ctx.globalAlpha = 0.9;
          self.ctx.beginPath();
          self.ctx.arc(cx + Math.cos(a) * sp * 8, cy + Math.sin(a) * sp * 8, 1.6, 0, Math.PI * 2);
          self.ctx.fill();
          self.ctx.restore();
        }, k * 12);
      })(i);
    }
  };

  function init() {
    document.querySelectorAll('.mandiq-portal').forEach(function (el) {
      new Portal(el);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
