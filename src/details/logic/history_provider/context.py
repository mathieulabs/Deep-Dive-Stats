# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from .shared import (
    Config,
    Period,
    datetime,
    get_deck_streaks,
)
from .ops.context_bulk import fetch_all_decks_context as fetch_all_decks_context_impl
from .ops.context_fsrs import fetch_fsrs_stats as fetch_fsrs_stats_impl
from .ops.context_pinned_processing import (
    build_activity_and_retention_data,
    build_processed_heatmap,
)


class ContextMixin:
    @staticmethod
    def fetch_pinned_context(addon_config, deck_id=None, range_type=Period.YEAR, custom_days=7, custom_type="relative", start_date_str="", end_date_str="", widget_settings=None):
        """Everything a pinned widget shows for one deck and period. Runs in a background
        thread: the aggregation is done here, not on the UI thread."""
        is_deleted = (deck_id == -1)

        did_limit = HistoryProvider._get_did_limit(addon_config, deck_id)

        reviews_history = HistoryProvider.fetch_history(
            addon_config, deck_id, range_type, is_deleted=is_deleted, did_limit=did_limit,
            custom_days=custom_days, custom_type=custom_type,
            start_date_str=start_date_str, end_date_str=end_date_str
        )

        added_history = HistoryProvider.fetch_added_history(
            addon_config, deck_id, range_type, is_deleted=is_deleted, did_limit=did_limit,
            custom_days=custom_days, custom_type=custom_type,
            start_date_str=start_date_str, end_date_str=end_date_str
        )

        target_year = range_type if (isinstance(range_type, int) and range_type > 7) else datetime.now().year
        future_reviews = HistoryProvider.fetch_future_reviews(deck_id, target_year, addon_config, did_limit=did_limit)

        counts = HistoryProvider.fetch_card_counts(addon_config, deck_id, is_deleted=is_deleted, did_limit=did_limit)

        processed_heatmap, active_days_set = build_processed_heatmap(reviews_history, future_reviews)

        stats = HistoryProvider.fetch_stats_direct(addon_config, deck_id, range_type, did_limit=did_limit)

        # Streak is global for the deck, ignoring the time range
        current_streak, _ = get_deck_streaks(deck_id, start_ms=0, excluded_dids=addon_config.config.get(Config.EXCLUDED_DECKS, []))
        stats["streak"] = current_streak

        dist_range = range_type
        if widget_settings and "distribution" in widget_settings:
            dist_range = int(widget_settings["distribution"].get("time_span", range_type))

        distribution = HistoryProvider.fetch_button_distribution(
            addon_config, deck_id, dist_range, is_deleted=is_deleted, did_limit=did_limit
        )

        added_range = range_type
        if widget_settings and "added" in widget_settings:
            added_range = int(widget_settings["added"].get("time_span", range_type))

        if added_range != range_type:
            added_history = HistoryProvider.fetch_added_history(
                addon_config, deck_id, added_range, is_deleted=is_deleted, did_limit=did_limit
            )

        from ..metrics.hourly import HourlyDataProvider
        hourly_range = range_type
        if widget_settings and "hourly" in widget_settings:
            hourly_range = int(widget_settings["hourly"].get("time_span", range_type))
        hourly_data = HourlyDataProvider.fetch_data(addon_config, deck_id, time_span=hourly_range)

        # Prefer GlobalHistoryCache for FSRS stats (full scan, all queues): direct SQL on queue=2 misses cards still in queue=1 right after a review.
        try:
            from ..history_cache import GlobalHistoryCache
            _ghc = GlobalHistoryCache()
            if deck_id:
                _deck_cache = _ghc.cache.get(deck_id) or {}
            else:
                _deck_cache = _ghc.cache.get("[[TOTAL]]") or _ghc.cache.get(None) or {}
            _total_ctx = _deck_cache.get(-1) or _deck_cache.get(list(_deck_cache.keys())[0]) if _deck_cache else {}
            _cached_fsrs = _total_ctx.get("fsrs") if _total_ctx else None
            if _cached_fsrs and _cached_fsrs.get("stability"):
                fsrs_stats = _cached_fsrs
            else:
                fsrs_stats = HistoryProvider.fetch_fsrs_stats(addon_config, deck_id, is_deleted=is_deleted, did_limit=did_limit)
        except Exception:
            fsrs_stats = HistoryProvider.fetch_fsrs_stats(addon_config, deck_id, is_deleted=is_deleted, did_limit=did_limit)

        from ..metrics.review_intervals import ReviewIntervalsDataProvider
        review_intervals = ReviewIntervalsDataProvider.fetch_data(addon_config, deck_id, time_span=range_type)

        from ..metrics.future_due import FutureDueDataProvider
        future_due_range = range_type
        if widget_settings and "future_due" in widget_settings:
            future_due_range = int(widget_settings["future_due"].get("time_span", range_type))
        future_due_data = FutureDueDataProvider.fetch_data(addon_config, deck_id, time_span=future_due_range)

        activity_data, activity_breakdown, retention_data = build_activity_and_retention_data(reviews_history)

        ctx = {
            "reviews": reviews_history,
            "added": added_history,
            "counts": counts,
            "distribution": distribution,
            "hourly": hourly_data,
            "fsrs": fsrs_stats,
            "review_intervals": review_intervals,
            "future_due": future_due_data,
            "future_reviews": future_reviews,
            "heatmap_data": processed_heatmap,
            "stats": stats,
            "activity_data": activity_data,
            "activity_breakdown": activity_breakdown,
            "retention_data": retention_data
        }
        if is_deleted:
            from .deleted_states import enrich_deleted_context
            ctx = enrich_deleted_context(ctx)
        return ctx

    @staticmethod
    def fetch_all_decks_context(addon_config, range_type=Period.YEAR, min_rev_id=None, min_card_id=None):
        return fetch_all_decks_context_impl(HistoryProvider, addon_config, range_type=range_type, min_rev_id=min_rev_id, min_card_id=min_card_id)

    @staticmethod
    def fetch_fsrs_stats(addon_config, deck_id=None, is_deleted=False, did_limit=None):
        return fetch_fsrs_stats_impl(HistoryProvider, addon_config, deck_id=deck_id, is_deleted=is_deleted, did_limit=did_limit)




