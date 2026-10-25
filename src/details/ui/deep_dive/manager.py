# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
import re
from aqt.qt import (
    QWidget,
    QObject,
    QTimer,
)

from .. import Config
from .. import Period
from .layout import DeepDiveLayoutMixin
from .charts import DeepDiveChartsMixin
from .stats import DeepDiveStatsMixin
from .controls import DeepDiveControlsMixin
from .runtime.open_flow import open_deep_dive
from .runtime.ui_runtime import show_and_animate
from .runtime.zoom_sync import setup_zoom_sync
from .runtime.widget_settings_runtime import (
    apply_dd_widget_setting_live,
    get_dd_charts_for_section,
    get_dd_widget_setting,
    open_dd_widget_settings,
    reset_dd_widget_size,
    update_dd_widget_setting,
    update_dd_widget_settings_bulk,
)
from ...widgets.chart_utils.theme import get_theme_colors, get_theme_manager
from ...logic.logger import log_swallowed


class DeepDiveEventFilter(QObject):
    def __init__(self, manager):
        super().__init__()
        self.manager = manager
    def eventFilter(self, obj, event):
        return self.manager.eventFilter(obj, event)

class DeepDiveManager(QObject, DeepDiveLayoutMixin, DeepDiveChartsMixin, DeepDiveStatsMixin, DeepDiveControlsMixin):
    def __init__(self, dialog):
        super().__init__()
        self.dialog = dialog
        self.dialog.setProperty("deepdivestats_theme_context", "details")
        self._event_filter_proxy = DeepDiveEventFilter(self)
        self._theme_manager = get_theme_manager()
        self._theme_manager.subscribe(self._on_theme_changed)
        self.addon_config = dialog.addon_config
        self.grid_mode = True
        self.grid_columns = self.addon_config.config.get(Config.DEEP_DIVE_GRID_COLUMNS, 4)
        self.section_collapse_states = {} # Persist collapse state across view changes
        self.last_activity_breakdown = self._get_dd_widget_setting("activity", "breakdown_enabled", True)
        self.last_retention_visibility = self._get_dd_widget_setting("retention", "visibility", {"all": False, "young": True, "mature": True})
        self.last_show_avg = self._get_dd_widget_setting("manager", "show_average", True)
        self.last_avg_active = self._get_dd_widget_setting("manager", "avg_on_active_days", True)
        self.last_show_cumulative = self._get_dd_widget_setting("manager", "show_cumulative", True)
        self.last_sync_zoom = self._get_dd_widget_setting("manager", "sync_zoom", True)  # Sync zoom across all charts by default
        self.last_pie_sep = self.addon_config.config.get(Config.PIE_CHART_SEPARATE_SUSPENDED, True)
        self.last_history_data = []
        self.last_history_range = Period.TOTAL

        self.last_row_data = None
        self.last_deck_identifier = None
        self.last_period_range = None
        self.last_history_context = None

        self.activity_chart = None
        self.stacked_chart = None
        self.retention_chart = None
        self.added_chart = None
        self.dist_chart = None
        self.heatmap_chart = None
        self.hourly_chart = None
        self.future_due_chart = None
        self.review_intervals_chart = None
        self.stability_chart = None
        self.difficulty_chart = None
        self.retrievability_chart = None
        self._build_queue_active = False
        self.last_fsrs_did = "__INIT__"
        self._is_skeleton = True
        self.section_wrappers = {}

        self._loading_seq = 0
        self._drag_source_id = None
        # Full rebuilds build real charts hidden, then reveal once at queue completion.
        self._defer_deep_dive_chart_reveal = False
        self._deep_dive_real_view_shown = False

    def _dialog_gone(self):
        from ...widgets.chart_utils.theme import _qt_deleted

        return _qt_deleted(self.dialog)

    def _on_theme_changed(self, _source=None):
        if self._dialog_gone():
            # Window closed: this manager outlives it until it is collected.
            self._theme_manager.unsubscribe(self._on_theme_changed)
            return
        self._init_theme_vars()
        # Defer the per-widget restyle so Qt finishes processing the parent
        # stylesheet change before we call setStyleSheet on individual children.
        QTimer.singleShot(0, self._apply_controls_theme_deferred)
        try:
            self._refresh_all_grid_headers_theme()
        except Exception:
            log_swallowed()
        try:
            if hasattr(self, "_refresh_chart_control_icons"):
                self._refresh_chart_control_icons()
        except Exception:
            log_swallowed()
        for w in self.dialog.findChildren(QWidget):
            try:
                if hasattr(w, "refresh_data_colors"):
                    w.refresh_data_colors()
                if hasattr(w, "refresh_theme"):
                    w.refresh_theme()
                elif hasattr(w, "update"):
                    w.update()
            except Exception:
                continue

    def _apply_controls_theme_deferred(self):
        if self._dialog_gone():
            return
        try:
            self.apply_deep_dive_theme(self.dialog)
        except Exception:
            log_swallowed()

    def warm_up(self):
        """Warm up lightweight Deep Dive state without mounting visible dashboard widgets."""
        self._init_theme_vars()

        # Do not mount a partial skeleton during warm-up.
        # The real open path will build the visible dashboard once with the right data.

    def _init_theme_vars(self):
        """Initialize common theme variables used across dashboard widgets."""
        t_colors = get_theme_colors(self.dialog)
        is_dark = bool(t_colors.get("is_dark"))
        text_primary = t_colors.get("text_primary", t_colors.get("text"))
        text_secondary = t_colors.get("text_secondary", t_colors.get("text"))
        border_col = t_colors.get("border")
        bg_col = t_colors.get("bg")

        def _hex_or_default(qc, default_hex):
            try:
                return qc.name() if qc is not None else default_hex
            except Exception:
                return default_hex

        text_primary_hex = _hex_or_default(text_primary, "#f4f4f5" if is_dark else "#18181b")
        text_secondary_hex = _hex_or_default(text_secondary, "#a1a1aa" if is_dark else "#71717a")
        border_hex = _hex_or_default(border_col, "#3f3f46" if is_dark else "#d4d4d8")
        bg_hex = _hex_or_default(bg_col, "#18181b" if is_dark else "#ffffff")

        from aqt.qt import QColor
        bg_qc = QColor(bg_hex)
        bg_element = f"rgba({bg_qc.red()}, {bg_qc.green()}, {bg_qc.blue()}, {18 if is_dark else 8})"
        border_subtle = f"rgba({bg_qc.red()}, {bg_qc.green()}, {bg_qc.blue()}, {40 if is_dark else 28})"
        bg_card = f"rgba({bg_qc.red()}, {bg_qc.green()}, {bg_qc.blue()}, {242 if is_dark else 245})"
        self.theme_vars = {
            "is_dark": is_dark,
            "text_primary": text_primary_hex,
            "text_secondary": text_secondary_hex,
            "bg_element": bg_element,
            "border_subtle": border_subtle,
            "bg_card": bg_card,
            "border": border_hex,
        }

    def _clean_title(self, title):
        """Remove tree characters, icons and HTML entities from title strings."""
        if not title: return ""
        t = re.sub(r'(?i)&nbsp;?', ' ', title)
        t = t.replace('\xa0', ' ')

        # Strip leading tree characters, box-drawing characters and ASCII fallbacks like |- or |_, plus Anki tree icons.
        t = re.sub(r'^[▶▼▸▾└─│├┌┐┘┼┬┴\|\-\s]+', '', t)
        t = t.replace('|', '').replace('::', ' // ') # Visual separator

        return t.strip()

    def open_deep_dive(self, deck_identifier, title, period_range=None):
        return open_deep_dive(self, deck_identifier, title, period_range)

    def _get_dd_widget_setting(self, section_key, setting_key, default=None):
        return get_dd_widget_setting(self, section_key, setting_key, default)

    def _open_dd_widget_settings(self, section_key, widget):
        return open_dd_widget_settings(self, section_key, widget)

    def _get_dd_charts_for_section(self, section_key):
        return get_dd_charts_for_section(self, section_key)

    def _apply_dd_widget_setting_live(self, section_key, key, value):
        return apply_dd_widget_setting_live(self, section_key, key, value)

    def _update_dd_widget_setting(self, section_key, key, value, replace_all=False, refresh=True, write=True):
        return update_dd_widget_setting(
            self,
            section_key,
            key,
            value,
            replace_all=replace_all,
            refresh=refresh,
            write=write,
        )

    def _reset_dd_widget_size(self, section_key):
        return reset_dd_widget_size(self, section_key)

    def _update_dd_widget_settings_bulk(self, section_key, updates, refresh=True, write=True):
        return update_dd_widget_settings_bulk(self, section_key, updates, refresh=refresh, write=write)

    def _show_and_animate(self):
        return show_and_animate(self)

    def _setup_zoom_sync(self):
        return setup_zoom_sync(self)





