# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from ....animations.chart_policy import chart_animations_allowed
from aqt.qt import QWidget


_UNSET = object()


def set_end_date_impl(widget, date):
    previous_end = getattr(widget, "end_date", None)
    if previous_end is not None and previous_end == date and not getattr(widget, "_mode_transition_active", False):
        # same window as before; keep every cached pixmap.
        return
    widget.end_date = date
    widget._grid_cache = None
    widget._pixmap_cache = None
    widget._labels_pixmap_cache = None
    widget._labels_pixmap_cache_key = None
    widget._cont_layout_cache = None
    if widget._mode_transition_active:
        # Mode transitions capture the old and new cell geometry up front. For
        # year <-> 365 the target layout depends on end_date, usually set right after
        # set_view_mode(), so refresh the "new" side here.
        _retarget_mode_transition(widget)
        widget._mode_transition_new_labels_pixmap = widget._render_labels_to_pixmap()
        widget._mode_transition_new_scaffold_pixmap = widget._render_scaffold_to_pixmap()
    widget.update()


def _retarget_mode_transition(widget):
    """Point a running mode transition at the current data and geometry.

    The cell pairs must follow, otherwise cells that only exist in the new data
    (late future-due counts, a window shifted after set_view_mode) are missing
    from the animation and pop in when it ends.
    """
    widget._mode_transition_new_cells = widget._build_current_cell_visuals(widget.data)
    old_cells = widget._mode_transition_old_cells or {}
    new_cells = widget._mode_transition_new_cells or {}
    keys = set(old_cells.keys()) | set(new_cells.keys())
    widget._mode_transition_cell_pairs = [(old_cells.get(key), new_cells.get(key)) for key in keys]
    widget._mode_transition_draw_ops = None


def update_data_impl(widget, new_data):
    """Update heatmap data and repaint."""
    next_data = new_data if isinstance(new_data, dict) else dict(new_data)
    old_data = widget.data if isinstance(widget.data, dict) else dict(widget.data)
    force_transition = bool(getattr(widget, "_force_next_data_transition", False))
    widget._force_next_data_transition = False

    def _has_meaningful_entries(data_map):
        try:
            for k in (data_map or {}).keys():
                reviews, future = widget._entry_counts(data_map, k)
                if float(reviews or 0.0) > 0.0 or float(future or 0.0) > 0.0:
                    return True
        except Exception:
            return False
        return False

    old_meaningful = _has_meaningful_entries(old_data)
    new_meaningful = _has_meaningful_entries(next_data)
    pinned_animation_key = None
    pinned_key_getter = getattr(widget, "_get_pinned_animation_key", None)
    if callable(pinned_key_getter):
        try:
            pinned_animation_key = pinned_key_getter()
        except Exception:
            pinned_animation_key = None

    if widget._nav_transition_active:
        widget._nav_transition_anim.stop()
        widget._clear_nav_transition_state()
    if widget._mode_transition_active:
        # The mode switch already animates; don't leave the "no animation" flag armed for the next real data change.
        widget._suppress_next_transition = False
        widget.data = next_data
        _retarget_mode_transition(widget)
        widget._pixmap_cache = None
        widget.update()
        return
    if widget._suppress_next_transition:
        widget._suppress_next_transition = False
        widget._data_transition_anim.stop()
        widget._clear_data_transition_state()
        widget.data = next_data
        widget._pixmap_cache = None
        widget._labels_pixmap_cache = None
        widget._labels_pixmap_cache_key = None
        widget.update()
        return
    if old_data == next_data:
        widget.data = next_data
        widget._pixmap_cache = None
        widget._labels_pixmap_cache = None
        widget._labels_pixmap_cache_key = None
        widget.update()
        return
    if (not bool(getattr(widget, "_initial_animation_done", False))) and (not old_meaningful) and new_meaningful and (not pinned_animation_key):
        widget._data_transition_anim.stop()
        widget._clear_data_transition_state()
        widget.data = next_data
        widget._pixmap_cache = None
        widget.maybe_start_initial_animation()
        widget.update()
        return
    delta_ratio = widget._visual_delta_ratio(old_data, next_data)
    if (delta_ratio < 0.015) and (not force_transition):
        widget._data_transition_anim.stop()
        widget._clear_data_transition_state()
        widget.data = next_data
        widget._pixmap_cache = None
        widget.update()
        return
    widget._data_transition_anim.stop()
    widget._transition_old_data = dict(old_data)
    widget._transition_new_data = dict(next_data)
    widget._data_transition_active = True
    widget._transition_progress = 0.0
    widget.data = next_data
    widget._transition_old_cells = widget._build_current_cell_visuals(widget._transition_old_data)
    widget._transition_new_cells = widget._build_current_cell_visuals(widget._transition_new_data)
    keys = set(widget._transition_old_cells.keys()) | set(widget._transition_new_cells.keys())
    widget._transition_cell_pairs = [
        (widget._transition_old_cells.get(key), widget._transition_new_cells.get(key))
        for key in keys
    ]
    widget._transition_draw_ops = None
    widget._transition_old_pixmap = widget._render_to_pixmap(widget._transition_old_data)
    widget._transition_new_pixmap = widget._render_to_pixmap(widget._transition_new_data)
    # The fade only repaints a few hundred cells, so it keeps running with many charts on screen (the usual 6-chart limit would make the cells jump on a busy page).
    if chart_animations_allowed(widget, max_visible_charts=24):
        widget._data_transition_anim.start()
    else:
        widget._on_data_transition_finished()
    widget._pixmap_cache = None
    widget.update()


