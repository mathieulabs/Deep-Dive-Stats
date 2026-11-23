# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""The reviews of a period counted by answer time, by interval or by their place in the day,
with their rating (the charts Answer Time, Rating by Interval and Rating Fatigue,
charts.daily_metrics), or by weekday and hour (Week by Hour, charts.week_hours), and the
time spent on each rating day by day (Ratings' Time view).

The period comes from the day rows the chart already has (the same as its other charts);
each count is one grouped query, kept until the review history changes."""

import threading
from datetime import datetime, timedelta

from aqt import mw

from ..history_provider import HistoryProvider

_CACHE = {}
_LOCK = threading.Lock()
_MAX = 24

MAX_SECONDS = 60  # answers of a minute or more in the last bar (Anki caps them at 60 s by default)
MAX_INTERVAL = 3650
MAX_POSITION = 1000  # the 1000th review of a day and the ones after it in the last bar


def did_limit(addon_config, deck_id, is_deleted):
    if is_deleted:
        return "AND (CASE WHEN cards.odid > 0 THEN cards.odid ELSE cards.did END) IS NULL"
    return HistoryProvider._get_did_limit(addon_config, deck_id)


def range_from_days(days):
    """(start ms, end ms) of the day rows (days, or bins of minutes for Today / Yesterday)."""
    from .. import rollover_hour

    dates = sorted({str(d.get("logical_date") or d.get("date") or "")[:10] for d in days or []} - {""})
    if not dates:
        return None
    roll = int(rollover_hour() or 0)
    first = datetime.strptime(dates[0], "%Y-%m-%d") + timedelta(hours=roll)
    last = datetime.strptime(dates[-1], "%Y-%m-%d") + timedelta(days=1, hours=roll)
    return int(first.timestamp() * 1000), int(last.timestamp() * 1000)


def _memo(key, compute):
    try:
        from .revlog_stamp import revlog_stamp

        stamp = revlog_stamp()  # (kept: one read of the history for all the charts)
    except Exception:
        stamp = None
    full = (key, stamp, id(mw.col))
    if stamp is not None:
        with _LOCK:
            hit = _CACHE.get(full)
        if hit is not None:
            return hit
    value = compute()
    if stamp is not None:
        with _LOCK:
            if len(_CACHE) >= _MAX:
                _CACHE.clear()
            _CACHE[full] = value
    return value


def _join(limit, excl=""):
    # The cards only when a deck is chosen or a deck-specific excluded-day rule references cards.*
    return "LEFT JOIN cards ON revlog.cid = cards.id" if ((limit or "").strip() or "cards." in (excl or "")) else ""
# Learning (and relearning) / young / mature, by the review's type and its interval before it.
_KIND = ("CASE WHEN revlog.type IN (0, 2) OR revlog.lastIvl <= 0 THEN 0 "
         "WHEN revlog.lastIvl >= 21 THEN 2 ELSE 1 END")
# A chart's card type filter: the kinds of _KIND it keeps (None: all).
_KIND_SETS = {"all": None, "learn": (0,), "young": (1,), "mature": (2,), "review": (1, 2)}


def kinds_of(card_type):
    """The card kinds (0 learning, 1 young, 2 mature) a card type filter keeps; None: all."""
    return _KIND_SETS.get(card_type or "all")


def _kinds_sql(kinds, kind=_KIND):
    return f" AND {kind} IN ({', '.join(str(int(k)) for k in kinds)})" if kinds else ""


def _excl():
    from ....utils import excluded_days_clause

    return excluded_days_clause()


def answer_time_counts(limit, start_ms, end_ms):
    """{(seconds, rating 1-4, kind 0 learning / 1 young / 2 mature): reviews}."""
    excl = _excl()

    def compute():
        rows = mw.col.db.all(f"""
            SELECT MIN(revlog.time / 1000, {MAX_SECONDS}) AS s, revlog.ease, {_KIND} AS k, COUNT(*)
            FROM revlog {_join(limit, excl)}
            WHERE revlog.id >= {int(start_ms)} AND revlog.id < {int(end_ms)}
              AND revlog.type < 4 AND revlog.ease BETWEEN 1 AND 4 {excl} {limit}
            GROUP BY s, revlog.ease, k
        """)
        return {(int(s or 0), int(e), int(k)): int(n) for s, e, k, n in rows}

    return _memo(("time", limit, start_ms, end_ms, excl), compute)


def interval_rating_counts(limit, start_ms, end_ms, kinds=None):
    """{(interval in days before the answer, rating 1-4): reviews} of review cards (the
    answers in learning steps, without an interval in days, are left out); kinds: only those
    card kinds (kinds_of)."""
    excl = _excl()

    def compute():
        rows = mw.col.db.all(f"""
            SELECT MIN(revlog.lastIvl, {MAX_INTERVAL}) AS i, revlog.ease, COUNT(*)
            FROM revlog {_join(limit, excl)}
            WHERE revlog.id >= {int(start_ms)} AND revlog.id < {int(end_ms)}
              AND revlog.type < 4 AND revlog.ease BETWEEN 1 AND 4 AND revlog.lastIvl >= 1{_kinds_sql(kinds)} {excl} {limit}
            GROUP BY i, revlog.ease
        """)
        return {(int(i), int(e)): int(n) for i, e, n in rows}

    return _memo(("ivl", limit, start_ms, end_ms, tuple(kinds or ()), excl), compute)


def fatigue_counts(limit, start_ms, end_ms, kinds=None):
    """Rating Fatigue: {(place of the review in its day, rating 1-4): reviews}.
    The place counts every review of the day (Anki's day), whatever its deck: the 50th review of
    a day is as tiring in any deck; the deck (and kinds: the card kinds, kinds_of) only picks which
    reviews are counted."""
    cutoff = int(mw.col.sched.day_cutoff)
    base = cutoff - 86400 * 40000  # days counted from far back: the division stays on positive numbers
    excl = _excl()

    def compute():
        inner_join = "LEFT JOIN cards ON revlog.cid = cards.id" if "cards." in (excl or "") else ""
        cards = "LEFT JOIN cards ON r.cid = cards.id" if (limit or "").strip() else ""
        rows = mw.col.db.all(f"""
            SELECT MIN(r.n, {MAX_POSITION}) AS p, r.ease, COUNT(*)
            FROM (SELECT revlog.cid AS cid, revlog.ease AS ease, {_KIND} AS k,
                         ROW_NUMBER() OVER (PARTITION BY (revlog.id / 1000 - {base}) / 86400 ORDER BY revlog.id) AS n
                  FROM revlog {inner_join}
                  WHERE revlog.id >= {int(start_ms)} AND revlog.id < {int(end_ms)}
                    AND revlog.type < 4 AND revlog.ease BETWEEN 1 AND 4 {excl}) AS r
            {cards}
            WHERE 1 = 1{_kinds_sql(kinds, "r.k")} {limit}
            GROUP BY p, r.ease
        """)
        return {(int(p), int(e)): int(n) for p, e, n in rows}

    return _memo(("fatigue", limit, int(start_ms), int(end_ms), cutoff, tuple(kinds or ()), excl), compute)


def reset_events(limit, start_ms, end_ms):
    """Reset Cards: the resets (Forget: a manual entry without
    interval or ease factor, as card_states._manual_state) of the period, [(id in ms, kind 0
    learning / 1 young / 2 mature)]: the card before it, by the interval of its entry before (none
    or not in days: learning)."""
    excl = _excl()

    def compute():
        rows = mw.col.db.all(f"""
            SELECT revlog.id, (SELECT p.ivl FROM revlog AS p WHERE p.cid = revlog.cid AND p.id < revlog.id
                               ORDER BY p.id DESC LIMIT 1)
            FROM revlog {_join(limit, excl)}
            WHERE revlog.id >= {int(start_ms)} AND revlog.id < {int(end_ms)}
              AND revlog.type = 4 AND revlog.factor = 0 AND revlog.ivl = 0 {excl} {limit}
        """)
        return [(int(rid), 2 if (ivl or 0) >= 21 else (1 if (ivl or 0) > 0 else 0)) for rid, ivl in rows]

    return _memo(("reset", limit, int(start_ms), int(end_ms), excl), compute)


def week_hour_counts(limit, start_ms, end_ms):
    """{(weekday 0 Monday .. 6 Sunday, hour 0-23): reviews} by the clock of this computer
    (the answers of the period; manual entries such as a due date set left out)."""
    excl = _excl()

    def compute():
        rows = mw.col.db.all(f"""
            SELECT CAST(strftime('%w', revlog.id / 1000, 'unixepoch', 'localtime') AS INTEGER) AS wd,
                   CAST(strftime('%H', revlog.id / 1000, 'unixepoch', 'localtime') AS INTEGER) AS h,
                   COUNT(*)
            FROM revlog {_join(limit, excl)}
            WHERE revlog.id >= {int(start_ms)} AND revlog.id < {int(end_ms)}
              AND revlog.type < 4 AND revlog.ease BETWEEN 1 AND 4 {excl} {limit}
            GROUP BY wd, h
        """)
        # strftime('%w'): 0 is Sunday; date.weekday(): 0 is Monday.
        return {((int(wd) + 6) % 7, int(h)): int(n) for wd, h, n in rows}

    return _memo(("week", limit, start_ms, end_ms, excl), compute)


def day_hour_counts(limit, start_ms, end_ms):
    """{(day 'YYYY-MM-DD', hour 0-23): reviews} (Week by Hour's By Day view). The day is Anki's (it
    starts at the rollover hour), the hour the clock's: a review at 1:00 is in the evening before."""
    from .. import rollover_hour

    roll = int(rollover_hour() or 0) * 3600
    excl = _excl()

    def compute():
        rows = mw.col.db.all(f"""
            SELECT strftime('%Y-%m-%d', revlog.id / 1000 - {roll}, 'unixepoch', 'localtime') AS d,
                   CAST(strftime('%H', revlog.id / 1000, 'unixepoch', 'localtime') AS INTEGER) AS h,
                   COUNT(*)
            FROM revlog {_join(limit, excl)}
            WHERE revlog.id >= {int(start_ms)} AND revlog.id < {int(end_ms)}
              AND revlog.type < 4 AND revlog.ease BETWEEN 1 AND 4 {excl} {limit}
            GROUP BY d, h
        """)
        return {(str(d), int(h)): int(n) for d, h, n in rows}

    return _memo(("dayhour", limit, start_ms, end_ms, roll, excl), compute)


def rating_times(limit, start_ms, end_ms, minutes=False, kinds=None):
    """Ratings by Duration: the time spent on the answers of each rating,
    {(day 'YYYY-MM-DD' of Anki (it starts at the rollover hour), rating 1-4): ms}; minutes=True
    (Today / Yesterday, rows of minutes): {(minute since 1970, rating 1-4): ms}. kinds: only those
    card kinds (kinds_of)."""
    from .. import rollover_hour

    roll = int(rollover_hour() or 0) * 3600
    excl = _excl()
    if minutes:
        key = "revlog.id / 60000"
    else:
        key = f"strftime('%Y-%m-%d', revlog.id / 1000 - {roll}, 'unixepoch', 'localtime')"

    def compute():
        rows = mw.col.db.all(f"""
            SELECT {key} AS d, revlog.ease, SUM(revlog.time)
            FROM revlog {_join(limit, excl)}
            WHERE revlog.id >= {int(start_ms)} AND revlog.id < {int(end_ms)}
              AND revlog.type < 4 AND revlog.ease BETWEEN 1 AND 4{_kinds_sql(kinds)} {excl} {limit}
            GROUP BY d, revlog.ease
        """)
        return {(int(d) if minutes else str(d), int(e)): int(ms or 0) for d, e, ms in rows}

    return _memo(("ratingtime", limit, start_ms, end_ms, roll, bool(minutes), tuple(kinds or ()), excl), compute)


def first_answers(limit, start_ms, end_ms):
    """Today's Retention, over any period: the first answer of each card on
    each day of Anki (a card answered on 3 days counts 3 times, its other answers of a day not at all),
    {(kind 0 learning / 1 young / 2 mature, passed 0/1): answers}."""
    cutoff = int(mw.col.sched.day_cutoff)
    base = cutoff - 86400 * 40000  # days counted from far back: the division stays on positive numbers
    excl = _excl()

    def compute():
        # SQLite guarantees bare columns in a GROUP BY with a single MIN() come from the minimizing row:
        # avoids scanning the whole collection in a subquery and eliminates the self-join back to revlog.
        rows = mw.col.db.all(f"""
            SELECT k, ok, COUNT(*) FROM (
                SELECT MIN(revlog.id), {_KIND} AS k, revlog.ease > 1 AS ok
                FROM revlog {_join(limit, excl)}
                WHERE revlog.id >= {int(start_ms)} AND revlog.id < {int(end_ms)}
                  AND revlog.type < 4 AND revlog.ease BETWEEN 1 AND 4 {excl} {limit}
                GROUP BY revlog.cid, (revlog.id / 1000 - {base}) / 86400
            )
            GROUP BY k, ok
        """)
        return {(int(k), int(ok)): int(n) for k, ok, n in rows}

    return _memo(("first", limit, int(start_ms), int(end_ms), cutoff, excl), compute)


