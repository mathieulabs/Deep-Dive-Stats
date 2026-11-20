# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Charts read from the review history of each day (the history cache already holds it):
the answer buttons over time, the time per review, the cards forgotten.

Each one is a stacked bar chart of the days (ActivityStackedChart) fed with the daily rows
of the cache. CHARTS describes them: the pinned widgets, the Deep Dive sections and the
widget gallery all read it."""

from ....logic.formatting import fmt_num, fmt_num_trim_zeros
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
    (the rows carry the keys of both).
    value: what a "level" counts: "cards", "load" (reviews a day, with decimals) or "days" (an
    average stability).
    has_span: whether the period chosen changes it (False: the whole history of the cards).
    measures: the views of the bars the header offers (the first by default), given to
    source(cfg, deck_id, is_deleted, measure=...).
    variation: a level whose change from bar to bar can be shown (the header's Variation pill).
    card_types: the card types the header offers to count ("all", "learn", "young", "mature",
    "review" = young and mature), given to rows(..., kinds=...) as
    review_buckets.kinds_of."""

    def __init__(self, widget_type, label, group, series, rows, unit="reviews", cumulative=False, percent=False,
                 source=None, alt=None, average=True, by_day=True, share_stats=False, value="cards", has_span=True, measures=(), variation=False,
                 card_types=()):
        self.widget_type = widget_type
        self.card_types = card_types
        self.variation = variation
        self.measures = measures
        self.has_span = has_span
        self.value = value
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


def variation_colors(cfg):
    """The colours of a gain / a loss (Variation): the Good / Again colours."""
    from ....ui import Config

    return {"gain": _color(cfg, Config.COLOR_GOOD), "loss": _color(cfg, Config.COLOR_AGAIN)}


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


def _ratings_rows(days, kinds=None):
    out = []
    names = [("learning", "young", "mature")[k] for k in (kinds or (0, 1, 2))]
    for d in days:
        if "again" in d and not kinds:
            counts = [int(d.get(k, 0) or 0) for k in ("again", "hard", "good", "easy")]
        else:
            counts = [sum(b) for b in zip(*(_buttons(d, k) for k in names))]
        out.append({"pretty_date": d.get("pretty_date", ""),
                    **dict(zip(("again", "hard", "good", "easy"), counts))})
    return out


def add_rating_times(days, rows, limit, kinds=None):
    """Ratings' Time view: each row (one per day row)
    gets the time spent on each rating, again_time_ms ... easy_time_ms, and their sum time_ms
    (kinds: of those card kinds only)."""
    from ....logic.metrics.review_buckets import range_from_days, rating_times

    for row in rows:
        row.update({f"{k}_time_ms": 0 for k in _RATING_KEYS})
        row["time_ms"] = 0
    rng = range_from_days(days)
    if not rows or not rng or limit is None:
        return rows
    minutes = any(len(str(d.get("date", "") or "")) > 10 for d in days)
    times = rating_times(limit, *rng, minutes=minutes, kinds=kinds)
    if minutes:
        row_of = _row_of(days)
        place = lambda key: row_of(key * 60000)  # noqa: E731
    else:
        index = {str(d.get("logical_date") or d.get("date") or "")[:10]: i for i, d in enumerate(days)}
        place = index.get
    for (key, ease), ms in times.items():
        i = place(key)
        if i is None or i >= len(rows):
            continue
        rows[i][f"{_RATING_KEYS[ease - 1]}_time_ms"] += ms
        rows[i]["time_ms"] += ms
    return rows


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


# the count and time fields of each card kind (0 learning, with the relearning; 1 young; 2 mature)
_SPEED_KEYS = {0: ("learn", "relearn"), 1: ("young",), 2: ("mature",)}


def _speed_rows(days, kinds=None):
    out = []
    names = [n for k in (kinds or ()) for n in _SPEED_KEYS.get(k, ())]
    for d in days:
        if names:
            # the answers of the card types chosen only (the cramming ones count under All)
            reviews = sum(int(d.get(f"{n}_count", 0) or 0) for n in names)
            ms = float(sum(float(d.get(f"{n}_time_ms", 0) or 0) for n in names))
        else:
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


