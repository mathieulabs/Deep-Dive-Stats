// Small dialogs inside a page, over it: a name, a number.
//   DD.ask({title, label, value, ok}) -> Promise: the text typed (trimmed, not empty), or null when cancelled.
//   DD.askInt({title, label, value, min, max}) -> Promise: the number, or null when cancelled.
// Their look comes from the page's theme (the --dd-* colours DD.setTheme sets); the texts go through DD.t.
(function(){
  'use strict';
  const CSS = [
    '.ddq-veil{position:fixed;inset:0;z-index:2147483000;display:flex;align-items:center;justify-content:center;background:rgba(0,0,0,.35)}',
    '.ddq-box{box-sizing:border-box;width:min(360px,calc(100vw - 32px));padding:16px;border:1px solid color-mix(in srgb,var(--dd-text) 13%,transparent);border-radius:12px;background:var(--dd-bg);color:var(--dd-text);box-shadow:0 12px 40px rgba(0,0,0,.35);font:13px -apple-system,"Segoe UI",sans-serif;text-align:left}',
    '.ddq-title{margin:0 0 10px;font-size:15px;font-weight:600}',
    '.ddq-label{margin-bottom:8px;color:var(--dd-text-dim);line-height:1.4}',
    '.ddq-input{box-sizing:border-box;width:100%;height:30px;padding:0 10px;border:1px solid color-mix(in srgb,var(--dd-text) 18%,transparent);border-radius:7px;background:color-mix(in srgb,var(--dd-text) 5%,var(--dd-bg));color:var(--dd-text);font:inherit;outline:none}',
    '.ddq-input:focus{border-color:var(--dd-accent)}',
    '.ddq-input.bad{border-color:#e5484d}',
    '.ddq-acts{display:flex;justify-content:flex-end;gap:8px;margin-top:14px}',
    // (:root:root .ddq-box: above dd.css's ":root:root button:hover", which took the buttons' padding and margin away
    // on hover: they moved)
    ':root:root .ddq-box .ddq-btn,:root:root .ddq-box .ddq-btn:hover,:root:root .ddq-box .ddq-btn:focus,:root:root .ddq-box .ddq-btn:active{box-sizing:border-box;height:28px;min-width:72px;margin:0;padding:0 14px;border:1px solid color-mix(in srgb,var(--dd-text) 18%,transparent);border-radius:7px;background:color-mix(in srgb,var(--dd-text) 5%,var(--dd-bg));color:var(--dd-text);font:inherit;cursor:pointer;transform:none;translate:none;box-shadow:none}',
    ':root:root .ddq-box .ddq-btn:hover{background:color-mix(in srgb,var(--dd-text) 10%,var(--dd-bg))}',
    ':root:root .ddq-box .ddq-btn.ok,:root:root .ddq-box .ddq-btn.ok:hover,:root:root .ddq-box .ddq-btn.ok:focus,:root:root .ddq-box .ddq-btn.ok:active{border-color:var(--dd-accent);background:var(--dd-accent);font-weight:500}',
    ':root:root .ddq-box .ddq-btn.ok:hover{filter:brightness(1.08)}',
    ':root:root .ddq-box .ddq-btn:disabled{opacity:.5;cursor:default;filter:none}',
  ].join('\n');
  function style(){
    if (document.getElementById('ddq-style')) return;
    const s = document.createElement('style');
    s.id = 'ddq-style';
    s.textContent = CSS;
    document.head.appendChild(s);
  }
  function el(tag, cls, text){
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  const T = function(s){ return DD.t ? DD.t(s) : s; };
  // the text on the accent colour: dark on a light accent (a grey or yellow one), else white
  function onAccent(){
    const c = document.createElement('span');
    c.style.color = 'var(--dd-accent)';
    document.body.appendChild(c);
    const m = getComputedStyle(c).color.match(/[\d.]+/g) || [];
    c.remove();
    const lin = function(v){ v = Number(v) / 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    const L = m.length >= 3 ? 0.2126 * lin(m[0]) + 0.7152 * lin(m[1]) + 0.0722 * lin(m[2]) : 0;
    return L > 0.5 ? '#1b1b1d' : '#fff';
  }

  // a dialog with one field; check(value) -> the result, or undefined while it is not valid
  function open(o, type, check){
    style();
    return new Promise(function(resolve){
      const veil = el('div', 'ddq-veil'), box = el('div', 'ddq-box');
      box.setAttribute('role', 'dialog');
      box.setAttribute('data-nt', '');  // translated here (a value typed stays as it is)
      veil.appendChild(box);
      if (o.title) box.appendChild(el('h2', 'ddq-title', T(o.title)));
      if (o.label) box.appendChild(el('div', 'ddq-label', T(o.label)));
      const input = el('input', 'ddq-input');
      input.type = type;
      if (type === 'number'){
        if (o.min != null) input.min = String(o.min);
        if (o.max != null) input.max = String(o.max);
        input.step = '1';
      }
      input.value = o.value == null ? '' : String(o.value);
      box.appendChild(input);
      const acts = el('div', 'ddq-acts');
      const cancel = el('button', 'ddq-btn', T('Cancel'));
      const ok = el('button', 'ddq-btn ok', T(o.ok || 'OK'));
      ok.style.color = onAccent();
      acts.appendChild(cancel); acts.appendChild(ok);
      box.appendChild(acts);
      function valid(){
        const v = check(input.value);
        ok.disabled = v === undefined;
        input.classList.toggle('bad', v === undefined && input.value !== '');
        return v;
      }
      function close(v){
        document.removeEventListener('keydown', key, true);
        veil.remove();
        resolve(v);
      }
      function key(e){
        if (e.key === 'Escape'){ e.preventDefault(); e.stopPropagation(); close(null); }
        else if (e.key === 'Enter'){ e.preventDefault(); e.stopPropagation(); const v = valid(); if (v !== undefined) close(v); }
      }
      input.oninput = valid;
      cancel.onclick = function(){ close(null); };
      ok.onclick = function(){ const v = valid(); if (v !== undefined) close(v); };
      veil.addEventListener('mousedown', function(e){ if (e.target === veil) close(null); });
      document.addEventListener('keydown', key, true);
      document.body.appendChild(veil);
      valid();
      input.focus();
      input.select();
    });
  }

  DD.ask = function(o){
    return open(o || {}, 'text', function(s){ s = String(s).trim(); return s ? s : undefined; });
  };
  DD.askInt = function(o){
    o = o || {};
    return open(o, 'number', function(s){
      if (!/^\s*-?\d+\s*$/.test(String(s))) return undefined;
      const n = parseInt(s, 10);
      if (o.min != null && n < o.min) return undefined;
      if (o.max != null && n > o.max) return undefined;
      return n;
    });
  };

  // Custom Pie / Custom Bar's searches (as in the browser), each with its colour:
  //   DD.editSearches({rows: [{q, c}], max, colors}) -> Promise: the rows kept ([{q, c}]), or null when cancelled.
  const CSS_S = [
    '.ddq-box.ddq-wide{width:min(480px,calc(100vw - 32px))}',
    '.ddq-rows{display:flex;flex-direction:column;gap:6px;max-height:50vh;overflow:auto}',
    '.ddq-row{display:flex;align-items:center;gap:6px}',
    '.ddq-row .ddq-input{flex:1;min-width:0}',
    '.ddq-color{flex:none;width:30px;height:30px;padding:2px;border:1px solid color-mix(in srgb,var(--dd-text) 18%,transparent);border-radius:7px;background:transparent;cursor:pointer}',
    ':root:root .ddq-box .ddq-x,:root:root .ddq-box .ddq-x:hover,:root:root .ddq-box .ddq-x:focus,:root:root .ddq-box .ddq-x:active{flex:none;box-sizing:border-box;width:30px;height:30px;margin:0;padding:0;border:0;border-radius:7px;background:transparent;color:var(--dd-text-dim);font:16px/1 inherit;cursor:pointer;transform:none;translate:none;box-shadow:none}',
    ':root:root .ddq-box .ddq-x:hover{background:color-mix(in srgb,var(--dd-text) 10%,transparent);color:var(--dd-text)}',
    ':root:root .ddq-box .ddq-btn.ddq-add,:root:root .ddq-box .ddq-btn.ddq-add:hover,:root:root .ddq-box .ddq-btn.ddq-add:focus,:root:root .ddq-box .ddq-btn.ddq-add:active{margin-top:8px}',
    '.ddq-acts .ddq-spacer{flex:1}',
  ].join('\n');
  DD.editSearches = function(o){
    o = o || {};
    style();
    if (!document.getElementById('ddq-style-s')){ const s = el('style'); s.id = 'ddq-style-s'; s.textContent = CSS_S; document.head.appendChild(s); }
    const max = o.max || 8, colors = o.colors || ['#5b8def', '#e5484d', '#30a46c', '#f5a524', '#8e4ec6', '#12a594', '#e93d82', '#978365'];
    return new Promise(function(resolve){
      const veil = el('div', 'ddq-veil'), box = el('div', 'ddq-box ddq-wide');
      box.setAttribute('role', 'dialog');
      box.setAttribute('data-nt', '');  // translated here (the searches typed stay as they are)
      veil.appendChild(box);
      box.appendChild(el('h2', 'ddq-title', T(o.title || 'Searches')));
      box.appendChild(el('div', 'ddq-label', T('One slice or series of bars per search, as typed in the browser, within the deck shown.')));
      const list = el('div', 'ddq-rows');
      box.appendChild(list);
      const add = el('button', 'ddq-btn ddq-add', T('Add Search'));
      box.appendChild(add);
      function row(q, c){
        const r = el('div', 'ddq-row'), col = el('input', 'ddq-color'), inp = el('input', 'ddq-input'), x = el('button', 'ddq-x', '×');
        col.type = 'color';
        col.title = T('Color');
        col.value = c || colors[list.children.length % colors.length];
        col.dataset.own = c ? '1' : '';
        col.oninput = function(){ col.dataset.own = '1'; };
        inp.type = 'text'; inp.spellcheck = false; inp.value = q || '';
        inp.placeholder = T('Search, as in the browser');
        x.title = T('Remove');
        x.onclick = function(){ r.remove(); sync(); };
        r.appendChild(col); r.appendChild(inp); r.appendChild(x);
        list.appendChild(r);
        return inp;
      }
      function sync(){
        add.disabled = list.children.length >= max;
        ok.disabled = !list.children.length;
      }
      const acts = el('div', 'ddq-acts');
      const cancel = el('button', 'ddq-btn', T('Cancel'));
      const ok = el('button', 'ddq-btn ok', T(o.ok || 'OK'));
      ok.style.color = onAccent();
      acts.appendChild(cancel); acts.appendChild(ok);
      box.appendChild(acts);
      (o.rows || []).slice(0, max).forEach(function(s){ row(s && s.q, s && s.c); });
      if (!list.children.length) row('', '');
      sync();
      add.onclick = function(){ if (list.children.length < max){ row('', '').focus(); sync(); } };
      function result(){
        return Array.prototype.map.call(list.children, function(r){
          const col = r.querySelector('.ddq-color'), inp = r.querySelector('.ddq-input');
          return {q: inp.value.trim(), c: col.dataset.own ? col.value : ''};
        });
      }
      function close(v){
        document.removeEventListener('keydown', key, true);
        veil.remove();
        resolve(v);
      }
      function key(e){
        if (e.key === 'Escape'){ e.preventDefault(); e.stopPropagation(); close(null); }
        else if (e.key === 'Enter' && !ok.disabled){ e.preventDefault(); e.stopPropagation(); close(result()); }
      }
      cancel.onclick = function(){ close(null); };
      ok.onclick = function(){ if (!ok.disabled) close(result()); };
      veil.addEventListener('mousedown', function(e){ if (e.target === veil) close(null); });
      document.addEventListener('keydown', key, true);
      document.body.appendChild(veil);
      const first = list.querySelector('.ddq-input');
      if (first) first.focus();
    });
  };
})();
