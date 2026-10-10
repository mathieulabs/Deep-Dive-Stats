# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
import time

from .. import Config
from ...logic.logger import log_swallowed
from ...widgets.stats_cards import build_dashboard_stat_values, build_total_row_entry

DELETED_TAB_DID = "__deleted_cards__"


def on_trend_toggled(dialog, checked):
    """Refresh currently loaded tables when Trend toggle is clicked (no full reload)."""
    dialog._trend_refresh_run_id = int(getattr(dialog, "_trend_refresh_run_id", 0) or 0) + 1
    run_id = dialog._trend_refresh_run_id
    dialog.addon_config.set_value(Config.SHOW_TRENDS, checked)
    dialog.addon_config.config[Config.SHOW_TRENDS] = checked
    current_idx = dialog.tab_widget.currentIndex()

    if checked:
        from aqt import mw
        from aqt.qt import QTimer

        if dialog.view_mode == "time":
            from ...logic.data import fetch_stats_for_range
            params_map = dict(getattr(dialog, "_time_tab_params", {}) or {})
            queue = sorted(params_map.keys())
            if current_idx in queue:
                queue.remove(current_idx)
                queue.insert(0, current_idx)

            if not queue:
                dialog.load_tabs(reason="trend_toggle_enable_fallback", force=True)
                return

            if hasattr(dialog, "invalidate_view_switch_cache"):
                dialog.invalidate_view_switch_cache()

            state = {"done": 0, "failed": 0, "total": len(queue)}

            def _process_next():
                if getattr(dialog, "_trend_refresh_run_id", 0) != run_id:
                    return
                if not queue:
                    return

                idx = queue.pop(0)
                p = params_map.get(idx)
                if p is None:
                    state["failed"] += 1
                    QTimer.singleShot(1, _process_next)
                    return


                def _fetch():
                    return fetch_stats_for_range(
                        range_type=p[1],
                        week_start=p[2],
                        custom_days=p[13],
                        custom_type=p[14],
                        start_date=p[15],
                        end_date=p[16],
                        pin_top=True,
                        spark_precision=p[20],
                    )

                def _done(future):
                    if getattr(dialog, "_trend_refresh_run_id", 0) != run_id:
                        return
                    try:
                        data = future.result()
                        dialog._time_tab_payloads[idx] = data

                        totals = data["totals"]
                        prec = dialog.addon_config.config.get(Config.STATS_PRECISION, 2)

                        total_row_entry = build_total_row_entry(totals)

                        stat_values = build_dashboard_stat_values(
                            totals,
                            use_decimal=p[3],
                            hrs_unit=p[4],
                            min_unit=p[5],
                            prec=prec,
                        )
                        dialog.tab_stats[idx] = {
                            **stat_values,
                            "results": data["results"] + [total_row_entry],
                            "meta": data["meta"],
                            "data": data,
                            "range_type": p[1],
                            "show_time": p[6],
                            "show_reviews": p[7],
                            "show_retention": p[8],
                            "show_retention_young": p[9],
                            "show_retention_mature": p[10],
                            "show_avg_time": p[11],
                            "show_counts": p[12],
                            "use_decimal": p[3],
                            "hrs_unit": p[4],
                            "min_unit": p[5],
                            "show_buttons_dist": p[19],
                            "show_streak": p[17],
                            "show_longest_streak": p[18],
                            "show_active_days": p[22],
                            "show_forecast": p[23],
                        }

                        if hasattr(dialog, "_time_tabs_populated"):
                            dialog._time_tabs_populated.discard(idx)
                        if idx == dialog.tab_widget.currentIndex():
                            populate_time_tab(dialog, idx, do_resize=True)
                            if hasattr(dialog, "on_tab_changed"):
                                dialog.on_tab_changed(idx)

                        state["done"] += 1
                    except Exception:

                        log_swallowed()
                        state["failed"] += 1
                    QTimer.singleShot(1, _process_next)

                mw.taskman.run_in_background(_fetch, _done)

            _process_next()
            return

        from ...logic.data import fetch_deck_stats
        from ...logic.tabs import get_tabs_config

        tabs_config = [t for t in get_tabs_config(dialog.addon_config) if t.get("enabled", True)]
        excluded = dialog.addon_config.config.get(Config.EXCLUDED_DECKS, [])
        week_start = dialog.addon_config.config.get(Config.WEEK_START, 0)
        spark_precision = dialog.addon_config.config.get(Config.SPARKLINE_PRECISION, False)

        queue = []
        visible_queue = []
        hidden_queue = []
        for i in range(dialog.tab_widget.count()):
            w = dialog.tab_widget.widget(i)
            did = w.property("deck_id") if w else None
            if did in queue:
                continue
            queue.append(did)
            if dialog.tab_widget.isTabVisible(i):
                visible_queue.append(did)
            else:
                hidden_queue.append(did)
        current_did = None
        if current_idx >= 0:
            w = dialog.tab_widget.widget(current_idx)
            current_did = w.property("deck_id") if w else None

        special_dids = {"collection", DELETED_TAB_DID}
        regular_visible = [d for d in visible_queue if d not in special_dids and d != current_did]
        regular_hidden = [d for d in hidden_queue if d not in special_dids and d != current_did]
        special = [d for d in queue if d in special_dids and d != current_did]
        queue = ([current_did] if current_did in queue else []) + regular_visible + regular_hidden + special

        if not queue:
            dialog.load_deck_view(reason="trend_toggle_enable_fallback", force=True)
            return

        if hasattr(dialog, "invalidate_view_switch_cache"):
            dialog.invalidate_view_switch_cache()

        state = {"done": 0, "failed": 0, "total": len(queue)}

        def _process_next_deck():
            if getattr(dialog, "_trend_refresh_run_id", 0) != run_id:
                return
            if not queue:
                return

            did = queue.pop(0)
            fetch_started_at = time.perf_counter()
            is_collection = did == "collection"
            is_deleted = did == DELETED_TAB_DID
            search_did = None if (is_collection or is_deleted) else did

            def _fetch_deck():
                return fetch_deck_stats(
                    search_did,
                    tabs_config,
                    excluded_dids=excluded,
                    show_trends=True,
                    week_start=week_start,
                    spark_precision=spark_precision,
                    is_collection=is_collection,
                    pin_top=True,
                )

            def _done_deck(future):
                if getattr(dialog, "_trend_refresh_run_id", 0) != run_id:
                    return
                next_delay_ms = 18
                try:
                    stats_list = future.result()
                    dialog.deck_view_data[did] = stats_list
                    for i in range(dialog.tab_widget.count()):
                        w = dialog.tab_widget.widget(i)
                        if not w or w.property("deck_id") != did:
                            continue
                        if hasattr(dialog, "_deck_tabs_populated"):
                            dialog._deck_tabs_populated.discard(i)
                        if i == dialog.tab_widget.currentIndex():
                            populate_deck_tab(dialog, i, do_resize=True, from_tab_change=True)
                            if hasattr(dialog, "on_tab_changed"):
                                dialog.on_tab_changed(i)
                            next_delay_ms = 6
                    state["done"] += 1
                    step_ms = (time.perf_counter() - fetch_started_at) * 1000.0
                    if step_ms > 250:
                        next_delay_ms = max(next_delay_ms, 45)
                    elif step_ms > 120:
                        next_delay_ms = max(next_delay_ms, 28)
                except Exception:

                    log_swallowed()
                    state["failed"] += 1
                QTimer.singleShot(next_delay_ms, _process_next_deck)

            mw.taskman.run_in_background(_fetch_deck, _done_deck)

        _process_next_deck()
        return

    if dialog.view_mode == "time":
        from ...logic.tabs import populate_time_tab

        repopulated = 0
        repopulated_active = False
        populated = sorted(getattr(dialog, "_time_tabs_populated", set()) or [])

        for idx in populated:
            dialog._time_tabs_populated.discard(idx)
            if populate_time_tab(dialog, idx, do_resize=(idx == current_idx)):
                repopulated += 1
                if idx == current_idx:
                    repopulated_active = True

        if not repopulated_active and current_idx >= 0:
            dialog._time_tabs_populated.discard(current_idx)
            if populate_time_tab(dialog, current_idx, do_resize=True):
                repopulated += 1
    else:
        from ..deck_view import populate_deck_tab

        repopulated = 0
        repopulated_active = False
        populated = sorted(getattr(dialog, "_deck_tabs_populated", set()) or [])

        for idx in populated:
            dialog._deck_tabs_populated.discard(idx)
            before = len(getattr(dialog, "_deck_tabs_populated", set()) or [])
            populate_deck_tab(dialog, idx, do_resize=(idx == current_idx), from_tab_change=True)
            after = len(getattr(dialog, "_deck_tabs_populated", set()) or [])
            if after > before:
                repopulated += 1
                if idx == current_idx:
                    repopulated_active = True

        if not repopulated_active and current_idx >= 0:
            dialog._deck_tabs_populated.discard(current_idx)
            before = len(getattr(dialog, "_deck_tabs_populated", set()) or [])
            populate_deck_tab(dialog, current_idx, do_resize=True, from_tab_change=True)
            after = len(getattr(dialog, "_deck_tabs_populated", set()) or [])
            if after > before:
                repopulated += 1

    if current_idx >= 0:
        dialog.tab_widget.setCurrentIndex(current_idx)
        if hasattr(dialog, "on_tab_changed"):
            dialog.on_tab_changed(current_idx)


