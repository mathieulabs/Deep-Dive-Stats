# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from datetime import datetime
import csv
import html
import re

from aqt.qt import QFileDialog, QTableWidget, QLabel, Qt
from aqt.utils import showInfo, showCritical

from ..logger import log_swallowed

_TAG = re.compile(r"<[^>]*>")


def _plain(text):
    """Cell text without the HTML the table uses for colors and layout."""
    text = str(text or "")
    text = re.sub(r"</(td|tr|p|div)>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<br\s*/?>", " ", text, flags=re.IGNORECASE)
    text = _TAG.sub("", text)
    text = html.unescape(text).replace("\u00a0", " ")
    return re.sub(r"\s+", " ", text).strip()


def _bar_text(bar):
    """The numbers behind a bar drawn in a cell (retention or answer buttons)."""
    counts = [int(c or 0) for c in (getattr(bar, "counts", None) or [])]
    labels = list(getattr(bar, "labels", None) or [])
    center = _plain(getattr(bar, "center_text", "") or "")
    if len(counts) == 2:
        # Retention bar: [wrong, correct]
        wrong, correct = counts
        return f"{center} ({correct}/{wrong})" if center else f"{correct}/{wrong}"
    parts = [f"{labels[i] if i < len(labels) else i} {n}" for i, n in enumerate(counts)]
    return " | ".join(parts)


def _cell_text(table, row, col):
    widget = table.cellWidget(row, col)
    if widget is not None:
        if isinstance(widget, QLabel):
            return _plain(widget.text())
        if hasattr(widget, "counts"):
            return _bar_text(widget)
    item = table.item(row, col)
    if item is None:
        return ""
    if col == 0:
        # The first column holds the deck name with tree decorations; the real name is stored.
        full = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(full, str) and full and full != "[[TOTAL]]":
            return full
        if full == "[[TOTAL]]":
            return _plain(item.text()) or "Total"
    return _plain(item.text())


def export_to_csv(dialog):
    tab = dialog.tab_widget.currentWidget()
    if not tab:
        return
    table = tab.findChild(QTableWidget)
    if not table:
        return

    title = dialog.tab_widget.tabText(dialog.tab_widget.currentIndex())
    import os

    clean = "".join(c if c.isalnum() else "_" for c in title)
    fn = f"Anki_Stats_{clean}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    start_dir = os.path.join(desktop if os.path.isdir(desktop) else os.path.expanduser("~"), fn)
    path, _ = QFileDialog.getSaveFileName(
        dialog, "Export CSV", start_dir, "CSV Files (*.csv)"
    )
    if not path:
        return
    if not path.lower().endswith('.csv'):
        path += '.csv'

    try:
        # Same as on screen: the visible columns, and the visible rows in the order shown.
        cols = [c for c in range(table.columnCount()) if not table.isColumnHidden(c)]
        header = table.verticalHeader()
        rows = [header.logicalIndex(v) for v in range(table.rowCount())]
        rows = [r for r in rows if r >= 0 and not table.isRowHidden(r)]
        # utf-8-sig: Excel only reads accents and non-latin deck names right with the BOM.
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow([
                _plain(table.horizontalHeaderItem(c).text())
                if table.horizontalHeaderItem(c)
                else f"Col {c}"
                for c in cols
            ])
            for r in rows:
                w.writerow([_cell_text(table, r, c) for c in cols])
        showInfo(f"Exported to:\n{path}")
    except Exception as e:
        log_swallowed()
        showCritical(f"CSV export failed:\n{str(e)}")
