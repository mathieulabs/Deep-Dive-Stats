# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QWidget, QColor, QPropertyAnimation, QEasingCurve, pyqtProperty
from ....ui import day_end_with_rollover
from ...chart_utils import TooltipWindow, ChartAnimationMixin, is_night_mode
from ....animations.motion import animations_enabled
from .metrics import entry_counts
from .interaction import (
    change_event_impl,
    get_live_today_pending_impl,
    hide_event_impl,
    leave_event_impl,
    mouse_move_event_impl,
    mouse_press_event_impl,
    show_tooltip_for_date_impl,
)
from .settings import (
    resize_event_impl,
    set_color_levels_impl,
    set_empty_opacity_impl,
    set_empty_white_impl,
    set_end_date_impl,
    set_filled_opacity_impl,
    set_hide_labels_impl,
    set_show_legend_impl,
    set_intensity_curve_impl,
    set_monday_first_impl,
    set_invert_intensity_impl,
    set_metric_impl,
    set_multi_hue_intensity_impl,
    set_rounding_impl,
    set_scale_impl,
    set_show_future_impl,
    set_tinted_future_impl,
    set_vibrance_impl,
    set_view_mode_impl,
    shift_continuous_impl,
    update_data_impl,
)
from .colors import (
    brush_for_color_impl,
    build_current_cell_visuals_impl,
    future_level_index_impl,
    is_empty_cell_color_impl,
    lerp_color_impl,
    refresh_data_colors_impl,
    resolve_cell_color_impl,
    update_empty_color_impl,
    update_levels_impl,
    visual_delta_ratio_impl,
)
from .layout_ops import (
    _CONT_BOX_COLS,
    compute_grid_info_impl,
    continuous_hit_test_impl,
    get_continuous_layout_impl,
    get_continuous_months_impl,
    get_grid_geometry_impl,
    get_max_counts_impl,
    has_height_for_width_impl,
    height_for_width_impl,
    minimum_size_hint_impl,
    size_hint_impl,
)
from .render_ops import (
    paint_event_impl,
    render_labels_to_pixmap_impl,
    render_scaffold_to_pixmap_impl,
    render_to_pixmap_impl,
)
from .transitions import (
    begin_navigation_transition_impl,
    clear_data_transition_state_impl,
    clear_mode_transition_state_impl,
    clear_nav_transition_state_impl,
    draw_nav_transition_frame_impl,
    finalize_navigation_transition_impl,
    interpolate_data_map_impl,
    on_data_transition_finished_impl,
    on_mode_transition_finished_impl,
    on_nav_transition_finished_impl,
)

