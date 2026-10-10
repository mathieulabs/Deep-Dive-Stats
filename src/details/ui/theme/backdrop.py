# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Painted window backdrop for the Deep Dive window.

A soft vertical gradient, two glows tinted from the theme accent and a light
grain against banding in dark mode, all derived from the active palette.

Adjustable in Settings > Colors > Window Background (BACKDROP_KEY config).
It is rendered once into a pixmap per (size, colors, settings) and blitted on
paint.
"""

import random
import weakref

from aqt.qt import (
    QColor,
    QEvent,
    QImage,
    QObject,
    QPainter,
    QPixmap,
    QPointF,
    QRectF,
    QRadialGradient,
    QLinearGradient,
    Qt,
)

from .design_overrides import _colors, _mix
from ...logic.logger import log_swallowed

BACKDROP_KEY = "Deep_Dive_Backdrop"

# 0-100 sliders. "tone" is how much deeper than the theme background the window
# is (darker for dark themes, a faint grey for light ones). Colors are "" for
# automatic (theme accent) or "#rrggbb".
BACKDROP_DEFAULTS = {
    "enabled": True,
    "tone": 50,
    "glow": 0,
    "glow2": 0,
    "depth": 0,
    "grain": 0,
    "color1": "",
    "color2": "",
}

# Presets only touch these keys; the user's colors are kept.
BACKDROP_PRESETS = {
    "clean": {"tone": 50, "glow": 0, "glow2": 0, "depth": 0, "grain": 0},
    "subtle": {"tone": 50, "glow": 30, "glow2": 25, "depth": 35, "grain": 15},
    "balanced": {"tone": 50, "glow": 50, "glow2": 50, "depth": 50, "grain": 25},
    "vivid": {"tone": 50, "glow": 90, "glow2": 85, "depth": 70, "grain": 30},
}

_PROP = "_deep_dive_backdrop"
_NOISE_TILES = {}


def get_backdrop_settings(conf):
    """Settings dict merged over the defaults, clamped to sane ranges."""
    out = dict(BACKDROP_DEFAULTS)
    raw = conf.get(BACKDROP_KEY) if isinstance(conf, dict) else None
    if isinstance(raw, dict):
        for k in BACKDROP_DEFAULTS:
            if k in raw:
                out[k] = raw[k]
    out["enabled"] = bool(out["enabled"])
    for k in ("tone", "glow", "glow2", "depth", "grain"):
        try:
            out[k] = max(0, min(100, int(out[k])))
        except (TypeError, ValueError):
            out[k] = BACKDROP_DEFAULTS[k]
    for k in ("color1", "color2"):
        v = out.get(k) or ""
        out[k] = v if isinstance(v, str) and QColor(v).isValid() and v.startswith("#") else ""
    return out


def matching_preset(settings):
    """Name of the preset the settings correspond to, 'off', or None (custom)."""
    if not settings.get("enabled", True):
        return "off"
    for name, vals in BACKDROP_PRESETS.items():
        if all(settings.get(k) == v for k, v in vals.items()):
            return name
    return None


def _noise_tile(is_dark):
    """Small tileable grain texture (at grain=100), generated once per mode."""
    tile = _NOISE_TILES.get(is_dark)
    if tile is not None:
        return tile
    size = 96
    img = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    rnd = random.Random(7)
    max_a = 14 if is_dark else 10
    for y in range(size):
        for x in range(size):
            a = rnd.randint(0, max_a)
            if a < 3:
                continue
            v = 255 if rnd.random() < 0.5 else 0
            img.setPixelColor(x, y, QColor(v, v, v, a))
    tile = QPixmap.fromImage(img)
    _NOISE_TILES[is_dark] = tile
    return tile


def glow_colors(accent, settings):
    """(main, second) glow colors: the user's picks, or the theme accent."""
    c1 = settings.get("color1") or accent
    c2 = settings.get("color2") or accent
    return c1, c2


def _eased(grad, color, alpha):
    """Radial falloff without a visible edge (roughly a gaussian)."""
    for pos, f in ((0.0, 1.0), (0.18, 0.66), (0.38, 0.34), (0.6, 0.13), (0.82, 0.035), (1.0, 0.0)):
        c = QColor(color)
        c.setAlphaF(max(0.0, min(1.0, alpha * f)))
        grad.setColorAt(pos, c)


