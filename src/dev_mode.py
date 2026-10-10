# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Tools for working on the add-on itself (Settings > General > Developer).

Only shown when running from a source checkout. They reset the saved settings, as if the
add-on was just installed, and refresh whatever is already on screen.
"""

import os

from aqt import mw

from .details.logic.logger import log_swallowed
from .config import ConfigManager, clear_config_caches, reload_live_managers


def data_dir() -> str:
    """The add-on's user_files folder (settings, history cache, debug log)."""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "user_files")


def _refresh_after_config_change(source: str) -> None:
    """Make everything that is already on screen or cached pick up the active config."""
    # The settings dialog that triggered this still points readers at its own in-memory copy of the
    # old config. Drop it, otherwise the charts redrawn below would be painted with the old values.
    try:
        from .config import set_live_config_override

        set_live_config_override(None)
    except Exception:
        log_swallowed()
    try:
        from .details.widgets.chart_utils import drawing as _drawing

        _drawing._STYLE_CACHE[0] = 0.0
    except Exception:
        log_swallowed()
    try:
        from .details.widgets.chart_utils.binning import invalidate_binning_level_cache

        invalidate_binning_level_cache()
    except Exception:
        log_swallowed()
    try:
        from .details.widgets.pinned.widget_factory.builders import stat_card as _stat_card

        _stat_card._STAT_VALUE_CACHE.clear()
    except Exception:
        log_swallowed()
    try:
        from .config import read_config_dict
        from .details.widgets.chart_utils.theme import sync_theme_manager_and_notify

        sync_theme_manager_and_notify(read_config_dict(), source=source)
    except Exception:
        log_swallowed()
    try:
        from .details.widgets.pinned.main_menu.manager import MainMenuWidgetManager

        if MainMenuWidgetManager.instance_exists():
            menu = MainMenuWidgetManager.instance()
            menu._mark_config_dirty()
            menu._get_config_manager(force_refresh=True)
            menu.refresh(clear_cache=True)
    except Exception:
        log_swallowed()
    try:
        mw.toolbar.draw()
        mw.reset()
    except Exception:
        log_swallowed()
    # Redo the cache part once the settings windows are gone, for anything painted in between.
    try:
        from aqt.qt import QTimer

        QTimer.singleShot(400, _drop_style_caches)
    except Exception:
        log_swallowed()


def _drop_style_caches() -> None:
    try:
        from .details.widgets.chart_utils import drawing as _drawing

        _drawing._STYLE_CACHE[0] = 0.0
        from .details.widgets.pinned.main_menu.manager import MainMenuWidgetManager

        if MainMenuWidgetManager.instance_exists():
            MainMenuWidgetManager.instance().refresh(clear_cache=True)
    except Exception:
        log_swallowed()


def _remove(path: str) -> int:
    try:
        os.remove(path)
        return 1
    except FileNotFoundError:
        return 0
    except OSError:
        log_swallowed()
        return 0


def reset_profile() -> int:
    """Delete the saved settings of the current Anki profile only. Returns files removed."""
    removed = _remove(ConfigManager(mw)._config_path)
    clear_config_caches()
    reload_live_managers()
    _refresh_after_config_change("reset_profile")
    return removed


def reset_everything() -> int:
    """Delete the saved settings of every Anki profile. Returns the number of files removed."""
    folder = os.path.join(data_dir(), "config")
    removed = 0
    try:
        names = os.listdir(folder)
    except OSError:
        names = []
    for name in names:
        if name.endswith(".json"):
            removed += _remove(os.path.join(folder, name))
    clear_config_caches()
    reload_live_managers()
    _refresh_after_config_change("reset_everything")
    return removed


def open_data_folder() -> None:
    from aqt.qt import QDesktopServices, QUrl

    os.makedirs(data_dir(), exist_ok=True)
    QDesktopServices.openUrl(QUrl.fromLocalFile(data_dir()))
