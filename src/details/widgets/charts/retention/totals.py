# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Review totals of each retention series, as a tooltip on its checkbox."""
from ...chart_utils.formatting import fmt_num
from .....i18n import tr, tr_name


def bind_totals(chart, checkboxes):
    """Keep each checkbox tooltip in step with the reviews the chart shows.

    checkboxes: {series key: QCheckBox}. Follows zoom, time span, decks and data
    refreshes, because it reads the same window the chart draws."""

    def refresh():
        totals = chart.series_totals()
        for key, cb in checkboxes.items():
            try:
                label = tr_name(chart.SERIES_CONFIG[key]["label"])
                passed, reviews = totals.get(key, (0, 0))
                cb.setToolTip(
                    tr("{name}: {reviews} reviews, {passed} passed", name=label, reviews=fmt_num(reviews), passed=fmt_num(passed))
                    if reviews > 0 else label
                )
            except RuntimeError:
                return

    chart.totals_changed.connect(refresh)
    refresh()
