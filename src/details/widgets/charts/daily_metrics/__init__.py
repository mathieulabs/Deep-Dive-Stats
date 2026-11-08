# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Charts read from the review history of each day (the history cache already holds it):
the answer buttons over time, the time per review, the cards forgotten.

Each one is a stacked bar chart of the days (ActivityStackedChart) fed with the daily rows
of the cache. CHARTS describes them: the pinned widgets, the Deep Dive sections and the
widget gallery all read it."""

from ..activity_stacked import ActivityStackedChart
from ...chart_utils.formatting import fmt_num, fmt_num_trim_zeros
from .....i18n import N_, tr, tr_n, tr_name


class DailyMetric:
    """One chart: its widget type, name, group in the gallery, and how its bars are made.

    series(cfg): [{"key", "label", "color", "color_key"}] (color_key: the Settings > Colors
    color, read again for the chart's place and own colors, see refresh_data_colors). rows(day rows, oldest first): the rows the
    chart draws (one dict per day with pretty_date and a value per series key).
    unit: "reviews" (counts of reviews), "lapses" (counts of lapses), "cards" or "seconds" (an
    average: bins are weighted by their reviews, no running total).
    cumulative: whether its running total means something (offered in its menu).
    percent: whether "Show as %" means something (several series that add up).
    source(cfg, deck_id, is_deleted): data read for the deck besides the day rows (then
    rows(days, data)), for charts not in the history cache.
    alt: (box label, series(cfg)): a second split of the same bars, chosen by a header box
    (the rows carry the keys of both)."""

    def __init__(self, widget_type, label, group, series, rows, unit="reviews", cumulative=False, percent=False,
                 source=None, alt=None, average=True, by_day=True, share_stats=False):
        self.widget_type = widget_type
        self.average = average  # its average line means something (offered in its menu)
        self.by_day = by_day  # bars of days (False: of seconds, intervals...: not zoomed with the days)
        self.share_stats = share_stats  # header stats: the share of each part
        self.percent = percent
        self.source = source
        self.alt = alt
        self.cumulative = cumulative
        self.label = label
        self.group = group
        self.series = series
        self.rows = rows
        self.unit = unit


def _color(cfg, key):
    """A first value; the chart reads it again for its own place (refresh_data_colors)."""
    from ....ui import get_color

    return get_color(cfg.config, key, "details")


def _ratings_series(cfg):
    from ....ui import Config

    return [
        {"key": "again", "label": tr("Again"), "color": _color(cfg, Config.COLOR_AGAIN), "color_key": Config.COLOR_AGAIN},
        {"key": "hard", "label": tr("Hard"), "color": _color(cfg, Config.COLOR_HARD), "color_key": Config.COLOR_HARD},
        {"key": "good", "label": tr("Good"), "color": _color(cfg, Config.COLOR_GOOD), "color_key": Config.COLOR_GOOD},
        {"key": "easy", "label": tr("Easy"), "color": _color(cfg, Config.COLOR_EASY), "color_key": Config.COLOR_EASY},
    ]


def _buttons(d, kind):
    """The 4 button counts of one card kind ("learning", "young", "mature") in a row. The
    rows of the cache carry them as lists and as fields; the rows read straight from the
    revlog (Today, Yesterday: by 10 minutes) only as lists."""
    values = d.get(f"{kind}_buttons")
    if isinstance(values, (list, tuple)) and len(values) >= 4:
        return [int(v or 0) for v in values[:4]]
    prefix = "learn" if kind == "learning" else kind
    return [int(d.get(f"{prefix}_btn{i}", 0) or 0) for i in range(1, 5)]


def _ratings_rows(days):
    out = []
    for d in days:
        if "again" in d:
            counts = [int(d.get(k, 0) or 0) for k in ("again", "hard", "good", "easy")]
        else:
            counts = [sum(b) for b in zip(*(_buttons(d, k) for k in ("learning", "young", "mature")))]
        out.append({"pretty_date": d.get("pretty_date", ""),
                    **dict(zip(("again", "hard", "good", "easy"), counts))})
    return out


def _forgotten_series(cfg):
    from ....ui import Config

    return [
        {"key": "mature", "label": tr("Mature"), "color": _color(cfg, Config.COLOR_MATURE), "color_key": Config.COLOR_MATURE},
        {"key": "young", "label": tr("Young"), "color": _color(cfg, Config.COLOR_YOUNG), "color_key": Config.COLOR_YOUNG},
    ]


def _forgotten_rows(days):
    # Again on a review card (not a card still in learning): the card was forgotten.
    return [{"pretty_date": d.get("pretty_date", ""),
             "young": _buttons(d, "young")[0],
             "mature": _buttons(d, "mature")[0]} for d in days]


def _speed_series(cfg):
    from ....ui import Config

    return [{"key": "seconds", "label": tr("Seconds per review"), "color": _color(cfg, Config.COLOR_BAR), "color_key": Config.COLOR_BAR}]


def _speed_rows(days):
    out = []
    for d in days:
        reviews = int(d.get("reviews", 0) or 0)
        ms = float(d.get("time_ms", 0) or 0)
        out.append({"pretty_date": d.get("pretty_date", ""),
                    "seconds": (ms / 1000.0 / reviews) if reviews else 0.0,
                    "_reviews": reviews, "_ms": ms})
    return out


def _introduced_series(cfg):
    from ....ui import Config

    return [
        {"key": "new", "label": tr("Introduced"), "color": _color(cfg, Config.COLOR_LEARN), "color_key": Config.COLOR_LEARN},
        {"key": "reintro", "label": tr("Re-introduced"), "color": _color(cfg, Config.COLOR_RELEARN), "color_key": Config.COLOR_RELEARN},
    ]


def _introduced_source(cfg, deck_id, is_deleted):
    from ....logic.metrics.introduced import introduction_events

    return introduction_events(cfg, deck_id, is_deleted)


def _introduced_rows(days, events):
    """The cards introduced in each row (a day, or a bin of minutes for Today / Yesterday):
    new / re-introduced, and their first rating (again ... easy)."""
    import bisect
    from datetime import datetime, timedelta

    from ....logic import rollover_hour

    out = [{"pretty_date": d.get("pretty_date", ""), "new": 0, "reintro": 0,
            "again": 0, "hard": 0, "good": 0, "easy": 0, "reviews": 0} for d in days]
    if not days or not events:
        return out
    dates = [str(d.get("date", "") or "") for d in days]
    by_minute = any(len(x) > 10 for x in dates)
    if by_minute:
        starts = [datetime.strptime(x[:16], "%Y-%m-%d %H:%M") for x in dates]
        step = (starts[1] - starts[0]) if len(starts) > 1 else timedelta(minutes=10)
        end = starts[-1] + step
    else:
        index = {x[:10]: i for i, x in enumerate(dates)}
        roll = timedelta(hours=int(rollover_hour() or 0))
    keys = ("again", "hard", "good", "easy")
    for rid, ease, reintro in events:
        dt = datetime.fromtimestamp(rid / 1000.0)
        if by_minute:
            if dt < starts[0] or dt >= end:
                continue
            i = bisect.bisect_right(starts, dt) - 1
        else:
            i = index.get((dt - roll).strftime("%Y-%m-%d"))
            if i is None:
                continue
        row = out[i]
        row["reintro" if reintro else "new"] += 1
        if 1 <= ease <= 4:
            row[keys[ease - 1]] += 1
        row["reviews"] += 1  # (a row with cards: kept by "show empty" checks)
    return out


def _types_series(cfg):
    from ....ui import Config

    return [
        {"key": "learn", "label": tr("Learning"), "color": _color(cfg, Config.COLOR_LEARN), "color_key": Config.COLOR_LEARN},
        {"key": "young", "label": tr("Young"), "color": _color(cfg, Config.COLOR_YOUNG), "color_key": Config.COLOR_YOUNG},
        {"key": "mature", "label": tr("Mature"), "color": _color(cfg, Config.COLOR_MATURE), "color_key": Config.COLOR_MATURE},
    ]


def _limit_source(cfg, deck_id, is_deleted):
    from ....logic.metrics.review_buckets import did_limit

    return did_limit(cfg, deck_id, is_deleted)


_RATING_KEYS = ("again", "hard", "good", "easy")


def _answer_time_rows(days, limit):
    """One bar per second spent on the answer (the last one: a minute or more), the reviews
    by rating and by card type, in the period of the day rows."""
    from ....logic.metrics.review_buckets import MAX_SECONDS, answer_time_counts, range_from_days

    rng = range_from_days(days)
    counts = answer_time_counts(limit, *rng) if (rng and limit is not None) else {}
    top = max([s for (s, _e, _k) in counts] + [9])
    rows = [{"pretty_date": tr("{value}s", value=s) + ("+" if s == MAX_SECONDS else ""),
             "again": 0, "hard": 0, "good": 0, "easy": 0, "learn": 0, "young": 0, "mature": 0, "reviews": 0}
            for s in range(0, top + 1)]
    for (s, ease, kind), n in counts.items():
        row = rows[s]
        row[_RATING_KEYS[ease - 1]] += n
        row[("learn", "young", "mature")[kind]] += n
        row["reviews"] += n
    return rows


def _interval_rows(days, limit):
    """One bar per interval in days before the answer, the reviews by rating."""
    from ....logic.metrics.review_buckets import interval_rating_counts, range_from_days

    rng = range_from_days(days)
    counts = interval_rating_counts(limit, *rng) if (rng and limit is not None) else {}
    top = max([i for (i, _e) in counts] + [7])
    rows = [{"pretty_date": tr("{value} d", value=i), "again": 0, "hard": 0, "good": 0, "easy": 0, "reviews": 0}
            for i in range(1, top + 1)]
    for (i, ease), n in counts.items():
        row = rows[i - 1]
        row[_RATING_KEYS[ease - 1]] += n
        row["reviews"] += n
    return rows


def _card_total_series(cfg):
    from ....ui import Config

    return [{"key": "total", "label": tr("Cards"), "color": _color(cfg, Config.COLOR_BAR), "color_key": Config.COLOR_BAR}]


def _card_states_series(cfg):
    from ....ui import Config

    parts = (("mature", N_("Mature"), Config.COLOR_MATURE), ("young", N_("Young"), Config.COLOR_YOUNG),
             ("relearn", N_("Relearning"), Config.COLOR_RELEARN), ("learn", N_("Learning"), Config.COLOR_LEARN),
             ("new", N_("New"), Config.COLOR_NEW))
    return [{"key": k, "label": tr_name(label), "color": _color(cfg, c), "color_key": c} for k, label, c in parts]


def _card_states_source(cfg, deck_id, is_deleted):
    from ....logic.metrics.card_states import timeline

    return timeline(cfg, deck_id, is_deleted)


def _card_states_rows(days, data):
    """Each day: how many cards were new / learning / relearning / young / mature at its end."""
    from datetime import date

    from ....logic.metrics.card_states import KEYS

    out = []
    for d in days:
        counts = (0, 0, 0, 0, 0)
        ordinal = None
        try:
            ordinal = date.fromisoformat(str(d.get("logical_date") or d.get("date") or "")[:10]).toordinal()
        except ValueError:
            pass
        if data is not None and ordinal is not None:
            counts = data.at(ordinal)
        row = {"pretty_date": d.get("pretty_date", ""), "_day": ordinal}
        row.update({k: int(v) for k, v in zip(KEYS, counts)})
        row["total"] = int(sum(counts))
        out.append(row)
    return out


CHARTS = (
    DailyMetric("ratings", N_("Ratings"), N_("Ratings and time"),
                _ratings_series, _ratings_rows, percent=True),
    DailyMetric("review_speed", N_("Review Speed"), N_("Ratings and time"),
                _speed_series, _speed_rows, unit="seconds"),
    DailyMetric("forgotten", N_("Forgotten"), N_("Ratings and time"),
                _forgotten_series, _forgotten_rows, unit="lapses", cumulative=True, percent=True),
    # Introduced cards (new cards studied) per day; "By First Rating": the same cards by the
    # answer given the first time (Search Stats Extended's Introductory Rating).
    DailyMetric("introduced", N_("Introduced"), N_("Ratings and time"),
                _introduced_series, _introduced_rows, unit="cards", cumulative=True, percent=True,
                source=_introduced_source, alt=(N_("By First Rating"), _ratings_series)),
    # The reviews of the period by the time spent on the answer, by rating ("By Card Type": by
    # learning / young / mature); "Show as %": how the answers go with the time taken.
    DailyMetric("answer_time", N_("Answer Time"), N_("Ratings and time"),
                _ratings_series, _answer_time_rows, percent=True, source=_limit_source,
                alt=(N_("By Card Type"), _types_series), average=False, by_day=False, share_stats=True),
    # The reviews of the period by the card's interval before the answer, by rating; with
    # "Show as %" the share of Again at each interval.
    DailyMetric("interval_ratings", N_("Rating by Interval"), N_("Ratings and time"),
                _ratings_series, _interval_rows, percent=True, source=_limit_source,
                average=False, by_day=False, share_stats=True),
    # How many cards were new / learning / relearning / young / mature on each past day (a
    # state at the end of the day, not a count of the day: bins show their last day).
    DailyMetric("card_states", N_("Card Counts over Time"), N_("Card history"),
                _card_total_series, _card_states_rows, unit="level", percent=True,
                source=_card_states_source, average=False,
                alt=(N_("Breakdown by Type"), _card_states_series)),
)
BY_TYPE = {m.widget_type: m for m in CHARTS}
# What their right-click menus offer (all of them: average line, adaptive binning, stats).
TYPES = tuple(BY_TYPE)
CUMULATIVE_TYPES = tuple(m.widget_type for m in CHARTS if m.cumulative)


def is_daily_metric(widget_type):
    return widget_type in BY_TYPE


class DailyMetricChart(ActivityStackedChart):
    """A stacked chart of the days for one DailyMetric."""

    # One colour (no breakdown): shaded by height like Added and the plain Activity bars.
    # A breakdown keeps its flat colours, as Activity by type.
    @property
    def _intensity_by_value_coloring(self):
        return len(getattr(self, "series_config", None) or []) == 1

    @_intensity_by_value_coloring.setter
    def _intensity_by_value_coloring(self, _value):
        pass

    def __init__(self, metric, days, cfg, parent=None, adaptive_binning=True, owner=None, source=None, alt=False):
        self.metric = metric
        self._cfg = cfg
        self._source_args = source  # (deck_id, is_deleted) for metric.source
        self._alt = bool(alt and metric.alt)
        self._hidden_series = set()
        series = metric.alt[1](cfg) if self._alt else metric.series(cfg)
        first = metric.rows(days or [], None) if metric.source is not None else metric.rows(days or [])
        super().__init__(first, series, parent=parent, adaptive_binning=adaptive_binning)
        self._rows_cache = {}
        self._pending_key = None
        self._last_rows = None
        if metric.source is not None:
            self.rows_for(days)  # read in the background, drawn when ready
        self._chart_owner = owner
        self.refresh_data_colors()
        if not metric.by_day:
            self._zoom_linked = False  # seconds or intervals: not zoomed along with the charts of days
            self._zoom_never = True  # no dates on its axis: no "linked zoom" entry in its menu
        # Read by the zoom animation (chart_utils.zoom_camera): no rescaling by bin size.
        self._bins_are_averages = metric.unit in ("seconds", "level")
        # Period changes animate as on Activity's breakdown (relative heights, a steady slide).
        # (Card Counts over Time: only for another period, see update_data.)
        self._relative_height_transition = True

    # The tooltip's running total only where it means something (a sum of averages would not).
    @property
    def tooltip_hidden(self):
        hidden = list(getattr(self, "_tooltip_hidden", None) or [])
        if not self.metric.cumulative:
            hidden.append("total")
        return hidden

    @tooltip_hidden.setter
    def tooltip_hidden(self, value):
        self._tooltip_hidden = list(value or [])

    def refresh_data_colors(self):
        """Each series' color again: the widget's own color, else the shared one of its place
        (the pinned theme on the main screen, the Deep Dive one there)."""
        from ....ui import get_chart_color
        from .....const.theme.color_resolver import own_color_for

        context = "pinned" if getattr(self, "_chart_owner", None) == "pinned" else "details"
        for sc in getattr(self, "series_config", None) or []:
            key = sc.get("color_key")
            if key:
                sc["color"] = own_color_for(self, key) or get_chart_color(key, context)
        self.update()

    def apply_options(self, show_average=True, avg_on_active_days=True, show_cumulative=True):
        """The menu options; a running total only where it means something (cumulative)."""
        # (No average line where it means nothing: not offered in the menu, so never shown.)
        self.set_average_mode(bool(show_average) and self.metric.average, bool(avg_on_active_days))
        self.set_cumulative_mode(bool(show_cumulative) and self.metric.cumulative)

    def set_source(self, deck_id=None, is_deleted=False):
        """The deck metric.source reads (charts not in the history cache)."""
        self._source_args = (deck_id, bool(is_deleted))

    def rows_for(self, days):
        """The rows of these days. Charts read outside the history cache (metric.source) read
        in the background: the rows shown so far stay until the new ones are ready (then
        drawn with a transition), so a deck or period change never waits on a query."""
        days = days or []
        if self.metric.source is None:
            return self.metric.rows(days)
        key = self._rows_key(days)
        hit = self._rows_cache.get(key)
        if hit is not None:
            self._last_rows = hit
            return hit
        self._request(days, key, apply=True)
        if self._last_rows is not None:
            return self._last_rows
        return self.metric.rows(days, None)

    def _rows_key(self, days):
        from aqt import mw

        try:
            stamp = mw.col.db.scalar("SELECT max(id) FROM revlog")
        except Exception:
            stamp = None
        dates = [str(d.get("date", "")) for d in days]
        span = (dates[0], dates[-1], len(dates)) if dates else ()
        return (getattr(self, "_source_args", None), span, stamp)

    def prefetch(self, days):
        """Read the rows of these days now, without drawing them: True when they are there
        already. Deep Dive reads them before its refresh, so these charts animate in their
        turn with the others instead of all at once when their data comes."""
        if self.metric.source is None:
            return True
        days = days or []
        key = self._rows_key(days)
        if key in self._rows_cache:
            return True
        self._request(days, key, apply=False)
        return False

    def is_ready(self, days):
        return self.metric.source is None or self._rows_key(days or []) in self._rows_cache

    def _request(self, days, key, apply=True):
        if self._pending_key == key:
            if apply:
                self._pending_apply = True  # asked to be drawn now: drawn when it comes
            return
        self._pending_key = key
        self._pending_apply = bool(apply)
        metric, cfg = self.metric, self._cfg
        deck_id, deleted = getattr(self, "_source_args", None) or (None, False)
        days = list(days)

        def work():
            return metric.rows(days, metric.source(cfg, deck_id, deleted))

        def done(fut):
            try:
                rows = fut.result()
            except Exception:
                from ....logic.logger import log_swallowed

                log_swallowed()
                return
            try:
                if len(self._rows_cache) > 6:
                    self._rows_cache.clear()
                self._rows_cache[key] = rows
                if self._pending_key != key:
                    return  # another deck or period asked since: its own result will come
                self._pending_key = None
                if not getattr(self, "_pending_apply", True):
                    return  # read ahead: the refresh draws it (in the cache now)
                first = self._last_rows is None
                self._last_rows = rows
                mode, self._pending_mode = getattr(self, "_pending_mode", None), None
                from ..common.background_reads import when_quiet

                def apply_late(rows=rows, mode=mode, first=first):
                    # Its own small batch: outside a refresh's batch, a chart only animates
                    # when few charts are on screen, so data coming late was drawn at once.
                    # when_quiet keeps the number of animations at once within the limit.
                    
                    with self._own_batch():
                        self.update_data(rows, transition_mode=mode)
                    if first:
                        self._intro_pending = True
                        self._play_intro_if_due()
                    from ...common import refresh_parent_chart_header_stats

                    refresh_parent_chart_header_stats(self)

                when_quiet(self, apply_late)
            except RuntimeError:
                pass  # the chart was closed meanwhile

        from ..common import background_reads

        background_reads.run(id(self), work, done, wait=bool(apply))

    def series_choices(self):
        """[(key, label)] of the parts of the current view (the "Series" menu)."""
        full = self.metric.alt[1](self._cfg) if self._alt else self.metric.series(self._cfg)
        return [(s["key"], s["label"]) for s in full]

    def _shown_series(self):
        full = self.metric.alt[1](self._cfg) if self._alt else self.metric.series(self._cfg)
        shown = [s for s in full if s["key"] not in self._hidden_series]
        return shown or full

    def set_hidden_series(self, keys):
        """Hide parts of the bars (right click > Series): gone from the bars, tooltip, stats,
        total and the shares of "Show as %"."""
        keys = set(keys or [])
        if keys == self._hidden_series:
            return
        self._hidden_series = keys
        self.series_config = self._shown_series()
        self.refresh_data_colors()
        self._invalidate_data_caches()
        self._chrome_cache_key = None
        self._scaffold_cache_key = None
        self.update()

    def _own_batch(self):
        """Lets this one chart animate outside a refresh's batch (its data came late) without
        the forced repaints of a local batch: those, during the main screen's fade-in right
        after Anki opens, flashed the window black."""
        from ....animations.chart_policy import chart_animation_batch

        return chart_animation_batch(self, [self], threshold=1, force_repaint_candidates=False)

    def _play_intro_if_due(self):
        """The first data of a chart that reads it in the background came after the chart
        appeared (Anki just opened, Deep Dive just built): its intro played while it was still
        empty, so its bars rise now, as the other charts' did when they appeared. Shown
        later: when it shows (showEvent)."""

        if not getattr(self, "_intro_pending", False) or not self.isVisible():
            return
        if not self._has_meaningful_data_for_animation():
            return
        self._intro_pending = False
        
        if getattr(self, "_data_transition_active", False):
            return  # already moving from the empty bars to these
        with self._own_batch():
            self._initial_animation_done = True
            self.replay_animation()

    def showEvent(self, event):
        moving = bool(getattr(self, "_data_transition_active", False)) and float(getattr(self, "_progress", 1.0)) < 1.0
        super().showEvent(event)
        if moving and getattr(self, "_data_transition_active", False) and float(getattr(self, "_progress", 1.0)) >= 1.0:
            # Shown again while its bars were still moving (the main screen fades in the
            # widgets that were loading, right after Anki opens): the show cut it short (too
            # many charts on screen for a new one); it plays again, now that it is seen.
            
            with self._own_batch():
                self.replay_animation()

        if getattr(self, "_intro_pending", False):
            from aqt.qt import QTimer

            from ..common.background_reads import when_quiet

            # After the charts appearing with it have started theirs, within the limit.
            QTimer.singleShot(0, lambda: when_quiet(self, self._play_intro_if_due))

    def set_percent_mode(self, enabled):
        """Show as %; Card Counts over Time only when split by type (one part is 100%)."""
        self._percent_wanted = bool(enabled)
        if self.metric.widget_type == "card_states" and not self._alt:
            enabled = False
        super().set_percent_mode(enabled)

    def set_alt(self, on):
        """The header box: the bars split the other way (metric.alt), animated."""
        on = bool(on and self.metric.alt)
        if on == self._alt:
            return
        self._alt = on
        if getattr(self, "_percent_wanted", None) is not None:
            self.set_percent_mode(self._percent_wanted)
        self.series_config = self._shown_series()
        self.refresh_data_colors()
        self._invalidate_data_caches()
        self._chrome_cache_key = None
        self._scaffold_cache_key = None
        self.update()

    def set_days(self, days, adaptive_binning=None, transition_mode=None):
        rows = self.rows_for(days)
        if self.metric.source is not None and not self.is_ready(days):
            # Still reading: drawn when the rows come, with this same transition (another
            # period slides as on every chart), not twice (old rows now, a plain morph later).
            self._pending_mode = transition_mode
            if adaptive_binning is not None:
                self.adaptive_binning = adaptive_binning
            # Its turn in the refresh's waves (the main screen's batch): it animates in that
            # turn once its rows come, instead of all such charts at once whenever they come.
            try:
                from ....animations.chart_policy import chart_animation_queue_plan

                self._deferred_queue_plan = chart_animation_queue_plan(self)
            except Exception:
                self._deferred_queue_plan = None
            return
        self._pending_mode = None
        self.update_data(rows, adaptive_binning=adaptive_binning, transition_mode=transition_mode)

    def update_data(self, new_data, adaptive_binning=None, transition_mode=None, transition_align_right=None):
        if self.metric.unit == "level":
            # A state on each day: another period slides exactly as on Activity and the other
            # charts of days (relative heights); another deck grows or shrinks the bars on one
            # axis (relative heights would barely move: its bars are all near the top of their
            # own scale).
            self._relative_height_transition = transition_mode == "timespan"
        # New data resets the chart's zoom (init_zoom): not a zoom of the user's, the linked
        # zoom must not pass it on (Deep Dive's runtime.zoom_sync checks this flag).
        self._applying_data = True
        try:
            return super().update_data(new_data, adaptive_binning=adaptive_binning, transition_mode=transition_mode,
                                       transition_align_right=transition_align_right)
        finally:
            self._applying_data = False

    def _compute_display_data(self, source_data):
        if self.metric.unit == "level":
            return self._level_bins(source_data)
        if self.metric.unit != "seconds":
            return super()._compute_display_data(source_data)
        # Seconds per review in a bin of days: the bin's time over its reviews (an average
        # of the days' averages would count a day of 3 reviews like a day of 300).
        source_data = source_data or []
        if not self.binning_active:
            return source_data
        from ...chart_utils.binning import get_bin_size

        bs = getattr(self, "_forced_bin_step", None) or get_bin_size(len(source_data))
        if bs <= 1:
            return source_data
        out = []
        for i in range(0, len(source_data), bs):
            chunk = source_data[i:i + bs]
            reviews = sum(int(r.get("_reviews", 0) or 0) for r in chunk)
            ms = sum(float(r.get("_ms", 0) or 0) for r in chunk)
            first, last = chunk[0].get("pretty_date", ""), chunk[-1].get("pretty_date", "")
            out.append({
                "pretty_date": f"{first} - {last}" if first and last and first != last else (first or ""),
                "seconds": (ms / 1000.0 / reviews) if reviews else 0.0,
                "_reviews": reviews, "_ms": ms,
            })
        return out

    def _level_bins(self, source_data):
        """A state on each day (counts of cards): a bin of days shows its last day, the state
        at its end (a sum of the days would count each card once per day)."""
        source_data = source_data or []
        if not self.binning_active:
            return source_data
        from ...chart_utils.binning import get_bin_size

        bs = getattr(self, "_forced_bin_step", None) or get_bin_size(len(source_data))
        if bs <= 1:
            return source_data
        out = []
        for i in range(0, len(source_data), bs):
            chunk = source_data[i:i + bs]
            # The empty days a deck change in Total lays around the data (marked _pad) are
            # not days of the deck: a bin ending on them shows its last real day.
            real = [r for r in chunk if not r.get("_pad")] or chunk
            row = dict(real[-1])
            first, last = real[0].get("pretty_date", ""), real[-1].get("pretty_date", "")
            row["pretty_date"] = f"{first} - {last}" if first and last and first != last else (first or "")
            out.append(row)
        return out

    def _format_metric_value(self, value, with_unit=True, per_day=False, axis=False, compact=True, raw=False):
        if self.percent_mode and not raw:
            return super()._format_metric_value(value, axis=axis)
        unit = self.metric.unit
        if unit == "seconds":
            v = float(value or 0.0)
            text = fmt_num_trim_zeros(v, 0 if (axis or v >= 10) else 1)
            return tr("{value}s", value=text) if (with_unit or axis) else text
        if unit in ("cards", "level") and with_unit and not axis:
            v = float(value or 0.0)
            n = int(round(v))
            out = tr_n("{count} card", "{count} cards", n,
                       count=fmt_num(n) if abs(v - n) < 1e-9 else fmt_num_trim_zeros(v, 1))
            return tr("{value}/day", value=out) if per_day else out
        if unit == "lapses" and with_unit and not axis:
            v = float(value or 0.0)
            n = int(round(v))
            out = tr_n("{count} lapse", "{count} lapses", n,
                       count=fmt_num(n) if abs(v - n) < 1e-9 else fmt_num_trim_zeros(v, 1))
            return tr("{value}/day", value=out) if per_day else out
        return super()._format_metric_value(value, with_unit=with_unit, per_day=per_day, axis=axis,
                                            compact=compact, raw=raw)

    def _is_time_mode(self):
        # The axis labels go through _format_metric_value (seconds) as in time mode.
        return self.metric.unit == "seconds" or super()._is_time_mode()

    def get_stats_text(self):
        if self.metric.unit == "level":
            return self._level_stats()
        if self.metric.widget_type == "ratings" or self.metric.share_stats or getattr(self, "_alt", False):
            return self._ratings_stats()
        if self.metric.unit != "seconds":
            return super().get_stats_text()
        reviews = sum(int(r.get("_reviews", 0) or 0) for r in self.data or [])
        ms = sum(float(r.get("_ms", 0) or 0) for r in self.data or [])
        if not reviews:
            return []
        return [tr("Avg: {value}", value=self._format_metric_value(ms / 1000.0 / reviews)),
                tr_n("{count} review", "{count} reviews", reviews, count=fmt_num(reviews))]

    def _level_stats(self):
        """The cards at the end of the days shown (the last day of the view), each part with
        its change since the first day of the view."""
        rows = [r for r in (self.data or []) if isinstance(r, dict)]  # (the zoomed days when zoomed)
        if not rows:
            return []
        first, last = rows[0], rows[-1]
        total = sum(int(last.get(c["key"], 0) or 0) for c in self.series_config)
        if not total:
            return []
        if len(self.series_config) == 1:
            change = total - sum(int(first.get(c["key"], 0) or 0) for c in self.series_config)
            text = tr_n("{count} card", "{count} cards", total, count=fmt_num(total))
            if change and first.get("_day") != last.get("_day"):
                sign = "+" if change > 0 else "\u2212"
                text += f" ({sign}{fmt_num(abs(change))})"
            return [text]
        out = []
        for c in reversed(self.series_config):
            now = int(last.get(c["key"], 0) or 0)
            change = now - int(first.get(c["key"], 0) or 0)
            text = fmt_num(now)
            if change and first.get("_day") != last.get("_day"):
                sign = "+" if change > 0 else "\u2212"
                text += f" ({sign}{fmt_num(abs(change))})"
            out.append(tr("{name}: {value}", name=c["label"], value=text))
        out.append(tr_n("{count} card", "{count} cards", total, count=fmt_num(total)))
        return out

    def _ratings_stats(self):
        """The share of each button over the days shown (what the chart is about), then
        the number of reviews."""
        totals = {c["key"]: 0 for c in self.series_config}
        for row in self.data or []:
            for key in totals:
                totals[key] += int(row.get(key, 0) or 0)
        total = sum(totals.values())
        if not total:
            return []
        out = [tr("{name}: {value}%", name=c["label"], value=fmt_num_trim_zeros(totals[c["key"]] * 100.0 / total, 1))
               for c in self.series_config]
        if self.metric.unit == "cards":
            out.append(tr_n("{count} card", "{count} cards", total, count=fmt_num(total)))
        else:
            out.append(tr_n("{count} review", "{count} reviews", total, count=fmt_num(total)))
        return out
