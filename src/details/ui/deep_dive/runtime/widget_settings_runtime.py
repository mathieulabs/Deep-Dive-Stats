# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
import copy

from ... import Config
from ....logic.logger import log_swallowed


def get_dd_widget_setting(manager, section_key, setting_key, default=None):
    """Get a setting for a Deep Dive widget from shared config (mode-aware)."""
    suffix = "_g"
    mode_key = f"{section_key}{suffix}"

    all_settings = manager.addon_config.config.get(Config.DEEP_DIVE_WIDGET_SETTINGS, {})
    widget_settings = all_settings.get(mode_key) or {}

    return widget_settings.get(setting_key, default)


def open_dd_widget_settings(manager, section_key, widget):
    """Open widget settings dialog for a Deep Dive widget (mode-aware)."""
    from ...config import WidgetSettingsDialog

    type_map = {
        "activity": "activity",
        "retention": "retention",
        "added": "added",
        "distribution": "distribution",
        "card_counts": "card_counts",
        "heatmap": "heatmap",
        "hourly": "hourly",
        "future_due": "future_due",
        "review_intervals": "review_intervals",
        "stability": "stability",
        "difficulty": "difficulty",
        "retrievability": "retrievability",
    }
    w_type = type_map.get(section_key, "stat_card" if "stat" in section_key else section_key)

    label_map = {
        "activity": "Activity",
        "retention": "Retention",
        "heatmap": "Heatmap",
        "future_due": "Future Due",
        "distribution": "Answer Buttons",
        "hourly": "Hourly Breakdown",
        "card_counts": "Card Counts",
        "review_intervals": "Review Intervals",
        "stability": "Stability",
        "difficulty": "Difficulty",
        "retrievability": "Retrievability",
        "added": "Added",
    }

    suffix = "_g"
    mode_id = f"{section_key}{suffix}"

    widget_def = {
        "id": mode_id,
        "type": w_type,
        "label": label_map.get(section_key, section_key.replace("_", " ").title()),
        "is_grid": True,
    }

    style_key = Config.DEEP_DIVE_GRID_STYLE
    if style_key not in manager.addon_config.config:
        manager.addon_config.config[style_key] = {}
    global_style = manager.addon_config.config[style_key]

    all_settings = manager.addon_config.config.get(Config.DEEP_DIVE_WIDGET_SETTINGS, {})
    current_settings = all_settings.get(mode_id)

    local_style = copy.deepcopy(current_settings or {})
    dialog_widget_def = copy.deepcopy(widget_def)
    dialog_widget_def.update(local_style)

    current_did = None
    if isinstance(getattr(manager, "last_row_data", None), dict):
        current_did = manager.last_row_data.get("did")
    if current_did is None and isinstance(getattr(manager, "last_deck_identifier", None), int):
        current_did = manager.last_deck_identifier
    dialog_widget_def["deck_id"] = current_did
    dialog_widget_def["time_span"] = manager._get_dd_widget_setting(
        section_key, "time_span", manager.last_history_range
    )
    dialog_widget_def["custom_days"] = manager._get_dd_widget_setting(section_key, "custom_days", 7)

    dialog = WidgetSettingsDialog(
        dialog_widget_def,
        parent=widget,
        global_config=global_style,
        local_config=local_style,
        theme_config=manager.addon_config.config,
    )

    if dialog.exec():
        # Keep per-widget behavior toggles edited via dialog in persisted local settings.
        _style_keys = ("line_opacity", "bar_gradient", "show_grid", "legend_mode", "radio_ranges", "filter_modes")
        for key in ("show_average", "show_cumulative", "avg_on_active_days", "chart_opacity", "show_legend", "tooltip_hidden") + _style_keys:
            if key in dialog_widget_def:
                local_style[key] = dialog_widget_def[key]
            elif key in _style_keys:
                local_style.pop(key, None)  # back to the global value
        manager.addon_config.config[style_key] = global_style
        manager._update_dd_widget_setting(section_key, None, local_style, replace_all=True)