def _row_of(days):
    """row_of(review id in ms): the index of the row (a day, or a bin of minutes for Today /
    Yesterday) a moment falls in, or None outside the rows."""
    import bisect
    from datetime import datetime, timedelta

    from ....logic import rollover_hour

    dates = [str(d.get("date", "") or "") for d in days]
    if any(len(x) > 10 for x in dates):
        starts = [datetime.strptime(x[:16], "%Y-%m-%d %H:%M") for x in dates]
        step = (starts[1] - starts[0]) if len(starts) > 1 else timedelta(minutes=10)
        end = starts[-1] + step

        def row_of(rid):
            dt = datetime.fromtimestamp(rid / 1000.0)
            if dt < starts[0] or dt >= end:
                return None
            return bisect.bisect_right(starts, dt) - 1
        return row_of
    index = {x[:10]: i for i, x in enumerate(dates)}
    roll = timedelta(hours=int(rollover_hour() or 0))
    return lambda rid: index.get((datetime.fromtimestamp(rid / 1000.0) - roll).strftime("%Y-%m-%d"))


def _introduced_rows(days, events):
    """The cards introduced in each row (a day, or a bin of minutes for Today / Yesterday):
    new / re-introduced, and their first rating (again ... easy; r_again ...: of the re-introduced
    ones, taken off when they are not counted, extras.js)."""
    out = [{"pretty_date": d.get("pretty_date", ""), "new": 0, "reintro": 0,
            "again": 0, "hard": 0, "good": 0, "easy": 0, "r_again": 0, "r_hard": 0, "r_good": 0, "r_easy": 0,
            "reviews": 0} for d in days]
    if not days or not events:
        return out
    row_of = _row_of(days)
    keys = ("again", "hard", "good", "easy")
    for rid, ease, reintro in events:
        i = row_of(rid)
        if i is None:
            continue
        row = out[i]
        row["reintro" if reintro else "new"] += 1
        if 1 <= ease <= 4:
            row[keys[ease - 1]] += 1
            if reintro:
                row["r_" + keys[ease - 1]] += 1
        row["reviews"] += 1  # (a row with cards: kept by "show empty" checks)
    return out


def _introduced_load_series(cfg):
    from ....ui import Config

    return [
        {"key": "mature", "label": tr("Mature"), "color": _color(cfg, Config.COLOR_MATURE), "color_key": Config.COLOR_MATURE},
        {"key": "young", "label": tr("Young"), "color": _color(cfg, Config.COLOR_YOUNG), "color_key": Config.COLOR_YOUNG},
    ]


def _introduced_load_source(cfg, deck_id, is_deleted):
    from ....logic.metrics.introduced import introduced_loads

    return introduced_loads(cfg, deck_id, is_deleted)


def _introduced_load_rows(days, loads):
    """The load the cards introduced in each row bring now (reviews a day), young / mature."""
    out = [{"pretty_date": d.get("pretty_date", ""), "young": 0.0, "mature": 0.0} for d in days]
    if not days or not loads:
        return out
    row_of = _row_of(days)
    for rid, load, mature in loads:
        i = row_of(rid)
        if i is not None:
            out[i]["mature" if mature else "young"] += load
    for row in out:
        row["reviews"] = row["young"] + row["mature"]  # (the bar's total, as the other charts of days)
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
# The card type filter of the charts of review answers (DailyMetric card_types)
_CARD_TYPES = ("all", "learn", "young", "mature", "review")


def _reset_series(cfg):
    from ....ui import Config

    return [
        {"key": "mature", "label": tr("Mature"), "color": _color(cfg, Config.COLOR_MATURE), "color_key": Config.COLOR_MATURE},
        {"key": "young", "label": tr("Young"), "color": _color(cfg, Config.COLOR_YOUNG), "color_key": Config.COLOR_YOUNG},
        {"key": "learn", "label": tr("Learning"), "color": _color(cfg, Config.COLOR_LEARN), "color_key": Config.COLOR_LEARN},
    ]


