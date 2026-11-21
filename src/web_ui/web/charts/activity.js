// Activity chart: bars by review type, cumulative line, average, hover, zoom, transitions.
// Drawn on a canvas.
(function(){
  'use strict';
  const DD = window.DD;
  const SETTINGS = {bin_scale: 100};
  const TYPE_KEYS = ['mature', 'young', 'relearn', 'learn', 'cram'];
  const TYPE_LABELS = { mature: 'Mature', young: 'Young', relearn: 'Relearn', learn: 'Learn', cram: 'Filtered' };
  const ROW_FIELDS = ['total'].concat(TYPE_KEYS);

  // An animation's clock: the time it has played, a frame counting 34 ms at most. A zoom starts with the page busy
  // (every linked chart starting its own, their stats read again: 50-90 ms tasks), and on the wall clock the first
  // frames skipped half the zoom (ZOOMFRAMES: 33 bars -> 17 at the second frame, then nothing left to see). A frame
  // late now plays the next step, not the whole wait.
  // (the zoom camera's, zoom_camera.js)
  function playClock(o, now){ return DD.zoomCam.clock(o, now); }

  function easeOutQuart(t){ const u = 1 - t; return 1 - u*u*u*u; }
  function easeInOutCubic(t){ return t < 0.5 ? 4*t*t*t : 1 - Math.pow(-2*t + 2, 3) / 2; }
  function smootherstep(t){ return t * t * (3 - 2 * t); }

  function formatNum(v){
    return Math.round(v).toLocaleString('en-US');
  }

  // a straight line through the bars (least squares): the bars with something in
  // them, by their index; with "Show as %", the passed share of each (trend_pass_keys). null: no trend to draw
  function trendOf(bins, o){
    if (!o.show_trend) return null;
    const pct = !!(o.show_percent && o.show_breakdown), pass = o.trend_pass_keys;
    if (pct && (!pass || (o.hidden_review_types || []).length || o.metric_mode === 'time')) return null;
    const pts = [];
    bins.forEach((b, i) => {
      const t = b.total || 0;
      if (t > 0) pts.push([i, pct ? pass.reduce((a, k) => a + (b[k] || 0), 0) * 100 / t : t]);
    });
    if (pts.length < 3) return null;
    let mx = 0, my = 0;
    pts.forEach((p) => { mx += p[0]; my += p[1]; });
    mx /= pts.length; my /= pts.length;
    let sxx = 0, sxy = 0;
    pts.forEach((p) => { sxx += (p[0] - mx) * (p[0] - mx); sxy += (p[0] - mx) * (p[1] - my); });
    if (!(sxx > 0)) return null;
    const slope = sxy / sxx;
    return {slope: slope, at: (i) => my + slope * (i - mx), i0: pts[0][0], i1: pts[pts.length - 1][0], pct: pct};
  }
  // the trend's words: its change from one bar to the next, in the bars' unit, per the rows a bar holds
  const TREND_PER = {
    day: ['Trend: {value} per day', 'Trend: {value} per {n} days'],
    review: ['Trend: {value} per prior review', 'Trend: {value} per {n} prior reviews'],
    ivl: ['Trend: {value} per day of interval', 'Trend: {value} per {n} days of interval'],
    second: ['Trend: {value} per second', 'Trend: {value} per {n} seconds'],
    sibling: ['Trend: {value} per day since the sibling', 'Trend: {value} per {n} days since the sibling'],
  };
  function trendText(c){
    const t = c.trend, o = c.options;
    if (!t) return '';
    const a = Math.abs(t.slope), sign = t.slope > 0 ? '+' : (t.slope < 0 ? '−' : '');
    const num = sign + (a >= 100 ? trimNum(a, 0) : a >= 10 ? trimNum(a, 1) : a >= 1 ? trimNum(a, 2) : a >= 0.001 ? trimNum(a, a >= 0.1 ? 2 : 3) : '0');
    let val;
    if (t.pct) val = DD.t('{value} retention', {value: num + '%'});
    else if (o.unit === 'rmse') val = num + '%';
    else if (o.value_days) val = DD.tn('{n} day', '{n} days', a, {n: num});
    else if (o.value_pct) val = num + '%';
    else if (o.unit === 'seconds') val = DD.t('{value}s', {value: num});
    else if (o.metric_mode === 'time') val = DD.t('{value} min', {value: num});
    else val = num;
    // a day's 10-minute rows (Today, a zoom on a day): per so many minutes
    if (t.sub) return DD.tn('Trend: {value} per minute', 'Trend: {value} per {n} minutes', t.n * 10, {value: val, n: t.n * 10});
    const per = TREND_PER[o.trend_unit] || TREND_PER.day;
    return DD.tn(per[0], per[1], t.n, {value: val, n: t.n});
  }

  function trimNum(v, prec){
    let s = Number(v).toLocaleString('en-US', {minimumFractionDigits: prec, maximumFractionDigits: prec});
    if (s.indexOf('.') >= 0) s = s.replace(/0+$/, '').replace(/\.$/, '');
    return s;
  }
  // axis numbers: short units (k, M, h), as the Python side formats them
  function formatAxis(v, mode){
    v = Number(v) || 0;
    if (mode === 'percent') return trimNum(v, 0) + '%';
    if (mode === 'seconds'){
      if (v <= 0) return '0';
      if (v < 1) return trimNum(v, 1) + 's';
      let r = Math.round(v); if (Math.abs(v - Math.trunc(v) - 0.5) < 1e-9 && r % 2) r -= 1; // half to even, as Python
      return formatNum(r) + 's';
    }
    if (mode !== 'time'){
      return v >= 10 ? formatNum(Math.trunc(v + 1e-9)) : (Math.abs(v - Math.round(v)) < 1e-9 ? formatNum(v) : trimNum(v, 1));
    }
    if (v <= 0) return '0';
    if (v < 1){ const s = v * 60; return trimNum(s, s >= 10 ? 0 : 1) + 's'; }
    if (v < 60) return trimNum(v, 1) + 'm';
    const h = v / 60;
    return trimNum(h, h < 10 ? 1 : 0) + 'h';
  }
  const AXIS_FONT = '12px "Segoe UI",-apple-system,BlinkMacSystemFont,sans-serif';



  // Monotone cubic (Fritsch-Butland).
  function smoothPath(ctx, pts){
    const n = pts.length;
    ctx.moveTo(pts[0][0], pts[0][1]);
    if (n < 3){ for (let i = 1; i < n; i++) ctx.lineTo(pts[i][0], pts[i][1]); return; }
    const last = n - 1, hs = [], ds = [];
    for (let i = 0; i < last; i++){
      const hh = pts[i + 1][0] - pts[i][0];
      if (hh <= 0){ for (let j = 1; j < n; j++) ctx.lineTo(pts[j][0], pts[j][1]); return; }
      hs.push(hh); ds.push((pts[i + 1][1] - pts[i][1]) / hh);
    }
    const ms = new Array(n).fill(0);
    ms[0] = ds[0]; ms[last] = ds[last - 1];
    for (let i = 1; i < last; i++){
      const d0 = ds[i - 1], d1 = ds[i];
      if (d0 * d1 > 0){ const h0 = hs[i - 1], h1 = hs[i]; ms[i] = 3 * (h0 + h1) / ((2 * h1 + h0) / d0 + (h1 + 2 * h0) / d1); }
    }
    [[0, 0], [last, last - 1]].forEach(function(ij){ if (ds[ij[1]] === 0 || ms[ij[0]] * ds[ij[1]] < 0) ms[ij[0]] = 0; });
    for (let i = 0; i < last; i++){
      const h3 = hs[i] / 3;
      ctx.bezierCurveTo(pts[i][0] + h3, pts[i][1] + ms[i] * h3, pts[i + 1][0] - h3, pts[i + 1][1] - ms[i + 1] * h3, pts[i + 1][0], pts[i + 1][1]);
    }
  }
  function smoothK(x){ x = Math.max(0, Math.min(1, x)); return x * x * (3 - 2 * x); }
  // lighter() / darker(): scales the HSV value.
  function scaleV(hex, k){
    const [r, g, b] = (function(){ const h = String(hex || '#888888').replace('#', ''); return [0, 2, 4].map((o) => parseInt(h.substr(o, 2), 16) || 0); })();
    const mx = Math.max(r, g, b), mn = Math.min(r, g, b), d = mx - mn;
    let hh = 0;
    if (d){ if (mx === r) hh = ((g - b) / d) % 6; else if (mx === g) hh = (b - r) / d + 2; else hh = (r - g) / d + 4; }
    if (hh < 0) hh += 6;  // (red highest, blue over green: a pink came out green)
    const s = mx ? d / mx : 0; const v = Math.min(255, mx * k);
    const c = v * s, x = c * (1 - Math.abs(hh % 2 - 1)), m = v - c;
    const sec = Math.floor(((hh % 6) + 6) % 6);
    const t = [[c, x, 0], [x, c, 0], [0, c, x], [0, x, c], [x, 0, c], [c, 0, x]][sec];
    return '#' + t.map((q) => Math.round(q + m).toString(16).padStart(2, '0')).join('');
  }

  function hexToRgb(hex){
    let h = String(hex || '#888888').replace('#', '');
    if (h.length === 3) h = h.split('').map((c) => c + c).join('');
    const num = parseInt(h, 16) || 0;
    return { r: (num >> 16) & 255, g: (num >> 8) & 255, b: num & 255 };
  }
  function rgba(hex, a){
    const { r, g, b } = hexToRgb(hex);
    return `rgba(${r},${g},${b},${a})`;
  }
  // the running total as Anki draws it (.cumulative-overlay): the area already in the path is filled flat and pale in
  // the text's colour (Anki: black 3 % light, white 8 % dark), then its curve is edged with a faint dark line (black
  // 8 % / 18 %); lineK is the Total / Average Lines setting, its default (80 %) giving Anki's values; line (the Total
  // Line setting, 0-1, none by default) draws a clear line over that edge, as the charts had before
  function totalArea(ctx, pts, colors, dark, lineK, line){
    const A = DD.areaStyle(colors, dark, lineK / 0.8);
    ctx.fillStyle = rgba(A.fill, A.fillA);
    ctx.fill();
    ctx.beginPath();
    smoothPath(ctx, pts);
    ctx.lineJoin = 'round';
    ctx.strokeStyle = rgba(A.line, A.lineA);
    ctx.lineWidth = A.lw;
    ctx.stroke();
    if (line > 0){
      ctx.strokeStyle = rgba(scaleV(colors.bg || (dark ? '#000000' : '#ffffff'), dark ? 1 / 1.6 : 1), Math.min(1, 150 / 255 * lineK * line));
      ctx.lineWidth = 3.4;
      ctx.stroke();
      ctx.strokeStyle = rgba(colors.text_primary || colors.total_line || (dark ? '#ffffff' : '#000000'), Math.min(1, 215 / 255 * lineK * line));
      ctx.lineWidth = 1.3;
      ctx.stroke();
    }
  }

  function hoverFill(hex, isDark, alpha){
    const { r, g, b } = hexToRgb(hex);
    let rr, gg, bb;
    if (isDark){
      const f = 0.3; // ~lighter(130)
      rr = Math.min(255, Math.round(r + (255 - r) * f));
      gg = Math.min(255, Math.round(g + (255 - g) * f));
      bb = Math.min(255, Math.round(b + (255 - b) * f));
    } else {
      const f = 1 / 1.15; // ~darker(115)
      rr = Math.round(r * f); gg = Math.round(g * f); bb = Math.round(b * f);
    }
    return alpha == null ? `rgb(${rr},${gg},${bb})` : `rgba(${rr},${gg},${bb},${alpha})`;
  }

  function hexToHsl(hex){
    const { r, g, b } = hexToRgb(hex);
    const rn = r / 255, gn = g / 255, bn = b / 255;
    const max = Math.max(rn, gn, bn), min = Math.min(rn, gn, bn);
    let h = 0, s = 0;
    const l = (max + min) / 2;
    const d = max - min;
    if (d !== 0){
      s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
      switch (max){
        case rn: h = (gn - bn) / d + (gn < bn ? 6 : 0); break;
        case gn: h = (bn - rn) / d + 2; break;
        default: h = (rn - gn) / d + 4;
      }
      h *= 60;
    }
    return { h, s: s * 100, l: l * 100 };
  }
  function hslToRgb(h, s, l){
    s /= 100; l /= 100;
    const c = (1 - Math.abs(2 * l - 1)) * s;
    const x = c * (1 - Math.abs(((h / 60) % 2) - 1));
    const m = l - c / 2;
    let r, g, b;
    if (h < 60){ r = c; g = x; b = 0; }
    else if (h < 120){ r = x; g = c; b = 0; }
    else if (h < 180){ r = 0; g = c; b = x; }
    else if (h < 240){ r = 0; g = x; b = c; }
    else if (h < 300){ r = x; g = 0; b = c; }
    else { r = c; g = 0; b = x; }
    return { r: Math.round((r + m) * 255), g: Math.round((g + m) * 255), b: Math.round((b + m) * 255) };
  }
  function heightShadedColor(hex, ratio, isDark, alpha){
    const { h, s, l } = hexToHsl(hex);
    const lightMul = isDark ? 1.4 : 1.22;
    const darkMul = isDark ? 0.7 : 0.68;
    const lMax = Math.min(100, l * lightMul);
    const lMin = Math.max(0, l * darkMul);
    const currentL = lMax - (lMax - lMin) * Math.max(0, Math.min(1, ratio));
    const { r, g, b } = hslToRgb(h, s, currentL);
    return `rgba(${r},${g},${b},${alpha})`;
  }

  function emptyRow(label, keys){
    const row = { label: label || '', total: 0 };
    (keys || TYPE_KEYS).forEach((k) => { row[k] = 0; });
    return row;
  }

  function blendRow(fromRow, toRow, t, labelOverride, keys){
    const blended = { label: (labelOverride !== undefined ? labelOverride : toRow.label) || '' };
    ['total'].concat(keys || TYPE_KEYS).forEach((k) => {
      const fv = fromRow[k] || 0, tv = toRow[k] || 0;
      blended[k] = fv + (tv - fv) * t;
    });
    if (fromRow._exp != null || toRow._exp != null){
      const fe = fromRow._exp != null ? fromRow._exp : toRow._exp, te = toRow._exp != null ? toRow._exp : fromRow._exp;
      blended._exp = fe + (te - fe) * t;
      // a bar with no mark on one side (no data there): its mark fades out (or in) with it
      if (fromRow._exp == null || toRow._exp == null) blended._expA = fromRow._exp == null ? t : 1 - t;
    }
    // Variation: a loss is drawn under the zero line, its total kept positive; the blend goes through zero
    if (fromRow._neg || toRow._neg){
      const sg = (r) => (r._neg ? -1 : 1) * (r.total || 0), s = sg(fromRow) + (sg(toRow) - sg(fromRow)) * t;
      blended.total = Math.abs(s);
      if (s < 0) blended._neg = true;
    }
    return blended;
  }

  function interpolateBarSlots(oldCount, newCount, t, plotLeft, plotWidth, alignRight, widthRatio){
    oldCount = oldCount || 0; newCount = newCount || 0;
    const n = Math.max(oldCount, newCount);
    if (n <= 0) return [];
    const oldStep = plotWidth / Math.max(1, oldCount);
    const newStep = plotWidth / Math.max(1, newCount);
    const oldPad = alignRight ? (n - oldCount) : 0;
    const newPad = alignRight ? (n - newCount) : 0;
    const slots = [];
    for (let i = 0; i < n; i++){
      const oldSlot = alignRight ? i - oldPad : i;
      const newSlot = alignRight ? i - newPad : i;
      const oldExists = oldSlot >= 0 && oldSlot < oldCount;
      const newExists = newSlot >= 0 && newSlot < newCount;

      let oldCenter, oldWidth;
      if (oldExists){
        oldCenter = plotLeft + (oldSlot + 0.5) * oldStep;
        oldWidth = oldStep * widthRatio;
      } else {
        oldCenter = alignRight ? (plotLeft - newStep * 0.5) : (plotLeft + plotWidth + oldStep * 0.5);
        oldWidth = Math.max(1, newStep * 0.2);
      }

      let newCenter, newWidth;
      if (newExists){
        newCenter = plotLeft + (newSlot + 0.5) * newStep;
        newWidth = newStep * widthRatio;
      } else {
        newCenter = alignRight ? (plotLeft - oldStep * 0.5) : (plotLeft + plotWidth + newStep * 0.5);
        newWidth = Math.max(1, oldStep * 0.2);
      }

      const center = oldCenter + (newCenter - oldCenter) * t;
      const width = oldWidth + (newWidth - oldWidth) * t;
      slots.push([center, Math.max(1, width)]);
    }
    return slots;
  }

  // the same, from bars that were on screen at given places (a transition that starts before the last one ended:
  // the bars go on from where they are, never from a fresh layout of the in-between bar count)
  function interpolateBarSlotsFrom(oldSlots, newCount, t, plotLeft, plotWidth, alignRight, widthRatio){
    const oldCount = oldSlots.length, n = Math.max(oldCount, newCount || 0);
    if (n <= 0) return [];
    const newStep = plotWidth / Math.max(1, newCount), oldStep = plotWidth / Math.max(1, oldCount);
    const oldPad = alignRight ? (n - oldCount) : 0, newPad = alignRight ? (n - newCount) : 0;
    const out = [];
    for (let i = 0; i < n; i++){
      const os = i - oldPad, ns = i - newPad;
      const oe = os >= 0 && os < oldCount, ne = ns >= 0 && ns < newCount;
      const oc = oe ? oldSlots[os][0] : (alignRight ? plotLeft - newStep * 0.5 : plotLeft + plotWidth + oldStep * 0.5);
      const ow = oe ? oldSlots[os][1] : Math.max(1, newStep * 0.2);
      const nc = ne ? plotLeft + (ns + 0.5) * newStep : (alignRight ? plotLeft - oldStep * 0.5 : plotLeft + plotWidth + newStep * 0.5);
      const nw = ne ? newStep * widthRatio : Math.max(1, oldStep * 0.2);
      out.push([oc + (nc - oc) * t, Math.max(1, ow + (nw - ow) * t)]);
    }
    return out;
  }

  // tracer: the total line's height where the plot starts and ends (the part one sees, points past the edges are clipped)
  function edgeYs(pts, x0, x1){
    const at = (x) => { if (!pts.length) return 0; if (x <= pts[0][0]) return pts[0][1]; for (let j = 1; j < pts.length; j++) if (x <= pts[j][0]){ const f = (x - pts[j - 1][0]) / Math.max(1e-9, pts[j][0] - pts[j - 1][0]); return pts[j - 1][1] + (pts[j][1] - pts[j - 1][1]) * f; } return pts[pts.length - 1][1]; };
    return [at(x0), at(x1)];
  }

  // the gaps close when bars get only a few pixels wide (no shimmer when they move)
  function denseRatio(slotPx, ratio){
    if (slotPx >= 3) return ratio;
    if (slotPx <= 1.5) return 1;
    return ratio + (1 - ratio) * (3 - slotPx) / 1.5;
  }
  function binSize(n, adaptiveBinning){
    if (adaptiveBinning === false) return 1;
    let base;
    if (n <= 31) base = 1;
    else if (n <= 90) base = 2;
    else if (n <= 185) base = 3;
    else if (n <= 366) base = 7;
    else if (n <= 730) base = 14;
    else if (n <= 1850) base = 30;
    else if (n <= 3650) base = 60;
    else base = 90;
    return Math.max(1, Math.round(base * (SETTINGS.bin_scale / 100)));
  }

  class Chart {
    constructor(root, daily, colors, options){
      const canvas = root.querySelector('canvas');
      this.canvas = canvas;
      this.ctx = canvas.getContext('2d');
      this.colors = colors || {};
      this.options = Object.assign({
        show_breakdown: true,
        show_average: true,
        avg_on_active_days: true,
        show_cumulative: true,
        metric_mode: 'reviews',
        adaptive_binning: true,
        relative_height_transition: false,
      }, options || {});
      this.keys = this.options.keys || TYPE_KEYS; // the series of the chart (the extra charts have their own)
      this.daily = daily || [];
      this.zoomRange = null; // [absStart, absEnd) into this.daily, or null
      this.progress = 0; // initial-load reveal only, 0..1 (OutQuart, 500ms)
      this._transition = null; // { from, to, alignRight, start, duration } - see _startTransition()
      this._dragging = false;
      this._dragStartX = null;
      this._dragCurrentX = null;
      this._padL = 40; this._padR = 40;
      this._plotW = 0; this._plotH = 0;
      this._bins = []; this._binAbsRanges = [];
      this._lastRenderedBins = [];
      this.w = 1; this.h = 1;
      this._hoverIndex = null;
      this._hoverAvg = false;
      this._mouseX = null; this._mouseY = null;
      this.tooltipEl = root.querySelector('.dd-tip');
      this.avgLabelEl = root.querySelector('.dd-avg');
      this._resize();
      this._recompute();
      this._lastRenderedBins = this._bins;
      this._bindEvents();
    }

    // the axis numbers and dates: the secondary text at 175 / 255 (215 light), as every other chart draws them (they
    // were at full strength here: brighter than Retention's or Hourly's next to it)
    _axisInk(){ return rgba(this.colors.text_secondary || this.colors.axis_text || '#888888', (this.colors.is_dark ? 175 : 215) / 255); }
    // the band under the plot for the dates: a little lower on the pinned cards (short cards: the room under the
    // dates showed), as in Deep Dive elsewhere
    _padB(){ if (this.__pb == null) this.__pb = this.canvas.closest && this.canvas.closest('.ddp') ? 24 : 30; return this.__pb; }
    col(k){ return (this.options.series_colors && this.options.series_colors[k]) || this.colors[k] || '#888888'; }

    _resize(){
      if (DD.dev && (this._cam || this._transition)) DD.trace('ANIMTRACE ' + (this._traceName || 'activity') + ' resized during ' + (this._cam ? 'camera' : 'transition') + ' at ' + Math.round(performance.now()));
      const f = DD.fitCanvas(this.canvas, this.ctx), w = f.w, h = f.h, dpr = f.dpr;
      this.w = w; this.h = h;
    }

    _visibleDaily(){
      if (!this.zoomRange) return this.daily;
      return this.daily.slice(this.zoomRange[0], this.zoomRange[1]);
    }

    _visibleOffset(){
      return this.zoomRange ? this.zoomRange[0] : 0;
    }

    // one bar from its days (the same sums as the bins of _recompute)
    _binOf(chunk){
      const mode = this.options.metric_mode;
      const pct = !!(this.options.show_percent && this.options.show_breakdown);
      const hid = this.options.hidden_review_types || [];
      const KEYS = hid.length ? this.keys.filter((k) => hid.indexOf(k) < 0) : this.keys;
        const label = chunk[0].date || '';
      let total = 0;
      const byType = {};
      this.keys.forEach((k) => { byType[k] = 0; });
      chunk.forEach((d) => {
        if (pct){
          // "Show as %": each day as shares of its parts (sum 100), a bin the mean of its days
          const tk = KEYS.reduce((a, k) => a + (mode === 'time' ? (d[k + '_time_ms'] || 0) : (d[k] || 0)), 0);
          KEYS.forEach((k) => { byType[k] += tk ? (mode === 'time' ? (d[k + '_time_ms'] || 0) : (d[k] || 0)) * 100 / tk / chunk.length : 0; });
          total += tk ? 100 / chunk.length : 0;
        } else if (mode === 'time'){
          total += hid.length ? KEYS.reduce((a, k) => a + (d[k + '_time_ms'] || 0), 0) / 60000 : (d.time_ms || 0) / 60000;
          KEYS.forEach((k) => { byType[k] += (d[k + '_time_ms'] || 0) / 60000; });
        } else {
          total += hid.length ? KEYS.reduce((a, k) => a + (d[k] || 0), 0) : (d.reviews || 0);
          KEYS.forEach((k) => { byType[k] += (d[k] || 0); });
        }
      });
      const unit = this.options.unit;
      if (!pct && unit === 'level'){
        // a state at the end of the day: a bin shows its last day
        const dl = chunk[chunk.length - 1];
        total = dl.total != null ? dl.total : this.keys.reduce((a, k) => a + (dl[k] || 0), 0);
        this.keys.forEach((k) => { byType[k] = dl[k] || 0; });
      } else if (!pct && unit === 'seconds'){
        // an average: the days weighted by their reviews
        let wsum = 0, ssum = 0;
        chunk.forEach((d) => { wsum += d._reviews || 0; ssum += (d.seconds || 0) * (d._reviews || 0); });
        total = wsum ? ssum / wsum : 0;
        this.keys.forEach((k) => { byType[k] = total; });
      } else if (!pct && unit === 'rmse'){
        // an error (FSRS Loss by Fatigue): the root of the mean squared gap of its rows, weighted by their answers
        let wsum = 0, qsum = 0;
        chunk.forEach((d) => { wsum += d._reviews || 0; qsum += d._sq || 0; });
        total = wsum ? Math.sqrt(qsum / wsum) : 0;
        this.keys.forEach((k) => { byType[k] = total; });
      }
      // Variation: the bin's net change (the sum of its days' changes), a gain or a loss (drawn under the zero line)
      let neg = false;
      if (this.options.variation){
        let net = 0;
        chunk.forEach((d) => { net += (d.gain || 0) - (d.loss || 0); });
        this.keys.forEach((k) => { byType[k] = 0; });
        byType.gain = Math.max(0, net); byType.loss = Math.max(0, -net); total = Math.abs(net); neg = net < 0;
      }
      const row = { label, total };
      if (neg) row._neg = true;
      // an average of seconds (Review Speed): the reviews and the time behind it, for the hover
      if (!pct && unit === 'seconds'){
        let n = 0, ms = 0;
        chunk.forEach((d) => { n += d._reviews || 0; ms += d._ms || 0; });
        row._reviews = n; row._ms = ms;
      }
      this.keys.forEach((k) => { row[k] = byType[k]; });
      if (this.options.expected_marks && !hid.length && (!unit || unit === 'cards')){
        let exp = 0, any = false;
        chunk.forEach((d) => {
          const n = d.reviews || 0;
          if (!(n > 0) || d._pred == null) return;
          any = true;
          exp += pct ? (n - d._pred) * 100 / n / chunk.length : n - d._pred;
        });
        if (any) row._exp = Math.max(0, exp);
      }
      return row;
    }

    _recompute(){
      const visible = this._visibleDaily();
      this._subDay = visible.length > 0 && String(visible[0].date || '').length > 10;
      const offset = this._visibleOffset();
      const bs = binSize(visible.length, this.options.adaptive_binning);
      const mode = this.options.metric_mode;

      const bins = [];
      const absRanges = [];
      const pct = !!(this.options.show_percent && this.options.show_breakdown);
      const hid = this.options.hidden_review_types || [];
      const KEYS = hid.length ? this.keys.filter((k) => hid.indexOf(k) < 0) : this.keys;
      for (let i = 0; i < visible.length; i += bs){
        const chunk = visible.slice(i, i + bs);
        if (!chunk.length) continue;
        const row = this._binOf(chunk);
        bins.push(row);
        absRanges.push([offset + i, offset + Math.min(i + bs, visible.length)]);
      }

      this._bins = bins.length ? bins : [emptyRow('', this.keys)];
      this._binAbsRanges = absRanges;
      const td = trendOf(this._bins, this.options);
      this.trend = td ? {slope: td.slope, pct: td.pct, n: absRanges.length ? absRanges[0][1] - absRanges[0][0] : 1, sub: !!this._subDay} : null;
      if (this.onTrend) this.onTrend();
    }

    _trendNorm(bs){
      if (!bs || !bs.length || !this.options.show_trend) return null;
      const td = trendOf(bs, this.options);
      if (!td) return null;
      const maxV = Math.max(0, ...bs.map((b) => b.total || 0)) || 1;
      const full = td.pct ? maxV / 100 : 1;
      const nn = bs.length;
      const clamp01 = (v) => Math.max(0, Math.min(1, v));
      return [
        (td.i0 + 0.5) / nn, clamp01(td.at(td.i0) * full / maxV),
        (td.i1 + 0.5) / nn, clamp01(td.at(td.i1) * full / maxV),
      ];
    }

    _startTransition(oldBins, alignRight, ax0){
      if (DD._noAnim){ this._transition = null; this._lastRenderedBins = this._bins; return; }  // out of view during a zoom: shown as it ends
      const newBins = this._bins;
      const nextAlignRight = alignRight !== false;

      if (
        this._transition &&
        !!this._transition.alignRight === nextAlignRight &&
        JSON.stringify(this._transition.to) === JSON.stringify(newBins)
      ){
        return;
      }

      const sameCount = oldBins && newBins && oldBins.length === newBins.length && oldBins.length > 0;
      // a different set of series (e.g. "By Card Type"): the old bars split into / merge to the new segments, they do not grow from nothing
      if (oldBins && oldBins.length && this.keys && this.keys.some((k) => oldBins[0][k] === undefined)){
        const keys = this.keys, pad = nextAlignRight ? newBins.length - oldBins.length : 0;
        oldBins = oldBins.map((fr, fi) => {
          const to = newBins[Math.max(0, Math.min(newBins.length - 1, fi + pad))];
          const o = Object.assign({}, fr), tot = fr.total || 0;
          keys.forEach((k) => {
            const share = (to && (to.total || 0) > 0) ? (to[k] || 0) / to.total : 1 / keys.length;
            o[k] = tot * share;
          });
          return o;
        });
      }
      const ls = this._lastRenderedSlots;
      const fromSlots = (this._transition && ls && oldBins && ls.length === oldBins.length) ? ls : null;
      const lx = this._lastLineXs;
      const trdA = this._lastTrd ? this._lastTrd.slice() : this._trendNorm(oldBins);
      const trdB = this._trendNorm(newBins);
      this._transition = {
        fromLineXs: (this._transition && lx && oldBins && lx.length === oldBins.length) ? lx : null,
        fromSlots: fromSlots,
        from: oldBins || [],
        to: newBins,
        alignRight: nextAlignRight,
        start: null,
        trdA: trdA,
        trdB: trdB,
        ax0: ax0 || null,
        fromMeta: this._meta ? Object.assign({}, this._meta) : null,
        fromVar: !!this._varDrawn,  // the chart it starts from was drawn around a zero line (Variation)
        duration: (sameCount ? 300 : 310) * (DD.calm ? DD.calm() : 1),  // 300 ms, every chart's change (was 240)
      };
    }

    setOptions(opts){
      this._lineMixStart(opts);
      this._cam = null;
      const oldBins = this._lastRenderedBins;
      Object.assign(this.options, opts || {});
      if (opts && opts.keys) this.keys = opts.keys;
      this._recompute();
      this._startTransition(oldBins, true);
    }

    // adaptive zoom: other rows (10-minute bins or back to days) shown over
    // range, a "timespan" morph of 320 ms anchored on the side of the zoom window
    swapData(newDaily, range, alignRight, opts){
      this._cam = null;
      const oldBins = this._lastRenderedBins;
      const ax0 = this._xAxisState();
      this.daily = newDaily || [];
      if (opts) Object.assign(this.options, opts);
      if (opts && opts.keys) this.keys = opts.keys;
      const N = this.daily.length;
      this.zoomRange = (range && !(range[0] <= 0 && range[1] >= N)) ? [Math.max(0, range[0]), Math.min(N, range[1])] : null;
      this._recompute();
      this._startTransition(oldBins, alignRight, ax0);
      if (this._transition) this._transition.duration = 320;
    }

    // mode (common/zoom/transition.timespan_transition_mode): "timespan" for another period, the bars morph in
    // place anchored on the right (resolve_transition_align_right), 250 ms (animate_transition_update); else a deck
    // change, its range on other days put on the new days first
    updateData(newDaily, opts, mode){
      this._lineMixStart(opts);
      this._cam = null;
      let oldBins = this._lastRenderedBins;
      // the dates / ticks on screen: they glide or cross-fade to the new ones during the morph (_draw)
      const ax0 = this._xAxisState();
      if (mode === 'timespan'){
        this.daily = newDaily || []; this.zoomRange = null;
        if (opts) Object.assign(this.options, opts);
        if (opts && opts.keys) this.keys = opts.keys;
        this._recompute();
        this._startTransition(oldBins, true, ax0);
        if (this._transition) this._transition.duration = 310 * (DD.calm ? DD.calm() : 1);
        return;
      }
      // common/zoom/transition.rows_on_new_days: another deck's range starts / ends on other days (Total: its first
      // and last review days); morphed bar by bar, each bar would turn into another day (the whole chart wobbled
      // by a day). The old rows are put on the new days first (a day they lack counts 0): each bar only changes height.
      const od = this.daily || [], nd = newDaily || [];
      // a value axis (Answer Time's seconds, Interval Ratings' days, the n-th review...: the rows are values from the
      // same first one): each bar keeps its value, the morph goes from the bars on screen anchored on the left, as a
      // zoom (the bars widen or narrow, those past the new end slide out on the right). Put on the new rows first,
      // the old bars were laid out on the new count at once: they jumped in the first frame, then only grew
      const valueAxis = !!((opts && opts.value_axis) || this.options.value_axis);
      if (valueAxis && od.length && nd.length && od[0].date === nd[0].date && od[od.length - 1].date !== nd[nd.length - 1].date){
        this.daily = nd; this.zoomRange = null;
        if (opts) Object.assign(this.options, opts);
        if (opts && opts.keys) this.keys = opts.keys;
        this._recompute();
        this._startTransition(oldBins, false, ax0);
        return;
      }
      if (od.length && nd.length && !this._transition && (od[0].date !== nd[0].date || od[od.length - 1].date !== nd[nd.length - 1].date)){
        const by = {}; od.forEach(function(r){ if (r && r.date != null) by[r.date] = r; });
        let shared = 0;
        const aligned = nd.map(function(r){
          const o = by[r.date]; if (o){ shared++; return o; }
          const z = {}; Object.keys(r).forEach(function(k){ z[k] = typeof r[k] === 'number' ? 0 : r[k]; }); return z;
        });
        if (shared && this._windowMove(od, nd, opts)) return;
        // Deep Dive (its slower transitions): the morph goes from the bars on screen to the new ones, the whole way,
        // never from the old rows binned again on the new range (a jump at the first frame)
        if (shared && !DD._calm){
          const keep = {daily: this.daily, zoom: this.zoomRange};
          this.daily = aligned; this.zoomRange = null;
          if (opts && opts.keys) this.keys = opts.keys;
          try { this._recompute(); oldBins = this._bins; } catch (e) { this.daily = keep.daily; this.zoomRange = keep.zoom; }
        }
      }
      this.daily = newDaily || [];
      this.zoomRange = null;
      if (opts) Object.assign(this.options, opts);
      if (opts && opts.keys) this.keys = opts.keys;
      this._recompute();
      this._startTransition(oldBins, true, ax0);
    }

    // another deck's range starts / ends on another day (Total, or a range ending on its
    // last review day). The time axis moves from the old range to the new one, as one zoom, while the bars change
    // their heights: both laid on one run of days, the camera going from the old window to the new one. With daily
    // bars only (one bin size on both sides); else the bars are put on the new days (updateData).
    _windowMove(od, nd, opts){
      const oldBinsShown = this._lastRenderedBins, ax0 = this._xAxisState();
      if (DD._noAnim || this.zoomRange || this._cam || this.progress < 1 || this._padL == null || this.canvas.width <= 1) return false;
      if (this.options.variation || this._varDrawn) return false;  // the camera draws no zero line (see _zoomTo)
      if (od.length < 2 || nd.length < 2) return false;
      const ad = this.options.adaptive_binning;
      if (binSize(od.length, ad) !== 1 || binSize(nd.length, ad) !== 1) return false;
      const t = function(r){ const v = Date.parse(r.date); return isNaN(v) ? null : v; };
      const seen = {}, all = [];
      od.concat(nd).forEach(function(r){ const v = t(r); if (v == null || seen[r.date]) return; seen[r.date] = v; all.push(r.date); });
      if (all.length !== Object.keys(seen).length) return false;
      all.sort(function(x, y){ return seen[x] - seen[y]; });
      const DAY = 86400000;
      for (let i = 1; i < all.length; i++){ if (Math.round((seen[all[i]] - seen[all[i - 1]]) / DAY) !== 1) return false; }  // one run of days
      const zero = function(r){ const z = {}; Object.keys(r).forEach(function(k){ z[k] = typeof r[k] === 'number' ? 0 : r[k]; }); return z; };
      const bo = {}, bn = {}; od.forEach(function(r){ bo[r.date] = r; }); nd.forEach(function(r){ bn[r.date] = r; });
      const tmpl = nd[0];
      const oldU = all.map(function(d){ return bo[d] || Object.assign(zero(tmpl), {date: d}); });
      const newU = all.map(function(d){ return bn[d] || Object.assign(zero(tmpl), {date: d}); });
      const a0 = all.indexOf(od[0].date), b0 = all.indexOf(nd[0].date);
      const wa = [a0, a0 + od.length], wb = [b0, b0 + nd.length], N = all.length;
      // the old chart on the run of days (its window shows exactly what was drawn), then the camera to the new window
      if (opts) Object.assign(this.options, opts);
      if (opts && opts.keys) this.keys = opts.keys;
      this._transition = null;
      this.daily = oldU; this.zoomRange = (wa[0] <= 0 && wa[1] >= N) ? null : wa; this._recompute(); this._lastRenderedBins = this._bins;
      const shownBefore = oldBinsShown || this._bins;  // what was on screen (the fallback below starts from it)
      this.daily = newU;
      this._camLerp = {from: oldU, to: newU, final: nd, done: false};
      this._zoomTo(wb[0] <= 0 && wb[1] >= N ? null : wb);
      if (!this._cam){ this._camLerp = null; this.daily = nd; this.zoomRange = null; this._recompute(); this._startTransition(shownBefore, true, ax0); return true; }  // no camera: a morph from the bars that were shown (it started from the new ones: no animation)
      // the running total's scale: from the old window's total (the old deck's), not the new deck's on the old days
      let ta = 0; for (let i = wa[0]; i < wa[1]; i++) ta += this._binOf([oldU[i]]).total || 0;
      this._cam.ta = Math.max(1, ta);
      return true;
    }
    _endWindowMove(){
      const L = this._camLerp; this._camLerp = null;
      this.daily = L.final; this.zoomRange = null; this._recompute(); this._lastRenderedBins = this._bins;
    }

    zoomToBinRange(i0, i1){
      if (this._zoomDisabled) return;
      if (!this._binAbsRanges.length) return;
      i0 = Math.max(0, Math.min(this._binAbsRanges.length - 1, i0));
      i1 = Math.max(0, Math.min(this._binAbsRanges.length - 1, i1));
      if (i1 < i0){ const t = i0; i0 = i1; i1 = t; }
      const absStart = this._binAbsRanges[i0][0];
      const absEnd = this._binAbsRanges[i1][1];
      if (absEnd - absStart < 2) return; // avoid degenerate zoom

      this._zoomTo([absStart, absEnd]);
      if (this.onZoom) this.onZoom();
    }

    wheelZoom(centerIdx, dir){
      if (this._zoomDisabled) return;
      if (!this._binAbsRanges.length || !this.daily.length) return;
      const total = this.daily.length;
      const curStart = this.zoomRange ? this.zoomRange[0] : 0;
      const curEnd = this.zoomRange ? this.zoomRange[1] : total;
      const span = curEnd - curStart;

      // Wheel zoom: 15% a step, at least 3 rows, the row under the cursor stays put
      const range = this._binAbsRanges[Math.max(0, Math.min(this._binAbsRanges.length - 1, centerIdx))];
      const cursorIdx = range ? Math.max(curStart, Math.min(curEnd - 1, range[0])) : Math.floor((curStart + curEnd) / 2);
      if (dir < 0 && span >= total){ if (this.onZoomOutLimit) this.onZoomOutLimit(); return; }  // zoom_out_limit
      const zf = 0.15;
      const newSpan = dir > 0
        ? Math.max(3, Math.floor(span * (1 - zf)))
        : Math.min(total, Math.max(span + 1, Math.floor(span * (1 + zf))));
      if (newSpan === span) return;
      const ratio = span > 0 ? (cursorIdx - curStart) / span : 0.5;
      let newStart = Math.floor(cursorIdx - ratio * newSpan);
      let newEnd = newStart + newSpan;
      if (newStart < 0){ newStart = 0; newEnd = newSpan; }
      if (newEnd > total){ newEnd = total; newStart = Math.max(0, newEnd - newSpan); }

      // the zoom set at once, no camera (only a drag zone zooms with it)
      // the charts linked to it follow at once too (zoom_sync sets their range the same way)
      const prev = DD._noAnim; DD._noAnim = true;
      try { this._zoomTo([newStart, newEnd]); if (this.onZoom) this.onZoom(); } finally { DD._noAnim = prev; }
    }

    // Shift+wheel: slide the zoom window by a tenth of it
    panZoom(dir){
      if (this._zoomDisabled) return;
      if (!this.zoomRange) return;
      const total = this.daily.length, span = this.zoomRange[1] - this.zoomRange[0];
      // a tenth of the view, whole bins
      const bst = this.options.adaptive_binning !== false ? binSize(span, true) : 1;
      const step = (bst > 1 ? Math.max(bst, Math.floor(Math.round(span * 0.1) / bst) * bst) : Math.max(1, Math.round(span * 0.1))) * (dir > 0 ? -1 : 1);
      let a = this.zoomRange[0] + step, b = a + span;
      if (a < 0){ a = 0; b = span; }
      if (b > total){ b = total; a = total - span; }
      const prev = DD._noAnim; DD._noAnim = true;  // handle_wheel_pan: at once, the linked charts with it
      try { this._zoomTo([a, b]); if (this.onZoom) this.onZoom(); } finally { DD._noAnim = prev; }
    }

    _marginsFor(bins){
      const ctx = this.ctx;
      ctx.font = AXIS_FONT;
      const isPct = !!(this.options.show_percent && this.options.show_breakdown);
      const mode = isPct ? 'percent' : this.options.metric_mode;
      const showCum = this.options.show_cumulative && !isPct && this.options.has_cumulative !== false;
      const totals = (bins || []).map((b) => b.total || 0);
      const mx = Math.max.apply(null, totals.concat([0])) || 1;
      let lw = 0;
      for (let g = 0; g <= 4; g++) lw = Math.max(lw, ctx.measureText(formatAxis(mx * g / 4, mode)).width);
      let r = 20;
      const sum = totals.reduce((a, b) => a + b, 0) || 1;
      if (showCum){
        let rw = 0;
        for (let g = 0; g <= 4; g++) rw = Math.max(rw, ctx.measureText(formatAxis(sum * g / 4, mode)).width);
        r = Math.max(20, Math.round(rw) + 10);
      }
      return {padL: Math.max(35, Math.round(lw) + 12), padR: r, cumTop: sum};
    }

    // ---- zoom camera: the chart is drawn on a moving window of days for 300 ms
    // (OutQuad), the window zooming about the point that stays still; the axis glides like a camera; the bars keep
    // the start bin size, then split (or merge) into the end one; labels: the old fade out, then the new fade in.
    _zoomTo(range){
      const N = this.daily.length;
      // with adaptive binning a zoom window starts and ends on the bin grid of its size
      // (multiples of the bin from the first day), so its bars are the same bars the zoom camera draws: no bar
      // regrouped or cut at the start or the end of a zoom, none at once while it runs
      if (range && this.options.adaptive_binning !== false){
        let s0 = Math.max(0, Math.round(range[0])), e0 = Math.min(N, Math.round(range[1])), st = 1;
        for (let it = 0; it < 3; it++){  // snapped, the window may need the next bin size: snapped again on that one
          st = binSize(Math.max(1, e0 - s0), true);
          if (st <= 1) break;
          s0 -= s0 % st; if (e0 % st) e0 += st - (e0 % st); e0 = Math.min(N, e0);
          if (s0 >= e0) s0 = Math.max(0, e0 - st);
          if (binSize(Math.max(1, e0 - s0), true) === st) break;
        }
        if (e0 - s0 < Math.max(2, st)) return;
        range = [s0, e0];
      }
      const nr = (!range || (range[0] <= 0 && range[1] >= N)) ? null : [range[0], range[1]];
      const pct = !!(this.options.show_percent && this.options.show_breakdown);
      const still = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      const c0 = this._cam;
      const a = c0 && c0.cur ? c0.cur.slice() : (this.zoomRange ? this.zoomRange.slice() : [0, N]);
      const oldBins = this._bins || [];
      const tot = (bs) => bs.map((r) => r.total || 0);
      const avgOf = (bs) => { const v = tot(bs); const rel = this.options.avg_on_active_days ? v.filter((x) => x > 0) : v; return rel.length ? rel.reduce((x, y) => x + y, 0) / rel.length : 0; };
      const ma = c0 && c0.curMx ? c0.curMx : (Math.max.apply(null, tot(oldBins).concat([0])) || 1);
      const ra = c0 && c0.curR != null ? c0.curR : avgOf(oldBins) / ma;
      const trendNorm = (bs, mxv) => {
        const td = trendOf(bs, this.options);
        if (!td || !bs.length) return null;
        const n = bs.length, full = td.pct ? Math.max(0, ...tot(bs)) / 100 : 1;
        return [(td.i0 + 0.5) / n, Math.max(0, Math.min(1, td.at(td.i0) * full / mxv)),
                (td.i1 + 0.5) / n, Math.max(0, Math.min(1, td.at(td.i1) * full / mxv))];
      };
      const trdA = (c0 && c0.curTrd) ? c0.curTrd.slice() : (this._lastTrd ? this._lastTrd.slice() : trendNorm(oldBins, ma));
      // Variation (or a change from it): its bars morph instead, about the zero line. The camera draws them up from
      // the bottom and would show the losses as gains until the zoom ends
      const signed = !!this.options.variation || !!this._varDrawn;
      const canCam = !still && !DD._noAnim && !pct && !signed && this._padL != null && this.canvas.width > 1 && this.progress >= 1;
      const g0 = {padL: this._padL, padR: this._padR}, cumTop0 = this._cumTop, ax0 = this._xAxisState();
      this.zoomRange = nr;
      this._recompute();
      const b = nr ? nr.slice() : [0, N];
      if (!canCam || DD._noAnim || DD.noZoomAnim || (a[0] === b[0] && a[1] === b[1])){
        if (DD.dev) DD.trace('ANIMTRACE total ' + (this._traceName || 'activity') + ' zoom ' + a.map(Math.round) + ' -> ' + b.map(Math.round) + ' of ' + N + ' days: no camera, a bar morph (' + (!canCam ? 'no camera: progress=' + (+this.progress).toFixed(2) + ' pct=' + pct + ' signed=' + signed : (DD._noAnim ? 'noAnim' : (DD.noZoomAnim ? 'noZoomAnim' : 'same window'))) + ')');  // ANIMTRACE
        this._cam = null;
        this._startTransition(this._lastRenderedBins, true, ax0);
        return;
      }
      const mb = Math.max.apply(null, tot(this._bins).concat([0])) || 1;
      const m1 = this._marginsFor(this._bins);
      this._transition = null;
      this._lastRenderedBins = this._bins;
      this._cam = {a: a, b: b, g0: g0, g1: {padL: m1.padL, padR: m1.padR}, ma: ma, mb: mb, ra: ra, rb: avgOf(this._bins) / mb,
        trdA: trdA, trdB: trendNorm(this._bins, mb), start: null, k: DD.calm ? DD.calm() : 1, _binCache: new Map(),
        ka: binSize(Math.max(1, Math.round(a[1] - a[0])), this.options.adaptive_binning), kb: binSize(b[1] - b[0], this.options.adaptive_binning),
        zoomIn: b[0] >= a[0] - 1e-6 && b[1] <= a[1] + 1e-6};
      // the chart draws a last, shorter bin as a whole bar: the camera's windows are padded to
      // whole bins so its first frame is the old chart and its last the new one exactly (no last bar cut, then back)
      { const C = this._cam, pad = (w, k) => [w[0], w[0] + Math.ceil(Math.round((w[1] - w[0]) * 1e6) / 1e6 / k) * k];
        C.pa = c0 ? a.slice() : pad(a, C.ka); C.pb = pad(b, C.kb); C.ea = c0 ? null : a[1]; C.eb = b[1];
        // a zoom taking over from one still running starts from the bars it was drawing (same bin size, same grid):
        // a new grid there moved the running total's start by a whole bar at once
        if (c0 && c0.lastK){ C.ka = c0.lastK; C.aAnchor = c0.lastAn; } }
      const pre = (c0 && c0.pre && c0.pre.length === N + 1 && !this._camLerp) ? c0.pre : (() => {
        const p = [0]; let run = 0; this.daily.forEach((d) => { run += this._binOf([d]).total || 0; p.push(run); }); return p;
      })();
      const wt = (w) => { const i0 = Math.max(0, Math.floor(w[0])), i1 = Math.min(N, Math.ceil(w[1])); return i1 > i0 ? pre[i1] - pre[i0] : 0; };
      // the running total's camera (_camDraw): the counts since the first day, its base at the start chart's left edge
      // (a zoom taking over: the base on screen)
      this._cam.pre = pre;
      { const cAt = (x) => { x = Math.max(0, Math.min(N, x)); const i = Math.min(N - 1, Math.floor(x)); return i < 0 ? 0 : pre[i] + (pre[i + 1] - pre[i]) * (x - i); };
        this._cam.baseA = (c0 && c0.curBase != null) ? c0.curBase : cAt(a[0]); this._cam.baseB = cAt(b[0]); }
      // a zoom that takes over from one still running: the total line's scale goes on from the one on screen (no jump of the line)
      this._cam.ta = Math.max(1, (c0 && c0.curTop) || cumTop0 || wt(a)); this._cam.tb = Math.max(1, m1.cumTop || wt(b));
      if (DD.dev) DD.trace('ANIMTRACE total ' + (this._traceName || 'activity') + ' zoom camera ' + a.map(Math.round) + ' -> ' + b.map(Math.round) + ' of ' + N + ' days, padded ' + this._cam.pa.map(Math.round) + ' -> ' + this._cam.pb.map(Math.round) + ' bins ' + this._cam.ka + ' -> ' + this._cam.kb + ' | total top ' + Math.round(this._cam.ta) + ' -> ' + Math.round(this._cam.tb) + (c0 ? ' (took over a running zoom, its top ' + Math.round(c0.curTop || 0) + ')' : ''));  // ANIMTRACE
    }

    _camDraw(now){
      const c = this._cam, ctx = this.ctx, W = this.w, H = this.h, cv = this.canvas;
      if (c.start === null) c.start = now;
      if (c.len == null){ const A = c.pa || c.a, B = c.pb || c.b; c.len = DD.zoomLen ? DD.zoomLen(A[1] - A[0], B[1] - B[0]) : 1; }
      const t = Math.min(1, playClock(c, now) / (300 * (c.k || 1) * c.len));
      if (t >= 1){ this._cam = null; if (this._camLerp) this._camLerp.done = true; return false; }
      const sm = (x) => { x = Math.max(0, Math.min(1, x)); return x * x * (3 - 2 * x); };
      const e = (DD.zoomCam && DD.zoomCam.ease) ? DD.zoomCam.ease(t) : sm(t);
      if (this._camLerp){  // a deck change on the move (_windowMove): the bars change height as the window goes
        const L = this._camLerp, ee = e;
        this.daily = L.to.map(function(r, i){ const f = L.from[i] || {}, o = Object.assign({}, r); Object.keys(r).forEach(function(k){ if (typeof r[k] === 'number') o[k] = (+f[k] || 0) + (r[k] - (+f[k] || 0)) * ee; }); return o; });
      }
      const N = this.daily.length;
      // the camera's moves are the shared zoom camera's (zoom_camera.js): its window, the bars' split, their layers
      const Z = DD.zoomCam;
      // window of the camera
      let [v0, v1] = Z.path(c.pa || c.a, c.pb || c.b, e);
      v0 = Math.max(0, v0); v1 = Math.min(Math.max(N, (c.pa || c.a)[1], (c.pb || c.b)[1]), v1);
      if (v1 - v0 < 1e-3){ this._cam = null; return false; }
      c.cur = [v0, v1]; this._drawnV = [v0, v1]; this._yaxL = {}; this._yaxR = {};
      const padT = 10, padB = this._padB();
      const ml = c.g0.padL + (c.g1.padL - c.g0.padL) * e, mr = c.g0.padR + (c.g1.padR - c.g0.padR) * e;
      const plotW = Math.max(1, W - ml - mr), plotH = Math.max(1, H - padT - padB), bottom = padT + plotH;
      const sc = DD.canvasScale(cv, W, H), dpr = sc[0], dpy = sc[1];
      ctx.save(); ctx.setTransform(dpr, 0, 0, dpy, 0, 0); ctx.clearRect(0, 0, W, H);
      // axis numbers, dates, stats: the old ones fade out, then the new ones fade in (never both at once)
      const fo = 1 - sm(t / 0.3), fn = sm((t - 0.2) / 0.3);
      // (web: the axis numbers are not in the fade: they count from the old scale to the new one, drawn below)
      // from just under the plot: the dates are centred 10 px under it (from 7 px, their tops were cut while zooming)
      ctx.save(); ctx.beginPath(); ctx.rect(0, bottom + 2, W, Math.max(0, H - bottom - 2)); ctx.clip();
      if (this.daily.length && this._sub()) this._drawTimes(ctx, v0, v1, ml, ml + plotW, H - padB + 10);
      else if (this.daily.length){
        // the dates move with the view (both axis animations: it read better than their fade); the marks of the start
        // step and of the end one, those in both stay, the start's others leave, the end's others come
        const [a0, a1] = c.pa || c.a, [b0, b1] = c.pb || c.b;
        const sa = this._dayStep(a0, a1, plotW), sb = this._dayStep(b0, b1, plotW);
        const A = this._dayTicks(v0, v1, sa), B = sa === sb ? A : this._dayTicks(v0, v1, sb), inB = new Set(B), inA = new Set(A), marks = [];
        A.forEach((i) => { const kept = inB.has(i); marks.push({i: i, a: kept ? 1 : 1 - sm(e / 0.67), p: kept ? 2 : 1 - e}); });
        B.forEach((i) => { if (!inA.has(i)) marks.push({i: i, a: sm((e - 0.33) / 0.67), p: e}); });
        this._drawDays(ctx, marks, (x) => ml + (x - v0) / (v1 - v0) * plotW, ml, ml + plotW, H - padB + 10);
      } else {
        if (fo > 0.001){ ctx.globalAlpha = fo; ctx.drawImage(c.from, 0, 0, W, H); }
        if (fn > 0.001){ ctx.globalAlpha = fn; ctx.drawImage(c.to, 0, 0, W, H); }
      }
      ctx.restore();
      ctx.save(); ctx.beginPath(); ctx.rect(ml, 0, plotW, bottom + 1); ctx.clip();
      ctx.strokeStyle = this.options.show_grid === false ? 'rgba(0,0,0,0)' : (this.colors.grid || 'rgba(128,128,128,0.12)'); ctx.lineWidth = 1;
      // Chart_Axis_Anim 'slide': the grid lines at the round values, sliding with the zoom's scale (the numbers below)
      const slideAx = !!(DD.axisSlide && DD.axisSlide());
      const camTicks = slideAx ? DD.slideTicks(c.ma, c.mb, Math.exp(Math.log(c.ma) + (Math.log(c.mb) - Math.log(c.ma)) * e), e, 4, plotH, {tag: (this._traceName || 'activity') + ' zoom'}) : null;
      if (camTicks) camTicks.forEach((k) => { const y = padT + plotH * (1 - k.f); ctx.globalAlpha = k.a; ctx.beginPath(); ctx.moveTo(ml, y); ctx.lineTo(ml + plotW, y); ctx.stroke(); });
      else for (let g = 0; g <= 4; g++){ const y = padT + plotH * (1 - g / 4); ctx.beginPath(); ctx.moveTo(ml, y); ctx.lineTo(ml + plotW, y); ctx.stroke(); }
      ctx.globalAlpha = 1;
      // bars: start bin size, then the end one (_split_state); heights scaled to a bin size gliding from one to the other
      const ka = c.ka, kb = c.kb, kf = Math.min(ka, kb), kc = Math.max(ka, kb);
      const unit = this.options.unit, avgUnit = unit === 'seconds' || unit === 'level' || unit === 'rmse';
      const kg = Z.lerpLog(ka, kb, e);
      // the bars' split or merge between the two sizes (null: one size); the split's start kept on c (c.tSplit)
      const sp = Z.split(c, ka, kb, c.a, c.b, t, e, v1 - v0, plotW);
      const mx = Z.lerpLog(c.ma, c.mb, e);
      c.curMx = mx; this._axY = {max: mx, mode: this.options.metric_mode};
      const showBreakdown = this.options.show_breakdown;
      const opacityFrac = Math.max(0, Math.min(100, this.options.chart_opacity_pct != null ? this.options.chart_opacity_pct : 71)) / 100;
      const hid = this.options.hidden_review_types || [];
      const KEYS = hid.length ? this.keys.filter((k) => hid.indexOf(k) < 0) : this.keys;
      // the bins on the grid of the first day, as the zoom windows are (see _zoomTo)
      const anchorOf = (k) => (this.options.adaptive_binning !== false) ? 0 : (k === kb ? c.b[0] : (k === ka ? (c.aAnchor != null ? c.aAnchor : c.a[0]) : 0));
      const endOf = (k) => k === kb ? c.eb : (k === ka ? c.ea : null);
      // a bin cut by the view's side: the rate of its days still in view (each day by its share in view) over the whole
      // bin, not its count with the days off screen. On a skewed chart (Rating by Interval) a whole count
      // kept for a sliver of a bin is clipped at the top for the whole zoom. Whole in view, a bin is its count (the start and end charts')
      const pctBars = !!(this.options.show_percent && this.options.show_breakdown);
      const binWhole = (r0, r1) => {
        if (!this._camLerp && c._binCache){
          const key = r0 + ':' + r1;
          let hit = c._binCache.get(key);
          if (!hit){ hit = this._binOf(this.daily.slice(r0, r1)); c._binCache.set(key, hit); }
          return hit;
        }
        return this._binOf(this.daily.slice(r0, r1));
      };
      const rowIn = (r0, r1) => {
        const a = Math.max(r0, v0), b = Math.min(r1, v1);
        if (avgUnit || pctBars || (a <= r0 + 1e-9 && b >= r1 - 1e-9) || b - a <= 1e-6) return binWhole(r0, r1);
        const chunk = [];
        for (let i = Math.floor(a); i < Math.ceil(b); i++){
          const d = this.daily[i], w = Math.min(i + 1, b) - Math.max(i, a);
          if (!d || w <= 0) continue;
          const o = {}; Object.keys(d).forEach((key) => { o[key] = typeof d[key] === 'number' ? d[key] * w : d[key]; });
          chunk.push(o);
        }
        if (!chunk.length) return binWhole(r0, r1);
        const row = this._binOf(chunk), f = (r1 - r0) / (b - a), out = {};
        Object.keys(row).forEach((key) => { const v = row[key]; out[key] = (typeof v === 'number' && key !== 'label') ? v * f : v; });
        return out;
      };
      const binsAt = (k, an0, end0) => {
        const an = an0 != null ? an0 : anchorOf(k), out = [];
        let r = an + Math.floor((v0 - an) / k) * k;
        // the bin across the end of its own window holds only that window's days (the shorter bin of the chart)
        const end = end0 !== undefined ? end0 : endOf(k);
        for (; r < v1; r += k){
          const r0 = Math.max(0, r); let r1 = Math.min(N, r + k);
          if (end != null && r < end && r + k > end) r1 = Math.min(r1, Math.round(end));
          if (r1 <= r0) continue;
          out.push({r: r, k: k, row: rowIn(r0, r1)});
        }
        return out;
      };
      const scaleRow = (r, f) => { const o = {}; Object.keys(r).forEach((key) => { const v = r[key]; o[key] = (typeof v === 'number' && key !== 'label') ? v * f : v; }); return o; };
      // the fine bars split out of their parent: tiled on the parent bar at w = 0, at their
      // own place and value at w = 1
      const drawSplit = (g, wsp, hsp) => {
        if (hsp == null) hsp = wsp;
        const span = v1 - v0, toX = (x) => ml + (x - v0) / span * plotW;
        const slotF = kf / span * plotW, rF = denseRatio(slotF, this._baseRatio()), rC = denseRatio(slotF * kc / kf, this._baseRatio());
        const fC = avgUnit ? 1 : kg / kc, fF = avgUnit ? 1 : kg / kf, ac = anchorOf(kc), endC = endOf(kc);
        const parents = {}; binsAt(kc).forEach((it) => { parents[it.r] = it; });
        const groups = new Map(), af = anchorOf(kf), endF = endOf(kf);
        binsAt(kf).forEach((it) => {
          const rc = ac + Math.floor((it.r + kf / 2 - ac) / kc) * kc;
          if (!groups.has(rc)) groups.set(rc, []); groups.get(rc).push(it);
        });
        groups.forEach((members, rc) => {
          const par = parents[rc];
          const p0 = rc, p1 = Math.min(N, rc + kc, endC != null && rc < endC && rc + kc > endC ? Math.round(endC) : Infinity);
          // the tiles count every fine bin of the parent, those out of view too: counted from the visible ones, a
          // parent cut by the plot's side had wider tiles that slid as the view moved (zoom trace: w5 by w4.1)
          const first = af + Math.ceil((rc - kf / 2 - af) / kf) * kf;
          const all = [];
          for (let r = first; r + kf / 2 < rc + kc; r += kf){
            let r1 = Math.min(N, r + kf); if (endF != null && r < endF && r + kf > endF) r1 = Math.min(r1, Math.round(endF));
            if (r1 > Math.max(0, r)) all.push(r);
          }
          const pw = (p1 - p0) * rC, left = (p0 + p1) / 2 - pw / 2, m = Math.max(all.length, members.length);
          members.forEach((it, i) => {
            let t = all.length >= members.length ? all.findIndex((r) => Math.abs(r - it.r) < 1e-6) : -1;
            if (t < 0) t = i;
            const own = scaleRow(it.row, fF), row = par ? {} : own;
            if (par){ const pr = scaleRow(par.row, fC); Object.keys(own).forEach((key) => { const a = pr[key], b = own[key]; row[key] = (typeof b === 'number' && key !== 'label') ? (a || 0) + (b - (a || 0)) * hsp : b; }); }
            const tx = left + t * pw / m, tw = pw / m, ox = it.r + kf * (1 - rF) / 2, ow = kf * rF;
            const x0 = toX(tx + (ox - tx) * wsp), x1 = toX(tx + (ox - tx) * wsp + tw + (ow - tw) * wsp);
            if (x0 > ml + plotW || x1 < ml) return;
            // close sub-pixel hairline seams between adjacent tiles right as they fuse into the parent bar
            const seam = (wsp < 0.25 && i < members.length - 1) ? 0.6 * (1 - wsp / 0.25) : 0;
            edgeBar(g, row, x0, Math.max(0.5, x1 - x0 + seam));
          });
        });
      };
      // a bar going out of the plot (or coming in) by its side: faded by the share of its width still in, else a thin
      // sliver of it at the edge shows its whole height for a frame, a different bar's at each frame (a flicker)
      const edgeBar = (g, row, x0, w) => Z.edge(g, ml, plotW, x0, w, () => {
        this._paintBar(g, row, x0, w, bottom, plotH, mx, mx, 1);
        if (row._exp != null && row.total > 0 && this.options.show_breakdown) this._expMark(g, x0, w, bottom - Math.min(1, row._exp / mx) * plotH);
      });
      const drawLayer = (g, k, an, end, wsp, hsp) => {
        if (wsp != null && kf !== kc && k === kf) return drawSplit(g, wsp, hsp);
        const f = avgUnit ? 1 : kg / k, bw = k / (v1 - v0) * plotW, ratio = denseRatio(bw, this._baseRatio()), barW = Math.max(1, bw * ratio);
        binsAt(k, an, end).forEach((it) => {
          const x = ml + (it.r - v0) / (v1 - v0) * plotW + (bw - barW) / 2;
          if (x > ml + plotW || x + barW < ml) return;
          const row = {};
          Object.keys(it.row).forEach((key) => { const v = it.row[key]; row[key] = (typeof v === 'number' && key !== 'label') ? v * f : v; });
          const sb = [x, barW];  // antialiased, never rounded: same size in motion and at rest
          edgeBar(g, row, sb[0], sb[1]);
          if (this._tr && g === ctx){ const vis = Math.min(sb[0] + sb[1], ml + plotW) - Math.max(sb[0], ml); if (vis > 0.5){ this._tr.bl = [sb[0], sb[1]]; this._tr.bn = (this._tr.bn || 0) + 1; this._tr.lh = Math.min(1, (row.total || 0) / mx) * plotH; this._tr.lr = Math.min(sb[0] + sb[1], ml + plotW); } }
        });
      };
      this._moving = true;
      // the bars' layers (zoom_camera.js split / mix): past the start the fine bars come out of their coarse parent bar,
      // never faded in at their own place; merging back, the same the other way
      // the layers: [bin size, weight, anchor, end, split width, split height]
      let layers = !sp ? [[kf, 1]] : Z.mix(sp).map((m) => (m.fine ? (m.split && !this.options.line_view ? [kf, m.w, undefined, undefined, sp.wsp, sp.hsp] : [kf, m.w]) : [kc, m.w]));  // (the line view: no bars coming out of their parent, the two lines cross-fade)
      // same bin size, but the start window's bins do not fall on the end one's (a zoom by a step that is not a whole
      // number of bins): the old grouping fades into the new one, the first frame is the old chart, no bar regrouped at once
      if (kf === kc && kf > 1){
        const aa = c.aAnchor != null ? c.aAnchor : c.a[0], sh = (((aa - c.b[0]) % kf) + kf) % kf;
        if (sh > 1e-6 && sh < kf - 1e-6){ const w = sm((e - 0.05) / 0.6); layers = [[kf, 1 - w, aa, c.ea], [kf, w, c.b[0], c.eb]]; }
      }
      { const dom = layers.reduce((a2, L) => (L[1] > a2[1] ? L : a2), layers[0]); c.lastK = dom[0]; c.lastAn = dom[2] != null ? dom[2] : anchorOf(dom[0]); }
      // one layer drawn on the chart, else the layers mixed on a clear surface first (Plus composition), then laid on it
      Z.composite(c, ctx, cv, dpr, dpy, layers.filter((L) => L[1] > 0.002), (g, L) => { this._lineBegin(); drawLayer(g, L[0], L[2], L[3], L[4], L[5]); this._lineFlush(g, ml, ml + plotW); });
      const isDark = !!this.colors.is_dark, lineK = (this.options.line_opacity_pct != null ? this.options.line_opacity_pct : 80) / 100;
      // trend line (Show Trend): glides smoothly from the start window's trend to the end one during camera zoom / timespan
      if (this.options.show_trend && (c.trdA || c.trdB)){
        const ta = c.trdA, tb = c.trdB;
        let tp, tAlpha = 1;
        if (ta && tb){
          tp = [ta[0] + (tb[0] - ta[0]) * e, ta[1] + (tb[1] - ta[1]) * e,
                ta[2] + (tb[2] - ta[2]) * e, ta[3] + (tb[3] - ta[3]) * e];
        } else if (ta){ tp = ta; tAlpha = 1 - e; }
        else { tp = tb; tAlpha = e; }
        c.curTrd = tp;
        this._lastTrd = tp;
        if (tAlpha > 0.01){
          const x0 = ml + tp[0] * plotW, y0 = bottom - tp[1] * plotH;
          const x1 = ml + tp[2] * plotW, y1 = bottom - tp[3] * plotH;
          const bgc = this.colors.bg || (isDark ? '#000000' : '#ffffff'), lw = H < 200 ? 1 : 1.2;
          const seg = () => { ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(x1, y1); ctx.stroke(); };
          ctx.save(); ctx.lineCap = 'round';
          ctx.strokeStyle = rgba(isDark ? scaleV(bgc, 1 / 1.6) : bgc, 70 / 255 * tAlpha); ctx.lineWidth = lw + 1.2; seg();
          ctx.strokeStyle = rgba(scaleV(this.colors.total_line, isDark ? 1.35 : 1 / 1.25), 150 / 255 * lineK * tAlpha); ctx.lineWidth = lw; seg();
          ctx.restore();
        }
      }
      // running total: the real counts (never the rescaled bars), its scale gliding from the start window total to the end one
      if (this.options.show_cumulative && this.options.has_cumulative !== false){
        // each layer's running total restarts at
        // the left edge of the view (a bin half out of view counts half), its top is what is in view, kept at least at
        // the camera glide; the layers' heights are mixed by their shares; the line is flat past its ends
        // (web: the glide goes from the start chart's own scale to the end chart's and is never let go: a scale that
        // follows what is in view makes the line's end leap at the end of the zoom, or rise and fall back on a zoom out)
        const glide = Z.lerpLog(c.ta, c.tb, e), wgt = 1;
        const interp = (vals, x) => { const n = vals.length; if (!n) return 0; if (x <= 0) return vals[0]; if (x >= n - 1) return vals[n - 1]; const i = Math.floor(x); return vals[i] + (vals[i + 1] - vals[i]) * (x - i); };
        // (web: the line is one curve seen through a camera: the counts since the first day, less a base gliding from
        // the start chart's left edge count to the end chart's, on the glide's scale. Its end held at the top by what is
        // in view, a zoom out that takes in busy days last let the line's right end sink 56 px under the top, then leap
        // back up in 3 frames as those days came in. Not for averages (no running count) nor a deck change on the move)
        const camLine = !!c.pre && !avgUnit && !this._camLerp && c.baseA != null && c.baseB != null;
        // the counts' window [base, base + scale] zooms as the view's days do (a point that stays,
        // the width gliding): the base moved straight while the scale glided, 4 frames into a zoom out the line rose
        // to the top (283 -> 15 px from the top), then came back down to 152
        let base0 = null;
        if (camLine) base0 = Z.glide(c.baseA, c.baseB, c.ta, c.tb, glide, e);
        c.curBase = base0;
        const lineOf = (k, an, end) => {
          const its = binsAt(k, an, end); if (!its.length) return null;
          let run = 0; const vals = its.map((it) => (run += it.row.total || 0));
          const off = (v0 - its[0].r) / k, view = (v1 - v0) / k, last = off + view - 1;
          if (camLine){
            const ref = c.pre[Math.max(0, Math.min(N, Math.round(its[0].r)))] - base0, stepC = view > 1 ? plotW / (view - 1) : 0;
            return {pts: vals.map((v, i) => [ml + (i - off) * stepC, v + ref]), top: glide};
          }
          const base = interp([0].concat(vals), off);
          let top = Math.max(1e-9, interp(vals, last) - base);
          const steady = Math.max(glide, top);
          top = wgt >= 1 ? steady : (wgt > 0 ? Math.exp(wgt * Math.log(steady) + (1 - wgt) * Math.log(top)) : top);
          const step = view > 1 ? plotW / (view - 1) : 0;
          return {pts: vals.map((v, i) => [ml + (i - off) * step, v - base]), top: top};
        };
        const L = layers.map((ly) => { const l = lineOf(ly[0], ly[2], ly[3]); return l ? {pts: l.pts, top: l.top, w: Math.max(0, ly[1])} : null; }).filter(Boolean);
        if (L.length){ const tw = L.reduce((a2, l) => a2 + l.w, 0) || 1; c.curTop = Math.exp(L.reduce((a2, l) => a2 + l.w * Math.log(Math.max(1e-9, l.top)), 0) / tw); }
        if (this._tr) this._tr.tot = 't=' + t.toFixed(3) + ' e=' + e.toFixed(3) + ' view ' + v0.toFixed(1) + '..' + v1.toFixed(1) + ' glide ' + Math.round(glide) + ' hold ' + wgt.toFixed(2) + ' top ' + Math.round(c.curTop || 0) + ' layers ' + L.map((l, i) => layers[i][0] + 'd:w' + l.w.toFixed(2) + ':top' + Math.round(l.top)).join(',');  // ANIMTRACE
        if (L.length){
          const tot = L.reduce((a2, l) => a2 + l.w, 0) || 1;
          const heightAt = (pts, top, x) => {
            if (x <= pts[0][0]) return pts[0][1] / top;
            for (let j = 1; j < pts.length; j++) if (x <= pts[j][0]){ const f = (x - pts[j - 1][0]) / Math.max(1e-9, pts[j][0] - pts[j - 1][0]); return (pts[j - 1][1] + (pts[j][1] - pts[j - 1][1]) * f) / top; }
            return pts[pts.length - 1][1] / top;
          };
          let pts;
          if (L.length === 1) pts = L[0].pts.map((q) => [q[0], bottom - Math.max(0, Math.min(1, q[1] / L[0].top)) * plotH]);
          else {
            const lo = ml - 2, hi = ml + plotW + 2, xs = new Set([lo, hi]);
            L.forEach((l) => l.pts.forEach((q) => { if (q[0] >= lo && q[0] <= hi) xs.add(q[0]); }));
            pts = Array.from(xs).sort((p1, p2) => p1 - p2).map((x) => [x, bottom - Math.max(0, Math.min(1, L.reduce((a2, l) => a2 + l.w * heightAt(l.pts, l.top, x), 0) / tot)) * plotH]);
          }
          if (this._tr){ const ev = edgeYs(pts, ml, ml + plotW); this._tr.cs = [ml, ev[0]]; this._tr.ce = [ml + plotW, ev[1]]; this._tr.cn = pts.length; this._tr.tail = pts.slice(-3); this._tr.pr = ml + plotW;
            // ANIMTRACE: the line's shape (its height across the plot) and where the days of the smaller window are
            const yAt = (x) => Math.round(edgeYs(pts, x, x)[0]), sx = (d) => ml + (d - v0) / (v1 - v0) * plotW;
            const zw = (c.b[1] - c.b[0]) < (c.a[1] - c.a[0]) ? c.b : c.a;
            this._tr.mid = 'plot 1/4,1/2,3/4 y ' + [0.25, 0.5, 0.75].map((f) => yAt(ml + plotW * f)) + ' | window days ' + zw.map(Math.round) + ' + middle at x ' + [zw[0], (zw[0] + zw[1]) / 2, zw[1]].map((d) => Math.round(sx(d))) + ' y ' + [zw[0], (zw[0] + zw[1]) / 2, zw[1]].map((d) => yAt(sx(d))); }
          ctx.beginPath(); smoothPath(ctx, pts); ctx.lineTo(pts[pts.length - 1][0], bottom); ctx.lineTo(pts[0][0], bottom); ctx.closePath();
          totalArea(ctx, pts, this.colors, isDark, lineK, (this.options.total_line_pct || 0) / 100);
        }
      }
      // average line: its height moves from the start one to the end one with the view
      const r = c.ra + (c.rb - c.ra) * e; c.curR = r;
      if (this.options.show_average && r > 0){
        const y = Math.trunc(bottom - Math.min(1, r) * plotH), small = H < 200, lw = small ? 0.9 : 1.1, dash = small ? 2.5 : 3.0;
        const bgc = this.colors.bg || (isDark ? '#000000' : '#ffffff');
        ctx.setLineDash([dash, dash]); ctx.lineCap = 'butt';
        ctx.strokeStyle = rgba(isDark ? scaleV(bgc, 1 / 1.6) : bgc, 90 / 255); ctx.lineWidth = lw + 1.2; ctx.beginPath(); ctx.moveTo(ml, y); ctx.lineTo(ml + plotW, y); ctx.stroke();
        ctx.strokeStyle = rgba(scaleV(this.colors.total_line, isDark ? 1.35 : 1 / 1.25), 175 / 255 * lineK); ctx.lineWidth = lw; ctx.beginPath(); ctx.moveTo(ml, y); ctx.lineTo(ml + plotW, y); ctx.stroke();
        ctx.setLineDash([]);
      }
      ctx.restore();
      // web: the axis numbers glide with the scale the bars are drawn at (the left one: the tallest bar, the right
      // one: the running total's top), so they count up or down during the zoom instead of fading into new ones
      {
        const mode = this.options.metric_mode, cum = this.options.show_cumulative && this.options.has_cumulative !== false;
        ctx.font = AXIS_FONT; ctx.textBaseline = 'middle'; ctx.textAlign = 'right'; ctx.fillStyle = this._axisInk();
        if (camTicks){
          camTicks.forEach((k) => { ctx.globalAlpha = k.a; ctx.fillText(formatAxis(k.v, mode), ml - 8, padT + plotH * (1 - k.f)); });
          if (cum && c.curTop) DD.slideTicks(c.ta, c.tb, c.curTop, e, 4, plotH).forEach((k) => { ctx.globalAlpha = 0.8 * k.a; ctx.fillText(formatAxis(k.v, mode), W - 4, padT + plotH * (1 - k.f)); });
        } else for (let g = 0; g <= 4; g++){
          const frac = g / 4, y = padT + plotH * (1 - frac);
          ctx.globalAlpha = 1; ctx.fillText(formatAxis(mx * frac, mode), ml - 8, y);
          if (cum && c.curTop){ ctx.globalAlpha = 0.8; ctx.fillText(formatAxis(c.curTop * frac, mode), W - 4, y); }
        }
        ctx.globalAlpha = 1;
      }
      ctx.restore();
      return true;
    }

    // one bar as the chart draws it (shared by the chart and the zoom camera, so the last zoom frame is the chart itself)
    // bar width / slot: 0.9 for the Activity charts, 0.95 for Added
    _baseRatio(){ return this.options.added_style ? 0.95 : 0.9; }
    // the dates under the plot at days a round number of days apart (counted back from the
    // last day, so a day keeps its date mark whatever the view), about 110 px apart. [day index, ...] for the view
    // [v0, v1) drawn plotW wide
    _dayStep(v0, v1, plotW){
      const want = (v1 - v0) / Math.max(1, plotW) * 110;
      const steps = [1, 2, 3, 7, 14, 28, 56, 91, 182, 364, 728, 1456];
      for (const k of steps) if (k >= want) return k;
      return steps[steps.length - 1];
    }
    _dayTicks(v0, v1, step){
      const N = this.daily.length, out = [];
      let i = N - 1 - Math.floor((N - 1 - Math.ceil(v0 - 0.5)) / step) * step;
      for (; i < v1 && out.length < 400; i += step) if (i >= 0 && i < N) out.push(i);
      return out;
    }
    // the rows on a time line (providers _daily_rows: t, dt): the time at a day index (fractions inside a row); null
    // without times. _sub: rows shorter than a day (the 10-minute view), whose marks are the clock's (DD.timeMarks)
    _T(x){
      const R = this.daily, N = R.length; if (!N || R[0].t == null) return null;
      const i = Math.max(0, Math.min(N - 1, Math.floor(x))), r = R[i], dt = r.dt || R[0].dt || 86400000;
      return (r.t != null ? r.t : R[0].t + i * dt) + (x - i) * dt;
    }
    _sub(){ const r = this.daily[0]; return !!(r && r.t != null && r.dt && r.dt < 86400000); }
    _drawTimes(ctx, v0, v1, left, right, yL){
      const t0 = this._T(v0), t1 = this._T(v1); if (t0 == null) return;
      ctx.save(); ctx.font = AXIS_FONT; ctx.fillStyle = this._axisInk();
      DD.placeMarks(ctx, DD.timeMarks(t0, t1, right - left), (t) => left + (t - t0) / (t1 - t0) * (right - left), left, right, yL);
      ctx.restore();
    }
    // what a picture zoom needs to draw this chart's axes itself while it moves (DD.pictureZoom): the time window of the
    // plot, its date marks (or the clock's), the left axis' top and how its numbers read
    _axisInfo(){
      const R = this.daily; if (!R.length || R[0].t == null || this._padL == null) return null;
      // the days last drawn (a snap is the canvas as it is: a zoom set at once is drawn on the next frame only)
      let v0, v1;
      if (this._drawnV){ v0 = this._drawnV[0]; v1 = this._drawnV[1]; }
      else { v0 = this._visibleOffset(); v1 = v0 + Math.max(1, this._visibleDaily().length); }
      const plotW = Math.max(1, this.w - this._padL - this._padR), sub = this._sub();
      const marks = sub ? null : this._dayTicks(v0, v1, this._dayStep(v0, v1, plotW)).map((i) => ({t: this._T(i + 0.5), label: R[i].date}));
      const Y = this._axY || {max: 1, mode: this.options.metric_mode};
      return {t0: this._T(v0), t1: this._T(v1), sub: sub, marks: marks, ymax: Y.max, ykind: 'bars:' + Y.mode,
        yfmt: (v) => formatAxis(v, Y.mode), ink: this._axisInk(), font: AXIS_FONT, mt: 10};
    }
    // X-axis snapshot for morph transitions: timed charts reuse _axisInfo(); non-dated charts (FSRS Loss by Fatigue,
    // Answer Time, Interval Ratings, Added, ...) capture their visible tick labels at normalized plot positions
    _xAxisState(){
      const R = this.daily; if (!R.length || this._padL == null) return null;
      if (R[0].t != null) return this._axisInfo();
      let v0, v1;
      if (this._drawnV){ v0 = this._drawnV[0]; v1 = this._drawnV[1]; }
      else { v0 = this._visibleOffset(); v1 = v0 + Math.max(1, this._visibleDaily().length); }
      const span = Math.max(1e-6, v1 - v0);
      const plotW = Math.max(1, this.w - this._padL - this._padR);
      const marks = this._dayTicks(v0, v1, this._dayStep(v0, v1, plotW))
        .filter((i) => R[i] && R[i].date != null && String(R[i].date) !== '')
        .map((i) => ({f: (i + 0.5 - v0) / span, label: String(R[i].date), j: i - v0}));
      return {idxAxis: true, t0: v0, t1: v1, marks: marks, vis: v1 - v0, bs: binSize(Math.max(1, v1 - v0), this.options.adaptive_binning)};
    }
    // the date marks of a view drawn: [{i, a}] with x from the day index; a mark coming close to another one fades as
    // they near, as do those whose text reaches past the plot's ends
    _drawDays(ctx, marks, toX, left, right, yL){
      const sm = (x) => { x = Math.max(0, Math.min(1, x)); return x * x * (3 - 2 * x); };
      ctx.save(); ctx.font = AXIS_FONT; ctx.textBaseline = 'middle'; ctx.textAlign = 'center'; ctx.fillStyle = this._axisInk();
      const placed = [];
      marks.slice().sort((p, q) => q.p - p.p).forEach((m) => {
        const r = this.daily[m.i]; if (!r || !r.date) return;
        const x = toX(m.i + 0.5), lw = ctx.measureText(r.date).width;
        // the whole date inside the plot's width: past it, it ran under the axis numbers' 0 (and the right axis' one)
        let a = m.a * sm((x - lw / 2 - left + 2) / 10) * sm((right - x - lw / 2 + 2) / 10);
        placed.forEach((q) => { const gap = Math.abs(q.x - x) - (q.w + lw) / 2; a *= sm(gap / 14); });
        if (a <= 0.003) return;
        if (a > 0.05) placed.push({x: x, w: lw});
        ctx.globalAlpha = a; ctx.fillText(r.date, x, yL);
      });
      ctx.restore();
    }
    // the share FSRS expected to fail (FSRS Calibration, Recall by Elapsed / Stability): a mark across the bar at y,
    // where its failed part should end (the chart's draw and the zoom camera's)
    // a: its opacity while it fades (a bar emptying or filling from nothing), else 1
    _expMark(ctx, x, barW, y, a){
      if (a != null && a <= 0.01) return;
      const ym = Math.round(y) + 0.5, ext = Math.min(3, barW * 0.25);
      const dk = !!this.colors.is_dark, bgc = this.colors.bg || (dk ? '#000000' : '#ffffff');
      ctx.save(); ctx.lineCap = 'butt';
      if (a != null && a < 1) ctx.globalAlpha *= a;
      ctx.strokeStyle = rgba(bgc, 0.75); ctx.lineWidth = 3.2;
      ctx.beginPath(); ctx.moveTo(x - ext, ym); ctx.lineTo(x + barW + ext, ym); ctx.stroke();
      ctx.strokeStyle = rgba(this.colors.text_primary || (dk ? '#ffffff' : '#000000'), dk ? 0.9 : 0.8); ctx.lineWidth = 1.6;
      ctx.beginPath(); ctx.moveTo(x - ext, ym); ctx.lineTo(x + barW + ext, ym); ctx.stroke();
      ctx.restore();
    }
    // Line (the level charts: options.line_view): the bars are not painted, their tops are kept (_lineBegin) and drawn
    // as one line, an area under it, stacked by series (_lineFlush); the zooms, intro and changes stay the bars' own
    _lineBegin(){ this._lp = this.options.line_view || this._lvM != null ? [] : null; }
    // Bars <-> Line (its pill): the bars narrow to their tops as the line and its area come in (and back), one
    // morph of 420 ms (times the animation speed); none out of view, during the intro or with the animations off
    _lineMixStart(opts){
      if (!opts || opts.line_view === undefined || !!opts.line_view === !!this.options.line_view) return;
      const still = DD._noAnim || DD.animOff || this.canvas.width <= 1;
      if (opts.line_view && this.options.variation && !opts.variation){
        // from Variation (another view): the line comes in as at its intro, from left to right (mount's frame)
        this._lvMix = null;
        if (!still && this.progress >= 1){ this.progress = 0; this._replayIntro = true; }
        return;
      }
      this._lvMix = (DD._noAnim || DD.animOff || this.progress < 1 || this.canvas.width <= 1) ? null : {to: !!opts.line_view, t0: null};
    }
    // the line's share in the frame (0: the bars, 1: the line), null when no morph runs
    _lineMixT(now){
      const L = this._lvMix;
      if (!L) return null;
      if (L.t0 == null) L.t0 = now;
      let t = Math.min(1, (now - L.t0) / (420 * DD.speed()));
      if (t >= 1){ this._lvMix = null; return null; }
      t = t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
      return L.to ? t : 1 - t;
    }
    _lineFlush(ctx, left, right){
      let P = this._lp; this._lp = null;
      // (an average with no answers in its bar: left out, the line goes over it)
      if (P && this.options.line_skip_empty) P = P.filter((p) => Math.abs(p.ys[p.ys.length - 1] - p.base) >= 0.25);
      if (!P || !P.length) return;
      P.sort((a, b) => a.x - b.x);
      const isDark = !!this.colors.is_dark, base = P[0].base, nk = P[0].ys.length;
      const op = Math.max(0, Math.min(100, this.options.chart_opacity_pct != null ? this.options.chart_opacity_pct : 71)) / 100;
      const keys = this.options.show_breakdown ? this.keys : null;
      // (one point: a short flat stroke, not nothing)
      const pts = (j) => (P.length > 1 ? P : [Object.assign({}, P[0], {x: P[0].x - 2}), Object.assign({}, P[0], {x: P[0].x + 2})]).map((p) => [p.x, j < 0 ? p.base : p.ys[j]]);
      ctx.save();
      if (this._lvM != null) ctx.globalAlpha *= this._lvM;  // (the morph from / to the bars)
      ctx.beginPath(); ctx.rect(left, 0, right - left, base + 1); ctx.clip();
      ctx.lineJoin = 'round'; ctx.lineCap = 'round';
      for (let j = 0; j < nk; j++){
        const top = pts(j), low = pts(j - 1);
        if (top.every((q, i) => Math.abs(q[1] - low[i][1]) < 0.25)) continue;  // (a series at 0 all along)
        const col = keys ? this.col(keys[j]) : (this.colors.bar || '#3b82f6');
        ctx.beginPath();
        top.forEach((q, i) => (i ? ctx.lineTo(q[0], q[1]) : ctx.moveTo(q[0], q[1])));
        for (let i = low.length - 1; i >= 0; i--) ctx.lineTo(low[i][0], low[i][1]);
        ctx.closePath();
        ctx.fillStyle = rgba(col, (isDark ? 0.34 : 0.26) * op / 0.71);
        ctx.fill();
        ctx.beginPath();
        top.forEach((q, i) => (i ? ctx.lineTo(q[0], q[1]) : ctx.moveTo(q[0], q[1])));
        ctx.strokeStyle = rgba(isDark ? scaleV(col, 1.12) : col, Math.min(1, op / 0.71));
        ctx.lineWidth = this.h < 200 ? 1.4 : 1.8;
        ctx.stroke();
      }
      // the bar hovered: a dot on each line
      const hv = P.filter((p) => p.hov)[0];
      if (hv){
        const bg = this.colors.bg || (isDark ? '#1e1e1e' : '#ffffff');
        for (let j = 0; j < nk; j++){
          if (Math.abs(hv.ys[j] - (j ? hv.ys[j - 1] : hv.base)) < 0.25) continue;
          ctx.beginPath(); ctx.arc(hv.x, hv.ys[j], 3.2, 0, Math.PI * 2);
          ctx.fillStyle = keys ? this.col(keys[j]) : (this.colors.bar || '#3b82f6'); ctx.fill();
          ctx.lineWidth = 1.5; ctx.strokeStyle = bg; ctx.stroke();
        }
      }
      ctx.restore();
    }
    _paintBar(ctx, b, x, barW, base, plotH, maxVal, barScaleMax, growT){
      const showBreakdown = this.options.show_breakdown, isDark = !!this.colors.is_dark;
      if (this._lp){
        const ys = [];
        if (showBreakdown){ let cum = 0; this.keys.forEach((k) => { cum += Math.max(0, b[k] || 0); ys.push(base - Math.min(1, cum / maxVal) * plotH * growT); }); }
        else ys.push(base - Math.min(1, (b.total || 0) / barScaleMax) * plotH * growT);
        this._lp.push({x: x + barW / 2, ys: ys, base: base, hov: !!this._lpHov});
        if (this._lvM == null) return;
        // (the morph: the bar painted too, narrowed to its middle as the line comes in)
        x += barW * this._lvM / 2; barW *= 1 - this._lvM;
        if (barW < 0.3) return;
      }
      const opacityFrac = Math.max(0, Math.min(100, this.options.chart_opacity_pct != null ? this.options.chart_opacity_pct : 71)) / 100;
    if (showBreakdown){
                let tot = 0;
      this.keys.forEach((k) => { if ((b[k] || 0) > 0) tot += Math.min(1, b[k] / maxVal) * plotH * growT; });
      const sk = smoothK((barW - 2) / 4) * smoothK((tot - 2) / 8);
      const kk = (this.options.bar_gradient_pct != null ? this.options.bar_gradient_pct : 43) / 100 * sk;
      let topKey = null;
      this.keys.forEach((k) => { if ((b[k] || 0) > 0) topKey = k; });
      let curY = base;
      this.keys.forEach((k) => {
        const val = b[k] || 0;
        if (val <= 0) return;
        const segH = Math.min(1, val / maxVal) * plotH * growT;
        const y = curY - segH;
        const col = this.col(k);
        if (sk > 0.01){
          const g = ctx.createLinearGradient(0, base - tot, 0, base);
          if (isDark){
            g.addColorStop(0, rgba(scaleV(col, (100 + Math.round(14 * kk)) / 100), opacityFrac));
            g.addColorStop(1, rgba(scaleV(col, 100 / (100 + Math.round(30 * kk))), Math.max(30 / 255, opacityFrac * (1 - 0.12 * kk))));
          } else {
            g.addColorStop(0, rgba(col, opacityFrac));
            g.addColorStop(1, rgba(col, Math.max(30 / 255, opacityFrac * (1 - 0.38 * kk))));
          }
          ctx.fillStyle = g;
        } else ctx.fillStyle = rgba(col, opacityFrac);
        const r = Math.min(1, barW / 2, segH);  // 1 px, as Anki's bars
        if (k === topKey && barW >= 4 && r >= 1){
          ctx.beginPath();
          ctx.moveTo(x, y + segH); ctx.lineTo(x, y + r); ctx.quadraticCurveTo(x, y, x + r, y);
          ctx.lineTo(x + barW - r, y); ctx.quadraticCurveTo(x + barW, y, x + barW, y + r);
          ctx.lineTo(x + barW, y + segH); ctx.closePath(); ctx.fill();
        } else ctx.fillRect(x, y, barW, Math.max(0, segH));
        curY = y;
      });
    } else {
      const bh = Math.min(1, b.total / barScaleMax) * plotH * growT;
      const y = base - bh;
      const ratio = barScaleMax > 0 ? Math.min(1, b.total / barScaleMax) : 0;
      if (this.options.added_style && DD.cu.barFill){
        const hex = DD.cu.gradientColor(this.colors.bar || '#3b82f6', ratio, isDark);
        DD.cu.roundedBar(ctx, x, y, barW, bh, DD.cu.barFill(ctx, hex, y, barW, bh, opacityFrac, isDark, 0.43), true);
      } else {
        ctx.fillStyle = heightShadedColor(this.colors.bar || '#3b82f6', ratio, isDark, opacityFrac);
        ctx.fillRect(x, y, barW, Math.max(0, bh));
      }
    }
    }

    resetZoom(){
      if (!this.zoomRange) return;
      this._zoomTo(null);
      if (this.onZoom) this.onZoom();
    }

    _xToBinIndex(x){
      if (!this._bins.length || this._plotW <= 0) return 0;
      const step = this._plotW / this._bins.length;
      const idx = Math.floor((x - this._padL) / step);
      return Math.max(0, Math.min(this._bins.length - 1, idx));
    }

    _updateHover(x, y){
      const n = this._bins.length;
      if (!n || this._plotW <= 0 || x < this._padL || x > this.w - this._padR){
        this._hoverIndex = null;
        this._hoverAvg = false;
        this._hideTooltipDom();
        return;
      }
      let idx = Math.floor(((x - this._padL) / this._plotW) * n);
      idx = Math.max(0, Math.min(n - 1, idx));
      this._hoverIndex = idx;

      if (this._lastAvgY != null){
        const threshold = this._hoverAvg ? 14 : 10;
        this._hoverAvg = Math.abs(y - this._lastAvgY) <= threshold;
      } else {
        this._hoverAvg = false;
      }
    }

    _hideTooltipDom(){
      if (this.tooltipEl) this.tooltipEl.style.display = 'none';
    }

    _formatTooltipValue(v){
      if (this.options.show_percent && this.options.show_breakdown) return trimNum(v, 1) + '%';
      if (this.options.unit === 'seconds') return DD.t('{value}s', {value: trimNum(v, 1)});  // Review Speed: 4.4s
      if (this.options.value_days) return DD.tn('{n} day', '{n} days', Math.round(v), {n: trimNum(v, v < 10 ? 1 : 0)});  // an average stability
      if (this.options.unit === 'rmse' || this.options.value_pct) return trimNum(v, 1) + '%';  // FSRS Loss by Fatigue, Memorised's average
      if (this.options.unit === 'load' || this.options.value_load) return trimNum(v, v < 10 ? 2 : 1);  // reviews a day: small fractions (Introduced Load, Load Trend)
      if (this.options.time_tip && this.options.metric_mode === 'time') return formatAxis(v, 'time');  // minutes (Ratings' Time view)
      return formatNum(v);
    }

    _updateTooltipDom(row, showBreakdown, showCumulative, cumulativeValue){
      const el = this.tooltipEl;
      if (!el || this._mouseX == null) return;

      const contentKey = row.label + '|' + row.total + '|' + showBreakdown + '|' + showCumulative + '|' + cumulativeValue
        + '|' + this.keys.map((k) => row[k] || 0).join(',') + '|' + (row._exp != null ? row._exp : '') + '|' + (row._reviews != null ? row._reviews : '');
      if (this._tooltipContentKey !== contentKey){
        this._tooltipContentKey = contentKey;
        const rows = [];
        rows.push(
          `<div class="row header"><span class="label">${row.label || ''}</span>` +
          `<span class="value">${this._formatTooltipValue(row.total)}</span></div>`
        );
        if (showBreakdown){
          this.keys.forEach((k) => {
            const val = row[k] || 0;
            if (val <= 0) return;
            rows.push(
              `<div class="row"><span class="swatch" style="background:${this.col(k)}"></span>` +
              `<span class="label">${(this.options.labels && this.options.labels[k]) || TYPE_LABELS[k] || k}</span>` +
              `<span class="value">${this._formatTooltipValue(val)}</span></div>`
            );
          });
        }
        if (showBreakdown && row._exp != null){
          rows.push(`<div class="row"><span class="label">${DD.t('Predicted fail')}</span>` +
            `<span class="value">${this._formatTooltipValue(row._exp)}</span></div>`);
        }
        // Review Speed: how many reviews the average is of, and the time they took
        if (row._reviews != null){
          const sec = Math.round((row._ms || 0) / 1000);
          const time = sec < 60 ? DD.t('{value}s', {value: sec}) : sec < 3600 ? DD.t('{minutes}m {seconds}s', {minutes: Math.floor(sec / 60), seconds: sec % 60})
            : DD.t('{value}h', {value: trimNum(sec / 3600, 1)});
          rows.push(`<div class="row"><span class="label">${DD.t('Reviews')}</span><span class="value">${formatNum(row._reviews)}</span></div>`,
            `<div class="row"><span class="label">${DD.t('Time')}</span><span class="value">${time}</span></div>`);
        }
        if (showCumulative){
          rows.push(`<div class="row total">${DD.t('Total: {value}', {value: this._formatTooltipValue(cumulativeValue || 0)})}</div>`);
        }
        el.innerHTML = rows.join('');
        el.style.background = rgba(this.colors.tooltip_bg || '#18181b', this.colors.is_dark ? 0.91 : 0.96);
        el.style.borderColor = this.colors.tooltip_border || 'rgba(128,128,128,0.4)';
        el.style.color = this.colors.text_secondary || '#888';
        const headerEl = el.querySelector('.row.header');
        if (headerEl) headerEl.style.color = this.colors.text_primary || '#fff';
        const totalEl = el.querySelector('.row.total');
        if (totalEl) totalEl.style.color = this.colors.text_primary || '#fff';
        el.style.display = 'block';
        this._tooltipW = el.offsetWidth;
        this._tooltipH = el.offsetHeight;
      } else if (el.style.display === 'none'){
        el.style.display = 'block';
      }

      const cw = this.w, ch = this.h;
      const tw = this._tooltipW || 0, th = this._tooltipH || 0;
      let left = this._mouseX + 15;
      let top = this._mouseY + 15;
      if (left + tw > cw) left = this._mouseX - tw - 15;
      if (left < 0) left = 2;
      if (top + th > ch) top = ch - th - 2;
      if (top < 0) top = 2;
      el.style.transform = `translate3d(${left}px, ${top}px, 0)`;
    }

    _updateAvgLabelDom(avgValue, avgY, padL){
      const el = this.avgLabelEl;
      if (!el) return;
      // as Retention's (its .dd-avg-label): "avg: value", in the average line's color
      const text = DD.t('avg: {value}', {value: this._formatTooltipValue(avgValue)});
      if (this._avgLabelTextKey !== text){
        this._avgLabelTextKey = text;
        el.textContent = text;
        el.style.background = rgba(this.colors.tooltip_bg || '#18181b', this.colors.is_dark ? 0.91 : 0.96);
        el.style.borderColor = this.colors.tooltip_border || 'rgba(128,128,128,0.4)';
        el.style.color = rgba(scaleV(this.colors.total_line, this.colors.is_dark ? 1.35 : 1 / 1.25), 1);
        el.style.display = 'block';
        this._avgLabelW = el.offsetWidth || 40;
      } else if (el.style.display === 'none'){
        el.style.display = 'block';
      }
      const tw = this._avgLabelW || 40;
      let left = padL - tw - 5;
      if (left < 0) left = 2;
      el.style.transform = `translate3d(${left}px, ${avgY}px, 0) translateY(-50%)`;
    }

    _bindEvents(){
      const chart = this;
      const canvas = this.canvas;
      canvas.style.cursor = 'default';

      canvas.addEventListener('contextmenu', (e) => { e.preventDefault(); });

      let touchLock = 0, tx0 = 0, ty0 = 0, tPid = null, tScrub = false;
      canvas.addEventListener('pointerdown', (e) => {
        if (e.pointerType !== 'touch') return;
        touchLock = Date.now() + 800;
        tPid = e.pointerId; tx0 = e.clientX; ty0 = e.clientY; tScrub = false;
        const rect = canvas.getBoundingClientRect();
        const x = e.clientX - rect.left, y = e.clientY - rect.top;
        chart._mouseX = x; chart._mouseY = Math.max(4, y - 34);
        chart._updateHover(x, y);
        const outside = (ev) => {
          if (!canvas.contains(ev.target)){
            chart._hoverIndex = null; chart._hoverAvg = false; chart._mouseX = null; chart._mouseY = null;
            chart._hideTooltipDom();
            window.removeEventListener('pointerdown', outside, true);
          }
        };
        setTimeout(() => window.addEventListener('pointerdown', outside, true), 0);
      }, {passive: true});
      canvas.addEventListener('pointermove', (e) => {
        if (e.pointerType !== 'touch' || e.pointerId !== tPid) return;
        const dx = Math.abs(e.clientX - tx0), dy = Math.abs(e.clientY - ty0);
        if (!tScrub && dy > 10 && dy > dx){ tPid = null; return; }
        if (dx > 6 && dx >= dy) tScrub = true;
        if (tScrub){
          touchLock = Date.now() + 800;
          const rect = canvas.getBoundingClientRect();
          const x = e.clientX - rect.left, y = e.clientY - rect.top;
          chart._mouseX = x; chart._mouseY = Math.max(4, y - 34);
          chart._updateHover(x, y);
        }
      }, {passive: true});
      const endTouch = (e) => { if (e.pointerId === tPid){ tPid = null; tScrub = false; } };
      canvas.addEventListener('pointerup', endTouch, {passive: true});
      canvas.addEventListener('pointercancel', endTouch, {passive: true});

      canvas.addEventListener('mousedown', (e) => {
        if (Date.now() < touchLock) return;
        if (e.button !== 0) return; // left button only - don't start a
        const rect = canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        if (x < chart._padL || x > chart.w - chart._padR) return;
        chart._dragging = true;
        chart._dragStartX = x;
        chart._dragCurrentX = x;
      });
      canvas.addEventListener('mousemove', (e) => {
        if (Date.now() < touchLock) return;
        const rect = canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        chart._mouseX = x; chart._mouseY = y;
        if (chart._dragging){
          chart._dragCurrentX = Math.max(chart._padL, Math.min(chart.w - chart._padR, x));
          chart._hoverIndex = null;
          chart._hoverAvg = false;
          chart._hideTooltipDom();
          return;
        }
        chart._updateHover(x, y);
      });
      canvas.addEventListener('mouseleave', () => {
        chart._hoverIndex = null;
        chart._hoverAvg = false;
        chart._mouseX = null; chart._mouseY = null;
        chart._hideTooltipDom();
      });
      window.addEventListener('mouseup', () => {
        if (!chart._dragging) return;
        chart._dragging = false;
        const x0 = chart._dragStartX, x1 = chart._dragCurrentX;
        chart._dragStartX = null; chart._dragCurrentX = null;
        if (x0 === null || x1 === null || Math.abs(x1 - x0) < 6) return;
        const i0 = chart._xToBinIndex(Math.min(x0, x1));
        const i1 = chart._xToBinIndex(Math.max(x0, x1));
        chart.zoomToBinRange(i0, i1);
      });

      canvas.addEventListener('wheel', (e) => {
        if (e.shiftKey && chart.zoomRange){ e.preventDefault(); e.stopPropagation(); chart.panZoom(e.deltaY < 0 ? 1 : -1); return; }
        if (!(e.ctrlKey || e.metaKey)) return;
        e.preventDefault();
        e.stopPropagation();
        const rect = canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const idx = chart._xToBinIndex(x);
        const dir = e.deltaY < 0 ? 1 : -1;
        chart.wheelZoom(idx, dir);
      }, { passive: false });
    }

    draw(now){
      const animating = !!(this._cam || this._transition);
      // trace: the bars changed between two frames without a transition (a jump)
      if (DD.dev && this._bins){
        const sig = this._bins.length + ':' + Math.round(this._bins.reduce(function(a, b){ return a + (b.total || 0); }, 0));
        if (!animating && !this._trRun && this._sigLast && sig !== this._sigLast) DD.trace('ANIMTRACE ' + (this._traceName || 'activity') + ' INSTANT bars ' + this._sigLast + ' -> ' + sig + ' (last call: ' + (this._lastCall || '?') + ')');
        this._sigLast = sig;
      }
      if (!animating && !this._trRun){ return this._draw(now); }
      const kind = this._cam ? 'zoom' : (this._transition ? 'data' : 'end');
      this._tr = {kind: kind};
      this._draw(now);
      const T = this._tr; this._tr = null;
      const R = this._trRun || (this._trRun = {kind: kind, frames: 0, jumps: 0, t0: performance.now()});
      R.frames++;
      const P = R.prev;
      // ANIMTRACE: the running total's line each frame (its height at the plot's left and right edges, px from the top)
      if (DD.dev && T.ce) DD.trace('ANIMTRACE total ' + (this._traceName || 'activity') + ' ' + kind + ' f' + R.frames + ' @' + Math.round(performance.now() - R.t0) + 'ms start y ' + Math.round(T.cs[1]) + ' end y ' + Math.round(T.ce[1]) + ' pts ' + T.cn + (T.tail ? ' | tail ' + T.tail.map((q) => Math.round(q[0]) + ':' + Math.round(q[1])).join(' ') + ' plot right ' + Math.round(T.pr) : '') + (T.bl ? ' lastBar x ' + Math.round(T.bl[0]) + '..' + Math.round(T.bl[0] + T.bl[1]) : '') + (T.mid ? ' | ' + T.mid : '') + (T.tot ? ' | ' + T.tot : ''));
      if (P && DD.dev){
        const j = [];
        const d = (a, b, i) => (a && b) ? Math.abs(a[i] - b[i]) : 0;
        if (d(P.ce, T.ce, 0) > 12 || d(P.ce, T.ce, 1) > 12) j.push('totalEnd ' + P.ce.map(Math.round) + '->' + (T.ce || []).map(Math.round));
        if (d(P.cs, T.cs, 1) > 12) j.push('totalStart y ' + Math.round(P.cs[1]) + '->' + Math.round(T.cs[1]));
        if (P.avg != null && T.avg != null && Math.abs(P.avg - T.avg) > 8) j.push('avg ' + Math.round(P.avg) + '->' + Math.round(T.avg));
        if (P.bn && T.bn && P.bn !== T.bn) j.push('bars ' + P.bn + '->' + T.bn);
        if (P.lr != null && T.lr != null && (Math.abs(P.lr - T.lr) > 6 || Math.abs((P.lh || 0) - (T.lh || 0)) > 12)) j.push('lastBar right ' + Math.round(P.lr) + '->' + Math.round(T.lr) + ' h ' + Math.round(P.lh || 0) + '->' + Math.round(T.lh || 0));
        if (P.bl && T.bl && Math.abs(P.bl[1] - T.bl[1]) > 3) j.push('barW ' + P.bl[1].toFixed(1) + '->' + T.bl[1].toFixed(1));
        if (T.gaps && T.gaps.length > 2){ const mn = Math.min.apply(null, T.gaps), mx = Math.max.apply(null, T.gaps); if (mx - mn > 1.5) j.push('gaps ' + mn.toFixed(1) + '..' + mx.toFixed(1)); }
        if (j.length && R.jumps++ < 30) DD.trace('ANIMTRACE ' + (this._traceName || 'activity') + ' ' + R.kind + ' f' + R.frames + ': ' + j.join(' | '));
      }
      // the end of a transition: the last frame of it against the chart as it stays (bars that move, grow or come / go
      // at once: "things that jump into place at the end")
      if (!animating && P && DD.dev){
        const a = P.rects || [], b = T.rects || [];
        let mx = 0, at = '';
        for (let k = 1; k <= Math.min(a.length, b.length); k++){
          const p = a[a.length - k], q = b[b.length - k];
          const d = Math.max(Math.abs(p[0] - q[0]), Math.abs(p[1] - q[1]), Math.abs(p[2] - q[2]));
          if (d > mx){ mx = d; at = 'bar -' + k + ' x ' + p[0].toFixed(1) + '->' + q[0].toFixed(1) + ' w ' + p[1].toFixed(1) + '->' + q[1].toFixed(1) + ' h ' + p[2].toFixed(1) + '->' + q[2].toFixed(1); }
        }
        if (mx > 1.5 || a.length !== b.length) DD.trace('ANIMTRACE ' + (this._traceName || 'activity') + ' END JUMP ' + R.kind + ': visible bars ' + a.length + ' -> ' + b.length + (mx > 1.5 ? ', most moved ' + mx.toFixed(1) + 'px (' + at + ')' : ''));
      }
      R.prev = T;
      if (!animating){
        if (DD.dev) DD.trace('ANIMTRACE ' + (this._traceName || 'activity') + ' ' + R.kind + ' done frames=' + R.frames + ' jumps=' + R.jumps + ' ' + Math.round(performance.now() - R.t0) + 'ms');
        this._trRun = null;
      }
    }
    _draw(now){
      this._lvM = this._lineMixT(now || performance.now());
      this._moving = !!this._cam;
      if (this._cam && this._camDraw(now || performance.now())) return;
      if (this._camLerp && this._camLerp.done) this._endWindowMove();
      const { ctx, w, h } = this;
      ctx.clearRect(0, 0, w, h);

      const showBreakdown = this.options.show_breakdown;
      const isPct = !!(this.options.show_percent && showBreakdown);
      const showCumulative = this.options.show_cumulative && !isPct && this.options.has_cumulative !== false;
      const showAverage = this.options.show_average && !isPct;
      const isDarkGlobal = !!this.colors.is_dark;
      const opacityFrac = Math.max(0, Math.min(100, this.options.chart_opacity_pct != null ? this.options.chart_opacity_pct : 71)) / 100;

      // The transition clock: eased progress (InOutCubic), then the smoothstep the values go through (interpolate_scalar).
      const tr0 = this._transition;
      let raw0 = 0, curve0 = null, value0 = null, gmode = null;
      if (tr0){
        raw0 = Math.min(1, playClock(tr0, now || 0) / tr0.duration);
        curve0 = easeInOutCubic(raw0); value0 = smootherstep(curve0);
        const os = tr0.from.reduce((a, b) => a + (b.total || 0), 0), ns = tr0.to.reduce((a, b) => a + (b.total || 0), 0);
        if (os <= 0 && ns > 0) gmode = 'from_empty'; else if (os > 0 && ns <= 0) gmode = 'to_empty';
      }
      // Margins like ChartGeometry: widest axis label + 12 (left) / + 10 (right); they glide between the two sides of a transition.
      ctx.font = AXIS_FONT;
      const mode0 = isPct ? 'percent' : this.options.metric_mode;
      const marginsOf = (totals, mode, cum) => {
        const mx = Math.max.apply(null, totals.concat([0])) || 1;
        let lw = 0;
        for (let g = 0; g <= 4; g++) lw = Math.max(lw, ctx.measureText(formatAxis(mx * g / 4, mode)).width);
        let r = 20;
        if (cum){
          const sm = totals.reduce((a, b) => a + b, 0) || 1;
          let rw = 0;
          for (let g = 0; g <= 4; g++) rw = Math.max(rw, ctx.measureText(formatAxis(sm * g / 4, mode)).width);
          r = Math.max(20, Math.round(rw) + 10);
        }
        return [Math.max(35, Math.round(lw) + 12), r];
      };
      const finalTotals = (this._bins || []).map((b) => b.total || 0);
      let [padL, padR] = marginsOf(finalTotals, mode0, showCumulative);
      if (tr0){
        const fm = tr0.fromMeta || {mode: mode0, cum: showCumulative};
        const [oL, oR] = marginsOf(tr0.from.map((b) => b.total || 0), fm.mode, fm.cum);
        padL = Math.round(oL + (padL - oL) * curve0); padR = Math.round(oR + (padR - oR) * curve0);
      }
      this._meta = {mode: mode0, cum: showCumulative};
      const padT = 10, padB = this._padB();
      this._padL = padL; this._padR = padR;
      const plotW = Math.max(1, w - padL - padR);
      const plotH = Math.max(1, h - padT - padB);
      this._plotW = plotW; this._plotH = plotH;

      let bins = this._bins;
      let slots = null;
      let growT = easeOutQuart(Math.min(1, this.progress));
      let curveT = null;

      const tr = this._transition;
      // Line: its intro as Retention's, drawn from left to right at its full height (not grown from the bottom)
      const lvReveal = this.options.line_view && this.progress < 1 && !tr ? 1 - Math.pow(1 - Math.min(1, this.progress), 3) : null;
      if (lvReveal != null) growT = 1;
      // Variation (or a change from it): the bars around a zero line, in real units during a change (never the
      // relative 0..1 scale, which loses the losses' sign and the axis' numbers)
      const signed = !!this.options.variation || !!(tr && tr.fromVar);
      this._varDrawn = signed;
      if (tr){
        const raw = raw0;
        curveT = curve0;
        const valueT = value0;
        const sameCount = tr.from.length === tr.to.length && tr.from.length > 0;

        if (gmode){
          // to or from nothing: the bars of the side that has data grow / sink in place (global transition mode)
          bins = gmode === 'from_empty' ? tr.to : tr.from;
          slots = null;
        } else if (this.options.relative_height_transition && !signed){
          const n = Math.max(tr.from.length, tr.to.length);
          const alignRight = tr.alignRight;
          const fromPad = alignRight ? (n - tr.from.length) : 0;
          const toPad = alignRight ? (n - tr.to.length) : 0;
          const fromVals = [], toVals = [], rowLabels = [];
          for (let i = 0; i < n; i++){
            const fi = i - fromPad, ti = i - toPad;
            const fromRow = (fi >= 0 && fi < tr.from.length) ? tr.from[fi] : null;
            const toRow = (ti >= 0 && ti < tr.to.length) ? tr.to[ti] : null;
            fromVals.push(fromRow ? (fromRow.total || 0) : 0);
            toVals.push(toRow ? (toRow.total || 0) : 0);
            rowLabels.push((toRow && toRow.label) || (fromRow && fromRow.label) || '');
          }
          const oldMax = Math.max(0, ...fromVals) || 1;
          const newMax = Math.max(0, ...toVals) || 1;
          const keysR = this.keys || [];
          bins = fromVals.map((fv, i) => {
            const oldNorm = fv / oldMax;
            const newNorm = toVals[i] / newMax;
            const row = { label: rowLabels[i], total: Math.max(0, oldNorm + (newNorm - oldNorm) * valueT) };
            // the segments of a stacked bar follow the same relative scale (else the bars vanish during the switch)
            const fi = i - fromPad, ti = i - toPad;
            const fr = (fi >= 0 && fi < tr.from.length) ? tr.from[fi] : null, to = (ti >= 0 && ti < tr.to.length) ? tr.to[ti] : null;
            keysR.forEach((k) => {
              const o = fr ? (fr[k] || 0) / oldMax : 0, nn = to ? (to[k] || 0) / newMax : 0;
              row[k] = Math.max(0, o + (nn - o) * valueT);
            });
            // FSRS's expected mark (FSRS Calibration...): on the same scale, so it stays through the morph
            const fe = fr && fr._exp != null ? fr._exp / oldMax : null, te = to && to._exp != null ? to._exp / newMax : null;
            if (fe != null || te != null){
              const a = fe != null ? fe : te, b = te != null ? te : fe; row._exp = Math.max(0, a + (b - a) * valueT);
              if (fe == null || te == null) row._expA = fe == null ? valueT : 1 - valueT;  // (as blendRow)
            }
            return row;
          });
          this._relScale = oldMax + (newMax - oldMax) * valueT;

          const oldCum = []; { let s = 0; fromVals.forEach((v) => { s += v; oldCum.push(s); }); }
          const newCum = []; { let s = 0; toVals.forEach((v) => { s += v; newCum.push(s); }); }
          const oldEnd = (oldCum.length ? oldCum[oldCum.length - 1] : 0) || 1;
          const newEnd = (newCum.length ? newCum[newCum.length - 1] : 0) || 1;
          this._relativeCumulative = oldCum.map((ov, i) => {
            const on = ov / oldEnd, nn = newCum[i] / newEnd;
            return Math.max(0, on + (nn - on) * valueT);
          });

          // (anchored on the left too: the bars go from their old grid to the new one, never laid out at once on the
          // larger count)
          if (alignRight || tr.from.length !== tr.to.length){
            slots = interpolateBarSlots(tr.from.length, tr.to.length, valueT, padL, plotW, alignRight, denseRatio(plotW / Math.max(1, tr.to.length), this._baseRatio()));
          }
        } else if (sameCount){
          bins = tr.to.map((toRow, i) => blendRow(tr.from[i] || emptyRow(toRow.label, this.keys), toRow, valueT, undefined, this.keys));
        } else {
          const n = Math.max(tr.from.length, tr.to.length);
          const alignRight = tr.alignRight;
          const fromPad = alignRight ? (n - tr.from.length) : 0;
          const toPad = alignRight ? (n - tr.to.length) : 0;
          bins = [];
          for (let i = 0; i < n; i++){
            const fi = i - fromPad, ti = i - toPad;
            const fromRow = (fi >= 0 && fi < tr.from.length) ? tr.from[fi] : emptyRow('', this.keys);
            const toRow = (ti >= 0 && ti < tr.to.length) ? tr.to[ti] : emptyRow('', this.keys);
            bins.push(blendRow(fromRow, toRow, valueT, toRow.label || fromRow.label, this.keys));
          }
          if (alignRight){
            const slideWidthRatio = denseRatio(plotW / Math.max(1, tr.to.length), this._baseRatio());
            slots = interpolateBarSlots(tr.from.length, tr.to.length, valueT, padL, plotW, alignRight, slideWidthRatio);
          } else {
            // not aligned right: the old bars keep their own grid at the start and glide to the new one (they were laid
            // out on the new count at once, so the bars re-positioned in the first frame, then animated)
            slots = interpolateBarSlots(tr.from.length, tr.to.length, valueT, padL, plotW, false, denseRatio(plotW / Math.max(1, tr.to.length), this._baseRatio()));
          }
        }
        if (tr.fromSlots && !gmode){
          // bins of the transitions above are max(from, to) long, the from ones padded the same way as the slots
          const fn = tr.from.length, tn = tr.to.length, nn = Math.max(fn, tn);
          if (bins.length !== nn){
            const fp = tr.alignRight ? nn - fn : 0, tp = tr.alignRight ? nn - tn : 0;
            bins = [];
            for (let i = 0; i < nn; i++){
              const fi = i - fp, ti = i - tp;
              const fr = (fi >= 0 && fi < fn) ? tr.from[fi] : emptyRow('', this.keys), to = (ti >= 0 && ti < tn) ? tr.to[ti] : emptyRow('', this.keys);
              bins.push(blendRow(fr, to, valueT, to.label || fr.label, this.keys));
            }
          }
          slots = interpolateBarSlotsFrom(tr.fromSlots, tn, valueT, padL, plotW, !!tr.alignRight, denseRatio(plotW / Math.max(1, tn), this._baseRatio()));
        }
        growT = gmode ? (gmode === 'from_empty' ? valueT : 1 - valueT) : 1;
        if (raw >= 1) this._transition = null;
      }

      // what is on screen, for a transition that starts before this one ends (bars sunk / grown by the presence)
      if (tr && !gmode && this.options.relative_height_transition && this._relScale && !signed){
        // kept in real units, so a transition starting now does not start from the 0..1 scale
        const sc = this._relScale;
        this._lastRenderedBins = bins.map((r) => { const o = Object.assign({}, r); ['total', '_exp'].concat(this.keys || []).forEach((k) => { if (r[k] !== undefined) o[k] = r[k] * sc; }); return o; });
      } else
      this._lastRenderedBins = (tr && gmode && growT < 1) ? bins.map((r) => { const o = Object.assign({}, r); ['total'].concat(this.keys).forEach((k) => { o[k] = (r[k] || 0) * growT; }); if (r._exp != null) o._exp = r._exp * growT; return o; }) : bins;

      this._lastRenderedSlots = slots ? slots.map((q) => [q[0], q[1]]) : null;
      const n = bins.length;
      const totals = bins.map((b) => b.total);

      let cumulative = [];
      if (showCumulative){
        let run = 0;
        cumulative = totals.map((v) => { run += v; return run; });
      }

      let maxVal, maxCum, barScaleMax, cumValues, axisRightMax;
      if (curveT !== null && tr && gmode){
        maxVal = Math.max.apply(null, totals.concat([0])) || 1;
        barScaleMax = maxVal;
        maxCum = cumulative.length ? (cumulative[cumulative.length - 1] || 1) : 1;
        cumValues = cumulative;
        axisRightMax = maxCum;
      } else if (curveT !== null && tr && this.options.relative_height_transition && !signed){
        maxVal = Math.max(0, ...bins.map((b) => b.total)) || 1;
        barScaleMax = 1.0;
        cumValues = this._relativeCumulative || [];
        maxCum = 1.0;
        const oldSum = tr.from.reduce((s, b) => s + (b.total || 0), 0);
        const newSum = tr.to.reduce((s, b) => s + (b.total || 0), 0);
        axisRightMax = Math.max(1, oldSum + (newSum - oldSum) * curveT);
      } else if (curveT !== null && tr){
        const oldMaxVal = Math.max(0, ...tr.from.map((b) => b.total || 0));
        const newMaxVal = Math.max(0, ...tr.to.map((b) => b.total || 0));
        maxVal = Math.max(1, oldMaxVal + (newMaxVal - oldMaxVal) * curveT);
        barScaleMax = maxVal;
        const oldSum = tr.from.reduce((s, b) => s + (b.total || 0), 0);
        const newSum = tr.to.reduce((s, b) => s + (b.total || 0), 0);
        // the running total's maximum = the last point of the running total being drawn (the line ends at the top)
        maxCum = (cumulative.length ? cumulative[cumulative.length - 1] : 0) || 1;
        cumValues = cumulative;
        axisRightMax = Math.max(1, oldSum + (newSum - oldSum) * curveT);  // the right axis numbers glide between the two totals
      } else {
        maxVal = Math.max.apply(null, totals.concat([0])) || 1;
        barScaleMax = maxVal;
        maxCum = cumulative.length ? (cumulative[cumulative.length - 1] || 1) : 1;
        cumValues = cumulative;
        axisRightMax = maxCum;
        this._cumTop = maxCum;  // the still chart's running total scale: a zoom camera's start and end (_camDraw)
      }
      if (this._tr && tr) this._tr.tot = 'morph raw ' + raw0.toFixed(3) + ' curve ' + (curveT == null ? '-' : curveT.toFixed(3)) + ' ' + (gmode || (this.options.relative_height_transition && !signed ? 'relative' : 'plain')) + ' bins ' + tr.from.length + ' -> ' + tr.to.length + ' total line top ' + Math.round(maxCum) + ' axis ' + Math.round(axisRightMax) + ' sums ' + Math.round(tr.from.reduce((s2, b2) => s2 + (b2.total || 0), 0)) + ' -> ' + Math.round(tr.to.reduce((s2, b2) => s2 + (b2.total || 0), 0));  // ANIMTRACE

      // Variation: gains above a zero line, losses under it, on one scale (the largest of each side)
      let zeroY = null, varNeg = 0, varStep = 1;
      if (signed){
        // a round step (1, 2, 2.5, 5 x 10^n) for about 4 lines, zero on one of them
        const stepOf = (span) => { const raw = span / 4, mag = Math.pow(10, Math.floor(Math.log10(raw))), f = raw / mag; return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10) * mag; };
        // the axis of some rows: [-largest loss, largest gain] on round steps (Variation), else [0, the tallest bar]
        const rangeOf = (rows, vari) => {
          let pm = 0, nm = 0;
          rows.forEach((b) => { if (b._neg) nm = Math.max(nm, b.total || 0); else pm = Math.max(pm, b.total || 0); });
          if (!vari) return [0, pm || 1];
          if (!(pm + nm > 0)) pm = 1;
          const st = stepOf(pm + nm);
          return [-Math.ceil(nm / st - 1e-9) * st, Math.ceil(pm / st - 1e-9) * st];
        };
        // during a change: the axis glides from the one of the chart before to the one after (Variation on / off, a
        // gain turning into a loss), the bars keep their real values
        let lo, hi;
        if (tr && !gmode && curveT !== null){
          const a = rangeOf(tr.from, !!tr.fromVar), b = rangeOf(tr.to, !!this.options.variation);
          lo = a[0] + (b[0] - a[0]) * curveT; hi = a[1] + (b[1] - a[1]) * curveT;
        } else [lo, hi] = rangeOf(bins, true);
        varStep = stepOf(hi - lo);
        const pm = hi, nm = -lo, top = hi, bot = -lo;
        maxVal = barScaleMax = top + bot; varNeg = bot; zeroY = padT + plotH * top / (top + bot);
      }

      const xAt = (i) => (slots && slots[i]) ? slots[i][0] : (padL + (n > 1 ? i * (plotW / (n - 1)) : plotW / 2));

      ctx.strokeStyle = this.options.show_grid === false ? 'rgba(0,0,0,0)' : (this.colors.grid || 'rgba(128,128,128,0.12)');
      ctx.lineWidth = 1;
      ctx.font = AXIS_FONT;
      ctx.textBaseline = 'middle';
      // to / from nothing: the bars keep the scale of the side with data, the axis numbers glide to the other side's scale
      let labMax = maxVal, labRight = axisRightMax;
      if (tr && gmode){
        const mx = (rows) => Math.max.apply(null, rows.map((b) => b.total || 0).concat([0])) || 1;
        const sm = (rows) => rows.reduce((a, b) => a + (b.total || 0), 0) || 1;
        labMax = DD.scaleLerp(mx(tr.from), mx(tr.to), curve0);
        labRight = DD.scaleLerp(sm(tr.from), sm(tr.to), curve0);
      }
      // The axis glides between the two real maxima (never the 0..1 scale of the relative bars);
      // on a Reviews <-> Time switch the old numbers fade out, then the new ones fade in.
      let layers = [[mode0, labMax, labRight, 1]];
      if (tr && !gmode){
        const mx = (rows) => Math.max.apply(null, rows.map((b) => b.total || 0).concat([0])) || 1;
        const sm = (rows) => rows.reduce((a, b) => a + (b.total || 0), 0) || 1;
        const oM = mx(tr.from), nM = mx(tr.to), oS = sm(tr.from), nS = sm(tr.to);
        const fmode = (tr.fromMeta && tr.fromMeta.mode) || mode0;
        if (fmode !== mode0){
          const tt = Math.max(0, Math.min(1, raw0)), e = tt * tt * (3 - 2 * tt);
          layers = [[fmode, oM, oS, Math.max(0, Math.min(1, 1 - e / 0.45))], [mode0, nM, nS, Math.max(0, Math.min(1, (e - 0.55) / 0.45))]];
        } else layers = [[mode0, DD.scaleLerp(oM, nM, curve0), DD.scaleLerp(oS, nS, curve0), 1]];
      }
      const steps = 4;
      this._axY = {max: layers[layers.length - 1][1], mode: layers[layers.length - 1][0]};  // for a picture zoom (_axisInfo)
      if (zeroY === null && DD.axisSlide && DD.axisSlide()){
        // Chart_Axis_Anim 'slide' (dd-core DD.slideTicks): round values at their heights on the scale of the moment and
        // the exact top, the grid lines with them; on a change of scale the values of both sides slide, the old fade
        // out, the new fade in
        let lf = null, lt = null, rf = null, rt = null;
        if (tr && layers.length === 1){
          const mxr = (rows) => Math.max.apply(null, rows.map((b) => b.total || 0).concat([0])) || 1;
          const smr = (rows) => rows.reduce((a, b) => a + (b.total || 0), 0) || 1;
          lf = mxr(tr.from); lt = mxr(tr.to); rf = smr(tr.from); rt = smr(tr.to);
        }
        ctx.fillStyle = this._axisInk(); ctx.textAlign = 'right';
        // a change at once (a wheel zoom: no camera, no morph): the values that come or go fade over 300 ms (the axis'
        // own fades, DD.slideAxis) instead of coming / going at once from one wheel step to the next; during a change
        // the chart knows (morph) they go with it, and the axis' state starts afresh after it
        const tag = this._traceName || 'activity', redraw = () => { if (!this._transition && !this._cam) this.draw(performance.now()); };
        const ticksOf = (st, from, to, cur, t, tg) => {
          if (from != null || layers.length > 1){ this[st] = {}; return DD.slideTicks(from != null ? from : cur, to != null ? to : cur, cur, from != null ? t : 1, steps, plotH, {tag: tg}); }
          return DD.slideAxis(this[st] || (this[st] = {}), 0, cur, {px: plotH, redraw: redraw, tag: tg});
        };
        for (const L of layers){
          if (L[3] <= 0.004) continue;
          ticksOf('_yaxL', lf, lt, L[1], curve0, tag).forEach((k) => {
            const y = padT + plotH * (1 - k.f);
            ctx.globalAlpha = k.a * L[3];
            ctx.beginPath(); ctx.moveTo(padL, y); ctx.lineTo(w - padR, y); ctx.stroke();
            ctx.fillText(formatAxis(k.v, L[0]), padL - 8, y);
          });
          if (showCumulative){
            ticksOf('_yaxR', rf, rt, L[2], curve0, tag + ' right').forEach((k) => {
              ctx.globalAlpha = 0.8 * k.a * L[3]; ctx.fillText(formatAxis(k.v, L[0]), w - 4, padT + plotH * (1 - k.f));
            });
          }
        }
        ctx.globalAlpha = 1;
      } else for (let g = 0; zeroY === null && g <= steps; g++){
        const frac = g / steps;
        const y = padT + plotH * (1 - frac);
        ctx.beginPath(); ctx.moveTo(padL, y); ctx.lineTo(w - padR, y); ctx.stroke();
        ctx.fillStyle = this._axisInk();
        ctx.textAlign = 'right';
        for (const L of layers){
          if (L[3] <= 0.004) continue;
          ctx.globalAlpha = L[3];
          ctx.fillText(formatAxis(L[1] * frac, L[0]), padL - 8, y);
          if (showCumulative){ ctx.globalAlpha = 0.8 * L[3]; ctx.fillText(formatAxis(L[2] * frac, L[0]), w - 4, y); }
        }
        ctx.globalAlpha = 1;
      }
      if (zeroY !== null){
        // Variation's grid: its round steps from the largest loss to the largest gain, the zero line stronger
        ctx.fillStyle = this._axisInk(); ctx.textAlign = 'right';
        const decs = varStep < 1 ? (varStep < 0.1 ? 2 : 1) : (varStep % 1 ? 1 : 0);
        for (let v = Math.ceil(-varNeg / varStep - 1e-6) * varStep; v <= maxVal - varNeg + varStep * 1e-6; v += varStep){
          const vz = Math.abs(v) < varStep * 1e-6 ? 0 : v, y = Math.round(zeroY - vz / maxVal * plotH) + 0.5;
          ctx.save();
          if (vz === 0) ctx.strokeStyle = rgba(this.colors.text_primary || (isDarkGlobal ? '#ffffff' : '#000000'), 0.35);
          ctx.beginPath(); ctx.moveTo(padL, y); ctx.lineTo(w - padR, y); ctx.stroke(); ctx.restore();
          ctx.fillText((vz < 0 ? '−' : '') + trimNum(Math.abs(vz), decs), padL - 8, y);
        }
      }


      this._moving = !!(tr && slots);
      // bars leaving or coming in during a change of bar count stay inside the plot (never over the axis numbers)
      const clipBars = !!(tr && slots);
      if (clipBars){ ctx.save(); ctx.beginPath(); ctx.rect(padL, 0, plotW, padT + plotH + 1); ctx.clip(); }
      const centers = [];
      this._lineBegin();
      bins.forEach((b, i) => {
        let x, barW;
        if (slots && slots[i]){
          const [centerX, slotW] = slots[i];
          barW = slotW;
          x = centerX - barW / 2;
        } else {
          const bw = plotW / n;
          const ratio = denseRatio(bw, this._baseRatio());
          barW = Math.max(1, bw * ratio);
          x = padL + i * bw + (bw - barW) / 2;
        }
        centers[i] = x + barW / 2;
        if (this._tr){ { const hh = Math.min(1, (b.total || 0) / Math.max(1e-9, barScaleMax)) * plotH * growT; if (hh > 0.5 && barW > 0.3) (this._tr.rects = this._tr.rects || []).push([x, barW, hh]); } if (i === 0) this._tr.b0 = [x, barW]; this._tr.bl = [x, barW]; this._tr.bn = bins.length; this._tr.lr = Math.min(x + barW, padL + plotW); this._tr.lh = Math.min(1, (b.total || 0) / Math.max(1e-9, barScaleMax)) * plotH * growT; this._tr.gaps = this._tr.gaps || []; if (this._tr.px != null && !(slots && slots[i])) this._tr.gaps.push(x - this._tr.px); this._tr.px = x + barW; }
        const hovHere = !this._dragging && i === this._hoverIndex;
        // the hovered bar's column, softly lit behind it (as Anki's charts): a thin or low bar is easy to aim at
        if (hovHere && DD.cu.hoverColumn){ const gap = Math.min(barW * 0.6, Math.max(1, plotW / Math.max(1, n) - barW) / 2); DD.cu.hoverColumn(ctx, x - gap, barW + gap * 2, padT, plotH, !!this.colors.is_dark, this.colors.text_primary); }
        if (zeroY !== null){ ctx.save(); if (b._neg){ ctx.translate(0, 2 * zeroY); ctx.scale(1, -1); } ctx.translate(0, zeroY - padT - plotH); }
        this._lpHov = hovHere;
        this._paintBar(ctx, b, x, barW, padT + plotH, plotH, maxVal, barScaleMax, growT);
        this._lpHov = false;
        // the hovered bar is lit here, in the bar pass: the total line is drawn over it; its top keeps
        // its rounded corners (it turned square); in the line view, a dot on the line (_lineFlush)
        if (hovHere && !this.options.line_view){
          const dk = !!this.colors.is_dark;
          const lit = (hex, y0, h, round) => {
            ctx.fillStyle = hex;
            const r = Math.min(1, barW / 2, h);
            if (round && barW >= 4 && r >= 1){
              ctx.beginPath();
              ctx.moveTo(x, y0 + h); ctx.lineTo(x, y0 + r); ctx.quadraticCurveTo(x, y0, x + r, y0);
              ctx.lineTo(x + barW - r, y0); ctx.quadraticCurveTo(x + barW, y0, x + barW, y0 + r);
              ctx.lineTo(x + barW, y0 + h); ctx.closePath(); ctx.fill();
            } else ctx.fillRect(x, y0, barW, Math.max(0, h));
          };
          if (showBreakdown){
            let cy = padT + plotH;
            const shown = this.keys.filter((k) => (b[k] || 0) > 0), last = shown[shown.length - 1];
            shown.forEach((k) => {
              const segH = Math.min(1, (b[k] || 0) / maxVal) * plotH * growT;
              lit(hoverFill(this.col(k), dk, opacityFrac), cy - segH, segH, k === last); cy -= segH;
            });
          } else {
            const bh = Math.min(1, b.total / barScaleMax) * plotH * growT;
            lit(hoverFill(this.colors.bar || '#3b82f6', dk), padT + plotH - bh, bh, true);
          }
        }
        if (zeroY !== null) ctx.restore();
        // the share FSRS expected to fail (FSRS Calibration, Recall by Elapsed / Stability): a mark across the bar where
        // its failed part should end
        // a fading mark stays on its bar as it sinks (at its mark's height, the bar empty, it hung over nothing)
        if (b._exp != null && b.total > 0 && showBreakdown) this._expMark(ctx, x, barW, padT + plotH - Math.min(1, (b._expA != null ? Math.min(b._exp, b.total) : b._exp) / maxVal) * plotH * growT, b._expA);
      });
      if (clipBars) ctx.restore();
      if (lvReveal != null){ ctx.save(); ctx.beginPath(); ctx.rect(0, 0, padL + plotW * lvReveal, h); ctx.clip(); }  // (to the average line)
      this._lineFlush(ctx, padL, padL + plotW);
      // the trend (Show Trend): during a data morph, interpolate endpoints smoothly from start trend to end trend
      // (recomputing least squares on padded/blended bins caused abrupt jumps on frame 1 and the final frame).
      if (this.options.show_trend){
        const dk = isDarkGlobal, bgc = this.colors.bg || (dk ? '#000000' : '#ffffff');
        const lk = (this.options.line_opacity_pct != null ? this.options.line_opacity_pct : 80) / 100, lw = h < 200 ? 1 : 1.2;
        let x0, y0, x1, y1, tAlpha = 1, hasSeg = false;
        if (tr && !gmode && (tr.trdA || tr.trdB)){
          const ta = tr.trdA, tb = tr.trdB, et = value0 == null ? 1 : value0;
          let tp;
          if (ta && tb){
            tp = [ta[0] + (tb[0] - ta[0]) * et, ta[1] + (tb[1] - ta[1]) * et,
                  ta[2] + (tb[2] - ta[2]) * et, ta[3] + (tb[3] - ta[3]) * et];
          } else if (ta){ tp = ta; tAlpha = 1 - et; }
          else { tp = tb; tAlpha = et; }
          this._lastTrd = tp;
          x0 = padL + tp[0] * plotW; y0 = padT + plotH - tp[1] * plotH * growT;
          x1 = padL + tp[2] * plotW; y1 = padT + plotH - tp[3] * plotH * growT;
          hasSeg = tAlpha > 0.01;
        } else {
          const trd = trendOf(bins, this.options);
          if (trd && centers[trd.i0] != null && centers[trd.i1] != null){
            const full = trd.pct ? Math.max(0, ...totals) / 100 : 1;
            const ny0 = Math.max(0, Math.min(1, trd.at(trd.i0) * full / barScaleMax));
            const ny1 = Math.max(0, Math.min(1, trd.at(trd.i1) * full / barScaleMax));
            x0 = centers[trd.i0]; y0 = padT + plotH - ny0 * plotH * growT;
            x1 = centers[trd.i1]; y1 = padT + plotH - ny1 * plotH * growT;
            this._lastTrd = plotW > 0 ? [(x0 - padL) / plotW, ny0, (x1 - padL) / plotW, ny1] : null;
            hasSeg = true;
          } else {
            this._lastTrd = null;
          }
        }
        if (hasSeg){
          const seg = () => { ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(x1, y1); ctx.stroke(); };
          ctx.save(); ctx.beginPath(); ctx.rect(padL, padT - 2, plotW, plotH + 4); ctx.clip(); ctx.lineCap = 'round';
          ctx.strokeStyle = rgba(dk ? scaleV(bgc, 1 / 1.6) : bgc, 70 / 255 * tAlpha); ctx.lineWidth = lw + 1.2; seg();
          ctx.strokeStyle = rgba(scaleV(this.colors.total_line, dk ? 1.35 : 1 / 1.25), 150 / 255 * lk * tAlpha); ctx.lineWidth = lw; seg();
          ctx.restore();
        }
      } else {
        this._lastTrd = null;
      }

      if (showCumulative && cumValues.length){
        const ptY = (v) => padT + plotH - Math.min(1, v / maxCum) * plotH * growT;

        // The line sits edge to edge (i / (n - 1)); during a transition aligned right its points glide
        // with interpolate_line_x_positions, never on the bar centres (the end left the last bar, then came back).
        const nC = cumValues.length;
        let lineXs = null;
        // also on the transition's last frame (the bins are still the padded ones there: the left-out points must stay
        // out of view, else the line's start dropped to the bottom for one frame)
        if (tr && !gmode && (tr.alignRight || tr.fromLineXs)){
          const oc = tr.from.length, nc = tr.to.length, nn = Math.max(oc, nc), FX = tr.fromLineXs;
          lineXs = [];
          for (let i = 0; i < nn; i++){
            const os = tr.alignRight ? i - (nn - oc) : i, ns = tr.alignRight ? i - (nn - nc) : i;
            // a transition that took over from another one: the points start where they were drawn
            const ox = (os >= 0 && os < oc) ? (FX ? FX[os] : (oc > 1 ? padL + plotW * os / (oc - 1) : padL + plotW * 0.5)) : (tr.alignRight ? padL - plotW * 0.05 : padL + plotW * 1.05);
            const nx = (ns >= 0 && ns < nc) ? (nc > 1 ? padL + plotW * ns / (nc - 1) : padL + plotW * 0.5) : (tr.alignRight ? padL - plotW * 0.05 : padL + plotW * 1.05);
            lineXs.push(ox + (nx - ox) * (value0 == null ? 1 : value0));
          }
        }
        const lineX = (i) => (lineXs && i < lineXs.length) ? lineXs[i] : (padL + (nC > 1 ? i * plotW / (nC - 1) : plotW / 2));
        const cpts = cumValues.map((v, i) => [lineX(i), ptY(v)]);
        this._lastLineXs = (tr && !gmode) ? cpts.map((q) => q[0]) : null;
        if (this._tr){ const ev = edgeYs(cpts, padL, padL + plotW); this._tr.cs = [padL, ev[0]]; this._tr.ce = [padL + plotW, ev[1]]; this._tr.cn = cpts.length; this._tr.tail = cpts.slice(-3); this._tr.pr = padL + plotW;
          this._tr.mid = 'plot 1/4,1/2,3/4 y ' + [0.25, 0.5, 0.75].map((f) => Math.round(edgeYs(cpts, padL + plotW * f, padL + plotW * f)[0])); }  // ANIMTRACE
        const lineK = (this.options.line_opacity_pct != null ? this.options.line_opacity_pct : 80) / 100;
        ctx.save();
        ctx.beginPath();
        ctx.rect(padL, padT - 2, plotW, plotH + 2);
        ctx.clip();
        ctx.beginPath();
        smoothPath(ctx, cpts);
        ctx.lineTo(cpts[cpts.length - 1][0], padT + plotH);
        ctx.lineTo(cpts[0][0], padT + plotH);
        ctx.closePath();
        // as Anki's charts draw it (.cumulative-overlay): a flat pale area in the text's colour, its edge a faint dark
        // line; the Total / Average Lines setting scales both (its default, 80 %, gives Anki's own values)
        totalArea(ctx, cpts, this.colors, isDarkGlobal, lineK, (this.options.total_line_pct || 0) / 100);
        ctx.restore();
      }

      this._lastAvgY = null;
      this._lastAvgValue = 0;
      if (showAverage){
        const avgOf = (arr) => { const r = this.options.avg_on_active_days ? arr.filter((v) => v > 0) : arr; return r.length ? r.reduce((a, b) => a + b, 0) / r.length : 0; };
        let avg = avgOf(totals), yT = null, aF = 1;
        if (tr){
          // during a transition the line glides from its old height (old average / old max) to
          // its new one with t; never the average of the bars in between (it jumps as days become active)
          const ov = tr.from.map((b) => b.total || 0), nv = tr.to.map((b) => b.total || 0);
          const oa = avgOf(ov), na = avgOf(nv), om = Math.max(0, ...ov) || 1, nm = Math.max(0, ...nv) || 1;
          const yo = oa > 0 ? padT + plotH - oa / om * plotH : padT + plotH, yn = na > 0 ? padT + plotH - na / nm * plotH : padT + plotH;
          yT = yo + (yn - yo) * curve0;
          avg = Math.max(oa, na);
          const tt = Math.max(0, Math.min(1, curve0));
          if (gmode === 'to_empty') aF = 1 - tt * tt * (3 - 2 * tt); else if (gmode === 'from_empty') aF = tt * tt * (3 - 2 * tt);
        }
        if (avg > 0){
          const y = yT != null ? yT : padT + plotH - Math.min(1, avg / barScaleMax) * plotH * growT;
          this._lastAvgY = y; if (this._tr) this._tr.avg = y;
          this._lastAvgValue = avg;
          const hov = !!this._hoverAvg;
          const small = h < 200;
          const lw = small ? (hov ? 1.3 : 0.9) : (hov ? 1.5 : 1.1);
          const dash = small ? 2.5 : 3.0;
          const yy = Math.trunc(y) + 0.0;
          const bgc = this.colors.bg || (isDarkGlobal ? '#000000' : '#ffffff');
          ctx.save();
          ctx.globalAlpha = aF;
          ctx.setLineDash([dash, dash]);
          ctx.lineCap = 'butt';
          ctx.strokeStyle = rgba(isDarkGlobal ? scaleV(bgc, 1 / 1.6) : bgc, 90 / 255);
          ctx.lineWidth = lw + 1.2;
          ctx.beginPath(); ctx.moveTo(padL, yy); ctx.lineTo(w - padR, yy); ctx.stroke();
          ctx.strokeStyle = rgba(scaleV(this.colors.total_line, isDarkGlobal ? 1.35 : 1 / 1.25), (hov ? 235 : 175) / 255 * ((this.options.line_opacity_pct != null ? this.options.line_opacity_pct : 80) / 100));
          ctx.lineWidth = lw;
          ctx.beginPath(); ctx.moveTo(padL, yy); ctx.lineTo(w - padR, yy); ctx.stroke();
          ctx.restore();
        }
      }
      if (lvReveal != null) ctx.restore();  // (the line's intro)

      if (this.options.now_start != null){
        // Due Today: a dashed line at the current time of the day
        const frac = (Date.now() / 1000 - this.options.now_start) / 86400;
        if (frac >= 0 && frac <= 1){
          const nx = padL + plotW * frac;
          ctx.save(); ctx.setLineDash([5, 5]); ctx.strokeStyle = rgba(this.colors.text_primary || '#888888', 170 / 255); ctx.lineWidth = 1.2;
          ctx.beginPath(); ctx.moveTo(nx, padT); ctx.lineTo(nx, padT + plotH); ctx.stroke(); ctx.restore();
        }
      }

      const drawLabels = (labels, alpha) => {
        const n = labels.length;
        if (n <= 0 || alpha <= 0) return;
        ctx.save(); ctx.globalAlpha = alpha;
        ctx.textBaseline = 'middle';
        ctx.font = AXIS_FONT;
        ctx.fillStyle = this._axisInk();
        const yL = h - padB + 10;
        const sw = ctx.measureText(labels[0]).width, ew = ctx.measureText(labels[n - 1]).width;
        ctx.textAlign = 'left'; ctx.fillText(labels[0], padL, yL);
        ctx.textAlign = 'right'; ctx.fillText(labels[n - 1], w - padR, yL);
        if (n > 2){
          const target = Math.max(1, Math.floor(w / 120));
          if (target > 2){
            const step = Math.floor(n / (target - 1));
            if (step > 0){
              const sBox = [padL, padL + sw + 15], eBox = [w - padR - ew - 15, w - padR];
              for (let i = step; i < n - Math.floor(step / 2); i += step){
                if (i >= n - 1) break;
                const xc = padL + i * (plotW / (n - 1));
                const lw = ctx.measureText(labels[i]).width;
                const a = xc - lw / 2 - 5, b = a + lw + 10;
                if ((a < sBox[1] && b > sBox[0]) || (a < eBox[1] && b > eBox[0])) continue;
                ctx.textAlign = 'center'; ctx.fillText(labels[i], xc, yL);
              }
            }
          }
        }
        ctx.restore();
      };
      if (this.daily.length){
        // date marks a round number of days apart, as the zoom camera draws them (_drawDays): they slide during a zoom
        const v0 = this._visibleOffset(), v1 = v0 + Math.max(1, this._visibleDaily().length);
        this._drawnV = [v0, v1];
        const A0 = tr0 && tr0.ax0 && tr0.ax0.t1 > tr0.ax0.t0 && raw0 < 1 ? tr0.ax0 : null, b0 = A0 && !A0.idxAxis ? this._T(v0) : null;
        if (A0 && !A0.idxAxis && b0 != null){
          // a change of period (or deck): the time window goes from the old view's to the new one with the bars, the
          // dates on it; the old ones leave, the new ones come, those in both stay
          const sm = (x) => { x = Math.max(0, Math.min(1, x)); return x * x * (3 - 2 * x); };
          const e = Math.max(0, Math.min(1, curve0 != null ? curve0 : raw0)), b1 = this._T(v1);
          const w0 = A0.t0 + (b0 - A0.t0) * e, w1 = A0.t1 + (b1 - A0.t1) * e;
          const mb = this._sub() ? DD.timeMarks(w0, w1, plotW) : this._dayTicks(v0, v1, this._dayStep(v0, v1, plotW)).map((i) => ({t: this._T(i + 0.5), label: this.daily[i].date}));
          const ma = A0.sub ? DD.timeMarks(w0, w1, plotW) : (A0.marks || []);
          const key = (m) => m.label + '@' + Math.round(m.t / 60000), inB = new Set(mb.map(key)), inA = new Set(ma.map(key)), marks = [];
          ma.forEach((m) => { const kept = inB.has(key(m)); marks.push({t: m.t, label: m.label, a: (m.a != null ? m.a : 1) * (kept ? 1 : 1 - sm(e / 0.67)), p: kept ? 2 : 1 - e}); });
          mb.forEach((m) => { if (!inA.has(key(m))) marks.push({t: m.t, label: m.label, a: (m.a != null ? m.a : 1) * sm((e - 0.33) / 0.67), p: e}); });
          ctx.save(); ctx.font = AXIS_FONT; ctx.fillStyle = this._axisInk();
          DD.placeMarks(ctx, marks, (t) => padL + (t - w0) / Math.max(1, w1 - w0) * plotW, padL, padL + plotW, h - padB + 10);
          ctx.restore();
        } else if (A0){
          // non-dated charts (FSRS Loss by Fatigue, Answer Time, Interval Ratings, Added, ...): identical labels glide
          // smoothly to their new X position, old-only labels fade out, new-only labels fade in
          const sm = (x) => { x = Math.max(0, Math.min(1, x)); return x * x * (3 - 2 * x); };
          const e = Math.max(0, Math.min(1, curve0 != null ? curve0 : raw0));
          const span = Math.max(1e-6, v1 - v0);
          const oldM = A0.idxAxis
            ? (A0.marks || [])
            : (A0.marks || []).map((m) => ({f: (m.t - A0.t0) / Math.max(1, A0.t1 - A0.t0), label: String(m.label)}));
          const newM = this._dayTicks(v0, v1, this._dayStep(v0, v1, plotW))
            .filter((i) => this.daily[i] && this.daily[i].date != null && String(this.daily[i].date) !== '')
            .map((i) => ({f: (i + 0.5 - v0) / span, label: String(this.daily[i].date), k: i - v0}));
          const cntA = {}, cntB = {}, byB = {};
          oldM.forEach((m) => { cntA[m.label] = (cntA[m.label] || 0) + 1; });
          newM.forEach((m) => { cntB[m.label] = (cntB[m.label] || 0) + 1; byB[m.label] = m; });
          const matched = new Set(), marks = [];
          // index axes (Answer Time, Added, ...): each label sits under its own bar slot, the bars' centres drawn this
          // frame. An old label is under the bar at its old index, a new one under its new index; a label on both sides
          // glides from one to the other on the bars' curve. At e = 0 and e = 1 they are exactly where the bars are, so
          // nothing moves at the start of the change
          const byIdx = !!A0.idxAxis && oldM.length > 0 && oldM.every((m) => m.j != null) && newM.every((m) => m.k != null);
          if (byIdx){
            const nB = bins.length;
            const oldPad = tr0.alignRight ? nB - tr0.from.length : 0, newPad = tr0.alignRight ? nB - tr0.to.length : 0;
            // a label is under its row; its bar is the bin holding that row (bars of 2 seconds or more: row 20 is bar 10).
            // It keeps its place from that bar's centre at rest (0 = old side, 1 = new side), scaled by the bars'
            // spacing of the moment: exactly where it was at e = 0, where it stays at e = 1
            const ab = this.options.adaptive_binning;
            const bsA = Math.max(1, A0.bs || binSize(Math.max(1, A0.vis || tr0.from.length), ab)), bsB = Math.max(1, binSize(Math.max(1, Math.round(span)), ab));
            const stepNow = (i, d) => { const a = centers[i], b = centers[i + 1], c = centers[i - 1]; return (a != null && b != null) ? b - a : (a != null && c != null) ? a - c : d; };
            const follow = (row, f, pad, nBins, bs) => {
              const st = plotW / Math.max(1, nBins), b = Math.floor(row / bs), i = pad + b, c = centers[i];
              const rest = padL + f * plotW;
              return c != null ? c + (rest - (padL + (b + 0.5) * st)) * stepNow(i, st) / st : rest;
            };
            const cOld = (m) => follow(m.j, m.f, oldPad, tr0.from.length, bsA);
            const cNew = (m) => follow(m.k, m.f, newPad, tr0.to.length, bsB);
            const newByLabel = {};
            newM.forEach((m) => { if (newByLabel[m.label] == null) newByLabel[m.label] = m; });
            const kept = new Set();
            oldM.forEach((m) => {
              const nm = newByLabel[m.label];
              if (nm && !kept.has(m.label)){
                kept.add(m.label);
                const a0 = cOld(m), a1 = cNew(nm);
                marks.push({x: a0 + (a1 - a0) * e, label: m.label, a: 1, p: 2});
              } else marks.push({x: cOld(m), label: m.label, a: 1 - sm(e / 0.67), p: 1 - e});
            });
            newM.forEach((m) => { if (!kept.has(m.label)) marks.push({x: cNew(m), label: m.label, a: sm((e - 0.33) / 0.67), p: e}); });
          }
          const oldLoop = byIdx ? [] : oldM, newLoop = byIdx ? [] : newM;
          oldLoop.forEach((m) => {
            if (cntA[m.label] === 1 && cntB[m.label] === 1){
              const nb = byB[m.label];
              matched.add(m.label);
              marks.push({x: padL + (m.f + (nb.f - m.f) * e) * plotW, label: m.label, a: 1, p: 2});
            } else {
              marks.push({x: padL + m.f * plotW, label: m.label, a: 1 - sm(raw0 / 0.35), p: 1 - raw0});
            }
          });
          newLoop.forEach((m) => {
            if (!matched.has(m.label)) marks.push({x: padL + m.f * plotW, label: m.label, a: sm((raw0 - 0.3) / 0.45), p: raw0});
          });
          ctx.save(); ctx.font = AXIS_FONT; ctx.fillStyle = this._axisInk();
          DD.placeMarks(ctx, marks, null, padL, padL + plotW, h - padB + 10);
          ctx.restore();
        } else if (this._sub()) this._drawTimes(ctx, v0, v1, padL, padL + plotW, h - padB + 10);
        else {
          const marks = this._dayTicks(v0, v1, this._dayStep(v0, v1, plotW)).map((i) => ({i: i, a: 1, p: 1}));
          this._drawDays(ctx, marks, (x) => padL + (x - v0) / (v1 - v0) * plotW, padL, padL + plotW, h - padB + 10);
        }
      } else if (tr0 && tr0.ax0 && tr0.ax0.marks && tr0.ax0.marks.length && raw0 < 1){
        // transitioning to an empty deck: fade out the previous tick marks in place
        const sm = (x) => { x = Math.max(0, Math.min(1, x)); return x * x * (3 - 2 * x); };
        const a = 1 - sm(raw0 / 0.35);
        if (a > 0.003){
          const A0 = tr0.ax0;
          const marks = A0.marks.map((m) => ({
            x: padL + (A0.idxAxis ? m.f : (m.t - A0.t0) / Math.max(1, A0.t1 - A0.t0)) * plotW,
            label: String(m.label), a: a, p: 1,
          }));
          ctx.save(); ctx.font = AXIS_FONT; ctx.fillStyle = this._axisInk();
          DD.placeMarks(ctx, marks, null, padL, padL + plotW, h - padB + 10);
          ctx.restore();
        }
      } else if (tr0 && tr0.from.length){  // to / from an empty deck too
        // the axis dates: the old ones fade out, then the new ones fade in (as the zoom camera does; crossed, both
        // would be half there at once and read as one jumble). The same dates stay as they are
        // the new side's dates as the chart will end (the in-between bars mix both sides: dates laid on them would
        // jump to the new ones at the end)
        const la = tr0.from.map((b) => b.label || ''), lb = (tr0.to && tr0.to.length ? tr0.to : bins).map((b) => b.label || '');
        if (la.join('|') === lb.join('|')) drawLabels(lb, 1);
        else {
          const sm = (x) => { x = Math.max(0, Math.min(1, x)); return x * x * (3 - 2 * x); };
          drawLabels(la, 1 - sm(raw0 / 0.35)); drawLabels(lb, sm((raw0 - 0.3) / 0.45));
        }
      } else drawLabels(bins.map((b) => b.label || ''), 1);
      // dev trace: the dates changed from one frame to the next without the fade above (a jump), and why
      if (DD.dev){
        const sig = bins.length + ':' + (bins[0] && bins[0].label) + '..' + (bins[bins.length - 1] && bins[bins.length - 1].label);
        if (this._labSig && sig !== this._labSig && !(tr0 && tr0.from.length))
          DD.trace('ANIMTRACE ' + (this._traceName || 'activity') + ' DATES JUMP ' + this._labSig + ' -> ' + sig + ' (transition ' + (tr0 ? 'yes' : 'no') + (gmode ? ', ' + gmode : '') + (tr0 && !tr0.from.length ? ', from nothing' : '') + ', camera ' + !!this._cam + ', last call: ' + (this._lastCall || '?') + ')');
        this._labSig = sig;
      }

      if (!this._dragging && this._hoverIndex != null && this._hoverIndex < n && bins[this._hoverIndex]){
        const hi = this._hoverIndex;
        const hb = bins[hi];
        let hx, hBarW;
        if (slots && slots[hi]){
          const [centerX, slotW] = slots[hi];
          hBarW = slotW; hx = centerX - hBarW / 2;
        } else {
          const bw = plotW / n;
          const ratio = denseRatio(bw, this._baseRatio());
          hBarW = Math.max(1, bw * ratio);
          hx = padL + hi * bw + (bw - hBarW) / 2;
        }
        const isDark = !!this.colors.is_dark;
        let markers = null;

        if (showBreakdown){
          let curY = padT + plotH;
          markers = [];
          this.keys.forEach((k) => {
            const val = hb[k] || 0;
            if (val <= 0) return;
            const segH = Math.min(1, val / maxVal) * plotH * growT;
            const y = curY - segH;
            markers.push({ y: y + segH / 2, color: this.col(k) });
            curY = y;
          });
        }

        const crossX = hx + hBarW / 2;
        ctx.save();
        ctx.setLineDash([4, 2]);
        ctx.strokeStyle = rgba(this.colors.text_secondary || this.colors.axis_text, isDark ? 0.39 : 0.33);
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(crossX, padT);
        ctx.lineTo(crossX, padT + plotH);
        ctx.stroke();
        ctx.restore();

        const drawMarker = (my, color) => {
          ctx.beginPath();
          ctx.arc(crossX, my, 4, 0, Math.PI * 2);
          ctx.fillStyle = color;
          ctx.fill();
          ctx.lineWidth = 1.5;
          ctx.strokeStyle = this.colors.tooltip_border || 'rgba(128,128,128,0.6)';
          ctx.stroke();
        };
        // One dot per colour of the hovered bar; a bar of a single colour gets none (the dot told nothing).
        if (markers && markers.length > 1) markers.forEach((m) => drawMarker(m.y, m.color));

        this._updateTooltipDom(hb, showBreakdown, showCumulative, cumulative[hi]);
      } else {
        this._hideTooltipDom();
      }

      if (this._hoverAvg && this._lastAvgY != null){
        this._updateAvgLabelDom(this._lastAvgValue, this._lastAvgY, padL);
      } else if (this.avgLabelEl){
        this.avgLabelEl.style.display = 'none';
      }

      if (this._dragging && this._dragStartX !== null && this._dragCurrentX !== null){
        const x0 = Math.min(this._dragStartX, this._dragCurrentX);
        const x1 = Math.max(this._dragStartX, this._dragCurrentX);
        const acc = this.colors.accent || '#3b82f6';  // theme accent, alpha 20 / 200 (draw_selection_overlay)
        ctx.fillStyle = rgba(acc, 20 / 255);
        ctx.fillRect(x0, padT, x1 - x0, plotH);
        ctx.strokeStyle = rgba(acc, 200 / 255);
        ctx.lineWidth = 1.5;
        ctx.strokeRect(x0 + 0.75, padT + 0.75, Math.max(0, (x1 - x0) - 1.5), Math.max(0, plotH - 1.5));
      }
    }
  }


  const OPTIONS = {show_breakdown: true, show_average: true, avg_on_active_days: true, show_cumulative: true,
    metric_mode: 'reviews', show_percent: false, adaptive_binning: true, relative_height_transition: false,
    chart_opacity_pct: 71};

  const activityMod = {
    mount: function(el, ctx){
      el.innerHTML = '<div class="dd-plot"><canvas></canvas><div class="dd-tip"></div><div class="dd-avg"></div></div>';
      const plot = el.firstChild;
      // a click on a bar shows its cards in the browser (the bar's date; Added: cards added)
      // A bar of several days (adaptive binning): all its days (the label "first - last"), not its first day alone.
      // The extra charts (extras.js) say what their bars hold: ctx.browse(the bar's rows [a, b), its label)
      plot._ddBrowse = function(){
        const c = plot._chart; if (!c) return null;
        const i = c._hoverIndex; if (i == null || i < 0 || !c._bins || !c._bins[i]) return null;
        const r = c._binAbsRanges && c._binAbsRanges[i], D = c.daily || [];
        let label = c._bins[i].label || '';
        if (r && r[1] - r[0] > 1 && D[r[0]] && D[r[1] - 1] && D[r[0]].date && D[r[1] - 1].date) label = D[r[0]].date + ' - ' + D[r[1] - 1].date;
        if (ctx.browse) return ctx.browse(r || [i, i + 1], label);
        return {kind: ctx.kind === 'added' ? 'added' : 'reviewed', label: label};
      };
      const head = ctx.head;
      const statEl = head && head.querySelector('.dd-stat'), pillsEl = head && head.querySelector('.dd-pills');
      let trendTxt = '', lastStat = null;
      function headStats(rows, o){
        lastStat = [rows, o];
        headStats0(rows, o);
        if (statEl && trendTxt) statEl.textContent = (statEl.textContent ? statEl.textContent + '  \u00b7  ' : '') + trendTxt;
      }
      function headStats0(rows, o){
        if (!statEl) return;
        if (ctx.statText){ statEl.textContent = ctx.statText(rows, o); return; }
        if (isAdded){
          let tot = 0, act = 0;
          (rows || []).forEach(function(d){ const v = d.reviews || 0; tot += v; if (v > 0) act += 1; });
          const per = o.avg_on_active_days ? (act || 1) : ((rows || []).length || 1);
          statEl.textContent = DD.t('Total: {count} added', {count: formatNum(tot)}) + '  \u00b7  ' + DD.t('Average: {count}/day', {count: trimNum(tot / per, 1)});
          return;
        }
        let tot = 0, act = 0, n = 0;
        (rows || []).forEach(function(d){ const v = o.metric_mode === 'time' ? (d.time_ms || 0) / 60000 : (d.reviews || 0); tot += v; if (v > 0){ act += 1; } n += 1; });
        const per = o.avg_on_active_days ? (act || 1) : (n || 1);
        const avg = tot / per;
        const fmtT = function(m){ return m < 60 ? DD.t('{value} min', {value: trimNum(m, 1)}) : DD.t('{value} h', {value: trimNum(m / 60, 1)}); };
        statEl.textContent = o.metric_mode === 'time'
          ? DD.t('Total: {value}', {value: fmtT(tot)}) + '  \u00b7  ' + DD.t('Avg: {value}', {value: DD.t('{value}/day', {value: fmtT(avg)})})
          : DD.tn('Total: {count} review', 'Total: {count} reviews', tot, {count: formatNum(tot)}) + '  \u00b7  ' + DD.t('Avg: {value}', {value: DD.t('{value}/day', {value: trimNum(avg, 1)})});
      }
      let curOpts = Object.assign({}, OPTIONS, ctx.options || {});
      const mapRows = ctx.mapRows || function(r){ return r; };
      const isAdded = ctx.kind === 'added';
      let derived = ctx.derive ? ctx.derive(ctx.data, curOpts) : null;
      let curRows = derived ? derived.rows : mapRows(ctx.data.rows);
      if (derived) Object.assign(curOpts, derived.options);
      headStats(curRows, curOpts);
      if (head){
        const acc = (DD.theme.chart && DD.theme.chart.accent) || '#3b82f6';
        head.style.setProperty('--dd-accent-b', rgba(acc, 0.6));
        head.style.setProperty('--dd-accent-f', rgba(acc, 0.12));
      }
      function pill(label, key){
        const b = document.createElement('button');
        b.className = 'dd-pill' + (curOpts[key === 'time' ? 'metric_mode' : 'show_breakdown'] === (key === 'time' ? 'time' : true) ? ' on' : '');
        b.textContent = label;
        b.addEventListener('click', function(){
          let o;
          if (key === 'time') o = {metric_mode: curOpts.metric_mode === 'time' ? 'reviews' : 'time'};
          else o = {show_breakdown: !curOpts.show_breakdown};
          Object.assign(curOpts, o);
          b.classList.toggle('on');
          inst.setOptions(o);
          headStats(curRows, curOpts);
          DD.call('set_setting', {section: 'activity', key: key === 'time' ? 'show_time_axis' : 'breakdown_enabled', value: key === 'time' ? curOpts.metric_mode === 'time' : !!curOpts.show_breakdown}).catch(function(){});
        });
        pillsEl.appendChild(b);
      }
      if (pillsEl && ctx.pills) ctx.pills(pillsEl, function(o, persist){
        Object.assign(curOpts, o);
        if (ctx.derive){ derived = ctx.derive(ctx.data, curOpts); curRows = derived.rows; Object.assign(curOpts, derived.options); chart.updateData(curRows, derived.options); }
        else inst.setOptions(o);
        headStats(chart._visibleDaily(), curOpts); state.last = true; DD.frame.kick();
        if (persist) DD.call('set_setting', {section: ctx.type, key: persist[0], value: persist[1]}).catch(function(){});
      }, curOpts);
      else if (pillsEl && !isAdded){ pill('Breakdown by Type', 'bd'); pill('Time', 'time'); }
      SETTINGS.bin_scale = (DD.settings && DD.settings.bin_scale) || 100;
      const chart = new Chart(plot, curRows, DD.theme.chart, Object.assign({}, OPTIONS, {relative_height_transition: ctx.kind !== 'added'}, ctx.options || {}, derived ? derived.options : {})); plot._chart = chart;
      if (!ctx.animate) chart.progress = 1;
      chart.onTrend = function(){ const t = trendText(chart); if (t !== trendTxt){ trendTxt = t; if (lastStat) headStats(lastStat[0], lastStat[1]); } };
      chart.onTrend();
      const state = {revealStart: null, last: true};
      function frame(now){
        // its intro not played yet (it waited out of view) and new data came meanwhile (a deck / period change): the
        // intro shows the new data, once; the change's transition played first, then the intro again (twice)
        if (chart.progress < 1 && state.revealStart === null && chart._transition){
          if (DD.dev) DD.trace('ANIMTRACE ' + (chart._traceName || 'activity') + ' intro not played yet: the transition dropped, the intro shows the new data (it played twice)');
          chart._transition = null; chart._lastRenderedBins = chart._bins;
        }
        if (chart._replayIntro){ chart._replayIntro = false; state.revealStart = null; chart._transition = null; chart._lastRenderedBins = chart._bins; }
        if (chart.progress < 1 && !chart._transition){
          if (state.revealStart === null) state.revealStart = now;
          chart.progress = Math.min(1, (now - state.revealStart) / DD.intro(500));
        }
        const needs = chart.progress < 1 || !!chart._transition || !!chart._cam || !!chart._lvMix || chart._dragging || chart._hoverIndex != null || chart._hoverAvg;
        if (needs || state.last) chart.draw(now);
        state.last = needs;
        return needs;
      }
      const wake = function(){ DD.frame.kick(); };
      ['mousemove', 'mouseleave', 'mousedown', 'dblclick', 'wheel'].forEach(function(n){ plot.addEventListener(n, wake, true); });
      window.addEventListener('mouseup', wake);
      const resizer = new ResizeObserver(function(){ DD.frame.resized(frame, function(){ chart._resize(); state.last = true; }); });
      DD.frame.observe(resizer, plot);
      if (!ctx.animate) chart.draw(performance.now());
      DD.frame.add(frame);
      const inst = {
        _chart: chart,
        update: function(data, mode){
          chart._lastCall = 'update ' + (mode || 'deck') + ' at ' + Math.round(performance.now());
          if (DD.dev) DD.trace('ANIMTRACE ' + (chart._traceName || 'activity') + ' update ' + (mode || 'deck') + ' at ' + Math.round(performance.now()) + ' calm=' + (DD.calm ? DD.calm() : 1));
          if (ctx.derive){ ctx.data = data; derived = ctx.derive(data, curOpts); curRows = derived.rows; Object.assign(curOpts, derived.options); headStats(curRows, curOpts); chart.updateData(curRows, derived.options, mode); }
          else { curRows = mapRows(data.rows); headStats(curRows, curOpts); chart.updateData(curRows, null, mode); }
          state.last = true; DD.frame.kick();
        },
        seriesChoices: function(){ return derived && derived.options && derived.options.keys ? derived.options.keys.map(function(k){ return [k, (derived.options.labels || {})[k] || k]; }) : []; },
        setOptions: function(o){
          if (ctx.derive && o && o.hidden_series !== undefined && ctx.data){
            Object.assign(curOpts, o); derived = ctx.derive(ctx.data, curOpts); curRows = derived.rows; Object.assign(curOpts, derived.options);
            headStats(curRows, curOpts); chart.updateData(curRows, derived.options);
          } else chart.setOptions(o);
          // Reviews / Time, breakdown, hidden types: the dots follow (read again)
          if (inst.dots && inst.dots.visible()){
            const m = chart.options || {};
            inst.dots.setMode(m.metric_mode === 'time' ? 'time' : 'reviews', !!m.show_breakdown);  // the dots glide at once (pinned cards have no DD.refreshDots)
            if (DD.refreshDots) DD.refreshDots(true);
          }
          state.last = true; DD.frame.kick();
        },
        setTheme: function(){ chart.colors = DD.theme.chart; state.last = true; DD.frame.kick(); },
        destroy: function(){ DD.frame.remove(frame); resizer.disconnect(); window.removeEventListener('mouseup', wake); el.innerHTML = ''; if (head){ if (statEl) statEl.textContent = ''; if (pillsEl) pillsEl.innerHTML = ''; } },
      };
      // zoom link with the other charts (app.js DD.zoomSync) and the bar under the plot
      inst.zoom = {
        count: function(){ return chart.daily.length; },
        label: function(i){ const r = chart.daily[i]; return r ? r.date : null; },
        get: function(){ return chart.zoomRange ? chart.zoomRange.slice() : null; },
        set: function(a, b){
          chart._lastCall = 'zoom.set ' + a + ',' + b + ' at ' + Math.round(performance.now());
          if (DD.dev) DD.trace('ANIMTRACE ' + (chart._traceName || 'activity') + ' zoom.set ' + a + ',' + b + ' noAnim=' + !!DD._noAnim + ' at ' + Math.round(performance.now()));
          chart._zoomTo(a == null ? null : [a, b]); headStats(chart._visibleDaily ? chart._visibleDaily() : curRows, curOpts);
          state.last = true; DD.frame.kick(); if (inst.zoom.bar) inst.zoom.bar();
        },
        onChange: null, onOutLimit: null,
        step: function(span){ return chart.options.adaptive_binning !== false ? binSize(span, true) : 1; },
        // adaptive zoom: new rows over range (null = all), morph anchored left / right
        swap: function(data, range, alignRight){
          let rows;
          if (ctx.derive){ ctx.data = data; derived = ctx.derive(data, curOpts); rows = derived.rows; Object.assign(curOpts, derived.options); }
          else rows = mapRows(data.rows);
          curRows = rows;
          chart.swapData(rows, range, alignRight, ctx.derive ? derived.options : null);
          headStats(chart._visibleDaily(), curOpts); state.last = true; DD.frame.kick(); if (inst.zoom.bar) inst.zoom.bar();
        },
      };
      // the chart as it is now, for a picture zoom: the running camera / transition ended first
      inst.zoom.picture = function(){
        chart._cam = null; chart._transition = null;
        chart.draw(performance.now());
        const c = document.createElement('canvas'); c.width = chart.canvas.width; c.height = chart.canvas.height; c.getContext('2d').drawImage(chart.canvas, 0, 0);
        return {img: c, ml: chart._padL, mr: chart._padR, ph: chart.h - chart._padB(), ax: chart._axisInfo()};
      };
      inst.zoom.snap = function(){
        const c = document.createElement('canvas'); c.width = chart.canvas.width; c.height = chart.canvas.height; c.getContext('2d').drawImage(chart.canvas, 0, 0);
        return {img: c, ml: chart._padL, mr: chart._padR, ph: chart.h - chart._padB(), ax: chart._axisInfo()};
      };
      inst.zoom.canvas = chart.canvas;
      inst.zoom.rows = function(){ return chart.daily; };
      inst.zoom.mode = function(){ return {mode: chart.options.metric_mode, breakdown: !!chart.options.show_breakdown}; };
      // Activity itself (not Added, not the extra charts of days): one dot per review once zoomed to 3 hours or less
      chart._traceName = ctx.type || ctx.kind || (ctx.derive ? 'extra' : 'activity');
      if (!ctx.kind && !ctx.derive && DD.reviewDots) inst.dots = DD.reviewDots(plot, {color: function(k){ return chart.col(k); }, onZoomOut: function(f){ if (DD._dotsZoomOut) DD._dotsZoomOut(f); }});
      chart.onZoomOutLimit = function(){ if (inst.zoom.onOutLimit) inst.zoom.onOutLimit(); };
      chart.onZoom = function(){ headStats(chart._visibleDaily(), curOpts); if (inst.zoom.bar) inst.zoom.bar(); if (inst.zoom.onChange) inst.zoom.onChange(chart.zoomRange ? chart.zoomRange.slice() : null); };
      if (ctx.noZoom){ delete inst.zoom; chart.onZoom = function(){}; chart._zoomDisabled = true; }
      else if (DD.zoomBar) DD.zoomBar(plot, inst.zoom);
      return inst;
    },
  };
  DD.registerChart('activity', activityMod);
  DD.dailyMount = function(el, ctx){ return activityMod.mount(el, ctx); }; // the extra charts of days (extras.js)
  // Added: Activity's chart over one series (cards added per day), bars shaded by value, no breakdown.
  DD.registerChart('added', {
    mount: function(el, ctx){
      return activityMod.mount(el, Object.assign({}, ctx, {kind: 'added',
        options: Object.assign({chart_opacity_pct: 100}, ctx.options || {}, {show_breakdown: false, added_style: true, show_average: true, avg_on_active_days: true, show_cumulative: true, metric_mode: 'reviews'}),
        mapRows: function(rows){ return (rows || []).map(function(r){ return {date: r.pretty_date, reviews: r.count || 0}; }); }}));
    },
  });
  // Shared with the other canvas charts (discrete.js ...).
  DD.cu = {formatNum: formatNum, trimNum: trimNum, formatAxis: formatAxis, smoothPath: smoothPath, scaleV: scaleV,
    hexToRgb: hexToRgb, rgba: rgba, hoverFill: hoverFill, smoothK: smoothK, easeOutQuart: easeOutQuart,
    easeInOutCubic: easeInOutCubic, smootherstep: smootherstep, interpolateBarSlots: interpolateBarSlots,
    AXIS_FONT: AXIS_FONT};
})();
