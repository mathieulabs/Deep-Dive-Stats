# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""'Set zoom as time span' (web_ui/window.py): the zoomed days' dates, their default name, the name dialog."""
import re
from datetime import date, datetime

from aqt import mw
from aqt.qt import QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, Qt, QVBoxLayout
from ....qss import set_qss

from ...logic.logger import log_swallowed
from ....i18n import tr

_MONTHS = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")
_TEXT_DATE = re.compile(r"^([A-Za-z]{3})[A-Za-z]*\.?\s+(\d{1,2}),?\s+(\d{4})")
_ISO_DATE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")


def _parse(value):
    """Date from 'Mon DD, YYYY' (English month names, locale independent) or 'YYYY-MM-DD'."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        return None
    text = value.strip()
    try:
        m = _ISO_DATE.match(text)
        if m:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        m = _TEXT_DATE.match(text)
        if m and m.group(1).lower() in _MONTHS:
            return date(int(m.group(3)), _MONTHS.index(m.group(1).lower()) + 1, int(m.group(2)))
    except ValueError:
        return None
    return None


def _default_name(d0, d1):
    def fmt(d):
        return f"{d.day:02d} {_MONTHS[d.month - 1].capitalize()} {d.year}"

    return fmt(d0) if d0 == d1 else f"{fmt(d0)} - {fmt(d1)}"


def _unique_title(tabs, name):
    used = {t.get("title") for t in tabs}
    if name not in used:
        return name
    i = 2
    while f"{name} ({i})" in used:
        i += 1
    return f"{name} ({i})"


def ask_span_name(default, parent=None):
    """Small themed dialog asking for the span name. Returns the name or None."""
    dlg = QDialog(parent or mw)
    dlg.setWindowTitle(tr("Time Span"))
    from ....window_icon import addon_icon
    addon_icon(dlg)
    dlg.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
    dlg.setMinimumWidth(340)
    try:
        from ...widgets.chart_utils.theme import ThemeContext, settings_dialog_qss_for

        set_qss(dlg, settings_dialog_qss_for(parent, default=ThemeContext.DETAILS))
    except Exception:
        log_swallowed()
    lay = QVBoxLayout(dlg)
    lay.setContentsMargins(14, 14, 14, 14)
    lay.setSpacing(10)
    lay.addWidget(QLabel(tr("Name:")))
    edit = QLineEdit(default, dlg)
    edit.selectAll()
    lay.addWidget(edit)
    row = QHBoxLayout()
    row.addStretch(1)
    cancel = QPushButton(tr("Cancel"), dlg)
    ok = QPushButton(tr("OK"), dlg)
    ok.setDefault(True)
    cancel.clicked.connect(dlg.reject)
    ok.clicked.connect(dlg.accept)
    edit.returnPressed.connect(dlg.accept)
    row.addWidget(cancel)
    row.addWidget(ok)
    lay.addLayout(row)
    if not dlg.exec():
        return None
    return edit.text().strip() or None