def set_empty_opacity_impl(widget, opacity_pct):
    # the pinned dashboard re-applies every heatmap setting after each
    # rebuild; skip the cache invalidation + full re-render when nothing changed.
    if getattr(widget, 'current_opacity_pct', _UNSET) == opacity_pct:
        # Value unchanged, but the derived colours also depend on light/dark
        # mode; _update_empty_color() is itself a no-op when nothing changed.
        widget._update_empty_color()
        return
    widget.current_opacity_pct = opacity_pct
    widget._update_empty_color()


def set_empty_white_impl(widget, white):
    if getattr(widget, 'empty_white', _UNSET) == white:
        widget._update_empty_color()
        return
    widget.empty_white = white
    widget._update_empty_color()


def set_filled_opacity_impl(widget, opacity_pct):
    if getattr(widget, 'filled_opacity_pct', _UNSET) == opacity_pct:
        widget._update_levels()
        return
    widget.filled_opacity_pct = opacity_pct
    widget._update_levels()


def set_scale_impl(widget, scale_pct):
    if getattr(widget, 'scale', _UNSET) == scale_pct / 100.0:
        # Unchanged: still make sure the height constraint is applied
        # (cheap, no re-render), but keep all cached pixmaps.
        widget.setMinimumHeight(widget.heightForWidth(widget.width()))
        return
    widget.scale = scale_pct / 100.0
    widget.updateGeometry()
    h = widget.heightForWidth(widget.width())
    widget.setMinimumHeight(h)
    widget._grid_cache = None
    widget._pixmap_cache = None
    widget._labels_pixmap_cache = None
    widget._labels_pixmap_cache_key = None
    widget.update()


def set_show_legend_impl(widget, show):
    show = bool(show)
    if bool(getattr(widget, "show_legend", False)) == show:
        return
    widget.show_legend = show
    widget._grid_cache = None
    widget._cont_layout_cache = None
    widget._pixmap_cache = None
    widget.updateGeometry()
    widget.setMinimumHeight(widget.heightForWidth(widget.width()))
    widget.update()


def set_hide_labels_impl(widget, hide):
    if getattr(widget, 'hide_labels', _UNSET) == hide:
        widget.setMinimumHeight(widget.heightForWidth(widget.width()))
        return
    widget.hide_labels = hide
    widget._grid_cache = None
    widget._cont_layout_cache = None
    widget._pixmap_cache = None
    widget._labels_pixmap_cache = None
    widget._labels_pixmap_cache_key = None
    widget.updateGeometry()
    h = widget.heightForWidth(widget.width())
    widget.setMinimumHeight(h)
    widget.update()


