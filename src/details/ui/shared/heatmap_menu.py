# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Heatmap display options shared by the Deep Dive and pinned context menus."""
from aqt.qt import QAction

from .. import Config
from ...widgets.charts.heatmap.metrics import METRICS, TYPE_KEYS, TYPE_METRICS, build_metric, metric_parts


def apply_heatmap_display(heatmap, key, value):
    if heatmap is None:
        return
    if key == Config.HEATMAP_METRIC:
        heatmap.set_metric(value)
    elif key == Config.HEATMAP_INVERT_INTENSITY:
        heatmap.set_invert_intensity(bool(value))


def add_heatmap_display_actions(menu, cfg, on_change):
    """Add the "what the heatmap shows" submenu and the invert toggle.

    Several measures can be checked: each is scaled on its own and the cells show
    their average. on_change(config_key, value) saves the option and applies it.
    """
    chosen = set(metric_parts(cfg.get(Config.HEATMAP_METRIC, "reviews")) or ["reviews"])
    sub = menu.addMenu("Heatmap Shows")

    def add_checks(items):
        for key, label in items:
            act = QAction(label, sub)
            act.setCheckable(True)
            act.setChecked(key in chosen)
            act.triggered.connect(
                lambda _=False, k=key: on_change(Config.HEATMAP_METRIC, build_metric(chosen ^ {k}))
            )
            sub.addAction(act)

    hint = sub.addAction("Check several to combine them")
    hint.setEnabled(False)
    add_checks(METRICS)
    sub.addSeparator()
    header = sub.addAction("Card types")
    header.setEnabled(False)
    all_types = QAction("All card types", sub)
    all_types.setCheckable(True)
    all_types.setChecked(not (chosen & set(TYPE_KEYS)))
    all_types.triggered.connect(
        lambda _=False: on_change(Config.HEATMAP_METRIC, build_metric(chosen - set(TYPE_KEYS)))
    )
    sub.addAction(all_types)
    add_checks(TYPE_METRICS)

    inv = QAction("Invert Intensity", menu)
    inv.setCheckable(True)
    inv.setChecked(bool(cfg.get(Config.HEATMAP_INVERT_INTENSITY, False)))
    inv.triggered.connect(lambda checked=False: on_change(Config.HEATMAP_INVERT_INTENSITY, bool(checked)))
    menu.addAction(inv)
