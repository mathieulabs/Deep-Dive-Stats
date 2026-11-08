# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Pinned Due Today by Hour (charts.due_today): the learning cards due today, as they are
now (no period)."""

from ..utils import _addon_config
from . import ADAPTIVE_CHART_BINNING, Config, pinned_title
from ..wrapper import _wrap
from ....charts.due_today import METRIC, DueTodayChart, fetch
from ....common import (
    apply_chart_display_config,
    connect_chart_header_refresh,
    create_chart_header_for_chart,
    refresh_parent_chart_header_stats,
)


def build_due_today(widget_def, deck_id, cache=None, parent=None, cfg=None):
    cfg = cfg or _addon_config()
    chart = DueTodayChart(fetch(cfg, deck_id), cfg, parent=parent,
                          adaptive_binning=cfg.config.get(ADAPTIVE_CHART_BINNING, True), owner="pinned")
    chart._last_deck_id = deck_id
    chart.set_source(cfg, deck_id)
    chart.apply_options(False, False, widget_def.get("show_cumulative", True))
    chart.set_hidden_series(widget_def.get("hidden_series"))
    apply_chart_display_config(
        chart,
        opacity=widget_def.get("chart_opacity", 100),
        line_opacity=widget_def.get("line_opacity"),
        bar_gradient=widget_def.get("bar_gradient"),
        show_grid=widget_def.get("show_grid"),
        tooltip_hidden=widget_def.get("tooltip_hidden"),
        minimum_height=120,
    )
    header_widget, _header_lay, _, stats_state = create_chart_header_for_chart(
        chart,
        cfg,
        Config.DEEP_DIVE_PINNED_SHOW_BOTTOM_STATS,
        Config.DEEP_DIVE_PINNED_SHOW_STATS,
        parent=parent,
        title=pinned_title(widget_def, METRIC.label),
        title_object_name="pinned_header",
    )
    connect_chart_header_refresh(chart, header_widget, enabled=stats_state["show_header_stats"])
    return _wrap(chart, None, header_widget=header_widget, widget_id=widget_def["id"],
                 saved_w=widget_def.get("width"), saved_h=widget_def.get("height"), parent=parent)


def update_due_today(chart, widget_def, deck_id, cache=None, fail_if_not_cached=False, cfg=None):
    if not isinstance(chart, DueTodayChart):
        return False
    cfg = cfg or _addon_config()
    chart.apply_options(False, False, widget_def.get("show_cumulative", True))
    chart.set_source(cfg, deck_id)
    chart.set_hidden_series(widget_def.get("hidden_series"))
    chart.set_payload(fetch(cfg, deck_id))
    chart._last_deck_id = deck_id
    refresh_parent_chart_header_stats(chart)
    return True
