# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Which charts draw a running total (a Total Line option of their own, widget_options.py)."""

from __future__ import annotations

_TOTAL_TYPES = ("activity", "added", "hourly", "future_due", "review_intervals", "stability", "due_today")


def has_total_curve(wtype):
    """A chart drawing a running total (the pale area of Total / Average Lines), so a Total Line of its own."""
    if wtype in _TOTAL_TYPES:
        return True
    try:
        from ....widgets.charts.daily_metrics import BY_TYPE

        m = BY_TYPE.get(wtype)
        return bool(m is not None and m.cumulative and m.unit not in ("level", "seconds"))
    except Exception:
        return False
