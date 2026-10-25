# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors

from aqt.qt import QSizePolicy, QWidget, QVBoxLayout as _QVBoxLayout

from ......qss import set_qss
from ..constants import CHART_SPACING


def prepare_charts_layout(
    manager,
    other_defs,
    pinned_conf,
    should_full_rebuild,
    should_animate_chart_reflow,
    overview_light_mode,
    review_return_light_mode,
    review_return_phase_b_mode,
    non_blocking_update,
    deck_id,
):
    if not isinstance(getattr(manager, "_chart_boxes", None), dict):
        manager._chart_boxes = {}

    if not manager._charts_container:
        manager._charts_container = QWidget(manager._overlay)
        set_qss(manager._charts_container, "background: transparent;")
        manager._charts_container.setAcceptDrops(True)
        manager._charts_container.installEventFilter(manager)
        manager._charts_container.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        manager._charts_vbox = _QVBoxLayout(manager._charts_container)
        manager._charts_vbox.setContentsMargins(0, 0, 0, 0)
        manager._charts_vbox.setSpacing(CHART_SPACING)
        manager._chart_masonry_rows = []
        manager._masonry_layout = None

    manager._chart_boxes[0] = {
        "container": manager._charts_container,
        "vbox": manager._charts_vbox,
        "rows": manager._chart_masonry_rows,
        "masonry": manager._masonry_layout,
    }

    if not should_full_rebuild:
        masonry_expected_ids = {d.get("id") for d in other_defs}
        pruned = manager._prune_chart_rows(masonry_expected_ids)
        reflow_pruned = int(pruned or 0)
    else:
        reflow_pruned = 0

    if should_animate_chart_reflow:
        manager._schedule_chart_reflow_animation(pruned_count=reflow_pruned)

    if should_full_rebuild:
        for box_id, box in sorted(manager._chart_boxes.items(), key=lambda kv: kv[0]):
            rows = box.get("rows", [])
            for row_w, row_ml in rows:
                row_ml.clear_items()
                row_w.hide()
            vbox = box.get("vbox")
            while vbox and vbox.count():
                vbox.takeAt(0)
            box["rows"] = []
            box["masonry"] = None
            if box_id != 0:
                container = box.get("container")
                if container is not None:
                    container.hide()

        manager._chart_masonry_rows = manager._chart_boxes[0]["rows"]
        manager._masonry_layout = manager._chart_boxes[0]["masonry"]

    charts_exist = False
    widget_index = 0

    if overview_light_mode:
        overview_sync_budget = 0
    elif review_return_light_mode:
        overview_sync_budget = 0 if review_return_phase_b_mode else (2 if non_blocking_update else 1)
    else:
        overview_sync_budget = 999

    return charts_exist, widget_index, overview_sync_budget



