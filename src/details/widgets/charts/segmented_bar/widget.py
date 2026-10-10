# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import Qt, QWidget

from ...chart_utils import ChartAnimationMixin
from ..common import get_review_button_colors, init_chart_widget_state
from .data_ops import refresh_data_colors_impl, tooltip_text_impl
from .event_ops import enter_event_impl, mouse_double_click_event_impl, show_event_impl
from .render_ops import paint_event_impl


class SegmentedBarWidget(ChartAnimationMixin, QWidget):
    def __init__(self, counts, parent=None, animate=True, labels=None, color_slots=None, center_text=None):
        super().__init__(parent)
        self.counts = counts
        # color_slots picks colors from the review button colors (again, hard, good, easy).
        self.color_slots = tuple(color_slots) if color_slots is not None else None
        self.center_text = center_text
        self._animate_on_show = bool(animate)
        self.colors = self._pick_colors(get_review_button_colors(self, as_qcolor=True))
        self.labels = list(labels) if labels else ["Again", "Hard", "Good", "Easy"]
        self.setMinimumWidth(50)
        self.setMinimumHeight(16)
        self.doubleClicked = None
        if self._animate_on_show:
            init_chart_widget_state(
                self,
                translucent=True,
                animation_kwargs={"duration": 1000},
            )
        else:
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            self._progress = 1.0
            self._initial_animation_done = True
            self.animation = None

    def _pick_colors(self, colors):
        if self.color_slots is None:
            return colors
        return [colors[i] for i in self.color_slots]

    def refresh_data_colors(self):
        return refresh_data_colors_impl(self)

    def tooltip_text(self):
        return tooltip_text_impl(self)

    def showEvent(self, event):
        return show_event_impl(self, event)

    def paintEvent(self, event):
        return paint_event_impl(self, event)

    def enterEvent(self, event):
        return enter_event_impl(self, event)

    def mouseDoubleClickEvent(self, event):
        return mouse_double_click_event_impl(self, event)
