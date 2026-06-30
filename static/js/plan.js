/* =========================================================================
   PortPlan: render the computed port geometry as a to-scale SVG schematic,
   matching the server-side SVG/DXF palette. Exposes window.PortPlan.
   ========================================================================= */
(() => {
  const PX = 1000;                         // longest side, design px
  const STYLE = {
    QUAY:      { stroke: '#e9b44c', fill: 'none',                   w: 3 },
    BERTH:     { stroke: '#5ef0ff', fill: 'rgba(94,240,255,0.12)',  w: 1.5 },
    TURNING:   { stroke: '#19f0c8', fill: 'rgba(25,240,200,0.05)',  w: 1.5 },
    CHANNEL:   { stroke: '#19f0c8', fill: 'rgba(25,240,200,0.04)',  w: 1.5 },
    ANCHORAGE: { stroke: '#7a5cff', fill: 'rgba(122,92,255,0.05)',  w: 1.5 },
    STRUCT:    { stroke: '#ffb454', fill: 'none',                   w: 2 },
    DIM:       { stroke: '#d6f2ec', fill: 'none',                   w: 1.4 },
  };
  const SVGNS = 'http://www.w3.org/2000/svg';

  function bbox(shapes) {
    const xs = [], ys = [];
    for (const s of shapes) {
      if (s.kind === 'circle') { xs.push(s.cx - s.r, s.cx + s.r); ys.push(s.cy - s.r, s.cy + s.r); }
      else if (s.kind === 'rect') { xs.push(s.x, s.x + s.w); ys.push(s.y, s.y + s.h); }
      else if (s.kind === 'dimension') { xs.push(s.p1[0], s.p2[0]); ys.push(s.p1[1], s.p2[1]); }
      else if (s.kind === 'note') { xs.push(s.x); ys.push(s.y); }
      else if (s.points) { for (const p of s.points) { xs.push(p[0]); ys.push(p[1]); } }
    }
    return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
  }

  /* dimension geometry: offset line, extension lines, ticks, text anchor */
  function dimGeo(p1, p2, off) {
    const [x1, y1] = p1, [x2, y2] = p2;
    const dx = x2 - x1, dy = y2 - y1, L = Math.hypot(dx, dy) || 1;
    const ux = dx / L, uy = dy / L, px = -uy, py = ux;
    const a = [x1 + px * off, y1 + py * off], b = [x2 + px * off, y2 + py * off];
    return { a, b, ext1: [[x1, y1], a], ext2: [[x2, y2], b],
             mid: [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2], u: [ux, uy], p: [px, py] };
  }

  function niceStep(raw) {
    if (raw <= 0) return 100;
    const mag = 10 ** Math.floor(Math.log10(raw));
    for (const m of [1, 2, 5, 10]) if (raw <= m * mag) return m * mag;
    return 10 * mag;
  }

  function el(name, attrs, text) {
    const n = document.createElementNS(SVGNS, name);
    for (const k in attrs) n.setAttribute(k, attrs[k]);
    if (text != null) n.textContent = text;
    return n;
  }

  /* Build an <svg> element from a geometry block (returns the node). */
  function buildSvg(geo, classLabel) {
    const shapes = geo.shapes;
    let [minx, miny, maxx, maxy] = bbox(shapes);
    const ext = Math.max(maxx - minx, maxy - miny, 1);
    const pad = ext * 0.08;
    minx -= pad; miny -= pad; maxx += pad; maxy += pad;
    const wM = maxx - minx, hM = maxy - miny;
    const scale = PX / Math.max(wM, hM);
    const W = wM * scale, H = hM * scale;
    const X = x => (x - minx) * scale;
    const Y = y => (maxy - y) * scale;          // flip to screen y-down

    const svg = el('svg', {
      xmlns: SVGNS, viewBox: `0 0 ${W.toFixed(0)} ${H.toFixed(0)}`,
      width: '100%', role: 'img',
      'aria-label': `To-scale port plan for ${classLabel}`,
    });
    svg.appendChild(el('rect', { x: 0, y: 0, width: W, height: H, fill: '#03070d' }));

    // survey grid
    const step = niceStep((maxx - minx) / 9);
    const grid = el('g', { stroke: 'rgba(25,240,200,0.10)', 'stroke-width': 1 });
    for (let x = step * Math.ceil(minx / step); x <= maxx; x += step)
      grid.appendChild(el('line', { x1: X(x), y1: 0, x2: X(x), y2: H }));
    for (let y = step * Math.ceil(miny / step); y <= maxy; y += step)
      grid.appendChild(el('line', { x1: 0, y1: Y(y), x2: W, y2: Y(y) }));
    svg.appendChild(grid);

    // shapes + labels
    for (const s of shapes) {
      const st = STYLE[s.layer] || STYLE.CHANNEL;
      let cx, cy;
      if (s.kind === 'dimension') {
        const g = dimGeo(s.p1, s.p2, s.off || 0);
        const line = (p, q, w, dash) => el('line', Object.assign(
          { x1: X(p[0]), y1: Y(p[1]), x2: X(q[0]), y2: Y(q[1]), stroke: st.stroke, 'stroke-width': w },
          dash ? { 'stroke-dasharray': '3 3' } : {}));
        svg.appendChild(line(g.a, g.b, 1.6));
        svg.appendChild(line(g.ext1[0], g.ext1[1], 1, true));
        svg.appendChild(line(g.ext2[0], g.ext2[1], 1, true));
        let tvx = g.u[0] + g.p[0], tvy = -(g.u[1] + g.p[1]);
        const tl = Math.hypot(tvx, tvy) || 1; tvx = tvx / tl * 5; tvy = tvy / tl * 5;
        for (const m of [g.a, g.b]) {
          const sx = X(m[0]), sy = Y(m[1]);
          svg.appendChild(el('line', { x1: sx - tvx, y1: sy - tvy, x2: sx + tvx, y2: sy + tvy, stroke: st.stroke, 'stroke-width': 1.6 }));
        }
        let npx = g.p[0], npy = -g.p[1]; const nl = Math.hypot(npx, npy) || 1;
        svg.appendChild(el('text', {
          x: X(g.mid[0]) + npx / nl * 12, y: Y(g.mid[1]) + npy / nl * 12 + 4,
          fill: st.stroke, 'font-size': 12, 'font-family': 'monospace', 'text-anchor': 'middle',
          'paint-order': 'stroke', stroke: '#03070d', 'stroke-width': 3,
        }, s.text));
        continue;
      } else if (s.kind === 'note') {
        svg.appendChild(el('text', {
          x: X(s.x), y: Y(s.y), fill: st.stroke, 'font-size': 13, 'font-family': 'monospace',
          'text-anchor': s.anchor || 'middle', 'paint-order': 'stroke', stroke: '#03070d', 'stroke-width': 3,
        }, s.text));
        continue;
      } else if (s.kind === 'circle') {
        svg.appendChild(el('circle', {
          cx: X(s.cx), cy: Y(s.cy), r: s.r * scale,
          fill: st.fill, stroke: st.stroke, 'stroke-width': st.w,
        }));
        cx = X(s.cx); cy = Y(s.cy);
      } else if (s.kind === 'rect') {
        svg.appendChild(el('rect', {
          x: X(s.x), y: Y(s.y + s.h), width: s.w * scale, height: s.h * scale,
          fill: st.fill, stroke: st.stroke, 'stroke-width': st.w, rx: 1,
        }));
        cx = X(s.x + s.w / 2); cy = Y(s.y + s.h / 2);
      } else {
        const pts = s.points.map(p => `${X(p[0]).toFixed(1)},${Y(p[1]).toFixed(1)}`).join(' ');
        svg.appendChild(el('polyline', { points: pts, fill: 'none', stroke: st.stroke, 'stroke-width': st.w }));
        const mid = s.points[Math.floor(s.points.length / 2)];
        cx = X(mid[0]); cy = Y(mid[1]) - 8;
      }
      if (s.label) {
        svg.appendChild(el('text', {
          x: cx, y: cy, fill: st.stroke, 'font-size': 13, 'font-family': 'monospace',
          'text-anchor': 'middle', 'paint-order': 'stroke', stroke: '#03070d', 'stroke-width': 3,
        }, s.label));
      }
    }

    // north arrow (top-right, screen space)
    if (geo.north) {
      const nx = W - 26, ny = 80;
      const ng = el('g', { stroke: '#d6f2ec', 'stroke-width': 2, fill: '#d6f2ec' });
      ng.appendChild(el('line', { x1: nx, y1: ny + 22, x2: nx, y2: ny }));
      ng.appendChild(el('polygon', { points: `${nx},${ny - 3} ${nx - 5},${ny + 8} ${nx + 5},${ny + 8}`, stroke: 'none' }));
      ng.appendChild(el('text', { x: nx, y: ny - 7, 'font-size': 12, 'text-anchor': 'middle', stroke: 'none' }, 'N'));
      svg.appendChild(ng);
    }

    // scale bar
    const barM = niceStep((W / scale) / 5);
    const barPx = barM * scale;
    const x0 = W * 0.03, y0 = H - H * 0.04;
    const g = el('g', { stroke: '#cfeee9', 'stroke-width': 2, fill: '#cfeee9' });
    g.appendChild(el('line', { x1: x0, y1: y0, x2: x0 + barPx, y2: y0 }));
    g.appendChild(el('line', { x1: x0, y1: y0 - 6, x2: x0, y2: y0 + 6 }));
    g.appendChild(el('line', { x1: x0 + barPx, y1: y0 - 6, x2: x0 + barPx, y2: y0 + 6 }));
    g.appendChild(el('text', {
      x: x0, y: y0 - 10, 'stroke-width': 0, 'font-size': 15, 'font-family': 'monospace',
    }, `${barM.toLocaleString()} m`));
    svg.appendChild(g);
    return svg;
  }

  window.PortPlan = {
    render(geo, classLabel, mount) {
      mount.innerHTML = '';
      mount.appendChild(buildSvg(geo, classLabel));
    },
    /* serialize the currently-mounted SVG to a standalone string */
    toSvgString(mount) {
      const svg = mount.querySelector('svg');
      if (!svg) return null;
      return '<?xml version="1.0" encoding="UTF-8"?>\n' + new XMLSerializer().serializeToString(svg);
    },
  };
})();
