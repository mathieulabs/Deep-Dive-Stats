# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QSizePolicy


def apply_chart_display_config(
    chart, *, opacity=None, minimum_height=None, expanding=False, line_opacity=None, bar_gradient=None,
    show_grid=None, tooltip_hidden=None,
):
    if chart is None:
        return None

    if opacity is not None and hasattr(chart, "set_chart_opacity"):
        chart.set_chart_opacity(opacity)

    # Per-chart overrides of the global "Chart Style" settings (None = follow the global value).
    chart.line_opacity_pct = None if line_opacity is None else int(line_opacity)
    chart.bar_gradient_pct = None if bar_gradient is None else int(bar_gradient)
    chart.show_grid_flag = None if show_grid is None else bool(show_grid)
    if tooltip_hidden is not None:
        chart.tooltip_hidden = list(tooltip_hidden)

    if minimum_height is not None and hasattr(chart, "setMinimumHeight"):
        chart.setMinimumHeight(int(minimum_height))

    if expanding and hasattr(chart, "setSizePolicy"):
        chart.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    return chart
