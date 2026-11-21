# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Web version of the Deep Dive views: Python serves data and settings, the page draws.

Layout of this package:
    bridge.py     JSON messages between the page (DD.call) and Python handlers
    providers.py  one data function per chart type, returning plain JSON
    theme.py      the add-on's colors as CSS variables and chart colors
    window.py     the Deep Dive window that hosts the page
    pinned.py     the pinned widgets, drawn by a block inside Anki's own pages
    onigiri.py    the pinned block on the Onigiri add-on's main screen
    web_menus.py  the main screen's right-click menus shown by the page
    live_preview.py  the settings dialogs' changes shown in the pages at once
    settings.py   the add-on's Settings window
    widget_settings.py  a widget's settings dialog drawn as a web page
    widget_options.py   a widget's settings as a schema of options (no Qt), read by widget_settings.py
    gallery_web.py, gallery_model.py, gallery_pics.py  the widget gallery (Add Widget, the Deep Dive's charts)
    text_editor.py, deck_picker.py  what the text editor and the deck picker need from Python
    tour.py       the guided tour of the main screen
    trace.py      what the pages write to debug.log
    web/          what the page loads (css, core, chart modules), served by Anki
"""
