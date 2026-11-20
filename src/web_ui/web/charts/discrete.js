// Discrete bar charts (Future Due, Review Intervals ...): bars per bin, a cumulative curve over them,
// left and right axes.
(function(){
  'use strict';
  const DD = window.DD;
  const U = DD.cu;
  const LINE_PCT = 80, GRAD_PCT = 43;          // Chart_Line_Opacity / Chart_Bar_Gradient defaults
  const TEXT_PX = 12;                          // 9 pt
  const FONT = TEXT_PX + 'px "Segoe UI",-apple-system,BlinkMacSystemFont,sans-serif';
  const FONT_X = '10px "Segoe UI",-apple-system,BlinkMacSystemFont,sans-serif';

  function parseColor(c){
    c = String(c || '#888888').trim();
    let m = /^rgba?\(([^)]+)\)$/.exec(c);
    if (m){
      const p = m[1].split(',').map(function(v){ return parseFloat(v); });
      return {r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1};
    }
    const o = U.hexToRgb(c);
    return {r: o.r, g: o.g, b: o.b, a: 1};
  }
  function css(c, a){ return 'rgba(' + Math.round(c.r) + ',' + Math.round(c.g) + ',' + Math.round(c.b) + ',' + a + ')'; }
  function hex2(o){ return '#' + [o.r, o.g, o.b].map(function(v){ return Math.max(0, Math.min(255, Math.round(v))).toString(16).padStart(2, '0'); }).join(''); }

  // HSL (hue 0-359, saturation/lightness 0-255 integers)
  function toHsl(hex){
    const c = U.hexToRgb(hex);
    const r = c.r, g = c.g, b = c.b;
    const mx = Math.max(r, g, b), mn = Math.min(r, g, b), d = mx - mn;
    const l = (mx + mn) / 2;
    let h = 0, s = 0;
    if (d){
      s = d / (255 - Math.abs(2 * l - 255));
      if (mx === r) h = (((g - b) / d) % 6 + 6) % 6; else if (mx === g) h = (b - r) / d + 2; else h = (r - g) / d + 4;
      h *= 60;
    }
    return {h: h, s: Math.round(s * 255), l: Math.floor(l)};
  }
  function fromHsl(h, s, l){
    s = s / 255; l = l / 255;
    const c = (1 - Math.abs(2 * l - 1)) * s, x = c * (1 - Math.abs((h / 60) % 2 - 1)), m = l - c / 2;
    const sec = Math.floor(h / 60) % 6;
    const t = [[c, x, 0], [x, c, 0], [0, c, x], [0, x, c], [x, 0, c], [c, 0, x]][sec];
    return {r: (t[0] + m) * 255, g: (t[1] + m) * 255, b: (t[2] + m) * 255};
  }
  // build_discrete_gradient_color(): lighter at the left, darker at the right
  function gradientColor(hex, ratio, dark){
    const o = toHsl(hex);
    const startL = Math.min(255, Math.floor(o.l * (dark ? 1.4 : 1.22)));
    const endL = Math.max(0, Math.floor(o.l * (dark ? 0.7 : 0.68)));
    const r = Math.max(0, Math.min(1, ratio));
    const cur = Math.floor(startL - (startL - endL) * r);
    return hex2(fromHsl(o.h, o.s, cur));
  }
  function mixHex(a, b, w){
    const p = U.hexToRgb(a), q = U.hexToRgb(b);
    return hex2({r: p.r + (q.r - p.r) * w, g: p.g + (q.g - p.g) * w, b: p.b + (q.b - p.b) * w});
  }

  // draw_bar_rect(): the soft vertical fade of a bar, and its softly rounded top corners
  function barFill(ctx, hex, y, bw, bh, alphaF, dark, gradK){
    const sk = U.smoothK((bw - 2) / 4) * U.smoothK((bh - 2) / 8);
    const k = gradK * sk;
    if (sk > 0.01 && alphaF > 0){
      const g = ctx.createLinearGradient(0, y, 0, y + bh);
      if (dark){
        g.addColorStop(0, U.rgba(U.scaleV(hex, (100 + Math.round(14 * k)) / 100), alphaF));
        g.addColorStop(1, U.rgba(U.scaleV(hex, 100 / (100 + Math.round(30 * k))), Math.max(30 / 255, alphaF * (1 - 0.12 * k))));
      } else {
        g.addColorStop(0, U.rgba(hex, alphaF));
        g.addColorStop(1, U.rgba(hex, Math.max(30 / 255, alphaF * (1 - 0.38 * k))));
      }
      return g;
    }
    return U.rgba(hex, alphaF);
  }
  // the bars' top corners: 1 px, as Anki's (rx 1), whatever their width (rounder ones made thin bars look like pills)
  function barRadius(bw, bh){ return Math.min(1, bw / 2, bh); }
  // the hovered bar's whole column, softly lit behind the bars (as Anki's charts), so a thin or low bar is easy to aim at
  function hoverColumn(ctx, x, w, top, h, dark, txt){
    if (!(w > 0 && h > 0)) return;
    ctx.save();
    ctx.fillStyle = U.rgba(txt || (dark ? '#ffffff' : '#000000'), dark ? 0.06 : 0.045);
    ctx.beginPath();
    if (ctx.roundRect) ctx.roundRect(x, top, w, h, Math.min(4, w / 2)); else ctx.rect(x, top, w, h);
    ctx.fill();
    ctx.restore();
  }
  function roundedBar(ctx, x, y, bw, bh, fill, rounded){
    ctx.fillStyle = fill;
    const r = barRadius(bw, bh);
    if (bw < 4 || r < 1 || rounded === false){ ctx.fillRect(x, y, bw, Math.max(0, bh)); return; }
    ctx.beginPath();
    ctx.moveTo(x, y + bh); ctx.lineTo(x, y + r); ctx.quadraticCurveTo(x, y, x + r, y);
    ctx.lineTo(x + bw - r, y); ctx.quadraticCurveTo(x + bw, y, x + bw, y + r);
    ctx.lineTo(x + bw, y + bh); ctx.closePath(); ctx.fill();
  }
  U.parseColor = parseColor; U.cssRgba = css;
  U.barFill = barFill; U.roundedBar = roundedBar; U.gradientColor = gradientColor; U.barRadius = barRadius; U.hoverColumn = hoverColumn;

  // ---- bins -------------------------------------------------
  function binSize(n, scale){
    let base;
    if (n <= 31) base = 1; else if (n <= 90) base = 2; else if (n <= 185) base = 3; else if (n <= 366) base = 7;
    else if (n <= 730) base = 14; else if (n <= 1850) base = 30; else if (n <= 3650) base = 60; else base = 90;
    const ladder = [1, 2, 3, 7, 14, 30, 60, 90];
    scale = scale || 100;
    const step = scale <= 60 ? -2 : (scale < 90 ? -1 : (scale <= 110 ? 0 : (scale <= 170 ? 1 : 2)));
    if (!step) return base;
    let pos = ladder.indexOf(base);
    if (pos < 0) pos = 0;
    return ladder[Math.max(0, Math.min(ladder.length - 1, pos + step))];
  }

  // A zoom of the histograms of days (Review Intervals, Interval Load, Stability), as Future Due's: opts._zoom the days
  // [a, b) shown (DiscreteChart.snapZoom). Within their days [lo, hi]: its days [a, b], null when it shows them all
  function zoomOf(z, lo, hi){
    if (!z || !(z[0] > lo || z[1] < hi + 1)) return null;
    const a = Math.max(lo, z[0]), b = Math.min(hi, z[1] - 1);
    return b > a ? [a, b] : null;
  }
  // the bins of the days [a, b] on the grid of day 0, of k days (those at the ends cut): a zoom's bars, as the zoom camera
  // draws them (zoom_camera.grid)
  function gridBins(a, b, k){
    const out = [];
    for (let r = Math.floor(a / k) * k; r <= b; r += k) out.push([Math.max(a, r), Math.min(b + 1, r + k)]);
    return out;
  }
  function binSums(dist, ranges){
    return ranges.map(function(r){ let s = 0; for (let d = r[0]; d < r[1]; d++) s += Number(dist[d] || 0); return s; });
  }

  function intKeys(obj){
    const o = {};
    Object.keys(obj || {}).forEach(function(k){ o[parseInt(k, 10)] = obj[k]; });
    return o;
  }

  // The running counts of Future Due's days [lo, hi] (its parts too, the hidden ones left out, as the bars count them):
  // pre(d) the count before day d (between two days: in proportion), row(r0, r1) the bar of days [r0, r1)
  function futureDueRuns(dist, days, hid, lo, hi){
    const n = hi - lo + 1, pre = new Float64Array(n + 1), pp = days ? [new Float64Array(n + 1), new Float64Array(n + 1), new Float64Array(n + 1)] : null;
    for (let i = 0; i < n; i++){
      const d = lo + i;
      let tot = Number(dist[d] || 0);
      if (pp){
        const c3 = days[d] || [0, 0, 0];
        for (let k = 0; k < 3; k++) pp[k][i + 1] = pp[k][i] + (hid.indexOf(k) >= 0 ? 0 : (c3[k] || 0));
        if (hid.length) tot = (hid.indexOf(0) >= 0 ? 0 : c3[0] || 0) + (hid.indexOf(1) >= 0 ? 0 : c3[1] || 0) + (hid.indexOf(2) >= 0 ? 0 : c3[2] || 0);
      }
      pre[i + 1] = pre[i] + tot;
    }
    const at = function(a, d){ const x = Math.max(0, Math.min(n, d - lo)), i = Math.min(n - 1, Math.floor(x)); return a[i] + (a[i + 1] - a[i]) * (x - i); };
    return {
      pre: function(d){ return at(pre, d); },
      row: function(r0, r1){
        const r = {total: at(pre, r1) - at(pre, r0), neg: r0 < 0};
        if (pp) r.sums = pp.map(function(a){ return at(a, r1) - at(a, r0); });
        return r;
      },
    };
  }

  // Future Due: a bar per bin of days (negative days = backlog)
  const futureDue = {
    colorKey: 'future_due',
    model: function(payload, opts){
      const data = payload.data || {};
      const showBacklog = payload.backlog != null ? !!payload.backlog : !!opts.show_backlog;
      const dist = intKeys(data.distribution);
      let maxDays = data.max_days != null ? data.max_days : 31;
      let minDay = 0;
      if (showBacklog){
        Object.keys(dist).forEach(function(k){ k = parseInt(k, 10); if (k < 0 && dist[k] > 0 && k < minDay) minDay = k; });
      }
      // a zoom (opts._zoom: the days [a, b) shown, on the grid of its bins, DiscreteChart.snapZoom): the bins of those
      // days alone, of the size for their span on the grid of day 0, as the zoom camera draws them (zoom_camera.js)
      // (the backlog's bins of their own size are the whole view's)
      const fullMin = minDay, fullMax = maxDays, z = opts._zoom;
      let zoomed = false;
      if (z && (z[0] > fullMin || z[1] < fullMax + 1)){
        const a = Math.max(fullMin, z[0]), b = Math.min(fullMax, z[1] - 1);
        if (b > a){ minDay = a; maxDays = b; zoomed = true; }
      }
      const span = maxDays - minDay;
      const adaptive = opts.adaptive_binning !== false;
      const scale = (DD.settings && DD.settings.bin_scale) || 100;
      const bs = adaptive ? binSize(span, scale) : 1;
      const zr = [];
      if (zoomed) for (let r = Math.floor(minDay / bs) * bs; r <= maxDays; r += bs) zr.push([Math.max(minDay, r), Math.min(maxDays + 1, r + bs)]);
      let count;
      if (zoomed) count = zr.length;
      else if (!adaptive || bs <= 1) count = span + 1;
      else if (minDay < 0){
        const back = Math.abs(minDay), bsBack = binSize(back, scale);
        count = Math.max(1, Math.floor(back / Math.max(1, bsBack))) + Math.max(1, Math.floor((maxDays + 1) / Math.max(1, binSize(maxDays, scale))));
      } else count = Math.max(1, Math.floor((span + 1) / bs));
      const range = function(idx){
        const binning = adaptive;
        if (zoomed) return zr[idx];
        if (!binning || minDay >= 0){
          return [minDay + Math.trunc(idx * (span + 1) / count), minDay + Math.trunc((idx + 1) * (span + 1) / count)];
        }
        const backSpan = Math.abs(minDay), bsBack = binSize(backSpan, scale);
        const backBuckets = Math.max(1, Math.floor(backSpan / Math.max(1, bsBack)));
        if (idx < backBuckets){
          return [minDay + Math.trunc(idx * backSpan / backBuckets), Math.min(0, minDay + Math.trunc((idx + 1) * backSpan / backBuckets))];
        }
        const fi = idx - backBuckets, fb = count - backBuckets;
        if (fb <= 0) return [0, maxDays + 1];
        return [Math.max(0, Math.trunc(fi * (maxDays + 1) / fb)), Math.trunc((fi + 1) * (maxDays + 1) / fb)];
      };
      const values = [], flags = [], ranges = [];
      for (let i = 0; i < count; i++){
        const r = range(i);
        let s = 0;
        for (let d = r[0]; d < r[1]; d++) s += Number(dist[d] || 0);
        values.push(s); flags.push(r[0] < 0); ranges.push(r);
      }
      // breakdown
      let parts = null, days = null, hidK = [];
      const bd = data.breakdown;
      if (bd && bd.days){
        days = intKeys(bd.days);
        const rawSums = [];
        const shares = ranges.map(function(r){
          const sums = [0, 0, 0];
          for (let d = r[0]; d < r[1]; d++){ const c3 = days[d]; if (c3) for (let k = 0; k < 3; k++) sums[k] += c3[k]; }
          rawSums.push(sums.slice());
          const tot = sums[0] + sums[1] + sums[2];
          return tot > 0 ? sums.map(function(v){ return v / tot; }) : [0, 0, 0];
        });
        const kind = bd.kind;
        const pcolors = kind === 'result' ? ['good', 'again', 'future_due'] : ['mature', 'young', 'learn'];
        // "Series": hidden parts are removed from the bars (heights follow the visible parts)
        const hid = (opts.hidden_series || []).map(function(n){ return pcolors.indexOf(n); }).filter(function(k){ return k >= 0; });
        if (hid.length && hid.length < 3){
          hidK = hid;
          rawSums.forEach(function(sums, i){
            hid.forEach(function(k){ sums[k] = 0; });
            const tot = sums[0] + sums[1] + sums[2];
            shares[i] = tot > 0 ? sums.map(function(v){ return v / tot; }) : [0, 0, 0];
            values[i] = tot;
          });
        }
        parts = {kind: kind, shares: shares, sums: rawSums, colors: pcolors};
      }
      // x labels: six, evenly spread over the bins
      const labels = [];
      let last = null;
      for (let i = 0; i < 6; i++){
        const idx = Math.trunc(i / 5 * (count - 1));
        const lab = String(ranges[idx][0]);
        if (lab === last) continue;
        last = lab; labels.push([idx, lab]);
      }
      let zeroIdx = null;
      if (minDay < 0){ for (let i = 0; i < count; i++){ if (ranges[i][0] >= 0){ zeroIdx = i; break; } } }
      return {count: count, values: values, flags: flags, ranges: ranges, parts: parts, labels: labels, zeroIdx: zeroIdx,
        emptyDeck: !Object.keys(dist).length,
        // the zoom's frame: the whole view's days [fullMin, fullMin + fullN), the days shown when zoomed, the bins' size
        fullMin: fullMin, fullN: fullMax - fullMin + 1, win: zoomed ? [minDay, maxDays + 1] : null,
        binK: (zoomed || bs <= 1 || minDay >= 0) ? bs : binSize(maxDays, scale),  // (with the backlog: the days ahead's)
        // the backlog's bins' size on the whole view (its own, not the days ahead's): null when they are the same
        backK: (zoomed || bs <= 1 || minDay >= 0) ? null : binSize(Math.abs(minDay), scale),
        // the zoom camera's bars of any days: a running count of the whole view's days (the parts shown)
        cam: futureDueRuns(dist, days, hidK, fullMin, fullMax)};
    },
  };

  // Review Intervals: a bar per bin of intervals (days), capped by the filter (1m, 50%, 95%, all ...)
  const reviewIntervals = {
    colorKey: 'bar',
    widthRatio: 0.95,
    model: function(payload, opts){
      const data = payload.data || {};
      const maxDays = Math.max(1, payload.max_days || 31);
      const dist = intKeys(data.distribution);
      const adaptive = opts.adaptive_binning !== false;
      const scale = (DD.settings && DD.settings.bin_scale) || 100;
      const bs = adaptive ? binSize(maxDays, scale) : 1;
      // zoomed (not with a bar at 0): the bins of the days shown, of the size for their span
      const z = payload.zero_bar == null ? zoomOf(opts._zoom, 1, maxDays) : null, zk = z ? (adaptive ? binSize(z[1] - z[0], scale) : 1) : bs;
      const count = z ? gridBins(z[0], z[1], zk).length : (bs <= 1 ? maxDays : Math.max(1, Math.floor(maxDays / bs)));
      const values = [], ranges = z ? gridBins(z[0], z[1], zk) : [], flags = [];
      for (let i = 0; i < count; i++){
        if (!z) ranges.push([1 + Math.trunc(i * maxDays / count), 1 + Math.trunc((i + 1) * maxDays / count)]);
        flags.push(false);
      }
      binSums(dist, ranges).forEach(function(s){ values.push(s); });
      // the zoom's frame (Future Due's): the whole view's days [1, maxDays], those shown, the bins' size, the camera's
      // running count of the days
      const zf = {fullMin: 1, fullN: maxDays, win: z ? [z[0], z[1] + 1] : null, binK: zk, backK: null, cam: futureDueRuns(dist, null, [], 1, maxDays)};
      const lo = z ? z[0] : 1, hi = z ? z[1] : maxDays;
      const labels = [];
      let last = null;
      for (let i = 0; i < 6; i++){
        const day = lo + Math.trunc((i / 5) * (hi - lo));
        const lab = String(day);
        if (lab === last) continue;
        last = lab; labels.push({text: lab, frac: i / 5, align: i === 0 ? 'left' : (i === 5 ? 'right' : 'center')});
      }
      // a bar at 0 first (Lapses per Card's Include Zero): the cards never forgotten
      if (payload.zero_bar != null){
        values.unshift(Number(payload.zero_bar) || 0); ranges.unshift([0, 1]); flags.unshift(false);
        const n = values.length, zl = [];
        labels.forEach(function(l){
          const t = String(ranges[Math.round(l.frac * (n - 1))][0]);
          if (!zl.length || zl[zl.length - 1].text !== t) zl.push(Object.assign({}, l, {text: t}));
        });
        return {count: n, values: values, flags: flags, ranges: ranges, parts: null, labels: zl, zeroIdx: null,
          emptyDeck: !Object.keys(dist).length && !values[0], fracLabels: true};
      }
      return Object.assign({count: count, values: values, flags: flags, ranges: ranges, parts: null, labels: labels, zeroIdx: null,
        emptyDeck: !Object.keys(dist).length, fracLabels: true}, zf);
    },
  };
  // Stability: a bar per day (or bin of days) of stability, capped by the filter, cumulative curve over it
  const stability = {
    colorKey: 'bar',
    widthRatio: 0.95,
    model: function(payload, opts){
      const dist = intKeys(payload.data);
      const maxDays = Math.max(1, payload.max_days || 31);
      const adaptive = opts.adaptive_binning !== false;
      const scale = (DD.settings && DD.settings.bin_scale) || 100;
      const bs = adaptive ? binSize(maxDays, scale) : 1;
      const nFull = bs <= 1 ? maxDays : Math.floor(maxDays / bs) + 1;
      let values = new Array(nFull).fill(0);
      let total = 0;
      Object.keys(dist).forEach(function(k){
        const day = parseInt(k, 10);
        if (day > maxDays) return;
        const idx = bs <= 1 ? day - 1 : Math.floor(day / bs);
        if (idx >= 0 && idx < nFull){ values[idx] += Number(dist[k] || 0); }
      });
      values.forEach(function(v){ total += v; });  // (the header's total: all the cards, zoomed or not)
      // its bins' days: one a day from day 1, else bins of bs days on the grid of day 0 (the first from day 1, the last
      // up to maxDays); zoomed, the bins of the days shown, of the size for their span (Review Intervals' zoom)
      const z = zoomOf(opts._zoom, 1, maxDays), zk = z ? (adaptive ? binSize(z[1] - z[0], scale) : 1) : bs;
      let ranges;
      if (z){ ranges = gridBins(z[0], z[1], zk); values = binSums(dist, ranges); }
      else ranges = values.map(function(v, i){ return bs <= 1 ? [i + 1, i + 2] : [Math.max(1, i * bs), Math.min(maxDays + 1, (i + 1) * bs)]; });
      const n = ranges.length;
      const interval = Math.max(1, Math.floor(n / 5));
      const med = payload.median || 0;
      return {count: n, values: values, flags: values.map(function(){ return false; }), parts: null, labels: [], zeroIdx: null,
        emptyDeck: !Object.keys(dist).length, binStep: bs, ranges: ranges,
        fullMin: 1, fullN: maxDays, win: z ? [z[0], z[1] + 1] : null, binK: zk, backK: null, cam: futureDueRuns(dist, null, [], 1, maxDays),
        labelsFn: function(g){
          const out = [];
          for (let i = 0; i < n; i += interval){
            out.push({x: g.ml + i * g.step + g.step / 2, text: (z ? ranges[i][0] : i * bs + (bs <= 1 ? 1 : 0)) + 'd', align: 'center'});
          }
          return out;
        },
        labelPx: 9,
        stat: DD.tn('Total: {count} card', 'Total: {count} cards', Math.round(total), {count: U.formatNum(Math.round(total))}) + '  \u00b7  ' + DD.tn('Median stability: {n} day', 'Median stability: {n} days', med)};
    },
  };

  // Difficulty / Retrievability: 101 bars (0-100 %), coloured along the gradient, no cumulative curve
  function lerpColor(c1, c2, t){
    const a = U.hexToRgb(c1), b = U.hexToRgb(c2);
    return hex2({r: Math.trunc(a.r + t * (b.r - a.r)), g: Math.trunc(a.g + t * (b.g - a.g)), b: Math.trunc(a.b + t * (b.b - a.b))});
  }
  function percent(kind){
    return {
      widthRatio: 0.95,
      noCum: true,
      model: function(payload, opts, C){
        const src = (payload && payload.data) || {};
        const dense = new Array(101).fill(0);
        Object.keys(src).forEach(function(k){
          const i = Math.round(parseFloat(k));
          if (i >= 0 && i <= 100) dense[i] = Math.trunc(Number(src[k] || 0));
        });
        let total = 0; dense.forEach(function(v){ total += v; });
        const low = (C && C.gradient_low) || '#ff3b30', high = (C && C.gradient_high) || '#4cd964';
        const rev = kind === 'difficulty';
        let stat = '';
        if (total > 0){
          if (kind === 'difficulty'){
            let run = 0, med = 0;
            for (let i = 0; i <= 100; i++){ run += dense[i]; if (run >= total / 2){ med = i; break; } }
            stat = DD.t('Median difficulty: {value}%', {value: med});
          } else {
            let sum = 0; for (let i = 0; i <= 100; i++) sum += i * dense[i];
            const avg = sum / total;
            const fa = Math.abs(avg - Math.round(avg)) < 1e-6 ? U.formatNum(Math.round(avg)) : U.trimNum(avg, 1);
            const know = Math.trunc(avg / 100 * total);
            stat = DD.t('Average retrievability: {value}%', {value: fa}) + '  \u00b7  ' + DD.tn('Estimated total knowledge: {n} card', 'Estimated total knowledge: {n} cards', know);
          }
        }
        // Breakdown by Type: each bar's mature, young and learning cards (stacked as Future Due's)
        let parts = null;
        const bk = payload && payload.breakdown && payload.by_kind;
        if (bk){
          const per = ['mature', 'young', 'learn'].map(function(k){
            const d = bk[k] || {}, out = new Array(101).fill(0);
            Object.keys(d).forEach(function(b){ const i = Math.round(parseFloat(b)); if (i >= 0 && i <= 100) out[i] = Math.trunc(Number(d[b] || 0)); });
            return out;
          });
          const sums = dense.map(function(_, i){ return [per[0][i], per[1][i], per[2][i]]; });
          parts = {kind: 'type', colors: ['mature', 'young', 'learn'], sums: sums,
            shares: sums.map(function(s){ const t = s[0] + s[1] + s[2]; return t > 0 ? s.map(function(v){ return v / t; }) : [0, 0, 0]; })};
        }
        return {count: 101, values: dense, flags: dense.map(function(){ return false; }), parts: parts, labels: [], zeroIdx: null,
          emptyDeck: total === 0, noCum: true, stat: stat, labelPx: 9,
          colorFn: function(i){ return rev ? lerpColor(high, low, i / 100) : lerpColor(low, high, i / 100); },
          labelsFn: function(g){
            const out = [];
            for (let i = 0; i <= 100; i += 20) out.push({x: g.ml + i * g.plotW / 101, text: i + '%', align: 'center'});
            return out;
          }};
      },
    };
  }

  const ADAPTERS = {future_due: futureDue, review_intervals: reviewIntervals, stability: stability,
    difficulty: percent('difficulty'), retrievability: percent('retrievability'),
    // the charts of the extra groups read the same payload (max_days, distribution) as Review Intervals
    interval_load: reviewIntervals, lapse_distribution: reviewIntervals, review_distribution: reviewIntervals,
    learning_steps: reviewIntervals, time_distribution: reviewIntervals, interval_history: reviewIntervals,
    // Card Stability / Card Difficulty on a past day (the same payload, and its day)
    stability_history: stability, difficulty_history: percent('difficulty')};
  const BASE = {stability_history: 'stability', difficulty_history: 'difficulty'};  // their tooltips
  // texts made from these names (i18n.web_catalog finds the quoted texts of the scripts): '{n} lapse' '{n} review'
  // '{n} learning review'
  const CARD_HISTORY = {lapse_distribution: ['lapse', 'lapses'], review_distribution: ['review', 'reviews'],
    learning_steps: ['learning review', 'learning reviews']};
  // a time in seconds (Time per Card): 45 s, 3 min 20 s, 1.5 h
  function dur(sec){
    const s = Math.max(0, Number(sec) || 0);
    if (s < 60) return DD.t('{value}s', {value: U.trimNum(s, s < 10 && s % 1 ? 1 : 0)});
    if (s < 3600) return DD.t('{minutes}m {seconds}s', {minutes: Math.floor(Math.round(s) / 60), seconds: Math.round(s) % 60});
    return DD.t('{value}h', {value: U.trimNum(s / 3600, s < 36000 ? 1 : 0)});
  }
  function perDay(v){
    const x = Number(v) || 0;
    return DD.t('{value}/day', {value: DD.tn('{count} review', '{count} reviews', x, {count: U.trimNum(x, x < 10 ? 1 : 0)})});
  }

  // ---- chart ----------------------------------------------------------------------------
  class Chart {
    constructor(root, type, payload, colors, options){
      this.canvas = root.querySelector('canvas');
      this.ctx = this.canvas.getContext('2d');
      this.type = type;
      this.adapter = ADAPTERS[type];
      this.colors = colors;
      this.options = Object.assign({adaptive_binning: true, show_cumulative: true, chart_opacity_pct: 100}, options || {});
      this.payload = payload;
      this.w = 1; this.h = 1;
      this.progress = 0;
      this.hover = -1;
      this._resize();
      this.zoomDays = null;  // Future Due zoomed: the days [a, b) shown (setZoom)
      this.m = this._model();
    }
    _model(){
      const o = this.zoomDays ? Object.assign({}, this.options, {_zoom: this.zoomDays}) : this.options;
      const m = this.adapter.model(this.payload, o, this.colors);
      // the days zoomed on, within the new data (a shorter range, the backlog off): the whole view when none are left
      if (this.zoomDays) this.zoomDays = m.win ? m.win.slice() : null;
      return m;
    }
    _resize(){
      const f = DD.fitCanvas(this.canvas, this.ctx), w = f.w, h = f.h, dpr = f.dpr;
      this.w = w; this.h = h;
    }
    // a change of data / option morphs the bars from the old model to the new one (the charts' value transition)
    _startMorph(old, align){
      if (DD._noAnim){ this.morph = null; return; }
      if (old) this.morph = {from: old, start: null, align: !!align, k: DD.calm ? DD.calm() : 1};
      if (old && DD.dev){
        const mx = function(x){ return Math.round(Math.max.apply(null, (x.values || []).concat([0]))); }, m = this.m;
        DD.trace('ANIMTRACE discrete ' + this.type + ': bars ' + old.count + ' -> ' + m.count + ', highest ' + mx(old) + ' -> ' + mx(m) +
          (old.emptyDeck ? ' (from empty)' : '') + (m.emptyDeck ? ' (to empty)' : '') + (align ? ', from the right' : '') + ', breakdown ' + (old.parts ? old.parts.kind : 'none') + ' -> ' + (m.parts ? m.parts.kind : 'none') + (old.morphing ? ' (from a running one)' : '') + ', ' + Math.round((align ? 310 : 300) * (this.morph.k || 1)) + ' ms');
      }
    }
    // hint "timespan": the bars slide in from / out to the right, else from the left
    setPayload(payload, hint){ const old = this.morph ? this.blended() : this.m; this.payload = payload; this.cam = null; this.m = this._model(); this._startMorph(old, hint === 'timespan'); }
    setOptions(o){ const old = this.morph ? this.blended() : this.m; Object.assign(this.options, o); this.cam = null; this.m = this._model(); this._startMorph(old); }
    // the grid lines and the numbers of the left axis (ticks: axisTicks), from x0 to x1
    _leftAxis(ctx, ticks, x0, x1, mt, plotH){
      const C = this.colors, dark = !!C.is_dark;
      const grid = parseColor((this.options && this.options.show_grid === false ? 'rgba(0,0,0,0)' : C.grid));
      const axisCol = css(parseColor(C.text_secondary), ((dark ? 175 : 215) / 255).toFixed(4));
      const fmtV = function(v){ return v === 0 ? '0' : (v >= 10 ? U.formatNum(Math.trunc(v)) : U.trimNum(v, 1)); };
      ctx.font = FONT; ctx.textBaseline = 'middle';
      ticks.forEach(function(k){
        const y = mt + plotH * (1 - k.f), yl = Math.trunc(y) + 0.5;
        ctx.globalAlpha = k.a;
        ctx.strokeStyle = css(grid, Math.min(1, grid.a * (k.f <= 0.0005 ? 2.6 : 1.5))); ctx.lineWidth = 1;
        ctx.beginPath(); ctx.moveTo(x0, yl); ctx.lineTo(x1, yl); ctx.stroke();
        ctx.fillStyle = axisCol; ctx.textAlign = 'right'; ctx.fillText(fmtV(k.v), x0 - 8, Math.trunc(y));
      });
      ctx.globalAlpha = 1;
    }
    // the running total's numbers on the right
    _rightAxis(ctx, ticks, w, mt, plotH){
      const dark = !!this.colors.is_dark;
      ctx.font = FONT; ctx.textBaseline = 'middle'; ctx.textAlign = 'right';
      ctx.fillStyle = css(parseColor(this.colors.text_secondary), ((dark ? 175 : 215) * 0.8 / 255).toFixed(4));
      ticks.forEach(function(k){ ctx.globalAlpha = k.a; ctx.fillText(U.formatNum(Math.trunc(k.v)), w - 4, Math.trunc(mt + plotH * (1 - k.f))); });
      ctx.globalAlpha = 1;
    }
    // the running total over the bars, as Anki's charts draw it (.cumulative-overlay): a flat pale area in the text's
    // colour (Anki: black 3 % light, white 8 % dark), its edge a faint dark line (black 8 % / 18 %); the Total /
    // Average Lines setting scales both, its default giving Anki's values
    _cumArea(ctx, pts, ml, mt, plotW, plotH){
      const C = this.colors, dark = !!C.is_dark, bottom = mt + plotH;
      const lineK = (this.options.line_opacity_pct != null ? this.options.line_opacity_pct : LINE_PCT) / 100;
      ctx.save();
      ctx.beginPath(); ctx.rect(ml, mt - 2, plotW, plotH + 2); ctx.clip();
      ctx.beginPath(); U.smoothPath(ctx, pts);
      ctx.lineTo(pts[pts.length - 1][0], bottom); ctx.lineTo(pts[0][0], bottom); ctx.closePath();
      const A = DD.areaStyle(C, dark, lineK * 100 / LINE_PCT);
      ctx.fillStyle = U.rgba(A.fill, A.fillA); ctx.fill();
      ctx.lineJoin = 'round'; ctx.lineCap = 'round';
      ctx.beginPath(); U.smoothPath(ctx, pts);
      ctx.strokeStyle = U.rgba(A.line, A.lineA); ctx.lineWidth = A.lw; ctx.stroke();
      // the Total Line setting (none by default): a clear line over that edge, as before
      const strong = (this.options.total_line_pct || 0) / 100;
      if (strong > 0){
        const bgc = C.bg || (dark ? '#000000' : '#ffffff');
        ctx.strokeStyle = U.rgba(dark ? U.scaleV(bgc, 1 / 1.6) : bgc, Math.min(1, 150 / 255 * lineK * strong)); ctx.lineWidth = 3.4; ctx.stroke();
        ctx.strokeStyle = U.rgba(C.text_primary || C.total_line || (dark ? '#ffffff' : '#000000'), Math.min(1, 215 / 255 * lineK * strong)); ctx.lineWidth = 1.3; ctx.stroke();
      }
      ctx.restore();
    }
    // the dashed line at today, between the backlog and the days ahead (x null: none)
    _zeroLine(ctx, x, alpha, y0, y1){
      if (x == null || alpha <= 0.01) return;
      ctx.save(); ctx.setLineDash([3.2, 3.2]); ctx.globalAlpha = alpha;
      ctx.strokeStyle = css(parseColor(this.colors.text_secondary), 1); ctx.lineWidth = 0.8;
      ctx.beginPath(); ctx.moveTo(x, y0); ctx.lineTo(x, y1); ctx.stroke(); ctx.restore();
    }
    // the top of a model's axis and the sum of its bars (draw's axisMax / totalCards)
    _axTop(m){ if (m.emptyDeck || m.count <= 0) return 4; const r = Math.max.apply(null, m.values.concat([0])); return r > 0 ? r : 1; }
    _sum(m){ const r = m.values.reduce(function(a, b){ return a + b; }, 0); return r === 0 ? 1 : r; }
    // the bars of a model, as the zoom camera reads them: the grid of its bins when zoomed, else the bins it drew.
    // With the backlog the whole view's bins have two sizes (the backlog's, the days ahead's): each bar keeps its
    // own, and the camera's size is that of the side the other window w lies in (most of its days): zooming into
    // the backlog its bars split from the backlog's, not from the days ahead's (smaller than them: they left gaps)
    _binning(m, w){
      if (m.win) return DD.zoomCam.grid(m.binK, m.fullMin, m.fullMin + m.fullN, m.win);
      if (m.backK == null) return DD.zoomCam.list(m.ranges, m.binK);
      const back = w ? Math.max(0, Math.min(0, w[1]) - w[0]) : 0, k = w && back * 2 > w[1] - w[0] ? m.backK : m.binK;
      return DD.zoomCam.list(m.ranges, k, function(i){ return m.flags[i] ? m.backK : m.binK; });
    }
    // a zoom window on the grid of its bins (as Activity's): its
    // bars are those the zoom camera draws, none cut at its ends. null: the whole view
    snapZoom(a, b){
      const m = this.m, lo = m.fullMin, hi = m.fullMin + m.fullN;
      if (a == null) return null;
      let s0 = Math.max(lo, Math.round(a)), e0 = Math.min(hi, Math.round(b));
      if (this.options.adaptive_binning !== false){
        const scale = (DD.settings && DD.settings.bin_scale) || 100;
        for (let it = 0; it < 3; it++){  // snapped, the window may need the next bin size: snapped again on that one
          const k = binSize(Math.max(1, e0 - s0) - 1, scale);
          if (k <= 1) break;
          // its start on the grid, its width whole bins (slid by Shift+wheel or the zoom bar, it keeps its width)
          const wd = Math.ceil((e0 - s0) / k) * k;
          s0 = Math.max(lo, Math.floor(s0 / k) * k); e0 = Math.min(hi, s0 + wd);
          if (binSize(Math.max(1, e0 - s0) - 1, scale) === k) break;
        }
      }
      if (e0 - s0 < 2) return this.zoomDays;
      return (s0 <= lo && e0 >= hi) ? null : [s0, e0];
    }
    // Future Due's zoom on the days [a, b) (null: the whole view), as Activity's: the shared zoom camera
    // (zoom_camera.js) draws the bars live on the moving window of days
    setZoom(a, b){
      const m0 = this.m, full = [m0.fullMin, m0.fullMin + m0.fullN], c0 = this.cam;
      const A = c0 && c0.cur ? c0.cur.slice() : (this.zoomDays ? this.zoomDays.slice() : full);
      const still = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      const can = !!DD.zoomCam && !still && !DD._noAnim && !DD.noZoomAnim && !!this.geo && this.canvas.width > 1 && this.progress >= 1 && !m0.emptyDeck;
      // a zoom taking over from one still running starts from what it draws (its window, bars, tops)
      const keepBin = c0 && c0.lastBin ? c0.lastBin : null, g0 = c0 && c0.gCur ? c0.gCur : (this.geo ? {ml: this.geo.ml, mr: this.geo.mr} : null);
      const ma = c0 && c0.curMx ? c0.curMx : this._axTop(m0), ta = c0 && c0.curTop != null ? c0.curTop : this._sum(m0);
      const baseA = c0 && c0.curBase != null ? c0.curBase : m0.cam.pre(A[0]);
      this.zoomDays = this.snapZoom(a, b);
      this.morph = null;
      this.m = this._model();
      const m1 = this.m, B = this.zoomDays ? this.zoomDays.slice() : full, binA = keepBin || this._binning(m0, B);
      this.cam = null;
      if (can && (Math.abs(A[0] - B[0]) > 1e-6 || Math.abs(A[1] - B[1]) > 1e-6)){
        this.cam = DD.zoomCam.create({a: A, b: B, binA: binA, binB: this._binning(m1, A), ma: ma, mb: this._axTop(m1),
          ta: ta, tb: this._sum(m1), baseA: baseA, baseB: m1.cam.pre(B[0]), pre: m1.cam.pre, row: m1.cam.row, plotW: this.geo.plotW});
        this.cam.g0 = g0; this.cam.m0 = c0 && c0.m1 && c0.lastBin === c0.binA ? c0.m0 : m0; this.cam.m1 = m1;
      }
      if (DD.dev) DD.trace('ANIMTRACE discrete ' + this.type + ' zoom: days ' + A.map(Math.round) + ' -> ' + B + ', bars ' + m0.count + ' -> ' + m1.count + ' (bins ' + binA.k + ' -> ' + m1.binK + ')' + (this.cam ? ', camera ' + Math.round(this.cam.dur) + ' ms' : ' (at once)') + (c0 ? ', took over a running zoom' : ''));
    }
    // a frame of the zoom camera: the bars live on the moving window, the axes counting from the start's tops to the
    // end's, the day numbers moving with their days. false: over (the still chart drawn)
    camFrame(now){
      const c = this.cam, cv = this.canvas;
      if (!c.g1){
        // the end chart's margins (its numbers' widths): drawn once to know them
        this.cam = null; this.draw(); this.cam = c;
        c.g1 = {ml: this.geo.ml, mr: this.geo.mr};
      }
      if (!c.step(now)){ this.cam = null; this.draw(); return false; }
      const s = c.s, e = s.e, ctx = this.ctx, W = this.w, H = this.h, C = this.colors, dark = !!C.is_dark;
      const g0 = c.g0 || c.g1, ml = g0.ml + (c.g1.ml - g0.ml) * e, mr = g0.mr + (c.g1.mr - g0.mr) * e;
      const mt = 10, mb = 30, plotW = Math.max(1, W - ml - mr), plotH = Math.max(1, H - mt - mb), bottom = mt + plotH;
      c.gCur = {ml: ml, mr: mr};
      const sc = DD.canvasScale(cv, W, H);
      ctx.save(); ctx.setTransform(sc[0], 0, 0, sc[1], 0, 0); ctx.clearRect(0, 0, W, H);
      this._leftAxis(ctx, axisTicks(c.ma, c.mb, s.mx, e, plotH, this.type + ' zoom'), ml, ml + plotW, mt, plotH);
      // the bars, each as the chart draws it (draw): its colour along the plot or the backlog's, its parts
      const baseHex = C[this.adapter.colorKey] || C.bar, P = c.m1.parts;
      const gradK = (this.options.bar_gradient_pct != null ? this.options.bar_gradient_pct : GRAD_PCT) / 100;
      const opac = Math.max(0, Math.min(100, this.options.chart_opacity_pct != null ? this.options.chart_opacity_pct : 100)) * 2.55 / 255;
      const paint = function(g, row, x, bw, top){
        const v = row.total || 0; if (v <= 0) return;
        const bh = Math.min(1, v / Math.max(1, top)) * plotH, y = bottom - bh;
        const sums = row.sums, whole = sums ? sums[0] + sums[1] + sums[2] : 0;
        if (P && whole > 0){
          const tops = []; let acc = 0;
          for (let k = 0; k < 3; k++){ acc += sums[k] / whole; tops.push(bottom - bh * acc); }
          let top3 = 2; for (let k = 2; k >= 0; k--){ if (sums[k] / whole > 1e-6){ top3 = k; break; } }
          for (let k = 2; k >= 0; k--){
            if (sums[k] / whole <= 1e-6) continue;
            const hex = C[P.colors[k]] || baseHex;
            let segBottom = bottom;
            for (let j = k - 1; j >= 0; j--){ if (sums[j] / whole > 1e-6){ segBottom = tops[j]; break; } }
            const segTop = k === top3 ? tops[k] : tops[k] - 0.75;
            roundedBar(g, x, segTop, bw, Math.max(0, segBottom - segTop), barFill(g, hex, y, bw, bh, opac, dark, gradK), k === top3);
          }
          return;
        }
        const hex = row.neg ? (C.backlog || baseHex) : gradientColor(baseHex, (x + bw / 2 - ml) / Math.max(1, plotW), dark);
        roundedBar(g, x, y, bw, bh, barFill(g, hex, y, bw, bh, opac, dark, gradK), true);
      };
      ctx.save(); ctx.beginPath(); ctx.rect(ml, 0, plotW, bottom + 1); ctx.clip();
      c.bars(ctx, {ml: ml, plotW: plotW, bottom: bottom, plotH: plotH, ratio: this.adapter.widthRatio || 0.9, cv: cv, dpr: sc[0], dpy: sc[1]}, paint);
      ctx.restore();
      // the running total: one curve seen through the camera, on its top gliding from the start's to the end's
      const showCum = this.options.show_cumulative !== false;
      if (showCum){ const pts = c.cumPoints({ml: ml, plotW: plotW, bottom: bottom, plotH: plotH}); if (pts && pts.length) this._cumArea(ctx, pts, ml, mt, plotW, plotH); }
      // the day numbers under the bars and the line at today, moving with their days
      // each label at the day under it on its chart (draw: at a bar's middle, at a share of the plot, or by labelsFn), and
      // its alignment there (Review Intervals' first and last labels at the plot's sides)
      const alA = {}, alB = {};
      const at = function(mm, align){
        const o = {}, n = mm.count, R = mm.ranges; if (!R || !n) return o;
        const dayAt = function(x){ x = Math.max(0, Math.min(n, x)); const i = Math.min(n - 1, Math.floor(x)), r = R[i]; return r[0] + (r[1] - r[0]) * (x - i); };
        if (mm.labelsFn) mm.labelsFn({ml: 0, step: 1, plotW: n}).forEach(function(l){ o[l.text] = dayAt(l.x); });
        (mm.labels || []).forEach(function(l){
          if (mm.fracLabels){ o[l.text] = dayAt(l.frac * n); if (l.align === 'left' || l.align === 'right') align[l.text] = l.align; }
          else o[l[1]] = dayAt(l[0] + 0.5);
        });
        return o;
      };
      const mA = at(c.m0, alA), mB = at(c.m1, alB);
      ctx.save(); ctx.beginPath(); ctx.rect(ml - 30, bottom, plotW + 60, H - bottom); ctx.clip();
      ctx.font = c.m1.labelPx ? (c.m1.labelPx + 'px "Segoe UI",-apple-system,BlinkMacSystemFont,sans-serif') : FONT_X;
      ctx.fillStyle = css(parseColor(C.text_secondary), 1); ctx.textBaseline = 'middle';
      c.marks(mA, mB).forEach(function(k){
        if (k.a <= 0.01 || k.x < ml - 2 || k.x > ml + plotW + 2) return;
        // drawn centred, moved by half its width for a side's alignment (gliding between the two charts' for a label in both)
        const hw = ctx.measureText(k.text).width / 2, off = function(al){ return al === 'left' ? hw : (al === 'right' ? -hw : 0); };
        const inA = k.text in mA, inB = k.text in mB, dx = inA && inB ? off(alA[k.text]) + (off(alB[k.text]) - off(alA[k.text])) * e : off(inB ? alB[k.text] : alA[k.text]);
        ctx.textAlign = 'center'; ctx.globalAlpha = k.a; ctx.fillText(k.text, k.x + dx, H - mb + 5 + 7.5);
      });
      ctx.restore();
      const zx = s.X(0), za = (c.m0.zeroIdx != null ? 1 - e : 0) + (c.m1.zeroIdx != null ? e : 0);
      if (zx >= ml && zx <= ml + plotW) this._zeroLine(ctx, Math.trunc(zx), za, mt, H - mb);
      if (showCum) this._rightAxis(ctx, axisTicks(c.ta, c.tb, s.top, e, plotH), W, mt, plotH);
      ctx.restore();
      return true;
    }
    blended(){
      const mo = this.morph, m = this.m;
      if (!mo) return m;
      const now = performance.now();
      if (mo.start === null) mo.start = now;
      const t = Math.min(1, (now - mo.start) / ((mo.align ? 310 : 300) * (mo.k || 1)));  // 300 ms, every chart.s change (240: its axis flew by)
      const a = mo.from;
      if (t >= 1 || (m.emptyDeck && a.emptyDeck)){ this.morph = null; return m; }
      const ec = t < 0.5 ? 4*t*t*t : 1 - Math.pow(-2*t + 2, 3) / 2, e = ec * ec * (3 - 2 * ec);
      const lerp = function(x, y){ return (x || 0) + ((y || 0) - (x || 0)) * e; };
      const oldN = a.count, newN = m.count, n = Math.max(oldN, newN), align = !!mo.align;
      const io = function(i){ const k = align ? i - (n - oldN) : i; return (k >= 0 && k < oldN) ? k : -1; };
      const inn = function(i){ const k = align ? i - (n - newN) : i; return (k >= 0 && k < newN) ? k : -1; };
      const out = Object.assign({}, m);
      out.count = n; out.labelCount = newN;
      // the axis glides from the old maximum to the new one (common/metric interpolate_axis_max; an empty deck's
      // axis on its side): a deck emptied sinks its bars, an empty one grows them
      const axOf = function(x){ if (x.axisMax != null) return x.axisMax; if (x.emptyDeck || x.count <= 0) return 4; const r = Math.max.apply(null, (x.values || []).concat([0])); return r > 0 ? r : 1; };
      const ax0 = axOf(a), ax1 = axOf(m);
      // the axis goes straight from the old maximum to the new one
      // and each bar from its old share of the old axis to its new share of the new one. (An axis eased in log space
      // with values eased straight draws bars far over the top halfway, from a small deck to a big one.)
      out.axisMax = Math.max(1, DD.scaleLerp(ax0, ax1, e));
      // the start and end tops of both axes and the progress: the sliding axis numbers go with the bars (DD.slideTicks)
      const sumOf = function(x){ const r = (x.values || []).reduce(function(p, q){ return p + q; }, 0); return r === 0 ? 1 : r; };
      out.ax = [Math.max(1, ax0), Math.max(1, ax1), e, sumOf(a), sumOf(m)];
      out.emptyDeck = false;
      out.values = []; for (let i = 0; i < n; i++){
        const o = io(i), w = inn(i);
        const r0 = Math.max(0, (o >= 0 ? a.values[o] || 0 : 0) / ax0), r1 = Math.max(0, (w >= 0 ? m.values[w] || 0 : 0) / ax1);
        out.values.push(Math.max(0, Math.min(1, r0 + (r1 - r0) * e)) * out.axisMax);
      }
      if (oldN !== newN) out.slotsFn = function(ml, plotW, ratio){ return U.interpolateBarSlots(oldN, newN, e, ml, plotW, align, ratio); };
      // the shares glide between two splits of the same kind; plain <-> split (or another kind)
      // keeps the shares of the split side and fades its colours in / out over the plain bar (w_split)
      if (m.parts || a.parts){
        const kindChanged = !!(a.parts && m.parts && a.parts.kind !== m.parts.kind);
        // one breakdown for another (by type <-> by result): the segments glide from the old shares to the new ones and
        // each one's colour turns into the new one's (the plain bar showed under the new colours fading in: a flash)
        const P = m.parts || a.parts, AP = a.parts, MP = m.parts;
        out.parts = Object.assign({}, P); out.parts.sums = []; out.parts.shares = [];
        out.parts.wsplit = !MP ? 1 - e : (!AP ? e : 1);
        if (kindChanged){ out.parts.mixFrom = a.parts.colors; out.parts.mixW = e; }
        for (let i = 0; i < n; i++){
          const o = io(i), w = inn(i);
          const ns = (MP && w >= 0) ? MP.shares[w] : null, os = (AP && o >= 0) ? AP.shares[o] : null;
          const nsum = (MP && w >= 0) ? MP.sums[w] : null, osum = (AP && o >= 0) ? AP.sums[o] : null;
          const ts = ns || os || [0, 0, 0], fs = os || ts;
          out.parts.shares.push([0, 1, 2].map(function(k){ return lerp(fs[k], ts[k]); }));
          // a bar of a chart with no breakdown before splits its own height in the new shares
          const tsum = nsum || osum || [0, 0, 0];
          out.parts.sums.push([0, 1, 2].map(function(k){ return lerp(osum ? osum[k] : (o >= 0 ? a.values[o] * (ts[k] / Math.max(1e-9, ts[0] + ts[1] + ts[2])) : 0), nsum ? nsum[k] : 0); }));
        }
      }
      // During a transition the curve is the old normalized running total gliding
      // to the new one, both resampled over the new number of points (never the running total of the padded bars).
      {
        const normRun = function(vals){ let r = 0; const run = vals.map(function(v){ r += (v || 0); return r; }); const tot = r > 0 ? r : 1; return run.map(function(v){ return v / tot; }); };
        const resample = function(src, cnt){
          if (cnt <= 0) return []; if (!src.length) return new Array(cnt).fill(0); if (src.length === 1) return new Array(cnt).fill(src[0]);
          const last = src.length - 1, o2 = [];
          for (let i = 0; i < cnt; i++){ const pos = (i * last) / Math.max(1, cnt - 1), lo = Math.trunc(pos), hi = Math.min(last, lo + 1); o2.push(src[lo] + (src[hi] - src[lo]) * (pos - lo)); }
          return o2;
        };
        const sn = Math.max(1, n);
        const lt = (oldN !== newN && e >= 0.98) ? 1 : e;
        const oc = resample(normRun(a.values || []), sn), nc = resample(normRun(m.values || []), sn);
        out.cumCurve = oc.map(function(v, i){ return v + (nc[i] - v) * lt; });
      }
      out.flags = []; for (let i = 0; i < n; i++){ const w = inn(i); out.flags.push(w >= 0 ? !!m.flags[w] : false); }
      // the backlog colour fades in / out with the bars (it switched at once: a bar became / stopped being backlog)
      out.flagW = []; for (let i = 0; i < n; i++){ const o = io(i), w = inn(i); const f0 = o >= 0 && a.flags && a.flags[o] ? 1 : 0, f1 = w >= 0 && m.flags[w] ? 1 : 0; out.flagW.push(f0 + (f1 - f0) * e); }
      if (m.colorFn) out.colorFn = function(i){ const w = inn(i); return m.colorFn(w >= 0 ? w : Math.max(0, Math.min(newN - 1, i))); };
      out._mFrom = a; out._mTo = m; out._e = e; out._t = t;  // the plot's margins & X-axis labels glide between the two sides' (draw)
      return out;
    }


    // ---- tooltip (get_tooltip_text of each chart) ----
    indexAt(mx, my){
      const g = this.geo, n = this.m.count;
      if (!g || n <= 0 || this.m.emptyDeck) return -1;
      if (!(mx >= g.ml && mx <= this.w - g.mr && my >= g.mt && my <= this.h - g.mb)) return -1;
      const step = g.plotW / n;
      return Math.max(0, Math.min(n - 1, Math.trunc((mx - g.ml) / step)));
    }
    // the cards a distribution counts in all (its % in the hover): every bar it can show, zoomed or capped or not
    allCount(){
      const p = this.payload || {}, t = BASE[this.type] || this.type, flat = t === 'stability' || t === 'difficulty' || t === 'retrievability';
      const d = (flat ? p.data : p.data && p.data.distribution) || {}, lo = flat ? 0 : 1;
      let s = Number(p.zero_bar) || 0;
      Object.keys(d).forEach(function(k){ if (Number(k) >= lo) s += Math.max(0, Number(d[k]) || 0); });
      return s;
    }
    // the hover's rows; a distribution's bar its share of all, its running total too (not zoomed: from the first bar)
    tipRows(i){
      const rows = this.baseRows(i), m = this.m, t = BASE[this.type] || this.type;
      if (t === 'future_due' || !rows || !rows.length) return rows;
      const all = this.allCount();
      if (!(all > 0)) return rows;
      const pc = function(x){ const p = x * 100 / all; return (p > 0 && p < 0.1 ? '<0.1' : U.trimNum(p, p < 10 ? 1 : 0)) + '%'; };
      if (rows[0].value == null) rows[0].value = pc(m.values[i] || 0);
      if (rows.length > 1 && !m.win && rows[1].value == null){ let r = 0; for (let k = 0; k <= i; k++) r += m.values[k] || 0; rows[1].value = pc(r); }
      return rows;
    }
    baseRows(i){
      const m = this.m, t = BASE[this.type] || this.type, C = this.colors;
      const noun = function(n, one, many){ return n === 1 ? one : many; };
      const fmt = U.formatNum;
      const running = function(){ let r = 0; for (let k = 0; k <= i; k++) r += m.values[k] || 0; return r; };
      const cum = this.options.show_cumulative !== false && !m.noCum;
      const v = m.values[i] || 0;
      if (t === 'future_due'){
        const r = m.ranges[i], day = r[0], next = r[1];
        let label, labelKey, lv;  // the label alone, and the key of "label: N reviews"
        if (next - day > 1){
          if (day < 0 && next <= 0){ lv = {start: Math.abs(day), end: Math.abs(next - 1)}; label = DD.t('{start}-{end} days ago', lv); labelKey = '{start}-{end} days ago: {reviews}'; }
          else { lv = {start: day, end: next - 1}; label = DD.t('Days {start}-{end}', lv); labelKey = 'Days {start}-{end}: {reviews}'; }
        }
        else if (day === -1) label = DD.t('Yesterday'); else if (day < -1){ lv = {days: Math.abs(day)}; label = DD.t('{days} days ago', lv); labelKey = '{days} days ago: {reviews}'; }
        else if (day === 0) label = DD.t('Today'); else { lv = {day: day}; label = DD.t('Day {day}', lv); labelKey = 'Day {day}: {reviews}'; }
        if (m.parts){
          const sums = m.parts.sums[i], rows = [];
          rows.push({header: true, text: label, value: v ? DD.tn('{n} card', '{n} cards', v, {n: fmt(v)}) : ''});
          const names = m.parts.kind === 'result' ? ['Good', 'Again', 'Future'] : ['Mature', 'Young', 'Learning'];
          const tot = sums[0] + sums[1] + sums[2];
          for (let k = 2; k >= 0; k--){
            const n = sums[k];
            if (n >= 0.05) rows.push({text: names[k], value: Number.isInteger(n) ? fmt(n) : U.trimNum(n, 1), color: C[m.parts.colors[k]]});
          }
          if (m.parts.kind === 'result' && sums[0] + sums[1] > 0) rows.push({text: 'Expected retention', value: U.trimNum(sums[0] / (sums[0] + sums[1]) * 100, 1) + '%'});
          if (cum) rows.push({text: '<b>' + DD.t('Total: {value}', {value: fmt(running())}) + '</b>'});
          return rows;
        }
        const revs = DD.tn('{n} review', '{n} reviews', v, {n: fmt(v)});
        const rows = [{text: labelKey ? DD.t(labelKey, Object.assign({reviews: revs}, lv)) : label + ': ' + revs}];
        if (cum) rows.push({text: DD.tn('Total: {count} review', 'Total: {count} reviews', running(), {count: fmt(running())})});
        return rows;
      }
      if (t === 'interval_load'){
        const r = m.ranges[i];
        const days = r[1] - r[0] > 1 ? r[0] + '-' + (r[1] - 1) : String(r[0]);
        const rows = [{text: DD.t('Interval {days} days: {value}', {days: days, value: perDay(v)})}];
        if (cum) rows.push({text: DD.t('Total: {value}', {value: perDay(running())})});
        return rows;
      }
      if (t === 'time_distribution'){
        // cards by the seconds spent on them; Total Time: the time of those cards
        const r = m.ranges[i];
        const what = r[1] - r[0] > 1 ? dur(r[0]) + ' \u2013 ' + dur(r[1] - 1) : dur(r[0]);
        if (this.payload.measure === 'total'){
          const out = [{text: DD.t('{name}: {value}', {name: what, value: dur(v)})}];
          if (cum) out.push({text: DD.t('Total: {value}', {value: dur(running())})});
          return out;
        }
        const rows = [{text: DD.tn('{value}: {n} card', '{value}: {n} cards', v, {value: what, n: fmt(v)})}];
        if (cum) rows.push({text: DD.tn('Total: {count} card', 'Total: {count} cards', running(), {count: fmt(running())})});
        return rows;
      }
      if (CARD_HISTORY[t]){
        const r = m.ranges[i], nm = CARD_HISTORY[t], ms = this.payload.measure;
        const what = r[1] - r[0] > 1 ? r[0] + '-' + (r[1] - 1) : DD.tn('{n} ' + nm[0], '{n} ' + nm[1], r[0]);
        // Total: the lapses / reviews of those cards; Load: their reviews a day
        if (ms === 'total' || ms === 'load'){
          const val = function(x){ return ms === 'load' ? perDay(x) : DD.tn('{n} ' + nm[0], '{n} ' + nm[1], x, {n: fmt(x)}); };
          const out = [{text: DD.t('{name}: {value}', {name: what, value: val(v)})}];
          if (cum) out.push({text: DD.t('Total: {value}', {value: val(running())})});
          return out;
        }
        const rows = [{text: DD.tn('{value}: {n} card', '{value}: {n} cards', v, {value: what, n: fmt(v)})}];
        if (cum) rows.push({text: DD.tn('Total: {count} card', 'Total: {count} cards', running(), {count: fmt(running())})});
        return rows;
      }
      if (t === 'review_intervals' || t === 'interval_history'){
        const r = m.ranges[i];
        const days = r[1] - r[0] > 1 ? r[0] + '-' + (r[1] - 1) : String(r[0]);
        const rows = [{text: DD.tn('Interval {days} days: {count} card', 'Interval {days} days: {count} cards', v, {days: days, count: fmt(v)})}];
        if (cum) rows.push({text: DD.tn('Total: {count} card', 'Total: {count} cards', running(), {count: fmt(running())})});
        return rows;
      }
      if (t === 'stability'){
        // its bin's days (zoomed too); the first of the whole view's from 0 as before
        const r = m.ranges[i], r0 = (!m.win && r[0] === 1 && r[1] - r[0] > 1) ? 0 : r[0];
        const rows = [{text: DD.tn('Stability {days} days: {n} card', 'Stability {days} days: {n} cards', v, {days: r[1] - r0 > 1 ? r0 + '-' + (r[1] - 1) : r0, n: fmt(v)})}];
        if (cum) rows.push({text: DD.tn('Total: {count} card', 'Total: {count} cards', running(), {count: fmt(running())})});
        return rows;
      }
      const rows = [{text: t === 'difficulty' ? DD.tn('Difficulty {value}%: {n} card', 'Difficulty {value}%: {n} cards', v, {value: i.toFixed(1), n: fmt(v)})
                                        : DD.tn('Retrievability {value}%: {n} card', 'Retrievability {value}%: {n} cards', v, {value: i.toFixed(1), n: fmt(v)})}];
      // Breakdown by Type: the bar's cards of each type, the top one first
      const ps = m.parts && m.parts.kind === 'type' && m.parts.sums[i];
      if (ps) for (let k = 2; k >= 0; k--) if (ps[k] > 0) rows.push({text: ['Mature', 'Young', 'Learning'][k], value: fmt(ps[k]), color: C[m.parts.colors[k]]});
      return rows;
    }

    draw(){
      const ctx = this.ctx, w = this.w, h = this.h, m = this.blended(), C = this.colors;
      ctx.clearRect(0, 0, w, h);
      const dark = !!C.is_dark;
      const n = m.count;
      const values = m.values;
      const rawMax = Math.max.apply(null, values.concat([0]));
      const axisMax = m.axisMax != null ? m.axisMax : (m.emptyDeck || n <= 0 ? 4 : (rawMax > 0 ? rawMax : 1));
      const sum = values.reduce(function(a, b){ return a + b; }, 0);
      const showCum = this.options.show_cumulative !== false && !m.noCum;
      const totalCards = sum === 0 ? 1 : sum;
      const t = Math.max(0, Math.min(1, this.progress));
      const intro = U.easeOutQuart(t);

      ctx.font = FONT;
      // the margins fit the axis numbers (left: the top value; right: the running total's); during a transition they
      // glide from the old chart's to the new one's, never snapping by a whole digit as the numbers count
      const self = this;
      const marginsOf = function(mm){
        const vv = mm.values || [], raw = Math.max.apply(null, vv.concat([0]));
        const ax = mm.axisMax != null ? mm.axisMax : (mm.emptyDeck || (mm.count || 0) <= 0 ? 4 : (raw > 0 ? raw : 1));
        const lab = ax >= 10 ? U.formatNum(Math.trunc(ax)) : (Math.round(ax * 10) / 10).toFixed(1);
        const l = Math.max(35, Math.trunc(ctx.measureText(lab).width) + 12);
        let r = mm.noCum ? 8 : 20;
        if (self.options.show_cumulative !== false && !mm.noCum){
          const sm = vv.reduce(function(a, b){ return a + b; }, 0);
          let rw = 0;
          for (let g = 0; g <= 4; g++) rw = Math.max(rw, ctx.measureText(U.formatNum(Math.trunc(sm * g / 4))).width);
          r = Math.max(20, Math.trunc(rw) + 10);
        }
        return [l, r];
      };
      let ml, mr;
      if (m._mFrom && m._mTo){
        const p0 = marginsOf(m._mFrom), p1 = marginsOf(m._mTo), e = m._e;
        ml = Math.round(p0[0] + (p1[0] - p0[0]) * e); mr = Math.round(p0[1] + (p1[1] - p0[1]) * e);
      } else { const p = marginsOf(m); ml = p[0]; mr = p[1]; }
      const mt = 10, mb = 30;
      const plotW = w - ml - mr, plotH = h - mt - mb;
      this.geo = {ml: ml, mr: mr, mt: mt, mb: mb, plotW: plotW, plotH: plotH};

      // grid + left axis
      const grid = parseColor((this.options && this.options.show_grid === false ? 'rgba(0,0,0,0)' : C.grid));
      const txt = parseColor(C.text_secondary);
      const axisCol = css(txt, ((dark ? 175 : 215) / 255).toFixed(4));
      const axisCol2 = css(txt, ((dark ? 175 : 215) * 0.8 / 255).toFixed(4));
      ctx.textBaseline = 'middle';
      if (DD.axisSlide && DD.axisSlide()){
        // Chart_Axis_Anim 'slide' (dd-core DD.slideAxis): round values at their heights on the scale of the moment, the
        // exact top written too; on a change of scale they slide, the old ones leave and the new ones come
        const fmtV = (v) => (v === 0 ? '0' : (v >= 10 ? U.formatNum(Math.trunc(v)) : U.trimNum(v, 1)));
        // during a change (m.ax: its start and end tops, its progress) the values slide with the bars; the axis' own
        // 220 ms fades ran apart from them and left values half there
        (m.ax ? DD.slideTicks(m.ax[0], m.ax[1], axisMax, m.ax[2], 4, plotH, {tag: this.type}) : DD.slideTicks(axisMax, axisMax, axisMax, 1, 4, plotH, {tag: this.type})).forEach((k) => {
          const y = mt + plotH * (1 - k.f), yl = Math.trunc(y) + 0.5;
          ctx.globalAlpha = k.a;
          ctx.strokeStyle = css(grid, Math.min(1, grid.a * (k.f <= 0.0005 ? 2.6 : 1.5))); ctx.lineWidth = 1;
          ctx.beginPath(); ctx.moveTo(ml, yl); ctx.lineTo(w - mr, yl); ctx.stroke();
          ctx.fillStyle = axisCol; ctx.textAlign = 'right'; ctx.fillText(fmtV(k.v), ml - 8, Math.trunc(y));
        });
        ctx.globalAlpha = 1;
      } else for (let i = 0; i <= 4; i++){
        const yr = i / 4;
        const y = mt + plotH * (1 - yr);
        const base = i === 0;
        ctx.strokeStyle = css(grid, Math.min(1, grid.a * (base ? 2.6 : 1.5)));
        ctx.lineWidth = 1;
        const yl = Math.trunc(y) + 0.5;
        ctx.beginPath(); ctx.moveTo(ml, yl); ctx.lineTo(w - mr, yl); ctx.stroke();
        const val = axisMax * yr;
        ctx.fillStyle = axisCol; ctx.textAlign = 'right';
        ctx.fillText(i === 0 ? '0' : (val >= 10 ? U.formatNum(Math.trunc(val)) : U.trimNum(val, 1)), ml - 8, Math.trunc(y));
      }

      // bars
      const step = n > 0 ? plotW / n : plotW;
      const barW = Math.max(1, step * (this.adapter.widthRatio || 0.9));
      const slots = m.slotsFn ? m.slotsFn(ml, plotW, this.adapter.widthRatio || 0.9) : null;
      const lstep = m.labelCount ? plotW / m.labelCount : step;  // the x labels follow the new bars
      const gradK = (this.options.bar_gradient_pct != null ? this.options.bar_gradient_pct : GRAD_PCT) / 100;
      const opac = Math.max(0, Math.min(100, this.options.chart_opacity_pct != null ? this.options.chart_opacity_pct : 100)) * 2.55 / 255;
      const baseHex = C[this.adapter.colorKey] || C.bar;
      const bottom = mt + plotH;
      this.hoverDots = [];
      const fadeFill = function(hex, x, y, bw, bh, alphaF){ return barFill(ctx, hex, y, bw, bh, alphaF, dark, gradK); };
      const rect = function(x, y, bw, bh, fill, rounded){ roundedBar(ctx, x, y, bw, bh, fill, rounded); };
      const maxR = Math.max(1, axisMax);
      // a bar's colour: the backlog one, the chart's own, or between the two during a transition (m.flagW)
      const barHex = function(i, x, bw){
        const own = m.colorFn ? m.colorFn(i) : gradientColor(baseHex, (x + bw / 2 - ml) / Math.max(1, plotW), dark);
        const fw = m.flagW ? m.flagW[i] : (m.flags[i] ? 1 : 0);
        if (fw >= 0.999) return C.backlog || baseHex;
        if (fw <= 0.001) return own;
        return mixHex(own, C.backlog || baseHex, fw);
      };
      for (let i = 0; i < n; i++){
        const v = values[i] || 0;
        if (i === this.hover && !slots) hoverColumn(ctx, ml + i * step, step, mt, plotH, dark, C.text_primary);
        if (v === 0) continue;
        const slot = slots ? slots[i] : null, bw = slot ? slot[1] : barW;
        const x = slot ? slot[0] - bw / 2 : ml + i * step + (step - bw) / 2;
        const bh = (v / maxR) * plotH * intro;
        const y = bottom - bh;
        const hov = i === this.hover;
        const sh = m.parts ? m.parts.shares[i] : null;
        const ws = (m.parts && m.parts.wsplit != null) ? Math.max(0, Math.min(1, m.parts.wsplit)) : 1;
        if (sh && (sh[0] + sh[1] + sh[2]) > 0 && ws < 0.999){
          // the plain bar under the type colours fading in / out
          let ph;
          ph = barHex(i, x, bw);
          rect(x, y, bw, bh, fadeFill(ph, x, y, bw, bh, opac), true);
        }
        if (sh && (sh[0] + sh[1] + sh[2]) > 0 && ws > 0.001){
          ctx.save(); ctx.globalAlpha *= ws;
          const parts = sh, whole = parts[0] + parts[1] + parts[2];
          const tops = []; let acc = 0;
          for (let k = 0; k < 3; k++){ acc += parts[k]; tops.push(bottom - bh * (acc / whole)); }
          let top = 2; for (let k = 2; k >= 0; k--){ if (parts[k] > 1e-6){ top = k; break; } }
          for (let k = 2; k >= 0; k--){
            if (parts[k] <= 1e-6) continue;
            let hex = C[m.parts.colors[k]] || baseHex;
            if (m.parts.mixFrom) hex = mixHex(C[m.parts.mixFrom[k]] || baseHex, hex, m.parts.mixW);
            let segBottom = bottom;
            for (let j = k - 1; j >= 0; j--){ if (parts[j] > 1e-6){ segBottom = tops[j]; break; } }
            const segTop = k === top ? tops[k] : tops[k] - 0.75;
            if (hov){
              rect(x, segTop, bw, Math.max(0, segBottom - segTop), U.hoverFill(hex, dark), k === top);
              this.hoverDots.push([x + bw / 2, (tops[k] + segBottom) / 2, hex]);
            } else {
              rect(x, segTop, bw, Math.max(0, segBottom - segTop), fadeFill(hex, x, y, bw, bh, opac), k === top);
            }
          }
          ctx.restore();
          continue;
        }
        if (sh && (sh[0] + sh[1] + sh[2]) > 0) continue;  // all plain this frame (drawn above)
        const hex = barHex(i, x, bw);
        if (hov) rect(x, y, bw, bh, U.hoverFill(hex, dark), true);
        else rect(x, y, bw, bh, fadeFill(hex, x, y, bw, bh, opac), true);
      }

      // cumulative curve + area
      const lineK = (this.options.line_opacity_pct != null ? this.options.line_opacity_pct : LINE_PCT) / 100;
      if (showCum && n > 0){
        const cumK = this.morph ? 1 : intro;
        const pts = [];
        if (m.cumCurve && m.cumCurve.length){
          const cc = m.cumCurve, cn = cc.length;
          for (let i = 0; i < cn; i++) pts.push([cn > 1 ? ml + plotW * i / (cn - 1) : ml + plotW * 0.5, mt + plotH - cc[i] * plotH * cumK]);
        } else {
          let run = 0;
          for (let i = 0; i < n; i++){
            run += values[i] || 0;
            pts.push([n > 1 ? ml + plotW * i / (n - 1) : ml + plotW * 0.5, mt + plotH - (run / totalCards * plotH) * cumK]);
          }
        }
        ctx.save();
        ctx.beginPath(); ctx.rect(ml, mt - 2, plotW, plotH + 2); ctx.clip();
        ctx.beginPath(); U.smoothPath(ctx, pts);
        ctx.lineTo(pts[pts.length - 1][0], bottom); ctx.lineTo(pts[0][0], bottom); ctx.closePath();
        // as Anki's charts draw it (.cumulative-overlay): a flat pale area in the text's colour (Anki: black 3 % light,
        // white 8 % dark), its edge a faint dark line (black 8 % / 18 %); the Total / Average Lines setting scales both,
        // its default giving Anki's values
        const A = DD.areaStyle(C, dark, lineK * 100 / LINE_PCT);
        ctx.fillStyle = U.rgba(A.fill, A.fillA); ctx.fill();
        ctx.lineJoin = 'round'; ctx.lineCap = 'round';
        ctx.beginPath(); U.smoothPath(ctx, pts);
        ctx.strokeStyle = U.rgba(A.line, A.lineA); ctx.lineWidth = A.lw; ctx.stroke();
        // the Total Line setting (none by default): a clear line over that edge, as before
        const strong = (this.options.total_line_pct || 0) / 100;
        if (strong > 0){
          const bgc = C.bg || (dark ? '#000000' : '#ffffff');
          ctx.strokeStyle = U.rgba(dark ? U.scaleV(bgc, 1 / 1.6) : bgc, Math.min(1, 150 / 255 * lineK * strong)); ctx.lineWidth = 3.4; ctx.stroke();
          ctx.strokeStyle = U.rgba(C.text_primary || C.total_line || (dark ? '#ffffff' : '#000000'), Math.min(1, 215 / 255 * lineK * strong)); ctx.lineWidth = 1.3; ctx.stroke();
        }
        ctx.restore();
      }

      // x axis (glides matching labels & cross-fades changed ones during morphs so numbers never snap)
      ctx.font = m.labelPx ? (m.labelPx + 'px "Segoe UI",-apple-system,BlinkMacSystemFont,sans-serif') : FONT_X; ctx.fillStyle = css(txt, 1);
      const yLab = h - mb + 5 + 7.5;
      const xMarksOf = function(mm){
        const out = [];
        if (!mm || mm.emptyDeck) return out;
        const st = plotW / Math.max(1, mm.count || 1);
        if (mm.labelsFn){
          mm.labelsFn({ml: ml, step: st, plotW: plotW}).forEach(function(l){
            out.push({x: l.x, text: String(l.text), align: 'center'});
          });
        }
        (mm.labels || []).forEach(function(l){
          if (mm.fracLabels){
            const x = ml + l.frac * plotW;
            const al = l.align === 'left' ? 'left' : (l.align === 'right' ? 'right' : 'center');
            out.push({x: al === 'left' ? ml : x, text: String(l.text), align: al});
          } else {
            out.push({x: ml + l[0] * st + st / 2, text: String(l[1]), align: 'center'});
          }
        });
        return out;
      };
      if (m._mFrom && m._mTo && m._t != null && m._t < 1){
        const sm = function(x){ x = Math.max(0, Math.min(1, x)); return x * x * (3 - 2 * x); };
        const oldM = xMarksOf(m._mFrom), newM = xMarksOf(m._mTo), em = m._e, tm = m._t;
        const cntA = {}, cntB = {}, byB = {};
        oldM.forEach(function(l){ cntA[l.text] = (cntA[l.text] || 0) + 1; });
        newM.forEach(function(l){ cntB[l.text] = (cntB[l.text] || 0) + 1; byB[l.text] = l; });
        const matched = {};
        ctx.save();
        oldM.forEach(function(l){
          if (cntA[l.text] === 1 && cntB[l.text] === 1){
            const nb = byB[l.text];
            matched[l.text] = true;
            ctx.globalAlpha = 1;
            ctx.textAlign = nb.align;
            ctx.fillText(l.text, l.x + (nb.x - l.x) * em, yLab);
          } else {
            const a = 1 - sm(tm / 0.35);
            if (a > 0.005){ ctx.globalAlpha = a; ctx.textAlign = l.align; ctx.fillText(l.text, l.x, yLab); }
          }
        });
        newM.forEach(function(l){
          if (matched[l.text]) return;
          const a = sm((tm - 0.3) / 0.45);
          if (a > 0.005){ ctx.globalAlpha = a; ctx.textAlign = l.align; ctx.fillText(l.text, l.x, yLab); }
        });
        ctx.restore();
      } else {
        xMarksOf(m).forEach(function(l){ ctx.textAlign = l.align; ctx.fillText(l.text, l.x, yLab); });
      }
      if (m._mFrom && m._mTo && m._t != null && m._t < 1 && (m._mFrom.zeroIdx != null || m._mTo.zeroIdx != null)){
        const z0 = m._mFrom.zeroIdx, z1 = m._mTo.zeroIdx;
        const x0 = z0 != null ? ml + z0 * (plotW / Math.max(1, m._mFrom.count || 1)) : null;
        const x1 = z1 != null ? ml + z1 * (plotW / Math.max(1, m._mTo.count || 1)) : null;
        const zx = Math.trunc(x0 != null && x1 != null ? x0 + (x1 - x0) * m._e : (x1 != null ? x1 : x0));
        const za = x0 != null && x1 != null ? 1 : (x1 != null ? m._e : 1 - m._e);
        if (za > 0.01){
          ctx.save(); ctx.globalAlpha = za; ctx.setLineDash([3.2, 3.2]);
          ctx.strokeStyle = css(txt, 1); ctx.lineWidth = 0.8;
          ctx.beginPath(); ctx.moveTo(zx, mt); ctx.lineTo(zx, h - mb); ctx.stroke(); ctx.restore();
        }
      } else if (m.zeroIdx != null){
        const zx = Math.trunc(ml + m.zeroIdx * lstep);
        ctx.save(); ctx.setLineDash([3.2, 3.2]);
        ctx.strokeStyle = css(txt, 1); ctx.lineWidth = 0.8;
        ctx.beginPath(); ctx.moveTo(zx, mt); ctx.lineTo(zx, h - mb); ctx.stroke(); ctx.restore();
      }

      // right axis
      if (showCum){
        ctx.font = FONT; ctx.fillStyle = axisCol2; ctx.textAlign = 'right';
        if (DD.axisSlide && DD.axisSlide()){
          (m.ax ? DD.slideTicks(m.ax[3], m.ax[4], totalCards, m.ax[2], 4, plotH) : DD.slideTicks(totalCards, totalCards, totalCards, 1, 4, plotH)).forEach((k) => {
            ctx.globalAlpha = k.a; ctx.fillText(U.formatNum(Math.trunc(k.v)), w - 4, Math.trunc(mt + plotH * (1 - k.f)));
          });
          ctx.globalAlpha = 1;
        } else for (let i = 0; i <= 4; i++){
          const y = mt + plotH * (1 - i / 4);
          ctx.fillText(U.formatNum(Math.trunc(totalCards * i / 4)), w - 4, Math.trunc(y));
        }
      }

      // the zone being picked for a zoom (Future Due)
      if (this.sel){
        const x1 = Math.max(ml, Math.min(this.sel[0], this.sel[1])), x2 = Math.min(ml + plotW, Math.max(this.sel[0], this.sel[1]));
        if (x2 > x1){
          const acc = parseColor(C.accent || '#3b82f6');
          ctx.save();
          ctx.fillStyle = css(acc, 0.08); ctx.fillRect(x1, mt, x2 - x1, plotH);
          ctx.strokeStyle = css(acc, 0.78); ctx.lineWidth = 1.5; ctx.strokeRect(x1, mt, x2 - x1, plotH);
          ctx.restore();
        }
      }

      // hover dots (breakdown)
      if (this.hoverDots.length){
        const outline = C.tooltip_border || '#888';
        this.hoverDots.forEach(function(d){
          ctx.beginPath(); ctx.arc(d[0], d[1], 4, 0, Math.PI * 2); ctx.fillStyle = d[2]; ctx.fill();
          ctx.lineWidth = 1.5; ctx.strokeStyle = outline; ctx.stroke();
        });
      }
    }
  }

  // the values of an axis: round ones sliding from the top a to the top b (Chart_Axis_Anim 'slide', DD.slideTicks),
  // else the top's quarters -> [{f: height 0-1, v, a: alpha}]
  function axisTicks(a, b, cur, e, plotH, tag){
    if (DD.axisSlide && DD.axisSlide()) return DD.slideTicks(a, b, cur, e, 4, plotH, tag ? {tag: tag} : undefined);
    const out = []; for (let i = 0; i <= 4; i++) out.push({f: i / 4, v: cur * i / 4, a: 1});
    return out;
  }

  // ---- header pills of Future Due -------------------------------------------------------
  const CHEV = '<svg class="dd-pill-chev" width="8" height="6" viewBox="0 0 8 6"><path d="M1 1.5L4 4.5L7 1.5" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  function shortLabel(l){ const m = { '1 week': '1w', '2 weeks': '2w', '1 month': '1m', '3 months': '3m', '1 year': '1y' }; return m[l] || l; }
  // the median of a distribution {n: cards} (n >= 1): the middle card's n, the mean of the two middle ones for an even count
  function distMedian(dist){
    const ks = Object.keys(dist || {}).map(Number).filter(function(k){ return k > 0 && Number(dist[k]) > 0; }).sort(function(a, b){ return a - b; });
    let n = 0; ks.forEach(function(k){ n += Number(dist[k]); });
    if (!n) return null;
    const at = function(i){ let acc = 0; for (let j = 0; j < ks.length; j++){ acc += Number(dist[ks[j]]); if (acc > i) return ks[j]; } return ks[ks.length - 1]; };
    return (at(Math.floor((n - 1) / 2)) + at(Math.ceil((n - 1) / 2))) / 2;
  }

  function headFor(type, payload, head, model){
    if (!head) return;
    const pillsEl = head.querySelector('.dd-pills');
    if (!pillsEl) return;
    const acc = (DD.theme.chart && DD.theme.chart.accent) || '#3b82f6';
    head.style.setProperty('--dd-accent-b', U.rgba(acc, 0.6));
    head.style.setProperty('--dd-accent-f', U.rgba(acc, 0.12));
    pillsEl.innerHTML = '';
    const add = function(label, on, menu, onClick, tip){
      const b = document.createElement('button');
      b.className = 'dd-pill' + (on ? ' on' : '');
      b.innerHTML = label + (menu ? CHEV : '');
      if (tip) b.title = tip;
      if (onClick) b.addEventListener('click', function(e){ e.stopPropagation(); onClick(b); });
      pillsEl.appendChild(b);
    };
    const section = payload.kind || type;
    // a Time Machine's day: the date, its calendar on a click (machineSlider's head._ddDay)
    const dayPill = function(){ if (payload.date) add(dayText(payload.date), false, true, function(b){ if (head._ddDay) head._ddDay(b); }, 'Day shown'); };
    const pick = function(btn, items, edit, onPick){
      const r = btn.getBoundingClientRect();
      // a choice is taken at once and the menu stays open, as the period list of Activity (radio entries)
      items = items.map(function(it){ return (it !== 'sep' && it[2] !== undefined && it[2] !== null) ? [it[0], it[1], it[2], null, 'radio'] : it; });
      if (edit) items = items.concat(['sep', ['__edit', 'Edit Buttons...']]);
      DD.menu({x: r.left, y: r.bottom + 2}, items, function(k){ if (k === '__edit') DD.openWidgetSettings(section); else onPick(k); });
    };
    // the range / filter choices: one pill with the current choice and a menu of all of them (always folded)
    const choices = function(labels, idx, key){
      if (!labels || !labels.length) return false;
      const full = labels.map(function(l, i){ return [String(i), l, i === idx]; });
      let cur = idx;  // the menu stays open: the last one picked
      add(shortLabel(labels[idx]), false, true, function(b){ pick(b, full, true, function(k){ if (+k !== cur){ cur = +k; DD.setWidgetSetting(section, key, +k); } }); }, labels[idx]);
      return true;
    };
    if (type === 'future_due'){
      const bd = payload.breakdown;
      add(bd === 'result' ? 'Breakdown by Result' : (bd === 'type' ? 'Breakdown by Type' : 'Breakdown'), !!bd, true, function(b){
        let cur = bd || 'none';
        pick(b, [['none', 'Off', !bd], ['type', 'Breakdown by Type', bd === 'type'], ['result', 'Breakdown by Result', bd === 'result']], false, function(k){ if (k !== cur){ cur = k; DD.setWidgetSetting('future_due', 'breakdown', k); } });
      });
      add('Backlog', !!payload.backlog, false, function(){ DD.setWidgetSetting('future_due', 'show_backlog', !payload.backlog); });
      if (!choices(payload.range_labels, payload.range_idx, 'time_span_idx')) add(payload.range_label || 'all', false, true);
    } else if (type === 'stability'){
      const st = head.querySelector('.dd-stat');
      if (st && model && model.stat) st.textContent = model.stat;
      if (!choices(payload.filter_labels, payload.filter_idx, 'time_span_idx')) add(payload.filter_label || '95%', false, true);
    } else if (type === 'difficulty' || type === 'retrievability'){
      const st = head.querySelector('.dd-stat');
      if (st && model) st.textContent = model.stat || '';
    } else if (type === 'time_distribution'){
      const st = head.querySelector('.dd-stat');
      const d = payload.data || {};
      const total = Number(d.total) || 0, sum = Number(d.sum) || 0, ms = payload.measure || 'count';
      if (st){
        const avg = total > 0 ? DD.t('Avg: {value}', {value: dur(sum / total)}) : '';
        st.textContent = total > 0 && ms === 'total' ? DD.t('Total: {value}', {value: dur(sum)}) + '  \u00b7  ' + avg : avg;
      }
      // what the bars sum: the cards, or the time spent on them
      const names = {count: 'Cards', total: 'Total Time'};
      add(names[ms] || names.count, ms === 'total', true, function(b){
        let cur = ms;
        pick(b, [['count', names.count, cur === 'count'], ['total', names.total, cur === 'total']], false,
          function(k){ if (k !== cur){ cur = k; DD.setWidgetSetting(type, 'measure', k); } });
      }, 'Cards, or the time spent on them');
      if (!choices(payload.filter_labels, payload.filter_idx, 'time_span_idx')) add(payload.filter_label || '95%', false, true);
    } else if (type === 'interval_load' || CARD_HISTORY[type]){
      const st = head.querySelector('.dd-stat');
      const d = payload.data || {};
      if (st){
        if (type === 'interval_load'){
          let tot = 0; Object.keys(d.distribution || {}).forEach(function(k){ tot += Number(d.distribution[k]) || 0; });
          st.textContent = tot > 0 ? DD.t('Daily load: {value}', {value: perDay(tot)}) : '';
        } else {
          const total = Number(d.total) || 0, zero = Number(d.zero) || 0, sum = Number(d.sum) || 0, nm = CARD_HISTORY[type];
          const txt = function(v){ const t0 = U.trimNum(v, 1); return DD.tn('{n} ' + nm[0], '{n} ' + nm[1], Number(t0), {n: t0}); };
          let out = '';
          if (total > 0){
            if (type === 'learning_steps'){
              const learned = total - zero;
              const parts = [];
              if (learned) parts.push(DD.t('Avg: {value}', {value: txt(sum / Math.max(1, learned))}));
              const md = distMedian(d.distribution);
              if (learned && md !== null) parts.push(DD.t('Median: {value}', {value: txt(md)}));
              if (zero) parts.push(DD.tn('Without learning: {count} card', 'Without learning: {count} cards', zero, {count: U.formatNum(zero)}));
              out = parts.join('  \u00b7  ');
            } else if (payload.measure === 'load'){
              let ld = Number(d.load_zero) || 0; Object.keys(d.load || {}).forEach(function(k){ ld += Number(d.load[k]) || 0; });
              out = ld > 0 ? DD.t('Daily load: {value}', {value: perDay(ld)}) : '';
            } else if (payload.measure === 'total'){
              out = DD.t('Total: {value}', {value: DD.tn('{n} ' + nm[0], '{n} ' + nm[1], sum, {n: U.formatNum(sum)})}) + '  \u00b7  ' +
                DD.t('Avg: {value}', {value: txt(sum / total)});
            } else {
              out = DD.t('Avg: {value}', {value: txt(sum / total)});
              if (type === 'lapse_distribution') out += '  \u00b7  ' + DD.t('Never forgotten: {value}%', {value: U.trimNum(zero * 100 / total, 1)});
            }
            // its leeches: the cards at their preset's leech threshold or over (the threshold when the decks share it)
            if (type === 'lapse_distribution' && payload.leeches != null && out){
              const nl = Number(payload.leeches) || 0;
              out += '  \u00b7  ' + (payload.leech_at
                ? DD.tn('Leeches ({n}+ lapses): {count} card', 'Leeches ({n}+ lapses): {count} cards', nl, {n: payload.leech_at, count: U.formatNum(nl)})
                : DD.tn('Leeches: {count} card', 'Leeches: {count} cards', nl, {count: U.formatNum(nl)}));
            }
            // their numbers sum all the history: the period does not change them
            if (out) out += '  \u00b7  ' + DD.t('Whole history');
          }
          st.textContent = out;
        }
      }
      // what the bars sum: the cards, their lapses / reviews, their load
      if (type === 'lapse_distribution' || type === 'review_distribution'){
        const ms = payload.measure || 'count';
        const names = {count: 'Cards', total: type === 'lapse_distribution' ? 'Total Lapses' : 'Total Reviews', load: 'Load'};
        add(names[ms], ms !== 'count', true, function(b){
          let cur = ms;
          pick(b, [['count', names.count, cur === 'count'], ['total', names.total, cur === 'total'], ['load', names.load, cur === 'load']], false,
            function(k){ if (k !== cur){ cur = k; DD.setWidgetSetting(type, 'measure', k); } });
        }, type === 'lapse_distribution' ? 'Cards, their lapses, or their reviews a day (load)' : 'Cards, their reviews, or their reviews a day (load)');
      }
      if (!choices(payload.filter_labels, payload.filter_idx, 'time_span_idx')) add(payload.filter_label || '95%', false, true);
    } else if (type === 'interval_history'){
      // the intervals on the period's first day
      const st = head.querySelector('.dd-stat');
      if (st){
        const n = payload.median || 0;
        const d = payload.data || {}, tot = Number(d.total) || 0, mean = tot > 0 ? (Number(d.sum) || 0) / tot : 0;
        st.textContent = DD.tn('Median interval: {n} day', 'Median interval: {n} days', n) + (tot > 0 ? '  \u00b7  ' +
          DD.t('Avg: {value}', {value: DD.tn('{n} day', '{n} days', mean, {n: U.trimNum(mean, 1)})}) : '');
      }
      dayPill();
      if (!choices(payload.filter_labels, payload.filter_idx, 'time_span_idx')) add(payload.filter_label || '95%', false, true);
    } else if (BASE[type]){
      // the memory states on the period's first day: that day, then the stats of Card Stability / Card Difficulty
      const st = head.querySelector('.dd-stat');
      if (st){
        st.textContent = (model && model.stat) || '';
      }
      dayPill();
      if (type === 'stability_history' && !choices(payload.filter_labels, payload.filter_idx, 'time_span_idx')) add(payload.filter_label || '95%', false, true);
    } else if (type === 'review_intervals'){
      const st = head.querySelector('.dd-stat');
      if (st){ const n = payload.median || 0; st.textContent = DD.tn('Median interval: {n} day', 'Median interval: {n} days', n); }
      if (!choices(payload.filter_labels, payload.filter_idx, 'time_span_idx')) add(payload.filter_label || '95%', false, true);
    }
    // its views, Bars | Pie: the one shown lit, a click on the other shows it (dd-pview: not an option turned on)
    if (PIE_TYPES[type] && head._ddPie){
      const views = [];
      const show = function(pie){
        if (pie !== head._ddPie.on()) head._ddPie.toggle();
        views[0].classList.toggle('on', !pie); views[1].classList.toggle('on', pie);
      };
      add('Bars', !head._ddPie.on(), false, function(){ show(false); }, 'The counts as bars'); views.push(pillsEl.lastChild);
      add('Pie', head._ddPie.on(), false, function(){ show(true); }, 'The bars as a pie, with the share of each part'); views.push(pillsEl.lastChild);
      views.forEach(function(v){ v.classList.add('dd-pview'); });
    }
    const items = [];
    // Card Difficulty / Retrievability: the bars split by card type (off by default)
    if ((type === 'difficulty' || type === 'retrievability') && payload.breakdown != null)
      items.push(['breakdown', 'Breakdown by Type', !!payload.breakdown, false]);
    if (payload.include_suspended != null){
      items.push(['include_suspended', 'Include Suspended Cards', payload.include_suspended !== false, true]);
      if (payload.include_zero != null) items.push(['include_zero', 'Show Cards Never Forgotten', !!payload.include_zero, false]);
    }
    // the pie's slices, while it is shown (Pie Range, Pie Slices)
    if (PIE_TYPES[type] && head._ddPie && head._ddPie.on()) items.push.apply(items, pieOptions(type, payload));
    if (items.length) DD.optionsPill(pillsEl, section, payload.include_suspended != null ? 'Which cards are counted' : "This chart's options", items);
    else if (head._ddOpt){ delete head._ddOpt; if (DD.ownOptions && head.closest('.dd-card')) DD.ownOptions(head); }
  }

  // The Time Machines (Interval / Stability / Difficulty): the day shown is picked in the header (its date pill opens a
  // calendar) or on a slider under the bars (right click: Day Slider), from the period's first day (the whole history
  // for Total) to today. Its data is asked again through ctx.fetch (the window's or the main screen's) and the bars
  // morph to it; the other charts don't move. The day picked stays while the period stays.
  const MACHINES = {interval_history: 1, stability_history: 1, difficulty_history: 1};
  const dayOrd = function(iso){ const p = String(iso).split('-').map(Number); return Math.round(Date.UTC(p[0], p[1] - 1, p[2]) / 864e5); };
  const dayIso = function(n){ return new Date(n * 864e5).toISOString().slice(0, 10); };
  const dayText = function(iso){ const p = String(iso).split('-').map(Number); return new Date(p[0], p[1] - 1, p[2]).toLocaleDateString(); };

  // a month's calendar under the date pill (weeks from Monday): the days out of [min, max] greyed, a click picks one
  function dayPicker(btn, cur, min, max, onPick){
    const open = document.querySelector('.dd-cal');
    document.querySelectorAll('.dd-menu').forEach(function(o){ o.remove(); });
    if (open && open._btn === btn) return;  // its pill clicked again: closed
    const lo = dayOrd(min), hi = dayOrd(max), on = dayOrd(cur);
    const box = document.createElement('div');
    box.className = 'dd-menu dd-cal'; box._btn = btn; box.setAttribute('data-nt', '');
    if (DD.menuStyle) DD.menuStyle(box);
    const d0 = new Date(on * 864e5);
    let y = d0.getUTCFullYear(), m = d0.getUTCMonth();
    const fmt = function(n, o){ return new Date(n * 864e5).toLocaleDateString(undefined, Object.assign({timeZone: 'UTC'}, o)); };
    const first = function(yy, mm){ return Math.round(Date.UTC(yy, mm, 1) / 864e5); };
    function draw(){
      const f = first(y, m), n = first(y, m + 1) - f, lead = (new Date(f * 864e5).getUTCDay() + 6) % 7;
      const nav = function(v, txt, ok){ return '<button data-v="' + v + '"' + (ok ? '' : ' disabled') + '>' + txt + '</button>'; };
      let h = '<div class="dd-cal-head">' + nav(-12, '«', first(y - 1, m + 1) - 1 >= lo) + nav(-1, '‹', f > lo) +
        '<span>' + fmt(f, {month: 'long', year: 'numeric'}) + '</span>' + nav(1, '›', f + n <= hi) + nav(12, '»', first(y + 1, m) <= hi) + '</div><div class="dd-cal-grid">';
      for (let i = 0; i < 7; i++) h += '<i>' + fmt(19723 + i, {weekday: 'narrow'}) + '</i>';  // 19723: a Monday
      for (let i = 0; i < lead; i++) h += '<b></b>';
      for (let i = 0; i < n; i++){
        const d = f + i;
        h += '<button data-d="' + d + '" class="' + (d === on ? 'on' : '') + (d === hi ? ' today' : '') + '"' + (d < lo || d > hi ? ' disabled' : '') + '>' + (i + 1) + '</button>';
      }
      box.innerHTML = h + '</div>';
    }
    draw();
    box.addEventListener('mousedown', function(e){ e.stopPropagation(); });
    box.addEventListener('click', function(e){
      e.stopPropagation();
      const b = e.target.closest('button'); if (!b || b.disabled) return;
      if (b.dataset.v){ const t = y * 12 + m + Number(b.dataset.v); y = Math.floor(t / 12); m = t - y * 12; draw(); return; }
      close(); onPick(dayIso(Number(b.dataset.d)));
    });
    document.body.appendChild(box);
    const r = btn.getBoundingClientRect(), W = box.offsetWidth, H = box.offsetHeight;
    box.style.left = Math.max(4, Math.min(r.left, window.innerWidth - W - 4)) + 'px';
    box.style.top = (r.bottom + 2 + H <= window.innerHeight - 4 ? r.bottom + 2 : Math.max(4, r.top - 2 - H)) + 'px';
    function out(e){ if (!box.isConnected || !box.contains(e.target)) close(); }
    function key(e){ if (e.key === 'Escape') close(); }
    function close(){ box.remove(); document.removeEventListener('click', out); document.removeEventListener('keydown', key); }
    setTimeout(function(){ if (box.isConnected){ document.addEventListener('click', out); document.addEventListener('keydown', key); } }, 0);
  }

  DD.dayPicker = dayPicker;  // (Card Counts' date pill, pie.js)

  // What a chart counts: an icon pill and
  // its menu of checks, each a setting read again by Python (DD.setWidgetSetting); lit when one is off its default.
  // items: [setting key, label, value now, default]
  const OPT_ICON = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M2 14h4M10 8h4M18 16h4"/></svg>';
  DD.optionsPill = function(pills, section, tip, items){
    // its on / off options (Breakdown by Type, Include Suspended Cards...): a pill each, lit when on, in the header
    // while it has room (dd-core watchStat moves the pills with no room, from the right, into its "..." menu); the
    // choices and actions stay in the options icon
    const toggles = items.filter(function(it){ return it[4] === undefined || it[4] === true; });
    toggles.forEach(function(it){
      const t = document.createElement('button');
      t.className = 'dd-pill dd-pill-tog' + (it[2] ? ' on' : '');
      t.textContent = DD.t(it[1]);
      let v = !!it[2];
      t.addEventListener('click', function(e){
        e.stopPropagation();
        v = !v;
        t.classList.toggle('on', v);
        DD.setWidgetSetting(section, it[0], v);
      });
      pills.appendChild(t);
    });
    items = items.filter(function(it){ return toggles.indexOf(it) < 0; });
    // the Deep Dive: one icon for the chart's options (app.js ownOpt), these entries first in it
    const head = pills.closest && pills.closest('.dd-head');
    if (head && DD.ownOptions && head.closest('.dd-card')){
      if (!items.length){ delete head._ddOpt; DD.ownOptions(head); return null; }
      const cur = {};
      items.forEach(function(it){ cur[it[0]] = it[2]; });
      head._ddOpt = {section: section, tip: tip, items: items, cur: cur};
      DD.ownOptions(head);
      return null;
    }
    if (!items.length) return null;
    const b = document.createElement('button');
    b.className = 'dd-pill dd-pill-opt dd-pill-ico' + (items.some(function(it){ return it[2] !== it[3]; }) ? ' on' : '');
    b.innerHTML = OPT_ICON;
    b.title = tip;
    const cur = {};
    items.forEach(function(it){ cur[it[0]] = it[2]; });
    b.addEventListener('click', function(e){
      e.stopPropagation();
      const r = b.getBoundingClientRect();
      const xo = {items: items, cur: cur};
      // (its windows, Edit Searches...: a pill of their own)
      DD.menu({x: r.left, y: r.bottom + 2}, DD.optItems(xo).filter(function(it, i){ return items[i][4] !== 'action'; }), function(k, on){
        const p = DD.optPick(xo, k, on);
        if (!p || p[1] === cur[p[0]]) return;
        k = p[0];
        const v = cur[k] = p[1];
        DD.setWidgetSetting(section, k, v);
      });
    });
    pills.appendChild(b);
    return b;
  };
  // the menu entries of a chart's options (head._ddOpt): a check each, or for a choice (it[4]: [[value, label], ...])
  // a submenu of its values, or for an action (it[4] 'action', it[5] its function: Edit Searches...) a plain entry;
  // DD.optPick reads a pick back: [key, value], or null (an action is run there)
  DD.optItems = function(xo){
    return xo.items.map(function(it){
      if (it[4] === 'action') return ['xo:' + it[0], it[1], undefined, it[6] || null];  // (it[6]: its icon)
      if (!Array.isArray(it[4])) return ['xo:' + it[0], it[1], xo.cur[it[0]], null, true];
      return ['xo:' + it[0], it[1], undefined, null, false,
        it[4].map(function(c){ return ['xo:' + it[0] + '=' + c[0], c[1], xo.cur[it[0]] === c[0], null, 'radio']; })];
    });
  };
  DD.optPick = function(xo, k, on){
    if (!xo || typeof k !== 'string' || k.indexOf('xo:') !== 0) return null;
    const s = k.slice(3), eq = s.indexOf('='), key = eq >= 0 ? s.slice(0, eq) : s;
    const it = xo.items.filter(function(x){ return x[0] === key; })[0];
    if (!it) return null;
    if (it[4] === 'action'){ if (eq < 0 && typeof it[5] === 'function') setTimeout(it[5], 0); return null; }
    if (!Array.isArray(it[4])) return eq >= 0 ? null : [key, on === undefined ? !xo.cur[key] : !!on];
    const c = eq >= 0 && it[4].filter(function(x){ return String(x[0]) === s.slice(eq + 1); })[0];
    return c ? [key, c[0]] : null;
  };

  function machineSlider(el, ctx, apply){
    if (!ctx.fetch) return null;
    el.classList.add('dd-tmb');
    const row = document.createElement('div');
    row.className = 'dd-tm';
    row.innerHTML = '<input type="range" min="0" max="1" step="1" value="0" title="Day shown">';
    el.appendChild(row);
    const inp = row.firstChild;
    // a drag on the slider is not a drag of the widget, nor a click on a bar
    ['pointerdown', 'mousedown', 'touchstart', 'click'].forEach(function(ev){ inp.addEventListener(ev, function(e){ e.stopPropagation(); }); });
    let last = null, base = null, picked = null, seq = 0, timer = 0, busy = false, next = null;
    // the part of the track before the thumb, filled
    function fill(){ const mx = Number(inp.max); inp.style.setProperty('--p', (mx > 0 ? 100 * Number(inp.value) / mx : 0) + '%'); }
    function sync(payload){
      last = payload || null;
      const f = last && last.first, t = last && last.today, d = last && last.date;
      if (!f || !t || !d || dayOrd(t) <= dayOrd(f)){ row.hidden = true; base = null; return; }
      row.hidden = last.day_slider === false;
      base = dayOrd(f);
      inp.max = String(dayOrd(t) - base);
      if (!busy && next === null) inp.value = String(Math.max(0, dayOrd(d) - base));
      fill();
    }
    // one request at a time; while it runs, only the last day asked waits
    function ask(at){
      if (busy){ next = at; return; }
      busy = true;
      const my = ++seq;
      ctx.fetch({at: at}).then(function(d){ if (my === seq && d && !d.error) apply(d); }).catch(function(){}).then(function(){
        busy = false;
        if (next !== null){ const n = next; next = null; ask(n); }
      });
    }
    inp.addEventListener('input', function(){
      if (base == null) return;
      fill();
      const at = picked = dayIso(base + Number(inp.value));
      clearTimeout(timer);
      timer = setTimeout(function(){ ask(at); }, 30);
    });
    sync(ctx.data);
    // the header's date pill (headFor): its calendar
    if (ctx.head) ctx.head._ddDay = function(btn){
      if (!last || !last.first || !last.today) return;
      dayPicker(btn, last.date || last.today, last.first, last.today, function(at){
        picked = at;
        if (base != null){ inp.value = String(dayOrd(at) - base); fill(); }
        ask(at);
      });
    };
    return {
      sync: sync,
      on: function(){ return !(last && last.day_slider === false); },
      // new data of a refresh (a setting changed, the main screen shown again): the day picked asked again instead,
      // one morph; another period (its first day moved) takes its own first day
      keep: function(data){
        if (!picked || !data || !data.first) return false;
        const curSpan = data.span_start || data.first, oldSpan = last && (last.span_start || last.first);
        if (!last || curSpan !== oldSpan || dayOrd(picked) > dayOrd(data.today)){ picked = null; return false; }
        if (data.date === picked) return false;
        ask(picked);
        return true;
      },
      destroy: function(){ clearTimeout(timer); seq++; if (ctx.head) delete ctx.head._ddDay; },
    };
  }

  // ---- Pie: the cards in slices of fixed ranges, in Card Counts' donut
  // (charts/pie.js DD.pieMount), its legend with each slice's count and share. The ranges: the chart's own (PIE_UNITS
  // edges: 1 day, 2-6 days, 1-3 weeks ...: the same from a deck or a day to another), or from its options while the pie
  // is shown (Pie Range: the last value; Pie Slices: the steps): from the smallest value to that
  // range, each slice wider than the one before, at the unit's round values, all the values above in a last one ----
  const PIE_TYPES = {lapse_distribution: 1, review_distribution: 1, learning_steps: 1, time_distribution: 1, interval_load: 1,
    review_intervals: 1, interval_history: 1, stability: 1, stability_history: 1};
  const PIE_UP = {review_intervals: 1, interval_history: 1, interval_load: 1, stability: 1, stability_history: 1};  // longer is better: red to green
  const PIE_UNIT = {review_intervals: 'days', interval_history: 'days', interval_load: 'days', lapse_distribution: 'lapses',
    review_distribution: 'reviews', learning_steps: 'steps', time_distribution: 'secs',
    // stability: days, from 0 (a stability under a day)
    stability: 'sdays', stability_history: 'sdays'};
  const COUNT_ROUND = [2, 3, 4, 5, 6, 8, 10, 15, 20, 25, 30, 40, 50, 75, 100, 150, 200, 300, 500, 1000];
  // min: the smallest value counted; edges: where each slice after the first starts; limits: Pie Range's choices;
  // round: the values a slice may start at with them
  const PIE_UNITS = {
    days: {min: 1, edges: [2, 7, 21, 91, 182, 365, 730], limits: [30, 91, 182, 365, 730, 1825, 3650],
      round: [2, 3, 4, 5, 6, 7, 14, 21, 30, 60, 91, 182, 273, 365, 730, 1095, 1825, 3650]},
    lapses: {min: 1, edges: [2, 3, 5, 8], limits: [3, 5, 8, 10, 15, 20, 30], round: COUNT_ROUND},
    reviews: {min: 1, edges: [3, 6, 11, 21, 51], limits: [5, 10, 20, 50, 100, 200], round: COUNT_ROUND},
    steps: {min: 1, edges: [2, 3, 4, 6], limits: [3, 5, 10, 20, 50], round: COUNT_ROUND},
    secs: {min: 0, edges: [10, 30, 60, 120, 300, 600], limits: [30, 60, 120, 300, 600, 1800, 3600],
      round: [5, 10, 15, 20, 30, 45, 60, 90, 120, 180, 300, 600, 900, 1200, 1800, 3600]},
  };
  PIE_UNITS.sdays = Object.assign({}, PIE_UNITS.days, {min: 0});
  const PIE_COUNTS = [3, 4, 5, 6, 8, 10, 12];
  function pieEdges(type, payload){
    const u = PIE_UNITS[PIE_UNIT[type]], lim = Number(payload.pie_limit) || 0, n = Number(payload.pie_slices) || 0;
    if (!lim && !n) return u.edges;
    const L = lim || u.edges[u.edges.length - 1], P = Math.max(2, n || u.edges.length + 1), a = Math.max(1, u.min);
    const out = [];
    for (let i = 1; i < P - 1; i++){
      // spaced evenly on a log scale, at the nearest round value above the slice before
      const t = a * Math.pow(L / a, i / (P - 1)), prev = out.length ? out[out.length - 1] : u.min;
      let best = null;
      u.round.forEach(function(v){ if (v > prev && v < L && (best === null || Math.abs(Math.log(v / t)) < Math.abs(Math.log(best / t)))) best = v; });
      if (best !== null) out.push(best);
    }
    out.push(L);
    return out;
  }
  // a number of days / seconds in its round unit: [value, text], or null (seconds not round: dur)
  function dayUnit(n){
    if (n >= 365 && n % 365 === 0) return [n / 365, '{value} yr'];
    const mo = n / 30.4;
    if (n >= 28 && Math.abs(mo - Math.round(mo)) < 0.1) return [Math.round(mo), '{value} mo'];
    if (n >= 7 && n % 7 === 0) return [n / 7, '{value} wk'];
    return [n, '{value} d'];
  }
  function secUnit(s){
    if (s >= 3600 && s % 3600 === 0) return [s / 3600, '{value}h'];
    if (s >= 60 && s % 60 === 0) return [s / 60, '{value}m'];
    return s < 60 ? [s, '{value}s'] : null;
  }
  // a unit's text (weeks, months, years: the plural form of the larger number)
  const PLURAL_UNIT = {'{value} wk': 1, '{value} mo': 1, '{value} yr': 1};
  function unitText(p, value){ return PLURAL_UNIT[p[1]] ? DD.tn(p[1], p[1], p[0], {value: value}) : DD.t(p[1], {value: value}); }
  function pieValue(type, n){
    const unit = PIE_UNIT[type] === 'sdays' ? 'days' : PIE_UNIT[type];
    if (unit === 'days' || unit === 'secs'){
      const p = (unit === 'days' ? dayUnit : secUnit)(n);
      return p ? unitText(p, p[0]) : dur(n);
    }
    const nm = CARD_HISTORY[type];
    return DD.tn('{n} ' + nm[0], '{n} ' + nm[1], n, {n: n});
  }
  // a slice's name: [lo, hi) (hi null: lo and more)
  function pieLabel(type, lo, hi){
    const unit = PIE_UNIT[type] === 'sdays' ? 'days' : PIE_UNIT[type];
    if (unit === 'days' || unit === 'secs'){
      const f = unit === 'days' ? dayUnit : secUnit;
      if (hi === null) return pieValue(type, lo) + '+';
      if (unit === 'days' && hi - 1 < 7) return DD.t('{value} d', {value: hi - 1 === lo ? lo : lo + '\u2013' + (hi - 1)});
      if (unit === 'secs' && lo === 0) return '< ' + pieValue(type, hi);
      const a = f(lo), b = f(hi);
      if (a && b && a[1] === b[1]) return unitText(b, a[0] + '\u2013' + b[0]);
      return pieValue(type, lo) + ' \u2013 ' + pieValue(type, hi);
    }
    const nm = CARD_HISTORY[type];
    if (hi === null) return DD.tn('{n} ' + nm[0], '{n} ' + nm[1], Math.max(2, lo), {n: lo + '+'});
    const top = hi - 1;
    return DD.tn('{n} ' + nm[0], '{n} ' + nm[1], top, {n: top === lo ? lo : lo + '\u2013' + top});
  }
  // its options while the pie is shown (the chart's options icon: DD.optionsPill, a choice each)
  function pieOptions(type, payload){
    const u = PIE_UNITS[PIE_UNIT[type]];
    const lim = [[0, 'Automatic']].concat(u.limits.map(function(v){ return [v, pieValue(type, v)]; }));
    const cnt = [[0, 'Automatic']].concat(PIE_COUNTS.map(function(v){ return [v, String(v)]; }));
    return [['pie_limit', 'Pie Range', Number(payload.pie_limit) || 0, 0, lim],
      ['pie_slices', 'Pie Slices', Number(payload.pie_slices) || 0, 0, cnt]];
  }
  function piePayload(type, m, payload, C){
    const u = PIE_UNITS[PIE_UNIT[type]], edges = pieEdges(type, payload);
    const dist = (PIE_UNIT[type] === 'sdays' ? payload.data : payload.data && payload.data.distribution) || {};
    const sums = edges.map(function(){ return 0; }).concat([0]);
    Object.keys(dist).forEach(function(k){
      const x = Number(k), v = Math.max(0, Number(dist[k]) || 0);
      if (!(x >= u.min) || !v) return;
      let i = 0;
      while (i < edges.length && x >= edges[i]) i++;
      sums[i] += v;
    });
    // [lo, hi (excluded; null: no end), amount]; Lapses per Card's bar at 0 first (Show Cards Never Forgotten)
    const groups = [];
    if (payload.zero_bar) groups.push([0, 1, Math.max(0, Number(payload.zero_bar) || 0)]);
    sums.forEach(function(s, i){ groups.push([i ? edges[i - 1] : u.min, i < edges.length ? edges[i] : null, s]); });
    const ms = payload.measure || 'count';
    const low = (C && C.gradient_low) || '#ff3b30', high = (C && C.gradient_high) || '#4cd964';
    const order = [], labels = {}, colors = {}, counts = {}, byKey = {};
    groups.forEach(function(g, i){
      // (each slice its colour from its place among all, its key from its range: the same from a deck to another; a
      // slice hidden from the legend stays hidden while its range stays)
      if (!(g[2] > 0)) return;
      const k = 'r' + g[0] + '_' + (g[1] === null ? 'x' : g[1]), t = groups.length > 1 ? i / (groups.length - 1) : 0;
      byKey[k] = g;
      order.push(k);
      labels[k] = pieLabel(type, g[0], g[1]);
      colors[k] = PIE_UP[type] ? lerpColor(low, high, t) : lerpColor(high, low, t);
      counts[k] = g[2];
    });
    const load = type === 'interval_load' || ms === 'load';
    return {counts: counts, order: order, labels: labels, colors: colors, legend_pct: true, show_legend: true,
      // a click on a row of the legend hides that slice (pie.js toggleKind), kept in the chart's setting pie_hidden
      hidden_kinds: (payload.pie_hidden || []).filter(function(k){ return byKey[k]; }),
      hide_save: {section: payload.kind || type, key: 'pie_hidden', done: function(hid){ payload.pie_hidden = hid; }},
      center_word: load ? DD.t('rev/day') : (ms === 'total' ? DD.t(type === 'review_distribution' ? 'reviews' : (type === 'lapse_distribution' ? 'lapses' : 'total')) : DD.t('cards')),
      fmt: load ? function(v){ return U.trimNum(v, v < 10 ? 1 : 0); } : (type === 'time_distribution' && ms === 'total' ? dur : null),
      // a click on a slice: its cards in the browser (as a click on its bars)
      browse: function(k){
        const g = byKey[k];
        if (!g) return null;
        const range = function(f){ return 'prop:' + f + '>=' + g[0] + (g[1] === null ? '' : ' prop:' + f + '<' + g[1]); };
        if (type === 'review_intervals' || type === 'interval_load') return {query: range('ivl')};
        if (type === 'stability') return {query: range('s')};
        if (type === 'lapse_distribution' || type === 'review_distribution') return {query: '-is:new ' + range(type === 'lapse_distribution' ? 'lapses' : 'reps')};
        return null;
      }};
  }

  // the charts that zoom on their days: Future Due, and the histograms of days (Review Intervals, Interval Load, Stability:
  // their days from 1 to years, most cards in the first weeks, crushed in the first bars of the whole view)
  const ZOOMS = {future_due: 1, review_intervals: 1, interval_load: 1, stability: 1};
  // The zoom of Future Due (inst.zoom, as Retention's: app.js / pinned.js add its reset arrow): in days, its index i the
  // whole view's day fullMin + i. Its labels ("12 d") are no dates: the zoom links of the charts of dates leave it alone.
  function zoomable(plot, chart, state){
    const tip = plot.querySelector('.dd-tip'), cv = chart.canvas;
    let drag = null;
    const full = function(){ return [chart.m.fullMin, chart.m.fullMin + chart.m.fullN]; };
    // the bar under x: its days [a, b)
    const binAt = function(mx){
      const g = chart.geo, m = chart.m; if (!g || !m.count) return full();
      const f = Math.max(0, Math.min(0.999999, (mx - g.ml) / Math.max(1, g.plotW)));
      return m.ranges[Math.trunc(f * m.count)];
    };
    const api = {
      count: function(){ return chart.m.fullN || 0; },
      label: function(i){ return (chart.m.fullMin + i) + ' d'; },
      get: function(){ const z = chart.zoomDays; return z ? [z[0] - chart.m.fullMin, z[1] - chart.m.fullMin] : null; },
      set: function(a, b){ to(a == null ? null : chart.m.fullMin + a, a == null ? null : chart.m.fullMin + b); },
      // the zoom bar slides by whole bins (those of the zoom's span, as snapZoom)
      step: function(span){ return chart.options.adaptive_binning !== false ? binSize(Math.max(1, span) - 1, (DD.settings && DD.settings.bin_scale) || 100) : 1; },
      onChange: null, onOutLimit: null,
      canvas: cv,
    };
    function to(a, b){ chart.setZoom(a, b); state.last = true; DD.frame.kick(); if (api.bar) api.bar(); }
    function emit(){ if (api.onChange) api.onChange(api.get()); }
    // the wheel moves the view at once
    function now(a, b){ const prev = DD._noAnim; DD._noAnim = true; try { to(a, b); emit(); } finally { DD._noAnim = prev; } }
    const xOf = function(e){ return e.clientX - cv.getBoundingClientRect().left; };
    function down(e){
      if (e.button !== 0 || chart.m.emptyDeck) return;
      const x = xOf(e), g = chart.geo;
      if (!g || x < g.ml || x > g.ml + g.plotW) return;
      drag = {x0: x}; chart.sel = [x, x]; if (tip) tip.style.display = 'none'; chart.hover = -1;
    }
    function move(e){
      if (!drag) return;
      const g = chart.geo;
      chart.sel = [drag.x0, Math.max(g.ml, Math.min(g.ml + g.plotW, xOf(e)))];
      state.last = true; DD.frame.kick();
    }
    function up(){
      if (!drag) return;
      const sel = chart.sel; drag = null; chart.sel = null; state.last = true; DD.frame.kick();
      if (!sel || Math.abs(sel[1] - sel[0]) < 6) return;
      if (!chart.cam && !chart.morph && chart.progress >= 1) chart.draw();  // the zoom's first picture without the zone
      const a = binAt(Math.min(sel[0], sel[1]))[0], b = binAt(Math.max(sel[0], sel[1]))[1];
      if (b - a >= 2){ to(a, b); emit(); }
    }
    function wheel(e){
      const n = api.count(); if (!n || chart.m.emptyDeck) return;
      const cur = api.get() || [0, n], span = cur[1] - cur[0];
      if (e.shiftKey && api.get()){
        e.preventDefault(); e.stopPropagation();
        const st = Math.max(1, Math.round(span * 0.1)) * (e.deltaY < 0 ? -1 : 1);
        let a = cur[0] + st; a = Math.max(0, Math.min(n - span, a));
        if (a !== cur[0]) now(chart.m.fullMin + a, chart.m.fullMin + a + span);
        return;
      }
      if (!(e.ctrlKey || e.metaKey)) return;
      e.preventDefault(); e.stopPropagation();
      if (e.deltaY > 0 && span >= n){ if (api.onOutLimit) api.onOutLimit(); return; }  // zoom_out_limit
      const r = binAt(xOf(e)), c = (r[0] + r[1]) / 2 - chart.m.fullMin;
      const ns = e.deltaY < 0 ? Math.max(3, Math.round(span * 0.85)) : Math.min(n, Math.max(span + 1, Math.round(span / 0.85)));
      if (ns === span) return;
      const ratio = span > 0 ? (c - cur[0]) / span : 0.5;
      let a = Math.round(c - ratio * ns), b = a + ns;
      if (a < 0){ a = 0; b = ns; } if (b > n){ b = n; a = Math.max(0, n - ns); }
      now(chart.m.fullMin + a, chart.m.fullMin + b);
    }
    cv.addEventListener('mousedown', down);
    window.addEventListener('mousemove', move);
    window.addEventListener('mouseup', up);
    cv.addEventListener('wheel', wheel, {passive: false});
    api.off = function(){ window.removeEventListener('mousemove', move); window.removeEventListener('mouseup', up); };
    return api;
  }

  function register(type){
    DD.registerChart(type, {
      mount: function(el, ctx){
        el.innerHTML = '<div class="dd-plot"><canvas></canvas><div class="dd-tip"></div></div>';
        const plot = el.firstChild;
        // browser_click: the cards of the hovered bar (due day, interval, stability, difficulty / retrievability)
        plot._ddBrowse = function(){
          const i = chart.hover, m = chart.m; if (i == null || i < 0 || !m || i >= m.count) return null;
          if (type === 'future_due' && m.ranges) return {query: 'prop:due>=' + m.ranges[i][0] + ' prop:due<' + m.ranges[i][1]};
          if ((type === 'review_intervals' || type === 'interval_load') && m.ranges) return {query: 'prop:ivl>=' + m.ranges[i][0] + ' prop:ivl<' + m.ranges[i][1]};
          // Lapses / Reviews per Card: the cards (not new) with that many lapses / reviews (card_history: cards.lapses, reps)
          if ((type === 'lapse_distribution' || type === 'review_distribution') && m.ranges){
            const f = type === 'lapse_distribution' ? 'lapses' : 'reps';
            return {query: '-is:new prop:' + f + '>=' + m.ranges[i][0] + ' prop:' + f + '<' + m.ranges[i][1]};
          }
          // (its bin's days; the whole view's first bin from 0, as its tooltip)
          if (type === 'stability' && m.ranges){ const r = m.ranges[i], k = (!m.win && r[0] === 1 && r[1] - r[0] > 1) ? 0 : r[0]; return {query: 'prop:s>=' + k + ' prop:s<' + r[1]}; }
          if (type === 'difficulty' || type === 'retrievability'){
            const p = type === 'difficulty' ? 'd' : 'r', f = function(x){ return String(Math.round(x * 1000) / 1000); };
            return {query: 'prop:' + p + '>=' + f(i / 100) + ' prop:' + p + '<' + f((i + 1) / 100)};
          }
          return null;
        };
        const chart = new Chart(plot, type, ctx.data, DD.theme.chart, ctx.options || {});
        // Pie (the header's pill): the donut in place of the bars, made from the bars of the moment
        let pieEl = null, pieInst = null, pieMeasure = null;
        const pieShow = function(){
          const on = !!(PIE_TYPES[type] && chart.options.pie_view);
          plot.style.display = on ? 'none' : '';
          if (!on){ if (pieEl) pieEl.style.display = 'none'; return; }
          const p = piePayload(type, chart.m, chart.payload, DD.theme.chart);
          if (!pieEl){ pieEl = document.createElement('div'); pieEl.className = 'dd-plot'; plot.insertAdjacentElement('afterend', pieEl); }
          pieEl.style.display = '';
          // another measure (Cards / Total Time ...): its slices are other ranges, the ring comes in again (a morph
          // turned one range into another)
          const pl = chart.payload || {}, ms = (pl.measure || 'count') + '|' + (pl.pie_limit || 0) + '|' + (pl.pie_slices || 0);
          const fresh = pieMeasure !== null && ms !== pieMeasure;
          pieMeasure = ms;
          if (!pieInst && DD.pieMount) pieInst = DD.pieMount(pieEl, {data: p, animate: ctx.animate, options: ctx.options || {}});
          else if (pieInst) pieInst.update(p, fresh ? 'fresh' : undefined);
        };
        if (ctx.head && PIE_TYPES[type]) ctx.head._ddPie = {
          on: function(){ return !!chart.options.pie_view; },
          toggle: function(){
            const on = !chart.options.pie_view;
            chart.options.pie_view = on;
            pieShow();
            headFor(type, chart.payload, ctx.head, chart.m);  // (the pie's options, in its view only)
            if (!on){ chart._resize(); state.last = true; DD.frame.kick(); }
            DD.call('set_setting', {section: type, key: 'pie_view', value: on}).catch(function(){});
          }};
        headFor(type, ctx.data, ctx.head, chart.m);
        if (!ctx.animate) chart.progress = 1;
        const state = {start: null, last: true};
        chart.hoverIdx = -1;
        Object.defineProperty(chart, 'hoverIdx', {get: function(){ return chart.hover; }, set: function(v){ chart.hover = v; }});
        DD.hover.attach(plot, chart, {
          index: function(mx, my){ return (chart.sel || chart.cam) ? -1 : chart.indexAt(mx, my); },
          rows: function(i){ return chart.tipRows(i); },
          redraw: function(){ state.last = true; DD.frame.kick(); },
        });
        function frame(now){
          // its intro not played yet (it waited out of view) and new data came meanwhile: the intro alone shows it
          // (the change's morph ran with it, a second animation over the first)
          if (chart.progress < 1 && state.start === null && (chart.morph)){ if (DD.dev) DD.trace('ANIMTRACE discrete intro not played yet: its morph dropped, the intro shows the new data'); chart.morph = null; }
          if (chart.progress < 1){
            if (state.start === null) state.start = now;
            chart.progress = Math.min(1, (now - state.start) / DD.intro(500));
          }
          if (chart.cam){
            if (chart.progress >= 1 && !chart.morph && chart.camFrame(now)){ state.last = true; return true; }
            chart.cam = null;
          }
          const needs = chart.progress < 1 || !!chart.morph;
          if (needs || state.last) chart.draw();
          state.last = needs;
          return needs;
        }
        const resizer = new ResizeObserver(function(){ DD.frame.resized(frame, function(){ chart._resize(); state.last = true; }); });
        DD.frame.observe(resizer, plot);
        if (!ctx.animate) chart.draw();
        DD.frame.add(frame);
        const tm = MACHINES[type] ? machineSlider(el, ctx, function(d){ chart.setPayload(d); headFor(type, d, ctx.head, chart.m); tm.sync(d); pieShow(); state.last = true; DD.frame.kick(); }) : null;
        pieShow();
        // Future Due and the histograms of days zoom on their days, as Retention: drag a zone, Ctrl+wheel to zoom,
        // Shift+wheel to slide; a zoom of their own, never linked to the charts of dates
        const zm = ZOOMS[type] ? zoomable(plot, chart, state) : null;
        // the zoom left by new data (a shorter range, the backlog off): its arrow and its bar follow
        const zoomKept = function(prev){ if (!zm) return; const now = zm.get(); if (zm.bar) zm.bar(); if (String(prev) !== String(now) && zm.onChange) zm.onChange(now); };
        const inst = {
          machine: tm,
          update: function(data, hint){ if (tm && tm.keep(data)) return; const zp = zm && zm.get(); chart.setPayload(data, hint); headFor(type, data, ctx.head, chart.m); if (tm) tm.sync(data); pieShow(); state.last = true; DD.frame.kick(); zoomKept(zp); },
          setOptions: function(o){ const zp = zm && zm.get(); chart.setOptions(o); pieShow(); state.last = true; DD.frame.kick(); zoomKept(zp); },
          setTheme: function(){ chart.colors = DD.theme.chart; state.last = true; DD.frame.kick(); },
          destroy: function(){ if (zm) zm.off(); if (pieInst) pieInst.destroy(); if (ctx.head) delete ctx.head._ddPie; if (tm) tm.destroy(); el.classList.remove('dd-tmb'); DD.frame.remove(frame); resizer.disconnect(); el.innerHTML = ''; if (ctx.head){ const p = ctx.head.querySelector('.dd-pills'); if (p) p.innerHTML = ''; } },
        };
        if (zm){ inst.zoom = zm; if (DD.zoomBar) DD.zoomBar(plot, zm); }
        return inst;
      },
    });
  }
  register('future_due');
  register('review_intervals');
  register('stability');
  register('difficulty');
  register('retrievability');
  register('interval_load');
  register('lapse_distribution');
  register('review_distribution');
  register('learning_steps');
  register('time_distribution');
  register('interval_history');
  register('stability_history');
  register('difficulty_history');
})();