class HeatmapWidget(ChartAnimationMixin, QWidget):

    def __init__(self, data, parent=None, color_scheme="#3b82f6", end_date=None, empty_opacity=None, empty_white=False, filled_opacity=None, hide_labels=False, scale=1.0, tinted_future=False, rounding=20, intensity_curve=100, monday_first=False, show_future=True, color_levels=15, grid_mode=True, vibrance=100, view_mode="year", multi_hue_intensity=False):
        super().__init__(parent)
        self.data = data if isinstance(data, dict) else dict(data)
        self.base_color = QColor(color_scheme)
        self.end_date = end_date if end_date else day_end_with_rollover()
        self.grid_mode = grid_mode
        self.vibrance = vibrance
        self.rounding = rounding
        self.intensity_curve = intensity_curve

        self.view_mode = view_mode  # "year", "365", or "continuous"
        self.cont_month_offset = 0  # months shifted from today in continuous mode
        self.empty_white = empty_white
        self.scale = scale
        self.hide_labels = hide_labels
        self.show_legend = False
        self.hidden_legend_steps = frozenset()
        self._legend_hits = []
        self._legend_from = None
        self._legend_t = 1.0
        self.tinted_future = tinted_future
        self.monday_first = monday_first
        self.show_future = show_future
        self.color_levels = max(2, color_levels)
        self.multi_hue_intensity = bool(multi_hue_intensity)
        self.metric = "reviews"
        self.invert_intensity = False

        initial_h = self.heightForWidth(450)
        self.setMinimumHeight(40 if self.grid_mode else initial_h)
        self.setMinimumWidth(150)
        self.setMouseTracking(True)
        self.hover_pos = None
        self.day_clicked = None
        self.tooltip_window = TooltipWindow(self)

        is_dark = is_night_mode(self)
        if empty_opacity is None:
            self.current_opacity_pct = 25 if is_dark else 20
        else:
            self.current_opacity_pct = empty_opacity

        if filled_opacity is None:
            self.filled_opacity_pct = 100
        else:
            self.filled_opacity_pct = filled_opacity

        self._update_levels()

        self._grid_cache = None
        self._pixmap_cache = None
        self._labels_pixmap_cache = None
        self._labels_pixmap_cache_key = None
        self._scaffold_pixmap_cache = None
        self._scaffold_pixmap_cache_key = None
        self._color_brush_cache = {}
        self._cont_layout_cache = None
        self._data_transition_active = False
        self._transition_old_data = {}
        self._transition_new_data = {}
        self._transition_old_cells = {}
        self._transition_new_cells = {}
        self._transition_cell_pairs = []
        self._transition_progress = 1.0
        self._suppress_next_transition = False
        self._transition_new_pixmap = None
        self._data_transition_anim = QPropertyAnimation(self, b"transition_progress")
        self._data_transition_anim.setDuration(320 if animations_enabled(self._animation_scope()) else 1)
        self._data_transition_anim.setStartValue(0.0)
        self._data_transition_anim.setEndValue(1.0)
        self._data_transition_anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._data_transition_anim.finished.connect(self._on_data_transition_finished)
        self._mode_transition_active = False
        self._mode_transition_old_cells = {}
        self._mode_transition_new_cells = {}
        self._mode_transition_cell_pairs = []
        self._mode_transition_progress = 1.0
        self._mode_transition_anim = QPropertyAnimation(self, b"mode_transition_progress")
        self._mode_transition_anim.setDuration(320 if animations_enabled(self._animation_scope()) else 1)
        self._mode_transition_anim.setStartValue(0.0)
        self._mode_transition_anim.setEndValue(1.0)
        self._mode_transition_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._mode_transition_anim.finished.connect(self._on_mode_transition_finished)
        self._mode_transition_old_labels_pixmap = None
        self._mode_transition_new_labels_pixmap = None
        self._nav_transition_active = False
        self._nav_transition_progress = 1.0
        self._nav_transition_direction = 1
        self._nav_transition_old_pixmap = None
        self._nav_transition_new_pixmap = None
        self._nav_transition_anim = QPropertyAnimation(self, b"nav_transition_progress")
        self._nav_transition_anim.setDuration(220 if animations_enabled(self._animation_scope()) else 1)
        self._nav_transition_anim.setStartValue(0.0)
        self._nav_transition_anim.setEndValue(1.0)
        self._nav_transition_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._nav_transition_anim.finished.connect(self._on_nav_transition_finished)

        self._update_empty_color()
        self.init_animation(duration=420, easing=QEasingCurve.Type.OutCubic)

    @pyqtProperty(float)
    def transition_progress(self):
        return self._transition_progress

    @transition_progress.setter
    def transition_progress(self, val):
        self._transition_progress = float(val)
        self.update()

    @pyqtProperty(float)
    def mode_transition_progress(self):
        return self._mode_transition_progress

    @mode_transition_progress.setter
    def mode_transition_progress(self, val):
        self._mode_transition_progress = float(val)
        self.update()

    @pyqtProperty(float)
    def nav_transition_progress(self):
        return self._nav_transition_progress

    @nav_transition_progress.setter
    def nav_transition_progress(self, val):
        self._nav_transition_progress = float(val)
        self.update()

    def _entry_counts(self, data_map, key):
        return entry_counts(self, data_map.get(key, 0))

    def _clear_data_transition_state(self):
        return clear_data_transition_state_impl(self)

    def _clear_nav_transition_state(self):
        return clear_nav_transition_state_impl(self)

    def _clear_mode_transition_state(self):
        return clear_mode_transition_state_impl(self)

    def _interpolate_data_map(self, t):
        return interpolate_data_map_impl(self, t)

    def _on_data_transition_finished(self):
        return on_data_transition_finished_impl(self)

    def _on_mode_transition_finished(self):
        return on_mode_transition_finished_impl(self)

    def _on_nav_transition_finished(self):
        return on_nav_transition_finished_impl(self)

    def begin_navigation_transition(self, delta):
        return begin_navigation_transition_impl(self, delta)

    def finalize_navigation_transition(self):
        return finalize_navigation_transition_impl(self)

    def _draw_nav_transition_frame(self, painter, old_x, new_x, fade_px=14):
        return draw_nav_transition_frame_impl(self, painter, old_x, new_x, fade_px=fade_px)

    @staticmethod
    def _lerp(a, b, t):
        return a + ((b - a) * t)

    def _lerp_color(self, c1, c2, t):
        return lerp_color_impl(self, c1, c2, t)

    def _brush_for_color(self, color):
        return brush_for_color_impl(self, color)

    def _is_empty_cell_color(self, color):
        return is_empty_cell_color_impl(self, color)

    def _resolve_cell_color(self, count, future, curr_date_val, logical_today, max_past_count, max_future_count):
        return resolve_cell_color_impl(self, count, future, curr_date_val, logical_today, max_past_count, max_future_count)

    def _future_level_index(self, future, max_future_count):
        return future_level_index_impl(self, future, max_future_count)

    def _build_current_cell_visuals(self, data_source=None):
        return build_current_cell_visuals_impl(self, data_source)

    def _visual_delta_ratio(self, old_data, new_data):
        return visual_delta_ratio_impl(self, old_data, new_data)

    def refresh_data_colors(self):
        return refresh_data_colors_impl(self)

    def _update_levels(self):
        return update_levels_impl(self)

    def _update_empty_color(self):
        return update_empty_color_impl(self)

    def resizeEvent(self, event):
        return resize_event_impl(self, event)

    def set_end_date(self, date):
        return set_end_date_impl(self, date)

    def update_data(self, new_data):
        return update_data_impl(self, new_data)

    def toggle_legend_step(self, step):
        from .settings import toggle_legend_step_impl

        return toggle_legend_step_impl(self, step)

    def transition_to(self, new_data, end_date):
        from .settings import transition_to_impl

        return transition_to_impl(self, new_data, end_date)

    def set_empty_opacity(self, opacity_pct):
        return set_empty_opacity_impl(self, opacity_pct)

    def set_empty_white(self, white: bool):
        return set_empty_white_impl(self, white)

    def set_filled_opacity(self, opacity_pct):
        return set_filled_opacity_impl(self, opacity_pct)

    def set_scale(self, scale_pct):
        return set_scale_impl(self, scale_pct)

    def set_hide_labels(self, hide: bool):
        return set_hide_labels_impl(self, hide)

    def set_show_legend(self, show: bool):
        return set_show_legend_impl(self, show)

    def set_monday_first(self, monday_first: bool):
        return set_monday_first_impl(self, monday_first)

    def set_tinted_future(self, tinted: bool):
        return set_tinted_future_impl(self, tinted)

    def set_show_future(self, show: bool):
        return set_show_future_impl(self, show)

    def set_color_levels(self, levels):
        return set_color_levels_impl(self, levels)

    def set_vibrance(self, vibrance_pct):
        return set_vibrance_impl(self, vibrance_pct)

    def set_rounding(self, rounding_pct):
        return set_rounding_impl(self, rounding_pct)

    def set_intensity_curve(self, intensity_pct):
        return set_intensity_curve_impl(self, intensity_pct)

    def set_metric(self, metric):
        return set_metric_impl(self, metric)

    def set_invert_intensity(self, invert: bool):
        return set_invert_intensity_impl(self, invert)

    def set_multi_hue_intensity(self, enabled: bool):
        return set_multi_hue_intensity_impl(self, enabled)

    def set_view_mode(self, mode):
        return set_view_mode_impl(self, mode)

    def shift_continuous(self, delta):
        return shift_continuous_impl(self, delta)

    @property
    def _effective_show_labels(self):
        return not self.hide_labels

    def _compute_grid_info(self):
        return compute_grid_info_impl(self)

    def _get_continuous_months(self):
        return get_continuous_months_impl(self)

    def _get_continuous_layout(self):
        return get_continuous_layout_impl(self)

    def _continuous_hit_test(self, mx, my):
        return continuous_hit_test_impl(self, mx, my)

    def _get_grid_geometry(self):
        return get_grid_geometry_impl(self)

    def _get_max_counts(self, data_source=None):
        return get_max_counts_impl(self, data_source)

    def _render_labels_to_pixmap(self):
        return render_labels_to_pixmap_impl(self)

    def _render_scaffold_to_pixmap(self):
        return render_scaffold_to_pixmap_impl(self)

    def _render_to_pixmap(self, data_source=None):
        return render_to_pixmap_impl(self, data_source)

    def paintEvent(self, event):
        result = paint_event_impl(self, event)
        self._notify_extent_listeners()
        return result

    def content_x_extent(self):
        """(left, right) of the drawn grid assembly in widget coordinates; the
        grid is centred in the widget, so this is narrower than the widget."""
        try:
            if self.view_mode == "continuous":
                (_cell, spacing, step, gap_width, label_space, _mt, start_x,
                 months) = self._get_continuous_layout()
                # The fixed box, not the grid inside it, so the controls don't move.
                cols = sum(m[3] for m in months)
                box_x = start_x - (_CONT_BOX_COLS - cols) * step / 2.0
                right = box_x + _CONT_BOX_COLS * step + max(0, len(months) - 1) * gap_width - spacing
                return (box_x - label_space, right)
            _cell, spacing, start_x, _sy, label_space = self._get_grid_geometry()
            step = _cell + spacing
            return (start_x - label_space, start_x + 53 * step - spacing)
        except Exception:
            return None

    def add_extent_listener(self, fn):
        if not hasattr(self, "_extent_listeners"):
            self._extent_listeners = []
        self._extent_listeners.append(fn)

    def _notify_extent_listeners(self):
        listeners = getattr(self, "_extent_listeners", None)
        if not listeners:
            return
        ext = self.content_x_extent()
        key = (None if ext is None else (round(ext[0]), round(ext[1])), self.width())
        if key == getattr(self, "_last_extent_key", None):
            return
        self._last_extent_key = key
        if ext is None:
            return
        from aqt.qt import QTimer

        w = self.width()
        for fn in list(listeners):
            QTimer.singleShot(0, lambda fn=fn, ext=ext, w=w: fn(ext, w))

    def hasHeightForWidth(self):
        return has_height_for_width_impl(self)

    def heightForWidth(self, width):
        return height_for_width_impl(self, width)

    def sizeHint(self):
        return size_hint_impl(self)

    def minimumSizeHint(self):
        return minimum_size_hint_impl(self)

    def _show_tooltip_for_date(self, target_date, mx, my):
        return show_tooltip_for_date_impl(self, target_date, mx, my)

    def _get_live_today_pending(self):
        return get_live_today_pending_impl(self)

    def mouseMoveEvent(self, event):
        return mouse_move_event_impl(self, event)

    def mousePressEvent(self, event):
        return mouse_press_event_impl(self, event)

    def leaveEvent(self, event):
        return leave_event_impl(self, event)

    def hideEvent(self, event):
        return hide_event_impl(self, event)

    def changeEvent(self, event):
        return change_event_impl(self, event)


