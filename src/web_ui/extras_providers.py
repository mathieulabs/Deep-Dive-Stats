# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Data of the charts added on demand (charts.more_charts), as plain JSON."""


def _plain(v):
    from .providers import _plain as plain

    return plain(v)


def _reset_waiting(cfg, deck):
    """The cards of the decks that were studied and are new again (reset), not introduced again yet."""
    from aqt import mw

    from ..details.logic.metrics.review_buckets import _memo, did_limit

    if deck == -1:
        return 0
    try:
        limit = did_limit(cfg, deck, False)
        # kept until the history (_memo) or the cards change
        cards = tuple(mw.col.db.first("SELECT count(), max(mod), total(mod) FROM cards") or ())
        return _memo(("reset_waiting", limit, cards), lambda: int(mw.col.db.scalar(
            "SELECT count() FROM cards WHERE cards.type = 0 AND EXISTS (SELECT 1 FROM revlog WHERE revlog.cid = cards.id "
            f"AND revlog.type IN (0, 1, 2)) {limit}") or 0))
    except Exception:
        return 0


def _custom_searches(wtype):
    if wtype not in ("custom_bar", "custom_pie"):
        return None
    from ..details.logic.metrics.custom_search import searches
    from . import providers

    return searches(providers._setting(wtype, "searches", None))


def daily_metric(wtype, deck, span, options=None, days=None):
    """The stacked charts of days (ratings, forgotten, introduced, review speed, card counts over
    time) and the ones by seconds / intervals (answer time, rating by interval). days: the history
    rows to use instead of the period's (the adaptive zoom's 10-minute rows)."""
    from ..details.widgets.charts.daily_metrics import BY_TYPE, variation_colors
    from . import providers

    metric = BY_TYPE[wtype]
    cfg = providers._cfg()
    if days is None:
        first, last = (options or {}).get("_zoom") or (None, None)
        days, _all = providers._history_slice(deck, span, first, last)
    measure = None
    if metric.measures and metric.source is not None:
        # the view chosen in the header (Average Stability: Mean / Median, Memorised: Cards / Notes ...)
        measure = providers._setting(wtype, "measure", metric.measures[0])
        if measure not in metric.measures:
            measure = metric.measures[0]
        data = metric.source(cfg, deck, deck == -1, measure=measure)
    else:
        data = metric.source(cfg, deck, deck == -1) if metric.source is not None else None
    card_type, kinds = None, None
    if metric.card_types:
        # the card type of the answers counted (the header's pill: All, Learning, Young, Mature, Young + Mature)
        from ..details.logic.metrics.review_buckets import kinds_of

        card_type = providers._setting(wtype, "card_type", "all")
        if card_type not in metric.card_types:
            card_type = "all"
        kinds = kinds_of(card_type)
    more = {"kinds": kinds} if kinds else {}
    rows = metric.rows(days, data, **more) if metric.source is not None else metric.rows(days, **more)
    if wtype == "custom_bar":
        # Count / Time (its options icon): the rows have both
        measure = "time" if providers._setting(wtype, "measure", "count") == "time" else "count"
    if wtype == "ratings":
        # Count / Time (the header's pill): the time spent on each rating, read only when shown
        measure = "time" if providers._setting(wtype, "measure", "count") == "time" else "count"
        if measure == "time":
            from ..details.logic.metrics.review_buckets import did_limit
            from ..details.widgets.charts.daily_metrics import add_rating_times

            rows = add_rating_times(days, [dict(r) for r in rows], did_limit(cfg, deck, deck == -1), kinds)
    series = metric.series(cfg)
    keys = [s["key"] for s in series]
    out_rows = []
    for r in rows:
        row = {"date": str(r.get("pretty_date", "") or "")}
        for k, v in r.items():
            if k == "pretty_date":
                continue
            if isinstance(v, (int, float)):
                row[k] = float(v)
        if "reviews" not in row and metric.unit != "seconds":
            row["reviews"] = float(sum(row.get(k, 0.0) for k in keys))
        out_rows.append(row)

    def ser(items):
        return [{"key": s["key"], "label": str(s["label"]), "color": str(s["color"])} for s in items]

    alt = None
    if metric.alt:
        alt = {"label": str(metric.alt[0]), "series": ser(metric.alt[1](cfg))}
    return {
        "rows": out_rows, "series": ser(series), "alt": alt, "unit": metric.unit,
        # Custom Bar: its searches, edited from the page (DD.editSearches)
        "searches": _custom_searches(wtype),
        "by_day": bool(metric.by_day), "share_stats": bool(metric.share_stats),
        "cumulative": bool(metric.cumulative), "percent": bool(metric.percent), "average": bool(metric.average),
        # what a level counts: cards, a load (reviews a day), days; Memorised's views: notes, pct, ratio
        "value": getattr(data, "value", None) or metric.value,
        # Ratings: "count" or "time" (the bars: the time spent on each rating); the view of the others (measures)
        "measure": measure,
        "measures": list(metric.measures),
        # the card type of the answers counted, and the ones offered (the header's pill)
        "card_type": card_type,
        "card_types": list(metric.card_types),
        # a level whose change from bar to bar can be shown (Variation): the colours of a gain / a loss
        "variation_colors": variation_colors(cfg) if metric.variation else None,
        # Introduced: the cards reset to new and not introduced again yet (its header)
        "reset_waiting": _reset_waiting(cfg, deck) if wtype == "introduced" else None,
        "stats": wtype,
        # the period of the rows in ms (a click on Answer Time / Rating by Interval: its answers, browser_search)
        "range": _range_of(days),
    }


