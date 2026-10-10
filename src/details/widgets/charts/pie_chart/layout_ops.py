# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QSize, QWidget
from ....animations.chart_mixin import ChartAnimationMixin


def get_scale_impl(widget):
    width = widget.width()
    if width <= 0:
        return 1.0
    return min(width / 180.0, 3.0)


def get_vertical_scale_impl(widget, logical_w=210.0):
    base = widget._get_scale()
    width = widget.width()
    if width <= 0 or logical_w <= 0:
        return base
    return min(base, width / logical_w)


def set_separate_suspended_impl(widget, separate):
    widget.separate_suspended = separate
    widget.update_geom()
    widget.update()
    widget.update_geom()
    widget.update()


def resize_event_impl(widget, event):
    QWidget.resizeEvent(widget, event)
    widget.update_geom()
    widget.update()


def show_event_impl(widget, event):
    widget.update_geom()
    # Route through ChartAnimationMixin so initial progress/animation state is valid.
    # Calling QWidget.showEvent directly can leave progress at 0 and hide slices.
    ChartAnimationMixin.showEvent(widget, event)


# Below this scale the legend text would be smaller than about 11 px: switch to the hover list.
LEGEND_MIN_SCALE = 0.9
# Back to the inline legend only above this one, so it does not flicker around the limit.
LEGEND_BACK_SCALE = 1.0


def _inline_legend_scale(widget, w, h):
    """Scale the legend layout (below or beside the donut) would be drawn at in w x h."""
    needed = widget.get_needed_vertical_height(with_legend=True)
    if widget.grid_mode and h < needed - 15:
        return min(h / 160.0, w / 252.0, 3.0)
    return widget._get_vertical_scale(210.0)


def refresh_legend_state_impl(widget):
    """Decide if the legend fits next to the donut (False: it goes to the hover list)."""
    mode = getattr(widget, "legend_mode", "auto")
    if not widget.show_legend or mode == "always":
        compact = False
    elif mode == "hover":
        compact = True
    else:
        w, h = widget.width(), widget.height()
        if w <= 0 or h <= 0:
            return
        scale = _inline_legend_scale(widget, w, h)
        limit = LEGEND_BACK_SCALE if widget._legend_compact else LEGEND_MIN_SCALE
        compact = scale < limit
    widget._legend_compact = compact


def legend_inline_impl(widget):
    """True when the legend is drawn with the donut."""
    if widget.show_legend:
        # An exported image has no hover, so the legend is always written out.
        try:
            from ..common.cache_dpr import exporting

            if exporting():
                return True
        except Exception:
            pass
    return bool(widget.show_legend) and not widget._legend_compact


def set_legend_mode_impl(widget, mode):
    mode = mode if mode in ("auto", "always", "hover") else "auto"
    if mode == widget.legend_mode:
        return
    widget.legend_mode = mode
    widget.update_geom()
    widget.updateGeometry()
    widget.update()


def get_needed_vertical_height_impl(widget, with_legend=None):
    active_keys = ["new", "learn", "relearn", "young", "mature"]
    if widget.separate_suspended:
        active_keys.extend(["suspended", "buried"])
    if with_legend is None:
        with_legend = widget.legend_inline()
    if not with_legend:
        return 150 * widget._get_vertical_scale(150.0)
    legend_rows = len([k for k in widget.order if k in active_keys])
    scale = widget._get_vertical_scale()
    return (187 + (18 * legend_rows)) * scale


def update_geom_impl(widget):
    refresh_legend_state_impl(widget)
    needed_h = widget.get_needed_vertical_height()
    if widget.grid_mode:
        cap = getattr(widget, "_zoom_min_cap", None)
        widget.setMinimumHeight(120 if cap is None else min(120, cap))
    else:
        widget.setMinimumHeight(int(needed_h))

    widget.optimalHeightChanged.emit(int(needed_h))
    widget.updateGeometry()
    if widget._layout_updates_suspended:
        return
    if widget.parentWidget() and widget.parentWidget().layout():
        widget.parentWidget().layout().invalidate()
        widget.parentWidget().updateGeometry()


def size_hint_impl(widget):
    h = widget.get_needed_vertical_height()
    if widget.grid_mode:
        h = min(300, h)
    return QSize(220 if widget.legend_inline() else 160, int(h))
