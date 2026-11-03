# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Margins around the pinned widgets overlay (left/right share one value)."""
from aqt.qt import QSizePolicy

from ..imports import Config
from .....logic.logger import log_swallowed

DEFAULT_SIDE = 20
DEFAULT_TOP = 0
DEFAULT_BOTTOM = 20
DEFAULT_SECTION_SPACING = 10
MAX_MARGIN = 200
# Room opened above the first box / below the last one while a dragged widget is near
# there (a new box there): its marker then has space and covers nothing.
DRAG_ROOM = 26


def _clamped(conf, key, default):
    try:
        return max(0, min(MAX_MARGIN, int(conf.get(key, default))))
    except Exception:
        return default


def apply_overlay_margins(manager):
    """Set the layout margins from the settings. Returns True if they changed.

    The webview scrollbar takes room on the right of the overlay (the overlay is as wide
    as the webview), so it is added to the right margin: both sides then look equal.
    """
    layout = getattr(manager, "_main_layout", None)
    if layout is None:
        return False
    conf = manager._config_manager.config
    side = _clamped(conf, Config.PINNED_MARGIN_SIDE, DEFAULT_SIDE)
    top = _clamped(conf, Config.PINNED_MARGIN_TOP, DEFAULT_TOP)
    bottom = _clamped(conf, Config.PINNED_MARGIN_BOTTOM, DEFAULT_BOTTOM)
    scrollbar = int(getattr(manager, "_scrollbar_px", 0) or 0)
    room_top = DRAG_ROOM if getattr(manager, "_drag_room_top", False) else 0
    room_bottom = DRAG_ROOM if getattr(manager, "_drag_room_bottom", False) else 0
    room_bottom += int(getattr(manager, "_drag_spot_room", 0) or 0)
    new = (side, top + room_top, side + scrollbar, bottom + room_bottom)
    m = layout.contentsMargins()
    gaps_changed = apply_section_gaps(manager)
    gaps_changed = apply_line_gaps(manager) or gaps_changed
    if (m.left(), m.top(), m.right(), m.bottom()) == new and layout.spacing() == 0 and not gaps_changed:
        return False
    layout.setContentsMargins(*new)
    # The space between two boxes is a spacer of its own (see apply_section_gaps).
    layout.setSpacing(0)
    manager._last_resize_signature = None
    return True


# -- the spaces between boxes and between lines --------------------------------------
# Each one can be changed by dragging it (gap_handle.py). Changed ones are kept in
# Config.PINNED_GAPS by key: "box:<box above>" for the space under a box, and
# "line:<box>:<line index>" for the space under a line of a box. The others use the
# default: the "Space Between Lines" setting, the same for every space (between two lines
# of a box or between two boxes: on screen, both are just two lines).

MAX_GAP = 200


def gap_px(conf, key, default):
    try:
        value = (conf.get(Config.PINNED_GAPS) or {}).get(key)
        if value is None:
            return int(default)
        return max(0, min(MAX_GAP, int(value)))
    except Exception:
        return int(default)


def section_gap_default(conf):
    return _clamped(conf, Config.PINNED_SECTION_SPACING, DEFAULT_SECTION_SPACING)


