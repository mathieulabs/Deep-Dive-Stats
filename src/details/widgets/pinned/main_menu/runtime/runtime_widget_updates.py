# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from datetime import datetime

from aqt import mw
from aqt.qt import QLabel, QPushButton, QTimer, QWidget

from .....animations.chart_policy import chart_animation_batch
from ..imports import Config
from ..imports import ThemeContext, get_theme_colors
from ...store.registry import WidgetRegistry
from ......qss import set_qss
from .....logic.logger import log_swallowed


def schedule_deferred_widget_update(
    manager,
    widget,
    widget_def,
    deck_id,
    signature,
    delay_ms,
    allow_blocking=False,
):
    widget_id = widget_def.get("id")
    update_key = (deck_id, widget_id, signature, bool(allow_blocking))
    if update_key in manager._pending_deferred_widget_updates:
        return
    manager._pending_deferred_widget_updates.add(update_key)

    def _run_deferred():
        manager._pending_deferred_widget_updates.discard(update_key)
        try:
            if manager._external_refresh_suspensions:
                return
            if not manager._overlay or widget is None or widget.isHidden():
                return
            if manager._current_deck_id != deck_id:
                return
            # Skip if a concurrent update (e.g. partial_refresh) already applied
            # this exact signature, avoids double animation.
            if manager._widget_update_signatures.get(widget_id) == signature:
                return
            from ...widget_factory.factory import WidgetFactory

            history_cache = manager.__class__._global_history_cache
            with chart_animation_batch(
                manager._overlay,
                [widget],
                force_repaint_candidates=True,
            ):
                sync_ok = WidgetFactory.update(
                    widget,
                    widget_def,
                    deck_id=deck_id,
                    cache=history_cache,
                    fail_if_not_cached=not bool(allow_blocking),
                    cfg=manager._config_manager,
                )
            if sync_ok:
                manager._widget_update_signatures[widget_id] = signature
                if getattr(widget, "_is_loading", False):
                    widget._is_loading = False
                    try:
                        manager._fade_in_widget(widget)
                    except Exception:
                        log_swallowed()
                return
            manager._trigger_async_widget_update(widget, widget_def, deck_id)
        except Exception:
            log_swallowed()

    QTimer.singleShot(max(0, int(delay_ms)), _run_deferred)


def get_zoom_factor(manager):
    """Return the current webview zoom factor (1.0 = no zoom)."""
    try:
        web = mw.deckBrowser.web if manager._is_deck_browser else mw.overview.web
        if web:
            return web.zoomFactor()
    except Exception:
        log_swallowed()
    return 1.0


def zoomed_scale(manager, base_pct):
    """A scale setting (percent) with Anki's current interface zoom applied."""
    try:
        z = min(3.0, max(0.5, float(get_zoom_factor(manager) or 1.0)))
        return max(50, int(round(int(base_pct) * z)))
    except Exception:
        log_swallowed()
        return base_pct


