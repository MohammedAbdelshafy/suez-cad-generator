/* =========================================================================
   Animated backdrop: a procedural Suez-port survey scene (#port-bg) with a
   reactive bioluminescent point-field floating above it (#scene).
   Pure canvas, no assets required. Exposes window.Scene.pulse(level).
   ========================================================================= */
(() => {
  const bg = document.getElementById('port-bg');
  const fg = document.getElementById('scene');
  const bx = bg.getContext('2d');
  const ox = fg.getContext('2d');

  let W, H, DPR;
  function resize() {
    DPR = Math.min(window.devicePixelRatio || 1, 2);
    W = window.innerWidth; H = window.innerHeight;
    for (const c of [bg, fg]) {
      c.width = W * DPR; c.height = H * DPR;
      c.style.width = W + 'px'; c.style.height = H + 'px';
    }
    bx.setTransform(DPR, 0, 0, DPR, 0, 0);
    ox.setTransform(DPR, 0, 0, DPR, 0, 0);
    buildPort();
  }

  /* ---------- holographic CAD survey overlay (over the real aerial) ----
     A translucent layer: drifting survey grid, rotating radar sweep, and
     pulsing measurement markers. Stays transparent so the photo shows. */
  let markers = [];
  function buildPort() {
    markers = [];
    const n = Math.max(5, Math.floor((W * H) / 240000));
    for (let i = 0; i < n; i++) {
      markers.push({
        x: 0.08 + Math.random() * 0.84,   // normalised
        y: 0.12 + Math.random() * 0.76,
        ph: Math.random() * 6.28,
        sp: 0.6 + Math.random() * 1.2,
      });
    }
  }

  function drawPort(t) {
    bx.clearRect(0, 0, W, H);

    // --- drifting survey grid ---
    const gap = 64;
    const off = (t * 0.012) % gap;
    bx.lineWidth = 1;
    bx.strokeStyle = 'rgba(25,240,200,0.07)';
    bx.beginPath();
    for (let x = -gap + off; x < W + gap; x += gap) { bx.moveTo(x, 0); bx.lineTo(x, H); }
    for (let y = -gap + off; y < H + gap; y += gap) { bx.moveTo(0, y); bx.lineTo(W, y); }
    bx.stroke();

    // --- radar sweep from the port centre ---
    const cx = W * 0.5, cy = H * 0.5, R = Math.hypot(W, H) * 0.6;
    const ang = (t * 0.0006) % (Math.PI * 2);
    const sweep = bx.createConicGradient ? bx.createConicGradient(ang, cx, cy) : null;
    if (sweep) {
      sweep.addColorStop(0, 'rgba(25,240,200,0.16)');
      sweep.addColorStop(0.06, 'rgba(25,240,200,0.0)');
      sweep.addColorStop(1, 'rgba(25,240,200,0.0)');
      bx.fillStyle = sweep;
      bx.beginPath(); bx.moveTo(cx, cy); bx.arc(cx, cy, R, 0, Math.PI * 2); bx.fill();
    }
    // concentric range rings
    bx.strokeStyle = 'rgba(25,240,200,0.08)';
    for (let r = 120; r < R; r += 140) {
      bx.beginPath(); bx.arc(cx, cy, r, 0, 6.28); bx.stroke();
    }

    // --- pulsing measurement markers + cross-ticks ---
    for (const m of markers) {
      const px = m.x * W, py = m.y * H;
      const pulse = 0.5 + 0.5 * Math.sin(t * 0.002 * m.sp + m.ph);
      const r = 4 + pulse * 7;
      bx.strokeStyle = `rgba(94,240,255,${0.25 + pulse * 0.5})`;
      bx.lineWidth = 1.2;
      bx.beginPath(); bx.arc(px, py, r, 0, 6.28); bx.stroke();
      bx.beginPath();
      bx.moveTo(px - 11, py); bx.lineTo(px - 4, py);
      bx.moveTo(px + 4, py); bx.lineTo(px + 11, py);
      bx.moveTo(px, py - 11); bx.lineTo(px, py - 4);
      bx.moveTo(px, py + 4); bx.lineTo(px, py + 11);
      bx.stroke();
      bx.fillStyle = `rgba(25,240,200,${0.4 + pulse * 0.6})`;
      bx.beginPath(); bx.arc(px, py, 1.6, 0, 6.28); bx.fill();
    }
  }

  /* ---------- reactive bioluminescent point-field ---------- */
  const N = 80;
  const nodes = [];
  for (let i = 0; i < N; i++) {
    nodes.push({
      x: Math.random(), y: Math.random(),
      vx: (Math.random() - 0.5) * 0.0006, vy: (Math.random() - 0.5) * 0.0006,
      r: Math.random() * 2 + 1, ph: Math.random() * 6.28,
    });
  }
  let energy = 0.25, targetEnergy = 0.25;
  const mouse = { x: 0.5, y: 0.5, on: false };
  window.addEventListener('mousemove', e => {
    mouse.x = e.clientX / W; mouse.y = e.clientY / H; mouse.on = true;
  });

  function drawField(t) {
    ox.clearRect(0, 0, W, H);
    energy += (targetEnergy - energy) * 0.04;
    const speed = 0.4 + energy * 1.8;
    const link = 0.16 + energy * 0.06;       // connection distance (normalised)

    for (const p of nodes) {
      p.x += p.vx * speed; p.y += p.vy * speed;
      if (p.x < 0 || p.x > 1) p.vx *= -1;
      if (p.y < 0 || p.y > 1) p.vy *= -1;
      // gentle pull toward cursor when active
      if (mouse.on) {
        p.vx += (mouse.x - p.x) * 0.000004 * energy;
        p.vy += (mouse.y - p.y) * 0.000004 * energy;
      }
    }

    // links
    for (let i = 0; i < N; i++) {
      for (let j = i + 1; j < N; j++) {
        const a = nodes[i], b = nodes[j];
        const dx = a.x - b.x, dy = a.y - b.y;
        const d = Math.hypot(dx, dy);
        if (d < link) {
          const al = (1 - d / link) * (0.18 + energy * 0.35);
          ox.strokeStyle = `rgba(25,240,200,${al})`;
          ox.lineWidth = 0.7;
          ox.beginPath();
          ox.moveTo(a.x * W, a.y * H); ox.lineTo(b.x * W, b.y * H); ox.stroke();
        }
      }
    }
    // nodes
    for (const p of nodes) {
      const pulse = 0.6 + 0.4 * Math.sin(t * 0.003 + p.ph);
      const r = p.r * (1 + energy) * pulse;
      const g = ox.createRadialGradient(p.x * W, p.y * H, 0, p.x * W, p.y * H, r * 5);
      g.addColorStop(0, `rgba(94,240,255,${0.7 * pulse})`);
      g.addColorStop(1, 'rgba(25,240,200,0)');
      ox.fillStyle = g;
      ox.beginPath(); ox.arc(p.x * W, p.y * H, r * 5, 0, 6.28); ox.fill();
    }
  }

  let burst = 0;
  let running = false;
  function frame(t) {
    if (!running) return;                 // loop is paused
    drawPort(t);
    drawField(t);
    if (burst > 0) { targetEnergy = 1; burst -= 16; }
    else targetEnergy = mouse.on ? 0.4 : 0.25;
    requestAnimationFrame(frame);
  }
  function start() {
    if (running) return;
    running = true;
    requestAnimationFrame(frame);
  }
  function stop() { running = false; }

  // Pause when the tab is hidden — saves CPU/GPU and battery.
  document.addEventListener('visibilitychange', () => {
    document.hidden ? stop() : start();
  });

  window.Scene = {
    // call on activity; level 0..1 sets sustained energy, burst flashes it
    pulse(level = 0.5) { targetEnergy = Math.max(targetEnergy, level); },
    burst() { burst = 1400; },
  };

  window.addEventListener('resize', resize);
  resize();

  // Honour reduced-motion: paint one static frame instead of animating.
  if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    drawPort(0);
    drawField(0);
    window.Scene.burst = window.Scene.pulse = () => {};
  } else {
    start();
  }
})();
