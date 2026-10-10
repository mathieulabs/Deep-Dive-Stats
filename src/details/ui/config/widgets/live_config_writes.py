# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from __future__ import annotations

from ... import Config


def _write_box_style(conf, *, show_key, intensity_key, border_key, dialog):
    conf[show_key] = dialog.glass_cb.isChecked()
    conf[intensity_key] = dialog.int_slider.value()
    conf[border_key] = dialog.border_slider.value()
    if hasattr(dialog, "hover_border_cb"):
        hover_key = (
            Config.TEXT_WIDGET_HOVER_BORDER if show_key == Config.TEXT_WIDGET_SHOW_GLASS else Config.PINNED_HOVER_BORDER
        )
        conf[hover_key] = dialog.hover_border_cb.isChecked()


def apply_stat_card_live_changes(dialog, conf):
    conf[dialog._get_key(Config.FACECARDS_SCALE, Config.DASHBOARD_SCALE)] = dialog.scale_spin.value()
    if hasattr(dialog, "title_size_slider"):
        conf[dialog._get_key(Config.FACECARDS_TITLE_SIZE, Config.DASHBOARD_TITLE_SIZE)] = dialog.title_size_slider.value()
    if hasattr(dialog, "title_color"):
        conf[dialog._get_key(Config.FACECARDS_TITLE_COLOR, Config.DASHBOARD_TITLE_COLOR)] = dialog.title_color
    if hasattr(dialog, "glass_cb"):
        conf[dialog._get_key(Config.FACECARDS_SHOW_GLASS, Config.DASHBOARD_SHOW_GLASS)] = dialog.glass_cb.isChecked()
    conf[dialog._get_key(Config.FACECARDS_GLASS_INTENSITY, Config.DASHBOARD_GLASS_INTENSITY)] = dialog.face_int_slider.value()
    conf[dialog._get_key(Config.FACECARDS_GLASS_BORDER, Config.DASHBOARD_GLASS_BORDER)] = dialog.face_border_slider.value()
    if hasattr(dialog, "hover_effect_cb"):
        conf[dialog._get_key(Config.FACECARDS_HOVER_EFFECT, Config.DASHBOARD_HOVER_EFFECT)] = dialog.hover_effect_cb.isChecked()
    if hasattr(dialog, "inline_stats_cb"):
        conf[dialog._get_key(Config.FACECARDS_INLINE_STATS, Config.DASHBOARD_INLINE_STATS)] = dialog.inline_stats_cb.isChecked()
    conf[dialog._get_key(Config.FACECARDS_TITLE_SHADOW_INTENSITY, Config.DASHBOARD_TITLE_SHADOW_INTENSITY)] = dialog.tshad_slider.value()
    conf[dialog._get_key(Config.FACECARDS_STAT_SHADOW_INTENSITY, Config.DASHBOARD_STAT_SHADOW_INTENSITY)] = dialog.sshad_slider.value()
    if dialog.is_dashboard_context:
        labels_conf = dialog.global_config if isinstance(dialog.global_config, dict) else conf
        labels_map = labels_conf.get(Config.DASH_STAT_LABELS, {})
        if not isinstance(labels_map, dict):
            labels_map = {}
        stat_key = dialog.widget_def.get("stat_key")
        if stat_key:
            label_val = (dialog.label_edit.text() or "").strip()
            default_label = dialog._get_default_label().strip()
            if label_val and label_val != default_label:
                labels_map[str(stat_key)] = label_val
            else:
                labels_map.pop(str(stat_key), None)
            labels_conf[Config.DASH_STAT_LABELS] = labels_map


