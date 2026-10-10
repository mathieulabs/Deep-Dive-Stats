# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import Qt, QLabel, QCheckBox, QColor, QRadioButton

from .. import Period, ADAPTIVE_CHART_BINNING
from ...widgets.common.pill_toggles import pill_checkbox_qss, pill_radio_qss
from ...widgets.charts.grouped_bar import GroupedBarWidget
from ...widgets.charts.added_chart import AddedChartWidget
from ...widgets.charts.pie_chart import PieChartWidget
from ...logic.data.transforms import (
    empty_distribution_payload,
    has_distribution_values,
    resolve_added_history_desc,
    resolve_card_counts_payload,
    resolve_distribution_payload,
    resolve_fsrs_payload,
)
from ...logic.data.section_fetchers import fetch_section_data
from ...widgets.chart_utils.theme import get_theme_colors, resolve_theme_runtime_state, ThemeContext
from ...widgets.common import (
    default_fsrs_filter_idx,
    resolve_fsrs_filters,
    apply_chart_display_config,
    create_chart_header_for_chart,
    create_fsrs_filter_group,
    create_checkbox,
    create_chart_header,
    create_radio_group,
    resolve_fsrs_filter_choice,
)
from .. import Config
from .charts_parts.runtime_sections import (
    build_future_due_section,
    build_hourly_section,
    build_review_intervals_section,
)
from .charts_parts.views import create_activity_chart_view, create_retention_chart_view
from .charts_parts.heatmap_section import build_heatmap_section
from ....qss import set_qss

