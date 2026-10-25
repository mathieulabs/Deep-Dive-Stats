# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Data loading and processing package."""

from .core.time_utils import get_time_range_ms
from .core.streaks import get_deck_streaks, get_all_deck_streaks
from .core.database import fetch_data, fetch_dids_with_data
from .context_payloads import get_context_history_payload, get_default_history_payload
from .transforms import process_deck_tree, calculate_totals
from .time_view.loader import load_stats_data
from .section_fetchers import fetch_section_data
from .stats import fetch_deck_stats
from .time_view.snapshot import fetch_stats_for_range
from .time_view.static import (
    get_time_view_static_bundle,
    warm_time_view_static_bundle_async,
    get_time_view_static_bundle_status,
)

__all__ = [
    "get_time_range_ms",
    "get_deck_streaks",
    "get_all_deck_streaks",
    "fetch_data",
    "fetch_dids_with_data",
    "get_context_history_payload",
    "get_default_history_payload",
    "process_deck_tree",
    "calculate_totals",
    "load_stats_data",
    "fetch_section_data",
    "fetch_deck_stats",
    "fetch_stats_for_range",
    "get_time_view_static_bundle",
    "warm_time_view_static_bundle_async",
    "get_time_view_static_bundle_status",
]
