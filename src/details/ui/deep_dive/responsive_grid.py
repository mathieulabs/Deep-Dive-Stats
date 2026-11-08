# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
import time

from aqt.qt import QLayout, QRect, QSize, Qt

from ...animations.layout_animation import animate_widget_position

_MAX_STRETCH = 1.6  # a card never grows past 1.6x its natural height
_REF_COLS = 3  # the layout the card heights were designed for
_WIDTH_SCALE_EXP = 0.7  # how much a wider card gets taller (1.0 would keep the aspect ratio)
_WIDTH_SCALE_MAX = 3.0
# A card is at least 1/_ASPECT as tall as it is wide (the shape of a card at 4 per row), so
# with 3, 2 or 1 per row the wider cards are not flat strips; never taller than
# _MAX_VIEW_FRAC of the window's chart area (one card per row: a whole screen of one chart).
_ASPECT = 2.1
_MAX_VIEW_FRAC = 0.7
_MAX_H_NO_VIEW = 560
# A height set by hand is kept as a scale of the automatic height (_grid_height_factor on the
# card), so it follows the card's width when the number of charts per row changes; never
# below GRID_MIN_HEIGHT (unreadable charts, a cut heatmap).
GRID_MIN_HEIGHT = 170


class ResponsiveGridLayout(QLayout):
    """
    A responsive grid layout that shows 1, 2, or 3 columns based on width.
    Unlike MasonryLayout, it aligns items strictly in rows.
    """
    def __init__(self, parent=None, margin=0, spacing=10):
        super().__init__(parent)
        if parent is not None:
            self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)
        self.itemList = []
        self.preferred_columns = 3
        self.animate_moves = False
        self._hold = False
        self._held = {}  # widget: (where it was, where it goes) while the moves are held
        self._appearing = []  # cards shown while held (placed at once, see take_held)
        self._shown_last = set()  # the cards shown at the last layout pass
        self.current_cols = 0
        self.on_cols_changed = None
        # The free slots at the end of the last row, as (x, y, slot width, height, slots)
        # (the "Add Chart" spot shows there on hover), or None when the row is full.
        self.free_slot = None
        self._anim_until = 0.0
        self._anims = {}
        self._placed = set()
        self.fill_height = 0

    def set_fill_height(self, height):
        """Total height the grid should fill when its natural height is shorter (0: off)."""
        height = max(0, int(height or 0))
        if height != self.fill_height:
            self.fill_height = height
            self.invalidate()
            if self.parentWidget():
                self.parentWidget().updateGeometry()

    def animate_next(self, ms=450):
        """Animate the next layout passes (a card shown or hidden): neighbors slide to their new spot."""
        self._anim_until = time.monotonic() + ms / 1000.0
        self.invalidate()

    def set_animate_moves(self, enabled):
        self.animate_moves = enabled

    def move_item(self, from_idx, to_idx):
        if from_idx == to_idx:
            return
        if 0 <= from_idx < len(self.itemList) and 0 <= to_idx < len(self.itemList):
            item = self.itemList.pop(from_idx)
            self.itemList.insert(to_idx, item)
            self.invalidate()
            if self.parentWidget():
                self.parentWidget().update()

    def __del__(self):
        item = self.takeAt(0)
        while item:
            item = self.takeAt(0)

    def addItem(self, item):
        self.itemList.append(item)
        self.invalidate()

    def count(self):
        return len(self.itemList)

    def itemAt(self, index):
        if 0 <= index < len(self.itemList):
            return self.itemList[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self.itemList):
            item = self.itemList.pop(index)
            try:
                self.invalidate()
            except RuntimeError:
                pass
            return item
        return None

    def set_preferred_columns(self, count):
        count = max(1, min(4, count))
        if self.preferred_columns != count:
            self.preferred_columns = count
            self.invalidate()
            if self.parentWidget():
                self.parentWidget().updateGeometry()

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def invalidate(self):
        self._hfw_cache = {}
        super().invalidate()

    def heightForWidth(self, width):
        # sizeHint, minimumSize and the parent all ask for this; one pass per width until invalidated.
        cache = getattr(self, "_hfw_cache", None)
        if cache is None:
            cache = self._hfw_cache = {}
        h = cache.get(width)
        if h is None:
            if len(cache) > 32:
                cache.clear()  # window being dragged: one entry per pixel width
            h = cache[width] = self._do_layout(QRect(0, 0, width, 0), True)
        return h

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self):
        w = self.target_width()
        h = self.heightForWidth(w)
        return QSize(w, h)

    def minimumSize(self):
        if not self.itemList:
            return QSize(0, 0)
        # Allow shrinking horizontally by returning a small min width
        h = self.heightForWidth(self.target_width())
        return QSize(100, h)

    def _place(self, item, target):
        widget = item.widget()
        key = id(widget) if widget else None
        was_placed = key in self._placed
        if key is not None:
            self._placed.add(key)
        running = self._anims.get(widget) if widget else None
        if running is not None and getattr(running, "target_rect", None) == target:
            return  # already sliding there: do not restart it on every layout pass
        animating = self.animate_moves or time.monotonic() < self._anim_until
        if self._hold and widget is not None and widget.isVisible() and id(widget) not in self._shown_last:
            # Shown by the refresh: at its place at once.
            if widget not in self._appearing:
                self._appearing.append(widget)
            self._held.pop(widget, None)
            item.setGeometry(target)
            return
        if widget and animating and was_placed and widget.isVisible():
            old = widget.geometry()
            if self._hold:
                # Held (see hold_moves): stays where it is, slides once released.
                start = self._held.get(widget, (old, None))[0]
                self._held[widget] = (start, target)
                return
            if old.isValid() and old.width() > 0 and old != target:
                # Only the position slides (the size is set at once): resizing every card on
                # every frame re-laid and repainted all the charts, and Deep Dive lagged
                # whenever a deck or period change showed or hid a chart.
                animate_widget_position(widget, old, target, self._anims, duration=260)
                return
        item.setGeometry(target)

    def hold_moves(self):
        """The cards stay where they are until take_held() or release_moves(): a refresh of
        Deep Dive moves them once, with its charts' new data."""
        self._hold = True

    def take_held(self):
        """End the hold: ([(card, from, to)], [cards shown]); the caller puts the cards at
        their places (they are not moved yet)."""
        self._hold = False
        held, self._held = self._held, {}
        appearing, self._appearing = self._appearing, []
        moves = []
        for widget, (start, target) in held.items():
            if target is None:
                continue
            try:
                if widget.isVisible() and start.isValid() and start.width() > 0 and start != target:
                    moves.append((widget, start, target))
                else:
                    widget.setGeometry(target)
            except RuntimeError:
                pass
        return moves, [w for w in appearing if w not in [m[0] for m in moves]]

    def release_moves(self):
        self._hold = False
        self._appearing = []
        held, self._held = self._held, {}
        for widget, (start, target) in held.items():
            try:
                if target is None:
                    continue
                if widget.isVisible() and start.isValid() and start.width() > 0 and start != target:
                    animate_widget_position(widget, start, target, self._anims, duration=260)
                else:
                    widget.setGeometry(target)
            except RuntimeError:
                pass

    def target_width(self):
        if self.parentWidget():
            return self.parentWidget().width()
        return self.geometry().width() if self.geometry().width() > 0 else 800

    def _row_height(self, row, col_width, spacing, scale=1.0, ref_col_w=0):
        """Natural height of one row of cards."""
        # Row is collapsed ONLY if ALL visible items in it are collapsed
        all_collapsed = all(getattr(item.widget(), "is_collapsed", False) for item, span in row if item.widget())

        if all_collapsed:
            row_h = 40
        else:
            dominant_heights = []
            adaptive_heights = []

            for item, span in row:
                widget = item.widget()
                is_adaptive = False
                if widget and hasattr(widget, "widget_id"):
                    is_adaptive = widget.widget_id in ["heatmap", "card_counts"]
                h = self._card_height(item, widget, span, col_width, spacing, ref_col_w)

                if is_adaptive:
                    adaptive_heights.append(h)
                else:
                    dominant_heights.append(h)

            if dominant_heights:
                row_h = max(dominant_heights)
            elif adaptive_heights:
                row_h = max(adaptive_heights)
            else:
                row_h = 150

            max_required_min_h = max([item.widget().minimumHeight() for item, span in row if item.widget()] or [row_h])
            if row_h < max_required_min_h:
                row_h = max_required_min_h

        return row_h

    def _auto_height(self, item, widget, span, col_width, spacing, ref_col_w):
        """The card's height with nothing set by hand: its natural height, at least the
        height of its width (_ASPECT) when its height does not follow its width already."""
        item_pixel_w = span * col_width + (span - 1) * spacing
        h = item.heightForWidth(item_pixel_w) if item.hasHeightForWidth() else item.sizeHint().height()
        if widget:
            h = max(h, int(getattr(widget, "_grid_base_min_h", None) or widget.minimumHeight()))
        # Few cards per row (zoomed in) means wide cards: give them the height of their
        # width, otherwise they come out flat. Cards whose height already follows their
        # width (heatmap, card counts, anything with a height-for-width) are left as they are.
        if widget and getattr(widget, "widget_id", "") != "heatmap":
            follows_width = False
            if item.hasHeightForWidth() and ref_col_w > 0:
                ref_w = span * ref_col_w + (span - 1) * spacing
                follows_width = abs(item.heightForWidth(ref_w) - h) > 4
            if not follows_width:
                cap = int(self.fill_height * _MAX_VIEW_FRAC) if self.fill_height > 0 else _MAX_H_NO_VIEW
                h = max(h, min(int(item_pixel_w / _ASPECT), cap))
        return h

    def _card_height(self, item, widget, span, col_width, spacing, ref_col_w):
        factor = getattr(widget, "_grid_height_factor", None) if widget else None
        if factor:
            return max(GRID_MIN_HEIGHT, int(self._auto_height(item, widget, span, col_width, spacing, ref_col_w) * factor))
        if widget and getattr(widget, "_has_saved_height", False):
            return widget.minimumHeight()  # a height in pixels (saved before the scale)
        return self._auto_height(item, widget, span, col_width, spacing, ref_col_w)

    def _geometry_now(self):
        """(columns, column width, reference column width) of the current layout."""
        spacing = self.spacing()
        ml, _mt, mr, _mb = self.getContentsMargins()
        eff_width = self.geometry().width() - ml - mr
        num_cols = max(1, int(self.current_cols or self.preferred_columns or 1))
        col_width = (eff_width - (num_cols - 1) * spacing) // num_cols
        ref_cols = min(_REF_COLS, 1 if eff_width < 600 else 2 if eff_width < 1000 else 3)
        ref_col_w = (eff_width - (ref_cols - 1) * spacing) // ref_cols
        return num_cols, col_width, ref_col_w

    def auto_height_of(self, widget):
        """The automatic height of the card widget at the current layout (0 if not found)."""
        for item in self.itemList:
            if item.widget() is widget:
                num_cols, col_width, ref_col_w = self._geometry_now()
                span = max(1, min(num_cols, int(getattr(widget, "col_span", 1) or 1)))
                return self._auto_height(item, widget, span, col_width, self.spacing(), ref_col_w)
        return 0

    def _stretch_extra(self, rows, row_hs, spacing, margins):
        """Extra pixels per row so the cards fill fill_height when they would leave empty space."""
        zeros = [0] * len(rows)
        if self.fill_height <= 0 or not rows:
            return zeros
        natural = sum(row_hs) + spacing * (len(rows) - 1) + margins
        free = self.fill_height - natural
        if free <= 0:
            return zeros
        eligible = []
        for i, row in enumerate(rows):
            widgets = [item.widget() for item, _span in row if item.widget()]
            if all(getattr(w, "is_collapsed", False) for w in widgets):
                continue
            # A saved height is the card's floor, not a fixed size, so it may grow too.
            eligible.append(i)
        out = list(zeros)
        caps = {i: int(row_hs[i] * (_MAX_STRETCH - 1)) for i in eligible}
        left = free
        # Share the free space in proportion to row height; whatever a capped row cannot
        # take goes to the others.
        for _ in range(3):
            open_rows = [i for i in eligible if out[i] < caps[i]]
            base = sum(row_hs[i] for i in open_rows)
            if left <= 0 or base <= 0:
                break
            for i in open_rows:
                add = min(int(left * row_hs[i] / base), caps[i] - out[i])
                out[i] += add
            left = free - sum(out)
        return out

    def _do_layout(self, rect, test_only):
        if not self.itemList:
            return 0

        spacing = self.spacing()
        margin_l, margin_t, margin_r, margin_b = self.getContentsMargins()

        eff_width = rect.width() - margin_l - margin_r

        num_cols = self.preferred_columns

        if eff_width < 600:
            num_cols = min(num_cols, 1)
        elif eff_width < 1000:
            num_cols = min(num_cols, 2)
        elif eff_width < 1400:
            num_cols = min(num_cols, 3)

        if num_cols != self.current_cols:
            self.current_cols = num_cols
            if self.on_cols_changed:
                self.on_cols_changed(num_cols)

        col_width = (eff_width - (num_cols - 1) * spacing) // num_cols

        x = rect.x() + margin_l
        y = rect.y() + margin_t

        # Pass 1: group items into rows and determine each row height from col_span
        rows = []
        current_row = []
        slots_occupied = 0

        visible_items = []
        for item in self.itemList:
            w = item.widget()
            if w and w.isHidden():
                continue
            visible_items.append(item)

        for item in visible_items:
            widget = item.widget()
            span = getattr(widget, "col_span", 1) if widget else 1
            span = max(1, min(num_cols, span))

            if slots_occupied + span > num_cols:
                rows.append(current_row)
                current_row = []
                slots_occupied = 0

            current_row.append((item, span))
            slots_occupied += span

        if current_row:
            rows.append(current_row)

        ref_cols = min(_REF_COLS, 1 if eff_width < 600 else 2 if eff_width < 1000 else 3)
        ref_col_w = (eff_width - (ref_cols - 1) * spacing) // ref_cols
        scale = 1.0
        if ref_col_w > 0 and col_width > ref_col_w:
            scale = min(col_width / ref_col_w, _WIDTH_SCALE_MAX) ** _WIDTH_SCALE_EXP
        row_hs = [self._row_height(row, col_width, spacing, scale, ref_col_w) for row in rows]
        extra = self._stretch_extra(rows, row_hs, spacing, margin_t + margin_b)

        current_y = y
        if not test_only:
            self.free_slot = None
        for ri, row in enumerate(rows):
            row_h = row_hs[ri] + extra[ri]
            if not test_only and ri == len(rows) - 1:
                used = sum(span for _item, span in row)
                if used < num_cols:
                    self.free_slot = (x + used * (col_width + spacing), current_y, col_width, row_h, num_cols - used)

            if not test_only:
                current_slot = 0
                num_items_in_row = len(row)
                total_slots_occupied = sum(span for item, span in row)
                is_last_row = (row == rows[-1])

                for idx, (item, span) in enumerate(row):
                    visual_span = span
                    # If row has gaps and it's not the last row, expand the last item
                    if not is_last_row and idx == num_items_in_row - 1:
                        if total_slots_occupied < num_cols:
                            visual_span += (num_cols - total_slots_occupied)

                    item_x = x + current_slot * (col_width + spacing)
                    item_pixel_w = visual_span * col_width + (visual_span - 1) * spacing
                    target = QRect(item_x, current_y, item_pixel_w, row_h)
                    self._place(item, target)
                    current_slot += visual_span

            current_y += row_h + spacing

        if not test_only:
            shown = set()
            for item in visible_items:
                w = item.widget()
                if w is not None:
                    shown.add(id(w))
            self._shown_last = shown

        return current_y - rect.y() - spacing + margin_b
