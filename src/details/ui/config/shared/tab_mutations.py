# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from ... import Period


def make_new_tab_definition():
    return {
        "title": "New Tab",
        "range": Period.WEEK,
        "use_decimal": True,
        "hrs_unit": "hrs",
        "min_unit": "min",
        "show_time": True,
        "show_reviews": True,
        "show_retention": True,
        "show_retention_young": True,
        "show_retention_mature": True,
        "show_avg_time": True,
        "show_counts": True,
        "show_streak": False,
        "show_active_days": True,
        "show_longest_streak": True,
        "show_buttons_dist": False,
        "show_forecast": True,
        "enabled": True,
    }


def set_tab_field(tabs_data, row, key, value):
    if row < 0 or row >= len(tabs_data or []):
        return False
    tabs_data[row][key] = value
    return True


def format_tab_list_title(title, enabled):
    title = str(title or "")
    return title if bool(enabled) else f"(Archived) {title}"


def set_tab_enabled(tabs_data, row, enabled):
    if row < 0 or row >= len(tabs_data or []):
        return None
    tabs_data[row]["enabled"] = bool(enabled)
    return format_tab_list_title(tabs_data[row].get("title", ""), bool(enabled))


def set_tab_title(tabs_data, row, text):
    if row < 0 or row >= len(tabs_data or []):
        return None
    tabs_data[row]["title"] = text
    return format_tab_list_title(text, tabs_data[row].get("enabled", True))


def append_new_tab(tabs_data):
    tabs_data.append(make_new_tab_definition())
    return len(tabs_data) - 1


def remove_tab(tabs_data, row, min_count=1):
    if row < 0 or row >= len(tabs_data or []):
        return False, "invalid_row", None
    if len(tabs_data) <= int(min_count):
        return False, "min_tabs", None
    removed_title = str(tabs_data[row].get("title", ""))
    del tabs_data[row]
    return True, "removed", removed_title

