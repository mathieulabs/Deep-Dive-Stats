# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""The add-on's theme for a web page: CSS variables for the page, colors for the charts."""

import sys


def _rgba(color):
    return f"rgba({color.red()},{color.green()},{color.blue()},{color.alpha() / 255.0:.3f})"


def _mix_hex(a, b, k):
    a, b = a.lstrip("#"), b.lstrip("#")
    return "#" + "".join("%02x" % int(round(int(a[i:i + 2], 16) + (int(b[i:i + 2], 16) - int(a[i:i + 2], 16)) * k)) for i in (0, 2, 4))


def _hover_css(t, is_dark):
    c = t.get("bg_hover")
    try:
        if hasattr(c, "red"):
            return _rgba(c)
        if c:
            return "rgba(%d,%d,%d,%.3f)" % (c[0], c[1], c[2], c[3] / 255.0)
    except Exception:
        pass
    return "rgba(255,255,255,0.1)" if is_dark else "rgba(0,0,0,0.05)"


def _menu_vars(cfg, is_dark, context="details"):
    """Colors of the add-on's menus (StyledMenu), so the page's menus look the same. Pinned: the pinned widgets'
    theme (it can be one of their own: the lists and tooltips of their settings had the Deep Dive's colors)."""
    from ..details.ui.theme import get_theme_effective_is_dark, get_theme_palette

    try:
        if context == "pinned":
            from ..details.widgets.chart_utils.theme import ThemeContext, get_context_theme_config

            dark = bool(is_dark)
            p = get_theme_palette(get_context_theme_config(ThemeContext.PINNED, conf=cfg)) or {}
        else:
            dark = bool(get_theme_effective_is_dark(cfg))
            p = get_theme_palette(cfg) or {}
    except Exception:
        dark, p = is_dark, {}
    if p:
        return {
            "menu-bg": p.get("bg_surface", "#27272a" if dark else "#f4f4f5"),
            "menu-border": p.get("border_subtle", "#3f3f46" if dark else "#e4e4e7"),
            "menu-text": p.get("text_primary", "#f4f4f5" if dark else "#18181b"),
            "menu-hover": p.get("bg_element", "#3f3f46" if dark else "#e4e4e7"),
            "menu-strong": p.get("border_strong", "#52525b" if dark else "#d4d4d8"),
            "menu-accent": p.get("accent", "#58a6ff" if dark else "#3b82f6"),
        }
    if dark:
        return {"menu-bg": "#27272a", "menu-border": "#3f3f46", "menu-text": "#f4f4f5", "menu-hover": "#3f3f46", "menu-strong": "#52525b", "menu-accent": "#58a6ff"}
    return {"menu-bg": "#ffffff", "menu-border": "#e4e4e7", "menu-text": "#18181b", "menu-hover": "#f4f4f5", "menu-strong": "#d4d4d8", "menu-accent": "#3b82f6"}


def _soft_button_vars(cfg, is_dark, context="details"):
    """The window's buttons as design_overrides.get_design_overrides draws them (soft pill UI): idle = muted 7 %,
    border = muted 36 %, hover = accent 14 % with an accent 70 % border."""
    try:
        from ..details.ui.theme.design_overrides import _colors
        from ..details.logic.theme.palette import get_theme_palette

        if context == "pinned":  # the pinned widgets' theme (see _menu_vars)
            from ..details.widgets.chart_utils.theme import ThemeContext, get_context_theme_config

            cfg = get_context_theme_config(ThemeContext.PINNED, conf=cfg)
        c = _colors(is_dark, get_theme_palette(cfg))
    except Exception:
        c = {"muted": "#a1a1aa" if is_dark else "#71717a", "accent": "#58a6ff" if is_dark else "#3b82f6"}

    def rgba(h, k):
        h = str(h).lstrip("#")
        return "rgba(%d, %d, %d, %.3f)" % (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), k)

    return {"btn-border": rgba(c["muted"], 0.36), "btn-idle": rgba(c["muted"], 0.07),
            "btn-hover": rgba(c["accent"], 0.14), "btn-hover-border": rgba(c["accent"], 0.7),
            "btn-press": rgba(c["accent"], 0.30), "btn-accent": c["accent"]}


