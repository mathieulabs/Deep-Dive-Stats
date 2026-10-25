# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors

from ....widgets.common import (
    default_fsrs_filter_idx,
    resolve_fsrs_filters,
    apply_chart_display_config,
    create_chart_header_for_chart,
    create_fsrs_filter_group,
    refresh_chart_header_stats,
    resolve_future_due_choice,
    resolve_future_due_ranges,
    resolve_fsrs_filter_choice,
)
from ....animations.chart_policy import local_chart_animation_batch
from ... import Config
from ... import ADAPTIVE_CHART_BINNING, Period
from .. import FutureDueChart, FutureDueDataProvider, HourlyBreakdownChart, HourlyDataProvider, ReviewIntervalsChart, ReviewIntervalsDataProvider


def build_hourly_section(manager, deck_identifier, period_range, row_data, target_layout=None, manual_add=False):
    current_idx = manager.dialog.tab_widget.currentIndex()
    tab_config = manager._resolve_tab_config(current_idx, period_range)
    target_did = row_data.get("did")
    if target_did is None and manager.dialog.view_mode != "time":
        target_did = tab_config.get("deck_id")
    history_range = int(period_range) if period_range is not None else tab_config.get("range", Period.TOTAL)
    is_deleted = row_data.get("is_deleted", False) if row_data else False

    ctx = getattr(manager, "last_history_context", {}) or {}
    data = ctx.get("hourly")

    if data is None and not getattr(manager, "_is_skeleton", False):
        data = HourlyDataProvider.fetch_data(
            manager.addon_config,
            target_did,
            is_deleted=is_deleted,
            time_span=history_range,
        )
    if data is None:
        data = {}

    if not data or all(h_data.get("total", 0) == 0 for h_data in data.values()):
        if not manager._show_empty_charts():
            return None, None
        data = {h: {"total": 0, "correct": 0} for h in range(24)}

    chart = HourlyBreakdownChart(data, parent=manager.dialog)
    chart._bc_span = history_range
    apply_chart_display_config(
        chart,
        opacity=manager._get_dd_widget_setting("hourly", "chart_opacity", 100),
        line_opacity=manager._get_dd_widget_setting("hourly", "line_opacity", None),
        bar_gradient=manager._get_dd_widget_setting("hourly", "bar_gradient", None),
        show_grid=manager._get_dd_widget_setting("hourly", "show_grid", None),
        minimum_height=120,
        expanding=True,
    )
    if hasattr(manager, "_apply_cumulative_mode_to_chart"):
        show_cumulative = manager._get_dd_widget_setting("hourly", "show_cumulative", True)
        manager._apply_cumulative_mode_to_chart(chart, show_cumulative)

    header_widget, _, _, _ = create_chart_header_for_chart(
        chart,
        manager.addon_config,
        Config.DEEP_DIVE_SHOW_BOTTOM_STATS,
        Config.DEEP_DIVE_SHOW_STATS,
        parent=manager.dialog,
    )
    return chart, header_widget


