# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from ....ui import Config
from aqt.qt import QColor
from ...common.color_utils import blend_colors
from ...chart_utils.theme import contrast_ratio
from ....logic.logger import log_swallowed

GLASS_MIN_ALPHA = 0.02
CARD_CORNER_RADIUS_PX = 14


def title_label_style(padding_left_px=0):
    return f"font-weight: 700; letter-spacing: 0.8px; padding-left: {int(padding_left_px)}px;"


def value_label_style(inline=False):
    return "font-weight: 800; margin-top: 0px;" if inline else "font-weight: 800; margin-top: 2px;"


def theme_title_color(is_dark, widget=None):
    """Stat card title colour: the active theme's secondary text (so it is
    tinted like the rest of the theme), or a neutral grey in Anki's native
    look. A colour picked in the card settings wins over both."""
    if widget is not None:
        try:
            conf = getattr(widget, "addon_config", None) or {}
            key = Config.FACECARDS_TITLE_COLOR if getattr(widget, "is_pinned", False) else Config.DASHBOARD_TITLE_COLOR
            custom = str(conf.get(key, "") or "")
            if custom and QColor(custom).isValid():
                return QColor(custom).name()
        except Exception:
            log_swallowed()
        try:
            from ...chart_utils.theme import get_theme_colors

            tc = get_theme_colors(widget)
            if tc.get("themed"):
                return tc["text_secondary"].name()
        except Exception:
            log_swallowed()
    return "#a1a1aa" if bool(is_dark) else "#71717a"


def value_contrast_reference(base_color, is_dark, glass_int):
    """Colour the stat value must stay readable on: the most tinted part of
    the card (its top-left corner), see tinted_card_surface()."""
    if is_dark:
        return QColor("#26262b")
    c = QColor(base_color)
    if not c.isValid():
        return QColor("#ffffff")
    t = min(1.0, 0.14 + max(0.0, float(glass_int)) * 0.3)
    return QColor(
        int(round(255 + (c.red() - 255) * t)),
        int(round(255 + (c.green() - 255) * t)),
        int(round(255 + (c.blue() - 255) * t)),
    )


def resolve_visual_profile(active_conf, is_pinned):
    conf = active_conf or {}
    if is_pinned:
        return {
            "show_glass": conf.get(Config.FACECARDS_SHOW_GLASS, True),
            "glass_int": conf.get(Config.FACECARDS_GLASS_INTENSITY, 5) / 100.0,
            "border_alpha_pct": conf.get(Config.FACECARDS_GLASS_BORDER, 50),
            "title_shadow": conf.get(Config.FACECARDS_TITLE_SHADOW_INTENSITY, 40) / 100.0,
            "stat_shadow": conf.get(Config.FACECARDS_STAT_SHADOW_INTENSITY, 60) / 100.0,
            "hover_effect": conf.get(Config.FACECARDS_HOVER_EFFECT, True),
        }
    return {
        "show_glass": conf.get(Config.DASHBOARD_SHOW_GLASS, True),
        "glass_int": conf.get(Config.DASHBOARD_GLASS_INTENSITY, 5) / 100.0,
        "border_alpha_pct": conf.get(Config.DASHBOARD_GLASS_BORDER, 50),
        "title_shadow": conf.get(Config.DASHBOARD_TITLE_SHADOW_INTENSITY, 0) / 100.0,
        "stat_shadow": conf.get(Config.DASHBOARD_STAT_SHADOW_INTENSITY, 0) / 100.0,
        "hover_effect": conf.get(Config.DASHBOARD_HOVER_EFFECT, True),
    }


def resolve_card_background(base_color, *, show_glass, glass_int):
    rgba_col = QColor(base_color)
    if not show_glass:
        return "transparent"
    alpha_base = max(GLASS_MIN_ALPHA, float(glass_int))
    rgb = f"{rgba_col.red()}, {rgba_col.green()}, {rgba_col.blue()}"
    # Diagonal tint: a touch stronger at the top-left corner, fading out.
    a_hi = min(1.0, alpha_base * 2.0 + 0.02)
    a_lo = max(0.0, alpha_base * 0.6)
    return (
        "qlineargradient(x1:0, y1:0, x2:1, y2:1, "
        f"stop:0 rgba({rgb}, {a_hi:.3f}), stop:1 rgba({rgb}, {a_lo:.3f}))"
    )


def card_layout_margins(show_glass):
    if show_glass:
        return (12, 6, 12, 6)
    return (0, 0, 0, 0)


