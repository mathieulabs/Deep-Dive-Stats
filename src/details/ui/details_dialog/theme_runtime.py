# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from .. import Config
from ...widgets.stats_cards import (
    get_stat_card_default_title,
    resolve_effective_stat_card_config,
)
from ...logic.refresh import request_details_runtime_refresh
from ...widgets.pinned.main_menu.manager import MainMenuWidgetManager
from ..theme.icons import get_svg_icon
from ..theme import apply_styles, get_theme_palette
from ...widgets.chart_utils.theme import get_theme_colors, resolve_theme_runtime_state, ThemeContext
from ....qss import set_qss
from ...logic.logger import log_swallowed


def refresh_styles(dialog):
    """Apply styles and propagate runtime theme refreshes."""
    apply_styles(dialog)
    refresh_ui_icons(dialog)
    request_details_runtime_refresh(
        dialog,
        reason="dialog.refresh_styles",
        update_dashboard=True,
    )
    try:
        mgr = MainMenuWidgetManager.instance()
        if mgr:
            mgr.update_styles(config_manager=dialog.addon_config)
    except Exception:
        log_swallowed()
    try:
        ddm = getattr(dialog, "deep_dive_manager", None)
        if (
            ddm
            and hasattr(dialog, "expanded_container")
            and dialog.expanded_container.isVisible()
            and getattr(ddm, "last_row_data", None) is not None
        ):
            ddm._init_theme_vars()
            ddm._populate_dashboard(is_warmup=False)
    except Exception:
        log_swallowed()
    try:
        ddm = getattr(dialog, "deep_dive_manager", None)
        if ddm:
            ddm.apply_deep_dive_theme(dialog)
    except Exception:
        log_swallowed()
    try:
        dialog._repopulate_current_table()
    except Exception:
        log_swallowed()


def refresh_ui_icons(dialog):
    """Refresh icons with the current theme palette."""
    conf = dialog.addon_config.config
    runtime = resolve_theme_runtime_state(conf, ThemeContext.DETAILS)
    is_dark = bool(runtime.get("is_dark", bool(get_theme_colors(dialog).get("is_dark"))))
    palette = get_theme_palette(conf, is_dark=is_dark) or {}
    icon_col = palette.get("text_secondary", "#a1a1aa" if is_dark else "#71717a")

    if hasattr(dialog, "search_clear_btn"):
        dialog.search_clear_btn.setIcon(get_svg_icon("x", color=icon_col, size=14))
    if hasattr(dialog, "view_toggle_btn"):
        is_deck_view = dialog.view_mode != "time"
        dialog.view_toggle_btn.setIcon(get_svg_icon("activity" if not is_deck_view else "calendar", color=icon_col))
    if hasattr(dialog, "visual_toggle"):
        dialog.visual_toggle.setIcon(get_svg_icon("bar-chart-2", color=icon_col))
    if hasattr(dialog, "settings_btn"):
        dialog.settings_btn.setIcon(get_svg_icon("settings", color=icon_col))
    if hasattr(dialog, "deck_opts_btn"):
        dialog.deck_opts_btn.setIcon(get_svg_icon("palette", color=icon_col))
    if hasattr(dialog, "support_btn"):
        dialog.support_btn.setIcon(get_svg_icon("heart", color=icon_col, size=16))
    if hasattr(dialog, "rate_btn"):
        dialog.rate_btn.setIcon(get_svg_icon("star", color=icon_col, size=16))
    if hasattr(dialog, "github_btn"):
        dialog.github_btn.setIcon(get_svg_icon("github", color=icon_col, size=16))
    if hasattr(dialog, "export_btn"):
        dialog.export_btn.setIcon(get_svg_icon("save", color=icon_col))
    if hasattr(dialog, "trend_toggle"):
        dialog.trend_toggle.setIcon(get_svg_icon("trending-up", color=icon_col))
    if hasattr(dialog, "overflow_btn"):
        dialog.overflow_btn.setIcon(get_svg_icon("chevron-down", color=icon_col))
    if hasattr(dialog, "grid_view_btn"):
        dialog.grid_view_btn.setIcon(get_svg_icon("grid", color=icon_col, size=18))
    if hasattr(dialog, "span_select_btn"):
        dialog.span_select_btn.setIcon(get_svg_icon("calendar", color=icon_col, size=16))
    if hasattr(dialog, "deck_select_btn"):
        dialog.deck_select_btn.setIcon(get_svg_icon("layers", color=icon_col, size=16))
    if hasattr(dialog, "expanded_close_btn"):
        dialog.expanded_close_btn.setIcon(get_svg_icon("x", color=icon_col, size=16))

    if hasattr(dialog, "layout_btns"):
        border_clr = palette.get("border_subtle", "rgba(255,255,255,0.1)" if is_dark else "rgba(0,0,0,0.1)")
        accent = palette.get("accent", "#3b82f6")
        try:
            h = accent.lstrip("#")
            ar, ag, ab = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        except Exception:
            ar, ag, ab = 59, 130, 246
        checked_bg = f"rgba({ar},{ag},{ab},0.2)" if is_dark else f"rgba({ar},{ag},{ab},0.12)"
        hover_bg = f"rgba({ar},{ag},{ab},0.1)"
        pressed_bg = f"rgba({ar},{ag},{ab},0.15)"
        for i, btn in enumerate(dialog.layout_btns):
            icon_name = btn.property("icon_name")
            if icon_name:
                btn.setIcon(get_svg_icon(str(icon_name), color=icon_col, size=16))
            style = f"""
                QPushButton {{
                    background: transparent;
                    border: 1px solid transparent;
                    border-radius: 0px;
                    padding: 0px;
                }}
                QPushButton:hover {{
                    background: {hover_bg};
                    border: 1px solid transparent;
                }}
                QPushButton:checked {{
                    background-color: {checked_bg};
                    border: 1px solid {accent};
                }}
                QPushButton:checked:hover {{
                    background-color: {checked_bg};
                    border: 1px solid {accent};
                }}
                QPushButton:pressed {{
                    background: {pressed_bg};
                    border: 1px solid transparent;
                }}
            """
            if i == 0:
                style += "QPushButton { border-top-left-radius: 7px; border-bottom-left-radius: 7px; }"
            elif i == 1:
                style += f"QPushButton {{ border-left: 1px solid {border_clr}; border-right: 1px solid {border_clr}; }}"
            else:
                style += "QPushButton { border-top-right-radius: 7px; border-bottom-right-radius: 7px; }"
            set_qss(btn, style)

    if hasattr(dialog, "layout_toggle_container"):
        container_border = palette.get("border_strong", "#52525b" if is_dark else "#d4d4d8")
        set_qss(dialog.layout_toggle_container, 
            f"QFrame#layout_toggle_container {{ background: transparent; border: 1px solid {container_border}; border-radius: 8px; }}"
        )

    if hasattr(dialog, "expanded_scroll"):
        try:
            from ..theme import hex_to_rgba

            handle = hex_to_rgba(palette.get("text_secondary", "#a1a1aa" if is_dark else "#71717a"), 0.26 if is_dark else 0.22)
            handle_hover = hex_to_rgba(palette.get("accent", "#3b82f6"), 0.42 if is_dark else 0.30)
            handle_pressed = hex_to_rgba(palette.get("accent_hover", palette.get("accent", "#3b82f6")), 0.58 if is_dark else 0.40)
            handle_border = hex_to_rgba(palette.get("border_strong", "#52525b" if is_dark else "#d4d4d8"), 0.75)
        except Exception:
            handle = "rgba(200, 200, 200, 0.25)" if is_dark else "rgba(90, 90, 90, 0.2)"
            handle_hover = "rgba(200, 200, 200, 0.45)" if is_dark else "rgba(90, 90, 90, 0.4)"
            handle_pressed = "rgba(200, 200, 200, 0.6)" if is_dark else "rgba(90, 90, 90, 0.5)"
            handle_border = "rgba(127, 127, 127, 0.55)"
        set_qss(dialog.expanded_scroll, 
            f"""
            QScrollArea#expanded_scroll {{ background: transparent; }}
            QScrollBar:vertical {{ width: 10px; background: transparent; margin: 0; }}
            QScrollBar::handle:vertical {{
                background: {handle};
                border: 1px solid {handle_border};
                min-height: 30px;
                border-radius: 2px;
                margin: 0px 4px 0px 4px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {handle_hover};
                border-radius: 4px;
                margin: 0px 2px 0px 2px;
            }}
            QScrollBar::handle:vertical:pressed {{
                background: {handle_pressed};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
        """
        )


