# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
import re

from aqt.qt import QFontMetrics, QHeaderView, QLabel

from .. import Config
from ...widgets import SparklineWidget
from ...logic.logger import log_swallowed


def auto_resize_window(dialog, table, resize_window=True):
    # No repaint between the column changes: otherwise the stretched last column
    # visibly flips back and forth while the others are resized.
    was_updating = table.updatesEnabled()
    table.setUpdatesEnabled(False)
    try:
        return _auto_resize_impl(dialog, table, resize_window)
    finally:
        table.setUpdatesEnabled(was_updating)


def _auto_resize_impl(dialog, table, resize_window=True):
    """Auto-resize columns and window width to fit content."""
    if not table.isVisible():
        # A table created while its page is already on screen is only shown on Qt's next
        # layout pass. Waiting for that left the columns unsized, then they jumped.
        parent = table.parentWidget()
        if parent is not None and parent.isVisible():
            table.show()
    if not table.isVisible():
        return False

    fm = QFontMetrics(table.font())
    header_fm = QFontMetrics(table.horizontalHeader().font())

    # Buffer for padding (12px * 2 = 24px) + margin
    CELL_PADDING = 30

    # Measure a representative subset of rows instead of every row.
    row_count = table.rowCount()
    sample_rows = set()
    if row_count <= 32:
        sample_rows.update(range(row_count))
    else:
        sample_rows.update({0, row_count - 1})
        selected = table.currentRow()
        if selected >= 0:
            sample_rows.add(selected)
        top_row = table.rowAt(0)
        bottom_row = table.rowAt(max(0, table.viewport().height() - 1))
        if top_row >= 0:
            if bottom_row < top_row:
                bottom_row = min(row_count - 1, top_row + 12)
            sample_rows.update(range(top_row, min(row_count, bottom_row + 1)))
        step = max(1, row_count // 16)
        sample_rows.update(range(0, row_count, step))
        if len(sample_rows) > 32:
            ordered = sorted(sample_rows)
            stride = max(1, len(ordered) // 32)
            sample_rows = set(ordered[::stride][:32])
            sample_rows.update({0, row_count - 1})
            if selected >= 0:
                sample_rows.add(selected)
    sample_rows = sorted(r for r in sample_rows if 0 <= r < row_count)

    show_buttons_visual = bool(
        getattr(getattr(dialog, "addon_config", None), "config", {}).get(Config.SHOW_BUTTONS_DIST_VISUAL, True)
    )

    # No repaint between the column changes: otherwise the stretched last column
    # visibly flips back and forth while the others are resized.
    for c in range(table.columnCount()):
        raw_header = table.horizontalHeaderItem(c).text() if table.horizontalHeaderItem(c) else ""
        header_text = raw_header.upper() # CSS text-transform: uppercase
        max_width = header_fm.horizontalAdvance(header_text) + CELL_PADDING

        for r in sample_rows:
            widget = table.cellWidget(r, c)
            if widget:
                if isinstance(widget, SparklineWidget):
                    text_width = widget.sizeHint().width() + 25
                elif isinstance(widget, QLabel):
                    if "<table" in widget.text():
                        # HTML table width: trust sizeHint with a minimum
                        text_width = widget.sizeHint().width() + 25
                    else:
                        plain_text = re.sub('<[^<]+?>', '', widget.text())
                        text_width = fm.horizontalAdvance(plain_text) + CELL_PADDING
                else:
                    text_width = widget.sizeHint().width() + 10
            else:
                item = table.item(r, c)
                if item:
                    txt = item.text()
                    if "<" in txt and ">" in txt:
                        # Fast HTML width estimate: strip tags instead of creating a QTextDocument per cell.
                        plain_text = re.sub('<[^<]+?>', '', txt)
                        text_width = fm.horizontalAdvance(plain_text) + CELL_PADDING
                        if "<table" in txt:
                            text_width += 36
                    else:
                        item_font = item.font()
                        if item_font.bold():
                            text_width = header_fm.horizontalAdvance(txt) + CELL_PADDING
                        else:
                            text_width = fm.horizontalAdvance(txt) + CELL_PADDING
                else:
                    text_width = 0

            if text_width > max_width:
                max_width = text_width

        if c == 0:
            max_width = min(max_width, 300) # Cap the deck column width but let the user widen it manually
        elif raw_header == "Buttons" and show_buttons_visual:
            # The bar widget reports a tiny size hint; populate gives it 140 px, keep at least that.
            max_width = max(max_width, table.columnWidth(c), 140)
        elif raw_header == "Buttons" and not show_buttons_visual:
            # Text mode only: keep a safe floor and preserve width set during populate.
            max_width = max(max_width, table.columnWidth(c), 190)
        table.setColumnWidth(c, int(max_width))

    # Cell widgets (buttons bar, sparklines, rich labels) only move to the new column
    # geometry on Qt's delayed layout pass, so they paint at the old positions for
    # a frame. Lay the table out now so the first paint after a tab switch is right.
    try:
        table.doItemsLayout()
    except Exception:
        log_swallowed()

    # First column is interactive so it does not get crushed
    table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
    from ..table.fill_width import install_fill, remember_natural_widths

    install_fill(table)
    remember_natural_widths(table)
    return True

