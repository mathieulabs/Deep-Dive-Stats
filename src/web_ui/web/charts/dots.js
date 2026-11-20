/* Picture zoom between two states of a chart and the Activity chart's
   "one dot per review" view. */
(function(){
  'use strict';
  const MARGIN_BOTTOM = 30;
  const outQuad = (t) => 1 - (1 - t) * (1 - t);
  const inOutQuad = (t) => t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
  const outCubic = (t) => 1 - Math.pow(1 - t, 3);
  const inOutCubic = (t) => t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
  const still = () => window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function copyCanvas(cv){ const c = document.createElement('canvas'); c.width = cv.width; c.height = cv.height; c.getContext('2d').drawImage(cv, 0, 0); return c; }
  function limitRatio(a, b){  // the two windows at most 16 times apart in width
    const wa = a[1] - a[0], wb = b[1] - b[0];
    if (wa <= 0 || wb <= 0) return [a, b];
    const widen = (s, big, w) => { const mid = (s[0] + s[1]) / 2, s0 = Math.max(big[0], Math.min(mid - w / 2, big[1] - w)); return [s0, s0 + w]; };
    if (wb / wa > 16) a = widen(a, b, wb / 16); else if (wa / wb > 16) b = widen(b, a, wa / 16);
    return [a, b];
  }
  function zoomPath(a, b, e){
    const wa = a[1] - a[0], wb = b[1] - b[0];
    if (wa <= 0 || wb <= 0) return b.slice();
    if (Math.abs(wb - wa) < 1e-6 * Math.max(wa, wb)) return [a[0] + (b[0] - a[0]) * e, a[1] + (b[1] - a[1]) * e];
    const w = Math.exp(Math.log(wa) + (Math.log(wb) - Math.log(wa)) * e), p = (a[0] * wb - b[0] * wa) / (wb - wa);
    const v0 = p - (p - a[0]) * w / wa; return [v0, v0 + w];
  }
  // An overlay canvas over `host` (the chart's canvas, hidden meanwhile) driven by its own frames; draw(ctx, t, W, H, dpr).
  function overlay(host, duration, draw, done){
    const ov = document.createElement('canvas');
    ov.width = host.width; ov.height = host.height;
    ov.style.cssText = 'position:absolute;left:' + host.offsetLeft + 'px;top:' + host.offsetTop + 'px;width:' + host.clientWidth + 'px;height:' + host.clientHeight + 'px;pointer-events:none';
    if (host._ddOverlay) host._ddOverlay();  // the running one ends first: its hidden canvas is shown again before this one hides it
    host.parentNode.appendChild(ov);
    const prevVis = host.style.visibility; host.style.visibility = 'hidden';
    const W = host.clientWidth || 1, H = host.clientHeight || 1, dpr = ov.width / W, g = ov.getContext('2d');
    let t0 = null, stopped = false;
    function end(){ if (stopped) return; stopped = true; ov.remove(); host.style.visibility = prevVis; host._ddOverlay = null; if (done) done(); }
    function step(now){
      if (stopped) return;
      if (t0 === null) t0 = now;
      const t = Math.min(1, (now - t0) / duration);
      g.setTransform(1, 0, 0, 1, 0, 0); g.clearRect(0, 0, ov.width, ov.height);
      draw(g, t, W, H, dpr);
      if (t >= 1) end(); else requestAnimationFrame(step);
    }
    host._ddOverlay = end;
    requestAnimationFrame(step);
    return end;
  }

  // The axes of a switch drawn live (both pictures know theirs: P.ax, from Activity's _axisInfo or the dots' axisInfo):
  // the plot's margins glide, the dates / times slide on one time line from the old window to the new one (the
  // clock's marks on both sides: the same marks go on; else the old leave and the new come), the left numbers count
  // or slide from the old top to the new one (the same measure) or the old fade out before the new come (another
  // one). e: the move's progress, view: the time window now
  function liveAxes(g, A, B, e, W, ml, mr, ph, view){
    const sm = (x) => { x = Math.max(0, Math.min(1, x)); return x * x * (3 - 2 * x); };
    const pw = Math.max(1, W - ml - mr), mt = A.mt != null ? A.mt : 10, plotH = Math.max(1, ph - mt);
    g.save(); g.font = B.font || A.font; g.fillStyle = B.ink || A.ink;
    const sp = Math.max(1e-9, view[1] - view[0]), toX = (t) => ml + (t - view[0]) / sp * pw;
    let marks;
    if (A.sub && B.sub) marks = DD.timeMarks(view[0], view[1], pw);
    else {
      const ma = A.sub ? DD.timeMarks(view[0], view[1], pw) : (A.marks || []), mb = B.sub ? DD.timeMarks(view[0], view[1], pw) : (B.marks || []);
      const key = (m) => m.label + '@' + Math.round(m.t / 1000), inB = new Set(mb.map(key)), inA = new Set(ma.map(key));
      marks = [];
      ma.forEach((m) => { const kept = inB.has(key(m)); marks.push({t: m.t, label: m.label, a: (m.a != null ? m.a : 1) * (kept ? 1 : 1 - sm(e / 0.67)), p: kept ? 2 : 1 - e}); });
      mb.forEach((m) => { if (!inA.has(key(m))) marks.push({t: m.t, label: m.label, a: (m.a != null ? m.a : 1) * sm((e - 0.33) / 0.67), p: e}); });
    }
    g.save(); g.beginPath(); g.rect(0, ph + 2, W, 1e4); g.clip();
    DD.placeMarks(g, marks, toX, ml, ml + pw, ph + 10);
    g.restore();
    g.textAlign = 'right'; g.textBaseline = 'middle';
    const slide = !!(DD.axisSlide && DD.axisSlide());
    const gap = (P) => (P.ykind && P.ykind.indexOf('dots') === 0 ? 6 : 8);
    const numbers = (P, top, from, t, alpha) => {
      if (alpha <= 0.003) return;
      if (slide) DD.slideTicks(from, P.ymax, top, t, 4, plotH).forEach((k) => { g.globalAlpha = alpha * k.a; g.fillText(P.yfmt(k.v), ml - gap(P), mt + plotH * (1 - k.f)); });
      else for (let i = 0; i <= 4; i++){
        g.globalAlpha = alpha; const v = top * i / 4;
        g.fillText(i === 0 ? '0' : (P.yfmtCount ? P.yfmtCount(top, v) : P.yfmt(v)), ml - gap(P), mt + plotH * (1 - i / 4));
      }
    };
    if (A.ykind === B.ykind && A.ymax > 0 && B.ymax > 0) numbers(B, A.ymax + (B.ymax - A.ymax) * e, A.ymax, e, 1);
    else { numbers(A, A.ymax, A.ymax, 1, 1 - sm(e / 0.45)); numbers(B, B.ymax, B.ymax, 1, sm((e - 0.55) / 0.45)); }
    g.restore();
  }
  // the picture held still over the chart until the next picture animation (or end()) takes over
  DD.holdPicture = function(host, P){
    if (still() || !host || !host.parentNode || !P) return function(){};
    return overlay(host, 1e9, function(g){ g.drawImage(P.img, 0, 0); });
  };

  // _PixmapZoom: the old and new pictures moved by their windows (any common unit, null = same place), cross-faded as a sum
  DD.pictureZoom = function(host, oldP, newP, winA, winB, duration){
    if (still() || !host || !host.parentNode || !oldP || !newP || oldP.img.width !== newP.img.width || oldP.img.height !== newP.img.height) return;
    const live = !!(oldP.ax && newP.ax && oldP.ax.t0 != null && newP.ax.t0 != null && oldP.ax.t1 > oldP.ax.t0 && newP.ax.t1 > newP.ax.t0);
    // both on a time line: the pictures move by their time windows (a day index and a 10-minute index are no common unit)
    const wins = live ? limitRatio([oldP.ax.t0, oldP.ax.t1], [newP.ax.t0, newP.ax.t1]) : ((winA && winB) ? limitRatio(winA, winB) : null);
    if (live && DD.dev) DD.trace('ANIMTRACE pictureZoom live axes ' + (oldP.ax.sub ? 'clock' : 'days') + ' -> ' + (newP.ax.sub ? 'clock' : 'days') + ' ' + oldP.ax.ykind + ' -> ' + newP.ax.ykind + ' window x' + ((newP.ax.t1 - newP.ax.t0) / (oldP.ax.t1 - oldP.ax.t0)).toFixed(3));
    const acc = document.createElement('canvas'), one = document.createElement('canvas');
    overlay(host, duration || 300, function(g, t, W, H, dpr){
      const e = outQuad(Math.min(1, t / 0.93));
      if (acc.width !== g.canvas.width || acc.height !== g.canvas.height){ acc.width = one.width = g.canvas.width; acc.height = one.height = g.canvas.height; }
      const ml = oldP.ml + (newP.ml - oldP.ml) * e, mr = oldP.mr + (newP.mr - oldP.mr) * e;
      const ph = Math.max(1, oldP.ph + (newP.ph - oldP.ph) * e), pw = Math.max(1, W - ml - mr);
      const view = wins ? zoomPath(wins[0], wins[1], e) : null;
      const ac = acc.getContext('2d'); ac.setTransform(1, 0, 0, 1, 0, 0); ac.clearRect(0, 0, acc.width, acc.height);
      function layer(P, win, alpha, keep){
        const o = one.getContext('2d'); o.setTransform(1, 0, 0, 1, 0, 0); o.clearRect(0, 0, one.width, one.height); o.setTransform(dpr, 0, 0, dpr, 0, 0);
        const pdpr = P.img.width / W;
        // axes and labels (outside the plot): the whole picture there; drawn live (liveAxes), only its right side
        // (Activity's running total numbers) is taken from the picture
        o.save(); o.beginPath();
        if (live){ o.rect(W - P.mr + 1, 0, P.mr, P.ph); o.clip(); }
        else { o.rect(0, 0, W, H); o.rect(ml, 0, pw, ph); o.clip('evenodd'); }
        o.globalAlpha = alpha; o.drawImage(P.img, 0, 0, W, H); o.restore();
        let tx = ml, tw = pw;
        if (view && win){ const sp = Math.max(1e-9, view[1] - view[0]); tx = ml + (win[0] - view[0]) / sp * pw; tw = Math.max(0.5, (win[1] - win[0]) / sp * pw); }
        const sx = P.ml * pdpr, sw = Math.max(1, (W - P.ml - P.mr) * pdpr), sh = P.ph * pdpr;
        o.save(); o.beginPath(); o.rect(ml, 0, pw, ph); o.clip();
        if (keep && view){
          // where the other picture is not there yet this one stays whole (the chart does not dim while the other is small)
          const sp = Math.max(1e-9, view[1] - view[0]), kx0 = ml + (keep[0] - view[0]) / sp * pw, kx1 = ml + (keep[1] - view[0]) / sp * pw;
          o.save(); o.beginPath(); o.rect(ml, 0, pw, ph); o.rect(kx0, 0, Math.max(0.5, kx1 - kx0), ph); o.clip('evenodd'); o.globalAlpha = 1; o.drawImage(P.img, sx, 0, sw, sh, tx, 0, tw, ph); o.restore();
          o.beginPath(); o.rect(kx0, 0, Math.max(0.5, kx1 - kx0), ph); o.clip();
        }
        o.globalAlpha = alpha; o.drawImage(P.img, sx, 0, sw, sh, tx, 0, tw, ph); o.restore();
        ac.globalCompositeOperation = 'lighter'; ac.drawImage(one, 0, 0); ac.globalCompositeOperation = 'source-over';
      }
      if (e < 0.999) layer(oldP, wins && wins[0], 1 - e, (wins && view) ? wins[1] : null);
      if (e > 0.001) layer(newP, wins && wins[1], e, null);
      g.setTransform(1, 0, 0, 1, 0, 0); g.drawImage(acc, 0, 0);
      if (live){ g.setTransform(dpr, 0, 0, dpr, 0, 0); liveAxes(g, oldP.ax, newP.ax, e, W, ml, mr, ph, view); }
    });
  };

  // _SinkOut: the old picture's bars squashed toward the baseline while fading (300 ms), its axes gone quickly
  // newA ({ml, mr, ph, ax} of what comes, the dots' axisInfo): the axes go from the old ones to the new ones live
  // (liveAxes: the times stay on, the numbers change) instead of fading out with the bars; the new view holds its own
  // axes back meanwhile (dots holdAxes)
  DD.sinkOut = function(host, oldP, duration, newA){
    if (still() || !host || !host.parentNode || !oldP) return;
    const live = !!(newA && newA.ax && oldP.ax && oldP.ax.t0 != null && oldP.ax.t1 > oldP.ax.t0 && newA.ax.t1 > newA.ax.t0);
    if (live && DD.dev) DD.trace('ANIMTRACE sinkOut live axes ' + oldP.ax.ykind + ' -> ' + newA.ax.ykind);
    overlay(host, duration || 300, function(g, t, W, H, dpr){
      const e = inOutQuad(t), pdpr = oldP.img.width / W, base = oldP.ph, pw = Math.max(1, W - oldP.ml - oldP.mr);
      g.setTransform(dpr, 0, 0, dpr, 0, 0);
      if (live){
        const ea = outQuad(t), ml = oldP.ml + (newA.ml - oldP.ml) * ea, mr = oldP.mr + (newA.mr - oldP.mr) * ea, ph = oldP.ph + (newA.ph - oldP.ph) * ea;
        g.save(); g.globalAlpha = Math.max(0, 1 - t * 2.5); g.beginPath(); g.rect(W - oldP.mr + 1, 0, oldP.mr, oldP.ph); g.clip(); g.drawImage(oldP.img, 0, 0, W, H); g.restore();
        liveAxes(g, oldP.ax, newA.ax, ea, W, ml, mr, ph, zoomPath([oldP.ax.t0, oldP.ax.t1], [newA.ax.t0, newA.ax.t1], ea));
      } else {
        g.save(); g.globalAlpha = Math.max(0, 1 - t * 2.5); g.beginPath(); g.rect(0, 0, W, H); g.rect(oldP.ml, 0, pw, base); g.clip('evenodd'); g.drawImage(oldP.img, 0, 0, W, H); g.restore();
      }
      g.globalAlpha = Math.max(0, 1 - e);
      const h = base * (1 - 0.85 * e);
      g.drawImage(oldP.img, oldP.ml * pdpr, 0, pw * pdpr, base * pdpr, oldP.ml, base - h, pw, h);
      g.globalAlpha = 1;
    });
  };

  // ---- one dot per review (ReviewDotsChart) ----
  const ML = 45, MR = 20, MT = 10;
  const KIND = ['learn', 'young', 'mature', 'relearn', 'cram'];
  const KIND_NAMES = ['Learning', 'Young', 'Mature', 'Relearning', 'Filtered'];
  const EASE_NAMES = {1: 'Again', 2: 'Hard', 3: 'Good', 4: 'Easy'};
  const pad2 = (n) => String(n).padStart(2, '0');

  DD.reviewDots = function(plot, opts){
    const cv = document.createElement('canvas');
    cv.className = 'dd-dots';
    cv.style.cssText = 'position:absolute;left:0;top:0;width:100%;height:100%;display:none';
    plot.appendChild(cv);
    const ctx = cv.getContext('2d');
    const st = {events: [], shown: false, t0: 0, t1: 1, v0: 0, v1: 1, mode: 'reviews', breakdown: false, intro: 1, introAnim: null,
      modeFrom: null, modeE: 1, viewAnim: null, viewTarget: null, points: [], press: null, dragX: null, tipIdx: null, visible: false};
    const tip = document.createElement('div'); tip.className = 'dd-tip'; tip.style.display = 'none'; plot.appendChild(tip);
    let W = 1, H = 1;
    // the band under the plot as Activity's (lower on the pinned cards): the times stay where the bars' were
    const MB = plot.closest && plot.closest('.ddp') ? 24 : 30;
    function size(){
      // (its layout size: a card sliding into its new place is stretched meanwhile, DD.boxOf)
      const B = DD.boxOf(plot), d = window.devicePixelRatio || 1, k = B.s;
      W = Math.max(1, B.w); H = Math.max(1, B.h);
      const pw = Math.round(W * k * d), ph = Math.round(H * k * d);
      if (cv.width !== pw || cv.height !== ph){ cv.width = pw; cv.height = ph; }
    }
    function C(){ return DD.theme.chart || {}; }
    function yValues(mode){ return mode === 'time' ? st.events.map((e) => e[1] / 1000) : st.events.map((_e, i) => i + 1); }
    function dotColor(ev){
      const c = C(), col = st.breakdown ? ((opts.color && opts.color(KIND[ev[3]])) || c[KIND[ev[3]]] || '#888') : (c.bar || '#4c8bf5');
      return DD.cu.rgba(col, 200 / 255);
    }
    function draw(){
      if (!st.visible) return;
      size();
      const c = C(), dpr = cv.width / W;
      ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.clearRect(0, 0, cv.width, cv.height); ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const px = ML, py = MT, pw = W - ML - MR, ph = H - MT - MB;
      if (pw <= 10 || ph <= 10) return;
      // Activity's font and ink: the bars' axes and these meet in the switches between them (DD.pictureZoom / sinkOut)
      const font = (DD.cu && DD.cu.AXIS_FONT) || '12px "Segoe UI",-apple-system,sans-serif';
      ctx.font = font;
      const ys = yValues(st.mode), ymax = Math.max(1, ys.length ? Math.max.apply(null, ys) : 1);
      const morph = (st.modeFrom && st.modeFrom !== st.mode) ? st.modeFrom : null, me = morph ? Math.max(0, Math.min(1, st.modeE)) : 1;
      const ysF = morph ? yValues(morph) : null, ymaxF = morph ? Math.max(1, ysF.length ? Math.max.apply(null, ysF) : 1) : 1;
      const text = ink(), grid = c.grid || 'rgba(128,128,128,0.25)';
      // the axes held back while a switch from the bars draws them (sinkOut): they come back as they were left
      const axesA = (st.axHold && performance.now() < st.axHold) ? 0 : Math.min(1, st.intro * 2.5);
      ctx.globalAlpha = axesA; ctx.lineWidth = 0.5;
      if (DD.axisSlide && DD.axisSlide() && !morph){
        // Chart_Axis_Anim 'slide' (dd-core DD.slideAxis): round values sliding with the scale, the exact top written too
        // (a switch of the measure keeps its fade from the old numbers to the new ones, below)
        DD.slideAxis(st.yax || (st.yax = {}), 0, ymax, {px: ph, top: true, redraw: draw}).forEach(function(k){
          const y = py + ph - k.f * ph;
          ctx.globalAlpha = axesA * k.a;
          ctx.strokeStyle = grid; ctx.beginPath(); ctx.moveTo(Math.trunc(px), Math.trunc(y) + 0.5); ctx.lineTo(Math.trunc(px + pw), Math.trunc(y) + 0.5); ctx.stroke();
          const s = yLab(st.mode, k.v);
          ctx.fillStyle = text; ctx.textAlign = 'right'; ctx.textBaseline = 'middle'; ctx.fillText(s, px - 6, Math.trunc(y));
        });
        ctx.globalAlpha = axesA;
      } else for (let i = 0; i < 5; i++){
        const fr = i / 4, y = py + ph - fr * ph;
        ctx.strokeStyle = grid; ctx.beginPath(); ctx.moveTo(Math.trunc(px), Math.trunc(y) + 0.5); ctx.lineTo(Math.trunc(px + pw), Math.trunc(y) + 0.5); ctx.stroke();
        const labs = [[st.mode, ymax, me]]; if (morph) labs.push([morph, ymaxF, 1 - me]);
        labs.forEach(function(L){
          const s = yLabCount(L[0], L[1], L[1] * fr);
          ctx.globalAlpha = axesA * L[2]; ctx.fillStyle = text; ctx.textAlign = 'right'; ctx.textBaseline = 'middle'; ctx.fillText(s, px - 6, Math.trunc(y));
        });
        ctx.globalAlpha = axesA;
      }
      const v0 = st.v0, v1 = st.v1, span = Math.max(1, v1 - v0);
      // the clock's marks (dd-core DD.timeMarks, as the 10-minute bars draw them): they slide and come or go with the
      // room as the view zooms, a grid line at each
      if (axesA > 0){
        ctx.fillStyle = text;
        DD.placeMarks(ctx, DD.timeMarks(v0, v1, pw).map(function(m){ m.k = axesA; return m; }), function(t){ return px + (t - v0) / span * pw; }, px, px + pw, py + ph + 10).forEach(function(m){
          ctx.globalAlpha = m.a * axesA; ctx.strokeStyle = grid;
          ctx.beginPath(); ctx.moveTo(Math.trunc(m.x) + 0.5, Math.trunc(py)); ctx.lineTo(Math.trunc(m.x) + 0.5, Math.trunc(py + ph)); ctx.stroke();
        });
      }
      ctx.globalAlpha = 1;
      st.points = [];
      const n = st.events.length, radius = n <= 300 ? 3.5 : n <= 700 ? 2.5 : 2.0;
      st.events.forEach(function(ev, k){
        const x = px + (ev[0] - v0) / span * pw;
        if (x < px - 1 || x > px + pw + 1) return;
        let yn = ys[k] / ymax;
        if (morph && k < ysF.length){ const yf = ysF[k] / ymaxF; yn = yf + (yn - yf) * me; }
        const y = py + ph - yn * ph;
        let r = radius, a = 1;
        if (st.intro < 1){
          // each dot starts a little later the further right it is
          let local = Math.max(0, Math.min(1, st.intro * 1.6 - ((x - px) / pw) * 0.6)); local = 1 - Math.pow(1 - local, 3);
          r = radius * (0.3 + 0.7 * local); a = local;
        }
        ctx.globalAlpha = a; ctx.fillStyle = dotColor(ev); ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill();
        st.points.push([x, y, ev]);
      });
      ctx.globalAlpha = 1;
      if (st.press && st.dragX != null){
        const x1 = Math.max(px, Math.min(st.press[0], st.dragX)), x2 = Math.min(px + pw, Math.max(st.press[0], st.dragX));
        if (x2 > x1){ const acc = c.accent || '#3b82f6'; ctx.fillStyle = DD.cu.rgba(acc, 20 / 255); ctx.fillRect(x1, py, x2 - x1, ph); ctx.strokeStyle = DD.cu.rgba(acc, 200 / 255); ctx.lineWidth = 1.5; ctx.strokeRect(x1, py, x2 - x1, ph); }
      }
    }
    // animations (each its own frames)
    function anim(dur, ease, onStep, onDone){
      const a = {stop: false}; let t0 = null;
      requestAnimationFrame(function f(now){ if (a.stop) return; if (t0 === null) t0 = now; const t = Math.min(1, (now - t0) / dur); onStep(ease(t)); if (t < 1) requestAnimationFrame(f); else { a.done = true; if (onDone) onDone(); } });
      return a;
    }
    function startIntro(){
      if (st.introAnim) st.introAnim.stop = true;
      if (still() || !st.events.length){ st.intro = 1; return; }
      st.intro = 0;
      st.introAnim = anim(Math.min(700, 380 + st.events.length * 0.5), (x) => x, function(v){ st.intro = v; draw(); }, function(){ st.intro = 1; draw(); });
    }
    function applyView(v0, span){
      span = Math.min(Math.max(span, 1), st.t1 - st.t0); v0 = Math.min(Math.max(v0, st.t0), st.t1 - span);
      st.v0 = Math.trunc(v0); st.v1 = Math.trunc(v0 + span); draw();
    }
    function stopView(){ if (st.viewAnim){ st.viewAnim.stop = true; st.viewAnim = null; } }
    function animateView(v0, span){
      stopView();
      span = Math.min(Math.max(span, 1), st.t1 - st.t0); v0 = Math.min(Math.max(v0, st.t0), st.t1 - span);
      if (still() || !st.visible){ applyView(v0, span); return; }
      const a0 = st.v0, aw = Math.max(1, st.v1 - st.v0), b0 = v0, bw = span;
      st.viewTarget = [b0, bw];
      st.viewAnim = anim(320, outCubic, function(e){
        const w = Math.exp(Math.log(aw) + (Math.log(bw) - Math.log(aw)) * e);
        let s; if (Math.abs(bw - aw) < 1e-6 * Math.max(aw, bw)) s = a0 + (b0 - a0) * e; else { const p = (a0 * bw - b0 * aw) / (bw - aw); s = p - (p - a0) * w / aw; }
        applyView(s, w);
      }, function(){ st.viewAnim = null; });
    }
    function ink(){ const c = C(); return DD.cu.rgba(c.text_secondary || c.axis_text || '#888888', (c.is_dark ? 175 : 215) / 255); }
    function yLab(mode, v){ return ((mode === 'reviews' || v >= 10 || v === Math.round(v)) ? String(Math.round(v)) : v.toFixed(1)) + (mode === 'time' ? 's' : ''); }
    function yLabCount(mode, top, v){ return ((mode === 'reviews' || top >= 10) ? String(Math.round(v)) : v.toFixed(1)) + (mode === 'time' ? 's' : ''); }
    // the axes of the view for a picture zoom (dd-core DD.pictureZoom): its time window, the top of its numbers
    function axisInfo(){
      const ys = yValues(st.mode), ymax = Math.max(1, ys.length ? Math.max.apply(null, ys) : 1), m = st.mode;
      return {t0: st.v0, t1: st.v1, sub: true, marks: null, ymax: ymax, ykind: 'dots:' + m, ink: ink(), font: (DD.cu && DD.cu.AXIS_FONT) || '12px sans-serif', mt: MT,
        yfmt: function(v){ return yLab(m, v); }, yfmtCount: function(top, v){ return yLabCount(m, top, v); }};
    }
    function picture(){ size(); draw(); return {img: copyCanvas(cv), ml: ML, mr: MR, ph: H - MB, ax: axisInfo()}; }
    function nearest(x, y){ let best = null, bd = 64; st.points.forEach(function(p){ const d = (p[0] - x) * (p[0] - x) + (p[1] - y) * (p[1] - y); if (d < bd){ bd = d; best = p[2]; } }); return best; }
    function local(e){ const r = cv.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; }
    function xToTime(x){ const pw = Math.max(1, W - ML - MR), f = Math.min(1, Math.max(0, (x - ML) / pw)); return st.v0 + f * (st.v1 - st.v0); }
    cv.addEventListener('mousedown', function(e){ if (e.button !== 0) return; st.press = local(e); st.dragX = null; });
    window.addEventListener('mouseup', function(e){
      const p = st.press; st.press = null; const dx = st.dragX; st.dragX = null;
      if (!p || !st.visible) return;
      const q = local(e);
      if (dx != null && Math.abs(q[0] - p[0]) > 5){
        // zone: the view zooms on it (at least one minute)
        let a = xToTime(Math.min(p[0], q[0])), b = xToTime(Math.max(p[0], q[0]));
        if (b - a < 60000){ const m = (a + b) / 2; a = m - 30000; b = m + 30000; }
        animateView(a, b - a);
      } else if (Math.abs(q[0] - p[0]) + Math.abs(q[1] - p[1]) <= 5){
        const ev = nearest(q[0], q[1]); if (ev && ev.length > 4) DD.call('open_card', {cid: ev[4]}).catch(function(){});
      }
      draw();
    });
    cv.addEventListener('mousemove', function(e){
      const q = local(e);
      if (st.press && (e.buttons & 1) && Math.abs(q[0] - st.press[0]) > 5){ st.dragX = q[0]; tip.style.display = 'none'; draw(); return; }
      const ev = nearest(q[0], q[1]);
      if (!ev){ tip.style.display = 'none'; st.tipIdx = null; return; }
      const c = C(), d = new Date(ev[0]);
      const head = d.toLocaleDateString(undefined, {month: 'short', day: 'numeric'}) + ', ' + pad2(d.getHours()) + ':' + pad2(d.getMinutes()) + ':' + pad2(d.getSeconds());
      const sw = st.breakdown ? '<span class="swatch" style="background:' + ((opts.color && opts.color(KIND[ev[3]])) || c[KIND[ev[3]]] || '#888') + '"></span>' : '';
      tip.innerHTML = '<div class="row header">' + head + '</div><div class="row">' + sw + '<span class="lbl">' + KIND_NAMES[ev[3]] + '</span><span class="val">' + (ev[1] / 1000).toFixed(1) + 's</span></div>' +
        '<div class="row"><span class="lbl">Answer</span><span class="val">' + (EASE_NAMES[ev[2]] || '?') + '</span></div>';
      tip.style.background = DD.cu.rgba(c.tooltip_bg || '#18181b', c.is_dark ? 0.91 : 0.96);
      tip.style.borderColor = c.tooltip_border || 'rgba(128,128,128,0.4)'; tip.style.color = c.text_secondary || '#888';
      const hd = tip.querySelector('.row.header'); if (hd) hd.style.color = c.text_primary || '#fff';
      tip.style.display = 'block';
      let left = q[0] + 15, top = q[1] + 15; const tw = tip.offsetWidth, th = tip.offsetHeight;
      if (left + tw > W) left = q[0] - tw - 15; if (left < 0) left = 2; if (top + th > H) top = H - th - 2; if (top < 0) top = 2;
      tip.style.transform = 'translate3d(' + left + 'px,' + top + 'px,0)';
    });
    cv.addEventListener('mouseleave', function(){ tip.style.display = 'none'; });
    cv.addEventListener('wheel', function(e){
      const dl = e.deltaY || e.deltaX; if (!dl) return;
      const full = st.t1 - st.t0, span = st.v1 - st.v0, pw = Math.max(1, W - ML - MR);
      const q = local(e), frac = Math.min(1, Math.max(0, (q[0] - ML) / pw));
      if (e.ctrlKey || e.metaKey){
        e.preventDefault(); e.stopPropagation();
        const zin = dl < 0;
        const tspan = (st.viewTarget && st.viewAnim) ? st.viewTarget[1] : span;
        if (!zin && Math.max(span, tspan) >= full * 0.999){ if (opts.onZoomOut) opts.onZoomOut(frac); return; }
        const anchor = st.v0 + frac * span; let ns = span * (zin ? 0.8 : 1.25); ns = Math.min(full, Math.max(60000, ns));
        stopView(); applyView(anchor - frac * ns, ns); return;
      }
      if (e.shiftKey){ e.preventDefault(); e.stopPropagation(); stopView(); applyView(st.v0 - span * 0.1 * (dl < 0 ? 1 : -1), span); }
    }, {passive: false});
    new ResizeObserver(function(){ draw(); }).observe(plot);

    return {
      canvas: cv,
      visible: function(){ return st.visible; },
      window: function(){ return [st.v0, st.v1]; },
      picture: picture,
      axisInfo: function(){ size(); return {ml: ML, mr: MR, ph: H - MB, ax: axisInfo()}; },
      // the axes left out for ms (a switch from the bars draws them meanwhile), then drawn again
      holdAxes: function(ms){ st.axHold = performance.now() + ms; setTimeout(draw, ms + 20); },
      setMode: function(mode, breakdown){
        mode = mode === 'time' ? 'time' : 'reviews'; st.breakdown = !!breakdown;
        if (mode === st.mode){ draw(); return; }
        const prev = st.mode; st.mode = mode;
        if (st.events.length && st.visible && !still()){
          st.modeFrom = prev; st.modeE = 0;
          anim(320, inOutCubic, function(v){ st.modeE = v; draw(); }, function(){ st.modeFrom = null; st.modeE = 1; draw(); });
        } else draw();
      },
      // new reviews over [t0, t1): wider than shown = the view glides out; else shown at once (the caller animates)
      setEvents: function(events, t0, t1){
        t1 = Math.max(t1, t0 + 1);
        if (st.shown && t0 === st.t0 && t1 === st.t1){ st.events = (events || []).slice(); draw(); return 'same'; }
        const widened = st.shown && st.visible && !still() && t0 <= st.v0 && t1 >= st.v1 && t1 - t0 > st.v1 - st.v0;
        st.events = (events || []).slice(); st.t0 = t0; st.t1 = t1; st.shown = true;
        if (widened){ animateView(t0, t1 - t0); return 'glide'; }
        stopView(); st.v0 = t0; st.v1 = t1; draw(); return 'set';
      },
      show: function(intro){ st.visible = true; cv.style.display = 'block'; plot.classList.add('dd-dots-on'); if (intro) startIntro(); else { st.intro = 1; } draw(); },
      hide: function(){ st.visible = false; cv.style.display = 'none'; plot.classList.remove('dd-dots-on'); tip.style.display = 'none'; stopView(); },
      redraw: draw,
    };
  };
})();
