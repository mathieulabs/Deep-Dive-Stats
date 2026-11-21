/* Charts of the extra groups (charts.more_charts): the stacked charts of days and hours drawn by Activity's chart
   (activity.js, with its own series), and Week by Hour. */
(function(){
  'use strict';
  const U = DD.cu;
  const TITLES = {
    ratings: 'Ratings', review_speed: 'Review Speed', forgotten: 'Forgotten', resets: 'Reset Cards', introduced: 'Introduced', introduced_load: 'Introduced Load', load_trend: 'Load Trend', stability_trend: 'Average Stability over Time', memorised: 'Memorised', todays_retention: 'First Answer Retention',
    answer_time: 'Answer Time',
    interval_ratings: 'Rating by Interval', rating_fatigue: 'Rating Fatigue', sibling_ratings: 'Rating by Sibling Gap', fsrs_calibration: 'FSRS Calibration', forgetting_curve: 'Recall by Elapsed / Stability', fsrs_fatigue: 'FSRS Loss by Fatigue', leech_detector: 'Leech Detector', stability_increase: 'Stability Increase Factor', future_retention: 'Future Due Retention', first_forgetting: 'First Long-term Forgetting Curve', first_forgetting_short: 'First Short-term Forgetting Curve', card_states: 'Card Counts over Time', due_today: 'Due Today by Hour',
    interval_load: 'Interval Load', lapse_distribution: 'Lapses per Card', review_distribution: 'Reviews per Card',
    learning_steps: 'Learning Steps per Card', time_distribution: 'Time per Card', interval_history: 'Interval Time Machine', stability_history: 'Stability Time Machine', difficulty_history: 'Difficulty Time Machine', week_hours: 'Week by Hour', sxr_heatmap: 'SxR Heatmap', bw_matrix: 'B-W Matrix', custom_pie: 'Custom Pie', custom_bar: 'Custom Bar',
  };
  DD.extraTitles = TITLES;
  // the charts with a trend (Show Trend) and what one row of their bars is: a day, a prior review of the day, ...
  const TREND_UNIT = {activity: 'day', added: 'day', ratings: 'day', review_speed: 'day', forgotten: 'day', resets: 'day', introduced: 'day', introduced_load: 'day', load_trend: 'day',
    stability_trend: 'day', memorised: 'day', card_states: 'day', future_retention: 'day', answer_time: 'second', interval_ratings: 'ivl',
    rating_fatigue: 'review', fsrs_fatigue: 'review', sibling_ratings: 'sibling'};
  DD.trendCharts = Object.keys(TREND_UNIT);
  const fmt = U.formatNum, trim = U.trimNum;
  const PILL_CHEV = '<svg class="dd-pill-chev" width="8" height="6" viewBox="0 0 8 6"><path d="M1 1.5L4 4.5L7 1.5" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  // Memorised's views (fsrs_history.MEMORISED_MEASURES)
  const MEASURE_NAMES = {cards: 'Cards', notes: 'Notes', average: 'Average per Card', load: 'Cards per Load', stable: 'Retrievability & Stability'};
  // the card types a chart of answers can count (DailyMetric card_types)
  const CARD_TYPE_NAMES = {all: 'All', learn: 'Learning', young: 'Young', mature: 'Mature', review: 'Young + Mature'};
  const noun = function(n, one, many){ return n === 1 ? one : many; };
  const sumKeys = function(rows, keys){ const t = {}; keys.forEach(function(k){ t[k] = 0; }); (rows || []).forEach(function(r){ keys.forEach(function(k){ t[k] += Number(r[k]) || 0; }); }); return t; };

  // ---- header stats ----
  function statText(type, data, cur){
    return function(rows, o){
      rows = rows || [];
      const series = cur.series, keys = series.map(function(s){ return s.key; });
      const unit = data.unit;
      if (unit === 'level'){
        if (!rows.length) return '';
        const first = rows[0], last = rows[rows.length - 1];
        const sign = function(c){ return (c > 0 ? '+' : '−') + fmt(Math.abs(c)); };
        const moved = first.date !== last.date;
        const tot = keys.reduce(function(a, k){ return a + (Number(last[k]) || 0); }, 0);
        if (!tot) return '';
        if (data.value === 'days'){
          // the average stability at the end of the days shown, with its change since their first day
          const now = Number(last.stability) || 0, ch = now - (Number(first.stability) || 0);
          const days = function(v){ return DD.tn('{n} day', '{n} days', Math.round(v), {n: trim(v, v < 10 ? 1 : 0)}); };
          return DD.t(data.measure === 'median' ? 'Median stability: {value}' : 'Average stability: {value}', {value: days(now)})
            + (moved && Math.abs(ch) >= 0.05 ? ' (' + (ch > 0 ? '+' : '−') + trim(Math.abs(ch), Math.abs(ch) < 10 ? 1 : 0) + ')' : '');
        }
        if (data.value === 'load'){
          // the reviews a day the cards asked for at the end of the days shown, with the change since their first day
          const perDay = function(v){ return DD.t('{value}/day', {value: DD.tn('{count} review', '{count} reviews', v, {count: trim(v, v < 10 ? 1 : 0)})}); };
          const ch = tot - keys.reduce(function(a, k){ return a + (Number(first[k]) || 0); }, 0);
          const chTxt = (ch > 0 ? '+' : '−') + trim(Math.abs(ch), Math.abs(ch) < 10 ? 1 : 0);
          return DD.t('Daily load: {value}', {value: perDay(tot)}) + (moved && Math.abs(ch) >= 0.05 ? ' (' + chTxt + ')' : '');
        }
        if (data.value === 'notes' || data.value === 'pct' || data.value === 'ratio'){
          // Memorised's views: notes, the average recall of a card, the cards known per review a day
          const ch = tot - keys.reduce(function(a, k){ return a + (Number(first[k]) || 0); }, 0);
          if (data.value === 'notes') return DD.tn('{n} note', '{n} notes', tot, {n: fmt(tot)}) + (ch && moved ? ' (' + sign(ch) + ')' : '');
          const pc = data.value === 'pct', dec = function(v){ return pc ? 1 : (Math.abs(v) < 10 ? 2 : 1); };
          const chTxt = (ch > 0 ? '+' : '−') + trim(Math.abs(ch), dec(ch)) + (pc ? '%' : '');
          return DD.t(pc ? 'Average recall: {value}' : 'Cards per load: {value}', {value: trim(tot, dec(tot)) + (pc ? '%' : '')})
            + (moved && Math.abs(ch) >= (pc ? 0.05 : 0.005) ? ' (' + chTxt + ')' : '');
        }
        if (series.length === 1){
          const change = tot - keys.reduce(function(a, k){ return a + (Number(first[k]) || 0); }, 0);
          return DD.tn('{n} card', '{n} cards', tot, {n: fmt(tot)}) + (change && moved ? ' (' + sign(change) + ')' : '');
        }
        const parts = series.slice().reverse().map(function(s){
          const now = Number(last[s.key]) || 0, ch = now - (Number(first[s.key]) || 0);
          return DD.t(s.label) + ': ' + fmt(now) + (ch && moved ? ' (' + sign(ch) + ')' : '');
        });
        parts.push(DD.tn('{n} card', '{n} cards', tot, {n: fmt(tot)}));
        return parts.join('  ·  ');
      }
      if ((type === 'ratings' || type === 'custom_bar') && data.measure === 'time'){
        // Time: each rating's share of the time spent, then that time
        const t = sumKeys(rows, keys.map(function(k){ return k + '_time_ms'; }));
        const total = keys.reduce(function(a, k){ return a + t[k + '_time_ms']; }, 0);
        if (!(total > 0)) return '';
        const mins = total / 60000;
        const parts = series.map(function(s){ return DD.t(s.label) + ': ' + trim(t[s.key + '_time_ms'] * 100 / total, 1) + '%'; });
        parts.push(DD.t('Total: {value}', {value: mins < 60 ? DD.t('{value} min', {value: trim(mins, 1)}) : DD.t('{value} h', {value: trim(mins / 60, 1)})}));
        return parts.join('  ·  ');
      }
      if (unit === 'rmse'){
        // FSRS Loss by Fatigue: the RMSE over the answers shown, then the recall predicted and the share passed
        let n = 0, sq = 0, ok = 0, pred = 0;
        rows.forEach(function(r){ n += Number(r._reviews) || 0; sq += Number(r._sq) || 0; ok += Number(r.passed) || 0; pred += Number(r._pred) || 0; });
        if (!n) return '';
        return DD.t('RMSE: {value}', {value: trim(Math.sqrt(sq / n), 1) + '%'}) + '  \u00b7  ' + DD.t('Predicted: {value}', {value: trim(pred * 100 / n, 1) + '%'})
          + '  \u00b7  ' + DD.t('Actual: {value}', {value: trim(ok * 100 / n, 1) + '%'}) + '  \u00b7  ' + DD.tn('{n} review', '{n} reviews', n, {n: fmt(n)});
      }
      if (type === 'leech_detector'){
        // (all the history of the cards: the period does not change it)
        let tot = 0; rows.forEach(function(r){ tot += Number(r.cards) || 0; });
        return tot ? DD.tn('{n} card', '{n} cards', tot, {n: fmt(tot)}) + '  \u00b7  ' + DD.t('Whole history') : '';
      }
      if (type === 'stability_increase'){
        // the cards shown and their average factor (as they are now: the period does not change it)
        let tot = 0, sum = 0; rows.forEach(function(r){ tot += Number(r.cards) || 0; sum += Number(r._fsum) || 0; });
        return tot ? DD.tn('{n} card', '{n} cards', tot, {n: fmt(tot)}) + '  \u00b7  ' + DD.t('Average factor: {value}', {value: '\u00d7' + trim(sum / tot, 2)}) : '';
      }
      if (type === 'fsrs_calibration' || type === 'forgetting_curve'){
        // the recall FSRS predicted on average against the share of answers passed, over the answers shown
        let n = 0, ok = 0, pred = 0;
        rows.forEach(function(r){ n += Number(r.reviews) || 0; ok += Number(r.passed) || 0; pred += Number(r._pred) || 0; });
        if (!n) return '';
        return DD.t('Predicted: {value}', {value: trim(pred * 100 / n, 1) + '%'}) + '  \u00b7  '
          + DD.t('Actual: {value}', {value: trim(ok * 100 / n, 1) + '%'}) + '  \u00b7  ' + DD.tn('{n} review', '{n} reviews', n, {n: fmt(n)});
      }
      if (type === 'future_retention'){
        // Future Due Retention: the recall to expect over the days shown, and their cards
        let n = 0, ok = 0;
        rows.forEach(function(r){ n += Number(r.cards) || 0; ok += Number(r.passed) || 0; });
        if (!n) return '';
        return DD.t('Expected retention: {value}', {value: trim(ok * 100 / n, 1) + '%'}) + '  \u00b7  ' + DD.tn('{n} card', '{n} cards', n, {n: fmt(n)});
      }
      if (type === 'ratings' || data.share_stats || cur.alt){
        const t = sumKeys(rows, keys), total = keys.reduce(function(a, k){ return a + t[k]; }, 0);
        if (!total) return '';
        const parts = series.map(function(s){ return DD.t(s.label) + ': ' + trim(t[s.key] * 100 / total, 1) + '%'; });
        parts.push(unit === 'cards' ? DD.tn('{n} card', '{n} cards', total, {n: fmt(total)}) : DD.tn('{n} review', '{n} reviews', total, {n: fmt(total)}));
        return parts.join('  ·  ');
      }
      if (unit === 'load'){
        // the reviews a day the cards introduced in the days shown bring now
        let tot = 0; rows.forEach(function(r){ tot += Number(r.reviews) || 0; });
        if (!(tot > 0)) return '';
        return DD.t('Daily load: {value}', {value: DD.t('{value}/day', {value: DD.tn('{count} review', '{count} reviews', tot, {count: trim(tot, tot < 10 ? 1 : 0)})})});
      }
      if (unit === 'seconds'){
        let rev = 0, ms = 0;
        rows.forEach(function(r){ rev += Number(r._reviews) || 0; ms += Number(r._ms) || 0; });
        if (!rev) return '';
        return DD.t('Avg: {value}', {value: trim(ms / 1000 / rev, 1) + 's'}) + '  ·  ' + DD.tn('{n} review', '{n} reviews', rev, {n: fmt(rev)});
      }
      if (type === 'due_today'){
        const total = Number(data.total) || 0;
        if (!total) return '';
        const parts = [DD.t('Due now: {value}', {value: DD.tn('{n} card', '{n} cards', data.due_now || 0, {n: fmt(data.due_now || 0)})}),
          DD.t('Later today: {value}', {value: DD.tn('{n} card', '{n} cards', data.later || 0, {n: fmt(data.later || 0)})})];
        if (data.next_due){
          const mins = Math.max(1, Math.round((data.next_due - Date.now() / 1000) / 60));
          const d = new Date(data.next_due * 1000), at = ('0' + d.getHours()).slice(-2) + ':' + ('0' + d.getMinutes()).slice(-2);
          parts.push(mins < 60 ? DD.t('Next card in {minutes} min ({time})', {minutes: mins, time: at}) : DD.t('Next card in {hours} h {minutes} min ({time})', {hours: Math.floor(mins / 60), minutes: mins % 60, time: at}));
        }
        return parts.join('  ·  ');
      }
      // Total and average per day of a count (forgotten: lapses, introduced: cards)
      let tot = 0, act = 0;
      rows.forEach(function(r){ const v = Number(r.reviews) || 0; tot += v; if (v > 0) act++; });
      const per = o.avg_on_active_days ? (act || 1) : (rows.length || 1);
      const noun2 = unit === 'lapses' ? ['lapse', 'lapses'] : (unit === 'cards' ? ['card', 'cards'] : ['review', 'reviews']);
      const avg = tot / per;
      const cnt = function(v, txt){ return DD.tn('{n} ' + noun2[0], '{n} ' + noun2[1], v, {n: txt}); };
      let line = DD.t('Total: {value}', {value: cnt(tot, fmt(tot))}) + '  ·  ' + DD.t('Avg: {value}', {value: DD.t('{value}/day', {value: cnt(avg === 1 ? 1 : 2, trim(avg, 1))})});
      // Introduced: the cards reset to new, not introduced again yet
      const rw = Number(data.reset_waiting) || 0;
      if (type === 'introduced' && rw > 0) line += '  ·  ' + DD.tn('Reset, not introduced again: {count} card', 'Reset, not introduced again: {count} cards', rw, {count: fmt(rw)});
      return line;
    };
  }

  // the units of the charts with a Line view: the levels, and the averages of a bar (seconds, RMSE)
  const LINE_UNITS = {level: 1, seconds: 1, rmse: 1};

  function registerDaily(type){
    DD.registerChart(type, {
      mount: function(el, ctx){
        const data0 = ctx.data || {};
        const cur = {series: data0.series || [], alt: false};
        const derive = function(data, o){
          const alt = !!(o.alt_view && data.alt);
          const series = alt ? data.alt.series : (data.series || []);
          cur.series = series; cur.alt = alt;
          let colors = {}, labels = {};
          series.forEach(function(s){ colors[s.key] = s.color; labels[s.key] = s.label; });
          const unit = data.unit;
          // (Custom Bar with one search: still drawn in its search's colour, not as one plain bar)
          const single = series.length === 1 && type !== 'custom_bar';
          let rows = data.rows || [];
          // Variation (the level charts): each day's change of the level, a gain or a loss
          const vari = !!(o.variation && data.variation_colors && unit === 'level');
          if (vari){
            let prev = null;
            rows = rows.map(function(r){
              const lv = r.total != null ? (Number(r.total) || 0) : series.reduce(function(a, s){ return a + (Number(r[s.key]) || 0); }, 0);
              const d = prev === null ? 0 : lv - prev;
              prev = lv;
              return Object.assign({}, r, {gain: Math.max(0, d), loss: Math.max(0, -d), reviews: Math.abs(d)});
            });
            const vc = data.variation_colors;
            colors = {gain: vc.gain, loss: vc.loss}; labels = {gain: DD.t('Gain'), loss: DD.t('Loss')};
          }
          if (type === 'introduced' && o.first_reintro === false){
            // without the cards introduced again: their count and first ratings (r_again ...) taken off
            rows = rows.map(function(r){
              const c = Object.assign({}, r);
              c.reintro = 0;
              ['again', 'hard', 'good', 'easy'].forEach(function(k){ c[k] = Math.max(0, (Number(c[k]) || 0) - (Number(c['r_' + k]) || 0)); });
              c.reviews = Number(c.new) || 0;
              return c;
            });
          }
          return {
            rows: rows,
            options: {
              keys: vari ? ['gain', 'loss'] : series.map(function(s){ return s.key; }), series_colors: colors, labels: labels,
              unit: vari ? undefined : ((unit === 'seconds' || unit === 'level' || unit === 'load' || unit === 'rmse') ? unit : undefined),
              variation: vari,
              // Line: the level drawn as a line (an area stacked by series), not bars; also the averages (Review Speed,
              // FSRS Loss by Fatigue), their bars without answers left out (the line goes over them, not down to 0)
              line_view: !!o.line_view && !!LINE_UNITS[unit] && !vari,
              line_skip_empty: unit !== 'level',
              value_load: unit === 'load' || data.value === 'load' || data.value === 'ratio',  // reviews a day: decimals in the tooltip
              value_pct: data.value === 'pct',  // Memorised's average recall of a card
              value_days: data.value === 'days',  // an average stability: days in the tooltip
              show_breakdown: vari || !single, added_style: !vari && single,
              has_cumulative: !!data.cumulative && unit !== 'level' && unit !== 'seconds',
              metric_mode: unit === 'seconds' ? 'seconds' : unit === 'rmse' ? 'percent' : (data.measure === 'time' ? 'time' : 'reviews'),
              time_tip: data.measure === 'time',  // the tooltip's values as times (Ratings' Time view)
              show_average: (o.show_average !== false) && data.average !== false && unit !== 'level' && type !== 'due_today',
              now_start: type === 'due_today' ? data.start : undefined,
              show_percent: !!(o.show_percent && data.percent && !single && !vari),
              hidden_review_types: vari ? [] : (o.hidden_series || []),
              adaptive_binning: o.adaptive_binning !== false && type !== 'due_today',
              expected_marks: type === 'fsrs_calibration' || type === 'forgetting_curve',  // FSRS's expected share on each bar
              // Show Trend (app.js TREND): with "Show as %", the trend of the passed share; the unit of a bar's rows
              show_trend: o.show_trend !== false && TREND_UNIT[type] !== undefined && !vari,
              trend_pass_keys: series.some(function(s){ return s.key === 'again'; }) ? series.map(function(s){ return s.key; }).filter(function(k){ return k !== 'again'; })
                : (series.some(function(s){ return s.key === 'passed'; }) ? ['passed'] : null),
              trend_unit: TREND_UNIT[type],
              // rows that are values counted from the first one (seconds, an interval, the n-th review): a zoom morphs
              // them anchored on the left (activity.js updateData)
              value_axis: TREND_UNIT[type] !== undefined && TREND_UNIT[type] !== 'day',
            },
          };
        };
        const sub = Object.assign({}, ctx, {
          kind: 'extra', type: type, derive: derive,
          // (bars of seconds / intervals / hours: zoomed on their own, app.js ZLINK)
          options: Object.assign({chart_opacity_pct: 100}, ctx.options || {}),
          statText: statText(type, data0, cur),
          pills: function(pillsEl, apply, o){
            if (type === 'custom_bar') customBarPill(pillsEl, function(){ return now; });
            if ((data0.card_types || []).length){
              // the card type of the answers counted, read again by Python: a pill
              // with the type counted and a menu of all of them
              let curK = data0.card_type || 'all';
              const kp = document.createElement('button');
              kp.className = 'dd-pill dd-pill-opt' + (curK !== 'all' ? ' on' : '');
              kp.innerHTML = '<span></span>' + PILL_CHEV;
              kp.firstChild.textContent = DD.t(CARD_TYPE_NAMES[curK] || curK);
              kp.title = DD.t('The cards counted: all, or one kind');
              kp.addEventListener('click', function(e){
                e.stopPropagation();
                const r = kp.getBoundingClientRect();
                DD.menu({x: r.left, y: r.bottom + 2}, data0.card_types.map(function(k){ return [k, DD.t(CARD_TYPE_NAMES[k] || k), k === curK, null, 'radio']; }), function(k){
                  if (!CARD_TYPE_NAMES[k] || k === curK) return;
                  curK = k;
                  kp.firstChild.textContent = DD.t(CARD_TYPE_NAMES[k]);
                  kp.classList.toggle('on', k !== 'all');
                  DD.setWidgetSetting(type, 'card_type', k);
                });
              });
              pillsEl.appendChild(kp);
            }
            if (type === 'ratings'){
              // Time: the time spent on each rating, read again by Python
              const t = document.createElement('button');
              t.className = 'dd-pill' + (data0.measure === 'time' ? ' on' : '');
              t.textContent = 'Time';
              t.title = 'The time spent on each rating instead of the reviews';
              t.addEventListener('click', function(){
                const on = !t.classList.contains('on');
                t.classList.toggle('on', on);
                DD.setWidgetSetting(type, 'measure', on ? 'time' : 'count');
              });
              pillsEl.appendChild(t);
            }
            if (type === 'stability_trend'){
              // Median: the bars of the median stability, read again by Python
              const t = document.createElement('button');
              t.className = 'dd-pill' + (data0.measure === 'median' ? ' on' : '');
              t.textContent = 'Median';
              t.title = 'The median stability instead of the mean';
              t.addEventListener('click', function(){
                const on = !t.classList.contains('on');
                t.classList.toggle('on', on);
                DD.setWidgetSetting(type, 'measure', on ? 'median' : 'mean');
              });
              pillsEl.appendChild(t);
            }
            if (type === 'memorised' && (data0.measures || []).length){
              // what the bars count, read again by Python: a pill with the
              // view shown and a menu of all of them
              let curM = data0.measure || data0.measures[0];
              const m = document.createElement('button');
              m.className = 'dd-pill dd-pill-opt' + (curM !== data0.measures[0] ? ' on' : '');
              m.innerHTML = '<span></span>' + PILL_CHEV;
              m.firstChild.textContent = DD.t(MEASURE_NAMES[curM] || curM);
              m.title = DD.t('What the bars count');
              m.addEventListener('click', function(e){
                e.stopPropagation();
                const r = m.getBoundingClientRect();
                DD.menu({x: r.left, y: r.bottom + 2}, data0.measures.map(function(k){ return [k, DD.t(MEASURE_NAMES[k] || k), k === curM, null, 'radio']; }), function(k){
                  if (!MEASURE_NAMES[k] || k === curM) return;
                  curM = k;
                  m.firstChild.textContent = DD.t(MEASURE_NAMES[k]);
                  m.classList.toggle('on', k !== data0.measures[0]);
                  DD.setWidgetSetting(type, 'measure', k);
                });
              });
              pillsEl.appendChild(m);
            }
            let lb = null, vb = null;
            // the Line chosen, kept apart (the options' line_view is the view drawn: off under Variation)
            if (o.line_chosen === undefined) o.line_chosen = !!o.line_view;
            if (LINE_UNITS[data0.unit]){
              // Line: the level (or the average) as a line, an area under it (drawn only); Line and Variation: one view at a time, the
              // line comes in from left to right as at its intro, back to Variation a cross-fade (the bars and the line
              // morph into each other)
              lb = document.createElement('button');
              lb.className = 'dd-pill' + (o.line_view && !o.variation ? ' on' : '');
              lb.textContent = 'Line';
              lb.title = 'As a line instead of bars';
              lb.addEventListener('click', function(){
                const on = !(o.line_view && !o.variation), offVar = on && !!o.variation;
                o.line_chosen = on;
                lb.classList.toggle('on', on); if (vb && offVar) vb.classList.remove('on');
                // (from the bars: they narrow into the line; from Variation: the line comes in as at its intro, from
                // left to right; activity.js _lineMixStart)
                apply(offVar ? {line_view: on, variation: false} : {line_view: on}, ['line_view', on]);
                if (offVar) DD.call('set_setting', {section: type, key: 'variation', value: false}).catch(function(){});
              });
              pillsEl.appendChild(lb);
            }
            if (data0.variation_colors){
              // Variation: each bar the gain or loss over its days (drawn only)
              vb = document.createElement('button');
              vb.className = 'dd-pill' + (o.variation ? ' on' : '');
              vb.textContent = 'Variation';
              vb.title = 'The change from one bar to the next';
              vb.addEventListener('click', function(){
                // (Line stays chosen under Variation: Variation off, the line comes back, from left to right as at its
                // intro, activity.js _lineMixStart)
                const on = !o.variation, offLine = on && !!o.line_view;
                vb.classList.toggle('on', on); if (lb) lb.classList.toggle('on', !on && !!o.line_chosen);
                const go = function(){ apply(on ? {variation: true} : {variation: false, line_view: !!o.line_chosen}, ['variation', on]); };
                // (from the line: a cross-fade, not the bars' morph into the gains / losses)
                if (offLine) DD.applyUpdate(el, go, true); else go();
              });
              pillsEl.appendChild(vb);
            }
            if (type === 'introduced'){
              // the cards introduced again after a reset, counted or not (both views; drawn only)
              const ri = document.createElement('button');
              ri.className = 'dd-pill' + (o.first_reintro !== false ? ' on' : '');
              ri.textContent = 'Re-introduced';
              ri.title = 'Count the cards introduced again after a reset';
              ri.addEventListener('click', function(){
                const on = o.first_reintro === false;
                ri.classList.toggle('on', on);
                apply({first_reintro: on}, ['first_reintro', on]);
              });
              pillsEl.appendChild(ri);
            }
            const a = data0.alt;
            if (!a) return;
            const b = document.createElement('button');
            b.className = 'dd-pill' + (o.alt_view ? ' on' : '');
            b.textContent = a.label;
            b.addEventListener('click', function(){
              const on = !o.alt_view;
              b.classList.toggle('on', on);
              apply({alt_view: on}, ['alt_view', on]);
            });
            pillsEl.appendChild(b);
          },
        });
        // a click on a bar: its cards in the browser (window._browse; the answers behind it: browser_search.reviews_sql)
        let now = data0;
        sub.browse = function(r, label){
          const ms = now.range, kind = now.card_type && now.card_type !== 'all' ? now.card_type : undefined;  // (its card type)
          if (type === 'answer_time') return ms ? {revs: {ms: ms, secs: [r[0], r[1]], kind: kind}} : null;  // a row a second
          if (type === 'interval_ratings') return ms ? {revs: {ms: ms, ivl: [r[0] + 1, r[1] + 1], kind: kind}} : null;  // from 1 day
          if (type === 'leech_detector') return {leech: [r[0], r[1]]};  // the cards of those bars (window._browse)
          if (type === 'stability_increase') return {sinc: [r[0], r[1]]};
          if (type === 'custom_bar') return label ? {revs: {label: label, searches: (now.searches || []).map(function(s){ return s.q || ''; })}} : null;  // (the answers of its searches' cards)
          if (!label || type === 'fsrs_fatigue' || type === 'card_states' || type === 'load_trend' || type === 'stability_trend' || type === 'memorised' || type === 'due_today' || type === 'rating_fatigue' || type === 'sibling_ratings' || type === 'fsrs_calibration' || type === 'forgetting_curve') return null;  // (cards in a state, due later: no answers)
          if (type === 'forgotten') return {revs: {label: label, lapse: true}};
          if (type === 'resets') return {revs: {label: label, reset: true}};  // the cards reset that day
          if (type === 'introduced' || type === 'introduced_load') return {revs: {label: label, introduced: true}};
          if ((type === 'ratings' || type === 'review_speed') && kind) return {revs: {label: label, kind: kind}};  // the answers of its card type
          return {kind: 'reviewed', label: label};
        };
        // the stat reads the data of the moment (an update brings new totals)
        const inst = DD.dailyMount(el, sub);
        const upd = inst.update;
        // (its mode passed on: "timespan" for another period, the bars morph in place as on the other charts)
        // Custom Bar with other searches: its bars are others (a search added or taken off appeared at once), the old
        // chart fades out over the new one
        inst.update = function(data, mode){
          const other = type === 'custom_bar' && searchesKey(now) !== searchesKey(data);
          now = data || {}; sub.statText = statText(type, data, cur);
          if (other) DD.applyUpdate(el, function(){ upd(data, mode); }, true); else upd(data, mode);
        };
        // a new theme: its series colours come with it (DD.theme.series, window.py _push_theme), the chart repaints at
        // once with the charts colored by the theme (its data read again later brings the same colours)
        const setTheme0 = inst.setTheme;
        inst.setTheme = function(){
          setTheme0.apply(inst, arguments);
          const c = DD.theme && DD.theme.series && DD.theme.series[type];
          if (!c || !now || !now.series) return;
          const paint = function(list, m){ return (list || []).map(function(s){ return m && m[s.key] ? Object.assign({}, s, {color: m[s.key]}) : s; }); };
          const d = Object.assign({}, now, {series: paint(now.series, c.series)});
          if (now.alt && c.alt) d.alt = Object.assign({}, now.alt, {series: paint(now.alt.series, c.alt)});
          if (now.variation_colors && c.variation) d.variation_colors = c.variation;
          const p = DD._noAnim; DD._noAnim = true;
          try { inst.update(d); } finally { DD._noAnim = p; }
        };
        return inst;
      },
    });
  }
  ['ratings', 'review_speed', 'forgotten', 'resets', 'introduced', 'introduced_load', 'answer_time', 'interval_ratings', 'rating_fatigue', 'sibling_ratings', 'card_states', 'load_trend', 'stability_trend', 'memorised', 'fsrs_calibration', 'forgetting_curve', 'fsrs_fatigue', 'leech_detector', 'stability_increase', 'custom_bar', 'future_retention', 'due_today'].forEach(registerDaily);

  // the frame loop of a grid chart (week_hours, SxR, the gap by button): st.t from 0 to 1 over dur() ms, a draw
  // each frame while it runs and once after a change (st.last), the redraw on resize; with the setOptions,
  // setTheme and destroy the three share (their update is their own)
  function gridLoop(st, el, plot, statEl, head, draw, resize, dur){
    function frame(now){
      if (st.t < 1){ if (st.start === null) st.start = now; st.t = Math.min(1, (now - st.start) / dur()); }
      const needs = st.t < 1;
      if (needs || st.last) draw();
      st.last = needs;
      return needs;
    }
    const resizer = new ResizeObserver(function(){ DD.frame.resized(frame, function(){ resize(); st.last = true; }); });
    DD.frame.observe(resizer, plot);
    if (st.t >= 1) draw();
    DD.frame.add(frame);
    const kick = function(){ st.last = true; DD.frame.kick(); };
    return {
      setOptions: function(o){ Object.assign(st.opts, o); kick(); },
      setTheme: kick,
      destroy: function(){ DD.frame.remove(frame); resizer.disconnect(); el.innerHTML = ''; if (statEl) statEl.textContent = ''; const p = head && head.querySelector('.dd-pills'); if (p) p.innerHTML = ''; },
    };
  }
  // ---- Week by Hour: 7 days by 24 hours, each cell as dark as its reviews ----
  const FONT = '11px "Segoe UI",-apple-system,BlinkMacSystemFont,sans-serif';
  function weekMount(el, ctx){
    el.innerHTML = '<div class="dd-plot"><canvas></canvas><div class="dd-tip"></div></div>';
    const plot = el.firstChild, canvas = plot.querySelector('canvas'), g = canvas.getContext('2d');
    const head = ctx.head, statEl = head && head.querySelector('.dd-stat');
    const st = {data: ctx.data || {}, opts: Object.assign({chart_opacity_pct: 100}, ctx.options || {}), from: {}, t: ctx.animate ? 0 : 1, start: null, hover: -1, geo: null, w: 1, h: 1, last: true};
    st.hoverIdx = -1; st.canvas = canvas;
    Object.defineProperty(st, 'colors', {get: function(){ return DD.theme.chart; }});
    Object.defineProperty(st, 'hoverIdx', {get: function(){ return st.hover; }, set: function(v){ st.hover = v; }});
    const counts = function(d){ return (d && d.counts) || {}; };
    function top(){ let m = 0; const c = counts(st.data); Object.keys(c).forEach(function(k){ if (c[k] > m) m = c[k]; }); return m; }
    function share(key){
      const tp = top(), n = Number(counts(st.data)[key] || 0);
      const nw = (tp > 0 && n > 0) ? Math.max(0.12, Math.sqrt(n / tp)) : 0;
      if (st.t >= 1) return nw;
      const old = Number(st.from[key] || 0);
      return old + (nw - old) * st.t;
    }
    // a share of a grid of other data (the old one while By Day is switched): no transition of its own
    function shareOf(d, key){
      let tp = 0; const c = counts(d); Object.keys(c).forEach(function(k){ if (c[k] > tp) tp = c[k]; });
      const n = Number(c[key] || 0);
      return (tp > 0 && n > 0) ? Math.max(0.12, Math.sqrt(n / tp)) : 0;
    }
    function rowDays(d){ return (d || st.data).monday_first ? [0, 1, 2, 3, 4, 5, 6] : [6, 0, 1, 2, 3, 4, 5]; }
    // the grid's rows: the 7 days of the week, or (By Day) the days of the period, keyed in counts by 'key,hour'
    function rowList(d){
      d = d || st.data;
      if (d.view === 'day') return (d.rows || []).map(function(r, i){ return {key: i, short: r.short, long: r.long}; });
      return rowDays(d).map(function(wd){ return {key: wd, short: DD.t((d.short || [])[wd] || ''), long: DD.t((d.long || [])[wd] || '')}; });
    }
    // the By Day pill in the header (its state is the widget's setting 'view')
    function pill(){
      const pills = head && head.querySelector('.dd-pills'); if (!pills) return;
      pills.innerHTML = '';
      const on = st.data.view === 'day';
      const b = document.createElement('button');
      b.className = 'dd-pill' + (on ? ' on' : '');
      b.textContent = DD.t('By Day');
      b.title = DD.t('Each day of the period, instead of the days of the week');
      b.addEventListener('click', function(e){ e.stopPropagation(); b.classList.toggle('on', !on); DD.setWidgetSetting('week_hours', 'view', on ? 'week' : 'day'); });
      pills.appendChild(b);
      if (st.data.include_filtered != null && DD.optionsPill)
        DD.optionsPill(pills, 'week_hours', 'Which reviews are counted', [['include_filtered', 'Include Filtered Reviews', st.data.include_filtered !== false, true]]);
    }
    function resize(){
      const f = DD.fitCanvas(canvas, g); st.w = f.w; st.h = f.h;
    }
    function geometry(d){
      g.font = FONT;
      const rows = rowList(d), nr = Math.max(1, rows.length);
      let lw = 0; rows.forEach(function(r){ lw = Math.max(lw, g.measureText(r.short).width); });
      const left = 6 + Math.ceil(lw) + 8, bottom = 14 + 4;
      const w = Math.max(10, st.w - left - 6), h = Math.max(10, st.h - 4 - bottom);
      return {left: left, top: 4, cw: w / 24, ch: h / nr, bottom: bottom, rows: rows, nr: nr};
    }
    // By Day switched on or off: the old grid fades out while the new one comes in row by row from the top
    // (its rows and their number differ, so its cells have nothing to move from)
    function draw(){
      g.clearRect(0, 0, st.w, st.h);
      const sw = st.swap;
      if (!sw || st.t >= 1){ st.swap = null; st.geo = grid(st.data, share, null, true); return; }
      const e = st.t * st.t * (3 - 2 * st.t);
      grid(sw.data, function(k){ return sw.share[k] || 0; }, function(){ return Math.max(0, 1 - e * 1.6); }, false);
      st.geo = grid(st.data, function(k){ return shareOf(st.data, k); }, function(row, nr){
        const at = 0.25 + 0.45 * (nr > 1 ? row / (nr - 1) : 0);  // this row's start in the transition
        return Math.max(0, Math.min(1, (e - at * 0.6) / 0.4));
      }, true);
    }
    // one grid: its data, a cell's share, the opacity of each row (null: all shown)
    function grid(d, shareFn, alphaOf, live){
      const C = DD.theme.chart, dark = !!C.is_dark, geo = geometry(d);
      const base = d.color || C.bar || '#3b82f6';
      const empty = dark ? 'rgba(255,255,255,0.055)' : 'rgba(0,0,0,0.047)';
      const op = Math.max(0.05, Math.min(1, (st.opts.chart_opacity_pct != null ? st.opts.chart_opacity_pct : 100) / 100));
      const gap = 2, radius = Math.max(1, Math.min(geo.cw, geo.ch) * 0.18);
      const rr = function(x, y, w, h){ g.beginPath(); if (g.roundRect) g.roundRect(x, y, w, h, radius); else g.rect(x, y, w, h); };
      geo.rows.forEach(function(rw, row){
        const a = alphaOf ? alphaOf(row, geo.nr) : 1;
        if (a <= 0) return;
        g.globalAlpha = a;
        for (let hour = 0; hour < 24; hour++){
          const x = geo.left + hour * geo.cw + gap / 2, y = geo.top + row * geo.ch + gap / 2, w = Math.max(1, geo.cw - gap), h = Math.max(1, geo.ch - gap);
          rr(x, y, w, h); g.fillStyle = empty; g.fill();
          const sh = shareFn(rw.key + ',' + hour);
          if (sh > 0){ rr(x, y, w, h); g.fillStyle = U.rgba(base, Math.min(1, sh) * op); g.fill(); }
          if (live && st.hover === row * 24 + hour){ rr(x, y, w, h); g.strokeStyle = U.rgba(C.text_primary || '#ffffff', 200 / 255); g.lineWidth = 1.2; g.stroke(); }
        }
      });
      g.font = FONT; g.fillStyle = C.text_secondary || '#888'; g.textBaseline = 'middle'; g.textAlign = 'right';
      const every = Math.max(1, Math.ceil(12 * 0.8 / geo.ch));  // one name in so many rows when they are thin
      geo.rows.forEach(function(rw, row){
        if (row % every) return;
        const a = alphaOf ? alphaOf(row, geo.nr) : 1;
        if (a <= 0) return;
        g.globalAlpha = a;
        g.fillText(rw.short, geo.left - 6, geo.top + row * geo.ch + geo.ch / 2);
      });
      // the hours' axis is the same in both grids: drawn once, by the new one
      g.globalAlpha = live ? 1 : 0;
      g.textAlign = 'center'; g.textBaseline = 'top';
      const step = geo.cw * 3 >= g.measureText('00').width + 6 ? 3 : 6;
      if (live) for (let hour = 0; hour < 24; hour += step) g.fillText(String(hour), geo.left + hour * geo.cw + geo.cw / 2, geo.top + geo.nr * geo.ch + 2);
      g.globalAlpha = 1;
      return geo;
    }
    function stats(){
      if (!statEl) return;
      const c = counts(st.data); let total = 0, best = null, bestN = -1;
      Object.keys(c).forEach(function(k){ total += c[k]; if (c[k] > bestN){ bestN = c[k]; best = k; } });
      if (total <= 0){ statEl.textContent = ''; return; }
      const byKey = {}; rowList().forEach(function(r){ byKey[r.key] = r; });
      const dayTot = {};
      Object.keys(c).forEach(function(k){ const d = k.split(',')[0]; dayTot[d] = (dayTot[d] || 0) + c[k]; });
      let bd = null; Object.keys(dayTot).forEach(function(d){ if (bd === null || dayTot[d] > dayTot[bd]) bd = d; });
      const bp = best.split(','), br = byKey[bp[0]] || {short: ''}, bdr = byKey[bd] || {long: ''};
      statEl.textContent = DD.t('Peak: {when}', {when: br.short + ' ' + ('0' + bp[1]).slice(-2) + ':00'}) + '  ·  ' + DD.t('Busiest day: {day} ({value}%)', {day: bdr.long, value: trim(dayTot[bd] * 100 / total, 0)});
    }
    stats(); pill();
    resize();
    // a click on a cell: the cards answered then (window._browse: its day of the week or its day / days, its hour)
    plot._ddBrowse = function(){
      const i = st.hover; if (i == null || i < 0) return null;
      const rw = rowList()[Math.floor(i / 24)], hour = i % 24; if (!rw) return null;
      if (st.data.view === 'day'){ const r = (st.data.rows || [])[rw.key]; return r && r.ms ? {revs: {ms: r.ms, hour: hour}} : null; }
      return st.data.range ? {revs: {ms: st.data.range, weekday: rw.key, hour: hour}} : null;
    };
    DD.hover.attach(plot, st, {
      index: function(mx, my){
        const geo = st.geo; if (!geo) return -1;
        const col = Math.floor((mx - geo.left) / geo.cw), row = Math.floor((my - geo.top) / geo.ch);
        return (mx >= geo.left && my >= geo.top && col >= 0 && col < 24 && row >= 0 && row < geo.nr && row < geo.rows.length) ? row * 24 + col : -1;
      },
      rows: function(i){
        const rw = rowList()[Math.floor(i / 24)] || {key: -1, long: ''}, hour = i % 24, n = Number(counts(st.data)[rw.key + ',' + hour] || 0);
        let total = 0; Object.keys(counts(st.data)).forEach(function(k){ total += counts(st.data)[k]; });
        const p2 = function(v){ return ('0' + v).slice(-2); };
        const rows = [{header: true, text: rw.long + '  ' + p2(hour) + ':00–' + p2((hour + 1) % 24) + ':00'}, {text: DD.tn('{n} review', '{n} reviews', n, {n: fmt(n)})}];
        if (total > 0) rows.push({text: DD.t('{value}% of the reviews', {value: trim(n * 100 / total, 1)})});
        return rows;
      },
      redraw: function(){ st.last = true; DD.frame.kick(); },
    });
    return Object.assign(gridLoop(st, el, plot, statEl, head, draw, resize, function(){ return st.swap ? 650 * DD.speed() : ctx.animate && !st.shown ? DD.intro(500) : 300 * (st.k || 1); }), {
      update: function(data){
        const from = {}; Object.keys(counts(st.data)).concat(Object.keys(counts(data))).forEach(function(k){ from[k] = share(k); });
        // By Day switched: the old grid as it is now, to fade out (see draw)
        st.swap = (data && data.view === 'day') !== (st.data.view === 'day') && !DD._noAnim ? {data: st.data, share: from} : null;
        st.from = from; st.shown = true; st.data = data; st.t = DD._noAnim ? 1 : 0; st.start = null; st.k = DD.calm ? DD.calm() : 1; stats(); pill(); st.last = true; DD.frame.kick();
      },
    });
  }
  DD.registerChart('week_hours', {mount: weekMount});
  // ---- SxR Heatmap: the review cards now by FSRS stability (rows, high at the top) and
  // retrievability (columns, low on the left); the darker a cell, the more cards. Binned here from the points read
  // in Python (metrics/sxr.py), by the chart's options: the width of the columns, about how many rows, a log scale.
  const SXR_R_BINS = [1, 2, 5, 10], SXR_S_ROWS = [10, 15, 20, 30, 40];
  const SXR_MONTH = 365 / 12;
  function sxrDays(d){
    if (d < 30) return DD.t('{value} d', {value: trim(d, d < 10 ? 1 : 0)});
    const m = d / SXR_MONTH;
    if (m < 11.95) return DD.tn('{value} mo', '{value} mo', m, {value: trim(m, m < 10 ? 1 : 0)});
    const y = d / 365; return DD.tn('{value} yr', '{value} yr', y, {value: trim(y, y < 10 ? 1 : 0)});
  }
  // a linear step of stability at least raw days, round in its unit: days, 1 / 2 / 3 / 4 / 6 months, years
  function sxrLinStep(raw){
    if (raw < 25) return niceStep(raw);
    const m = raw / SXR_MONTH, k = [1, 2, 3, 4, 6].filter(function(x){ return x >= m - 1e-9; })[0];
    return k ? k * SXR_MONTH : niceStep(raw / 365) * 365;
  }
  // a round step at least raw (1, 2, 2.5, 3, 4, 5, 6, 8 times a power of ten: near the rows asked)
  function niceStep(raw){
    const p = Math.pow(10, Math.floor(Math.log10(raw)));
    const m = [1, 2, 2.5, 3, 4, 5, 6, 8, 10].filter(function(x){ return x * p >= raw - 1e-9; })[0];
    return m * p;
  }
  // the grid of the payload: {counts 'col,row' (row 0 at the bottom), top, total, nc, nr, rLo / wm (in 0.1 %), edge(k):
  // the stability in days at the bottom of row k, rMean, sMedian}, or null (no card)
  function sxrBins(d){
    const p = (d && d.points) || [];
    const wm = 10 * (SXR_R_BINS.indexOf(Number(d.r_bin)) >= 0 ? Number(d.r_bin) : 5);
    const want = SXR_S_ROWS.indexOf(Number(d.s_rows)) >= 0 ? Number(d.s_rows) : 20, log = d.log_s !== false;
    const f = log ? function(v){ return Math.log10(v); } : function(v){ return v; };
    let rMin = Infinity, rMax = -Infinity, sMin = Infinity, sMax = -Infinity, total = 0, rSum = 0;
    const pts = [];
    for (let i = 0; i + 2 < p.length; i += 3){
      const r = Number(p[i]), s = Math.max(0.1, Number(p[i + 1]) / 10), n = Number(p[i + 2]) || 0;
      if (n <= 0) continue;
      pts.push([r, s, n]);
      rMin = Math.min(rMin, r); rMax = Math.max(rMax, r); sMin = Math.min(sMin, s); sMax = Math.max(sMax, s);
      total += n; rSum += r * n;
    }
    if (!total) return null;
    const rLo = Math.floor(rMin / wm) * wm, nc = Math.max(1, Math.ceil((rMax - rLo) / wm - 1e-9) || 1);
    const step = (log ? niceStep : sxrLinStep)(Math.max(f(sMax) - f(sMin), log ? 0.05 : 0.5) / want);
    const sLo = Math.floor(f(sMin) / step + 1e-9) * step, nr = Math.max(1, Math.ceil((f(sMax) - sLo) / step - 1e-9) || 1);
    const counts = {}; let top = 0;
    pts.forEach(function(q){
      const c = Math.min(nc - 1, Math.max(0, Math.floor((q[0] - rLo) / wm)));
      const row = Math.min(nr - 1, Math.max(0, Math.floor((f(q[1]) - sLo) / step + 1e-9)));
      const k = c + ',' + row; counts[k] = (counts[k] || 0) + q[2]; if (counts[k] > top) top = counts[k];
    });
    pts.sort(function(a, b){ return a[1] - b[1]; });
    let acc = 0, sMedian = pts[pts.length - 1][1];
    for (let i = 0; i < pts.length; i++){ acc += pts[i][2]; if (acc * 2 >= total){ sMedian = pts[i][1]; break; } }
    const edge = function(k){ const v = sLo + k * step; return log ? Math.pow(10, v) : v; };
    // its rows' stability as text: in days when a linear step is in days (8 d, 16 d, 24 d, 32 d: not 1.1 mo)
    const sText = !log && step < 25 ? function(v){ return DD.t('{value} d', {value: trim(v, v < 10 ? 1 : 0)}); } : sxrDays;
    return {counts: counts, top: top, total: total, nc: nc, nr: nr, rLo: rLo, wm: wm, edge: edge, sText: sText, rMean: rSum / total / 10, sMedian: sMedian};
  }
  // a cross-fade's ease (the old grid out, the new one in)
  const crossEase = function(t){ return t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2; };
  // the same grid (columns, rows and their edges): its cells morph one by one; else the grids cross-fade
  function sxrSame(a, b){ return !!(a && b && a.nc === b.nc && a.nr === b.nr && a.rLo === b.rLo && a.wm === b.wm && Math.abs(a.edge(0) - b.edge(0)) < 1e-9 && Math.abs(a.edge(a.nr) - b.edge(b.nr)) < 1e-9); }
  function sxrMount(el, ctx){
    el.innerHTML = '<div class="dd-plot"><canvas></canvas><div class="dd-tip"></div></div>';
    const plot = el.firstChild, canvas = plot.querySelector('canvas'), g = canvas.getContext('2d');
    const head = ctx.head, statEl = head && head.querySelector('.dd-stat');
    const st = {data: ctx.data || {}, opts: Object.assign({chart_opacity_pct: 100}, ctx.options || {}), from: {}, t: ctx.animate ? 0 : 1, start: null, hover: -1, geo: null, w: 1, h: 1, last: true};
    st.canvas = canvas; st.bins = sxrBins(st.data);
    Object.defineProperty(st, 'colors', {get: function(){ return DD.theme.chart; }});
    Object.defineProperty(st, 'hoverIdx', {get: function(){ return st.hover; }, set: function(v){ st.hover = v; }});
    function shareNow(b, key){
      const n = b ? Number(b.counts[key] || 0) : 0;
      return (b && b.top > 0 && n > 0) ? Math.max(0.12, Math.sqrt(n / b.top)) : 0;
    }
    function share(key){
      const nw = shareNow(st.bins, key);
      if (st.t >= 1) return nw;
      const old = Number(st.from[key] || 0);
      return old + (nw - old) * st.t;
    }
    // its options, in the chart's options icon (DD.optionsPill)
    function pill(){
      const pills = head && head.querySelector('.dd-pills'); if (!pills || !DD.optionsPill) return;
      pills.innerHTML = '';
      const d = st.data;
      DD.optionsPill(pills, 'sxr_heatmap', "This chart's options", [
        ['r_bin', 'Retrievability Bins', Number(d.r_bin) || 5, 5, SXR_R_BINS.map(function(v){ return [v, v + '%']; })],
        ['s_rows', 'Stability Rows', Number(d.s_rows) || 20, 20, SXR_S_ROWS.map(function(v){ return [v, String(v)]; })],
        ['log_s', 'Logarithmic Stability', d.log_s !== false, true],
        ['two_colors', 'Two-Color Gradient', d.two_colors !== false, true],
      ]);
    }
    function stats(){
      if (!statEl) return;
      const b = st.bins;
      statEl.textContent = b ? DD.tn('{n} card', '{n} cards', b.total, {n: fmt(b.total)}) + '  ·  ' + DD.t('Average retrievability: {value}%', {value: trim(b.rMean, 1)}) + '  ·  ' + DD.t('Median stability: {value}', {value: sxrDays(b.sMedian)}) : '';
    }
    function resize(){ const f = DD.fitCanvas(canvas, g); st.w = f.w; st.h = f.h; }
    function geometry(b){
      g.font = FONT;
      const nc = b ? b.nc : 1, nr = b ? b.nr : 1;
      let lw = 0;
      if (b) for (let k = 0; k <= nr; k++) lw = Math.max(lw, g.measureText(b.sText(b.edge(k))).width);
      const left = 4 + 14 + Math.ceil(lw) + 6, bottom = 14 + 2 + 14, top = 6;
      const right = Math.ceil(g.measureText('100%').width / 2) + 2;  // (the last column's edge label)
      const w = Math.max(10, st.w - left - right), h = Math.max(10, st.h - top - bottom);
      return {left: left, top: top, cw: w / nc, ch: h / nr, nc: nc, nr: nr};
    }
    function draw(){
      g.clearRect(0, 0, st.w, st.h);
      st.geo = geometry(st.bins);
      if (st.prev !== undefined && st.t < 1){
        const e = crossEase(st.t), pb = st.prev, nb = st.bins;
        layer(pb, st.prevData, function(k){ return shareNow(pb, k); }, 1 - e, false);
        layer(nb, st.data, function(k){ return shareNow(nb, k); }, e, true);
      } else layer(st.bins, st.data, share, 1, true);
    }
    // a grid (b, of its payload d) at an opacity; main: the one shown (its hovered cell outlined)
    function layer(b, d, shareOf, alpha, main){
      if (!b || alpha <= 0) return;
      const C = DD.theme.chart, dark = !!C.is_dark, geo = geometry(b);
      g.globalAlpha = alpha;
      const base = d.color || C.bar || '#3b82f6';
      const empty = dark ? 'rgba(255,255,255,0.055)' : 'rgba(0,0,0,0.047)';
      const op = Math.max(0.05, Math.min(1, (st.opts.chart_opacity_pct != null ? st.opts.chart_opacity_pct : 100) / 100));
      // a cell's fill for its share (0.12 to 1): one colour by opacity, or (Two-Color Gradient) from the Easy colour
      // (fewest cards) to the Again colour (most), opaque (a cell coming in fades in)
      const lo = U.hexToRgb(C.easy || '#6495ed'), hi = U.hexToRgb(C.again || '#ff3b30');
      const fill = d.two_colors === false ? function(sh){ return U.rgba(base, Math.min(1, sh) * op); } : function(sh){
        // (the cells with few cards dimmer: a full blue stood out as much as a full red)
        const t = Math.max(0, Math.min(1, (sh - 0.12) / 0.88)), a = op * (0.4 + 0.6 * t) * Math.min(1, sh / 0.12);
        return 'rgba(' + Math.round(lo.r + t * (hi.r - lo.r)) + ',' + Math.round(lo.g + t * (hi.g - lo.g)) + ',' + Math.round(lo.b + t * (hi.b - lo.b)) + ',' + a + ')';
      };
      const gap = Math.min(2, Math.min(geo.cw, geo.ch) * 0.2), radius = Math.max(0.5, Math.min(geo.cw, geo.ch) * 0.18);
      const rr = function(x, y, w, h){ g.beginPath(); if (g.roundRect) g.roundRect(x, y, w, h, radius); else g.rect(x, y, w, h); };
      for (let rowT = 0; rowT < geo.nr; rowT++){
        const row = geo.nr - 1 - rowT;
        for (let c = 0; c < geo.nc; c++){
          const x = geo.left + c * geo.cw + gap / 2, y = geo.top + rowT * geo.ch + gap / 2, w = Math.max(1, geo.cw - gap), h = Math.max(1, geo.ch - gap);
          rr(x, y, w, h); g.fillStyle = empty; g.fill();
          const sh = shareOf(c + ',' + row);
          if (sh > 0){ rr(x, y, w, h); g.fillStyle = fill(sh); g.fill(); }
          if (main && st.hover === rowT * geo.nc + c){ rr(x, y, w, h); g.strokeStyle = U.rgba(C.text_primary || '#ffffff', 200 / 255); g.lineWidth = 1.2; g.stroke(); }
        }
      }
      g.font = FONT; g.fillStyle = C.text_secondary || '#888';
      // the stability at the edges of the rows (one in so many when they are thin)
      g.textAlign = 'right'; g.textBaseline = 'middle';
      const everyR = Math.max(1, Math.ceil(14 / geo.ch));
      for (let k = 0; k <= geo.nr; k += everyR) g.fillText(b.sText(b.edge(k)), geo.left - 6, Math.max(geo.top + 5, Math.min(geo.top + geo.nr * geo.ch - 5, geo.top + (geo.nr - k) * geo.ch)));
      // the retrievability at the edges of the columns
      g.textAlign = 'center'; g.textBaseline = 'top';
      const everyC = Math.max(1, Math.ceil((g.measureText('100%').width + 8) / geo.cw));
      for (let c = 0; c <= geo.nc; c += everyC) g.fillText(trim((b.rLo + c * b.wm) / 10, 1) + '%', geo.left + c * geo.cw, geo.top + geo.nr * geo.ch + 2);
      // the axes' names
      g.fillText(DD.t('Retrievability'), geo.left + geo.nc * geo.cw / 2, geo.top + geo.nr * geo.ch + 16);
      g.save(); g.translate(4, geo.top + geo.nr * geo.ch / 2); g.rotate(-Math.PI / 2); g.textBaseline = 'top';
      g.fillText(DD.t('Stability'), 0, 0); g.restore();
      g.globalAlpha = 1;
    }
    // a cell: its column, its row from the bottom, the ranges it holds
    function cellOf(i){
      const b = st.bins; if (!b || i == null || i < 0) return null;
      const c = i % b.nc, row = b.nr - 1 - Math.floor(i / b.nc);
      if (row < 0) return null;
      return {c: c, row: row, r0: (b.rLo + c * b.wm) / 1000, r1: (b.rLo + (c + 1) * b.wm) / 1000, s0: b.edge(row), s1: b.edge(row + 1), n: Number(b.counts[c + ',' + row] || 0)};
    }
    stats(); pill(); resize();
    // a click on a cell: its cards (as they are now: a card reviewed since moved to another one)
    plot._ddBrowse = function(){
      const x = cellOf(st.hover), b = st.bins; if (!x || !x.n) return null;
      const lastC = x.c === b.nc - 1, lastR = x.row === b.nr - 1;
      // (the points are rounded: the outer edges keep a margin, so the cards at the ends are not left out)
      return {query: ['is:review', '-is:learn',
        'prop:r>=' + Math.max(0, x.r0 - (x.c === 0 ? 0.0005 : 0)).toFixed(4), 'prop:r' + (lastC ? '<=' : '<') + (x.r1 + (lastC ? 0.0005 : 0)).toFixed(4),
        'prop:s>=' + Math.max(0, x.s0 - (x.row === 0 ? 0.05 : 0)).toFixed(3), 'prop:s' + (lastR ? '<=' : '<') + (x.s1 + (lastR ? 0.05 : 0)).toFixed(3)].join(' ')};
    };
    DD.hover.attach(plot, st, {
      index: function(mx, my){
        const geo = st.geo; if (!geo || !st.bins) return -1;
        const col = Math.floor((mx - geo.left) / geo.cw), row = Math.floor((my - geo.top) / geo.ch);
        return (mx >= geo.left && my >= geo.top && col >= 0 && col < geo.nc && row >= 0 && row < geo.nr) ? row * geo.nc + col : -1;
      },
      rows: function(i){
        const x = cellOf(i), b = st.bins; if (!x) return [];
        const pc = function(v){ return trim(v * 100, 1); };
        const rows = [{header: true, text: DD.t('{name}: {value}', {name: DD.t('Retrievability'), value: pc(x.r0) + '–' + pc(x.r1) + '%'})},
          {text: DD.t('{name}: {value}', {name: DD.t('Stability'), value: b.sText(x.s0) + ' – ' + b.sText(x.s1)})},
          {text: DD.tn('{n} card', '{n} cards', x.n, {n: fmt(x.n)})}];
        if (b.total > 0) rows.push({text: DD.t('{value}% of the cards', {value: trim(x.n * 100 / b.total, 1)})});
        return rows;
      },
      redraw: function(){ st.last = true; DD.frame.kick(); },
    });
    return Object.assign(gridLoop(st, el, plot, statEl, head, draw, resize, function(){ return ctx.animate && !st.shown ? DD.intro(500) : 300 * (st.k || 1); }), {
      update: function(data){
        // the same grid: each cell goes from its shade now to its new one; another grid (bins, rows, deck): the one
        // shown fades out as the new one fades in
        const from = {}, nb = sxrBins(data || {}), same = sxrSame(st.bins, nb) && st.prev === undefined;
        if (same) Object.keys((st.bins || {}).counts || {}).concat(Object.keys((nb || {}).counts || {})).forEach(function(k){ from[k] = share(k); });
        st.prev = undefined;
        if (st.bins && !same){ st.prev = st.bins; st.prevData = st.data; }
        st.from = from; st.shown = true; st.data = data || {}; st.bins = nb; st.t = DD._noAnim ? 1 : 0; st.start = null; st.k = DD.calm ? DD.calm() : 1;
        if (st.t >= 1) st.prev = undefined;
        stats(); pill(); st.last = true; DD.frame.kick();
      },
    });
  }
  DD.registerChart('sxr_heatmap', {mount: sxrMount});
  // B-W Matrix: the share of review answers passed minus the recall FSRS predicted, by the
  // card's stability (rows of 1.4 times) and difficulty (1 to 10) before the answer. Blue: remembered more than
  // predicted; red: less; a cell with fewer answers than the option's stays empty.
  const BW_MIN = [10, 20, 50, 100, 200], BW_FULL = 0.2;  // (a gap of 20 points: the full colour)
  // {cells 'row,d': [answers, passed, predicted sum], lo / hi: the rows shown, total, ok, pred, power, least}, or null
  function bwGrid(d){
    const p = (d && d.cells) || [];
    const cells = {}; let lo = Infinity, hi = -Infinity, total = 0, ok = 0, pred = 0;
    for (let i = 0; i + 4 < p.length; i += 5){
      const row = Number(p[i]), dd = Number(p[i + 1]), n = Number(p[i + 2]) || 0;
      if (n <= 0) continue;
      const c = [n, Number(p[i + 3]) || 0, (Number(p[i + 4]) || 0) / 100];
      cells[row + ',' + dd] = c; lo = Math.min(lo, row); hi = Math.max(hi, row);
      total += n; ok += c[1]; pred += c[2];
    }
    if (!total) return null;
    return {cells: cells, lo: lo, hi: hi, total: total, ok: ok, pred: pred, power: Number(d.power) || 1.4,
            least: BW_MIN.indexOf(Number(d.min_answers)) >= 0 ? Number(d.min_answers) : 50};
  }
  // a cell's gap (passed minus predicted, as a share), or null (no cell, or too few answers)
  function bwGap(b, key){
    const c = b && b.cells[key];
    return c && c[0] >= b.least ? (c[1] - c[2]) / c[0] : null;
  }
  function bwSame(a, b){ return !!(a && b && a.lo === b.lo && a.hi === b.hi); }
  function bwMount(el, ctx){
    el.innerHTML = '<div class="dd-plot"><canvas></canvas><div class="dd-tip"></div></div>';
    const plot = el.firstChild, canvas = plot.querySelector('canvas'), g = canvas.getContext('2d');
    const head = ctx.head, statEl = head && head.querySelector('.dd-stat');
    const st = {data: ctx.data || {}, opts: Object.assign({}, ctx.options || {}), from: {}, t: ctx.animate ? 0 : 1, start: null, hover: -1, geo: null, w: 1, h: 1, last: true};
    st.canvas = canvas; st.b = bwGrid(st.data);
    Object.defineProperty(st, 'colors', {get: function(){ return DD.theme.chart; }});
    Object.defineProperty(st, 'hoverIdx', {get: function(){ return st.hover; }, set: function(v){ st.hover = v; }});
    // a cell's gap now (from its old one while the chart changes)
    function gap(key){
      const nw = bwGap(st.b, key);
      if (st.t >= 1) return nw;
      const old = st.from[key];
      if (old == null || nw == null) return nw != null ? nw : old;
      return old + (nw - old) * st.t;
    }
    // its opacity: a cell coming (the intro: all of them) fades in, a cell going fades out
    function shown(key){
      if (st.t >= 1) return 1;
      const nw = bwGap(st.b, key), old = st.from[key];
      return old == null ? (nw == null ? 0 : st.t) : (nw == null ? 1 - st.t : 1);
    }
    function edge(k){ return Math.pow(st.b ? st.b.power : 1.4, k); }
    function pill(){
      const pills = head && head.querySelector('.dd-pills'); if (!pills || !DD.optionsPill) return;
      pills.innerHTML = '';
      DD.optionsPill(pills, 'bw_matrix', "This chart's options", [
        ['min_answers', 'Minimum Reviews per Cell', st.b ? st.b.least : (Number(st.data.min_answers) || 50), 50, BW_MIN.map(function(v){ return [v, String(v)]; })],
      ]);
    }
    function stats(){
      if (!statEl) return;
      const b = st.b;
      statEl.textContent = b ? DD.tn('{n} review', '{n} reviews', b.total, {n: fmt(b.total)})
        + '  ·  ' + DD.t('Predicted: {value}', {value: trim(b.pred * 100 / b.total, 1) + '%'})
        + '  ·  ' + DD.t('Actual: {value}', {value: trim(b.ok * 100 / b.total, 1) + '%'})
        + '  ·  ' + DD.t('Whole history') : '';
    }
    function resize(){ const f = DD.fitCanvas(canvas, g); st.w = f.w; st.h = f.h; }
    // (kept while the grid and the canvas's size stay: measuring the rows' labels every frame of an animation cost)
    let geoMemo = null;
    function geometry(b){
      if (geoMemo && geoMemo.b === b && geoMemo.w === st.w && geoMemo.h === st.h) return geoMemo.geo;
      const geo = geometry0(b);
      geoMemo = {b: b, w: st.w, h: st.h, geo: geo};
      return geo;
    }
    function geometry0(b){
      g.font = FONT;
      const nr = b ? b.hi - b.lo + 1 : 1;
      let lw = 0;
      if (b) for (let k = b.lo; k <= b.hi + 1; k++) lw = Math.max(lw, g.measureText(sxrDays(edge(k))).width);
      const left = 4 + 14 + Math.ceil(lw) + 6, bottom = 14 + 2 + 14, top = 6, right = 4;
      const w = Math.max(10, st.w - left - right), h = Math.max(10, st.h - top - bottom);
      return {left: left, top: top, cw: w / 10, ch: h / nr, nr: nr};
    }
    const sign = function(v, dec){ return (v > 0 ? '+' : v < 0 ? '−' : '') + trim(Math.abs(v) * 100, dec == null ? 1 : dec) + '%'; };
    // a cell's %, as large as the cell lets it be (11 px with a decimal, down to 8 px without): [text, font], or null
    // when even that does not fit. Its label is its gap to come, the same through an animation: kept per grid and cell
    // size (trying fonts on ~300 cells each frame took a whole frame: its row's intros played at 30 fps)
    const LABELS = [[11, 1], [11, 0], [10, 0], [9, 0], [8, 0]];
    const labelMemo = new WeakMap();  // grid -> {w, h, m: key -> label}
    let fontMoved = false;  // a label measured: the canvas's font is no longer the one layer() set
    function cellLabel0(v, w, h){
      fontMoved = true;
      for (let i = 0; i < LABELS.length; i++){
        const px = LABELS[i][0], t = sign(v, LABELS[i][1]);
        if (h < px + 2) continue;
        const font = FONT.replace('11px', px + 'px');
        g.font = font;
        if (g.measureText(t).width <= w - 4) return [t, font];
      }
      return null;
    }
    function cellLabel(b, key, v, w, h, fixed){
      if (!fixed) return cellLabel0(v, w, h);  // (a cell fading out: its value moves)
      let memo = labelMemo.get(b);
      if (!memo || memo.w !== w || memo.h !== h) labelMemo.set(b, memo = {w: w, h: h, m: {}});
      const m = memo.m;
      if (!(key in m)) m[key] = cellLabel0(v, w, h);
      return m[key];
    }
    function draw(){
      g.clearRect(0, 0, st.w, st.h);
      st.geo = geometry(st.b);
      if (st.prev !== undefined && st.t < 1){
        const e = crossEase(st.t), pb = st.prev, nb = st.b, one = function(){ return 1; };
        layer(pb, st.prevData, function(k){ return bwGap(pb, k); }, one, 1 - e, false);
        layer(nb, st.data, function(k){ return bwGap(nb, k); }, one, e, true);
      } else layer(st.b, st.data, gap, shown, 1, true);
    }
    // a grid (b, of its payload d) at an opacity; main: the one shown (its hovered cell outlined)
    function layer(b, d, gapOf, shownOf, alpha, main){
      if (!b || alpha <= 0) return;
      const C = DD.theme.chart, dark = !!C.is_dark, geo = geometry(b);
      g.globalAlpha = alpha;
      const more = d.more || C.easy || '#3b82f6', less = d.less || C.again || '#ef4444';
      const empty = dark ? 'rgba(255,255,255,0.055)' : 'rgba(0,0,0,0.047)';
      const sp = Math.min(2, Math.min(geo.cw, geo.ch) * 0.2), radius = Math.max(0.5, Math.min(geo.cw, geo.ch) * 0.18);
      const rr = function(x, y, w, h){ g.beginPath(); if (g.roundRect) g.roundRect(x, y, w, h, radius); else g.rect(x, y, w, h); };
      let font = null;
      for (let rowT = 0; rowT < geo.nr; rowT++){
        const row = b.hi - rowT;
        for (let c = 0; c < 10; c++){
          const x = geo.left + c * geo.cw + sp / 2, y = geo.top + rowT * geo.ch + sp / 2, w = Math.max(1, geo.cw - sp), h = Math.max(1, geo.ch - sp);
          rr(x, y, w, h); g.fillStyle = empty; g.fill();
          const key = row + ',' + (c + 1), v = gapOf(key), a = shownOf(key);
          if (v != null && a > 0){
            // (the colour by the size of the gap; a tiny one still shows the cell has its answers)
            rr(x, y, w, h); g.fillStyle = U.rgba(v >= 0 ? more : less, (0.08 + 0.82 * Math.min(1, Math.abs(v) / BW_FULL)) * a); g.fill();
            // its % (the gap it goes to: no digits rolling while it changes)
            const nv = bwGap(b, key), lab = cellLabel(b, key, nv != null ? nv : v, w, h, nv != null);
            if (fontMoved){ font = null; fontMoved = false; }
            if (lab){
              if (lab[1] !== font){ g.font = lab[1]; font = lab[1]; }
              g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillStyle = C.text_primary || '#222';
              g.globalAlpha = a * alpha; g.fillText(lab[0], x + w / 2, y + h / 2); g.globalAlpha = alpha;
            }
          }
          if (main && st.hover === rowT * 10 + c){ rr(x, y, w, h); g.strokeStyle = U.rgba(C.text_primary || '#ffffff', 200 / 255); g.lineWidth = 1.2; g.stroke(); }
        }
      }
      g.font = FONT; g.fillStyle = C.text_secondary || '#888';
      // the stability at the edges of the rows (one in so many when they are thin)
      g.textAlign = 'right'; g.textBaseline = 'middle';
      const everyR = Math.max(1, Math.ceil(14 / geo.ch));
      for (let k = 0; k <= geo.nr; k += everyR) g.fillText(sxrDays(edge(b.lo + k)), geo.left - 6, Math.max(geo.top + 5, Math.min(geo.top + geo.nr * geo.ch - 5, geo.top + (geo.nr - k) * geo.ch)));
      // the difficulty of each column
      g.textAlign = 'center'; g.textBaseline = 'top';
      for (let c = 0; c < 10; c++) g.fillText(String(c + 1), geo.left + (c + 0.5) * geo.cw, geo.top + geo.nr * geo.ch + 2);
      g.fillText(DD.t('Difficulty'), geo.left + 5 * geo.cw, geo.top + geo.nr * geo.ch + 16);
      g.save(); g.translate(4, geo.top + geo.nr * geo.ch / 2); g.rotate(-Math.PI / 2); g.textBaseline = 'top';
      g.fillText(DD.t('Stability'), 0, 0); g.restore();
      g.globalAlpha = 1;
    }
    stats(); pill(); resize();
    DD.hover.attach(plot, st, {
      index: function(mx, my){
        const geo = st.geo; if (!geo || !st.b) return -1;
        const col = Math.floor((mx - geo.left) / geo.cw), row = Math.floor((my - geo.top) / geo.ch);
        return (mx >= geo.left && my >= geo.top && col >= 0 && col < 10 && row >= 0 && row < geo.nr) ? row * 10 + col : -1;
      },
      rows: function(i){
        const b = st.b; if (!b || i < 0) return [];
        const row = b.hi - Math.floor(i / 10), d = i % 10 + 1, c = b.cells[row + ',' + d];
        const rows = [{header: true, text: DD.t('{name}: {value}', {name: DD.t('Stability'), value: sxrDays(edge(row)) + ' – ' + sxrDays(edge(row + 1))})},
          {text: DD.t('{name}: {value}', {name: DD.t('Difficulty'), value: String(d)})}];
        if (!c) return rows;
        rows.push({text: DD.t('Predicted: {value}', {value: trim(c[2] * 100 / c[0], 1) + '%'})},
          {text: DD.t('Actual: {value}', {value: trim(c[1] * 100 / c[0], 1) + '%'})},
          {text: DD.tn('{n} review', '{n} reviews', c[0], {n: fmt(c[0])})});
        const v = bwGap(b, row + ',' + d);
        rows.push({text: v != null ? DD.t('Difference: {value}', {value: sign(v)}) : DD.t('Too few reviews')});
        return rows;
      },
      redraw: function(){ st.last = true; DD.frame.kick(); },
    });
    return Object.assign(gridLoop(st, el, plot, statEl, head, draw, resize, function(){ return ctx.animate && !st.shown ? DD.intro(500) : 300 * (st.k || 1); }), {
      update: function(data){
        // the same rows: the cells move from their gaps now to the new ones; other rows (another deck): the grid
        // shown fades out as the new one fades in
        const from = {}, nb = bwGrid(data || {}), same = bwSame(st.b, nb) && st.prev === undefined;
        if (same) Object.keys((st.b || {}).cells || {}).concat(Object.keys((nb || {}).cells || {})).forEach(function(k){ from[k] = gap(k); });
        st.prev = undefined;
        if (st.b && !same){ st.prev = st.b; st.prevData = st.data; }
        st.from = from; st.shown = true; st.data = data || {}; st.b = nb; st.t = DD._noAnim ? 1 : 0; st.start = null; st.k = DD.calm ? DD.calm() : 1;
        if (st.t >= 1) st.prev = undefined;
        stats(); pill(); st.last = true; DD.frame.kick();
      },
    });
  }
  DD.registerChart('bw_matrix', {mount: bwMount});
  // Custom Pie / Custom Bar: the user's own searches (logic.metrics.custom_search), edited in
  // a dialog from the chart's options icon (DD.editSearches), saved in the chart's "searches" setting
  function editSearches(section, rows){
    if (!DD.editSearches) return;
    DD.editSearches({rows: rows || []}).then(function(r){ if (r) DD.setWidgetSetting(section, 'searches', r); });
  }
  // a search's name: its text (the user's own: not translated), and when Anki cannot read it, that
  function searchName(s){ return (s.q || '*') + (s.bad ? '  (' + DD.t('Invalid search') + ')' : ''); }
  // a chart's searches (their text and colour), to tell a change of them from new data
  function searchesKey(d){ return JSON.stringify((d && d.searches) || []); }
  // the Searches pill of the header (as Pie / Bars: folded into the pills' menu when the header is narrow)
  function searchesPill(pills, open){
    const b = document.createElement('button');
    b.className = 'dd-pill';
    b.textContent = 'Searches';
    b.title = 'Edit Searches...';
    b.addEventListener('click', function(e){ e.stopPropagation(); open(); });
    pills.appendChild(b);
  }
  const CP_MEASURES = [['cards', 'Cards'], ['load', 'Load'], ['lapses', 'Lapses'], ['reviews', 'Reviews']];
  // the donut's payload (charts/pie.js DD.pieMount): a slice per search, its cards' value
  function customPiePayload(d){
    const order = [], labels = {}, colors = {}, counts = {}, ms = d.measure || 'cards';
    (d.slices || []).forEach(function(s, i){
      const k = 's' + i;
      order.push(k); labels[k] = searchName(s); colors[k] = s.color; counts[k] = Math.max(0, Number(s.value) || 0);
    });
    const load = ms === 'load';
    return {counts: counts, order: order, labels: labels, colors: colors, legend_pct: true, show_legend: true,
      center_word: DD.t(load ? 'rev/day' : ms === 'lapses' ? 'lapses' : ms === 'reviews' ? 'reviews' : 'cards'),
      fmt: load ? function(v){ return U.trimNum(v, v < 10 ? 1 : 0); } : null,
      // a click on a slice: its search in the browser
      browse: function(k){ const s = (d.slices || [])[Number(String(k).slice(1))]; return s && !s.bad ? {query: s.q || ''} : null; }};
  }
  function customPieMount(el, ctx){
    const head = ctx.head;
    let data = ctx.data || {};
    const inst = DD.pieMount(el, {data: customPiePayload(data), animate: ctx.animate, options: ctx.options || {}});
    function pill(){
      const pills = head && head.querySelector('.dd-pills'); if (!pills || !DD.optionsPill) return;
      pills.innerHTML = '';
      searchesPill(pills, function(){ editSearches('custom_pie', data.searches); });
      DD.optionsPill(pills, 'custom_pie', "This chart's options", [
        ['searches', 'Edit Searches...', undefined, undefined, 'action', function(){ editSearches('custom_pie', data.searches); }, 'search'],
        ['measure', 'Value', data.measure || 'cards', 'cards', CP_MEASURES],
      ]);
    }
    pill();
    return {
      update: function(d, hint){
        // other searches (other slices): the old pie fades out over the new
        const other = searchesKey(data) !== searchesKey(d);
        data = d || {};
        if (other) DD.applyUpdate(el, function(){ inst.update(customPiePayload(data), hint); }, true); else inst.update(customPiePayload(data), hint);
        pill();
      },
      setOptions: function(o){ inst.setOptions(o); },
      setTheme: function(){ inst.setTheme(); },
      destroy: function(){ inst.destroy(); const p = head && head.querySelector('.dd-pills'); if (p) p.innerHTML = ''; },
    };
  }
  DD.registerChart('custom_pie', {mount: customPieMount});
  // Custom Bar: its options icon (the stacked bars of days: registerDaily)
  // (data(): its data of now: the searches saved last)
  function customBarPill(pillsEl, data){
    if (!DD.optionsPill) return;
    searchesPill(pillsEl, function(){ editSearches('custom_bar', data().searches); });
    DD.optionsPill(pillsEl, 'custom_bar', "This chart's options", [
      ['searches', 'Edit Searches...', undefined, undefined, 'action', function(){ editSearches('custom_bar', data().searches); }, 'search'],
      ['measure', 'Value', data().measure === 'time' ? 'time' : 'count', 'count', [['count', 'Reviews'], ['time', 'Time']]],
    ]);
  }
})();
