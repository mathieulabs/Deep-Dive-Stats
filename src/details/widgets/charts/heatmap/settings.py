# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from ....animations.chart_policy import chart_animations_allowed
from aqt.qt import QTimer, QWidget

# A click on this heatmap animates only this heatmap, so the usual limit of visible charts
# (meant for page-wide animations) would wrongly turn it off once the page is scrolled.
USER_ACTION_MAX_CHARTS = 24


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
    widget.update()


def _years_change_with(widget, next_data):
    """True when next_data shows other years than the current data (years view)."""
    from . import years_ops

    current = widget.data
    try:
        before = tuple(years_ops.years_shown(widget))
        widget.data = next_data
        after = tuple(years_ops.years_shown(widget))
    except Exception:
        return False
    finally:
        widget.data = current
    return before != after


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
    if getattr(widget, "view_mode", "") == "years" and _years_change_with(widget, next_data):
        # Another deck with other years: rows come and go and the card changes height,
        # which would cut the color fade short. The rows move instead, like a fold.
        widget._data_transition_anim.stop()
        widget._clear_data_transition_state()
        widget.data = old_data
        relayout_years_impl(widget, lambda: setattr(widget, "data", next_data))
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
    old_h = widget.height()
    try:
        from .legend import legend_rest_top

        widget._legend_top_from = legend_rest_top(widget)
    except Exception:
        widget._legend_top_from = None
    old_cells = widget._build_current_cell_visuals(widget.data)
    widget._mode_transition_old_labels_pixmap = widget._render_labels_to_pixmap()

    widget.view_mode = mode
    widget._suppress_next_transition = False
    widget.cont_month_offset = 0
    widget._grid_cache = None
    widget._pixmap_cache = None
    widget._labels_pixmap_cache = None
    widget._labels_pixmap_cache_key = None
    widget._cont_layout_cache = None
    widget.updateGeometry()
    _set_height_for_switch(widget, old_h)
    new_cells = widget._build_current_cell_visuals(widget.data)
    widget._mode_transition_new_labels_pixmap = widget._render_labels_to_pixmap()

    widget._mode_transition_old_cells = old_cells
    widget._mode_transition_new_cells = new_cells
    keys = set(old_cells.keys()) | set(new_cells.keys())
    widget._mode_transition_cell_pairs = [
        (old_cells.get(key), new_cells.get(key))
        for key in keys
    ]
    widget._mode_transition_active = True
    widget._mode_transition_progress = 0.0
    if chart_animations_allowed(widget, max_visible_charts=USER_ACTION_MAX_CHARTS):
        widget._mode_transition_anim.start()
    else:
        widget._on_mode_transition_finished()
    widget.update()


def toggle_years_fold_impl(widget):
    """Fold or unfold the older years of the years view."""
    relayout_years_impl(
        widget, lambda: setattr(widget, "_years_expanded", not bool(getattr(widget, "_years_expanded", False)))
    )


def set_years_no_gap_impl(widget, no_gap):
    """Years view without the space between the years (the button next to YRS)."""
    if bool(getattr(widget, "years_no_gap", False)) == bool(no_gap):
        return
    relayout_years_impl(widget, lambda: setattr(widget, "years_no_gap", bool(no_gap)))


def set_years_fold_impl(widget, count):
    """Years shown before the older ones fold (0: never)."""
    try:
        count = max(0, int(count))
    except (TypeError, ValueError):
        return
    if int(getattr(widget, "years_fold", 3)) == count:
        return
    relayout_years_impl(widget, lambda: setattr(widget, "years_fold", count))


def _invalidate_up(widget):
    """Every layout from the heatmap up to the main screen's area works out its height
    again (each one keeps its heightForWidth until told)."""
    w = widget
    while w is not None:
        try:
            lay = w.layout()
            if lay is not None:
                lay.invalidate()
            w.updateGeometry()
            w = w.parentWidget()
        except RuntimeError:
            return


def _follow_height_now(widget):
    """A pinned heatmap that changes height: the main screen's area that holds it follows
    at once. Left to its own timer it caught up a moment later, and meanwhile the bottom of
    the heatmap (its legend) was cut off."""
    try:
        if not widget.property("pinned_widget"):
            return
        from ...pinned.main_menu.manager import MainMenuWidgetManager

        if not MainMenuWidgetManager.instance_exists():
            return
        manager = MainMenuWidgetManager.instance()
        if getattr(manager, "_rebuild_in_progress", False):
            return  # the rebuild sizes everything when it ends
        _invalidate_up(widget)
        manager._resize_overlay()
        # Once more after Qt has laid the new height out.
        QTimer.singleShot(0, manager._resize_overlay)
    except Exception:
        pass


def _set_height_for_switch(widget, old_h):
    """The height after a switch that animates (mode, fold, gap). On the main screen the
    height goes from the old to the new one along with the cells (step_height_anim), so the
    charts under the heatmap slide with it instead of jumping at the start or the end."""
    # An animation still running (a click during the previous one, a deck change) is
    # forgotten first: heightForWidth would answer its height on the way.
    widget._height_anim = None
    widget._hold_min_height = None
    new_h = widget.heightForWidth(widget.width())
    if new_h != old_h and widget.property("pinned_widget") and chart_animations_allowed(widget, max_visible_charts=USER_ACTION_MAX_CHARTS):
        widget._height_anim = (int(old_h), int(new_h))
        widget._hold_min_height = old_h
        widget.setMinimumHeight(old_h)
        # heightForWidth above may have cached a grid placed for the current height.
        widget._grid_cache = None
        widget._cont_layout_cache = None
        return
    widget._hold_min_height = None
    widget.setMinimumHeight(new_h)
    _follow_height_now(widget)


