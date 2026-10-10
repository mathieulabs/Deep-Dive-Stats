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
    def fetch_data(addon_config, deck_id=None, is_deleted=False, time_span=Period.TOTAL, override_start_ms=None, override_end_ms=None):
        """
        Fetches review counts and success rates grouped by hour of the day.
        Returns: {hour: {"total": count, "correct": count}} for hours 0-23
        """
        if is_deleted:
            did_limit = "AND (CASE WHEN cards.odid > 0 THEN cards.odid ELSE cards.did END) IS NULL"
        else:
            did_limit = HistoryProvider._get_did_limit(addon_config, deck_id)

        week_start = addon_config.config.get("week_start", 0)
        
        if override_start_ms is not None and override_end_ms is not None:
             start_ms, end_ms = override_start_ms, override_end_ms
        else:
             start_ms, end_ms, _, _ = get_time_range_ms(time_span, week_start=week_start)
        
        time_limit = ""
        if start_ms > 0:
            time_limit += f" AND (CASE WHEN revlog.id > 1000000000000 THEN revlog.id ELSE revlog.id * 1000 END) >= {start_ms}"
        if end_ms > 0 and (time_span != Period.TOTAL or override_end_ms is not None):
            time_limit += f" AND (CASE WHEN revlog.id > 1000000000000 THEN revlog.id ELSE revlog.id * 1000 END) < {end_ms}"
        
        # Aggregate by local hour inside SQLite instead of building a datetime per
        # review in Python (about 150k rows on a large collection). SQLite's
        # 'localtime' uses the same OS timezone rules as datetime.fromtimestamp().
        query = f"""
            SELECT CAST(strftime('%H',
                       CASE WHEN revlog.id > 1000000000000 THEN revlog.id / 1000.0 ELSE revlog.id END,
                       'unixepoch', 'localtime') AS INTEGER) AS h,
                   COUNT(*),
                   SUM(CASE WHEN revlog.ease > 1 THEN 1 ELSE 0 END)
            FROM revlog
            LEFT JOIN cards ON revlog.cid = cards.id
            WHERE revlog.type < 4
            {did_limit} {excluded_days_clause()}
            {time_limit}
            GROUP BY h
        """
        hours_data = {h: {"total": 0, "correct": 0} for h in range(24)}
        try:
            rows = [] if did_limit_has_no_cards(did_limit) else mw.col.db.all(query)
            for h, total, correct in rows:
                if h is None or h not in hours_data:
                    continue
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




