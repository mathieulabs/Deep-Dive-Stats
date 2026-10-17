# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QWidget

from ....chart_utils import ZoomableMixin
from ....chart_utils.tooltip import hide_tooltip_targets, hide_tooltips_on_window_deactivate
from .....animations.chart_policy import local_chart_animation_batch
from .transition import animate_transition_update, apply_transition_state


def leave_event_impl(widget, event):
    widget.hover_index = -1
    widget.hover_avg = False
    hide_tooltip_targets(widget, "tooltip_window", "avg_tooltip")
    widget.update()


def hide_event_impl(widget, event):
    hide_tooltip_targets(widget, "tooltip_window", "avg_tooltip")
    QWidget.hideEvent(widget, event)


def change_event_impl(widget, event):
    hide_tooltips_on_window_deactivate(widget, event, "tooltip_window", "avg_tooltip")
    QWidget.changeEvent(widget, event)


def set_zoom_range_impl(widget, start_idx, end_idx):
    # The mixin may clamp or refuse the range, so read the final range after it ran.
    ZoomableMixin.set_zoom_range(widget, start_idx, end_idx)
    n = len(widget._full_data or [])
    if int(start_idx) <= 0 and int(end_idx) >= n:
        # Full range (also for 0 or 1 rows, which the mixin refuses): never keep a stale window.
        widget._zoom_start = 0
        widget._zoom_end = n
        widget._is_zoomed = False
    widget.data = widget.get_visible_data(widget._full_data)
    widget._invalidate_data_caches()
    widget.update()


def mouse_press_event_impl(widget, event):
    margin_left, margin_right = widget._get_margins()
    plot_width = widget.width() - margin_left - margin_right

    if widget.handle_selection_press(event, margin_left, plot_width):
        return
    QWidget.mousePressEvent(widget, event)


def resize_event_impl(widget, event):
    QWidget.resizeEvent(widget, event)
    widget._invalidate_geometry_caches()
    widget.update_scrollbar_geometry()


def mouse_release_event_impl(widget, event):
    margin_left, margin_right = widget._get_margins()
    plot_width = widget.width() - margin_left - margin_right

    if widget.handle_selection_release(event, margin_left, plot_width):
        return
    QWidget.mouseReleaseEvent(widget, event)


def reset_zoom_with_transition_impl(widget, *, old_attr, new_attr):
    def _row_total(rows):
        total = 0.0
        for row in (rows or []):
            if isinstance(row, dict):
                total += sum(float(v or 0.0) for v in row.values() if isinstance(v, (int, float)))
            elif isinstance(row, (list, tuple)) and len(row) >= 2:
                total += float(row[1] or 0.0)
            elif isinstance(row, (int, float)):
                total += float(row)
        return total

    from ....chart_utils import zoom_camera

    if widget.isVisible() or zoom_camera.active():
        # The zoom animation takes over: a plain reset under it.
        with zoom_camera.camera_zoom(widget):
            ZoomableMixin.reset_zoom(widget)
        return

    old_display = widget._compute_display_data(list(widget.data))
    new_display = widget._compute_display_data(list(widget._full_data))

    # If data is already at full extent (zoom_sync may have pre-reset it), skip transition
    if old_display == new_display:
        ZoomableMixin.reset_zoom(widget)
        return

    with local_chart_animation_batch(widget, [widget]):
        apply_transition_state(
            widget,
            old_display,
            new_display,
            True,
            old_attr=old_attr,
            new_attr=new_attr,
            total_getter=_row_total,
        )
        widget._progress = 0.0
        ZoomableMixin.reset_zoom(widget)
        animate_transition_update(widget, "timespan", old_attr=old_attr, new_attr=new_attr)
        widget.update()
