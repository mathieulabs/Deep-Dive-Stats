# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QWidget

from .data_ops import current_value_range
from .series import SERIES_KEYS
from ...chart_utils import ChartGeometry, ZoomableMixin, get_theme_colors
from ...chart_utils.formatting import fmt_num, fmt_num_compact
from ...chart_utils.tooltip import (
    hide_tooltip_targets,
    hide_tooltips_on_window_deactivate,
    show_floating_label_at_y,
    show_tooltip_near,
)


def _plot_left_margin(widget):
    """Left margin of the plot as painted, which follows the value axis range."""
    min_val, max_val = current_value_range(widget)
    return ChartGeometry.calculate_dynamic_left_margin(widget.fontMetrics(), max_val, min_val=min_val)


def mouse_move_event_impl(widget, event):
    display_data = widget._get_display_data()
    if not display_data:
        return
    n = widget._get_display_n()
    if n == 0:
        return

    min_val, max_val = current_value_range(widget)
    margin_left = ChartGeometry.calculate_dynamic_left_margin(widget.fontMetrics(), max_val, min_val=min_val)
    margin_right = widget._get_margin_right(widget.fontMetrics())
    width = widget.width() - margin_left - margin_right

    show_stats = getattr(widget, "show_stats", False)
    if show_stats:
        stats = widget.get_stats_text()
        margin_bottom = ChartGeometry.calculate_stats_margin(stats, width, widget.fontMetrics())
    else:
        margin_bottom = ChartGeometry.MARGIN_BOTTOM

    margin_top = ChartGeometry.MARGIN_TOP
    plot_h = widget.height() - margin_bottom - margin_top
    if width <= 0:
        return

    if widget.handle_selection_move(event, margin_left, width):
        return

    x = event.pos().x() - margin_left
    if n > 1:
        idx = int((x / width) * (n - 1) + 0.5)
    else:
        idx = 0
    if idx < 0:
        idx = 0
    if idx >= n:
        idx = n - 1

    was_hover_index = widget.hover_index
    widget.hover_index = idx
    changed = widget.hover_index != was_hover_index
    mouse_y = event.pos().y()
    in_plot_x = (0 <= x < width)
    in_plot_y = (margin_top <= mouse_y <= (margin_top + plot_h))
    for key in widget.SERIES_CONFIG:
        y_avg = widget._get_series_avg_y(key, margin_top, plot_h, max_val, min_val=min_val)
        if y_avg is None:
            if widget.hover_avgs[key]:
                widget.hover_avgs[key] = False
                changed = True
            continue
        threshold = 14 if widget.hover_avgs[key] else 10
        is_hovering = in_plot_x and in_plot_y and abs(mouse_y - y_avg) < threshold
        if is_hovering != widget.hover_avgs[key]:
            widget.hover_avgs[key] = is_hovering
            changed = True

    if changed:
        widget.update()

    if widget.hover_index == -1:
        return

    tooltip_lines = None
    if widget.hover_index != was_hover_index or not widget.tooltip_window.isVisible():
        if widget._labels_cache is None:
            labels = []
            for k in SERIES_KEYS:
                if k in display_data and display_data[k]:
                    labels = [str(item[0]) if isinstance(item, (list, tuple)) else "" for item in display_data[k]]
                    break
            widget._labels_cache = labels
        labels = widget._labels_cache
        tooltip_lines = []
        if labels and widget.hover_index < len(labels):
            tooltip_lines.append({"text": labels[widget.hover_index], "header": True})
        for k in SERIES_KEYS:
            if widget.visible_series.get(k, False) and k in display_data:
                series_data = display_data[k]
                if widget.hover_index < len(series_data):
                    item = series_data[widget.hover_index]
                    val = item[1] if isinstance(item, (list, tuple)) else item
                    has_counts = isinstance(item, (list, tuple)) and len(item) >= 3 and item[2]
                    if val is None and not (has_counts and item[2][1]):
                        continue
                    label = widget.SERIES_CONFIG[k]["label"]
                    color = widget._get_series_color(k, widget)
                    txt = f"{label}"
                    val_str = "too few reviews" if val is None else f"{fmt_num_compact(val)}%"
                    if has_counts:
                        passed, total = item[2]
                        val_str += f" ({fmt_num(passed)}/{fmt_num(total)})"
                    tooltip_lines.append({"id": k, "text": txt, "value": val_str, "color": color})

    t_colors = get_theme_colors(widget)
    last_y_local = -100
    sorted_keys = sorted(widget.SERIES_CONFIG.keys(), key=lambda k: widget.avg_values[k] or 0.0, reverse=True)
    for key in sorted_keys:
        tooltip = widget.avg_tooltips[key]
        if widget.hover_avgs[key]:
            y_avg = widget._get_series_avg_y(key, margin_top, plot_h, max_val, min_val=min_val)
            if y_avg is None:
                tooltip.hide()
                continue
            avg_val = widget.avg_values.get(key)
            if avg_val is None:
                avg_val = 0.0
            draw_y_local = int(y_avg)
            if last_y_local != -100 and abs(draw_y_local - last_y_local) < 22:
                draw_y_local = last_y_local + 22
            m_label_left = margin_left
            show_floating_label_at_y(
                widget,
                tooltip,
                text=f"avg: {fmt_num_compact(avg_val)}%",
                y_local=draw_y_local,
                anchor_x_local=m_label_left,
                theme_colors=t_colors,
                text_color=widget._get_series_color(key, widget),
                show_only_if_hidden=True,
            )
            last_y_local = draw_y_local
        else:
            tooltip.hide()

    show_tooltip_near(
        widget,
        widget.tooltip_window,
        event.pos(),
        lines=tooltip_lines,
        x_offset=15,
        y_offset=15,
        show_only_if_hidden=True,
    )


