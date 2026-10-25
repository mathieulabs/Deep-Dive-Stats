# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt import mw
from aqt.qt import QAction
from .. import Config
from ..shared.menu import StyledMenu
from ..shared.heatmap_menu import add_heatmap_display_actions, apply_heatmap_display
from ..theme.icons import get_svg_icon
from ...widgets.pinned import WidgetRegistry
from ...widgets.pinned.main_menu.manager import MainMenuWidgetManager
from ...logic.logger import log_swallowed

class DeepDiveContextMenu:
    def __init__(self, manager):
        self.manager = manager

    def show(self, widget, section_key, pos):
        menu = StyledMenu(widget)
        from ...widgets.common.fullscreen import close_fullscreen, is_fullscreen

        if is_fullscreen(widget):
            fs_action = QAction("Exit Fullscreen", menu)
            fs_action.triggered.connect(lambda _=False, w=widget: close_fullscreen(w))
        else:
            fs_action = QAction("Fullscreen", menu)
            fs_action.triggered.connect(lambda _=False, w=widget: self._open_fullscreen(w))
        fs_action.setIcon(get_svg_icon("maximize", size=16, context_ref=menu))
        fs_action.setEnabled(not bool(getattr(widget, "is_collapsed", False)))
        menu.addAction(fs_action)
        menu.addSeparator()

        settings_action = QAction("Settings", menu)
        settings_action.setIcon(get_svg_icon("settings", size=16, context_ref=menu))
        settings_action.triggered.connect(lambda: self.manager._open_dd_widget_settings(section_key, widget))
        menu.addAction(settings_action)
        menu.addSeparator()

        avg_sections = ["activity", "added", "retention"]
        cumulative_sections = ["activity", "added", "hourly", "future_due", "review_intervals", "stability"]

        if section_key in avg_sections:
            menu.addSeparator()

            show_avg = self.manager._get_dd_widget_setting(section_key, "show_average", True)
            avg_act = QAction("Show Average", menu)
            avg_act.setCheckable(True)
            avg_act.setChecked(show_avg)
            avg_act.triggered.connect(lambda checked:
                self.manager._update_dd_widget_setting(section_key, "show_average", checked))
            menu.addAction(avg_act)

            avg_active = self.manager._get_dd_widget_setting(section_key, "avg_on_active_days", True)
            avg_active_act = QAction("Average on Active Days", menu)
            avg_active_act.setCheckable(True)
            avg_active_act.setChecked(avg_active)
            avg_active_act.triggered.connect(lambda checked:
                self.manager._update_dd_widget_setting(section_key, "avg_on_active_days", checked))
            menu.addAction(avg_active_act)

            if section_key == "retention":
                fit = self.manager._get_dd_widget_setting(section_key, "fit_to_data", False)
                fit_act = QAction("Within data limit", menu)
                fit_act.setCheckable(True)
                fit_act.setChecked(bool(fit))
                fit_act.triggered.connect(lambda checked:
                    self.manager._update_dd_widget_setting("retention", "fit_to_data", checked))
                menu.addAction(fit_act)

                bars_on = self.manager._get_dd_widget_setting(section_key, "review_bars", True)
                bars_menu = menu.addMenu("Review Bars")
                bars_act = QAction("Show Bars", bars_menu)
                bars_act.setCheckable(True)
                bars_act.setChecked(bool(bars_on))
                bars_act.triggered.connect(lambda checked:
                    self.manager._update_dd_widget_setting("retention", "review_bars", checked))
                bars_menu.addAction(bars_act)

                axis_act = QAction("Show Count Axis", bars_menu)
                axis_act.setCheckable(True)
                axis_act.setChecked(bool(self.manager._get_dd_widget_setting(section_key, "review_axis", False)))
                axis_act.setEnabled(bool(bars_on))
                axis_act.triggered.connect(lambda checked:
                    self.manager._update_dd_widget_setting("retention", "review_axis", checked))
                bars_menu.addAction(axis_act)

                round_act = QAction("Rounded Look", menu)
                round_act.setCheckable(True)
                round_act.setChecked(bool(self.manager._get_dd_widget_setting(section_key, "rounded", True)))
                round_act.setToolTip("Smooth lines and rounded bar tops")
                round_act.triggered.connect(lambda checked:
                    self.manager._update_dd_widget_setting("retention", "rounded", checked))
                menu.addAction(round_act)

                current_min = int(self.manager._get_dd_widget_setting(section_key, "min_reviews", 0) or 0)
                min_act = QAction(f"Min Reviews per Point: {current_min if current_min else 'Off'}...", menu)

                def _ask_min(_=False, current=current_min, parent=widget):
                    from ..shared.number_dialog import ask_number

                    value = ask_number(
                        "Min Reviews",
                        "Hide points with fewer reviews than this (0 = show all):",
                        current,
                        parent=parent,
                    )
                    if value is not None:
                        self.manager._update_dd_widget_setting("retention", "min_reviews", value)

                min_act.triggered.connect(_ask_min)
                menu.addAction(min_act)

            if section_key == "added":
                is_synced = self.manager._get_dd_widget_setting("added", "sync_zoom", True)
                sync_act = QAction("Sync with other charts", menu)
                sync_act.setCheckable(True)
                sync_act.setChecked(is_synced)
                sync_act.triggered.connect(lambda checked:
                    self.manager._update_dd_widget_setting("added", "sync_zoom", checked))
                menu.addAction(sync_act)

        if section_key == "activity":
            from ..shared.review_types_menu import add_review_type_actions

            add_review_type_actions(
                menu,
                self.manager._get_dd_widget_setting("activity", "hidden_review_types", None),
                lambda hidden: self.manager._update_dd_widget_setting("activity", "hidden_review_types", hidden),
            )

        if section_key in cumulative_sections:
            if section_key not in avg_sections:
                menu.addSeparator()
            show_total = self.manager._get_dd_widget_setting(section_key, "show_cumulative", True)
            total_act = QAction("Show Right Axis", menu)
            total_act.setCheckable(True)
            total_act.setChecked(show_total)
            total_act.triggered.connect(lambda checked:
                self.manager._update_dd_widget_setting(section_key, "show_cumulative", checked))
            menu.addAction(total_act)

        binning_charts = ["activity", "added", "retention", "future_due", "review_intervals", "stability", "difficulty", "retrievability"]
        if section_key in binning_charts:
            from .. import ADAPTIVE_CHART_BINNING
            global_binning = self.manager.addon_config.config.get(ADAPTIVE_CHART_BINNING, True)
            binning_override = self.manager._get_dd_widget_setting(section_key, "binning_override", None)
            effective_binning = binning_override if binning_override is not None else global_binning

            binning_act = QAction("Adaptive Binning", menu)
            binning_act.setCheckable(True)
            binning_act.setChecked(effective_binning)
            binning_act.triggered.connect(lambda checked:
                self.manager._update_dd_widget_setting(section_key, "binning_override", checked))
            menu.addAction(binning_act)

        if section_key in ["activity", "added", "retention", "hourly", "future_due", "review_intervals", "stability", "difficulty", "retrievability"]:
            menu.addSeparator()
            show_bottom_stats = self.manager.addon_config.config.get(Config.DEEP_DIVE_SHOW_BOTTOM_STATS, False)
            bottom_stats_act = QAction("Show Bottom Stats (All Charts)", menu)
            bottom_stats_act.setCheckable(True)
            bottom_stats_act.setChecked(show_bottom_stats)
            bottom_stats_act.triggered.connect(lambda checked:
                self.manager._toggle_global_bottom_stats(checked))
            menu.addAction(bottom_stats_act)

            show_all_stats = self.manager.addon_config.config.get(Config.DEEP_DIVE_SHOW_STATS, True)
            all_stats_act = QAction("Show Stats (All Charts)", menu)
            all_stats_act.setCheckable(True)
            all_stats_act.setChecked(show_all_stats)
            all_stats_act.triggered.connect(lambda checked:
                self.manager._toggle_global_show_stats(checked))
            menu.addAction(all_stats_act)

        menu.addSeparator()

        _type_map = {
            "activity": "activity",
            "retention": "retention",
            "added": "added",
            "distribution": "distribution",
            "card_counts": "card_counts",
            "heatmap": "heatmap",
            "hourly": "hourly",
            "future_due": "future_due",
            "review_intervals": "review_intervals",
            "stability": "stability",
            "difficulty": "difficulty",
            "retrievability": "retrievability",
        }
        stype = _type_map.get(section_key)

        if stype:
            ctx_span = int(self.manager.last_history_range)
            label_text = section_key.replace("_", " ").title()

            act = QAction(f"Pin {label_text} to main menu", menu)
            act.setIcon(get_svg_icon("push-pin", size=16, context_ref=menu))
            act.triggered.connect(lambda: self._pin_section(stype, label_text, None, ctx_span))
            menu.addAction(act)

        if section_key == "heatmap":
            menu.addSeparator()
            multi_hue = self.manager.addon_config.config.get(Config.HEATMAP_MULTI_HUE_INTENSITY, False)
            multi_hue_act = QAction("Multicolor Intensity", menu)
            multi_hue_act.setCheckable(True)
            multi_hue_act.setChecked(multi_hue)

            def on_multi_hue_toggled(checked):
                self.manager.addon_config.set_value(Config.HEATMAP_MULTI_HUE_INTENSITY, checked)
                hm = getattr(self.manager, "heatmap_chart", None)
                if hm and hasattr(hm, "set_multi_hue_intensity"):
                    hm.set_multi_hue_intensity(checked)
                # Keep pinned heatmaps aligned with the same global option.
                try:
                    _pm = MainMenuWidgetManager.instance()
                    _pcm = getattr(_pm, "_config_manager", None)
                    if _pcm is not None and _pcm.config is not self.manager.addon_config.config:
                        _pcm.config[Config.HEATMAP_MULTI_HUE_INTENSITY] = checked
                    _pm.refresh(clear_cache=False)
                except Exception:
                    log_swallowed()

            multi_hue_act.triggered.connect(on_multi_hue_toggled)
            menu.addAction(multi_hue_act)

            def on_display_changed(key, value):
                self.manager.addon_config.set_value(key, value)
                apply_heatmap_display(getattr(self.manager, "heatmap_chart", None), key, value)
                try:
                    _pm = MainMenuWidgetManager.instance()
                    _pcm = getattr(_pm, "_config_manager", None)
                    if _pcm is not None and _pcm.config is not self.manager.addon_config.config:
                        _pcm.config[key] = value
                    _pm.refresh(clear_cache=False)
                except Exception:
                    log_swallowed()

            add_heatmap_display_actions(menu, self.manager.addon_config.config, on_display_changed)

        has_h = self.manager._get_dd_widget_setting(section_key, "height") is not None
        has_span = int(self.manager._get_dd_widget_setting(section_key, "col_span", 1)) > 1
        if has_h or has_span:
            menu.addSeparator()
            reset_act = QAction("Reset Size", menu)
            reset_act.setIcon(get_svg_icon("rotate-ccw", size=16, context_ref=menu))
            reset_act.triggered.connect(lambda: self.manager._reset_dd_widget_size(section_key))
            menu.addAction(reset_act)

        from ..shared.zoom_span import create_span_from_zoom, find_zoomed_chart

        zoomed = find_zoomed_chart(widget)
        if zoomed is not None:
            menu.addSeparator()
            zoom_act = QAction("Set zoom as time span", menu)
            zoom_act.setIcon(get_svg_icon("calendar", size=16, context_ref=menu))

            def _apply_zoom_span(_=False, chart=zoomed):
                mgr = self.manager
                code = create_span_from_zoom(chart, mgr.addon_config, parent=widget)
                if code is not None:
                    mgr.open_deep_dive(
                        getattr(mgr, "last_deck_identifier", None),
                        getattr(mgr, "last_title", "Details"),
                        period_range=code,
                    )

            zoom_act.triggered.connect(_apply_zoom_span)
            menu.addAction(zoom_act)

        menu.exec(widget.mapToGlobal(pos))

    def _open_fullscreen(self, widget):
        from ...widgets.common.fullscreen import open_fullscreen

        def _on_closed(card, placed):
            if card is not None and not placed:
                # The grid was rebuilt while fullscreen: this card is no longer used.
                card.deleteLater()
                return
            grid = getattr(self.manager, "current_grid_layout", None)
            if grid is not None:
                try:
                    grid.invalidate()
                except Exception:
                    log_swallowed()

        open_fullscreen(widget, on_closed=_on_closed)

    def _pin_section(self, stype, slabel, did, span):
        extras = []
        if did is not None:
             deck = mw.col.decks.get(did)
             if deck: extras.append(deck['name'])
        final_label = slabel
        if extras:
            final_label = f"{slabel} ({', '.join(extras)})"
        WidgetRegistry.add(stype, final_label, deck_id=did, time_span=span)
        MainMenuWidgetManager.instance().refresh()

