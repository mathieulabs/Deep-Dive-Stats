# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
import math

from aqt.qt import QEasingCurve, QPointF, QVariantAnimation

PIE_SIZE = 130.0
RING_W = 22.0
GROW = 2.0  # the hovered ring gets this much wider on each side
SLICE_GAP = 20.0  # empty space between slices, in 1/16 degree (1.25 degrees)
DIM = 0.45  # how much the other slices fade while one is hovered
HOVER_MS = 130


def hover_amount(widget, key):
    return float((getattr(widget, "_hover_amt", None) or {}).get(key, 0.0))


def hover_max(widget):
    amts = getattr(widget, "_hover_amt", None) or {}
    return max(amts.values()) if amts else 0.0


def hover_display_key(widget):
    """Slice whose numbers replace the total in the middle of the ring."""
    amts = getattr(widget, "_hover_amt", None) or {}
    best = max(amts.items(), key=lambda kv: kv[1], default=(None, 0.0))
    return best[0] if best[1] > 0.5 else None


def _slice_at(widget, pos):
    xform = getattr(widget, "_pie_xform", None)
    if not xform or float(widget.get_progress()) < 0.999 or widget._global_transition_mode:
        return None
    tx, ty, sc, is_horizontal = xform
    if sc <= 0:
        return None
    if is_horizontal:
        pie_x, pie_y = 0.0, (150 - PIE_SIZE) / 2
    else:
        pie_x, pie_y = (210.0 - PIE_SIZE) / 2, 5.0
    dx = (pos.x() - tx) / sc - (pie_x + PIE_SIZE / 2)
    dy = (pos.y() - ty) / sc - (pie_y + PIE_SIZE / 2)
    r = math.hypot(dx, dy)
    outer = PIE_SIZE / 2 + GROW
    inner = PIE_SIZE / 2 - RING_W - GROW
    if r < inner or r > outer:
        return None
    # Clockwise angle from 12 o'clock, the way the slices are laid out.
    cw = (90.0 - math.degrees(math.atan2(-dy, dx))) % 360.0
    keys = [k for k in widget.order if k in widget._active_keys()]
    total = sum(max(0.0, float(widget.counts.get(k, 0))) for k in keys)
    if total <= 0:
        return None
    acc = 0.0
    for k in keys:
        v = max(0.0, float(widget.counts.get(k, 0)))
        if v <= 0:
            continue
        acc += v / total * 360.0
        if cw < acc:
            return k
    return None


def set_hover_key(widget, key):
    if getattr(widget, "_hover_key", None) == key:
        return
    widget._hover_key = key
    start = dict(getattr(widget, "_hover_amt", None) or {})
    keys = set(start) | ({key} if key else set())
    target = {k: (1.0 if k == key else 0.0) for k in keys}
    anim = getattr(widget, "_hover_anim", None)
    if anim is None:
        anim = QVariantAnimation(widget)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        widget._hover_anim = anim
        anim.valueChanged.connect(lambda p, w=widget: _step(w, float(p)))
    anim.stop()
    widget._hover_from = start
    widget._hover_to = target
    try:
        from ....animations.motion import animations_enabled
        animated = animations_enabled(widget._animation_scope())
    except Exception:
        animated = True
    if not animated:
        _step(widget, 1.0)
        return
    anim.setDuration(HOVER_MS)
    anim.start()


def _step(widget, p):
    src = widget._hover_from
    dst = widget._hover_to
    widget._hover_amt = {
        k: v for k, v in
        ((k, src.get(k, 0.0) + (dst.get(k, 0.0) - src.get(k, 0.0)) * p) for k in dst)
        if v > 0.001
    }
    widget.update()


def _set_legend_hot(widget, hot):
    if bool(getattr(widget, "_legend_hot", False)) != hot:
        widget._legend_hot = hot
        widget.update()


def mouse_move_impl(widget, event):
    try:
        pos = event.position().toPoint()
    except AttributeError:
        pos = event.pos()
    # The list of card types (shown instead of an inline legend) opens over the donut.
    icon = getattr(widget, "_legend_icon_rect", None)
    panel = getattr(widget, "_legend_panel_rect", None)
    point = QPointF(pos)
    hot = icon is not None and (icon.contains(point) or (panel is not None and panel.contains(point)))
    _set_legend_hot(widget, bool(hot))
    set_hover_key(widget, None if hot else _slice_at(widget, pos))


def leave_impl(widget):
    _set_legend_hot(widget, False)
    set_hover_key(widget, None)
