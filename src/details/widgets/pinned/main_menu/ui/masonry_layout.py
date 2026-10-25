# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QLayout, QRect, QSize, QSizePolicy, Qt
from ....common.row_projection import project_row_positions
from ..imports import animate_widget_geometry, animations_enabled
from .....logic.logger import log_swallowed

class MasonryLayout(QLayout):
    def __init__(self, parent=None, margin=0, spacing=-1, min_column_width=420, centered=True):
        super().__init__(parent)
        if parent is not None:
            self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)
        self.spacing()
        self.min_column_width = min_column_width
        self.centered = centered
        self.itemList = []
        self._animations = {}
        self._animate_moves = False
        self._last_animated_targets = {}

    def clear_items(self):
        self.itemList = []
        self.invalidate()

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
            return self.itemList.pop(index)
        return None

    def move_item(self, source_idx, target_idx):
        if 0 <= source_idx < len(self.itemList) and 0 <= target_idx < len(self.itemList):
            if source_idx == target_idx:
                return
            item = self.itemList.pop(source_idx)
            self.itemList.insert(target_idx, item)
            self.invalidate()
            if self.parentWidget():
                self.parentWidget().update()

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def set_animate_moves(self, enabled: bool):
        self._animate_moves = enabled
        if not enabled:
            self._last_animated_targets.clear()

    def invalidate(self):
        self._hfw_cache = {}
        super().invalidate()

    def heightForWidth(self, width):
        # Qt asks this many times per layout pass for the same width. Any change to the
        # items (sizes, hints, items added or removed) invalidates the layout first.
        cache = self.__dict__.setdefault("_hfw_cache", {})
        h = cache.get(width)
        if h is None:
            h = cache[width] = self._do_layout(QRect(0, 0, width, 0), True)
        return h

    def setGeometry(self, rect):
        super().setGeometry(rect)
        parent = self.parentWidget()
        if parent: parent.setUpdatesEnabled(False)
        try:
            self._do_layout(rect, False)
        finally:
            if parent: parent.setUpdatesEnabled(True)

    def sizeHint(self):
        # Prefer actual width if available to avoid stacking height in 0-width states
        w = self.geometry().width()
        if w <= 0 and self.parentWidget():
            w = self.parentWidget().width()

        if w > 0:
            h = self.heightForWidth(w)
            return QSize(w, h if self.itemList else 0)
        return QSize(self.min_column_width, 0)

    def minimumSize(self):
        if not self.itemList:
            return QSize(0, 0)

        min_w = self.min_column_width + self.contentsMargins().left() + self.contentsMargins().right()
        w = self.geometry().width()
        if w <= 0 and self.parentWidget():
            w = self.parentWidget().width()
        if w <= 0:
            w = min_w

        try:
            min_h = max(0, int(self.heightForWidth(max(min_w, int(w)))))
        except Exception:
            min_h = 0
        return QSize(min_w, min_h)

    def _do_layout(self, rect, test_only):
        spacing = self.spacing()
        margin_l = self.contentsMargins().left()
        margin_r = self.contentsMargins().right()
        margin_t = self.contentsMargins().top()
        margin_b = self.contentsMargins().bottom()

        eff_width = rect.width() - margin_l - margin_r
        num_cols = max(1, (eff_width + spacing) // (self.min_column_width + spacing))
        col_width = (eff_width - (num_cols - 1) * spacing) // num_cols

        # Prevent division by zero if col_width + spacing becomes 0 or negative
        if col_width <= 0 or (col_width + spacing) <= 0:
            return 0

        max_row_w = max(1, int(eff_width))

        # Row-flow placement: wrap by width and center each row independently.
        # This avoids the "only first row centered" effect from masonry-style packing.
        items_meta = []
        for item in self.itemList:
            _widget = item.widget()
            min_w = item.minimumSize().width()
            hint_w = item.sizeHint().width()
            actual_w = max(int(min_w), int(hint_w))
            is_fixed_width_widget = False
            if _widget is not None:
                try:
                    is_fixed_width_widget = (
                        str(getattr(_widget, "wtype", "")) == "text_label"
                        or (
                            str(getattr(_widget, "wtype", "")) == "heatmap"
                            and (getattr(_widget, "_last_size_args", None) or (None, None))[0] is None
                        )
                        or _widget.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Fixed
                        or (
                            int(getattr(_widget, "minimumWidth", lambda: 0)())
                            == int(getattr(_widget, "maximumWidth", lambda: 16777215)())
                            and int(getattr(_widget, "minimumWidth", lambda: 0)()) > 0
                        )
                    )
                except Exception:
                    is_fixed_width_widget = False

            if is_fixed_width_widget:
                item_w = max(1, min(max_row_w, int(actual_w)))
            else:
                span = max(1, min(num_cols, (min_w + spacing + col_width + spacing - 1) // (col_width + spacing)))
                item_w = span * col_width + (span - 1) * spacing

            if _widget and getattr(_widget, "_has_saved_height", False):
                item_h = _widget.minimumHeight()
            else:
                item_h = item.heightForWidth(item_w) if item.hasHeightForWidth() else item.sizeHint().height()
                item_h = max(item_h, item.minimumSize().height())

            items_meta.append((item, int(item_w), int(item_h)))

        rows = []
        current_row = []
        current_row_w = 0
        current_row_h = 0
        for item, item_w, item_h in items_meta:
            gap = spacing if current_row else 0
            if current_row and (current_row_w + gap + item_w) > max_row_w:
                rows.append((current_row, current_row_w, current_row_h))
                current_row = []
                current_row_w = 0
                current_row_h = 0
                gap = 0

            current_row.append((item, item_w, item_h))
            current_row_w += gap + item_w
            current_row_h = max(current_row_h, item_h)

        if current_row:
            rows.append((current_row, current_row_w, current_row_h))

        items_to_place = []
        y = rect.y() + margin_t

        for row_items, row_w, row_h in rows:
            if self.centered:
                row_x = rect.x() + margin_l + max(0, (eff_width - row_w) // 2)
            else:
                row_x = rect.x() + margin_l

            x = row_x
            step = int(col_width + spacing)
            row_min_x = int(rect.x() + margin_l)
            row_entries = []
            base_xs = []
            desired_xs = []
            widths = []
            weights = []
            for item, item_w, item_h in row_items:
                base_x = int(x)
                w = item.widget()
                col_offset = int(getattr(w, "_col_offset", 0)) if w else 0
                desired_x = int(base_x + (col_offset * step))
                row_entries.append((item, int(item_w), int(item_h)))
                base_xs.append(base_x)
                desired_xs.append(desired_x)
                widths.append(int(item_w))
                # Strongly prioritize the actively shifted widget so each click
                # feels like a consistent modular step.
                weights.append(1.0 + (1000.0 * abs(col_offset)))
                x += item_w + spacing

            final_xs = project_row_positions(
                base_xs=base_xs,
                desired_xs=desired_xs,
                widths=widths,
                row_min=row_min_x,
                row_spacing=spacing,
                row_max=int(rect.x() + margin_l + eff_width),
                weights=weights,
            )
            for idx, (item, item_w, item_h) in enumerate(row_entries):
                items_to_place.append((item, QRect(int(final_xs[idx]), int(y), int(item_w), int(item_h))))

            y += row_h + spacing

        if not test_only:
             for item, target_rect in items_to_place:
                widget = item.widget()
                if widget and self._animate_moves:
                     old_rect = widget.geometry()
                     # Avoid snapping to target before starting animation (spring/pop effect).
                     if old_rect.isValid() and old_rect != target_rect and old_rect.width() > 0:
                          did_animate = self._animate_widget(widget, old_rect, target_rect)
                          if not did_animate:
                               item.setGeometry(target_rect)
                     else:
                          item.setGeometry(target_rect)
                else:
                     item.setGeometry(target_rect)

        if not self.itemList:
            return 0
        total_h = (y - spacing) + margin_b - rect.y()
        return max(0, int(total_h))

    def _animate_widget(self, widget, start_rect, end_rect):
        if not animations_enabled("pinned"):
            return False
        if widget is None:
            return False
        try:
            is_text_label = (str(getattr(widget, "wtype", "")) == "text_label")
        except Exception:
            is_text_label = False
        if is_text_label:
            return False
        # For newly shown widgets, avoid move animation once (fade-only appearance).
        try:
            no_move_once = bool(widget.property("deepdivestats_no_reflow_move_once"))
        except Exception:
            no_move_once = False
        if no_move_once:
            try:
                widget.setProperty("deepdivestats_no_reflow_move_once", False)
            except Exception:
                log_swallowed()
            return False
        if not widget.isVisible():
            return False
        if start_rect == end_rect:
            return False
        # Prevent replaying the same target repeatedly across coalesced relayout passes.
        target_key = (int(end_rect.x()), int(end_rect.y()), int(end_rect.width()), int(end_rect.height()))
        if self._last_animated_targets.get(widget) == target_key:
            return True
        self._last_animated_targets[widget] = target_key

        if (start_rect.width() != end_rect.width()) or (start_rect.height() != end_rect.height()):
            widget.resize(end_rect.width(), end_rect.height())
            start_rect = QRect(start_rect.x(), start_rect.y(), end_rect.width(), end_rect.height())

        dx = int(end_rect.x() - start_rect.x())
        dy = int(end_rect.y() - start_rect.y())
        max_lateral_travel = 220
        if abs(dx) > max_lateral_travel:
            clamped_x = int(end_rect.x() - max_lateral_travel) if dx > 0 else int(end_rect.x() + max_lateral_travel)
            start_rect = QRect(clamped_x, start_rect.y(), start_rect.width(), start_rect.height())
            dx = int(end_rect.x() - start_rect.x())

        travel = abs(dx) + abs(dy)
        duration = max(180, min(320, int(180 + (travel * 0.18))))
        animate_widget_geometry(widget, start_rect, end_rect, self._animations, duration=duration)
        return True




