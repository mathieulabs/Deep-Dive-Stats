# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""'Set zoom as time span': turn the zoomed window of a chart into a saved fixed-date span."""
import copy
import re
from datetime import date, datetime

from aqt import mw
from aqt.qt import QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, Qt, QVBoxLayout
from ....qss import set_qss

from ...logic.data.core import abs_period
from ...logic.logger import log_swallowed

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


def _row_date(row):
    if isinstance(row, (list, tuple)):
        cands = row[:1]
    elif isinstance(row, dict):
        cands = [row.get(k) for k in ("pretty_date", "label", "logical_date", "date", "x")]
    else:
        cands = [row]
    for c in cands:
        d = _parse(c)
        if d:
            return d
    return None


def find_zoomed_chart(widget):
    """First chart inside widget (or widget itself) that is zoomed and has dated rows."""
    from ...widgets.chart_utils.zoom_mixin import ZoomableMixin

    cands = [widget] if isinstance(widget, ZoomableMixin) else []
    try:
        cands += widget.findChildren(ZoomableMixin)
    except Exception:
        log_swallowed()
    for c in cands:
        if not (getattr(c, "_is_zoomed", False) or _adaptive_dates(c)):
            continue
        if zoom_dates(c):
            return c
    return None


def _adaptive_dates(chart):
    """Day range kept by a pinned chart while it shows the 10-minute view."""
    st = getattr(chart, "_adaptive_state", None)
    if isinstance(st, dict) and st.get("active") and st.get("dates"):
        return st["dates"]
    return None


def zoom_dates(chart):
    """(start_date, end_date) of the zoomed window, or None."""
    from ...widgets.chart_utils.zoom_mixin import zoom_rows

    dates = _adaptive_dates(chart)
    if dates:
        return dates

    rows = zoom_rows(chart)
    s, e = int(chart._zoom_start), int(chart._zoom_end)
    if not (0 <= s < e <= len(rows)):
        return None
    d0, d1 = _row_date(rows[s]), _row_date(rows[e - 1])
    if not d0 or not d1 or d1 < d0:
        return None
    return d0, d1


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
    dlg.setWindowTitle("Time Span")
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
    lay.addWidget(QLabel("Name:"))
    edit = QLineEdit(default, dlg)
    edit.selectAll()
    lay.addWidget(edit)
    row = QHBoxLayout()
    row.addStretch(1)
    cancel = QPushButton("Cancel", dlg)
    ok = QPushButton("OK", dlg)
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


def create_span_from_zoom(chart, addon_config, parent=None):
    """Ask for a name, save the span as a tab, return its encoded period (or None)."""
    from ...logic.tabs import DEFAULT_DETAILS_TABS, get_tabs_config, refresh_open_details_tabs, save_tabs_config

    dates = zoom_dates(chart)
    if not dates:
        return None
    d0, d1 = dates
    name = ask_span_name(_default_name(d0, d1), parent)
    if not name:
        return None
    code = abs_period.encode(d0, d1)
    tabs = copy.deepcopy(get_tabs_config(addon_config))
    for t in tabs:
        if t.get("range") == code:
            return code
    tab = copy.deepcopy(DEFAULT_DETAILS_TABS[0])
    tab["title"] = _unique_title(tabs, name)
    tab["range"] = code
    tabs.append(tab)
    save_tabs_config(addon_config, tabs)
    refresh_open_details_tabs()
    return code