def _range_of(days):
    from ..details.logic.metrics.review_buckets import range_from_days

    try:
        rng = range_from_days(days)
    except Exception:
        rng = None
    return list(rng) if rng else None


def pie_settings(wtype):
    """The pie view's slices (discrete.js pieOptions): how far they go (Pie Range) and how many (Pie Slices); 0: the
    chart's own. pie_hidden: the slices hidden from its legend (their keys, pie.js toggleKind)."""
    from . import providers

    out = {}
    for key in ("pie_limit", "pie_slices"):
        try:
            out[key] = max(0, int(providers._setting(wtype, key, 0) or 0))
        except (TypeError, ValueError):
            out[key] = 0
    out["pie_hidden"] = [str(k) for k in (providers._setting(wtype, "pie_hidden", None) or []) if k]
    return out


def _interval_like(wtype, data, deck, span):
    """The payload of the Review Intervals chart (what discrete.js reads) over another distribution."""
    from ..details.widgets.common.fsrs_filters import (
        compute_fsrs_distribution_percentiles,
        resolve_fsrs_filter_choice,
        resolve_fsrs_filter_max_days,
        resolve_fsrs_filters,
    )
    from . import providers

    modes, short, _long = resolve_fsrs_filters(providers._setting(wtype, "filter_modes", None))
    idx, mode = resolve_fsrs_filter_choice(providers._setting(wtype, "time_span_idx"), modes=modes)
    dist = data.get("distribution", {}) or {}
    found = compute_fsrs_distribution_percentiles(dist, percentiles=(0.50, 0.95), positive_only=True, default_value=30)
    p50 = int(found["values"].get(0.50, 31))
    p95 = int(found["values"].get(0.95, 365))
    max_days = resolve_fsrs_filter_max_days(
        mode, dist=dist, p50=p50, p95=p95, one_month_days=31, all_fallback_days=30, invalid_fallback_days=31, minimum_days=1
    )
    filtered = {k: v for k, v in dist.items() if 0 < k <= max_days}
    label = short[modes.index(mode)] if mode in modes else ""
    return {
        "data": _plain(data), "max_days": max_days, "median": p50 if found["total"] > 0 else 0,
        "filter_label": str(label), "filter_labels": [str(x) for x in _long], "filter_idx": idx,
        "shown_total": sum(filtered.values()), "kind": wtype, **pie_settings(wtype),
    }


