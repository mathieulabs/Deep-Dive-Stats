// Core of the web pages: Python bridge, theme, chart registry, frame scheduler.
(function(){
  'use strict';
  const DD = window.DD = window.DD || {};
  // Settings > General > Animations (DD.setAnim): "No Animations" (for this page) keeps every chart change instant,
  // whatever code sets DD._noAnim around an update and puts it back after
  let noAnim = false;
  Object.defineProperty(DD, '_noAnim', {configurable: true, get: function(){ return noAnim || !!DD.animOff; }, set: function(v){ noAnim = !!v; }});
  DD.anim = {on: true, appear: true, zoom: true, style: 'morph', speed: 1};
  DD.setAnim = function(a){
    DD.anim = Object.assign({on: true, appear: true, zoom: true, style: 'morph', speed: 1}, a || {});
    DD.animOff = !DD.anim.on;
    DD.noZoomAnim = !DD.anim.zoom || !DD.anim.on;
  };
  // a chart's new data as the transition setting wants it: "morph" (its own animation), "none" (at once), "fade"
  // (drawn at once under a picture of the old chart fading out: much lighter on a slow computer). fade: a fade in any
  // case (unless "none"), for a change a morph cannot show (a chart's series added or taken off)
  DD.applyUpdate = function(el, fn, fade){
    if (fade && DD._noAnim){ fn(); return; }  // (an update its caller wants at once)
    const s0 = DD.anim.on ? DD.anim.style : 'none', style = fade && s0 !== 'none' ? 'fade' : s0;
    if (style === 'none'){ const p = noAnim; noAnim = true; try { fn(); } finally { noAnim = p; } return; }
    if (style !== 'fade' || !el || !document.body.animate){ fn(); return; }
    const shots = [];
    el.querySelectorAll('canvas').forEach(function(c){
      const par = c.parentNode; if (!par || !c.width || !c.height || !c.offsetWidth) return;
      const cp = document.createElement('canvas'); cp.width = c.width; cp.height = c.height;
      try { cp.getContext('2d').drawImage(c, 0, 0); } catch (e) { return; }
      const rc = c.getBoundingClientRect(), rp = par.getBoundingClientRect();
      if (getComputedStyle(par).position === 'static') par.style.position = 'relative';
      cp.style.cssText = 'position:absolute;left:' + (rc.left - rp.left) + 'px;top:' + (rc.top - rp.top) + 'px;width:' + rc.width + 'px;height:' + rc.height + 'px;pointer-events:none;z-index:3';
      par.appendChild(cp); shots.push(cp);
    });
    const p = noAnim; noAnim = true; try { fn(); } finally { noAnim = p; }
    const ms = 320 * (DD.calm ? DD.calm() : 1);
    shots.forEach(function(cp){ cp.animate([{opacity: 1}, {opacity: 0}], {duration: ms, easing: 'ease-in-out', fill: 'forwards'}).finished.then(function(){ cp.remove(); }, function(){ cp.remove(); }); });
  };
  DD.charts = {};
  DD.settings = {};
  DD.registerChart = function(type, def){ DD.charts[type] = painted(type, fsrsGuard(def)); };
  // A chart whose colours come with its data (Week by Hour, SxR, B-W Matrix, First Answer Retention): a new theme
  // brings them (DD.theme.paint[type], window.py _push_theme) and the chart repaints at once with its last data, not
  // animated, instead of when its data is read again a moment later
  function painted(type, def){
    if (!def || typeof def.mount !== 'function') return def;
    const mount = def.mount;
    return Object.assign({}, def, {mount: function(el, ctx){
      const inst = mount.call(def, el, ctx);
      if (!inst || typeof inst.update !== 'function') return inst;
      let last = ctx && ctx.data;
      const up = inst.update, theme = inst.setTheme;
      inst.update = function(d){ last = d; return up.apply(inst, arguments); };
      inst.setTheme = function(){
        const r = theme ? theme.apply(inst, arguments) : undefined;
        const c = DD.theme && DD.theme.paint && DD.theme.paint[type];
        if (c && last && typeof last === 'object' && !last.error && !last._empty){
          const p = DD._noAnim; DD._noAnim = true;
          try { inst.update(Object.assign({}, last, c)); } finally { DD._noAnim = p; }
        }
        return r;
      };
      return inst;
    }});
  }
  // A chart whose recall needs the formulas of an FSRS version this add-on does not know gets {fsrs_unsupported}
  // from Python (providers.fetch): a note stands in its card instead of numbers that would be wrong. The note's
  // instance mounts the real chart if supported data comes later, then hands every call on to it.
  const FSRS_NOTE = 'Not available with this version of FSRS: an update of the add-on is needed.';
  function fsrsOff(d){ return !!(d && d.fsrs_unsupported); }
  function fsrsNote(el){
    el.innerHTML = '';
    const n = document.createElement('div'); n.className = 'dd-fsrs-note';
    n.textContent = DD.t ? DD.t(FSRS_NOTE) : FSRS_NOTE;
    el.appendChild(n);
  }
  function fsrsGuard(def){
    if (!def || typeof def.mount !== 'function') return def;
    const mount = def.mount;
    return Object.assign({}, def, {mount: function(el, ctx){
      ctx = ctx || {};
      let cur = null;
      const real = function(inst){
        const up = inst.update;  // supported until now: the note if a later answer is not
        if (typeof up === 'function') inst.update = function(d){
          if (!fsrsOff(d)) return up.apply(inst, arguments);
          try { if (inst.destroy) inst.destroy(); } catch (e) {}
          fsrsNote(el);
          ['update', 'setOptions', 'setTheme', 'onSize'].forEach(function(k){ if (inst[k]) inst[k] = function(){}; });
        };
        return inst;
      };
      if (!fsrsOff(ctx.data)) return real(mount.call(def, el, ctx));
      fsrsNote(el);
      let opts = Object.assign({}, ctx.options || {});
      const note = {
        update: function(d, mode){
          if (cur) return cur.update(d, mode);
          if (fsrsOff(d)) return;
          el.innerHTML = '';
          cur = real(mount.call(def, el, Object.assign({}, ctx, {data: d, options: opts, animate: false})));
        },
        setOptions: function(o){ if (cur && cur.setOptions) return cur.setOptions(o); Object.assign(opts, o || {}); },
        setTheme: function(){ if (cur && cur.setTheme) return cur.setTheme.apply(cur, arguments); },
        destroy: function(){ if (cur && cur.destroy) return cur.destroy(); el.innerHTML = ''; },
      };
      // the other methods (zoom, natural, ...) are the real chart's once it is there, absent before
      return new Proxy(note, {
        get: function(t, k){
          if (k in t) return t[k];
          const v = cur ? cur[k] : undefined;
          return typeof v === 'function' ? v.bind(cur) : v;
        },
        has: function(t, k){ return k in t || !!(cur && k in cur); },
      });
    }});
  }
  // A chart's place while its data loads (Deep Dive reads most of them after opening): a faint light passing across
  // its card, no shape (a sketch of bars or of a frame stood where a pie came, its axes elsewhere). With animations
  // off, three still dots. When the chart comes, its light stops where it is and fades in 220 ms (app.js: removed at
  // once, it vanished mid-card)
  DD.loadingPlaceholder = function(){
    if (!(DD.anim && DD.anim.on)) return '<div class="dd-loading dd-loading-still" aria-hidden="true"><i></i><i></i><i></i></div>';
    const sp = DD.speed ? DD.speed() : 1;
    return '<div class="dd-loading" aria-hidden="true" style="--dd-shimmer:' + (1.8 * sp).toFixed(2) + 's"></div>';
  };

  // ---- Python bridge ----
  let seq = 0;
  const waiting = {}, listeners = {};
  // Anki's bridge (QWebChannel) is not up for the first tens of ms of a page: pycmd does not exist yet, and what was
  // sent then threw and was lost (Deep Dive's first calls, the charts' chart_help: never answered, a "?" kept on
  // charts with no text, and the log line of the failure lost the same way). It waits here and goes out, in order,
  // once pycmd is there (the pinned page greets Python for the same reason, pinned.js)
  const early = []; let earlyT = 0;
  DD._send = function(msg){
    if (!early.length && typeof window.pycmd === 'function'){ window.pycmd(msg); return; }
    early.push(msg);
    if (!earlyT) earlyT = setInterval(function(){
      if (typeof window.pycmd !== 'function') return;
      clearInterval(earlyT); earlyT = 0;
      early.splice(0).forEach(function(m){ try { window.pycmd(m); } catch (e) {} });
    }, 10);
  };
  DD.call = function(cmd, args){
    return new Promise(function(resolve, reject){
      const id = ++seq;
      waiting[id] = {resolve: resolve, reject: reject, cmd: cmd, t: performance.now()};
      if (DD._rz) DD._rz.calls.push(cmd);
      DD._send('dd:' + JSON.stringify({id: id, cmd: cmd, args: args || {}}));
    });
  };
  // dev trace (RESIZETRACE): the answers still awaited from Python, by command and age
  DD._pending = function(){ const now = performance.now(); return Object.keys(waiting).map(function(k){ return waiting[k].cmd + ' ' + Math.round(now - waiting[k].t) + 'ms'; }); };
  DD.__resolve = function(id, ok, payload){
    const w = waiting[id];
    if (!w) return;
    if (DD._rz) DD._rz.answers.push(w.cmd + ' ' + Math.round(performance.now() - w.t) + 'ms');
    if (DD._perfNotes && DD._perfNotes.length < 20) DD._perfNotes.push('answer ' + w.cmd);
    delete waiting[id];
    if (ok) w.resolve(payload); else w.reject(new Error(payload));
    // dev trace: the page's time on a Python answer (its callbacks, run right after this), when it is long
    if (DD.dev && window.MessageChannel){
      const t = performance.now(), mc = new MessageChannel();
      mc.port1.onmessage = function(){ const ms = performance.now() - t; if (ms >= 8) DD.trace('PERFTRACE answer ' + w.cmd + ' handled=' + ms.toFixed(1) + 'ms'); mc.port1.close(); };
      mc.port2.postMessage(0);
    }
  };
  // The header stats & adaptive action pills: stats shrink to icon -> hidden on narrow cards, and action pills
  // tighten spacing before collapsing into a single compact menu button instead of truncating to "..."
  DD.watchStat = function(head){
    const stat = head && head.querySelector('.dd-stat');
    if (!stat || stat.__watched) return;
    stat.__watched = true;
    const card = head.closest && head.closest('.dd-card');
    const pc = head.querySelector('.dd-pills:not(.dd-ownopt)');
    const SLIDERS_SVG = '<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"><path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M2 14h4M10 8h4M18 16h4"/></svg>';
    const CHEV_SVG = '<svg class="dd-pill-chev" width="8" height="6" viewBox="0 0 8 6"><path d="M1 1.5L4 4.5L7 1.5" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/></svg>';
    let trig = null, openMenu = null;
    if (pc && !pc.classList.contains('dd-hm-nav')){
      trig = document.createElement('button');
      trig.type = 'button';
      trig.className = 'dd-pill dd-pills-trig';
      trig.style.display = 'none';
      pc.parentNode.insertBefore(trig, pc.nextSibling);
    }
    function getPills(){
      if (!pc || pc.classList.contains('dd-hm-nav')) return [];
      return Array.prototype.slice.call(pc.querySelectorAll('.dd-pill'));
    }
    function pillLabel(b){
      const t = (b.textContent || '').replace(/\s+/g, ' ').trim();
      return t || b.title || b.getAttribute('aria-label') || 'Options';
    }
    function isDrop(b){
      return !!(b.querySelector('.dd-pill-chev') || b.classList.contains('dd-pill-ico'));
    }
    function toHex(c){
      if (!c) return null;
      if (/^#[0-9a-f]{3,8}$/i.test(c)) return c;
      const m = c.match(/rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/i);
      if (!m) return null;
      return '#' + [1, 2, 3].map(function(i){ return ('0' + Number(m[i]).toString(16)).slice(-2); }).join('');
    }
    function syncTrig(pills){
      if (!trig) return;
      // a chart's view (Pie / Bars) is always one lit: not an option turned on
      const onCount = pills.filter(function(b){ return b.classList.contains('on') && !b.classList.contains('dd-pview'); }).length;
      trig.classList.toggle('on', onCount > 0);
      // written once: a fit between press and release must not replace the icon under the mouse, or the click
      // loses its target
      if (!trig.firstChild) trig.innerHTML = SLIDERS_SVG + CHEV_SVG;
      trig.title = pills.map(function(b){ return pillLabel(b) + (b.classList.contains('on') ? ' \u2713' : ''); }).join(' \u00b7 ');
    }
    function getHiddenPills(){
      return getPills().filter(function(b){ return b.classList.contains('dd-pill-ovf') || head.classList.contains('dd-pills-menu'); });
    }
    // a pill of the menu picked: its own click (a pill with a menu of its own opens it under the "..." button)
    function pickPill(idx){
      const live = getPills()[idx];
      if (!live) return;
      if (window.DDP && card && card.dataset && card.dataset.wid) window.DDP.curWid = card.dataset.wid;
      if (isDrop(live)){
        openMenu = null;
        const prevRect = live.getBoundingClientRect;
        live.getBoundingClientRect = function(){ return trig.getBoundingClientRect(); };
        try { live.click(); } finally {
          if (prevRect === Element.prototype.getBoundingClientRect) delete live.getBoundingClientRect;
          else live.getBoundingClientRect = prevRect;
        }
      } else {
        live.click();
        syncTrig(getHiddenPills());
      }
    }
    if (trig){
      trig.addEventListener('click', function(e){
        e.stopPropagation();
        if (openMenu && openMenu.isConnected){ openMenu.remove(); openMenu = null; return; }
        const allPills = getPills();
        const hidden = getHiddenPills();
        const shown = hidden.length ? hidden : allPills;
        if (!shown.length || !DD.menu) return;
        const items = shown.map(function(b){
          const i = allPills.indexOf(b);
          const lbl = pillLabel(b);
          const col = toHex(b.style.color);
          if (isDrop(b)) return [i, lbl + (b.querySelector('.dd-pill-chev') ? ' \u25be' : ''), null, col, false];
          return [i, lbl, b.classList.contains('on'), col, true];
        });
        // the chart's options icon hidden too: one menu, these pills first then its options (its own menu, built
        // by app.js cardMenu / pinned.js ownMenu, which put head._ddPre's entries first), not a menu in a menu
        const ownBtn = head.classList.contains('dd-pills-ovf') ? head.querySelector('.dd-ownopt .dd-pill') : null;
        if (ownBtn){
          head._ddPre = {
            items: items.map(function(it){ return ['ovf:' + it[0]].concat(it.slice(1)); }),
            pick: function(k){
              if (typeof k !== 'string' || k.indexOf('ovf:') !== 0) return false;
              pickPill(Number(k.slice(4))); return true;
            },
          };
          openMenu = null;
          const prevRect = ownBtn.getBoundingClientRect;
          ownBtn.getBoundingClientRect = function(){ return trig.getBoundingClientRect(); };
          try { ownBtn.click(); } finally {
            delete head._ddPre;
            if (prevRect === Element.prototype.getBoundingClientRect) delete ownBtn.getBoundingClientRect;
            else ownBtn.getBoundingClientRect = prevRect;
          }
          return;
        }
        const r = trig.getBoundingClientRect(), av = card ? card.getBoundingClientRect() : null;
        openMenu = DD.menu({x: r.left, y: r.bottom + 2, top: r.top, avoid: av}, items, pickPill);
      });
    }
    let busy = false, raf = 0;
    // the observers below: fit's own changes (the pills' classes set again) are dropped from them, or each fit queued
    // the next one, every frame for good (seen on a phone: 300 fits a second with the page at rest)
    const watchers = [];
    function fit(){
      raf = 0; if (busy) return; busy = true;
      const pills = getPills();
      head.classList.remove('dd-pills-compact', 'dd-pills-menu', 'dd-pills-ovf', 'dd-help-off');
      if (trig) trig.style.display = 'none';
      if (pc && !pc.classList.contains('dd-hm-nav')) pc.style.display = '';
      pills.forEach(function(o){ o.style.display = ''; o.classList.remove('dd-pill-ovf'); });
      stat.classList.remove('dd-stat-ico', 'dd-stat-hid');
      if (stat.textContent && (stat.dataset.ico || stat.scrollWidth > stat.clientWidth + 1)) stat.classList.add('dd-stat-ico');
      const ti = head.querySelector('.dd-title');
      const cut = function(e){ return e.style.display !== 'none' && e.offsetParent !== null && e.scrollWidth > e.clientWidth + 1; };
      const short = function(){
        if (head.scrollWidth > head.clientWidth + 1) return true;
        if (pills.some(cut)) return true;
        if (Array.prototype.some.call(head.querySelectorAll('.ddp-chip'), cut)) return true;
        return !!ti && cut(ti) && ti.clientWidth < 72;
      };
      // the title already cut: the steps that take nothing away (tighter spacing, Bars | Pie as one button) come
      // first, whatever the title's width; only moving pills into the "..." waits for the title to be down to 72 px
      const tight = function(){ return short() || (!!ti && cut(ti)); };
      // 1) hide stat icon before touching pills (stats move to title hover tooltip)
      if (stat.classList.contains('dd-stat-ico') && short()) stat.classList.add('dd-stat-hid');
      // 2) tighten header/pill spacing and drop spacer min-width so full-label pills fit whenever possible
      if (pills.length && tight()) head.classList.add('dd-pills-compact');
      // the pills that go together, kept together: a chart's views (dd-pview: Bars | Pie), its series (data-grp:
      // Retention's All, Young...); any other pill alone
      const groups = [];
      pills.forEach(function(p){
        const g = p.classList.contains('dd-pview') ? 'pview' : p.dataset.grp, last = groups[groups.length - 1];
        if (g && last && last.g === g){ last.ps.push(p); last.all.push(p); } else groups.push({g: g, ps: [p], all: [p]});
      });
      // 2b) the views, Bars | Pie, as one button: the view not shown (a click shows it, and the button then offers
      //     the other one)
      const views = groups.filter(function(gr){ return gr.g === 'pview' && gr.ps.length > 1; })[0];
      if (views && tight()){
        const off = views.ps.filter(function(p){ return !p.classList.contains('on'); });
        if (off.length){ views.ps.forEach(function(p){ if (p !== off[0]) p.style.display = 'none'; }); views.ps = [off[0]]; }
      }
      // 3) still no room -> progressively move the overflowing groups into the menu button, a group whole, keeping
      //    as many inline pills visible as actually fit in the header: first the pills with a menu of their own (a
      //    date, a range: their menu opens from the "..." the same), then the others, each from right to left
      if (trig && pills.length && (pills.length > 1 || pills.some(cut)) && short()){
        head.classList.add('dd-pills-ovf');
        trig.style.display = '';
        const drop = function(gr){ return gr.all.every(isDrop); }, ord = [];
        for (let i = groups.length - 1; i >= 0; i--) if (drop(groups[i])) ord.push(groups[i]);
        for (let i = groups.length - 1; i >= 0; i--) if (!drop(groups[i])) ord.push(groups[i]);
        for (let j = 0; j < ord.length; j++){
          // (the views whole in the menu, the one shown too: both listed, the shown one ticked)
          ord[j].all.forEach(function(p){
            p.style.display = 'none';
            p.classList.add('dd-pill-ovf');
          });
          if (!short()) break;
        }
        if (pills.every(function(p){ return p.style.display === 'none'; })) head.classList.add('dd-pills-menu');
        syncTrig(pills.filter(function(p){ return p.classList.contains('dd-pill-ovf'); }));
      }
      // 4) the "?" is drawn past its empty box: when it would cover the next button, it is hidden (nothing moves)
      const hq = head.querySelector('.dd-help'), hs = hq && hq.querySelector('svg');
      if (hs && hq.offsetParent !== null){
        const hr = hs.getBoundingClientRect();
        let after = false, nx = Infinity;
        Array.prototype.forEach.call(head.children, function(n){
          if (n === hq){ after = true; return; }
          if (!after || n.classList.contains('dd-spacer') || n.offsetParent === null) return;
          const r = n.getBoundingClientRect(); if (r.width >= 2) nx = Math.min(nx, r.left);
        });
        if (hr.right + 2 > nx) head.classList.add('dd-help-off');
      }
      watchers.forEach(function(w){ w.takeRecords(); });
      busy = false;
    }
    // Show Bottom Stats: the same stats centered under the chart, "Label:" in bold, wrapped by whole stats
    // (13 px, 18 px lines, the plot gives up 18 per line + 15)
    let bs = null;
    function syncBottom(){
      if (!card) return;
      if (!bs){ bs = document.createElement('div'); bs.className = 'dd-bstats'; card.appendChild(bs); }
      const parts = (stat.textContent || '').split(/\s*\u00b7\s*/).map(function(t){ return t.trim(); }).filter(Boolean);
      bs.innerHTML = parts.map(function(t){
        const esc = function(x){ return x.replace(/&/g, '&amp;').replace(/</g, '&lt;'); };
        const i = t.indexOf(':');
        return '<span>' + (i > 0 ? '<b>' + esc(t.slice(0, i + 1)) + '</b>' + esc(t.slice(i + 1)) : esc(t)) + '</span>';
      }).join('<i> \u00b7 </i>');
    }
    function later(){ if (!raf) raf = requestAnimationFrame(function(){ fit(); syncBottom(); }); }
    watchers.push(new MutationObserver(function(){ if (!busy) later(); }));
    watchers[0].observe(stat, {childList: true, characterData: true, subtree: true});
    if (pc && !pc.classList.contains('dd-hm-nav')){
      watchers.push(new MutationObserver(function(){ if (!busy) later(); }));
      watchers[1].observe(pc, {childList: true, subtree: true, attributes: true, attributeFilter: ['class']});
    }
    new ResizeObserver(later).observe(head);
    let tip = null;
    // the stats' lines in a tooltip: over the icon, or over the title when the icon has no room either (the full
    // title first then, it may be cut)
    function showTip(over, withTitle){
      if (tip) tip.remove();
      tip = document.createElement('div'); tip.className = 'dd-helptip';
      const esc = function(t){ return t.replace(/&/g, '&amp;').replace(/</g, '&lt;'); };
      tip.innerHTML = (withTitle ? '<div><b>' + esc(withTitle) + '</b></div>' : '') +
        stat.textContent.split(/\s\s\u00b7\s\s/).map(function(t){ return '<div>' + esc(t) + '</div>'; }).join('');
      (head.closest('.ddp') || document.body).appendChild(tip); tip.style.position = 'fixed';
      const r = over.getBoundingClientRect(), tr = tip.getBoundingClientRect();
      tip.style.left = Math.max(4, Math.min(window.innerWidth - tr.width - 4, withTitle ? r.left : r.right - tr.width)) + 'px';
      tip.style.top = (r.bottom + 5) + 'px';
    }
    function hideTip(){ if (tip){ tip.remove(); tip = null; } }
    stat.addEventListener('mouseenter', function(){ if (stat.classList.contains('dd-stat-ico')) showTip(stat); });
    stat.addEventListener('mouseleave', hideTip);
    stat.addEventListener('click', function(e){
      if (!DD.isTouch() || !stat.classList.contains('dd-stat-ico')) return;
      e.stopPropagation();
      if (tip){ hideTip(); return; }
      showTip(stat);
      const off = function(ev){ if (tip && !tip.contains(ev.target) && ev.target !== stat){ hideTip(); window.removeEventListener('pointerdown', off, true); } };
      setTimeout(function(){ window.addEventListener('pointerdown', off, true); }, 0);
    });
    const tt = head.querySelector('.dd-title');
    if (tt){
      let native = null;
      tt.addEventListener('mouseenter', function(){
        if (!stat.classList.contains('dd-stat-hid') || !stat.textContent) return;
        native = tt.getAttribute('title'); if (native !== null) tt.removeAttribute('title');  // (not both tooltips)
        showTip(tt, tt.textContent);
      });
      tt.addEventListener('mouseleave', function(){ hideTip(); if (native !== null){ tt.setAttribute('title', native); native = null; } });
    }
    later();
  };
  // "About This Chart" of a right-click menu: the chart's explanation (chart_help) where the menu was, in the "?"'s
  // tooltip, until the next click, key or scroll
  DD.helpPopup = function(text, x, y, host){
    if (!text) return;
    host = host || document.body;
    document.querySelectorAll('.dd-helptip').forEach(function(o){ o.remove(); });
    const t = document.createElement('div'); t.className = 'dd-helptip'; t.style.position = 'fixed'; t.textContent = text;
    host.appendChild(t);
    t.style.left = Math.max(8, Math.min((x || 0) + 10, window.innerWidth - t.offsetWidth - 8)) + 'px';
    t.style.top = Math.max(8, Math.min((y || 0) + 10, window.innerHeight - t.offsetHeight - 8)) + 'px';
    const close = function(){ t.remove(); ['mousedown', 'touchstart', 'keydown', 'wheel', 'blur'].forEach(function(e){ window.removeEventListener(e, close, true); }); };
    // from the next event on (the click that chose the entry may still be on its way)
    setTimeout(function(){ ['mousedown', 'touchstart', 'keydown', 'wheel', 'blur'].forEach(function(e){ window.addEventListener(e, close, true); }); }, 0);
  };
  // a drag starts (body.dd-dragging): the charts drop the hover they had (their mouseleave), none comes meanwhile (dd.css)
  (function(){
    let was = false;
    const watch = function(){
      new MutationObserver(function(){
        const on = document.body.classList.contains('dd-dragging');
        if (on && !was) document.querySelectorAll('.dd-plot canvas').forEach(function(c){ c.dispatchEvent(new MouseEvent('mouseleave')); });
        was = on;
      }).observe(document.body, {attributes: true, attributeFilter: ['class']});
    };
    if (document.body) watch(); else document.addEventListener('DOMContentLoaded', watch);
  })();
  DD.on = function(event, fn){ (listeners[event] = listeners[event] || []).push(fn); };
  DD.__push = function(event, payload){ (listeners[event] || []).forEach(function(fn){ fn(payload); }); };
  // ---- axis numbers that slide (Chart_Axis_Anim 'slide', as Anki's d3 charts while the scale moves) ----
  DD.axisSlide = function(){ return !(DD.theme && DD.theme.axis_anim === 'count'); };  // the default: slide
  DD.niceTicks = function(min, max, n){
    min = +min || 0; max = +max || 0; n = n || 4;
    const span = max - min;
    if (!(span > 0)) return [min];
    const raw = span / n, p = Math.pow(10, Math.floor(Math.log10(raw))), fr = raw / p;
    const step = (fr >= 7.0711 ? 10 : fr >= 3.1623 ? 5 : fr >= 1.4142 ? 2 : 1) * p;  // d3's tickStep
    const out = [];
    for (let v = Math.ceil(min / step - 1e-9) * step; v <= max * (1 + 1e-9) + 1e-9 && out.length < 60; v += step) out.push(+v.toPrecision(12));
    return out;
  };
  // the round values written at rest on a scale min..max: with the exact top (and the exact bottom when it is not 0)
  // written too, those closer to them than half a step (at least 24 px, two lines of text) are left out: 539 over 500
  // read as one, and 1.1h a third of a step over 1h looked crowded among the evenly spaced others
  function slideShown(min, max, n, px, bottom){
    const span = Math.max(1e-9, max - min), all = DD.niceTicks(min, max, n);
    const stepPx = all.length > 1 ? (all[1] - all[0]) / span * px : px;
    const gap = Math.max(24, 0.5 * stepPx);
    return all.filter(function(v){
      if (!(px > 0)) return true;
      if ((max - v) / span * px < gap) return false;
      return !(bottom && min !== 0 && (v - min) / span * px < gap);
    });
  }
  // ---- a time line under a plot (Activity's 10-minute bars, the one-dot-per-review view and the switches between
  // them): marks at round local times, each level of rounding (5 s ... 1 day) coming in as its marks get room, so the
  // marks slide and come or go smoothly at any zoom, and the bars and the dots draw the same marks for the same hours.
  // DD.timeMarks(t0, t1, px): [{t (ms), label, a (opacity from the room), lv (its level, s)}] for the window [t0, t1]
  // drawn px wide. DD.placeMarks(ctx, marks, toX, left, right, y): draws [{t?, x?, label, a, p?}] with the font and
  // colour set, a mark fading as it nears a more lasting one or reaches past the plot's ends; returns those drawn
  const TIME_LV = [5, 10, 30, 60, 300, 600, 1800, 3600, 7200, 21600, 43200, 86400];
  const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const p2 = function(n){ return (n < 10 ? '0' : '') + n; };
  DD.timeMarks = function(t0, t1, px){
    const span = t1 - t0, out = [];
    if (!(span > 0) || !(px > 0)) return out;
    const sm = function(x){ x = Math.max(0, Math.min(1, x)); return x * x * (3 - 2 * x); };
    const roomA = function(lv){ return sm((lv * 1000 / span * px - (lv < 60 ? 66 : 48)) / 26); };
    let fine = TIME_LV.length - 1;
    for (let i = 0; i < TIME_LV.length; i++){ if (roomA(TIME_LV[i]) > 0){ fine = i; break; } }
    const st = TIME_LV[fine] * 1000;
    // local time: the marks at round hours of the clock, a day's at midnight
    const loc = function(t){ return t - new Date(t).getTimezoneOffset() * 60000; };
    let t = t0 - ((loc(t0) % st) + st) % st;
    for (let k = 0; t <= t1 + st && k < 2000; k++, t += st){
      const L = loc(t) / 1000;
      let lv = TIME_LV[fine];
      for (let i = TIME_LV.length - 1; i > fine; i--){ if (Math.abs(L % TIME_LV[i]) < 0.5){ lv = TIME_LV[i]; break; } }
      const d = new Date(t), a = roomA(lv);
      const label = lv >= 86400 ? MON[d.getMonth()] + ' ' + p2(d.getDate()) : p2(d.getHours()) + ':' + p2(d.getMinutes()) + (lv < 60 ? ':' + p2(d.getSeconds()) : '');
      if (a > 0.003) out.push({t: t, label: label, a: a, lv: lv, p: lv + a});
    }
    return out;
  };
  DD.placeMarks = function(ctx, marks, toX, left, right, y){
    const sm = function(x){ x = Math.max(0, Math.min(1, x)); return x * x * (3 - 2 * x); };
    const placed = [], drawn = [];
    ctx.save(); ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    marks.slice().sort(function(p, q){ return (q.p || 0) - (p.p || 0); }).forEach(function(m){
      const x = m.x != null ? m.x : toX(m.t), lw = ctx.measureText(m.label).width;
      let a = m.a * sm((x - lw / 2 - left + 2) / 10) * sm((right - x - lw / 2 + 2) / 10);
      placed.forEach(function(q){ a *= sm((Math.abs(q.x - x) - (q.w + lw) / 2) / 14); });
      if (a <= 0.003) return;
      if (a > 0.05) placed.push({x: x, w: lw});
      ctx.globalAlpha = a * (m.k != null ? m.k : 1); ctx.fillText(m.label, x, y);
      drawn.push({x: x, a: a, t: m.t});
    });
    ctx.restore();
    return drawn;
  };
  // a scale (an axis top) between two at progress t: by ratio, not by difference. A value's height is v / top, so a
  // top going down straight left the values almost still at first, then rushing up at the end (29425 -> 5902: the
  // 4000 went from 13% to 23% of the height in the first half, to 68% in the second); by ratio the scale changes at
  // the same pace all along (as Activity's zoom camera)
  DD.scaleLerp = function(a, b, t){
    a = +a || 0; b = +b || 0;
    if (a > 0 && b > 0 && a !== b) return Math.exp(Math.log(a) + (Math.log(b) - Math.log(a)) * t);
    return a + (b - a) * t;
  };
  // the ticks of a scale whose change the chart knows: [{v, f (height as a share of the plot), a (opacity)}] for a
  // scale gliding from [fromMin, fromMax] to [toMin, toMax] (curMin / curMax now, t the progress 0..1). Values in both
  // just move; the old others leave over the first two thirds, the new others come over the last two; while it moves
  // a value coming close to a more lasting one fades as they near. At rest: all or nothing. px: the plot's height
  DD.slideTicks = function(fromMax, toMax, curMax, t, n, px, o){
    o = o || {};
    const fromMin = o.fromMin || 0, toMin = o.toMin || 0, curMin = o.curMin || 0, bottom = !!o.bottom;
    t = Math.max(0, Math.min(1, t == null ? 1 : t)); curMax = curMax > curMin ? curMax : curMin + 1;
    const span = curMax - curMin, sm = function(x){ x = Math.max(0, Math.min(1, x)); return x * x * (3 - 2 * x); };
    const a = slideShown(fromMin, fromMax, n, px, bottom), b = slideShown(toMin, toMax, n, px, bottom), out = [];
    const ka = a.map(String), kb = b.map(String);
    a.forEach(function(v){ const kept = kb.indexOf(String(v)) >= 0; out.push({v: v, f: (v - curMin) / span, a: kept ? 1 : 1 - sm(t / 0.67), p: kept ? 2 : 1 - t}); });
    b.forEach(function(v){ if (ka.indexOf(String(v)) < 0) out.push({v: v, f: (v - curMin) / span, a: sm((t - 0.33) / 0.67), p: t}); });
    let ticks = out.filter(function(k){ return k.f <= 0.9995 && k.f >= -0.0005 && k.a > 0.003; });
    ticks.push({v: curMax, f: 1, a: 1, p: 3, exact: true});
    if (bottom && (fromMin !== 0 || toMin !== 0)) ticks.push({v: curMin, f: 0, a: 1, p: 3, exact: true});
    const moving = t < 1 && (fromMax !== toMax || fromMin !== toMin);
    if (px > 0 && moving){
      ticks.sort(function(x, y){ return y.p - x.p; });
      const placed = [];
      ticks.forEach(function(k){
        let d = Infinity;
        placed.forEach(function(q){ d = Math.min(d, Math.abs(q.f - k.f) * px); });
        k.a *= sm((d - 9) / 9);
        if (k.a > 0.05) placed.push(k);
      });
      ticks = ticks.filter(function(k){ return k.a > 0.003; });
    }
    // dev trace (o.tag: the chart): every frame of a change, and any change of the values shown at rest (a value
    // that comes or goes at once)
    if (o.tag && DD.dev){
      const fm = function(v){ return String(+(+v).toPrecision(5)); };
      const sig = ticks.filter(function(k){ return k.a > 0.5; }).map(function(k){ return fm(k.v); }).sort(function(p, q){ return p - q; }).join(',');
      const L = DD._axLog || (DD._axLog = {}), prev = L[o.tag], changed = prev != null && prev !== sig;
      if (moving || changed) DD.trace('ANIMTRACE axis ' + o.tag + (moving ? ' t=' + t.toFixed(3) : ' AT REST') + ' top ' + fm(fromMax) + ' -> ' + fm(toMax) + ' now ' + fm(curMax) +
        (fromMin || toMin ? ' bottom ' + fm(fromMin) + ' -> ' + fm(toMin) : '') + ' plot ' + Math.round(px) + 'px | ' +
        ticks.map(function(k){ return fm(k.v) + ':' + k.a.toFixed(2); }).join(' ') + (changed ? ' | SHOWN ' + prev + ' => ' + sig : '') + ' @' + Math.round(performance.now()));
      L[o.tag] = sig;
    }
    return ticks;
  };
  // the same for a chart that only knows the scale it draws at: DD.slideAxis(st, min, max, {n, px, bottom, redraw}),
  // st kept by the chart. It remembers each round value's opacity: the values of the scale of the moment come in and
  // the others leave over 300 ms (times the speed); redraw() is called on the next frames until they are done (only if
  // the chart has not drawn meanwhile: its own animation draws them)
  DD.slideAxis = function(st, min, max, o){
    o = o || {}; min = +min || 0; max = +max || 0;
    const n = o.n || 4, px = o.px || 0, span = Math.max(1e-9, max - min), bottom = !!o.bottom;
    const sm = function(x){ x = Math.max(0, Math.min(1, x)); return x * x * (3 - 2 * x); };
    const target = {}; slideShown(min, max, n, px, bottom).forEach(function(v){ target[String(v)] = true; });
    const now = (window.performance && performance.now()) || Date.now();
    const live = !DD._noAnim && !(DD.anim && DD.anim.on === false);
    const moved = st.min !== undefined && (st.min !== min || st.max !== max);
    let pending = false;
    if (!st.a || !live){ st.a = {}; Object.keys(target).forEach(function(k){ st.a[k] = 1; }); }
    else {
      const k = Math.min(100, Math.max(0, now - (st.t || now))) / (300 * DD.speed());
      const keys = Object.keys(st.a); Object.keys(target).forEach(function(key){ if (!(key in st.a)) keys.push(key); });
      keys.forEach(function(key){
        const cur = st.a[key] || 0, to = target[key] ? 1 : 0;
        const nv = to > cur ? Math.min(1, cur + k) : (to < cur ? Math.max(0, cur - k) : cur);
        if (nv <= 0 && !to) delete st.a[key]; else st.a[key] = nv;
        if (nv !== to) pending = true;
      });
    }
    st.t = now; st.min = min; st.max = max;
    let ticks = Object.keys(st.a).map(function(key){ const v = +key; return {v: v, f: (v - min) / span, a: sm(st.a[key]), p: (target[key] ? 1 : 0) + st.a[key]}; })
      .filter(function(k){ return k.f >= -0.0005 && k.f <= 0.9995 && k.a > 0.003; });
    ticks.push({v: max, f: 1, a: 1, p: 3, exact: true});
    if (bottom && min !== 0) ticks.push({v: min, f: 0, a: 1, p: 3, exact: true});
    if (px > 0 && (moved || pending)){
      ticks.sort(function(x, y){ return y.p - x.p; });
      const placed = [];
      ticks.forEach(function(k){
        let d = Infinity;
        placed.forEach(function(q){ d = Math.min(d, Math.abs(q.f - k.f) * px); });
        k.a *= sm((d - 9) / 9);
        if (k.a > 0.05) placed.push(k);
      });
      ticks = ticks.filter(function(k){ return k.a > 0.003; });
    }
    if (pending && o.redraw && !st.raf && window.requestAnimationFrame){
      const t0 = st.t;
      st.raf = requestAnimationFrame(function(){ st.raf = 0; if (st.t === t0) o.redraw(); });
    }
    if (o.tag && DD.dev && (moved || pending)){  // dev trace: the values fading in / out after a change at once
      const fm = function(v){ return String(+(+v).toPrecision(5)); };
      DD.trace('ANIMTRACE axis ' + o.tag + ' (fades) top ' + fm(max) + (moved ? ' MOVED' : '') + ' | ' + ticks.map(function(k){ return fm(k.v) + ':' + k.a.toFixed(2); }).join(' ') + ' @' + Math.round(now));
    }
    return ticks;
  };
  // the page's lines for debug.log. Each send is a call to Python on Anki's UI thread: the traces (hundreds a second
  // during a change, one per chart and frame) go in batches, and none while a change is measured (DD.perfWatch), so
  // the log does not slow down what it watches; an error goes at once
  const LOGQ = []; let logT = null;
  const flushLog = function(force){
    logT = null;
    if (!LOGQ.length) return;
    if (!force && DD._logHold > 0){ logT = setTimeout(flushLog, 300); return; }
    const t = LOGQ.join('\n'); LOGQ.length = 0;
    try { DD._send('dd_log:' + t); } catch (e) {}
  };
  // DD.log: an error or a warning, written at once. DD.trace: a development trace, batched, and only in a source
  // checkout (DD.dev, set by Python before the page starts): a user's page neither builds nor sends them
  DD.dev = !!DD.dev;
  DD.log = function(text){ LOGQ.push(String(text)); flushLog(true); };
  // DD.swallowed: an error the page goes on after (a callback, a chart's drawing), logged once per place
  const SWALLOWED = new Set();
  DD.swallowed = function(where, e){
    if (SWALLOWED.has(where)) return; SWALLOWED.add(where);
    try { DD.log('Ignored error at ' + where + ': ' + ((e && e.stack) || e)); } catch (x) {}
  };
  DD.trace = function(text){
    if (!DD.dev) return;
    LOGQ.push(String(text));
    if (!logT) logT = setTimeout(flushLog, 500);
  };
  window.addEventListener('pagehide', function(){ flushLog(true); });
  // dev trace: how smooth a change is on screen, one line at its end (ANIMTRACE PERF): the gaps between frames, the
  // script run in each frame (the animations' requestAnimationFrame callbacks, timed), the slowest callbacks and the
  // long tasks (the page busy 50 ms or more at once: an answer from Python handled, a chart rebuilt...)
  DD.perfWatch = function(label, ms){
    if (!DD.dev || !window.pycmd) return;
    if (DD._pw) DD._pw.stop();
    const raf0 = DD._raf0 || (DD._raf0 = window.requestAnimationFrame.bind(window));
    const W = DD._pw = {t0: performance.now(), gaps: [], js: [], cur: 0, slow: {}, charts: {}, long: [], last: null, done: false};
    DD._logHold = (DD._logHold || 0) + 1;
    window.requestAnimationFrame = function(cb){
      return raf0(function(ts){
        const a = performance.now();
        try { cb(ts); } finally {
          const d = performance.now() - a; W.cur += d;
          if (d > 3){ const nm = (cb.name || String(cb).slice(0, 70)).replace(/\s+/g, ' '); W.slow[nm] = Math.max(W.slow[nm] || 0, d); }
        }
      });
    };
    W.main = [];
    try { W.mc = new MessageChannel(); W.mc.port1.onmessage = function(){ if (W.mcAt != null){ W.main.push(performance.now() - W.mcAt); W.mcAt = null; } }; } catch (e) { W.mc = null; }
    // the page's changes (style, class, text, nodes) over the watch, by where they are: what makes the browser work
    // out styles and layout again at each frame
    W.dom = {}; W.domN = 0;
    let mo = null;
    try {
      mo = new MutationObserver(function(ms){
        ms.forEach(function(m){
          let el = m.target.nodeType === 1 ? m.target : m.target.parentElement;
          const card = el && el.closest ? el.closest('[data-type]') : null;
          const at = (card ? card.dataset.type + ' ' : '') + (el ? el.tagName.toLowerCase() + (el.className && typeof el.className === 'string' ? '.' + el.className.split(' ')[0] : '') : '?') + ' ' + (m.type === 'attributes' ? m.attributeName : m.type);
          W.dom[at] = (W.dom[at] || 0) + 1; W.domN++;
        });
      });
      mo.observe(document.body, {subtree: true, attributes: true, childList: true, characterData: true});
    } catch (e) { mo = null; }
    let obs = null;
    try { obs = new PerformanceObserver(function(l){ l.getEntries().forEach(function(e){ W.long.push([Math.round(e.startTime - W.t0), Math.round(e.duration)]); }); }); obs.observe({entryTypes: ['longtask']}); } catch (e) { obs = null; }
    (function fr(now){
      if (W.done) return;
      if (W.last != null){ W.gaps.push([Math.round(now - W.t0), now - W.last, W.py]); W.js.push(W.cur); }
      W.py = !!(DD._pending && DD._pending().length);  // an answer awaited from Python over the next frame
      W.cur = 0; W.last = now;
      if (now - W.t0 >= ms){ W.stop(); return; }
      // the page's whole work on this frame, from its start (now) through scripts, style, layout and paint: a message
      // posted now comes after it
      if (W.mc){ W.mcAt = now; W.mc.port2.postMessage(0); }
      raf0(fr);
    })(performance.now());
    W.stop = function(){
      if (W.done) return; W.done = true;
      if (DD._pw === W){ DD._pw = null; window.requestAnimationFrame = raf0; }
      if (obs) try { obs.disconnect(); } catch (e) {}
      DD._logHold = Math.max(0, (DD._logHold || 1) - 1);
      const g = W.gaps.map(function(x){ return x[1]; }).sort(function(p, q){ return p - q; });
      const p95 = g.length ? g[Math.min(g.length - 1, Math.floor(g.length * 0.95))] : 0, avg = g.length ? g.reduce(function(p, q){ return p + q; }, 0) / g.length : 0;
      const bad = W.gaps.filter(function(x){ return x[1] > 25; }).map(function(x){ return '+' + x[0] + ':' + Math.round(x[1]) + (x[2] ? 'py' : ''); });
      // the frames while Python computed an answer for the page (py) and the others: whether its work is what slows them
      const pyN = W.gaps.filter(function(x){ return x[2]; }), pyBad = pyN.filter(function(x){ return x[1] > 25; }).length;
      const idN = W.gaps.length - pyN.length, idBad = bad.length - pyBad;
      const jsAvg = W.js.length ? W.js.reduce(function(p, q){ return p + q; }, 0) / W.js.length : 0, jsMax = W.js.length ? Math.max.apply(null, W.js) : 0;
      const mn = W.main.slice().sort(function(p, q){ return p - q; });
      const mainAvg = mn.length ? mn.reduce(function(p, q){ return p + q; }, 0) / mn.length : 0, mainP95 = mn.length ? mn[Math.min(mn.length - 1, Math.floor(mn.length * 0.95))] : 0;
      if (W.mc) try { W.mc.port1.close(); } catch (e) {}
      if (mo) try { mo.disconnect(); } catch (e) {}
      const domTop = Object.keys(W.dom).sort(function(p, q){ return W.dom[q] - W.dom[p]; }).slice(0, 8).map(function(k){ return k + ' x' + W.dom[k]; });
      const slow = Object.keys(W.slow).sort(function(p, q){ return W.slow[q] - W.slow[p]; }).slice(0, 4).map(function(k){ return Math.round(W.slow[k]) + 'ms ' + k.slice(0, 50); });
      const chTop = Object.keys(W.charts).sort(function(p, q){ return W.charts[q].ms - W.charts[p].ms; }).slice(0, 8)
        .map(function(k){ const c = W.charts[k]; return k + ':' + c.ms.toFixed(0) + 'ms(max ' + c.max.toFixed(1) + ',n=' + c.n + ')'; });
      DD.trace('ANIMTRACE PERF ' + label + ': ' + W.gaps.length + ' frames in ' + Math.round(performance.now() - W.t0) + ' ms | gap avg ' + avg.toFixed(1) + ', p95 ' + Math.round(p95) +
        ', worst ' + Math.round(g[g.length - 1] || 0) + ' ms; ' + bad.length + ' over 25 ms ' + (bad.length ? '[' + bad.slice(0, 12).join(' ') + ']' : '') + ' (Python computing: ' + pyBad + ' of ' + pyN.length + ' frames over 25 ms; idle: ' + idBad + ' of ' + idN + ')' +
        ' | page work per frame (scripts to paint) avg ' + mainAvg.toFixed(1) + ', p95 ' + Math.round(mainP95) + ' ms' +
        ' | page changes ' + W.domN + (domTop.length ? ' [' + domTop.join(', ') + ']' : '') +
        ' | script in frames avg ' + jsAvg.toFixed(1) + ', worst ' + jsMax.toFixed(1) + ' ms' + (slow.length ? ' | slowest: ' + slow.join(' ; ') : '') +
        (chTop.length ? ' | charts: ' + chTop.join(', ') : '') +
        ' | long tasks ' + (W.long.length ? W.long.map(function(x){ return '+' + x[0] + ':' + x[1] + 'ms'; }).join(' ') : 'none'));
      flushLog();
    };
  };
  DD.perfMark = function(label, ms, extra){
    if (!DD.dev) return;
    DD.trace('PERFTRACE ' + label + ' ' + (+ms).toFixed(1) + 'ms' + (extra ? ' ' + extra : ''));
  };
  DD.perfScroll = function(el, label){
    if (!DD.dev || !el) return;
    let last = -1e9;
    el.addEventListener('scroll', function(){
      const now = performance.now();
      if (now - last < 1200 || DD._pw) return;
      last = now;
      DD.perfWatch(label, 900);
    }, {passive: true});
  };
  // ("ResizeObserver loop completed with undelivered notifications": no error, the browser delivers them at the next
  // frame; while cards change size it came dozens of times a second, each one written to the log)
  window.addEventListener('error', function(e){
    if (/ResizeObserver loop/.test(e.message || '')) return;
    DD.log('JS error: ' + e.message + ' (line ' + e.lineno + ')');
  });
  window.addEventListener('unhandledrejection', function(e){ DD.log('JS promise error: ' + (e.reason && e.reason.message || e.reason)); });

  // ---- translations ----
  // The scripts' texts are English; Python gives the current language's entries for them (i18n.web_catalog).
  // DD.t(text, {name: ...}) for a text built in a script; the pages' own elements are translated as they come
  // (exact texts of text nodes, title and placeholder attributes), so menus, buttons and toasts need no call.
  DD.i18n = {};
  DD.t = function(s, vars){
    let r = (DD.i18n && typeof DD.i18n[s] === 'string' && DD.i18n[s]) || s;
    if (vars) r = String(r).replace(/\{(\w+)\}/g, function(m, k){ return Object.prototype.hasOwnProperty.call(vars, k) ? vars[k] : m; });
    return r;
  };
  // DD.tn(singular, plural, n, vars): the form for the count n ({n} is n), as i18n.tr_n (plural_index)
  function pluralIndex(code, n){
    n = Math.abs(+n || 0);
    const forms = {ja: 1, ko: 1, zh_CN: 1, pl: 3, ru: 3}[code] || 2;
    if (forms === 1) return 0;
    if (code === 'fr' || code === 'pt_BR') return n < 2 ? 0 : 1;
    if (forms === 3){
      if (n !== Math.floor(n)) return 1;
      const i = Math.floor(n);
      if (code === 'ru' && i % 10 === 1 && i % 100 !== 11) return 0;
      if (code === 'pl' && i === 1) return 0;
      if (i % 10 >= 2 && i % 10 <= 4 && !(i % 100 >= 12 && i % 100 <= 14)) return 1;
      return 2;
    }
    return n === 1 ? 0 : 1;
  }
  DD.tn = function(singular, plural, n, vars){
    vars = Object.assign({n: n}, vars || {});
    const v = DD.i18n && DD.i18n[singular], code = DD.i18n && DD.i18n['@lang'];
    let text = (Array.isArray(v) && v.length && v.every(Boolean)) ? v[Math.min(v.length - 1, pluralIndex(code, n))] : (n === 1 ? singular : plural);
    return String(text).replace(/\{(\w+)\}/g, function(m, k){ return Object.prototype.hasOwnProperty.call(vars, k) ? vars[k] : m; });
  };
  // the English dates of the charts' labels and tips ("Mar 05, 2026", "Mar 05, 14:30"), as i18n.localize_dates
  // (texts used: '{month} {day}, {year}' '{month} {day}, {time}' 'Jan' 'Feb' 'Mar' 'Apr' 'May' 'Jun' 'Jul' 'Aug'
  // 'Sep' 'Oct' 'Nov' 'Dec')
  const EN_DATE = /\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) (\d{1,2}), (\d{4}|\d{1,2}:\d{2}(?::\d{2})?)\b/g;
  DD.localizeDates = function(text){
    if (typeof text !== 'string' || !DD.i18n || !DD.i18n['@lang'] || text.indexOf(', ') < 0) return text;
    return text.replace(EN_DATE, function(m, mon, day, rest){
      const d = DD.i18n['@unpadded'] ? String(+day) : ('0' + (+day)).slice(-2);
      return rest.indexOf(':') >= 0 ? DD.t('{month} {day}, {time}', {month: DD.t(mon), day: d, time: rest})
                                    : DD.t('{month} {day}, {year}', {month: DD.t(mon), day: d, year: rest});
    });
  };
  // user content is never translated (deck names, a text widget's sentence, the table's rows)
  const NO_TR = '.dd-tbl tbody, .dd-deckpick-list, .ddp-text, [data-nt]';
  // dev (debug.log, I18N, a source checkout only): each text shown in English in another language, once, with where
  const missed = new Set();
  let shownTr = null;
  function missing(text, where){
    if (!DD.dev || !DD.i18n['@lang'] || missed.has(text) || !/[A-Za-z]{2}/.test(text) || DD.i18n[text]) return;
    if (!shownTr){ shownTr = new Set(); Object.keys(DD.i18n).forEach(function(k){ const v = DD.i18n[k]; (Array.isArray(v) ? v : [v]).forEach(function(x){ if (typeof x === 'string') shownTr.add(x.trim()); }); }); }
    if (shownTr.has(text)) return;
    missed.add(text);
    DD.trace('I18N not translated: "' + text.slice(0, 160) + '" (' + where + ')');
  }
  function whereOf(el){
    const out = [];
    for (let e = el; e && e.nodeType === 1 && out.length < 3; e = e.parentElement){
      const c = typeof e.className === 'string' ? e.className.trim().split(/\s+/)[0] : '';
      out.push(e.tagName.toLowerCase() + (c ? '.' + c : ''));
    }
    return out.join(' < ');
  }
  function trText(node){
    const raw = node.nodeValue; if (!raw) return;
    const k = raw.trim(); if (!k || k.length > 200) return;
    const p = node.parentElement; if (p && p.closest && p.closest(NO_TR)) return;
    if (p && (p.tagName === 'STYLE' || p.tagName === 'SCRIPT')) return;
    const v = DD.i18n[k];
    if (typeof v === 'string' && v && v !== k){ node.nodeValue = raw.replace(k, v); return; }
    const dt = DD.localizeDates(raw); if (dt !== raw){ node.nodeValue = dt; return; }
    missing(k, whereOf(p));
  }
  function trAttrs(el){
    if (el.closest && el.closest(NO_TR)) return;
    ['title', 'placeholder'].forEach(function(a){
      const v = el.getAttribute && el.getAttribute(a); if (!v) return;
      const t = DD.i18n[v.trim()];
      if (typeof t === 'string' && t !== v) el.setAttribute(a, t);
      else if (t === undefined) missing(v.trim(), a + ' of ' + whereOf(el));
    });
  }
  DD.translate = function(root){
    if (!root || !DD.i18n || Object.keys(DD.i18n).length < 2) return;
    if (root.nodeType === 3){ trText(root); return; }
    if (root.nodeType !== 1) return;
    trAttrs(root);
    const w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT);
    let n; while ((n = w.nextNode())){ if (n.nodeType === 3) trText(n); else trAttrs(n); }
  };
  // the charts' canvas texts (legends, groups, month and day names, "Total"...): a text drawn or measured that is a
  // whole entry of the catalog is the translation (one lookup; numbers and dates are never entries)
  function patchCanvas(){
    const P = window.CanvasRenderingContext2D && CanvasRenderingContext2D.prototype;
    if (!P || P._ddTr) return;
    P._ddTr = true;
    const fill = P.fillText, stroke = P.strokeText, measure = P.measureText;
    const tr = function(t){
      if (typeof t !== 'string') return t;
      const v = DD.i18n[t]; if (typeof v === 'string' && v) return v;
      const d = DD.localizeDates(t); if (d === t) missing(t, 'drawn in a chart');
      return d;
    };
    P.fillText = function(t, x, y, mw){ return mw === undefined ? fill.call(this, tr(t), x, y) : fill.call(this, tr(t), x, y, mw); };
    P.strokeText = function(t, x, y, mw){ return mw === undefined ? stroke.call(this, tr(t), x, y) : stroke.call(this, tr(t), x, y, mw); };
    P.measureText = function(t){ return measure.call(this, tr(t)); };
  }
  // roots: the page's own part (the whole window for Deep Dive, the block for the pinned widgets); the menus and
  // tips the scripts add to the body are translated too
  DD.setI18n = function(dict, root){
    DD.i18n = dict || {};
    // languages without capitals (i18n.uses_case): the small upper-case captions without letter spacing, larger
    if (/^(ja|ko|zh_CN)$/.test(DD.i18n['@lang'] || '')) document.documentElement.classList.add('dd-nocase');
    if (Object.keys(DD.i18n).length < 2 || !window.MutationObserver) return;
    root = root || document.body;
    patchCanvas();
    DD.translate(root);
    const mine = function(el){ return root === document.body || (el.nodeType === 1 && /(^|\s)(dd|ddp)-/.test(el.className || '')); };
    new MutationObserver(function(list){
      list.forEach(function(m){
        if (m.type === 'attributes'){ trAttrs(m.target); return; }
        m.addedNodes.forEach(function(n){ if (n.nodeType === 3 || n.nodeType === 1) DD.translate(n); });
      });
    }).observe(root, {childList: true, subtree: true, attributes: true, attributeFilter: ['title', 'placeholder']});
    if (root !== document.body) new MutationObserver(function(list){
      list.forEach(function(m){ m.addedNodes.forEach(function(n){ if (n.nodeType === 1 && mine(n)) DD.translate(n); }); });
    }).observe(document.body, {childList: true});
  };

  // ---- a fullscreen chart turned a quarter (landscape) on a phone held upright ----
  // Kioku keeps the screen upright (it never asks Android for an orientation, and Android's WebView has no
  // screen.orientation.lock): the page turns the layer that holds the chart itself. Its content lays out on a
  // landscape screen (the two sides swapped), and what reads positions sees the layer's own frame: the pointer, mouse
  // and touch events' coordinates, getBoundingClientRect of what is in it, innerWidth / innerHeight, elementFromPoint;
  // menus and tips added to <body> meanwhile go into it. The phone itself turned to landscape (Kioku follows it) puts
  // the layer back upright: onOff is told.
  DD.rot = (function(){
    let L = null, rw = 0, rh = 0, saved = '', onOff = null, descW, descH, mq = null;
    const inside = function(el){ return el === L || (el && el.nodeType && L.contains(el)); };
    // the layer turned 90deg clockwise: its top along the screen's right edge (the phone turned to the left to read it)
    const toV = function(x, y){ return [y, rw - x]; };
    const gbcr = Element.prototype.getBoundingClientRect;
    Element.prototype.getBoundingClientRect = function(){
      const r = gbcr.call(this);
      if (!L || !inside(this)) return r;
      return new DOMRect(r.top, rw - r.right, r.height, r.width);
    };
    const efp = Document.prototype.elementFromPoint;
    Document.prototype.elementFromPoint = function(x, y){
      return L ? efp.call(this, rw - y, x) : efp.call(this, x, y);
    };
    function fixPt(o){
      if (!o || o._ddRot) return;
      const v = toV(o.clientX, o.clientY);
      try {
        ['clientX', 'pageX', 'x'].forEach(function(k){ Object.defineProperty(o, k, {value: v[0], configurable: true}); });
        ['clientY', 'pageY', 'y'].forEach(function(k){ Object.defineProperty(o, k, {value: v[1], configurable: true}); });
        if (typeof o.movementX === 'number'){
          const mx = o.movementX, my = o.movementY;
          Object.defineProperty(o, 'movementX', {value: my, configurable: true});
          Object.defineProperty(o, 'movementY', {value: -mx, configurable: true});
        }
        o._ddRot = true;
      } catch (e) {}
    }
    function fix(e){
      if (!L || !e.isTrusted) return;
      if (e.touches){
        [e.touches, e.changedTouches, e.targetTouches].forEach(function(list){
          if (list) for (let i = 0; i < list.length; i++) fixPt(list[i]);
        });
      }
      if (typeof e.clientX === 'number') fixPt(e);
    }
    ['pointerdown', 'pointermove', 'pointerup', 'pointercancel', 'pointerover', 'pointerout', 'pointerenter', 'pointerleave',
     'mousedown', 'mousemove', 'mouseup', 'mouseover', 'mouseout', 'click', 'auxclick', 'dblclick', 'contextmenu',
     'touchstart', 'touchmove', 'touchend', 'touchcancel', 'wheel'].forEach(function(t){
      window.addEventListener(t, fix, {capture: true, passive: true});
    });
    function bodyAppend(n){ return Node.prototype.appendChild.call(L && n !== L ? L : document.body, n); }
    function turned(){ if (mq && mq.matches){ const cb = onOff; off(); if (cb) cb(); } }
    function place(){
      L.style.cssText = saved + ';position:fixed;left:0;top:0;right:auto;bottom:auto;width:' + rh + 'px;height:' + rw + 'px;' +
        'transform-origin:0 0;transform:translateX(' + rw + 'px) rotate(90deg);--dd-vw:' + (rh / 100) + 'px;--dd-vh:' + (rw / 100) + 'px';
    }
    // the view resized while turned (Kioku sizes it in steps after a rotation, the bars coming and going): the layer
    // follows (innerWidth / innerHeight are its own meanwhile: the page's from the root element)
    function refit(){
      if (!L) return;
      const w = document.documentElement.clientWidth, h = document.documentElement.clientHeight;
      if (!w || !h || w >= h || (w === rw && h === rh)) return;
      rw = w; rh = h; place();
      if (DD.frame) DD.frame.kick();
    }
    function on(el, cb){
      if (L) off();
      rw = window.innerWidth; rh = window.innerHeight;
      if (rw >= rh) return false;  // already landscape
      L = el; onOff = cb || null; saved = el.getAttribute('style') || '';
      el.classList.add('dd-rot');
      place();
      descW = Object.getOwnPropertyDescriptor(window, 'innerWidth'); descH = Object.getOwnPropertyDescriptor(window, 'innerHeight');
      try {
        Object.defineProperty(window, 'innerWidth', {get: function(){ return rh; }, configurable: true});
        Object.defineProperty(window, 'innerHeight', {get: function(){ return rw; }, configurable: true});
      } catch (e) {}
      document.body.appendChild = bodyAppend;
      mq = window.matchMedia ? window.matchMedia('(orientation: landscape)') : null;
      if (mq) mq.addEventListener('change', turned);
      window.addEventListener('resize', refit);
      return true;
    }
    function off(){
      if (!L) return;
      const el = L; L = null; onOff = null;
      if (mq){ mq.removeEventListener('change', turned); mq = null; }
      window.removeEventListener('resize', refit);
      delete document.body.appendChild;
      try {
        if (descW) Object.defineProperty(window, 'innerWidth', descW); else delete window.innerWidth;
        if (descH) Object.defineProperty(window, 'innerHeight', descH); else delete window.innerHeight;
      } catch (e) {}
      el.classList.remove('dd-rot');
      if (saved) el.setAttribute('style', saved); else el.removeAttribute('style');
      // menus and tips it held: gone with it (closed), or back on <body>
      el.querySelectorAll(':scope > .dd-menu, :scope > .dd-helptip, :scope > .dd-tip, :scope > .dd-toast').forEach(function(n){ n.remove(); });
    }
    // the charts best seen wide by default (the calendar fits the screen's width, a pie a square); the choice made
    // with the button is kept per chart type
    function wanted(type){
      let v = null;
      try { v = localStorage.getItem('dd-fs-land:' + type); } catch (e) {}
      if (v === '1' || v === '0') return v === '1';
      return !/^(heatmap|card_counts|todays_retention|custom_pie|text_label)$/.test(type) && String(type).indexOf('text:') !== 0;
    }
    // the phone held upright again (after it was turned to landscape, the layer then off): fn, until the stop returned
    function upagain(fn){
      const q = window.matchMedia ? window.matchMedia('(orientation: portrait)') : null;
      if (!q) return function(){};
      const h = function(){ if (q.matches) fn(); };
      q.addEventListener('change', h);
      return function(){ q.removeEventListener('change', h); };
    }
    function remember(type, land){ try { localStorage.setItem('dd-fs-land:' + type, land ? '1' : '0'); } catch (e) {} }
    // the button that turns it (fullscreen on a phone held upright): drawn by the caller, in the card's header
    const ICON = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 9V7a2 2 0 0 0-2-2h-6"/><path d="m15 2-3 3 3 3"/><path d="M20 13v5a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h2"/></svg>';
    return {on: on, off: off, active: function(){ return !!L; }, wanted: wanted, remember: remember, upagain: upagain, icon: ICON,
      upright: function(){ return window.innerHeight > window.innerWidth; }};
  })();

  // ---- touch / interaction mode ----
  const mqCoarse = window.matchMedia ? window.matchMedia('(pointer: coarse)') : null;
  const mqNoHover = window.matchMedia ? window.matchMedia('(hover: none)') : null;
  const uaMobile = /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent || '');
  let seenTouch = false;
  DD.isTouch = function(){
    const m = DD.theme && DD.theme.interaction_mode;
    if (m === 'touch') return true;
    if (m === 'desktop') return false;
    if (DD.theme && DD.theme.is_mobile) return true;
    if (seenTouch) return true;
    if (uaMobile && (navigator.maxTouchPoints > 0 || 'ontouchstart' in window)) return true;
    return !!((mqCoarse && mqCoarse.matches) || (mqNoHover && mqNoHover.matches));
  };
  DD.applyTouchClass = function(){
    const on = DD.isTouch();
    if (document.documentElement) document.documentElement.classList.toggle('dd-touch', on);
    if (document.body) document.body.classList.toggle('dd-touch', on);
  };
  if (mqCoarse && mqCoarse.addEventListener) mqCoarse.addEventListener('change', DD.applyTouchClass);
  if (mqNoHover && mqNoHover.addEventListener) mqNoHover.addEventListener('change', DD.applyTouchClass);
  window.addEventListener('pointerdown', function(e){
    if (e.pointerType === 'touch' && !seenTouch){ seenTouch = true; DD.applyTouchClass(); }
  }, {passive: true, capture: true});
  DD.applyTouchClass();

  // Unified long-press helper (~450 ms) for opening context menus on touch screens without interfering with scroll.
  DD.onLongPress = function(el, cb, opts){
    if (!el || !cb) return function(){};
    const ms = (opts && opts.ms) || 450, slop = (opts && opts.slop) || 10;
    let tm = 0, sx = 0, sy = 0, pid = null, fired = false;
    function cancel(){ if (tm){ clearTimeout(tm); tm = 0; } pid = null; }
    function onDown(e){
      if (e.pointerType !== 'touch' && !(DD.isTouch() && e.button === 0 && opts && opts.allowMouse)) return;
      if (opts && opts.ignore && e.target && e.target.closest && e.target.closest(opts.ignore)) return;
      cancel(); fired = false; pid = e.pointerId; sx = e.clientX; sy = e.clientY;
      tm = setTimeout(function(){
        tm = 0; fired = true;
        cb({clientX: sx, clientY: sy, target: e.target, preventDefault: function(){}, stopPropagation: function(){}, isTouch: true});
      }, ms);
    }
    function onMove(e){
      if (pid == null || e.pointerId !== pid) return;
      if (Math.hypot(e.clientX - sx, e.clientY - sy) > slop) cancel();
    }
    function onUp(e){
      if (pid != null && e.pointerId === pid) cancel();
    }
    function onClick(e){
      if (fired){ fired = false; e.preventDefault(); e.stopPropagation(); }
    }
    el.addEventListener('pointerdown', onDown, {passive: true});
    el.addEventListener('pointermove', onMove, {passive: true});
    el.addEventListener('pointerup', onUp, {passive: true});
    el.addEventListener('pointercancel', onUp, {passive: true});
    el.addEventListener('click', onClick, true);
    return function(){
      cancel();
      el.removeEventListener('pointerdown', onDown);
      el.removeEventListener('pointermove', onMove);
      el.removeEventListener('pointerup', onUp);
      el.removeEventListener('pointercancel', onUp);
      el.removeEventListener('click', onClick, true);
    };
  };

  // Touch: hold a card to lift it, then move the finger to drag it (the page scrolls near the edges);
  // let go without moving and its menu opens. A swipe before the hold scrolls the page as usual.
  // opts: pick(target) -> the card or null, ignore (selector), drag(phase, x, y, card, target) with
  // phase 'start' | 'move' | 'end' | 'cancel', menu(x, y, target), edge(card, x, y) -> the resize edge
  // under a hold ('r' | 'b' | 'rb' | null: the drag then resizes the card).
  // The drag functions feed the page's own mouse / pointer drag code with synthetic events (ddTouch set).
  let liftOn = null;  // the gesture in progress (one at a time)
  window.addEventListener('contextmenu', function(e){
    // the system's own long-press menu event: the lift decides what a hold does
    if (liftOn && e.isTrusted){ e.preventDefault(); e.stopImmediatePropagation(); }
  }, true);
  DD.touchLift = function(el, opts){
    const HOLD = 380, SLOP = 10, EDGE = 56;
    let g = null;
    function scroller(node){
      for (let n = node && node.parentElement; n && n !== document.body; n = n.parentElement){
        const cs = getComputedStyle(n);
        if (/(auto|scroll)/.test(cs.overflowY) && n.scrollHeight > n.clientHeight + 1) return n;
      }
      return document.scrollingElement || document.documentElement;
    }
    function hScroller(node){
      for (let n = node && node.parentElement; n && n !== document.body; n = n.parentElement){
        const cs = getComputedStyle(n);
        if (/(auto|scroll)/.test(cs.overflowX) && n.scrollWidth > n.clientWidth + 1) return n;
      }
      return null;
    }
    function finish(){
      if (!g) return;
      if (g.tm) clearTimeout(g.tm);
      if (g.raf) cancelAnimationFrame(g.raf);
      if (g.card) g.card.classList.remove('dd-lifted', 'dd-lift-edge');
      document.body.classList.remove('dd-lifting');
      g = null; liftOn = null;
    }
    function autoScroll(){
      if (!g || !g.dragging) return;
      const sc = g.sc, top = sc === document.scrollingElement || sc === document.documentElement ? 0 : sc.getBoundingClientRect().top;
      const bottom = top ? sc.getBoundingClientRect().bottom : window.innerHeight;
      let dy = 0;
      if (g.y < top + EDGE) dy = -Math.ceil((top + EDGE - g.y) / 4);
      else if (g.y > bottom - EDGE) dy = Math.ceil((g.y - (bottom - EDGE)) / 4);
      let moved = false;
      if (dy){ const before = sc.scrollTop; sc.scrollTop = before + dy; moved = sc.scrollTop !== before; }
      const hs = g.hsc;  // a row that scrolls sideways (the phone's strip of stat cards)
      if (hs){
        const r = hs.getBoundingClientRect();
        let dx = 0;
        if (g.x < r.left + EDGE) dx = -Math.ceil((r.left + EDGE - g.x) / 4);
        else if (g.x > r.right - EDGE) dx = Math.ceil((g.x - (r.right - EDGE)) / 4);
        if (dx){ const before = hs.scrollLeft; hs.scrollLeft = before + dx; moved = moved || hs.scrollLeft !== before; }
      }
      if (moved) opts.drag('move', g.x, g.y, g.card, g.target);
      g.raf = requestAnimationFrame(autoScroll);
    }
    el.addEventListener('touchstart', function(e){
      if (g || e.touches.length !== 1) { finish(); return; }
      const t = e.target, card = opts.pick(t);
      if (!card || (opts.ignore && t.closest && t.closest(opts.ignore))) return;
      const p = e.touches[0];
      g = {card: card, target: t, x0: p.clientX, y0: p.clientY, x: p.clientX, y: p.clientY, lifted: false, dragging: false};
      liftOn = g;
      g.tm = setTimeout(function(){
        if (!g) return;
        g.tm = 0; g.lifted = true; g.sc = scroller(card); g.hsc = hScroller(card);
        const ms = DD.anim && DD.anim.on === false ? 0 : Math.round(140 * (DD.speed ? DD.speed() : 1));
        document.documentElement.style.setProperty('--dd-lift-ms', ms + 'ms');
        // held on a resize edge: the edge shows, the move resizes (opts.edge); else the card rises
        g.cls = opts.edge && opts.edge(card, g.x0, g.y0) ? 'dd-lift-edge' : 'dd-lifted';
        card.classList.add(g.cls); document.body.classList.add('dd-lifting');
        try { if (navigator.vibrate) navigator.vibrate(12); } catch (err) {}
      }, HOLD);
    }, {passive: true});
    el.addEventListener('touchmove', function(e){
      if (!g) return;
      const p = e.touches[0]; if (!p) return;
      g.x = p.clientX; g.y = p.clientY;
      if (!g.lifted){
        // moved before the hold ended: a scroll
        if (Math.hypot(g.x - g.x0, g.y - g.y0) > SLOP) finish();
        return;
      }
      if (e.cancelable) e.preventDefault();  // the page stays put: the card moves
      if (!g.dragging){
        if (Math.hypot(g.x - g.x0, g.y - g.y0) < 6) return;
        g.dragging = true; if (g.cls === 'dd-lifted') g.card.classList.remove('dd-lifted');
        opts.drag('start', g.x0, g.y0, g.card, g.target);
        g.raf = requestAnimationFrame(autoScroll);
      }
      opts.drag('move', g.x, g.y, g.card, g.target);
    }, {passive: false});
    el.addEventListener('touchend', function(e){
      if (!g) return;
      const s = g;
      if (!s.lifted){ finish(); return; }
      if (e.cancelable) e.preventDefault();  // no tap / click after a hold
      finish();
      if (s.dragging) opts.drag('end', s.x, s.y, s.card, s.target);
      else if (opts.menu) opts.menu(s.x0, s.y0, s.target);
    }, {passive: false});
    el.addEventListener('touchcancel', function(){
      if (!g) return;
      const s = g; finish();
      if (s.dragging) opts.drag('cancel', s.x, s.y, s.card, s.target);
    }, {passive: true});
  };
  // a synthetic event for the page's own drag code, marked as coming from a touch lift
  DD.touchEvent = function(kind, type, x, y, target, extra){
    const init = {bubbles: true, cancelable: true, clientX: x, clientY: y, button: 0, buttons: type.slice(-2) === 'up' ? 0 : 1};
    let ev;
    if (kind === 'pointer' && window.PointerEvent) ev = new PointerEvent(type, Object.assign({pointerId: 9999, pointerType: 'mouse', isPrimary: true}, init));
    else ev = new MouseEvent(type, init);
    ev.ddTouch = true;
    if (extra) Object.assign(ev, extra);
    (target || window).dispatchEvent(ev);
    return ev;
  };
  // the resize edge of a card under (x, y) for a finger: a band of `band` px inside its right / bottom edge
  DD.touchEdge = function(card, x, y, dirs, band){
    const r = card.getBoundingClientRect(); band = band || 24;
    const right = dirs.indexOf('r') >= 0 && x >= r.right - band && x <= r.right + 4;
    const bottom = dirs.indexOf('b') >= 0 && y >= r.bottom - band && y <= r.bottom + 4;
    return right && bottom ? 'rb' : (right ? 'r' : (bottom ? 'b' : null));
  };
  // the system's context menu from a hold on the card: opened by the lift on release instead
  DD.openMenuAt = function(x, y, target){
    if (target && target.dispatchEvent) target.dispatchEvent(new MouseEvent('contextmenu', {bubbles: true, cancelable: true, clientX: x, clientY: y}));
  };

  // the text on the accent colour (an OK button): dark on a light accent (a grey or yellow one), else white
  DD.onAccent = function(){
    const c = document.createElement('span');
    c.style.color = 'var(--dd-accent)';
    document.body.appendChild(c);
    const m = getComputedStyle(c).color.match(/[\d.]+/g) || [];
    c.remove();
    const lin = function(v){ v = Number(v) / 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    const L = m.length >= 3 ? 0.2126 * lin(m[0]) + 0.7152 * lin(m[1]) + 0.0722 * lin(m[2]) : 0;
    return L > 0.5 ? '#1b1b1d' : '#fff';
  };

  // ---- theme ----
  DD.setTheme = function(theme){
    DD.theme = theme;
    DD.applyTouchClass();
    const root = document.documentElement;
    Object.keys(theme.css).forEach(function(k){ root.style.setProperty('--dd-' + k, theme.css[k]); });
    document.body.classList.toggle('dd-light', !theme.is_dark);
    if (!window.DDP){
      // a page of its own (not the pinned block inside Anki's page): Anki's styles in it (a button's hover, the
      // scrollbars, a list's popup) follow Anki's night mode; here they follow the page's theme (a light Deep Dive in a
      // dark Anki had dark hovers)
      root.classList.toggle('night-mode', !!theme.is_dark);
      document.body.classList.toggle('nightMode', !!theme.is_dark);
      root.style.colorScheme = theme.is_dark ? 'dark' : 'light';
    }
    DD.__push('theme', theme);
    DD.applyBackdrop();
  };

  // Window backdrop (theme.backdrop_spec): a gradient, two glows, a vignette and a grain.
  function eased(color, alpha){
    const rgb = hexRgb(color);
    return [[0, 1], [0.18, 0.66], [0.38, 0.34], [0.6, 0.13], [0.82, 0.035], [1, 0]].map(function(p){
      return 'rgba(' + rgb + ',' + (alpha * p[1]).toFixed(4) + ') ' + (p[0] * 100).toFixed(0) + '%';
    }).join(',');
  }
  function hexRgb(hex){
    const h = String(hex).replace('#', '');
    return [0, 2, 4].map(function(o){ return parseInt(h.substr(o, 2), 16) || 0; }).join(',');
  }
  let grainUrl = {};
  function grainTile(dark, k){
    const key = dark + ':' + k;
    if (grainUrl[key]) return grainUrl[key];
    const c = document.createElement('canvas'); c.width = c.height = 96;
    const x = c.getContext('2d'), img = x.createImageData(96, 96);
    let seed = 7;
    function rnd(){ seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 4294967296; }
    const maxA = dark ? 14 : 10;
    for (let i = 0; i < 96 * 96; i++){
      const a = Math.floor(rnd() * (maxA + 1));
      if (a < 3) continue;
      const v = rnd() < 0.5 ? 255 : 0;
      img.data[i * 4] = img.data[i * 4 + 1] = img.data[i * 4 + 2] = v; img.data[i * 4 + 3] = Math.round(a * k);
    }
    x.putImageData(img, 0, 0);
    return (grainUrl[key] = c.toDataURL());
  }
  DD.applyBackdrop = function(){
    // only a page of its own (Deep Dive, Settings...): the pinned block lives in Anki's main screen, whose background
    // is Anki's (or the user's picture). Its resize listener painted the Deep Dive backdrop over it (darkened by the
    // backdrop's tone) at the first resize of the main window
    if (window.DDP) return;
    const b = DD.theme && DD.theme.backdrop;
    if (!b) return;
    const bodyEl = document.body;
    let bgEl = document.getElementById('dd-backdrop');
    if (!b.enabled){
      if (bgEl) bgEl.style.display = 'none';
      bodyEl.style.background = b.flat;
      bodyEl.style.backgroundAttachment = '';
      return;
    }
    // Paint the 5-layer gradient + grain onto a dedicated GPU-promoted fixed layer instead of
    // body { background-attachment: fixed }: avoids Chromium's BackgroundAttachmentFixed
    // main-thread repaint on every scroll frame at 2560x1440.
    if (!bgEl){
      bgEl = document.createElement('div');
      bgEl.id = 'dd-backdrop';
      bgEl.setAttribute('aria-hidden', 'true');
      bgEl.style.cssText = 'position:fixed;inset:0;z-index:-1;pointer-events:none;contain:strict;transform:translateZ(0);';
      bodyEl.insertBefore(bgEl, bodyEl.firstChild);
    }
    bgEl.style.display = '';
    const w = window.innerWidth, h = window.innerHeight, span = Math.max(w, h);
    const layers = [];
    if (b.grain > 0) layers.push('url(' + grainTile(b.dark, b.grain) + ')');
    if (b.vignette_a > 0){
      layers.push('radial-gradient(circle ' + (span * 0.72).toFixed(0) + 'px at ' + (w / 2).toFixed(0) + 'px ' + (h * 0.4).toFixed(0) + 'px,rgba(0,0,0,0) 0%,rgba(0,0,0,0) 50%,rgba(0,0,0,' + b.vignette_a.toFixed(3) + ') 100%)');
    }
    if (b.glow2_a > 0) layers.push('radial-gradient(circle ' + (span * 0.55).toFixed(0) + 'px at ' + (w * 0.02).toFixed(0) + 'px ' + (h * 1.18).toFixed(0) + 'px,' + eased(b.glow2, b.glow2_a) + ')');
    if (b.glow1_a > 0) layers.push('radial-gradient(circle ' + (span * 0.62).toFixed(0) + 'px at ' + (w * 0.66).toFixed(0) + 'px ' + (-h * 0.3).toFixed(0) + 'px,' + eased(b.glow1, b.glow1_a) + ')');
    layers.push('linear-gradient(180deg,' + b.top + ' 0%,' + b.mid + ' 55%,' + b.bottom + ' 100%)');
    bgEl.style.background = layers.join(',');
    bgEl.style.backgroundRepeat = b.grain > 0 ? 'repeat,' + layers.slice(1).map(function(){ return 'no-repeat'; }).join(',') : 'no-repeat';
    document.documentElement.style.background = b.flat;
    bodyEl.style.background = 'transparent';
    bodyEl.style.backgroundAttachment = '';
    bodyEl.style.opacity = '';
  };
  // the time of the window's last resize: work that can wait (the table's tabs read ahead) waits for it to end; Python
  // busy with it held the window still, and a window being resized showed old pictures for 300-500 ms
  DD._lastResizeAt = 0;
  window.addEventListener('resize', function(){ DD._lastResizeAt = performance.now(); rzEvent(); DD.applyBackdrop(); });
  // the time of the last scroll (the page's or a scrolling area's): the work that can wait (the charts' late data,
  // the table's tabs read ahead) waits for the scroll to stop. Started during it, Python's 100-700 ms of reading held
  // Anki's UI thread now and then and the scroll stuttered
  DD._lastScrollAt = 0;
  const markScroll = function(){ DD._lastScrollAt = performance.now(); };
  window.addEventListener('scroll', markScroll, {capture: true, passive: true});
  window.addEventListener('wheel', markScroll, {capture: true, passive: true});
  window.addEventListener('touchmove', markScroll, {capture: true, passive: true});
  // fn once no scroll for `quiet` ms (at once when none is going on)
  DD.whenStill = function(fn, quiet){
    quiet = quiet == null ? 250 : quiet;
    (function check(){
      const left = quiet - (performance.now() - DD._lastScrollAt);
      if (left > 0) setTimeout(check, Math.max(30, left)); else fn();
    })();
  };

  // dev trace (RESIZETRACE): what a window resize costs the page. One burst = the resize events until 400 ms of quiet;
  // a line for each slow frame in it, then a summary: the sizes, the frames and their gaps, the time in the charts'
  // redraws (by chart) and in the grid's layout, the long tasks, the Python calls awaited, sent and answered. The
  // clock (epoch ms) lines it up with the window's own RESIZETRACE lines (Qt's resize events, Python side).
  DD._rz = null;
  let rzLongObs = null;
  DD.rzNote = function(kind, ms, name){
    const B = DD._rz; if (!B) return;
    B.cur[kind] = (B.cur[kind] || 0) + ms;
    if (kind === 'later'){ B.laterN++; return; }
    if (kind === 'draw'){ B.drawN++; B.drawMs += ms; const k = name || '?'; B.byChart[k] = (B.byChart[k] || 0) + ms; }
    else if (kind === 'layout'){ B.layoutN++; B.layoutMs += ms; B.layoutMax = Math.max(B.layoutMax, ms); }
  };
  // The burst (DD._rz) is also what puts the charts' redraws off while the window is resized (DD.frame.resized):
  // kept for every user, only its trace is a source checkout's. A zoom (Anki's Ctrl + / Ctrl -, Ctrl + wheel: the
  // pixel ratio changes) is not put off: each chart drawn again at once for its new size and ratio. Put off, each kept
  // its last picture stretched to its new box for 120-300 ms, then jumped to the right one: the charts bounced
  // inside their cards at each zoom step
  function rzEvent(){
    const now = performance.now(), w = window.innerWidth, h = window.innerHeight, d = window.devicePixelRatio || 1;
    let B = DD._rz;
    if (!B){
      B = DD._rz = {t0: now, clock: Date.now(), ev: 0, sizes: [], frames: 0, gaps: [], cur: {}, drawN: 0, drawMs: 0, byChart: {},
        layoutN: 0, layoutMs: 0, layoutMax: 0, laterN: 0, long: [], calls: [], answers: [], pending0: DD._pending && DD.dev ? DD._pending() : [], last: null, end: 0,
        dpr: d, zoom: false};
      B.end = now + 400;
      if (DD.dev) try { rzLongObs = new PerformanceObserver(function(l){ l.getEntries().forEach(function(e){ if (DD._rz) DD._rz.long.push(Math.round(e.startTime - DD._rz.t0) + '+' + Math.round(e.duration)); }); }); rzLongObs.observe({entryTypes: ['longtask']}); } catch (e) { rzLongObs = null; }
      const raf0 = DD._raf0 || window.requestAnimationFrame.bind(window);
      (function fr(t){
        if (DD._rz !== B) return;
        if (t == null){ raf0(fr); return; }
        if (B.last != null){
          const gap = t - B.last; B.frames++; B.gaps.push(Math.round(gap));
          if (gap > 50) DD.trace('RESIZETRACE slow frame +' + Math.round(t - B.t0) + 'ms gap=' + Math.round(gap) + 'ms window ' + window.innerWidth + 'x' + window.innerHeight
            + ' draws=' + Math.round(B.cur.draw || 0) + 'ms layout=' + Math.round(B.cur.layout || 0) + 'ms awaited=[' + (DD._pending ? DD._pending().join(', ') : '') + ']');
        }
        B.cur = {}; B.last = t;
        if (performance.now() >= B.end){ rzEnd(B); return; }
        raf0(fr);
      })(null);
    }
    B.ev++; B.end = now + 400;
    if (d !== B.dpr){ B.dpr = d; B.zoom = true; if (DD.dev) DD.trace('RESIZETRACE zoom: pixel ratio ' + d.toFixed(3) + ', charts drawn at once'); }
    const sz = w + 'x' + h; if (B.sizes[B.sizes.length - 1] !== sz) B.sizes.push(sz);
  }
  function rzEnd(B){
    DD._rz = null;
    if (rzLongObs){ try { rzLongObs.disconnect(); } catch (e) {} rzLongObs = null; }
    if (!DD.dev) return;
    const g = B.gaps.slice().sort(function(a, b){ return a - b; });
    const top = Object.keys(B.byChart).sort(function(a, b){ return B.byChart[b] - B.byChart[a]; }).slice(0, 5).map(function(k){ return k + ' ' + Math.round(B.byChart[k]); });
    const sizes = B.sizes.length > 6 ? B.sizes.slice(0, 3).concat(['...'], B.sizes.slice(-2)) : B.sizes;
    DD.trace('RESIZETRACE burst at clock ' + B.clock + ' dur=' + Math.round(B.last - B.t0) + 'ms events=' + B.ev + ' sizes ' + sizes.join(' -> ')
      + ' | frames=' + B.frames + ' gap median=' + (g[g.length >> 1] || 0) + 'ms max=' + (g[g.length - 1] || 0) + 'ms over50=' + g.filter(function(x){ return x > 50; }).length
      + ' | draws n=' + B.drawN + ' ' + Math.round(B.drawMs) + 'ms (' + top.join(', ') + ') put off ' + B.laterN
      + ' | layout n=' + B.layoutN + ' ' + Math.round(B.layoutMs) + 'ms max=' + Math.round(B.layoutMax)
      + ' | longtasks [' + B.long.join(' ') + ']'
      + ' | awaited at start [' + B.pending0.join(', ') + '] sent [' + B.calls.join(', ') + '] answered [' + B.answers.join(', ') + ']');
  }

  // Deep Dive: a deck / time span change plays every chart's own transition TEMPO x slower, the cards one after the
  // other (app.js refresh). Zooms and header switches keep their own speed.
  DD.TEMPO = 2.4;
  // the pinned widgets (pinned.js feed): close to Deep Dive's calm pace (~630 ms) so deck switches stay readable
  DD.PIN_TEMPO = 2.1;
  // Settings > General > Animations, "Animation Speed" of this page: every duration times this (Slow 1.5, Fast 0.6)
  DD.speed = function(){ const k = Number(DD.anim && DD.anim.speed); return k > 0 ? k : 1; };
  // a zoom out's length grows with how far it goes: 300 ms for a small step, up to 1.4 times that for a reset from a
  // narrow window to the whole span (it flew out in 300 ms, abrupt); a zoom in keeps its 300 ms
  DD.zoomLen = function(w0, w1){ if (!(w1 > w0 * 1.001)) return 1; const r = Math.log(w1 / Math.max(1e-9, w0)); return 1 + 0.4 * Math.min(1, r / Math.log(8)); };
  // a chart's intro (its first drawing, as it comes in view): ms times the speed, and in the Deep Dive window
  // INTRO_TEMPO slower (500 ms -> 750, near its deck / time span changes); the main screen keeps its quick intros
  DD.INTRO_TEMPO = 1.5;
  DD.intro = function(ms){ return ms * DD.speed() * (DD._introTempo || 1); };
  DD.calm = function(){ return (DD._calm === 'dd' ? (DD._ddTempo || DD.TEMPO) : DD._calm === 'pin' ? DD.PIN_TEMPO : 1) * DD.speed(); };
  // ---- frame scheduler: one loop for every chart; it stops when nothing moves ----
  const frames = new Set();
  let running = false;
  // a chart out of the window is not drawn (it catches up when it comes back): only what is seen costs frames
  // A chart coming into view starts its waiting animations once a good part of it shows (35 % of it, or of the
  // window for a tall one): started on its first pixel, a slow scroll only showed their end. Once playing, it
  // goes on until the chart has fully left.
  // Scrolled into view, it waits for more of it (45 %): at 35 %, a quick scroll down played the intro while the card
  // was still at the window's bottom, half hidden, and it looked already drawn once in sight. A chart already in the
  // window as it opens keeps 35 % (a row cut by the window's bottom plays at once).
  const VIS_PART = 0.35, VIS_SCROLL = 0.45;
  // A chart in full screen (DD._fsCard, app.js) covers the others: they count as out of view (they were drawn under
  // it at each of its zooms, ~10 hidden charts animating with it). What they missed is drawn as it closes (DD.fsEnd)
  DD._fsCard = null;
  const fsMissed = new Set();
  function unseen(fn){ return !!(fn._el && (fn._el._ddVis === false || (DD._fsCard && fn._el !== DD._fsCard && !DD._fsCard.contains(fn._el)))); }
  DD.fsEnd = function(){ DD._fsCard = null; const l = Array.from(fsMissed); fsMissed.clear(); l.forEach(function(fn){ DD.frame.drawNow(fn); }); DD.frame.kick(); };
  const io = window.IntersectionObserver ? new IntersectionObserver(function(es){
    es.forEach(function(en){
      const el = en.target;
      if (!en.isIntersecting){ el._ddVis = false; return; }
      const rb = en.rootBounds;
      const enough = en.intersectionRatio >= VIS_SCROLL || (rb && en.intersectionRect.height >= rb.height * VIS_SCROLL);
      if (enough || el._ddVis){ el._ddVis = true; el._ddSeen = true; DD.frame.kick(); }
      else el._ddVis = false;
    });
  }, {rootMargin: '16px', threshold: [0, 0.1, 0.2, 0.3, VIS_PART, VIS_SCROLL, 0.5, 0.75, 1]}) : null;
  const idleCbs = [];
  DD.onIdle = function(fn, maxWait){
    if (!running){ setTimeout(fn, 0); return; }
    let done = false;
    const go = function(){ if (done) return; done = true; fn(); };
    idleCbs.push(go);
    if (maxWait) setTimeout(go, maxWait);
  };
  // PERF: one line per run of animation (frames, real interval between frames, time spent drawing)
  let run = null, runs = 0;
  // The charts' opening animations wait for the window to be on screen and the page laid out (DD.go, called by the
  // window once both are true), so none is over before the window shows.
  DD._go = false;
  const goCbs = [];
  DD.onGo = function(fn){ if (DD._go) fn(); else goCbs.push(fn); };
  // (a loop already asked for, by a chart mounted before, runs now with DD._go set: asked for again, the
  // two ran side by side to the end of the opening, every chart drawn twice a frame)
  DD.go = function(){ if (DD._go) return; DD._go = true; DD.frame.kick(); goCbs.splice(0).forEach(function(fn){ try { fn(); } catch (e) { DD.swallowed('DD.onGo', e); } }); };
  setTimeout(function(){ DD.go(); }, 3000);  // never kept waiting (a page shown another way)
  const FRAME_BUDGET = 9;
  // one loop asked for at a time (asked for twice, two ran side by side, every chart drawn twice a frame). Not told
  // apart by the frame's time: a frame given the time of the one before stopped the only loop, for good (the charts
  // shown after it stayed blank)
  let asked = false;
  function ask(){ if (!asked){ asked = true; requestAnimationFrame(loop); } }
  function loop(now){
    asked = false;
    if (!DD._go){ running = false; return; }
    let busy = false, active = 0;
    const t0 = performance.now();
    if (!run) run = {n: 0, start: now, last: now, maxGap: 0, js: 0, jsMax: 0, maxActive: 0, by: {}, put: 0};
    // A frame's drawing kept within FRAME_BUDGET ms: past it, the charts left are drawn on the next frame, first (each
    // drawn at least every other frame). ~17 intros at once at the opening (Anki just started, its scripts not yet
    // made fast) took 18-35 ms a frame: every frame of the page came late, two or three lost at a time; so the page
    // keeps its pace and only a chart now and then skips one. Their animations go by the time, not the frame: a chart
    // drawn a frame later is where it should be.
    const order = [];
    frames.forEach(function(fn){ if (fn._late) order.push(fn); });
    frames.forEach(function(fn){ if (!fn._late) order.push(fn); });
    let drawn = 0;
    order.forEach(function(fn){
      if (unseen(fn)){ fn._held = true; fn._late = false; return; }
      if (!fn._late && drawn && performance.now() - t0 > FRAME_BUDGET){ fn._late = true; busy = true; run.put++; return; }
      fn._late = false; drawn++;
      // dev trace: a chart that waited out of view comes in: whether it had an animation waiting (it plays now) or
      // comes in drawn as it ends
      const back = !!fn._held;
      fn._held = false;
      const ft0 = performance.now();
      try {
        const moves = !!fn(now);
        if (moves){ busy = true; active++; }
        if (back && DD.dev) DD.trace('ANIMTRACE resume ' + ((fn._el.dataset && fn._el.dataset.type) || '?') + ': in view, ' + (moves ? 'ANIMATES now' : 'already still') + (fn._el._ddSeen ? '' : ' (never seen)'));
      } catch (e) { DD.log('frame error: ' + e.message + ' @ ' + String(e.stack || '').split('\n').slice(1, 3).join(' | ')); }
      const fdt = performance.now() - ft0;
      if (fdt > 0.2){
        const k = (fn._el && fn._el.dataset && fn._el.dataset.type) || 'other';
        const b = run.by[k] || (run.by[k] = {ms: 0, n: 0, max: 0});
        b.ms += fdt; b.n++; if (fdt > b.max) b.max = fdt;
        const pw = DD._pw;
        if (pw && pw.charts){
          const pc = pw.charts[k] || (pw.charts[k] = {ms: 0, n: 0, max: 0});
          pc.ms += fdt; pc.n++; if (fdt > pc.max) pc.max = fdt;
        } else if (DD.dev && fdt >= 8 && (!fn._slowAt || now - fn._slowAt > 1500)){
          fn._slowAt = now;
          DD.trace('PERFTRACE slow_draw ' + k + ' ' + fdt.toFixed(1) + 'ms');
        }
      }
    });
    const js = performance.now() - t0;
    run.n++; run.maxGap = Math.max(run.maxGap, now - run.last); run.last = now; run.js += js; run.jsMax = Math.max(run.jsMax, js);
    if (active > run.maxActive) run.maxActive = active;
    if (busy) ask();
    else {
      running = false;
      if (DD.dev && run.n > 6 && runs++ < 120){
        const top = Object.keys(run.by).sort(function(a, b){ return run.by[b].ms - run.by[a].ms; }).slice(0, 6)
          .map(function(k){ const b = run.by[k]; return k + ':' + (b.ms / Math.max(1, b.n)).toFixed(1) + 'ms(max ' + b.max.toFixed(1) + ',n=' + b.n + ')'; });
        DD.trace('PERF anim frames=' + run.n + ' dur=' + (now - run.start).toFixed(0) + 'ms avg=' + ((now - run.start) / Math.max(1, run.n - 1)).toFixed(1) + 'ms maxGap=' + run.maxGap.toFixed(0) + 'ms drawAvg=' + (run.js / run.n).toFixed(1) + 'ms drawMax=' + run.jsMax.toFixed(0) + 'ms active=' + run.maxActive + (run.put ? ' put off ' + run.put : '') + (top.length ? ' top=[' + top.join(', ') + ']' : ''));
      }
      run = null;
      if (idleCbs.length) idleCbs.splice(0).forEach(function(fn){ try { fn(); } catch (e) { DD.swallowed('frame idle', e); } });
    }
  }
  // While the window is resized the charts are redrawn now and then, all together (RZ_EVERY ms apart, and once the
  // window stops for RZ_QUIET ms), not at each step: redrawn at each step, they kept being drawn again under the eye
  // while the edge was dragged. Meanwhile each keeps its last picture, stretched to its new size. A first resize
  // (a maximize, the start of a drag) is drawn at once.
  const RZ_EVERY = 300, RZ_QUIET = 120, rzLater = new Map();
  let rzQueued = false, rzFlushAt = -1e9;
  function rzFlush(){
    rzFlushAt = performance.now();
    const todo = Array.from(rzLater.entries()); rzLater.clear();
    todo.forEach(function(e){ try { e[1](); } catch (x) { DD.swallowed('resize prep', x); } DD.frame.drawNow(e[0]); });
  }
  function rzKick(){
    if (rzQueued) return; rzQueued = true;
    (function check(){
      requestAnimationFrame(function(){
        if (!rzLater.size){ rzQueued = false; return; }
        const now = performance.now();
        if (!DD._rz || now - rzFlushAt >= RZ_EVERY || now - (DD._lastResizeAt || 0) >= RZ_QUIET){ rzQueued = false; rzFlush(); return; }
        check();
      });
    })();
  }
  // the running total's area, as Anki draws it (.cumulative-overlay, CumulativeOverlay.svelte): light, black 3 % fill
  // and black 8 % edge; dark, white 8 % fill and black 18 % edge. Black, not the theme's text colour (a purple or grey
  // text is paler than Anki's). k: the Total / Average Lines setting over its default; under it, Anki's values
  // stay (any lower and the total is hardly seen in light mode)
  DD.areaStyle = function(C, dark, k){
    k = Math.max(1, k || 1);
    // (light: a hair over Anki's 3 % / 8 %, 4 % / 11 %: on the cards' tint and through the canvas it read a little
    // paler than Anki's page side by side)
    return {fill: dark ? '#ffffff' : '#000000', fillA: Math.min(1, (dark ? 0.08 : 0.04) * k),
      line: '#000000', lineA: Math.min(1, (dark ? 0.18 : 0.11) * k), lw: 1};
  };

  // a chart drawn at its own size and shown smaller (the gallery's tiles: a holder with data-dd-scale and a CSS scale
  // of that much): its layout stays the full size, its canvas has the pixels it is shown on
  // a chart's tooltip at (left, top) of its plot, moved onto whole screen pixels: the mouse's place on the plot is
  // fractional (a card at x.5, Anki's zoom), and the tooltip, a layer of its own (will-change), had its text blurred
  DD.tipAt = function(tip, left, top){
    const p = tip.offsetParent;
    if (p){
      const d = window.devicePixelRatio || 1, s = DD.scaleOf(p) || 1, r = p.getBoundingClientRect();
      const x0 = r.left + p.clientLeft * s, y0 = r.top + p.clientTop * s;
      left = (Math.round((x0 + left * s) * d) / d - x0) / s;
      top = (Math.round((y0 + top * s) * d) / d - y0) / s;
    } else { left = Math.round(left); top = Math.round(top); }
    tip.style.transform = 'translate3d(' + left.toFixed(3) + 'px,' + top.toFixed(3) + 'px,0)';
  };
  DD.scaleOf = function(node){
    const h = node && node.closest ? node.closest('[data-dd-scale]') : null;
    return h ? (Number(h.dataset.ddScale) || 1) : 1;
  };
  // an element's size in its layout (CSS px): its box on screen over its holder's scale. While something moves it
  // (Deep Dive's cards slide and stretch, a scale(sx, sy) not the same across and down, when the layout changes) a
  // canvas fitted to that box would stay squashed once the card is still: then its layout size (offsetWidth /
  // offsetHeight, whole pixels), with moved: true.
  DD.boxOf = function(node){
    const r = node.getBoundingClientRect(), s = DD.scaleOf(node), ow = node.offsetWidth, oh = node.offsetHeight;
    if (ow > 0 && oh > 0 && (Math.abs(r.width - ow * s) > 1.5 || Math.abs(r.height - oh * s) > 1.5))
      return {w: ow, h: oh, s: s, r: r, moved: true};
    return {w: (r.width / s) || node.clientWidth || 1, h: (r.height / s) || node.clientHeight || 1, s: s, r: r, moved: false};
  };
  // a canvas sized to the device pixels it covers on screen. Its box rarely falls on whole device pixels (zoomed
  // to 120 %, a card 160.37 css px high starts at 747.48): the browser shows it on 193 pixels, and a canvas of
  // round(160 * 1.2) = 192 was stretched onto them, blurred (the ring charts most). The size comes from the
  // canvas's own device-pixel box (watched here), else from its placement; the drawing is scaled onto it.
  DD.fitCanvas = function(cv, g){
    const rawD = window.devicePixelRatio || 1;
    const d = DD.isTouch() ? Math.min(rawD, 2) : rawD;
    if (cv._ddFit && !cv._ddDirty && cv._ddFit.d === d && cv.width === cv._ddFit.cw && cv.height === cv._ddFit.ch){
      const F = cv._ddFit;
      g.setTransform(F.sx, 0, 0, F.sy, 0, 0);
      return {w: F.w, h: F.h, dpr: d};
    }
    const B = DD.boxOf(cv), r = B.r, s = B.s, w = B.w, h = B.h;
    if (!cv._ddPx && window.ResizeObserver){
      cv._ddPx = {};
      const ro = new ResizeObserver(function(es){
        cv._ddDirty = true;
        const e = es[es.length - 1], b = e.devicePixelContentBoxSize && e.devicePixelContentBoxSize[0];
        if (b) cv._ddPx = {w: b.inlineSize, h: b.blockSize, d: window.devicePixelRatio || 1};
      });
      try { ro.observe(cv, {box: 'device-pixel-content-box'}); } catch (e) { ro.observe(cv); }
    }
    const p = cv._ddPx;
    let cw = Math.round(r.right * d) - Math.round(r.left * d), ch = Math.round(r.bottom * d) - Math.round(r.top * d);
    if (B.moved){ cw = Math.round(w * s * d); ch = Math.round(h * s * d); }  // (its place on screen is not its own yet)
    // (the observer's size, while it is for this ratio and this size; else the one of the placement)
    if (s === 1 && p && p.w && p.d === d && Math.abs(p.w - w * d) < 1.5 && Math.abs(p.h - h * d) < 1.5){ cw = p.w; ch = p.h; }
    cw = Math.max(1, cw); ch = Math.max(1, ch);
    if (cv.width !== cw) cv.width = cw;
    if (cv.height !== ch) cv.height = ch;
    const sx = cw / w, sy = ch / h;
    cv._ddS = [sx, sy];
    cv._ddDirty = false;
    if (!B.moved) cv._ddFit = {w: w, h: h, cw: cw, ch: ch, sx: sx, sy: sy, d: d};
    else cv._ddFit = null;
    g.setTransform(sx, 0, 0, sy, 0, 0);
    return {w: w, h: h, dpr: d};
  };
  // the scale of a canvas sized by DD.fitCanvas, across and down (they differ by a hair)
  DD.canvasScale = function(cv, w, h){ return cv._ddS || [cv.width / (w || 1), cv.height / (h || 1)]; };

  DD.frame = {
    kick: function(){ if (!running){ running = true; ask(); } },
    add: function(fn){
      const el = DD._mountEl;
      if (el && io){
        fn._el = el;
        if (!el._ddObs){
          el._ddObs = true;
          // in view as the observer counts it (VIS_PART of it, or of the window): counted from its first pixel, a row
          // only peeking at the bottom as the window opened played its intro there, unseen, and came in already still
          const r = el.getBoundingClientRect(), vh = window.innerHeight;
          const part = Math.min(r.bottom, vh + 16) - Math.max(r.top, -16);
          el._ddVis = r.height > 0 && part > 0 && (part >= r.height * VIS_PART || part >= vh * VIS_PART);
          if (el._ddVis) el._ddSeen = true;
          io.observe(el);
        }
      }
      frames.add(fn); DD.frame.kick();
    },
    remove: function(fn){ frames.delete(fn); },
    busy: function(){ return running; },
    // a chart's size watched in device pixels: a zoom (Ctrl + wheel, Anki's zoom) changes them without changing the
    // CSS size, and the canvas would keep its old resolution, its text stretched and blurred
    observe: function(ro, el){ try { ro.observe(el, {box: 'device-pixel-content-box'}); } catch (e) { ro.observe(el); } },
    // a chart's canvas resized, through here (its ResizeObserver): resized and drawn at once (drawNow), or, while the
    // window is resized, now and then (rzKick above)
    resized: function(fn, prep){
      const B = DD._rz;
      // a zoom: this chart and those put off before it, drawn now (rzEvent above)
      if (B && (B.zoom || (window.devicePixelRatio || 1) !== B.dpr)){
        B.zoom = true;
        rzLater.delete(fn); if (rzLater.size) rzFlush();
        try { prep(); } catch (e) { DD.swallowed('zoom prep', e); }
        DD.frame.drawNow(fn); return;
      }
      if (B && (rzLater.size || B.ev > 1)){
        if (!rzLater.has(fn)) DD.rzNote('later');
        rzLater.set(fn, prep); rzKick(); return;
      }
      if (B && !rzLater.size) rzFlushAt = performance.now();
      rzLater.delete(fn);
      try { prep(); } catch (e) { DD.swallowed('resize prep', e); }
      DD.frame.drawNow(fn);
    },
    drawNow: function(fn){
      if (DD._go && DD._fsCard && unseen(fn) && fn._el._ddVis !== false) fsMissed.add(fn);
      else if (DD._go && !unseen(fn) && !fn._held){
        const t = performance.now();
        try { fn(t); } catch (e) { DD.swallowed('draw ' + ((fn._el && fn._el.dataset && fn._el.dataset.type) || '?'), e); }
        if (DD._rz) DD.rzNote('draw', performance.now() - t, fn._el && fn._el.dataset && fn._el.dataset.type);
      }
      DD.frame.kick();
    },  // something still moving (an export waits for it to settle)
  };
})();