def apply_section_gaps(manager):
    """Size the spacers between the boxes from the settings. True if one changed."""
    spacers = getattr(manager, "_section_spacers", None) or []
    if not spacers:
        return False
    conf = manager._config_manager.config
    default = section_gap_default(conf)
    changed = False
    for spacer, key in spacers:
        try:
            px = gap_px(conf, "box:" + key, default)
            if spacer.sizeHint().height() != px:
                spacer.changeSize(0, px, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
                changed = True
        except RuntimeError:
            continue
    if changed:
        try:
            manager._main_layout.invalidate()
        except Exception:
            log_swallowed()
    return changed


def apply_line_gaps(manager):
    """The space above each line of every box (none above its first one shown). True if
    one changed."""
    conf = manager._config_manager.config
    default = section_gap_default(conf)
    changed = False
    for attr, kind in (("_chart_boxes", "charts"), ("_text_boxes", "texts")):
        boxes = getattr(manager, attr, None)
        if not isinstance(boxes, dict):
            continue
        for box_id, entry in boxes.items():
            vbox = entry.get("vbox")
            if vbox is not None and vbox.spacing() != 0:
                vbox.setSpacing(0)
                changed = True
            prev = None
            for idx, (row_w, ml) in enumerate(entry.get("rows", []) or []):
                try:
                    shown = ml.count() > 0 and not row_w.isHidden()
                    top = 0
                    if shown and prev is not None:
                        top = gap_px(conf, f"line:{kind}:{int(box_id)}:{prev}", default)
                    m = ml.contentsMargins()
                    if m.top() != top:
                        ml.setContentsMargins(m.left(), top, m.right(), m.bottom())
                        ml.invalidate()
                        changed = True
                    if shown:
                        prev = idx
                except RuntimeError:
                    continue
    stats = getattr(manager, "_stats_containers", None)
    if isinstance(stats, dict):
        for box_id, container in stats.items():
            setter = getattr(container, "set_line_gaps", None)
            if setter is None:
                continue
            try:
                rows = getattr(container, "_rows", []) or []
                gaps = {i: gap_px(conf, f"line:stats:{int(box_id)}:{i}", default) for i in range(len(rows))}
                if setter(gaps):
                    changed = True
            except RuntimeError:
                continue
    return changed


def row_content_rect(row_w, ml):
    """A line's rect without the space above it."""
    r = row_w.geometry()
    try:
        return r.adjusted(0, ml.contentsMargins().top(), 0, 0)
    except Exception:
        return r


def measure_scrollbar(manager, web, zoom):
    """Read the width of the webview scrollbar (0 if hidden) and update the right margin."""
    if web is None:
        return

    def _done(value):
        try:
            px = max(0, min(40, int(round(float(value or 0) * zoom))))
        except Exception:
            px = 0
        if px == int(getattr(manager, "_scrollbar_px", 0) or 0):
            return
        manager._scrollbar_px = px
        try:
            if apply_overlay_margins(manager):
                manager._schedule_overlay_sync(delay_ms=0)
        except Exception:
            log_swallowed()

    try:
        web.evalWithCallback("(window.innerWidth - document.documentElement.clientWidth)", _done)
    except Exception:
        log_swallowed()


def refresh_overlay_margins():
    """Apply changed margin settings to the live overlay, if any."""
    try:
        from ..manager import MainMenuWidgetManager

        if not MainMenuWidgetManager.instance_exists():
            return
        manager = MainMenuWidgetManager.instance()
        if getattr(manager, "_overlay", None) is None:
            return
        if apply_overlay_margins(manager):
            manager._schedule_overlay_sync(delay_ms=0)
    except Exception:
        log_swallowed()


def set_spot_room(px):
    """Room under the last box for a drag's landing outline: a widget taller than the last
    line's ones, dropped there, had its outline cut at the bottom of the pinned area."""
    try:
        from ..manager import MainMenuWidgetManager

        if not MainMenuWidgetManager.instance_exists():
            return
        manager = MainMenuWidgetManager.instance()
        px = max(0, int(px))
        if getattr(manager, "_overlay", None) is None or int(getattr(manager, "_drag_spot_room", 0) or 0) == px:
            return
        manager._drag_spot_room = px
        if apply_overlay_margins(manager):
            manager.sync_overlay()
            try:
                manager._overlay.update_mask()
            except Exception:
                log_swallowed()
    except Exception:
        log_swallowed()


def spot_room():
    try:
        from ..manager import MainMenuWidgetManager

        if MainMenuWidgetManager.instance_exists():
            return int(getattr(MainMenuWidgetManager.instance(), "_drag_spot_room", 0) or 0)
    except Exception:
        log_swallowed()
    return 0


def set_drag_room(top, bottom=None):
    """Open or close the room above the first box (top) and below the last one."""
    if bottom is None:
        bottom = top
    try:
        from ..manager import MainMenuWidgetManager

        if not MainMenuWidgetManager.instance_exists():
            return
        manager = MainMenuWidgetManager.instance()
        if getattr(manager, "_overlay", None) is None:
            return
        if (bool(getattr(manager, "_drag_room_top", False)), bool(getattr(manager, "_drag_room_bottom", False))) == (bool(top), bool(bottom)):
            return
        manager._drag_room_top, manager._drag_room_bottom = bool(top), bool(bottom)
        if apply_overlay_margins(manager):
            manager.sync_overlay()
            try:
                manager._overlay.update_mask()
            except Exception:
                log_swallowed()
    except Exception:
        log_swallowed()
