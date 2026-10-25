# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors

from aqt import gui_hooks, mw
from aqt.qt import QAction, QTimer

from .config import ConfigManager, dev_label
from .qss import set_qss
from .details.logic.logger import log_error
from .details.logic.logger import log_swallowed
# DetailedStatsDialog is imported lazily in on_show_details(): importing it at module level forced the whole Deep Dive UI stack to load at every Anki launch.


# Where "Report a Bug" sends people. Replace with the project's GitHub issues page.
BUG_REPORT_URL = "https://github.com/mathieulabs/Deep-Dive-Stats/issues"


def open_bug_report():
    from aqt.qt import QDesktopServices, QUrl
    QDesktopServices.openUrl(QUrl(BUG_REPORT_URL))


def register_hooks():
    from .details.logic import log_info
    from .const import CURRENT_VERSION
    import sys, platform
    try:
        from aqt.main import AnkiQt
        anki_ver = AnkiQt.resizeEvent.__module__
    except Exception:
        anki_ver = "?"
    try:
        import aqt
        anki_ver = getattr(aqt, 'appVersion', '?')
    except Exception:
        log_swallowed()
    log_info(
        f"=== Deep Dive Stats v{CURRENT_VERSION} started | "
        f"Anki {anki_ver} | Python {sys.version.split()[0]} | "
        f"{platform.system()} {platform.release()} ===",
        tag="STARTUP"
    )

    gui_hooks.webview_did_receive_js_message.append(on_webview_message)
    gui_hooks.sync_did_finish.append(on_sync_did_finish)
    gui_hooks.top_toolbar_did_init_links.append(on_top_toolbar_did_init_links)

    # Flush buffered debug logs on profile close, since logging is batched.
    try:
        from .details.logic import DeepDiveLogger
        gui_hooks.profile_will_close.append(DeepDiveLogger.flush)
    except Exception:
        log_swallowed()
    gui_hooks.profile_will_close.append(_discard_parked_dialog)
    gui_hooks.profile_did_open.append(_seed_rollover)
    gui_hooks.operation_did_execute.append(_on_operation_for_rollover)
    gui_hooks.theme_did_change.append(_on_anki_theme_change)

    from .config import pinned_widgets_disabled
    if not pinned_widgets_disabled():
        from .details.widgets.pinned.main_menu.manager import MainMenuWidgetManager
        MainMenuWidgetManager.instance().register_hooks()

    add_toolbar_action()
    gui_hooks.profile_did_open.append(apply_shortcut)
    apply_shortcut()


def apply_shortcut(*_args):
    """Keyboard shortcut that opens the Deep Dive window (Settings > General)."""
    try:
        from aqt.qt import QKeySequence, QShortcut
        from .const import Config

        seq = str(ConfigManager(mw).config.get(Config.OPEN_SHORTCUT, "") or "")
        shortcut = getattr(mw, "_deep_dive_shortcut", None)
        if shortcut is None:
            shortcut = QShortcut(QKeySequence(), mw)
            shortcut.activated.connect(on_show_details)
            mw._deep_dive_shortcut = shortcut
        shortcut.setKey(QKeySequence(seq))
        open_action = getattr(mw, "_deep_dive_open_action", None)
        if open_action is not None:
            hint = QKeySequence(seq).toString(QKeySequence.SequenceFormat.NativeText)
            open_action.setText("Open Deep Dive" + (f"\t{hint}" if hint else ""))
    except Exception:
        log_swallowed()


