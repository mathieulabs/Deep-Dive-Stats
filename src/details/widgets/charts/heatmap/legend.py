# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Color legend under the heatmap: what each color step means, with numbers."""
import math

from aqt.qt import QColor, QEasingCurve, QFont, QFontMetrics, QPen, QRectF, QVariantAnimation, Qt

from ...chart_utils import get_theme_colors
from .metrics import components

LEGEND_STEPS = 5


def _legend_scale(widget):
    """The legend keeps a readable size even when the heatmap itself is scaled down."""
    return max(1.0, float(getattr(widget, "scale", 1.0)))


def level_starts(widget):
    """First color level of each legend swatch after the empty one."""
    n = int(widget.color_levels)
    steps = min(LEGEND_STEPS, n)
    return sorted({round(i * (n - 1) / (steps - 1)) for i in range(steps)}) if steps > 1 else [0]


def step_for_level(widget, level):
    """Index of the legend swatch (0 = the first colored one) a color level belongs to."""
    step = 0
    for i, start in enumerate(level_starts(widget)):
        if level >= start:
            step = i
    return step


def legend_step_at(widget, pos):
    """Legend swatch under pos (a QPointF), or None."""
    if pos is None:
        return None
    for rect, step in getattr(widget, "_legend_hits", None) or []:
        if rect.contains(pos):
            return step
    return None


def legend_height(widget):
    """Extra height reserved for the legend (0 when it is off)."""
    if not getattr(widget, "show_legend", False):
        return 0
    return int(28 * _legend_scale(widget))


def format_threshold(metric, value):
    """Short text for a threshold, in the unit of the metric."""
    comps = components(metric) or [("reviews", None)]
    if len(comps) > 1:
        # Several measures: the cell shows an index from 0 to 100 against each one's own scale.
        return f"{int(round(value))}%"
    key = comps[0][0]
    if key == "time":
        secs = value / 1000.0
        if secs >= 3600:
            return f"{secs / 3600.0:.1f}h"
        if secs >= 60:
            return f"{int(round(secs / 60.0))}m"
        return f"{int(round(secs))}s"
    if key == "avg_time":
        secs = value / 1000.0
        return f"{secs:.1f}s" if secs < 10 else f"{int(round(secs))}s"
    if key == "retention":
        return f"{int(round(value))}%"
    if value >= 10000:
        return f"{value / 1000.0:.0f}k"
    return f"{int(math.ceil(value))}"


def legend_items(widget):
    """[(color, text)] from empty to the strongest step. Cached per data and settings."""
    n = int(widget.color_levels)
    levels = list(getattr(widget, "levels", []) or [])
    if n < 2 or len(levels) < n:
        return []
    key = (
        id(widget.data), len(widget.data), widget.metric, widget.view_mode,
        getattr(widget, "cont_month_offset", 0), str(widget.end_date), n,
        widget.intensity_curve, bool(widget.invert_intensity),
    )
    if getattr(widget, "_last_max_counts", None) is None:
        widget._get_max_counts()
    # The swatches are the cells' own colors, so any change of opacity, theme or color must rebuild them.
    key = key + (
        widget._last_max_counts[0],
        QColor(widget.empty_color).rgba(),
        tuple(QColor(c).rgba() for c in levels[:n]),
    )
    cached = getattr(widget, "_legend_cache", None)
    if cached is not None and cached[0] == key:
        return cached[1]
    previous = cached[1] if cached is not None else None

    max_past = widget._last_max_counts[0]
    curve = 65.0 / max(1.0, float(widget.intensity_curve))
    idxs = level_starts(widget)
    comps = components(widget.metric) or [("reviews", None)]
    count_like = len(comps) == 1 and comps[0][0] not in ("time", "avg_time", "retention")
    items = [(widget.empty_color, "0")]
    for li in idxs:
        if li == 0:
            text = "1" if count_like else ">0"
        else:
            low = max_past * ((li / float(n)) ** (1.0 / curve))
            text = format_threshold(widget.metric, low)
        if li == idxs[-1]:
            text += "+"
        items.append((levels[li], text))
    widget._legend_cache = (key, items)
    _animate_legend_change(widget, previous, items)
    return items


def _animate_legend_change(widget, previous, items):
    """Blend the swatch colors and cross-fade the numbers when the legend values change
    (another deck, period or metric), in step with the cells."""
    if not previous or len(previous) != len(items) or not widget.isVisible():
        return
    if all(a[1] == b[1] for a, b in zip(previous, items)):
        # Only the colors changed (opacity, theme): follow the cells at once.
        return
    try:
        from ....animations.chart_policy import chart_animations_allowed

        if not chart_animations_allowed(widget):
            return
    except Exception:
        return
    anim = getattr(widget, "_legend_anim", None)
    if anim is None:
        anim = QVariantAnimation(widget)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setDuration(320)
        anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        anim.valueChanged.connect(lambda v, w=widget: _legend_anim_step(w, float(v)))
        anim.finished.connect(lambda w=widget: _legend_anim_done(w))
        widget._legend_anim = anim
    anim.stop()
    widget._legend_from = list(previous)
    widget._legend_t = 0.0
    anim.start()


