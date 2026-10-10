# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt import mw
from .. import Period
from ..history_provider import HistoryProvider

class ReviewIntervalsDataProvider:
    @staticmethod
    def fetch_data(addon_config, deck_id=None, is_deleted=False, time_span=Period.TOTAL):
        """
        Fetches distribution of card review intervals.
        """
        if is_deleted:
            # The cards are gone: use the interval of each one's last review.
            from ..history_provider.deleted_states import deleted_review_intervals

            payload = deleted_review_intervals()
            if payload is not None:
                return payload
            did_limit = "AND (CASE WHEN cards.odid > 0 THEN cards.odid ELSE cards.did END) IS NULL"
        else:
            did_limit = HistoryProvider._get_did_limit(addon_config, deck_id)

        # We only care about reviews (queue = 2) or day learning (queue = 3)
        # We filter for ivl > 0 to ignore learning cards with negative sub-day intervals
        query = f"""
            SELECT ivl
            FROM cards
            WHERE queue IN (2, 3) 
            AND ivl > 0
            {did_limit}
        """
        rows = mw.col.db.all(query)
        
        distribution = {}
        for (ivl,) in rows:
            distribution[ivl] = distribution.get(ivl, 0) + 1
            
        # Percentiles (p50, p95) for the UI, next to the max interval bounds
        all_ivls = [r[0] for r in rows]
        all_ivls.sort()
        
        p50 = 31
        p95 = 365
        median = 0
        if all_ivls:
            # Same rule as the history cache snapshot (first interval whose cumulative count
            # reaches the share), so the median is the same for a direct fetch and the
            # cached value.
            n = len(all_ivls)
            p50 = all_ivls[max(0, -(-n * 50 // 100) - 1)]
            p95 = all_ivls[max(0, -(-n * 95 // 100) - 1)]
            median = p50
            
        total_cards = len(all_ivls)
        
        return {
            "distribution": distribution,
            "total": total_cards,
            "median": median,
            "p50": p50,
            "p95": p95
        }



