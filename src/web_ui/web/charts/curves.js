// First Long-term / Short-term Forgetting Curve: how the cards were recalled after their
// first rating, one point per interval (its size: the samples in it), with the FSRS curve fitted to each first rating
// (logic.metrics.first_curves). Under the plot: the longest interval shown and the most points per rating (Max Bin
// Count); the long-term one also has an Outlier Filtering pill. These options are kept as the chart's settings.
(function(){
  'use strict';
  const DD = window.DD;
  const U = DD.cu;
  const FONT = '12px "Segoe UI",-apple-system,BlinkMacSystemFont,sans-serif';
  const NAMES = {1: 'Again', 2: 'Hard', 3: 'Good', 4: 'Easy'};
  const COLOR_KEY = {1: 'again', 2: 'hard', 3: 'good', 4: 'easy'};

  // ---- the points of a rating: outliers left out (long-term, on demand), then merged into at most maxBins ----
  // (adaptive binning, at least 1 sample a bin)
  function filterOutliers(rating, entries){
    if (!entries.length) return [];
    const total = entries.reduce(function(a, e){ return a + e.count; }, 0);
    if (total < 20) return entries.slice().sort(function(a, b){ return a.delta - b.delta; });
    const sorted = entries.slice().sort(function(a, b){ return a.count !== b.count ? a.count - b.count : b.delta - a.delta; });
    const threshold = Math.max(total * 0.05, 20), limit = rating === 4 ? 365 : 100, gone = new Set();
    let removed = 0;
    sorted.forEach(function(e){
      if (removed + e.count < threshold){ gone.add(e.delta); removed += e.count; return; }
      if (e.count < 6 || e.delta > limit){ gone.add(e.delta); removed += e.count; }
    });
    return entries.filter(function(e){ return !gone.has(e.delta); }).sort(function(a, b){ return a.delta - b.delta; });
  }
  function merge(a, b){
    const n = a.count + b.count;
    return {delta: (a.delta * a.count + b.delta * b.count) / n, success: a.success + b.success, count: n};
  }
  function binned(entries, maxBins){
    const bins = entries.slice().sort(function(a, b){ return a.delta - b.delta; });
    while (bins.length > maxBins){
      // the two closest neighbours merged first
      let at = 0, span = Infinity;
      for (let i = 0; i < bins.length - 1; i++){ const s = bins[i + 1].delta - bins[i].delta; if (s < span){ span = s; at = i; } }
      bins.splice(at, 2, merge(bins[at], bins[at + 1]));
    }
    return bins;
  }
  function recall(t, s, decay){ const f = Math.pow(0.9, -1 / decay) - 1; return Math.pow(1 + f * t / s, -decay); }
  function niceMax(v){
    if (!(v > 0)) return 1;
    const p = Math.pow(10, Math.floor(Math.log10(v))), m = v / p;
    // (steps whose quarters stay round: the axis has 4 ticks, and little room is lost past the longest interval)
    const steps = [1, 1.2, 1.6, 2, 2.4, 3, 4, 6, 8, 10];
    for (let i = 0; i < steps.length; i++) if (m <= steps[i] + 1e-9) return steps[i] * p;
    return 10 * p;
  }

  class Chart {
    constructor(plot, payload, colors, options){
      this.canvas = plot.querySelector('canvas');
      this.ctx = this.canvas.getContext('2d');
      this.colors = colors; this.options = options || {};
      this.progress = 1; this.hoverIdx = -1; this.dots = [];
      this.setPayload(payload);
      this._resize();
    }
    _resize(){ const f = DD.fitCanvas(this.canvas, this.ctx); this.w = f.w; this.h = f.h; }
    setPayload(p){
      this.payload = p || {};
      this.short = !!this.payload.short;
      let lo = Infinity, hi = 0;
      (this.payload.series || []).forEach(function(s){ (s.points || []).forEach(function(q){ lo = Math.min(lo, q[0]); hi = Math.max(hi, q[0]); }); });
      this.dmin = lo === Infinity ? (this.short ? 0.1 : 1) : lo;
      this.dmax = hi || (this.short ? 10 : 30);
      this.view();
    }
    // the points shown with the options of the moment
    view(){
      const o = this.options, maxBins = Math.max(1, Math.min(100, Number(this.payload.max_bins) || 20));
      const outl = !this.short && !!this.payload.outliers;
      this.series = (this.payload.series || []).map(function(s){
        let e = (s.points || []).map(function(q){ return {delta: q[0], success: q[1], count: q[2]}; });
        e = outl ? filterOutliers(s.rating, e) : e;
        return {rating: s.rating, stability: s.stability, n: s.n, points: binned(e, maxBins)};
      }).filter(function(s){ return s.points.length; });
      const xm = Number(this.payload.max_interval) || 0;
      this.xmax = xm > 0 ? Math.max(this.dmin, Math.min(this.dmax, xm)) : this.dmax;
      void o;
    }
    // what is drawn, in data space: the x axis' top, the fitted curves and the points (a morph blends two of these)
    model(){
      const self = this, xTop = niceMax(this.xmax);
      let top = 1;
      this.series.forEach(function(s){ s.points.forEach(function(p){ if (p.count > top) top = p.count; }); });
      const curves = [], dots = [];
      this.series.forEach(function(s){
        if (s.stability > 0) curves.push({rating: s.rating, s: s.stability, a: 1});
        s.points.forEach(function(p){
          if (p.delta > self.xmax + 1e-9) return;
          dots.push({rating: s.rating, delta: p.delta, rate: p.success / p.count, rr: 3 + 9 * Math.sqrt(Math.max(0, p.count - 1) / Math.max(1, top - 1)), p: p, a: 1});
        });
      });
      return {xTop: xTop, labelTop: xTop, curves: curves, dots: dots, ghosts: []};
    }
    // a change (another period / deck, a slider, Outlier Filtering): from what is on screen to the new picture.
    // kind 'drag': a slider being dragged (short, it follows the hand)
    change(fn, kind){
      const from = (this.morph || this.progress >= 1) && !DD._noAnim ? this.shown() : null;
      fn();
      if (!from || DD._noAnim){ this.morph = null; return; }
      const ms = kind === 'drag' ? 200 * DD.speed() : 300 * (DD.calm ? DD.calm() : 1);
      this.morph = {from: from, start: null, ms: ms};
    }
    shown(){
      const to = this.model(), mo = this.morph;
      if (!mo) return to;
      const now = performance.now();
      if (mo.start === null) mo.start = now;
      const t = Math.min(1, (now - mo.start) / Math.max(1, mo.ms));
      if (t >= 1){ this.morph = null; return to; }
      const e = 1 - Math.pow(1 - t, 3), fo = mo.from;  // OutCubic, as the other charts' morphs
      const L = function(a, b){ return a + (b - a) * e; };
      const LL = function(a, b){ return a > 0 && b > 0 ? Math.exp(L(Math.log(a), Math.log(b))) : L(a, b); };
      const out = {xTop: LL(fo.xTop, to.xTop), labelFrom: fo.labelTop, labelTop: e < 0.5 ? fo.labelTop : to.labelTop, xTo: to.labelTop, e: e, curves: [], dots: [], ghosts: []};
      // curves: a rating on both sides glides to its new stability; one that comes or goes fades
      const fc = {}, tc = {};
      fo.curves.forEach(function(c){ fc[c.rating] = c; });
      to.curves.forEach(function(c){ tc[c.rating] = c; });
      to.curves.forEach(function(c){ const o = fc[c.rating]; out.curves.push(o ? {rating: c.rating, s: LL(o.s, c.s), a: L(o.a, 1)} : {rating: c.rating, s: c.s, a: e}); });
      fo.curves.forEach(function(o){ if (!tc[o.rating] && o.a * (1 - e) > 0.01) out.curves.push({rating: o.rating, s: o.s, a: o.a * (1 - e)}); });
      // points, as bubbles: each old point goes to its nearest new one of its rating. Several going to one (bins
      // merged, another deck): the biggest becomes it, the others fly into it shrinking to nothing (absorbed, no
      // cross-fade of overlapping see-through dots). A new point no old one goes to (bins split): it buds out of its
      // nearest old point, growing from nothing. A rating with no point on the other side grows / shrinks in place.
      const lg = function(d){ return Math.log(Math.max(1e-6, d)); };
      const near = function(list, d){
        let b = null, bd = Infinity; const ld = lg(d.delta);
        list.forEach(function(x){ if (x.rating !== d.rating) return; const k = Math.abs(lg(x.delta) - ld) + Math.abs(x.rate - d.rate) * 0.05; if (k < bd){ bd = k; b = x; } });
        return b;
      };
      const groups = new Map(), lone = [];
      fo.dots.forEach(function(o){
        const n = near(to.dots, o);
        if (!n){ lone.push(o); return; }
        if (!groups.has(n)) groups.set(n, []);
        groups.get(n).push(o);
      });
      const shrink = 1 - e, fade = 1 - e * e * e;  // absorbed: solid while it flies, gone as it lands
      to.dots.forEach(function(d){
        const g = groups.get(d);
        if (g && g.length){
          let main = g[0];
          g.forEach(function(o){ if (o.rr > main.rr) main = o; });
          const cur = {rating: d.rating, delta: LL(main.delta, d.delta), rate: L(main.rate, d.rate), rr: L(main.rr, d.rr), p: d.p, a: L(main.a, 1)};
          out.dots.push(cur);
          g.forEach(function(o){
            if (o === main) return;
            out.ghosts.push({rating: o.rating, delta: LL(o.delta, d.delta), rate: L(o.rate, d.rate), rr: o.rr * shrink, a: o.a * fade});
          });
          return;
        }
        const s = near(fo.dots, d);
        if (s) out.dots.push({rating: d.rating, delta: LL(s.delta, d.delta), rate: L(s.rate, d.rate), rr: d.rr * e, p: d.p, a: 1});
        else out.dots.push({rating: d.rating, delta: d.delta, rate: d.rate, rr: d.rr * e, p: d.p, a: e});
      });
      lone.forEach(function(o){ out.ghosts.push({rating: o.rating, delta: o.delta, rate: o.rate, rr: o.rr * shrink, a: o.a * shrink}); });
      (fo.ghosts || []).forEach(function(g){ if (g.a * shrink > 0.01 && g.rr * shrink > 0.2) out.ghosts.push(Object.assign({}, g, {rr: g.rr * shrink, a: g.a * shrink})); });
      return out;
    }
    unit(v){ return this.short ? DD.t('{value} min', {value: U.trimNum(v, v < 10 ? 1 : 0)}) : DD.t('{value} d', {value: U.trimNum(v, v < 10 ? 1 : 0)}); }
    indexAt(mx, my){
      let best = -1, bd = Infinity;
      this.dots.forEach(function(d, i){ const dd = Math.hypot(mx - d.x, my - d.y); if (dd <= Math.max(9, d.r + 4) && dd < bd){ bd = dd; best = i; } });
      return best;
    }
    tipRows(i){
      const d = this.dots[i]; if (!d) return [];
      return [{header: true, text: DD.t('First rating: {rating}', {rating: DD.t(NAMES[d.rating])}), color: d.color},
        {text: DD.t('Interval'), value: this.unit(d.p.delta)},
        {text: DD.t('Recall'), value: U.trimNum(d.p.success * 100 / d.p.count, 1) + '%'},
        {text: DD.t('Samples'), value: U.formatNum(d.p.count)}];
    }
    draw(){
      const ctx = this.ctx, w = this.w, h = this.h, C = this.colors, dark = !!C.is_dark, self = this;
      ctx.clearRect(0, 0, w, h);
      // (read first: a morph also ends while the card is too small to draw, or the frames never stopped)
      const S = this.shown();
      if (!this.series.length && !this.morph) return;
      const k = U.easeOutQuart ? U.easeOutQuart(Math.max(0, Math.min(1, this.progress))) : this.progress;
      const colorOf = function(r){ return C[COLOR_KEY[r]] || '#888888'; };
      const ml = 42, mr = 16, mb = 26;
      // legend laid out in its own row(s) above the plot so it never covers points or curves
      ctx.font = '11px "Segoe UI",-apple-system,BlinkMacSystemFont,sans-serif';
      const legGap = 14, dotR = 3.5, dotGap = 5, legAvail = Math.max(80, w - ml - mr);
      const legItems = this.series.map(function(s){
        const st = s.stability > 0 ? (self.short ? DD.t('{value} min', {value: U.trimNum(s.stability, 2)}) : DD.t('{value} d', {value: U.trimNum(s.stability, 2)})) : '—';
        const txt = DD.t(NAMES[s.rating]) + ': S ' + st + ' (' + U.formatNum(s.n) + ')';
        return {rating: s.rating, color: colorOf(s.rating), txt: txt, w: dotR * 2 + dotGap + ctx.measureText(txt).width};
      });
      const legRows = [];
      let curRow = [], curW = 0;
      legItems.forEach(function(it){
        const add = curRow.length ? legGap + it.w : it.w;
        if (curRow.length && curW + add > legAvail){ legRows.push({items: curRow, w: curW}); curRow = [it]; curW = it.w; }
        else { curRow.push(it); curW += add; }
      });
      if (curRow.length) legRows.push({items: curRow, w: curW});
      const mt = 6 + legRows.length * 16 + 6;
      const pw = w - ml - mr, ph = h - mt - mb;
      if (pw < 20 || ph < 20) return;
      // what is on screen: the new picture, or a blend from the old one while a change morphs
      const xTop = S.xTop;
      const X = function(v){ return ml + pw * Math.min(1, v / xTop); }, Y = function(v){ return mt + ph * (1 - v); };
      // build dot positions first so we know which rating is hovered before drawing legend & curves
      this.dots = [];
      S.dots.forEach(function(d){
        self.dots.push({x: X(d.delta), y: Y(d.rate), r: d.rr * k, rating: d.rating, p: d.p, color: colorOf(d.rating), a: d.a});
      });
      const hovDot = (this.hoverIdx >= 0 && this.hoverIdx < this.dots.length) ? this.dots[this.hoverIdx] : null;
      const hovRating = hovDot ? hovDot.rating : null;
      // draw legend above the plot
      ctx.textBaseline = 'middle'; ctx.textAlign = 'left';
      ctx.font = '11px "Segoe UI",-apple-system,BlinkMacSystemFont,sans-serif';
      legRows.forEach(function(row, ri){
        let lx = w - mr - row.w;
        if (lx < ml) lx = ml;
        const ly = 6 + ri * 16 + 7;
        row.items.forEach(function(it){
          const dim = hovRating != null && hovRating !== it.rating;
          ctx.globalAlpha = k * (dim ? 0.45 : 1);
          ctx.fillStyle = it.color; ctx.beginPath(); ctx.arc(lx + dotR, ly, dotR, 0, Math.PI * 2); ctx.fill();
          ctx.fillStyle = (hovRating === it.rating) ? (C.text_primary || '#fff') : (C.text_secondary || '#888');
          ctx.fillText(it.txt, lx + dotR * 2 + dotGap, ly);
          lx += it.w + legGap;
        });
      });
      ctx.globalAlpha = 1;
      ctx.font = FONT; ctx.textBaseline = 'middle';
      const grid = U.parseColor(this.options.show_grid === false ? 'rgba(0,0,0,0)' : (C.grid || 'rgba(128,128,128,0.2)'));
      const axisCol = U.cssRgba(U.parseColor(C.text_secondary || '#888'), ((dark ? 175 : 215) / 255).toFixed(4));
      for (let g = 0; g <= 4; g++){
        const y = Math.trunc(Y(g / 4)) + 0.5;
        ctx.strokeStyle = U.cssRgba(grid, Math.min(1, grid.a * (g === 0 ? 2.6 : 1.5))); ctx.lineWidth = 1;
        ctx.beginPath(); ctx.moveTo(ml, y); ctx.lineTo(w - mr, y); ctx.stroke();
        ctx.fillStyle = axisCol; ctx.textAlign = 'right'; ctx.fillText((g * 25) + '%', ml - 6, y);
      }
      ctx.textAlign = 'center';
      // the interval ticks: they slide with the axis; another scale's ticks cross-fade with the old ones
      const self2 = this, xl = function(top, alpha){
        if (alpha <= 0.01) return;
        ctx.globalAlpha = alpha;
        for (let g = 1; g <= 4; g++){
          const v = top * g / 4; if (v > xTop * 1.001) continue;
          ctx.fillText(self2.unit(v), Math.min(w - mr - 14, X(v)), h - mb + 14);
        }
        ctx.globalAlpha = 1;
      };
      ctx.fillText('0', X(0), h - mb + 14);
      if (S.e != null && Math.abs(S.labelFrom - S.xTo) > 1e-9){ xl(S.labelFrom, 1 - S.e); xl(S.xTo, S.e); }
      else xl(S.labelTop, 1);
      // subtle crosshair guides for the hovered point
      if (hovDot){
        ctx.save();
        ctx.strokeStyle = U.rgba(hovDot.color, dark ? 0.28 : 0.24);
        ctx.lineWidth = 1; ctx.setLineDash([3, 3]);
        ctx.beginPath();
        ctx.moveTo(hovDot.x, mt); ctx.lineTo(hovDot.x, mt + ph);
        ctx.moveTo(ml, hovDot.y); ctx.lineTo(ml + pw, hovDot.y);
        ctx.stroke();
        ctx.restore();
      }
      // the fitted curves, drawn from the left as the chart appears
      const decay = Number(this.payload.decay) || 0.5, opac = Math.max(0, Math.min(100, this.options.chart_opacity_pct != null ? this.options.chart_opacity_pct : 100)) / 100;
      ctx.save(); ctx.beginPath(); ctx.rect(ml, mt - 2, pw * k + 1, ph + 4); ctx.clip();
      S.curves.forEach(function(c){
        const active = hovRating === c.rating, dim = hovRating != null && !active;
        ctx.strokeStyle = U.rgba(colorOf(c.rating), (active ? 1 : (dim ? 0.3 : 0.9)) * c.a);
        ctx.lineWidth = active ? 2.4 : 1.6;
        ctx.beginPath();
        for (let i = 0; i <= 200; i++){ const t = xTop * i / 200, y = Y(recall(t, c.s, decay)); if (i) ctx.lineTo(X(t), y); else ctx.moveTo(X(t), y); }
        ctx.stroke();
      });
      ctx.restore();
      // the points going away (merged into a neighbour, past the interval shown, another period): fading out
      S.ghosts.forEach(function(g){
        const dim = hovRating != null && hovRating !== g.rating, a = (dim ? 0.35 : 1) * g.a, col = colorOf(g.rating);
        if (a <= 0.01) return;
        ctx.fillStyle = U.rgba(col, 0.6 * opac * a);
        ctx.strokeStyle = U.rgba(col, opac * a); ctx.lineWidth = 1;
        ctx.beginPath(); ctx.arc(X(g.delta), Y(g.rate), Math.max(0.5, g.rr * k), 0, Math.PI * 2); ctx.fill(); ctx.stroke();
      });
      // the points (their size: the samples), grown with the intro; hovered point drawn last on top
      this.dots.forEach(function(d, i){
        if (i === self.hoverIdx) return;
        const dim = hovRating != null && hovRating !== d.rating;
        const a = (dim ? 0.35 : 1) * (d.a == null ? 1 : d.a);
        ctx.fillStyle = U.rgba(d.color, 0.6 * opac * a);
        ctx.strokeStyle = U.rgba(d.color, opac * a); ctx.lineWidth = 1;
        ctx.beginPath(); ctx.arc(d.x, d.y, Math.max(0.5, d.r), 0, Math.PI * 2); ctx.fill(); ctx.stroke();
      });
      if (hovDot){
        const hr = Math.max(2, hovDot.r + 1.5);
        ctx.save();
        ctx.fillStyle = U.rgba(hovDot.color, dark ? 0.26 : 0.2);
        ctx.beginPath(); ctx.arc(hovDot.x, hovDot.y, hr + 4.5, 0, Math.PI * 2); ctx.fill();
        ctx.fillStyle = U.rgba(U.scaleV(hovDot.color, dark ? 1.2 : 1 / 1.1), Math.min(1, 0.95 * opac));
        ctx.strokeStyle = dark ? '#ffffff' : (C.bg || '#ffffff'); ctx.lineWidth = 1.8;
        ctx.beginPath(); ctx.arc(hovDot.x, hovDot.y, hr, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
        ctx.restore();
      }
    }
  }

  function mountCurve(type){
    return {
      mount: function(el, ctx){
        el.innerHTML = '<div class="dd-plot"><canvas></canvas><div class="dd-tip"></div></div>'
          + '<div class="dd-tm dd-cv"><span class="dd-cv-l" style="font-size:11px;opacity:.75;margin:0 6px;white-space:nowrap"></span><input type="range" min="0" max="100" step="1" title="Longest interval shown">'
          + '<span class="dd-cv-l" style="font-size:11px;opacity:.75;margin:0 6px;white-space:nowrap"></span><input type="range" min="1" max="50" step="1" title="Max Bin Count"></div>';
        el.classList.add('dd-tmb');
        const plot = el.firstChild, row = plot.nextSibling, ins = row.querySelectorAll('input'), labs = row.querySelectorAll('.dd-cv-l');
        const xs = ins[0], bs = ins[1];
        const chart = new Chart(plot, ctx.data, DD.theme.chart, ctx.options || {});
        if (ctx.animate) chart.progress = 0;
        const state = {start: null, last: true};
        // a drag on the sliders is not a drag of the widget
        ['pointerdown', 'mousedown', 'touchstart', 'click'].forEach(function(ev){ row.addEventListener(ev, function(e){ e.stopPropagation(); }); });
        // the interval slider: 0..100 over the intervals of the points (log scale: most points are short)
        const toX = function(v){ const a = Math.log(Math.max(1e-3, chart.dmin)), b = Math.log(Math.max(chart.dmin * 1.0001, chart.dmax)); return Math.exp(a + (b - a) * v / 100); };
        const fromX = function(x){ const a = Math.log(Math.max(1e-3, chart.dmin)), b = Math.log(Math.max(chart.dmin * 1.0001, chart.dmax)); return Math.round(Math.max(0, Math.min(100, (Math.log(x) - a) / (b - a) * 100))); };
        function syncFill(){
          xs.style.setProperty('--p', xs.value + '%');
          bs.style.setProperty('--p', ((Number(bs.value) - 1) / 49 * 100) + '%');
        }
        function sync(){
          const p = chart.payload;
          row.hidden = !chart.series.length;
          xs.value = String(fromX(chart.xmax));
          bs.value = String(Math.max(1, Math.min(50, Number(p.max_bins) || 20)));
          syncFill();
          labs[0].textContent = '≤ ' + chart.unit(chart.xmax);
          labs[1].textContent = DD.tn('{n} bin', '{n} bins', Number(bs.value), {n: bs.value});
          const st = ctx.head && ctx.head.querySelector('.dd-stat');
          if (st){
            const n = (p.series || []).reduce(function(a, s){ return a + (Number(s.n) || 0); }, 0);
            // (all the history of the cards: the period does not change it)
            st.textContent = n ? DD.tn('{n} card', '{n} cards', n, {n: U.formatNum(n)}) + '  ·  ' + DD.t('Decay: {value}', {value: U.trimNum(Number(p.decay) || 0.5, 2)}) + '  ·  ' + DD.t('Whole history') : '';
          }
          pills();
        }
        // Outlier Filtering (long-term): a pill in the header
        function pills(){
          const pe = ctx.head && ctx.head.querySelector('.dd-pills');
          if (!pe || chart.short) return;
          let b = pe.querySelector('.dd-cv-out');
          if (!b){
            b = document.createElement('button'); b.className = 'dd-pill dd-cv-out'; b.textContent = 'Outlier Filtering';
            b.title = 'Leaves out the intervals with few samples or far out';
            b.addEventListener('click', function(e){
              e.stopPropagation();
              const on = !chart.payload.outliers;
              chart.change(function(){ chart.payload.outliers = on; chart.view(); }); sync(); redraw();
              DD.setWidgetSetting(type, 'outliers', on);
            });
            pe.appendChild(b);
          }
          b.classList.toggle('on', !!chart.payload.outliers);
        }
        function redraw(){ state.last = true; DD.frame.kick(); }
        xs.addEventListener('input', function(){ chart.change(function(){ chart.payload.max_interval = toX(Number(xs.value)); chart.view(); }, 'drag'); labs[0].textContent = '≤ ' + chart.unit(chart.xmax); syncFill(); redraw(); });
        xs.addEventListener('change', function(){ DD.setWidgetSetting(type, 'max_interval', Number(xs.value) >= 100 ? 0 : chart.xmax); });
        bs.addEventListener('input', function(){ chart.change(function(){ chart.payload.max_bins = Number(bs.value); chart.view(); }, 'drag'); labs[1].textContent = DD.tn('{n} bin', '{n} bins', Number(bs.value), {n: bs.value}); syncFill(); redraw(); });
        bs.addEventListener('change', function(){ DD.setWidgetSetting(type, 'max_bins', Number(bs.value)); });
        DD.hover.attach(plot, chart, {index: function(x, y){ return chart.indexAt(x, y); }, rows: function(i){ return chart.tipRows(i); }, redraw: redraw});
        function frame(now){
          if (chart.progress < 1){ if (state.start === null) state.start = now; chart.progress = Math.min(1, (now - state.start) / DD.intro(600)); }
          const needs = chart.progress < 1 || !!chart.morph;
          if (needs || state.last) chart.draw();
          state.last = needs;
          return needs;
        }
        const resizer = new ResizeObserver(function(){ DD.frame.resized(frame, function(){ chart._resize(); state.last = true; }); });
        DD.frame.observe(resizer, plot);
        sync();
        if (!ctx.animate) chart.draw();
        DD.frame.add(frame);
        return {
          // new data (another period / deck, an option saved): the axis, the curves and the points morph to it
          // (during the intro: the intro shows the new data, no second animation over the first)
          update: function(data){ chart.change(function(){ chart.setPayload(data); }); sync(); redraw(); },
          setOptions: function(o){ Object.assign(chart.options, o); redraw(); },
          setTheme: function(){ chart.colors = DD.theme.chart; redraw(); },
          destroy: function(){ DD.frame.remove(frame); resizer.disconnect(); el.classList.remove('dd-tmb'); el.innerHTML = ''; },
        };
      },
    };
  }
  DD.registerChart('first_forgetting', mountCurve('first_forgetting'));
  DD.registerChart('first_forgetting_short', mountCurve('first_forgetting_short'));
})();