def interval_load(deck, span, options=None):
    from ..details.logic.metrics import ReviewIntervalsDataProvider
    from ..details.widgets.charts.interval_load import to_load
    from . import providers

    susp = bool(providers._setting("interval_load", "include_suspended", True))
    data = ReviewIntervalsDataProvider.fetch_data(providers._cfg(), deck, deck == -1, span, suspended=susp) or {}
    return dict(_interval_like("interval_load", to_load(data), deck, span), include_suspended=susp)


def machine_days(span, options=None):
    """The Time Machines' days: (the day shown, the earliest history day, today, period start) as day ordinals.
    Both the calendar and the slider run across the full review history (not limited to the active Time Span);
    the default day shown is the period's first day (today for Total) until the user picks a day ("at")."""
    from datetime import date, datetime, timedelta

    from aqt import mw

    from ..const.base import Period
    from ..details.logic import rollover_hour
    from ..details.logic.metrics.card_states import span_ordinal

    options = options or {}
    today = span_ordinal(Period.TOTAL)
    start = span_ordinal(span, options.get("custom_days", 7))
    first = min(start, today)
    try:
        rid = mw.col.db.scalar("SELECT min(id) FROM revlog")
        if rid:
            roll = timedelta(hours=int(rollover_hour() or 0))
            first = min(first, (datetime.fromtimestamp(int(rid) / 1000.0) - roll).date().toordinal())
    except Exception:
        pass
    day = start
    at = options.get("at")
    if at:
        try:
            day = max(first, min(today, date.fromisoformat(str(at)[:10]).toordinal()))
        except ValueError:
            pass
    return day, first, today, start


def _machine_out(out, days, wtype):
    from datetime import date

    from . import providers

    day, first, today = days[0], days[1], days[2]
    span_start = days[3] if len(days) > 3 else first
    out["day_slider"] = bool(providers._setting(wtype, "day_slider", True))  # its right click: Day Slider
    out["date"] = date.fromordinal(day).isoformat()
    out["first"] = date.fromordinal(first).isoformat()
    out["today"] = date.fromordinal(today).isoformat()
    out["span_start"] = date.fromordinal(span_start).isoformat()
    return out


def card_history(wtype, deck, span, options=None):
    from ..details.widgets.charts.card_history import card_distribution
    from . import providers

    timed = wtype == "interval_history"
    if timed:
        # the intervals of the cards on the day picked (the period's first day, today for Total)
        from ..details.logic.metrics.card_states import intervals_at

        empty = {"distribution": {}, "total": 0, "zero": 0, "sum": 0}
        days = machine_days(span, options)
        data = intervals_at(providers._cfg(), deck, False, days[0]) if deck != -1 else empty
    else:
        # the suspended cards counted or not
        susp = bool(providers._setting(wtype, "include_suspended", True))
        data = card_distribution(providers._cfg(), deck, wtype, suspended=susp)
    out = _interval_like(wtype, data, deck, span)
    if not timed:
        out["include_suspended"] = susp
    if wtype in ("lapse_distribution", "review_distribution", "time_distribution"):
        # Count / Total / Load (the header's choice): the same bars (range from the card counts), other heights
        # (Time per Card: Cards or Total Time)
        from ..details.widgets.charts.card_history import measured

        shown = measured(data, providers._setting(wtype, "measure", "count"))
        out["data"] = _plain(shown)
        out["measure"] = shown["measure"]
        out["shown_total"] = sum(v for k, v in shown["distribution"].items() if 0 < k <= out["max_days"])
    if wtype == "lapse_distribution":
        # its leeches: the cards at or over their preset's leech threshold (Anki tags them "leech" there)
        from ..details.widgets.charts.card_history import leech_count

        try:
            out["leeches"], out["leech_at"] = leech_count(providers._cfg(), deck, susp)
        except Exception:
            out["leeches"], out["leech_at"] = None, None
    if wtype == "lapse_distribution" and out.get("measure", "count") != "total":
        # a bar at 0: the cards never forgotten. Not on Reviews per Card (its
        # cards all have reviews) nor on Total (no lapses: a bar of 0)
        inc0 = bool(providers._setting(wtype, "include_zero", False))
        out["include_zero"] = inc0
        if inc0:
            ms = out.get("measure", "count")
            out["zero_bar"] = float(data.get("load_zero") or 0) if ms == "load" else int(data.get("zero") or 0)
    if timed:
        _machine_out(out, days, wtype)
    return out


