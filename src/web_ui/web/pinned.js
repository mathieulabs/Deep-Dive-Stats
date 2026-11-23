/* Pinned widgets drawn inside Anki's own page (deck list, deck overview, Congratulations).
   Boxes in the configured order: stat cards, charts, texts; each box
   is one line (columns of 220 px, 10 px apart,
   a widget spans the columns its width needs, lines centered). The charts are the web Deep Dive's. */
(function(){
  'use strict';
  const DD = window.DD;
  const DDP = window.DDP = {};
  const COL = 220, SP = 10;  // column width, spacing
  // the widths and heights of a widget with no saved size
  const DEF_W = {card_counts: 220, todays_retention: 220}, DEF_H = {text_label: 44};  // the ring charts small (their legend behind its icon); a text line before its text: its least height
  // the heatmap's height for a width (with its legend), with the header row of
  // its mode buttons (20 px, 2 px under it, no margins without the glass)
  function heatmapNatural(o){
    const s = +o.scale || 1, cell = 14 * s, sp = cell * 0.25, lab = o.hide_labels ? 2 * s : 30 * s, top = o.hide_labels ? 2 * s : 22 * s;
    const grid = 53 * (cell + sp) - sp;
    const w = Math.max(150, Math.min(3000, Math.floor(lab + grid + 4)));
    const legend = o.show_legend === false ? 0 : Math.floor(28 * Math.max(1, s));
    const h = Math.floor(top + 7 * (cell + sp) + 10 * s + legend);
    return {w: w, h: 20 + 2 + h};
  }
  function syncHeatmapSize(el, d, o){
    if (!d || !d.it || !d.w || d.w.type !== 'heatmap') return false;
    const lk = el._ddpLook || d.w.look, g = !!(lk && lk.glass), p = g ? (lk.pad || [6, 10, 6, 10]) : [0, 0, 0, 0];
    const opts = Object.assign({}, d.w.options || {}, o || {});
    const nat = heatmapNatural(opts);
    let moved = false;
    if (d.w.width == null){
      const nw = nat.w + (g ? p[1] + p[3] + 2 : 0);
      if (d.it.w !== nw){ d.it.w = nw; moved = true; }
    }
    if (d.w.height == null && !d.it.folded){
      const innerW = d.it.w - (g ? p[1] + p[3] + 2 : 0);
      const nh = (d.inst && d.inst.natural ? (22 + d.inst.natural(innerW)) : nat.h) + (g ? p[0] + p[2] + 2 : 0);
      if (d.it.h !== nh){ d.it.h = nh; moved = true; }
    }
    return moved;
  }

  // ---- bridge: answers carry this page's token (Anki rebuilds the page often; old answers are dropped) ----
  let token = '', seq = 0;
  const waiting = {};
  // Anki's bridge is not up while the page loads (QWebChannel): what is sent then is lost. The page greets
  // Python until it answers, then sends what waited.
  let ready = false, queue = [], hello = 0;
  function send(id, cmd, args){
    try { window.pycmd('dd:' + JSON.stringify({id: id, cmd: cmd, args: Object.assign({_token: token}, args || {})})); }
    catch (e){ probe('pycmd failed ' + (e && e.message)); }
  }
  function greet(){
    if (ready || hello++ > 100) return;
    const id = ++seq;
    waiting[id] = {resolve: function(){ if (ready) return; ready = true; T0.ready = performance.now(); const q = queue; queue = []; q.forEach(function(r){ send(r[0], r[1], r[2]); }); }, reject: function(){}};
    send(id, 'hello', {});
    setTimeout(greet, 120);
  }
  DDP.call = function(cmd, args){
    return new Promise(function(resolve, reject){
      const id = ++seq;
      waiting[id] = {resolve: resolve, reject: reject};
      if (ready) send(id, cmd, args); else queue.push([id, cmd, args]);
    });
  };
  // an answer to a call sent under a token this page had before (the block built again in place in between: a tour
  // scene answered after the refresh of the one before it) is still its answer; another page's answers are not
  const known = {};
  DDP.__resolve = function(tok, id, ok, payload){
    if (tok !== token && !known[tok]) return;
    const w = waiting[id]; if (!w) return;
    delete waiting[id];
    if (ok) w.resolve(payload); else w.reject(new Error(payload));
  };

  function setTheme(root, theme){
    DD.theme = theme;
    Object.keys(theme.css || {}).forEach(function(k){ root.style.setProperty('--dd-' + k, theme.css[k]); });
    document.body.classList.toggle('dd-light', !theme.is_dark);
    DD.__push('theme', theme);
  }

  // ---- each widget as near its wanted x as the others allow ----
  function project(base, desired, widths, rowMin, sp, rowMax, weights){
    const n = base.length; if (!n) return [];
    const prefix = [0]; for (let i = 1; i < n; i++) prefix[i] = prefix[i - 1] + (widths[i - 1] | 0) + (sp | 0);
    const r = desired.map(function(d, i){ return d - prefix[i]; });
    const blocks = [];
    r.forEach(function(val, i){
      const w = weights && weights[i] > 0 ? weights[i] : 1;
      blocks.push([i, i, val * w, w, val]);
      while (blocks.length >= 2 && blocks[blocks.length - 2][4] > blocks[blocks.length - 1][4]){
        const b2 = blocks.pop(), b1 = blocks.pop(), sum = b1[2] + b2[2], c = b1[3] + b2[3];
        blocks.push([b1[0], b2[1], sum, c, sum / c]);
      }
    });
    const q = new Array(n).fill(0);
    blocks.forEach(function(b){ const v = Math.max(rowMin, b[4]); for (let i = b[0]; i <= b[1]; i++) q[i] = v; });
    const xs = q.map(function(v, i){ return Math.round(v + prefix[i]); });
    xs[0] = Math.max(xs[0], rowMin);
    for (let i = 1; i < n; i++) xs[i] = Math.max(xs[i], xs[i - 1] + widths[i - 1] + sp);
    if (rowMax != null){
      xs[n - 1] = Math.min(xs[n - 1], rowMax - widths[n - 1]);
      for (let i = n - 2; i >= 0; i--) xs[i] = Math.min(xs[i], xs[i + 1] - widths[i] - sp);
      xs[0] = Math.max(xs[0], rowMin);
      for (let i = 1; i < n; i++) xs[i] = Math.max(xs[i], xs[i - 1] + widths[i - 1] + sp);
    }
    return xs;
  }

  // one box: its items wrap into rows, each row centered; a widget moved sideways
  // (col_offset) keeps its place by whole columns (project_row_positions)
  function masonry(host, items){
    const W = host.clientWidth; if (W <= 0) return;
    const cols = Math.max(1, Math.floor((W + SP) / (COL + SP)));
    const cw = Math.floor((W - (cols - 1) * SP) / cols);
    if (cw <= 0) return;
    host._cw = cw;
    const sized = items.map(function(it){
      let w;
      if (it.fixed) w = Math.max(1, Math.min(W, it.w));
      else { const span = Math.max(1, Math.min(cols, Math.floor((it.w + SP + cw + SP - 1) / (cw + SP)))); w = span * cw + (span - 1) * SP; }
      return {it: it, w: w, h: it.h};
    });
    const rows = []; let cur = [], rw = 0, rh = 0;
    sized.forEach(function(s){
      if (cur.length && rw + SP + s.w > W){ rows.push([cur, rw, rh]); cur = []; rw = 0; rh = 0; }
      rw += (cur.length ? SP : 0) + s.w; rh = Math.max(rh, s.h); cur.push(s);
    });
    if (cur.length) rows.push([cur, rw, rh]);
    let y = 0;
    host._rows = [];
    rows.forEach(function(r){
      let x = Math.max(0, Math.floor((W - r[1]) / 2));
      const base = [], desired = [], widths = [], weights = [];
      r[0].forEach(function(s){
        const off = s.it.off | 0;
        base.push(x); desired.push(x + off * (cw + SP)); widths.push(s.w); weights.push(1 + 1000 * Math.abs(off));
        x += s.w + SP;
      });
      const xs = project(base, desired, widths, 0, SP, W, weights);
      r[0].forEach(function(s, i){
        const it = s.it, st = it.el.style;
        it.x = xs[i]; it.y = y; it.pw = s.w; it.ph = s.h;
        if (it.fs) return;  // shown fullscreen: its place is kept
        st.left = xs[i] + 'px'; st.top = y + 'px'; st.width = s.w + 'px'; st.height = s.h + 'px';
      });
      host._rows.push({y: y, h: r[2], x0: xs[0], x1: xs[xs.length - 1] + widths[widths.length - 1], items: r[0].map(function(s){ return s.it; })});
      y += r[2] + SP;
    });
    host.style.height = Math.max(0, y - SP) + 'px';
  }

  // ---- the block: built from the boot, built again in place when the settings change (no page reload) ----
  let S = null;  // {boot, root, boxes: [{key, el, fam, items}], insts: []}
  function familyOf(t){ return t === 'stat_card' ? 'stat' : (t === 'text_label' ? 'text' : 'chart'); }
  function boxKey(w){
    return w.type === 'stat_card' ? 'stats:' + (w.stat_box | 0)
      : w.type === 'text_label' ? 'texts:' + ((w.text_box != null ? w.text_box : w.chart_box) | 0)
      : 'charts:' + (w.chart_box | 0);
  }
  function rectIn(el, root){ const a = el.getBoundingClientRect(), b = root.getBoundingClientRect(); return {x: a.left - b.left, y: a.top - b.top, w: a.width, h: a.height}; }

  function build(boot, flip){
    const root = S.root;
    known[token] = true; token = boot.token; DDP.boot = boot; S.boot = boot; S.insts = []; S.boxes = [];
    S.root.classList.toggle('dd-nostats', boot.show_stats === false);  // the "Show Stats" / "Show Bottom Stats" of the pinned charts
    S.root.classList.toggle('dd-bottomstats', boot.show_bottom_stats === true);
    DD.settings = boot.settings || {};
    setTheme(root, boot.theme);
    statFx(root, boot.stat_fx);
    const m = boot.margins || [0, 20, 20];
    root.style.padding = m[0] + 'px ' + m[1] + 'px ' + m[2] + 'px';
    root.style.setProperty('--ddp-mx', m[1] + 'px');
    const byBox = {};
    boot.widgets.forEach(function(w){ (byBox[boxKey(w)] = byBox[boxKey(w)] || []).push(w); });
    const shown = boot.order.filter(function(k){ return byBox[k] && byBox[k].length; });
    shown.forEach(function(k, i){
      const el = document.createElement('div');
      el.className = 'ddp-box'; el.dataset.box = k;
      el.style.marginBottom = (i < shown.length - 1 ? (boot.gaps && boot.gaps[k] != null ? boot.gaps[k] : boot.gap) : 0) + 'px';
      root.appendChild(el);
      const ws = byBox[k], fam = k.indexOf('stats:') === 0 ? 'stat' : (k.indexOf('texts:') === 0 ? 'text' : 'chart');
      const box = {key: k, el: el, fam: fam, num: parseInt(k.split(':')[1], 10) || 0, ws: ws, items: []};
      S.boxes.push(box);
      if (fam === 'stat') statsBox(el, ws, boot, box);
      else chartsBox(el, ws, boot, box);
    });
    if (boot.widgets && boot.widgets.length){
      const wrap = document.createElement('div'); wrap.className = 'ddp-touch-add-wrap';
      const btn = document.createElement('button'); btn.type = 'button'; btn.className = 'ddp-touch-add';
      btn.textContent = '+ ' + (DD.t ? DD.t('Add Widget') : 'Add Widget');
      btn.addEventListener('click', function(ev){ ev.stopPropagation(); DDP.call('add_here', {target: {}}).catch(function(){}); });
      wrap.appendChild(btn); root.appendChild(wrap);
    }
    // a phone: a chart without a frame (the heatmap's own look) right under the box above, its buttons at its very
    // top: a little more room above it, as a framed card's padding would give (the spaces can't be dragged there)
    if (DD.isTouch && DD.isTouch()){
      S.boxes.forEach(function(b, i){
        const next = S.boxes[i + 1], first = next && next.fam === 'chart' && next.el.querySelector('.ddp-card');
        if (first && first.classList.contains('ddp-noglass')) b.el.style.marginBottom = ((parseFloat(b.el.style.marginBottom) || 0) + 8) + 'px';
      });
    }
    DDP.relayout();
    if (flip) glide(flip);
    if (DD.go && !(S && S.holdGo)){ if (boot.widgets.some(function(w){ return w.pre != null; }) || flip) DD.go(); else setTimeout(function(){ DD.go(); }, 60); }
  }
  // after a rebuild, each widget slides from where it was (180-320 ms by distance),
  // a new one fades in (CHART_FADE_IN_MS 100)
  function glide(before, movesOnly){
    const root = S.root;
    if (DD.dev && !movesOnly){
      const fresh = [], moved = [];
      root.querySelectorAll('[data-wid], .dd-sc[data-key]').forEach(function(el){ const id = el.dataset.wid || el.dataset.key, a = before[id]; if (!a) fresh.push(id.slice(0, 18)); else { const b = rectIn(el, root); if (Math.abs(a.x - b.x) > 0.5 || Math.abs(a.y - b.y) > 0.5) moved.push(id.slice(0, 18)); } });
      if (fresh.length || moved.length) DD.trace('ANIMTRACE rebuild: ' + fresh.length + ' new (fade in 100 ms) ' + moved.length + ' moved (glide)' + (fresh.length ? ' new=' + fresh.join(',') : ''));
    }
    root.querySelectorAll('[data-wid], .dd-sc[data-key]').forEach(function(el){
      const id = el.dataset.wid || el.dataset.key, a = before[id], b = rectIn(el, root);
      if (!el.animate || el.classList.contains('ddp-dragsrc') && false) return;
      if (!a){ if (!movesOnly) el.animate([{opacity: 0}, {opacity: 1}], {duration: 100}); return; }
      if (el._ddpGlide){ try { el._ddpGlide.cancel(); } catch (e) {} el._ddpGlide = null; b.x = rectIn(el, root).x; b.y = rectIn(el, root).y; }
      let dx = a.x - b.x; const dy = a.y - b.y;
      if (Math.abs(dx) < 0.5 && Math.abs(dy) < 0.5) return;
      if (Math.abs(dx) > 220) dx = dx > 0 ? 220 : -220;
      const ms = Math.max(180, Math.min(320, 180 + (Math.abs(dx) + Math.abs(dy)) * 0.18));
      el._ddpGlide = el.animate([{transform: 'translate(' + dx + 'px,' + dy + 'px)'}, {transform: 'none'}], {duration: ms, easing: 'cubic-bezier(0.33, 1, 0.68, 1)'});
    });
  }
  // A card whose chart is the same (type, options, look, title) is kept as it is (its picture, its zoom) and only
  // asked for its data again: another period or deck morphs in it, in place.
  // refresh_runtime: a widget whose period changed since its last data updates with the "timespan" transition
  const lastSpan = {};
  function spanMode(w){
    const k = JSON.stringify(w.span || null), was = lastSpan[w.id]; lastSpan[w.id] = k;
    return was !== undefined && was !== k ? 'timespan' : undefined;
  }
  // dev: what each update of a pinned chart is (another period, another deck, to or from nothing), to set against
  // what was expected (ANIMTRACE: the chart's own trace then says how it animated)
  function hasData(d){ return !!d && !d._empty && /[:,\[]\s*[1-9]/.test(JSON.stringify(d)); }
  function feed(inst, data, mode, w, old, el){
    if (DD.dev && w){
      const a = old !== undefined ? hasData(old) : null, b = hasData(data);
      DD.trace('ANIMTRACE update ' + w.type + ' ' + (mode || 'deck/data') + (a === null ? '' : (a && !b ? ' TO EMPTY' : !a && b ? ' FROM EMPTY' : !a && !b ? ' empty -> empty' : '')));
    }
    const run = function(){
      const t0 = performance.now();
      DD._calm = 'pin';
      try { DD.applyUpdate(el, function(){ inst.update(data || {}, mode); }); } finally { DD._calm = false; }
      const dt = performance.now() - t0;
      if (DD.perfMark && w && dt >= 8) DD.perfMark('pinned_feed ' + w.type, dt, mode || 'deck');
    };
    // web: after a deck / period change the widgets start one after the other in reading order (a wave down the
    // block, ~0.35 s), counted from the change: a late answer waits no more
    const now = performance.now();
    if (el && S && S.wave0 && now - S.wave0 < 1500 && S.root){
      const r = el.getBoundingClientRect(), rr = S.root.getBoundingClientRect();
      const fy = Math.max(0, Math.min(1, (r.top - rr.top) / Math.max(1, rr.height - r.height)));
      const fx = Math.max(0, Math.min(1, (r.left - rr.left) / Math.max(1, rr.width - r.width)));
      const wait = S.wave0 + fy * 300 + fx * 60 - now;
      if (wait > 8){ setTimeout(function(){ if (el._ddp && el._ddp.inst === inst) run(); }, wait); return; }
    }
    run();
  }
  function cardSig(w){ return JSON.stringify([w.type, w.options || null, w.look || null, w.title || null, w.height == null && w.type === 'heatmap']); }
  function coreSig(w){ return JSON.stringify([w.type, w.title || null, w.height == null && w.type === 'heatmap']); }
  // the block as laid out (all but the period / deck labels and the data): when only those changed (a period or a
  // deck picked from a card's label or menu), the widgets that changed update in place and nothing else is touched,
  // one widget refreshed at a time
  function softSig(boot, noOpts){
    const b = Object.assign({}, boot, {token: 0, built: 0, first: 0, skel: 0, pre_stats: 0, tour: 0, theme: 0, stat_fx: 0});
    b.widgets = (boot.widgets || []).map(function(w){ const c = Object.assign({}, w); delete c.chips; delete c.span; delete c.pre; delete c.nat; delete c.expanded; delete c.title; delete c.look; delete c.search_query; if (noOpts) delete c.options; return c; });
    return JSON.stringify(b);
  }
  function wSig(w){ const c = Object.assign({}, w); delete c.pre; delete c.nat; delete c.expanded; return JSON.stringify(c); }
  function softReboot(boot){
    const old = S.boot;
    known[token] = true; token = boot.token; DDP.boot = boot; S.boot = boot;
    const byId = {}; (old.widgets || []).forEach(function(w){ byId[w.id] = w; });
    const stripMeta = function(x){ const c = Object.assign({}, x); delete c.look; delete c.options; return wSig(c); };
    let changedN = 0;
    (boot.widgets || []).forEach(function(w){ const ow = byId[w.id]; if (ow && stripMeta(w) !== stripMeta(ow)) changedN++; });
    // only stagger updates in a wave when multiple widgets change together (e.g. Apply to all / deck switch);
    // a single widget's period change starts immediately with 0ms artificial delay
    S.wave0 = changedN > 1 ? performance.now() : 0;
    // another theme: everything repainted in place (theme_manager: the widgets restyled, not rebuilt), the charts'
    // old pictures fading over the new colors, the boxes' colors gliding
    const themed = JSON.stringify(old.theme || null) !== JSON.stringify(boot.theme || null);
    const fxChanged = JSON.stringify(old.stat_fx || null) !== JSON.stringify(boot.stat_fx || null);
    if (themed || fxChanged){
      const all = {}; S.boxes.forEach(function(b){ (b.items || []).forEach(function(it){ if (it.el._ddp && it.el._ddp.inst) all[it.wid] = it.el; }); });
      const fades = themed ? themeFades(all) : [];
      S.root.classList.add('ddp-themefx'); clearTimeout(S.fxT); S.fxT = setTimeout(function(){ if (S) S.root.classList.remove('ddp-themefx'); }, 320);
      if (themed) setTheme(S.root, boot.theme);
      statFx(S.root, boot.stat_fx);
      Object.keys(all).forEach(function(id){ const i = all[id]._ddp.inst; try { if (themed && i.setTheme) i.setTheme(DD.theme); } catch (e) {} });
      fades.forEach(function(f){ f(); });
      if (DD.dev) DD.trace('ANIMTRACE reboot soft: theme repainted in place (' + Object.keys(all).length + ' charts, ' + fades.length + ' pictures fading)');
    }
    S.boxes.forEach(function(b){ if (b.fam === 'stat' && (themed || fxChanged) && b.el._ddpStats) b.el._ddpStats(); });
    S.boxes.forEach(function(b){
      let stats = false;
      b.ws = b.ws.map(function(w0){ return boot.widgets.filter(function(x){ return x.id === w0.id; })[0] || w0; });
      if (b.fam === 'stat'){ if (!themed && !fxChanged){ b.ws.forEach(function(w){ if (wSig(w) !== wSig(byId[w.id] || {})) stats = true; }); if (stats && b.el._ddpStats) b.el._ddpStats(); } return; }
      b.items.forEach(function(it){
        const w = boot.widgets.filter(function(x){ return x.id === it.wid; })[0], el = it.el, d = el._ddp;
        if (!w || !d) return;
        const ow = byId[w.id] || {};
        if (JSON.stringify(ow.look || null) !== JSON.stringify(w.look || null)) applyLook(el, w.look);
        const optsChanged = JSON.stringify(ow.options || null) !== JSON.stringify(w.options || null);
        if (d.inst && d.inst.setOptions && optsChanged){
          const o = Object.assign({}, w.options || {}); delete o.mode; delete o.today; delete o.logical_today;  // its view stays (DDP.restyle)
          // some options are read in Python (a range, a filter, Future Due's breakdown): its data asked again, taken
          // only if it changed (the same data: nothing moves, the zoom stays). The options are given with that data,
          // in the same frame: given first, the chart would morph to the old data seen with the new options, then to
          // the new data
          const onlyBin = function(a, b){
            const ca = Object.assign({}, a || {}), cb = Object.assign({}, b || {});
            delete ca.adaptive_binning; delete ca.binning; delete cb.adaptive_binning; delete cb.binning;
            return JSON.stringify(ca) === JSON.stringify(cb);
          };
          const setO = function(){ try { d.inst.setOptions(o); if (syncHeatmapSize(el, d, o)) DDP.relayout(); } catch (e) {} };
          if (themed || onlyBin(ow.options, w.options)) setO();
          else DDP.call('data', {id: w.id, deck: boot.deck}).then(function(data){
            if (!d.inst) return;
            const js = JSON.stringify(data || {});
            setO();
            if (js === d.dataJs) return; const old = d.dataJs ? JSON.parse(d.dataJs) : undefined; d.dataJs = js; feed(d.inst, data, undefined, w, old);
          }).catch(function(){ setO(); });
        }
        const strip = function(x){ const c = Object.assign({}, x); delete c.look; delete c.options; return wSig(c); };
        const changed = strip(w) !== strip(ow);
        it.def = w; d.w = w; d.sig = cardSig(w); d._pvOpts = null;
        // a text widget's sentence is not in its definition sent to the page (its template is read in Python): it is
        // always asked again, and shown when it is another one (the texts step changes only that)
        if (!changed && w.type !== 'text_label') return;
        if (w.type === 'text_label'){
          el._ddpT = true;
          const tAsk = performance.now();
          DDP.call('text', {id: w.id, deck: boot.deck}).then(function(html){
            if (T) tlog('text answer in ' + Math.round(performance.now() - tAsk) + ' ms');
            el._ddpT = false;
            if (html === d.lastHtml) return;
            // the old sentence fades out over the new one fading in (200 ms)
            const ghost = el.cloneNode(true);
            ghost.removeAttribute('data-wid'); ghost.style.pointerEvents = 'none';
            el.parentNode.insertBefore(ghost, el);
            d.put(html);
            if (ghost.animate){
              el.animate([{opacity: 0}, {opacity: 1}], {duration: 200});
              const an = ghost.animate([{opacity: 1}, {opacity: 0}], {duration: 200, fill: 'forwards'}); an.onfinish = function(){ ghost.remove(); };
            } else ghost.remove();
          }).catch(function(){ el._ddpT = false; });
          return;
        }
        const head = el.querySelector('.dd-head');
        head.querySelectorAll('.ddp-chip').forEach(function(c){ c.remove(); });
        chips(head, w);
        const tt = head.querySelector('.dd-title'), title = w.type === 'heatmap' ? (boot.heatmap_title ? w.title : null) : w.title;
        if (tt && title) tt.textContent = title;
        if (zoomed[w.id]){ dotsToBars(zoomed[w.id], true); zoomed[w.id].last = null; showReset(zoomed[w.id]); }
        delete AZ[w.id];
        const mode = spanMode(w);
        DDP.call('data', {id: w.id, deck: boot.deck}).then(function(data){
          if (!d.inst) return;
          const js = JSON.stringify(data || {});
          if (js === d.dataJs) return;
          const old = d.dataJs ? JSON.parse(d.dataJs) : undefined;
          d.dataJs = js;
          feed(d.inst, data, mode, w, old, el);
        }).catch(function(){});
      });
    });
  }
  DDP.reboot = function(boot){
    if (!S){ DDP.start(boot); return; }
    if (DD.setAnim) DD.setAnim(boot.anim);  // the animation settings as saved now
    // another theme also changes the options that carry its colors (the calendar's color): still repainted in place
    const themedNow = S.boot && JSON.stringify(S.boot.theme || null) !== JSON.stringify(boot.theme || null);
    // the layout the same and only options changed (a chart's binning, a toggle from its menu): the charts take their
    // new options in place and keep their view and zoom (the widget is told, not rebuilt)
    void themedNow;
    if (S.boot && softSig(boot, true) === softSig(S.boot, true) && S.boxes.every(function(b){ return b.fam === 'stat' || b.items.every(function(it){ return it.el._ddp; }); })){
      if (DD.dev) DD.trace('ANIMTRACE reboot soft');
      if (DD.perfWatch) DD.perfWatch('pinned softReboot', 1000);
      softReboot(boot); return;
    }
    if (DD.perfWatch) DD.perfWatch('pinned fullReboot', 1200);
    if (DD.dev && S.boot){
      const a = JSON.parse(softSig(S.boot, true)), c = JSON.parse(softSig(boot, true)), why = [];
      Object.keys(Object.assign({}, a, c)).forEach(function(k){ if (k !== 'widgets' && JSON.stringify(a[k]) !== JSON.stringify(c[k])) why.push(k); });
      if (JSON.stringify(a.widgets) !== JSON.stringify(c.widgets)) why.push('widgets (layout)');
      else if (softSig(S.boot) !== softSig(boot)) why.push('options');
      DD.trace('ANIMTRACE reboot full because: ' + why.join(', '));
    }
    if (window.DDP && DDP._tourRebuild) DDP._tourRebuild();
    const before = snapshot();
    const keep = {}, reopt = {};
    // another theme: a card whose look or options changed with it is kept too, and recolored in place (its colors
    // fade over, nothing is built again)
    const themed = JSON.stringify((S.boot && S.boot.theme) || null) !== JSON.stringify(boot.theme || null);
    S.boxes.forEach(function(b){ b.items.forEach(function(it){
      const nw = boot.widgets.filter(function(x){ return x.id === it.wid; })[0], d = it.el._ddp;
      if (!nw || !d) return;
      if (d.sig === cardSig(nw)) keep[it.wid] = it.el;
      else if (themed && d.inst && d.w && coreSig(d.w) === coreSig(nw)){ keep[it.wid] = it.el; if (JSON.stringify(d.w.options || null) !== JSON.stringify(nw.options || null)) reopt[it.wid] = nw.options; }
    }); });
    const fades = themed ? themeFades(keep) : [];
    if (DD.dev){
      const lost = [];
      S.boxes.forEach(function(b){ b.items.forEach(function(it){ if (!keep[it.wid]){ const nw = boot.widgets.filter(function(x){ return x.id === it.wid; })[0], d = it.el._ddp; lost.push(it.wid + (nw && d ? ' sig ' + (d.sig === cardSig(nw)) + ' core ' + (d.w && coreSig(d.w) === coreSig(nw)) + ' ' + (d.sig || '').slice(0, 300) + ' => ' + cardSig(nw).slice(0, 300) : ' gone')); } }); });
      DD.trace('ANIMTRACE reboot kept=' + Object.keys(keep).length + ' themed=' + themed + ' rebuilt: ' + lost.join(' || '));
    }
    // the page keeps its height and its scroll while the block is emptied and built again: emptied, the page gets
    // shorter for a moment and the browser scrolls it back up
    const sy = window.scrollY, rootH = S.root.offsetHeight;
    S.root.style.minHeight = rootH + 'px';
    Object.keys(keep).forEach(function(id){ keep[id].remove(); });
    S.insts = S.insts.filter(function(i){ return !Object.keys(keep).some(function(id){ return keep[id]._ddp.inst === i; }); }).concat([]);
    const kept = Object.keys(keep).map(function(id){ return keep[id]._ddp.inst; });
    S.keep0 = keep;
    teardownExcept(kept);
    S.keep0 = null;
    S.keep = keep;
    if (themed){ S.root.classList.add('ddp-themefx'); clearTimeout(S.fxT); S.fxT = setTimeout(function(){ if (S) S.root.classList.remove('ddp-themefx'); }, 320); }
    build(boot, before);
    S.keep = null;
    S.root.style.minHeight = '';
    if (Math.abs(window.scrollY - sy) > 0.5){ window.scrollTo(window.scrollX, sy); if (DD.dev) DD.trace('ANIMTRACE rebuild: scroll kept at ' + Math.round(sy)); }
    // another theme (the tour's themes, the settings): the charts kept repaint with its colors (DD.on('theme') of the window)
    if (themed) kept.forEach(function(i){ try { if (i && i.setTheme) i.setTheme(DD.theme); } catch (e) {} });
    Object.keys(reopt).forEach(function(id){ const d = keep[id]._ddp; try { if (d.inst && d.inst.setOptions) d.inst.setOptions(reopt[id] || {}); } catch (e) {} });
    Object.keys(keep).forEach(function(id){ const d = keep[id]._ddp, nw = boot.widgets.filter(function(x){ return x.id === id; })[0]; if (d && nw){ d.sig = cardSig(nw); d.w = nw; d._pvOpts = null; } });
    fades.forEach(function(f){ f(); });
  };
  // a kept chart recolored: a cross-fade of its old picture to its new one, mixed in one canvas over it (the old
  // picture faded over the new canvas would stack two half-transparent bars, cells or lines, darker or lighter
  // halfway); 220 ms, the chart itself hidden meanwhile
  function themeFades(keep){
    const out = [];
    Object.keys(keep).forEach(function(id){
      keep[id].querySelectorAll('canvas').forEach(function(cv){
        if (!cv.width || !cv.height || !cv.offsetParent) return;
        const old = document.createElement('canvas'); old.width = cv.width; old.height = cv.height;
        try { old.getContext('2d').drawImage(cv, 0, 0); } catch (e) { return; }
        out.push(function(){
          if (!cv.parentNode) return;
          const o = document.createElement('canvas'); o.width = cv.width; o.height = cv.height;
          o.style.cssText = 'position:absolute;pointer-events:none;left:' + cv.offsetLeft + 'px;top:' + cv.offsetTop + 'px;width:' + cv.offsetWidth + 'px;height:' + cv.offsetHeight + 'px';
          const g = o.getContext('2d'); g.drawImage(old, 0, 0);
          // a fade still running on this canvas (two themes in a row, a step left halfway) ends first: it gives the
          // chart back its own opacity (taken as "0" by the next fade, the chart stayed invisible: empty charts)
          if (cv._ddFadeEnd) cv._ddFadeEnd();
          cv.parentNode.insertBefore(o, cv.nextSibling);
          const vis = cv.style.opacity; cv.style.opacity = '0';
          let over = false;
          const done = function(){ if (over) return; over = true; cv._ddFadeEnd = null; cv.style.opacity = vis; o.remove(); };
          cv._ddFadeEnd = done;
          // the new colors drawn by the chart's next frame, then mixed: old x (1 - t) + new x t
          requestAnimationFrame(function(){ requestAnimationFrame(function(){
            if (over) return;
            if (!cv.parentNode || cv.width !== o.width || cv.height !== o.height){ done(); return; }
            const nw = document.createElement('canvas'); nw.width = cv.width; nw.height = cv.height;
            try { nw.getContext('2d').drawImage(cv, 0, 0); } catch (e) { done(); return; }
            const t0 = performance.now();
            (function step(now){
              const t = Math.min(1, (now - t0) / 220), e = t * t * (3 - 2 * t);
              g.globalCompositeOperation = 'source-over'; g.globalAlpha = 1; g.clearRect(0, 0, o.width, o.height);
              g.globalAlpha = 1 - e; g.drawImage(old, 0, 0);
              g.globalCompositeOperation = 'lighter'; g.globalAlpha = e; g.drawImage(nw, 0, 0);
              if (over) return;
              if (t < 1) requestAnimationFrame(step); else done();
            })(t0);
          }); });
        });
      });
    });
    return out;
  }
  function teardownExcept(kept){
    S.insts.forEach(function(i){ if (kept.indexOf(i) >= 0) return; try { if (i && i.destroy) i.destroy(); } catch (e) {} });
    Object.keys(zoomed).forEach(function(k){ if (!(S.keep0 && S.keep0[k])) delete zoomed[k]; });
    S.root.innerHTML = '';
    marks = null;
  }

  // dev: when the block shows after Anki built its page (since the page began loading), and what it waited for
  const T0 = {};
  function pageTimes(){
    const nav = performance.timing || {}, dcl = nav.domContentLoadedEventEnd && nav.navigationStart ? nav.domContentLoadedEventEnd - nav.navigationStart : null;
    const pre = (S && S.boot && S.boot.widgets || []).filter(function(w){ return w.pre != null; }).length, all = (S && S.boot && S.boot.widgets || []).length;
    let fcp = null; try { (performance.getEntriesByType('paint') || []).forEach(function(e){ if (e.name === 'first-contentful-paint') fcp = e.startTime; }); } catch (e) {}
    probe('PERF page: first paint of the page (deck list) ' + (fcp != null ? Math.round(fcp) : '-') + ' ms, script ran at ' + Math.round(T0.start) + ' ms, block built at ' + Math.round(T0.built) + ', first frame ' + Math.round(T0.frame) +
      ', bridge ready ' + (T0.ready != null ? Math.round(T0.ready) : '-') + ', page loaded ' + (dcl != null ? dcl : '-') + ' ms; ' + pre + '/' + all + ' widgets shown from their last picture, ' + (T0.lazy || 0) + ' drawn after the first paint (under the window)');
  }
  DDP.start = function(boot){
    T0.start = performance.now();
    if (DD.perfWatch) DD.perfWatch('pinned start', 1400);
    if (DD.perfScroll && !window.__ddpScrollPerf){ window.__ddpScrollPerf = true; DD.perfScroll(window, 'pinned scroll'); }
    probe('start ' + boot.token + ' widgets=' + (boot.widgets || []).length + ' pycmd=' + typeof window.pycmd);
    greet();
    try {
      const root = document.getElementById('ddp-root');
      if (!root || root._ddp) return;
      root._ddp = true;
      if (DD.setI18n && !DD._i18nOn){ DD._i18nOn = true; DD.setI18n(boot.i18n, root); }  // the block's texts in the add-on's language
      if (DD.setAnim) DD.setAnim(boot.anim);  // Settings > General > Animations (for the pinned widgets)
      S = {root: root, boot: boot, boxes: [], insts: []};
      setup(root);
      onigiriFit(root);
      // Anki started (boot.first; a return to the main screen shows it at once, as it was): the block fades in at
      // once (its boxes and what is in them), not box by box: hidden until the widgets
      // without a last picture have their data (350 ms at most), then 150 ms of fade, the charts' opening
      // animations starting in its last third (DD.go held till then). Appearance Animations off: shown as before.
      const fade = !!(boot.first && root.animate && DD.anim && DD.anim.on && DD.anim.appear);
      const waits = [];
      const call0 = DDP.call;
      const skel = fade && !!boot.skel;  // the page before showed the skeleton: shown at once, the charts wait
      if (fade){
        if (skel) root.classList.add('ddp-skel'); else root.style.visibility = 'hidden';
        S.holdGo = true; S.introQ = [];  // what plays with the charts' intro (reveal): the heatmap's values
        const pre = {}; (boot.widgets || []).forEach(function(w){ pre[w.id] = w.pre != null; });
        DDP.call = function(cmd, args){
          const p = call0.apply(this, arguments), a = args || {};
          const fresh = cmd === 'stats' ? !(boot.pre_stats && boot.pre_stats[(a.ids || []).join(',')])
            : (cmd === 'data' || cmd === 'text') ? !pre[a.id] : false;
          if (fresh) waits.push(Promise.resolve(p).catch(function(){}));
          return p;
        };
        reveal(root, waits, skel);
      }
      if (DD.dev) DD.trace('ANIMTRACE start first=' + !!boot.first + ' fade=' + fade + ' still=' + (boot.widgets || []).filter(function(w){ return w.pre != null && w.type !== 'text_label'; }).length + '/' + (boot.widgets || []).length);
      // Python keeps building the block for its intro (boot.first) until it is told the intro played: an intro
      // cut short by Anki building the deck list again plays again, instead of the charts showing still
      if (boot.first && !fade) introDone(0);
      // the charts in view drawn with the page; the ones under the window right after (the block came ~60 ms after
      // the deck list, all its charts drawn before the first paint)
      S.lazyQ = [];
      try { build(boot, null); } finally { DDP.call = call0; }
      const q = S.lazyQ; S.lazyQ = null;
      const vh = window.innerHeight + 80, later = [];
      q.forEach(function(x){ if (x.el.getBoundingClientRect().top < vh) x.run(); else later.push(x); });
      if (later.length) requestAnimationFrame(function(){ setTimeout(function(){ later.forEach(function(x){ try { x.run(); } catch (e) {} }); DDP.relayout(); }, 0); });
      T0.built = performance.now(); T0.lazy = later.length;
      requestAnimationFrame(function(){ T0.frame = performance.now(); setTimeout(pageTimes, 1500); });
      if (boot.tour) setTimeout(function(){ DDP.tour(boot.tour); }, 400);
    } catch (e){ probe('start error ' + (e && e.message) + ' ' + (e && e.stack || '').split('\n').slice(0, 3).join(' | ')); }
    setTimeout(function(){ const n = Object.keys(waiting).length; if (n > hello + 1) probe('ready=' + ready + ' still waiting for ' + n + ' answers after 4 s'); }, 4000);
  };
  function introDone(ms){
    setTimeout(function(){ if (document.visibilityState !== 'hidden') DDP.call('intro_done', {}).catch(function(){}); }, ms);
  }
  // Onigiri's main screen: the block sits in a grid cell of whole rows that clips what does not fit. Its height
  // changes without the deck list being drawn again (a widget added, folded or resized, the window resized): the
  // cell follows (onigiri.py fit), in place; a cell grown into another tile has Onigiri place the grid again
  function onigiriFit(root){
    const cell = root.closest && root.closest('.external-widget-container');
    if (!cell || !window.ResizeObserver) return;
    let timer = null, last = 0;
    const overlaps = function(){
      const a = cell.getBoundingClientRect();
      return Array.prototype.some.call(cell.parentElement ? cell.parentElement.children : [], function(o){
        if (o === cell) return false;
        const b = o.getBoundingClientRect();
        return Math.min(a.right, b.right) - Math.max(a.left, b.left) > 2 && Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > 2;
      });
    };
    const send = function(){
      const cs = getComputedStyle(root);
      const h = Math.ceil(root.getBoundingClientRect().height + (parseFloat(cs.marginTop) || 0) + (parseFloat(cs.marginBottom) || 0));
      if (h <= 0 || Math.abs(h - last) < 2) return;
      last = h;
      DDP.call('onigiri_fit', {h: h}).then(function(r){
        if (!r || !r.rows) return;
        if (DD.dev) DD.trace('ONIGIRI cell ' + r.rows + ' rows x ' + r.cols + ' cols for ' + h + ' px');
        cell.style.gridRowEnd = 'span ' + r.rows; cell.style.gridColumnEnd = 'span ' + r.cols;
        requestAnimationFrame(function(){ if (overlaps()) DDP.call('onigiri_relayout', {}).catch(function(){}); });
      }).catch(function(){});
    };
    new ResizeObserver(function(){ clearTimeout(timer); timer = setTimeout(send, 400); }).observe(root);
  }
  // the block's fade in when Anki shows it first (DDP.start): once what it waits for is there, or 350 ms at most
  // skel: the cards already on screen (the skeleton, held page before): only the charts' intro is left
  function reveal(root, waits, skel){
    let done = false, asked = false, cards = !!skel;
    const fadeCards = function(ms){
      // fade each card on its own: an opacity on an ancestor (#ddp-root) creates a backdrop root and kills backdrop-filter blur
      try { root.querySelectorAll('[data-wid], .dd-sc[data-key]').forEach(function(e){ e.animate([{opacity: 0}, {opacity: 1}], {duration: ms, easing: 'ease-out'}); }); } catch (e) {}
    };
    // held: the skeleton (cards, titles, texts, stat cards from their last values) at once, the charts wait
    const skeleton = function(){
      if (cards) return; cards = true;
      root.classList.add('ddp-skel'); root.style.visibility = '';
      fadeCards(150 * (DD.speed ? DD.speed() : 1));
      DDP.call('intro_skel', {}).catch(function(){});
    };
    const t0 = performance.now();
    // Anki syncing on opening: this page is about to be replaced, the intro waits for the next one (3 s at most)
    const show = function(){
      if (done || asked) return; asked = true;
      const ask = function(){
        if (performance.now() - t0 > 3000) return go();
        DDP.call('intro_hold', {built: S && S.boot ? S.boot.built : null}).then(function(hold){
          if (!hold) return go();
          if (DD.dev && !show.logged){ show.logged = true; DD.trace('ANIMTRACE intro held: Anki is syncing, the deck list comes again (skeleton shown)'); }
          skeleton();
          setTimeout(ask, 150);
        }).catch(go);
      };
      ask();
    };
    const go = function(){
      if (done) return; done = true;
      requestAnimationFrame(function(){  // the data just mounted, drawn first
        const ms = cards ? 0 : 150 * (DD.speed ? DD.speed() : 1);
        root.style.visibility = ''; root.classList.remove('ddp-skel');
        if (!cards) fadeCards(ms);
        setTimeout(function(){
          if (S) S.holdGo = false; if (DD.go) DD.go();
          const q = (S && S.introQ) || []; if (S) S.introQ = null;
          q.forEach(function(fn){ try { fn(); } catch (e) {} });
        }, ms * 2 / 3);
        introDone(ms + 900 * (DD.speed ? DD.speed() : 1));  // the charts' opening animations seen through
      });
    };
    setTimeout(show, 350);
    setTimeout(function(){ Promise.all(waits).then(show); }, 0);  // the calls made while the block was built
  }
  // relayout: a window resized puts the widgets in place at once; a change of the
  // layout itself (live reorder) slides them
  DDP.relayout = function(animate){
    if (!S) return;
    const before = animate ? snapshot() : null;
    S.boxes.forEach(function(b){ if (b.layout) b.layout(); });
    if (before) glide(before, true);
  };
  function snapshot(){
    const out = {};
    S.root.querySelectorAll('[data-wid], .dd-sc[data-key]').forEach(function(el){ out[el.dataset.wid || el.dataset.key] = rectIn(el, S.root); });
    return out;
  }

  function setup(root){
    root.classList.add('ddp');
    wallpaper = hasWallpaper() || wallpaperBefore(); recheckWallpaper();
    // the chart modules ask Python through the page's bridge; what they save goes to the widget under the mouse
    DD.call = function(cmd, args){ return DDP.call(cmd, Object.assign({_wid: DDP.curWid || null}, args || {})); };
    // the choices of a chart's header control (Future Due's Breakdown, its range): the Deep Dive window's menu
    // (app.js DD.webMenu), as the cards' other menus here
    DD.menu = function(pos, items, onPick){
      // "Edit Buttons...": this widget's settings window (its right click's Settings), the widget the menu came from
      const wid = DDP.curWid || null;
      return DD.webMenu(pos || {x: 0, y: 0}, items || [], function(k, on){
        if (k === '__edit'){ if (wid) DDP.call('widget_settings', {id: wid}).catch(function(){}); return; }
        onPick(k, on);
      });
    };
    // the menus built by Python (web_menus.py) shown by the page; a click triggers the
    // entry's action. at: {x, y, top?} (top: above the label that opened it when there is no room under it)
    let menuShownAt = {x: 0, y: 0};
    function openWidgetSearch(wid, anchor, curQ){
      if (!wid || !DD.openSearchPopover) return;
      const rec = (S.boot && S.boot.recent_searches) || [];
      let pos = anchor;
      const el = S.root && S.root.querySelector('[data-wid="' + CSS.escape(String(wid)) + '"], [data-k="' + CSS.escape(String(wid)) + '"]');
      const box = el && (el.closest('.dd-card') || el.closest('.ddp-box') || el);
      if (box && box.getBoundingClientRect){
        pos = Object.assign({}, anchor && !anchor.nodeType ? anchor : {}, {avoid: box.getBoundingClientRect()});
      }
      DD.openSearchPopover(
        pos,
        curQ || '',
        rec,
        function(q){ return DDP.call('set_search_filter', {id: wid, query: q}); },
        function(res){
          if (S.boot && res && Array.isArray(res.recent)) S.boot.recent_searches = res.recent.slice();
        }
      );
    }
    function pyMenu(r, at){
      if (!r || !r.items || !r.items.length) return;
      menuShownAt = at;
      const m = DD.webMenu(at, r.items, function(k, on){ if (r.xo && typeof k === 'string' && k.indexOf('xo:') === 0){ DDP.curWid = r.xoWid; DD.optPick(r.xo, k, on); return; }
        if (k === '__dslider'){ DD.setWidgetSetting('', 'day_slider', !!on); return; }
        if ((k === '__lineup' || k === '__linedown') && r.lineMove){
          const lm = r.lineMove;
          DDP.call('drop', {cross: {id: lm.key, kind: 'movebox', keys: lm.keys, index: k === '__lineup' ? lm.up : lm.down}}).catch(function(){});
          return;
        }
        if (k === '__search_filter'){ openWidgetSearch(r.wid || DDP.curWid, at, r.search_query || ''); return; }
        DDP.call('menu_pick', {key: k, on: on === undefined ? null : on}).catch(function(){});
      });
      // reopened after a move of Position: its list open again
      if (m && r.open){ const b = m.querySelector('.dd-mi[data-k="' + String(r.open).replace(/"/g, '') + '"]'); if (b && b.onmouseenter) b.onmouseenter(); }
    }
    DDP.menuAgain = function(r){ pyMenu(r, menuShownAt); };
    DDP.menu = pyMenu;
    // a chart's own options, as in the Deep Dive (app.js ownOpt): an icon after its pills, the entries of its right
    // click that change this chart alone (web_menus: its own entries), the options of its header's icon first (Include
    // Suspended Cards...: discrete.js DD.optionsPill), its Day Slider last. Whether it has any is asked on its first
    // hover (a menu built by Python: nothing more while the main screen is built), then kept for the widget
    const ownN = DDP._ownN || (DDP._ownN = {});
    const OWN_SVG = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M2 14h4M10 8h4M18 16h4"/></svg>';
    function isChart(card){ return !!card && card.classList.contains('dd-card') && !!card.dataset.wid && card.dataset.type !== 'heatmap' && card.dataset.type !== 'text_label'; }
    function ownOpt(card){
      if (!isChart(card)) return;
      const head = card.querySelector('.dd-head'); if (!head) return;
      const xo = head._ddOpt, mi = card._ddp && card._ddp.inst && card._ddp.inst.machine;
      // its own entries counted at its first hover (askOwn: a menu built by Python, nothing more while the main screen
      // is built); till then it is taken to have some: the icon is there from the start, as on the other charts
      // (Activity, Retention showed it only once hovered), and goes if it has none
      // counted at a hover of an earlier main screen: kept with the widget (pinned.py own_n), no icon that goes
      const wid = card.dataset.wid, own = (wid in ownN) ? ownN[wid] : card.dataset.ownN != null ? (+card.dataset.ownN || 0) : 1;
      const n = own + (xo ? xo.items.length : 0) + (mi ? 1 : 0) + (DD.pastOf && DD.pastOf[card.dataset.type] ? 1 : 0) + (head._retPayload ? 1 : 0);
      let wrap = head.querySelector('.dd-ownopt');
      if (!n){ if (wrap) wrap.remove(); return; }
      if (!wrap){
        wrap = document.createElement('span'); wrap.className = 'dd-pills dd-ownopt';
        wrap.innerHTML = '<button class="dd-pill dd-pill-opt dd-pill-ico" title="This chart\'s options">' + OWN_SVG + '</button>';
        head.appendChild(wrap);
        wrap.firstChild.addEventListener('click', function(e){ e.stopPropagation(); e.preventDefault(); ownMenu(card, e.currentTarget); });
      }
      // lit while an option of its header's icon is off its default (as in the Deep Dive)
      wrap.firstChild.classList.toggle('on', !!(xo && xo.items.some(function(it){ return xo.cur[it[0]] !== it[3]; })));
    }
    function askOwn(card){
      const wid = card.dataset.wid;
      if (!isChart(card) || wid in ownN || card._ownAsk) return;
      card._ownAsk = true;
      DDP.call('menu', {id: wid, own: true, count: true, deck: S.boot.deck}).then(function(r){
        ownN[wid] = (r && r.n) || 0; card._ownAsk = false; ownOpt(card);
      }).catch(function(){ card._ownAsk = false; });
    }
    function ownMenu(card, btn){
      const wid = card.dataset.wid, head = card.querySelector('.dd-head'), xo = head && head._ddOpt;
      const mi = card._ddp && card._ddp.inst && card._ddp.inst.machine;
      const r = btn.getBoundingClientRect(), at = {x: r.left, y: r.bottom + 2, top: r.top};
      // opened from the header's "..." (its pills with no room, dd-core watchStat): those pills first, in this menu
      const pre = head && head._ddPre; if (pre) delete head._ddPre;
      DDP.curWid = wid; menuAt = [r.left, r.bottom];
      DDP.call('menu', {id: wid, own: true, deck: S.boot.deck, zoom: Object.keys(zoomed)}).then(function(res){
        // (its windows, Edit Searches...: a pill of their own, and in the right click)
        let items = xo ? DD.optItems(xo).filter(function(it, i){ return xo.items[i][4] !== 'action'; }) : [];
        // First Answer Retention: the cards counted (as its header's pill) and what the ring shows (pie.js)
        const retP = card.dataset.type === 'todays_retention' && head && head._retPayload;
        if (retP && DD.retentionOptions) items = items.concat([['rkind', 'Cards', undefined, null, false, DD.retentionMenu(retP)]], DD.retentionOptions(retP));
        if (res && res.items && res.items.length) items = items.concat(['sep'], res.items);
        if (pre) items = pre.items.concat(['sep'], items);
        if (mi) items.push('sep', ['__dslider', 'Day Slider', mi.on(), null, true]);
        // its Time Machine, pinned right after it (or brought into view when it is already pinned)
        if (DD.pastOf && DD.pastOf[card.dataset.type]) items.push('sep', ['__past', 'View on a Past Day', undefined, 'history']);
        items = items.filter(function(it, i){ return it !== 'sep' || (i > 0 && i < items.length - 1 && items[i - 1] !== 'sep'); });
        if (!items.length) return;
        menuShownAt = at;
        DD.webMenu(at, items, function(k, on){
          DDP.curWid = wid;
          if (pre && pre.pick(k, on)) return;
          if (k === '__dslider'){ DD.setWidgetSetting('', 'day_slider', !!on); return; }
          if (k === '__past'){
            DDP.call('pin_past', {id: wid}).then(function(r){
              if (!r || r.added) return;  // (a new one comes in with the main screen built again)
              const el = root.querySelector('.ddp-card[data-wid="' + String(r.id).replace(/"/g, '') + '"]');
              if (!el) return;
              el.scrollIntoView({block: 'nearest', behavior: DD.anim && DD.anim.on === false ? 'auto' : 'smooth'});
              DD.flashCard && DD.flashCard(el);
            }).catch(function(){});
            return;
          }
          if (retP && DD.retentionPick(retP, k, on)) return;
          if (xo && typeof k === 'string' && k.indexOf('xo:') === 0){
            const p = DD.optPick(xo, k, on);
            if (p && p[1] !== xo.cur[p[0]]){ xo.cur[p[0]] = p[1]; ownOpt(card); DD.setWidgetSetting(xo.section, p[0], p[1]); }
            return;
          }
          // (an entry may bring others: Breakdown by Type, Series. Asked again on the next hover)
          delete ownN[wid];
          DDP.call('menu_pick', {key: k, on: on === undefined ? null : on}).catch(function(){});
        });
      }).catch(function(){});
    }
    DD.ownOptions = function(head){ ownOpt(head.closest('.ddp-card')); };
    root.addEventListener('mouseover', function(ev){ const t = ev.target.closest && ev.target.closest('.ddp-card[data-wid]'); if (t) askOwn(t); }, true);
    // the menus are on the page's body, out of the block that holds the theme's --dd-* colours: given them
    DD.menuStyle = function(m){
      const st = S && S.root && S.root.style;
      if (!st) return;
      for (let i = 0; i < st.length; i++){ const k = st[i]; if (k.indexOf('--dd-') === 0) m.style.setProperty(k, st.getPropertyValue(k)); }
    };
    // a chart's header control (Future Due's Backlog / Breakdown / range): DD.setWidgetSetting was Deep Dive's only, the
    // click did nothing here. Saved on the widget, then its data read again and morphed in (the page shows it itself)
    DD.setWidgetSetting = function(type, key, value){
      const wid = DDP.curWid;
      if (!wid) return Promise.resolve();
      return DD.call('set_setting', {section: type, key: key, value: value}).then(function(){
        return DDP.call('data', {id: wid, deck: S && S.boot ? S.boot.deck : null});
      }).then(function(data){
        const el = S && S.root.querySelector('[data-wid="' + wid + '"]'), d = el && el._ddp;
        if (!d || !d.inst || !data) return;
        const js = JSON.stringify(data); if (js === d.dataJs) return;
        const old = d.dataJs ? JSON.parse(d.dataJs) : undefined; d.dataJs = js;
        // another breakdown: the colours change at once, the bars stay
        const still = key === 'breakdown', prev = DD._noAnim; if (still) DD._noAnim = true;
        try { feed(d.inst, data, key === 'time_span_idx' ? undefined : 'timespan', d.w, old); } finally { DD._noAnim = prev; }
      }).catch(function(e){ DD.log('pinned setting ' + type + '.' + key + ': ' + (e && e.message || e)); });
    };
    // the menu's "About This Chart": the explanation where the menu was opened
    let menuAt = [0, 0];
    DDP.showHelp = function(wid){
      const card = root.querySelector('.ddp-card[data-wid="' + String(wid).replace(/"/g, '') + '"]'); if (!card) return;
      DDP.call('chart_help', {wtype: card.dataset.type}).then(function(h){ DD.helpPopup(h, menuAt[0], menuAt[1], root); }).catch(function(){});
    };
    // right click (or the stat cards' "⋯"): the pinned menu (web_menus.py)
    // touch: hold a card to lift it, move to drag it (the mouse drag of setupEdit, fed by the lift), or let go for its menu
    if (DD.touchLift){
      DD.touchLift(root, {
        pick: function(t){ return t.closest && t.closest('.ddp-card[data-wid], .dd-sc[data-key]'); },
        ignore: 'button, input, select, .dd-zbar, .dd-tm',
        // held near its right / bottom edge: the card is resized (the 8 px edge of the mouse is too thin for a finger)
        edge: function(card, x, y){ const f = itemOf(card); return f ? DD.touchEdge(card, x, y, resizeDirs(f.it)) : null; },
        drag: function(phase, x, y, card, target){
          if (phase === 'start'){
            const f = itemOf(card);
            DD.touchEvent('mouse', 'mousedown', x, y, card, {ddEdge: f ? DD.touchEdge(card, x, y, resizeDirs(f.it)) : null});  // on the card: not a zoom on its plot
          } else DD.touchEvent('mouse', phase === 'move' ? 'mousemove' : 'mouseup', x, y);
        },
        menu: DD.openMenuAt,
      });
    }
    root.addEventListener('contextmenu', function(ev){
      const t = ev.target.closest('[data-wid], .dd-sc[data-key]'); if (!t) return;
      ev.preventDefault();
      menuAt = [ev.clientX, ev.clientY];
      const at = {x: ev.clientX, y: ev.clientY};
      // a Time Machine: its Day Slider (the page's own entry), before the menu's last group
      const mi = t._ddp && t._ddp.inst && t._ddp.inst.machine;
      if (mi) DDP.curWid = t.dataset.wid;
      DDP.call('menu', {id: t.dataset.wid || t.dataset.key, x: ev.clientX, y: ev.clientY, deck: S.boot.deck, zoom: Object.keys(zoomed)}).then(function(r){
        if (mi && r && r.items){ const it = r.items.slice(), s = it.lastIndexOf('sep'); it.splice(s < 0 ? it.length : s, 0, 'sep', ['__dslider', 'Day Slider', mi.on(), null, true]); r = Object.assign({}, r, {items: it}); }
        // the chart's own windows (Edit Searches...: an action of its header's options icon) right under Settings
        const hd = t.querySelector && t.querySelector('.dd-head'), xo = hd && hd._ddOpt;
        const acts = xo ? DD.optItems(xo).filter(function(it, i){ return xo.items[i][4] === 'action'; }) : [];
        if (acts.length && r && r.items){
          const it = r.items.slice(), set = DD.t('Settings');
          const at0 = it.findIndex(function(x){ return Array.isArray(x) && (x[1] === set || x[1] === 'Settings'); });
          it.splice(at0 < 0 ? 0 : at0 + 1, 0, ...acts);
          r = Object.assign({}, r, {items: it, xo: xo, xoWid: t.dataset.wid});
        }
        // touch: no line grip; a line showing several widgets side by side (a tablet) moves from its menu instead
        const lm = DD.isTouch && DD.isTouch() && r && r.items ? lineMoves(t.dataset.wid || t.dataset.key) : null;
        if (lm){
          const it = r.items.slice(), s = it.lastIndexOf('sep'), add = ['sep'];
          if (lm.up != null) add.push(['__lineup', 'Line: move up', undefined, null]);
          if (lm.down != null) add.push(['__linedown', 'Line: move down', undefined, null]);
          it.splice(s < 0 ? it.length : s, 0, ...add);
          r = Object.assign({}, r, {items: it, lineMove: lm});
        }
        pyMenu(r, at);
      }).catch(function(){});
    });
    // the moves of a widget's whole line (as its grip's drag: drag_layout's box moves), when it has several side by side
    function lineMoves(id){
      const b = boxOfId(id); if (!b) return null;
      const secs = sections(), keys = secs.map(function(s){ return s.box.key; }), i = keys.indexOf(b.key);
      if (secs.length < 2 || i < 0) return null;
      const els = b.fam === 'stat' ? Array.from(b.el.querySelectorAll('.dd-sc')) : b.items.map(function(it){ return it.el; });
      const tops = els.map(function(el){ return Math.round(el.getBoundingClientRect().top / 6); });
      if (!tops.some(function(t, j){ return tops.indexOf(t) !== j; })) return null;  // one per row: moving the widget is enough
      return {key: b.key, keys: keys, up: i > 0 ? i - 1 : null, down: i < keys.length - 1 ? i + 2 : null};
    }
    root.addEventListener('mouseover', function(ev){
      const t = ev.target.closest && ev.target.closest('[data-wid], .dd-sc[data-key]'); if (!t) return;
      DDP.curWid = t.dataset.wid || t.dataset.key;
      // more_button: the "⋯" floats in the empty stretch of the title row, right before its buttons; no room, none
      // (it never covers the title or a pill, nothing moves)
      if (t.dataset.wid) placeMore(t);
    }, true);
    // at the right end of the title row's empty stretch, right before the first thing on
    // the right of it (the pills, the zoom arrow...), or the row's end; less than its width free there, none
    function placeMore(card){
      const head = card.querySelector('.dd-head'), sp = head && head.querySelector('.dd-spacer'), hb = sp && sp.querySelector('.dd-hbtns');
      if (!hb){ card.classList.add('nomore'); return; }
      // the pills gliding (a heatmap's view switch): measured now they are halfway; the switch places it itself
      const pl = head.querySelector('.dd-pills');
      if (pl && pl.getAnimations && pl.getAnimations({subtree: true}).some(function(a){ return a.playState === 'running'; })) return;
      const hr = head.getBoundingClientRect(), sr = sp.getBoundingClientRect();
      let right = hr.right - (parseFloat(getComputedStyle(head).paddingRight) || 0);
      // the leftmost thing drawn on the right of the empty stretch (a pill, a chip, the zoom arrow...), however deep
      // the stretch starts after what is drawn before it (the "?" draws over the spacer's first pixels)
      let left = sr.left;
      const shown = function(n, r){ if (r.width < 2 || r.height < 2) return false; const cs = getComputedStyle(n); return cs.visibility !== 'hidden' && cs.display !== 'none' && +cs.opacity !== 0; };
      head.querySelectorAll('*').forEach(function(n){
        if (sp.contains(n) || n.contains(sp) || !(sp.compareDocumentPosition(n) & Node.DOCUMENT_POSITION_PRECEDING)) return;
        if (n.closest('.dd-help')) return;  // the "?" gives way to the "⋯" (below)
        const r = n.getBoundingClientRect(); if (shown(n, r)) left = Math.max(left, r.right);
      });
      const hq = head.querySelector('.dd-help'), hs = hq && hq.querySelector('svg');
      const qr = hs && hq.offsetParent !== null && !head.classList.contains('dd-help-off') ? hs.getBoundingClientRect() : null;
      head.querySelectorAll('*').forEach(function(n){
        if (sp.contains(n) || n.contains(sp) || !(sp.compareDocumentPosition(n) & Node.DOCUMENT_POSITION_FOLLOWING)) return;
        const r = n.getBoundingClientRect();
        if (r.width < 2 || r.height < 2 || r.left < sr.left + 1 || r.left >= right) return;
        const cs = getComputedStyle(n);
        if (cs.visibility === 'hidden' || cs.display === 'none' || +cs.opacity === 0) return;
        // a box (the pills' row) counts by what it shows, not by its empty part
        if (n.children.length && !Array.from(n.childNodes).some(function(c){ return c.nodeType === 3 && c.textContent.trim(); }) && !/^(svg|img|canvas|button)$/i.test(n.tagName)) return;
        right = r.left;
      });
      const w = hb.offsetWidth || 22;
      if (right - left < w + 6){ card.classList.add('nomore'); card.classList.remove('dd-help-yield'); return; }
      // already shown (the mouse in the card): it glides to its new place with the pills (320 ms), not at once
      const nr = (sr.right - right + 4) + 'px', wasOff = card.classList.contains('nomore');
      card.classList.remove('nomore');
      if (hb.style.right !== nr){
        const seen = !wasOff && hb.style.right && card.matches(':hover') && +getComputedStyle(hb).opacity > 0.05 && hb.animate && DD.anim && DD.anim.on;
        const x0 = seen ? hb.getBoundingClientRect().left : 0;
        if (hb.getAnimations) hb.getAnimations().forEach(function(a){ a.cancel(); });
        hb.style.right = nr;
        if (seen){
          const dx = x0 - hb.getBoundingClientRect().left;
          if (Math.abs(dx) >= 0.5) hb.animate([{translate: dx + 'px 0'}, {translate: '0 0'}], {duration: 320 * (DD.calm ? DD.calm() : 1), easing: 'cubic-bezier(.33,1,.68,1)'});
        }
      }
      // the "⋯" before the "?": room for one only, the "?" is hidden
      card.classList.toggle('dd-help-yield', !!qr && qr.right + 2 > right - 4 - w);
    }
    DDP.placeMore = placeMore;
    // a chart's "⋯" (more_button): the same menu, under the button
    root.addEventListener('click', function(ev){
      const b = ev.target.closest && ev.target.closest('.dd-more'); if (!b) return;
      const card = b.closest('[data-wid]'); if (!card) return;
      ev.stopPropagation(); ev.preventDefault();
      const r = b.getBoundingClientRect();
      card.dispatchEvent(new MouseEvent('contextmenu', {bubbles: true, cancelable: true, clientX: r.left, clientY: r.bottom}));
    }, true);
    // a click (no drag) on a bar, a point, a slice or an hour shows its cards in Anki's browser (browser_click)
    let clickAt = null, lastTouchAt = 0;
    root.addEventListener('pointerdown', function(e){ if (e.pointerType === 'touch') lastTouchAt = Date.now(); }, true);
    root.addEventListener('mousedown', function(e){ clickAt = e.button === 0 ? [e.clientX, e.clientY] : null; }, true);
    root.addEventListener('mouseup', function(e){
      const p = clickAt; clickAt = null;
      if (!p || e.button !== 0 || Math.abs(e.clientX - p[0]) + Math.abs(e.clientY - p[1]) > 5) return;
      // On touch screens, tapping a bar inspects its tooltip instead of opening the Card Browser.
      if ((DD.isTouch && DD.isTouch()) || Date.now() - lastTouchAt < 800) return;
      const plot = e.target.closest && e.target.closest('.dd-plot'), card = e.target.closest && e.target.closest('[data-wid]');
      if (!plot || !card || !plot._ddBrowse || plot.classList.contains('dd-dots-on') || e.target.closest('.dd-zbar, .dd-zctl')){
        if (DD.dev && card) DD.trace('BROWSE no (' + (card.querySelector('.dd-title') ? card.querySelector('.dd-title').textContent : card.dataset.wid) + '): ' + (!plot ? 'not on the chart' : !plot._ddBrowse ? 'this chart opens nothing' : 'dots / scroll bar'));
        return;
      }
      let spec = null; try { spec = plot._ddBrowse(); } catch (err) { spec = null; }
      if (DD.dev) DD.trace('BROWSE ' + (card.querySelector('.dd-title') ? card.querySelector('.dd-title').textContent : '') + ': ' + (spec ? JSON.stringify(spec) : 'nothing under the mouse'));
      if (spec) DDP.call('browse', Object.assign({_wid: card.dataset.wid, deck: S.boot.deck}, spec)).catch(function(e){ DD.trace('BROWSE failed: ' + (e && e.message || e)); });
    });
    // Anki's zoom changes the pixel ratio: the charts watch their size in device pixels (DD.frame.observe) and are
    // drawn again for it at once. One still drawn for the old ratio (blurred) is told to size its canvas again:
    // the plots are made a pixel narrower for one frame, put back two frames later, as a media-query change runs before
    // that frame's requestAnimationFrame callbacks (put back in the first one, the layout never sees the narrower
    // plots, no ResizeObserver runs, and a chart can stay drawn for the old ratio). Only then: done at every zoom, each
    // chart was drawn a pixel narrower then wide again, and bounced inside its card
    let sharpAfter = 0;
    // a page Anki has just built is laid out at first without Anki's zoom (dpr 1 for a frame or two, then 1.2): a
    // layout chosen from the pixel ratio (a donut's legend beside it or behind its icon, pie.js) takes the ratio the
    // main screen had last (boot.dpr, sent by the page below) until the zoom is applied or 1.5 s have passed
    let expectDpr = (S && S.boot && +S.boot.dpr) || 0, sentDpr = (S && S.boot && +S.boot.dpr) || 0;
    DD.layoutDpr = function(d){ return expectDpr || d; };
    function sendDpr(){
      const d = window.devicePixelRatio || 1;
      if (Math.abs(d - sentDpr) < 0.001) return;
      sentDpr = d; DDP.call('dpr', {v: d}).catch(function(){});
    }
    function nudge(){
      root.querySelectorAll('.dd-plot').forEach(function(p){ p.style.width = 'calc(100% - 1px)'; });
      requestAnimationFrame(function(){ requestAnimationFrame(function(){ root.querySelectorAll('.dd-plot').forEach(function(p){ p.style.width = ''; }); }); });
    }
    (function watchDpr(){
      if (!window.matchMedia) return;
      const mq = window.matchMedia('(resolution: ' + (window.devicePixelRatio || 1) + 'dppx)');
      const on = function(){
        mq.removeEventListener ? mq.removeEventListener('change', on) : mq.removeListener(on);
        DD.trace('SHARP dpr change -> ' + (window.devicePixelRatio || 1).toFixed(3));
        expectDpr = 0; sendDpr();
        requestAnimationFrame(function(){ requestAnimationFrame(function(){ checkSharp('zoom'); }); });
        clearTimeout(sharpAfter); sharpAfter = setTimeout(function(){ checkSharp('after zoom'); }, 400);
        watchDpr();
      };
      mq.addEventListener ? mq.addEventListener('change', on) : mq.addListener(on);
    })();
    // a page shown again (another deck and back) can be laid out before Anki's zoom is applied: canvases drawn for the
    // old ratio look blurred. Checked a little after it shows; the charts are told to size their canvases again.
    function checkSharp(tag){
      const d = window.devicePixelRatio || 1; let bad = 0, n = 0, ex = '';
      root.querySelectorAll('.dd-plot canvas').forEach(function(cv){
        if (!cv.clientWidth) return; n++;
        const want = Math.round(cv.clientWidth * d), wantH = Math.round(cv.clientHeight * d);
        const card = cv.closest('[data-wid]'), name = (card && card.dataset.wid) || '?';
        if (Math.abs(cv.width - want) > 2 || Math.abs(cv.height - wantH) > 2){
          bad++;
          ex += ' ' + name + ' ' + cv.width + 'x' + cv.height + ' for ' + cv.clientWidth + 'x' + cv.clientHeight + 'css';
        }
      });
      DD.trace('SHARP ' + tag + ' dpr=' + d.toFixed(3) + ' canvases=' + n + ' blurred=' + bad + ex);
      if (bad) nudge();
    }
    setTimeout(function(){ checkSharp('300ms'); }, 300);
    setTimeout(function(){ checkSharp('1500ms'); expectDpr = 0; sendDpr(); }, 1500);
    document.addEventListener('visibilitychange', function(){ if (!document.hidden) setTimeout(function(){ checkSharp('shown'); }, 200); });
    // the "?" of a chart: its explanation on hover (chart_help), and no "?" when there is none
    const helpCache = {};
    const helpText = function(t){ return helpCache[t] !== undefined ? Promise.resolve(helpCache[t]) : DDP.call('chart_help', {wtype: t}).then(function(h){ helpCache[t] = h || ''; return helpCache[t]; }); };
    DDP.helpCheck = function(head){
      const hq = head && head.querySelector('.dd-help'); if (!hq) return;
      helpText(hq.getAttribute('data-t')).then(function(t){ if (!t) hq.style.display = 'none'; }).catch(function(){});
    };
    let helpTip = null;
    root.addEventListener('mouseover', function(e){
      const h = e.target.closest && e.target.closest('.dd-help'); if (!h || h === helpTip) return;
      helpTip = h;
      helpText(h.getAttribute('data-t')).then(function(txt){
        if (helpTip !== h || !txt) return;
        const old = root.querySelector('.dd-helptip'); if (old) old.remove();
        const t = document.createElement('div'); t.className = 'dd-helptip'; t.style.position = 'fixed'; t.textContent = txt; root.appendChild(t);
        const r = h.getBoundingClientRect();
        t.style.left = Math.min(r.right + 6, window.innerWidth - t.offsetWidth - 8) + 'px';
        t.style.top = Math.min(r.bottom + 6, window.innerHeight - t.offsetHeight - 8) + 'px';
      });
    });
    root.addEventListener('mouseout', function(e){
      const h = e.target.closest && e.target.closest('.dd-help'); if (!h) return;
      if (e.relatedTarget && h.contains(e.relatedTarget)) return;
      helpTip = null; const old = root.querySelector('.dd-helptip'); if (old) old.remove();
    });
    if (window.ResizeObserver) new ResizeObserver(function(){ DDP.relayout(); }).observe(root);
    window.addEventListener('resize', function(){ DDP.relayout(); });
    if (DDP.setupEdit) DDP.setupEdit(root);
  }

  function statsBox(el, ws, boot, box){
    const host = document.createElement('div'); host.className = 'dd-sc-host';
    el.appendChild(host);
    const ids = ws.map(function(w){ return w.id; });
    const pre = boot.pre_stats && boot.pre_stats[ids.join(',')];
    let inst = null;
    // Anki's start (the block's intro): the values count up from zero with the charts' intro, as the Deep Dive's
    // (stats.js hooks.intro: shown at zero in the skeleton, rolled at DD.go)
    const intro = function(){ return !!(S && S.introQ) && !DD._go; };
    // the values the cards showed last, on any screen (pinned.py _LAST_STAT): another deck or the deck list may show
    // other cards, or show these last for another deck. The cards start from them (a new one from zero) and roll to
    // their values when those come; without, they start from their own last picture
    const last = boot.stat_last && Object.keys(boot.stat_last).length ? boot.stat_last : null;
    let from = intro() ? null : last;
    const mount = function(spec, hold){
      inst = DD.stats.mount(host, spec, boot.theme, intro() ? {intro: true} : (from ? {from: from, hold: !!hold} : {}));
      from = null;
    };
    const held = !!(from && pre && pre.cards && pre.cards.length);
    if (pre && pre.cards && pre.cards.length) mount(pre, true);
    el._ddpStats = function(){  // a settings dialog's live preview: the cards with its settings
      DDP.call('stats', {ids: ids, deck: boot.deck}).then(function(spec){
        if (!spec || !spec.cards) return;
        if (inst){ inst.setTheme(DD.theme); inst.update(spec); } else mount(spec);
        DDP.relayout && DDP.relayout();
      }).catch(function(){});
    };
    DDP.call('stats', {ids: ids, deck: boot.deck}).then(function(spec){
      if (!spec || !spec.cards || !spec.cards.length) return;
      if (inst){
        if (!held && JSON.stringify(spec) === JSON.stringify(pre)) return;
        if (intro()){ inst.destroy(); mount(spec); }  // still at zero: its intro counts up to the new values
        else inst.update(spec);  // the values roll to the new ones
      }
      else mount(spec);
    }).catch(function(e){ DD.log('pinned stats: ' + (e && e.message || e)); });
  }

  function chartsBox(el, ws, boot, box){
    el.style.position = 'relative';
    box.items = ws.map(function(w){
      const old = S.keep && S.keep[w.id];
      const card = old || document.createElement('div');
      card.style.position = 'absolute';
      el.appendChild(card);
      const fixed = w.type === 'text_label' || (w.type === 'heatmap' && w.width == null);
      const nat = w.type === 'heatmap' ? heatmapNatural(w.options || {}) : null;
      // with its box, the heatmap's card is its natural size plus the box's margins (_wrap: 10, 6, 10, 6)
      if (nat && w.look && w.look.glass){ const p = w.look.pad || [6, 10, 6, 10]; nat.w += p[1] + p[3] + 2; nat.h += p[0] + p[2] + 2; }  // + its 1 px border
      const it = {wid: w.id, def: w, el: card, off: w.col_offset | 0, w: w.width != null ? +w.width : (nat ? nat.w : (DEF_W[w.type] || 450)),
        h: w.height != null ? +w.height : (w.nat ? +w.nat : (nat ? nat.h : (DEF_H[w.type] || 200))), fixed: fixed};
      if (old){ old._ddp.it = it; old._ddp.w = w; if (w.type === 'text_label') textRefresh(card, w, boot, it); else chartRefresh(card, w, boot, it); }
      else if (w.type === 'text_label') textWidget(card, w, boot, it);
      else chartWidget(card, w, boot, it);
      return it;
    });
    box.layout = function(){ masonry(el, box.items); };
  }

  function probe(t){ try { window.pycmd('ddp_probe:' + t); } catch (e) {} }
  window.addEventListener('error', function(e){ probe('error ' + (e.message || e) + ' @ ' + (e.filename || '').split('/').pop() + ':' + (e.lineno || 0)); });
  window.addEventListener('unhandledrejection', function(e){ probe('rejection ' + (e.reason && e.reason.message || e.reason)); });
  function textWidget(el, w, boot, it){
    const it0 = it, w0 = w;
    el.className = 'ddp-text ddp-card'; el.dataset.wid = w.id;
    applyLook(el, w.look);
    const put = function(html){
      const it = (el._ddp && el._ddp.it) || it0, w = (el._ddp && el._ddp.w) || w0;
      el.innerHTML = html || '';
      if (el._ddp) el._ddp.lastHtml = html;
      if (T && DD.dev) tlog('text put ' + String(html || '').replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 40));
      el.style.padding = '0 9px';
      if (w.width != null){ el.style.whiteSpace = 'normal'; it.w = +w.width; el.style.width = it.w + 'px'; el.style.height = 'auto'; }
      else { el.style.width = 'auto'; el.style.height = 'auto'; el.style.whiteSpace = 'nowrap'; it.w = Math.ceil(el.scrollWidth) + 2; }
      it.h = Math.max(44, Math.ceil(el.scrollHeight));  // wrapper: 44 px at least
      DDP.relayout();
    };
    el._ddp = {sig: cardSig(w), it: it, w: w, put: put};
    if (w.pre != null) put(w.pre);
    DDP.call('text', {id: w.id, deck: boot.deck}).then(function(html){ if (html !== w.pre) put(html); }).catch(function(){});
  }
  function textRefresh(el, w, boot, it){
    applyLook(el, w.look);
    const put = function(html){ el._ddp.it = it; el._ddp.put(html); };
    if (w.pre != null) put(w.pre);
    DDP.call('text', {id: w.id, deck: boot.deck}).then(function(html){ put(html); }).catch(function(){});
  }

  // The card's look (computed in Python, pinned._card_look): glass surface, hairline border, its hover
  function applyLook(el, look){
    if (!look) return;
    // the tint of the settings, as it is, with Auto glass or not: one default suits both (config.py)
    el.style.setProperty('--ddp-bg', look.bg);
    el.style.setProperty('--ddp-bd', look.border);
    el.style.setProperty('--ddp-bdh', look.hover);
    el.style.setProperty('--ddp-rad', (look.radius || 14) + 'px');
    el.style.setProperty('--ddp-pad', (look.pad || [0, 0, 0, 0]).map(function(v){ return v + 'px'; }).join(' '));
    // frosted glass: what is behind the box (Anki's background) blurred, when the setting asks for it
    el._ddpLook = look;
    const b = blurPx(look.blur);
    el.style.setProperty('--ddp-blur', look.glass && b ? 'blur(' + b + 'px)' : 'none');
    el.style.setProperty('--ddp-shadow', shadowCss(look.glass ? look.shadow : 0));
    el.classList.toggle('ddp-noglass', !look.glass);
  }
  // a soft shadow under a box (0-100 %): the box seems to float over Anki's background
  function shadowCss(p){
    const s = Math.max(0, Math.min(100, +p || 0)) / 100;
    return s ? '0 ' + (2 + 10 * s).toFixed(1) + 'px ' + (6 + 30 * s).toFixed(1) + 'px rgba(0,0,0,' + (0.08 + 0.35 * s).toFixed(3) + ')' : 'none';
  }
  // "Auto" blur (-1, the default): frosted only when Anki shows a background image (a wallpaper add-on's image on
  // the page, or a fixed full-window image behind it); over a plain background a blur shows nothing and only costs
  const AUTO_BLUR = 14;
  let wallpaper = null;
  function hasWallpaper(){
    const url = function(el, pseudo){ try { return /url\(/.test(getComputedStyle(el, pseudo || null).backgroundImage || ''); } catch (e) { return false; } };
    // the image of the page itself, or of its ::before / ::after (how background add-ons lay theirs, e.g. body::before)
    for (const el of [document.documentElement, document.body]){ if (url(el) || url(el, '::before') || url(el, '::after')) return true; }
    const vw = window.innerWidth, vh = window.innerHeight;
    for (const el of document.body.querySelectorAll('body > *, body > * > *')){
      if (el.id === 'ddp-root' || el.closest('#ddp-root')) continue;
      const cs = getComputedStyle(el);
      if (cs.position !== 'fixed' && cs.position !== 'absolute') continue;
      const r = el.getBoundingClientRect();
      if (r.width < vw * 0.8 || r.height < vh * 0.8) continue;
      if (url(el) || el.tagName === 'IMG' || el.tagName === 'VIDEO' || el.querySelector('img, video')) return true;
    }
    return false;
  }
  function blurPx(b){
    b = +b || 0;
    if (b >= 0) return b;
    return AUTO_BLUR;  // -1, saved by the former "Auto": the default blur (over a plain background it shows nothing)
  }
  // Anki builds its page again for many things (a deck folder opened, a deck studied): a wallpaper add-on puts its
  // image in after the block, so the block came up without the glass and took it a second later, at each new page.
  // What the last page found is remembered (for this webview's pages) and used until the page is looked at again.
  function wallpaperBefore(){ try { return localStorage.getItem('ddp-wallpaper') === '1'; } catch (e) { return false; } }
  function wallpaperSeen(v){ try { localStorage.setItem('ddp-wallpaper', v ? '1' : '0'); } catch (e) {} }
  // a wallpaper add-on may put its image in after the block: looked at again a little later
  function recheckWallpaper(){
    setTimeout(function(){
      const now = hasWallpaper();
      probe('wallpaper ' + now + ' (auto blur ' + (now ? AUTO_BLUR : 0) + ' px)' + (now !== wallpaper ? ' - changed since the page came up' : ''));
      wallpaperSeen(now);
      if (now === wallpaper) return;
      wallpaper = now;
      if (!S) return;
      S.root.querySelectorAll('[data-wid]').forEach(function(el){ if (el._ddpLook) applyLook(el, el._ddpLook); });
      statFx(S.root, S.root._ddpFx);
    }, 1200);
  }
  function statFx(root, fx){
    fx = fx || {}; root._ddpFx = fx;
    const b = blurPx(fx.blur);
    root.style.setProperty('--ddp-scblur', b ? 'blur(' + b + 'px) saturate(1.35)' : 'none');
    root.classList.remove('ddp-sclight');  // Auto keeps the fill as set (see applyLook)
    root.style.setProperty('--ddp-scshadow', shadowCss(fx.shadow));
  }
  // the settings dialogs' live preview (preview_styles): new looks for the boxes, the stat cards' glass, the theme
  DDP.restyle = function(p){
    if (!S || !p) return;
    // another theme previewed: the charts repainted with it too (their canvases kept the old one's texts)
    if (p.theme){
      const other = JSON.stringify(DD.theme || null) !== JSON.stringify(p.theme);
      setTheme(S.root, p.theme);
      if (other) S.root.querySelectorAll('[data-wid]').forEach(function(el){ const i = el._ddp && el._ddp.inst; try { if (i && i.setTheme) i.setTheme(DD.theme); } catch (e) {} });
    }
    statFx(S.root, p.stat_fx);
    let relay = false;
    Object.keys(p.looks || {}).forEach(function(id){
      const el = S.root.querySelector('[data-wid="' + id + '"]');
      if (el){ applyLook(el, p.looks[id]); if (syncHeatmapSize(el, el._ddp, p.opts && p.opts[id])) relay = true; }
    });
    // only the charts whose options changed, redrawn at once (no transition for each step of a slider)
    DD._noAnim = true;
    try {
      Object.keys(p.opts || {}).forEach(function(id){
        const el = S.root.querySelector('[data-wid="' + id + '"]'), d = el && el._ddp;
        if (!d || !d.inst || !d.inst.setOptions) return;
        const o = Object.assign({}, p.opts[id]); delete o.mode; delete o.today; delete o.logical_today;  // its view stays
        const js = JSON.stringify(o);
        if (d._pvOpts == null && d.w){ const w0 = Object.assign({}, d.w.options || {}); delete w0.mode; delete w0.today; delete w0.logical_today; d._pvOpts = JSON.stringify(w0); }
        if (d._pvOpts === js) return;
        d._pvOpts = js;
        try { d.inst.setOptions(o); if (syncHeatmapSize(el, d, o)) relay = true; } catch (e) {}
      });
    } finally { DD._noAnim = false; }
    if (relay && DDP.relayout) DDP.relayout();
    S.root.querySelectorAll('.dd-sc-host').forEach(function(h){ if (h.parentNode && h.parentNode._ddpStats) h.parentNode._ddpStats(); });
  };
  // the heatmap's right-click Color...: its live preview, on every heatmap that reads the shared colors
  DDP.heatmapPalette = function(p){
    if (!S || !p) return;
    DD._noAnim = true;
    try {
      S.root.querySelectorAll('[data-wid]').forEach(function(el){
        const d = el._ddp;
        if (!d || !d.w || d.w.type !== 'heatmap' || !d.inst || !d.inst.setOptions) return;
        d.w.options = Object.assign(d.w.options || {}, p);
        try { d.inst.setOptions(p); } catch (e) {}
      });
    } finally { DD._noAnim = false; }
  };
  // card_chips._Chip: the period ("Past Month") and the deck it reads, right after the title
  function chips(head, w){
    const t = head.querySelector('.dd-title'); if (!t) return;
    if (w.search_query){
      const f = document.createElement('span');
      f.className = 'ddp-chip ddp-flt-chip';
      f.title = 'Search filter: ' + w.search_query + ' (click to edit)';
      f.addEventListener('mousedown', function(ev){ ev.stopPropagation(); });
      f.addEventListener('click', function(ev){
        ev.stopPropagation();
        const card = f.closest('.dd-card');
        if (card) DDP.curWid = card.dataset.wid;
        if (DD.openSearchPopover){
          const rec = (S.boot && S.boot.recent_searches) || [];
          DD.openSearchPopover(
            f,
            w.search_query || '',
            rec,
            function(q){ return DDP.call('set_search_filter', {id: w.id, query: q}); },
            function(res){ if (S.boot && res && Array.isArray(res.recent)) S.boot.recent_searches = res.recent.slice(); }
          );
        }
      });
      f.textContent = w.search_query;
      t.parentNode.insertBefore(f, t.nextSibling);
    }
    (w.chips || []).map(function(label, i){ return [label, i ? 'deck' : 'span']; }).filter(function(p){ return p[0]; }).reverse().forEach(function(p){
      const label = p[0];
      const c = document.createElement('span'); c.className = 'ddp-chip'; c.title = p[1] === 'deck' ? 'Select Decks...' : 'Time Span';
      c.addEventListener('mousedown', function(ev){ ev.stopPropagation(); });
      c.addEventListener('click', function(ev){
        ev.stopPropagation(); const r = c.getBoundingClientRect();
        // the period list shown here (its entries from Python); the decks, a dialog of Anki's
        const card = c.closest('.dd-card'), av = card ? card.getBoundingClientRect() : null;
        DDP.call('chip', {id: w.id, which: p[1], x: r.left, y: r.bottom + 2, top: r.top}).then(function(q){
          if (q && q.items && DDP.menu) DDP.menu(q, {x: r.left, y: r.bottom + 2, top: r.top, avoid: av});
        }).catch(function(){});
      });
      c.innerHTML = '<span></span><svg width="7" height="5" viewBox="0 0 7 5"><path d="M.5 1 3.5 4 6.5 1" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/></svg>';
      c.firstChild.textContent = label;
      t.parentNode.insertBefore(c, t.nextSibling);
    });
  }

  // ---- zoom shared between the pinned charts: one chart zoomed, the others linked to it
  // zoom to the same dates; the reset arrow in the header (add_pinned_zoom_reset_button) while zoomed ----
  const ZF = DD.zoomFlow;  // (charts/zoom_camera.js: shared with the Deep Dive)
  const zoomed = {};  // widget id -> {w, z, btn}
  const EXP = {};     // widget id -> true | 'busy' when temporarily zoomed out past its saved time span
  let zbusy = false;
  function dateOf(label){ if (label == null) return null; const t = Date.parse(String(label)); return isNaN(t) ? null : t; }
  function indexRange(z, d0, d1){
    let first = null, last = null;
    for (let i = 0, n = z.count(); i < n; i++){
      const d = dateOf(z.label(i)); if (d == null) return null;
      if (first == null && d >= d0) first = i;
      if (d <= d1) last = i;
    }
    return (first == null || last == null || last < first) ? null : [first, last];
  }
  function showReset(e){
    if (!e.btn) return;
    const vis = (e.z.get() || AZ[e.w.id] || EXP[e.w.id] === true) ? 'visible' : 'hidden';
    if (e.btn.style.visibility === vis) return;
    e.btn.style.visibility = vis;
    // the "⋯" make room for the arrow (or take it back) at once
    const card = e.btn.closest('[data-wid]'); if (card && DDP.placeMore) DDP.placeMore(card);
  }
  function inView(id){
    const el = S && S.root && S.root.querySelector('[data-wid="' + id + '"]');
    if (!el) return false;
    const r = el.getBoundingClientRect();
    return r.height > 0 && r.bottom > 4 && r.top < window.innerHeight - 4;
  }
  function quiet(id, fn){
    const prev = DD._noAnim;
    if (!inView(id)) DD._noAnim = true;
    try { fn(); } finally { DD._noAnim = prev; }
  }
  function linkFrom(srcId, range){
    if (zbusy) return;
    const src = zoomed[srcId]; if (!src || src.unlinked || AZ[srcId] && range) return;  // inside the 10-minute view: its own
    if (dateOf(src.z.label(0)) == null) return;  // not a chart of days (seconds, intervals, hours): its zoom is its own
    followSoon(srcId, range);
    let d0 = null, d1 = null;
    if (range){ d0 = dateOf(src.z.label(range[0])); d1 = dateOf(src.z.label(range[1] - 1)); if (d0 == null || d1 == null) return; }
    zbusy = true;
    try {
      Object.keys(zoomed).forEach(function(id){
        if (id === srcId) return;
        const e = zoomed[id]; if (e.unlinked) return;
        if (!range){ quiet(id, function(){ if (AZ[id]) leaveAdaptive(e, false); else if (e.z.get()) e.z.set(null); }); showReset(e); return; }
        if (AZ[id]) return;
        const span = indexRange(e.z, d0, d1); if (!span) return;
        if (span[0] === 0 && span[1] === e.z.count() - 1){ if (e.z.get()) quiet(id, function(){ e.z.set(null); }); showReset(e); return; }
        const cur = e.z.get(), r = [span[0], span[1] + 1];
        if (!cur || cur[0] !== r[0] || cur[1] !== r[1]){
          const vis = inView(id), held = vis && adaptiveCan(e, r) ? ZF.hold(e.z, cur) : null;
          quiet(id, function(){ e.z.set(r[0], r[1]); }); e.last = r;
          if (held || (!vis && adaptiveCan(e, r))) tryAdaptive(e, r, held);  // each linked chart goes to its 10-minute view too
        }
        showReset(e);
      });
    } finally { zbusy = false; }
  }
  // ---- the charts with no time axis follow a zoom of a chart of days, as in the Deep Dive (app.js followZoom):
  // Hourly, Answer Buttons, Answer Time... reading the same deck and search as the zoomed chart show its zoomed
  // days that fall in their own period, linked by dates as the charts of days are (pinned._h_zoom_follow); a reset
  // gives them their own data back. Asked once a burst of zoom steps
  // pauses, shown once the zoom's animation is over; the ones out of view take it without animation ----
  const FOLLOW = {distribution: 1, hourly: 1, answer_time: 1, interval_ratings: 1, rating_fatigue: 1, sibling_ratings: 1, fsrs_calibration: 1, forgetting_curve: 1, fsrs_fatigue: 1, week_hours: 1, todays_retention: 1};
  const FW = {};  // widget id (as a string) -> its id, while it shows zoomed days
  let fwTm = 0, fwSeq = 0;
  function followSoon(srcId, range){
    const src = zoomed[srcId];
    let first = null, last = null;
    if (range){ first = isoDay(src.z.label(range[0])); last = isoDay(src.z.label(range[1] - 1)); if (!first || !last) first = last = null; }
    const my = ++fwSeq;
    clearTimeout(fwTm);
    fwTm = setTimeout(function(){ follow(my, srcId, first, last); }, first == null ? 0 : 140);
  }
  function isoDay(label){  // "Nov 21, 2026" -> "2026-11-21" (its local day)
    const t = dateOf(/\d{4}\s*$/.test(String(label)) ? label : null); if (t == null) return null;  // (a 10-minute label, "Nov 21, 14:30": none)
    const d = new Date(t), p = function(n){ return (n < 10 ? '0' : '') + n; };
    return d.getFullYear() + '-' + p(d.getMonth() + 1) + '-' + p(d.getDate());
  }
  function followCard(id){
    const el = S && S.root && S.root.querySelector('[data-wid="' + CSS.escape(String(id)) + '"]');
    return el && el._ddp && el._ddp.inst ? el : null;
  }
  function follow(my, srcId, first, last){
    if (!S) return;
    const deck = S.boot.deck, wait = Math.round(300 * 1.4 * DD.speed()) + 60;
    const show = function(pairs){
      if (!pairs.length) return;
      DD.onIdle(function(){
        if (my !== fwSeq) return;
        pairs.forEach(function(p){
          const el = followCard(p[0]); if (!el || !p[1]) return;
          const d = el._ddp, js = JSON.stringify(p[1]); if (js === d.dataJs) return;
          const old = d.dataJs ? JSON.parse(d.dataJs) : undefined; d.dataJs = js;
          quiet(p[0], function(){ feed(d.inst, p[1], undefined, d.w, old, el); });
        });
      }, wait);
    };
    const restore = function(ids){
      ids.forEach(function(id){ delete FW[String(id)]; });
      return Promise.all(ids.map(function(id){
        return DDP.call('data', {id: id, deck: deck}).then(function(d){ return [id, d]; }).catch(function(){ return [id, null]; });
      }));
    };
    const back = Object.keys(FW).map(function(k){ return FW[k]; });
    if (first == null){ if (back.length) restore(back).then(show); return; }
    const ids = (S.boot.widgets || []).filter(function(w){ return FOLLOW[w.type] && String(w.id) !== String(srcId); }).map(function(w){ return w.id; });
    if (!ids.length) return;
    DDP.call('zoom_follow', {src: srcId, ids: ids, d0: first, d1: last, deck: deck}).then(function(r){
      if (my !== fwSeq) return;
      r = r || [];
      const got = {}; r.forEach(function(p){ got[String(p[0])] = true; });
      // those that followed another zoom (or these days are their whole period now): their own data again
      const stale = back.filter(function(id){ return !got[String(id)]; });
      r.forEach(function(p){ FW[String(p[0])] = p[0]; });
      (stale.length ? restore(stale) : Promise.resolve([])).then(function(more){ show(r.concat(more)); });
    }).catch(function(){});
  }
  DDP.setUnlinked = function(map){ Object.keys(zoomed).forEach(function(id){ zoomed[id].unlinked = !!(map || {})[id]; }); if (S) S.boot.unlinked = map || {}; };

  // ---- adaptive zoom (as in the Deep Dive, app.js): a zoom down to 2 days
  // switches Activity / Retention / Added and the charts of answers by day (providers.AZ_METRICS) to 10-minute bins over
  // those days, zooming from the held picture of the days; out of the whole 10-minute view (wheel) or the reset arrow
  // brings the days back ----
  const AZT = {activity: 1, retention: 1, added: 1, ratings: 1, forgotten: 1, review_speed: 1, introduced: 1, resets: 1}, AZ = {};
  function adaptiveCan(e, range){ return !!AZT[e.w.type] && !AZ[e.w.id] && ZF.canAdapt(e.z, range); }
  function swapPictured(e, data, range, alignRight, wa, wb, held){ ZF.swapPictured(e.z, data, range, alignRight, wa, wb, held, true); }
  function tryAdaptive(e, range, held){
    const f = e.z.label(range[0]), l = e.z.label(range[1] - 1), n = e.z.count(), my = e.azSeq = (e.azSeq || 0) + 1;
    DDP.call('adaptive', {id: e.w.id, first: f, last: l, deck: S ? S.boot.deck : null}).then(function(r){
      const cur = e.z.get();
      if (my !== e.azSeq || AZ[e.w.id] || !r || !r.data || !cur || cur[0] !== range[0] || cur[1] !== range[1]){ if (held) held.end(); return; }
      const alignRight = ZF.alignRight(range, n);
      AZ[e.w.id] = {first: f, last: l, alignRight: alignRight, times: r.times || null};
      swapPictured(e, r.data, null, alignRight, null, null, held);
      showReset(e);
      refreshDots(e, false);
    }).catch(function(){ if (held) held.end(); });
  }
  function leaveAdaptive(e, toWider){
    const az = AZ[e.w.id]; if (!az) return;
    // what is on screen (the dots, or the 10-minute bars) held still until the days are in, then one zoom from it
    // into them
    const held = ZF.holdShown(e.z, e.dots);
    dotsToBars(e, true);
    ZF.holdNow(e.z, held);
    delete AZ[e.w.id]; e.azSeq = (e.azSeq || 0) + 1;
    DDP.call('data', {id: e.w.id, deck: S ? S.boot.deck : null}).then(function(d){
      if (AZ[e.w.id] || !d){ if (held) held.end(); return; }
      const W = ZF.leaveWindows(ZF.labelsOf(e.w.type, d), az.first, az.last, e.z, toWider);
      swapPictured(e, d, W.range, az.alignRight, W.wa, W.wb, held);
      e.last = W.range; showReset(e);
      if (toWider) linkFrom(e.w.id, W.range);
    }).catch(function(){ if (held) held.end(); });
  }

  // ---- one dot per review (as in the Deep Dive): in the
  // 10-minute view zoomed to 3 hours or less, Activity shows each review as a dot; the bars sink while the dots
  // pop in (_SinkOut + their intro); back to the bars by a picture zoom; the dots window moves by camera zoom ----
  function dotsOf(e){
    return e.dotsFlow || (e.dotsFlow = ZF.dots({
      get: function(){ return e.dots ? {D: e.dots, z: e.z} : null; },
      active: function(){ return !!AZ[e.w.id]; },
      times: function(){ const az = AZ[e.w.id]; return az ? az.times : null; },
      fetch: function(t0, t1){ return DDP.call('review_events', {id: e.w.id, t0: t0, t1: t1, deck: S ? S.boot.deck : null}); },
      leave: function(){ leaveAdaptive(e, true); },
      onSet: function(){ e.last = e.z.get(); showReset(e); },
    }));
  }
  function dotsToBars(e, instant){ dotsOf(e).toBars(instant); }
  function refreshDots(e, immediate){ if (e.w.type === 'activity') dotsOf(e).refresh(immediate); }
  // Ctrl+wheel out of the whole dots window (the chart showing its dots)
  DD._dotsZoomOut = function(frac){
    const id = Object.keys(zoomed).filter(function(k){ const e = zoomed[k]; return e.dots && e.dots.visible(); })[0];
    if (id) dotsOf(zoomed[id]).zoomOut(frac);
  };

  function restorePinnedExpanded(e){
    const wid = e && e.w && e.w.id;
    if (!wid || !EXP[wid]) return;
    delete EXP[wid];
    const card = S && S.root && S.root.querySelector('[data-wid="' + CSS.escape(String(wid)) + '"]');
    const d = card && card._ddp;
    if (!d || !d.inst) return;
    DDP.call('data', {id: wid, deck: S.boot.deck}).then(function(data){
      if (!d.inst || !data) return;
      d.dataJs = JSON.stringify(data || {});
      e.last = null;
      if (e.z && e.z.swap) e.z.swap(data, null, true);
      else feed(d.inst, data, 'timespan', e.w, undefined, card);
      if (e.z && e.z.bar) e.z.bar();
      showReset(e);
    }).catch(function(){});
  }

  function expandPinnedBeyondSpan(e){
    const w = e && e.w;
    if (!w || EXP[w.id] || !w.span || w.span[0] === -1) return;
    const z = e.z;
    if (!z || !z.count || z.count() < 1) return;
    const first = z.label(0), last = z.label(z.count() - 1);
    const targets = e.unlinked ? [e] : Object.keys(zoomed).map(function(id){ return zoomed[id]; }).filter(function(o){
      return o && !o.unlinked && o.w && o.w.span && o.w.span[0] !== -1 && !EXP[o.w.id];
    });
    if (targets.indexOf(e) < 0) targets.unshift(e);
    targets.forEach(function(o){ EXP[o.w.id] = 'busy'; });
    Promise.all(targets.map(function(o){
      return DDP.call('data', {id: o.w.id, deck: S.boot.deck, span: -1}).then(function(data){ return [o, data]; }).catch(function(){ return [o, null]; });
    })).then(function(pairs){
      zbusy = true;
      try {
        pairs.forEach(function(pair){
          const o = pair[0], data = pair[1];
          if (!data){ delete EXP[o.w.id]; return; }
          const card = S && S.root && S.root.querySelector('[data-wid="' + CSS.escape(String(o.w.id)) + '"]');
          const d = card && card._ddp;
          if (!d || !d.inst){ delete EXP[o.w.id]; return; }
          EXP[o.w.id] = true;
          if (o.z.swap){ o.z.swap(data, null, true); }
          else ZF.noAnim(function(){ d.inst.update(data); });
          const win = ZF.expandWindow(o.z, first, last);
          if (win) o.z.set(win[0], win[1]); else o.z.set(null);
          o.last = o.z.get();
          showReset(o);
        });
      } finally { zbusy = false; }
      linkFrom(w.id, e.z.get());
    });
  }

  function zoomLink(w, el, head, inst){
    const z = inst && inst.zoom; if (!z || !z.set) return;
    const e = zoomed[w.id] = {w: w, z: z, dots: inst.dots || null, btn: null, last: z.get(), unlinked: !!((DDP.boot && DDP.boot.unlinked) || {})[w.id]};
    const b = document.createElement('button'); b.className = 'dd-zreset'; b.title = 'Reset Zoom';
    b.innerHTML = DD.icon ? DD.icon('reset', 14) : '&#8634;'; b.style.visibility = 'hidden';
    b.addEventListener('mousedown', function(ev){ ev.stopPropagation(); });
    b.addEventListener('click', function(ev){
      ev.stopPropagation();
      if (AZ[w.id]) leaveAdaptive(e, false);
      else if (EXP[w.id]){
        if (e.unlinked) restorePinnedExpanded(e);
        else Object.keys(zoomed).forEach(function(id){ const o = zoomed[id]; if (o && !o.unlinked && EXP[id]) restorePinnedExpanded(o); });
      }
      else { z.set(null); e.last = null; }
      showReset(e); linkFrom(w.id, null);
    });
    const pills = head.querySelector('.dd-pills'); head.insertBefore(b, pills || null);
    e.btn = b;
    z.onChange = function(r){
      if (DD.perfWatch) DD.perfWatch(r ? 'pinned zoom' : 'pinned zoom reset', 900);
      const prev = e.last; e.last = r ? r.slice() : null;
      showReset(e);
      if (!AZ[w.id] && adaptiveCan(e, r)) tryAdaptive(e, r, ZF.hold(e.z, prev));
      if (AZ[w.id]) refreshDots(e, false);
      linkFrom(w.id, r);
    };
    z.onOutLimit = function(){
      if (AZ[w.id]) leaveAdaptive(e, true);
      else if (!EXP[w.id] && w.span && w.span[0] !== -1) expandPinnedBeyondSpan(e);
    };
    z.canOutLimit = function(){ return !!AZ[w.id]; };  // the zoom bar's minus, in the hours of a zoom under two days
    showReset(e);
  }

  // a switch that changes the heatmap's height (mode, older years, space between the
  // years) takes the card from the old to the new height along with the cells (320 ms, smoothstep), the charts
  // under it following at each frame; the heatmap is laid out for the final height the whole time (layout_height)
  function heightTo(el, it, h1, wid){
    if (it && it.fs && el._fsFit){ it.fsH = true; el._fsFit(); return; }  // fullscreen: the screen's width sets its height (h1 is for that width: measured again on close)
    if (it && it.folded){ it.hFull = h1; DDP.call('natural', {id: wid, h: h1}).catch(function(){}); return; }  // collapsed: kept for later
    if (!it || it.h === h1) return;
    const body = el.querySelector('.dd-body'), h0 = it.h;
    if (el._ddpH){ cancelAnimationFrame(el._ddpH); el._ddpH = 0; const i0 = el._ddp && el._ddp.inst; if (i0 && i0.heightEnd) i0.heightEnd(); }
    const still = !S || !it.ph || (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
    DDP.call('natural', {id: wid, h: h1}).catch(function(){});
    if (still){ it.h = h1; DDP.relayout(); return; }
    // a switch of height: the canvas keeps the larger of both heights while the card glides, the grid is
    // placed for the final height and the legend stays above the card's edge (same easing as the cells)
    const inst = el._ddp && el._ddp.inst, cv = body && body.querySelector('canvas');
    let extra = 0, k = 0;
    if (body){
      const cs = getComputedStyle(el);
      extra = 22 + (parseFloat(cs.paddingTop) || 0) + (parseFloat(cs.paddingBottom) || 0) + (parseFloat(cs.borderTopWidth) || 0) + (parseFloat(cs.borderBottomWidth) || 0);
      k = cv ? body.clientHeight - cv.clientHeight : 0;
      body.style.flex = 'none'; body.style.height = Math.max(0, Math.max(h0, h1) - extra) + 'px';
    }
    const canvasH = function(h){ return Math.max(1, h - extra - k); };
    if (inst && inst.heightAnim) inst.heightAnim(canvasH(h1), canvasH(h0));
    el.style.overflow = 'hidden';
    let t0 = null;  // started on the next frame, as the heatmap's mode transition: the card edge and the legend stay together
    el._ddpH = requestAnimationFrame(function step(now){
      if (t0 === null) t0 = now;
      const t = Math.min(1, (now - t0) / 320), oc = 1 - Math.pow(1 - t, 3), e = oc * oc * (3 - 2 * oc);
      it.h = Math.round(h0 + (h1 - h0) * e); DDP.relayout();
      if (inst && inst.heightStep) inst.heightStep(canvasH(it.h));
      if (t < 1){ el._ddpH = requestAnimationFrame(step); return; }
      it.h = h1;
      el._ddpH = 0; if (body){ body.style.flex = ''; body.style.height = ''; }
      if (inst && inst.heightEnd) inst.heightEnd();
    });
  }
  // "Collapsible Charts": the chevron or the title folds the card to its
  // header (margins + header + 4), the body hidden; remembered for the session (_COLLAPSED_PINNED)
  function foldH(el){
    const cs = getComputedStyle(el), head = el.querySelector('.dd-head');
    return Math.round((parseFloat(cs.paddingTop) || 0) + (parseFloat(cs.paddingBottom) || 0) + (parseFloat(cs.borderTopWidth) || 0)
      + (parseFloat(cs.borderBottomWidth) || 0) + Math.max(22, head ? head.offsetHeight : 22) + 4);
  }
  function foldAnim(el, it, h1, done){
    const body = el.querySelector('.dd-body'), h0 = it.h, full = it.hFull || h0;
    if (el._ddpH){ cancelAnimationFrame(el._ddpH); el._ddpH = 0; const i0 = el._ddp && el._ddp.inst; if (i0 && i0.heightEnd) i0.heightEnd(); }
    if (body){ const cs = getComputedStyle(el), extra = (parseFloat(cs.paddingTop) || 0) + (parseFloat(cs.paddingBottom) || 0) + (parseFloat(cs.borderTopWidth) || 0) + (parseFloat(cs.borderBottomWidth) || 0);
      body.style.flex = 'none'; body.style.height = Math.max(0, full - 22 - extra) + 'px'; }
    el.style.overflow = 'hidden';
    const t0 = performance.now();
    (function step(now){
      const t = Math.min(1, (now - t0) / 220), e = t * t * (3 - 2 * t);
      it.h = Math.round(h0 + (h1 - h0) * e); DDP.relayout();
      if (t < 1){ el._ddpH = requestAnimationFrame(step); return; }
      el._ddpH = 0; if (body){ body.style.flex = ''; body.style.height = ''; }
      if (done) done();
    })(t0);
  }
  function foldSetup(el, w, boot, it){
    if (el._ddpFold) return; el._ddpFold = true;
    const head = el.querySelector('.dd-head');
    head.querySelector('.dd-chev').style.cursor = 'pointer';
    const tt = head.querySelector('.dd-title'); if (tt) tt.style.cursor = 'pointer';
    let down = null;
    head.addEventListener('mousedown', function(ev){ down = [ev.clientX, ev.clientY]; });
    head.addEventListener('click', function(ev){
      const p = down; down = null;  // a drag of the card is no click
      if (!p || Math.abs(ev.clientX - p[0]) + Math.abs(ev.clientY - p[1]) > 5) return;
      if (!ev.target.closest('.dd-chev, .dd-title') || !S.boot.collapsible) return;
      ev.stopPropagation();
      const cur = el._ddp ? el._ddp.it : it, on = !cur.folded;
      DDP.call('collapse', {id: w.id, on: on}).catch(function(){});
      if (on){ cur.hFull = cur.h; cur.folded = true; foldAnim(el, cur, foldH(el), function(){ el.classList.add('dd-collapsed'); }); }
      else { cur.folded = false; el.classList.remove('dd-collapsed'); foldAnim(el, cur, cur.hFull || cur.h); }
    });
    if ((boot.collapsed || []).indexOf(w.id) >= 0) foldNow(el, it);
  }
  function foldNow(el, it){
    if (it.folded) return;
    it.hFull = it.h; it.folded = true; el.classList.add('dd-collapsed');
    it.h = foldH(el);
  }

  // a kept card: its period / deck labels, its look, then its new data (morphed in, calmer like a period change)
  function chartRefresh(el, w, boot, it){
    const d = el._ddp, head = el.querySelector('.dd-head');
    head.querySelectorAll('.ddp-chip').forEach(function(c){ c.remove(); });
    chips(head, w); applyLook(el, w.look);
    if (d.inst) S.insts.push(d.inst);
    if (zoomed[w.id]) dotsToBars(zoomed[w.id], true);  // the block built again: the days, as after a deck change
    delete AZ[w.id]; delete FW[String(w.id)];  // (its own data comes below)
    const z = zoomed[w.id]; if (!z && d.inst) zoomLink(w, el, head, d.inst);
    // a heatmap of its own height: the last height its grid asked for at its real width (the build's estimate is
    // for its default width; the chart reports its height only when it changes)
    if (w.type === 'heatmap' && w.height == null && it){ it.h = el._ddp.lastH || it.h; }
    const chev = head.querySelector('.dd-chev'), canFold = boot.collapsible && w.type !== 'text_label';
    if (chev) chev.style.display = canFold ? '' : 'none';
    if (canFold){ foldSetup(el, w, boot, it); if (el.classList.contains('dd-collapsed') && it) foldNow(el, it); }
    else el.classList.remove('dd-collapsed');
    const mode = spanMode(w);
    DDP.call('data', {id: w.id, deck: boot.deck}).then(function(data){
      if (!d.inst) return;
      const js = JSON.stringify(data || {});
      if (js === d.dataJs) return;  // the same days: nothing moves
      const old = d.dataJs ? JSON.parse(d.dataJs) : undefined;
      d.dataJs = js;
      feed(d.inst, data, mode, w, old, el);
    }).catch(function(){});
  }

  // The heatmap has no opening animation: at Anki's start (the block's intro) its grid is drawn empty with the
  // block (the skeleton too: it has no box of its own, the page Anki builds again draws it at once), its values
  // fading in with the other charts' intro (its data cross-fade). The years view takes its rows from the data (an
  // empty one is shorter): it fades in whole.
  function heatIntro(el, w, data, mount, instOf){
    mount(data, true);
    const body = el.querySelector('.dd-body'); body.style.opacity = '0';
    S.introQ.push(function(){
      body.style.opacity = '';
      if (body.animate && DD.anim && DD.anim.on) body.animate([{opacity: 0}, {opacity: 1}], {duration: 320 * (DD.speed ? DD.speed() : 1), easing: 'ease-out'});
    });
  }
  function chartWidget(el, w, boot, it){
    el.className = 'dd-card dd-fixed ddp-card'; el.dataset.type = w.type; el.dataset.wid = w.id;
    if (w.own_n != null) el.dataset.ownN = w.own_n;  // its own options, counted at an earlier hover (pinned.py)
    el.innerHTML = DD.headHtml(w.type) + '<div class="dd-body"></div>';
    applyLook(el, w.look);
    const head = el.querySelector('.dd-head');
    const title = w.type === 'heatmap' ? (boot.heatmap_title ? w.title : null) : w.title;
    if (title){ const ti = head.querySelector('.dd-title'); ti.textContent = title; ti.title = title; }  // (cut in a narrow card: its tooltip)
    else head.querySelector('.dd-title').style.display = 'none';
    if (!boot.collapsible || w.type === 'text_label'){ const ch = head.querySelector('.dd-chev'); if (ch) ch.style.display = 'none'; }
    else foldSetup(el, w, boot, it);
    chips(head, w);
    // a chart with its title emptied and no buttons has no header row
    if (!title && w.type !== 'heatmap') head.classList.add('ddp-headless');
    if (w.type === 'heatmap'){ const hq = head.querySelector('.dd-help'); if (hq) hq.remove(); }
    else if (DDP.helpCheck) DDP.helpCheck(head);
    let inst = null;
    const mount = function(data, animate){
      const mod = DD.charts[w.type];
      if (!mod){ el.querySelector('.dd-body').innerHTML = '<div class="dd-todo">not ported yet</div>'; return; }
      DD._mountEl = el;
      const opts = Object.assign({}, w.options || {});
      if (w.type === 'heatmap' && w.height == null) opts.own_height = true;
      if (w.type === 'heatmap') opts.keep_color = true;  // its color comes with its options (its own, or the pinned one)  // years: rows of its own height
      const ctx = {data: data || {}, options: opts, animate: animate && DD.anim.on && DD.anim.appear, head: head, type: w.type};  // Appearance Animations
      ctx.fetch = function(extra){ return DDP.call('data', {id: w.id, deck: boot.deck, at: (extra && extra.at) || null}); };  // a Time Machine's day
      if (w.type === 'heatmap'){ ctx.expanded = !!w.expanded; ctx.onExpand = function(on){ w.expanded = on; DDP.call('hm_expanded', {id: w.id, on: on}).catch(function(){}); }; }
      if (w.type === 'heatmap' && w.height == null) ctx.onNatural = function(nh){ const cur = el._ddp ? el._ddp.it : it, lk = el._ddpLook || w.look, p = lk && lk.glass ? (lk.pad || [6, 10, 6, 10]) : [0, 0, 0, 0]; const h1 = 22 + nh + p[0] + p[2] + (lk && lk.glass ? 2 : 0); if (el._ddp) el._ddp.lastH = h1; heightTo(el, cur, h1, w.id); };
      if (ctx.onNatural) el._ddpNat = ctx.onNatural;  // fullscreen's close: the height at the pinned width again
      try { inst = mod.mount(el.querySelector('.dd-body'), ctx); }
      finally { DD._mountEl = null; }
      if (S) S.insts.push(inst);
      ctx.animate = true;  // shown at once from the last picture, but its next data animates (the modules read ctx.animate then)
      if (DD.watchStat) DD.watchStat(head);
      zoomLink(w, el, head, inst);
      el._ddp = {sig: cardSig(w), inst: inst, it: it, w: w, ctx: ctx, dataJs: JSON.stringify(data || {})};
      if (DD.ownOptions) DD.ownOptions(head);  // (known from a hover before the main screen was built again)
    };
    // the page Anki rebuilt: the chart as it was, at once, then its new data glides in
    // (the new data waits for the old picture to be drawn once: a chart morphs from what it has drawn)
    let drawn = Promise.resolve();
    if (w.pre){
      // a page Anki has just built: the charts below the window are drawn right after its first paint (S.lazyQ)
      const pre = function(){ if (!inst) mount(w.pre, false); };
      if (S.lazyQ) S.lazyQ.push({el: el, run: pre}); else pre();
      drawn = new Promise(function(r){ requestAnimationFrame(function(){ requestAnimationFrame(function(){ setTimeout(r, 0); }); }); });
    }
    // the heatmap at Anki's start: its empty grid now, its values with the intro (heatIntro)
    const heatEmpty = w.type === 'heatmap' && !w.pre && S && S.introQ && (w.options || {}).mode !== 'years';
    if (heatEmpty){ el.classList.add('ddp-skel-show'); mount({data: {}}, true); }
    const before = w.pre ? JSON.stringify(w.pre) : null, mode = spanMode(w);
    DDP.call('data', {id: w.id, deck: boot.deck}).then(function(data){
      if (heatEmpty && inst){
        if (el._ddp) el._ddp.dataJs = JSON.stringify(data || {});
        const show = function(){ if (inst.update) inst.update(data); };
        if (S && S.introQ) S.introQ.push(show); else show();
        return;
      }
      if (!inst){
        if (DD.dev) DD.trace('ANIMTRACE mount ' + w.type + ' (no last picture: its intro animation)' + (hasData(data) ? '' : ' EMPTY'));
        if (w.type === 'heatmap' && S && S.introQ){ heatIntro(el, w, data, mount, function(){ return inst; }); return; }
        mount(data, true); return;
      }
      if (JSON.stringify(data) !== before) drawn.then(function(){ if (el._ddp) el._ddp.dataJs = JSON.stringify(data || {}); feed(inst, data, mode, w, w.pre); });
    }).catch(function(e){ DD.log('pinned ' + w.type + ': ' + (e && e.message || e)); });
  }
  // =====================================================================================================
  // Layout editing, always on:
  //  - a card's right / bottom edge resizes it (8 px edges, heights snap to the other cards' within 15 px,
  //    columns from the width);
  //  - a card dragged (from its header or its empty parts; texts and stat cards anywhere) goes elsewhere on its
  //    line (live reorder), on another line of its kind, on the empty part of a line (snapped to the columns),
  //    or in a new box between two boxes;
  //  - the space between two boxes can be dragged (2 px steps, double click = default);
  //  - a "+" near the end of a line or between two boxes adds a widget there (add_here.py).
  // What a drop changes is written in Python; the block is then built again in place.
  // =====================================================================================================
  const EDGE = 8, SNAP = 15, DRAG_DIST = 10, EDGE_BAND = 10, SECTION_BAND = 10;
  const NO_DRAG = '.dd-plot, button, input, select, .ddp-chip, .dd-pill, .dd-zreset, .dd-help, .dd-sc-more, .dd-hm-btn, .dd-pills *, .dd-zbar';

  function itemOf(el){
    if (!S) return null;
    for (const b of S.boxes) for (const it of b.items) if (it.el === el) return {it: it, box: b};
    return null;
  }
  function boxOfId(id){
    for (const b of S.boxes){
      if (b.items.some(function(it){ return it.wid === id; })) return b;
      if (b.fam === 'stat' && b.ws.some(function(w){ return w.id === id; })) return b;
    }
    return null;
  }
  function resizeDirs(it){
    const w = it.def;
    if (w.type === 'text_label') return 'r';
    if (w.type === 'heatmap' && !(w.look && w.look.glass)) return '';
    return it.folded ? 'r' : 'rb';  // a collapsed card keeps only its right edge
  }
  function borderAt(it, cx, cy){
    const r = it.el.getBoundingClientRect(), dirs = resizeDirs(it);
    const right = dirs.indexOf('r') >= 0 && cx >= r.right - EDGE && cx <= r.right;
    const bottom = dirs.indexOf('b') >= 0 && cy >= r.bottom - EDGE && cy <= r.bottom;
    return right && bottom ? 'rb' : (right ? 'r' : (bottom ? 'b' : null));
  }
  const CURSOR = {rb: 'nwse-resize', r: 'ew-resize', b: 'ns-resize'};

  // ---- markers ----
  let marks = null;
  function markEls(){
    if (marks && marks.root === S.root) return marks;
    const mk = function(cls){ const d = document.createElement('div'); d.className = cls; d.style.display = 'none'; S.root.appendChild(d); return d; };
    marks = {root: S.root, gap: mk('ddp-gapbar'), line: mk('ddp-linemark'), bar: mk('ddp-landbar'), spot: mk('ddp-spot'), plus: mk('ddp-plus'), gh: mk('ddp-gaphandle'), grip: mk('ddp-grip')};
    marks.grip.title = 'Drag to move this line';
    marks.grip.innerHTML = '<i></i><i></i><i></i><i></i><i></i><i></i>';
    marks.gap.innerHTML = '<span></span>';
    marks.plus.innerHTML = '<svg width="20" height="20" viewBox="0 0 20 20"><circle cx="10" cy="10" r="9.5"/><path d="M10 5.5v9M5.5 10h9"/></svg>';
    marks.gh.innerHTML = '<i></i><b></b><em></em>';
    return marks;
  }
  function place(el, r){ el.style.left = r.x + 'px'; el.style.top = r.y + 'px'; el.style.width = r.w + 'px'; el.style.height = r.h + 'px'; el.style.display = 'block'; }
  function hideMarks(keepPlus){ if (!marks) return; ['gap', 'line', 'bar', 'spot'].concat(keepPlus ? [] : ['plus']).forEach(function(k){ marks[k].style.display = 'none'; }); }

  // ---- the boxes as shown (root coords) ----
  function sections(){
    return S.boxes.map(function(b){ return {box: b, r: rectIn(b.el, S.root)}; }).filter(function(s){ return s.r.h > 0; });
  }
  // in a gap between two boxes, or near the top of the first / the bottom of the last
  function gapAt(secs, y){
    if (!secs.length) return null;
    const first = secs[0].r, last = secs[secs.length - 1].r;
    if (y <= first.y + EDGE_BAND) return [0, first.y >= 12 ? first.y / 2 : first.y - 4];
    if (y >= last.y + last.h - EDGE_BAND) return [secs.length, last.y + last.h + 4];
    for (let i = 0; i < secs.length - 1; i++){
      const a = secs[i].r, b = secs[i + 1].r, ab = a.y + a.h, gy = (ab + b.y) / 2;
      if (Math.abs(y - gy) <= SECTION_BAND + (b.y - ab) / 2) return [i + 1, gy];
    }
    return null;
  }
  function famOfId(id){ const w = S.boot.widgets.filter(function(x){ return x.id === id; })[0]; return w ? familyOf(w.type) : null; }

  // the target of a drag at (x, y) in root coords for the widget id
  function dropTarget(id, x, y){
    const fam = famOfId(id), own = boxOfId(id), secs = sections();
    const hit = gapAt(secs, y);
    if (hit){
      const keys = secs.map(function(s){ return s.box.key; }), oi = own ? keys.indexOf(own.key) : -1;
      const alone = own && (own.fam === 'stat' ? own.ws.length : own.items.length) <= 1;
      if (!(alone && oi >= 0 && (hit[0] === oi || hit[0] === oi + 1))){
        const left = Math.min.apply(null, secs.map(function(s){ return s.r.x; })), right = Math.max.apply(null, secs.map(function(s){ return s.r.x + s.r.w; }));
        return {kind: 'newbox', keys: keys, index: hit[0], bar: {x: left, y: hit[1] - 2, w: right - left, h: 4}};
      }
    }
    // the box under the mouse (else the nearest one): only a box of the same kind takes the widget
    let sec = secs.filter(function(s){ return y >= s.r.y && y <= s.r.y + s.r.h; })[0];
    if (!sec) sec = secs.slice().sort(function(a, b){ return Math.min(Math.abs(y - a.r.y), Math.abs(y - a.r.y - a.r.h)) - Math.min(Math.abs(y - b.r.y), Math.abs(y - b.r.y - b.r.h)); })[0];
    if (!sec || sec.box.fam !== fam) return null;
    return sec.box.fam === 'stat' ? statTarget(id, sec, x, y) : chartTarget(id, sec, x, y);
  }

  // a line of graphs / texts
  function chartTarget(id, sec, x, y){
    const b = sec.box, others = b.items.filter(function(it){ return it.wid !== id; });
    const srcEl = S.root.querySelector('[data-wid="' + id + '"]'); if (!srcEl) return null;
    const src = itemOf(srcEl); const srcW = src ? src.it.pw : srcEl.offsetWidth, srcH = src ? src.it.ph : srcEl.offsetHeight;
    const lx = x - sec.r.x, W = b.el.clientWidth, cw = b.el._cw || COL;
    // the empty part of the line (left / right of its widgets, with room): free_spot
    const side = !others.length ? 'end' : (lx < Math.min.apply(null, others.map(function(o){ return o.x; })) - 8 ? 'start'
      : (lx > Math.max.apply(null, others.map(function(o){ return o.x + o.pw; })) + 8 ? 'end' : null));
    const total = others.reduce(function(a, o){ return a + o.pw; }, 0) + srcW + SP * others.length;
    if (side && total <= W){
      const order = others.map(function(o){ return [o.pw, o.off | 0]; });
      const idx = side === 'start' ? 0 : order.length;
      order.splice(idx, 0, [srcW, 0]);
      const xStart = Math.max(0, Math.floor((W - total) / 2)), step = cw + SP;
      let best = null;
      const ks = []; for (let k = -12; k <= 12; k++) ks.push(k); ks.sort(function(a, c){ return Math.abs(a) - Math.abs(c); });
      ks.forEach(function(k){
        const widths = order.map(function(o){ return o[0]; }), offs = order.map(function(o){ return o[1]; }); offs[idx] = k;
        const base = []; let bx = xStart; widths.forEach(function(w){ base.push(bx); bx += w + SP; });
        const xs = project(base, base.map(function(v, i){ return v + offs[i] * step; }), widths, 0, SP, W, offs.map(function(o){ return 1 + 1000 * Math.abs(o); }));
        const d = Math.abs(xs[idx] + srcW / 2 - lx);
        if (!best || d < best[0] - 0.5) best = [d, k, xs[idx]];
      });
      const top = b.el._rows && b.el._rows[0] ? b.el._rows[0].y : 0;
      return {kind: 'place', box: b.num, row: 0, side: side, k: best[1], spot: {x: sec.r.x + best[2], y: sec.r.y + top, w: srcW, h: Math.max(20, srcH)}};
    }
    // in front of which widget it lands (rows, then x)
    let idx = others.length;
    for (let i = 0; i < others.length; i++){
      const o = others[i], oy = sec.r.y + o.y;
      if (y < oy || (y <= oy + o.ph && lx < o.x + o.pw / 2)){ idx = i; break; }
    }
    const anchor = idx < others.length ? others[idx].wid : null;
    if (boxOfId(id) === b) return {kind: 'reorder', box: b.num, anchor: anchor, live: true};
    const barX = anchor ? others[idx].x - 3 : (others.length ? others[others.length - 1].x + others[others.length - 1].pw + 3 : W / 2);
    return {kind: 'move', box: b.num, row: 0, anchor: anchor, line: sec.r, barX: sec.r.x + barX};
  }

  // a line of stat cards
  function statTarget(id, sec, x, y){
    const b = sec.box, cards = Array.from(b.el.querySelectorAll('.dd-sc[data-key]')).filter(function(c){ return c.dataset.key !== id; });
    let idx = cards.length;
    for (let i = 0; i < cards.length; i++){ const r = rectIn(cards[i], S.root); if (y < r.y || (y <= r.y + r.h && x < r.x + r.w / 2)){ idx = i; break; } }
    const anchor = idx < cards.length ? cards[idx].dataset.key : null;
    if (boxOfId(id) === b) return {kind: 'reorder', box: b.num, anchor: anchor, live: true, stat: true};
    const last = cards.length ? rectIn(cards[cards.length - 1], S.root) : null;
    const barX = anchor ? rectIn(cards[idx], S.root).x - 3 : (last ? last.x + last.w + 3 : sec.r.x + sec.r.w / 2);
    return {kind: 'move', box: b.num, row: 0, anchor: anchor, line: sec.r, barX: barX};
  }

  function showTarget(t){
    const M = markEls(); hideMarks(true);
    if (!t) return;
    if (t.kind === 'newbox'){ place(M.gap, t.bar); M.gap.firstChild.textContent = 'New line'; }
    else if (t.kind === 'place') place(M.spot, t.spot);
    else if (t.kind === 'move'){ place(M.line, t.line); place(M.bar, {x: t.barX - 1, y: t.line.y + 4, w: 3, h: t.line.h - 8}); }
  }
  // same line: the widgets make room while dragging (live reorder), the dragged one shown at its new place
  function liveReorder(id, t){
    const b = boxOfId(id); if (!b) return;
    if (t.stat){
      const card = b.el.querySelector('.dd-sc[data-key="' + id + '"]'), anchor = t.anchor ? b.el.querySelector('.dd-sc[data-key="' + t.anchor + '"]') : null;
      if (card && anchor !== card.nextSibling) card.parentNode.insertBefore(card, anchor);
      return;
    }
    const i = b.items.findIndex(function(it){ return it.wid === id; }); if (i < 0) return;
    const it = b.items.splice(i, 1)[0];
    const j = t.anchor ? b.items.findIndex(function(o){ return o.wid === t.anchor; }) : b.items.length;
    b.items.splice(j < 0 ? b.items.length : j, 0, it);
    if (i !== (j < 0 ? b.items.length - 1 : j)) DDP.relayout(true);
  }

  // ---- the "+" ----
  function plusTarget(x, y){
    const lines = [];
    S.boxes.forEach(function(b){
      const r = rectIn(b.el, S.root); if (r.h <= 0) return;
      if (b.fam === 'stat'){
        const rows = Array.from(b.el.querySelectorAll('.dd-sc-line'));
        if (rows.length){
          rows.forEach(function(rl){
            const rr = rectIn(rl, S.root); if (rr.h <= 0) return;
            let right = rr.x;
            rl.querySelectorAll('.dd-sc').forEach(function(c){ const cr = rectIn(c, S.root); right = Math.max(right, cr.x + cr.w); });
            if (right > rr.x) lines.push({b: b, top: rr.y, bottom: rr.y + rr.h, right: right, lastId: null});
          });
          return;
        }
        let right = r.x;
        b.el.querySelectorAll('.dd-sc').forEach(function(c){ const cr = rectIn(c, S.root); right = Math.max(right, cr.x + cr.w); });
        lines.push({b: b, top: r.y, bottom: r.y + r.h, right: right, lastId: null});
        return;
      }
      const rows = b.el._rows;
      if (rows && rows.length){
        rows.forEach(function(rw){
          const last = rw.items && rw.items.length ? rw.items[rw.items.length - 1] : null;
          lines.push({b: b, top: r.y + rw.y, bottom: r.y + rw.y + rw.h, right: r.x + rw.x1, lastId: last ? last.wid : null, multi: rows.length > 1});
        });
        return;
      }
      let right = r.x;
      b.items.forEach(function(it){ right = Math.max(right, r.x + it.x + it.pw); });
      lines.push({b: b, top: r.y, bottom: r.y + r.h, right: right, lastId: null});
    });
    if (!lines.length) return null;
    const W = S.root.clientWidth, near = function(right){ return right - 70 <= x && x <= right + 34; };
    const px = function(right){ return Math.min(right + 6, W - 22); };
    for (const l of lines){
      if (l.top <= y && y <= l.bottom && near(l.right)){
        const t = (l.multi && l.lastId) ? {kind: 'after', id: l.lastId, family: l.b.fam, box: l.b.num, row: 0}
          : {kind: 'end', family: l.b.fam, box: l.b.num, row: 0};
        return {t: t, x: px(l.right), y: (l.top + l.bottom) / 2 - 10};
      }
    }
    const ordered = lines.slice().sort(function(a, b){ return a.top - b.top; });
    for (let i = 0; i < ordered.length - 1; i++){
      const a = ordered[i], b = ordered[i + 1];
      if (a.b === b.b) continue;  // same box: the row-end "+" already inserts right after it
      if (!(a.bottom - 5 <= y && y <= b.top + 5)) continue;
      const right = Math.max(a.right, b.right); if (!near(right)) continue;
      const keys = S.boxes.map(function(bx){ return bx.key; });
      return {t: {kind: 'newbox', keys: keys, index: keys.indexOf(b.b.key), family: b.b.fam}, x: px(right), y: (a.bottom + b.top) / 2 - 10};
    }
    const last = ordered[ordered.length - 1];
    if (last.bottom < y && y <= last.bottom + 24 && near(last.right)) return {t: {kind: 'newline', family: last.b.fam, box: last.b.num, row: 1}, x: px(last.right), y: last.bottom + 6 - 10};
    return null;
  }

  // ---- the spaces between boxes (gap_handle) ----
  // the widgets of a box as they stand (the box itself spans the whole page: centered stat cards or a short row
  // leave most of it empty)
  function contentOf(s){
    let c = null;
    const els = s.box.fam === 'stat' ? Array.from(s.box.el.querySelectorAll('.dd-sc')) : s.box.items.map(function(it){ return it.el; });
    els.forEach(function(el){ const r = rectIn(el, S.root); c = !c ? r : {x: Math.min(c.x, r.x), y: Math.min(c.y, r.y), w: Math.max(c.x + c.w, r.x + r.w) - Math.min(c.x, r.x), h: Math.max(c.y + c.h, r.y + r.h) - Math.min(c.y, r.y)}; });
    return c || s.r;
  }
  function gapHandleAt(x, y){
    const secs = sections();
    for (let i = 0; i < secs.length - 1; i++){
      const a = secs[i].r, b = secs[i + 1].r, top = a.y + a.h, h = b.y - top;
      const gy = h >= 10 ? top : top + h / 2 - 5, gh = Math.max(10, h);
      if (y < gy || y > gy + gh) continue;
      // only across the width the widgets of the two boxes take, never far from any widget
      const ca = contentOf(secs[i]), cb = contentOf(secs[i + 1]);
      const x0 = Math.min(ca.x, cb.x), x1 = Math.max(ca.x + ca.w, cb.x + cb.w);
      if (x < x0 - 8 || x > x1 + 8) continue;
      return {key: secs[i].box.key, el: secs[i].box.el, r: {x: x0, y: gy, w: x1 - x0, h: gh}};
    }
    return null;
  }

  // ---- fullscreen: the card itself over the whole view (zoom, toggles and hover go with
  // it), the theme's background, an "x" at the top right (Esc closes); its place is kept meanwhile ----
  DDP.fullscreen = function(wid){
    if (!S) return;
    const card = S.root.querySelector('.ddp-card[data-wid="' + wid + '"]'); if (!card || card.classList.contains('ddp-fs')) return;
    const f = itemOf(card), ph = document.createElement('div');
    ph.style.cssText = card.style.cssText; ph.className = 'ddp-fs-slot';
    card.parentNode.insertBefore(ph, card);
    const win = document.createElement('div'); win.className = 'ddp-fs-win';
    const x = document.createElement('button'); x.className = 'ddp-fs-x'; x.title = 'Exit fullscreen (Esc)';
    x.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M18 6 6 18M6 6l12 12"/></svg>';
    win.appendChild(x); S.root.appendChild(win);  // inside the block: its theme variables and card styles apply
    const saved = card.style.cssText; card.classList.add('ddp-fs');
    card.style.cssText = 'position:relative;left:auto;top:auto;width:100%;' + (f && f.it.def.type === 'heatmap' ? 'height:' + f.it.ph + 'px;margin:auto 0' : 'height:100%;flex:1');
    win.appendChild(card);
    if (f) f.it.fs = true;
    // a heatmap: the calendar the screen's width, centered, only as tall as its grid at that width
    let ro = null;
    const isHm = f && f.it.def.type === 'heatmap';
    if (isHm){
      const fit = function(){
        const body = card.querySelector('.dd-body'), inst = card._ddp && card._ddp.inst;
        if (!body || !inst || !inst.natural) return;
        const nh = inst.natural(Math.max(150, body.clientWidth));
        const room = Math.max(60, win.clientHeight - 12 - 24 - 40);
        const h = Math.min(room, card.offsetHeight - body.clientHeight + nh);
        if (nh > 0 && card.style.height !== h + 'px') card.style.height = h + 'px';
      };
      card._fsFit = fit;
      fit(); ro = new ResizeObserver(fit); ro.observe(win);
    }
    // a phone held upright: the whole fullscreen view turned to landscape (DD.rot), the charts best seen wide by
    // default; its button beside the "x" turns it back, the choice kept for the chart type
    let turn = null, unwatch = null;
    const type = f ? f.it.def.type : '';
    if (DD.isTouch() && DD.rot){
      turn = document.createElement('button'); turn.className = 'ddp-fs-x ddp-fs-turn'; turn.title = 'Rotate'; turn.innerHTML = DD.rot.icon;
      win.insertBefore(turn, x);
      const set = function(want){
        if (want && !DD.rot.active()){ if (DD.rot.on(win, function(){ turn.classList.remove('on'); })) turn.classList.add('on'); }
        else if (!want && DD.rot.active()){ DD.rot.off(); turn.classList.remove('on'); }
        if (DD.frame) DD.frame.kick();
      };
      turn.onclick = function(){ const want = !DD.rot.active(); set(want); DD.rot.remember(type, want); };
      if (DD.rot.upright() && DD.rot.wanted(type)) set(true);
      // held upright again after the phone was turned to landscape: turned back
      unwatch = DD.rot.upagain(function(){ if (!DD.rot.active() && DD.rot.wanted(type)) set(true); });
    }
    function close(){
      if (unwatch){ unwatch(); unwatch = null; }
      if (turn && DD.rot.active()) DD.rot.off();
      if (ro){ ro.disconnect(); ro = null; } card._fsFit = null;
      document.removeEventListener('keydown', key, true);
      card.classList.remove('ddp-fs'); card.style.cssText = saved;
      ph.parentNode.insertBefore(card, ph); ph.remove(); win.remove();
      if (f) f.it.fs = false;
      DDP.relayout(); if (DD.frame) DD.frame.kick();
      // a mode switched while fullscreen: the pinned card takes the height of the new mode
      // the heights asked for meanwhile were for the screen's width (a hover redraws and measures again): the card takes
      // the height of its grid at its own width, as the heatmap would ask for it there
      if (f) f.it.fsH = null;
      const inst = card._ddp && card._ddp.inst, body = card.querySelector('.dd-body');
      if (isHm && card._ddpNat && inst && inst.natural && body && body.clientWidth > 0){
        const nh = inst.natural(body.clientWidth);
        if (nh > 0) card._ddpNat(nh);
      }
    }
    function key(ev){ if (ev.key === 'Escape'){ ev.stopPropagation(); close(); } }
    document.addEventListener('keydown', key, true); x.onclick = close;
    if (DD.frame) DD.frame.kick();
  };

  // ---- the grip of a whole box (section_handle): near its left edge when there are several boxes ----
  function gripAt(x, y){
    const secs = sections(); if (secs.length < 2) return null;
    for (const s of secs){
      let c = null;
      const els = s.box.fam === 'stat' ? Array.from(s.box.el.querySelectorAll('.dd-sc')) : s.box.items.map(function(it){ return it.el; });
      els.forEach(function(el){ const r = rectIn(el, S.root); c = !c ? r : {x: Math.min(c.x, r.x), y: Math.min(c.y, r.y), w: Math.max(c.x + c.w, r.x + r.w) - Math.min(c.x, r.x), h: Math.max(c.y + c.h, r.y + r.h) - Math.min(c.y, r.y)}; });
      c = c || s.r;
      if (y >= c.y - 4 && y <= c.y + c.h && x >= c.x - 16 - 14 && x <= c.x + 40) return {key: s.box.key, box: s.box, x: Math.max(0, c.x - 16 - 6), y: c.y + 2};
    }
    return null;
  }
  // the room above the first box / below the last one opens while a drag is near there (overlay_margins.DRAG_ROOM)
  function dragRoom(top, bottom){
    if (!S) return;
    const m = S.boot.margins || [0, 20, 20];
    S.root.style.paddingTop = (m[0] + (top ? 26 : 0)) + 'px';
    S.root.style.paddingBottom = (m[2] + (bottom ? 26 : 0)) + 'px';
  }

  DDP.setupEdit = function(root){
    let op = null;  // {type: 'resize'|'drag'|'gap', ...}
    const toRoot = function(ev){ const r = root.getBoundingClientRect(); return {x: ev.clientX - r.left, y: ev.clientY - r.top}; };
    root.addEventListener('mousemove', function(ev){
      if (op || ev.buttons) return;
      if (DD.isTouch && DD.isTouch()){ if (marks){ marks.grip.style.display = 'none'; marks.gh.style.display = 'none'; marks.plus.style.display = 'none'; } return; }
      const p = toRoot(ev), M = markEls();
      // resize edges
      const card = ev.target.closest && ev.target.closest('.ddp-card[data-wid]');
      const f = card ? itemOf(card) : null, mode = f ? borderAt(f.it, ev.clientX, ev.clientY) : null;
      if (card) card.style.cursor = mode ? CURSOR[mode] : '';
      // the space between two boxes
      const g = !card ? gapHandleAt(p.x, p.y) : null;
      if (g){ place(M.gh, g.r); M.gh.dataset.key = g.key; M.gh.querySelector('b').style.left = Math.max(14, Math.min(g.r.w - 14, p.x - g.r.x)) + 'px'; M.gh.classList.remove('on'); }
      else M.gh.style.display = 'none';
      // the grip of a box
      const gp = gripAt(p.x, p.y);
      if (gp){ place(M.grip, {x: gp.x, y: gp.y, w: 16, h: 26}); M.grip._key = gp.key; } else M.grip.style.display = 'none';
      // the "+"
      const pt = !mode ? plusTarget(p.x, p.y) : null;
      if (pt){ place(M.plus, {x: pt.x, y: pt.y, w: 20, h: 20}); M.plus._t = pt.t; } else M.plus.style.display = 'none';
    });
    root.addEventListener('mouseleave', function(ev){
      if (op || !marks) return;
      marks.plus.style.display = 'none'; marks.gh.style.display = 'none';
      // the line's grip too, unless the mouse went onto it (it sits left of the boxes)
      const to = ev.relatedTarget;
      if (!(to && marks.grip.contains(to))) marks.grip.style.display = 'none';
    });
    markEls().grip.addEventListener('mouseleave', function(ev){
      if (op) return;
      const to = ev.relatedTarget;
      if (!(to && root.contains(to))) markEls().grip.style.display = 'none';
    });
    root.addEventListener('mousedown', function(ev){
      if (ev.button !== 0 || !S) return;
      const M = markEls(), lift = !!ev.ddTouch;  // a card lifted by a touch hold: dragged from anywhere on it
      if (!lift && ev.target.closest('.ddp-plus')){
        ev.preventDefault(); ev.stopPropagation();
        const t = M.plus._t; if (t) DDP.call('add_here', {target: t}).catch(function(){});
        return;
      }
      if (!lift && ev.target.closest('.ddp-grip')){
        ev.preventDefault(); ev.stopPropagation();
        const key = M.grip._key, b = S.boxes.filter(function(x){ return x.key === key; })[0]; if (!b) return;
        op = {type: 'pendbox', key: key, b: b, x0: ev.clientX, y0: ev.clientY};
        return;
      }
      if (!lift && ev.target.closest('.ddp-gaphandle')){
        ev.preventDefault(); ev.stopPropagation();
        const key = M.gh.dataset.key, b = S.boxes.filter(function(x){ return x.key === key; })[0]; if (!b) return;
        op = {type: 'gap', key: key, b: b, y0: ev.clientY, s0: parseFloat(b.el.style.marginBottom) || 0};
        M.gh.classList.add('on');
        return;
      }
      const card = ev.target.closest('.ddp-card[data-wid]');
      const f = card ? itemOf(card) : null;
      if (f){
        const mode = lift ? ev.ddEdge : borderAt(f.it, ev.clientX, ev.clientY);
        if (mode){
          ev.preventDefault(); ev.stopPropagation();
          op = {type: 'resize', f: f, mode: mode, x0: ev.clientX, y0: ev.clientY, w0: f.it.pw, h0: f.it.ph, minH: Math.max(50, f.it.def.type === 'heatmap' ? 60 : 200)};
          document.body.style.cursor = CURSOR[mode];
          return;
        }
      }
      const src = ev.target.closest('.ddp-card[data-wid], .dd-sc[data-key]');
      if (!src) return;
      if (!lift && src.matches('.ddp-card:not(.ddp-text)') && ev.target.closest(NO_DRAG)) return;
      if (!lift && ev.target.closest('.dd-sc-more')) return;
      op = {type: 'pending', el: src, id: src.dataset.wid || src.dataset.key, x0: ev.clientX, y0: ev.clientY};
    }, true);
    window.addEventListener('mousemove', function(ev){
      if (!op || !S) return;
      if (op.type === 'gap'){
        const px = Math.max(0, Math.min(200, Math.round((op.s0 + ev.clientY - op.y0) / 2) * 2));
        op.px = px; op.b.el.style.marginBottom = px + 'px';
        const M = markEls(); M.gh.querySelector('em').textContent = px + ' px';
        const r = rectIn(op.b.el, S.root); M.gh.style.top = (r.y + r.h) + 'px'; M.gh.style.height = Math.max(10, px) + 'px';
        return;
      }
      if (op.type === 'resize'){
        const it = op.f.it, dx = ev.clientX - op.x0, dy = ev.clientY - op.y0;
        if (op.mode.indexOf('r') >= 0) it.w = Math.min(op.f.box.el.clientWidth, Math.max(100, op.w0 + dx));
        if (op.mode.indexOf('b') >= 0){
          let h = Math.max(op.minH, op.h0 + dy), best = SNAP;
          op.f.box.items.forEach(function(o){ if (o !== it && Math.abs(o.ph - h) < best){ best = Math.abs(o.ph - h); h = o.ph; } });
          it.h = h;
        }
        if (it.def.type === 'text_label'){ it.el.style.whiteSpace = 'normal'; it.fixed = true; }
        op.moved = true;
        DDP.relayout();
        return;
      }
      if (op.type === 'pendbox'){
        if (Math.abs(ev.clientX - op.x0) + Math.abs(ev.clientY - op.y0) < DRAG_DIST) return;
        // the box's picture (at most 420 px wide, 75 % opaque) follows the mouse, held at (10, 10)
        const r = op.b.el.getBoundingClientRect(), k = Math.min(1, 420 / Math.max(1, r.width)), ghost = op.b.el.cloneNode(true);
        const srcC = op.b.el.querySelectorAll('canvas'), dstC = ghost.querySelectorAll('canvas');
        dstC.forEach(function(c, i){ const s = srcC[i]; if (!s) return; c.width = s.width; c.height = s.height; try { c.getContext('2d').drawImage(s, 0, 0); } catch (e) {} });
        ghost.className += ' ddp-ghost ddp-boxghost';
        ghost.style.cssText = 'position:fixed;left:0;top:0;width:' + r.width + 'px;height:' + r.height + 'px;margin:0;pointer-events:none;z-index:9999;opacity:.75;transform-origin:0 0;transform:scale(' + k + ')';
        S.root.appendChild(ghost);
        markEls().grip.style.display = 'none';
        op = {type: 'boxdrag', key: op.key, ghost: ghost, k: k, target: null};
        document.body.classList.add('dd-dragging');
      }
      if (op.type === 'boxdrag'){
        op.ghost.style.left = (ev.clientX - 10) + 'px'; op.ghost.style.top = (ev.clientY - 10) + 'px';
        const p = toRoot(ev), secs = sections(), keys = secs.map(function(s){ return s.box.key; }), hit = gapAt(secs, p.y);
        const oi = keys.indexOf(op.key);
        dragRoom(hit && hit[0] === 0, hit && hit[0] === secs.length);
        if (hit && hit[0] !== oi && hit[0] !== oi + 1){
          const left = Math.min.apply(null, secs.map(function(s){ return s.r.x; })), right = Math.max.apply(null, secs.map(function(s){ return s.r.x + s.r.w; }));
          op.target = {kind: 'movebox', keys: keys, index: hit[0]};
          showTarget({kind: 'newbox', bar: {x: left, y: hit[1] - 2, w: right - left, h: 4}});
        } else { op.target = null; hideMarks(true); }
        return;
      }
      if (op.type === 'pending'){
        if (Math.abs(ev.clientX - op.x0) + Math.abs(ev.clientY - op.y0) < DRAG_DIST) return;
        // the drag starts: a picture of the card follows the mouse, the card itself stays as its slot
        const r = op.el.getBoundingClientRect(), ghost = op.el.cloneNode(true);
        const srcC = op.el.querySelectorAll('canvas'), dstC = ghost.querySelectorAll('canvas');
        dstC.forEach(function(c, i){ const s = srcC[i]; if (!s) return; c.width = s.width; c.height = s.height; try { c.getContext('2d').drawImage(s, 0, 0); } catch (e) {} });
        ghost.classList.add('ddp-ghost');
        ghost.style.cssText += ';position:fixed;left:' + r.left + 'px;top:' + r.top + 'px;width:' + r.width + 'px;height:' + r.height + 'px;margin:0;pointer-events:none;z-index:9999';
        Array.from(getComputedStyle(op.el)).forEach(function(){});
        S.root.appendChild(ghost);
        op = {type: 'drag', el: op.el, id: op.id, ghost: ghost, hx: op.x0 - r.left, hy: op.y0 - r.top, target: null};
        op.el.classList.add('ddp-dragsrc');
        const f = itemOf(op.el); if (f) f.it.dragSrc = true;
        document.body.classList.add('dd-dragging');
      }
      if (op.type === 'drag'){
        op.ghost.style.left = (ev.clientX - op.hx) + 'px'; op.ghost.style.top = (ev.clientY - op.hy) + 'px';
        const p = toRoot(ev), t = dropTarget(op.id, p.x, p.y);
        op.target = t;
        dragRoom(t && t.kind === 'newbox' && t.index === 0, t && t.kind === 'newbox' && t.index === t.keys.length);
        if (t && t.live){ hideMarks(true); liveReorder(op.id, t); }
        else showTarget(t);
      }
    });
    window.addEventListener('mouseup', function(){
      if (!op || !S){ op = null; return; }
      const o = op; op = null;
      document.body.style.cursor = '';
      if (o.type === 'gap'){
        markEls().gh.classList.remove('on');
        if (o.px != null && o.px !== o.s0) DDP.call('gap', {key: o.key, px: o.px}).catch(function(){});
        return;
      }
      if (o.type === 'resize'){
        if (!o.moved) return;
        const it = o.f.it;
        DDP.call('resize', {id: it.wid, w: Math.round(o.mode.indexOf('r') >= 0 ? it.pw : it.w), h: o.mode.indexOf('b') >= 0 ? Math.round(it.ph) : null}).catch(function(){});
        return;
      }
      if (o.type === 'boxdrag'){
        o.ghost.remove(); document.body.classList.remove('dd-dragging'); hideMarks(); dragRoom(false, false);
        if (o.target) DDP.call('drop', {cross: Object.assign({id: o.key}, o.target)}).catch(function(){});
        return;
      }
      if (o.type !== 'drag') return;
      dragRoom(false, false);
      o.ghost.remove(); o.el.classList.remove('ddp-dragsrc'); document.body.classList.remove('dd-dragging');
      const f = itemOf(o.el); if (f) f.it.dragSrc = false;
      hideMarks();
      const t = o.target; if (!t) { DDP.relayout(); return; }
      const cross = Object.assign({id: o.id}, t); delete cross.bar; delete cross.spot; delete cross.line; delete cross.barX; delete cross.live; delete cross.stat;
      DDP.call('drop', {cross: cross}).catch(function(){});
    });
    root.addEventListener('dblclick', function(ev){
      if (!ev.target.closest('.ddp-gaphandle')) return;
      const key = markEls().gh.dataset.key; if (key) DDP.call('gap', {key: key, px: null}).catch(function(){});
    });
  };
  // =====================================================================================================
  // Guided tour (web_ui/tour.py; steps, texts and demo scenes of common/guided_tour.py): the screen dimmed but
  // for what the step talks about, a dark card with the text, dots for the steps, Back / Skip / Next. A demo
  // scene builds the block again: the light waits until it has settled, then glides to it. The steps show the
  // thing live: the scenes one after the other (layouts, themes, texts), the "+" at the end
  // of a line, pictures of the real right-click menu and period list with a pointer, a chart zooming, the grip.
  // =====================================================================================================
  // The overlay, pointer, picture, dots, keys and tween are DD.tourKit's (dd-core.js), shared with the Deep Dive's tour.
  const TOUR_SCENE_MS = 2600, TOUR_PAD = 6, K = DD.tourKit;
  let T = null;
  function tourVis(el){ return K.rect(el, 20); }
  const tourUnite = K.unite;
  function tourCharts(){ return S ? Array.from(S.root.querySelectorAll('.ddp-card.dd-card[data-wid]')).filter(function(el){ return el.dataset.type !== 'heatmap'; }) : []; }
  // the chart the span step changes: one over time first (its look changes with the period)
  function tourSpanCard(){
    const cs = tourCharts().filter(function(el){ return el.querySelector('.ddp-chip[title="Time Span"]'); });
    for (const t of ['activity', 'retention', 'added']){ const c = cs.filter(function(el){ return el.dataset.type === t; })[0]; if (c) return c; }
    return cs[0] || null;
  }
  // a touch screen (Kioku): the steps' touch texts, no drawn mouse pointer, only the gestures a finger has
  function tourTouch(){ return !!(DD.isTouch && DD.isTouch()); }
  function tourRect(kind){
    if (!S) return null;
    if (kind === 'all') return tourUnite(Array.from(S.root.querySelectorAll('.ddp-card[data-wid], .dd-sc')).map(tourVis));
    if (kind === 'text') return tourVis(S.root.querySelector('.ddp-text[data-wid]'));
    if (kind === 'menu') return tourVis(tourMenuCard());
    if (kind === 'span') return tourVis(tourSpanCard());
    if (kind === 'zoom'){ const z = tourZoomCard(); return z ? tourVis(z.el) : null; }
    if (kind === 'add'){
      // the widget just added while it shows, the "+" while it is clicked, else the widget
      // whose menu opens
      const f = T && T.addFocus;
      if (f === 'plus'){ const p = tourPlusSpot('stat'); if (p) return p.r; }
      else if (f === 'touchadd'){ const b = tourVis(S.root.querySelector('.ddp-touch-add')); if (b) return b; }
      else if (f){ const e = S.root.querySelector('[data-wid="' + f + '"], .dd-sc[data-key="' + f + '"]'); if (e) return tourVis(e); }
      const a = tourAddAnchor('chart'); if (a) return tourVis(a);
      const p = tourPlusSpot(); return p ? tourUnite([tourVis(p.line), p.r]) : null;
    }
    return null;
  }
  // the chart the zoom step zooms: Activity first (a bar a day), else the first chart that zooms
  function tourZoomCard(){
    const ids = Object.keys(zoomed).filter(function(id){ const e = zoomed[id]; return e.z && e.z.count && e.z.count() > 6 && S.root.querySelector('[data-wid="' + id + '"]'); });
    if (!ids.length) return null;
    ids.sort(function(a, b){ return (zoomed[a].w.type === 'activity' ? 0 : 1) - (zoomed[b].w.type === 'activity' ? 0 : 1); });
    return {id: ids[0], e: zoomed[ids[0]], el: S.root.querySelector('[data-wid="' + ids[0] + '"]')};
  }
  // the "+" at the end of the first line of charts (else of any line), where the mouse would show it
  function tourPlusSpot(fam){
    const b = S.boxes.filter(function(x){ return x.fam === (fam || 'chart'); })[0] || (fam ? null : S.boxes[0]); if (!b) return null;
    const r = rectIn(b.el, S.root);
    let right = r.x;
    if (b.fam === 'stat') b.el.querySelectorAll('.dd-sc').forEach(function(c){ const cr = rectIn(c, S.root); right = Math.max(right, cr.x + cr.w); });
    else b.items.forEach(function(it){ right = Math.max(right, r.x + it.x + it.pw); });
    const pt = plusTarget(right, r.y + Math.min(r.h, 120) / 2); if (!pt) return null;
    const rr = S.root.getBoundingClientRect(), x = rr.left + pt.x, y = rr.top + pt.y;
    return {line: b.el, pt: pt, r: {left: x - 6, top: y - 6, right: x + 26, bottom: y + 26, width: 32, height: 32}};
  }
  DDP.tourClose = function(){ tourClose(); };  // tour.stop: its screen left (the Deep Dive window over it)
  DDP.tour = function(p){
    if (T || !S || !p || !p.steps) return;
    if (DD.dev) DD.trace('TOUR start win=' + window.innerWidth + 'x' + window.innerHeight + ' dpr=' + (window.devicePixelRatio || 1) + ' steps=' + p.steps.map(function(x){ return x.action || '-'; }).join(','));
    const L = p.labels || {}, el = K.build(L);
    el.title.textContent = L.title || 'Quick tour';
    el.ov.style.setProperty('--ddp-tour-acc', (DD.theme && DD.theme.chart && DD.theme.chart.accent) || '#58a6ff');
    // steps whose thing is not on screen are left out (a demo step brings its own scene)
    const steps = p.steps.filter(function(st){ return st.scene || tourRect(st.target); });
    if (!steps.length){ el.ov.remove(); DDP.call('tour_end').catch(function(){}); return; }
    T = {el: el, steps: steps, i: -1, scene: null, busy: false, frozen: false, timers: [], extra: null, L: L, gen: 0};
    el.next.addEventListener('click', function(){ tourGo(T.i + 1); });
    el.back.addEventListener('click', function(){ tourGo(T.i - 1); });
    el.skip.addEventListener('click', tourClose);
    el.ov.addEventListener('wheel', function(ev){ window.scrollBy(0, ev.deltaY); ev.preventDefault(); }, {passive: false});
    T.key = K.keys(tourClose, function(d){ if (T) tourGo(T.i + d); });
    document.addEventListener('keydown', T.key, true);
    // the page never stays scrolled sideways under the tour (a demo widget wider for a moment moved it)
    (function follow(){ if (!T) return; if (window.scrollX) window.scrollTo(0, window.scrollY);
      if (T.lastY != null && Math.abs(window.scrollY - T.lastY) > 0.5 && !T.scrolling) tlog('page scrolled by itself ' + Math.round(T.lastY) + ' -> ' + Math.round(window.scrollY));
      T.lastY = window.scrollY; T.scrolling = false; if (!T.frozen) tourPlace(false, false); T.raf = requestAnimationFrame(follow); })();
    // the page's scrollbar keeps its room the whole tour: an example taller or shorter than the page made it come and
    // go, and everything centered moved sideways by half its width
    // dev: anything put in the page near its top left corner during the tour (something showing there for a moment)
    if (DD.dev && window.MutationObserver){
      T.watch = new MutationObserver(function(list){
        const els = [];
        list.forEach(function(m){ m.addedNodes.forEach(function(n){ if (n.nodeType === 1) els.push(n); }); });
        if (!els.length) return;
        requestAnimationFrame(function(){ els.forEach(function(n){
          if (!n.isConnected) return;
          const q = n.getBoundingClientRect();
          if (q.width > 0 && q.height > 0 && q.left < 60 && q.top < 60 && getComputedStyle(n).visibility !== 'hidden' && getComputedStyle(n).display !== 'none') tlog('!! element at the top left: <' + n.tagName.toLowerCase() + ' class="' + (n.className && n.className.baseVal === undefined ? n.className : '') + '"> ' + trc(q) + ' in ' + (n.parentNode && n.parentNode.className || n.parentNode && n.parentNode.tagName));
        }); });
      });
      T.watch.observe(document.body, {childList: true, subtree: true});
    }
    T.gutter = document.documentElement.style.scrollbarGutter;
    document.documentElement.style.scrollbarGutter = 'stable';
    tourGo(0);
    setTimeout(tourMeasure, 400);
  };
  // the block built again for a scene has settled: its boxes no longer move nor grow (a few frames alike)
  // ---- dev traces of the tour (TOUR ..., in a source checkout only): steps, scenes and their timing, where the light
  // and the card go, and what looks wrong (the card over the light or a picture, off the window, the light jumping)
  const tz = performance.now();
  function tlog(m){ if (DD.dev) DD.trace('TOUR ' + ((performance.now() - tz) / 1000).toFixed(3) + ' ' + (T ? 's' + T.i + ' ' : '') + m); }
  function trc(q){ return q ? '[' + Math.round(q.left) + ',' + Math.round(q.top) + ' ' + Math.round(q.width != null ? q.width : q.right - q.left) + 'x' + Math.round(q.height != null ? q.height : q.bottom - q.top) + ']' : 'none'; }
  function tcross(a, b){ return a && b && a.left < (b.right != null ? b.right : b.left + b.width) && (a.right != null ? a.right : a.left + a.width) > b.left && a.top < (b.bottom != null ? b.bottom : b.top + b.height) && (a.bottom != null ? a.bottom : a.top + a.height) > b.top; }
  function tcheck(why){
    if (!T || T.i < 0) return;
    const c = T.el.card.getBoundingClientRect(), h = T.el.hole.getBoundingClientRect(), W = window.innerWidth, H = window.innerHeight;
    const bad = [];
    if (T.el.hole.style.opacity !== '0' && tcross(c, {left: h.left + 4, top: h.top + 4, right: h.right - 4, bottom: h.bottom - 4})) bad.push('card over light');
    if (T.extra && tcross(c, T.extra)) bad.push('card over pictures ' + trc(T.extra));
    if (c.left < 0 || c.top < 0 || c.right > W || c.bottom > H) bad.push('card off window');
    if (T.el.hole.style.opacity !== '0' && (h.bottom < 0 || h.top > H)) bad.push('light off window');
    tlog(why + ' light=' + trc(h) + ' card=' + trc(c) + ' win=' + W + 'x' + H + ' scrollY=' + Math.round(window.scrollY) + (bad.length ? ' !! ' + bad.join(', ') : ''));
  }
  function tourSettled(){
    return new Promise(function(resolve){
      const t0 = performance.now(); let last = '', same = 0;
      (function check(){
        if (!T) return resolve();
        const r = tourRect('all'), busy = S && Array.from(S.root.querySelectorAll('[data-wid]')).some(function(e){ return e._ddpH || e._ddpT; });
        const k = r ? [r.left, r.top, r.width, r.height].map(Math.round).join(',') : '';
        same = (k === last && !busy) ? same + 1 : 0; last = k;
        if (same >= 3 || performance.now() - t0 > 3000){ if (same < 3) tlog('settle TIMEOUT 3 s (the block kept moving: ' + k + ')'); return resolve(); }
        requestAnimationFrame(check);
      })();
    });
  }
  // the block as it is stays on screen (a copy, its charts' pictures in it) while the scene is
  // built under it, hidden; _thaw: the new block shows, the light at its place at once, the copy fades away (200 ms)
  DDP._tourRebuild = function(){ if (T && T.onRebuild) T.onRebuild(); };
  function tourFreeze(){
    if (T.cover) return;  // already under a picture (the layouts being measured): it stays
    const root = S && S.root; if (!root || !root.parentNode) return;
    const cover = root.cloneNode(true);
    const src = root.querySelectorAll('canvas'), dst = cover.querySelectorAll('canvas');
    for (let i = 0; i < src.length && i < dst.length; i++){
      try { dst[i].width = src[i].width; dst[i].height = src[i].height; dst[i].getContext('2d').drawImage(src[i], 0, 0); } catch (e) {}
    }
    cover.style.position = 'absolute'; cover.style.margin = '0'; cover.style.pointerEvents = 'none'; cover.style.zIndex = '2147482000';
    cover.style.left = root.offsetLeft + 'px'; cover.style.top = root.offsetTop + 'px';
    cover.style.width = root.offsetWidth + 'px'; cover.style.height = root.offsetHeight + 'px'; cover.style.boxSizing = 'border-box';
    root.parentNode.insertBefore(cover, root.nextSibling);
    root.style.visibility = 'hidden';
    tourLockH(root);
    tlog('picture over the block ' + trc(cover.getBoundingClientRect()));
    T.cover = cover;
  }
  function tourThawNow(){
    const c = T && T.cover; if (!c) return;
    tlog('picture over the block removed at once');
    T.cover = null; c.remove(); if (S && S.root) S.root.style.visibility = '';
    tourUnlockH();
  }
  // the block keeps its height while it is built again under the picture (the layouts measured on the first step, a
  // scene): its height followed each layout, and what is under it in the page (another add-on's part of the deck
  // list) went up and down, into the picture, several times
  function tourLockH(root){
    if (T.lockH) return;
    T.lockH = {el: root, h: root.style.height, o: root.style.overflow};
    root.style.height = root.offsetHeight + 'px'; root.style.overflow = 'visible';
  }
  function tourUnlockH(){
    const l = T && T.lockH; if (!l) return;
    T.lockH = null; l.el.style.height = l.h; l.el.style.overflow = l.o;
  }
  function tourThaw(){
    const c = T && T.cover; if (!c) return;
    T.cover = null;
    const root = S && S.root, CARDS = '[data-wid], .dd-sc[data-key]';
    if (root) root.style.visibility = '';
    tourUnlockH();
    // a cross-fade card by card: a box faded as a whole (the copy, the block) lost its frosted glass for the time of
    // the fade (an ancestor with an opacity cuts what a backdrop blur sees), and the two glass layers darkened
    tlog('picture over the block fading away');
    if (!c.animate || !root){ c.remove(); return; }
    root.querySelectorAll(CARDS).forEach(function(e){ e.animate([{opacity: 0}, {opacity: 1}], {duration: 200}); });
    c.querySelectorAll(CARDS).forEach(function(e){ e.animate([{opacity: 1}, {opacity: 0}], {duration: 200, fill: 'forwards'}); });
    setTimeout(function(){ c.remove(); }, 210);
  }
  function tourScene(name, opts){
    if (!T) return Promise.resolve();
    // the same scene still being built (a layout of the cycle asked just before Next): waited for, not shown as ready
    if (T.scene === name) return T.sceneP && T.sceneP.name === name ? T.sceneP.p : Promise.resolve();
    // the light keeps following a scene updated in place (the next text: it grew with it at once); it waits only under
    // the picture of a block built again
    T.prevScene = T.scene; T.scene = name;
    // a newer scene asked meanwhile (Next while a layout of the cycle was being built) takes over: this one, done
    // first, neither unfreezes the light nor takes the picture away, the newer block still being built under it
    const seq = T.sceneSeq = (T.sceneSeq || 0) + 1;
    // the picture over the block is put by the block itself when it is built again (DDP.reboot, full): a scene that
    // only repaints or updates widgets in place (a theme, a period, the next text) has none, whatever came before
    let cover = false;
    T.onRebuild = function(){ cover = true; T.frozen = true; tourFreeze(); };
    const t0 = performance.now(); let t1 = 0;
    const tok0 = token, T0 = T;
    const p = DDP.call('tour_scene', {name: name}).catch(function(){})
      .then(function(){
        t1 = performance.now();
        // the block is built after the answer (Python's refresh on its next turn): waited for, at most 300 ms
        return new Promise(function(r){ const t2 = performance.now(); (function w(){ if (token !== tok0 || performance.now() - t2 > 300) return r(); requestAnimationFrame(w); })(); });
      })
      .then(tourSettled)
      .then(function(){
        if (!T || T !== T0) return;
        if (T.sceneSeq !== seq){ tlog('scene ' + name + ' done, a newer scene asked meanwhile: the light stays'); return; }
        T.onRebuild = null; T.snapUntil = performance.now() + 80;
        tlog('scene ' + name + (cover ? ' (picture over)' : ' (in place)') + ' answer=' + (t1 - t0).toFixed(0) + 'ms settled=' + (performance.now() - t0).toFixed(0) + 'ms');
        T.frozen = false; T.glideUntil = 0; tourPlace(false, false);
        if (opts && opts.handOver){ tourThawNow(); opts.handOver(); } else tourThaw();
      });
    T.sceneP = {name: name, p: p};
    return p;
  }
  // while the first step is read, under a picture of the screen, each layout of the
  // layouts step is built once and the tallest kept: the card of that step then sits under it from the start and
  // stays there. Next does not wait: the measuring stops, the picture stays, the step's own scene is built under it.
  function tourMeasure(){
    if (!T || T.i !== 0 || T.steps[0].scene) return;
    const lay = T.steps.filter(function(x){ return x.action === 'layouts'; })[0], scenes = lay ? (lay.cycle || []) : [];
    if (!scenes.length || T.layoutMax) return;
    T.measuring = true; T.frozen = true; tourFreeze();
    let k = 0, max = 0;
    const wait = function(){ return new Promise(function(res){ setTimeout(res, 60); }); };
    const done = function(){
      if (!T) return;
      if (max) T.layoutMax = max;
      tlog('layouts measured: tallest=' + Math.round(max) + ' (' + k + '/' + scenes.length + ')' + (T.pendingGo != null ? ' cut by Next' : ''));
      const pend = T.pendingGo; T.pendingGo = null;
      if (pend != null){ T.measuring = false; T.frozen = false; tourGo(pend); if (!T.frozen) tourThaw(); return; }
      // still "measuring" while the user's own layout comes back: a Next meanwhile waits for it instead of asking a
      // second scene on top of this one
      T.frozen = true; T.scene = null;
      DDP.call('tour_scene', {name: null}).catch(function(){}).then(wait).then(tourSettled).then(function(){
        if (!T) return;
        // the user's own layout again, as it was under the picture: the picture goes at once (a cross-fade of the same
        // widgets showed the background through them for a moment, a flash)
        T.measuring = false; T.frozen = false; tourPlace(false, false); tourThawNow(); tlog('layouts measured: own layout back, picture removed at once');
        if (T.steps.some(function(x){ return x.action === 'add'; })) tourAddAsk();
        const mc = tourMenuCard(), sc = tourSpanCard();
        if (mc && T.steps.some(function(x){ return x.action === 'menu'; })) tourAsk('tour_menu', {id: mc.dataset.wid});
        if (sc && T.steps.some(function(x){ return x.action === 'spans'; })) tourAsk('tour_span', {id: sc.dataset.wid});
        if (T.pendingGo != null){ const p = T.pendingGo; T.pendingGo = null; tourGo(p); }
      });
    };
    const one = function(){
      if (!T) return;
      if (T.pendingGo != null || k >= scenes.length){ done(); return; }
      const name = scenes[k++]; T.scene = name;
      DDP.call('tour_scene', {name: name}).catch(function(){}).then(wait).then(tourSettled).then(function(){
        const r = tourRect('all'); if (r) max = Math.max(max, r.height + 2 * TOUR_PAD); one();
      });
    };
    one();
  }
  function tourLater(fn, ms){ const g = T.gen; T.timers.push(setTimeout(function(){ if (T && T.gen === g) fn(); }, ms)); }
  function tourGo(i){
    if (!T || T.busy) return;
    if (T.measuring){ T.pendingGo = i; T.el.card.classList.add('wait'); return; }  // the layouts being measured stop at once (_go: interrupted)
    if (i >= T.steps.length){ tourClose(); return; }
    if (i < 0) return;
    tourStop();
    T.i = i; T.gen++;
    const st = T.steps[i], cyc = st.cycle || [];
    const want = st.scene && cyc.indexOf(T.scene) >= 0 ? T.scene : (st.scene || null), tGo = performance.now();  // a scene of this step already shown
    const show = function(){
      if (!T || T.i !== i) return;
      T.busy = false; T.el.card.classList.remove('wait');
      T.el.text.textContent = (tourTouch() && st.touch_text) || st.text;
      T.el.back.style.visibility = i > 0 ? '' : 'hidden';
      T.el.next.textContent = i === T.steps.length - 1 ? (T.L.done || 'Done') : (T.L.next || 'Next');
      K.dots(T.el, T.steps.length, i, tourGo);
      tourScroll(st);
      tourPlace(true, true);
      tourAction(st);
      tlog('step ' + (st.action || '-') + ' target=' + st.target + ' scene=' + T.scene + ' ready in ' + Math.round(performance.now() - tGo) + ' ms');
      setTimeout(function(){ if (T && T.i === i) tcheck('placed'); }, 260);
    };
    const fade = function(){ tourLater(function(){ if (T && T.busy) T.el.card.classList.add('wait'); }, 150); };  // a quick wait: the card does not blink
    if (want === T.scene){
      const pp = tourPrep(st);
      if (!pp){ show(); return; }
      T.busy = true; fade(); pp.then(show);
      return;
    }
    // a scene to build: the card waits (faded), the light stays where it is until the new layout has settled
    T.busy = true; fade();
    tourScene(want).then(function(){ return T && T.i === i ? tourPrep(st) : null; }).then(show);
  }
  // the pictures a step shows, built in Anki (the add step's menu and gallery, the menu and span steps' ones): waited
  // for before the card is placed, so it is placed once, clear of them. They are asked ahead while the first step is
  // read, but a Next during the layouts' measuring cut that short: the card was placed, then moved aside 70 ms later
  // when they came. Asked once the step's own layout has settled (their anchors are found in it); at most 800 ms.
  function tourPrep(st){
    let p = null;
    if (st.action === 'add') p = tourAddAsk();
    else if (st.action === 'menu'){ const c = tourMenuCard(); if (c) p = tourAsk('tour_menu', {id: c.dataset.wid}); }
    else if (st.action === 'spans'){ const c = tourSpanCard(); if (c) p = tourAsk('tour_span', {id: c.dataset.wid}); }
    if (!p) return null;
    return Promise.race([p.catch(function(){}), new Promise(function(r){ setTimeout(r, 800); })]);
  }
  // what the step talks about brought into view, the page scrolling under the dimmed screen: the target and the card
  // under it (margin 24); the layouts step counts its tallest layout; never past the target's top
  function tourScroll(st){
    const r = tourRect(st.target); if (!r) return;
    const H = window.innerHeight, m = 24, ch = (T.el.card.offsetHeight || 120) + 12;
    const hgt = st.action === 'layouts' && T.layoutMax ? Math.max(r.height, T.layoutMax - 2 * TOUR_PAD) : r.height;
    const need = r.top + hgt + m + (hgt < H / 2 || st.action === 'layouts' ? ch : 0);
    if (r.top >= m && need <= H){ tourHoldHeight(0); return; }
    let dy;
    if (need > H && hgt + 2 * m < H) dy = Math.min(need - H, r.top - m);
    else dy = r.top - m;
    tourHoldHeight(dy);
    if (Math.abs(dy) >= 3){ T.scrolling = true; window.scrollBy({top: dy, left: 0, behavior: 'auto'}); tlog('scroll by ' + Math.round(dy) + ' (target ' + trc(r) + ' needs ' + Math.round(need) + ' of ' + H + ')'); }
  }
  // the page never shorter than the view the tour scrolled to: the block at the page's end, its examples taking
  // turns (a short layout after a tall one) shrank the page, the scroll was cut and the block went down, its tallest
  // example under the window's edge; and a target there could not be scrolled up to. Put back on close.
  function tourHoldHeight(dy){
    const de = document.documentElement, want = Math.ceil(window.scrollY + dy + window.innerHeight);
    if (T.minH0 == null) T.minH0 = de.style.minHeight;
    if (want > (T.minH || 0)){ T.minH = want; de.style.minHeight = want + 'px'; }
  }
  // the light on the step's target; the card (moveCard) centered under it, else over it, else
  // over its lower part; a step whose examples change size leaves the card where every example leaves it room (the
  // layouts: under the tallest one measured, _layout_heights); the menu, add and span steps then take it clear of
  // their pictures (_card_clear_of). Without moveCard the card stays, unless the light grew over it (_thaw).
  function tourPlace(glide, moveCard){
    if (!T || T.i < 0) return;
    // the next step's scene being built (tourGo, busy): the light stays on the step before until show() glides it, once
    // the new block has settled. T.i is already the next step's: followed each frame meanwhile, the light went to that
    // step's target as found in the scene still on screen (the add step's chart in a layout example), then jumped
    if (T.busy) return;
    const st = T.steps[T.i], r = tourRect(st.target), el = T.el;
    if (!r){ if (el.hole.style.opacity !== '0') tlog('no target for ' + st.target + ': light hidden'); el.hole.style.opacity = '0'; T.lastHole = null; return; }
    el.hole.style.opacity = '1';
    // a glide (180 ms, _hole_anim) is not cut by the follow of the next frames: they only move its end. A target that
    // changes size by itself (a text widget's new sentence, a chart's data) is followed gliding too (_watch_target);
    // after a picture over the block and while the page scrolls, the light goes at once
    const P = TOUR_PAD, h = {left: r.left - P, top: r.top - P, width: r.width + 2 * P, height: r.height + 2 * P};
    h.right = h.left + h.width; h.bottom = h.top + h.height;
    const now = performance.now(), ph0 = T.lastHole;
    const sizeMoved = ph0 && (Math.abs(ph0.width - h.width) > 2 || Math.abs(ph0.height - h.height) > 2 || Math.abs(ph0.left - h.left) > 2);
    const scrolled = T.holeY != null && Math.abs(window.scrollY - T.holeY) > 0.5;
    T.holeY = window.scrollY;
    // (a target that changes size by itself, the text widget's next sentence, is followed at once: the light
    // jumps to it while the picture fades, it does not glide behind it)
    void sizeMoved; void scrolled;
    if (glide) T.glideUntil = now + 200;
    el.hole.classList.toggle('snap', !glide && !(T.glideUntil > now));
    const ph = T.lastHole;
    if (ph && !glide && !(T.glideUntil > now) && (Math.abs(ph.left - h.left) > 30 || Math.abs(ph.top - h.top) > 30 || Math.abs(ph.width - h.width) > 30 || Math.abs(ph.height - h.height) > 30)) tlog('light JUMP ' + trc(ph) + ' -> ' + trc(h) + ' target=' + st.target + (T.addFocus ? ' focus=' + T.addFocus : ''));
    if (st.action === 'texts' && ph && (Math.abs(ph.left - h.left) > 0.5 || Math.abs(ph.top - h.top) > 0.5 || Math.abs(ph.width - h.width) > 0.5 || Math.abs(ph.height - h.height) > 0.5)) tlog('text light ' + trc(ph) + ' -> ' + trc(h) + (glide || T.glideUntil > now ? ' (gliding)' : ' (at once)') + ' frozen=' + !!T.frozen);
    T.lastHole = h;
    el.hole.style.left = h.left + 'px'; el.hole.style.top = h.top + 'px'; el.hole.style.width = h.width + 'px'; el.hole.style.height = h.height + 'px';
    if (st.action === 'layouts' && !T.frozen) T.layoutMax = Math.max(T.layoutMax || 0, h.height);  // _layout_partial
    const cw = el.card.offsetWidth || 358, ch = el.card.offsetHeight || 120, W = window.innerWidth, H = window.innerHeight;
    const cur = el.card.getBoundingClientRect();
    if (!moveCard && T.placed !== T.i) return;  // the next step is being made ready: its card is placed when it shows
    if (!moveCard){
      // an example grew over the card: it moves away on the side it is on, never sideways
      if (cur.right > h.left && cur.left < h.right && cur.bottom > h.top && cur.top < h.bottom){
        if (cur.top + ch / 2 < h.top + h.height / 2){ const y = h.top - 12 - ch; if (y >= 8 && y < cur.top){ el.card.style.top = Math.round(y) + 'px'; tlog('card moved up (light grew over it) to ' + Math.round(y)); } }
        else { const y = Math.min(h.bottom + 12, H - ch - 8); if (y > cur.top){ el.card.style.top = Math.round(y) + 'px'; tlog('card moved down (light grew over it) to ' + Math.round(y)); } }
        if (!T.overWarned || performance.now() - T.overWarned > 1500){ T.overWarned = performance.now(); tcheck('light over card'); }
      }
      return;
    }
    T.placed = T.i;
    let slack = st.action === 'texts' ? 48 : 0;  // _CARD_SLACK
    if (st.action === 'layouts' && T.layoutMax) slack = Math.max(0, T.layoutMax - h.height);
    let x = h.left + h.width / 2 - cw / 2, y;
    // the tallest example and the card under it do not fit in the window (and the page cannot scroll that far): the
    // card goes over the light, where every example leaves it room, instead of over the examples' lower part
    if ((st.action === 'texts' || st.action === 'layouts') && h.top - 12 - ch >= 8) y = h.top - 12 - ch;  // the texts / layout examples grow downwards: the card over them stays put, in the free space over the block
    else if (slack && h.bottom + slack + 12 + ch > H - 8 && h.top - 12 - ch >= 8) y = h.top - 12 - ch;
    else if (h.bottom + 12 + ch <= H - 8) y = Math.min(h.bottom + 12 + slack, H - ch - 8);
    else if (h.top - 12 - ch >= 8) y = h.top - 12 - ch;
    else y = Math.min(H - ch - 8, Math.max(8, h.bottom - ch - 12));
    x = Math.max(8, Math.min(x, W - cw - 8)); y = Math.max(8, Math.min(y, H - ch - 8));
    if (T.extra && /^(menu|add|spans)$/.test(st.action)){ const q = tourClearOf(x, y, cw, ch, T.extra, h, W, H); x = q[0]; y = q[1]; }
    el.card.style.left = Math.round(x) + 'px'; el.card.style.top = Math.round(y) + 'px';
    tlog('card placed ' + st.action + ' light=' + trc(h) + ' slack=' + Math.round(slack) + (T.layoutMax ? ' tallest=' + Math.round(T.layoutMax) : '') + ' extra=' + trc(T.extra) + ' -> card ' + Math.round(x) + ',' + Math.round(y) + ' ' + cw + 'x' + ch + ' win=' + W + 'x' + H);
  }
  // _card_clear_of: beside the light on the side away from the picture, then under / over it, then around the
  // picture; else where it covers the least
  function tourClearOf(x, y, cw, ch, a, h, W, H){
    const hit = function(cx, cy){ return cx < a.right && cx + cw > a.left && cy < a.bottom && cy + ch > a.top; };
    if (!hit(x, y)) return [x, y];
    const spots = [], acx = (a.left + a.right) / 2, hcx = h.left + h.width / 2;
    if (acx >= hcx) spots.push([h.left - cw - 12, h.top], [a.left - cw - 12, h.bottom + 12], [a.left - cw - 12, h.top - ch - 12]);
    else spots.push([h.right + 12, h.top], [a.right + 12, h.bottom + 12], [a.right + 12, h.top - ch - 12]);
    [h.bottom + 12, h.top - 12 - ch].forEach(function(yy){ [h.left, h.right - cw, (W - cw) / 2].forEach(function(xx){ spots.push([xx, yy]); }); });
    spots.push([acx - cw / 2, a.bottom + 12], [acx - cw / 2, a.top - ch - 12], [a.left - cw - 12, a.top], [a.right + 12, a.top], [a.left - cw - 12, a.bottom - ch], [a.right + 12, a.bottom - ch]);
    let best = null;
    const over = function(cx, cy){ const w = Math.max(0, Math.min(cx + cw, a.right) - Math.max(cx, a.left)), hh = Math.max(0, Math.min(cy + ch, a.bottom) - Math.max(cy, a.top)); return w * hh; };
    for (const sp of spots){
      const cx = Math.max(8, Math.min(sp[0], W - cw - 8)), cy = Math.max(8, Math.min(sp[1], H - ch - 8));
      if (!hit(cx, cy)) return [cx, cy];
      const o = over(cx, cy); if (!best || o < best[0]) best = [o, cx, cy];
    }
    return best && best[0] < over(x, y) ? [best[1], best[2]] : [x, y];
  }
  // ---- the step's live part ----
  function tourPtr(x, y, show){ K.ptr(T.el, x, y, show); }
  function tourPic(src, x, y, w, h){
    const was = T.el.pic.style.display === 'block', q = K.pic(T.el, src, x, y, w, h);
    if (!q){ if (was) tlog('picture hidden'); return; }
    const W = window.innerWidth, H = window.innerHeight;
    tlog('picture ' + trc(q) + (x < 0 || y < 0 || x + w > W || y + h > H ? ' !! off window ' + W + 'x' + H : '') + (tcross(T.el.card.getBoundingClientRect(), q) ? ' !! under the card' : ''));
  }
  function tourAction(st){
    const cyc = st.cycle || [];
    // _on_action_timer: the layouts, themes and texts change every 1.5 s
    if (cyc.length > 1){
      const next = function(){
        if (!T) return;
        tourScene(cyc[(cyc.indexOf(T.scene) + 1) % cyc.length]);
        tourLater(next, 1500);
      };
      tourLater(next, 1500);
    }
    if (st.action === 'add') tourAddDemo();
    if (st.action === 'zoom') tourZoomDemo();
    if (st.action === 'swap') tourDragDemo();
    if (st.action === 'menu') tourMenuDemo();
    if (st.action === 'spans') tourSpanDemo();
  }
  // ---- what the demos move over the dimmed screen: copies of the widgets (their charts' pictures in them), with
  // the block's look (its classes and colors) ----
  function tourLayer(){
    if (T.layer) return T.layer;
    const l = document.createElement('div');
    l.className = S.root.className; l.style.cssText = S.root.style.cssText;
    l.style.position = 'fixed'; l.style.left = '0'; l.style.top = '0'; l.style.width = '100%'; l.style.height = '100%';
    l.style.padding = '0'; l.style.margin = '0'; l.style.pointerEvents = 'none'; l.style.background = 'none'; l.style.visibility = 'visible';
    T.el.ov.insertBefore(l, T.el.pic);
    T.layer = l; return l;
  }
  function tourGhost(el){
    const r = el.getBoundingClientRect(), c = el.cloneNode(true);
    const src = el.querySelectorAll('canvas'), dst = c.querySelectorAll('canvas');
    for (let i = 0; i < src.length && i < dst.length; i++){
      try { dst[i].width = src[i].width; dst[i].height = src[i].height; dst[i].getContext('2d').drawImage(src[i], 0, 0); } catch (e) {}
    }
    c.style.position = 'absolute'; c.style.left = r.left + 'px'; c.style.top = r.top + 'px'; c.style.width = r.width + 'px'; c.style.height = r.height + 'px';
    c.style.margin = '0'; c.style.transform = 'none'; c.style.transformOrigin = '0 0'; c.style.boxSizing = 'border-box'; c.style.opacity = '1';
    tourLayer().appendChild(c);
    return {el: c, r: {left: r.left, top: r.top, width: r.width, height: r.height}};
  }
  function tourHide(el, a){ T.hidden = T.hidden || []; T.hidden.push([el, el.style.opacity]); el.style.opacity = String(a); }
  function tourClearGhosts(fade){
    if (!T) return;
    if (T.layer){
      const l = T.layer; T.layer = null;
      if (fade && l.animate){ tlog('copies fading over the new layout'); const a = l.animate([{opacity: 1}, {opacity: 0}], {duration: 160, fill: 'forwards'}); a.onfinish = function(){ l.remove(); }; }
      else l.remove();
    }
    (T.hidden || []).forEach(function(h){ h[0].style.opacity = h[1]; }); T.hidden = [];
    tourPtr(0, 0, false);
  }
  // a tween on the frames, dropped when the step changes
  function tourTween(ms, fn, done){
    const g = T.gen;
    K.tween(ms, K.ease.cubic, function(){ return !!T && T.gen === g; }, fn, done);
  }
  // _carry: the pointer on the copy first, then both move together (the copy to rect `to`, scaled)
  function tourCarry(g, to, grab, grabTo, ms, pause, done){
    tourPtr(grab.x, grab.y);
    tourLater(function(){
      const r = g.r, sx = to.width / r.width;
      tourTween(ms, function(e){
        const x = r.left + (to.left - r.left) * e, y = r.top + (to.top - r.top) * e, s = 1 + (sx - 1) * e;
        g.el.style.transform = 'translate(' + (x - r.left) + 'px,' + (y - r.top) + 'px) scale(' + s + ')';
        tourPtr(grab.x + (grabTo.x - grab.x) * e, grab.y + (grabTo.y - grab.y) * e);
      }, done);
    }, pause || 0);
  }
  function tourSlide(g, to, ms, delay){
    tourLater(function(){
      const r = g.r;
      tourTween(ms, function(e){ g.el.style.transform = 'translate(' + (to.left - r.left) * e + 'px,' + (to.top - r.top) * e + 'px)'; });
    }, delay || 0);
  }
  // _GapMarker.show_bar: the accent bar where the widget would land, with what a drop there does
  function tourBar(rect, label){
    const b = document.createElement('div'); b.className = 'ddp-gapbar';
    b.style.position = 'absolute'; b.style.display = 'block';
    b.style.left = rect.left + 'px'; b.style.top = rect.top + 'px'; b.style.width = rect.width + 'px'; b.style.height = rect.height + 'px';
    b.innerHTML = '<span></span>'; b.querySelector('span').textContent = label || '';
    tourLayer().appendChild(b);
  }
  // ---- the zoom step: the mouse drags across the chart (its real selection shows), lets go,
  // the chart zooms on it; back to the full view 1.9 s later; again every 4.6 s ----
  function tourResetZoom(){
    zbusy = true;
    try {
      Object.keys(zoomed).forEach(function(id){
        const e = zoomed[id]; if (!e) return;
        if (e.last || (e.z && e.z.get && e.z.get())){
          if (e.z && e.z.set) e.z.set(null);
          e.last = null;
          showReset(e);
        }
      });
    } finally { zbusy = false; }
  }
  function tourZoomDemo(){
    const run = function(){
      if (!T) return;
      tourLater(run, 4600);
      const z = tourZoomCard(); if (!z) return;
      const cv = z.el.querySelector('.dd-plot canvas'); if (!cv) return;
      T.zoomed = z;
      tourResetZoom();
      const at = function(f){ const r = cv.getBoundingClientRect(); return {x: r.left + r.width * f, y: r.top + r.height * 0.55}; };
      const send = function(type, p, target){ (target || cv).dispatchEvent(new MouseEvent(type, {clientX: p.x, clientY: p.y, button: 0, buttons: type === 'mouseup' ? 0 : 1, bubbles: true})); };
      let p = at(0.42); tourPtr(p.x, p.y);
      tourLater(function(){
        p = at(0.42); send('mousedown', p);
        let k = 0;
        const move = function(){
          k++; const q = at(0.42 + (0.72 - 0.42) * k / 10); tourPtr(q.x, q.y); send('mousemove', q);
          if (k < 10){ tourLater(move, 30); return; }
          tourLater(function(){
            send('mouseup', at(0.72), window); tourPtr(0, 0, false);
            const took = !!z.e.z.get();
            if (!took){ const n = z.e.z.count(), a = Math.floor(n * 0.42); z.e.z.set(a, Math.min(n, Math.max(a + 3, Math.floor(n * 0.72)))); }
            tlog('zoom drag ' + (took ? 'taken by the chart' : 'NOT taken: zoomed directly') + ' range=' + JSON.stringify(z.e.z.get()));
            z.e.last = z.e.z.get(); showReset(z.e);
            tourLater(tourResetZoom, 1900);
          }, 150);
        };
        tourLater(move, 40);
      }, 200);
    };
    tourLater(run, 500);
  }
  // ---- the drag step: two charts trade places, one goes in a new box, a whole box
  // moves, a space between two lines is dragged bigger and back; again and again ----
  function tourPair(){
    const cs = tourCharts().filter(function(el){ return !/^tour-/.test(el.dataset.wid); });
    if (cs.length < 2) return null;
    const rows = {};
    cs.forEach(function(el){ const k = Math.round(el.getBoundingClientRect().top / 20); (rows[k] = rows[k] || []).push(el); });
    const keys = Object.keys(rows).map(Number).sort(function(a, b){ return a - b; });
    for (const k of keys){ const same = rows[k].sort(function(a, b){ return a.getBoundingClientRect().left - b.getBoundingClientRect().left; }); if (same.length >= 2) return [same[0], same[1]]; }
    return [cs[0], cs[1]];
  }
  function tourDragDemo(){
    const g = T.gen, L = T.L, p0 = tourPair();
    const moveId = p0 ? p0[1].dataset.wid : null;
    if (moveId) DDP.call('tour_drag', {move: moveId}).catch(function(){});
    // on touch no line grip and no gap handle: only what a finger does (hold, then drag)
    const demos = tourTouch() ? ['swap', 'newbox'] : ['swap', 'newbox', 'movebox', 'gap'];
    const seq = function(k){
      if (!T || T.gen !== g) return;
      const nxt = function(){ tourLater(function(){ seq(k + 1); }, 150); };
      const kind = demos[k % demos.length];
      tlog('drag demo ' + kind);
      if (kind === 'swap') swap(nxt); else if (kind === 'gap') gap(nxt); else drop(kind, nxt);
    };
    const cardRect = function(){ return T.el.card.getBoundingClientRect(); };
    // a scene that lands after the step was left (Next during it) does nothing more: the demo belonged to that step
    // the swap: the copies already stand where the two charts land, so the new layout shows at once under them and
    // they fade away (with a picture over the block cross-faded first, the cards blinked: switched "d'un coup");
    // the other drops: the copies fade while the new layout fades in
    const scene = function(name, then){
      const swapped = name === 'drag:swap';
      tourScene(name, swapped ? {handOver: function(){ tlog('swap: new layout under the copies, copies fading'); tourClearGhosts(true); }} : null).then(function(){
        if (!T || T.gen !== g) return;
        if (!swapped) tourClearGhosts(true);
        if (then) then();
      });
    };
    // _swap_demo: the right one taken by the mouse onto the left one, the left one slides over; the layout takes the order
    const swap = function(done){
      const p = tourPair(); if (!p) return done();
      const a = p[0], b = p[1], ra = a.getBoundingClientRect(), rb = b.getBoundingClientRect(), gapX = rb.left - ra.right;
      const nb = {left: ra.left, top: rb.top, width: rb.width, height: rb.height}, na = {left: ra.left + rb.width + gapX, top: ra.top, width: ra.width, height: ra.height};
      tourClearGhosts();
      tlog('swap ' + a.dataset.type + ' ' + trc(ra) + ' <-> ' + b.dataset.type + ' ' + trc(rb) + ' to ' + trc(nb) + ' / ' + trc(na));
      const ga = tourGhost(a), gb = tourGhost(b); tourHide(a, 0); tourHide(b, 0);
      DDP.call('tour_drag', {swap: [a.dataset.wid, b.dataset.wid]}).catch(function(){});
      tourSlide(ga, na, 500, 350);
      tourCarry(gb, nb, {x: rb.left + 70, y: rb.top + 14}, {x: nb.left + 70, y: nb.top + 14}, 500, 350, function(){
        tourPtr(0, 0, false);
        scene('drag:swap', function(){ tourLater(done, 450); });
      });
    };
    // _drop_demo: a copy carried to a gap, the gap's bar, dropped: the layout changes (1.6 s), then back
    const drop = function(kind, done){
      const area = tourRect('all'); if (!area) return done();
      let el, point, bar, label, grab, scale, grip = null;
      if (kind === 'movebox'){
        const secs = sections(); if (secs.length < 2) return done();
        const pick = secs.filter(function(x){ return x.box.fam === 'stat'; })[0] || secs.filter(function(x){ return x.box.fam === 'chart'; })[0] || secs[0];
        const idx = secs.indexOf(pick);
        const below = idx === 0 ? true : idx === secs.length - 1 ? false : cardRect().top + cardRect().height / 2 < area.top + area.height / 2;
        DDP.call('tour_drag', {box: [pick.box.key, below ? 'bottom' : 'top']}).catch(function(){});
        const y = below ? area.bottom + 14 : area.top - 14;
        el = pick.box.el; point = {x: area.left + area.width / 2, y: y}; bar = {left: area.left, top: y - 2, width: area.width, height: 4};
        label = L.movehere || 'Move here'; scale = 0.45;
      } else {
        el = moveId && S.root.querySelector('[data-wid="' + moveId + '"]'); if (!el) return done();
        const below = cardRect().top + cardRect().height / 2 < area.top + area.height / 2;
        DDP.call('tour_drag', {move: moveId, end: below ? 'bottom' : 'top'}).catch(function(){});
        const y = below ? area.bottom + 14 : area.top - 14;
        point = {x: area.left + area.width / 2, y: y}; bar = {left: area.left, top: y - 2, width: area.width, height: 4};
        label = L.newline || 'New line'; scale = 0.6;
      }
      tourClearGhosts();
      const gh = tourGhost(el); tourHide(el, 0.25);
      let st = gh.r;
      if (kind === 'movebox'){
        // the box's widgets, not the whole width of the line
        const ws = Array.from(el.querySelectorAll('[data-wid], .dd-sc[data-key]')).map(function(e){ return e.getBoundingClientRect(); }).filter(function(q){ return q.width > 0; });
        if (ws.length) st = {left: Math.min.apply(null, ws.map(function(q){ return q.left; })), top: Math.min.apply(null, ws.map(function(q){ return q.top; }))};
      }
      if (kind === 'movebox'){
        // taken by its handle, on its left
        grip = document.createElement('div'); grip.className = 'ddp-grip';
        grip.innerHTML = '<i></i><i></i><i></i><i></i><i></i><i></i>';
        grip.style.position = 'absolute'; grip.style.display = 'block'; grip.style.width = '16px'; grip.style.height = '26px';
        grip.style.left = Math.max(0, st.left - 16 - 6) + 'px'; grip.style.top = (st.top + 2) + 'px';
        tourLayer().appendChild(grip);
        grab = {x: Math.max(0, st.left - 22) + 8, y: st.top + 15};
      } else grab = {x: st.left + 70, y: st.top + 14};
      const g0 = gh.r, end = {width: g0.width * scale, height: g0.height * scale}; end.left = point.x - end.width / 2; end.top = point.y - end.height / 2;
      const grabTo = {x: end.left + (grab.x - g0.left) * scale, y: end.top + (grab.y - g0.top) * scale};
      tlog(kind + ' ' + trc(g0) + ' carried to ' + trc(end) + ' bar ' + trc(bar));
      tourCarry(gh, end, grab, grabTo, 450, 350);
      tourLater(function(){
        tourBar(bar, label);
        tourLater(function(){
          tourPtr(0, 0, false);
          const t0 = performance.now();
          scene('drag:' + kind, function(){
            tourLater(function(){ scene(null, function(){ tourLater(done, 600); }); }, Math.max(0, 1600 - (performance.now() - t0)));
          });
        }, 450);
      }, 850);
    };
    // _gap_demo: the mouse rests in a space between two lines, its grip shows, the space is dragged 70 px bigger,
    // then back (only on screen, nothing saved)
    const gap = function(done){
      const secs = sections(), card = cardRect(), rr = S.root.getBoundingClientRect();
      let pick = null;
      for (let i = 0; i < secs.length - 1; i++){
        const a = secs[i].r, b = secs[i + 1].r, top = rr.top + a.y + a.h, bot = rr.top + b.y;
        const r = {left: rr.left + Math.min(a.x, b.x), top: top, right: rr.left + Math.max(a.x + a.w, b.x + b.w), bottom: Math.max(bot, top + 10)};
        if (r.right < card.left - 10 || r.left > card.right + 10 || r.bottom < card.top - 10 || r.top > card.bottom + 10){ pick = {box: secs[i].box, r: r}; break; }
      }
      if (!pick) return done();
      const box = pick.box, orig = parseFloat(box.el.style.marginBottom) || 0, M = markEls();
      const w = pick.r.right - pick.r.left, xl = Math.max(40, Math.min(w - 40, Math.floor(w / 3)));
      const spot = function(){ const r = rectIn(box.el, S.root); return {x: rr.left + r.x + xl, y: S.root.getBoundingClientRect().top + r.y + r.h + Math.max(10, parseFloat(box.el.style.marginBottom) || 0) / 2}; };
      const s0 = spot(), from = {x: s0.x + 60, y: s0.y + 70};
      tourTween(450, function(e){ tourPtr(from.x + (s0.x - from.x) * e, from.y + (s0.y - from.y) * e); });
      T.gapUndo = function(){ box.el.style.marginBottom = orig + 'px'; M.gh.style.display = 'none'; M.gh.classList.remove('on'); DDP.relayout(); };
      const set = function(px){
        box.el.style.marginBottom = px + 'px';
        const r = rectIn(box.el, S.root);
        place(M.gh, {x: pick.r.left - rr.left, y: r.y + r.h, w: w, h: Math.max(10, px)});
        M.gh.querySelector('b').style.left = xl + 'px'; M.gh.querySelector('em').textContent = px + ' px'; M.gh.classList.add('on');
        const q = spot(); tourPtr(q.x, q.y);
      };
      tourLater(function(){
        set(orig);
        const step = function(i, sign){
          const t = i / 14, e = t * t * (3 - 2 * t), d = sign > 0 ? e : 1 - e;
          set(orig + Math.round(70 * d / 2) * 2);
          if (i < 14){ tourLater(function(){ step(i + 1, sign); }, 35); return; }
          if (sign > 0){ tourLater(function(){ step(0, -1); }, 900); return; }
          tourLater(function(){ if (T.gapUndo){ T.gapUndo(); T.gapUndo = null; } tourPtr(0, 0, false); tourLater(done, 400); }, 250);
        };
        tourLater(function(){ step(0, 1); }, 350);
      }, 800);
    };
    tourLater(function(){ seq(0); }, 250);
  }
  // the calendar when it is pinned (the one people least expect a menu on), else the first chart
  function tourMenuCard(){
    if (!S) return null;
    return S.root.querySelector('.ddp-card.dd-card[data-type="heatmap"]') || tourCharts()[0] || null;
  }
  // the widget's real right-click menu opens (850 ms), the mouse on Settings (850 ms), then its
  // settings window beside it (1900 ms), over again; pictures only
  function tourMenuDemo(){
    const card = tourMenuCard(); if (!card) return;
    const g = T.gen, id = card.dataset.wid;
    tourAsk('tour_menu', {id: id}).then(function(m){
      if (!T || T.gen !== g || !m) return;
      const shots = [{kind: 'menu', src: m.plain, w: m.w, h: m.h}, {kind: 'menu', src: m.lit, w: m.w, h: m.h, entry: m.entry}];
      // the settings window's picture: taken meanwhile (its web page built off screen), asked when its turn comes
      if (m.settings) shots.push({kind: 'settings', src: null, w: m.settings.w, h: m.settings.h});
      // _menu_geometry
      const geo = function(sh){
        const el = S.root.querySelector('[data-wid="' + id + '"]') || card, r = el.getBoundingClientRect(), W = window.innerWidth, H = window.innerHeight;
        let sc = Math.min(1, (H - 16) / Math.max(1, sh.h)), x, y, fits = false;
        if (sh.kind === 'settings'){
          sc = Math.min(1, 0.62 * H / Math.max(1, sh.h), 0.42 * W / Math.max(1, sh.w));
          const roomR = W - 8 - (r.right + 12), roomL = r.left - 12 - 8, room = Math.max(roomR, roomL);
          fits = room >= 0.6 * sh.w * sc;
          if (fits) sc = Math.min(sc, room / Math.max(1, sh.w));
          const wv = sh.w * sc;
          x = fits ? (roomR >= roomL ? r.right + 12 : r.left - 12 - wv) : W - wv - 8; y = r.top;
        } else {
          x = r.right - 30; y = r.top + 24;
          if (x + sh.w * sc > W - 8) x = r.right - 30 - sh.w * sc;
        }
        const wv = sh.w * sc, hv = sh.h * sc;
        return {x: Math.max(8, Math.min(x, W - wv - 8)), y: Math.max(8, Math.min(y, H - hv - 8)), w: wv, h: hv, s: sc};
      };
      T.extra = tourUnite(shots.map(function(sh){ const q = geo(sh); return {left: q.x, top: q.y, right: q.x + q.w, bottom: q.y + q.h}; }));
      tourPlace(true, true);
      let k = 0;
      const one = function(){
        if (!T || T.gen !== g) return;
        const sh = shots[k % shots.length]; k++;
        if (sh.kind === 'settings' && !sh.src){
          DDP.call('tour_settings', {id: id}).then(function(p){
            if (!T || T.gen !== g) return;
            if (p && p.pic){ sh.src = p.pic; sh.w = p.w; sh.h = p.h; k--; }  // shown now; else the next one
            one();
          }).catch(function(){ if (T && T.gen === g) one(); });
          return;
        }
        const q = geo(sh);
        tlog('menu shot ' + sh.kind);
        tourPic(sh.src, q.x, q.y, q.w, q.h);
        if (sh.entry) tourPtr(q.x + (sh.entry[0] + sh.entry[2] / 2) * q.s, q.y + (sh.entry[1] + sh.entry[3] / 2) * q.s); else tourPtr(0, 0, false);
        tourLater(one, sh.kind === 'settings' ? 1900 : 850);
      };
      tourLater(one, 200);
    }).catch(function(){});
  }
  // a chart (not the calendar) for the chart added, the stat line for the stat card
  function tourAddAnchor(which){
    if (!S) return null;
    if (which === 'stat'){ const b = S.boxes.filter(function(x){ return x.fam === 'stat'; })[0]; const cs = b ? b.el.querySelectorAll('.dd-sc[data-key]') : []; return cs.length ? cs[cs.length - 1] : null; }
    const c = tourSpanCard() || tourCharts()[0]; return c && !/^tour-add-/.test(c.dataset.wid) ? c : null;
  }
  // what the add step shows, asked of Python ahead (its gallery is built in Anki, which holds the page meanwhile):
  // while the first step is read, under its picture, so Next to the add step does not wait for it and its card is
  // placed once, clear of the pictures, instead of twice
  function tourAddAsk(){
    const ca = tourAddAnchor('chart'), sa = tourAddAnchor('stat');
    const key = (ca ? ca.dataset.wid : '') + '|' + (sa ? sa.dataset.key : '');
    if (T.addAsk && T.addAsk.key === key) return T.addAsk.p;
    const t0 = performance.now();
    const ask = {key: key, p: null, d: null};
    ask.p = DDP.call('tour_add', {chart: ca ? ca.dataset.wid : null, stat: sa ? sa.dataset.key : null}).then(function(d){ tlog('add pictures ready in ' + Math.round(performance.now() - t0) + ' ms'); ask.d = d; return d; });
    T.addAsk = ask;
    return ask.p;
  }
  // the pictures of the menu and span steps (real menus and the settings window, built in Anki, which holds the page
  // while it does), asked once, ahead, while the first step is read
  function tourAsk(cmd, args){
    T.asks = T.asks || {};
    const k = cmd + JSON.stringify(args);
    if (!T.asks[k]){ const t0 = performance.now(); T.asks[k] = DDP.call(cmd, args).then(function(v){ tlog(cmd + ' pictures ready in ' + Math.round(performance.now() - t0) + ' ms'); return v; }); T.asks[k].catch(function(){ if (T && T.asks) delete T.asks[k]; }); }
    return T.asks[k];
  }
  // the add step: the chart's right-click menu opens, the pointer on
  // Add Widget..., the gallery on the chart's tile, the chart shows up; then the "+" at the end of the stat line, a
  // click, the gallery on the stat's tile, the stat card shows up; over again
  function tourAddDemo(){
    const g = T.gen, ca = tourAddAnchor('chart'), sa = tourAddAnchor('stat');
    const key = (ca ? ca.dataset.wid : '') + '|' + (sa ? sa.dataset.key : '');
    const ready = T.addAsk && T.addAsk.key === key && T.addAsk.d;
    const then = function(f){ if (ready) f(T.addAsk.d); else tourAddAsk().then(f).catch(function(){}); };  // asked ahead: the card placed at once
    then(function(d){
      if (!T || T.gen !== g || !d || (!d.chart && !d.stat)) return;
      const chartId = ca ? ca.dataset.wid : null;
      const W = function(){ return window.innerWidth; }, H = function(){ return window.innerHeight; };
      // _gallery_place: centered, at most 70 % of the window, the card under it when it fits
      const gplace = function(){
        const ch = T.el.card.offsetHeight || 120, gw = d.gallery[0], gh = d.gallery[1];
        const sc = Math.min(1, W() * 0.7 / gw, H() * 0.7 / gh, Math.max(0.3, (H() - ch - 28) / gh));
        const w = gw * sc, h = gh * sc; let y = (H() - h) / 2;
        if (y + h + 12 + ch > H() - 8) y = Math.max(8, (H() - (h + 12 + ch)) / 2);
        return {x: (W() - w) / 2, y: y, w: w, h: h, s: sc};
      };
      // where a right click near the top right of the widget opens it, inside the window (a long menu smaller)
      const mplace = function(){
        const e = S.root.querySelector('[data-wid="' + chartId + '"]'); if (!e || !d.chart) return null;
        const r = e.getBoundingClientRect(), m = d.chart, sc = Math.min(1, (H() - 16) / Math.max(1, m.h)), w = m.w * sc, h = m.h * sc;
        let x = r.right - 30; if (x + w > W() - 8) x = r.right - 30 - w;
        return {x: Math.max(8, Math.min(x, W() - w - 8)), y: Math.max(8, Math.min(r.top + 24, H() - h - 8)), w: w, h: h, s: sc};
      };
      const area = function(){ const a = [], gp = gplace(), mp = mplace(); a.push({left: gp.x, top: gp.y, right: gp.x + gp.w, bottom: gp.y + gp.h}); if (mp) a.push({left: mp.x, top: mp.y, right: mp.x + mp.w, bottom: mp.y + mp.h}); return tourUnite(a); };
      const touchBtn = function(){ return tourTouch() ? S.root.querySelector('.ddp-touch-add') : null; };
      const plusOff = function(){
        if (marks){ marks.plus.style.display = 'none'; marks.plus.classList.remove('ddp-pulse'); }
        const b = touchBtn(); if (b) b.classList.remove('ddp-pulse');
      };
      const plusOn = function(){ const p = tourPlusSpot('stat'); if (!p) return null; const M = markEls(); place(M.plus, {x: p.pt.x, y: p.pt.y, w: 20, h: 20}); M.plus._t = p.pt.t; tlog('+ shown at ' + trc(p.r)); return p; };
      const gallery = function(which, then){
        DDP.call('tour_gallery', {which: which}).then(function(q){
          if (!T || T.gen !== g) return;
          if (q){
            const gp = gplace();
            tourPic(q.pic, gp.x, gp.y, gp.w, gp.h);
            const sx = gp.w / Math.max(1, q.w || d.gallery[0]), sy = gp.h / Math.max(1, q.h || d.gallery[1]);
            const tx = gp.x + q.x * sx, ty = gp.y + q.y * sy;
            const pr = T.el.ptr.getBoundingClientRect();
            const fx = T.el.ptr.style.opacity === '1' && pr.width ? pr.left : gp.x + gp.w * 0.5;
            const fy = T.el.ptr.style.opacity === '1' && pr.height ? pr.top : gp.y + gp.h * 0.85;
            tourTween(380, function(e){ tourPtr(fx + (tx - fx) * e, fy + (ty - fy) * e); }, function(){
              if (!T || T.gen !== g) return;
              tourPtr(tx, ty);
              if (T.el.ptr.animate) T.el.ptr.animate([{transform: 'scale(1)'}, {transform: 'scale(.82)'}, {transform: 'scale(1)'}], {duration: 240, easing: 'ease-out'});
            });
          }
          tourLater(then, 1900);
        }).catch(function(){});
      };
      const added = function(which, then){
        tlog('add: ' + which + ' shown');
        tourPic(null); tourPtr(0, 0, false); plusOff();
        T.addFocus = 'tour-add-' + which;
        tourScene('add:' + which).then(function(){
          if (!T || T.gen !== g) return;
          if (touchBtn()) tourScroll(T.steps[T.i]);  // touch: the button was brought into view, the widget added may be out of it
          tourLater(then, 2600);
        });
      };
      const own = function(then, focus){  // the user's own layout back (the widget added taken away)
        T.addFocus = focus || null;
        if (T.scene && /^add:/.test(T.scene)) tourScene(null).then(function(){ if (T && T.gen === g) then(); }); else then();
      };
      const viaMenu = function(){
        tlog('add: via the menu (anchor ' + chartId + ')');
        if (!d.chart) return viaPlus();
        own(function(){
          if (!T || T.gen !== g) return;
          T.addFocus = chartId;
          if (touchBtn()) tourScroll(T.steps[T.i]);  // back from the button under the block
          tourPlace(true, false);
          const m = mplace(); if (!m) return viaPlus();
          tourPic(d.chart.plain, m.x, m.y, m.w, m.h); tourPtr(0, 0, false);
          tourLater(function(){
            const m2 = mplace() || m; tourPic(d.chart.lit, m2.x, m2.y, m2.w, m2.h);
            tourPtr(m2.x + (d.chart.entry[0] + d.chart.entry[2] / 2) * m2.s, m2.y + (d.chart.entry[1] + d.chart.entry[3] / 2) * m2.s);
            tourLater(function(){ gallery('chart', function(){ added('chart', viaPlus); }); }, 900);
          }, 650);
        });
      };
      const viaPlus = function(){
        tlog('add: via the + of the stat line');
        if (!d.stat) return tourLater(viaMenu, 0);
        const tb = touchBtn();
        if (tb){  // touch: no + at the end of a line, the "+ Add Widget" button under the block, lit and pulsing
          own(function(){
            if (!T || T.gen !== g) return;
            tourPic(null);
            tourScroll(T.steps[T.i]);  // under the block: often below the window
            tourLater(function(){
              tb.classList.add('ddp-pulse'); tlog('add: + Add Widget button lit');
              tourLater(function(){ tb.classList.remove('ddp-pulse'); gallery('stat', function(){ added('stat', viaMenu); }); }, 1400);
            }, 500);
          }, 'touchadd');
          return;
        }
        // the light goes straight to the end of the stat line (where the + shows), not back to the chart first
        own(function(){
          if (!T || T.gen !== g) return;
          tourPic(null); tourPtr(0, 0, false);
          tourLater(function(){
            const p = plusOn(); if (!p){ viaMenu(); return; }
            T.addFocus = 'plus';
            tourPtr(p.r.left + 15, p.r.top + 15);
            tourLater(function(){ gallery('stat', function(){ added('stat', viaMenu); }); }, 1100);
          }, 500);
        }, 'plus');
      };
      T.extra = area(); tourPlace(true, true);
      tourLater(viaMenu, 200);
    });
  }
  // for each period, the pointer on the chart's period label (650 ms), its list opens
  // (650 ms), the period lit under the mouse (900 ms), then the chart over that period, updated in place (2.2 s), a
  // tag on it with the period (_show_span_badge)
  function tourSpanDemo(){
    const card0 = tourSpanCard(); if (!card0) return;
    const id = card0.dataset.wid, g = T.gen;
    tourAsk('tour_span', {id: id}).then(function(list){
      if (!T || T.gen !== g || !list || !list.length) return;
      const chip = function(){ const c = S.root.querySelector('[data-wid="' + id + '"] .ddp-chip[title="Time Span"]'); return c ? c.getBoundingClientRect() : null; };
      const spot = function(m, c){
        const W = window.innerWidth, H = window.innerHeight, x = Math.max(8, Math.min(W - m.w - 8, c.left));
        const y = c.top - m.h - 2 >= 8 ? c.top - m.h - 2 : Math.min(H - m.h - 8, c.bottom + 2);
        return {x: x, y: y};
      };
      const c0 = chip(); if (c0){ const s = spot(list[0], c0); T.extra = {left: s.x, top: s.y, right: s.x + list[0].w, bottom: s.y + list[0].h}; tourPlace(true, true); }
      let k = 0;
      const one = function(){
        const m = list[k % list.length], c = chip(); if (!c) return;
        tourPic(null); tourPtr(c.left + c.width / 2, c.top + c.height / 2);
        tourLater(function(){
          const c2 = chip() || c, s = spot(m, c2); tourPic(m.plain, s.x, s.y, m.w, m.h);
          tourLater(function(){
            const c3 = chip() || c2, s3 = spot(m, c3);
            tourPic(m.lit, s3.x, s3.y, m.w, m.h);
            if (m.entry) tourPtr(s3.x + m.entry[0] + m.entry[2] / 2, s3.y + m.entry[1] + m.entry[3] / 2);
            tourLater(function(){
              tourPic(null); tourPtr(0, 0, false);
              tlog('span -> ' + m.value);
              tourScene('span:' + m.value).then(function(){ if (!T || T.gen !== g) return; tourBadge(m.badge); k++; tourLater(one, 2200); });
            }, 900);
          }, 650);
        }, 650);
      };
      tourLater(one, 200);
    }).catch(function(){});
  }
  function tourBadge(text){
    if (T.badge){ T.badge.remove(); T.badge = null; }
    if (!text) return;
    const b = document.createElement('div'); b.className = 'ddp-tour-badge'; b.textContent = text;
    T.el.ov.insertBefore(b, T.el.card); T.badge = b;
    const pos = function(){ if (!T || T.badge !== b) return; const h = T.el.hole.getBoundingClientRect(); b.style.left = Math.round(h.left + 6) + 'px'; b.style.top = Math.round(Math.max(4, h.top - b.offsetHeight - 6)) + 'px'; requestAnimationFrame(pos); };
    pos();
  }
  function tourStop(){
    if (!T) return;
    T.timers.forEach(clearTimeout); T.timers = [];
    T.extra = null; T.addFocus = null;
    tourPic(null); tourPtr(0, 0, false);
    tourClearGhosts();
    if (T.gapUndo){ T.gapUndo(); T.gapUndo = null; }
    if (T.badge){ T.badge.remove(); T.badge = null; }
    if (T.zoomed){ T.zoomed = null; tourResetZoom(); }
    if (marks){ marks.plus.style.display = 'none'; marks.grip.style.display = 'none'; marks.plus.classList.remove('ddp-pulse'); marks.grip.classList.remove('ddp-pulse'); }
    if (S){ const tb = S.root.querySelector('.ddp-touch-add.ddp-pulse'); if (tb) tb.classList.remove('ddp-pulse'); }
  }
  function tourClose(){
    if (!T) return;
    tourStop(); tourThawNow();
    cancelAnimationFrame(T.raf);
    document.removeEventListener('keydown', T.key, true);
    if (T.watch) T.watch.disconnect();
    const ov = T.el.ov, gut = T.gutter || '', minH = T.minH0; T = null;
    setTimeout(function(){  // once the user's own layout is back
      document.documentElement.style.scrollbarGutter = gut;
      if (minH != null) document.documentElement.style.minHeight = minH;
    }, 400);
    ov.classList.add('out'); setTimeout(function(){ ov.remove(); }, 200);
    DDP.call('tour_end').catch(function(){});  // the user's own settings back (when a demo scene was shown)
  }
})();
