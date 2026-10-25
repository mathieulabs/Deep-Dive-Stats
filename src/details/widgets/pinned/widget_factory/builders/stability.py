# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from ..wrapper import _wrap
from . import pinned_title
from .fsrs_common import add_fsrs_filter_radio, fetch_fsrs_data
from . import ADAPTIVE_CHART_BINNING, Config
from ....common import (
    apply_chart_display_config,
    create_chart_header_for_chart,
    refresh_parent_chart_header_stats,
)
from ....charts.common.zoom import (
    get_timespan_transition_meta,
    should_use_timespan_transition,
)



def _build_stability(widget_def, deck_id, cache=None, parent=None, cfg=None):
    from ....charts.stability import StabilityChartWidget

    if cfg is None:
        from ..utils import _addon_config
        cfg = _addon_config()
    cfg = _addon_config() if cfg is None else cfg
    adaptive_binning = cfg.config.get(ADAPTIVE_CHART_BINNING, True)
    # Not cached yet: start empty, the data comes with the next update (as the other FSRS charts).
    fsrs_data = fetch_fsrs_data(deck_id, cfg, fail_if_not_cached=True) or {}

    chart = StabilityChartWidget(fsrs_data.get("stability", {}), parent=parent, adaptive_binning=adaptive_binning)
    chart._last_timespan_token = widget_def.get("_timespan_token", widget_def.get("time_span"))
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
        title=pinned_title(widget_def, "CARD STABILITY"),
        title_object_name="pinned_header",
    )

    add_fsrs_filter_radio(chart, widget_def, header_widget, header_lay)

    return _wrap(chart, None,
                 header_widget=header_widget,
                 widget_id=widget_def["id"],
                 saved_w=widget_def.get("width"),
                 saved_h=widget_def.get("height"),
                 parent=parent)


def _update_stability(chart, widget_def, deck_id, cache=None, fail_if_not_cached=False, cfg=None):
    fsrs_data = fetch_fsrs_data(deck_id, cfg, fail_if_not_cached=fail_if_not_cached)
    if fsrs_data is None:
        return False
    if hasattr(chart, "update_data"):
        if cfg is None:
            from ..utils import _addon_config
            cfg = _addon_config()
        adaptive_binning = cfg.config.get(ADAPTIVE_CHART_BINNING, True)
        current_span_token = widget_def.get("_timespan_token", widget_def.get("time_span"))
        transition_meta = get_timespan_transition_meta(
            getattr(chart, "_last_timespan_token", current_span_token),
            current_span_token,
            prev_deck_id=getattr(chart, "_last_deck_id", deck_id),
            current_deck_id=deck_id,
        )
        # Match breakdown-like behavior: deck switches should also use timespan morph.
        use_timespan_transition = should_use_timespan_transition(
            transition_meta,
            deck_policy="force",
            extra_trigger=bool(fail_if_not_cached),
        )

        chart.binning_override = widget_def.get("binning_override", None)
        chart.set_cumulative_mode(widget_def.get("show_cumulative", True))
        chart.update_data(
            fsrs_data.get("stability", {}),
            adaptive_binning=adaptive_binning,
            transition_mode="timespan" if use_timespan_transition else None,
        )
        chart._last_timespan_token = current_span_token
        chart._last_deck_id = deck_id

        refresh_parent_chart_header_stats(chart)

        return True
    return False




