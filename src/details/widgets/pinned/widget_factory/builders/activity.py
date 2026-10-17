# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QStackedWidget
from . import pinned_title
from .....animations.chart_policy import local_chart_animation_batch
from ....chart_utils.zoom_mixin import preserve_zoom
from ....chart_utils.zoom_camera import switch_stack
from ..utils import _make_checkbox
from ..wrapper import _wrap
from . import ADAPTIVE_CHART_BINNING, Config, HistoryProvider, Period, get_color
from ..shared.header import add_pinned_zoom_reset_button, prepare_pinned_header
from .....logic.data.transforms.activity_series import (
    attach_breakdown_totals,
    build_activity_series_from_breakdown,
    build_breakdown_rows,
    convert_breakdown_metric_rows,
    filter_activity_types,
    normalize_hidden_types,
)
from ....charts.activity import ActivityChart
from ....charts.activity_stacked import ActivityStackedChart
from ....charts.common.zoom import (
    build_adaptive_fetch_bounds,
    compute_transition_align_right,
    freeze_chart_transition_state,
    get_timespan_transition_meta,
    resolve_adaptive_zoom_window,
    widen_zoom_window,
    should_use_timespan_transition,
    update_chart_for_transition,
)
from ...store.registry import WidgetRegistry
from ..shared.reviews import load_activity_source
from ....common import (
    apply_chart_display_config,
    connect_chart_header_refresh,
    create_chart_header_for_chart,
    refresh_parent_chart_header_stats,
)
from .....logic.logger import log_swallowed
from ....chart_utils.zoom_camera import with_camera



