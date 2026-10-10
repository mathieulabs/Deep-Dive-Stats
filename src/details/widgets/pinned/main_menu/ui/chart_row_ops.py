# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors


from aqt.qt import (
    QAbstractAnimation,
    QEasingCurve,
    QGraphicsOpacityEffect,
    QPropertyAnimation,
    QSizePolicy,
    QTimer,
    QVBoxLayout,
    QWidget,
)

from ..imports import animations_enabled
from ..constants import (
    CHART_FADE_IN_MS,
    CHART_FADE_OUT_MS,
    CHART_MIN_COLUMN_WIDTH,
    CHART_REFLOW_DISABLE_DELAY_MS,
    CHART_REFLOW_PASS_DELAY_MS,
    CHART_SPACING,
    IMMEDIATE_TIMER_MS,
)
from .masonry_layout import MasonryLayout
from ......qss import set_qss
from .....logic.logger import log_swallowed


def _normalize_chart_box(box_id):
    try:
        return max(0, int(box_id or 0))
    except Exception:
        return 0


def _box_attr_names(box_kind):
    if str(box_kind or "chart") == "text":
        return (
            "_text_boxes",
            "_texts_container",
            "_texts_vbox",
            "_text_masonry_rows",
            "_text_box_order",
        )
    return (
        "_chart_boxes",
        "_charts_container",
        "_charts_vbox",
        "_chart_masonry_rows",
        "_chart_box_order",
    )


def _iter_chart_boxes(manager, box_kind="chart"):
    boxes_attr, _, _, _, _ = _box_attr_names(box_kind)
    boxes = getattr(manager, boxes_attr, None)
    if not isinstance(boxes, dict):
        return []
    return sorted(boxes.items(), key=lambda kv: kv[0])


def _ensure_chart_box(manager, box_id: int, box_kind: str = "chart"):
    box_id = _normalize_chart_box(box_id)
    box_kind = str(box_kind or "chart")
    boxes_attr, container_attr, vbox_attr, rows_attr, _ = _box_attr_names(box_kind)
    boxes = getattr(manager, boxes_attr, None)
    if not isinstance(boxes, dict):
        boxes = {}
        setattr(manager, boxes_attr, boxes)

    entry = boxes.get(box_id)
    if entry is None:
        parent = getattr(manager, "_overlay", None)
        container = QWidget(parent)
        set_qss(container, "background: transparent;")
        container.setAcceptDrops(True)
        container.installEventFilter(manager)
        container.setProperty("deepdivestats_box_kind", box_kind)
        container.setProperty("deepdivestats_box_id", int(box_id))
        container.setProperty("deepdivestats_chart_box_id", int(box_id))
        container.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        vbox = QVBoxLayout(container)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(CHART_SPACING)

        entry = {
            "container": container,
            "vbox": vbox,
            "rows": [],
            "masonry": None,
        }
        boxes[box_id] = entry

    if box_id == 0:
        setattr(manager, container_attr, entry["container"])
        setattr(manager, vbox_attr, entry["vbox"])
        setattr(manager, rows_attr, entry["rows"])
        if box_kind == "chart":
            manager._masonry_layout = entry["masonry"]
    return entry


def _iter_all_row_layouts(manager):
    for box_kind in ("chart", "text"):
        for _box_id, entry in _iter_chart_boxes(manager, box_kind=box_kind):
            for row_pair in entry.get("rows", []):
                yield row_pair


