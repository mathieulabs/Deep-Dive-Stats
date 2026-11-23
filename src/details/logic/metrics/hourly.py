# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from ....utils import excluded_days_clause
from aqt import mw
from .. import Period
from ..history_provider import HistoryProvider
from ..data.core.time_utils import get_time_range_ms
from ..logger import log_swallowed
from ..data.core.empty_deck import did_limit_has_no_cards

class HourlyDataProvider:
    @staticmethod
    def fetch_data(addon_config, deck_id=None, is_deleted=False, time_span=Period.TOTAL, override_start_ms=None, override_end_ms=None, custom_days=7, filtered=True):
        """
        Fetches review counts and success rates grouped by hour of the day.
        Returns: {hour: {"total": count, "correct": count}} for hours 0-23
        """
        if is_deleted:
            did_limit = "AND (CASE WHEN cards.odid > 0 THEN cards.odid ELSE cards.did END) IS NULL"
        else:
            did_limit = HistoryProvider._get_did_limit(addon_config, deck_id)

        if not filtered:  # the reviews of filtered decks (revlog type 3) left out: Include Filtered off
            did_limit += " AND revlog.type != 3"

        week_start = addon_config.config.get("week_start", 0)

        if override_start_ms is not None and override_end_ms is not None:
             start_ms, end_ms = override_start_ms, override_end_ms
        else:
             start_ms, end_ms, _, _ = get_time_range_ms(time_span, week_start=week_start, custom_days=custom_days)

        eff_end_ms = end_ms if (end_ms > 0 and (time_span != Period.TOTAL or override_end_ms is not None)) else 0
        time_limit = ""
        if start_ms > 0:
            time_limit += f" AND (CASE WHEN revlog.id > 1000000000000 THEN revlog.id ELSE revlog.id * 1000 END) >= {start_ms}"
        if eff_end_ms > 0:
            time_limit += f" AND (CASE WHEN revlog.id > 1000000000000 THEN revlog.id ELSE revlog.id * 1000 END) < {eff_end_ms}"

        # Summed in SQLite by slot of 15 minutes (an integer division), each slot's local hour read in Python: a
        # few thousand slots instead of a local time made for every review (strftime 'localtime' on ~100,000 rows
        # was most of the ~110 ms Deep Dive's opening waited for on the UI thread). 15 minutes: a slot lies in
        # one local hour for every time zone (offsets of :30 and :45 too), daylight saving time included.
        query = f"""
            SELECT (CASE WHEN revlog.id > 1000000000000 THEN revlog.id ELSE revlog.id * 1000 END) / 900000 AS slot,
                   COUNT(*),
                   SUM(CASE WHEN revlog.ease > 1 THEN 1 ELSE 0 END)
            FROM revlog
            LEFT JOIN cards ON revlog.cid = cards.id
            WHERE revlog.type < 4
            {did_limit} {excluded_days_clause()}
            {time_limit}
            GROUP BY slot
        """
        hours_data = {h: {"total": 0, "correct": 0} for h in range(24)}
        try:
            import datetime

            if did_limit_has_no_cards(did_limit):
                rows = []
            else:
                rows = _by_offset_period(did_limit + " " + excluded_days_clause(), start_ms=start_ms, end_ms=eff_end_ms)
                if rows is None:
                    rows = mw.col.db.all(query)
                else:
                    for off, quarter, total, correct in rows[0]:
                        h = ((int(quarter) * 900 + off) // 3600) % 24
                        hours_data[h]["total"] += int(total or 0)
                        hours_data[h]["correct"] += int(correct or 0)
                    rows = rows[1]  # the old reviews stamped in seconds, read slot by slot as before
            for slot, total, correct in rows:
                if slot is None:
                    continue
                h = datetime.datetime.fromtimestamp(int(slot) * 900).hour
                hours_data[h]["total"] += int(total or 0)
                hours_data[h]["correct"] += int(correct or 0)
        except Exception:
            import datetime
            rows = mw.col.db.all(f"""
                SELECT revlog.id, revlog.ease
                FROM revlog
                LEFT JOIN cards ON revlog.cid = cards.id
                WHERE revlog.type < 4
                {did_limit} {excluded_days_clause()}
                {time_limit}
            """)
            for rev_id, ease in rows:
                ts = rev_id / 1000.0 if rev_id > 1000000000000 else rev_id
                try:
                    h = datetime.datetime.fromtimestamp(ts).hour
                    hours_data[h]["total"] += 1
                    if ease > 1:
                        hours_data[h]["correct"] += 1
                except Exception:
                    log_swallowed()
        return hours_data






_PERIODS = {}  # {(first slot, last slot, time zone names): [(first slot, UTC offset in seconds)]}


def _offset(slot):
    import time

    return time.localtime(int(slot) * 900).tm_gmtoff


def _periods(first, last):
    """[(first slot, UTC offset)] of the stretches of one UTC offset from slot first to slot last
    (slots of 15 minutes; an offset changes on a slot's start): the daylight saving time changes,
    found day by day then to the slot."""
    import time

    key = (first, last, tuple(time.tzname))
    hit = _PERIODS.get(key)
    if hit is not None:
        return hit
    out = [(first, _offset(first))]
    s = first
    while s < last:
        n = min(s + 96, last)
        if _offset(n) != out[-1][1]:
            lo, hi = s, n
            while hi - lo > 1:
                m = (lo + hi) // 2
                if _offset(m) == out[-1][1]:
                    lo = m
                else:
                    hi = m
            out.append((hi, _offset(hi)))
        s = n
    if len(_PERIODS) > 8:
        _PERIODS.clear()
    _PERIODS[key] = out
    return out


def _by_offset_period(limits, start_ms=0, end_ms=0):
    """([(UTC offset, quarter of the UTC day 0-95, reviews, passed)], [(slot, reviews, passed)] of
    the reviews stamped in seconds) of the reviews matching limits; None when it can't be read so.

    Summed by quarter of the UTC day over each stretch of one UTC offset, read by its range of review
    ids: a few hundred rows instead of one per 15-minute slot reviewed (47,000 on 150,000 reviews,
    each given its local hour in Python), ~35 ms less, the hours the same."""
    try:
        join_cards = "LEFT JOIN cards ON revlog.cid = cards.id" if "cards." in limits else ""
        min_all, max_all = mw.col.db.first("SELECT min(id), max(id) FROM revlog") or (None, None)
        if min_all is None:
            return [], []
        has_old = int(min_all) <= 1000000000000
        if has_old:
            lo, hi = mw.col.db.first("SELECT min(id), max(id) FROM revlog WHERE id > 1000000000000") or (None, None)
        else:
            lo, hi = min_all, max_all
        out = []
        if lo is not None:
            lo_i = max(int(lo), int(start_ms)) if start_ms > 0 else int(lo)
            hi_i = min(int(hi) + 1, int(end_ms)) if end_ms > 0 else int(hi) + 1
            if lo_i < hi_i:
                first, last = lo_i // 900000, (hi_i - 1) // 900000 + 1
                ps = _periods(first, last)
                for i, (s0, off) in enumerate(ps):
                    s1 = ps[i + 1][0] if i + 1 < len(ps) else last
                    a = max(s0 * 900000, lo_i)
                    b = min(s1 * 900000, hi_i)
                    if a >= b:
                        continue
                    for quarter, total, correct in mw.col.db.all(f"""
                        SELECT (revlog.id / 900000) % 96, COUNT(*), SUM(CASE WHEN revlog.ease > 1 THEN 1 ELSE 0 END)
                        FROM revlog {join_cards}
                        WHERE revlog.id >= {a} AND revlog.id < {b} AND revlog.type < 4
                        {limits}
                        GROUP BY 1"""):
                        out.append((off, quarter, total, correct))
        old = []
        if has_old:
            old_lo = f" AND revlog.id >= {int(start_ms) // 1000}" if start_ms > 0 else ""
            old_hi = f" AND revlog.id < {(int(end_ms) + 999) // 1000}" if end_ms > 0 else ""
            old = mw.col.db.all(f"""
                SELECT revlog.id * 1000 / 900000, COUNT(*), SUM(CASE WHEN revlog.ease > 1 THEN 1 ELSE 0 END)
                FROM revlog {join_cards}
                WHERE revlog.id <= 1000000000000 AND revlog.type < 4{old_lo}{old_hi}
                {limits}
                GROUP BY 1""")
        return out, old
    except Exception:
        log_swallowed()
        return None
