# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QPushButton, QSizePolicy, Qt

from ..builders import get_svg_icon
from ......qss import set_qss


def prepare_pinned_header(header_widget, header_layout, *, spacing=8):
    if header_widget is not None:
        set_qss(header_widget, "background: transparent;")
    if header_layout is not None:
        header_layout.setSpacing(int(spacing))


def add_pinned_zoom_reset_button(
    header_widget,
    header_layout,
    *,
    retain_size_when_hidden=False,
):
    btn_reset = QPushButton("", parent=header_widget)
    btn_reset.setIcon(get_svg_icon("rotate-ccw", size=14))
    btn_reset.setFixedSize(20, 20)
    btn_reset.setCursor(Qt.CursorShape.PointingHandCursor)
    btn_reset.setToolTip("Reset Zoom")
    btn_reset.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    btn_reset.setVisible(False)
    set_qss(btn_reset,
        """
        QPushButton { background: transparent; border: none; padding: 2px; }
        QPushButton:hover { background: rgba(255,255,255,0.1); border-radius: 4px; }
    """
    )
    btn_reset.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    if retain_size_when_hidden:
        sp = btn_reset.sizePolicy()
        sp.setRetainSizeWhenHidden(True)
        btn_reset.setSizePolicy(sp)
    if header_layout is not None:
        header_layout.addWidget(btn_reset)
    return btn_reset
