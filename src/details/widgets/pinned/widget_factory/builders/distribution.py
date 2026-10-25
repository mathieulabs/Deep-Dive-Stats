# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from ..utils import _addon_config
from . import pinned_title
from . import Period
from ..shared.reviews import load_distribution_source
from ....charts.grouped_bar import GroupedBarWidget
from ....common import apply_chart_display_config
from ..wrapper import _wrap

def _build_distribution(widget_def, deck_id, cache=None, parent=None, cfg=None):
    span = widget_def.get("time_span", Period.TOTAL)
    days = widget_def.get("custom_days", 7)
    source = load_distribution_source(
        deck_id,
        span,
        cache=cache,
        cfg=cfg or _addon_config(),
        custom_days=days,
        fail_if_not_cached=True,
    )
    dist_data = source["distribution_data"]

    chart = GroupedBarWidget(dist_data, parent=parent)
    apply_chart_display_config(
        chart,
        opacity=widget_def.get("chart_opacity", 100),
        line_opacity=widget_def.get("line_opacity"),
        bar_gradient=widget_def.get("bar_gradient"),
        show_grid=widget_def.get("show_grid"),
        minimum_height=120,
    )

    display_label = pinned_title(widget_def, "DISTRIBUTION").upper()
    return _wrap(chart, display_label,
                 widget_id=widget_def["id"],
                 saved_w=widget_def.get("width"),
                 saved_h=widget_def.get("height"),
                 parent=parent)

def _update_distribution(chart, widget_def, deck_id, cache=None, fail_if_not_cached=False, cfg=None):
    span = widget_def.get("time_span", Period.TOTAL)
    days = widget_def.get("custom_days", 7)
    source = load_distribution_source(
        deck_id,
        span,
        cache=cache,
        cfg=cfg,
        custom_days=days,
        fail_if_not_cached=fail_if_not_cached,
    )
    if source["history_is_none"]:
        return False
    dist_data = source["distribution_data"]
    if hasattr(chart, "update_data"):
        if hasattr(chart, "_initial_animation_done"):
            chart._initial_animation_done = True
        chart.update_data(dist_data)
        return True
    return False

