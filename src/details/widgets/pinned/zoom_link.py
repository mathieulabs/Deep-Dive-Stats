# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Zoom-link hooks patched by web_ui/pinned.py when opening pinned context menus."""


def has_charts(_widget):
    return False


def counts(_manager):
    return (0, 0)


def is_linked(_widget):
    return True


def set_linked(_widget, _linked):
    pass


def set_all_linked(_manager, _linked):
    pass


