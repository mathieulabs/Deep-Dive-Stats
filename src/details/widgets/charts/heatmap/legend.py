# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Color legend under the heatmap: what each color step means, with numbers."""
import math

from aqt.qt import QColor, QEasingCurve, QFont, QFontMetrics, QPen, QRectF, QVariantAnimation, Qt

from ...chart_utils import get_theme_colors
from .metrics import components
from .....i18n import num, tr

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
        return num(f"{int(round(value))}%")
    key = comps[0][0]
    if key == "time":
        secs = value / 1000.0
        if secs >= 3600:
            return tr("{value}h", value=num(f"{secs / 3600.0:.1f}"))
        if secs >= 60:
            return tr("{value}m", value=int(round(secs / 60.0)))
        return tr("{value}s", value=int(round(secs)))
    if key == "avg_time":
        secs = value / 1000.0
        return tr("{value}s", value=num(f"{secs:.1f}") if secs < 10 else int(round(secs)))
    if key == "retention":
        return num(f"{int(round(value))}%")
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
    # With few reviews several swatches round to the same number ("1, 1, 2"): only the
    # last of them, the color those cells really get, keeps the number.
    for i in range(1, len(items) - 1):
        if items[i][1] == items[i + 1][1].rstrip("+"):
            items[i] = (items[i][0], "")
    widget._legend_cache = (key, items)
    _animate_legend_change(widget, previous, items)
    return items


def _animate_legend_change(widget, previous, items):
    """Blend the swatch colors when the legend values change (another deck, period or
    metric), in step with the cells; the numbers change at once."""
    if not previous or len(previous) != len(items) or not widget.isVisible():
        return
    if all(a[1] == b[1] for a, b in zip(previous, items)):
        # Only the colors changed (opacity, theme): follow the cells at once.
        return
    try:
        from ....animations.chart_policy import chart_animations_allowed
        from .settings import USER_ACTION_MAX_CHARTS

        if not chart_animations_allowed(widget, max_visible_charts=USER_ACTION_MAX_CHARTS):
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


def legend_anchor(widget, h):
    """(right edge, top) of the legend at rest: under the grid, lined up with it."""
    right = widget.width() - 6.0
    from .settings import layout_height

    top = layout_height(widget) - h  # the final height while it is on its way
    if getattr(widget, "view_mode", "year") == "years":
        try:
            from .years_ops import layout

            lay = layout(widget)
            right = min(right, lay["start_x"] + 53 * lay["step"] - lay["spacing"])
            top = min(top, lay["bottom"] + 10 * getattr(widget, "scale", 1.0))
        except Exception:
            pass
    elif getattr(widget, "grid_mode", False) and getattr(widget, "view_mode", "year") != "continuous":
        # Under the grid, lined up with its right edge, instead of in the corner of a taller card.
        try:
            cell, spacing, start_x, start_y, _label = widget._get_grid_geometry()
            right = min(right, start_x + 53 * (cell + spacing) - spacing)
            top = min(top, start_y + 7 * (cell + spacing) - spacing + 10 * getattr(widget, "scale", 1.0))
        except Exception:
            pass
    elif getattr(widget, "view_mode", "year") == "continuous":
        # Lined up with the right edge of the month boxes (where the controls end), not
        # with the card's corner.
        try:
            from .layout_ops import _CONT_BOX_COLS
            _cell, spacing, step, gap_w, _label, _top, start_x, months = widget._get_continuous_layout()
            box_left = start_x - (_CONT_BOX_COLS - sum(m[3] for m in months)) * step / 2.0
            right = min(right, box_left + _CONT_BOX_COLS * step + (len(months) - 1) * gap_w - spacing)
        except Exception:
            pass
    return right, top


def legend_rest_top(widget):
    """Top of the legend at rest, or None when there is none (start of a transition)."""
    h = legend_height(widget)
    if h <= 0:
        return None
    try:
        return min(legend_anchor(widget, h)[1], widget.height() - h)
    except Exception:
        return None


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
    def total_width(with_numbers):
        # The numbers already say which way the scale goes: "Less" and "More" are only
        # shown when the card is too narrow for them.
        w = 0.0 if with_numbers else fm.horizontalAdvance(tr("Less")) + gap + fm.horizontalAdvance(tr("More")) + gap
        for _c, t in items:
            w += sq + (gap + fm.horizontalAdvance(t) if with_numbers else 0) + between
        return w - between + (0.0 if with_numbers else gap)

    with_numbers = total_width(True) <= widget.width() - 8
    less, more = ("", "") if with_numbers else (tr("Less"), tr("More"))
    total = total_width(with_numbers)
    right, top = legend_anchor(widget, h)
    from_top = getattr(widget, "_legend_top_from", None)
    if from_top is not None and getattr(widget, "_mode_transition_active", False):
        # The legend glides with the cells (a switch that changes the height): jumping to
        # its new place at once, it showed under cells still on their way, or cut off
        # below a card not resized yet.
        t = max(0.0, min(1.0, float(getattr(widget, "_mode_transition_progress", 1.0))))
        top = from_top + (top - from_top) * (t * t * (3.0 - 2.0 * t))
    top = min(top, widget.height() - h)  # never under the card's edge
    x = max(4.0, right - total)
    y = top + (h - sq) / 2.0 - 1

    painter.setPen(text_col)
    if less:
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
            # The new numbers at once: faded out and in, laid out at the new widths, they
            # blinked and the old ones were cut. Only the swatch colors blend.
            painter.drawText(rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text)
            if off:
                mid = y + sq / 2.0
                painter.drawLine(int(x), int(mid), int(x + w), int(mid))
            x += w
        painter.setOpacity(1.0)
        if step >= 0:
            hits.append((QRectF(x0 - 2, y - 3, x - x0 + 4, sq + 6), step))
        x += between
    widget._legend_hits = hits
    if more:
        x += gap - between
        painter.setPen(text_col)
        painter.drawText(QRectF(x, y - 4, fm.horizontalAdvance(more) + 2, sq + 8), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, more)
    painter.restore()
    if getattr(widget, "view_mode", "") == "years":
        # "+ N older years" on the legend's line, on the left (see years_ops.toggle_in_legend).
        try:
            from .years_ops import draw_toggle_in_legend

            draw_toggle_in_legend(widget, painter, top, h)
        except Exception:
            pass