def first_forgetting(wtype, deck, span, options=None):
    """First Long-term / Short-term Forgetting Curve (charts/curves.js): the samples by first rating and their fitted
    stabilities (logic.metrics.first_curves, the whole history), with the chart's options: the longest interval
    shown (0: all), the most points per rating, the outliers left out (long-term)."""
    from ..details.logic.metrics.first_curves import first_curve
    from ..details.logic.metrics.review_buckets import did_limit
    from . import providers

    out = dict(first_curve(did_limit(providers._cfg(), deck, deck == -1), short=wtype == "first_forgetting_short"))
    try:
        out["max_bins"] = max(1, min(50, int(providers._setting(wtype, "max_bins", 20) or 20)))
        out["max_interval"] = max(0.0, float(providers._setting(wtype, "max_interval", 0) or 0))
    except (TypeError, ValueError):
        out["max_bins"], out["max_interval"] = 20, 0.0
    out["outliers"] = bool(providers._setting(wtype, "outliers", False))
    return out


def memory_history(wtype, deck, span, options=None):
    """Stability / Difficulty Time Machine: the payload of Card Stability / Card Difficulty, from the
    cards' memory states on the day picked (the period's first day, today for Total), and that day."""
    from ..details.logic.metrics import fsrs_history
    from . import providers

    days = machine_days(span, options)
    day = days[0]
    kind = "stability" if wtype == "stability_history" else "difficulty"
    dist = {}
    if deck != -1:  # deleted cards: no memory state
        src = fsrs_history.deck_cards(providers._cfg(), deck, False)
        dist = fsrs_history.states_at(src, day)[kind]
    out = _machine_out({"data": providers._plain(dict(dist))}, days, wtype)
    if kind == "difficulty":
        return out
    from ..details.widgets.common.fsrs_filters import (
        compute_fsrs_distribution_percentiles,
        resolve_fsrs_filter_choice,
        resolve_fsrs_filter_max_days,
        resolve_fsrs_filters,
    )

    modes, short, _long = resolve_fsrs_filters(providers._setting(wtype, "filter_modes", None))
    idx, mode = resolve_fsrs_filter_choice(providers._setting(wtype, "time_span_idx"), modes=modes)
    found = compute_fsrs_distribution_percentiles(dist, percentiles=(0.50, 0.95), positive_only=False, default_value=30)
    p50 = int(found["values"].get(0.50, 30))
    p95 = int(found["values"].get(0.95, 30))
    out["max_days"] = resolve_fsrs_filter_max_days(
        mode, dist=dist, p50=p50, p95=p95, one_month_days=31, all_fallback_days=30, invalid_fallback_days=1,
        minimum_days=1, positive_only=False,
    )
    out["median"] = int(compute_fsrs_distribution_percentiles(
        dist, percentiles=(0.50,), positive_only=False, default_value=0)["values"].get(0.50, 0))
    out["filter_label"] = str(short[modes.index(mode)] if mode in modes else "")
    out["filter_labels"] = [str(x) for x in _long]
    out["filter_idx"] = idx
    out.update(pie_settings(wtype))
    return out


