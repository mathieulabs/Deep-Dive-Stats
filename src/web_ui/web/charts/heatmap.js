// Heatmap: one cell per day, colored by the reviews of the day (continuous, year and 365 views).
(function(){
  'use strict';
  const DD = window.DD;
  const U = DD.cu;
  const FONT_FAMILY = '"Segoe UI",-apple-system,BlinkMacSystemFont,sans-serif';
  const MS_DAY = 86400000;
  const BOX_COLS = 48, MAX_GROW = 6.0, HALF = 27;  // HALF: the weeks of a split year's older half
  const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
  const TYPE_FIELDS = {new: 'learn_count', young: 'young_count', mature: 'mature_count', relearn: 'relearn_count', cram: 'cram_count'};
  const METRIC_KEYS = ['reviews', 'time', 'correct', 'failed', 'retention', 'avg_time'];
  const TYPE_KEYS = ['new', 'young', 'mature', 'relearn', 'cram'];

  // Python round(): halves go to the even number
  function pyRound(x){ const f = Math.floor(x), d = x - f; if (d < 0.5) return f; if (d > 0.5) return f + 1; return f % 2 === 0 ? f : f + 1; }
  function pad(n){ return n < 10 ? '0' + n : '' + n; }
  function iso(d){ return d.getUTCFullYear() + '-' + pad(d.getUTCMonth() + 1) + '-' + pad(d.getUTCDate()); }
  function utc(y, m, d){ return new Date(Date.UTC(y, m, d)); }
  function addDays(d, n){ return new Date(d.getTime() + n * MS_DAY); }
  function parseIso(s){ const p = s.split('-'); return utc(+p[0], +p[1] - 1, +p[2]); }

  // ---- color helpers (hue 0-359, HSV saturation, HSL lightness 0-255) -----------------
  function rgbOf(c){ const o = U.parseColor(c); return [Math.round(o.r), Math.round(o.g), Math.round(o.b)]; }
  function hueOf(r, g, b){
    const mx = Math.max(r, g, b), mn = Math.min(r, g, b), d = mx - mn;
    if (!d) return -1;
    let h;
    if (mx === r) h = (((g - b) / d) % 6 + 6) % 6; else if (mx === g) h = (b - r) / d + 2; else h = (r - g) / d + 4;
    return Math.round(h * 60) % 360;
  }
  function hsvSat(r, g, b){ const mx = Math.max(r, g, b), mn = Math.min(r, g, b); return mx ? Math.round((mx - mn) / mx * 255) : 0; }
  function lightnessOf(r, g, b){ return Math.round((Math.max(r, g, b) + Math.min(r, g, b)) / 2); }
  function fromHsl(h, s, l){
    if (h < 0) h = 0;
    s = s / 255; l = l / 255;
    const c = (1 - Math.abs(2 * l - 1)) * s, x = c * (1 - Math.abs((h / 60) % 2 - 1)), m = l - c / 2;
    const sec = Math.floor(h / 60) % 6;
    const t = [[c, x, 0], [x, c, 0], [0, c, x], [0, x, c], [x, 0, c], [c, 0, x]][sec];
    return [Math.round((t[0] + m) * 255), Math.round((t[1] + m) * 255), Math.round((t[2] + m) * 255)];
  }
  function rgbaStr(c, a){ return 'rgba(' + c[0] + ',' + c[1] + ',' + c[2] + ',' + (a / 255).toFixed(4) + ')'; }

  // ---- metrics ----------------------------------------------------------------------------
  function metricParts(m){
    const parts = String(m || '').split('+');
    return parts.every(function(p){ return METRIC_KEYS.indexOf(p) >= 0 || TYPE_KEYS.indexOf(p) >= 0; }) ? parts : [];
  }
  function components(m){
    const parts = metricParts(m); const ps = parts.length ? parts : ['reviews'];
    const comps = ps.filter(function(p){ return METRIC_KEYS.indexOf(p) >= 0; }).map(function(p){ return [p, null]; });
    const types = ps.filter(function(p){ return TYPE_KEYS.indexOf(p) >= 0; });
    if (types.length) comps.push(['types', types]);
    return comps;
  }
  function compValue(comp, e){
    const key = comp[0], reviews = +(e.reviews || 0), passed = +(e.passed || 0), tm = +(e.time_ms || 0);
    if (key === 'types') return comp[1].reduce(function(a, t){ return a + (+(e[TYPE_FIELDS[t]] || 0)); }, 0);
    if (key === 'time') return tm;
    if (key === 'correct') return passed;
    if (key === 'failed') return Math.max(0, reviews - passed);
    if (key === 'retention') return reviews > 0 ? passed / reviews * 100 : 0;
    if (key === 'avg_time') return reviews > 0 ? tm / reviews : 0;
    return reviews;
  }
  function metricValue(metric, e, scales){
    if (!e || typeof e !== 'object') return +(e || 0);
    const comps = components(metric);
    if (comps.length === 1) return compValue(comps[0], e);
    let tot = 0;
    comps.forEach(function(c, i){ const sc = scales && scales[i] ? scales[i] : 1; tot += compValue(c, e) / sc; });
    return tot / comps.length * 100;
  }
  function computeScales(metric, entries){
    const comps = components(metric);
    if (comps.length < 2) return [];
    return comps.map(function(c){
      const vals = entries.map(function(e){ return compValue(c, e); }).filter(function(v){ return v > 0; }).sort(function(a, b){ return a - b; });
      if (!vals.length) return 1;
      return vals.length >= 20 ? vals[Math.min(vals.length - 1, Math.floor(vals.length * 0.95))] : vals[vals.length - 1];
    });
  }

  class Chart {
    constructor(root, payload, colors, options){
      this.canvas = root.querySelector('canvas');
      this.ctx = this.canvas.getContext('2d');
      this.colors = colors;
      this.o = Object.assign({color: '#3b82f6', monday_first: false, empty_opacity: 15, filled_opacity: 100, empty_white: false,
        hide_labels: false, tinted_future: false, show_future: true, scale: 1, color_levels: 15, vibrance: 100, rounding: 20,
        intensity_curve: 100, multi_hue: false, palette: '', palette_colors: null, metric: 'reviews', show_legend: true, invert: false, mode: 'year', today: null,
        cont_month_offset: 0, rollover_hour: 0}, options || {});
      this.progress = 1;
      this._yearOff = 0; this._endOff = 0; this.hover = null;
      this.setPayload(payload);
      this._resize();
    }
    setPayload(p){ this.data = (p && p.data) || {}; }
    // The heatmap goes to the days the other charts show: the year
    // holding most of a zoom, the 365 days ending on its last day, the months around it; a new period: its last day.
    // Only when that place changes (a year browsed with the arrows stays otherwise). Returns the move's direction.
    anchorTo(a){
      if (!a || !a.last) return 0;
      const mode = this.o.mode, key = mode + '|' + (a.first || '') + '|' + a.last;
      if (this._anchorKey === key) return 0;
      this._anchorKey = key;
      const today = this.logicalToday(), last = parseIso(a.last), first = a.first ? parseIso(a.first) : null;
      if (mode === 'year'){
        let day = last;
        if (!a.full && first && first.getUTCFullYear() < last.getUTCFullYear()){  // zoom_year_anchor
          let best = last.getUTCFullYear(), bestDays = -1;
          for (let y = first.getUTCFullYear(); y <= last.getUTCFullYear(); y++){
            const lo = first > utc(y, 0, 1) ? first : utc(y, 0, 1), hi = last < utc(y, 11, 31) ? last : utc(y, 11, 31);
            const days = Math.round((hi - lo) / MS_DAY) + 1;
            if (days >= bestDays){ best = y; bestDays = days; }
          }
          day = utc(best, 11, 31);
        }
        const off = Math.min(0, day.getUTCFullYear() - this.today().getUTCFullYear()), dir = Math.sign(off - this._yearOff);
        this._yearOff = off; return dir;
      }
      if (mode === '365'){
        const before = 365 * this._endOff + (this._endShift | 0), shift = Math.min(0, Math.round((last - today) / MS_DAY));
        this._endOff = 0; this._endShift = shift; return Math.sign(shift - before);
      }
      if (mode === 'continuous'){  // continuous_offset_for_zoom
        const cur = this.o.cont_month_offset | 0;
        let off = cur;
        if (last >= today) off = 0;
        else {
          const center = today.getUTCFullYear() * 12 + today.getUTCMonth(), endM = last.getUTCFullYear() * 12 + last.getUTCMonth();
          const f = a.full ? null : first, startM = f ? f.getUTCFullYear() * 12 + f.getUTCMonth() : endM;
          const R = this.contR(), lo = center + cur - R, hi = center + cur + R;
          off = (lo <= startM && endM <= hi) ? cur : endM - R - center;
        }
        this.o.cont_month_offset = off; return Math.sign(off - cur);
      }
      return 0;
    }
    _resize(){
      const cw0 = this.canvas.width, ch0 = this.canvas.height, w0 = this.w, h0 = this.h;
      const f = DD.fitCanvas(this.canvas, this.ctx), w = f.w, h = f.h;
      if (this.canvas.width === cw0 && this.canvas.height === ch0 && w0 === w && h0 === h) return false;  // a new size clears the canvas
      this.w = w; this.h = h;
    }
    // while a pinned card glides to a new height, the grid is placed for the final one. In a switch whose cells glide
    // too (a mode transition), the legend stays above the card's current edge; in any other glide (the first height
    // asked for at startup, other data) the cells are already in place, so the legend stays under them and the
    // card's edge uncovers it (held to the edge, it was drawn over the grid while the card grew)
    lh(){ return this._layoutH != null ? this._layoutH : this.h; }
    vh(){ return this._visH != null && this._legendRides ? Math.min(this._visH, this.h) : this.h; }
    today(){ return this.o.today ? parseIso(this.o.today) : (function(){ const n = new Date(); return utc(n.getFullYear(), n.getMonth(), n.getDate()); })(); }
    logicalToday(){ return this.o.logical_today ? parseIso(this.o.logical_today) : this.today(); }
    dark(){ return !!this.colors.is_dark; }
    // ---- levels
    levels(){
      const o = this.o, dark = this.dark();
      const maxA = Math.trunc(o.filled_opacity * 2.55);
      const base = rgbOf(o.color);
      const h = hueOf(base[0], base[1], base[2]);
      let s = hsvSat(base[0], base[1], base[2]);
      s = Math.max(0, Math.min(255, Math.trunc(s * (o.vibrance / 100))));
      const l = lightnessOf(base[0], base[1], base[2]);
      const L = function(p){ return Math.max(0, Math.min(255, pyRound(p / 100 * 255))); };
      const n = Math.max(2, o.color_levels | 0), levels = [], fut = [];
      function lerpHue(h0, h1, t){
        if (h0 < 0 && h1 < 0) return 0; if (h0 < 0) return Math.trunc(h1); if (h1 < 0) return Math.trunc(h0);
        const d = (((h1 - h0 + 180) % 360) + 360) % 360 - 180;
        return ((Math.trunc(h0 + d * t) % 360) + 360) % 360;
      }
      // a palette (heatmap/palettes.py): its colors spread over the levels; a gradient of the user's, its colors as they are
      // the presets' colors (heatmap/palettes.PRESET_COLORS, sent with the options), the least to the most in a light
      // theme; a dark theme goes the other way (as in the Review Heatmap add-on), apart from the rainbow
      const FIXED = o.preset_colors || {}, NO_FLIP = {};
      (o.preset_noflip || []).forEach(function(k){ NO_FLIP[k] = true; });
      function along(stops, t){
        const x = t * (stops.length - 1), i = Math.min(stops.length - 2, Math.floor(x));
        return [i, x - i];
      }
      let cust = String(o.palette || '').indexOf('custom') === 0 && Array.isArray(o.palette_colors) && o.palette_colors.length >= 2
        ? o.palette_colors.map(rgbOf) : null;
      if (FIXED[o.palette]){ cust = FIXED[o.palette].map(rgbOf); if (dark && !NO_FLIP[o.palette]) cust.reverse(); }
      if (cust){
        for (let i = 0; i < n; i++){
          const p = along(cust, i / (n - 1)), a = cust[p[0]], b = cust[p[0] + 1];
          levels.push([0, 1, 2].map(function(j){ return Math.round(a[j] + (b[j] - a[j]) * p[1]); }));
        }
      } else if (o.multi_hue){
        const sh = h >= 0 ? (((h - 34) % 360) + 360) % 360 : 0, eh = h >= 0 ? (h + 8) % 360 : 0;
        let sl, el;
        if (dark){ sl = L(56); el = Math.max(L(74), l); } else { sl = L(86); el = Math.max(L(62), Math.min(l, L(78))); }
        const ss = Math.max(70, Math.trunc(s * 0.7)), es = Math.min(255, Math.max(120, Math.trunc(s * 1.05)));
        for (let i = 0; i < n; i++){
          const t = i / (n - 1);
          levels.push(fromHsl(lerpHue(sh, eh, t), Math.trunc(ss + (es - ss) * t), Math.trunc(sl + (el - sl) * t)));
        }
      } else {
        let sl, el;
        if (dark){ sl = L(46); el = Math.max(l, L(70)); } else { sl = L(84); el = Math.min(l, L(52)); }
        for (let i = 0; i < n; i++){ const t = i / (n - 1); levels.push(fromHsl(h, s, Math.trunc(sl + t * (el - sl)))); }
      }
      if (o.invert) levels.reverse();
      let hg = 0, sg = 0;
      if (o.tinted_future){ hg = h; sg = Math.trunc(s * 0.2); }
      let sg2, eg2;
      if (dark){ sg2 = 56; eg2 = 150; } else { sg2 = L(82); eg2 = L(48); }
      for (let i = 0; i < n; i++){ const t = i / (n - 1); fut.push(fromHsl(hg, sg, Math.trunc(sg2 + t * (eg2 - sg2)))); }
      const opacity = Math.trunc(o.empty_opacity * 2.55);
      let empty, emptyA;
      if (dark){ empty = o.empty_white ? [255, 255, 255] : [0, 0, 0]; emptyA = opacity; }
      else if (o.empty_white){ empty = [255, 255, 255]; emptyA = opacity; }
      else { empty = [132, 132, 132]; emptyA = Math.max(18, Math.min(110, Math.trunc(opacity * 0.7))); }
      return {levels: levels, future: fut, alpha: maxA, n: n, empty: empty, emptyA: emptyA};
    }
    // ---- layout
    legendH(){ return this.o.show_legend ? Math.trunc(28 * Math.max(1, this.o.scale)) : 0; }
    // months on each side of the middle one: 9 months, fewer on a narrow card (a phone) so the days stay 9 px or more
    contR(width){
      const o = this.o, w = (width == null ? this.w : width) - 4, step = 17.5, label = !o.hide_labels ? 30 : 2;  // the cell's size on screen: the widget's scale cancels out
      for (let r = 4; r > 2; r--){ if (w * 14 >= 9 * (label + this.boxCols(r) * step + 2 * r * 0.35 * step)) return r; }
      return 2;
    }
    boxCols(r){ return r == null ? this.boxCols(this.contR()) : Math.round(BOX_COLS * (2 * r + 1) / 9); }
    // a month of the continuous view (m from 1; out of 1-12 it goes to the year before or after)
    contMonth(y, m){
      while (m > 12){ m -= 12; y++; } while (m < 1){ m += 12; y--; }
      const first = utc(y, m - 1, 1), next = m === 12 ? utc(y + 1, 0, 1) : utc(y, m, 1);
      const dim = Math.round((next - first) / MS_DAY);
      const wd = (first.getUTCDay() + 6) % 7;   // Monday = 0
      const startCol = this.o.monday_first ? wd : (wd + 1) % 7;
      return {y: y, m: m, startCol: startCol, cols: Math.trunc((startCol + dim + 6) / 7), dim: dim, first: first};
    }
    contMonths(){
      const t = this.today(), R = this.contR();
      let rm = t.getUTCMonth() + 1 + (this.o.cont_month_offset | 0), ry = t.getUTCFullYear();
      while (rm > 12){ rm -= 12; ry++; } while (rm < 1){ rm += 12; ry--; }
      const res = [];
      for (let off = -R; off <= R; off++){
        let m = rm + off, y = ry;
        while (m > 12){ m -= 12; y++; } while (m < 1){ m += 12; y--; }
        const first = utc(y, m - 1, 1), next = m === 12 ? utc(y + 1, 0, 1) : utc(y, m, 1);
        const dim = Math.round((next - first) / MS_DAY);
        const wd = (first.getUTCDay() + 6) % 7;   // Monday = 0
        const startCol = this.o.monday_first ? wd : (wd + 1) % 7;
        res.push({y: y, m: m, startCol: startCol, cols: Math.trunc((startCol + dim + 6) / 7), dim: dim, first: first});
      }
      return res;
    }
    grow(ratio, unitH){
      if (ratio <= 1) return 1;
      let g = Math.min(ratio, MAX_GROW);
      if (this.lh() > 0 && unitH > 0){ g = Math.min(g, (this.lh() - (10 * this.o.scale + this.legendH())) / unitH); }
      return Math.max(1, g);
    }
    contLayout(){
      const o = this.o, months = this.contMonths();
      const target = 14 * o.scale;
      const showLbl = !o.hide_labels;
      let label = showLbl ? 30 * o.scale : 2 * o.scale;
      let mt = showLbl ? 22 * o.scale : 2 * o.scale;
      let spacing = target * 0.25, step = target + spacing, gap = 0.35 * step;
      const cols = this.boxCols();
      let total = label + cols * step + (months.length - 1) * gap;
      const avail = this.w - 4;
      let cell;
      if (total > avail && avail > 50){
        const r = avail / total;
        cell = target * r; spacing *= r; step *= r; gap *= r; label *= r; mt *= r; total = avail;
      } else {
        cell = target;
        if (avail > 50 && total > 0){
          const g = this.grow(avail / total, mt + 7 * step);
          if (g > 1){ cell *= g; spacing *= g; step *= g; gap *= g; label *= g; mt *= g; total *= g; }
        }
      }
      const contentH = mt + 7 * (cell + spacing) - spacing + 10 * o.scale + this.legendH();
      if (contentH < this.lh()) mt += (this.lh() - contentH) / 2;
      let off = 0; if (total < this.w) off = (this.w - total) / 2;
      let startX = off + label;
      const boxLeft = startX;
      startX += (cols - months.reduce(function(a, m){ return a + m.cols; }, 0)) * step / 2;
      return {cell: cell, spacing: spacing, step: step, gap: gap, label: label, mt: mt, startX: startX, boxLeft: boxLeft, months: months};
    }
    // year / 365 on a narrow card, where 53 weeks side by side would make the days smaller than 9 px.
    // By default the year in two halves, one over the other, the recent half on top (as the years view puts the latest
    // year first), close together; the widget's scale cancels out of the cell's size on screen
    narrowGrid(width){
      if (this.o.mode !== 'year' && this.o.mode !== '365') return false;
      if (!this.narrowOn()) return false;
      const w = (width == null ? this.w : width) - 4, label = !this.o.hide_labels ? 30 : 2;
      return w > 50 && w * 14 < 9 * (label + 53 * 17.5 - 3.5);
    }
    // the right-click option narrow_layout; unset (the Deep Dive's default): on a phone only
    narrowOn(){
      const v = this.o.narrow_layout;
      return v == null ? !!(DD.isTouch && DD.isTouch()) : !!v;
    }
    gridSplit(width){ return !this.o.month_grid && this.narrowGrid(width); }
    // the years view on a narrow card (a phone): its cells already as small as the width makes them, the Deep Dive
    // card takes the height of all its years (at its row's height, only the latest showed, the others scrolled)
    yearsNarrow(width){
      if (this.o.mode !== 'years' || !this.narrowOn()) return false;
      const w = (width == null ? this.w : width) - 4, s = this.o.scale;
      return w > 50 && w < 50 * s + 53 * 17.5 * s - 3.5 * s;
    }
    // the lower half's top, from the upper's: under its 7 rows, with room for the lower half's months' labels
    gridHalfY(split, cell, sp, mt){ return split ? 7 * (cell + sp) - sp + Math.max(mt, 0.4 * (cell + sp)) : 0; }
    // a week's place: its column and its half's top (the older weeks, 1-27, on the lower row)
    gridPos(G, wk){
      const b = G.split && wk >= HALF;
      return {col: b ? wk - HALF : wk, top: G.startY + (G.split && !b ? G.y2 : 0), half: b ? 1 : 0};
    }
    // With the month_grid option: the
    // months as blocks in a grid, the recent row on top, each row in reading order (4 a row and 3 rows: about a square; 6 a row when that keeps the days
    // 11 px). Each block is a month as in the continuous view (a column a week). 365: the 12 months ending with its last
    // day. nat: the natural height's layout (no height to fit in).
    mgMonths(){
      const o = this.o, today = this.today();
      let y, m;
      if (o.mode === 'year'){ y = today.getUTCFullYear() + this._yearOff; m = 11; }
      else { const end = addDays(today, 365 * this._endOff + (this._endShift | 0)); y = end.getUTCFullYear(); m = end.getUTCMonth(); }
      const res = [];
      for (let k = 11; k >= 0; k--){
        let mm = m - k, yy = y; while (mm < 0){ mm += 12; yy--; }
        const first = utc(yy, mm, 1), next = mm === 11 ? utc(yy + 1, 0, 1) : utc(yy, mm + 1, 1);
        const dim = Math.round((next - first) / MS_DAY), wd = (first.getUTCDay() + 6) % 7;
        const startCol = o.monday_first ? wd : (wd + 1) % 7;
        res.push({y: yy, m: mm, first: first, dim: dim, startCol: startCol});
      }
      return res;
    }
    mgrid(width, nat){
      const o = this.o;
      if (!o.month_grid || !this.narrowGrid(width)) return null;
      const W = (width == null ? this.w : width) - 4, lab0 = !o.hide_labels ? 30 : 2;
      // the days' size on screen for P months a row (the widget's scale cancels out)
      const unitW = function(P){ return lab0 + P * (6 * 17.5 - 3.5) + (P - 1) * 0.6 * 17.5; };
      const P = W * 14 / unitW(6) >= 11 ? 6 : W * 14 / unitW(4) >= 9 ? 4 : 3, rows = Math.ceil(12 / P);
      const s = o.scale;
      let cell = 14 * s, sp = cell * 0.25, label = lab0 * s, mt = !o.hide_labels ? 22 * s : 0;
      const dims = function(){
        const step = cell + sp, blockW = 6 * step - sp, hgap = 0.6 * step, vgap = (mt ? 0.4 : 0.7) * step, rowH = mt + 7 * step - sp;
        return {step: step, blockW: blockW, hgap: hgap, vgap: vgap, rowH: rowH,
          w: label + P * blockW + (P - 1) * hgap, h: rows * rowH + (rows - 1) * vgap};
      };
      let D = dims(), f = 1;
      if (D.w > W) f = W / D.w;
      else if (nat) f = Math.max(1, Math.min(W / D.w, MAX_GROW));
      else f = this.grow(W / D.w, D.h);
      cell *= f; sp *= f; label *= f; mt *= f; D = dims();
      let startY = mt;
      if (!nat){ const contentH = D.h + 10 * s + this.legendH(); if (contentH < this.lh()) startY += (this.lh() - contentH) / 2; }
      const startX = (D.w < this.w ? (this.w - D.w) / 2 : 0) + label;
      const blocks = this.mgMonths().map(function(mo, i){
        // the rows from the recent one down (as the two rows), each in reading order
        return {mo: mo, x: startX + (i % P) * (D.blockW + D.hgap), y: startY + (rows - 1 - Math.floor(i / P)) * (D.rowH + D.vgap)};
      });
      return {cell: cell, sp: sp, step: D.step, label: label, mt: mt, P: P, rows: rows, startX: startX, startY: startY,
        blocks: blocks, h: D.h, right: startX + P * D.blockW + (P - 1) * D.hgap,
        bottom: startY + (rows - 1) * (D.rowH + D.vgap) + D.rowH - mt, rowTops: blocks.filter(function(b, i){ return i % P === 0; }).map(function(b){ return b.y; })};
    }
    gridGeometry(){
      const o = this.o, split = this.gridSplit(), cols = split ? HALF : 53;
      const target = 14 * o.scale;
      let label = !o.hide_labels ? 30 * o.scale : 2 * o.scale;
      let mt = !o.hide_labels ? 22 * o.scale : 2 * o.scale;
      let spacing = target * 0.25;
      const gridW = cols * (target + spacing) - spacing;
      let total = label + gridW;
      const avail = this.w - 4;
      let cell;
      if (total > avail && avail > 50){
        const r = avail / total; cell = target * r; spacing *= r; label *= r; mt *= r; total = avail;
      } else {
        cell = target;
        if (avail > 50 && total > 0){
          const g = this.grow(avail / total, mt + this.gridHalfY(split, target, spacing, mt) + 7 * (target + spacing));
          if (g > 1){ cell *= g; spacing *= g; label *= g; mt *= g; total *= g; }
        }
      }
      // a split year on a card too short for its two halves (a narrow Deep Dive card): smaller days, rather than the
      // lower half running under the legend and out of the card
      const below = 10 * o.scale + this.legendH();
      const needH = mt + this.gridHalfY(split, cell, spacing, mt) + 7 * (cell + spacing) - spacing;
      if (split && this.lh() > below && needH + below > this.lh()){
        const r = (this.lh() - below) / needH;
        cell *= r; spacing *= r; label *= r; mt *= r; total = label + cols * (cell + spacing) - spacing;
      }
      let off = 0; if (total < this.w) off = (this.w - total) / 2;
      let startY = mt;
      const y2 = this.gridHalfY(split, cell, spacing, mt);
      const contentH = mt + y2 + 7 * (cell + spacing) - spacing + below;
      if (contentH < this.lh()) startY += (this.lh() - contentH) / 2;
      return {cell: cell, spacing: spacing, startX: off + label, startY: startY, label: label, cols: cols, split: split, y2: y2};
    }
    // [left, right] of the drawn grid assembly (in canvas px) so the nav bar aligns with it
    contentXExtent(){
      if (!this.w) return null;
      if (this.o.mode === 'continuous'){
        const L = this.contLayout();
        const right = L.boxLeft + this.boxCols() * L.step + Math.max(0, L.months.length - 1) * L.gap - L.spacing;
        return [L.boxLeft - L.label, right];
      }
      const M = this.mgrid(); if (M) return [M.startX - M.label, M.right];
      const G = this.gridGeometry(), step = G.cell + G.spacing;
      return [G.startX - G.label, G.startX + G.cols * step - G.spacing];
    }
    gridInfo(){
      const today = this.today();
      if (this.o.mode === 'year' || this.o.mode === 'years'){
        const yr = today.getUTCFullYear() + this._yearOff;
        const start = utc(yr, 0, 1);
        const wd = (start.getUTCDay() + 6) % 7, dow = this.o.monday_first ? wd : (wd + 1) % 7;
        return {start: addDays(start, -dow), inRange: function(d){ return d.getUTCFullYear() === yr; }};
      }
      const end = addDays(today, 365 * this._endOff + (this._endShift | 0)), rs = addDays(end, -364);
      const wd = (rs.getUTCDay() + 6) % 7, dow = this.o.monday_first ? wd : (wd + 1) % 7;
      return {start: addDays(rs, -dow), inRange: function(d){ return d >= rs && d <= end; }};
    }
    // ---- years view
    yearsList(){
      const last = this.today().getUTCFullYear(), self = this;
      let first = last; const totals = {};
      Object.keys(this.data).forEach(function(k){
        const y = parseInt(k.slice(0, 4), 10);
        if (!(y >= 2006 && y <= last)) return;
        const e = self.data[k]; if (!e) return;
        const pf = self.entryCounts(e);
        if (pf[0] > 0){ totals[y] = (totals[y] || 0) + pf[0]; if (y < first) first = y; }
      });
      const ys = []; for (let y = last; y >= first; y--) ys.push(y);
      return ys;
    }
    yearsShown(){
      const all = this.yearsList(), fold = Math.max(0, this.o.years_fold == null ? 3 : this.o.years_fold | 0);
      const can = fold > 0 && all.length > fold + 1;
      this._canFold = can; this._allYears = all;
      this._hidden = can && !this._expanded ? all.length - fold : 0;
      return this._hidden === 0 ? all : all.slice(0, fold);
    }
    // 14 px cells (scaled) however many years show, made smaller only when too wide
    yearsFixedFit(width){
      const o = this.o, s = o.scale;
      let cell = 14 * s, sp = cell * 0.25, label = 50 * s, mt = !o.hide_labels ? 22 * s : 6 * s;
      let tw = label + 53 * (cell + sp) - sp;
      const avail = width - 4;
      if (tw > avail && avail > 50){ const r = avail / tw; cell *= r; sp *= r; label *= r; mt *= r; tw = avail; }
      return {cell: cell, sp: sp, tw: tw, label: label, mt: mt};
    }
    // the height the widget asks for at this width
    naturalHeight(width){
      const o = this.o, s = o.scale;
      const key = [o.mode, this._expanded, this.data, width, o.hide_labels, o.show_legend, o.years_fold, o.years_no_gap, o.month_grid, o.narrow_layout, s].join('|');
      if (this._natKey === key) return this._nat;
      let h;
      if (o.mode === 'years'){
        const n = Math.max(1, this.yearsShown().length), f = this.yearsFixedFit(width);
        const gapF = o.years_no_gap ? 0.25 : 1.25, legendH = this.legendH();
        const toggleH = this._canFold && !(legendH > 0) ? 22 * Math.max(0.8, s) : 0;
        h = f.mt + n * (7 * (f.cell * 1.25) - f.cell * 0.25) + Math.max(0, n - 1) * gapF * f.cell + toggleH + 10 * s + legendH;
      } else {
        const target = 14 * s, label = o.hide_labels ? 2 * s : 30 * s, mt0 = o.hide_labels ? 2 * s : 22 * s;
        let cell = target, sp = target * 0.25, mt = mt0;
        // continuous on a narrow card: its fewer months side by side (contLayout); the 9 months as wide as a year
        // a narrow year / 365: its two halves (gridGeometry)
        const R = o.mode === 'continuous' ? this.contR(width) : 0, split = this.gridSplit(width);
        const total = R && R < 4 ? label + this.boxCols(R) * (target + sp) + 2 * R * 0.35 * (target + sp) : label + (split ? HALF : 53) * (target + sp) - sp, avail = width - 4;
        if (total > avail && avail > 50){ const r = avail / total; cell *= r; sp *= r; mt *= r; }
        else if (avail > 50){ const g = Math.max(1, Math.min(avail / total, 6)); cell *= g; sp *= g; mt *= g; }
        h = mt + this.gridHalfY(split, cell, sp, mt) + 7 * (cell + sp) + 10 * s + this.legendH();
        const M = this.mgrid(width, true); if (M) h = M.h + 10 * s + this.legendH();  // a narrow year / 365: its months' grid
      }
      this._natKey = key; this._nat = Math.trunc(h);
      return this._nat;
    }
    yearsLayout(){
      const self0 = this;
      const o = this.o, s = o.scale, years = this.yearsShown(), n = Math.max(1, years.length);
      const H = this.lh(), legendH = this.legendH();
      const inLegend = this._canFold && legendH > 0;
      const toggleH = this._canFold && !inLegend ? 22 * Math.max(0.8, s) : 0;
      const bottom = 10 * s + legendH;
      const gapF = o.years_no_gap ? 0.25 : 1.25;
      const labelSpace = 50 * s, mt = !o.hide_labels ? 22 * s : 6 * s;
      const avail = this.w - 4, perW = 53 * 1.25 - 0.25;
      const own = !!o.own_height;  // pinned: its own height, the fixed cell size
      const fit = function(width){
        if (own) return self0.yearsFixedFit(width);
        const cellW = width - 4 > labelSpace ? (width - 4 - labelSpace) / perW : 14 * s;
        const perH = n * (7 * 1.25 - 0.25) + Math.max(0, n - 1) * gapF;
        const cellAll = perH > 0 ? (H - (mt + toggleH + bottom)) / perH : 14 * s;
        const cellYear = (H - mt - bottom) / (7 * 1.25 - 0.25);
        let cell = Math.max(cellAll, cellYear);
        cell = Math.min(cellW, Math.max(6, cell)); cell = Math.max(1, cell);
        const sp = cell * 0.25;
        return {cell: cell, sp: sp, tw: labelSpace + 53 * (cell + sp) - sp};
      };
      const gridH = function(cell){ return n * (7 * (cell * 1.25) - cell * 0.25) + Math.max(0, n - 1) * gapF * cell; };
      const vpBottom = own ? H : H - bottom;
      let room = 0, f, maxScroll = 0;
      for (let k = 0; k < 2; k++){
        f = fit(this.w - room);
        const contentH = mt + gridH(f.cell) + toggleH;
        maxScroll = Math.max(0, contentH - vpBottom);
        if (maxScroll <= 0 || room) break;
        room = 10;
      }
      const step = f.cell + f.sp, gap = gapF * f.cell;
      const lab = own ? f.label : labelSpace, mtop = own ? f.mt : mt;
      if (own) maxScroll = 0;
      const startX = Math.max(0, (this.w - room - f.tw) / 2) + lab;
      const scroll = Math.min(maxScroll, Math.max(0, this._scroll || 0)); this._scroll = scroll;
      let startY = mtop - scroll;
      const contentH = mtop + gridH(f.cell) + toggleH;
      if (!own && contentH + bottom < H) startY += (H - contentH - bottom) / 2;
      const blocks = []; let y = startY;
      const self = this;
      years.forEach(function(yr){
        const st = utc(yr, 0, 1), wd = (st.getUTCDay() + 6) % 7, dow = o.monday_first ? wd : (wd + 1) % 7;
        blocks.push({yr: yr, gs: addDays(st, -dow), y0: y}); y += 7 * step - f.sp + gap;
      });
      const gridBottom = blocks.length ? blocks[blocks.length - 1].y0 + 7 * step - f.sp : startY;
      return {cell: f.cell, sp: f.sp, step: step, startX: startX, startY: startY, label: lab, blocks: blocks, years: years,
        bottom: Math.min(gridBottom + toggleH, vpBottom), vpBottom: vpBottom, toggleH: toggleH, inLegend: inLegend, gridBottom: gridBottom, scroll: scroll, maxScroll: maxScroll};
    }
    yearTotalLines(yr){
      const o = this.o, comps = components(o.metric), self = this;
      let reviews = 0, passed = 0, tm = 0; const sums = comps.map(function(){ return 0; });
      let any = false;
      Object.keys(this.data).forEach(function(k){
        if (parseInt(k.slice(0, 4), 10) !== yr) return;
        const e = self.data[k]; if (!e || typeof e !== 'object') return;
        any = true;
        reviews += +(e.reviews || 0); passed += +(e.passed || 0); tm += +(e.time_ms || 0);
        comps.forEach(function(c, i){ if (['reviews', 'correct', 'failed', 'types'].indexOf(c[0]) >= 0) sums[i] += compValue(c, e); });
      });
      if (!any) return [];
      const lines = [];
      comps.forEach(function(c, i){
        const key = c[0]; let text = '';
        if (['reviews', 'correct', 'failed', 'types'].indexOf(key) >= 0){
          const v = sums[i];
          text = v <= 0 ? '' : (v >= 100000 ? (v / 1000).toFixed(0) + 'k' : (v >= 1000 ? (v / 1000).toFixed(1) + 'k' : String(pyRound(v))));
        } else if (key === 'time') text = tm > 0 ? self.fmtThreshold1('time', tm) : '';
        else if (key === 'retention') text = reviews > 0 ? (passed / reviews * 100).toFixed(1) + '%' : '';
        else if (key === 'avg_time') text = reviews > 0 ? self.fmtThreshold1('avg_time', tm / reviews) : '';
        if (text) lines.push(text);
      });
      return lines;
    }
    fmtThreshold1(key, v){
      const s = v / 1000;
      if (key === 'time'){ if (s >= 3600) return (s / 3600).toFixed(1) + 'h'; if (s >= 60) return pyRound(s / 60) + 'm'; return pyRound(s) + 's'; }
      return (s < 10 ? s.toFixed(1) : String(pyRound(s))) + 's';
    }
    // every visible cell: {date, str, x, y}
    cells(){
      const out = [];
      if (this.o.mode === 'years'){
        const Y = this.yearsLayout();
        Y.blocks.forEach(function(b){
          for (let wk = 0; wk < 53; wk++) for (let dy = 0; dy < 7; dy++){
            const d = addDays(b.gs, wk * 7 + dy);
            if (d.getUTCFullYear() !== b.yr) continue;
            out.push({d: d, s: iso(d), x: Y.startX + wk * Y.step, y: b.y0 + dy * Y.step});
          }
        });
        return {cells: out, cell: Y.cell, Y: Y};
      }
      if (this.o.mode === 'continuous'){
        const L = this.contLayout(), ms = [], px = this._panPx || 0;
        let cx = L.startX, clipX = null;
        L.months.forEach(function(m){ ms.push({mo: m, x: cx}); cx += m.cols * L.step + L.gap; });
        // a finger dragging the months (panSettle): all of them moved by px, more months coming in at the side it
        // uncovers, the box's edges cutting them
        if (px){
          const left = L.boxLeft, right = L.boxLeft + this.boxCols() * L.step + (L.months.length - 1) * L.gap - L.spacing;
          ms.forEach(function(e){ e.x += px; });
          while (ms[0].x > left - L.step){ const f = ms[0].mo, q = this.contMonth(f.y, f.m - 1); ms.unshift({mo: q, x: ms[0].x - q.cols * L.step - L.gap}); }
          for (;;){
            const e = ms[ms.length - 1], end = e.x + e.mo.cols * L.step;
            if (end > right + L.step) break;
            ms.push({mo: this.contMonth(e.mo.y, e.mo.m + 1), x: end + L.gap});
          }
          clipX = [left - L.spacing, right + L.spacing];
        }
        ms.forEach(function(e){
          const m = e.mo;
          if (clipX && (e.x > clipX[1] || e.x + m.cols * L.step < clipX[0])) return;
          for (let col = 0; col < m.cols; col++) for (let row = 0; row < 7; row++){
            const off = col * 7 + row - m.startCol;
            if (off < 0 || off >= m.dim) continue;
            const d = addDays(m.first, off);
            out.push({d: d, s: iso(d), x: e.x + col * L.step, y: L.mt + row * L.step});
          }
        });
        return {cells: out, cell: L.cell, L: L, ms: ms, clipX: clipX};
      }
      const M = this.mgrid();
      if (M){
        const inf = this.gridInfo();
        M.blocks.forEach(function(b){
          const m = b.mo;
          for (let col = 0; col < 6; col++) for (let row = 0; row < 7; row++){
            const off = col * 7 + row - m.startCol;
            if (off < 0 || off >= m.dim) continue;
            const d = addDays(m.first, off);
            if (!inf.inRange(d)) continue;
            out.push({d: d, s: iso(d), x: b.x + col * M.step, y: b.y + row * M.step});
          }
        });
        return {cells: out, cell: M.cell, M: M, step: M.step, info: inf};
      }
      const G = this.gridGeometry(), info = this.gridInfo(), step = G.cell + G.spacing;
      for (let wk = 0; wk < 53; wk++) for (let dy = 0; dy < 7; dy++){
        const d = addDays(info.start, wk * 7 + dy);
        if (!info.inRange(d)) continue;
        const P = this.gridPos(G, wk);
        out.push({d: d, s: iso(d), x: G.startX + P.col * step, y: P.top + dy * step});
      }
      return {cells: out, cell: G.cell, G: G, step: step, info: info};
    }
    // ---- values and colors
    entryCounts(e){
      const m = this.o.metric;
      const v = metricValue(m, e, this._scales);
      if (m !== 'reviews' || !e || typeof e !== 'object') return [v, 0];
      return [v, +(e.future || 0)];
    }
    maxCounts(dates){
      const data = this.data, entries = [];
      dates.forEach(function(s){ const e = data[s]; if (e && typeof e === 'object') entries.push(e); });
      this._scales = computeScales(this.o.metric, entries);
      let maxP = 0, maxF = 0; const past = [], fut = [];
      dates.forEach(function(s){
        const e = data[s]; if (!e) return;
        const pf = this.entryCounts(e);
        if (pf[0] > 0) past.push(pf[0]); if (pf[1] > 0) fut.push(pf[1]);
        if (pf[0] > maxP) maxP = pf[0]; if (pf[1] > maxF) maxF = pf[1];
      }, this);
      if (past.length >= 20){ past.sort(function(a, b){ return a - b; }); maxP = past[Math.min(past.length - 1, Math.floor(past.length * 0.95))]; }
      if (fut.length >= 20){ fut.sort(function(a, b){ return a - b; }); maxF = fut[Math.min(fut.length - 1, Math.floor(fut.length * 0.95))]; }
      this.maxP = Math.max(1, maxP); this.maxF = Math.max(1, maxF);
    }
    // a drag of the continuous view: the months coming and going change the scale (the colors and the legend's
    // numbers) a step at a time; while it moves (and glides back) the scale eases to the new one instead.
    // Returns true while it still moves (a frame more wanted).
    easeScale(){
      const moving = !!(this._panPx || this.panTr);
      if (!(DD.anim && DD.anim.on)){ this._mS = null; return false; }  // animations off: the scale at once
      if (!moving && !this._mS) return false;
      const now = performance.now();
      if (!this._mS){ this._mS = {p: this.maxP, f: this.maxF, t: now}; return true; }
      const S = this._mS, dt = Math.min(64, Math.max(0, now - S.t)), k = 1 - Math.exp(-dt / (140 * DD.speed()));
      S.t = now;
      S.p += (this.maxP - S.p) * k; S.f += (this.maxF - S.f) * k;
      const done = Math.abs(this.maxP - S.p) <= this.maxP * 0.005 && Math.abs(this.maxF - S.f) <= this.maxF * 0.005;
      if (done && !moving){ this._mS = null; return false; }
      this.maxP = S.p; this.maxF = S.f;
      return true;
    }
    pastLevel(count){
      const curve = 65 / this.o.intensity_curve, n = this.lv.n;
      return Math.min(n - 1, Math.trunc(Math.pow(count / this.maxP, curve) * n));
    }
    futureLevel(f){
      const curve = 65 / this.o.intensity_curve, n = this.lv.n, den = Math.max(1, this.maxF || 0);
      let lvl = Math.min(n - 1, Math.trunc(Math.pow(f / den, curve) * n));
      if (f > 0 && n > 1) lvl = Math.max(1, lvl);
      return lvl;
    }
    cellColor(count, future, d, today){
      const lv = this.lv, A = lv.alpha;
      const isFuture = d > today, isToday = +d === +today;
      if (isFuture){
        if (this.o.show_future && future > 0) return rgbaStr(lv.future[this.futureLevel(future)], A);
        return null;
      }
      if (isToday && count === 0 && future > 0 && this.o.show_future) return rgbaStr(lv.future[this.futureLevel(future)], A);
      if (count === 0) return null;
      const level = this.pastLevel(count);
      if (this.hiddenSteps && this.hiddenSteps.size && this.hiddenSteps.has(this.stepForLevel(level))) return null;
      const c = lv.levels[level];
      const ratio = count / this.maxP;
      if (ratio <= 1 || level < lv.n - 1) return rgbaStr(c, A);
      const t = Math.min(1, Math.log2(ratio) / 2);
      const sat = hsvSat(c[0], c[1], c[2]), hue = hueOf(c[0], c[1], c[2]);
      let light = lightnessOf(c[0], c[1], c[2]);
      const shift = Math.trunc(255 * 0.16 * t);
      const lighter = this.dark() !== !!this.o.invert;
      light = lighter ? Math.min(255, light + shift) : Math.max(0, light - shift);
      return rgbaStr(fromHsl(Math.max(0, hue), sat, light), A);
    }
    levelStarts(){
      const n = this.lv.n, steps = Math.min(5, n), set = {};
      if (steps > 1) for (let i = 0; i < steps; i++) set[pyRound(i * (n - 1) / (steps - 1))] = 1; else set[0] = 1;
      return Object.keys(set).map(Number).sort(function(a, b){ return a - b; });
    }
    stepForLevel(level){
      let step = 0; this.levelStarts().forEach(function(st, i){ if (level >= st) step = i; });
      return step;
    }
    legendStepAt(mx, my){
      const hs = this._legendHits || [];
      for (let i = 0; i < hs.length; i++){ const r = hs[i]; if (mx >= r.x && mx <= r.x + r.w && my >= r.y && my <= r.y + r.h) return r.step; }
      return null;
    }
    toggleHit(mx, my){
      const r = this._toggleRect;
      return !!(r && mx >= r.x && mx <= r.x + r.w && my >= r.y && my <= r.y + r.h);
    }
    legendItems(){
      const lv = this.lv, n = lv.n, steps = Math.min(5, n);
      const set = {};
      if (steps > 1) for (let i = 0; i < steps; i++) set[pyRound(i * (n - 1) / (steps - 1))] = 1; else set[0] = 1;
      const idxs = Object.keys(set).map(Number).sort(function(a, b){ return a - b; });
      const curve = 65 / Math.max(1, this.o.intensity_curve);
      const comps = components(this.o.metric);
      const countLike = comps.length === 1 && ['time', 'avg_time', 'retention'].indexOf(comps[0][0]) < 0;
      const items = [[rgbaStr(lv.empty, lv.emptyA), '0']];
      const self = this;
      idxs.forEach(function(li){
        let text;
        if (li === 0) text = countLike ? '1' : '>0';
        else text = self.fmtThreshold(self.maxP * Math.pow(li / n, 1 / curve));
        if (li === idxs[idxs.length - 1]) text += '+';
        items.push([rgbaStr(lv.levels[li], lv.alpha), text]);
      });
      for (let i = 1; i < items.length - 1; i++) if (items[i][1] === items[i + 1][1].replace(/\+$/, '')) items[i][1] = '';
      return items;
    }
    fmtThreshold(v){
      const comps = components(this.o.metric);
      if (comps.length > 1) return pyRound(v) + '%';
      const key = comps[0][0];
      if (key === 'time'){
        const s = v / 1000;
        if (s >= 3600) return (s / 3600).toFixed(1) + 'h';
        if (s >= 60) return pyRound(s / 60) + 'm';
        return pyRound(s) + 's';
      }
      if (key === 'avg_time'){ const s = v / 1000; return (s < 10 ? s.toFixed(1) : String(pyRound(s))) + 's'; }
      if (key === 'retention') return pyRound(v) + '%';
      if (v >= 10000) return (v / 1000).toFixed(0) + 'k';
      return String(Math.ceil(v));
    }
    draw(){
      this._toggleRect = null; this._legendHits = [];
      const ctx = this.ctx, w = this.w, h = this.h, o = this.o, C = this.colors;
      ctx.clearRect(0, 0, w, h);
      this.lv = this.levels();
      const cs = this.cells();
      this._cs = cs;
      if (o.mode === 'years'){
        const ys = this._allYears && this._allYears.length ? this._allYears : [this.today().getUTCFullYear()];
        const lo = String(ys[ys.length - 1]), hi = String(ys[0]);
        this.maxCounts(Object.keys(this.data).filter(function(k){ const y = k.slice(0, 4); return y >= lo && y <= hi; }));
      } else this.maxCounts(cs.cells.map(function(c){ return c.s; }));
      this._easing = o.mode === 'continuous' && this.easeScale();
      const today = this.logicalToday();
      const radius = (cs.cell / 2) * (o.rounding / 100);
      const rr = function(x, y, s, r){
        ctx.beginPath();
        if (ctx.roundRect) ctx.roundRect(x, y, s, s, r); else ctx.rect(x, y, s, s);
        ctx.fill();
      };
      const emptyCss = rgbaStr(this.lv.empty, this.lv.emptyA);
      ctx.save();
      ctx.globalAlpha = Math.max(0, Math.min(1, this.progress));
      ctx.fillStyle = emptyCss;
      if (cs.Y){ ctx.save(); ctx.beginPath(); ctx.rect(0, 0, w, cs.Y.vpBottom); ctx.clip(); }
      if (cs.clipX){ ctx.save(); ctx.beginPath(); ctx.rect(cs.clipX[0], 0, cs.clipX[1] - cs.clipX[0], h); ctx.clip(); }
      cs.cells.forEach(function(c){ rr(c.x, c.y, cs.cell, radius); });
      cs.cells.forEach(function(c){
        const pf = this.entryCounts(this.data[c.s] || 0);
        const col = this.cellColor(pf[0], pf[1], c.d, today);
        if (!col) return;
        ctx.fillStyle = col; rr(c.x, c.y, cs.cell, radius);
      }, this);
      if (cs.clipX) ctx.restore();
      if (cs.Y) ctx.restore();
      // a thin bar on the right edge while the years scroll (in the room kept for it)
      const sb = this.scrollBar(cs);
      if (sb){
        ctx.save(); ctx.fillStyle = U.rgba(this.colors.text, (this._sbDrag ? 150 : 90) / 255);
        ctx.beginPath(); if (ctx.roundRect) ctx.roundRect(w - 6, sb.by, 4, sb.bh, 2); else ctx.rect(w - 6, sb.by, 4, sb.bh); ctx.fill(); ctx.restore();
      }
      this.drawLabels(ctx, cs);
      if (o.show_legend) this.drawLegend(ctx, cs);
      this.drawHover(ctx, cs, radius);
      ctx.restore();
    }
    // the years' scroll bar (its track and thumb), drawn on the right edge and taken by the mouse
    scrollBar(cs){
      const Y = cs && cs.Y; if (!Y || !(Y.maxScroll > 0)) return null;
      const top = 2, bot = Y.vpBottom - 2, track = Math.max(10, bot - top), vis = track / (track + Y.maxScroll);
      const bh = Math.max(18, track * vis), by = top + (track - bh) * (Y.scroll / Y.maxScroll);
      return {top: top, track: track, bh: bh, by: by, max: Y.maxScroll};
    }
    // ---- mode / navigation transitions ----
    // every cell of the current view: place, size, radius, empty colour and data colour (or null)
    visuals(){
      this.lv = this.levels();
      const cs = this.cells(), o = this.o;
      if (o.mode === 'years'){
        const ys = this._allYears && this._allYears.length ? this._allYears : [this.today().getUTCFullYear()];
        const lo = String(ys[ys.length - 1]), hi = String(ys[0]);
        this.maxCounts(Object.keys(this.data).filter(function(k){ const y = k.slice(0, 4); return y >= lo && y <= hi; }));
      } else this.maxCounts(cs.cells.map(function(c){ return c.s; }));
      const today = this.logicalToday(), radius = (cs.cell / 2) * (o.rounding / 100), m = {};
      const empty = [this.lv.empty[0], this.lv.empty[1], this.lv.empty[2], this.lv.emptyA / 255];
      cs.cells.forEach(function(c){
        const pf = this.entryCounts(this.data[c.s] || 0), col = this.cellColor(pf[0], pf[1], c.d, today);
        let rgba = null;
        if (col){ const q = U.parseColor(col); rgba = [q.r, q.g, q.b, q.a == null ? 1 : q.a]; }
        m[c.s] = {x: c.x, y: c.y, s: cs.cell, r: radius, e: empty, c: rgba};
      }, this);
      return {m: m, cs: cs, clip: cs.Y ? cs.Y.vpBottom : null};
    }
    labelsPicture(cs){
      const cv = document.createElement('canvas'); cv.width = this.canvas.width; cv.height = this.canvas.height;
      const g = cv.getContext('2d'), sc = DD.canvasScale(this.canvas, this.w, this.h); g.setTransform(sc[0], 0, 0, sc[1], 0, 0);
      try { this.drawLabels(g, cs); } catch (e) { DD.swallowed('heatmap labels', e); }
      return cv;
    }
    snapshotMode(){ const v = this.visuals(); return {v: v, labels: this.labelsPicture(v.cs), legendTop: this._legendTop}; }
    // a change of the years view (space between the years, older years folded) moves the
    // cells to their new places and fades the years that come or go, with the animation of a mode switch
    relayoutYears(change){
      if (this.o.mode !== 'years'){ change(); return; }
      let before = null; try { before = this.snapshotMode(); } catch (e) {}
      this.navTr = null; this.fade = null;
      change(); this._scroll = 0;
      try { if (before) this.startModeTr(before); } catch (e) { this.modeTr = null; }
    }
    // the continuous view let go after a drag of px: the months from the month nearest to where they are (the
    // offset), and what is left of px to glide back to their places (0 when they are there)
    panSettle(px){
      const o = this.o, base = o.cont_month_offset | 0, R = this.contR(), self = this;
      this._panPx = 0;
      const centerX = function(){ const L = self.contLayout(); let x = L.startX; for (let i = 0; i < R; i++) x += L.months[i].cols * L.step + L.gap; return {x: x, L: L}; };
      const c0 = centerX(), L = c0.L, mid = L.months[R];
      const width = function(j){ return self.contMonth(mid.y, mid.m + j).cols * L.step + L.gap; };
      const k0 = Math.round(-px / (4.4 * L.step + L.gap));
      let best = null;
      for (let k = k0 - 1; k <= k0 + 1; k++){
        let S = 0;
        if (k > 0) for (let j = 0; j < k; j++) S += width(j); else for (let j = k; j < 0; j++) S -= width(j);
        o.cont_month_offset = base + k;
        const r = c0.x + px + S - centerX().x;
        if (!best || Math.abs(r) < Math.abs(best.r)) best = {k: k, r: r};
      }
      o.cont_month_offset = base + best.k;
      return best.r;
    }
    startModeTr(before){
      if (!before || window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches){ this.modeTr = null; return; }
      const v = this.visuals();
      this.modeTr = {a: before.v, b: v, la: before.labels, lb: this.labelsPicture(v.cs), start: null, legendFrom: before.legendTop, k: DD.calm ? DD.calm() : 1};
      // years view on both sides: the year labels are drawn on each frame, sliding with their rows
      if (this.o.mode === 'years' && before.v.cs && before.v.cs.Y && v.cs.Y){
        const F = {}; before.v.cs.Y.blocks.forEach(function(b){ F[b.yr] = b.y0; }); this.modeTr.yearsFrom = F;
      }
    }
    drawModeTr(now){
      const T = this.modeTr; if (T.start === null) T.start = now;
      const p = Math.min(1, (now - T.start) / (320 * (T.k || 1))), oc = 1 - Math.pow(1 - p, 3), tt = oc * oc * (3 - 2 * oc);  // OutCubic, then smoothstep
      if (p >= 1){ this.modeTr = null; return false; }
      const ctx = this.ctx, W = this.w, H = this.h;
      ctx.clearRect(0, 0, W, H);
      const css = function(c, a){ return 'rgba(' + Math.round(c[0]) + ',' + Math.round(c[1]) + ',' + Math.round(c[2]) + ',' + (c[3] * a).toFixed(4) + ')'; };
      const mixc = function(a, b, t){ if (!a && !b) return null; const x = a || [b[0], b[1], b[2], 0], y = b || [a[0], a[1], a[2], 0]; return [x[0] + (y[0] - x[0]) * t, x[1] + (y[1] - x[1]) * t, x[2] + (y[2] - x[2]) * t, x[3] + (y[3] - x[3]) * t]; };
      const rr = function(x, y, sz, r){ ctx.beginPath(); if (ctx.roundRect) ctx.roundRect(x, y, sz, sz, Math.max(0, Math.min(r, sz / 2))); else ctx.rect(x, y, sz, sz); ctx.fill(); };
      // each side cut as it shows: a view with a viewport (the years scrolled) cuts its own cells at its bottom, a cell
      // under that cut on one side fades on the other (it was not on screen to move from or to), and the cells that move
      // are cut at a bottom going from the old view's to the new one's with them. One cut for all (the old view's or the
      // new one's) hid the lower row of the months as a grid during the move, popping in at the end (YRS -> 365) or
      // gone at once (365 -> YRS).
      const ca = T.a.clip, cb = T.b.clip, cm = ca == null && cb == null ? null : (ca == null ? H : ca) + ((cb == null ? H : cb) - (ca == null ? H : ca)) * tt;
      const seen = function(c, cut){ return c && (cut == null || c.y < cut) ? c : null; };
      const gone = [], come = [], move = [];
      new Set(Object.keys(T.a.m).concat(Object.keys(T.b.m))).forEach(function(k){
        const o = seen(T.a.m[k], ca), n = seen(T.b.m[k], cb);
        if (o || n) (o && n ? move : (o ? gone : come)).push([o, n]);
      });
      const pass = function(cut, list){
        ctx.save();
        if (cut != null){ ctx.beginPath(); ctx.rect(0, 0, W, cut); ctx.clip(); }
        list.forEach(function(p){ cell(p[0], p[1]); });
        ctx.restore();
      };
      const cell = function(o, n){
        if (o && n){
          const x = o.x + (n.x - o.x) * tt, y = o.y + (n.y - o.y) * tt, sz = o.s + (n.s - o.s) * tt, r = o.r + (n.r - o.r) * tt;
          ctx.fillStyle = css(mixc(o.e, n.e, tt), 1); rr(x, y, sz, r);
          const c = mixc(o.c, n.c, tt); if (c){ ctx.fillStyle = css(c, 1); rr(x, y, sz, r); }
        } else {
          const q = o || n, a = o ? 1 - tt : tt;  // a cell only on one side fades out / in where it is
          ctx.fillStyle = css(q.e, a); rr(q.x, q.y, q.s, q.r);
          if (q.c){ ctx.fillStyle = css(q.c, a); rr(q.x, q.y, q.s, q.r); }
        }
      };
      pass(ca, gone);
      pass(cb, come);
      pass(cm, move);
      if (T.yearsFrom){ ctx.save(); try { this.drawYearLabels(ctx, T.b.cs, {from: T.yearsFrom, tt: tt}); } catch (e) { DD.swallowed('heatmap year labels', e); } ctx.restore(); }
      else {
        ctx.save(); ctx.setTransform(1, 0, 0, 1, 0, 0);
        ctx.globalAlpha = 1 - tt; ctx.drawImage(T.la, 0, 0);
        ctx.globalAlpha = tt; ctx.drawImage(T.lb, 0, 0);
        ctx.restore();
      }
      if (this.o.show_legend){ ctx.save(); this.drawLegend(ctx, T.b.cs, T.legendFrom, tt); ctx.restore(); }
      return true;
    }
    // arrows: the old view slides out, the new one in (nav transition, 300 ms OutCubic)
    startNavTr(img, dir){ this.navTr = {img: img, dir: dir, start: null, to: null}; }
    drawNavTr(now){
      const T = this.navTr, cv = this.canvas;
      if (T.start === null){
        T.start = now; this.navTr = null; this.draw(); this.navTr = T;
        T.to = document.createElement('canvas'); T.to.width = cv.width; T.to.height = cv.height; T.to.getContext('2d').drawImage(cv, 0, 0);
      }
      const p = Math.min(1, (now - T.start) / (300 * (DD.calm ? DD.calm() : DD.speed()))), t = 1 - Math.pow(1 - p, 3);  // the add-on's tempo, as its other moves
      if (p >= 1 || T.to.width !== cv.width){ this.navTr = null; return false; }
      const ctx = this.ctx, W = cv.width, shift = t * W;
      ctx.save(); ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.clearRect(0, 0, W, cv.height);
      ctx.drawImage(T.img, Math.round(-T.dir * shift), 0); ctx.drawImage(T.to, Math.round(T.dir * (W - shift)), 0);
      ctx.restore();
      return true;
    }
    hitTest(mx, my){
      const cs = this._cs; if (!cs) return null;
      const step = cs.step || (cs.L && cs.L.step) || (cs.Y && cs.Y.step) || cs.cell * 1.25;
      if (cs.Y && my > cs.Y.vpBottom) return null;
      for (let i = 0; i < cs.cells.length; i++){
        const c = cs.cells[i];
        if (mx >= c.x && mx < c.x + step && my >= c.y && my < c.y + step) return c;
      }
      return null;
    }
    drawHover(ctx, cs, radius){
      const c = this.hover; if (!c) return;
      ctx.strokeStyle = U.rgba(this.colors.text_primary || this.colors.text, 1); ctx.lineWidth = 2;
      ctx.beginPath(); if (ctx.roundRect) ctx.roundRect(c.x, c.y, cs.cell, cs.cell, radius); else ctx.rect(c.x, c.y, cs.cell, cs.cell); ctx.stroke();
    }
    tooltipRows(c){
      const e0 = this.data[c.s], e = (e0 && typeof e0 === 'object') ? e0 : {reviews: e0 || 0};
      const count = +(e.reviews || 0), future = +(e.future || 0), tm = +(e.time_ms || 0), passed = +(e.passed || 0);
      const today = this.logicalToday(), d = c.d;
      const rows = [{header: true, text: MONTHS[d.getUTCMonth()] + ' ' + pad(d.getUTCDate()) + ', ' + d.getUTCFullYear(), value: ''}];
      const isFuture = d > today, isToday = +d === +today;
      const f = function(v){ return U.formatNum(Math.round(v)); };
      if (isFuture) rows.push(future > 0 ? {text: 'Future Reviews', value: f(future)} : {text: 'No reviews due', value: ''});
      else {
        rows.push({text: 'Reviews', value: f(count)});
        if (isToday) rows.push({text: 'Today Pending', value: f(future)});
      }
      if (!isFuture && count > 0){
        components(this.o.metric).forEach(function(comp){
          if (['reviews', 'time', 'retention'].indexOf(comp[0]) >= 0) return;
          const v = compValue(comp, e);
          rows.push({text: comp[0] === 'types' ? comp[1].join(' + ') : comp[0], value: comp[0] === 'avg_time' ? (v / 1000).toFixed(1) + 's' : f(v)});
        });
      }
      if (tm > 0){ const mins = Math.trunc(tm / 60000), secs = Math.trunc((tm % 60000) / 1000); rows.push({text: 'Time', value: mins > 0 ? mins + 'm ' + secs + 's' : secs + 's'}); }
      if (count > 0) rows.push({text: 'Retention', value: U.trimNum(passed / count * 100, 1) + '%'});
      return rows;
    }
    showTip(el, c, mx, my){
      const C = this.colors;
      const key = c.s;
      if (this._tipKey !== key){
        this._tipKey = key;
        el.innerHTML = this.tooltipRows(c).map(function(r){
          return '<div class="row' + (r.header ? ' header' : '') + '"><span class="label">' + r.text + '</span>' + (r.value !== '' ? '<span class="value">' + r.value + '</span>' : '') + '</div>';
        }).join('');
        el.style.background = U.rgba(C.tooltip_bg || '#18181b', C.is_dark ? 0.91 : 0.96);
        el.style.borderColor = C.tooltip_border || 'rgba(128,128,128,0.4)';
        el.style.color = C.text_secondary || '#888';
        const h = el.querySelector('.row.header'); if (h) h.style.color = C.text_primary || '#fff';
        el.style.display = 'block';
        this._tipW = el.offsetWidth; this._tipH = el.offsetHeight;
      } else if (el.style.display === 'none') el.style.display = 'block';
      let left = mx + 15, top = my + 15;
      if (left + this._tipW > this.w) left = mx - this._tipW - 15;
      if (left < 0) left = 2;
      if (top + this._tipH > this.h) top = this.h - this._tipH - 2;
      if (top < 0) top = 2;
      DD.tipAt(el, left, top);
    }
    drawYearLabels(ctx, cs, motion){
      const o = this.o, Y = cs.Y, s = o.scale, col = this.colors.text;
      ctx.save(); ctx.beginPath(); ctx.rect(0, 0, this.w, Y.vpBottom + 0); ctx.clip();
      ctx.textAlign = 'left';
      if (!o.hide_labels && Y.blocks.length){
        const b = Y.blocks[0], seen = {};
        ctx.font = Math.max(6, Math.min(8, Math.trunc(Y.cell * 0.7))) * 4 / 3 + 'px ' + FONT_FAMILY;
        ctx.fillStyle = U.rgba(col, 1); ctx.textBaseline = 'bottom';
        for (let wk = 0; wk < 53; wk++) for (let dy = 0; dy < 7; dy++){
          const d = addDays(b.gs, wk * 7 + dy);
          if (d.getUTCFullYear() !== b.yr || seen[d.getUTCMonth()]) continue;
          seen[d.getUTCMonth()] = 1;
          ctx.fillText(MONTHS[d.getUTCMonth()], Y.startX + wk * Y.step, b.y0 - 1 * s);
        }
      }
      const x = Y.startX - Y.label + 2 * s;
      const yearPx = Math.max(7, Math.min(10, Y.cell * 0.72)) * 4 / 3;
      const totPx = Math.max(7.5, Math.min(9.5, Y.cell * 0.7)) * 4 / 3;
      const self = this;
      // while the years move (fold, gap, other years) each label slides from its old row
      // to its new one, the years that come or go fade where they are
      let rows = Y.blocks.map(function(b){ return {yr: b.yr, y0: b.y0, a: 1}; });
      if (motion){
        const F = motion.from, tt = motion.tt, shown = {};
        rows = Y.blocks.map(function(b){ shown[b.yr] = 1; return F[b.yr] != null ? {yr: b.yr, y0: F[b.yr] + (b.y0 - F[b.yr]) * tt, a: 1} : {yr: b.yr, y0: b.y0, a: tt}; });
        Object.keys(F).forEach(function(yr){ if (!shown[yr]) rows.push({yr: +yr, y0: F[yr], a: 1 - tt}); });
      }
      rows.forEach(function(b){
        if (b.a <= 0.01) return;
        ctx.save(); ctx.globalAlpha *= b.a;
        ctx.textBaseline = 'top'; ctx.fillStyle = U.rgba(col, 1);
        ctx.font = '700 ' + yearPx + 'px ' + FONT_FAMILY;
        ctx.fillText(String(b.yr), x, b.y0);
        const lines = self.yearTotalLines(b.yr);
        if (lines.length){
          ctx.font = '700 ' + totPx + 'px ' + FONT_FAMILY;
          ctx.fillStyle = U.rgba(col, 0.8);
          const lineH = Math.max(1.4 * Y.step, totPx * 1.3 + 1), rowBottom = b.y0 + 7 * Y.step - Y.sp;
          let ty = b.y0 + 1.7 * Y.step;
          lines.forEach(function(t){ if (ty + lineH * 0.8 > rowBottom) return; ctx.fillText(t, x, ty); ty += lineH; });
        }
        ctx.restore();
      });
      if (this._canFold && !Y.inLegend){
        ctx.font = '700 ' + Math.max(7, 8.5 * Math.min(1, Math.max(0.85, s))) * 4 / 3 + 'px ' + FONT_FAMILY;
        ctx.fillStyle = U.rgba(col, 0.75); ctx.textBaseline = 'middle';
        ctx.fillText(this.toggleText(), Y.startX - Y.label, Y.gridBottom + 4 * s + (Y.toggleH - 4 * s) / 2);
        this._toggleRect = {x: Y.startX - Y.label, y: Y.gridBottom + 4 * s, w: Math.min(ctx.measureText(this.toggleText()).width, 220 * s), h: Y.toggleH - 4 * s};
      }
      ctx.restore();
    }
    toggleText(){ return this._hidden ? '+ ' + this._hidden + ' older years' : 'Show fewer years'; }
    drawLabels(ctx, cs){
      const o = this.o;
      if (cs.Y){ this.drawYearLabels(ctx, cs); return; }
      if (o.hide_labels) return;
      ctx.fillStyle = U.rgba(this.colors.text, 1);
      ctx.textBaseline = 'alphabetic'; ctx.textAlign = 'left';
      if (o.mode === 'continuous'){
        const L = cs.L;
        ctx.font = Math.max(6, Math.min(8, Math.trunc(L.cell * 0.7))) * 4 / 3 + 'px ' + FONT_FAMILY;
        if (cs.clipX){ ctx.save(); ctx.beginPath(); ctx.rect(cs.clipX[0], 0, cs.clipX[1] - cs.clipX[0], this.h); ctx.clip(); }
        ctx.textBaseline = 'bottom';
        (cs.ms || []).forEach(function(e){ ctx.fillText(MONTHS[e.mo.m - 1], e.x, L.mt - 1 * o.scale); });
        if (cs.clipX) ctx.restore();
        ctx.textBaseline = 'alphabetic';
        const lx = L.startX - L.label + 2 * o.scale;
        const names = this.dayNames(L.cell);
        names.forEach(function(nm, i){ ctx.fillText(nm, Math.trunc(lx), Math.trunc(L.mt + (i * 2 + 1) * L.step + L.cell * 0.8)); });
        return;
      }
      if (cs.M){
        const M = cs.M;
        ctx.font = Math.max(6, Math.min(8, Math.trunc(M.cell * 0.7))) * 4 / 3 + 'px ' + FONT_FAMILY;
        ctx.textBaseline = 'bottom';
        M.blocks.forEach(function(b){ ctx.fillText(MONTHS[b.mo.m], b.x, b.y - 1 * o.scale); });
        ctx.textBaseline = 'alphabetic';
        const lx = M.startX - M.label + 2 * o.scale, names = this.dayNames(M.cell);
        M.rowTops.forEach(function(top){ names.forEach(function(nm, i){ ctx.fillText(nm, Math.trunc(lx), Math.trunc(top + (i * 2 + 1) * M.step + M.cell * 0.8)); }); });
        return;
      }
      const G = cs.G, step = cs.step;
      ctx.font = Math.max(6, Math.min(8, Math.trunc(G.cell * 0.7))) * 4 / 3 + 'px ' + FONT_FAMILY;
      const seen = {}, lbls = [];
      for (let wk = 0; wk < 53; wk++) for (let dy = 0; dy < 7; dy++){
        const d = addDays(cs.info.start, wk * 7 + dy);
        if (!cs.info.inRange(d)) continue;
        const P = this.gridPos(G, wk), k = d.getUTCFullYear() * 12 + d.getUTCMonth() + '|' + P.half;  // a split year names its older half's last month again
        if (seen[k]) continue; seen[k] = 1;
        if (G.split && P.col > G.cols - 2) continue;  // a month starting in a half's last week: named at the other half's start
        lbls.push({t: MONTHS[d.getUTCMonth()], col: P.col, half: P.half, top: P.top});
      }
      // a half's first name (the month going on from the other half) gives way to a month starting right after it
      ctx.textBaseline = 'bottom';
      lbls.forEach(function(L, i){
        const n = lbls[i + 1];
        if (G.split && L.col === 0 && n && n.half === L.half && n.col < 3) return;
        ctx.fillText(L.t, G.startX + L.col * step, L.top - 1 * o.scale);
      });
      ctx.textBaseline = 'alphabetic';
      const lx = G.startX - G.label + 2 * o.scale, names = this.dayNames(G.cell);
      (G.split ? [G.startY, G.startY + G.y2] : [G.startY]).forEach(function(top){
        names.forEach(function(nm, i){ ctx.fillText(nm, Math.trunc(lx), Math.trunc(top + (i * 2 + 1) * step + G.cell * 0.8)); });
      });
    }
    dayNames(cell){
      const idx = this.o.monday_first ? [1, 3, 5] : [0, 2, 4];
      const initials = (cell / this.o.scale) < 11;
      return idx.map(function(i){ const n = DAYS[i]; return initials ? n[0].toUpperCase() : n; });
    }
    drawLegend(ctx, cs, glideFrom, glideT){
      const o = this.o, h = this.legendH();
      if (h <= 0) return;
      const items = this.legendItems();
      const sc = Math.max(1, o.scale);
      const fpx = 9 * sc * 4 / 3;
      ctx.font = fpx + 'px ' + FONT_FAMILY;
      const sq = 13 * sc, gap = 5 * sc, between = 11 * sc;
      const tw = function(t){ return ctx.measureText(t).width; };
      let total = 0;
      items.forEach(function(it){ total += sq + gap + tw(it[1]) + between; });
      total -= between;
      let right = this.w - 6;
      let top = this.lh() - h;
      if (cs.Y){
        right = Math.min(right, cs.Y.startX + 53 * cs.Y.step - cs.Y.sp);
        top = Math.min(top, cs.Y.bottom + 10 * o.scale);
      } else if (o.mode === 'continuous'){
        const L = cs.L;
        right = Math.min(right, L.boxLeft + this.boxCols() * L.step + (L.months.length - 1) * L.gap - L.spacing);
      } else if (cs.M){
        right = Math.min(right, cs.M.right);
        top = Math.min(top, cs.M.bottom + 10 * o.scale);
      } else if (cs.G){
        right = Math.min(right, cs.G.startX + cs.G.cols * cs.step - cs.G.spacing);
        top = Math.min(top, cs.G.startY + cs.G.y2 + 7 * cs.step - cs.G.spacing + 10 * o.scale);
      }
      // a mode switch that moves the legend: it glides with the cells
      if (glideFrom != null && glideT != null) top = glideFrom + (top - glideFrom) * glideT;  // glideT is already eased like the cells and the card edge
      top = Math.min(top, this.vh() - h);
      let x = Math.max(4, right - total);
      this._legendTop = top; this._legendRect = {x: x - 2, y: top - 2, w: total + 4, h: h + 4};
      const y = top + (h - sq) / 2 - 1;
      const radius = (sq / 2) * (o.rounding / 100);
      ctx.textBaseline = 'middle'; ctx.textAlign = 'left';
      const hits = [], hid = this.hiddenSteps || new Set();
      items.forEach(function(it, i){
        const step = i - 1, off = step >= 0 && hid.has(step), x0 = x;
        ctx.globalAlpha = off ? 0.4 : 1;
        ctx.fillStyle = it[0];
        ctx.beginPath(); if (ctx.roundRect) ctx.roundRect(x, y, sq, sq, radius); else ctx.rect(x, y, sq, sq); ctx.fill();
        if (off){
          ctx.strokeStyle = U.rgba(this.colors.text, 1); ctx.lineWidth = 1;
          ctx.beginPath(); if (ctx.roundRect) ctx.roundRect(x + 0.5, y + 0.5, sq - 1, sq - 1, radius); else ctx.rect(x + 0.5, y + 0.5, sq - 1, sq - 1); ctx.stroke();
        }
        x += sq + gap;
        ctx.fillStyle = U.rgba(this.colors.text, 1);
        ctx.fillText(it[1], x, y + sq / 2 + 0.5);
        if (off){ const mid = Math.trunc(y + sq / 2) + 0.5; ctx.strokeStyle = U.rgba(this.colors.text, 1); ctx.beginPath(); ctx.moveTo(Math.trunc(x), mid); ctx.lineTo(Math.trunc(x + tw(it[1])), mid); ctx.stroke(); }
        ctx.globalAlpha = 1;
        x += tw(it[1]);
        if (step >= 0) hits.push({x: x0, y: y - 4, w: x - x0, h: sq + 8, step: step});
        x += between;
      }, this);
      this._legendHits = hits;
      if (cs.Y && cs.Y.inLegend){
        ctx.font = '700 ' + Math.max(7, 8.5 * Math.min(1, Math.max(0.85, o.scale))) * 4 / 3 + 'px ' + FONT_FAMILY;
        ctx.fillStyle = U.rgba(this.colors.text, 0.75); ctx.textBaseline = 'middle';
        ctx.fillText(this.toggleText(), cs.Y.startX - cs.Y.label, top + h / 2);
        this._toggleRect = {x: cs.Y.startX - cs.Y.label, y: top, w: Math.min(ctx.measureText(this.toggleText()).width, 220 * o.scale), h: h};
      }
    }
  }

  function headControls(el, chart, redraw){
    if (!el) return;
    const pills = el.querySelector('.dd-pills');
    if (!pills) return;
    pills.innerHTML = '';
    pills.classList.add('dd-hm-nav');
    pills.style.setProperty('--dd-accent-f', U.rgba((DD.theme.chart && DD.theme.chart.accent) || '#3b82f6', 40 / 255));
    const o = chart.o, mode = o.mode;
    const showCont = o.show_mode_cont !== false, show365 = o.show_mode_365 !== false, showYear = o.show_mode_year !== false, showYears = o.show_mode_years !== false;
    const CHEV = {'<': '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 18l-6-6 6-6"/></svg>',
                  '>': '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18l6-6-6-6"/></svg>'};
    function sep(){ const e = document.createElement('span'); e.className = 'dd-hm-sep'; e.textContent = '|'; pills.appendChild(e); }
    function modeBtn(label, m, wide){
      const b = document.createElement('button');
      b.className = 'dd-hm-btn' + (wide ? ' w28' : '') + (mode === m ? ' on' : '');
      b.textContent = label;
      b.addEventListener('click', function(){
        if (chart.o.mode === m) return;
        let before = null; try { before = chart.snapshotMode(); } catch (e) {}
        chart.navTr = null; chart.fade = null; chart.panTr = null; chart._panPx = 0; chart._mS = null;
        chart.o.mode = m; chart._yearOff = 0; chart._endOff = 0; chart._endShift = 0; chart._anchorKey = null; chart.o.cont_month_offset = 0; chart.hover = null;
        DD.call('set_setting', {section: 'heatmap', key: 'heatmap_mode', value: m}).catch(function(){});
        const shot = navShot(pills);
        headControls(el, chart, redraw);
        try { chart.startModeTr(before); } catch (e) { chart.modeTr = null; }
        redraw(); navGlide(pills, shot);
      });
      pills.appendChild(b);
    }
    if (showYears){
      modeBtn('YRS', 'years', true);
      // years_gap_button: next to YRS in the years view, takes out (or puts back) the space between the years; the icon
      // shows what a click does
      if (mode === 'years'){
        const FOLD = '<path d="M12 22v-6"/><path d="M12 8V2"/><path d="M4 12H2"/><path d="M10 12H8"/><path d="M16 12h-2"/><path d="M22 12h-2"/>';
        const g = document.createElement('button'); g.className = 'dd-hm-btn dd-hm-gap';
        const noGap = !!chart.o.years_no_gap;
        g.title = noGap ? 'Add space between the years' : 'Remove the space between the years';
        g.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' + FOLD +
          (noGap ? '<path d="m15 19-3 3-3-3"/><path d="m15 5-3-3-3 3"/>' : '<path d="m15 19-3-3-3 3"/><path d="m15 5-3 3-3-3"/>') + '</svg>';
        g.addEventListener('click', function(){
          const v = !chart.o.years_no_gap;
          chart.relayoutYears(function(){ chart.o.years_no_gap = v; });
          DD.call('set_heatmap', {name: 'years_no_gap', value: v}).catch(function(){});
          const shot = navShot(pills);
          headControls(el, chart, redraw); redraw(); navGlide(pills, shot);
        });
        pills.appendChild(g);
      }
      if (showCont || show365 || showYear) sep();
    }
    if (showCont) modeBtn('\u221e', 'continuous', false);
    if (showCont && show365) sep();
    if (show365) modeBtn('365', '365', true);
    if (show365 && showYear) sep(); else if (showCont && !show365 && showYear) sep();
    if (showYear) modeBtn('Y', 'year', false);
    // month_grid_button: on a narrow card in year / 365, the year in two rows (default) or the months as a grid; the
    // icon shows what a click does
    chart._hcNarrow = chart.narrowGrid();
    if (chart._hcNarrow){
      const g = document.createElement('button'); g.className = 'dd-hm-btn dd-hm-gap';
      const grid = !!chart.o.month_grid;
      g.title = grid ? 'Show the year in two rows' : 'Show the months as a grid';
      g.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
        (grid ? '<rect width="18" height="7" x="3" y="3" rx="1"/><rect width="18" height="7" x="3" y="14" rx="1"/>'
              : '<rect width="7" height="7" x="3" y="3" rx="1"/><rect width="7" height="7" x="14" y="3" rx="1"/><rect width="7" height="7" x="14" y="14" rx="1"/><rect width="7" height="7" x="3" y="14" rx="1"/>') + '</svg>';
      g.addEventListener('click', function(){
        const v = !chart.o.month_grid;
        let before = null; try { before = chart.snapshotMode(); } catch (e) {}
        chart.navTr = null; chart.fade = null; chart.hover = null;
        chart.o.month_grid = v; chart._natKey = null;
        DD.call('set_heatmap', {name: 'month_grid', value: v}).catch(function(){});
        const shot = navShot(pills);
        headControls(el, chart, redraw);
        try { chart.startModeTr(before); } catch (e) { chart.modeTr = null; }
        redraw(); navGlide(pills, shot);
      });
      pills.appendChild(g);
    }
    const gap = document.createElement('span'); gap.style.width = '4px'; pills.appendChild(gap);
    if (mode !== 'years'){
      function arrow(ch, d){
        const b = document.createElement('button'); b.className = 'dd-hm-btn dd-hm-arrow'; b.innerHTML = CHEV[ch];
        b.addEventListener('click', function(){
          const m = chart.o.mode;
          let img = null;
          if (chart.canvas.width > 2){ img = document.createElement('canvas'); img.width = chart.canvas.width; img.height = chart.canvas.height; img.getContext('2d').drawImage(chart.canvas, 0, 0); }
          chart.modeTr = null; chart.fade = null; chart.panTr = null; chart._panPx = 0; chart._mS = null;
          if (m === 'continuous') chart.o.cont_month_offset = (chart.o.cont_month_offset | 0) + d * (2 * chart.contR() + 1);
          else if (m === 'year') chart._yearOff += d;
          else if (m === '365') chart._endOff += d;
          chart.hover = null; headControls(el, chart, redraw);
          if (img) chart.startNavTr(img, d);
          redraw();
        });
        pills.appendChild(b);
      }
      arrow('<', -1);
      if (mode === 'year'){ const l = document.createElement('span'); l.className = 'dd-hm-year'; l.textContent = String(new Date().getUTCFullYear() + chart._yearOff); pills.appendChild(l); }
      arrow('>', 1);
    }
  }

  // the nav bar's buttons where they are (before a mode switch rebuilds them), keyed by what they are
  function navShot(pills){
    if (!pills) return null;
    const out = {}, n = {};
    Array.prototype.forEach.call(pills.children, function(e){
      let k = e.classList.contains('dd-hm-sep') ? 'sep' : e.classList.contains('dd-hm-arrow') ? 'arr' : e.classList.contains('dd-hm-gap') ? 'gap'
        : e.classList.contains('dd-hm-year') ? 'yr' : e.tagName === 'BUTTON' ? 'b:' + e.textContent : null;
      if (!k) return;
      n[k] = (n[k] || 0) + 1; k += '#' + n[k];
      out[k] = e.getBoundingClientRect().left; e._hmKey = k;
    });
    const hb = pills.parentNode && pills.parentNode.querySelector('.dd-hbtns');  // the "⋯" (on the left of the pills)
    if (hb) out.hb = hb.getBoundingClientRect().left;
    return out;
  }
  // a mode switch: the buttons kept glide from their old places to their new ones (the new ones fade in) with the
  // cells' move (320 ms): the bar was rebuilt at once, its buttons and its inset to the grid jumping
  function navGlide(pills, before){
    if (!pills || !before || !(DD.anim && DD.anim.on) || !pills.animate) return;
    if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    // (a glide still running is let go: the buttons start from where they are seen, their new places measured bare)
    Array.prototype.forEach.call(pills.children, function(e){ if (e.getAnimations) e.getAnimations().forEach(function(a){ a.cancel(); }); });
    const after = navShot(pills), dur = 320 * (DD.calm ? DD.calm() : 1), runs = [];
    Array.prototype.forEach.call(pills.children, function(e){
      const k = e._hmKey; if (!k || after[k] == null) return;
      if (before[k] != null){
        const dx = before[k] - after[k];
        if (Math.abs(dx) >= 0.5) runs.push(e.animate([{transform: 'translateX(' + dx + 'px)'}, {transform: 'none'}], {duration: dur, easing: 'cubic-bezier(.33,1,.68,1)'}));
      } else e.animate([{opacity: 0}, {opacity: 1}], {duration: dur, easing: 'ease-out'});
    });
    // the bar clips its overflow (.dd-head .dd-pills): a button gliding in from outside its new box (YRS when the
    // arrows go) was cut, so it shows its overflow while the glide runs
    if (runs.length && window.Promise){
      const tok = pills._hmOvf = (pills._hmOvf || 0) + 1;
      pills.style.overflow = 'visible';
      Promise.all(runs.map(function(a){ return a.finished.catch(function(){}); })).then(function(){ if (pills._hmOvf === tok) pills.style.overflow = ''; });
    }
    // the main screen's "⋯" before the pills: placed now, on their new places (no glide measured yet), it glides with them
    const card = pills.closest && pills.closest('[data-wid]');
    if (card && window.DDP && DDP.placeMore){ const run = Array.prototype.map.call(pills.children, function(e){ return e.getAnimations ? e.getAnimations() : []; });
      run.forEach(function(l){ l.forEach(function(a){ a.pause(); a.currentTime = dur; }); });  // (at their end: measured bare)
      DDP.placeMore(card);
      run.forEach(function(l){ l.forEach(function(a){ a.currentTime = 0; a.play(); }); }); }
    const hb = pills.parentNode && pills.parentNode.querySelector('.dd-hbtns');
    if (hb && before.hb != null){
      hb.getAnimations().forEach(function(a){ a.cancel(); });
      const dx = before.hb - hb.getBoundingClientRect().left;
      if (Math.abs(dx) >= 0.5) hb.animate([{translate: dx + 'px 0'}, {translate: '0 0'}], {duration: dur, easing: 'cubic-bezier(.33,1,.68,1)'});
    }
  }

  DD.registerChart('heatmap', {
    mount: function(el, ctx){
      el.innerHTML = '<div class="dd-plot"><canvas></canvas><div class="dd-tip"></div></div>';
      const plot = el.firstChild;
      const chart = new Chart(plot, ctx.data, DD.theme.chart, ctx.options || {});
      chart.anchorTo(ctx.data && ctx.data.anchor);
      const state = {last: true};
      // pinned & deep dive (_align_nav_to_grid): inset the nav bar to the grid's edges (centered grids, e.g. continuous mode)
      // (glide: the buttons slide to the new inset, as when the card's new height is known at the start of its move)
      const alignNav = function(glide){
        if (!ctx.head || !chart.w) return;
        const pills = ctx.head.querySelector('.dd-pills'); if (!pills) return;
        const ext = chart.contentXExtent(); if (!ext) return;
        const fs = !!(ctx.head.closest && ctx.head.closest('.dd-fs'));
        const rm = Math.max(0, Math.round(chart.w - ext[1]) - (fs ? 34 : 0)), v = rm ? (rm + 'px') : '';
        if (pills.style.marginRight === v) return;
        const shot = glide ? navShot(pills) : null;
        pills.style.marginRight = v;
        if (shot) navGlide(pills, shot);
      };
      // pinned: the card follows the height the heatmap asks for (mode, older years unfolded, other data). Asked
      // for the canvas's width as it is now: chart.w is the width at mount until its ResizeObserver runs, and at
      // Anki's start the card is mounted before it is laid out (a few hundred px): the first ask (setTimeout
      // below) sometimes came before that observer, and the card glided to a wrong height and back, moving the
      // widgets under it
      const notify = function(){
        alignNav();
        if (!ctx.onNatural) return;
        const live = chart.canvas.isConnected ? DD.boxOf(chart.canvas).w : 0;
        const nh = chart.naturalHeight(live > 1 ? live : (chart.w || 1));
        if (nh !== state.nat){ state.nat = nh; ctx.onNatural(nh); }
      };
      const redraw = function(){ state.last = true; DD.frame.kick(); notify(); };
      headControls(ctx.head, chart, redraw);
      const tip = plot.querySelector('.dd-tip');
      chart.canvas.addEventListener('mousemove', function(ev){
        if (chart._sbDrag) return;
        const r = chart.canvas.getBoundingClientRect(), mx = ev.clientX - r.left, my = ev.clientY - r.top;
        const onLegend = chart.legendStepAt(mx, my) !== null, onToggle = chart.o.mode === 'years' && chart.toggleHit(mx, my);
        const c = onLegend || onToggle ? null : chart.hitTest(mx, my);
        chart.canvas.style.cursor = onLegend || onToggle ? 'pointer' : 'default';  // a day opens the browser, but the cursor stays an arrow
        if (c) chart.showTip(tip, c, mx, my); else { tip.style.display = 'none'; chart._tipKey = null; }
        if ((c && chart.hover && c.s === chart.hover.s) || (!c && !chart.hover)) return;
        chart.hover = c; redraw();
      });
      let hmTouchAt = 0, hmLastDay = null, hmLastTime = 0;
      chart.canvas.addEventListener('pointerdown', function(ev){ if (ev.pointerType === 'touch') hmTouchAt = Date.now(); }, {passive: true});
      chart.canvas.addEventListener('click', function(ev){
        if (Date.now() - (chart._sbClickAt || 0) < 300) return;  // the end of a scroll bar drag
        const r = chart.canvas.getBoundingClientRect(), mx = ev.clientX - r.left, my = ev.clientY - r.top;
        const st = chart.legendStepAt(mx, my);
        if (st !== null){
          // the days of that range fade out (or back in) like a mode switch,
          // the legend staying where it is (320 ms)
          let before = null; try { before = chart.snapshotMode(); } catch (e) {}
          chart.navTr = null; chart.fade = null;
          chart.hiddenSteps = chart.hiddenSteps || new Set();
          if (chart.hiddenSteps.has(st)) chart.hiddenSteps.delete(st); else chart.hiddenSteps.add(st);
          try { if (before) chart.startModeTr(before); } catch (e) { chart.modeTr = null; }
          redraw(); return;
        }
        if (chart.o.mode === 'years' && chart.toggleHit(mx, my)){ chart.relayoutYears(function(){ chart._expanded = !chart._expanded; }); redraw(); return; }
        if (chart.o.click_browser === false) return;
        const c = chart.hitTest(mx, my);
        if (c && c.s && mx - c.x <= ((chart._cs && chart._cs.cell) || 0) && my - c.y <= ((chart._cs && chart._cs.cell) || 0)){
          if ((DD.isTouch && DD.isTouch()) || Date.now() - hmTouchAt < 800) return;
          DD.call('open_day', {date: String(c.s).slice(0, 10), deck: DD.state ? DD.state.deck : null}).catch(function(){});
        }
      });
      // the wheel scrolls the years inside the card (3 rows a notch); at an end, the page scrolls
      // (a touchpad's small steps move it as they come: each under half a pixel was let go to the page, and the years
      // never moved)
      chart.canvas.addEventListener('wheel', function(ev){
        if (chart.o.mode !== 'years' || ev.ctrlKey) return;
        const Y = chart._cs && chart._cs.Y; if (!Y || Y.maxScroll <= 0 || !ev.deltaY) return;
        const px = ev.deltaY * (ev.deltaMode === 1 ? 40 : ev.deltaMode === 2 ? Y.vpBottom : 1);
        const old = chart._scroll || 0;
        if ((px < 0 && old <= 0) || (px > 0 && old >= Y.maxScroll)) return;
        ev.preventDefault();
        chart._scroll = Math.min(Y.maxScroll, Math.max(0, old + px / 100 * Y.step * 3));
        chart.hover = null; tip.style.display = 'none'; redraw();
      }, {passive: false});
      // the scroll bar: its thumb dragged, or a press on its track brings the thumb there and drags it
      let sbDrag = null;
      chart.canvas.addEventListener('pointerdown', function(ev){
        if (chart.o.mode !== 'years' || ev.button !== 0) return;
        const sb = chart.scrollBar(chart._cs); if (!sb) return;
        const r = chart.canvas.getBoundingClientRect(), k = (chart.w || r.width) / (r.width || 1);
        const mx = (ev.clientX - r.left) * k, my = (ev.clientY - r.top) * k;
        if (mx < chart.w - 12 || my < 0 || my > sb.top + sb.track + 2) return;
        const grab = my >= sb.by && my <= sb.by + sb.bh ? my - sb.by : sb.bh / 2;
        sbDrag = {id: ev.pointerId, grab: grab, k: k, top: r.top};
        try { chart.canvas.setPointerCapture(ev.pointerId); } catch (e) {}
        ev.preventDefault(); chart._sbDrag = true; chart.hover = null; tip.style.display = 'none';
        sbMove(ev);
      });
      const sbMove = function(ev){
        if (!sbDrag || ev.pointerId !== sbDrag.id) return;
        const sb = chart.scrollBar(chart._cs); if (!sb) return;
        const my = (ev.clientY - chart.canvas.getBoundingClientRect().top) * sbDrag.k;
        const f = sb.track > sb.bh ? (my - sbDrag.grab - sb.top) / (sb.track - sb.bh) : 0;
        chart._scroll = Math.min(sb.max, Math.max(0, f * sb.max)); redraw();
      };
      chart.canvas.addEventListener('pointermove', sbMove);
      const sbEnd = function(ev){
        if (!sbDrag || ev.pointerId !== sbDrag.id) return;
        sbDrag = null; chart._sbDrag = false; chart._sbClickAt = Date.now(); redraw();
      };
      chart.canvas.addEventListener('pointerup', sbEnd);
      chart.canvas.addEventListener('pointercancel', sbEnd);
      // a phone, the continuous view: a finger drags the months sideways, as far as it goes, the nearest month
      // taking its place when let go (a flick goes on a little); the arrows stay. Up or down, the page scrolls
      let pan = null;
      const settle = function(v){
        const px = chart._panPx || 0, proj = px + Math.max(-1.5, Math.min(1.5, v)) * 180;
        const r = chart.panSettle(proj), from = r - (proj - px);
        if (Math.abs(from) < 0.5 || !(DD.anim && DD.anim.on)){ chart._panPx = 0; chart.panTr = null; }
        else { chart._panPx = from; chart.panTr = {from: from, start: null, dur: 300 * DD.speed()}; }
        state.last = true; DD.frame.kick();
      };
      chart.canvas.addEventListener('pointerdown', function(ev){
        pan = null;
        if (ev.pointerType !== 'touch' || !ev.isPrimary || chart.o.mode !== 'continuous') return;
        let base = 0;
        if (chart.panTr){ base = chart._panPx || 0; chart.panTr = null; }  // caught while it glides: held where it is
        pan = {id: ev.pointerId, x0: ev.clientX, y0: ev.clientY, on: false, base: base, s: []};
      }, {passive: true});
      chart.canvas.addEventListener('pointermove', function(ev){
        if (!pan || ev.pointerId !== pan.id) return;
        const dx = ev.clientX - pan.x0, dy = ev.clientY - pan.y0;
        if (!pan.on){
          if (Math.abs(dy) > 10 && Math.abs(dy) > Math.abs(dx)){ const b = pan.base; pan = null; if (b) settle(0); return; }
          if (Math.abs(dx) < 10) return;
          pan.on = true; pan.x0 = ev.clientX;
          chart.navTr = null; chart.modeTr = null; chart.fade = null; chart.hover = null; tip.style.display = 'none'; chart._tipKey = null;
        }
        chart._panPx = pan.base + (ev.clientX - pan.x0);
        pan.s.push([performance.now(), ev.clientX]); if (pan.s.length > 5) pan.s.shift();
        state.last = true; DD.frame.kick();
      }, {passive: true});
      const panEnd = function(ev){
        if (!pan || ev.pointerId !== pan.id) return;
        const p = pan; pan = null;
        if (!p.on){ if (p.base) settle(0); return; }
        const a = p.s[0], b = p.s[p.s.length - 1], dt = b && a ? b[0] - a[0] : 0;
        settle(dt > 0 && performance.now() - b[0] < 80 ? (b[1] - a[1]) / dt : 0);
      };
      chart.canvas.addEventListener('pointerup', panEnd);
      chart.canvas.addEventListener('pointercancel', panEnd);
      chart.canvas.addEventListener('mouseleave', function(){ tip.style.display = 'none'; chart._tipKey = null; if (chart.hover){ chart.hover = null; redraw(); } });
      // a change of data: the old picture fades into the new one (320 ms)
      function frame(now){
        if (chart.panTr){
          const T = chart.panTr; if (T.start === null) T.start = now;
          const p = Math.min(1, (now - T.start) / T.dur), e = 1 - Math.pow(1 - p, 3);
          chart._panPx = p >= 1 ? 0 : T.from * (1 - e);
          chart.draw();
          if (p < 1){ state.last = true; return true; }
          chart.panTr = null; state.last = true; return true;  // the scale may still ease (easeScale)
        }
        if (chart.modeTr){ if (chart.drawModeTr(now)){ state.last = true; return true; } chart.draw(); state.last = false; return false; }
        if (chart.navTr){ if (chart.drawNavTr(now)){ state.last = true; return true; } chart.draw(); state.last = false; return false; }
        const f = chart.fade; let needs = state.last;
        if (f){
          if (f.start === null) f.start = now;
          const t = Math.min(1, (now - f.start) / (320 * (f.k || 1)));
          chart.draw();
          if (t < 1){
            // a cross-fade as a sum (old x (1 - e) + new x e on a clear canvas): a cell the same in both keeps its
            // color and opacity the whole time (drawn one over the other, the half-transparent empty cells dimmed and
            // came back); the legend stays the new one
            const cv = chart.canvas, c = chart.ctx, a = (1 + Math.cos(Math.PI * t)) / 2;  // InOutSine (_data_transition_anim)
            if (!f.tmp || f.tmp.width !== cv.width || f.tmp.height !== cv.height){ f.tmp = document.createElement('canvas'); f.tmp.width = cv.width; f.tmp.height = cv.height; }
            const tc = f.tmp.getContext('2d'); tc.setTransform(1, 0, 0, 1, 0, 0); tc.clearRect(0, 0, cv.width, cv.height); tc.drawImage(cv, 0, 0);
            c.save(); c.setTransform(1, 0, 0, 1, 0, 0); c.clearRect(0, 0, cv.width, cv.height);
            c.globalAlpha = a; c.drawImage(f.img, 0, 0);
            c.globalCompositeOperation = 'lighter'; c.globalAlpha = 1 - a; c.drawImage(f.tmp, 0, 0);
            c.globalCompositeOperation = 'source-over'; c.globalAlpha = 1;
            const L = chart._legendRect, d = cv.width / (chart.w || 1);
            if (L && chart.o.show_legend){ c.beginPath(); c.rect(L.x * d, L.y * d, L.w * d, L.h * d); c.clip(); c.clearRect(0, 0, cv.width, cv.height); c.drawImage(f.tmp, 0, 0); }
            c.restore();
            state.last = true; return true;
          }
          chart.fade = null; state.last = false; return false;
        }
        if (needs || chart._easing) chart.draw();
        if (chart._easing){ state.last = true; return true; }
        state.last = false; return false;
      }
      // the card takes its new height during a mode switch: the cells go to their places in that height (_retarget_mode_transition)
      const retarget = function(){ if (chart.modeTr){ try { const v = chart.visuals(); chart.modeTr.b = v; chart.modeTr.lb = chart.labelsPicture(v.cs); } catch (e) { chart.modeTr = null; } } };
      const resizer = new ResizeObserver(function(){
        if (chart._resize() === false) return;
        alignNav();
        retarget();
        if (chart.navTr) chart.navTr = null;
        // a card made narrow or wide again (a phone turned, a window resized): its controls (the month grid button)
        // and the height it asks for follow at once (asked only on the next redraw, the card kept the old height
        // and cut the grid for a moment)
        if (chart.narrowGrid() !== !!chart._hcNarrow) headControls(ctx.head, chart, redraw);
        notify();
        // drawn now, before the page is painted: a resized canvas is blank until it is drawn (the card growing
        // with the years view, a space between the years taken out, showed the heatmap empty for a frame)
        state.last = true;
        try { frame(performance.now()); } catch (e) { DD.swallowed('heatmap frame', e); }
        DD.frame.kick();
      });
      DD.frame.observe(resizer, plot);
      chart.draw();
      DD.frame.add(frame);
      setTimeout(notify, 0);
      return {
        natural: function(w){ return chart.naturalHeight(w); },
        // a narrow card's layout (two rows, the month grid, fewer months, the years): the Deep Dive row takes its natural height
        narrow: function(w){ return chart.narrowGrid(w) || chart.yearsNarrow(w) || (chart.o.mode === 'continuous' && chart.contR(w) < 4); },
        // the height glide of a switch, driven by the pinned card
        heightAnim: function(lh, vh){ chart._layoutH = Math.max(1, lh); chart._visH = vh; chart._legendRides = !!chart.modeTr; retarget(); alignNav(true); state.last = true; DD.frame.kick(); },
        heightStep: function(vh){ if (chart._layoutH == null) return; chart._visH = vh; state.last = true; DD.frame.kick(); },
        heightEnd: function(){ chart._layoutH = null; chart._visH = null; chart._legendRides = false; state.last = true; DD.frame.kick(); },
        update: function(data){
          let img = null;
          const anim = ctx.animate !== false && !DD._noAnim && chart.canvas.width > 2;
          if (anim){ img = document.createElement('canvas'); img.width = chart.canvas.width; img.height = chart.canvas.height; img.getContext('2d').drawImage(chart.canvas, 0, 0); }
          let shot = null; if (anim && chart.o.mode !== 'continuous' && chart.o.mode !== 'years'){ try { shot = chart.snapshotMode(); } catch (e) {} }
          const dir = chart.anchorTo(data && data.anchor);
          if (chart.o.mode === 'years' && anim){
            // in the years view, other years (a zoom, another deck): the rows move like a fold
            // (the mode switch animation), the color fade would be cut by the change of height
            const before = (chart.yearsList() || []).join(',');
            const was = chart.data; chart.setPayload(data);
            const after = (chart.yearsList() || []).join(',');
            if (before !== after){ chart.data = was; chart.relayoutYears(function(){ chart.setPayload(data); }); state.last = true; DD.frame.kick(); notify(); return; }
            chart.data = was;
          }
          chart.setPayload(data);
          if (dir && chart.o.mode !== 'continuous'){
            // another year or another 365 days (a zoom elsewhere): the cells move and fade
            // to their new places, the labels cross-fade; the slide is for the months out of view only
            chart.navTr = null; chart.fade = null; chart.hover = null; headControls(ctx.head, chart, redraw);
            try { if (shot) chart.startModeTr(shot); } catch (e) { chart.modeTr = null; }
          } else if (dir){
            // out of what is on screen: it slides like the arrows, the new days already there (begin_navigation_transition)
            chart.modeTr = null; chart.fade = null; chart.hover = null; headControls(ctx.head, chart, redraw);
            if (img) chart.startNavTr(img, dir);
          } else if (img) chart.fade = {img: img, start: null, k: DD.calm ? DD.calm() : 1};  // 320 ms (slowed down, the deck change dragged)
          if (DD.dev) DD.trace('ANIMTRACE heatmap update: ' + (chart.modeTr ? 'mode transition' : chart.navTr ? 'slide' : chart.fade ? 'fade' : 'NO ANIMATION (noAnim=' + !!DD._noAnim + ' canvas ' + chart.canvas.width + ')'));
          state.last = true; DD.frame.kick(); notify(); },
        setOptions: function(o){ Object.assign(chart.o, o); headControls(ctx.head, chart, redraw); redraw(); notify(); },
        narrowOn: function(){ return chart.narrowOn(); },  // its right-click menu's check
        // a new theme takes the calendar to its color only when it showed the old theme's: a color of its own (a pinned
        // heatmap's own Settings, the pinned theme's custom colors) stays
        setTheme: function(){
          const old = chart.colors && chart.colors.heatmap, now = DD.theme.chart && DD.theme.chart.heatmap;
          chart.colors = DD.theme.chart;
          if (now && !chart.o.keep_color && (!chart.o.color || String(chart.o.color).toLowerCase() === String(old || '').toLowerCase())) chart.o.color = now;
          state.last = true; DD.frame.kick();
        },
        destroy: function(){ DD.frame.remove(frame); resizer.disconnect(); el.innerHTML = ''; if (ctx.head){ const p = ctx.head.querySelector('.dd-pills'); if (p) p.innerHTML = ''; } },
      };
    },
  });
})();
