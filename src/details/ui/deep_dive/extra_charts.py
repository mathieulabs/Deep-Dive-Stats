# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Which charts Deep Dive shows, and the ones added on demand (charts.more_charts): their
sections, their refresh, adding and removing any chart (right click > Remove, with Undo).

The header button, "Add Chart..." / "Add Stat Card..." of the right-click menus and the
"+ Add Chart" spot open the gallery as the manager of Deep Dive: every chart and stat card,
the ones shown checked, a click adds or removes one, Done applies it all.

The usual charts show until removed (Config.DEEP_DIVE_HIDDEN_CHARTS); the others only once
added (Config.DEEP_DIVE_EXTRA_CHARTS), so the window does not grow for people who do not
want them."""


from .. import Config
from ...widgets.charts.more_charts import BY_TYPE


def base_types():
    """The usual Deep Dive charts (the same types as the pinned ones)."""
    from ...widgets.pinned.main_menu.ui.add_widget_menu import CHARTS as BASE

    return [t for t, _label in BASE]


def hidden_types(manager):
    saved = manager.addon_config.config.get(Config.DEEP_DIVE_HIDDEN_CHARTS, []) or []
    return [t for t in saved if t in base_types()]


def extra_types(manager):
    """The added charts, in the order they were added (unknown types left out)."""
    saved = manager.addon_config.config.get(Config.DEEP_DIVE_EXTRA_CHARTS, []) or []
    return [t for t in saved if t in BY_TYPE]


def _days(manager, wtype):
    rows = manager._get_widget_history(wtype, manager.last_history_data) or []
    return list(rows)[::-1]  # oldest first


def _save(manager, types):
    manager.addon_config.set_value(Config.DEEP_DIVE_EXTRA_CHARTS, list(types))


def _save_hidden(manager, types):
    manager.addon_config.set_value(Config.DEEP_DIVE_HIDDEN_CHARTS, list(types))


def _show(manager, wtype, index=None):
    if wtype in base_types():
        _save_hidden(manager, [t for t in hidden_types(manager) if t != wtype])
    elif wtype in BY_TYPE:
        types = extra_types(manager)
        if wtype not in types:
            types.insert(len(types) if index is None else min(index, len(types)), wtype)
            _save(manager, types)


def shown_charts(manager):
    hidden = set(hidden_types(manager))
    return [t for t in base_types() if t not in hidden] + extra_types(manager)


# -- the "Add Chart" spot in the free end of the last row (on hover) ----------------------