def leave_event_impl(widget, event):
    widget.hover_index = -1
    for k in widget.hover_avgs:
        widget.hover_avgs[k] = False
    hide_tooltip_targets(widget, "tooltip_window", "avg_tooltips")
    widget.update()


def hide_event_impl(widget, event):
    hide_tooltip_targets(widget, "tooltip_window", "avg_tooltips")
    QWidget.hideEvent(widget, event)


def change_event_impl(widget, event):
    hide_tooltips_on_window_deactivate(widget, event, "tooltip_window", "avg_tooltips")
    QWidget.changeEvent(widget, event)


def wheel_event_impl(widget, event):
    min_val, max_val = current_value_range(widget)
    margin_left = ChartGeometry.calculate_dynamic_left_margin(widget.fontMetrics(), max_val, min_val=min_val)
    margin_right = widget._get_margin_right(widget.fontMetrics())
    plot_width = widget.width() - margin_left - margin_right
    if widget.handle_wheel_zoom(event, margin_left, plot_width):
        return
    QWidget.wheelEvent(widget, event)


def reset_zoom_impl(widget):
    from ...chart_utils import zoom_camera

    if not getattr(widget, "_is_zoomed", False):
        ZoomableMixin.reset_zoom(widget)
        return
    if widget.isVisible() or zoom_camera.active():
        with zoom_camera.camera_zoom(widget):
            ZoomableMixin.reset_zoom(widget)
        return

    transition_payload = None
    if widget.isVisible() and widget.width() > 0 and widget.height() > 0:
        transition_payload = widget._prepare_data_transition(widget._full_retention_data)

    if transition_payload is not None:
        (old_series, new_series, sample_count, old_labels, new_labels,
         old_display_data, new_display_data, render_cache, old_range, new_range) = transition_payload
        widget._data_transition_active = True
        widget._data_transition_old_series = old_series
        widget._data_transition_new_series = new_series
        widget._data_transition_sample_count = sample_count
        widget._data_transition_old_labels = old_labels
        widget._data_transition_new_labels = new_labels
        widget._data_transition_old_display_data = old_display_data
        widget._data_transition_new_display_data = new_display_data
        widget._data_transition_render_cache = render_cache
        widget._data_transition_old_range = old_range
        widget._data_transition_new_range = new_range
        widget._progress = 0.0

    ZoomableMixin.reset_zoom(widget)

    if transition_payload is not None:
        widget.animation.stop()
        widget.animation.setDuration(220)
        widget._progress = 0.0
        widget.animation.start()

    widget.update()


def mouse_press_event_impl(widget, event):
    margin_left = _plot_left_margin(widget)
    margin_right = widget._get_margin_right(widget.fontMetrics())
    plot_width = widget.width() - margin_left - margin_right
    if widget.handle_selection_press(event, margin_left, plot_width):
        return
    QWidget.mousePressEvent(widget, event)


def resize_event_impl(widget, event):
    QWidget.resizeEvent(widget, event)
    widget.update_scrollbar_geometry()
    widget._path_cache = {}
    widget._margin_cache = None


def set_zoom_range_impl(widget, start_idx, end_idx):
    # The mixin may clamp or refuse the range, so read the final range after it ran.
    ZoomableMixin.set_zoom_range(widget, start_idx, end_idx)
    widget._apply_zoom_to_data()


def mouse_release_event_impl(widget, event):
    margin_left = _plot_left_margin(widget)
    margin_right = widget._get_margin_right(widget.fontMetrics())
    plot_width = widget.width() - margin_left - margin_right
    if widget.handle_selection_release(event, margin_left, plot_width):
        return
    QWidget.mouseReleaseEvent(widget, event)
