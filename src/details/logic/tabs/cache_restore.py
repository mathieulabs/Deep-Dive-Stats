# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QTableWidget, QVBoxLayout, QWidget

from .. import Config
from ...widgets import HorizontalScrollTable


def ensure_time_tab_table(dialog, index):
    """Create the heavy table widget for a time tab only when it is actually needed."""
    params_map = getattr(dialog, "_time_tab_params", {}) or {}
    p = params_map.get(index)
    if not p:
        return None

    existing = p[0]
    if existing is not None:
        return existing

    tab = dialog.tab_widget.widget(index)
    if tab is None:
        return None

    layout = tab.layout()
    if layout is None:
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)

    table = HorizontalScrollTable()
    if hasattr(dialog, "_last_horizontal_scroll"):
        table.horizontalScrollBar().setValue(dialog._last_horizontal_scroll)
        table.horizontalScrollBar().valueChanged.connect(dialog._on_horizontal_scroll_changed)

    from ...ui.table import setup_table

    row_height = dialog.addon_config.config.get(Config.GLOBAL_ROW_HEIGHT, 30)
    setup_table(
        dialog,
        table,
        p[6],
        p[7],
        p[8],
        p[9],
        p[10],
        p[11],
        p[17],
        p[18],
        p[19],
        row_height=row_height,
        show_active_days=p[22],
        show_forecast=p[23],
    )
    layout.addWidget(table)
    table.cellDoubleClicked.connect(dialog.on_cell_double_clicked)
    table.cellClicked.connect(dialog.on_cell_clicked)
    p[0] = table
    return table


def stash_time_tabs_for_restore(dialog):
    """Detach current Time View tabs so they can be restored without rebuilding."""
    tw = dialog.tab_widget
    if tw.count() == 0:
        return

    cache = getattr(dialog, "_time_view_cache", None)
    if not isinstance(cache, dict):
        cache = {}

    entries = []
    current_idx = tw.currentIndex()
    while tw.count() > 0:
        w = tw.widget(0)
        title = tw.tabText(0)
        visible = tw.isTabVisible(0)
        tw.removeTab(0)
        if w is not None:
            w.setParent(None)
        entries.append(
            {
                "widget": w,
                "title": title,
                "visible": visible,
            }
        )

    cache["ui_tabs"] = entries
    cache["selected_index"] = current_idx
    cache["time_tabs_populated"] = list(getattr(dialog, "_time_tabs_populated", set()) or [])
    dialog._time_view_cache = cache


def restore_time_view_from_cache(dialog, cache, populate_time_tab_fn, ensure_time_tab_table_fn=None):
    """Restore Time View from an in-memory snapshot (no SQL/background fetch)."""
    ensure_fn = ensure_time_tab_table_fn or ensure_time_tab_table
    tabs_data = [dict(t) for t in (cache.get("tabs_data") or []) if t.get("enabled", True)]
    if not tabs_data:
        return False

    week_start = cache.get("week_start", 0)

    ui_tabs = cache.get("ui_tabs") or []
    if ui_tabs:
        dialog.tab_widget.clear()
        dialog.tab_stats = dict(cache.get("tab_stats") or {})
        dialog._time_tab_payloads = dict(cache.get("payloads") or {})
        dialog._time_tab_params = {}
        dialog._tab_fetch_queue = []

        for i, tab_config in enumerate(tabs_data):
            entry = ui_tabs[i] if i < len(ui_tabs) else {}
            w = entry.get("widget")
            if w is None:
                w = QWidget(dialog.tab_widget)
                lay = QVBoxLayout(w)
                lay.setContentsMargins(0, 0, 0, 0)
            tab_index = dialog.tab_widget.count()
            dialog.tab_widget.addTab(w, entry.get("title", tab_config.get("title", "Stats")))
            dialog.tab_widget.setTabVisible(tab_index, bool(entry.get("visible", True)))

            range_type = tab_config.get("range", "week")
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
            existing_table = w.findChild(QTableWidget)
            params = [
                existing_table,
                range_type,
                week_start,
                use_decimal,
                hrs_unit,
                min_unit,
                show_time,
                show_reviews,
                show_retention,
                show_retention_young,
                show_retention_mature,
                show_avg_time,
                show_counts,
                custom_days,
                custom_type,
                start_date_str,
                end_date_str,
                show_streak,
                show_longest_streak,
                show_buttons_dist,
                spark_precision,
                show_retention_sparkline,
                show_active_days,
                show_forecast,
                None,
                None,
                tab_index,
            ]
            dialog._time_tab_params[tab_index] = params

        cached_populated = set(cache.get("time_tabs_populated") or [])
        if not cached_populated:
            for i in range(dialog.tab_widget.count()):
                w = dialog.tab_widget.widget(i)
                t = w.findChild(QTableWidget) if w else None
                if t is not None and t.rowCount() > 0:
                    cached_populated.add(i)
        dialog._time_tabs_populated = cached_populated

        target_span = getattr(dialog, "target_time_span", None)
        saved_idx = getattr(dialog, "_saved_time_tab", 0)
        best_index = cache.get("selected_index", 0)
        if target_span is not None:
            for i, t in enumerate(tabs_data):
                if str(t.get("range")) == str(target_span):
                    best_index = i
                    break
        elif 0 <= saved_idx < len(tabs_data):
            best_index = saved_idx
        if not (0 <= best_index < dialog.tab_widget.count()):
            best_index = 0

        dialog.tab_widget.setCurrentIndex(best_index)
        if best_index not in dialog._time_tabs_populated:
            ensure_fn(dialog, best_index)
            populate_time_tab_fn(dialog, best_index, do_resize=False)
        dialog._tab_widget_view_kind = "time"
        dialog.on_tab_changed(best_index)
        return True

    dialog.tab_widget.clear()
    dialog.tab_stats = dict(cache.get("tab_stats") or {})
    dialog._time_tab_payloads = dict(cache.get("payloads") or {})
    dialog._time_tab_params = {}
    dialog._time_tabs_populated = set()
    dialog._tab_fetch_queue = []

    target_span = getattr(dialog, "target_time_span", None)
    saved_idx = getattr(dialog, "_saved_time_tab", 0)
    active_index = 0
    if target_span is not None:
        for i, t in enumerate(tabs_data):
            if str(t.get("range")) == str(target_span):
                active_index = i
                break
    elif 0 <= saved_idx < len(tabs_data):
        active_index = saved_idx

    for tab_config in tabs_data:
        title = tab_config.get("title", "Stats")
        range_type = tab_config.get("range", "week")
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

        params = [
            None,
            range_type,
            week_start,
            use_decimal,
            hrs_unit,
            min_unit,
            show_time,
            show_reviews,
            show_retention,
            show_retention_young,
            show_retention_mature,
            show_avg_time,
            show_counts,
            custom_days,
            custom_type,
            start_date_str,
            end_date_str,
            show_streak,
            show_longest_streak,
            show_buttons_dist,
            spark_precision,
            show_retention_sparkline,
            show_active_days,
            show_forecast,
            None,
            None,
            tab_index,
        ]
        dialog._time_tab_params[tab_index] = params

    best_index = active_index if 0 <= active_index < dialog.tab_widget.count() else 0
    dialog.tab_widget.setCurrentIndex(best_index)
    ensure_fn(dialog, best_index)
    populate_time_tab_fn(dialog, best_index, do_resize=False)
    dialog._tab_widget_view_kind = "time"
    dialog.on_tab_changed(best_index)
    return True


