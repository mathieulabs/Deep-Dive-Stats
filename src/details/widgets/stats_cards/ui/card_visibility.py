# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QGraphicsOpacityEffect


def set_card_opacity(widget, opacity):
    if opacity < 1.0:
        widget._is_ghost = True
        eff = QGraphicsOpacityEffect(widget)
        eff.setOpacity(0.0)
        widget.setGraphicsEffect(eff)
    else:
        widget._is_ghost = False
        widget.setGraphicsEffect(None)
        widget.apply_visual_style()

    from ...pinned.main_menu.manager import MainMenuWidgetManager

    if MainMenuWidgetManager.instance_exists():
        MainMenuWidgetManager.instance().sync_overlay()