def _reset_rows(days, limit):
    """The cards reset to new (Forget) in each row (a day, or a bin of minutes for Today /
    Yesterday), by what they were before: learning, young, mature."""
    from ....logic.metrics.review_buckets import range_from_days, reset_events

    out = [{"pretty_date": d.get("pretty_date", ""), "learn": 0, "young": 0, "mature": 0} for d in days]
    rng = range_from_days(days)
    if not days or not rng or limit is None:
        return out
    row_of = _row_of(days)
    for rid, kind in reset_events(limit, *rng):
        i = row_of(rid)
        if i is not None:
            out[i][("learn", "young", "mature")[kind]] += 1
    return out


def _answer_time_rows(days, limit, kinds=None):
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
        if kinds and kind not in kinds:
            continue
        row = rows[s]
        row[_RATING_KEYS[ease - 1]] += n
        row[("learn", "young", "mature")[kind]] += n
        row["reviews"] += n
    return rows


def _interval_rows(days, limit, kinds=None):
    """One bar per interval in days before the answer, the reviews by rating."""
    from ....logic.metrics.review_buckets import interval_rating_counts, range_from_days

    rng = range_from_days(days)
    counts = interval_rating_counts(limit, *rng, kinds=kinds) if (rng and limit is not None) else {}
    top = max([i for (i, _e) in counts] + [7])
    rows = [{"pretty_date": tr("{value} d", value=i), "again": 0, "hard": 0, "good": 0, "easy": 0, "reviews": 0}
            for i in range(1, top + 1)]
    for (i, ease), n in counts.items():
        row = rows[i - 1]
        row[_RATING_KEYS[ease - 1]] += n
        row["reviews"] += n
    return rows


def _fatigue_rows(days, limit, kinds=None):
    """One bar per place of a review in its day (the 1st, the 2nd... of all the reviews of that
    day), the reviews by rating: how the answers go as the session gets longer."""
    from ....logic.metrics.review_buckets import MAX_POSITION, fatigue_counts, range_from_days

    rng = range_from_days(days)
    counts = fatigue_counts(limit, *rng, kinds=kinds) if (rng and limit is not None) else {}
    top = max([p for (p, _e) in counts] + [20])
    rows = [{"pretty_date": fmt_num(p) + ("+" if p == MAX_POSITION else ""),
             "again": 0, "hard": 0, "good": 0, "easy": 0, "reviews": 0}
            for p in range(1, top + 1)]
    for (p, ease), n in counts.items():
        row = rows[p - 1]
        row[_RATING_KEYS[ease - 1]] += n
        row["reviews"] += n
    return rows


def _sibling_rows(days, limit):
    """One bar per number of days since another card of the same note was last answered (0: the
    same day), the review answers by rating."""
    from ....logic.metrics.review_buckets import range_from_days
    from ....logic.metrics.siblings import MAX_GAP, sibling_counts

    rng = range_from_days(days)
    counts = sibling_counts(limit, *rng) if (rng and limit is not None) else {}
    rows = [{"pretty_date": tr("{value} d", value=g) + ("+" if g == MAX_GAP else ""),
             "again": 0, "hard": 0, "good": 0, "easy": 0, "reviews": 0}
            for g in range(0, MAX_GAP + 1)]
    for (g, ease), n in counts.items():
        row = rows[g]
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


def _day_ordinal(d):
    from datetime import date

    try:
        return date.fromisoformat(str(d.get("logical_date") or d.get("date") or "")[:10]).toordinal()
    except ValueError:
        return None


def _load_trend_source(cfg, deck_id, is_deleted):
    from ....logic.metrics.card_states import load_timeline

    return load_timeline(cfg, deck_id, is_deleted)


def _load_trend_rows(days, data):
    """Each day: the load at its end (reviews a day: 1 / interval of each review card), young / mature."""
    out = []
    for d in days:
        ordinal = _day_ordinal(d)
        young, mature = data.at(ordinal) if (data is not None and ordinal is not None) else (0.0, 0.0)
        out.append({"pretty_date": d.get("pretty_date", ""), "_day": ordinal, "young": young, "mature": mature,
                    "total": young + mature})
    return out


def _stability_source(cfg, deck_id, is_deleted, measure="mean"):
    from ....logic.metrics.fsrs_history import deck_cards, stability_levels

    if deck_id == -1 or is_deleted:
        return None  # deleted cards: no card info (no memory state)
    return _Measured(stability_levels(deck_cards(cfg, deck_id, is_deleted)), measure if measure == "median" else "mean")