def get_dd_charts_for_section(manager, section_key):
    """Return live chart instances associated with a Deep Dive section key."""
    mapping = {
        "activity": ["activity_chart", "stacked_chart"],
        "retention": ["retention_chart"],
        "added": ["added_chart"],
        "future_due": ["future_due_chart"],
        "review_intervals": ["review_intervals_chart"],
        "stability": ["stability_chart"],
        "difficulty": ["difficulty_chart"],
        "retrievability": ["retrievability_chart"],
        "hourly": ["hourly_chart"],
    }
    attrs = mapping.get(section_key, [])
    charts = []
    for attr in attrs:
        chart = getattr(manager, attr, None)
        if chart is not None:
            charts.append(chart)
    return charts


def apply_dd_widget_setting_live(manager, section_key, key, value):
    """Try to apply a widget setting without rebuilding the whole dashboard."""
    charts = manager._get_dd_charts_for_section(section_key)
    if not charts:
        return False

    applied = False
    key = str(key or "").strip()

    if key in ("show_average", "avg_on_active_days"):
        if section_key not in ("activity", "retention", "added"):
            return False
        show_avg = bool(manager._get_dd_widget_setting(section_key, "show_average", True))
        avg_on_active = bool(manager._get_dd_widget_setting(section_key, "avg_on_active_days", True))
        for chart in charts:
            if hasattr(chart, "set_average_mode"):
                chart.set_average_mode(show_avg, avg_on_active)
                chart.update()
                applied = True

    elif key == "show_cumulative":
        # Retention should never display cumulative totals.
        visible = False if section_key == "retention" else bool(value)
        for chart in charts:
            if hasattr(manager, "_apply_cumulative_mode_to_chart"):
                manager._apply_cumulative_mode_to_chart(chart, visible)
                chart.update()
                applied = True
            elif hasattr(chart, "set_cumulative_mode"):
                chart.set_cumulative_mode(visible)
                chart.update()
                applied = True

    elif key == "chart_opacity":
        try:
            opacity = int(value)
        except Exception:
            return False
        for chart in charts:
            if hasattr(chart, "set_chart_opacity"):
                chart.set_chart_opacity(opacity)
                chart.update()
                applied = True

    elif key in ("line_opacity", "bar_gradient"):
        attr = "line_opacity_pct" if key == "line_opacity" else "bar_gradient_pct"
        for chart in charts:
            setattr(chart, attr, None if value is None else int(value))
            chart.update()
            applied = True

    elif key == "tooltip_hidden":
        for chart in charts:
            chart.tooltip_hidden = list(value or [])
            applied = True

    elif key == "show_grid":
        attr = key + "_flag"
        for chart in charts:
            setattr(chart, attr, None if value is None else bool(value))
            chart.update()
            applied = True

    elif key == "binning_override":
        for chart in charts:
            if hasattr(chart, "binning_override"):
                chart.binning_override = value
                if hasattr(chart, "_invalidate_data_caches"):
                    chart._invalidate_data_caches()
                elif hasattr(chart, "_invalidate_caches"):
                    chart._invalidate_caches()
                chart.update()
                applied = True

    elif key == "fit_to_data":
        for chart in charts:
            if hasattr(chart, "set_fit_to_data"):
                chart.set_fit_to_data(bool(value))
                applied = True

    elif key == "min_reviews":
        for chart in charts:
            if hasattr(chart, "set_min_reviews"):
                chart.set_min_reviews(value)
                applied = True

    elif key == "review_bars":
        for chart in charts:
            if hasattr(chart, "set_review_bars"):
                chart.set_review_bars(bool(value))
                applied = True

    elif key == "review_axis":
        for chart in charts:
            if hasattr(chart, "set_review_axis"):
                chart.set_review_axis(bool(value))
                applied = True

    elif key == "rounded":
        for chart in charts:
            if hasattr(chart, "set_rounded"):
                chart.set_rounded(bool(value))
                applied = True

    if applied and hasattr(manager, "_refresh_bottom_stats"):
        try:
            manager._refresh_bottom_stats()
        except Exception:
            log_swallowed()
    return applied