def build_future_due_section(manager, deck_identifier, period_range, row_data, target_layout=None, manual_add=False):

    is_deleted = row_data.get("is_deleted", False) if row_data else False
    fd_ranges, _fd_short, fd_labels = resolve_future_due_ranges(
        manager._get_dd_widget_setting("future_due", "radio_ranges", None)
    )
    default_idx, active_range, _source = resolve_future_due_choice(
        manager._get_dd_widget_setting("future_due", "time_span_idx", None),
        fallback_range=period_range,
        default_idx=0,
        ranges=fd_ranges,
    )

    manager._update_dd_widget_setting("future_due", "time_span_idx", default_idx, refresh=False)

    show_backlog = manager._get_dd_widget_setting("future_due", "show_backlog", False)
    is_skeleton = getattr(manager, "_is_skeleton", False)

    if is_skeleton:
        data = {"total": 0, "days": [], "counts": [], "backlog": 0}
    else:
        data = FutureDueDataProvider.fetch_data(
            manager.addon_config,
            deck_identifier,
            is_deleted,
            active_range,
            include_backlog=show_backlog,
        )

    if not is_skeleton:
        has_visible_due = bool(
            data
            and (data.get("total", 0) > 0 or (show_backlog and data.get("backlog", 0) > 0))
        )
        if not has_visible_due:
            total_check = FutureDueDataProvider.fetch_data(
                manager.addon_config,
                deck_identifier,
                is_deleted,
                Period.TOTAL,
                include_backlog=show_backlog,
            )
            total_has_visible = bool(
                total_check
                and (
                    total_check.get("total", 0) > 0
                    or (show_backlog and total_check.get("backlog", 0) > 0)
                )
            )
            if not total_has_visible:
                if not manager._show_empty_charts():
                    return None, None
                data = {"total": 0, "days": [], "counts": [], "backlog": 0}

    adaptive = manager.dialog.addon_config.config.get(ADAPTIVE_CHART_BINNING, True)
    binning_override = manager._get_dd_widget_setting("future_due", "binning_override", None)
    chart = FutureDueChart(
        data,
        parent=manager.dialog,
        adaptive_binning=adaptive,
        show_backlog=show_backlog,
    )
    chart.binning_override = binning_override
    apply_chart_display_config(
        chart,
        opacity=manager._get_dd_widget_setting("future_due", "chart_opacity", 100),
        line_opacity=manager._get_dd_widget_setting("future_due", "line_opacity", None),
        bar_gradient=manager._get_dd_widget_setting("future_due", "bar_gradient", None),
        show_grid=manager._get_dd_widget_setting("future_due", "show_grid", None),
        minimum_height=120,
        expanding=True,
    )
    if hasattr(manager, "_apply_cumulative_mode_to_chart"):
        show_cumulative = manager._get_dd_widget_setting("future_due", "show_cumulative", True)
        manager._apply_cumulative_mode_to_chart(chart, show_cumulative)

    header_widget, header_lay, _, _ = create_chart_header_for_chart(
        chart,
        manager.addon_config,
        Config.DEEP_DIVE_SHOW_BOTTOM_STATS,
        Config.DEEP_DIVE_SHOW_STATS,
        parent=manager.dialog,
    )

    state = {"range_idx": default_idx}
    backlog_cb = manager._make_styled_checkbox("Backlog", checked=show_backlog, parent=header_widget)
    header_lay.addWidget(backlog_cb)

    def _refresh_chart(new_data, cur_backlog, transition_mode=None):
        chart.show_backlog = cur_backlog
        with local_chart_animation_batch(chart):
            chart.update_data(new_data, transition_mode=transition_mode)
        refresh_chart_header_stats(header_widget, chart)
        if hasattr(manager, "_refresh_bottom_stats"):
            manager._refresh_bottom_stats()

    def on_future_due_radio(idx):
        state["range_idx"] = idx
        cur_deck = manager.last_deck_identifier
        cur_is_deleted = manager.last_row_data.get("is_deleted", False) if manager.last_row_data else False
        cur_backlog = backlog_cb.isChecked()
        new_data = FutureDueDataProvider.fetch_data(
            manager.addon_config,
            cur_deck,
            cur_is_deleted,
            fd_ranges[idx],
            include_backlog=cur_backlog,
        )
        _refresh_chart(new_data, cur_backlog)
        manager._update_dd_widget_setting("future_due", "time_span_idx", idx, refresh=False)

    def on_backlog_toggled(checked):
        cur_deck = manager.last_deck_identifier
        cur_is_deleted = manager.last_row_data.get("is_deleted", False) if manager.last_row_data else False
        cur_range = fd_ranges[state["range_idx"]]
        new_data = FutureDueDataProvider.fetch_data(
            manager.addon_config,
            cur_deck,
            cur_is_deleted,
            cur_range,
            include_backlog=checked,
        )
        _refresh_chart(new_data, checked, transition_mode="timespan")
        manager._update_dd_widget_setting("future_due", "show_backlog", checked, refresh=False)

    backlog_cb.toggled.connect(on_backlog_toggled)

    radio_group = manager._make_radio_group(
        list(fd_labels),
        default_idx,
        on_future_due_radio,
        header_widget,
    )
    header_lay.addWidget(radio_group)
    return chart, header_widget


