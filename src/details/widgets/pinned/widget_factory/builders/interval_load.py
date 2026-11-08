# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Pinned Interval Load (charts.interval_load): the review intervals data of the decks, the
cards as they are now (no period)."""

from ..utils import _addon_config
from . import ADAPTIVE_CHART_BINNING, Config, Period, pinned_title
from .fsrs_common import add_fsrs_filter_radio
from ..wrapper import _wrap
from ..shared.context import get_pinned_context_value
from ....charts.interval_load import IntervalLoadChart
from ....common import apply_chart_display_config, create_chart_header_for_chart, refresh_parent_chart_header_stats
from ......i18n import N_


def _data(deck_id, cfg, fail_if_not_cached):
    from .....logic.metrics import ReviewIntervalsDataProvider

    _ctx, data = get_pinned_context_value(deck_id, Period.TOTAL, "review_intervals", cfg=cfg,
                                          fail_if_not_cached=fail_if_not_cached)
    if data is None and not fail_if_not_cached:
        data = ReviewIntervalsDataProvider.fetch_data(cfg, deck_id, False, Period.TOTAL)
    return data


def build_interval_load(widget_def, deck_id, cache=None, parent=None, cfg=None):
    cfg = cfg or _addon_config()
    data = _data(deck_id, cfg, fail_if_not_cached=False)
    chart = IntervalLoadChart(data or {}, parent=parent,
                              adaptive_binning=cfg.config.get(ADAPTIVE_CHART_BINNING, True))
    chart._last_deck_id = deck_id
    chart.binning_override = widget_def.get("binning_override", None)
    chart.set_cumulative_mode(widget_def.get("show_cumulative", True))
    apply_chart_display_config(
        chart,
        opacity=widget_def.get("chart_opacity", 100),
        line_opacity=widget_def.get("line_opacity"),
        bar_gradient=widget_def.get("bar_gradient"),
        show_grid=widget_def.get("show_grid"),
        minimum_height=120,
    )
    header_widget, header_lay, _, _stats = create_chart_header_for_chart(
        chart,
        cfg,
        Config.DEEP_DIVE_PINNED_SHOW_BOTTOM_STATS,
        Config.DEEP_DIVE_PINNED_SHOW_STATS,
        parent=parent,
        title=pinned_title(widget_def, N_("Interval Load")),
        title_object_name="pinned_header",
    )
    # The same view choice as Review Intervals (the intervals that make most of the load).
    add_fsrs_filter_radio(chart, widget_def, header_widget, header_lay)
    return _wrap(chart, None, header_widget=header_widget, widget_id=widget_def["id"],
                 saved_w=widget_def.get("width"), saved_h=widget_def.get("height"), parent=parent)


def update_interval_load(chart, widget_def, deck_id, cache=None, fail_if_not_cached=False, cfg=None):
    if not isinstance(chart, IntervalLoadChart):
        return False
    cfg = cfg or _addon_config()
    data = _data(deck_id, cfg, fail_if_not_cached)
    if data is None:
        return False
    chart.binning_override = widget_def.get("binning_override", None)
    chart.set_cumulative_mode(widget_def.get("show_cumulative", True))
    chart.update_data(data, adaptive_binning=cfg.config.get(ADAPTIVE_CHART_BINNING, True))
    chart._last_deck_id = deck_id
    refresh_parent_chart_header_stats(chart)
    return True
