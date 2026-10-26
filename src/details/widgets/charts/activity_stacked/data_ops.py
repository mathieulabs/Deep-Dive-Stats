# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from ...chart_utils import ChartGeometry
from ...chart_utils.binning import get_bin_size
from ..common.core import set_flag_and_update
from ..common.metric import (
    animate_transition_update,
    apply_transition_state,
    axis_value_formatter_for_mode_impl,
    axis_value_formatter_impl,
    begin_mode_switch,
    binning_active_getter,
    build_cumulative_values,
    commit_chart_data_update,
    zoom_slice_for_update,
    finalize_transition_state,
    format_metric_value_impl,
    is_time_mode_impl,
    pad_transition_rows,
    resolve_transition_align_right,
    safe_positive_max,
    set_chart_opacity_impl,
    set_show_stats_impl,
    set_value_mode_impl as set_common_value_mode_impl,
    set_zoom_range_impl,
    transition_update_is_redundant,
)
from ....logic.logger import log_swallowed


def get_margins_impl(widget):
    if widget._margin_cache:
        return widget._margin_cache

    totals = widget._get_totals()
    max_val = max(totals) if totals else 1
    fmt = widget._axis_value_formatter if widget._is_time_mode() else None
    margin_left = ChartGeometry.calculate_dynamic_left_margin(widget.fontMetrics(), max_val, value_formatter=fmt)
    margin_right = ChartGeometry.calculate_dynamic_right_margin(
        widget.fontMetrics(),
        totals,
        getattr(widget, "cumulative_visible", False),
        value_formatter=fmt,
    )
    widget._margin_cache = (margin_left, margin_right)
    return margin_left, margin_right


def set_cumulative_mode_impl(widget, visible):
    return set_flag_and_update(widget, "cumulative_visible", visible)


def refresh_data_colors_impl(widget):
    try:
        from aqt import mw
        from ....ui import Config, ConfigManager, get_color

        cfg = ConfigManager(mw).config
        color_map = {
            "mature": get_color(cfg, Config.COLOR_MATURE, widget),
            "young": get_color(cfg, Config.COLOR_YOUNG, widget),
            "relearn": get_color(cfg, Config.COLOR_RELEARN, widget),
            "learn": get_color(cfg, Config.COLOR_LEARN, widget),
            "cram": get_color(cfg, Config.COLOR_CRAM, widget),
        }
        for sc in widget.series_config:
            key = str(sc.get("key") or "")
            key = key[: -len("_count")] if key.endswith("_count") else key  # series keys are "young_count", ...
            if key in color_map:
                sc["color"] = color_map[key]
        widget.update()
    except Exception:
        log_swallowed()


def set_average_mode_impl(widget, visible, on_active_days):
    widget.avg_visible = visible
    widget.avg_on_active_days = on_active_days
    widget._avg_cache = None
    widget.update()


def set_value_mode_impl(widget, mode):
    return set_common_value_mode_impl(widget, mode, track_mode_switch=True)



def invalidate_data_caches_impl(widget):
    widget._totals_cache = None
    widget._avg_cache = None
    widget._cumulative_cache = None
    widget._margin_cache = None
    widget._binned_data_cache = None
    widget._path_cache = {}
    widget._get_totals()
    if widget.avg_visible:
        widget._get_avg()


def compute_display_data_impl(widget, source_data):
    source_data = source_data or []
    if not widget.binning_active:
        return source_data
    # A zoom animation draws with a fixed bin size (see chart_utils.zoom_camera).
    bs = getattr(widget, "_forced_bin_step", None) or get_bin_size(len(source_data))
    if bs <= 1:
        return source_data

    binned = []
    for i in range(0, len(source_data), bs):
        chunk = source_data[i : i + bs]
        binned_item = {}
        for config in widget.series_config:
            key = config["key"]
            binned_item[key] = sum(item.get(key, 0) for item in chunk)

        first_label = chunk[0].get("pretty_date", "")
        last_label = chunk[-1].get("pretty_date", "")
        if first_label and last_label and first_label != last_label:
            binned_item["pretty_date"] = f"{first_label} - {last_label}"
        else:
            binned_item["pretty_date"] = first_label or ""
        binned.append(binned_item)
    return binned


def get_display_data_impl(widget):
    if widget._binned_data_cache is not None:
        return widget._binned_data_cache
    widget._binned_data_cache = widget._compute_display_data(widget.data)
    return widget._binned_data_cache


def get_totals_impl(widget):
    if widget._totals_cache is not None:
        return widget._totals_cache
    display_data = widget._get_display_data()
    totals = []
    for item in display_data:
        total = 0
        for config in widget.series_config:
            total += item.get(config["key"], 0)
        totals.append(total)
    widget._totals_cache = totals
    return totals


def get_avg_impl(widget):
    if widget._avg_cache is not None:
        return widget._avg_cache
    totals = widget._get_totals()
    if not totals:
        widget._avg_cache = 0
        return 0
    if getattr(widget, "avg_on_active_days", False):
        source_totals = totals if widget.binning_active else [
            sum(item.get(config["key"], 0) for config in widget.series_config)
            for item in (widget.data or [])
        ]
        non_zeros = [v for v in source_totals if v > 0]
        avg = sum(non_zeros) / len(non_zeros) if non_zeros else 0
    else:
        avg = sum(totals) / len(totals)
    widget._avg_cache = avg
    return avg


