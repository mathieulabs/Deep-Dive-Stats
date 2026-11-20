# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt import mw
from .. import Period
from ..fsrs_math import curve_known
from ..history_provider import HistoryProvider


def build_future_due_payload(distribution, time_span=Period.TOTAL, addon_config=None, backlog_count=None):
    normalized = {}
    for day_key, count in (distribution or {}).items():
        try:
            day_idx = int(day_key)
        except Exception:
            continue
        normalized[day_idx] = normalized.get(day_idx, 0) + int(count or 0)

    max_days = 31  # default 1 month
    if isinstance(time_span, int) and 1000 <= time_span <= 9999:
        max_days = time_span - 1000  # n days, see widgets/common/future_due_filters.py
    elif time_span == Period.THREE_MONTHS:
        max_days = 90
    elif time_span == Period.YEAR:
        max_days = 365
    elif time_span == Period.TOTAL:
        # Dynamic: use max scheduled day, cap at 10 years.
        if normalized:
            valid_keys = [k for k in normalized.keys() if k >= 0]
            max_days = max(valid_keys) if valid_keys else 365
            max_days = min(max_days, 365 * 10)
        else:
            max_days = 365
    elif time_span == Period.CUSTOM:
        config = getattr(addon_config, "config", {}) if addon_config is not None else {}
        max_days = config.get("custom_days", 90)

    filtered = {k: v for k, v in normalized.items() if k <= max_days}
    if backlog_count is None:
        backlog_count = sum(v for k, v in filtered.items() if k < 0)

    total_due = sum(v for k, v in filtered.items() if k >= 0)
    days_in_span = max(1, max_days)
    avg_due = total_due / days_in_span
    due_tomorrow = filtered.get(1, 0)

    return {
        "distribution": filtered,
        "total": total_due,
        "average": avg_due,
        "tomorrow": due_tomorrow,
        "max_days": max_days,
        "backlog": backlog_count,
    }


def due_day_sql():
    """(day expression, condition) of the cards counted in Future Due, as in Anki's own
    graph (rslib stats/graphs/future_due.rs): every card that is not new or suspended, by
    its due (the original one in a filtered deck), learning cards included; day 0 is today,
    below 0 overdue. Buried cards only count on a later day. For cards AS cards."""
    sched = mw.col.sched
    today, cutoff = int(sched.today), int(sched.day_cutoff)
    due = "(CASE WHEN cards.odid != 0 THEN cards.odue ELSE cards.due END)"
    # A learning card's due is a timestamp: whole days from the next day's start, rounded
    # toward 0 (SQLite's integer division, like Rust's), so later today is day 0.
    day = f"(CASE WHEN {due} > 1000000000 THEN ({due} - {cutoff}) / 86400 ELSE {due} - {today} END)"
    cond = f"cards.type != 0 AND cards.queue != -1 AND NOT (cards.queue IN (-2, -3) AND {day} <= 0)"
    return day, cond


def _due_by_type(did_limit):
    """{day from today: [learning, young, mature]} of the cards due (overdue below 0).
    Learning and relearning cards are "learning", the others young or mature by interval."""
    day, cond = due_day_sql()
    rows = mw.col.db.all(
        f"SELECT {day} AS d, "
        "CASE WHEN cards.type IN (1, 3) THEN 0 WHEN cards.ivl >= 21 THEN 2 ELSE 1 END AS k, COUNT(*) "
        f"FROM cards AS cards WHERE {cond} {did_limit} GROUP BY d, k")
    out = {}
    for d, k, n in rows:
        if d is None or k is None:
            continue
        out.setdefault(int(d), [0, 0, 0])[int(k)] += int(n)
    return out


_RET_CACHE = {}


def _expected_retention(did_limit, include_backlog):
    """Kept until a card changes or the day turns (reading every FSRS card's data is the slow
    part: a fraction of a second on a large collection)."""
    try:
        fp = tuple(mw.col.db.first("SELECT count(), max(mod), total(mod) FROM cards") or ())
    except Exception:
        fp = None
    key = (did_limit, bool(include_backlog), int(mw.col.sched.today), fp, id(mw.col))
    if fp is not None and key in _RET_CACHE:
        return _RET_CACHE[key]
    out = _read_expected_retention(did_limit, include_backlog)
    if fp is not None:
        if len(_RET_CACHE) > 16:
            _RET_CACHE.clear()
        _RET_CACHE[key] = out
    return out


def _read_expected_retention(did_limit, include_backlog):
    """{day from today: [sum of R, cards]}: the FSRS retrievability each card due that day
    will have then (the day it is due; an overdue card: today, when it can next be
    reviewed). Cards without a memory state are left out."""
    import time

    from ..fsrs_math import FSRS_CARD_COLS, memory_state, retrievability, seconds_since_last_review

    day, cond = due_day_sql()
    sched = mw.col.sched
    today, now = int(sched.today), int(time.time())
    rows = mw.col.db.all(
        f"SELECT {day} AS d, {FSRS_CARD_COLS} FROM cards AS cards "
        f"WHERE {cond} AND cards.data IS NOT NULL AND cards.data != '' {did_limit}")
    out = {}
    for d, data, due, odue, odid, ivl, queue, ctype in rows:
        if d is None or (d < 0 and not include_backlog):
            continue
        mem = memory_state(data)
        if mem is None:
            continue
        s, _d, decay, lrt = mem
        elapsed = seconds_since_last_review(lrt, due, odue, odid, ivl, queue, ctype, today, now)
        # Days from now until the card is due (an overdue one: now).
        elapsed += max(0, int(d)) * 86400
        r = retrievability(elapsed / 86400.0, s, decay)
        acc = out.setdefault(int(d), [0.0, 0])
        acc[0] += r
        acc[1] += 1
    return out


