# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from .. import Config


def on_visual_buttons_toggled(dialog, state):
    from aqt.qt import QTimer
    import time as _time

    val = state if isinstance(state, bool) else dialog.visual_toggle.isChecked()
    dialog.addon_config.config[Config.SHOW_BUTTONS_DIST_VISUAL] = val
    dialog.addon_config.set_value(Config.SHOW_BUTTONS_DIST_VISUAL, val)
    run_id = int(getattr(dialog, "_visual_refresh_run_id", 0) or 0) + 1
    dialog._visual_refresh_run_id = run_id

    if hasattr(dialog, "invalidate_view_switch_cache"):
        dialog.invalidate_view_switch_cache()

    idx = dialog.tab_widget.currentIndex()

    if dialog.view_mode == "time":
        from ...logic.tabs import populate_time_tab

        queue = list(range(dialog.tab_widget.count()))
        if idx in queue:
            queue.remove(idx)
            queue.insert(0, idx)
        state = {"done": 0, "skipped": 0, "total": len(queue)}

        def _step():
            if getattr(dialog, "_visual_refresh_run_id", 0) != run_id:
                return
            if not queue:
                return

            tab_idx = queue.pop(0)
            step_started_at = _time.perf_counter()
            if hasattr(dialog, "_time_tabs_populated"):
                dialog._time_tabs_populated.discard(tab_idx)
            ok = populate_time_tab(dialog, tab_idx, do_resize=(tab_idx == idx))
            if ok:
                state["done"] += 1
                if tab_idx == idx and hasattr(dialog, "on_tab_changed"):
                    dialog.on_tab_changed(tab_idx)
            else:
                state["skipped"] += 1

            step_ms = (_time.perf_counter() - step_started_at) * 1000.0
            next_delay_ms = 6 if tab_idx == idx else 12
            if step_ms > 80:
                next_delay_ms = max(next_delay_ms, 24)
            QTimer.singleShot(next_delay_ms, _step)

        _step()
        return

    from ..deck_view import populate_deck_tab

    queue = []
    visible = []
    hidden = []
    for i in range(dialog.tab_widget.count()):
        w = dialog.tab_widget.widget(i)
        did = w.property("deck_id") if w else None
        if did not in getattr(dialog, "deck_view_data", {}):
            continue
        queue.append(i)
        if dialog.tab_widget.isTabVisible(i):
            visible.append(i)
        else:
            hidden.append(i)
    ordered = []
    if idx in queue:
        ordered.append(idx)
    ordered.extend([i for i in visible if i != idx])
    ordered.extend([i for i in hidden if i != idx])
    queue = ordered

    state = {"done": 0, "total": len(queue)}

    def _step_deck():
        if getattr(dialog, "_visual_refresh_run_id", 0) != run_id:
            return
        if not queue:
            return

        tab_idx = queue.pop(0)
        step_started_at = _time.perf_counter()
        if hasattr(dialog, "_deck_tabs_populated"):
            dialog._deck_tabs_populated.discard(tab_idx)
        populate_deck_tab(dialog, tab_idx, do_resize=(tab_idx == idx), from_tab_change=True)
        state["done"] += 1
        if tab_idx == idx and hasattr(dialog, "on_tab_changed"):
            dialog.on_tab_changed(tab_idx)

        step_ms = (_time.perf_counter() - step_started_at) * 1000.0
        next_delay_ms = 6 if tab_idx == idx else 14
        if step_ms > 80:
            next_delay_ms = max(next_delay_ms, 26)
        QTimer.singleShot(next_delay_ms, _step_deck)

    _step_deck()


def on_visual_option_toggled(dialog, key, value):
    """One entry of the Visuals menu changed."""
    if key == Config.SHOW_BUTTONS_DIST_VISUAL:
        return on_visual_buttons_toggled(dialog, bool(value))
    dialog.addon_config.config[key] = bool(value)
    dialog.addon_config.set_value(key, bool(value))
    if hasattr(dialog, "invalidate_view_switch_cache"):
        dialog.invalidate_view_switch_cache()
    idx = dialog.tab_widget.currentIndex()
    if dialog.view_mode == "time":
        dialog.load_tabs(reason="retention_visual_toggle", force=True)
    else:
        dialog.load_deck_view(reason="retention_visual_toggle", force=True)
    dialog.tab_widget.setCurrentIndex(idx)


def on_retention_spark_toggled(dialog, state):
    val = dialog.retention_spark_toggle.isChecked()
    dialog.addon_config.config[Config.RETENTION_SPARKLINE] = val
    dialog.addon_config.set_value(Config.RETENTION_SPARKLINE, val)
    if hasattr(dialog, "invalidate_view_switch_cache"):
        dialog.invalidate_view_switch_cache()
    idx = dialog.tab_widget.currentIndex()
    if dialog.view_mode == "time":
        dialog.load_tabs(reason="retention_spark_toggle", force=True)
    else:
        dialog.load_deck_view(reason="retention_spark_toggle", force=True)
    dialog.tab_widget.setCurrentIndex(idx)

