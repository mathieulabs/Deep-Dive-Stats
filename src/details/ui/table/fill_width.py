# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Spread the free width of a stats table over all its columns.

Without this the last column took all the free space, which left a wide empty
column on large screens and in exports. Each column grows in proportion to its
natural width, up to MAX_GROWTH times it; whatever is left stays on the right.
A column the user resizes by hand keeps its width until the next auto-size.
"""
from aqt.qt import QEvent, QObject
from ...logic.logger import log_swallowed

MAX_GROWTH = 1.8


def _visible_columns(table):
    return [c for c in range(table.columnCount()) if not table.isColumnHidden(c)]


def apply_fill(table):
    natural = getattr(table, "_dd_natural_widths", None)
    if not natural:
        return
    header = table.horizontalHeader()
    cols = [c for c in _visible_columns(table) if c in natural]
    if not cols:
        return
    manual = getattr(table, "_dd_manual_widths", {})
    base = {c: manual.get(c, natural[c]) for c in cols}
    free = table.viewport().width() - sum(base.values())
    grow = [c for c in cols if c not in manual]
    total = sum(base[c] for c in grow) or 1
    table._dd_filling = True
    try:
        for c in cols:
            w = base[c]
            if free > 0 and c in grow:
                w = int(min(w * MAX_GROWTH, w + free * base[c] / total))
            if header.sectionSize(c) != w:
                header.resizeSection(c, w)
    finally:
        table._dd_filling = False


def remember_natural_widths(table):
    """Call after the columns were sized to their content."""
    table._dd_natural_widths = {c: table.columnWidth(c) for c in range(table.columnCount())}
    table._dd_manual_widths = {}
    apply_fill(table)


class _ResizeWatcher(QObject):
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Resize:
            try:
                apply_fill(self.parent())
            except Exception:
                log_swallowed()
        return False


def install_fill(table):
    """Turn off last-column stretching and keep the table filled on resize."""
    header = table.horizontalHeader()
    header.setStretchLastSection(False)
    if getattr(table, "_dd_fill_installed", False):
        return
    table._dd_fill_installed = True
    table._dd_filling = False
    watcher = _ResizeWatcher(table)
    table.viewport().installEventFilter(watcher)
    table._dd_fill_watcher = watcher

    def _on_section_resized(col, _old, new):
        if getattr(table, "_dd_filling", False):
            return
        if getattr(table, "_dd_natural_widths", None) is None:
            return
        # Resized by hand: keep this width.
        table._dd_manual_widths = dict(getattr(table, "_dd_manual_widths", {}))
        table._dd_manual_widths[col] = new

    header.sectionResized.connect(_on_section_resized)
