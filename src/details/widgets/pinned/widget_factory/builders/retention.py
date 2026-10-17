# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from . import ADAPTIVE_CHART_BINNING, Config, HistoryProvider, rollover_hour
from . import pinned_title
from .....animations.chart_policy import local_chart_animation_batch
from ..utils import _make_checkbox, _apply_checkbox_style
from ..wrapper import _wrap
from ..shared.header import add_pinned_zoom_reset_button, prepare_pinned_header
from ....charts.common.zoom import (
    build_adaptive_fetch_bounds,
    resolve_adaptive_zoom_window,
    widen_zoom_window,
    update_chart_for_transition,
)
from ....charts.retention import RetentionChart
from ...store.registry import WidgetRegistry
from ..shared.reviews import load_retention_source
from ....common import (
    apply_chart_display_config,
    connect_chart_header_refresh,
    create_chart_header_for_chart,
    refresh_parent_chart_header_stats,
)
from .....logic.data.transforms.retention_series import (
    RETENTION_SERIES_KEYS,
    build_retention_series,
)
from .....logic.logger import log_swallowed
from ....chart_utils.zoom_camera import with_camera


def _build_retention(widget_def, deck_id, cache=None, parent=None, cfg=None):
    span = widget_def.get("time_span")
    days = widget_def.get("custom_days", 7)

    source = load_retention_source(
        deck_id,
        span,
        cache=cache,
        cfg=cfg,
        custom_days=days,
        fail_if_not_cached=True,
    )
    ret_data = source["retention_data"]
    _raw_hist = source["raw_hist"]
    _loading = bool(source["history_is_none"])
    if _loading:
        pass
    if cfg is None:
        from ..utils import _addon_config
        cfg = _addon_config()
    adaptive_binning = cfg.config.get(ADAPTIVE_CHART_BINNING, True)

    chart = RetentionChart(ret_data, parent=parent, adaptive_binning=adaptive_binning)
    chart.binning_override = widget_def.get("binning_override", None)
    apply_chart_display_config(
        chart,
        opacity=widget_def.get("chart_opacity", 100),
        line_opacity=widget_def.get("line_opacity"),
        bar_gradient=widget_def.get("bar_gradient"),
        show_grid=widget_def.get("show_grid"),
        tooltip_hidden=widget_def.get("tooltip_hidden"),
    )
    show_avg = widget_def.get("show_average", True)
    avg_on_active = widget_def.get("avg_on_active_days", True)
    chart.set_average_mode(show_avg, avg_on_active)
    chart.set_cumulative_mode(False)
    chart.set_fit_to_data(bool(widget_def.get("fit_to_data", False)))
    chart.min_reviews = int(widget_def.get("min_reviews", 0) or 0)
    chart.review_bars = bool(widget_def.get("review_bars", True))
    chart.review_axis = bool(widget_def.get("review_axis", False))
    chart.rounded = bool(widget_def.get("rounded", True))
    
    header_widget, header_lay, _, stats_state = create_chart_header_for_chart(
        chart,
        cfg,
        Config.DEEP_DIVE_PINNED_SHOW_BOTTOM_STATS,
        Config.DEEP_DIVE_PINNED_SHOW_STATS,
        parent=parent,
        title=pinned_title(widget_def, "RETENTION"),
        title_object_name="pinned_header",
    )
    prepare_pinned_header(header_widget, header_lay)
    btn_reset = add_pinned_zoom_reset_button(
        header_widget,
        header_lay,
        retain_size_when_hidden=True,
    )
    _adaptive_ret = {"active": False, "pre_data": None, "dates": None}
    chart._adaptive_state = _adaptive_ret
    # Store on chart so _update_retention can refresh stale closure references
    _state = {"deck_id": deck_id}
    chart._pinned_state = _state
    chart._pinned_raw_hist = _raw_hist
    chart._pinned_adaptive_ret = _adaptive_ret

    def _restore_adaptive_ret():
        pre_data = _adaptive_ret["pre_data"]
        # Clear state BEFORE update_data to prevent re-entry via zoom_changed signal
        _adaptive_ret["active"] = False
        _adaptive_ret["pre_data"] = None
        if pre_data is not None:
            with local_chart_animation_batch(chart):
                _zoom_sigs = getattr(chart, '_zoom_signals', None)
                if _zoom_sigs:
                    _zoom_sigs.blockSignals(True)
                try:
                    if hasattr(chart, "update_data"):
                        update_chart_for_transition(
                            chart,
                            pre_data,
                            adaptive_binning=getattr(chart, "adaptive_binning", None),
                            transition=True,
                            transition_duration_ms=260,
                        )
                    else:
                        chart._full_retention_data = pre_data
                        chart.retention_data = pre_data
                        first_key = next(iter(pre_data))
                        new_len = len(pre_data[first_key])
                        chart._full_length = new_len
                        chart._zoom_start = 0
                        chart._zoom_end = new_len
                        chart._is_zoomed = False
                        if hasattr(chart, '_scrollbar'):
                            chart._scrollbar.hide()
                        if hasattr(chart, '_calc_averages'):
                            chart._calc_averages()
                        chart.update()
                finally:
                    if _zoom_sigs:
                        _zoom_sigs.blockSignals(False)

    def _on_adaptive_zoom_ret(is_zoomed, start, end):
        if _adaptive_ret["active"]:
            # Stays in the 10-minute view until a zoom-out past its full range
            # (_leave_adaptive_ret) or the reset button.
            return
        raw_hist = chart._pinned_raw_hist  # Always read current value
        if not is_zoomed or not raw_hist:
            return
        zoomed_slice = raw_hist[start:end]
        zoom_window = resolve_adaptive_zoom_window(zoomed_slice, date_keys=("date", "logical_date"))
        if zoom_window is None:
            return
        try:
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
            hi_res_ret = build_retention_series(hi_res, strict_series=RETENTION_SERIES_KEYS)
            _adaptive_ret["pre_data"] = chart._full_retention_data
            _adaptive_ret["pre_zoom"] = (int(start), int(end))
            with local_chart_animation_batch(chart):
                _zoom_sigs_enter = getattr(chart, '_zoom_signals', None)
                if _zoom_sigs_enter:
                    _zoom_sigs_enter.blockSignals(True)
                try:
                    if hasattr(chart, "update_data"):
                        update_chart_for_transition(
                            chart,
                            hi_res_ret,
                            adaptive_binning=getattr(chart, "adaptive_binning", None),
                            transition=True,
                            transition_duration_ms=260,
                        )
                    else:
                        chart._full_retention_data = hi_res_ret
                        chart.retention_data = hi_res_ret
                        first_key = next(iter(hi_res_ret))
                        new_len = len(hi_res_ret[first_key])
                        chart._full_length = new_len
                        chart._zoom_start = 0
                        chart._zoom_end = new_len
                        chart._is_zoomed = False
                        if hasattr(chart, '_scrollbar'):
                            chart._scrollbar.hide()
                        if hasattr(chart, '_calc_averages'):
                            chart._calc_averages()
                        chart.update()
                finally:
                    if _zoom_sigs_enter:
                        _zoom_sigs_enter.blockSignals(False)
            _adaptive_ret["dates"] = (zoom_window["first_dt"].date(), zoom_window["last_dt"].date())
            _adaptive_ret["active"] = True
            btn_reset.setVisible(True)
        except Exception:
            log_swallowed()
    _on_adaptive_zoom_ret = with_camera(_on_adaptive_zoom_ret)

    def _ret_reset_clicked():
        if _adaptive_ret["active"]:
            _restore_adaptive_ret()
            btn_reset.setVisible(False)
        else:
            chart.reset_zoom()
        from ...zoom_link import propagate_reset
        propagate_reset(chart)
    _ret_reset_clicked = with_camera(_ret_reset_clicked)

    btn_reset.clicked.connect(_ret_reset_clicked)

    def _leave_adaptive_ret():
        """Zoom-out from the full 10-minute view: back to daily data, one step
        wider than the window the user had before."""
        if not _adaptive_ret["active"]:
            return
        pre_zoom = _adaptive_ret.pop("pre_zoom", None)
        _restore_adaptive_ret()
        rows = list(getattr(chart, "_pinned_raw_hist", None) or [])
        if pre_zoom and rows:
            s, e = widen_zoom_window(rows, pre_zoom[0], pre_zoom[1], date_keys=("date", "logical_date"))
            chart.set_zoom_range(s, e)
        btn_reset.setVisible(bool(chart._is_zoomed))
    _leave_adaptive_ret = with_camera(_leave_adaptive_ret)

    _adaptive_ret["leave"] = _leave_adaptive_ret

    if getattr(chart, "zoom_out_limit", None) is not None:
        chart.zoom_out_limit.connect(_leave_adaptive_ret)

    chart.zoom_changed.connect(lambda z, s, e: btn_reset.setVisible(z or _adaptive_ret["active"]))
    connect_chart_header_refresh(
        chart,
        header_widget,
        enabled=stats_state["show_header_stats"],
    )

    # Adaptive zoom: re-fetch at 10-min resolution when zoomed span ≤ 2 days
    chart.zoom_changed.connect(lambda z, s, e: _on_adaptive_zoom_ret(z, s, e))

    vis_states = widget_def.get("visible_series", {})

    series_checkboxes = {}
    for key, series in RetentionChart.SERIES_CONFIG.items():
        lbl = series["label"]
        is_checked = vis_states.get(key, series["default_on"])
        cb = _make_checkbox(lbl, checked=is_checked, parent=header_widget)
        # Keep retention legend tint dynamic across theme/data-color changes.
        cb.setProperty("deepdivestats_retention_series_key", key)
        cb._deepdivestats_retention_chart_ref = chart

        # Theme-aware checkbox styling with per-series tint (keeps pinned/details themes separated).
        cb.setProperty("deepdivestats_font_weight", "700")
        cb.setProperty("deepdivestats_padding_right", 6)
        _apply_checkbox_style(cb)
        
        chart.set_series_visible(key, is_checked)
        
        def on_toggle(state, k=key, wid=widget_def["id"]):
            val = bool(state)
            chart.set_series_visible(k, val)
            current = widget_def.get("visible_series", {}).copy()
            current[k] = val
            WidgetRegistry.update_setting(wid, "visible_series", current)
            widget_def["visible_series"] = current

            
        cb.stateChanged.connect(on_toggle)
        header_lay.addWidget(cb)
        series_checkboxes[key] = cb

    from ....charts.retention.totals import bind_totals

    bind_totals(chart, series_checkboxes)

    wrapped = _wrap(chart, None, header_widget=header_widget,
                    widget_id=widget_def["id"],
                    saved_w=widget_def.get("width"),
                    saved_h=widget_def.get("height"),
                    parent=parent)
    if _loading and wrapped is not None:
        wrapped._is_loading = True
    return wrapped

