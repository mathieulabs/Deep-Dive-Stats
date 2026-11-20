# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from datetime import datetime

from aqt import mw

from ... import excluded_decks_clause
from ..core.streaks import get_all_deck_streaks
from ..core.forecast import deck_new_limit

_TIME_VIEW_STATIC_CACHE = {}
_TIME_VIEW_STATIC_TTL_S = 10
_TIME_VIEW_STATIC_WARMING = set()


def _static_cache_key(excluded_dids):
    # The bundle describes one collection: never serve it across a profile/
    # collection switch inside the TTL.
    # str: the list holds deck ids and may hold "deleted" (Deleted Cards), which do not compare.
    return (tuple(sorted(excluded_dids or [], key=str)), id(getattr(mw, 'col', None)))


def get_time_view_static_bundle(excluded_dids):
    cache_key = _static_cache_key(excluded_dids)
    now = datetime.now().timestamp()
    cached = _TIME_VIEW_STATIC_CACHE.get(cache_key)
    if cached and (now - cached[0]) < _TIME_VIEW_STATIC_TTL_S:
        return cached[1], True

    did_limit = excluded_decks_clause(excluded_dids)
    all_decks_list = list(mw.col.decks.all_names_and_ids())
    deck_limits = {}
    for d in all_decks_list:
        deck_limits[d.id] = deck_new_limit(mw.col, d.id)

    new_cards_results = mw.col.db.all(
        f"SELECT (CASE WHEN odid > 0 THEN odid ELSE did END), COUNT(*) FROM cards WHERE type = 0 {did_limit} GROUP BY 1"
    )
    remaining_new_map = dict(new_cards_results)

    streak_map = get_all_deck_streaks(did_limit)
    deck_name_maps = (
        {d.id: d.name for d in all_decks_list},
        {d.name: d.id for d in all_decks_list},
    )
    bundle = {
        "did_limit": did_limit,
        "deck_limits": deck_limits,
        "remaining_new_map": remaining_new_map,
        "streak_map": streak_map,
        "deck_name_maps": deck_name_maps,
    }
    _TIME_VIEW_STATIC_CACHE[cache_key] = (now, bundle)
    return bundle, False


