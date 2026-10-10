# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from .ops.warmup import (
    schedule_deferred_full_warmup as schedule_deferred_full_warmup_impl,
    warmup_selected_decks as warmup_selected_decks_impl,
)


class WarmupMixin:
    def warmup_selected_decks(self, deck_ids, cfg=None):
        return warmup_selected_decks_impl(self, deck_ids, cfg=cfg)

    def schedule_deferred_full_warmup(self, delay_ms=2000, batch_size=24, budget_ms=10, priority_deck_ids=None):
        return schedule_deferred_full_warmup_impl(
            self,
            delay_ms=delay_ms,
            batch_size=batch_size,
            budget_ms=budget_ms,
            priority_deck_ids=priority_deck_ids,
        )