def due_today_by_hour(addon_config, deck_id=None, is_deleted=False):
    """The learning cards due today (Anki's intraday learning queue), by hour of the day from
    the day's start (the rollover): {"rows": 24 rows {"pretty_date": "14:00", "learn",
    "relearn"}, "total", "due_now", "later", "next_due" (timestamp or None), "now_slot",
    "start" (the day's start, a timestamp)}.

    A card due before the day's start is in the first hour, and so are the learning cards
    due today by day (steps of a day or more): Anki shows them the whole day. "Due now"
    counts the cards Anki already shows (its learn ahead limit included), "later" the others."""
    import time
    from datetime import datetime

    if is_deleted:
        did_limit = "AND (CASE WHEN cards.odid > 0 THEN cards.odid ELSE cards.did END) IS NULL"
    else:
        did_limit = HistoryProvider._get_did_limit(addon_config, deck_id)
    cutoff = int(mw.col.sched.day_cutoff)
    start = cutoff - 86400
    now = int(time.time())
    try:
        ahead = int(mw.col.get_config("collapseTime", 1200) or 0)
    except Exception:
        ahead = 1200
    rows = [{"pretty_date": datetime.fromtimestamp(start + h * 3600).strftime("%H:00"), "learn": 0, "relearn": 0}
            for h in range(24)]
    due_now = later = 0
    next_due = None
    today = int(mw.col.sched.today)
    for ctype, n in mw.col.db.all(
            f"SELECT cards.type, COUNT(*) FROM cards AS cards WHERE cards.queue = 3 AND cards.due <= {today} "
            f"{did_limit} GROUP BY cards.type"):
        rows[0]["relearn" if ctype == 3 else "learn"] += int(n)
        due_now += int(n)
    for due, ctype in mw.col.db.all(
            f"SELECT cards.due, cards.type FROM cards AS cards WHERE cards.queue = 1 AND cards.due < {cutoff} {did_limit}"):
        due = int(due or 0)
        slot = min(23, max(0, (due - start) // 3600))
        rows[slot]["relearn" if ctype == 3 else "learn"] += 1
        if due <= now + ahead:
            due_now += 1
        else:
            later += 1
            next_due = due if next_due is None else min(next_due, due)
    return {"rows": rows, "total": due_now + later, "due_now": due_now, "later": later,
            "next_due": next_due, "now_slot": min(23, max(0, (now - start) // 3600)), "start": start}


# Breakdowns of the bars (each part bottom to top): "type" (mature, young, learning) and
# "result" (FSRS predicted pass, predicted fail, cards without FSRS memory state).
BREAKDOWNS = ("type", "result")


def resolve_breakdown(mode, legacy_show_breakdown=False):
    """The breakdown saved in a chart's settings ("breakdown"; an older "show_breakdown"
    box meant by type), or None."""
    if mode in BREAKDOWNS:
        return mode
    return "type" if (mode is None and legacy_show_breakdown) else None


class FutureDueDataProvider:
    @staticmethod
    def fetch_data(addon_config, deck_id=None, is_deleted=False, time_span=Period.TOTAL, include_backlog=False,
                   breakdown=None, hidden_parts=()):
        """
        Fetches the cards due by day from today, counted as in Anki's Future Due graph.

        breakdown ("type" or "result", see BREAKDOWNS): also "breakdown" ({"kind", "days":
        {day: (bottom, middle, top)}}), the same cards split in three (the bars and totals
        stay the same). "result" also gives "retention" ({day: (sum of R, FSRS cards)}): the
        retrievability each card will have the day it is due (see _expected_retention), its
        sum being the reviews FSRS expects you to pass.
        hidden_parts: with the breakdown by type, the types left out ("learn", "young",
        "mature"; right click > Series): gone from the bars and the totals.
        """
        if is_deleted:
            did_limit = "AND (CASE WHEN cards.odid > 0 THEN cards.odid ELSE cards.did END) IS NULL"
        else:
            did_limit = HistoryProvider._get_did_limit(addon_config, deck_id)

        counts = _due_by_type(did_limit)
        hidden = set(hidden_parts or ()) if breakdown == "type" else set()
        if hidden:
            idx = {"learn": 0, "young": 1, "mature": 2}
            for c in counts.values():
                for name in hidden:
                    if name in idx:
                        c[idx[name]] = 0
        by_day = {d: c for d, c in counts.items() if (include_backlog or d >= 0) and sum(c) > 0}
        payload = build_future_due_payload(
            {d: sum(c) for d, c in by_day.items()},
            time_span=time_span,
            addon_config=addon_config,
            backlog_count=sum(sum(c) for d, c in by_day.items() if d < 0),
        )
        shown = [d for d in payload["distribution"] if d in by_day]
        if breakdown == "type":
            days = {d: (by_day[d][2], by_day[d][1], by_day[d][0]) for d in shown}
            payload["breakdown"] = {"kind": "type", "days": days}
        elif breakdown == "result" and curve_known():  # (another FSRS: no retention, see fsrs_math)
            ret = _expected_retention(did_limit, include_backlog)
            days = {}
            for d in shown:
                r_sum, n = ret.get(d, (0.0, 0))
                days[d] = (r_sum, n - r_sum, max(0, sum(by_day[d]) - n))
            payload["breakdown"] = {"kind": "result", "days": days}
            payload["retention"] = {d: tuple(ret[d]) for d in shown if d in ret}
        return payload
