# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Retention cells drawn as a correct / wrong bar instead of text."""
from aqt import mw

from .. import Config
from ...widgets import SegmentedBarWidget
from ....config import ConfigManager

_KEYS = {
    "all": Config.RETENTION_VISUAL_ALL,
    "young": Config.RETENTION_VISUAL_YOUNG,
    "mature": Config.RETENTION_VISUAL_MATURE,
}


def retention_visual_on(kind):
    """kind is 'all', 'young' or 'mature'."""
    try:
        return bool(ConfigManager(mw).config.get(_KEYS[kind], False))
    except Exception:
        return False


def retention_bar(passed, rev, parent=None, background=None):
    """Bar split in wrong (red) and correct (green), with the percentage on top."""
    from ....qss import set_qss
    from ...widgets.chart_utils.formatting import stats_precision

    pct = (passed / rev * 100) if rev > 0 else 0
    text = "0%" if pct == 0 else f"{pct:.{stats_precision()}f}%"
    bar = SegmentedBarWidget(
        [max(rev - passed, 0), passed],
        parent=parent,
        animate=False,
        labels=["Wrong", "Correct"],
        color_slots=(0, 2),
        center_text=text,
    )
    if background:
        set_qss(bar, f"background-color: {background};")
    return bar
