# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Pinned widgets of the charts read from the review history of each day (Ratings, Review
Speed, Forgotten: see charts.daily_metrics)."""

from ..utils import _addon_config
from . import ADAPTIVE_CHART_BINNING, Config, Period, pinned_title
from ..wrapper import _wrap
from ..shared.header import add_pinned_zoom_reset_button, prepare_pinned_header
from ..shared.reviews import load_activity_source
from ....charts.common.zoom import get_timespan_transition_meta, timespan_transition_mode
from ....charts.daily_metrics import BY_TYPE, DailyMetricChart
from ....chart_utils.zoom_camera import with_camera
from ....common import (
    apply_chart_display_config,
    connect_chart_header_refresh,
    create_chart_header_for_chart,
    refresh_parent_chart_header_stats,
)


def _days(widget_def, deck_id, cache, cfg, fail_if_not_cached):
    """The day rows of the widget's decks and period, oldest first (None: still loading)."""
    source = load_activity_source(
        deck_id,
        widget_def.get("time_span", Period.TOTAL),
        cache=cache,
        cfg=cfg,
        custom_days=widget_def.get("custom_days", 7),
        fail_if_not_cached=fail_if_not_cached,
        allow_context_slow_ops=False,
    )
    if source.get("history_is_none"):
        return None
    return source.get("raw_hist") or []


def build_daily_metric(widget_def, deck_id, cache=None, parent=None, cfg=None):
    cfg = cfg or _addon_config()
    metric = BY_TYPE[widget_def.get("type")]
    days = _days(widget_def, deck_id, cache, cfg, fail_if_not_cached=True)
    chart = DailyMetricChart(metric, days or [], cfg, parent=parent,
                             adaptive_binning=cfg.config.get(ADAPTIVE_CHART_BINNING, True), owner="pinned",
                             source=(deck_id, False), alt=bool(widget_def.get("alt_view", False)))
    chart._last_timespan_token = widget_def.get("_timespan_token", 0)
    chart._last_deck_id = deck_id
    chart.binning_override = widget_def.get("binning_override", None)
    chart.apply_options(widget_def.get("show_average", True), widget_def.get("avg_on_active_days", True),
                        widget_def.get("show_cumulative", True))
    if chart.metric.percent:
        chart.set_percent_mode(bool(widget_def.get("show_percent", False)))
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
    header_widget, header_lay, _, stats_state = create_chart_header_for_chart(
        chart,
        cfg,
        Config.DEEP_DIVE_PINNED_SHOW_BOTTOM_STATS,
        Config.DEEP_DIVE_PINNED_SHOW_STATS,
        parent=parent,
        title=pinned_title(widget_def, metric.label),
        title_object_name="pinned_header",
    )
    prepare_pinned_header(header_widget, header_lay)
    if metric.alt:
        # The other split of the same bars (Introduced: "By First Rating").
        from ..utils import _make_checkbox
        from ......i18n import tr_name

        alt_cb = _make_checkbox(tr_name(metric.alt[0]), checked=bool(widget_def.get("alt_view", False)),
                                parent=header_widget)

        def _on_alt(checked):
            from ...store.registry import WidgetRegistry

            chart.set_alt(checked)
            refresh_parent_chart_header_stats(chart)
            WidgetRegistry.update_setting(widget_def["id"], "alt_view", bool(checked))

        alt_cb.toggled.connect(_on_alt)
        header_lay.addWidget(alt_cb)
    # The zoom reset, as on the other charts of days (and the linked charts with it).
    btn_reset = add_pinned_zoom_reset_button(header_widget, header_lay, retain_size_when_hidden=False)

    def _reset_clicked():
        chart.reset_zoom()
        from ...zoom_link import propagate_reset

        propagate_reset(chart)

    btn_reset.clicked.connect(with_camera(_reset_clicked))
    chart.zoom_changed.connect(lambda zoomed, _s, _e: btn_reset.setVisible(bool(zoomed)))
    connect_chart_header_refresh(chart, header_widget, enabled=stats_state["show_header_stats"])

    wrapped = _wrap(chart, None, header_widget=header_widget,
                    widget_id=widget_def["id"],
                    saved_w=widget_def.get("width"),
                    saved_h=widget_def.get("height"),
                    parent=parent)
    if days is None and wrapped is not None:
        # Not in the cache yet: the rebuild loads it in the background (else it stays empty).
        wrapped._is_loading = True
    return wrapped


def update_daily_metric(chart, widget_def, deck_id, cache=None, fail_if_not_cached=False, cfg=None):
    if not hasattr(chart, "set_days"):
        return False
    cfg = cfg or _addon_config()
    days = _days(widget_def, deck_id, cache, cfg, fail_if_not_cached)
    if days is None:
        return False
    chart.set_source(deck_id, False)
    span = widget_def.get("time_span", Period.TOTAL)
    span_token = widget_def.get("_timespan_token", 0)
    # Another period: the bars slide to it; another deck: no slide (other data).
    meta = get_timespan_transition_meta(
        getattr(chart, "_last_timespan_token", span_token),
        span_token,
        prev_deck_id=getattr(chart, "_last_deck_id", deck_id),
        current_deck_id=deck_id,
        old_series=getattr(chart, "_full_data", []),
        new_series=chart.rows_for(days),
        total_span_active=(int(span if span is not None else Period.TOTAL) == int(Period.TOTAL)),
    )
    chart.binning_override = widget_def.get("binning_override", None)
    chart.apply_options(widget_def.get("show_average", True), widget_def.get("avg_on_active_days", True),
                        widget_def.get("show_cumulative", True))
    if chart.metric.percent:
        chart.set_percent_mode(bool(widget_def.get("show_percent", False)))
    chart.set_hidden_series(widget_def.get("hidden_series"))
    chart.set_days(days, adaptive_binning=cfg.config.get(ADAPTIVE_CHART_BINNING, True),
                   transition_mode=timespan_transition_mode(meta, deck_policy="block"))
    chart._last_timespan_token = span_token
    chart._last_deck_id = deck_id
    refresh_parent_chart_header_stats(chart)
    return True
