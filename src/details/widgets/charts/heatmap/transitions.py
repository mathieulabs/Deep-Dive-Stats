# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QColor, QBrush, QLinearGradient, QPainter, QPixmap, Qt

from ....animations.chart_policy import chart_animations_allowed


def clear_data_transition_state_impl(widget):
    widget._data_transition_active = False
    widget._transition_old_data = {}
    widget._transition_new_data = {}
    widget._transition_old_cells = {}
    widget._transition_new_cells = {}
    widget._transition_cell_pairs = []
    widget._transition_draw_ops = None
    widget._transition_progress = 1.0
    widget._transition_old_pixmap = None
    widget._transition_new_pixmap = None


def clear_nav_transition_state_impl(widget):
    widget._nav_transition_active = False
    widget._nav_transition_progress = 1.0
    widget._nav_transition_old_pixmap = None
    widget._nav_transition_new_pixmap = None


def clear_mode_transition_state_impl(widget):
    widget._mode_transition_active = False
    widget._mode_transition_old_cells = {}
    widget._mode_transition_new_cells = {}
    widget._mode_transition_cell_pairs = []
    widget._mode_transition_draw_ops = None
    widget._mode_transition_progress = 1.0
    widget._mode_transition_old_labels_pixmap = None
    widget._mode_transition_new_labels_pixmap = None
    widget._mode_transition_old_scaffold_pixmap = None
    widget._mode_transition_new_scaffold_pixmap = None


def interpolate_data_map_impl(widget, t):
    if not widget._data_transition_active:
        return widget.data
    keys = set(widget._transition_old_data.keys()) | set(widget._transition_new_data.keys())
    out = {}
    for k in keys:
        old_reviews, old_future = widget._entry_counts(widget._transition_old_data, k)
        new_reviews, new_future = widget._entry_counts(widget._transition_new_data, k)
        reviews = max(0.0, old_reviews + ((new_reviews - old_reviews) * t))
        future = max(0.0, old_future + ((new_future - old_future) * t))
        if reviews > 0.0001 or future > 0.0001:
            out[k] = {"_v": reviews, "future": future}
    return out


def on_data_transition_finished_impl(widget):
    new_pix = widget._transition_new_pixmap
    widget._clear_data_transition_state()
    if new_pix is not None:
        widget._pixmap_cache = new_pix
    else:
        widget._pixmap_cache = None
    widget.update()


def on_mode_transition_finished_impl(widget):
    widget._clear_mode_transition_state()
    widget.update()


def on_nav_transition_finished_impl(widget):
    new_pix = widget._nav_transition_new_pixmap
    if new_pix is not None:
        widget._pixmap_cache = new_pix
    widget._clear_nav_transition_state()
    widget.update()


def begin_navigation_transition_impl(widget, delta):
    """Capture current frame before arrow-driven update."""
    if widget._mode_transition_active:
        return
    widget._nav_transition_anim.stop()
    widget._nav_transition_active = False
    widget._nav_transition_progress = 0.0
    widget._nav_transition_direction = 1 if delta > 0 else -1
    widget._nav_transition_old_pixmap = widget._render_to_pixmap(widget.data)
    widget._nav_transition_new_pixmap = None


def finalize_navigation_transition_impl(widget):
    """Capture destination frame and start slide animation."""
    if not chart_animations_allowed(widget):
        widget._clear_nav_transition_state()
        widget._pixmap_cache = None
        widget.update()
        return
    if widget._mode_transition_active:
        return
    if widget._nav_transition_old_pixmap is None:
        return
    widget._nav_transition_new_pixmap = widget._render_to_pixmap(widget.data)
    if widget._nav_transition_new_pixmap is None:
        widget._clear_nav_transition_state()
        return
    widget._nav_transition_active = True
    widget._nav_transition_progress = 0.0
    widget._nav_transition_anim.start()


def draw_nav_transition_frame_impl(widget, painter, old_x, new_x, fade_px=14):
    """Draw combined nav transition with one shared soft edge mask."""
    dpr = widget.devicePixelRatio()
    w = int(widget.width() * dpr)
    h = int(widget.height() * dpr)
    if w <= 0 or h <= 0:
        return

    layer = QPixmap(w, h)
    layer.setDevicePixelRatio(dpr)
    layer.fill(Qt.GlobalColor.transparent)

    lp = QPainter(layer)
    lp.setRenderHint(QPainter.RenderHint.Antialiasing, False)
    if widget._nav_transition_old_pixmap:
        lp.drawPixmap(old_x, 0, widget._nav_transition_old_pixmap)
    if widget._nav_transition_new_pixmap:
        lp.drawPixmap(new_x, 0, widget._nav_transition_new_pixmap)

    lp.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
    lp.fillRect(0, 0, widget.width(), widget.height(), QColor(255, 255, 255, 255))
    if fade_px > 0:
        left = QLinearGradient(0, 0, fade_px, 0)
        left.setColorAt(0.0, QColor(255, 255, 255, 0))
        left.setColorAt(1.0, QColor(255, 255, 255, 255))
        lp.fillRect(0, 0, fade_px, widget.height(), QBrush(left))

        right_start = max(0, widget.width() - fade_px)
        right = QLinearGradient(right_start, 0, widget.width(), 0)
        right.setColorAt(0.0, QColor(255, 255, 255, 255))
        right.setColorAt(1.0, QColor(255, 255, 255, 0))
        lp.fillRect(right_start, 0, fade_px, widget.height(), QBrush(right))
    lp.end()

    painter.drawPixmap(0, 0, layer)
