# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""The Settings' Decks tab (web_ui/settings.py, settings_decks.js): its values put in the config, and the caches
that depend on them cleared."""
from ... import Config


def clear_stat_caches():
    """The all-decks aggregates of the caches depend on the excluded decks and dates."""
    try:
        from ....logic.history_cache import GlobalHistoryCache
        from ....widgets.pinned.widget_factory.utils import PinnedDataManager

        GlobalHistoryCache.clear_all_cache()
        PinnedDataManager.clear()
    except Exception:
        from ....logic.logger import log_swallowed

        log_swallowed()


def apply_deck_options(conf, values):
    """Puts the tab's values (excluded decks, deck colors, excluded dates) in the config (not written). True when
    the excluded decks or dates changed (the caches are cleared then)."""
    excluded, colors, dates = values
    before = (sorted(conf.get(Config.EXCLUDED_DECKS, []) or [], key=str), list(conf.get(Config.EXCLUDED_DATES, []) or []))
    conf[Config.EXCLUDED_DATES] = dates
    conf[Config.EXCLUDED_DECKS] = excluded
    conf[Config.DECK_COLORS] = colors
    changed = before != (sorted(excluded, key=str), list(dates))
    if changed:
        clear_stat_caches()
    return changed