def update_dashboard_visibility(dialog):
    conf = dialog.addon_config.config
    if hasattr(dialog, "stats_container") and dialog.stats_container:
        scale = conf.get(Config.DASHBOARD_SCALE, 100)
        dialog.stats_container.set_scale(scale)
        custom_labels = conf.get(Config.DASH_STAT_LABELS, {})
        if not isinstance(custom_labels, dict):
            custom_labels = {}
        custom_styles = conf.get(Config.DASH_STAT_STYLES, {})
        if not isinstance(custom_styles, dict):
            custom_styles = {}
        default_labels = {
            str(c.config_key): get_stat_card_default_title(c.config_key)
            for c in dialog.stats_container.cards
            if getattr(c, "config_key", None)
        }

        for card in dialog.stats_container.cards:
            card_conf = conf
            style_entry = custom_styles.get(str(getattr(card, "config_key", "")))
            if isinstance(style_entry, dict):
                card_conf = resolve_effective_stat_card_config(conf, style_entry)
            if hasattr(card, "refresh_theme"):
                card.refresh_theme(conf=card_conf)
            if hasattr(card, "set_centered"):
                card.set_centered(False)
            if hasattr(card, "config_key"):
                ck = str(card.config_key)
                card_title = custom_labels.get(ck) or default_labels.get(ck, card.display_name)
                if card_title and card_title != getattr(card, "display_name", ""):
                    card.update_val(card.value_lbl.text(), title=card_title, refresh=False)

            is_dd = hasattr(dialog, "expanded_container") and dialog.expanded_container.isVisible()
            card.set_title_visible(True)
            if is_dd:
                if hasattr(card, "config_key"):
                    dd_key = card.config_key.replace("dash_show_", "deep_dive_show_")
                    card.setVisible(conf.get(dd_key, True))
            else:
                if hasattr(card, "config_key"):
                    card.setVisible(conf.get(card.config_key, True))

    if hasattr(dialog, "stats_container") and dialog.stats_container:
        dialog.stats_container.resizeEvent(None)

