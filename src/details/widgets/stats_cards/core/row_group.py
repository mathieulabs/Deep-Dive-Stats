# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QFrame, QVBoxLayout, QSizePolicy, QTimer

from ..logic.row_state import (
    group_cards_by_row,
    apply_saved_order as apply_row_saved_order,
    collect_visible_unique_cards,
    normalize_row_nums,
    persist_row_nums,
    persist_dashboard_order,
)
from ..ui.sizing import PINNED_BASE_HEIGHT, normalize_scale_percent, scale_ratio_from_percent
from ..logic.constants import HEIGHT_REFRESH_DELAY_MS, ANIMATE_VISIBILITY_REFRESH_DELAY_MS
from .....qss import set_qss
from ....logic.logger import log_swallowed


class RowGroupedStatContainer(QFrame):
    """Wraps several StatCardsContainer rows so line breaks can be inserted between
    cards. Same API as StatCardsContainer.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        set_qss(self, "background: transparent; border: none;")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(0, 0, 0, 0)
        self._outer.setSpacing(4)

        self.cards = []
        self._row_nums = {}
        self._compact_mode = False
        self._compact_align = "center"
        self._scale_pct = 100
        self._on_visibility_changed = None

        self._rows = []
        self._ensure_rows(1)

    def _apply_row_runtime_options(self, row):
        row.set_compact_mode(self._compact_mode, self._compact_align)
        row.set_scale(self._scale_pct)
        if self._on_visibility_changed:
            row.set_visibility_callback(self._on_visibility_changed)

    def _ensure_rows(self, n):
        while len(self._rows) < n:
            from .container import StatCardsContainer

            row = StatCardsContainer(self)
            row.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            row.set_row_num_callbacks(
                num_fn=lambda key: self._row_nums.get(key, 0),
                change_fn=self._on_row_num_change,
            )
            self._apply_row_runtime_options(row)
            self._outer.addWidget(row)
            self._rows.append(row)

    def _schedule_height_refresh(self, delay_ms=HEIGHT_REFRESH_DELAY_MS):
        QTimer.singleShot(int(delay_ms), self._update_height)

    def _set_empty_state(self):
        for row in self._rows:
            row.clear_cards()
            row.hide()
        self.setFixedHeight(0)

    def _rebuild_row_groups(self):
        if not self.cards:
            self._set_empty_state()
            return

        groups_by_num = group_cards_by_row(self.cards, self._row_nums)
        max_num = max(groups_by_num.keys())
        num_rows = max_num + 1

        self._ensure_rows(num_rows)

        spacer_h = max(30, int(PINNED_BASE_HEIGHT * scale_ratio_from_percent(self._scale_pct)))
        for i in range(num_rows):
            row = self._rows[i]
            self._apply_row_runtime_options(row)
            group_cards = groups_by_num.get(i, [])
            if group_cards:
                row.set_cards(group_cards)
                row.show()
            else:
                row.clear_cards()
                row.setFixedHeight(spacer_h)
                row.show()

        for i in range(num_rows, len(self._rows)):
            self._rows[i].set_cards([])
            self._rows[i].hide()

        self._schedule_height_refresh()

    def _update_height(self):
        visible = [r for r in self._rows if r.isVisible()]
        if not visible:
            self.setFixedHeight(0)
            return
        total_h = sum(r.height() for r in visible)
        gaps = max(0, len(visible) - 1) * self._outer.spacing()
        self.setFixedHeight(total_h + gaps)

    def _on_row_num_change(self, key, delta):
        current = self._row_nums.get(key, 0)
        new_val = max(0, current + delta)
        if new_val == 0:
            self._row_nums.pop(key, None)
        else:
            self._row_nums[key] = new_val
        self._row_nums = normalize_row_nums(self._row_nums)
        self._save_row_nums()
        self._rebuild_row_groups()

    def _save_row_nums(self):
        try:
            persist_row_nums(self._row_nums, __name__)
        except Exception:
            log_swallowed()

    def _save_dashboard_order(self):
        if any(getattr(c, "is_pinned", False) for c in self.cards):
            return
        try:
            persist_dashboard_order(self.cards, __name__)
        except Exception:
            log_swallowed()

    def apply_saved_order(self, ordered_keys):
        if not ordered_keys:
            return
        self.cards = apply_row_saved_order(self.cards, ordered_keys)
        self._rebuild_row_groups()

    def on_stat_cards_reordered(self, _row):
        ordered = collect_visible_unique_cards(self._rows)
        if ordered:
            self.cards = ordered
            self._save_dashboard_order()

    def set_row_nums(self, nums_dict):
        self._row_nums = normalize_row_nums(nums_dict)
        self._rebuild_row_groups()

    def set_cards(self, new_cards, row_nums_by_id=None):
        self.cards = list(new_cards)
        if row_nums_by_id is not None:
            self._row_nums = normalize_row_nums(row_nums_by_id)
        self._rebuild_row_groups()

    def add_card(self, card):
        self.cards.append(card)
        self._rebuild_row_groups()

    def clear_cards(self):
        self.cards = []
        self._set_empty_state()

    def set_compact_mode(self, enabled, align="center"):
        self._compact_mode = enabled
        self._compact_align = align
        for row in self._rows:
            row.set_compact_mode(enabled, align)
        self._schedule_height_refresh()

    def set_scale(self, scale_pct):
        self._scale_pct = normalize_scale_percent(scale_pct)
        for row in self._rows:
            row.set_scale(self._scale_pct)
        self._schedule_height_refresh()

    def set_visibility_callback(self, callback):
        self._on_visibility_changed = callback
        for row in self._rows:
            row.set_visibility_callback(callback)

    def _iter_active_rows(self):
        for row in self._rows:
            if row.isVisible() and row.cards:
                yield row

    def update_layout(self, w, animate=False):
        for row in self._iter_active_rows():
            row.update_layout(w, animate)
        self._update_height()

    def trigger_layout_update(self):
        for row in self._rows:
            row.trigger_layout_update()
        self._schedule_height_refresh()

    def resizeEvent(self, event):
        if event:
            super().resizeEvent(event)
        w = self.width()
        for row in self._iter_active_rows():
            row.update_layout(w)
        self._update_height()

    def animate_visibility(self, visible):
        if visible:
            for row in self._rows:
                if row.cards:
                    row.show()
            if self._rows:
                self._rows[0].animate_visibility(True)
            self._schedule_height_refresh(ANIMATE_VISIBILITY_REFRESH_DELAY_MS)
        else:
            for row in self._rows:
                row.animate_visibility(False)
            self._schedule_height_refresh(ANIMATE_VISIBILITY_REFRESH_DELAY_MS)

    def set_scaling_lock(self, locked):
        for row in self._rows:
            row.set_scaling_lock(locked)

    def set_reduced_height_mode(self, enabled):
        for row in self._rows:
            if hasattr(row, "set_reduced_height_mode"):
                row.set_reduced_height_mode(enabled)
        self._schedule_height_refresh()