def tinted_card_surface(base_color, is_dark, glass_int, border_alpha_pct, theme_bg=None):
    """Stat card surface in the stat's own color.

    A soft glow from the top-left corner and a hairline border in that color.
    glass_int (0-1): up to about 0.2 a translucent tint, above it the card fills in
    (dark mode: theme card color tinted with the stat color) up to opaque at 1.0.
    border_alpha_pct (0-100): hairline opacity.
    Returns (background, border_color) for the stylesheet.
    """
    from ...common.surface import opaque_card_color

    c = QColor(base_color)
    if not c.isValid():
        c = QColor("#8ab4f8")
    k = max(0.0, min(1.0, float(glass_int)))
    b = max(0.0, min(1.0, float(border_alpha_pct) / 100.0))

    def rgba(col, a):
        return f"rgba({col.red()}, {col.green()}, {col.blue()}, {max(0.0, min(1.0, a)):.3f})"

    def mix(a, z, t):
        return QColor(
            int(round(a.red() + (z.red() - a.red()) * t)),
            int(round(a.green() + (z.green() - a.green()) * t)),
            int(round(a.blue() + (z.blue() - a.blue()) * t)),
        )

    if is_dark:
        k0 = 0.2
        if k <= k0:
            a = 0.10 + k * 0.6
            hi_col, hi_a = c, a * 1.6
            mid_col, mid_a = c, a * 0.55
            lo_col, lo_a = c, a * 0.3
        else:
            t = (k - k0) / (1.0 - k0)
            fill = t ** 1.4
            u = min(1.0, t * 8.0)  # quickly from pure tint to the opaque card color
            a0 = 0.10 + k0 * 0.6
            card = mix(opaque_card_color(theme_bg), c, 0.10)
            hi_col, hi_a = mix(c, mix(card, c, 0.35), u), a0 * 1.6 + (1.0 - a0 * 1.6) * fill
            mid_col, mid_a = mix(c, mix(card, c, 0.15), u), a0 * 0.55 + (1.0 - a0 * 0.55) * fill
            lo_col, lo_a = mix(c, card, u), a0 * 0.3 + (1.0 - a0 * 0.3) * fill
    else:
        white = QColor("#ffffff")
        hi_col, hi_a = mix(white, c, 0.14 + k * 0.3), 1.0
        mid_col, mid_a = mix(white, c, 0.07 + k * 0.15), 1.0
        lo_col, lo_a = mix(white, c, 0.04 + k * 0.1), 1.0

    bg = (
        "qradialgradient(cx:0, cy:0, radius:1.25, fx:0, fy:0, "
        f"stop:0 {rgba(hi_col, hi_a)}, stop:0.55 {rgba(mid_col, mid_a)}, stop:1 {rgba(lo_col, lo_a)})"
    )
    border = rgba(c, 0.12 + 0.88 * (b ** 1.5))
    return bg, border


# Hover boost for the stat cards' colored glow: the border slider is linear
# (100% = full glow) and hover divides by this, so the default 30% shows a full
# glow on hover.
DASHBOARD_GLOW_SCALE = 0.3


def card_frame_stylesheet(bg_card, border="none"):
    return f"""
            #StatCard, #pinned_widget_card {{
                background: {bg_card};
                border: {border};
                border-radius: {CARD_CORNER_RADIUS_PX}px;
            }}
        """


def resolve_adaptive_text_colors(base_color, title_color, *, is_dark, show_glass, glass_int):
    """Return (value_color_hex, title_color_hex) with readability safeguards."""
    value_q = QColor(base_color)
    title_q = QColor(title_color)
    # The card background is a tint of the base color, so the value starts at contrast 1 and is
    # pushed toward the target color whenever glass is strong.
    bg_q = QColor(base_color)

    if not value_q.isValid():
        value_q = QColor("#8ab4f8")
    if not title_q.isValid():
        title_q = QColor("#a1a1aa" if is_dark else "#71717a")
    if not bg_q.isValid():
        bg_q = QColor("#27272a" if is_dark else "#ffffff")

    if show_glass and glass_int >= 0.45:
        target = QColor("#ffffff" if is_dark else "#111111")
        force = min(0.85, max(0.25, (glass_int - 0.45) / 0.55))

        if contrast_ratio(value_q, bg_q) < 2.8:
            value_q = blend_colors(value_q, target, force)
        if contrast_ratio(title_q, bg_q) < 3.2:
            title_q = blend_colors(title_q, target, max(force, 0.5))

        if glass_int >= 0.9:
            hard = QColor("#ffffff" if is_dark else "#000000")
            value_q = hard
            title_q = hard
        else:
            for _ in range(4):
                if contrast_ratio(value_q, bg_q) >= 3.6:
                    break
                value_q = blend_colors(value_q, target, 0.35)
            for _ in range(4):
                if contrast_ratio(title_q, bg_q) >= 4.0:
                    break
                title_q = blend_colors(title_q, target, 0.35)

    return value_q.name(), title_q.name()

