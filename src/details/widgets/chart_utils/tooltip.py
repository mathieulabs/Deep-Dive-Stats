# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import (
    QWidget, Qt, QColor, QPainter, QRectF, QFontMetrics, QPen, QEvent, QApplication, QPoint
)
from .theme import get_theme_colors
from .tooltip_fields import filter_tooltip_lines
from ...logic.logger import log_swallowed


def _resolve_tooltip_colors(widget):
    """Resolve tooltip colors from the current chart/theme context."""
    try:
        t = get_theme_colors(widget)
    except Exception:
        t = {}
    is_dark = bool(t.get("is_dark", False))
    text_primary = QColor(t.get("text_primary", "#f4f4f5" if is_dark else "#18181b"))
    text_secondary = QColor(t.get("text_secondary", "#d4d4d8" if is_dark else "#3f3f46"))
    border = QColor(t.get("border", "#3f3f46" if is_dark else "#d4d4d8"))
    bg = QColor(t.get("bg", "#18181b" if is_dark else "#ffffff"))
    bg.setAlpha(232 if is_dark else 245)
    return {"bg": bg, "border": border, "text_primary": text_primary, "text_secondary": text_secondary}


def place_tooltip_near(widget, tooltip, local_pos, x_offset=15, y_offset=15, edge_padding=10):
    """Place a tooltip window near a local widget position while clamping to screen bounds."""
    if widget is None or tooltip is None:
        return
    try:
        local = local_pos if isinstance(local_pos, QPoint) else QPoint(int(local_pos.x()), int(local_pos.y()))
    except Exception:
        local = QPoint(0, 0)

    global_pos = widget.mapToGlobal(QPoint(int(local.x() + x_offset), int(local.y() + y_offset)))
    screen = widget.screen() if hasattr(widget, "screen") else None
    if screen is None:
        screen = QApplication.primaryScreen()
    if screen is None:
        tooltip.move(global_pos)
        return
    screen_rect = screen.availableGeometry()

    if global_pos.x() + tooltip.width() > screen_rect.right():
        fallback_x = widget.mapToGlobal(QPoint(int(local.x() - tooltip.width() - edge_padding), 0)).x()
        global_pos.setX(int(fallback_x))
    if global_pos.x() < screen_rect.left() + edge_padding:
        global_pos.setX(screen_rect.left() + edge_padding)

    if global_pos.y() + tooltip.height() > screen_rect.bottom():
        global_pos.setY(screen_rect.bottom() - tooltip.height() - edge_padding)
    if global_pos.y() < screen_rect.top() + edge_padding:
        global_pos.setY(screen_rect.top() + edge_padding)

    tooltip.move(global_pos)


def show_tooltip_near(
    widget,
    tooltip,
    local_pos,
    *,
    lines=None,
    x_offset=15,
    y_offset=15,
    edge_padding=10,
    show_only_if_hidden=True,
):
    """Update tooltip content, place it near cursor and show it."""
    if widget is None or tooltip is None:
        return
    if lines is not None:
        tooltip.update_content(filter_tooltip_lines(widget, lines))
    place_tooltip_near(
        widget,
        tooltip,
        local_pos,
        x_offset=x_offset,
        y_offset=y_offset,
        edge_padding=edge_padding,
    )
    if show_only_if_hidden:
        if not tooltip.isVisible():
            tooltip.show()
    else:
        tooltip.show()


def show_tooltip_text_near(
    widget,
    tooltip,
    local_pos,
    text,
    *,
    x_offset=15,
    y_offset=15,
    edge_padding=10,
    show_only_if_hidden=True,
):
    """Build simple text lines then show tooltip near a local position."""
    lines = [{"text": line_text} for line_text in str(text or "").split("\n")]
    show_tooltip_near(
        widget,
        tooltip,
        local_pos,
        lines=lines,
        x_offset=x_offset,
        y_offset=y_offset,
        edge_padding=edge_padding,
        show_only_if_hidden=show_only_if_hidden,
    )