class _Measured:
    """A timeline with the view chosen in the chart's header (DailyMetric.measures), and what its
    values count (DailyMetric.value, for the payload)."""

    def __init__(self, data, measure, value=None):
        self.data = data
        self.measure = measure
        self.value = value

    def at(self, ordinal):
        return self.data.at(ordinal)


def _stability_rows(days, data):
    """Each day: the mean or median stability (days) of the cards with a FSRS memory state at its
    end, split by the share of young / mature cards (stability under / over 21 days), with
    their average difficulty and how many they were."""
    median = getattr(data, "measure", None) == "median"
    out = []
    for d in days:
        ordinal = _day_ordinal(d)
        mean, med, ry, dif, n = data.at(ordinal) if (data is not None and ordinal is not None) else (0.0, 0.0, 0.0, 0.0, 0)
        v = med if median else mean
        out.append({"pretty_date": d.get("pretty_date", ""), "_day": ordinal, "young": v * ry, "mature": v * (1.0 - ry),
                    "total": v, "stability": v, "difficulty": dif, "cards": n})
    return out


def _memorised_series(cfg):
    from ....ui import Config

    return [{"key": "memorised", "label": tr("Memorised"), "color": _color(cfg, Config.COLOR_BAR), "color_key": Config.COLOR_BAR}]


class _PerLoad:
    """Memorised over the load of the same day (Cards per Load): the cards known per review a day."""

    def __init__(self, mem, load):
        self.mem = mem
        self.load = load

    def at(self, ordinal):
        y, m = self.load.at(ordinal)
        return self.mem.at(ordinal) / (y + m) if (y + m) > 0 else 0.0


def _memorised_source(cfg, deck_id, is_deleted, measure="cards"):
    from ....logic.metrics.fsrs_history import MEMORISED_MEASURES, deck_cards, memorised

    if deck_id == -1 or is_deleted:
        return None  # deleted cards: no card info (no memory state)
    if measure not in MEMORISED_MEASURES:
        measure = "cards"
    src = deck_cards(cfg, deck_id, is_deleted)
    if measure == "load":
        from ....logic.metrics.card_states import load_timeline

        return _Measured(_PerLoad(memorised(src), load_timeline(cfg, deck_id, is_deleted)), measure, "ratio")
    value = {"notes": "notes", "average": "pct"}.get(measure, "cards")
    return _Measured(memorised(src, measure), measure, value)


def _memorised_rows(days, data):
    """Each day: how many cards were known at its end (the sum of their recall, FSRS), or the
    view of it chosen (_memorised_source): notes, a percent, cards per review a day."""
    whole = (getattr(data, "value", None) or "cards") in ("cards", "notes")
    out = []
    for d in days:
        ordinal = _day_ordinal(d)
        v = data.at(ordinal) if (data is not None and ordinal is not None) else 0.0
        out.append({"pretty_date": d.get("pretty_date", ""), "_day": ordinal, "memorised": int(round(v)) if whole else v})
    return out


def _passed_series(cfg):
    from ....ui import Config

    return [
        {"key": "failed", "label": tr("Failed"), "color": _color(cfg, Config.COLOR_AGAIN), "color_key": Config.COLOR_AGAIN},
        {"key": "passed", "label": tr("Passed"), "color": _color(cfg, Config.COLOR_GOOD), "color_key": Config.COLOR_GOOD},
    ]


def _fsrs_cards_source(cfg, deck_id, is_deleted):
    from ....logic.metrics.fsrs_history import deck_cards

    if deck_id == -1 or is_deleted:
        return None  # deleted cards: no card info (no memory state)
    return deck_cards(cfg, deck_id, is_deleted)


def _fsrs_bins(days, src, kind):
    """{bin: [failed, passed, predicted recall sum]} of the review answers of the days shown."""
    from ....logic.metrics import fsrs_history

    ords = [o for o in (_day_ordinal(d) for d in days) if o is not None]
    if src is None or not ords:
        return {}
    fn = fsrs_history.calibration if kind == "calibration" else fsrs_history.forgetting
    return fn(src, min(ords), max(ords))


def _fsrs_row(label, cell):
    failed, passed, pred = cell if cell else (0, 0, 0.0)
    return {"pretty_date": label, "failed": failed, "passed": passed, "reviews": failed + passed, "_pred": pred}


