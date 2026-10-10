# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from ....chart_utils.formatting import format_metric_value
from ..core import binning_active_getter, set_chart_opacity_impl, set_flag_and_update
from ..stats.render import draw_chart_bottom_stats

def set_show_stats_impl(widget, enabled):
    return set_flag_and_update(widget, "show_stats", enabled)


def normalize_metric_mode(mode):
    mode_str = str(mode or "reviews").strip().lower()
    if mode_str not in ("reviews", "time"):
        mode_str = "reviews"
    return mode_str


def set_value_mode_impl(widget, mode, *, track_mode_switch=False):
    mode_str = normalize_metric_mode(mode)
    if widget.value_mode != mode_str:
        if track_mode_switch and bool(getattr(widget, "_initial_animation_done", False)):
            widget._pending_mode_switch = (widget.value_mode, mode_str)
        elif track_mode_switch:
            widget._pending_mode_switch = None
        widget.value_mode = mode_str
        widget._invalidate_data_caches()
        widget.update()


def is_time_mode_impl(widget):
    return widget.value_mode == "time"


def format_metric_value_impl(widget, value, with_unit=True, per_day=False, axis=False, compact=True):
    return format_metric_value(
        value,
        value_mode=widget.value_mode,
        with_unit=with_unit,
        per_day=per_day,
        axis=axis,
        compact=compact,
    )


def axis_value_formatter_impl(widget, value):
    return widget._format_metric_value(value, axis=True)


def draw_bottom_stats_impl(widget, painter, plot_w, h, margin_left, margin_bottom):
    return draw_chart_bottom_stats(widget, painter, plot_w, h, margin_left, margin_bottom)


def axis_value_formatter_for_mode_impl(mode, value):
    from ....chart_utils.formatting import format_metric_axis_value_for_mode

    return format_metric_axis_value_for_mode(mode, value)


def begin_mode_switch(widget):
    """Consume a pending Reviews <-> Time switch and remember both sides for the transition."""
    pending = getattr(widget, "_pending_mode_switch", None)
    if pending and len(pending) == 2:
        widget._transition_old_value_mode = pending[0]
        widget._transition_new_value_mode = pending[1]
    else:
        pending = None
        widget._transition_old_value_mode = widget.value_mode
        widget._transition_new_value_mode = widget.value_mode
    widget._pending_mode_switch = None
    return pending


def transition_margin_formatters(widget):
    """(old, new) axis formatters, each in its own mode, so margins glide across a mode switch."""
    def _for(mode):
        if str(mode).lower() != "time":
            return None
        return lambda vv, m=mode: widget._axis_value_formatter_for_mode(m, vv)

    return (
        _for(getattr(widget, "_transition_old_value_mode", widget.value_mode)),
        _for(getattr(widget, "_transition_new_value_mode", widget.value_mode)),
    )
