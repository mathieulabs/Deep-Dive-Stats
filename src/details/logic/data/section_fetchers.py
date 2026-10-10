# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from datetime import datetime


def fetch_section_data(
    addon_config,
    section_type,
    *,
    deck_id=None,
    range_type=None,
    is_deleted=False,
    did_limit=None,
    custom_days=None,
    custom_type=None,
    start_date_str=None,
    end_date_str=None,
    minimal=None,
    target_year=None,
    override_start_ms=None,
    override_end_ms=None,
    override_bin_ms=None,
):
    from ..history_provider import HistoryProvider

    kwargs = {}
    if range_type is not None:
        kwargs["range_type"] = range_type
    if did_limit is not None:
        kwargs["did_limit"] = did_limit
    if custom_days is not None:
        kwargs["custom_days"] = custom_days
        kwargs["custom_type"] = custom_type if custom_type is not None else "relative"
        kwargs["start_date_str"] = start_date_str or ""
        kwargs["end_date_str"] = end_date_str or ""
    if override_start_ms is not None:
        kwargs["override_start_ms"] = override_start_ms
    if override_end_ms is not None:
        kwargs["override_end_ms"] = override_end_ms
    if override_bin_ms is not None:
        kwargs["override_bin_ms"] = override_bin_ms

    if section_type == "reviews":
        return HistoryProvider.fetch_history(
            addon_config,
            deck_id,
            is_deleted=is_deleted,
            minimal=bool(minimal),
            **kwargs,
        )

    if section_type == "heatmap":
        return HistoryProvider.fetch_history(
            addon_config,
            deck_id,
            is_deleted=is_deleted,
            minimal=True if minimal is None else bool(minimal),
            **kwargs,
        )

    if section_type == "added":
        return HistoryProvider.fetch_added_history(
            addon_config,
            deck_id,
            is_deleted=is_deleted,
            **kwargs,
        )

    if section_type == "card_counts":
        return HistoryProvider.fetch_card_counts(
            addon_config,
            deck_id,
            is_deleted=is_deleted,
            did_limit=did_limit,
        )

    if section_type == "distribution":
        return HistoryProvider.fetch_button_distribution(
            addon_config,
            deck_id,
            is_deleted=is_deleted,
            **kwargs,
        )

    if section_type == "future_reviews":
        year = target_year if target_year is not None else (
            range_type if isinstance(range_type, int) else datetime.now().year
        )
        return HistoryProvider.fetch_future_reviews(
            deck_id,
            year,
            addon_config,
            did_limit=did_limit,
        )

    if section_type == "stats":
        return HistoryProvider.fetch_stats_direct(
            addon_config,
            deck_id,
            **kwargs,
        )

    if section_type == "fsrs":
        return HistoryProvider.fetch_fsrs_stats(
            addon_config,
            deck_id,
            is_deleted=is_deleted,
            did_limit=did_limit,
        )

    return []
