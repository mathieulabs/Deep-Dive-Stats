# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from datetime import datetime, timedelta

from aqt.qt import QPoint, Qt, QWidget

from ....ui import rollover_hour
from ...chart_utils.formatting import fmt_num_trim_zeros
from .metrics import components, component_label, component_value
from ...chart_utils.tooltip import (
    hide_tooltip_targets,
    hide_tooltips_on_window_deactivate,
    show_tooltip_near,
)


def show_tooltip_for_date_impl(widget, target_date, mx, my):
    """Build and display the tooltip for a given datetime."""
    date_str = target_date.isoformat()[:10]
    months_en = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    pretty_date = f"{months_en[target_date.month-1]} {target_date.day}, {target_date.year}"

    entry = widget.data.get(date_str, {})
    if not isinstance(entry, dict):
        entry = {"reviews": entry}

    count = entry.get("reviews", 0)
    future = entry.get("future", 0)
    time_ms = entry.get("time_ms", 0)
    passed = entry.get("passed", 0)

    lines = [{"text": pretty_date, "header": True}]

    offset = rollover_hour()
    logical_today_date = (datetime.now() - timedelta(hours=offset)).date()
    is_future = target_date.date() > logical_today_date
    is_today = target_date.date() == logical_today_date

    if is_future:
        lines.append({"id": "reviews", "text": "Future Reviews", "value": str(future)} if future > 0 else {"id": "reviews", "text": "No reviews due", "value": ""})
    else:
        lines.append({"id": "reviews", "text": "Reviews", "value": str(count)})
        if is_today:
            live_pending = widget._get_live_today_pending()
            pending_val = int(live_pending) if live_pending is not None else int(future)
            lines.append({"id": "pending", "text": "Today Pending", "value": str(pending_val)})

    if not is_future and count > 0:
        for comp in components(getattr(widget, "metric", "reviews")):
            if comp[0] in ("reviews", "time", "retention"):
                continue  # already listed below
            val = component_value(comp, entry)
            shown = f"{val / 1000.0:.1f}s" if comp[0] == "avg_time" else str(int(val))
            lines.append({"id": "details", "text": component_label(comp), "value": shown})

    if time_ms > 0:
        mins = int(time_ms / 60000)
        secs = int((time_ms % 60000) / 1000)
        lines.append({"id": "time", "text": "Time", "value": f"{mins}m {secs}s" if mins > 0 else f"{secs}s"})

    if count > 0:
        lines.append({"id": "retention", "text": "Retention", "value": f"{fmt_num_trim_zeros((passed / count) * 100, 1)}%"})

    show_tooltip_near(
        widget,
        widget.tooltip_window,
        QPoint(int(mx), int(my)),
        lines=lines,
        x_offset=15,
        y_offset=15,
        edge_padding=10,
        show_only_if_hidden=False,
    )


def get_live_today_pending_impl(widget):
    """Return live pending count for 'today' (deck-scoped when possible)."""
    try:
        from aqt import mw
        if not getattr(mw, "col", None):
            return None
        today = int(mw.col.sched.today or 0)
        day_cutoff = int(getattr(mw.col.sched, "day_cutoff", 0) or 0)
        daystart = day_cutoff - 86400

        deck_id = widget.property("pinned_deck_id")
        if deck_id is None:
            deck_id = widget.property("heatmap_deck_id")

        did_clause = ""
        params = [today, daystart, day_cutoff]

        if deck_id == -1:
            did_clause = " AND (CASE WHEN cards.odid > 0 THEN cards.odid ELSE cards.did END) IS NULL"
        elif deck_id in [None, 0, "0", "collection"]:
            did_clause = ""
        elif isinstance(deck_id, str):
            all_decks = mw.col.decks.all_names_and_ids()
            dids = [d.id for d in all_decks if d.name == deck_id or d.name.startswith(deck_id + "::")]
            if not dids:
                return 0
            placeholders = ",".join("?" for _ in dids)
            did_clause = f" AND (CASE WHEN cards.odid > 0 THEN cards.odid ELSE cards.did END) IN ({placeholders})"
            params.extend(dids)
        else:
            dids = list(mw.col.decks.deck_and_child_ids(int(deck_id)) or [])
            if not dids:
                return 0
            placeholders = ",".join("?" for _ in dids)
            did_clause = f" AND (CASE WHEN cards.odid > 0 THEN cards.odid ELSE cards.did END) IN ({placeholders})"
            params.extend(dids)

        q = (
            "SELECT COUNT(*) FROM cards "
            "WHERE ("
            " (queue IN (2, 3) AND due = ?) OR "
            " (queue IN (1, 3) AND due >= ? AND due < ?)"
            f"){did_clause}"
        )
        return int(mw.col.db.scalar(q, *params) or 0)
    except Exception:
        return None