def due_today(deck, span, options=None):
    from ..details.widgets.charts.due_today import METRIC, fetch
    from . import providers

    cfg = providers._cfg()
    payload = fetch(cfg, deck, deck == -1) or {}
    series = METRIC.series(cfg)
    rows = []
    for r in payload.get("rows") or []:
        row = {"date": str(r.get("pretty_date", "") or "")}
        for k, v in r.items():
            if k != "pretty_date" and isinstance(v, (int, float)):
                row[k] = float(v)
        row["reviews"] = float(sum(row.get(s["key"], 0.0) for s in series))
        rows.append(row)
    out = {k: payload.get(k) for k in ("total", "due_now", "later", "next_due", "start")}
    out.update({"rows": rows, "series": [{"key": s["key"], "label": str(s["label"]), "color": str(s["color"])} for s in series],
                "unit": "cards", "by_day": False, "cumulative": True, "stats": "due_today"})
    return out


def week_hours(deck, span, options=None):
    from ..const.config import Config
    from ..details.widgets.charts.week_hours import fetch_counts
    from ..details.ui import get_chart_color
    from ..i18n import weekday_long, weekday_short
    from . import providers

    cfg = providers._cfg()
    # follows the zoom (extra_charts.follow_zoom): the zoomed days, or the days of the 10-minute view
    first, last = (options or {}).get("_zoom") or (None, None)
    days, _all = providers._history_slice(deck, span, first, last)
    dates = (options or {}).get("_dates")
    if dates:
        days = [r for r in _all if dates[0] <= str(r.get("logical_date") or r.get("date") or "")[:10] <= dates[1]]
    try:
        color = str(get_chart_color(Config.HEATMAP_COLOR, None))
    except Exception:
        color = "#3b82f6"
    out = {
        "monday_first": bool(cfg.config.get(Config.HEATMAP_MONDAY_FIRST, False)),
        "color": color,
        "short": [str(weekday_short(d)) for d in range(7)],
        "long": [str(weekday_long(d)) for d in range(7)],
        "view": "week",
        # the reviews of filtered decks counted or not
        "include_filtered": bool(providers._setting("week_hours", "include_filtered", True)),
    }
    if providers._setting("week_hours", "view", "week") == "day":
        out.update(_week_hours_by_day(cfg, deck, days, out["include_filtered"]))
    else:
        counts = fetch_counts(cfg, deck, deck == -1, days, filtered=out["include_filtered"])
        out["counts"] = {f"{wd},{h}": int(n) for (wd, h), n in counts.items()}
        out["range"] = _range_of(days)  # (a click on a cell: its answers, browser_search)
    return out


_DAY_ROWS = 31  # at most: longer periods put several days in a row