def _calibration_rows(days, src):
    """One bar per 5% of the recall FSRS predicted before the answer, the review answers passed /
    failed: with "Show as %", the share passed should match the bar's range. Always the 20 bars
    (another deck or period morphs the same bars)."""
    from ....logic.metrics.fsrs_history import BINS

    bins = _fsrs_bins(days, src, "calibration")
    if not bins:
        return []
    step = 100 // BINS
    return [_fsrs_row(f"{b * step}–{(b + 1) * step}%", bins.get(b)) for b in range(BINS)]


def _forgetting_rows(days, src):
    """One bar per tenth of the days since the last review divided by the stability then, the
    review answers passed / failed: with "Show as %", the forgetting curve seen in the answers
    (at 1.0, FSRS expects 90%). Always the bars 0 to 3+ (another deck or period morphs the same bars)."""
    from ....logic.metrics.fsrs_history import RATIO_BINS, RATIO_STEP

    bins = _fsrs_bins(days, src, "forgetting")
    if not bins:
        return []
    return [_fsrs_row(fmt_num_trim_zeros(b * RATIO_STEP, 1) + ("+" if b == RATIO_BINS else ""), bins.get(b))
            for b in range(0, RATIO_BINS + 1)]


def _loss_series(cfg):
    from ....ui import Config

    return [{"key": "loss", "label": tr("RMSE"), "color": _color(cfg, Config.COLOR_BAR), "color_key": Config.COLOR_BAR}]


def _fatigue_loss_rows(days, src, kinds=None):
    """One bar per place of a review answer in its day (as Rating Fatigue), its height the gap
    between the share passed and the recall FSRS predicted (in %): how far off FSRS is as the
    day's reviews add up. A bar of several places
    shows their RMSE (activity.js, unit "rmse": _sq and _reviews)."""
    from ....logic.metrics import fsrs_history
    from ....logic.metrics.review_buckets import MAX_POSITION

    ords = [o for o in (_day_ordinal(d) for d in days) if o is not None]
    if src is None or not ords:
        return []
    bins = fsrs_history.fatigue_loss(src, min(ords), max(ords), kinds)
    if not bins:
        return []
    top = max(list(bins) + [20])
    rows = []
    for p in range(1, top + 1):
        n, ok, pred = bins.get(p) or (0, 0, 0.0)
        gap = (ok - pred) * 100.0 / n if n else 0.0
        rows.append({"pretty_date": fmt_num(p) + ("+" if p == MAX_POSITION else ""), "loss": abs(gap),
                     "reviews": n, "_reviews": n, "_sq": n * gap * gap, "passed": ok, "_pred": pred})
    return rows


def _leech_series(cfg):
    from ....ui import Config

    return [{"key": "cards", "label": tr("Cards"), "color": _color(cfg, Config.COLOR_AGAIN), "color_key": Config.COLOR_AGAIN}]


def _leech_source(cfg, deck_id, is_deleted):
    from ....logic.metrics.fsrs_history import deck_cards, leech_odds

    if deck_id == -1 or is_deleted:
        return None  # deleted cards: no card info (no memory state)
    return leech_odds(deck_cards(cfg, deck_id, is_deleted))


def _leech_rows(days, data):
    """One bar per 5% of how unlikely the cards' lapses are (from 5% to 100%), the cards in it:
    the cards on the right failed far more often than FSRS expected, leeches in the making.
    The whole history of the cards, whatever the period."""
    from ....logic.metrics.fsrs_history import LEECH_BINS

    counts = data[0] if data else None
    if not counts or not any(counts):
        return []
    return [{"pretty_date": f"{(b + 1) * 5}–{(b + 2) * 5}%", "cards": counts[b], "reviews": counts[b]}
            for b in range(LEECH_BINS)]


def _sinc_series(cfg):
    from ....ui import Config

    return [{"key": "cards", "label": tr("Cards"), "color": _color(cfg, Config.COLOR_GOOD), "color_key": Config.COLOR_GOOD}]