def set_monday_first_impl(widget, monday_first):
    if getattr(widget, 'monday_first', _UNSET) == monday_first:
        return
    widget.monday_first = monday_first
    widget._grid_cache = None
    widget._pixmap_cache = None
    widget._labels_pixmap_cache = None
    widget._labels_pixmap_cache_key = None
    widget._cont_layout_cache = None
    widget.update()


def set_tinted_future_impl(widget, tinted):
    if getattr(widget, 'tinted_future', _UNSET) == tinted:
        widget._update_levels()
        return
    widget.tinted_future = tinted
    widget._update_levels()


def set_show_future_impl(widget, show):
    if getattr(widget, 'show_future', _UNSET) == show:
        return
    widget.show_future = show
    widget._pixmap_cache = None
    widget.update()


def set_color_levels_impl(widget, levels):
    if getattr(widget, 'color_levels', _UNSET) == max(2, levels):
        widget._update_levels()
        return
    widget.color_levels = max(2, levels)
    widget._update_levels()


def set_vibrance_impl(widget, vibrance_pct):
    if getattr(widget, 'vibrance', _UNSET) == vibrance_pct:
        widget._update_levels()
        return
    widget.vibrance = vibrance_pct
    widget._update_levels()


def set_rounding_impl(widget, rounding_pct):
    if getattr(widget, 'rounding', _UNSET) == rounding_pct:
        return
    widget.rounding = rounding_pct
    widget._pixmap_cache = None
    widget.update()


def set_intensity_curve_impl(widget, intensity_pct):
    if getattr(widget, 'intensity_curve', _UNSET) == intensity_pct:
        return
    widget.intensity_curve = intensity_pct
    widget._pixmap_cache = None
    widget.update()


def set_multi_hue_intensity_impl(widget, enabled):
    if getattr(widget, 'multi_hue_intensity', _UNSET) == bool(enabled):
        widget._update_levels()
        return
    widget.multi_hue_intensity = bool(enabled)
    widget._update_levels()


def set_metric_impl(widget, metric):
    from .metrics import normalize_metric

    metric = normalize_metric(metric)
    if getattr(widget, "metric", "reviews") == metric:
        return
    widget.metric = metric
    widget._data_transition_anim.stop()
    widget._clear_data_transition_state()
    widget._pixmap_cache = None
    widget._transition_old_pixmap = None
    widget._transition_new_pixmap = None
    widget.update()


def set_invert_intensity_impl(widget, invert):
    invert = bool(invert)
    if getattr(widget, "invert_intensity", False) == invert:
        return
    widget.invert_intensity = invert
    widget._update_levels()


def set_view_mode_impl(widget, mode):
    if mode == widget.view_mode:
        return

    widget._data_transition_anim.stop()
    widget._clear_data_transition_state()
    widget._nav_transition_anim.stop()
    widget._clear_nav_transition_state()

    widget._mode_transition_anim.stop()
    old_cells = widget._build_current_cell_visuals(widget.data)
    widget._mode_transition_old_labels_pixmap = widget._render_labels_to_pixmap()
    widget._mode_transition_old_scaffold_pixmap = widget._render_scaffold_to_pixmap()

    widget.view_mode = mode
    widget._suppress_next_transition = False
    widget.cont_month_offset = 0
    widget._grid_cache = None
    widget._pixmap_cache = None
    widget._labels_pixmap_cache = None
    widget._labels_pixmap_cache_key = None
    widget._cont_layout_cache = None
    widget.updateGeometry()
    h = widget.heightForWidth(widget.width())
    widget.setMinimumHeight(h)
    new_cells = widget._build_current_cell_visuals(widget.data)
    widget._mode_transition_new_labels_pixmap = widget._render_labels_to_pixmap()
    widget._mode_transition_new_scaffold_pixmap = widget._render_scaffold_to_pixmap()

    widget._mode_transition_old_cells = old_cells
    widget._mode_transition_new_cells = new_cells
    keys = set(old_cells.keys()) | set(new_cells.keys())
    widget._mode_transition_cell_pairs = [
        (old_cells.get(key), new_cells.get(key))
        for key in keys
    ]
    widget._mode_transition_draw_ops = None
    widget._mode_transition_active = True
    widget._mode_transition_progress = 0.0
    if chart_animations_allowed(widget):
        widget._mode_transition_anim.start()
    else:
        widget._on_mode_transition_finished()
    widget.update()


