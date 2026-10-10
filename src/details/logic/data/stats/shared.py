# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from ... import excluded_decks_clause, rollover_hour
from ..core.time_utils import get_time_range_ms, custom_exact_date_bounds_from_ms


def build_collection_did_limit(excluded_dids):
    from .....utils import excluded_not_in_clause
    return excluded_not_in_clause(excluded_dids)


def build_global_did_limit(excluded_dids):
    return excluded_decks_clause(excluded_dids)


def resolve_tab_range(tab_config, default_week_start, show_trends=False):
    return get_time_range_ms(
        tab_config.get("range"),
        tab_config.get("week_start", default_week_start),
        tab_config.get("days", 7),
        tab_config.get("custom_type", "relative"),
        tab_config.get("start_date", ""),
        tab_config.get("end_date", ""),
        show_trends,
    )


def resolve_prev_exact_bounds(prev_start_ms, prev_end_ms):
    return custom_exact_date_bounds_from_ms(prev_start_ms, prev_end_ms, rollover_hour())