def _build_activity(widget_def, deck_id, cache=None, parent=None, cfg=None):
    span = widget_def.get("time_span")
    days = widget_def.get("custom_days", 7)

    source = load_activity_source(
        deck_id,
        span,
        cache=cache,
        cfg=cfg,
        custom_days=days,
        fail_if_not_cached=True,
        allow_context_slow_ops=False,
        hidden_types=widget_def.get("hidden_review_types"),
    )
    activity_data = source["activity_data"]
    breakdown_data = source["breakdown_data"]
    _raw_hist = source["raw_hist"]
    _loading = bool(source["history_is_none"])
    if _loading:
        pass
    metric_mode = "time" if bool(widget_def.get("show_time_axis", False)) else "reviews"
    if breakdown_data is not None:
        breakdown_data = attach_breakdown_totals(breakdown_data, _raw_hist)
        metric_breakdown_data = convert_breakdown_metric_rows(
            breakdown_data,
            metric_mode,
            count_key_style="plain",
        )
        # Keep Activity totals exactly aligned with Breakdown totals.
        activity_data = build_activity_series_from_breakdown(
            metric_breakdown_data,
            count_key_style="plain",
        )
    else:
        metric_breakdown_data = breakdown_data

    if cfg is None:
        from ..utils import _addon_config
        cfg = _addon_config()
    adaptive_binning = cfg.config.get(ADAPTIVE_CHART_BINNING, True)

    stack = QStackedWidget(parent)
    normal_chart = ActivityChart(activity_data, color=get_color(cfg.config, Config.COLOR_BAR, "pinned"), chart_type="bar", parent=stack, adaptive_binning=adaptive_binning)
    normal_chart._color_config_key = Config.COLOR_BAR
    normal_chart.binning_override = widget_def.get("binning_override", None)
    normal_chart._chart_owner = "pinned_activity"
    normal_chart._relative_height_transition = True
    normal_chart.show_hover_marker = False
    normal_chart.set_value_mode(metric_mode)
    apply_chart_display_config(
        normal_chart,
        opacity=widget_def.get("chart_opacity", 100),
        line_opacity=widget_def.get("line_opacity"),
        bar_gradient=widget_def.get("bar_gradient"),
        show_grid=widget_def.get("show_grid"),
        tooltip_hidden=widget_def.get("tooltip_hidden"),
        minimum_height=120,
    )

    show_avg = widget_def.get("show_average", True)
    show_total = widget_def.get("show_cumulative", True)
    avg_on_active = widget_def.get("avg_on_active_days", True)
    
    normal_chart.set_average_mode(show_avg, avg_on_active)
    normal_chart.set_cumulative_mode(show_total)
    
    stack.addWidget(normal_chart)

    breakdown_chart = None
    try:
        from ..utils import _addon_config
        if cfg is None:
            cfg = _addon_config()
            
        colors = {
            "mature": get_color(cfg.config, Config.COLOR_MATURE, "pinned"),
            "young": get_color(cfg.config, Config.COLOR_YOUNG, "pinned"),
            "relearn": get_color(cfg.config, Config.COLOR_RELEARN, "pinned"),
            "learn": get_color(cfg.config, Config.COLOR_LEARN, "pinned"),
            "cram": get_color(cfg.config, Config.COLOR_CRAM, "pinned"),
        }
        
        series_config = [
            {"key": "mature", "label": "Mature", "color": colors["mature"]},
            {"key": "young", "label": "Young", "color": colors["young"]},
            {"key": "relearn", "label": "Relearning", "color": colors["relearn"]},
            {"key": "learn", "label": "Learning", "color": colors["learn"]}, 
            {"key": "cram", "label": "Filtered", "color": colors["cram"]}
        ]
        
        _hidden_types = normalize_hidden_types(widget_def.get("hidden_review_types"))
        _all_series = list(series_config)
        series_config = [s for s in series_config if s["key"] not in _hidden_types]
        breakdown_chart = ActivityStackedChart(metric_breakdown_data, series_config, parent=stack, adaptive_binning=adaptive_binning)
        breakdown_chart._all_series_config = _all_series
        breakdown_chart.binning_override = widget_def.get("binning_override", None)
        breakdown_chart._chart_owner = "pinned"
        # Use relative-height transitions for Activity breakdown to keep motion stable across scale changes.
        breakdown_chart._relative_height_transition = True
        breakdown_chart.set_average_mode(show_avg, avg_on_active)
        breakdown_chart.set_cumulative_mode(show_total)
        breakdown_chart.set_value_mode(metric_mode)
        apply_chart_display_config(
            breakdown_chart,
            opacity=widget_def.get("chart_opacity", 100),
            line_opacity=widget_def.get("line_opacity"),
            bar_gradient=widget_def.get("bar_gradient"),
            show_grid=widget_def.get("show_grid"),
            tooltip_hidden=widget_def.get("tooltip_hidden"),
            minimum_height=120,
        )
        stack.addWidget(breakdown_chart)
    except Exception:
        log_swallowed()
    
    # Page 2: one dot per review, used when zoomed on a few hours.
    dots_chart = None
    if breakdown_chart is not None:
        try:
            from ....charts.activity.review_dots import ReviewDotsChart

            dots_chart = ReviewDotsChart(stack)
            dots_chart.set_style(
                get_color(cfg.config, Config.COLOR_BAR, "pinned"),
                [
                    get_color(cfg.config, Config.COLOR_LEARN, "pinned"),
                    get_color(cfg.config, Config.COLOR_YOUNG, "pinned"),
                    get_color(cfg.config, Config.COLOR_MATURE, "pinned"),
                    get_color(cfg.config, Config.COLOR_RELEARN, "pinned"),
                    get_color(cfg.config, Config.COLOR_CRAM, "pinned"),
                ],
            )
            stack.addWidget(dots_chart)
        except Exception:
            dots_chart = None
            log_swallowed()

    header_widget, header_lay, _, stats_state = create_chart_header_for_chart(
        normal_chart,
        cfg,
        Config.DEEP_DIVE_PINNED_SHOW_BOTTOM_STATS,
        Config.DEEP_DIVE_PINNED_SHOW_STATS,
        parent=parent,
        title=pinned_title(widget_def, "ACTIVITY"),
        title_object_name="pinned_header",
    )
    if breakdown_chart:
        breakdown_chart.show_stats = stats_state["show_chart_stats"]
    prepare_pinned_header(header_widget, header_lay)
    btn_reset = add_pinned_zoom_reset_button(
        header_widget,
        header_lay,
        retain_size_when_hidden=True,
    )
    
    _adaptive = {"active": False, "pre_normal": None, "pre_breakdown": None, "align_right": True, "dates": None, "rows": None}
    for _c in (normal_chart, breakdown_chart):
        if _c:
            _c._adaptive_state = _adaptive
    # Store on chart so _update_activity can refresh stale closure references
    _state = {"deck_id": deck_id}
    normal_chart._pinned_state = _state
    normal_chart._pinned_raw_hist = _raw_hist
    normal_chart._hidden_review_types = normalize_hidden_types(widget_def.get("hidden_review_types"))
    normal_chart._pinned_adaptive = _adaptive
    normal_chart._metric_source_breakdown = breakdown_data
    normal_chart._last_time_span = span
    normal_chart._last_timespan_token = widget_def.get("_timespan_token", 0)
    normal_chart._last_deck_id = deck_id
    if breakdown_chart:
        breakdown_chart._metric_source_breakdown = breakdown_data
        breakdown_chart._last_time_span = span
        breakdown_chart._last_timespan_token = widget_def.get("_timespan_token", 0)
        breakdown_chart._last_deck_id = deck_id

    _view = {"breakdown": bool(widget_def.get("show_breakdown", True))}

    def _dots_show_bars():
        if stack.currentIndex() == 2 or getattr(stack, "_pending_switch", None) is not None:
            switch_stack(stack, 1 if (breakdown_chart is not None and _view["breakdown"]) else 0, "pinned")

    def _dots_apply():
        try:
            if dots_chart is None:
                return
            rows = _adaptive.get("rows")
            chart = breakdown_chart if (breakdown_chart is not None and _view["breakdown"]) else normal_chart
            if not _adaptive["active"] or not rows or chart is None:
                _dots_show_bars()
                return
            start, end = chart.get_zoom_range()
            end = min(int(end), len(rows))
            start = max(0, int(start))
            if end - start < 1:
                _dots_show_bars()
                return
            from datetime import datetime as _dt
            from .....logic.history_provider.ops.review_events import fetch_review_events

            def _parse(s):
                return int(_dt.strptime(s, "%Y-%m-%d %H:%M").timestamp() * 1000)

            t0 = _parse(rows[start]["date"])
            t1 = _parse(rows[end - 1]["date"]) + 600000
            from ....charts.activity.review_dots import DOTS_MAX_SPAN_MS

            if t1 - t0 > DOTS_MAX_SPAN_MS:
                _dots_show_bars()
                return
            events = fetch_review_events(HistoryProvider, cfg, _state.get("deck_id", deck_id), False, t0, t1)
            if events is None:
                _dots_show_bars()
                return
            hidden = getattr(normal_chart, "_hidden_review_types", ()) or ()
            if hidden:
                kind_keys = ("learn", "young", "mature", "relearn", "cram")
                events = [e for e in events if kind_keys[e[3]] not in hidden]
            mode = getattr(normal_chart, "value_mode", metric_mode)
            dots_chart.set_mode("time" if mode == "time" else "reviews", _view["breakdown"])
            dots_chart.set_events(events, t0, t1)
            dots_chart.wheel_target = chart
            switch_stack(stack, 2, "pinned")
        except Exception:
            log_swallowed()

    def _schedule_dots():
        if dots_chart is None:
            return
        timer = getattr(stack, "_dots_timer", None)
        if timer is None:
            from aqt.qt import QTimer

            timer = QTimer(stack)
            timer.setSingleShot(True)
            timer.timeout.connect(_dots_apply)
            stack._dots_timer = timer
        timer.start(120)

    def _replace_chart_data(chart, new_data):
        if not chart:
            return
        chart._full_data = new_data
        chart.data = new_data
        chart._full_length = len(new_data)
        chart._zoom_start = 0
        chart._zoom_end = len(new_data)
        chart._is_zoomed = False
        if hasattr(chart, '_scrollbar'):
            chart._scrollbar.hide()
        chart.update()

    def _block_zoom(chart, block):
        """Block/unblock the zoom_changed signal correctly (it lives on _zoom_signals)."""
        if chart and hasattr(chart, '_zoom_signals') and chart._zoom_signals:
            chart._zoom_signals.blockSignals(block)

    def _restore_adaptive():
        pre_normal = _adaptive["pre_normal"]
        pre_breakdown = _adaptive["pre_breakdown"]
        align_right = bool(_adaptive.get("align_right", True))
        # Clear state BEFORE update_data to prevent re-entry via zoom_changed signal
        _adaptive["active"] = False
        _adaptive["pre_normal"] = None
        _adaptive["pre_breakdown"] = None
        _adaptive["align_right"] = True
        _adaptive["rows"] = None
        pre_source = _adaptive.pop("pre_source", None)
        if pre_source:
            # Daily rows again, in the current Reviews / Time mode (it may have changed in
            # the 10-minute view).
            mode = getattr(normal_chart, "value_mode", metric_mode)
            converted = convert_breakdown_metric_rows(pre_source, mode, count_key_style="plain")
            pre_normal = build_activity_series_from_breakdown(converted, count_key_style="plain") if converted else []
            if pre_breakdown is not None:
                pre_breakdown = converted
            for _c in (normal_chart, breakdown_chart):
                if _c is not None:
                    _c._metric_source_breakdown = pre_source
        restore_candidates = [c for c in (normal_chart, breakdown_chart) if c]
        with local_chart_animation_batch(normal_chart or breakdown_chart, candidates=restore_candidates):
            if pre_normal is not None:
                _block_zoom(normal_chart, True)
                try:
                    if hasattr(normal_chart, "update_data"):
                        update_chart_for_transition(
                            normal_chart,
                            pre_normal,
                            adaptive_binning=getattr(normal_chart, "adaptive_binning", None),
                            transition_mode="timespan",
                            transition_align_right=align_right,
                            transition=True,
                            transition_duration_ms=260,
                        )
                    else:
                        _replace_chart_data(normal_chart, pre_normal)
                finally:
                    _block_zoom(normal_chart, False)
            if breakdown_chart and pre_breakdown is not None:
                _block_zoom(breakdown_chart, True)
                try:
                    if hasattr(breakdown_chart, "update_data"):
                        update_chart_for_transition(
                            breakdown_chart,
                            pre_breakdown,
                            adaptive_binning=getattr(breakdown_chart, "adaptive_binning", None),
                            transition_mode="timespan",
                            transition_align_right=align_right,
                            transition=True,
                            transition_duration_ms=260,
                        )
                    else:
                        _replace_chart_data(breakdown_chart, pre_breakdown)
                finally:
                    _block_zoom(breakdown_chart, False)
        _schedule_dots()

    def _on_adaptive_zoom(is_zoomed, start, end):
        if _adaptive["active"]:
            # Stays in the 10-minute view until a zoom-out past its full range
            # (_leave_adaptive) or the reset button.
            return
        raw_hist = normal_chart._pinned_raw_hist  # Always read current value
        if not is_zoomed or not raw_hist:
            return
        zoomed_slice = raw_hist[start:end]
        zoom_window = resolve_adaptive_zoom_window(zoomed_slice, date_keys=("date", "logical_date"))
        if zoom_window is None:
            return
        try:
            from .....ui import rollover_hour
            _HP = HistoryProvider
            offset_s = rollover_hour() * 3600
            start_ms, end_ms = build_adaptive_fetch_bounds(
                zoom_window["first_dt"],
                zoom_window["last_dt"],
                offset_seconds=offset_s,
            )
            cur_deck_id = _state.get("deck_id", deck_id)
            hi_res = _HP.fetch_history(cfg, cur_deck_id, override_start_ms=start_ms,
                                       override_end_ms=end_ms, override_bin_ms=600000)
            if not hi_res:
                return
            _rows_unfiltered = hi_res
            hi_res = filter_activity_types(hi_res, getattr(normal_chart, "_hidden_review_types", ()))
            hi_res_breakdown = build_breakdown_rows(hi_res, count_key_style="plain")
            _adaptive["pre_normal"] = normal_chart._full_data
            _adaptive["pre_source"] = getattr(normal_chart, "_metric_source_breakdown", None)
            _adaptive["pre_zoom"] = (int(start), int(end))
            _adaptive["align_right"] = compute_transition_align_right(
                start_idx=start,
                end_idx=end,
                source_len=len(raw_hist),
                default=True,
            )
            hi_res_breakdown = attach_breakdown_totals(hi_res_breakdown, hi_res)
            metric_hi_res = convert_breakdown_metric_rows(
                hi_res_breakdown,
                normal_chart.value_mode if hasattr(normal_chart, "value_mode") else metric_mode,
                count_key_style="plain",
            )
            hi_res_activity = build_activity_series_from_breakdown(
                metric_hi_res,
                count_key_style="plain",
            )
            adaptive_candidates = [c for c in (normal_chart, breakdown_chart) if c]
            with local_chart_animation_batch(normal_chart, candidates=adaptive_candidates):
                _block_zoom(normal_chart, True)
                try:
                    if hasattr(normal_chart, "update_data"):
                        update_chart_for_transition(
                            normal_chart,
                            hi_res_activity,
                            adaptive_binning=getattr(normal_chart, "adaptive_binning", None),
                            transition_mode="timespan",
                            transition_align_right=_adaptive["align_right"],
                            transition=True,
                            transition_duration_ms=260,
                        )
                    else:
                        _replace_chart_data(normal_chart, hi_res_activity)
                finally:
                    _block_zoom(normal_chart, False)
                normal_chart._metric_source_breakdown = hi_res_breakdown
                if breakdown_chart:
                    _adaptive["pre_breakdown"] = breakdown_chart._full_data
                    _block_zoom(breakdown_chart, True)
                    try:
                        if hasattr(breakdown_chart, "update_data"):
                            update_chart_for_transition(
                                breakdown_chart,
                                metric_hi_res,
                                adaptive_binning=getattr(breakdown_chart, "adaptive_binning", None),
                                transition_mode="timespan",
                                transition_align_right=_adaptive["align_right"],
                                transition=True,
                                transition_duration_ms=260,
                            )
                        else:
                            _replace_chart_data(breakdown_chart, metric_hi_res)
                    finally:
                        _block_zoom(breakdown_chart, False)
                    breakdown_chart._metric_source_breakdown = hi_res_breakdown
            _adaptive["dates"] = (zoom_window["first_dt"].date(), zoom_window["last_dt"].date())
            _adaptive["active"] = True
            _adaptive["rows"] = _rows_unfiltered
            btn_reset.setVisible(True)
            _schedule_dots()
        except Exception:
            log_swallowed()
    _on_adaptive_zoom = with_camera(_on_adaptive_zoom)

    def reset_clicked():
        if _adaptive["active"]:
            _restore_adaptive()
            btn_reset.setVisible(False)
            refresh_parent_chart_header_stats(normal_chart)
        else:
            charts_to_reset = [c for c in (normal_chart, breakdown_chart) if c]
            if not charts_to_reset:
                return
            # Block the inter-chart sync while both charts are reset here, so the first
            # reset_zoom() does not pre-reset the second through set_zoom_range (which would
            # make old_display equal new_display and skip the transition).
            for c in charts_to_reset:
                _block_zoom(c, True)
            try:
                with local_chart_animation_batch(charts_to_reset[0], candidates=charts_to_reset):
                    for c in charts_to_reset:
                        c.reset_zoom()
            finally:
                for c in charts_to_reset:
                    _block_zoom(c, False)
            # The zoom signals were blocked, so hide the button and refresh the header by hand.
            btn_reset.setVisible(False)
            refresh_parent_chart_header_stats(charts_to_reset[0])
        from ...zoom_link import propagate_reset
        propagate_reset(normal_chart)
        _dots_apply()
    reset_clicked = with_camera(reset_clicked)
    btn_reset.clicked.connect(reset_clicked)

    def _leave_adaptive():
        """Zoom-out from the full 10-minute view: back to daily data, one step
        wider than the window the user had before."""
        if not _adaptive["active"]:
            return
        pre_zoom = _adaptive.pop("pre_zoom", None)
        _restore_adaptive()
        rows = list(getattr(normal_chart, "_pinned_raw_hist", None) or [])
        if pre_zoom and rows:
            s, e = widen_zoom_window(rows, pre_zoom[0], pre_zoom[1], date_keys=("date", "logical_date"))
            target = breakdown_chart if (breakdown_chart and stack.currentIndex() == 1) else normal_chart
            target.set_zoom_range(s, e)
        btn_reset.setVisible(bool(normal_chart._is_zoomed))
    _leave_adaptive = with_camera(_leave_adaptive)

    _adaptive["leave"] = _leave_adaptive

    for _c in (normal_chart, breakdown_chart):
        if _c is not None and getattr(_c, "zoom_out_limit", None) is not None:
            _c.zoom_out_limit.connect(_leave_adaptive)
    
    def sync_zoom(source_chart, other_chart):
        def _sync(is_zoomed, start, end):
            # Only between charts showing the same rows. During a data update the first chart
            # already has the new rows and the second still the old ones: syncing then would zoom
            # the second on the wrong slice and its transition would start from it.
            if getattr(source_chart, "_full_length", None) != getattr(other_chart, "_full_length", None):
                return
            if other_chart and other_chart.get_zoom_range() != (start, end):
                _block_zoom(other_chart, True)
                other_chart.set_zoom_range(start, end)
                _block_zoom(other_chart, False)
        return _sync

    if normal_chart and breakdown_chart:
        normal_chart.zoom_changed.connect(sync_zoom(normal_chart, breakdown_chart))
        breakdown_chart.zoom_changed.connect(sync_zoom(breakdown_chart, normal_chart))

    if normal_chart:
        normal_chart.zoom_changed.connect(lambda z, s, e: btn_reset.setVisible(z or _adaptive["active"]))
        connect_chart_header_refresh(
            normal_chart,
            header_widget,
            enabled=stats_state["show_header_stats"],
        )
    if breakdown_chart:
        breakdown_chart.zoom_changed.connect(lambda z, s, e: btn_reset.setVisible(z or _adaptive["active"]))
        connect_chart_header_refresh(
            breakdown_chart,
            header_widget,
            enabled=stats_state["show_header_stats"],
            chart_getter=lambda: breakdown_chart if stack.currentIndex() == 1 else normal_chart,
        )

    # Adaptive zoom: re-fetch at 10-min resolution when zoomed span ≤ 2 days
    normal_chart.zoom_changed.connect(lambda z, s, e: _on_adaptive_zoom(z, s, e))
    if breakdown_chart:
        breakdown_chart.zoom_changed.connect(lambda z, s, e: _on_adaptive_zoom(z, s, e))
    for _zc in (normal_chart, breakdown_chart):
        if _zc is not None:
            _zc.zoom_changed.connect(lambda *_a: _schedule_dots())

    if breakdown_chart:
        show_breakdown = widget_def.get("show_breakdown", True)
        cb = _make_checkbox("Breakdown by Type", checked=show_breakdown, parent=header_widget)
        stack.setCurrentIndex(1 if show_breakdown else 0)

        def _on_breakdown_toggled(checked):
            # Switching views should never replay chart transitions.
            freeze_chart_transition_state(normal_chart)
            freeze_chart_transition_state(breakdown_chart)
            _view["breakdown"] = bool(checked)
            if stack.currentIndex() == 2 and dots_chart is not None:
                # One dot per review is on screen: only their colours change, so recolour
                # them in place and stay on the dots.
                mode = getattr(normal_chart, "value_mode", metric_mode)
                dots_chart.set_mode("time" if mode == "time" else "reviews", bool(checked))
                return
            stack.setCurrentIndex(1 if checked else 0)
            _schedule_dots()

        cb.toggled.connect(_on_breakdown_toggled)
        cb.toggled.connect(lambda c, wid=widget_def["id"]: 
                           WidgetRegistry.update_setting(wid, "show_breakdown", c))
        header_lay.addWidget(cb)

    cb_time = _make_checkbox("Time", checked=(metric_mode == "time"), parent=header_widget)
    def _on_time_toggled(checked):
        next_mode = "time" if bool(checked) else "reviews"
        visible_chart = breakdown_chart if (breakdown_chart and stack.currentIndex() == 1) else normal_chart
        with local_chart_animation_batch(visible_chart):
            with preserve_zoom(normal_chart, breakdown_chart):
                normal_chart.set_value_mode(next_mode)
                source_breakdown = getattr(normal_chart, "_metric_source_breakdown", None) or []
                if not source_breakdown:
                    raw_hist = list(getattr(normal_chart, "_pinned_raw_hist", []) or [])
                    source_breakdown = build_breakdown_rows(raw_hist, count_key_style="plain")
                    normal_chart._metric_source_breakdown = source_breakdown
                converted_breakdown = convert_breakdown_metric_rows(
                    source_breakdown,
                    next_mode,
                    count_key_style="plain",
                )
                normal_chart.update_data(
                    converted_breakdown and build_activity_series_from_breakdown(
                        converted_breakdown,
                        count_key_style="plain",
                    ) or []
                )
                if breakdown_chart:
                    breakdown_chart.set_value_mode(next_mode)
                    breakdown_chart.update_data(converted_breakdown)
        WidgetRegistry.update_setting(widget_def["id"], "show_time_axis", bool(checked))
        if dots_chart is not None and dots_chart.isVisible():
            # One dot per review is on screen: glide it to the new mode right away.
            dots_chart.set_mode(next_mode, _view["breakdown"])
        _schedule_dots()
    cb_time.toggled.connect(_on_time_toggled)
    header_lay.addWidget(cb_time)

    stack.setObjectName("activity_stack")
    wrapped = _wrap(stack, None, header_widget=header_widget, 
                    widget_id=widget_def["id"], 
                    saved_w=widget_def.get("width"), 
                    saved_h=widget_def.get("height"),
                    parent=parent)
    if _loading and wrapped is not None:
        wrapped._is_loading = True
    return wrapped

