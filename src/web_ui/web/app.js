// The Deep Dive page: toolbar (deck, period, chart count, look) and a grid of chart cards.
(function(){
  'use strict';
  const DD = window.DD;
  const PERIODS = [[5, 'Today'], [6, 'Yesterday'], [0, 'Past Week'], [1, 'Past 2 Weeks'], [2, 'Past Month'], [8, 'Past 3 Months'], [3, 'Past Year'], [7, 'Last Year'], [-1, 'Total']];

  // One card of a given size, nothing else: for the dev comparison page.
  const TITLES = {activity: 'Activity', retention: 'Retention', heatmap: 'Heatmap', future_due: 'Future Due', distribution: 'Answer Buttons',
    hourly: 'Hourly Breakdown', card_counts: 'Card Counts', review_intervals: 'Review Intervals', stability: 'Stability', difficulty: 'Difficulty',
    retrievability: 'Retrievability', added: 'Added'};
  DD.headHtml = function(type){
    return '<div class="dd-head"><svg class="dd-chev" width="12" height="12" viewBox="0 0 12 12"><path d="M2 4l4 4 4-4" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>' +
      '<span class="dd-title">' + (TITLES[type] || (DD.extraTitles && DD.extraTitles[type]) || type) + '</span><span class="dd-stat"></span><span class="dd-help" data-t="' + type + '"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M9.1 9a3 3 0 0 1 5.8 1c0 2-3 3-3 3M12 17h.01"/></svg></span><span class="dd-spacer"><span class="dd-hbtns"><button class="dd-pinb" title="Pin to main menu"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 17v5M9 10.8a2 2 0 0 1-1.1 1.8l-1.8.9A2 2 0 0 0 5 15.2V16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-.8a2 2 0 0 0-1.1-1.8l-1.8-.9a2 2 0 0 1-1.1-1.8V7a1 1 0 0 1 1-1 2 2 0 0 0 0-4H8a2 2 0 0 0 0 4 1 1 0 0 1 1 1z"/></svg></button><button class="dd-more" title="Options (or right click)"><svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><circle cx="5" cy="12" r="1.8"/><circle cx="12" cy="12" r="1.8"/><circle cx="19" cy="12" r="1.8"/></svg></button></span></span><span class="dd-pills"></span></div>';
  };

  DD.startCard = function(boot){
    DD.settings = boot.settings || {};
    DD.setTheme(boot.theme);
    const root = document.getElementById('dd-root');
    root.innerHTML = '<div class="dd-card dd-fixed" style="width:' + boot.size.w + 'px;height:' + boot.size.h + 'px">' + DD.headHtml(boot.type) +
      '<div class="dd-body"></div></div>';
    DD.charts[boot.type].mount(root.querySelector('.dd-body'), {data: boot.data, options: boot.options || {}, animate: false, head: root.querySelector('.dd-head')});
  };

  // Lucide-style 24x24 icons (stroke).
  // texts made in the scripts: 'Reset Activity Zoom' 'Reset Retention Zoom' 'Reset Added Zoom'
  function titleOf(t){ return DD.t(TITLES[t] || (DD.extraTitles && DD.extraTitles[t]) || t); }
  // a text of the Deep Dive ("text:<id>", providers.is_text), not a chart
  function isText(t){ return typeof t === 'string' && t.indexOf('text:') === 0; }
  const ICONS = {
    palette: '<circle cx="13.5" cy="6.5" r=".5"/><circle cx="17.5" cy="10.5" r=".5"/><circle cx="8.5" cy="7.5" r=".5"/><circle cx="6.5" cy="12.5" r=".5"/><path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10c.9 0 1.6-.7 1.6-1.6 0-.4-.2-.8-.4-1.1-.3-.3-.4-.7-.4-1.1 0-.9.7-1.6 1.6-1.6H16c3.3 0 6-2.7 6-6 0-4.9-4.5-8.6-10-8.6z"/>',
    reset: '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/>',
    image: '<rect width="18" height="18" x="3" y="3" rx="2" ry="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.1-3.1a2 2 0 0 0-2.8 0L6 21"/>',
    grid: '<rect width="18" height="18" x="3" y="3" rx="2"/><path d="M3 9h18M3 15h18M9 3v18M15 3v18"/>',
    table: '<rect width="18" height="18" x="3" y="3" rx="2"/><path d="M3 9h18M3 15h18M12 3v18"/>',
    filetext: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6M16 13H8M16 17H8M10 9H8"/>',
    minus: '<path d="M5 12h14"/>', plus: '<path d="M5 12h14M12 5v14"/>', x: '<path d="M18 6 6 18M6 6l12 12"/>',
    gear: '<path d="M12.2 2h-.4a2 2 0 0 0-2 2v.2a2 2 0 0 1-1 1.7l-.4.3a2 2 0 0 1-2 0l-.2-.1a2 2 0 0 0-2.7.7l-.2.4a2 2 0 0 0 .7 2.7l.2.1a2 2 0 0 1 1 1.7v.5a2 2 0 0 1-1 1.8l-.2.1a2 2 0 0 0-.7 2.7l.2.4a2 2 0 0 0 2.7.7l.2-.1a2 2 0 0 1 2 0l.4.3a2 2 0 0 1 1 1.7v.2a2 2 0 0 0 2 2h.4a2 2 0 0 0 2-2v-.2a2 2 0 0 1 1-1.7l.4-.3a2 2 0 0 1 2 0l.2.1a2 2 0 0 0 2.7-.7l.2-.4a2 2 0 0 0-.7-2.7l-.2-.1a2 2 0 0 1-1-1.8v-.5a2 2 0 0 1 1-1.7l.2-.1a2 2 0 0 0 .7-2.7l-.2-.4a2 2 0 0 0-2.7-.7l-.2.1a2 2 0 0 1-2 0l-.4-.3a2 2 0 0 1-1-1.7V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/>',
    chartplus: '<path d="M3 3v16a2 2 0 0 0 2 2h16"/><path d="M7 16v-5M12 16V9M17 16v-3"/><path d="M19 3v4M17 5h4"/>',
    chevup: '<path d="m18 15-6-6-6 6"/>', chevdown: '<path d="m6 9 6 6 6-6"/>',
    dots: '<circle cx="5" cy="12" r="1.4"/><circle cx="12" cy="12" r="1.4"/><circle cx="19" cy="12" r="1.4"/>',
    type: '<path d="M4 7V4h16v3M9 20h6M12 4v16"/>', pencil: '<path d="M21.2 6.8a2.8 2.8 0 0 0-4-4L4 16v4h4z"/><path d="m15 5 4 4"/>',
    activity: '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>', layers: '<path d="m12 2 9 5-9 5-9-5 9-5z"/><path d="m3 12 9 5 9-5"/><path d="m3 17 9 5 9-5"/>',
    calendar: '<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>',
    split: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 12h18"/>',
    bars: '<path d="M6 20V10M12 20V4M18 20v-6"/>', trend: '<path d="m22 7-8.5 8.5-5-5L2 17"/><path d="M16 7h6v6"/>',
    save: '<path d="M15.2 3a2 2 0 0 1 1.4.6l3.8 3.8a2 2 0 0 1 .6 1.4V19a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z"/><path d="M17 21v-7a1 1 0 0 0-1-1H8a1 1 0 0 0-1 1v7M7 3v4a1 1 0 0 0 1 1h7"/>',
    maximize: '<path d="M8 3H5a2 2 0 0 0-2 2v3M21 8V5a2 2 0 0 0-2-2h-3M3 16v3a2 2 0 0 0 2 2h3M16 21h3a2 2 0 0 0 2-2v-3"/>',
    pin: '<path d="M12 17v5M9 10.8a2 2 0 0 1-1.1 1.8l-1.8.9A2 2 0 0 0 5 15.2V16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-.8a2 2 0 0 0-1.1-1.8l-1.8-.9a2 2 0 0 1-1.1-1.8V7a1 1 0 0 1 1-1 2 2 0 0 0 0-4H8a2 2 0 0 0 0 4 1 1 0 0 1 1 1z"/>',
    trash: '<path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>',
    help: '<circle cx="12" cy="12" r="10"/><path d="M9.1 9a3 3 0 0 1 5.8 1c0 2-3 3-3 3M12 17h.01"/>',
    wrench: '<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>',
    sliders: '<path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M2 14h4M10 8h4M18 16h4"/>',
    heart: '<path d="M19 14c1.5-1.5 3-3.2 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.8 0-3 .5-4.5 2-1.5-1.5-2.7-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4 3 5.5l7 7z"/>',
    thumb: '<path d="M7 10v12M15 5.9 14 10h5.8a2 2 0 0 1 1.9 2.5l-2.3 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.8a2 2 0 0 0 1.8-1.1L12 2a3.1 3.1 0 0 1 3 3.9z"/>',
    github: '<path d="M15 22v-4a4.8 4.8 0 0 0-1-3.5c3 0 6-2 6-5.5.1-1.3-.3-2.7-1-3.8.3-1.1.3-2.4 0-3.5 0 0-1 0-3 1.5-2.6-.7-5.4-.7-8 0C6 2 5 2 5 2c-.3 1.1-.3 2.4 0 3.5-.7 1.1-1.1 2.500-1 3.800 0 3.500 3 5.500 6 5.500-.4.400-.7 1-.8 1.700-.1.700-.2 1.400-.2 2.200V22"/><path d="M9 18c-4.500 1-5-2-7-2"/>',
  };
  function icon(name, size){
    return '<svg class="dd-ic" width="' + (size || 16) + '" height="' + (size || 16) + '" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' + ICONS[name] + '</svg>';
  }
  ICONS.history = '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M12 7v5l4 2"/>';
  ICONS.search = '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>';
  ICONS.filter = '<polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/>';
  DD.icon = icon;
  // a chart and its Time Machine, the same chart on a past day (View on a Past Day: here and on the main screen,
  // pinned.js; logic/pinning.py PAST)
  DD.pastOf = {review_intervals: 'interval_history', stability: 'stability_history', difficulty: 'difficulty_history'};
  // a chart brought into view: a short ring around it (none with the animations off)
  DD.flashCard = function(card){
    if (!card || (DD.anim && DD.anim.on === false)) return;
    card.classList.remove('dd-flash'); void card.offsetWidth;
    card.style.setProperty('--dd-flash-ms', Math.round(1600 * (DD.speed ? DD.speed() : 1)) + 'ms');
    card.classList.add('dd-flash');
    card.addEventListener('animationend', function end(e){
      if (e.animationName !== 'dd-flash') return;
      card.classList.remove('dd-flash'); card.style.removeProperty('--dd-flash-ms'); card.removeEventListener('animationend', end);
    });
  };

  // the page's own menu: items [key, label, checked or null, icon (a name of ICONS or
  // an image's data URL), mode (true: a tick that keeps it open, 'radio': one of a choice), submenu items, disabled]
  // or 'sep'; onPick(key, on). Deep Dive's DD.menu, and the main screen's menus (pinned.js, web_menus.py)
  function menu(anchor, items, onPick, sub){
    // no separator first, last or twice in a row
    items = (function(src){ const out = []; src.forEach(function(it){ if (it === 'sep' && (!out.length || out[out.length - 1] === 'sep')) return; out.push(it); }); while (out.length && out[out.length - 1] === 'sep') out.pop(); return out; })(items);
    // web: the button of an open menu clicked again closes it (it opened it again)
    if (!sub && anchor && anchor.nodeType === 1 && DD._menuAnchor === anchor && document.querySelector('.dd-menu')){
      document.querySelectorAll('.dd-menu').forEach(function(o){ o.remove(); });
      DD._menuAnchor = null; return null;
    }
    if (!sub) document.querySelectorAll('.dd-menu').forEach(function(o){ o.remove(); });
    if (!sub) DD._menuAnchor = (anchor && anchor.nodeType === 1) ? anchor : null;
    const m = document.createElement('div'); m.className = 'dd-menu' + (sub ? ' dd-submenu' : '');
    // the button that opened it (given, or the one just clicked: a menu opened at a point, or built by Python)
    if (!sub) m._opener = (anchor && anchor.nodeType === 1) ? anchor : (DD._lastOpener && performance.now() - DD._lastOpener.t < 3000 ? DD._lastOpener.el : null);
    let subEl = null;
    // with an icon on some entries, the others' text lines up with theirs
    const anyIcon = items.some(function(it){ return Array.isArray(it) && it[3]; });
    items.forEach(function(it){
      if (it === 'sep'){ const s = document.createElement('div'); s.className = 'dd-msep'; m.appendChild(s); return; }
      const isSub = Array.isArray(it[5]);
      const b = document.createElement('div'); b.dataset.k = String(it[0]); b.className = 'dd-mi' + (it[2] ? ' on' : '') + (it[2] !== undefined && it[2] !== null ? ' chk' : '') + (it[6] ? ' off' : '');
      b.innerHTML = (it[3] ? '<span class="dd-mic">' + (/^data:/.test(it[3]) ? '<img src="' + it[3] + '" width="16" height="16" alt="">' : (/^#[0-9a-f]{3,8}$/i.test(it[3]) ? '<span class="dd-mswatch" style="background:' + it[3] + '"></span>' : icon(it[3], 16))) + '</span>' : (anyIcon ? '<span class="dd-mic"></span>' : '')) + '<span class="dd-mt">' + it[1] + '</span>' + ((it[2] !== undefined && it[2] !== null) ? '<span class="ind"></span>' : '') + (isSub ? '<span class="dd-arr">\u203a</span>' : '');
      b.onmouseenter = function(){
        if (subEl && (!isSub || b.classList.contains('off'))){ subEl.remove(); subEl = null; }
        if (isSub && !b.classList.contains('off')){
          if (subEl) subEl.remove();
          subEl = menu(b, it[5], onPick, true);
        }
      };
      b.onclick = function(ev){
        ev.stopPropagation();
        if (isSub) return;
        if (it[6]) return;  // disabled
        // a checked entry of a choice (StyledMenu.mouseReleaseEvent): it is picked and the menu stays open
        // the entries keep the ticks shown (this one, and others its action changed): a submenu closed and opened
        // again is built from them, not from the ticks it opened with
        const keep = function(){ items.forEach(function(x){ if (!Array.isArray(x) || x[2] === undefined || x[2] === null) return; const el = m.querySelector('.dd-mi[data-k="' + CSS.escape(String(x[0])) + '"]'); if (el) x[2] = el.classList.contains('on'); }); };
        if (it[4] === 'radio'){ m.querySelectorAll('.dd-mi.chk').forEach(function(x){ if (x._radio) x.classList.remove('on'); }); b.classList.add('on'); onPick(it[0]); keep(); return; }
        if (it[4]){ b.classList.toggle('on'); onPick(it[0], b.classList.contains('on')); keep(); return; }
        document.querySelectorAll('.dd-menu').forEach(function(o){ o.remove(); }); onPick(it[0]);
      };
      b._radio = it[4] === 'radio';
      m.appendChild(b);
    });
    if (DD.menuStyle) DD.menuStyle(m);  // the main screen: its theme's colours are on its block, not on the page
    document.body.appendChild(m);
    if (sub){
      const r = anchor.getBoundingClientRect();
      // beside its entry, on the right; no room there (a menu at the window's right edge): on its left, never over it
      const right = r.right - 2, left = r.left - m.offsetWidth + 2;
      m.style.left = (right + m.offsetWidth <= window.innerWidth - 4 || left < 4 ? Math.min(right, window.innerWidth - m.offsetWidth - 4) : left) + 'px';
      m.style.top = Math.max(4, Math.min(r.top - 4, window.innerHeight - m.offsetHeight - 4)) + 'px';
      return m;
    }
    if (anchor && anchor.getBoundingClientRect){
      const r = anchor.getBoundingClientRect();
      m.style.left = Math.max(4, Math.min(r.left, window.innerWidth - m.offsetWidth - 4)) + 'px'; m.style.bottom = (window.innerHeight - r.top) + 'px';  // kept in the window
    } else {
      m.style.maxHeight = (window.innerHeight - 8) + 'px';  // as tall as the window lets it (a long right-click menu)
      const mw = m.offsetWidth, h = m.offsetHeight;
      let left = Math.max(4, Math.min(anchor.x, window.innerWidth - mw - 4));
      const below = window.innerHeight - anchor.y - 4, up = (anchor.top != null ? anchor.top : anchor.y) - 4;
      // menus opened from a card's header: avoid covering the chart when there is room above or beside the card
      let av = anchor.avoid || null;
      if (!av && anchor.x != null && anchor.y != null){
        const probe = document.elementFromPoint(
          Math.max(0, Math.min(window.innerWidth - 1, anchor.x + 2)),
          Math.max(0, Math.min(window.innerHeight - 1, anchor.top != null ? anchor.top + 2 : anchor.y - 6))
        );
        const hd = probe && probe.closest && probe.closest('.dd-head');
        const cd = hd && hd.closest('.dd-card');
        if (cd) av = cd.getBoundingClientRect();
      }
      let top = null;
      if (av){
        const upRoom = (anchor.top != null ? anchor.top : av.top) - 4;
        const roomL = av.left - 6, roomR = window.innerWidth - av.right - 6;
        const onLeft = (anchor.x - av.left) <= (av.right - anchor.x);
        const narrow = (av.right - av.left) < 360;
        if (h <= upRoom - 4){
          top = upRoom - h;
        } else if (onLeft && roomL >= mw + 4){
          left = av.left - mw - 6; top = Math.max(4, Math.min(av.top, window.innerHeight - h - 4));
        } else if (!onLeft && roomR >= mw + 4){
          left = av.right + 6; top = Math.max(4, Math.min(av.top, window.innerHeight - h - 4));
        } else if (narrow && roomL >= mw + 4){
          left = av.left - mw - 6; top = Math.max(4, Math.min(av.top, window.innerHeight - h - 4));
        } else if (narrow && roomR >= mw + 4){
          left = av.right + 6; top = Math.max(4, Math.min(av.top, window.innerHeight - h - 4));
        }
      }
      if (top === null){
        // under the point; no room there (a card low in the window): above it (anchor.top: above the button that
        // opened it), never over the point where it would cover the button and the card
        if (h <= below) top = anchor.y;
        else if (h <= up - 4) top = up - h;
        // a right click (no button to keep in view): moved up over the point, the whole menu in the window, not
        // cut to the room below and scrolled
        else if (anchor.top == null && h <= window.innerHeight - 8) top = window.innerHeight - h - 4;
        else if (below >= up){ top = anchor.y; m.style.maxHeight = Math.max(80, below) + 'px'; }
        else { const hh = Math.max(80, up - 4); m.style.maxHeight = hh + 'px'; top = Math.max(4, up - Math.min(h, hh)); }
      }
      m.style.left = Math.max(4, Math.min(left, window.innerWidth - mw - 4)) + 'px';
      m.style.top = Math.max(4, top) + 'px';
    }
    // one closer at a time: a closer left by an earlier menu (its entry was clicked) closed the next menu as it opened
    if (DD._menuCloser){ document.removeEventListener('click', DD._menuCloser); DD._menuCloser = null; }
    setTimeout(function(){
      const f = function(ev){
        if (ev.target.closest && ev.target.closest('.dd-menu')) return;
        document.querySelectorAll('.dd-menu').forEach(function(o){ o.remove(); });
        document.removeEventListener('click', f); if (DD._menuCloser === f) DD._menuCloser = null;
      };
      DD._menuCloser = f; document.addEventListener('click', f);
    }, 0);
    return m;
  }
  DD.webMenu = menu;
  // the button of the menu shown clicked again: the menu closes, its button's own handler never runs (it opened it
  // again, at once or through Python). Seen before any handler, for every menu of the page; the button clicked is
  // kept for the menu it may open (menu: m._opener)
  if (!DD._menuToggle){
    DD._menuToggle = true;
    const OPENER = 'button, .dd-pill, .dd-tb, .dd-btn, [role="button"]';
    document.addEventListener('click', function(e){
      const src = e.target && e.target.closest ? e.target.closest(OPENER) : null;
      const open = document.querySelector('.dd-menu:not(.dd-submenu)');
      if (src && open && open._opener === src){
        document.querySelectorAll('.dd-menu').forEach(function(o){ o.remove(); });
        DD._menuAnchor = null; DD._lastOpener = null;
        e.stopPropagation(); e.preventDefault();
        return;
      }
      DD._lastOpener = src ? {el: src, t: performance.now()} : null;
    }, true);
    document.addEventListener('contextmenu', function(){ DD._lastOpener = null; }, true);
  }

  // Reusable Anki search filter popover (used by Deep Dive's bottom bar and by Pinned widgets in pinned.js)
  const QUICK_FILTERS = ['is:leech', 'flag:1', 'prop:lapses>3', 'prop:ivl>=21', '-is:suspended'];
  DD.openSearchPopover = function(anchor, currentQuery, recentList, resolveFn, onApply){
    const open = document.querySelector('.dd-fltpop');
    document.querySelectorAll('.dd-menu').forEach(function(o){ o.remove(); });
    if (open && open._anchor === anchor) return;
    const pop = document.createElement('div');
    pop.className = 'dd-menu dd-fltpop';
    pop._anchor = anchor;
    pop.innerHTML =
      '<div class="dd-flt-head">' + icon('filter', 13) + '<span>' + DD.t('Search Filter') + '</span></div>' +
      '<div class="dd-flt-row">' +
        '<input class="dd-flt-inp" type="text" spellcheck="false" placeholder="tag:kanji  prop:lapses>3  flag:1">' +
        '<button class="dd-flt-go" type="button">' + DD.t('Apply') + '</button>' +
      '</div>' +
      '<div class="dd-flt-status"></div>' +
      '<div class="dd-flt-chips"></div>' +
      '<div class="dd-flt-recent" style="display:none"></div>' +
      '<div class="dd-flt-foot">' +
        '<span class="dd-flt-hint">' + DD.t('Same syntax as the Browser') + '</span>' +
        '<button class="dd-flt-clr" type="button">' + DD.t('Clear') + '</button>' +
      '</div>';
    if (DD.menuStyle) DD.menuStyle(pop);
    document.body.appendChild(pop);
    const inp = pop.querySelector('.dd-flt-inp');
    const goBtn = pop.querySelector('.dd-flt-go');
    const clrBtn = pop.querySelector('.dd-flt-clr');
    const status = pop.querySelector('.dd-flt-status');
    const chipsEl = pop.querySelector('.dd-flt-chips');
    const recEl = pop.querySelector('.dd-flt-recent');
    inp.value = currentQuery || '';
    clrBtn.style.display = currentQuery ? '' : 'none';

    function close(){
      pop.remove();
      document.removeEventListener('mousedown', away, true);
    }
    function setStatus(text, isErr){
      status.textContent = text || '';
      status.classList.toggle('err', !!isErr);
    }
    function submit(q){
      const val = String(q == null ? inp.value : q).trim();
      goBtn.disabled = true;
      setStatus(val ? DD.t('Checking...') : '', false);
      Promise.resolve(resolveFn(val)).then(function(res){
        goBtn.disabled = false;
        if (!res || !res.ok){
          setStatus((res && res.error) || DD.t('Invalid search query'), true);
          return;
        }
        close();
        onApply(res);
      }).catch(function(err){
        goBtn.disabled = false;
        setStatus(String(err || 'Error'), true);
      });
    }

    QUICK_FILTERS.forEach(function(q){
      const c = document.createElement('button');
      c.type = 'button'; c.className = 'dd-flt-chip'; c.textContent = q;
      c.onclick = function(){
        const cur = inp.value.trim();
        inp.value = cur ? (cur + ' ' + q) : q;
        if (!DD.isTouch()) inp.focus();  // a phone: no keyboard over the popup for a chip
      };
      chipsEl.appendChild(c);
    });

    const rec = (recentList || []).filter(Boolean);
    if (rec.length){
      recEl.style.display = '';
      const lbl = document.createElement('div');
      lbl.className = 'dd-flt-rlbl'; lbl.textContent = DD.t('Recent');
      recEl.appendChild(lbl);
      rec.slice(0, 6).forEach(function(q){
        const b = document.createElement('div');
        b.className = 'dd-mi dd-flt-ritem' + (q === currentQuery ? ' on' : '');
        b.textContent = q; b.title = q;
        b.onclick = function(){ submit(q); };
        recEl.appendChild(b);
      });
    }

    goBtn.onclick = function(){ submit(); };
    clrBtn.onclick = function(){ submit(''); };
    inp.addEventListener('keydown', function(ev){
      if (ev.key === 'Escape'){ close(); return; }
      if (ev.key === 'Enter'){ ev.preventDefault(); submit(); }
    });
    function away(ev){
      if (!pop.contains(ev.target) && (!anchor || !anchor.contains || !anchor.contains(ev.target))){
        close();
      }
    }
    document.addEventListener('mousedown', away, true);

    const pw = pop.offsetWidth || 350, ph = pop.offsetHeight || 190;
    const vw = window.innerWidth, vh = window.innerHeight;
    let av = (anchor && anchor.avoid) || null;
    if (!av && anchor && anchor.closest){
      const cd = anchor.closest('.dd-card, .ddp-box');
      if (cd) av = cd.getBoundingClientRect();
    }
    if (av){
      // Avoid covering the widget: try above -> below -> beside (right/left) -> fallback
      const ax = (anchor && anchor.getBoundingClientRect) ? anchor.getBoundingClientRect().left
        : (anchor && anchor.x != null ? anchor.x : av.left);
      let left = Math.max(6, Math.min(ax, vw - pw - 6)), top = null;
      if (av.top - 8 >= ph){
        top = av.top - ph - 6;
      } else if (vh - av.bottom - 8 >= ph){
        top = av.bottom + 6;
      } else if (vw - av.right - 8 >= pw){
        left = av.right + 6;
        top = Math.max(6, Math.min(av.top, vh - ph - 6));
      } else if (av.left - 8 >= pw){
        left = av.left - pw - 6;
        top = Math.max(6, Math.min(av.top, vh - ph - 6));
      } else {
        top = Math.max(6, Math.min((vh - ph) / 2, vh - ph - 6));
      }
      pop.style.left = Math.max(6, Math.min(left, vw - pw - 6)) + 'px';
      pop.style.top = Math.max(6, Math.min(top, vh - ph - 6)) + 'px';
    } else if (anchor && anchor.getBoundingClientRect){
      const r = anchor.getBoundingClientRect();
      pop.style.left = Math.max(6, Math.min(r.left, vw - pw - 6)) + 'px';
      if (r.top > ph + 12){
        pop.style.bottom = (vh - r.top + 4) + 'px';
      } else {
        pop.style.top = Math.min(vh - ph - 6, r.bottom + 4) + 'px';
      }
    } else {
      const x = anchor && anchor.x != null ? anchor.x : (vw - pw) / 2;
      const y = anchor && anchor.y != null ? anchor.y : (vh - ph) / 2;
      pop.style.left = Math.max(6, Math.min(x, vw - pw - 6)) + 'px';
      pop.style.top = Math.max(6, Math.min(y, vh - ph - 6)) + 'px';
    }
    // on a phone the field waits for a tap: focused at once, it brought the keyboard up over the popup
    if (!DD.isTouch()){ inp.focus(); inp.select(); }
  };

  DD.start = function(boot){
    // dev trace (PERF boot): how long each part of this start took, logged at its end
    const bootT = [[performance.now(), 'start']], bm = function(l){ bootT.push([performance.now(), l]); };
    DD._bootMounts = [];
    // the whole window is the page: it never scrolls (a menu or tooltip past an edge made scrollbars flash around it)
    document.documentElement.classList.add('dd-window');
    DD.settings = boot.settings;
    DD.setI18n(boot.i18n);  // the window's texts in the add-on's language (dd-core.js)
    DD.setAnim(boot.anim);  // Settings > General > Animations (for the Deep Dive window)
    DD._introTempo = DD.INTRO_TEMPO;  // its charts' intros calmer than the main screen's (dd-core.js DD.intro)
    DD.setTheme(boot.theme);
    bm('i18n+theme');
    const state = {deck: boot.deck, span: boot.span, widgets: boot.widgets, cards: {}, deckTitle: boot.deck_title || '',
      searchQuery: '', searchCount: null, recentSearches: (boot.recent_searches || []).slice()};
    // a chart's options icon (discrete.js DD.optionsPill): its entries join the chart's own (ownOpt). Set before any
    // chart is mounted, otherwise the first ones draw the old icon. The icons wait for the end of this start (the menu reads
    // the lists set further down), then come on the charts mounted until then
    let ownReady = false;
    DD.ownOptions = function(head){ ownOpt(head.closest('.dd-card')); };
    // the deck shown as View by Deck takes it: the collection for the Total row or several decks picked together
    function deckViewKey(){ return state.deck === 0 || Array.isArray(state.deck) ? 'collection' : String(state.deck); }
    DD.statGap = 12;  // web: the stat cards spaced as the charts (the grid's gap), see stats.js layout
    DD.state = state;
    const root = document.getElementById('dd-root');
    const spanList = function(){ return (boot.spans && boot.spans.length) ? boot.spans : PERIODS.map(function(p){ return [p[1], p[0], null]; }); };
    const periodLabel = function(){ const p = spanList().filter(function(q){ return q[1] === state.span; })[0] || PERIODS.map(function(p){ return [p[1], p[0]]; }).filter(function(q){ return q[1] === state.span; })[0]; return p ? p[0] : ''; };
    root.innerHTML =
      '<div class="dd-shell">' +
      '<div class="dd-sc-host"></div>' +
      // web: the deck's title and the charts' buttons share the table's bar
      '<div class="dd-gridwrap"><div class="dd-grid"></div></div>' +
      '<div class="dd-tblhost"></div>' +
      '<div class="dd-drawerrow"><span class="dd-dtitle"></span>' +
      '<div class="dd-drawer" title="Open or close the table"><span class="dd-dr-ico">' + icon('table', 14) + '</span><span class="dd-dr-text">Table</span><button class="dd-dr-chev">' + icon('chevup', 12) + '</button></div>' +  // Auto-close only on the open table (it acts there)
      '<span class="dd-tbgroup">' +
      '<button class="dd-tb dd-rzoom" title="Reset All Zooms" style="display:none">' + icon('reset', 14) + '</button>' +
      // web: what each button does, said on it
      '<button class="dd-tb dd-cols" title="Charts per row (Ctrl + wheel)">' + icon('grid', 14) + '<span class="dd-cols-n"></span>' + icon('chevdown', 10) + '</button>' +
      '<button class="dd-tb dd-charts" title="Add or Remove Charts, Stat Cards and Texts">' + icon('chartplus', 16) + '<span>Add / Remove</span></button>' +
      '<button class="dd-tb dd-set" title="Options shared by every chart (zoom link, binning, stats...)">' + icon('wrench', 14) + '<span>Chart Options</span>' + icon('chevdown', 10) + '</button></span></div>' +  // no gear: the window's Settings has it; a wrench, its name left out in a narrow window
      '<div class="dd-bottom">' +
      // View by Deck / Time acts on the table only: it joins the table's buttons on its foot once the table is mounted
      '<button class="dd-tbl-opt dd-view"></button>' +
      '<button class="dd-btn dd-deck">' + icon('layers', 16) + '<span>Deck</span></button>' +
      '<button class="dd-btn dd-span">' + icon('calendar', 16) + '<span>Time Span</span></button>' +
      '<button class="dd-btn dd-filter" title="Filter charts &amp; stats with search syntax">' + icon('filter', 15) + '<span class="dd-flt-txt">Filter</span><span class="dd-flt-x" title="Clear filter" style="display:none">&times;</span></button>' +
      '<button class="dd-btn dd-table-btn" title="Open or close the table">' + icon('table', 16) + '<span>' + DD.t('Table') + '</span></button>' +
      '<span class="dd-spacer"></span>' +
      '<input class="dd-search" placeholder="Search decks...">' +
      '<button class="dd-btn dd-export">' + icon('save', 16) + '<span>Export</span></button>' +
      '<button class="dd-btn dd-settings">' + icon('gear', 16) + '<span>Settings</span></button>' +
      // web: Support / Rate / GitHub in one menu (three square buttons took room on the bar)
      '<button class="dd-btn dd-sq dd-links" title="Support, rate, GitHub">' + icon('thumb', 16) + '</button>' +
      '</div></div>';
    const grid = root.querySelector('.dd-grid');
    const tblHost = root.querySelector('.dd-tblhost'), drawerRow = root.querySelector('.dd-drawerrow');
    const dr = boot.drawer || {};
    const drawer = {open: false, autoClose: dr.auto_close !== false, stack: dr.stack | 0, anim: null, tm: 0};
    const ANIM_MS = 220, FLOOR = 220, CLOSE_DRAG = 40;
    const bottomEl = root.querySelector('.dd-bottom');
    // the table's layout is the bar's one control (dd-seg: full table / drawer / charts alone): no handle of its own
    function setAutoPills(){ root.querySelectorAll('.dd-autoclose').forEach(function(b){ b.classList.toggle('on', drawer.autoClose); }); }
    function areaH(){ return window.innerHeight - bottomEl.offsetHeight; }
    function panelH(){
      const H = areaH(), max = Math.max(FLOOR, H - 80);
      if (drawer.stack) return Math.min(Math.max(drawer.stack, FLOOR), max);
      let h = Math.min(Math.max(Math.round(H * 0.55), FLOOR), max);
      const panel = tblHost.querySelector('.dd-tbl-panel');
      const content = panel ? (panel.querySelector('.dd-tbl').offsetHeight + panel.querySelector('.dd-tbl-foot').offsetHeight + 4) : 0;
      if (content) h = Math.min(h, Math.max(content, 130));
      return h;
    }
    function place(){ tblHost.style.bottom = bottomEl.offsetHeight + 'px'; }
    // web: the table's bar says what is shown, "Deck (PERIOD) · reviews · retention" (it said "Table: <tab>")
    let drSum = '';
    function drText(){
      // in the bottom bar, next to the Deck and Time Span buttons that name the deck and the period: just "Table"
      const t = root.querySelector('.dd-dr-text'); if (!t) return;
      t.textContent = DD.t('Table');
    }
    // the charts' buttons (zoom, charts per row, Add / Remove, options): in the bottom bar, the table open or not
    const tbGroup = root.querySelector('.dd-tbgroup');
    // the table's tabs scroll when there are many: their edges fade then, apart from the buttons on both sides
    (function(){
      const tabs = function(){ return tblHost.querySelector('.dd-tbl-tabs'); };
      const check = function(){ const t = tabs(); if (t) t.classList.toggle('dd-over', t.scrollWidth > t.clientWidth + 1); };
      const t0 = tabs(); if (!t0){ setTimeout(function(){ const t = tabs(); if (t) watch(t); }, 0); } else watch(t0);
      function watch(t){
        if (window.ResizeObserver) new ResizeObserver(check).observe(t);
        if (window.MutationObserver) new MutationObserver(check).observe(t, {childList: true, subtree: true});
        check();
      }
    })();
    function toolsTo(){
      // in the bottom bar, right before Export, the table open or not (they act on the charts)
      const ex = bottomEl.querySelector('.dd-export');
      if (tbGroup.parentNode !== bottomEl || tbGroup.nextElementSibling !== ex) bottomEl.insertBefore(tbGroup, ex);
    }
    function setBar(){
      const t = root.querySelector('.dd-dr-chev'); if (t) t.innerHTML = icon(drawer.open ? 'chevdown' : 'chevup', 12);
      const d = root.querySelector('.dd-drawer'); if (d) d.classList.toggle('on', drawer.open);
    }
    let openTable = function(open, o){
      o = o || {};
      if (open === drawer.open) return;
      drawer.open = open; clearTimeout(drawer.tm);
      place();
      const instant = !!o.instant || window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      if (open){
        tblHost.style.display = 'block'; tblHost.style.height = 'auto';
        tblHost.style.height = panelH() + 'px';
        drawerRow.style.visibility = 'hidden';
        tblHost.style.transition = 'none'; tblHost.style.transform = 'translateY(100%)';
        void tblHost.offsetHeight;
        tblHost.style.transition = instant ? 'none' : 'transform ' + ANIM_MS + 'ms cubic-bezier(.215,.61,.355,1)';
        tblHost.style.transform = 'none';
      } else {
        tblHost.style.transition = instant ? 'none' : 'transform ' + ANIM_MS + 'ms cubic-bezier(.215,.61,.355,1)';
        tblHost.style.transform = 'translateY(100%)';
        drawerRow.style.visibility = '';  // back at once: the panel slides away over it
        const done = function(){ if (!drawer.open){ tblHost.style.display = 'none'; } };
        if (instant) done(); else drawer.tm = setTimeout(done, ANIM_MS + 20);
      }
      setBar();
      if (o.remember !== false) DD.call('set_drawer', {open: open}).catch(function(){});
    };
    // the span of a table tab becomes the span shown, when it is one of the Time Span entries (custom spans are left alone)
    function takeSpan(rg){
      if (rg === undefined || rg === null || isNaN(+rg)) return false;
      const hit = (boot.spans || []).filter(function(p){ return +p[1] === +rg && (p[2] === null || p[2] === undefined); })[0];
      if (!hit || state.span === +rg) return false;
      state.span = +rg; return true;
    }
    let tblInst = null;
    // Settings > Show Table: off, the window has the charts only. The table is mounted (and loaded) only once shown;
    // its handle on the bar, the layout buttons, the deck search and the table's exports are hidden while it is off
    let tableOn = dr.show !== false;
    function mountTable(boot0){
      if (tblInst || !DD.table) return;
      tblInst = DD.table.mount(tblHost, {selectedDid: boot.deck, initial: boot.table,
        onHide: function(){ openTable(false); },
        onSpan: function(sp){ state.span = sp; setTitle(); refresh(); if (tableOnly) setLayout(1); else if (drawer.autoClose && drawer.open) openTable(false, {instant: true, remember: false}); },
        onDeckTab: function(k){ if (DD.onDeckPicked) DD.onDeckPicked(k === 'collection' ? 0 : (k === '__deleted_cards__' ? -1 : k)); },
        onTimeTab: function(rg){ if (takeSpan(rg)) DD.onDeckPicked(state.deck); },
        onSummary: function(title, sum){ drSum = sum || ''; drText(); },
        onPick: function(did, name, rg){ takeSpan(rg); if (DD.onDeckPicked) DD.onDeckPicked(did); if (tableOnly) setLayout(1); else if (drawer.autoClose && drawer.open) openTable(false, {instant: true, remember: false}); }});
      tblHost.insertAdjacentHTML('afterbegin', '<div class="dd-tbl-edge"></div>');
      const vb = root.querySelector('.dd-view'), tf = tblHost.querySelector('.dd-tbl-foot');
      const fr = tf && tf.querySelector('.dd-tbl-fr');
      if (vb && fr) fr.insertBefore(vb, fr.firstChild);  // first of the table's buttons, right of the tabs
      tblHost.style.display = 'none'; tblHost.style.transform = 'translateY(100%)'; place();
      root.querySelector('.dd-drawer').onclick = function(e){ if (e.target.closest('.dd-autoclose')) return; openTable(!drawer.open); };
      root.querySelectorAll('.dd-autoclose').forEach(function(b){
        b.onclick = function(e){ e.stopPropagation(); drawer.autoClose = !drawer.autoClose; setAutoPills(); DD.call('set_drawer', {auto_close: drawer.autoClose}).catch(function(){}); };
      });
      root.querySelectorAll('.dd-tbl-full').forEach(function(b){
        b.onclick = function(e){ e.stopPropagation(); setLayout(tableOnly ? 1 : 0); };
      });
      setAutoPills(); setBar();
      if (dr.open && boot0) openTable(true, {instant: true, remember: false});
      // drag the top edge to resize; dragged well below the smallest size, it closes
      const edge = tblHost.querySelector('.dd-tbl-edge');
      edge.addEventListener('pointerdown', function(ev){
        if (ev.button !== 0) return;
        ev.preventDefault(); edge.setPointerCapture(ev.pointerId);
        const before = drawer.stack; let closeOnRelease = false;
        tblHost.style.transition = 'none';
        function mv(e){
          const size = (window.innerHeight - bottomEl.offsetHeight) - e.clientY;
          closeOnRelease = size < FLOOR - CLOSE_DRAG;
          drawer.stack = Math.min(Math.max(size, FLOOR), Math.max(FLOOR, areaH() - 80));
          tblHost.style.height = drawer.stack + 'px';
        }
        function up(){
          edge.removeEventListener('pointermove', mv); edge.removeEventListener('pointerup', up);
          if (closeOnRelease){ drawer.stack = before; openTable(false); }
          else DD.call('set_drawer', {size: Math.round(drawer.stack)}).catch(function(){});
        }
        edge.addEventListener('pointermove', mv); edge.addEventListener('pointerup', up);
      });
      // a click on the charts closes the open table (the click still goes through)
      document.addEventListener('pointerdown', function(e){
        if (!drawer.open) return;
        if (e.target.closest('.dd-tblhost,.dd-menu,.dd-drawerrow,.dd-bottom')) return;
        if (e.target.closest('.dd-sc-host,.dd-gridwrap')) openTable(false, {remember: false});
      }, true);
      document.addEventListener('keydown', function(e){
        if (!tableOn) return;
        if (e.key === 'Escape' && drawer.open){ openTable(false); return; }
        const tg = e.target && e.target.tagName;
        if (tg === 'INPUT' || tg === 'TEXTAREA' || e.ctrlKey || e.metaKey || e.altKey) return;
        if (dr.shortcut && e.key.toLowerCase() === String(dr.shortcut).toLowerCase()){
          e.preventDefault(); openTable(!drawer.open);
          if (drawer.open){ const s = root.querySelector('.dd-search'); if (s){ s.focus(); s.select(); } }
        }
      });
      window.addEventListener('resize', function(){ if (drawer.open){ place(); tblHost.style.height = panelH() + 'px'; } });
    }
    // The Table button on the bottom bar opens/closes the table; Full Table is in the table's footer beside Auto-close.
    const shell = root.querySelector('.dd-shell'), btnTable = root.querySelector('.dd-table-btn');
    let tableOnly = false;
    let chartFilterQ = '', tableFilterQ = '';
    function applyChartFilter(q){
      chartFilterQ = String(q || '');
      const needle = chartFilterQ.trim().toLowerCase();
      Object.keys(state.cards).forEach(function(id){
        const c = state.cards[id]; if (!c || !c.card) return;
        if (!needle){ c.card.classList.remove('dd-cfilt-out'); return; }
        const t = c.card.querySelector('.dd-title');
        const hay = ((t ? t.textContent : '') + ' ' + (c.card.dataset.type || '').replace(/_/g, ' ') + ' ' + (c.card.classList.contains('dd-text') ? c.card.textContent : '')).toLowerCase();
        c.card.classList.toggle('dd-cfilt-out', hay.indexOf(needle) < 0);
      });
      if (typeof layoutGrid === 'function') layoutGrid();
      chartFinds(needle);
    }
    // Find chart: under the charts kept, the ones of the gallery not in Deep Dive yet that match (by their name, English
    // name, group or type), each with Add; "No chart found" when nothing matches at all
    let catalog = null, catalogAsk = null;
    function chartFinds(needle){
      const wrap = root.querySelector('.dd-gridwrap');
      let box = wrap && wrap.querySelector('.dd-cfind');
      if (!needle){ if (box) box.remove(); return; }
      if (!catalog){
        if (!catalogAsk) catalogAsk = DD.call('chart_catalog', {}).then(function(r){ catalog = r || []; }).catch(function(){ catalog = []; })
          .then(function(){ catalogAsk = null; chartFinds(chartFilterQ.trim().toLowerCase()); });
        return;
      }
      const shownTypes = {};
      Object.keys(state.cards).forEach(function(id){ const c = state.cards[id]; if (c && c.card) shownTypes[c.card.dataset.type] = 1; });
      const found = catalog.filter(function(c){
        if (c.shown || shownTypes[c.type]) return false;
        return (c.name + ' ' + c.en + ' ' + c.group + ' ' + c.type.replace(/_/g, ' ')).toLowerCase().indexOf(needle) >= 0;
      });
      const anyShown = !!grid.querySelector('.dd-card:not(.dd-cfilt-out)');
      if (!found.length && anyShown){ if (box) box.remove(); return; }
      if (!box){ box = document.createElement('div'); box.className = 'dd-cfind'; wrap.appendChild(box); }
      box.innerHTML = '';
      const head = document.createElement('div');
      head.className = 'dd-cfind-head';
      head.textContent = DD.t(found.length ? 'Not in Deep Dive yet' : 'No chart found');
      box.appendChild(head);
      found.forEach(function(c){
        const row = document.createElement('div');
        row.className = 'dd-cfind-row';
        const nm = document.createElement('span'); nm.className = 'dd-cfind-name'; nm.textContent = c.name; nm.setAttribute('data-nt', '');
        const gr = document.createElement('span'); gr.className = 'dd-cfind-group'; gr.textContent = c.group; gr.setAttribute('data-nt', '');
        const add = document.createElement('button');
        add.className = 'dd-btn dd-cfind-add';
        add.innerHTML = icon('plus', 13) + '<span></span>';
        add.lastChild.textContent = DD.t('Add');
        add.title = DD.t('Add this chart to Deep Dive');
        add.addEventListener('click', function(){
          add.disabled = true;
          // Python saves it and pushes rebuild: it comes in with the others, kept by the filter (it matches)
          DD.call('add_chart', {type: c.type}).then(function(ok){ if (ok) c.shown = true; else add.disabled = false; })
            .catch(function(){ add.disabled = false; });
        });
        row.appendChild(nm); row.appendChild(gr); row.appendChild(add);
        box.appendChild(row);
      });
    }
    function syncSearchMode(){
      const sr = root.querySelector('.dd-search'); if (!sr) return;
      const open = tableOn && (tableOnly || drawer.open);
      sr.placeholder = open ? (state.view === 'deck' ? DD.t('Search decks...') : DD.t('Filter rows...')) : DD.t('Find chart...');
      const want = open ? tableFilterQ : chartFilterQ;
      if (sr.value !== want) sr.value = want;
    }
    function syncLayoutBtns(){
      const open = tableOnly || drawer.open;
      if (btnTable) btnTable.classList.toggle('on', open);
      root.querySelectorAll('.dd-tbl-full').forEach(function(b){ b.classList.toggle('on', tableOnly); });
      // the table shown (drawer or alone): its search box switches between table rows and charts
      shell.classList.toggle('dd-tblopen', tableOn && open);
      syncSearchMode();
    }
    function fitTableOnly(){
      const top = root.querySelector('.dd-sc-host').getBoundingClientRect().bottom + 8;
      tblHost.style.height = Math.max(200, areaH() - top) + 'px';
    }
    function setLayout(n){
      if (n === 0){
        if (tableOnly) return;
        const wasOpen = drawer.open && tblHost.style.display !== 'none';
        tableOnly = true; shell.classList.add('tableonly');
        drawer.open = true; drawer.restore = false; clearTimeout(drawer.tm);
        place(); tblHost.style.display = 'block';
        const anim = !window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        if (wasOpen && anim){
          // from the drawer: its top goes up to the full height
          const h0 = tblHost.offsetHeight;
          tblHost.style.transition = 'none'; tblHost.style.transform = 'none'; tblHost.style.height = h0 + 'px'; void tblHost.offsetHeight;
          tblHost.style.transition = 'height ' + ANIM_MS + 'ms cubic-bezier(.215,.61,.355,1)';
          fitTableOnly();
        } else if (anim){
          // from the charts alone: it rises from the bottom
          fitTableOnly(); tblHost.style.transition = 'none'; tblHost.style.transform = 'translateY(100%)'; void tblHost.offsetHeight;
          tblHost.style.transition = 'transform ' + ANIM_MS + 'ms cubic-bezier(.215,.61,.355,1)'; tblHost.style.transform = 'none';
        } else { tblHost.style.transition = 'none'; tblHost.style.transform = 'none'; fitTableOnly(); }
        drawerRow.style.visibility = 'hidden';
      } else {
        if (tableOnly){
          tableOnly = false; shell.classList.remove('tableonly');
          drawer.open = true;
          if (n === 1){
            // from the full table to the drawer: its top comes down to the drawer's height (it does not leave and come
            // back from the bottom)
            const h0 = tblHost.offsetHeight, h1 = panelH();
            tblHost.style.transition = 'none'; tblHost.style.height = h0 + 'px'; void tblHost.offsetHeight;
            tblHost.style.transition = 'height ' + ANIM_MS + 'ms cubic-bezier(.215,.61,.355,1)';
            tblHost.style.height = h1 + 'px';
            setBar(); DD.call('set_drawer', {open: true}).catch(function(){});
            syncLayoutBtns(); return;
          }
          // to the charts alone: the full table slides down out of the window
          drawerRow.style.visibility = '';
        }
        openTable(n === 1);
      }
      syncLayoutBtns();
    }
    if (btnTable) btnTable.onclick = function(){
      setLayout(tableOnly || drawer.open ? 2 : 1);
    };
    const _open = openTable;
    openTable = function(open, o){ if (tableOnly && open === false){ setLayout(2); return; } _open(open, o); syncLayoutBtns(); };
    syncLayoutBtns();
    // Show Table turned on or off in Settings: the table goes away (closed first when it was open) or is mounted now
    function setTableOn(on){
      if (on === tableOn && (!on || tblInst)) return;
      tableOn = on; shell.classList.toggle('dd-notable', !on);
      if (on){
        mountTable(false);
        if (tblInst && state.view === 'deck') tblInst.setMode('deck', deckViewKey(), String(state.span));
        syncLayoutBtns(); return;
      }
      if (tableOnly) setLayout(2); else if (drawer.open) openTable(false, {instant: true, remember: false});
      const s = root.querySelector('.dd-search'); if (s && s.value){ s.value = ''; if (tblInst) tblInst.setFilter(''); }
    }
    shell.classList.toggle('dd-notable', !tableOn);
    toolsTo();
    bm('bar');
    if (tableOn) mountTable(true);
    bm('table');
    window.addEventListener('resize', function(){ if (tableOnly) fitTableOnly(); });
    // the drawer's height follows its table (its rows arrive after it opens)
    (function(){
      const refit = function(){
        if (!drawer.open || tableOnly || drawer.stack || tblHost.style.display === 'none') return;
        const h = panelH(), cur = parseFloat(tblHost.style.height) || 0;
        if (Math.abs(h - cur) > 1) tblHost.style.height = h + 'px';
      };
      if (!window.ResizeObserver) return;
      const ro = new ResizeObserver(function(){ requestAnimationFrame(refit); });
      const watch = function(){ tblHost.querySelectorAll('.dd-tbl, .dd-tbl-foot').forEach(function(t){ if (!t._ddRo){ t._ddRo = true; ro.observe(t); } }); };
      new MutationObserver(function(){ watch(); requestAnimationFrame(refit); }).observe(tblHost, {childList: true, subtree: true});
      watch();
    })();
    const scHooks = {
      onLayout: function(order, rows){ DD.call('stat_layout', {order: order, rows: rows}).catch(function(){}); },
      onMenu: function(key, card, x, y, api){
        const lines = api.lines;
        let li = -1; lines.forEach(function(g, i){ if (g.indexOf(key) >= 0) li = i; });
        const items = [['color', DD.t('Change {name} Color...', {name: card.label}), undefined, 'palette']];
        if (card.own_color) items.push(['rcolor', DD.t('Use Shared {name} Color', {name: card.label}), undefined, 'reset']);
        // Reviews/Day and Time/Day: the same over the days studied only (the card becomes Reviews/Active Day)
        const twin = card.active_twin;
        if (twin) items.push('sep', ['active', 'Active days only', !!twin.active, null, false]);
        const curIco = (card.style && card.style.icon_mode) || (DD.theme && DD.theme.stat && DD.theme.stat.icon_mode) || 'inline';
        const curPos = (card.style && card.style.icon_pos) || (DD.theme && DD.theme.stat && DD.theme.stat.icon_pos) || 'tl';
        items.push('sep', ['pin', DD.t('Pin {name}', {name: card.label}), undefined, 'pin'], ['remove', 'Remove', undefined, 'trash'], 'sep',
          ['settings', 'Settings', undefined, 'gear'],
          ['icon', 'Icon', undefined, null, false, [
            ['ico:off', 'Off', curIco === 'off', null, 'radio'],
            ['ico:inline', 'Next to title', curIco === 'inline', null, 'radio'],
            ['ico:watermark', 'Watermark', curIco === 'watermark', null, 'radio'],
            'sep',
            ['ipos', 'Position', undefined, null, false, [
              ['ipos:tl', 'Top Left', curPos === 'tl', null, 'radio'],
              ['ipos:tr', 'Top Right', curPos === 'tr', null, 'radio'],
              ['ipos:bl', 'Bottom Left', curPos === 'bl', null, 'radio'],
              ['ipos:br', 'Bottom Right', curPos === 'br', null, 'radio'],
            ], curIco !== 'watermark'],
          ]],
          // Stat_Num_Anim: one setting for every stat card (also in Settings > General > Animations)
          numAnimItem(), 'sep',
          ['add', 'Add Stat Card...', undefined, 'plus'], 'sep', ['down', 'Move to next line', undefined, null]);
        if (li > 0) items.push(['up', 'Move up a line', undefined, null]);
        menu({x: x, y: y}, items, function(k){
          if (k === 'color'){
            const inp = document.createElement('input'); inp.type = 'color'; inp.value = card.color && /^#[0-9a-f]{6}$/i.test(card.color) ? card.color : '#888888';
            inp.style.cssText = 'position:fixed;left:' + x + 'px;top:' + y + 'px;opacity:0;width:1px;height:1px';
            document.body.appendChild(inp);
            inp.addEventListener('change', function(){ DD.call('stat_color', {key: key, color: inp.value}).then(function(){ refresh(); }); inp.remove(); });
            inp.addEventListener('blur', function(){ setTimeout(function(){ inp.remove(); }, 200); });
            inp.click();
          } else if (k === 'rcolor') DD.call('stat_color', {key: key, color: null}).then(function(){ refresh(); });
          else if (k === 'active') DD.call('stat_swap', {key: key}).then(function(){ refresh(); });
          else if (k === 'pin') DD.call('stat_pin', {key: key, label: card.label, span: state.span}).then(function(){ toast(DD.t('{name} pinned to the main menu', {name: card.label})); });
          else if (k === 'remove') DD.call('stat_hide', {key: key, show: false}).then(function(){ refresh(); toast('Widget removed'); });
          else if (k === 'add') DD.call('open_gallery', {family: 'stat'});
          else if (k === 'settings') DD.call('stat_settings', {key: key, label: card.label}).then(function(){ refresh(); });
          else if (typeof k === 'string' && k.indexOf('ico:') === 0){
            const md = k.slice(4), posEl = document.querySelector('.dd-mi[data-k="ipos"]');
            if (posEl) posEl.classList.toggle('off', md !== 'watermark');
            DD.call('stat_icon', {key: key, mode: md}).then(function(){
              if (scInst) DD.call('stats', {deck: state.deck, span: state.span, query: state.searchQuery || ''}).then(function(s){ scInst.update(s); }).catch(function(){});
            });
          }
          else if (typeof k === 'string' && k.indexOf('ipos:') === 0) DD.call('stat_icon', {key: key, pos: k.slice(5)}).then(function(){
            if (scInst) DD.call('stats', {deck: state.deck, span: state.span, query: state.searchQuery || ''}).then(function(s){ scInst.update(s); }).catch(function(){});
          });
          else if (animChoice(k)){ /* done */ }
          else if (k === 'down' || k === 'up'){
            const ls = lines.map(function(g){ return g.filter(function(q){ return q !== key; }); });
            const to = k === 'down' ? li + 1 : li - 1;
            if (k === 'down' && !ls[li].length){ /* a card alone on its line: nothing below to move to */ }
            if (to >= ls.length) ls.push([key]); else ls[Math.max(0, to)].push(key);
            api.commit(ls);
          }
        });
      },
      intro: !boot.export,
    };
    const scInst = boot.stats ? DD.stats.mount(root.querySelector('.dd-sc-host'), boot.stats, boot.theme, scHooks) : null;
    const titleEl = root.querySelector('.dd-dtitle');
    // web: the Deck and Time Span buttons show what is shown (the deck, the period) instead of their names
    function setTitle(){
      const fq = state.searchQuery ? (' · ' + state.searchQuery) : '';
      titleEl.textContent = state.deckTitle + ' (' + periodLabel().toUpperCase() + ')' + fq;
      drText();
      const db = root.querySelector('.dd-deck span'), sb = root.querySelector('.dd-span span');
      if (db){ db.textContent = state.deckTitle || DD.t('Deck'); db.parentNode.title = DD.t('Deck: {name}', {name: state.deckTitle || ''}); }
      if (sb){ sb.textContent = periodLabel() || DD.t('Time Span'); sb.parentNode.title = DD.t('Time Span: {name}', {name: periodLabel()}); }
      fsChipText();
      const fb = root.querySelector('.dd-filter'), ft = fb && fb.querySelector('.dd-flt-txt'), fx = fb && fb.querySelector('.dd-flt-x');
      if (fb && ft && fx){
        const active = !!state.searchQuery;
        fb.classList.toggle('on', active);
        if (active){
          const shortQ = state.searchQuery.length > 22 ? (state.searchQuery.slice(0, 21) + '\u2026') : state.searchQuery;
          const cnt = state.searchCount != null ? (' (' + state.searchCount + ')') : '';
          ft.textContent = shortQ + cnt;
          fb.title = 'Search filter: ' + state.searchQuery + (state.searchCount != null ? (' — ' + state.searchCount + ' cards') : '');
          fx.style.display = '';
        } else {
          ft.textContent = DD.t('Filter');
          fb.title = DD.t('Filter charts & stats with Anki search syntax');
          fx.style.display = 'none';
        }
      }
    }
    setTitle();

    function addCard(w, data, animate){
      const card = document.createElement('div');
      card.className = 'dd-card'; card.dataset.type = w.type;
      if (isText(w.type)){
        // a text (charts/text.js): no title row, its sentence fills the card; dragged from anywhere on it, its "..."
        // on hover, only its width resized (its height is its sentence's)
        card.classList.add('dd-text');
        card.innerHTML = '<div class="dd-body"></div><button class="dd-more dd-tx-more" title="Options (or right click)">' + icon('dots', 14) + '</button><div class="dd-rsz dd-rsz-r" data-mode="r"></div>';
        grid.appendChild(card);
        let inst;
        try { inst = DD.charts.text.mount(card.querySelector('.dd-body'), {data: data, options: w.options, animate: false, head: null, type: w.type}); }
        catch (e){ DD.log('text mount: ' + (e && e.message || e)); inst = {update: function(){}, setTheme: function(){}, setOptions: function(){}, destroy: function(){}}; }
        let pend = 0;
        inst.onSize = function(){ if (!pend) pend = requestAnimationFrame(function(){ pend = 0; layoutGrid(); }); };
        // past _boot's first charts it has no data yet: lateData asks it with the others
        const entry = {card: card, inst: inst, late: data === undefined};
        const upd = inst.update;
        inst.update = function(d){ entry.late = false; upd.call(inst, d); };
        state.cards[w.id] = entry;
        if (animate && card.animate && DD.anim.on && DD.anim.appear) card.animate([{opacity: 0}, {opacity: 1}], {duration: 300, easing: 'ease-out'});
        return;
      }
      card.innerHTML = DD.headHtml(w.type) + '<div class="dd-body"></div><div class="dd-rsz dd-rsz-r" data-mode="r"></div><div class="dd-rsz dd-rsz-b" data-mode="b"></div><div class="dd-rsz dd-rsz-rb" data-mode="rb"></div>';
      grid.appendChild(card);
      // no data yet (_boot answers the first charts only, lateData asks the rest): an empty card for now, its
      // chart mounted when its data comes (its intro then, held while out of view)
      if (DD.charts[w.type] && data === undefined){
        const entry = {card: card, late: true};
        card.querySelector('.dd-body').innerHTML = DD.loadingPlaceholder();
        entry.inst = {update: function(d){
          if (state.cards[w.id] !== entry || !d) return;
          entry.late = false;
          const sk = card.querySelector('.dd-loading'); if (sk) sk.remove();
          mountChart(card, w, d, animate, entry);
        },
          setTheme: function(){}, setOptions: function(){}, destroy: function(){}};
        state.cards[w.id] = entry;
        return;
      }
      mountChart(card, w, data, animate, null);
    }
    function mountChart(card, w, data, animate, entry){
      const mod = DD.charts[w.type];
      let inst;
      if (mod){
        DD._mountEl = card;
        // Appearance Animations off (or no animations): the chart shows at once, its later changes still animate
        // as the transition setting says (the modules read ctx.animate again then)
        const intro = animate && DD.anim.on && DD.anim.appear;
        const mctx = {data: data, options: w.options, animate: intro, head: card.querySelector('.dd-head'), type: w.type,
          // the heatmap asks for another height (a mode, the month grid, a narrow card): its row follows
          // (a wide card keeps the row's own rule: nothing to lay out again)
          onNatural: w.type === 'heatmap' ? function(){
            const hi = state.cards[w.id] && state.cards[w.id].inst, nw = !!(hi && hi.narrow && hi.narrow());
            if (!nw && !mctx._narrow) return;
            mctx._narrow = nw;
            if (!mctx._pend) mctx._pend = requestAnimationFrame(function(){ mctx._pend = 0; layoutGrid(); });
          } : null,
          // the chart's data again with more options (a Time Machine's day): the deck and period shown
          fetch: function(extra){
            const ww = Object.assign({}, w, {options: Object.assign({}, w.options || {}, extra || {})});
            return DD.call('data', {widgets: [ww], deck: state.deck, span: state.span, query: state.searchQuery || ''}).then(function(d){ return d && d[w.id]; });
          }};
        const tm0 = performance.now();
        try { inst = mod.mount(card.querySelector('.dd-body'), mctx); } finally {
          DD._mountEl = null;
          if (DD._perfNotes && DD._perfNotes.length < 20) DD._perfNotes.push('mount ' + w.type + ' ' + Math.round(performance.now() - tm0) + 'ms');
          if (DD._bootMounts) DD._bootMounts.push([performance.now() - tm0, w.type, !!data, data && Array.isArray(data.rows) ? data.rows.length : null]);
        }
        if (!intro && animate) mctx.animate = true;
        DD.watchStat(card.querySelector('.dd-head'));
        // no explanation for this chart: no "?" (chart_help: the icon is only made when there is a text)
        const hq = card.querySelector('.dd-help');
        if (hq) setTimeout(function(){ helpText(w.type).then(function(t){ if (!t) hq.style.display = 'none'; }).catch(function(){}); }, 0);
      } else {
        card.querySelector('.dd-body').innerHTML = '<div class="dd-todo">not ported yet</div>';
        inst = {update: function(){}, setTheme: function(){}, setOptions: function(){}, destroy: function(){}};
      }
      if (entry) entry.inst = inst; else state.cards[w.id] = {card: card, inst: inst, _deckQ: state.deck + '|' + (state.searchQuery || '')};
      if (entry) entry._deckQ = state.deck + '|' + (state.searchQuery || '');
      // only once the setup has reached its menus' lists (cardMenu reads them): the first charts mount before
      if (DD.ownOptions) ownOpt(card);
      if (inst.zoom){
        inst.zoom.onChange = function(r){ onZoom(w.id, r); };
        inst.zoom.onOutLimit = function(){
          if (AZ && AZ.ids.some(function(x){ return String(x) === String(w.id); })) leaveAdaptive(true);
          else if (ZLINK[w.type] && state.span !== -1 && !inEXP(w.id)) expandBeyondSpan(w.id);
        };
      }
    }

    // ---- zoom link: zooming Activity / Retention / Added zooms the others to the same days; the stat cards,
    // Answer Buttons, Hourly and the Heatmap follow with the sums of those days ----
    // the charts of days, zoomed together (introduced_load was left out); the others (Answer Time, Rating by Interval:
    // seconds / intervals, Due Today: today's hours) zoom on their own, they follow the days' zoom by their data
    const ZLINK = {activity: 1, retention: 1, added: 1, ratings: 1, review_speed: 1, forgotten: 1, resets: 1, introduced: 1, introduced_load: 1, card_states: 1, load_trend: 1, stability_trend: 1, memorised: 1};
    let zseq = 0, ztm = null;
    function widgetOf(id){ return state.widgets.filter(function(x){ return String(x.id) === String(id); })[0]; }
    const G = state.globals = Object.assign({show_average: true, avg_on_active_days: true, show_cumulative: true, sync_zoom: true, binning: true}, boot.globals || {});
    const rzBtn = root.querySelector('.dd-rzoom');
    let EXP = null;  // {ids: [...], busy: bool} when temporarily zoomed out past state.span into Total
    function inEXP(id){ return !!(EXP && EXP.ids && EXP.ids.indexOf(String(id)) >= 0); }
    function findDateIdx(z, first, last){
      let a = -1, b = -1, n = z.count ? z.count() : 0;
      for (let i = 0; i < n; i++){
        const l = z.label(i);
        if (l === first && a < 0) a = i;
        if (l === last) b = i;
      }
      if (a < 0 || b < a){ a = Math.max(0, n - 30); b = n - 1; }
      return [a, b, n];
    }
    function expandBeyondSpan(srcId){
      if (state.span === -1 || (EXP && EXP.busy)) return;
      const srcCard = state.cards[srcId], srcZ = srcCard && srcCard.inst && srcCard.inst.zoom;
      if (!srcZ || !srcZ.count || srcZ.count() < 1) return;
      const first = srcZ.label(0), last = srcZ.label(srcZ.count() - 1);
      const ws = G.sync_zoom
        ? state.widgets.filter(function(w){ const c = state.cards[w.id]; return ZLINK[w.type] && c && c.inst && c.inst.zoom; })
        : [widgetOf(srcId)].filter(Boolean);
      if (!ws.length) return;
      const round = DD._round;
      EXP = {ids: ws.map(function(w){ return String(w.id); }), busy: true};
      DD.call('data', {widgets: ws, deck: state.deck, span: -1, query: state.searchQuery || ''}).then(function(d){
        if (DD._round !== round || !EXP){ return; }
        EXP.busy = false;
        let srcRange = null;
        ws.forEach(function(w){
          const c = state.cards[w.id], data = d && d[w.id];
          if (!c || !data || !c.inst || !c.inst.zoom) return;
          const z = c.inst.zoom;
          DD._scopeUpdate = true;
          try {
            if (z.swap){ z.swap(data, null, true); }
            else { DD._noAnim = true; try { c.inst.update(data); } finally { DD._noAnim = false; } }
          } finally { DD._scopeUpdate = false; }
          const ab = findDateIdx(z, first, last), a = ab[0], b = ab[1], n = ab[2];
          if (n <= 1) return;
          const spanLen = Math.max(2, b - a + 1);
          const newA = Math.max(0, a - Math.max(3, Math.round(spanLen * 0.28)));
          const newB = Math.min(n - 1, b);
          if (newA === 0 && newB >= n - 1){
            quiet(w.id, function(){ z.set(null); });
          } else {
            quiet(w.id, function(){ z.set(newA, newB + 1); });
          }
          if (String(w.id) === String(srcId)) srcRange = z.get();
        });
        updateRZoom();
        onZoom(srcId, srcRange);
      }).catch(function(){ EXP = null; });
    }
    function restoreExpanded(ids){
      const list = (ids && ids.length) ? ids : (EXP ? EXP.ids.slice() : []);
      if (!list.length) return;
      if (EXP){
        EXP.ids = EXP.ids.filter(function(x){ return list.indexOf(String(x)) < 0; });
        if (!EXP.ids.length) EXP = null;
      }
      const ws = state.widgets.filter(function(w){ return list.indexOf(String(w.id)) >= 0; });
      if (!ws.length) return;
      const round = DD._round;
      DD.call('data', {widgets: ws, deck: state.deck, span: state.span, query: state.searchQuery || ''}).then(function(d){
        if (DD._round !== round) return;
        ws.forEach(function(w){
          const c = state.cards[w.id];
          if (!c || !d || !d[w.id]) return;
          const z = c.inst && c.inst.zoom;
          DD._scopeUpdate = true;
          try {
            quiet(w.id, function(){
              if (z && z.swap) z.swap(d[w.id], null, true);
              else c.inst.update(d[w.id], 'timespan');
            });
          } finally { DD._scopeUpdate = false; }
          if (z && z.bar) z.bar();
        });
        updateRZoom();
      }).catch(function(){});
    }
    function updateRZoom(){
      const any = !!AZ || !!EXP || Object.keys(state.cards).some(function(id){ const z = state.cards[id].inst.zoom; return z && z.get && z.get(); });
      if (rzBtn) rzBtn.style.display = 'none';  // web: no window-wide arrow (hard to find at the bottom): each zoomed chart has its own
      // zoom link off: each zoomed chart shows its own reset arrow in its header (create_local_reset)
      Object.keys(state.cards).forEach(function(id){
        const c = state.cards[id], z = c.inst.zoom; if (!z || !z.get) return;
        let b = c.card.querySelector('.dd-zreset');
        // zoom link on: the reset arrow is the window's (top right), out of sight behind a chart shown fullscreen:
        // that chart gets one in its header, which resets them all
        const fs = c.card.classList.contains('dd-fs');
        // web: zoom link on too, every zoomed chart shows the arrow in its header (it resets them all)
        const show = !!z.get() || inAZ(id) || inEXP(id) || (G.sync_zoom && fs && any);
        if (!b && !show) return;
        if (!b){
          b = document.createElement('button'); b.className = 'dd-zreset'; b.title = (TITLES[c.card.dataset.type] ? DD.t('Reset ' + TITLES[c.card.dataset.type] + ' Zoom') : DD.t('Reset Zoom'));
          b.innerHTML = icon('reset', 14);
          b.addEventListener('click', function(e){ e.stopPropagation(); if (G.sync_zoom && ZLINK[c.card.dataset.type]){ resetAllZooms(); return; } if (inAZ(id)){ leaveAdaptive(false); return; } if (inEXP(id)){ restoreExpanded([String(id)]); return; } z.set(null); onZoom(id, null); });
          // on the right of the header, before the chart's pills (it sat after the "?", on the left)
          const head = c.card.querySelector('.dd-head'), pills = head.querySelector('.dd-pills');
          if (pills) head.insertBefore(b, pills); else head.appendChild(b);
        }
        b.style.display = show ? '' : 'none';
        b.title = G.sync_zoom && ZLINK[c.card.dataset.type] ? DD.t('Reset All Zooms') : (TITLES[c.card.dataset.type] ? DD.t('Reset ' + TITLES[c.card.dataset.type] + ' Zoom') : DD.t('Reset Zoom'));
      });
    }
    function resetAllZooms(){
      if (DD.perfWatch) DD.perfWatch('reset zoom', 1000);
      // the charts leaving the 10-minute view go straight to the days (leaveAdaptive): not zoomed out first inside
      // the 10-minute rows on the way
      const azIds = AZ ? AZ.ids.map(String) : [];
      if (AZ) leaveAdaptive(false);
      const expIds = EXP ? EXP.ids.slice() : [];
      if (expIds.length) restoreExpanded(expIds);
      Object.keys(state.cards).forEach(function(id){ if (azIds.indexOf(String(id)) >= 0 || expIds.indexOf(String(id)) >= 0) return; const z = state.cards[id].inst.zoom; if (z && z.get && z.get()) quiet(id, function(){ z.set(null); }); });
      updateRZoom(); refreshFollowers(++zseq);
    }
    if (rzBtn) rzBtn.addEventListener('click', resetAllZooms);
    DD._updateRZoom = updateRZoom;
    // a chart out of view takes a zoom's result at once (no animation waiting for it when one scrolls down)
    function inView(id){
      const c = state.cards[id]; if (!c || !c.card) return false;
      // seen = inside the charts' own scrolling area (the table bar and the bottom bar cover the rest of the window)
      const r = c.card.getBoundingClientRect(), v = wrapEl.getBoundingClientRect();
      return r.height > 0 && r.bottom > v.top + 4 && r.top < v.bottom - 4;
    }
    function quiet(id, fn){ const prev = DD._noAnim, off = !inView(id); if (off) DD._noAnim = true; try { fn(); } finally { DD._noAnim = prev; } }
    const zPrev = {};
    function onZoom(srcId, range){
      if (DD.perfWatch) DD.perfWatch(range ? 'zoom' : 'zoom reset', 1000);
      const prevSrc = zPrev[srcId]; zPrev[srcId] = range ? range.slice() : null;
      updateRZoom();
      if (DD._scopeUpdate){ if (DD.dev) DD.trace('ANIMTRACE zoom link: ' + ((state.cards[srcId] && state.cards[srcId].card.dataset.type) || srcId) + ' reset by its new data, not sent to the others'); return; }
      // a step down to 2 days: the charts that will switch to 10-minute bins hold the picture they show now (the
      // days before this step) until the 10-minute rows are in, then zoom from it into them (one camera zoom)
      const pre = adaptiveCan(srcId, range) ? holdAdaptive(srcId, prevSrc) : null;
      tryAdaptive(srcId, range, pre);
      if (AZ) refreshDots(false);
      if (!G.sync_zoom) return;
      // a chart that isn't of days (its bars: seconds, intervals...): its zoom is its own, sent to none
      const sw = widgetOf(srcId); if (!sw || !ZLINK[sw.type]) return;
      const src = state.cards[srcId] && state.cards[srcId].inst.zoom; if (!src) return;
      const first = range ? src.label(range[0]) : null, last = range ? src.label(range[1] - 1) : null;
      Object.keys(state.cards).forEach(function(id){
        if (String(id) === String(srcId)) return;
        const w = widgetOf(id), z = state.cards[id].inst.zoom;
        if (!w || !z || !ZLINK[w.type]) return;
        if (w.type === 'added' && (w.options && w.options.sync_zoom) === false) return;
        if (first === null){ if (z.get()) quiet(id, function(){ z.set(null); }); return; }
        let a = -1, b = -1;
        for (let i = 0, n = z.count(); i < n; i++){ const l = z.label(i); if (l === first && a < 0) a = i; if (l === last) b = i; }
        if (a >= 0 && b >= a) quiet(id, function(){ z.set(a, b + 1); }); else if (z.get()) quiet(id, function(){ z.set(null); });
      });
      updateRZoom();  // the charts zoomed with it get their arrow too (only the one zoomed had it)
      // no cascade: the charts that follow the zoom are asked at once, with the zoom (the read runs off the UI thread);
      // a burst of zoom steps (wheel, scroll bar) asks again once it pauses, for its last window
      clearTimeout(ztm);
      const my = ++zseq;
      const go = function(){ if (first === null) refreshFollowers(my); else followZoom(my, first, last); };
      const now = performance.now();
      if (!followBusy || now - followBusy > 120){ followBusy = now; go(); }
      else ztm = setTimeout(function(){ followBusy = performance.now(); go(); }, 60);
    }
    let followBusy = 0;
    function followZoom(my, first, last){
        DD.call('zoom_stats', {deck: state.deck, span: state.span, first: first, last: last, bounds: AZ ? AZ.bounds : null, query: state.searchQuery || ''}).then(function(r){
          if (my !== zseq || !r) return;
          if (scInst && r.stats) scInst.update(r.stats);
          const off = [];
          state.widgets.forEach(function(w){
            const c = state.cards[w.id];
            if (!c || !r[w.type]) return;
            if (w.type === 'distribution' || w.type === 'hourly' || w.type === 'heatmap' || w.type === 'answer_time' || w.type === 'interval_ratings' || w.type === 'rating_fatigue' || w.type === 'sibling_ratings' || w.type === 'fsrs_calibration' || w.type === 'forgetting_curve' || w.type === 'fsrs_fatigue' || w.type === 'week_hours' || w.type === 'todays_retention'){
              if (inView(w.id)) c.inst.update(r[w.type]);
              else off.push([w.id, r[w.type]]);
            }
          });
          updateRZoom();  // (new data: a follower's own zoom is gone, its arrow too)
          if (off.length){
            DD.onIdle(function(){
              if (my !== zseq) return;
              off.forEach(function(it){ const c = state.cards[it[0]]; if (c) quiet(it[0], function(){ c.inst.update(it[1]); }); });
            }, 420);
          }
        }).catch(function(e){ DD.log('zoom_stats: ' + (e && e.message || e)); });
    }
    // ---- adaptive zoom: a zoom down to
    // 2 days switches Activity / Retention / Added, and the charts of answers by day (Ratings, Forgotten, Review Speed,
    // Introduced, Reset Cards: providers.AZ_METRICS), to 10-minute bins over those days; zooming out past the whole
    // 10-minute view (or a reset) brings the days back, one wheel step wider than the window before ----
    const AZT = {activity: 1, retention: 1, added: 1, ratings: 1, forgotten: 1, review_speed: 1, introduced: 1, resets: 1};
    let AZ = null, azSeq = 0;
    function inAZ(id){ return !!AZ && AZ.ids.some(function(x){ return String(x) === String(id); }); }
    DD.leaveAdaptiveSilently = function(){ AZ = null; azSeq++; };  // another deck / period: the new data replaces it
    function labelsOf(type, p){
      if (!p) return [];
      if (type === 'activity') return (p.rows || []).map(function(r){ return String(r.date); });
      if (type === 'added') return (p.rows || []).map(function(r){ return String(r.pretty_date); });
      if (Array.isArray(p.rows)) return p.rows.map(function(r){ return String(r.date); });  // (the charts of answers by day)
      const d = p.data || {}; for (const k in d){ if (Array.isArray(d[k]) && d[k].length) return d[k].map(function(x){ return String(x[0]); }); }
      return [];
    }
    function adaptiveCan(srcId, range){
      if (AZ || !range) return false;
      const w = widgetOf(srcId); if (!w || !AZT[w.type]) return false;
      const z = state.cards[srcId] && state.cards[srcId].inst.zoom; if (!z || !z.swap) return false;
      if (range[1] - range[0] > 3) return false;  // resolve_adaptive_zoom_window: 2 days or less between the first and last day
      const first = z.label(range[0]), last = z.label(range[1] - 1);
      return !!(first && last && !/\d:\d\d$/.test(first));  // not already 10-minute rows (Today / Yesterday)
    }
    function holdAdaptive(srcId, prevSrc){
      if (!DD.holdPicture) return null;
      const out = {};
      state.widgets.forEach(function(x){
        const c = state.cards[x.id], z = c && c.inst.zoom; if (!AZT[x.type] || !z || !z.snap || !inView(x.id)) return;
        const src = String(x.id) === String(srcId);
        if (!src && (!G.sync_zoom || (x.type === 'added' && x.options && x.options.sync_zoom === false))) return;
        const win = src ? (prevSrc || [0, z.count()]) : (z.get() || [0, z.count()]);
        const P = z.snap(); if (!P || !P.img.width) return;
        out[x.id] = {P: P, win: win.slice(), end: DD.holdPicture(z.canvas, P)};
      });
      setTimeout(function(){ releaseHolds(out); }, 1500);
      return out;
    }
    function releaseHolds(pre){ if (pre) Object.keys(pre).forEach(function(k){ try { pre[k].end(); } catch (e) {} }); }
    function tryAdaptive(srcId, range, pre){
      if (!adaptiveCan(srcId, range)){ releaseHolds(pre); return; }
      const w = widgetOf(srcId), z = state.cards[srcId].inst.zoom;
      const first = z.label(range[0]), last = z.label(range[1] - 1), n = z.count();
      const my = ++azSeq;
      // (the charts shown that switch with it: their 10-minute rows read only for them)
      const types = state.widgets.filter(function(x){ return AZT[x.type] && state.cards[x.id]; }).map(function(x){ return x.type; });
      DD.call('adaptive', {deck: state.deck, span: state.span, first: first, last: last, source: w.type, query: state.searchQuery || '', types: types}).then(function(r){
        if (my !== azSeq || AZ || !r || !r.bounds){ releaseHolds(pre); return; }
        const cur = z.get(); if (!cur || cur[0] !== range[0] || cur[1] !== range[1]){ releaseHolds(pre); return; }  // the zoom moved on since
        const alignRight = (range[0] + range[1]) / (2 * Math.max(1, n)) >= 0.5;  // compute_transition_align_right
        const ids = state.widgets.filter(function(x){
          const c = state.cards[x.id]; if (!AZT[x.type] || !c || !c.inst.zoom || !c.inst.zoom.swap || !r[x.type]) return false;
          if (String(x.id) === String(srcId)) return true;
          if (r.added_only || !G.sync_zoom) return false;  // zoom link off: only the zoomed chart switches
          return !(x.type === 'added' && x.options && x.options.sync_zoom === false);
        }).map(function(x){ return x.id; });
        AZ = {ids: ids, bounds: r.bounds, first: first, last: last, src: srcId, alignRight: alignRight, times: r.times || null};
        // inside the camera zoom, the chart's own zoom ends (finish), its data is swapped, then the old picture (days)
        // cross-fades into the new one (10-minute bars) over the same days (_PixmapZoom, 280 ms OutQuad)
        ids.forEach(function(id){ swapPictured(id, r[widgetOf(id).type], null, alignRight, null, null, pre && pre[id]); });
        releaseHolds(pre);
        updateRZoom();
        refreshDots(false);
        if (G.sync_zoom && !r.added_only){ clearTimeout(ztm); followZoom(++zseq, null, null); }
      }).catch(function(e){ releaseHolds(pre); DD.log('adaptive: ' + (e && e.message || e)); });
    }
    function swapPictured(id, data, range, alignRight, wa, wb, held){
      const c = state.cards[id], z = c && c.inst.zoom; if (!z) return;
      if (!inView(id) || !z.picture || !DD.pictureZoom){ if (held) held.end(); quiet(id, function(){ z.swap(data, range, alignRight); }); return; }
      let before;
      if (held){ before = held.P; if (held.win){ wa = held.win; wb = z.get() || [0, z.count()]; } }  // from the days held, into the days zoomed to
      else before = z.picture();
      DD._noAnim = true; try { z.swap(data, range, alignRight); } finally { DD._noAnim = false; }
      const after = z.picture();
      if (held) held.end();
      DD.pictureZoom(z.canvas, before, after, wa, wb, 300);
    }
    function leaveAdaptive(toWider){
      if (!AZ) return;
      // what is on screen (the dots, or the 10-minute bars) held still until the days are in, then one zoom from it
      // into them
      const held = {};
      AZ.ids.forEach(function(id){
        const c = state.cards[id], z = c && c.inst.zoom; if (!z || !z.picture || !DD.holdPicture || !inView(id)) return;
        const D = c.inst.dots, P = (D && D.visible()) ? D.picture() : z.picture();
        if (P && P.img && P.img.width) held[id] = {P: P, win: null};
      });
      dotsToBars(true);
      Object.keys(held).forEach(function(id){ held[id].end = DD.holdPicture(state.cards[id].inst.zoom.canvas, held[id].P); });
      setTimeout(function(){ releaseHolds(held); }, 1500);
      const az = AZ; AZ = null; azSeq++;
      const ws = az.ids.map(widgetOf).filter(Boolean);
      DD.call('data', {widgets: ws, deck: state.deck, span: state.span, query: state.searchQuery || ''}).then(function(d){
        if (AZ){ releaseHolds(held); return; }
        let win = null;
        ws.forEach(function(w){
          const c = state.cards[w.id]; if (!c || !d[w.id]) return;
          let range = null;
          if (toWider){
            // widen_zoom_window: one wheel step (15 %) wider, and wider than the 2-day threshold
            const L = labelsOf(w.type, d[w.id]), a = L.indexOf(az.first), b = L.lastIndexOf(az.last) + 1, n = L.length;
            if (a >= 0 && b > a){
              let nl = Math.max(b - a + 1, Math.floor((b - a) * 1.15), 4); nl = Math.min(n, nl);
              let s0 = Math.round((a + b) / 2 - nl / 2); s0 = Math.max(0, Math.min(s0, n - nl));
              range = nl >= n ? null : [s0, s0 + nl];
              if (range && String(w.id) === String(az.src)) win = [L[range[0]], L[range[1] - 1]];
            }
          }
          // the 10-minute window shown, in days of the restored rows: the picture zooms out to the wider window of days
          const L = labelsOf(w.type, d[w.id]), da = L.indexOf(az.first), db = L.lastIndexOf(az.last) + 1, z = c.inst.zoom;
          let wa = null, wb = null;
          if (da >= 0 && db > da){
            const cur = z.get(), cnt = Math.max(1, z.count()), s0 = cur ? cur[0] : 0, e0 = cur ? cur[1] : cnt, D = db - da;
            wa = [da + s0 / cnt * D, da + e0 / cnt * D]; wb = range ? range.slice() : [0, L.length];
          }
          swapPictured(w.id, d[w.id], range, az.alignRight, wa, wb, held[w.id]);
        });
        releaseHolds(held);
        updateRZoom();
        clearTimeout(ztm);
        if (win && G.sync_zoom) followZoom(++zseq, win[0], win[1]); else refreshFollowers(++zseq);
      }).catch(function(e){ releaseHolds(held); DD.log('adaptive leave: ' + (e && e.message || e)); });
    }
    // ---- one dot per review: in the 10-minute view zoomed to 3 hours or less, Activity
    // shows each review as a dot; the bars sink while the dots pop in; back to the bars by a picture zoom ----
    const DOTS_MAX = 3 * 3600 * 1000, BIN10 = 600000;
    let dotsSeq = 0, dotsTm = null;
    function actId(){ const w = state.widgets.filter(function(x){ return x.type === 'activity' && state.cards[x.id] && state.cards[x.id].inst.dots; })[0]; return w ? w.id : null; }
    function barsWindow(z){
      const cur = z.get(), n = z.count(), s0 = cur ? cur[0] : 0, e0 = cur ? cur[1] : n;
      return (AZ && AZ.times && AZ.times[s0] != null && AZ.times[e0 - 1] != null) ? [AZ.times[s0], AZ.times[e0 - 1] + BIN10] : null;
    }
    function dotsToBars(instant){
      const id = actId(); if (id == null) return;
      const c = state.cards[id], D = c.inst.dots, z = c.inst.zoom;
      dotsSeq++; clearTimeout(dotsTm);
      if (!D.visible()) return;
      const before = (!instant && inView(id)) ? D.picture() : null, wd = D.window(), wbars = barsWindow(z);
      D.hide(); z.canvas.style.visibility = '';
      if (before) DD.pictureZoom(z.canvas, before, z.picture(), wd, wbars, 300);
    }
    function refreshDots(immediate){
      const id = actId(); if (id == null) return;
      if (!state.cards[id].inst.dots.visible() && !inAZ(id)) return;
      clearTimeout(dotsTm);
      if (immediate) applyDots(); else dotsTm = setTimeout(applyDots, 120);
    }
    DD.refreshDots = refreshDots;
    function applyDots(){
      const id = actId(); if (id == null) return;
      const c = state.cards[id], D = c.inst.dots, z = c.inst.zoom;
      const rng = z.get();
      if (!AZ || !inAZ(id) || !AZ.times || !rng){ dotsToBars(); return; }
      const t0 = AZ.times[Math.max(0, rng[0])], t1 = AZ.times[Math.min(AZ.times.length, rng[1]) - 1] + BIN10;
      if (!(t1 > t0) || t1 - t0 > DOTS_MAX){ dotsToBars(); return; }
      const my = ++dotsSeq;
      DD.call('review_events', {deck: state.deck, t0: t0, t1: t1, query: state.searchQuery || ''}).then(function(r){
        if (my !== dotsSeq || !AZ) return;
        if (!r || !r.events){ dotsToBars(); return; }
        const m = z.mode();
        D.setMode(m.mode === 'time' ? 'time' : 'reviews', m.breakdown);
        if (D.visible()){
          // zooming out: the view glides to the wider window; in or moving: the dots page slides (camera_zoom)
          const before = inView(id) ? D.picture() : null, wa = D.window();
          if (D.setEvents(r.events, t0, t1) === 'set' && before) DD.pictureZoom(D.canvas, before, D.picture(), wa, [t0, t1], 300);
          return;
        }
        // bars -> dots over the same hours: the bars sink and fade while the dots pop in (_SinkOut + their intro)
        const anim = inView(id), before = anim ? z.picture() : null;
        D.setEvents(r.events, t0, t1);
        // the axes go from the bars' to the dots' while the bars sink (dots.js sinkOut), the dots' own held back meanwhile
        const na = (before && DD.sinkOut && D.axisInfo) ? D.axisInfo() : null;
        if (na && D.holdAxes) D.holdAxes(300);
        z.canvas.style.visibility = 'hidden';
        D.show(anim);
        if (before && DD.sinkOut) DD.sinkOut(z.canvas, before, 300, na);
      }).catch(function(e){ DD.log('review_events: ' + (e && e.message || e)); });
    }
    // Ctrl+wheel out of the whole dots window: the 10-minute zoom widens by a step right away
    function dotsZoomOut(frac){
      const id = actId(); if (id == null || !AZ || !AZ.times) return;
      const c = state.cards[id], D = c.inst.dots, z = c.inst.zoom, times = AZ.times, n = times.length;
      const cur = z.get() || [0, n], cs = Math.max(0, cur[0]), ce = Math.min(n, cur[1]);
      const w = D.window(), span = (w[1] - w[0]) * 1.25, n0 = w[0] + frac * (w[1] - w[0]) - frac * span, n1 = n0 + span;
      const br = (x) => { let i = 0; while (i < n && times[i] <= x) i++; return i; }, bl = (x) => { let i = 0; while (i < n && times[i] < x) i++; return i; };
      let s0 = Math.max(0, br(n0) - 1), e0 = Math.min(n, bl(n1 - BIN10) + 1);
      s0 = Math.min(s0, cs); e0 = Math.max(e0, ce);
      if (s0 === cs && e0 === ce){ s0 = Math.max(0, cs - 1); e0 = Math.min(n, ce + 1); }
      if (s0 >= cs && e0 <= ce){ leaveAdaptive(true); return; }  // the whole 10-minute view: back to the days
      DD._noAnim = true; try { z.set(s0, e0); } finally { DD._noAnim = false; }
      onZoom(id, z.get());
      refreshDots(true);
    }
    DD._dotsZoomOut = dotsZoomOut;
    // zoom gone: only what followed the zoom is read again; the zoomed charts keep playing their own zoom-out animation
    const FOLLOW = {distribution: 1, hourly: 1, heatmap: 1, answer_time: 1, interval_ratings: 1, rating_fatigue: 1, sibling_ratings: 1, fsrs_calibration: 1, forgetting_curve: 1, fsrs_fatigue: 1, week_hours: 1, todays_retention: 1};
    function refreshFollowers(my){
      if (scInst) DD.call('stats', {deck: state.deck, span: state.span, query: state.searchQuery || ''}).then(function(s){ if (my === undefined || my === zseq) scInst.update(s); }).catch(function(){});
      const ws = state.widgets.filter(function(w){ return FOLLOW[w.type]; });
      if (!ws.length) return;
      DD.call('data', {widgets: ws, deck: state.deck, span: state.span, query: state.searchQuery || ''}).then(function(d){
        if (my !== undefined && my !== zseq) return;  // an answer for a zoom since replaced
        const off = [];
        ws.forEach(function(w){
          const c = state.cards[w.id]; if (!c || !d[w.id]) return;
          if (inView(w.id)) c.inst.update(d[w.id]);
          else off.push([w.id, d[w.id]]);
        });
        updateRZoom();
        if (off.length){
          DD.onIdle(function(){
            if (my !== undefined && my !== zseq) return;
            off.forEach(function(it){ const c = state.cards[it[0]]; if (c) quiet(it[0], function(){ c.inst.update(it[1]); }); });
          }, 420);
        }
      }).catch(function(){});
    }

    // an export's hidden page (boot.export): the charts drawn at once, no intro
    bm('setup');
    boot.widgets.forEach(function(w){ addCard(w, boot.data[w.id], !boot.export); const c = state.cards[w.id]; if (c && boot.data[w.id] && boot.data[w.id]._empty) c.card.style.display = 'none'; });
    bm('cards');
    function whenIdleOrScroll(fn, maxWait){
      let done = false;
      const scroller = root.querySelector('.dd-gridwrap');
      const go = function(){
        if (done) return;
        done = true;
        if (scroller) scroller.removeEventListener('scroll', go);
        fn();
      };
      // a scroll asks for them once it stops (asked during it, Python's reading stuttered it)
      if (scroller) scroller.addEventListener('scroll', function(){ DD.whenStill(go); }, {once: true, passive: true});
      DD.onIdle(function(){ DD.whenStill(go); }, maxWait);
    }
    function prioritizeVisible(ws){
      const vh = window.innerHeight;
      return ws.slice().sort(function(a, b){
        const ca = state.cards[a.id], cb = state.cards[b.id];
        const ra = ca && ca.card ? ca.card.getBoundingClientRect() : null;
        const rb = cb && cb.card ? cb.card.getBoundingClientRect() : null;
        const va = ra && ra.bottom > 0 && ra.top < vh ? 0 : 1;
        const vb = rb && rb.bottom > 0 && rb.top < vh ? 0 : 1;
        return va - vb || (ra ? ra.top : 1e9) - (rb ? rb.top : 1e9);
      });
    }
    // the charts _boot left out (it reads ~300 ms of them, the window opens at once): asked again here, the "data"
    // command running off Anki's UI thread, a few at a time; each card gets its chart as its data comes. A new deck or
    // period meanwhile (DD._round) gives them their data itself
    (function lateData(){
      const left = boot.widgets.filter(function(w){ const c = state.cards[w.id]; return c && c.late; });
      if (!left.length) return;
      const round = DD._round, deck = state.deck, span = state.span, t0 = performance.now();
      const vh = window.innerHeight;
      const visLeft = left.filter(function(w){ const c = state.cards[w.id]; if (!c || !c.card) return false; const r = c.card.getBoundingClientRect(); return r.bottom > 0 && r.top < vh; });
      const offLeft = left.filter(function(w){ return visLeft.indexOf(w) < 0; });
      const ordered = visLeft.concat(offLeft);
      function next(ws){
        if (!ws.length || DD._round !== round) return;
        // each batch once no scroll is going on, then the cards in view first (those the scroll brought in)
        DD.whenStill(function(){ if (DD._round === round) ask(prioritizeVisible(ws)); });
      }
      function ask(batch){
        DD.call('data', {widgets: batch, deck: deck, span: span, budget_ms: 80, query: state.searchQuery || ''}).then(function(d){
          if (DD._round !== round) return;
          const rest = [];
          let hid = false;
          batch.forEach(function(w){
            const c = state.cards[w.id];
            if (!d || d[w.id] === undefined){ rest.push(w); return; }
            if (!c || !c.late) return;
            c.inst.update(d[w.id]);
            if (d[w.id] && d[w.id]._empty){ c.card.style.display = 'none'; hid = true; }
          });
          if (hid) layoutGrid();
          if (DD.dev) DD.trace('late data: ' + (batch.length - rest.length) + ' charts at +' + Math.round(performance.now() - t0) + 'ms, ' + rest.length + ' left');
          if (rest.length < batch.length){
            const curVh = window.innerHeight;
            const anyVis = rest.some(function(w){ const c = state.cards[w.id]; if (!c || !c.card) return false; const r = c.card.getBoundingClientRect(); return r.bottom > 0 && r.top < curVh; });
            if (anyVis) next(rest);
            else whenIdleOrScroll(function(){ next(rest); }, 1800);
          }
        }).catch(function(e){ DD.log('late data: ' + (e && e.message || e)); });
      }
      if (visLeft.length) next(ordered);
      else DD.onGo(function(){ setTimeout(function(){ whenIdleOrScroll(function(){ next(ordered); }, 1800); }, 120); });
    })();
    // A chart with no data is left out (unless "Show Empty Charts"): shown or hidden at once,
    // the other cards slide to their new places (260 ms OutCubic, the position only)
    // Web: in three overlapping beats instead of at once: the cards that go fade and shrink a little (300 ms), then
    // the others glide to their new places (650 ms, a soft landing) while the new ones fade and grow in.
    const LAY = {pend: new Map(), timer: 0, round: 0};
    function cancelPendingLayout(){
      if (LAY.timer){ clearTimeout(LAY.timer); LAY.timer = 0; }
      LAY.pend.forEach(function(_hide, c){
        if (c.getAnimations) c.getAnimations().forEach(function(a){ if (a.id === 'ddgo' || a.id === 'ddcome') a.cancel(); });
      });
      LAY.pend.clear();
    }
    function settle(silent){
      LAY.timer = 0;
      const changes = LAY.pend; LAY.pend = new Map();
      if (!changes.size) return;
      const still = silent || (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
      const before = new Map();
      // Capture current visual positions BEFORE cancelling active moves, so rapid clicks glide from where cards actually are.
      grid.querySelectorAll('.dd-card').forEach(function(c){
        if (c.style.display !== 'none' && !changes.get(c)) before.set(c, c.getBoundingClientRect());
      });
      // Cancel any in-flight move/fade animations so layoutGrid() and post-rects measure true resting targets.
      grid.querySelectorAll('.dd-card').forEach(function(c){
        if (c.getAnimations) c.getAnimations().forEach(function(a){ if (a.id === 'ddmove' || a.id === 'ddgo' || a.id === 'ddcome') a.cancel(); });
      });
      const coming = [];
      changes.forEach(function(hide, c){
        if (!hide && c.style.display === 'none') coming.push(c);
        c.style.display = hide ? 'none' : '';
      });
      layoutGrid();
      if (DD.dev){
        const mv = [], sz = [];
        before.forEach(function(r, c){ if (c.style.display === 'none') return; const n = c.getBoundingClientRect(); if (Math.abs(r.left - n.left) > 0.5 || Math.abs(r.top - n.top) > 0.5) mv.push(c.dataset.type + ' ' + Math.round(n.left - r.left) + ',' + Math.round(n.top - r.top)); if (Math.abs(r.width - n.width) > 0.5 || Math.abs(r.height - n.height) > 0.5) sz.push(c.dataset.type + ' ' + Math.round(r.width) + 'x' + Math.round(r.height) + '->' + Math.round(n.width) + 'x' + Math.round(n.height)); });
        const gone = [], came = []; changes.forEach(function(hide, c){ (hide ? gone : came).push(c.dataset.type); });
        const since = DD._lastScopeAt ? ('+' + Math.round(performance.now() - DD._lastScopeAt) + 'ms ') : '';
        DD.trace('ANIMTRACE layout ' + since + '(round ' + (DD._round || 0) + (silent ? ' silent' : '') + '): gone [' + gone.join(',') + '] came [' + came.join(',') + '] moved [' + mv.join(' | ') + '] resized [' + sz.join(' | ') + ']');
      }
      if (still || !document.body.animate) return;
      const vh = window.innerHeight;
      before.forEach(function(r, c){
        if (c.style.display === 'none') return;
        const n = c.getBoundingClientRect(), dx = r.left - n.left, dy = r.top - n.top;
        // Skip animating cards completely outside the viewport both before and after.
        if ((r.bottom < -40 || r.top > vh + 40) && (n.bottom < -40 || n.top > vh + 40)) return;
        const sx = n.width > 0 ? r.width / n.width : 1, sy = n.height > 0 ? r.height / n.height : 1;
        const moved = Math.abs(dx) >= 0.5 || Math.abs(dy) >= 0.5;
        const resized = Math.abs(sx - 1) >= 0.005 || Math.abs(sy - 1) >= 0.005;
        if (!moved && !resized) return;
        const tf = resized
          ? 'translate3d(' + dx + 'px,' + dy + 'px,0) scale(' + sx + ',' + sy + ')'
          : 'translate3d(' + dx + 'px,' + dy + 'px,0)';
        const a = c.animate([{transformOrigin: '0 0', transform: tf}, {transformOrigin: '0 0', transform: 'none'}], {duration: 380, easing: 'cubic-bezier(0.22, 1, 0.36, 1)'});
        a.id = 'ddmove';
      });
      coming.forEach(function(c, i){
        const r = c.getBoundingClientRect();
        if (r.bottom < -40 || r.top > vh + 40) return;
        const a = c.animate([{opacity: 0, transform: 'scale(0.97)'}, {opacity: 1, transform: 'none'}], {duration: 280, delay: 40 + Math.min(i, 5) * 25, easing: 'cubic-bezier(0.22, 1, 0.36, 1)', fill: 'backwards'});
        a.id = 'ddcome';
      });
    }
    function setEmpty(changes, silent){
      if (!changes.length) return;
      const vh = window.innerHeight;
      const allOff = silent || changes.every(function(ch){
        const c = ch[0];
        if (c.style.display === 'none') return false;
        const r = c.getBoundingClientRect();
        return r.bottom < -40 || r.top > vh + 40;
      });
      if (allOff){
        changes.forEach(function(ch){ LAY.pend.set(ch[0], !!ch[1]); });
        if (!LAY.timer) settle(true);
        return;
      }
      const still = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      let going = false;
      const round = DD._round || 0;
      LAY.round = round;
      changes.forEach(function(ch){
        const c = ch[0], hide = !!ch[1];
        LAY.pend.set(c, hide);
        if (hide && c.style.display !== 'none' && !still && c.animate){
          going = true;
          c.getAnimations().forEach(function(a){ if (a.id === 'ddgo' || a.id === 'ddcome') a.cancel(); });
          const a = c.animate([{opacity: 1, transform: 'none'}, {opacity: 0, transform: 'scale(0.97)'}], {duration: 150, easing: 'cubic-bezier(0.4, 0, 1, 1)', fill: 'forwards'});
          a.id = 'ddgo';
        }
      });
      // Short 120 ms lead for leaving cards to fade, guarded by DD._round so rapid clicks never fire a stale settle().
      if (going){
        if (!LAY.timer) LAY.timer = setTimeout(function(){ if ((DD._round || 0) === round) settle(false); else cancelPendingLayout(); }, 120);
      } else if (!LAY.timer) settle(false);
    }
    DD.setEmpty = setEmpty;
    // Grid layout: columns by width, card height from its width, stretch to fill.
    const wrapEl = root.querySelector('.dd-gridwrap');
    const sizes = {scale: (boot.sizes && boot.sizes.scale) || null, spans: Object.assign({}, boot.sizes && boot.sizes.spans)};
    // Settings > General > Deep Dive: Collapsible Charts, Fill Height, Same Height for All Rows
    const lay = Object.assign({collapsible: true, fill: true, shared: false}, boot.layout || {});
    function applyFoldable(){
      grid.classList.toggle('dd-nofold', !lay.collapsible);
      if (!lay.collapsible) grid.querySelectorAll('.dd-card.dd-collapsed').forEach(function(c){ c.classList.remove('dd-collapsed'); });
    }
    DD.setLayoutOpts = function(o){ Object.assign(lay, o || {}); applyFoldable(); layoutGrid(); };
    bm('late data setup');
    applyFoldable();
    const grid_state = {cols: Math.max(1, Math.min(4, boot.grid_cols | 0 || 3))};
    // dev trace (LAYOUT): the stat cards' and the charts' left / right edges, to check that they line up
    let alignTm = 0;
    function alignTrace(){
      clearTimeout(alignTm);
      alignTm = setTimeout(function(){
        if (!DD.dev) return;
        const sc = Array.from(root.querySelectorAll('.dd-sc-host .dd-sc')).map(function(e){ return e.getBoundingClientRect(); });
        const cs = Array.from(grid.querySelectorAll('.dd-card')).filter(function(c){ return c.style.display !== 'none'; }).map(function(e){ return e.getBoundingClientRect(); });
        if (!sc.length || !cs.length) return;
        const r = function(v){ return v.toFixed(1); };
        const top = cs.filter(function(c){ return Math.abs(c.top - cs[0].top) < 2; });
        const scRow = sc.filter(function(c){ return Math.abs(c.top - sc[0].top) < 2; });
        DD.trace('LAYOUT stat cards ' + scRow.map(function(c){ return r(c.left) + '-' + r(c.right); }).join(' ') + ' | charts ' + top.map(function(c){ return r(c.left) + '-' + r(c.right); }).join(' ') +
          ' | window ' + window.innerWidth + ' gridwrap ' + wrapEl.clientWidth + '/' + wrapEl.offsetWidth + ' scroll ' + (wrapEl.scrollHeight > wrapEl.clientHeight));
      }, 400);
    }
    // timed for the resize trace (RESIZETRACE, dd-core.js)
    function layoutGrid(){
      const t = performance.now();
      try { return layoutGrid0.apply(this, arguments); } finally { if (DD._rz) DD.rzNote('layout', performance.now() - t); }
    }
    function layoutGrid0(){
      alignTrace();
      // the scroll bar's room (kept, scrollbar-gutter: 15 px here whatever the bar's drawn width) comes out of the
      // charts' right margin: their right edge stays under the stat cards' one (16 px from the window's edge)
      { const gut = Math.max(0, wrapEl.offsetWidth - wrapEl.clientWidth); grid.style.paddingRight = Math.max(0, 16 - gut) + 'px'; }
      const cards = Array.prototype.slice.call(grid.children).filter(function(c){ return c.style.display !== 'none' && !c.classList.contains('dd-cfilt-out'); });
      if (!cards.length){ grid.style.gridTemplateRows = ''; return; }  // (no rows left over: Find chart's list right under)
      const cs = getComputedStyle(grid);
      const eff = grid.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
      let cols = grid_state.cols;
      if (eff < 700) cols = Math.min(cols, 1); else if (eff < 1080) cols = Math.min(cols, 2); else if (eff < 1400) cols = Math.min(cols, 3);
      const gap = 12, colW = Math.floor((eff - (cols - 1) * gap) / cols);
      // the stat cards follow the charts' columns (stats.js layout: their edges on the columns, their height)
      if (DD.statCols !== cols){ DD.statCols = cols; try { if (scInst) scInst.relayout(); } catch (e) {} }
      const fillH = wrapEl.clientHeight, cap = fillH > 0 ? Math.floor(fillH * 0.7) : 560;
      const NATURAL = 150;
      // rows by column spans
      let rowsN = 0, used = 0;
      const rowAll = [];
      cards.forEach(function(c){
        const sp = Math.max(1, Math.min(cols, sizes.spans[c.dataset.type] || 1));
        c.style.gridColumn = 'span ' + sp;
        if (used + sp > cols || rowsN === 0){ rowsN++; used = 0; rowAll.push(true); }
        used += sp;
        c._row = rowsN - 1;
        if (!c.classList.contains('dd-collapsed')) rowAll[rowsN - 1] = false;
      });
      // each card's floor (a chart: 200, heatmap 40, card counts
      // 200, + the bottom stats room), at least the height of its width (/ 2.1, at most 70 % of the view; not the
      // heatmap); a row takes its tallest chart, the heatmap / card counts only when they are alone in it
      const STATS_EXTRA = {future_due: 90, review_intervals: 70, stability: 70, difficulty: 70, retrievability: 90, activity: 70, retention: 70, added: 70, hourly: 50};
      const bstats = grid.classList.contains('dd-bottomstats') && !grid.classList.contains('dd-nostats');
      const dom = [], ada = [], txt = [], onlyText = [], hmOnly = [];
      for (let r = 0; r < rowsN; r++){ dom.push(0); ada.push(0); txt.push(0); onlyText.push(true); hmOnly.push(true); }
      cards.forEach(function(c){
        const t = c.dataset.type, sp = Math.max(1, Math.min(cols, sizes.spans[t] || 1));
        const pw = sp * colW + (sp - 1) * gap;
        // a text: the height of its sentence (+ the card's padding); it sets the row's height only in a row of texts
        // (next to a chart it takes the chart's height), which neither grows with the window nor with the scale
        if (isText(t)){
          const c0 = c.querySelector('.dd-tx-in'), id = Object.keys(state.cards).filter(function(k){ return state.cards[k].card === c; })[0];
          const inst = id !== undefined && state.cards[id].inst;
          txt[c._row] = Math.max(txt[c._row], Math.max(44, (inst && inst.natural ? inst.natural() : (c0 ? c0.scrollHeight : 20)) + 26));
          return;
        }
        onlyText[c._row] = false;
        if (t !== 'heatmap') hmOnly[c._row] = false;
        let h = t === 'heatmap' ? 40 : 200;
        if (bstats) h += STATS_EXTRA[t] || 0;
        // the height of one column's width: a chart made wider (2 columns...) keeps its row's height (by its own width,
        // a 2-column chart made its row about twice as tall, the charts next to it with it)
        if (t !== 'heatmap') h = Math.max(h, Math.min(Math.floor(colW / 2.1), cap));
        else {
          h = Math.max(h, Math.floor(pw * 0.165 + 50));  // its grid follows its width (53 weeks of 7 days, labels and legend)
          // a narrow card (a phone): the year in two rows, the month grid or fewer months: the height it asks for
          const id = Object.keys(state.cards).filter(function(k){ return state.cards[k].card === c; })[0];
          const hi = id !== undefined && state.cards[id].inst, pl = c.querySelector('.dd-plot');
          if (hi && hi.narrow && hi.natural && pl && pl.clientWidth > 0){
            const inner = pw - (c.offsetWidth - pl.clientWidth);
            if (inner > 50 && hi.narrow(inner)) h = Math.max(40, hi.natural(inner) + (c.offsetHeight - pl.clientHeight));
          }
        }
        if (t === 'heatmap' || t === 'card_counts' || t === 'todays_retention') ada[c._row] = Math.max(ada[c._row], h); else dom[c._row] = Math.max(dom[c._row], h);
      });
      let hs = [];
      for (let r = 0; r < rowsN; r++) hs.push(onlyText[r] ? txt[r] : (dom[r] || ada[r] || NATURAL));
      { const firstChart = hs.filter(function(h, i){ return !onlyText[i]; })[0]; grid_state.autoH = firstChart || hs[0]; }
      grid_state.colW = colW; grid_state.gap = gap; grid_state.cols_eff = cols;
      if (sizes.scale) hs = hs.map(function(h, i){ return onlyText[i] ? h : Math.max(120, Math.round(h * sizes.scale)); });
      // Same Height for All Rows: a row of the heatmap alone keeps its own height (its grid's, the year in two rows on
      // a phone: much taller than a chart) and does not set the others'
      { const own = function(i){ return rowAll[i] || onlyText[i] || hmOnly[i]; };
        if (lay.shared && hs.length > 1){ const top = Math.max.apply(null, hs.filter(function(h, i){ return !own(i); }).concat([0])); if (top) hs = hs.map(function(h, i){ return own(i) ? h : top; }); } }
      hs = hs.map(function(h, i){ return rowAll[i] && !onlyText[i] ? 40 : h; });
      const natural = hs.reduce(function(s, h){ return s + h; }, 0) + gap * (rowsN - 1) + parseFloat(cs.paddingBottom);
      let free = (sizes.scale || !lay.fill) ? 0 : fillH - natural;
      if (free > 0){
        const caps = hs.map(function(h, i){ return onlyText[i] ? 0 : Math.floor(h * 0.6); }), out = hs.map(function(){ return 0; });
        let left = free;
        for (let k = 0; k < 3; k++){
          const open = out.map(function(v, i){ return i; }).filter(function(i){ return out[i] < caps[i]; });
          const base = open.reduce(function(s, i){ return s + hs[i]; }, 0);
          if (left <= 0 || base <= 0) break;
          open.forEach(function(i){ out[i] += Math.min(Math.floor(left * hs[i] / base), caps[i] - out[i]); });
          left = free - out.reduce(function(s, v){ return s + v; }, 0);
        }
        hs = hs.map(function(h, i){ return h + out[i]; });
      }
      grid.style.setProperty('--dd-cols', cols);
      grid.style.gridTemplateRows = hs.map(function(h){ return h + 'px'; }).join(' ');
      requestAnimationFrame(function(){ const minW = DD.isTouch() ? 24 : 60; Array.prototype.forEach.call(grid.children, function(c){ const sp = c.querySelector && c.querySelector('.dd-spacer'); if (sp) c.classList.toggle('nomore', sp.clientWidth < minW); }); });
    }
    function setCols(n){
      n = Math.max(1, Math.min(4, n));
      if (n === grid_state.cols) return;
      grid_state.cols = n; layoutGrid(); colsLabel();
      DD.call('set_grid_cols', {cols: n}).catch(function(){});
    }
    const colsBtn = root.querySelector('.dd-cols');
    function colsLabel(){ const s = colsBtn.querySelector('.dd-cols-n'); if (s) s.textContent = DD.t('{n} per row', {n: grid_state.cols}); }
    colsLabel();
    colsBtn.onclick = function(e){
      menu(e.currentTarget, [1, 2, 3, 4].map(function(n){ return [n, DD.tn('{n} chart per row', '{n} charts per row', n), n === grid_state.cols]; }), function(v){ setCols(+v); });
    };
    wrapEl.addEventListener('wheel', function(e){
      if (!e.ctrlKey) return;
      if (e.target && e.target.closest && e.target.closest('.dd-card')) return;
      e.preventDefault();
      setCols(grid_state.cols + (e.deltaY < 0 ? -1 : 1));
    }, {passive: false});
    new ResizeObserver(function(){ layoutGrid(); }).observe(wrapEl);

    // Resize handle: width in columns, height as a scale of the automatic height (shared by every row).
    function hasSizes(){ return !!sizes.scale || Object.keys(sizes.spans).some(function(k){ return sizes.spans[k] > 1; }); }
    DD.hasSizes = hasSizes;
    DD.resetSizes = function(){
      sizes.scale = null; sizes.spans = {}; layoutGrid();
      DD.call('reset_card_size', {}).catch(function(){});
    };
    grid.addEventListener('pointerdown', function(e){
      const h = e.target.closest && e.target.closest('.dd-rsz'); if (!h) return;
      const card = h.parentNode, type = card.dataset.type, mode = h.dataset.mode || 'rb'; e.preventDefault();
      try { h.setPointerCapture(e.pointerId); } catch (err) {}  // a touch lift's synthetic pointer has none
      const x0 = e.clientX, y0 = e.clientY, r = card.getBoundingClientRect(), w0 = r.width, h0 = r.height;
      // the floor of a resize: 200 px (60 for the heatmap), at least one column
      const minH = type === 'heatmap' ? 60 : 200;
      card.classList.add('dd-resizing');
      function mv(ev){
        const cols = grid_state.cols_eff || grid_state.cols, g = grid_state.gap || 12, cw = grid_state.colW || w0;
        if (mode.indexOf('r') >= 0){
          const sp = Math.max(1, Math.min(cols, Math.round((w0 + ev.clientX - x0 + g) / (cw + g))));
          sizes.spans[type] = sp;
        }
        if (mode.indexOf('b') >= 0){
          const auto = grid_state.autoH || h0;
          const sc = Math.max(minH / auto, Math.min(3, (h0 + ev.clientY - y0) / auto));
          sizes.scale = Math.abs(sc - 1) < 0.04 ? null : Math.round(sc * 100) / 100;
        }
        layoutGrid();
      }
      function up(){
        h.removeEventListener('pointermove', mv); h.removeEventListener('pointerup', up); h.removeEventListener('pointercancel', up); card.classList.remove('dd-resizing');
        if (sizes.spans[type] <= 1) delete sizes.spans[type];
        DD.call('set_card_size', {type: type, col_span: sizes.spans[type] || 1, scale: sizes.scale || 1}).catch(function(){});
        window.dispatchEvent(new Event('resize'));
      }
      h.addEventListener('pointermove', mv); h.addEventListener('pointerup', up); h.addEventListener('pointercancel', up);
    });

    // ---- drag a chart by its header to move it: the others shift live (ReorderEngine), saved on drop ----
    (function(){
      let dr = null;
      grid.addEventListener('pointerdown', function(e){
        // a finger drags through the touch lift below (hold, then move), never straight away: a swipe scrolls
        if (e.button !== 0 || e.pointerType === 'touch') return;
        // a chart by its title row, a text from anywhere on it (it has none); a lifted card from anywhere
        const head = e.target.closest && (e.ddTouch ? e.target.closest('.dd-card') : (e.target.closest('.dd-head') || e.target.closest('.dd-card.dd-text'))); if (!head) return;
        if (e.target.closest(e.ddTouch ? '.dd-rsz' : 'button, .dd-pills, .dd-help, .dd-hbtns, .dd-chev, .dd-pill, select, input, .dd-rsz, a')) return;
        const card = head.closest('.dd-card'); if (!card || card.classList.contains('dd-fs')) return;
        dr = {card: card, x0: e.clientX, y0: e.clientY, on: false};
      });
      function abortDrag(){
        if (!dr) return; const d = dr; dr = null;
        if (d.ghost) d.ghost.remove(); d.card.classList.remove('dd-cdrag'); document.body.classList.remove('dd-dragging');
      }
      window.addEventListener('pointercancel', function(e){ if (e.pointerType !== 'touch') abortDrag(); });
      window.addEventListener('blur', abortDrag);
      window.addEventListener('pointermove', function(e){
        if (!dr || e.pointerType === 'touch') return;
        if (!(e.buttons & 1)){ abortDrag(); return; }
        if (!dr.on){
          if (Math.abs(e.clientX - dr.x0) + Math.abs(e.clientY - dr.y0) < 8) return;
          dr.on = true; dr.card.classList.add('dd-cdrag');
          const r = dr.card.getBoundingClientRect(); dr.ox = e.clientX - r.left; dr.oy = e.clientY - r.top;
          const g = document.createElement('div'); g.className = 'dd-cghost'; g.style.width = r.width + 'px'; g.style.height = r.height + 'px';
          document.body.appendChild(g); dr.ghost = g; document.body.classList.add('dd-dragging');
        }
        dr.ghost.style.left = (e.clientX - dr.ox) + 'px'; dr.ghost.style.top = (e.clientY - dr.oy) + 'px';
        const over = document.elementFromPoint(e.clientX, e.clientY), t = over && over.closest && over.closest('.dd-card');
        if (!t || t === dr.card || t.parentNode !== grid) return;
        const r = t.getBoundingClientRect();
        const before = (e.clientY < r.top + r.height / 2) && (e.clientX < r.left + r.width / 2) || e.clientY < r.top + r.height * 0.25 || (e.clientX < r.left + r.width / 2 && e.clientY < r.bottom - r.height * 0.25);
        const first = new Map(); Array.prototype.forEach.call(grid.children, function(c){ first.set(c, c.getBoundingClientRect()); });
        grid.insertBefore(dr.card, before ? t : t.nextSibling);
        layoutGrid();
        // FLIP: the cards that moved glide to their new place
        Array.prototype.forEach.call(grid.children, function(c){
          if (c === dr.card) return;
          const a = first.get(c), b = c.getBoundingClientRect(); if (!a) return;
          const dx = a.left - b.left, dy = a.top - b.top; if (!dx && !dy) return;
          c.style.transition = 'none'; c.style.transform = 'translate(' + dx + 'px,' + dy + 'px)';
          requestAnimationFrame(function(){ c.style.transition = 'transform 180ms ease'; c.style.transform = ''; });
        });
      });
      window.addEventListener('pointerup', function(e){
        if (!dr || e.pointerType === 'touch') return; const d = dr; dr = null;
        if (!d.on) return;
        d.ghost.remove(); d.card.classList.remove('dd-cdrag'); document.body.classList.remove('dd-dragging');
        grid._justDragged = true; setTimeout(function(){ grid._justDragged = false; }, 0);
        const order = Array.prototype.map.call(grid.children, function(c){ return c.dataset.type; }).filter(Boolean);
        DD.call('chart_order', {order: order}).catch(function(){});
        layoutGrid();
      });
      grid.addEventListener('click', function(e){ if (grid._justDragged){ e.stopPropagation(); e.preventDefault(); } }, true);
    })();
    DD.layoutGrid = layoutGrid;


    // dev trace (PERF): long tasks (>50 ms) and frame gaps (>80 ms) go to debug.log
    (function(){
      if (!DD.dev) return;
      let n = 0;
      try { new PerformanceObserver(function(l){ l.getEntries().forEach(function(e){ if (n++ < 150) DD.trace('PERF longtask ' + e.duration.toFixed(0) + 'ms at ' + e.startTime.toFixed(0)); }); }).observe({entryTypes: ['longtask']}); } catch (e) {}
      // what the page did since the last frame (answers from Python, charts mounted), named on a frame gap
      DD._perfNotes = [];
      // where a long frame went (script or the rendering after it), when the browser tells (long-animation-frame)
      try {
        new PerformanceObserver(function(l){ l.getEntries().forEach(function(e){
          if (e.duration < 80 || n++ >= 150) return;
          const scr = (e.scripts || []).slice().sort(function(a, b){ return b.duration - a.duration; }).slice(0, 3).map(function(s){
            return (s.invoker || '?') + ' ' + Math.round(s.duration) + 'ms';
          });
          const render = e.renderStart ? Math.round(e.startTime + e.duration - e.renderStart) : 0;
          const style = e.styleAndLayoutStart ? Math.round(e.startTime + e.duration - e.styleAndLayoutStart) : 0;
          DD.trace('PERF long frame ' + Math.round(e.duration) + 'ms at ' + Math.round(e.startTime) + ': blocking ' + Math.round(e.blockingDuration || 0)
            + 'ms, render ' + render + 'ms (style+layout ' + style + 'ms), scripts [' + scr.join('; ') + ']');
        }); }).observe({type: 'long-animation-frame', buffered: false});
      } catch (e) { DD.trace('PERF long-animation-frame not supported'); }
      let last = performance.now();
      (function tick(t){
        if (t - last > 80 && n++ < 150) DD.trace('PERF frame gap ' + (t - last).toFixed(0) + 'ms' + (DD._perfNotes.length ? ' after [' + DD._perfNotes.join(', ') + ']' : ' (nothing the page did)'));
        last = t; if (DD._perfNotes.length) DD._perfNotes = []; requestAnimationFrame(tick);
      })(last);
      document.addEventListener('pointerdown', function(e){
        const t0 = performance.now(), el = e.target, d = (el.className && el.className.baseVal === undefined ? el.className : '') + '';
        requestAnimationFrame(function(){ requestAnimationFrame(function(){ if (n++ < 150) DD.trace('PERF click->2nd frame ' + (performance.now() - t0).toFixed(0) + 'ms on <' + el.tagName + ' ' + d.slice(0, 30) + '>'); }); });
      }, true);
    })();
    // every card gets its new data in the same frame: no cascade
    // The Python side runs on the UI thread: one call for every chart froze the window for 200+ ms (and the animations with it).
    // Charts are asked one by one (visible ones first), the UI breathes between two calls, an older round is dropped.
    function refresh(){
      EXP = null;
      if (DD.leaveAdaptiveSilently){ dotsToBars(true); DD.leaveAdaptiveSilently(); }
      DD._lastScope = state.deck + '|' + state.span + '|' + (state.searchQuery || '');
      // refresh_runtime: another period than the one shown animates as one ("timespan"), another deck as a deck change
      if (DD._spanShown === undefined) DD._spanShown = boot.span;  // the period shown at the opening (the first change of period animated as a deck change)
      const spanMode = DD._spanShown !== undefined && String(DD._spanShown) !== String(state.span) ? 'timespan' : undefined;
      DD._spanShown = state.span;
      const round = DD._round = (DD._round || 0) + 1, t0 = performance.now();
      cancelPendingLayout();
      DD._lastScopeAt = t0;
      // dev trace (SPEED): where the time of a deck / period change goes, from the click to the last chart moving
      const SP = {calls: [], first: null, last: null};
      DD._speed = SP;
      if (DD.perfWatch) DD.perfWatch((spanMode || 'deck') + ' change', 2200);  // dev trace: frames from the click to the charts at rest
      setTimeout(function(){ if (DD.dev && DD._speed === SP) DD.trace('ANIMTRACE SPEED ' + (spanMode || 'deck') + ': first chart starts at ' + (SP.first == null ? '-' : Math.round(SP.first) + 'ms') + ', last at ' + (SP.last == null ? '-' : Math.round(SP.last) + 'ms') + ' (+' + Math.round(600 * (DD.TEMPO || 1) / 2.4) + ' ms of its animation) | Python: ' + SP.calls.join(', ')); }, 2500);
      // the cards on screen at the click, in reading order (the wave's turns)
      let rank0 = null;
      const waveRank = function(){
        if (rank0) return rank0;
        const vh = window.innerHeight, cs = [];
        Object.keys(state.cards).forEach(function(id){ const c = state.cards[id].card; if (c.style.display === 'none') return; const r = c.getBoundingClientRect(); if (r.bottom > 0 && r.top < vh) cs.push([c, Math.round(r.top / 8), r.left]); });
        cs.sort(function(a, b){ return a[1] - b[1] || a[2] - b[2]; });
        const of = new Map(); cs.forEach(function(x, i){ of.set(x[0], i); });
        return (rank0 = {of: of, n: cs.length});
      };
      waveRank();
      DD.call('set_scope', {deck: state.deck, span: state.span}).catch(function(){});
      // the stat cards start with the charts on screen, once their data is in: Python reads the charts' data on Anki's
      // UI thread (~175 ms for a dozen charts), and the window shows no new frame meanwhile; the stat cards' numbers,
      // answered first, started rolling and froze for that time (ANIMTRACE PERF: a 117 ms frame)
      let chartsIn = null; const chartsReady = new Promise(function(r){ chartsIn = r; });
      setTimeout(function(){ chartsIn(); }, 1500);  // an answer that never comes: the stat cards still change
      if (scInst) Promise.all([DD.call('stats', {deck: state.deck, span: state.span, query: state.searchQuery || ''}), chartsReady]).then(function(a){
        if (round === DD._round){ DD._calm = 'dd'; try { scInst.update(a[0]); } finally { DD._calm = false; } }
      });
      // Charts whose data does not depend on the Deep Dive time span (card states / whole-history charts).
      const NO_SPAN = {
        heatmap: 1, card_counts: 1, future_due: 1, review_intervals: 1, stability: 1, difficulty: 1, retrievability: 1,
        interval_load: 1, due_today: 1, lapse_distribution: 1, review_distribution: 1, learning_steps: 1, time_distribution: 1,
        future_retention: 1, stability_increase: 1, leech_detector: 1, first_forgetting: 1, first_forgetting_short: 1,
        custom_pie: 1, text_label: 1,
      };
      const prevDeckQ = DD._lastDeckQ !== undefined ? DD._lastDeckQ : (boot.deck + '|');
      const curDeckQ = state.deck + '|' + (state.searchQuery || '');
      const spanOnly = !!(spanMode && prevDeckQ === curDeckQ);
      DD._lastDeckQ = curDeckQ;
      const vh = window.innerHeight;
      const order = state.widgets.filter(function(w){
        const c = state.cards[w.id];
        if (!c || c.late || c._deckQ !== curDeckQ) return true;
        return !(spanOnly && NO_SPAN[w.type]);
      }).sort(function(a, b){
        const ca = state.cards[a.id], cb = state.cards[b.id];
        const ra = ca && ca.card ? ca.card.getBoundingClientRect().top : 1e9, rb = cb && cb.card ? cb.card.getBoundingClientRect().top : 1e9;
        return (ra < vh ? 0 : 1) - (rb < vh ? 0 : 1) || ra - rb;
      });
      // one call gives everything Python can do in ~30 ms (all of it when already known), the rest is asked again
      // the charts on screen are read in one go and all start together (no cascade);
      // the ones out of view follow, as Python can (~30 ms a call)
      let lastVisIdx = -1;
      state.widgets.forEach(function(w, idx){
        const c = state.cards[w.id];
        if (!c || !c.card || c.card.style.display === 'none') return;
        const r = c.card.getBoundingClientRect();
        if (r.bottom > 0 && r.top < vh) lastVisIdx = idx;
      });
      const onScreen = order.filter(function(w){
        const c = state.cards[w.id];
        if (!c || !c.card) return false;
        const idx = state.widgets.indexOf(w);
        if (c.card.style.display === 'none') return idx <= lastVisIdx;
        const r = c.card.getBoundingClientRect();
        // Include cards in view, plus cards just above the viewport (up to 12) so shrinking grids (e.g. Deleted Cards)
        // resolve all cards that scroll back into view in the same first batch without a second layout jump.
        return (r.bottom > 0 && r.top < vh) || (r.bottom <= 0 && idx <= lastVisIdx && idx < 12);
      });
      const offScreen = order.filter(function(w){ return onScreen.indexOf(w) < 0; });
      return new Promise(function(done){
        (function next(left, first){
          if (round !== DD._round || !left.length){ done(); return; }
          const ask = first ? onScreen : left, args = {widgets: ask, deck: state.deck, span: state.span, query: state.searchQuery || ''};
          if (!first) args.budget_ms = 30;
          const ct = performance.now();
          DD.call('data', args).then(function(data){
            if (first) chartsIn();
            SP.calls.push('data ' + ask.length + ' charts asked, ' + Object.keys(data || {}).length + ' answered in ' + Math.round(performance.now() - ct) + 'ms (at +' + Math.round(ct - t0) + ')');
            if (round !== DD._round) return [];
            const rest = [];
            const vis = [], go = [];
            left.forEach(function(w){ const c = state.cards[w.id]; if (data && data[w.id] !== undefined){ if (c){
              const emp = !!(data[w.id] && data[w.id]._empty), shown = c.card.style.display !== 'none';
              if (emp === shown) vis.push([c.card, emp]);
              go.push([c, data[w.id]]); } } else rest.push(w); });
            // Web: the cards on screen take their new data one after the other, in reading order (a wave down the
            // page, ~0.5 s in all), each with its transition DD.TEMPO x slower; the ones out of view at once
            // the wave: each card on screen has its turn by its place in reading order among all the cards on screen
            // (not only those of this answer: Python answers in parts, and a later part started at once), counted
            // from the click; one whose data comes after its turn starts at once
            const rank = waveRank(), step = Math.min(55, 480 / Math.max(1, rank.n - 1)), since = performance.now() - t0;
            go.forEach(function(x, i){
              const ri = rank.of.get(x[0].card);
              const emp = !!(x[1] && x[1]._empty);
              // a card that goes (no data now): it keeps its picture while it fades out (its chart emptied at once
              // under the fade: it seemed to vanish); one that comes: its chart takes the data once the card shows
              // (updated while hidden, its animation ran unseen and it appeared done)
              if (emp && x[0].card.style.display !== 'none'){ if (DD.dev) DD.trace('ANIMTRACE scope ' + x[0].card.dataset.type + ' goes (no data): kept as it was while it fades out'); x[0].pendingData = x[1]; return; }
              let tries = 0;
              const run = function(){
                if (round !== DD._round) return;
                if (x[0].card.style.display === 'none' && !emp && tries++ < 20){ setTimeout(run, 50); return; }  // coming: wait until shown
                if (DD.dev) DD.trace('ANIMTRACE scope ' + x[0].card.dataset.type + ' ' + (spanMode || 'deck') + ' at +' + Math.round(performance.now() - t0) + 'ms (turn ' + (ri == null ? '-' : ri) + ')' + (DD._noAnim ? ' NOANIM' : '')
                  + (x[0].card._ddVis === false ? ' OUT-OF-VIEW (waits)' : '') + (x[0].card._ddObs && !x[0].card._ddSeen ? ' NEVER-SEEN (intro not played)' : ''));
                // a new deck / period: the charts' zoom resets they make on their own new data are not sent to the
                // others (their own new data is on its way, animated; the followers read again at once took it first,
                // without animation, and the wave's update then had nothing left to show)
                { const at = performance.now() - t0; if (SP.first == null) SP.first = at; SP.last = Math.max(SP.last || 0, at); }
                DD._calm = 'dd'; DD._scopeUpdate = true;
                try { DD.applyUpdate(x[0].card, function(){ x[0].inst.update(x[1], spanMode); }); x[0]._deckQ = curDeckQ; } finally { DD._calm = false; DD._scopeUpdate = false; }
              };
              const wait = ri == null ? 0 : ri * step - since;
              if (wait > 8) setTimeout(run, Math.round(wait)); else run();
            });
            setEmpty(vis);
            if (first) return offScreen.concat(rest.filter(function(w){ return offScreen.indexOf(w) < 0; }));
            return rest.length === left.length ? [] : rest;
          }).catch(function(){ if (first) chartsIn(); return []; }).then(function(rest){
            // Wait until the visible wave has actually started (180ms) and finished animating (or user scrolls)
            // before fetching offscreen charts, so offscreen batches never interrupt visible transitions/reflows.
            if (first) setTimeout(function(){ if (round === DD._round) whenIdleOrScroll(function(){ next(prioritizeVisible(rest || []), false); }, 1800 * (DD.speed ? DD.speed() : 1)); }, 180);
            else setTimeout(function(){ next(prioritizeVisible(rest || []), false); }, 0);
          });
        })(order, onScreen.length > 0);
        if (!onScreen.length) chartsIn();
      });
    }
    // Same look as the add-on's StyledMenu. items: [value, label, checked?, icon?, keepOpen?] or 'sep'.
    DD.menu = DD.webMenu;
    // dev trace (CALL): each Python call, its time and failures
    (function(){
      if (!DD.dev) return;
      const orig = DD.call; let n = 0;
      DD.call = function(cmd, args){
        const id = ++n, t0 = performance.now(), noisy = (cmd === 'set_drawer' || cmd === 'dd_log');
        return orig.apply(DD, arguments).then(function(r){
          const ms = Math.round(performance.now() - t0); if (n < 400 && (ms > 400 || !noisy)) DD.trace('CALL #' + id + ' ' + cmd + ' ' + ms + 'ms');
          return r;
        }, function(err){ DD.trace('CALL #' + id + ' ' + cmd + ' FAILED ' + (err && err.message || err)); throw err; });
      };
    })();
    // dev trace (CLICKTRACE): a pointer press that is not followed by a click, and what sits under the pointer
    (function(){
      if (!DD.dev) return;
      let seq = 0, pend = null, lines = 0;
      const nm = function(el){ if (!el || !el.tagName) return String(el); return el.tagName.toLowerCase() + (el.className && el.className.baseVal === undefined ? '.' + String(el.className).trim().split(/\s+/).slice(0, 2).join('.') : ''); };
      const log = function(s){ if (lines++ < 80) DD.trace('CLICKTRACE ' + s); };
      window.addEventListener('pointerdown', function(e){
        pend = {id: ++seq, tgt: nm(e.target), top: nm(document.elementFromPoint(e.clientX, e.clientY)), clicked: false, x: e.clientX | 0, y: e.clientY | 0};
        if (pend.tgt !== pend.top) log('#' + pend.id + ' target ' + pend.tgt + ' != under pointer ' + pend.top + ' at ' + pend.x + ',' + pend.y);
      }, true);
      window.addEventListener('click', function(){ if (pend) pend.clicked = true; }, true);
      window.addEventListener('pointercancel', function(e){ log('pointercancel on ' + nm(e.target)); }, true);
      window.addEventListener('pointerup', function(){
        const p = pend; if (!p) return;
        setTimeout(function(){ if (!p.clicked) log('#' + p.id + ' NO click after press on ' + p.tgt + ' (under: ' + p.top + ') at ' + p.x + ',' + p.y + ' drawer=' + (typeof drawer !== 'undefined' && drawer.open) + ' dragging=' + document.body.classList.contains('dd-dragging')); }, 300);
      }, true);
    })();
    // a header control of a chart changed (Backlog, Breakdown, range...): stored, then that chart is read again
    DD.setWidgetSetting = function(type, key, value){
      if (DD.dev) DD.trace('ANIMTRACE setting ' + type + '.' + key + ' = ' + JSON.stringify(value));
      return DD.call('set_setting', {section: type, key: key, value: value}).then(function(){
        const w = state.widgets.filter(function(x){ return x.type === type; })[0]; if (!w) return;
        return DD.call('data', {widgets: [w], deck: state.deck, span: state.span, query: state.searchQuery || ''}).then(function(d){
          const c = state.cards[w.id]; if (!(c && d && d[w.id])) return;
          // another breakdown: the colours change at once, the bars stay (an animation moved them a little)
          const still = key === 'breakdown', prev = DD._noAnim; if (still) DD._noAnim = true;
          try { c.inst.update(d[w.id], key === 'time_span_idx' ? undefined : 'timespan'); } finally { DD._noAnim = prev; }
        });
      }).catch(function(e){ DD.log('setting ' + type + '.' + key + ': ' + (e && e.message || e)); });
    };
    DD.openWidgetSettings = function(type){ DD.call('widget_settings', {wtype: type, deck: state.deck || null}); };
    // View by Deck / View by Time: the table shows the time spans of one deck (tabs = decks) instead of the decks of one span
    const viewBtn = root.querySelector('.dd-view');
    // both names in the button, the other one hidden: its width stays the same whichever is shown (nothing moves)
    function viewHtml(mode){
      const deck = mode === 'deck';
      return icon(deck ? 'calendar' : 'activity', 14) + '<span class="dd-view-l"><span' + (deck ? ' class="off"' : '') +
        '>View by Deck</span><span' + (deck ? '' : ' class="off"') + '>View by Time</span></span>';
    }
    if (viewBtn) viewBtn.innerHTML = viewHtml('time');

    function setView(mode, persist){
      state.view = mode;
      viewBtn.innerHTML = viewHtml(mode); if (DD.translate) DD.translate(viewBtn);
      syncSearchMode();
      if (tblInst) tblInst.setMode(mode, deckViewKey(), String(state.span));
      if (persist) DD.call('set_view_mode', {mode: mode}).catch(function(){});
    }
    if (viewBtn){
      viewBtn.onclick = function(){ setView(state.view === 'deck' ? 'time' : 'deck', true); };
      // opened in the view it was left in, at once, not by time first
      if (boot.view_mode === 'deck'){
        state.view = 'deck';
        viewBtn.innerHTML = viewHtml('deck');
        const sr = root.querySelector('.dd-search'); if (sr) sr.placeholder = 'Search decks...';
        if (tblInst && tblInst.startMode) tblInst.startMode('deck', deckViewKey(), String(state.span), boot.table);
        else setTimeout(function(){ setView('deck', false); }, 0);
      }
    }
    root.querySelector('.dd-span').onclick = function(e){ spanMenu(e.currentTarget); };
    function spanMenu(anchor){
      menu(anchor, spanList().map(function(p, i){ return [i, p[0], p[1] === state.span, null, 'radio']; }).concat(['sep', ['add', 'Add New Time Span', null, 'plus']]), function(v){ if (v === 'add'){ DD.call('open_settings', {start_tab: 'Time Span'}); return; } state.span = +spanList()[+v][1]; setTitle(); refresh(); });
    }
    // web: the deck chooser opens over the button, in the page: a search field, then
    // Collection and every deck as a tree; typing filters on the whole name, Enter takes the first one, Esc closes
    const deckBtn = root.querySelector('.dd-deck');
    deckBtn.onclick = function(e){ e.stopPropagation(); deckPick(deckBtn); };
    // anchor: the bar's button (the list above it) or a fullscreen chart's chip (under it)
    function deckPick(anchor){
      const open = document.querySelector('.dd-deckpick');
      document.querySelectorAll('.dd-menu').forEach(function(o){ o.remove(); });
      if (open){ return; }  // the button clicked again: closed
      const pop = document.createElement('div'); pop.className = 'dd-menu dd-deckpick';
      pop.innerHTML = '<input class="dd-dp-search" placeholder="Search decks..." spellcheck="false"><div class="dd-dp-list"></div>';
      document.body.appendChild(pop);
      const input = pop.querySelector('input'), list = pop.querySelector('.dd-dp-list');
      const decks = (boot.decks || []).slice().sort(function(a, b){ return a[1].localeCompare(b[1]); });
      let items = [];
      function pick(id){
        pop.remove(); document.removeEventListener('mousedown', away, true);
        DD.onDeckPicked(+id);
      }
      function render(){
        const q = input.value.trim().toLowerCase();
        list.innerHTML = ''; items = [];
        // Collection apart, first (every deck), then the decks as a tree: a line per level on the left, a caret on a
        // deck that has decks under it
        if (!q || 'collection'.indexOf(q) >= 0){
          const c = document.createElement('div'); c.className = 'dd-mi dd-dp-row dd-dp-all' + (state.deck === 0 ? ' on' : '');
          c.innerHTML = icon('layers', 14) + '<span>Collection</span><span class="dd-dp-hint">all decks</span>';
          c.onclick = function(){ pick(0); };
          list.appendChild(c); items.push(c);
          const sep = document.createElement('div'); sep.className = 'dd-dp-sep'; list.appendChild(sep);
        }
        const shown = decks.filter(function(d){ return !q || d[1].toLowerCase().indexOf(q) >= 0; });
        shown.forEach(function(d, i){
          const parts = d[1].split('::'), depth = q ? 0 : parts.length - 1;
          const parent = !q && decks.some(function(x){ return x[1].indexOf(d[1] + '::') === 0; });
          const b = document.createElement('div'); b.className = 'dd-mi dd-dp-row' + (d[0] === state.deck ? ' on' : '') + (parent ? ' dd-dp-parent' : '');
          b.style.setProperty('--d', depth); b.style.paddingLeft = (10 + depth * 16) + 'px'; b.title = d[1];
          const caret = document.createElement('span'); caret.className = 'dd-dp-caret'; caret.textContent = parent ? '\u25be' : '';
          const name = document.createElement('span'); name.className = 'dd-dp-name'; name.textContent = q ? d[1] : parts[parts.length - 1];
          b.appendChild(caret); b.appendChild(name);
          b.onclick = function(){ pick(d[0]); };
          list.appendChild(b); items.push(b);
        });
        if (!items.length){ const n = document.createElement('div'); n.className = 'dd-dp-none'; n.textContent = 'No deck found.'; list.appendChild(n); }
        let sel = list.querySelector('.dd-dp-row.on') || items[0]; mark(sel, q ? items[0] : sel);
      }
      let cur = null;
      function mark(_, el){ if (cur) cur.classList.remove('dd-dp-cur'); cur = el || null; if (cur){ cur.classList.add('dd-dp-cur'); cur.scrollIntoView({block: 'nearest'}); } }
      input.addEventListener('input', render);
      input.addEventListener('keydown', function(ev){
        if (ev.key === 'Escape'){ pop.remove(); document.removeEventListener('mousedown', away, true); return; }
        if (ev.key === 'Enter' && cur){ cur.click(); return; }
        if (ev.key === 'ArrowDown' || ev.key === 'ArrowUp'){
          ev.preventDefault(); const i = items.indexOf(cur), j = Math.max(0, Math.min(items.length - 1, i + (ev.key === 'ArrowDown' ? 1 : -1))); mark(null, items[j]);
        }
      });
      function away(ev){ if (!pop.contains(ev.target) && !anchor.contains(ev.target)){ pop.remove(); document.removeEventListener('mousedown', away, true); } }
      document.addEventListener('mousedown', away, true);
      render();
      // above the button, kept in the window (under a chip in a chart's header)
      const r = anchor.getBoundingClientRect();
      pop.style.left = Math.max(4, Math.min(r.left, window.innerWidth - pop.offsetWidth - 4)) + 'px';
      if (anchor === deckBtn) pop.style.bottom = (window.innerHeight - r.top + 4) + 'px';
      else { pop.style.top = (r.bottom + 4) + 'px'; pop.style.maxHeight = Math.max(160, window.innerHeight - r.bottom - 12) + 'px'; }
      if (!DD.isTouch()) input.focus();  // a phone: the list first, the keyboard only on a tap in the field
    }

    const filterBtn = root.querySelector('.dd-filter');
    function applySearchResult(res){
      state.searchQuery = (res && res.query) || '';
      state.searchCount = (res && res.query) ? res.count : null;
      if (res && Array.isArray(res.recent)) state.recentSearches = res.recent.slice();
      setTitle();
      refresh();
    }
    if (filterBtn){
      const clrX = filterBtn.querySelector('.dd-flt-x');
      if (clrX){
        clrX.onclick = function(e){
          e.stopPropagation();
          applySearchResult({ok: true, query: '', count: null});
        };
      }
      filterBtn.onclick = function(e){
        e.stopPropagation();
        DD.openSearchPopover(
          filterBtn,
          state.searchQuery,
          state.recentSearches,
          function(q){ return DD.call('resolve_search', {query: q}); },
          applySearchResult
        );
      };
    }
    // the window already open, asked for a deck and a period (a pinned widget's "Open in Deep Dive")
    DD.openScope = function(did, span){
      if (span != null) state.span = +span;
      DD._lastScope = null;
      DD.onDeckPicked(did);
    };
    // several decks picked together in the table: a list of deck ids (and "deleted"), titled "N decks"
    DD.onDeckPicked = function(did){
      if (Array.isArray(did)){ state.deck = did.slice(); state.deckTitle = DD.tn('{n} deck', '{n} decks', did.length, {n: did.length}); }
      else {
        state.deck = +did;
        const d = boot.decks.filter(function(x){ return x[0] === state.deck; })[0];
        state.deckTitle = state.deck === 0 ? 'Total' : state.deck === -1 ? 'Deleted Cards' : (d ? d[1].split('::').pop() : state.deckTitle);
      }
      setTitle();
      // let the table repaint first; coalesce rapid clicks; skip when the scope did not change
      // right after the table has repainted (an older round is dropped by refresh itself)
      clearTimeout(DD._pickT);
      DD._pickT = setTimeout(function(){
        const k = state.deck + '|' + state.span;
        if (DD._lastScope === k) return;
        DD._lastScope = k; refresh();
      }, 16);
    };
    // ---- card interactions: collapse by the chevron, right-click menu ----
    const DAILYX = ['ratings', 'review_speed', 'forgotten', 'resets', 'introduced', 'introduced_load', 'answer_time', 'interval_ratings', 'rating_fatigue', 'sibling_ratings', 'card_states', 'load_trend', 'stability_trend', 'memorised', 'fsrs_calibration', 'forgetting_curve', 'fsrs_fatigue', 'leech_detector', 'stability_increase', 'custom_bar', 'future_retention', 'due_today'];
    const AVG = ['activity', 'added', 'retention', 'ratings', 'review_speed', 'forgotten', 'introduced'];
    const STATS = ['activity', 'added', 'retention', 'hourly', 'future_due', 'review_intervals', 'stability', 'difficulty', 'retrievability'].concat(Object.keys(DD.extraTitles || {}));
    grid.classList.toggle('dd-nostats', boot.show_stats === false);
    grid.classList.toggle('dd-bottomstats', boot.show_bottom_stats === true);
    const CUM = ['activity', 'future_due', 'review_intervals', 'stability', 'difficulty', 'retrievability', 'forgotten', 'resets', 'introduced', 'introduced_load', 'due_today', 'interval_load', 'lapse_distribution', 'review_distribution', 'learning_steps', 'time_distribution', 'interval_history', 'stability_history'];
    // the charts with bins (context_menu binning_charts: the base ones and every added chart of days or values)
    const BIN = ['future_due', 'review_intervals', 'stability', 'difficulty', 'retrievability', 'interval_load', 'lapse_distribution', 'review_distribution', 'learning_steps', 'time_distribution', 'interval_history', 'stability_history', 'difficulty_history', 'ratings', 'review_speed', 'forgotten', 'introduced', 'introduced_load', 'answer_time', 'interval_ratings', 'rating_fatigue', 'sibling_ratings', 'card_states', 'load_trend', 'stability_trend', 'memorised', 'fsrs_calibration', 'forgetting_curve', 'fsrs_fatigue', 'leech_detector', 'stability_increase', 'custom_bar', 'future_retention'];
    const OPT_KEY = {show_breakdown: 'breakdown_enabled'};
    function cardOpt(w, k, dflt){ const v = w.options && w.options[k]; return v === undefined ? dflt : !!v; }
    function setOpt(w, section, key, val, optKey){
      w.options = w.options || {}; w.options[optKey || key] = val;
      const c = state.cards[w.id];
      if (c){ const o = {}; o[optKey || key] = val; c.inst.setOptions(o); }
      DD.call('set_setting', {section: section, key: key, value: val}).catch(function(){});
    }
    function toast(text, undo){
      const old = document.querySelector('.dd-toast'); if (old) old.remove();
      const t = document.createElement('div'); t.className = 'dd-toast';
      t.innerHTML = '<span></span>' + (undo ? '<button class="dd-toast-u">Undo</button>' : '');
      t.firstChild.textContent = text; document.body.appendChild(t);
      const tm = setTimeout(function(){ t.remove(); }, 6000);
      if (undo) t.querySelector('button').onclick = function(){ clearTimeout(tm); t.remove(); undo(); };
    }
    // a chart fullscreen on a phone (the bottom bar under it): the deck and the period after its title, as on a
    // pinned chart (pinned.js chips), opening the bar's own choosers
    function fsChips(card){
      const t = card.querySelector('.dd-title'); if (!t) return [];
      const out = [['span', function(el){ const r = el.getBoundingClientRect(); spanMenu({x: r.left, y: r.bottom + 2, top: r.top}); }], ['deck', function(el){ deckPick(el); }]].map(function(p){
        const ch = document.createElement('span'); ch.className = 'ddp-chip dd-fs-chip'; ch.dataset.k = p[0];
        ch.innerHTML = '<span></span><svg width="7" height="5" viewBox="0 0 7 5"><path d="M.5 1 3.5 4 6.5 1" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/></svg>';
        ch.addEventListener('mousedown', function(ev){ ev.stopPropagation(); });
        ch.addEventListener('click', function(ev){ ev.stopPropagation(); p[1](ch); });
        return ch;
      });
      out.slice().reverse().forEach(function(ch){ t.parentNode.insertBefore(ch, t.nextSibling); });
      fsChipText();
      // the header's total and average: away when they no longer fit whole (a cut "To..."), back when they do
      const stat = card.querySelector('.dd-head .dd-stat');
      if (stat){
        const fit = function(){ stat.style.display = ''; if (stat.scrollWidth > stat.clientWidth + 1) stat.style.display = 'none'; };
        const ro = new ResizeObserver(function(){ requestAnimationFrame(fit); }); ro.observe(card);
        out.push({remove: function(){ ro.disconnect(); stat.style.display = ''; }});
      }
      return out;
    }
    function fsChipText(){
      document.querySelectorAll('.dd-fs-chip').forEach(function(ch){
        const deck = ch.dataset.k === 'deck', label = deck ? (state.deckTitle || DD.t('Deck')) : (periodLabel() || DD.t('Time Span'));
        ch.firstChild.textContent = label;
        ch.title = deck ? DD.t('Deck: {name}', {name: state.deckTitle || ''}) : DD.t('Time Span: {name}', {name: periodLabel()});
      });
    }
    function fullscreen(w){
      const c = state.cards[w.id]; if (!c) return;
      const ph = document.createComment('dd-fs'); c.card.parentNode.insertBefore(ph, c.card);
      c.card.classList.add('dd-fs'); document.body.appendChild(c.card);
      const back = document.createElement('button'); back.className = 'dd-fs-x'; back.innerHTML = icon('x', 16);
      c.card.appendChild(back);
      // the window's bottom bar stays under it (dd.css body.dd-fsbar): its deck and time span can still be changed
      document.body.classList.add('dd-fsbar');
      if (DD._updateRZoom) DD._updateRZoom();  // its own reset arrow while it hides the window's
      // a heatmap: the calendar centered, the screen's width, only as tall as its grid (its controls above it, its
      // legend under it, not at the screen's edges)
      let hmRO = null; const body = c.card.querySelector('.dd-body'), oldBodyH = body ? body.style.height : '';
      if (w.type === 'heatmap' && body && c.inst.natural){
        c.card.classList.add('dd-fs-hm');
        const fit = function(){
          const nh = c.inst.natural(Math.max(150, body.clientWidth));
          if (nh > 0 && body.style.height !== nh + 'px') body.style.height = nh + 'px';
        };
        fit(); hmRO = new ResizeObserver(fit); hmRO.observe(c.card);
        // a mode button (YRS, 365, ...) changes the height the grid asks for
        c.card._hmFsClick = function(){ setTimeout(fit, 0); }; c.card.addEventListener('click', c.card._hmFsClick, true);
      }
      // a phone: the chart in a layer of its own over the bottom bar, the deck and the period as chips in its header
      // (fsChips); held upright, the layer turned to landscape (DD.rot), the charts best seen wide by default; its
      // button beside the "x" turns it back, the choice kept for the chart type. The phone turned to landscape: the
      // layer as it is, the same view; held upright again, turned again
      let wrap = null, turn = null, unwatch = null, chips = null;
      function unwrap(){
        if (!wrap) return;
        document.body.appendChild(c.card); wrap.remove(); wrap = null;
      }
      function land(want){
        if (want && !DD.rot.active()){ if (DD.rot.on(wrap, function(){ turn.classList.remove('on'); if (DD.frame) DD.frame.kick(); })) turn.classList.add('on'); }
        else if (!want && DD.rot.active()){ DD.rot.off(); turn.classList.remove('on'); }
        if (DD.frame) DD.frame.kick();
      }
      if (DD.isTouch() && DD.rot){
        wrap = document.createElement('div'); wrap.className = 'dd-rot-wrap';
        document.body.appendChild(wrap); wrap.appendChild(c.card);
        chips = fsChips(c.card);
        turn = document.createElement('button'); turn.className = 'dd-fs-turn'; turn.title = 'Rotate'; turn.innerHTML = DD.rot.icon;
        c.card.appendChild(turn);
        turn.onclick = function(){ const want = !DD.rot.active(); land(want); DD.rot.remember(w.type, want); };
        if (DD.rot.upright() && DD.rot.wanted(w.type)) land(true);
        unwatch = DD.rot.upagain(function(){ if (!DD.rot.active() && DD.rot.wanted(w.type)) land(true); });
      }
      function close(){
        if (unwatch){ unwatch(); unwatch = null; }
        if (DD.rot && DD.rot.active()) DD.rot.off();
        unwrap();
        if (turn){ turn.remove(); turn = null; }
        if (chips){ chips.forEach(function(x){ x.remove(); }); chips = null; }
        if (hmRO){ hmRO.disconnect(); hmRO = null; body.style.height = oldBodyH; c.card.classList.remove('dd-fs-hm'); c.card.removeEventListener('click', c.card._hmFsClick, true); }
        document.removeEventListener('keydown', key, true); back.remove(); c.card.classList.remove('dd-fs');
        document.body.classList.remove('dd-fsbar');
        ph.parentNode.insertBefore(c.card, ph); ph.remove(); layoutGrid(); if (DD.frame) DD.frame.kick();
        if (DD._updateRZoom) DD._updateRZoom();
      }
      function key(e){ if (e.key === 'Escape'){ e.stopPropagation(); close(); } }
      document.addEventListener('keydown', key, true); back.onclick = close;
      if (DD.frame) DD.frame.kick();
    }
    // a text taken off, with its Undo (back at its place, with the same sentence)
    function removeText(w){
      DD.call('remove_text', {wid: w.id}).then(function(r){
        DD.bridgeRebuild && DD.bridgeRebuild();
        if (r) toast(DD.t('Text removed'), function(){ DD.call('restore_text', {wid: w.id, template: r.template, index: r.index}).then(function(){ DD.bridgeRebuild && DD.bridgeRebuild(); }); });
      }).catch(function(){});
    }
    function textMenu(w, x, y, top){
      const items = [['edit', DD.t('Edit Text...'), undefined, 'pencil'], 'sep'];
      if (DD.hasSizes && DD.hasSizes()) items.push(['rsz', 'Reset Size', undefined, 'reset'], 'sep');
      items.push(['add', 'Add Chart...', undefined, 'chartplus'], ['remove', 'Remove', undefined, 'trash']);
      menu({x: x, y: y, top: top}, items, function(k){
        if (k === 'edit') editText(w);
        else if (k === 'rsz') DD.resetSizes();
        else if (k === 'add') DD.call('open_gallery', {family: 'text'});
        else if (k === 'remove') removeText(w);
      });
    }
    // the chart's own options (own: its header's options icon, the entries of this chart alone; dry: their count,
    // no menu)
    function cardMenu(w, x, y, top, own, dry){
      if (isText(w.type)){ if (!own) textMenu(w, x, y, top); return 0; }
      const c = state.cards[w.id], t = w.type, items = [];
      if (!c || !c.inst) return 0;
      // the options of its header's icon (Include Suspended Cards, ...: DD.optionsPill)
      const xo = c.card.querySelector('.dd-head') && c.card.querySelector('.dd-head')._ddOpt;
      const xoItems = xo ? DD.optItems(xo) : [], isAct = function(i){ return xo.items[i][4] === 'action'; };
      // the chart's context menu
      if (!own){
        items.push(['fs', c.card.classList.contains('dd-fs') ? 'Exit Fullscreen' : 'Fullscreen', undefined, 'maximize'], 'sep');
        items.push(['settings', 'Settings', undefined, 'gear']);
        // its own windows (Edit Searches...) right under Settings, not again with its other options
        xoItems.forEach(function(it, i){ if (isAct(i)) items.push(it); });
        // its explanation (the "?"'s text), when it has one
        if (helpCache[t]) items.push(['help', 'About This Chart', undefined, 'help']);
        items.push('sep');
      }
      // the options of its header's icon, first (its windows: under Settings, and a pill of their own)
      if (xo) items.push('sep', ...xoItems.filter(function(it, i){ return !isAct(i); }));
      const isAvg = AVG.indexOf(t) >= 0;
      if (isAvg){
        items.push('sep', ['avg', 'Show Average', cardOpt(w, 'show_average', true), null, true], ['avga', 'Average on Active Days', cardOpt(w, 'avg_on_active_days', true), null, true]);
        if (t === 'retention'){
          const barsOn = cardOpt(w, 'review_bars', true), mr = (w.options && w.options.min_reviews) | 0;
          items.push(['fit', 'Within data limit', cardOpt(w, 'fit_to_data', false), null, true],
            ['rb', 'Review Bars', undefined, null, false, [['bars', 'Show Bars', barsOn, null, true], ['axis', 'Show Count Axis', cardOpt(w, 'review_axis', false), null, true, null, !barsOn]]],
            ['round', 'Rounded Look', cardOpt(w, 'rounded', true), null, true],
            ['minrev', DD.t('Min Reviews per Point: {value}...', {value: mr ? mr : DD.t('Off')})]);
        }
        if (t === 'added') items.push(['sync', 'Sync with other charts', cardOpt(w, 'sync_zoom', true), null, true]);
      }
      if (t === 'activity'){
        const hid = (w.options && w.options.hidden_review_types) || [];
        const RT = [['learn', 'Learning'], ['young', 'Young'], ['mature', 'Mature'], ['relearn', 'Relearning'], ['cram', 'Filtered / custom study']];
        const vis = RT.length - hid.length;
        items.push(['rt', 'Review Types', undefined, null, false, RT.map(function(r){ const shown = hid.indexOf(r[0]) < 0; return ['rt:' + r[0], r[1], shown, null, true, null, shown && vis <= 1]; })]);
      }
      if (CUM.indexOf(t) >= 0){ if (!isAvg) items.push('sep'); items.push(['cum', 'Show Right Axis', cardOpt(w, 'show_cumulative', true), null, true]); }
      if (t === 'future_due'){
        if (w.options && (w.options.breakdown === 'type' || (w.options.breakdown == null && w.options.show_breakdown))){
          const hs = (w.options && w.options.hidden_series) || [];
          const SR = [['mature', 'Mature'], ['young', 'Young'], ['learn', 'Learning']];
          items.push(['sr', 'Series', undefined, null, false, SR.map(function(r){ const shown = hs.indexOf(r[0]) < 0; return ['sr:' + r[0], r[1], shown, null, true, null, shown && SR.length - hs.length <= 1]; })]);
        }
      } else if (c.inst.seriesChoices){
        const SRX = c.inst.seriesChoices(), hsx = (w.options && w.options.hidden_series) || [];
        if (SRX.length > 1) items.push(['sr', 'Series', undefined, null, false, SRX.map(function(r){ const shown = hsx.indexOf(r[0]) < 0; return ['sr:' + r[0], r[1], shown, null, true, null, shown && SRX.length - hsx.length <= 1]; })]);
      }
      const noSplit = t === 'card_states' && !(w.options && w.options.alt_view);
      if ((['ratings', 'forgotten', 'introduced', 'answer_time', 'interval_ratings', 'rating_fatigue', 'sibling_ratings', 'fsrs_calibration', 'forgetting_curve', 'card_states', 'load_trend'].indexOf(t) >= 0 && !noSplit)
          || (t === 'future_due' && w.options && w.options.breakdown === 'result')
          || (t === 'activity' && cardOpt(w, 'show_breakdown', true))) items.push(['pct', 'Show as %', cardOpt(w, 'show_percent', false), null, true]);
      // a line through the bars, its slope in the header
      if ((DD.trendCharts || []).indexOf(t) >= 0) items.push(['trend', 'Show Trend', cardOpt(w, 'show_trend', t !== 'activity' && t !== 'added'), null, true]);
      if ((t === 'activity' || t === 'retention' || BIN.indexOf(t) >= 0) && t !== 'due_today' && t !== 'week_hours')
        items.push(['adapt', 'Adaptive Binning', cardOpt(w, t === 'retention' ? 'binning' : 'adaptive_binning', true), null, true]);
      if (!own && STATS.indexOf(t) >= 0) items.push('sep', ['bstats', 'Show Bottom Stats (All Charts)', grid.classList.contains('dd-bottomstats'), null, true], ['stats', 'Show Stats (All Charts)', !grid.classList.contains('dd-nostats'), null, true]);
      // the axis numbers' animation (a chart with a numbered axis)
      if (!own && ['heatmap', 'card_counts', 'todays_retention', 'week_hours', 'sxr_heatmap'].indexOf(t) < 0) items.push('sep', axisAnimItem());
      // First Answer Retention: the cards counted (as its header's pill)
      const retHead = t === 'todays_retention' && c.card && c.card.querySelector('.dd-head'), retP = retHead && retHead._retPayload;
      if (retP && DD.retentionOptions) items.push.apply(items, ['sep', ['rkind', 'Cards', undefined, null, false, DD.retentionMenu(retP)]].concat(DD.retentionOptions(retP)));
      const legendItems = (t === 'card_counts' || t === 'todays_retention') && DD.pieLegendMenu && DD.pieLegendMenu(c.card);
      if (legendItems) items.push('sep', ['plgm', 'Legend Layout', undefined, null, false, legendItems]);
      // a Time Machine: its slider under the bars shown or not (the date pill stays)
      if (c.inst && c.inst.machine) items.push('sep', ['dslider', 'Day Slider', c.inst.machine.on(), null, true]);
      // its Time Machine: added right after it, or brought into view when it is already shown
      const past = DD.pastOf[t];
      if (past) items.push('sep', ['past', 'View on a Past Day', undefined, 'history']);
      if (!own) items.push('sep', ['pin', DD.t('Pin {name} to main menu', {name: titleOf(t)}), undefined, 'pin']);
      if (t === 'heatmap'){
        const cur = String((w.options && w.options.metric) || 'reviews').split('+');
        const M = [['reviews', 'Reviews'], ['time', 'Time spent'], ['correct', 'Correct answers'], ['failed', 'Failed answers'], ['retention', 'Retention %'], ['avg_time', 'Average time per review']];
        const TM = [['new', 'New cards'], ['young', 'Young reviews'], ['mature', 'Mature reviews'], ['relearn', 'Relearning'], ['cram', 'Filtered']];
        const tkeys = TM.map(function(x){ return x[0]; });
        const sub = [['hint', 'Check several to combine them', undefined, null, false, null, true]];
        M.forEach(function(m){ sub.push(['hm:' + m[0], m[1], cur.indexOf(m[0]) >= 0, null, true]); });
        sub.push('sep', ['hmtext', 'Card types', undefined, null, false, null, true],
          ['hm:alltypes', 'All card types', !cur.some(function(k){ return tkeys.indexOf(k) >= 0; }), null, true]);
        TM.forEach(function(m){ sub.push(['hm:' + m[0], m[1], cur.indexOf(m[0]) >= 0, null, true]); });
        const pal = (w.options && w.options.palette) || '';
        const psub = [['', 'Chosen color'], ['lime', 'Lime'], ['olive', 'Olive'], ['ice', 'Ice'], ['magenta', 'Magenta'],
          ['flame', 'Flame'], ['rainbow', 'Rainbow'], ['ocean', 'Ocean'], ['sunset', 'Sunset'],
          ['viridis', 'Viridis']].map(function(p){ return ['hmp:' + p[0], p[1], pal === p[0]]; });
        // the user's own gradients (saved in Settings)
        const mine = (w.options && w.options.custom_palettes) || [];
        if (mine.length){ psub.push('sep'); mine.forEach(function(p){ psub.push(['hmp:custom:' + p.id, p.name, pal === 'custom:' + p.id]); }); }
        // a gradient of one's own, made from the palette shown (or the one chosen changed), in a small window
        psub.push('sep', ['hmpnew', 'New gradient...', undefined, 'palette']);
        if (pal.indexOf('custom:') === 0) psub.push(['hmpedit', 'Edit gradient...', undefined, 'gear']);
        const hmCol = (w.options && w.options.color && /^#[0-9a-f]{3,8}$/i.test(w.options.color)) ? w.options.color : 'palette';
        items.push('sep', ['hmcol', 'Color...', undefined, hmCol], ['hmpal', 'Palette', undefined, null, false, psub],
          ['hmi', 'Multicolor Intensity', cardOpt(w, 'multi_hue', false), null, true, null, pal !== ''],  // only the chosen color's shades
          ['hms', 'Heatmap Shows', undefined, null, false, sub], ['hminv', 'Invert Intensity', cardOpt(w, 'invert', false), null, true],
          ['hmnl', 'Adapt the year to narrow cards', c.inst.narrowOn(), null, true]);
      }
      const zr = c.inst.zoom && c.inst.zoom.get();
      if (!own){
        if (DD.hasSizes && DD.hasSizes()) items.push('sep', ['rsz', 'Reset Size', undefined, 'reset']);
        if (zr && ZLINK[t]) items.push('sep', ['zspan', 'Set zoom as time span', undefined, 'calendar']);
        items.push('sep', ['add', 'Add Chart...', undefined, 'chartplus'], ['remove', 'Remove', undefined, 'trash']);
      }
      // opened from the header's "..." (its pills with no room, dd-core watchStat): those pills first, in this menu
      const hd = !dry && c.card.querySelector('.dd-head'), pre = hd && hd._ddPre;
      if (pre){ delete hd._ddPre; items.unshift.apply(items, pre.items.concat(['sep'])); }
      // no separator first, last or twice
      for (let i = items.length - 1; i >= 0; i--) if (items[i] === 'sep' && (i === 0 || i === items.length - 1 || items[i - 1] === 'sep')) items.splice(i, 1);
      if (dry) return items.length;
      menu({x: x, y: y, top: top}, items, function(k, on){
        if (pre && pre.pick(k, on)) return;
        if (animChoice(k)) return;
        if (xo && typeof k === 'string' && k.indexOf('xo:') === 0){
          const p = DD.optPick(xo, k, on);
          if (p && p[1] !== xo.cur[p[0]]){ xo.cur[p[0]] = p[1]; ownOpt(c.card); DD.setWidgetSetting(xo.section, p[0], p[1]); }
          return;
        }
        if (retP && DD.retentionPick(retP, k, on)) return;
        if (legendItems && DD.pieLegendPick(c.card, t, k, on)) return;
        if (k === 'fs') fullscreen(w);
        else if (k === 'rsz') DD.resetSizes();
        else if (k === 'settings') DD.call('widget_settings', {wtype: t, deck: state.deck || null});
        else if (k === 'help') helpText(t).then(function(h){ DD.helpPopup(h, x, y); });
        else if (typeof k === 'string' && k.indexOf('rt:') === 0){
          const key = k.slice(3); let hid = ((w.options && w.options.hidden_review_types) || []).filter(function(x){ return x !== key; });
          if (!on) hid.push(key);
          w.options = w.options || {}; w.options.hidden_review_types = hid;
          c.inst.setOptions({hidden_review_types: hid});
          DD.call('set_setting', {section: 'activity', key: 'hidden_review_types', value: hid}).catch(function(){});
        }
        else if (k === 'sync') setOpt(w, 'added', 'sync_zoom', on);
        else if (k === 'hmi'){ w.options.multi_hue = on; c.inst.setOptions({multi_hue: on}); DD.call('set_heatmap', {name: 'multi_hue', value: !!on}).catch(function(){}); }
        else if (typeof k === 'string' && k.indexOf('hmp:') === 0){
          const p = k.slice(4); w.options = w.options || {}; w.options.palette = p;
          const g = ((w.options.custom_palettes) || []).filter(function(x){ return 'custom:' + x.id === p; })[0];
          w.options.palette_colors = g ? g.colors : null;
          c.inst.setOptions({palette: p, palette_colors: w.options.palette_colors});
          DD.call('set_heatmap', {name: 'palette', value: p}).catch(function(){});
        }
        else if (k === 'hmcol') DD.call('pick_heatmap_color', {}).catch(function(){});
        else if (k === 'hmpnew') DD.call('edit_gradient', {new: true, color: (w.options && w.options.color) || null}).catch(function(){});
        else if (k === 'hmpedit') DD.call('edit_gradient', {new: false}).catch(function(){});
        else if (k === 'hmnl'){ w.options = w.options || {}; w.options.narrow_layout = !!on; c.inst.setOptions({narrow_layout: !!on}); DD.call('set_setting', {section: 'heatmap', key: 'narrow_layout', value: !!on}).catch(function(){}); }
        else if (k === 'hminv'){ w.options.invert = on; c.inst.setOptions({invert: on}); DD.call('set_heatmap', {name: 'invert', value: !!on}).catch(function(){}); }
        else if (typeof k === 'string' && k.indexOf('hm:') === 0){
          let set = String((w.options && w.options.metric) || 'reviews').split('+');
          const key = k.slice(3), tkeys = ['new', 'young', 'mature', 'relearn', 'cram'];
          if (key === 'alltypes') set = set.filter(function(x){ return tkeys.indexOf(x) < 0; });
          else if (set.indexOf(key) >= 0) set = set.filter(function(x){ return x !== key; }); else set.push(key);
          const order = ['reviews', 'time', 'correct', 'failed', 'retention', 'avg_time'].concat(tkeys);
          const m = order.filter(function(x){ return set.indexOf(x) >= 0; }).join('+') || 'reviews';
          w.options.metric = m; c.inst.setOptions({metric: m});
          (function(){ const ms = m.split('+'); document.querySelectorAll('.dd-mi[data-k^="hm:"]').forEach(function(el){ const kk = el.dataset.k.slice(3); el.classList.toggle('on', kk === 'alltypes' ? !ms.some(function(x){ return tkeys.indexOf(x) >= 0; }) : ms.indexOf(kk) >= 0); }); })();
          DD.call('set_heatmap', {name: 'metric', value: m}).catch(function(){});
          // reopen with the new checks: the menu stays open on a toggle
        }
        else if (k === 'dslider') DD.setWidgetSetting(t, 'day_slider', !!on);
        else if (k === 'pct') setOpt(w, t, 'show_percent', on);
        else if (k === 'trend') setOpt(w, t, 'show_trend', on);
        else if (k === 'cum') setOpt(w, t, 'show_cumulative', on);
        else if (k === 'avg') setOpt(w, t, 'show_average', on);
        else if (k === 'avga') setOpt(w, t, 'avg_on_active_days', on);
        else if (k === 'fit') setOpt(w, t, 'fit_to_data', on);
        else if (k === 'bars') setOpt(w, t, 'review_bars', on);
        else if (k === 'axis') setOpt(w, t, 'review_axis', on);
        else if (k === 'round') setOpt(w, t, 'rounded', on);
        else if (k === 'minrev'){
          (DD.askInt || function(o){ return DD.call('ask_int', o); })({title: 'Min Reviews', label: 'Hide points with fewer reviews than this (0 = show all):', value: (w.options && w.options.min_reviews) | 0, min: 0, max: 10000}).then(function(v){
            if (v == null) return; setOpt(w, t, 'min_reviews', v | 0);
          }).catch(function(){});
        }
        else if (k === 'adapt'){
          const ok = t === 'retention' ? 'binning' : 'adaptive_binning';
          w.options = w.options || {}; w.options[ok] = on; c.inst.setOptions({[ok]: on});
          DD.call('set_setting', {section: t, key: 'binning_override', value: on}).catch(function(){});
        }
        else if (k === 'bstats'){ grid.classList.toggle('dd-bottomstats', !!on); DD.call('set_show_stats', {value: !grid.classList.contains('dd-nostats'), bottom: !!on}).catch(function(){}); }
        else if (typeof k === 'string' && k.indexOf('sr:') === 0){
          const key = k.slice(3); const hs = ((w.options && w.options.hidden_series) || []).filter(function(x){ return x !== key; });
          if (!on) hs.push(key);
          w.options = w.options || {}; w.options.hidden_series = hs;
          c.inst.setOptions({hidden_series: hs});
          DD.call('set_setting', {section: t, key: 'hidden_series', value: hs.length ? hs : null}).catch(function(){});
        }
        else if (k === 'stats'){ grid.classList.toggle('dd-nostats', !on); DD.call('set_show_stats', {value: !!on}).catch(function(){}); }
        else if (k === 'zspan'){
          const z = c.inst.zoom, r = z.get(); if (!r) return;
          const first = z.label(r[0]), last = z.label(r[1] - 1);
          // its name asked in the page (the dates by default), then the span saved
          DD.call('span_name', {first: first, last: last}).then(function(name){
            if (!name) return null;
            return DD.ask ? DD.ask({title: 'Time Span', label: 'Name:', value: name}) : name;
          }).then(function(name){
            return name ? DD.call('span_from_zoom', {first: first, last: last, name: name}) : null;
          }).then(function(res){
            if (!res) return;
            boot.spans = res.spans; state.span = +res.code; setTitle(); refresh();
          });
        }
        else if (k === 'past') showPast(t, past);
        else if (k === 'pin') DD.call('pin_chart', {wtype: t, span: state.span}).then(function(ok){ toast(ok ? DD.t('{name} pinned to the main menu', {name: titleOf(t)}) : DD.t('This chart cannot be pinned')); });
        else if (k === 'add') DD.call('open_gallery');
        else if (k === 'remove'){
          const idx = state.widgets.indexOf(w);
          DD.call('remove_chart', {wtype: t}).then(function(i){
            DD.bridgeRebuild && DD.bridgeRebuild();
            toast('Widget removed', function(){ DD.call('restore_chart', {wtype: t, index: i}).then(function(){ DD.bridgeRebuild && DD.bridgeRebuild(); }); });
          });
        }
      });
    }
    DD.bridgeRebuild = function(){ DD.__push('rebuild'); };
    // View on a Past Day: the chart's Time Machine put right after it (the window's order), then brought into view
    // once it has come in (the rebuild below)
    let pastFocus = null;
    // fresh: just added (its intro shows it: no cue while it is in view)
    function focusCard(type, fresh){
      const id = Object.keys(state.cards).filter(function(i){ return state.cards[i].card.dataset.type === type; })[0];
      const card = id && state.cards[id].card;
      if (!card || card.style.display === 'none') return false;
      const smooth = !(DD.anim && DD.anim.on === false);
      const io = new IntersectionObserver(function(es){
        io.disconnect();
        const seen = es[0] && es[0].intersectionRatio > 0.9;
        if (seen && fresh) return;
        if (!seen) card.scrollIntoView({block: 'nearest', behavior: smooth ? 'smooth' : 'auto'});
        // (once it has come into view: one animation at a time)
        setTimeout(function(){ DD.flashCard(card); }, seen ? 0 : Math.round(450 * DD.speed()));
      }, {threshold: [0, 0.9]});
      io.observe(card);
      return true;
    }
    function showPast(from, past){
      if (focusCard(past)) return;
      pastFocus = past;
      DD.call('show_past', {wtype: past, after: from, order: state.widgets.map(function(x){ return String(x.type); })})
        .then(function(){ DD.bridgeRebuild(); }).catch(function(){ pastFocus = null; });
    }
    // a chart shown fullscreen is out of the grid (on <body>): its header's buttons, right click and help answer too
    function onCards(type, fn){
      document.addEventListener(type, function(e){
        const t = e.target;
        if (t && t.closest && (grid.contains(t) || t.closest('.dd-card.dd-fs'))) fn(e);
      });
    }
    // a double click on a text writes it again (Edit Text...)
    onCards('dblclick', function(e){
      const card = e.target.closest && e.target.closest('.dd-card.dd-text'); if (!card || e.target.closest('button, .dd-rsz')) return;
      const w = cardOf(card); if (w) editText(w);
    });
    // a text's sentence written again in the page's text editor (text_editor.js), saved by window.py _edit_text
    function editText(w){
      if (!DD.editText){ DD.call('edit_text', {wid: w.id}).catch(function(){}); return; }
      DD.call('text_get', {wid: w.id}).then(function(d){
        if (!d) return null;
        return DD.editText({template: d.template, title: 'Edit Text', ok: 'Save'}).then(function(t){
          if (t != null) return DD.call('text_set', {wid: w.id, template: t});
        });
      }).catch(function(e){ DD.log('edit text: ' + e); });
    }
    // a text edited (window.py _edit_text): its sentence read again for the deck and period shown
    DD.on('text_changed', function(p){
      const w = p && widgetOf(p.id), c = w && state.cards[w.id]; if (!c) return;
      DD.call('data', {widgets: [w], deck: state.deck, span: state.span, query: state.searchQuery || ''}).then(function(d){ if (d && d[w.id]) c.inst.update(d[w.id]); }).catch(function(){});
    });
    // a click (no drag) on a bar, a point, a slice or an hour shows its cards in Anki's browser (browser_click)
    let clickAt = null, lastTouchAt = 0;
    grid.addEventListener('pointerdown', function(e){ if (e.pointerType === 'touch') lastTouchAt = Date.now(); }, true);
    grid.addEventListener('mousedown', function(e){ clickAt = e.button === 0 ? [e.clientX, e.clientY] : null; }, true);
    grid.addEventListener('mouseup', function(e){
      const p = clickAt; clickAt = null;
      if (!p || e.button !== 0 || Math.abs(e.clientX - p[0]) + Math.abs(e.clientY - p[1]) > 5) return;
      // On touch screens, tapping a bar inspects its tooltip instead of opening the Card Browser.
      if ((DD.isTouch && DD.isTouch()) || Date.now() - lastTouchAt < 800) return;
      const plot = e.target.closest && e.target.closest('.dd-plot');
      if (!plot || !plot._ddBrowse || plot.classList.contains('dd-dots-on') || e.target.closest('.dd-zbar, .dd-zctl')) return;
      let spec = null; try { spec = plot._ddBrowse(); } catch (err) { spec = null; }
      if (!spec) return;
      DD.call('browse', Object.assign({deck: state.deck, span: state.span}, spec)).catch(function(){});
    });
    // touch: hold a chart to lift it, move to drag it (the pointer drag above, fed by the lift), or let go for its menu
    let liftRsz = null;
    function touchHandle(card, x, y){
      const hs = Array.from(card.querySelectorAll(':scope > .dd-rsz')).filter(function(h){ return h.offsetParent !== null; }); if (!hs.length) return null;
      const dirs = hs.map(function(h){ return h.dataset.mode; }).join(''), m = DD.touchEdge(card, x, y, dirs);
      return m ? (hs.filter(function(h){ return h.dataset.mode === m; })[0] || hs.filter(function(h){ return m.indexOf(h.dataset.mode) >= 0; })[0]) : null;
    }
    if (DD.touchLift){
      DD.touchLift(grid, {
        pick: function(t){ const c = t.closest && t.closest('.dd-card'); return c && c.parentNode === grid && !c.classList.contains('dd-fs') ? c : null; },
        ignore: 'button, input, select, .dd-zbar, .dd-tm',
        // held near its right / bottom edge, where the mouse's resize handles are (none shown on a phone): resized
        edge: function(card, x, y){ return touchHandle(card, x, y) ? 'edge' : null; },
        drag: function(phase, x, y, card, target){
          if (phase === 'start'){
            liftRsz = touchHandle(card, x, y);
            DD.touchEvent('pointer', 'pointerdown', x, y, liftRsz || card);  // on the card: not a zoom on its plot
          } else DD.touchEvent('pointer', phase === 'move' ? 'pointermove' : 'pointerup', x, y, liftRsz);
          if (phase === 'end' || phase === 'cancel') liftRsz = null;
        },
        menu: DD.openMenuAt,
      });
    }
    onCards('contextmenu', function(e){
      const card = e.target.closest && e.target.closest('.dd-card'); if (!card) return;
      const id = Object.keys(state.cards).filter(function(k){ return state.cards[k].card === card; })[0];
      const w = state.widgets.filter(function(x){ return String(x.id) === id; })[0];
      if (!w) return;
      e.preventDefault(); cardMenu(w, e.clientX, e.clientY);
    });
    const helpCache = Object.assign({}, boot.chart_help || {});
    function helpText(t){ return helpCache[t] !== undefined ? Promise.resolve(helpCache[t]) : DD.call('chart_help', {wtype: t}).then(function(h){ helpCache[t] = h || ''; return helpCache[t]; }); }
    let helpTip = null;
    onCards('mouseover', function(e){
      const h = e.target.closest && e.target.closest('.dd-help'); if (!h || h === helpTip) return;
      helpTip = h;
      helpText(h.getAttribute('data-t')).then(function(txt){
        if (helpTip !== h || !txt) return;
        const old = document.querySelector('.dd-helptip'); if (old) old.remove();
        const t = document.createElement('div'); t.className = 'dd-helptip'; t.textContent = txt; document.body.appendChild(t);
        const r = h.getBoundingClientRect();
        t.style.left = Math.min(r.right + 6, window.innerWidth - t.offsetWidth - 8) + 'px';
        t.style.top = Math.min(r.bottom + 6, window.innerHeight - t.offsetHeight - 8) + 'px';
      });
    });
    onCards('mouseout', function(e){
      const h = e.target.closest && e.target.closest('.dd-help'); if (!h) return;
      if (e.relatedTarget && h.contains(e.relatedTarget)) return;
      helpTip = null; const old = document.querySelector('.dd-helptip'); if (old) old.remove();
    });
    // a chart's own options in its header: an icon after its pills (Include Suspended Cards' one, merged), the
    // entries of its right click that change this chart alone; none when it has none
    function ownOpt(card){
      if (!ownReady) return;
      const head = card && card.querySelector('.dd-head'), w = head && cardOf(head);
      if (!w) return;
      if (w.type === 'heatmap') return;  // its header is its view's controls: its options stay in the right click
      let wrap = head.querySelector('.dd-ownopt');
      if (!cardMenu(w, 0, 0, 0, true, true)){ if (wrap) wrap.remove(); return; }
      if (!wrap){
        wrap = document.createElement('span'); wrap.className = 'dd-pills dd-ownopt';
        wrap.innerHTML = '<button class="dd-pill dd-pill-opt dd-pill-ico" title="This chart\'s options"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M2 14h4M10 8h4M18 16h4"/></svg></button>';
        head.appendChild(wrap);
        wrap.firstChild.addEventListener('click', function(e){
          e.stopPropagation();
          const ww = cardOf(head), r = e.currentTarget.getBoundingClientRect();
          if (ww) cardMenu(ww, r.left, r.bottom + 2, r.top, true);
        });
      }
      // lit while an option of its icon is off its default (as Include Suspended's)
      const xo = head._ddOpt;
      wrap.firstChild.classList.toggle('on', !!(xo && xo.items.some(function(it){ return xo.cur[it[0]] !== it[3]; })));
    }
    Object.keys(state.cards).forEach(function(k){ ownOpt(state.cards[k].card); });  // the charts mounted before
    function cardOf(el){ const card = el.closest('.dd-card'); const id = Object.keys(state.cards).filter(function(k){ return state.cards[k].card === card; })[0]; return id === undefined ? null : widgetOf(id); }
    onCards('click', function(e){
      const more = e.target.closest && e.target.closest('.dd-more');
      if (more){ const w = cardOf(more); if (w){ const r = more.getBoundingClientRect(); cardMenu(w, r.left, r.bottom + 4, r.top); } return; }
      const pb = e.target.closest && e.target.closest('.dd-pinb');
      if (pb){ const w = cardOf(pb); if (w) DD.call('pin_chart', {wtype: w.type, span: state.span}).then(function(ok){ toast(ok ? DD.t('{name} pinned to the main menu', {name: titleOf(w.type)}) : DD.t('This chart cannot be pinned')); }); return; }
      // the chevron or the chart's name folds its whole row
      const ch = e.target.closest && e.target.closest('.dd-chev, .dd-title'); if (!ch || !lay.collapsible) return;
      const card = ch.closest('.dd-card'); if (!card || card.parentNode !== grid) return;
      const fold = !card.classList.contains('dd-collapsed');
      grid.querySelectorAll('.dd-card').forEach(function(c){ if (c._row === card._row) c.classList.toggle('dd-collapsed', fold); });
      layoutGrid();
    });
    DD.on('theme', function(){ Object.keys(state.cards).forEach(function(id){ state.cards[id].inst.setTheme(); }); if (scInst) scInst.setTheme(DD.theme); if (tblInst && tblInst.setTheme) tblInst.setTheme(DD.theme); });
    // the gradient window (heatmap_gradient): its changes shown at once
    DD.on('heatmap_palette', function(p){
      if (!p) return;
      state.widgets.forEach(function(w){
        if (w.type !== 'heatmap' || !state.cards[w.id]) return;
        w.options = Object.assign(w.options || {}, p);
        state.cards[w.id].inst.setOptions(p);
      });
    });
    DD.on('rebuild', function(){
      DD.call('widgets_now', {deck: state.deck, span: state.span}).then(function(r){
        // only what changed (the gallery's live preview: a chart added or taken off at each click): the charts kept stay
        // as they are, a new one opens with its intro, those that move glide (everything was built again at once)
        const before = new Map();
        grid.querySelectorAll('.dd-card').forEach(function(c){ if (c.style.display !== 'none') before.set(c, c.getBoundingClientRect()); });
        const keep = {}; r.widgets.forEach(function(w){ keep[w.id] = w.type; });
        Object.keys(state.cards).forEach(function(id){
          const c = state.cards[id];
          if (keep[id] === c.card.dataset.type) return;
          try { c.inst.destroy(); } catch (e) {}
          c.card.remove(); delete state.cards[id];
        });
        const fresh = [];
        r.widgets.forEach(function(w){
          if (!state.cards[w.id]){ addCard(w, r.data[w.id], true); fresh.push(state.cards[w.id] && state.cards[w.id].card); }
          const c = state.cards[w.id]; if (!c) return;
          grid.appendChild(c.card);  // the order of the list
          c.card.style.display = (r.data[w.id] && r.data[w.id]._empty) ? 'none' : '';
        });
        state.widgets = r.widgets;
        catalog = null;  // (Find chart's list: what is shown changed)
        if (chartFilterQ.trim()) applyChartFilter(chartFilterQ);
        // the stat cards first: a line of cards that comes or goes changes where the charts start, and the charts'
        // glide must end where they will really be
        if (scInst && r.stats) scInst.update(r.stats);
        layoutGrid();
        if (document.body.animate){
          before.forEach(function(a, c){
            if (!c.isConnected || c.style.display === 'none') return;
            const b = c.getBoundingClientRect(), dx = a.left - b.left, dy = a.top - b.top, sx = b.width ? a.width / b.width : 1, sy = b.height ? a.height / b.height : 1;
            if (Math.abs(dx) < 0.5 && Math.abs(dy) < 0.5 && Math.abs(sx - 1) < 0.005 && Math.abs(sy - 1) < 0.005) return;
            c.animate([{transformOrigin: '0 0', transform: 'translate(' + dx + 'px,' + dy + 'px) scale(' + sx + ',' + sy + ')'}, {transformOrigin: '0 0', transform: 'none'}], {duration: 420, easing: 'cubic-bezier(0.22, 1, 0.36, 1)'});
          });
          fresh.forEach(function(c){ if (c && c.style.display !== 'none') c.animate([{opacity: 0, transform: 'scale(0.96)'}, {opacity: 1, transform: 'none'}], {duration: 360, easing: 'cubic-bezier(0.22, 1, 0.36, 1)'}); });
        }
        if (pastFocus){ const p = pastFocus; pastFocus = null; focusCard(p, true); }
      }).catch(function(e){ DD.log('rebuild: ' + (e && e.message || e)); });
    });
    DD.on('table_reload', function(){
      if (tblInst) tblInst.reload();
    });
    DD.on('refresh', function(){
      refresh(); if (tblInst) tblInst.reload();
      DD.call('drawer', {}).then(function(d){ if (d) setTableOn(d.show !== false); }).catch(function(){});
      // the charts' options and the grid's layout as Settings has them now (Chart Style, Collapsible, Fill Height...)
      DD.call('widget_opts', {}).then(function(r){
        if (!r) return;
        Object.keys(r.options || {}).forEach(function(id){
          const c = state.cards[id], o = r.options[id]; if (!c || !o) return;
          const w = widgetOf(id), js = JSON.stringify(o);
          if (w && JSON.stringify(w.options || {}) === js) return;
          if (w) w.options = o;
          try { c.inst.setOptions(o); } catch (e) {}
        });
        if (r.layout) DD.setLayoutOpts(r.layout);
        if (r.anim) DD.setAnim(r.anim);  // Settings > General > Animations saved
      }).catch(function(){});
    });
    function wire(sel, cmd, args){ root.querySelectorAll(sel).forEach(function(b){ b.addEventListener('click', function(){ DD.call(cmd, args || {}).catch(function(){}); }); }); }
    wire('.dd-settings', 'open_settings');
    wire('.dd-charts', 'open_gallery');
    // the two animation choices, one setting each for the whole add-on (also in Settings > General > Animations):
    // the charts' axis numbers (Chart_Axis_Anim) and the stat cards' numbers (Stat_Num_Anim)
    function axisAnimItem(){ return ['axanim', 'Axis Animation', undefined, null, false, [['ax:count', 'Numbers count', !DD.axisSlide()], ['ax:slide', 'Ticks slide', DD.axisSlide()]]]; }
    // label: on a stat card's own menu "Number Animation"; in Chart Options (no stat card in sight) "Stat Card Numbers"
    function numAnimItem(label){ const roll = !!(DD.theme && DD.theme.num_anim === 'roll'); return ['numanim', label || 'Number Animation', undefined, null, false, [['na:count', 'Numbers count', !roll], ['na:roll', 'Digits roll', roll]]]; }
    // a choice of these menus (true: it was one)
    function animChoice(k){
      if (k === 'ax:count' || k === 'ax:slide'){
        const v = k.slice(3); if (DD.theme) DD.theme.axis_anim = v;
        DD.call('global_option', {name: 'axis_anim', value: v}).catch(function(){});
        // every chart drawn again at once with its axis' new way (no transition)
        DD._noAnim = true;
        try { Object.keys(state.cards).forEach(function(id){ const i = state.cards[id].inst; if (i && i.setOptions) try { i.setOptions({}); } catch (e) {} }); } finally { DD._noAnim = false; }
        return true;
      }
      if (k === 'na:count' || k === 'na:roll'){
        const v = k.slice(3); if (DD.theme) DD.theme.num_anim = v;
        DD.call('global_option', {name: 'num_anim', value: v}).catch(function(){});
        return true;
      }
      return false;
    }
    // the header gear: "Chart Options" (global choices of the normal window)
    const CUMS = ['activity', 'added', 'hourly', 'future_due', 'review_intervals', 'stability'];
    function liveAll(types, o){ state.widgets.forEach(function(w){ if (types.indexOf(w.type) >= 0 && state.cards[w.id]){ w.options = Object.assign(w.options || {}, o); state.cards[w.id].inst.setOptions(o); } }); }
    const gearBtn = root.querySelector('.dd-set');
    if (gearBtn) gearBtn.addEventListener('click', function(e){
      e.stopPropagation();
      // opened above the button like the other menus of the bar
      menu(gearBtn, [
        ['avg', 'Show Average Line', G.show_average, null, true], ['avga', 'Average on Active Days', G.avg_on_active_days, null, true], 'sep',
        ['cum', 'Show Right Axis (Global)', G.show_cumulative, null, true],
        ['bstats', 'Show Bottom Stats (All Charts)', grid.classList.contains('dd-bottomstats'), null, true],
        ['stats', 'Show Stats (All Charts)', !grid.classList.contains('dd-nostats'), null, true], 'sep',
        ['bin', 'Adaptive Binning (Global)', G.binning, null, true], ['sync', 'Sync Zoom Across Charts', G.sync_zoom, null, true], 'sep',
        // how the axis numbers move when a scale changes, how the stat cards' numbers change
        axisAnimItem(), numAnimItem('Stat Card Numbers'), 'sep',
        ['layout', 'Reset Chart Layout']
      ], function(k, on){
        if (k === 'avg'){ G.show_average = on; DD.call('global_option', {name: 'show_average', value: on}); liveAll(['activity', 'added', 'retention'], {show_average: on}); }
        else if (k === 'avga'){ G.avg_on_active_days = on; DD.call('global_option', {name: 'avg_on_active_days', value: on}); liveAll(['activity', 'added', 'retention'], {avg_on_active_days: on}); }
        else if (k === 'cum'){ G.show_cumulative = on; DD.call('global_option', {name: 'show_cumulative', value: on}); liveAll(CUMS, {show_cumulative: on}); }
        else if (k === 'bstats'){ grid.classList.toggle('dd-bottomstats', !!on); DD.call('set_show_stats', {value: !grid.classList.contains('dd-nostats'), bottom: !!on}).catch(function(){}); layoutGrid(); }
        else if (k === 'stats'){ grid.classList.toggle('dd-nostats', !on); DD.call('set_show_stats', {value: !!on}).catch(function(){}); layoutGrid(); }
        else if (k === 'bin'){  // toggle_global_binning: per-chart choices cleared, every chart redrawn at once (no transition)
          G.binning = on; DD.call('global_option', {name: 'binning', value: on});
          DD._noAnim = true;
          try { liveAll(['activity', 'added'].concat(BIN), {adaptive_binning: on}); liveAll(['retention'], {binning: on}); }
          finally { DD._noAnim = false; }
        }
        else if (k === 'sync'){  // toggle_sync: off = the stats of the whole period; on = the others follow a chart already zoomed
          G.sync_zoom = on; DD.call('global_option', {name: 'sync_zoom', value: on}); updateRZoom();
          if (!on){ refreshFollowers(++zseq); return; }
          const src = state.widgets.filter(function(w){ const c = state.cards[w.id]; return ZLINK[w.type] && c && c.inst.zoom && c.inst.zoom.get && c.inst.zoom.get(); })[0];
          if (src) onZoom(src.id, state.cards[src.id].inst.zoom.get());
        }
        else if (k === 'layout'){ DD.call('global_option', {name: 'reset_layout'}); }
        else animChoice(k);
      });
    });
    const links = root.querySelector('.dd-links');
    if (links) links.addEventListener('click', function(e){
      menu(e.currentTarget, [['tour', 'Quick Tour', null, 'help'], 'sep', ['support', 'Support the Add-on', null, 'heart'], ['rate', 'Rate the Add-on', null, 'thumb'], ['github', 'GitHub', null, 'github']],
        function(n){
          if (n === 'tour'){ if (DD.startTour) DD.startTour(); return; }
          DD.call('open_link', {name: n}).catch(function(){});
        });
    });
    if (!boot.tour_seen && !boot.export && !DD.isTouch() && DD.startTour){
      setTimeout(function(){ if (DD.startTour) DD.startTour({auto: true}); }, 750);
    }
    const trendsBtn = root.querySelector('.dd-trends');
    if (trendsBtn) trendsBtn.classList.toggle('on', !!boot.trends);
    if (trendsBtn) trendsBtn.addEventListener('click', function(){
      const on = !trendsBtn.classList.contains('on');
      trendsBtn.classList.toggle('on', on);
      DD.call('set_trends', {on: on}).then(function(){ if (tblInst) tblInst.reload(); }).catch(function(){});
    });
    // ---- image export (logic/export/visual.py): the stat cards, every chart (the whole height, not only what is on
    // screen) and every row of the table, each taken by the window in pieces while the page scrolls itself, then laid
    // out under the export header by Python ----
    // ---- the hidden page an export draws at 2x (window.py _export_offscreen): the window's view and table ----
    DD.exportState = function(){
      const t = tblInst ? tblInst.state : null;
      return {w: window.innerWidth, h: window.innerHeight, view: state.view || 'time',
        table: t ? {mode: t.mode, deckKey: t.deckKey, tab: t.tab, sort: t.sort, expanded: Array.from(t.expanded || []), filter: t.filter || ''} : null};
    };
    let expTable = !boot.export, expNudged = !boot.export;
    if (boot.export && boot.export_state){
      const es = boot.export_state, t = es.table;
      DD.exportWrapW = +es.w || 0;  // the window's width: the stat cards break into lines as there (stats.js)
      if (es.view && es.view !== (state.view || 'time')) setView(es.view, false);
      if (tblInst && t){
        const s = tblInst.state;
        s.mode = t.mode; s.deckKey = t.deckKey; s.tab = t.tab; s.sort = t.sort; s.expanded = new Set(t.expanded || []); s.expandedInit = true; s.gen = (s.gen || 0) + 1;
        Promise.resolve(tblInst.reload()).catch(function(){}).then(function(){ if (t.filter) tblInst.setFilter(t.filter); expTable = true; });
      } else expTable = true;
    } else if (boot.export) expTable = true;
    DD.exportNudge = function(){
      // the charts' canvases drawn again for the zoomed page's pixel ratio (their size did not change: no resize came)
      grid.style.width = 'calc(100% - 1px)';
      requestAnimationFrame(function(){ grid.style.width = ''; window.dispatchEvent(new Event('resize')); setTimeout(function(){ expNudged = true; }, 400); });
    };
    DD.exportReady = function(){ return expTable && expNudged && !!DD._go && !(DD.frame.busy && DD.frame.busy()); };
    // how much wider than the page the table is (many columns: it scrolls sideways), in page px: the hidden page is
    // made that much wider before the export, so every column is in the picture, not cut at the window's edge
    DD.exportOverflow = function(kind){
      if (kind !== 'table' && kind !== 'full') return 0;
      const tsc = root.querySelector('.dd-tbl-scroll'); if (!tsc) return 0;
      const was = drawer.open;
      if (!was) openTable(true, {instant: true, remember: false});
      const over = Math.max(0, tsc.scrollWidth - tsc.clientWidth);
      if (!was) openTable(false, {instant: true, remember: false});
      return over;
    };
    DD.exportBegin = function(kind, bg, stats){
      const st = {kind: kind, shots: [], wasOpen: drawer.open, wrapTop: wrapEl.scrollTop, t0: performance.now()};
      // the export's own flat background under everything (the window's shaded backdrop showed around the pieces)
      if (bg) document.documentElement.style.setProperty('--dd-export-bg', bg);
      const tsc = root.querySelector('.dd-tbl-scroll'); st.tblTop = tsc ? tsc.scrollTop : 0;
      document.documentElement.classList.add('dd-exporting');
      layoutGrid();  // no scroll bar room now (see dd.css html.dd-exporting)
      document.querySelectorAll('.dd-menu,.dd-tip').forEach(function(m){ if (m.classList.contains('dd-menu')) m.remove(); else m.style.display = 'none'; });
      const closeT = function(){ if (drawer.open) openTable(false, {instant: true, remember: false}); };
      const openT = function(){ if (!drawer.open) openTable(true, {instant: true, remember: false}); };
      const sc = root.querySelector('.dd-sc-host');
      if (sc && sc.offsetHeight > 2 && stats !== false) st.shots.push({sec: 'summary', prep: closeT, rect: function(){ const r = sc.getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; }});
      if (kind === 'deep_dive' || kind === 'full'){
        // the whole height of the charts, down to the last card shown
        let bottom = 0;
        grid.querySelectorAll('.dd-card').forEach(function(c){ if (c.style.display !== 'none' && c.offsetHeight > 1) bottom = Math.max(bottom, c.offsetTop + c.offsetHeight); });
        const total = Math.max(20, bottom + 8), vh = wrapEl.clientHeight;
        for (let y = 0; y < total; y += vh){
          (function(y0){
            st.shots.push({sec: 'charts', prep: function(){ closeT(); wrapEl.scrollTop = y0; }, rect: function(){
              const r = wrapEl.getBoundingClientRect(), off = y0 - wrapEl.scrollTop;  // the last piece: the scroll stops early
              return [r.left, r.top + off, r.width, Math.min(vh - off, total - y0)];
            }});
          })(y);
        }
      }
      if ((kind === 'table' || kind === 'full') && tsc){
        // every row: the header once, then the rows under the sticky header piece by piece
        openT();
        const tbl = tsc.querySelector('table'), head = tbl && tbl.querySelector('thead');
        const total = tbl ? tbl.offsetHeight : tsc.scrollHeight, hh = head ? head.offsetHeight : 0, vh = tsc.clientHeight;
        let c = 0, first = true;
        while (c < total && vh > hh + 4){
          (function(c0, isFirst){
            st.shots.push({sec: 'table', prep: function(){ openT(); tsc.scrollTop = isFirst ? 0 : c0 - hh; }, rect: function(){
              const r = tsc.getBoundingClientRect(), w = Math.min(r.width, tbl ? tbl.offsetWidth : r.width);
              const viewY = isFirst ? 0 : c0 - tsc.scrollTop;  // where content c0 sits in the view
              return [r.left, r.top + viewY, w, Math.min(vh - viewY, total - c0)];
            }});
          })(c, first);
          c += first ? vh : vh - hh; first = false;
        }
      }
      DD._exp = st;
      return st.shots.length;
    };
    DD.exportShot = function(i){
      const s = DD._exp && DD._exp.shots[i]; if (!s) return null;
      s.ready = false; s.prep(); DD.frame.kick();
      // painted: two frames in a row with nothing moving (the scroll, the charts that came into view, the rows)
      // (the first piece also waits for the export's background to be on screen: the stat cards came out on the
      // window's darker background, a dark band behind them in the picture, the charts below on the export's)
      let calm = 0;
      const first = i === 0, t0 = DD._exp.t0 || 0;
      const tick = function(){ if (DD.frame.busy && DD.frame.busy()) calm = 0; else calm++; if (calm >= (first ? 4 : 2) && (!first || performance.now() - t0 > 250)) s.ready = true; else requestAnimationFrame(tick); };
      requestAnimationFrame(tick);
      return null;
    };
    DD.exportShotReady = function(i){ const s = DD._exp && DD._exp.shots[i]; return !s || !!s.ready; };
    DD.exportRect = function(i){ const s = DD._exp && DD._exp.shots[i]; if (!s) return null; const r = s.rect(); return {sec: s.sec, x: r[0], y: r[1], w: r[2], h: Math.max(0, r[3])}; };
    DD.exportEnd = function(){
      const st = DD._exp; DD._exp = null;
      document.documentElement.classList.remove('dd-exporting');
      layoutGrid();  // the scroll bar's room back
      if (!st) return true;
      if (st.wasOpen) openTable(true, {instant: true, remember: false}); else if (drawer.open) openTable(false, {instant: true, remember: false});
      wrapEl.scrollTop = st.wrapTop;
      const tsc = root.querySelector('.dd-tbl-scroll'); if (tsc) tsc.scrollTop = st.tblTop;
      return true;
    };
    // the rating banner: a pill centred just above the toolbar, floating over the charts
    // (web: the table is a panel that slides up over them: the banner sat behind it). It stays above the bar or above
    // the open table, and follows the table as it slides or is resized (its style changes: a few frames of following)
    function placeRate(){
      const r = root.querySelector('.dd-rate'); if (!r) return;
      let top = bottomEl.getBoundingClientRect().top;
      if (tblHost.style.display !== 'none' && getComputedStyle(tblHost).display !== 'none'){ const t = tblHost.getBoundingClientRect().top; if (t < top) top = t; }
      r.style.bottom = Math.round(window.innerHeight - top + 10) + 'px';
    }
    let rateRaf = 0, rateUntil = 0;
    function followRate(){
      if (!root.querySelector('.dd-rate')) return;
      rateUntil = performance.now() + ANIM_MS + 80;
      if (!rateRaf) rateRaf = requestAnimationFrame(function step(){
        placeRate();
        rateRaf = performance.now() < rateUntil && root.querySelector('.dd-rate') ? requestAnimationFrame(step) : 0;
      });
    }
    new MutationObserver(followRate).observe(tblHost, {attributes: true, attributeFilter: ['style']});
    window.addEventListener('resize', followRate);
    DD.showRate = function(opts){
      opts = opts || {};
      const old = root.querySelector('.dd-rate'); if (old) old.remove();
      const row = document.createElement('div'); row.className = 'dd-rate';
      row.innerHTML = '<div class="dd-rate-pill"><span class="dd-rate-ic">' + icon('thumb', 18) + '</span><span class="dd-rate-t">Enjoying Deep Dive Stats? A rating on AnkiWeb helps others find it :)</span>' +
        '<button class="dd-rate-b on" data-a="rate">' + icon('thumb', 16) + '<span>Rate</span></button><button class="dd-rate-b" data-a="later">Later</button><button class="dd-rate-b" data-a="never">Don\'t ask again</button></div>';
      root.appendChild(row); placeRate();
      if (row.animate && DD.anim.on && DD.anim.appear) row.firstChild.animate([{opacity: 0, transform: 'translateY(8px)'}, {opacity: 1, transform: 'none'}], {duration: 260 * DD.speed(), easing: 'ease-out'});
      let counted = false;
      const tm = setTimeout(function(){ if (row.isConnected && row.offsetParent !== null){ DD.call('rate_action', {action: 'seen', preview: !!opts.preview, counted: counted}).catch(function(){}); counted = true; } }, opts.seen_ms || 12000);
      row.querySelectorAll('.dd-rate-b').forEach(function(b){
        b.addEventListener('click', function(){
          clearTimeout(tm);
          DD.call('rate_action', {action: b.dataset.a, preview: !!opts.preview, counted: counted}).catch(function(){});
          row.remove();
        });
      });
    };
    // the window while an image export is drawn in a hidden view (window.py _export_progress): a notice with its
    // progress over the whole window, which takes no click meanwhile (another deck or period then changed the export)
    DD.exportProgress = function(done, total){
      let ov = document.querySelector('.dd-exp-ov');
      if (done === null || done === undefined){ if (ov){ ov.classList.remove('on'); setTimeout(function(){ if (!ov.classList.contains('on')) ov.remove(); }, 200); } return; }
      if (!ov){
        ov = document.createElement('div'); ov.className = 'dd-exp-ov';
        ov.innerHTML = '<div class="dd-exp-box"><div class="dd-exp-t"></div><div class="dd-exp-bar"><i></i></div></div>';
        document.body.appendChild(ov); void ov.offsetWidth;
      }
      ov.classList.add('on');
      ov.querySelector('.dd-exp-t').textContent = total ? DD.t('Exporting... {done}/{total}', {done: done + 1, total: total}) : DD.t('Preparing the export...');
      ov.querySelector('.dd-exp-bar i').style.width = (total ? Math.round((done + 1) / total * 100) : 4) + '%';
    };
    let exportStats = boot.export_stats !== false;  // the Export menu's "Include Stat Cards"
    const expBtn = root.querySelector('.dd-export');
    if (expBtn) expBtn.addEventListener('click', function(e){
      e.stopPropagation();
      const items = tableOn
        ? [['deep_dive', 'Export Deep Dive', null, 'bars'], ['table', 'Export Table + Dashboard', null, 'grid'], ['full', 'Export Full View', null, 'image'], 'sep', ['stats', 'Include Stat Cards', exportStats, null, true], 'sep', ['csv', 'Export Data (CSV)', null, 'filetext']]
        : [['deep_dive', 'Export Deep Dive', null, 'bars'], 'sep', ['stats', 'Include Stat Cards', exportStats, null, true]];  // without the table: nothing of it to export
      menu(expBtn, items.map(function(x){ if (x !== 'sep' && x[2] === null) x[2] = undefined; return x; }), function(k, on){
        if (k === 'stats'){ exportStats = !!on; DD.call('set_export_stats', {on: exportStats}).catch(function(){}); return; }
        if (k === 'full' || k === 'deep_dive' || k === 'table') DD.call('export_image', {kind: k, title: state.deckTitle, period: periodLabel()}).catch(function(){});
        else { const c = tblInst && tblInst.csvData(); if (c) DD.call('export_csv', c).catch(function(){}); }
      });
    });
    const search = root.querySelector('.dd-search');
    if (search){
      search.addEventListener('input', function(){
        if (tableOn && (tableOnly || drawer.open)){
          tableFilterQ = search.value;
          if (tblInst) tblInst.setFilter(search.value);
        } else {
          applyChartFilter(search.value);
        }
      });
      search.addEventListener('keydown', function(ev){
        if (ev.key === 'Escape'){
          if (search.value){
            search.value = '';
            search.dispatchEvent(new Event('input'));
          }
          search.blur();
        }
      });
      document.addEventListener('keydown', function(ev){
        if ((ev.ctrlKey || ev.metaKey) && !ev.altKey && (ev.key === 'f' || ev.key === 'F')){
          ev.preventDefault();
          search.focus();
          search.select();
        }
      });
      syncSearchMode();
    }
    const visBtn = root.querySelector('.dd-visuals');
    if (visBtn) visBtn.addEventListener('click', function(e){
      e.stopPropagation();
      const v = (tblInst && tblInst.state.data && tblInst.state.data.visuals) || {};
      const items = [['buttons', 'Answer buttons'], ['all', 'Retention'], ['young', 'Retention (young)'], ['mature', 'Retention (mature)']];
      menu(visBtn, items.map(function(it){ return [it[0], it[1], !!v[it[0]], null, true]; }), function(k, on){
        v[k] = on;
        DD.call('set_visual', {which: k, on: !!on}).then(function(){ if (tblInst) tblInst.reload(); }).catch(function(){});
      });
    });
    ownReady = true;
    Object.keys(state.cards).forEach(function(id){ ownOpt(state.cards[id].card); });
    bm('grid+rest');
    (function(){
      const parts = bootT.slice(1).map(function(m, i){ return m[1] + ' ' + Math.round(m[0] - bootT[i][0]); });
      const ms = DD._bootMounts || [], sum = ms.reduce(function(a, m){ return a + m[0]; }, 0);
      const top = ms.slice().sort(function(a, b){ return b[0] - a[0]; }).slice(0, 6).map(function(m){ return m[1] + (m[2] ? '' : '(empty)') + ' ' + Math.round(m[0]) + (m[3] != null ? ' (' + m[3] + ' rows)' : ''); });
      DD.trace('PERF boot ' + Math.round(bootT[bootT.length - 1][0] - bootT[0][0]) + 'ms (scripts loaded at ' + Math.round(bootT[0][0]) + 'ms): ' + parts.join(', ')
        + ' | ' + ms.length + ' charts mounted ' + Math.round(sum) + 'ms, top [' + top.join(', ') + ']');
      DD._bootMounts = null;
      // what the browser did after: the first style and layout of the whole page
      const t1 = performance.now(); requestAnimationFrame(function(){ DD.trace('PERF boot: first frame ' + Math.round(performance.now() - t1) + 'ms after the start'); });
    })();
  };
})();
