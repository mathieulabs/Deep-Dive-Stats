# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from .fsrs_common import build_simple_fsrs_chart, update_simple_fsrs_chart


def _build_difficulty(widget_def, deck_id, cache=None, parent=None, cfg=None):
    from ....charts.difficulty import DifficultyChartWidget

    return build_simple_fsrs_chart(
        DifficultyChartWidget, "difficulty", "CARD DIFFICULTY", widget_def, deck_id, parent=parent, cfg=cfg
    )


def _update_difficulty(chart, widget_def, deck_id, cache=None, fail_if_not_cached=False, cfg=None):
    return update_simple_fsrs_chart(
        chart, "difficulty", widget_def, deck_id, fail_if_not_cached=fail_if_not_cached, cfg=cfg
    )
