# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QAction, QActionGroup
from .. import Period
from ..theme.icons import get_svg_icon

def populate_span_menu(menu, current_span, current_days, on_update_callback, addon_config, on_manage_callback=None, on_zoom_callback=None):
    """Fill a 'Time Span' menu with mutually exclusive items and custom tab ranges.

    menu: the QMenu or StyledMenu to fill.
    current_span, current_days: current range and custom day count (or None).
    on_update_callback(range_val, custom_days): called when an item is picked.
    addon_config: used to read the tabs.
    on_manage_callback: optional, opens the Time Span settings.
    on_zoom_callback: optional, turns the zoomed chart range into a time span.
    """
    group = QActionGroup(menu)
    
    # Predefined spans, with the tabs configuration below taking priority.
    spans = []
    
    from ...logic.tabs import get_tabs_config
    tabs_config = get_tabs_config(addon_config)
    
    added_ranges = set()
    for tab in tabs_config:
        r = tab.get("range")
        if r is None: continue
        
        days = tab.get("days", None) if r == Period.CUSTOM else None
        label = tab.get("title", "Stats")
        
        # Add if not a duplicate custom range
        if r == Period.CUSTOM:
            spans.append((label, r, days))
        elif r not in added_ranges:
            spans.append((label, r, days))
            added_ranges.add(r)
    
    pass
    
    for label, val, days in spans:
        act = QAction(label, menu)
        act.setCheckable(True)
        act.setActionGroup(group)
        
        is_checked = (int(current_span) == val)
        if val == Period.CUSTOM and days is not None:
            is_checked = is_checked and (current_days == days)
        
        act.setChecked(is_checked)
        act.triggered.connect(lambda _, v=val, d=days: on_update_callback(v, d))
        menu.addAction(act)

    if callable(on_zoom_callback):
        menu.addSeparator()
        zoom_act = QAction("Set zoom as time span", menu)
        zoom_act.setIcon(get_svg_icon("zoom-in", size=14))
        zoom_act.triggered.connect(lambda _=False: on_zoom_callback())
        menu.addAction(zoom_act)

    if callable(on_manage_callback):
        if not callable(on_zoom_callback):
            menu.addSeparator()
        add_new_act = QAction("Add New Time Span", menu)
        add_new_act.setIcon(get_svg_icon("plus", size=14))
        add_new_act.triggered.connect(on_manage_callback)
        menu.addAction(add_new_act)