def _update_legend_cursor(widget, pos):
    from .legend import legend_step_at

    over = legend_step_at(widget, pos) is not None
    if over != bool(getattr(widget, "_legend_cursor_on", False)):
        widget._legend_cursor_on = over
        if over:
            widget.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            widget.unsetCursor()
    return over


def mouse_move_event_impl(widget, event):
    widget.hover_pos = event.position()
    if _update_legend_cursor(widget, widget.hover_pos):
        widget.tooltip_window.hide()
        widget.update()
        return
    mx = widget.hover_pos.x()
    my = widget.hover_pos.y()

    if widget.view_mode == "continuous":
        hit = widget._continuous_hit_test(mx, my)
        if not hit:
            widget.tooltip_window.hide()
            widget.update()
            return
        _date_str, target_date, _col, _row, _bx = hit
        widget._show_tooltip_for_date(target_date, mx, my)
        widget.update()
        return

    cell_size, spacing, start_x, start_y, _label_space = widget._get_grid_geometry()
    step = cell_size + spacing

    if mx < start_x or my < start_y:
        widget.tooltip_window.hide()
        widget.update()
        return

    week_idx = int((mx - start_x) / step)
    day_idx = int((my - start_y) / step)

    if week_idx < 0 or week_idx > 52 or day_idx < 0 or day_idx > 6:
        widget.tooltip_window.hide()
        widget.update()
        return

    grid_start, in_range = widget._compute_grid_info()
    target_date = grid_start + timedelta(weeks=week_idx, days=day_idx)

    if not in_range(target_date):
        widget.tooltip_window.hide()
        widget.update()
        return

    widget._show_tooltip_for_date(target_date, mx, my)
    widget.update()


def mouse_press_event_impl(widget, event):
    if event.button() == Qt.MouseButton.LeftButton:
        from .legend import legend_step_at

        step = legend_step_at(widget, event.position())
        if step is not None:
            widget.toggle_legend_step(step)
            return
    if widget.day_clicked and event.button() == Qt.MouseButton.LeftButton:
        mx = event.position().x()
        my = event.position().y()

        if widget.view_mode == "continuous":
            hit = widget._continuous_hit_test(mx, my)
            if hit:
                date_str, _dt, _c, _r, _bx = hit
                widget.day_clicked(date_str)
            return

        cell_size, spacing, start_x, start_y, _label_space = widget._get_grid_geometry()
        step = cell_size + spacing

        if mx < start_x or my < start_y:
            return
        week_idx = int((mx - start_x) / step)
        day_idx = int((my - start_y) / step)

        if week_idx < 0 or week_idx > 52 or day_idx < 0 or day_idx > 6:
            return

        cell_rel_x = (mx - start_x) % step
        cell_rel_y = (my - start_y) % step

        if cell_rel_x > cell_size or cell_rel_y > cell_size:
            return

        grid_start, in_range = widget._compute_grid_info()
        target_date = grid_start + timedelta(weeks=week_idx, days=day_idx)

        if not in_range(target_date):
            return

        date_str = target_date.isoformat()[:10]
        widget.day_clicked(date_str)
        return

    QWidget.mousePressEvent(widget, event)


def leave_event_impl(widget, event):
    widget.hover_pos = None
    _update_legend_cursor(widget, None)
    hide_tooltip_targets(widget, "tooltip_window")
    widget.update()


def hide_event_impl(widget, event):
    """Make sure tooltips are hidden when the widget is hidden."""
    hide_tooltip_targets(widget, "tooltip_window")
    if hasattr(widget, "_data_transition_anim"):
        widget._data_transition_anim.stop()
        widget._clear_data_transition_state()
    if hasattr(widget, "_mode_transition_anim"):
        widget._mode_transition_anim.stop()
        widget._clear_mode_transition_state()
    if hasattr(widget, "_nav_transition_anim"):
        widget._nav_transition_anim.stop()
        widget._clear_nav_transition_state()
    QWidget.hideEvent(widget, event)


def change_event_impl(widget, event):
    """Hide tooltips if window becomes inactive."""
    hide_tooltips_on_window_deactivate(widget, event, "tooltip_window")
    QWidget.changeEvent(widget, event)
