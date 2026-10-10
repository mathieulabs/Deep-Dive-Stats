# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QEasingCurve

from ...chart_utils.formatting import fmt_num
from ..common.discrete import (
    apply_discrete_transition_update,
    binning_active_getter,
    reset_discrete_transition_state,
    set_chart_opacity_impl,
)


def normalize_data_dict_impl(widget, data_dict):
    data_dict = data_dict or {}
    title_l = str(getattr(widget, "title", "")).strip().lower()
    if title_l not in ("difficulty", "retrievability"):
        return data_dict
    dense = {i: 0 for i in range(101)}
    for k, v in data_dict.items():
        try:
            idx = int(round(float(k)))
        except Exception:
            continue
        if 0 <= idx <= 100:
            dense[idx] = int(v or 0)
    return dense

def get_margins_impl(widget):
    from ...chart_utils.geometry import ChartGeometry

    fm = widget.fontMetrics()
    ml = ChartGeometry.calculate_dynamic_left_margin(fm, widget.max_val)
    if widget.show_cumulative_axis:
        mr = ChartGeometry.calculate_dynamic_right_margin(fm, [widget.total_cards], True)
    else:
        mr = widget._non_cumulative_margin_right
    mb = ChartGeometry.MARGIN_BOTTOM
    mt = ChartGeometry.MARGIN_TOP
    return ml, mr, mb, mt


def update_data_impl(widget, new_data_dict, adaptive_binning=None):
    if adaptive_binning is not None:
        widget.adaptive_binning = adaptive_binning
    new_data_dict = widget._normalize_data_dict(new_data_dict)
    old_values = widget._current_values_snapshot()
    new_items = sorted(new_data_dict.items())
    new_values = [float(v or 0.0) for _, v in new_items]
    old_max = max(old_values) if old_values and max(old_values) > 0 else 1.0
    new_max = max(new_values) if new_values and max(new_values) > 0 else 1.0
    widget.data_dict = new_data_dict
    widget.data_list = new_items
    widget.max_val = max([v for _, v in widget.data_list]) if widget.data_list else 1
    widget.total_cards = sum([v for _, v in widget.data_list])
    widget._clear_hover()
    if apply_discrete_transition_update(
        widget,
        old_values=old_values,
        new_values=new_values,
        old_max=old_max,
        new_max=new_max,
        old_count=len(old_values),
        new_count=len(new_values),
        animate_kwargs={
            "min_duration_ms": 210,
            "max_duration_ms": 210,
            "empty_transition_duration_ms": 210,
        },
    ):
        widget.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
    else:
        reset_discrete_transition_state(widget)
        widget._progress = 1.0
        widget.animation.stop()
        widget.maybe_start_initial_animation()
    widget.update()


def current_values_snapshot_impl(widget):
    if not widget._data_transition_active:
        return [float(v or 0.0) for _, v in (widget.data_list or [])]
    t = widget.get_progress()
    if t >= 0.995:
        t = 1.0
    return widget.interpolate_numeric_series(
        widget._transition_old_values,
        widget._transition_new_values,
        t,
        align_right=False,
    )


def get_stats_text_impl(widget):
    return [f"Total: {fmt_num(widget.total_cards)} cards"]
