# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import (
    QEvent,
    QHBoxLayout,
    QObject,
    QPushButton,
    QWidget,
    QVBoxLayout,
    QFrame,
    QSizePolicy,
    QLabel,
    Qt,
    QCursor,
    QSize,
    QGraphicsOpacityEffect,
    QTimer,
    pyqtSignal,
)
from ..drag_drop.constants import MIME_CHART_ID
from ..drag_drop.initiator import DragInitiator

from .styler import apply_style
from .. import WidgetRegistry
from ....ui import Config
from ...chart_utils.theme import ThemeContext, apply_theme_context, resolve_widget_theme_context
from .....qss import set_qss
from ....logic.logger import log_swallowed

# Pinned charts collapsed by the user (session only, like the Deep Dive cards).
_COLLAPSED_PINNED = set()


def pinned_charts_collapsible():
    try:
        from .utils import _addon_config

        return bool(_addon_config().config.get(Config.PINNED_CHARTS_COLLAPSIBLE, False))
    except Exception:
        return False


def refresh_pinned_collapsible():
    """Re-apply the "Collapsible Charts" setting to every pinned card on screen."""
    try:
        from ..main_menu.manager import MainMenuWidgetManager

        if not MainMenuWidgetManager.instance_exists():
            return
        mgr = MainMenuWidgetManager.instance()
        overlay = getattr(mgr, "_overlay", None)
        if overlay is None:
            return
        for card in overlay.findChildren(ResizableWrapper):
            card.refresh_collapsible()
        mgr.sync_overlay()
    except Exception:
        log_swallowed()


def _refresh_pinned_overlay():
    try:
        from ..main_menu.manager import MainMenuWidgetManager

        if MainMenuWidgetManager.instance_exists():
            MainMenuWidgetManager.instance().sync_overlay()
    except Exception:
        log_swallowed()


class _HeaderClickFilter(QObject):
    """Lets a click on the title toggle the card, like in the Deep Dive."""

    def __init__(self, callback, parent=None):
        super().__init__(parent)
        self._callback = callback

    def eventFilter(self, obj, event):
        if (
            event.type() == QEvent.Type.MouseButtonRelease
            and event.button() == Qt.MouseButton.LeftButton
            and pinned_charts_collapsible()
        ):
            self._callback()
            return True
        return super().eventFilter(obj, event)


class _EdgeCursorSync(QObject):
    """Keeps the resize cursor in step with the mouse while it is over a child widget.

    The wrapper only sees mouse moves that no child takes, so a resize cursor set on
    the border would stay once the mouse went on into the chart."""

    def __init__(self, card):
        super().__init__(card)
        self._card = card

    def eventFilter(self, obj, event):
        if event.type() in (QEvent.Type.MouseMove, QEvent.Type.Enter):
            try:
                self._card._sync_edge_cursor(self._card.mapFromGlobal(QCursor.pos()))
            except Exception:
                log_swallowed()
        return False


