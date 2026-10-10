# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QEasingCurve

from ..common import get_review_button_colors
from ..common.core import set_chart_opacity_impl


def refresh_data_colors_impl(widget):
    widget.colors = get_review_button_colors(widget)

def has_meaningful_data_for_animation_impl(widget):
    vals = flatten_grouped_values_impl(widget, getattr(widget, "data", None))
    return any(float(v or 0.0) > 0.0 for v in vals)


def flatten_grouped_values_impl(widget, data):
    out = []
    data = data or {}
    for group_key in widget._group_order:
        values = data.get(group_key, [])
        for i in range(widget._buttons_per_group):
            try:
                out.append(float(values[i]))
            except Exception:
                out.append(0.0)
    return out


def interpolate_series_fast_impl(widget, old_values, new_values, t):
    return [max(0.0, ov + ((nv - ov) * t)) for ov, nv in zip(old_values, new_values)]


def current_values_snapshot_impl(widget):
    if not widget._data_transition_active:
        return widget._flatten_grouped_values(widget.data)
    t = widget.get_progress()
    if t >= 0.995:
        t = 1.0
    return widget._interpolate_series_fast(widget._transition_old_values, widget._transition_new_values, t)


def update_data_impl(widget, new_data, transition_mode=None):
    old_values = widget._current_values_snapshot()
    new_values = widget._flatten_grouped_values(new_data)
    old_max = max(old_values) if old_values and max(old_values) > 0 else 1.0
    new_max = max(new_values) if new_values and max(new_values) > 0 else 1.0
    new_has_real = any(float(v or 0.0) > 0.0 for v in new_values)
    force_instant = transition_mode == "instant" or (not widget._has_real_data and new_has_real)

    widget.data = new_data
    all_values = []
    for values in widget.data.values():
        all_values.extend(values)
    widget.max_val = max(all_values) if all_values and max(all_values) > 0 else 1

    widget._recalculate_layout()
    if force_instant:
        widget._data_transition_active = False
        widget._transition_old_values = []
        widget._transition_new_values = []
        widget._transition_old_max = 1.0
        widget._transition_new_max = 1.0
        keep_intro_from_zero = (
            not bool(getattr(widget, "_initial_animation_done", False))
            and not bool(widget._get_pinned_animation_key())
        )
        widget._progress = 0.0 if keep_intro_from_zero else 1.0
        widget.animation.stop()
    elif old_values != new_values:
        widget._transition_old_values = old_values
        widget._transition_new_values = new_values
        widget._transition_old_max = old_max
        widget._transition_new_max = new_max
        widget._data_transition_active = True
        widget.animate_data_update(
            old_values,
            new_values,
            min_duration_ms=210,
            max_duration_ms=210,
            empty_transition_duration_ms=210,
        )
        widget.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
    else:
        widget._data_transition_active = False
        widget._transition_old_values = []
        widget._transition_new_values = []
        widget._transition_old_max = 1.0
        widget._transition_new_max = 1.0
        widget._progress = 1.0
        widget.animation.stop()
    widget._has_real_data = bool(new_has_real)
    widget.update()
