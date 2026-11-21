"""The first size of the add-on's windows."""

import sys


def size_window(w, geom, size, minimum):
    """size and minimum on a computer. On Android, Kioku makes every window
    fill the screen right after it shows (kioku/windows.py _fill: the available
    geometry, one pixel taller): taken at once, the page lays out once at its
    real width instead of at ours first (Deep Dive, the gallery, the settings
    were seen settling into place)."""
    if sys.platform == "android":
        w.setGeometry(geom.adjusted(0, 0, 0, 1))
        return
    w.resize(*size)
    w.setMinimumSize(*minimum)



def follow_safe_area(w):
    """On Android: keep Kioku's title bar (Back) under the status bar. Kioku places it on each resize from the
    window's safe area; a window shown again (Deep Dive is kept hidden between openings) got one last resize while
    that area still read 0, so the bar sat over the clock until the window was built again. After a resize, a bar
    that isn't where the safe area says gets one more layout. Call from showEvent."""
    if sys.platform != "android" or getattr(w, "_safe_area_filter", None) is not None:
        return
    from aqt.qt import QApplication, QEvent, QObject, QResizeEvent, QTimer

    state = {"fixes": 0}

    def check():
        try:
            handle = w.windowHandle()
            if handle is None or not w.isVisible():
                return
            top = handle.safeAreaMargins().top()
            bars = [c for c in w.children() if type(c).__name__ == "TitleBar"]
            if not bars or bars[0].y() == top or state["fixes"] >= 3:
                return
            state["fixes"] += 1
            QApplication.sendEvent(w, QResizeEvent(w.size(), w.size()))
        except RuntimeError:
            pass  # the window is gone

    class _Filter(QObject):
        def eventFilter(self, obj, event):
            kind = event.type()
            if kind == QEvent.Type.Show:
                state["fixes"] = 0
            elif kind == QEvent.Type.Resize:
                QTimer.singleShot(0, check)
            return False

    w._safe_area_filter = _Filter(w)
    w.installEventFilter(w._safe_area_filter)
    handle = w.windowHandle()
    if handle is not None and hasattr(handle, "safeAreaMarginsChanged"):
        handle.safeAreaMarginsChanged.connect(lambda _m: QTimer.singleShot(0, check))