def _custom_surface_hex(context="details", cfg=None):
    """If the user customized 'Surface / Cards' (bg_surface) in Theme Colors (or saved a custom preset with it),
    return that hex so chart boxes use it directly instead of the default white veil / Anki panel fallback."""
    try:
        from ..config import addon_config as _addon_config
        from ..const import Config
        from ..details.widgets.chart_utils.theme import ThemeContext, resolve_theme_runtime_state

        c = cfg if isinstance(cfg, dict) else _addon_config().config
        if str(context) == "pinned":
            st = resolve_theme_runtime_state(c, ThemeContext.PINNED)
            key = Config.PINNED_THEME_CUSTOM_COLORS if st.get("use_separate_theme") else Config.THEME_CUSTOM_COLORS
        else:
            key = Config.THEME_CUSTOM_COLORS
        custom = c.get(key)
        val = custom.get("bg_surface") if isinstance(custom, dict) else None
        return str(val) if val else None
    except Exception:
        return None


def box_look(intensity, border_pct, hover_border=True, context="pinned", cfg=None):
    """The box behind a chart, as widget_factory/styler.apply_style draws it with the glass on (pinned charts,
    texts, heatmap, and the Deep Dive cards through Deep_Dive_Grid_Style): {"bg", "edge", "border", "hover"}."""
    from aqt.qt import QColor

    from ..const.glass_scale import box_glass_k
    from ..details.widgets.common.surface import dark_surface_rgba
    from ..details.widgets.pinned.widget_factory.utils import _theme_vars

    tv = _theme_vars(context)
    k = box_glass_k(intensity)
    # apply_style: the border setting is raised for the chart boxes (readable on every theme)
    b = min(100, int(round((float(border_pct) * 1.5) + 12))) / 100.0

    def edge_of(base_at_half, slope):
        if b <= 0.5:
            return base_at_half - slope * (0.5 - b)
        return base_at_half + (1.0 - base_at_half) * (((b - 0.5) / 0.5) ** 1.6)

    custom_surf = _custom_surface_hex(context, cfg)
    if tv["is_dark"]:
        if custom_surf and QColor(custom_surf).isValid():
            col = QColor(custom_surf)
            surface = f"rgba({col.red()}, {col.green()}, {col.blue()}, {min(1.0, 0.85 + k * 0.15):.3f})"
        else:
            surface = dark_surface_rgba(k, tv.get("surface_hex") or tv.get("bg_hex"), lambda x: 0.02 + x * 0.12)
        rgb, edge = "255, 255, 255", edge_of(0.07, 0.08)
    else:
        col = QColor(custom_surf or tv.get("surface_hex") or "#ffffff")
        if not col.isValid():
            col = QColor("#ffffff")
        surface = f"rgba({col.red()}, {col.green()}, {col.blue()}, {min(1.0, 0.8 + k):.3f})"
        rgb, edge = "0, 0, 0", edge_of(0.08, 0.08)
    edge_css = f"rgba({rgb}, {edge:.3f})"
    border = f"1px solid {edge_css}"
    hover = f"1px solid rgba({rgb}, {min(1.0, edge + 0.10):.3f})" if hover_border else border
    return {"bg": surface, "edge": edge_css, "border": border, "hover": hover}


def pinned_box(opacity, border_pct, hover_border=True):
    """The box behind a web pinned widget: the theme's card color (dark: the theme surface or background one step
    lighter; light: the theme surface) at opacity % as it is (0 see-through, 100 solid), never a white veil (over a
    bright background image a white veil under light text was unreadable); the border as box_look. Blurring what is
    behind is the other setting (pinned.js)."""
    from aqt.qt import QColor

    from ..details.widgets.common.surface import opaque_card_color
    from ..details.widgets.pinned.widget_factory.utils import _theme_vars

    look = box_look(50, border_pct, hover_border, "pinned")
    tv = _theme_vars("pinned")
    a = max(0.0, min(1.0, float(opacity or 0) / 100.0))
    custom_surf = _custom_surface_hex("pinned")
    if custom_surf and QColor(custom_surf).isValid():
        col = QColor(custom_surf)
    elif tv["is_dark"]:
        s_hex = tv.get("surface_hex")
        col = QColor(s_hex) if (s_hex and QColor(s_hex).isValid()) else opaque_card_color(tv.get("bg_hex"))
    else:
        col = QColor(tv.get("surface_hex") or "#ffffff")
        if not col.isValid():
            col = QColor("#ffffff")
    look["bg"] = f"rgba({col.red()}, {col.green()}, {col.blue()}, {a:.3f})"
    # Anki's own theme (the native preset, when bg_surface is not customized): the box is Anki's raised panel colour,
    # the one of its deck list (--canvas-elevated), at that opacity.
    if not custom_surf:
        try:
            from ..details.widgets.chart_utils.theme import ThemeContext, resolve_theme_runtime_state
            from ..config import addon_config as _addon_config
            from ..const.theme.palettes import ThemePalettes

            st = resolve_theme_runtime_state(_addon_config().config, ThemeContext.PINNED)
            if st.get("preset") == ThemePalettes.NATIVE:
                look["anki_bg"] = round(a * 100, 1)
                look["anki_fallback"] = col.name()
        except Exception:
            pass
    return look


