# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from ..wrapper import _wrap
from . import pinned_title
from ..utils import _addon_config
from . import Config, Period
from ..shared.context import get_pinned_context_value
from ....common import (
    apply_chart_display_config,
    create_chart_header_for_chart,
    refresh_parent_chart_header_stats,
)



def _build_hourly(widget_def, deck_id, cache=None, parent=None, cfg=None):
    from .....logic.metrics import HourlyDataProvider
    from ....charts.hourly import HourlyBreakdownChart

    config = cfg or _addon_config()
    span = widget_def.get("time_span", Period.YEAR)
    _, data = get_pinned_context_value(
        deck_id,
        span,
        "hourly",
        cfg=config,
        allow_slow_ops=False,
    )
    data = data or HourlyDataProvider.fetch_data(config, deck_id, False, span)

    chart = HourlyBreakdownChart(data, parent=parent)
    chart._bc_span = span
    apply_chart_display_config(
        chart,
        opacity=widget_def.get("chart_opacity", 100),
        line_opacity=widget_def.get("line_opacity"),
        bar_gradient=widget_def.get("bar_gradient"),
        show_grid=widget_def.get("show_grid"),
        minimum_height=120,
    )

    label = pinned_title(widget_def, "HOURLY BREAKDOWN")
    header_widget, _, _, _ = create_chart_header_for_chart(
        chart,
        config,
        Config.DEEP_DIVE_PINNED_SHOW_BOTTOM_STATS,
        Config.DEEP_DIVE_PINNED_SHOW_STATS,
        parent=parent,
        title=label,
        title_object_name="pinned_header",
        include_when_no_header_stats=False,
    )

    return _wrap(chart, label.upper() if not header_widget else None,
                 header_widget=header_widget,
                 widget_id=widget_def["id"],
                 saved_w=widget_def.get("width"),
                 saved_h=widget_def.get("height"),
                 parent=parent)


def _update_hourly(chart, widget_def, deck_id, cache=None, fail_if_not_cached=False, cfg=None):
    from .....logic.metrics import HourlyDataProvider

    config = cfg or _addon_config()
    span = widget_def.get("time_span", Period.YEAR)
    chart._bc_span = span
    _, data = get_pinned_context_value(
        deck_id,
        span,
        "hourly",
        cfg=config,
        fail_if_not_cached=fail_if_not_cached,
    )
    if data is None and fail_if_not_cached:
        return False
    if data is None:
        data = HourlyDataProvider.fetch_data(config, deck_id, False, span)
    if data is None:
        return False
    if hasattr(chart, "update_data"):
        chart.update_data(data)

        refresh_parent_chart_header_stats(chart)

        return True
    return False
