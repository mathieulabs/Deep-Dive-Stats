// The decks a widget reads: a dialog inside the page, over it. Rows from deck_tree()
// (deck_picker.py, through the page's 'decks_tree' handler), checked one by one (a deck does not check its subdecks),
// and a row for the deleted cards.
//   DD.pickDecks({ids}) -> Promise: {ids} once saved (null: the deck shown, everything checked; []: every deck
//   but not the deleted cards; else the ids checked and/or "deleted"), or null when cancelled.
// Needs settings.js (DD.settingsUI) and a #dds-root.
(function(){
  'use strict';
  const DELETED = 'deleted';
  let tree = null;  // the decks, read once per page

  function lang(){ return ((DD.i18n && DD.i18n['@lang']) || 'en').replace('_', '-'); }

  DD.pickDecks = function(opts){
    opts = opts || {};
    const U = DD.settingsUI, el = U.el, T = DD.t;
    const host = document.getElementById('dds-root') || document.body;
    const load = tree ? Promise.resolve(tree) : DD.call('decks_tree').then(function(d){ tree = d || []; return tree; });
    return load.then(function(decks){
      return new Promise(function(resolve){
        const all = opts.ids == null;
        const allNoDel = Array.isArray(opts.ids) && opts.ids.length === 0;
        const on = new Set(all ? [DELETED].concat(decks.map(function(d){ return String(d.id); }))
                               : allNoDel ? decks.map(function(d){ return String(d.id); })
                               : opts.ids.map(String));
        const veil = el('div', 'ddk-veil');
        const box = el('div', 'ddk-box');
        box.setAttribute('role', 'dialog');
        veil.appendChild(box);
        box.appendChild(el('h2', 'ddk-title', opts.title || T('Select Decks')));
        box.appendChild(el('div', 'ddk-intro', opts.intro || T('Choose which decks provide data for this graph.')));
        const search = el('input', 'dds-input ddk-search');
        search.type = 'search';
        search.placeholder = T('Filter decks...');
        box.appendChild(search);
        const list = el('div', 'dds-tree ddk-tree');
        box.appendChild(list);
        const foot = el('div', 'dds-actions ddk-foot');
        const bulk = U.btn('', 'ddk-bulk', function(){
          const every = rows.every(function(r){ return on.has(r.key); });
          rows.forEach(function(r){ if (every) on.delete(r.key); else on.add(r.key); });
          show();
        });
        foot.appendChild(bulk);
        foot.appendChild(el('span', 'ddk-gap'));
        foot.appendChild(U.btn(T('Cancel'), '', function(){ close(null); }));
        const save = U.btn(T('Save'), 'primary', function(){ close({ids: result()}); });
        foot.appendChild(save);
        box.appendChild(foot);

        const rows = [];
        function row(key, label, depth, cls, count){
          const r = el('label', 'dds-row ddk-row' + (cls ? ' ' + cls : ''));
          r.style.paddingLeft = (10 + depth * 18) + 'px';
          const ck = el('input', 'ddk-ck');
          ck.type = 'checkbox';
          ck.onchange = function(){ if (ck.checked) on.add(key); else on.delete(key); show(); };
          r.appendChild(ck);
          r.appendChild(el('span', 'dds-name', label));
          if (count != null) r.appendChild(el('span', 'dds-count', Number(count).toLocaleString(lang())));
          list.appendChild(r);
          const x = {key: key, el: r, ck: ck, find: (label + ' ' + (cls === 'ddk-del' ? '' : key)).toLowerCase()};
          rows.push(x);
          return x;
        }
        row(DELETED, T('Deleted / removed cards'), 0, 'ddk-del', null);
        list.appendChild(el('div', 'ddk-sep'));
        decks.forEach(function(d){
          const x = row(String(d.id), d.name, d.depth, d.filtered ? 'ddk-dyn' : '', d.cards);
          x.find = String(d.path).toLowerCase();
          x.el.title = d.path;
        });

        function show(){
          rows.forEach(function(r){ r.ck.checked = on.has(r.key); });
          const every = rows.every(function(r){ return on.has(r.key); });
          bulk.textContent = every ? T('Deselect all') : T('Select all');
          save.disabled = !rows.some(function(r){ return on.has(r.key); });
        }
        function filter(){
          const words = search.value.toLowerCase().split(/\s+/).filter(Boolean);
          rows.forEach(function(r){
            r.el.style.display = words.every(function(w){ return r.find.indexOf(w) >= 0; }) ? '' : 'none';
          });
        }
        search.oninput = filter;
        // saved as: everything checked, the deck shown; every deck without the deleted cards, []
        function result(){
          const ids = decks.map(function(d){ return String(d.id); });
          const decksAll = ids.every(function(i){ return on.has(i); });
          if (decksAll && on.has(DELETED)) return null;
          if (decksAll) return [];
          const out = on.has(DELETED) ? [DELETED] : [];
          return out.concat(ids.filter(function(i){ return on.has(i); }));
        }
        function key(e){
          if (e.key === 'Escape'){ e.preventDefault(); e.stopPropagation(); close(null); }
        }
        function close(v){
          document.removeEventListener('keydown', key, true);
          veil.remove();
          resolve(v);
        }
        veil.addEventListener('mousedown', function(e){ if (e.target === veil) close(null); });
        document.addEventListener('keydown', key, true);
        show();
        host.appendChild(veil);
        search.focus();
      });
    });
  };
})();
