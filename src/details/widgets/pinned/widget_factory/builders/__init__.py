# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Builder modules for pinned widget factory."""

from .....ui import ADAPTIVE_CHART_BINNING, Config, Period, rollover_hour, get_color, get_svg_icon
from .....logic.history_provider import HistoryProvider
from .....logic import log_debug

__all__ = [
    "ADAPTIVE_CHART_BINNING",
    "Config",
    "HistoryProvider",
    "Period",
    "rollover_hour",
    "get_color",
    "get_svg_icon",
    "log_debug",
]


def pinned_title(widget_def, default):
    """Title of a pinned chart. An emptied label means no title at all."""
    label = widget_def.get("label")
    if label is None:
        return default
    return label if str(label).strip() else ""