def _legend_anim_step(widget, t):
    widget._legend_t = t
    widget.update()


def _legend_anim_done(widget):
    widget._legend_from = None
    widget._legend_t = 1.0
    widget.update()


def paint_legend(widget, painter):
    h = legend_height(widget)
    if h <= 0:
        return
    items = legend_items(widget)
    if not items:
        return
    colors = get_theme_colors(widget)
    text_col = colors["text"]
    scale = _legend_scale(widget)

    painter.save()
    font = QFont(painter.font())
    font.setPointSizeF(9.0 * scale)
    painter.setFont(font)
    fm = QFontMetrics(font)
    sq = 13.0 * scale
    gap = 5.0 * scale
    between = 11.0 * scale
    less, more = "Less", "More"

    def total_width(with_numbers):
        w = fm.horizontalAdvance(less) + gap + fm.horizontalAdvance(more) + gap
        for _c, t in items:
            w += sq + (gap + fm.horizontalAdvance(t) if with_numbers else 0) + between
        return w - between + gap

    with_numbers = total_width(True) <= widget.width() - 8
    total = total_width(with_numbers)
    right = widget.width() - 6.0
    top = widget.height() - h
    if getattr(widget, "grid_mode", False) and getattr(widget, "view_mode", "year") != "continuous":
        # Under the grid, lined up with its right edge, instead of in the corner of a taller card.
        try:
            cell, spacing, start_x, start_y, _label = widget._get_grid_geometry()
            right = min(right, start_x + 53 * (cell + spacing) - spacing)
            top = min(top, start_y + 7 * (cell + spacing) - spacing + 10 * getattr(widget, "scale", 1.0))
        except Exception:
            pass
    x = max(4.0, right - total)
    y = top + (h - sq) / 2.0 - 1

    painter.setPen(text_col)
    painter.drawText(QRectF(x, y - 4, fm.horizontalAdvance(less) + 2, sq + 8), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, less)
    x += fm.horizontalAdvance(less) + gap
    radius = (sq / 2.0) * (widget.rounding / 100.0)
    hidden = getattr(widget, "hidden_legend_steps", None) or frozenset()
    old_items = getattr(widget, "_legend_from", None)
    t = float(getattr(widget, "_legend_t", 1.0))
    if old_items is not None and len(old_items) != len(items):
        old_items = None
    hits = []
    for i, (color, text) in enumerate(items):
        step = i - 1  # items[0] is the empty swatch, not clickable
        off = step in hidden
        x0 = x
        painter.setOpacity(0.4 if off else 1.0)
        draw_color = color
        if old_items is not None:
            draw_color = widget._lerp_color(old_items[i][0], color, t)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(draw_color)
        painter.drawRoundedRect(QRectF(x, y, sq, sq), radius, radius)
        if off:
            # Outlined swatch: this range is hidden in the heatmap.
            pen = QPen(text_col)
            pen.setWidthF(1.0)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(QRectF(x + 0.5, y + 0.5, sq - 1, sq - 1), radius, radius)
        x += sq
        if with_numbers:
            x += gap
            painter.setPen(text_col)
            w = fm.horizontalAdvance(text)
            rect = QRectF(x, y - 4, w + 2, sq + 8)
            flags = Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
            old_text = old_items[i][1] if old_items is not None else text
            if old_text != text:
                base = painter.opacity()
                if t < 0.5:
                    painter.setOpacity(base * (1.0 - t * 2.0))
                    painter.drawText(rect, flags, old_text)
                else:
                    painter.setOpacity(base * (t * 2.0 - 1.0))
                    painter.drawText(rect, flags, text)
            else:
                painter.drawText(rect, flags, text)
            if off:
                mid = y + sq / 2.0
                painter.drawLine(int(x), int(mid), int(x + w), int(mid))
            x += w
        painter.setOpacity(1.0)
        if step >= 0:
            hits.append((QRectF(x0 - 2, y - 3, x - x0 + 4, sq + 6), step))
        x += between
    widget._legend_hits = hits
    x += gap - between
    painter.setPen(text_col)
    painter.drawText(QRectF(x, y - 4, fm.horizontalAdvance(more) + 2, sq + 8), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, more)
    painter.restore()