def layout_height(widget):
    """Height the grid is placed for: the final one while the height is still on its way
    (step_height_anim). Placed for the current height, the cells changed size and place at
    each frame along with the card."""
    anim = getattr(widget, "_height_anim", None)
    if anim is not None:
        return anim[1]
    return widget.height()


def height_anim_active(widget):
    return getattr(widget, "_height_anim", None) is not None and getattr(widget, "_mode_transition_active", False)


def step_height_anim(widget):
    """One frame of the mode transition: the height follows the cells (same easing as
    the legend glide in legend.paint_legend)."""
    anim = getattr(widget, "_height_anim", None)
    if anim is None or not getattr(widget, "_mode_transition_active", False):
        return
    t = max(0.0, min(1.0, float(getattr(widget, "_mode_transition_progress", 1.0))))
    tt = t * t * (3.0 - 2.0 * t)
    h = int(round(anim[0] + (anim[1] - anim[0]) * tt))
    if h == getattr(widget, "_hold_min_height", None):
        return
    widget._hold_min_height = h
    widget.setMinimumHeight(h)
    try:
        if not widget.property("pinned_widget"):
            return
        from ...pinned.main_menu.manager import MainMenuWidgetManager

        if not MainMenuWidgetManager.instance_exists():
            return
        manager = MainMenuWidgetManager.instance()
        if getattr(manager, "_rebuild_in_progress", False):
            return
        _invalidate_up(widget)
        manager._resize_overlay()
    except Exception:
        pass


def release_height_hold(widget):
    """End of the animation: the height kept for it goes to the new one."""
    if getattr(widget, "_height_anim", None) is not None:
        widget._height_anim = None
        widget._grid_cache = None
        widget._cont_layout_cache = None
    if getattr(widget, "_hold_min_height", None) is None:
        return
    widget._hold_min_height = None
    widget.updateGeometry()
    widget.setMinimumHeight(widget.heightForWidth(widget.width()))
    _follow_height_now(widget)


def relayout_years_impl(widget, change):
    """Apply change() to the years view. The cells move to their new place and the years
    that come or go fade, with the animation of a mode switch. In another view, change()
    is only stored for later."""
    if getattr(widget, "view_mode", "") != "years":
        change()
        return
    widget._data_transition_anim.stop()
    widget._clear_data_transition_state()
    widget._mode_transition_anim.stop()
    old_h = widget.height()
    try:
        from .legend import legend_rest_top

        widget._legend_top_from = legend_rest_top(widget)
    except Exception:
        widget._legend_top_from = None
    old_cells = widget._build_current_cell_visuals(widget.data)
    widget._mode_transition_old_labels_pixmap = widget._render_labels_to_pixmap()
    try:
        from . import years_ops

        label_from = years_ops.row_tops(widget)
    except Exception:
        label_from = None

    change()
    widget._years_scroll = 0.0
    widget._pixmap_cache = None
    widget._labels_pixmap_cache = None
    widget._labels_pixmap_cache_key = None
    widget.updateGeometry()
    _set_height_for_switch(widget, old_h)
    new_cells = widget._build_current_cell_visuals(widget.data)
    widget._mode_transition_new_labels_pixmap = widget._render_labels_to_pixmap()

    widget._mode_transition_old_cells = old_cells
    widget._mode_transition_new_cells = new_cells
    keys = set(old_cells.keys()) | set(new_cells.keys())
    widget._mode_transition_cell_pairs = [(old_cells.get(key), new_cells.get(key)) for key in keys]
    widget._mode_transition_active = True
    widget._mode_transition_progress = 0.0
    widget._years_label_from = label_from
    if chart_animations_allowed(widget, max_visible_charts=USER_ACTION_MAX_CHARTS):
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
    if getattr(widget, "_hold_min_height", None) is not None:
        min_h = widget._hold_min_height  # kept until the animation ends (_set_height_for_switch)
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
    if height_anim_active(widget) and event.oldSize().width() == event.size().width():
        # The height following the cells (step_height_anim): the grid is already placed for
        # the final height (layout_height), so the cells keep their path; only the labels
        # are drawn again for the new size.
        try:
            widget._mode_transition_new_labels_pixmap = widget._render_labels_to_pixmap()
        except Exception:
            pass
        widget.update()
        return
    if getattr(widget, "_mode_transition_active", False):
        # A mode switch that changes the height (the all years view is taller than the
        # others) resizes the widget right as its animation starts: stopping it there made
        # that switch the only one without animation. The cells keep moving, towards their
        # place in the new size.
        try:
            _retarget_mode_transition(widget)
            widget._mode_transition_new_labels_pixmap = widget._render_labels_to_pixmap()
        except Exception:
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
    widget._legend_top_from = None  # the legend stays where it is

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
    keys = set(old_cells.keys()) | set(new_cells.keys())
    widget._mode_transition_cell_pairs = [(old_cells.get(k), new_cells.get(k)) for k in keys]
    widget._mode_transition_active = True
    widget._mode_transition_progress = 0.0
    if chart_animations_allowed(widget, max_visible_charts=USER_ACTION_MAX_CHARTS):
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
    widget._legend_top_from = None

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
    keys = set(old_cells.keys()) | set(new_cells.keys())
    widget._mode_transition_cell_pairs = [(old_cells.get(k), new_cells.get(k)) for k in keys]
    widget._mode_transition_active = True
    widget._mode_transition_progress = 0.0
    if chart_animations_allowed(widget, max_visible_charts=USER_ACTION_MAX_CHARTS):
        widget._mode_transition_anim.start()
    else:
        widget._on_mode_transition_finished()
    widget.update()
