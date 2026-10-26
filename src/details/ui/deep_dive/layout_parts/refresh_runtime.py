# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Deep Dive layout refresh runtime helpers."""

from datetime import datetime

from aqt.qt import QLabel, QWidget, sip

from ....animations.chart_policy import chart_animation_batch, collect_chart_animation_targets
from ....logic.data.transforms.activity_series import (
    build_activity_series,
    convert_breakdown_metric_rows,
)
from ....logic.data.transforms.heatmap_series import (
    build_heatmap_data,
    extract_heatmap_future_values,
    merge_heatmap_future_values,
)
from ....logic.data.transforms.retention_series import build_retention_series
from ....logic.data.section_fallbacks import resolve_card_counts_payload
from ....logic.data.context_payloads import context_stats
from ....logic.data.section_fetchers import fetch_section_data
from ....widgets.common import get_future_due_range
from ....widgets.pinned.context_access import get_pinned_context
from ... import Period
from .. import FutureDueDataProvider, ReviewIntervalsDataProvider
from ....widgets.charts.common.zoom import (
    get_timespan_transition_meta,
    should_use_timespan_transition,
)
from ....logic.logger import log_swallowed


def _payload_changed(old_payload, new_payload):
    return old_payload != new_payload


def _queue_chart_update(update_queue, animation_candidates, chart, apply_fn, *, animate_candidate=False):
    update_queue.append((chart, apply_fn))
    if animate_candidate and chart is not None:
        animation_candidates.append(chart)


def _sort_animation_candidates_by_section_order(manager, candidates):
    if not candidates:
        return []
    wrappers = getattr(manager, "section_wrappers", {}) or {}
    order_map = {}
    order_idx = 0
    for _, wrapper in wrappers.items():
        if wrapper is None:
            continue
        for target in collect_chart_animation_targets(wrapper):
            tid = id(target)
            if tid not in order_map:
                order_map[tid] = order_idx
                order_idx += 1
    indexed = list(enumerate(candidates))
    indexed.sort(key=lambda item: (order_map.get(id(item[1]), 10**9), item[0]))
    return [candidate for _, candidate in indexed]


def _sort_chart_updates_by_section_order(manager, chart_updates):
    if not chart_updates:
        return []
    wrappers = getattr(manager, "section_wrappers", {}) or {}
    order_map = {}
    order_idx = 0
    for _, wrapper in wrappers.items():
        if wrapper is None:
            continue
        for target in collect_chart_animation_targets(wrapper):
            tid = id(target)
            if tid not in order_map:
                order_map[tid] = order_idx
                order_idx += 1
    indexed = list(enumerate(chart_updates))
    indexed.sort(
        key=lambda item: (
            order_map.get(id(item[1][0]), 10**9) if item[1][0] is not None else 10**9,
            item[0],
        )
    )
    return [entry for _, entry in indexed]


def _dd_refresh_batch_animation_enabled(manager, section_key):
    """
    Restrict the grouped refresh animation budget only for global time-span
    changes. Other refresh reasons should keep the normal broader behavior.
    """
    if str(getattr(manager, "_dd_refresh_reason", "") or "") != "time_span":
        return True
    return str(section_key or "") in {
        "activity",
        "retention",
        "added",
        "distribution",
        "heatmap",
        "hourly",
    }

