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