def _week_hours_by_day(cfg, deck, days, filtered=True):
    """Week by Hour's By Day view: a row per day of the period (or per group of days), counts by
    'row,hour'."""
    from datetime import date, timedelta
    from ..details.logic.metrics.review_buckets import day_hour_counts, did_limit, range_from_days
    from ..i18n import _day_text, month_short, tr

    dates = sorted({str(d.get("logical_date") or d.get("date") or "")[:10] for d in days or []} - {""})
    rng = range_from_days(days)
    if not dates or not rng:
        return {"view": "day", "rows": [], "counts": {}}
    first, last = date.fromisoformat(dates[0]), date.fromisoformat(dates[-1])
    n = (last - first).days + 1
    per = -(-n // _DAY_ROWS)  # days in a row
    label = lambda d: str(tr("{month} {day}", month=month_short(d.month), day=_day_text(d.day)))
    rows, row_of = [], {}
    for i in range(0, n, per):
        a, b = first + timedelta(days=i), min(last, first + timedelta(days=i + per - 1))
        for j in range((b - a).days + 1):
            row_of[(a + timedelta(days=j)).isoformat()] = len(rows)
        rows.append({"short": label(a), "long": label(a) if a == b else f"{label(a)} – {label(b)}",
                     "ms": _range_of([{"date": a.isoformat()}, {"date": b.isoformat()}])})
    counts = {}
    limit = did_limit(cfg, deck, deck == -1) + ("" if filtered else " AND revlog.type != 3")
    for (d, h), c in day_hour_counts(limit, *rng).items():
        r = row_of.get(d)
        if r is not None:
            key = f"{r},{h}"
            counts[key] = counts.get(key, 0) + int(c)
    return {"view": "day", "rows": rows, "counts": counts}


def _ret_range(code, deck, days=None):
    """(start ms, end ms, previous (start, end) or None) of a period (Anki's days, ending with today), or of the
    day rows given (a zoom)."""
    from aqt import mw

    from ..const import Period
    from ..details.logic.metrics.review_buckets import range_from_days
    from . import providers

    day = 86400
    cutoff = int(mw.col.sched.day_cutoff)
    if days is None:
        if code == Period.TODAY:
            s, e = cutoff - day, cutoff
        elif code == Period.YESTERDAY:
            s, e = cutoff - 2 * day, cutoff - day
        elif code == Period.TOTAL:
            return 0, cutoff * 1000, None
        elif code in Period.DAYS_IN and code != Period.CUSTOM:
            s, e = cutoff - Period.DAYS_IN[code] * day, cutoff
        else:  # a custom period, last year: its days
            days = providers._history_slice(deck, code, None, None)[0]
    if days is not None:
        rng = range_from_days(days)
        if not rng:
            return 0, 0, None
        return rng[0], rng[1], (2 * rng[0] - rng[1], rng[0])
    return s * 1000, e * 1000, ((2 * s - e) * 1000, s * 1000)


# the period before, by the chart's period: its name in the stats (texts of the catalogs, translated where used)
_BEFORE = {
    "today": "Yesterday", "yesterday": "Day before", "week": "Week before", "two_weeks": "2 weeks before",
    "month": "Month before", "three_months": "3 months before", "year": "Year before", None: "Period before",
}


def _desired_retention(deck):
    """The desired retention of FSRS (the deck's preset; for several decks or the whole collection, the current
    deck's), or None without FSRS."""
    from aqt import mw

    try:
        if not mw.col.get_config("fsrs", False) or deck == -1:
            return None
        did = deck[0] if isinstance(deck, (list, tuple)) and deck else deck
        if not isinstance(did, int) or did <= 0:
            did = int(mw.col.decks.current()["id"])
        dr = mw.col.decks.config_dict_for_deck_id(did).get("desiredRetention")
        return float(dr) if dr else None
    except Exception:
        return None


def todays_retention(deck, span, options=None):
    """First Answer Retention: the first answer of each card on each
    day, passed / failed, for the cards of one kind (all, learning, young, mature), over the chart's period (the
    Deep Dive's and its zoom, or a pinned widget's own). With the period before for comparison and FSRS's desired
    retention as a mark. Drawn by the pie chart."""
    from ..const import Period
    from ..const.config import Config
    from ..details.logic.metrics.review_buckets import did_limit, first_answers
    from ..details.ui import get_color
    from ..i18n import tr, tr_name
    from . import providers

    cfg = providers._cfg()
    pinned = getattr(providers._OWN, "d", None) is not None
    code = int(span)
    # follows the zoom (as Week by Hour): the zoomed days, or the days of the 10-minute view
    first, last = (options or {}).get("_zoom") or (None, None)
    dates = (options or {}).get("_dates")
    days = None
    if first is not None or dates:
        days, _all = providers._history_slice(deck, span, first, last)
        if dates:
            days = [r for r in _all if dates[0] <= str(r.get("logical_date") or r.get("date") or "")[:10] <= dates[1]]
    start, end, prev = _ret_range(code, deck, days)
    limit = did_limit(cfg, deck, deck == -1)
    kinds = ("learn", "young", "mature")
    choice = providers._setting("todays_retention", "card_type", "all")
    choice = choice if choice in kinds else "all"
    picked = kinds if choice == "all" else (choice,)

    def tally(counts):
        return (sum(counts.get((kinds.index(k), 1), 0) for k in picked),
                sum(counts.get((kinds.index(k), 0), 0) for k in picked))

    counts = first_answers(limit, start, end) if end > start else {}
    by_kind = {k: [counts.get((i, 1), 0), counts.get((i, 0), 0)] for i, k in enumerate(kinds)}
    passed, failed = tally(counts)
    before = None
    if prev:
        p, f = tally(first_answers(limit, *prev))
        before = round(p * 100.0 / (p + f), 1) if p + f else None
    names = {Period.TODAY: "today", Period.YESTERDAY: "yesterday", Period.WEEK: "week", Period.TWO_WEEKS: "two_weeks",
             Period.MONTH: "month", Period.THREE_MONTHS: "three_months", Period.YEAR: "year", Period.LAST_YEAR: "year"}
    before_name = _BEFORE[None if days is not None else names.get(code)]
    from .trace import trace

    show_change = providers._setting("todays_retention", "show_change", True) is not False
    show_target = providers._setting("todays_retention", "show_target", True) is not False
    trace(f"RETENTION span={code} pinned={pinned} zoom={'%d days' % len(days) if days is not None else '-'} "
          f"range={start}..{end} passed={passed} failed={failed} before={before}")
    return {
        "counts": {"pass": passed, "fail": failed},
        "order": ["pass", "fail"],
        "labels": {"pass": str(tr("Passed")), "fail": str(tr("Failed"))},
        "colors": {"pass": str(get_color(cfg.config, Config.COLOR_GOOD, "details")),
                   "fail": str(get_color(cfg.config, Config.COLOR_AGAIN, "details"))},
        "center": {"key": "pass", "label": str(tr("Retention"))},
        "by_kind": by_kind, "card_type": choice, "range": [int(start), int(end)] if end > start else None,
        "before": before, "before_label": str(tr_name(before_name)),
        "target": _desired_retention(deck),
        "show_change": show_change, "show_target": show_target,
        "show_legend": bool(providers._setting("todays_retention", "show_legend", True)),
        "legend_mode": str(providers._setting("todays_retention", "legend_mode", "auto") or "auto"),
        "legend_pct": bool(providers._setting("todays_retention", "legend_pct", False)),
    }


_SXR_R_BINS = (1, 2, 5, 10)  # the width of its columns, in % of retrievability
_SXR_S_ROWS = (10, 15, 20, 30, 40)  # about how many rows of stability


def sxr_heatmap(deck, span, options=None):
    """SxR Heatmap (charts/extras.js sxrMount): the review cards now by FSRS stability and retrievability
    (logic.metrics.sxr; no period), flat [retrievability in 0.1 %, stability in 0.1 day, cards, ...], with the
    chart's options, which the page bins them by."""
    from ..const.config import Config
    from ..details.logic.metrics.sxr import sxr_points
    from ..details.ui import get_chart_color
    from . import providers

    flat = []
    for (r, s), n in sorted(sxr_points(providers._cfg(), deck, deck == -1).items()):
        flat += (r, s, n)
    try:
        color = str(get_chart_color(Config.HEATMAP_COLOR, None))
    except Exception:
        color = "#3b82f6"

    def pick(key, default, allowed):
        try:
            v = int(providers._setting("sxr_heatmap", key, default))
        except (TypeError, ValueError):
            return default
        return v if v in allowed else default

    return {"points": flat, "color": color, "log_s": bool(providers._setting("sxr_heatmap", "log_s", True)),
            # the cells from the Easy colour (fewest cards) to the Again colour (most)
            "two_colors": bool(providers._setting("sxr_heatmap", "two_colors", True)),
            "r_bin": pick("r_bin", 5, _SXR_R_BINS), "s_rows": pick("s_rows", 20, _SXR_S_ROWS)}


_BW_MIN = (10, 20, 50, 100, 200)  # B-W Matrix: the fewest answers a cell shows its gap with


def bw_matrix(deck, span, options=None):
    """B-W Matrix (charts/extras.js bwMount): flat [row, difficulty, answers, passed, predicted recall
    sum (hundredths), ...] of logic.metrics.fsrs_history.bw_matrix (no period), its colours and the
    fewest answers a cell needs."""
    from ..const.config import Config
    from ..details.logic.metrics import fsrs_history
    from ..details.ui import get_chart_color
    from . import providers

    flat = []
    if deck != -1:  # deleted cards: no memory state
        src = fsrs_history.deck_cards(providers._cfg(), deck, False)
        for (row, d), (n, ok, pred) in sorted(fsrs_history.bw_matrix(src).items()):
            flat += (row, d, n, ok, round(pred * 100))

    def color(key, default):
        try:
            return str(get_chart_color(key, None))
        except Exception:
            return default

    try:
        least = int(providers._setting("bw_matrix", "min_answers", 50))
    except (TypeError, ValueError):
        least = 50
    return {"cells": flat, "power": fsrs_history.BW_POWER, "min_answers": least if least in _BW_MIN else 50,
            "more": color(Config.COLOR_EASY, "#3b82f6"), "less": color(Config.COLOR_AGAIN, "#ef4444")}


def custom_pie(deck, span, options=None):
    """Custom Pie (charts/extras.js customPieMount): a slice per search of its setting, the value of the deck's
    cards it finds (logic.metrics.custom_search; no period), the searches as saved (edited from the page)."""
    from ..details.logic.metrics import custom_search as cs
    from . import providers

    rows = _custom_searches("custom_pie")
    measure = providers._setting("custom_pie", "measure", "cards")
    if measure not in cs.PIE_MEASURES:
        measure = "cards"
    values = cs.pie_values(providers._cfg(), deck, deck == -1, [s["q"] for s in rows], measure)
    return {"slices": [{"q": s["q"], "color": cs.colour(i, s["c"]), "value": v or 0.0, "bad": v is None}
                       for i, (s, v) in enumerate(zip(rows, values))],
            "measure": measure, "searches": rows}


EXTRA_PROVIDERS = {
    "interval_load": interval_load, "due_today": due_today, "week_hours": week_hours,
    "todays_retention": todays_retention,
    "lapse_distribution": lambda deck, span, options=None: card_history("lapse_distribution", deck, span, options),
    "review_distribution": lambda deck, span, options=None: card_history("review_distribution", deck, span, options),
    "learning_steps": lambda deck, span, options=None: card_history("learning_steps", deck, span, options),
    "time_distribution": lambda deck, span, options=None: card_history("time_distribution", deck, span, options),
    "interval_history": lambda deck, span, options=None: card_history("interval_history", deck, span, options),
    "stability_history": lambda deck, span, options=None: memory_history("stability_history", deck, span, options),
    "difficulty_history": lambda deck, span, options=None: memory_history("difficulty_history", deck, span, options),
    "first_forgetting": lambda deck, span, options=None: first_forgetting("first_forgetting", deck, span, options),
    "first_forgetting_short": lambda deck, span, options=None: first_forgetting("first_forgetting_short", deck, span, options),
    "sxr_heatmap": sxr_heatmap,
    "bw_matrix": bw_matrix,
    "custom_pie": custom_pie,
}
for _t in ("ratings", "review_speed", "forgotten", "resets", "introduced", "introduced_load", "answer_time", "interval_ratings",
           "rating_fatigue", "sibling_ratings", "card_states", "load_trend", "stability_trend", "memorised",
           "fsrs_calibration", "forgetting_curve", "fsrs_fatigue", "leech_detector", "stability_increase", "custom_bar", "future_retention"):
    EXTRA_PROVIDERS[_t] = (lambda t: (lambda deck, span, options=None: daily_metric(t, deck, span, options)))(_t)
