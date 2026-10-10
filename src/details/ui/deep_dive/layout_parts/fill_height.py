# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Stretch the Deep Dive cards to the window height when they would leave empty space."""
from aqt.qt import QEvent, QObject, QTimer

from ... import Config
from ....logic.logger import log_swallowed

_MARGIN = 2  # keep the content a hair shorter than the viewport so no scrollbar flickers


def enabled(manager):
    try:
        return bool(manager.addon_config.config.get(Config.DEEP_DIVE_FILL_HEIGHT, True))
    except Exception:
        return True


def update(manager):
    """Tell the grid how tall it may be: the viewport minus whatever sits above it."""
    lay = getattr(manager, "masonry_layout", None)
    if lay is None:
        return
    try:
        if not enabled(manager):
            lay.set_fill_height(0)
            return
        scroll = manager.dialog.expanded_scroll
        area = manager.dialog.expanded_chart_area
        grid = lay.parentWidget()
        others = 0
        for i in range(area.count()):
            w = area.itemAt(i).widget()
            if w is None or w is grid or not w.isVisible():
                continue
            others += w.height()
        m = area.contentsMargins()
        avail = scroll.viewport().height() - others - m.top() - m.bottom() - _MARGIN
        lay.set_fill_height(avail)
    except Exception:
        log_swallowed()


class _ViewportFilter(QObject):
    def __init__(self, manager):
        super().__init__(manager.dialog)
        self._manager = manager
        self._pending = False

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Resize and not self._pending:
            self._pending = True
            QTimer.singleShot(0, self._run)
        return False

    def _run(self):
        self._pending = False
        update(self._manager)


def install(manager):
    """Watch the scroll viewport once, and apply the current size."""
    if getattr(manager, "_fill_filter", None) is None:
        try:
            manager._fill_filter = _ViewportFilter(manager)
            manager.dialog.expanded_scroll.viewport().installEventFilter(manager._fill_filter)
        except Exception:
            log_swallowed()
    QTimer.singleShot(0, lambda: update(manager))
