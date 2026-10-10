# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QPainter

from ...chart_utils import is_night_mode
from .label_fx import apply_text_shadow
from .style import (
    resolve_visual_profile,
    resolve_card_background,
    card_layout_margins,
    card_frame_stylesheet,
    tinted_card_surface,
    DASHBOARD_GLOW_SCALE,
)
from .....qss import set_qss


def paint_hover_effect(widget):
    if (
        not getattr(widget, "hover_effect_enabled", True)
        or float(getattr(widget, "_max_effect_opacity", 0.0)) <= 0.001
    ):
        return
    max_opacity = widget._max_effect_opacity
    if getattr(widget, "_max_effect_opacity", 0.0) > 0 and getattr(widget._effect, "_is_hovered", False):
        # Hover brings the locked glow up (to full at the default ~30%).
        max_opacity = min(1.0, max_opacity / DASHBOARD_GLOW_SCALE)
    widget._effect.paint(
        QPainter(widget),
        widget.rect(),
        widget.base_color,
        max_opacity=max_opacity,
    )


def apply_visual_style(widget):
    conf = widget.addon_config
    is_dark = is_night_mode(widget)

    profile = resolve_visual_profile(conf, widget.is_pinned)
    show_glass = bool(profile["show_glass"])
    glass_int = float(profile["glass_int"])
    border_alpha_pct = float(profile["border_alpha_pct"])
    title_shad = float(profile["title_shadow"])
    stat_shad = float(profile["stat_shadow"])
    widget.hover_effect_enabled = bool(profile["hover_effect"])

    widget._max_effect_opacity = (border_alpha_pct / 100.0) if show_glass else 0.0

    border = "none"
    if show_glass:
        # Card in the stat's own color: corner glow + matching hairline.
        try:
            from ...chart_utils import get_theme_colors

            theme_bg = get_theme_colors(widget).get("bg")
        except Exception:
            theme_bg = None
        # No stylesheet border: the colored glow (toggled by clicking the
        # card, strength = border slider) is the card's border.
        bg_card, _border_col = tinted_card_surface(widget.base_color, is_dark, glass_int, border_alpha_pct, theme_bg)
    else:
        bg_card = resolve_card_background(
            widget.base_color,
            show_glass=show_glass,
            glass_int=glass_int,
        )
    style_key = (bg_card, border, widget.is_pinned, is_dark, title_shad, stat_shad, show_glass)
    if getattr(widget, "_last_style_key", None) == style_key:
        return
    widget._last_style_key = style_key
    css = card_frame_stylesheet(bg_card, border)

    if hasattr(widget, "main_layout") and widget.main_layout:
        widget.main_layout.setContentsMargins(*card_layout_margins(show_glass))
    set_qss(widget, css)

    apply_text_shadow(widget, widget.title_lbl, title_shad)
    apply_text_shadow(widget, widget.value_lbl, stat_shad)
    if getattr(widget, "sub_lbl", None):
        apply_text_shadow(widget, widget.sub_lbl, title_shad * 0.5)

    widget.set_centered(bool(widget.is_pinned))
    widget.setGraphicsEffect(None)
