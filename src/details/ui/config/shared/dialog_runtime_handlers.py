# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors

from __future__ import annotations

from aqt import mw

from ... import Config
from ... import ADAPTIVE_CHART_BINNING, CHART_BINNING_SCALE
from ....logic.logger import log_swallowed
from .....i18n import N_, tr_name


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
BINNING_LABELS = (N_("Much finer"), N_("Finer"), N_("Normal"), N_("Coarser"), N_("Much coarser"))


def binning_index_from_scale(scale) -> int:
    try:
        s = int(scale)
    except Exception:
        s = 100
    return min(range(len(BINNING_SCALES)), key=lambda i: abs(BINNING_SCALES[i] - s))


def update_binning_scale_label(dialog, index: int) -> None:
    idx = max(0, min(len(BINNING_LABELS) - 1, int(index)))
    dialog.binning_scale_value_lbl.setText(tr_name(BINNING_LABELS[idx]))
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
    sync_animation_controls(dialog)


def sync_animation_controls(dialog) -> None:
    """The animation settings that cannot apply under the chosen Animation Mode greyed out
    (the Deep Dive transitions when its animations are off, and so on)."""
    scope = str(dialog.animation_scope_combo.currentData() or "all")
    details_on = scope in ("all", "no_pinned")
    pinned_on = scope in ("all", "no_details")
    any_on = scope != "none"
    for name, on in (
        ("transition_style_combo", details_on),
        ("pinned_transition_style_combo", pinned_on),
        ("appear_animation_check", any_on),
        ("zoom_animation_check", any_on),
        ("chart_animation_threshold_spin", any_on),
    ):
        w = getattr(dialog, name, None)
        if w is None:
            continue
        w.setEnabled(on)
        try:
            label = w.parentWidget().layout().labelForField(w)
            if label is not None:
                label.setEnabled(on)
        except Exception:
            pass


def on_transition_style_changed(dialog) -> None:
    style = str(dialog.transition_style_combo.currentData() or "morph")
    dialog.parent_dialog.addon_config.config[Config.DEEP_DIVE_TRANSITION_STYLE] = style


def on_pinned_transition_style_changed(dialog) -> None:
    style = str(dialog.pinned_transition_style_combo.currentData() or "morph")
    dialog.parent_dialog.addon_config.config[Config.PINNED_TRANSITION_STYLE] = style


def on_appear_animation_changed(dialog, state) -> None:
    dialog.parent_dialog.addon_config.config[Config.CHART_APPEAR_ANIMATION] = bool(state)


def on_zoom_animation_changed(dialog, state) -> None:
    dialog.parent_dialog.addon_config.config[Config.ZOOM_ANIMATION] = bool(state)


def on_chart_animation_threshold_changed(dialog, value: int) -> None:
    dialog.parent_dialog.addon_config.config[Config.CHART_ANIMATION_VISIBLE_THRESHOLD] = max(1, min(24, int(value)))


def on_global_row_height_changed(dialog, value: int) -> None:
    dialog.parent_dialog.addon_config.config[Config.GLOBAL_ROW_HEIGHT] = value


def on_stats_precision_changed(dialog, value: int) -> None:
    dialog.parent_dialog.addon_config.config[Config.STATS_PRECISION] = value


def on_thousands_separator_changed(dialog, state) -> None:
    dialog.parent_dialog.addon_config.config[Config.USE_THOUSANDS_SEPARATOR] = bool(state)
    dialog.parent_dialog.update_dashboard_visibility()


def on_chart_help_changed(dialog, state) -> None:
    """The "?" next to chart titles (widgets.common.chart_help): shown on the next build of the
    charts (closing the settings rebuilds them)."""
    dialog.parent_dialog.addon_config.config[Config.SHOW_CHART_HELP] = bool(state)
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

