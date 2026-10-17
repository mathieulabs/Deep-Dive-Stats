# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import (
    QWidget, QVBoxLayout, Qt
)
from aqt import mw
from .. import Config, LAST_YEAR, Period
from ..logger import log_error
from ..logger import log_swallowed

DEFAULT_DETAILS_TABS = [
    {"title": "Total", "range": Period.TOTAL, "use_decimal": True, "hrs_unit": "hrs", "min_unit": "min", "show_time": True, "show_reviews": True, "show_retention": True, "show_retention_young": True, "show_retention_mature": True, "show_avg_time": True, "show_counts": True, "show_streak": True, "show_longest_streak": True, "show_buttons_dist": True, "row_height": 30, "show_active_days": True, "show_forecast": True},
    {"title": "Today", "range": Period.TODAY, "use_decimal": True, "hrs_unit": "hrs", "min_unit": "min", "show_time": True, "show_reviews": True, "show_retention": True, "show_retention_young": True, "show_retention_mature": True, "show_avg_time": True, "show_counts": True, "show_streak": True, "show_longest_streak": True, "show_buttons_dist": True, "row_height": 30, "show_active_days": True, "show_forecast": True},
    {"title": "Yesterday", "range": Period.YESTERDAY, "use_decimal": True, "hrs_unit": "hrs", "min_unit": "min", "show_time": True, "show_reviews": True, "show_retention": True, "show_retention_young": True, "show_retention_mature": True, "show_avg_time": True, "show_counts": True, "show_streak": True, "show_longest_streak": True, "show_buttons_dist": True, "row_height": 30, "show_active_days": True, "show_forecast": True},
    {"title": "Past Week", "range": Period.WEEK, "use_decimal": True, "hrs_unit": "hrs", "min_unit": "min", "show_time": True, "show_reviews": True, "show_retention": True, "show_retention_young": True, "show_retention_mature": True, "show_avg_time": True, "show_counts": True, "show_streak": True, "show_longest_streak": True, "show_buttons_dist": True, "row_height": 30, "show_active_days": True, "show_forecast": True},
    {"title": "Past 2 Weeks", "range": Period.TWO_WEEKS, "use_decimal": True, "hrs_unit": "hrs", "min_unit": "min", "show_time": True, "show_reviews": True, "show_retention": True, "show_retention_young": True, "show_retention_mature": True, "show_avg_time": True, "show_counts": True, "show_streak": True, "show_longest_streak": True, "show_buttons_dist": True, "row_height": 30, "show_active_days": True, "show_forecast": True},
    {"title": "Past Month", "range": Period.MONTH, "use_decimal": True, "hrs_unit": "hrs", "min_unit": "min", "show_time": True, "show_reviews": True, "show_retention": True, "show_retention_young": True, "show_retention_mature": True, "show_avg_time": True, "show_counts": True, "show_streak": True, "show_longest_streak": True, "show_buttons_dist": True, "row_height": 30, "show_active_days": True, "show_forecast": True},
    {"title": "Past Year", "range": Period.YEAR, "use_decimal": True, "hrs_unit": "hrs", "min_unit": "min", "show_time": True, "show_reviews": True, "show_retention": True, "show_retention_young": True, "show_retention_mature": True, "show_avg_time": True, "show_counts": True, "show_streak": True, "show_longest_streak": True, "show_buttons_dist": True, "row_height": 30, "show_active_days": True, "show_forecast": True},
    {"title": "Last Year", "range": LAST_YEAR, "use_decimal": True, "hrs_unit": "hrs", "min_unit": "min", "show_time": True, "show_reviews": True, "show_retention": True, "show_retention_young": True, "show_retention_mature": True, "show_avg_time": True, "show_counts": True, "show_streak": True, "show_longest_streak": True, "show_buttons_dist": True, "row_height": 30, "show_active_days": True, "show_forecast": True},
]


def _ensure_time_tab_table(dialog, index):
    from .cache_restore import ensure_time_tab_table
    return ensure_time_tab_table(dialog, index)


def get_tabs_config(addon_config):
    import copy

    return addon_config.config.get(Config.DETAILS_TABS_DATA, copy.deepcopy(DEFAULT_DETAILS_TABS))

def get_active_tabs_config(addon_config):
    """Enabled time spans, in the order of the tabs of the Details window."""
    return [t for t in get_tabs_config(addon_config) if t.get("enabled", True)]


