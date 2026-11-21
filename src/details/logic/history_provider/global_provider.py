# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
import functools

from .did_limit import DidLimitMixin
from .ops.cards import fetch_added_history, fetch_card_counts, fetch_future_reviews
from .ops.context_bulk import fetch_all_decks_context
from .ops.context_fsrs import fetch_fsrs_stats
from .ops.history_fetch import fetch_history
from .stats import StatsMixin


class HistoryProvider(DidLimitMixin, StatsMixin):
    pass


for _fn in (fetch_history, fetch_added_history, fetch_card_counts, fetch_future_reviews,
            fetch_all_decks_context, fetch_fsrs_stats):
    # The ops/ functions take the provider class first (for _get_did_limit and the session's deleted count).
    setattr(HistoryProvider, _fn.__name__, staticmethod(functools.partial(_fn, HistoryProvider)))
del _fn
