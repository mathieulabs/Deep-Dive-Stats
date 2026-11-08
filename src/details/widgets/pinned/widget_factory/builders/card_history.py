# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Pinned charts of the cards by number of lapses / reviews (charts.card_history): the
cards as they are now (no period)."""

from ..utils import _addon_config
from . import ADAPTIVE_CHART_BINNING, Config, pinned_title
from .fsrs_common import add_fsrs_filter_radio
from ..wrapper import _wrap
from ....charts.card_history import CardCountChart, card_distribution
from ....charts.more_charts import BY_TYPE
from ....common import apply_chart_display_config, create_chart_header_for_chart, refresh_parent_chart_header_stats


def build_card_history(widget_def, deck_id, cache=None, parent=None, cfg=None):
    cfg = cfg or _addon_config()
    wtype = widget_def.get("type")
    chart = CardCountChart(wtype, card_distribution(cfg, deck_id, wtype), parent=parent,
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
        title=pinned_title(widget_def, BY_TYPE[wtype].label),
        title_object_name="pinned_header",
    )
    # The same view choice as Review Intervals (the most common values, or all of them).
    add_fsrs_filter_radio(chart, widget_def, header_widget, header_lay)
    return _wrap(chart, None, header_widget=header_widget, widget_id=widget_def["id"],
                 saved_w=widget_def.get("width"), saved_h=widget_def.get("height"), parent=parent)


def update_card_history(chart, widget_def, deck_id, cache=None, fail_if_not_cached=False, cfg=None):
    if not isinstance(chart, CardCountChart):
        return False
    cfg = cfg or _addon_config()
    chart.binning_override = widget_def.get("binning_override", None)
    chart.set_cumulative_mode(widget_def.get("show_cumulative", True))
    chart.update_data(card_distribution(cfg, deck_id, widget_def.get("type")),
                      adaptive_binning=cfg.config.get(ADAPTIVE_CHART_BINNING, True))
    chart._last_deck_id = deck_id
    refresh_parent_chart_header_stats(chart)
    return True