def get_or_create_chart_masonry_row(manager, row_idx: int, chart_box: int = 0, box_kind: str = "chart"):
    box_id = _normalize_chart_box(chart_box)
    box_kind = str(box_kind or "chart")
    _, _, _, rows_attr, _ = _box_attr_names(box_kind)
    entry = _ensure_chart_box(manager, box_id, box_kind=box_kind)
    rows = entry["rows"]

    while len(rows) <= row_idx:
        row_w = QWidget(entry["container"])
        set_qss(row_w, "background: transparent;")
        row_w.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        row_ml = MasonryLayout(
            row_w,
            margin=0,
            spacing=CHART_SPACING,
            min_column_width=CHART_MIN_COLUMN_WIDTH,
        )
        rows.append((row_w, row_ml))
        if entry["vbox"] is not None:
            entry["vbox"].addWidget(row_w)
        if len(rows) == 1:
            entry["masonry"] = row_ml
            if box_id == 0 and box_kind == "chart":
                manager._masonry_layout = row_ml

    if box_id == 0:
        setattr(manager, rows_attr, rows)
        if box_kind == "chart":
            manager._masonry_layout = entry["masonry"]
    return rows[row_idx][1]


def set_chart_rows_animate_moves(manager, enabled: bool):
    try:
        from aqt.qt import sip
    except Exception:
        sip = None
    for _, row_layout in _iter_all_row_layouts(manager):
        try:
            if sip is not None and sip.isdeleted(row_layout):
                continue
            row_layout.set_animate_moves(bool(enabled))
        except Exception:
            log_swallowed()


def run_chart_reflow_animation_pass(manager):
    try:
        from aqt.qt import sip
    except Exception:
        sip = None
    try:
        for row_widget, row_layout in _iter_all_row_layouts(manager):
            try:
                if sip is not None and sip.isdeleted(row_layout):
                    continue
                row_layout.invalidate()
            except Exception:
                log_swallowed()
            try:
                if sip is not None and sip.isdeleted(row_widget):
                    continue
                row_widget.updateGeometry()
            except Exception:
                log_swallowed()
        if getattr(manager, "_main_layout", None):
            try:
                if sip is None or not sip.isdeleted(manager._main_layout):
                    manager._main_layout.invalidate()
                    manager._main_layout.activate()
            except Exception:
                log_swallowed()
    except Exception:
        log_swallowed()


def schedule_chart_reflow_animation(manager, pruned_count=0):
    if not animations_enabled("pinned"):
        manager._set_chart_rows_animate_moves(False)
        manager._run_chart_reflow_animation_pass()
        return
    manager._chart_reflow_epoch = int(getattr(manager, "_chart_reflow_epoch", 0)) + 1
    epoch = manager._chart_reflow_epoch
    manager._set_chart_rows_animate_moves(True)

    def _pass_if_current():
        if epoch != getattr(manager, "_chart_reflow_epoch", -1):
            return
        manager._run_chart_reflow_animation_pass()

    def _disable_if_current():
        if epoch != getattr(manager, "_chart_reflow_epoch", -1):
            return
        manager._set_chart_rows_animate_moves(False)

    QTimer.singleShot(IMMEDIATE_TIMER_MS, _pass_if_current)
    QTimer.singleShot(CHART_REFLOW_PASS_DELAY_MS, _pass_if_current)
    QTimer.singleShot(CHART_REFLOW_DISABLE_DELAY_MS, _disable_if_current)


def mark_skip_next_show_anim(manager, widget):
    if widget is None:
        return
    try:
        widget.setProperty("deepdivestats_skip_next_show_anim", True)
    except Exception:
        log_swallowed()
    try:
        for child in widget.findChildren(QWidget):
            try:
                child.setProperty("deepdivestats_skip_next_show_anim", True)
            except Exception:
                log_swallowed()
    except Exception:
        log_swallowed()