class DeepDiveChartsMixin:
    def _control_theme_tokens(self):
        t_colors = get_theme_colors(getattr(self, "dialog", None))
        conf = getattr(getattr(self, "dialog", None), "addon_config", None)
        conf_data = getattr(conf, "config", {}) if conf is not None else {}
        runtime = resolve_theme_runtime_state(conf_data, ThemeContext.DETAILS)
        is_dark = bool(runtime.get("is_dark", bool(t_colors.get("is_dark"))))
        text_secondary = t_colors.get(
            "text_secondary",
            t_colors.get("text", QColor("#a1a1aa" if is_dark else "#71717a")),
        )
        border = t_colors.get("border", QColor("#52525b" if is_dark else "#a1a1aa"))
        accent = t_colors.get("accent", QColor("#3b82f6"))
        indicator_bg = QColor(border)
        indicator_bg.setAlpha(36 if is_dark else 24)
        return {
            "is_dark": is_dark,
            "text_secondary": text_secondary.name(),
            "indicator_border": border.name(),
            "indicator_bg": f"rgba({indicator_bg.red()},{indicator_bg.green()},{indicator_bg.blue()},{indicator_bg.alpha()})",
            "accent": f"rgba({accent.red()},{accent.green()},{accent.blue()},180)",
        }

    def _apply_checkbox_theme(self, cb):
        # Header toggles drawn as small pills (shared with pinned widgets).
        if cb is None:
            return
        tokens = self._control_theme_tokens()
        text_color = cb.property("deepdivestats_text_color") or tokens["text_secondary"]
        accent = cb.property("deepdivestats_accent_rgba") or tokens["accent"]
        font_weight = cb.property("deepdivestats_font_weight") or "600"
        set_qss(cb, pill_checkbox_qss(text_color, accent, tokens["is_dark"], font_weight=str(font_weight)))

    def _apply_radio_theme(self, rb):
        # Radio groups as a segmented control (shared with pinned widgets).
        if rb is None:
            return
        tokens = self._control_theme_tokens()
        text_color = rb.property("deepdivestats_text_color") or tokens["text_secondary"]
        accent = rb.property("deepdivestats_accent_rgba") or tokens["accent"]
        set_qss(rb, pill_radio_qss(text_color, accent, tokens["is_dark"]))

    def apply_deep_dive_theme(self, root=None):
        target = root or getattr(self, "dialog", None)
        if target is None:
            return

        all_cbs = target.findChildren(QCheckBox)
        all_rbs = target.findChildren(QRadioButton)
        styled_cbs = [cb for cb in all_cbs if cb.property("deepdivestats_theme_role") in {"styled_checkbox", "retention_checkbox"}]
        styled_rbs = [rb for rb in all_rbs if rb.property("deepdivestats_theme_role") == "styled_radio"]

        if isinstance(target, QCheckBox):
            self._apply_checkbox_theme(target)
        elif isinstance(target, QRadioButton):
            self._apply_radio_theme(target)
        elif isinstance(target, QLabel):
            if target.property("deepdivestats_theme_role") == "empty_label":
                tokens = self._control_theme_tokens()
                set_qss(target, f"color: {tokens['text_secondary']}; font-size: 13px;")

        for cb in styled_cbs:
            self._apply_checkbox_theme(cb)
            cb.style().unpolish(cb)
            cb.style().polish(cb)
            cb.update()

        for rb in styled_rbs:
            self._apply_radio_theme(rb)
            rb.style().unpolish(rb)
            rb.style().polish(rb)
            rb.update()

        for lbl in target.findChildren(QLabel):
            if lbl.property("deepdivestats_theme_role") == "empty_label":
                tokens = self._control_theme_tokens()
                set_qss(lbl, f"color: {tokens['text_secondary']}; font-size: 13px;")

    def _make_styled_checkbox(self, text, checked=True, parent=None):
        def _setup_checkbox(cb):
            cb.setProperty("deepdivestats_theme_role", "styled_checkbox")
            self.apply_deep_dive_theme(cb)

        return create_checkbox(text, checked=checked, parent=parent, setup=_setup_checkbox)

    def _make_radio_group(self, options, default_idx, callback, parent=None):
        return create_radio_group(
            options,
            default_idx,
            callback,
            parent=parent,
            setup_button=lambda rb: rb.setProperty("deepdivestats_theme_role", "styled_radio"),
            setup_container=self.apply_deep_dive_theme,
        )


    def _create_activity_chart_view(self, activity_data, history_oldest_first):
        return create_activity_chart_view(self, activity_data, history_oldest_first)

    def _create_retention_chart_view(self, retention_data):
        return create_retention_chart_view(self, retention_data)

    def _show_empty_charts(self):
        """Setting: keep Deep Dive charts that have no data (default off: they are left out)."""
        try:
            from .. import Config
            return bool(self.addon_config.config.get(Config.SHOW_EMPTY_CHARTS, False))
        except Exception:
            return False

    def _add_empty_label(self, stack, text):
        l = QLabel(text, parent=stack)
        l.setProperty("deepdivestats_theme_role", "empty_label")
        self.apply_deep_dive_theme(l)
        l.setAlignment(Qt.AlignmentFlag.AlignCenter)
        stack.addWidget(l)

    def _build_added_section(self, deck_identifier, period_range, row_data, target_layout=None, manual_add=False, header_layout=None):
        current_idx = self.dialog.tab_widget.currentIndex()
        tab_config = self._resolve_tab_config(current_idx, period_range)
        
        target_did = row_data.get("did")
        if target_did is None and self.dialog.view_mode != 'time':
             target_did = tab_config.get("deck_id")
            
        if period_range is not None:
             history_range = int(period_range)
        else:
             history_range = tab_config.get("range", Period.TOTAL)

        is_deleted = row_data.get("is_deleted", False)
        
        ctx = getattr(self, "last_history_context", {}) or {}
        is_skeleton = getattr(self, "_is_skeleton", False)
        added_data_desc = resolve_added_history_desc(
            ctx,
            is_skeleton=is_skeleton,
            fetcher=(
                None
                if is_skeleton
                else lambda: fetch_section_data(
                    self.addon_config,
                    "added",
                    deck_id=target_did,
                    range_type=history_range,
                    is_deleted=is_deleted,
                )
            ),
        )
        added_data = added_data_desc[::-1]
        
        if not added_data or not any(d.get("count", 0) > 0 for d in added_data):
            if not (is_skeleton or self._show_empty_charts()):
                return None, None
            added_data = []
 
        adaptive = self.dialog.addon_config.config.get(ADAPTIVE_CHART_BINNING, True)
        self.added_chart = AddedChartWidget(added_data, parent=self.dialog, adaptive_binning=adaptive)
        
        section_key = "added"
        binning_override = self._get_dd_widget_setting(section_key, "binning_override", None)
        self.added_chart.binning_override = binning_override
        self.added_chart.binning_toggled_callback = lambda val: self._update_dd_widget_setting("added", "binning_override", val, refresh=False)
        
        section_key = "added"
        is_cumul = self._get_dd_widget_setting(section_key, "show_cumulative", True)
        show_avg = self._get_dd_widget_setting(section_key, "show_average", True)
        avg_on_active = self._get_dd_widget_setting(section_key, "avg_on_active_days", True)
        self.added_chart.set_cumulative_mode(is_cumul)
        if hasattr(self.added_chart, "set_average_mode"):
            self.added_chart.set_average_mode(show_avg, avg_on_active)
        apply_chart_display_config(
            self.added_chart,
            opacity=self._get_dd_widget_setting(section_key, "chart_opacity", 100),
            line_opacity=self._get_dd_widget_setting(section_key, "line_opacity", None),
            bar_gradient=self._get_dd_widget_setting(section_key, "bar_gradient", None),
            show_grid=self._get_dd_widget_setting(section_key, "show_grid", None),
            minimum_height=120,
            expanding=True,
        )

        header_widget, _, _, _ = create_chart_header_for_chart(
            self.added_chart,
            self.addon_config,
            Config.DEEP_DIVE_SHOW_BOTTOM_STATS,
            Config.DEEP_DIVE_SHOW_STATS,
            parent=self.dialog,
        )
        
        return self.added_chart, header_widget

    def _build_distribution_section(self, deck_identifier, period_range, row_data, target_layout=None, manual_add=False):
        current_idx = self.dialog.tab_widget.currentIndex()
        tab_config = self._resolve_tab_config(current_idx, period_range)
        
        target_did = row_data.get("did")
        if target_did is None and self.dialog.view_mode != 'time':
             target_did = tab_config.get("deck_id")
            
        if period_range is not None:
             history_range = int(period_range)
        else:
             history_range = tab_config.get("range", Period.TOTAL)

        is_deleted = row_data.get("is_deleted", False)

        ctx = getattr(self, "last_history_context", {}) or {}
        is_skeleton = getattr(self, "_is_skeleton", False)
        c_days = self._get_dd_widget_setting("distribution", "custom_days", 7)
        c_type = self._get_dd_widget_setting("distribution", "custom_type", "relative")
        s_date = self._get_dd_widget_setting("distribution", "start_date", "")
        e_date = self._get_dd_widget_setting("distribution", "end_date", "")
        dist_data = resolve_distribution_payload(
            ctx,
            is_skeleton=is_skeleton,
            fetcher=(
                None
                if is_skeleton
                else lambda: fetch_section_data(
                    self.addon_config,
                    "distribution",
                    deck_id=target_did,
                    range_type=history_range,
                    is_deleted=is_deleted,
                    custom_days=c_days,
                    custom_type=c_type,
                    start_date_str=s_date,
                    end_date_str=e_date,
                )
            ),
        )

        if not has_distribution_values(dist_data):
            if not (is_skeleton or self._show_empty_charts()):
                return None, None
            dist_data = empty_distribution_payload()
        
        dist_chart = GroupedBarWidget(dist_data, parent=self.dialog)
        apply_chart_display_config(
            dist_chart,
            opacity=self._get_dd_widget_setting("distribution", "chart_opacity", 100),
            line_opacity=self._get_dd_widget_setting("distribution", "line_opacity", None),
            bar_gradient=self._get_dd_widget_setting("distribution", "bar_gradient", None),
            show_grid=self._get_dd_widget_setting("distribution", "show_grid", None),
            minimum_height=120,
            expanding=True,
        )

        self.dist_chart = dist_chart

        header_widget, _, _ = create_chart_header(parent=self.dialog)
        
        return dist_chart, header_widget

    def _build_card_counts_section(self, deck_identifier, period_range, row_data, target_layout=None, manual_add=False):
        """Build the Card Counts Pie Chart section."""
        current_idx = self.dialog.tab_widget.currentIndex()
        target_did = row_data.get("did")
        if target_did is None and self.dialog.view_mode != 'time':
             tab_config = self._resolve_tab_config(current_idx, None)
             target_did = tab_config.get("deck_id")
             
        is_deleted = row_data.get("is_deleted", False)
        
        # Prefer context counts, then fall back to SQL when they are missing or suspicious.
        is_skeleton = getattr(self, "_is_skeleton", False)
        ctx = getattr(self, "last_history_context", {}) or {}
        data = resolve_card_counts_payload(
            ctx,
            is_skeleton=is_skeleton,
            is_deleted=is_deleted,
            fetcher=(
                None
                if is_skeleton
                else lambda: fetch_section_data(
                    self.addon_config,
                    "card_counts",
                    deck_id=target_did,
                    is_deleted=is_deleted,
                )
            ),
        )

        if is_deleted or (not data or data.get("total", 0) <= 0) and not getattr(self, "_is_skeleton", False):
            return None, None
        
        pie_chart = PieChartWidget(data, parent=self.dialog)
        self.pie_chart = pie_chart
        apply_chart_display_config(
            pie_chart,
            opacity=self._get_dd_widget_setting("card_counts", "chart_opacity", 100),
            line_opacity=self._get_dd_widget_setting("card_counts", "line_opacity", None),
            bar_gradient=self._get_dd_widget_setting("card_counts", "bar_gradient", None),
            show_grid=self._get_dd_widget_setting("card_counts", "show_grid", None),
            minimum_height=200,
            expanding=True,
        )
        pie_chart.set_separate_suspended(self.last_pie_sep)
        pie_chart.set_show_legend(self._get_dd_widget_setting("card_counts", "show_legend", True))
        pie_chart.set_legend_mode(self._get_dd_widget_setting("card_counts", "legend_mode", "auto"))
        
        header_widget, header_lay, _ = create_chart_header(parent=self.dialog)
        
        cb_sep = self._make_styled_checkbox("Sep. Susp.", checked=self.last_pie_sep, parent=header_widget)
        def on_sep_toggled(checked):
            self.last_pie_sep = checked
            self.addon_config.set_value(Config.PIE_CHART_SEPARATE_SUSPENDED, checked)
            pie_chart.set_separate_suspended(checked)
        cb_sep.toggled.connect(on_sep_toggled)
        header_lay.addWidget(cb_sep)
        
        return pie_chart, header_widget

    def _build_heatmap_section(self, history_data, row_data, history_range, period_range, target_layout=None, manual_add=False):
        return build_heatmap_section(
            self,
            history_data,
            row_data,
            history_range,
            period_range,
            target_layout=target_layout,
            manual_add=manual_add,
        )

    def _get_or_fetch_fsrs_data(self, row_data):
        if hasattr(self, 'last_fsrs_data') and hasattr(self, 'last_fsrs_did') and self.last_fsrs_did == row_data.get("did"):
            return self.last_fsrs_data
            
        target_did = row_data.get("did")
        if target_did is None and self.dialog.view_mode != 'time':
             tab_config = self._resolve_tab_config(self.dialog.tab_widget.currentIndex(), None)
             target_did = tab_config.get("deck_id")
             
        # Fall back to the background context (opened via DeepDiveManager with a cache hit); only use it when stability is non-empty, since the FSRS job may not have completed.
        ctx = getattr(self, "last_history_context", {}) or {}
        is_skeleton = getattr(self, "_is_skeleton", False)
        is_deleted = row_data.get("is_deleted", False)
        self.last_fsrs_data = resolve_fsrs_payload(
            ctx,
            is_skeleton=is_skeleton,
            fetcher=(
                None
                if is_skeleton
                else lambda: fetch_section_data(
                    self.addon_config,
                    "fsrs",
                    deck_id=target_did,
                    is_deleted=is_deleted,
                )
            ),
            require_stability=True,
        )
        self.last_fsrs_did = row_data.get("did")
        return self.last_fsrs_data

    def _build_stability_section(self, deck_identifier, period_range, row_data, target_layout=None, manual_add=False):
        fsrs_data = self._get_or_fetch_fsrs_data(row_data)
        from ...widgets.charts.stability import StabilityChartWidget
        
        if fsrs_data is None:
            if getattr(self, "_is_skeleton", False):
                fsrs_data = {"stability": {}, "difficulty": {}, "retrievability": {}}
            else:
                fsrs_data = self._get_or_fetch_fsrs_data(row_data)
        
        stability_data = fsrs_data.get("stability", {})
        if not stability_data and not (getattr(self, "_is_skeleton", False) or self._show_empty_charts()):
            return None, None
            
        adaptive = self.dialog.addon_config.config.get(ADAPTIVE_CHART_BINNING, True)
        binning_override = self._get_dd_widget_setting("stability", "binning_override", None)
        chart = StabilityChartWidget(stability_data, parent=self.dialog, adaptive_binning=adaptive)
        chart.binning_override = binning_override
        chart.binning_toggled_callback = lambda val: self._update_dd_widget_setting("stability", "binning_override", val, refresh=False)
        chart._last_timespan_token = (
            int(period_range if period_range is not None else self.last_history_range),
            int(self._get_dd_widget_setting("stability", "custom_days", 7) or 7),
        )
        chart._last_deck_id = deck_identifier
        apply_chart_display_config(
            chart,
            opacity=self._get_dd_widget_setting("stability", "chart_opacity", 100),
            line_opacity=self._get_dd_widget_setting("stability", "line_opacity", None),
            bar_gradient=self._get_dd_widget_setting("stability", "bar_gradient", None),
            show_grid=self._get_dd_widget_setting("stability", "show_grid", None),
            minimum_height=120,
            expanding=True,
        )
        if hasattr(self, "_apply_cumulative_mode_to_chart"):
            show_cumulative = self._get_dd_widget_setting("stability", "show_cumulative", True)
            self._apply_cumulative_mode_to_chart(chart, show_cumulative)
        
        header_widget, header_lay, _, _ = create_chart_header_for_chart(
            chart,
            self.addon_config,
            Config.DEEP_DIVE_SHOW_BOTTOM_STATS,
            Config.DEEP_DIVE_SHOW_STATS,
            parent=self.dialog,
        )
        
        def on_stability_filter_applied(idx):
            self._update_dd_widget_setting("stability", "time_span_idx", idx, refresh=False)
            if hasattr(self, '_refresh_bottom_stats'):
                self._refresh_bottom_stats()
            
        fsrs_modes, _fsrs_short, fsrs_labels = resolve_fsrs_filters(
            self._get_dd_widget_setting("stability", "filter_modes", None)
        )
        default_idx, initial_mode = resolve_fsrs_filter_choice(
            self._get_dd_widget_setting("stability", "time_span_idx"), modes=fsrs_modes
        )
        chart.set_view_filter(initial_mode)
            
        radio_group = create_fsrs_filter_group(
            chart,
            labels=fsrs_labels,
            resolved_idx=default_idx,
            make_radio_group=self._make_radio_group,
            parent=header_widget,
            on_idx_applied=on_stability_filter_applied,
            modes=fsrs_modes,
            default_idx=default_fsrs_filter_idx(fsrs_modes),
        )
        header_lay.addWidget(radio_group)
        
        return chart, header_widget

    def _build_difficulty_section(self, deck_identifier, period_range, row_data, target_layout=None, manual_add=False):
        fsrs_data = self._get_or_fetch_fsrs_data(row_data)
        from ...widgets.charts.difficulty import DifficultyChartWidget
        difficulty_data = fsrs_data.get("difficulty", {})
        if not difficulty_data and not self._show_empty_charts():
            return None, None
            
        adaptive = self.addon_config.config.get(ADAPTIVE_CHART_BINNING, True)
        binning_override = self._get_dd_widget_setting("difficulty", "binning_override", None)
        chart = DifficultyChartWidget(difficulty_data, parent=self.dialog, adaptive_binning=adaptive)
        chart.binning_override = binning_override
        chart.binning_toggled_callback = lambda val: self._update_dd_widget_setting("difficulty", "binning_override", val, refresh=False)
        apply_chart_display_config(
            chart,
            opacity=self._get_dd_widget_setting("difficulty", "chart_opacity", 100),
            line_opacity=self._get_dd_widget_setting("difficulty", "line_opacity", None),
            bar_gradient=self._get_dd_widget_setting("difficulty", "bar_gradient", None),
            show_grid=self._get_dd_widget_setting("difficulty", "show_grid", None),
            minimum_height=120,
            expanding=True,
        )
        
        header_widget, _, _, _ = create_chart_header_for_chart(
            chart,
            self.addon_config,
            Config.DEEP_DIVE_SHOW_BOTTOM_STATS,
            Config.DEEP_DIVE_SHOW_STATS,
            parent=self.dialog,
        )
        
        return chart, header_widget

    def _build_retrievability_section(self, deck_identifier, period_range, row_data, target_layout=None, manual_add=False):
        fsrs_data = self._get_or_fetch_fsrs_data(row_data)
        from ...widgets.charts.retrievability import RetrievabilityChartWidget
        retrievability_data = fsrs_data.get("retrievability", {})
        if not retrievability_data and not self._show_empty_charts():
            return None, None
            
        adaptive = self.addon_config.config.get(ADAPTIVE_CHART_BINNING, True)
        binning_override = self._get_dd_widget_setting("retrievability", "binning_override", None)
        chart = RetrievabilityChartWidget(retrievability_data, parent=self.dialog, adaptive_binning=adaptive)
        chart.binning_override = binning_override
        chart.binning_toggled_callback = lambda val: self._update_dd_widget_setting("retrievability", "binning_override", val, refresh=False)
        apply_chart_display_config(
            chart,
            opacity=self._get_dd_widget_setting("retrievability", "chart_opacity", 100),
            line_opacity=self._get_dd_widget_setting("retrievability", "line_opacity", None),
            bar_gradient=self._get_dd_widget_setting("retrievability", "bar_gradient", None),
            show_grid=self._get_dd_widget_setting("retrievability", "show_grid", None),
            minimum_height=120,
            expanding=True,
        )
        
        header_widget, _, _, _ = create_chart_header_for_chart(
            chart,
            self.addon_config,
            Config.DEEP_DIVE_SHOW_BOTTOM_STATS,
            Config.DEEP_DIVE_SHOW_STATS,
            parent=self.dialog,
        )
        
        return chart, header_widget

    def _build_hourly_section(self, deck_identifier, period_range, row_data, target_layout=None, manual_add=False):
        return build_hourly_section(
            self,
            deck_identifier,
            period_range,
            row_data,
            target_layout=target_layout,
            manual_add=manual_add,
        )

    def _build_future_due_section(self, deck_identifier, period_range, row_data, target_layout=None, manual_add=False):
        return build_future_due_section(
            self,
            deck_identifier,
            period_range,
            row_data,
            target_layout=target_layout,
            manual_add=manual_add,
        )

    def _build_review_intervals_section(self, deck_identifier, period_range, row_data, target_layout=None, manual_add=False):
        return build_review_intervals_section(
            self,
            deck_identifier,
            period_range,
            row_data,
            target_layout=target_layout,
            manual_add=manual_add,
        )

    def on_heatmap_day_clicked(self, date_str, did=None):
        """Find cards reviewed on a specific date asynchronously and show them in the Browser."""
        from ...logic.interactions import HeatmapInteractions
        HeatmapInteractions.open_browser_for_date(date_str, did)





