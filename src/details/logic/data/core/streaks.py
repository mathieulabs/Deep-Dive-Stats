# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Streak calculation utilities for deck statistics."""

from .....utils import excluded_days_clause
import time
from aqt import mw
from .empty_deck import did_limit_has_no_cards
from .revlog_slices import scan_slices, sliced_all
from ... import REVLOG_RESCHED, sql_id_list
from .....utils import get_logical_day_sql, logical_day_number

_streak_cache = {}  # key -> (timestamp, result)
_all_streaks_cache = {}  # did_limit -> (timestamp, result)
_STREAK_CACHE_TTL = 5  # seconds


def _cache_key(deck_id, start_ms, end_ms, excluded_dids):
    return (deck_id, start_ms, end_ms, tuple(excluded_dids) if excluded_dids else ())


def logical_today():
    """Today's date as Anki sees it: before the rollover hour it is still the previous day."""
    from datetime import datetime, timedelta
    from .....utils import rollover_hour

    now = datetime.now()
    if now.hour < rollover_hour():
        now -= timedelta(days=1)
    return now.date()


def current_streak_from_dates(dates):
    """Current streak from logical dates ("YYYY-MM-DD") that have reviews.

    Counts back from today, or from yesterday while today has no review yet, using the
    rollover hour for what "today" is.
    """
    from datetime import timedelta

    # Compare ISO strings, so only the few days of the streak are ever turned into dates.
    days = {str(d)[:10] for d in (dates or ()) if d}
    if not days:
        return 0
    day = logical_today()
    if day.isoformat() not in days:
        day -= timedelta(days=1)
    streak = 0
    while day.isoformat() in days:
        streak += 1
        day -= timedelta(days=1)
    return streak


def _compute_streaks_from_days(days, end_ms):
    """Pure Python streak computation from a sorted (DESC) list of day indices."""
    if not days:
        return 0, 0

    last_day_idx = logical_day_number(end_ms)

    current_streak = 0
    if days[0] == last_day_idx or days[0] == last_day_idx - 1:
        current_streak = 1
        last_day = days[0]
        for day in days[1:]:
            if day == last_day - 1:
                current_streak += 1
                last_day = day
            else:
                break

    temp_streak = 1
    longest_streak = 1
    for i in range(len(days) - 1):
        if days[i] == days[i + 1] + 1:
            temp_streak += 1
        else:
            longest_streak = max(longest_streak, temp_streak)
            temp_streak = 1
    longest_streak = max(longest_streak, temp_streak)

    return current_streak, longest_streak


def get_deck_streaks(deck_id, start_ms=0, end_ms=None, excluded_dids=None):
    """
    Calculates current and longest streak for a deck within a time range.
    If end_ms is None, uses current time.
    Returns: (current_streak, longest_streak) tuple of integers.
    """
    if end_ms is None:
        end_ms = int(time.time() * 1000)

    key = _cache_key(deck_id, start_ms, end_ms, excluded_dids)
    now = time.time()
    if key in _streak_cache:
        ts, result = _streak_cache[key]
        if now - ts < _STREAK_CACHE_TTL:
            return result

    if deck_id is not None:
        dids = mw.col.decks.deck_and_child_ids(deck_id)
        did_limit = f"AND (CASE WHEN cards.odid > 0 THEN cards.odid ELSE cards.did END) IN {sql_id_list(dids)}"
    else:
        from .....utils import excluded_not_in_clause
        did_limit = excluded_not_in_clause(excluded_dids)

    if did_limit_has_no_cards(did_limit):
        days = []
    else:
        slices = scan_slices(start_ms, end_ms)
        rows = sliced_all(lambda part: f"""
            SELECT DISTINCT {get_logical_day_sql("(CASE WHEN revlog.id > 1000000000000 THEN revlog.id ELSE revlog.id * 1000 END)")}
            FROM revlog
            LEFT JOIN cards ON revlog.cid = cards.id
            WHERE revlog.type < {REVLOG_RESCHED}
            AND (CASE WHEN revlog.id > 1000000000000 THEN revlog.id ELSE revlog.id * 1000 END) >= {start_ms}
            AND (CASE WHEN revlog.id > 1000000000000 THEN revlog.id ELSE revlog.id * 1000 END) < {end_ms}
            {did_limit} {excluded_days_clause()} {part}
        """, slices, 1)
        days = sorted((r[0] for r in rows), reverse=True)
    result = _compute_streaks_from_days(days, end_ms)

    _streak_cache[key] = (now, result)
    return result


def get_all_deck_streaks(did_limit=""):
    """
    Bulk streak calculation: ONE SQL query for all decks, then compute streaks per-deck in Python.
    did_limit: pre-computed SQL AND clause for deck filtering (thread-safe).
    Returns: dict {did: (current_streak, longest_streak)}
    """
    now = time.time()
    cached = _all_streaks_cache.get(did_limit)
    if cached:
        ts, result = cached
        if now - ts < _STREAK_CACHE_TTL:
            return result

    end_ms = int(now * 1000)

    slices = scan_slices()
    rows = sliced_all(lambda part: f"""
        SELECT (CASE WHEN cards.odid > 0 THEN cards.odid ELSE cards.did END),
               {get_logical_day_sql("(CASE WHEN revlog.id > 1000000000000 THEN revlog.id ELSE revlog.id * 1000 END)")} as day_idx
        FROM revlog
        LEFT JOIN cards ON revlog.cid = cards.id
        WHERE revlog.type < {REVLOG_RESCHED}
        {did_limit} {excluded_days_clause()} {part}
        GROUP BY (CASE WHEN cards.odid > 0 THEN cards.odid ELSE cards.did END), day_idx
    """, slices, 2)
    rows.sort(key=lambda r: (r[0] is None, r[0] or 0, -r[1]))

    from collections import defaultdict
    did_days = defaultdict(list)
    for did, day_idx in rows:
        did_days[did].append(day_idx)

    streak_map = {}
    for did, days in did_days.items():
        # days are newest first (sorted above)
        streak_map[did] = _compute_streaks_from_days(days, end_ms)

    # Also compute collection-wide streak (all days merged) under "collection" key
    all_days = sorted(set(d for days in did_days.values() for d in days), reverse=True)
    streak_map["collection"] = _compute_streaks_from_days(all_days, end_ms)

    _all_streaks_cache[did_limit] = (now, streak_map)
    return streak_map

