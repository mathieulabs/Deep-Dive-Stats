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
                
        self.setMask(visible_region)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Debounce mask updates during active resizing to prevent flickering (16ms is about 60fps).
        self._mask_timer.start(16)
        
    def paintEvent(self, event):
        pass






