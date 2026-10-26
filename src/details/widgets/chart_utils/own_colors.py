# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Colors a widget keeps for itself instead of the shared ones of Settings > Colors.

By default every chart and stat card uses the shared colors, so a card type looks the same
everywhere. With "Own colors" ticked in its settings, a widget keeps {color key: hex} of
its own: in its definition for a pinned widget, in its Deep Dive settings for a Deep Dive
chart, in Config.DASH_STAT_COLORS for a Deep Dive stat card. A color it does not set
stays the shared one.

On screen the colors sit on the widget's card (see OWN_COLORS_ATTR): get_color looks them
up from any chart inside it, so a chart that reads its colors again (data update, theme
change) keeps them.
"""

from aqt.qt import QColor, QWidget

from ....const.theme.color_resolver import OWN_COLORS_ATTR
from ...logic.logger import log_swallowed


def clean_own_colors(colors):
    """{color key: hex} with the valid entries of `colors`, or None when it is not a dict
    (no own colors). An empty dict means own colors are on but none is set yet."""
    if not isinstance(colors, dict):
        return None
    return {k: v for k, v in colors.items() if isinstance(k, str) and isinstance(v, str) and QColor(v).isValid()}


def _holders(container):
    """container plus the widgets above and inside it that already hold own colors: they
    all belong to the same widget (a pinned box and its card, a section and its chart), so
    they must agree, or a chart would still find an old value on its way up."""
    out, w = [container], container.parentWidget()
    for _depth in range(64):
        if w is None:
            break
        if isinstance(getattr(w, OWN_COLORS_ATTR, None), dict):
            out.append(w)
        w = w.parentWidget()
    out.extend(c for c in container.findChildren(QWidget) if isinstance(getattr(c, OWN_COLORS_ATTR, None), dict))
    return out


def apply_own_colors(container, colors):
    """Give `container` (a widget's card) these own colors, None for the shared ones, and
    have the charts and stat cards inside it read their colors again."""
    if container is None:
        return
    colors = clean_own_colors(colors)
    try:
        holders = _holders(container)
        if colors is None and all(getattr(h, OWN_COLORS_ATTR, None) is None for h in holders):
            return  # nothing was there and nothing to set
        for h in holders:
            setattr(h, OWN_COLORS_ATTR, None if colors is None else dict(colors))
        top = holders[0]
        for h in holders[1:]:
            if h.isAncestorOf(top):
                top = h
        targets = [top, *top.findChildren(QWidget)]
    except RuntimeError:
        return
    for w in targets:
        try:
            if hasattr(w, "refresh_data_colors"):
                w.refresh_data_colors()
            elif hasattr(w, "config_key") and hasattr(w, "refresh_theme"):  # stat card
                w._last_theme_refresh_key = None
                w.refresh_theme()
            w.update()
        except RuntimeError:
            pass
        except Exception:
            log_swallowed()