def _sinc_source(cfg, deck_id, is_deleted):
    """(width of a bar, cards per bar, sum of their factors per bar) of logic.metrics.sinc, or None."""
    from ....logic.metrics.sinc import BINS, binned, factors

    if deck_id == -1 or is_deleted:
        return None  # deleted cards: no preset
    pairs = factors(cfg, deck_id, is_deleted)
    b = binned(pairs)
    if not b:
        return None
    sums = [0.0] * BINS
    for cid, f in pairs:
        sums[b[2][cid]] += f
    return b[0], b[1], sums


def _sinc_rows(days, data):
    """One bar per step of the factor from 1x (the last: that and more), the cards in it (Search
    Stats Extended's Ease Factors). The cards as they are now, whatever the period."""
    if not data or not any(data[1]):
        return []
    width, counts, sums = data
    last = len(counts) - 1

    def x(v):
        return "\u00d7" + fmt_num_trim_zeros(v, 2)

    return [{"pretty_date": x(1 + b * width) + ("+" if b == last else "\u2013" + fmt_num_trim_zeros(1 + (b + 1) * width, 2)),
             "cards": counts[b], "reviews": counts[b], "_fsum": sums[b]} for b in range(len(counts))]


def _custom_bar_searches():
    """Custom Bar's searches (its setting, logic.metrics.custom_search.searches)."""
    from .....web_ui import providers
    from ....logic.metrics.custom_search import searches

    return searches(providers._setting("custom_bar", "searches", None))


def _custom_bar_series(cfg):
    from ....logic.metrics.custom_search import colour

    return [{"key": f"s{i}", "label": s["q"] or "*", "color": colour(i, s["c"]), "color_key": None}
            for i, s in enumerate(_custom_bar_searches())]


def _custom_bar_source(cfg, deck_id, is_deleted):
    """The deck's cards each search finds (None: a search Anki cannot read)."""
    from ....logic.metrics.custom_search import matching

    return matching(cfg, deck_id, is_deleted, [s["q"] for s in _custom_bar_searches()])[0]


def _custom_bar_rows(days, sets):
    """Each row: the reviews of each search's cards (s0, s1...) and their time (s0_time_ms...: the Time view)."""
    from ....logic.metrics.custom_search import bar_counts

    sets = list(sets or [])
    counts = bar_counts(sets, days, _row_of(days)) if days and sets else [[] for _d in days]
    out = []
    for d, row in zip(days, counts):
        r = {"pretty_date": d.get("pretty_date", ""), "reviews": 0, "time_ms": 0}
        for i in range(len(sets)):
            n, ms = row[i] if i < len(row) else (0, 0)
            r[f"s{i}"], r[f"s{i}_time_ms"] = n, ms
            r["reviews"] += n
            r["time_ms"] += ms
        out.append(r)
    return out


def _predicted_series(cfg):
    from ....ui import Config

    return [
        {"key": "failed", "label": tr("Predicted fail"), "color": _color(cfg, Config.COLOR_AGAIN), "color_key": Config.COLOR_AGAIN},
        {"key": "passed", "label": tr("Predicted pass"), "color": _color(cfg, Config.COLOR_GOOD), "color_key": Config.COLOR_GOOD},
    ]


FUTURE_RETENTION_DAYS = 365  # the days ahead shown, at most


def _future_retention_source(cfg, deck_id, is_deleted):
    from ....logic.metrics.future_due import _expected_retention
    from ....logic.metrics.review_buckets import did_limit

    if deck_id == -1 or is_deleted:
        return None  # deleted cards: no card info (no memory state)
    return _expected_retention(did_limit(cfg, deck_id, is_deleted), False)


def _future_retention_rows(days, data):
    """One bar per day ahead (today first, up to the last day a card is due, a year at most), the
    cards due that day split by the recall FSRS expects then: passed (the sum of their
    retrievabilities) and failed. With "Show as %", the retention to expect each day (Search Stats
    Extended's Future Due Retention). Overdue cards left out; nothing with FSRS off."""
    if not data:
        return []
    last = min(FUTURE_RETENTION_DAYS, max((d for d in data if d >= 0), default=-1))
    if last < 0:
        return []
    rows = []
    for d in range(0, last + 1):
        sum_r, n = data.get(d) or (0.0, 0)
        ok = round(float(sum_r), 1)
        rows.append({"pretty_date": tr("Today") if d == 0 else tr("{value} d", value=fmt_num(d)),
                     "passed": ok, "failed": round(n - ok, 1), "reviews": int(n), "cards": int(n)})
    return rows


