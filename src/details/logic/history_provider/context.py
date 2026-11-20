# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from .shared import (
    Period,
)
from .ops.context_bulk import fetch_all_decks_context as fetch_all_decks_context_impl
from .ops.context_fsrs import fetch_fsrs_stats as fetch_fsrs_stats_impl


class ContextMixin:

    @staticmethod
    def fetch_all_decks_context(addon_config, range_type=Period.YEAR, min_rev_id=None, min_card_id=None):
        from .global_provider import HistoryProvider
        return fetch_all_decks_context_impl(HistoryProvider, addon_config, range_type=range_type, min_rev_id=min_rev_id, min_card_id=min_card_id)

    @staticmethod
    def fetch_fsrs_stats(addon_config, deck_id=None, is_deleted=False, did_limit=None):
        from .global_provider import HistoryProvider
        return fetch_fsrs_stats_impl(HistoryProvider, addon_config, deck_id=deck_id, is_deleted=is_deleted, did_limit=did_limit)


