# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import (
    QHBoxLayout, Qt, QLabel, QPushButton, QWidget, QSizePolicy, QSize, QEvent
)
from ...ui.theme.icons import get_svg_icon
from ..chart_utils.tooltip import TooltipWindow
from ..chart_utils.theme import get_theme_colors, subscribe_theme_changed, unsubscribe_theme_changed
from ....qss import set_qss

class AdaptiveStatsWidget(QWidget):
    """A widget that shows stats as text, or an icon with a tooltip if space is limited."""
    def __init__(self, stats_text_list, parent=None):
        super().__init__(parent)
        self.stats_text = "  ·  ".join(stats_text_list)
        self.stats_text_list = stats_text_list
        self.parent_header = parent
        
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        
        self.label = QLabel(self.stats_text, self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.layout.addWidget(self.label)
        
        self.icon_btn = QPushButton(self)
        self.icon_btn.setFixedSize(20, 20)
        self.icon_btn.hide()
        self.layout.addWidget(self.icon_btn)
        
        self.layout.addStretch()
        
        self.tooltip = TooltipWindow(self)
        self.icon_btn.enterEvent = self._on_enter
        self.icon_btn.leaveEvent = self._on_leave
        self._theme_subscription = subscribe_theme_changed(self._on_theme_changed)
        self._apply_theme()
        
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(20)

    def sizeHint(self):
        fm = self.label.fontMetrics()
        text_w = fm.horizontalAdvance(self.stats_text) + 20
        return QSize(text_w, 20)

    def minimumSizeHint(self):
        return QSize(20, 20)

    def update_text(self, stats_text_list):
        self.stats_text = "  ·  ".join(stats_text_list)
        self.stats_text_list = stats_text_list
        self.label.setText(self.stats_text)
        self.updateGeometry()

    def _on_enter(self, event):
        lines = []
        for line in self.stats_text_list:
            lines.append({"text": line})
        self.tooltip.update_content(lines)
        
        pos = self.icon_btn.mapToGlobal(self.icon_btn.rect().bottomRight())
        self.tooltip.move(pos.x() - self.tooltip.width(), pos.y() + 5)
        self.tooltip.show()

    def _on_leave(self, event):
        self.tooltip.hide()

    def _on_theme_changed(self, *_args, **_kwargs):
        self._apply_theme()

    def _apply_theme(self):
        t_colors = get_theme_colors(self)
        text_col = t_colors.get("text_secondary", t_colors.get("text"))
        is_dark = bool(t_colors.get("is_dark"))
        if hasattr(text_col, "name"):
            text_hex = text_col.name()
        else:
            text_hex = "#888888"
        hover_bg = "rgba(255,255,255,0.1)" if is_dark else "rgba(0,0,0,0.06)"
        set_qss(self.label, 
            f"color: {text_hex}; font-size: 11px; background: transparent; border: none;"
        )
        self.icon_btn.setIcon(get_svg_icon("bar-chart-2", size=14, color=text_hex))
        set_qss(self.icon_btn, 
            "QPushButton { background: transparent; border: none; } "
            f"QPushButton:hover {{ background: {hover_bg}; border-radius: 4px; }}"
        )

    def hideEvent(self, event):
        """Make sure tooltips are hidden when the widget is hidden."""
        if hasattr(self, "tooltip"):
            self.tooltip.hide()
        super().hideEvent(event)

    def showEvent(self, event):
        # Re-resolve colors after final parenting/context is established
        # (important for pinned widgets initialized before full attach).
        self._apply_theme()
        super().showEvent(event)

    def closeEvent(self, event):
        if getattr(self, "_theme_subscription", None):
            unsubscribe_theme_changed(self._theme_subscription)
            self._theme_subscription = None
        super().closeEvent(event)

    def changeEvent(self, event):
        """Hide tooltips if window becomes inactive."""
        if event.type() in (QEvent.Type.ParentChange, QEvent.Type.Polish):
            self._apply_theme()
        if event.type() == QEvent.Type.ActivationChange:
            if not self.isActiveWindow():
                if hasattr(self, "tooltip"):
                    self.tooltip.hide()
        super().changeEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        full_w = self.sizeHint().width()
        
        if self.width() < full_w:
            self.label.hide()
            self.icon_btn.show()
        else:
            self.label.show()
            self.icon_btn.hide()

