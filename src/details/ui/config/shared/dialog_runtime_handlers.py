# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors

from __future__ import annotations

from aqt import mw

from ... import Config
from ... import ADAPTIVE_CHART_BINNING, CHART_BINNING_SCALE
from ....logic.logger import log_swallowed


def on_adaptive_binning_changed(dialog, state) -> None:
    try:
        from aqt.qt import Qt

        checked = state == Qt.CheckState.Checked.value
    except Exception:
        checked = bool(state)
    dialog.parent_dialog.addon_config.config[ADAPTIVE_CHART_BINNING] = checked
    try:
        dialog.parent_dialog.addon_config.set_value(ADAPTIVE_CHART_BINNING, checked)
    except Exception:
        log_swallowed()
    dialog._refresh_binning_live()


BINNING_SCALES = (50, 75, 100, 150, 200)
BINNING_LABELS = ("Much finer", "Finer", "Normal", "Coarser", "Much coarser")


def binning_index_from_scale(scale) -> int:
    try:
        s = int(scale)
    except Exception:
        s = 100
    return min(range(len(BINNING_SCALES)), key=lambda i: abs(BINNING_SCALES[i] - s))


def update_binning_scale_label(dialog, index: int) -> None:
    idx = max(0, min(len(BINNING_LABELS) - 1, int(index)))
    dialog.binning_scale_value_lbl.setText(BINNING_LABELS[idx])
    if hasattr(dialog, "binning_scale_reset_btn"):
        dialog.binning_scale_reset_btn.setVisible(idx != 2)


def on_binning_scale_changed(dialog, value: int) -> None:
    idx = max(0, min(len(BINNING_SCALES) - 1, int(value)))
    update_binning_scale_label(dialog, idx)
    scale = BINNING_SCALES[idx]
    dialog.parent_dialog.addon_config.config[CHART_BINNING_SCALE] = scale
    timer = getattr(dialog, "_binning_apply_timer", None)
    if timer is None:
        from aqt.qt import QTimer

        timer = QTimer(dialog)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: _apply_binning_scale(dialog))
        dialog._binning_apply_timer = timer
    timer.start(150)


def _apply_binning_scale(dialog) -> None:
    conf = dialog.parent_dialog.addon_config.config
    try:
        dialog.parent_dialog.addon_config.write_config_vals(
            {
                CHART_BINNING_SCALE: conf.get(CHART_BINNING_SCALE, 100),
            }
        )
    except Exception:
        log_swallowed()
    dialog._refresh_binning_live()


def on_side_view_changed(dialog, state) -> None:
    val = bool(state)
    dialog.parent_dialog.addon_config.config[Config.DETAILS_SIDE_VIEW] = val
    d = dialog.parent_dialog
    d.side_view = val

    if getattr(d, "layout_splitter", None) is not None:
        from ...dialog.lifecycle import apply_split_orientation, effective_side_view

        apply_split_orientation(d, effective_side_view(d))


def on_animation_scope_changed(dialog) -> None:
    scope = str(dialog.animation_scope_combo.currentData() or "all")
    dialog.parent_dialog.addon_config.config[Config.ANIMATION_SCOPE] = scope


def on_chart_animation_threshold_changed(dialog, value: int) -> None:
    dialog.parent_dialog.addon_config.config[Config.CHART_ANIMATION_VISIBLE_THRESHOLD] = max(1, min(24, int(value)))


def on_global_row_height_changed(dialog, value: int) -> None:
    dialog.parent_dialog.addon_config.config[Config.GLOBAL_ROW_HEIGHT] = value


def on_stats_precision_changed(dialog, value: int) -> None:
    dialog.parent_dialog.addon_config.config[Config.STATS_PRECISION] = value


def on_thousands_separator_changed(dialog, state) -> None:
    dialog.parent_dialog.addon_config.config[Config.USE_THOUSANDS_SEPARATOR] = bool(state)
    dialog.parent_dialog.update_dashboard_visibility()


def on_toolbar_button_style_changed(dialog) -> None:
    val = dialog.toolbar_style_combo.currentData()
    dialog.parent_dialog.addon_config.config[Config.TOOLBAR_BUTTON_STYLE] = val
    dialog.parent_dialog.addon_config.config[Config.SHOW_TOP_TOOLBAR_BUTTON] = (
        val != Config.TOOLBAR_STYLE_NONE
    )
    sync_toolbar_text_row(dialog)


def sync_toolbar_text_row(dialog) -> None:
    """Show the "Button Text" field only for the Text style."""
    edit = getattr(dialog, "toolbar_text_edit", None)
    form = getattr(dialog, "_toolbar_form", None)
    if edit is None:
        return
    show = dialog.toolbar_style_combo.currentData() == Config.TOOLBAR_STYLE_TEXT
    try:
        form.setRowVisible(edit, show)
    except Exception:
        edit.setVisible(show)
        label = form.labelForField(edit) if form is not None else None
        if label is not None:
            label.setVisible(show)


def save_and_close(dialog) -> None:
    # save_tabs_config already writes the whole config (global settings included).
    dialog.parent_dialog.save_tabs_config(dialog.tabs_data)
    try:
        from ..... import startup

        startup.apply_shortcut()
    except Exception:
        log_swallowed()
    mw.reset()
    try:
        mw.toolbar.draw()
    except Exception:
        log_swallowed()
    dialog._cancel_restored = True
    dialog.accept()

