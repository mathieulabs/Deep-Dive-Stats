# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from .fsrs_common import build_simple_fsrs_chart, update_simple_fsrs_chart


def _build_retrievability(widget_def, deck_id, cache=None, parent=None, cfg=None):
    from ....charts.retrievability import RetrievabilityChartWidget

    return build_simple_fsrs_chart(
        RetrievabilityChartWidget, "retrievability", "CARD RETRIEVABILITY", widget_def, deck_id, parent=parent, cfg=cfg
    )


def _update_retrievability(chart, widget_def, deck_id, cache=None, fail_if_not_cached=False, cfg=None):
    return update_simple_fsrs_chart(
        chart, "retrievability", widget_def, deck_id, fail_if_not_cached=fail_if_not_cached, cfg=cfg
    )
