# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors

from ..imports import mw, QTimer
from ..constants import (
    CHART_MIN_COLUMN_WIDTH,
    CHART_SPACING,
    IMMEDIATE_TIMER_MS,
    OVERLAY_GEOM_EPSILON,
    OVERLAY_JS_RETRY_ATTEMPTS,
    OVERLAY_JS_RETRY_DELAY_MS,
    OVERLAY_ZOOM_EPSILON,
)
from .....logic.logger import log_swallowed
from .overlay_margins import measure_scrollbar


def schedule_overlay_sync(manager, delay_ms=0):
    try:
        t = getattr(manager, "_geom_sync_timer", None)
        if t is not None:
            try:
                if t.parent() is not manager._overlay:
                    t = None
            except RuntimeError:
                t = None
        if t is None:
            t = QTimer(manager._overlay)
            t.setSingleShot(True)
            t.timeout.connect(manager._run_scheduled_overlay_sync)
            manager._geom_sync_timer = t
        t.start(max(0, int(delay_ms)))
    except Exception:
        try:
            manager.sync_overlay()
            manager._update_placeholder_height(manager._overlay.height())
        except Exception:
            log_swallowed()


def run_scheduled_overlay_sync(manager):
    try:
        manager.sync_overlay()
        try:
            manager._update_placeholder_height(manager._overlay.height())
        except Exception:
            log_swallowed()
    except Exception:
        log_swallowed()


def update_overlay_geom(manager, left, top, width, height):
    if not manager._overlay or not manager._overlay.isVisible():
        return

    zoom = manager._get_zoom_factor()

    prev_css = getattr(manager, "_last_placeholder_css_rect", None)
    try:
        manager._last_placeholder_css_rect = (float(left), float(top), float(width), float(height))
    except Exception:
        manager._last_placeholder_css_rect = prev_css

    size_changed = False
    try:
        if prev_css is None:
            size_changed = True
        else:
            _pl, _pt, _pw, _ph = prev_css
            size_changed = (
                (abs(float(width) - float(_pw)) > OVERLAY_GEOM_EPSILON)
                or (abs(float(height) - float(_ph)) > OVERLAY_GEOM_EPSILON)
                or (abs(float(left) - float(_pl)) > OVERLAY_GEOM_EPSILON)
            )
    except Exception:
        size_changed = True
    current_geom = (int(left), int(top), int(width), int(height), round(zoom, 3))
    if manager._last_geom == current_geom:
        return

    manager._last_geom = current_geom

    web = mw.deckBrowser.web if manager._is_deck_browser else mw.overview.web
    curr_w = web.width() if web else mw.width()
    measure_scrollbar(manager, web, zoom)

    manager._overlay.move(0, int(top * zoom))
    if manager._overlay.width() != curr_w:
        manager._overlay.setFixedWidth(curr_w)

    needs_init = bool(manager._overlay.property("needs_init_geom"))
    if needs_init:
        try:
            manager._overlay.setProperty("needs_init_geom", False)
        except Exception:
            log_swallowed()
        manager._schedule_overlay_sync(delay_ms=0)
    elif size_changed:
        manager._schedule_overlay_sync(delay_ms=0)


def current_resize_signature(manager, width):
    visible = []
    for i in range(manager._main_layout.count()):
        item = manager._main_layout.itemAt(i)
        w = item.widget() if item else None
        if not w or not w.isVisible():
            continue
        g = w.geometry()
        visible.append((id(w), g.width(), g.height(), w.sizePolicy().horizontalPolicy(), w.sizePolicy().verticalPolicy()))
    return (int(width), tuple(visible))


def resize_overlay(manager, force_refresh_blur=False):
    if not hasattr(manager, "_overlay") or not manager._overlay:
        return
    if not hasattr(manager, "_main_layout") or not manager._main_layout:
        return

    web = mw.deckBrowser.web if manager._is_deck_browser else mw.overview.web
    w = web.width() if web else mw.width()
    if w <= 0:
        w = mw.width()

    for _, _ml_row in getattr(manager, "_chart_masonry_rows", []):
        try:
            _ml_row.min_column_width = CHART_MIN_COLUMN_WIDTH
            _ml_row.setSpacing(CHART_SPACING)
        except Exception:
            log_swallowed()

    sig = manager._current_resize_signature(w)

    if manager._overlay.width() != w:
        manager._overlay.setFixedWidth(w)

    manager._main_layout.invalidate()
    manager._main_layout.activate()

    hint = manager._main_layout.sizeHint()
    h = hint.height()

    try:
        m = manager._main_layout.contentsMargins()
        spacing = int(manager._main_layout.spacing() or 0)
        vis_widgets = []
        for i in range(manager._main_layout.count()):
            item = manager._main_layout.itemAt(i)
            ww = item.widget() if item else None
            if ww is None or not ww.isVisible():
                continue
            try:
                hh = max(int(ww.minimumSizeHint().height()), int(ww.sizeHint().height()))
            except Exception:
                hh = int(ww.sizeHint().height())
            vis_widgets.append(max(0, hh))
        if vis_widgets:
            content_h = int(m.top() + m.bottom() + sum(vis_widgets) + spacing * (len(vis_widgets) - 1))
            h = max(int(h), int(content_h))
    except Exception:
        log_swallowed()

    if not force_refresh_blur and sig == manager._last_resize_signature and abs(manager._overlay.height() - h) < 1:
        return

    manager._overlay.resize(w, h)
    manager._update_placeholder_height(h)
    manager._last_resize_signature = sig


def update_placeholder_height(manager, h):
    if hasattr(manager, "_last_h") and abs(manager._last_h - h) < 1:
        return
    manager._last_h = h

    webview = mw.deckBrowser.web if manager._is_deck_browser else mw.overview.web
    if webview:
        zoom = manager._get_zoom_factor()
        h_css = h / zoom if zoom > 0 else h
        script = f"""
            (function() {{
                var h = {h_css:.2f};
                var attempts = 0;
                function trySet() {{
                    if (window.setPinnedHeight) {{
                        window.setPinnedHeight(h);
                    }} else if (attempts < {OVERLAY_JS_RETRY_ATTEMPTS}) {{
                        attempts++;
                        setTimeout(trySet, {OVERLAY_JS_RETRY_DELAY_MS});
                    }}
                }}
                trySet();
            }})();
            """
        webview.eval(script)


def sync_overlay(manager):
    if not manager._overlay:
        return
    manager._sync_timer.start(IMMEDIATE_TIMER_MS)


def do_sync_overlay(manager):
    zoom = manager._get_zoom_factor()
    last_zoom = getattr(manager, "_last_zoom", None)
    if last_zoom is None:
        manager._apply_zoom_scale_to_widgets(zoom)
    elif abs(zoom - last_zoom) > OVERLAY_ZOOM_EPSILON:
        manager._last_geom = None
        manager._last_h = -1
        manager._last_resize_signature = None
        manager._apply_zoom_scale_to_widgets(zoom)
        try:
            web = mw.deckBrowser.web if manager._is_deck_browser else mw.overview.web
            if web:
                web.eval("if (window.forcePinnedUpdate) window.forcePinnedUpdate();")
        except Exception:
            log_swallowed()
    manager._last_zoom = zoom

    if not manager._overlay:
        return
    manager._resize_overlay()
    if not manager._overlay:
        return
    manager._overlay.update_mask()






