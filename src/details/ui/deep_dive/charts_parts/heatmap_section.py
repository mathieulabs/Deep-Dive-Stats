# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from datetime import datetime

from aqt.qt import QLabel, QPushButton, QSizePolicy, Qt

from ....logic.heatmap import step_heatmap_mode_state, switch_heatmap_mode_state
from ....logic.data.transforms.heatmap_series import build_heatmap_data
from ....animations.chart_policy import local_chart_animation_batch
from ....widgets.common import create_chart_header, create_hbox_container
from ... import Config
from .. import HeatmapWidget, get_theme_colors
from ...theme.icons import get_svg_icon
from .....qss import set_qss


def build_heatmap_section(
    manager,
    history_data,
    row_data,
    history_range,
    period_range,
    target_layout=None,
    manual_add=False,
):
    row_color = row_data.get("row_color")
    hm_default = manager.addon_config.config.get(Config.HEATMAP_COLOR, "#3b82f6")
    color_scheme = (
        row_color.name()
        if row_color and hasattr(row_color, "name") and row_color.isValid()
        else hm_default
    )

    ctx = getattr(manager, "last_history_context", {}) or {}
    heatmap_data = ctx.get("heatmap_data")

    if heatmap_data is None:
        if getattr(manager, "_is_skeleton", False):
            heatmap_data = {}
        else:
            heatmap_data, _ = build_heatmap_data(history_data)

    if not heatmap_data and not (getattr(manager, "_is_skeleton", False) or manager._show_empty_charts()):
        return None, None

    current_idx = manager.dialog.tab_widget.currentIndex()
    target_did = row_data.get("did") or (
        manager._resolve_tab_config(current_idx, period_range).get("deck_id")
        if manager.dialog.view_mode != "time"
        else None
    )

    grid_style = manager.addon_config.config.get(Config.DEEP_DIVE_GRID_STYLE, {})
    wid = "heatmap_g" if manager.grid_mode else "heatmap_l"
    local_settings = manager.addon_config.config.get(Config.DEEP_DIVE_WIDGET_SETTINGS, {}).get(wid, {})
    use_custom = local_settings.get("use_custom_style", False)

    active_style = manager.addon_config.config.copy()
    if use_custom:
        active_style.update(local_settings)
    else:
        active_style.update(grid_style)

    monday_first = active_style.get(
        Config.HEATMAP_MONDAY_FIRST,
        manager.addon_config.config.get(Config.HEATMAP_MONDAY_FIRST, False),
    )
    empty_opacity = active_style.get(
        Config.HEATMAP_EMPTY_OPACITY,
        manager.addon_config.config.get(Config.HEATMAP_EMPTY_OPACITY, 15),
    )
    filled_opacity = active_style.get(
        Config.HEATMAP_FILLED_OPACITY,
        manager.addon_config.config.get(Config.HEATMAP_FILLED_OPACITY, 100),
    )
    empty_white = active_style.get(
        Config.HEATMAP_EMPTY_WHITE,
        manager.addon_config.config.get(Config.HEATMAP_EMPTY_WHITE, False),
    )
    hide_labels = active_style.get(
        Config.HEATMAP_HIDE_LABELS,
        manager.addon_config.config.get(Config.HEATMAP_HIDE_LABELS, False),
    )
    tinted_future = active_style.get(
        Config.HEATMAP_TINTED_FUTURE,
        manager.addon_config.config.get(Config.HEATMAP_TINTED_FUTURE, False),
    )
    scale = (
        active_style.get(Config.HEATMAP_SCALE, manager.addon_config.config.get(Config.HEATMAP_SCALE, 100))
        / 100.0
    )
    color_levels = active_style.get(
        Config.HEATMAP_COLOR_LEVELS,
        manager.addon_config.config.get(Config.HEATMAP_COLOR_LEVELS, 15),
    )
    vibrance = active_style.get(
        Config.HEATMAP_VIBRANCE,
        manager.addon_config.config.get(Config.HEATMAP_VIBRANCE, 100),
    )
    rounding = active_style.get(
        Config.HEATMAP_ROUNDING,
        manager.addon_config.config.get(Config.HEATMAP_ROUNDING, 20),
    )
    intensity_curve = active_style.get(
        Config.HEATMAP_INTENSITY_CURVE,
        manager.addon_config.config.get(Config.HEATMAP_INTENSITY_CURVE, 100),
    )
    multi_hue_intensity = manager.addon_config.config.get(Config.HEATMAP_MULTI_HUE_INTENSITY, False)

    current_mode = [manager._get_dd_widget_setting("heatmap", "heatmap_mode", "year")]
    if isinstance(current_mode[0], bool) or current_mode[0] not in ["year", "365", "continuous"]:
        current_mode[0] = "year"

    now = datetime.now()
    from ..runtime.heatmap_anchor import resolve_heatmap_state

    manager.heatmap_year, manager.end_date_365, initial_end = resolve_heatmap_state(
        manager, current_mode[0], getattr(manager, "_dd_range_last_day", None), now=now
    )

    heatmap = HeatmapWidget(
        heatmap_data,
        color_scheme=color_scheme,
        end_date=initial_end,
        parent=manager.dialog,
        monday_first=monday_first,
        empty_opacity=empty_opacity,
        empty_white=empty_white,
        filled_opacity=filled_opacity,
        hide_labels=hide_labels,
        scale=scale,
        tinted_future=tinted_future,
        rounding=rounding,
        intensity_curve=intensity_curve,
        color_levels=color_levels,
        vibrance=vibrance,
        multi_hue_intensity=multi_hue_intensity,
    )
    manager.heatmap_chart = heatmap
    heatmap.set_metric(manager.addon_config.config.get(Config.HEATMAP_METRIC, "reviews"))
    heatmap.set_show_legend(
        active_style.get(
            Config.HEATMAP_SHOW_LEGEND,
            manager.addon_config.config.get(Config.HEATMAP_SHOW_LEGEND, True),
        )
    )
    heatmap.set_invert_intensity(manager.addon_config.config.get(Config.HEATMAP_INVERT_INTENSITY, False))
    heatmap.tooltip_hidden = list(manager.addon_config.config.get(Config.HEATMAP_TOOLTIP_HIDDEN, []) or [])
    heatmap.setObjectName("heatmap_widget")
    heatmap.setProperty("heatmap_deck_id", target_did)

    if manager.addon_config.config.get(Config.HEATMAP_CLICK_BROWSER, True):

        def on_click(date_str):
            did = None
            rd = getattr(manager, "last_row_data", None)
            if rd:
                did = rd.get("did")
            manager.on_heatmap_day_clicked(date_str, did)

        heatmap.day_clicked = on_click

    heatmap.setMinimumHeight(40)
    heatmap.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    nav_controls, header_lay = create_hbox_container(
        manager.dialog,
        margins=(0, 0, 0, 0),
        spacing=2,
    )

    tokens = manager._control_theme_tokens()
    t_colors = get_theme_colors(nav_controls)
    is_dark = bool(t_colors.get("is_dark"))
    text_primary = t_colors.get("text_primary", t_colors.get("text"))
    accent_col = t_colors.get("accent")
    bg_hover_col = t_colors.get("bg_hover")
    text_primary_hex = text_primary.name() if text_primary is not None else ("#f4f4f5" if is_dark else "#18181b")
    if bg_hover_col is not None:
        hover_bg = (
            f"rgba({bg_hover_col.red()},{bg_hover_col.green()},{bg_hover_col.blue()},{bg_hover_col.alpha()})"
        )
    else:
        hover_bg = "rgba(255,255,255,0.1)" if is_dark else "rgba(0,0,0,0.05)"
    active_bg = (
        f"rgba({accent_col.red()},{accent_col.green()},{accent_col.blue()},40)"
        if accent_col is not None
        else "rgba(59,130,246,40)"
    )
    btn_prev = QPushButton(parent=nav_controls)
    btn_next = QPushButton(parent=nav_controls)
    btn_prev.setIcon(get_svg_icon("chevron-left", size=14, color=tokens["text_secondary"]))
    btn_next.setIcon(get_svg_icon("chevron-right", size=14, color=tokens["text_secondary"]))

    year_lbl = QLabel(str(manager.heatmap_year), parent=nav_controls)
    year_lbl.setObjectName("heatmap_year_lbl")

    nav_style = (
        f"font-weight: 800; font-size: 10px; color: {tokens['text_secondary']}; letter-spacing: 1px;"
    )
    btn_style = f"""
            QPushButton {{
                background: transparent;
                border: none;
                font-weight: 800;
                font-size: 10px;
                color: {tokens['text_secondary']};
                letter-spacing: 1px;
                padding: 0px;
                margin: 0px;
                border-radius: 3px;
            }}
            QPushButton:hover {{
                background: {hover_bg};
            }}
            QPushButton:pressed {{
                background: {active_bg};
            }}
        """
    set_qss(btn_prev, btn_style)
    set_qss(btn_next, btn_style)

    for btn in [btn_prev, btn_next]:
        btn.setFixedSize(20, 20)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    set_qss(year_lbl, nav_style + " margin-left: 2px; margin-right: 2px;")

    mode_btn_style = f"""
            QPushButton {{
                background: transparent;
                border: none;
                font-weight: 800;
                font-size: 10px;
                color: {tokens['text_secondary']};
                padding: 0px;
                margin: 0px;
                border-radius: 3px;
            }}
            QPushButton:hover {{ background: {hover_bg}; color: {text_primary_hex}; }}
            QPushButton:pressed {{ background: {active_bg}; color: {text_primary_hex}; }}
        """
    sep_style = f"color: {tokens['text_secondary']}; font-size: 10px; background: transparent; margin: 0px 1px;"

    mode_cont_btn = QPushButton("∞", parent=nav_controls)
    mode_cont_btn.setObjectName("heatmap_mode_cont")
    mode_cont_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    mode_cont_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    mode_cont_btn.setFlat(True)
    set_qss(mode_cont_btn, mode_btn_style)
    mode_cont_btn.setFixedSize(20, 20)

    sep_cont_365 = QLabel("|", parent=nav_controls)
    sep_cont_365.setObjectName("heatmap_sep_cont_365")
    set_qss(sep_cont_365, sep_style)

    mode_365_btn = QPushButton("365", parent=nav_controls)
    mode_365_btn.setObjectName("heatmap_mode_365")
    mode_365_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    mode_365_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    mode_365_btn.setFlat(True)
    set_qss(mode_365_btn, mode_btn_style)
    mode_365_btn.setFixedSize(28, 20)

    sep_365_year = QLabel("|", parent=nav_controls)
    sep_365_year.setObjectName("heatmap_sep_365_year")
    set_qss(sep_365_year, sep_style)

    sep_cont_year = QLabel("|", parent=nav_controls)
    sep_cont_year.setObjectName("heatmap_sep_cont_year")
    set_qss(sep_cont_year, sep_style)

    mode_year_btn = QPushButton("Y", parent=nav_controls)
    mode_year_btn.setObjectName("heatmap_mode_year")
    mode_year_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    mode_year_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    mode_year_btn.setFlat(True)
    set_qss(mode_year_btn, mode_btn_style)
    mode_year_btn.setFixedSize(20, 20)

    def _refresh_seps(cont_v, mode365_v, year_v):
        sep_cont_365.setVisible(cont_v and mode365_v)
        sep_365_year.setVisible(mode365_v and year_v)
        sep_cont_year.setVisible(cont_v and (not mode365_v) and year_v)

    def refresh_mode_styles():
        year_lbl.setVisible(current_mode[0] == "year")
        btn_prev.setVisible(True)
        btn_next.setVisible(True)
        mode_btn_active_style = f"""
                QPushButton {{
                    background: {active_bg};
                    border: none;
                    font-weight: 800;
                    font-size: 10px;
                    color: {text_primary_hex};
                    padding: 0px;
                    margin: 0px;
                    border-radius: 3px;
                }}
                QPushButton:hover {{ background: {active_bg}; color: {text_primary_hex}; }}
                QPushButton:pressed {{ background: {active_bg}; color: {text_primary_hex}; }}
            """
        for btn, mode in (
            (mode_cont_btn, "continuous"),
            (mode_365_btn, "365"),
            (mode_year_btn, "year"),
        ):
            is_active = current_mode[0] == mode
            btn.setProperty("heatmap_mode_active", bool(is_active))
            set_qss(btn, mode_btn_active_style if is_active else mode_btn_style)

    def switch_mode(new_mode):
        with local_chart_animation_batch(heatmap):
            previous_mode = current_mode[0]
            current_mode[0] = new_mode
            manager._update_dd_widget_setting("heatmap", "heatmap_mode", new_mode, refresh=False)
            heatmap.set_view_mode(new_mode)
            manager.heatmap_year, manager.end_date_365, target_end = switch_heatmap_mode_state(
                previous_mode,
                new_mode,
                getattr(manager, "heatmap_year", None),
                getattr(manager, "end_date_365", None),
                now=datetime.now(),
            )
            heatmap.set_end_date(target_end)

            year_lbl.setText(str(manager.heatmap_year))
            refresh_mode_styles()

    def update_year_or_window(delta):
        with local_chart_animation_batch(heatmap):
            if hasattr(heatmap, "begin_navigation_transition"):
                heatmap.begin_navigation_transition(delta)

            if current_mode[0] == "continuous":
                heatmap.shift_continuous(delta * 9)
                if hasattr(heatmap, "finalize_navigation_transition"):
                    heatmap.finalize_navigation_transition()
                return
            if current_mode[0] == "365":
                manager.heatmap_year, manager.end_date_365, target_end = step_heatmap_mode_state(
                    current_mode[0],
                    getattr(manager, "heatmap_year", None),
                    delta=delta,
                    end_date_365=getattr(manager, "end_date_365", None),
                    now=datetime.now(),
                )
                heatmap.set_end_date(target_end)
                if hasattr(heatmap, "finalize_navigation_transition"):
                    heatmap.finalize_navigation_transition()
                return

            manager.heatmap_year, manager.end_date_365, target_end = step_heatmap_mode_state(
                current_mode[0],
                getattr(manager, "heatmap_year", None),
                delta=delta,
                end_date_365=getattr(manager, "end_date_365", None),
                now=datetime.now(),
            )
            heatmap.set_end_date(target_end)
            year_lbl.setText(str(manager.heatmap_year))
            if hasattr(heatmap, "finalize_navigation_transition"):
                heatmap.finalize_navigation_transition()

    btn_prev.clicked.connect(lambda: update_year_or_window(-1))
    btn_next.clicked.connect(lambda: update_year_or_window(1))
    mode_year_btn.clicked.connect(lambda: switch_mode("year"))
    mode_365_btn.clicked.connect(lambda: switch_mode("365"))
    mode_cont_btn.clicked.connect(lambda: switch_mode("continuous"))

    show_365 = manager.addon_config.config.get(Config.HEATMAP_SHOW_365_MODE, True)
    show_cont = manager.addon_config.config.get(Config.HEATMAP_SHOW_CONTINUOUS_MODE, True)
    show_year = manager.addon_config.config.get(Config.HEATMAP_SHOW_YEAR_MODE, True)

    mode_365_btn.setVisible(show_365)
    mode_cont_btn.setVisible(show_cont)
    mode_year_btn.setVisible(show_year)
    _refresh_seps(show_cont, show_365, show_year)

    switch_mode(current_mode[0])

    header_widget, top_header_lay, _ = create_chart_header(parent=manager.dialog)

    header_lay.addWidget(mode_cont_btn)
    header_lay.addWidget(sep_cont_365)
    header_lay.addWidget(mode_365_btn)
    header_lay.addWidget(sep_365_year)
    header_lay.addWidget(sep_cont_year)
    header_lay.addWidget(mode_year_btn)
    header_lay.addSpacing(4)
    header_lay.addWidget(btn_prev)
    header_lay.addWidget(year_lbl)
    header_lay.addWidget(btn_next)

    top_header_lay.addWidget(nav_controls)

    return heatmap, header_widget


