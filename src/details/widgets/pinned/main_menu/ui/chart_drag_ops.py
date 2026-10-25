# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors

import time

from ...drag_drop.engine import ReorderEngine


def handle_chart_move(manager, drop_pos):
    if not manager._masonry_layout or not getattr(manager, "_drag_source_id", None):
        return

    now = time.time()
    if now - manager._last_drag_move_time < 0.02:
        return
    manager._last_drag_move_time = now

    target_idx = ReorderEngine.get_grid_target_index(
        manager._masonry_layout, drop_pos, manager._drag_source_id
    )

    source = ReorderEngine.get_source_widget(manager._masonry_layout, manager._drag_source_id)
    if source:
        manager._masonry_layout.move_item(manager._masonry_layout.indexOf(source), target_idx)


def finalize_chart_reorder(manager):
    if not manager._masonry_layout:
        return

    widget_type_group = "chart"
    try:
        parent = manager._masonry_layout.parentWidget() if manager._masonry_layout is not None else None
        box_parent = parent.parentWidget() if parent is not None else None
        box_kind = str(box_parent.property("deepdivestats_box_kind") or "chart") if box_parent is not None else "chart"
        if box_kind == "text":
            widget_type_group = "text_label"
    except Exception:
        widget_type_group = "chart"

    ReorderEngine.persist_reorder(manager._masonry_layout, widget_type_group=widget_type_group)
    manager.sync_overlay()


def end_chart_drag(manager, accepted):
    """Called when a chart drag ends. A drop already persisted everything; a cancelled
    or out-of-box drop leaves the live order changed, so rebuild from the saved order."""
    drag_id = getattr(manager, "_drag_source_id", None)
    manager._drag_source_id = None
    manager._set_chart_rows_animate_moves(False)
    if not accepted and drag_id:
        manager.refresh(clear_cache=False)
