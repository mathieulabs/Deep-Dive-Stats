# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
import time

from .. import AddedChartWidget, log_debug
from ....animations.chart_policy import local_chart_animation_batch


# Each part of the stats update runs in its own timer tick, so no single tick holds the
# UI thread long. None of them runs while a zoom still animates: each part takes 15 to 70 ms,
# which made zoom frames late (measured: gaps of 45 to 125 ms between frames). They wait for
# the end of the zoom, then run one after the other, STATS_SPACING_MS apart, the heatmap (the
# heaviest) last. Every part plays its own transition.
# "extra": the added charts that follow the zoom (Week by Hour...), see extra_charts.follow_zoom.
STATS_STEPS = (("cards", 90), ("dist", 120), ("hourly", 150), ("extra", 200), ("heatmap", 310))
STATS_SPACING_MS = 40
_ZOOM_POLL_MS = 30
_ZOOM_WAIT_MAX_S = 1.5  # never wait longer (an animation left behind must not block the stats)


def window_dates(manager, rows):
    """(first, last) day of rows (history rows, days or 10-minute bins), or None when they
    cover the whole period (no zoom)."""
    from ....ui.shared.zoom_span import _row_date

    rows = list(rows or [])
    if not rows:
        return None
    d0, d1 = _row_date(rows[0]), _row_date(rows[-1])
    if d0 is None or d1 is None:
        return None
    dates = (min(d0, d1), max(d0, d1))
    full = list(getattr(manager, "last_history_data", None) or [])
    if full:
        f0, f1 = _row_date(full[0]), _row_date(full[-1])
        if f0 is not None and f1 is not None and dates == (min(f0, f1), max(f0, f1)):
            return None
    return dates


def _linked_extras(manager):
    try:
        from ..extra_charts import zoom_linked_charts

        return zoom_linked_charts(manager)
    except Exception:
        return []


def _zoom_animating(manager):
    """True while one of the zoomed charts still shows its zoom animation."""
    charts = [getattr(manager, a, None) for a in ("activity_chart", "stacked_chart", "retention_chart", "added_chart")]
    for chart in charts + _linked_extras(manager):
        try:
            if chart is not None and getattr(chart, "_zoom_camera", None) is not None:
                return True
        except RuntimeError:
            pass
    return False


def _after_zoom(manager, timers):
    """Wait for the zoom animation to end, then start the pending parts one after the other."""
    from aqt.qt import QTimer

    wait = getattr(manager, "_stats_wait_timer", None)
    if wait is None:
        wait = manager._stats_wait_timer = QTimer()
        wait.setSingleShot(True)

        def _check():
            try:
                since = getattr(manager, "_stats_wait_since", None) or time.perf_counter()
                if _zoom_animating(manager) and time.perf_counter() - since < _ZOOM_WAIT_MAX_S:
                    wait.start(_ZOOM_POLL_MS)
                    return
                manager._stats_wait_since = None
                jobs = getattr(manager, "_stats_jobs", None) or {}
                k = 0
                for part, _delay in STATS_STEPS:
                    if part in jobs and part in timers:
                        timers[part].start(k * STATS_SPACING_MS)
                        k += 1
            except RuntimeError:
                pass

        wait.timeout.connect(_check)
    if not wait.isActive():
        if getattr(manager, "_stats_wait_since", None) is None:
            manager._stats_wait_since = time.perf_counter()
        wait.start(_ZOOM_POLL_MS)


def _stats_candidates(manager):
    return [
        c for c in (
            getattr(manager, "hourly_chart", None),
            getattr(manager, "dist_chart", None),
            getattr(manager, "heatmap_chart", None),
        ) if c is not None
    ]


