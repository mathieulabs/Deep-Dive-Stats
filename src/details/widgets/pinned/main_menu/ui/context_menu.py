# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors

from aqt import mw
from aqt.qt import QAction, QActionGroup, Qt, QTimer

from ..imports import Config, Period
from ..imports import ConfigManager
from ... import PinnedViewSelectorDialog, WidgetRegistry
from .....ui import get_svg_icon
from .....logic.logger import log_swallowed
from ......i18n import tr, tr_name


class PinnedContextMenu:
    def __init__(self, manager):
        self.manager = manager

    def _open_fullscreen(self, widget):
        """Replaced by the web block while its menu is open (web_ui/pinned.py: the page's card fullscreen)."""
        return


    def _open_details_for_widget(self, widget_def):
        """Open the Deep Dive on the deck(s) and period this widget shows."""
        try:
            from ...widget_factory.utils import _resolve_deck_ids

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

        def _write_config_value(key, value):
            cm = getattr(self.manager, "_config_manager", None)
            if cm is not None and hasattr(cm, "set_value"):
                cm.set_value(key, value)
                return
            ConfigManager(mw).set_value(key, value)

        from .card_chips import themed_menu

        menu = themed_menu(widget, self.manager)
        global_pos = fixed_global_pos if fixed_global_pos is not None else widget.mapToGlobal(pos)

        details_action = QAction(tr("Open Details Window"), menu)
        details_action.setIcon(get_svg_icon("external-link", size=16, context_ref=menu))
        # Open once the menu has closed: a window shown from inside the menu's loop stays white
        # until the loop ends.
        details_action.triggered.connect(
            lambda _=False, wd=widget_def: QTimer.singleShot(0, lambda: self._open_details_for_widget(wd))
        )
        menu.addAction(details_action)

        if widget_def.get("type") not in ("stat_card", "text_label"):
            fs_action = QAction(tr("Fullscreen"), menu)
            fs_action.triggered.connect(lambda _=False, w=widget: self._open_fullscreen(w))
            fs_action.setIcon(get_svg_icon("maximize", size=16, context_ref=menu))
            menu.addAction(fs_action)

        from .add_widget_menu import add_widget_actions

        add_widget_actions(
            menu,
            self.manager,
            icon_fn=lambda name: get_svg_icon(name, size=16, context_ref=menu),
            after_def=widget_def if isinstance(widget_def, dict) else None,
        )

        menu.addSeparator()
        # The text widget's dialog is mostly its text (plus its box settings): say so.
        is_text = widget_def.get("type") == "text_label"
        settings_action = QAction(tr("Edit Text and Settings...") if is_text else tr("Settings"), menu)
        settings_action.setMenuRole(QAction.MenuRole.NoRole)  # macOS would otherwise move it into the app menu as Preferences/Quit
        settings_action.setIcon(get_svg_icon("file-text" if is_text else "settings", size=16, context_ref=menu))
        settings_action.triggered.connect(lambda: self.manager._open_widget_settings(widget, widget_def))
        menu.addAction(settings_action)
        from ....common.chart_help import add_help_action

        add_help_action(menu, widget_def.get("type"), widget)

        menu.addSeparator()

        from .card_chips import choose_decks, fill_span_menu, has_time_span

        if has_time_span(widget_def):
            span_menu = menu.addMenu(tr("Time Span"))
            span_menu.setIcon(get_svg_icon("calendar", size=16, context_ref=menu))
            fill_span_menu(span_menu, self.manager, widget, widget_def)

        try:
            from ... import zoom_link

            if zoom_link.has_charts(widget):
                linked_n, off_n = zoom_link.counts(self.manager)
                mine = zoom_link.is_linked(widget)
                z_act = QAction(tr("Disconnect zoom") if mine else tr("Reconnect zoom"), menu)
                z_act.setIcon(get_svg_icon("zoom-in", size=16, context_ref=menu))
                z_act.triggered.connect(lambda _=False, w=widget, v=not mine: zoom_link.set_linked(w, v))
                menu.addAction(z_act)
                if linked_n + off_n >= 2:
                    if linked_n >= 2 or (linked_n == 1 and not mine):
                        a = QAction(tr("Disconnect all charts' zoom"), menu)
                        a.triggered.connect(lambda _=False: zoom_link.set_all_linked(self.manager, False))
                        menu.addAction(a)
                    if off_n:
                        a = QAction(tr("Reconnect all charts' zoom"), menu)
                        a.triggered.connect(lambda _=False: zoom_link.set_all_linked(self.manager, True))
                        menu.addAction(a)
        except Exception:
            log_swallowed()

        deck_act = QAction(tr("Select Decks..."), menu)
        deck_act.setIcon(get_svg_icon("layers", size=16, context_ref=menu))
        deck_act.triggered.connect(lambda _=False: choose_decks(self.manager, widget, widget_def))
        menu.addAction(deck_act)

        view_act = QAction(tr("View..."), menu)
        view_act.setIcon(get_svg_icon("eye", size=16, context_ref=menu))

        def on_view_select():
            current_view = widget_def.get("view_dids", None)
            dialog = PinnedViewSelectorDialog(current_view, parent=widget)
            if dialog.exec():
                WidgetRegistry.update_setting(widget_def["id"], "view_dids", dialog.selected_values)
                self.manager.refresh()

        view_act.triggered.connect(on_view_select)
        menu.addAction(view_act)

        # Reviews/Day and Time/Day: the same over the days studied only (the card becomes Reviews/Active Day)
        if widget_def.get("type") == "stat_card":
            from .....logic.stat_cards import active_day_twin

            twin = active_day_twin(widget_def.get("stat_key"))
            if twin:
                act_days = QAction(tr("Active days only"), menu)
                act_days.setCheckable(True)
                act_days.setChecked(twin[1])

                # the menu stays open on a check: each click follows the box (checked: the active-days card), not
                # the card the menu was opened on (otherwise a second click puts the same card back)
                every_day, active = (widget_def.get("stat_key"), twin[0]) if not twin[1] else (twin[0], widget_def.get("stat_key"))

                def _swap_twin(checked=False, wid=widget_def["id"], every_day=every_day, active=active):
                    WidgetRegistry.update_setting(wid, "stat_key", active if checked else every_day)
                    self.manager.refresh(clear_cache=False)

                act_days.triggered.connect(_swap_twin)
                menu.addAction(act_days)

            # how the stat cards' numbers change (Stat_Num_Anim, one setting for every stat card, here and in Deep
            # Dive; also in Settings > General > Animations)
            na_menu = menu.addMenu(tr("Number Animation"))
            na_now = "roll" if self.manager._config_manager.config.get(Config.STAT_NUM_ANIM) == "roll" else "count"
            for na_key, na_label in (("count", tr("Numbers count")), ("roll", tr("Digits roll"))):
                na_act = QAction(na_label, na_menu)
                na_act.setCheckable(True)
                na_act.setChecked(na_key == na_now)

                def _set_num_anim(_=False, value=na_key):
                    _write_config_value(Config.STAT_NUM_ANIM, value)
                    self.manager.refresh(clear_cache=False)

                na_act.triggered.connect(_set_num_anim)
                na_menu.addAction(na_act)

            # Icon style & position (per-card when unlinked, else global)
            ico_menu = menu.addMenu(tr("Icon"))
            ico_group = QActionGroup(ico_menu)
            ico_group.setExclusive(True)
            own_style = bool(widget_def.get("use_custom_style", False))
            conf_now = self.manager._config_manager.config
            raw_ico = widget_def.get(Config.FACECARDS_SHOW_ICONS) if (own_style and Config.FACECARDS_SHOW_ICONS in widget_def) else conf_now.get(Config.FACECARDS_SHOW_ICONS, "inline")
            ico_now = "off" if raw_ico in (False, "", "off", None) else ("watermark" if raw_ico == "watermark" else "inline")
            for ico_key, ico_label in (("off", tr("Off")), ("inline", tr("Next to title")), ("watermark", tr("Watermark"))):
                ico_act = QAction(ico_label, ico_menu)
                ico_act.setCheckable(True)
                ico_act.setChecked(ico_key == ico_now)
                ico_group.addAction(ico_act)

                def _set_ico(_=False, value=ico_key, wid=widget_def["id"], own=own_style):
                    if own:
                        WidgetRegistry.update_setting(wid, Config.FACECARDS_SHOW_ICONS, value)
                    else:
                        _write_config_value(Config.FACECARDS_SHOW_ICONS, value)
                    self.manager.refresh(clear_cache=False)

                ico_act.triggered.connect(_set_ico)
                ico_menu.addAction(ico_act)

            ico_menu.addSeparator()
            pos_menu = ico_menu.addMenu(tr("Position"))
            pos_menu.setEnabled(ico_now == "watermark")
            pos_group = QActionGroup(pos_menu)
            pos_group.setExclusive(True)
            raw_pos = widget_def.get(Config.FACECARDS_ICON_POS) if (own_style and Config.FACECARDS_ICON_POS in widget_def) else conf_now.get(Config.FACECARDS_ICON_POS, "tl")
            pos_now = raw_pos if raw_pos in ("tl", "tr", "bl", "br") else "tl"
            for p_key, p_label in (("tl", tr("Top Left")), ("tr", tr("Top Right")), ("bl", tr("Bottom Left")), ("br", tr("Bottom Right"))):
                p_act = QAction(p_label, pos_menu)
                p_act.setCheckable(True)
                p_act.setChecked(p_key == pos_now)
                pos_group.addAction(p_act)

                def _set_pos(_=False, value=p_key, wid=widget_def["id"], own=own_style):
                    if own:
                        WidgetRegistry.update_setting(wid, Config.FACECARDS_ICON_POS, value)
                    else:
                        _write_config_value(Config.FACECARDS_ICON_POS, value)
                    self.manager.refresh(clear_cache=False)

                p_act.triggered.connect(_set_pos)
                pos_menu.addAction(p_act)

        wtype = widget_def.get("type")
        from ....charts.more_charts import AVERAGE_TYPES, CUMULATIVE_TYPES, TYPES as MORE_TYPES

        avg_sections = ["activity", "added", "retention", *AVERAGE_TYPES]
        cumulative_sections = ["activity", "added", "future_due", "review_intervals", "stability", *CUMULATIVE_TYPES]

        if wtype in ("card_counts", "todays_retention"):
            # the ring charts' Legend Layout (Settings has the same choice; the Deep Dive's right-click too)
            menu.addSeparator()
            lg_menu = menu.addMenu(tr("Legend Layout"))
            lg_now = widget_def.get("legend_mode") or "auto"
            # one choice (the menu stays open on a checked entry: without the group each one was ticked on its own)
            lg_group = QActionGroup(lg_menu)
            lg_group.setExclusive(True)
            for lg_key, lg_name in (("auto", "Auto"), ("always", "Always next to the donut"), ("hover", "On hover")):
                lg_act = QAction(tr_name(lg_name), lg_menu)
                lg_act.setCheckable(True)
                lg_act.setChecked(lg_key == lg_now)
                lg_act.triggered.connect(lambda _=False, wid=widget_def["id"], v=lg_key:
                    self.manager._update_setting(wid, "legend_mode", v))
                lg_group.addAction(lg_act)
                lg_menu.addAction(lg_act)

        if wtype == "todays_retention":
            # First Answer Retention: the kind of cards, the change from the period before, FSRS's target (the
            # page's pill menu and the Deep Dive's right-click have the same)
            menu.addSeparator()
            kind_menu = menu.addMenu(tr("Cards"))
            kind_now = widget_def.get("card_type") or "all"
            kind_group = QActionGroup(kind_menu)
            kind_group.setExclusive(True)
            for kind_key, kind_name in (("all", "All"), ("learn", "Learning"), ("young", "Young"), ("mature", "Mature")):
                kind_act = QAction(tr_name(kind_name), kind_menu)
                kind_act.setCheckable(True)
                kind_act.setChecked(kind_key == kind_now)
                kind_act.triggered.connect(lambda _=False, wid=widget_def["id"], v=kind_key:
                    self.manager._update_setting(wid, "card_type", v))
                kind_group.addAction(kind_act)
                kind_menu.addAction(kind_act)
            chg_act = QAction(tr("Show Change from Period Before"), menu)
            chg_act.setCheckable(True)
            chg_act.setChecked(widget_def.get("show_change", True) is not False)
            chg_act.triggered.connect(lambda checked, wid=widget_def["id"]:
                self.manager._update_setting(wid, "show_change", checked))
            menu.addAction(chg_act)
            try:
                fsrs = bool(mw.col.get_config("fsrs", False))
            except Exception:
                fsrs = False
            if fsrs:
                tgt_act = QAction(tr("Show FSRS Target"), menu)
                tgt_act.setCheckable(True)
                tgt_act.setChecked(widget_def.get("show_target", True) is not False)
                tgt_act.triggered.connect(lambda checked, wid=widget_def["id"]:
                    self.manager._update_setting(wid, "show_target", checked))
                menu.addAction(tgt_act)

        if wtype in set(avg_sections + cumulative_sections):
            menu.addSeparator()

            if wtype in avg_sections:
                show_avg = widget_def.get("show_average", True)
                avg_act = QAction(tr("Show Average"), menu)
                avg_act.setCheckable(True)
                avg_act.setChecked(show_avg)
                avg_act.triggered.connect(lambda checked, wid=widget_def["id"]:
                    self.manager._update_setting(wid, "show_average", checked))
                menu.addAction(avg_act)

                show_active = widget_def.get("avg_on_active_days", True)
                active_act = QAction(tr("Average on active days"), menu)
                active_act.setCheckable(True)
                active_act.setChecked(show_active)
                active_act.triggered.connect(lambda checked, wid=widget_def["id"]:
                    self.manager._update_setting(wid, "avg_on_active_days", checked))
                menu.addAction(active_act)

                if wtype == "retention":
                    fit = bool(widget_def.get("fit_to_data", False))
                    fit_act = QAction(tr("Within data limit"), menu)
                    fit_act.setCheckable(True)
                    fit_act.setChecked(fit)
                    fit_act.triggered.connect(lambda checked, wid=widget_def["id"]:
                        self.manager._update_setting(wid, "fit_to_data", checked))
                    menu.addAction(fit_act)

                    bars_menu = menu.addMenu(tr("Review Bars"))
                    bars_act = QAction(tr("Show Bars"), bars_menu)
                    bars_act.setCheckable(True)
                    bars_act.setChecked(bool(widget_def.get("review_bars", True)))
                    bars_act.triggered.connect(lambda checked, wid=widget_def["id"]:
                        self.manager._update_setting(wid, "review_bars", checked))
                    bars_menu.addAction(bars_act)

                    axis_act = QAction(tr("Show Count Axis"), bars_menu)
                    axis_act.setCheckable(True)
                    axis_act.setChecked(bool(widget_def.get("review_axis", False)))
                    axis_act.setEnabled(bool(widget_def.get("review_bars", True)))
                    axis_act.triggered.connect(lambda checked, wid=widget_def["id"]:
                        self.manager._update_setting(wid, "review_axis", checked))
                    bars_menu.addAction(axis_act)

                    round_act = QAction(tr("Rounded Look"), menu)
                    round_act.setCheckable(True)
                    round_act.setChecked(bool(widget_def.get("rounded", True)))
                    round_act.setToolTip(tr("Smooth lines and rounded bar tops"))
                    round_act.triggered.connect(lambda checked, wid=widget_def["id"]:
                        self.manager._update_setting(wid, "rounded", checked))
                    menu.addAction(round_act)

                    current_min = int(widget_def.get("min_reviews", 0) or 0)
                    min_act = QAction(tr("Min Reviews per Point: {value}...", value=current_min if current_min else tr("Off")), menu)

                    def _ask_min(_=False, current=current_min, wid=widget_def["id"], parent=widget):
                        from .....ui.shared.number_dialog import ask_number

                        value = ask_number(
                            tr("Min Reviews"),
                            tr("Hide points with fewer reviews than this (0 = show all):"),
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
                total_act = QAction(tr("Show Total (Cumulative)"), menu)
                total_act.setCheckable(True)
                total_act.setChecked(show_total)
                total_act.triggered.connect(lambda checked, wid=widget_def["id"]:
                    self.manager._update_setting(wid, "show_cumulative", checked))
                menu.addAction(total_act)

            # "Series": hide parts of the bars (the charts split in parts; Future Due by type).
            from .....ui.shared.review_types_menu import add_series_actions

            _choices = []
            if wtype == "future_due":
                from .....logic.metrics.future_due import resolve_breakdown

                if resolve_breakdown(widget_def.get("breakdown"), widget_def.get("show_breakdown", False)) == "type":
                    _choices = [("mature", "Mature"), ("young", "Young"), ("learn", "Learning")]
            if len(_choices) > 1:
                add_series_actions(
                    menu, _choices, widget_def.get("hidden_series"),
                    lambda hidden, wid=widget_def["id"]: self.manager._update_setting(wid, "hidden_series", hidden or None),
                )

            # "Show as %": each bar as the shares of its parts (Activity: with Breakdown by Type).
            from ....charts.more_charts import PERCENT_TYPES

            fd_breakdown = None
            if wtype == "future_due":
                from .....logic.metrics.future_due import resolve_breakdown

                fd_breakdown = resolve_breakdown(widget_def.get("breakdown"), widget_def.get("show_breakdown", False))
            no_split = wtype == "card_states" and not widget_def.get("alt_view", True)
            if ((wtype in PERCENT_TYPES and not no_split) or fd_breakdown == "result"
                    or (wtype == "activity" and widget_def.get("show_breakdown", True))):
                pct_act = QAction(tr("Show as %"), menu)
                pct_act.setCheckable(True)
                pct_act.setChecked(bool(widget_def.get("show_percent", False)))
                pct_act.triggered.connect(lambda checked, wid=widget_def["id"]:
                    self.manager._update_setting(wid, "show_percent", checked))
                menu.addAction(pct_act)
            # Show Trend: a line through the bars, its slope in the header (web: extras.js TREND_UNIT)
            if wtype in ("activity", "added", "ratings", "review_speed", "forgotten", "resets", "introduced", "introduced_load", "load_trend",
                         "stability_trend", "memorised", "card_states", "future_retention", "answer_time",
                         "interval_ratings", "rating_fatigue", "fsrs_fatigue", "sibling_ratings"):
                trend_act = QAction(tr("Show Trend"), menu)
                trend_act.setCheckable(True)
                trend_act.setChecked(bool(widget_def.get("show_trend", wtype not in ("activity", "added"))))
                trend_act.triggered.connect(lambda checked, wid=widget_def["id"]:
                    self.manager._update_setting(wid, "show_trend", checked))
                menu.addAction(trend_act)

        if wtype == "heatmap":
            menu.addSeparator()
            multi_hue = cfg.get(Config.HEATMAP_MULTI_HUE_INTENSITY, False)

            multi_hue_act = QAction(tr("Multicolor Intensity"), menu)
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

            # the levels' palette (heatmap/palettes.py); the custom gradient's colors are in the heatmap's Settings
            from ....charts.heatmap.palettes import CUSTOM, PALETTES, customs_of, palette_of

            current_pal = palette_of(cfg.get)
            from ......const.theme.color_resolver import get_color as _get_hm_color

            cur_col = _get_hm_color(cfg, Config.HEATMAP_COLOR, "pinned")

            def _pick_color():
                from aqt.qt import QColor, QColorDialog

                cur = _get_hm_color(cfg, Config.HEATMAP_COLOR, "pinned")
                color = QColorDialog.getColor(QColor(cur), mw, tr("Pick Color"))
                if not color.isValid():
                    return
                chosen = color.name()
                if cfg.get(Config.PINNED_THEME_SEPARATE, False):
                    custom = dict(cfg.get(Config.PINNED_THEME_CUSTOM_COLORS, {}) or {})
                    custom[Config.HEATMAP_COLOR] = chosen
                    _write_config_value(Config.PINNED_THEME_CUSTOM_COLORS, custom)
                    _write_config_value(Config.PINNED_THEME_IS_CUSTOM, True)
                else:
                    _write_config_value(Config.HEATMAP_COLOR, chosen)
                if current_pal:
                    _write_config_value(Config.HEATMAP_PALETTE, "")
                self.manager.refresh(clear_cache=False)

            def _swatch_icon(hex_col):
                from aqt.qt import QColor, QIcon, QPainter, QPen, QPixmap

                pm = QPixmap(32, 32)
                pm.fill(Qt.GlobalColor.transparent)
                p = QPainter(pm)
                p.setRenderHint(QPainter.RenderHint.Antialiasing)
                p.setBrush(QColor(hex_col))
                p.setPen(QPen(QColor(128, 128, 128, 115), 2))
                p.drawEllipse(3, 3, 26, 26)
                p.end()
                return QIcon(pm)

            color_act = QAction(_swatch_icon(cur_col), tr("Color..."), menu)
            color_act.triggered.connect(lambda _=False: QTimer.singleShot(0, _pick_color))
            menu.addAction(color_act)

            pal_menu = menu.addMenu(tr("Palette"))
            entries = [(k, tr_name(label)) for k, label in PALETTES]
            mine = customs_of(cfg.get)
            if mine:  # the user's own gradients
                entries += [None] + [(CUSTOM + p["id"], p["name"]) for p in mine]
            for entry in entries:
                if entry is None:
                    pal_menu.addSeparator()
                    continue
                pal_key, pal_label = entry
                pal_act = QAction(pal_label, pal_menu)
                pal_act.setCheckable(True)
                pal_act.setChecked(pal_key == current_pal)

                def _set_palette(_=False, value=pal_key):
                    _write_config_value(Config.HEATMAP_PALETTE, value)
                    self.manager.refresh(clear_cache=False)
                    pal_menu.close()
                    menu.close()

                pal_act.triggered.connect(_set_palette)
                pal_menu.addAction(pal_act)

            # a gradient of one's own, made from the palette shown (or the one chosen changed), in a small window
            def _gradient(_=False, new=True):
                from .....ui.config.dialogs.heatmap_gradient import edit_gradient
                from .....ui.theme import get_theme_effective_is_dark
                from ......const.theme.color_resolver import get_color
                from ....charts.heatmap.palettes import seed_colors

                pal_menu.close()
                menu.close()
                seed = None
                if new:
                    seed = seed_colors(current_pal, mine, get_color(cfg, Config.HEATMAP_COLOR, "pinned"), dark=get_theme_effective_is_dark(cfg))
                edit_gradient(mw, cfg, _write_config_value, lambda: self.manager.refresh(clear_cache=False),
                              new=new, seed=seed)

            pal_menu.addSeparator()
            new_act = QAction(tr("New gradient..."), pal_menu)
            new_act.triggered.connect(lambda _=False: QTimer.singleShot(0, lambda: _gradient(new=True)))
            pal_menu.addAction(new_act)
            if current_pal.startswith(CUSTOM):
                edit_act = QAction(tr("Edit gradient..."), pal_menu)
                edit_act.triggered.connect(lambda _=False: QTimer.singleShot(0, lambda: _gradient(new=False)))
                pal_menu.addAction(edit_act)
            multi_hue_act.setEnabled(current_pal == "")  # only the chosen color's shades
            menu.addAction(multi_hue_act)

            def on_display_changed(key, value):
                _write_config_value(key, value)
                from ....charts.heatmap import HeatmapWidget
                from .....ui.shared.heatmap_menu import apply_heatmap_display
                apply_heatmap_display(widget.findChild(HeatmapWidget), key, value)
                self.manager.refresh(clear_cache=False)

            from .....ui.shared.heatmap_menu import add_heatmap_display_actions
            add_heatmap_display_actions(menu, cfg, on_display_changed)

            # this card's own: the year in two rows or the month grid when it is narrow (heatmap.js narrowOn)
            narrow_act = QAction(tr("Adapt the year to narrow cards"), menu)
            narrow_act.setCheckable(True)
            narrow_act.setChecked(bool(widget_def.get("narrow_layout", True)))
            narrow_act.triggered.connect(lambda checked, wid=widget_def["id"]:
                self.manager._update_setting(wid, "narrow_layout", checked))
            menu.addAction(narrow_act)

        wtype_stats = ["activity", "added", "hourly", "future_due", "review_intervals", "stability", "difficulty",
                       "retrievability", "retention", *MORE_TYPES]
        if wtype in wtype_stats:
            menu.addSeparator()
            global_show_bottom_stats = self.manager._config_manager.config.get(Config.DEEP_DIVE_PINNED_SHOW_BOTTOM_STATS, False)
            bottom_stats_act = QAction(tr("Show Bottom Stats (Global)"), menu)
            bottom_stats_act.setCheckable(True)
            bottom_stats_act.setChecked(global_show_bottom_stats)
            bottom_stats_act.triggered.connect(self.manager._toggle_global_bottom_stats)
            menu.addAction(bottom_stats_act)

            global_show_all_stats = self.manager._config_manager.config.get(Config.DEEP_DIVE_PINNED_SHOW_STATS, True)
            all_stats_act = QAction(tr("Show Stats (Global)"), menu)
            all_stats_act.setCheckable(True)
            all_stats_act.setChecked(global_show_all_stats)
            all_stats_act.triggered.connect(self.manager._toggle_global_show_stats)
            menu.addAction(all_stats_act)

        wtype_binning = ["activity", "added", "retention", "future_due", "review_intervals", "stability", "difficulty",
                         "retrievability", *MORE_TYPES]
        if wtype in wtype_binning and wtype not in ("due_today", "week_hours"):  # 24 bars, a grid, every day
            menu.addSeparator()

            from ..imports import Config as _Cfg
            global_binning = self.manager._config_manager.config.get(_Cfg.ADAPTIVE_CHART_BINNING, True)
            binning_override = widget_def.get("binning_override", None)
            effective_binning = binning_override if binning_override is not None else global_binning

            binning_act = QAction(tr("Adaptive Binning"), menu)
            binning_act.setCheckable(True)
            binning_act.setChecked(effective_binning)
            binning_act.triggered.connect(lambda checked, wid=widget_def["id"]:
                self.manager._update_setting(wid, "binning_override", checked))
            menu.addAction(binning_act)

        # the charts' axis animation (Chart_Axis_Anim, one setting for every chart, here and in Deep Dive; also in
        # Settings > General > Animations)
        if wtype in wtype_stats or wtype == "distribution":
            ax_menu = menu.addMenu(tr("Axis Animation"))
            ax_now = "count" if self.manager._config_manager.config.get(Config.CHART_AXIS_ANIM) == "count" else "slide"
            for ax_key, ax_label in (("count", tr("Numbers count")), ("slide", tr("Ticks slide"))):
                ax_act = QAction(ax_label, ax_menu)
                ax_act.setCheckable(True)
                ax_act.setChecked(ax_key == ax_now)

                def _set_axis_anim(_=False, value=ax_key):
                    _write_config_value(Config.CHART_AXIS_ANIM, value)
                    self.manager.refresh(clear_cache=False)

                ax_act.triggered.connect(_set_axis_anim)
                ax_menu.addAction(ax_act)

        menu.addSeparator()
        remove_action = QAction(tr("Remove from main menu"), menu)
        remove_action.setIcon(get_svg_icon("trash-2", size=14, context_ref=menu))
        remove_action.triggered.connect(lambda: self.manager._unpin(widget_def["id"]))
        menu.addAction(remove_action)

        has_size = widget_def.get("width") or widget_def.get("height")
        if has_size:
            menu.addSeparator()
            reset_size_act = QAction(tr("Reset Size"), menu)
            reset_size_act.setIcon(get_svg_icon("maximize", size=16, context_ref=menu))
            reset_size_act.triggered.connect(lambda: self.manager._reset_widget_size(widget_def["id"]))
            menu.addAction(reset_size_act)

        menu.exec(global_pos)
