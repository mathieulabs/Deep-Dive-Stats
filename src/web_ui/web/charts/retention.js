// Retention: smooth success-rate lines per card type over faint review-count bars, dashed averages.
(function(){
  'use strict';
  const DD = window.DD;
  const U = DD.cu;
  const FONT = '12px "Segoe UI",-apple-system,BlinkMacSystemFont,sans-serif';
  const FONT_X = '12px "Segoe UI",-apple-system,BlinkMacSystemFont,sans-serif';
  const DATE_STEPS = [1, 2, 3, 7, 14, 28, 56, 91, 182, 364, 728, 1456];
  const KEYS = ['all', 'young', 'mature', 'true'];
  const LABELS = {all: 'All', young: 'Young', mature: 'Mature', true: 'True'};
  const COLOR_KEY = {all: 'retention', young: 'young', mature: 'mature', true: 'cram'};
  const BAR_SHARE = 0.35;

  function binSize(n, scale){
    let base;
    if (n <= 31) base = 1; else if (n <= 90) base = 2; else if (n <= 185) base = 3; else if (n <= 366) base = 7;
    else if (n <= 730) base = 14; else if (n <= 1850) base = 30; else if (n <= 3650) base = 60; else base = 90;
    const ladder = [1, 2, 3, 7, 14, 30, 60, 90];
    scale = scale || 100;
    const step = scale <= 60 ? -2 : (scale < 90 ? -1 : (scale <= 110 ? 0 : (scale <= 170 ? 1 : 2)));
    if (!step) return base;
    let pos = ladder.indexOf(base); if (pos < 0) pos = 0;
    return ladder[Math.max(0, Math.min(ladder.length - 1, pos + step))];
  }
  function fmtCompact(v){ return Math.abs(v - Math.round(v)) < 1e-6 ? U.formatNum(Math.round(v)) : U.trimNum(v, 1); }

  // Mean of the rate over the rows; active_only skips the days without reviews.
  // slopes of the smooth curve through pts (the same monotone cubic as DD.cu.smoothPath)
  function tangents(pts){
    const n = pts.length, ms = new Array(n).fill(0);
    if (n < 3) return ms;
    const last = n - 1, hs = [], ds = [];
    for (let i = 0; i < last; i++){ const hh = pts[i + 1][0] - pts[i][0]; if (hh <= 0) return new Array(n).fill(0); hs.push(hh); ds.push((pts[i + 1][1] - pts[i][1]) / hh); }
    ms[0] = ds[0]; ms[last] = ds[last - 1];
    for (let i = 1; i < last; i++){ const d0 = ds[i - 1], d1 = ds[i]; if (d0 * d1 > 0){ const h0 = hs[i - 1], h1 = hs[i]; ms[i] = 3 * (h0 + h1) / ((2 * h1 + h0) / d0 + (h1 + 2 * h0) / d1); } }
    if (ds[0] === 0 || ms[0] * ds[0] < 0) ms[0] = 0;
    if (ds[last - 1] === 0 || ms[last] * ds[last - 1] < 0) ms[last] = 0;
    return ms;
  }
  function avgRows(rows, activeOnly){
    const vals = [];
    (rows || []).forEach(function(it){
      const val = it[1] == null ? null : Number(it[1]);
      const tc = (it.length >= 3 && it[2]) ? Number(it[2][1] || 0) : null;
      const active = (tc !== null && tc > 0) || (tc === null && val !== null && val > 0);
      if (activeOnly){ if (active && val !== null) vals.push(val); }
      else vals.push(active && val !== null ? val : 0);
    });
    return vals.length ? vals.reduce(function(a, b){ return a + b; }, 0) / vals.length : null;
  }

  function display(data, opts){
    let n = 0;
    for (const k of KEYS){ if (data[k] && data[k].length){ n = data[k].length; break; } }
    let out = data;
    const bs = opts.binning ? binSize(n, (DD.settings && DD.settings.bin_scale) || 100) : 1;
    if (opts.binning && bs > 1){
      out = {};
      KEYS.forEach(function(k){
        const rows = data[k] || [];
        if (!rows.length){ out[k] = []; return; }
        const res = [];
        for (let i = 0; i < rows.length; i += bs){
          const chunk = rows.slice(i, i + bs);
          let tp = 0, tc = 0, sp = 0, cp = 0;
          chunk.forEach(function(it){
            if (it.length >= 3 && it[2]){ tp += it[2][0]; tc += it[2][1]; }
            else if (it.length >= 2 && it[1] != null){ sp += it[1]; cp++; }
          });
          const pct = tc > 0 ? tp / tc * 100 : (cp > 0 ? sp / cp : null);
          const first = String(chunk[0][0]), last = String(chunk[chunk.length - 1][0]);
          const label = first && last && first !== last ? first + ' - ' + last : first;
          res.push(tc > 0 ? [label, pct, [tp, tc]] : [label, pct]);
        }
        out[k] = res;
      });
    }
    const mr = opts.min_reviews | 0;
    if (mr > 0){
      const m = {};
      KEYS.forEach(function(k){
        m[k] = (out[k] || []).map(function(it){
          if (it.length >= 3 && it[2]){ const t = Number(it[2][1] || 0); if (t > 0 && t < mr) return [it[0], null, it[2]]; }
          return it;
        });
      });
      out = m;
    }
    return out;
  }

  class Chart {
    constructor(root, payload, colors, options){
      this.canvas = root.querySelector('canvas');
      this.ctx = this.canvas.getContext('2d');
      this.colors = colors;
      this.options = Object.assign({visible: {young: true, mature: true}, fit_to_data: false, binning: true, show_average: true,
        avg_on_active_days: true, review_bars: true, review_axis: false, rounded: true, min_reviews: 0, chart_opacity_pct: 100}, options || {});
      this.progress = 0;
      this.setPayload(payload);
      this._resize();
    }
    // the rows shown: all of them, or the zoom window [a, b) of each series
    srcData(){
      const d = (this.payload && this.payload.data) || {};
      if (!this.zoom) return d;
      const out = {}, z = this.zoom;
      KEYS.forEach(function(k){ out[k] = (d[k] || []).slice(z[0], z[1]); });
      return out;
    }
    total(){ const d = (this.payload && this.payload.data) || {}; for (const k of KEYS){ if (d[k] && d[k].length) return d[k].length; } return 0; }
    binStep(){ const n = this.zoom ? this.zoom[1] - this.zoom[0] : this.total(); return this.options.binning ? binSize(n, (DD.settings && DD.settings.bin_scale) || 100) : 1; }
    setPayload(p){ this.payload = p; this.zoom = null; this.morph = null; this.cam = null; this.real = this.disp = display(this.srcData(), this.options); }
    refresh(){ this.morph = null; this.real = this.disp = display(this.srcData(), this.options); }
    // value transition between two display models (300 ms, InOutCubic): both resampled on the union grid U0
    // (precomputed once in this.morph._prep), the gaps of each filled by a straight
    // line between its neighbours, with a mask of the real points; values glide, segments fade with the masks
    blended(t){
      const M = this.morph, a = M.from, b = this.real, o = this.options, tt = t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2, out = {};
      const prepKey = (o.rounded ? 1 : 0) | (o.avg_on_active_days ? 2 : 0);
      let P = M._prep;
      if (!P || P.key !== prepKey){
        const fill = function(vals, n){
          const mask = [], known = [];
          for (let i = 0; i < n; i++){ const v = vals[i]; const k = v != null; mask.push(k ? 1 : 0); if (k) known.push([i, +v]); }
          const f = new Array(n).fill(0);
          if (!known.length) return [f, mask];
          for (let i = 0; i <= known[0][0]; i++) f[i] = known[0][1];
          for (let j = 0; j < known.length - 1; j++){
            const [ai, av] = known[j], [bi, bv] = known[j + 1], sp = bi - ai;
            f[ai] = av; for (let k = 1; k < sp; k++) f[ai + k] = av + (bv - av) * k / sp; f[bi] = bv;
          }
          const last = known[known.length - 1]; for (let i = last[0]; i < n; i++) f[i] = last[1];
          return [f, mask];
        };
        const lenOf = function(src){ for (const k of KEYS){ if (src && src[k] && src[k].length) return src[k].length; } return 0; };
        const lenA = lenOf(a), lenB = lenOf(b);
        let U0;
        if (lenA > 1 && lenB > 1 && lenA !== lenB){
          const fr = [];
          for (let j = 0; j < lenA; j++) fr.push(j / (lenA - 1));
          for (let j = 0; j < lenB; j++) fr.push(j / (lenB - 1));
          fr.sort(function(x, y){ return x - y; });
          U0 = fr.filter(function(v, i){ return i === 0 || v - fr[i - 1] > 1e-9; });
        } else { const N0 = Math.max(lenA, lenB); U0 = []; for (let i = 0; i < N0; i++) U0.push(N0 > 1 ? i / (N0 - 1) : 0); }
        const nearestU = function(U, uj){
          let lo = 0, hi = U.length - 1;
          while (lo < hi){ const mid = (lo + hi) >> 1; if (U[mid] < uj) lo = mid + 1; else hi = mid; }
          return lo > 0 && Math.abs(U[lo - 1] - uj) < Math.abs(U[lo] - uj) ? lo - 1 : lo;
        };
        const series = {}, avgs = {};
        const ao = o.avg_on_active_days, hideK = M && M.hiding;
        KEYS.forEach(function(k){
          const nb = b[k] || [], na = a[k] || [], n = nb.length ? U0.length : 0, U = U0;
          if (!n){ series[k] = null; return; }
          const sample = function(arr){
            if (!arr.length) return new Array(n).fill(null);
            if (n === 1) return [arr[arr.length - 1][1]];
            if (arr.length === 1){ const r = new Array(n).fill(null); r[0] = arr[0][1]; return r; }
            const last = arr.length - 1, r = [], dv = r.d = [];
            let slopes = null;
            if (o.rounded){
              slopes = new Array(arr.length).fill(0);
              let s0 = -1;
              for (let j = 0; j <= arr.length; j++){
                const ok = j < arr.length && arr[j][1] != null;
                if (ok && s0 < 0) s0 = j;
                if (!ok && s0 >= 0){
                  if (j - s0 >= 3){
                    const pts = []; for (let p = s0; p < j; p++) pts.push([p, +arr[p][1]]);
                    const m = tangents(pts); for (let p = 0; p < m.length; p++) slopes[s0 + p] = m[p];
                  } else if (j - s0 === 2){
                    const sl = +arr[s0 + 1][1] - +arr[s0][1]; slopes[s0] = slopes[s0 + 1] = sl;
                  }
                  s0 = -1;
                }
              }
            }
            for (let i = 0; i < n; i++){
              const pos = U[i] * last, i0 = Math.min(last, Math.floor(pos + 1e-9)), i1 = Math.min(last, i0 + 1), fr = Math.max(0, pos - i0);
              const v0 = arr[i0][1], v1 = arr[i1][1];
              if (fr < 1e-9){ r.push(v0 == null ? null : +v0); dv.push(v0 != null && slopes ? slopes[i0] * last : null); continue; }
              if (v0 != null && v1 != null){
                if (slopes && i1 > i0){
                  const f2 = fr * fr, f3 = f2 * fr;
                  r.push((2*f3 - 3*f2 + 1) * v0 + (f3 - 2*f2 + fr) * slopes[i0] + (-2*f3 + 3*f2) * v1 + (f3 - f2) * slopes[i1]);
                  dv.push(((6*f2 - 6*fr) * v0 + (3*f2 - 4*fr + 1) * slopes[i0] + (-6*f2 + 6*fr) * v1 + (3*f2 - 2*fr) * slopes[i1]) * last);
                } else { r.push(v0 + (v1 - v0) * fr); dv.push((v1 - v0) * last); }
              } else { r.push(null); dv.push(null); }
            }
            for (let j = 0; j < arr.length; j++){
              if (arr[j][1] == null) continue;
              const prevOk = j > 0 && arr[j - 1][1] != null, nextOk = j < last && arr[j + 1][1] != null;
              if (!prevOk || !nextOk){
                const idx = nearestU(U, j / Math.max(1, last));
                if (r[idx] == null) r[idx] = +arr[j][1];
              }
            }
            return r;
          };
          const sampleCnt = function(arr){
            if (!arr.length) return new Array(n).fill(0);
            const get = function(it){ return (it && it.length >= 3 && it[2]) ? Number(it[2][1] || 0) : 0; };
            if (arr.length === n) return arr.map(get);
            if (n === 1) return [get(arr[arr.length - 1])];
            if (arr.length === 1){ const r = new Array(n).fill(0); r[0] = get(arr[0]); return r; }
            const last = arr.length - 1, r = [];
            for (let i = 0; i < n; i++){
              const pos = U[i] * last, i0 = Math.min(last, Math.floor(pos + 1e-9)), i1 = Math.min(last, i0 + 1), fr = Math.max(0, Math.min(1, pos - i0));
              r.push(get(arr[i0]) * (1 - fr) + get(arr[i1]) * fr);
            }
            return r;
          };
          const hiding = hideK === k;
          const sa = sample(na), sb = hiding ? null : sample(nb);
          const [of, om] = fill(sa, n), [nf, nm] = hiding ? [of, new Array(n).fill(0)] : fill(sb, n);
          const hadOld = om.some(Boolean);
          const slopesOf = function(sm, f){
            const d0 = (sm && sm.d) || [];
            return f.map(function(v, i){
              if (d0[i] != null) return d0[i];
              const p0 = Math.max(0, i - 1), p1 = Math.min(n - 1, i + 1);
              return p1 > p0 && U[p1] > U[p0] ? (f[p1] - f[p0]) / (U[p1] - U[p0]) : 0;
            });
          };
          const so = o.rounded ? slopesOf(sa, of) : null, sn = o.rounded ? (hiding ? so : slopesOf(sb, nf)) : null;
          const oCnt = sampleCnt(na), nCnt = sampleCnt(nb);
          const lbls = new Array(n), cands = new Array(n);
          for (let i = 0; i < n; i++){
            lbls[i] = nb[Math.min(nb.length - 1, Math.round(U[i] * (nb.length - 1)))][0];
            cands[i] = i < n - 1 && ((om[i] && om[i + 1]) || (nm[i] && nm[i + 1]));
          }
          series[k] = {n: n, U: U, of: of, om: om, nf: nf, nm: nm, hadOld: hadOld, so: so, sn: sn, oCnt: oCnt, nCnt: nCnt, lbls: lbls, cands: cands};
        });
        KEYS.forEach(function(k){
          const oa0 = avgRows(a[k], ao), na0 = (hideK === k) ? null : avgRows(b[k], ao);
          if (oa0 === null && na0 === null) return;
          avgs[k] = {oa: oa0 === null ? na0 : oa0, na: na0 === null ? oa0 : na0, oa0: oa0 !== null ? 1 : 0, na0: na0 !== null ? 1 : 0};
        });
        P = M._prep = {key: prepKey, series: series, avgs: avgs};
      }
      KEYS.forEach(function(k){
        const S = P.series[k];
        if (!S){ out[k] = []; return; }
        const n = S.n, U = S.U, of = S.of, om = S.om, nf = S.nf, nm = S.nm, hadOld = S.hadOld, so = S.so, sn = S.sn, oCnt = S.oCnt, nCnt = S.nCnt, lbls = S.lbls, cands = S.cands;
        const rows = new Array(n);
        for (let i = 0; i < n; i++){
          const v = hadOld ? (of[i] + (nf[i] - of[i]) * tt) : nf[i], pres = om[i] * (1 - tt) + nm[i] * tt;
          const oc = oCnt[i] || 0, nc = nCnt[i] || 0, cMix = oc + (nc - oc) * tt;
          const sl = so ? (hadOld ? so[i] + (sn[i] - so[i]) * tt : sn[i]) : null;
          rows[i] = [lbls[i], (om[i] || nm[i]) ? v : null, (oc || nc) ? [0, cMix] : null, pres, !!cands[i], v, om[i], nm[i], U[i], sl];
        }
        out[k] = rows;
      });
      out._avg = {}; out._avgA = {};
      Object.keys(P.avgs).forEach(function(k){
        const A = P.avgs[k];
        out._avg[k] = A.oa + (A.na - A.oa) * tt;
        out._avgA[k] = A.oa0 * (1 - tt) + A.na0 * tt;
      });
      out._morph = true; out._tt = tt; out._t = t;
      return out;
    }
    // Zoom animation of the line charts: the picture before and the picture after are
    // moved by their time windows while one fades into the other (300 ms, OutQuad).
    setZoom(a, b){
      const n = this.total();
      const cur = (this.cam && this.cam.cur) || (this.zoom ? this.zoom.slice() : [0, n]);
      let snap = null;
      const still = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      if (this.zoomAnim && !still && !DD._noAnim && !DD.noZoomAnim && this._g && this.canvas.width > 1 && this.progress >= 1){
        snap = document.createElement('canvas'); snap.width = this.canvas.width; snap.height = this.canvas.height;
        snap.getContext('2d').drawImage(this.canvas, 0, 0);
      }
      const g0 = this._g ? Object.assign({}, this._g) : null;
      this.zoom = (a == null || (a <= 0 && b >= n)) ? null : [Math.max(0, a), Math.min(n, b)];
      this.refresh();
      const w1 = this.zoom ? this.zoom.slice() : [0, n];
      this.cam = (snap && (cur[0] !== w1[0] || cur[1] !== w1[1])) ? {from: snap, g0: g0, w0: cur, w1: w1, start: null, to: null, cur: cur} : null;
    }
    camFrame(now){
      const c = this.cam, cv = this.canvas;
      if (c.start === null){
        c.start = now; this.draw();
        c.to = document.createElement('canvas'); c.to.width = cv.width; c.to.height = cv.height; c.to.getContext('2d').drawImage(cv, 0, 0);
        c.g1 = Object.assign({}, this._g);
      }
      if (c.len == null) c.len = DD.zoomLen ? DD.zoomLen(c.w0[1] - c.w0[0], c.w1[1] - c.w1[0]) : 1;
      // the shared zoom camera's clock (zoom_camera.js): a late frame plays the next step, not the whole wait
      const Z = DD.zoomCam, t = Math.min(1, Z.clock(c, now) / (300 * (DD.calm ? DD.calm() : DD.speed()) * c.len));  // the add-on's tempo, as Activity's zoom
      if (t >= 1 || c.to.width !== cv.width || c.to.height !== cv.height){ this.cam = null; this._yax = {}; this.draw(); return false; }
      const e = Z.ease ? Z.ease(t) : (1 - (1 - t) * (1 - t));
      const ctx = this.ctx, W = this.w, H = this.h, g = c.g1, g0 = c.g0 || c.g1, sc = DD.canvasScale(cv, W, H), dpr = sc[0], dpy = sc[1];
      // the window: zoom_camera's path, as the bar charts' zoom: its width glides in log space about the point that
      // stays still (straight, the scale changed slowly at a zoom in's start and rushed at its end)
      const w = Z.path(c.w0, c.w1, e); c.cur = w;
      const ph = g.mt + g.plotH;
      // the plot's margins glide from the start's to the end's
      const ml = g0.ml + (g.ml - g0.ml) * e, pw = Math.max(1, g0.plotW + (g.plotW - g0.plotW) * e);
      ctx.save(); ctx.setTransform(dpr, 0, 0, dpy, 0, 0); ctx.clearRect(0, 0, W, H);
      // the right side (the review counts' numbers): one picture fades into the other
      [[c.from, g0, 1 - e], [c.to, g, e]].forEach(function(q){
        const x0 = q[1].ml + q[1].plotW;
        ctx.save(); ctx.beginPath(); ctx.rect(x0 + 1, 0, Math.max(0, W - x0 - 1), ph + 1); ctx.clip();
        ctx.globalAlpha = q[2]; ctx.drawImage(q[0], 0, 0, W, H); ctx.restore();
      });
      // the left numbers and the dates, drawn live: the numbers count (or slide) from the start's range to the end's,
      // the dates slide with the window (they faded from one picture into the other)
      this.liveAxes(ctx, [g0.minV, g0.minV + g0.valRange], [g.minV, g.minV + g.valRange], e, c.w0, c.w1, w, g0.plotW, g.plotW, ml, pw, g.mt, g.plotH);
      // the plot: each picture sits where its own days are in the moving window
      ctx.beginPath(); ctx.rect(ml, 0, pw, ph); ctx.clip();
      const lo = w[0], hi = Math.max(w[0] + 1, w[1] - 1);
      const X = function(i){ return ml + (i - lo) / (hi - lo) * pw; };
      [[c.from, g0, c.w0, 1 - e], [c.to, g, c.w1, e]].forEach(function(q){
        const gp = q[1], wp = q[2]; if (!gp) return;
        const x0 = X(wp[0]), x1 = X(Math.max(wp[0] + 1, wp[1] - 1));
        ctx.globalAlpha = q[3];
        ctx.drawImage(q[0], gp.ml * dpr, 0, gp.plotW * dpr, (gp.mt + gp.plotH) * dpy, x0, 0, x1 - x0, gp.mt + gp.plotH);
      });
      ctx.restore();
      return true;
    }
    // the dates of the rows (the period's, not zoomed), a range's start for a binned one
    rawLabels(){
      const d = (this.payload && this.payload.data) || {};
      for (const k of KEYS){ if (d[k] && d[k].length) return d[k].map(function(it){ return String(it[0]).split(' - ')[0]; }); }
      return [];
    }
    // the date marks (as Activity's): rows a round number apart (counted back from the last row, so a day keeps its
    // mark whatever the view), about 110 px apart, for the window of rows [w0, w1) drawn plotW wide
    _dateStep(win, plotW){
      const want = Math.max(1, win[1] - 1 - win[0]) / Math.max(1, plotW) * 110;
      for (const k of DATE_STEPS) if (k >= want) return k;
      return DATE_STEPS[DATE_STEPS.length - 1];
    }
    _dateIdx(win, step, N){
      const out = [];
      let i = N - 1 - Math.floor((N - 1 - Math.ceil(win[0] - 0.5)) / step) * step;
      for (; i < win[1] && out.length < 400; i += step) if (i >= 0 && i < N) out.push(i);
      return out;
    }
    _axisInk(){ const C = this.colors, txt = U.parseColor(C.text_secondary); return U.cssRgba(txt, ((C.is_dark ? 175 : 215) / 255).toFixed(4)); }
    _fmtV(v){ return v === 0 ? '0' : (v >= 10 ? U.formatNum(Math.trunc(v)) : U.trimNum(v, 1)); }
    // the left numbers and the dates while the window moves from wa to wb (now: win) and the range from ra to rb
    liveAxes(ctx, ra, rb, e, wa, wb, win, pwa, pwb, ml, pw, mt, plotH){
      const sm = function(x){ x = Math.max(0, Math.min(1, x)); return x * x * (3 - 2 * x); };
      const lo = ra[0] + (rb[0] - ra[0]) * e, hi = ra[1] + (rb[1] - ra[1]) * e;
      ctx.save(); ctx.font = FONT; ctx.fillStyle = this._axisInk(); ctx.textAlign = 'right'; ctx.textBaseline = 'middle';
      if (DD.axisSlide && DD.axisSlide()){
        DD.slideTicks(ra[1], rb[1], hi, e, 4, plotH, {fromMin: ra[0], toMin: rb[0], curMin: lo, bottom: true, tag: 'retention zoom'}).forEach((k) => {
          ctx.globalAlpha = k.a; ctx.fillText(this._fmtV(k.v), ml - 8, Math.trunc(mt + plotH * (1 - k.f)));
        });
      } else for (let i = 0; i <= 4; i++){
        const v = lo + (hi - lo) * i / 4;
        ctx.globalAlpha = 1; ctx.fillText(i === 0 && v === 0 ? '0' : this._fmtV(v), ml - 8, Math.trunc(mt + plotH * (1 - i / 4)));
      }
      ctx.restore();
      const labs = this.rawLabels(), N = labs.length; if (!N) return;
      const a0 = win[0], a1 = Math.max(win[0] + 1, win[1] - 1), X = function(i){ return ml + (i - a0) / (a1 - a0) * pw; };
      const sa = this._dateStep(wa, pwa), sb = this._dateStep(wb, pwb);
      const A = this._dateIdx(win, sa, N), B = sa === sb ? A : this._dateIdx(win, sb, N), inA = new Set(A), inB = new Set(B), marks = [];
      A.forEach(function(i){ const kept = inB.has(i); marks.push({x: X(i), label: labs[i], a: kept ? 1 : 1 - sm(e / 0.67), p: kept ? 2 : 1 - e}); });
      B.forEach(function(i){ if (!inA.has(i)) marks.push({x: X(i), label: labs[i], a: sm((e - 0.33) / 0.67), p: e}); });
      ctx.save(); ctx.font = FONT_X; ctx.fillStyle = this._axisInk();
      DD.placeMarks(ctx, marks, null, ml, ml + pw, this.h - this._mb() + 10);
      ctx.restore();
    }
    _mb(){ return this.canvas.closest && this.canvas.closest('.ddp') ? 24 : 30; }
    _resize(){
      const f = DD.fitCanvas(this.canvas, this.ctx), w = f.w, h = f.h, dpr = f.dpr;
      this.w = w; this.h = h;
    }
    seriesColor(k){ return this.colors[COLOR_KEY[k]] || this.colors.total_line; }
    range(){
      if (!this.options.fit_to_data) return [0, 100];
      // during a data transition the axis glides from the old range to the new one: taken from the blended points it
      // went by whole steps (floor / ceil) from frame to frame, and every line shook with it
      const d = this.disp;
      if (d && d._morph && this.morph){
        const M = this.morph, b = M.rTo || (M.rTo = this.rangeOf(this.real)), t = d._tt || 0;
        // from a chart without a line (an empty day, a deck without reviews: its range is only a default) the axis is
        // the new one at once: gliding from it threw the lines far off and back
        if (M.rFrom === undefined) M.rFrom = this.points(M.from) >= 2 ? this.rangeOf(M.from) : null;
        if (M.toLine === undefined) M.toLine = this.points(this.real) >= 2;
        const a = M.rFrom || b, e = M.toLine ? b : a;  // to a chart without a line: the lines fade where they are
        if (!M.toLine && t >= 0.999) return b;
        return [a[0] + (e[0] - a[0]) * t, a[1] + (e[1] - a[1]) * t];
      }
      return this.rangeOf(d);
    }
    points(src){
      let c = 0;
      for (const k of KEYS){ if (this.options.visible[k]) ((src || {})[k] || []).forEach(function(it){ if (it[1] != null) c++; }); }
      return c;
    }
    rangeOf(src){
      if (!this.options.fit_to_data) return [0, 100];
      let lo = Infinity, hi = -Infinity;
      for (const k of KEYS){
        if (!this.options.visible[k]) continue;
        ((src || {})[k] || []).forEach(function(it){ if (it[1] != null){ lo = Math.min(lo, it[1]); hi = Math.max(hi, it[1]); } });
      }
      if (lo === Infinity) return [0, 100];
      lo = Math.floor(lo); hi = Math.ceil(hi);
      if (hi <= lo) hi = lo + 1;
      return [lo, hi];
    }
    counts(n, src){
      const c = new Array(n).fill(0);
      for (const k of KEYS){
        if (!this.options.visible[k]) continue;
        ((src || this.disp)[k] || []).slice(0, n).forEach(function(it, i){ if (it.length >= 3 && it[2]) c[i] = Math.max(c[i], Number(it[2][1] || 0)); });
      }
      return c;
    }
    draw(){
      this._avgY = {};
      const ctx = this.ctx, w = this.w, h = this.h, C = this.colors, o = this.options;
      ctx.clearRect(0, 0, w, h);
      const dark = !!C.is_dark;
      const css = U.cssRgba;
      const d = this.disp;
      let n = 0;
      for (const k of KEYS){ if (d[k] && d[k].length){ n = d[k].length; break; } }
      const rg = this.range(), minV = rg[0], maxV = rg[1], valRange = Math.max(maxV - minV, 0.001);
      ctx.font = FONT;
      const lab = function(v){ return v >= 10 ? String(Math.trunc(v)) : (Math.round(v * 10) / 10).toFixed(1); };
      const mlOf = function(r){ let lw = ctx.measureText(lab(r[1])).width; if (r[0] > 0) lw = Math.max(lw, ctx.measureText(lab(r[0])).width); return Math.max(35, Math.trunc(lw) + 12); };
      // during a data transition the margins glide from the start's widths to the end's (taken from the gliding range or
      // the counts, they would jump by a digit's width mid-way, 100 to 99 or 999 to 1000)
      const MO = d._morph && this.morph ? this.morph : null, mt0 = d._tt || 0;
      let ml = mlOf([minV, maxV]);
      if (MO && MO.rTo && o.fit_to_data){ const ra = MO.rFrom || MO.rTo, re = MO.toLine ? MO.rTo : ra; ml = Math.round(mlOf(ra) + (mlOf(re) - mlOf(ra)) * mt0); }
      // "Show Count Axis": the review counts labelled on the right, with room for them
      const AXF = '12px "Segoe UI",-apple-system,sans-serif';
      const cntLab = function(v){ v = +v; return v >= 10000 ? (Math.round(v / 100) / 10).toString().replace(/\.0$/, '') + 'k' : String(Math.round(v)); };
      let cntTop = 0;
      const axisOn = !!(o.review_bars && o.review_axis);
      if (axisOn && n > 0){ const cc = this.counts(n); cntTop = cc.length ? Math.max.apply(null, cc) : 0; }
      const mrOf = function(v){ return v > 0 ? Math.max(8, Math.ceil(ctx.measureText(cntLab(v)).width) + 16) : 8; };
      let mr = 8;
      if (axisOn && (cntTop > 0 || MO)){
        ctx.font = AXF;
        if (MO && n > 0){
          const top = function(src){ const cc = src ? this.counts(n, src) : []; return cc.length ? Math.max.apply(null, cc) : 0; }.bind(this);
          mr = Math.round(mrOf(top(MO.from)) + (mrOf(top(this.real)) - mrOf(top(MO.from))) * mt0);
        } else mr = mrOf(cntTop);
        ctx.font = FONT;
      }
      const mt = 10, mb = this.canvas.closest && this.canvas.closest('.ddp') ? 24 : 30;  // pinned: a lower band for the dates (the room under them showed)
      const plotW = w - ml - mr, plotH = h - mt - mb, bottom = mt + plotH;
      const grid = U.parseColor((this.options && this.options.show_grid === false ? 'rgba(0,0,0,0)' : C.grid)), txt = U.parseColor(C.text_secondary);
      const axisCol = css(txt, ((dark ? 175 : 215) / 255).toFixed(4));
      ctx.textBaseline = 'middle';
      if (DD.axisSlide && DD.axisSlide()){
        // Chart_Axis_Anim 'slide' (dd-core DD.slideAxis): round values at their heights on the scale of the moment, the
        // exact top written too; on a change of scale they slide, the old ones leave and the new ones come
        const fmtV = (v) => this._fmtV(v);
        // a change of the data (it knows the start and end ranges and its progress): the values slide with the lines
        // (the axis' own 220 ms fades ran apart from the lines' change); else the axis' own fades (series shown / hidden)
        const MR = d._morph && this.morph && this.morph.rTo && o.fit_to_data ? this.morph : null;
        let ticks;
        if (MR){
          const ra = MR.rFrom || MR.rTo, rb = MR.toLine ? MR.rTo : ra;
          ticks = DD.slideTicks(ra[1], rb[1], maxV, d._tt || 0, 4, plotH, {fromMin: ra[0], toMin: rb[0], curMin: minV, bottom: true, tag: 'retention'});
          this._yax = {};
        } else ticks = DD.slideAxis(this._yax || (this._yax = {}), minV, maxV, {px: plotH, top: true, bottom: true, redraw: () => this.draw()});
        ticks.forEach((k) => {
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
        const v = minV + (maxV - minV) * i / 4;
        ctx.fillStyle = axisCol; ctx.textAlign = 'right';
        ctx.fillText(i === 0 && v === 0 ? '0' : (v >= 10 ? U.formatNum(Math.trunc(v)) : U.trimNum(v, 1)), ml - 8, Math.trunc(y));
      }
      // the dates: marks a round number of rows apart (as the zoom draws them, liveAxes: they slide while it zooms).
      // During a change of the data the old dates fade out, then the new ones fade in (the same ones stay)
      const labelsOf = function(dd){ for (const k of KEYS){ if (dd && dd[k] && dd[k].length) return dd[k].map(function(it){ return String(it[0]).split(' - ')[0]; }); } return []; };
      const sm = function(x){ x = Math.max(0, Math.min(1, x)); return x * x * (3 - 2 * x); };
      const ly = h - mb + 10;
      const marksOf = (labels, win, alpha, p) => {
        const N = labels.length; if (!N || alpha <= 0.003) return [];
        const a0 = win[0], a1 = Math.max(win[0] + 1, win[1] - 1);
        return this._dateIdx(win, this._dateStep(win, plotW), N).map(function(i){ return {x: ml + (i - a0) / (a1 - a0) * plotW, label: labels[i], a: alpha, p: p, key: labels[i]}; });
      };
      const raw = this.rawLabels(), nowM = marksOf(raw, this.zoom || [0, raw.length], 1, 1);
      let xm = nowM;
      if (d._morph && this.morph && this.morph.from){
        const oldL = (this.morph.oldLabels && this.morph.oldLabels.length) ? this.morph.oldLabels : labelsOf(this.morph.from);
        const tl = Math.max(0, Math.min(1, d._t != null ? d._t : d._tt));  // the time itself, as Activity's dates
        const oldM = marksOf(oldL, [0, oldL.length], 1, 1);
        const same = function(m, list){ return list.some(function(q){ return q.key === m.key && Math.abs(q.x - m.x) < 1; }); };
        xm = oldM.map(function(m){ const k = same(m, nowM); return Object.assign(m, {a: k ? 1 : 1 - sm(tl / 0.35), p: k ? 2 : 1 - tl}); })
          .concat(nowM.filter(function(m){ return !same(m, oldM); }).map(function(m){ return Object.assign(m, {a: sm((tl - 0.3) / 0.45), p: tl}); }));
      }
      ctx.save(); ctx.font = FONT_X; ctx.fillStyle = axisCol;
      DD.placeMarks(ctx, xm, null, ml, ml + plotW, ly);
      ctx.restore();
      if (n === 0) return;
      const lineK = (this.options.line_opacity_pct != null ? this.options.line_opacity_pct : 80) / 100;
      const bgc = C.bg || (dark ? '#000000' : '#ffffff');
      const halo = dark ? U.scaleV(bgc, 1 / 1.6) : bgc;
      // average lines
      if (o.show_average){
        KEYS.forEach(function(k){
          const isHiding = MO && MO.hiding === k;
          if (!o.visible[k] && !isHiding) return;
          const avg = (d._avg && d._avg[k] !== undefined) ? d._avg[k] : avgRows(this.srcData()[k], o.avg_on_active_days);
          if (avg === null) return;
          const aa = (d._avgA && d._avgA[k] !== undefined) ? d._avgA[k] : 1;
          if (aa <= 0.01) return;
          const y = mt + plotH - Math.max(0, (avg - minV) / valRange) * plotH;
          const col = this.seriesColor(k);
          ctx.save();
          ctx.setLineDash([3, 3]); ctx.lineCap = 'butt';
          const hv = !!(this.hoverAvg && this.hoverAvg[k]);
          this._avgY = this._avgY || {}; this._avgY[k] = y;
          ctx.strokeStyle = U.rgba(halo, 90 / 255 * lineK * aa); ctx.lineWidth = hv ? 2.7 : 2.3;
          ctx.beginPath(); ctx.moveTo(ml, y); ctx.lineTo(w - mr, y); ctx.stroke();
          const lc = dark ? U.scaleV(col, 1.35) : U.scaleV(col, 100 / 125);
          ctx.strokeStyle = U.rgba(lc, Math.round((hv ? 235 : 175) * lineK) / 255 * aa); ctx.lineWidth = hv ? 1.5 : 1.1;
          ctx.beginPath(); ctx.moveTo(ml, y); ctx.lineTo(w - mr, y); ctx.stroke();
          ctx.restore();
        }, this);
      }
      // clip to the reveal progress
      const t = Math.max(0, Math.min(1, this.progress));
      const reveal = 1 - Math.pow(1 - t, 3);
      ctx.save();
      ctx.beginPath(); ctx.rect(0, 0, Math.trunc(w * reveal), h); ctx.clip();
      const xStep = n > 1 ? plotW / (n - 1) : 0;
      this._geo = {ml: ml, xStep: xStep, mt: mt, plotH: plotH, minV: minV, valRange: valRange, n: n, morph: !!d._morph};
      // review bars
      if (o.review_bars){
        const ink = U.parseColor(C.text), barMax = plotH * BAR_SHARE;
        const drawBarRatios = function(ratios, alpha){
          const bn = ratios.length;
          if (!bn || alpha <= 0.005) return;
          const bStep = bn > 1 ? plotW / (bn - 1) : 0;
          const half = bn > 1 ? Math.max(0.75, bStep * 0.35) : 6;
          ctx.fillStyle = css(ink, (55 * alpha / 255).toFixed(4));
          for (let i = 0; i < bn; i++){
            const f = ratios[i]; if (!(f > 0)) continue;
            const x = ml + i * bStep;
            const x0 = Math.max(ml, x - half), x1 = Math.min(ml + plotW, x + half);
            if (x1 <= x0) continue;
            const bh = f * barMax;
            if (bh < 0.25) continue;
            const y0 = bottom - bh;
            ctx.beginPath();
            if (o.rounded && x1 - x0 >= 3){
              const r = Math.max(0, Math.min(3, (x1 - x0) / 2, bh));
              ctx.moveTo(x0, bottom); ctx.lineTo(x0, y0 + r); ctx.quadraticCurveTo(x0, y0, x0 + r, y0);
              ctx.lineTo(x1 - r, y0); ctx.quadraticCurveTo(x1, y0, x1, y0 + r); ctx.lineTo(x1, bottom); ctx.closePath();
            } else ctx.rect(x0, y0, x1 - x0, bh);
            ctx.fill();
          }
        };
        const toRatios = function(c, tp){ return tp > 0 ? c.map(function(v){ return Math.max(0, Math.min(1, v / tp)); }) : c.map(function(){ return 0; }); };
        const lenOf = function(src){ for (const k of KEYS){ if (src && src[k] && src[k].length) return src[k].length; } return 0; };
        const newN = MO ? lenOf(this.real) : n;
        const cnt = this.counts(newN, MO ? this.real : this.disp);
        let top = Math.max.apply(null, cnt);
        let oldN = newN;
        if (MO){
          oldN = MO.barRatios ? MO.barRatios.length : lenOf(MO.from);
          const maxOf = function(src){
            let m = 0;
            for (const k of KEYS){
              if (!o.visible[k]) continue;
              ((src || {})[k] || []).forEach(function(it){ if (it && it.length >= 3 && it[2]) m = Math.max(m, Number(it[2][1] || 0)); });
            }
            return m;
          };
          if (MO.cFrom === undefined) MO.cFrom = maxOf(MO.from);
          if (MO.cTo === undefined) MO.cTo = maxOf(this.real);
          top = (MO.cFrom > 0 && MO.cTo > 0) ? (MO.cFrom + (MO.cTo - MO.cFrom) * mt0) : Math.max(MO.cFrom, MO.cTo, top);
        }
        if (MO && oldN > 0 && oldN !== newN){
          // different bin count (e.g. 33 -> 26): cross-fade old and new bar grids smoothly instead of snapping bar count
          const rOld = MO.barRatios || toRatios(this.counts(oldN, MO.from), MO.cFrom);
          const rNew = toRatios(this.counts(newN, this.real), MO.cTo);
          drawBarRatios(rOld, 1 - mt0);
          drawBarRatios(rNew, mt0);
          this._lastBars = {ratios: mt0 < 0.5 ? rOld : rNew, top: top};
        } else if (MO && oldN === newN){
          // same bin count: interpolate normalized bar heights directly so toggling All/Young/Mature never dips
          const rOld = MO.barRatios || toRatios(this.counts(newN, MO.from), MO.cFrom);
          const rNew = toRatios(this.counts(newN, this.real), MO.cTo);
          const rMix = rNew.map(function(v, i){ return (rOld[i] || 0) + (v - (rOld[i] || 0)) * mt0; });
          drawBarRatios(rMix, 1);
          this._lastBars = {ratios: rMix, top: top};
        } else if (top > 0){
          const rNow = toRatios(cnt, top);
          drawBarRatios(rNow, 1);
          this._lastBars = {ratios: rNow, top: top};
        } else {
          this._lastBars = {ratios: new Array(newN).fill(0), top: 0};
        }
        if (top > 0 && axisOn){  // axis labels: half and top of the tallest bar
          ctx.save(); ctx.font = AXF; ctx.fillStyle = css(ink, (150 / 255).toFixed(4)); ctx.textAlign = 'left'; ctx.textBaseline = 'middle';
          [top / 2, top].forEach(function(v){ ctx.fillText(cntLab(v), ml + plotW + 6, bottom - v / top * barMax); });
          ctx.restore();
        }
      }
      // series
      const opac = Math.max(0, Math.min(100, o.chart_opacity_pct)) / 100;
      const drawStillSeries = (src, alpha) => {
        if (!src || alpha <= 0.005) return;
        KEYS.forEach(function(k){
          if (!o.visible[k] || !src[k] || !src[k].length) return;
          const col = this.seriesColor(k), sn = src[k].length, sx = sn > 1 ? plotW / (sn - 1) : 0;
          const vals = src[k].map(function(it){ return it[1]; });
          const runs = []; let cur = null; const iso = [];
          vals.forEach(function(v, i){
            if (v == null){ cur = null; return; }
            const p = [ml + i * sx, Math.max(mt, Math.min(mt + plotH, mt + plotH - (v - minV) / valRange * plotH))];
            if (!cur){ cur = []; runs.push(cur); }
            cur.push(p);
            const hl = i > 0 && vals[i - 1] != null, hr = i < vals.length - 1 && vals[i + 1] != null;
            if (!hl && !hr) iso.push(p);
          });
          const a = opac * alpha;
          const gr = ctx.createLinearGradient(0, mt, 0, mt + plotH);
          gr.addColorStop(0, U.rgba(col, 40 * a / 255)); gr.addColorStop(1, U.rgba(col, 0));
          runs.forEach(function(run){
            ctx.beginPath();
            if (o.rounded && run.length > 1) U.smoothPath(ctx, run);
            else { ctx.moveTo(run[0][0], run[0][1]); for (let i = 1; i < run.length; i++) ctx.lineTo(run[i][0], run[i][1]); }
            ctx.lineTo(run[run.length - 1][0], bottom); ctx.lineTo(run[0][0], bottom); ctx.closePath();
            ctx.fillStyle = gr; ctx.fill();
          });
          ctx.lineWidth = 1.5; ctx.lineJoin = 'round'; ctx.lineCap = 'round';
          ctx.strokeStyle = U.rgba(col, a);
          runs.forEach(function(run){
            if (run.length < 2) return;
            ctx.beginPath();
            if (o.rounded) U.smoothPath(ctx, run);
            else { ctx.moveTo(run[0][0], run[0][1]); for (let i = 1; i < run.length; i++) ctx.lineTo(run[i][0], run[i][1]); }
            ctx.stroke();
          });
          ctx.fillStyle = U.rgba(col, a);
          iso.forEach(function(p){ ctx.beginPath(); ctx.arc(p[0], p[1], 1.5, 0, Math.PI * 2); ctx.fill(); });
        }, this);
      };
      if (!d._morph){
        drawStillSeries(d, 1);
      } else KEYS.forEach(function(k){
        if ((!o.visible[k] && !(MO && MO.hiding === k)) || !d[k] || !d[k].length) return;
        const col = this.seriesColor(k);
        if (d._morph){
          // during a data transition each segment is drawn with the presence of its ends
          const it = d[k], P = it.map(function(r, i){ return [r[8] != null ? ml + r[8] * plotW : ml + i * xStep, Math.max(mt, Math.min(mt + plotH, mt + plotH - (r[5] - minV) / valRange * plotH))]; });  // kept in the plot: a point from below the axis (an empty side, a rate under its minimum) came up from under the chart
          ctx.lineWidth = 1.5; ctx.lineJoin = 'round'; ctx.lineCap = 'round';
          // rounded look kept while morphing: each segment is the piece of the smooth curve through all the points
          // (the morph draws the round curves, sampled finely enough, not straight segments)
          // the curve's slopes as the still chart draws them: each stretch of days with data rounded on its own (a day
          // next to a day without data ends its stretch); those of the old stretches glide into those of the new ones
          // (taken over every point, a day by a gap was rounded otherwise, and took its shape at once at the end)
          const runMs = function(mi){
            const out = new Array(P.length).fill(0);
            let s0 = -1;
            for (let i = 0; i <= P.length; i++){
              const on = i < P.length && it[i][mi];
              if (on && s0 < 0) s0 = i;
              if (!on && s0 >= 0){ if (i - s0 >= 3){ const m = tangents(P.slice(s0, i)); for (let j = 0; j < m.length; j++) out[s0 + j] = m[j]; } else if (i - s0 === 2){ const sl = (P[s0 + 1][1] - P[s0][1]) / Math.max(1e-6, P[s0 + 1][0] - P[s0][0]); out[s0] = out[s0 + 1] = sl; } s0 = -1; }
            }
            return out;
          };
          const tt0 = d._tt != null ? d._tt : 1;
          // the slopes of the still curves carried by the points (a piece of a cubic drawn from its ends' values and
          // slopes is that cubic: the first and last frames are the still curves, with any number of points)
          const ms = !o.rounded ? null : (it.length && it[0][9] != null) ? it.map(function(r){ return -r[9] * plotH / valRange / plotW; })
            : (function(){ const a = runMs(6), b = runMs(7); return a.map(function(v, i){ return v + (b[i] - v) * tt0; }); })();  // as smoothPath when still
          const seg = function(i){
            if (!ms){ ctx.lineTo(P[i + 1][0], P[i + 1][1]); return; }
            const h3 = (P[i + 1][0] - P[i][0]) / 3;
            ctx.bezierCurveTo(P[i][0] + h3, P[i][1] + ms[i] * h3, P[i + 1][0] - h3, P[i + 1][1] - ms[i + 1] * h3, P[i + 1][0], P[i + 1][1]);
          };
          // batch consecutive segments of matching alpha into a single continuous path so gradient fills never show vertical seams
          let i = 0;
          while (i < it.length - 1){
            if (!it[i][4]){ i++; continue; }
            const sa = Math.max(0, Math.min(1, Math.min(it[i][3], it[i + 1][3])));
            if (sa <= 0.001){ i++; continue; }
            let j = i + 1;
            while (j < it.length - 1 && it[j][4]){
              const sb = Math.max(0, Math.min(1, Math.min(it[j][3], it[j + 1][3])));
              if (Math.abs(sb - sa) > 0.02) break;
              j++;
            }
            const g2 = ctx.createLinearGradient(0, mt, 0, mt + plotH);
            g2.addColorStop(0, U.rgba(col, 40 * opac * sa / 255)); g2.addColorStop(1, U.rgba(col, 0));
            ctx.beginPath(); ctx.moveTo(P[i][0], bottom); ctx.lineTo(P[i][0], P[i][1]);
            for (let s = i; s < j; s++) seg(s);
            ctx.lineTo(P[j][0], bottom); ctx.closePath();
            ctx.fillStyle = g2; ctx.fill();
            ctx.beginPath(); ctx.moveTo(P[i][0], P[i][1]);
            for (let s = i; s < j; s++) seg(s);
            ctx.strokeStyle = U.rgba(col, opac * sa); ctx.stroke();
            i = j;
          }
          // a day alone between days without data is a dot when still: the dots of the old side fade out and those of
          // the new side fade in with the lines (they came at once at the end; a stretch shrunk to one day turns into
          // its dot as its segments fade)
          const isoAt = function(mi, i){ return !!it[i][mi] && !(i > 0 && it[i - 1][mi]) && !(i < it.length - 1 && it[i + 1][mi]); };
          for (let i = 0; i < it.length; i++){
            const a = (isoAt(6, i) ? 1 - tt0 : 0) + (isoAt(7, i) ? tt0 : 0);
            if (a <= 0.01) continue;
            ctx.beginPath(); ctx.arc(P[i][0], P[i][1], 1.5, 0, Math.PI * 2); ctx.fillStyle = U.rgba(col, opac * a); ctx.fill();
          }
          return;
        }
        const vals = d[k].map(function(it){ return it[1]; });
        const runs = []; let cur = null; const iso = [];
        vals.forEach(function(v, i){
          if (v == null){ cur = null; return; }
          const p = [ml + i * xStep, mt + plotH - (v - minV) / valRange * plotH];
          if (!cur){ cur = []; runs.push(cur); }
          cur.push(p);
          const hl = i > 0 && vals[i - 1] != null, hr = i < vals.length - 1 && vals[i + 1] != null;
          if (!hl && !hr) iso.push(p);
        });
        const gr = ctx.createLinearGradient(0, mt, 0, mt + plotH);
        gr.addColorStop(0, U.rgba(col, 40 * opac / 255)); gr.addColorStop(1, U.rgba(col, 0));
        runs.forEach(function(run){
          ctx.beginPath();
          if (o.rounded && run.length > 1) U.smoothPath(ctx, run);
          else { ctx.moveTo(run[0][0], run[0][1]); for (let i = 1; i < run.length; i++) ctx.lineTo(run[i][0], run[i][1]); }
          ctx.lineTo(run[run.length - 1][0], bottom); ctx.lineTo(run[0][0], bottom); ctx.closePath();
          ctx.fillStyle = gr; ctx.fill();
        });
        ctx.lineWidth = 1.5; ctx.lineJoin = 'round'; ctx.lineCap = 'round';
        ctx.strokeStyle = U.rgba(col, opac);
        runs.forEach(function(run){
          if (run.length < 2) return;
          ctx.beginPath();
          if (o.rounded) U.smoothPath(ctx, run);
          else { ctx.moveTo(run[0][0], run[0][1]); for (let i = 1; i < run.length; i++) ctx.lineTo(run[i][0], run[i][1]); }
          ctx.stroke();
        });
        ctx.fillStyle = U.rgba(col, opac);
        iso.forEach(function(p){ ctx.beginPath(); ctx.arc(p[0], p[1], 1.5, 0, Math.PI * 2); ctx.fill(); });
      }, this);
      ctx.restore();
      this._g = {ml: ml, plotW: plotW, mt: mt, plotH: plotH, n: n, minV: minV, valRange: valRange, xStep: xStep};
      if (this.sel){
        const x1 = Math.max(ml, Math.min(this.sel[0], this.sel[1])), x2 = Math.min(ml + plotW, Math.max(this.sel[0], this.sel[1]));
        if (x2 > x1){
          const acc = U.parseColor(C.accent || '#3b82f6');
          ctx.save();
          ctx.fillStyle = U.cssRgba(acc, 0.08); ctx.fillRect(x1, mt, x2 - x1, plotH);
          ctx.strokeStyle = U.cssRgba(acc, 0.78); ctx.lineWidth = 1.5; ctx.strokeRect(x1, mt, x2 - x1, plotH);
          ctx.restore();
        }
      }
      const hi = this.hoverIdx;
      if (hi != null && hi >= 0 && hi < n){
        const x = n > 1 ? ml + hi * xStep : ml;
        ctx.save();
        ctx.strokeStyle = U.rgba(C.text_secondary || C.text, 0.5); ctx.lineWidth = 1;
        ctx.beginPath(); ctx.moveTo(x, mt); ctx.lineTo(x, mt + plotH); ctx.stroke();
        KEYS.forEach(function(k){
          if (!o.visible[k] || !d[k] || hi >= d[k].length) return;
          const v = d[k][hi][1]; if (v == null) return;
          const y = mt + plotH - (v - minV) / valRange * plotH;
          ctx.fillStyle = this.seriesColor(k);
          ctx.strokeStyle = U.rgba(dark ? '#ffffff' : (C.bg || '#ffffff'), dark ? 230 / 255 : 210 / 255); ctx.lineWidth = 1.5;
          ctx.beginPath(); ctx.arc(x, y, 4, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
        }, this);
        ctx.restore();
      }
    }
    indexAt(mx){
      const g = this._g; if (!g || g.plotW <= 0 || g.n === 0) return -1;
      const x = mx - g.ml;
      let i = g.n > 1 ? Math.trunc(x / g.plotW * (g.n - 1) + 0.5) : 0;
      return Math.max(0, Math.min(g.n - 1, i));
    }
    tooltipHtml(i){
      const d = this.disp, o = this.options, rows = [];
      let label = '';
      for (const k of KEYS){ if (d[k] && d[k].length){ label = String(d[k][i] ? d[k][i][0] : ''); break; } }
      rows.push('<div class="row header"><span class="label">' + label + '</span></div>');
      KEYS.forEach(function(k){
        if (!o.visible[k] || !d[k] || i >= d[k].length) return;
        const it = d[k][i], v = it[1], hasC = it.length >= 3 && it[2];
        if (v == null && !(hasC && it[2][1])) return;
        let txt = v == null ? 'too few reviews' : fmtCompact(v) + '%';
        if (hasC) txt += ' (' + U.formatNum(it[2][0]) + '/' + U.formatNum(it[2][1]) + ')';
        rows.push('<div class="row"><span class="swatch" style="background:' + this.seriesColor(k) + '"></span><span class="label">' + LABELS[k] + '</span><span class="value">' + txt + '</span></div>');
      }, this);
      return rows.join('');
    }
  }

  function head(el, payload, chart){
    if (!el) return;
    const o = chart.options;
    const st = el.querySelector('.dd-stat');
    if (st){
      const parts = [];
      KEYS.forEach(function(k){
        if (!o.visible[k]) return;
        const v = avgRows(chart.srcData()[k], o.avg_on_active_days);
        if (v !== null && v >= 0) parts.push(DD.t('{name} Avg: {value}%', {name: DD.t(LABELS[k]), value: fmtCompact(v)}));
      });
      st.textContent = parts.join('  ·  ');
    }
    const pillsEl = el.querySelector('.dd-pills');
    if (!pillsEl) return;
    pillsEl.innerHTML = '';
    KEYS.forEach(function(k){
      const b = document.createElement('button');
      const on = !!o.visible[k];
      b.className = 'dd-pill' + (on ? ' on' : '');
      b.dataset.grp = 'series';  // the series stay together in a narrow header (dd-core.js fit)
      b.textContent = LABELS[k];
      const col = chart.seriesColor(k);
      // a pill in the series color: its text in the color
      // (55 % when off), a 16 % tint (12 % light) and a 45 % border when on, the hairline border when off, bold
      const dark = !!(DD.theme && DD.theme.is_dark);
      b.style.borderColor = on ? U.rgba(col, 0.45) : (dark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.10)');
      b.style.color = U.rgba(col, on ? 1 : 0.55);
      b.style.background = on ? U.rgba(col, dark ? 0.16 : 0.12) : 'transparent';
      b.style.fontWeight = '700';
      b.addEventListener('click', function(){
        const prevDisp = chart.disp, prevRange = chart.rangeOf(prevDisp), prevBars = chart._lastBars, turningOn = !chart.options.visible[k];
        const vis = Object.assign({}, chart.options.visible); vis[k] = turningOn;
        chart.options.visible = vis;
        if (chart.refresh) chart.refresh();
        if (!DD._noAnim && chart.progress >= 1 && prevDisp){
          const from = {};
          KEYS.forEach(function(sk){ from[sk] = (sk === k && turningOn) ? [] : (prevDisp[sk] || []); });
          chart.morph = {from: from, start: null, k: 0.75 * (DD.speed ? DD.speed() : 1), rFrom: prevRange,
            hiding: turningOn ? null : k,
            barRatios: prevBars ? prevBars.ratios.slice() : undefined, cFrom: prevBars ? prevBars.top : undefined};
        }
        head(el, chart.payload, chart);
        if (chart.requestDraw) chart.requestDraw();
        DD.call('set_setting', {section: 'retention', key: 'visibility', value: vis}).catch(function(){});
      });
      pillsEl.appendChild(b);
    });
  }

  DD.registerChart('retention', {
    mount: function(el, ctx){
      el.innerHTML = '<div class="dd-plot"><canvas></canvas><div class="dd-tip"></div></div>';
      const plot = el.firstChild;
      plot._ddBrowse = function(){
        const i = chart.hoverIdx; if (i == null || i < 0) return null;
        const d = chart.disp || {}; let label = '';
        for (const k of KEYS){ if (d[k] && d[k][i]){ label = String(d[k][i][0]); break; } }
        return label ? {kind: 'reviewed', label: label} : null;
      };
      const chart = new Chart(plot, ctx.data, DD.theme.chart, ctx.options || {}); Object.defineProperty(chart, 'zoomAnim', {get: function(){ return ctx.animate !== false; }});  // read when zooming (a chart shown at once animates later)
      head(ctx.head, ctx.data, chart);
      if (!ctx.animate) chart.progress = 1;
      const state = {start: null, last: true};
      chart.requestDraw = function(){ state.last = true; DD.frame.kick(); };
      const tip = plot.querySelector('.dd-tip');
      chart.canvas.addEventListener('mousemove', function(ev){
        // selecting a zone to zoom: no tooltip, no hover marker (as the other charts)
        if (drag){
          tip.style.display = 'none'; chart._tipIdx = null; showAvgLabels([]); chart.hoverAvg = {};
          if (chart.hoverIdx != null && chart.hoverIdx !== -1){ chart.hoverIdx = -1; state.last = true; DD.frame.kick(); }
          return;
        }
        const r = chart.canvas.getBoundingClientRect(), mx = ev.clientX - r.left, my = ev.clientY - r.top;
        const g = chart._g, inside = g && mx >= g.ml - 1 && mx <= g.ml + g.plotW + 1;
        const idx = inside ? chart.indexAt(mx) : -1;
        if (idx >= 0){
          const C = chart.colors;
          if (chart._tipIdx !== idx){
            chart._tipIdx = idx;
            tip.innerHTML = chart.tooltipHtml(idx);
            tip.style.background = U.rgba(C.tooltip_bg || '#18181b', C.is_dark ? 0.91 : 0.96);
            tip.style.borderColor = C.tooltip_border || 'rgba(128,128,128,0.4)';
            tip.style.color = C.text_secondary || '#888';
            const hd = tip.querySelector('.row.header'); if (hd) hd.style.color = C.text_primary || '#fff';
            tip.style.display = 'block'; chart._tw = tip.offsetWidth; chart._th = tip.offsetHeight;
          } else if (tip.style.display === 'none') tip.style.display = 'block';
          let left = mx + 15, top = my + 15;
          if (left + chart._tw > chart.w) left = mx - chart._tw - 15;
          if (left < 0) left = 2;
          if (top + chart._th > chart.h) top = chart.h - chart._th - 2;
          if (top < 0) top = 2;
          DD.tipAt(tip, left, top);
        } else { tip.style.display = 'none'; chart._tipIdx = null; }
        const g2 = chart._g; let achanged = false; const labels = [];
        chart.hoverAvg = chart.hoverAvg || {};
        KEYS.forEach(function(k){
          const ya = chart._avgY && chart._avgY[k];
          let on = false;
          if (ya != null && g2){
            const thr = chart.hoverAvg[k] ? 14 : 10;
            on = mx >= 0 && mx < chart.w && my >= g2.mt && my <= g2.mt + g2.plotH && Math.abs(my - ya) < thr;
          }
          if (on !== !!chart.hoverAvg[k]){ chart.hoverAvg[k] = on; achanged = true; }
          if (on) labels.push(k);
        });
        showAvgLabels(labels);
        if (achanged || idx !== chart.hoverIdx){ chart.hoverIdx = idx; state.last = true; DD.frame.kick(); }
      });
      const avgLabels = {};
      function showAvgLabels(keys){
        const C = chart.colors, g = chart._g;
        KEYS.forEach(function(k){ if (avgLabels[k]) avgLabels[k].style.display = 'none'; });
        let last = -100;
        keys.slice().sort(function(a, b){ return (avgRows(chart.srcData()[b], chart.options.avg_on_active_days) || 0) - (avgRows(chart.srcData()[a], chart.options.avg_on_active_days) || 0); }).forEach(function(k){
          const v = avgRows(chart.srcData()[k], chart.options.avg_on_active_days) || 0;
          let el2 = avgLabels[k];
          if (!el2){ el2 = avgLabels[k] = document.createElement('div'); el2.className = 'dd-avg-label'; plot.appendChild(el2); }
          el2.textContent = DD.t('avg: {value}%', {value: fmtCompact(v)});
          el2.style.background = U.rgba(C.tooltip_bg || '#18181b', C.is_dark ? 0.91 : 0.96);
          el2.style.borderColor = C.tooltip_border || 'rgba(128,128,128,0.4)';
          el2.style.color = chart.seriesColor(k);
          el2.style.display = 'block';
          let y = Math.trunc(chart._avgY[k]);
          if (last !== -100 && Math.abs(y - last) < 22) y = last + 22;
          last = y;
          el2.style.top = (y - 10) + 'px';
          el2.style.left = Math.max(2, g.ml - 5 - el2.offsetWidth) + 'px';
        });
      }
      // zoom: drag a zone, Ctrl+wheel, Shift+wheel to slide, double-click to reset
      chart.canvas.style.cursor = 'default';
      let drag = null;
      function absAt(mx){ const g = chart._g; const i = chart.indexAt(mx); return (chart.zoom ? chart.zoom[0] : 0) + i * chart.binStep(); }
      function zoomTo(a, b){
        chart.setZoom(a, b); head(ctx.head, chart.payload, chart); state.last = true; DD.frame.kick();
        if (inst.zoom.bar) inst.zoom.bar();
      }
      function emit(){ if (inst.zoom.onChange) inst.zoom.onChange(chart.zoom ? chart.zoom.slice() : null); }
      // the wheel (Ctrl: zoom, Shift: pan) moves the view at once
      function zoomNow(a, b, then){ const prev = DD._noAnim; DD._noAnim = true; try { zoomTo(a, b); if (then) then(); } finally { DD._noAnim = prev; } }  // the linked charts at once too
      chart.canvas.addEventListener('mousedown', function(e){
        if (e.button !== 0) return;
        const r = chart.canvas.getBoundingClientRect(), x = e.clientX - r.left, g = chart._g;
        if (!g || x < g.ml || x > g.ml + g.plotW) return;
        drag = {x0: x}; chart.sel = [x, x]; tip.style.display = 'none'; chart._tipIdx = null; chart.hoverIdx = -1;
      });
      const onMove = function(e){
        if (!drag) return;
        const r = chart.canvas.getBoundingClientRect(), g = chart._g;
        chart.sel = [drag.x0, Math.max(g.ml, Math.min(g.ml + g.plotW, e.clientX - r.left))];
        state.last = true; DD.frame.kick();
      };
      const onUp = function(){
        if (!drag) return;
        const sel = chart.sel; drag = null; chart.sel = null; state.last = true; DD.frame.kick();
        if (!sel || Math.abs(sel[1] - sel[0]) < 6) return;
        const lo = Math.min(sel[0], sel[1]), hi = Math.max(sel[0], sel[1]);
        const a = absAt(lo), step = chart.binStep();
        const b = Math.min(chart.total(), absAt(hi) + step);
        if (b - a >= 2){ zoomTo(a, b); emit(); }
      };
      window.addEventListener('mousemove', onMove);
      window.addEventListener('mouseup', onUp);
      chart.canvas.addEventListener('wheel', function(e){
        const n = chart.total(); if (!n) return;
        if (e.shiftKey && chart.zoom){
          e.preventDefault(); e.stopPropagation();
          const span = chart.zoom[1] - chart.zoom[0], st = Math.max(1, Math.round(span * 0.1)) * (e.deltaY < 0 ? -1 : 1);
          let a = chart.zoom[0] + st, b = a + span; if (a < 0){ a = 0; b = span; } if (b > n){ b = n; a = n - span; }
          zoomNow(a, b, emit); return;
        }
        if (!(e.ctrlKey || e.metaKey)) return;
        e.preventDefault(); e.stopPropagation();
        const cur = chart.zoom || [0, n], span = cur[1] - cur[0];
        if (e.deltaY > 0 && span >= n){ if (inst.zoom.onOutLimit) inst.zoom.onOutLimit(); return; }  // zoom_out_limit
        const c = absAt(e.clientX - chart.canvas.getBoundingClientRect().left);
        let ns = e.deltaY < 0 ? Math.max(3, Math.round(span * 0.85)) : Math.min(n, Math.max(span + 1, Math.round(span / 0.85)));
        if (ns === span) return;
        const ratio = span > 0 ? (c - cur[0]) / span : 0.5;
        let a = Math.round(c - ratio * ns), b = a + ns;
        if (a < 0){ a = 0; b = ns; } if (b > n){ b = n; a = Math.max(0, n - ns); }
        zoomNow(a, b, emit);
      }, {passive: false});
      chart.canvas.addEventListener('mouseleave', function(){ showAvgLabels([]); chart.hoverAvg = {}; state.last = true; DD.frame.kick(); tip.style.display = 'none'; chart._tipIdx = null; if (chart.hoverIdx != null && chart.hoverIdx !== -1){ chart.hoverIdx = -1; state.last = true; DD.frame.kick(); } });
      // dev trace (ANIMTRACE retention): where each line's points are drawn, frame to frame; a point that moves a lot
      // in one frame, and above all at the end of a transition (the last frame of it against the still chart)
      function geoSig(){
        const g = chart._geo, d = chart.disp; if (!g || !d) return null;
        const ys = {};
        KEYS.forEach(function(k){
          if (!chart.options.visible[k] || !d[k]) return;
          ys[k] = d[k].map(function(r){ const v = g.morph ? r[5] : r[1]; return v == null ? null : g.mt + g.plotH - (v - g.minV) / g.valRange * g.plotH; });
        });
        return {g: g, ys: ys};
      }
      let trPrev = null, trWas = false, trStart = null, trFrames = 0;
      function trCheck(ending){
        if (!DD.dev) return;
        const cur = geoSig(); if (!cur) return;
        if (!trWas && chart.morph){ trStart = cur; trFrames = 0; }
        trFrames++;
        if (ending && trStart){
          // how far the lines went over the whole transition (0: nothing moved, as if not animated)
          let mv = 0; const vis = [];
          Object.keys(cur.ys).forEach(function(k){
            const a = trStart.ys[k] || [], b = cur.ys[k]; let n = 0;
            for (let i = 0; i < b.length; i++){ if (b[i] != null) n++; if (a[i] != null && b[i] != null) mv = Math.max(mv, Math.abs(a[i] - b[i])); }
            vis.push(k + ' ' + n);
          });
          DD.trace('ANIMTRACE retention morph over ' + trFrames + ' frames: points went up to ' + mv.toFixed(1) + 'px | first frame ' + trStart.g.n + ' points, last ' + cur.g.n + ' | drawn ' + vis.join(', '));
          trStart = null;
        }
        const p = trPrev;
        if (p && (ending || chart.morph)){
          let mx = 0, at = '';
          Object.keys(cur.ys).forEach(function(k){
            const a = p.ys[k] || [], b = cur.ys[k];
            for (let i = 0; i < Math.min(a.length, b.length); i++){ if (a[i] == null || b[i] == null) continue; const dd = Math.abs(a[i] - b[i]); if (dd > mx){ mx = dd; at = k + ' #' + i + ' y ' + a[i].toFixed(1) + '->' + b[i].toFixed(1); } }
          });
          const axis = Math.abs(p.g.minV - cur.g.minV) > 1e-6 || Math.abs(p.g.valRange - cur.g.valRange) > 1e-6;
          if (ending && (mx > 1.5 || p.g.n !== cur.g.n || axis)) DD.trace('ANIMTRACE retention END JUMP: points ' + p.g.n + ' -> ' + cur.g.n + ', axis ' + p.g.minV.toFixed(1) + '+' + p.g.valRange.toFixed(1) + ' -> ' + cur.g.minV.toFixed(1) + '+' + cur.g.valRange.toFixed(1) + (mx > 1.5 ? ', most moved ' + mx.toFixed(1) + 'px (' + at + ')' : ''));
          else if (!ending && mx > 14) DD.trace('ANIMTRACE retention morph step ' + mx.toFixed(1) + 'px (' + at + ')');
        }
        trPrev = cur;
      }
      function frame(now){
        // its intro not played yet (it waited out of view) and new data came meanwhile: the intro alone shows it
        // (the change's morph ran with it, a second animation over the first)
        if (chart.progress < 1 && state.start === null && (chart.morph)){ if (DD.dev) DD.trace('ANIMTRACE retention intro not played yet: its morph dropped, the intro shows the new data'); chart.morph = null; chart.fadeOut = null; }
        if (chart.progress < 1){ if (state.start === null) state.start = now; chart.progress = Math.min(1, (now - state.start) / DD.intro(600)); }
        let mo = false;
        if (chart.morph){
          const m = chart.morph; if (m.start === null) m.start = now;
          const t = Math.min(1, (now - m.start) / (300 * (m.k || 1)));
          if (t >= 1){ chart.morph = null; chart.disp = chart.real; } else { chart.disp = chart.blended(t); mo = true; }
        }
        if (chart.cam && chart.progress >= 1 && !mo){ if (chart.camFrame(now)){ state.last = true; return true; } }
        if (chart.fadeOut){
          const F = chart.fadeOut; if (F.start === null) F.start = now;
          const t = Math.min(1, (now - F.start) / (300 * (F.k || 1))), e = 1 - Math.pow(1 - t, 3);
          chart.draw();
          if (t < 1 && F.img.width === chart.canvas.width && F.img.height === chart.canvas.height){
            const c = chart.ctx; c.save(); c.setTransform(1, 0, 0, 1, 0, 0); c.globalAlpha = 1 - e; c.drawImage(F.img, 0, 0); c.restore();
            state.last = true; return true;
          }
          chart.fadeOut = null; state.last = false; return false;
        }
        const needs = chart.progress < 1 || mo;
        if (needs || state.last){ chart.draw(); if (mo || trWas) trCheck(!mo && trWas); trWas = mo; }
        state.last = needs;
        return needs;
      }
      const resizer = new ResizeObserver(function(){ DD.frame.resized(frame, function(){ chart._resize(); state.last = true; }); });
      DD.frame.observe(resizer, plot);
      if (!ctx.animate) chart.draw();
      DD.frame.add(frame);
      const inst = {
        update: function(data){
          const old = (chart.morph && chart.disp) ? chart.disp : chart.real, had = old && KEYS.some(function(k){ return old[k] && old[k].length; });
          const oldRawLabels = chart.rawLabels();
          const shown = chart.progress >= 1, live = ctx.animate && !DD._noAnim;
          // to an empty deck: the lines fade out over the empty chart (a picture of them, 300 ms)
          let snap = null;
          if (live && had && shown && chart.canvas.width > 1){ snap = document.createElement('canvas'); snap.width = chart.canvas.width; snap.height = chart.canvas.height; snap.getContext('2d').drawImage(chart.canvas, 0, 0); }
          const oldPay = chart.payload, running = !!chart.morph;
          chart.setPayload(data);
          const hasNew = KEYS.some(function(k){ return chart.real[k] && chart.real[k].length; });
          chart.fadeOut = null;
          // another deck's range on other days (rows_on_new_days): the old rows put on the new days first, so each
          // point glides on its own day (sampled point by point, the whole line slid by a day)
          let from = old;
          const RT = {shared: '-', from: 'screen'};  // dev trace
          try {
            const od = (oldPay && oldPay.data) || {}, nd = (data && data.data) || {};
            const k0 = KEYS.filter(function(k){ return (od[k] || []).length && (nd[k] || []).length; })[0];
            if (had && !running && k0 && (String(od[k0][0][0]) !== String(nd[k0][0][0]) || String(od[k0][od[k0].length - 1][0]) !== String(nd[k0][nd[k0].length - 1][0]))){
              const al = {}; let shared = 0;
              KEYS.forEach(function(k){
                const by = {}; (od[k] || []).forEach(function(r){ by[String(r[0])] = r; });
                al[k] = (nd[k] || []).map(function(r){ const o = by[String(r[0])]; if (o){ shared++; return o; } return [r[0], null]; });
              });
              // only when most of the new days were shown before and most of the old days are still there (another
              // deck over the same period); otherwise the lines on screen morph into the new ones, resampled
              const tot = KEYS.reduce(function(a, k){ return a + (nd[k] || []).length; }, 0), totOld = KEYS.reduce(function(a, k){ return a + (od[k] || []).length; }, 0);
              // (nearly the same days only, a range a day or two off: on fewer shared days the old lines would be cut
              // and stretched at the first frame, a jump)
              if (shared && shared >= 0.9 * tot && shared >= 0.9 * totOld) from = display(al, chart.options);
              RT.shared = shared + '/' + tot + ' new, ' + totOld + ' old'; RT.from = from === old ? 'screen' : 'old rows on the new days';
            }
          } catch (e) { from = old; }
          if (ctx.animate && !had && !shown){ chart.progress = 0; state.start = null; }  // the very first data: the intro
          // from an empty deck too, the lines rise and fade in from nothing
          else if (live && hasNew && (had || shown)) chart.morph = {from: had ? from : {}, oldLabels: oldRawLabels, start: null, k: DD.calm ? DD.calm() : 1};
          else if (snap && !hasNew) chart.fadeOut = {img: snap, start: null, k: DD.calm ? DD.calm() : 1};
          if (DD.dev){
            const cnt = function(dd){ return KEYS.map(function(k){ return k + ' ' + ((dd && dd[k]) || []).filter(function(r){ return r && r[1] != null; }).length; }).join(', '); };
            DD.trace('ANIMTRACE retention data: points ' + cnt(old) + ' -> ' + cnt(chart.real) + ' | days shared ' + RT.shared + ' | morph from ' + RT.from + ' | live=' + live + ' had=' + !!had + ' shown=' + shown + ' running=' + running + ' noAnim=' + !!DD._noAnim + ' k=' + (DD.calm ? DD.calm() : 1));
          }
          if (DD.dev) DD.trace('ANIMTRACE retention update: ' + (chart.morph ? 'morph' : chart.fadeOut ? 'fade out' : chart.progress < 1 ? 'intro' : 'NO ANIMATION (noAnim=' + !!DD._noAnim + ' had=' + !!had + ' running=' + running + ')'));
          head(ctx.head, data, chart); state.last = true; DD.frame.kick(); if (inst.zoom.bar) inst.zoom.bar(); },
        setOptions: function(o){ Object.assign(chart.options, o); chart.refresh(); head(ctx.head, chart.payload, chart); state.last = true; DD.frame.kick(); },
        setTheme: function(){ chart.colors = DD.theme.chart; head(ctx.head, chart.payload, chart); state.last = true; DD.frame.kick(); },
        destroy: function(){ DD.frame.remove(frame); resizer.disconnect(); window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp); el.innerHTML = ''; if (ctx.head){ const st = ctx.head.querySelector('.dd-stat'); if (st) st.textContent = ''; const p = ctx.head.querySelector('.dd-pills'); if (p) p.innerHTML = ''; } },
      };
      inst.zoom = {
        count: function(){ return chart.total(); },
        label: function(i){ const d = (chart.payload && chart.payload.data) || {}; for (const k of KEYS){ if (d[k] && d[k][i]) return String(d[k][i][0]); } return null; },
        get: function(){ return chart.zoom ? chart.zoom.slice() : null; },
        set: function(a, b){ zoomTo(a, b); },
        onChange: null, onOutLimit: null,
        picture: function(){
          chart.cam = null; chart.morph = null; chart.progress = 1; chart.draw();
          const c = document.createElement('canvas'); c.width = chart.canvas.width; c.height = chart.canvas.height; c.getContext('2d').drawImage(chart.canvas, 0, 0);
          const g = chart._g || {ml: 0, plotW: chart.w, mt: 0, plotH: chart.h - 30};
          return {img: c, ml: g.ml, mr: chart.w - g.ml - g.plotW, ph: g.mt + g.plotH};
        },
        snap: function(){
          const c = document.createElement('canvas'); c.width = chart.canvas.width; c.height = chart.canvas.height; c.getContext('2d').drawImage(chart.canvas, 0, 0);
          const g = chart._g || {ml: 0, plotW: chart.w, mt: 0, plotH: chart.h - 30};
          return {img: c, ml: g.ml, mr: chart.w - g.ml - g.plotW, ph: g.mt + g.plotH};
        },
        canvas: chart.canvas,
        // adaptive zoom: other rows shown over range (null = all), the lines glide from what is shown
        swap: function(data, range){
          const old = (chart.morph && chart.disp) ? chart.disp : chart.real;
          chart.setPayload(data);
          const n = chart.total();
          if (range && !(range[0] <= 0 && range[1] >= n)){ chart.zoom = [Math.max(0, range[0]), Math.min(n, range[1])]; chart.refresh(); }
          if (!DD._noAnim && old && KEYS.some(function(k){ return old[k] && old[k].length; })) chart.morph = {from: old, start: null, k: 1};
          head(ctx.head, data, chart); state.last = true; DD.frame.kick(); if (inst.zoom.bar) inst.zoom.bar();
        },
      };
      if (DD.zoomBar) DD.zoomBar(plot, inst.zoom);
      return inst;
    },
  });
})();