def apply_heatmap_live_changes(dialog, conf):
    prev_nav = conf.get(Config.HEATMAP_NAV_POS, "top_right")
    if hasattr(dialog, "scale_slider"):
        conf[Config.HEATMAP_SCALE] = dialog.scale_slider.value()
    if hasattr(dialog, "nav_combo"):
        conf[Config.HEATMAP_NAV_POS] = dialog.nav_combo.currentData()
    if hasattr(dialog, "hide_title_cb"):
        conf[Config.HEATMAP_HIDE_TITLE] = dialog.hide_title_cb.isChecked()
    if hasattr(dialog, "hide_labels_cb"):
        conf[Config.HEATMAP_HIDE_LABELS] = dialog.hide_labels_cb.isChecked()
    if hasattr(dialog, "show_legend_cb"):
        conf[Config.HEATMAP_SHOW_LEGEND] = dialog.show_legend_cb.isChecked()
    if hasattr(dialog, "future_cb"):
        conf[Config.HEATMAP_SHOW_FUTURE] = dialog.future_cb.isChecked()
    if hasattr(dialog, "tinted_future_cb"):
        conf[Config.HEATMAP_TINTED_FUTURE] = dialog.tinted_future_cb.isChecked()
    if hasattr(dialog, "rounding_slider"):
        conf[Config.HEATMAP_ROUNDING] = dialog.rounding_slider.value()
    if hasattr(dialog, "monday_first_cb"):
        conf[Config.HEATMAP_MONDAY_FIRST] = dialog.monday_first_cb.isChecked()
    if (
        getattr(dialog, "is_pinned_mode", False)
        and hasattr(dialog, "_is_pinned_separate_theme_mode")
        and dialog._is_pinned_separate_theme_mode()
    ):
        if hasattr(dialog, "_set_pinned_separate_data_color_override"):
            dialog._set_pinned_separate_data_color_override(Config.HEATMAP_COLOR, dialog.current_color)
        else:
            conf[Config.HEATMAP_COLOR] = dialog.current_color
    else:
        conf[Config.HEATMAP_COLOR] = dialog.current_color
    if hasattr(dialog, "opacity_slider"):
        conf[Config.HEATMAP_EMPTY_OPACITY] = dialog.opacity_slider.value()
    if hasattr(dialog, "filled_opacity_slider"):
        conf[Config.HEATMAP_FILLED_OPACITY] = dialog.filled_opacity_slider.value()
    if hasattr(dialog, "vibrance_slider"):
        conf[Config.HEATMAP_VIBRANCE] = dialog.vibrance_slider.value()
    if hasattr(dialog, "intensity_curve_slider"):
        conf[Config.HEATMAP_INTENSITY_CURVE] = dialog.intensity_curve_slider.value()
    if hasattr(dialog, "hm_levels_slider"):
        conf[Config.HEATMAP_COLOR_LEVELS] = dialog.hm_levels_slider.value()
    if hasattr(dialog, "click_browser_cb"):
        conf[Config.HEATMAP_CLICK_BROWSER] = dialog.click_browser_cb.isChecked()
    if hasattr(dialog, "hm_glass_cb"):
        conf[Config.HEATMAP_SHOW_GLASS] = dialog.hm_glass_cb.isChecked()
    if hasattr(dialog, "hm_int_slider"):
        conf[Config.HEATMAP_GLASS_INTENSITY] = dialog.hm_int_slider.value()
    if hasattr(dialog, "hm_border_slider"):
        conf[Config.HEATMAP_GLASS_BORDER] = dialog.hm_border_slider.value()
    if hasattr(dialog, "show_cont_cb"):
        conf[Config.HEATMAP_SHOW_CONTINUOUS_MODE] = dialog.show_cont_cb.isChecked()
    if hasattr(dialog, "show_365_cb"):
        conf[Config.HEATMAP_SHOW_365_MODE] = dialog.show_365_cb.isChecked()
    if hasattr(dialog, "show_year_cb"):
        conf[Config.HEATMAP_SHOW_YEAR_MODE] = dialog.show_year_cb.isChecked()
    if getattr(dialog, "hm_tooltip_checks", None):
        from ....widgets.chart_utils.tooltip_fields import hidden_from_checks
        conf[Config.HEATMAP_TOOLTIP_HIDDEN] = hidden_from_checks(dialog.hm_tooltip_checks)
    dialog._heatmap_requires_structure_refresh = (
        hasattr(dialog, "nav_combo")
        and prev_nav != conf.get(Config.HEATMAP_NAV_POS, "top_right")
    )


def apply_activity_live_changes(dialog, conf):
    if hasattr(dialog, "avg_cb"):
        dialog.widget_def["show_average"] = dialog.avg_cb.isChecked()
    if hasattr(dialog, "cum_cb"):
        dialog.widget_def["show_cumulative"] = dialog.cum_cb.isChecked()
    _write_box_style(
        conf,
        show_key=Config.PINNED_GLASS,
        intensity_key=Config.PINNED_GLASS_INTENSITY,
        border_key=Config.PINNED_GLASS_BORDER,
        dialog=dialog,
    )


