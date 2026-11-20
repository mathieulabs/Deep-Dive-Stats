# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Web version of the Deep Dive views: Python serves data and settings, the page draws.

Layout of this package:
    bridge.py     JSON messages between the page (DD.call) and Python handlers
    providers.py  one data function per chart type, returning plain JSON
    theme.py      the add-on's colors as CSS variables and chart colors
    window.py     the Deep Dive window that hosts the page
    pinned.py     the pinned widgets, drawn by a block inside Anki's own pages
    live_preview.py  the settings dialogs' changes shown in the pages at once
    widget_settings.py  a widget's settings dialog drawn as a web page
    widget_options.py   a widget's settings as a schema of options (no Qt), read by widget_settings.py
    mode.py       web pages, or the Qt interface kept for development
    trace.py      what the pages write to debug.log
    reference.py  development exports to compare the pages with the Qt interface
    web/          what the page loads (css, core, chart modules), served by Anki
"""
