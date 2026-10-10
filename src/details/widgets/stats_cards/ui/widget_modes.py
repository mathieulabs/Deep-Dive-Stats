# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import Qt

from ....ui import Config
from .....qss import set_qss


def inline_stats_enabled(widget):
    cfg = getattr(widget, "addon_config", {}) or {}
    if getattr(widget, "is_pinned", False):
        return bool(cfg.get(Config.FACECARDS_INLINE_STATS, False))
    return bool(cfg.get(Config.DASHBOARD_INLINE_STATS, False))


def title_size_multiplier(widget):
    cfg = getattr(widget, "addon_config", {}) or {}
    key = Config.FACECARDS_TITLE_SIZE if getattr(widget, "is_pinned", False) else Config.DASHBOARD_TITLE_SIZE
    try:
        raw = float(cfg.get(key, 100))
    except Exception:
        raw = 100.0
    return max(0.5, min(2.0, raw / 100.0))


def apply_inline_layout_mode(widget):
    inline = inline_stats_enabled(widget)
    if getattr(widget, "_inline_mode_active", None) == inline:
        return
    widget._inline_mode_active = inline

    widget._content_grid.removeWidget(widget.title_lbl)
    widget._content_grid.removeWidget(widget.value_lbl)
    if inline:
        widget._content_grid.setHorizontalSpacing(8)
        widget._content_grid.setVerticalSpacing(0)
        widget._content_grid.addWidget(widget.title_lbl, 0, 0)
        widget._content_grid.addWidget(widget.value_lbl, 0, 1)
        widget._content_grid.setColumnStretch(0, 1)
        widget._content_grid.setColumnStretch(1, 0)
    else:
        widget._content_grid.setHorizontalSpacing(0)
        widget._content_grid.setVerticalSpacing(2)
        widget._content_grid.addWidget(widget.title_lbl, 0, 0)
        widget._content_grid.addWidget(widget.value_lbl, 1, 0)
        widget._content_grid.setColumnStretch(0, 0)
        widget._content_grid.setColumnStretch(1, 0)

    widget.set_centered(bool(getattr(widget, "is_pinned", False)))


def set_title_visible(widget, visible: bool):
    if hasattr(widget, "title_lbl"):
        widget.title_lbl.setVisible(visible)

    if not visible:
        if not getattr(widget, "_top_stretch_added", False):
            widget.main_layout.insertStretch(0, 0)
            widget._top_stretch_added = True
    else:
        if getattr(widget, "_top_stretch_added", False):
            item = widget.main_layout.takeAt(0)
            if item:
                del item
            widget._top_stretch_added = False


def set_centered(widget, centered: bool = True):
    inline = bool(getattr(widget, "_inline_mode_active", False))
    if inline:
        widget.title_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        widget.value_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        if getattr(widget, "sub_lbl", None):
            widget.sub_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        set_qss(widget.title_lbl, "font-weight: 700; letter-spacing: 0.8px; padding-left: 0px;")
        set_qss(widget.value_lbl, "font-weight: 800; margin-top: 0px;")
        widget.main_layout.setAlignment(Qt.AlignmentFlag(0))
        widget.update()
        return

    align = Qt.AlignmentFlag.AlignCenter if centered else (Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    widget.title_lbl.setAlignment(align)

    pad = "0px" if centered else "2px"
    set_qss(widget.title_lbl, f"font-weight: 700; letter-spacing: 0.8px; padding-left: {pad};")

    widget.value_lbl.setAlignment(align)
    if getattr(widget, "sub_lbl", None):
        widget.sub_lbl.setAlignment(align)
    set_qss(widget.value_lbl, "font-weight: 800; margin-top: 2px;")
    widget.main_layout.setAlignment(Qt.AlignmentFlag(0))
    widget.update()
