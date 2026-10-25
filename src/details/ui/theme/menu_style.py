# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from __future__ import annotations


from . import get_theme_effective_is_dark, get_theme_palette
from ...widgets.chart_utils.theme import ThemeContext, get_context_theme_config
from ....qss import set_qss


def apply_menu_theme_style(menu, *, context: str, is_submenu: bool) -> None:
    conf = menu.property("deepdivestats_config_override")
    if not isinstance(conf, dict):
        try:
            from aqt import mw
            from ....config import ConfigManager

            conf = ConfigManager(mw).config
        except Exception:
            conf = {}

    if context != ThemeContext.DETAILS.value:
        # Pinned menus: the pinned theme (own preset, the main one, or native).
        conf = get_context_theme_config(ThemeContext.PINNED, conf)
    is_dark = get_theme_effective_is_dark(conf)
    palette = get_theme_palette(conf) or {}
    if palette:
        bg_color = palette.get("bg_surface", "#27272a" if is_dark else "#f4f4f5")
        border_color = palette.get("border_subtle", "#3f3f46" if is_dark else "#e4e4e7")
        text_color = palette.get("text_primary", "#f4f4f5" if is_dark else "#18181b")
        hover_bg = palette.get("bg_element", "#3f3f46" if is_dark else "#e4e4e7")
        border_strong = palette.get("border_strong", "#52525b" if is_dark else "#d4d4d8")
        accent = palette.get("accent", "#58a6ff" if is_dark else "#3b82f6")
    elif is_dark:
        bg_color = "#27272a"
        border_color = "#3f3f46"
        text_color = "#f4f4f5"
        hover_bg = "#3f3f46"
        border_strong = "#52525b"
        accent = "#58a6ff"
    else:
        bg_color = "#ffffff"
        border_color = "#e4e4e7"
        text_color = "#18181b"
        hover_bg = "#f4f4f5"
        border_strong = "#d4d4d8"
        accent = "#3b82f6"

    padding_left = "2px" if is_submenu else "8px"

    set_qss(menu,
        f"""
            QMenu {{
                background-color: {bg_color};
                color: {text_color};
                border: 1px solid {border_color};
                border-radius: 6px;
                padding: 4px 0px;
                font-family: "Segoe UI", sans-serif;
                font-size: 13px;
                spacing: 0px;
            }}
            QMenu::item {{
                padding: 6px 44px 6px {padding_left};
                border-radius: 4px;
                margin: 1px 4px;
            }}
            QMenu::icon {{
                left: 4px;
            }}
            QMenu::item:selected {{
                background-color: {hover_bg};
                color: {text_color};
            }}
            QMenu::indicator {{
                width: 14px;
                height: 14px;
                subcontrol-origin: padding;
                subcontrol-position: center right;
                right: 14px;
                border: 1.5px solid {border_strong};
                border-radius: 3px;
                background-color: transparent;
            }}
            QMenu::indicator:checked {{
                background-color: {accent};
                border-color: {accent};
            }}
            QMenu::indicator:checked:selected {{
                border-color: {text_color};
            }}
            QMenu::separator {{
                height: 1px;
                background: {border_color};
                margin: 4px 8px;
            }}
        """
    )
