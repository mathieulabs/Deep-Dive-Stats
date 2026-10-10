# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Faint review-count bars behind the retention lines."""
from aqt.qt import QColor, QEasingCurve, QFont, QFontMetrics, QPen, QPointF, QRectF, Qt, QVariantAnimation

from ...chart_utils import get_theme_colors
from ...chart_utils.formatting import fmt_num_compact

from .series import SERIES_KEYS
from .smooth import bar_path
from ....logic.logger import log_swallowed

_BAR_SHARE = 0.35  # tallest bar, as a share of the plot height


def _review_counts(display_data, visible_series, n):
    """Reviews behind each point: the best supported of the visible lines."""
    counts = [0.0] * n
    for key in SERIES_KEYS:
        if not visible_series.get(key, False):
            continue
        for i, item in enumerate((display_data.get(key) or [])[:n]):
            if isinstance(item, (list, tuple)) and len(item) >= 3 and item[2]:
                try:
                    counts[i] = max(counts[i], float(item[2][1] or 0))
                except Exception:
                    log_swallowed()
    return counts


def axis_enabled(widget):
    """The right axis is free unless the cumulative line already uses it."""
    return (
        bool(getattr(widget, "review_bars", True))
        and bool(getattr(widget, "review_axis", False))
        and not getattr(widget, "cumulative_visible", False)
    )


def current_fade(widget):
    """Fade level; None means no animation yet, so it follows the option."""
    fade = getattr(widget, "_bars_fade", None)
    if fade is None:
        return 1.0 if getattr(widget, "review_bars", True) else 0.0
    return float(fade)


def fade_to(widget, enabled):
    """Fade the bars in or out when the option is switched."""
    start = current_fade(widget)
    anim = getattr(widget, "_bars_fade_anim", None)
    if anim is None:
        anim = QVariantAnimation(widget)
        anim.setDuration(250)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        def _step(value):
            widget._bars_fade = float(value)
            widget.update()

        anim.valueChanged.connect(_step)
        widget._bars_fade_anim = anim
    anim.stop()
    anim.setStartValue(start)
    anim.setEndValue(1.0 if enabled else 0.0)
    widget._bars_fade = start
    anim.start()


def _ink(widget, alpha, is_dark):
    """The theme's text color at a given opacity (white or black as a fallback)."""
    try:
        color = QColor(get_theme_colors(widget).get("text"))
        if not color.isValid():
            raise ValueError
    except Exception:
        color = QColor(255, 255, 255) if is_dark else QColor(0, 0, 0)
    color.setAlpha(max(0, min(255, int(alpha))))
    return color


def _label(value):
    value = float(value)
    if value >= 10000:
        return f"{fmt_num_compact(value / 1000.0)}k"
    return str(int(round(value)))


def axis_margin(widget, font_metrics, display_data, n):
    """Room on the right for the review count labels."""
    if not axis_enabled(widget) or n <= 0:
        return 0
    top = max(_review_counts(display_data, widget.visible_series, n))
    if top <= 0:
        return 0
    return QFontMetrics(_axis_font(widget)).horizontalAdvance(_label(top)) + 16


def _axis_font(widget):
    """One font for the margin and the labels, so they always agree."""
    font = QFont(widget.font())
    font.setPointSize(9)
    return font


def _axis_labels(painter, widget, top, margin_top, plot_w, plot_h, margin_left, is_dark, fade=1.0):
    bar_max = plot_h * _BAR_SHARE
    bottom = margin_top + plot_h
    painter.setFont(_axis_font(widget))
    fm = painter.fontMetrics()
    color = _ink(widget, 150 * fade, is_dark)
    painter.setPen(color)
    x = margin_left + plot_w + 6
    for value in (top / 2.0, top):
        y = bottom - value / top * bar_max
        painter.drawText(QPointF(x, y + fm.ascent() / 2.0 - 1), _label(value))


def _counts_and_top(widget, display_data, count):
    """Review counts resampled to `count` points, and their maximum."""
    n_src = max((len(display_data.get(k) or []) for k in SERIES_KEYS), default=0)
    if n_src <= 0:
        return [0.0] * count, 0.0
    raw = _review_counts(display_data, widget.visible_series, n_src)
    sampled = widget._sample_series_values(raw, count)
    sampled = [float(v or 0.0) for v in sampled]
    return sampled, (max(sampled) if sampled else 0.0)


def draw_review_bars(widget, painter, display_data, n, margin_left, margin_top, plot_w, plot_h, x_step, is_dark):
    fade = max(0.0, min(1.0, current_fade(widget)))
    if fade <= 0.001 or n <= 0:
        return

    if getattr(widget, "_data_transition_active", False):
        count = int(widget._data_transition_sample_count)
        if count < 2:
            return
        p = max(0.0, min(1.0, float(widget._progress)))
        old, old_top = _counts_and_top(widget, widget._data_transition_old_display_data or {}, count)
        new, new_top = _counts_and_top(widget, widget._data_transition_new_display_data or {}, count)
        fractions = [
            (o / old_top if old_top > 0 else 0.0) * (1.0 - p) + (c / new_top if new_top > 0 else 0.0) * p
            for o, c in zip(old, new)
        ]
        top = old_top * (1.0 - p) + new_top * p
        x_step = plot_w / (count - 1)
        n = count
        min_reviews_top = new_top
    else:
        counts = _review_counts(display_data, widget.visible_series, n)
        top = max(counts)
        fractions = [c / top if top > 0 else 0.0 for c in counts]
        min_reviews_top = top
    if top <= 0:
        return

    bar_max = plot_h * _BAR_SHARE
    bottom = margin_top + plot_h
    half = max(0.75, x_step * 0.35) if n > 1 else 6.0
    left_edge = margin_left
    right_edge = margin_left + plot_w

    color = _ink(widget, 55 * fade, is_dark)
    painter.save()
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(color)
    rounded = bool(getattr(widget, "rounded", False))
    for i, f in enumerate(fractions):
        if f <= 0:
            continue
        x = margin_left + i * x_step
        x0 = max(left_edge, x - half)
        x1 = min(right_edge, x + half)
        if x1 <= x0:
            continue
        h = max(1.0, f * bar_max)
        if rounded and x1 - x0 >= 3.0:
            painter.drawPath(bar_path(x0, x1, bottom - h, bottom))
        else:
            painter.drawRect(QRectF(x0, bottom - h, x1 - x0, h))

    min_reviews = int(getattr(widget, "min_reviews", 0) or 0)
    if 0 < min_reviews < min_reviews_top:
        y = bottom - min_reviews / min_reviews_top * bar_max
        pen = QPen(_ink(widget, 150 * fade, is_dark), 1, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawLine(QPointF(left_edge, y), QPointF(right_edge, y))
    painter.restore()
    if axis_enabled(widget):
        painter.save()
        _axis_labels(painter, widget, top, margin_top, plot_w, plot_h, margin_left, is_dark, fade)
        painter.restore()