def _grid_box_css(cfg, context):
    """The Deep Dive cards' box from Settings (Deep_Dive_Grid_Style: show, intensity, border); the defaults
    give a 4 % veil and a 65 % border."""
    from ..const import Config

    grid = dict((Config.DEFAULT_CONFIG.get(Config.DEEP_DIVE_GRID_STYLE) or {}))
    grid.update(cfg.get(Config.DEEP_DIVE_GRID_STYLE) or {})
    if not grid.get(Config.PINNED_GLASS, True):
        return {"card": "transparent", "card-border": "transparent"}
    look = box_look(grid.get(Config.PINNED_GLASS_INTENSITY, 4), grid.get(Config.PINNED_GLASS_BORDER, 50), True, context, cfg=cfg)
    return {"card": look["bg"], "card-border": look["edge"]}


def build_theme(context="details", conf=None):
    from ..const import Config
    from ..const.theme.color_resolver import get_color
    from ..details.widgets.chart_utils.theme import ThemeContext, get_theme_colors
    from ..config import addon_config as _addon_config

    ctx = ThemeContext.PINNED if context == "pinned" else ThemeContext.DETAILS
    cfg = conf if conf is not None else _addon_config().config  # the settings dialog's live preview passes its own
    if conf is None:
        # the theme manager follows the profile's config: after a profile switch it could still hold the previous
        # profile's mode (native dark) while the colours came from the new one's preset (Modern Light): dark cards
        # and backdrop with dark text. Synced here from the config the page is drawn with (a no-op when it is).
        try:
            from ..details.widgets.chart_utils.theme import sync_theme_manager_and_notify, theme_already_synced

            if not theme_already_synced(cfg):
                sync_theme_manager_and_notify(cfg, source="web_theme")
                from .trace import trace

                trace(f"THEME synced from the config before drawing ({context}): preset={cfg.get(Config.THEME_PRESET)}")
        except Exception:
            pass
    t = get_theme_colors(ctx)
    is_dark = bool(t["is_dark"])
    try:
        from ..details.ui.theme.theme_mode import get_theme_effective_is_dark
        from ..details.widgets.chart_utils.theme import _THEME_MANAGER
        from .trace import trace

        trace(f"THEME {context}: dark={is_dark} text={t['text_primary'].name()} bg={t['bg'].name()} "
              f"backdrop dark={bool(get_theme_effective_is_dark(cfg))} manager mode={_THEME_MANAGER._details_mode} "
              f"preset={cfg.get(Config.THEME_PRESET)} profile={getattr(__import__('aqt').mw.pm, 'name', None)}")
    except Exception:
        pass
    surface = t.get("surface")
    chart = {
        "bar": get_color(cfg, Config.COLOR_BAR, ctx),
        "heatmap": get_color(cfg, Config.HEATMAP_COLOR, ctx),
        "mature": get_color(cfg, Config.COLOR_MATURE, ctx),
        "young": get_color(cfg, Config.COLOR_YOUNG, ctx),
        "relearn": get_color(cfg, Config.COLOR_RELEARN, ctx),
        "learn": get_color(cfg, Config.COLOR_LEARN, ctx),
        "cram": get_color(cfg, Config.COLOR_CRAM, ctx),
        "retention": get_color(cfg, Config.COLOR_RETENTION, ctx),
        "future_due": get_color(cfg, Config.COLOR_FUTURE_DUE, ctx),
        "backlog": get_color(cfg, Config.COLOR_BACKLOG, ctx),
        "good": get_color(cfg, Config.COLOR_GOOD, ctx),
        "again": get_color(cfg, Config.COLOR_AGAIN, ctx),
        "new": get_color(cfg, Config.COLOR_NEW, ctx),
        "suspended": get_color(cfg, Config.COLOR_SUSPENDED, ctx),
        "buried": get_color(cfg, Config.COLOR_BURIED, ctx),
        "deleted": get_color(cfg, Config.COLOR_DELETED, ctx),
        "hard": get_color(cfg, Config.COLOR_HARD, ctx),
        "easy": get_color(cfg, Config.COLOR_EASY, ctx),
        "text": t["text"].name(),
        "gradient_low": get_color(cfg, Config.COLOR_GRADIENT_LOW, ctx),
        "gradient_high": get_color(cfg, Config.COLOR_GRADIENT_HIGH, ctx),
        "bg": t["bg"].name(),
        "total_line": t["total_line"].name(),
        # the zoom selection and other highlights: the theme accent (zoom_mixin.draw_selection_overlay)
        "accent": (t.get("accent").name() if t.get("accent") is not None else ("#58a6ff" if is_dark else "#3b82f6")),
        "grid": _rgba(t["grid"]),
        "axis_text": t["text_secondary"].name(),
        "is_dark": is_dark,
        "text_primary": t["text_primary"].name(),
        "text_secondary": t["text_secondary"].name(),
        "tooltip_bg": t["bg"].name(),
        "tooltip_border": t["border"].name(),
    }
    css = {
        "bg": t["bg"].name(),
        # Dark: the cards are a faint white veil over the window backdrop (4 % white, border 65 % white),
        # not the theme's solid surface color.
        "card": "rgba(255, 255, 255, 0.04)" if is_dark else (surface.name() if surface is not None else "#ffffff"),
        "border": t["border"].name(),
        "text": t["text_primary"].name(),
        "text-dim": t["text_secondary"].name(),
        "card-border": "rgba(255, 255, 255, 0.65)" if is_dark else _mix_hex(t["text_primary"].name(), surface.name() if surface is not None else "#ffffff", 0.14),
        "drawer": _mix_hex(t["bg"].name(), "#000000", 0.07),
        **_soft_button_vars(cfg, is_dark, context),
        # the window's accent (tabs, selected rows, active buttons, drag marks): the theme accent
        "accent": (t.get("accent").name() if t.get("accent") is not None else ("#58a6ff" if is_dark else "#3b82f6")),
        # the header pills / toggles light up in the theme accent (pill_toggles._tokens via get_theme_colors()["accent"])
        "ctl-accent": (t.get("accent").name() if t.get("accent") is not None else ("#58a6ff" if is_dark else "#3b82f6")),
        **_menu_vars(cfg, is_dark, context),
        "hover": _hover_css(t, is_dark),
    }
    if context != "pinned":
        try:
            css.update(_grid_box_css(cfg, "details"))
        except Exception:
            pass
        css.update(_rate_vars(cfg))
    stat = stat_style(cfg, t, is_dark, pinned=(context == "pinned"))
    axis_anim = "count" if cfg.get(Config.CHART_AXIS_ANIM) == "count" else "slide"
    num_anim = "roll" if cfg.get(Config.STAT_NUM_ANIM) == "roll" else "count"
    im = cfg.get(Config.INTERACTION_MODE, "auto")
    interaction_mode = im if im in ("auto", "desktop", "touch") else "auto"
    is_mobile = sys.platform in ("android", "ios")
    return {"is_dark": is_dark, "css": css, "chart": chart, "stat": stat, "backdrop": backdrop_spec(cfg), "axis_anim": axis_anim,
            "num_anim": num_anim, "interaction_mode": interaction_mode, "is_mobile": is_mobile}