def apply_zoom_scale_to_widgets(manager, zoom):
    """Apply webview zoom factor to pinned widget runtime sizing."""
    try:
        z = float(zoom or 1.0)
    except Exception:
        z = 1.0
    if z < 0.5:
        z = 0.5
    elif z > 3.0:
        z = 3.0

    try:
        base_face = int(manager._config_manager.config.get(Config.FACECARDS_SCALE, 100))
        scaled_face = max(50, int(round(base_face * z)))
        stats_boxes = []
        stats_map = getattr(manager, "_stats_containers", None)
        if isinstance(stats_map, dict) and stats_map:
            stats_boxes.extend([w for w in stats_map.values() if w is not None])
        elif manager._stats_container:
            stats_boxes.append(manager._stats_container)

        for stats_box in stats_boxes:
            stats_box.set_scale(scaled_face)
            try:
                stats_box.update_layout(stats_box.width())
            except Exception:
                log_swallowed()
    except Exception:
        log_swallowed()

    try:
        base_hm = int(manager._config_manager.config.get(Config.HEATMAP_SCALE, 100))
        hm_scale = max(50, int(round(base_hm * z)))
    except Exception:
        hm_scale = max(50, int(round(100 * z)))

    defs_by_id = {d.get("id"): d for d in WidgetRegistry.get_all()}
    for wid, widget in list(manager._active_widgets.items()):
        if not widget or not hasattr(widget, "apply_size"):
            continue
        try:
            widget._zoom_scale = z
            wdef = defs_by_id.get(wid, {})
            widget.apply_size(wdef.get("width"), wdef.get("height"))
            try:
                from ....charts.heatmap import HeatmapWidget

                hm = widget.findChild(HeatmapWidget)
                if hm:
                    hm.set_scale(hm_scale)
            except Exception:
                log_swallowed()
            try:
                nav = widget.findChild(QWidget, "heatmap_nav_controls")
                if nav:
                    fs = max(7, int(round(10 * z)))
                    btn_sz = max(14, int(round(20 * z)))
                    btn_365_w = max(20, int(round(28 * z)))
                    nav_lay = nav.layout()
                    if nav_lay:
                        nav_lay.setSpacing(max(2, int(round(2 * z))))
                    t = get_theme_colors(ThemeContext.PINNED)
                    is_dark = bool(t.get("is_dark"))
                    txt_sec = t.get("text_secondary", t.get("text"))
                    txt_pri = t.get("text_primary", t.get("text"))
                    accent = t.get("accent")
                    bg_hover = t.get("bg_hover")
                    txt_sec_hex = txt_sec.name() if txt_sec is not None else ("#a1a1aa" if is_dark else "#71717a")
                    txt_pri_hex = txt_pri.name() if txt_pri is not None else ("#f4f4f5" if is_dark else "#18181b")
                    if bg_hover is not None:
                        hover_bg = f"rgba({bg_hover.red()},{bg_hover.green()},{bg_hover.blue()},{bg_hover.alpha()})"
                    else:
                        hover_bg = "rgba(255,255,255,0.1)" if is_dark else "rgba(0,0,0,0.05)"
                    active_bg = (
                        f"rgba({accent.red()},{accent.green()},{accent.blue()},40)"
                        if accent is not None
                        else "rgba(59,130,246,40)"
                    )
                    year_lbl = nav.findChild(QLabel, "heatmap_year_lbl")
                    if year_lbl:
                        set_qss(year_lbl, 
                            f"font-weight: 800; font-size: {fs}px; color: {txt_sec_hex}; letter-spacing: 1px; "
                            f"margin-left: {max(2, int(round(2 * z)))}px; margin-right: {max(2, int(round(2 * z)))}px;"
                        )
                    for name in ("heatmap_mode_cont", "heatmap_mode_year", "heatmap_btn_prev", "heatmap_btn_next"):
                        b = nav.findChild(QPushButton, name)
                        if b:
                            b.setFixedSize(btn_sz, btn_sz)
                            is_active = bool(b.property("heatmap_mode_active"))
                            if is_active and name.startswith("heatmap_mode_"):
                                set_qss(b, 
                                    "QPushButton { "
                                    f"background: {active_bg}; border: none; "
                                    f"font-weight: 800; font-size: {fs}px; color: {txt_pri_hex}; "
                                    "padding: 0px; margin: 0px; border-radius: 3px; } "
                                    f"QPushButton:hover {{ background: {active_bg}; color: {txt_pri_hex}; }} "
                                    f"QPushButton:pressed {{ background: {active_bg}; color: {txt_pri_hex}; }}"
                                )
                            else:
                                set_qss(b, 
                                    "QPushButton { background: transparent; border: none; "
                                    f"font-weight: 800; font-size: {fs}px; color: {txt_sec_hex}; "
                                    "padding: 0px; margin: 0px; border-radius: 3px; } "
                                    f"QPushButton:hover {{ background: {hover_bg}; color: {txt_pri_hex}; }} "
                                    f"QPushButton:pressed {{ background: {active_bg}; color: {txt_pri_hex}; }}"
                                )
                    b365 = nav.findChild(QPushButton, "heatmap_mode_365")
                    if b365:
                        b365.setFixedSize(btn_365_w, btn_sz)
                        is_active_365 = bool(b365.property("heatmap_mode_active"))
                        if is_active_365:
                            set_qss(b365, 
                                "QPushButton { "
                                f"background: {active_bg}; border: none; "
                                f"font-weight: 800; font-size: {fs}px; color: {txt_pri_hex}; "
                                "padding: 0px; margin: 0px; border-radius: 3px; } "
                                f"QPushButton:hover {{ background: {active_bg}; color: {txt_pri_hex}; }} "
                                f"QPushButton:pressed {{ background: {active_bg}; color: {txt_pri_hex}; }}"
                            )
                        else:
                            set_qss(b365, 
                                "QPushButton { background: transparent; border: none; "
                                f"font-weight: 800; font-size: {fs}px; color: {txt_sec_hex}; "
                                "padding: 0px; margin: 0px; border-radius: 3px; } "
                                f"QPushButton:hover {{ background: {hover_bg}; color: {txt_pri_hex}; }} "
                                f"QPushButton:pressed {{ background: {active_bg}; color: {txt_pri_hex}; }}"
                            )
                    header_lbl = widget.findChild(QLabel, "pinned_header")
                    if header_lbl:
                        hf = header_lbl.font()
                        hf.setPixelSize(max(8, int(round(11 * z))))
                        header_lbl.setFont(hf)
                    header = nav.parentWidget()
                    if header and header.layout():
                        header.layout().setSpacing(max(6, int(round(8 * z))))
            except Exception:
                log_swallowed()
        except Exception:
            continue


