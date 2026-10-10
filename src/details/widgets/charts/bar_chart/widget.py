# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QColor, QWidget

from ....animations.chart_mixin import ChartAnimationMixin
from ..common import init_chart_widget_state
from .data_ops import normalized_values_impl, set_chart_opacity_impl, size_hint_impl
from .event_ops import mouse_double_click_event_impl
from .render_ops import paint_event_impl


class BarChartWidget(ChartAnimationMixin, QWidget):
    def __init__(self, data, parent=None, color="#8ab4f8"):
        super().__init__(parent)
        self.data = data
        self.color = QColor(color)
        self.chart_opacity_pct = 100
        self.setMinimumWidth(50)
        self.setMinimumHeight(30)
        self.doubleClicked = None
        init_chart_widget_state(
            self,
            translucent=True,
            animation_kwargs={"duration": 420},
        )

    def set_chart_opacity(self, pct):
        return set_chart_opacity_impl(self, pct)

    def sizeHint(self):
        return size_hint_impl(self)

    def normalized_values(self):
        return normalized_values_impl(self)

    def paintEvent(self, event):
        return paint_event_impl(self, event)

    def mouseDoubleClickEvent(self, event):
        return mouse_double_click_event_impl(self, event)