def add_toolbar_action():
    """Adds a button to the main menu bar to open Deep Dive."""
    from aqt.qt import QMenu
    from .details.logic.history_cache import GlobalHistoryCache

    try:
        existing_action = getattr(mw, "_deep_dive_action", None)
        if existing_action is not None:
            return
    except Exception:
        log_swallowed()

    action = QAction(dev_label("Deep Dive"), mw)
    action.setToolTip(dev_label("Deep Dive Stats"))

    menu = QMenu(mw)

    open_action = menu.addAction("Open Deep Dive")
    open_action.triggered.connect(on_show_details)
    mw._deep_dive_open_action = open_action

    def on_open_settings():
        global _settings_open_guard
        from .details.ui.config import find_visible_settings_dialog

        if bool(_settings_open_guard):
            return

        try:
            existing_cfg = find_visible_settings_dialog()
            if existing_cfg is not None:
                try:
                    existing_cfg.raise_()
                    existing_cfg.activateWindow()
                except Exception:
                    log_swallowed()
                return
        except Exception:
            log_swallowed()

        if _current_dialog is not None:
            try:
                if _current_dialog.isVisible():
                    _current_dialog.open_settings(start_tab="General")
                    return
            except Exception:
                log_swallowed()

        # Create a lightweight host dialog for settings only: building the full Details window can cause intermittent extra windows.
        _settings_open_guard = True
        try:
            from aqt.qt import QDialog
            from .details.ui.config import DetailedStatsConfigDialog
            from .details.logic.tabs import get_tabs_config, save_tabs_config

            class _SettingsHost(QDialog):
                def __init__(self, cfg_manager, parent=None):
                    super().__init__(parent or mw)
                    self.addon_config = cfg_manager

                def get_tabs_config(self):
                    return get_tabs_config(self.addon_config)

                def save_tabs_config(self, tabs_data):
                    save_tabs_config(self.addon_config, tabs_data)

                def update_dashboard_visibility(self):
                    return

                def refresh_styles(self):
                    return

            conf_manager = ConfigManager(mw)
            host = _SettingsHost(conf_manager, parent=mw)
            config_dialog = DetailedStatsConfigDialog(host)
            try:
                for i in range(config_dialog.tabs_widget.count()):
                    if config_dialog.tabs_widget.tabText(i).strip().lower() == "general":
                        config_dialog.tabs_widget.setCurrentIndex(i)
                        break
            except Exception:
                log_swallowed()

            config_dialog.exec()
            try:
                host.deleteLater()
            except Exception:
                log_swallowed()
        except Exception:
            log_swallowed()
        finally:
            _settings_open_guard = False

    settings_action = menu.addAction("Settings")
    settings_action.triggered.connect(on_open_settings)

    menu.addSeparator()

    def on_clear_cache():
        from .details.logic import log_info
        log_info("User triggered Clear Cache.", tag="CACHE")
        _discard_parked_dialog()

        def on_reinit_done():
            if _current_dialog:
                try:
                    _current_dialog.refresh_data()
                except Exception:
                    pass
        GlobalHistoryCache.clear_all_cache(callback=on_reinit_done)

    clear_action = menu.addAction("Clear Cache")
    clear_action.triggered.connect(on_clear_cache)

    def on_view_logs():
        import os
        from .details.logic import DeepDiveLogger
        from .details.ui.theme.icons import get_svg_icon
        from aqt.qt import (QDialog, QVBoxLayout, QHBoxLayout, QTextEdit,
                            QPushButton, QLabel, QApplication, QMessageBox,
                            QSize, Qt, QTimer)

        DeepDiveLogger.flush()
        log_dir = DeepDiveLogger._get_log_dir()
        log_file = os.path.join(log_dir, "debug.log")
        try:
            if os.path.exists(log_file):
                with open(log_file, "r", encoding="utf-8") as f:
                    content = f.read()
                if not content.strip():
                    content = "(No logs yet)"
            else:
                content = "(Log file not found. Logs will appear after the next Anki restart.)"
        except Exception as e:
            content = f"Error reading logs: {e}"

        dlg = QDialog(mw)
        dlg.setWindowTitle("Deep Dive Debug Logs")
        dlg.resize(900, 600)

        layout = QVBoxLayout(dlg)

        path_row = QHBoxLayout()
        path_icon = QLabel()
        path_icon.setPixmap(get_svg_icon("file-text", color="#808080", size=14).pixmap(14, 14))
        path_row.addWidget(path_icon)
        label = QLabel(log_file)
        set_qss(label, "color: gray; font-size: 11px;")
        path_row.addWidget(label)
        copy_path_btn = QPushButton()
        copy_path_btn.setIcon(get_svg_icon("copy", size=14, context_ref=dlg))
        copy_path_btn.setIconSize(QSize(14, 14))
        copy_path_btn.setFixedSize(24, 24)
        copy_path_btn.setFlat(True)
        copy_path_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_path_btn.setToolTip("Copy path")
        def do_copy_path():
            QApplication.clipboard().setText(log_file)
            copy_path_btn.setIcon(get_svg_icon("check", size=14, context_ref=dlg))
            QTimer.singleShot(1200, lambda: copy_path_btn.setIcon(get_svg_icon("copy", size=14, context_ref=dlg)))
        copy_path_btn.clicked.connect(do_copy_path)
        path_row.addWidget(copy_path_btn)
        path_row.addStretch()
        layout.addLayout(path_row)

        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setPlainText(content)
        set_qss(text_edit, "font-family: monospace; font-size: 12px;")
        layout.addWidget(text_edit)
        from aqt.qt import QTimer as _QT
        _QT.singleShot(0, lambda: text_edit.verticalScrollBar().setValue(
            text_edit.verticalScrollBar().maximum()))

        btn_row = QHBoxLayout()

        copy_btn = QPushButton(" Copy All")
        copy_btn.setIcon(get_svg_icon("copy", size=16, context_ref=dlg))
        def do_copy():
            QApplication.clipboard().setText(text_edit.toPlainText())
            copy_btn.setText(" Copied")
            copy_btn.setIcon(get_svg_icon("check", size=16, context_ref=dlg))
        copy_btn.clicked.connect(do_copy)
        btn_row.addWidget(copy_btn)

        report_btn = QPushButton(" Report a Bug")
        report_btn.setIcon(get_svg_icon("bug", size=16, context_ref=dlg))
        report_btn.clicked.connect(open_bug_report)
        btn_row.addWidget(report_btn)

        btn_row.addStretch()

        clear_cache_btn = QPushButton(" Clear Cache")
        clear_cache_btn.setIcon(get_svg_icon("trash", color="#ffffff", size=16))
        set_qss(clear_cache_btn,
            "QPushButton { background-color: #c0392b; color: white; font-weight: bold; "
            "border-radius: 4px; padding: 4px 12px; }"
            "QPushButton:hover { background-color: #e74c3c; }"
        )
        def do_clear_cache():
            reply = QMessageBox.question(
                dlg, "Clear Cache",
                "Are you sure you want to clear the Deep Dive cache?\n"
                "It will be rebuilt automatically (may take a few seconds).",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                from .details.logic.history_cache import GlobalHistoryCache
                GlobalHistoryCache.clear_all_cache()
                dlg.accept()
        clear_cache_btn.clicked.connect(do_clear_cache)
        btn_row.addWidget(clear_cache_btn)

        clear_logs_btn = QPushButton(" Clear Logs")
        clear_logs_btn.setIcon(get_svg_icon("eraser", color="#ffffff", size=16))
        set_qss(clear_logs_btn,
            "QPushButton { background-color: #7f8c8d; color: white; font-weight: bold; "
            "border-radius: 4px; padding: 4px 12px; }"
            "QPushButton:hover { background-color: #95a5a6; }"
        )
        def do_clear_logs():
            reply = QMessageBox.question(
                dlg, "Clear Logs",
                "Are you sure you want to clear the debug log file?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                from .details.logic import DeepDiveLogger
                DeepDiveLogger.clear_logs()
                text_edit.setPlainText("(Logs cleared)")
                clear_logs_btn.setText(" Logs Cleared")
                clear_logs_btn.setIcon(get_svg_icon("check", color="#ffffff", size=16))
                clear_logs_btn.setEnabled(False)
        clear_logs_btn.clicked.connect(do_clear_logs)
        btn_row.addWidget(clear_logs_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dlg.accept)
        btn_row.addWidget(close_btn)

        layout.addLayout(btn_row)
        dlg.exec()

    view_logs_action = menu.addAction("View Debug Logs")
    view_logs_action.triggered.connect(on_view_logs)

    report_action = menu.addAction("Report a Bug")
    report_action.triggered.connect(open_bug_report)

    action.setMenu(menu)
    mw._deep_dive_menu = menu

    if hasattr(mw.form, 'menubar'):
        mw.form.menubar.addAction(action)

    if hasattr(mw.form, 'mainToolBar'):
        mw.form.mainToolBar.addAction(action)

        from aqt.qt import QToolButton
        button = mw.form.mainToolBar.widgetForAction(action)
        if isinstance(button, QToolButton):
            from aqt.qt import Qt
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
            button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)

    mw._deep_dive_action = action



# Singleton reference: keeps the window alive and makes sure a single instance
_current_dialog = None
_settings_open_guard = False

_last_rollover = None


def _seed_rollover(*_args):
    global _last_rollover
    try:
        from . import utils

        utils._ROLLOVER_CACHE[0] = None
        _last_rollover = utils.rollover_hour()
    except Exception:
        log_swallowed()


def _on_operation_for_rollover(changes, handler=None):
    """When Anki's "next day starts at" changes, the daily bins of the cache are
    wrong: rebuild it and refresh what is on screen."""
    global _last_rollover
    if not getattr(changes, "config", False):
        return
    try:
        from . import utils

        utils._ROLLOVER_CACHE[0] = None
        new = utils.rollover_hour()
    except Exception:
        return
    if _last_rollover is None:
        _last_rollover = new
        return
    if new == _last_rollover:
        return
    _last_rollover = new
    try:
        from .details.logic import log_info

        log_info(f"Rollover hour changed to {new}: rebuilding stats", tag="STARTUP")
    except Exception:
        log_swallowed()
    try:
        from .details.logic.history_cache import GlobalHistoryCache
        from .details.widgets.pinned.widget_factory.utils import PinnedDataManager

        _discard_parked_dialog()
        PinnedDataManager.clear()
        GlobalHistoryCache.clear_all_cache(callback=lambda *_a: mw.taskman.run_on_main(_refresh_after_rollover))
    except Exception:
        log_swallowed()


def _refresh_after_rollover():
    try:
        from .config import pinned_widgets_disabled

        if not pinned_widgets_disabled():
            from .details.widgets.pinned.main_menu.manager import MainMenuWidgetManager

            if MainMenuWidgetManager.instance_exists():
                MainMenuWidgetManager.instance().refresh()
    except Exception:
        log_swallowed()
    try:
        dlg = _current_dialog
        if dlg is not None and dlg.isVisible():
            dlg.invalidate_view_switch_cache()
            if dlg.view_mode == "time":
                dlg.load_tabs()
            else:
                dlg.load_deck_view()
    except Exception:
        log_swallowed()


# Deep Dive window kept hidden after it is closed, with the state it was closed in. Reopening shows
# it instantly when nothing it displays can have changed; otherwise it is destroyed and a fresh one
# is built.
_parked_dialog = None
_parked_signature = None


def _deep_dive_reuse_signature():
    """Everything a closed Deep Dive window shows depends on: the collection
    (and any change to it), the scheduler day, the selected deck, the add-on
    time spans and Anki's light/dark mode. None if it can't be computed."""
    try:
        from .details.widgets.chart_utils.theme import theme_config_signature

        col = mw.col
        if col is None:
            return None
        conf = ConfigManager(mw).config
        theme_sig = theme_config_signature(conf)
        if theme_sig is None:
            return None
        from .const import Config
        import json

        tabs_sig = json.dumps(conf.get(Config.DETAILS_TABS_DATA), sort_keys=True, default=str)
        return (id(col), col.mod, col.sched.today, col.decks.selected(), theme_sig, tabs_sig)
    except Exception:
        return None


def _on_anki_theme_change():
    """Anki switched between light and dark (by hand, or following the system): restyle an
    open Stats window. Without this only its cards followed and the charts kept the old theme."""

    def _restyle():
        dlg = _current_dialog
        if dlg is None:
            return
        try:
            if not dlg.isVisible():
                return
            from .details.widgets.chart_utils.theme import sync_theme_manager_from_config, theme_already_synced

            conf = dlg.addon_config.config
            if not theme_already_synced(conf):
                sync_theme_manager_from_config(conf, emit=True, source="anki_theme_change")
            dlg.refresh_styles()
        except RuntimeError:
            pass  # window already deleted
        except Exception:
            log_swallowed()

    # After Anki has finished applying its own palette.
    QTimer.singleShot(0, _restyle)


def _discard_parked_dialog(*_args):
    global _parked_dialog, _parked_signature
    dlg = _parked_dialog
    _parked_dialog = None
    _parked_signature = None
    if dlg is None:
        return
    try:
        dlg.deleteLater()
    except RuntimeError:
        pass


def _take_parked_dialog_if_fresh():
    """Return the parked window if it can be shown as is, else None (and
    the parked window, if any, is destroyed)."""
    global _parked_dialog, _parked_signature
    dlg = _parked_dialog
    if dlg is None:
        return None
    sig = _deep_dive_reuse_signature()
    if sig is None or sig != _parked_signature:
        _discard_parked_dialog()
        return None
    try:
        dlg.isVisible()
    except RuntimeError:
        _parked_dialog = None
        _parked_signature = None
        return None
    _parked_dialog = None
    _parked_signature = None
    return dlg

def _open_when_rows_ready(dialog, identifier, title, period_range, tries=40):
    """Open the Deep Dive once the current tab's rows are loaded (tabs fill in the background)."""
    from aqt.qt import QTimer

    def attempt(left):
        try:
            stats = dialog.tab_stats.get(dialog.tab_widget.currentIndex()) or {}
            if stats.get("results") or left <= 0:
                dialog.deep_dive_manager.open_deep_dive(identifier, title, period_range=period_range)
                return
        except RuntimeError:
            return
        QTimer.singleShot(150, lambda: attempt(left - 1))

    QTimer.singleShot(150, lambda: attempt(tries))


def open_details_for(deck=None, period_range=None):
    """Open the Deep Dive on a given deck (or decks) and period.

    deck: a deck id, -1 for deleted cards, a list of deck ids and/or "deleted", or None for the whole collection.
    period_range: a Period value, or None to keep the one the window already uses.
    """
    from .const import Config

    ids = deck
    if isinstance(ids, list):
        nums = [d for d in ids if isinstance(d, int)]
        if "deleted" in ids and not nums:
            ids = -1
        elif len(ids) == 1 and nums:
            ids = nums[0]
        elif not ids:
            ids = None
    if ids is None:
        identifier, title = "[[TOTAL]]", "Total"
    elif ids == -1:
        identifier, title = "Deleted Cards", "Deleted Cards"
    elif isinstance(ids, list):
        identifier, title = ids, f"{len(ids)} decks"
    else:
        identifier = ids
        try:
            title = mw.col.decks.name(ids)
        except Exception:
            title = str(ids)

    on_show_details()
    dialog = _current_dialog
    if dialog is None:
        return
    try:
        if getattr(dialog, "_pending_deep_dive_restore", False):
            # Freshly built window: its first tab load restores the Deep Dive from these values.
            conf = dialog.addon_config.config
            conf[Config.DETAILS_DEEP_DIVE_IDENTIFIER] = identifier
            conf[Config.DETAILS_DEEP_DIVE_TITLE] = title
            dialog.target_deck_id = identifier
            if period_range is not None:
                conf[Config.DETAILS_DEEP_DIVE_PERIOD_RANGE] = period_range
                dialog.target_time_span = period_range
        else:
            if period_range is None:
                period_range = dialog.target_time_span
            dialog.target_deck_id = identifier
            dialog.target_time_span = period_range
            if dialog.view_mode == "deck":
                # In the deck view the deck is the tab, so go to its tab first (or to the time
                # view for several decks) and open once that tab's rows are loaded.
                if isinstance(identifier, list):
                    dialog.toggle_view()
                else:
                    wanted = {"[[TOTAL]]": "collection", "Deleted Cards": "__deleted_cards__"}.get(identifier, identifier)
                    for i in range(dialog.tab_widget.count()):
                        if dialog.tab_widget.widget(i).property("deck_id") == wanted:
                            dialog.tab_widget.setCurrentIndex(i)
                            break
                open_id = identifier
                if not isinstance(identifier, list):
                    open_id = {"Deleted Cards": "__deleted_cards__", "[[TOTAL]]": "collection"}.get(identifier, identifier)
                _open_when_rows_ready(dialog, open_id, title, period_range)
            else:
                dialog.deep_dive_manager.open_deep_dive(identifier, title, period_range=period_range)
    except Exception:
        log_swallowed()


def on_show_details():
    """Open the main DetailedStatsDialog (Non-blocking)."""
    global _current_dialog

    if _current_dialog is not None:
        try:
            if _current_dialog.isVisible():
                if _current_dialog.isMinimized():
                    _current_dialog.showNormal()
                _current_dialog.raise_()
                _current_dialog.activateWindow()
                try:
                    from .details.widgets.pinned.main_menu.manager import MainMenuWidgetManager
                    if MainMenuWidgetManager.instance_exists():
                        MainMenuWidgetManager.instance().set_external_refresh_suspended(False, reason="details_open")
                except Exception:
                    log_swallowed()
                return
        except RuntimeError:
            _current_dialog = None

    reused = _take_parked_dialog_if_fresh()
    if reused is not None:
        try:
            try:
                from .details.widgets.pinned.main_menu.manager import MainMenuWidgetManager
                MainMenuWidgetManager.instance().set_external_refresh_suspended(True, reason="details_open")
            except Exception:
                log_swallowed()
            _current_dialog = reused
            _current_dialog.show()
            _current_dialog.raise_()
            _current_dialog.activateWindow()
            return
        except RuntimeError:
            _current_dialog = None
        finally:
            try:
                from .details.widgets.pinned.main_menu.manager import MainMenuWidgetManager
                if MainMenuWidgetManager.instance_exists():
                    MainMenuWidgetManager.instance().set_external_refresh_suspended(False, reason="details_open")
            except Exception:
                log_swallowed()

    try:
        try:
            from .details.widgets.pinned.main_menu.manager import MainMenuWidgetManager
            MainMenuWidgetManager.instance().set_external_refresh_suspended(True, reason="details_open")
        except Exception:
            log_swallowed()
        from .details import DetailedStatsDialog
        conf_manager = ConfigManager(mw)
        _current_dialog = DetailedStatsDialog(conf_manager, mw)
        _current_dialog._deepdivestats_built_night_mode = _anki_night_mode()

        _current_dialog.finished.connect(_on_dialog_finished)

        _current_dialog.show()
    except Exception as e:
        try:
            from .details.widgets.pinned.main_menu.manager import MainMenuWidgetManager
            MainMenuWidgetManager.instance().set_external_refresh_suspended(False, reason="details_open")
        except Exception:
            log_swallowed()
        log_error(f"Error opening Deep Dive: {e}")
    finally:
        try:
            from .details.widgets.pinned.main_menu.manager import MainMenuWidgetManager
            if MainMenuWidgetManager.instance_exists():
                MainMenuWidgetManager.instance().set_external_refresh_suspended(False, reason="details_open")
        except Exception:
            log_swallowed()

def _on_dialog_finished(result):
    global _current_dialog
    try:
        from .details.widgets.pinned.main_menu.manager import MainMenuWidgetManager
        if MainMenuWidgetManager.instance_exists():
            MainMenuWidgetManager.instance().set_external_refresh_suspended(False, reason="details_open")
    except Exception:
        log_swallowed()
    # Park the closed window for an instant reopen (see _parked_dialog).
    global _parked_dialog, _parked_signature
    closed = _current_dialog
    _current_dialog = None
    if closed is not None and closed is not _parked_dialog:
        _discard_parked_dialog()
        _parked_dialog = closed
        _parked_signature = _deep_dive_reuse_signature()
        if _parked_signature is None or not _closed_on_selected_deck(closed):
            # A fresh window always opens on Anki's selected deck; only reuse
            # this one if that is what it was showing.
            _discard_parked_dialog()


def _anki_night_mode():
    try:
        from aqt.theme import theme_manager

        return bool(theme_manager.night_mode)
    except Exception:
        return None


def _closed_on_selected_deck(dlg):
    try:
        # A light/dark switch while the window was open only half re-themes
        # it; a rebuilt window is always correct.
        if getattr(dlg, "_deepdivestats_built_night_mode", None) != _anki_night_mode():
            return False
        ddm = dlg.deep_dive_manager
        panel_open = hasattr(dlg, "layout_toggle_container") and not dlg.layout_toggle_container.isHidden()
        if not panel_open:
            return False
        return str(getattr(ddm, "last_deck_identifier", None)) == str(mw.col.decks.selected())
    except Exception:
        return False


def on_sync_did_finish():
    """Trigger integrity check after sync."""
    from .details.logic import log_info
    log_info("Anki sync finished. Scheduling integrity check in 1.5s.", tag="SYNC")
    from .details.logic.history_cache import GlobalHistoryCache
    from aqt.qt import QTimer
    QTimer.singleShot(1500, lambda: GlobalHistoryCache().verify_integrity())


def on_webview_message(handled, message, context):
    if message == 'sts_show_details':
        on_show_details()
        return (True, None)
    return handled


def on_top_toolbar_did_init_links(links: list, toolbar):
    """Inject the Deep Dive button into Anki's top bar."""
    from .const import Config, ASSETS_DIR
    import os
    import base64

    conf_manager = ConfigManager(mw)
    toolbar_style_key = getattr(Config, "TOOLBAR_BUTTON_STYLE", "Toolbar_Button_Style")
    toolbar_style_logo = getattr(Config, "TOOLBAR_STYLE_LOGO", "logo")
    toolbar_style_text = getattr(Config, "TOOLBAR_STYLE_TEXT", "text")
    toolbar_style_none = getattr(Config, "TOOLBAR_STYLE_NONE", "none")
    button_style = conf_manager.config.get(toolbar_style_key, toolbar_style_logo)

    if button_style == toolbar_style_none or not conf_manager.config.get(Config.SHOW_TOP_TOOLBAR_BUTTON, True):
        return

    if button_style == toolbar_style_text:
        import html as _html

        custom_text = str(conf_manager.config.get(getattr(Config, "TOOLBAR_BUTTON_TEXT", "Toolbar_Button_Text"), "") or "").strip()
        content_html = _html.escape(custom_text or dev_label("Deep Dive"))
    else:
        icon_path = os.path.join(ASSETS_DIR, "logo_icon.svg")
        try:
            with open(icon_path, "rb") as f:
                svg_data = f.read()
            b64_icon = base64.b64encode(svg_data).decode('utf-8')
            icon_url = f"data:image/svg+xml;base64,{b64_icon}"
            content_html = f'<img src="{icon_url}" style="height: 24px; width: 24px;">'
        except Exception:
            content_html = "Deep Dive"

    # The logo needs a slight downward centering, the text needs a bold weight
    extra_style = "font-weight: bold;" if button_style == toolbar_style_text else "transform: translateY(2.5px);"

    html = (
        f'<a class="nav-link" href="#" onclick="pycmd(\'sts_show_details\'); return false;" '
        f'title="{dev_label("Deep Dive Stats")}" style="color: inherit; text-decoration: none; display: inline-flex; align-items: center; padding: 0 10px; {extra_style}">'
        f'{content_html}</a>'
    )

    # Try to insert between "Stats" and "Sync" (links are usually [Decks, Add, Browse, Stats, Sync]).
    if len(links) >= 1:
        links.insert(-1, html)
    else:
        links.append(html)