def _update_activity(stack, widget_def, deck_id, cache=None, fail_if_not_cached=False, cfg=None):
    from aqt.qt import QStackedWidget
    if not isinstance(stack, QStackedWidget): return False

    show_avg = widget_def.get("show_average", True)
    show_total = widget_def.get("show_cumulative", True)
    avg_on_active = widget_def.get("avg_on_active_days", True)
    span = widget_def.get("time_span", Period.TOTAL)
    days = widget_def.get("custom_days", 7)

    source = load_activity_source(
        deck_id,
        span,
        cache=cache,
        cfg=cfg,
        custom_days=days,
        fail_if_not_cached=fail_if_not_cached,
        allow_context_slow_ops=(not fail_if_not_cached),
        hidden_types=widget_def.get("hidden_review_types"),
    )
    if source["history_is_none"]:
        return False
    activity_data = source["activity_data"]
    breakdown_data = source["breakdown_data"]
    new_raw_hist = source["raw_hist"]
    metric_mode = "time" if bool(widget_def.get("show_time_axis", False)) else "reviews"
    if breakdown_data is not None:
        breakdown_data = attach_breakdown_totals(breakdown_data, new_raw_hist)
        metric_breakdown_data = convert_breakdown_metric_rows(
            breakdown_data,
            metric_mode,
            count_key_style="plain",
        )
        # Keep Activity totals exactly aligned with Breakdown totals.
        activity_data = build_activity_series_from_breakdown(
            metric_breakdown_data,
            count_key_style="plain",
        )
    else:
        metric_breakdown_data = breakdown_data

    normal_chart = stack.widget(0)
    if hasattr(normal_chart, "update_data"):
        normal_chart._chart_owner = "pinned_activity"
        if cfg is None:
             from ..utils import _addon_config
             cfg = _addon_config()
        adaptive_binning = cfg.config.get(ADAPTIVE_CHART_BINNING, True)
        
        span_token = widget_def.get("_timespan_token", 0)
        transition_meta = get_timespan_transition_meta(
            getattr(normal_chart, "_last_timespan_token", span_token),
            span_token,
            prev_deck_id=getattr(normal_chart, "_last_deck_id", deck_id),
            current_deck_id=deck_id,
            old_series=getattr(normal_chart, "_full_data", []),
            new_series=activity_data,
            total_span_active=(int(span) == int(Period.TOTAL)),
        )
        use_timespan_transition = should_use_timespan_transition(
            transition_meta,
            deck_policy="block",
        )

        normal_chart.set_average_mode(show_avg, avg_on_active)
        normal_chart.set_cumulative_mode(show_total)
        normal_chart.set_value_mode(metric_mode)
        normal_chart.binning_override = widget_def.get("binning_override", None)
        normal_chart.update_data(
            activity_data,
            adaptive_binning=adaptive_binning,
            transition_mode="timespan" if use_timespan_transition else None,
        )
        normal_chart._last_time_span = span
        normal_chart._last_timespan_token = span_token
        normal_chart._last_deck_id = deck_id
        normal_chart._metric_source_breakdown = breakdown_data
        
        wrapper = stack.parentWidget()
        if wrapper:
            refresh_parent_chart_header_stats(normal_chart)
        
    breakdown_chart = stack.widget(1)
    _hidden_now = normalize_hidden_types(widget_def.get("hidden_review_types"))
    try:
        normal_chart._hidden_review_types = _hidden_now
        if breakdown_chart is not None and getattr(breakdown_chart, "_all_series_config", None):
            breakdown_chart.series_config = [
                s for s in breakdown_chart._all_series_config if s["key"] not in _hidden_now
            ]
    except Exception:
        log_swallowed()
    if breakdown_chart and hasattr(breakdown_chart, "update_data") and metric_breakdown_data is not None:
        breakdown_chart._chart_owner = "pinned"
        span_token_b = widget_def.get("_timespan_token", 0)
        transition_meta_b = get_timespan_transition_meta(
            getattr(breakdown_chart, "_last_timespan_token", span_token_b),
            span_token_b,
            prev_deck_id=getattr(breakdown_chart, "_last_deck_id", deck_id),
            current_deck_id=deck_id,
            old_series=getattr(breakdown_chart, "_full_data", []),
            new_series=metric_breakdown_data,
            total_span_active=(int(span) == int(Period.TOTAL)),
        )
        use_timespan_transition_b = should_use_timespan_transition(
            transition_meta_b,
            deck_policy="block",
        )
        breakdown_chart.set_average_mode(show_avg, avg_on_active)
        breakdown_chart.set_cumulative_mode(show_total)
        breakdown_chart.set_value_mode(metric_mode)
        
        if cfg is None:
             from ..utils import _addon_config
             cfg = _addon_config()
             
        colors = {
            "mature": get_color(cfg.config, Config.COLOR_MATURE, "pinned"),
            "young": get_color(cfg.config, Config.COLOR_YOUNG, "pinned"),
            "relearn": get_color(cfg.config, Config.COLOR_RELEARN, "pinned"),
            "learn": get_color(cfg.config, Config.COLOR_LEARN, "pinned"),
            "cram": get_color(cfg.config, Config.COLOR_CRAM, "pinned"),
        }
        
        series_config = [
            {"key": "mature", "label": "Mature", "color": colors["mature"]},
            {"key": "young", "label": "Young", "color": colors["young"]},
            {"key": "relearn", "label": "Relearning", "color": colors["relearn"]},
            {"key": "learn", "label": "Learning", "color": colors["learn"]}, 
            {"key": "cram", "label": "Filtered", "color": colors["cram"]}
        ]
        breakdown_chart._all_series_config = list(series_config)
        breakdown_chart.series_config = [s for s in series_config if s["key"] not in _hidden_now]
        breakdown_chart.update_data(
            metric_breakdown_data,
            adaptive_binning=adaptive_binning,
            transition_mode="timespan" if use_timespan_transition_b else None,
        )
        breakdown_chart._last_time_span = span
        breakdown_chart._last_timespan_token = span_token_b
        breakdown_chart._last_deck_id = deck_id
        breakdown_chart._metric_source_breakdown = breakdown_data
        
    # Refresh adaptive zoom state so handler uses current history after span change
    if hasattr(normal_chart, '_pinned_state'):
        normal_chart._pinned_state["deck_id"] = deck_id
    
    if hasattr(normal_chart, '_pinned_raw_hist'):
        normal_chart._pinned_raw_hist = new_raw_hist
        adaptive = getattr(normal_chart, '_pinned_adaptive', None)
        if adaptive:
            adaptive["active"] = False
            adaptive["pre_normal"] = None
            adaptive["pre_breakdown"] = None
            adaptive["align_right"] = True
            adaptive["rows"] = None
            adaptive.pop("pre_source", None)
            adaptive.pop("pre_zoom", None)
            if stack.currentIndex() == 2:
                stack.setCurrentIndex(1 if (widget_def.get("show_breakdown", True) and stack.widget(1) is not None) else 0)

    if "show_breakdown" in widget_def:
        show_breakdown = widget_def["show_breakdown"]
        target_idx = 1 if show_breakdown else 0
        # Freeze only on actual view switches. Freezing on every refresh kills
        # data-transition animations for both charts.
        if stack.currentIndex() != target_idx:
            freeze_chart_transition_state(normal_chart)
            freeze_chart_transition_state(breakdown_chart)
            stack.setCurrentIndex(target_idx)
        parent = stack.parentWidget()
        if parent:
             from aqt.qt import QCheckBox
             for cb in parent.findChildren(QCheckBox):
                  txt = (cb.text() or "").strip().lower()
                  if "breakdown" in txt:
                      cb.blockSignals(True)
                      cb.setChecked(show_breakdown)
                      cb.blockSignals(False)
                  elif txt == "time":
                      cb.blockSignals(True)
                      cb.setChecked(metric_mode == "time")
                      cb.blockSignals(False)

    return True