class ResizableWrapper(QFrame):
    height_changed = pyqtSignal(int)
    col_span_changed = pyqtSignal(int)

    def __init__(self, widget_id, saved_w=None, saved_h=None, resizable=True, resize_directions=None, save_callback=None, parent=None, col_span=1):
        super().__init__(parent)
        self.widget_id = widget_id
        self.resizable = resizable
        self.resize_directions = resize_directions
        self.save_callback = save_callback
        self.setObjectName("pinned_widget_card")
        # Theme: pinned widgets always use native Anki mode, Deep Dive grid widgets
        # follow the details context (which can force a dark preset).
        force_details = (
            resolve_widget_theme_context(parent, default=ThemeContext.PINNED)
            == ThemeContext.DETAILS
        )
        apply_theme_context(self, ThemeContext.DETAILS if force_details else ThemeContext.PINNED)
        self.setMouseTracking(self.resizable)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        
        self._resize_mode = None  # "r", "b", "rb" or None
        self._drag_start_pos = None
        self._drag_start_pos_local = None
        self._start_geom = None
        
        self.border_sensitivity = 8
        self.col_span = col_span
        
        self.inner_widget = None
        
        self.apply_size(saved_w, saved_h)

    def _layout_outer_metrics(self):
        layout = self.layout()
        if not layout:
            return 12, 12, 0

        margins = layout.contentsMargins()
        extra_w = margins.left() + margins.right()
        extra_h = margins.top() + margins.bottom()
        max_header_w = 0

        visible_items = []
        for idx in range(layout.count()):
            item = layout.itemAt(idx)
            widget = item.widget() if item else None
            if not widget or not widget.isVisible():
                continue
            visible_items.append(widget)
            if widget is self.inner_widget:
                continue
            hint = widget.sizeHint()
            max_header_w = max(max_header_w, hint.width())
            extra_h += hint.height()

        if len(visible_items) > 1:
            extra_h += layout.spacing() * (len(visible_items) - 1)

        return extra_w, extra_h, max_header_w

    def _text_label_target_size(self, outer_width=None):
        inner = getattr(self, "inner_widget", None)
        if inner is None:
            return QSize(260, 72)

        extra_w, extra_h, header_w = self._layout_outer_metrics()
        preferred_content_w = 260
        if hasattr(inner, "preferredTextWidth"):
            try:
                preferred_content_w = max(120, int(inner.preferredTextWidth()))
            except Exception:
                preferred_content_w = 260
        else:
            try:
                preferred_content_w = max(120, int(inner.sizeHint().width()))
            except Exception:
                preferred_content_w = 260

        max_outer_w = 0
        try:
            parent = self.parentWidget()
            if parent is not None:
                max_outer_w = max(0, int(parent.width()))
                layout = parent.layout()
                if layout is not None:
                    margins = layout.contentsMargins()
                    max_outer_w -= int(margins.left() + margins.right())
        except Exception:
            max_outer_w = 0

        if outer_width is None:
            target_outer_w = max(preferred_content_w, header_w) + extra_w
        else:
            target_outer_w = max(120, int(outer_width))
        if 0 < max_outer_w < 200:
            max_outer_w = 0  # the row is not laid out yet: a tiny width is not a real limit
        if max_outer_w > 0:
            target_outer_w = min(target_outer_w, max_outer_w)

        content_w = max(80, target_outer_w - extra_w)
        if hasattr(inner, "heightForWidth"):
            try:
                content_h = max(20, int(inner.heightForWidth(content_w)))
            except Exception:
                content_h = max(20, int(inner.sizeHint().height()))
        else:
            content_h = max(20, int(inner.sizeHint().height()))

        target_outer_h = content_h + extra_h
        return QSize(max(160, target_outer_w), max(44, target_outer_h))

    def _text_label_actual_target_size(self, saved_w=None, saved_h=None):
        zoom_scale = float(getattr(self, "_zoom_scale", 1.0) or 1.0)
        if zoom_scale < 0.5:
            zoom_scale = 0.5
        elif zoom_scale > 3.0:
            zoom_scale = 3.0

        # The text is drawn at its real font size whatever the page zoom, so measure
        # the box from the real text. Scaling it made the box narrower than the text
        # when zoomed out, and the second line was cut off.
        if saved_w is None:
            size = self._text_label_target_size(None)
        else:
            size = self._text_label_target_size(max(1, int(round(float(saved_w) * zoom_scale))))
        target_w = max(1, int(size.width()))
        target_h = max(1, int(size.height()))
        if saved_h is not None:
            target_h = max(target_h, int(round(float(saved_h) * zoom_scale)))

        return QSize(target_w, target_h)

    def apply_size(self, w=None, h=None):
        """Apply specific dimensions or fall back to defaults based on widget type."""
        from ...chart_utils.geometry import ChartGeometry
        from .utils import _addon_config
        conf = _addon_config().config
        show_bottom_stats = conf.get(Config.DEEP_DIVE_PINNED_SHOW_BOTTOM_STATS, False)
        show_all_stats = conf.get(Config.DEEP_DIVE_PINNED_SHOW_STATS, True)
        zoom_scale = float(getattr(self, "_zoom_scale", 1.0) or 1.0)
        if zoom_scale < 0.5:
            zoom_scale = 0.5
        elif zoom_scale > 3.0:
            zoom_scale = 3.0

        self._last_size_args = (w, h)
        self.setMinimumSize(0, 0)
        self.setMaximumSize(16777215, 16777215)
        
        w_type = getattr(self, "wtype", self.widget_id)
        self._has_saved_height = (h is not None) and (w_type != "text_label")

        if w is not None:
            self.setMinimumWidth(max(1, int(round(w * zoom_scale))))
        if h is not None and w_type != "text_label":
            # If we are in deep dive or pinned mode, saved_h is the "Base" height.
            # We must add the statistics offset if they are currently enabled.
            offset = 0
            if show_bottom_stats and show_all_stats:
                offset = ChartGeometry.STATS_EXTRA_HEIGHT.get(w_type, 0)
            self.setMinimumHeight(max(1, int(round((h + offset) * zoom_scale))))
            
        # 2. If a dimension is missing (reset state), apply the type defaults.
        # Always recompute _content_min_h so the drag floor is correct, even when
        # apply_size gets a saved h.
        from ...stats_cards import StatCardWidget
        from ...charts.heatmap import HeatmapWidget
        from ...charts.pie_chart import PieChartWidget
        inner = getattr(self, "inner_widget", None)
        if inner:
            if w_type == "text_label":
                self._content_min_h = max(44, self._text_label_target_size(w).height())
            elif isinstance(inner, StatCardWidget):
                self._content_min_h = 100
            elif isinstance(inner, HeatmapWidget) or inner.findChild(HeatmapWidget):
                self._content_min_h = 60
            elif isinstance(inner, PieChartWidget):
                self._content_min_h = 200
            else:
                _base = 200
                if show_bottom_stats and show_all_stats:
                    _base += ChartGeometry.STATS_EXTRA_HEIGHT.get(w_type, 70)
                self._content_min_h = _base

        if w_type == "text_label":
            target_size = self._text_label_actual_target_size(w, h)
            self.setMinimumWidth(target_size.width())
            self.setMaximumWidth(target_size.width())
            self.setMinimumHeight(target_size.height())
            self.setMaximumHeight(target_size.height())
            try:
                self.resize(target_size)
            except Exception:
                log_swallowed()
        elif w is None or h is None:
            if inner:
                if w_type == "text_label":
                     auto_size = self._text_label_target_size(w)
                     if w is None:
                         self.setMinimumWidth(max(1, int(round(auto_size.width() * zoom_scale))))
                     if h is None:
                         self.setMinimumHeight(max(1, int(round(auto_size.height() * zoom_scale))))
                elif isinstance(inner, StatCardWidget):
                     if w is None: self.setMinimumWidth(max(1, int(round(200 * zoom_scale))))
                     if h is None: self.setMinimumHeight(max(1, int(round(self._content_min_h * zoom_scale))))
                elif isinstance(inner, HeatmapWidget) or inner.findChild(HeatmapWidget):
                     if w is None: self.setMinimumWidth(max(1, int(round(450 * zoom_scale))))
                     if h is None: self.setMinimumHeight(max(1, int(round(self._content_min_h * zoom_scale))))
                elif isinstance(inner, PieChartWidget):
                     if w is None: self.setMinimumWidth(max(1, int(round(220 * zoom_scale))))
                     if h is None: self.setMinimumHeight(max(1, int(round(self._content_min_h * zoom_scale))))
                else:
                     if w is None: self.setMinimumWidth(max(1, int(round(450 * zoom_scale))))
                     if h is None: self.setMinimumHeight(max(1, int(round(self._content_min_h * zoom_scale))))
            
            if w is None:
                self.setMinimumWidth(self.minimumWidth())
                self.setMaximumWidth(16777215)
            if h is None:
                self.setMinimumHeight(self.minimumHeight())
                self.setMaximumHeight(16777215)

        if getattr(self, "wtype", self.widget_id) == "text_label":
            try:
                pass
            except Exception:
                log_swallowed()

        if getattr(self, "_pinned_collapsed", False):
            ch = self._collapsed_height()
            self.setMinimumHeight(ch)
            self.setMaximumHeight(ch)

        self._fit_chart_min_heights()

        if self.parentWidget() and self.parentWidget().layout():
            self.parentWidget().layout().invalidate()
        self.updateGeometry()

    def _collapsed_height(self):
        layout = self.layout()
        if layout is None:
            return 30
        m = layout.contentsMargins()
        header_h = 0
        for idx in range(layout.count()):
            item = layout.itemAt(idx)
            w = item.widget() if item else None
            if w is None or w is getattr(self, "body_widget", None):
                continue
            header_h += max(22, int(w.sizeHint().height()))
        return int(m.top() + m.bottom() + header_h + 4)

    def _update_collapse_icon(self):
        btn = getattr(self, "_collapse_btn", None)
        if btn is None:
            return
        try:
            from ....ui.theme.icons import get_svg_icon
            from .utils import _theme_vars

            # Same color as the card title, so it follows the pinned theme.
            color = _theme_vars(self).get("text_secondary", "#888888")
            collapsed = bool(getattr(self, "_pinned_collapsed", False))
            btn.setIcon(get_svg_icon("chevron-right" if collapsed else "chevron-down", color=color, size=16))
        except Exception:
            log_swallowed()

    def toggle_collapsed(self):
        self.set_collapsed(not getattr(self, "_pinned_collapsed", False))

    def refresh_collapsible(self):
        """Apply the "Collapsible Charts" setting to this card right away."""
        btn = getattr(self, "_collapse_btn", None)
        if btn is None:
            return
        on = pinned_charts_collapsible()
        btn.setVisible(on)
        header = self.findChild(QLabel, "pinned_header")
        if header is not None and getattr(self, "_header_click_filter", None) is not None:
            header.setCursor(Qt.CursorShape.PointingHandCursor if on else Qt.CursorShape.ArrowCursor)
        if not on and getattr(self, "_pinned_collapsed", False):
            self.set_collapsed(False, remember=True)
        self._update_collapse_icon()

    def set_collapsed(self, collapsed, remember=True):
        collapsed = bool(collapsed)
        self._pinned_collapsed = collapsed
        if remember:
            if collapsed:
                _COLLAPSED_PINNED.add(self.widget_id)
            else:
                _COLLAPSED_PINNED.discard(self.widget_id)
        body = getattr(self, "body_widget", None)
        if body is not None:
            body.setVisible(not collapsed)
        self._update_collapse_icon()
        w, h = getattr(self, "_last_size_args", (None, None))
        self.apply_size(w, h)
        if remember:
            _refresh_pinned_overlay()

    def _fit_chart_min_heights(self):
        """Zoomed out, the card gets shorter but its charts kept their own minimum
        height, so the bottom of the chart was cut off. Let them shrink to the room
        the card really has, and give them their normal minimum back at 100 %."""
        inner = getattr(self, "inner_widget", None)
        if inner is None or getattr(self, "wtype", None) == "text_label":
            return
        try:
            from aqt.qt import QWidget
            charts = [c for c in inner.findChildren(QWidget) if hasattr(c, "set_chart_opacity")]
            if hasattr(inner, "set_chart_opacity"):
                charts.append(inner)
            if not charts:
                return
            zoomed_out = float(getattr(self, "_zoom_scale", 1.0) or 1.0) < 0.999
            _, extra_h, _ = self._layout_outer_metrics()
            avail = max(40, self.minimumHeight() - extra_h - 4)
            for c in charts:
                base = c.property("_dd_base_min_h")
                if base is None:
                    base = int(c.minimumHeight())
                    c.setProperty("_dd_base_min_h", base)
                base = int(base)
                c._zoom_min_cap = avail if zoomed_out else None
                c.setMinimumHeight(min(base, avail) if zoomed_out else base)
        except Exception:
            log_swallowed()

    def showEvent(self, event):
        super().showEvent(event)
        if self.resizable:
            self._install_edge_cursor_sync()
        if getattr(self, "wtype", self.widget_id) == "text_label":
            # The first size was measured before the row had its real width; measure again
            # once it has, or the text stays wrapped on a few short lines.
            QTimer.singleShot(0, self._safe_refit_text_label)
            QTimer.singleShot(300, self._safe_refit_text_label)

    def _safe_refit_text_label(self):
        try:
            self.refit_text_label()
        except RuntimeError:
            pass  # the card was deleted before the timer fired

    def refit_text_label(self):
        """Resize a text card to its current text (called by the label on change)."""
        if getattr(self, "wtype", self.widget_id) != "text_label":
            return
        if getattr(self, "_resize_mode", None):
            return  # the user is dragging the border
        if getattr(self, "inner_widget", None) is None:
            return
        w, h = getattr(self, "_last_size_args", (None, None))
        before = (self.minimumWidth(), self.minimumHeight())
        target = self._text_label_actual_target_size(w, h)
        if (target.width(), target.height()) == before:
            return
        self.apply_size(w, h)

    def sizeHint(self):
        if getattr(self, "wtype", self.widget_id) == "text_label" and getattr(self, "inner_widget", None) is not None:
            w = self.minimumWidth() if self.minimumWidth() > 0 else self.width()
            h = self.minimumHeight() if self.minimumHeight() > 0 else self.height()
            if w > 0 and h > 0:
                return QSize(int(w), int(h))
            return self._text_label_actual_target_size(None, None)
        return super().sizeHint()

    def minimumSizeHint(self):
        if getattr(self, "wtype", self.widget_id) == "text_label" and getattr(self, "inner_widget", None) is not None:
            w = self.minimumWidth() if self.minimumWidth() > 0 else self.width()
            h = self.minimumHeight() if self.minimumHeight() > 0 else self.height()
            if w > 0 and h > 0:
                return QSize(int(w), int(h))
            return self._text_label_actual_target_size(None, None)
        return super().minimumSizeHint()

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        if self.layout():
            h = self.layout().heightForWidth(width)
            if getattr(self, "widget_id", "") == "heatmap":
                pass
            return h
        h = self.height()
        if getattr(self, "widget_id", "") == "heatmap":
            pass
        return h

    def mousePressEvent(self, event):
        if getattr(self, "_fullscreen_active", False):
            # No resize or drag-to-reorder while shown fullscreen.
            self._resize_mode = None
            super().mousePressEvent(event)
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos_local = event.pos()
            if self.resizable:
                mode = self._check_border(event.pos())
                if mode:
                    self._resize_mode = mode
                    self._drag_start_pos = event.globalPosition().toPoint()
                    self._start_geom = self.geometry()
                    self._start_min_h = self.minimumHeight()
                    return
            else:
                self._resize_mode = None
        
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if getattr(self, "_fullscreen_active", False):
            super().mouseMoveEvent(event)
            return
        if not self.resizable:
            if (event.buttons() & Qt.MouseButton.LeftButton) and self.widget_id:
                self._handle_drag(event)
            super().mouseMoveEvent(event)
            return

        if not self._resize_mode:
            self._install_edge_cursor_sync()
            if not self._sync_edge_cursor(event.pos()):
                if (event.buttons() & Qt.MouseButton.LeftButton) and self.widget_id:
                    self._handle_drag(event)
        else:
            diff = event.globalPosition().toPoint() - self._drag_start_pos
            min_h = max(50, getattr(self, "_content_min_h", 50))
            new_w = max(100, self._start_geom.width())
            new_h = max(min_h, self._start_geom.height())

            if "r" in self._resize_mode:
                raw_w = max(100, self._start_geom.width() + diff.x())
                if self.parentWidget() and self.parentWidget().layout():
                    m = self.parentWidget().layout().contentsMargins()
                    max_avail_w = self.parentWidget().width() - m.left() - m.right()
                    raw_w = min(raw_w, max_avail_w)
                from ....ui.deep_dive.responsive_grid import ResponsiveGridLayout
                p_layout = self.parentWidget().layout() if (self.parentWidget() and self.parentWidget().layout()) else None
                if isinstance(p_layout, ResponsiveGridLayout) and p_layout.current_cols > 1:
                    _sp = p_layout.spacing()
                    _ml, _, _mr, _ = p_layout.getContentsMargins()
                    _eff_w = p_layout.geometry().width() - _ml - _mr
                    _col_w = (_eff_w - (p_layout.current_cols - 1) * _sp) // p_layout.current_cols
                    if _col_w > 0:
                        slots = round((raw_w + _sp) / (_col_w + _sp))
                        slots = max(1, min(p_layout.current_cols, slots))
                        new_w = slots * _col_w + (slots - 1) * _sp
                        self.col_span = slots
                    else:
                        new_w = raw_w
                else:
                    new_w = raw_w
            if "b" in self._resize_mode:
                new_h = max(min_h, self._start_geom.height() + diff.y())

            snapped_w, snapped_h = new_w, new_h

            snap_threshold = 15
            best_diff_h = snap_threshold
            
            if self.parentWidget():
                for child in self.parentWidget().children():
                    if child is self: continue
                    if not isinstance(child, type(self)): continue
                    if not child.isVisible(): continue
                    
                    if "b" in self._resize_mode:
                        diff_h = abs(child.height() - new_h)
                        if diff_h < best_diff_h:
                            best_diff_h = diff_h
                            snapped_h = child.height()
            
            # Apply changes only when the delta is significant (more than 5px), to avoid flicker from micro-movements.
            if abs(self.width() - snapped_w) < 5 and abs(self.height() - snapped_h) < 5:
                # Still accept the move event so the cursor logic stays smooth 
                # but don't trigger the expensive layout/sync sequence.
                super().mouseMoveEvent(event)
                return

            # During a live resize use a fixed size to force the layout to follow; setting both min and max overrides earlier fixed constraints.
            self.setFixedSize(snapped_w, snapped_h)
            
            if self.parentWidget():
                if self.parentWidget().layout():
                    self.parentWidget().layout().invalidate()
                self.parentWidget().updateGeometry()
            
            self._sync_all()
            # Only propagate row-height sync while vertical resizing is active. During a
            # horizontal resize it could sync neighboring rows after the col_span reflow.
            if self._resize_mode and ("b" in self._resize_mode):
                self.height_changed.emit(snapped_h)

        super().mouseMoveEvent(event)

    def setOpacity(self, opacity):
        """Standardized ghosting effect using QGraphicsOpacityEffect."""
        if opacity >= 1.0:
            self.setGraphicsEffect(None)
        else:
            eff = QGraphicsOpacityEffect(self)
            eff.setOpacity(opacity)
            self.setGraphicsEffect(eff)

    def mouseReleaseEvent(self, event):
        if self._resize_mode:
            release_mode = self._resize_mode  # save before clearing
            self._resize_mode = None
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))

            if self.widget_id:
                w, h = self.width(), self.height()
                zoom_scale = float(getattr(self, "_zoom_scale", 1.0) or 1.0)
                if zoom_scale <= 0:
                    zoom_scale = 1.0

                # Compute col_span from the final drag position. The drag is free (no column
                # snap during the move), so round to the nearest column once, on release.
                if "r" in release_mode:
                    from ....ui.deep_dive.responsive_grid import ResponsiveGridLayout
                    p_layout = self.parentWidget().layout() if (self.parentWidget() and self.parentWidget().layout()) else None
                    if isinstance(p_layout, ResponsiveGridLayout) and p_layout.current_cols > 1:
                        num_cols = p_layout.current_cols
                        _sp = p_layout.spacing()
                        _ml, _, _mr, _ = p_layout.getContentsMargins()
                        _eff_w = p_layout.geometry().width() - _ml - _mr
                        _col_w = (_eff_w - (num_cols - 1) * _sp) // num_cols
                        if _col_w > 0:
                            slots = round((w + _sp) / (_col_w + _sp))
                            self.col_span = max(1, min(num_cols, slots))
                            w = self.col_span * _col_w + (self.col_span - 1) * _sp
                
                if "b" in release_mode:
                    # Subtract the extra stats height so the saved config always holds the base
                    # chart height, like _persist_grid_row_height does in the grid layout.
                    from ...chart_utils.geometry import ChartGeometry
                    from .utils import _addon_config
                    conf = _addon_config().config
                    if conf.get(Config.DEEP_DIVE_PINNED_SHOW_BOTTOM_STATS, False) and conf.get(Config.DEEP_DIVE_PINNED_SHOW_STATS, True):
                        offset = ChartGeometry.STATS_EXTRA_HEIGHT.get(self.widget_id, 0)
                        h = max(50, h - offset)

                    w_save = max(1, int(round(w / zoom_scale)))
                    h_save = max(50, int(round(h / zoom_scale)))

                    if self.save_callback:
                        self.save_callback(self, w_save, h_save)
                    else:
                        WidgetRegistry.update_setting(self.widget_id, "width", w_save)
                        WidgetRegistry.update_setting(self.widget_id, "height", h_save)
                        WidgetRegistry.update_setting(self.widget_id, "col_span", self.col_span)
                    self.col_span_changed.emit(self.col_span)
                    self.apply_size(w_save, h_save)
                else:
                    # Horizontal-only resize: leave the saved height alone. Restore the pre-drag
                    # minimumHeight so the widget is not stuck at the grid-stretched height.
                    w_save = max(1, int(round(w / zoom_scale)))
                    if self.save_callback:
                        self.save_callback(self, w_save, None)
                    else:
                        WidgetRegistry.update_setting(self.widget_id, "width", w_save)
                        WidgetRegistry.update_setting(self.widget_id, "col_span", self.col_span)
                    self.col_span_changed.emit(self.col_span)
                    self.apply_size(w_save, None)
                    start_min_h = getattr(self, "_start_min_h", 0)
                    if getattr(self, "wtype", self.widget_id) != "text_label" and start_min_h > 0:
                        self.setMinimumHeight(start_min_h)
            
            self._sync_all()
                
        super().mouseReleaseEvent(event)


    def _sync_all(self):
        """Trigger global sync of overlay, mask, and Anki placeholder."""
        _refresh_pinned_overlay()

    def _handle_drag(self, event):

        
        DragInitiator.maybe_start_drag(
            self, event, self._drag_start_pos_local,
            MIME_CHART_ID, self.widget_id
        )
        

    def _sync_edge_cursor(self, pos):
        """Set the cursor for a position in this widget. Returns True on a resize border."""
        if self._resize_mode or getattr(self, "_fullscreen_active", False) or not self.resizable:
            return False
        mode = self._check_border(pos)
        shape = {
            "rb": Qt.CursorShape.SizeFDiagCursor,
            "r": Qt.CursorShape.SizeHorCursor,
            "b": Qt.CursorShape.SizeVerCursor,
        }.get(mode)
        self.setCursor(QCursor(shape or Qt.CursorShape.ArrowCursor))
        return shape is not None

    def _install_edge_cursor_sync(self):
        sync = getattr(self, "_edge_cursor_sync", None)
        if sync is None:
            sync = self._edge_cursor_sync = _EdgeCursorSync(self)
        for child in self.findChildren(QWidget):
            child.installEventFilter(sync)

    def leaveEvent(self, event):
        if not self._resize_mode:
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        super().leaveEvent(event)

    def _check_border(self, pos):
        w, h = self.width(), self.height()
        x, y = pos.x(), pos.y()
        
        dirs = self.resize_directions if self.resize_directions else ["r", "b"]
        if getattr(self, "_pinned_collapsed", False):
            dirs = [d for d in dirs if d != "b"]
        
        on_right = "r" in dirs and (w - self.border_sensitivity) <= x <= w
        on_bottom = "b" in dirs and (h - self.border_sensitivity) <= y <= h
        
        if on_right and on_bottom: return "rb"
        if on_right: return "r"
        if on_bottom: return "b"
        return None

