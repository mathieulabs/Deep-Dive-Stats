# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from datetime import datetime, timedelta
from . import pinned_title
from aqt.qt import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, Qt, QColor
from . import Config, rollover_hour, get_color, get_svg_icon
from .....animations.chart_policy import local_chart_animation_batch
from .....logic.heatmap import (
    normalize_heatmap_mode_state,
    step_heatmap_mode_state,
    switch_heatmap_mode_state,
)
from ..shared.heatmap import (
    compose_heatmap_mode_data,
    fetch_missing_heatmap_years,
    load_pinned_heatmap_year_data,
)
from ..utils import _addon_config, _get_max_ids, cache_data_version
from ..wrapper import _wrap
from ...store.registry import WidgetRegistry
from ....charts.heatmap import HeatmapWidget
from ....chart_utils.theme import get_theme_colors
from ....common import create_hbox_container
from ......qss import set_qss
from .....logic.logger import log_swallowed

class _PinnedHeatmapNavControls(QWidget):
    """Theme-refreshable nav controls container (same live-refresh contract as charts)."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._mode_getter = None

    def set_mode_getter(self, getter):
        self._mode_getter = getter

    def refresh_data_colors(self):
        mode = None
        try:
            if callable(self._mode_getter):
                mode = self._mode_getter()
        except Exception:
            mode = None
        _apply_pinned_heatmap_nav_theme(self, current_mode=mode)

def _apply_pinned_heatmap_nav_theme(nav_controls, current_mode=None):
    """Re-apply theme-aware style to pinned heatmap nav controls (live, no restart)."""
    if not nav_controls:
        return
    try:
        t_colors = get_theme_colors(nav_controls)
        is_dark = bool(t_colors.get("is_dark"))
        text_secondary = t_colors.get("text_secondary", t_colors.get("text"))
        text_primary = t_colors.get("text_primary", t_colors.get("text"))
        accent_col = t_colors.get("accent")
        bg_hover_col = t_colors.get("bg_hover")
        text_secondary_hex = text_secondary.name() if text_secondary is not None else ("#a1a1aa" if is_dark else "#71717a")
        text_primary_hex = text_primary.name() if text_primary is not None else ("#f4f4f5" if is_dark else "#18181b")
        if bg_hover_col is not None:
            hover_bg = f"rgba({bg_hover_col.red()},{bg_hover_col.green()},{bg_hover_col.blue()},{bg_hover_col.alpha()})"
        else:
            hover_bg = "rgba(255,255,255,0.1)" if is_dark else "rgba(0,0,0,0.05)"
        active_bg = f"rgba({accent_col.red()},{accent_col.green()},{accent_col.blue()},40)" if accent_col is not None else "rgba(59,130,246,40)"

        set_qss(nav_controls, "background: transparent;")
        btn_prev = nav_controls.findChild(QPushButton, "heatmap_btn_prev")
        btn_next = nav_controls.findChild(QPushButton, "heatmap_btn_next")
        year_lbl = nav_controls.findChild(QLabel, "heatmap_year_lbl")
        mode_cont_btn = nav_controls.findChild(QPushButton, "heatmap_mode_cont")
        mode_365_btn = nav_controls.findChild(QPushButton, "heatmap_mode_365")
        mode_year_btn = nav_controls.findChild(QPushButton, "heatmap_mode_year")
        sep_cont_365 = nav_controls.findChild(QLabel, "heatmap_sep_cont_365")
        sep_365_year = nav_controls.findChild(QLabel, "heatmap_sep_365_year")
        sep_cont_year = nav_controls.findChild(QLabel, "heatmap_sep_cont_year")

        btn_style = f"""
            QPushButton {{
                background: transparent;
                border: none;
                font-weight: 800;
                font-size: 10px;
                color: {text_secondary_hex};
                letter-spacing: 1px;
                padding: 0px;
                margin: 0px;
                border-radius: 3px;
            }}
            QPushButton:hover {{ background: {hover_bg}; }}
            QPushButton:pressed {{ background: {active_bg}; }}
        """
        mode_btn_style = f"""
            QPushButton {{
                background: transparent;
                border: none;
                font-weight: 800;
                font-size: 10px;
                color: {text_secondary_hex};
                padding: 0px;
                margin: 0px;
                border-radius: 3px;
            }}
            QPushButton:hover {{ background: {hover_bg}; color: {text_primary_hex}; }}
            QPushButton:pressed {{ background: {active_bg}; color: {text_primary_hex}; }}
        """
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
        sep_style = f"color: {text_secondary_hex}; font-size: 10px; background: transparent; margin: 0px 1px;"
        nav_style = f"font-weight: 800; font-size: 10px; color: {text_secondary_hex}; letter-spacing: 1px;"

        if btn_prev:
            btn_prev.setIcon(get_svg_icon("chevron-left", size=14, color=text_secondary_hex))
            set_qss(btn_prev, btn_style)
        if btn_next:
            btn_next.setIcon(get_svg_icon("chevron-right", size=14, color=text_secondary_hex))
            set_qss(btn_next, btn_style)
        if year_lbl:
            set_qss(year_lbl, nav_style + " margin-left: 2px; margin-right: 2px;")
        for sep in (sep_cont_365, sep_365_year, sep_cont_year):
            if sep:
                set_qss(sep, sep_style)

        mode_map = (
            (mode_cont_btn, "continuous"),
            (mode_365_btn, "365"),
            (mode_year_btn, "year"),
        )
        for btn, mode in mode_map:
            if not btn:
                continue
            if current_mode is not None:
                btn.setProperty("heatmap_mode_active", bool(current_mode == mode))
            is_active = bool(btn.property("heatmap_mode_active"))
            set_qss(btn, mode_btn_active_style if is_active else mode_btn_style)
    except Exception:
        log_swallowed()
_SESSION_YEARS = {}


def _build_heatmap(widget_def, deck_id, cache=None, parent=None, cfg=None):
    rollover = rollover_hour()
    now = datetime.now()
    if now.hour < rollover:
        effective_now = now - timedelta(days=1)
    else:
        effective_now = now
        
    # The browsed year is kept for this Anki session only (deck navigation and rebuilds keep it); a new session opens on the current year. A "year" left in old configs is ignored.
    try:
        year = int(_SESSION_YEARS.get(widget_def.get("id"), effective_now.year) or effective_now.year)
    except Exception:
        year = effective_now.year
    if cfg is None:
        cfg = _addon_config()


    chart_ref = [None]
    total_heatmap_data = {}  # deck_id -> total heatmap_data dict
    year_data_cache = {}

    def _active_deck_id():
        chart_obj = chart_ref[0]
        if chart_obj is not None:
            return chart_obj.property("pinned_deck_id")
        return deck_id

    def get_year_data(target_year, allow_blocking=False):
        active_deck_id = _active_deck_id()
        # Mode switches and arrows must read the same caches as the runtime refresh.
        # The build-time caches below never see reviews made after the widget was built,
        # so today's reviews vanished on a mode switch until the next refresh.
        total_cache, year_cache = total_heatmap_data, year_data_cache
        chart_obj = chart_ref[0]
        if chart_obj is not None:
            try:
                _ensure_runtime_heatmap_caches(
                    chart_obj,
                    active_deck_id,
                    (_get_max_ids(allow_db=allow_blocking), cache_data_version(), _heatmap_snapshot_version()),
                )
                total_cache = chart_obj._runtime_total_heatmap_cache
                year_cache = chart_obj._runtime_year_data_cache
            except Exception:
                log_swallowed()
        data, end, _ = load_pinned_heatmap_year_data(
            active_deck_id,
            target_year,
            cfg=cfg,
            allow_slow_ops=allow_blocking,
            total_heatmap_cache=total_cache,
            year_data_cache=year_cache,
            prefer_total_cache=True,
            missing_default={},
        )
        return data, end

    empty_opacity = cfg.config.get(Config.HEATMAP_EMPTY_OPACITY, 50)
    filled_opacity = cfg.config.get(Config.HEATMAP_FILLED_OPACITY, 100)
    empty_white = cfg.config.get(Config.HEATMAP_EMPTY_WHITE, False)
    hide_title = cfg.config.get(Config.HEATMAP_HIDE_TITLE, True)
    hide_labels = cfg.config.get(Config.HEATMAP_HIDE_LABELS, True)
    tinted_future = cfg.config.get(Config.HEATMAP_TINTED_FUTURE, False)
    heatmap_color = get_color(cfg.config, Config.HEATMAP_COLOR, "pinned")
    monday_first = cfg.config.get(Config.HEATMAP_MONDAY_FIRST, False)
    scale = (cfg.config.get(Config.HEATMAP_SCALE, 78) / 100.0)
    color_levels = cfg.config.get(Config.HEATMAP_COLOR_LEVELS, 20)
    vibrance = cfg.config.get(Config.HEATMAP_VIBRANCE, 100)
    rounding = cfg.config.get(Config.HEATMAP_ROUNDING, 30)
    intensity_curve = cfg.config.get(Config.HEATMAP_INTENSITY_CURVE, 100)
    multi_hue_intensity = cfg.config.get(Config.HEATMAP_MULTI_HUE_INTENSITY, False)
    
    current_mode = [widget_def.get("heatmap_mode", "year")]
    if isinstance(current_mode[0], bool) or current_mode[0] not in ["year", "365", "continuous"]:
        current_mode[0] = "year"
    year, initial_end_365, _ = normalize_heatmap_mode_state(
        current_mode[0],
        year,
        None,
        now=datetime.now(),
    )
    end_date_365 = [initial_end_365]

    # Allow one blocking fill on first render only, then keep navigation non-blocking.
    if current_mode[0] == "year":
        heatmap_data, initial_end = get_year_data(year, allow_blocking=True)
    else:
        heatmap_data, initial_end = compose_heatmap_mode_data(
            year,
            current_mode[0],
            lambda yr: get_year_data(yr, allow_blocking=True),
            now=datetime.now(),
        )
        if current_mode[0] == "365":
            initial_end = end_date_365[0]

    show_365 = cfg.config.get(Config.HEATMAP_SHOW_365_MODE, True)
    show_cont = cfg.config.get(Config.HEATMAP_SHOW_CONTINUOUS_MODE, True)
    show_year = cfg.config.get(Config.HEATMAP_SHOW_YEAR_MODE, True)

    chart = HeatmapWidget(heatmap_data, color_scheme=heatmap_color, end_date=initial_end,
                          empty_opacity=empty_opacity, empty_white=empty_white, filled_opacity=filled_opacity, hide_labels=hide_labels, scale=scale, tinted_future=tinted_future, rounding=rounding, intensity_curve=intensity_curve, monday_first=monday_first,
                          color_levels=color_levels, parent=parent, vibrance=vibrance, view_mode=current_mode[0], multi_hue_intensity=multi_hue_intensity)
    chart_ref[0] = chart
    chart.set_metric(cfg.config.get(Config.HEATMAP_METRIC, "reviews"))
    chart.set_show_legend(bool(widget_def.get(Config.HEATMAP_SHOW_LEGEND, cfg.config.get(Config.HEATMAP_SHOW_LEGEND, True))))
    chart.set_invert_intensity(cfg.config.get(Config.HEATMAP_INVERT_INTENSITY, False))
    chart.tooltip_hidden = list(cfg.config.get(Config.HEATMAP_TOOLTIP_HIDDEN, []) or [])

    chart.setObjectName("heatmap_widget")
    chart.setProperty("pinned_widget", True)  # Mark as pinned to distinguish from deep-dive heatmaps
    chart.setProperty("pinned_deck_id", deck_id)
    chart._last_pinned_deck_id = deck_id

    if cfg.config.get(Config.HEATMAP_CLICK_BROWSER, True):
        from .....logic.interactions import HeatmapInteractions
        chart.day_clicked = lambda date_str, did=deck_id: HeatmapInteractions.open_browser_for_date(date_str, did)

    nav_pos = cfg.config.get(Config.HEATMAP_NAV_POS, "top_right")
    chart.setProperty("nav_pos", nav_pos)

    is_top = nav_pos.startswith("top_")
    is_left = nav_pos.endswith("_left")

    chart.cont_right_anchor = not is_left

    nav_controls = _PinnedHeatmapNavControls(parent)
    nav_controls.setObjectName("heatmap_nav_controls")
    # Nav controls are styled immediately (before being wrapped into a pinned card),
    # so we must set the theme context explicitly to avoid defaulting to Details.
    nav_controls.setProperty("deepdivestats_theme_context", "pinned")
    nav_controls.setProperty("deepdivestats_ignore_forced_dark_theme", True)
    set_qss(nav_controls, "background: transparent;")
    nav_lay = QHBoxLayout(nav_controls)
    nav_lay.setContentsMargins(0, 0, 0, 0)
    nav_lay.setSpacing(2)

    btn_prev = QPushButton(parent=nav_controls)
    btn_next = QPushButton(parent=nav_controls)
    btn_prev.setObjectName("heatmap_btn_prev")
    btn_next.setObjectName("heatmap_btn_next")
    t_colors = get_theme_colors(nav_controls)
    is_dark = bool(t_colors.get("is_dark"))
    text_secondary = t_colors.get("text_secondary", t_colors.get("text"))
    text_primary = t_colors.get("text_primary", t_colors.get("text"))
    accent_col = t_colors.get("accent")
    bg_hover_col = t_colors.get("bg_hover")

    text_secondary_hex = text_secondary.name() if text_secondary is not None else ("#a1a1aa" if is_dark else "#71717a")
    text_primary_hex = text_primary.name() if text_primary is not None else ("#f4f4f5" if is_dark else "#18181b")
    if bg_hover_col is not None:
        hover_bg = f"rgba({bg_hover_col.red()},{bg_hover_col.green()},{bg_hover_col.blue()},{bg_hover_col.alpha()})"
    else:
        hover_bg = "rgba(255,255,255,0.1)" if is_dark else "rgba(0,0,0,0.05)"
    active_bg = f"rgba({accent_col.red()},{accent_col.green()},{accent_col.blue()},40)" if accent_col is not None else "rgba(59,130,246,40)"

    btn_prev.setIcon(get_svg_icon("chevron-left", size=14, color=text_secondary_hex))
    btn_next.setIcon(get_svg_icon("chevron-right", size=14, color=text_secondary_hex))

    year_lbl = QLabel(str(year), parent=nav_controls)
    year_lbl.setObjectName("heatmap_year_lbl")

    NAV_STYLE = f"font-weight: 800; font-size: 10px; color: {text_secondary_hex}; letter-spacing: 1px;"
    btn_style = f"""
        QPushButton {{
            background: transparent;
            border: none;
            font-weight: 800;
            font-size: 10px;
            color: {text_secondary_hex};
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
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.setFixedSize(20, 20)

    set_qss(year_lbl, NAV_STYLE + " margin-left: 2px; margin-right: 2px;")

    # Mode buttons have no letter-spacing so the text stays centered in the fixed-size box
    mode_btn_style = f"""
        QPushButton {{
            background: transparent;
            border: none;
            font-weight: 800;
            font-size: 10px;
            color: {text_secondary_hex};
            padding: 0px;
            margin: 0px;
            border-radius: 3px;
        }}
        QPushButton:hover {{ background: {hover_bg}; color: {text_primary_hex}; }}
        QPushButton:pressed {{ background: {active_bg}; color: {text_primary_hex}; }}
    """
    sep_style = f"color: {text_secondary_hex}; font-size: 10px; background: transparent; margin: 0px 1px;"

    mode_cont_btn = QPushButton("\u221e", parent=nav_controls)
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

    # Extra separator: shown between ∞ and Y when 365 is hidden
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

    # Keep hidden sep labels so context_menu findChild still works
    sep1 = QLabel(parent=nav_controls)
    sep1.setObjectName("heatmap_sep_365")
    sep1.hide()
    sep2 = QLabel(parent=nav_controls)
    sep2.setObjectName("heatmap_sep_cont")
    sep2.hide()

    def _refresh_seps(cont_v, mode365_v, year_v):
        """Update separator visibility so there's always a | between adjacent visible modes."""
        sep_cont_365.setVisible(cont_v and mode365_v)
        sep_365_year.setVisible(mode365_v and year_v)
        sep_cont_year.setVisible(cont_v and not mode365_v and year_v)

    # Years whose data is already merged into chart.data (for lazy-fetch in rolling modes)
    fetched_years = {year, year - 1}
    # The runtime refresh replaces chart.data with the years it composes, so it
    # resets this set too. Otherwise years fetched earlier, or for another deck,
    # count as loaded and the arrows show them empty.
    chart._pinned_fetched_years = fetched_years
    nav_controls.set_mode_getter(lambda: current_mode[0])

    def refresh_mode_styles():
        year_lbl.setVisible(current_mode[0] == "year")
        btn_prev.setVisible(True)
        btn_next.setVisible(True)
        mode_map = (
            (mode_cont_btn, "continuous"),
            (mode_365_btn, "365"),
            (mode_year_btn, "year"),
        )
        for btn, mode in mode_map:
            is_active = (current_mode[0] == mode)
            btn.setProperty("heatmap_mode_active", bool(is_active))
        _apply_pinned_heatmap_nav_theme(nav_controls, current_mode=current_mode[0])

    def get_data_for_mode(target_year, mode):
        """Fetch data appropriate for the given mode and year."""
        return compose_heatmap_mode_data(
            target_year,
            mode,
            lambda yr: get_year_data(yr, allow_blocking=False),
            now=datetime.now(),
        )

    def switch_mode(new_mode):
        nonlocal year
        previous_mode = current_mode[0]
        if new_mode == previous_mode:
            refresh_mode_styles()
            return
        with local_chart_animation_batch(chart):
            current_mode[0] = new_mode
            WidgetRegistry.update_setting(widget_def["id"], "heatmap_mode", new_mode)
            chart.set_view_mode(new_mode)
            year, end_date_365[0], _ = switch_heatmap_mode_state(
                previous_mode,
                new_mode,
                year,
                end_date_365=end_date_365[0],
                now=datetime.now(),
            )
            _SESSION_YEARS[widget_def.get("id")] = int(year)
            new_data, new_end = get_data_for_mode(year, new_mode)
            if new_mode == "365":
                new_end = end_date_365[0]
            if new_mode in ("365", "continuous"):
                fetched_years.clear()
                fetched_years.update({year, year - 1})
            chart._suppress_next_transition = True
            if new_mode == "year":
                chart.set_end_date(new_end)
                chart.update_data(new_data)
            else:
                chart.update_data(new_data)
                chart.set_end_date(new_end)
            if new_mode == "year":
                year_lbl.setText(str(year))
            refresh_mode_styles()

    def update_year_or_window(delta):
        nonlocal year
        with local_chart_animation_batch(chart):
            chart.begin_navigation_transition(delta)
            if current_mode[0] == "continuous":
                chart.shift_continuous(delta * 9)
                months = chart._get_continuous_months()
                missing, combined = fetch_missing_heatmap_years(
                    {m[0] for m in months},
                    fetched_years,
                    chart.data,
                    lambda yr: get_year_data(yr, allow_blocking=False),
                )
                if missing and combined:
                    chart._suppress_next_transition = True
                    chart.update_data(combined)
                chart.finalize_navigation_transition()
                return
            if current_mode[0] == "365":
                year, end_date_365[0], target_end = step_heatmap_mode_state(
                    current_mode[0],
                    year,
                    delta=delta,
                    end_date_365=end_date_365[0],
                    now=datetime.now(),
                )
                target_yr = year
                missing, combined = fetch_missing_heatmap_years(
                    {target_yr, target_yr - 1},
                    fetched_years,
                    chart.data,
                    lambda yr: get_year_data(yr, allow_blocking=False),
                )
                if missing and combined is not None:
                    chart._suppress_next_transition = True
                    chart.update_data(combined)
                chart.set_end_date(target_end)
                chart.finalize_navigation_transition()
                _SESSION_YEARS[widget_def.get("id")] = int(year)
                return
            year, end_date_365[0], new_end = step_heatmap_mode_state(
                current_mode[0],
                year,
                delta=delta,
                end_date_365=end_date_365[0],
                now=datetime.now(),
            )
            new_data, new_end = get_data_for_mode(year, current_mode[0])
            chart.set_end_date(new_end)
            chart._suppress_next_transition = True
            chart.update_data(new_data)
            chart.finalize_navigation_transition()
            if current_mode[0] == "year":
                year_lbl.setText(str(year))
            _SESSION_YEARS[widget_def.get("id")] = int(year)

    btn_prev.clicked.connect(lambda: update_year_or_window(-1))
    btn_next.clicked.connect(lambda: update_year_or_window(1))
    mode_year_btn.clicked.connect(lambda: switch_mode("year"))
    mode_365_btn.clicked.connect(lambda: switch_mode("365"))
    mode_cont_btn.clicked.connect(lambda: switch_mode("continuous"))

    mode_365_btn.setVisible(show_365)
    mode_cont_btn.setVisible(show_cont)
    mode_year_btn.setVisible(show_year)
    _refresh_seps(show_cont, show_365, show_year)
    refresh_mode_styles()
    _apply_pinned_heatmap_nav_theme(nav_controls, current_mode=current_mode[0])

    if current_mode[0] != "year":
        switch_mode(current_mode[0])

    if is_left:
        # Left nav: ‹ 2026 ›  [spacing]  Y | 365 | ∞
        nav_lay.addWidget(btn_prev)
        nav_lay.addWidget(year_lbl)
        nav_lay.addWidget(btn_next)
        nav_lay.addSpacing(4)
        nav_lay.addWidget(mode_year_btn)
        nav_lay.addWidget(sep_365_year)
        nav_lay.addWidget(sep_cont_year)
        nav_lay.addWidget(mode_365_btn)
        nav_lay.addWidget(sep_cont_365)
        nav_lay.addWidget(mode_cont_btn)
    else:
        # Right nav: ∞ | 365 | Y  [spacing]  ‹ 2026 ›
        nav_lay.addWidget(mode_cont_btn)
        nav_lay.addWidget(sep_cont_365)
        nav_lay.addWidget(mode_365_btn)
        nav_lay.addWidget(sep_365_year)
        nav_lay.addWidget(sep_cont_year)
        nav_lay.addWidget(mode_year_btn)
        nav_lay.addSpacing(4)
        nav_lay.addWidget(btn_prev)
        nav_lay.addWidget(year_lbl)
        nav_lay.addWidget(btn_next)

    show_glass = cfg.config.get(Config.HEATMAP_SHOW_GLASS, False)
    
    if is_top:
        header_widget, header_lay = create_hbox_container(
            parent,
            margins=(0, 0, 0, 0),
            spacing=8,
            transparent=True,
        )
        
        title_text = pinned_title(widget_def, "ACTIVITY")
        title = QLabel(title_text.upper(), parent=header_widget)
        title.setObjectName("pinned_header")
        title.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        title.setVisible(not hide_title and bool(title_text))

        if is_left:
            header_lay.addWidget(nav_controls)
            header_lay.addStretch()
            header_lay.addWidget(title)
        else:
            header_lay.addWidget(title)
            header_lay.addStretch()
            header_lay.addWidget(nav_controls)
        _align_nav_to_grid(chart, header_lay, is_left)

        return _wrap(chart, None, header_widget=header_widget, wtype="heatmap",
                     widget_id=widget_def["id"],
                     saved_w=widget_def.get("width"),
                     saved_h=widget_def.get("height"),
                     resizable=show_glass,
                     parent=parent)
    else:
        footer_widget, footer_lay = create_hbox_container(
            parent,
            margins=(0, 2, 0, 0),
            transparent=True,
        )
        
        if is_left:
            footer_lay.addWidget(nav_controls)
            footer_lay.addStretch()
        else:
            footer_lay.addStretch()
            footer_lay.addWidget(nav_controls)
        _align_nav_to_grid(chart, footer_lay, is_left)
        
        container = QWidget(parent)
        set_qss(container, "background: transparent;")
        container_lay = QVBoxLayout(container)
        container_lay.setContentsMargins(0, 4, 0, 0)
        container_lay.setSpacing(0)
        container_lay.addWidget(chart)
        container_lay.addWidget(footer_widget)

        label = None if hide_title else (pinned_title(widget_def, "ACTIVITY") or None)
        return _wrap(container, label, wtype="heatmap",
                     widget_id=widget_def["id"],
                     saved_w=widget_def.get("width"),
                     saved_h=widget_def.get("height"),
                     resizable=show_glass,
                     parent=parent)


def _align_nav_to_grid(chart, lay, is_left):
    """The grid is centred inside the chart widget, so a nav row anchored to the
    widget edge floats past the visible cells. Inset it to the grid's edges."""
    if not hasattr(chart, "add_extent_listener"):
        return
    base = lay.contentsMargins()

    def _apply(ext, widget_w):
        left, right = ext
        left_m = max(0, int(round(left)))
        right_m = max(0, int(round(widget_w - right)))
        m = lay.contentsMargins()
        if is_left:
            new = (base.left() + left_m, m.top(), base.right(), m.bottom())
        else:
            new = (base.left(), m.top(), base.right() + right_m, m.bottom())
        if (m.left(), m.right()) != (new[0], new[2]):
            lay.setContentsMargins(*new)

    chart.add_extent_listener(_apply)


def _runtime_heatmap_refresh_anchor(now, current_view_mode, target_year, end_date):
    if current_view_mode == "year":
        return f"year:{int(target_year)}"
    if current_view_mode == "365":
        logical_now = now - timedelta(days=1) if now.hour < rollover_hour() else now
        if int(target_year) == int(logical_now.year):
            return f"365:{logical_now.strftime('%Y-%m-%d')}"
        if end_date is not None:
            try:
                return f"365:{end_date.strftime('%Y-%m-%d')}"
            except Exception:
                log_swallowed()
        return f"365:{int(target_year)}"
    if end_date is not None:
        try:
            return f"{current_view_mode}:{end_date.strftime('%Y-%m-%d')}"
        except Exception:
            log_swallowed()
    return f"{current_view_mode}:{int(target_year)}"


def _color_token(value):
    try:
        return int(QColor(value).rgba())
    except Exception:
        return str(value)


def _same_heatmap_value(current, expected):
    if isinstance(current, float) or isinstance(expected, float):
        try:
            return abs(float(current) - float(expected)) < 0.0001
        except Exception:
            return current == expected
    return current == expected


def _heatmap_snapshot_version():
    # Future (due) cells are re-projected by the snapshot pass without new ids.
    try:
        from .....logic.history_cache.population import snapshot_version

        return snapshot_version()
    except Exception:
        return None


def _collection_token():
    # Another profile can have the same deck ids and similar revlog ids: key caches on the collection too.
    try:
        from aqt import mw

        return str(getattr(mw.col, "path", "") or "")
    except Exception:
        return ""


def _ensure_runtime_heatmap_caches(chart, deck_id, max_ids):
    cache_key = (deck_id, max_ids, _collection_token())
    if getattr(chart, "_runtime_heatmap_cache_key", None) != cache_key:
        chart._runtime_heatmap_cache_key = cache_key
        chart._runtime_total_heatmap_cache = {}
        chart._runtime_year_data_cache = {}
    elif not hasattr(chart, "_runtime_total_heatmap_cache"):
        chart._runtime_total_heatmap_cache = {}
        chart._runtime_year_data_cache = {}


def _apply_heatmap_runtime_visuals(chart, widget_def):
    current_scale_pct = float(getattr(chart, "scale", 1.0)) * 100.0
    if Config.HEATMAP_SCALE in widget_def:
        next_scale_pct = float(widget_def.get(Config.HEATMAP_SCALE, 100))
        if not _same_heatmap_value(current_scale_pct, next_scale_pct):
            chart.set_scale(next_scale_pct)

    if Config.HEATMAP_EMPTY_OPACITY in widget_def:
        next_empty_opacity = widget_def.get(Config.HEATMAP_EMPTY_OPACITY, 15)
        if not _same_heatmap_value(getattr(chart, "current_opacity_pct", None), next_empty_opacity):
            chart.set_empty_opacity(next_empty_opacity)

    if Config.HEATMAP_FILLED_OPACITY in widget_def:
        next_filled_opacity = widget_def.get(Config.HEATMAP_FILLED_OPACITY, 100)
        if not _same_heatmap_value(getattr(chart, "filled_opacity_pct", None), next_filled_opacity):
            chart.set_filled_opacity(next_filled_opacity)

    if Config.HEATMAP_EMPTY_WHITE in widget_def:
        next_empty_white = bool(widget_def.get(Config.HEATMAP_EMPTY_WHITE, False))
        if bool(getattr(chart, "empty_white", False)) != next_empty_white:
            chart.set_empty_white(next_empty_white)

    if Config.HEATMAP_HIDE_LABELS in widget_def:
        next_hide_labels = bool(widget_def.get(Config.HEATMAP_HIDE_LABELS, True))
        if bool(getattr(chart, "hide_labels", False)) != next_hide_labels:
            chart.set_hide_labels(next_hide_labels)

    if Config.HEATMAP_SHOW_LEGEND in widget_def:
        chart.set_show_legend(bool(widget_def.get(Config.HEATMAP_SHOW_LEGEND, True)))

    if Config.HEATMAP_TINTED_FUTURE in widget_def:
        next_tinted_future = bool(widget_def.get(Config.HEATMAP_TINTED_FUTURE, False))
        if bool(getattr(chart, "tinted_future", False)) != next_tinted_future:
            chart.set_tinted_future(next_tinted_future)

    if Config.HEATMAP_MONDAY_FIRST in widget_def:
        next_monday_first = bool(widget_def.get(Config.HEATMAP_MONDAY_FIRST, True))
        if bool(getattr(chart, "monday_first", False)) != next_monday_first:
            chart.set_monday_first(next_monday_first)

    if Config.HEATMAP_SHOW_FUTURE in widget_def:
        next_show_future = bool(widget_def.get(Config.HEATMAP_SHOW_FUTURE, True))
        if bool(getattr(chart, "show_future", True)) != next_show_future:
            chart.set_show_future(next_show_future)

    if Config.HEATMAP_COLOR in widget_def:
        next_color = widget_def.get(Config.HEATMAP_COLOR, "#3b82f6")
        if not isinstance(next_color, str) or not next_color.strip():
            next_color = "#3b82f6"
        if _color_token(getattr(chart, "base_color", None)) != _color_token(next_color):
            chart.base_color = QColor(next_color)
            chart._update_levels()

    if Config.HEATMAP_COLOR_LEVELS in widget_def:
        next_color_levels = max(2, int(widget_def.get(Config.HEATMAP_COLOR_LEVELS, 15)))
        if int(getattr(chart, "color_levels", 15)) != next_color_levels:
            chart.set_color_levels(next_color_levels)

    if Config.HEATMAP_VIBRANCE in widget_def:
        next_vibrance = int(widget_def.get(Config.HEATMAP_VIBRANCE, 100))
        if int(getattr(chart, "vibrance", 100)) != next_vibrance:
            chart.set_vibrance(next_vibrance)

    if Config.HEATMAP_ROUNDING in widget_def:
        next_rounding = int(widget_def.get(Config.HEATMAP_ROUNDING, 20))
        if int(getattr(chart, "rounding", 20)) != next_rounding:
            chart.set_rounding(next_rounding)

    if Config.HEATMAP_INTENSITY_CURVE in widget_def:
        next_curve = int(widget_def.get(Config.HEATMAP_INTENSITY_CURVE, 100))
        if int(getattr(chart, "intensity_curve", 100)) != next_curve:
            chart.set_intensity_curve(next_curve)

    if Config.HEATMAP_MULTI_HUE_INTENSITY in widget_def:
        next_multi_hue = bool(widget_def.get(Config.HEATMAP_MULTI_HUE_INTENSITY, False))
        if bool(getattr(chart, "multi_hue_intensity", False)) != next_multi_hue:
            chart.set_multi_hue_intensity(next_multi_hue)

    if Config.HEATMAP_METRIC in widget_def:
        chart.set_metric(widget_def.get(Config.HEATMAP_METRIC, "reviews"))

    if Config.HEATMAP_INVERT_INTENSITY in widget_def:
        chart.set_invert_intensity(bool(widget_def.get(Config.HEATMAP_INVERT_INTENSITY, False)))

    if Config.HEATMAP_TOOLTIP_HIDDEN in widget_def:
        chart.tooltip_hidden = list(widget_def.get(Config.HEATMAP_TOOLTIP_HIDDEN) or [])

def _update_heatmap(inner, widget_def, deck_id=None, cache=None, fail_if_not_cached=False, cfg=None):
    chart = inner
    if not hasattr(chart, "update_data"):
        chart = inner.findChild(HeatmapWidget)
        
    if not chart:
        return False
    previous_pinned_deck_id = getattr(chart, "_last_pinned_deck_id", chart.property("pinned_deck_id"))
    chart.setProperty("pinned_deck_id", deck_id)
    chart._force_next_data_transition = previous_pinned_deck_id != deck_id
    
    # widget_def holds the live-edited settings (in the settings context it is the config).
    
    c = widget_def
    _apply_heatmap_runtime_visuals(chart, c)

    # A nav position change needs a full rebuild
    # The position is a global setting: widget_def only has it when it carries the live
    # settings, so fall back to the config instead of the default (or a change to a position
    # that equals the default would never be seen by a rebuild).
    if Config.HEATMAP_NAV_POS in c:
        current_nav_pos = c.get(Config.HEATMAP_NAV_POS, "top_right")
    else:
        if cfg is None:
            from ..utils import _addon_config
            cfg = _addon_config()
        current_nav_pos = cfg.config.get(Config.HEATMAP_NAV_POS, "top_right")
    if hasattr(chart, "property"):
        if chart.property("nav_pos") != current_nav_pos:
            return False
        chart.setProperty("nav_pos", current_nav_pos)
        
    if Config.HEATMAP_HIDE_TITLE in c:
        hide_title = c.get(Config.HEATMAP_HIDE_TITLE, True)
        parent = chart.parentWidget()
        if parent:
            header_lbl = parent.findChild(QLabel, "pinned_header")
            if header_lbl:
                header_lbl.setVisible(not hide_title)
            if hasattr(parent, "set_label_visible"):
                 parent.set_label_visible(not hide_title)

    now = datetime.now()
    current_view_mode = getattr(chart, "view_mode", "year")

    if hasattr(chart, "end_date") and chart.end_date:
        target_year = chart.end_date.year
    else:
        target_year = now.year

    # Deep Dive heatmaps need no data refresh here (the global chart refresh handles them); pinned heatmaps carry the pinned_widget property.
    is_deep_dive = not bool(chart.property("pinned_widget"))

    # Cache data version too: the same DB ids can map to newer cache contents.
    max_ids = (_get_max_ids(allow_db=not fail_if_not_cached), cache_data_version(), _heatmap_snapshot_version())
    force_runtime_refresh = bool(getattr(chart, "_force_runtime_refresh_once", False))
    applied_refresh_key = (
        deck_id,
        current_view_mode,
        int(target_year),
        _runtime_heatmap_refresh_anchor(now, current_view_mode, target_year, getattr(chart, "end_date", None)),
        max_ids,
    )
    runtime_refresh_key = (
        deck_id,
        current_view_mode,
        int(target_year),
        applied_refresh_key[3],
        bool(fail_if_not_cached),
        max_ids,
    )


    if cfg is None:
        cfg = _addon_config()

    if cfg.config.get(Config.HEATMAP_CLICK_BROWSER, True):
        from .....logic.interactions import HeatmapInteractions
        chart.day_clicked = lambda date_str, did=deck_id: HeatmapInteractions.open_browser_for_date(date_str, did)
    else:
        chart.day_clicked = None

    if not is_deep_dive:
        _ensure_runtime_heatmap_caches(chart, deck_id, max_ids)
        if (not force_runtime_refresh) and getattr(chart, "_last_applied_runtime_refresh_key", None) == applied_refresh_key:
            return True
        if (not force_runtime_refresh) and getattr(chart, "_last_runtime_refresh_key", None) == runtime_refresh_key:
            pass
        else:
            def _fetch_year_data(yr):
                data, _, source = load_pinned_heatmap_year_data(
                    deck_id, yr, cfg=cfg,
                    allow_slow_ops=not fail_if_not_cached,
                    total_heatmap_cache=chart._runtime_total_heatmap_cache,
                    year_data_cache=chart._runtime_year_data_cache,
                    prefer_total_cache=True,
                    missing_default=None,
                )
                if data is None:
                    return None
                if source == "context_heatmap_data":
                    return data
                if source == "context_reviews":
                    return data
                return data

            new_data, new_end = compose_heatmap_mode_data(
                target_year,
                current_view_mode,
                lambda yr: (_fetch_year_data(yr), datetime(yr, 12, 31, 23, 59, 59)),
                now=now,
            )
            if new_data is None:
                return False

            if (not force_runtime_refresh) and (getattr(chart, "data", None) == new_data) and (getattr(chart, "end_date", None) == new_end):
                chart._last_runtime_refresh_key = runtime_refresh_key
                chart._last_applied_runtime_refresh_key = applied_refresh_key
                chart._last_pinned_deck_id = deck_id
                return True

            chart.update_data(new_data)
            chart.set_end_date(new_end)
            fetched = getattr(chart, "_pinned_fetched_years", None)
            if isinstance(fetched, set):
                fetched.clear()
                fetched.add(int(target_year))
                if current_view_mode != "year":
                    fetched.add(int(target_year) - 1)
            chart._last_runtime_refresh_key = runtime_refresh_key
            chart._last_applied_runtime_refresh_key = applied_refresh_key
            chart._last_pinned_deck_id = deck_id
            chart._force_runtime_refresh_once = False
        if force_runtime_refresh and getattr(chart, "_force_runtime_refresh_once", False):
            chart._force_runtime_refresh_once = False

    if current_view_mode == "year":
        year_lbl = inner.findChild(QLabel, "heatmap_year_lbl")
        if year_lbl:
            year_lbl.setText(str(target_year))


    return True


