/**
 * MandiIQ Canvas Effects — Combined Vanilla JS
 * FlowingDots: noise-based flow field + mouse-proximity particles
 * CursorTrail: spring physics cursor trail with color cycling
 * Both are self-contained, responsive, and mouse-interactive.
 */
(function() {
  'use strict';

  function boot() {

  /* ═══════════════════════════════════════════════════════════
     Cursor Trail — Spring Physics
     ═══════════════════════════════════════════════════════════ */
  (function initCursor() {
    if (window.matchMedia('(pointer: coarse)').matches && !window.matchMedia('(pointer: fine)').matches) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

    var E = { friction: 0.5, trails: 20, size: 50, dampening: 0.25, tension: 0.98 };
    var canvas = document.createElement('canvas');
    canvas.id = 'mandiq-cursor-canvas';
    canvas.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;pointer-events:none;z-index:99999;';
    document.body.appendChild(canvas);

    var ctx = canvas.getContext('2d');
    ctx.running = true;
    ctx.frame = 1;
    var pos = { x: window.innerWidth / 2, y: window.innerHeight / 2 };
    var lines = [];

    function Osc(e) { this.phase = e.phase || 0; this.offset = e.offset || 0; this.frequency = e.frequency || 0.001; this.amplitude = e.amplitude || 1; }
    Osc.prototype.update = function() { this.phase += this.frequency; return this.offset + Math.sin(this.phase) * this.amplitude; };
    var osc = new Osc({ phase: Math.random() * 2 * Math.PI, amplitude: 85, frequency: 0.0015, offset: 285 });

    function Node() { this.x = 0; this.y = 0; this.vx = 0; this.vy = 0; }

    function Line(spring) {
      this.spring = spring + 0.1 * Math.random() - 0.02;
      this.friction = E.friction + 0.01 * Math.random() - 0.002;
      this.nodes = [];
      for (var i = 0; i < E.size; i++) {
        var n = new Node();
        n.x = pos.x; n.y = pos.y;
        this.nodes.push(n);
      }
    }
    Line.prototype.update = function() {
      var s = this.spring, p = this.nodes[0];
      p.vx += (pos.x - p.x) * s; p.vy += (pos.y - p.y) * s;
      for (var i = 0; i < this.nodes.length; i++) {
        var n = this.nodes[i];
        if (i > 0) {
          var q = this.nodes[i - 1];
          n.vx += (q.x - n.x) * s; n.vy += (q.y - n.y) * s;
          n.vx += q.vx * E.dampening; n.vy += q.vy * E.dampening;
        }
        n.vx *= this.friction; n.vy *= this.friction;
        n.x += n.vx; n.y += n.vy;
        s *= E.tension;
      }
    };
    Line.prototype.draw = function() {
      ctx.beginPath();
      var n0 = this.nodes[0]; ctx.moveTo(n0.x, n0.y);
      for (var i = 1; i < this.nodes.length - 2; i++) {
        var e = this.nodes[i], t = this.nodes[i + 1];
        ctx.quadraticCurveTo(e.x, e.y, (e.x + t.x) / 2, (e.y + t.y) / 2);
      }
      var l = this.nodes[this.nodes.length - 2], e = this.nodes[this.nodes.length - 1];
      ctx.quadraticCurveTo(l.x, l.y, e.x, e.y);
      ctx.stroke(); ctx.closePath();
    };

    function render() {
      if (!ctx.running) return;
      ctx.globalCompositeOperation = 'source-over';
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.globalCompositeOperation = 'lighter';
      var hue = Math.round(osc.update());
      ctx.strokeStyle = 'hsla(' + hue + ',50%,50%,0.2)';
      ctx.lineWidth = 1;
      for (var i = 0; i < lines.length; i++) { lines[i].update(); lines[i].draw(); }
      ctx.frame++;
      requestAnimationFrame(render);
    }

    function resize() { canvas.width = window.innerWidth; canvas.height = window.innerHeight; }

    function createLines() {
      lines = [];
      for (var i = 0; i < E.trails; i++) lines.push(new Line(0.4 + (i / E.trails) * 0.025));
    }

    document.addEventListener('mousemove', function(e) { pos.x = e.clientX; pos.y = e.clientY; }, { passive: true });
    document.addEventListener('touchmove', function(e) { if (e.touches.length > 0) { pos.x = e.touches[0].pageX; pos.y = e.touches[0].pageY; } }, { passive: true });
    document.addEventListener('touchstart', function(e) { if (e.touches.length > 0) { pos.x = e.touches[0].pageX; pos.y = e.touches[0].pageY; } }, { passive: true });

    resize();
    createLines();
    render();

    window.addEventListener('resize', resize);
    window.addEventListener('orientationchange', resize);
    document.addEventListener('visibilitychange', function() {
      if (document.hidden) ctx.running = false; else { ctx.running = true; render(); }
    });
  })();

  /* ═══════════════════════════════════════════════════════════
     Flowing Dots — Noise-Based Flow Field
     ═══════════════════════════════════════════════════════════ */
  (function initFlowing() {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

    var backgroundColor = getComputedStyle(document.documentElement).getPropertyValue('--bg-base').trim() || '#000000';
    var particleColor = '215, 255, 0'; // lime
    var lineColor = '215, 255, 0';
    var animationSpeed = 0.005;

    var canvas = document.createElement('canvas');
    canvas.id = 'mandiq-flowing-canvas';
    canvas.style.cssText = 'position:fixed;top:0;left:0;width:100vw;height:100vh;pointer-events:none;z-index:1;';
    document.body.insertBefore(canvas, document.body.firstChild);

    var ctx = canvas.getContext('2d');
    var flowPoints = [];
    var mouse = { x: -1000, y: -1000 };
    var time = 0;
    var animId = null;

    function noise(x, y, t) {
      var s1 = Math.sin(x * 0.01 + t);
      var s2 = Math.sin(y * 0.01 + t * 0.8);
      var s3 = Math.sin((x + y) * 0.005 + t * 1.2);
      return (s1 + s2 + s3) / 3;
    }

    function resize() {
      var dpr = window.devicePixelRatio || 1;
      var w = window.innerWidth;
      var h = window.innerHeight;
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      canvas.style.width = w + 'px';
      canvas.style.height = h + 'px';
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.scale(dpr, dpr);

      var gridSize = 14;
      flowPoints = [];
      for (var x = gridSize / 2; x < w; x += gridSize) {
        for (var y = gridSize / 2; y < h; y += gridSize) {
          flowPoints.push({
            x: x, y: y, vx: 0, vy: 0,
            angle: Math.random() * Math.PI * 2,
            phase: Math.random() * Math.PI * 2,
            noiseOffset: Math.random() * 1000,
            originalX: x, originalY: y,
          });
        }
      }
    }

    function animate() {
      if (!ctx) return;
      time += animationSpeed;

      ctx.fillStyle = backgroundColor;
      ctx.fillRect(0, 0, canvas.width / (window.devicePixelRatio || 1), canvas.height / (window.devicePixelRatio || 1));

      for (var i = 0; i < flowPoints.length; i++) {
        var p = flowPoints[i];
        var nv = noise(p.x, p.y, time);
        var angle = nv * Math.PI * 4;

        // Mouse proximity push
        var dx = mouse.x - p.x;
        var dy = mouse.y - p.y;
        var dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 150) {
          var push = (1 - dist / 150) * 0.5;
          if (dist > 0.01) { p.vx += (dx / dist) * push; p.vy += (dy / dist) * push; }
        }

        // Flow field
        p.vx += Math.cos(angle) * 0.1;
        p.vy += Math.sin(angle) * 0.1;

        // Damping
        p.vx *= 0.95;
        p.vy *= 0.95;

        var nextX = p.x + p.vx;
        var nextY = p.y + p.vy;

        // Draw dot
        var speed = Math.sqrt(p.vx * p.vx + p.vy * p.vy);
        var alpha = Math.min(0.7, speed * 6 + 0.2);
        var sz = 2 + speed * 2;

        ctx.beginPath();
        ctx.arc(p.x, p.y, Math.min(sz, 3.5), 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(' + particleColor + ', ' + alpha + ')';
        ctx.fill();

        // Update position
        p.x = nextX;
        p.y = nextY;

        // Wrap around screen edges
        var w = window.innerWidth;
        var h = window.innerHeight;
        if (nextX < -10) p.x = w + 10;
        if (nextX > w + 10) p.x = -10;
        if (nextY < -10) p.y = h + 10;
        if (nextY > h + 10) p.y = -10;

        // Return to original position
        p.vx += (p.originalX - p.x) * 0.01;
        p.vy += (p.originalY - p.y) * 0.01;
      }

      animId = requestAnimationFrame(animate);
    }

    function onMouse(e) {
      mouse.x = e.clientX;
      mouse.y = e.clientY;
    }

    resize();
    animate();

    document.addEventListener('mousemove', onMouse, { passive: true });
    window.addEventListener('resize', resize);
    window.addEventListener('orientationchange', function() { setTimeout(resize, 200); });

    // Pause when tab hidden
    document.addEventListener('visibilitychange', function() {
      if (document.hidden && animId) { cancelAnimationFrame(animId); animId = null; }
      else if (!document.hidden && !animId) animate();
    });

    // Expose for cleanup
    window.__mandiqFlowingCleanup = function() {
      if (animId) cancelAnimationFrame(animId);
      document.removeEventListener('mousemove', onMouse);
      window.removeEventListener('resize', resize);
      if (canvas.parentNode) canvas.parentNode.removeChild(canvas);
    };
  })();

  } // end boot

  // The script may be loaded from <head> (landing) where <body> does not
  // exist yet — both effects append canvases to document.body, so defer
  // until the DOM is ready.
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
