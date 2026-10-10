# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors

from __future__ import annotations

from typing import Any

from aqt.qt import QDate, Qt

from ... import Config
from ... import (
    ADAPTIVE_CHART_BINNING,
    CHART_BINNING_SCALE,
    Period,
)

from .range_options import RANGE_OPTIONS
from ....logic.logger import log_swallowed

_BASE_CONTROL_ATTRS = (
    "enabled_check",
    "title_edit",
    "range_combo",
    "custom_type_combo",
    "days_spin",
    "start_date_edit",
    "end_date_edit",
    "to_today_check",
)

_TAB_BOOL_FIELDS = (
    ("decimal_check", "use_decimal", True),
    ("show_time_check", "show_time", True),
    ("show_reviews_check", "show_reviews", True),
    ("retention_check", "show_retention", True),
    ("retention_young_check", "show_retention_young", True),
    ("retention_mature_check", "show_retention_mature", True),
    ("avg_time_check", "show_avg_time", True),
    ("show_counts_check", "show_counts", True),
    ("show_streak_check", "show_streak", False),
    ("show_active_days_check", "show_active_days", True),
    ("show_longest_streak_check", "show_longest_streak", True),
    ("show_buttons_dist_check", "show_buttons_dist", False),
    ("show_forecast_check", "show_forecast", True),
)


def _set_groups_enabled(dialog: Any, enabled: bool) -> None:
    dialog.group_general.setEnabled(enabled)
    dialog.group_range.setEnabled(enabled)
    dialog.group_format.setEnabled(enabled)
    dialog.group_cols.setEnabled(enabled)


def _resolve_binning_scale(conf: dict[str, Any]) -> int:
    try:
        scale = int(conf.get(CHART_BINNING_SCALE, 100))
    except Exception:
        scale = 100
    return max(50, min(200, scale))


