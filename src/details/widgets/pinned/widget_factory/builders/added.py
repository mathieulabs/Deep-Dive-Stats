# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from ..utils import _addon_config
from . import pinned_title
from ..wrapper import _wrap
from . import ADAPTIVE_CHART_BINNING, Config, Period
from ..shared.header import add_pinned_zoom_reset_button, prepare_pinned_header
from ..shared.reviews import load_added_source
from ....charts.added_chart import AddedChartWidget
from ....charts.common.zoom import (
    get_timespan_transition_meta,
    should_use_timespan_transition,
)
from ....common import (
    apply_chart_display_config,
    connect_chart_header_refresh,
    create_chart_header_for_chart,
    refresh_parent_chart_header_stats,
)
from ....chart_utils.zoom_camera import with_camera


def _build_added(widget_def, deck_id, cache=None, parent=None, cfg=None):
    config = cfg or _addon_config()
    span = widget_def.get("time_span", Period.TOTAL)
    days = widget_def.get("custom_days", 7)
    source = load_added_source(
        deck_id,
        span,
        cache=cache,
        cfg=config,
        custom_days=days,
        fail_if_not_cached=True,
    )
    added_data = source["oldest_first"]
    
    if cfg is None:
        cfg = _addon_config()
    adaptive_binning = cfg.config.get(ADAPTIVE_CHART_BINNING, True)

    chart = AddedChartWidget(added_data, parent=parent, adaptive_binning=adaptive_binning)
    chart._chart_owner = "added"
    chart.binning_override = widget_def.get("binning_override", None)
    chart._last_time_span = span
    chart._last_timespan_token = widget_def.get("_timespan_token", 0)
    chart._last_deck_id = deck_id
    apply_chart_display_config(
        chart,
        opacity=widget_def.get("chart_opacity", 100),
        line_opacity=widget_def.get("line_opacity"),
        bar_gradient=widget_def.get("bar_gradient"),
        show_grid=widget_def.get("show_grid"),
        minimum_height=120,
    )
    chart.set_average_mode(
        widget_def.get("show_average", True),
        widget_def.get("avg_on_active_days", True),
    )
    chart.set_cumulative_mode(widget_def.get("show_cumulative", True))

    header_widget, header_lay, _, stats_state = create_chart_header_for_chart(
        chart,
        config,
        Config.DEEP_DIVE_PINNED_SHOW_BOTTOM_STATS,
        Config.DEEP_DIVE_PINNED_SHOW_STATS,
        parent=parent,
        title=pinned_title(widget_def, "ADDED"),
        title_object_name="pinned_header",
    )
    prepare_pinned_header(header_widget, header_lay)
    btn_reset = add_pinned_zoom_reset_button(
        header_widget,
        header_lay,
        retain_size_when_hidden=False,
    )
    def _added_reset_clicked():
        chart.reset_zoom()
        from ...zoom_link import propagate_reset
        propagate_reset(chart)
    _added_reset_clicked = with_camera(_added_reset_clicked)

    btn_reset.clicked.connect(_added_reset_clicked)
    
    if hasattr(chart, 'zoom_changed'):
        chart.zoom_changed.connect(lambda z, s, e: btn_reset.setVisible(z))
        connect_chart_header_refresh(
            chart,
            header_widget,
            enabled=stats_state["show_header_stats"],
        )

    return _wrap(chart, None, header_widget=header_widget,
                 widget_id=widget_def["id"],
                 saved_w=widget_def.get("width"),
                 saved_h=widget_def.get("height"),
                 parent=parent)

def _update_added(chart, widget_def, deck_id, cache=None, fail_if_not_cached=False, cfg=None):
    span = widget_def.get("time_span", Period.TOTAL)
    days = widget_def.get("custom_days", 7)
    source = load_added_source(
        deck_id,
        span,
        cache=cache,
        cfg=cfg,
        custom_days=days,
        fail_if_not_cached=fail_if_not_cached,
    )
    if source["history_is_none"]:
        return False
    oldest_first = source["oldest_first"]
    
    show_avg = widget_def.get("show_average", True)
    show_total = widget_def.get("show_cumulative", True)
    avg_on_active = widget_def.get("avg_on_active_days", True)
    
    if hasattr(chart, "update_data"):
        chart._chart_owner = "added"
        if cfg is None:
             cfg = _addon_config()
        adaptive_binning = cfg.config.get(ADAPTIVE_CHART_BINNING, True)

        span_token = widget_def.get("_timespan_token", 0)
        transition_meta = get_timespan_transition_meta(
            getattr(chart, "_last_timespan_token", span_token),
            span_token,
            prev_deck_id=getattr(chart, "_last_deck_id", deck_id),
            current_deck_id=deck_id,
            old_series=getattr(chart, "_full_data", []),
            new_series=oldest_first,
            total_span_active=(int(span) == int(Period.TOTAL)),
        )
        use_timespan_transition = should_use_timespan_transition(
            transition_meta,
            deck_policy="block",
        )
        
        chart.set_average_mode(show_avg, avg_on_active)
        chart.set_cumulative_mode(show_total)
        chart.binning_override = widget_def.get("binning_override", None)
        chart.update_data(
            oldest_first,
            adaptive_binning=adaptive_binning,
            transition_mode="timespan" if use_timespan_transition else None,
        )
        chart._last_time_span = span
        chart._last_timespan_token = span_token
        chart._last_deck_id = deck_id
        
        refresh_parent_chart_header_stats(chart)
                
        return True
    return False



