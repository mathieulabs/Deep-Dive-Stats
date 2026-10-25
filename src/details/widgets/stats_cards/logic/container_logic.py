# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QTimer

from ..ui.sizing import compact_typography, dashboard_typography


def resolve_layout_width(container, w):
    if w > 0:
        return w
    parent = container.parentWidget()
    if parent:
        w = parent.width()
    return w


def collect_visible_cards(container):
    return [
        c for c in container.cards
        if not getattr(c, "isHidden", lambda: False)() or getattr(c, "_is_ghost", False)
    ]


def capture_old_geometries(visible_cards, animate):
    old_geoms = {}
    if not animate:
        return old_geoms
    for card in visible_cards:
        if card.isVisible():
            old_geoms[card] = card.geometry()
    return old_geoms


def compute_compact_layout_metrics(container, stat_card_cls):
    if container.layout.count() == len(container.cards) and container.width() > 100:
        QTimer.singleShot(0, container.update_compact_stretches)

    metrics = compact_typography(container._scale)
    for card in container.cards:
        idx = container.layout.indexOf(card)
        if idx == -1:
            continue
        is_ghost = getattr(card, "_is_ghost", False)
        if isinstance(card, stat_card_cls) and (not getattr(card, "isHidden", lambda: False)() or is_ghost):
            card.setFixedWidth(int(card.get_ideal_width(container._scale)))
        container.layout.setStretch(idx, 0)
    return metrics


def compute_dashboard_layout_metrics(container, visible_cards, width, stat_card_cls):
    cards_only = [c for c in visible_cards if isinstance(c, stat_card_cls)]
    gaps = (len(cards_only) - 1) * container.layout.spacing()
    total_ideal = sum(card.get_ideal_width() for card in cards_only) + gaps
    height_ideal = sum(card.get_height_ideal_width() for card in cards_only) + gaps

    for card in container.cards:
        idx = container.layout.indexOf(card)
        if idx == -1:
            continue
        container.layout.setStretch(idx, 1 if not getattr(card, "isHidden", lambda: False)() else 0)

    return dashboard_typography(
        container._scale,
        width,
        total_ideal,
        getattr(container, "_reduced_height_mode", False),
        height_ideal=height_ideal,
    )


def apply_layout_height(container, target_h, width):
    if container._compact_mode:
        container.layout.setRowHeight(int(target_h))
        container.setFixedHeight(container.layout.heightForWidth(width))
        return
    container.setFixedHeight(int(target_h))


def apply_card_typography(visible_cards, metrics, stat_card_cls):
    for card in visible_cards:
        if isinstance(card, stat_card_cls):
            card.set_font_sizes(
                metrics["val_fs"],
                metrics["title_fs"],
                metrics["sub_fs"],
                metrics["h_margin"],
            )


def activate_layout_with_optional_animation(container, visible_cards, old_geoms, animate, animate_fn):
    container.setUpdatesEnabled(False)
    try:
        container.layout.activate()
        if animate:
            for card in visible_cards:
                if card in old_geoms:
                    old_rect = old_geoms[card]
                    new_rect = card.geometry()
                    if old_rect != new_rect and old_rect.width() > 0:
                        animate_fn(card, old_rect, new_rect)
    finally:
        container.setUpdatesEnabled(True)
