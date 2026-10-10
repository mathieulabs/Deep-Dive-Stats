# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Keep the tab bar from staying scrolled when there is room to show every tab."""
from aqt.qt import QEvent, QObject, QTimer

from ...logic.logger import log_swallowed


class _TabScrollFix(QObject):
    def __init__(self, tab_bar):
        super().__init__(tab_bar)
        self._bar = tab_bar
        self._queued = False
        tab_bar.installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() in (QEvent.Type.Resize, QEvent.Type.Show) and not self._queued:
            self._queued = True
            QTimer.singleShot(0, self.fix)
        return False

    def fix(self, force=False):
        self._queued = False
        try:
            bar = self._bar
            visible = [i for i in range(bar.count()) if bar.isTabVisible(i)]
            if len(visible) < 2 or not bar.isVisible():
                return
            first, last = visible[0], visible[-1]
            scrolled = bar.tabRect(first).x() < 0
            empty_right = bar.tabRect(last).right() < bar.width() - 60
            if not (force or (scrolled and empty_right)):
                return
            cur = bar.currentIndex()
            # Back to offset 0, then scroll just enough to show the current tab.
            bar.blockSignals(True)
            try:
                bar.setCurrentIndex(first)
                bar.setCurrentIndex(cur)
            finally:
                bar.blockSignals(False)
        except Exception:
            log_swallowed()


def install(tab_widget):
    bar = tab_widget.tabBar()
    if getattr(bar, "_scroll_fix", None) is None:
        bar._scroll_fix = _TabScrollFix(bar)
