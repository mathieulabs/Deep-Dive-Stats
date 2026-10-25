# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QCheckBox, QColor, QSizePolicy, QStackedWidget

from ....animations.chart_policy import local_chart_animation_batch
from ....widgets.chart_utils.zoom_mixin import preserve_zoom
from ....logic.data.transforms.activity_series import (
    build_activity_series,
    convert_breakdown_metric_rows,
    normalize_hidden_types,
)
from ... import Config
from ... import ADAPTIVE_CHART_BINNING, get_color
from .. import (
    ActivityChart,
    ActivityStackedChart,
    RetentionChart,
)
from ....widgets.common import apply_chart_display_config, create_chart_header_for_chart
from ....logic.logger import log_swallowed
from ....widgets.charts.activity.review_dots import ReviewDotsChart
from ..controls_parts.review_dots import refresh_review_dots


def create_activity_chart_view(manager, activity_data, history_oldest_first):
    """Create the Activity chart widget (with breakdown toggle support)."""
    is_skeleton = getattr(manager, "_is_skeleton", False) or manager._show_empty_charts()
    time_mode_enabled = bool(manager._get_dd_widget_setting("activity", "show_time_axis", False))
    metric_mode = "time" if time_mode_enabled else "reviews"

    metric_history_oldest_first = convert_breakdown_metric_rows(
        history_oldest_first,
        metric_mode,
        count_key_style="count",
        preserve_source_fields=True,
    )
    if metric_history_oldest_first:
        activity_data = build_activity_series(
            metric_history_oldest_first,
            value_key=("time_ms" if metric_mode == "time" else "reviews"),
            scale=(1.0 / 60000.0 if metric_mode == "time" else 1.0),
        )
    if not activity_data or not any(h[1] > 0 for h in activity_data):
        if not is_skeleton:
            return None, None, None, None
        activity_data = []
        history_oldest_first = []
    stack = QStackedWidget(manager.dialog)
    stack.setMinimumHeight(120)
    stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    section_key = "activity"
    show_avg = manager._get_dd_widget_setting(section_key, "show_average", True)
    avg_on_active = manager._get_dd_widget_setting(section_key, "avg_on_active_days", True)
    show_cumulative = manager._get_dd_widget_setting(section_key, "show_cumulative", True)
    binning_override = manager._get_dd_widget_setting(section_key, "binning_override", None)

    normal_chart = None
    if activity_data or is_skeleton:
        conf = manager.dialog.addon_config.config
        adaptive = conf.get(ADAPTIVE_CHART_BINNING, True)
        normal_chart = ActivityChart(
            activity_data,
            color=get_color(conf, Config.COLOR_BAR),
            chart_type="bar",
            parent=stack,
            adaptive_binning=adaptive,
        )
        normal_chart._color_config_key = Config.COLOR_BAR
        normal_chart.binning_override = binning_override
        normal_chart._chart_owner = "deep_dive_activity"
        normal_chart._relative_height_transition = True
        normal_chart.show_hover_marker = False
        normal_chart.set_value_mode(metric_mode)
        normal_chart.set_average_mode(show_avg, avg_on_active)
        normal_chart.set_cumulative_mode(show_cumulative)
        apply_chart_display_config(
            normal_chart,
            opacity=manager._get_dd_widget_setting(section_key, "chart_opacity", 100),
            line_opacity=manager._get_dd_widget_setting(section_key, "line_opacity", None),
            bar_gradient=manager._get_dd_widget_setting(section_key, "bar_gradient", None),
            show_grid=manager._get_dd_widget_setting(section_key, "show_grid", None),
            tooltip_hidden=manager._get_dd_widget_setting(section_key, "tooltip_hidden", None),
            minimum_height=120,
            expanding=True,
        )
        stack.addWidget(normal_chart)
    else:
        manager._add_empty_label(stack, "No activity data")

    stacked_chart = None
    if activity_data or is_skeleton:
        conf = manager.dialog.addon_config.config
        series_config = [
            {"key": "mature_count", "label": "Mature", "color": get_color(conf, Config.COLOR_MATURE)},
            {"key": "young_count", "label": "Young", "color": get_color(conf, Config.COLOR_YOUNG)},
            {"key": "relearn_count", "label": "Relearning", "color": get_color(conf, Config.COLOR_RELEARN)},
            {"key": "learn_count", "label": "Learning", "color": get_color(conf, Config.COLOR_LEARN)},
            {"key": "cram_count", "label": "Filtered", "color": get_color(conf, Config.COLOR_CRAM)},
        ]
        hidden_types = normalize_hidden_types(manager._get_dd_widget_setting("activity", "hidden_review_types", None))
        series_config = [s for s in series_config if s["key"].replace("_count", "") not in hidden_types]
        adaptive = conf.get(ADAPTIVE_CHART_BINNING, True)
        stacked_chart = ActivityStackedChart(
            metric_history_oldest_first,
            series_config,
            parent=stack,
            adaptive_binning=adaptive,
        )
        stacked_chart.binning_override = binning_override
        stacked_chart._chart_owner = "deep_dive_activity"
        stacked_chart._relative_height_transition = True
        stacked_chart.set_value_mode(metric_mode)
        stacked_chart.set_average_mode(show_avg, avg_on_active)
        stacked_chart.set_cumulative_mode(show_cumulative)
        apply_chart_display_config(
            stacked_chart,
            opacity=manager._get_dd_widget_setting(section_key, "chart_opacity", 100),
            line_opacity=manager._get_dd_widget_setting(section_key, "line_opacity", None),
            bar_gradient=manager._get_dd_widget_setting(section_key, "bar_gradient", None),
            show_grid=manager._get_dd_widget_setting(section_key, "show_grid", None),
            tooltip_hidden=manager._get_dd_widget_setting(section_key, "tooltip_hidden", None),
            minimum_height=120,
            expanding=True,
        )
        stack.addWidget(stacked_chart)

    # Page 2: one dot per review, used when zoomed on a few hours.
    dots_chart = None
    if normal_chart and stacked_chart:
        conf = manager.dialog.addon_config.config
        dots_chart = ReviewDotsChart(stack)
        dots_chart.set_style(
            get_color(conf, Config.COLOR_BAR),
            [
                get_color(conf, Config.COLOR_LEARN),
                get_color(conf, Config.COLOR_YOUNG),
                get_color(conf, Config.COLOR_MATURE),
                get_color(conf, Config.COLOR_RELEARN),
                get_color(conf, Config.COLOR_CRAM),
            ],
        )
        stack.addWidget(dots_chart)
    manager.activity_stack = stack
    manager.review_dots_chart = dots_chart

    chart_ref = stacked_chart if manager.last_activity_breakdown and stacked_chart else normal_chart
    header_widget, header_lay, _, stats_state = create_chart_header_for_chart(
        normal_chart,
        manager.addon_config,
        Config.DEEP_DIVE_SHOW_BOTTOM_STATS,
        Config.DEEP_DIVE_SHOW_STATS,
        parent=manager.dialog,
        stats_chart=chart_ref,
    )
    if stacked_chart:
        stacked_chart.show_stats = stats_state["show_chart_stats"]
    cb = manager._make_styled_checkbox(
        "Breakdown by Type", checked=manager.last_activity_breakdown, parent=header_widget
    )

    def on_breakdown(checked):
        target_chart = stacked_chart if (checked and stacked_chart) else normal_chart
        if target_chart is not None:
            try:
                if hasattr(target_chart, "animation"):
                    target_chart.animation.stop()
                target_chart._initial_animation_done = True
                target_chart._progress = 1.0
                target_chart.update()
            except Exception:
                log_swallowed()
        manager.last_activity_breakdown = checked
        if stack.currentIndex() == 2 and dots_chart is not None:
            # One dot per review is on screen: the type split only changes their colours,
            # so recolour them in place and stay on the dots.
            time_on = bool(manager._get_dd_widget_setting("activity", "show_time_axis", False))
            dots_chart.set_mode("time" if time_on else "reviews", checked)
        else:
            stack.setCurrentIndex(1 if checked and stacked_chart else 0)
            refresh_review_dots(manager)
        manager._update_dd_widget_setting("activity", "breakdown_enabled", checked, refresh=False)

    cb.toggled.connect(on_breakdown)
    header_lay.addWidget(cb)

    cb_time = manager._make_styled_checkbox("Time", checked=time_mode_enabled, parent=header_widget)

    def on_time_mode(checked):
        next_mode = "time" if bool(checked) else "reviews"
        latest_history = getattr(manager, "last_history_data", None) or []
        latest_widget_rows = manager._get_widget_history("activity", latest_history)
        latest_oldest_first = latest_widget_rows[::-1]
        metric_rows = convert_breakdown_metric_rows(
            latest_oldest_first,
            next_mode,
            count_key_style="count",
            preserve_source_fields=True,
        )
        metric_activity = build_activity_series(
            metric_rows,
            value_key=("time_ms" if next_mode == "time" else "reviews"),
            scale=(1.0 / 60000.0 if next_mode == "time" else 1.0),
        )
        hi_res = getattr(manager, "_hi_res_history", None) if getattr(manager, "_adaptive_zoom_active", False) else None
        if hi_res:
            # 10-minute view: switch it in place and keep the daily data, in the new mode,
            # for the way back.
            from ..controls_parts.adaptive_zoom import activity_payloads

            if normal_chart is not None and hasattr(normal_chart, "_pre_adaptive_data"):
                normal_chart._pre_adaptive_data = metric_activity
            if stacked_chart is not None and hasattr(stacked_chart, "_pre_adaptive_data"):
                stacked_chart._pre_adaptive_data = metric_rows
            metric_activity, metric_rows = activity_payloads(manager, hi_res, next_mode)
        visible_chart = stacked_chart if (stacked_chart and stack.currentIndex() == 1) else normal_chart
        with local_chart_animation_batch(visible_chart):
            with preserve_zoom(normal_chart, stacked_chart):
                if normal_chart:
                    normal_chart.set_value_mode(next_mode)
                    normal_chart.update_data(
                        metric_activity,
                        adaptive_binning=normal_chart.adaptive_binning,
                        transition_mode=None,
                    )
                if stacked_chart:
                    stacked_chart.set_value_mode(next_mode)
                    stacked_chart.update_data(
                        metric_rows,
                        adaptive_binning=stacked_chart.adaptive_binning,
                        transition_mode=None,
                    )
        manager._update_dd_widget_setting("activity", "show_time_axis", bool(checked), refresh=False)
        dots = getattr(manager, "review_dots_chart", None)
        if dots is not None and dots.isVisible():
            # One dot per review is on screen: glide it to the new mode right away.
            dots.set_mode(next_mode, manager.last_activity_breakdown)
        refresh_review_dots(manager)

    cb_time.toggled.connect(on_time_mode)
    header_lay.addWidget(cb_time)

    if manager.last_activity_breakdown and stacked_chart:
        stack.setCurrentIndex(1)

    return stack, normal_chart, stacked_chart, header_widget


