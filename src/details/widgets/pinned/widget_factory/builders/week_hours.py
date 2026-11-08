# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Pinned Week by Hour (charts.week_hours): when the reviews of the widget's period and decks
were answered, by day of the week and hour."""

from ..utils import _addon_config
from . import Config, pinned_title
from ..wrapper import _wrap
from .daily_metrics import _days
from ....charts.week_hours import LABEL, WeekHoursChart
from ....common import apply_chart_display_config, create_chart_header_for_chart, refresh_parent_chart_header_stats


def build_week_hours(widget_def, deck_id, cache=None, parent=None, cfg=None):
    cfg = cfg or _addon_config()
    days = _days(widget_def, deck_id, cache, cfg, fail_if_not_cached=True)
    chart = WeekHoursChart(cfg, parent=parent, owner="pinned")
    chart.set_source(cfg, deck_id, False)
    chart.set_payload(days or [])
    chart._last_deck_id = deck_id
    apply_chart_display_config(
        chart,
        opacity=widget_def.get("chart_opacity", 100),
        line_opacity=widget_def.get("line_opacity"),
        bar_gradient=widget_def.get("bar_gradient"),
        show_grid=widget_def.get("show_grid"),
        tooltip_hidden=widget_def.get("tooltip_hidden"),
        minimum_height=120,
    )
    header_widget, _header_lay, _, _stats_state = create_chart_header_for_chart(
        chart,
        cfg,
        Config.DEEP_DIVE_PINNED_SHOW_BOTTOM_STATS,
        Config.DEEP_DIVE_PINNED_SHOW_STATS,
        parent=parent,
        title=pinned_title(widget_def, LABEL),
        title_object_name="pinned_header",
    )
    wrapped = _wrap(chart, None, header_widget=header_widget, widget_id=widget_def["id"],
                    saved_w=widget_def.get("width"), saved_h=widget_def.get("height"), parent=parent)
    if days is None and wrapped is not None:
        wrapped._is_loading = True  # not in the cache yet: the rebuild loads it in the background
    return wrapped


def update_week_hours(chart, widget_def, deck_id, cache=None, fail_if_not_cached=False, cfg=None):
    if not isinstance(chart, WeekHoursChart):
        return False
    cfg = cfg or _addon_config()
    days = _days(widget_def, deck_id, cache, cfg, fail_if_not_cached)
    if days is None:
        return False
    chart.set_source(cfg, deck_id, False)
    chart.set_payload(days)
    chart._last_deck_id = deck_id
    refresh_parent_chart_header_stats(chart)
    return True