def shift_continuous_impl(widget, delta):
    widget.cont_month_offset += delta
    widget._pixmap_cache = None
    widget._labels_pixmap_cache = None
    widget._labels_pixmap_cache_key = None
    widget.update()


def resize_event_impl(widget, event):
    QWidget.resizeEvent(widget, event)

    req_h = widget.heightForWidth(widget.width())
    min_h = 40 if widget.grid_mode else req_h
    if widget.minimumHeight() != min_h:
        widget.setMinimumHeight(min_h)

    widget._grid_cache = None
    widget._pixmap_cache = None
    widget._labels_pixmap_cache = None
    widget._labels_pixmap_cache_key = None
    widget._cont_layout_cache = None
    widget._data_transition_anim.stop()
    widget._clear_data_transition_state()
    widget._nav_transition_anim.stop()
    widget._clear_nav_transition_state()
    widget._mode_transition_anim.stop()
    widget._clear_mode_transition_state()
    widget.update()


def _current_frame_cells(widget):
    """Cell visuals as currently on screen, mid-animation included."""
    from aqt.qt import QColor, QRectF

    if getattr(widget, "_mode_transition_active", False):
        t = max(0.0, min(1.0, float(getattr(widget, "_mode_transition_progress", 1.0))))
        tt = t * t * (3.0 - (2.0 * t))
        old_cells = widget._mode_transition_old_cells or {}
        new_cells = widget._mode_transition_new_cells or {}
        out = {}
        for key in set(old_cells.keys()) | set(new_cells.keys()):
            old_item = old_cells.get(key)
            new_item = new_cells.get(key)
            if old_item and new_item:
                (o_rect, o_col), (n_rect, n_col) = old_item, new_item
                rect = QRectF(
                    widget._lerp(o_rect.x(), n_rect.x(), tt),
                    widget._lerp(o_rect.y(), n_rect.y(), tt),
                    widget._lerp(o_rect.width(), n_rect.width(), tt),
                    widget._lerp(o_rect.height(), n_rect.height(), tt),
                )
                out[key] = (rect, QColor(widget._lerp_color(o_col, n_col, tt)))
            elif old_item:
                rect, col = old_item
                c = QColor(col)
                c.setAlpha(int(col.alpha() * (1.0 - tt)))
                out[key] = (rect, c)
            else:
                rect, col = new_item
                c = QColor(col)
                c.setAlpha(int(col.alpha() * tt))
                out[key] = (rect, c)
        return out
    if getattr(widget, "_data_transition_active", False):
        t = max(0.0, min(1.0, float(getattr(widget, "_transition_progress", 1.0))))
        return widget._build_current_cell_visuals(widget._interpolate_data_map(t))
    return widget._build_current_cell_visuals(widget.data)