def _card_states_rows(days, data):
    """Each day: how many cards were new / learning / relearning / young / mature at its end."""
    from ....logic.metrics.card_states import KEYS

    out = []
    for d in days:
        counts = (0, 0, 0, 0, 0)
        ordinal = _day_ordinal(d)
        if data is not None and ordinal is not None:
            counts = data.at(ordinal)
        row = {"pretty_date": d.get("pretty_date", ""), "_day": ordinal}
        row.update({k: int(v) for k, v in zip(KEYS, counts)})
        row["total"] = int(sum(counts))
        out.append(row)
    return out


CHARTS = (
    DailyMetric("ratings", N_("Ratings"), N_("Ratings and time"),
                _ratings_series, _ratings_rows, percent=True, card_types=_CARD_TYPES),
    DailyMetric("review_speed", N_("Review Speed"), N_("Ratings and time"),
                _speed_series, _speed_rows, unit="seconds", card_types=_CARD_TYPES),
    DailyMetric("forgotten", N_("Forgotten"), N_("Ratings and time"),
                _forgotten_series, _forgotten_rows, unit="lapses", cumulative=True, percent=True),
    # The cards reset to new (Forget) each day, by what they were before.
    DailyMetric("resets", N_("Reset Cards"), N_("Card history"),
                _reset_series, _reset_rows, unit="cards", cumulative=True, percent=True, source=_limit_source),
    # Introduced cards (new cards studied) per day; "By First Rating": the same cards by the
    # answer given the first time.
    DailyMetric("introduced", N_("Introduced"), N_("Ratings and time"),
                _introduced_series, _introduced_rows, unit="cards", cumulative=True, percent=True,
                source=_introduced_source, alt=(N_("By First Rating"), _ratings_series)),
    # The load (reviews a day, 1 / interval) the cards introduced each day bring now: which
    # days of new cards still cost reviews.
    DailyMetric("introduced_load", N_("Introduced Load"), N_("Load and due"),
                _introduced_load_series, _introduced_load_rows, unit="load", cumulative=True,
                source=_introduced_load_source, average=False),
    # The load of the whole deck on each past day (reviews a day, 1 / interval of each review
    # card at the end of the day), young / mature: how the daily work the cards ask for grew.
    # A level, as Card Counts over Time.
    DailyMetric("load_trend", N_("Load Trend"), N_("Load and due"),
                _introduced_load_series, _load_trend_rows, unit="level", percent=True,
                source=_load_trend_source, average=False, value="load", variation=True),
    # The average FSRS stability of the cards on each past day, from Anki's own memory states
    # after each review. A level.
    # Mean / Median (the header's pill), the bar split by the share of young / mature cards.
    DailyMetric("stability_trend", N_("Average Stability over Time"), N_("Card history"),
                _introduced_load_series, _stability_rows, unit="level", percent=True,
                source=_stability_source, average=False, value="days", measures=("mean", "median"), variation=True),
    # How many cards were known on each past day: the sum over the cards of their probability of
    # recall then (FSRS, Anki's own memory states). A level.
    # Its views (the header's pill): fsrs_history.MEMORISED_MEASURES.
    DailyMetric("memorised", N_("Memorised"), N_("Card history"),
                _memorised_series, _memorised_rows, unit="level",
                source=_memorised_source, average=False, measures=("cards", "notes", "average", "load", "stable"), variation=True),
    # The review answers of the period by the recall FSRS predicted before them, passed / failed:
    # with "Show as %", how well the predictions held.
    DailyMetric("fsrs_calibration", N_("FSRS Calibration"), N_("Ratings and time"),
                _passed_series, _calibration_rows, percent=True, source=_fsrs_cards_source,
                average=False, by_day=False, share_stats=True),
    # The review answers of the period by the days since the last review over the stability then,
    # passed / failed, with the share FSRS expected to fail marked on each bar: with "Show as %",
    # the forgetting curve of the answers (the first-answer curves are first_forgetting /
    # first_forgetting_short; the type keeps its old name for saved widgets).
    DailyMetric("forgetting_curve", N_("Recall by Elapsed / Stability"), N_("Ratings and time"),
                _passed_series, _forgetting_rows, percent=True, source=_fsrs_cards_source,
                average=False, by_day=False, share_stats=True),
    # How far FSRS's predictions are off by the place of the answer in its day (the 1st review of
    # the day, the 2nd...): the RMSE of the share passed against the recall predicted (Search Stats
    # Extended's FSRS Loss by Fatigue). Useful to set a daily review limit.
    DailyMetric("fsrs_fatigue", N_("FSRS Loss by Fatigue"), N_("Ratings and time"),
                _loss_series, _fatigue_loss_rows, unit="rmse", source=_fsrs_cards_source,
                average=False, by_day=False, card_types=("all", "young", "mature")),
    # The cards by how unlikely their lapses are given the recall FSRS predicted before each
    # answer: a click opens them in the browser.
    DailyMetric("leech_detector", N_("Leech Detector"), N_("Card history"),
                _leech_series, _leech_rows, unit="cards", source=_leech_source,
                average=False, by_day=False, has_span=False),
    # The cards by how much a Good on their due day would grow their stability (Search Stats
    # Extended's Ease Factors): a click opens them in the browser.
    DailyMetric("stability_increase", N_("Stability Increase Factor"), N_("Card history"),
                _sinc_series, _sinc_rows, unit="cards", source=_sinc_source,
                average=False, by_day=False, has_span=False),
    # The reviews of the cards of the user's own searches, a
    # series each; their time in the Time view (the chart's options icon)
    DailyMetric("custom_bar", N_("Custom Bar"), N_("Ratings and time"),
                _custom_bar_series, _custom_bar_rows, source=_custom_bar_source, cumulative=True, percent=True),
    # The cards due each day ahead, by the recall FSRS expects then: with "Show as %" (on by
    # default), the retention to expect.
    DailyMetric("future_retention", N_("Future Due Retention"), N_("Card history"),
                _predicted_series, _future_retention_rows, unit="cards", percent=True,
                source=_future_retention_source, average=False, by_day=False, share_stats=True,
                has_span=False),
    # The reviews of the period by the time spent on the answer, by rating ("By Card Type": by
    # learning / young / mature); "Show as %": how the answers go with the time taken.
    DailyMetric("answer_time", N_("Answer Time"), N_("Ratings and time"),
                _ratings_series, _answer_time_rows, percent=True, source=_limit_source,
                alt=(N_("By Card Type"), _types_series), average=False, by_day=False, share_stats=True,
                card_types=_CARD_TYPES),
    # The reviews of the period by the card's interval before the answer, by rating; with
    # "Show as %" the share of Again at each interval.
    DailyMetric("interval_ratings", N_("Rating by Interval"), N_("Ratings and time"),
                _ratings_series, _interval_rows, percent=True, source=_limit_source,
                average=False, by_day=False, share_stats=True, card_types=("all", "young", "mature")),  # (no interval in days in learning)
    # The reviews of the period by their place in the day (the 1st review of the day, the 2nd...),
    # by rating; with "Show as %" the share of Again as the day's reviews add up (Search Stats
    # Extended's Rating Fatigue).
    DailyMetric("rating_fatigue", N_("Rating Fatigue"), N_("Ratings and time"),
                _ratings_series, _fatigue_rows, percent=True, source=_limit_source,
                average=False, by_day=False, share_stats=True, card_types=_CARD_TYPES),
    # The review answers of the period by the days since a sibling (another card of the same note)
    # was last answered, by rating; with "Show as %" whether a sibling seen lately makes the
    # answer easier.
    DailyMetric("sibling_ratings", N_("Rating by Sibling Gap"), N_("Ratings and time"),
                _ratings_series, _sibling_rows, percent=True, source=_limit_source,
                average=False, by_day=False, share_stats=True),
    # How many cards were new / learning / relearning / young / mature on each past day (a
    # state at the end of the day, not a count of the day: bins show their last day).
    DailyMetric("card_states", N_("Card Counts over Time"), N_("Card history"),
                _card_total_series, _card_states_rows, unit="level", percent=True,
                source=_card_states_source, average=False, variation=True,
                alt=(N_("Breakdown by Type"), _card_states_series)),
)
BY_TYPE = {m.widget_type: m for m in CHARTS}


