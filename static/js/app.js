/* Front-end logic: collect the design-vessel parameters, compute the port
   dimensions, draw the to-scale port plan and export CAD/SVG/PNG/JSON. */
(() => {
  const form = document.getElementById('vessel-form');
  const cells = document.getElementById('cells');
  const status = document.getElementById('status');
  const vesselClass = document.getElementById('vessel-class');
  const disclaimer = document.getElementById('disclaimer');
  const btn = form.querySelector('.evolve-btn');
  const presetSel = document.getElementById('preset');
  const planStage = document.getElementById('plan');
  const exportBar = document.getElementById('export-bar');
  const legend = document.getElementById('legend');

  let lastData = null;       // last successful API result
  let lastPayload = null;    // the request that produced it

  /* ---------- presets ---------- */
  fetch('/api/presets').then(r => r.ok ? r.json() : {}).then(presets => {
    for (const [key, p] of Object.entries(presets)) {
      const o = document.createElement('option');
      o.value = key; o.textContent = p.label;
      presetSel.appendChild(o);
    }
    presetSel._data = presets;
  }).catch(() => { /* presets are optional */ });

  presetSel.addEventListener('change', () => {
    const p = presetSel._data?.[presetSel.value];
    if (!p) return;
    for (const [k, v] of Object.entries(p)) {
      if (k === 'label') continue;
      const fld = form.elements[k];
      if (fld) fld.value = v;
    }
    window.Scene?.pulse(0.7);
    status.textContent = `LOADED — ${p.label} parameters`;
  });

  /* the backdrop reacts to any input; changing a field drops back to "custom" */
  form.addEventListener('input', (e) => {
    window.Scene?.pulse(0.5);
    status.textContent = 'PARAMETERS CHANGED — ready to regenerate';
    if (e.target !== presetSel) presetSel.value = '';
  });

  // ripple highlight follows cursor on the generate button
  btn.addEventListener('mousemove', e => {
    const r = btn.getBoundingClientRect();
    btn.style.setProperty('--mx', `${((e.clientX - r.left) / r.width) * 100}%`);
    btn.style.setProperty('--my', `${((e.clientY - r.top) / r.height) * 100}%`);
  });

  /* ---------- payload + validation ---------- */
  function payload() {
    const d = Object.fromEntries(new FormData(form).entries());
    const num = (x, def) => { const n = +x; return Number.isFinite(n) ? n : def; };
    return {
      vessel_type: d.vessel_type,
      loa: num(d.loa, 366), beam: num(d.beam, 51), draft: num(d.draft, 15.5),
      dwt: Math.max(0, num(d.dwt, 0)), speed_kn: num(d.speed_kn, 6),
      exposure: d.exposure, channel_type: d.channel_type,
      maneuver_aids: d.maneuver_aids, num_berths: Math.round(num(d.num_berths, 2)),
    };
  }

  function validate(p) {
    const errs = [];
    if (!(p.loa > 0) || p.loa > 600) errs.push('LOA must be 1–600 m');
    if (!(p.beam > 0) || p.beam > 120) errs.push('Beam must be 1–120 m');
    if (!(p.draft > 0) || p.draft > 40) errs.push('Draft must be 1–40 m');
    if (!(p.speed_kn > 0) || p.speed_kn > 25) errs.push('Speed must be 1–25 kn');
    if (p.num_berths < 1 || p.num_berths > 20) errs.push('Berths must be 1–20');
    if (p.beam > p.loa) errs.push('Beam cannot exceed LOA');
    return errs;
  }

  /* ---------- rendering ---------- */
  function renderCells(data) {
    cells.innerHTML = '';
    data.results.forEach((r, i) => {
      const el = document.createElement('div');
      el.className = 'cell';
      el.style.animationDelay = `${i * 70}ms`;
      el.innerHTML = `
        <div class="c-label">${r.label}</div>
        <div class="c-value">${fmt(r.value)}<span class="c-unit">${r.unit}</span></div>
        <div class="c-note">${r.note}</div>`;
      cells.appendChild(el);
    });
    vesselClass.textContent = `◆ ${data.summary.vessel_class} · Cb ${data.summary.block_coefficient} · squat ${data.summary.squat_m} m`;
    disclaimer.textContent = data.disclaimer;
    if (data.geometry && window.PortPlan) {
      window.PortPlan.render(data.geometry, data.summary.vessel_class, planStage);
      exportBar.hidden = false;
      legend.hidden = false;
    }
  }

  function fmt(v) {
    return Number.isInteger(v) ? v.toLocaleString()
      : v.toLocaleString(undefined, { maximumFractionDigits: 2 });
  }

  /* ---------- submit ---------- */
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const p = payload();
    const errs = validate(p);
    if (errs.length) {
      status.textContent = '⚠ INPUT REJECTED — ' + errs[0];
      return;
    }
    lastPayload = p;
    btn.classList.add('loading');
    status.textContent = 'GENERATING — computing port dimensions…';
    window.Scene?.burst();
    try {
      const res = await fetch('/api/calculate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(p),
      });
      if (!res.ok) throw new Error('HTTP ' + res.status);
      lastData = await res.json();
      renderCells(lastData);
      status.textContent = 'DONE — port masterplan computed ✓';
    } catch (err) {
      status.textContent = '⚠ FAILED — ' + err.message;
      cells.innerHTML = `<div class="empty-state">Could not reach the calculation engine.<br>Is the backend running?</div>`;
    } finally {
      btn.classList.remove('loading');
    }
  });

  /* ---------- exports ---------- */
  function download(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = filename;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  async function exportFile(kind, srcBtn) {
    if (!lastPayload || !lastData) return;
    const label = srcBtn.textContent;
    srcBtn.disabled = true; srcBtn.textContent = '…';
    try {
      if (kind === 'json') {
        download(new Blob([JSON.stringify(lastData, null, 2)], { type: 'application/json' }),
          'suez_port.json');
      } else if (kind === 'png') {
        await exportPng();
      } else {
        const res = await fetch(`/api/export.${kind}`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(lastPayload),
        });
        if (!res.ok) throw new Error('HTTP ' + res.status);
        download(await res.blob(), `suez_port_plan.${kind}`);
      }
      status.textContent = `EXPORTED — ${kind.toUpperCase()} drawing saved ✓`;
    } catch (err) {
      status.textContent = '⚠ EXPORT FAILED — ' + err.message;
    } finally {
      srcBtn.disabled = false; srcBtn.textContent = label;
    }
  }

  function exportPng() {
    return new Promise((resolve, reject) => {
      const svgStr = window.PortPlan?.toSvgString(planStage);
      if (!svgStr) return reject(new Error('no plan'));
      const svg = planStage.querySelector('svg');
      const vb = svg.viewBox.baseVal;
      const scale = 2;
      const canvas = document.createElement('canvas');
      canvas.width = vb.width * scale; canvas.height = vb.height * scale;
      const ctx = canvas.getContext('2d');
      const img = new Image();
      const blob = new Blob([svgStr], { type: 'image/svg+xml;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      img.onload = () => {
        ctx.fillStyle = '#03070d';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
        URL.revokeObjectURL(url);
        canvas.toBlob(b => { download(b, 'suez_port_plan.png'); resolve(); }, 'image/png');
      };
      img.onerror = () => { URL.revokeObjectURL(url); reject(new Error('render')); };
      img.src = url;
    });
  }

  exportBar.addEventListener('click', e => {
    const b = e.target.closest('.exp-btn');
    if (b) exportFile(b.dataset.export, b);
  });
})();