def _rate_vars(cfg):
    """The colors of the rating banner (details_dialog/rate_prompt._build_banner): the theme's surface, border, texts
    and accent, white or dark text on the accent."""
    try:
        from aqt.qt import QColor

        from ..details.ui.theme import get_theme_effective_is_dark, get_theme_palette
        from ..details.widgets.chart_utils.theme import relative_luminance

        dark = get_theme_effective_is_dark(cfg)
        pal = get_theme_palette(cfg, dark) or {}
        accent = pal.get("accent", "#58a6ff")
        return {
            "rate-surface": pal.get("bg_surface", "#3a3a3a"), "rate-border": pal.get("border_strong", "#555555"),
            "rate-text": pal.get("text_primary", "#ffffff"), "rate-muted": pal.get("text_secondary", "#d7d7d7"),
            "rate-accent": accent, "rate-accent-hover": pal.get("accent_hover", accent),
            "rate-on-accent": "#18181b" if relative_luminance(QColor(accent)) > 0.5 else "#ffffff",
            "rate-hover": "rgba(255,255,255,0.08)" if dark else "rgba(0,0,0,0.06)",
        }
    except Exception:
        return {}


def stat_style(cfg, t=None, is_dark=None, pinned=False):
    """Stat cards (Dashboard_* settings): the web page computes the tint like stats_cards/ui/style.py. Also used for
    a card with its own style (Settings on the card: Dashboard_* keys of its entry over the global ones)."""
    from ..const import Config
    from ..details.widgets.chart_utils.theme import ThemeContext, get_theme_colors

    if t is None:
        t = get_theme_colors(ThemeContext.DETAILS)
        is_dark = bool(t["is_dark"])
    surface = t.get("surface")
    # the pinned stat cards have their own settings (Facecards_*), the Deep Dive / dashboard ones (Dashboard_*)
    K = {k: getattr(Config, ("FACECARDS_" if pinned else "DASHBOARD_") + k) for k in (
        "TITLE_COLOR", "SHOW_GLASS", "GLASS_INTENSITY", "GLASS_BORDER", "SCALE", "TITLE_SIZE",
        "TITLE_SHADOW_INTENSITY", "STAT_SHADOW_INTENSITY", "HOVER_EFFECT", "SHOW_ICONS", "ICON_POS")}
    D = Config.DEFAULT_CONFIG
    title_color = str(cfg.get(K["TITLE_COLOR"], "") or "")
    if not title_color:
        title_color = t["text_secondary"].name() if t.get("themed") else ("#a1a1aa" if is_dark else "#71717a")
    raw_ico = cfg.get(K["SHOW_ICONS"], D.get(K["SHOW_ICONS"], "inline"))
    ico_mode = "off" if raw_ico in (False, "", "off", None) else ("watermark" if raw_ico == "watermark" else "inline")
    raw_pos = cfg.get(K["ICON_POS"], D.get(K["ICON_POS"], "tl"))
    ico_pos = raw_pos if raw_pos in ("tl", "tr", "bl", "br") else "tl"
    stat = {
        "glass": bool(cfg.get(K["SHOW_GLASS"], True)),
        "glass_int": float(cfg.get(K["GLASS_INTENSITY"], D.get(K["GLASS_INTENSITY"], 5))) / 100.0,
        "border_pct": float(cfg.get(K["GLASS_BORDER"], D.get(K["GLASS_BORDER"], 50))),
        "scale": float(cfg.get(K["SCALE"], 100)),
        "title_size": float(cfg.get(K["TITLE_SIZE"], D.get(K["TITLE_SIZE"], 100))),
        "title_color": title_color,
        "surface": surface.name() if surface is not None else "#ffffff",
        "bg": t["bg"].name(),
        "title_shadow": float(cfg.get(K["TITLE_SHADOW_INTENSITY"], D.get(K["TITLE_SHADOW_INTENSITY"], 0)) or 0) / 100.0,
        "stat_shadow": float(cfg.get(K["STAT_SHADOW_INTENSITY"], D.get(K["STAT_SHADOW_INTENSITY"], 0)) or 0) / 100.0,
        "hover": bool(cfg.get(K["HOVER_EFFECT"], True)),
        "show_icons": ico_mode != "off",
        "icon_mode": ico_mode,
        "icon_pos": ico_pos,
    }
    return stat


