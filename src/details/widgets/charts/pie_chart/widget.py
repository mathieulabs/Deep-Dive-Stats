# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QEasingCurve, QWidget, pyqtSignal

from ...chart_utils import ChartAnimationMixin
from ..common import init_chart_widget_state
from .constants import PIE_CHART_LABELS, PIE_CHART_ORDER
from .data_ops import (
    active_keys_impl,
    get_pie_chart_colors,
    refresh_data_colors_impl,
    set_chart_opacity_impl,
    update_counts_impl,
)
from .layout_ops import (
    get_needed_vertical_height_impl,
    legend_inline_impl,
    set_legend_mode_impl,
    get_scale_impl,
    get_vertical_scale_impl,
    resize_event_impl,
    set_separate_suspended_impl,
    show_event_impl,
    size_hint_impl,
    update_geom_impl,
)
from .hover_ops import leave_impl, mouse_move_impl
from .render_ops import paint_event_impl


class PieChartWidget(ChartAnimationMixin, QWidget):
    optimalHeightChanged = pyqtSignal(int)

    def __init__(self, counts, parent=None, grid_mode=True):
        super().__init__(parent)
        self.counts = counts
        self._prev_counts = dict(counts or {})
        self._next_counts = dict(counts or {})
        self._is_data_morph = False
        self._global_transition_mode = None
        self._morph_duration_ms = 270
        self._empty_graph_morph_duration_ms = 280
        self.grid_mode = grid_mode
        self.separate_suspended = True
        self.setMinimumHeight(150)
        self.setMouseTracking(True)
        self.show_legend = True
        # "auto": legend next to the donut when it can be read, else a list shown on hover.
        self.legend_mode = "auto"
        self._legend_compact = False
        self._legend_hot = False
        self._legend_icon_rect = None
        self._legend_panel_rect = None
        self._hover_key = None
        self._hover_amt = {}
        init_chart_widget_state(
            self,
            translucent=True,
            animation_kwargs={"duration": 800, "easing": QEasingCurve.Type.OutCubic},
        )

        self.colors = get_pie_chart_colors(self)
        self.labels = dict(PIE_CHART_LABELS)
        self.order = list(PIE_CHART_ORDER)
        self.chart_opacity_pct = 100
        self._slice_base_color_cache_key = None
        self._slice_base_color_cache = None
        self._layout_updates_suspended = True
        self.update_geom()
        self._layout_updates_suspended = False

    def set_show_legend(self, show):
        show = bool(show)
        if show == self.show_legend:
            return
        self.show_legend = show
        self.update_geom()
        self.updateGeometry()
        self.update()

    def set_legend_mode(self, mode):
        return set_legend_mode_impl(self, mode)

    def legend_inline(self):
        return legend_inline_impl(self)

    def refresh_data_colors(self):
        return refresh_data_colors_impl(self)

    def set_chart_opacity(self, pct):
        return set_chart_opacity_impl(self, pct)

    def _get_scale(self):
        return get_scale_impl(self)

    def _get_vertical_scale(self, logical_w=210.0):
        return get_vertical_scale_impl(self, logical_w=logical_w)

    def set_separate_suspended(self, separate):
        return set_separate_suspended_impl(self, separate)

    def _active_keys(self):
        return active_keys_impl(self)

    def update_counts(self, counts):
        return update_counts_impl(self, counts)

    def update_data(self, new_counts):
        return self.update_counts(new_counts)

    def resizeEvent(self, event):
        return resize_event_impl(self, event)

    def showEvent(self, event):
        return show_event_impl(self, event)

    def get_needed_vertical_height(self, with_legend=None):
        return get_needed_vertical_height_impl(self, with_legend=with_legend)

    def update_geom(self):
        return update_geom_impl(self)

    def sizeHint(self):
        return size_hint_impl(self)

    def mouseMoveEvent(self, event):
        mouse_move_impl(self, event)
        QWidget.mouseMoveEvent(self, event)

    def leaveEvent(self, event):
        leave_impl(self)
        QWidget.leaveEvent(self, event)

    def paintEvent(self, event):
        return paint_event_impl(self, event)
