# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Glass settings of the web pinned widgets (web_ui/pinned.py): what is behind a box blurred (frosted glass)
and a soft shadow under it. The native boxes can do neither, so these sliders do not show with the native interface (dev).

add_web_glass(dialog, layout, prefix, blur_key, shadow_key) puts the sliders in layout as
dialog.<prefix>blur_slider and dialog.<prefix>shadow_slider; write_web_glass(dialog, conf, ...) saves them."""

from __future__ import annotations

from .components import SettingsSlider
from .....i18n import tr


_AUTO_BLUR = 14  # px: the default blur (a saved -1, the former "Auto", is this one too: pinned.js AUTO_BLUR)


def web_preview_on(dialog=None):
    if dialog is not None and getattr(dialog, "is_grid", False):
        return False
    try:
        from .....web_ui.pinned import enabled

        return bool(enabled())
    except Exception:
        return False


def add_web_glass(dialog, layout, prefix, blur_key, shadow_key):
    if not web_preview_on(dialog):
        return
    from .....const.config import Config

    raw = dialog.addon_config.get(blur_key, Config.DEFAULT_CONFIG.get(blur_key, 0))
    raw = 0 if raw is None else int(raw)
    blur = SettingsSlider(tr("Background Blur"), _AUTO_BLUR if raw < 0 else raw, 0, 40, suffix=" px")
    blur.setToolTip(tr("Blur what is behind the box (frosted glass), seen over a background image. 0 px: no blur."))
    # right under the opacity: the two settings of the box's background, side by side
    opac = getattr(dialog, prefix + "int_slider", None)
    idx = layout.indexOf(opac) if opac is not None else -1
    if idx >= 0:
        layout.insertWidget(idx + 1, blur)
    else:
        layout.addWidget(blur)
    shadow = SettingsSlider(tr("Shadow"), dialog.addon_config.get(shadow_key, 0) or 0, 0, 100, suffix="%")
    shadow.setToolTip(tr("A soft shadow under the box: it seems to float over the background."))
    layout.addWidget(shadow)
    setattr(dialog, prefix + "blur_slider", blur)
    setattr(dialog, prefix + "shadow_slider", shadow)


def write_web_glass(dialog, conf, prefix, blur_key, shadow_key):
    blur = getattr(dialog, prefix + "blur_slider", None)
    shadow = getattr(dialog, prefix + "shadow_slider", None)
    if blur is not None:
        conf[blur_key] = blur.value()
    if shadow is not None:
        conf[shadow_key] = shadow.value()


def reset_web_glass(dialog, prefix):
    for name, v in (("blur_slider", _AUTO_BLUR), ("shadow_slider", 0)):
        s = getattr(dialog, prefix + name, None)
        if s is not None:
            s.setValue(v)
