# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Small helpers that turn theme colors and series into hashable cache keys."""

from aqt.qt import QColor


def theme_color_token(value):
    try:
        return int(QColor(value).rgba())
    except Exception:
        return str(value)


def series_cache_token(values):
    out = []
    for value in values or []:
        try:
            out.append(round(float(value or 0.0), 4))
        except Exception:
            out.append(0.0)
    return tuple(out)
