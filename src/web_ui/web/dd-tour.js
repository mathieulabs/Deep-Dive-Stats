// Concise interactive guided tour for the Deep Dive window: its steps and demos, on the overlay, pointer and dots
// of DD.tourKit (dd-core.js, shared with the main screen's tour), styled by .ddp-tour* in dd.css.
(function(){
  'use strict';
  const DD = window.DD;
  if (!DD) return;

  const PAD = 6;
  let active = null;

  const K = DD.tourKit;  // (dd-core.js)
  function visRect(el){
    if (!el || !el.getBoundingClientRect) return null;
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden') return null;
    return K.rect(el, 1);
  }
  const unite = K.unite;

  function findZoomCard(){
    const st = DD.state;
    if (!st || !st.cards) return null;
    const wrap = document.querySelector('.dd-gridwrap');
    const wr = wrap ? wrap.getBoundingClientRect() : {top: 0, bottom: window.innerHeight};
    const ids = Object.keys(st.cards).filter(function(id){
      const c = st.cards[id];
      if (!c || !c.card || !c.inst || !c.inst.zoom) return false;
      if (!visRect(c.card)) return false;
      const cv = c.card.querySelector('canvas');
      if (!cv || !visRect(cv)) return false;
      return !c.inst.zoom.count || c.inst.zoom.count() > 6;
    });
    if (!ids.length) return null;
    function inView(id){
      const r = st.cards[id].card.getBoundingClientRect();
      return r.top >= wr.top - 4 && r.bottom <= wr.bottom + 4;
    }
    ids.sort(function(a, b){
      const va = inView(a) ? 0 : 1, vb = inView(b) ? 0 : 1;
      if (va !== vb) return va - vb;
      const ta = st.cards[a].card.dataset.type, tb = st.cards[b].card.dataset.type;
      return (ta === 'activity' ? 0 : 1) - (tb === 'activity' ? 0 : 1);
    });
    return {id: ids[0], card: st.cards[ids[0]].card, inst: st.cards[ids[0]].inst};
  }

  function buildSteps(){
    const root = document.getElementById('dd-root') || document.body;
    const q = function(sel){ return root.querySelector(sel); };
    // a phone: no mouse (tap, pinch, the chart's own buttons), no Export button on its bar
    const touch = !!(DD.isTouch && DD.isTouch());
    const all = [
      {
        id: 'scope',
        title: DD.t('Deck, period and filter'),
        text: DD.t('Choose a deck, a time span, or type a search filter like tag:kanji or prop:lapses>3. Every chart and stat card updates together.'),
        rect: function(){ return unite([visRect(q('.dd-deck')), visRect(q('.dd-span')), visRect(q('.dd-filter'))]); },
        bar: ['.dd-deck', '.dd-filter']
      },
      {
        id: 'add',
        title: DD.t('Charts and stat cards'),
        text: touch ? DD.t('Tap Add / Remove to show or hide charts and stat cards, or add text blocks.')
          : DD.t('Click Add / Remove to show or hide charts and stat cards, or add text blocks. Drag cards to reorder or resize them, and change charts per row with the grid button (or Ctrl + scroll).'),
        rect: function(){ return unite([visRect(q('.dd-cols')), visRect(q('.dd-charts'))]); },
        bar: ['.dd-charts'],
        gallery: true
      },
      {
        id: 'zoom',
        title: DD.t('Zoom and explore'),
        text: touch ? DD.t('Pinch a chart with two fingers to zoom in, or use + and − under it. Slide a finger across it to read each bar, and tap ⋯ for its options and fullscreen.')
          : DD.t('Drag across a chart to zoom in, or click a bar to open those cards in the Browser. Right-click any chart for its options, fullscreen, or to pin it to the main screen.'),
        rect: function(){ const z = findZoomCard(); return z ? visRect(z.card) : null; },
        zoom: true
      },
      {
        id: 'table',
        title: DD.t('Deck table'),
        text: touch ? DD.t('Open Table to compare all your decks side by side or over time. The tabs at its foot switch between decks.')
          : DD.t('Open Table to compare all your decks side by side or over time. Switch tabs and drag column headers to reorder them.'),
        rect: function(){
          const panel = visRect(q('.dd-tbl-panel'));
          return panel ? unite([panel, visRect(q('.dd-table-btn'))]) : visRect(q('.dd-table-btn'));
        },
        table: true,
        bar: ['.dd-table-btn']
      },
      {
        id: 'export',
        title: touch ? DD.t('Share your layout') : DD.t('Export and share'),
        text: touch ? DD.t('Open Settings to copy a share code for your layout and presets.')
          : DD.t('Export the dashboard as an image or CSV, or open Settings to copy a share code for your layout and presets.'),
        rect: function(){ return unite([visRect(q('.dd-export')), visRect(q('.dd-settings'))]); },
        bar: ['.dd-settings']
      }
    ];
    return all.filter(function(st){ return !!st.rect(); });
  }

  DD.startTour = function(opts){
    if (active) return;
    const steps = buildSteps();
    if (!steps.length) return;

    // Pre-capture the Add / Remove gallery offscreen so it is ready on step 2
    DD.call('dd_tour_gallery_prep').catch(function(){});

    const el = K.build({back: DD.t('Back'), skip: DD.t('Skip'), next: DD.t('Next')}), ov = el.ov;
    ov.style.setProperty('--ddp-tour-acc', getComputedStyle(document.documentElement).getPropertyValue('--dd-accent').trim() || '#58a6ff');

    const T = active = {steps: steps, i: -1, timers: [], gen: 0, cleanups: [], picRect: null};

    function later(fn, ms){
      const id = setTimeout(function(){
        T.timers = T.timers.filter(function(x){ return x !== id; });
        if (active === T) fn();
      }, ms);
      T.timers.push(id);
      return id;
    }

    function tween(ms, step, done){
      const g = T.gen;
      K.tween(ms, K.ease.quad, function(){ return active === T && T.gen === g; }, step, done);
    }

    function setPic(src, x, y, w, h){ T.picRect = K.pic(el, src, x, y, w, h); }

    const touch = !!(DD.isTouch && DD.isTouch());
    function setPtr(x, y, show){ K.ptr(el, x, y, show); }

    function stopStep(){
      T.gen++;
      T.timers.forEach(clearTimeout);
      T.timers = [];
      setPtr(0, 0, false);
      setPic(null);
      const cs = T.cleanups.splice(0);
      cs.forEach(function(fn){ try { fn(); } catch (e) { DD.swallowed('tour cleanup', e); } });
    }

    function runGalleryDemo(){
      const root = document.getElementById('dd-root') || document.body;
      const btn = root.querySelector('.dd-charts');
      const g = T.gen;

      function showShot(q, done){
        if (active !== T || T.gen !== g || !q || !q.pic) return;
        const W = window.innerWidth, H = window.innerHeight;
        const ch = el.card.offsetHeight || 130;
        const sc = Math.min(1, (W * 0.68) / Math.max(1, q.w), (H - ch - 95) / Math.max(1, q.h));
        const pw = q.w * sc, ph = q.h * sc;
        const px = (W - pw) / 2, py = Math.max(14, (H - ch - ph - 68) / 2);
        setPic(q.pic, px, py, pw, ph);
        place(true);
        if (q.x && q.y){
          const tx = px + q.x * sc, ty = py + q.y * sc;
          const pr = el.ptr.getBoundingClientRect();
          const fx = el.ptr.style.opacity === '1' && pr.width ? pr.left : px + pw * 0.5;
          const fy = el.ptr.style.opacity === '1' && pr.height ? pr.top : py + ph * 0.85;
          tween(420, function(e){ setPtr(fx + (tx - fx) * e, fy + (ty - fy) * e, true); }, function(){
            if (active !== T || T.gen !== g) return;
            setPtr(tx, ty, true);
            later(function(){
              if (active !== T || T.gen !== g) return;
              if (el.ptr.animate) el.ptr.animate([{transform: 'scale(1)'}, {transform: 'scale(.82)'}, {transform: 'scale(1)'}], {duration: 240, easing: 'ease-out'});
              if (done) later(done, 1500);
            }, 260);
          });
        } else if (done){
          later(done, 1800);
        }
      }

      function startGalleryCycle(){
        let tries = 0;
        function poll(){
          if (active !== T || T.gen !== g) return;
          DD.call('dd_tour_gallery').then(function(shots){
            if (active !== T || T.gen !== g) return;
            const list = [];
            if (shots && shots.chart && shots.chart.pic) list.push(shots.chart);
            if (shots && shots.stat && shots.stat.pic) list.push(shots.stat);
            if (!list.length){
              if (++tries < 30) later(poll, 180);
              return;
            }
            let idx = 0;
            function next(){
              if (active !== T || T.gen !== g) return;
              // Re-check once in case the stat shot finished slightly after the chart shot
              DD.call('dd_tour_gallery').then(function(fresh){
                if (active !== T || T.gen !== g) return;
                const cur = [];
                if (fresh && fresh.chart && fresh.chart.pic) cur.push(fresh.chart);
                if (fresh && fresh.stat && fresh.stat.pic) cur.push(fresh.stat);
                const arr = cur.length ? cur : list;
                showShot(arr[idx % arr.length], arr.length > 1 ? function(){ idx++; next(); } : null);
              }).catch(function(){
                showShot(list[idx % list.length], list.length > 1 ? function(){ idx++; next(); } : null);
              });
            }
            next();
          }).catch(function(){});
        }
        poll();
      }

      // Step 1: focus on Add / Remove button, glide cursor to it, click, then show the gallery window
      if (btn){
        later(function(){
          if (active !== T || T.gen !== g) return;
          const r = btn.getBoundingClientRect();
          const tx = r.left + r.width * 0.5, ty = r.top + r.height * 0.5;
          const fx = tx + 55, fy = ty - 65;
          tween(420, function(e){ setPtr(fx + (tx - fx) * e, fy + (ty - fy) * e, true); }, function(){
            if (active !== T || T.gen !== g) return;
            setPtr(tx, ty, true);
            later(function(){
              if (active !== T || T.gen !== g) return;
              if (el.ptr.animate) el.ptr.animate([{transform: 'scale(1)'}, {transform: 'scale(.82)'}, {transform: 'scale(1)'}], {duration: 220, easing: 'ease-out'});
              later(startGalleryCycle, 260);
            }, 280);
          });
        }, 420);
      } else {
        later(startGalleryCycle, 200);
      }
    }

    function runTableDemo(){
      const root = document.getElementById('dd-root') || document.body;
      const btn = root.querySelector('.dd-table-btn');
      if (!btn) return;
      const g = T.gen;
      const wasOpen = btn.classList.contains('on');
      if (wasOpen) return;
      // First focus on the Table button, glide the cursor to it, click, then spotlight the open table
      later(function(){
        if (active !== T || T.gen !== g) return;
        const r = btn.getBoundingClientRect();
        const tx = r.left + r.width * 0.5, ty = r.top + r.height * 0.5;
        const fx = tx + 55, fy = ty - 65;
        tween(420, function(e){ setPtr(fx + (tx - fx) * e, fy + (ty - fy) * e, true); }, function(){
          if (active !== T || T.gen !== g) return;
          setPtr(tx, ty, true);
          later(function(){
            if (active !== T || T.gen !== g) return;
            if (el.ptr.animate) el.ptr.animate([{transform: 'scale(1)'}, {transform: 'scale(.82)'}, {transform: 'scale(1)'}], {duration: 220, easing: 'ease-out'});
            later(function(){
              if (active !== T || T.gen !== g) return;
              setPtr(0, 0, false);
              if (!btn.classList.contains('on')){
                btn.click();
                T.cleanups.push(function(){
                  if (btn.classList.contains('on')) btn.click();
                });
              }
              later(function(){ place(true); }, 260);
              later(function(){ place(true); }, 520);
            }, 220);
          }, 300);
        });
      }, 450);
    }

    function runZoomDemo(){
      const z = findZoomCard();
      if (!z) return;
      const cv = z.card.querySelector('canvas');
      if (!cv) return;
      const g = T.gen;
      const send = function(type, p, target){
        (target || cv).dispatchEvent(new MouseEvent(type, {
          clientX: p.x, clientY: p.y, button: 0, buttons: type === 'mouseup' ? 0 : 1, bubbles: true
        }));
      };
      const resetZoom = function(){
        const rb = document.querySelector('.dd-rzoom');
        if (rb && rb.style.display !== 'none'){ rb.click(); return; }
        // the web window has no window-wide arrow: a zoomed chart's own arrow resets them all and brings the stat
        // cards and the charts that follow the zoom back to the whole period (a bare zoom.set(null) left them zoomed)
        const zr = Array.prototype.filter.call(document.querySelectorAll('.dd-zreset'), function(b){ return b.style.display !== 'none'; })[0];
        if (zr){ zr.click(); return; }
        const st = DD.state && DD.state.cards;
        if (st){
          Object.keys(st).forEach(function(id){
            const c = st[id];
            if (c && c.inst && c.inst.zoom && c.inst.zoom.set) c.inst.zoom.set(null);
          });
        } else if (z.inst && z.inst.zoom && z.inst.zoom.set){
          z.inst.zoom.set(null);
        }
      };
      T.cleanups.push(resetZoom);

      function cycle(){
        if (active !== T || T.gen !== g) return;
        const r = cv.getBoundingClientRect();
        if (r.width < 40 || r.height < 20) return;
        const at = function(f){ return {x: r.left + r.width * f, y: r.top + r.height * 0.52}; };
        const p0 = at(0.38);
        setPtr(p0.x, p0.y, true);
        later(function(){
          if (active !== T || T.gen !== g) return;
          send('mousedown', p0);
          let k = 0;
          function step(){
            if (active !== T || T.gen !== g) return;
            k++;
            const q = at(0.38 + (0.70 - 0.38) * k / 10);
            setPtr(q.x, q.y, true);
            send('mousemove', q);
            if (k < 10){ later(step, 32); return; }
            later(function(){
              if (active !== T || T.gen !== g) return;
              send('mouseup', at(0.70), window);
              setPtr(0, 0, false);
              later(function(){
                if (active !== T || T.gen !== g) return;
                resetZoom();
                later(cycle, 1300);
              }, 1600);
            }, 140);
          }
          step();
        }, 550);
      }
      later(cycle, 350);
    }

    // the bottom bar scrolls sideways on a phone: the step's buttons brought into it (Deck was out of sight on the
    // first step, the bar left scrolled to its end)
    function revealBar(st){
      const bar = document.querySelector('.dd-bottom');
      if (!bar || !st.bar || bar.scrollWidth <= bar.clientWidth + 1) return;
      const br = bar.getBoundingClientRect();
      const rs = st.bar.map(function(sel){ return visRect(bar.querySelector(sel)); }).filter(Boolean);
      if (!rs.length) return;
      const u = unite(rs), m = 10;
      let dx = 0;
      if (u.left < br.left + m) dx = u.left - br.left - m;
      else if (u.right > br.right - m) dx = Math.min(u.right - br.right + m, u.left - br.left - m);
      if (Math.abs(dx) >= 1) bar.scrollLeft += dx;
    }

    function place(glide){
      if (active !== T || T.i < 0) return;
      const st = T.steps[T.i];
      const r = st.rect();
      if (!r) return;
      const h = {
        left: r.left - PAD, top: r.top - PAD,
        width: r.width + 2 * PAD, height: r.height + 2 * PAD
      };
      h.right = h.left + h.width; h.bottom = h.top + h.height;
      el.hole.classList.toggle('snap', !glide);
      el.hole.style.left = Math.round(h.left) + 'px';
      el.hole.style.top = Math.round(h.top) + 'px';
      el.hole.style.width = Math.round(h.width) + 'px';
      el.hole.style.height = Math.round(h.height) + 'px';

      const W = window.innerWidth, H = window.innerHeight;
      const cw = el.card.offsetWidth || 358, ch = el.card.offsetHeight || 130;
      let cx, cy;
      if (T.picRect){
        // Place card cleanly right below the gallery preview, clear of the bottom button
        cx = Math.max(10, Math.min((W - cw) / 2, W - cw - 10));
        cy = Math.min(T.picRect.bottom + 12, h.top - ch - 12);
        if (cy < 10) cy = Math.max(10, H - ch - 12);
      } else {
        cx = Math.max(10, Math.min(h.left + h.width / 2 - cw / 2, W - cw - 10));
        if (h.top - 14 - ch >= 10) cy = h.top - 14 - ch;
        else if (h.bottom + 14 + ch <= H - 10) cy = h.bottom + 14;
        else if (h.right + 14 + cw <= W - 10){ cx = h.right + 14; cy = Math.max(10, Math.min(h.top, H - ch - 10)); }
        else if (h.left - 14 - cw >= 10){ cx = h.left - 14 - cw; cy = Math.max(10, Math.min(h.top, H - ch - 10)); }
        else cy = Math.max(10, Math.min((H - ch) / 2, H - ch - 10));
        // the table over the whole screen (a phone): the card over its foot, in the room its rows leave, not
        // over the rows themselves
        if (st.table && h.height > H * 0.6){
          const foot = document.querySelector('.dd-tbl-foot');
          const ft = foot ? foot.getBoundingClientRect().top : H;
          cx = Math.max(10, (W - cw) / 2);
          cy = Math.max(10, Math.min(ft, H) - ch - 12);
        }
      }

      el.card.classList.toggle('glide', !!glide);
      el.card.style.left = Math.round(cx) + 'px';
      el.card.style.top = Math.round(cy) + 'px';
    }

    function renderDots(){ K.dots(el, T.steps.length, T.i, go); }

    function go(idx){
      if (active !== T) return;
      if (idx < 0) idx = 0;
      if (idx >= T.steps.length){ close(); return; }
      stopStep();
      const first = T.i < 0;
      T.i = idx;
      const st = T.steps[idx];
      el.title.textContent = (idx + 1) + ' / ' + T.steps.length + ' · ' + st.title;
      el.text.textContent = st.text;
      el.back.style.visibility = idx > 0 ? 'visible' : 'hidden';
      el.next.textContent = idx === T.steps.length - 1 ? DD.t('Done') : DD.t('Next');
      renderDots();
      if (st.zoom){
        const z = findZoomCard();
        if (z && z.card && z.card.scrollIntoView){
          const wrap = document.querySelector('.dd-gridwrap');
          const wr = wrap ? wrap.getBoundingClientRect() : {top: 0, bottom: window.innerHeight};
          const cr = z.card.getBoundingClientRect();
          if (cr.top < wr.top + 4 || cr.bottom > wr.bottom - 4) z.card.scrollIntoView({block: 'center', behavior: 'instant'});
        }
      }
      if (touch) revealBar(st);
      place(!first);
      if (st.gallery) runGalleryDemo();
      else if (st.zoom) runZoomDemo();
      else if (st.table) runTableDemo();
    }

    function close(){
      if (active !== T) return;
      stopStep();
      active = null;
      window.removeEventListener('resize', onResize);
      document.removeEventListener('keydown', onKey, true);
      ov.classList.add('out');
      setTimeout(function(){ ov.remove(); }, 190);
      if (!opts || opts.markSeen !== false){
        DD.call('dd_tour_done').catch(function(){});
      }
      if (opts && opts.auto){
        const tip = document.createElement('div');
        tip.className = 'dd-toast';
        tip.textContent = DD.t('You can replay this tour anytime from the bottom-right menu (Quick Tour).');
        document.body.appendChild(tip);
        setTimeout(function(){ tip.remove(); }, 4500);
      }
    }

    function onResize(){ place(false); }
    const onKey = K.keys(close, function(d){ if (active === T && (d > 0 || T.i > 0)) go(T.i + d); });

    el.back.onclick = function(){ go(T.i - 1); };
    el.skip.onclick = close;
    el.next.onclick = function(){ go(T.i + 1); };
    window.addEventListener('resize', onResize);
    document.addEventListener('keydown', onKey, true);

    go(0);
  };
})();
