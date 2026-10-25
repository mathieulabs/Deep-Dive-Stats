# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt import mw
from .. import Period
from ..history_provider import HistoryProvider
from ..logger import log_swallowed


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


class FutureDueDataProvider:
    @staticmethod
    def fetch_data(addon_config, deck_id=None, is_deleted=False, time_span=Period.TOTAL, include_backlog=False):
        """
        Fetches future due reviews distribution.
        """

        if is_deleted:
            did_limit = "AND (CASE WHEN cards.odid > 0 THEN cards.odid ELSE cards.did END) IS NULL"
            lookup_id = -1
        else:
            did_limit = HistoryProvider._get_did_limit(addon_config, deck_id)
            lookup_id = deck_id

        today = mw.col.sched.today

        from ..history_cache import GlobalHistoryCache

        ghc = GlobalHistoryCache()
        distribution = None

        if isinstance(lookup_id, int) and lookup_id != -1:
            try:
                name = mw.col.decks.name(lookup_id)
                if name and name in ghc.cache:
                    lookup_id = name
            except Exception:
                log_swallowed()

        backlog_count = 0
        if ghc.is_initialized and not isinstance(lookup_id, list) and lookup_id in ghc.cache:
            ctx = ghc.get_context(lookup_id, Period.TOTAL, allow_sync_check=False)
            if ctx and "future_due" in ctx:
                raw_dist = ctx["future_due"].get("distribution", {})

                # The cache stores absolute Anki due days (queues 2 and 3): make them relative.
                distribution = {}
                for k, v in raw_dist.items():
                    try:
                        k = int(k)
                    except Exception:
                        continue
                    # Epoch timestamps are learning cards (queue 1), left out like in
                    # Anki's own forecast. Negative due days are invalid.
                    if k >= 1000000000 or k < 0:
                        continue
                    rel_day = k - today
                    if include_backlog or rel_day >= 0:
                        distribution[rel_day] = distribution.get(rel_day, 0) + v
                        if rel_day < 0:
                            backlog_count += v

        if distribution is None:
            # Future cards (review and day-learning only, matching Anki's native forecast)
            query = f"""
                SELECT due
                FROM cards
                WHERE queue IN (2, 3) AND due >= {today}
                {did_limit}
            """
            distribution = {}
            for (due,) in mw.col.db.all(query):
                days_future = due - today
                distribution[days_future] = distribution.get(days_future, 0) + 1

            if include_backlog:
                try:
                    # Backlog cards (review and day-learning overdue only)
                    b_query = f"""
                        SELECT due, COUNT(*)
                        FROM cards
                        WHERE queue IN (2, 3) AND due >= 0 AND due < {today}
                        {did_limit}
                        GROUP BY due
                    """
                    for (due, cnt) in mw.col.db.all(b_query):
                        day = due - today
                        distribution[day] = distribution.get(day, 0) + cnt
                        backlog_count += cnt
                except Exception:
                    log_swallowed()

        payload = build_future_due_payload(
            distribution,
            time_span=time_span,
            addon_config=addon_config,
            backlog_count=backlog_count,
        )
        return payload