// ---- zoom bar: the thin scrollbar under a zoomed chart ----
(function(){
  'use strict';
  const DD = window.DD;
  DD.zoomBar = function(plot, api){
    const bar = document.createElement('div'); bar.className = 'dd-zbar';
    const thumb = document.createElement('div'); thumb.className = 'dd-zthumb'; bar.appendChild(thumb);
    plot.appendChild(bar);
    // Touch-only compact zoom +/- pills (hidden on desktop mouse via CSS)
    const zctl = document.createElement('div'); zctl.className = 'dd-zctl';
    zctl.innerHTML = '<button type="button" class="dd-zbtn dd-zout" aria-label="Zoom out">&minus;</button><button type="button" class="dd-zbtn dd-zin" aria-label="Zoom in">+</button>';
    plot.appendChild(zctl);
    const zOut = zctl.querySelector('.dd-zout'), zIn = zctl.querySelector('.dd-zin');
    // past the whole view, zooming out goes on as the wheel does (onOutLimit) where the page allows it (canOutLimit):
    // out of the hours of a zoom under two days, which the adaptive zoom shows unzoomed
    function outLimit(){ return !!(api.onOutLimit && api.canOutLimit && api.canOutLimit()); }
    function stepZoom(dir){
      if (dir < 0 && !api.get() && outLimit()){ api.onOutLimit(); return; }
      const n = api.count(); if (n < 3) return;
      const r = api.get() || [0, n];
      const span = r[1] - r[0], mid = (r[0] + r[1]) / 2;
      const next = dir > 0 ? Math.max(2, Math.round(span * 0.55)) : Math.min(n, Math.round(span * 1.8));
      if (dir < 0 && next >= n * 0.94){
        api.set(null); if (api.onChange) api.onChange(null); return;
      }
      let a = Math.round(mid - next / 2);
      a = Math.max(0, Math.min(n - next, a));
      api.set(a, a + next);
      if (api.onChange) api.onChange(api.get() || [a, a + next]);
    }
    zctl.addEventListener('pointerdown', function(e){ e.stopPropagation(); });
    zIn.addEventListener('click', function(e){ e.stopPropagation(); stepZoom(1); });
    zOut.addEventListener('click', function(e){ e.stopPropagation(); stepZoom(-1); });
    const MIN_THUMB = 28;  // a scroll bar's handle keeps a size one can grab, however deep the zoom
    function geom(r, n){
      const w = bar.clientWidth || 1, span = r[1] - r[0], tw = Math.min(w, Math.max(MIN_THUMB, span / n * w));
      const free = Math.max(0, n - span), left = free > 0 ? r[0] / free * (w - tw) : 0;
      return {w: w, tw: tw, left: left, free: free};
    }
    function update(){
      const r = api.get(), n = api.count();
      zOut.disabled = !r && !outLimit();
      zIn.disabled = !n || (r ? (r[1] - r[0] <= 2) : n <= 2);
      if (!r || !n){ bar.style.display = 'none'; return; }
      bar.style.display = 'block';
      const g = geom(r, n);
      thumb.style.left = g.left + 'px'; thumb.style.width = g.tw + 'px';
    }
    api.bar = update;
    thumb.addEventListener('pointerdown', function(e){
      if (e.button !== 0 && e.pointerType === 'mouse') return;
      e.preventDefault(); e.stopPropagation();
      try { thumb.setPointerCapture(e.pointerId); } catch (err) {}
      const r0 = api.get(); if (!r0) return;
      const n = api.count(), x0 = e.clientX, span = r0[1] - r0[0], g = geom(r0, n);
      const step = api.step ? Math.max(1, api.step(span)) : 1;
      let lastA = r0[0];
      function mv(ev){
        if (ev.pointerId !== e.pointerId) return;
        // dragged like a scroll bar: the window follows at once (no zoom animation), on whole bins
        let a = r0[0] + (g.w - g.tw > 0 ? (ev.clientX - x0) / (g.w - g.tw) * g.free : 0);
        a = Math.round(a / step) * step;
        a = Math.max(0, Math.min(n - span, a));
        if (a === lastA) return;
        lastA = a;
        // the linked charts follow at once too
        DD._noAnim = true; try { api.set(a, a + span); if (api.onChange) api.onChange(api.get() || [a, a + span]); } finally { DD._noAnim = false; }
      }
      function up(ev){
        if (ev.pointerId !== e.pointerId) return;
        thumb.removeEventListener('pointermove', mv);
        thumb.removeEventListener('pointerup', up);
        thumb.removeEventListener('pointercancel', up);
      }
      thumb.addEventListener('pointermove', mv);
      thumb.addEventListener('pointerup', up);
      thumb.addEventListener('pointercancel', up);
    });
    bar.addEventListener('pointerdown', function(e){
      e.stopPropagation();
      if (e.target === thumb) return;
      const r0 = api.get(); if (!r0) return;
      const n = api.count(), span = r0[1] - r0[0], br = bar.getBoundingClientRect();
      const frac = Math.max(0, Math.min(1, (e.clientX - br.left) / Math.max(1, br.width)));
      const step = api.step ? Math.max(1, api.step(span)) : 1;
      let a = Math.round((frac * n - span / 2) / step) * step;
      a = Math.max(0, Math.min(n - span, a));
      DD._noAnim = true; try { api.set(a, a + span); if (api.onChange) api.onChange(api.get() || [a, a + span]); } finally { DD._noAnim = false; }
    });
    // 2-finger pinch-to-zoom on the chart canvas (never interferes with 1-finger vertical page scroll)
    const cv = plot.querySelector('canvas');
    if (cv && !cv._ddPinch){
      cv._ddPinch = true;
      let p = null;
      cv.addEventListener('touchstart', function(e){
        if (e.touches.length !== 2) return;
        const n = api.count(); if (n < 3) return;
        const t0 = e.touches[0], t1 = e.touches[1];
        const dist = Math.hypot(t1.clientX - t0.clientX, t1.clientY - t0.clientY);
        if (dist < 12) return;
        const r = api.get() || [0, n], rect = cv.getBoundingClientRect();
        const midX = (t0.clientX + t1.clientX) / 2;
        const frac = Math.max(0, Math.min(1, (midX - rect.left) / Math.max(1, rect.width)));
        p = {dist: dist, a0: r[0], b0: r[1], n: n, anchor: r[0] + (r[1] - r[0]) * frac, frac: frac, last: null};
      }, {passive: true});
      cv.addEventListener('touchmove', function(e){
        if (!p || e.touches.length !== 2) return;
        e.preventDefault();
        const t0 = e.touches[0], t1 = e.touches[1];
        const dist = Math.hypot(t1.clientX - t0.clientX, t1.clientY - t0.clientY);
        if (dist < 12) return;
        const scale = p.dist / dist;
        const span0 = p.b0 - p.a0;
        let span = Math.max(2, Math.min(p.n, Math.round(span0 * scale)));
        if (span >= p.n * 0.97){
          if (p.last !== 'full'){
            p.last = 'full';
            DD._noAnim = true; try { api.set(null); } finally { DD._noAnim = false; }
          }
          return;
        }
        let a = Math.round(p.anchor - span * p.frac);
        a = Math.max(0, Math.min(p.n - span, a));
        const b = a + span, key = a + ':' + b;
        if (p.last === key) return;
        p.last = key;
        DD._noAnim = true; try { api.set(a, b); } finally { DD._noAnim = false; }
      }, {passive: false});
      const endPinch = function(){
        if (!p) return;
        const changed = p.last != null;
        p = null;
        if (changed && api.onChange) api.onChange(api.get());
      };
      cv.addEventListener('touchend', endPinch, {passive: true});
      cv.addEventListener('touchcancel', endPinch, {passive: true});
    }
    update();
    return update;
  };
})();

