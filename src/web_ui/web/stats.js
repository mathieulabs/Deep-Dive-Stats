/* Stat cards row of the Deep Dive window. */
(function(){
  'use strict';

  const VALUE_FS = 15.0, TITLE_FS = 6.8, SUB_FS = 7.0, H_MARGIN = 8;
  const THRESHOLD_MULT = 1.2, MIN_FIT = 0.4, MAX_FIT = 1.0, FIT_EXP = 1.6;
  const FIT_VALUE_BASE = 5.5, FIT_VALUE_GAIN = 7.0, FIT_TITLE_BASE = 3.5, FIT_TITLE_GAIN = 2.7;
  const FIT_MARGIN_BASE = 3, FIT_MARGIN_GAIN = 5, GROW_EXP = 0.5, MAX_GROW = 1.3;
  const BASE_H = 32, HEIGHT_GAIN = 32, SPACING = 6, RADIUS = 14;
  const PT = 96 / 72; // point sizes at 96 dpi

  function parse(hex){
    const h = String(hex || '#888888').replace('#', '');
    return [0, 2, 4].map(function(o){ return parseInt(h.substr(o, 2), 16) || 0; });
  }
  function mix(a, z, t){ return [0, 1, 2].map(function(i){ return Math.round(a[i] + (z[i] - a[i]) * t); }); }
  function rgba(c, a){ return 'rgba(' + c[0] + ',' + c[1] + ',' + c[2] + ',' + Math.max(0, Math.min(1, a)).toFixed(3) + ')'; }
  function lighter(c, f){ // lighter(f): HSV value * f/100
    const mx = Math.max.apply(null, c), mn = Math.min.apply(null, c), d = mx - mn;
    let h = 0;
    if (d){ if (mx === c[0]) h = ((c[1] - c[2]) / d) % 6; else if (mx === c[1]) h = (c[2] - c[0]) / d + 2; else h = (c[0] - c[1]) / d + 4; }
    const s = mx ? d / mx : 0, v = Math.min(255, mx * f / 100);
    const k = v * s, x = k * (1 - Math.abs(h % 2 - 1)), m = v - k;
    const sec = Math.floor(((h % 6) + 6) % 6);
    const t = [[k, x, 0], [x, k, 0], [0, k, x], [0, x, k], [x, 0, k], [k, 0, x]][sec];
    return t.map(function(q){ return Math.round(q + m); });
  }

  // tinted_card_surface(): 0-45 % = pure translucent stat color (0 % black/grey, bright over wallpapers);
  // above 45 %, gently deepens toward a richer shade while keeping 100 % saturation.
  function surfaceCss(baseHex, st, dark){
    const c = parse(baseHex);
    const k = Math.max(0, Math.min(1, st.glass_int));
    let hi, mid, lo, hiA = 1, midA = 1, loA = 1;
    if (dark){
      const t = Math.pow(k, 1.08), u = Math.max(0, (k - 0.45) / 0.55);
      hi = mix(lighter(c, 118), c, 0.35 * u);
      mid = mix(c, [0, 0, 0], 0.38 * u);
      lo = mix(c, [0, 0, 0], 0.48 * u);
      hiA = 0.08 + 0.80 * t;
      midA = 0.04 + 0.72 * t;
      loA = 0.02 + 0.62 * t;
    } else {
      const white = parse(st.surface);
      hi = mix(white, c, 0.22 + k * 0.38);
      mid = mix(white, c, 0.12 + k * 0.26);
      lo = mix(white, c, 0.06 + k * 0.18);
      hiA = 0.18 + 0.78 * k;
      midA = 0.12 + 0.76 * k;
      loA = 0.08 + 0.74 * k;
    }
    return 'radial-gradient(ellipse 125% 125% at 0 0,' + rgba(hi, hiA) + ' 0%,' + rgba(mid, midA) + ' 55%,' + rgba(lo, loA) + ' 100%)';
  }

  // Above 45 % opacity, lift only the stat value slightly toward a bright tint of its own color so it stays legible
  // without ever overriding the user's Title Color.
  function valueColor(baseHex, cs, dark){
    const k = cs && cs.glass ? Math.max(0, Math.min(1, +cs.glass_int || 0)) : 0;
    if (k <= 0.45) return baseHex;
    const u = (k - 0.45) / 0.55, c = parse(baseHex);
    return dark ? rgba(mix(c, [255, 255, 255], 0.62 * u), 1) : rgba(mix(c, [0, 0, 0], 0.32 * u), 1);
  }

  // the colored glow border (1.35 px gradient along the diagonal).
  function borderCss(baseHex, st, dark, strength){
    const c = parse(baseHex), a = strength;
    let g;
    if (!dark){
      g = [rgba(lighter(c, 118), 0.65 * a) + ' 0%', rgba(lighter(c, 108), 0.82 * a) + ' 35%', rgba(c, 0.92 * a) + ' 100%'];
    } else {
      const hi = mix(lighter(c, 160), [255, 255, 255], 0.55);
      g = [rgba(hi, 0.88 * a) + ' 0%', rgba(lighter(c, 135), 0.92 * a) + ' 35%', rgba(c, 0.78 * a) + ' 100%'];
    }
    return 'linear-gradient(135deg,' + g.join(',') + ')';
  }

  // the card's 1.35 px gradient ring, drawn as an SVG stroke: a CSS mask cuts its inner edge on the device pixels, so at
  // some zooms (125 %, 150 %) the ring is thicker on one side than the other; a stroke is drawn alike all around
  let ringN = 0;
  function ring(d, css){
    d.style.setProperty('--sc-border', css);
    const bd = d.querySelector('.dd-sc-bd'); if (!bd) return;
    let svg = bd.querySelector('svg');
    if (!svg){
      const id = 'ddscring' + (++ringN);
      bd.innerHTML = '<svg width="100%" height="100%" style="position:absolute;left:0;top:0;overflow:visible"><defs><linearGradient id="' + id + '" x1="0" y1="0" x2="1" y2="1"></linearGradient></defs>' +
        '<rect x="0.7" y="0.7" rx="13.3" ry="13.3" fill="none" stroke-width="1.35" stroke="url(#' + id + ')" style="width:calc(100% - 1.4px);height:calc(100% - 1.4px)"/></svg>';
      svg = bd.querySelector('svg');
    }
    const stops = [], re = /(rgba?\([^)]*\)|#[0-9a-fA-F]{3,8})\s+([\d.]+)%/g;
    let m; while ((m = re.exec(css || ''))) stops.push('<stop offset="' + m[2] + '%" stop-color="' + m[1] + '"/>');
    svg.style.display = stops.length ? '' : 'none';
    svg.querySelector('linearGradient').innerHTML = stops.join('');
  }

  // fit: fonts from the cards' texts, height from a typical value
  function fit(width, total){
    const thr = total * THRESHOLD_MULT;
    if (width < thr && width > 0) return [Math.pow(Math.max(MIN_FIT, Math.min(MAX_FIT, width / thr)), FIT_EXP), 1];
    let grow = 1; if (thr > 0 && width > thr) grow = Math.min(MAX_GROW, Math.pow(width / thr, GROW_EXP));
    return [1, grow];
  }
  function typography(width, totalIdeal, scale, heightIdeal){
    const user = Math.max(0.5, Math.min(1.8, (scale || 100) / 100));
    let [adj, grow] = fit(width, totalIdeal), hAdj = adj, hGrow = grow;
    if (heightIdeal != null){ [hAdj, hGrow] = fit(width, heightIdeal); adj = Math.min(adj, hAdj); grow = Math.min(grow, hGrow); }
    let val, title, sub, hm;
    if (adj < 1){
      val = FIT_VALUE_BASE + FIT_VALUE_GAIN * adj; title = FIT_TITLE_BASE + FIT_TITLE_GAIN * adj;
      sub = val * 0.5 + 2.0; hm = FIT_MARGIN_BASE + FIT_MARGIN_GAIN * adj;
    } else { val = VALUE_FS; title = TITLE_FS; sub = SUB_FS; hm = H_MARGIN; }
    const fs = user * grow;
    return {val: val * fs, title: title * fs, sub: sub * fs, hm: hm * fs, h: (BASE_H + HEIGHT_GAIN * hAdj) * user * hGrow};
  }


  // ---- value roll: the number counts from the old value to the new one ----
  const ROLL_MS = 180;  // ROLL_ANIM_DURATION_MS, InOutCubic
  function parseRoll(text){
    const m = /^([^\d\-+]*)(-?\d[\d,]*(?:\.\d+)?)(.*)$/.exec(String(text).trim());
    if (!m || !/^\s*[%a-zA-Z]*$/.test(m[3])) return null;
    const num = parseFloat(m[2].replace(/,/g, ''));
    if (!isFinite(num)) return null;
    const sfx = m[3];
    return {kind: sfx.trim() === '%' ? 'percent' : 'number', val: num, dec: (m[2].split('.')[1] || '').length, prefix: m[1], suffix: sfx};
  }
  function fmtRoll(v, dec, kind){
    let t = Math.abs(v).toFixed(dec);
    if (kind !== 'percent'){ const p = t.split('.'); p[0] = p[0].replace(/\B(?=(\d{3})+(?!\d))/g, ','); t = p.join('.'); }
    return (v < 0 ? '-' : '') + t;
  }
  function zeroFor(text){
    const p = parseRoll(text);
    if (!p || Math.abs(p.val) < 1e-9) return null;
    return p.prefix + fmtRoll(0, p.dec, p.kind) + (p.kind === 'percent' ? '%' : p.suffix);
  }
  // ---- digits that roll (Stat_Num_Anim 'roll', as a view counter). The new text is laid out at once, hidden: the card
  // never changes its layout while the digits move (no width animated, nothing reflows, nothing shakes). Over it, each
  // character is drawn on its own at its measured place (in em, so a font size set by the card's layout right after
  // scales it too), and only moves by transform / opacity: the old text and the new one lined up from the right, a
  // character that changed leaves upward while the new one comes from below (downward when the value goes down), the
  // rightmost first; the others glide from their old place to the new one (a number that gains a digit moves over as
  // a whole). At the end the plain text again, at the very same places ----
  const SLOT_MS = 420, SLOT_STAGGER = 25, SLOT_PAD = 4;
  // the characters of a value by their place in the number, as a counter lines them up: the integer digits (and
  // their separators) from the right, the decimals from the left, the text before and after as one piece each (a unit
  // that changes, h -> min, goes as a whole). "1.48 h" and "27.80 min": 1 with 7, 2 comes, . stays, 48 with 80, " h"
  // gives way to " min" (lined up from the right, the point rolled into a digit and the unit's letters into digits)
  function slotParts(list){
    const s = list.map(function(c){ return c.ch; }).join('');
    const i0 = s.search(/\d/);
    if (i0 < 0) return [{key: 'T', ch: s, x: list.length ? list[0].x : 0}];
    let i1 = i0; for (let i = i0; i < s.length; i++){ if (/\d/.test(s[i])) i1 = i; else if (!/[.,\u00a0\u202f' ]/.test(s[i])) break; }
    const body = s.slice(i0, i1 + 1);
    // the decimal mark: the last separator if both kinds are there, else a lone '.' or ',' not followed by 3 digits
    let dm = -1;
    const lp = body.lastIndexOf('.'), lc = body.lastIndexOf(',');
    if (lp >= 0 && lc >= 0) dm = Math.max(lp, lc);
    else { const k = Math.max(lp, lc); if (k >= 0 && body.indexOf(body[k]) === k && body.length - k - 1 !== 3) dm = k; }
    const out = [];
    if (i0 > 0) out.push({key: 'P', ch: s.slice(0, i0), x: list[0].x});
    const intEnd = dm >= 0 ? i0 + dm : i1 + 1;
    for (let i = i0; i < intEnd; i++) out.push({key: 'I' + (intEnd - 1 - i), ch: list[i].ch, x: list[i].x});
    if (dm >= 0){
      out.push({key: 'D', ch: list[i0 + dm].ch, x: list[i0 + dm].x});
      for (let i = i0 + dm + 1; i <= i1; i++) out.push({key: 'F' + (i - i0 - dm - 1), ch: list[i].ch, x: list[i].x});
    }
    if (i1 + 1 < s.length) out.push({key: 'S', ch: s.slice(i1 + 1), x: list[i1 + 1].x});
    return out;
  }
  function slotRoll(v, oldT, newT, up){
    // a roll still running (zoom steps a few hundred ms apart): taken over where its characters are now, instead of
    // jumping to its end first
    const prev = v._slotTake ? v._slotTake() : null;
    if (v._slotEnd) v._slotEnd();
    // the same pace for every change (a zoom, a deck, a period), as a counter: the Deep Dive's calm tempo, meant for
    // the charts' changes, made a period's roll slower than a zoom's (1.3 times, the digits one after the other)
    const k = DD.speed ? DD.speed() : 1, ms = SLOT_MS * k;
    const cs = getComputedStyle(v), fs = parseFloat(cs.fontSize) || 16;
    let lhPx = parseFloat(cs.lineHeight); if (!isFinite(lhPx)) lhPx = fs * 1.2;
    const lh = lhPx / fs, PAD = SLOT_PAD;
    const wrap = document.createElement('span'), txt = document.createElement('span'), lay = document.createElement('span');
    wrap.style.cssText = 'display:inline-block;position:relative;white-space:pre';
    txt.style.cssText = 'white-space:pre';
    // clipped above and below (a character goes out of the line as it leaves); wider than the text by PAD em on each
    // side, so a longer old text is not cut. A plain overflow clip (a clip-path made it repaint on every frame)
    lay.style.cssText = 'position:absolute;left:-' + PAD + 'em;top:0;right:-' + PAD + 'em;height:' + lh + 'em;overflow:hidden;pointer-events:none';
    wrap.append(txt, lay);
    const boxes = function(text){
      txt.textContent = text;
      const node = txt.firstChild, base = wrap.getBoundingClientRect(), out = [];
      if (node){
        const r = document.createRange(); let i = 0;
        for (const ch of Array.from(node.data)){ r.setStart(node, i); r.setEnd(node, i + ch.length); out.push({ch: ch, x: (r.getBoundingClientRect().left - base.left) / fs}); i += ch.length; }
      }
      return {list: out, left: base.left};
    };
    v.textContent = ''; v.appendChild(wrap);
    // the value's box is as wide as the new text and clips (overflow: hidden, for a text too long for its card): an
    // old text longer than the new one had its leftmost digit cut while it left
    v.style.overflow = 'visible';
    const A = boxes(String(oldT)), B = boxes(String(newT));
    txt.style.visibility = 'hidden';
    const dx = (A.left - B.left) / fs;   // where the old text was, from the new one's start (a centered number moves)
    const E = 'cubic-bezier(0.22, 0.8, 0.25, 1)', anims = [];
    // a character: from (x0, y0, o0) to (x1, y1, o1), in em from the text's start; j: its place in the number (slotParts)
    const put = function(ch, x0, y0, o0, x1, y1, o1, delay, j, dur){
      const c = document.createElement('span');
      c.style.cssText = 'position:absolute;left:0;top:0;white-space:pre;line-height:' + lh + 'em';
      c.textContent = ch; lay.appendChild(c);
      c._j = j; c._in = o1 > 0; c._to = [x1, y1];
      anims.push(c.animate([{transform: 'translate(' + (x0 + PAD) + 'em,' + y0 + 'em)', opacity: o0}, {transform: 'translate(' + (x1 + PAD) + 'em,' + y1 + 'em)', opacity: o1}],
        {duration: dur || ms, delay: delay, easing: E, fill: 'both'}));
    };
    // the previous roll's characters where they are now: those coming in start the new roll from there (in place of
    // the old text's resting characters), those going out go on leaving from there
    const from = {};
    if (prev){
      const sx = prev.fs / fs;
      prev.chars.forEach(function(q){
        const x = q.x * sx + dx, y = q.y * sx;
        if (q.in){ if (q.j != null) from[q.j] = {x: x, y: y, o: q.o}; }
        else if (q.o > 0.01) put(q.ch, x, y, q.o, q.to[0] * sx + dx, q.to[1] * sx, 0, 0, null, ms * 0.6);
      });
    }
    const PA = slotParts(A.list), PB = slotParts(B.list), dy = up ? 1 : -1;
    const byA = {}; PA.forEach(function(q){ byA[q.key] = q; });
    const byB = {}; PB.forEach(function(q){ byB[q.key] = q; });
    // the new text's places from the right (the rightmost rolls first), then those only the old text had
    const order = PB.map(function(q){ return q.key; }).reverse().concat(PA.map(function(q){ return q.key; }).reverse().filter(function(key){ return !byB[key]; }));
    let rank = 0;
    for (const j of order){
      const a = byA[j], b = byB[j];
      const f = a ? (from[j] || {x: a.x + dx, y: 0, o: 1}) : null, xb = b ? b.x : null;
      if (a && b && a.ch === b.ch){ put(b.ch, f.x, f.y, f.o, xb, 0, 1, 0, j); continue; }
      const delay = rank * SLOT_STAGGER * k; rank++;
      // straight up / down, each at its own place (the old one where it was, the new one where it lands): from the old
      // one's place the new one came in on a slant when the text changed length (1.48 h -> 27.80 min)
      if (a) put(a.ch, f.x, f.y, f.o, f.x, f.y - dy * lh, 0, delay, null);
      if (b) put(b.ch, xb, dy * lh, 0, xb, 0, 1, delay, j);
    }
    let done = false;
    // dev trace: the frames while it rolls (a long gap: the page could not keep up)
    const tr = {n: 0, max: 0, last: performance.now(), t0: performance.now()};
    (function fr(now){ if (done) return; tr.n++; tr.max = Math.max(tr.max, now - tr.last); tr.last = now; requestAnimationFrame(fr); })(tr.t0);
    v._slotTake = function(){
      const chars = [];
      Array.prototype.forEach.call(lay.children, function(c){
        const st = getComputedStyle(c), m = new DOMMatrixReadOnly(st.transform === 'none' ? undefined : st.transform);
        chars.push({ch: c.textContent, x: m.m41 / fs - PAD, y: m.m42 / fs, o: +st.opacity, in: c._in, j: c._j, to: c._to});
      });
      return {chars: chars, fs: fs};
    };
    const end = function(){ if (done) return; done = true; v._slotEnd = null; v._slotTake = null;
      if (DD.dev) DD.trace('ANIMTRACE statroll done ' + newT + ' after ' + Math.round(performance.now() - tr.t0) + ' ms (' + ms.toFixed(0) + ' planned), ' + tr.n + ' frames, longest gap ' + Math.round(tr.max) + ' ms');
      anims.forEach(function(x){ try { x.cancel(); } catch (e) {} }); v.style.overflow = ''; v.textContent = newT; };
    v._slotEnd = end;
    Promise.all(anims.map(function(x){ return x.finished.catch(function(){}); })).then(end);
    if (!anims.length) end();
    if (DD.dev) DD.trace('ANIMTRACE statroll layout ' + oldT + ' -> ' + newT + ' shift ' + dx.toFixed(3) + 'em, ' + rank + ' rolled' + (prev ? ', took over a running roll (' + prev.chars.length + ' characters where they were)' : '') + ', font ' + fs + 'px');
  }
  function isNA(t){ return /^(n\/?a|-|—|\.\.\.)$/i.test(String(t).trim()); }
  const TU = {h: 'hour', hr: 'hour', min: 'minute', m: 'minute'};
  function rollPlan(oldT, newT){
    let a = parseRoll(oldT), b = parseRoll(newT);
    if (!a || !b){
      if (a && a.kind === 'percent' && isNA(newT)) b = {kind: 'percent', val: 0, dec: a.dec, prefix: a.prefix, suffix: '%'};
      else if (b && b.kind === 'percent' && isNA(oldT)) a = {kind: 'percent', val: 0, dec: b.dec, prefix: b.prefix, suffix: '%'};
    }
    if (!a || !b || a.kind !== b.kind) return null;
    if (a.prefix !== b.prefix || a.suffix !== b.suffix){
      const ta = TU[a.suffix.trim()], tb = TU[b.suffix.trim()];
      if (a.kind === 'number' && a.prefix === b.prefix && ta && tb){
        const hour = ta === 'hour' || tb === 'hour';
        const conv = function(v, u){ return hour ? (u === 'hour' ? v : v / 60) : (u === 'minute' ? v : v * 60); };
        a = Object.assign({}, a, {val: conv(a.val, ta)}); b = Object.assign({}, b, {val: conv(b.val, tb), dec: Math.max(a.dec, b.dec, hour ? 2 : 0)});
        a.suffix = b.suffix = hour ? ' h' : ' min';
      } else return null;
    }
    if (Math.abs(a.val - b.val) < 1e-9) return null;
    return {from: a.val, to: b.val, dec: b.dec, kind: b.kind, prefix: b.prefix, suffix: b.suffix};
  }

  const MINW = 0.62;   // a card narrower than this (times its ideal width) goes to the next line
  const LINE_GAP = 4;

  // Stat card SVG icons by metric type (toggleable globally or per card via Show Icons)
  const STAT_ICONS = {
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    timer: '<circle cx="12" cy="13" r="8"/><path d="M12 9v4l2 2M9 2h6"/>',
    layers: '<path d="M12 3 2 8l10 5 10-5-10-5zM2 13l10 5 10-5M2 18l10 5 10-5"/>',
    check: '<circle cx="12" cy="12" r="9"/><path d="m9 12 2 2 4-4"/>',
    // spans x 3.5-21.5: reaches as far right as the other icons (a bit further, as its tip tapers),
    // so the gap to the label looks the same on every card; its right side one even curve up to the tip
    flame: '<path d="M12.5 2C14.5 6 21.5 8 21.5 13a9 9 0 1 1-18 0c0-2 .6-3.8 1.8-5.2 1.1 1.7 2.3 2.4 2.9 2.4-.6-3 .8-6.2 4.3-8.2z"/>',
    trophy: '<path d="M6 9H4a2 2 0 0 1-2-2V5h4M18 9h2a2 2 0 0 0 2-2V5h-4M6 4h12v5a6 6 0 0 1-12 0V4zM12 15v5M8 20h8"/>',
    calendar: '<rect x="3" y="4" width="18" height="17" rx="2"/><path d="M8 2v4M16 2v4M3 10h18"/>',
    again: '<path d="M3 12a9 9 0 1 0 3-6.7L3 8M3 3v5h5"/>',
    cards: '<rect x="5" y="5" width="14" height="16" rx="2"/><path d="M9 2h8a2 2 0 0 1 2 2v12"/>',
    plus: '<circle cx="12" cy="12" r="9"/><path d="M12 8v8M8 12h8"/>',
    book: '<path d="M2 6h7a3 3 0 0 1 3 3v11a2 2 0 0 0-2-2H2zM22 6h-7a3 3 0 0 0-3 3v11a2 2 0 0 1 2-2h8z"/>',
    sprout: '<path d="M12 20V10M12 14c-4 0-7-3-7-7 4 0 7 3 7 7zM12 11c4 0 7-3 7-7-4 0-7 3-7 7z"/>',
    shield: '<path d="M12 2 4 5v6c0 5.5 3.4 9.7 8 11 4.6-1.3 8-5.5 8-11V5l-8-3z"/><path d="m9 12 2 2 4-4"/>',
    pause: '<circle cx="12" cy="12" r="9"/><path d="M10 9v6M14 9v6"/>',
    archive: '<rect x="3" y="4" width="18" height="5" rx="1"/><path d="M5 9v10a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V9M10 14h4"/>',
    trash: '<path d="M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14"/>',
    bell: '<path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9M10.3 21a2 2 0 0 0 3.4 0"/>',
    alert: '<path d="M12 3 3 19h18L12 3zM12 9v4M12 16h.01"/>',
    pulse: '<path d="M2 12h4l3-7 4 14 3-7h6"/>',
    anchor: '<circle cx="12" cy="5" r="2.5"/><path d="M12 7.5V21M5 12H2a10 10 0 0 0 20 0h-3"/>',
  };
  const STAT_ICON_MAP = {
    Time: 'clock', Time_Per_Day: 'clock', Time_Per_Active_Day: 'clock',
    Avg_Time: 'timer',
    Reviews: 'layers', Reviews_Per_Day: 'layers', Reviews_Per_Active_Day: 'layers', Rev_Young: 'layers', Rev_Mature: 'layers',
    Ret_All: 'check', Ret_Young: 'check', Ret_Mature: 'check', Ret_True: 'check',
    Streak: 'flame',
    Longest_Streak: 'trophy', Best_Day: 'trophy',
    Active_Days: 'calendar', Days_Learned: 'calendar',
    Again: 'again', Lapses: 'again',
    Cards_Total: 'cards', Cards_New: 'plus', Cards_Learning: 'book',
    Cards_Young: 'sprout', Cards_Mature: 'shield',
    Cards_Suspended: 'pause', Cards_Buried: 'archive', Cards_Deleted: 'trash',
    Due_Today: 'bell', Backlog: 'alert',
    Avg_Retrievability: 'pulse', Avg_Stability: 'anchor',
  };
  function statIconPath(c){
    const raw = String((c && (c.stat_key || c.key)) || '').replace(/^(Dash|Deep_Dive)_Show_/, '');
    return STAT_ICONS[STAT_ICON_MAP[raw]] || null;
  }
  function iconMode(cs){
    if (!cs) return 'inline';
    if (cs.icon_mode === 'off' || cs.icon_mode === 'inline' || cs.icon_mode === 'watermark') return cs.icon_mode;
    return cs.show_icons === false ? 'off' : 'inline';
  }
  function iconPos(cs){
    const p = cs && cs.icon_pos;
    return (p === 'tl' || p === 'tr' || p === 'bl' || p === 'br') ? p : 'tl';
  }
  function renderIcon(d, t, c, cs, dark){
    const lbl = String(c.label == null ? '' : c.label);
    const mode = iconMode(cs), pos = iconPos(cs);
    const p = (mode !== 'off' && lbl) ? statIconPath(c) : null;
    const col = p ? valueColor(c.color, cs, dark) : '';
    const sig = lbl + '|' + (p ? (mode + '|' + pos + '|' + col) : '');
    if (d._icoSig === sig) return;
    d._icoSig = sig;
    d.querySelectorAll(':scope > .dd-sc-ico').forEach(function(el){ el.remove(); });
    const mkSvg = function(cls, sw){
      const ns = 'http://www.w3.org/2000/svg';
      const svg = document.createElementNS(ns, 'svg');
      svg.setAttribute('class', 'dd-sc-ico ' + cls);
      svg.setAttribute('viewBox', '0 0 24 24');
      svg.setAttribute('fill', 'none');
      svg.setAttribute('stroke', col || 'currentColor');
      svg.setAttribute('stroke-width', sw);
      svg.setAttribute('stroke-linecap', 'round');
      svg.setAttribute('stroke-linejoin', 'round');
      svg.setAttribute('aria-hidden', 'true');
      svg.innerHTML = p;
      return svg;
    };
    if (p && mode === 'inline'){
      t.textContent = '';
      t.appendChild(mkSvg('inline', '2.1'));
      const sp = document.createElement('span'); sp.textContent = lbl;
      t.appendChild(sp);
      // an empty twin of the icon after the title: the title itself sits centered over the value. It shrinks
      // first when the card is tight, so the card's width doesn't change (idealW counts the icon once)
      const bal = document.createElement('i'); bal.className = 'dd-sc-ico-bal';
      t.appendChild(bal);
    } else {
      t.textContent = lbl;
      if (p && mode === 'watermark') d.appendChild(mkSvg('watermark ' + pos, '1.5'));
    }
  }

  DD.stats = {
    mount: function(el, spec, theme, hooks){
      hooks = hooks || {};
      const root = document.createElement('div');
      root.className = 'dd-sc-lines';
      el.appendChild(root);
      const meas = document.createElement('canvas').getContext('2d');
      let cur = spec, th = theme, byKey = {}, lines = [], rolls = {};

      function textW(txt, pt, weight){
        meas.font = weight + ' ' + (pt * PT) + 'px "Segoe UI",-apple-system,sans-serif';
        return meas.measureText(txt).width;
      }
      // the widest of the value and the title (upper case, bold, letter
      // spacing 0.8 px; none in the languages without capitals, i18n.adapt_qss), + 24 + 10. pin: the pinned sizes
      // (sizing.PINNED_*), tmul: the title size multiplier (with i18n.caption_scale), s: the card's scale.
      function idealW(value, label, pin, tmul, s, hasIcon){
        const nocase = document.documentElement.classList.contains('dd-nocase');
        let t = String(label == null ? '' : label);
        if ((DD.i18n && DD.i18n['@lang']) === 'tr') t = t.replace(/i/g, '\u0130');
        t = t.toUpperCase();
        const tPt = (pin ? 7.5 : TITLE_FS) * tmul * s;
        const icoW = (hasIcon === 'inline' && t) ? (Math.max(12, tPt * PT * 1.4) + 5) : 0;
        const wv = textW(String(value == null ? '' : value), (pin ? 14.5 : VALUE_FS) * s, 700);
        const wt = textW(t, tPt, 700) + (nocase ? 0 : 0.8 * t.length) + icoW + (pin ? 10 * s : 0);
        return Math.trunc(Math.max(wv, wt) + 24 * s + 10);
      }
      // the line of each card: its saved row number, the lines numbered one after the other (normalize_row_nums)
      function groupLines(cards){
        const nums = Array.from(new Set(cards.map(function(c){ return c.row | 0; }))).sort(function(a, b){ return a - b; });
        return nums.map(function(n){ return cards.filter(function(c){ return (c.row | 0) === n; }); });
      }
      function build(){
        const cards = cur.cards || [];
        const sig = cards.map(function(c){ return c.key + ':' + (c.row | 0); }).join('|');
        let before = null;
        if (sig !== build.sig && build.sig !== undefined){
          // cards moved (drop, line change, card shown / hidden): each one glides from where it was to its new place
          // (300 ms, OutCubic)
          before = {};
          Object.keys(byKey).forEach(function(k){ const r = byKey[k].getBoundingClientRect(); if (r.width > 0) before[k] = r; });
        }
        // the row's height before (a line that comes or goes): the block glides to its new height so the charts under
        // it slide instead of jumping; a card taken off fades where it was (a copy over the page) while the others close up
        const big = !!(hooks && hooks.onMenu);  // the Deep Dive window's row (the pinned block places its widgets itself)
        const h0 = before ? el.getBoundingClientRect().height : 0;
        const gone = {}, oldLines = before ? lines.map(function(g){ return g.map(function(c){ return c.key; }); }) : null;
        if (before && big) Object.keys(before).forEach(function(k){
          if ((cur.cards || []).some(function(c){ return c.key === k; })) return;
          gone[k] = byKey[k].cloneNode(true);
        });
        if (sig !== build.sig){
          build.sig = sig; root.innerHTML = ''; byKey = {};
          lines = groupLines(cards);
          lines.forEach(function(group){
            const ln = document.createElement('div'); ln.className = 'dd-sc-line';
            group.forEach(function(c){
              const d = document.createElement('div');
              d.className = 'dd-sc'; d.dataset.key = c.key;
              // more_button: the "⋯" shown while the card is hovered, it opens the card's right-click menu
              d.innerHTML = '<div class="dd-sc-bd"></div><div class="dd-sc-t"></div><div class="dd-sc-v"></div>' +
                '<button class="dd-sc-more" title="Options (or right click)"><svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><circle cx="5" cy="12" r="2.2"/><circle cx="12" cy="12" r="2.2"/><circle cx="19" cy="12" r="2.2"/></svg></button>';
              d.querySelector('.dd-sc-more').addEventListener('click', function(ev){
                ev.stopPropagation(); const r = ev.currentTarget.getBoundingClientRect();
                d.dispatchEvent(new MouseEvent('contextmenu', {bubbles: true, cancelable: true, clientX: r.left, clientY: r.bottom}));
              });
              d.querySelector('.dd-sc-more').addEventListener('mousedown', function(ev){ ev.stopPropagation(); });
              d.querySelector('.dd-sc-t').textContent = c.label;
              d.querySelector('.dd-sc-v').textContent = c.value;
              d._text = c.value;
              ln.appendChild(d); byKey[c.key] = d;
            });
            root.appendChild(ln);
          });
        } else {
          // the same cards in the same places: their new values, and the lines hold the new card objects (their
          // color, label, style: a theme change kept the old colors until the window was built again)
          lines = groupLines(cards);
          cards.forEach(function(c){
            const d = byKey[c.key]; if (!d) return;
            setValue(d, c.key, c.value);
          });
        }
        layout();
        if (before && document.body.animate){
          const still = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
          const E = 'cubic-bezier(0.22, 1, 0.36, 1)', h1 = el.getBoundingClientRect().height;
          if (!still && big && Math.abs(h1 - h0) > 0.5){
            const prevO = el.style.overflow; el.style.overflow = 'hidden';
            el.animate([{height: h0 + 'px'}, {height: h1 + 'px'}], {duration: 420, easing: E}).finished.then(function(){ el.style.overflow = prevO; }, function(){ el.style.overflow = prevO; });
          }
          if (!still) animateMoves(before, oldLines, gone, big, E);
          if (DD.dev) DD.trace('LAYOUT stats row ' + Math.round(h0) + ' -> ' + Math.round(h1) + ' gone=' + Object.keys(gone).length + ' new=' + (cur.cards || []).filter(function(c){ return !before[c.key]; }).length);
        }
      }
      // the cards' moves after a card came, went or moved. A line that keeps its cards in the same order on one row
      // animates in its flow: the widths go from the old ones to the new (a card that comes grows from nothing, one that
      // goes shrinks to nothing while fading), so the cards never sum wider than the line (it wrapped the last card
      // onto a second row for the time of the glide) and never move twice (flow + translate). The other cards glide
      // from where they were (translate only); a card taken off elsewhere fades where it was.
      function animateMoves(before, oldLines, gone, big, E){
        const GAP = DD.statGap || SPACING, D = 420, lineEls = root.querySelectorAll('.dd-sc-line'), flow = {};
        const oneRow = function(rs){ return rs.every(function(r){ return Math.abs(r.top - rs[0].top) < 1; }); };
        const padOf = function(d){ const cs = getComputedStyle(d); return [cs.paddingLeft, cs.paddingRight]; };
        lines.forEach(function(group, li){
          const ln = lineEls[li]; if (!ln) return;
          const keys = group.map(function(c){ return c.key; }), kept = keys.filter(function(k){ return before[k]; });
          if (!kept.length) return;
          const og = oldLines.filter(function(g){ return g.indexOf(kept[0]) >= 0; })[0]; if (!og) return;
          if (og.filter(function(k){ return keys.indexOf(k) >= 0; }).join('|') !== kept.join('|')) return;  // other cards or order
          if (!oneRow(og.filter(function(k){ return before[k]; }).map(function(k){ return before[k]; }))) return;
          const now = {}; keys.forEach(function(k){ now[k] = byKey[k].getBoundingClientRect(); });
          if (!oneRow(keys.map(function(k){ return now[k]; }))) return;
          ln.style.flexWrap = 'nowrap';
          const anims = [];
          // the cards of the old line that are not on it any more: a copy shrinks in their place (fading when taken off)
          og.forEach(function(k, i){
            if (keys.indexOf(k) >= 0) return;
            const a = before[k]; if (!a) return;
            const g = gone[k] || byKey[k] && byKey[k].cloneNode(true); if (!g) return;
            delete gone[k];
            g.removeAttribute('data-key'); g.style.pointerEvents = 'none'; g.style.width = a.width + 'px'; g.style.height = a.height + 'px';
            let next = null; for (let q = i + 1; q < og.length && !next; q++) if (keys.indexOf(og[q]) >= 0) next = byKey[og[q]];
            ln.insertBefore(g, next);
            const p = padOf(g), fade = (cur.cards || []).some(function(c){ return c.key === k; }) ? 0 : 1;
            anims.push(g.animate([{width: a.width + 'px', paddingLeft: p[0], paddingRight: p[1], marginRight: '0px', opacity: fade},
                                  {width: '0px', paddingLeft: '0px', paddingRight: '0px', marginRight: -GAP + 'px', opacity: 0}],
                                 {duration: D, easing: E, fill: 'forwards'}));
            anims[anims.length - 1].finished.then(function(){ g.remove(); }, function(){ g.remove(); });
          });
          keys.forEach(function(k){
            const d = byKey[k], b = now[k]; flow[k] = true;
            if (before[k]){
              if (Math.abs(before[k].width - b.width) > 0.5) anims.push(d.animate([{width: before[k].width + 'px'}, {width: b.width + 'px'}], {duration: D, easing: E}));
            } else {
              const p = padOf(d);
              anims.push(d.animate([{width: '0px', paddingLeft: '0px', paddingRight: '0px', marginRight: -GAP + 'px'},
                                    {width: b.width + 'px', paddingLeft: p[0], paddingRight: p[1], marginRight: '0px'}], {duration: D, easing: E}));
              d.animate([{opacity: 0}, {opacity: 0, offset: 0.4}, {opacity: 1}], {duration: D + 100, easing: 'ease-out'});
            }
          });
          Promise.all(anims.map(function(x){ return x.finished.catch(function(){}); })).then(function(){ ln.style.flexWrap = ''; });
          if (DD.dev) DD.trace('LAYOUT stats line ' + li + ' in flow: ' + keys.length + ' cards (' + keys.filter(function(k){ return !before[k]; }).length + ' new, ' + og.filter(function(k){ return keys.indexOf(k) < 0; }).length + ' out)');
        });
        // what is left: copies of the cards taken off fade where they were, new cards fade in, moved cards glide
        Object.keys(gone).forEach(function(k){
          const a = before[k], g = gone[k];
          g.style.cssText += ';position:fixed;left:' + a.left + 'px;top:' + a.top + 'px;width:' + a.width + 'px;height:' + a.height + 'px;margin:0;pointer-events:none;z-index:5';
          el.appendChild(g);  // inside the block: it keeps the cards' look (.dd-shell .dd-sc ...)
          g.animate([{opacity: 1, transform: 'none'}, {opacity: 0, transform: 'scale(0.96)'}], {duration: 220, easing: 'ease-out', fill: 'forwards'}).finished.then(function(){ g.remove(); }, function(){ g.remove(); });
        });
        Object.keys(byKey).forEach(function(k){
          if (flow[k]) return;
          const d = byKey[k];
          if (!before[k]){
            if (big) d.animate([{opacity: 0, transform: 'scale(0.96)'}, {opacity: 0, offset: 0.35, transform: 'scale(0.96)'}, {opacity: 1, transform: 'none'}], {duration: 520, easing: E});
            return;
          }
          const a = before[k], b = d.getBoundingClientRect();
          if (Math.abs(a.left - b.left) < 0.5 && Math.abs(a.top - b.top) < 0.5 && Math.abs(a.width - b.width) < 0.5) return;
          // a transform only (a width animation in the flow moves its neighbours too, and wrapped them onto another
          // row): the card glides from its old box to its new one, its width included (scaled, as the charts' glide)
          const sx = b.width ? a.width / b.width : 1, sy = b.height ? a.height / b.height : 1;
          d.animate([{transformOrigin: '0 0', transform: 'translate(' + (a.left - b.left) + 'px,' + (a.top - b.top) + 'px) scale(' + sx + ',' + sy + ')'},
                     {transformOrigin: '0 0', transform: 'none'}], {duration: D, easing: E});
        });
      }
      function setValue(d, key, text, durMs){
        const v = d.querySelector('.dd-sc-v');
        if (d._text === text){ return; }
        const plan = rollPlan(d._text, text), old = d._text;
        d._text = text;
        if (rolls[key]) cancelAnimationFrame(rolls[key].raf);
        if (!plan){ if (v._slotEnd) v._slotEnd(); v.textContent = text; delete rolls[key]; return; }
        // Stat_Num_Anim 'roll' (Settings > General > Animations): the digits roll instead of the number counting
        const still = (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) || DD._noAnim || (DD.anim && DD.anim.on === false);
        if (DD.theme && DD.theme.num_anim === 'roll' && document.body.animate && !still && old != null){
          // dev trace: each roll, and one cut short by the next value (the digits jump to the end, then roll again)
          if (DD.dev) DD.trace('ANIMTRACE statroll ' + key + ' ' + old + ' -> ' + text + (v._slotEnd ? ' (cut the running one)' : '') + ' font ' + getComputedStyle(v).fontSize + ' @' + Math.round(performance.now()));
          delete rolls[key]; slotRoll(v, old, text, plan.to >= plan.from); return;
        }
        if (v._slotEnd) v._slotEnd();
        const t0 = performance.now(), r = rolls[key] = {}, rollMs = durMs || (ROLL_MS * (DD.calm ? DD.calm() : 1));
        (function step(now){
          const t = Math.min(1, (now - t0) / rollMs), e = t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
          const cv = plan.from + (plan.to - plan.from) * e;
          if (t >= 1){ v.textContent = text; delete rolls[key]; return; }
          v.textContent = plan.prefix + fmtRoll(plan.dec > 0 ? cv : Math.round(cv), plan.dec, plan.kind) + (plan.kind === 'percent' ? '%' : plan.suffix);
          r.raf = requestAnimationFrame(step);
        })(t0);
      }
      // StatCardEffect: the glow border fades in on hover (0.08 per frame) and out again unless the card is "locked";
      // a click toggles the lock (UNLOCKED_EFFECTS). Cards start locked (border on).
      const fxs = {}; let fxRaf = 0, fxLast = 0;
      const GLOW_SCALE = 0.3, FX_STEP = 0.08;
      function fxOf(key){
        if (fxs[key]) return fxs[key];
        // a card shown again (the page or the row built again) has its border as it was, without fading in
        const locked = (cur.unlocked || []).indexOf(key) < 0;
        return (fxs[key] = {op: locked ? 1 : 0, target: locked ? 1 : 0, hover: false, locked: locked});
      }
      function fxApply(key){
        const d = byKey[key]; if (!d) return;
        const f = fxOf(key), st = th.stat, max = Math.max(0, Math.min(1, (st.border_pct || 0) / 100));
        const eff = st.glass ? (f.hover && max > 0 ? Math.min(1, max / GLOW_SCALE) : max) : 0;
        const bd = d.querySelector('.dd-sc-bd'); if (bd) bd.style.opacity = String(f.op * eff);
      }
      function fxTick(now){
        const dt = fxLast ? Math.min(64, now - fxLast) : 16.7; fxLast = now;
        let more = false;
        Object.keys(fxs).forEach(function(k){
          const f = fxs[k]; if (f.op === f.target){ return; }
          const step = FX_STEP * dt / 16.7;
          f.op = f.op < f.target ? Math.min(f.target, f.op + step) : Math.max(f.target, f.op - step);
          if (f.op !== f.target) more = true;
          fxApply(k);
        });
        fxRaf = more ? requestAnimationFrame(fxTick) : 0; if (!more) fxLast = 0;
      }
      function fxKick(){ if (!fxRaf){ fxLast = 0; fxRaf = requestAnimationFrame(fxTick); } }
      function fxBind(d, key){
        const f = fxOf(key), on = th.stat.hover_effect !== false && cur.hover_effect !== false;
        if (f.bound === d) return; f.bound = d;
        f.target = f.locked ? 1 : 0; fxApply(key); fxKick();
        d.addEventListener('mouseenter', function(){ if (!on) return; f.hover = true; if (!f.locked) f.target = 1; fxApply(key); fxKick(); });
        d.addEventListener('mouseleave', function(){ f.hover = false; if (!f.locked) f.target = 0; fxApply(key); fxKick(); });
        d.addEventListener('click', function(){
          if (root._justDragged || !on) return;
          f.locked = !f.locked; f.target = f.locked ? 1 : 0;
          cur.unlocked = (cur.unlocked || []).filter(function(x){ return x !== key; }); if (!f.locked) cur.unlocked.push(key);
          fxKick(); DD.call('stat_lock', {key: key, locked: f.locked}).catch(function(){});
        });
      }
      // a drop shadow (blur radius 4, 1 px down, black at the setting's opacity) on the
      // title and on the value (Title / Stat Shadow Intensity)
      function textShadows(t, v, cs){
        const sh = function(o){ o = +o || 0; return o > 0.01 ? '0 1px 4px rgba(0,0,0,' + Math.min(1, o).toFixed(3) + ')' : 'none'; };
        t.style.textShadow = sh(cs.title_shadow); v.style.textShadow = sh(cs.stat_shadow);
      }
      function layout(){
        const st = th.stat, all = cur.cards || [];
        if (!all.length) return;
        const avail = root.clientWidth;
        const tm = (st.title_size || 100) / 100;
        if (cur.compact){
          // pinned (StatCardsContainer compact mode): each card at its own ideal width (idealW), fonts and height
          // of compact_typography, the line centered
          const k = cur.compact;
          root.querySelectorAll('.dd-sc-line').forEach(function(ln){ ln.style.justifyContent = 'center'; ln.style.flexWrap = 'wrap'; ln.style.gap = SPACING + 'px'; });
          const idealOfC = function(c){
            const cs = c.style || st;
            return c.w != null ? c.w : idealW(c.value, c.label, true, c.tm != null ? c.tm : (k.tm != null ? k.tm : tm), c.s || 1, statIconPath(c) ? iconMode(cs) : 'off');
          };
          // a phone, a line too wide for one row: balanced rows (4 cards make 2 + 2), the cards of the line all as wide as
          // its widest one, centered
          const fill = {}, lineEls = root.querySelectorAll('.dd-sc-line');
          lines.forEach(function(group, li){
            const ln = lineEls[li]; if (!ln) return;
            ln.style.maxWidth = ''; ln.style.margin = '';
            const n = group.length;
            if (!n || !(DD.isTouch && DD.isTouch() && avail > 0 && avail < 520)) return;
            const need = Math.max.apply(null, group.map(idealOfC));
            const rowW = function(per){ return per * need + (per - 1) * SPACING; };
            if (group.reduce(function(a, c){ return a + idealOfC(c); }, 0) + (n - 1) * SPACING <= avail) return;  // one row: as before
            let per = 1;
            for (let r = 2; r <= n; r++){ const p = Math.ceil(n / r); if (rowW(p) <= avail){ per = p; break; } }
            group.forEach(function(c){ fill[c.key] = need; });
            ln.style.maxWidth = (rowW(per) + 1) + 'px'; ln.style.margin = '0 auto';
          });
          all.forEach(function(c){
            const d = byKey[c.key]; if (!d) return;
            const cs = c.style || st;
            const cardW = fill[c.key] || idealOfC(c);
            d.style.width = cardW + 'px';
            d.style.height = Math.trunc(k.h) + 'px';
            d.style.setProperty('--sc-px', Math.round(k.hm) + 'px');
            d.style.setProperty('--sc-bg', cs.glass ? surfaceCss(c.color, cs, th.is_dark) : 'transparent');
            ring(d, cs.glass ? borderCss(c.color, cs, th.is_dark, 1) : 'none');
            fxBind(d, c.key); fxApply(c.key);
            const t = d.querySelector('.dd-sc-t'), v = d.querySelector('.dd-sc-v');
            renderIcon(d, t, c, cs, th.is_dark);
            d.style.alignItems = 'center'; t.style.textAlign = v.style.textAlign = 'center'; t.style.paddingLeft = '0';  // pinned cards: centered texts
            t.style.fontSize = (k.title * (c.tm != null ? c.tm : (k.tm != null ? k.tm : tm)) * PT) + 'px'; t.style.color = cs.title_color;
            let valPt = k.val;
            if (c.w != null){
              const maxTxtW = Math.max(20, cardW - 2 * Math.round(k.hm) - 4);
              const vw = textW(String(c.value == null ? '' : c.value), valPt, 700);
              if (vw > maxTxtW) valPt = valPt * (maxTxtW / vw);
            }
            v.style.fontSize = (valPt * PT) + 'px'; v.style.color = valueColor(c.color, cs, th.is_dark);
            const mb = d.querySelector('.dd-sc-more'); if (mb) mb.style.color = cs.title_color;
            textShadows(t, v, cs);
          });
          return;
        }
        // the dashboard's sizes at scale 1, the title multiplier
        const tmul = Math.max(0.5, Math.min(2, tm)) * (document.documentElement.classList.contains('dd-nocase') ? 1.2 : 1);
        const idealOf = function(val, label, c){ const cs = (c && c.style) || st; return idealW(val, label, false, tmul, 1, statIconPath(c) ? iconMode(cs) : 'off'); };
        const lineEls = root.querySelectorAll('.dd-sc-line');
        // web (Deep Dive): the cards spaced as the charts under them (DD.statGap), so that they fall on the charts' columns
        const GAP = DD.statGap || SPACING;
        const wk = DD.exportWrapW && window.innerWidth > DD.exportWrapW ? DD.exportWrapW / window.innerWidth : 1;
        const C2 = DD.statCols | 0, phone = !!(DD.isTouch && DD.isTouch() && avail < 520);
        const kC = phone ? 0.78 : (!C2 ? 1 : C2 <= 2 ? 1.12 : C2 === 3 ? 1.05 : C2 === 4 ? 1 : C2 === 5 ? 0.93 : 0.87);
        const plans = [];
        let shared = null;
        lineEls.forEach(function(ln, li){
          ln.style.columnGap = GAP + 'px';
          const group = lines[li] || [], n = group.length;
          if (!n) return;
          // as few lines as keep a readable size (balanced, 7 cards make 4 + 3)
          const hid = group.map(function(c){ return Math.max(1, Math.trunc(idealOf('0.00%', c.label, c))); });
          // an export made wider than the window (a table with many columns): the lines break as in the window (all
          // the cards went on one line), then each line spreads over the export's width
          const allowed = avail * wk / 0.8;
          const maxPer = phone ? 2 : n;
          let chunks = null;
          for (let k = 1; k <= n && !chunks; k++){
            const per = Math.ceil(n / k);
            if (per > maxPer) continue;
            const cs = [];
            for (let i = 0; i < n; i += per) cs.push(group.slice(i, i + per).map(function(_c, j){ return i + j; }));
            if (cs.every(function(ch){ return ch.reduce(function(a, j){ return a + hid[j]; }, 0) + GAP * (ch.length - 1) <= allowed; })) chunks = cs;
          }
          if (!chunks) chunks = group.map(function(_c, i){ return [i]; });
          ln.style.rowGap = GAP + 'px';
          chunks.forEach(function(ch){
            const m = ch.length, gaps = GAP * (m - 1), cg = gaps;
            const total = ch.reduce(function(a, j){ return a + Math.trunc(idealOf(group[j].value, group[j].label)); }, 0) + cg;
            const hTot = ch.reduce(function(a, j){ return a + hid[j]; }, 0) + cg;
            const ty = Object.assign({}, typography(avail * wk, total, st.scale, hTot));  // the text as big as in the window
            // web: a little taller with few charts per row (big charts under them), lower with many
            if (kC !== 1){ ty.h *= kC; ty.val *= kC; ty.title *= kC; }
            if (!shared) shared = Object.assign({}, ty);
            else {
              shared.h = Math.min(shared.h, ty.h);
              shared.val = Math.min(shared.val, ty.val);
              shared.title = Math.min(shared.title, ty.title);
              shared.hm = Math.min(shared.hm, ty.hm);
            }
            plans.push({group: group, ch: ch, w: (avail - gaps) / m});
          });
        });
        // share one uniform typography across all wrapped rows so Row 1 and Row 2 never have mismatched text sizes
        plans.forEach(function(p){
          const ty = shared;
          p.ch.forEach(function(j){
            const c = p.group[j], d = byKey[c.key]; if (!d) return;
            const cs = c.style || st;  // a card with its own style (its Settings) draws with it
            d.style.width = Math.floor(p.w * 100) / 100 + 'px';
            d.style.height = Math.round(ty.h) + 'px';
            d.style.setProperty('--sc-px', Math.round(ty.hm) + 'px');
            d.style.setProperty('--sc-bg', cs.glass ? surfaceCss(c.color, cs, th.is_dark) : 'transparent');
            ring(d, cs.glass ? borderCss(c.color, cs, th.is_dark, 1) : 'none');
            fxBind(d, c.key); fxApply(c.key);
            const t = d.querySelector('.dd-sc-t'), v = d.querySelector('.dd-sc-v');
            renderIcon(d, t, c, cs, th.is_dark);
            t.style.fontSize = (ty.title * tm * PT) + 'px';
            t.style.color = cs.title_color;
            v.style.fontSize = (ty.val * PT) + 'px';
            const mb = d.querySelector('.dd-sc-more');
            if (mb){ mb.style.color = cs.title_color; requestAnimationFrame(function(){ mb.style.top = Math.max(2, t.offsetTop + (t.offsetHeight - 16) / 2) + 'px'; }); }
            v.style.color = valueColor(c.color, cs, th.is_dark);
            d.style.setProperty('--sc-c', c.color);  // web: the card's colour for its centered look (dd.css)
            textShadows(t, v, cs);
          });
        });
      }
      // ---- drag and drop: reorder in a line, move to another line, or drop between lines for a new one ----
      let drag = null;
      function modelLines(){ return lines.map(function(g){ return g.map(function(c){ return c.key; }); }); }
      function commit(ls){
        ls = ls.filter(function(g){ return g.length; });
        const order = [], rows = {};
        ls.forEach(function(g, i){ g.forEach(function(k){ order.push(k); rows[k] = i; }); });
        const byk = {}; (cur.cards || []).forEach(function(c){ byk[c.key] = c; });
        cur = Object.assign({}, cur, {cards: order.map(function(k){ return Object.assign({}, byk[k], {row: rows[k]}); })});
        build();
        if (hooks.onLayout) hooks.onLayout(order, rows);
      }
      function target(x, y){
        const lineEls = Array.from(root.querySelectorAll('.dd-sc-line'));
        // the phone's single strip (the lines laid out in one scrolling row): before / after the card under the finger
        if (lineEls.length && getComputedStyle(lineEls[0]).display === 'contents'){
          let best = null;
          lineEls.forEach(function(le, i){
            Array.from(le.children).filter(function(c){ return c !== drag.el; }).forEach(function(c, j){
              const r = c.getBoundingClientRect(), d = Math.abs(x - (r.left + r.width / 2));
              if (!best || d < best.d) best = {d: d, line: i, j: j, r: r, after: x > r.left + r.width / 2};
            });
          });
          if (!best) return {line: 0, idx: 0, rect: lineEls[0].getBoundingClientRect(), after: true, vertical: true};
          return {line: best.line, idx: best.j + (best.after ? 1 : 0), rect: best.r, after: best.after, vertical: true};
        }
        const rr = root.getBoundingClientRect();
        for (let i = 0; i < lineEls.length; i++){
          const r = lineEls[i].getBoundingClientRect();
          if (y >= r.top - 3 && y <= r.bottom + 3){
            const cs = Array.from(lineEls[i].children).filter(function(c){ return c !== drag.el; });
            let idx = cs.length;
            for (let j = 0; j < cs.length; j++){ const cr = cs[j].getBoundingClientRect(); if (y < cr.top && j === 0) { idx = 0; break; } if (y >= cr.top && y <= cr.bottom && x < cr.left + cr.width / 2){ idx = j; break; } if (y < cr.bottom && x < cr.left){ idx = j; break; } }
            // the edge of a line: a new line above / under when the pointer is at the very top / bottom of the line
            return {line: i, idx: idx, rect: cs[idx] ? cs[idx].getBoundingClientRect() : (cs.length ? cs[cs.length - 1].getBoundingClientRect() : r), after: !cs[idx], vertical: true};
          }
        }
        // between two lines (or above / under them): a new line
        let at = lineEls.length;
        for (let i = 0; i < lineEls.length; i++){ if (y < lineEls[i].getBoundingClientRect().top){ at = i; break; } }
        const ref = lineEls[Math.min(at, lineEls.length - 1)].getBoundingClientRect();
        return {newLine: at, y: at >= lineEls.length ? ref.bottom + 2 : ref.top - 2, vertical: false, rect: ref};
      }
      root.addEventListener('pointerdown', function(e){
        if (e.button !== 0 || e.pointerType === 'touch') return;  // a finger: through the touch lift below
        const d = e.target.closest('.dd-sc'); if (!d || !hooks.onLayout) return;
        drag = {el: d, key: d.dataset.key, x0: e.clientX, y0: e.clientY, on: false, ghost: null, mark: null};
      });
      function abortSc(){
        if (!drag) return; const d = drag; drag = null;
        if (d.ghost) d.ghost.remove(); if (d.mark) d.mark.remove(); d.el.classList.remove('dd-sc-drag');
      }
      window.addEventListener('pointercancel', function(e){ if (e.pointerType !== 'touch') abortSc(); });
      window.addEventListener('blur', abortSc);
      window.addEventListener('pointermove', function(e){
        if (!drag || e.pointerType === 'touch') return;
        if (!(e.buttons & 1)){ abortSc(); return; }
        if (!drag.on){
          if (Math.abs(e.clientX - drag.x0) + Math.abs(e.clientY - drag.y0) < 6) return;
          drag.on = true; drag.el.classList.add('dd-sc-drag');
          const r = drag.el.getBoundingClientRect();
          drag.ox = e.clientX - r.left; drag.oy = e.clientY - r.top;
          const g = drag.el.cloneNode(true); g.classList.add('dd-sc-ghost'); g.style.width = r.width + 'px'; g.style.height = r.height + 'px';
          document.body.appendChild(g); drag.ghost = g;
          const m = document.createElement('div'); m.className = 'dd-sc-mark'; document.body.appendChild(m); drag.mark = m;
        }
        drag.ghost.style.left = (e.clientX - drag.ox) + 'px'; drag.ghost.style.top = (e.clientY - drag.oy) + 'px';
        const tg = drag.tg = target(e.clientX, e.clientY), m = drag.mark;
        if (tg.vertical){
          const r = tg.rect;
          m.style.cssText = 'display:block;width:3px;height:' + r.height + 'px;left:' + ((tg.after ? r.right + 1 : r.left - 4)) + 'px;top:' + r.top + 'px';
        } else {
          const rr = root.getBoundingClientRect();
          m.style.cssText = 'display:block;height:3px;width:' + rr.width + 'px;left:' + rr.left + 'px;top:' + (tg.y - 1) + 'px';
        }
      });
      window.addEventListener('pointerup', function(e){
        if (!drag || e.pointerType === 'touch') return;
        const d = drag; drag = null;
        if (!d.on) return;
        d.ghost.remove(); d.mark.remove(); d.el.classList.remove('dd-sc-drag');
        d.moved = true; root._justDragged = true; setTimeout(function(){ root._justDragged = false; }, 0);
        const tg = d.tg; if (!tg) return;
        const ls = modelLines().map(function(g){ return g.filter(function(k){ return k !== d.key; }); });
        if (tg.newLine !== undefined){
          // indexes are those of the lines before the card left its own (an emptied line is dropped after)
          ls.splice(tg.newLine, 0, [d.key]);
        } else {
          ls[tg.line].splice(tg.idx, 0, d.key);
        }
        commit(ls);
      });
      // touch: hold a card to lift it, move to drag it (the pointer drag above, fed by the lift), or let go for its menu;
      // in the pinned block the block itself does all this (no hooks here)
      if (DD.touchLift && (hooks.onLayout || hooks.onMenu)){
        DD.touchLift(root, {
          pick: function(t){ return t.closest && t.closest('.dd-sc'); },
          ignore: 'button, input, select',
          drag: function(phase, x, y, card){
            if (!hooks.onLayout) return;
            if (phase === 'start') DD.touchEvent('pointer', 'pointerdown', x, y, card);
            else DD.touchEvent('pointer', phase === 'move' ? 'pointermove' : 'pointerup', x, y);
          },
          menu: DD.openMenuAt,
        });
      }
      root.addEventListener('contextmenu', function(e){
        const d = e.target.closest('.dd-sc'); if (!d || !hooks.onMenu) return;
        e.preventDefault(); const k = d.dataset.key;
        hooks.onMenu(k, (cur.cards || []).filter(function(c){ return c.key === k; })[0], e.clientX, e.clientY, {lines: modelLines(), commit: commit});
      });
      build();
      let introPending = false;
      const wantIntro = !!(hooks && hooks.intro) && !(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) && !DD._noAnim && (!DD.anim || (DD.anim.on !== false && DD.anim.appear !== false));
      if (wantIntro){
        const targets = {};
        (cur.cards || []).forEach(function(c){
          const d = byKey[c.key], z = zeroFor(c.value);
          if (!d || !z) return;
          targets[c.key] = c.value;
          d.querySelector('.dd-sc-v').textContent = z;
          d._text = z;
        });
        if (Object.keys(targets).length){
          introPending = true;
          const runIntro = function(){
            if (!introPending || !root.isConnected) return;
            introPending = false;
            Object.keys(targets).forEach(function(k){
              const d = byKey[k], cc = (cur.cards || []).filter(function(x){ return x.key === k; })[0];
              if (!d || !cc || cc.value !== targets[k]) return;
              setValue(d, k, cc.value, 520);
            });
          };
          if (DD.onGo) DD.onGo(runIntro); else requestAnimationFrame(runIntro);
        }
      }
      // the pinned block on another deck or screen (hooks.from: the value each card showed last, wherever): a card
      // rolls from it, as a pinned chart morphs from its last picture. hooks.hold: they wait at those values for
      // update() (the spec given here is this set's last picture, maybe of another deck); a card never shown before
      // keeps it there, else counts up from zero
      if (hooks && hooks.from && !wantIntro){
        const moving = !(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) && !DD._noAnim && (!DD.anim || DD.anim.on !== false);
        const appear = moving && (!DD.anim || DD.anim.appear !== false);
        (cur.cards || []).forEach(function(c){
          const d = byKey[c.key], was = hooks.from[c.key], start = was != null ? was : (appear && !hooks.hold ? zeroFor(c.value) : null);
          if (!d || !moving || start == null || start === c.value) return;
          d.querySelector('.dd-sc-v').textContent = start;
          d._text = start;
          if (!hooks.hold) setValue(d, c.key, c.value);
        });
      }
      const ro = new ResizeObserver(layout);
      ro.observe(root);
      return {
        update: function(next){
          introPending = false;
          cur = next;
          // the locks as Python has them now (a card clicked on another page, shown here from an older picture):
          // taken at once, without the border fading
          const un = cur.unlocked || [];
          Object.keys(fxs).forEach(function(k){ const f = fxs[k], lk = un.indexOf(k) < 0; if (f.locked !== lk){ f.locked = lk; f.target = f.op = (lk || f.hover) ? 1 : 0; } });
          build();
          Object.keys(fxs).forEach(function(k){ fxApply(k); });
        },
        setTheme: function(t){ th = t; layout(); },
        relayout: function(){ layout(); },
        destroy: function(){ ro.disconnect(); root.remove(); },
      };
    },
  };
})();