def build_review_intervals_section(
    manager, deck_identifier, period_range, row_data, target_layout=None, manual_add=False
):
    is_deleted = row_data.get("is_deleted", False) if row_data else False
    did = row_data.get("did") if row_data else None

    is_skeleton = getattr(manager, "_is_skeleton", False)
    if is_skeleton:
        data = {"total": 0, "intervals": [], "counts": []}
    else:
        data = ReviewIntervalsDataProvider.fetch_data(manager.addon_config, did, is_deleted, period_range)

    if (not data or data.get("total", 0) <= 0) and not is_skeleton:
        if not manager._show_empty_charts():
            return None, None
        data = {"total": 0, "intervals": [], "counts": []}

    adaptive = manager.dialog.addon_config.config.get(ADAPTIVE_CHART_BINNING, True)
    binning_override = manager._get_dd_widget_setting("review_intervals", "binning_override", None)
    fsrs_modes, _fsrs_short, fsrs_labels = resolve_fsrs_filters(
        manager._get_dd_widget_setting("review_intervals", "filter_modes", None)
    )
    default_idx, initial_mode = resolve_fsrs_filter_choice(
        manager._get_dd_widget_setting("review_intervals", "time_span_idx"), modes=fsrs_modes
    )
    chart = ReviewIntervalsChart(
        data,
        parent=manager.dialog,
        adaptive_binning=adaptive,
        filter_mode=initial_mode,
    )
    chart.binning_override = binning_override
    apply_chart_display_config(
        chart,
        opacity=manager._get_dd_widget_setting("review_intervals", "chart_opacity", 100),
        line_opacity=manager._get_dd_widget_setting("review_intervals", "line_opacity", None),
        bar_gradient=manager._get_dd_widget_setting("review_intervals", "bar_gradient", None),
        show_grid=manager._get_dd_widget_setting("review_intervals", "show_grid", None),
        minimum_height=120,
        expanding=True,
    )
    chart._last_timespan_token = (
        int(period_range if period_range is not None else manager.last_history_range),
        int(manager._get_dd_widget_setting("review_intervals", "custom_days", 7) or 7),
    )
    chart._last_deck_id = did
    if hasattr(manager, "_apply_cumulative_mode_to_chart"):
        show_cumulative = manager._get_dd_widget_setting("review_intervals", "show_cumulative", True)
        manager._apply_cumulative_mode_to_chart(chart, show_cumulative)

    header_widget, header_lay, _, _ = create_chart_header_for_chart(
        chart,
        manager.addon_config,
        Config.DEEP_DIVE_SHOW_BOTTOM_STATS,
        Config.DEEP_DIVE_SHOW_STATS,
        parent=manager.dialog,
    )

    def on_review_interval_filter_applied(idx):
        manager._update_dd_widget_setting("review_intervals", "time_span_idx", idx, refresh=False)
        if hasattr(manager, "_refresh_bottom_stats"):
            manager._refresh_bottom_stats()

    radio_group = create_fsrs_filter_group(
        chart,
        labels=fsrs_labels,
        resolved_idx=default_idx,
        make_radio_group=manager._make_radio_group,
        parent=header_widget,
        on_idx_applied=on_review_interval_filter_applied,
        modes=fsrs_modes,
        default_idx=default_fsrs_filter_idx(fsrs_modes),
    )
    header_lay.addWidget(radio_group)
    return chart, header_widget




