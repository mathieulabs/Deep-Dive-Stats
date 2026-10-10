# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
import time

from ...pinned.drag_drop.constants import MIME_STAT_ID
from ...pinned.drag_drop.engine import ReorderEngine


def handle_drag_enter(container, event):
    if event.mimeData().hasFormat(MIME_STAT_ID):
        event.acceptProposedAction()
        container._drag_source_id = event.mimeData().data(MIME_STAT_ID).data().decode()


def handle_drag_move(container, event, *, throttle_s, on_shifted):
    if not event.mimeData().hasFormat(MIME_STAT_ID) or not container._drag_source_id:
        return

    event.acceptProposedAction()
    drop_pos = event.position().toPoint()

    # Over another line or box of the pinned stat cards: only show where it would land.
    from ...pinned.main_menu.ui.drag_move import stat_drag_over

    if stat_drag_over(container, drop_pos, container._drag_source_id):
        return

    now = time.time()
    if now - container._last_drag_move_time < float(throttle_s):
        return
    container._last_drag_move_time = now

    index_offset = 0
    for i in range(container.layout.count()):
        if container.layout.itemAt(i).widget():
            break
        index_offset += 1

    target_idx = ReorderEngine.get_linear_target_index(
        container.layout, drop_pos, container._drag_source_id, index_offset
    )

    source = ReorderEngine.get_source_widget(container.layout, container._drag_source_id)
    if source and ReorderEngine.shift_in_layout(container.layout, source, target_idx):
        on_shifted()


def handle_drop(container, event):
    if not event.mimeData().hasFormat(MIME_STAT_ID):
        return

    from ...pinned.main_menu.ui.drag_move import hide_marker, queue_move

    hide_marker(container)
    cross = getattr(container, "_drag_cross", None)
    if cross and cross.get("id") == container._drag_source_id:
        # Another line or box: applied once the drag has ended.
        queue_move(cross)
        container._drag_cross = None
        container._drag_source_id = None
        event.acceptProposedAction()
        return

    if any(getattr(c, "is_pinned", False) for c in container.cards):
        ReorderEngine.persist_reorder(container.layout, widget_type_group="stat_card")
    container.cards = ReorderEngine.sync_internal_list(container.layout, container.cards)

    parent = container.parentWidget()
    if parent and hasattr(parent, "on_stat_cards_reordered"):
        parent.on_stat_cards_reordered(container)

    container.update_layout(container.width(), animate=True)
    event.acceptProposedAction()
    container._drag_source_id = None
