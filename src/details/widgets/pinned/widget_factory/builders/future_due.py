# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from ..utils import _addon_config, _make_radio_group, _make_checkbox
from . import pinned_title
from ..wrapper import _wrap
from . import ADAPTIVE_CHART_BINNING, Config, Period
from ..shared.context import get_pinned_context_value
from .....animations.chart_policy import local_chart_animation_batch
from ....common import (
    future_due_span_max_days,
    resolve_future_due_ranges,
    apply_chart_display_config,
    create_chart_header_for_chart,
    refresh_parent_chart_header_stats,
    resolve_future_due_choice,
)



def _build_future_due(widget_def, deck_id, cache=None, parent=None, cfg=None):
    from .....logic.metrics import FutureDueDataProvider
    from ....charts.future_due import FutureDueChart


    config = cfg or _addon_config()
    span = widget_def.get("time_span", Period.YEAR)
    show_backlog = widget_def.get("show_backlog", False)
    # fetch_data uses GlobalHistoryCache internally for the distribution,
    # then adds the backlog SQL if needed - no need for a separate cache shortcut
    data = FutureDueDataProvider.fetch_data(config, deck_id, False, span, include_backlog=show_backlog)

    adaptive_binning = config.config.get(ADAPTIVE_CHART_BINNING, True)
    
    chart = FutureDueChart(data, parent=parent, adaptive_binning=adaptive_binning, show_backlog=show_backlog)
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

    header_widget, header_lay, _, _ = create_chart_header_for_chart(
        chart,
        config,
        Config.DEEP_DIVE_PINNED_SHOW_BOTTOM_STATS,
        Config.DEEP_DIVE_PINNED_SHOW_STATS,
        parent=parent,
        title=pinned_title(widget_def, "FUTURE DUE"),
        title_object_name="pinned_header",
    )

    default_range = widget_def.get("time_span", Period.YEAR)
    fd_ranges, fd_short, _ = resolve_future_due_ranges(widget_def.get("radio_ranges"))
    default_idx, _, _ = resolve_future_due_choice(fallback_range=default_range, default_idx=2, ranges=fd_ranges)

    state = {"range_idx": default_idx, "deck_id": deck_id}
    chart._pinned_state = state

    backlog_cb = _make_checkbox("Backlog", checked=show_backlog, parent=header_widget)
    header_lay.addWidget(backlog_cb)

    def _refresh(new_data, cur_backlog, transition_mode=None):
        chart.show_backlog = cur_backlog
        with local_chart_animation_batch(chart):
            chart.update_data(new_data, transition_mode=transition_mode)
        refresh_parent_chart_header_stats(chart)

    def on_range_change(idx):
        state["range_idx"] = idx
        new_range = fd_ranges[idx]
        cur_backlog = backlog_cb.isChecked()
        cur_deck_id = state.get("deck_id", deck_id)
        new_data = FutureDueDataProvider.fetch_data(config, cur_deck_id, False, new_range, include_backlog=cur_backlog)
        _refresh(new_data, cur_backlog)
        from ...store.registry import WidgetRegistry
        WidgetRegistry.update_setting(widget_def["id"], "time_span", new_range)

    def on_backlog_toggled(checked):
        cur_range = fd_ranges[state["range_idx"]]
        cur_deck_id = state.get("deck_id", deck_id)
        new_data = FutureDueDataProvider.fetch_data(config, cur_deck_id, False, cur_range, include_backlog=checked)
        _refresh(new_data, checked, transition_mode="timespan")
        from ...store.registry import WidgetRegistry
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
    from .....logic.metrics.future_due import FutureDueDataProvider, build_future_due_payload

    config = cfg or _addon_config()
    span = widget_def.get("time_span", Period.YEAR)
    show_backlog = widget_def.get("show_backlog", False)

    # Compute max_days for the widget's span (mirrors FutureDueDataProvider logic)
    span_max_days = future_due_span_max_days(span)  # None means dynamic (all)

    # Check GlobalHistoryCache first - but only reuse if the span matches or data needs trimming
    _, cached_data = get_pinned_context_value(
        deck_id,
        Period.TOTAL,
        "future_due",
        cfg=config,
        allow_slow_ops=False,
    )

    data = None
    if cached_data:
        # Cache has Total-span data: re-filter distribution to the widget's span
        raw_dist = cached_data.get("distribution", {})
        from aqt import mw
        today = int(mw.col.sched.today or 0)
        

        filtered = {}
        backlog_count = 0
        excluded_invalid_rel_keys = 0
        excluded_invalid_rel_cards = 0
        extreme_rel_samples = []
        max_abs_rel = 0
        for k, v in raw_dist.items():
            orig_k = k
            try:
                k = int(k)
            except Exception:
                continue
            # Cache stores absolute Anki day offsets, convert to relative days.
            # Skip epoch timestamps (queue=1 learning cards, excluded to match Anki native forecast).
            if k >= 1000000000:
                excluded_invalid_rel_keys += 1
                excluded_invalid_rel_cards += int(v or 0)
                continue
            rel_day = k - today
            # For day-based dues, the minimum plausible relative day is -today.
            # Values far below this are invalid artifacts (e.g. -100000).
            if rel_day < -today:
                excluded_invalid_rel_keys += 1
                excluded_invalid_rel_cards += int(v or 0)
                continue
            abs_rel = abs(int(rel_day))
            if abs_rel > max_abs_rel:
                max_abs_rel = abs_rel
            if abs_rel > 5000 and len(extreme_rel_samples) < 8:
                extreme_rel_samples.append((int(orig_k), int(rel_day), int(v or 0)))
            
            is_in_span = (span_max_days is None) or (rel_day <= span_max_days)
            
            if rel_day >= 0:
                if is_in_span:
                    filtered[rel_day] = filtered.get(rel_day, 0) + v
            elif show_backlog:
                # Backlog is always included regardless of span limit (it's the past)
                filtered[rel_day] = filtered.get(rel_day, 0) + v
                backlog_count += v
                
        if filtered:
            data = build_future_due_payload(
                filtered,
                time_span=span,
                addon_config=config,
                backlog_count=backlog_count,
            )
    
    # Fall back to the provider fetch on a cache miss or unresolved span. This
    # widget must stay live when navigating decks even if the Deep Dive has not
    # primed the cache key yet.
    if data is None:
        data = FutureDueDataProvider.fetch_data(config, deck_id, False, span, include_backlog=show_backlog)

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
        
        refresh_parent_chart_header_stats(chart)
                
        return True
    return False