def render_backdrop(w, h, dpr, bg, accent, is_dark, settings):
    """Render the backdrop into a QPixmap of logical size w x h."""
    dark = bool(is_dark)
    s = settings
    k_glow = s["glow"] / 50.0
    k_glow2 = s["glow2"] / 50.0
    k_depth = s["depth"] / 50.0
    c1, c2 = glow_colors(accent, s)

    pm = QPixmap(max(1, int(w * dpr)), max(1, int(h * dpr)))
    pm.setDevicePixelRatio(dpr)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    full = QRectF(0, 0, w, h)
    span = max(w, h)

    k_tone = s["tone"] / 50.0

    # 1. Base: a deeper version of the theme bg (tone), faintly tinted with
    #    the glow color, lighter at the top and darker at the bottom.
    deep = _mix(bg, "#000000", min(0.8, (0.42 if dark else 0.035) * k_tone))
    base = _mix(deep, c1, 0.03 if dark else 0.02)
    lin = QLinearGradient(0, 0, 0, h)
    lin.setColorAt(0.0, QColor(_mix(base, c1, min(0.4, 0.045 * k_glow))))
    lin.setColorAt(0.55, QColor(base))
    lin.setColorAt(1.0, QColor(_mix(base, "#000000", min(0.6, (0.16 if dark else 0.04) * k_depth))))
    p.fillRect(full, lin)

    # 2. Main glow: above the top edge, center-right (where the window is
    #    mostly empty, so it stays visible behind the table).
    if k_glow > 0:
        rg = QRadialGradient(QPointF(w * 0.66, -h * 0.30), span * 0.62)
        _eased(rg, c1, (0.20 if dark else 0.10) * k_glow)
        p.fillRect(full, rg)

    # 3. Second glow: below the bottom-left corner.
    if k_glow2 > 0:
        rg2 = QRadialGradient(QPointF(w * 0.02, h * 1.18), span * 0.55)
        _eased(rg2, c2, (0.10 if dark else 0.06) * k_glow2)
        p.fillRect(full, rg2)

    # 4. Vignette: edges slightly darker, gives depth.
    if k_depth > 0:
        vg = QRadialGradient(QPointF(w / 2, h * 0.40), span * 0.72)
        vg.setColorAt(0.0, QColor(0, 0, 0, 0))
        vg.setColorAt(0.5, QColor(0, 0, 0, 0))
        edge = QColor(0, 0, 0)
        edge.setAlphaF(min(1.0, (0.20 if dark else 0.04) * k_depth))
        vg.setColorAt(1.0, edge)
        p.fillRect(full, vg)

    # 5. Grain.
    if s["grain"] > 0:
        p.setOpacity(s["grain"] / 100.0)
        p.drawTiledPixmap(full, _noise_tile(dark))
        p.setOpacity(1.0)
    p.end()
    return pm


class _BackdropFilter(QObject):
    def __init__(self, dialog):
        super().__init__(dialog)
        self._dialog = dialog
        self.colors = None  # (bg, accent)
        self.is_dark = True
        self.settings = dict(BACKDROP_DEFAULTS)
        self._cache_key = None
        self._cache = None
        self._listeners = []

    def add_listener(self, widget):
        """Widgets (e.g. the settings preview) repainted on theme changes."""
        self._listeners.append(weakref.ref(widget))

    def set_theme(self, is_dark, palette, settings):
        c = _colors(is_dark, palette)
        self.is_dark = bool(is_dark)
        self.colors = (c["bg"], c["accent"])
        self.settings = settings
        self._cache_key = None
        self._dialog.update()
        alive = []
        for ref in self._listeners:
            w = ref()
            if w is None:
                continue
            try:
                w.update()
                alive.append(ref)
            except RuntimeError:
                pass
        self._listeners = alive

    def eventFilter(self, obj, event):
        if (
            obj is self._dialog
            and event.type() == QEvent.Type.Paint
            and self.colors
            and self.settings.get("enabled", True)
        ):
            try:
                w, h = obj.width(), obj.height()
                dpr = obj.devicePixelRatioF()
                key = (w, h, dpr, self.colors, self.is_dark, tuple(sorted(self.settings.items())))
                if key != self._cache_key:
                    self._cache = render_backdrop(
                        w, h, dpr, self.colors[0], self.colors[1], self.is_dark, self.settings
                    )
                    self._cache_key = key
                p = QPainter(obj)
                r = QRectF(event.rect())
                # Source rect is in device pixels of the cached pixmap.
                src = QRectF(r.x() * dpr, r.y() * dpr, r.width() * dpr, r.height() * dpr)
                p.drawPixmap(r, self._cache, src)
                p.end()
            except Exception:
                log_swallowed()
        return False


def get_backdrop_filter(dialog):
    return getattr(dialog, _PROP, None)


def install_backdrop(dialog, is_dark, palette):
    """Install (once) and refresh the painted backdrop on a dialog."""
    flt = getattr(dialog, _PROP, None)
    if flt is None:
        flt = _BackdropFilter(dialog)
        dialog.installEventFilter(flt)
        setattr(dialog, _PROP, flt)
    conf = getattr(getattr(dialog, "addon_config", None), "config", None) or {}
    flt.set_theme(is_dark, palette, get_backdrop_settings(conf))


def refresh_backdrop_settings(dialog):
    """Re-read the backdrop settings from config (theme unchanged)."""
    flt = getattr(dialog, _PROP, None)
    if flt is None or flt.colors is None:
        return
    conf = getattr(getattr(dialog, "addon_config", None), "config", None) or {}
    flt.settings = get_backdrop_settings(conf)
    flt._cache_key = None
    dialog.update()
