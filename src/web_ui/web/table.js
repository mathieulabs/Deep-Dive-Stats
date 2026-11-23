// The deck table (drawer under the cards): header, Total row, the deck tree, the time-span tabs.
// Python (providers.table) sends every cell as text/HTML with its sort value; this file only lays it out.
(function(){
  'use strict';
  const DD = window.DD = window.DD || {};

  function esc(s){ return String(s == null ? '' : s).replace(/[&<>"]/g, function(c){ return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]; }); }
  function rgba(hex, a){
    const m = /^#?([0-9a-f]{6})$/i.exec(String(hex || '').trim());
    if (!m) return hex;
    const n = parseInt(m[1], 16);
    return 'rgba(' + (n >> 16) + ',' + ((n >> 8) & 255) + ',' + (n & 255) + ',' + a + ')';
  }

  // SegmentedBarWidget: a rounded track, one translucent (alpha 180) segment per count; optional centred text.
  function segBar(counts, colors, text){
    const total = counts.reduce(function(a, b){ return a + b; }, 0);
    let h = '<div class="dd-seg-bar">';
    if (total > 0){
      counts.forEach(function(c, i){
        if (c > 0) h += '<span style="width:' + (c / total * 100) + '%;background:' + rgba(colors[i], 180 / 255) + '"></span>';
      });
      if (text) h += '<b>' + esc(text) + '</b>';
    }
    return h + '</div>';
  }

  function cellHtml(cell, key, colors){
    if (!cell) return '';
    if (cell.bar) return segBar(cell.bar, [colors.bad, colors.good], cell.t);
    if (cell.seg) return segBar(cell.seg, [colors.bad, colors.hard, colors.good, colors.easy], '');
    if (cell.parts){
      return '<span class="dd-parts">' + cell.parts.map(function(p, i){
        return (i ? '<i>|</i>' : '') + '<span style="color:' + p[1] + '">' + esc(p[0]) + '</span>';
      }).join('') + '</span>';
    }
    return cell.t;
  }

  DD.table = {
    mount: function(host, opts){
      const st = {tab: 0, sort: {col: 'time', desc: true}, data: null, expanded: new Set(), selected: null, open: true,
        autoClose: true, filter: '', selDid: opts && opts.selectedDid, mode: 'time', deckKey: 'collection', selSpan: opts && opts.selectedSpan};
      host.innerHTML =
        '<div class="dd-tbl-panel">' +
        '<div class="dd-tbl-mbar"><span class="dd-tbl-mtitle">' + DD.t('Decks') + '</span>' +
        '<button type="button" class="dd-tbl-close" title="' + DD.t('Close') + '" aria-label="' + DD.t('Close') + '">&times;</button></div>' +
        '<div class="dd-tbl-scroll"><table class="dd-tbl"><thead></thead><tbody></tbody></table></div>' +
        // the foot in three parts: Auto-close on the left, the tabs in the middle of the table, on the right what the table
        // shows (app.js puts View by Deck / Time first there). No Hide: the bottom bar's Table handle and layout buttons close it
        '<div class="dd-tbl-foot"><div class="dd-tbl-fl">' +
        '<button class="dd-pill dd-autoclose">Auto-close</button>' +
        '<button class="dd-tbl-opt dd-tbl-full" title="Full Table">' + (DD.icon ? DD.icon('maximize', 14) : '') + '<span>Full Table</span></button></div>' +
        '<div class="dd-tbl-tabs"></div><div class="dd-tbl-fr">' +
        // the columns (the right-click menu of the header, which few people find): always in sight, the table may scroll sideways
        '<button class="dd-tbl-cols">' + (DD.icon ? DD.icon('sliders', 14) : '') + '<span>Columns</span></button>' +
        // what the table shows besides its numbers, next to the table
        '<button class="dd-tbl-opt dd-visuals" title="Bars in the table: answer buttons, retention">' + (DD.icon ? DD.icon('bars', 14) : '') + '<span>Visuals</span>' + (DD.icon ? DD.icon('chevdown', 10) : '') + '</button>' +
        '<button class="dd-tbl-opt dd-trends" title="Compare each value with the period before">' + (DD.icon ? DD.icon('trend', 14) : '') + '<span>Trends</span></button>' +
        '</div></div></div>';
      const thead = host.querySelector('thead'), tbody = host.querySelector('tbody'), tabsEl = host.querySelector('.dd-tbl-tabs');
      const panel = host.querySelector('.dd-tbl-panel');
      const closeBtn = host.querySelector('.dd-tbl-close');
      if (closeBtn) closeBtn.addEventListener('click', function(ev){ ev.stopPropagation(); if (opts && opts.onHide) opts.onHide(); });

      function hidden(r, byName){
        if (r.kind !== 'deck') return false;
        if (st.filter){
          const f = st.filter;
          return !((r.full_name || '').toLowerCase().indexOf(f) >= 0 || (r.name || '').toLowerCase().indexOf(f) >= 0);
        }
        if (r.empty) return true;
        let p = r.parent;
        while (p){
          if (!st.expanded.has(p)) return true;
          const pr = byName[p]; p = pr ? pr.parent : null;
        }
        return false;
      }

      // a row's key in a selection of several: its deck's full name, the Total row's own
      function rowKey(r){ return r.kind === 'total' ? '__total__' : (r.full_name || ''); }
      // the decks behind the rows picked together: the Total row covers it all
      // (0); a deck under another one picked is dropped (its parent has it); a folder without a deck of its own stands
      // for the decks under it; the Deleted Cards row is the "deleted" token. One deck left: that deck alone
      function multiDecks(){
        const rows = (st.data && st.data.rows) || [], picked = rows.filter(function(r){ return st.multi.has(rowKey(r)); });
        if (picked.some(function(r){ return r.kind === 'total'; })) return {did: 0, name: 'Total'};
        const deleted = picked.filter(function(r){ return r.deleted; })[0];
        const names = picked.filter(function(r){ return !r.deleted && r.full_name; }).map(function(r){ return r.full_name; });
        const kept = names.filter(function(n){ return !names.some(function(o){ return o !== n && n.indexOf(o + '::') === 0; }); });
        let dids = [];
        kept.forEach(function(n){
          const r = rows.filter(function(x){ return x.full_name === n; })[0];
          if (r && r.did){ dids.push(+r.did); return; }
          rows.forEach(function(x){ if (x.did && (x.full_name || '').indexOf(n + '::') === 0) dids.push(+x.did); });
        });
        dids = dids.filter(function(v, i){ return dids.indexOf(v) === i; });
        if (!dids.length) return deleted ? {did: -1, name: deleted.name} : null;
        if (dids.length === 1 && !deleted){ const r = rows.filter(function(x){ return +x.did === dids[0]; })[0]; return {did: dids[0], name: r ? r.name : ''}; }
        const all = deleted ? dids.concat(['deleted']) : dids;
        return {did: all, name: DD.tn('{n} deck', '{n} decks', all.length, {n: all.length})};
      }
      function render(){
        const d = st.data;
        if (!d) return;
        const _t0 = performance.now(); setTimeout(function(){ DD.trace('PERF table render sync=' + (performance.now() - _t0).toFixed(0) + 'ms rows=' + d.rows.length + ' (incl. next paint wait)'); }, 0);
        const colors = d.colors, cols = d.columns;
        thead.innerHTML = '<tr>' + cols.map(function(c){
          const on = st.userSorted && st.sort.col === c.key;
          return '<th data-col="' + c.key + '"' + (on ? ' class="sorted"' : '') + '>' + esc(c.label) + (on ? '<s>' + (st.sort.desc ? '▼' : '▲') + '</s>' : '') + '</th>';
        }).join('') + '</tr>';
        const byName = {};
        d.rows.forEach(function(r){ if (r.full_name) byName[r.full_name] = r; });
        const totalBottom = d.total_bottom !== false;
        const isTot = function(r){ return r.kind === 'total' || !!r.total; };
        const ordered = [];
        const tots = [];
        d.rows.forEach(function(r){ if (isTot(r)) tots.push(r); else ordered.push(r); });
        const finalRows = totalBottom ? ordered.concat(tots) : tots.concat(ordered);
        let html = '', n = 0;
        finalRows.forEach(function(r){
          if (hidden(r, byName)) return;
          // several rows picked together (Ctrl / Shift + click, View by Time): those are the ones shown selected
          const sel = r.kind === 'span' ? (r.range !== undefined && String(r.range) === String(st.selSpan))
            : st.multi ? st.multi.has(rowKey(r))
            : r.kind === 'total' ? String(st.selDid) === '0' : ((r.did && String(r.did) === String(st.selDid)) || (r.deleted && String(st.selDid) === '-1'));
          const bg = r.color ? ' style="background:' + r.color + '"' : '';
          let name;
          if (r.kind === 'total') name = '<b>' + esc(r.name) + '</b>';
          else if (r.kind === 'span') name = r.total ? '<b>' + esc(r.name) + '</b>' : esc(r.name);
          else {
            const icon = r.has_children ? (st.expanded.has(r.full_name) ? '▾ ' : '▸ ') : '';
            name = '<span class="dd-nm"><span class="dd-tree">' + esc(r.prefix).replace(/ /g, '&nbsp;') + '</span>' + icon + esc(r.name) + '</span>';
            if (r.has_children) name = '<b>' + name + '</b>';
          }
          const rkey = r.kind === 'total' ? 'total' : (r.deleted ? 'deleted' : (r.did ? String(r.did) : ''));
          const totCls = isTot(r) ? ('total ' + (totalBottom ? 'total-bot ' : 'total-top ')) : '';
          html += '<tr class="' + totCls + (sel ? 'sel ' : '') + ((n++ % 2) ? 'odd' : 'even') + '" data-name="' + esc(r.full_name || '') + '"' + (r.did ? ' data-did="' + r.did + '"' : '') + (rkey ? ' data-ckey="' + rkey + '"' : '') + (r.color ? ' data-colored="1"' : '') + (r.kind === 'span' ? ' data-range="' + esc(r.range) + '"' : '') + '>' +
            '<td class="deck"' + bg + '>' + name + '</td>' +
            cols.slice(1).map(function(c){
              const cell = r.cells[c.key];
              const sty = [];
              if (r.color) sty.push('background:' + r.color);
              if (cell && cell.color) sty.push('color:' + cell.color);
              return '<td' + (cell && cell.tip ? ' title="' + esc(cell.tip) + '"' : '') + (sty.length ? ' style="' + sty.join(';') + '"' : '') + '>' + cellHtml(cell, c.key, colors) + '</td>';
            }).join('') + '</tr>';
        });
        tbody.innerHTML = html;
        // the closed table's bar: "Table: <tab>  ·  N reviews  ·  R%" (from the tab's totals)
        if (opts && opts.onSummary){
          const tab = d.tabs[d.tab] || {}, tot = d.rows.filter(function(r){ return r.kind === 'total'; })[0], bits = [];
          if (tot && st.mode !== 'deck'){
            const rv = tot.cells.reviews, rt = tot.cells.retention;
            if (rv && rv.s) bits.push(DD.tn('{n} review', '{n} reviews', Number(rv.s), {n: Number(rv.s).toLocaleString('en-US')}));
            if (rt){ const tx = plain(rt.t || ''); if (tx && tx !== 'N/A') bits.push(tx.split(' ')[0]); }
          }
          opts.onSummary(tab.title || '', bits.join('  \u00b7  '));
        }
        // View by Deck: a folder's tab has a caret that folds / unfolds the decks under it (the deck shown keeps its
        // folders open)
        tabsEl.innerHTML = d.tabs.map(function(t, i){
          const car = t.kids ? '<span class="dd-tcar' + (t.keep ? ' keep' : '') + '" data-n="' + esc(t.name) + '" title="' + (t.keep ? 'Holds the deck shown' : (t.open ? 'Fold' : 'Unfold')) + '">' + (t.open ? '\u25be' : '\u25b8') + '</span>' : '';
          return '<button' + (i === d.tab ? ' class="on"' : '') + ' data-i="' + i + '"' + (t.did !== undefined ? ' data-d="' + esc(t.did) + '"' : '') + '>' + car + '<span data-nt>' + esc(t.title) + '</span></button>';
        }).join('');
        panel.style.setProperty('--dd-row-h', (d.row_height || 30) + 'px');
        panel.classList.toggle('dd-nozebra', d.zebra === false);  // Settings > General > Zebra Rows
      }

      // the time span of the tab shown (View by Time): a deck picked there opens over that span
      function tabRange(){ const t = st.data && st.data.tabs && st.data.tabs[st.tab]; return t ? t.range : undefined; }
      const cache = {};
      function ckey(){ return st.tab + '|' + st.sort.col + '|' + st.sort.desc + '|' + (st.mode === 'deck' ? st.deckKey : ''); }
      function apply(d){
        st.data = d; st.tab = d.tab; st.sort = d.sort;
        if (!st.expandedInit){ st.expanded = new Set(d.expanded || []); st.expandedInit = true; }
        render();
      }
      // shows the last answer for this view at once, then refreshes it
      function load(){
        const k = ckey(), hit = cache[k], gen = st.gen = (st.gen || 0), vm = st.mode, vdk = st.deckKey, cg = st.colGen;
        if (hit) apply(hit);
        return DD.call('table', {tab: st.tab, sort: st.sort, deck: st.mode === 'deck' ? st.deckKey : null, expanded: (st.mode === 'deck' && st.expandedInit) ? Array.from(st.expanded) : null}).then(function(d){
          if (!d || !d.rows) return;
          st.answered = true;
          if (vm !== st.mode || vdk !== st.deckKey || gen !== st.gen || cg !== st.colGen) return;  // answer of a view we left (or older columns)
          cache[k] = d; cache[d.tab + '|' + d.sort.col + '|' + d.sort.desc + '|' + (st.mode === 'deck' ? st.deckKey : '')] = d;
          if (k === ckey() || !hit) apply(d);
          prefetch();
        }).catch(function(e){ DD.log('table: ' + (e && e.message || e)); });
      }
      function prefetch(){
        const d = st.data;
        const pkey = st.mode === 'deck' ? 'deck' : st.mode + st.deckKey;
        if (!d || st.prefetched === pkey) return;
        st.prefetched = pkey;
        const mode = st.mode, dk = st.deckKey, sort = st.sort, cg = st.colGen;
        // one at a time, and only while nothing else is asked (each one takes Python 300-700 ms: several at once,
        // or one during a deck change, slowed the charts' own reading down)
        const todo = d.tabs.map(function(t, i){ return [t, i]; });
        (function nextOne(){
          if (!todo.length || mode !== st.mode || (mode !== 'deck' && dk !== st.deckKey) || cg !== st.colGen) return;
          if (performance.now() - (DD._lastScopeAt || 0) < 2500){ setTimeout(nextOne, 800); return; }
          // nor while the window is resized (Python busy here, the window can't paint its new size)
          if (performance.now() - (DD._lastResizeAt || 0) < 1500){ setTimeout(nextOne, 500); return; }
          // nor while the charts are scrolled (Python's reading stuttered the scroll)
          if (performance.now() - (DD._lastScrollAt || 0) < 600){ setTimeout(nextOne, 300); return; }
          const pair = todo.shift(), t = pair[0], i = pair[1];
          (function(){
            if (mode !== st.mode || (mode !== 'deck' && dk !== st.deckKey)) return;
            // View by Deck: each tab is a deck (its own key): it was asked for with the deck shown, so another
            // deck's tab was never ready and took ~300 ms when clicked (View by Time's tabs were)
            const tdk = mode === 'deck' ? (t.did !== undefined ? String(t.did) : dk) : '';
            const k = i + '|' + sort.col + '|' + sort.desc + '|' + tdk;
            if (cache[k]){ setTimeout(nextOne, 0); return; }
            DD.call('table', {tab: i, sort: sort, deck: mode === 'deck' ? tdk : null, expanded: (mode === 'deck' && st.expandedInit) ? Array.from(st.expanded) : null}).then(function(r){ if (r && r.rows && cg === st.colGen) cache[k] = r; }).catch(function(){}).then(function(){ setTimeout(nextOne, 300); });
          })();
        })();
      }

      thead.addEventListener('click', function(ev){
        if (thead._dragged || st.mode === 'deck') return;
        const th = ev.target.closest('th'); if (!th) return;
        const c = th.getAttribute('data-col'); st.userSorted = true;
        if (st.sort.col === c){ if (st.sort.desc) st.sort = {col: c, desc: false}; else st.sort = {col: 'time', desc: true}; }
        else st.sort = {col: c, desc: true};
        load();
      });
      // Drag-and-drop column reordering (column 0 = Deck / Time Span stays pinned first)
      let cdrag = null;
      thead.addEventListener('pointerdown', function(ev){
        if (ev.button !== 0) return;
        const th = ev.target.closest('th'); if (!th || th.getAttribute('data-col') === 'deck') return;
        cdrag = {th: th, x0: ev.clientX, on: false};
      });
      window.addEventListener('pointermove', function(ev){
        const d = cdrag; if (!d) return;
        const dx = ev.clientX - d.x0;
        if (!d.on){
          if (Math.abs(dx) < 6) return;
          headTip(null);
          d.on = true;
          d.ths = Array.prototype.slice.call(thead.querySelectorAll('th')).slice(1);
          d.rects = d.ths.map(function(x){ return x.getBoundingClientRect(); });
          d.from = d.ths.indexOf(d.th);
          if (d.from < 0){ cdrag = null; return; }
          d.to = d.from;
          const anim = !(DD.anim && DD.anim.on === false) && !DD._noAnim;
          d.ths.forEach(function(x){ if (x !== d.th) x.style.transition = anim ? 'transform ' + Math.round(150 * (DD.speed ? DD.speed() : 1)) + 'ms ease' : ''; });
          d.th.classList.add('dd-tdrag');
        }
        const r0 = d.rects[d.from], lo = d.rects[0].left - r0.left, hi = d.rects[d.rects.length - 1].right - r0.right;
        const mx = Math.max(lo, Math.min(hi, dx)), px = ev.clientX;
        let to = 0;
        d.rects.forEach(function(r, i){ if (i !== d.from && r.left + r.width / 2 < px) to++; });
        d.to = to;
        d.th.style.transform = 'translateX(' + mx + 'px)';
        const w = r0.width;
        d.ths.forEach(function(x, i){
          if (i === d.from) return;
          const s = d.from < to && i > d.from && i <= to ? -w : (to < d.from && i >= to && i < d.from ? w : 0);
          x.style.transform = s ? 'translateX(' + s + 'px)' : '';
        });
      });
      function endColDrag(){
        const d = cdrag; cdrag = null;
        if (!d || !d.on) return;
        d.ths.forEach(function(x){ x.style.transform = ''; x.style.transition = ''; });
        d.th.classList.remove('dd-tdrag');
        thead._dragged = true; setTimeout(function(){ thead._dragged = false; }, 0);
        if (d.to === d.from || !st.data || !st.data.columns) return;
        const movable = st.data.columns.slice(1);
        const moved = movable.splice(d.from, 1)[0];
        if (!moved) return;
        movable.splice(d.to, 0, moved);
        st.data.columns = [st.data.columns[0]].concat(movable);
        const newKeys = movable.map(function(c){ return c.key; });
        Object.keys(cache).forEach(function(k){ delete cache[k]; }); st.prefetched = null; st.colGen = (st.colGen || 0) + 1;
        render();
        DD.call('set_table_columns', {keys: newKeys}).catch(function(e){ DD.log('table col order: ' + (e && e.message || e)); load(); });
      }
      window.addEventListener('pointerup', endColDrag);
      window.addEventListener('pointercancel', endColDrag);
      // the header's right-click menu: every column (the stat cards' figures), by group; one list for every time span
      if (DD.onLongPress){
        DD.onLongPress(thead, function(ev){
          if (ev.target && ev.target.dispatchEvent) ev.target.dispatchEvent(new MouseEvent('contextmenu', {bubbles: true, cancelable: true, clientX: ev.clientX, clientY: ev.clientY}));
        });
        DD.onLongPress(tbody, function(ev){
          if (ev.target && ev.target.dispatchEvent) ev.target.dispatchEvent(new MouseEvent('contextmenu', {bubbles: true, cancelable: true, clientX: ev.clientX, clientY: ev.clientY}));
        });
      }
      thead.addEventListener('contextmenu', function(ev){ headTip(null); columnsMenu(ev, {x: ev.clientX, y: ev.clientY}); });
      // a deck's right-click menu: its color (and reset), left out of the stats, the Settings' Decks tab
      tbody.addEventListener('contextmenu', function(ev){
        const tr = ev.target.closest('tr[data-ckey]'); if (!tr || !DD.menu) return;
        ev.preventDefault();
        const key = tr.getAttribute('data-ckey');
        const items = [['color', DD.t('Deck Color...')]];
        if (tr.getAttribute('data-colored') === '1') items.push(['reset_color', DD.t('Reset Deck Color')]);
        if (key !== 'total') items.push(['exclude', DD.t('Exclude from Stats')]);
        items.push('sep', ['settings', DD.t('Deck Settings...'), undefined, 'gear']);
        DD.menu({x: ev.clientX, y: ev.clientY}, items, function(k){
          DD.call('deck_action', {did: key, action: k}).catch(function(e){ DD.log('deck action: ' + (e && e.message || e)); });
        });
      });
      // the header's hint, "Right-click: columns" (the window shows no title tooltip): drawn as the charts' help, after a
      // short rest of the mouse on a column's name
      let tipTimer = null, tipEl = null, tipTh = null;
      function headTip(th){
        clearTimeout(tipTimer); tipTh = th;
        if (tipEl){ tipEl.remove(); tipEl = null; }
        if (!th) return;
        tipTimer = setTimeout(function(){
          if (tipTh !== th || !th.isConnected || document.querySelector('.dd-menu')) return;
          tipEl = document.createElement('div'); tipEl.className = 'dd-helptip'; tipEl.textContent = DD.t('Right-click: columns');
          document.body.appendChild(tipEl);
          const r = th.getBoundingClientRect();
          tipEl.style.left = Math.max(4, Math.min(r.left, window.innerWidth - tipEl.offsetWidth - 8)) + 'px';
          tipEl.style.top = Math.min(r.bottom + 4, window.innerHeight - tipEl.offsetHeight - 8) + 'px';
        }, 700);
      }
      thead.addEventListener('mouseover', function(ev){ const th = ev.target.closest('th'); if (th !== tipTh) headTip(th); });
      thead.addEventListener('mouseleave', function(){ headTip(null); });
      thead.addEventListener('mousedown', function(){ headTip(null); });
      host.querySelector('.dd-tbl-cols').addEventListener('click', function(ev){ ev.stopPropagation(); columnsMenu(ev, ev.currentTarget); });
      function columnsMenu(ev, anchor){
        const d = st.data, ch = d && d.column_choices;
        if (!ch || !DD.menu) return;
        ev.preventDefault();
        const shown = d.columns.slice(1).map(function(c){ return c.key; });
        let keys = shown.slice(), counts = !!ch.counts;
        const th = ev.target.closest('th'), at = th && th.getAttribute('data-col');
        const label = {}; ch.all.forEach(function(c){ label[c[0]] = c[1]; });
        const items = [];
        if (at && at !== 'deck') items.push(['hide:' + at, DD.t('Hide Column') + ' · ' + esc(label[at] || at)], 'sep');
        ch.groups.forEach(function(g){
          const sub = ch.all.filter(function(c){ return c[2] === g[0]; }).map(function(c){ return ['col:' + c[0], esc(c[1]), keys.indexOf(c[0]) >= 0, null, true]; });
          if (sub.length) items.push(['grp:' + g[0], esc(g[1]), undefined, null, false, sub]);
        });
        items.push('sep', ['counts', DD.t('Show counts (pass / fail)'), counts, null, true],
          ['total_bottom', DD.t('Total row at bottom'), d.total_bottom !== false, null, true],
          'sep', ['reset', DD.t('Reset Columns'), undefined, 'reset']);
        function save(reset){
          st.colGen = (st.colGen || 0) + 1;
          if (keys.indexOf(st.sort.col) < 0 && st.sort.col !== 'deck'){ st.sort = {col: 'time', desc: true}; st.userSorted = false; }
          Object.keys(cache).forEach(function(k){ delete cache[k]; }); st.prefetched = null;
          DD.call('set_table_columns', reset ? {reset: true} : {keys: keys, counts: counts}).then(function(){ load(); }).catch(function(e){ DD.log('table columns: ' + (e && e.message || e)); });
        }
        DD.menu(anchor, items, function(k, on){
          if (k === 'counts'){ counts = !!on; save(); return; }
          if (k === 'total_bottom'){
            const v = !!on;
            if (st.data) st.data.total_bottom = v;
            Object.keys(cache).forEach(function(ck){ if (cache[ck]) cache[ck].total_bottom = v; });
            render();
            DD.call('set_table_total_bottom', {on: v}).catch(function(){});
            return;
          }
          if (k === 'reset'){ keys = (ch.defaults || []).slice(); save(true); return; }
          const hide = /^hide:/.test(k), key = String(k).replace(/^(hide|col):/, '');
          if (hide || (/^col:/.test(k) && !on)) keys = keys.filter(function(x){ return x !== key; });
          else if (/^col:/.test(k) && keys.indexOf(key) < 0) keys.push(key);
          else return;
          save();
        });
      }
      tbody.addEventListener('click', function(ev){
        const tr = ev.target.closest('tr'); if (!tr) return;
        if (DD.dev) DD.trace('TABLE row click name=' + tr.getAttribute('data-name') + ' did=' + tr.getAttribute('data-did') + ' mode=' + st.mode);
        if (st.mode === 'deck'){
          const rg = tr.getAttribute('data-range'); if (rg === null) return;
          st.selSpan = rg; render();
          if (opts && opts.onSpan) opts.onSpan(+rg);
          return;
        }
        // several decks together (View by Time): Ctrl + click adds or takes off a row, Shift +
        // click the rows from the last one clicked; a plain click on one of them opens one Deep Dive of them all, a
        // plain click elsewhere goes back to one deck
        const key = tr.classList.contains('total') ? '__total__' : (tr.getAttribute('data-name') || '');
        if (key && (ev.ctrlKey || ev.metaKey || ev.shiftKey)){
          if (!st.multi){
            st.multi = new Set();
            const cur = (st.data.rows || []).filter(function(r){ return r.kind === 'total' ? String(st.selDid) === '0' : ((r.did && String(r.did) === String(st.selDid)) || (r.deleted && String(st.selDid) === '-1')); })[0];
            if (cur){ st.multi.add(rowKey(cur)); if (!st.anchor) st.anchor = rowKey(cur); }
          }
          if (ev.shiftKey && st.anchor){
            const trs = Array.prototype.slice.call(tbody.querySelectorAll('tr')).map(function(x){ return x.classList.contains('total') ? '__total__' : (x.getAttribute('data-name') || ''); });
            const a = trs.indexOf(st.anchor), b = trs.indexOf(key);
            if (a >= 0 && b >= 0){ if (!(ev.ctrlKey || ev.metaKey)) st.multi.clear(); trs.slice(Math.min(a, b), Math.max(a, b) + 1).forEach(function(k){ if (k) st.multi.add(k); }); }
            else st.multi.add(key);
          } else {
            if (st.multi.has(key)) st.multi.delete(key); else st.multi.add(key);
            st.anchor = key;
          }
          if (!st.multi.size) st.multi = null;
          render();
          return;
        }
        if (st.multi && st.multi.size > 1 && st.multi.has(key)){
          const m = multiDecks();
          if (m && opts && opts.onPick) opts.onPick(m.did, m.name, tabRange());
          return;
        }
        st.multi = null; st.anchor = key;
        if (tr.classList.contains('total')){
          st.selDid = 0; render();
          if (opts && opts.onPick) opts.onPick(0, 'Total', tabRange());
          return;
        }
        const name = tr.getAttribute('data-name');
        if (!name) return;
        const row = st.data.rows.filter(function(r){ return r.full_name === name; })[0];
        // a folder's arrow and name only fold / unfold it
        if (row && row.has_children && ev.target.closest && ev.target.closest('.dd-nm')){
          if (st.expanded.has(name)) st.expanded.delete(name); else st.expanded.add(name);
          DD.call('set_expanded', {names: Array.from(st.expanded)}).catch(function(){});
          render();
          return;
        }
        // the Deleted Cards row opens the Deep Dive of the deleted cards (deck -1)
        if (row && row.deleted){ st.selDid = -1; render(); if (opts && opts.onPick) opts.onPick(-1, row.name, tabRange()); return; }
        if (row && row.did) st.selDid = row.did;
        render();
        if (opts && opts.onPick && row && row.did) opts.onPick(row.did, row.name, tabRange());
      });
      tabsEl.addEventListener('click', function(ev){
        const car = ev.target.closest('.dd-tcar');
        if (car && st.mode === 'deck'){
          ev.stopPropagation();
          if (car.classList.contains('keep')) return;
          const name = car.getAttribute('data-n');
          if (!st.expandedInit){ st.expanded = new Set((st.data && st.data.expanded) || []); st.expandedInit = true; }
          if (st.expanded.has(name)) st.expanded.delete(name); else st.expanded.add(name);
          DD.call('set_expanded', {names: Array.from(st.expanded)}).catch(function(){});
          Object.keys(cache).forEach(function(k){ delete cache[k]; }); st.prefetched = null;  // the tabs changed
          load();
          return;
        }
        if (tabsEl._dragged) return;  // the end of a tab's drag, not a click
        const b = ev.target.closest('button'); if (!b) return;
        if (DD.dev) DD.trace('TABLE tab click i=' + b.getAttribute('data-i') + ' mode=' + st.mode);
        if (st.mode === 'deck'){
          st.deckKey = b.getAttribute('data-d'); st.tab = +b.getAttribute('data-i');
          load();
          if (opts && opts.onDeckTab) opts.onDeckTab(st.deckKey);
          return;
        }
        st.tab = +b.getAttribute('data-i'); load();
        if (opts && opts.onTimeTab) opts.onTimeTab(tabRange());
      });
      // View by Time: a tab dragged to another place (the normal window's tabs are movable); the others make room
      // while it moves, the order is saved on the drop (table_tab_order) and the tab shown stays shown
      let tdrag = null;
      tabsEl.addEventListener('pointerdown', function(ev){
        if (st.mode !== 'time' || ev.button !== 0 || ev.target.closest('.dd-tcar')) return;
        const b = ev.target.closest('button'); if (!b) return;
        tdrag = {b: b, x0: ev.clientX, on: false};
      });
      window.addEventListener('pointermove', function(ev){
        const d = tdrag; if (!d) return;
        const dx = ev.clientX - d.x0;
        if (!d.on){
          if (Math.abs(dx) < 6) return;
          d.on = true; d.btns = Array.prototype.slice.call(tabsEl.querySelectorAll('button'));
          d.rects = d.btns.map(function(x){ return x.getBoundingClientRect(); }); d.from = d.btns.indexOf(d.b); d.to = d.from;
          d.gap = d.btns.length > 1 ? Math.max(0, d.rects[1].left - d.rects[0].right) : 0;
          const anim = !(DD.anim && DD.anim.on === false) && !DD._noAnim;
          d.btns.forEach(function(x){ if (x !== d.b) x.style.transition = anim ? 'transform ' + Math.round(150 * (DD.speed ? DD.speed() : 1)) + 'ms ease' : ''; });
          d.b.classList.add('dd-tdrag');
        }
        const r0 = d.rects[d.from], lo = d.rects[0].left - r0.left, hi = d.rects[d.rects.length - 1].right - r0.right;
        const mx = Math.max(lo, Math.min(hi, dx)), px = ev.clientX;
        let to = 0;
        d.rects.forEach(function(r, i){ if (i !== d.from && r.left + r.width / 2 < px) to++; });
        d.to = to;
        d.b.style.transform = 'translateX(' + mx + 'px)';
        const w = r0.width + d.gap;
        d.btns.forEach(function(x, i){
          if (i === d.from) return;
          const s = d.from < to && i > d.from && i <= to ? -w : (to < d.from && i >= to && i < d.from ? w : 0);
          x.style.transform = s ? 'translateX(' + s + 'px)' : '';
        });
      });
      function endTabDrag(){
        const d = tdrag; tdrag = null;
        if (!d || !d.on) return;
        d.btns.forEach(function(x){ x.style.transform = ''; x.style.transition = ''; });
        d.b.classList.remove('dd-tdrag');
        tabsEl._dragged = true; setTimeout(function(){ tabsEl._dragged = false; }, 0);
        if (d.to === d.from) return;
        const order = d.btns.map(function(x, i){ return i; });
        order.splice(d.from, 1); order.splice(d.to, 0, d.from);
        st.tab = order.indexOf(st.tab);
        Object.keys(cache).forEach(function(k){ delete cache[k]; }); st.prefetched = null;  // the tabs' places changed
        if (st.data && st.data.tabs){ st.data.tabs = order.map(function(i){ return st.data.tabs[i]; }); st.data.tab = st.tab; render(); }
        DD.call('table_tab_order', {order: order}).then(function(){ load(); }).catch(function(e){ DD.log('table tab order: ' + (e && e.message || e)); load(); });
      }
      window.addEventListener('pointerup', endTabDrag);
      window.addEventListener('pointercancel', endTabDrag);
      host.querySelector('.dd-tbl-foot').addEventListener('click', function(ev){
        if (ev.target === ev.currentTarget || ev.target === tabsEl || ev.target.matches('.dd-tbl-fl, .dd-tbl-fr')){ if (opts && opts.onHide) opts.onHide(); }  // empty part of the tab row closes the table
      });
      if (opts && opts.initial && opts.initial.rows){
        const d = opts.initial;
        st.data = d; st.tab = d.tab; st.sort = d.sort; st.expanded = new Set(d.expanded || []); st.expandedInit = true;
        render();
      }
      // the page's Python link may not be ready yet: ask again until the first answer comes
      // (the table of the boot only shows at once: it may have been built before the data was ready, with no rows;
      // it is asked again until Python answers)
      // A table shown from the boot is refreshed once the window's opening animations are over: asked at once, its
      // answer and the tabs read after it came in the middle of the charts' intro, which stuttered
      let tries = 0;
      function first(){
        if (st.answered || tries++ > 12) return;
        load();
        setTimeout(first, 700);
      }
      // A table not shown (its drawer closed) waits the same way, or loads as soon as it shows: read at once (~0.4 s
      // of Python), it kept waiting the charts on screen the window's first answer had left out (~1.3 s to open).
      // (Looked at once the page's opening script is done: the drawer is closed after the table is mounted)
      Promise.resolve().then(function(){
        const unseen = !host.getClientRects().length;
        if (((st.data && st.data.rows) || unseen) && DD.onGo && DD.onIdle){
          DD.onGo(function(){ setTimeout(function(){ DD.onIdle(first, 2000); }, 60); });
          if (unseen && window.ResizeObserver){
            const ro = new ResizeObserver(function(){ if (host.getClientRects().length){ ro.disconnect(); if (!st.answered && !tries) first(); } });
            ro.observe(host);
          }
        } else first();
      });
      function plain(html){ const d = document.createElement('div'); d.innerHTML = html; return (d.textContent || '').replace(/\s+/g, ' ').trim(); }
      function csvData(){
        const d = st.data; if (!d) return null;
        const byName = {}; d.rows.forEach(function(r){ if (r.full_name) byName[r.full_name] = r; });
        const cols = d.columns;
        const rows = [];
        d.rows.forEach(function(r){
          if (hidden(r, byName)) return;
          const line = [r.kind === 'total' ? r.name : r.full_name];
          cols.slice(1).forEach(function(c){
            const cell = r.cells[c.key];
            if (!cell) { line.push(''); return; }
            if (cell.bar) line.push((cell.t ? cell.t + ' ' : '') + '(' + cell.bar[1] + '/' + cell.bar[0] + ')');
            else if (cell.seg) line.push(['Again', 'Hard', 'Good', 'Easy'].map(function(n, i){ return n + ' ' + cell.seg[i]; }).join(' | '));
            else if (cell.parts) line.push(cell.parts.map(function(p){ return p[0]; }).join(' | '));
            else line.push(plain(cell.t));
          });
          rows.push(line);
        });
        return {header: cols.map(function(c){ return c.label; }), rows: rows, title: (d.tabs[d.tab] || {}).title || ''};
      }
      function reload(){
        Object.keys(cache).forEach(function(k){ delete cache[k]; });
        st.prefetched = null;
        st.colGen = (st.colGen || 0) + 1;
        return load();
      }
      return {csvData: csvData, reload: reload, state: st, setFilter: function(text){ st.filter = String(text || '').toLowerCase(); render(); }, select: function(did){ st.multi = null; st.selDid = did; render(); },
        // the view the window opens with (View by Deck), its first data already there: no round by time first
        startMode: function(mode, deckKey, span, data){ st.mode = mode; if (deckKey !== undefined) st.deckKey = deckKey; if (span !== undefined) st.selSpan = span; if (data && data.rows){ st.data = data; st.tab = data.tab || 0; render(); } else { st.tab = 0; tbody.innerHTML = ''; if (host.getClientRects().length) load(); } },  // (not shown: loaded once the opening is over, or when shown)
        setMode: function(mode, deckKey, span){ st.gen = (st.gen || 0) + 1; st.prefetched = null; st.multi = null; tbody.innerHTML = ''; st.mode = mode; if (deckKey !== undefined) st.deckKey = deckKey; if (span !== undefined) st.selSpan = span; st.tab = 0; st.data = null; return load(); },
        setTheme: function(t){
          const ch = (t && t.chart) || (DD.theme && DD.theme.chart);
          if (!ch) return;
          const apply = function(d){
            if (!d || !d.colors) return;
            if (ch.again) d.colors.bad = ch.again;
            if (ch.hard) d.colors.hard = ch.hard;
            if (ch.good) d.colors.good = ch.good;
            if (ch.easy) d.colors.easy = ch.easy;
          };
          apply(st.data);
          Object.keys(cache).forEach(function(k){ apply(cache[k]); });
          if (st.data) render();
        }};
    },
  };
})();