def show_floating_label_at_y(
    widget,
    label,
    *,
    text,
    y_local,
    anchor_x_local,
    theme_colors,
    text_color=None,
    show_only_if_hidden=True,
):
    """Update/style/place a FloatingAvgLabel near a local Y coordinate."""
    if widget is None or label is None:
        return
    label.update_style(text, theme_colors, text_color=text_color)
    global_pos = widget.mapToGlobal(QPoint(int(anchor_x_local), int(y_local)))
    box_w = label.width()
    target_tx = global_pos.x() - box_w - 5
    label.move(int(target_tx), int(global_pos.y() - label.height() / 2))
    if show_only_if_hidden:
        if not label.isVisible():
            label.show()
    else:
        label.show()


def _hide_tooltip_target(target):
    """Hide one tooltip target or a collection of tooltip targets."""
    if target is None:
        return
    if isinstance(target, dict):
        for value in target.values():
            _hide_tooltip_target(value)
        return
    if isinstance(target, (list, tuple, set)):
        for value in target:
            _hide_tooltip_target(value)
        return
    if hasattr(target, "hide"):
        try:
            target.hide()
        except Exception:
            log_swallowed()


def hide_tooltip_targets(widget, *attr_names):
    """Hide tooltip-like attributes on a chart widget."""
    if widget is None:
        return
    for name in attr_names:
        _hide_tooltip_target(getattr(widget, name, None))


def hide_tooltips_on_window_deactivate(widget, event, *attr_names):
    """Hide tooltip-like attributes when the host window deactivates."""
    if event is None or widget is None:
        return
    if event.type() == QEvent.Type.ActivationChange and not widget.isActiveWindow():
        hide_tooltip_targets(widget, *attr_names)

class _ShowOnlyWhenActiveMixin:
    """Popup windows only show while their parent is visible and the host window is active."""

    def show(self):
        if QApplication.mouseButtons() & Qt.MouseButton.RightButton:
            return
        p = self.parentWidget()
        if p and not p.isVisible():
            return
        aw = QApplication.activeWindow()
        if p and p.window() is not None and aw is not None and aw != p.window():
            return
        if aw is None:
            return
        super().show()


