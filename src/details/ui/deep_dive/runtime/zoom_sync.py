# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from .. import AddedChartWidget, log_debug
from ....animations.chart_policy import local_chart_animation_batch


# Each part of the stats update runs in its own timer tick, so no single tick holds the
# UI thread long enough to make a zoom frame late. The heatmap one, the heaviest, runs
# right after the zoom (280 ms). Every part plays its own transition.
STATS_STEPS = (("cards", 90), ("dist", 120), ("hourly", 150), ("heatmap", 310))


def _stats_candidates(manager):
    return [
        c for c in (
            getattr(manager, "hourly_chart", None),
            getattr(manager, "dist_chart", None),
            getattr(manager, "heatmap_chart", None),
        ) if c is not None
    ]


def _apply_stats(manager, part, data):
    candidates = _stats_candidates(manager)
    log_debug(f"[ZOOM-SYNC] Updating stats ({part}): rows={len(data)}", tag="DEEPDIVE")
    if candidates:
        with local_chart_animation_batch(candidates[0], candidates=candidates):
            manager._update_stats_from_history(data, part)
    else:
        manager._update_stats_from_history(data, part)


def schedule_stats(manager, data):
    """Update the stats widgets for data (history rows, oldest first) in steps while a
    zoom animation runs. The last request wins; a direct full update cancels it."""
    from aqt.qt import QTimer

    if not data:
        return
    jobs = getattr(manager, "_stats_jobs", None)
    if jobs is None:
        jobs = manager._stats_jobs = {}
    timers = getattr(manager, "_stats_timers", None)
    if timers is None:
        timers = manager._stats_timers = {}
    for part, delay in STATS_STEPS:
        jobs[part] = data
        timer = timers.get(part)
        if timer is None:
            timer = QTimer()
            timer.setSingleShot(True)

            def _run(part=part):
                pending = jobs.pop(part, None)
                if not pending:
                    return
                try:
                    _apply_stats(manager, part, pending)
                except RuntimeError:
                    pass  # the window went away meanwhile
                except Exception:
                    from ....logic.logger import log_swallowed

                    log_swallowed()

            timer.timeout.connect(_run)
            timers[part] = timer
        timer.start(delay)


def setup_zoom_sync(manager):
    """Link charts so zooming in one zooms the others to the same range."""
    valid_charts = []
    for attr in ["activity_chart", "stacked_chart", "retention_chart", "added_chart"]:
        chart = getattr(manager, attr, None)
        if chart:
            if attr == "added_chart":
                if not manager._get_dd_widget_setting("added", "sync_zoom", True):
                    continue
            valid_charts.append(chart)

    if not valid_charts:
        return

    def sync_zoom(source_chart, is_zoomed, start, end):
        if (
            getattr(manager, "_is_syncing_zoom", False)
            or getattr(manager, "_syncing_zoom", False)
            or getattr(manager, "_adaptive_transitioning", False)
            or not getattr(manager, "last_sync_zoom", False)
        ):
            return
        # Ignore transient zoom callbacks while Deep Dive refreshes datasets.
        if getattr(manager, "_dd_refresh_in_progress", False):
            return
        # A callback whose range no longer matches its chart is stale (an earlier
        # handler swapped the data, e.g. entering the 10-minute view): skip it, or
        # the other charts get zoomed with indexes from the old data.
        try:
            if (bool(source_chart._is_zoomed), int(source_chart._zoom_start), int(source_chart._zoom_end)) != (
                bool(is_zoomed), int(start), int(end)
            ):
                return
        except (AttributeError, RuntimeError, TypeError, ValueError):
            pass

        # If we are in an isolated added-only zoom, ignore sync attempts from Added chart.
        if getattr(manager, "_adaptive_zoom_active_added_only", False):
            if isinstance(source_chart, AddedChartWidget):
                return

        manager._is_syncing_zoom = True
        try:
            log_debug(
                f"[ZOOM_SYNC] Source: {source_chart.__class__.__name__}, "
                f"Zoomed: {is_zoomed}, Range: {start}-{end}"
            )

            adaptive_active = getattr(manager, "_adaptive_zoom_active", False)
            if adaptive_active and hasattr(manager, "_hi_res_history"):
                total_len = len(manager._hi_res_history)
            else:
                total_len = len(manager.last_history_data)

            source_len = getattr(source_chart, "_full_length", total_len)

            # Added chart can have a larger local domain than the standard activity period.

            source_offset = total_len - source_len
            global_start = start + source_offset
            global_end = end + source_offset

            for target in valid_charts:
                if target != source_chart:
                    try:
                        if not is_zoomed:
                            if hasattr(target, "reset_zoom"):
                                target.reset_zoom()
                        else:
                            target_len = getattr(target, "_full_length", total_len)
                            target_offset = total_len - target_len

                            local_start = global_start - target_offset
                            local_end = global_end - target_offset

                            local_start = max(0, local_start)
                            local_end = max(0, min(target_len, local_end))

                            if local_end > local_start:
                                target.set_zoom_range(local_start, local_end)
                            elif hasattr(target, "reset_zoom"):
                                # Never keep stale zoom when mapped slice is invalid.
                                target.reset_zoom()
                    except (RuntimeError, AttributeError):
                        pass

            if adaptive_active:
                history_source = getattr(manager, "_hi_res_history", None)
            else:
                history_source = getattr(manager, "last_history_data", None)

            if hasattr(manager, "_update_stats_from_history") and history_source:
                # If adaptive, history_source is already oldest-first.
                history_oldest_first = history_source if adaptive_active else history_source[::-1]
                if is_zoomed:
                    s = max(0, int(global_start))
                    e = max(0, min(len(history_source), int(global_end)))
                    data = history_oldest_first[s:e] if e > s else None
                else:
                    data = history_oldest_first
                log_debug(f"[ZOOM-SYNC] stats: adaptive={adaptive_active}, zoomed={is_zoomed}", tag="DEEPDIVE")
                schedule_stats(manager, data)

            if hasattr(manager, "update_all_reset_buttons"):
                manager.update_all_reset_buttons()

            if hasattr(manager, "_refresh_bottom_stats"):
                manager._refresh_bottom_stats()

        finally:
            manager._is_syncing_zoom = False

    for chart in valid_charts:
        # Disconnect only previously registered sync handler, not all slots.
        if hasattr(chart, "_sync_zoom_handler"):
            try:
                chart.zoom_changed.disconnect(chart._sync_zoom_handler)
            except (RuntimeError, TypeError):
                pass

        def make_handler(c):
            return lambda z, s, e: sync_zoom(c, z, s, e)

        handler = make_handler(chart)
        chart.zoom_changed.connect(handler)
        chart._sync_zoom_handler = handler
        chart._sync_connected = True
