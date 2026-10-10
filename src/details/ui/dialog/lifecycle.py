# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QAction, Qt, QWidget

from .. import Config
from ...logic.refresh import queue_ui_callback, request_details_runtime_refresh
from ..theme.icons import get_svg_icon
from ...logic.logger import log_swallowed


def show_event(dialog, event):
    QWidget.showEvent(dialog, event)
    if not getattr(dialog, "_fit_connected", False):
        from .screen_fit import install

        install(dialog)
    try:
        from .tab_scroll import install as _install_tab_scroll

        _install_tab_scroll(dialog.tab_widget)
    except Exception:
        log_swallowed()
    if not getattr(dialog, "_theme_first_show_synced", False):
        dialog._theme_first_show_synced = True
        try:
            queue_ui_callback(
                dialog.refresh_ui_icons,
                delay_ms=0,
                owner=dialog,
                reason="dialog.showEvent.refresh_ui_icons",
            )
        except Exception:
            try:
                dialog.refresh_ui_icons()
            except Exception:
                log_swallowed()


def save_ui_state(dialog):
    updates = {Config.DETAILS_LAYOUT_STATE: dialog.layout_state}
    idx = dialog.tab_widget.currentIndex()
    if idx >= 0:
        if dialog.view_mode == "time":
            updates[Config.DETAILS_TIME_TAB_INDEX] = idx
        else:
            updates[Config.DETAILS_DECK_TAB_INDEX] = idx
    ddm = dialog.deep_dive_manager
    is_active = hasattr(dialog, "layout_toggle_container") and dialog.layout_toggle_container.isVisible()
    if is_active and ddm.last_deck_identifier:
        updates[Config.DETAILS_DEEP_DIVE_IDENTIFIER] = ddm.last_deck_identifier
        updates[Config.DETAILS_DEEP_DIVE_TITLE] = dialog.expanded_title.text() if hasattr(dialog, "expanded_title") else ""
        updates[Config.DETAILS_DEEP_DIVE_PERIOD_RANGE] = getattr(ddm, "last_period_range", None)
    else:
        updates[Config.DETAILS_DEEP_DIVE_IDENTIFIER] = None
        updates[Config.DETAILS_DEEP_DIVE_TITLE] = ""
        updates[Config.DETAILS_DEEP_DIVE_PERIOD_RANGE] = None
    dialog.addon_config.write_config_vals(updates)


def close_event(dialog, event):
    # Skipped right after a reset: saving would write the old values back into the fresh config.
    if not getattr(dialog, "_skip_state_save", False):
        dialog._save_ui_state()
    try:
        from ...widgets.pinned.main_menu.manager import MainMenuWidgetManager
        if MainMenuWidgetManager.instance_exists():
            MainMenuWidgetManager.instance().set_external_refresh_suspended(
                False, reason="details_open"
            )
    except Exception:
        log_swallowed()
    QWidget.closeEvent(dialog, event)
    # QWidget.closeEvent (not QDialog's) never emits finished, so the owner was not
    # told the window closed and built a new one on every open. Notify it
    # explicitly.
    if event.isAccepted():
        try:
            dialog.finished.emit(0)
        except Exception:
            log_swallowed()


def toggle_side_view(dialog):
    dialog.side_view = not dialog.side_view
    apply_split_orientation(dialog, effective_side_view(dialog))
    dialog.addon_config.set_value(Config.DETAILS_SIDE_VIEW, dialog.side_view)


def apply_split_orientation(dialog, side):
    """Put the table on the side (right edge) or at the bottom."""
    sp = dialog.layout_splitter
    want = Qt.Orientation.Horizontal if side else Qt.Orientation.Vertical
    if sp.orientation() != want:
        sp.setOrientation(want)
        _sync_table_drawer(dialog)


def effective_side_view(dialog):
    return bool(dialog.side_view)


def on_deep_dive_closed(dialog):
    dialog.expanded_container.setVisible(False)
    if hasattr(dialog, "layout_toggle_container"):
        dialog.layout_toggle_container.setVisible(False)
    if hasattr(dialog, "deck_select_btn"):
        dialog.deck_select_btn.setVisible(False)
        dialog.span_select_btn.setVisible(False)
    dialog.layout_state = 0
    _sync_table_drawer(dialog)
    request_details_runtime_refresh(dialog, reason="dialog.on_deep_dive_closed", update_dashboard=True)
    from ..interactions import on_tab_changed

    on_tab_changed(dialog, dialog.tab_widget.currentIndex())


def _sync_table_drawer(dialog):
    try:
        from ..details_dialog.table_drawer import sync

        sync(dialog)
    except Exception:
        log_swallowed()


def switch_layout(dialog, state):
    dialog.apply_layout_state(state)


