# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors


class ChartGeometry:
    MARGIN_LEFT = 35
    MARGIN_TOP = 10
    MARGIN_BOTTOM = 30
    DEFAULT_MARGIN_RIGHT = 20

    STATS_EXTRA_HEIGHT = {
        "future_due": 90,
        "review_intervals": 70,
        "stability": 70,
        "difficulty": 70,
        "retrievability": 90,
        "activity": 70,
        "retention": 70,
        "added": 70,
        "hourly": 50,
        "card_counts": 0, # Pie charts don't have bottom stats
        "heatmap": 0
    }


