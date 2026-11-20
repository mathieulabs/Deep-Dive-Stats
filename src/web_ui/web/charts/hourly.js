// Hourly Breakdown: a bar per hour of the day, the success rate as a smooth line over it (right axis in %).
(function(){
  'use strict';
  const DD = window.DD;
  const U = DD.cu;
  const FONT = '12px "Segoe UI",-apple-system,BlinkMacSystemFont,sans-serif';
  const FONT_X = '10px "Segoe UI",-apple-system,BlinkMacSystemFont,sans-serif';

  // slopes of the smooth curve through pts, the same monotone cubic as DD.cu.smoothPath (2 points: a straight line)
  function slopes(pts){
    const n = pts.length, ms = new Array(n).fill(0);
    if (n < 2) return ms;
    const last = n - 1, hs = [], ds = [];
    for (let i = 0; i < last; i++){ const hh = pts[i + 1][0] - pts[i][0]; if (hh <= 0) return ms; hs.push(hh); ds.push((pts[i + 1][1] - pts[i][1]) / hh); }
    if (n === 2){ ms[0] = ms[1] = ds[0]; return ms; }
    ms[0] = ds[0]; ms[last] = ds[last - 1];
    for (let i = 1; i < last; i++){ const d0 = ds[i - 1], d1 = ds[i]; if (d0 * d1 > 0){ const h0 = hs[i - 1], h1 = hs[i]; ms[i] = 3 * (h0 + h1) / ((2 * h1 + h0) / d0 + (h1 + 2 * h0) / d1); } }
    if (ds[0] === 0 || ms[0] * ds[0] < 0) ms[0] = 0;
    if (ds[last - 1] === 0 || ms[last] * ds[last - 1] < 0) ms[last] = 0;
    return ms;
  }
  class Chart {
    constructor(root, payload, colors, options){
      this.canvas = root.querySelector('canvas');
      this.ctx = this.canvas.getContext('2d');
      this.colors = colors;
      this.options = Object.assign({chart_opacity_pct: 100, show_rate: true}, options || {});
      this.payload = payload;
      this.progress = 0;
      this.hoverIdx = -1;
      this._resize();
    }
    _resize(){
      const f = DD.fitCanvas(this.canvas, this.ctx), w = f.w, h = f.h, dpr = f.dpr;
      this.w = w; this.h = h;
    }
    setPayload(p){ if (DD._noAnim){ this.morph = null; this.payload = p; return; } this.morph = {from: this.series(), start: null, k: DD.calm ? DD.calm() : 1}; this.payload = p; }  // from what is on screen (a morph may be running)
    rawSeries(){
      const d = (this.payload && this.payload.data) || {};
      const totals = [], correct = [];
      for (let i = 0; i < 24; i++){ const r = d[i] || d[String(i)] || {}; totals.push(Number(r.total || 0)); correct.push(Number(r.correct || 0)); }
      return {totals: totals, correct: correct};
    }
    series(){
      const to = this.rawSeries(), mo = this.morph;
      to.rates = to.totals.map(function(v, i){ return v > 0 ? to.correct[i] / v : 0; });
      to.vis = to.totals.map(function(v){ return v > 0 ? 1 : 0; });
      to.active = to.totals.map(function(v){ return v > 0; });
      const toMax = Math.max.apply(null, to.totals) > 0 ? Math.max.apply(null, to.totals) : 1;
      to.ratios = to.totals.map(function(v){ return Math.max(0, v / Math.max(1, toMax)); });
      to.axisMax = Math.max(1, toMax);
      if (!mo) return to;
      const now = performance.now();
      if (mo.start === null) mo.start = now;
      const t = Math.min(1, (now - mo.start) / (300 * (mo.k || 1)));  // 300 ms, as Activity's zoom (210: its axis flew by)
      if (t >= 1){ this.morph = null; if (DD.dev) DD.trace('ANIMTRACE hourly morph end after ' + Math.round(now - mo.start) + ' ms (' + (mo.n || 0) + ' frames)'); return to; }
      // dev trace: the morph's time, its curve and the gap since the last frame (a slow start then a jump: frames missed)
      if (DD.dev && mo.lastT !== now){ mo.n = (mo.n || 0) + 1; DD.trace('ANIMTRACE hourly morph frame ' + mo.n + ' t=' + t.toFixed(3) + ' gap ' + (mo.lastT ? Math.round(now - mo.lastT) : 0) + ' ms, k=' + (mo.k || 1).toFixed(2) + ', axis ' + Math.round((mo.from && mo.from.axisMax) || 0) + ' -> ' + Math.round(to.axisMax)); mo.lastT = now; }
      const e = 1 - Math.pow(1 - t, 3);  // OutCubic
      const mix = function(a, b){ return b.map(function(v, i){ return a[i] + (v - a[i]) * e; }); };
      // the total line: an hour on both sides glides; one that appears or goes fades in / out
      // where it is, along a smoothstep of the time (no pop at the fast start of the curve)
      const lt = t * t * (3 - 2 * t), fo = mo.from, rates = [], vis = [], active = [];
      for (let i = 0; i < 24; i++){
        const ot = fo.totals[i] || 0, nt = to.totals[i] || 0;
        const orate = fo.rates ? fo.rates[i] : (ot > 0 ? fo.correct[i] / ot : 0), nrate = nt > 0 ? to.correct[i] / nt : 0;
        const oa = fo.active ? !!fo.active[i] && (fo.vis ? fo.vis[i] > 0.001 : true) : ot > 0, na = nt > 0;
        if (oa && na){ rates.push(orate + (nrate - orate) * e); vis.push(1); active.push(true); }
        else if (oa){ rates.push(orate); const v = (fo.vis ? fo.vis[i] : 1) * (1 - lt); vis.push(v); active.push(v > 0.001 && t < 0.999); }
        else if (na){ rates.push(nrate); vis.push(lt); active.push(true); }
        else { rates.push(0); vis.push(0); active.push(false); }
      }
      // an hour that comes or goes is drawn on the straight way between the hours kept on both sides while it is
      // faint (it rises out of it / sinks into it as it fades), so the line never bends at once when it is added at
      // the start or cut out at the end
      const kept = []; for (let i = 0; i < 24; i++){ const ot = fo.totals[i] || 0, nt = to.totals[i] || 0; kept.push((fo.active ? !!fo.active[i] : ot > 0) && nt > 0); }
      for (let i = 0; i < 24; i++){
        if (kept[i] || !active[i]) continue;
        let a = i - 1; while (a >= 0 && !kept[a]) a--;
        let b = i + 1; while (b < 24 && !kept[b]) b++;
        if (a < 0 && b >= 24) continue;
        const nb = a < 0 ? rates[b] : b >= 24 ? rates[a] : rates[a] + (rates[b] - rates[a]) * (i - a) / (b - a);
        const w = 1 - Math.max(0, Math.min(1, vis[i]));
        rates[i] = rates[i] + (nb - rates[i]) * w;
      }
      // each bar goes from its height on the old scale to its height on the new one, the axis gliding between the
      // two maxima: a deck emptied sinks its bars, an empty one grows them (old / new draw ratios)
      const fr = fo.ratios || fo.totals.map(function(){ return 0; }), fa = fo.axisMax || 1;
      const om = [], nm = []; for (let i = 0; i < 24; i++){ const ot = fo.totals[i] || 0; om.push(fo.active ? !!fo.active[i] && (fo.vis ? fo.vis[i] > 0.001 : true) : ot > 0); nm.push((to.totals[i] || 0) > 0); }
      return {ax0: fa, ax1: to.axisMax, om: om, nm: nm, e: e, totals: mix(fo.totals, to.totals), correct: mix(fo.correct, to.correct), rates: rates, vis: vis, active: active,
        ratios: to.ratios.map(function(r, i){ return Math.max(0, Math.min(1, fr[i] + (r - fr[i]) * e)); }), axisMax: Math.max(1, DD.scaleLerp(fa, to.axisMax, e))};
    }
    indexAt(mx, my){
      const g = this._g; if (!g) return -1;
      if (!(mx >= g.ml && mx <= this.w - g.mr && my >= g.mt + 10 && my <= this.h - g.mb)) return -1;
      return Math.max(0, Math.min(23, Math.trunc((mx - g.ml) / (g.plotW / 24))));
    }
    tipRows(i){
      const s = this.series(), t = s.totals[i], f = function(v){ return U.formatNum(Math.round(v)); };
      const rows = [{header: true, text: i + ':00 - ' + i + ':59'}];
      rows.push({text: DD.t('Reviews: {count}', {count: f(t)})});
      if (t > 0) rows.push({text: DD.t('Correct: {rate}%', {rate: U.trimNum(s.correct[i] / t * 100, 1)})});
      return rows;
    }
    draw(){
      const ctx = this.ctx, w = this.w, h = this.h, C = this.colors;
      ctx.clearRect(0, 0, w, h);
      const dark = !!C.is_dark;
      const s = this.series();
      const maxVal = s.axisMax || Math.max(1, Math.max.apply(null, s.totals));
      const t = Math.max(0, Math.min(1, this.progress));
      const intro = U.easeOutQuart(t);
      ctx.font = FONT;
      // the left margin fits the top value; during a transition it glides from the old one's to the new one's, never
      // snapping by a whole digit as the value counts
      const mlOf = function(v){ const lb = v >= 10 ? U.formatNum(Math.trunc(v)) : (Math.round(v * 10) / 10).toFixed(1); return Math.max(35, Math.trunc(ctx.measureText(lb).width) + 12); };
      const ml = s.ax0 != null ? Math.round(mlOf(s.ax0) + (mlOf(s.ax1) - mlOf(s.ax0)) * s.e) : mlOf(maxVal);
      const showRate = this.options.show_rate !== false;
      const mr = showRate ? 35 : 10, mt = 10, mb = 30;
      const plotW = w - ml - mr, plotH = h - mt - mb;
      this._g = {ml: ml, mr: mr, mt: mt, mb: mb, plotW: plotW};
      const bottom = mt + plotH;
      const grid = U.parseColor((this.options && this.options.show_grid === false ? 'rgba(0,0,0,0)' : C.grid)), txt = U.parseColor(C.text_secondary);
      const css = U.cssRgba;
      const axisCol = css(txt, ((dark ? 175 : 215) / 255).toFixed(4));
      const axisCol2 = css(txt, ((dark ? 175 : 215) * 0.8 / 255).toFixed(4));
      ctx.textBaseline = 'middle';
      if (DD.axisSlide && DD.axisSlide()){
        // Chart_Axis_Anim 'slide' (dd-core DD.slideTicks): round values at their heights on the scale of the moment, the
        // exact top written too; during the change of the bars (it knows its start, end and progress) they slide, the
        // old ones leave and the new ones come with the bars (the axis' own 220 ms fades ran apart from the bars and
        // left values half there)
        const fmtV = (v) => (v === 0 ? '0' : (v >= 10 ? U.formatNum(Math.trunc(v)) : U.trimNum(v, 1)));
        (s.ax0 != null ? DD.slideTicks(s.ax0, s.ax1, maxVal, s.e, 4, plotH, {tag: 'hourly'}) : DD.slideTicks(maxVal, maxVal, maxVal, 1, 4, plotH, {tag: 'hourly'})).forEach((k) => {
          const y = mt + plotH * (1 - k.f), yl = Math.trunc(y) + 0.5;
          ctx.globalAlpha = k.a;
          ctx.strokeStyle = css(grid, Math.min(1, grid.a * (k.f <= 0.0005 ? 2.6 : 1.5))); ctx.lineWidth = 1;
          ctx.beginPath(); ctx.moveTo(ml, yl); ctx.lineTo(w - mr, yl); ctx.stroke();
          ctx.fillStyle = axisCol; ctx.textAlign = 'right'; ctx.fillText(fmtV(k.v), ml - 8, Math.trunc(y));
        });
        ctx.globalAlpha = 1;
      } else for (let i = 0; i <= 4; i++){
        const y = mt + plotH * (1 - i / 4);
        ctx.strokeStyle = css(grid, Math.min(1, grid.a * (i === 0 ? 2.6 : 1.5))); ctx.lineWidth = 1;
        const yl = Math.trunc(y) + 0.5;
        ctx.beginPath(); ctx.moveTo(ml, yl); ctx.lineTo(w - mr, yl); ctx.stroke();
        const v = maxVal * i / 4;
        ctx.fillStyle = axisCol; ctx.textAlign = 'right';
        ctx.fillText(i === 0 ? '0' : (v >= 10 ? U.formatNum(Math.trunc(v)) : U.trimNum(v, 1)), ml - 8, Math.trunc(y));
      }
      if (showRate){
        ctx.fillStyle = axisCol2; ctx.textAlign = 'right';
        for (let i = 0; i <= 5; i++){
          const y = mt + plotH * (1 - i / 5);
          ctx.fillText(Math.trunc(100 * i / 5) + '%', w - 4, Math.trunc(y));
        }
      }
      // x axis
      ctx.font = FONT_X; ctx.fillStyle = css(txt, 1); ctx.textAlign = 'center';
      const step = plotW / 24;
      const skip = step < 10 ? 4 : (step < 20 ? 2 : 1);
      for (let i = 0; i < 24; i++){
        if (i % skip) continue;
        ctx.fillText(String(i), ml + i * step + step / 2, h - mb + 5 + 7.5);
      }
      // bars
      const barW = Math.max(1, step * 0.9);
      const opac = Math.max(0, Math.min(100, this.options.chart_opacity_pct)) * 2.55 / 255;
      const base = C.bar;
      for (let i = 0; i < 24; i++){
        const v = s.totals[i];
        if (i === this.hoverIdx && U.hoverColumn) U.hoverColumn(ctx, ml + i * step, step, mt, plotH, dark, C.text_primary);
        if (v === 0) continue;
        const ratio = s.ratios ? s.ratios[i] : v / maxVal;
        const x = ml + i * step + (step - barW) / 2;
        const bh = ratio * plotH * (this.morph ? 1 : intro), y = bottom - bh;
        let hex = U.gradientColor(base, Math.min(1, ratio), dark);
        const hov = i === this.hoverIdx;
        if (hov){ const m = /rgb\((\d+),(\d+),(\d+)\)/.exec(U.hoverFill(hex, dark)); hex = '#' + [m[1], m[2], m[3]].map(function(v){ return (+v).toString(16).padStart(2, '0'); }).join(''); }
        U.roundedBar(ctx, x, y, barW, bh, U.barFill(ctx, hex, y, barW, bh, hov ? 1 : opac, dark, 0.43), true);
      }
      // success rate
      if (showRate) this.drawRate(ctx, s, ml, mt, plotW, plotH, step, txt, dark, this.morph ? 1 : intro);
    }
    // one line through every active hour; each point has its own visibility and
    // each segment takes the visibility of its least visible end; an hour whose neighbours are not shown yet is a stub
    drawRate(ctx, s, ml, mt, plotW, plotH, step, txt, dark, grow){
      const k = grow == null ? 1 : grow;
      const C = this.colors, css = U.cssRgba;
      const lineK = (this.options.line_opacity_pct != null ? this.options.line_opacity_pct : 80) / 100, bottom = mt + plotH;
      const runs = []; let cur = [];
      for (let i = 0; i < 24; i++){ if (s.active[i]) cur.push(i); else if (cur.length){ runs.push(cur); cur = []; } }
      if (cur.length) runs.push(cur);
      // dev trace: the line as drawn (each hour's point and how visible it is, the runs it is cut in)
      this._lsig = {runs: runs.map(function(r){ return r[0] + '-' + r[r.length - 1]; }).join(','), pts: {}};
      { const sig = this._lsig; for (let i = 0; i < 24; i++) if (s.active[i]) sig.pts[i] = [mt + plotH - Math.max(0, Math.min(1, s.rates[i])) * plotH, Math.max(0, Math.min(1, s.vis[i]))]; }
      // as Anki's charts draw it (.cumulative-overlay): a flat pale area in the text's colour (Anki: black 3 % light,
      // white 8 % dark), its edge a faint dark line (black 8 % / 18 %); the Total / Average Lines setting scales both,
      // its default (80 %) giving Anki's values
      const A = DD.areaStyle(C, dark, lineK / 0.8), fillCol = A.fill, fillA = A.fillA, lineA = A.lineA;
      const lineCol = A.line, lineW = A.lw, self = this;
      // the Total Line setting (none by default): a clear line over that edge, as before
      const strong = (this.options.total_line_pct || 0) / 100, bgc = C.bg || (dark ? '#000000' : '#ffffff');
      const halo = dark ? U.scaleV(bgc, 1 / 1.6) : bgc, clearCol = C.text_primary || C.total_line || (dark ? '#ffffff' : '#000000');
      // during a transition: the slopes of the curve as the still chart rounds it, stretch by stretch of hours with data
      // (an hour by an hour without data ends its stretch), those of the old stretches gliding into the new ones. One
      // curve through every point (the hours coming / going too) rounded the hours by a gap otherwise, and they took
      // their shape at once at the end
      let hourMs = null;
      if (s.om){
        const X = function(i){ return ml + (i + 0.5) * step; }, Y = function(i){ return mt + plotH - Math.max(0, Math.min(1, s.rates[i])) * plotH; };
        const msOf = function(M){
          const out = new Array(24).fill(0);
          let a = -1;
          for (let i = 0; i <= 24; i++){
            const on = i < 24 && M[i];
            if (on && a < 0) a = i;
            if (!on && a >= 0){
              const run = []; for (let j = a; j < i; j++) run.push(j);
              const pts = run.map(function(j){ return [X(j), Y(j)]; }), off = run[0] === 0 && run.length > 1 ? 1 : 0;
              if (run.length > 1){ if (run[0] === 0) pts.unshift([ml, pts[0][1]]); if (run[run.length - 1] === 23) pts.push([ml + plotW, pts[pts.length - 1][1]]); }
              const m = slopes(pts);
              run.forEach(function(j, k){ out[j] = m[k + off]; });
              a = -1;
            }
          }
          return out;
        };
        const mo = msOf(s.om), mn = msOf(s.nm);
        hourMs = mo.map(function(v, i){ return v + (mn[i] - v) * s.e; });
      }
      // the path through xy with the slopes above (U.smoothPath when still)
      const curve = function(g, xy, hours){
        if (!hourMs || xy.length < 2){ U.smoothPath(g, xy); return; }
        const ms = hours.map(function(h){ return h == null ? 0 : hourMs[h]; });
        g.moveTo(xy[0][0], xy[0][1]);
        for (let i = 0; i < xy.length - 1; i++){
          const h3 = (xy[i + 1][0] - xy[i][0]) / 3;
          g.bezierCurveTo(xy[i][0] + h3, xy[i][1] + ms[i] * h3, xy[i + 1][0] - h3, xy[i + 1][1] - ms[i + 1] * h3, xy[i + 1][0], xy[i + 1][1]);
        }
      };
      runs.forEach(function(run){
        let pts = run.map(function(i){ return [ml + (i + 0.5) * step, mt + plotH - Math.max(0, Math.min(1, s.rates[i])) * plotH * k, Math.max(0, Math.min(1, s.vis[i]))]; });
        if (Math.max.apply(null, pts.map(function(p){ return p[2]; })) <= 0.002) return;
        const single = pts.length === 1;
        let hours = run.slice();
        if (single){
          const half = step * 0.32;
          pts = [[pts[0][0] - half, pts[0][1], pts[0][2]], [pts[0][0] + half, pts[0][1], pts[0][2]]];
        } else {
          if (run[0] === 0){ pts.unshift([ml, pts[0][1], pts[0][2]]); hours.unshift(null); }
          if (run[run.length - 1] === 23){ pts.push([ml + plotW, pts[pts.length - 1][1], pts[pts.length - 1][2]]); hours.push(null); }
        }
        const x0 = pts[0][0], x1 = pts[pts.length - 1][0], span = Math.max(1e-6, x1 - x0);
        const ramp = function(col, alpha){
          const g = ctx.createLinearGradient(x0, 0, x1, 0), eps = 1e-4;
          for (let i = 0; i < pts.length - 1; i++){
            const a = Math.min(pts[i][2], pts[i + 1][2]);
            const p0 = Math.max(0, Math.min(1, (pts[i][0] - x0) / span)), p1 = Math.max(0, Math.min(1, (pts[i + 1][0] - x0) / span));
            g.addColorStop(Math.min(1, p0 + (i > 0 ? eps : 0)), col(alpha * a));
            g.addColorStop(Math.max(0, p1 - (i < pts.length - 2 ? eps : 0)), col(alpha * a));
          }
          return g;
        };
        const xy = pts.map(function(p){ return [p[0], p[1]]; });
        // the area: flat, with the horizontal visibility ramp (each stretch as visible as its least visible end), laid over the bars
        ctx.save();
        ctx.beginPath(); if (single) U.smoothPath(ctx, xy); else curve(ctx, xy, hours); ctx.lineTo(x1, bottom); ctx.lineTo(x0, bottom); ctx.closePath();
        ctx.fillStyle = ramp(function(a){ return U.rgba(fillCol, a); }, fillA); ctx.fill();
        ctx.lineJoin = 'round'; ctx.lineCap = 'round';
        ctx.beginPath(); if (single) U.smoothPath(ctx, xy); else curve(ctx, xy, hours);
        ctx.strokeStyle = ramp(function(a){ return U.rgba(lineCol, a); }, lineA); ctx.lineWidth = lineW; ctx.stroke();
        if (strong > 0){
          ctx.strokeStyle = ramp(function(a){ return U.rgba(halo, a); }, Math.min(1, 150 / 255 * lineK * strong)); ctx.lineWidth = 3.4; ctx.stroke();
          ctx.strokeStyle = ramp(function(a){ return U.rgba(clearCol, a); }, Math.min(1, 215 / 255 * lineK * strong)); ctx.lineWidth = 1.3; ctx.stroke();
        }
        if (!single){
          for (let i = 0; i < pts.length; i++){
            const sl = i > 0 ? Math.min(pts[i - 1][2], pts[i][2]) : 0, sr = i < pts.length - 1 ? Math.min(pts[i + 1][2], pts[i][2]) : 0;
            const sa = pts[i][2] - Math.max(sl, sr);
            if (sa <= 0.01) continue;
            const half = step * 0.32;
            ctx.beginPath(); ctx.moveTo(pts[i][0] - half, pts[i][1]); ctx.lineTo(pts[i][0] + half, pts[i][1]);
            ctx.strokeStyle = U.rgba(strong > 0 ? clearCol : lineCol, (strong > 0 ? Math.min(1, 215 / 255 * lineK * strong) : lineA) * sa); ctx.lineWidth = strong > 0 ? 1.3 : lineW; ctx.stroke();
          }
        }
        ctx.restore();
      });
    }
  }

  function head(el, payload){
    if (!el) return;
    // the reviews of filtered decks counted or not
    const pills = el.querySelector('.dd-pills');
    if (pills && payload && payload.include_filtered != null && DD.optionsPill){
      pills.innerHTML = '';
      DD.optionsPill(pills, 'hourly', 'Which reviews are counted', [['include_filtered', 'Include Filtered Reviews', payload.include_filtered !== false, true]]);
    }
    const st = el.querySelector('.dd-stat');
    if (!st) return;
    const d = (payload && payload.data) || {};
    let tot = 0, cor = 0;
    for (let i = 0; i < 24; i++){ const r = d[i] || d[String(i)] || {}; tot += Number(r.total || 0); cor += Number(r.correct || 0); }
    const f = function(v){ return Math.abs(v - Math.round(v)) < 1e-6 ? U.formatNum(Math.round(v)) : U.trimNum(v, 1); };
    st.textContent = DD.t('Total: {count} revs', {count: f(tot)}) + '  ·  ' + (tot > 0 ? DD.t('Retention: {value}%', {value: f(cor / tot * 100)}) : DD.t('Retention: -'));
  }

  DD.registerChart('hourly', {
    mount: function(el, ctx){
      el.innerHTML = '<div class="dd-plot"><canvas></canvas><div class="dd-tip"></div></div>';
      const plot = el.firstChild;
      plot._ddBrowse = function(){ const i = chart.hoverIdx; return (i == null || i < 0) ? null : {hour: i}; };
      const chart = new Chart(plot, ctx.data, DD.theme.chart, ctx.options || {});
      head(ctx.head, ctx.data);
      if (!ctx.animate) chart.progress = 1;
      const state = {start: null, last: true};
      DD.hover.attach(plot, chart, {index: function(x, y){ return chart.indexAt(x, y); }, rows: function(i){ return chart.tipRows(i); }, redraw: function(){ state.last = true; DD.frame.kick(); }});
      // dev trace (ANIMTRACE hourly): the total line frame to frame: a point that jumps, a run that splits / joins, an
      // hour that pops in or out (not faded), and the end of a transition against the still chart
      let lPrev = null, lWas = false;
      function lineCheck(ending){
        const c = chart._lsig; if (!DD.dev || !c) return;
        const p = lPrev;
        if (p){
          const msg = [];
          let mx = 0, at = '';
          for (let i = 0; i < 24; i++){
            const a = p.pts[i], b = c.pts[i];
            if (a && b){ const dy = Math.abs(a[0] - b[0]); if (dy > mx){ mx = dy; at = i + 'h y ' + a[0].toFixed(1) + '->' + b[0].toFixed(1); } if (Math.abs(a[1] - b[1]) > 0.25) msg.push(i + 'h vis ' + a[1].toFixed(2) + '->' + b[1].toFixed(2)); }
            else if (a && a[1] > 0.05) msg.push(i + 'h GONE at vis ' + a[1].toFixed(2));
            else if (b && b[1] > 0.05) msg.push(i + 'h CAME at vis ' + b[1].toFixed(2));
          }
          if (mx > (ending ? 1.5 : 12)) msg.unshift('moved ' + mx.toFixed(1) + 'px (' + at + ')');
          if (p.runs !== c.runs) msg.push('runs ' + p.runs + ' -> ' + c.runs);
          if (msg.length) DD.trace('ANIMTRACE hourly line ' + (ending ? 'END ' : '') + msg.slice(0, 6).join(' | '));
        }
        lPrev = c;
      }
      function frame(now){
        // its intro not played yet (it waited out of view) and new data came meanwhile: the intro alone shows it
        // (the change's morph ran with it, a second animation over the first)
        if (chart.progress < 1 && state.start === null && (chart.morph)){ if (DD.dev) DD.trace('ANIMTRACE hourly intro not played yet: its morph dropped, the intro shows the new data'); chart.morph = null; }
        if (chart.progress < 1){ if (state.start === null) state.start = now; chart.progress = Math.min(1, (now - state.start) / DD.intro(500)); }
        const needs = chart.progress < 1 || !!chart.morph;
        const morphing = !!chart.morph;
        if (needs || state.last){ chart.draw(); if (morphing || lWas) lineCheck(!morphing && lWas); else lPrev = chart._lsig; lWas = morphing; }
        state.last = needs;
        return needs;
      }
      const resizer = new ResizeObserver(function(){ DD.frame.resized(frame, function(){ chart._resize(); state.last = true; }); });
      DD.frame.observe(resizer, plot);
      if (!ctx.animate) chart.draw();
      DD.frame.add(frame);
      return {
        update: function(data){ chart.setPayload(data); head(ctx.head, data); state.last = true; DD.frame.kick(); },
        setOptions: function(o){ Object.assign(chart.options, o); state.last = true; DD.frame.kick(); },
        setTheme: function(){ chart.colors = DD.theme.chart; state.last = true; DD.frame.kick(); },
        destroy: function(){ DD.frame.remove(frame); resizer.disconnect(); el.innerHTML = ''; if (ctx.head){ const st = ctx.head.querySelector('.dd-stat'); if (st) st.textContent = ''; } },
      };
    },
  });
})();
