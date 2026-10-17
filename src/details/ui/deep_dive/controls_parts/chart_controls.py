# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Deep Dive chart-header controls runtime helpers."""

from aqt.qt import QAction, QHBoxLayout, QLayout, QPushButton, QSize, Qt

from ... import Config
from ...theme.icons import get_svg_icon
from .....qss import set_qss
from ....logic.logger import log_swallowed
from .review_dots import refresh_review_dots
from ....widgets.chart_utils.zoom_camera import with_camera


def add_chart_controls(self, activity_header, retention_header, added_header, activity_data, retention_data):
    
    self.btn_reset_zoom = QPushButton("", parent=self.dialog)
    self.btn_reset_zoom.setIcon(get_svg_icon("rotate-ccw", context_ref=self.dialog))
    self.btn_reset_zoom.setIconSize(QSize(16, 16))
    self.btn_reset_zoom.setFixedSize(24, 24)
    self.btn_reset_zoom.setCursor(Qt.CursorShape.PointingHandCursor)
    self.btn_reset_zoom.setToolTip("Reset All Zooms")
    self.btn_reset_zoom.setVisible(False)
    self.btn_reset_zoom.setProperty("class", "expanded_header_btn")
    set_qss(self.btn_reset_zoom, "QPushButton::menu-indicator { width: 0px; }")
    
    def create_local_reset(tooltip, reset_callback):
        btn = QPushButton("", parent=self.dialog)
        btn.setIcon(get_svg_icon("rotate-ccw", context_ref=self.dialog))
        btn.setIconSize(QSize(14, 14))
        btn.setFixedSize(20, 20)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setToolTip(tooltip)
        btn.setVisible(False)
        btn.setProperty("class", "expanded_header_btn")
        btn.clicked.connect(reset_callback)
        return btn

    def reset_chart(chart, container=None):
        if chart and hasattr(chart, 'reset_zoom'):
            chart.reset_zoom()
            chart.update()
        
    def reset_all_zoom():
        self._syncing_zoom = True
        if getattr(self, '_adaptive_zoom_active', False):
            self._adaptive_zoom_active = False
            self._restore_original_chart_data()
        elif getattr(self, '_adaptive_zoom_active_added_only', False):
            self._adaptive_zoom_active_added_only = False
            self._restore_original_chart_data(only_added=True)

        for chart_attr in ['activity_chart', 'stacked_chart', 'retention_chart', 'added_chart']:
            reset_chart(getattr(self, chart_attr, None))
        self._syncing_zoom = False
        if self.last_history_data:
            # In steps during the zoom animation, like a zoom from the charts.
            from ..runtime.zoom_sync import schedule_stats

            schedule_stats(self, self.last_history_data[::-1])
            self._refresh_bottom_stats()
        update_all_reset_buttons()
        refresh_review_dots(self, immediate=True)
    reset_all_zoom = with_camera(reset_all_zoom)
    
    self.btn_reset_zoom.clicked.connect(reset_all_zoom)

    def reset_activity_local_zoom():
        # Activity header can display either Normal or Breakdown chart.
        # Reset both to avoid a no-op when only one variant is zoomed.
        if getattr(self, '_adaptive_zoom_active', False):
            self._adaptive_zoom_active = False
            self._restore_original_chart_data()
        reset_chart(getattr(self, "activity_chart", None))
        reset_chart(getattr(self, "stacked_chart", None))
        if self.last_history_data:
            from ..runtime.zoom_sync import schedule_stats

            schedule_stats(self, self.last_history_data[::-1])
            self._refresh_bottom_stats()
        update_all_reset_buttons()
        refresh_review_dots(self, immediate=True)
    reset_activity_local_zoom = with_camera(reset_activity_local_zoom)

    def reset_retention_local_zoom():
        reset_chart(getattr(self, "retention_chart", None))
        if self.last_history_data:
            from ..runtime.zoom_sync import schedule_stats

            schedule_stats(self, self.last_history_data[::-1])
            self._refresh_bottom_stats()
        update_all_reset_buttons()
    reset_retention_local_zoom = with_camera(reset_retention_local_zoom)

    def reset_added_local_zoom():
        if getattr(self, '_adaptive_zoom_active_added_only', False):
            self._adaptive_zoom_active_added_only = False
            self._restore_original_chart_data(only_added=True)
        reset_chart(getattr(self, "added_chart", None))
        if self.last_history_data:
            from ..runtime.zoom_sync import schedule_stats

            schedule_stats(self, self.last_history_data[::-1])
            self._refresh_bottom_stats()
        update_all_reset_buttons()
    reset_added_local_zoom = with_camera(reset_added_local_zoom)
    
    self.activity_reset_btn = create_local_reset("Reset Activity Zoom", reset_activity_local_zoom)
    self.retention_reset_btn = create_local_reset("Reset Retention Zoom", reset_retention_local_zoom)
    self.added_reset_btn = create_local_reset("Reset Added Zoom", reset_added_local_zoom)

    def update_all_reset_buttons():
        sync = getattr(self, 'last_sync_zoom', False)
        
        states = {}
        any_zoomed = False
        for attr in ['activity_chart', 'stacked_chart', 'retention_chart', 'added_chart']:
            chart = getattr(self, attr, None)
            is_z = bool(chart and hasattr(chart, '_is_zoomed') and chart._is_zoomed)
            states[attr] = is_z
            if is_z: any_zoomed = True
        
        # If adaptive zoom is active, it means we are zoomed in conceptually
        if getattr(self, '_adaptive_zoom_active', False) or getattr(self, '_adaptive_zoom_active_added_only', False):
            any_zoomed = True
        
        self.btn_reset_zoom.setVisible(sync and any_zoomed)
        
        self.activity_reset_btn.setVisible(not sync and (states.get('activity_chart') or states.get('stacked_chart')))
        self.retention_reset_btn.setVisible(not sync and states.get('retention_chart'))
        self.added_reset_btn.setVisible(not sync and states.get('added_chart'))
        refresh_review_dots(self)

    self.update_all_reset_buttons = update_all_reset_buttons

    self._adaptive_zoom_active = False  # Track adaptive resolution state
    self._adaptive_transitioning = False # Track when transitioning adaptive data

    def on_chart_zoom_changed(is_zoomed, start, end, source_chart=None):
        if is_zoomed:
            self.last_zoom_range = (start, end)
        else:
            self.last_zoom_range = None

        update_all_reset_buttons()

        # Charts zoomed by the sync of another chart: the source chart already
        # handled the adaptive check.
        if getattr(self, "_is_syncing_zoom", False):
            return
        # Stale callback (the data was swapped by an earlier handler).
        try:
            if source_chart is not None and (
                bool(source_chart._is_zoomed), int(source_chart._zoom_start), int(source_chart._zoom_end)
            ) != (bool(is_zoomed), int(start), int(end)):
                return
        except (AttributeError, RuntimeError, TypeError, ValueError):
            pass

        # Ignore transient callbacks while adaptive data replacement is in-flight.
        # During this phase, charts can emit temporary non-zoomed states.
        if getattr(self, "_adaptive_transitioning", False):
            return

        if self._adaptive_zoom_active:
            # Keep adaptive mode until an explicit reset, so a temporary is_zoomed=False
            # from an updated chart does not bounce back to the normal-resolution data.
            return

        if getattr(self, "_adaptive_zoom_active_added_only", False):
            # Same rationale as above for added-only adaptive mode.
            return

        sync_on = bool(getattr(self, 'last_sync_zoom', False))
        # 10-minute view when the zoom gets down to 2 days. With the sync off only the
        # charts of the zoomed section switch.
        if is_zoomed and self.last_history_data:
            history_oldest_first = self.last_history_data[::-1]
            is_added_chart = source_chart and source_chart == getattr(self, "added_chart", None)
            if is_added_chart and hasattr(source_chart, "_full_data") and isinstance(source_chart._full_data, list):
                zoomed_slice = source_chart._full_data[start:end]
            else:
                total_len = len(history_oldest_first)
                source_len = getattr(source_chart, "_full_length", total_len) if source_chart else total_len
                offset = total_len - source_len

                s_idx = max(0, start + offset)
                e_idx = max(0, min(total_len, end + offset))

                zoomed_slice = history_oldest_first[s_idx:e_idx]

            charts = None
            if not sync_on and source_chart is not None:
                activity_group = [c for c in (self.activity_chart, self.stacked_chart) if c is not None]
                charts = activity_group if source_chart in activity_group else [source_chart]
            self._try_adaptive_zoom(zoomed_slice, source_chart, start, end, charts=charts)

        if not sync_on and self.last_history_data:
            # If sync is OFF, make sure dashboard shows FULL range even if individual charts are zoomed
            self._update_stats_from_history(self.last_history_data[::-1])
            self._refresh_bottom_stats()
    
    def _connect_controls_zoom_handler(chart):
        if not (chart and hasattr(chart, "zoom_changed")):
            return
        # Only disconnect this module's previous handler; keep other subscribers intact.
        if hasattr(chart, "_controls_zoom_handler"):
            try:
                chart.zoom_changed.disconnect(chart._controls_zoom_handler)
            except (RuntimeError, TypeError):
                pass
        handler = (lambda z, s, e, c=chart: on_chart_zoom_changed(z, s, e, c))
        chart.zoom_changed.connect(handler)
        chart._controls_zoom_handler = handler

    def leave_adaptive_zoom(source_chart=None):
        """Zoom-out from the full 10-minute view: back to daily data, one step
        wider than the window the user had before entering it."""
        from ....widgets.charts.common.zoom import widen_zoom_window

        pre = getattr(self, "_pre_adaptive_zoom", None)
        self._pre_adaptive_zoom = None
        if getattr(self, "_adaptive_zoom_active", False):
            self._adaptive_zoom_active = False
            restored = [
                c for c in (self.activity_chart, self.stacked_chart, getattr(self, "retention_chart", None), getattr(self, "added_chart", None))
                if c is not None and hasattr(c, "_pre_adaptive_data")
            ]
            self._restore_original_chart_data()
            rows = list(reversed(self.last_history_data or []))
            if restored and rows and pre and pre[0] == "history":
                s, e = widen_zoom_window(rows, pre[1], pre[2])
                # With the sync on, zooming one chart zooms the others.
                for target in (restored[:1] if getattr(self, "last_sync_zoom", False) else restored):
                    offset = len(rows) - int(getattr(target, "_full_length", len(rows)) or len(rows))
                    target.set_zoom_range(max(0, s - offset), max(0, e - offset))
            elif self.last_history_data:
                self._update_stats_from_history(self.last_history_data[::-1])
                self._refresh_bottom_stats()
        elif getattr(self, "_adaptive_zoom_active_added_only", False):
            self._adaptive_zoom_active_added_only = False
            self._restore_original_chart_data(only_added=True)
            added = getattr(self, "added_chart", None)
            rows = list(getattr(added, "_full_data", None) or []) if added else []
            if added is not None and rows and pre and pre[0] == "added":
                s, e = widen_zoom_window(rows, pre[1], pre[2])
                added.set_zoom_range(s, e)
        update_all_reset_buttons()
    leave_adaptive_zoom = with_camera(leave_adaptive_zoom)

    def _connect_zoom_out_limit(chart):
        sig = getattr(chart, "zoom_out_limit", None) if chart else None
        if sig is None:
            return
        old = getattr(chart, "_controls_zoom_out_handler", None)
        if old is not None:
            try:
                sig.disconnect(old)
            except (RuntimeError, TypeError):
                pass

        def handler(c=chart):
            if getattr(self, "_adaptive_zoom_active", False) or getattr(self, "_adaptive_zoom_active_added_only", False):
                leave_adaptive_zoom(c)

        sig.connect(handler)
        chart._controls_zoom_out_handler = handler

    for chart in [self.activity_chart, self.stacked_chart, self.retention_chart, getattr(self, "added_chart", None)]:
        _connect_controls_zoom_handler(chart)
        _connect_zoom_out_limit(chart)

    self.btn_zoom_in = QPushButton("", parent=self.dialog)
    self.btn_zoom_in.setIcon(get_svg_icon("plus", context_ref=self.dialog))
    self.btn_zoom_in.setIconSize(QSize(16, 16))
    self.btn_zoom_in.setFixedSize(24, 24)
    self.btn_zoom_in.setCursor(Qt.CursorShape.PointingHandCursor)
    self.btn_zoom_in.setToolTip("Zoom In (Bigger Charts)")
    self.btn_zoom_in.setProperty("class", "expanded_header_btn")
    self.btn_zoom_in.clicked.connect(lambda: self._zoom_grid(1))

    self.btn_zoom_out = QPushButton("", parent=self.dialog)
    self.btn_zoom_out.setIcon(get_svg_icon("minus", context_ref=self.dialog))
    self.btn_zoom_out.setIconSize(QSize(16, 16))
    self.btn_zoom_out.setFixedSize(24, 24)
    self.btn_zoom_out.setCursor(Qt.CursorShape.PointingHandCursor)
    self.btn_zoom_out.setToolTip("Zoom Out (Smaller Charts)")
    self.btn_zoom_out.setProperty("class", "expanded_header_btn")
    self.btn_zoom_out.clicked.connect(lambda: self._zoom_grid(-1))

    btn_settings = QPushButton("", parent=self.dialog)
    btn_settings.setIcon(get_svg_icon("settings", context_ref=self.dialog))
    btn_settings.setIconSize(QSize(16, 16))
    btn_settings.setFixedSize(24, 24)
    btn_settings.setCursor(Qt.CursorShape.PointingHandCursor)
    btn_settings.setToolTip("Chart Options")
    btn_settings.setProperty("class", "expanded_header_btn")
    set_qss(btn_settings, "QPushButton::menu-indicator { width: 0px; }")
    
    from ...shared.menu import StyledMenu
    menu = StyledMenu(self.dialog)
    
    # Keep the header menu state aligned with the Activity section defaults. Do not
    # apply them at init, or they would override per-widget right-click settings
    # after each rebuild.
    effective_show_avg = self._get_dd_widget_setting("activity", "show_average", self.last_show_avg)
    effective_avg_active = self._get_dd_widget_setting("activity", "avg_on_active_days", self.last_avg_active)
    effective_show_cumulative = self._get_dd_widget_setting("activity", "show_cumulative", self.last_show_cumulative)
    self.last_show_avg = bool(effective_show_avg)
    self.last_avg_active = bool(effective_avg_active)
    self.last_show_cumulative = bool(effective_show_cumulative)

    self.action_show_avg = QAction("Show Average Line", self.dialog)
    self.action_show_avg.setCheckable(True)
    self.action_show_avg.setChecked(self.last_show_avg)
    
    self.action_avg_active = QAction("Average on Active Days", self.dialog)
    self.action_avg_active.setCheckable(True)
    self.action_avg_active.setChecked(self.last_avg_active)
    
    self.action_show_cumulative = QAction("Show Right Axis (Global)", self.dialog)
    self.action_show_cumulative.setCheckable(True)
    self.action_show_cumulative.setChecked(self.last_show_cumulative)
    
    self.action_global_stats = QAction("Show Bottom Stats (All Charts)", self.dialog)
    self.action_global_stats.setCheckable(True)
    self.action_global_stats.setChecked(self.addon_config.config.get(Config.DEEP_DIVE_SHOW_BOTTOM_STATS, False))

    self.action_global_show_stats = QAction("Show Stats (All Charts)", self.dialog)
    self.action_global_show_stats.setCheckable(True)
    self.action_global_show_stats.setChecked(self.addon_config.config.get(Config.DEEP_DIVE_SHOW_STATS, True))        
    def update_options():
        self.last_show_avg = self.action_show_avg.isChecked()
        self.last_avg_active = self.action_avg_active.isChecked()
        self.last_show_cumulative = self.action_show_cumulative.isChecked()
        
        self._update_dd_widget_settings_bulk("manager", {
            "show_average": self.last_show_avg,
            "avg_on_active_days": self.last_avg_active,
            "show_cumulative": self.last_show_cumulative
        }, refresh=False)

        # Mirror right-axis visibility preference to all supported sections.
        cumulative_sections = ["activity", "added", "hourly", "future_due", "review_intervals", "stability"]
        for section in cumulative_sections:
            self._update_dd_widget_setting(
                section,
                "show_cumulative",
                self.last_show_cumulative,
                refresh=False,
                write=False,
            )
        try:
            self.addon_config.write_config()
        except Exception:
            log_swallowed()

        avg_chart_attrs = [
            "activity_chart",
            "stacked_chart",
            "retention_chart",
            "added_chart",
        ]
        for attr in avg_chart_attrs:
            chart = getattr(self, attr, None)
            if chart and hasattr(chart, 'set_average_mode'):
                chart.set_average_mode(self.last_show_avg, self.last_avg_active)

        cumulative_chart_attrs = [
            "activity_chart",
            "stacked_chart",
            "added_chart",
            "hourly_chart",
            "future_due_chart",
            "review_intervals_chart",
            "stability_chart",
        ]
        for attr in cumulative_chart_attrs:
            chart = getattr(self, attr, None)
            if chart:
                self._apply_cumulative_mode_to_chart(chart, self.last_show_cumulative)
                
    self.action_show_avg.triggered.connect(update_options)
    self.action_avg_active.triggered.connect(update_options)
    self.action_show_cumulative.triggered.connect(update_options)
    self.action_global_stats.triggered.connect(lambda checked: self._toggle_global_bottom_stats(checked))
    self.action_global_show_stats.triggered.connect(lambda checked: self._toggle_global_show_stats(checked))

    
    def toggle_sync(checked):
        self.last_sync_zoom = checked
        self._update_dd_widget_setting("manager", "sync_zoom", checked, refresh=False)
        update_all_reset_buttons()
        
        if self.last_history_data:
            history_oldest_first = self.last_history_data[::-1]
            if not checked:
                self._update_stats_from_history(history_oldest_first)
            else:
                # If turning ON, and something is zoomed, sync dashboard AND other charts to it
                any_zoomed = False
                start, end = 0, 0
                source_c = None
                for attr in ['activity_chart', 'stacked_chart', 'retention_chart', 'added_chart']:
                    c = getattr(self, attr, None)
                    if c and hasattr(c, '_is_zoomed') and c._is_zoomed:
                        any_zoomed = True
                        source_c = c
                        if hasattr(self, 'last_zoom_range') and self.last_zoom_range:
                            start, end = self.last_zoom_range
                        break
                
                if any_zoomed:
                    history_oldest_first = self.last_history_data[::-1]
                    self._update_stats_from_history(history_oldest_first[start:end])
                    if source_c:
                        source_c.zoom_changed.emit(True, start, end)

    self.action_sync_zoom = QAction("Sync Zoom Across Charts", self.dialog)
    self.action_sync_zoom.setCheckable(True)
    self.action_sync_zoom.setChecked(self.last_sync_zoom)
    self.action_sync_zoom.triggered.connect(lambda: toggle_sync(self.action_sync_zoom.isChecked()))
    
    self.action_reset_order = QAction("Reset Chart Layout", self.dialog)
    self.action_reset_order.triggered.connect(self._reset_chart_order)
    
    menu.addAction(self.action_show_avg)
    menu.addAction(self.action_avg_active)
    menu.addSeparator()
    menu.addAction(self.action_show_cumulative)
    menu.addAction(self.action_global_stats)
    menu.addAction(self.action_global_show_stats)
    menu.addSeparator()
    
    from ... import ADAPTIVE_CHART_BINNING
    self.action_adaptive_binning = QAction("Adaptive Binning (Global)", self.dialog)
    self.action_adaptive_binning.setCheckable(True)
    self.action_adaptive_binning.setChecked(self.addon_config.config.get(ADAPTIVE_CHART_BINNING, True))
    def toggle_global_binning(checked):
        self.addon_config.config[ADAPTIVE_CHART_BINNING] = checked
        # Global toggle should be authoritative: clear per-chart overrides so
        # charts immediately follow the global mode.
        override_sections = [
            "activity", "retention", "added",
            "future_due", "review_intervals", "stability",
            "difficulty", "retrievability",
        ]
        for section in override_sections:
            self._update_dd_widget_setting(
                section, "binning_override", None, refresh=False, write=False
            )
        self.addon_config.write_config()
        # Apply to all visible Deep Dive charts (only if no per-chart override)
        all_chart_attrs = [
            'activity_chart', 'stacked_chart', 'retention_chart', 'added_chart',
            'stability_chart', 'difficulty_chart', 'retrievability_chart',
            'future_due_chart', 'review_intervals_chart'
        ]
        for attr in all_chart_attrs:
            c = getattr(self, attr, None)
            if not c:
                continue
            if not hasattr(c, 'adaptive_binning'):
                continue
            c.binning_override = None
            c.adaptive_binning = checked
            # Force a true data rebuild for immediate visual effect.
            if hasattr(c, 'update_data'):
                try:
                    if hasattr(c, '_full_retention_data'):
                        c.update_data(c._full_retention_data or c.retention_data, adaptive_binning=checked, transition=False)
                    elif hasattr(c, 'data_dict'):
                        c.update_data(c.data_dict, adaptive_binning=checked, transition_mode=None)
                    elif hasattr(c, 'data'):
                        c.update_data(c.data, adaptive_binning=checked, transition_mode=None)
                    else:
                        raise RuntimeError("No known data source for update_data")
                except Exception:
                    if hasattr(c, '_invalidate_data_caches'):
                        c._invalidate_data_caches()
                    elif hasattr(c, '_invalidate_caches'):
                        c._invalidate_caches()
            c.update()
    self.action_adaptive_binning.triggered.connect(lambda: toggle_global_binning(self.action_adaptive_binning.isChecked()))
    menu.addAction(self.action_adaptive_binning)

    menu.addAction(self.action_sync_zoom)
    menu.addSeparator()
    menu.addAction(self.action_reset_order)
    btn_settings.setMenu(menu)

    self.chart_settings_menu = menu 
    self.chart_settings_btn = btn_settings
    self._refresh_chart_control_icons()

    if hasattr(self.dialog, 'expanded_header_controls') and self.dialog.expanded_header_controls is not None:
        while self.dialog.expanded_header_controls.count():
            item = self.dialog.expanded_header_controls.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        self.dialog.expanded_header_controls.addWidget(self.btn_reset_zoom, 0, Qt.AlignmentFlag.AlignVCenter)
        self.dialog.expanded_header_controls.addWidget(self.btn_zoom_out, 0, Qt.AlignmentFlag.AlignVCenter)
        self.dialog.expanded_header_controls.addWidget(self.btn_zoom_in, 0, Qt.AlignmentFlag.AlignVCenter)
        self.dialog.expanded_header_controls.addWidget(btn_settings, 0, Qt.AlignmentFlag.AlignVCenter)
    else:
        header_layout = self.dialog.findChild(QHBoxLayout, "expanded_header_controls")
        if header_layout:
             header_layout.addWidget(self.btn_reset_zoom, 0, Qt.AlignmentFlag.AlignVCenter)
             header_layout.addWidget(btn_settings, 0, Qt.AlignmentFlag.AlignVCenter)
        
    for h_obj, btn in [
        (activity_header, self.activity_reset_btn),
        (retention_header, self.retention_reset_btn),
        (added_header, self.added_reset_btn)
    ]:
        if h_obj:
            if isinstance(h_obj, (QHBoxLayout, QLayout)):
                h_obj.addWidget(btn)
            else:
                lay = h_obj.layout()
                if lay:
                    lay.addWidget(btn)


