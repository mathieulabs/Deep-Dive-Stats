# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from .shared import Period
from .ops.cards import (
    fetch_added_history as fetch_added_history_impl,
    fetch_card_counts as fetch_card_counts_impl,
    fetch_future_reviews as fetch_future_reviews_impl,
)


class CardsMixin:
    @staticmethod
    def fetch_added_history(
        addon_config,
        deck_id=None,
        range_type=Period.YEAR,
        is_deleted=False,
        override_start_ms=None,
        override_end_ms=None,
        override_bin_ms=None,
        did_limit=None,
        custom_days=7,
        custom_type="relative",
        start_date_str="",
        end_date_str="",
    ):
        from .global_provider import HistoryProvider
        return fetch_added_history_impl(
            HistoryProvider,
            addon_config,
            deck_id=deck_id,
            range_type=range_type,
            is_deleted=is_deleted,
            override_start_ms=override_start_ms,
            override_end_ms=override_end_ms,
            override_bin_ms=override_bin_ms,
            did_limit=did_limit,
            custom_days=custom_days,
            custom_type=custom_type,
            start_date_str=start_date_str,
            end_date_str=end_date_str,
        )

    @staticmethod
    def fetch_card_counts(addon_config, deck_id=None, is_deleted=False, did_limit=None):
        from .global_provider import HistoryProvider
        return fetch_card_counts_impl(
            HistoryProvider,
            addon_config,
            deck_id=deck_id,
            is_deleted=is_deleted,
            did_limit=did_limit,
        )

    @staticmethod
    def fetch_future_reviews(deck_id, target_year, cfg, did_limit=None):
        from .global_provider import HistoryProvider
        return fetch_future_reviews_impl(
            HistoryProvider,
            deck_id,
            target_year,
            cfg,
            did_limit=did_limit,
        )

