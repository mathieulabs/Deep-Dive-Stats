# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from .core.card import StatCardWidget
from .core.container import StatCardsContainer
from .core.row_group import RowGroupedStatContainer
from .logic.model import (
    get_stat_card_info,
    get_stat_card_default_title,
    DASHBOARD_CARD_SPECS,
    CARD_STATE_FIELDS,
    DECK_STATE_FIELDS,
    DECK_STATE_STAT_KEYS,
    deck_state_from_context,
    HISTORY_DERIVED_FIELDS,
    HISTORY_DERIVED_STAT_KEYS,
    iter_dashboard_stat_cards,
    apply_dashboard_stat_values,
    clear_dashboard_stat_values,
    build_dashboard_history_totals,
    build_dashboard_stat_values,
    build_total_row_entry,
    get_dashboard_stat_placeholder_values,
    map_stat_fields_to_config_keys,
    merge_stat_card_style_config,
    resolve_effective_stat_card_config,
    get_dashboard_local_stat_style,
)

__all__ = [
    "StatCardWidget",
    "StatCardsContainer",
    "RowGroupedStatContainer",
    "get_stat_card_info",
    "get_stat_card_default_title",
    "DASHBOARD_CARD_SPECS",
    "CARD_STATE_FIELDS",
    "DECK_STATE_FIELDS",
    "DECK_STATE_STAT_KEYS",
    "deck_state_from_context",
    "HISTORY_DERIVED_FIELDS",
    "HISTORY_DERIVED_STAT_KEYS",
    "iter_dashboard_stat_cards",
    "apply_dashboard_stat_values",
    "clear_dashboard_stat_values",
    "build_dashboard_history_totals",
    "build_dashboard_stat_values",
    "build_total_row_entry",
    "get_dashboard_stat_placeholder_values",
    "map_stat_fields_to_config_keys",
    "merge_stat_card_style_config",
    "resolve_effective_stat_card_config",
    "get_dashboard_local_stat_style",
]

