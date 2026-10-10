# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
import time

from aqt.qt import QLayout, QRect, QSize, Qt

from ...animations.layout_animation import animate_widget_geometry

_MAX_STRETCH = 1.6  # a card never grows past 1.6x its natural height
_REF_COLS = 3  # the layout the card heights were designed for
_WIDTH_SCALE_EXP = 0.7  # how much a wider card gets taller (1.0 would keep the aspect ratio)
_WIDTH_SCALE_MAX = 3.0


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
        self.current_cols = 0
        self.on_cols_changed = None
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
        if running is not None and running.endValue() == target:
            return  # already sliding there: do not restart it on every layout pass
        animating = self.animate_moves or time.monotonic() < self._anim_until
        if widget and animating and was_placed and widget.isVisible():
            old = widget.geometry()
            if old.isValid() and old.width() > 0 and old != target:
                animate_widget_geometry(widget, old, target, self._anims, duration=260)
                return
        item.setGeometry(target)

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
                
                # For spanning items, heightForWidth needs to know the actual pixel width
                item_pixel_w = span * col_width + (span - 1) * spacing

                saved = bool(widget and getattr(widget, "_has_saved_height", False))
                if saved:
                    h = widget.minimumHeight()
                else:
                    h = item.heightForWidth(item_pixel_w) if item.hasHeightForWidth() else item.sizeHint().height()
                    if widget:
                        h = max(h, widget.minimumHeight())
                # Few cards per row (zoomed in) means wide cards: give them more height too,
                # otherwise they come out flat. Cards whose height already follows their
                # width (heatmap, card counts, anything with a height-for-width) are left as is.
                if widget and scale > 1.03 and getattr(widget, "widget_id", "") != "heatmap":
                    follows_width = False
                    if not saved and item.hasHeightForWidth() and ref_col_w > 0:
                        ref_w = span * ref_col_w + (span - 1) * spacing
                        follows_width = abs(item.heightForWidth(ref_w) - h) > 4
                    if not follows_width:
                        h = int(h * scale)

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

            if adaptive_heights:
                pass
            if dominant_heights:
                pass
        return row_h

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
        for ri, row in enumerate(rows):
            row_h = row_hs[ri] + extra[ri]

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
            
        return current_y - rect.y() - spacing + margin_b
