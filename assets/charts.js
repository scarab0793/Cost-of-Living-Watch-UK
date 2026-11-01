/* Minimal accessible SVG line chart with hover/tap tooltips. No dependencies. */
(function (root) {
  'use strict';
  const NS = 'http://www.w3.org/2000/svg';
  const COLORS = ['var(--c1)', 'var(--c2)', 'var(--c3)', 'var(--c4)', 'var(--c5)', 'var(--c6)'];
  const el = (n, a, kids) => { const e = document.createElementNS(NS, n); for (const k in a || {}) e.setAttribute(k, a[k]); (kids || []).forEach(c => e.appendChild(c)); return e; };

  function niceTicks(min, max, n) {
    if (!isFinite(min) || !isFinite(max)) return [0, 1];
    if (min === max) { min -= 1; max += 1; }
    const span = max - min, step0 = span / n, mag = Math.pow(10, Math.floor(Math.log10(step0)));
    const step = [1, 2, 2.5, 5, 10].map(m => m * mag).find(s => s >= step0) || 10 * mag;
    const lo = Math.floor(min / step) * step, hi = Math.ceil(max / step) * step, t = [];
    for (let v = lo; v <= hi + step / 2; v += step) t.push(+v.toFixed(10));
    return t;
  }

  /* spec: {series:[{name,color?,points:[[year,value],...],dash?,partial?:[[year,value]]}],
            yFormat:fn, title:str, zeroBase?:bool, markers:[{x,label}], height?:number} */
  function line(host, spec) {
    host.innerHTML = '';
    host.classList.add('charthost');
    const series = (spec.series || []).filter(s => s.points && s.points.length);
    const wrap = document.createElement('div'); wrap.className = 'chart';
    host.appendChild(wrap);
    if (!series.length) { wrap.innerHTML = '<p class="small">No data available for this selection.</p>'; return; }
    const W = 760, H = spec.height || 340, m = { l: 58, r: 14, t: 14, b: 30 };
    const xs = series.flatMap(s => s.points.map(p => p[0])).concat(series.flatMap(s => (s.partial || []).map(p => p[0])));
    const ys = series.flatMap(s => s.points.map(p => p[1])).concat(series.flatMap(s => (s.partial || []).map(p => p[1])));
    const x0 = Math.min.apply(null, xs), x1 = Math.max.apply(null, xs);
    let y0 = Math.min.apply(null, ys), y1 = Math.max.apply(null, ys);
    if (spec.zeroBase) y0 = Math.min(0, y0);
    const yt = niceTicks(y0, y1, 5); y0 = yt[0]; y1 = yt[yt.length - 1];
    const X = x => m.l + (x1 === x0 ? 0.5 : (x - x0) / (x1 - x0)) * (W - m.l - m.r);
    const Y = y => H - m.b - (y - y0) / (y1 - y0) * (H - m.t - m.b);
    const fmt = spec.yFormat || (v => String(Math.round(v * 100) / 100));
    const svg = el('svg', { viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': spec.title || 'chart' });
    if (spec.title) svg.appendChild(el('title', {}, [document.createTextNode(spec.title)]));
    const g = el('g', { class: 'grid' }), ax = el('g', { class: 'axis' });
    yt.forEach(v => {
      g.appendChild(el('line', { x1: m.l, x2: W - m.r, y1: Y(v), y2: Y(v) }));
      const t = el('text', { x: m.l - 6, y: Y(v) + 4, 'text-anchor': 'end' }); t.textContent = fmt(v); ax.appendChild(t);
    });
    const span = x1 - x0, step = span > 25 ? 5 : span > 12 ? 2 : 1;
    for (let x = Math.ceil(x0 / step) * step; x <= x1; x += step) {
      const t = el('text', { x: X(x), y: H - 8, 'text-anchor': 'middle' }); t.textContent = x; ax.appendChild(t);
      g.appendChild(el('line', { x1: X(x), x2: X(x), y1: H - m.b, y2: H - m.b + 4, style: 'stroke:var(--line)' }));
    }
    svg.appendChild(g); svg.appendChild(ax);
    (spec.markers || []).forEach(mk => {
      if (mk.x < x0 || mk.x > x1) return;
      svg.appendChild(el('line', { x1: X(mk.x), x2: X(mk.x), y1: m.t, y2: H - m.b, stroke: 'var(--muted)', 'stroke-dasharray': '3 3', 'stroke-width': 1 }));
      const t = el('text', { x: X(mk.x) + 3, y: m.t + 10, fill: 'var(--muted)', 'font-size': 10 }); t.textContent = mk.label; svg.appendChild(t);
    });
    series.forEach((s, i) => {
      const col = s.color || COLORS[i % COLORS.length];
      s._col = col;
      // break the line across gaps of more than one year (never join across missing data)
      let d = '', prev = null;
      s.points.forEach(p => { d += (prev == null || p[0] - prev > 1 ? 'M' : 'L') + X(p[0]).toFixed(1) + ' ' + Y(p[1]).toFixed(1); prev = p[0]; });
      svg.appendChild(el('path', { d, fill: 'none', stroke: col, 'stroke-width': 2.2, 'stroke-linejoin': 'round', 'stroke-dasharray': s.dash || '' }));
      if (s.points.length < 40) s.points.forEach(p => svg.appendChild(el('circle', { cx: X(p[0]), cy: Y(p[1]), r: 2.4, fill: col })));
      (s.partial || []).forEach(p => svg.appendChild(el('circle', { cx: X(p[0]), cy: Y(p[1]), r: 4, fill: 'var(--panel)', stroke: col, 'stroke-width': 2 })));
    });
    const hair = el('line', { y1: m.t, y2: H - m.b, stroke: 'var(--muted)', 'stroke-width': 1, opacity: 0 }); svg.appendChild(hair);
    wrap.appendChild(svg);
    const tip = document.createElement('div'); tip.className = 'tip'; tip.style.display = 'none'; host.appendChild(tip);
    const years = Array.from(new Set(xs)).sort((a, b) => a - b);
    function show(evt) {
      const r = svg.getBoundingClientRect();
      const px = ((evt.touches ? evt.touches[0].clientX : evt.clientX) - r.left) / r.width * W;
      const xv = x0 + (px - m.l) / (W - m.l - m.r) * (x1 - x0);
      const yr = years.reduce((a, b) => Math.abs(b - xv) < Math.abs(a - xv) ? b : a, years[0]);
      let html = `<b>${yr}</b>`;
      series.forEach(s => {
        const p = s.points.find(q => q[0] === yr) || (s.partial || []).find(q => q[0] === yr);
        const isPart = !s.points.find(q => q[0] === yr) && p;
        if (p) html += `<div><span style="color:${s._col}">●</span> ${s.name}: ${fmt(p[1])}${isPart ? ' <i>(part-year)</i>' : ''}</div>`;
      });
      tip.innerHTML = html; tip.style.display = 'block';
      hair.setAttribute('x1', X(yr)); hair.setAttribute('x2', X(yr)); hair.setAttribute('opacity', 1);
      const hr = host.getBoundingClientRect();
      let left = (X(yr) / W) * r.width + (r.left - hr.left) + 10;
      if (left + 240 > hr.width) left = left - 260;
      tip.style.left = Math.max(0, left) + 'px'; tip.style.top = '8px';
    }
    function hide() { tip.style.display = 'none'; hair.setAttribute('opacity', 0); }
    svg.addEventListener('mousemove', show); svg.addEventListener('mouseleave', hide);
    svg.addEventListener('touchstart', show, { passive: true }); svg.addEventListener('touchmove', show, { passive: true });
    if (spec.legend !== false && series.length > 0) {
      const lg = document.createElement('div'); lg.className = 'legend';
      series.forEach(s => { const sp = document.createElement('span'); sp.innerHTML = `<i style="background:${s._col}"></i>${s.name}`; lg.appendChild(sp); });
      host.appendChild(lg);
    }
  }
  root.Charts = { line };
})(typeof self !== 'undefined' ? self : this);
