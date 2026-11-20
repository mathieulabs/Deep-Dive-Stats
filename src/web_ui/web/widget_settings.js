// A widget's settings (widget_settings.py), with the look of the web Settings (settings.js's controls). Two kinds of
// state come from Python:
//  - schema: the widget type's options (widget_options.py), groups of switches, sliders, menus, colors. A change is
//    sent by its key (wo_set), a button by its name (wo_do); the page is drawn again from the state sent back;
//  - else: the controls of the Qt settings dialog, kept hidden in Python (the types not converted yet). Each change
//    goes back to the Qt control it stands for (ws_set / ws_click).
// The text comes already translated from Python: the page is data-nt.
(function(){
  'use strict';
  let U = null, root = null, mainEl = null, footEl = null, ST = null, titleEl = null;

  function fail(e){
    DD.log('widget settings: ' + e);
    if (U) U.toast(String(e && e.message || e));
  }
  const noColon = function(s){ return String(s || '').replace(/\s*[:：]\s*$/, ''); };
  function apply(st){
    if (st){ ST = st; render(); }
  }
  function setv(id, value){ return DD.call('ws_set', {id: id, value: value}).then(apply).catch(fail); }
  function click(id){ return DD.call('ws_click', {id: id}).catch(fail); }

  // ---- one control ----
  function control(n){
    const el = U.el;
    switch (n.t){
      case 'check': return U.sw(n.on, function(v){ setv(n.id, v); }, !n.en);
      case 'slider': return slider(n);
      case 'combo': return U.select(n.i, n.opts, function(v){ setv(n.id, Number(v)); }, !n.en);
      case 'text': {
        const t = U.textInput(n.v, function(v){ setv(n.id, v); }, {placeholder: n.ph, id: n.id});
        t.disabled = !n.en;
        return t;
      }
      case 'num': {
        const box = el('span', 'dws-num');
        box.appendChild(U.numInput(n.v, n.min, n.max, function(v){ setv(n.id, v); }, !n.en));
        if (n.suffix && n.suffix.trim()) box.appendChild(el('span', 'dws-unit', n.suffix.trim()));
        return box;
      }
      case 'button': {
        const b = U.btn(n.text, 'small', function(){ click(n.id); }, n.tip || null);
        b.disabled = !n.en;
        return b;
      }
      case 'icon': {
        const b = U.iconBtn('dds-x set dws-icon', n.icon, n.tip || null);
        b.disabled = !n.en;
        b.onclick = function(){ click(n.id); };
        return b;
      }
      case 'swatch': {
        const b = U.swatch(n.color, function(){ click(n.id); }, n.tip || null);
        b.disabled = !n.en;
        return b;
      }
      case 'strip': {
        const d = el('span', 'dws-strip');
        d.style.backgroundImage = n.css;  // (the image under the border too: else its start shows again there)
        if (n.tip) d.title = n.tip;
        return d;
      }
      case 'pic': {
        const img = el('img', 'dws-pic');
        img.src = n.src; img.width = n.w; img.height = n.h;
        return img;
      }
      case 'label': return el('span', 'dws-text', n.text);
    }
    return null;
  }
  function slider(n){
    const fmt = function(v){ return v + (n.suffix || ''); };
    return U.slider(n.v, n.min, n.max, n.step, fmt, function(v){ setv(n.id, v); }, !n.en);
  }

  // ---- the blocks: a setting per line, its name on the left ----
  function flat(items){
    const out = [];
    items.forEach(function(n){
      if (n.t === 'row' || n.t === 'box') flat(n.items).forEach(function(m){ out.push(m); });
      else out.push(n);
    });
    return out;
  }
  // a row of the dialog: a label names the controls after it; a switch or a slider is a line of its own
  function row(items, parent){
    let label = null, tipText = '', ctrls = [];
    function flush(){
      if (label !== null || ctrls.length){
        // the arrow back to the default before what it resets: the swatch / field keeps its place when it is gone
        const resets = ctrls.filter(function(c){ return c.n.t === 'icon' && c.n.icon === 'reset'; });
        const others = ctrls.filter(function(c){ return resets.indexOf(c) < 0; });
        const els = resets.concat(others).map(function(c){ return c.e; }).filter(Boolean);
        const wide = ctrls.some(function(c){ return c.n.t === 'strip'; });
        const f = U.field(noColon(label || ''), tipText || null, els, {off: ctrls.length && ctrls.every(function(c){ return c.n.en === false; })});
        if (wide) f.classList.add('dws-wide');
        parent.appendChild(f);
      }
      label = null; tipText = ''; ctrls = [];
    }
    flat(items).forEach(function(n){
      if (n.t === 'label'){
        flush();
        label = n.text; tipText = n.tip || '';
      } else if (n.t === 'check' || n.t === 'slider'){
        if (label !== null && !ctrls.length && n.t === 'slider'){ ctrls.push({n: n, e: slider(n)}); flush(); return; }
        flush();
        block(n, parent);
      } else if (n.t === 'group' || n.t === 'texteditor'){
        flush();
        block(n, parent);
      } else {
        if (n.tip && !tipText && n.t !== 'icon' && n.t !== 'swatch' && n.t !== 'button' && n.t !== 'strip') tipText = n.tip;
        ctrls.push({n: n, e: control(n)});
      }
    });
    flush();
  }
  function block(n, parent){
    const el = U.el;
    if (n.t === 'group'){
      const sec = U.section(n.title, n.tip || null);
      sec.dataset.id = n.id;
      blocks(n.items, sec);
      parent.appendChild(sec);
    } else if (n.t === 'check'){
      parent.appendChild(U.field(n.label, n.tip || null, control(n), {off: !n.en}));
    } else if (n.t === 'slider'){
      parent.appendChild(U.field(noColon(n.label), n.tip || null, slider(n), {off: !n.en}));
    } else if (n.t === 'label'){
      const p = el('p', 'dws-note', n.text);
      parent.appendChild(p);
    } else if (n.t === 'texteditor'){
      parent.appendChild(textEditor(n));
    } else if (n.t === 'box'){
      n.items.forEach(function(m){ block(m, parent); });  // (lines one under the other)
    } else if (n.t === 'row'){
      row(n.items, parent);
    } else {
      row([n], parent);
    }
  }
  function blocks(items, parent){
    // the lines outside a group (the "Own style" switch and its note) sit together in a box of their own
    let loose = null;
    items.forEach(function(n){
      if (parent === mainEl && n.t !== 'group'){
        if (!loose){ loose = U.section(null, null); loose.classList.add('dws-loose'); parent.appendChild(loose); }
        block(n, loose);
        return;
      }
      loose = null;
      block(n, parent);
    });
  }

  // ---- the page drawn from the option schema ----
  function oset(key, value){ return DD.call('wo_set', {key: key, value: value}).then(apply).catch(fail); }
  function odo(act, key){
    return DD.call('wo_do', {act: act, key: key || null}).then(function(st){ if (st && st.groups) apply(st); }).catch(fail);
  }
  function resetIcon(tipText, onclick){
    const b = U.iconBtn('dds-x set dws-icon', 'reset', tipText || null);
    b.onclick = onclick;
    return b;
  }
  function option(n, parent){
    const el = U.el, off = n.en === false;
    let ctl = null;
    switch (n.kind){
      case 'note': parent.appendChild(el('p', 'dws-note', n.text)); return;
      case 'switch': ctl = U.sw(!!n.v, function(v){ oset(n.key, v); }, off); break;
      case 'slider':
        ctl = U.slider(n.v, n.min, n.max, n.step || 1, function(v){ return v + (n.suffix || ''); },
                       function(v){ oset(n.key, v); }, off);
        break;
      case 'select': ctl = U.select(n.v, n.opts || [], function(v){ oset(n.key, v); }, off); break;
      case 'text': {
        const t = U.textInput(n.v, function(v){ oset(n.key, v); }, {placeholder: n.ph, id: n.key});
        t.disabled = off;
        // the arrow back to the default before the field: the field keeps its place when it is gone
        ctl = n.reset ? [resetIcon(n.reset_tip, function(){ odo('reset_label', n.key); }), t] : t;
        break;
      }
      case 'color': {
        const sw = U.swatch(n.color, function(){ odo('pick', n.key); }, null);
        sw.disabled = off;
        ctl = n.reset ? [resetIcon(n.reset_tip, function(){ odo('reset_color', n.key); }), sw] : sw;
        break;
      }
      case 'ranges': ranges(n, parent); return;
      case 'palette': palette(n, parent); return;
    }
    if (ctl) parent.appendChild(U.field(noColon(n.label), n.tip || null, ctl, {off: off}));
  }
  // the Range Buttons: a line per button (a preset, or Custom with its number), x to remove one, + to add one; the
  // whole list is sent at each change (written to the chart on Save)
  const CUSTOM = '__custom__';
  function ranges(n, parent){
    const el = U.el;
    const rows = (n.v || []).map(function(r){ return {pick: r.pick, n: r.n, u: r.u}; });
    const send = function(){ oset(n.key, rows); };
    rows.forEach(function(r, i){
      const ctl = [U.select(r.pick, n.opts || [], function(v){ r.pick = v; send(); })];
      if (r.pick === CUSTOM){
        const box = el('span', 'dws-num');
        box.appendChild(U.numInput(r.n, 1, n.nmax[r.u] || 9999, function(v){ r.n = v; send(); }));
        if (n.rkind === 'fsrs'){
          box.appendChild(U.select(r.u, n.units, function(v){ r.u = v; r.n = Math.min(r.n, n.nmax[v] || r.n); send(); }));
        } else {
          box.appendChild(el('span', 'dws-unit', n.day_unit));
        }
        ctl.push(box);
      }
      const rm = U.iconBtn('dds-x set dws-icon', 'x', n.remove);
      rm.disabled = rows.length <= n.min;
      rm.onclick = function(){ if (rows.length > n.min){ rows.splice(i, 1); send(); } };
      ctl.push(rm);
      parent.appendChild(U.field(noColon(n.btn[i] || ''), null, ctl));
    });
    const foot = el('div');
    foot.style.cssText = 'display:flex;justify-content:flex-end;padding-top:6px';
    const add = U.btn(n.add, 'small', function(){
      if (rows.length >= n.max) return;
      // the first preset not used yet
      const used = rows.map(function(r){ return String(r.pick); });
      const free = (n.opts || []).filter(function(o){ return o[0] !== CUSTOM && used.indexOf(String(o[0])) < 0; })[0];
      rows.push({pick: free ? free[0] : n.opts[0][0], n: 30, u: 'd'});
      send();
    });
    add.disabled = rows.length >= n.max;
    foot.appendChild(add);
    parent.appendChild(foot);
  }
  // the heatmap's palette: the presets and the user's gradients, a new one; the chosen gradient's name, its colors as a
  // strip (- / + a color), a swatch per color
  function palette(n, parent){
    const el = U.el, g = n.grad;
    const sel = U.select(n.v, n.opts || [], function(v){ oset(n.key, {pick: v}); });
    const nb = U.btn(n.new, 'small', function(){ odo('hm_new'); }, n.new_tip || null);
    parent.appendChild(U.field(noColon(n.label), n.tip || null, [sel, nb]));
    if (!g) return;
    const name = U.textInput(g.name, function(v){ oset(n.key, {name: v}); }, {id: 'hm_name'});
    const del = U.btn(g.del, 'small', function(){ odo('hm_del'); });
    parent.appendChild(U.field(noColon(g.name_label), null, [name, del]));
    const strip = el('span', 'dws-strip');
    const cols = g.colors.map(function(c){ return c.color; });
    strip.style.backgroundImage = 'linear-gradient(to right, ' + (cols.length > 1 ? cols.join(', ') : cols[0] + ', ' + cols[0]) + ')';
    strip.title = g.strip_tip || '';
    const rem = U.btn('−', 'small', function(){ odo('hm_rem'); }, g.rem_tip);
    rem.disabled = !g.rem;
    const add = U.btn('+', 'small', function(){ odo('hm_add'); }, g.add_tip);
    add.disabled = !g.add;
    const f = U.field('', null, [strip, rem, add]);
    f.classList.add('dws-wide');
    parent.appendChild(f);
    g.colors.forEach(function(c, i){
      parent.appendChild(U.field(c.label, null, U.swatch(c.color, function(){ odo('pick', 'hmc:' + i); }, null)));
    });
  }
  function schemaBlocks(groups, parent){
    groups.forEach(function(g){
      if (!g.items || !g.items.length) return;
      const sec = U.section(g.title || null, g.tip || null);
      if (!g.title) sec.classList.add('dws-loose');  // (the "Own style" switch and its note)
      sec.dataset.id = g.id;
      g.items.forEach(function(n){ option(n, sec); });
      parent.appendChild(sec);
    });
  }

  // the text widget's sentence (text_editor.js): one editor for the window, kept as the page is drawn again (its
  // cursor, its undo); each change written to the widget a moment after it is typed
  const editors = {};
  function textEditor(n){
    let x = editors[n.id];
    if (!x){
      const wrap = U.el('div', 'dws-texted');
      wrap.style.cssText = 'display:flex;flex-direction:column;min-height:300px;margin:4px 0 8px';
      x = editors[n.id] = {wrap: wrap};
      x.ed = DD.textEditor(wrap, {template: n.v || '', onChange: function(t){
        DD.call('ws_text', {value: t}).catch(fail);
      }});
    }
    return x.wrap;
  }

  // ---- the window ----
  function render(){
    if (!mainEl || !ST) return;
    if (U.dragging()) return;
    U.dropTips();
    const a = document.activeElement, keep = a && a.dataset && a.dataset.keep;
    const sel = keep ? [a.selectionStart, a.selectionEnd] : null;
    const top = mainEl.scrollTop;
    // the text editor's cursor (moving the editor in the page takes its focus)
    const ws = window.getSelection(), inText = a && a.closest && a.closest('.dws-texted');
    const textRange = inText && ws.rangeCount ? ws.getRangeAt(0).cloneRange() : null;
    while (mainEl.firstChild) mainEl.removeChild(mainEl.firstChild);
    if (ST.schema) schemaBlocks(ST.groups || [], mainEl);
    else blocks(ST.items || [], mainEl);
    mainEl.scrollTop = top;
    if (keep){
      const n = mainEl.querySelector('[data-keep="' + keep + '"]');
      if (n){ n.focus(); try { n.setSelectionRange(sel[0], sel[1]); } catch (e) {} }
    }
    if (inText && inText.isConnected){
      a.focus();
      if (textRange){ ws.removeAllRanges(); ws.addRange(textRange); }
    }
    while (footEl.firstChild) footEl.removeChild(footEl.firstChild);
    (ST.foot || []).forEach(function(f){
      let b;
      const press = ST.schema ? function(){ odo(f.id); } : function(){ click(f.id); };
      if (f.role === 'reset'){
        b = U.btn('', 'dws-reset', press);
        b.appendChild(U.icon('reset'));
        b.appendChild(document.createTextNode(f.text));
      } else {
        b = U.btn(f.text, f.role === 'save' ? 'primary' : '', press);
      }
      b.disabled = f.en === false;
      footEl.appendChild(b);
    });
  }

  DD.on('ws_state', apply);
  DD.widgetSettingsBoot = function(){
    U = DD.settingsUI;
    root = document.getElementById('dds-root');
    root.setAttribute('data-nt', '');
    DD.call('init').then(function(d){
      if (d.i18n) DD.setI18n(d.i18n, root);
      U.setTheme(d.theme);
      ST = d.state;
      const app = U.el('div', 'dws-app');
      mainEl = U.el('main', 'dds-main dws-main');
      footEl = U.el('footer', 'dds-foot dws-foot');
      app.appendChild(mainEl); app.appendChild(footEl);
      root.appendChild(app);
      render();
      if (d.focus){
        const sec = mainEl.querySelector('[data-id="' + d.focus + '"]');
        if (sec) mainEl.scrollTop = Math.max(0, sec.offsetTop - 16);
      }
    }).catch(function(e){ DD.log('widget settings: boot failed ' + e); root.textContent = String(e); });
  };
})();
