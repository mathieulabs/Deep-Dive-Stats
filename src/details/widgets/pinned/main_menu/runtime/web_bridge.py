# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt import mw
from aqt.qt import QEvent, QTimer

from ..imports import Config
from ...drag_drop.constants import MIME_CHART_ID
from ..ui.drag_move import chart_drag_over, hide_marker, queue_move
from .....logic.logger import log_swallowed


def on_webview_did_inject_style(manager, webview):
    if manager._is_deck_browser:
        pass

    try:
        url = webview.page().url()
        if url.isEmpty():
            return
        page_uri = url.toDisplayString().lower()
    except Exception:
        return

    if "congrats" in page_uri:
        manager._is_deck_browser = False
        manager._last_state = None

        js_code = manager._get_placeholder_js()
        curr_h = 0
        if manager._overlay:
            if manager._overlay.isVisible():
                curr_h = manager._overlay.height()
            else:
                curr_h = max(0, int(getattr(manager, "_last_h", 0) or 0))

        html = (
            f'<div id="pinned-placeholder" style="width: 100%; height: {curr_h}px; '
            'background: transparent; margin-top: 0px; margin-bottom: 10px;"></div>'
        )

        full_js = f"""
            (function() {{
                var existing = document.getElementById('pinned-placeholder');
                if (existing) existing.remove();

                var container = document.createElement('div');
                container.innerHTML = `{html}`;
                var placeholder = container.firstChild;

                var target = document.querySelector('.congrats:not(body), #congrats, .finished');

                if (target) {{
                    placeholder.style.marginTop = '0px';
                    target.before(placeholder);
                }} else {{
                    placeholder.style.marginTop = '15px';
                    var statsTable = document.querySelector('table');
                    if (statsTable) {{
                        statsTable.after(placeholder);
                    }} else {{
                        document.body.prepend(placeholder);
                    }}
                }}

                {js_code}
            }})();
            """
        webview.eval(full_js)
        try:
            did = mw.col.decks.selected()
        except Exception:
            did = None
        manager._current_deck_id = did
        manager._schedule_rebuild(did)


def get_placeholder_js(_manager):
    return """
            var throttleTimer = null;
            function requestGeom() {
                if (throttleTimer) return;
                throttleTimer = setTimeout(function() {
                    try { sendGeom(); } finally { throttleTimer = null; }
                }, 16);
            }
            function sendGeom() {
                var el = document.getElementById('pinned-placeholder');
                if (!el) return;
                var rect = el.getBoundingClientRect();
                var msg = `pinned:geom:${rect.left}:${rect.top}:${rect.width}:${rect.height}`;
                
                // Defensive check for bridge readiness
                if (typeof pycmd !== 'undefined' && typeof pycmd === 'function') {
                    pycmd(msg);
                } else if (window.qt && window.qt.postMessage) {
                    window.qt.postMessage(msg);
                } else {
                    // Bridge not ready, retry soon
                    setTimeout(sendGeom, 100);
                }
            }
            window.addEventListener('scroll', requestGeom, {passive: true, capture: true});
            window.addEventListener('resize', requestGeom, {passive: true});
            new MutationObserver(requestGeom).observe(document.body, {childList: true, subtree: true});
            
            // Heavy polling during initial "settlement" phase
            var pollCount = 0;
            function pollSettle() {
                sendGeom();
                if (pollCount < 20) {
                    pollCount++;
                    setTimeout(pollSettle, 100);
                }
            }
            pollSettle();
            
            window.forcePinnedUpdate = sendGeom;
            window.setPinnedHeight = function(h) {
                var el = document.getElementById('pinned-placeholder');
                if (el) { el.style.height = h + 'px'; sendGeom(); }
            };
        """


def inject_placeholder(manager, content, is_browser):
    curr_h = 0
    if manager._overlay:
        if manager._overlay.isVisible():
            curr_h = manager._overlay.height()
        elif is_browser:
            curr_h = max(0, int(getattr(manager, "_last_h", 0) or 0))

    cm = manager._get_config_manager()
    browser_is_top = bool(is_browser and cm.config.get(Config.PINNED_POSITION_TOP, True))
    js_logic = manager._get_placeholder_js()
    browser_reposition_js = ""
    if browser_is_top:
        browser_reposition_js = """
            function removeDeckBrowserStudiedToday() {
                var studiedToday = document.getElementById('studiedToday');
                if (!studiedToday) return false;
                studiedToday.remove();
                return true;
            }

            removeDeckBrowserStudiedToday();

            var deckBrowserPollCount = 0;
            function retryRemoveDeckBrowserStudiedToday() {
                if (removeDeckBrowserStudiedToday()) return;
                if (deckBrowserPollCount < 20) {
                    deckBrowserPollCount++;
                    setTimeout(retryRemoveDeckBrowserStudiedToday, 100);
                }
            }
            retryRemoveDeckBrowserStudiedToday();

            new MutationObserver(function() {
                removeDeckBrowserStudiedToday();
            }).observe(document.body, {childList: true, subtree: true});
        """

    m_top = 15 if is_browser else 0
    js = f"""
        <div id="pinned-placeholder" style="width: 100%; height: {curr_h}px; background: transparent; margin-top: {m_top}px; margin-bottom: 10px;"></div>
        <script>
        (function() {{
            {browser_reposition_js}
            {js_logic}
        }})();
        </script>
        """

    if is_browser:
        is_top = cm.config.get(Config.PINNED_POSITION_TOP, True)
        content.stats = js + content.stats if is_top else content.stats + js
    else:
        is_top = cm.config.get(Config.PINNED_POSITION_TOP_DECK, False)
        content.table = js + content.table if is_top else content.table + js

    try:
        webview_widget = mw.deckBrowser.web if manager._is_deck_browser else mw.overview.web
        if webview_widget:
            webview_widget.installEventFilter(manager)
    except Exception:
        log_swallowed()


