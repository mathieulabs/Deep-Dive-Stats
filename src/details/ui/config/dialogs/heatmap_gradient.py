# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""A gradient of the user's for the heatmap, made or changed from its right-click menu (Palette > New gradient... /
Edit gradient...): its name, its colors (2 to 12, the least activity first), a color more or less, delete it.

Each change is saved and shown at once (Heatmap_Custom_Palettes, Heatmap_Palette); the heatmap's Settings edit the
same gradients."""

from aqt.qt import (
    QColor, QDialog, QHBoxLayout, QIcon, QLabel, QLineEdit, QPainter, QPalette, QPixmap, QPushButton, QSize, Qt, QTimer,
    QVBoxLayout, QWidget,
)

from ... import Config
from ...theme import get_settings_dialog_style
from ...theme.icons import get_svg_icon
from ....widgets.charts.heatmap.palettes import (CUSTOM, DEFAULT_COLORS, MAX_COLORS, MIN_COLORS, customs_of, new_id,
                                                  palette_of)
from .....qss import set_qss
from .....i18n import tr


def color_label(i, n):
    if i == 0:
        return tr("Low")
    if i == n - 1:
        return tr("High")
    return tr("Middle") if n == 3 else "%s %d" % (tr("Middle"), i)


def mix_hex(a, b):
    try:
        ra, rb = int(a.lstrip("#")[:6], 16), int(b.lstrip("#")[:6], 16)
    except ValueError:
        return b
    return "#%02x%02x%02x" % tuple(((ra >> s & 255) + (rb >> s & 255)) // 2 for s in (16, 8, 0))


def _sign_icon(color, plus):
    """A "−" or "+" of 2 px strokes in a 14 px square, centred to the pixel (drawn at 3x for sharp edges); greyed out
    when the button is disabled."""
    icon = QIcon()
    for mode, alpha in ((QIcon.Mode.Normal, 255), (QIcon.Mode.Disabled, 90)):
        pm = QPixmap(42, 42)
        pm.fill(Qt.GlobalColor.transparent)
        qp = QPainter(pm)
        c = QColor(color)
        c.setAlpha(alpha)
        qp.fillRect(6, 18, 30, 6, c)
        if plus:
            qp.fillRect(18, 6, 6, 30, c)
        qp.end()
        pm.setDevicePixelRatio(3)
        icon.addPixmap(pm, mode)
    return icon


def stops_row(parent):
    """The gradient as a strip (the least activity on the left), with "−" and "+" for a color less / more.
    Returns (layout, minus, plus, show(colors))."""
    row = QHBoxLayout()
    strip = QLabel(parent)
    strip.setFixedHeight(16)
    strip.setToolTip(tr("Low") + " → " + tr("High"))
    row.addWidget(strip, 1)
    minus = QPushButton(parent)
    plus = QPushButton(parent)
    ink = parent.palette().color(QPalette.ColorRole.ButtonText)
    for b, tip, vertical in ((minus, tr("Remove color"), False), (plus, tr("Add color"), True)):
        b.setFixedSize(34, 28)
        # its own look (the dialog style rounded it into a circle and its padding cut the sign off); the sign is drawn,
        # centred to the pixel (the "−" character sat off centre in the font). Its size is in the style too: a style's
        # min-width / min-height replace setFixedSize's minimum (0 there, the layout squeezed it to 22 x 16)
        set_qss(b, "QPushButton { padding: 0px; min-width: 34px; max-width: 34px; min-height: 28px; max-height: 28px;"
                   " border-radius: 7px; border: 1px solid rgba(128,128,128,0.45); background: rgba(128,128,128,0.12); }"
                   " QPushButton:hover { background: rgba(128,128,128,0.24); }"
                   " QPushButton:pressed { background: rgba(128,128,128,0.34); }"
                   " QPushButton:disabled { background: transparent; border-color: rgba(128,128,128,0.25); }")
        b.setIcon(_sign_icon(ink, vertical))
        b.setIconSize(QSize(14, 14))
        b.setToolTip(tip)
        row.addWidget(b)

    def show(colors):
        n = len(colors)
        stops = ", ".join("stop:%g %s" % (i / max(1, n - 1), c) for i, c in enumerate(colors))
        set_qss(strip, "QLabel { border-radius: 4px; border: 1px solid rgba(128,128,128,0.45);"
                       " background: qlineargradient(x1:0, y1:0, x2:1, y2:0, %s); }" % stops)

    return row, minus, plus, show


def _color_row(dialog, box, label, current_fn, is_default_fn, set_fn, reset_fn, reset_tip):
    """label, a swatch to pick a color and a button back to the default one. Returns
    (swatch, show): show() repaints the row from current_fn / is_default_fn."""
    row = QHBoxLayout()
    row.addWidget(QLabel(label))
    row.addStretch()
    swatch = QPushButton(dialog)  # parented: a lone button would show as a window
    swatch.setFixedSize(28, 22)
    swatch.setCursor(Qt.CursorShape.PointingHandCursor)
    swatch.setToolTip(tr("Click to pick a color"))
    reset = QPushButton(dialog)
    reset.setIcon(get_svg_icon("rotate-ccw", size=13, context_ref=dialog))
    reset.setFixedSize(22, 22)
    reset.setCursor(Qt.CursorShape.PointingHandCursor)
    reset.setToolTip(reset_tip)
    set_qss(reset, "QPushButton { background: transparent; border: none; } QPushButton:hover { background: rgba(128,128,128,0.18); border-radius: 4px; }")

    def show():
        set_qss(swatch, f"background-color: {current_fn()}; border: 1px solid rgba(128,128,128,0.45); border-radius: 4px;")
        reset.setVisible(not is_default_fn())

    def pick(_checked=False):
        from ..shared.color_picker import pick_color_live

        def live(hex_):
            set_fn(hex_)
            show()

        pick_color_live(dialog, current_fn(), tr("Pick Color"), live)

    def back(_checked=False):
        reset_fn()
        show()

    swatch.clicked.connect(pick)
    reset.clicked.connect(back)
    show()
    row.addWidget(swatch)
    row.addWidget(reset)
    box.addLayout(row)
    return swatch, show


def edit_gradient(parent, conf, write, on_change, new=False, seed=None):
    """conf: the add-on config (dict); write(key, value) saves one value; on_change() shows the change.
    new: a new gradient from `seed` (the colors of the palette shown), chosen at once; else the chosen one."""

    customs = customs_of(conf.get)
    key = palette_of(conf.get, customs)
    if new:
        pid = new_id(customs)
        customs.append({"id": pid, "name": tr("Gradient {number}", number=pid),
                        "colors": list(seed or DEFAULT_COLORS)[:MAX_COLORS]})
        key = CUSTOM + pid
    grad = next((p for p in customs if CUSTOM + p["id"] == key), None)
    if grad is None:
        return False

    timer = QTimer()
    timer.setSingleShot(True)
    timer.setInterval(120)  # a color dragged in the picker: saved and shown once it rests

    def save_now():
        write(Config.HEATMAP_CUSTOM_PALETTES, [dict(p, colors=list(p["colors"])) for p in customs])
        write(Config.HEATMAP_PALETTE, key)
        on_change()

    timer.timeout.connect(save_now)
    if new:
        save_now()

    dlg = QDialog(parent)
    dlg.setWindowTitle(tr("Gradient"))
    dlg.setMinimumWidth(320)
    try:
        set_qss(dlg, get_settings_dialog_style(True, conf))
    except Exception:
        pass
    lay = QVBoxLayout(dlg)
    name_row = QHBoxLayout()
    name_row.addWidget(QLabel(tr("Name")))
    name_edit = QLineEdit(grad["name"], dlg)
    name_row.addWidget(name_edit, 1)
    lay.addLayout(name_row)
    host = QWidget(dlg)
    colors_box = QVBoxLayout(host)
    colors_box.setContentsMargins(0, 4, 0, 4)
    lay.addWidget(host)
    stop_row, rem_btn, add_btn, show_strip = stops_row(dlg)
    lay.insertLayout(1, stop_row)  # under the name, over the colors
    foot = QHBoxLayout()
    del_btn = QPushButton(tr("Delete"), dlg)
    foot.addWidget(del_btn)
    foot.addStretch()
    close_btn = QPushButton(tr("Close"), dlg)
    close_btn.setDefault(True)
    foot.addWidget(close_btn)
    lay.addLayout(foot)

    def clear(layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
            elif item.layout() is not None:
                clear(item.layout())

    def set_color(i, color):
        if i < len(grad["colors"]):
            grad["colors"][i] = color
            show_strip(grad["colors"])
            timer.start()

    def build():
        clear(colors_box)
        n = len(grad["colors"])
        for i in range(n):
            _color_row(dlg, colors_box, color_label(i, n),
                       current_fn=lambda i=i: grad["colors"][i] if i < len(grad["colors"]) else "#000000",
                       is_default_fn=lambda: True, set_fn=lambda color, i=i: set_color(i, color),
                       reset_fn=lambda: None, reset_tip="")
        add_btn.setEnabled(n < MAX_COLORS)
        rem_btn.setEnabled(n > MIN_COLORS)
        show_strip(grad["colors"])

    def on_name(text):
        if text.strip():
            grad["name"] = text.strip()
            timer.start()

    def on_add(_checked=False):
        if len(grad["colors"]) < MAX_COLORS:
            grad["colors"].insert(len(grad["colors"]) - 1, mix_hex(grad["colors"][-2], grad["colors"][-1]))
            build()
            timer.start()

    def on_remove(_checked=False):
        if len(grad["colors"]) > MIN_COLORS:
            grad["colors"].pop(len(grad["colors"]) - 2)
            build()
            timer.start()

    def on_delete(_checked=False):
        nonlocal key
        from aqt.utils import askUser

        if not askUser(tr("Delete the gradient {name}?", name=grad["name"]), parent=dlg):
            return
        customs.remove(grad)
        key = ""
        timer.stop()
        save_now()
        dlg.reject()

    name_edit.textChanged.connect(on_name)
    add_btn.clicked.connect(on_add)
    rem_btn.clicked.connect(on_remove)
    del_btn.clicked.connect(on_delete)
    close_btn.clicked.connect(dlg.accept)
    build()
    if new:
        name_edit.setFocus()
        name_edit.selectAll()
    dlg.exec()
    if timer.isActive():
        timer.stop()
        save_now()
    return True
