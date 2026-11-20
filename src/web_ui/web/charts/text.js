// A text of the Deep Dive (providers.text_data): a sentence written in the pinned text widget's editor, its variables
// ({reviews}, {retention}, {reviews:week}, {reviews@Deck}...) read for the deck and period shown. A new sentence fades
// in (a deck or period change); a text not written yet says how to write it.
(function(){
  'use strict';
  const DD = window.DD;
  DD.charts = DD.charts || {};
  DD.charts.text = {
    mount: function(body, ctx){
      body.classList.add('dd-tx');
      const box = document.createElement('div');
      box.className = 'dd-tx-in';
      box.setAttribute('data-nt', '');  // the user's words: never translated by the page (dd-core.js NO_TR)
      body.appendChild(box);
      let shown = null;
      const inst = {
        onSize: null,
        update: function(d){
          if (d === undefined) return;  // its data not come yet (app.js lateData): empty, not "write a text"
          const blank = !d || !!d.blank || !!d.error;
          const html = blank ? '' : String(d.html || '');
          const key = (blank ? 'b:' : 'h:') + html;
          if (key === shown) return;
          const first = shown === null;
          shown = key;
          box.classList.toggle('dd-tx-blank', blank);
          if (blank) box.textContent = DD.t('Double-click to write a text');
          else box.innerHTML = html;
          if (!first && box.animate && !DD._noAnim && (!DD.anim || DD.anim.on !== false))
            box.animate([{opacity: 0}, {opacity: 1}], {duration: 220, easing: 'ease-out'});
          if (inst.onSize) inst.onSize();
        },
        // the height its sentence needs at the card's width (the grid gives a row of texts only that height)
        natural: function(){ return Math.ceil(box.scrollHeight); },
        setTheme: function(){}, setOptions: function(){},
        destroy: function(){ box.remove(); },
      };
      inst.update(ctx.data);
      return inst;
    },
  };
})();