def trigger_async_widget_update(manager, widget, widget_def, deck_id):
    from ...context_access import get_pinned_context
    from ...widget_factory.utils import fetch_history_async

    if manager._external_refresh_suspensions:
        return

    wtype = widget_def.get("type", "")
    widget_id = widget_def.get("id")

    type_map = {
        "added": "added",
        "distribution": "distribution",
        "card_counts": "card_counts",
        "heatmap": "heatmap",
        "stat_card": "stats",
    }
    history_type = type_map.get(wtype, "reviews")

    span = manager._normalize_time_span(widget_def.get("time_span"), wtype)
    if wtype == "heatmap":
        from ....charts.heatmap import HeatmapWidget

        chart = widget if hasattr(widget, "end_date") else widget.findChild(HeatmapWidget)
        if chart and hasattr(chart, "end_date"):
            span = chart.end_date.year
        else:
            span = datetime.now().year

    span = manager._normalize_time_span(span, wtype)
    update_key = (deck_id, int(span), history_type, widget_id)
    if update_key in manager._pending_updates:
        return

    def on_data_ready(data):
        manager._pending_updates.discard(update_key)
        if manager._external_refresh_suspensions:
            return
        try:
            from aqt.qt import sip

            if widget is not None and sip.isdeleted(widget):
                return
        except Exception:
            log_swallowed()

        if not manager._overlay or not widget:
            current_did = manager._current_deck_id
            QTimer.singleShot(0, lambda d=current_did: manager._schedule_rebuild(d))
            return
        if manager._current_deck_id != deck_id:
            current_did = manager._current_deck_id
            QTimer.singleShot(0, lambda d=current_did: manager._schedule_rebuild(d))
            return

        from ...widget_factory.factory import WidgetFactory

        history_cache = manager.__class__._global_history_cache
        must_allow_blocking = history_type == "heatmap"
        with chart_animation_batch(
            manager._overlay,
            [widget],
            force_repaint_candidates=True,
        ):
            _async_ok = WidgetFactory.update(
                widget,
                widget_def,
                deck_id=deck_id,
                cache=history_cache,
                fail_if_not_cached=not must_allow_blocking,
                cfg=manager._config_manager,
            )
        if _async_ok and getattr(widget, "_is_loading", False):
            widget._is_loading = False
            try:
                manager._fade_in_widget(widget)
            except Exception:
                log_swallowed()
        if _async_ok and wtype == "heatmap" and deck_id is None:
            try:
                manager._clear_browser_heatmap_snapshot_overlay()
            except Exception:
                log_swallowed()
        manager._resize_overlay()

    ctx = get_pinned_context(
        deck_id,
        span,
        cfg=manager._config_manager,
        allow_slow_ops=False,
    )
    if ctx:
        if history_type == "card_counts":
            ctx_key = "counts"
        elif history_type == "heatmap":
            ctx_key = "heatmap_data"
        elif history_type == "stats":
            ctx_key = "stats"
        else:
            ctx_key = history_type
        data = ctx.get(ctx_key)
        if data:
            on_data_ready(data)
            return

    manager._pending_updates.add(update_key)
    fetch_history_async(
        deck_id,
        span,
        on_data_ready,
        cache=manager.__class__._global_history_cache,
        history_type=history_type,
    )