def fade_in_widget(manager, widget, duration=CHART_FADE_IN_MS):
    if widget is None:
        return
    try:
        from aqt.qt import sip

        if sip.isdeleted(widget):
            return
    except Exception:
        log_swallowed()

    manager._mark_skip_next_show_anim(widget)
    if not animations_enabled("pinned"):
        try:
            if widget.graphicsEffect() is not None:
                widget.setGraphicsEffect(None)
        except Exception:
            log_swallowed()
        if not widget.isVisible():
            widget.show()
        return
    if not widget.isVisible():
        widget.show()

    eff = widget.graphicsEffect()
    if not isinstance(eff, QGraphicsOpacityEffect):
        eff = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(eff)
    start_opacity = 0.0
    prev = manager._fade_anims.get(widget)
    if prev is not None:
        try:
            # A fade that is still running (typically a fade-out that is being
            # reversed) continues from its current opacity instead of flashing to 0.
            if prev.state() == QAbstractAnimation.State.Running:
                start_opacity = max(0.0, min(1.0, float(eff.opacity())))
            prev.stop()
        except Exception:
            log_swallowed()
    eff.setOpacity(start_opacity)

    anim = QPropertyAnimation(eff, b"opacity", widget)
    anim.setDuration(max(70, int(duration)))
    anim.setStartValue(start_opacity)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def _cleanup():
        if manager._fade_anims.get(widget) is anim:
            manager._fade_anims.pop(widget, None)
        try:
            if widget.graphicsEffect() is eff:
                widget.setGraphicsEffect(None)
        except Exception:
            log_swallowed()

    anim.finished.connect(_cleanup)
    widget.destroyed.connect(lambda *_a, _w=widget: manager._fade_anims.pop(_w, None))
    manager._fade_anims[widget] = anim
    anim.start()


def fade_out_widget(manager, widget, duration=CHART_FADE_OUT_MS):
    if widget is None:
        return
    try:
        from aqt.qt import sip

        if sip.isdeleted(widget):
            return
    except Exception:
        log_swallowed()

    manager._mark_skip_next_show_anim(widget)
    if not animations_enabled("pinned"):
        try:
            if widget.graphicsEffect() is not None:
                widget.setGraphicsEffect(None)
        except Exception:
            log_swallowed()
        try:
            widget.hide()
        except Exception:
            log_swallowed()
        return
    eff = widget.graphicsEffect()
    if not isinstance(eff, QGraphicsOpacityEffect):
        eff = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(eff)
    start_opacity = float(eff.opacity())
    if start_opacity <= 0.0:
        start_opacity = 1.0
        eff.setOpacity(1.0)

    prev = manager._fade_anims.get(widget)
    if prev is not None:
        try:
            prev.stop()
        except Exception:
            log_swallowed()

    anim = QPropertyAnimation(eff, b"opacity", widget)
    anim.setDuration(max(70, int(duration)))
    anim.setStartValue(start_opacity)
    anim.setEndValue(0.0)
    anim.setEasingCurve(QEasingCurve.Type.InCubic)

    def _on_done():
        if manager._fade_anims.get(widget) is anim:
            manager._fade_anims.pop(widget, None)
        try:
            widget.hide()
        except Exception:
            log_swallowed()
        try:
            if widget.graphicsEffect() is eff:
                widget.setGraphicsEffect(None)
        except Exception:
            log_swallowed()

    anim.finished.connect(_on_done)
    widget.destroyed.connect(lambda *_a, _w=widget: manager._fade_anims.pop(_w, None))
    manager._fade_anims[widget] = anim
    anim.start()


def remove_widget_from_chart_rows(manager, widget):
    if widget is None:
        return False
    removed = False
    for _row_w, row_layout in _iter_all_row_layouts(manager):
        try:
            for idx in reversed(range(row_layout.count())):
                item = row_layout.itemAt(idx)
                if item and item.widget() is widget:
                    row_layout.takeAt(idx)
                    manager._fade_out_widget(widget)
                    removed = True
        except Exception:
            continue
    return removed


def prune_chart_rows(manager, valid_widget_ids):
    valid_ids = set(valid_widget_ids or [])
    removed = 0
    for _row_w, row_layout in _iter_all_row_layouts(manager):
        try:
            for idx in reversed(range(row_layout.count())):
                item = row_layout.itemAt(idx)
                w = item.widget() if item else None
                wid = getattr(w, "widget_id", None) if w else None
                if wid and wid not in valid_ids:
                    row_layout.takeAt(idx)
                    manager._fade_out_widget(w)
                    removed += 1
        except Exception:
            continue
    return removed




