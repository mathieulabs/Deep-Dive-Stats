# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QSize

from ..common.core import set_chart_opacity_impl


def size_hint_impl(widget):
    return QSize(120, 30)


def normalized_values_impl(widget):
    values = []
    for item in widget.data:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            values.append(item[1])
        elif isinstance(item, (int, float)):
            values.append(item)
        else:
            try:
                values.append(float(item))
            except Exception:
                values.append(0)
    return values
