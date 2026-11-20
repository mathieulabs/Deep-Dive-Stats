// The zoom camera of the bar charts, shared by the chart engines: for 300 ms the
// chart is drawn live on a window of days that moves from the start view to the end one (zooming about the point
// that stays still), the axis gliding like a camera; the bars keep the start bin size, then split out of their
// parents (or merge into them) to the end one. The engine keeps its own look: it gives the bars of a bin
// (row(r0, r1)) and paints them (paint), and draws its axes and labels from the camera's state.
//
// Two levels:
//  - the pieces, for an engine that lays out its own bars (Activity: its bins, anchors and pixel snapping):
//    clock, path, split + mix (the bars' split or merge and the layers it makes), composite (the layers mixed),
//    edge (a bar at the plot's side), glide (the running total's base), lerpLog, sm
//  - the whole camera, built on them, for an engine that gives its bars by days (Future Due):
//      const cam = DD.zoomCam.create({a, b, binA, binB, ma, mb, ...});   // windows [d0, d1) in days
//      in the frame: if (cam.step(now)){ ...axes from cam.s...; cam.bars(ctx, G, paint); cam.cumPoints(G) ... }
//
// A binning is the bars of one view: DD.zoomCam.grid(k, lo, hi) (bins of k days on the grid of day 0, those at the
// data's ends cut), or DD.zoomCam.list(ranges, k, kOf) (the bins a chart drew, side by side whatever their days: a warp
// takes their days to even slots, so the camera's first and last frames are that chart exactly; kOf(i): bin i's own
// size when they are not all of k days, as Future Due's backlog and days ahead). A bar's height is its count for the
// bin size gliding at its days from the start view's to the end one's (kAt(d)): the start's bars as their chart
// drew them at the start, the end's at the end.
(function(){
  'use strict';
  const DD = window.DD;
  const sm = function(x){ x = Math.max(0, Math.min(1, x)); return x * x * (3 - 2 * x); };
  const ease = function(t){ return sm(t); };
  const lerpLog = function(a, b, e){ return Math.exp(Math.log(a) + (Math.log(b) - Math.log(a)) * e); };

  // An animation's clock: the time it has played, a frame counting 34 ms at most (a busy page's late first frames
  // play the next step, not the whole wait)
  function clock(o, now){
    if (o.start === null || o.el == null){ if (o.start === null) o.start = now; o.el = 0; o.last = now; }
    else if (now > o.last){ o.el += Math.min(now - o.last, 34); o.last = now; }
    return o.el;
  }

  // the window at e: its width glides in log space about the point that stays still
  function path(A, B, e){
    const a0 = A[0], a1 = A[1], b0 = B[0], b1 = B[1], wa = a1 - a0, wb = b1 - b0;
    if (wa <= 0 || wb <= 0) return [b0, b1];
    if (Math.abs(wb - wa) < 1e-6 * Math.max(wa, wb)) return [a0 + (b0 - a0) * e, a1 + (b1 - a1) * e];
    const ww = lerpLog(wa, wb, e), pp = (a0 * wb - b0 * wa) / (wb - wa), v0 = pp - (pp - a0) * ww / wa;
    return [v0, v0 + ww];
  }

  // The bars' split or merge between the bin sizes ka and kb, for windows A -> B
  // seen span days wide on a plot plotW px wide, at the zoom's time t (eased: e). st keeps the split's start
  // (st.tSplit). null: one size. wf: the view's share of the way to the fine bars; wsp: the fine bars' place and
  // width, from tiles on their parent (0) to their own (1); hsp: their height, from their parent's to their own.
  // Past the start the fine bars come out of their coarse parent bar (same place, width and height at first, then
  // their own), never faded in at their own place; the coarse bars only fade into them at the very start of the split.
  // The split takes a third of the zoom at least: led by the view's width alone, which shrinks fastest at the start,
  // it would be over in a few frames. Merging back, the same the
  // other way.
  function split(st, ka, kb, A, B, t, e, span, plotW){
    if (ka === kb) return null;
    // Zooming out / reset zoom (fine -> coarse): synchronized physical merge.
    // Heights level out (0.05..0.50) slightly ahead of horizontal gathering (0.08..0.55) so bars are already
    // flat right as they touch (no jagged comb), then hand off to solid coarse bars (0.50..0.62).
    if (ka < kb){
      const kf = Math.min(ka, kb);
      const finePx = Math.max(50, plotW) * kf / Math.max(1e-6, span);
      const hsp = 1 - sm((t - 0.05) / 0.45);
      const wsp = 1 - sm((t - 0.08) / 0.47);
      // hand off to solid coarse bars once merged, or earlier if fine bars shrink under ~1.8 px (avoids drawing 500+ slivers)
      const handoff = Math.min(1 - sm((t - 0.50) / 0.12), sm((finePx - 0.9) / 1.1));
      return {wf: handoff, wsp: wsp, hsp: hsp, merge: true};
    }
    const kf = Math.min(ka, kb);
    let wf;
    { const plotPx = Math.max(50, plotW), mid = plotPx * kf / 3;
      const small = Math.min(A[1] - A[0], B[1] - B[0]), large = Math.max(A[1] - A[0], B[1] - B[0]);
      let hi = Math.min(large, Math.max(small, mid * 1.8)), lo = Math.min(hi, Math.max(small, hi / 6));
      if (hi <= lo * 1.05){ lo = small; hi = large; }
      wf = span <= lo ? 1 : span >= hi ? 0 : sm((Math.log(hi) - Math.log(span)) / Math.max(1e-9, Math.log(hi) - Math.log(lo)));
      const teq = 1 - Math.sqrt(1 - Math.min(1, e)); wf = Math.min(wf, sm((teq - 0.04) / 0.71)); }
    let wsp = sm((wf - 0.2) / 0.8), hsp;
    if (wsp > 0 && st.tSplit == null) st.tSplit = t;
    if (st.tSplit != null) wsp = Math.min(wsp, sm((t - st.tSplit) / Math.max(0.03, Math.min(0.35, (1 - st.tSplit) * 0.9))));
    else wsp = 0;
    // the heights go on to the zoom's end: a bin half full under its parent's average rose to the top of the chart
    // with the split, fast however long it took
    hsp = st.tSplit != null ? Math.min(wsp, sm((t - st.tSplit) / Math.max(0.03, (1 - st.tSplit) * 0.97))) : 0;
    return {wf: wf, wsp: wsp, hsp: hsp};
  }
  // the layers of a split (split's result): [{fine, w: weight, split: the fine bars drawn out of their parents}]
  function mix(sp){
    if (sp.merge){
      if (sp.wsp >= 0.999 && sp.hsp >= 0.999) return [{fine: true, w: 1}];
      if (sp.wf <= 0.002) return [{fine: false, w: 1}];
      return (sp.wf < 0.998 ? [{fine: false, w: 1 - sp.wf}] : []).concat([{fine: true, w: sp.wf, split: true}]);
    }
    if (sp.wf >= 1 && sp.wsp >= 1 && sp.hsp >= 0.999) return [{fine: true, w: 1}];
    if (sp.wf <= 0 && sp.wsp <= 0 && sp.hsp <= 0.001) return [{fine: false, w: 1}];
    const gF = sm(Math.max(sp.wf, sp.wsp, sp.hsp) / 0.2);
    return (gF < 1 ? [{fine: false, w: 1 - gF}] : []).concat([{fine: true, w: gF, split: true}]);
  }
  // the layers (live: [[..., weight, ...]]) drawn by draw(g, layer): one alone right on the chart, else mixed on a
  // clear surface first (Plus composition), then laid on the chart: a bar in both layers keeps its
  // colour and opacity (no dip, no over-bright edge where they overlap). st keeps the surfaces
  function composite(st, ctx, cv, dpr, dpy, live, draw){
    if (live.length === 1 && live[0][1] >= 0.998){ draw(ctx, live[0]); return; }
    if (!live.length) return;
    const mk = function(key){
      const cvs = st[key] || (st[key] = document.createElement('canvas'));
      if (cvs.width !== cv.width || cvs.height !== cv.height){ cvs.width = cv.width; cvs.height = cv.height; }
      const o2 = cvs.getContext('2d'); o2.setTransform(1, 0, 0, 1, 0, 0); o2.clearRect(0, 0, cvs.width, cvs.height); return [cvs, o2];
    };
    const acc = mk('offAcc'), one = mk('off');
    live.forEach(function(L){
      one[1].setTransform(1, 0, 0, 1, 0, 0); one[1].clearRect(0, 0, one[0].width, one[0].height); one[1].setTransform(dpr, 0, 0, dpy, 0, 0);
      draw(one[1], L);
      acc[1].globalAlpha = L[1]; acc[1].globalCompositeOperation = 'lighter'; acc[1].drawImage(one[0], 0, 0);
    });
    acc[1].globalAlpha = 1; acc[1].globalCompositeOperation = 'source-over';
    ctx.save(); ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.drawImage(acc[0], 0, 0); ctx.restore();
  }
  // a bar [x0, x0 + w) going out of the plot (or coming in) by its side: painted (paint()) faded by the share of its
  // width still in; else a thin sliver of it at the edge shows its whole height for a frame, a different bar's at
  // each frame (a flicker at the side of the bars)
  function edge(g, ml, plotW, x0, w, paint){
    const vis = Math.min(x0 + w, ml + plotW) - Math.max(x0, ml), a = Math.max(0, Math.min(1, vis / Math.max(1e-6, w)));
    if (a <= 0) return;
    const ga = g.globalAlpha; if (a < 1) g.globalAlpha = ga * a;
    paint();
    g.globalAlpha = ga;
  }
  // the running total's base (the count at the view's left edge) for its top `top` gliding from wa to wb: the counts'
  // window [base, base + top] zooms as the view's days do (a point that stays, the width gliding); the base moved
  // straight while the top glided, 4 frames into a zoom out the line rose to the top, then came back down
  function glide(baseA, baseB, wa, wb, top, e){
    if (Math.abs(wb - wa) < 1e-6 * Math.max(wa, wb)) return baseA + (baseB - baseA) * e;
    const pp = (baseA * wb - baseB * wa) / (wb - wa);
    return pp - (pp - baseA) * top / wa;
  }

  // the slot position of day d among bins [r0, r1) side by side: i + its share of bin i
  function slotOf(ranges, d){
    const n = ranges.length;
    if (!n || d <= ranges[0][0]) return 0; if (d >= ranges[n - 1][1]) return n;
    let a = 0, b = n - 1;
    while (a < b){ const m = (a + b + 1) >> 1; if (ranges[m][0] <= d) a = m; else b = m - 1; }
    const r = ranges[a]; return a + (d - r[0]) / Math.max(1e-9, r[1] - r[0]);
  }

  // bins of k days on the grid of day 0, within the data [lo, hi); win: the window its chart shows, where a bin cut
  // by the data's end takes a whole slot as the others (the chart draws its bars side by side)
  function grid(k, lo, hi, win){
    k = Math.max(1, k);
    const at = function(v0, v1){
      const out = [];
      for (let r = Math.floor(Math.max(lo, v0) / k) * k; r < Math.min(hi, v1); r += k){
        const r0 = Math.max(lo, r), r1 = Math.min(hi, r + k);
        if (r1 > r0 && r1 > v0) out.push({r0: r0, r1: r1, g: Math.round(r / k)});
      }
      return out;
    };
    const w0 = win ? win[0] : lo, w1 = win ? win[1] : hi;
    const own = at(w0, w1).map(function(b){ return [b.r0, b.r1]; });
    const cut = own.some(function(r){ return r[1] - r[0] < k; });
    return {
      k: k, key: 'G' + k + ':' + lo + ':' + hi,
      at: at,
      kAt: function(){ return k; }, kb: function(){ return k; },
      warp: function(d){ if (!cut || d <= w0 || d >= w1) return 0; return slotOf(own, d) / own.length * (w1 - w0) + w0 - d; },
      // the bins of a window: their first index and count (the running total's points spread over them)
      ref: function(w){ const f = Math.floor(Math.max(lo, w[0]) / k), l = Math.ceil(Math.min(hi, w[1]) / k); return [f, Math.max(1, l - f)]; },
    };
  }

  // the bins a chart drew (ranges [r0, r1) in a row), k their nominal size (kOf(i): bin i's, else k): drawn in even slots
  function list(ranges, k, kOf){
    const n = ranges.length, lo = n ? ranges[0][0] : 0, hi = n ? ranges[n - 1][1] : 1;
    // bins on the grid of k days: that grid (no change of bars between the two)
    let even = n > 0;
    for (let i = 0; i < n && even; i++){ const r = ranges[i]; if ((i > 0 && r[0] % k !== 0) || (i < n - 1 && r[1] % k !== 0) || r[1] - r[0] > k) even = false; }
    if (even && !kOf) return grid(k, lo, hi, [lo, hi]);
    const idx = function(d){ return slotOf(ranges, d); };
    const kb = kOf ? function(b){ return Math.max(1, kOf(b.g)); } : function(){ return Math.max(1, k); };
    return {
      k: Math.max(1, k), key: 'L' + n + ':' + lo + ':' + hi + ':' + k,
      // the size of the bin at day d (those out of the bins: the nearest one's), and of a bin of at()
      kAt: function(d){ return n ? kb({g: Math.max(0, Math.min(n - 1, Math.floor(idx(d))))}) : Math.max(1, k); }, kb: kb,
      at: function(v0, v1){
        const out = [];
        for (let i = 0; i < n; i++){ const r = ranges[i]; if (r[1] > v0 && r[0] < v1) out.push({r0: r[0], r1: r[1], g: i}); }
        return out;
      },
      // the days to add to d so the bins are even slots over [lo, hi)
      warp: function(d){ if (d <= lo || d >= hi) return 0; return idx(d) / n * (hi - lo) + lo - d; },
      ref: function(){ return [0, Math.max(1, n)]; },
    };
  }

  // o: {a, b: the start and end windows; binA, binB: their binnings; ma, mb: the tops of their bars' axis;
  //     row(r0, r1): the bar of those days ({total, ...numbers}); scale(row, f) (default: its numbers times f);
  //     ta, tb, baseA, baseB, pre(d): the running total (its tops, the count before each window, the count before
  //     day d); took: a camera running when this one started (its state goes on)}
  function create(o){
    const c = Object.assign({start: null, el: null, last: null}, o);
    const ka = c.binA.k, kb = c.binB.k;
    c.kf = Math.min(ka, kb); c.kc = Math.max(ka, kb);
    c.len = DD.zoomLen ? DD.zoomLen(c.a[1] - c.a[0], c.b[1] - c.b[0]) : 1;
    c.k = c.k || (DD.calm ? DD.calm() : 1);
    c.dur = 300 * c.k * c.len;
    const scale = c.scale || function(r, f){
      const out = {};
      Object.keys(r).forEach(function(key){ const v = r[key]; out[key] = typeof v === 'number' ? v * f : (Array.isArray(v) ? v.map(function(x){ return typeof x === 'number' ? x * f : x; }) : v); });
      return out;
    };
    const mixRow = function(p, q, w){
      const out = {};
      Object.keys(q).forEach(function(key){
        const a = p[key], b = q[key];
        if (typeof b === 'number') out[key] = (a || 0) + (b - (a || 0)) * w;
        else if (Array.isArray(b)) out[key] = b.map(function(x, i){ const y = a ? a[i] || 0 : 0; return typeof x === 'number' ? y + (x - y) * w : x; });
        else out[key] = b;
      });
      return out;
    };

    // the state of the frame at `now`: false once the zoom is over
    c.step = function(now){
      const t = Math.min(1, clock(c, now) / c.dur);
      if (t >= 1) return false;
      const e = ease(t);
      // Each day goes straight from its place on the start chart (xA) to its place on the end one (xB), at a zoom's
      // pace: the share of the way g(e) is that of a camera whose scale glides in log space, S the end window's
      // magnification as the start chart shows it (S^e - 1) / (S - 1). On even bins it is the camera zooming about the
      // point that stays still, as before. With bins of two sizes (Future Due's 18 days of backlog drawn as wide as 350
      // days ahead) a camera on the days, or two cameras mixed, zooms about a point the charts do not show at the
      // same place: day 0 goes to the chart's middle and back
      const uA = function(d){ return d + c.binA.warp(d); }, uB = function(d){ return d + c.binB.warp(d); };
      const a0 = uA(c.a[0]), wa = uA(c.a[1]) - a0, b0 = uB(c.b[0]), wb = uB(c.b[1]) - b0;
      if (wa < 1e-3 || wb < 1e-3) return false;
      const xA = function(d){ return (uA(d) - a0) / wa; }, xB = function(d){ return (uB(d) - b0) / wb; };
      const S = 1 / Math.max(1e-9, xA(c.b[1]) - xA(c.b[0]));
      const g = Math.abs(S - 1) < 1e-6 ? e : (Math.pow(S, e) - 1) / (S - 1);
      // a day's place across the plot (0: its left side, 1: its right one)
      const f = function(d){ const p = xA(d); return p + (xB(d) - p) * g; };
      // the days at the plot's sides (f grows with the day)
      const L = Math.min(c.a[0], c.b[0]), R = Math.max(c.a[1], c.b[1]), pad = (R - L) * 100;
      const dayAt = function(x){ let lo = L - pad, hi = R + pad; for (let i = 0; i < 60; i++){ const m = (lo + hi) / 2; if (f(m) < x) lo = m; else hi = m; } return (lo + hi) / 2; };
      const v = [dayAt(0), dayAt(1)];
      if (v[1] - v[0] < 1e-3) return false;
      const s = {t: t, e: e, v0: v[0], v1: v[1], f: f};
      s.mx = lerpLog(Math.max(1e-9, c.ma), Math.max(1e-9, c.mb), e);
      if (c.ta != null){
        s.top = lerpLog(Math.max(1, c.ta), Math.max(1, c.tb), e);
        s.base = glide(c.baseA, c.baseB, Math.max(1, c.ta), Math.max(1, c.tb), s.top, e);
      }
      s.layers = layers(t, e, v[1] - v[0]);  // (c.plotW: the plot's width, given at the start or by the last frame)
      c.s = s; c.cur = [v[0], v[1]]; c.curMx = s.mx; c.curTop = s.top; c.curBase = s.base;
      return true;
    };

    // the layers of the frame: [binning, weight, split width, split height, its coarse binning] (split, mix)
    function layers(t, e, span){
      const A = c.binA, B = c.binB;
      if (A.k === B.k){
        if (A.key === B.key) return [[B, 1]];
        // the same size on other bins (the even slots of the whole view, a window off the grid): one fades into the other
        const w = sm((e - 0.05) / 0.6);
        return [[A, 1 - w], [B, w]];
      }
      const fine = A.k < B.k ? A : B, coarse = A.k < B.k ? B : A;
      const sp = split(c, A.k, B.k, c.a, c.b, t, e, span, c.plotW || 600);
      return mix(sp).map(function(m){ return m.fine ? (m.split ? [fine, m.w, sp.wsp, sp.hsp, coarse] : [fine, m.w]) : [coarse, m.w]; });
    }

    // the bars of the frame. G: {ml, plotW, bottom, plotH, ratio (bar / slot), cv, dpr, dpy};
    // paint(g, row, x, w, top): one bar as the chart draws it
    c.bars = function(ctx, G, paint){
      const s = c.s, ml = G.ml, plotW = G.plotW, ratio = G.ratio || 0.9;
      c.plotW = plotW;
      const X = function(d){ return ml + s.f(d) * plotW; };
      s.X = X;
      // the bin size gliding at the days [r0, r1): the start view's there to the end one's
      const kg = function(r0, r1){ const m = (r0 + r1) / 2; return lerpLog(c.binA.kAt(m), c.binB.kAt(m), s.e); };
      // a bar going out of the plot (or coming in) by its side: faded by the share of its width still in
      const bar = function(g, row, x0, w){ edge(g, ml, plotW, x0, w, function(){ paint(g, row, x0, w, s.mx); }); };
      const slot = function(b){ const x0 = X(b.r0), x1 = X(b.r1), w = x1 - x0, bw = Math.max(1, w * ratio); return [x0 + (w - bw) / 2, bw]; };
      const plain = function(g, bin){
        bin.at(s.v0, s.v1).forEach(function(b){
          const sl = slot(b); if (sl[0] > ml + plotW || sl[0] + sl[1] < ml) return;
          bar(g, scale(c.row(b.r0, b.r1), kg(b.r0, b.r1) / bin.kb(b)), sl[0], sl[1]);
        });
      };
      // the fine bars split out of their parent: tiled on the parent bar at 0, at their own
      // place and height at 1 (the tiles count every fine bin of the parent, those out of view too)
      // Where the bins of the two views are not finer and coarser there (Future Due's backlog and days ahead: each side
      // its own size), the roles swap: the fine view's bins are the parents there, the coarse view's their kids, and
      // the kids go the other way (merging while the rest splits). Faded from one to the other instead, the backlog's
      // days became one big bar (or one big bar fell into days) in a few frames
      // merging (merge), a kid lower than its parent keeps its height until the bars gather, and rises with them: rising
      // from the start, the kids of a tall parent (Future Due's first month, today's reviews not done yet) stood as a
      // wall of tall bars still apart. A kid taller than its parent still sinks over the whole zoom (at once, it fell)
      const tiles = function(g, p, pk, kidBin, wsp, hsp, merge){
        const kids = kidBin.at(p.r0, p.r1).filter(function(b){ const m = (b.r0 + b.r1) / 2; return m >= p.r0 && m < p.r1; });
        if (!kids.length) return false;
        const ps = slot(p), pr = scale(c.row(p.r0, p.r1), kg(p.r0, p.r1) / pk), n = kids.length;
        kids.forEach(function(b, i){
          if (b.r1 <= s.v0 || b.r0 >= s.v1) return;
          // its own height at most the chart's top: a kid far above it (today's reviews in a bin of 2 days, its
          // month's parent much lower) sank from out of view, a needle cut at the top for most of the zoom
          let own = scale(c.row(b.r0, b.r1), kg(p.r0, p.r1) / kidBin.kb(b)); const os = slot(b);
          if ((own.total || 0) > s.mx) own = scale(own, s.mx / own.total);
          const row = mixRow(pr, own, merge && (own.total || 0) < (pr.total || 0) ? Math.max(hsp, wsp) : hsp);
          const tw = ps[1] / n, tx = ps[0] + i * tw;
          const x0 = tx + (os[0] - tx) * wsp, w = tw + (os[1] - tw) * wsp;
          if (x0 > ml + plotW || x0 + w < ml) return;
          bar(g, row, x0, Math.max(0.5, w));
        });
        return true;
      };
      const split = function(g, fine, coarse, wsp, hsp){
        fine.at(s.v0, s.v1).forEach(function(b){
          const m = (b.r0 + b.r1) / 2, k = fine.kb(b), kc = coarse.kAt(m); if (k < kc) return;
          if (k > kc && tiles(g, b, k, coarse, 1 - wsp, 1 - hsp, c.binA.k > c.binB.k)) return;
          const sl = slot(b); if (sl[0] > ml + plotW || sl[0] + sl[1] < ml) return;
          bar(g, scale(c.row(b.r0, b.r1), kg(b.r0, b.r1) / k), sl[0], sl[1]);
        });
        coarse.at(s.v0, s.v1).forEach(function(p){
          if (coarse.kb(p) <= fine.kAt((p.r0 + p.r1) / 2)) return;
          tiles(g, p, coarse.kb(p), fine, wsp, hsp, c.binA.k < c.binB.k);
        });
      };
      const draw = function(g, L){ if (L[2] != null) split(g, L[0], L[4], L[2], L[3]); else plain(g, L[0]); };
      const live = s.layers.filter(function(L){ return L[1] > 0.002; });
      c.lastBin = live.reduce(function(a, L){ return L[1] > a[1] ? L : a; }, live[0] || [c.binB, 1])[0];
      composite(c, ctx, G.cv, G.dpr, G.dpy, live, draw);
    };

    // the running total as a line over the bars: one curve seen through the camera (the count since the first day,
    // less the base, on the gliding top). Each layer's points as its own chart spreads them (its first bin at the
    // left edge, its last at the right one, for its own window), their heights mixed by the layers' weights.
    // -> [[x, y]] or null
    c.cumPoints = function(G){
      const s = c.s; if (s.base == null || !c.pre) return null;
      const ml = G.ml, plotW = G.plotW, bottom = G.bottom, plotH = G.plotH, X = s.X;
      const lineOf = function(L){
        const bin = L[0], own = bin === c.binA ? c.a : c.b;
        const ref = bin.ref(own), its = bin.at(s.v0 - (s.v1 - s.v0), s.v1 + (s.v1 - s.v0));
        if (!its.length) return null;
        return its.map(function(b){
          // its point: at its slot, where its chart puts it (bin i of n at i / (n - 1) of the window)
          const q = ref[1] > 1 ? (b.g - ref[0]) / (ref[1] - 1) : 0.5;
          return [X(b.r0) + (X(b.r1) - X(b.r0)) * q, c.pre(b.r1) - s.base];
        });
      };
      const live = s.layers.filter(function(L){ return L[1] > 0.002; });
      const L = live.map(function(ly){ const p = lineOf(ly); return p ? {pts: p, w: ly[1]} : null; }).filter(Boolean);
      if (!L.length) return null;
      const yOf = function(v){ return bottom - Math.max(0, Math.min(1, v / s.top)) * plotH; };
      if (L.length === 1) return L[0].pts.map(function(q){ return [q[0], yOf(q[1])]; });
      const at = function(pts, x){
        if (x <= pts[0][0]) return pts[0][1];
        for (let j = 1; j < pts.length; j++) if (x <= pts[j][0]){ const f = (x - pts[j - 1][0]) / Math.max(1e-9, pts[j][0] - pts[j - 1][0]); return pts[j - 1][1] + (pts[j][1] - pts[j - 1][1]) * f; }
        return pts[pts.length - 1][1];
      };
      const lo = ml - 2, hi = ml + plotW + 2, xs = new Set([lo, hi]), tw = L.reduce(function(a, l){ return a + l.w; }, 0) || 1;
      L.forEach(function(l){ l.pts.forEach(function(q){ if (q[0] >= lo && q[0] <= hi) xs.add(q[0]); }); });
      return Array.from(xs).sort(function(p, q){ return p - q; }).map(function(x){ return [x, yOf(L.reduce(function(a, l){ return a + l.w * at(l.pts, x); }, 0) / tw)]; });
    };

    // labels that move with their days: those of the start and the end ({text: day}), a text in both glides from
    // its old place to its new one, the start's others leave, the end's others come -> [{text, x, a}]
    c.marks = function(A, B){
      const s = c.s, out = [];
      Object.keys(A).forEach(function(k){
        if (k in B) out.push({text: k, x: s.X(A[k] + (B[k] - A[k]) * s.e), a: 1});
        else out.push({text: k, x: s.X(A[k]), a: 1 - sm(s.e / 0.67)});
      });
      Object.keys(B).forEach(function(k){ if (!(k in A)) out.push({text: k, x: s.X(B[k]), a: sm((s.e - 0.33) / 0.67)}); });
      return out;
    };
    return c;
  }

  DD.zoomCam = {clock: clock, path: path, split: split, mix: mix, composite: composite, edge: edge, glide: glide,
    lerpLog: lerpLog, sm: sm, ease: ease, grid: grid, list: list, create: create};
})();