def update_dd_widget_setting(
    manager,
    section_key,
    key,
    value,
    replace_all=False,
    refresh=True,
    write=True,
):
    """Update one widget setting for the current mode."""
    suffix = "_g"
    mode_key = f"{section_key}{suffix}"

    conf = manager.addon_config.config
    if Config.DEEP_DIVE_WIDGET_SETTINGS not in conf:
        conf[Config.DEEP_DIVE_WIDGET_SETTINGS] = {}

    if mode_key not in conf[Config.DEEP_DIVE_WIDGET_SETTINGS]:
        gen_settings = conf[Config.DEEP_DIVE_WIDGET_SETTINGS].get(section_key, {})
        conf[Config.DEEP_DIVE_WIDGET_SETTINGS][mode_key] = copy.deepcopy(gen_settings)

    if replace_all:
        conf[Config.DEEP_DIVE_WIDGET_SETTINGS][mode_key] = value
    else:
        conf[Config.DEEP_DIVE_WIDGET_SETTINGS][mode_key][key] = value

    if write:
        manager.addon_config.write_config()
    if refresh:
        if (not replace_all) and key is not None:
            if manager._apply_dd_widget_setting_live(section_key, key, value):
                return
        manager._populate_dashboard()


def reset_dd_widget_size(manager, section_key):
    """Reset height and column span for a specific widget."""
    # Grid mode: a vertical reset (height) applies to every widget in the row, a
    # horizontal reset (col_span) only to the clicked widget.
    if getattr(manager, "grid_mode", False):
        try:
            layout = getattr(manager, "current_grid_layout", None)
            wrappers = getattr(manager, "section_wrappers", {}) or {}
            target_wrapper = wrappers.get(section_key)

            if layout and target_wrapper:
                num_cols = int(
                    getattr(layout, "current_cols", 0) or getattr(layout, "preferred_columns", 1) or 1
                )
                num_cols = max(1, num_cols)

                # Simulate target col_span=1 so the target row matches post-reset layout.
                rows = []
                current_row = []
                slots_occupied = 0

                for idx in range(layout.count()):
                    item = layout.itemAt(idx)
                    if not item:
                        continue
                    widget = item.widget()
                    if not widget or widget.isHidden():
                        continue
                    if widget is target_wrapper:
                        span = 1
                    else:
                        span = int(getattr(widget, "col_span", 1) or 1)
                    span = max(1, min(num_cols, span))

                    if slots_occupied + span > num_cols and current_row:
                        rows.append(current_row)
                        current_row = []
                        slots_occupied = 0

                    current_row.append(widget)
                    slots_occupied += span

                if current_row:
                    rows.append(current_row)

                target_row = None
                for row in rows:
                    if target_wrapper in row:
                        target_row = row
                        break

                if target_row:
                    for row_widget in target_row:
                        state_key = getattr(row_widget, "state_key", None)
                        if state_key:
                            manager._update_dd_widget_setting(
                                state_key,
                                "height",
                                None,
                                refresh=False,
                                write=False,
                            )

                    manager._update_dd_widget_setting(
                        section_key,
                        "col_span",
                        1,
                        refresh=False,
                        write=False,
                    )

                    manager.addon_config.write_config()
                    manager._populate_dashboard()
                    return
        except Exception:
            # Row resolution failed: reset this widget on its own below.
            log_swallowed()

    updates = {"height": None, "col_span": 1}
    manager._update_dd_widget_settings_bulk(section_key, updates)


def update_dd_widget_settings_bulk(manager, section_key, updates, refresh=True, write=True):
    """Update several widget settings at once for the current mode."""
    suffix = "_g"
    mode_key = f"{section_key}{suffix}"

    conf = manager.addon_config.config
    if Config.DEEP_DIVE_WIDGET_SETTINGS not in conf:
        conf[Config.DEEP_DIVE_WIDGET_SETTINGS] = {}

    if mode_key not in conf[Config.DEEP_DIVE_WIDGET_SETTINGS]:
        gen_settings = conf[Config.DEEP_DIVE_WIDGET_SETTINGS].get(section_key, {})
        conf[Config.DEEP_DIVE_WIDGET_SETTINGS][mode_key] = copy.deepcopy(gen_settings)

    for key, value in updates.items():
        conf[Config.DEEP_DIVE_WIDGET_SETTINGS][mode_key][key] = value

    if write:
        manager.addon_config.write_config()
    if refresh:
        manager._populate_dashboard()