def _update_retention(chart, widget_def, deck_id, cache=None, fail_if_not_cached=False, cfg=None):
    show_avg = widget_def.get("show_average", True)
    avg_on_active = widget_def.get("avg_on_active_days", True)
    span = widget_def.get("time_span")
    days = widget_def.get("custom_days", 7)

    source = load_retention_source(
        deck_id,
        span,
        cache=cache,
        cfg=cfg,
        custom_days=days,
        fail_if_not_cached=fail_if_not_cached,
    )
    if source["history_is_none"]:
        return False
    ret_data = source["retention_data"]
    new_raw_hist = source["raw_hist"]

    if hasattr(chart, "update_data"):
        if cfg is None:
            from ..utils import _addon_config
            cfg = _addon_config()
        adaptive_binning = cfg.config.get(ADAPTIVE_CHART_BINNING, True)

        chart.set_average_mode(show_avg, avg_on_active)
        chart.set_cumulative_mode(False)
        chart.set_min_reviews(widget_def.get("min_reviews", 0))
        chart.set_review_bars(widget_def.get("review_bars", True))
        chart.set_review_axis(widget_def.get("review_axis", False))
        chart.set_rounded(widget_def.get("rounded", True))
        chart.binning_override = widget_def.get("binning_override", None)
        if hasattr(chart, "_initial_animation_done"):
            chart._initial_animation_done = True
        chart.update_data(
            ret_data,
            adaptive_binning=adaptive_binning,
            transition=True,
            transition_duration_ms=220,
        )

        if hasattr(chart, '_pinned_state'):
            chart._pinned_state["deck_id"] = deck_id

        # Refresh adaptive zoom state so handler uses current history after span change
        if hasattr(chart, '_pinned_raw_hist'):
            chart._pinned_raw_hist = new_raw_hist
            adaptive = getattr(chart, '_pinned_adaptive_ret', None)
            if adaptive:
                adaptive["active"] = False
                adaptive["pre_data"] = None

        if not cfg.config.get(Config.DEEP_DIVE_PINNED_SHOW_BOTTOM_STATS, False):
            from ..wrapper import ResizableWrapper
            parent_widget = chart.parentWidget()
            while parent_widget and not isinstance(parent_widget, ResizableWrapper):
                parent_widget = parent_widget.parentWidget()
            if parent_widget:
                refresh_parent_chart_header_stats(chart)

        return True
    return False
