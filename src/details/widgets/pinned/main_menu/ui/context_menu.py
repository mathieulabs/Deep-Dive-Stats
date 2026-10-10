# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors

from aqt import mw
from aqt.qt import QAction, Qt, QTimer, QWidget, QWidgetAction, QSizePolicy, QHBoxLayout, QPushButton

from ..imports import Config, Period
from ..imports import ConfigManager
from ..block_order import (
    BLOCK_CHARTS,
    BLOCK_STATS,
    BLOCK_TEXTS,
    block_for_widget,
    charts_section_key,
    normalize_block_order,
    parse_section_key,
    section_label,
    stats_section_key,
    texts_section_key,
)
from ... import DeckMultiSelectDialog, PinnedViewSelectorDialog, WidgetRegistry
from .....ui import StyledMenu, get_svg_icon
from ......qss import set_qss
from .....logic.logger import log_swallowed


class PinnedContextMenu:
    def __init__(self, manager):
        self.manager = manager

    def _add_persistent_action(self, menu, text, callback):
        row = QWidget(menu)
        row.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        row.setMinimumWidth(max(220, menu.sizeHint().width()))
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        btn = QPushButton(text, row)
        btn.setFlat(True)
        btn.setText(text)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        btn.setMinimumHeight(30)
        set_qss(btn, 
            "QPushButton {"
            " text-align: left;"
            " padding: 4px 8px 4px 24px;"
            " border: none;"
            " background: transparent;"
            "}"
            "QPushButton:hover { background: rgba(255,255,255,0.08); }"
            "QPushButton:pressed { background: rgba(255,255,255,0.14); }"
        )
        btn.clicked.connect(callback)
        lay.addWidget(btn)

        wa = QWidgetAction(menu)
        wa.setDefaultWidget(row)
        menu.addAction(wa)

    def _open_fullscreen(self, widget):
        from ....common.fullscreen import open_fullscreen

        manager = self.manager

        def _on_closed(card, placed):
            try:
                if not placed and card is not None:
                    # Its row was rebuilt meanwhile: let a rebuild attach it again.
                    manager._last_state = None
                    manager.refresh(clear_cache=False)
                manager.sync_overlay()
            except Exception:
                log_swallowed()

        open_fullscreen(widget, on_closed=_on_closed)

    def _get_widget_def_by_id(self, wid):
        for d in WidgetRegistry.get_all():
            if d.get("id") == wid:
                return d
        return None

    def _add_text_label_widget(self, parent_widget):
        """Open a themed dialog to create a new text_label pinned widget."""
        from aqt.qt import QDialog, QVBoxLayout, QHBoxLayout, QPushButton
        from aqt.theme import theme_manager
        from .....ui.theme import get_settings_dialog_style
        from .....ui.config.widgets.text_label_editor import TextLabelEditor
        from .....ui.config.shared import clamp_dialog_width

        dlg = QDialog(parent_widget)
        dlg.setWindowTitle("Add Text Widget")
        dlg.setMinimumWidth(500)

        cfg = {}
        try:
            cfg = (self.manager._config_manager.config or {}) if getattr(self.manager, "_config_manager", None) else {}
            from ....chart_utils.theme import ThemeContext, get_context_theme_config

            cfg = get_context_theme_config(ThemeContext.PINNED, cfg)
            set_qss(dlg, get_settings_dialog_style(bool(theme_manager.get_night_mode()), cfg))
        except Exception:
            log_swallowed()

        layout = QVBoxLayout(dlg)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 16)

        tl_editor = TextLabelEditor(dlg, theme_config=cfg)
        layout.addWidget(tl_editor)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        ok_btn = QPushButton("Add")
        ok_btn.setDefault(True)
        cancel_btn.clicked.connect(dlg.reject)
        ok_btn.clicked.connect(dlg.accept)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)

        from aqt.qt import QCoreApplication
        QCoreApplication.processEvents()
        wanted_w = max(dlg.minimumWidth(), dlg.sizeHint().width() + 24)
        dlg.resize(clamp_dialog_width(wanted_w, min_width=500), dlg.sizeHint().height())

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        template = tl_editor.get_template().strip()
        WidgetRegistry.add("text_label", "Text Widget", template=template)
        self.manager._last_state = None
        self.manager._last_widget_set = None
        self.manager.refresh()

    def _open_details_for_widget(self, widget_def):
        """Open the Deep Dive on the deck(s) and period this widget shows."""
        try:
            from ...widget_factory.factory import _resolve_deck_ids

            context_deck = getattr(self.manager, "_current_deck_id", None)
            if "deck_ids" in widget_def:
                deck = _resolve_deck_ids(widget_def["deck_ids"], context_deck)
            elif "deck_id" in widget_def:
                deck = widget_def["deck_id"]
            else:
                deck = context_deck
            if isinstance(deck, str):
                deck = None
            span = self.manager._normalized_widget_def(widget_def).get("time_span")
            if span == Period.CUSTOM or widget_def.get("type") == "text_label":
                span = None
            from ......startup import open_details_for

            open_details_for(deck, span)
        except Exception:
            log_swallowed()

    def show(self, widget, widget_def, pos, *, fixed_global_pos=None, reopen_position_menu=False):
        for d in WidgetRegistry.get_all():
            if d.get("id") == widget_def.get("id"):
                widget_def = d
                break
        cfg = (self.manager._config_manager.config or {}) if getattr(self.manager, "_config_manager", None) else {}

        def _nonneg_int(value, default=0):
            try:
                return max(0, int(value or 0))
            except Exception:
                return int(default)

        def _collect_boxes_from_defs(defs):
            stat_boxes = sorted(
                {
                    _nonneg_int(d.get("stat_box", 0), 0)
                    for d in defs
                    if d.get("type") == "stat_card"
                }
            )
            chart_boxes = sorted(
                {
                    _nonneg_int(d.get("chart_box", 0), 0)
                    for d in defs
                    if d.get("type") not in ("stat_card", "text_label")
                }
            )
            text_boxes = sorted(
                {
                    _nonneg_int(d.get("text_box", d.get("chart_box", 0)), 0)
                    for d in defs
                    if d.get("type") == "text_label"
                }
            )
            return stat_boxes, chart_boxes, text_boxes

        def _live_section_order(defs):
            live_cfg = (self.manager._config_manager.config or {})
            stat_boxes, chart_boxes, text_boxes = _collect_boxes_from_defs(defs)
            return normalize_block_order(
                live_cfg.get(Config.PINNED_BLOCK_ORDER, None),
                stats_boxes=stat_boxes,
                chart_boxes=chart_boxes,
                text_boxes=text_boxes,
            )

        def _write_config_value(key, value):
            cm = getattr(self.manager, "_config_manager", None)
            if cm is not None and hasattr(cm, "set_value"):
                cm.set_value(key, value)
                return
            ConfigManager(mw).set_value(key, value)

        menu = StyledMenu(widget)
        global_pos = fixed_global_pos if fixed_global_pos is not None else widget.mapToGlobal(pos)
        menu.setProperty("deepdivestats_theme_context", "pinned")
        menu.setProperty("deepdivestats_ignore_forced_dark_theme", True)
        menu.setProperty("deepdivestats_config_override", dict(cfg))
        try:
            menu._apply_theme_style()
        except Exception:
            log_swallowed()

        def _refresh_and_reopen_menu(reopen_position=False):
            self.manager._last_state = None
            self.manager._last_widget_set = None
            self.manager.refresh(clear_cache=False)

            def _reopen():
                try:
                    if widget is None:
                        return
                    latest = self._get_widget_def_by_id(widget_def.get("id")) or widget_def
                    local_pos = widget.mapFromGlobal(global_pos)
                    self.show(
                        widget,
                        latest,
                        local_pos,
                        fixed_global_pos=global_pos,
                        reopen_position_menu=bool(reopen_position),
                    )
                except Exception:
                    log_swallowed()

            try:
                menu.close()
            except Exception:
                log_swallowed()
            QTimer.singleShot(0, _reopen)

        position_menu = None
        
        details_action = QAction("Open Details Window", menu)
        details_action.setIcon(get_svg_icon("external-link", size=16, context_ref=menu))
        details_action.triggered.connect(lambda _=False, wd=widget_def: self._open_details_for_widget(wd))
        menu.addAction(details_action)

        if widget_def.get("type") not in ("stat_card", "text_label"):
            from ....common.fullscreen import close_fullscreen, is_fullscreen

            if is_fullscreen(widget):
                fs_action = QAction("Exit Fullscreen", menu)
                fs_action.triggered.connect(lambda _=False, w=widget: close_fullscreen(w))
            else:
                fs_action = QAction("Fullscreen", menu)
                fs_action.triggered.connect(lambda _=False, w=widget: self._open_fullscreen(w))
            fs_action.setIcon(get_svg_icon("maximize", size=16, context_ref=menu))
            menu.addAction(fs_action)

        from .edit_mode import is_edit_mode, set_edit_mode

        _edit_act = QAction("Edit layout", menu)
        _edit_act.setCheckable(True)
        _edit_act.setChecked(is_edit_mode(self.manager))
        _edit_act.triggered.connect(lambda checked: set_edit_mode(self.manager, bool(checked)))
        menu.addAction(_edit_act)
        from .add_widget_menu import add_widget_actions

        add_widget_actions(
            menu,
            self.manager,
            lambda: self._add_text_label_widget(widget),
            icon_fn=lambda name: get_svg_icon(name, size=16, context_ref=menu),
        )

        menu.addSeparator()
        settings_action = QAction("Settings", menu)
        settings_action.setIcon(get_svg_icon("settings", size=16, context_ref=menu))
        settings_action.triggered.connect(lambda: self.manager._open_widget_settings(widget, widget_def))
        menu.addAction(settings_action)
        
        menu.addSeparator()
        
        no_span_types = [
            "card_counts", "heatmap", "future_due", "review_intervals",
            "stability", "difficulty", "retrievability"
        ]
        is_streak = widget_def.get("stat_key") in [Config.DASH_SHOW_STREAK, Config.DEEP_DIVE_SHOW_STREAK]
        
        if widget_def.get("type") not in no_span_types and not is_streak:
            span_menu = menu.addMenu("Time Span")
            span_menu.setIcon(get_svg_icon("calendar", size=16, context_ref=menu))
            
            from .....ui.shared.span_menu import populate_span_menu
            
            current_span = widget_def.get("time_span", Period.TOTAL)
            current_days = widget_def.get("custom_days", None)
            
            def on_update_span(v, d=None):
                updates = {"time_span": v}
                if d is not None:
                    updates["custom_days"] = d
                
                if hasattr(self.manager, "_update_span_bulk"):
                    self.manager._update_span_bulk(widget_def["id"], updates)
                else:
                    self.manager._update_span(widget_def["id"], v)

            from .....ui.shared.zoom_span import create_span_from_zoom, find_zoomed_chart

            zoomed = find_zoomed_chart(widget)

            def on_zoom_span(chart=zoomed):
                code = create_span_from_zoom(chart, self.manager._config_manager, parent=widget)
                if code is not None:
                    self.manager._update_span_bulk(widget_def["id"], {"time_span": code})

            populate_span_menu(
                span_menu,
                current_span,
                current_days,
                on_update_span,
                self.manager._config_manager,
                on_manage_callback=self.manager._open_time_span_settings,
                on_zoom_callback=on_zoom_span if zoomed is not None else None,
            )

        try:
            from ... import zoom_link

            if zoom_link.has_charts(widget):
                linked_n, off_n = zoom_link.counts(self.manager)
                mine = zoom_link.is_linked(widget)
                z_act = QAction("Disconnect zoom" if mine else "Reconnect zoom", menu)
                z_act.setIcon(get_svg_icon("zoom-in", size=16, context_ref=menu))
                z_act.triggered.connect(lambda _=False, w=widget, v=not mine: zoom_link.set_linked(w, v))
                menu.addAction(z_act)
                if linked_n + off_n >= 2:
                    if linked_n >= 2 or (linked_n == 1 and not mine):
                        a = QAction("Disconnect all charts' zoom", menu)
                        a.triggered.connect(lambda _=False: zoom_link.set_all_linked(self.manager, False))
                        menu.addAction(a)
                    if off_n:
                        a = QAction("Reconnect all charts' zoom", menu)
                        a.triggered.connect(lambda _=False: zoom_link.set_all_linked(self.manager, True))
                        menu.addAction(a)
        except Exception:
            log_swallowed()

        deck_act = QAction("Select Decks...", menu)
        deck_act.setIcon(get_svg_icon("layers", size=16, context_ref=menu))

        def on_deck_multi_select():
            current_deck_ids = widget_def.get("deck_ids", None)
            if current_deck_ids is None and "deck_id" in widget_def:
                old_did = widget_def["deck_id"]
                if old_did is None or old_did == 0 or str(old_did) == "0":
                    current_deck_ids = None  # all/adaptive: default all checked
                else:
                    current_deck_ids = [int(old_did)]
            dialog = DeckMultiSelectDialog(current_deck_ids, parent=widget)
            if dialog.exec():
                new_deck_ids = dialog.selected_deck_ids
                WidgetRegistry.update_settings_bulk(widget_def["id"], {
                    "deck_ids": new_deck_ids,
                    "deck_id": None,
                })
                self.manager.refresh()

        deck_act.triggered.connect(on_deck_multi_select)
        menu.addAction(deck_act)

        view_act = QAction("View...", menu)
        view_act.setIcon(get_svg_icon("eye", size=16, context_ref=menu))

        def on_view_select():
            current_view = widget_def.get("view_dids", None)
            dialog = PinnedViewSelectorDialog(current_view, parent=widget)
            if dialog.exec():
                WidgetRegistry.update_setting(widget_def["id"], "view_dids", dialog.selected_values)
                self.manager.refresh()

        view_act.triggered.connect(on_view_select)
        menu.addAction(view_act)

        wtype = widget_def.get("type")
        avg_sections = ["activity", "added", "retention"]
        cumulative_sections = ["activity", "added", "future_due", "review_intervals", "stability"]

        if wtype in set(avg_sections + cumulative_sections):
            menu.addSeparator()

            if wtype in avg_sections:
                show_avg = widget_def.get("show_average", True)
                avg_act = QAction("Show Average", menu)
                avg_act.setCheckable(True)
                avg_act.setChecked(show_avg)
                avg_act.triggered.connect(lambda checked, wid=widget_def["id"]:
                    self.manager._update_setting(wid, "show_average", checked))
                menu.addAction(avg_act)

                show_active = widget_def.get("avg_on_active_days", True)
                active_act = QAction("Average on active days", menu)
                active_act.setCheckable(True)
                active_act.setChecked(show_active)
                active_act.triggered.connect(lambda checked, wid=widget_def["id"]:
                    self.manager._update_setting(wid, "avg_on_active_days", checked))
                menu.addAction(active_act)

                if wtype == "retention":
                    fit = bool(widget_def.get("fit_to_data", False))
                    fit_act = QAction("Within data limit", menu)
                    fit_act.setCheckable(True)
                    fit_act.setChecked(fit)
                    fit_act.triggered.connect(lambda checked, wid=widget_def["id"]:
                        self.manager._update_setting(wid, "fit_to_data", checked))
                    menu.addAction(fit_act)

                    bars_menu = menu.addMenu("Review Bars")
                    bars_act = QAction("Show Bars", bars_menu)
                    bars_act.setCheckable(True)
                    bars_act.setChecked(bool(widget_def.get("review_bars", True)))
                    bars_act.triggered.connect(lambda checked, wid=widget_def["id"]:
                        self.manager._update_setting(wid, "review_bars", checked))
                    bars_menu.addAction(bars_act)

                    axis_act = QAction("Show Count Axis", bars_menu)
                    axis_act.setCheckable(True)
                    axis_act.setChecked(bool(widget_def.get("review_axis", False)))
                    axis_act.setEnabled(bool(widget_def.get("review_bars", True)))
                    axis_act.triggered.connect(lambda checked, wid=widget_def["id"]:
                        self.manager._update_setting(wid, "review_axis", checked))
                    bars_menu.addAction(axis_act)

                    round_act = QAction("Rounded Look", menu)
                    round_act.setCheckable(True)
                    round_act.setChecked(bool(widget_def.get("rounded", True)))
                    round_act.setToolTip("Smooth lines and rounded bar tops")
                    round_act.triggered.connect(lambda checked, wid=widget_def["id"]:
                        self.manager._update_setting(wid, "rounded", checked))
                    menu.addAction(round_act)

                    current_min = int(widget_def.get("min_reviews", 0) or 0)
                    min_act = QAction(f"Min Reviews per Point: {current_min if current_min else 'Off'}...", menu)

                    def _ask_min(_=False, current=current_min, wid=widget_def["id"], parent=widget):
                        from .....ui.shared.number_dialog import ask_number

                        value = ask_number(
                            "Min Reviews",
                            "Hide points with fewer reviews than this (0 = show all):",
                            current,
                            parent=parent,
                        )
                        if value is not None:
                            self.manager._update_setting(wid, "min_reviews", value)

                    min_act.triggered.connect(_ask_min)
                    menu.addAction(min_act)

            if wtype == "activity":
                from .....ui.shared.review_types_menu import add_review_type_actions

                add_review_type_actions(
                    menu,
                    widget_def.get("hidden_review_types"),
                    lambda hidden, wid=widget_def["id"]: self.manager._update_setting(
                        wid, "hidden_review_types", hidden or None
                    ),
                )

            if wtype in cumulative_sections:
                show_total = widget_def.get("show_cumulative", True)
                total_act = QAction("Show Total (Cumulative)", menu)
                total_act.setCheckable(True)
                total_act.setChecked(show_total)
                total_act.triggered.connect(lambda checked, wid=widget_def["id"]:
                    self.manager._update_setting(wid, "show_cumulative", checked))
                menu.addAction(total_act)

        if wtype == "heatmap":
            menu.addSeparator()
            multi_hue = cfg.get(Config.HEATMAP_MULTI_HUE_INTENSITY, False)

            multi_hue_act = QAction("Multicolor Intensity", menu)
            multi_hue_act.setCheckable(True)
            multi_hue_act.setChecked(multi_hue)

            def on_multi_hue_toggled(checked):
                _write_config_value(Config.HEATMAP_MULTI_HUE_INTENSITY, checked)
                from ....charts.heatmap import HeatmapWidget
                hm = widget.findChild(HeatmapWidget)
                if hm:
                    hm.set_multi_hue_intensity(checked)
                # Keep all pinned heatmaps in sync with the global setting.
                self.manager.refresh(clear_cache=False)

            multi_hue_act.triggered.connect(on_multi_hue_toggled)
            menu.addAction(multi_hue_act)

            def on_display_changed(key, value):
                _write_config_value(key, value)
                from ....charts.heatmap import HeatmapWidget
                from .....ui.shared.heatmap_menu import apply_heatmap_display
                apply_heatmap_display(widget.findChild(HeatmapWidget), key, value)
                self.manager.refresh(clear_cache=False)

            from .....ui.shared.heatmap_menu import add_heatmap_display_actions
            add_heatmap_display_actions(menu, cfg, on_display_changed)
        
        wtype_stats = ["activity", "added", "hourly", "future_due", "review_intervals", "stability", "difficulty", "retrievability", "retention"]
        if wtype in wtype_stats:
            menu.addSeparator()
            global_show_bottom_stats = self.manager._config_manager.config.get(Config.DEEP_DIVE_PINNED_SHOW_BOTTOM_STATS, False)
            bottom_stats_act = QAction("Show Bottom Stats (Global)", menu)
            bottom_stats_act.setCheckable(True)
            bottom_stats_act.setChecked(global_show_bottom_stats)
            bottom_stats_act.triggered.connect(self.manager._toggle_global_bottom_stats)
            menu.addAction(bottom_stats_act)
            
            global_show_all_stats = self.manager._config_manager.config.get(Config.DEEP_DIVE_PINNED_SHOW_STATS, True)
            all_stats_act = QAction("Show Stats (Global)", menu)
            all_stats_act.setCheckable(True)
            all_stats_act.setChecked(global_show_all_stats)
            all_stats_act.triggered.connect(self.manager._toggle_global_show_stats)
            menu.addAction(all_stats_act)

        wtype_binning = ["activity", "added", "retention", "future_due", "review_intervals", "stability", "difficulty", "retrievability"]
        if wtype in wtype_binning:
            menu.addSeparator()
            
            from ..imports import Config as _Cfg
            global_binning = self.manager._config_manager.config.get(_Cfg.ADAPTIVE_CHART_BINNING, True)
            binning_override = widget_def.get("binning_override", None)
            effective_binning = binning_override if binning_override is not None else global_binning
            
            binning_act = QAction("Adaptive Binning", menu)
            binning_act.setCheckable(True)
            binning_act.setChecked(effective_binning)
            binning_act.triggered.connect(lambda checked, wid=widget_def["id"]:
                self.manager._update_setting(wid, "binning_override", checked))
            menu.addAction(binning_act)


        # Row break option, only for chart widgets (stat cards expose it through StatCardsContainer's own context menu).
        _wtype = widget_def.get("type")
        menu.addSeparator()
        position_menu = menu.addMenu("Position")

        def _do_down(_=None, wid=widget_def["id"]):
            cur = self._get_widget_def_by_id(wid) or {}
            rn = int(cur.get("row_num", 0) or 0)
            WidgetRegistry.update_setting(wid, "row_num", rn + 1)
            _refresh_and_reopen_menu(reopen_position=True)

        def _do_up(_=None, wid=widget_def["id"]):
            cur = self._get_widget_def_by_id(wid) or {}
            rn = int(cur.get("row_num", 0) or 0)
            new_rn = max(0, rn - 1)
            WidgetRegistry.update_setting(wid, "row_num", new_rn if new_rn > 0 else None)
            _refresh_and_reopen_menu(reopen_position=True)

        def _do_shift_right(_=None, wid=widget_def["id"]):
            cur = self._get_widget_def_by_id(wid) or {}
            co = int(cur.get("col_offset", 0) or 0)
            new_co = co + 1
            WidgetRegistry.update_setting(wid, "col_offset", None if new_co == 0 else new_co)
            try:
                live = self.manager._active_widgets.get(wid)
                if live is not None:
                    live._col_offset = int(new_co)
                    # Enable move animations before relayout so the card glides.
                    self.manager._schedule_chart_reflow_animation()
                    p = live.parentWidget()
                    if p is not None and p.layout() is not None:
                        p.layout().invalidate()
                        p.layout().activate()
                        p.updateGeometry()
                        p.update()
                    self.manager.sync_overlay()
            except Exception:
                log_swallowed()
            _refresh_and_reopen_menu(reopen_position=True)

        def _do_shift_left(_=None, wid=widget_def["id"]):
            cur = self._get_widget_def_by_id(wid) or {}
            co = int(cur.get("col_offset", 0) or 0)
            new_co = co - 1
            WidgetRegistry.update_setting(wid, "col_offset", None if new_co == 0 else new_co)
            try:
                live = self.manager._active_widgets.get(wid)
                if live is not None:
                    live._col_offset = int(new_co)
                    # Enable move animations before relayout so the card glides.
                    self.manager._schedule_chart_reflow_animation()
                    p = live.parentWidget()
                    if p is not None and p.layout() is not None:
                        p.layout().invalidate()
                        p.layout().activate()
                        p.updateGeometry()
                        p.update()
                    self.manager.sync_overlay()
            except Exception:
                log_swallowed()
            _refresh_and_reopen_menu(reopen_position=True)

        self._add_persistent_action(position_menu, "\u2193 Move to next line", _do_down)
        self._add_persistent_action(position_menu, "\u2191 Move up a line", _do_up)
        self._add_persistent_action(position_menu, "\u2192 Shift right", _do_shift_right)
        self._add_persistent_action(position_menu, "\u2190 Shift left", _do_shift_left)

        _cur_def = self._get_widget_def_by_id(widget_def["id"]) or widget_def
        _cur_row = int(_cur_def.get("row_num", 0) or 0)
        _cur_col = int(_cur_def.get("col_offset", 0) or 0)
        if _cur_row != 0 or _cur_col != 0:
            def _do_reset_position(_=None, wid=widget_def["id"]):
                WidgetRegistry.update_setting(wid, "row_num", None)
                WidgetRegistry.update_setting(wid, "col_offset", None)
                try:
                    live = self.manager._active_widgets.get(wid)
                    if live is not None:
                        live._col_offset = 0
                except Exception:
                    log_swallowed()
                _refresh_and_reopen_menu(reopen_position=True)
            self._add_persistent_action(position_menu, "\u21ba Reset line/shift position", _do_reset_position)

        position_menu.addSeparator()

        if _wtype == "stat_card":
            def _stat_box_num(defn):
                try:
                    return max(0, int(defn.get("stat_box", 0) or 0))
                except Exception:
                    return 0

            def _refresh_after_box_move():
                _refresh_and_reopen_menu(reopen_position=True)

            def _next_stat_box_id(defs):
                used = [_stat_box_num(d) for d in defs if d.get("type") == "stat_card"]
                return (max(used) + 1) if used else 1

            def _do_box_down(_=None, wid=widget_def["id"]):
                cur = self._get_widget_def_by_id(wid) or {}
                cur_box = _stat_box_num(cur)
                defs = WidgetRegistry.get_all()
                order = _live_section_order(defs)
                cur_key = stats_section_key(cur_box)
                if cur_key not in order:
                    order.append(cur_key)
                idx = order.index(cur_key)

                target_box = cur_box
                next_same = None
                for key in order[idx + 1 :]:
                    base, box = parse_section_key(key)
                    if base == BLOCK_STATS:
                        next_same = _nonneg_int(box, 0)
                        break
                if next_same is not None:
                    target_box = next_same
                elif idx + 1 < len(order):
                    target_box = _next_stat_box_id(defs)
                    new_key = stats_section_key(target_box)
                    insert_at = min(len(order), idx + 2)
                    if new_key not in order:
                        order.insert(insert_at, new_key)
                else:
                    target_box = _next_stat_box_id(defs)
                    new_key = stats_section_key(target_box)
                    if new_key not in order:
                        order.append(new_key)

                WidgetRegistry.update_setting(wid, "stat_box", None if target_box == 0 else int(target_box))
                _write_config_value(Config.PINNED_BLOCK_ORDER, order)
                _refresh_after_box_move()

            def _do_box_up(_=None, wid=widget_def["id"]):
                cur = self._get_widget_def_by_id(wid) or {}
                cur_box = _stat_box_num(cur)
                defs = WidgetRegistry.get_all()
                order = _live_section_order(defs)
                cur_key = stats_section_key(cur_box)
                if cur_key not in order:
                    order.insert(0, cur_key)
                idx = order.index(cur_key)
                if idx <= 0:
                    return

                target_box = None
                for key in reversed(order[:idx]):
                    base, box = parse_section_key(key)
                    if base == BLOCK_STATS:
                        target_box = _nonneg_int(box, 0)
                        break
                if target_box is None:
                    target_box = _next_stat_box_id(defs)
                    new_key = stats_section_key(target_box)
                    if new_key not in order:
                        order.insert(idx - 1, new_key)
                if target_box == cur_box:
                    return

                WidgetRegistry.update_setting(wid, "stat_box", None if target_box == 0 else int(target_box))
                _write_config_value(Config.PINNED_BLOCK_ORDER, order)
                _refresh_after_box_move()

            self._add_persistent_action(position_menu, "\u2193 Move to next box/section", _do_box_down)
            self._add_persistent_action(position_menu, "\u2191 Move to previous box/section", _do_box_up)

            _cur_box = _stat_box_num(self._get_widget_def_by_id(widget_def["id"]) or widget_def)
            if _cur_box != 0:
                def _do_box_reset(_=None, wid=widget_def["id"]):
                    WidgetRegistry.update_setting(wid, "stat_box", None)
                    _refresh_after_box_move()

                self._add_persistent_action(position_menu, "\u21ba Return to main stats box", _do_box_reset)
        else:
            def _chart_box_num(defn):
                try:
                    return max(0, int(defn.get("chart_box", 0) or 0))
                except Exception:
                    return 0

            def _text_box_num(defn):
                try:
                    return max(0, int(defn.get("text_box", defn.get("chart_box", 0)) or 0))
                except Exception:
                    return 0

            def _refresh_after_chart_box_move():
                _refresh_and_reopen_menu(reopen_position=True)

            def _next_chart_box_id(defs):
                used = [
                    _chart_box_num(d)
                    for d in defs
                    if d.get("type") not in ("stat_card", "text_label")
                ]
                return (max(used) + 1) if used else 1

            def _next_text_box_id(defs):
                used = [_text_box_num(d) for d in defs if d.get("type") == "text_label"]
                return (max(used) + 1) if used else 1

            is_text_widget = (_wtype == "text_label")
            current_family = BLOCK_TEXTS if is_text_widget else BLOCK_CHARTS
            current_section_key_fn = texts_section_key if is_text_widget else charts_section_key
            current_box_num = _text_box_num if is_text_widget else _chart_box_num
            next_box_id = _next_text_box_id if is_text_widget else _next_chart_box_id
            main_box_label = "main text box" if is_text_widget else "main charts box"

            def _write_current_box(wid, target_box):
                if is_text_widget:
                    WidgetRegistry.update_setting(wid, "text_box", int(target_box))
                else:
                    WidgetRegistry.update_setting(wid, "chart_box", None if target_box == 0 else int(target_box))

            def _do_chart_box_down(_=None, wid=widget_def["id"]):
                cur = self._get_widget_def_by_id(wid) or {}
                cur_box = current_box_num(cur)
                defs = WidgetRegistry.get_all()
                order = _live_section_order(defs)
                cur_key = current_section_key_fn(cur_box)
                if cur_key not in order:
                    order.append(cur_key)
                idx = order.index(cur_key)

                target_box = cur_box
                next_same = None
                for key in order[idx + 1 :]:
                    base, box = parse_section_key(key)
                    if base == current_family:
                        next_same = _nonneg_int(box, 0)
                        break
                if next_same is not None:
                    target_box = next_same
                elif idx + 1 < len(order):
                    target_box = next_box_id(defs)
                    new_key = current_section_key_fn(target_box)
                    insert_at = min(len(order), idx + 2)
                    if new_key not in order:
                        order.insert(insert_at, new_key)
                else:
                    target_box = next_box_id(defs)
                    new_key = current_section_key_fn(target_box)
                    if new_key not in order:
                        order.append(new_key)

                _write_current_box(wid, target_box)
                _write_config_value(Config.PINNED_BLOCK_ORDER, order)
                _refresh_after_chart_box_move()

            def _do_chart_box_up(_=None, wid=widget_def["id"]):
                cur = self._get_widget_def_by_id(wid) or {}
                cur_box = current_box_num(cur)
                defs = WidgetRegistry.get_all()
                order = _live_section_order(defs)
                cur_key = current_section_key_fn(cur_box)
                if cur_key not in order:
                    order.append(cur_key)
                idx = order.index(cur_key)
                if idx <= 0:
                    return

                target_box = None
                for key in reversed(order[:idx]):
                    base, box = parse_section_key(key)
                    if base == current_family:
                        target_box = _nonneg_int(box, 0)
                        break
                if target_box is None:
                    target_box = next_box_id(defs)
                    new_key = current_section_key_fn(target_box)
                    if new_key not in order:
                        order.insert(idx - 1, new_key)
                if target_box == cur_box:
                    return

                _write_current_box(wid, target_box)
                _write_config_value(Config.PINNED_BLOCK_ORDER, order)
                _refresh_after_chart_box_move()

            self._add_persistent_action(position_menu, "\u2193 Move to next box/section", _do_chart_box_down)
            self._add_persistent_action(position_menu, "\u2191 Move to previous box/section", _do_chart_box_up)

            _cur_box = current_box_num(self._get_widget_def_by_id(widget_def["id"]) or widget_def)
            if _cur_box != 0:
                def _do_chart_box_reset(_=None, wid=widget_def["id"]):
                    _write_current_box(wid, 0)
                    _refresh_after_chart_box_move()

                self._add_persistent_action(position_menu, f"\u21ba Return to {main_box_label}", _do_chart_box_reset)

        all_defs_for_blocks = WidgetRegistry.get_all()
        stat_boxes, chart_boxes, text_boxes = _collect_boxes_from_defs(all_defs_for_blocks)

        available_sections = [stats_section_key(box_id) for box_id in stat_boxes]
        available_sections.extend(charts_section_key(box_id) for box_id in chart_boxes)
        available_sections.extend(texts_section_key(box_id) for box_id in text_boxes)

        if len(available_sections) >= 2:
            raw_block_order = cfg.get(Config.PINNED_BLOCK_ORDER, None)
            full_order = normalize_block_order(
                raw_block_order,
                stats_boxes=stat_boxes,
                chart_boxes=chart_boxes,
                text_boxes=text_boxes,
            )
            working_order = [section for section in full_order if section in available_sections]
            current_block = block_for_widget(widget_def)

            if current_block in working_order:
                current_index = working_order.index(current_block)
                current_label = section_label(current_block)

                def _persist_block_order(new_working_order):
                    _write_config_value(Config.PINNED_BLOCK_ORDER, list(new_working_order))
                    _refresh_and_reopen_menu(reopen_position=True)

                def _load_working_order():
                    live_cfg = (self.manager._config_manager.config or {})
                    live_full = normalize_block_order(
                        live_cfg.get(Config.PINNED_BLOCK_ORDER, None),
                        stats_boxes=stat_boxes,
                        chart_boxes=chart_boxes,
                        text_boxes=text_boxes,
                    )
                    return [section for section in live_full if section in available_sections]

                position_menu.addSeparator()
                if current_index > 0:
                    def _move_block_up(_=None):
                        updated = _load_working_order()
                        if current_block not in updated:
                            return
                        idx = updated.index(current_block)
                        if idx <= 0:
                            return
                        updated[idx - 1], updated[idx] = updated[idx], updated[idx - 1]
                        _persist_block_order(updated)

                    self._add_persistent_action(position_menu, f"\u2191 Move {current_label} up", _move_block_up)

                if current_index < len(working_order) - 1:
                    def _move_block_down(_=None):
                        updated = _load_working_order()
                        if current_block not in updated:
                            return
                        idx = updated.index(current_block)
                        if idx >= len(updated) - 1:
                            return
                        updated[idx + 1], updated[idx] = updated[idx], updated[idx + 1]
                        _persist_block_order(updated)

                    self._add_persistent_action(position_menu, f"\u2193 Move {current_label} down", _move_block_down)

                default_order = normalize_block_order(
                    None,
                    stats_boxes=stat_boxes,
                    chart_boxes=chart_boxes,
                    text_boxes=text_boxes,
                )
                if working_order != default_order:
                    def _reset_block_order(_=None):
                        _write_config_value(Config.PINNED_BLOCK_ORDER, default_order)
                        _refresh_and_reopen_menu(reopen_position=True)

                    self._add_persistent_action(position_menu, "\u21ba Reset section order", _reset_block_order)

        menu.addSeparator()
        remove_action = QAction("Remove from main menu", menu)
        remove_action.setIcon(get_svg_icon("trash-2", size=14, context_ref=menu))
        remove_action.triggered.connect(lambda: self.manager._unpin(widget_def["id"]))
        menu.addAction(remove_action)

        has_size = widget_def.get("width") or widget_def.get("height")
        if has_size:
            menu.addSeparator()
            reset_size_act = QAction("Reset Size", menu)
            reset_size_act.setIcon(get_svg_icon("maximize", size=16, context_ref=menu))
            reset_size_act.triggered.connect(lambda: self.manager._reset_widget_size(widget_def["id"]))
            menu.addAction(reset_size_act)

        if reopen_position_menu and position_menu is not None:
            def _open_position_submenu():
                try:
                    action = position_menu.menuAction()
                    if action is None:
                        return
                    menu.setActiveAction(action)
                    rect = menu.actionGeometry(action)
                    anchor = menu.mapToGlobal(rect.topRight()) if rect.isValid() else global_pos
                    position_menu.popup(anchor)
                except Exception:
                    log_swallowed()

            QTimer.singleShot(0, _open_position_submenu)

        menu.exec(global_pos)
