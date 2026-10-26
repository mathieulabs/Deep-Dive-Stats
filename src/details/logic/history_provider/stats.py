# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from ....utils import excluded_days_clause
from ..data.core.empty_deck import did_limit_has_no_cards
from .shared import Config, REVLOG_RESCHED, Period, get_daystart_epoch_sql, get_time_range_ms, mw


class StatsMixin:
    @staticmethod
    def fetch_stats_direct(addon_config, deck_id=None, range_type=Period.TOTAL, did_limit=None,
                           custom_days=7, custom_type="relative", start_date_str="", end_date_str=""):
        """Fetch global stats directly via SQL SUM/COUNT.
        Ultra-lightweight: No daily grouping.
        """
        from .global_provider import HistoryProvider
        if did_limit is None:
            did_limit = HistoryProvider._get_did_limit(addon_config, deck_id)

        week_start = addon_config.config.get(Config.WEEK_START, 0)
        start_ms, end_ms, _, _ = get_time_range_ms(range_type, week_start=week_start,
                                                   custom_days=custom_days, custom_type=custom_type,
                                                   start_date_str=start_date_str, end_date_str=end_date_str)

        query = f"""
            SELECT 
                COUNT(*) as reviews,
                COALESCE(SUM(revlog.time), 0) as time_ms,
                COALESCE(SUM(CASE WHEN revlog.ease > 1 THEN 1 ELSE 0 END), 0) as passed,
                COALESCE(SUM(CASE WHEN revlog.ease > 0 AND NOT (revlog.type = 3 AND revlog.factor = 0) AND (revlog.type = 1 OR revlog.lastIvl <= -86400 OR revlog.lastIvl >= 1) AND revlog.lastIvl < 21 THEN 1 ELSE 0 END), 0) as rev_young,
                COALESCE(SUM(CASE WHEN revlog.ease > 0 AND NOT (revlog.type = 3 AND revlog.factor = 0) AND (revlog.type = 1 OR revlog.lastIvl <= -86400 OR revlog.lastIvl >= 1) AND revlog.lastIvl < 21 AND revlog.ease > 1 THEN 1 ELSE 0 END), 0) as pass_young,
                COALESCE(SUM(CASE WHEN revlog.ease > 0 AND NOT (revlog.type = 3 AND revlog.factor = 0) AND (revlog.type = 1 OR revlog.lastIvl <= -86400 OR revlog.lastIvl >= 1) AND revlog.lastIvl >= 21 THEN 1 ELSE 0 END), 0) as rev_mat,
                COALESCE(SUM(CASE WHEN revlog.ease > 0 AND NOT (revlog.type = 3 AND revlog.factor = 0) AND (revlog.type = 1 OR revlog.lastIvl <= -86400 OR revlog.lastIvl >= 1) AND revlog.lastIvl >= 21 AND revlog.ease > 1 THEN 1 ELSE 0 END), 0) as pass_mat,
                COUNT(DISTINCT {get_daystart_epoch_sql('CASE WHEN revlog.id > 1000000000000 THEN revlog.id ELSE revlog.id * 1000 END', is_ms=True)}) as active_days
            FROM revlog
            LEFT JOIN cards ON revlog.cid = cards.id
            WHERE revlog.type < {REVLOG_RESCHED}
            AND (CASE WHEN revlog.id > 1000000000000 THEN revlog.id ELSE revlog.id * 1000 END) >= {start_ms} 
            AND (CASE WHEN revlog.id > 1000000000000 THEN revlog.id ELSE revlog.id * 1000 END) < {end_ms}
            {did_limit} {excluded_days_clause()}
        """
        row = None if did_limit_has_no_cards(did_limit) else mw.col.db.first(query)
        if not row or not row[0]:
            return {
                "total_reviews": 0, "total_time_ms": 0, "total_passed": 0,
                "rev_young": 0, "pass_young": 0, "rev_mat": 0, "pass_mat": 0, "active_days": 0, "retention": 0
            }

        reviews, t_ms, passed, r_young, p_young, r_mat, p_mat, active_days = row
        return {
            "total_reviews": reviews,
            "total_time_ms": t_ms,
            "total_passed": passed,
            "rev_young": r_young,
            "pass_young": p_young,
            "rev_mat": r_mat,
            "pass_mat": p_mat,
            "active_days": active_days,
            "retention": (passed / reviews * 100) if reviews > 0 else 0
        }

    @staticmethod
    def fetch_button_distribution(addon_config, deck_id=None, range_type=Period.YEAR, is_deleted=False, did_limit=None,
                                  custom_days=7, custom_type="relative", start_date_str="", end_date_str=""):
        """Button usage counts by card state.

        Returns {"learning": [b1, b2, b3, b4], "young": [...], "mature": [...]}.
        """
        from .global_provider import HistoryProvider
        if is_deleted:
            did_limit = "AND (CASE WHEN cards.odid > 0 THEN cards.odid ELSE cards.did END) IS NULL"
        elif did_limit is None:
            did_limit = HistoryProvider._get_did_limit(addon_config, deck_id)

        week_start = addon_config.config.get(Config.WEEK_START, 0)
        start_ms, end_ms, _, _ = get_time_range_ms(range_type, week_start=week_start,
                                                   custom_days=custom_days, custom_type=custom_type,
                                                   start_date_str=start_date_str, end_date_str=end_date_str)

        if range_type == Period.TOTAL:
            start_ms = 0

        # Card Types:
        # Learning: type in (0, 2)
        # Young: type = 1 AND lastIvl < 21
        # Mature: type = 1 AND lastIvl >= 21

        query = f"""
            SELECT 
                CASE 
                    WHEN revlog.type IN (0, 2) THEN 'learning'
                    WHEN revlog.type = 1 AND revlog.lastIvl < 21 THEN 'young'
                    WHEN revlog.type = 1 AND revlog.lastIvl >= 21 THEN 'mature'
                    ELSE 'other'
                END as card_type,
                revlog.ease,
                COUNT(*) as count
            FROM revlog
            LEFT JOIN cards ON revlog.cid = cards.id
            WHERE revlog.type < {REVLOG_RESCHED}
            AND (CASE WHEN revlog.id > 1000000000000 THEN revlog.id ELSE revlog.id * 1000 END) >= {start_ms}
            AND (CASE WHEN revlog.id > 1000000000000 THEN revlog.id ELSE revlog.id * 1000 END) < {end_ms}
            {did_limit} {excluded_days_clause()}
            GROUP BY card_type, revlog.ease
        """

        rows = [] if did_limit_has_no_cards(did_limit) else mw.col.db.all(query)

        distribution = {
            "learning": [0, 0, 0, 0],
            "young": [0, 0, 0, 0],
            "mature": [0, 0, 0, 0]
        }

        for r in rows:
            ctype, ease, count = r
            if ctype in distribution and 1 <= ease <= 4:
                # ease 1-4 maps to index 0-3
                distribution[ctype][ease-1] = count

        return distribution



