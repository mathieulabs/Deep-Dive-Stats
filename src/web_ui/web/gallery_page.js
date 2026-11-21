// The widget gallery (gallery_web.py, its content gallery_model.py): the charts, stat cards and the text widget by
// category. A click goes to Python (add one more, take one off, check or uncheck), which answers with the new state.
// The previews are the widgets themselves, drawn in their tiles by the pinned widgets' own modules once a tile comes
// into view: a chart at a widget's size (its text keeps its proportions), shrunk into its tile. Their data comes from
// Python in small batches ('gal_charts' off the UI thread, 'gal_stats'). The text comes translated: the page is data-nt.
(function(){
  'use strict';
  let U = null, root = null, ST = null, DRAW = [440, 269];
  let mainEl = null, navEl = null, headEl = null, footEl = null, searchEl = null, emptyEl = null, tailEl = null;
  const tiles = {}, secs = {};
  let words = [], filterMissing = false, ask = null;

  function fail(e){
    DD.log('gallery: ' + e);
    if (U) U.toast(String(e && e.message || e));
  }
  function call(cmd, args){
    return DD.call(cmd, args || {}).then(function(r){ if (r && r.sections) apply(r); return r; }).catch(fail);
  }
  const el = function(t, c, x){ return U.el(t, c, x); };

  // ---- a tooltip a moment after the mouse stops on a tile or a button (the help bubble of the settings) ----
  let tipEl = null, tipTimer = 0;
  function hideTip(){ clearTimeout(tipTimer); if (tipEl){ tipEl.remove(); tipEl = null; } }
  function hoverTip(node, content){
    node.addEventListener('mouseenter', function(){
      hideTip();
      tipTimer = setTimeout(function(){
        const parts = content();
        if (!parts || !parts.length) return;
        tipEl = el('div', 'dd-helptip dds-helptip dg-tip');
        parts.forEach(function(p, i){
          if (!p) return;
          tipEl.appendChild(el('div', i && parts[0] ? 'dg-tip-act' : null, p));
        });
        document.body.appendChild(tipEl);
        const r = node.getBoundingClientRect(), w = tipEl.offsetWidth, h = tipEl.offsetHeight;
        let top = r.bottom + 6;
        if (top + h > window.innerHeight - 8) top = Math.max(8, r.top - h - 6);
        tipEl.style.left = Math.max(8, Math.min(r.left, window.innerWidth - w - 8)) + 'px';
        tipEl.style.top = top + 'px';
      }, 450);
    });
    node.addEventListener('mouseleave', hideTip);
    node.addEventListener('mousedown', hideTip);
  }
  document.addEventListener('wheel', hideTip, true);

  // ---- a tile ----
  const CHECK = 'M3.4 6.3l1.8 1.8 3.5-3.9';
  function svg(d, sw){
    const ns = 'http://www.w3.org/2000/svg', s = document.createElementNS(ns, 'svg'), p = document.createElementNS(ns, 'path');
    s.setAttribute('width', '12'); s.setAttribute('height', '12'); s.setAttribute('viewBox', '0 0 12 12');
    p.setAttribute('d', d); p.setAttribute('fill', 'none'); p.setAttribute('stroke', 'currentColor');
    p.setAttribute('stroke-width', String(sw || 1.6)); p.setAttribute('stroke-linecap', 'round'); p.setAttribute('stroke-linejoin', 'round');
    s.appendChild(p);
    return s;
  }
  // Charts that support switching between Bars and Pie views right inside the gallery preview
  const PIE_DUAL = {card_counts: 'pie', lapse_distribution: 'bars', review_distribution: 'bars', learning_steps: 'bars',
    time_distribution: 'bars', interval_load: 'bars', review_intervals: 'bars', interval_history: 'bars',
    stability: 'bars', stability_history: 'bars'};
  function syncVsw(x){
    if (!x.vsw) return;
    x.vsw.querySelectorAll('button').forEach(function(b){ b.classList.toggle('on', b.dataset.v === x.view); });
  }
  function scaleTile(t){
    if (DD.isTouch && DD.isTouch() && window.innerWidth <= 720 && (t.family === 'chart' || t.family === 'text') && t.w > 0){
      const fullW = Math.max(t.w, Math.floor(window.innerWidth - 32)), r = fullW / t.w;
      return Object.assign({}, t, {w: fullW, h: Math.round(t.h * r), pw: Math.round((t.pw || t.w) * r), ph: Math.round((t.ph || t.h) * r)});
    }
    return t;
  }
  function tileEl(t){
    t = scaleTile(t);
    const d = el('div', 'dg-tile dg-f-' + t.family);
    d.dataset.id = t.id;
    const pic = el('div', 'dg-pic');
    pic.style.width = t.w + 'px'; pic.style.height = t.h + 'px';
    if (t.family === 'stat') pic.style.borderRadius = (ST.stat_radius || 8) + 'px';
    d.appendChild(pic);
    const mark = el('span', 'dg-mark');
    const minus = el('button', 'dg-minus');
    minus.appendChild(svg('M3.2 6h5.6', 1.8));
    minus.onclick = function(e){ e.stopPropagation(); hideTip(); call('gal_minus', {id: t.id}); };
    let vsw = null;
    if (t.family === 'chart' && PIE_DUAL[t.type]){
      vsw = el('div', 'dg-vsw');
      const order = t.type === 'card_counts' ? [['pie', 'Pie'], ['bars', 'Bars']] : [['bars', 'Bars'], ['pie', 'Pie']];
      order.forEach(function(p){
        const b = el('button', '', DD.t ? DD.t(p[1]) : p[1]);
        b.type = 'button'; b.dataset.v = p[0];
        b.onclick = function(e){
          e.stopPropagation();
          if (x.view === p[0]) return;
          x.view = p[0];
          syncVsw(x);
          if (x.chartIt){
            try { if (x.inst && x.inst.destroy) x.inst.destroy(); } catch (err) {}
            x.inst = null;
            if (x.live){ x.live.remove(); x.live = null; }
            mountChart(x, x.chartIt);
          }
        };
        vsw.appendChild(b);
      });
    }
    if (t.show_name){
      if (vsw){
        const row = el('div', 'dg-name dg-name-row');
        row.appendChild(el('span', 'dg-ntxt', t.name));
        row.appendChild(vsw);
        d.appendChild(row);
      } else d.appendChild(el('div', 'dg-name', t.name));
    }
    d.onclick = function(){ hideTip(); pick(x.t, x.vsw ? x.view : null); };
    // My Widgets: a saved widget's right click renames or deletes it (asked in Python)
    if (t.saved) d.addEventListener('contextmenu', function(e){
      e.preventDefault(); hideTip();
      if (!DD.webMenu) return;
      DD.webMenu({x: e.clientX, y: e.clientY}, [['rename', DD.t('Rename...'), null, 'pencil'], ['delete', DD.t('Delete'), null, 'trash']], function(v){
        call(v === 'rename' ? 'gal_rename' : 'gal_delete', {id: x.t.id});
      });
    });
    const x = {el: d, pic: pic, mark: mark, minus: minus, vsw: vsw, view: PIE_DUAL[t.type] || null, chartIt: null, t: t, live: null, inst: null, state: 'none'};
    syncVsw(x);
    tiles[t.id] = x;
    hoverTip(d, function(){ return x.t.tip; });
    showPic(x);
    update(x, t);
    if (io && !t.text) io.observe(d);
    return d;
  }
  // the tile's picture: the text widget's sentence, else the loading shimmer until its preview is drawn over it
  function showPic(x){
    const t = x.t, pic = x.pic;
    while (pic.firstChild) pic.removeChild(pic.firstChild);
    x.el.classList.remove('has-pic');
    if (t.text) pic.appendChild(el('div', 'dg-text', t.text));
    else pic.appendChild(el('div', 'dg-skel'));
    pic.appendChild(x.mark);
    pic.appendChild(x.minus);
  }
  // its check mark (checked or not: the Deep Dive's), or how many are on the main screen, and its "−"
  function update(x, t){
    t = scaleTile(t);
    x.t = t;
    const m = x.mark;
    while (m.firstChild) m.removeChild(m.firstChild);
    m.className = 'dg-mark';
    if (t.marks && !t.pinned) m.classList.add('empty');
    else if (!t.marks && t.pinned && t.count >= 2){ m.classList.add('count'); m.textContent = t.count < 100 ? String(t.count) : '99+'; }
    else if (t.pinned){ m.classList.add('check'); if (t.marks) m.classList.add('accent'); m.appendChild(svg(CHECK, 1.6)); }
    else m.classList.add('none');
    x.el.classList.toggle('can-minus', !t.marks && t.count > 0);
    x.el.classList.toggle('pinned', !!t.pinned);
  }

  // ---- the previews ----
  // a tile in view (or nearly) asks for its data; the charts' come in batches, one batch at a time
  const io = window.IntersectionObserver ? new IntersectionObserver(function(es){
    es.forEach(function(en){
      const x = tiles[en.target.dataset.id];
      if (!x) return;
      x.seen = en.isIntersecting;
      if (en.isIntersecting && x.state === 'none') want(x);
    });
  }, {rootMargin: '600px 0px'}) : null;
  let gen = 0;  // the period or decks changed: the answers asked before are dropped
  const queue = {chart: [], stat: []}, busy = {chart: false, stat: false};
  const BATCH = {chart: 3, stat: 8};
  function want(x){
    const kind = x.t.family === 'chart' ? 'chart' : 'stat';
    x.state = 'queued';
    queue[kind].push(x.t.id);
    pump(kind);
  }
  function pump(kind){
    if (busy[kind]) return;
    // a tile scrolled away before its turn waits for the next time it is seen
    const ids = [];
    while (queue[kind].length && ids.length < BATCH[kind]){
      const id = queue[kind].shift(), x = tiles[id];
      if (!x || x.state !== 'queued') continue;
      if (!x.seen){ x.state = 'none'; continue; }
      x.state = 'asked';
      ids.push(id);
    }
    if (!ids.length) return;
    busy[kind] = true;
    const g = gen;
    DD.call(kind === 'chart' ? 'gal_charts' : 'gal_stats', {ids: ids}).then(function(r){
      if (g !== gen) return;
      ids.forEach(function(id){
        const x = tiles[id];
        if (!x || x.state !== 'asked') return;
        if (r && r[id]){ x.state = 'shown'; if (kind === 'chart') mountChart(x, r[id]); else mountStat(x, r[id]); }
        else { x.state = 'failed'; x.el.classList.add('dg-failed'); }  // (logged in Python): the shimmer stands still
      });
    }).catch(function(e){ DD.log('gallery previews: ' + e); }).then(function(){
      busy[kind] = false;
      pump(kind);
    });
  }
  function liveBox(x){
    const t = x.t, live = el('div', 'dg-live');
    if (t.family === 'chart'){
      live.style.left = Math.round((t.w - t.pw) / 2) + 'px';
      live.style.top = Math.round((t.h - t.ph) / 2) + 'px';
      live.style.width = t.pw + 'px';
      live.style.height = t.ph + 'px';
    }
    x.pic.insertBefore(live, x.mark);
    return live;
  }
  function shown(x, live){
    const sk = x.pic.querySelector('.dg-skel');
    x.live = live;
    x.el.classList.add('has-pic');
    if (DD.anim && DD.anim.on === false){ live.classList.add('in'); if (sk) sk.remove(); return; }
    // the shimmer stops at once and fades out as the preview fades in: it swept on under the cards (see-through)
    // for a while after they were shown
    if (sk) sk.classList.add('out');
    requestAnimationFrame(function(){ live.classList.add('in'); });
    if (sk) setTimeout(function(){ sk.remove(); }, Math.round(180 * (DD.speed ? DD.speed() : 1)) + 60);
  }
  function mountChart(x, it){
    const mod = DD.charts && DD.charts[it.type];
    if (!mod){ DD.log('gallery: no web chart for ' + it.type); x.state = 'failed'; return; }
    x.chartIt = it;
    const data = Object.assign({}, it.data || {}), opts = Object.assign({}, it.options || {});
    if (x.vsw && x.view){
      if (it.type === 'card_counts') data.bars_view = x.view === 'bars';
      else opts.pie_view = x.view === 'pie';
    }
    const live = liveBox(x), k = x.t.pw / DRAW[0];
    const stage = el('div', 'dg-stage ddp');
    stage.style.width = DRAW[0] + 'px'; stage.style.height = DRAW[1] + 'px';
    stage.style.transform = 'scale(' + k + ')';
    stage.dataset.ddScale = String(k);
    live.appendChild(stage);
    const card = el('div', 'dd-card dd-fixed ddp-card ddg-card');
    card.dataset.type = it.type;
    card.innerHTML = (DD.headHtml ? DD.headHtml(it.type) : '<div class="dd-head"></div>') + '<div class="dd-body"></div>';
    const head = card.querySelector('.dd-head');
    if (head) head.style.display = 'none';  // the tile shows the name under the picture
    stage.appendChild(card);
    DD._mountEl = null;
    try {
      x.inst = mod.mount(card.querySelector('.dd-body'), {data: data, options: opts, animate: false, head: head, type: it.type});
    } catch (e){ DD.log('gallery ' + it.type + ': ' + (e && e.message || e)); }
    shown(x, live);
  }
  function mountStat(x, spec){
    const live = liveBox(x), box = el('div', 'dd-sc-host ddp');
    live.appendChild(box);
    try {
      x.inst = DD.stats.mount(box, spec, DD.theme, {});
      box.querySelectorAll('.dd-sc').forEach(function(d){ d.style.width = x.t.pw + 'px'; d.style.height = x.t.ph + 'px'; });
    } catch (e){ DD.log('gallery stat: ' + (e && e.message || e)); }
    shown(x, live);
  }
  function drop(x){
    try { if (x.inst && x.inst.destroy) x.inst.destroy(); } catch (e) {}
    x.inst = null;
    if (x.live){ x.live.remove(); x.live = null; }
    x.state = 'none';
    x.el.classList.remove('dg-failed');
    if (!x.t.text) showPic(x);
  }
  // drawn again with the new period or decks: the tiles in view first
  function redo(){
    gen++;
    queue.chart.length = 0; queue.stat.length = 0;
    Object.keys(tiles).forEach(function(id){
      const x = tiles[id];
      if (x.t.text) return;
      drop(x);
      if (x.seen) want(x);
    });
  }

  // ---- what is shown: the search, "Not added" ----
  function filter(){
    let any = false;
    (ST.sections || []).forEach(function(s){
      let n = 0;
      s.tiles.forEach(function(t){
        const x = tiles[t.id];
        const show = words.every(function(w){ return x.t.search.indexOf(w) >= 0; }) && !(filterMissing && x.t.pinned);
        x.el.style.display = show ? '' : 'none';
        if (show) n++;
      });
      const sc = secs[s.key];
      const hinted = !!sc.hint && !s.tiles.length && !words.length;
      if (sc.hint) sc.hint.style.display = hinted ? '' : 'none';
      sc.sec.style.display = n || hinted ? '' : 'none';
      sc.head.textContent = hinted ? s.head : s.head + '  ·  ' + n;
      sc.nav.disabled = !n && !hinted;
      sc.count.textContent = n ? String(n) : '';
      sc.shown = n > 0 || hinted;
      any = any || n > 0;
    });
    emptyEl.textContent = filterMissing && !words.length ? ST.all_added : ST.empty;
    emptyEl.style.display = any ? 'none' : '';
    fitTail();
  }
  // room under the last category: each one can come to the top of the view (the list on the left marks that one)
  function fitTail(){
    const shownSecs = (ST.sections || []).filter(function(s){ return secs[s.key].shown; });
    let room = 0;
    if (shownSecs.length){
      const last = secs[shownSecs[shownSecs.length - 1].key].sec;
      room = Math.max(0, mainEl.clientHeight - last.offsetHeight - 12);
    }
    tailEl.style.height = room + 'px';
    follow();
  }
  function follow(){
    const y = mainEl.scrollTop + 12;
    let cur = null;
    (ST.sections || []).forEach(function(s){
      const sc = secs[s.key];
      if (sc.shown && sc.sec.offsetTop - mainEl.offsetTop <= y) cur = s.key;
    });
    if (cur === null){ const f = (ST.sections || []).find(function(s){ return secs[s.key].shown; }); cur = f ? f.key : null; }
    Object.keys(secs).forEach(function(k){ secs[k].nav.classList.toggle('on', k === cur); });
  }
  function scrollTo(key){
    const sc = secs[key];
    if (!sc || !sc.shown) return;
    mainEl.scrollTop = Math.max(0, sc.sec.offsetTop - mainEl.offsetTop - 4);
    follow();
  }
  // a tile picked; the text widget's sentence first written in the text editor (text_editor.js; cancelled: nothing)
  function pick(t, view){
    if (t.family !== 'text' || t.saved){ call('gal_pick', view ? {id: t.id, view: view} : {id: t.id}); return; }
    const save = ST.save_text ? {} : null;  // the editor's "Also keep in Add Widget as:" (its name, once added)
    DD.editText({title: ST.toggle ? 'Add Text' : 'Add Text Widget', ok: 'Add', save: save}).then(function(tpl){
      if (tpl == null) return;
      const a = {id: t.id, template: tpl};
      if (save && save.name) a.save_name = save.name;
      call('gal_pick', a);
    });
  }
  function addFirst(){
    if (!words.length) return;
    for (const s of ST.sections || []){
      for (const t of s.tiles){
        if (tiles[t.id].el.style.display !== 'none'){ pick(t); return; }
      }
    }
  }

  // ---- the window ----
  function build(){
    const app = el('div', 'dg-app');
    headEl = el('header', 'dg-head');
    const body = el('div', 'dg-body');
    navEl = el('nav', 'dg-nav');
    mainEl = el('main', 'dg-main');
    footEl = el('footer', 'dds-foot dg-foot');
    body.appendChild(navEl); body.appendChild(mainEl);
    app.appendChild(headEl); app.appendChild(body); app.appendChild(footEl);
    root.appendChild(app);

    let last = null;
    (ST.sections || []).forEach(function(s){
      if (last !== null && last !== s.family) navEl.appendChild(el('div', 'dg-rule'));
      if (s.family === 'stat' && last !== 'stat') navEl.appendChild(el('div', 'dg-group', ST.stat_group));
      last = s.family;
      const nav = el('button', 'dg-navbtn');
      nav.appendChild(el('span', 'dg-navname', s.title));
      const count = el('span', 'dg-navcount');
      nav.appendChild(count);
      nav.onclick = function(){ scrollTo(s.key); };
      navEl.appendChild(nav);
      const sec = el('section', 'dg-sec');
      const head = el('h3', 'dg-sechead');
      const grid = el('div', 'dg-grid dg-grid-' + s.family);
      sec.appendChild(head); sec.appendChild(grid);
      // (an empty category that says how to fill it: My Widgets)
      const hint = s.hint ? el('p', 'dg-sechint', s.hint) : null;
      if (hint) sec.appendChild(hint);
      mainEl.appendChild(sec);
      secs[s.key] = {sec: sec, head: head, nav: nav, count: count, shown: true, grid: grid, hint: hint};
    });
    emptyEl = el('div', 'dg-empty');
    mainEl.appendChild(emptyEl);
    tailEl = el('div', 'dg-tail');
    mainEl.appendChild(tailEl);
    mainEl.addEventListener('scroll', follow, {passive: true});
    window.addEventListener('resize', fitTail);
    renderHead();
    renderFoot();
  }
  // the tiles, once the view is at its place (the first ones asked are those seen)
  function fill(){
    (ST.sections || []).forEach(function(s){
      const grid = secs[s.key].grid;
      s.tiles.forEach(function(t){ grid.appendChild(tileEl(t)); });
    });
    filter();
  }
  function renderHead(){
    const typing = searchEl && document.activeElement === searchEl;
    while (headEl.firstChild) headEl.removeChild(headEl.firstChild);
    const titles = el('div', 'dg-titles');
    titles.appendChild(el('h1', 'dg-title', ST.title));
    if (ST.where) titles.appendChild(el('div', 'dg-where', ST.where));
    headEl.appendChild(titles);
    headEl.appendChild(U.seg(String(!!ST.missing), [['false', ST.seg[0]], ['true', ST.seg[1]]], function(v){
      filterMissing = v === 'true';
      ST.missing = filterMissing;
      renderHead();
      filter();
      call('gal_missing', {on: filterMissing});
    }));
    const sbox = el('label', 'dg-search');
    sbox.appendChild(svg('M5.2 1.8a3.4 3.4 0 1 0 0 6.8 3.4 3.4 0 0 0 0-6.8zM7.7 7.7l2.6 2.6', 1.4));
    if (!searchEl){
      searchEl = el('input', 'dds-input');
      searchEl.type = 'search';
      searchEl.placeholder = ST.search;
      searchEl.oninput = function(){
        words = searchEl.value.toLowerCase().split(/\s+/).filter(Boolean);
        filter();
        mainEl.scrollTop = 0;
        follow();
      };
      searchEl.onkeydown = function(e){ if (e.key === 'Enter'){ e.preventDefault(); addFirst(); } };
    }
    sbox.appendChild(searchEl);
    headEl.appendChild(sbox);
    if (typing) searchEl.focus();  // moving it in the page drops the focus
  }
  function chevronBtn(text, onclick, tip){
    const b = U.btn('', 'dg-pickbtn', onclick);
    b.appendChild(document.createTextNode(text));
    b.appendChild(svg('M3.2 4.7L6 7.5l2.8-2.8', 1.4));
    if (tip) hoverTip(b, function(){ return [tip]; });
    return b;
  }
  function renderFoot(){
    while (footEl.firstChild) footEl.removeChild(footEl.firstChild);
    const f = ST.foot || {};
    const left = el('div', 'dg-foot-left');
    footEl.appendChild(left);
    // the main screen's reset asks first, in the bar (it removes the widgets there)
    if (ask){
      const box = el('div', 'dg-ask');
      box.appendChild(el('span', 'dg-ask-text', ask.ask));
      box.appendChild(U.btn(ST.cancel_text || f.cancel, '', function(){ ask = null; renderFoot(); }));
      box.appendChild(U.btn(ask.ok, 'danger', function(){ ask = null; renderFoot(); call('gal_reset', {confirmed: true}); }));
      left.appendChild(box);
      return;
    }
    if (f.add){
      left.appendChild(el('span', 'dg-added', f.add.label));
      const sel = U.select(f.add.span, f.add.spans || [], function(v){ call('gal_span', {value: v}); });
      sel.classList.add('dg-span');
      if (f.add.span_tip) hoverTip(sel, function(){ return [f.add.span_tip]; });
      left.appendChild(sel);
      left.appendChild(chevronBtn(f.add.deck, function(){
        hideTip();
        if (!DD.pickDecks) return;
        DD.pickDecks({ids: f.add.deck_ids && f.add.deck_ids.length ? f.add.deck_ids : null}).then(function(r){
          if (r) call('gal_decks', {ids: r.ids});
        }).catch(fail);
      }, f.add.deck_tip));
    }
    if (f.reset){
      const b = U.btn('', 'dg-reset', function(){
        hideTip();
        DD.call('gal_reset', {}).then(function(r){
          if (r && r.ask){ ask = r; renderFoot(); }
        }).catch(fail);
      });
      b.appendChild(U.icon('reset'));
      b.appendChild(document.createTextNode(f.reset.text));
      if (f.reset.tip) hoverTip(b, function(){ return [f.reset.tip]; });
      left.appendChild(b);
    }
    footEl.appendChild(U.btn(f.cancel, '', function(){ call('gal_cancel'); }));
    if (f.done) footEl.appendChild(U.btn(f.done, 'primary', function(){ call('gal_done'); }));
  }

  // ---- from Python ----
  function apply(st){
    if (!st || !mainEl) return;
    const viewWas = ST && ST.view;
    ST = st;
    const keep = {}, keepSec = {};
    (st.sections || []).forEach(function(s){
      keepSec[s.key] = true;
      s.tiles.forEach(function(t){
        const x = tiles[t.id];
        keep[t.id] = true;
        // a text saved as it was added: its tile comes (after the Text tile)
        if (!x){ if (secs[s.key]) secs[s.key].grid.appendChild(tileEl(t)); return; }
        const textWas = x.t.text, nameWas = x.t.name;
        update(x, t);
        if (t.text !== textWas) showPic(x);
        if (t.name !== nameWas){ const n = x.el.querySelector('.dg-ntxt') || x.el.querySelector('.dg-name'); if (n) n.textContent = t.name; }
      });
    });
    // a saved widget deleted (My Widgets): its tile goes, and its category when it was the last one
    Object.keys(tiles).forEach(function(id){
      if (keep[id]) return;
      const x = tiles[id];
      try { if (x.inst && x.inst.destroy) x.inst.destroy(); } catch (e) {}
      if (io) io.unobserve(x.el);
      x.el.remove(); delete tiles[id];
    });
    Object.keys(secs).forEach(function(k){
      if (keepSec[k]) return;
      const sc = secs[k];
      sc.sec.remove(); sc.nav.remove();
      const rule = navEl.querySelector('.dg-rule');
      if (rule && navEl.firstChild === rule) rule.remove();  // (the line under it, the first thing left)
      delete secs[k];
    });
    filterMissing = !!st.missing;
    renderHead();
    renderFoot();
    filter();
    hideTip();
    if (viewWas !== undefined && st.view !== viewWas) redo();
  }
  DD.on('gal_state', apply);

  // ---- the guided tour's picture of the gallery (tour.py: this page kept off screen) ----
  // DD.galleryTour(id, where): the tile lit as under the mouse, in view, its preview asked, and the line under the
  // title saying where the widget goes. Called again until ready: {ready, x, y} (the tile's center in the page), or
  // null while the page is not built. DD.galleryTour(null): nothing lit.
  DD.galleryTour = function(id, where){
    if (!ST || !mainEl) return null;
    Object.keys(tiles).forEach(function(k){ tiles[k].el.classList.toggle('dg-hot', id != null && k === String(id)); });
    if (id == null) return true;
    const x = tiles[String(id)];
    if (!x) return {missing: true};
    if (document.activeElement && document.activeElement.blur) document.activeElement.blur();
    if (where != null && ST.where !== where){ ST.where = where; renderHead(); }
    if (!x.el.offsetParent && (filterMissing || words.length)){
      filterMissing = false; words = []; if (searchEl) searchEl.value = ''; filter();
    }
    const m = mainEl.getBoundingClientRect(), r = x.el.getBoundingClientRect();  // the tile in view, 40 px above and below
    if (r.top < m.top + 40) mainEl.scrollTop -= m.top + 40 - r.top;
    else if (r.bottom > m.bottom - 40) mainEl.scrollTop += Math.min(r.bottom - (m.bottom - 40), r.top - (m.top + 40));
    x.seen = true;
    if (x.state === 'none') want(x);
    const b = x.el.getBoundingClientRect();
    const fade = DD.anim && DD.anim.on === false ? 0 : Math.round(180 * (DD.speed ? DD.speed() : 1));
    return {ready: !!x.t.text || x.state === 'shown' || x.state === 'failed',
            x: Math.round(b.left + b.width / 2), y: Math.round(b.top + b.height / 2),
            vw: window.innerWidth || 0, vh: window.innerHeight || 0, fade: fade};
  };

  DD.galleryPageBoot = function(){
    U = DD.settingsUI;
    root = document.getElementById('dds-root');
    root.setAttribute('data-nt', '');
    DD.call('init').then(function(d){
      if (d.i18n) DD.setI18n(d.i18n, root);
      U.setTheme(d.theme);
      DD.theme = d.theme;
      if (d.anim && DD.setAnim) DD.setAnim(d.anim);
      if (d.chart_draw) DRAW = d.chart_draw;
      if (DD.go) DD.go();  // the previews draw at once (no opening animation: they are pictures)
      DD.settings = Object.assign({bin_scale: 100}, DD.settings || {});  // as the pinned page's boot
      const still = !!(DD.anim && DD.anim.on === false);
      // the loading shimmer stands still with the animations off; a preview fades in, at the user's speed
      root.classList.toggle('dg-still', still);
      root.style.setProperty('--dg-fade', still ? '0s' : (0.18 * (DD.speed ? DD.speed() : 1)).toFixed(3) + 's');
      ST = d.state;
      filterMissing = !!ST.missing;
      const dark = !!d.theme.is_dark;
      root.style.setProperty('--dg-card', dark ? 'rgba(255,255,255,0.039)' : 'rgba(0,0,0,0.027)');
      root.style.setProperty('--dg-line', dark ? 'rgba(255,255,255,0.157)' : 'rgba(0,0,0,0.157)');
      build();
      fill();
      if (d.family){
        const s = (ST.sections || []).find(function(x){ return x.family === d.family; });
        if (s) scrollTo(s.key);
      }
      if (searchEl) searchEl.focus();
    }).catch(function(e){ DD.log('gallery: boot failed ' + e); root.textContent = String(e); });
  };
})();
