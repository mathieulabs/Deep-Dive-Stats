# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""The reviews of a period counted by answer time or by interval, with their rating (the
charts Answer Time and Rating by Interval, charts.daily_metrics), or by weekday and hour
(Week by Hour, charts.week_hours).

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
        stamp = tuple(mw.col.db.first("SELECT max(id), count() FROM revlog") or ())
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


def _join(limit):
    # The cards only when a deck is chosen (the whole collection: the reviews alone, faster).
    return "LEFT JOIN cards ON revlog.cid = cards.id" if (limit or "").strip() else ""
# Learning (and relearning) / young / mature, by the review's type and its interval before it.
_KIND = ("CASE WHEN revlog.type IN (0, 2) OR revlog.lastIvl <= 0 THEN 0 "
         "WHEN revlog.lastIvl >= 21 THEN 2 ELSE 1 END")


def answer_time_counts(limit, start_ms, end_ms):
    """{(seconds, rating 1-4, kind 0 learning / 1 young / 2 mature): reviews}."""
    def compute():
        rows = mw.col.db.all(f"""
            SELECT MIN(revlog.time / 1000, {MAX_SECONDS}) AS s, revlog.ease, {_KIND} AS k, COUNT(*)
            FROM revlog {_join(limit)}
            WHERE revlog.id >= {int(start_ms)} AND revlog.id < {int(end_ms)}
              AND revlog.type < 4 AND revlog.ease BETWEEN 1 AND 4 {limit}
            GROUP BY s, revlog.ease, k
        """)
        return {(int(s or 0), int(e), int(k)): int(n) for s, e, k, n in rows}

    return _memo(("time", limit, start_ms, end_ms), compute)


def interval_rating_counts(limit, start_ms, end_ms):
    """{(interval in days before the answer, rating 1-4): reviews} of review cards (the
    answers in learning steps, without an interval in days, are left out)."""
    def compute():
        rows = mw.col.db.all(f"""
            SELECT MIN(revlog.lastIvl, {MAX_INTERVAL}) AS i, revlog.ease, COUNT(*)
            FROM revlog {_join(limit)}
            WHERE revlog.id >= {int(start_ms)} AND revlog.id < {int(end_ms)}
              AND revlog.type < 4 AND revlog.ease BETWEEN 1 AND 4 AND revlog.lastIvl >= 1 {limit}
            GROUP BY i, revlog.ease
        """)
        return {(int(i), int(e)): int(n) for i, e, n in rows}

    return _memo(("ivl", limit, start_ms, end_ms), compute)


def week_hour_counts(limit, start_ms, end_ms):
    """{(weekday 0 Monday .. 6 Sunday, hour 0-23): reviews} by the clock of this computer
    (the answers of the period; manual entries such as a due date set left out)."""
    def compute():
        rows = mw.col.db.all(f"""
            SELECT CAST(strftime('%w', revlog.id / 1000, 'unixepoch', 'localtime') AS INTEGER) AS wd,
                   CAST(strftime('%H', revlog.id / 1000, 'unixepoch', 'localtime') AS INTEGER) AS h,
                   COUNT(*)
            FROM revlog {_join(limit)}
            WHERE revlog.id >= {int(start_ms)} AND revlog.id < {int(end_ms)}
              AND revlog.type < 4 AND revlog.ease BETWEEN 1 AND 4 {limit}
            GROUP BY wd, h
        """)
        # strftime('%w'): 0 is Sunday; date.weekday(): 0 is Monday.
        return {((int(wd) + 6) % 7, int(h)): int(n) for wd, h, n in rows}

    return _memo(("week", limit, start_ms, end_ms), compute)
