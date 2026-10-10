# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QColor

from ...chart_utils import ChartGeometry
from ...chart_utils.binning import get_bin_size
from ..common.metric import (
    animate_transition_update,
    apply_transition_state,
    axis_value_formatter_impl,
    begin_mode_switch,
    binning_active_getter,
    build_cumulative_values,
    commit_chart_data_update,
    zoom_slice_for_update,
    finalize_transition_state,
    format_metric_value_impl,
    is_time_mode_impl,
    pad_transition_values,
    resolve_transition_align_right,
    safe_positive_max,
    set_chart_opacity_impl,
    set_show_stats_impl,
    set_value_mode_impl as set_common_value_mode_impl,
    transition_update_is_redundant,
)
from ....logic.logger import log_swallowed

def refresh_data_colors_impl(widget):
    color_key = getattr(widget, "_color_config_key", None)
    if color_key is None:
        return
    try:
        from ....ui import get_chart_color

        widget.color = QColor(get_chart_color(color_key, widget))
        widget.update()
    except Exception:
        log_swallowed()


def set_average_mode_impl(widget, visible, on_active_days):
    widget.avg_visible = visible
    widget.avg_on_active_days = on_active_days
    widget._avg_val_cache = None
    widget._trace_activity_state(
        "set_average_mode",
        avg_visible=bool(visible),
        avg_on_active=bool(on_active_days),
        data_len=len(widget.data or []),
        display_len=len(widget._get_display_data() or []),
    )
    widget.update()


def set_value_mode_impl(widget, mode):
    return set_common_value_mode_impl(widget, mode, track_mode_switch=True)


def set_cumulative_mode_impl(widget, visible):
    widget.cumulative_visible = visible
    widget._invalidate_data_caches()
    widget._trace_activity_state(
        "set_cumulative_mode",
        cumulative_visible=bool(visible),
        data_len=len(widget.data or []),
        display_len=len(widget._get_display_data() or []),
    )
    widget.update()


def get_averages_impl(widget):
    if widget._avg_val_cache is not None:
        return widget._avg_val_cache

    values = widget._get_values()
    if not values:
        widget._avg_val_cache = 0
        return 0

    if widget.avg_on_active_days:
        source_vals = values if widget.binning_active else [
            d[1] if isinstance(d, (list, tuple)) else d for d in (widget.data or [])
        ]
        non_zeros = [v for v in source_vals if v > 0]
        avg = sum(non_zeros) / len(non_zeros) if non_zeros else 0
    else:
        avg = sum(values) / len(values)

    widget._avg_val_cache = avg
    return avg


def get_stats_text_impl(widget):
    raw_values = [d[1] if isinstance(d, (list, tuple)) else d for d in (widget.data or [])]
    if not raw_values:
        avg = 0
        total = 0
    else:
        if widget.avg_on_active_days:
            non_zeros = [v for v in raw_values if v > 0]
            avg = sum(non_zeros) / len(non_zeros) if non_zeros else 0
        else:
            avg = sum(raw_values) / len(raw_values)
        total = sum(raw_values)

    stats = [f"Total: {widget._format_metric_value(total, compact=False)}"]
    if avg > 0:
        stats.append(f"Avg: {widget._format_metric_value(avg, per_day=True, compact=False)}")
    return stats


def get_cumulative_impl(widget):
    if widget._cumulative_cache is not None:
        return widget._cumulative_cache

    cum = []
    run_sum = 0
    for val in widget._get_values():
        run_sum += val
        cum.append(run_sum)

    widget._cumulative_cache = cum
    return cum
def get_margins_impl(widget):
    values = widget._get_values()
    max_val = widget._get_max_val()

    fmt = widget._axis_value_formatter if widget._is_time_mode() else None
    margin_left = ChartGeometry.calculate_dynamic_left_margin(widget.fontMetrics(), max_val, value_formatter=fmt)
    margin_right = ChartGeometry.calculate_dynamic_right_margin(
        widget.fontMetrics(),
        values,
        getattr(widget, "cumulative_visible", False),
        value_formatter=fmt,
    )
    return margin_left, margin_right


def compute_display_data_impl(widget, source_data):
    source_data = source_data or []
    if not widget.binning_active:
        return source_data
    bs = get_bin_size(len(source_data))
    if bs <= 1:
        return source_data

    binned = []
    for i in range(0, len(source_data), bs):
        chunk = source_data[i : i + bs]
        vals = [d[1] if isinstance(d, (list, tuple)) else d for d in chunk]
        total_val = sum(vals)
        first_label = str(chunk[0][0]) if isinstance(chunk[0], (list, tuple)) else ""
        last_label = str(chunk[-1][0]) if isinstance(chunk[-1], (list, tuple)) else ""

        if first_label and last_label and first_label != last_label:
            label = f"{first_label} - {last_label}"
        else:
            label = first_label or ""
        binned.append((label, total_val))
    return binned


def get_display_data_impl(widget):
    if widget._binned_data_cache is not None:
        return widget._binned_data_cache
    widget._binned_data_cache = widget._compute_display_data(widget.data)
    return widget._binned_data_cache


def get_values_impl(widget):
    if widget._values_cache is not None:
        return widget._values_cache
    display_data = widget._get_display_data()
    widget._values_cache = [d[1] if isinstance(d, (list, tuple)) else d for d in display_data]
    return widget._values_cache


