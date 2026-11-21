# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Small themed dialog asking for a whole number."""
from aqt import mw
from aqt.qt import QDialog, QHBoxLayout, QLabel, QPushButton, QSpinBox, Qt, QVBoxLayout

from ...logic.logger import log_swallowed
from ....qss import set_qss
from ....i18n import tr


def ask_number(title, label, value=0, minimum=0, maximum=100000, parent=None):
    """Return the number the user typed, or None if they cancelled."""
    dlg = QDialog(parent or mw)
    dlg.setWindowTitle(title)
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
    text = QLabel(label, dlg)
    text.setWordWrap(True)
    lay.addWidget(text)
    spin = QSpinBox(dlg)
    spin.setRange(int(minimum), int(maximum))
    spin.setValue(int(value))
    spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
    spin.selectAll()
    lay.addWidget(spin)
    row = QHBoxLayout()
    row.addStretch(1)
    cancel = QPushButton(tr("Cancel"), dlg)
    ok = QPushButton(tr("OK"), dlg)
    ok.setDefault(True)
    cancel.clicked.connect(dlg.reject)
    ok.clicked.connect(dlg.accept)
    row.addWidget(cancel)
    row.addWidget(ok)
    lay.addLayout(row)
    spin.setFocus()
    if not dlg.exec():
        return None
    return spin.value()


def ask_text(title, label, value="", ok_text=None, parent=None):
    """Return the text the user typed (trimmed, never empty), or None if they cancelled."""
    from aqt.qt import QLineEdit

    dlg = QDialog(parent or mw)
    dlg.setWindowTitle(title)
    from ....window_icon import addon_icon
    addon_icon(dlg)
    dlg.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
    dlg.setMinimumWidth(360)
    try:
        from ...widgets.chart_utils.theme import ThemeContext, settings_dialog_qss_for

        set_qss(dlg, settings_dialog_qss_for(parent, default=ThemeContext.DETAILS))
    except Exception:
        log_swallowed()
    lay = QVBoxLayout(dlg)
    lay.setContentsMargins(14, 14, 14, 14)
    lay.setSpacing(10)
    text = QLabel(label, dlg)
    text.setWordWrap(True)
    lay.addWidget(text)
    edit = QLineEdit(dlg)
    edit.setText(str(value or ""))
    edit.setMaxLength(80)
    edit.selectAll()
    lay.addWidget(edit)
    row = QHBoxLayout()
    row.addStretch(1)
    cancel = QPushButton(tr("Cancel"), dlg)
    ok = QPushButton(ok_text or tr("OK"), dlg)
    ok.setDefault(True)
    cancel.clicked.connect(dlg.reject)
    ok.clicked.connect(dlg.accept)
    edit.textChanged.connect(lambda s: ok.setEnabled(bool(s.strip())))
    ok.setEnabled(bool(edit.text().strip()))
    row.addWidget(cancel)
    row.addWidget(ok)
    lay.addLayout(row)
    edit.setFocus()
    if not dlg.exec():
        return None
    return edit.text().strip() or None
