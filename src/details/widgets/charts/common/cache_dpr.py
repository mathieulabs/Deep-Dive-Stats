# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
import math


def cache_dpr(widget, painter=None):
    """Device pixel ratio for a cached pixmap drawn with painter.

    Normally the widget's own ratio. When the painter is scaled up (the visual
    export uses a 2x painter) the cache must be rendered at that scale too, or
    text and lines come out blurry.
    """
    try:
        dpr = max(1.0, float(widget.devicePixelRatioF()))
    except Exception:
        dpr = 1.0
    if _EXPORTING[0]:
        # Exact export scale: the bitmap then maps 1:1 onto the export's
        # pixels (no resampling, so text stays sharp).
        return _EXPORT_SCALE[0]
    try:
        if painter is not None:
            scale = float(painter.worldTransform().m11())
            try:
                scale *= max(1.0, float(painter.device().devicePixelRatioF()))
            except Exception:
                log_swallowed()
            if scale > dpr:
                dpr = min(4.0, math.ceil(scale * 2.0) / 2.0)
    except Exception:
        log_swallowed()
    return dpr


# Visual export: the grid, axis and overlay caches are bitmaps at screen
# resolution and came out blurry in a 2x export. While exporting they are
# rebuilt at the export's exact scale (see cache_dpr) in a marked pixmap that is
# never reused on screen. A vector QPicture cannot be used: it does not replay
# everything the charts draw (e.g. Hourly's faded area).
from aqt.qt import QPixmap
from ....logic.logger import log_swallowed

_EXPORTING = [False]
_EXPORT_SCALE = [1.0]


def set_exporting(on, scale=None):
    """Mark an export in progress; *scale* is the export's device pixels per
    widget pixel for the section being rendered (e.g. 2.0)."""
    _EXPORTING[0] = bool(on)
    if not on:
        _EXPORT_SCALE[0] = 1.0
    elif scale is not None:
        _EXPORT_SCALE[0] = max(1.0, float(scale))


def exporting():
    return _EXPORTING[0]


def raster_dpr(widget=None, painter=None):
    """Resolution for an offscreen bitmap: the widget/device ratio, or the
    export's scale while exporting (so it isn't upscaled and blurred)."""
    dpr = 1.0
    try:
        if widget is not None:
            dpr = max(dpr, float(widget.devicePixelRatioF()))
    except Exception:
        log_swallowed()
    try:
        if painter is not None:
            dpr = max(dpr, float(painter.device().devicePixelRatioF()))
    except Exception:
        log_swallowed()
    if _EXPORTING[0]:
        dpr = max(dpr, _EXPORT_SCALE[0])
    return dpr


class _ExportPixmap(QPixmap):
    """Cache bitmap made during an export (at the export's resolution)."""


def cache_surface(width_px, height_px):
    """Bitmap for a chart cache; marked when made during an export."""
    if exporting():
        return _ExportPixmap(width_px, height_px)
    return QPixmap(width_px, height_px)


def stale_cache(cache):
    """True when a stored cache must be rebuilt regardless of its key:
    always while exporting, and for an export-made bitmap afterwards."""
    return exporting() or isinstance(cache, _ExportPixmap)


def draw_cache(painter, cache, x=0, y=0):
    painter.drawPixmap(x, y, cache)
