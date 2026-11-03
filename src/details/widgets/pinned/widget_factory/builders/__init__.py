# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Builder modules for pinned widget factory."""

from .....ui import ADAPTIVE_CHART_BINNING, Config, Period, rollover_hour, get_color, get_svg_icon
from .....logic.history_provider import HistoryProvider
from .....logic import log_debug
from ......i18n import tr_name, upper

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
    """Title of a pinned chart. An emptied label means no title at all.

    default is the English name (marked with N_), shown in capitals and translated; a
    saved label goes through tr_name() (default names are saved in English)."""
    label = widget_def.get("label")
    if label is None:
        return upper(tr_name(default))
    return tr_name(label) if str(label).strip() else ""
