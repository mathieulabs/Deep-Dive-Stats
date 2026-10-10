# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from ..utils import _addon_config
from . import pinned_title
from .fsrs_common import add_fsrs_filter_radio
from ..wrapper import _wrap
from . import ADAPTIVE_CHART_BINNING, Config, Period
from ..shared.context import get_pinned_context_value
from ....common import (
    apply_chart_display_config,
    create_chart_header_for_chart,
    refresh_parent_chart_header_stats,
)
from ....charts.common.zoom import (
    get_timespan_transition_meta,
    should_use_timespan_transition,
)

def _build_review_intervals(widget_def, deck_id, cache=None, parent=None, cfg=None):
    from .....logic.metrics import ReviewIntervalsDataProvider
    from ....charts.review_intervals import ReviewIntervalsChart

    config = cfg or _addon_config()
    span = widget_def.get("time_span", Period.YEAR)
    # Align with updater source ordering to avoid startup value changes.
    ctx, data = get_pinned_context_value(
        deck_id,
        span,
        "review_intervals",
        cfg=config,
        allow_slow_ops=False,
    )
    if data is None:
        data = ReviewIntervalsDataProvider.fetch_data(config, deck_id, False, span)

    chart = ReviewIntervalsChart(data, parent=parent)
    chart._last_timespan_token = widget_def.get("_timespan_token", span)
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

    header_widget, header_lay, _, stats_state = create_chart_header_for_chart(
        chart,
        cfg,
        Config.DEEP_DIVE_PINNED_SHOW_BOTTOM_STATS,
        Config.DEEP_DIVE_PINNED_SHOW_STATS,
        parent=parent,
        title=pinned_title(widget_def, "REVIEW INTERVALS"),
        title_object_name="pinned_header",
    )

    add_fsrs_filter_radio(chart, widget_def, header_widget, header_lay)

    return _wrap(
        chart,
        None,
        header_widget=header_widget,
        widget_id=widget_def["id"],
        saved_w=widget_def.get("width"),
        saved_h=widget_def.get("height"),
        parent=parent,
    )


def _update_review_intervals(chart, widget_def, deck_id, cache=None, fail_if_not_cached=False, cfg=None):
    from .....logic.metrics import ReviewIntervalsDataProvider

    config = cfg or _addon_config()
    span = widget_def.get("time_span", Period.YEAR)
    # Non-blocking path (review-return): cache only, never SQL on UI thread.
    ctx, data = get_pinned_context_value(
        deck_id,
        span,
        "review_intervals",
        cfg=config,
        fail_if_not_cached=fail_if_not_cached,
    )
    if data is None and fail_if_not_cached:
        return False
    if data is None:
        data = ReviewIntervalsDataProvider.fetch_data(config, deck_id, False, span)
    if data is None:
        return False
    if hasattr(chart, "update_data"):
        if cfg is None:
            cfg = _addon_config()
        adaptive_binning = cfg.config.get(ADAPTIVE_CHART_BINNING, True)
        current_span_token = widget_def.get("_timespan_token", span)
        transition_meta = get_timespan_transition_meta(
            getattr(chart, "_last_timespan_token", current_span_token),
            current_span_token,
            prev_deck_id=getattr(chart, "_last_deck_id", deck_id),
            current_deck_id=deck_id,
        )
        use_timespan_transition = should_use_timespan_transition(
            transition_meta,
            deck_policy="block",
            extra_trigger=bool(fail_if_not_cached),
        )

        chart.binning_override = widget_def.get("binning_override", None)
        chart.set_cumulative_mode(widget_def.get("show_cumulative", True))
        chart.update_data(
            data,
            adaptive_binning=adaptive_binning,
            transition_mode="timespan" if use_timespan_transition else None,
        )
        chart._last_timespan_token = current_span_token
        chart._last_deck_id = deck_id

        refresh_parent_chart_header_stats(chart)

        return True
    return False
