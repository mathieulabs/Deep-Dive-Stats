# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""The Deep Dive window's backdrop settings (Settings > Colors > Window Background, BACKDROP_KEY config).

A soft vertical gradient, two glows tinted from the theme accent and a light grain, drawn by the page from the
numbers web_ui/theme.backdrop_spec sends it.
"""

from aqt.qt import QColor

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


def glow_colors(accent, settings):
    """(main, second) glow colors: the user's picks, or the theme accent."""
    c1 = settings.get("color1") or accent
    c2 = settings.get("color2") or accent
    return c1, c2


def refresh_backdrop_settings(dialog):
    """The settings changed: the web Deep Dive window (web_ui/window.py) sends its page the theme again, whose
    backdrop it draws (backdrop_spec). Without this, Settings > Window Background changed nothing there until saved
    and reopened."""
    push = getattr(dialog, "_theme_cb", None)
    if callable(push):
        try:
            push()
        except Exception:
            log_swallowed()