def apply_layout_state(dialog, state=None, update_sizes=True, animated=True):
    """State 0: the table fills the window. Otherwise the charts do and the table is the drawer."""
    from ..details_dialog.table_drawer import engaged, handle_layout_state, toggle as drawer_toggle

    old_state = dialog.layout_state
    if state == 0 and engaged(dialog):
        # Full table: hand the table back to the splitter before anything else runs on it.
        dialog.layout_state = 0
        _sync_table_drawer(dialog)
    elif handle_layout_state(dialog, state, update_sizes):
        return
    if state is not None:
        dialog.layout_state = state
        if state == 0 and old_state != 0:
            from ..interactions import on_tab_changed

            on_tab_changed(dialog, dialog.tab_widget.currentIndex())
        elif state != 0 and old_state == 0:
            is_active = hasattr(dialog, "layout_toggle_container") and dialog.layout_toggle_container.isVisible()
            if is_active and hasattr(dialog, "deep_dive_manager") and update_sizes:
                dialog.deep_dive_manager._refresh_dashboard_data()
    for i, btn in enumerate(getattr(dialog, "layout_btns", [])):
        btn.setChecked(i == dialog.layout_state)
    sp = dialog.layout_splitter
    sizes = sp.sizes()
    total_size = sum(sizes) if sizes else 0
    if total_size == 0:
        total_size = sp.width() or dialog.width()
    if not dialog.expanded_container.isVisible():
        dialog.expanded_container.setVisible(True)
    dialog._splitter_timer_gen = getattr(dialog, "_splitter_timer_gen", 0) + 1
    if update_sizes:
        target_first = 0 if dialog.layout_state == 0 else total_size
        sp.blockSignals(True)
        sp.setSizes([target_first, total_size - target_first])
        sp.blockSignals(False)
        tf, ts, gen = target_first, total_size, dialog._splitter_timer_gen

        def _deferred(sp=sp, tf=tf, ts=ts, gen=gen):
            if getattr(dialog, "_splitter_timer_gen", 0) != gen:
                return
            sp.blockSignals(True)
            sp.setSizes([tf, ts - tf])
            sp.blockSignals(False)

        queue_ui_callback(
            _deferred,
            delay_ms=0,
            owner=dialog,
            reason="dialog.apply_layout_state.deferred_splitter",
        )
    _sync_table_drawer(dialog)
    if state in (1, 2):
        # Coming back from the full table: the drawer was just set up, put it in the asked state.
        drawer_toggle(dialog, state == 1)


def resize_event(dialog, event):
    QWidget.resizeEvent(dialog, event)
    dialog._update_responsive_toolbar()
    if getattr(dialog, "layout_splitter", None) is not None:
        apply_split_orientation(dialog, effective_side_view(dialog))
    from .screen_fit import on_resize

    on_resize(dialog)


def update_responsive_toolbar(dialog):
    if not hasattr(dialog, "overflow_btn"):
        return
    w = dialog.width()
    show_secondary = w >= 1150
    show_primary = w >= 1000
    show_view_btn = w >= 700
    dialog.trend_toggle.setVisible(show_secondary)
    dialog.visual_toggle.setVisible(show_secondary)
    dialog.settings_btn.setVisible(show_primary)
    dialog.deck_opts_btn.setVisible(show_primary)
    dialog.export_btn.setVisible(show_primary)
    for _n in ("support_btn", "rate_btn", "github_btn"):
        if hasattr(dialog, _n):
            getattr(dialog, _n).setVisible(show_primary)
    is_deep_dive = dialog.expanded_container.isVisible()
    if is_deep_dive:
        dialog.layout_toggle_container.setVisible(True)
    dialog.view_toggle_btn.setVisible(show_view_btn)
    needs_overflow = not (show_secondary and show_primary and show_view_btn)
    dialog.overflow_btn.setVisible(needs_overflow)
    if needs_overflow:
        from ..shared.menu import StyledMenu
        from ..theme import get_theme_palette
        from ...widgets.chart_utils.theme import ThemeContext, get_theme_colors, resolve_theme_runtime_state

        menu = StyledMenu(dialog)
        palette = get_theme_palette(dialog.addon_config.config) or {}
        runtime = resolve_theme_runtime_state(dialog.addon_config.config, ThemeContext.DETAILS)
        is_dark = bool(runtime.get("is_dark", bool(get_theme_colors(dialog).get("is_dark"))))
        icon_col = palette.get("text_secondary", "#a1a1aa" if is_dark else "#71717a")
        if not show_view_btn:
            view_txt = "Switch to Time View" if dialog.view_mode == "deck" else "Switch to Deck View"
            act = QAction(view_txt, menu)
            act.setIcon(get_svg_icon("activity" if dialog.view_mode == "deck" else "calendar", color=icon_col, size=16))
            act.triggered.connect(dialog.view_toggle_btn.click)
            menu.addAction(act)
            menu.addSeparator()
        if not show_secondary:
            act = QAction("Trend Lines", menu)
            act.setIcon(get_svg_icon("trending-up", color=icon_col, size=16))
            act.setCheckable(True)
            act.setChecked(dialog.trend_toggle.isChecked())
            act.triggered.connect(dialog.trend_toggle.click)
            menu.addAction(act)
            from ..details_dialog.visual_menu import populate_visual_menu

            visuals_menu = menu.addMenu("Visuals")
            visuals_menu.setIcon(get_svg_icon("bar-chart-2", color=icon_col, size=16))
            populate_visual_menu(dialog, visuals_menu)
            menu.addSeparator()
        if not show_primary:
            act = QAction("Export Data...", menu)
            act.setIcon(get_svg_icon("save", color=icon_col, size=16))
            act.triggered.connect(dialog.export_btn.click)
            menu.addAction(act)
            act = QAction("Deck Options", menu)
            act.setIcon(get_svg_icon("palette", color=icon_col, size=16))
            act.triggered.connect(dialog.deck_opts_btn.click)
            menu.addAction(act)
            act = QAction("Settings", menu)
            act.setIcon(get_svg_icon("settings", color=icon_col, size=16))
            act.triggered.connect(dialog.settings_btn.click)
            menu.addAction(act)
            for _n, _txt, _ic in (("support_btn", "Support", "heart"), ("rate_btn", "Rate", "star"), ("github_btn", "GitHub", "github")):
                if hasattr(dialog, _n):
                    act = QAction(_txt, menu)
                    act.setIcon(get_svg_icon(_ic, color=icon_col, size=16))
                    act.triggered.connect(getattr(dialog, _n).click)
                    menu.addAction(act)
            menu.addSeparator()
        dialog.overflow_btn.setMenu(menu)

