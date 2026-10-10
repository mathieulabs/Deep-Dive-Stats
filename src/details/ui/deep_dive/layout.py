# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import Qt, QWidget, QPropertyAnimation, QEvent
import time
from ..theme.icons import get_svg_icon
from ...widgets.chart_utils.theme import get_theme_colors
from .. import Config
from .layout_parts.section_card import add_section_card
from .layout_parts.refresh_runtime import refresh_dashboard_data
from .layout_parts.populate_runtime import populate_dashboard
from ...widgets.pinned.widget_factory.wrapper import ResizableWrapper
from ....qss import set_qss
from ...logic.logger import log_swallowed

class GridContainer(QWidget):
    def __init__(self, parent, manager):
        super().__init__(parent)
        self.manager = manager
        
    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.manager._handle_grid_wheel(event)
            event.accept()
        else:
            super().wheelEvent(event)

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat("application/x-ankidive-chart-id"):
            event.acceptProposedAction()
            if self.layout() and hasattr(self.layout(), "set_animate_moves"):
                self.layout().set_animate_moves(True)
    
    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat("application/x-ankidive-chart-id"):
            event.acceptProposedAction()
            self.manager._handle_deep_dive_reorder_move(event)

    def dropEvent(self, event):
        if event.mimeData().hasFormat("application/x-ankidive-chart-id"):
            event.acceptProposedAction()
            self.manager._finalize_deep_dive_reorder()
            if self.layout() and hasattr(self.layout(), "set_animate_moves"):
                self.layout().set_animate_moves(False)

