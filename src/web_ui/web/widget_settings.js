// A widget's settings (widget_settings.py), with the look of the web Settings (settings.js's controls): the widget
// type's options (widget_options.py), groups of switches, sliders, menus, colors, the text widget's sentence. A
// change is sent by its key (wo_set), a button by its name (wo_do); the page is drawn again from the state sent back.
// The text comes already translated from Python: the page is data-nt.
(function(){
  'use strict';
  let U = null, root = null, mainEl = null, footEl = null, ST = null;

  function fail(e){
    DD.log('widget settings: ' + e);
    if (U) U.toast(String(e && e.message || e));
  }
  const noColon = function(s){ return String(s || '').replace(/\s*[:：]\s*$/, ''); };
  function apply(st){
    if (st){ ST = st; render(); }
  }
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
      case 'texteditor': parent.appendChild(textEditor(n)); return;
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
  // cursor, its undo); each change written to the widget a moment after it is typed (the page not drawn again)
  const editors = {};
  function textEditor(n){
    let x = editors[n.key];
    if (!x){
      const wrap = U.el('div', 'dws-texted');
      wrap.style.cssText = 'display:flex;flex-direction:column;min-height:300px;margin:4px 0 8px';
      x = editors[n.key] = {wrap: wrap};
      x.ed = DD.textEditor(wrap, {template: n.v || '', onChange: function(t){
        DD.call('wo_set', {key: n.key, value: t}).catch(fail);
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
    schemaBlocks(ST.groups || [], mainEl);
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
      const press = function(){ odo(f.id); };
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