def apply_tab_selection_state(dialog: Any, row: int) -> None:
    if row < 0 or row >= len(dialog.tabs_data):
        _set_groups_enabled(dialog, False)
        return

    _set_groups_enabled(dialog, True)
    tab = dialog.tabs_data[row]
    conf = dialog.parent_dialog.addon_config.config
    base_controls = [getattr(dialog, name) for name in _BASE_CONTROL_ATTRS]
    tab_bool_bindings = [(getattr(dialog, attr), key, default) for attr, key, default in _TAB_BOOL_FIELDS]

    for control in base_controls:
        control.blockSignals(True)
    for checkbox, _key, _default in tab_bool_bindings:
        checkbox.blockSignals(True)
    try:
        dialog.enabled_check.setChecked(tab.get("enabled", True))
        dialog.title_edit.setText(tab.get("title", ""))

        range_val = tab.get("range", Period.WEEK)
        for i, (_label, val) in enumerate(RANGE_OPTIONS):
            if val == range_val:
                dialog.range_combo.setCurrentIndex(i)
                break

        is_custom = range_val == Period.CUSTOM
        dialog.custom_type_label.setVisible(is_custom)
        dialog.custom_type_combo.setVisible(is_custom)

        custom_type = tab.get("custom_type", "relative")
        idx = dialog.custom_type_combo.findData(custom_type)
        if idx >= 0:
            dialog.custom_type_combo.setCurrentIndex(idx)

        is_relative = is_custom and custom_type == "relative"
        is_absolute = is_custom and custom_type == "absolute"

        dialog.days_spin.setVisible(is_relative)
        dialog.days_label.setVisible(is_relative)
        dialog.days_spin.setValue(tab.get("days", 7))

        dialog.start_date_label.setVisible(is_absolute)
        dialog.start_date_edit.setVisible(is_absolute)
        dialog.end_date_label.setVisible(is_absolute)
        dialog.end_date_edit.setVisible(is_absolute)
        dialog.to_today_label.setVisible(is_absolute)
        dialog.to_today_check.setVisible(is_absolute)

        start_date_str = tab.get("start_date", QDate.currentDate().toString(Qt.DateFormat.ISODate))
        dialog.start_date_edit.setDate(QDate.fromString(start_date_str, Qt.DateFormat.ISODate))
        end_date_str = tab.get("end_date", QDate.currentDate().toString(Qt.DateFormat.ISODate))
        to_today = bool(tab.get("to_today", False))
        if not end_date_str:
            end_date_str = QDate.currentDate().toString(Qt.DateFormat.ISODate)
        dialog.end_date_edit.setDate(QDate.fromString(end_date_str, Qt.DateFormat.ISODate))
        dialog.to_today_check.setChecked(to_today)
        dialog.end_date_edit.setEnabled(not to_today)

        for checkbox, key, default in tab_bool_bindings:
            checkbox.setChecked(tab.get(key, default))

        dialog.full_name_check.setChecked(conf.get(Config.SHOW_FULL_DECK_NAME, False))
        dialog.adaptive_binning_check.setChecked(conf.get(ADAPTIVE_CHART_BINNING, True))
        dialog.show_empty_charts_check.setChecked(conf.get(Config.SHOW_EMPTY_CHARTS, False))
        dialog.dd_collapsible_check.setChecked(conf.get(Config.DEEP_DIVE_CHARTS_COLLAPSIBLE, True))
        dialog.dd_fill_height_check.setChecked(conf.get(Config.DEEP_DIVE_FILL_HEIGHT, True))

        from .dialog_runtime_handlers import binning_index_from_scale

        scale_idx = binning_index_from_scale(_resolve_binning_scale(conf))
        dialog.binning_scale_slider.blockSignals(True)
        dialog.binning_scale_slider.setValue(scale_idx)
        dialog.binning_scale_slider.blockSignals(False)
        dialog._update_binning_scale_label(scale_idx)
        _bin_on = dialog.adaptive_binning_check.isChecked()
        dialog.binning_scale_slider.setEnabled(_bin_on)
        dialog.binning_scale_reset_btn.setEnabled(_bin_on)

        dialog.thousands_separator_check.setChecked(conf.get(Config.USE_THOUSANDS_SEPARATOR, True))

        toolbar_style = conf.get(Config.TOOLBAR_BUTTON_STYLE, Config.TOOLBAR_STYLE_LOGO)
        if not conf.get(Config.SHOW_TOP_TOOLBAR_BUTTON, True):
            toolbar_style = Config.TOOLBAR_STYLE_NONE
        idx = dialog.toolbar_style_combo.findData(toolbar_style)
        if idx >= 0:
            dialog.toolbar_style_combo.blockSignals(True)
            dialog.toolbar_style_combo.setCurrentIndex(idx)
            dialog.toolbar_style_combo.blockSignals(False)
        for _attr, _key in (
            ("chart_line_opacity_slider", Config.CHART_LINE_OPACITY),
            ("chart_bar_gradient_slider", Config.CHART_BAR_GRADIENT),
        ):
            _sl = getattr(dialog, _attr, None)
            if _sl is not None:
                _sl.blockSignals(True)
                _sl.setValue(int(conf.get(_key, 100)))
                _sl.blockSignals(False)
                _lbl = getattr(dialog, _attr.replace("slider", "lbl"), None)
                if _lbl is not None:
                    _lbl.setText(f"{_sl.value()}%")
        for _attr, _key in (
            ("chart_show_grid_check", Config.CHART_SHOW_GRID),
        ):
            _cb = getattr(dialog, _attr, None)
            if _cb is not None:
                _cb.blockSignals(True)
                _cb.setChecked(bool(conf.get(_key, True)))
                _cb.blockSignals(False)
        if hasattr(dialog, "toolbar_text_edit"):
            dialog.toolbar_text_edit.blockSignals(True)
            dialog.toolbar_text_edit.setText(str(conf.get(Config.TOOLBAR_BUTTON_TEXT, "Deep Dive") or ""))
            dialog.toolbar_text_edit.blockSignals(False)
        try:
            from .dialog_runtime_handlers import sync_toolbar_text_row

            sync_toolbar_text_row(dialog)
        except Exception:
            log_swallowed()

        dialog.side_view_check.blockSignals(True)
        dialog.side_view_check.setChecked(conf.get(Config.DETAILS_SIDE_VIEW, False))
        dialog.side_view_check.blockSignals(False)
        dialog.table_drawer_auto_check.blockSignals(True)
        dialog.table_drawer_auto_check.setChecked(conf.get(Config.DETAILS_TABLE_DRAWER_AUTO_CLOSE, True))
        dialog.table_drawer_auto_check.blockSignals(False)

        scope = str(conf.get(Config.ANIMATION_SCOPE, "all") or "all").strip().lower()
        if scope not in {"all", "no_pinned", "no_details", "none"}:
            scope = "all"
        idx_scope = dialog.animation_scope_combo.findData(scope)
        dialog.animation_scope_combo.blockSignals(True)
        dialog.animation_scope_combo.setCurrentIndex(max(0, idx_scope))
        dialog.animation_scope_combo.blockSignals(False)

        threshold = conf.get(Config.CHART_ANIMATION_VISIBLE_THRESHOLD, 6)
        try:
            threshold = max(1, min(24, int(threshold)))
        except Exception:
            threshold = 6
        dialog.chart_animation_threshold_spin.blockSignals(True)
        dialog.chart_animation_threshold_spin.setValue(threshold)
        dialog.chart_animation_threshold_spin.blockSignals(False)

        dialog.pinned_pos_top_cb.setChecked(conf.get(Config.PINNED_POSITION_TOP, True))
        dialog.pinned_pos_top_deck_cb.setChecked(conf.get(Config.PINNED_POSITION_TOP_DECK, False))
        _cb = getattr(dialog, "pinned_collapsible_cb", None)
        if _cb is not None:
            _cb.blockSignals(True)
            _cb.setChecked(bool(conf.get(Config.PINNED_CHARTS_COLLAPSIBLE, False)))
            _cb.blockSignals(False)
        for _attr, _key, _default in (
            ("pinned_margin_side_spin", Config.PINNED_MARGIN_SIDE, 20),
            ("pinned_margin_top_spin", Config.PINNED_MARGIN_TOP, 0),
            ("pinned_margin_bottom_spin", Config.PINNED_MARGIN_BOTTOM, 20),
        ):
            _spin = getattr(dialog, _attr, None)
            if _spin is not None:
                _spin.blockSignals(True)
                _spin.setValue(int(conf.get(_key, _default)))
                _spin.blockSignals(False)
        mode = dialog._get_pinned_theme_mode_from_config(conf)
        dialog.pinned_theme_mode_combo.blockSignals(True)
        idx_mode = dialog.pinned_theme_mode_combo.findData(mode)
        if idx_mode < 0:
            idx_mode = dialog.pinned_theme_mode_combo.findData("native")
        if idx_mode >= 0:
            dialog.pinned_theme_mode_combo.setCurrentIndex(idx_mode)
        dialog.pinned_theme_mode_combo.blockSignals(False)
        dialog._refresh_pinned_theme_controls()
        dialog._update_pinned_theme_controls_state()
        dialog._apply_pinned_theme_runtime(source="settings_load")
    finally:
        for control in base_controls:
            control.blockSignals(False)
        for checkbox, _key, _default in tab_bool_bindings:
            checkbox.blockSignals(False)

