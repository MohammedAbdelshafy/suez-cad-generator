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
  };
  const SVGNS = 'http://www.w3.org/2000/svg';

  function bbox(shapes) {
    const xs = [], ys = [];
    for (const s of shapes) {
      if (s.kind === 'circle') { xs.push(s.cx - s.r, s.cx + s.r); ys.push(s.cy - s.r, s.cy + s.r); }
      else if (s.kind === 'rect') { xs.push(s.x, s.x + s.w); ys.push(s.y, s.y + s.h); }
      else { for (const p of s.points) { xs.push(p[0]); ys.push(p[1]); } }
    }
    return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
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
      if (s.kind === 'circle') {
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
      const t = el('text', {
        x: cx, y: cy, fill: st.stroke, 'font-size': 13, 'font-family': 'monospace',
        'text-anchor': 'middle', 'paint-order': 'stroke', stroke: '#03070d', 'stroke-width': 3,
      }, s.label);
      svg.appendChild(t);
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
