# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt import mw
from aqt.qt import (
    QWidget,
    QHBoxLayout,
    Qt,
    QRegion,
)

from .masonry_layout import MasonryLayout
from .....logic.logger import log_swallowed

class PinnedOverlay(QWidget):
    """
    Transparent overlay that uses masking to allow click-through on empty areas.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        from aqt.qt import QTimer
        self._mask_timer = QTimer(self)
        self._mask_timer.setSingleShot(True)
        self._mask_timer.timeout.connect(self.update_mask)
        if parent is not None:
            parent.installEventFilter(self)

    def eventFilter(self, obj, event):
        from aqt.qt import QEvent, QTimer
        if obj is self.parentWidget() and event.type() == QEvent.Type.ChildAdded:
            child = event.child()
            if isinstance(child, QWidget) and child is not self:
                QTimer.singleShot(0, self.keep_above_page)
        return False

    def wheelEvent(self, event):
        # A child widget that ignored the event (no Ctrl+zoom) bubbles it here. Scroll the page by
        # injecting a scroll command into the WebView, since standard propagation to QWebEngineView
        # often fails.

        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            # Ctrl + wheel is Anki's interface zoom. Over a pinned widget the event never
            # reaches the page, so apply the zoom here (same 10 % step as View > Zoom In).
            web = self.parent()
            delta = event.angleDelta().y()
            if delta and web is not None and hasattr(web, "setZoomFactor"):
                zoom = web.zoomFactor() + (0.1 * delta / 120.0)
                web.setZoomFactor(round(max(0.25, min(5.0, zoom)), 2))
                try:
                    from ..manager import MainMenuWidgetManager
                    if MainMenuWidgetManager.instance_exists():
                        MainMenuWidgetManager.instance().sync_overlay()
                except Exception:
                    log_swallowed()
                event.accept()
            else:
                event.ignore()
            return

        delta = event.angleDelta().y()
        if delta == 0:
            return

        scroll_amount = -delta

        cmd = f"window.scrollBy({{top: {scroll_amount}, left: 0, behavior: 'auto'}});"
        if self.parent() and hasattr(self.parent(), "eval"):
            self.parent().eval(cmd)
        else:
            mw.web.eval(cmd)

        event.accept()

    def update_mask(self):
        """Update the mask to only allow events on child widgets."""
        if not self.isVisible():
            return

        visible_region = QRegion()

        if not self.layout():
            return

        for i in range(self.layout().count()):
            item = self.layout().itemAt(i)
            if not item or not item.widget(): continue
            w = item.widget()

            if not w.isVisible(): continue
            from ....stats_cards import StatCardsContainer
            if isinstance(w, StatCardsContainer):
                for card in w.cards:
                     if card.isVisible():
                         geo = card.geometry()
                         geo.translate(w.geometry().topLeft())
                         visible_region += geo.adjusted(-20, -20, 20, 20)

            elif w.layout() and isinstance(w.layout(), MasonryLayout):
                 for j in range(w.layout().count()):
                     c_item = w.layout().itemAt(j)
                     if c_item and c_item.widget() and c_item.widget().isVisible():
                         cw = c_item.widget()
                         geo = cw.geometry()
                         geo.translate(w.geometry().topLeft())
                         visible_region += geo.adjusted(-20, -20, 20, 20)

            elif w.layout() and isinstance(w.layout(), QHBoxLayout):
                 for j in range(w.layout().count()):
                     c_item = w.layout().itemAt(j)
                     if c_item and c_item.widget() and c_item.widget().isVisible():
                         cw = c_item.widget()
                         geo = cw.geometry()
                         geo.translate(w.geometry().topLeft())
                         visible_region += geo.adjusted(-20, -20, 20, 20)

            else:
                visible_region += w.geometry().adjusted(-20, -20, 20, 20)

        # A drag's gap marker (it can sit in the room opened above / below the boxes) and
        # the box handle: never cut off by the mask.
        for attr in ("_dd_gap_marker", "_dd_spot_marker"):
            extra = getattr(self, attr, None)
            try:
                if extra is not None and extra.isVisible():
                    visible_region += extra.geometry().adjusted(-2, -2, 2, 2)
            except RuntimeError:
                pass
        gaps = getattr(self, "_dd_gap_hover", None)
        try:
            if gaps is not None:
                for extra in (gaps.bar, gaps._label):
                    if extra.isVisible():
                        visible_region += extra.geometry().adjusted(-2, -2, 2, 2)
        except RuntimeError:
            pass
        hover = getattr(self, "_dd_section_hover", None)
        try:
            if hover is not None and hover.grip.isVisible():
                visible_region += hover.grip.geometry().adjusted(-2, -2, 2, 2)
        except RuntimeError:
            pass
        adder = getattr(self, "_dd_add_hover", None)
        try:
            if adder is not None and adder.plus.isVisible():
                visible_region += adder.plus.geometry().adjusted(-2, -2, 2, 2)
        except RuntimeError:
            pass

        self.setMask(visible_region)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Debounce mask updates during active resizing to prevent flickering (16ms is about 60fps).
        self._mask_timer.start(16)

    def paintEvent(self, event):
        pass

    def keep_above_page(self):
        """Stay above the web view's own drawing surface. The web view makes that surface
        again when its renderer starts over (first page of a profile, a crashed renderer,
        a GPU change...), and the new one comes on top: the page then hid the widgets
        (an empty box showed where they are)."""
        try:
            parent = self.parentWidget()
            if parent is None:
                return
            siblings = [c for c in parent.children() if isinstance(c, QWidget) and c.isVisible()]
            if siblings and siblings[-1] is not self and self in siblings:
                self.raise_()
        except RuntimeError:
            pass






