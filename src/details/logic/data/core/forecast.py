# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Forecast: days left to see every new card at the decks' daily new-card limits.

One rule for every table (time view, deck view, folders, total):
- no new card left: 0 days;
- new cards left but no deck holding them has a limit (new cards off): no forecast ("-");
- otherwise the slowest of those decks, rounded up (a few cards left is 1 day, not 0).
"""
import math


def deck_new_limit(col, did):
    """New cards per day of a deck. A filtered deck has no limit of its own (0)."""
    try:
        conf = col.decks.config_dict_for_deck_id(did)
    except Exception:
        return 20
    new = conf.get("new") if isinstance(conf, dict) else None
    if not isinstance(new, dict):
        return 0
    try:
        return int(new.get("perDay", 20))
    except (TypeError, ValueError):
        return 20


def forecast_parts(dids, deck_limits, remaining_new_map):
    """(limit of the decks that still have new cards, slowest deck in days, new cards left)."""
    limit, slowest, remaining = 0, 0.0, 0
    for did in dids:
        rem = remaining_new_map.get(did, 0) or 0
        lim = deck_limits.get(did, 0) or 0
        remaining += rem
        if rem > 0 and lim > 0:
            limit += lim
            slowest = max(slowest, rem / lim)
    return limit, slowest, remaining


def forecast_days(limit, slowest, remaining):
    """Days left, or None when there is no forecast (new cards off)."""
    if not remaining:
        return 0
    if not limit or limit <= 0 or slowest is None:
        return None
    return int(math.ceil(max(0.0, float(slowest)) - 1e-9))
