# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from __future__ import annotations

from ... import Config


def reset_heatmap(dialog) -> None:
    if dialog.is_grid:
        reset_heatmap_grid(dialog)
    else:
        reset_heatmap_pinned(dialog)


def reset_heatmap_pinned(dialog) -> None:
    """Defaults for the pinned widget heatmap. The color is not reset here: it is in the
    Colors section, with its own reset button, like for the other charts."""
    defaults = Config.DEFAULT_CONFIG

    if hasattr(dialog, "scale_slider"):
        dialog.scale_slider.setValue(defaults.get(Config.HEATMAP_SCALE, 78))

    if hasattr(dialog, "nav_combo"):
        idx = dialog.nav_combo.findData(defaults.get(Config.HEATMAP_NAV_POS, "top_right"))
        if idx >= 0:
            dialog.nav_combo.setCurrentIndex(idx)

    if hasattr(dialog, "rounding_slider"):
        dialog.rounding_slider.setValue(defaults.get(Config.HEATMAP_ROUNDING, 30))
    if hasattr(dialog, "hide_title_cb"):
        dialog.hide_title_cb.setChecked(defaults.get(Config.HEATMAP_HIDE_TITLE, True))
    if hasattr(dialog, "hide_labels_cb"):
        dialog.hide_labels_cb.setChecked(defaults.get(Config.HEATMAP_HIDE_LABELS, True))
    if hasattr(dialog, "show_legend_cb"):
        dialog.show_legend_cb.setChecked(defaults.get(Config.HEATMAP_SHOW_LEGEND, True))

    if hasattr(dialog, "monday_first_cb"):
        dialog.monday_first_cb.setChecked(defaults.get(Config.HEATMAP_MONDAY_FIRST, False))
    if hasattr(dialog, "future_cb"):
        dialog.future_cb.setChecked(defaults.get(Config.HEATMAP_SHOW_FUTURE, True))
    if hasattr(dialog, "tinted_future_cb"):
        dialog.tinted_future_cb.setChecked(defaults.get(Config.HEATMAP_TINTED_FUTURE, False))
    if hasattr(dialog, "click_browser_cb"):
        dialog.click_browser_cb.setChecked(defaults.get(Config.HEATMAP_CLICK_BROWSER, True))

    if hasattr(dialog, "opacity_slider"):
        dialog.opacity_slider.setValue(defaults.get(Config.HEATMAP_EMPTY_OPACITY, 50))
    if hasattr(dialog, "filled_opacity_slider"):
        dialog.filled_opacity_slider.setValue(defaults.get(Config.HEATMAP_FILLED_OPACITY, 100))
    if hasattr(dialog, "vibrance_slider"):
        dialog.vibrance_slider.setValue(defaults.get(Config.HEATMAP_VIBRANCE, 100))
    if hasattr(dialog, "intensity_curve_slider"):
        dialog.intensity_curve_slider.setValue(defaults.get(Config.HEATMAP_INTENSITY_CURVE, 100))
    if hasattr(dialog, "hm_levels_slider"):
        dialog.hm_levels_slider.setValue(defaults.get(Config.HEATMAP_COLOR_LEVELS, 20))

    if hasattr(dialog, "hm_glass_cb"):
        dialog.hm_glass_cb.setChecked(defaults.get(Config.HEATMAP_SHOW_GLASS, False))
    if hasattr(dialog, "hm_int_slider"):
        dialog.hm_int_slider.setValue(defaults.get(Config.HEATMAP_GLASS_INTENSITY, 43))
    if hasattr(dialog, "hm_border_slider"):
        dialog.hm_border_slider.setValue(defaults.get(Config.HEATMAP_GLASS_BORDER, 0))

    if hasattr(dialog, "show_cont_cb"):
        dialog.show_cont_cb.setChecked(defaults.get(Config.HEATMAP_SHOW_CONTINUOUS_MODE, True))
    if hasattr(dialog, "show_365_cb"):
        dialog.show_365_cb.setChecked(defaults.get(Config.HEATMAP_SHOW_365_MODE, True))
    if hasattr(dialog, "show_year_cb"):
        dialog.show_year_cb.setChecked(defaults.get(Config.HEATMAP_SHOW_YEAR_MODE, True))
    if getattr(dialog, "hm_tooltip_checks", None):
        from ....widgets.chart_utils.tooltip_fields import set_checks
        set_checks(dialog.hm_tooltip_checks, defaults.get(Config.HEATMAP_TOOLTIP_HIDDEN, []))

    dialog.apply_live_changes()


def reset_heatmap_grid(dialog) -> None:
    """Defaults for the deep dive grid-embedded heatmap (the color too is left to the
    Colors section)."""
    if hasattr(dialog, "hide_labels_cb"):
        dialog.hide_labels_cb.setChecked(True)
    if hasattr(dialog, "show_legend_cb"):
        dialog.show_legend_cb.setChecked(True)

    if hasattr(dialog, "monday_first_cb"):
        dialog.monday_first_cb.setChecked(False)
    if hasattr(dialog, "future_cb"):
        dialog.future_cb.setChecked(True)
    if hasattr(dialog, "tinted_future_cb"):
        dialog.tinted_future_cb.setChecked(False)
    if hasattr(dialog, "click_browser_cb"):
        dialog.click_browser_cb.setChecked(True)

    if hasattr(dialog, "opacity_slider"):
        dialog.opacity_slider.setValue(50)
    if hasattr(dialog, "filled_opacity_slider"):
        dialog.filled_opacity_slider.setValue(100)
    if hasattr(dialog, "vibrance_slider"):
        dialog.vibrance_slider.setValue(100)
    if hasattr(dialog, "intensity_curve_slider"):
        dialog.intensity_curve_slider.setValue(100)
    if hasattr(dialog, "hm_levels_slider"):
        dialog.hm_levels_slider.setValue(20)

    if hasattr(dialog, "hm_glass_cb"):
        dialog.hm_glass_cb.setChecked(False)
    if hasattr(dialog, "hm_int_slider"):
        dialog.hm_int_slider.setValue(0)
    if hasattr(dialog, "hm_border_slider"):
        dialog.hm_border_slider.setValue(0)

    dialog.apply_live_changes()

