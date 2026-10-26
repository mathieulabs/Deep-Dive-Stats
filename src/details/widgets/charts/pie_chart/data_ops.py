# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from ...chart_utils.theme import is_details_context
from ..common.core import set_chart_opacity_impl
from aqt.qt import QAbstractAnimation

from .....const.theme.color_resolver import own_color_for

_PIE_CHART_COLORS: dict[str, dict[str, str]] = {}


def invalidate_pie_chart_color_cache():
    global _PIE_CHART_COLORS
    _PIE_CHART_COLORS = {}


_PIE_COLOR_KEYS = {
    "new": "Color_New",
    "learn": "Color_Learn",
    "relearn": "Color_Relearn",
    "young": "Color_Young",
    "mature": "Color_Mature",
    "suspended": "Color_Suspended",
    "buried": "Color_Buried",
    "deleted": "Color_Deleted",
}


def get_pie_chart_colors(widget_or_context=None, force_refresh=False):
    is_details = is_details_context(widget_or_context)
    cache_key = "details" if is_details else "pinned"
    if force_refresh:
        _PIE_CHART_COLORS.pop(cache_key, None)
    resolved = _PIE_CHART_COLORS.get(cache_key)
    if resolved is None:
        from aqt import mw
        from ....ui import ConfigManager, get_color

        cfg = ConfigManager(mw).config
        # The shared colors are cached per context; a widget's own colors are not shared.
        context = None if is_details else "pinned"
        resolved = {name: get_color(cfg, key, context) for name, key in _PIE_COLOR_KEYS.items()}
        _PIE_CHART_COLORS[cache_key] = resolved
    return {name: own_color_for(widget_or_context, _PIE_COLOR_KEYS[name]) or color for name, color in resolved.items()}


def refresh_data_colors_impl(widget):
    widget.colors = get_pie_chart_colors(widget, force_refresh=True)
    widget.update()

def active_keys_impl(widget):
    keys = ["new", "learn", "relearn", "young", "mature"]
    if widget.separate_suspended:
        keys.extend(["suspended", "buried"])
    return keys


def update_counts_impl(widget, counts):
    next_counts = counts or {}
    if next_counts == widget.counts:
        # If no new data arrives but progress is still at 0 (e.g. intro show path skipped),
        # force final draw so pie slices are visible.
        anim = getattr(widget, "animation", None)
        is_running = bool(anim and anim.state() == QAbstractAnimation.State.Running)
        if (not is_running) and float(getattr(widget, "_progress", 1.0)) <= 0.0:
            if hasattr(widget, "_finish_without_animation"):
                widget._finish_without_animation()
            else:
                widget._progress = 1.0
        widget.update_geom()
        widget.update()
        return

    prev_counts = dict(widget.counts or {})
    new_counts = dict(next_counts)
    active_keys = widget._active_keys()
    prev_total = sum(float(prev_counts.get(k, 0)) for k in active_keys)
    next_total = sum(float(new_counts.get(k, 0)) for k in active_keys)

    empty_graph_transition = prev_total > 0.0 and next_total <= 0.0
    from_empty_transition = prev_total <= 0.0 and next_total > 0.0

    duration = int(widget._morph_duration_ms)
    widget._prev_counts = prev_counts
    widget._next_counts = new_counts
    widget.counts = new_counts
    widget._is_data_morph = not (empty_graph_transition or from_empty_transition)
    if empty_graph_transition:
        widget._global_transition_mode = "to_empty"
        widget.animation.setDuration(widget._empty_graph_morph_duration_ms)
    elif from_empty_transition:
        widget._global_transition_mode = "from_empty"
        widget.animation.setDuration(widget._empty_graph_morph_duration_ms)
    else:
        widget._global_transition_mode = None
        widget.animation.setDuration(duration)
    from aqt.qt import QEasingCurve

    widget.animation.setEasingCurve(QEasingCurve.Type.InOutSine)
    widget.replay_animation()
    widget.update_geom()
    widget.update()