def create_retention_chart_view(manager, retention_data):
    """Create the Retention chart widget with its specific controls."""
    is_skeleton = getattr(manager, "_is_skeleton", False) or manager._show_empty_charts()
    if not retention_data or not any(t[2][1] > 0 for t in retention_data.get("all", [])):
        if not is_skeleton:
            return None, None, None
        retention_data = {"all": [], "young": [], "mature": []}
    chart = None

    section_key = "retention"
    show_avg = manager._get_dd_widget_setting(section_key, "show_average", True)
    avg_on_active = manager._get_dd_widget_setting(section_key, "avg_on_active_days", True)
    binning_override = manager._get_dd_widget_setting(section_key, "binning_override", None)

    if retention_data:
        adaptive = manager.addon_config.config.get(ADAPTIVE_CHART_BINNING, True)
        chart = RetentionChart(
            retention_data,
            visible_series=manager.last_retention_visibility,
            parent=manager.dialog,
            adaptive_binning=adaptive,
        )
        chart.binning_override = binning_override
        if hasattr(chart, "set_average_mode"):
            chart.set_average_mode(show_avg, avg_on_active)
        if hasattr(chart, "set_cumulative_mode"):
            chart.set_cumulative_mode(False)
        chart.fit_to_data = bool(manager._get_dd_widget_setting(section_key, "fit_to_data", False))
        if hasattr(chart, "set_min_reviews"):
            chart.min_reviews = int(manager._get_dd_widget_setting(section_key, "min_reviews", 0) or 0)
            chart.review_bars = bool(manager._get_dd_widget_setting(section_key, "review_bars", True))
            chart.review_axis = bool(manager._get_dd_widget_setting(section_key, "review_axis", False))
            chart.rounded = bool(manager._get_dd_widget_setting(section_key, "rounded", True))
        apply_chart_display_config(
            chart,
            opacity=manager._get_dd_widget_setting(section_key, "chart_opacity", 100),
            line_opacity=manager._get_dd_widget_setting(section_key, "line_opacity", None),
            bar_gradient=manager._get_dd_widget_setting(section_key, "bar_gradient", None),
            show_grid=manager._get_dd_widget_setting(section_key, "show_grid", None),
            tooltip_hidden=manager._get_dd_widget_setting(section_key, "tooltip_hidden", None),
            minimum_height=120,
            expanding=True,
        )

    header_widget, header_lay, _, _ = create_chart_header_for_chart(
        chart,
        manager.addon_config,
        Config.DEEP_DIVE_SHOW_BOTTOM_STATS,
        Config.DEEP_DIVE_SHOW_STATS,
        parent=manager.dialog,
    )

    if chart:
        series_checkboxes = {}
        for key, series in RetentionChart.SERIES_CONFIG.items():
            label = series["label"]
            is_checked = manager.last_retention_visibility.get(key, series["default_on"])
            cb = QCheckBox(label, parent=header_widget)
            cb.setChecked(is_checked)
            c = QColor(RetentionChart._get_series_color(key))
            rgba = f"rgba({c.red()}, {c.green()}, {c.blue()}, 180)"
            cb.setProperty("deepdivestats_theme_role", "retention_checkbox")
            cb.setProperty("deepdivestats_text_color", rgba)
            cb.setProperty("deepdivestats_accent_rgba", rgba)
            cb.setProperty("deepdivestats_font_weight", "700")
            manager.apply_deep_dive_theme(cb)

            def toggle_visibility(state, k=key):
                visible = bool(state)
                if chart:
                    chart.set_series_visible(k, visible)
                manager.last_retention_visibility[k] = visible
                manager._update_dd_widget_setting(
                    "retention", "visibility", manager.last_retention_visibility, refresh=False
                )

            cb.stateChanged.connect(toggle_visibility)
            header_lay.addWidget(cb)
            series_checkboxes[key] = cb

        if hasattr(chart, "series_totals"):
            from ....widgets.charts.retention.totals import bind_totals

            bind_totals(chart, series_checkboxes)

    return chart, chart, header_widget