def get_labels_impl(widget):
    if widget._labels_cache is not None:
        return widget._labels_cache
    display_data = widget._get_display_data()
    widget._labels_cache = [str(d[0]) if isinstance(d, (list, tuple)) else "" for d in display_data]
    widget._has_labels_cache = any(widget._labels_cache)
    return widget._labels_cache


def get_max_val_impl(widget):
    if widget._max_val_cache is not None:
        return widget._max_val_cache
    values = widget._get_values()
    widget._max_val_cache = max(values) if values else 1
    if widget._max_val_cache == 0:
        widget._max_val_cache = 1
    return widget._max_val_cache


def invalidate_geometry_caches_impl(widget):
    widget._path_cache = None
    widget._area_path_cache = None
    widget._cum_path_cache = None


def invalidate_data_caches_impl(widget):
    widget._invalidate_geometry_caches()
    widget._max_val_cache = None
    widget._has_labels_cache = None
    widget._avg_val_cache = None
    widget._cumulative_cache = None
    widget._values_cache = None
    widget._labels_cache = None
    widget._binned_data_cache = None


def invalidate_caches_impl(widget):
    widget._invalidate_data_caches()


def trace_activity_state_impl(widget, event_name, **fields):
    return


def update_data_impl(
    widget,
    new_data,
    adaptive_binning=None,
    transition_mode=None,
    transition_align_right=None,
):
    def _row_total(rows):
        return sum(float(d[1] if isinstance(d, (list, tuple)) else d) for d in (rows or []))

    old_data = list(widget._full_data or [])
    new_data = list(new_data or [])
    begin_mode_switch(widget)
    if adaptive_binning is not None:
        widget.adaptive_binning = adaptive_binning

    _src_old, _src_new = zoom_slice_for_update(widget, old_data, new_data)
    old_display = widget._compute_display_data(_src_old)
    new_display = widget._compute_display_data(_src_new)
    next_align_right = resolve_transition_align_right(transition_mode, transition_align_right)

    if transition_update_is_redundant(
        widget,
        new_display,
        next_align_right,
        new_attr="_transition_new_data",
    ):
        commit_chart_data_update(widget, new_data)
        widget.update()
        return

    old_total, new_total = apply_transition_state(
        widget,
        old_display,
        new_display,
        next_align_right,
        old_attr="_transition_old_data",
        new_attr="_transition_new_data",
        total_getter=_row_total,
    )
    old_max = max((float(d[1] if isinstance(d, (list, tuple)) else d) for d in widget._transition_old_data), default=0.0)
    new_max = max((float(d[1] if isinstance(d, (list, tuple)) else d) for d in widget._transition_new_data), default=0.0)
    widget._trace_activity_state(
        "update_data",
        transition_mode=transition_mode,
        align_right=widget._transition_align_right,
        global_mode=widget._global_transition_mode,
        rel_height=bool(widget._relative_height_transition),
        old_len=len(widget._transition_old_data),
        new_len=len(widget._transition_new_data),
        old_total=round(old_total, 3),
        new_total=round(new_total, 3),
        old_max=round(old_max, 3),
        new_max=round(new_max, 3),
        show_avg=bool(getattr(widget, "avg_visible", True)),
        avg_on_active=bool(getattr(widget, "avg_on_active_days", False)),
        show_total=bool(getattr(widget, "cumulative_visible", False)),
    )
    commit_chart_data_update(widget, new_data)
    did_animate = animate_transition_update(
        widget,
        transition_mode,
        old_attr="_transition_old_data",
        new_attr="_transition_new_data",
    )
    if not did_animate:
        widget._finalize_data_transition()
    widget.update()


def _interp_padded_values(widget, old_rows, new_rows):
    def _val(item):
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            return float(item[1] or 0.0)
        return float(item or 0.0)

    return pad_transition_values(
        old_rows,
        new_rows,
        to_value=_val,
        align_right=widget._transition_align_right,
    )


def interpolate_relative_height_values_impl(widget, t):
    old_rows = list(widget._transition_old_data or [])
    new_rows = list(widget._transition_new_data or [])
    old_vals, new_vals, n = _interp_padded_values(widget, old_rows, new_rows)
    if n <= 0:
        return []

    old_max = safe_positive_max(old_vals)
    new_max = safe_positive_max(new_vals)

    out = []
    for i in range(n):
        old_norm = old_vals[i] / old_max
        new_norm = new_vals[i] / new_max
        out.append(max(0.0, widget.interpolate_scalar(old_norm, new_norm, t)))
    return out


def interpolate_relative_cumulative_impl(widget, t):
    old_rows = list(widget._transition_old_data or [])
    new_rows = list(widget._transition_new_data or [])
    old_vals, new_vals, n = _interp_padded_values(widget, old_rows, new_rows)
    if n <= 0:
        return []

    old_cum = build_cumulative_values(old_vals)
    new_cum = build_cumulative_values(new_vals)

    old_end = safe_positive_max([old_cum[-1]] if old_cum else [])
    new_end = safe_positive_max([new_cum[-1]] if new_cum else [])

    out = []
    for i in range(n):
        old_norm = old_cum[i] / old_end
        new_norm = new_cum[i] / new_end
        out.append(max(0.0, widget.interpolate_scalar(old_norm, new_norm, t)))
    return out


def finalize_data_transition_impl(widget):
    return finalize_transition_state(
        widget,
        old_attr="_transition_old_data",
        new_attr="_transition_new_data",
    )
