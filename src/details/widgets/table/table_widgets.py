# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import (
    QApplication, QKeySequence, QTableWidget, QTextDocument, Qt
)
import re

class HorizontalScrollTable(QTableWidget):
    def wheelEvent(self, event):
        if event.modifiers() == Qt.KeyboardModifier.ShiftModifier:
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - event.angleDelta().y()
            )
        else:
            super().wheelEvent(event)

    def keyPressEvent(self, event):
        # Keep row-selection UX, but allow normal text copy from selected rows/cells.
        if event.matches(QKeySequence.StandardKey.Copy):
            self._copy_selection_plain_text()
            event.accept()
            return
        super().keyPressEvent(event)

    def _copy_selection_plain_text(self):
        indexes = self.selectedIndexes()
        if not indexes:
            item = self.currentItem()
            if not item:
                return
            text = self._to_plain_text(item.text())
            QApplication.clipboard().setText(text)
            return

        ordered = sorted(indexes, key=lambda i: (i.row(), i.column()))
        rows = {}
        selected_cols = sorted({idx.column() for idx in ordered})
        for idx in ordered:
            rows.setdefault(idx.row(), []).append(idx)

        tab_title = self._resolve_tab_title()
        row_lines = []

        # Human-friendly row format:
        # Tab: Total | Deck: X | Time: Y | Reviews: Z | ...
        for r in sorted(rows.keys()):
            parts = []
            if tab_title:
                parts.append(f"Tab: {tab_title}")
            for c in selected_cols:
                item = self.item(r, c)
                raw = item.text() if item else ""
                txt = self._to_plain_text(raw)
                h_item = self.horizontalHeaderItem(c)
                header = (h_item.text() if h_item else f"Column {c + 1}").strip()
                if c == 0 and item is not None:
                    # Prefer full deck/time path when available for clearer context.
                    try:
                        full_path = item.data(Qt.ItemDataRole.UserRole)
                    except Exception:
                        full_path = None
                    if isinstance(full_path, str) and full_path.strip():
                        fp = full_path.strip()
                        txt = "Total" if fp == "[[TOTAL]]" else fp
                parts.append(f"{header}: {txt}")
            row_lines.append(" | ".join(parts))

        QApplication.clipboard().setText("\n\n".join(row_lines))

    def _resolve_tab_title(self):
        try:
            win = self.window()
            tab_widgets = win.findChildren(type(win.tab_widget)) if hasattr(win, "tab_widget") else []
            if not tab_widgets and hasattr(win, "findChildren"):
                from aqt.qt import QTabWidget
                tab_widgets = win.findChildren(QTabWidget)
            for tw in tab_widgets:
                for i in range(tw.count()):
                    page = tw.widget(i)
                    if page and page.isAncestorOf(self):
                        return tw.tabText(i)
        except Exception:
            return None
        return None

    @staticmethod
    def _to_plain_text(raw):
        txt = str(raw or "")
        if "<" in txt and ">" in txt:
            doc = QTextDocument()
            doc.setHtml(txt)
            txt = doc.toPlainText()
        # Normalize whitespace/newlines so copy stays one-line and readable.
        txt = txt.replace("\r", "\n")
        txt = re.sub(r"\s*\n\s*", " ", txt)
        txt = re.sub(r"\s*\|\s*", " | ", txt)
        txt = re.sub(r"[ \t]+", " ", txt).strip()
        return txt
