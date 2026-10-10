# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from .single import fetch_deck_stats
from .bulk import fetch_all_decks_stats

__all__ = [
    "fetch_deck_stats",
    "fetch_all_decks_stats",
]
