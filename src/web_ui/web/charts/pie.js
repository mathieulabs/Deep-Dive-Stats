// Card Counts: donut of the card types with the legend beside or under it.
// The donut and the legend are drawn in a logical box that is scaled to the card.
(function(){
  'use strict';
  const DD = window.DD;
  const U = DD.cu;
  const FONT_FAMILY = '"Segoe UI",-apple-system,BlinkMacSystemFont,sans-serif';
  const ORDER = ['new', 'learn', 'relearn', 'young', 'mature', 'suspended', 'buried', 'deleted'];
  const LABELS = {new: 'New', learn: 'Learning', relearn: 'Relearning', young: 'Young', mature: 'Mature',
    suspended: 'Suspended', buried: 'Buried', deleted: 'Deleted'};
  const PIE = 130, RING_W = 22, SLICE_GAP = 20;

  const dayText = function(iso){ const p = String(iso).split('-').map(Number); return new Date(p[0], p[1] - 1, p[2]).toLocaleDateString(); };
  function smooth(t){ t = Math.max(0, Math.min(1, t)); return t * t * (3 - 2 * t); }

  class Chart {
    constructor(root, payload, colors, options){
      this.hoverAmt = {}; this.hoverKey = null; this.hAnim = false;
      this.canvas = root.querySelector('canvas');
      this.ctx = this.canvas.getContext('2d');
      this.colors = colors; this.payload = payload;
      this.options = Object.assign({chart_opacity_pct: 100}, options || {});
      this.progress = 0;
      this._resize();
    }
    _resize(){
      const f = DD.fitCanvas(this.canvas, this.ctx), w = f.w, h = f.h, dpr = f.dpr;
      this.w = w; this.h = h; this.dpr = dpr;
    }
    // the legend beside the donut (the horizontal layout of draw): its rows and the widest name and count, at a
    // readable size (10 px on screen), fit the room right of the donut and the card's height
    _legendFits(ctx, w, h, rows, counts){
      const scale = Math.min(h / 142, w / 252, 3), tx = Math.max(6, w * 0.28 - (PIE / 2) * scale);
      const px = 10;
      const room = (w - 3) - (tx + PIE * scale + 4) - Math.max(9, 12 * scale);
      const self = this, keys = rows.filter(function(k){ return (counts[k] || 0) > 0; });
      ctx.save();
      ctx.font = 'bold ' + px + 'px ' + FONT_FAMILY;
      const lw = Math.max.apply(null, (keys.length ? keys : rows).map(function(k){ return ctx.measureText(self.label(k)).width; }).concat([ctx.measureText('Total').width]));
      ctx.font = px + 'px ' + FONT_FAMILY;
      let tot = 0; rows.forEach(function(k){ tot += Number(counts[k] || 0); });
      let cw = Math.max(ctx.measureText(U.formatNum(Math.round(tot))).width, ctx.measureText('0').width);
      if (this.payload.legend_pct && tot > 0) cw += ctx.measureText('  100%').width;  // (its % column, when on)
      ctx.restore();
      return lw + 8 + cw + 2 <= room && ((keys.length || 1) + 1) * (px + 3) + 8 <= h;
    }
    // a pie of other parts (Today's Retention): the payload names its keys, labels and colours
    order(){ return this.payload.order || ORDER; }
    label(k){ const l = this.payload.labels && this.payload.labels[k]; return DD.t(l || LABELS[k] || k); }
    color(k){ const c = this.payload.colors && this.payload.colors[k]; return c || this.colors[k] || '#888888'; }
    // a card type hidden from a click on the legend (Card Counts, a distribution's pie: kindsToggle): how much of it
    // is shown, 0 .. 1
    shown(k){ return 1 - ((this.hideAmt && this.hideAmt[k]) || 0); }
    hiddenKinds(){ return (this.kindsToggle && this.payload.hidden_kinds) || []; }
    // the payload's hidden types, at once while no change of them is animated (a refresh, another day)
    syncHide(){
      if (this.hideAnim) return;
      const hid = this.hiddenKinds(), amt = {};
      hid.forEach(function(k){ amt[k] = 1; });
      this.hideAmt = amt;
    }
    // hides or shows a card type (never the last one shown); returns the types hidden now, or null
    toggleKind(k){
      const hid = this.hiddenKinds().slice(), i = hid.indexOf(k), counts = this.payload.counts || {};
      if (i >= 0) hid.splice(i, 1);
      else {
        const left = this.activeKeys().filter(function(a){ return a !== k && hid.indexOf(a) < 0 && Number(counts[a] || 0) > 0; });
        if (!left.length) return null;
        hid.push(k);
      }
      this.payload = Object.assign({}, this.payload, {hidden_kinds: hid});
      const from = Object.assign({}, this.hideAmt || {}), to = {};
      this.activeKeys().forEach(function(a){ to[a] = hid.indexOf(a) >= 0 ? 1 : 0; });
      if (DD.anim && DD.anim.on === false){ this.hideAmt = to; this.hideAnim = null; }
      else this.hideAnim = {from: from, to: to, t0: null};
      return hid;
    }
    // Show Percentages: how much of the legend's % column shows (0 .. 1); the payload's at once (a refresh, the
    // first draw), the toggle animated (pctTo): the counts slide left as the % fade in, back as they go
    pctNow(){
      if (!this.pctAnim) this.pctAmt = this.payload.legend_pct ? 1 : 0;
      return this.pctAmt || 0;
    }
    pctTo(on){
      const from = this.pctNow(), to = on ? 1 : 0;
      this.payload = Object.assign({}, this.payload, {legend_pct: !!on});
      if (from === to) return;
      if (DD.anim && DD.anim.on === false){ this.pctAmt = to; this.pctAnim = null; return; }
      this.pctAnim = {from: from, to: to, t0: null};
    }
    stepPct(now){
      const A = this.pctAnim;
      if (!A) return false;
      if (A.t0 === null) A.t0 = now;
      const p = Math.min(1, (now - A.t0) / (300 * DD.speed())), e = p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2;
      this.pctAmt = A.from + (A.to - A.from) * e;
      if (p >= 1) this.pctAnim = null;
      return true;
    }
    stepHide(now){
      const A = this.hideAnim;
      if (!A) return false;
      if (A.t0 === null) A.t0 = now;
      const p = Math.min(1, (now - A.t0) / (300 * DD.speed())), e = p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2;
      const amt = {};
      Object.keys(A.to).forEach(function(k){ const f = A.from[k] || 0; amt[k] = f + (A.to[k] - f) * e; });
      this.hideAmt = amt;
      if (p >= 1) this.hideAnim = null;
      return true;  // (its last step drawn too: it stopped one frame short)
    }
    // the legend row under a point (Card Counts): its card type
    legendRowAt(x, y){
      if (!this.kindsToggle) return null;
      const hit = (this.legendHits || []).filter(function(r){ return x >= r.x && x <= r.x + r.w && y >= r.y && y <= r.y + r.h; })[0];
      return hit ? hit.k : null;
    }
    activeKeys(){
      if (this.payload.order) return this.payload.order.slice();
      const k = ['new', 'learn', 'relearn', 'young', 'mature'];
      if (this.payload.separate) k.push('suspended', 'buried');
      return k;
    }
    setHover(key){
      if (this.hoverKey === key) return;
      this.hoverKey = key;
      const from = Object.assign({}, this.hoverAmt), keys = {};
      Object.keys(from).forEach(function(k){ keys[k] = 1; }); if (key) keys[key] = 1;
      const to = {}; Object.keys(keys).forEach(function(k){ to[k] = k === key ? 1 : 0; });
      this.hFrom = from; this.hTo = to; this.hT0 = null; this.hAnim = true;
    }
    stepHover(now){
      if (!this.hAnim) return false;
      if (this.hT0 === null) this.hT0 = now;
      const p = Math.min(1, (now - this.hT0) / 130), e = 1 - Math.pow(1 - p, 3);
      const amt = {}, self = this;
      Object.keys(this.hTo).forEach(function(k){
        const v = (self.hFrom[k] || 0) + (self.hTo[k] - (self.hFrom[k] || 0)) * e;
        if (v > 0.001) amt[k] = v;
      });
      this.hoverAmt = amt;
      if (p >= 1) this.hAnim = false;
      return this.hAnim;
    }
    sliceAt(mx, my){
      const xf = this.xf;
      if (!xf || this.progress < 0.999 || xf.scale <= 0) return null;
      if (xf.bars){
        const lx = (mx - xf.tx) / xf.scale, ly = (my - xf.ty) / xf.scale;
        const self = this, hit = xf.bars.filter(function(r){ return self.shown(r.k) > 0.5 && lx >= r.x && lx <= r.x + r.w && ly >= r.y && ly <= r.y + r.h; })[0];
        return hit ? hit.k : null;
      }
      const dx = (mx - xf.tx) / xf.scale - (xf.pieX + PIE / 2), dy = (my - xf.ty) / xf.scale - (xf.pieY + PIE / 2);
      const r = Math.hypot(dx, dy);
      if (r < PIE / 2 - RING_W - 2 || r > PIE / 2 + 2) return null;
      const cw = (((90 - Math.atan2(-dy, dx) * 180 / Math.PI) % 360) + 360) % 360;
      const counts = this.payload.counts || {}, active = this.activeKeys();
      const keys = this.order().filter(function(k){ return active.indexOf(k) >= 0; });
      const self = this;
      let total = 0; keys.forEach(function(k){ total += Math.max(0, Number(counts[k] || 0)) * self.shown(k); });
      if (total <= 0) return null;
      let acc = 0;
      for (let i = 0; i < keys.length; i++){
        const v = Math.max(0, Number(counts[keys[i]] || 0)) * self.shown(keys[i]);
        if (v <= 0) continue;
        acc += v / total * 360;
        if (cw < acc) return keys[i];
      }
      return null;
    }
    draw(){
      const ctx = this.ctx, w = this.w, h = this.h, C = this.colors;
      this.syncHide();
      { const s = DD.canvasScale(this.canvas, w, h); ctx.setTransform(s[0], 0, 0, s[1], 0, 0); }
      ctx.clearRect(0, 0, w, h);
      let counts = (this.view || this.payload).counts || {};
      const active = this.activeKeys();
      const showLegend = this.payload.show_legend !== false;
      const mode = this.payload.legend_mode || 'auto';
      // the intro's sweep: OutCubic (OutQuart was three quarters round in a fifth of its time, a whoosh)
      const p0 = Math.max(0, Math.min(1, this.progress));
      let t = 1 - Math.pow(1 - p0, 3);
      let st = smooth(t), ga = 1;
      // to / from an empty deck: the slices of the side that has cards close (or open) round
      // the ring as they fade, the numbers going down to 0 (or up from it)
      const E = this.etr;
      if (E){ counts = E.counts; t = E.mul; st = E.mul; ga = E.mul; }
      const rows = this.order().filter(function(k){ return active.indexOf(k) >= 0; });
      const self = this;

      const baseScale = w > 0 ? Math.min(w / 180, 3) : 1;
      const vScale = function(lw, ){ return Math.min(baseScale, w / lw); };
      const needed = function(withLegend){ return withLegend ? (187 + 18 * rows.length) * vScale(210) : 150 * vScale(150); };
      let compact;
      if (!showLegend || mode === 'always') compact = false;
      else if (mode === 'hover') compact = true;
      else {
        const nd = needed(true);
        const sc = h < nd - 15 ? Math.min(h / 142, w / 252, 3) : vScale(210);
        // readable on screen: the legend's size in device pixels (a zoom makes the card smaller in CSS pixels but
        // its text as big on screen, so the legend does not go behind its icon when zoomed in)
        compact = sc * Math.max(1, this.dpr || 1) < 0.9;
        // and beside the donut, its text at a readable size: a narrow card (the main screen's auto layout, ~230 px)
        // kept the legend there, its text shrunk to 6 px to fit; the donut alone fills it, the list on its icon
        if (!compact && h < nd - 15) compact = !this._legendFits(ctx, w, h, rows, counts);
      }
      const inline = showLegend && !compact;
      const gridMode = true;
      const neededH = needed(inline);
      const horizontal = gridMode && h < neededH - 15 && inline;
      const logicalW = 210;
      let tx, ty, scale, totalScaledW = 0;
      ctx.save();
      if (!inline){
        scale = Math.max(0.1, Math.min(w / (PIE + 8 + 8), h / (PIE + 8 + 8), 3));
        tx = (w - PIE * scale) / 2 - (((logicalW - PIE) / 2) * scale);
        ty = (h - PIE * scale) / 2 - 5 * scale;
      } else if (horizontal){
        const cw = 252;
        scale = Math.min(h / 142, w / cw, 3);
        totalScaledW = cw * scale;
        // anchor the donut's center X to the card's width so stacked pie cards align vertically even when one has a slider
        tx = Math.max(6, w * 0.28 - (PIE / 2) * scale); ty = (h - 150 * scale) / 2;
      } else {
        scale = vScale(logicalW);
        tx = Math.max(2, (w - logicalW * scale) / 2); ty = Math.max(2, (h - neededH) / 2);
      }
      ctx.translate(tx, ty); ctx.scale(scale, scale);

      const pieX = horizontal ? 0 : (logicalW - PIE) / 2;
      const pieY = horizontal ? (150 - PIE) / 2 : 5;
      this.xf = {tx: tx, ty: ty, scale: scale, pieX: pieX, pieY: pieY};
      const hov = this.hoverAmt || {};
      let hpeak = 0; Object.keys(hov).forEach(function(k){ if (hov[k] > hpeak) hpeak = hov[k]; });
      let hkey = null, hbest = 0.5; Object.keys(hov).forEach(function(k){ if (hov[k] > hbest){ hbest = hov[k]; hkey = k; } });
      const interp = {}; let total = 0, legendTotal = 0;
      active.forEach(function(k){
        const v = Math.max(0, Number(counts[k] || 0));
        const vis = self.shown(k);  // (a type hidden from the legend: out of the ring and the total)
        interp[k] = v * st * vis; total += v * st * vis;
      });
      active.forEach(function(k){ legendTotal += interp[k]; });
      const opac = Math.max(0, Math.min(100, this.options.chart_opacity_pct)) / 100 * ga;
      const cx = pieX + PIE / 2, cy = pieY + PIE / 2, rad = (PIE - RING_W) / 2;
      // Bars (Card Counts): a bar of each kind in the donut's square, its count over it
      const bars = !!this.payload.bars_view && !this.payload.order;
      this.xf.bars = null;
      if (bars && total > 0){
        const ks = this.order().filter(function(k){ return active.indexOf(k) >= 0; });
        let mx = 0; ks.forEach(function(k){ mx = Math.max(mx, Number(counts[k] || 0) * self.shown(k)); });
        const slot = PIE / Math.max(1, ks.length), bw = slot * 0.62, top = 14, base = pieY + PIE, rects = [];
        ctx.textAlign = 'center'; ctx.textBaseline = 'bottom'; ctx.font = '9px ' + FONT_FAMILY;
        ks.forEach(function(k, i){
          const x = pieX + i * slot + (slot - bw) / 2, bh = mx > 0 ? interp[k] / mx * (PIE - top) : 0, hk = hov[k] || 0;
          rects.push({k: k, x: x, w: bw, y: pieY, h: PIE});
          const fill = U.rgba(self.color(k), opac * (1 - 0.45 * hpeak * (1 - hk)));
          if (bh > 0.5){ if (U.roundedBar) U.roundedBar(ctx, x, base - bh, bw, bh, fill); else { ctx.fillStyle = fill; ctx.fillRect(x, base - bh, bw, bh); } }
          const va = self.shown(k);
          if (va > 0.02){
            ctx.save(); ctx.globalAlpha *= va; ctx.fillStyle = C.text_secondary;
            ctx.fillText(U.formatNum(Math.round(interp[k] / va)), x + bw / 2, base - bh - 2);
            ctx.restore();
          }
        });
        this.xf.bars = rects;
      }
      if (total > 0 && !bars){
        // the slices at their own size from the start, a sweep round the ring showing them one after the other
        // (scaled by t, every slice came at once squeezed into a short arc, the small ones flashing by, then spread)
        let start = -Math.PI / 2, reached = 0;
        const reveal = 360 * 16 * t;
        this.order().forEach(function(k){
          if (active.indexOf(k) < 0) return;
          const val = interp[k];
          if (val <= 0.0001) return;
          const fraction = val / total;
          if (fraction <= 0.000001) return;
          const drawn = fraction * 360 * 16;           // 1/16 degree, clockwise
          const gap = Math.min(SLICE_GAP, drawn * 0.3);
          const span = Math.min(drawn - gap, reveal - reached - gap / 2);
          reached += drawn;
          if (span > 1){
            const hk = hov[k] || 0;
            ctx.strokeStyle = U.rgba(self.color(k), opac * (1 - 0.45 * hpeak * (1 - hk)));
            ctx.lineWidth = RING_W + 4 * hk; ctx.lineCap = 'butt';
            ctx.beginPath();
            ctx.arc(cx, cy, rad, start + (gap / 2) / 16 * Math.PI / 180, start + (gap / 2 + span) / 16 * Math.PI / 180);
            ctx.stroke();
          }
          start += drawn / 16 * Math.PI / 180;
        });
      }
      // the empty deck's thin circle: it fades in as the ring closes and out as it opens (it came at once at the end)
      const ea = E ? 1 - E.mul : (total > 0 ? 0 : 1);
      if (ea > 0.005 && !bars){
        ctx.save(); ctx.globalAlpha *= ea;
        ctx.strokeStyle = '#555555'; ctx.lineWidth = 2;
        ctx.beginPath(); ctx.arc(cx, cy, PIE / 2, 0, Math.PI * 2); ctx.stroke();
        ctx.restore();
      }
      // total in the middle (Bars: the counts over them instead)
      if (!bars){
      ctx.textBaseline = 'middle'; ctx.textAlign = 'center';
      const holeW = Math.max(40, PIE - RING_W * 2 - 8);
      // a share in the middle (Today's Retention: the passed part), else the total of cards
      const cen = this.payload.center;
      const share = cen && !hkey && legendTotal > 0 ? Math.round(Number(counts[cen.key] || 0) * st / legendTotal * 100) : null;
      const cfmt = this.payload.fmt || function(v){ return U.formatNum(Math.round(v)); };
      const mainTxt = share !== null ? share + '%' : cfmt(hkey ? Number(counts[hkey] || 0) * st : legendTotal);
      let mainFs = 20;
      ctx.font = 'bold ' + mainFs + 'px ' + FONT_FAMILY;
      const mw0 = ctx.measureText(mainTxt).width;
      if (mw0 > holeW){ mainFs = Math.max(11, mainFs * holeW / mw0); ctx.font = 'bold ' + mainFs.toFixed(1) + 'px ' + FONT_FAMILY; }
      ctx.fillStyle = C.text_primary;
      const subTxt = hkey ? (this.label(hkey) + ' ' + Math.round(legendTotal > 0 ? Number(counts[hkey] || 0) * st / legendTotal * 100 : 0) + '%')
        : (share !== null ? DD.t(cen.label) : (this.payload.center_word != null ? this.payload.center_word : 'cards'));
      const subBaseFs = hkey ? 10 : 11;
      ctx.font = subBaseFs + 'px ' + FONT_FAMILY;
      const twoLines = !!(hkey && ctx.measureText(subTxt).width > holeW - 2);
      ctx.font = 'bold ' + mainFs.toFixed(1) + 'px ' + FONT_FAMILY;
      ctx.fillText(mainTxt, cx, pieY + PIE / 2 + (!subTxt ? 0 : (twoLines ? -11 : -4)));
      ctx.fillStyle = C.text_secondary;
      if (twoLines){
        const lbl = this.label(hkey), pctTxt = Math.round(legendTotal > 0 ? Number(counts[hkey] || 0) * st / legendTotal * 100 : 0) + '%';
        let lfs = 9.5;
        ctx.font = lfs + 'px ' + FONT_FAMILY;
        const lw0 = ctx.measureText(lbl).width;
        if (lw0 > holeW - 2){ lfs = Math.max(7.5, lfs * (holeW - 2) / lw0); ctx.font = lfs.toFixed(1) + 'px ' + FONT_FAMILY; }
        ctx.fillText(lbl, cx, pieY + PIE / 2 + 8);
        ctx.font = 'bold 9.5px ' + FONT_FAMILY;
        ctx.fillText(pctTxt, cx, pieY + PIE / 2 + 20);
      } else if (subTxt){
        let sfs = subBaseFs;
        ctx.font = sfs + 'px ' + FONT_FAMILY;
        const sw0 = ctx.measureText(subTxt).width;
        if (sw0 > holeW - 2){ sfs = Math.max(7.5, sfs * (holeW - 2) / sw0); ctx.font = sfs.toFixed(1) + 'px ' + FONT_FAMILY; }
        ctx.fillText(subTxt, cx, pieY + PIE / 2 + 13);
      }
      const pv = this.view || this.payload;
      // the change from the period before (an option): "+3.1", points of retention, under the name
      const chA = pv.chA != null ? pv.chA : (pv.show_change ? 1 : 0);
      if (chA > 0.01 && share !== null && pv.before != null && !E){
        const exact = Number(counts[cen.key] || 0) * st / legendTotal * 100, diff = Math.round((exact - pv.before) * 10) / 10;
        ctx.save(); ctx.globalAlpha *= t * chA;
        ctx.font = 'bold 10px ' + FONT_FAMILY;
        ctx.fillStyle = diff > 0 ? this.color('pass') : diff < 0 ? this.color('fail') : C.text_secondary;
        ctx.fillText((diff > 0 ? '+' : diff < 0 ? '−' : '±') + Math.abs(diff).toFixed(1), cx, pieY + PIE / 2 + 6 + 7 + 14);
        ctx.restore();
      }
      // the target (FSRS's desired retention): a mark across the ring where the passed part should end
      // (an option: hidden, it fades out)
      const tg = pv.target, tgA = pv.tgA != null ? pv.tgA : (pv.show_target === false ? 0 : 1);
      if (tg && tgA > 0.01 && total > 0 && !hkey){
        const ang = -Math.PI / 2 + tg * Math.PI * 2, r0 = rad - RING_W / 2 - 3, r1 = rad + RING_W / 2 + 3;
        ctx.save(); ctx.globalAlpha *= Math.min(1, t) * tgA;
        ctx.strokeStyle = C.text_primary; ctx.lineWidth = 2; ctx.lineCap = 'round';
        ctx.beginPath(); ctx.moveTo(cx + Math.cos(ang) * r0, cy + Math.sin(ang) * r0); ctx.lineTo(cx + Math.cos(ang) * r1, cy + Math.sin(ang) * r1); ctx.stroke();
        ctx.restore();
      }
      }
      ctx.restore();
      this.iconRect = null; this.panelRect = null; this.legendHits = [];
      if (!inline){
        // the legend that does not fit beside the donut is a small list icon in the
        // corner; hovered, it opens the list of card types over the chart
        if (showLegend) this._legendOverlay(ctx, w, h, rows, interp, legendTotal, counts);
        return;
      }

      // legend
      let legendScale, legendXStart, legendY, legendRight;
      if (horizontal){
        legendScale = scale;
        const pieRight = tx + (pieX + PIE) * scale;
        legendXStart = pieRight + Math.max(6, 8 * legendScale);
        legendY = ty + Math.max(8, 10 * legendScale);
        legendRight = tx + totalScaledW - Math.max(4, 4 * legendScale);
      } else {
        legendScale = scale;
        legendXStart = tx + 5 * scale;
        legendY = ty + ((pieY + PIE + 15) * scale);
        legendRight = tx + logicalW * scale - Math.max(5, 5 * scale);
      }
      const widthScale = Math.max(0.75, Math.min(1.5, Math.max(1, legendRight - legendXStart) / 130));
      let fontPx = Math.max(9, Math.min(18, Math.round(12 * Math.min(legendScale, widthScale))));
      let rowH = Math.max(fontPx + 4, Math.round((horizontal ? 16 : 18) * legendScale));
      let keys = rows.slice();
      if (horizontal){
        const room = h - legendY - 4;
        if ((keys.length + 1) * rowH + 4 > room){
          const nz = keys.filter(function(k){ return (counts[k] || 0) > 0; });
          if (nz.length) keys = nz;
          rowH = Math.max(10, Math.min(rowH, Math.trunc((room - 4) / (keys.length + 1))));
          fontPx = Math.max(7, Math.min(fontPx, rowH - 3));
        }
      }
      // beside the donut, the legend is centred on it (it sat at the card's top, the space under it empty)
      if (horizontal){
        const blockH = (keys.length + 1) * rowH + 4, mid = ty + (pieY + PIE / 2) * scale;
        legendY = Math.max(legendY, Math.min(mid - blockH / 2, h - 4 - blockH));
      }
      const setFont = function(bold){ ctx.font = (bold ? 'bold ' : '') + fontPx + 'px ' + FONT_FAMILY; };
      setFont(false);
      const pf = self.payload.fmt, pa = legendTotal > 0 ? this.pctNow() : 0;
      // the count, and its share of the total in a column of its own right of it (Show Percentages), pa of it shown
      const fmtc = function(v){ return pf ? pf(v) : U.formatNum(Math.round(v)); };
      const fmtp = function(v){ const p = legendTotal > 0 ? v * 100 / legendTotal : 0; return U.trimNum(p, p < 10 ? 1 : 0) + '%'; };
      const tw = function(s){ return ctx.measureText(s).width; };
      let pctColW = 0;
      const pctShift = function(){ return pa > 0.001 ? pa * (tw('  ') + pctColW) : 0; };
      const measureBoth = function(){
        setFont(true);
        maxLabelW = Math.max.apply(null, keys.map(function(k){ return tw(self.label(k)); }).concat([tw('Total')]));
        setFont(false);
        pctColW = pa > 0.001 ? Math.max.apply(null, keys.map(function(k){ return tw(fmtp(counts[k] || 0)); }).concat([tw(fmtp(legendTotal))])) : 0;
        maxCountW = Math.max.apply(null, keys.map(function(k){ return tw(fmtc(counts[k] || 0)); }).concat([tw(fmtc(legendTotal))])) + pctShift();
      };
      // (vis: how much of a type hidden from the legend shows; out of the total, its % goes as it is struck through)
      const countAt = function(v, x, y, vis){
        const sh = pctShift(), a = pa * (vis === undefined ? 1 : vis);
        ctx.fillText(fmtc(v), x - sh, y);
        if (sh > 0 && a > 0.01){ ctx.save(); ctx.globalAlpha *= a; ctx.fillText(fmtp(v), x, y); ctx.restore(); }
      };
      let maxLabelW = 0, maxCountW = 0;
      measureBoth();
      if (horizontal){
        const rightLim = w - 10;
        const labelGap = Math.max(9, 12 * legendScale);
        const xMin = tx + (pieX + PIE) * scale + 4;
        while (xMin + labelGap + maxLabelW + 12 + maxCountW + 2 > rightLim && fontPx > 6){
          fontPx -= 1;
          measureBoth();
        }
        const need = labelGap + maxLabelW + 12 + maxCountW + 2;
        if (legendXStart + need > rightLim) legendXStart = Math.max(xMin, rightLim - need);
        legendRight = Math.min(Math.max(legendRight, legendXStart + need), rightLim);
        // with room on the right, the legend stands a little away from the donut: half the free
        // room, at most 24 px at this scale
        const shift = Math.max(0, Math.min((rightLim - legendRight) * 0.5, 24 * legendScale));
        legendXStart += shift; legendRight += shift;
      }
      const labelX = legendXStart + Math.max(9, 12 * legendScale);
      const countRight = legendRight;
      setFont(false);
      const shownCountW = Math.max.apply(null, keys.map(function(k){ return tw(fmtc(interp[k] || 0)); }).concat([tw(fmtc(legendTotal))])) + pctShift();
      const maxLabelAvail = Math.max(20, countRight - Math.max(maxCountW, shownCountW) - 10 - labelX);
      const fitLabel = function(s){
        if (tw(s) <= maxLabelAvail) return s;
        let out = s;
        while (out.length > 1 && tw(out + '…') > maxLabelAvail) out = out.slice(0, -1);
        return out + '…';
      };
      const text = C.text_primary;
      ctx.textBaseline = 'middle';
      let y = legendY;
      keys.forEach(function(k){
        const box = rowH <= 16 ? 7 : 8, vis = self.shown(k);
        if (self.kindsToggle) self.legendHits.push({k: k, x: legendXStart - 2, y: y, w: countRight - legendXStart + 4, h: rowH});
        ctx.save(); ctx.globalAlpha *= 0.4 + 0.6 * vis;
        ctx.fillStyle = self.color(k);
        ctx.fillRect(legendXStart, y + (rowH - box) / 2, box, box);
        ctx.fillStyle = text; ctx.textAlign = 'left'; setFont(true);
        const lbl = fitLabel(self.label(k));
        ctx.fillText(lbl, labelX, y + rowH / 2);
        if (vis < 0.999) self._strike(ctx, labelX, y + rowH / 2, tw(lbl), 1 - vis, text);
        setFont(false); ctx.textAlign = 'right';
        countAt(vis > 0.001 ? (interp[k] || 0) / vis : Number(counts[k] || 0) * st, countRight, y + rowH / 2, vis);
        ctx.restore();
        y += rowH;
      });
      y += 4;
      ctx.fillStyle = text; ctx.textAlign = 'left'; setFont(true);
      ctx.fillText('Total', labelX, y + rowH / 2);
      setFont(false); ctx.textAlign = 'right';
      countAt(legendTotal, countRight, y + rowH / 2);
    }
  }

  // a hidden type's name struck through (the line drawn from the left as it is hidden)
  Chart.prototype._strike = function(ctx, x, y, w, a, color){
    ctx.save(); ctx.strokeStyle = color; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(x, Math.round(y) + 0.5); ctx.lineTo(x + w * Math.min(1, a), Math.round(y) + 0.5); ctx.stroke();
    ctx.restore();
  };
  Chart.prototype._legendOverlay = function(ctx, w, h, keys, interp, total, counts){
    const C = this.colors, icon = {x: w - 24, y: 4, w: 20, h: 18}, self = this;
    this.iconRect = icon;
    if (!this.legendHot){
      ctx.save(); ctx.strokeStyle = C.text_secondary || '#a1a1aa'; ctx.lineWidth = 1.6; ctx.lineCap = 'round';
      for (let i = 0; i < 3; i++){ const y = Math.trunc(icon.y + 5 + i * 4) + 0.5; ctx.beginPath(); ctx.moveTo(Math.trunc(icon.x + 5), y); ctx.lineTo(Math.trunc(icon.x + icon.w - 5), y); ctx.stroke(); }
      ctx.restore();
      return;
    }
    let shown = keys.slice(), px = 11, rowH = 16;
    const pad = 8, room = h - 8 - 2 * pad;
    if ((shown.length + 1) * rowH + 4 > room){
      const nz = keys.filter(function(k){ return (counts[k] || 0) > 0; }); if (nz.length) shown = nz;
      rowH = Math.max(11, Math.min(rowH, Math.trunc((room - 4) / (shown.length + 1))));
      px = Math.max(8, Math.min(px, rowH - 3));
    }
    const pf = this.payload.fmt, pa = total > 0 ? this.pctNow() : 0;
    const fmtc = function(v){ return pf ? pf(v) : U.formatNum(Math.round(v)); };
    const fmtp = function(v){ const p = total > 0 ? v * 100 / total : 0; return U.trimNum(p, p < 10 ? 1 : 0) + '%'; };
    ctx.save();
    const setFont = function(bold){ ctx.font = (bold ? 'bold ' : '') + px + 'px ' + FONT_FAMILY; };
    setFont(true);
    const maxL = Math.max.apply(null, shown.map(function(k){ return ctx.measureText(self.label(k)).width; }).concat([ctx.measureText('Total').width]));
    setFont(false);
    // Show Percentages: a % column right of the counts, as beside the donut
    const pctColW = pa > 0.001 ? Math.max.apply(null, shown.map(function(k){ return ctx.measureText(fmtp(interp[k] || 0)).width; }).concat([ctx.measureText(fmtp(total)).width])) : 0;
    const sh = pa > 0.001 ? pa * (ctx.measureText('  ').width + pctColW) : 0;
    const countAt = function(v, x, y, vis){
      const a = pa * (vis === undefined ? 1 : vis);
      ctx.fillText(fmtc(v), x - sh, y);
      if (sh > 0 && a > 0.01){ ctx.save(); ctx.globalAlpha *= a; ctx.fillText(fmtp(v), x, y); ctx.restore(); }
    };
    const maxC = Math.max.apply(null, shown.map(function(k){ return ctx.measureText(fmtc(interp[k] || 0)).width; }).concat([ctx.measureText(fmtc(total)).width])) + sh;
    const box = rowH <= 16 ? 7 : 8;
    const pw = Math.min(pad + box + 6 + maxL + 12 + maxC + pad, w - 8), ph = Math.min(2 * pad + (shown.length + 1) * rowH + 4, h - 8);
    const P = {x: w - 4 - pw, y: 4, w: pw, h: ph};
    this.panelRect = P;
    ctx.fillStyle = U.rgba(C.bg || '#222222', 242 / 255);
    ctx.strokeStyle = C.tooltip_border || '#555555'; ctx.lineWidth = 1;
    ctx.beginPath();
    if (ctx.roundRect) ctx.roundRect(P.x + 0.5, P.y + 0.5, P.w - 1, P.h - 1, 6); else ctx.rect(P.x + 0.5, P.y + 0.5, P.w - 1, P.h - 1);
    ctx.fill(); ctx.stroke();
    const lx = P.x + pad, labelX = lx + box + 6, countRight = P.x + P.w - pad;
    ctx.textBaseline = 'middle';
    let y = P.y + pad;
    shown.forEach(function(k){
      const vis = self.shown(k);
      if (self.kindsToggle) self.legendHits.push({k: k, x: P.x + 2, y: y, w: P.w - 4, h: rowH});
      ctx.save(); ctx.globalAlpha *= 0.4 + 0.6 * vis;
      ctx.fillStyle = self.color(k); ctx.fillRect(lx, y + (rowH - box) / 2, box, box);
      ctx.fillStyle = C.text_primary; ctx.textAlign = 'left'; setFont(true); ctx.fillText(self.label(k), labelX, y + rowH / 2);
      if (vis < 0.999) self._strike(ctx, labelX, y + rowH / 2, ctx.measureText(self.label(k)).width, 1 - vis, C.text_primary);
      setFont(false); ctx.textAlign = 'right'; countAt(vis > 0.001 ? (interp[k] || 0) / vis : Number(counts[k] || 0), countRight, y + rowH / 2, vis);
      ctx.restore();
      y += rowH;
    });
    y += 4;
    ctx.fillStyle = C.text_primary; ctx.textAlign = 'left'; setFont(true); ctx.fillText('Total', labelX, y + rowH / 2);
    setFont(false); ctx.textAlign = 'right'; countAt(total, countRight, y + rowH / 2);
    ctx.restore();
  };
  Chart.prototype.legendAt = function(x, y){
    const inR = function(r){ return r && x >= r.x && x <= r.x + r.w && y >= r.y && y <= r.y + r.h; };
    return inR(this.iconRect) || (this.legendHot && inR(this.panelRect));
  };

  const CHEV = '';
  function head(el, payload){
    if (!el) return;
    const pills = el.querySelector('.dd-pills');
    if (!pills) return;
    const acc = (DD.theme.chart && DD.theme.chart.accent) || '#3b82f6';
    el.style.setProperty('--dd-accent-b', U.rgba(acc, 0.6));
    el.style.setProperty('--dd-accent-f', U.rgba(acc, 0.12));
    pills.innerHTML = '';
    const b = document.createElement('button');
    b.className = 'dd-pill' + (payload.separate ? ' on' : '');
    b.textContent = 'Sep. Susp.';
    pills.appendChild(b);
    return b;
  }

  // First Answer Retention: the kind of cards in the header (a pill, its menu; the Deep Dive's right-click menu has it
  // too), its title from its period (the payload's), each kind's share, the period before and FSRS's desired retention
  // in the stats. Its period is the chart's: the Deep Dive's (and its zoom), or a pinned widget's own.
  const KIND_NAMES = {all: 'All', learn: 'Learning', young: 'Young', mature: 'Mature'};
  const RET_KINDS = ['all', 'learn', 'young', 'mature'];
  // the menu items (DD.menu radios): 'rk:' a kind; 'rchg' the change from the period before in the ring (a check)
  DD.retentionMenu = function(payload){
    const kind = (payload && payload.card_type) || 'all';
    return RET_KINDS.map(function(k){ return ['rk:' + k, KIND_NAMES[k], kind === k, null, 'radio']; });
  };
  // the options' checks: the change from the period before, FSRS's target (only with FSRS)
  DD.retentionOptions = function(payload){
    const o = [['rchg', 'Show Change from Period Before', !!(payload && payload.show_change), null, true]];
    if (payload && payload.target) o.push(['rtgt', 'Show FSRS Target', payload.show_target !== false, null, true]);
    return o;
  };
  // the change and the target are only drawn: shown at once on the chart (as Card Counts' Sep. Susp.), then saved;
  // the kind of cards is read in Python (its data asked again)
  const RET_APPLY = new WeakMap();
  function retentionShow(payload, key, value){
    const apply = RET_APPLY.get(payload);
    if (apply) apply(key, value);
    DD.call('set_setting', {section: 'todays_retention', key: key, value: value}).catch(function(){});
  }
  // on: the check's state in the menu. The Deep Dive's menu stays open on its checks: a second click in it read the
  // chart as it was when the menu opened, and sent the same value again (the option seemed not to change)
  DD.retentionPick = function(payload, k, on){
    // the chart's payload now (the one given is the menu's, maybe older)
    const cur = (payload && payload._now && payload._now()) || payload;
    if (k === 'rchg'){ retentionShow(cur, 'show_change', on === undefined ? !cur.show_change : !!on); return true; }
    if (k === 'rtgt'){ retentionShow(cur, 'show_target', on === undefined ? cur.show_target === false : !!on); return true; }
    if (typeof k !== 'string' || k.indexOf('rk:') !== 0) return false;
    if (k.slice(3) !== (cur.card_type || 'all')) DD.setWidgetSetting('todays_retention', 'card_type', k.slice(3));
    return true;
  };
  function pct(v){ return (Math.round(v * 10) / 10) + '%'; }
  function retentionHead(el, payload){
    if (!el) return;
    el._retPayload = payload;  // for the Deep Dive's right-click menu (app.js)
    const st = el.querySelector('.dd-stat');
    if (st){
      const bk = payload.by_kind || {}, parts = [];
      ['learn', 'young', 'mature'].forEach(function(k){
        const v = bk[k] || [0, 0], n = (v[0] || 0) + (v[1] || 0);
        if (n > 0) parts.push(DD.t('{name}: {value}', {name: DD.t(KIND_NAMES[k]), value: Math.round(v[0] * 100 / n) + '%'}));
      });
      if (payload.before != null) parts.push(DD.t('{name}: {value}', {name: payload.before_label, value: pct(payload.before)}));
      const tgOn = payload.target && payload.show_target !== false;
      if (tgOn) parts.push(DD.t('Target: {value}', {value: pct(payload.target * 100)}));
      st.textContent = parts.join('  ·  ');
      st.title = '';  // (no title tooltip: over the stats icon it came on top of the list; the help says what Target is)
    }
    const pills = el.querySelector('.dd-pills'); if (!pills) return;
    pills.innerHTML = '';
    // a pill of the kind of cards (read in Python), with its menu; what the ring shows (drawn only: the change from the
    // period before, FSRS's target) is in the chart's options icon (app.js cardMenu, pinned.js ownMenu) and its right
    // click
    const pill = function(label, on, tip, items, ico){
      const b = document.createElement('button');
      b.className = 'dd-pill dd-pill-opt' + (on ? ' on' : '') + (ico ? ' dd-pill-ico' : '');
      b.innerHTML = ico || ('<span></span>' + CHEV);
      if (!ico) b.firstChild.textContent = DD.t(label);
      b.title = DD.t(tip);
      b.addEventListener('click', function(e){
        e.stopPropagation();
        const r = b.getBoundingClientRect();
        DD.menu({x: r.left, y: r.bottom + 2}, items(), function(k, on){ DD.retentionPick(payload, k, on); });
      });
      pills.appendChild(b);
    };
    const kind = payload.card_type || 'all';
    pill(KIND_NAMES[kind] || 'All', kind !== 'all', 'The cards counted: all, or one kind', function(){ return DD.retentionMenu(payload); });
  }

  function mountPie(type){ return {
    mount: function(el, ctx){
      el.innerHTML = '<div class="dd-plot"><canvas></canvas><div class="dd-tip"></div></div>';
      const plot = el.firstChild;
      // a click on a slice: its cards in the browser (Card Counts: the cards in that state; First Answer Retention: the
      // cards whose first answer of a day of the period passed / failed, of the kind shown: browser_search.reviews_sql)
      plot._ddBrowse = function(){
        const k = chart.hoverKey; if (!k) return null;
        if (type === 'card_counts') return {pie: k};
        if (type === 'dist_pie') return chart.payload.browse ? chart.payload.browse(k) : null;
        const p = chart.payload || {}; if (!p.range || (k !== 'pass' && k !== 'fail')) return null;
        const revs = {ms: p.range, first: true, passed: k === 'pass'};
        if (p.card_type && p.card_type !== 'all') revs.kind = p.card_type;
        return {revs: revs};
      };
      const chart = new Chart(plot, ctx.data, DD.theme.chart, ctx.options || {});
      // a distribution's pie (discrete.js piePayload): its slices hidden kept in its own setting (hide_save)
      chart.kindsToggle = type === 'card_counts' || (type === 'dist_pie' && !!(ctx.data && ctx.data.hide_save));
      // Card Counts, a distribution's pie: a click on a row of its legend hides that card type / slice, or shows it
      // again; drawn only: shown at once, then saved
      chart.canvas.addEventListener('click', function(ev){
        const r = chart.canvas.getBoundingClientRect(), k = chart.legendRowAt(ev.clientX - r.left, ev.clientY - r.top);
        if (!k) return;
        ev.stopPropagation(); ev.preventDefault();
        const hid = chart.toggleKind(k);
        if (!hid) return;
        const save = type === 'card_counts' ? {section: 'card_counts', key: 'hidden_kinds'} : chart.payload.hide_save;
        if (save && save.done) save.done(hid);
        if (save) DD.call('set_setting', {section: save.section, key: save.key, value: hid}).catch(function(){});
        state.last = true; DD.frame.kick();
      }, true);
      // the chart's payload and a drawn option changed at once (the Legend Layout): DD.pieLegendPick
      plot._ddPie = {payload: function(){ return chart.payload; }, set: function(key, value){
        if (key === 'legend_pct') chart.pctTo(!!value);  // (its % column fades in / out)
        else { const o = {}; o[key] = value; chart.payload = Object.assign({}, chart.payload, o); }
        bindSep(); state.last = true; DD.frame.kick(); }};
      // Sep. Suspended: suspended and buried cards get slices of their own (the pie morphs to it)
      const bindSep = function(){
        if (type === 'dist_pie') return;  // (no header of its own)
        if (type !== 'card_counts'){
          try { Object.defineProperty(chart.payload, '_now', {value: function(){ return chart.payload; }, configurable: true}); } catch (e) {}
          RET_APPLY.set(chart.payload, function(key, value){
            const o = {}; o[key] = value;
            chart.morph = {from: chart.view || chart.payload, start: null, k: DD.calm ? DD.calm() : 1};
            chart.payload = Object.assign({}, chart.payload, o);
            bindSep(); state.last = true; DD.frame.kick();
          });
          retentionHead(ctx.head, chart.payload); return;
        }
        const b = head(ctx.head, chart.payload); if (!b) return;
        countsPills(b);
        b.addEventListener('click', function(){
          const on = !chart.payload.separate, old = chart.payload;
          chart.morph = {from: old, start: null, k: 1};
          chart.payload = Object.assign({}, chart.payload, {separate: on});
          b.classList.toggle('on', on);
          DD.call('pie_separate', {on: on}).catch(function(){});
          state.last = true; DD.frame.kick();
        });
      };
      if (!ctx.animate) chart.progress = 1;
      const state = {start: null, last: true};
      // Card Counts at a date: its date pill opens a calendar
      // (discrete.js DD.dayPicker) from the first review to today; the day picked stays while the chart lives
      const PICK = {};
      let picked = null, askSeq = 0, api = null;
      // Optional Day Slider under Card Counts (off by default; toggled via right-click -> Day Slider, as Time Machines)
      let tmRow = null, tmInp = null, tmBase = null, tmTimer = null;
      const dayOrd = function(iso){ const p = String(iso || '').split('-').map(Number); return Math.floor(Date.UTC(p[0], (p[1] || 1) - 1, p[2] || 1) / 86400000); };
      const dayIso = function(n){ return new Date(n * 86400000).toISOString().slice(0, 10); };
      const tmFill = function(){ if (!tmInp) return; const mx = Number(tmInp.max) || 0; tmInp.style.setProperty('--p', (mx > 0 ? Number(tmInp.value) / mx * 100 : 100) + '%'); };
      const syncSlider = function(p){
        if (!tmRow || !tmInp) return;
        const ok = !!(p && p.day_slider && p.first && p.today && p.first < p.today && ctx.fetch);
        tmRow.hidden = !ok;
        if (!ok) return;
        tmBase = dayOrd(p.first);
        const span = Math.max(0, dayOrd(p.today) - tmBase);
        tmInp.max = String(span);
        tmInp.value = String(Math.max(0, Math.min(span, dayOrd(p.date || p.today) - tmBase)));
        tmFill();
      };
      if (type === 'card_counts' && ctx.fetch){
        el.classList.add('dd-tmb');
        tmRow = document.createElement('div'); tmRow.className = 'dd-tm'; tmRow.hidden = true;
        tmRow.innerHTML = '<input type="range" min="0" max="0" step="1">';
        tmInp = tmRow.firstChild;
        ['pointerdown', 'mousedown', 'touchstart', 'click'].forEach(function(ev){ tmRow.addEventListener(ev, function(e){ e.stopPropagation(); }); });
        tmInp.addEventListener('input', function(){
          if (tmBase == null) return;
          tmFill();
          const at = dayIso(tmBase + Number(tmInp.value));
          clearTimeout(tmTimer);
          tmTimer = setTimeout(function(){ askDay(at); }, 30);
        });
        el.appendChild(tmRow);
      }
      const askDay = function(at){
        if (!ctx.fetch) return;
        picked = at;
        const my = ++askSeq;
        ctx.fetch({at: at}).then(function(d){
          if (my === askSeq && d && !d.error && api) api.update(d, PICK); }).catch(function(){});
      };
      const countsPills = function(b){
        const p = chart.payload, pills = b.parentNode;
        if (p.first && p.today && p.first < p.today && DD.dayPicker && ctx.fetch){
          const d = document.createElement('button');
          d.className = 'dd-pill' + (p.past ? ' on' : '');
          if (p.past) d.setAttribute('data-nt', '');
          // its chevron: a click opens a calendar (as the Time Machines' date pill)
          d.innerHTML = (p.past ? dayText(p.date) : 'Today') + '<svg class="dd-pill-chev" width="8" height="6" viewBox="0 0 8 6"><path d="M1 1.5L4 4.5L7 1.5" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/></svg>';
          d.title = 'Day shown';
          d.addEventListener('click', function(e){ e.stopPropagation(); DD.dayPicker(d, p.date || p.today, p.first, p.today, askDay); });
          pills.insertBefore(d, b);
        }
        // its views, Pie | Bars (the counts as bars in the donut's place, drawn only, grown in as the donut's intro):
        // the one shown lit, a click on the other shows it (dd-pview: not an option turned on)
        const pv = document.createElement('button'), bb = document.createElement('button');
        pv.className = 'dd-pill dd-pview' + (p.bars_view ? '' : ' on');
        pv.textContent = 'Pie';
        bb.className = 'dd-pill dd-pview' + (p.bars_view ? ' on' : '');
        bb.textContent = 'Bars';
        bb.title = 'The counts as bars';
        const view = function(on){
          if (!!chart.payload.bars_view === on) return;
          chart.payload = Object.assign({}, chart.payload, {bars_view: on});
          bb.classList.toggle('on', on); pv.classList.toggle('on', !on);
          chart.morph = null; chart.view = null;
          if (ctx.animate){ chart.progress = 0; state.start = null; }
          DD.call('set_setting', {section: 'card_counts', key: 'bars_view', value: on}).catch(function(){});
          state.last = true; DD.frame.kick();
        };
        pv.addEventListener('click', function(){ view(false); });
        bb.addEventListener('click', function(){ view(true); });
        pills.insertBefore(pv, b); pills.insertBefore(bb, b);
      };
      bindSep();
      syncSlider(chart.payload);
      // Bars (Card Counts): a tooltip over the bar hovered, its kind, count and share (the donut shows them in its
      // middle, which the bars do not have)
      if (DD.hover) DD.hover.attach(el.querySelector('.dd-plot') || el, chart, {
        index: function(mx, my){ const k = chart.xf && chart.xf.bars ? chart.sliceAt(mx, my) : null; return k ? chart.order().indexOf(k) : -1; },
        rows: function(i){
          const k = chart.order()[i], counts = chart.payload.counts || {}, n = Number(counts[k] || 0);
          let tot = 0; chart.activeKeys().forEach(function(a){ tot += Math.max(0, Number(counts[a] || 0)) * chart.shown(a); });
          return [{header: true, text: chart.label(k), color: chart.color(k)},
            {text: DD.tn('{count} card', '{count} cards', n, {count: U.formatNum(n)}), value: (tot > 0 ? U.trimNum(n * 100 / tot, 1) : '0') + '%'}];
        },
        redraw: function(){ state.last = true; DD.frame.kick(); },
      });
      chart.canvas.addEventListener('mousemove', function(ev){
        const r = chart.canvas.getBoundingClientRect(), x = ev.clientX - r.left, y = ev.clientY - r.top;
        // over the list icon (or its open list) the list shows, no slice is hovered
        const hot = !!chart.legendAt(x, y);
        chart.canvas.style.cursor = chart.legendRowAt(x, y) ? 'pointer' : '';  // (a legend row: a click hides its type)
        if (hot !== !!chart.legendHot){ chart.legendHot = hot; state.last = true; }
        chart.setHover(hot ? null : chart.sliceAt(x, y)); DD.frame.kick();
      });
      chart.canvas.addEventListener('mouseleave', function(){ if (chart.legendHot){ chart.legendHot = false; state.last = true; } chart.setHover(null); DD.frame.kick(); });
      function frame(now){
        // its intro not played yet (it waited out of view) and new data came meanwhile: the intro alone shows it
        // (the change's morph ran with it, a second animation over the first)
        if (chart.progress < 1 && state.start === null && (chart.morph || chart.etr)){ if (DD.dev) DD.trace('ANIMTRACE pie intro not played yet: its morph dropped, the intro shows the new data'); chart.morph = null; chart.etr = null; chart.view = null; }
        const ha = chart.stepHover(now) | chart.stepHide(now) | chart.stepPct(now);
        if (chart.progress < 1){ if (state.start === null) state.start = now; chart.progress = Math.min(1, (now - state.start) / DD.intro(500)); }
        let mo = false;
        if (chart.etr){
          const E = chart.etr; if (E.start === null) E.start = now;
          const u = Math.min(1, (now - E.start) / (300 * (E.k || 1))), p = 0.5 - 0.5 * Math.cos(Math.PI * u), s = smooth(p);  // InOutSine, smooth01
          if (u >= 1) chart.etr = null; else { E.mul = E.from ? s : 1 - s; mo = true; }
        }
        if (chart.morph){
          const m = chart.morph; if (m.start === null) m.start = now;
          // 300 ms, every chart's change; InOutCubic alone (a smoothstep over it made the middle fly by)
          const t = Math.min(1, (now - m.start) / (300 * (m.k || 1)));
          if (t >= 1){ chart.morph = null; chart.view = null; } else {
            const tt = t < 0.5 ? 4*t*t*t : 1 - Math.pow(-2*t + 2, 3) / 2, a = (m.from && m.from.counts) || {}, b = chart.payload.counts || {}, c = {};
            Object.keys(b).concat(Object.keys(a)).forEach(function(k){ const o = a[k] || 0, v = b[k] || 0; c[k] = o + (v - o) * tt; });
            const lerp = function(o, v){ return (o == null || v == null) ? v : o + (v - o) * tt; };
            chart.view = Object.assign({}, chart.payload, {counts: c, before: lerp(m.from && m.from.before, chart.payload.before),
              target: lerp(m.from && m.from.target, chart.payload.target),
              chA: lerp(m.from ? (m.from.chA != null ? m.from.chA : (m.from.show_change ? 1 : 0)) : null, chart.payload.show_change ? 1 : 0),
              tgA: lerp(m.from ? (m.from.tgA != null ? m.from.tgA : (m.from.show_target === false ? 0 : 1)) : null, chart.payload.show_target === false ? 0 : 1)}); mo = true;
          }
        }
        const needs = chart.progress < 1 || mo;
        if (needs || ha || state.last) chart.draw();
        state.last = needs;
        return needs || ha;
      }
      const resizer = new ResizeObserver(function(){ DD.frame.resized(frame, function(){ chart._resize(); state.last = true; }); });
      DD.frame.observe(resizer, plot);
      if (!ctx.animate) chart.draw();
      DD.frame.add(frame);
      api = {
        machine: type === 'card_counts' && ctx.fetch ? { on: function(){ return !!(chart.payload && chart.payload.day_slider); } } : null,
        update: function(data, hint){
          // a day picked (Card Counts): a refresh asks for that day again instead (one change)
          if (type === 'card_counts' && hint !== PICK && picked && data && data.today && !data.error){
            if (data.day_slider !== undefined){ chart.payload = Object.assign({}, chart.payload, {day_slider: data.day_slider}); syncSlider(chart.payload); }
            if (picked > data.today) picked = null;
            else if (data.date !== picked){ askDay(picked); return; }
          }
          // cards in the ring: the kinds it shows only (suspended / buried apart only with Sep. Susp.). A deck whose
          // cards are all suspended has an empty ring: counted as cards, the ring stayed whole to the last frame
          // and vanished at once (its slices are shares of a total going to 0), instead of closing
          const inRing = function(p){ if (!p || !p.counts) return false; const ks = p.order || ['new', 'learn', 'relearn', 'young', 'mature'].concat(p.separate ? ['suspended', 'buried'] : []); return ks.some(function(k){ return p.counts[k] > 0; }); };
          const old = chart.payload, had = inRing(old), has = inRing(data);
          // other slices (a distribution's Pie view on another measure): its intro again, no morph
          if (hint === 'fresh' && ctx.animate && !DD._noAnim && has){
            chart.morph = null; chart.view = null; chart.etr = null; chart.progress = 0; state.start = null;
            chart.payload = data; bindSep(); syncSlider(data); state.last = true; DD.frame.kick(); return;
          }
          // to an empty deck / from one, the ring closes / opens (300 ms); the very first
          // cards keep the intro
          if (ctx.animate && !DD._noAnim && had && !has){ const shown = (chart.view || old).counts; chart.morph = null; chart.view = null; chart.etr = {from: false, counts: shown, start: null, mul: 1, k: DD.calm ? DD.calm() : 1}; }
          else if (ctx.animate && !DD._noAnim && !had && has && chart.progress >= 1){ chart.morph = null; chart.view = null; chart.etr = {from: true, counts: data.counts, start: null, mul: 0, k: DD.calm ? DD.calm() : 1}; }
          else if (ctx.animate && !had){ chart.progress = 0; state.start = null; } else if (ctx.animate && !DD._noAnim){
            chart.etr = null; chart.morph = {from: (chart.morph && chart.view) ? chart.view : old, start: null, k: DD.calm ? DD.calm() : 1}; }
          if (DD.dev) DD.trace('ANIMTRACE ' + type + ' update: ' + (chart.etr ? (chart.etr.from ? 'ring opens (from empty)' : 'ring closes (to empty)') : chart.morph ? 'morph' : chart.progress < 1 ? 'intro' : 'NO ANIMATION') + ' had=' + !!had + ' has=' + !!has + ' noAnim=' + !!DD._noAnim + ' shown=' + (el.offsetParent !== null));
          chart.payload = data; bindSep(); syncSlider(data); state.last = true; DD.frame.kick(); },
        setOptions: function(o){ Object.assign(chart.options, o); state.last = true; DD.frame.kick(); },
        setTheme: function(){ chart.colors = DD.theme.chart; state.last = true; DD.frame.kick(); },
        destroy: function(){ clearTimeout(tmTimer); askSeq++; api = null; DD.frame.remove(frame); resizer.disconnect(); el.classList.remove('dd-tmb'); el.innerHTML = ''; if (ctx.head){ const p = ctx.head.querySelector('.dd-pills'); if (p) p.innerHTML = ''; } },
      };
      return api;
    },
  }; }
  // Legend Layout (the ring charts' right-click): Auto (beside the ring while readable, else behind its icon), Always
  // next to the donut, On hover. Only drawn: shown at once, then saved (Settings has the same choice)
  const LEGEND_MODES = [['auto', 'Auto'], ['always', 'Always next to the donut'], ['hover', 'On hover']];
  DD.pieLegendMenu = function(card){
    const plot = card && card.querySelector('.dd-plot'), p = plot && plot._ddPie;
    if (!p) return null;
    const cur = p.payload().legend_mode || 'auto';
    return LEGEND_MODES.map(function(m){ return ['plg:' + m[0], m[1], cur === m[0], null, 'radio']; })
      .concat(['sep', ['plgpct', 'Show Percentages', !!p.payload().legend_pct, null, true]]);
  };
  DD.pieLegendPick = function(card, type, k, on){
    const plot = card && card.querySelector('.dd-plot'), p = plot && plot._ddPie;
    // each count's share of the total, beside it in the legend
    if (k === 'plgpct'){
      if (p) p.set('legend_pct', !!on);
      DD.call('set_setting', {section: type, key: 'legend_pct', value: !!on}).catch(function(){});
      return true;
    }
    if (typeof k !== 'string' || k.indexOf('plg:') !== 0) return false;
    const mode = k.slice(4);
    if (p && (p.payload().legend_mode || 'auto') !== mode) p.set('legend_mode', mode);
    DD.call('set_setting', {section: type, key: 'legend_mode', value: mode}).catch(function(){});
    return true;
  };
  DD.registerChart('card_counts', mountPie('card_counts'));
  DD.registerChart('todays_retention', mountPie('todays_retention'));
  // the Pie view of the distribution charts (discrete.js): this donut in their card, their payload made for it
  DD.pieMount = function(el, ctx){ return mountPie('dist_pie').mount(el, ctx); };
})();
