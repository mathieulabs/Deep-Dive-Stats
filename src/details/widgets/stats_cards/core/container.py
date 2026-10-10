# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import (
    QFrame,
    QSizePolicy,
    QPropertyAnimation,
    QEasingCurve,
    QTimer,
    pyqtProperty,
)

from ....animations.motion import animations_enabled
from .layout import WrappingHBoxLayout
from ..ui.sizing import PINNED_BASE_HEIGHT, normalize_scale_percent, scale_ratio_from_percent
from ..logic.container_logic import (
    resolve_layout_width,
    collect_visible_cards,
    capture_old_geometries,
    compute_compact_layout_metrics,
    compute_dashboard_layout_metrics,
    apply_layout_height,
    apply_card_typography,
    activate_layout_with_optional_animation,
)
from ..logic.container_dnd import handle_drag_enter, handle_drag_move, handle_drop
from ..logic.constants import (
    CONTAINER_VIS_ANIM_DURATION_MS,
    WIDGET_MOVE_ANIM_DURATION_MS,
    SHOW_EVENT_SYNC_DELAYS_MS,
    DRAG_MOVE_THROTTLE_S,
)
from .....qss import set_qss


class StatCardsContainer(QFrame):
    """
    A container that manages multiple StatCardWidgets and ensures
    they all scale their fonts synchronously and uniformly.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        set_qss(self, "background: transparent; border: none;")
        self.layout = WrappingHBoxLayout(self, spacing=6)
        self.cards = []
        self._on_visibility_changed = None
        self._scaling_locked = False
        self._compact_mode = False
        self._reduced_height_mode = False
        self._scale = 1.0

        self.setAcceptDrops(True)
        self._animations = {}

        self.setFixedHeight(PINNED_BASE_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._last_drag_move_time = 0

        self._row_num_fn = None
        self._row_num_change_fn = None

        self._layout_timer = QTimer(self)
        self._layout_timer.setSingleShot(True)
        self._layout_timer.timeout.connect(lambda: self.update_layout(self.width()))

    def set_scale(self, scale_pct: int):
        scale_pct = normalize_scale_percent(scale_pct)
        self._scale = scale_ratio_from_percent(scale_pct)
        self.update_layout(self.width())

    def clear_cards(self):
        while self.layout.count():
            self.layout.takeAt(0)
        self.cards = []

    def set_compact_mode(self, enabled: bool, align="center"):
        self._compact_mode = enabled
        self._align = align
        self.update_compact_stretches()

    def set_reduced_height_mode(self, enabled: bool):
        self._reduced_height_mode = enabled
        self.update_layout(self.width())

    def update_compact_stretches(self):
        if not self._compact_mode:
            return

        while self.layout.count():
            item = self.layout.itemAt(0)
            if item.widget():
                break
            self.layout.takeAt(0)

        while self.layout.count():
            count = self.layout.count()
            item = self.layout.itemAt(count - 1)
            if item.widget():
                break
            self.layout.takeAt(count - 1)

        if self._align in ("center", "right"):
            self.layout.insertStretch(0)
        if self._align in ("center", "left"):
            self.layout.addStretch()

        self.update_layout(self.width())

    def set_scaling_lock(self, locked: bool):
        self._scaling_locked = locked
        if not locked:
            self.update_layout(self.width())

    def set_visibility_callback(self, callback):
        self._on_visibility_changed = callback

    def set_row_num_callbacks(self, num_fn, change_fn):
        self._row_num_fn = num_fn
        self._row_num_change_fn = change_fn

    def get_container_height(self):
        return self.height()

    def set_container_height(self, h):
        self.setFixedHeight(h)

    containerHeight = pyqtProperty(int, get_container_height, set_container_height)

    def animate_visibility(self, visible: bool):
        scope = "pinned" if bool(getattr(self, "_compact_mode", False)) else "details"
        if not animations_enabled(scope):
            if visible:
                row_h = int(PINNED_BASE_HEIGHT * self._scale)
                self.layout.setRowHeight(row_h)
                self.setVisible(True)
                self.update_layout(self.width())
            else:
                self.setVisible(False)
                self.setFixedHeight(0)
            return
        if visible:
            row_h = int(PINNED_BASE_HEIGHT * self._scale)
            self.layout.setRowHeight(row_h)
            target_h = self.layout.heightForWidth(self.width() or 600)
        else:
            target_h = 0
        start_h = self.height()

        if not hasattr(self, "anim"):
            self.anim = QPropertyAnimation(self, b"containerHeight")
            self.anim.setDuration(CONTAINER_VIS_ANIM_DURATION_MS)
            self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            self.anim.finished.connect(self._on_anim_finished)

        for card in self.cards:
            card.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)

        self.anim.stop()
        self.anim.setStartValue(start_h)
        self.anim.setEndValue(target_h)

        if visible:
            self.setVisible(True)

        self.set_scaling_lock(True)
        self.anim.start()

    def _on_anim_finished(self):
        for card in self.cards:
            card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.set_scaling_lock(False)
        if self.height() == 0:
            self.setVisible(False)
        else:
            self.setVisible(True)
            self.update_layout(self.width())

    def set_cards(self, new_cards):
        if self.cards == new_cards:
            return

        to_remove = [c for c in self.cards if c not in new_cards]
        for c in to_remove:
            self.layout.removeWidget(c)
            self.cards.remove(c)

        for i, card in enumerate(new_cards):
            current_idx = self.layout.indexOf(card)
            if current_idx == i:
                continue
            if current_idx != -1:
                self.layout.removeWidget(card)
            self.layout.insertWidget(i, card, 1)
            card.show()

        self.cards = list(new_cards)
        self.update_compact_stretches()
        self.trigger_layout_update()

    def add_card(self, card):
        if card in self.cards:
            return
        self.cards.append(card)
        self.layout.addWidget(card, 1)

    def addWidget(self, widget):
        from .card import StatCardWidget

        if isinstance(widget, StatCardWidget):
            self.add_card(widget)
        else:
            self.layout.addWidget(widget, 0)

    def resizeEvent(self, event):
        if event:
            super().resizeEvent(event)
        self.trigger_layout_update()

    def trigger_layout_update(self):
        if not self._layout_timer.isActive():
            self._layout_timer.start(0)

    def update_layout(self, w, animate=False):
        if self._scaling_locked:
            return

        w = resolve_layout_width(self, w)
        if w <= 0:
            return

        visible_cards = collect_visible_cards(self)
        if not visible_cards:
            return

        old_geoms = capture_old_geometries(visible_cards, animate)

        from .card import StatCardWidget

        metrics = (
            compute_compact_layout_metrics(self, StatCardWidget)
            if self._compact_mode
            else compute_dashboard_layout_metrics(self, visible_cards, w, StatCardWidget)
        )

        old_h = self.height()
        apply_layout_height(self, metrics["targ_h"], w)
        if self.height() != old_h:
            # A row group above us adds up its rows' heights once; tell it this one changed.
            parent = self.parentWidget()
            refresh = getattr(parent, "_schedule_height_refresh", None)
            if refresh is not None:
                refresh(0)
        apply_card_typography(visible_cards, metrics, StatCardWidget)
        activate_layout_with_optional_animation(self, visible_cards, old_geoms, animate, self._animate_widget)

    def _animate_widget(self, widget, start_rect, end_rect):
        scope = "pinned" if bool(getattr(self, "_compact_mode", False)) else "details"
        if not animations_enabled(scope):
            widget.setGeometry(end_rect)
            return

        if widget in self._animations:
            self._animations[widget].stop()

        anim = QPropertyAnimation(widget, b"geometry")
        anim.setDuration(WIDGET_MOVE_ANIM_DURATION_MS)
        anim.setStartValue(start_rect)
        anim.setEndValue(end_rect)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start()
        self._animations[widget] = anim

    def showEvent(self, event):
        super().showEvent(event)
        self.update_layout(self.width())
        for delay_ms in SHOW_EVENT_SYNC_DELAYS_MS:
            QTimer.singleShot(delay_ms, lambda: self.update_layout(self.width()))

    def contextMenuEvent(self, event):
        from .menu import show_stat_cards_container_menu
        from .card import StatCardWidget

        show_stat_cards_container_menu(self, event, StatCardWidget)

    def dragEnterEvent(self, event):
        handle_drag_enter(self, event)

    def dragMoveEvent(self, event):
        handle_drag_move(
            self,
            event,
            throttle_s=DRAG_MOVE_THROTTLE_S,
            on_shifted=lambda: self.update_layout(self.width(), animate=True),
        )

    def dragLeaveEvent(self, event):
        from ...pinned.main_menu.ui.drag_move import hide_marker

        hide_marker(self)
        self._drag_cross = None
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        handle_drop(self, event)
