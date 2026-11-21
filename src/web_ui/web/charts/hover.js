// Shared hover tooltip for the canvas charts: the chart gives the hovered index and the rows to show.
(function(){
  'use strict';
  const DD = window.DD;
  function rgba(c, a){ const o = DD.cu.parseColor(c); return 'rgba(' + Math.round(o.r) + ',' + Math.round(o.g) + ',' + Math.round(o.b) + ',' + a + ')'; }
  // chart: {canvas, w, h, colors, hoverIdx}; hooks: index(mx,my) -> idx|-1, rows(idx) -> [{header,text,value,color}], redraw()
  DD.hover = {
    attach: function(plot, chart, hooks){
      const tip = plot.querySelector('.dd-tip');
      let cur = null, tw = 0, th = 0;
      function hide(){ if (tip) tip.style.display = 'none'; cur = null; }
      function showAt(mx, my, aboveFinger){
        const idx = hooks.index(mx, my);
        if (idx >= 0 && tip){
          const C = chart.colors;
          if (cur !== idx){
            cur = idx;
            tip.innerHTML = hooks.rows(idx).map(function(r){
              return '<div class="row' + (r.header ? ' header' : '') + '">' +
                (r.color ? '<span class="swatch" style="background:' + r.color + '"></span>' : '') +
                '<span class="label">' + r.text + '</span>' + (r.value ? '<span class="value">' + r.value + '</span>' : '') + '</div>';
            }).join('');
            tip.style.background = rgba(C.tooltip_bg || '#18181b', C.is_dark ? 0.91 : 0.96);
            tip.style.borderColor = C.tooltip_border || 'rgba(128,128,128,0.4)';
            tip.style.color = C.text_secondary || '#888';
            const hd = tip.querySelector('.row.header'); if (hd) hd.style.color = C.text_primary || '#fff';
            tip.style.display = 'block'; tw = tip.offsetWidth; th = tip.offsetHeight;
          } else if (tip.style.display === 'none') tip.style.display = 'block';
          let left = aboveFinger ? (mx - tw / 2) : (mx + 15);
          let top = aboveFinger ? (my - th - 26) : (my + 15);
          if (left + tw > chart.w) left = aboveFinger ? (chart.w - tw - 2) : (mx - tw - 15);
          if (left < 0) left = 2;
          if (top + th > chart.h) top = chart.h - th - 2;
          if (top < 0) top = 2;
          DD.tipAt(tip, left, top);
        } else hide();
        if (idx !== chart.hoverIdx){ chart.hoverIdx = idx; hooks.redraw(); }
      }
      let touchLock = 0;
      chart.canvas.addEventListener('mousemove', function(ev){
        if (Date.now() < touchLock) return;
        const r = chart.canvas.getBoundingClientRect();
        showAt(ev.clientX - r.left, ev.clientY - r.top, false);
      });
      chart.canvas.addEventListener('mouseleave', function(){ hide(); if (chart.hoverIdx != null && chart.hoverIdx !== -1){ chart.hoverIdx = -1; hooks.redraw(); } });
      // Touch: tap shows tooltip, horizontal drag scrubs bars/points, vertical drag scrolls page normally
      let tx0 = 0, ty0 = 0, tPid = null, tScrub = false;
      function clearTouch(){ hide(); if (chart.hoverIdx != null && chart.hoverIdx !== -1){ chart.hoverIdx = -1; hooks.redraw(); } }
      chart.canvas.addEventListener('pointerdown', function(ev){
        if (ev.pointerType !== 'touch') return;
        touchLock = Date.now() + 800;
        tPid = ev.pointerId; tx0 = ev.clientX; ty0 = ev.clientY; tScrub = false;
        const r = chart.canvas.getBoundingClientRect();
        showAt(ev.clientX - r.left, ev.clientY - r.top, true);
        const outside = function(e2){
          if (!chart.canvas.contains(e2.target)){ clearTouch(); window.removeEventListener('pointerdown', outside, true); }
        };
        setTimeout(function(){ window.addEventListener('pointerdown', outside, true); }, 0);
      }, {passive: true});
      chart.canvas.addEventListener('pointermove', function(ev){
        if (ev.pointerType !== 'touch' || ev.pointerId !== tPid) return;
        const dx = Math.abs(ev.clientX - tx0), dy = Math.abs(ev.clientY - ty0);
        if (!tScrub && dy > 10 && dy > dx){ tPid = null; return; }  // vertical scroll
        if (dx > 6 && dx >= dy){ tScrub = true; }
        if (tScrub){
          touchLock = Date.now() + 800;
          const r = chart.canvas.getBoundingClientRect();
          showAt(ev.clientX - r.left, ev.clientY - r.top, true);
        }
      }, {passive: true});
      const endT = function(ev){ if (ev.pointerId === tPid){ tPid = null; tScrub = false; } };
      chart.canvas.addEventListener('pointerup', endT, {passive: true});
      chart.canvas.addEventListener('pointercancel', endT, {passive: true});
    },
  };
})();