def set_hidden_legend_steps_impl(widget, steps):
    """Hide (or show again) the days of some legend ranges, fading the cells."""
    steps = frozenset(steps)
    if steps == getattr(widget, "hidden_legend_steps", frozenset()):
        return

    old_cells = _current_frame_cells(widget)
    if getattr(widget, "_mode_transition_active", False) and widget._mode_transition_new_labels_pixmap is not None:
        old_labels = widget._mode_transition_new_labels_pixmap
    else:
        old_labels = widget._render_labels_to_pixmap()

    widget._data_transition_anim.stop()
    widget._clear_data_transition_state()
    widget._nav_transition_anim.stop()
    widget._clear_nav_transition_state()
    widget._mode_transition_anim.stop()

    widget.hidden_legend_steps = steps
    widget._grid_cache = None
    widget._pixmap_cache = None
    widget._labels_pixmap_cache = None
    widget._labels_pixmap_cache_key = None
    widget._cont_layout_cache = None

    new_cells = widget._build_current_cell_visuals(widget.data)
    widget._mode_transition_old_cells = old_cells
    widget._mode_transition_new_cells = new_cells
    widget._mode_transition_old_labels_pixmap = old_labels
    widget._mode_transition_new_labels_pixmap = widget._render_labels_to_pixmap()
    widget._mode_transition_old_scaffold_pixmap = None
    widget._mode_transition_new_scaffold_pixmap = widget._render_scaffold_to_pixmap()
    keys = set(old_cells.keys()) | set(new_cells.keys())
    widget._mode_transition_cell_pairs = [(old_cells.get(k), new_cells.get(k)) for k in keys]
    widget._mode_transition_draw_ops = None
    widget._mode_transition_active = True
    widget._mode_transition_progress = 0.0
    if chart_animations_allowed(widget):
        widget._mode_transition_anim.start()
    else:
        widget._on_mode_transition_finished()
    widget.update()


def toggle_legend_step_impl(widget, step):
    hidden = set(getattr(widget, "hidden_legend_steps", None) or ())
    hidden.symmetric_difference_update({step})
    set_hidden_legend_steps_impl(widget, hidden)


def transition_to_impl(widget, new_data, end_date):
    """Animate to new_data over the window ending at end_date.

    Same window: days entering or leaving the range fade. New window (another
    year, or shifted 365 days): every cell moves or fades and the labels
    cross-fade.
    """
    next_data = new_data if isinstance(new_data, dict) else dict(new_data or {})
    same_window = getattr(widget, "end_date", None) == end_date
    if getattr(widget, "view_mode", "year") == "continuous" or (
        same_window and not getattr(widget, "_mode_transition_active", False)
    ):
        if getattr(widget, "_data_transition_active", False):
            # Retarget from the frame on screen instead of jumping to the old target.
            t = max(0.0, min(1.0, float(getattr(widget, "_transition_progress", 1.0))))
            widget.data = widget._interpolate_data_map(t)
        widget._suppress_next_transition = False
        update_data_impl(widget, next_data)
        if not same_window:
            set_end_date_impl(widget, end_date)
        return

    old_cells = _current_frame_cells(widget)
    if getattr(widget, "_mode_transition_active", False) and widget._mode_transition_new_labels_pixmap is not None:
        old_labels = widget._mode_transition_new_labels_pixmap
    else:
        old_labels = widget._render_labels_to_pixmap()

    widget._data_transition_anim.stop()
    widget._clear_data_transition_state()
    widget._nav_transition_anim.stop()
    widget._clear_nav_transition_state()
    widget._mode_transition_anim.stop()

    widget._suppress_next_transition = False
    widget.data = next_data
    widget.end_date = end_date
    widget._grid_cache = None
    widget._pixmap_cache = None
    widget._labels_pixmap_cache = None
    widget._labels_pixmap_cache_key = None
    widget._cont_layout_cache = None

    new_cells = widget._build_current_cell_visuals(next_data)
    widget._mode_transition_old_cells = old_cells
    widget._mode_transition_new_cells = new_cells
    widget._mode_transition_old_labels_pixmap = old_labels
    widget._mode_transition_new_labels_pixmap = widget._render_labels_to_pixmap()
    widget._mode_transition_old_scaffold_pixmap = None
    widget._mode_transition_new_scaffold_pixmap = widget._render_scaffold_to_pixmap()
    keys = set(old_cells.keys()) | set(new_cells.keys())
    widget._mode_transition_cell_pairs = [(old_cells.get(k), new_cells.get(k)) for k in keys]
    widget._mode_transition_draw_ops = None
    widget._mode_transition_active = True
    widget._mode_transition_progress = 0.0
    if chart_animations_allowed(widget):
        widget._mode_transition_anim.start()
    else:
        widget._on_mode_transition_finished()
    widget.update()
