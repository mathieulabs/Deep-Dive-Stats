# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
import time

from aqt.qt import QFrame, QRect, QVBoxLayout, QSizePolicy, QSpacerItem, QTimer, Qt

from ..logic.row_state import (
    card_key,
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
from .....i18n import tr
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
        # The space between two lines: a spacer above each line but the first, so each
        # one can have its own size (set_line_gaps).
        self._outer.setSpacing(0)
        self._line_gaps = {}
        self._spacers = []

        self.cards = []
        self._row_nums = {}
        self._compact_mode = False
        self._compact_align = "center"
        self._scale_pct = 100
        self._on_visibility_changed = None

        self._rows = []
        self._ensure_rows(1)
        self.setAcceptDrops(True)

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
            spacer = QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
            self._outer.addItem(spacer)
            self._spacers.append(spacer)
            self._outer.addWidget(row)
            self._rows.append(row)

    LINE_GAP = 4

    def set_line_gaps(self, gaps):
        """{line index: space under it}. True if it changed."""
        gaps = {int(k): int(v) for k, v in (gaps or {}).items()}
        if gaps == self._line_gaps:
            return False
        self._line_gaps = gaps
        self._apply_line_gaps()
        self._update_height()
        return True

    def _apply_line_gaps(self):
        """Size the spacer above each line: the space under the line shown before it."""
        prev = None
        changed = False
        opened = getattr(self, "_gap_open", None)
        for i, (row, spacer) in enumerate(zip(self._rows, self._spacers)):
            shown = not row.isHidden()
            h = self._line_gaps.get(prev, self.LINE_GAP) if (shown and prev is not None) else 0
            if shown and prev is not None and opened == ("under", prev):
                h = self.OPEN_GAP
            if spacer.sizeHint().height() != h:
                spacer.changeSize(0, h, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
                changed = True
            if shown:
                prev = i
        # Room above the first line / under the last one while a card is dragged there.
        top = self.OPEN_GAP if opened == ("top",) else 0
        bottom = self.OPEN_GAP if (opened is not None and opened == ("under", prev)) else 0
        m = self._outer.contentsMargins()
        if (m.top(), m.bottom()) != (top, bottom):
            self._outer.setContentsMargins(0, top, 0, bottom)
            changed = True
        if changed:
            self._outer.invalidate()

    # -- room for a new line while a card is dragged (Deep Dive) -------------------------

    OPEN_GAP = 22

    def _open_gap(self, where):
        """Open room at where (("under", line index) or ("top",)) for the new line bar, so
        it does not go over the cards. Closed again when the drag ends."""
        if getattr(self, "_gap_open", None) == where:
            return
        self._gap_open = where
        self._update_height()
        self._outer.activate()
        timer = getattr(self, "_gap_timer", None)
        if timer is None:
            timer = self._gap_timer = QTimer(self)
            timer.setInterval(150)
            timer.timeout.connect(self._close_gap_if_done)
        timer.start()

    # The opened room is part of this group, not of a line: a drop there lands here.
    def dragEnterEvent(self, event):
        if getattr(self, "_gap_open", None) is not None and self._is_card_drag(event):
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if getattr(self, "_gap_open", None) is None or not self._is_card_drag(event):
            return
        from ...pinned.main_menu.ui import drag_layout as gaps

        event.acceptProposedAction()
        gaps._seen[0] = time.monotonic()
        rect = getattr(self, "_gap_rect", None)
        if rect is not None:
            gaps.show_gap(self, rect, tr("New line"))

    def dropEvent(self, event):
        cross = getattr(self, "_gap_cross", None)
        if getattr(self, "_gap_open", None) is None or cross is None or not self._is_card_drag(event):
            return
        event.acceptProposedAction()
        QTimer.singleShot(0, lambda: self.drop_on_line(cross))

    @staticmethod
    def _is_card_drag(event):
        from ...pinned.drag_drop.constants import MIME_STAT_ID

        return event.mimeData().hasFormat(MIME_STAT_ID)

    def _close_gap(self):
        if getattr(self, "_gap_open", None) is None:
            return
        self._gap_open = None
        timer = getattr(self, "_gap_timer", None)
        if timer is not None:
            timer.stop()
        self._update_height()

    def _close_gap_if_done(self):
        from aqt.qt import QApplication

        if QApplication.mouseButtons() == Qt.MouseButton.NoButton:
            from ...pinned.main_menu.ui.drag_layout import hide_gaps

            hide_gaps()
            self._close_gap()

    def _schedule_height_refresh(self, delay_ms=HEIGHT_REFRESH_DELAY_MS):
        QTimer.singleShot(int(delay_ms), self._update_height)

    def _set_empty_state(self):
        for row in self._rows:
            row.clear_cards()
            row.hide()
        self.setFixedHeight(0)

    # Deep Dive: a line whose cards would shrink below this share of their natural width
    # is split in several lines of the same length instead.
    MIN_FIT = 0.8

    @staticmethod
    def _removed(card):
        """A card taken off the dashboard: it stays in the list, hidden on purpose (a card
        just built is hidden too until shown, but not on purpose)."""
        return card.isHidden() and card.testAttribute(Qt.WidgetAttribute.WA_WState_ExplicitShowHide)

    def _shown_cards(self):
        return [c for c in self.cards if not self._removed(c)]

    def _dense_row_nums(self):
        """The line numbers of the cards shown, without the empty lines between them (the
        cards of a line all removed: the lines under it move up). The removed cards keep
        theirs, for when they come back."""
        groups = group_cards_by_row(self._shown_cards(), self._row_nums)
        order = {num: i for i, num in enumerate(sorted(groups))}
        out = {k: v for k, v in normalize_row_nums(self._row_nums).items()
               if k not in {card_key(c) for c in self._shown_cards()}}
        for num, cards in groups.items():
            for card in cards:
                key = card_key(card)
                if key and order[num]:
                    out[key] = order[num]
        return out

    def _wrapped(self, cards):
        """The cards of one line, in as few lines as needed for them to keep a readable
        size at this width (balanced: 7 cards make 4 + 3). Pinned cards are not split."""
        width = self.width()
        if self._compact_mode or width <= 0 or len(cards) < 2:
            return [cards]
        spacing = 6
        ideal = [max(1, int(c.get_height_ideal_width())) for c in cards]
        allowed = width / self.MIN_FIT
        for n in range(1, len(cards) + 1):
            per = -(-len(cards) // n)
            chunks = [list(range(i, min(i + per, len(cards)))) for i in range(0, len(cards), per)]
            if all(sum(ideal[j] for j in ch) + spacing * (len(ch) - 1) <= allowed for ch in chunks):
                return [[cards[j] for j in ch] for ch in chunks]
        return [[c] for c in cards]

    def _lines(self):
        groups = group_cards_by_row(self._shown_cards(), self._dense_row_nums())
        lines = []
        self._line_nums = []  # the line number (as saved) of each line shown
        for num in sorted(groups):
            for part in self._wrapped(groups[num]):
                lines.append(part)
                self._line_nums.append(num)
        return lines or [[]]

    # -- drag to another line (Deep Dive) ----------------------------------------------

    def _card_by_key(self, key):
        return next((c for c in self.cards if card_key(c) == key), None)

    def drag_over_line(self, row, pos, source_id):
        """A card dragged over another line than its own: show where it lands (the line
        outlined, a bar at the spot). False when the line's own reorder handles it."""
        from ...pinned.main_menu.ui import drag_layout as gaps
        from ...pinned.main_menu.ui.drag_move import hide_marker, show_marker

        source = self._card_by_key(source_id)
        if self._compact_mode or source is None or row not in self._rows:
            return False
        index = self._rows.index(row)
        nums = getattr(self, "_line_nums", [])
        num = nums[index] if index < len(nums) else 0
        # Near the bottom edge of a line (or the top edge of the first one): a new line there.
        band = 14
        shown_rows = [r for r in self._rows if r.isVisible()]
        below = pos.y() >= row.height() - band
        above = bool(shown_rows) and row is shown_rows[0] and pos.y() <= band
        if below or above:
            hide_marker(row)
            row._drag_cross = {"id": source_id, "deep_dive": True, "newline": num + 1 if below else 0}
            self._open_gap(("under", index) if below else ("top",))
            g = row.geometry()
            half = self.OPEN_GAP // 2
            y = g.bottom() + 1 + half if below else g.top() - half
            self._gap_cross = dict(row._drag_cross)
            self._gap_rect = QRect(0, y - 2, self.width(), 4)
            gaps.show_gap(self, self._gap_rect, tr("New line"))
            gaps._seen[0] = time.monotonic()  # still in the drag (see drag_layout.drag_left)
            return True
        gaps.hide_gaps()
        self._close_gap()
        if source in row.cards:
            hide_marker(row)
            row._drag_cross = None
            return False
        shown = [c for c in row.cards if not self._removed(c)]
        anchor, bar_x = None, (shown[-1].geometry().right() + 3) if shown else row.width() // 2
        for card in shown:
            g = card.geometry()
            if pos.x() < g.center().x():
                anchor, bar_x = card, g.left() - 3
                break
        row._drag_cross = {
            "id": source_id, "deep_dive": True,
            "before": anchor, "after": shown[-1] if (anchor is None and shown) else None,
            "num": num,
        }
        show_marker(row, row.rect(), bar_x)
        return True

    def _new_line(self, source, new_num):
        """The card alone on a new line, numbered new_num (the lines from there move down)."""
        nums = self._dense_row_nums()
        key = card_key(source)
        shown_keys = {card_key(c) for c in self._shown_cards()}
        out = {}
        for k in shown_keys:
            if not k or k == key:
                continue
            n = nums.get(k, 0)
            if n >= new_num:
                n += 1
            if n:
                out[k] = n
        for k, n in nums.items():
            if k not in shown_keys and k != key:
                out[k] = n  # cards taken off the dashboard keep theirs
        if key and new_num:
            out[key] = new_num
        self._row_nums = out
        self._save_row_nums()
        self._rebuild_row_groups()

    def drop_on_line(self, cross):
        """The card dragged to another line goes there, at the spot shown."""
        from ...pinned.main_menu.ui.drag_layout import hide_gaps

        hide_gaps()
        self._close_gap()
        source = self._card_by_key(cross.get("id"))
        if source is None:
            return
        if "newline" in cross:
            self._new_line(source, int(cross["newline"]))
            return
        cards = [c for c in self.cards if c is not source]
        before, after = cross.get("before"), cross.get("after")
        if before in cards:
            cards.insert(cards.index(before), source)
        elif after in cards:
            cards.insert(cards.index(after) + 1, source)
        else:
            cards.append(source)
        self.cards = cards
        self._row_nums = self._dense_row_nums()
        key = card_key(source)
        if key:
            if cross.get("num"):
                self._row_nums[key] = int(cross["num"])
            else:
                self._row_nums.pop(key, None)
        self._save_row_nums()
        self._save_dashboard_order()
        self._rebuild_row_groups()

    def _lines_sig(self, lines):
        return tuple(tuple(id(c) for c in line) for line in lines)

    def _rebuild_row_groups(self):
        if not self.cards:
            self._set_empty_state()
            return

        if self._compact_mode:
            self._rebuild_pinned_rows()
            return
        lines = self._lines()
        self._wrap_sig = self._lines_sig(lines)
        # The removed cards go in the last line, hidden (they keep a parent, and come back
        # with the next rebuild when shown again).
        hidden = [c for c in self.cards if self._removed(c)]
        lines = [list(line) for line in lines]
        lines[-1] += hidden
        self._ensure_rows(len(lines))
        for row, line in zip(self._rows, lines):
            self._apply_row_runtime_options(row)
            row.set_cards(line)
            for card in hidden:
                if card in line:
                    card.setHidden(True)  # set_cards shows the cards it moves
            row.setVisible(any(not self._removed(c) for c in line))

        for i in range(len(lines), len(self._rows)):
            self._rows[i].set_cards([])
            self._rows[i].hide()

        self._schedule_height_refresh()

    def _rebuild_pinned_rows(self):
        """Main screen: the lines as the pinned layout numbers them (an empty one keeps its
        place while widgets are dragged between lines)."""
        groups_by_num = group_cards_by_row(self.cards, self._row_nums)
        num_rows = max(groups_by_num.keys()) + 1
        self._ensure_rows(num_rows)
        spacer_h = max(30, int(PINNED_BASE_HEIGHT * scale_ratio_from_percent(self._scale_pct)))
        for i in range(num_rows):
            row = self._rows[i]
            self._apply_row_runtime_options(row)
            group_cards = groups_by_num.get(i, [])
            if group_cards:
                row.set_cards(group_cards)
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
        self._apply_line_gaps()
        total_h = sum(r.height() for r in visible)
        gaps = sum(s.sizeHint().height() for r, s in zip(self._rows, self._spacers) if r.isVisible())
        m = self._outer.contentsMargins()
        self.setFixedHeight(total_h + gaps + m.top() + m.bottom())

    def _on_row_num_change(self, key, delta):
        if not self._compact_mode:
            self._row_nums = self._dense_row_nums()
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
        # Pinned: drops between the lines are the pinned area's (drag_layout).
        self.setAcceptDrops(not enabled)
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
        if self.cards and not self._compact_mode:
            if self._lines_sig(self._lines()) != getattr(self, "_wrap_sig", None):
                # More or fewer lines at this width, or a card removed or back.
                self._rebuild_row_groups()
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
