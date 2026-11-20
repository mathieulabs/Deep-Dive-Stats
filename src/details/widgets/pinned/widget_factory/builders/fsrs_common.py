# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Shared helper for FSRS chart data fetching (stability, difficulty, retrievability)."""

from ..utils import _addon_config
from . import HistoryProvider, Period
from ...context_access import get_pinned_context_value
from .....logic.data.section_fetchers import fetch_section_data
from .....logic.data.section_fallbacks import resolve_fsrs_payload


def fetch_fsrs_data(deck_id, cfg=None, fail_if_not_cached=False):
    """Fetch FSRS stats for a given deck, cache first then SQL fallback."""
    config = cfg or _addon_config()

    # Concrete decks: query with a did_limit built from the deck and its children.
    # This matches the Deep Dive folder behavior and avoids stale cache snapshots
    # for FSRS payloads.
    if isinstance(deck_id, int) and deck_id not in (-1, 0):
        did_limit = HistoryProvider._get_did_limit(config, deck_id)
        return fetch_section_data(
            config,
            "fsrs",
            deck_id=deck_id,
            is_deleted=False,
            did_limit=did_limit,
        ) or {}

    _, fsrs = get_pinned_context_value(
        deck_id,
        Period.TOTAL,
        "fsrs",
        cfg=config,
        fail_if_not_cached=fail_if_not_cached,
    )

    resolved_fsrs = resolve_fsrs_payload(
        {"fsrs": fsrs} if fsrs is not None else None,
        fetcher=None,
        require_stability=False,
    )
    if resolved_fsrs is not None:
        return resolved_fsrs

    # Non-blocking UI pass: don't mix in SQL fallback snapshots.
    # Wait for cache-ready callback so both FSRS charts consume the same source.
    if fail_if_not_cached:
        return None

    res = fetch_section_data(config, "fsrs", deck_id=deck_id, is_deleted=False)
    return res