def _wrap(inner_widget, label, header_widget=None, base_color=None, wtype=None, widget_id=None, saved_w=None, saved_h=None, resizable=True, parent=None):
    """Wrap *inner_widget* in a styled card with a header label or custom header widget."""
    resize_dirs = ["r"] if wtype == "text_label" else None
    card = ResizableWrapper(widget_id, saved_w, saved_h, resizable=resizable, resize_directions=resize_dirs, parent=parent)
    card.wtype = wtype
    if wtype == "text_label":
        label = None
    
    layout = QVBoxLayout(card)
    top_margin = 3 if (header_widget or label is not None) else 2
    layout.setContentsMargins(6, top_margin, 6, 6)
    layout.setSpacing(2)
    
    apply_style(card, base_color=base_color, inner_widget=inner_widget)
    
    from ...stats_cards import StatCardWidget

    # The arrow is always built for charts and shown or hidden by the setting, so the
    # setting applies without rebuilding the widgets.
    collapsible = wtype != "text_label" and not isinstance(inner_widget, StatCardWidget)
    collapsible_on = pinned_charts_collapsible()
    collapse_btn = None
    if collapsible and (header_widget or label):
        collapse_btn = QPushButton("", parent=card)
        collapse_btn.setFixedSize(18, 20)
        collapse_btn.setFlat(True)
        collapse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        collapse_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        collapse_btn.setToolTip("Collapse / expand")
        set_qss(collapse_btn, "QPushButton { background: transparent; border: none; padding: 0; }")
        collapse_btn.clicked.connect(card.toggle_collapsed)
        collapse_btn.setVisible(collapsible_on)
        card._collapse_btn = collapse_btn

    if header_widget:
        header_widget.setCursor(Qt.CursorShape.ArrowCursor)
        if collapse_btn is not None and header_widget.layout() is not None:
            header_widget.layout().insertWidget(0, collapse_btn)
        elif collapse_btn is not None:
            collapse_btn.hide()
            card._collapse_btn = None
        layout.addWidget(header_widget)
    elif label:
        header = QLabel(label.upper())
        header.setObjectName("pinned_header")
        header.setCursor(Qt.CursorShape.ArrowCursor)
        if collapse_btn is not None:
            row = QWidget(card)
            row_lay = QHBoxLayout(row)
            row_lay.setContentsMargins(0, 0, 0, 0)
            row_lay.setSpacing(4)
            row_lay.addWidget(collapse_btn)
            row_lay.addWidget(header)
            row_lay.addStretch(1)
            header.setCursor(Qt.CursorShape.PointingHandCursor if collapsible_on else Qt.CursorShape.ArrowCursor)
            click_filter = _HeaderClickFilter(card.toggle_collapsed, header)
            header.installEventFilter(click_filter)
            card._header_click_filter = click_filter
            layout.addWidget(row)
        else:
            layout.addWidget(header)

    set_qss(inner_widget, "background: transparent; border: none;")
    inner_widget.setCursor(Qt.CursorShape.ArrowCursor)
    if wtype == "text_label":
        inner_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
    else:
        inner_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    # Used by chart widgets to run startup animation only once per pinned widget id.
    setattr(inner_widget, "_pinned_widget_id", widget_id)
    layout.addWidget(inner_widget)
    card.inner_widget = inner_widget
    card.body_widget = inner_widget
    
    card.apply_size(saved_w, saved_h)

    if getattr(card, "_collapse_btn", None) is not None:
        card._pinned_collapsed = collapsible_on and widget_id in _COLLAPSED_PINNED
        if card._pinned_collapsed:
            inner_widget.setVisible(False)
            card.apply_size(saved_w, saved_h)
        card._update_collapse_icon()
    

    if wtype == "text_label":
        card.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    else:
        card.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.MinimumExpanding)

    return card