def backdrop_spec(conf=None):
    """Window backdrop (details/ui/theme/backdrop.py render_backdrop) as numbers for CSS."""
    from ..details.ui.theme.backdrop import get_backdrop_settings
    from ..details.ui.theme.design_overrides import _colors, _mix
    from ..details.logic.theme.palette import get_theme_palette
    from ..details.ui.theme.theme_mode import get_theme_effective_is_dark
    from ..config import addon_config as _addon_config

    if conf is None:
        conf = _addon_config().config
    dark = bool(get_theme_effective_is_dark(conf))
    c = _colors(dark, get_theme_palette(conf))
    s = get_backdrop_settings(conf)
    bg, accent = c["bg"], c["accent"]
    c1 = s.get("color1") or accent
    c2 = s.get("color2") or accent
    k_tone, k_glow, k_glow2, k_depth = s["tone"] / 50.0, s["glow"] / 50.0, s["glow2"] / 50.0, s["depth"] / 50.0
    deep = _mix(bg, "#000000", min(0.8, (0.42 if dark else 0.035) * k_tone))
    base = _mix(deep, c1, 0.03 if dark else 0.02)
    return {
        "enabled": bool(s["enabled"]),
        "flat": bg,
        "top": _mix(base, c1, min(0.4, 0.045 * k_glow)),
        "mid": base,
        "bottom": _mix(base, "#000000", min(0.6, (0.16 if dark else 0.04) * k_depth)),
        "glow1": c1, "glow1_a": (0.20 if dark else 0.10) * k_glow,
        "glow2": c2, "glow2_a": (0.10 if dark else 0.06) * k_glow2,
        "vignette_a": min(1.0, (0.20 if dark else 0.04) * k_depth),
        "grain": s["grain"] / 100.0, "dark": dark,
    }
