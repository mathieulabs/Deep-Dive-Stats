# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from ...chart_utils.theme import is_details_context
from ..common.core import set_chart_opacity_impl
from aqt.qt import QAbstractAnimation

_PIE_CHART_COLORS: dict[str, dict[str, str]] = {}


def invalidate_pie_chart_color_cache():
    global _PIE_CHART_COLORS
    _PIE_CHART_COLORS = {}


def get_pie_chart_colors(widget_or_context=None, force_refresh=False):
    cache_key = "details" if is_details_context(widget_or_context) else "pinned"
    if force_refresh:
        _PIE_CHART_COLORS.pop(cache_key, None)
    if cache_key in _PIE_CHART_COLORS:
        return dict(_PIE_CHART_COLORS[cache_key])

    from aqt import mw
    from ....ui import Config, ConfigManager, get_color

    cfg = ConfigManager(mw).config
    resolved = {
        "new": get_color(cfg, Config.COLOR_NEW, widget_or_context),
        "learn": get_color(cfg, Config.COLOR_LEARN, widget_or_context),
        "relearn": get_color(cfg, Config.COLOR_RELEARN, widget_or_context),
        "young": get_color(cfg, Config.COLOR_YOUNG, widget_or_context),
        "mature": get_color(cfg, Config.COLOR_MATURE, widget_or_context),
        "suspended": get_color(cfg, Config.COLOR_SUSPENDED, widget_or_context),
        "buried": get_color(cfg, Config.COLOR_BURIED, widget_or_context),
        "deleted": get_color(cfg, Config.COLOR_DELETED, widget_or_context),
    }
    _PIE_CHART_COLORS[cache_key] = resolved
    return dict(resolved)


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