def get_stats_text_impl(widget):
    total = 0
    counts = []
    for item in widget.data:
        day_total = sum(item.get(config["key"], 0) for config in widget.series_config)
        total += day_total
        counts.append(day_total)

    if getattr(widget, "avg_on_active_days", False):
        non_zeros = [v for v in counts if v > 0]
        avg = sum(non_zeros) / len(non_zeros) if non_zeros else 0
    else:
        avg = sum(counts) / len(counts) if counts else 0

    stats = [f"Total: {widget._format_metric_value(total, compact=False)}"]
    if avg > 0:
        stats.append(f"Avg: {widget._format_metric_value(avg, per_day=True, compact=False)}")
    return stats


def get_cumulative_impl(widget):
    if widget._cumulative_cache is not None:
        return widget._cumulative_cache
    totals = widget._get_totals()
    cum = []
    run_sum = 0
    for t in totals:
        run_sum += t
        cum.append(run_sum)
    widget._cumulative_cache = cum
    return cum


def invalidate_geometry_caches_impl(widget):
    widget._margin_cache = None


def invalidate_all_data_caches_impl(widget):
    widget._invalidate_geometry_caches()
    widget._totals_cache = None
    widget._avg_cache = None
    widget._cumulative_cache = None
    widget._binned_data_cache = None


def invalidate_caches_impl(widget):
    widget._invalidate_data_caches()


def update_data_impl(
    widget,
    new_data,
    adaptive_binning=None,
    transition_mode=None,
    transition_align_right=None,
):
    keys = [cfg["key"] for cfg in widget.series_config]

    def _row_total(rows):
        return sum(sum(float(row.get(k, 0) or 0.0) for k in keys) for row in (rows or []))

    old_data = list(widget._full_data or [])
    new_data = list(new_data or [])
    pending_mode_switch = begin_mode_switch(widget)
    if adaptive_binning is not None:
        widget.adaptive_binning = adaptive_binning

    _src_old, _src_new = zoom_slice_for_update(widget, old_data, new_data)
    old_display = widget._compute_display_data(_src_old)
    new_display = widget._compute_display_data(_src_new)
    next_align_right = resolve_transition_align_right(transition_mode, transition_align_right)
    if (
        pending_mode_switch
        and len(pending_mode_switch) == 2
        and transition_mode is None
        and list(old_display or []) == list(new_display or [])
    ):
        widget._transition_old_value_mode = widget.value_mode
        widget._transition_new_value_mode = widget.value_mode
        widget._finalize_data_transition()
        commit_chart_data_update(widget, new_data)
        widget.update()
        return
    if transition_update_is_redundant(
        widget,
        new_display,
        next_align_right,
        new_attr="_transition_new_display_data",
    ):
        commit_chart_data_update(widget, new_data)
        widget.update()
        return

    apply_transition_state(
        widget,
        old_display,
        new_display,
        next_align_right,
        old_attr="_transition_old_display_data",
        new_attr="_transition_new_display_data",
        total_getter=_row_total,
    )
    commit_chart_data_update(widget, new_data)
    did_animate = animate_transition_update(
        widget,
        transition_mode,
        old_attr="_transition_old_display_data",
        new_attr="_transition_new_display_data",
    )
    if not did_animate:
        widget._finalize_data_transition()
    widget.update()


def finalize_data_transition_impl(widget):
    return finalize_transition_state(
        widget,
        old_attr="_transition_old_display_data",
        new_attr="_transition_new_display_data",
    )


def interpolate_relative_height_rows_impl(widget, t):
    old_rows = list(widget._transition_old_display_data or [])
    new_rows = list(widget._transition_new_display_data or [])
    old_rows, new_rows, n = pad_transition_rows(
        old_rows,
        new_rows,
        align_right=widget._transition_align_right,
    )
    if n <= 0:
        return []

    keys = [cfg["key"] for cfg in widget.series_config]
    old_max = safe_positive_max([sum(float(row.get(k, 0) or 0.0) for k in keys) for row in old_rows])
    new_max = safe_positive_max([sum(float(row.get(k, 0) or 0.0) for k in keys) for row in new_rows])

    out = []
    for i in range(n):
        old_item = old_rows[i]
        new_item = new_rows[i]
        row = {"pretty_date": new_item.get("pretty_date", old_item.get("pretty_date", ""))}
        for key in keys:
            old_norm = float(old_item.get(key, 0) or 0.0) / old_max
            new_norm = float(new_item.get(key, 0) or 0.0) / new_max
            row[key] = max(0.0, widget.interpolate_scalar(old_norm, new_norm, t))
        out.append(row)
    return out


def interpolate_relative_cumulative_impl(widget, t):
    old_rows = list(widget._transition_old_display_data or [])
    new_rows = list(widget._transition_new_display_data or [])
    old_rows, new_rows, n = pad_transition_rows(
        old_rows,
        new_rows,
        align_right=widget._transition_align_right,
    )
    if n <= 0:
        return []

    keys = [cfg["key"] for cfg in widget.series_config]
    old_totals = [sum(float(row.get(k, 0) or 0.0) for k in keys) for row in old_rows]
    new_totals = [sum(float(row.get(k, 0) or 0.0) for k in keys) for row in new_rows]

    old_cum = build_cumulative_values(old_totals)
    new_cum = build_cumulative_values(new_totals)

    old_end = safe_positive_max([old_cum[-1]] if old_cum else [])
    new_end = safe_positive_max([new_cum[-1]] if new_cum else [])

    out = []
    for i in range(n):
        old_norm = old_cum[i] / old_end
        new_norm = new_cum[i] / new_end
        out.append(max(0.0, widget.interpolate_scalar(old_norm, new_norm, t)))
    return out
