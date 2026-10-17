# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from ..core import binning_active_getter, set_chart_opacity_impl, set_flags_and_update


def set_cumulative_mode_impl(widget, visible):
    return set_flags_and_update(widget, bool(visible), "cumulative_visible", "show_cumulative_axis")


def _transition_count_attr(count_attr):
    name = str(count_attr or "points_count").strip()
    if not name:
        name = "points_count"
    return f"_transition_old_{name}", f"_transition_new_{name}"


def reset_discrete_transition_state(widget, *, count_attr="points_count"):
    widget._data_transition_active = False
    widget._transition_old_values = []
    widget._transition_new_values = []
    widget._transition_old_max = 1.0
    widget._transition_new_max = 1.0
    old_attr, new_attr = _transition_count_attr(count_attr)
    setattr(widget, old_attr, 0)
    setattr(widget, new_attr, 0)
    widget._transition_align_right = False


def discrete_transition_target_unchanged(widget, *, new_points_count, new_values, count_attr="points_count"):
    _old_attr, new_attr = _transition_count_attr(count_attr)
    return bool(
        widget._data_transition_active
        and int(new_points_count or 0) == int(getattr(widget, new_attr, 0) or 0)
        and [float(v or 0.0) for v in (new_values or [])]
        == [float(v or 0.0) for v in (widget._transition_new_values or [])]
    )


def current_discrete_values_snapshot_impl(widget):
    if not widget._data_transition_active:
        return [float(v or 0.0) for v in (widget._display_values or [])]
    t = widget.get_progress()
    return widget.interpolate_numeric_series(
        widget._transition_old_values,
        widget._transition_new_values,
        t,
        align_right=widget._transition_align_right,
    )


def apply_discrete_transition_update(
    widget,
    *,
    old_values,
    new_values,
    old_max,
    new_max,
    old_count,
    new_count,
    count_attr="points_count",
    align_right=False,
    animate_kwargs=None,
):
    widget._transition_align_right = bool(align_right)
    changed = (old_values != new_values) or (int(old_count or 0) != int(new_count or 0))
    if not changed:
        reset_discrete_transition_state(widget, count_attr=count_attr)
        return False

    widget._transition_old_values = [float(v or 0.0) for v in (old_values or [])]
    widget._transition_new_values = [float(v or 0.0) for v in (new_values or [])]
    widget._transition_old_max = max(1.0, float(old_max or 0.0))
    widget._transition_new_max = max(1.0, float(new_max or 0.0))
    old_attr, new_attr = _transition_count_attr(count_attr)
    setattr(widget, old_attr, int(old_count or 0))
    setattr(widget, new_attr, int(new_count or 0))
    widget._data_transition_active = True

    kwargs = dict(animate_kwargs or {})
    widget.animate_data_update(widget._transition_old_values, widget._transition_new_values, **kwargs)
    return True
