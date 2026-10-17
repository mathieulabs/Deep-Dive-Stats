# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Fractional view used while a bar chart zooms (see chart_utils.zoom_camera).

During the zoom animation the chart is drawn on the bins around the moving window,
shifted and spaced so the window [start, end) (in bins, may be fractional) fills the
plot. widget._zoom_view then holds:

    offset   first visible bin position, from the first drawn bin
    view     number of bins across the plot
    max      left axis maximum
    avg      average line value (None: no line)
    margins  (left, right) plot margins
    geom     optional [(x, width)] per bar, in bins (bars splitting out of wider ones)
    radius   optional corner radius of the bars
"""
import math

from ...chart_utils import ChartGeometry


def dense_bar_ratio(slot_px, ratio):
    """Bar width ratio: the gaps close when bars get only a few pixels wide, so a dense
    chart does not shimmer (stripes beating with the pixel grid) when it moves."""
    if slot_px >= 3.0:
        return ratio
    if slot_px <= 1.5:
        return 1.0
    f = (3.0 - slot_px) / 1.5
    return ratio + (1.0 - ratio) * f


def zoom_view_bar(zv, i, x, width, slot_x0, slot_w):
    """(x, width) of bar i: its own slot, unless the animation gives its geometry
    (bars splitting out of a wider bar), in bins from the first drawn bin."""
    geom = zv.get("geom")
    if geom and i < len(geom):
        gx, gw = geom[i]
        return slot_x0 + gx * slot_w, gw * slot_w
    return x, width


def get_zoom_view(widget):
    return getattr(widget, "_zoom_view", None)


def zoom_view_margins(zv, font_metrics, cumulative_values, cumulative_visible, value_formatter=None):
    if zv.get("margins"):
        # Given by the animation (moves from the start margins to the end ones), so the
        # plot does not shift by a few pixels each frame.
        return zv["margins"]
    left = ChartGeometry.calculate_dynamic_left_margin(
        font_metrics, max(1e-9, float(zv["max"])), value_formatter=value_formatter
    )
    top = cumulative_range(zv, cumulative_values)[1] if cumulative_values else 1.0
    right = ChartGeometry.calculate_dynamic_right_margin(
        font_metrics, [top], cumulative_visible, value_formatter=value_formatter
    )
    return left, right


def bar_slot(zv, plot_left, plot_w):
    """(x of the first drawn bin, width of one bin)."""
    slot = plot_w / max(1e-9, float(zv["view"]))
    return plot_left - float(zv["offset"]) * slot, slot


def _interp(values, x):
    n = len(values)
    if n == 0:
        return 0.0
    if x <= 0:
        return float(values[0])
    if x >= n - 1:
        return float(values[-1])
    i = int(x)
    f = x - i
    return float(values[i]) + (float(values[i + 1]) - float(values[i])) * f


def cumulative_range(zv, cumulative_values):
    """(base, top): the running total restarted at the first visible bin, like the chart
    does for its visible window, but continuous while the window moves.

    With cum_glide (scale, weight) the top follows a scale gliding from the start window's
    total to the end window's, never under what is in view: scaled to its own top on every
    frame, the few rows left at the edge of a nearly empty window would draw a ramp the full
    height of the chart sweeping across it."""
    off = float(zv["offset"])
    last = off + float(zv["view"]) - 1.0
    # The running total before the first visible bin (the bins left of it are not counted;
    # a bin half out of view counts half): cumulative_values[i] includes bin i, so the total
    # before bin i is the previous entry (0 before the first one).
    base = _interp([0.0] + list(cumulative_values), off)
    top = max(1e-9, _interp(cumulative_values, last) - base)
    glide = zv.get("cum_glide")
    if glide:
        scale, weight = glide
        steady = max(float(scale), top)
        if weight >= 1.0:
            top = steady
        elif weight > 0.0:
            top = math.exp(weight * math.log(steady) + (1.0 - weight) * math.log(top))
    return base, top


def cumulative_points(zv, cumulative_values, plot_left, plot_w):
    """[(x, value from 0 to top)] for the running total line, and top."""
    if zv.get("cum_values") is not None:
        # Given by the animation: the real running total (the bars are rescaled).
        cumulative_values = zv["cum_values"]
    base, top = cumulative_range(zv, cumulative_values)
    view = float(zv["view"])
    step = plot_w / (view - 1.0) if view > 1.0 else 0.0
    off = float(zv["offset"])
    pts = [(plot_left + (i - off) * step, float(v) - base) for i, v in enumerate(cumulative_values)]
    return pts, top
