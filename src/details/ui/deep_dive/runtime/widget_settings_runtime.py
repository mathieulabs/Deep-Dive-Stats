# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
import copy

from ... import Config
from ....logic.logger import log_swallowed
from .....i18n import N_


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
        "activity": N_("Activity"),
        "retention": N_("Retention"),
        "heatmap": N_("Heatmap"),
        "future_due": N_("Future Due"),
        "distribution": N_("Answer Buttons"),
        "hourly": N_("Hourly Breakdown"),
        "card_counts": N_("Card Counts"),
        "review_intervals": N_("Review Intervals"),
        "stability": N_("Stability"),
        "difficulty": N_("Difficulty"),
        "retrievability": N_("Retrievability"),
        "added": N_("Added"),
    }
    from ..extra_charts import BY_TYPE as _EXTRA

    for _t, _m in _EXTRA.items():  # the charts added on demand
        label_map[_t] = _m.label

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
        # (tooltip_hidden too: all its lines ticked again leaves no list, the full tooltip)
        _style_keys = ("line_opacity", "bar_gradient", "show_grid", "legend_mode", "radio_ranges", "filter_modes", "own_colors", "tooltip_hidden")
        for key in ("show_average", "show_cumulative", "avg_on_active_days", "chart_opacity", "show_legend") + _style_keys:
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
    # The charts added on demand (extra_charts.build_section keeps them by type).
    extra = (getattr(manager, "_extra_charts", None) or {}).get(section_key)
    if extra is not None:
        try:
            extra[0].isVisible()  # still there
            charts.append(extra[0])
        except RuntimeError:
            pass
    return charts


def apply_dd_widget_setting_live(manager, section_key, key, value):
    """Try to apply a widget setting without rebuilding the whole dashboard."""
    charts = manager._get_dd_charts_for_section(section_key)
    if not charts:
        return False

    applied = False
    key = str(key or "").strip()

    if key in ("show_average", "avg_on_active_days"):
        from ....widgets.charts.more_charts import AVERAGE_TYPES

        if section_key not in ("activity", "retention", "added", *AVERAGE_TYPES):
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

    elif key == "hidden_series" and section_key != "future_due":  # (Future Due: read again)
        for chart in charts:
            if hasattr(chart, "set_hidden_series"):
                chart.set_hidden_series(value)
                applied = True

    elif key == "show_percent":
        for chart in charts:
            if hasattr(chart, "set_percent_mode"):
                chart.set_percent_mode(bool(value))
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
    """Reset Size: the cards' height back to automatic (one height for every row, see
    layout.py: all of them; rows resized one by one: the row of the card clicked) and the
    column span of the card clicked."""
    if getattr(manager, "grid_mode", False) and hasattr(manager, "_clear_grid_heights"):
        try:
            if not manager._shared_row_height():
                # Rows resized one by one: the row of the card clicked.
                target = (getattr(manager, "section_wrappers", {}) or {}).get(section_key)
                row = manager._row_of(target) if target is not None else []
                manager._clear_grid_heights([k for k in [getattr(w, "state_key", None) for w in row] if k]
                                            or [section_key])
            else:
                row = list((getattr(manager, "section_wrappers", {}) or {}).values())
                manager._clear_grid_heights()
            # The cards shown now go back to their automatic height at once (they are kept
            # through the refresh, with their height set by hand otherwise).
            for w in row:
                if w is not None:
                    manager._apply_grid_scale(w, None)
            manager._update_dd_widget_setting(section_key, "col_span", 1, refresh=False, write=False)
            manager.addon_config.write_config()
            manager._populate_dashboard()
            return
        except Exception:
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

