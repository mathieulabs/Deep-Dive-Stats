# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QBoxLayout, QHBoxLayout, QVBoxLayout, QWidget
from ....qss import set_qss


def _build_layout_container(
    layout_cls,
    parent=None,
    *,
    margins=(0, 0, 0, 0),
    spacing=None,
    alignment=None,
    transparent=False,
    object_name=None,
):
    widget = QWidget(parent)
    if object_name:
        widget.setObjectName(str(object_name))
    if transparent:
        set_qss(widget, "background: transparent;")

    layout = layout_cls(widget)
    layout.setContentsMargins(*margins)
    if spacing is not None:
        layout.setSpacing(int(spacing))
    if alignment is not None and isinstance(layout, QBoxLayout):
        layout.setAlignment(alignment)
    return widget, layout


def create_hbox_container(
    parent=None,
    *,
    margins=(0, 0, 0, 0),
    spacing=None,
    alignment=None,
    transparent=False,
    object_name=None,
):
    return _build_layout_container(
        QHBoxLayout,
        parent,
        margins=margins,
        spacing=spacing,
        alignment=alignment,
        transparent=transparent,
        object_name=object_name,
    )


def create_vbox_container(
    parent=None,
    *,
    margins=(0, 0, 0, 0),
    spacing=None,
    alignment=None,
    transparent=False,
    object_name=None,
):
    return _build_layout_container(
        QVBoxLayout,
        parent,
        margins=margins,
        spacing=spacing,
        alignment=alignment,
        transparent=transparent,
        object_name=object_name,
    )