def on_js_message(manager, handled, message, _context):
    if not isinstance(message, str):
        return handled
    if manager._rebuild_in_progress and message.startswith("pinned:geom:"):
        return handled

    if message.startswith("pinned:geom:"):
        try:
            parts = message.split(":")
            left = float(parts[2])
            top = float(parts[3])
            width = float(parts[4])
            height = float(parts[5])
            manager._update_overlay_geom(left, top, width, height)
            if manager._overlay and manager._overlay.property("needs_init_geom"):
                QTimer.singleShot(0, manager.sync_overlay)
        except Exception:
            log_swallowed()
        return (True, None)

    if message == "min-pinned-update-config":
        manager._mark_config_dirty()
        manager._get_config_manager(force_refresh=True)
        manager._schedule_rebuild(manager._current_deck_id)
        return (True, None)

    return handled


def event_filter(manager, obj, event, super_event_filter):
    box_containers = []
    for box_attr, container_attr in (
        ("_chart_boxes", "_charts_container"),
        ("_text_boxes", "_texts_container"),
    ):
        boxes = getattr(manager, box_attr, None)
        if isinstance(boxes, dict) and boxes:
            for box in boxes.values():
                container = box.get("container")
                if container is not None:
                    box_containers.append(container)
        else:
            container = getattr(manager, container_attr, None)
            if container is not None:
                box_containers.append(container)

    if obj in box_containers:
        box_id = 0
        box_kind = "chart"
        try:
            box_id = int(obj.property("deepdivestats_box_id") or obj.property("deepdivestats_chart_box_id") or 0)
        except Exception:
            box_id = 0
        try:
            box_kind = str(obj.property("deepdivestats_box_kind") or "chart")
        except Exception:
            box_kind = "chart"

        if event.type() == QEvent.Type.DragEnter:
            if event.mimeData().hasFormat("application/x-ankidive-chart-id"):
                source_id = event.mimeData().data("application/x-ankidive-chart-id").data().decode()
                manager._drag_cross = None
                status, _ml, _row_w = chart_drag_over(
                    manager, obj, box_id, box_kind, event.position().toPoint(), source_id
                )
                if status == "reject":
                    event.ignore()
                    return True
                manager._drag_source_id = source_id
                manager._drag_chart_box_id = box_id
                boxes_attr = "_text_boxes" if box_kind == "text" else "_chart_boxes"
                rows_attr = "_text_masonry_rows" if box_kind == "text" else "_chart_masonry_rows"
                box = getattr(manager, boxes_attr, {}).get(box_id) if isinstance(getattr(manager, boxes_attr, None), dict) else None
                if box and box.get("masonry") is not None:
                    manager._masonry_layout = box.get("masonry")
                for _, ml_anim in getattr(manager, rows_attr, []):
                    ml_anim.set_animate_moves(True)
                if box:
                    for _, ml_anim in box.get("rows", []):
                        ml_anim.set_animate_moves(True)
                event.acceptProposedAction()
                return True
        elif event.type() == QEvent.Type.DragMove:
            if event.mimeData().hasFormat("application/x-ankidive-chart-id"):
                pos = event.position().toPoint()
                status, ml, row_w = chart_drag_over(manager, obj, box_id, box_kind, pos, manager._drag_source_id)
                if status == "reject":
                    event.ignore()
                    return True
                event.acceptProposedAction()
                if status == "same":
                    # Live reorder inside the line the widget already is on.
                    manager._masonry_layout = ml
                    manager._handle_chart_move(pos - row_w.pos())
                return True
        elif event.type() == QEvent.Type.DragLeave:
            hide_marker(obj)
            manager._drag_cross = None
            return False
        elif event.type() == QEvent.Type.Drop:
            wid = event.mimeData().data(MIME_CHART_ID).data().decode()
            if wid:
                hide_marker(obj)
                cross = getattr(manager, "_drag_cross", None)
                if cross and cross.get("id") == wid:
                    # Another line or box: applied once the drag has ended (see flush_pending).
                    queue_move(cross)
                else:
                    manager._finalize_chart_reorder()
                manager._drag_cross = None
                event.acceptProposedAction()
                for rows_attr, boxes_attr in (
                    ("_chart_masonry_rows", "_chart_boxes"),
                    ("_text_masonry_rows", "_text_boxes"),
                ):
                    for _, ml_anim in getattr(manager, rows_attr, []):
                        ml_anim.set_animate_moves(False)
                    if not isinstance(getattr(manager, boxes_attr, None), dict):
                        continue
                    for box in getattr(manager, boxes_attr).values():
                        for _, ml_anim in box.get("rows", []):
                            ml_anim.set_animate_moves(False)
                manager._drag_source_id = None
                manager._drag_chart_box_id = None
                return True

    if event.type() in (QEvent.Type.Resize, QEvent.Type.Move, QEvent.Type.Show):
        if manager._overlay and manager._overlay.isVisible():
            manager.sync_overlay()
            if event.type() == QEvent.Type.Resize:
                manager._settle_sync_timer.start(180)
    return super_event_filter(obj, event)