class TooltipWindow(_ShowOnlyWhenActiveMixin, QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        # Prevent focus-stealing / flicker when host window is not active.
        try:
            self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        except Exception:
            log_swallowed()
        self.lines = []
        if parent:
            parent.installEventFilter(self)

    def eventFilter(self, obj, event):
        if obj == self.parent():
            if event.type() in [QEvent.Type.Hide, QEvent.Type.Leave, QEvent.Type.WindowDeactivate, QEvent.Type.Close]:
                self.hide()
            elif event.type() == QEvent.Type.MouseButtonPress:
                try:
                    if event.button() == Qt.MouseButton.RightButton:
                        self.hide()
                except Exception:
                    log_swallowed()
            elif event.type() == QEvent.Type.MouseButtonRelease:
                try:
                    if event.button() == Qt.MouseButton.RightButton:
                        self.hide()
                except Exception:
                    log_swallowed()
            elif event.type() == QEvent.Type.MouseMove:
                # If right-click is being held and cursor leaves the parent graph,
                # force-hide tooltip (leaveEvent may not fire while dragging/holding button).
                try:
                    if QApplication.mouseButtons() & Qt.MouseButton.RightButton:
                        p = self.parentWidget()
                        if p:
                            pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
                            if not p.rect().contains(pos):
                                self.hide()
                except Exception:
                    log_swallowed()
        return super().eventFilter(obj, event)

    def update_content(self, lines):
        self.lines = lines
        self.adjustSize()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        cols = _resolve_tooltip_colors(self.parentWidget() or self)
        
        fm_normal = painter.fontMetrics()
        font_bold = painter.font()
        font_bold.setBold(True)
        fm_bold = QFontMetrics(font_bold)
        
        max_w = 0
        box_h = 10
        
        for line in self.lines:
            use_fm = fm_bold if (line.get("header") or line.get("bold")) else fm_normal
            
            tw_left = use_fm.horizontalAdvance(line["text"])
            if line.get("color"): tw_left += 15
            tw_right = use_fm.horizontalAdvance(line.get("value", ""))
            
            gap = 40
            total_w = tw_left + (gap if line.get("value") else 0) + tw_right
            if total_w > max_w: max_w = total_w
            box_h += use_fm.height() + 4
        
        tw = max_w + 30
        th = box_h
        
        self.resize(tw, th)
        
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setBrush(cols["bg"])
        pen = QPen(cols["border"], 0.8)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.drawRoundedRect(rect, 10, 10)
        
        y_text = 5
        
        for line in self.lines:
            if line.get("header"):
                font = painter.font()
                font.setBold(True)
                painter.setFont(font)
                painter.setPen(cols["text_primary"])
                painter.drawText(QRectF(10, y_text, tw - 20, fm_normal.height()), Qt.AlignmentFlag.AlignLeft, line["text"])
                if line.get("value"):
                    painter.drawText(QRectF(10, y_text, tw - 20, fm_normal.height()), Qt.AlignmentFlag.AlignRight, line["value"])
                font.setBold(False)
                painter.setFont(font)
            elif line.get("bold"):
                painter.setPen(cols["text_primary"])
                font = painter.font()
                font.setBold(True)
                painter.setFont(font)
                painter.drawText(QRectF(10, y_text, tw - 20, fm_normal.height()), Qt.AlignmentFlag.AlignCenter, line["text"])
                font.setBold(False)
                painter.setFont(font)
            else:
                painter.setPen(cols["text_secondary"])
                x_text = 10
                if line.get("color"):
                    painter.setBrush(QColor(line["color"]))
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.drawRoundedRect(QRectF(x_text, y_text + 4, 8, 8), 4, 4)
                    x_text += 15
                
                painter.setPen(cols["text_secondary"])
                text_rect = QRectF(x_text, y_text, tw - 20 - (x_text - 10), fm_normal.height())
                painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, line["text"])
                
                if line.get("value"):
                    painter.drawText(QRectF(10, y_text, tw - 20, fm_normal.height()), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, line["value"])

            y_text += fm_normal.height() + 4

class FloatingAvgLabel(_ShowOnlyWhenActiveMixin, QWidget):
    """
    A small floating window for the 'Average' label.
    Allows overflowing the chart widget boundaries.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        # Prevent focus-stealing / flicker when host window is not active.
        try:
            self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        except Exception:
            log_swallowed()
        self.text = ""
        self.text_color = QColor("white")
        self.bg_color = QColor(0, 0, 0)
        self.border_color = QColor(255, 255, 255, 50)
        if parent:
            parent.installEventFilter(self)

    def eventFilter(self, obj, event):
        if obj == self.parent():
            if event.type() in [QEvent.Type.Hide, QEvent.Type.Leave, QEvent.Type.WindowDeactivate, QEvent.Type.Close]:
                self.hide()
            elif event.type() == QEvent.Type.MouseButtonPress:
                try:
                    if event.button() == Qt.MouseButton.RightButton:
                        self.hide()
                except Exception:
                    log_swallowed()
            elif event.type() == QEvent.Type.MouseMove:
                try:
                    if QApplication.mouseButtons() & Qt.MouseButton.RightButton:
                        p = self.parentWidget()
                        if p:
                            pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
                            if not p.rect().contains(pos):
                                self.hide()
                except Exception:
                    log_swallowed()
        return super().eventFilter(obj, event)

    def update_style(self, text, t_colors, text_color=None):
        self.text = text
        cols = _resolve_tooltip_colors(self.parentWidget() or self)
        self.bg_color = cols["bg"]
        self.border_color = cols["border"]
        self.text_color = QColor(text_color) if text_color else cols["text_primary"]
        
        fm = QFontMetrics(self.font())
        tw = fm.horizontalAdvance(self.text)
        self.resize(tw + 8, 20)
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self.bg_color)
        painter.drawRoundedRect(rect, 6, 6)
        
        pen = QPen(self.border_color, 0.8)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect, 6, 6)
        
        painter.setPen(self.text_color)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter, self.text)