// The guided tours' shared parts (the Deep Dive's in dd-tour.js, the main screen's in pinned.js): the dimmed screen
// with its light, the card, the drawn pointer and the example picture, the step dots, the keys, a tween. Each page
// keeps its own steps, demos and where it puts the card.
(function(){
  'use strict';
  const DD = window.DD;
  const PTR = '<svg width="20" height="24" viewBox="0 0 20 24"><path d="M2 1.5v18l4.6-4.3 3.2 7.1 3-1.4-3.1-6.9H16z" fill="#fff" stroke="#111" stroke-width="1.3" stroke-linejoin="round"/></svg>';
  // an element's box on screen, or null when it is narrower or lower than min
  function rect(el, min){
    if (!el || !el.getBoundingClientRect) return null;
    const r = el.getBoundingClientRect(), m = min || 0;
    if (!(r.width > m && r.height > m)) return null;
    return {left: r.left, top: r.top, right: r.right, bottom: r.bottom, width: r.width, height: r.height, x: r.left, y: r.top};
  }
  // the box around boxes (the missing ones left out), or null
  function unite(rs){
    const xs = (rs || []).filter(Boolean);
    if (!xs.length) return null;
    let l = Infinity, t = Infinity, r = -Infinity, b = -Infinity;
    xs.forEach(function(q){ l = Math.min(l, q.left); t = Math.min(t, q.top); r = Math.max(r, q.right); b = Math.max(b, q.bottom); });
    return {left: l, top: t, right: r, bottom: b, width: r - l, height: b - t};
  }
  // the overlay, put on <body>: {ov, hole, pic, ptr, card, title, dots, text, back, skip, next}
  function build(labels){
    const L = labels || {};
    const ov = document.createElement('div');
    ov.className = 'ddp-tour';
    ov.innerHTML = '<div class="ddp-tour-hole"></div><img class="ddp-tour-pic"><div class="ddp-tour-ptr">' + PTR + '</div>' +
      '<div class="ddp-tour-card"><div class="ddp-tour-head"><span class="ddp-tour-title"></span><span class="ddp-tour-dots"></span></div>' +
      '<div class="ddp-tour-text"></div><div class="ddp-tour-row"><button class="ddp-tour-back" type="button"></button><span></span>' +
      '<button class="ddp-tour-skip" type="button"></button><button class="ddp-tour-next" type="button"></button></div></div>';
    document.body.appendChild(ov);
    const q = function(c){ return ov.querySelector(c); };
    const el = {ov: ov, hole: q('.ddp-tour-hole'), pic: q('.ddp-tour-pic'), ptr: q('.ddp-tour-ptr'), card: q('.ddp-tour-card'),
      title: q('.ddp-tour-title'), dots: q('.ddp-tour-dots'), text: q('.ddp-tour-text'), back: q('.ddp-tour-back'),
      skip: q('.ddp-tour-skip'), next: q('.ddp-tour-next')};
    el.back.textContent = L.back || 'Back'; el.skip.textContent = L.skip || 'Skip'; el.next.textContent = L.next || 'Next';
    return el;
  }
  // the drawn mouse pointer of the examples: never on a touch screen (no mouse there)
  function ptr(el, x, y, show){
    if (show === false || (DD.isTouch && DD.isTouch())){ el.ptr.style.opacity = '0'; return; }
    el.ptr.style.opacity = '1';
    el.ptr.style.left = Math.round(x) + 'px';
    el.ptr.style.top = Math.round(y) + 'px';
  }
  // the example picture at x, y, w x h (src null: hidden); its box, or null
  function pic(el, src, x, y, w, h){
    const im = el.pic;
    if (!src){ im.style.display = 'none'; return null; }
    if (im.getAttribute('src') !== src) im.setAttribute('src', src);
    im.style.display = 'block';
    im.style.left = Math.round(x) + 'px'; im.style.top = Math.round(y) + 'px';
    im.style.width = Math.round(w) + 'px'; im.style.height = Math.round(h) + 'px';
    return {left: x, top: y, right: x + w, bottom: y + h, width: w, height: h};
  }
  // one dot a step, the current one lit and those before it seen; a click on one goes to it
  function dots(el, n, i, pick){
    const d = el.dots;
    if (d.children.length !== n){
      d.innerHTML = '';
      for (let k = 0; k < n; k++){
        const dot = document.createElement('i');
        dot.addEventListener('click', function(){ pick(k); });
        d.appendChild(dot);
      }
    }
    Array.from(d.children).forEach(function(dot, k){ dot.className = k === i ? 'on' : k < i ? 'seen' : ''; });
  }
  // Escape closes, Right / Enter goes on, Left goes back: the keydown listener (added on capture by the caller)
  function keys(close, step){
    return function(ev){
      if (ev.key === 'Escape'){ ev.preventDefault(); close(); }
      else if (ev.key === 'ArrowRight' || ev.key === 'Enter'){ ev.preventDefault(); step(1); }
      else if (ev.key === 'ArrowLeft'){ ev.preventDefault(); step(-1); }
    };
  }
  const ease = {
    quad: function(t){ return t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2; },
    cubic: function(t){ return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2; }
  };
  // fn(eased 0..1) on the frames for ms, then done; dropped as soon as alive() is false (the step changed)
  function tween(ms, curve, alive, fn, done){
    const t0 = performance.now();
    (function f(now){
      if (!alive()) return;
      const t = Math.min(1, (now - t0) / Math.max(1, ms));
      fn(curve(t));
      if (t < 1) requestAnimationFrame(f); else if (done) done();
    })(t0);
  }
  DD.tourKit = {rect: rect, unite: unite, build: build, ptr: ptr, pic: pic, dots: dots, keys: keys, ease: ease, tween: tween};
})();