def _apply_stats(manager, part, data):
    if part == "extra":
        from ..extra_charts import follow_zoom

        # The days of the stats (not a date kept from the last zoom: a reset by the Reset
        # button does not go through sync_zoom).
        follow_zoom(manager, window_dates(manager, data))
        return
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
                if not jobs.get(part):
                    return
                try:
                    since = getattr(manager, "_stats_wait_since", None)
                    waited_long = since is not None and time.perf_counter() - since >= _ZOOM_WAIT_MAX_S
                    if _zoom_animating(manager) and not waited_long:
                        # Not during the zoom: the part waits for its end (see _after_zoom).
                        _after_zoom(manager, timers)
                        return
                except RuntimeError:
                    return
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

    extras = _linked_extras(manager)
    if not valid_charts and not extras:
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
            else:
                data = None

            # The added charts of days: the same days as the stats (the 10-minute view
            # included), by date (their own period may differ from Activity's).
            if extras:
                from ....widgets.pinned.zoom_link import _apply as _zoom_to

                dates = window_dates(manager, data) if data else None
                if dates is None and is_zoomed:
                    try:
                        from ....ui.shared.zoom_span import zoom_dates

                        dates = zoom_dates(source_chart)
                    except Exception:
                        dates = None
                origin = getattr(manager, "_dd_zoom_origin", None)
                for target in extras:
                    if target is source_chart or target is origin:
                        continue
                    try:
                        _zoom_to(target, dates, False)
                    except (RuntimeError, AttributeError, TypeError):
                        pass

            if hasattr(manager, "update_all_reset_buttons"):
                manager.update_all_reset_buttons()

            if hasattr(manager, "_refresh_bottom_stats"):
                manager._refresh_bottom_stats()

        finally:
            manager._is_syncing_zoom = False

    def from_extra(chart, is_zoomed):
        """An added chart of days zoomed: the base chart shown first takes the same dates and
        passes them on as if zoomed itself (the others, the stats), else the other added
        charts follow directly."""
        if (
            getattr(manager, "_is_syncing_zoom", False)
            or getattr(manager, "_syncing_zoom", False)
            or not getattr(manager, "last_sync_zoom", False)
            or getattr(manager, "_dd_refresh_in_progress", False)
        ):
            return
        if getattr(chart, "_applying_data", False):
            # Its data came (read in the background, after the refresh): that reset its zoom.
            # Not passed on: it takes the zoom of the others back once its update is done.
            from aqt.qt import QTimer

            QTimer.singleShot(0, lambda c=chart: _rejoin(c))
            return
        try:
            from ....ui.shared.zoom_span import zoom_dates
            from ....widgets.pinned.zoom_link import _apply as _zoom_to

            dates = zoom_dates(chart) if is_zoomed else None
            if is_zoomed and dates is None:
                return
            anchor = next((c for c in valid_charts if c.isVisible()), None)
            manager._dd_zoom_origin = chart
            try:
                if anchor is not None:
                    _zoom_to(anchor, dates, False)  # its zoom_changed runs sync_zoom
                    return
                manager._is_syncing_zoom = True
                try:
                    for other in extras:
                        if other is not chart:
                            _zoom_to(other, dates, False)
                finally:
                    manager._is_syncing_zoom = False
                history = list(getattr(manager, "last_history_data", None) or [])[::-1]
                if history and dates is not None:
                    from ....ui.shared.zoom_span import _row_date

                    history = [r for r in history if (_row_date(r) is not None and dates[0] <= _row_date(r) <= dates[1])]
                if history:
                    schedule_stats(manager, history)
            finally:
                manager._dd_zoom_origin = None
        except RuntimeError:
            pass
        except Exception:
            from ....logic.logger import log_swallowed

            log_swallowed()

    def _rejoin(chart):
        """chart at the zoom of the charts it is linked with (after its data changed)."""
        try:
            from ....ui.shared.zoom_span import zoom_dates
            from ....widgets.pinned.zoom_link import _apply as _zoom_to

            anchor = next((c for c in valid_charts if c.isVisible()), None)
            if anchor is None or not getattr(anchor, "_is_zoomed", False):
                return
            dates = zoom_dates(anchor)
            if dates is None:
                return
            manager._is_syncing_zoom = True
            try:
                _zoom_to(chart, dates, False)
            finally:
                manager._is_syncing_zoom = False
        except RuntimeError:
            pass
        except Exception:
            from ....logic.logger import log_swallowed

            log_swallowed()

    for chart in extras:
        if hasattr(chart, "_sync_zoom_handler"):
            try:
                chart.zoom_changed.disconnect(chart._sync_zoom_handler)
            except (RuntimeError, TypeError):
                pass
        handler = (lambda c: (lambda z, _s, _e: from_extra(c, bool(z))))(chart)
        chart.zoom_changed.connect(handler)
        chart._sync_zoom_handler = handler

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
