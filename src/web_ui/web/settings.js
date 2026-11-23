// Settings (settings.py): General, Time Span, Colors and Decks in one page. Python keeps the values: each change is a
// call that edits the config (the open windows preview it live) and answers with the new state of its part, which
// the page shows again. Save writes the config, Cancel puts it back as it was.
// The page's text is translated here (DD.t), the whole page being marked data-nt.
(function(){
  'use strict';
  const S = {tab: 'general', g: null, spans: null, colors: null, backdrop: null, K: {}, dev: false, span: 0,
             themeFilter: 'all', themeFind: '', pthemeFind: '', dataPinned: false, form: null, decks: null,
             dragging: false};
  let root = null, mainEl = null, navEl = null, decksEl = null;

  // ---- helpers ----
  function el(tag, cls, text){
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  const T = function(s, vars){ return DD.t(s, vars); };
  // small line icons (12 px) for the icon buttons
  const ICONS = {reset: 'M2.6 6.4A3.6 3.6 0 1 0 3.9 3.3M3.9 1.2v2.3h2.3', drop: 'M6 1.6C6 1.6 2.9 5 2.9 7.2a3.1 3.1 0 0 0 6.2 0C9.1 5 6 1.6 6 1.6z', info: 'M6 1.25a4.75 4.75 0 1 0 0 9.5 4.75 4.75 0 0 0 0-9.5zM6 5.4v3.1M6 3.7v.05', up: 'M6 9.5V2.5M2.5 6L6 2.5 9.5 6', down: 'M6 2.5v7M2.5 6L6 9.5 9.5 6', x: 'M3 3l6 6M9 3L3 9', minus: 'M2.5 6h7', plus: 'M2.5 6h7M6 2.5v7'};
  function icon(name){
    const ns = 'http://www.w3.org/2000/svg', svg = document.createElementNS(ns, 'svg'), path = document.createElementNS(ns, 'path');
    svg.setAttribute('width', '12'); svg.setAttribute('height', '12'); svg.setAttribute('viewBox', '0 0 12 12');
    path.setAttribute('d', ICONS[name]); path.setAttribute('fill', 'none'); path.setAttribute('stroke', 'currentColor');
    path.setAttribute('stroke-width', '1.5'); path.setAttribute('stroke-linecap', 'round'); path.setAttribute('stroke-linejoin', 'round');
    svg.appendChild(path);
    return svg;
  }
  function iconBtn(cls, name, title){
    const b = el('button', cls);
    b.appendChild(icon(name));
    if (title) b.title = title;
    return b;
  }
  DD.settingsIcon = icon;
  // a label ("Decimal Precision:") without its colon
  const L = function(s){ return DD.t(s).replace(/\s*[:：]\s*$/, ''); };
  function btn(text, cls, onclick, title){
    const b = el('button', 'dds-btn' + (cls ? ' ' + cls : ''), text);
    if (onclick) b.onclick = onclick;
    if (title) b.title = title;
    return b;
  }
  function fail(e){
    DD.log('settings: ' + e);
    toast(String(e && e.message || e));
  }
  let toastTimer = 0;
  function toast(text){
    let t = document.querySelector('.dds-toast');
    if (!t){ t = el('div', 'dds-toast'); document.body.appendChild(t); }
    t.textContent = text;
    t.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function(){ t.classList.remove('show'); }, 3500);
  }
  // a call whose answer is the new state of one part (part: 'g', 'spans', 'colors', 'backdrop')
  function call(cmd, args, part, opts){
    return DD.call(cmd, args || {}).then(function(res){
      if (part) S[part] = res;
      // a theme change moves the glow's automatic color too: the colors' answer carries the background's state
      if (part === 'colors' && res && res.backdrop) S.backdrop = res.backdrop;
      if (!(opts && opts.quiet)) render();
      return res;
    }).catch(fail);
  }
  const setG = function(key, value, opts){ return call('set', {key: key, value: value}, 'g', opts); };
  const gv = function(key){ return S.g.values[key]; };

  // ---- controls ----
  function sw(on, onclick, disabled){
    const b = el('button', 'dds-sw' + (on ? ' on' : ''));
    b.disabled = !!disabled;
    b.setAttribute('role', 'switch');
    b.setAttribute('aria-checked', on ? 'true' : 'false');
    b.onclick = function(){ onclick(!on); };
    return b;
  }
  function select(value, options, onchange, disabled){
    const s = el('select', 'dds-select');
    options.forEach(function(o){
      const op = el('option', null, o[1]);
      op.value = String(o[0]);
      if (String(o[0]) === String(value)) op.selected = true;
      s.appendChild(op);
    });
    s.disabled = !!disabled;
    s.onchange = function(){
      const o = options[s.selectedIndex];
      onchange(o ? o[0] : s.value);
    };
    return s;
  }
  function seg(value, options, onchange, disabled){
    const box = el('span', 'dds-seg' + (disabled ? ' disabled' : ''));
    options.forEach(function(o){
      const b = el('button', String(o[0]) === String(value) ? 'on' : '', o[1]);
      b.disabled = !!disabled;
      if (o[2]) b.title = o[2];
      b.onclick = function(){ if (String(o[0]) !== String(value)) onchange(o[0]); };
      box.appendChild(b);
    });
    return box;
  }
  // a slider whose value shows beside it; while it is dragged the page is not redrawn (it would drop the drag)
  function slider(value, min, max, step, fmt, oninput, disabled, lead){
    const box = el('span', 'dds-slider');
    const r = el('input');
    r.type = 'range'; r.min = min; r.max = max; r.step = step || 1; r.value = value;
    r.disabled = !!disabled;
    // the value box: an optional reset arrow (lead) right beside the value text
    const vbox = el('span', 'dds-val');
    const v = el('span', null, fmt(value));
    if (lead) vbox.appendChild(lead);
    vbox.appendChild(v);
    let last = 0, timer = 0;
    function send(){ last = Date.now(); oninput(Number(r.value)); }
    r.oninput = function(){
      S.dragging = true;
      v.textContent = fmt(Number(r.value));
      clearTimeout(timer);
      if (Date.now() - last > 60) send(); else timer = setTimeout(send, 60);
    };
    r.onchange = function(){ clearTimeout(timer); S.dragging = false; send(); };
    // the value before the slider: the slider ends at the right edge, in line with the switches
    box.appendChild(vbox); box.appendChild(r);
    return box;
  }
  function numInput(value, min, max, onchange, disabled){
    const n = el('input', 'dds-input dds-num');
    n.type = 'number'; n.min = min; n.max = max; n.value = value;
    n.disabled = !!disabled;
    n.onchange = function(){
      let x = Math.round(Number(n.value));
      if (!isFinite(x)) x = min;
      x = Math.max(min, Math.min(max, x));
      n.value = x;
      onchange(x);
    };
    return n;
  }
  function textInput(value, onchange, opts){
    const t = el('input', 'dds-input');
    t.type = 'text'; t.value = value || '';
    if (opts && opts.max) t.maxLength = opts.max;
    if (opts && opts.placeholder) t.placeholder = opts.placeholder;
    if (opts && opts.id) t.dataset.keep = opts.id;
    let timer = 0;
    t.oninput = function(){ clearTimeout(timer); timer = setTimeout(function(){ onchange(t.value); }, 350); };
    t.onchange = function(){ clearTimeout(timer); onchange(t.value); };
    return t;
  }
  // a key combination: a click, then the keys (Escape gives up, Backspace clears)
  const KEYNAMES = {' ': 'Space', ArrowUp: 'Up', ArrowDown: 'Down', ArrowLeft: 'Left', ArrowRight: 'Right',
                    Escape: 'Esc', Enter: 'Return', PageUp: 'PgUp', PageDown: 'PgDown'};
  const IS_MAC = /^Mac/.test(navigator.platform || '');
  function keyCapture(value, onset, opts){
    const box = el('span', 'dds-keybox');
    const b = el('button', 'dds-key' + (value ? '' : ' empty'), value || '—');
    let waiting = false;
    function stop(){ waiting = false; b.classList.remove('wait'); b.textContent = value || '—'; document.removeEventListener('keydown', onKey, true); }
    function onKey(e){
      if (!b.isConnected){ stop(); return; }
      e.preventDefault(); e.stopPropagation();
      if (/^(Control|Shift|Alt|Meta|AltGraph|CapsLock)$/.test(e.key)) return;
      if (e.key === 'Escape'){ stop(); return; }
      if (e.key === 'Backspace' || e.key === 'Delete'){ stop(); onset(''); return; }
      const mods = [];
      if (opts && opts.single){
        // the table's key: one key alone
      } else {
        // Qt's key sequences on macOS: "Ctrl" is Command, "Meta" is the Control key
        if (IS_MAC ? e.metaKey : e.ctrlKey) mods.push('Ctrl');
        if (e.altKey) mods.push('Alt');
        if (e.shiftKey) mods.push('Shift');
        if (IS_MAC ? e.ctrlKey : e.metaKey) mods.push('Meta');
      }
      const chord = e.ctrlKey || e.metaKey || e.altKey;
      let k = KEYNAMES[e.key] || (e.key.length === 1 ? e.key.toUpperCase() : e.key);
      if (/^Key[A-Z]$/.test(e.code) && chord) k = e.code.slice(3);
      if (/^Digit\d$/.test(e.code) && (chord || e.shiftKey)) k = e.code.slice(5);
      stop();
      onset(mods.concat([k]).join('+'));
    }
    b.onclick = function(){
      if (waiting){ stop(); return; }
      waiting = true;
      b.classList.add('wait');
      b.textContent = T('Press a key...');
      document.addEventListener('keydown', onKey, true);
    };
    b.onblur = function(){ if (waiting) stop(); };
    // a cross before the key (hidden, its place kept, when no key is set): the key box ends at the right edge
    const clear = iconBtn('dds-x' + (value ? ' set' : ''), 'x', T('Clear'));
    clear.onclick = function(){ onset(''); };
    box.appendChild(clear); box.appendChild(b);
    return box;
  }
  // a setting: its name (and what it does, under it) on the left, the control on the right
  function field(label, hint, control, opts){
    const row = el('div', 'dds-field' + (opts && opts.off ? ' off' : '') + (opts && opts.wide ? ' wide' : ''));
    const text = el('div', 'dds-field-text');
    const lab = el('div', 'dds-label', label);
    if (hint) tip(lab, hint);
    text.appendChild(lab);
    row.appendChild(text);
    const ctl = el('div', 'dds-ctl');
    (Array.isArray(control) ? control : [control]).forEach(function(c){ if (c) ctl.appendChild(c); });
    row.appendChild(ctl);
    return row;
  }
  function section(title, hint){
    const sec = el('section', 'dds-sec');
    if (title){
      const h = el('h2', null, title);
      if (hint) tip(h, hint);
      sec.appendChild(h);
    }
    return sec;
  }
  // an explanation only where one is needed: an (i) after the name, the text in its tooltip
  function tip(node, text){
    const i = el('span', 'dds-tip');
    i.appendChild(icon('info'));
    // (not a title tooltip: Anki's window shows it late or not at all) the help bubble of the charts' "?", at once
    i.onmouseenter = function(){ showTip(i, text); };
    i.onmouseleave = function(){ if (!i.classList.contains('pinned')) hideTip(); };
    i.onclick = function(e){
      e.stopPropagation();
      const on = !i.classList.contains('pinned');
      document.querySelectorAll('.dds-tip.pinned').forEach(function(o){ o.classList.remove('pinned'); });
      if (on){ i.classList.add('pinned'); showTip(i, text); } else hideTip();
    };
    node.appendChild(i);
    return node;
  }
  let tipEl = null;
  function showTip(over, text){
    hideTip();
    tipEl = el('div', 'dd-helptip dds-helptip', text);
    document.body.appendChild(tipEl);
    const r = over.getBoundingClientRect(), w = tipEl.offsetWidth, h = tipEl.offsetHeight;
    let top = r.bottom + 6;
    if (top + h > window.innerHeight - 8) top = Math.max(8, r.top - h - 6);
    tipEl.style.left = Math.max(8, Math.min(r.left - 10, window.innerWidth - w - 8)) + 'px';
    tipEl.style.top = top + 'px';
  }
  function hideTip(){
    if (tipEl){ tipEl.remove(); tipEl = null; }
  }
  function dropTips(){
    document.querySelectorAll('.dds-tip.pinned').forEach(function(o){ o.classList.remove('pinned'); });
    hideTip();
  }
  document.addEventListener('mousedown', function(e){ if (!(e.target.closest && e.target.closest('.dds-tip'))) dropTips(); }, true);
  document.addEventListener('wheel', dropTips, true);
  document.addEventListener('keydown', function(e){ if (e.key === 'Escape') dropTips(); }, true);
  DD.settingsTip = tip;
  // an inline confirmation: text, then Cancel and the action
  function confirmBox(text, okText, onok, danger){
    const box = el('div', 'dds-confirm');
    box.appendChild(el('div', 'dds-confirm-text', text));
    const act = el('div', 'dds-actions');
    act.appendChild(btn(T('Cancel'), '', function(){ S.form = null; render(); }));
    act.appendChild(btn(okText, danger ? 'danger' : 'primary', onok));
    box.appendChild(act);
    return box;
  }
  const pct = function(v){ return v + ' %'; };
  const px = function(v){ return v + ' px'; };

  // ---- General ----
  function pageGeneral(){
    const K = S.K, g = S.g, page = el('div', 'dds-page');
    // language
    const lang = section(T('Global Style'));
    const langs = [['auto', T('Same as Anki')], ['en', 'English']].concat(g.languages);
    const langNotes = [];
    if (g.lang_restart) langNotes.push(el('div', 'dds-note', T('Restart Anki to apply the new language.')));
    lang.appendChild(field(L('Language:'), null,
      select(gv(K.LANGUAGE) || 'auto', langs, function(v){ setG(K.LANGUAGE, v); })));
    langNotes.forEach(function(n){ lang.appendChild(n); });
    if (g.lang_note && g.translations_url){
      const note = el('div', 'dds-note');
      const parts = T('Translations may contain mistakes. Corrections are welcome on {link}.').split('{link}');
      note.appendChild(document.createTextNode(parts[0]));
      const a = el('a', 'dds-a', 'GitHub');
      a.href = '#';
      a.onclick = function(e){ e.preventDefault(); DD.call('open_link', {name: 'translations'}); };
      note.appendChild(a);
      note.appendChild(document.createTextNode(parts[1] || ''));
      lang.appendChild(note);
    }
    const style = lang;
    style.appendChild(field(L('Decimal Precision:'), null,
      seg(gv(K.STATS_PRECISION), [0, 1, 2, 3, 4].map(function(n){ return [n, String(n)]; }), function(v){ setG(K.STATS_PRECISION, v); })));
    style.appendChild(field(L('Thousands Separator (400,000):'), null,
      sw(gv(K.USE_THOUSANDS_SEPARATOR), function(v){ setG(K.USE_THOUSANDS_SEPARATOR, v); })));
    style.appendChild(field(L('Chart Explanations (?):'), null,
      sw(gv(K.SHOW_CHART_HELP), function(v){ setG(K.SHOW_CHART_HELP, v); })));
    const touchTip = T('Controls mouse vs touch gestures and tap target sizing. Layout always adapts automatically to window width.');
    style.appendChild(field(L('Interaction Mode:'), touchTip,
      seg(gv(K.INTERACTION_MODE) || 'auto', [['auto', T('Auto')], ['desktop', T('Mouse')], ['touch', T('Touch')]],
        function(v){ setG(K.INTERACTION_MODE, v); })));
    page.appendChild(style);

    // animations
    const anim = section(T('Animations'));
    const scope = gv(K.ANIMATION_SCOPE) || 'all';
    const detailsOn = scope === 'all' || scope === 'no_pinned', pinnedOn = scope === 'all' || scope === 'no_details', anyOn = scope !== 'none';
    anim.appendChild(field(L('Animation Mode:'), null,
      select(scope, [['all', T('All Animations')], ['no_pinned', T('No Pinned Animations')], ['no_details', T('No Details Animations')], ['none', T('No Animations')]],
        function(v){ setG(K.ANIMATION_SCOPE, v); })));
    anim.appendChild(field(L('Appearance Animations:'), null,
      sw(gv(K.CHART_APPEAR_ANIMATION), function(v){ setG(K.CHART_APPEAR_ANIMATION, v); }, !anyOn), {off: !anyOn}));
    anim.appendChild(field(L('Zoom Animations:'), null,
      sw(gv(K.ZOOM_ANIMATION), function(v){ setG(K.ZOOM_ANIMATION, v); }, !anyOn), {off: !anyOn}));
    const axisTip = T("How the axes change when a chart's scale changes (zoom, deck, period).\nNumbers count: the numbers stay in place and count to their new values.\nTicks slide: round values slide to their new places, the dates move with the bars, as in Anki's charts.");
    anim.appendChild(field(L('Axis Animation:'), axisTip,
      select(gv(K.CHART_AXIS_ANIM) || 'slide', [['count', T('Numbers count')], ['slide', T('Ticks slide')]], function(v){ setG(K.CHART_AXIS_ANIM, v); })));
    const numTip = T("How a stat card's number changes (zoom, deck, period).\nNumbers count: the number counts to its new value.\nDigits roll: each digit that changes rolls to its new one, as a view counter.");
    anim.appendChild(field(L('Stat Card Numbers:'), numTip,
      select(gv(K.STAT_NUM_ANIM) || 'count', [['count', T('Numbers count')], ['roll', T('Digits roll')]], function(v){ setG(K.STAT_NUM_ANIM, v); })));
    const styles = [['morph', T('Animate Each Chart')], ['fade', T('Fade (Lighter)')], ['none', T('No Animation')]];
    const ddTip = T('How the Deep Dive charts show new data when the deck or period changes.\nAnimate Each Chart: every chart moves from its old values to the new ones.\nFade: the view fades from the old charts to the new ones, much lighter on slow computers.\nNo Animation: the new data shows at once.');
    const f1 = field(L('Deep Dive Transitions:'), ddTip,
      select(gv(K.DEEP_DIVE_TRANSITION_STYLE) || 'morph', styles, function(v){ setG(K.DEEP_DIVE_TRANSITION_STYLE, v); }, !detailsOn), {off: !detailsOn});
    anim.appendChild(f1);
    const pTip = T('How the pinned widgets show new data when the deck changes.\nAnimate Each Chart: every chart moves from its old values to the new ones.\nFade: each widget fades from its old chart to the new one, much lighter on slow computers.\nNo Animation: the new data shows at once.');
    const f2 = field(L('Pinned Transitions:'), pTip,
      select(gv(K.PINNED_TRANSITION_STYLE) || 'morph', styles, function(v){ setG(K.PINNED_TRANSITION_STYLE, v); }, !pinnedOn), {off: !pinnedOn});
    anim.appendChild(f2);
    const speeds = [['slow', T('Slow')], ['normal', T('Normal')], ['fast', T('Fast')]];
    anim.appendChild(field(L('Deep Dive Animation Speed:'), null,
      seg(gv(K.DEEP_DIVE_ANIMATION_SPEED) || 'normal', speeds, function(v){ setG(K.DEEP_DIVE_ANIMATION_SPEED, v); }, !detailsOn), {off: !detailsOn}));
    anim.appendChild(field(L('Pinned Animation Speed:'), null,
      seg(gv(K.PINNED_ANIMATION_SPEED) || 'normal', speeds, function(v){ setG(K.PINNED_ANIMATION_SPEED, v); }, !pinnedOn), {off: !pinnedOn}));
    page.appendChild(anim);

    // the Deep Dive window
    const disp = section(T('Deep Dive Display'));
    const adaptive = !!gv(K.ADAPTIVE_CHART_BINNING);
    disp.appendChild(field(L('Adaptive Chart Binning:'), null, sw(adaptive, function(v){ setG(K.ADAPTIVE_CHART_BINNING, v); })));
    const SCALES = [50, 75, 100, 150, 200], NAMES = ['Much finer', 'Finer', 'Normal', 'Coarser', 'Much coarser'];
    let si = SCALES.indexOf(Number(gv(K.CHART_BINNING_SCALE)));
    if (si < 0) si = 2;
    // the arrow back to the default before the slider: hidden (its place kept) at the default, the slider never moves
    const reset = iconBtn('dds-x dws-icon' + (si !== 2 ? ' set' : ''), 'reset', T('Reset to default (Normal)'));
    reset.disabled = !adaptive;
    reset.onclick = function(){ setG(K.CHART_BINNING_SCALE, 100); };
    disp.appendChild(field(L('Chart Binning:'), T('How many days are grouped in one bar when adaptive binning is enabled. Each step moves along day, 2 days, 3 days, week, 2 weeks, month, 2 months, 3 months.'),
      [slider(si, 0, 4, 1, function(i){ return T(NAMES[i]); }, function(i){ reset.classList.toggle('set', i !== 2); setG(K.CHART_BINNING_SCALE, SCALES[i], {quiet: true}); }, !adaptive, reset)], {off: !adaptive}));
    const table = !!gv(K.DETAILS_TABLE_SHOW);
    disp.appendChild(field(L('Show Table:'), null,
      sw(table, function(v){ setG(K.DETAILS_TABLE_SHOW, v); })));
    disp.appendChild(field(L('Close Table After Picking:'), null,
      sw(gv(K.DETAILS_TABLE_DRAWER_AUTO_CLOSE), function(v){ setG(K.DETAILS_TABLE_DRAWER_AUTO_CLOSE, v); }, !table), {off: !table}));
    disp.appendChild(field(L('Table Shortcut:'), null,
      keyCapture(gv(K.DETAILS_TABLE_DRAWER_SHORTCUT), function(v){ setG(K.DETAILS_TABLE_DRAWER_SHORTCUT, v); }, {single: true}), {off: !table}));
    disp.appendChild(field(L('Show Charts Without Data:'), T('Off: Deep Dive leaves out charts that have no data for the selected deck and period. On: they stay, with a "No data for this graph" message.'),
      sw(gv(K.SHOW_EMPTY_CHARTS), function(v){ setG(K.SHOW_EMPTY_CHARTS, v); })));
    disp.appendChild(field(L('Collapsible Charts:'), null,
      sw(gv(K.DEEP_DIVE_CHARTS_COLLAPSIBLE), function(v){ setG(K.DEEP_DIVE_CHARTS_COLLAPSIBLE, v); })));
    disp.appendChild(field(L('Fill Window Height:'), T('When the Deep Dive charts do not fill the window, make them taller (up to 1.6x) so there is no empty space under them. Charts you resized by hand are left alone.'),
      sw(gv(K.DEEP_DIVE_FILL_HEIGHT), function(v){ setG(K.DEEP_DIVE_FILL_HEIGHT, v); })));
    disp.appendChild(field(L('Same Height for All Rows:'), T("Resizing a chart's height resizes every row of the Deep Dive. Off: only the row of that chart, each row keeping its own height."),
      sw(gv(K.DEEP_DIVE_SHARED_ROW_HEIGHT), function(v){ setG(K.DEEP_DIVE_SHARED_ROW_HEIGHT, v); })));
    page.appendChild(disp);

    // chart style
    const cs = section(T('Chart Style'));
    cs.appendChild(field(L('Total / Average Lines:'), T('Opacity of the Total and Average lines (and the soft area under Total). Lower = more discreet.'),
      slider(gv(K.CHART_LINE_OPACITY), 0, 200, 5, pct, function(v){ setG(K.CHART_LINE_OPACITY, v, {quiet: true}); })));
    cs.appendChild(field(L('Total Line:'), T("A line over the edge of the Total area. 0% = no line (Anki's look), 100% = a clear line."),
      slider(gv(K.CHART_TOTAL_LINE), 0, 100, 5, pct, function(v){ setG(K.CHART_TOTAL_LINE, v, {quiet: true}); })));
    cs.appendChild(field(L('Bar Gradient:'), null,
      slider(gv(K.CHART_BAR_GRADIENT), 0, 100, 5, pct, function(v){ setG(K.CHART_BAR_GRADIENT, v, {quiet: true}); })));
    cs.appendChild(field(T('Grid lines'), null,
      sw(gv(K.CHART_SHOW_GRID), function(v){ setG(K.CHART_SHOW_GRID, v); })));
    page.appendChild(cs);

    // table
    const tl = section(T('Table Layout'));
    tl.appendChild(field(L('Row Height (px):'), null, numInput(gv(K.GLOBAL_ROW_HEIGHT), 10, 200, function(v){ setG(K.GLOBAL_ROW_HEIGHT, v); })));
    tl.appendChild(field(L('Zebra Rows:'), null,
      sw(gv(K.TABLE_ZEBRA), function(v){ setG(K.TABLE_ZEBRA, v); })));
    page.appendChild(tl);

    // Anki's toolbar
    const tb = section(T('Anki Toolbar'));
    const st = g.toolbar_styles, cur = gv(K.TOOLBAR_BUTTON_STYLE);
    tb.appendChild(field(L('Toolbar Button:'), null,
      seg(cur, [[st[0], T('Logo')], [st[1], T('Text (Deep Dive)')], [st[2], T('None (Hidden)')]], function(v){ setG(K.TOOLBAR_BUTTON_STYLE, v); })));
    if (cur === st[1]) tb.appendChild(field(L('Button Text:'), null,
      textInput(gv(K.TOOLBAR_BUTTON_TEXT), function(v){ setG(K.TOOLBAR_BUTTON_TEXT, v, {quiet: true}); }, {max: 40, placeholder: 'Deep Dive', id: 'toolbar_text'})));
    const open = field(L('Open Shortcut:'), null, keyCapture(gv(K.OPEN_SHORTCUT), function(v){ setG(K.OPEN_SHORTCUT, v); }));
    tb.appendChild(open);
    if (g.open_conflict){
      const w = el('div', 'dds-note warn', T('Already used by Anki: {action}', {action: g.open_conflict}));
      tb.appendChild(w);
    }
    page.appendChild(tb);

    page.appendChild(pinnedSection());
    page.appendChild(shareSection());
    page.appendChild(profilesSection());
    if (S.dev) page.appendChild(devSection());
    return page;
  }

  function pinnedSection(){
    const K = S.K, sec = section(T('Pinned Widgets'),
      T('Each widget also has its own settings (title, deck, time span, style): right click it, then {settings}.', {settings: T('Settings')}));
    const off = !!S.g.pinned_off;
    sec.appendChild(field(T('Main Menu: Above Stats Line'), T("Displays pinned widgets above Anki's study summary (Studied X cards...)."),
      sw(gv(K.PINNED_POSITION_TOP), function(v){ setG(K.PINNED_POSITION_TOP, v); }, off), {off: off}));
    sec.appendChild(field(T('Deck View: Above Study Button'), T("Displays pinned widgets above the 'Study Now' button in the deck overview."),
      sw(gv(K.PINNED_POSITION_TOP_DECK), function(v){ setG(K.PINNED_POSITION_TOP_DECK, v); }, off), {off: off}));
    sec.appendChild(field(T('Collapsible Charts'), null,
      sw(gv(K.PINNED_CHARTS_COLLAPSIBLE), function(v){ setG(K.PINNED_CHARTS_COLLAPSIBLE, v); }, off), {off: off}));
    sec.appendChild(field(T("Period and deck labels next to the charts' titles"), T('A label such as "Past Month" by each chart\'s title; a click on it changes the period or the deck.'),
      sw(gv(K.PINNED_CARD_LABELS), function(v){ setG(K.PINNED_CARD_LABELS, v); }, off), {off: off}));
    sec.appendChild(field(T('Show "Add a widget" when nothing is pinned'), null,
      sw(gv(K.PINNED_EMPTY_HINT), function(v){ setG(K.PINNED_EMPTY_HINT, v); }, off), {off: off}));
    [[K.PINNED_MARGIN_SIDE, 'Side Margin:', ''],
     [K.PINNED_MARGIN_TOP, 'Top Margin:', ''],
     [K.PINNED_MARGIN_BOTTOM, 'Bottom Margin:', ''],
     [K.PINNED_SECTION_SPACING, 'Space Between Lines:', 'Empty space between two lines of widgets, by default. Each one can also be changed by dragging it.']
    ].forEach(function(m){
      sec.appendChild(field(L(m[1]), m[2] ? T(m[2]) : null, slider(gv(m[0]) || 0, 0, 200, 1, px, function(v){ setG(m[0], v, {quiet: true}); }, off), {off: off}));
    });
    const dis = field(T('Disable Pinned Widgets (restart Anki)'),
      T("Turns off the widgets pinned on Anki's main screen. Use it if they clash with another add-on. Takes effect after restarting Anki."),
      sw(off, function(v){ setG('pinned_off', v); }));
    sec.appendChild(dis);
    return sec;
  }

  function shareSection(){
    const sec = section(T('Export & Share'),
      T('Export or share your setup (themes, custom presets, colors, pinned & Deep Dive layouts, table columns and animations). Decks, deck colors, excluded dates and language stay private by default.'));
    const F = S.form && S.form.kind === 'share' ? S.form : null;
    if (S._shareFull === undefined) S._shareFull = false;
    const codeRow = el('div', 'dds-row');
    codeRow.appendChild(btn(T('Copy Share Code'), '', function(){
      DD.call('share', {action: 'copy_code'}).then(function(r){
        toast((r && r.message) || T('Share code copied to clipboard.'));
      }).catch(fail);
    }));
    codeRow.appendChild(btn(T('Paste Share Code...'), '', function(){
      S.form = F ? null : {kind: 'share', text: ''};
      render();
    }));
    sec.appendChild(field(T('Share Code'), T('Compact code (DDCFG1:...) easy to paste on Discord, Reddit or with friends.'), codeRow));
    if (F){
      const box = el('div', 'dds-confirm');
      box.appendChild(el('div', 'dds-note', T('Paste a share code (DDCFG1:...) or exported JSON below. Your decks, deck colors, excluded dates and existing custom presets are kept.')));
      const ta = document.createElement('textarea');
      ta.className = 'dds-in';
      ta.rows = 3;
      ta.style.cssText = 'width:100%;box-sizing:border-box;font-family:Consolas,monospace;font-size:11px;resize:vertical;margin:6px 0';
      ta.placeholder = 'DDCFG1:...';
      ta.value = F.text || '';
      ta.oninput = function(){ F.text = ta.value; };
      box.appendChild(ta);
      const acts = el('div', 'dds-row');
      acts.appendChild(btn(T('Import'), 'accent', function(){
        if (!(F.text || '').trim()){ toast(T('Paste a share code first.')); return; }
        DD.call('share', {action: 'import_code', code: F.text}).then(function(r){
          if (r && !r.ok) toast(r.message || T('Could not import settings.'));
        }).catch(fail);
      }));
      acts.appendChild(btn(T('Cancel'), '', function(){ S.form = null; render(); }));
      box.appendChild(acts);
      sec.appendChild(box);
    }
    const fileRow = el('div', 'dds-row');
    fileRow.appendChild(btn(T('Export to File...'), '', function(){
      DD.call('share', {action: 'export_file', shareable: !S._shareFull}).catch(fail);
    }));
    fileRow.appendChild(btn(T('Import from File...'), '', function(){
      DD.call('share', {action: 'import_file'}).catch(fail);
    }));
    sec.appendChild(field(T('Config File (.json)'), T('Save to a JSON file or restore from one.'), fileRow));
    sec.appendChild(field(T('Include profile-specific data in file export'),
      T('Off (recommended for sharing): excludes decks, deck colors, excluded dates and language. On: full personal backup.'),
      sw(!!S._shareFull, function(v){ S._shareFull = !!v; render(); })));
    return sec;
  }

  function profilesSection(){
    const sec = section(T('Profiles'), T('Each Anki profile has its own settings. A new profile starts with the settings of the profile used last, without its decks.'));
    const F = S.form && S.form.kind === 'profiles' ? S.form : null;
    if (!F){
      sec.appendChild(field(T('Copy settings from another profile...').replace(/\s*(\.\.\.|…)$/, ''),
        T('Look, charts, pinned widgets and layout of another profile. This profile keeps its decks, excluded dates and deck colors.'),
        btn(T('Copy...'), '', function(){
          DD.call('profiles', {action: 'list'}).then(function(names){
            S.form = {kind: 'profiles', names: names || [], name: (names || [])[0]};
            render();
          }).catch(fail);
        })));
      return sec;
    }
    if (!F.names.length){
      sec.appendChild(el('div', 'dds-note', T('There is no other profile with Deep Dive settings.')));
      sec.appendChild(btn(T('OK'), '', function(){ S.form = null; render(); }));
      return sec;
    }
    const pick = select(F.name, F.names.map(function(n){ return [n, n]; }), function(v){ F.name = v; render(); });
    sec.appendChild(field(L('Profile:'), null, pick));
    sec.appendChild(confirmBox(T('Replace the settings of this profile with those of {name}? This profile keeps its decks, excluded dates and deck colors.', {name: F.name}),
      T('Copy settings from another profile...').replace(/\.\.\.$|…$/, ''), function(){
        DD.call('profiles', {action: 'copy', name: F.name}).then(function(r){
          if (r && !r.ok) toast(r.message || '');
        }).catch(fail);
      }));
    return sec;
  }

  function devSection(){
    const sec = section(T('Developer'));
    const F = S.form && S.form.kind === 'dev' ? S.form : null;
    function act(action, label, hint, confirmText){
      const b = btn(label, '', function(){
        if (confirmText){ S.form = {kind: 'dev', action: action, text: confirmText, label: label.replace(/\.\.\.$/, '')}; render(); }
        else DD.call('dev', {action: action}).catch(fail);
      });
      sec.appendChild(field(label.replace(/\.\.\.$/, ''), hint, b));
      if (F && F.action === action) sec.appendChild(confirmBox(F.text, F.label, function(){ DD.call('dev', {action: action}).catch(fail); }, true));
    }
    act('reset_profile', T("Reset this profile's settings..."), null,
        T('This deletes the Deep Dive settings of the current Anki profile (pinned widgets, colors, excluded dates, everything) and cannot be undone.\n\nContinue?'));
    act('reset_everything', T('Reset all profiles...'), null,
        T('This deletes the Deep Dive settings of every Anki profile (pinned widgets, colors, excluded dates, everything) and cannot be undone.\n\nContinue?'));
    act('data_folder', T('Open data folder'), T('Opens user_files: settings, history cache and the debug log.'));
    act('rate_banner', T('Preview rating banner'), null);
    act('reset_tips', T('Reset guided tour'), null);
    return sec;
  }

  // ---- Time Span ----
  function pageSpans(){
    const P = S.spans, page = el('div', 'dds-page');
    const tabs = P.tabs;
    if (S.span >= tabs.length) S.span = tabs.length - 1;
    const sec = section(T('Time Span'));
    const resetAll = el('button', 'dds-link dds-h2-act', T('Reset Defaults'));
    resetAll.onclick = function(){ S.span = 0; call('span', {action: 'reset'}, 'spans'); };
    sec.firstChild.appendChild(resetAll);
    const wrap = el('div', 'dds-spans');
    // the list
    const list = el('div', 'dds-span-list');
    tabs.forEach(function(t, i){
      const item = el('div', 'dds-span-item' + (i === S.span ? ' on' : '') + (t.enabled === false ? ' off' : ''));
      item.appendChild(el('span', 'dds-span-name', t.shown_title || T('Untitled')));
      item.onclick = function(){ S.span = i; render(); };
      if (i === S.span){
        const up = iconBtn('dds-mini', 'up', T('Move up')), down = iconBtn('dds-mini', 'down', T('Move down'));
        up.disabled = i === 0; down.disabled = i === tabs.length - 1;
        up.onclick = function(e){ e.stopPropagation(); S.span = i - 1; call('span', {action: 'move', index: i, value: i - 1}, 'spans'); };
        down.onclick = function(e){ e.stopPropagation(); S.span = i + 1; call('span', {action: 'move', index: i, value: i + 1}, 'spans'); };
        item.appendChild(up); item.appendChild(down);
      }
      list.appendChild(item);
    });
    const lb = el('div', 'dds-span-btns');
    lb.appendChild(btn(T('+ Add Tab'), 'small', function(){ S.span = tabs.length; call('span', {action: 'add'}, 'spans'); }));
    const rm = btn(T('- Remove Tab'), 'small', function(){ call('span', {action: 'remove', index: S.span}, 'spans'); });
    rm.disabled = tabs.length <= 1;
    lb.appendChild(rm);
    const left = el('div', 'dds-span-left');
    left.appendChild(list); left.appendChild(lb);
    wrap.appendChild(left);
    // the editor
    const t = tabs[S.span] || {}, i = S.span, ed = el('div', 'dds-span-edit');
    const setS = function(key, value, opts){ return call('span', {action: 'set', index: i, key: key, value: value}, 'spans', opts); };
    ed.appendChild(field(L('Active:'), null, sw(t.enabled !== false, function(v){ setS('enabled', v); })));
    ed.appendChild(field(L('Title:'), null, textInput(t.shown_title, function(v){ setS('title', v, {quiet: true}).then(function(){ refreshSpanNames(); }); }, {id: 'span_title_' + i})));
    const isCustom = Number(t.range) === Number(P.custom);
    ed.appendChild(field(L('Range:'), null, select(t.range, P.ranges.map(function(r){ return [r[1], r[0]]; }), function(v){ setS('range', Number(v)); })));
    if (isCustom){
      const type = t.custom_type || 'relative';
      ed.appendChild(field(L('Type:'), null, seg(type, [['relative', T('Relative Days')], ['absolute', T('Date Range')]], function(v){ setS('custom_type', v); })));
      if (type === 'relative'){
        ed.appendChild(field(L('Past Days:'), null, numInput(t.days || 7, 1, 9999, function(v){ setS('days', v); })));
      } else {
        const today = new Date(), iso = today.getFullYear() + '-' + ('0' + (today.getMonth() + 1)).slice(-2) + '-' + ('0' + today.getDate()).slice(-2);
        const start = el('input', 'dds-input dds-date'); start.type = 'date'; start.value = t.start_date || iso;
        start.onchange = function(){ if (start.value) setS('start_date', start.value); };
        ed.appendChild(field(L('Start Date:'), null, start));
        const toToday = !!t.to_today;
        ed.appendChild(field(L('Until today:'), null,
          sw(toToday, function(v){
            if (v) setS('to_today', true);
            else setS('to_today', false, {quiet: true}).then(function(){ setS('end_date', iso); });
          })));
        if (!toToday){
          const end = el('input', 'dds-input dds-date'); end.type = 'date'; end.value = t.end_date || iso;
          end.onchange = function(){ if (end.value) setS('end_date', end.value); };
          ed.appendChild(field(L('End Date:'), null, end));
        }
      }
    }
    ed.appendChild(el('h3', null, T('Formatting')));
    ed.appendChild(field(L('Use Decimal:'), null, sw(t.use_decimal !== false, function(v){ setS('use_decimal', v); })));
    wrap.appendChild(ed);
    sec.appendChild(wrap);
    page.appendChild(sec);

    // the table's columns (the same for every span)
    const cols = section(T('Columns to Show'), T("The same columns for every time span. Also in the right-click menu of the table's header."));
    const shown = new Set(P.shown);
    const grid = el('div', 'dds-cols');
    P.groups.forEach(function(gr){
      const box = el('div', 'dds-colgroup');
      box.appendChild(el('div', 'dds-colgroup-title', gr[1]));
      P.columns.filter(function(c){ return c.group === gr[0]; }).forEach(function(c){
        const lab = el('label', 'dds-check');
        const cb = el('input'); cb.type = 'checkbox'; cb.checked = shown.has(c.key);
        cb.onchange = function(){
          const keys = P.columns.map(function(x){ return x.key; }).filter(function(k){ return k === c.key ? cb.checked : shown.has(k); });
          call('columns', {keys: keys, counts: P.counts}, 'spans');
        };
        lab.appendChild(cb); lab.appendChild(el('span', null, c.label));
        box.appendChild(lab);
      });
      grid.appendChild(box);
    });
    cols.appendChild(grid);
    cols.appendChild(field(T('Show counts (pass / fail)'), T('Pass / fail counts next to the retention and the buttons.'),
      sw(P.counts, function(v){ call('columns', {keys: P.shown, counts: v}, 'spans'); })));
    cols.appendChild(field(L('Show Full Deck Path:'), null, sw(gv(S.K.SHOW_FULL_DECK_NAME), function(v){ setG(S.K.SHOW_FULL_DECK_NAME, v); })));
    const rc = el('div', 'dds-actions');
    rc.appendChild(btn(T('Reset Columns'), 'small', function(){ call('columns', {reset: true}, 'spans'); }));
    cols.appendChild(rc);
    page.appendChild(cols);
    return page;
  }
  // a title typed: the list follows without redrawing the field being typed in
  function refreshSpanNames(){
    const items = mainEl.querySelectorAll('.dds-span-item .dds-span-name');
    S.spans.tabs.forEach(function(t, i){ if (items[i]) items[i].textContent = t.shown_title || T('Untitled'); });
  }

  // ---- Colors ----
  function swatch(hex, onclick, title){
    const b = el('button', 'dds-swatch');
    b.style.background = hex;
    b.title = title || T('Click to pick color');
    b.onclick = onclick;
    return b;
  }
  function themeGrid(current, pinned){
    const box = el('div');
    const bar = el('div', 'dds-bar');
    const find = el('input', 'dds-input');
    find.placeholder = T('Search themes...');
    find.value = pinned ? S.pthemeFind : S.themeFind;
    find.dataset.keep = pinned ? 'ptheme_find' : 'theme_find';
    bar.appendChild(find);
    if (!pinned) bar.appendChild(seg(S.themeFilter, [['all', T('All')], ['dark', T('Dark')], ['light', T('Light')], ['custom', T('Custom')]],
      function(v){ S.themeFilter = v; render(); }));
    box.appendChild(bar);
    const grid = el('div', 'dds-themes');
    grid.dataset.keepScroll = pinned ? 'pthemes' : 'themes';
    function fill(){
      grid.innerHTML = '';
      const q = (pinned ? S.pthemeFind : S.themeFind).trim().toLowerCase();
      const f = pinned ? 'all' : S.themeFilter;
      S.colors.presets.forEach(function(p){
        if (q && T(p.name).toLowerCase().indexOf(q) < 0 && p.name.toLowerCase().indexOf(q) < 0) return;
        if (f === 'dark' && !p.dark) return;
        if (f === 'light' && p.dark) return;
        if (f === 'custom' && !p.custom) return;
        const c = el('button', 'dds-theme' + (p.key === current ? ' on' : ''));
        const pal = p.pal;
        c.style.background = pal.bg_root;
        c.style.borderColor = p.key === current ? '' : pal.border_subtle;
        const prev = el('span', 'dds-theme-prev');
        prev.style.background = pal.bg_surface;
        const bar1 = el('i'); bar1.style.background = pal.accent;
        const bar2 = el('i'); bar2.style.background = pal.total_line || pal.text_secondary;
        const bar3 = el('i'); bar3.style.background = pal.text_secondary;
        prev.appendChild(bar1); prev.appendChild(bar2); prev.appendChild(bar3);
        const nm = el('span', 'dds-theme-name', p.custom ? p.name : T(p.name));
        nm.style.color = pal.text_primary;
        c.appendChild(prev); c.appendChild(nm);
        c.title = nm.textContent;
        c.onclick = function(){ call('theme', {action: 'preset', key: p.key, pinned: pinned}, 'colors'); };
        grid.appendChild(c);
      });
      if (!grid.childNodes.length) grid.appendChild(el('div', 'dds-empty', T('No theme matches.')));
    }
    find.oninput = function(){ if (pinned) S.pthemeFind = find.value; else S.themeFind = find.value; fill(); };
    fill();
    box.appendChild(grid);
    return box;
  }
  function themeColors(st, pinned){
    const box = el('div', 'dds-colorlist');
    st.colors.forEach(function(c){
      const row = el('div', 'dds-crow');
      row.appendChild(swatch(c.hex, function(){ DD.call('pick', {what: 'theme', key: c.key, pinned: pinned}); }, c.hex + ' · ' + T('Click to pick color')));
      row.appendChild(el('span', 'dds-clabel', c.label));
      const x = iconBtn('dds-x' + (c.changed ? ' set' : ''), 'reset', T('Reset to preset value'));
      x.onclick = function(){ call('theme', {action: 'reset_color', key: c.key, pinned: pinned}, 'colors'); };
      row.appendChild(x);
      box.appendChild(row);
    });
    return box;
  }
  function modeSeg(st, pinned){
    return seg(st.mode, [['native', T('Follow Anki')], ['dark', T('Dark')], ['light', T('Light')]],
      function(v){ call('theme', {action: 'mode', mode: v, pinned: pinned}, 'colors'); }, st.native);
  }

  // the adaptation mode against the theme's own (settings._adapt_warn): the note, and a button for the theme's mode
  function adaptWarn(w, pinned){
    const row = el('div', 'dds-warn-row');
    row.appendChild(el('div', 'dds-note warn', w.text));
    row.appendChild(btn(w.btn, 'small', function(){ call('theme', {action: 'mode', mode: w.fix, pinned: pinned}, 'colors'); }));
    return row;
  }
  function pageColors(){
    const C = S.colors, page = el('div', 'dds-page');
    // the Deep Dive theme
    const th = section(T('Theme'), null);
    th.appendChild(themeGrid(C.details.preset, false));
    th.appendChild(field(L('Graph Adaptation Mode:'), C.details.native ? T('Anki Native always follows Anki light/dark mode.') : T('Controls graph adaptation mode (line/border/text contrast) for this preset.'),
      modeSeg(C.details, false), {off: C.details.native}));
    if (C.details.adapt_warn) th.appendChild(adaptWarn(C.details.adapt_warn, false));
    if (C.mismatch){
      // the way out at hand: the main screen's widgets take a theme of their own (Anki's own by default)
      const w = el('div', 'dds-warn-row');
      w.appendChild(el('div', 'dds-note warn', C.mismatch));
      w.appendChild(btn(T('Use Separate Pinned Theme'), 'small', function(){
        call('theme', {action: 'pinned_mode', mode: 'separate'}, 'colors').then(function(){
          const sec = mainEl.querySelector('.dds-pinned-theme');
          if (sec) mainEl.scrollTop += sec.getBoundingClientRect().top - mainEl.getBoundingClientRect().top - 12;
        });
      }));
      th.appendChild(w);
    }
    th.appendChild(el('h3', null, T('Theme Colors')));
    th.appendChild(themeColors(C.details, false));
    // presets of one's own
    const F = S.form && S.form.kind === 'preset' ? S.form : null;
    const pa = el('div', 'dds-actions start');
    if (F && F.action === 'save'){
      const name = el('input', 'dds-input');
      name.placeholder = L('Preset name:');
      name.value = F.name || '';
      name.dataset.keep = 'preset_name';
      name.oninput = function(){ F.name = name.value; };
      const err = el('span', 'dds-err', F.err || '');
      const ok = btn(T('Save'), 'primary', function(){
        if (!String(F.name || '').trim()){ F.err = T('Preset name cannot be empty.'); render(); return; }
        S.form = null;
        call('theme', {action: 'save_preset', name: F.name}, 'colors');
      });
      name.onkeydown = function(e){ if (e.key === 'Enter') ok.click(); if (e.key === 'Escape'){ S.form = null; render(); } };
      pa.appendChild(name); pa.appendChild(btn(T('Cancel'), '', function(){ S.form = null; render(); })); pa.appendChild(ok); pa.appendChild(err);
      if (!F.focused){ F.focused = true; setTimeout(function(){ name.focus(); }, 0); }
    } else if (F && F.action === 'delete'){
      th.appendChild(confirmBox(T("Delete theme preset '{name}'?", {name: F.name}), T('Delete Preset'), function(){
        S.form = null; call('theme', {action: 'delete_preset'}, 'colors');
      }, true));
    } else {
      pa.appendChild(btn(T('Save as New Preset'), 'small', function(){ S.form = {kind: 'preset', action: 'save', name: ''}; render(); }));
      if (C.details.custom){
        pa.appendChild(btn(T('Update Preset'), 'small', function(){ call('theme', {action: 'update_preset'}, 'colors'); }));
        const cur = C.presets.filter(function(p){ return p.key === C.details.preset; })[0];
        pa.appendChild(btn(T('Delete Preset'), 'small', function(){ S.form = {kind: 'preset', action: 'delete', name: cur ? cur.name : ''}; render(); }));
      }
    }
    th.appendChild(pa);
    page.appendChild(th);

    // the pinned widgets' theme
    const pt = section(T('Pinned Theme Mode'));
    pt.classList.add('dds-pinned-theme');
    const hints = {native: T('Pinned widgets use Anki native colors (not Details theme colors).'),
                   linked: T('Pinned widgets use the same theme as Details (same preset and same custom colors).'),
                   separate: T("Pinned widgets use an independent theme. Configure it in the 'Pinned' tab.")};
    pt.appendChild(field(T('Theme'), C.pinned_mode === 'separate' ? T('Choose how pinned widgets pick their theme.') : hints[C.pinned_mode],
      select(C.pinned_mode, [['native', T('Use Native (Anki)')], ['linked', T('Use Details Theme')], ['separate', T('Use Separate Pinned Theme')]],
        function(v){ call('theme', {action: 'pinned_mode', mode: v}, 'colors'); })));
    if (C.pinned_mode === 'separate'){
      pt.appendChild(themeGrid(C.pinned.preset, true));
      pt.appendChild(field(L('Pinned Graph Adaptation Mode:'), null, modeSeg(C.pinned, true), {off: C.pinned.native}));
      if (C.pinned.adapt_warn) pt.appendChild(adaptWarn(C.pinned.adapt_warn, true));
      pt.appendChild(el('h3', null, T('Pinned Theme Colors')));
      pt.appendChild(themeColors(C.pinned, true));
    }
    page.appendChild(pt);

    page.appendChild(backdropSection());

    // data colors
    const sep = C.pinned_mode === 'separate';
    if (!sep) S.dataPinned = false;
    const dc = section(T('Data Colors'));
    if (sep){
      dc.appendChild(field(S.dataPinned ? T('Data colors currently target Pinned (separate pinned theme mode).') : T('Data colors currently target Details (global details theme).'), null,
        seg(S.dataPinned ? 'p' : 'd', [['d', T('Details')], ['p', T('Pinned')]], function(v){ S.dataPinned = v === 'p'; render(); })));
    }
    const groups = el('div', 'dds-dgroups');
    (S.dataPinned ? C.data.pinned : C.data.details).forEach(function(gr){
      const box = el('div', 'dds-dgroup');
      box.appendChild(el('div', 'dds-colgroup-title', gr.title));
      gr.rows.forEach(function(c){
        const row = el('div', 'dds-crow');
        row.appendChild(swatch(c.hex, function(){ DD.call('pick', {what: 'data', key: c.key, pinned: S.dataPinned}); }));
        row.appendChild(el('span', 'dds-clabel', c.label));
        const x = iconBtn('dds-x' + (c.changed ? ' set' : ''), 'reset', T('Reset to preset value'));
        x.onclick = function(){ call('data_color', {action: 'reset', key: c.key, pinned: S.dataPinned}, 'colors'); };
        row.appendChild(x);
        box.appendChild(row);
      });
      groups.appendChild(box);
    });
    dc.appendChild(groups);
    const ra = el('div', 'dds-actions');
    ra.appendChild(btn(T('Reset Colors to Default'), 'small', function(){ call('data_color', {action: 'reset_all', pinned: S.dataPinned}, 'colors'); }));
    dc.appendChild(ra);
    page.appendChild(dc);
    return page;
  }

  function backdropSection(){
    const B = S.backdrop, s = B.settings, sec = section(T('Window Background'),
      null);
    const names = {off: 'Off', clean: 'Clean', subtle: 'Subtle', balanced: 'Balanced', vivid: 'Vivid'};
    // the arrow back to the default first: the buttons keep their place when it is hidden (at the default look)
    const reset = iconBtn('dds-x dws-icon' + (B.preset !== 'clean' ? ' set' : ''), 'reset', T('Back to the default look (Clean).'));
    reset.onclick = function(){ call('backdrop', {action: 'reset'}, 'backdrop'); };
    const styleCtl = [reset];
    if (!B.preset) styleCtl.push(el('span', 'dds-tag', T('Custom')));
    styleCtl.push(seg(B.preset || '', B.presets.map(function(k){ return [k, T(names[k] || k)]; }),
      function(v){ call('backdrop', {action: 'preset', key: v}, 'backdrop'); }));
    sec.appendChild(field(L('Style:'), null, styleCtl));
    const off = !s.enabled;
    sec.appendChild(field(T('Background tone'), T('How much deeper than the theme color the window background is.'),
      slider(s.tone, 0, 100, 1, pct, function(v){ call('backdrop', {action: 'slider', key: 'tone', value: v}, 'backdrop', {quiet: true}); }), {off: off}));
    sec.appendChild(field(T('Glow'), null,
      slider(s.glow, 0, 100, 1, pct, function(v){ call('backdrop', {action: 'slider', key: 'glow', value: v}, 'backdrop', {quiet: true}); }), {off: off}));
    const auto = el('button', 'dds-link', T('Auto'));
    auto.title = T("Go back to the theme's accent color.");
    auto.disabled = B.auto;
    auto.onclick = function(){ call('backdrop', {action: 'auto_color'}, 'backdrop'); };
    const hint = B.auto ? el('span', 'dds-tag', T('Auto')) : null;
    sec.appendChild(field(L('Glow color:'), null,
      [swatch(B.color, function(){ DD.call('pick', {what: 'glow'}); }, T("Click to pick a color. 'Auto' uses your theme's accent color.")), hint, B.auto ? null : auto], {off: off}));
    return sec;
  }

  // ---- Decks (settings_decks.js) ----
  function pageDecks(){
    if (!decksEl) decksEl = DD.decksPage(S.decks);
    return decksEl;
  }

  // ---- the window ----
  const TABS = [['general', 'General'], ['spans', 'Time Span'], ['colors', 'Colors'], ['decks', 'Decks']];
  // 15 px line icons for the sidebar tabs
  const NAV_ICONS = {
    general: '<line x1="4" y1="6" x2="20" y2="6"/><line x1="4" y1="12" x2="20" y2="12"/><line x1="4" y1="18" x2="20" y2="18"/><circle cx="9" cy="6" r="2" fill="var(--dd-bg)"/><circle cx="15" cy="12" r="2" fill="var(--dd-bg)"/><circle cx="10" cy="18" r="2" fill="var(--dd-bg)"/>',
    spans: '<rect x="3" y="5" width="18" height="16" rx="2"/><line x1="16" y1="3" x2="16" y2="7"/><line x1="8" y1="3" x2="8" y2="7"/><line x1="3" y1="10" x2="21" y2="10"/>',
    colors: '<path d="M8 1.6C4.4 1.6 1.6 4.3 1.6 7.6c0 3.3 2.8 6.3 6.2 6.3 1.1 0 1.6-.6 1.6-1.3 0-.8-.6-1.1-.6-1.9 0-.7.6-1.2 1.3-1.2h1.5c1.6 0 2.8-1.3 2.8-2.9C14.4 3.9 11.6 1.6 8 1.6z" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linejoin="round"/><circle cx="4.7" cy="7.7" r="1.15" fill="#e5484d" stroke="none"/><circle cx="6.1" cy="4.7" r="1.15" fill="#f5a524" stroke="none"/><circle cx="9.5" cy="4.3" r="1.15" fill="#30a46c" stroke="none"/><circle cx="11.9" cy="6.7" r="1.15" fill="#3b82f6" stroke="none"/>',
    decks: '<polygon points="12 3 2 8.5 12 14 22 8.5 12 3"/><polyline points="2 13 12 18.5 22 13"/><polyline points="2 17.5 12 23 22 17.5"/>',
  };
  function navIcon(name){
    const s = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    const vb = name === 'colors' ? '0 0 16 16' : '0 0 24 24';
    s.setAttribute('width', '15'); s.setAttribute('height', '15'); s.setAttribute('viewBox', vb);
    s.setAttribute('fill', 'none'); s.setAttribute('stroke', 'currentColor');
    s.setAttribute('stroke-width', '1.7'); s.setAttribute('stroke-linecap', 'round'); s.setAttribute('stroke-linejoin', 'round');
    s.classList.add('dds-nav-ico');
    s.innerHTML = NAV_ICONS[name] || '';
    return s;
  }
  function secTitle(sec){
    const h = sec && sec.querySelector(':scope > h2');
    if (!h) return '';
    let t = '';
    h.childNodes.forEach(function(n){ if (n.nodeType === 3) t += n.textContent; });
    return t.trim();
  }
  let subSecs = [], subBtns = [];
  function syncSubNav(){
    if (!navEl || !mainEl) return;
    navEl.querySelectorAll('.dds-subnav').forEach(function(n){ n.remove(); });
    subSecs = []; subBtns = [];
    const active = navEl.querySelector('button[data-tab="' + S.tab + '"]');
    if (!active) return;
    const secs = Array.from(mainEl.querySelectorAll('.dds-sec')).filter(function(s){ return !!secTitle(s); });
    if (secs.length < 2) return;
    const box = el('div', 'dds-subnav');
    secs.forEach(function(sec, idx){
      const b = el('button', 'dds-subitem' + (idx === 0 ? ' on' : ''), secTitle(sec));
      b.onclick = function(){
        const y = Math.max(0, sec.offsetTop - 16);
        mainEl.scrollTo({top: y, behavior: 'smooth'});
        subBtns.forEach(function(x, i){ x.classList.toggle('on', i === idx); });
      };
      box.appendChild(b);
      subSecs.push(sec); subBtns.push(b);
    });
    active.parentNode.insertBefore(box, active.nextSibling);
    updateSubSpy();
  }
  function updateSubSpy(){
    if (!subSecs.length || !mainEl) return;
    const st = mainEl.scrollTop, atBottom = st + mainEl.clientHeight >= mainEl.scrollHeight - 8;
    let cur = 0;
    if (atBottom){ cur = subSecs.length - 1; }
    else {
      for (let i = 0; i < subSecs.length; i++){
        if (subSecs[i].offsetTop - 40 <= st) cur = i;
      }
    }
    subBtns.forEach(function(b, i){ b.classList.toggle('on', i === cur); });
  }
  function render(){
    if (!mainEl || !S.g) return;
    if (S.dragging) return;
    dropTips();  // (its icon is redrawn)
    // keep the field being typed in (and the scroll) across the redraw
    const a = document.activeElement, keep = a && a.dataset && a.dataset.keep;
    const sel = keep ? [a.selectionStart, a.selectionEnd] : null;
    const top = mainEl.scrollTop;
    // lists that scroll on their own (the theme grids) keep their place too
    const inner = {};
    mainEl.querySelectorAll('[data-keep-scroll]').forEach(function(n){ inner[n.dataset.keepScroll] = n.scrollTop; });
    navEl.querySelectorAll('button[data-tab]').forEach(function(b){ b.classList.toggle('on', b.dataset.tab === S.tab); });
    const page = S.tab === 'general' ? pageGeneral() : S.tab === 'spans' ? pageSpans() : S.tab === 'colors' ? pageColors() : pageDecks();
    if (mainEl.firstChild !== page){
      while (mainEl.firstChild) mainEl.removeChild(mainEl.firstChild);
      mainEl.appendChild(page);
    }
    mainEl.querySelectorAll('[data-keep-scroll]').forEach(function(n){
      const v = inner[n.dataset.keepScroll];
      if (v) n.scrollTop = v;
    });
    mainEl.scrollTop = top;
    syncSubNav();
    if (keep){
      const n = mainEl.querySelector('[data-keep="' + keep + '"]');
      if (n){ n.focus(); try { n.setSelectionRange(sel[0], sel[1]); } catch (e) {} }
    }
  }
  function showTab(name){
    const map = {general: 'general', 'time span': 'spans', time: 'spans', spans: 'spans', colors: 'colors', colours: 'colors', decks: 'decks'};
    const t = map[String(name || '').toLowerCase()];
    if (!t || t === S.tab) return;
    S.tab = t; S.form = null;
    render();
    mainEl.scrollTop = 0;
  }

  function setTheme(theme){
    document.documentElement.style.colorScheme = theme.is_dark ? 'dark' : 'light';
    document.documentElement.classList.toggle('dds-dark', !!theme.is_dark);
    document.documentElement.style.setProperty('--dds-scheme', theme.is_dark ? 'dark' : 'light');
    DD.setTheme(theme);
    // the text on the accent (Save, a switch's knob): dark on a light accent (Anki's own dark theme has a light gray one)
    document.documentElement.style.setProperty('--dds-on-accent', lightColor(theme.css && theme.css.accent) ? '#1b1b1d' : '#fff');
  }
  function lightColor(c){
    const m = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.exec(String(c || '').trim());
    if (!m) return false;
    let h = m[1];
    if (h.length === 3) h = h.replace(/./g, '$&$&');
    const n = parseInt(h, 16), r = n >> 16 & 255, g = n >> 8 & 255, bl = n & 255;
    return (0.299 * r + 0.587 * g + 0.114 * bl) > 165;
  }
  // (not 'theme': DD.setTheme announces itself under that name)
  DD.on('settings_theme', setTheme);
  DD.on('state', function(st){
    if (!st) return;
    S.g = st.general; S.spans = st.spans; S.colors = st.colors; S.backdrop = st.backdrop;
    render();
  });
  DD.on('show_tab', showTab);
  document.addEventListener('keydown', function(e){
    if (e.key === 'Escape' && S.form){ S.form = null; render(); }
  });
  // a slider let go outside the window: the page may be redrawn again
  document.addEventListener('pointerup', function(){ if (S.dragging){ S.dragging = false; } });

  // the controls, for the other pages drawn with this look (widget_settings.js)
  DD.settingsUI = {el: el, icon: icon, iconBtn: iconBtn, btn: btn, sw: sw, select: select, seg: seg, slider: slider,
                   numInput: numInput, textInput: textInput, field: field, section: section, tip: tip, dropTips: dropTips,
                   swatch: swatch, toast: toast, setTheme: setTheme, dragging: function(){ return S.dragging; }};

  DD.settingsBoot = function(){
    root = document.getElementById('dds-root');
    root.setAttribute('data-nt', '');
    DD.call('init').then(function(d){
      if (d.i18n) DD.setI18n(d.i18n, root);
      setTheme(d.theme);
      S.K = d.K || {}; S.dev = !!d.dev;
      S.g = d.general; S.spans = d.spans; S.colors = d.colors; S.backdrop = d.backdrop; S.decks = d.decks;
      const app = el('div', 'dds-app');
      navEl = el('nav', 'dds-nav');
      TABS.forEach(function(t){
        const b = el('button', 'dds-tab');
        b.dataset.tab = t[0];
        b.appendChild(navIcon(t[0]));
        b.appendChild(el('span', null, T(t[1])));
        b.onclick = function(){ showTab(t[0]); };
        navEl.appendChild(b);
      });
      mainEl = el('main', 'dds-main');
      mainEl.addEventListener('scroll', updateSubSpy, {passive: true});
      const foot = el('footer', 'dds-foot');
      foot.appendChild(btn(T('Cancel'), '', function(){ DD.call('cancel').catch(fail); }));
      foot.appendChild(btn(T('Save'), 'primary', function(){ DD.call('save').catch(fail); }));
      app.appendChild(navEl); app.appendChild(mainEl); app.appendChild(foot);
      root.appendChild(app);
      if (d.start) showTab(d.start);
      render();
    }).catch(function(e){ DD.log('settings: boot failed ' + e); root.textContent = String(e); });
  };
})();
