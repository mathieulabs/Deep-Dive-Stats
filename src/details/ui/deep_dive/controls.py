# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from ..theme.icons import get_svg_icon
from .. import Config
from ...animations.chart_policy import local_chart_animation_batch
from ...widgets.charts.common.zoom import update_chart_for_transition
from ...widgets.chart_utils.theme import get_theme_colors
from .controls_parts.adaptive_zoom import try_adaptive_zoom
from .controls_parts.chart_controls import add_chart_controls

class DeepDiveControlsMixin:
    def _adaptive_update_chart_data(self, chart, data):
        """Update chart data with a stable transition profile for adaptive zoom flows."""
        return update_chart_for_transition(
            chart,
            data,
            adaptive_binning=getattr(chart, "adaptive_binning", None),
            transition_mode="timespan",
            transition_align_right=getattr(self, "_adaptive_zoom_transition_align_right", True),
            transition=True,
            transition_duration_ms=260,
        )

    def _refresh_chart_control_icons(self):
        """Refresh Deep Dive header control icons using the active theme color."""
        try:
            t_colors = get_theme_colors(self.dialog)
            text_col = t_colors.get("text_secondary", t_colors.get("text"))
            icon_col = text_col.name() if hasattr(text_col, "name") else None
        except Exception:
            icon_col = None

        if hasattr(self, "btn_reset_zoom") and self.btn_reset_zoom:
            self.btn_reset_zoom.setIcon(get_svg_icon("rotate-ccw", color=icon_col, size=16, context_ref=self.dialog))
        for attr in ("activity_reset_btn", "retention_reset_btn", "added_reset_btn"):
            btn = getattr(self, attr, None)
            if btn:
                btn.setIcon(get_svg_icon("rotate-ccw", color=icon_col, size=14, context_ref=self.dialog))
        if hasattr(self, "btn_zoom_in") and self.btn_zoom_in:
            self.btn_zoom_in.setIcon(get_svg_icon("plus", color=icon_col, size=16, context_ref=self.dialog))
        if hasattr(self, "btn_zoom_out") and self.btn_zoom_out:
            self.btn_zoom_out.setIcon(get_svg_icon("minus", color=icon_col, size=16, context_ref=self.dialog))
        if hasattr(self, "chart_settings_btn") and self.chart_settings_btn:
            self.chart_settings_btn.setIcon(get_svg_icon("settings", color=icon_col, size=16, context_ref=self.dialog))

    def _apply_cumulative_mode_to_chart(self, chart, visible):
        """Apply running-total visibility to any compatible chart widget."""
        if not chart:
            return
        v = bool(visible)
        if hasattr(chart, "set_cumulative_mode"):
            chart.set_cumulative_mode(v)
            return
        changed = False
        if hasattr(chart, "cumulative_visible"):
            chart.cumulative_visible = v
            changed = True
        if hasattr(chart, "show_cumulative_axis"):
            chart.show_cumulative_axis = v
            changed = True
        if changed and hasattr(chart, "update"):
            chart.update()

    def _add_chart_controls(self, activity_header, retention_header, added_header, activity_data, retention_data):
        return add_chart_controls(self, activity_header, retention_header, added_header, activity_data, retention_data)

    def _try_adaptive_zoom(self, zoomed_slice, source_chart=None, start_idx=None, end_idx=None, charts=None):
        return try_adaptive_zoom(
            self,
            zoomed_slice,
            source_chart=source_chart,
            start_idx=start_idx,
            end_idx=end_idx,
            charts=charts,
        )

    def _adaptive_replace(self, chart, data_attr, new_data):
        """Replace chart data for adaptive zoom, saving originals for restoration."""
        if not chart:
            return
        if not hasattr(chart, '_pre_adaptive_data'):
            chart._pre_adaptive_data = getattr(chart, data_attr)

        if hasattr(chart, 'update_data'):
            self._adaptive_update_chart_data(chart, new_data)
        else:
            setattr(chart, data_attr, new_data)
            chart.data = new_data
            chart._full_length = len(new_data)
            chart._zoom_start = 0
            chart._zoom_end = len(new_data)
            chart._is_zoomed = False
            if hasattr(chart, '_scrollbar'):
                chart._scrollbar.hide()
            chart.update()

    def _restore_original_chart_data(self, only_added=False):
        """Restore chart data to original (pre-adaptive) state."""
        if hasattr(self, '_hi_res_history') and not only_added:
            del self._hi_res_history

        self._adaptive_transitioning = True
        try:
            charts_to_restore = []
            if only_added:
                charts_to_restore = [(getattr(self, 'added_chart', None), '_full_data')]
            else:
                charts_to_restore = [
                    (self.activity_chart, '_full_data'),
                    (self.stacked_chart, '_full_data'),
                    (getattr(self, 'added_chart', None), '_full_data'),
                    (getattr(self, 'retention_chart', None), '_full_retention_data')
                ]

            batch_anchor = (
                getattr(self, 'activity_chart', None)
                or getattr(self, 'stacked_chart', None)
                or getattr(self, 'added_chart', None)
                or getattr(self, 'retention_chart', None)
            )
            batch_candidates = [chart for chart, _data_attr in charts_to_restore if chart and hasattr(chart, '_pre_adaptive_data')]
            with local_chart_animation_batch(batch_anchor, candidates=batch_candidates or [batch_anchor]):
                for chart, data_attr in charts_to_restore:
                    if chart and hasattr(chart, '_pre_adaptive_data'):
                        original = chart._pre_adaptive_data
                        if hasattr(chart, 'update_data'):
                            self._adaptive_update_chart_data(chart, original)
                        else:
                            setattr(chart, data_attr, original)
                            chart.data = original
                            chart._full_length = len(original[next(iter(original))]) if isinstance(original, dict) else len(original)
                            chart._zoom_start = 0
                            chart._zoom_end = chart._full_length
                            chart._is_zoomed = False
                            if hasattr(chart, '_scrollbar'):
                                chart._scrollbar.hide()
                            if hasattr(chart, '_calc_averages'):
                                chart._calc_averages()
                            chart.update()

                        delattr(chart, '_pre_adaptive_data')
        finally:
            self._adaptive_transitioning = False

    def _reset_chart_order(self):
        """Reset the chart order and all chart sizes to defaults."""
        conf = self.addon_config.config
        changed = False

        if Config.DEEP_DIVE_CHART_ORDER in conf:
            del conf[Config.DEEP_DIVE_CHART_ORDER]
            changed = True

        if Config.DEEP_DIVE_WIDGET_SETTINGS in conf:
            settings = conf[Config.DEEP_DIVE_WIDGET_SETTINGS]
            for section in settings:
                if "height" in settings[section]:
                    del settings[section]["height"]
                    changed = True
                if "col_span" in settings[section]:
                    settings[section]["col_span"] = 1
                    changed = True

        if changed:
            self.addon_config.write_config()
            if hasattr(self, '_populate_dashboard'):
                self._populate_dashboard()



