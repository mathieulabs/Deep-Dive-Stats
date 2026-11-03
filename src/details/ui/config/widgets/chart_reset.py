# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from __future__ import annotations


def _box_defaults(dialog):
    """(intensity, border) defaults of the background box this dialog edits."""
    from ... import Config

    if getattr(dialog, "is_grid", False):
        grid = Config.DEFAULT_CONFIG.get(Config.DEEP_DIVE_GRID_STYLE, {}) or {}
        return grid.get(Config.PINNED_GLASS_INTENSITY, 4), grid.get(Config.PINNED_GLASS_BORDER, 50)
    d = Config.DEFAULT_CONFIG
    if getattr(dialog, "type", None) == "text_label":
        return d.get(Config.TEXT_WIDGET_GLASS_INTENSITY, Config.DEFAULT_CONFIG[Config.TEXT_WIDGET_GLASS_INTENSITY]), d.get(Config.TEXT_WIDGET_GLASS_BORDER, 50)
    return d.get(Config.PINNED_GLASS_INTENSITY, Config.DEFAULT_CONFIG[Config.PINNED_GLASS_INTENSITY]), d.get(Config.PINNED_GLASS_BORDER, 34)


def reset_chart_settings(dialog) -> None:
    intensity, border = _box_defaults(dialog)
    if hasattr(dialog, "glass_cb"):
        dialog.glass_cb.setChecked(True)
    if hasattr(dialog, "int_slider"):
        dialog.int_slider.setValue(int(intensity))
    if hasattr(dialog, "border_slider"):
        dialog.border_slider.setValue(int(border))
    if hasattr(dialog, "hover_border_cb"):
        dialog.hover_border_cb.setChecked(True)
    if hasattr(dialog, "avg_cb"):
        dialog.avg_cb.setChecked(True)
    if hasattr(dialog, "cum_cb"):
        dialog.cum_cb.setChecked(True)
    if hasattr(dialog, "chart_opacity_slider"):
        opacity_defaults = {"card_counts": 100, "distribution": 100, "retention": 100}
        dialog.chart_opacity_slider.setValue(opacity_defaults.get(dialog.type, 100))
    if hasattr(dialog, "show_legend_cb"):
        dialog.show_legend_cb.setChecked(True)
    if hasattr(dialog, "legend_mode_combo"):
        dialog.legend_mode_combo.setCurrentIndex(max(0, dialog.legend_mode_combo.findData("auto")))
    if getattr(dialog, "tooltip_checks", None):
        from ....widgets.chart_utils.tooltip_fields import set_checks
        set_checks(dialog.tooltip_checks, [])
    if hasattr(dialog, "line_opacity_slider"):
        dialog.line_opacity_slider.setValue(int(dialog.addon_config.get("Chart_Line_Opacity", 80)))
    if hasattr(dialog, "bar_gradient_slider"):
        dialog.bar_gradient_slider.setValue(int(dialog.addon_config.get("Chart_Bar_Gradient", 43)))
    for _i, _combo in enumerate(getattr(dialog, "range_btn_combos", []) or []):
        if getattr(dialog, "range_btn_key", "") == "filter_modes":
            from ....widgets.common.fsrs_filters import FSRS_FILTER_MODES as _DEFAULT
        else:
            from ....widgets.common.future_due_filters import FUTURE_DUE_DEFAULT_DAYS as _DEFAULT
        _combo.set_value(_DEFAULT[_i])
    for _attr, _conf_key in (
        ("show_grid_cb", "Chart_Show_Grid"),
    ):
        if hasattr(dialog, _attr):
            getattr(dialog, _attr).setChecked(bool(dialog.addon_config.get(_conf_key, True)))
    dialog.apply_live_changes()

