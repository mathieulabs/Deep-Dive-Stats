// The Decks page of Settings (settings.py, settings.js): which decks count in the stats (a tree, a deck's subdecks following
// it), the deck names' colors, and the excluded days. Each change goes to Python at once (decks_set); it reaches the
// config when Settings is saved.
(function(){
  'use strict';
  const S = {decks: [], byId: {}, kids: {}, excluded: new Set(), colors: {}, dates: [], open: new Set(), filter: '',
             form: null};

  // ---- helpers ----
  function el(tag, cls, text){
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  const CHEV = '<svg width="10" height="10" viewBox="0 0 10 10"><path d="M3.5 1.5 7 5l-3.5 3.5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  function lang(){ return ((DD.i18n && DD.i18n['@lang']) || 'en').replace('_', '-'); }
  function fmtDay(iso){
    const p = String(iso).split('-').map(Number);
    if (p.length !== 3 || !p[0]) return iso;
    try { return new Intl.DateTimeFormat(lang(), {day: 'numeric', month: 'short', year: 'numeric'}).format(new Date(p[0], p[1] - 1, p[2])); }
    catch (e) { return iso; }
  }
  function isOn(id){ return !S.excluded.has(id); }
  function descendants(id){
    const out = [];
    (function walk(i){ (S.kids[i] || []).forEach(function(c){ out.push(c); walk(c); }); })(id);
    return out;
  }
  function save(what){
    const args = {};
    if (what.indexOf('excluded') >= 0) args.excluded = Array.from(S.excluded);
    if (what.indexOf('colors') >= 0) args.colors = S.colors;
    if (what.indexOf('dates') >= 0) args.dates = S.dates;
    DD.call('decks_set', args).catch(function(e){ DD.log('settings decks: save failed ' + e); });
  }

  // ---- a color dot and its reset ----
  const PALETTE = '<svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">' +
    '<path d="M8 1.6C4.4 1.6 1.6 4.3 1.6 7.6c0 3.3 2.8 6.3 6.2 6.3 1.1 0 1.6-.6 1.6-1.3 0-.8-.6-1.1-.6-1.9 0-.7.6-1.2 1.3-1.2h1.5c1.6 0 2.8-1.3 2.8-2.9C14.4 3.9 11.6 1.6 8 1.6z" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linejoin="round"/>' +
    '<circle cx="4.7" cy="7.7" r="1.15" fill="#e5484d"/><circle cx="6.1" cy="4.7" r="1.15" fill="#f5a524"/>' +
    '<circle cx="9.5" cy="4.3" r="1.15" fill="#30a46c"/><circle cx="11.9" cy="6.7" r="1.15" fill="#3b82f6"/></svg>';
  function colorCtl(key, nameEl){
    const box = el('span', 'dds-color');
    const dot = el('button', 'dds-dot'), x = el('button', 'dds-x');
    // no color yet: a palette says the dot picks one; the reset is an arrow, at the end of the row (the name stays put)
    dot.innerHTML = PALETTE;
    if (DD.settingsIcon) x.appendChild(DD.settingsIcon('reset')); else x.textContent = '×';
    function show(){
      const c = S.colors[key];
      dot.classList.toggle('auto', !c);
      dot.style.background = c || 'transparent';
      x.classList.toggle('set', !!c);
      if (nameEl) nameEl.style.color = c || '';
    }
    dot.title = DD.t('Color of the name in the table. Click to pick one.');
    x.title = DD.t('Reset to default color');
    dot.onclick = function(){ DD.call('pick', {what: 'deck', key: key}); };
    x.onclick = function(){ delete S.colors[key]; show(); save(['colors']); };
    box._show = show;
    box._x = x;
    box.appendChild(dot);
    show();
    return box;
  }
  const colorBoxes = {};
  DD.on('color_picked', function(p){
    if (!p || !p.key) return;
    S.colors[p.key] = p.color;
    (colorBoxes[p.key] || []).forEach(function(b){ b._show(); });
    save(['colors']);
  });

  // ---- the deck tree ----
  function visibleRows(){
    const f = S.filter.trim().toLowerCase();
    if (f){
      const keep = new Set();
      S.decks.forEach(function(d){
        if (d.path.toLowerCase().indexOf(f) < 0) return;
        keep.add(d.id);
        for (let p = d.parent; p != null; p = S.byId[p] ? S.byId[p].parent : null) keep.add(p);
      });
      return S.decks.filter(function(d){ return keep.has(d.id); });
    }
    return S.decks.filter(function(d){
      for (let p = d.parent; p != null; p = S.byId[p] ? S.byId[p].parent : null) if (!S.open.has(p)) return false;
      return true;
    });
  }
  function deckRow(d, filtering){
    const row = el('div', 'dds-row' + (isOn(d.id) ? '' : ' off'));
    row.style.paddingLeft = (6 + d.depth * 18) + 'px';
    const hasKids = (S.kids[d.id] || []).length > 0;
    const chev = el('button', 'dds-chev' + (hasKids ? '' : ' none') + (filtering || S.open.has(d.id) ? ' open' : ''));
    chev.innerHTML = CHEV;
    if (hasKids && !filtering) chev.onclick = function(){ S.open.has(d.id) ? S.open.delete(d.id) : S.open.add(d.id); renderTree(); };
    const sw = el('button', 'dds-sw' + (isOn(d.id) ? ' on' : ''));
    sw.title = isOn(d.id) ? DD.t('In the stats. Click to leave it out (its subdecks too).') : DD.t('Left out of the stats. Click to count it again (its subdecks too).');
    sw.onclick = function(){
      const on = !isOn(d.id);
      [d.id].concat(descendants(d.id)).forEach(function(i){ if (on) S.excluded.delete(i); else S.excluded.add(i); });
      save(['excluded']); renderTree();
    };
    const name = el('span', 'dds-name', d.name);
    name.setAttribute('data-nt', '');
    name.title = d.path;
    const color = colorCtl(String(d.id), name);
    (colorBoxes[String(d.id)] = colorBoxes[String(d.id)] || []).push(color);
    row.appendChild(chev); row.appendChild(sw); row.appendChild(color); row.appendChild(name); row.appendChild(color._x);
    // a deck counted with some of its subdecks left out: said beside it (they are hidden when it is folded)
    if (isOn(d.id) && hasKids){
      const offN = descendants(d.id).filter(function(i){ return !isOn(i); }).length;
      if (offN) row.appendChild(el('span', 'dds-tag warn', DD.tn('{n} subdeck left out', '{n} subdecks left out', offN)));
    }
    if (d.filtered) row.appendChild(el('span', 'dds-tag', DD.t('Filtered')));
    row.appendChild(el('span', 'dds-count', DD.tn('{n} card', '{n} cards', d.cards, {n: d.cards.toLocaleString(lang())})));
    return row;
  }
  let treeEl = null;
  function renderTree(){
    if (!treeEl) return;
    const top = treeEl.scrollTop;
    treeEl.innerHTML = '';
    Object.keys(colorBoxes).forEach(function(k){ if (k !== 'total' && k !== 'deleted') delete colorBoxes[k]; });
    const filtering = !!S.filter.trim();
    const rows = visibleRows();
    if (!rows.length) treeEl.appendChild(el('div', 'dds-empty', DD.t('No deck matches.')));
    rows.forEach(function(d){ treeEl.appendChild(deckRow(d, filtering)); });
    treeEl.scrollTop = top;
  }

  function decksSection(){
    const sec = el('section', 'dds-sec');
    const h = el('h2', null, DD.t('Decks in the stats'));
    if (DD.settingsTip) DD.settingsTip(h, DD.t('Turn a deck off to leave its cards and reviews out of every stat. Its subdecks follow it. The dot is the color of the deck\'s name in the table.'));
    sec.appendChild(h);
    const bar = el('div', 'dds-bar');
    const search = el('input', 'dds-input');
    search.placeholder = DD.t('Filter decks...');
    search.oninput = function(){ S.filter = search.value; renderTree(); };
    const openAll = el('button', 'dds-link', DD.t('Expand all')), closeAll = el('button', 'dds-link', DD.t('Collapse all'));
    openAll.onclick = function(){ S.decks.forEach(function(d){ if ((S.kids[d.id] || []).length) S.open.add(d.id); }); renderTree(); };
    closeAll.onclick = function(){ S.open.clear(); renderTree(); };
    bar.appendChild(search); bar.appendChild(openAll); bar.appendChild(closeAll);
    sec.appendChild(bar);
    treeEl = el('div', 'dds-tree');
    sec.appendChild(treeEl);
    renderTree();
    return sec;
  }

  // ---- Total and deleted cards: rows of the stats that are not decks ----
  function otherSection(){
    const sec = el('section', 'dds-sec');
    const h = el('h2', null, DD.t('All decks and deleted cards'));
    if (DD.settingsTip) DD.settingsTip(h, DD.t('Rows of the table that are not decks: all decks together, and the reviews of cards deleted since.'));
    sec.appendChild(h);
    const tree = el('div', 'dds-tree');
    [['total', DD.t('Total'), false], ['deleted', DD.t('Deleted Cards'), true]].forEach(function(o){
      const row = el('div', 'dds-row' + (o[2] && S.excluded.has('deleted') ? ' off' : ''));
      row.appendChild(el('span', 'dds-chev none'));
      // (Total has no switch: all decks together, always shown)
      const sw = o[2] ? el('button', 'dds-sw' + (!S.excluded.has('deleted') ? ' on' : '')) : el('span', 'dds-nosw');
      if (o[2]) sw.onclick = function(){
        S.excluded.has('deleted') ? S.excluded.delete('deleted') : S.excluded.add('deleted');
        sw.classList.toggle('on', !S.excluded.has('deleted')); row.classList.toggle('off', S.excluded.has('deleted'));
        save(['excluded']);
      };
      const name = el('span', 'dds-name', o[1]);
      const color = colorCtl(o[0], name);
      colorBoxes[o[0]] = [color];
      row.appendChild(sw); row.appendChild(color); row.appendChild(name); row.appendChild(color._x);
      tree.appendChild(row);
    });
    sec.appendChild(tree);
    return sec;
  }

  // ---- excluded days ----
  function ruleParts(entry){
    const dates = typeof entry === 'string' ? entry : ((entry && entry.dates) || '');
    const decks = (entry && typeof entry === 'object' && entry.decks) || [];
    const ab = dates.split('..');
    return {from: ab[0] || '', to: ab[1] || '', decks: decks.map(Number)};
  }
  function ruleWhen(r){ return r.to && r.to !== r.from ? fmtDay(r.from) + ' – ' + fmtDay(r.to) : fmtDay(r.from); }
  function ruleWhat(r){
    if (!r.decks.length) return DD.t('All decks');
    const names = r.decks.map(function(i){ return S.byId[i] ? S.byId[i].path : '#' + i; });
    return DD.tn('{n} deck', '{n} decks', names.length) + ': ' + names.join(', ');
  }
  let datesEl = null;
  function renderDates(){
    if (!datesEl) return;
    datesEl.innerHTML = '';
    const list = el('div', 'dds-rules');
    if (!S.dates.length && !S.form) list.appendChild(el('div', 'dds-empty', DD.t('No excluded days.')));
    S.dates.forEach(function(entry, i){
      if (S.form && S.form.index === i){ list.appendChild(formEl()); return; }
      const r = ruleParts(entry), row = el('div', 'dds-rule');
      row.appendChild(el('span', 'dds-rule-when', ruleWhen(r)));
      const what = el('span', 'dds-rule-what', ruleWhat(r));
      what.setAttribute('data-nt', ''); what.title = what.textContent;
      row.appendChild(what);
      const edit = el('button', 'dds-btn small', DD.t('Edit')), rm = el('button', 'dds-btn small', DD.t('Remove'));
      edit.onclick = function(){ S.form = Object.assign({index: i}, r, {some: r.decks.length > 0, pick: new Set(r.decks), find: ''}); renderDates(); };
      rm.onclick = function(){ S.dates.splice(i, 1); if (S.form && S.form.index > i) S.form.index--; save(['dates']); renderDates(); };
      row.appendChild(edit); row.appendChild(rm);
      list.appendChild(row);
    });
    if (S.form && S.form.index == null) list.appendChild(formEl());
    datesEl.appendChild(list);
    if (!S.form){
      const add = el('button', 'dds-btn', '+ ' + DD.t('Add a day or a period'));
      add.onclick = function(){
        const t = new Date(), iso = t.getFullYear() + '-' + ('0' + (t.getMonth() + 1)).slice(-2) + '-' + ('0' + t.getDate()).slice(-2);
        S.form = {index: null, from: iso, to: '', some: false, pick: new Set(), find: ''}; renderDates();
      };
      datesEl.appendChild(add);
    }
  }
  function formEl(){
    const F = S.form, box = el('div', 'dds-form');
    const r1 = el('div', 'dds-form-row');
    r1.appendChild(el('label', null, DD.t('From')));
    const from = el('input'); from.type = 'date'; from.value = F.from; from.oninput = function(){ F.from = from.value; };
    r1.appendChild(from);
    r1.appendChild(el('label', null, DD.t('To (optional)')));
    const to = el('input'); to.type = 'date'; to.value = F.to; to.oninput = function(){ F.to = to.value; };
    r1.appendChild(to);
    box.appendChild(r1);
    const r2 = el('div', 'dds-form-row');
    r2.appendChild(el('label', null, DD.t('Applies to')));
    const seg = el('span', 'dds-seg');
    const all = el('button', F.some ? '' : 'on', DD.t('All decks')), some = el('button', F.some ? 'on' : '', DD.t('Some decks'));
    all.onclick = function(){ F.some = false; renderDates(); };
    some.onclick = function(){ F.some = true; renderDates(); };
    seg.appendChild(all); seg.appendChild(some);
    r2.appendChild(seg);
    box.appendChild(r2);
    if (F.some){
      const find = el('input', 'dds-input');
      find.placeholder = DD.t('Filter decks...'); find.value = F.find; find.style.marginBottom = '6px'; find.style.width = '100%';
      const pick = el('div', 'dds-pick');
      function fill(){
        pick.innerHTML = '';
        const f = F.find.trim().toLowerCase();
        S.decks.forEach(function(d){
          if (f && d.path.toLowerCase().indexOf(f) < 0) return;
          const lab = el('label'); lab.style.paddingLeft = (10 + (f ? 0 : d.depth * 16)) + 'px';
          const cb = el('input'); cb.type = 'checkbox'; cb.checked = F.pick.has(d.id);
          cb.onchange = function(){ cb.checked ? F.pick.add(d.id) : F.pick.delete(d.id); };
          const nm = el('span', null, f ? d.path : d.name); nm.setAttribute('data-nt', ''); nm.title = d.path;
          lab.appendChild(cb); lab.appendChild(nm);
          pick.appendChild(lab);
        });
      }
      find.oninput = function(){ F.find = find.value; fill(); };
      fill();
      box.appendChild(find); box.appendChild(pick);
    }
    const act = el('div', 'dds-actions');
    const err = el('span', 'dds-err');
    const cancel = el('button', 'dds-btn', DD.t('Cancel')), ok = el('button', 'dds-btn primary', F.index == null ? DD.t('Add') : DD.t('Save'));
    cancel.onclick = function(){ S.form = null; renderDates(); };
    ok.onclick = function(){
      if (!/^\d{4}-\d{2}-\d{2}$/.test(F.from)){ err.textContent = DD.t('Pick the first day.'); return; }
      if (F.to && !/^\d{4}-\d{2}-\d{2}$/.test(F.to)){ err.textContent = DD.t('Pick the first day.'); return; }
      if (F.to && F.to < F.from){ err.textContent = DD.t('The last day is before the first one.'); return; }
      const decks = F.some ? Array.from(F.pick) : [];
      if (F.some && !decks.length){ err.textContent = DD.t('Pick at least one deck.'); return; }
      const dates = F.to && F.to !== F.from ? F.from + '..' + F.to : F.from;
      const entry = decks.length ? {dates: dates, decks: decks} : dates;
      if (F.index == null) S.dates.push(entry); else S.dates[F.index] = entry;
      S.form = null; save(['dates']); renderDates();
    };
    act.appendChild(err); act.appendChild(cancel); act.appendChild(ok);
    box.appendChild(act);
    return box;
  }
  function datesSection(){
    const sec = el('section', 'dds-sec');
    const h = el('h2', null, DD.t('Excluded days'));
    if (DD.settingsTip) DD.settingsTip(h, DD.t('Reviews done on these days are left out of the stats, for all decks or only some. A day starts at your Anki rollover hour.'));
    sec.appendChild(h);
    datesEl = el('div');
    sec.appendChild(datesEl);
    renderDates();
    return sec;
  }

  // ---- the Decks page of Settings (settings.js): built once, it keeps its own state ----
  DD.decksPage = function(d){
    d = d || {};
    S.decks = d.decks || [];
    S.decks.forEach(function(x){
      S.byId[x.id] = x;
      if (x.parent != null) (S.kids[x.parent] = S.kids[x.parent] || []).push(x.id);
    });
    S.excluded = new Set((d.excluded || []).map(function(x){ return x === 'deleted' ? x : Number(x); }));
    S.colors = Object.assign({}, d.colors || {});
    S.dates = (d.dates || []).slice();
    // a short list opens whole; a long one shows its top decks
    if (S.decks.length <= 30) S.decks.forEach(function(x){ if ((S.kids[x.id] || []).length) S.open.add(x.id); });
    const page = el('div', 'dds-page');
    page.appendChild(decksSection());
    page.appendChild(otherSection());
    page.appendChild(datesSection());
    return page;
  };
})();