class DeepDiveLayoutMixin:
    def _apply_grid_header_theme(self, container):
        """Apply theme-aware colors to a grid card header (title + collapse arrow)."""
        if container is None:
            return
        t_colors = get_theme_colors(container)
        text_col = t_colors.get("text_secondary", t_colors.get("text"))
        bg_hover_col = t_colors.get("bg_hover")
        text_hex = text_col.name() if hasattr(text_col, "name") else "#a1a1aa"
        if hasattr(bg_hover_col, "red"):
            hover_bg = f"rgba({bg_hover_col.red()},{bg_hover_col.green()},{bg_hover_col.blue()},{bg_hover_col.alpha()})"
        else:
            hover_bg = "rgba(255,255,255,0.1)" if bool(t_colors.get("is_dark")) else "rgba(0,0,0,0.06)"

        if hasattr(container, "btn_toggle") and container.btn_toggle:
            collapsed = bool(getattr(container, "is_collapsed", False))
            container.btn_toggle.setIcon(
                get_svg_icon("chevron-right" if collapsed else "chevron-down", color=text_hex)
            )
            set_qss(container.btn_toggle, 
                "QPushButton { background: transparent; border: none; padding: 0; margin: 0; } "
                f"QPushButton:hover {{ background: {hover_bg}; border-radius: 4px; }}"
            )

        title_label = getattr(container, "title_label", None)
        if title_label is not None:
            set_qss(title_label, 
                f"margin-left: 0px; color: {text_hex}; font-weight: 700; font-size: 10px; letter-spacing: 0.6px;"
            )

    def _refresh_all_grid_headers_theme(self):
        """Refresh all deep-dive grid card headers currently mounted."""
        root = getattr(self.dialog, "expanded_container", None) or self.dialog
        for w in root.findChildren(ResizableWrapper):
            if getattr(w, "is_deep_dive", False):
                self._apply_grid_header_theme(w)

    def _clear_layout(self, layout):
        """Recursively clear a layout and delete all widgets."""
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                if item.widget():
                    w = item.widget()
                    if hasattr(w, "animation") and isinstance(w.animation, QPropertyAnimation):
                        w.animation.stop()
                    w.deleteLater()
                elif item.layout():
                    self._clear_layout(item.layout())
            layout.deleteLater()

    def _handle_grid_wheel(self, event):
        """Handle Ctrl+Wheel zoom for Grid mode."""
        delta = event.angleDelta().y()
        self._zoom_grid(1 if delta > 0 else -1)

    def _zoom_grid(self, direction):
        """Scale grid columns: direction > 0 is In (fewer columns), < 0 is Out (more columns)."""
        if direction > 0:
            # Zoom in: bigger boxes, fewer columns
            self.grid_columns = max(1, self.grid_columns - 1)
        else:
            # Zoom out: smaller boxes, more columns
            self.grid_columns = min(4, self.grid_columns + 1)
            
        if hasattr(self, 'current_grid_layout') and self.current_grid_layout:
            self.current_grid_layout.set_preferred_columns(self.grid_columns)
            self.current_grid_layout.activate()
            self.addon_config.set_value(Config.DEEP_DIVE_GRID_COLUMNS, self.grid_columns)

    def _update_grid_widget_collapse(self, w, collapsed, update_persistence=True):
        w.is_collapsed = collapsed
        
        sk = getattr(w, "state_key", None)
        if sk and update_persistence: 
            self.section_collapse_states[sk] = collapsed
        
        if collapsed:
            if not hasattr(w, "original_min_h"):
                w.original_min_h = w.minimumHeight()
            w.setFixedHeight(40)
            w.setMaximumHeight(40)
        else:
            orig_h = getattr(w, "original_min_h", 200)
            w.setMinimumHeight(orig_h)
            w.setMaximumHeight(16777215)

        self._apply_grid_header_theme(w)
        if hasattr(w, "body_widget") and w.body_widget:
            if collapsed: w.body_widget.hide()
            else: w.body_widget.show()
        if hasattr(w, "controls_wrapper") and w.controls_wrapper:
            w.controls_wrapper.setVisible(not collapsed)

    def _update_grid_widget_height(self, w, h):
        """Update a widget's height visually and update session-local original_min_h."""
        w.setMinimumHeight(h)
        # Make sure it doesn't get capped by initial setup max heights
        w.setMaximumHeight(16777215)
        w.original_min_h = h

    def _get_grid_rows(self):
        """Return visible grid rows using the same span-aware packing as ResponsiveGridLayout."""
        layout = getattr(self, "current_grid_layout", None)
        if not layout:
            return []

        num_cols = int(getattr(layout, "current_cols", 0) or getattr(layout, "preferred_columns", 1) or 1)
        num_cols = max(1, num_cols)

        rows = []
        current_row = []
        slots_occupied = 0

        for i in range(layout.count()):
            item = layout.itemAt(i)
            if not item:
                continue
            w = item.widget()
            if not w or w.isHidden():
                continue

            span = int(getattr(w, "col_span", 1) or 1)
            span = max(1, min(num_cols, span))

            if slots_occupied + span > num_cols and current_row:
                rows.append(current_row)
                current_row = []
                slots_occupied = 0

            current_row.append(w)
            slots_occupied += span

        if current_row:
            rows.append(current_row)

        return rows


    def _sync_grid_row_collapse(self):
        if not hasattr(self, 'current_grid_layout') or not self.current_grid_layout:
            return
        layout = self.current_grid_layout
        row_sets = self._get_grid_rows()
        if not row_sets:
            return

        for row_widgets in row_sets:
            if not row_widgets:
                continue
            
            # Source of truth: is ANY widget in this row marked as collapsed in persistence?
            should_collapse = any(
                self.section_collapse_states.get(getattr(w, "state_key", ""), False) 
                for w in row_widgets
            )
            
            for w in row_widgets:
                self._update_grid_widget_collapse(w, should_collapse, update_persistence=False)
        
        layout.invalidate()
        if layout.parentWidget():
            layout.parentWidget().updateGeometry()

    def _sync_grid_row_height(self, emitting_widget, new_h):
        """When one chart in a grid row is resized, update all siblings in that row visually."""
        if not hasattr(self, 'current_grid_layout') or not self.current_grid_layout:
            return
        # Ignore pure horizontal drags; only vertical resize should sync row height.
        resize_mode = getattr(emitting_widget, "_resize_mode", None)
        if resize_mode and ("b" not in str(resize_mode)):
            return
        layout = self.current_grid_layout
        row_sets = self._get_grid_rows()
        if not row_sets:
            return

        emitting_widget.setFixedHeight(new_h)
        
        for row_widgets in row_sets:
            if emitting_widget in row_widgets:
                for wi in row_widgets:
                    if wi != emitting_widget:
                        wi.setFixedHeight(new_h)
                break
        
        layout.invalidate()
        if layout.parentWidget():
            layout.parentWidget().updateGeometry()

    def _persist_grid_row_height(self, emitting_widget, new_h):
        """When a resize finishes (mouse release), save heights of all widgets in the row to the config."""
        if new_h is None:
            return
            
        if not hasattr(self, 'current_grid_layout') or not self.current_grid_layout:
            return
        layout = self.current_grid_layout
        row_sets = self._get_grid_rows()
        if not row_sets:
            return


        self._update_grid_widget_height(emitting_widget, new_h)
        
        target_row = None
        for row_widgets in row_sets:
            if emitting_widget in row_widgets:
                target_row = row_widgets
                break

        if target_row:
            for wi in target_row:
                self._update_grid_widget_height(wi, new_h)
                
                # Persist to config WITHOUT triggering a refresh and WITHOUT writing to disk yet
                sk = getattr(wi, "state_key", None)
                if sk:
                    # Normalize height: Subtract extra stats height before saving
                    # so that saved height always reflects the BASE chart height.
                    _text_extra = {
                        "future_due": 90, "review_intervals": 50, "stability": 50,
                        "difficulty": 60, "retrievability": 80,
                        "activity": 50, "retention": 50, "added": 50,
                    }
                    show_bottom_stats = self.addon_config.config.get(Config.DEEP_DIVE_SHOW_BOTTOM_STATS, False)
                    show_all_stats = self.addon_config.config.get(Config.DEEP_DIVE_SHOW_STATS, True)
                    
                    persisted_h = new_h
                    if show_bottom_stats and show_all_stats:
                        persisted_h -= _text_extra.get(sk, 50)
                    
                    self._update_dd_widget_setting(sk, "height", persisted_h, refresh=False, write=False)
        
            if hasattr(self, 'addon_config'):
                self.addon_config.write_config()

        
        layout.invalidate()
        if layout.parentWidget():
            layout.parentWidget().updateGeometry()


    def _get_widget_history(self, section_key, full_history):
        """Slice history data based on widget-specific time span (Newest First).

        The Activity chart also leaves out the review types the user hid.
        """
        rows = self._slice_widget_history(section_key, full_history)
        if section_key == "activity":
            from ...logic.data.transforms.activity_series import filter_activity_types

            hidden = self._get_dd_widget_setting("activity", "hidden_review_types", None)
            rows = filter_activity_types(rows, hidden)
        return rows

    def _slice_widget_history(self, section_key, full_history):
        span = self._get_dd_widget_setting(section_key, "time_span")
        
        # In List mode, we want Activity and Retention to strictly follow the global tab range
        # (ignoring ghost settings from previous versions or Pinned views)
        if not self.grid_mode and section_key in ["activity", "retention"]:
            return full_history
            
        if span is None or int(span) == int(self.last_history_range):
            return full_history
            
        from .. import Period
        days = Period.DAYS_IN.get(int(span), 0)
        
        if int(span) == Period.CUSTOM:
             days = self._get_dd_widget_setting(section_key, "custom_days", 7)
        elif int(span) == Period.TOTAL:
             return full_history
        elif int(span) == Period.TODAY: days = 1
        elif int(span) == Period.YESTERDAY:
             return full_history[1:2] if len(full_history) > 1 else []
        elif int(span) == Period.YEAR: days = 365
        elif int(span) == Period.LAST_YEAR:
             days = 365 # Rough slicing for last year if global is Total
             
        if days > 0:
             return full_history[:days]
        return full_history

    def _handle_deep_dive_reorder_move(self, event):
        drop_pos = event.position().toPoint()
        now = time.time()
        if now - getattr(self, "_last_drag_move_time", 0) < 0.02:
            return
        self._last_drag_move_time = now

        from ...widgets.pinned.drag_drop.engine import ReorderEngine
        
        if self.grid_mode:
            if not self.current_grid_layout: return
            target_idx = ReorderEngine.get_grid_target_index(
                self.current_grid_layout, drop_pos, exclude_id=self._drag_source_id
            )
        else:
            target_idx = ReorderEngine.get_linear_target_index(
                self.dialog.expanded_chart_area, drop_pos, exclude_id=self._drag_source_id, vertical=True
            )
        
        # Capture the source ID if it is still missing
        if not getattr(self, "_drag_source_id", None):
             if event and hasattr(event, "mimeData"):
                  mime = event.mimeData()
                  if mime.hasFormat("application/x-ankidive-chart-id"):
                       self._drag_source_id = mime.data("application/x-ankidive-chart-id").data().decode()
        
        if not getattr(self, "_drag_source_id", None):
            return

        layout = self.current_grid_layout if self.grid_mode else self.dialog.expanded_chart_area
        source_w = ReorderEngine.get_source_widget(layout, self._drag_source_id)
        if source_w:
            if self.grid_mode:
                layout.move_item(layout.indexOf(source_w), target_idx)
            else:
                ReorderEngine.shift_in_layout(layout, source_w, target_idx)

    def _finalize_deep_dive_reorder(self):
        from ...widgets.pinned.drag_drop.engine import ReorderEngine
        layout = self.current_grid_layout if self.grid_mode else self.dialog.expanded_chart_area
        ReorderEngine.persist_reorder(layout, widget_type_group="deep_dive_chart", manager=self)
        self._drag_source_id = None

    def _add_section_card(self, label_text, widget_or_layout, spacing=25, target_layout=None, manual_add=False, header_layout=None, state_key=None):
        return add_section_card(
            self,
            label_text,
            widget_or_layout,
            spacing=spacing,
            target_layout=target_layout,
            manual_add=manual_add,
            header_layout=header_layout,
            state_key=state_key,
        )

    def _toggle_global_bottom_stats(self, enabled):
        """Toggle the visibility of bottom stats for all charts globally. Forces a full rebuild."""
        self.addon_config.set_value(Config.DEEP_DIVE_SHOW_BOTTOM_STATS, enabled)
        
        # Only rebuild if the deep dive is currently open with data
        if not getattr(self, 'last_row_data', None):
            return

        # Clean up and repopulate from cached data, no data fetch
        self._cleanup_previous_view()
        self._populate_dashboard()
        self._setup_zoom_sync()

    def _toggle_global_show_stats(self, enabled):
        """Toggle the visibility of all stats globally. Forces a full rebuild."""
        self.addon_config.set_value(Config.DEEP_DIVE_SHOW_STATS, enabled)
        
        # Only rebuild if the deep dive is currently open with data
        if not getattr(self, 'last_row_data', None):
            return

        # Clean up and repopulate from cached data, no data fetch
        self._cleanup_previous_view()
        self._populate_dashboard()
        self._setup_zoom_sync()


    def _set_section_visible(self, key, visible):
        wrapper = self.section_wrappers.get(key)
        if wrapper:
            if wrapper.isHidden() == bool(visible):
                parent = wrapper.parentWidget()
                lay = parent.layout() if parent is not None else None
                if lay is not None and hasattr(lay, "animate_next") and wrapper.isVisibleTo(parent) != bool(visible):
                    lay.animate_next()
            wrapper.setVisible(visible)

    def _set_section_empty(self, key, empty):
        """Show a "No data for this graph" label over a section that has no data."""
        from ...widgets.chart_utils.empty_overlay import set_no_data

        wrapper = self.section_wrappers.get(key)
        body = getattr(wrapper, "body_widget", None) if wrapper else None
        set_no_data(body, empty, style_label=self.apply_deep_dive_theme)

    def _refresh_dashboard_data(self):
        return refresh_dashboard_data(self)

    def _refresh_bottom_stats(self):
        """Refresh all AdaptiveStatsWidget instances, O(N) via body_widget lookup."""
        from ...widgets.common import AdaptiveStatsWidget
        scroll_content = self.dialog.expanded_chart_area.parentWidget()
        if not scroll_content:
            return
        for stats_w in scroll_content.findChildren(AdaptiveStatsWidget):
            chart = None
            p = stats_w.parent()
            while p and p is not scroll_content:
                if hasattr(p, 'body_widget') and p.body_widget:
                    from aqt.qt import QStackedWidget
                    if hasattr(p.body_widget, 'get_stats_text'):
                        chart = p.body_widget
                    elif isinstance(p.body_widget, QStackedWidget):
                        chart = p.body_widget.currentWidget()
                    else:
                        for candidate in p.body_widget.findChildren(QWidget):
                            if hasattr(candidate, 'get_stats_text'):
                                chart = candidate
                                break
                    break
                p = p.parent()
            if chart:
                try:
                    stats_w.update_text(chart.get_stats_text())
                except Exception:
                    log_swallowed()

    def _populate_dashboard(self, is_warmup=False):
        return populate_dashboard(self, GridContainer, is_warmup=is_warmup)

    def eventFilter(self, obj, event):
        if not self.grid_mode and obj == self.dialog.expanded_scroll.widget():
            if event.type() == QEvent.Type.DragEnter:
                if event.mimeData().hasFormat("application/x-ankidive-chart-id"):
                    self._drag_source_id = event.mimeData().data("application/x-ankidive-chart-id").data().decode()
                    event.acceptProposedAction()
                    return True
            elif event.type() == QEvent.Type.DragMove:
                if event.mimeData().hasFormat("application/x-ankidive-chart-id"):
                    event.acceptProposedAction()
                    self._handle_deep_dive_reorder_move(event)
                    return True
            elif event.type() == QEvent.Type.Drop:
                if event.mimeData().hasFormat("application/x-ankidive-chart-id"):
                    event.acceptProposedAction()
                    self._finalize_deep_dive_reorder()
                    return True
        
        # For Grid mode, the GridContainer calls manager directly,
        # but the source ID must still be captured on drag enter.
        if self.grid_mode and isinstance(obj, GridContainer):
            if event.type() == QEvent.Type.DragEnter:
                if event.mimeData().hasFormat("application/x-ankidive-chart-id"):
                    self._drag_source_id = event.mimeData().data("application/x-ankidive-chart-id").data().decode()
                    # Event is accepted in GridContainer.dragEnterEvent
        
        return super().eventFilter(obj, event)


    def _cleanup_previous_view(self):
        stats_container = getattr(self.dialog, 'expanded_stats_layout', None)
        while self.dialog.expanded_chart_area.count():
            item = self.dialog.expanded_chart_area.takeAt(0)
            if item.widget():
                w = item.widget()
                if w == stats_container: w.hide(); w.setParent(self.dialog); continue
                # Disconnect zoom callbacks before deletion to prevent stale-reference crashes
                if getattr(w, '_sync_connected', False):
                    try:
                        w.zoom_changed.disconnect()
                    except Exception:
                        log_swallowed()
                    w._sync_connected = False
                w.deleteLater()
            elif item.layout(): self._clear_layout(item.layout())

        self.activity_chart = None
        self.stacked_chart = None
        self.retention_chart = None
        self.added_chart = None
        self.dist_chart = None
        self.heatmap_chart = None
        self.hourly_chart = None
        self.future_due_chart = None
        self.review_intervals_chart = None
        self.stability_chart = None
        self.difficulty_chart = None
        self.retrievability_chart = None
        self.section_wrappers = {}
        self.current_grid_layout = None
        self.masonry_layout = None
        self._build_queue_active = False