def apply_generic_chart_live_changes(dialog, conf):
    _write_box_style(
        conf,
        show_key=Config.PINNED_GLASS,
        intensity_key=Config.PINNED_GLASS_INTENSITY,
        border_key=Config.PINNED_GLASS_BORDER,
        dialog=dialog,
    )


def apply_text_label_live_changes(dialog, conf):
    _write_box_style(
        conf,
        show_key=Config.TEXT_WIDGET_SHOW_GLASS,
        intensity_key=Config.TEXT_WIDGET_GLASS_INTENSITY,
        border_key=Config.TEXT_WIDGET_GLASS_BORDER,
        dialog=dialog,
    )


def apply_chart_opacity_live_change(dialog):
    _legend_cb = getattr(dialog, "show_legend_cb", None)
    if _legend_cb is not None:
        dialog.widget_def["show_legend"] = bool(_legend_cb.isChecked())
        dialog.local_config["show_legend"] = bool(_legend_cb.isChecked())
    _tip_checks = getattr(dialog, "tooltip_checks", None)
    if _tip_checks:
        from ....widgets.chart_utils.tooltip_fields import hidden_from_checks
        _hidden = hidden_from_checks(_tip_checks)
        if _hidden:
            dialog.widget_def["tooltip_hidden"] = _hidden
            dialog.local_config["tooltip_hidden"] = _hidden
        else:
            dialog.widget_def.pop("tooltip_hidden", None)
            dialog.local_config.pop("tooltip_hidden", None)
    _mode_combo = getattr(dialog, "legend_mode_combo", None)
    if _mode_combo is not None:
        _mode = _mode_combo.currentData() or "auto"
        if _mode == "auto":
            dialog.widget_def.pop("legend_mode", None)
            dialog.local_config.pop("legend_mode", None)
        else:
            dialog.widget_def["legend_mode"] = _mode
            dialog.local_config["legend_mode"] = _mode
    if hasattr(dialog, "chart_opacity_slider"):
        value = dialog.chart_opacity_slider.value()
        dialog.widget_def["chart_opacity"] = value
        dialog.local_config["chart_opacity"] = value
    _range_combos = getattr(dialog, "range_btn_combos", None)
    if _range_combos:
        _key = getattr(dialog, "range_btn_key", "radio_ranges")
        _vals = [c.currentData() for c in _range_combos]
        if _key == "filter_modes":
            from ....widgets.common.fsrs_filters import FSRS_FILTER_MODES as _DEFAULT, normalize_fsrs_filter_modes as _normalize
        else:
            from ....widgets.common.future_due_filters import FUTURE_DUE_DEFAULT_DAYS as _DEFAULT, normalize_future_due_days as _normalize
        _norm = _normalize(_vals)
        # Duplicates fall back to the defaults, so only a valid set is stored.
        if len(set(_vals)) < 4 or tuple(_norm) == tuple(_DEFAULT):
            dialog.widget_def.pop(_key, None)
            dialog.local_config.pop(_key, None)
        else:
            dialog.widget_def[_key] = list(_norm)
            dialog.local_config[_key] = list(_norm)
    # Per-chart line / bar-gradient overrides: only stored when they differ from the global
    # "Chart Style" value, so charts keep following the global setting otherwise.
    for _attr, _key, _conf_key in (
        ("line_opacity_slider", "line_opacity", "Chart_Line_Opacity"),
        ("bar_gradient_slider", "bar_gradient", "Chart_Bar_Gradient"),
    ):
        _slider = getattr(dialog, _attr, None)
        if _slider is None:
            continue
        _value = _slider.value()
        try:
            _global = int(dialog.addon_config.get(_conf_key, 100))
        except Exception:
            _global = 100
        if _value == _global:
            dialog.widget_def.pop(_key, None)
            dialog.local_config.pop(_key, None)
        else:
            dialog.widget_def[_key] = _value
            dialog.local_config[_key] = _value
    for _attr, _key, _conf_key in (
        ("show_grid_cb", "show_grid", Config.CHART_SHOW_GRID),
    ):
        _cb = getattr(dialog, _attr, None)
        if _cb is None:
            continue
        _value = bool(_cb.isChecked())
        if _value == bool(dialog.addon_config.get(_conf_key, True)):
            dialog.widget_def.pop(_key, None)
            dialog.local_config.pop(_key, None)
        else:
            dialog.widget_def[_key] = _value
            dialog.local_config[_key] = _value

