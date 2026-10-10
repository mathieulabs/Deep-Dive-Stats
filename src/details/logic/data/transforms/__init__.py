# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from .tree import process_deck_tree
from .totals import calculate_totals
from .cache_adapter import adapter_from_cache
from .activity_series import (
    BREAKDOWN_BASE_KEYS,
    attach_breakdown_totals,
    build_activity_series,
    build_activity_series_from_breakdown,
    build_breakdown_rows,
    convert_breakdown_metric_rows,
    filter_activity_types,
    normalize_hidden_types,
    REVIEW_TYPE_CHOICES,
    HIDDEN_TYPES_KEY,
)
from .heatmap_series import (
    HEATMAP_BASE_KEYS,
    build_heatmap_data,
    extract_heatmap_future_values,
    make_heatmap_entry,
    merge_heatmap_future_values,
)
from .retention_series import RETENTION_SERIES_KEYS, build_retention_series
from ..section_fallbacks import (
    CARD_COUNT_TOTAL_KEYS,
    empty_card_counts_payload,
    empty_distribution_payload,
    empty_fsrs_payload,
    get_context_payload,
    has_distribution_values,
    normalize_card_counts,
    resolve_added_history_desc,
    resolve_card_counts_payload,
    resolve_distribution_payload,
    resolve_fsrs_payload,
)

__all__ = [
    "process_deck_tree",
    "calculate_totals",
    "adapter_from_cache",
    "BREAKDOWN_BASE_KEYS",
    "attach_breakdown_totals",
    "build_activity_series",
    "build_activity_series_from_breakdown",
    "build_breakdown_rows",
    "convert_breakdown_metric_rows",
    "filter_activity_types",
    "normalize_hidden_types",
    "REVIEW_TYPE_CHOICES",
    "HIDDEN_TYPES_KEY",
    "HEATMAP_BASE_KEYS",
    "build_heatmap_data",
    "extract_heatmap_future_values",
    "make_heatmap_entry",
    "merge_heatmap_future_values",
    "RETENTION_SERIES_KEYS",
    "build_retention_series",
    "CARD_COUNT_TOTAL_KEYS",
    "empty_card_counts_payload",
    "empty_distribution_payload",
    "empty_fsrs_payload",
    "get_context_payload",
    "has_distribution_values",
    "normalize_card_counts",
    "resolve_added_history_desc",
    "resolve_card_counts_payload",
    "resolve_distribution_payload",
    "resolve_fsrs_payload",
]