def save_tabs_config(addon_config, tabs_data):
    addon_config.config[Config.DETAILS_TABS_DATA] = tabs_data
    addon_config.write_config()


def refresh_open_details_tabs():
    """Make an open Details window show the saved time spans right away."""
    try:
        from .... import startup

        dlg = getattr(startup, "_current_dialog", None)
        if dlg is None or not dlg.isVisible():
            return
        dlg.invalidate_view_switch_cache()
        if getattr(dlg, "view_mode", "time") == "time":
            dlg.load_tabs()
        else:
            dlg.load_deck_view()
    except Exception:
        log_swallowed()

def stash_time_tabs_for_restore(dialog):
    from .cache_restore import stash_time_tabs_for_restore as _impl
    return _impl(dialog)

def _restore_time_view_from_cache(dialog, cache):
    from .cache_restore import restore_time_view_from_cache as _impl
    return _impl(
        dialog,
        cache,
        populate_time_tab_fn=populate_time_tab,
        ensure_time_tab_table_fn=_ensure_time_tab_table,
    )

def load_tabs(dialog, prefer_cached=False):
    """Load all tabs from configuration with progressive rendering."""
    dialog.load_generation += 1
    gen = dialog.load_generation

    cache = getattr(dialog, "_time_view_cache", None)
    cache_has_payload = bool(cache and cache.get("tabs_data") and cache.get("payloads"))
    if prefer_cached and cache_has_payload:
        if _restore_time_view_from_cache(dialog, cache):
            return
    if getattr(dialog, "_tab_widget_view_kind", None) == "deck":
        try:
            from ...ui.deck_view import stash_deck_tabs_for_restore
            stash_deck_tabs_for_restore(dialog)
        except Exception:
            log_swallowed()
    
    dialog._tab_widget_view_kind = "time"
    dialog.tab_widget.clear()
    dialog._time_tab_payloads = {}
    dialog._time_tab_params = {}
    dialog._time_tabs_populated = set()
    
    tabs_data = get_tabs_config(dialog.addon_config)
    dialog._time_view_cache = {
        "complete": False,
        "tabs_data": [dict(t) for t in tabs_data],
        "week_start": 0,
        "payloads": {},
        "tab_stats": {},
        "ui_tabs": [],
        "selected_index": 0,
        "time_tabs_populated": [],
    }
    
    week_start = dialog.addon_config.config.get(Config.WEEK_START, 0)
    dialog._time_view_cache["week_start"] = week_start
    
    # Calculate active_index for loading priority (Selection happens at the end)
    active_index = 0
    target_span = getattr(dialog, 'target_time_span', None)
    saved_idx = getattr(dialog, '_saved_time_tab', 0)
    _enabled_tabs = [t for t in tabs_data if t.get("enabled", True)]
    if target_span is not None:
         for i, t in enumerate(_enabled_tabs):
              if str(t.get("range")) == str(target_span):
                   active_index = i
                   break
    elif 0 <= saved_idx < len(_enabled_tabs):
        active_index = saved_idx

    from ..data import warm_time_view_static_bundle_async
    warm_time_view_static_bundle_async(
        dialog.addon_config.config.get(Config.EXCLUDED_DECKS, []),
        generation_key=gen,
    )
    
    pending_skeletons = [] # list of (tab_config, original_i)
    pending_data = [] # list of params
    
    for i, tab_config in enumerate(tabs_data):
        if not tab_config.get("enabled", True):
            continue
        pending_skeletons.append((tab_config, i))

    data_loading_started = [False]
    loader_busy = [False] # True while the loader is running

    dialog._tab_fetch_queue = pending_data
    first_tab_wait_attempts = [0]

    def process_next_tab():
        if dialog.load_generation != gen: return
        if not dialog._tab_fetch_queue:
            loader_busy[0] = False
            if getattr(dialog, "_time_view_cache", None):
                dialog._time_view_cache["complete"] = True
            return

        current_idx = dialog.tab_widget.currentIndex()
        if (
            dialog._tab_fetch_queue
            and dialog._tab_fetch_queue[0][26] == current_idx
            and first_tab_wait_attempts[0] < 8
        ):
            from ..data import get_time_view_static_bundle_status
            bundle_status = get_time_view_static_bundle_status(
                dialog.addon_config.config.get(Config.EXCLUDED_DECKS, [])
            )
            if not bundle_status["ready"] and bundle_status["warming"]:
                first_tab_wait_attempts[0] += 1
                from aqt.qt import QTimer
                QTimer.singleShot(20, process_next_tab)
                return
        
        loader_busy[0] = True
        
        current_idx = dialog.tab_widget.currentIndex()
        for i, p_item in enumerate(dialog._tab_fetch_queue):
            if p_item[26] == current_idx:
                p_item = dialog._tab_fetch_queue.pop(i)
                dialog._tab_fetch_queue.insert(0, p_item)
                break
                
        next_params = dialog._tab_fetch_queue.pop(0)
        p = next_params
        
        def on_tab_done(future):
            if dialog.load_generation != gen: return
            from ...widgets.stats_cards import build_dashboard_stat_values, build_total_row_entry
            try:
                data = future.result()
                dialog._time_tab_payloads[p[26]] = data
                if getattr(dialog, "_time_view_cache", None):
                    dialog._time_view_cache["payloads"] = dict(dialog._time_tab_payloads)
                
                totals = data["totals"]
                
                prec = dialog.addon_config.config.get(Config.STATS_PRECISION, 2)
                
                total_row_entry = build_total_row_entry(totals)
                
                results_with_total = data["results"] + [total_row_entry]
                
                stat_values = build_dashboard_stat_values(
                    totals,
                    use_decimal=p[3],
                    hrs_unit=p[4],
                    min_unit=p[5],
                    prec=prec,
                )
                dash_stats = {
                    **stat_values,
                    "results": results_with_total,
                    "meta": data["meta"],
                    "data": data,
                    "range_type": p[1],
                    "show_time": p[6],
                    "show_reviews": p[7],
                    "show_retention": p[8],
                    # Fields needed for re-sort in on_header_clicked
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
                
                dialog.tab_stats[p[26]] = dash_stats
                getattr(dialog, "_refresh_drawer_bar", lambda: None)()
                if getattr(dialog, "_time_view_cache", None):
                    dialog._time_view_cache["tab_stats"] = dict(dialog.tab_stats)
                    dialog._time_view_cache["time_tabs_populated"] = list(getattr(dialog, "_time_tabs_populated", set()) or [])
                
                if p[26] == dialog.tab_widget.currentIndex():
                    populate_time_tab(dialog, p[26], do_resize=False)
                    dialog.on_tab_changed(p[26])
                    from ...ui.details_dialog import auto_resize_window
                    auto_resize_window(dialog, p[0], resize_window=False)
                else:
                    pass
                    
                target_did = getattr(dialog, 'target_deck_id', None)
                if target_did is not None:
                     table_widget = p[0]
                     if table_widget is None:
                         return
                     
                     all_decks = mw.col.decks.all_names_and_ids()
                     target_name = next((d.name for d in all_decks if d.id == target_did), None)
                     
                     if target_name:
                         parts = target_name.split("::")
                         has_new_expansion = False
                         for j in range(1, len(parts)): # We don't expand the exact deck itself, only ancestors
                              parent_path = "::".join(parts[:j])
                              if parent_path not in dialog.expanded_decks:
                                   dialog.expanded_decks.add(parent_path)
                                   has_new_expansion = True
                                   
                         if has_new_expansion:
                              from ...ui.deck_view.visibility import persist_expanded_decks
                              persist_expanded_decks(dialog)
                              for r in range(table_widget.rowCount()):
                                  r_item = table_widget.item(r, 0)
                                  if not r_item: continue
                                  r_path = r_item.data(Qt.ItemDataRole.UserRole)
                                  if not r_path: continue
                                  
                                  curr_text = r_item.text()
                                  if r_path in dialog.expanded_decks and "▸" in curr_text:
                                       r_item.setText(curr_text.replace("▸", "▾", 1))
                                  
                                  r_parts = r_path.split("::")
                                  ancestors = ["::".join(r_parts[:x]) for x in range(1, len(r_parts))]
                                  should_hide = False
                                  for ancestor in ancestors:
                                       if ancestor not in dialog.expanded_decks:
                                            should_hide = True
                                            break
                                  table_widget.setRowHidden(r, should_hide)
                                  
                     target_row_found = False
                     for r in range(table_widget.rowCount()):
                          item = table_widget.item(r, 0)
                          if item:
                               row_data_val = str(item.data(Qt.ItemDataRole.UserRole))
                               if row_data_val == str(target_did if target_did else "deleted") or (target_name and row_data_val == str(target_name)):
                                   table_widget.selectRow(r)
                                   target_row_found = True
                                   break
                               
                     # Fallback: Select parent if nested folder not listed literally
                     if not target_row_found and target_name:
                          parts = target_name.split("::")
                          for j in range(len(parts) - 1, 0, -1):
                               parent_path = "::".join(parts[:j])
                               for r in range(table_widget.rowCount()):
                                    item = table_widget.item(r, 0)
                                    if item and item.data(Qt.ItemDataRole.UserRole) == parent_path:
                                         table_widget.selectRow(r)
                                         target_row_found = True
                                         break
                               if target_row_found:
                                    break
                
            except Exception as e:
                log_error(f"Error loading background tab: {e}")
                log_swallowed()
            finally:
                if dialog.load_generation == gen:
                    from aqt.qt import QTimer
                    next_delay_ms = 140 if p[26] == dialog.tab_widget.currentIndex() else 10
                    QTimer.singleShot(next_delay_ms, process_next_tab)

        from ..data import fetch_stats_for_range
        def bg_worker():
            return fetch_stats_for_range(
                range_type=p[1], week_start=p[2], custom_days=p[13], custom_type=p[14], 
                start_date=p[15], end_date=p[16], pin_top=True,
                spark_precision=p[20]
            )
            
        mw.taskman.run_in_background(bg_worker, on_tab_done)

    prev_updates_enabled = dialog.tab_widget.updatesEnabled()
    prev_bar_updates_enabled = dialog.tab_widget.tabBar().updatesEnabled()
    prev_blocked = dialog.tab_widget.blockSignals(True)
    dialog.tab_widget.setUpdatesEnabled(False)
    dialog.tab_widget.tabBar().setUpdatesEnabled(False)
    try:
        # Build all skeleton tabs immediately
        for _pos, (tab_config, orig_i) in enumerate(pending_skeletons):
            if dialog.load_generation != gen: return
            
            is_active = (_pos == active_index)
            
            title = tab_config.get("title", "Stats")
            range_type = tab_config.get("range", Period.WEEK)
            use_decimal = tab_config.get("use_decimal", True)
            hrs_unit = tab_config.get("hrs_unit", "hrs")
            min_unit = tab_config.get("min_unit", "min")
            show_time = tab_config.get("show_time", True)
            show_reviews = tab_config.get("show_reviews", True)
            show_retention = tab_config.get("show_retention", True)
            show_retention_young = tab_config.get("show_retention_young", True)
            show_retention_mature = tab_config.get("show_retention_mature", True)
            show_avg_time = tab_config.get("show_avg_time", True)
            show_counts = tab_config.get("show_counts", False)
            show_streak = tab_config.get("show_streak", False)
            show_longest_streak = tab_config.get("show_longest_streak", True)
            show_buttons_dist = tab_config.get("show_buttons_dist", True)
            custom_days = tab_config.get("days", 7)
            custom_type = tab_config.get("custom_type", "relative")
            start_date_str = tab_config.get("start_date", "")
            end_date_str = tab_config.get("end_date", "")
            spark_precision = dialog.addon_config.config.get(Config.SPARKLINE_PRECISION, False)
            show_retention_sparkline = dialog.addon_config.config.get(Config.RETENTION_SPARKLINE, False)
            show_active_days = tab_config.get("show_active_days", True)
            show_forecast = tab_config.get("show_forecast", True)
            
            tab = QWidget(dialog.tab_widget)
            tab_layout = QVBoxLayout(tab)
            tab_layout.setContentsMargins(0, 0, 0, 0)
            
            tab_index = dialog.tab_widget.count()
            dialog.tab_widget.addTab(tab, title)
            
            params = [None, range_type, week_start, use_decimal, hrs_unit, min_unit,
                    show_time, show_reviews, show_retention, show_retention_young, show_retention_mature, show_avg_time,
                    show_counts, custom_days, custom_type, start_date_str, end_date_str,
                    show_streak, show_longest_streak,
                    show_buttons_dist, spark_precision, show_retention_sparkline, show_active_days,
                    show_forecast, None, None, tab_index]
            dialog._time_tab_params[tab_index] = params

            if is_active:
                _ensure_time_tab_table(dialog, tab_index)
            
            if is_active:
                dialog._tab_fetch_queue.insert(0, params)
            else:
                dialog._tab_fetch_queue.append(params)
    finally:
        dialog.tab_widget.blockSignals(prev_blocked)
        dialog.tab_widget.setUpdatesEnabled(prev_updates_enabled)
        dialog.tab_widget.tabBar().setUpdatesEnabled(prev_bar_updates_enabled)

    # Finalize selection: Prioritize target_time_span, then fallback to saved index
    best_index = 0
    target_span = getattr(dialog, 'target_time_span', None)
    saved_idx = getattr(dialog, '_saved_time_tab', 0)

    found_target = False
    for i, (tab_config, orig_i) in enumerate(pending_skeletons):
        r = tab_config.get("range")
        if target_span is not None and str(r) == str(target_span):
            best_index = i
            found_target = True
            break
            
    if not found_target and 0 <= saved_idx < dialog.tab_widget.count():
        best_index = saved_idx
        
    dialog.tab_widget.setCurrentIndex(best_index)
    try:
        from ...ui.time_spans import install_time_tab_features

        install_time_tab_features(dialog)
    except Exception:
        log_swallowed()

    
    if not data_loading_started[0] and not loader_busy[0]:
        data_loading_started[0] = True
        process_next_tab()
    
    
    buttons_action = getattr(dialog, '_visual_actions', {}).get(Config.SHOW_BUTTONS_DIST_VISUAL)
    if buttons_action is not None:
        buttons_action.blockSignals(True)
        buttons_action.setChecked(bool(dialog.addon_config.config.get(Config.SHOW_BUTTONS_DIST_VISUAL, True)))
        buttons_action.blockSignals(False)

def prioritize_time_tab(dialog, index):
    """Move a specific tab to the front of the streaming fetch queue."""
    if not hasattr(dialog, '_tab_fetch_queue') or not dialog._tab_fetch_queue:
        return
        
    for i, p_item in enumerate(dialog._tab_fetch_queue):
        if p_item[26] == index:
            target = dialog._tab_fetch_queue.pop(i)
            dialog._tab_fetch_queue.insert(0, target)
            break


def populate_time_tab(dialog, index, do_resize=True):
    """Populate a time-view tab lazily once its background payload is ready."""
    if index < 0:
        return False
    if index in getattr(dialog, "_time_tabs_populated", set()):
        return True

    payloads = getattr(dialog, "_time_tab_payloads", {}) or {}
    params_map = getattr(dialog, "_time_tab_params", {}) or {}
    data = payloads.get(index)
    p = params_map.get(index)
    if not p:
        return False
    table = _ensure_time_tab_table(dialog, index)
    if table is None or not data:
        return False

    from ...ui.table import populate_table
    populate_table(
        table=table, results=data["results"], totals=data["totals"],
        expanded_decks=dialog.expanded_decks,
        deck_colors=dialog.addon_config.config.get(Config.DECK_COLORS, {}),
        range_type=p[1], show_time=p[6], show_reviews=p[7],
        show_retention=p[8], show_retention_young=p[9], show_retention_mature=p[10],
        show_buttons_dist=p[19], show_avg_time=p[11], show_streak=p[17],
        show_longest_streak=p[18], show_active_days=p[22], show_forecast=p[23],
        show_trends=dialog.trend_toggle.isChecked() if hasattr(dialog, 'trend_toggle') else False,
        show_counts=p[12],
        show_buttons_visual=dialog.addon_config.config.get(Config.SHOW_BUTTONS_DIST_VISUAL, True),
        show_retention_sparkline=p[21], use_decimal=p[3], hrs_unit=p[4], min_unit=p[5],
        tree_data=data["tree_data"], bin_labels=data["meta"]["bin_labels"],
        start_ms=data["range_info"]["start_ms"], end_ms=data["range_info"]["end_ms"],
        pin_top=True
    )
    dialog._time_tabs_populated.add(index)
    try:
        table._has_been_resized = False
        if do_resize and dialog.auto_resize_window(table, resize_window=False):
            table._has_been_resized = True
    except Exception:
        log_swallowed()
    return True


