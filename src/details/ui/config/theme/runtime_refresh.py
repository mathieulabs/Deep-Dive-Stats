# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from ....logic.logger import log_swallowed
def refresh_live_data_colors(*, parent_dialog, addon_config, self_widget=None, source=None, emit_theme_runtime=True):
    # Invalidate pie chart module cache so instances reload current config.
    try:
        from ....widgets.charts import pie_chart as _pc
        if hasattr(_pc, "invalidate_pie_chart_color_cache"):
            _pc.invalidate_pie_chart_color_cache()
        else:
            _pc._PIE_CHART_COLORS = None
    except Exception:
        log_swallowed()

    try:
        from ....widgets.pinned.main_menu.manager import MainMenuWidgetManager
        MainMenuWidgetManager.instance().update_styles(config_manager=addon_config)
    except Exception:
        log_swallowed()

    if emit_theme_runtime:
        try:
            from ....widgets.chart_utils.theme import sync_theme_manager_from_config
            sync_theme_manager_from_config(
                addon_config.config,
                emit=True,
                source=source or "data_color_change",
            )
        except Exception:
            log_swallowed()

    try:
        from aqt.qt import QWidget as _QWidget
        for w in parent_dialog.findChildren(_QWidget):
            if hasattr(w, "refresh_data_colors"):
                w.refresh_data_colors()
                w.update()
    except Exception:
        log_swallowed()

    try:
        from aqt.qt import QApplication as _QApplication, QWidget as _QWidget
        app = _QApplication.instance()
        if app is not None:
            for top in app.topLevelWidgets():
                if top is None or top is self_widget or top is parent_dialog:
                    continue
                if not hasattr(top, "findChildren"):
                    continue
                for w in top.findChildren(_QWidget):
                    if hasattr(w, "refresh_data_colors"):
                        w.refresh_data_colors()
                        w.update()
    except Exception:
        log_swallowed()

