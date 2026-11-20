// Answer Buttons: Again / Hard / Good / Easy counts for learning, young and mature cards, grouped bars.
(function(){
  'use strict';
  const DD = window.DD;
  const U = DD.cu;
  const FONT = '12px "Segoe UI",-apple-system,BlinkMacSystemFont,sans-serif';
  const BTN = ['Again', 'Hard', 'Good', 'Easy'];
  const GROUPS = [['learning', 'Learning'], ['young', 'Young'], ['mature', 'Mature']];

  class Chart {
    constructor(root, payload, colors, options){
      this.canvas = root.querySelector('canvas');
      this.ctx = this.canvas.getContext('2d');
      this.colors = colors; this.payload = payload;
      this.options = Object.assign({chart_opacity_pct: 100}, options || {});
      this.progress = 0;
      this.hoverIdx = -1; this.rects = [];
      this._resize();
    }
    _resize(){
      const f = DD.fitCanvas(this.canvas, this.ctx), w = f.w, h = f.h, dpr = f.dpr;
      this.w = w; this.h = h;
    }
    indexAt(mx, my){
      for (let i = 0; i < this.rects.length; i++){
        const r = this.rects[i];
        if (mx >= r.x && mx <= r.x + r.w && my >= r.y && my <= r.y + r.h) return r.idx;
      }
      return -1;
    }
    tipRows(idx){
      const r = this.rects.filter(function(q){ return q.idx === idx; })[0];
      if (!r) return [];
      return [{header: true, text: r.group + ' - ' + r.btn}, {text: 'Value', value: U.formatNum(r.v)}];
    }
    draw(){
      const ctx = this.ctx, w = this.w, h = this.h, C = this.colors, css = U.cssRgba;
      ctx.clearRect(0, 0, w, h);
      const dark = !!C.is_dark;
      const data = ((this.view || this.payload) && (this.view || this.payload).data) || {};
      let maxVal = 0;
      GROUPS.forEach(function(g){ (data[g[0]] || []).forEach(function(v){ if (v > maxVal) maxVal = v; }); });
      if (maxVal <= 0) maxVal = 1;
      if (this.view && this.view.axisMax) maxVal = this.view.axisMax;  // a transition: the axis glides
      const intro = U.easeOutQuart(Math.max(0, Math.min(1, this.progress)));
      ctx.font = FONT;
      // a transition: the start and end tops of its scale and its progress (the frame below); the left margin glides
      // from the start top's width to the end one's, so the chart neither shakes sideways nor jumps at the end
      const ax = this.view && this.view.ax;
      const mlOf = (v) => Math.max(35, Math.trunc(ctx.measureText(v >= 10 ? U.formatNum(Math.trunc(v)) : (Math.round(v * 10) / 10).toFixed(1)).width) + 12);
      const ml = ax ? Math.round(mlOf(ax[0]) + (mlOf(ax[1]) - mlOf(ax[0])) * ax[2]) : mlOf(maxVal), mr = 20, mt = 10, mb = 30;
      const availW = w - ml - mr, availH = h - mt - mb;
      const grid = U.parseColor((this.options && this.options.show_grid === false ? 'rgba(0,0,0,0)' : C.grid)), txt = U.parseColor(C.text_secondary);
      const axisCol = css(txt, ((dark ? 175 : 215) / 255).toFixed(4));
      ctx.textBaseline = 'middle';
      if (DD.axisSlide && DD.axisSlide()){
        // Chart_Axis_Anim 'slide' (dd-core DD.slideTicks): round values at their heights on the scale of the moment, the
        // exact top written too; during the change of the bars (it knows its start, end and progress) they slide, the
        // old ones leave and the new ones come with the bars (a fade of its own outlasted the bars' short change)
        const fmtV = (v) => (v === 0 ? '0' : (v >= 10 ? U.formatNum(Math.trunc(v)) : U.trimNum(v, 1)));
        (ax ? DD.slideTicks(ax[0], ax[1], maxVal, ax[2], 4, availH, {tag: 'buttons'}) : DD.slideTicks(maxVal, maxVal, maxVal, 1, 4, availH, {tag: 'buttons'})).forEach((k) => {
          const y = mt + availH * (1 - k.f), yl = Math.trunc(y) + 0.5;
          ctx.globalAlpha = k.a;
          ctx.strokeStyle = css(grid, Math.min(1, grid.a * (k.f <= 0.0005 ? 2.6 : 1.5))); ctx.lineWidth = 1;
          ctx.beginPath(); ctx.moveTo(ml, yl); ctx.lineTo(w - mr, yl); ctx.stroke();
          ctx.fillStyle = axisCol; ctx.textAlign = 'right'; ctx.fillText(fmtV(k.v), ml - 8, Math.trunc(y));
        });
        ctx.globalAlpha = 1;
      } else for (let i = 0; i <= 4; i++){
        const y = mt + availH * (1 - i / 4);
        ctx.strokeStyle = css(grid, Math.min(1, grid.a * (i === 0 ? 2.6 : 1.5))); ctx.lineWidth = 1;
        const yl = Math.trunc(y) + 0.5;
        ctx.beginPath(); ctx.moveTo(ml, yl); ctx.lineTo(w - mr, yl); ctx.stroke();
        const v = maxVal * i / 4;
        ctx.fillStyle = axisCol; ctx.textAlign = 'right';
        ctx.fillText(i === 0 ? '0' : (v >= 10 ? U.formatNum(Math.trunc(v)) : U.trimNum(v, 1)), ml - 8, Math.trunc(y));
      }
      const gw = availW / GROUPS.length;
      const cols = [C.again, C.hard, C.good, C.easy];
      const spacing = 4, pad = 20;
      const barW = Math.max(2, (gw - pad * 2 - 3 * spacing) / 4);
      const alpha = Math.max(0, Math.min(100, this.options.chart_opacity_pct)) * 2.55 / 255;
      const self = this; this.rects = [];
      GROUPS.forEach(function(g, gi){
        const vals = data[g[0]] || [0, 0, 0, 0];
        for (let b = 0; b < 4; b++){
          const v = Number(vals[b] || 0);
          const bh = (v / maxVal) * availH * intro;
          const x = ml + gi * gw + pad + b * (barW + spacing);
          const y = mt + availH - bh;
          if (bh <= 0) continue;
          self.rects.push({idx: gi * 4 + b, x: x, y: y, w: barW, h: bh, group: g[1], btn: BTN[b], v: v});
          const r = Math.min(1, barW / 2, bh / 2);  // 1 px, as Anki's bars
          const hov = self.hoverIdx === gi * 4 + b;
          ctx.fillStyle = U.rgba(hov ? U.scaleV(cols[b] || '#888888', dark ? 1.3 : 1 / 1.15) : (cols[b] || '#888888'), alpha);
          ctx.beginPath();
          ctx.moveTo(x + r, y); ctx.lineTo(x + barW - r, y); ctx.quadraticCurveTo(x + barW, y, x + barW, y + r);
          ctx.lineTo(x + barW, y + bh - r); ctx.quadraticCurveTo(x + barW, y + bh, x + barW - r, y + bh);
          ctx.lineTo(x + r, y + bh); ctx.quadraticCurveTo(x, y + bh, x, y + bh - r);
          ctx.lineTo(x, y + r); ctx.quadraticCurveTo(x, y, x + r, y); ctx.closePath(); ctx.fill();
        }
      });
      // group separators and names
      ctx.save();
      ctx.setLineDash([4, 2]);
      ctx.strokeStyle = dark ? 'rgba(255,255,255,0.039)' : 'rgba(0,0,0,0.039)';
      ctx.lineWidth = 1;
      for (let i = 1; i < GROUPS.length; i++){
        const gx = Math.trunc(ml + i * gw) + 0.5;
        ctx.beginPath(); ctx.moveTo(gx, mt); ctx.lineTo(gx, h - mb); ctx.stroke();
      }
      ctx.restore();
      ctx.font = 'bold ' + FONT; ctx.fillStyle = C.text_primary || '#000'; ctx.textAlign = 'center';
      GROUPS.forEach(function(g, gi){
        ctx.fillText(g[1], Math.trunc(ml + gi * gw) + Math.trunc(gw) / 2, h - mb + 5 + 10);
      });
    }
  }

  DD.registerChart('distribution', {
    mount: function(el, ctx){
      el.innerHTML = '<div class="dd-plot"><canvas></canvas><div class="dd-tip"></div></div>';
      const plot = el.firstChild;
      const chart = new Chart(plot, ctx.data, DD.theme.chart, ctx.options || {});
      // a click on a bar: the cards answered with that button, in that group, in the chart's period (window._browse)
      plot._ddBrowse = function(){
        const i = chart.hoverIdx; if (i == null || i < 0) return null;
        return {revs: {btn_kind: GROUPS[Math.floor(i / 4)][0], ease: i % 4 + 1}};
      };
      if (!ctx.animate) chart.progress = 1;
      const state = {start: null, last: true};
      DD.hover.attach(plot, chart, {index: function(x, y){ return chart.indexAt(x, y); }, rows: function(i){ return chart.tipRows(i); }, redraw: function(){ state.last = true; DD.frame.kick(); }});
      function frame(now){
        // its intro not played yet (it waited out of view) and new data came meanwhile: the intro alone shows it
        // (the change's morph ran with it, a second animation over the first)
        if (chart.progress < 1 && state.start === null && (chart.morph)){ if (DD.dev) DD.trace('ANIMTRACE buttons intro not played yet: its morph dropped, the intro shows the new data'); chart.morph = null; }
        if (chart.progress < 1){ if (state.start === null) state.start = now; chart.progress = Math.min(1, (now - state.start) / DD.intro(500)); }
        let mo = false;
        if (chart.morph){
          const m = chart.morph; if (m.start === null) m.start = now;
          // 300 ms, as Activity's zoom (they change together on a zoom); InOutCubic alone (a smoothstep over it makes
          // the middle too steep to read the axis numbers)
          const t = Math.min(1, (now - m.start) / (300 * (m.k || 1)));
          if (t >= 1){ chart.morph = null; chart.view = null; } else {
            const tt = t < 0.5 ? 4*t*t*t : 1 - Math.pow(-2*t + 2, 3) / 2, a = (m.from && m.from.data) || {}, b = (chart.payload && chart.payload.data) || {}, d = {};
            const mx = function(src){ let x = 0; GROUPS.forEach(function(g){ (src[g[0]] || []).forEach(function(v){ if (v > x) x = v; }); }); return Math.max(1, x); };
            const am = m.fromMax || (m.fromMax = mx(a)), bm = mx(b), top = Math.max(1, DD.scaleLerp(am, bm, tt));
            // each bar goes from its height on the old scale to its height on the new one, the scale changing by ratio
            // (DD.scaleLerp: the axis numbers at the same pace all along), as Hourly's
            GROUPS.forEach(function(g){ d[g[0]] = (b[g[0]] || []).map(function(v, i){ const o = (a[g[0]] || [])[i] || 0; return (o / am + (v / bm - o / am) * tt) * top; }); });
            chart.view = {data: d, axisMax: top, ax: [am, bm, tt]}; mo = true;
          }
        }
        const needs = chart.progress < 1 || mo;
        if (needs || state.last) chart.draw();
        state.last = needs;
        return needs;
      }
      const resizer = new ResizeObserver(function(){ DD.frame.resized(frame, function(){ chart._resize(); state.last = true; }); });
      DD.frame.observe(resizer, plot);
      if (!ctx.animate) chart.draw();
      DD.frame.add(frame);
      return {
        update: function(data){
          const old = chart.payload, had = old && old.data && GROUPS.some(function(g){ return (old.data[g[0]] || []).some(function(v){ return v > 0; }); });
          if (ctx.animate && !had){ chart.progress = 0; state.start = null; }
          else if (ctx.animate && !DD._noAnim){ const v = chart.morph && chart.view; chart.morph = {from: v ? Object.assign({}, old, chart.view) : old, fromMax: v ? chart.view.axisMax : null, start: null, k: DD.calm ? DD.calm() : 1}; }
          if (DD.dev) DD.trace('ANIMTRACE distribution update: ' + (chart.morph && chart.morph.start === null ? 'morph' : !had ? 'intro' : 'NO ANIMATION (noAnim=' + !!DD._noAnim + ')'));
          chart.payload = data; state.last = true; DD.frame.kick(); },
        setOptions: function(o){ Object.assign(chart.options, o); state.last = true; DD.frame.kick(); },
        setTheme: function(){ chart.colors = DD.theme.chart; state.last = true; DD.frame.kick(); },
        destroy: function(){ DD.frame.remove(frame); resizer.disconnect(); el.innerHTML = ''; },
      };
    },
  });
})();
