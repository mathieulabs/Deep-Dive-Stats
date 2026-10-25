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
    return (tuple(sorted(excluded_dids or [])), id(getattr(mw, 'col', None)))


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


def warm_time_view_static_bundle_async(excluded_dids):
    """Warm the static time-view bundle in the background if needed."""
    cache_key = _static_cache_key(excluded_dids)
    now = datetime.now().timestamp()
    cached = _TIME_VIEW_STATIC_CACHE.get(cache_key)
    if cached and (now - cached[0]) < _TIME_VIEW_STATIC_TTL_S:
        return False
    if cache_key in _TIME_VIEW_STATIC_WARMING:
        return False

    _TIME_VIEW_STATIC_WARMING.add(cache_key)

    def _bg():
        get_time_view_static_bundle(excluded_dids)
        return True

    def _done(_future):
        _TIME_VIEW_STATIC_WARMING.discard(cache_key)

    mw.taskman.run_in_background(_bg, _done)
    return True


def get_time_view_static_bundle_status(excluded_dids):
    """Return whether the static bundle is ready or still warming for a cache key."""
    cache_key = _static_cache_key(excluded_dids)
    now = datetime.now().timestamp()
    cached = _TIME_VIEW_STATIC_CACHE.get(cache_key)
    is_ready = bool(cached and (now - cached[0]) < _TIME_VIEW_STATIC_TTL_S)
    return {
        "ready": is_ready,
        "warming": cache_key in _TIME_VIEW_STATIC_WARMING,
        "cache_key_size": len(cache_key),
    }



