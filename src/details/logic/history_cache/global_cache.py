# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from .context import ContextMixin
from .core import GlobalHistoryCacheCore
from .ops import init as _init, warmup as _warmup
from .population import PopulationMixin
from .refresh import RefreshMixin
from .storage import StorageMixin


class GlobalHistoryCache(
    RefreshMixin,
    ContextMixin,
    PopulationMixin,
    StorageMixin,
    GlobalHistoryCacheCore,
):
    def _on_collection_loaded(self, *args, **kwargs):
        # At startup the cache is not initialized yet and profile_did_open does the work.
        if not self.is_initialized:
            return
        return _init.on_profile_switch(self, GlobalHistoryCache, *args, **kwargs)

    def _on_profile_switch(self, *args, **kwargs):
        return _init.on_profile_switch(self, GlobalHistoryCache, *args, **kwargs)

    @staticmethod
    def init_async(callback=None):
        return _init.init_async(GlobalHistoryCache, callback=callback)

    def warmup_selected_decks(self, deck_ids, cfg=None):
        return _warmup.warmup_selected_decks(self, deck_ids, cfg=cfg)

    def schedule_deferred_full_warmup(self, delay_ms=2000, batch_size=24, budget_ms=10, priority_deck_ids=None):
        return _warmup.schedule_deferred_full_warmup(self, delay_ms=delay_ms, batch_size=batch_size,
                                                     budget_ms=budget_ms, priority_deck_ids=priority_deck_ids)
