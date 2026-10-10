# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QColor


def get_review_button_colors(widget, *, as_qcolor=False):
    from .....ui import Config, get_chart_color

    colors = [
        get_chart_color(Config.COLOR_AGAIN, widget),
        get_chart_color(Config.COLOR_HARD, widget),
        get_chart_color(Config.COLOR_GOOD, widget),
        get_chart_color(Config.COLOR_EASY, widget),
    ]
    if as_qcolor:
        return [QColor(color) for color in colors]
    return colors
