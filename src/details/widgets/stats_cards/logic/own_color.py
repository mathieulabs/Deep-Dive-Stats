# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""The color of a stat card when it has "Own colors" on (see chart_utils/own_colors.py).

A pinned card keeps it in its definition like any widget ("own_colors"). A Deep Dive card
keeps it in Config.DASH_STAT_COLORS, {stat key: hex}: an entry means own colors are on.
"""

from aqt.qt import QColor

from ....ui import Config
from .....const.theme.color_resolver import own_color_for


def valid_color(value):
    return value if isinstance(value, str) and QColor(value).isValid() else None


def card_color_key(widget):
    """The shared color key the card's value uses."""
    stat_type = getattr(widget, "stat_type", None)
    if stat_type:
        return stat_type
    from .....const.theme.data_colors import STAT_KEY_TO_COLOR_KEY

    return STAT_KEY_TO_COLOR_KEY.get(str(getattr(widget, "config_key", "") or ""))


def own_card_color(widget):
    """The card's own color, or None (then the shared one)."""
    key = card_color_key(widget)
    return own_color_for(widget, key) if key else None


def dashboard_card_color(conf, stat_key):
    colors = (conf or {}).get(Config.DASH_STAT_COLORS) or {}
    return valid_color(colors.get(stat_key)) if isinstance(colors, dict) else None


def with_dashboard_card_color(conf, stat_key, color):
    """A copy of the Deep Dive card colors with `stat_key` set to `color` (None removes it)."""
    colors = (conf or {}).get(Config.DASH_STAT_COLORS) or {}
    colors = dict(colors) if isinstance(colors, dict) else {}
    if valid_color(color):
        colors[stat_key] = color
    else:
        colors.pop(stat_key, None)
    return colors