def refresh_dashboard_data(self):
    """Update data for all existing charts without rebuilding the UI elements."""

    # Guard against transient sync callbacks while we are replacing chart datasets.
    self._dd_refresh_in_progress = True

    # Reset adaptive zoom state: stale hi-res data from a previous deck must not leak.
    self._adaptive_zoom_active = False
    self._adaptive_zoom_active_added_only = False
    self._pre_adaptive_zoom = None
    if hasattr(self, '_hi_res_history'):
        del self._hi_res_history
    for _attr in ("activity_chart", "stacked_chart", "retention_chart", "added_chart"):
        _chart = getattr(self, _attr, None)
        if _chart is not None and hasattr(_chart, "_pre_adaptive_data"):
            # The daily data saved on entering the 10-minute view is replaced by this refresh.
            del _chart._pre_adaptive_data

    ctx_did = self.last_row_data.get("did") if self.last_row_data else None
    is_deleted = self.last_row_data.get("is_deleted", False) if self.last_row_data else False
    _cache_did = -1 if is_deleted else (None if (self.last_row_data and self.last_row_data.get("is_total_row")) else ctx_did)

    from ... import ADAPTIVE_CHART_BINNING
    adaptive_binning = self.addon_config.config.get(ADAPTIVE_CHART_BINNING, True)

    stats_span = self._get_dd_widget_setting("stats", "time_span", self.last_history_range)
    stats_row_data = self.last_row_data
    if stats_span is not None and int(stats_span) != int(self.last_history_range):
        c_days = self._get_dd_widget_setting("stats", "custom_days", 7)
        alt_ctx = get_pinned_context(_cache_did, int(stats_span), cfg=self.addon_config, custom_days=c_days)
        if alt_ctx and alt_ctx.get("stats"):
            cs = context_stats(alt_ctx)
            stats_row_data = dict(self.last_row_data or {})
            stats_row_data.update({
                "reviews": cs.get("total_reviews", 0),
                "time_ms": cs.get("total_time_ms", 0),
                "passed": cs.get("total_passed", 0),
                "rev_young": cs.get("rev_young", 0),
                "pass_young": cs.get("pass_young", 0),
                "rev_mat": cs.get("rev_mat", 0),
                "pass_mat": cs.get("pass_mat", 0),
                "active_days": cs.get("active_days", 0),
                "streak_current": cs.get("streak", 0),
            })
        else:
            stats_row_data = fetch_section_data(
                self.addon_config,
                "stats",
                deck_id=ctx_did,
                range_type=int(stats_span),
                custom_days=c_days,
            )

    if hasattr(self, '_build_stats_section'):
        self._build_stats_section(stats_row_data, manual_add=True, deck_id=ctx_did, time_span=stats_span)

    is_skeleton = getattr(self, "_is_skeleton", False)
    show_empty = self._show_empty_charts()

    def _vis(key, real):
        """Section visibility. With "show empty charts" on, an empty chart stays and gets a No data label."""
        real = bool(real)
        try:
            self._set_section_empty(key, show_empty and not real and not is_skeleton)
        except Exception:
            log_swallowed()
        return real or is_skeleton or show_empty

    if not self.last_history_data and not is_skeleton and not show_empty:
        for k in self.section_wrappers:
            if k != "stats": self._set_section_visible(k, False)
        self._dd_refresh_in_progress = False
        return

    # Always resolve the cache context live from the current deck and range
    _cached_ctx = get_pinned_context(_cache_did, self.last_history_range, cfg=self.addon_config)

    # Widget lookup from one scan of the current sections only: after a rebuild the old
    # charts can still be in the window until Qt deletes them, and a scan of the whole
    # window could find one of those first and give it the data instead.
    _widget_map = {}  # {class_name_lower: widget}
    for _wrapper in list((self.section_wrappers or {}).values()):
        try:
            if _wrapper is None or sip.isdeleted(_wrapper):
                continue
            for _w in _wrapper.findChildren(QWidget):
                _widget_map.setdefault(type(_w).__name__.lower(), _w)
        except RuntimeError:
            continue
    def find_chart(keyword):
        kw = keyword.lower()
        return next((v for k, v in _widget_map.items() if kw in k), None)

    queued_chart_updates = []
    queued_animation_candidates = []

    def _effective_span_and_days(section_key):
        """
        Resolve the real span used by _get_widget_history():
        - In list mode, activity/retention follow global range.
        - Otherwise use widget-specific setting (fallback global).
        """
        if (not self.grid_mode) and section_key in ["activity", "retention"]:
            span_eff = int(self.last_history_range)
        else:
            span_eff = int(self._get_dd_widget_setting(section_key, "time_span", self.last_history_range))
        custom_days_eff = int(self._get_dd_widget_setting(section_key, "custom_days", 7) or 7)
        return span_eff, custom_days_eff

    _real_act = any(h.get("reviews", 0) > 0 for h in (self.last_history_data or []))
    has_act = _vis("activity", _real_act)
    self._set_section_visible("activity", has_act)
    if has_act and hasattr(self, 'activity_chart') and self.activity_chart:
        w_act_history = self._get_widget_history("activity", self.last_history_data)
        w_act_oldest = w_act_history[::-1]
        time_mode_enabled = bool(self._get_dd_widget_setting("activity", "show_time_axis", False))
        metric_mode = "time" if time_mode_enabled else "reviews"
        metric_w_act_oldest = convert_breakdown_metric_rows(
            w_act_oldest,
            metric_mode,
            count_key_style="count",
            preserve_source_fields=True,
        )
        activity_data = build_activity_series(
            metric_w_act_oldest,
            value_key=("time_ms" if metric_mode == "time" else "reviews"),
            scale=(1.0 / 60000.0 if metric_mode == "time" else 1.0),
        )
        cur_span, cur_custom_days = _effective_span_and_days("activity")
        span_token = (int(cur_span), int(cur_custom_days or 0))
        transition_meta = get_timespan_transition_meta(
            getattr(self.activity_chart, "_last_timespan_token", span_token),
            span_token,
            prev_deck_id=getattr(self.activity_chart, "_last_deck_id", self.last_deck_identifier),
            current_deck_id=self.last_deck_identifier,
            old_series=getattr(self.activity_chart, "_full_data", []),
            new_series=activity_data,
            total_span_active=(int(cur_span) == int(Period.TOTAL)),
        )
        # Keep span-change and TOTAL-range date-bound morphs driven by one shared rule set.
        use_timespan_transition = should_use_timespan_transition(
            transition_meta,
            deck_policy="ignore",
        )
        if hasattr(self.activity_chart, "set_value_mode"):
            self.activity_chart.set_value_mode(metric_mode)
        activity_transition_mode = "timespan" if use_timespan_transition else None
        activity_should_animate = _dd_refresh_batch_animation_enabled(self, "activity") and _payload_changed(
            list(getattr(self.activity_chart, "_full_data", []) or []),
            list(activity_data or []),
        )
        _queue_chart_update(
            queued_chart_updates,
            queued_animation_candidates,
            self.activity_chart,
            lambda chart=self.activity_chart, data=activity_data, adaptive=adaptive_binning, mode=activity_transition_mode: chart.update_data(
                data,
                adaptive_binning=adaptive,
                transition_mode=mode,
            ),
            animate_candidate=activity_should_animate,
        )
        self.activity_chart._last_timespan_token = span_token
        self.activity_chart._last_deck_id = self.last_deck_identifier
        if hasattr(self, 'stacked_chart') and self.stacked_chart:
            cur_span_b, cur_custom_days_b = _effective_span_and_days("activity")
            span_token_b = (int(cur_span_b), int(cur_custom_days_b or 0))
            transition_meta_b = get_timespan_transition_meta(
                getattr(self.stacked_chart, "_last_timespan_token", span_token_b),
                span_token_b,
                prev_deck_id=getattr(self.stacked_chart, "_last_deck_id", self.last_deck_identifier),
                current_deck_id=self.last_deck_identifier,
                old_series=getattr(self.stacked_chart, "_full_data", []),
                new_series=metric_w_act_oldest,
                total_span_active=(int(cur_span_b) == int(Period.TOTAL)),
            )
            use_timespan_transition_b = should_use_timespan_transition(
                transition_meta_b,
                deck_policy="ignore",
            )
            if hasattr(self.stacked_chart, "set_value_mode"):
                self.stacked_chart.set_value_mode(metric_mode)
            stacked_transition_mode = "timespan" if use_timespan_transition_b else None
            stacked_should_animate = _dd_refresh_batch_animation_enabled(self, "activity") and _payload_changed(
                list(getattr(self.stacked_chart, "_full_data", []) or []),
                list(metric_w_act_oldest or []),
            )
            _queue_chart_update(
                queued_chart_updates,
                queued_animation_candidates,
                self.stacked_chart,
                lambda chart=self.stacked_chart, data=metric_w_act_oldest, adaptive=adaptive_binning, mode=stacked_transition_mode: chart.update_data(
                    data,
                    adaptive_binning=adaptive,
                    transition_mode=mode,
                ),
                animate_candidate=stacked_should_animate,
            )
            self.stacked_chart._last_timespan_token = span_token_b
            self.stacked_chart._last_deck_id = self.last_deck_identifier

    has_ret = _vis("retention", _real_act) # Retention usually exists if activity exists
    self._set_section_visible("retention", has_ret)
    if has_ret and hasattr(self, 'retention_chart') and self.retention_chart:
        w_ret_history = self._get_widget_history("retention", self.last_history_data)
        w_ret_oldest = w_ret_history[::-1]
        cur_span_r, cur_custom_days_r = _effective_span_and_days("retention")
        span_token_r = (int(cur_span_r), int(cur_custom_days_r or 0))
        has_prev_commit_r = hasattr(self.retention_chart, "_last_committed_deck_id")
        transition_meta_r = get_timespan_transition_meta(
            getattr(self.retention_chart, "_last_committed_timespan_token", span_token_r),
            span_token_r,
            prev_deck_id=getattr(self.retention_chart, "_last_committed_deck_id", self.last_deck_identifier),
            current_deck_id=self.last_deck_identifier,
        )
        use_retention_transition = (
            (not is_skeleton)
            and should_use_timespan_transition(
                transition_meta_r,
                deck_policy="force",
                require_prev_commit=has_prev_commit_r,
            )
        )
        if use_retention_transition and hasattr(self.retention_chart, "_initial_animation_done"):
            self.retention_chart._initial_animation_done = True
        retention_series = build_retention_series(w_ret_oldest, count_default=0)
        retention_should_animate = _dd_refresh_batch_animation_enabled(self, "retention") and bool(use_retention_transition) and _payload_changed(
            dict(getattr(self.retention_chart, "retention_data", {}) or {}),
            dict(retention_series or {}),
        )
        _queue_chart_update(
            queued_chart_updates,
            queued_animation_candidates,
            self.retention_chart,
            lambda chart=self.retention_chart, data=retention_series, adaptive=adaptive_binning, transition=use_retention_transition: chart.update_data(
                data,
                adaptive_binning=adaptive,
                transition=transition,
                transition_duration_ms=220,
            ),
            animate_candidate=retention_should_animate,
        )
        # Only commit transition anchors on real data passes.
        # Skeleton/intermediate refreshes must not consume the next span/deck transition.
        if not is_skeleton:
            self.retention_chart._last_committed_timespan_token = span_token_r
            self.retention_chart._last_committed_deck_id = self.last_deck_identifier

    added_chart = find_chart("addedchart")
    if added_chart and hasattr(added_chart, 'update_data'):
        # Use self.last_history_context (from bg thread) first to preserve high resolution (hourly)
        added_data_desc = None
        if hasattr(self, "last_history_context") and self.last_history_context:
            added_data_desc = self.last_history_context.get("added")

        if added_data_desc is None and _cached_ctx:
            added_data_desc = _cached_ctx.get("added")

        if added_data_desc is None:
            added_data_desc = []

        has_added = _vis("added", (any(d.get("count", 0) > 0 for d in added_data_desc) if added_data_desc else False))
        self._set_section_visible("added", has_added)
        if has_added:
            added_oldest = added_data_desc[::-1]
            cur_span_a, cur_custom_days_a = _effective_span_and_days("activity")
            span_token_a = (int(cur_span_a), int(cur_custom_days_a or 0))
            transition_meta_a = get_timespan_transition_meta(
                getattr(added_chart, "_last_timespan_token", span_token_a),
                span_token_a,
                prev_deck_id=getattr(added_chart, "_last_deck_id", self.last_deck_identifier),
                current_deck_id=self.last_deck_identifier,
                old_series=getattr(added_chart, "_full_data", []),
                new_series=added_oldest,
                total_span_active=(int(cur_span_a) == int(Period.TOTAL)),
            )
            use_timespan_transition_a = should_use_timespan_transition(
                transition_meta_a,
                deck_policy="ignore",
            )
            added_transition_mode = "timespan" if use_timespan_transition_a else None
            added_should_animate = _dd_refresh_batch_animation_enabled(self, "added") and _payload_changed(
                list(getattr(added_chart, "_full_data", []) or []),
                list(added_oldest or []),
            )
            _queue_chart_update(
                queued_chart_updates,
                queued_animation_candidates,
                added_chart,
                lambda chart=added_chart, data=added_oldest, adaptive=adaptive_binning, mode=added_transition_mode: chart.update_data(
                    data,
                    adaptive_binning=adaptive,
                    transition_mode=mode,
                ),
                animate_candidate=added_should_animate,
            )
            added_chart._last_timespan_token = span_token_a
            added_chart._last_deck_id = self.last_deck_identifier
    dist_chart = find_chart("groupedbar")
    if dist_chart and hasattr(dist_chart, 'update_data'):
        cached_dist = _cached_ctx.get("distribution") if _cached_ctx else None
        if cached_dist is not None:
            dist_data = cached_dist
        else:
            dist_data = {}

        has_dist = _vis("distribution", bool(dist_data and any(any(val > 0 for val in counts) for counts in dist_data.values())))
        self._set_section_visible("distribution", has_dist)
        if has_dist:
            dist_should_animate = _dd_refresh_batch_animation_enabled(self, "distribution") and _payload_changed(
                dict(getattr(dist_chart, "data", {}) or {}),
                dict(dist_data or {}),
            )
            _queue_chart_update(
                queued_chart_updates,
                queued_animation_candidates,
                dist_chart,
                lambda chart=dist_chart, data=dist_data: chart.update_data(data),
                animate_candidate=dist_should_animate,
            )

    hm_chart = find_chart("heatmap")
    if hm_chart and hasattr(hm_chart, 'update_data'):
        ctx = getattr(self, "last_history_context", {}) or {}
        hm_context_data = ctx.get("heatmap_data")
        hm_history = self._get_widget_history("heatmap", self.last_history_data)
        hm_data = {}
        if getattr(self, "_is_skeleton", False):
            hm_data = dict(hm_context_data or {})
        else:
            hm_data, _ = build_heatmap_data(
                hm_history,
                skip_zero_review_rows=True,
            )
            future_cells = {}
            if isinstance(hm_context_data, dict):
                future_cells = extract_heatmap_future_values(hm_context_data)
            if not future_cells:
                future_cells = extract_heatmap_future_values(dict(getattr(hm_chart, "data", {}) or {}))
            if future_cells:
                merge_heatmap_future_values(hm_data, future_cells, mode="max")

        has_hm = _vis("heatmap", bool(hm_data))
        self._set_section_visible("heatmap", has_hm)
        if has_hm:
            now = datetime.now()
            current_mode = getattr(hm_chart, "view_mode", "year")
            from ..runtime.heatmap_anchor import resolve_heatmap_state

            self.heatmap_year, self.end_date_365, target_end = resolve_heatmap_state(
                self, current_mode, getattr(self, "_dd_range_last_day", None), now=now
            )
            heatmap_should_animate = _dd_refresh_batch_animation_enabled(self, "heatmap") and _payload_changed(
                dict(getattr(hm_chart, "data", {}) or {}),
                dict(hm_data or {}),
            )
            _queue_chart_update(
                queued_chart_updates,
                queued_animation_candidates,
                hm_chart,
                lambda chart=hm_chart, data=hm_data, end_date=target_end, year=self.heatmap_year: (
                    chart.transition_to(data, end_date),
                    (
                        lambda parent=chart.parentWidget(), label_text=str(year): (
                            parent.findChild(QLabel, "heatmap_year_lbl").setText(label_text)
                            if parent and parent.findChild(QLabel, "heatmap_year_lbl")
                            else None
                        )
                    )(),
                ),
                animate_candidate=heatmap_should_animate,
            )

    # Card counts: prefer context counts, fall back to SQL when missing or suspicious
    pie_chart = find_chart("piechart")
    if pie_chart and hasattr(pie_chart, 'update_data'):
        ctx = getattr(self, "last_history_context", {}) or {}
        counts_data = resolve_card_counts_payload(
            ctx,
            is_deleted=is_deleted,
            fetcher=lambda: fetch_section_data(
                self.addon_config,
                "card_counts",
                deck_id=ctx_did,
                is_deleted=is_deleted,
            ) or {},
        )

        # Deleted cards have no live state: the pie shows the state of their last review.
        has_counts = bool(
            counts_data
            and counts_data.get("total", 0) > 0
            and (not is_deleted or any(counts_data.get(k, 0) > 0 for k in ("learn", "relearn", "young", "mature")))
        )
        self._set_section_visible("card_counts", has_counts)
        if has_counts:
            counts_should_animate = _dd_refresh_batch_animation_enabled(self, "card_counts") and _payload_changed(
                dict(getattr(pie_chart, "counts", {}) or {}),
                dict(counts_data or {}),
            )
            _queue_chart_update(
                queued_chart_updates,
                queued_animation_candidates,
                pie_chart,
                lambda chart=pie_chart, data=counts_data: chart.update_data(data),
                animate_candidate=counts_should_animate,
            )

    # FSRS charts: fall back to SQL via _get_or_fetch_fsrs_data when the context stability is empty
    fsrs_data = self._get_or_fetch_fsrs_data(self.last_row_data or {})

    has_stab = _vis("stability", bool(fsrs_data.get("stability")))
    self._set_section_visible("stability", has_stab)
    stab_chart = find_chart("stabilitychart")
    if has_stab and stab_chart and hasattr(stab_chart, 'update_data'):
        cur_span_s, cur_days_s = _effective_span_and_days("stability")
        span_token_s = (int(cur_span_s), int(cur_days_s or 0))
        transition_meta_s = get_timespan_transition_meta(
            getattr(stab_chart, "_last_timespan_token", span_token_s),
            span_token_s,
            prev_deck_id=getattr(stab_chart, "_last_deck_id", self.last_deck_identifier),
            current_deck_id=self.last_deck_identifier,
        )
        use_timespan_transition_s = should_use_timespan_transition(
            transition_meta_s,
            deck_policy="force",
        )
        stability_payload = fsrs_data.get("stability", {})
        stability_transition_mode = "timespan" if use_timespan_transition_s else None
        stability_should_animate = _dd_refresh_batch_animation_enabled(self, "stability") and _payload_changed(
            dict(getattr(stab_chart, "data_dict", {}) or {}),
            dict(stability_payload or {}),
        )
        _queue_chart_update(
            queued_chart_updates,
            queued_animation_candidates,
            stab_chart,
            lambda chart=stab_chart, data=stability_payload, adaptive=adaptive_binning, mode=stability_transition_mode: chart.update_data(
                data,
                adaptive_binning=adaptive,
                transition_mode=mode,
            ),
            animate_candidate=stability_should_animate,
        )
        stab_chart._last_timespan_token = span_token_s
        stab_chart._last_deck_id = self.last_deck_identifier

    has_diff = _vis("difficulty", bool(fsrs_data.get("difficulty")))
    self._set_section_visible("difficulty", has_diff)
    diff_chart = find_chart("difficultychart")
    if has_diff and diff_chart and hasattr(diff_chart, 'update_data'):
        difficulty_payload = fsrs_data.get("difficulty", {})
        difficulty_should_animate = _dd_refresh_batch_animation_enabled(self, "difficulty") and _payload_changed(
            dict(getattr(diff_chart, "data_dict", {}) or {}),
            dict(difficulty_payload or {}),
        )
        _queue_chart_update(
            queued_chart_updates,
            queued_animation_candidates,
            diff_chart,
            lambda chart=diff_chart, data=difficulty_payload, adaptive=adaptive_binning: chart.update_data(data, adaptive_binning=adaptive),
            animate_candidate=difficulty_should_animate,
        )

    has_retr = _vis("retrievability", bool(fsrs_data.get("retrievability")))
    self._set_section_visible("retrievability", has_retr)
    ret_chart = find_chart("retrievabilitychart")
    if has_retr and ret_chart and hasattr(ret_chart, 'update_data'):
        retrievability_payload = fsrs_data.get("retrievability", {})
        retrievability_should_animate = _dd_refresh_batch_animation_enabled(self, "retrievability") and _payload_changed(
            dict(getattr(ret_chart, "data_dict", {}) or {}),
            dict(retrievability_payload or {}),
        )
        _queue_chart_update(
            queued_chart_updates,
            queued_animation_candidates,
            ret_chart,
            lambda chart=ret_chart, data=retrievability_payload, adaptive=adaptive_binning: chart.update_data(data, adaptive_binning=adaptive),
            animate_candidate=retrievability_should_animate,
        )

    # Hourly breakdown is aggregated from the cached history bins (same source as the activity and retention charts, so always in sync).
    hourly_data = {h: {"total": 0, "correct": 0} for h in range(24)}
    history_source = self.last_history_data or []
    has_bin_hourly = False
    for h_bin in history_source:
        b_hourly = h_bin.get("hourly")
        if b_hourly:
            has_bin_hourly = True
            for h in range(24):
                if h in b_hourly:
                    hourly_data[h]["total"] += b_hourly[h].get("total", 0)
                    hourly_data[h]["correct"] += b_hourly[h].get("correct", 0)

    # Fallback: if bins have no hourly sub-data, use the TOTAL-range cached aggregate
    if not has_bin_hourly and _cached_ctx:
        cached_hourly = _cached_ctx.get("hourly")
        if cached_hourly:
            hourly_data = cached_hourly

    has_hourly = _vis("hourly", bool(any(h_data.get("total", 0) > 0 for h_data in hourly_data.values())))
    self._set_section_visible("hourly", has_hourly)
    hourly_chart = find_chart("hourlybreakdown")
    if has_hourly and hourly_chart and hasattr(hourly_chart, 'update_data'):
        hourly_should_animate = _dd_refresh_batch_animation_enabled(self, "hourly") and _payload_changed(
            dict(getattr(hourly_chart, "data_dict", {}) or {}),
            dict(hourly_data or {}),
        )
        _queue_chart_update(
            queued_chart_updates,
            queued_animation_candidates,
            hourly_chart,
            lambda chart=hourly_chart, data=hourly_data: chart.update_data(data),
            animate_candidate=hourly_should_animate,
        )

    f_idx = self._get_dd_widget_setting("future_due", "time_span_idx")
    from ....widgets.common import resolve_future_due_ranges
    f_span = get_future_due_range(
        f_idx,
        default_idx=0,
        ranges=resolve_future_due_ranges(self._get_dd_widget_setting("future_due", "radio_ranges", None))[0],
    )
    show_backlog_cached = self._get_dd_widget_setting("future_due", "show_backlog", False)

    current_deck_for_future_due = self.last_deck_identifier
    current_seq_for_future_due = getattr(self, "_loading_seq", 0)

    def _refresh_future_due_now():
        # If deck/sequence changed since scheduling, skip stale work.
        if (
            self.last_deck_identifier != current_deck_for_future_due
            or getattr(self, "_loading_seq", 0) != current_seq_for_future_due
        ):
            return

        # Always fetch Future Due from SQL for deck-specific accuracy. The cache keys
        # it by absolute Anki day and only for Period.TOTAL, so it cannot serve deck
        # views or sub-spans.
        future_data = FutureDueDataProvider.fetch_data(
            self.addon_config, self.last_deck_identifier, is_deleted, f_span,
            include_backlog=show_backlog_cached
        )

        has_future = bool(
            future_data
            and (
                future_data.get("total", 0) > 0
                or (show_backlog_cached and future_data.get("backlog", 0) > 0)
            )
        )

        # Also check for scheduled or overdue (backlog) cards. Visible if the deck has
        # any due cards, whether or not the backlog checkbox is on.
        if not has_future:
            total_check = FutureDueDataProvider.fetch_data(
                self.addon_config, self.last_deck_identifier, is_deleted, Period.TOTAL,
                include_backlog=show_backlog_cached
            )
            total_has_visible = bool(
                total_check
                and (
                    total_check.get("total", 0) > 0
                    or (show_backlog_cached and total_check.get("backlog", 0) > 0)
                )
            )
            if total_has_visible:
                has_future = True
                future_data = total_check
            else:
                # Check for backlog even if checkbox is off (determines if section is useful)
                backlog_check = FutureDueDataProvider.fetch_data(
                    self.addon_config, self.last_deck_identifier, is_deleted, f_span,
                    include_backlog=True  # Always check backlog for visibility
                )
                if backlog_check and backlog_check.get("backlog", 0) > 0:
                    has_future = True
                    future_data = backlog_check  # Use backlog-included data; chart will hide bars based on show_backlog

        if show_empty and not has_future and not future_data:
            future_data = {"total": 0, "days": [], "counts": [], "backlog": 0}
        has_future = _vis("future_due", has_future)
        self._set_section_visible("future_due", has_future)
        future_chart = find_chart("futuredue")
        if has_future and future_chart and hasattr(future_chart, 'update_data'):
            future_should_animate = _dd_refresh_batch_animation_enabled(self, "future_due") and (
                _payload_changed(
                    dict(getattr(future_chart, "data_dict", {}) or {}),
                    dict(future_data or {}),
                )
                or bool(getattr(future_chart, "show_backlog", False)) != bool(show_backlog_cached)
            )
            _queue_chart_update(
                queued_chart_updates,
                queued_animation_candidates,
                future_chart,
                lambda chart=future_chart, data=future_data, adaptive=adaptive_binning, show_backlog=show_backlog_cached: (
                    setattr(chart, "show_backlog", show_backlog),
                    chart.update_data(data, adaptive_binning=adaptive),
                ),
                animate_candidate=future_should_animate,
            )

    _refresh_future_due_now()

    cur_span_i, cur_days_i = _effective_span_and_days("review_intervals")
    int_data = ReviewIntervalsDataProvider.fetch_data(self.addon_config, ctx_did, is_deleted, int(cur_span_i))

    if show_empty and not int_data:
        int_data = {"total": 0, "intervals": [], "counts": []}
    has_int = _vis("review_intervals", bool(int_data and int_data.get("total", 0) > 0))
    self._set_section_visible("review_intervals", has_int)
    intervals_chart = find_chart("reviewintervals")
    if has_int and intervals_chart and hasattr(intervals_chart, 'update_data'):
        span_token_i = (int(cur_span_i), int(cur_days_i or 0))
        has_prev_commit_i = hasattr(intervals_chart, "_last_deck_id")
        transition_meta_i = get_timespan_transition_meta(
            getattr(intervals_chart, "_last_timespan_token", span_token_i),
            span_token_i,
            prev_deck_id=getattr(intervals_chart, "_last_deck_id", self.last_deck_identifier),
            current_deck_id=self.last_deck_identifier,
        )
        use_timespan_transition_i = should_use_timespan_transition(
            transition_meta_i,
            deck_policy="block",
            require_prev_commit=has_prev_commit_i,
        )
        intervals_transition_mode = "timespan" if use_timespan_transition_i else None
        intervals_should_animate = _dd_refresh_batch_animation_enabled(self, "review_intervals") and _payload_changed(
            dict(getattr(intervals_chart, "data_dict", {}) or {}),
            dict(int_data or {}),
        )
        _queue_chart_update(
            queued_chart_updates,
            queued_animation_candidates,
            intervals_chart,
            lambda chart=intervals_chart, data=int_data, adaptive=adaptive_binning, mode=intervals_transition_mode: chart.update_data(
                data,
                adaptive_binning=adaptive,
                transition_mode=mode,
            ),
            animate_candidate=intervals_should_animate,
        )
        intervals_chart._last_timespan_token = span_token_i
        intervals_chart._last_deck_id = self.last_deck_identifier

    ordered_animation_candidates = _sort_animation_candidates_by_section_order(
        self,
        queued_animation_candidates,
    )
    ordered_chart_updates = _sort_chart_updates_by_section_order(
        self,
        queued_chart_updates,
    )

    with chart_animation_batch(
        self.dialog,
        ordered_animation_candidates,
        queue_mode=True,
    ):
        for _, apply_chart_update in ordered_chart_updates:
            apply_chart_update()

    self._refresh_bottom_stats()

    if hasattr(self, '_show_and_animate'):
        self._show_and_animate()
    self._dd_refresh_in_progress = False


