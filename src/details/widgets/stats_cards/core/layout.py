# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QLayout, QSize, QSizePolicy, Qt, QRect
from ...common.row_projection import project_row_positions

try:
    from aqt.qt import QWidgetItem as _QWidgetItem, QSpacerItem as _QSpacerItem
except ImportError:
    try:
        from PyQt6.QtWidgets import QWidgetItem as _QWidgetItem, QSpacerItem as _QSpacerItem
    except ImportError:
        from PyQt5.QtWidgets import QWidgetItem as _QWidgetItem, QSpacerItem as _QSpacerItem


class WrappingHBoxLayout(QLayout):
    """QHBoxLayout-like layout that wraps items to a second row when they overflow."""

    def __init__(self, parent=None, spacing=6):
        super().__init__(parent)
        self._items = []
        self._h_spacing = spacing
        self._v_spacing = 4
        self._row_h = 66
        if parent is not None:
            self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item):
        self._items.append(item)
        if not hasattr(item, "_stretch"):
            item._stretch = 0
        self.invalidate()

    def count(self):
        return len(self._items)

    def itemAt(self, idx):
        return self._items[idx] if 0 <= idx < len(self._items) else None

    def takeAt(self, idx):
        if 0 <= idx < len(self._items):
            self.invalidate()
            return self._items.pop(idx)
        return None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        has_stretch = any(getattr(it, "_stretch", 0) > 0 for it in self._items if it.widget())
        return not has_stretch

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def sizeHint(self):
        return QSize(0, self._row_h)

    def minimumSize(self):
        return QSize(50, self._row_h)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def indexOf(self, widget):
        for i, item in enumerate(self._items):
            if item.widget() is widget:
                return i
        return -1

    def insertWidget(self, idx, widget, stretch=0):
        item = _QWidgetItem(widget)
        item._stretch = stretch
        self._items.insert(max(0, min(idx, len(self._items))), item)
        if self.parentWidget() and widget.parent() is not self.parentWidget():
            widget.setParent(self.parentWidget())
        self.invalidate()

    def removeWidget(self, widget):
        for i, item in enumerate(self._items):
            if item.widget() is widget:
                self._items.pop(i)
                self.invalidate()
                return

    def setStretch(self, idx, stretch):
        if 0 <= idx < len(self._items):
            self._items[idx]._stretch = stretch
        self.invalidate()

    def insertStretch(self, idx, stretch=0):
        spacer = _QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self._items.insert(max(0, min(idx, len(self._items))), spacer)
        self.invalidate()

    def addWidget(self, widget, stretch=0):
        item = _QWidgetItem(widget)
        item._stretch = stretch
        self.addItem(item)
        if self.parentWidget() and widget.parent() is not self.parentWidget():
            widget.setParent(self.parentWidget())

    def addStretch(self, stretch=0):
        spacer = _QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        spacer._stretch = stretch
        self._items.append(spacer)
        self.invalidate()

    def spacing(self):
        return self._h_spacing

    def setSpacing(self, spacing):
        self._h_spacing = spacing

    def setRowHeight(self, h):
        self._row_h = int(h)

    def _is_spacer(self, item):
        return not item.widget()

    def _has_leading_spacer(self):
        return bool(self._items) and self._is_spacer(self._items[0])

    def _has_trailing_spacer(self):
        return bool(self._items) and self._is_spacer(self._items[-1])

    def _widget_items(self):
        return [it for it in self._items if it.widget() and it.widget().isVisible()]

    def _item_width(self, item):
        w = item.widget()
        min_w = w.minimumWidth()
        if min_w > 0:
            return min_w
        curr_w = w.width()
        if curr_w > 0:
            return curr_w
        return max(1, w.sizeHint().width())

    def _do_layout(self, rect, test_only=False):
        m_l, m_t, m_r, m_b = self.getContentsMargins()
        avail_w = rect.width() - m_l - m_r

        widget_items = self._widget_items()
        if not widget_items:
            return self._row_h + m_t + m_b

        has_leading = self._has_leading_spacer()
        has_trailing = self._has_trailing_spacer()
        has_stretch = any(getattr(it, "_stretch", 0) > 0 for it in self._items if it.widget())

        if has_stretch:
            natural_h = self._row_h + m_t + m_b
            if test_only:
                return natural_h
            item_h = max(1, rect.height() - m_t - m_b) if rect.height() > 0 else self._row_h
            n = len(widget_items)
            total_spacing = max(0, n - 1) * self._h_spacing
            item_w = max(1, (avail_w - total_spacing) // n) if n > 0 else avail_w
            x = rect.x() + m_l
            y = rect.y() + m_t
            for item in widget_items:
                item.setGeometry(QRect(int(x), int(y), int(item_w), item_h))
                x += item_w + self._h_spacing
            return item_h + m_t + m_b

        ref_w = self._item_width(widget_items[0]) if widget_items else 0
        aug_items = list(widget_items)
        aug_widths = [self._item_width(it) for it in widget_items]
        total_w = sum(aug_widths) + max(0, len(aug_widths) - 1) * self._h_spacing

        if avail_w <= 0 or total_w <= avail_w or len(aug_items) <= 1:
            rows = [list(zip(aug_items, aug_widths))]
        else:
            mid = (len(aug_items) + 1) // 2
            rows = [
                list(zip(aug_items[:mid], aug_widths[:mid])),
                list(zip(aug_items[mid:], aug_widths[mid:])),
            ]

        num_rows = len(rows)
        total_h = num_rows * self._row_h + max(0, num_rows - 1) * self._v_spacing + m_t + m_b
        if test_only:
            return total_h

        for row_idx, row_pairs in enumerate(rows):
            row_w = sum(w for _, w in row_pairs) + max(0, len(row_pairs) - 1) * self._h_spacing
            if has_leading and has_trailing:
                x_start = rect.x() + m_l + max(0, (avail_w - row_w) // 2)
            elif has_leading:
                x_start = rect.x() + m_l + max(0, avail_w - row_w)
            else:
                x_start = rect.x() + m_l
            y = rect.y() + m_t + row_idx * (self._row_h + self._v_spacing)
            x = x_start
            step = int(ref_w + self._h_spacing)
            row_min_x = int(rect.x() + m_l)
            row_entries = []
            base_xs = []
            desired_xs = []
            widths = []
            weights = []
            for item, w in row_pairs:
                base_x = int(x)
                col_offset = int(getattr(item.widget(), "_col_offset", 0)) if item.widget() else 0
                desired_x = int(base_x + (col_offset * step))
                row_entries.append((item, int(w)))
                base_xs.append(base_x)
                desired_xs.append(desired_x)
                widths.append(int(w))
                weights.append(1.0 + (1000.0 * abs(col_offset)))
                x += w + self._h_spacing

            final_xs = project_row_positions(
                base_xs=base_xs,
                desired_xs=desired_xs,
                widths=widths,
                row_min=row_min_x,
                row_spacing=self._h_spacing,
                row_max=int(rect.x() + m_l + avail_w),
                weights=weights,
            )
            for idx, (item, w) in enumerate(row_entries):
                item.setGeometry(QRect(int(final_xs[idx]), int(y), int(w), self._row_h))

        return total_h
