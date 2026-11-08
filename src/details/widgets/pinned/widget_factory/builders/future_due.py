# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from ..utils import _addon_config, _make_radio_group, _make_checkbox
from . import pinned_title
from ..wrapper import _wrap
from . import ADAPTIVE_CHART_BINNING, Config, Period
from .....animations.chart_policy import local_chart_animation_batch
from ....common import (
    resolve_future_due_ranges,
    apply_chart_display_config,
    create_chart_header_for_chart,
    refresh_parent_chart_header_stats,
    resolve_future_due_choice,
)
from ......i18n import tr, N_



def _build_future_due(widget_def, deck_id, cache=None, parent=None, cfg=None):
    from .....logic.metrics import FutureDueDataProvider
    from ....charts.future_due import FutureDueChart

    config = cfg or _addon_config()
    span = widget_def.get("time_span", Period.YEAR)
    show_backlog = widget_def.get("show_backlog", False)
    from .....logic.metrics.future_due import resolve_breakdown

    bd_mode = resolve_breakdown(widget_def.get("breakdown"), widget_def.get("show_breakdown", False))
    # fetch_data uses GlobalHistoryCache internally for the distribution,
    # then adds the backlog SQL if needed - no need for a separate cache shortcut
    data = FutureDueDataProvider.fetch_data(config, deck_id, False, span, include_backlog=show_backlog, breakdown=bd_mode,
                                            hidden_parts=widget_def.get("hidden_series") or ())

    adaptive_binning = config.config.get(ADAPTIVE_CHART_BINNING, True)

    chart = FutureDueChart(data, parent=parent, adaptive_binning=adaptive_binning, show_backlog=show_backlog)
    chart.binning_override = widget_def.get("binning_override", None)
    chart.tooltip_hidden = list(widget_def.get("tooltip_hidden") or [])
    chart.set_percent_mode(bool(widget_def.get("show_percent", False)), animate=False)
    chart.set_cumulative_mode(widget_def.get("show_cumulative", True))
    apply_chart_display_config(
        chart,
        opacity=widget_def.get("chart_opacity", 100),
        line_opacity=widget_def.get("line_opacity"),
        bar_gradient=widget_def.get("bar_gradient"),
        show_grid=widget_def.get("show_grid"),
        minimum_height=120,
    )

    header_widget, header_lay, _, _ = create_chart_header_for_chart(
        chart,
        config,
        Config.DEEP_DIVE_PINNED_SHOW_BOTTOM_STATS,
        Config.DEEP_DIVE_PINNED_SHOW_STATS,
        parent=parent,
        title=pinned_title(widget_def, N_("Future Due")),
        title_object_name="pinned_header",
    )

    default_range = widget_def.get("time_span", Period.YEAR)
    fd_ranges, fd_short, _ = resolve_future_due_ranges(widget_def.get("radio_ranges"))
    default_idx, _, _ = resolve_future_due_choice(fallback_range=default_range, default_idx=2, ranges=fd_ranges)

    state = {"range_idx": default_idx, "deck_id": deck_id, "backlog": bool(show_backlog), "breakdown": bd_mode}
    chart._pinned_state = state

    def _refetch(transition_mode=None):
        new_data = FutureDueDataProvider.fetch_data(
            config, state.get("deck_id", deck_id), False, fd_ranges[state["range_idx"]],
            include_backlog=state["backlog"], breakdown=state["breakdown"],
            hidden_parts=widget_def.get("hidden_series") or (),
        )
        chart.show_backlog = state["backlog"]
        with local_chart_animation_batch(chart):
            chart.update_data(new_data, transition_mode=transition_mode)
        refresh_parent_chart_header_stats(chart)

    # "Breakdown": the bars split in three, by type (learning / young / mature) or by
    # result (the reviews FSRS expects you to pass / fail), chosen in the button's menu.
    from ....charts.future_due.breakdown_button import setup_breakdown_button

    def on_breakdown(kind):
        from ...store.registry import WidgetRegistry

        state["breakdown"] = kind
        _refetch(transition_mode="timespan")
        WidgetRegistry.update_setting(widget_def["id"], "breakdown", kind or "none")

    breakdown_btn = _make_checkbox(tr("Breakdown"), checked=bd_mode is not None, parent=header_widget)
    setup_breakdown_button(breakdown_btn, bd_mode, on_breakdown)
    header_lay.addWidget(breakdown_btn)

    backlog_cb = _make_checkbox(tr("Backlog"), checked=show_backlog, parent=header_widget)
    header_lay.addWidget(backlog_cb)

    def on_range_change(idx):
        from ...store.registry import WidgetRegistry

        state["range_idx"] = idx
        _refetch()
        WidgetRegistry.update_setting(widget_def["id"], "time_span", fd_ranges[idx])

    def on_backlog_toggled(checked):
        from ...store.registry import WidgetRegistry

        state["backlog"] = bool(checked)
        _refetch(transition_mode="timespan")
        WidgetRegistry.update_setting(widget_def["id"], "show_backlog", checked)

    backlog_cb.toggled.connect(on_backlog_toggled)

    radio = _make_radio_group(list(fd_short), default_idx, on_range_change, header_widget)
    header_lay.addWidget(radio)

    return _wrap(chart, None,
                 header_widget=header_widget,
                 widget_id=widget_def["id"],
                 saved_w=widget_def.get("width"),
                 saved_h=widget_def.get("height"),
                 parent=parent)


def _update_future_due(chart, widget_def, deck_id, cache=None, fail_if_not_cached=False, cfg=None):
    from .....logic.metrics.future_due import FutureDueDataProvider

    config = cfg or _addon_config()
    span = widget_def.get("time_span", Period.YEAR)
    show_backlog = widget_def.get("show_backlog", False)
    pinned_state = getattr(chart, "_pinned_state", None) or {}
    from .....logic.metrics.future_due import resolve_breakdown

    if "breakdown" in pinned_state:
        bd_mode = pinned_state["breakdown"]
    else:
        bd_mode = resolve_breakdown(widget_def.get("breakdown"), widget_def.get("show_breakdown", False))

    # Straight from the cards table (a quick grouped query), counted as in Anki's graph.
    data = FutureDueDataProvider.fetch_data(config, deck_id, False, span, include_backlog=show_backlog, breakdown=bd_mode,
                                            hidden_parts=widget_def.get("hidden_series") or ())

    if data is None:
        return False
    if hasattr(chart, "_pinned_state"):
        chart._pinned_state["deck_id"] = deck_id

    if hasattr(chart, "update_data"):
        if cfg is None:
             cfg = _addon_config()
        adaptive_binning = cfg.config.get(ADAPTIVE_CHART_BINNING, True)

        chart.show_backlog = show_backlog
        chart.binning_override = widget_def.get("binning_override", None)
        chart.set_cumulative_mode(widget_def.get("show_cumulative", True))
        chart.update_data(data, adaptive_binning=adaptive_binning)
        if hasattr(chart, "_pinned_state"):
            chart._pinned_state["backlog"] = bool(show_backlog)

        refresh_parent_chart_header_stats(chart)

        return True
    return False
