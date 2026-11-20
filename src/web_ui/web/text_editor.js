// The text widget's sentence editor inside a page: bold, italic,
// underline, strike, shadow, font, size, colour, titles, lists, alignment and a line; {placeholders} highlighted and
// completed (variables, then ":" a time span, "@" a deck, "|" a unit), braces paired; Markdown turned into formatting
// as it is typed (# , - , 1. , **bold**, *italic*, ~~strike~~, --- then Enter) or pasted.
//   DD.editText({template, title, ok}) -> Promise: the template written (trimmed), or null when cancelled.
//   DD.textEditor(host, {template, onChange}) -> {el, get(), set(template), focus()}: the editor alone, in host.
// The template in and out: one paragraph is its
// words only, else the paragraphs' HTML, made only of what safe_html (text_label.py) keeps. The variables, spans,
// decks and help come from Python ('te_data', text_editor.py); the look from the page's --dd-* colours.
(function(){
  'use strict';
  const T = function(s, v){ return DD.t ? DD.t(s, v) : s; };
  const HEADING_PT = {1: 22, 2: 18, 3: 15};
  const DECK = '@';
  // as _TEMPLATE_RE (text_label.py): {var:span@deck|unit~}
  const TEMPLATE_RE = /\{(\w+)(?::([^@}|]+?))?(?:@([^}|]+?))?(?:\|([^}]+?))?(~)?\}/g;
  const MD_BLOCK = /^(#{1,3}|[-*+]|1[.)])$/;
  const MD_RULE = /^(?:-{3,}|\*{3,}|_{3,})$/;
  const MD_INLINE = [
    [/\*\*([^*\n]+)\*\*$/, 'b'],
    [/(?:^|[^*\w])\*([^*\s][^*\n]*)\*$/, 'i'],  // not the first star of a closing "**"
    [/~~([^~\n]+)~~$/, 's'],
  ];
  const MD_PASTED = /^(?:#{1,6} |[-*+] |\d+[.)] |> |(?:-{3,}|\*{3,})\s*$)|\*\*[^*\n]+\*\*|~~[^~\n]+~~/m;
  const FONTS = ['Segoe UI', 'Arial', 'Helvetica', 'Verdana', 'Tahoma', 'Trebuchet MS', 'Georgia', 'Times New Roman',
                 'Palatino Linotype', 'Garamond', 'Courier New', 'Consolas', 'Comic Sans MS', 'Impact'];
  const SIZES = [8, 9, 10, 11, 12, 14, 16, 18, 20, 24, 28, 32, 36, 48, 72];
  const SEARCH_AT = 9;  // a filter field over the suggestions from this many
  const MARK = 'rgb(1, 2, 3)';  // a background put on a selection to find it again (the spans it makes get a style)
  const ICONS = {
    list: 'M6 4h8M6 8h8M6 12h8M2.5 4h.01M2.5 8h.01M2.5 12h.01',
    'list-ordered': 'M7 4h7M7 8h7M7 12h7M2 3l1-.5V6M2 6h2M2 9.5c.3-.6 1.9-.6 1.9.3 0 .7-1.9 1.5-1.9 2.2h2',
    'align-left': 'M2 4h12M2 8h8M2 12h11',
    'align-center': 'M2 4h12M4 8h8M3 12h10',
    'align-right': 'M2 4h12M6 8h8M3 12h11',
    rule: 'M2 8h12M2 4h.01M14 4h.01M2 12h.01M14 12h.01',
    palette: 'M8 2a6 6 0 1 0 0 12c.8 0 1.2-.6 1.2-1.2 0-.8-.6-1-.6-1.8 0-.6.5-1 1.1-1H11a3 3 0 0 0 3-3C14 4.2 11.3 2 8 2zM5 7.5h.01M6.5 5h.01M9.5 5h.01',
  };

  const CSS = [
    '.ddte-veil{position:fixed;inset:0;z-index:2147483000;display:flex;align-items:center;justify-content:center;background:rgba(0,0,0,.35)}',
    '.ddte-box{box-sizing:border-box;display:flex;flex-direction:column;width:min(660px,calc(100vw - 32px));max-height:calc(100vh - 32px);padding:16px;border:1px solid color-mix(in srgb,var(--dd-text) 13%,transparent);border-radius:12px;background:var(--dd-bg);color:var(--dd-text);box-shadow:0 12px 40px rgba(0,0,0,.35);font:13px -apple-system,"Segoe UI",sans-serif;text-align:left}',
    '.ddte-title{margin:0 0 10px;font-size:15px;font-weight:600}',
    '.ddte-box .ddte{flex:1 1 auto;min-height:0}',
    '.ddte{display:flex;flex-direction:column;gap:8px;color:var(--dd-text);font:13px -apple-system,"Segoe UI",sans-serif;text-align:left}',
    '.ddte-frame{display:flex;flex-direction:column;gap:8px;min-height:0;flex:1 1 auto;padding:8px;border:1px solid color-mix(in srgb,var(--dd-text) 11%,transparent);border-radius:10px;background:color-mix(in srgb,var(--dd-text) 3%,var(--dd-bg))}',
    '.ddte-bar{display:flex;flex-direction:column;gap:5px;padding:6px;border:1px solid color-mix(in srgb,var(--dd-text) 11%,transparent);border-radius:9px;background:var(--dd-bg)}',
    '.ddte-row{display:flex;align-items:center;flex-wrap:wrap;gap:4px}',
    '.ddte-sep{width:1px;height:20px;margin:0 3px;background:color-mix(in srgb,var(--dd-text) 13%,transparent)}',
    ':root:root .ddte-b,:root:root .ddte-b:hover,:root:root .ddte-b:focus,:root:root .ddte-b:active{box-sizing:border-box;display:inline-flex;align-items:center;justify-content:center;min-width:28px;height:28px;padding:0 6px;margin:0;border:1px solid transparent;border-radius:7px;background:transparent;color:var(--dd-text);font:inherit;font-size:13px;line-height:1;cursor:pointer;box-shadow:none;transform:none}',
    ':root:root .ddte-b:hover{background:color-mix(in srgb,var(--dd-text) 7%,transparent);border-color:color-mix(in srgb,var(--dd-text) 11%,transparent)}',
    ':root:root .ddte-b.on{background:color-mix(in srgb,var(--dd-accent) 16%,transparent);border-color:color-mix(in srgb,var(--dd-accent) 40%,transparent)}',
    '.ddte-b svg{width:16px;height:16px;fill:none;stroke:currentColor;stroke-width:1.4;stroke-linecap:round;stroke-linejoin:round}',
    '.ddte-sel,.ddte-size{box-sizing:border-box;height:28px;padding:0 6px;border:1px solid color-mix(in srgb,var(--dd-text) 16%,transparent);border-radius:7px;background:color-mix(in srgb,var(--dd-text) 4%,var(--dd-bg));color:var(--dd-text);font:inherit;font-size:12px;outline:none}',
    '.ddte-sel:focus,.ddte-size:focus{border-color:var(--dd-accent)}',
    '.ddte-font{width:150px}.ddte-size{width:58px}.ddte-head{width:116px}',
    '.ddte-color{position:relative}',
    '.ddte-color input{position:absolute;inset:0;width:100%;height:100%;opacity:0;cursor:pointer;border:0;padding:0}',
    '.ddte-area{box-sizing:border-box;flex:1 1 auto;min-height:120px;overflow:auto;padding:10px 12px;border:1px solid color-mix(in srgb,var(--dd-text) 18%,transparent);border-radius:9px;background:color-mix(in srgb,var(--dd-text) 5%,var(--dd-bg));color:var(--dd-text);font-size:14px;line-height:1.45;outline:none;overflow-wrap:anywhere;cursor:text}',
    '.ddte-area:focus{border-color:var(--dd-accent)}',
    '.ddte-area p{margin:0}',
    '.ddte-area :is(h1,h2,h3){margin:.15em 0 .3em;line-height:1.25;font-weight:700}',
    '.ddte-area h1{font-size:22pt}.ddte-area h2{font-size:18pt}.ddte-area h3{font-size:15pt}',
    '.ddte-area :is(ul,ol){margin:.2em 0;padding-left:1.4em}',
    '.ddte-area hr{border:0;border-top:1px solid color-mix(in srgb,currentColor 22%,transparent);margin:.5em 0;height:0}',
    '.ddte-area.empty::before{content:attr(data-ph);position:absolute;color:var(--dd-text-dim);opacity:.7;pointer-events:none}',
    '.ddte-area code{font-family:Consolas,monospace}',
    '.ddte-help{display:flex;flex-direction:column;align-items:stretch;gap:4px}',
    ':root:root .ddte-helpbtn,:root:root .ddte-helpbtn:hover,:root:root .ddte-helpbtn:focus{align-self:flex-end;height:auto;padding:0 2px;margin:0;border:0;background:none;color:var(--dd-accent);font:inherit;font-size:11px;font-weight:600;cursor:pointer;box-shadow:none}',
    '.ddte-helpbtn:hover{text-decoration:underline}',
    '.ddte-helpbody{max-height:190px;overflow:auto;padding:9px 11px 2px;border:1px solid color-mix(in srgb,var(--dd-text) 11%,transparent);border-radius:8px;background:color-mix(in srgb,var(--dd-text) 4%,transparent);color:var(--dd-text-dim);font-size:11px;line-height:1.45;user-select:text}',
    '.ddte-helpbody p{margin:0 0 7px}',
    '.ddte-helpbody code{padding:0 3px;border-radius:4px;background:color-mix(in srgb,var(--dd-text) 8%,transparent);color:var(--dd-text);font:11px Consolas,monospace}',
    '.ddte-pop{position:fixed;z-index:2147483100;box-sizing:border-box;width:340px;display:flex;flex-direction:column;gap:6px;padding:6px;border:1px solid color-mix(in srgb,var(--dd-text) 18%,transparent);border-radius:10px;background:color-mix(in srgb,var(--dd-text) 4%,var(--dd-bg));box-shadow:0 8px 28px rgba(0,0,0,.3);font:12px -apple-system,"Segoe UI",sans-serif}',
    '.ddte-search{box-sizing:border-box;width:100%;height:28px;padding:0 9px;border:1px solid color-mix(in srgb,var(--dd-text) 18%,transparent);border-radius:7px;background:var(--dd-bg);color:var(--dd-text);font:inherit;outline:none}',
    '.ddte-search:focus{border-color:var(--dd-accent)}',
    '.ddte-list{max-height:228px;overflow:auto}',
    '.ddte-item{padding:6px 10px;margin:1px 0;border:1px solid transparent;border-radius:6px;color:var(--dd-text-dim);cursor:pointer;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}',
    '.ddte-item b{color:var(--dd-text);font-weight:600}',
    '.ddte-item:hover{background:color-mix(in srgb,var(--dd-text) 6%,transparent);color:var(--dd-text)}',
    '.ddte-item.cur{background:color-mix(in srgb,var(--dd-accent) 14%,transparent);border-color:color-mix(in srgb,var(--dd-accent) 38%,transparent);color:var(--dd-text)}',
    '.ddte-menu{position:fixed;z-index:2147483100;padding:4px;border:1px solid color-mix(in srgb,var(--dd-text) 18%,transparent);border-radius:8px;background:var(--dd-bg);box-shadow:0 8px 28px rgba(0,0,0,.3);font:12px -apple-system,"Segoe UI",sans-serif;color:var(--dd-text)}',
    '.ddte-menu div{display:flex;gap:8px;padding:6px 10px;border-radius:5px;cursor:pointer}',
    '.ddte-menu div:hover{background:color-mix(in srgb,var(--dd-accent) 16%,transparent)}',
    '.ddte-menu span{width:12px}',
    '.ddte-acts{display:flex;justify-content:flex-end;gap:8px;margin-top:14px}',
    '.ddte-btn,.ddte-btn:hover,.ddte-btn:focus,.ddte-btn:active{height:28px;min-width:72px;padding:0 14px;border:1px solid color-mix(in srgb,var(--dd-text) 18%,transparent);border-radius:7px;background:color-mix(in srgb,var(--dd-text) 5%,var(--dd-bg));color:var(--dd-text);font:inherit;cursor:pointer}',
    '.ddte-btn:hover{background:color-mix(in srgb,var(--dd-text) 10%,var(--dd-bg))}',
    '.ddte-btn.ok,.ddte-btn.ok:hover,.ddte-btn.ok:focus{border-color:var(--dd-accent);background:var(--dd-accent);font-weight:500}',
    '.ddte-btn.ok:hover{filter:brightness(1.08)}',
  ].join('\n');
  function style(){
    if (document.getElementById('ddte-style')) return;
    const s = document.createElement('style');
    s.id = 'ddte-style';
    s.textContent = CSS;
    document.head.appendChild(s);
  }
  function el(tag, cls, text){
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  function svg(name){
    const ns = 'http://www.w3.org/2000/svg', s = document.createElementNS(ns, 'svg'), p = document.createElementNS(ns, 'path');
    s.setAttribute('viewBox', '0 0 16 16');
    p.setAttribute('d', ICONS[name]);
    s.appendChild(p);
    return s;
  }
  function esc(s){ return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }

  // ---- what Python gives: the variables, spans, decks, units and the help ----
  let dataP = null;
  function data(){
    if (!dataP){
      dataP = DD.call('te_data', {}).then(function(d){ return d || {}; }).catch(function(e){
        dataP = null;
        DD.log('text editor: no data ' + e);
        return {};
      });
    }
    return dataP;
  }
  let helpOpen = true;  // the help unfolded or not, as it was last left (for the page)
  try { helpOpen = localStorage.getItem('ddte-help') !== '0'; } catch (e) {}

  // ---- the template in and out ----
  function unescapeAll(s){
    const ta = document.createElement('textarea');
    ta.innerHTML = s;
    return ta.value;
  }
  function normalize(t){
    let s = String(t || '');
    if (!s) return '';
    s = unescapeAll(s).trim();
    if (s.charAt(0) !== '<' && s.indexOf('</p>') >= 0){
      const i = s.indexOf('</p>');
      let suffix = s.slice(i + 4);
      if (suffix.indexOf('</p>') === 0) suffix = suffix.slice(4);
      s = '<p>' + s.slice(0, i) + '</p>' + suffix;
    }
    return s;
  }
  function templateHtml(t){
    t = normalize(t);
    if (t.trim().charAt(0) === '<' || /<\/?(?:p|span|br|strong|em|u|s|div)\b/i.test(t)) return clean(t);
    return t ? t.split(/\r?\n/).map(function(l){ return '<p>' + (esc(l) || '<br />') + '</p>'; }).join('') : '';
  }
  function extract(area){
    const body = serialize(area, true);
    if (!body.replace(/<br \/>|<\/?p>/g, '').trim()) return '';
    if ((body.toLowerCase().match(/<p/g) || []).length === 1 && !/<p[^>]*\balign=/i.test(body)){
      const m = /^<p[^>]*>([\s\S]*)<\/p>\s*$/i.exec(body);
      if (m) return m[1].trim();
    }
    return body;
  }

  // ---- HTML kept: what the editor writes, as safe_html (text_label.py) keeps it ----
  const BLOCKS = {P: 'p', DIV: 'p', BLOCKQUOTE: 'p', PRE: 'p', H1: 'h1', H2: 'h2', H3: 'h3', H4: 'h3', H5: 'h3', H6: 'h3',
                  UL: 'ul', OL: 'ol', LI: 'li'};
  const INLINE = {B: 'b', STRONG: 'b', I: 'i', EM: 'i', U: 'u', INS: 'u', S: 's', STRIKE: 's', DEL: 's', SUB: 'sub',
                  SUP: 'sup', CODE: 'code', SPAN: 'span', FONT: 'span', A: 'span', SMALL: 'span', BIG: 'span'};
  const CSS_KEPT = ['color', 'font-family', 'font-size', 'font-weight', 'font-style', 'text-decoration-line',
                    'text-shadow'];
  const DROPPED = /^(SCRIPT|STYLE|IFRAME|OBJECT|EMBED|SVG|MATH|TEMPLATE|NOSCRIPT|TEXTAREA|SELECT|TITLE|HEAD|IMG|VIDEO|AUDIO|BUTTON|INPUT)$/;
  const BLOCK_TAGS = /^(P|DIV|BLOCKQUOTE|PRE|H[1-6]|UL|OL|LI|HR|TABLE|TBODY|THEAD|TFOOT|TR|TD|TH)$/;
  function clean(html){
    const doc = new DOMParser().parseFromString('<body>' + html + '</body>', 'text/html');
    return serialize(doc.body, true);
  }
  function inlineCss(n){
    const st = n.style, out = [];
    if (!st) return out;
    CSS_KEPT.forEach(function(k){
      let v = st.getPropertyValue(k);
      if (!v && k === 'text-decoration-line'){
        const d = st.getPropertyValue('text-decoration');
        if (/underline|line-through/.test(d)) v = d.match(/underline|line-through/g).join(' ');
      }
      if (!v || /url\(|expression|\\/i.test(v)) return;
      if (k === 'text-decoration-line') k = 'text-decoration';
      out.push(k + ':' + v.replace(/"/g, "'"));
    });
    if (n.tagName === 'FONT'){
      if (n.getAttribute('color')) out.push('color:' + n.getAttribute('color').replace(/[";]/g, ''));
      if (n.getAttribute('face')) out.push('font-family:' + n.getAttribute('face').replace(/[";]/g, ''));
    }
    return out;
  }
  function alignOf(n){
    const a = ((n.style && n.style.textAlign) || n.getAttribute('align') || '').toLowerCase();
    return a === 'center' || a === 'right' || a === 'justify' ? a : '';
  }
  function hasBlock(n){
    for (let c = n.firstChild; c; c = c.nextSibling) if (c.nodeType === 1 && BLOCK_TAGS.test(c.tagName)) return true;
    return false;
  }
  // the children of n as HTML; at the top (the editor, a list, a box of blocks), loose words go in a paragraph
  function serialize(n, top){
    let out = '', loose = '';
    function flush(){
      if (loose.replace(/<br \/>/g, '').trim() || /<br \/>/.test(loose)) out += '<p>' + loose + '</p>';
      loose = '';
    }
    for (let c = n.firstChild; c; c = c.nextSibling){
      if (top && c.nodeType === 1 && BLOCK_TAGS.test(c.tagName)){ flush(); out += node(c); }
      else if (top) loose += node(c);
      else out += node(c);
    }
    if (top) flush();
    return out;
  }
  function node(c){
    if (c.nodeType === 3) return esc(c.nodeValue.replace(/\u200b/g, ''));
    if (c.nodeType !== 1 || DROPPED.test(c.tagName)) return '';
    const tag = c.tagName;
    if (tag === 'BR'){
      // the browser's placeholder at a block's end is no line of its own
      const p = c.parentNode;
      let next = c.nextSibling;
      while (next && next.nodeType === 3 && !next.nodeValue) next = next.nextSibling;
      if (!next && p && BLOCKS[p.tagName] && p.textContent.replace(/\u200b/g, '') !== '') return '';
      return '<br />';
    }
    if (tag === 'HR') return '<hr />';
    if (BLOCKS[tag]){
      if ((tag === 'DIV' || tag === 'P' || tag === 'BLOCKQUOTE') && hasBlock(c)) return serialize(c, true);
      const t = BLOCKS[tag], a = alignOf(c);
      let attrs = a ? ' align="' + a + '"' : '';
      if (/^h\d$/.test(t)) attrs += ' style="font-size:' + HEADING_PT[t.charAt(1)] + 'pt; font-weight:700"';
      let inner = serialize(c, t === 'ul' || t === 'ol');
      if (t === 'p' && !inner) inner = '<br />';
      return '<' + t + attrs + '>' + inner + '</' + t + '>';
    }
    if (!INLINE[tag]) return serialize(c, hasBlock(c));  // a table, a form... their words
    const inner = serialize(c, false), t = INLINE[tag];
    const css = inlineCss(c);
    if (t === 'span'){
      if (!css.length || !inner) return inner;
      return '<span style="' + css.join('; ') + '">' + inner + '</span>';
    }
    if (!inner) return '';
    return '<' + t + (css.length ? ' style="' + css.join('; ') + '"' : '') + '>' + inner + '</' + t + '>';
  }

  // ---- Markdown pasted ----
  function mdInline(s){
    return esc(s).replace(/\*\*([^*\n]+)\*\*/g, '<b>$1</b>').replace(/(^|[^*\w])\*([^*\s][^*\n]*)\*/g, '$1<i>$2</i>')
      .replace(/~~([^~\n]+)~~/g, '<s>$1</s>').replace(/`([^`\n]+)`/g, '<code>$1</code>');
  }
  function mdToHtml(text){
    const out = [];
    let para = [], list = null;
    function endPara(){ if (para.length){ out.push('<p>' + para.join(' ') + '</p>'); para = []; } }
    function endList(){ if (list){ out.push('</' + list + '>'); list = null; } }
    String(text).split(/\r?\n/).forEach(function(line){
      let m;
      if (!line.trim()){ endPara(); endList(); return; }
      if (MD_RULE.test(line.trim())){ endPara(); endList(); out.push('<hr />'); return; }
      if ((m = /^(#{1,6})\s+(.*)$/.exec(line))){
        endPara(); endList();
        const n = Math.min(3, m[1].length);
        out.push('<h' + n + '>' + mdInline(m[2]) + '</h' + n + '>');
        return;
      }
      if ((m = /^\s*([-*+]|\d+[.)])\s+(.*)$/.exec(line))){
        endPara();
        const kind = /\d/.test(m[1]) ? 'ol' : 'ul';
        if (list !== kind){ endList(); out.push('<' + kind + '>'); list = kind; }
        out.push('<li>' + mdInline(m[2]) + '</li>');
        return;
      }
      endList();
      para.push(mdInline(line.replace(/^>\s?/, '')));
    });
    endPara(); endList();
    return out.join('');
  }

  // ---- the editor ----
  DD.textEditor = function(host, opts){
    opts = opts || {};
    style();
    let D = {vars: [], spans: [], decks: [], units: [], help: ''};
    const root = el('div', 'ddte');
    root.setAttribute('data-nt', '');
    const frame = el('div', 'ddte-frame');
    const bar = el('div', 'ddte-bar');
    const area = el('div', 'ddte-area');
    area.contentEditable = 'true';
    area.spellcheck = false;
    area.setAttribute('data-ph', T('{reviews} cards in {total_time}'));
    frame.appendChild(bar); frame.appendChild(area);
    root.appendChild(frame);
    host.appendChild(root);

    // -- the toolbar --
    const btns = {};
    function button(row, key, label, tip, fn, cls){
      const b = el('button', 'ddte-b' + (cls ? ' ' + cls : ''));
      b.type = 'button';
      if (ICONS[label]) b.appendChild(svg(label)); else b.textContent = label;
      b.title = T(tip);
      b.addEventListener('mousedown', function(e){ e.preventDefault(); });  // the text keeps its selection
      b.onclick = function(){ restore(); fn(); changed(); sync(); };
      row.appendChild(b);
      if (key) btns[key] = b;
      return b;
    }
    function sep(row){ row.appendChild(el('span', 'ddte-sep')); }
    const row1 = el('div', 'ddte-row'), row2 = el('div', 'ddte-row');
    bar.appendChild(row1); bar.appendChild(row2);
    button(row1, 'bold', 'B', 'Bold (Ctrl+B)', function(){ exec('bold'); }).style.fontWeight = '700';
    button(row1, 'italic', 'I', 'Italic (Ctrl+I)', function(){ exec('italic'); }).style.fontStyle = 'italic';
    button(row1, 'underline', 'U', 'Underline (Ctrl+U)', function(){ exec('underline'); }).style.textDecoration = 'underline';
    button(row1, 'strike', 'S', 'Strikethrough', function(){ exec('strikeThrough'); }).style.textDecoration = 'line-through';
    button(row1, 'shadow', 'Sh', 'Shadow / outline', function(){ shadow(!btns.shadow.classList.contains('on')); });
    sep(row1);
    const font = el('select', 'ddte-sel ddte-font');
    font.title = T('Font family');
    font.appendChild(new Option(T('Default font'), ''));
    FONTS.forEach(function(f){ const o = new Option(f, f); o.style.fontFamily = f; font.appendChild(o); });
    font.onchange = function(){
      restore();
      if (font.value) exec('fontName', font.value); else clearProp('font-family', 'face');
      changed(); area.focus(); sync();
    };
    row1.appendChild(font);
    const size = el('input', 'ddte-size');
    size.title = T('Font size');
    size.setAttribute('list', 'ddte-sizes');
    if (!document.getElementById('ddte-sizes')){
      const dl = el('datalist');
      dl.id = 'ddte-sizes';
      SIZES.forEach(function(s){ dl.appendChild(new Option(String(s), String(s))); });
      document.body.appendChild(dl);
    }
    size.onchange = function(){
      const v = parseFloat(size.value);
      if (!(v > 0)) return;
      restore();
      styleSel('font-size', v + 'pt');
      changed(); area.focus(); sync();
    };
    size.onkeydown = function(e){ if (e.key === 'Enter'){ e.preventDefault(); size.onchange(); } };
    row1.appendChild(size);
    sep(row1);
    button(row1, null, '{}', 'Insert a live-value placeholder', function(){ placeholder(); });
    const colorBtn = el('label', 'ddte-b ddte-color');
    colorBtn.title = T('Text color');
    colorBtn.appendChild(svg('palette'));
    const colorIn = el('input');
    colorIn.type = 'color';
    colorIn.addEventListener('mousedown', function(){ keep(); });
    colorIn.oninput = function(){ restore(); exec('foreColor', colorIn.value); changed(); sync(); };
    colorBtn.appendChild(colorIn);
    row1.appendChild(colorBtn);
    button(row1, null, T('Clear'), 'Clear text color', function(){ clearProp('color', 'color'); });

    const head = el('select', 'ddte-sel ddte-head');
    head.title = T('Paragraph style (or type # , ## , ### then a space)');
    [['p', 'Normal text'], ['h1', 'Title 1'], ['h2', 'Title 2'], ['h3', 'Title 3']].forEach(function(o){
      head.appendChild(new Option(T(o[1]), o[0]));
    });
    head.onchange = function(){ restore(); exec('formatBlock', head.value); changed(); area.focus(); sync(); };
    row2.appendChild(head);
    sep(row2);
    button(row2, 'ul', 'list', 'Bulleted list (or type - then a space)', function(){ exec('insertUnorderedList'); });
    button(row2, 'ol', 'list-ordered', 'Numbered list (or type 1. then a space)', function(){ exec('insertOrderedList'); });
    sep(row2);
    button(row2, 'left', 'align-left', 'Align left', function(){ exec('justifyLeft'); });
    button(row2, 'center', 'align-center', 'Center', function(){ exec('justifyCenter'); });
    button(row2, 'right', 'align-right', 'Align right', function(){ exec('justifyRight'); });
    sep(row2);
    button(row2, null, 'rule', 'Horizontal line (or type --- then Enter)', function(){ rule(); });

    // -- the help --
    const help = el('div', 'ddte-help');
    const helpBtn = el('button', 'ddte-helpbtn');
    helpBtn.type = 'button';
    const helpBody = el('div', 'ddte-helpbody');
    help.appendChild(helpBtn); help.appendChild(helpBody);
    function showHelp(on){
      helpOpen = on;
      try { localStorage.setItem('ddte-help', on ? '1' : '0'); } catch (e) {}
      helpBody.style.display = on && helpBody.firstChild ? '' : 'none';
      helpBtn.textContent = on ? T('Hide help') + ' \u25b4' : T('Help') + ' \u25be';
    }
    helpBtn.onclick = function(){ showHelp(!helpOpen); };
    root.appendChild(help);

    // -- selection --
    let saved = null;
    function sel(){ return window.getSelection(); }
    function range(){
      const s = sel();
      if (!s.rangeCount) return null;
      const r = s.getRangeAt(0);
      return area.contains(r.commonAncestorContainer) ? r : null;
    }
    function keep(){ const r = range(); if (r) saved = r.cloneRange(); }
    function restore(){
      if (document.activeElement === area && range()) return;
      area.focus();
      const s = sel();
      s.removeAllRanges();
      if (saved && area.contains(saved.startContainer)) s.addRange(saved);
      else { const r = document.createRange(); r.selectNodeContents(area); r.collapse(false); s.addRange(r); }
    }
    function exec(cmd, value){
      try { document.execCommand('styleWithCSS', false, /^(foreColor|fontName|hiliteColor)$/.test(cmd)); } catch (e) {}
      document.execCommand(cmd, false, value == null ? null : value);
    }
    // a style on the selection (a collapsed one: on what is typed next, in a span of its own); the same style
    // inside it gives way
    function styleSel(prop, value){
      const r = range();
      if (!r) return;
      if (r.collapsed){
        const span = el('span');
        span.style.setProperty(prop, value);
        span.textContent = '\u200b';
        r.insertNode(span);
        const s = sel(), c = document.createRange();
        c.setStart(span.firstChild, 1); c.collapse(true);
        s.removeAllRanges(); s.addRange(c);
        return;
      }
      exec('hiliteColor', MARK);
      area.querySelectorAll('[style]').forEach(function(n){
        if (n.style.backgroundColor !== MARK) return;
        n.style.removeProperty('background-color');
        n.querySelectorAll('[style]').forEach(function(m){ m.style.removeProperty(prop); });
        n.style.setProperty(prop, value);
      });
    }
    function shadow(on){ styleSel('text-shadow', on ? shadowCss() : 'none'); }
    function shadowCss(){
      const r = range(), n = r && (r.startContainer.nodeType === 1 ? r.startContainer : r.startContainer.parentNode);
      const c = getComputedStyle(n || area).color.match(/[\d.]+/g) || [0, 0, 0];
      const light = (0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]) >= 150;
      return light ? '0 0 2px rgba(0, 0, 0, 0.55)' : '0 0 2px rgba(255, 255, 255, 0.55)';
    }
    // a style taken off what the selection holds whole (a collapsed one: what is typed next has the text's own)
    function clearProp(prop, attr){
      const r = range();
      if (!r) return;
      if (r.collapsed){ styleSel(prop, prop === 'color' ? 'var(--dd-text)' : 'inherit'); return; }
      area.querySelectorAll('[style],font').forEach(function(n){
        if (!r.intersectsNode(n)) return;
        // its words from the first to the last letter (a selection of the words alone holds it whole)
        const all = document.createRange(), w = document.createTreeWalker(n, NodeFilter.SHOW_TEXT);
        let first = null, last = null, t;
        while ((t = w.nextNode())){ if (!first) first = t; last = t; }
        if (!first) return;
        all.setStart(first, 0); all.setEnd(last, last.nodeValue.length);
        if (r.compareBoundaryPoints(Range.START_TO_START, all) > 0 || r.compareBoundaryPoints(Range.END_TO_END, all) < 0) return;
        n.style.removeProperty(prop);
        if (attr) n.removeAttribute(attr);
      });
    }

    // -- paragraphs --
    const BLOCK_SEL = 'p,h1,h2,h3,h4,h5,h6,li,div:not(.ddte-area),blockquote,pre';
    function blockOf(nd){
      let n = nd && nd.nodeType === 3 ? nd.parentNode : nd;
      while (n && n !== area){
        if (n.nodeType === 1 && n.matches(BLOCK_SEL)) return n;
        n = n.parentNode;
      }
      return area;
    }
    function textOf(block){ return block.textContent; }
    function offsetIn(block, nd, off){
      const r = document.createRange();
      r.selectNodeContents(block);
      try { r.setEnd(nd, off); } catch (e) { return 0; }
      return r.toString().length;
    }
    function pointAt(block, off){
      const w = document.createTreeWalker(block, NodeFilter.SHOW_TEXT);
      let n, last = null;
      while ((n = w.nextNode())){
        last = n;
        if (off <= n.nodeValue.length) return {node: n, offset: off};
        off -= n.nodeValue.length;
      }
      return last ? {node: last, offset: last.nodeValue.length} : {node: block, offset: 0};
    }
    function caret(){
      const r = range();
      if (!r || !r.collapsed) return null;
      const block = blockOf(r.startContainer);
      return {block: block, text: textOf(block), pos: offsetIn(block, r.startContainer, r.startOffset)};
    }
    function setCaret(block, off){
      const p = pointAt(block, off), r = document.createRange(), s = sel();
      r.setStart(p.node, p.offset); r.collapse(true);
      s.removeAllRanges(); s.addRange(r);
    }
    function selectIn(block, a, b){
      const p = pointAt(block, a), q = pointAt(block, b), r = document.createRange(), s = sel();
      r.setStart(p.node, p.offset); r.setEnd(q.node, q.offset);
      s.removeAllRanges(); s.addRange(r);
    }
    function insert(text){ document.execCommand('insertText', false, text); }
    function newPara(after){
      const p = el('p');
      p.appendChild(el('br'));
      after.parentNode.insertBefore(p, after.nextSibling);
      return p;
    }
    // a line (<hr>) as its own paragraph, the cursor in a new paragraph under it
    function rule(){
      const r = range();
      let block = r ? blockOf(r.startContainer) : area;
      if (block === area){
        const p = el('p');
        if (r) r.insertNode(p); else area.appendChild(p);
        block = p;
      }
      if (block.tagName === 'LI') block = block.closest('ul,ol') || block;
      const hr = el('hr');
      if (!block.textContent.trim() && block.tagName !== 'UL' && block.tagName !== 'OL') block.replaceWith(hr);
      else block.parentNode.insertBefore(hr, block.nextSibling);
      const p = newPara(hr);
      setCaret(p, 0);
    }
    function heading(){ const r = range(); const b = r && r.startContainer && blockOf(r.startContainer); return b && /^H[1-3]$/.test(b.tagName) ? b : null; }

    // -- placeholders: where the caret is in one --
    function context(){
      const c = caret();
      if (!c) return null;
      const text = c.text, pos = c.pos;
      const open = text.lastIndexOf('{', pos - 1), close = text.lastIndexOf('}', pos - 1);
      if (open < 0 || close > open) return null;
      const next = text.indexOf('}', open + 1);
      if (next !== -1 && pos > next) return null;
      const inner = text.slice(open + 1, pos);
      if (/[\n\r\t{}]/.test(inner)) return null;
      const base = {block: c.block, text: text, pos: pos};
      function to(from, chars){
        const ends = chars.map(function(ch){ return text.indexOf(ch, from); }).filter(function(i){ return i !== -1; });
        return ends.length ? Math.min.apply(null, ends) : pos;
      }
      if (inner.indexOf('|') >= 0){
        const i = inner.indexOf('|'), before = inner.slice(0, i), prefix = inner.slice(i + 1);
        if (!/^[A-Za-z0-9_]+(?::[^\n\r\t{}@|]*)?(?:@[^\n\r\t{}|]*)?$/.test(before) || /[\n\r\t{}|@]/.test(prefix)) return null;
        const start = open + 2 + before.length;
        return Object.assign(base, {mode: 'unit', prefix: prefix, anchor: start, end: to(start, ['}'])});
      }
      if (inner.indexOf(DECK) >= 0){
        const i = inner.indexOf(DECK), before = inner.slice(0, i), prefix = inner.slice(i + 1);
        if (before.indexOf(':') >= 0){
          const j = before.indexOf(':');
          if (!/^[A-Za-z0-9_]+$/.test(before.slice(0, j)) || /[\n\r\t{}@]/.test(before.slice(j + 1))) return null;
        } else if (!/^[A-Za-z0-9_]+$/.test(before)) return null;
        const start = open + 2 + before.length;
        return Object.assign(base, {mode: 'deck', prefix: prefix, anchor: start, end: to(start, ['}'])});
      }
      if (inner.indexOf(':') >= 0){
        const i = inner.indexOf(':'), v = inner.slice(0, i), prefix = inner.slice(i + 1);
        if (!/^[A-Za-z0-9_]+$/.test(v) || /[\n\r\t{}@]/.test(prefix)) return null;
        const start = open + 2 + v.length;
        return Object.assign(base, {mode: 'span', prefix: prefix, anchor: start, end: to(start, [DECK, '}'])});
      }
      if (!/^[A-Za-z0-9_]*$/.test(inner)) return null;
      return Object.assign(base, {mode: 'variable', prefix: inner, anchor: open + 1, end: to(open + 1, [':', '}'])});
    }
    function charAfter(){ const c = caret(); return c ? c.text.charAt(c.pos) : ''; }
    function placeholder(){
      const r = range();
      if (r && !r.collapsed){
        const t = r.toString();
        insert('{' + t + '}');
        hidePop();
        return;
      }
      openPair('{', '}', 'variable');
    }
    // typed: the character and its closing brace, the cursor between them, the suggestions shown
    function openPair(ch, closing, mode){
      const before = caret();
      if (!before) return;
      const pos = before.pos;
      if (closing && before.text.charAt(pos) === '}' && ch !== '{') insert(ch);
      else {
        insert(ch + (closing || ''));
        const c = caret();
        if (c) setCaret(c.block, pos + ch.length);
      }
      showPop(mode, '');
    }

    // -- the suggestions --
    const pop = el('div', 'ddte-pop');
    pop.setAttribute('data-nt', '');
    const search = el('input', 'ddte-search');
    search.type = 'search';
    const list = el('div', 'ddte-list');
    pop.appendChild(search); pop.appendChild(list);
    pop.addEventListener('mousedown', function(e){ if (e.target !== search) e.preventDefault(); });
    let popMode = null, popPrefix = '', rows = [], cur = 0, popRange = null;
    function entries(mode){
      if (mode === 'span') return D.spans || [];
      if (mode === 'unit') return D.units || [];
      if (mode === 'deck') return D.decks || [];
      return D.vars || [];
    }
    function ranked(mode, prefix){
      const all = entries(mode);
      if (!prefix) return all.slice();
      const p = prefix.toLowerCase(), exact = [], starts = [], has = [], rest = [];
      all.forEach(function(e){
        const t = e[0].toLowerCase();
        if (t === p) exact.push(e);
        else if (t.indexOf(p) === 0) starts.push(e);
        else if ((t + ' ' + e[1]).toLowerCase().indexOf(p) >= 0) has.push(e);
        else rest.push(e);
      });
      return exact.concat(starts, has, rest);
    }
    function filtered(){
      const base = ranked(popMode, popPrefix), q = search.value.trim().toLowerCase();
      if (!q) return base;
      const starts = [], has = [];
      base.forEach(function(e){
        if (e[0].toLowerCase().indexOf(q) === 0) starts.push(e);
        else if ((e[0] + ' ' + e[1]).toLowerCase().indexOf(q) >= 0) has.push(e);
      });
      return starts.concat(has);
    }
    function fill(){
      rows = filtered();
      cur = 0;
      list.textContent = '';
      rows.forEach(function(e, i){
        const it = el('div', 'ddte-item');
        it.appendChild(el('b', null, e[0]));
        it.appendChild(document.createTextNode('  -  ' + e[1]));
        it.title = e[1];
        it.onmouseenter = function(){ mark(i, false); };
        it.onclick = function(){ cur = i; accept(); };
        list.appendChild(it);
      });
      mark(0, true);
    }
    function mark(i, scroll){
      if (!rows.length) return;
      cur = Math.max(0, Math.min(rows.length - 1, i));
      Array.prototype.forEach.call(list.children, function(c, k){ c.classList.toggle('cur', k === cur); });
      if (scroll && list.children[cur]) list.children[cur].scrollIntoView({block: 'nearest'});
    }
    function showPop(mode, prefix){
      if (!ranked(mode, prefix).length){ hidePop(); return; }
      if (popMode !== mode || popPrefix !== prefix) search.value = '';
      popMode = mode; popPrefix = prefix;
      search.style.display = ranked(mode, prefix).length >= SEARCH_AT ? '' : 'none';
      search.placeholder = T(mode === 'deck' ? 'Filter decks...' : 'Filter suggestions...');
      fill();
      if (!pop.parentNode) document.body.appendChild(pop);
      place();
    }
    function hidePop(){
      popMode = null; popPrefix = ''; search.value = '';
      if (pop.parentNode) pop.remove();
    }
    function place(){
      if (!pop.parentNode) return;
      const r = range();
      let rect = null;
      if (r){
        const rs = r.getClientRects();
        rect = rs.length ? rs[rs.length - 1] : null;
        if (!rect || (!rect.width && !rect.height)){
          const b = blockOf(r.startContainer);
          rect = (b === area ? area : b).getBoundingClientRect();
          rect = {left: rect.left + 12, top: rect.top, bottom: rect.top + 20};
        }
      } else if (popRange){
        rect = popRange;
      }
      if (!rect) return;
      popRange = {left: rect.left, top: rect.top, bottom: rect.bottom};
      const w = pop.offsetWidth, h = pop.offsetHeight;
      let x = rect.left, y = rect.bottom + 6;
      if (x + w > window.innerWidth - 8) x = Math.max(8, window.innerWidth - w - 8);
      if (y + h > window.innerHeight - 8) y = Math.max(8, rect.top - h - 6);
      pop.style.left = x + 'px'; pop.style.top = y + 'px';
    }
    function refresh(){
      const c = context();
      if (!c){ hidePop(); return; }
      showPop(c.mode, c.prefix);
    }
    function accept(){
      const e = rows[cur];
      if (!e) return;
      if (document.activeElement !== area){
        area.focus();
        if (saved){ const s = sel(); s.removeAllRanges(); s.addRange(saved); }
      }
      const c = context();
      if (!c || c.mode !== popMode){ hidePop(); return; }
      selectIn(c.block, c.anchor, c.end);
      insert(e[0]);
      if (c.mode !== 'variable'){
        const after = caret();
        if (after && after.text.charAt(after.pos) === '}') setCaret(after.block, after.pos + 1);
        else insert('}');
      }
      hidePop();
      changed();
    }
    search.addEventListener('input', function(){ fill(); place(); });
    search.addEventListener('keydown', function(e){
      if (popKey(e)) return;
      if (e.key === 'Escape'){ e.preventDefault(); e.stopPropagation(); hidePop(); restore(); }
    });
    search.addEventListener('focus', keep);
    function popKey(e){
      if (!pop.parentNode) return false;
      const k = e.key;
      if (k === 'ArrowDown' || k === 'ArrowUp' || k === 'PageDown' || k === 'PageUp'){
        e.preventDefault(); e.stopPropagation();
        mark(cur + ({ArrowDown: 1, ArrowUp: -1, PageDown: 6, PageUp: -6})[k], true);
        return true;
      }
      if (k === 'Tab' || k === 'Enter'){
        e.preventDefault(); e.stopPropagation();
        accept();
        return true;
      }
      return false;
    }

    // -- {placeholders} highlighted (display only, the HTML is unchanged): the CSS Highlight API --
    const known = function(v){ return (D.vars || []).some(function(e){ return e[0] === v; }); };
    function highlight(){
      const HL = window.CSS && window.CSS.highlights;
      if (!HL || typeof Highlight === 'undefined') return;
      const ok = new Highlight(), bad = new Highlight();
      const blocks = area.querySelectorAll(BLOCK_SEL);
      (blocks.length ? Array.prototype.slice.call(blocks) : [area]).forEach(function(b){
        if (b.querySelector(BLOCK_SEL)) return;  // (its own blocks are read)
        const text = textOf(b);
        let m;
        TEMPLATE_RE.lastIndex = 0;
        while ((m = TEMPLATE_RE.exec(text))){
          const p = pointAt(b, m.index), q = pointAt(b, m.index + m[0].length), r = new Range();
          try { r.setStart(p.node, p.offset); r.setEnd(q.node, q.offset); } catch (e) { continue; }
          (known(m[1]) ? ok : bad).add(r);
        }
      });
      HL.set('ddte-ok', ok);
      HL.set('ddte-bad', bad);
      let hs = document.getElementById('ddte-hl');
      if (!hs){ hs = el('style'); hs.id = 'ddte-hl'; document.head.appendChild(hs); }
      const a = getComputedStyle(area).getPropertyValue('--dd-accent').trim() || '#3b82f6';
      const tint = DD.theme && DD.theme.is_dark === false ? 18 : 30;
      const css = '::highlight(ddte-ok){background-color:color-mix(in srgb,' + a + ' ' + tint + '%,transparent)}'
        + '::highlight(ddte-bad){text-decoration:underline wavy #ef4444}';
      if (hs.textContent !== css) hs.textContent = css;
    }

    // -- typing --
    function empty(){ area.classList.toggle('empty', !area.textContent.replace(/\u200b/g, '') && !area.querySelector('hr,li')); }
    let changeT = 0;
    function changed(){
      empty();
      highlight();
      if (opts.onChange){ clearTimeout(changeT); changeT = setTimeout(function(){ opts.onChange(extract(area)); }, 250); }
    }
    area.addEventListener('keydown', function(e){
      if (e.isComposing) return;
      if (popKey(e)) return;
      if (e.key === 'Escape' && pop.parentNode){ e.preventDefault(); e.stopPropagation(); hidePop(); return; }
      if ((e.key === 'Enter') && !e.shiftKey && !e.ctrlKey && !e.metaKey && enterKey(e)) return;
      const r = range();
      if (!r || e.ctrlKey || e.metaKey || e.altKey) return;
      if (e.key === '}' && r.collapsed && charAfter() === '}'){
        e.preventDefault();
        const c = caret(); setCaret(c.block, c.pos + 1); hidePop();
        return;
      }
      if (e.key === '{'){ e.preventDefault(); placeholder(); changed(); return; }
      const ctx = r.collapsed ? context() : null;
      if (e.key === ':' && ctx && ctx.mode === 'variable' && ctx.prefix){ e.preventDefault(); openPair(':', '}', 'span'); changed(); return; }
      if (e.key === '|' && ctx && /^(variable|span|deck)$/.test(ctx.mode) && ctx.prefix){ e.preventDefault(); openPair('|', '}', 'unit'); changed(); return; }
      if (e.key === DECK && ctx && /^(variable|span)$/.test(ctx.mode) && ctx.prefix){ e.preventDefault(); openPair(DECK, '}', 'deck'); changed(); return; }
      if (e.key === 'Backspace' && r.collapsed){
        const c = caret();
        const pair = c && c.pos > 0 ? c.text.charAt(c.pos - 1) + c.text.charAt(c.pos) : '';
        if (pair === '{}' || pair === ':}'){
          e.preventDefault();
          selectIn(c.block, c.pos - 1, c.pos + 1);
          document.execCommand('delete');
          hidePop(); changed();
        }
      }
    });
    // Enter: "---" becomes a line; after a title, normal text again (an empty list item leaves its list by itself)
    function enterKey(e){
      if (pop.parentNode) return false;
      const c = caret();
      if (!c) return false;
      if (MD_RULE.test(c.text.trim()) && c.pos >= c.text.length && c.block !== area && c.block.tagName !== 'LI'){
        e.preventDefault();
        c.block.textContent = '';
        setCaret(c.block, 0);
        rule();
        changed();
        return true;
      }
      const h = heading();
      if (h && c.pos >= c.text.length){
        e.preventDefault();
        setCaret(newPara(h), 0);
        changed(); sync();
        return true;
      }
      return false;
    }
    // Markdown as it is typed
    area.addEventListener('input', function(e){
      try { if (e.inputType === 'insertText' && e.data) markdown(e.data); } catch (err) { DD.log('text editor: ' + err); }
      changed();
      refresh();
    });
    function markdown(typed){
      const c = caret();
      if (!c || context()) return;
      const before = c.text.slice(0, c.pos);
      if (typed === ' '){
        const m = MD_BLOCK.exec(before.slice(0, -1));
        if (!m || c.block.closest('li')) return;
        selectIn(c.block, 0, c.pos);
        document.execCommand('delete');
        const t = m[1];
        if (t.charAt(0) === '#') exec('formatBlock', 'h' + t.length);
        else exec(/\d/.test(t) ? 'insertOrderedList' : 'insertUnorderedList');
        return;
      }
      if (typed !== '*' && typed !== '~') return;
      for (let i = 0; i < MD_INLINE.length; i++){
        const m = MD_INLINE[i][0].exec(before);
        if (!m) continue;
        const kind = MD_INLINE[i][1];
        const whole = kind === 'i' ? m[0].slice(m[0].indexOf('*')) : m[0];
        const start = c.pos - whole.length;
        selectIn(c.block, start, c.pos);
        insert(m[1]);
        selectIn(c.block, start, start + m[1].length);
        const cmd = {b: 'bold', i: 'italic', s: 'strikeThrough'}[kind];
        exec(cmd);
        // what follows is not bold / italic / struck: typed after the formatted words, outside their tag
        const end = pointAt(c.block, start + m[1].length);
        const tags = {b: 'b,strong', i: 'i,em', s: 's,strike,del'}[kind];
        const from = end.node.nodeType === 3 ? end.node.parentNode : end.node;
        const fmt = from.closest && from.closest(tags);
        if (fmt && fmt !== c.block && c.block.contains(fmt)){
          const after = document.createTextNode('​');
          fmt.parentNode.insertBefore(after, fmt.nextSibling);
          const r = document.createRange(), s = sel();
          r.setStart(after, 1); r.collapse(true);
          s.removeAllRanges(); s.addRange(r);
        } else {
          setCaret(c.block, start + m[1].length);
          if (document.queryCommandState(cmd)) exec(cmd);
        }
        return;
      }
    }
    area.addEventListener('paste', function(e){
      const cd = e.clipboardData;
      if (!cd) return;
      const html = cd.getData('text/html'), text = cd.getData('text/plain');
      let put = null;
      if (html) put = clean(html.replace(/^[\s\S]*<!--StartFragment-->|<!--EndFragment-->[\s\S]*$/g, ''));
      else if (text && MD_PASTED.test(text)) put = mdToHtml(text);
      if (put == null) return;
      e.preventDefault();
      document.execCommand('insertHTML', false, put);
    });
    area.addEventListener('drop', function(e){ if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length) e.preventDefault(); });
    // a right click on a variable: whether its changes fade the text ("~")
    area.addEventListener('contextmenu', function(e){
      const at = document.caretRangeFromPoint ? document.caretRangeFromPoint(e.clientX, e.clientY) : null;
      if (!at || !area.contains(at.startContainer)) return;
      const block = blockOf(at.startContainer), text = textOf(block), pos = offsetIn(block, at.startContainer, at.startOffset);
      let m, hit = null;
      TEMPLATE_RE.lastIndex = 0;
      while ((m = TEMPLATE_RE.exec(text))) if (m.index <= pos && pos <= m.index + m[0].length){ hit = m; break; }
      if (!hit) return;
      e.preventDefault();
      const fixed = !!hit[5], start = hit.index, raw = hit[0];
      const menu = el('div', 'ddte-menu');
      menu.setAttribute('data-nt', '');
      const item = el('div');
      item.appendChild(el('span', null, fixed ? '' : '\u2713'));
      item.appendChild(document.createTextNode(T('Animate changes of {name}', {name: '{' + hit[1] + '}'})));
      item.title = T('When off, the text does not fade when this value changes.');
      menu.appendChild(item);
      document.body.appendChild(menu);
      menu.style.left = Math.min(e.clientX, window.innerWidth - menu.offsetWidth - 8) + 'px';
      menu.style.top = Math.min(e.clientY, window.innerHeight - menu.offsetHeight - 8) + 'px';
      function close(){ menu.remove(); document.removeEventListener('mousedown', out, true); }
      function out(ev){ if (!menu.contains(ev.target)) close(); }
      document.addEventListener('mousedown', out, true);
      item.onmousedown = function(ev){ ev.preventDefault(); };
      item.onclick = function(){
        close();
        area.focus();
        selectIn(block, start, start + raw.length);
        insert(fixed ? raw.slice(0, -2) + '}' : raw.slice(0, -1) + '~}');
        changed();
      };
    });

    // -- the toolbar follows the cursor --
    function sync(){
      const r = range();
      if (!r) return;
      keep();
      const q = function(c){ try { return document.queryCommandState(c); } catch (e) { return false; } };
      btns.bold.classList.toggle('on', q('bold'));
      btns.italic.classList.toggle('on', q('italic'));
      btns.underline.classList.toggle('on', q('underline'));
      btns.strike.classList.toggle('on', q('strikeThrough'));
      let n = r.startContainer.nodeType === 1 ? r.startContainer : r.startContainer.parentNode;
      if (!r.collapsed && r.startContainer.nodeType === 3 && r.startOffset === r.startContainer.nodeValue.length){
        const p = pointAt(blockOf(r.startContainer), offsetIn(blockOf(r.startContainer), r.startContainer, r.startOffset) + 1);
        if (p.node.nodeType === 3) n = p.node.parentNode;
      }
      const cs = getComputedStyle(n);
      btns.shadow.classList.toggle('on', !!cs.textShadow && cs.textShadow !== 'none');
      const fam = (cs.fontFamily || '').split(',')[0].replace(/["']/g, '').trim();
      let own = null;
      for (let x = n; x && x !== area; x = x.parentNode) if (x.style && x.style.fontFamily || x.getAttribute && x.getAttribute('face')){ own = x; break; }
      if (!own) font.value = '';
      else {
        if (fam && !Array.prototype.some.call(font.options, function(o){ return o.value === fam; })) font.appendChild(new Option(fam, fam));
        font.value = fam;
      }
      if (document.activeElement !== size) size.value = String(Math.round(parseFloat(cs.fontSize) * 0.75 * 2) / 2);
      let col = null;
      for (let x = n; x && x !== area; x = x.parentNode) if (x.style && x.style.color && x.style.color !== 'inherit' || x.getAttribute && x.getAttribute('color')){ col = cs.color; break; }
      colorBtn.style.color = col || '';
      const b = blockOf(n);
      head.value = /^H[1-3]$/.test(b.tagName) ? b.tagName.toLowerCase() : 'p';
      const li = n.closest && n.closest('li');
      const lst = li && li.parentNode;
      btns.ul.classList.toggle('on', !!lst && lst.tagName === 'UL');
      btns.ol.classList.toggle('on', !!lst && lst.tagName === 'OL');
      const al = getComputedStyle(b === area ? area : b).textAlign;
      const which = al === 'center' ? 'center' : (al === 'right' || al === 'end') ? 'right' : 'left';
      ['left', 'center', 'right'].forEach(function(k){ btns[k].classList.toggle('on', k === which); });
    }
    function onSel(){
      if (!root.isConnected){ document.removeEventListener('selectionchange', onSel); hidePop(); return; }
      if (!range()) return;
      sync();
      if (pop.parentNode) refresh();
    }
    document.addEventListener('selectionchange', onSel);
    area.addEventListener('blur', function(){
      setTimeout(function(){ if (document.activeElement !== search && document.activeElement !== area) hidePop(); }, 0);
    });
    window.addEventListener('resize', place);
    area.addEventListener('scroll', place);

    try { document.execCommand('defaultParagraphSeparator', false, 'p'); } catch (e) {}
    function set(t){
      area.innerHTML = templateHtml(t) || '<p><br /></p>';
      hidePop();
      empty();
      highlight();
    }
    set(opts.template || '');
    showHelp(helpOpen);
    data().then(function(d){
      D = Object.assign(D, d);
      helpBody.innerHTML = D.help || '';
      showHelp(helpOpen);
      highlight();
    });
    return {
      el: root,
      area: area,
      get: function(){ return extract(area); },
      set: set,
      focus: function(){
        area.focus();
        // the cursor at the end of the last paragraph (not after it, at the editor's top)
        let last = area.lastElementChild;
        while (last && last.lastElementChild && last.lastElementChild.tagName !== 'BR') last = last.lastElementChild;
        if (last && last.tagName === 'HR') last = null;
        if (last) setCaret(blockOf(last) === area ? last : blockOf(last), textOf(blockOf(last) === area ? last : blockOf(last)).length);
        else { const r = document.createRange(), s = sel(); r.selectNodeContents(area); r.collapse(false); s.removeAllRanges(); s.addRange(r); }
      },
      busy: function(){ return !!pop.parentNode || !!document.querySelector('.ddte-menu'); },
      destroy: function(){ hidePop(); document.removeEventListener('selectionchange', onSel); window.removeEventListener('resize', place); root.remove(); },
    };
  };

  // the text on the accent colour: dark on a light accent, else white (as dialogs.js)
  function onAccent(){
    const c = el('span');
    c.style.color = 'var(--dd-accent)';
    document.body.appendChild(c);
    const m = getComputedStyle(c).color.match(/[\d.]+/g) || [];
    c.remove();
    const lin = function(v){ v = Number(v) / 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    const L = m.length >= 3 ? 0.2126 * lin(m[0]) + 0.7152 * lin(m[1]) + 0.0722 * lin(m[2]) : 0;
    return L > 0.5 ? '#1b1b1d' : '#fff';
  }

  // ---- the dialog ----
  DD.editText = function(o){
    o = o || {};
    style();
    return new Promise(function(resolve){
      const veil = el('div', 'ddte-veil'), box = el('div', 'ddte-box');
      box.setAttribute('role', 'dialog');
      box.setAttribute('data-nt', '');
      veil.appendChild(box);
      box.appendChild(el('h2', 'ddte-title', T(o.title || 'Add Text Widget')));
      const ed = DD.textEditor(box, {template: o.template || ''});
      const acts = el('div', 'ddte-acts');
      const cancel = el('button', 'ddte-btn', T('Cancel'));
      const ok = el('button', 'ddte-btn ok', T(o.ok || 'Add'));
      cancel.type = ok.type = 'button';
      acts.appendChild(cancel); acts.appendChild(ok);
      box.appendChild(acts);
      function close(v){
        document.removeEventListener('keydown', key, true);
        ed.destroy();
        veil.remove();
        resolve(v);
      }
      function key(e){
        if (!veil.contains(e.target) && e.target !== document.body) return;
        if (e.key === 'Escape' && !ed.busy()){ e.preventDefault(); e.stopPropagation(); close(null); }
        else if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)){ e.preventDefault(); e.stopPropagation(); close(ed.get().trim()); }
      }
      // the page's own keys (its shortcuts) stay out of the dialog
      ['keydown', 'keyup', 'keypress'].forEach(function(t){ veil.addEventListener(t, function(e){ e.stopPropagation(); }); });
      cancel.onclick = function(){ close(null); };
      ok.onclick = function(){ close(ed.get().trim()); };
      ok.style.color = onAccent();
      veil.addEventListener('mousedown', function(e){ if (e.target === veil) close(null); });
      document.addEventListener('keydown', key, true);
      document.body.appendChild(veil);
      ed.focus();
    });
  };
  DD.textTemplate = {normalize: normalize, html: templateHtml, clean: clean, markdown: mdToHtml};
})();
