# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Settings as one web page (web/settings.js): General, Time Spans, Colors and Decks in a window of its own.

Python keeps the values and the page shows them: each change goes to a handler here, which edits the config of the
window that opened Settings (so the open windows preview it live), and answers with the new state of the page.
Save writes the config; Cancel (or closing the window) puts the config back as it was when Settings opened.
"""

from __future__ import annotations

import copy
import json
import os
from urllib.parse import quote

from aqt import mw
from aqt.qt import QColor, QDialog, QKeySequence, QTimer, QVBoxLayout, Qt

from ..const import COLOR_DEFAULTS, Config, Period, ThemePalettes
from ..details.logic.logger import log_error, log_swallowed
from .bridge import Bridge
from .trace import dev_flag, page_log
from ..i18n import N_

# Texts of settings.js that check_translations cannot read there (quotes inside quotes): kept in the catalogs.
_PAGE_TEXTS = (N_("Pinned widgets use an independent theme. Configure it in the 'Pinned' tab."),)

_WEB_DIR = "src/web_ui/web"
_CSS = ["dd.css", "settings.css"]
_JS = ["dd-core.js", "settings_decks.js", "settings.js"]

# keys of the user's uncommitted-safe settings (present in recent configs only)
_AXIS_ANIM = getattr(Config, "CHART_AXIS_ANIM", "Chart_Axis_Anim")
_NUM_ANIM = getattr(Config, "STAT_NUM_ANIM", "Stat_Num_Anim")

_OPEN = []  # the window shown (find_open)


def _url(addon, name):
    return f"/_addons/{quote(addon)}/{_WEB_DIR}/{name}"


def find_open():
    """The settings window when one is open, else None."""
    for dlg in list(_OPEN):
        try:
            if dlg.isVisible():
                return dlg
        except Exception:
            _OPEN.remove(dlg)
    return None


def _deck_tree():
    from .deck_picker import deck_tree

    return deck_tree()


# ---- General: the values the page sets directly, with what each one does at once ----
def _general_keys():
    """{config key: default}. Values not listed here are refused."""
    D = Config.DEFAULT_CONFIG
    keys = [
        Config.LANGUAGE, Config.STATS_PRECISION, Config.USE_THOUSANDS_SEPARATOR, Config.SHOW_CHART_HELP,
        Config.INTERACTION_MODE,
        Config.ANIMATION_SCOPE, Config.CHART_APPEAR_ANIMATION, Config.ZOOM_ANIMATION, _AXIS_ANIM, _NUM_ANIM,
        Config.DEEP_DIVE_TRANSITION_STYLE, Config.PINNED_TRANSITION_STYLE, Config.DEEP_DIVE_ANIMATION_SPEED,
        Config.PINNED_ANIMATION_SPEED, Config.ADAPTIVE_CHART_BINNING, Config.CHART_BINNING_SCALE,
        Config.DETAILS_TABLE_SHOW, Config.DETAILS_TABLE_DRAWER_AUTO_CLOSE,
        Config.DETAILS_TABLE_DRAWER_SHORTCUT, Config.SHOW_EMPTY_CHARTS, Config.DEEP_DIVE_CHARTS_COLLAPSIBLE,
        Config.DEEP_DIVE_FILL_HEIGHT, Config.DEEP_DIVE_SHARED_ROW_HEIGHT, Config.CHART_LINE_OPACITY,
        Config.CHART_TOTAL_LINE, Config.CHART_BAR_GRADIENT, Config.CHART_SHOW_GRID, Config.GLOBAL_ROW_HEIGHT,
        Config.TABLE_ZEBRA, Config.TOOLBAR_BUTTON_STYLE, Config.TOOLBAR_BUTTON_TEXT, Config.OPEN_SHORTCUT,
        Config.PINNED_POSITION_TOP, Config.PINNED_POSITION_TOP_DECK, Config.PINNED_CHARTS_COLLAPSIBLE,
        Config.PINNED_CARD_LABELS, Config.PINNED_EMPTY_HINT, Config.PINNED_MARGIN_SIDE, Config.PINNED_MARGIN_TOP,
        Config.PINNED_MARGIN_BOTTOM, Config.PINNED_SECTION_SPACING, Config.SHOW_FULL_DECK_NAME,
    ]
    fallback = {Config.LANGUAGE: "auto", Config.STATS_PRECISION: 2, Config.INTERACTION_MODE: "auto", Config.ANIMATION_SCOPE: "all",
                _AXIS_ANIM: "slide", _NUM_ANIM: "count", Config.DEEP_DIVE_TRANSITION_STYLE: "morph",
                Config.PINNED_TRANSITION_STYLE: "morph", Config.DEEP_DIVE_ANIMATION_SPEED: "normal",
                Config.PINNED_ANIMATION_SPEED: "normal", Config.CHART_BINNING_SCALE: 100,
                Config.DETAILS_TABLE_DRAWER_SHORTCUT: "T", Config.GLOBAL_ROW_HEIGHT: 30,
                Config.TOOLBAR_BUTTON_STYLE: Config.TOOLBAR_STYLE_LOGO, Config.TOOLBAR_BUTTON_TEXT: "Deep Dive",
                Config.OPEN_SHORTCUT: "", Config.SHOW_FULL_DECK_NAME: False}
    return {k: D.get(k, fallback.get(k)) for k in keys}


def _norm_keys(text):
    """One key combination in Qt's portable form ("" when none or not a valid one)."""
    text = str(text or "").split(",")[0].strip()
    if not text:
        return ""
    seq = QKeySequence(text)
    if seq.isEmpty():
        return ""
    return seq.toString(QKeySequence.SequenceFormat.PortableText).split(",")[0].strip()


class WebSettingsDialog(QDialog):
    """host: the window Settings was opened from (the web Deep Dive, or a small stand-in from the main screen):
    addon_config, get_tabs_config(), save_tabs_config(), update_dashboard_visibility(), refresh_styles()."""

    def __init__(self, host, start_tab=None):
        super().__init__(host if hasattr(host, "isVisible") else mw)
        from ..config import set_live_config_override
        from ..i18n import tr

        self.parent_dialog = host
        self.addon_config = host.addon_config
        self._start_tab = start_tab
        self._cancel_restored = False
        self.setWindowTitle(tr("Settings"))
        from ..window_icon import addon_icon

        addon_icon(self)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowMaximizeButtonHint)
        conf = self.addon_config.config
        self.tabs_data = copy.deepcopy(host.get_tabs_config())
        self._initial_tabs = copy.deepcopy(self.tabs_data)
        self._initial_config = copy.deepcopy(conf)
        from ..config import pinned_widgets_disabled

        self._initial_pinned_off = bool(pinned_widgets_disabled())
        # the Decks part is kept here and put in the config on Save
        self._excluded = list(conf.get(Config.EXCLUDED_DECKS, []) or [])
        self._colors = dict(conf.get(Config.DECK_COLORS, {}) or {})
        self._dates = list(conf.get(Config.EXCLUDED_DATES, []) or [])
        set_live_config_override(conf)

        screen = (host.screen() if hasattr(host, "screen") else None) or mw.screen() or mw.app.primaryScreen()
        geom = screen.availableGeometry()
        from .win_size import size_window
        size_window(self, geom, (min(1080, int(geom.width() * 0.9)), min(860, int(geom.height() * 0.88))),
                    (min(640, geom.width() - 40), min(480, geom.height() - 40)))
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        from aqt.webview import AnkiWebView

        mw.addonManager.setWebExports(__name__, _WEB_DIR + "/.*")
        self._addon = mw.addonManager.addonFromModule(__name__)
        self.webview = AnkiWebView(parent=self, title="deep_dive_settings")
        lay.addWidget(self.webview)
        self.bridge = Bridge(self.webview, self)
        for name, fn in (
            ("init", self._init), ("set", self._set), ("span", self._span), ("columns", self._columns),
            ("theme", self._theme_action), ("data_color", self._data_color), ("backdrop", self._backdrop),
            ("decks_set", self._decks_set), ("profiles", self._profiles), ("share", self._share), ("dev", self._dev),
            ("save", lambda: self._later(self._save)), ("cancel", lambda: self._later(self.reject)),
            ("pick", lambda what, key=None, pinned=False: self._later(lambda: self._pick(what, key, pinned))),
            ("open_link", self._open_link),
        ):
            self.bridge.register(name, fn)
        self._bd_timer = QTimer(self)
        self._bd_timer.setSingleShot(True)
        self._bd_timer.setInterval(15)
        self._bd_timer.timeout.connect(self._apply_backdrop)
        self._bin_timer = QTimer(self)
        self._bin_timer.setSingleShot(True)
        self._bin_timer.setInterval(150)
        self._bin_timer.timeout.connect(self._apply_binning_scale)
        self._load()
        _OPEN.append(self)

    # ---- page ----
    def _load(self):
        base = os.path.join(os.path.dirname(__file__), "web")
        try:
            q = "?v=" + str(int(max(os.path.getmtime(os.path.join(base, n)) for n in _CSS + _JS)))
        except Exception:
            q = ""
        self.webview.stdHtml('<div id="dds-root"></div><script>' + dev_flag() + 'DD.settingsBoot && DD.settingsBoot();</script>',
                             css=[_url(self._addon, n) + q for n in _CSS],
                             js=[_url(self._addon, n) + q for n in _JS])

    def _later(self, fn):
        QTimer.singleShot(0, fn)
        return True

    def show_tab(self, name):
        self.bridge.push("show_tab", str(name or ""))

    def _page_theme(self):
        from .theme import build_theme

        return build_theme("details", self.addon_config.config)

    def refresh_styles(self):
        """The theme changed: the page takes it (its own backdrop shows the Window Background as it is set)."""
        try:
            self.bridge.push("settings_theme", self._page_theme())
        except Exception as e:
            page_log(f"settings theme push: {e!r}")

    def _push_state(self):
        try:
            self.bridge.push("state", self._state())
        except Exception as e:
            page_log(f"settings state push: {e!r}")

    def _init(self):
        from ..config import is_dev_build
        from ..i18n import web_catalog

        try:
            i18n = web_catalog()
        except Exception:
            i18n = {}
        out = self._state()
        out.update({"theme": self._page_theme(), "i18n": i18n, "decks": {"decks": _deck_tree(), "excluded": self._excluded,
                    "colors": self._colors, "dates": self._dates}, "start": self._start_tab or "",
                    "dev": is_dev_build(), "K": self._key_names()})
        return out

    @staticmethod
    def _key_names():
        """{Config attribute name: config key} of the General settings, so the page names them as Python does."""
        allowed = _general_keys()
        out = {n: getattr(Config, n) for n in dir(Config)
               if n.isupper() and isinstance(getattr(Config, n), str) and getattr(Config, n) in allowed}
        out.update({"CHART_AXIS_ANIM": _AXIS_ANIM, "STAT_NUM_ANIM": _NUM_ANIM})
        return out

    # ---- the state shown by the page ----
    def _state(self):
        return {"general": self._general_state(), "spans": self._spans_state(), "colors": self._colors_state(),
                "backdrop": self._backdrop_state()}

    def _general_state(self):
        from ..config import pinned_widgets_disabled
        from ..i18n import ENGLISH, LANGUAGES, language, resolve_language

        conf = self.addon_config.config
        vals = {k: conf.get(k, d) for k, d in _general_keys().items()}
        if not conf.get(Config.SHOW_TOP_TOOLBAR_BUTTON, True):
            vals[Config.TOOLBAR_BUTTON_STYLE] = Config.TOOLBAR_STYLE_NONE
        lang = str(vals.get(Config.LANGUAGE) or "auto")
        try:
            from ..details.ui.details_dialog.links import TRANSLATIONS_URL
        except Exception:
            TRANSLATIONS_URL = ""
        return {
            "values": vals,
            "languages": [[code, name] for code, name in LANGUAGES.items()],
            "lang_restart": resolve_language(lang) != language(),
            "lang_note": resolve_language(lang) != ENGLISH,
            "translations_url": bool(TRANSLATIONS_URL),
            "open_conflict": self._shortcut_conflict(vals.get(Config.OPEN_SHORTCUT) or ""),
            "pinned_off": bool(pinned_widgets_disabled()),
            "toolbar_styles": [Config.TOOLBAR_STYLE_LOGO, Config.TOOLBAR_STYLE_TEXT, Config.TOOLBAR_STYLE_NONE],
        }

    @staticmethod
    def _shortcut_conflict(text):
        if not text:
            return ""
        from aqt.qt import QAction

        mine = getattr(mw, "_deep_dive_open_action", None)
        for act in mw.findChildren(QAction):
            if act is mine:
                continue
            for key in act.shortcuts():
                if key.toString(QKeySequence.SequenceFormat.PortableText) == text:
                    return act.text().replace("&", "").split("\t")[0].strip()
        return ""

    def _spans_state(self):
        from ..details.logic.tabs.columns import COLUMNS, GROUPS, table_columns, table_show_counts
        from ..details.logic.spans.range_options import RANGE_OPTIONS
        from ..i18n import tr_name

        conf = self.addon_config.config
        tabs = []
        for t in self.tabs_data:
            d = dict(t)
            d["shown_title"] = tr_name(str(t.get("title", "") or ""))
            tabs.append(d)
        return {
            "tabs": tabs,
            "ranges": [[tr_name(label), value] for label, value in RANGE_OPTIONS],
            "custom": Period.CUSTOM,
            "columns": [{"key": k, "label": tr_name(label), "group": g} for k, label, g, _f in COLUMNS],
            "groups": [[g, tr_name(label)] for g, label in GROUPS],
            "shown": list(table_columns(conf)),
            "counts": bool(table_show_counts(conf)),
        }

    def _colors_state(self):
        from aqt.theme import theme_manager

        from ..details.ui.config.theme.pinned_mode_controls import get_pinned_theme_mode_from_config
        from ..details.logic.theme.pinned_theme_state import (
            get_current_pinned_theme_base_palette,
            get_current_pinned_theme_effective_base_mode,
            get_current_pinned_theme_effective_palette,
        )
        from ..details.logic.theme.preset_helpers import (
            get_custom_theme_presets,
            is_custom_theme_preset_selected,
            resolve_effective_theme_palette,
            resolve_theme_preset_palette,
        )
        from ..details.logic.theme.pinned_theme_state import get_current_pinned_theme_base_mode
        from ..details.logic.theme.theme_state import (
            get_current_theme_base_mode,
            get_current_theme_base_palette,
            get_current_theme_effective_base_mode,
        )
        from ..details.ui.config.theme.ui_helpers import get_builtin_theme_defs, get_theme_color_keys
        from ..i18n import tr

        conf = self.addon_config.config
        night = bool(theme_manager.get_night_mode())
        custom = get_custom_theme_presets(conf)
        presets = []
        defs = list(get_builtin_theme_defs()) + [(k, str(e.get("name", k))) for k, e in custom.items() if isinstance(e, dict)]
        for key, name in defs:
            pal = resolve_theme_preset_palette(preset_key=key, custom_presets=custom, is_night_mode=night)
            presets.append({"key": key, "name": name, "custom": key in custom,
                            "dark": QColor(pal.get("bg_root", "#222222")).lightness() < 128,
                            "pal": {k: pal.get(k) for k in ("bg_root", "bg_surface", "bg_element", "accent",
                                                             "text_primary", "text_secondary", "border_subtle",
                                                             "total_line")}})
        keys = get_theme_color_keys()

        def color_rows(base, eff, custom_map):
            rows = []
            for key, label in keys:
                b = base.get(key, ThemePalettes.CHARCOAL_PALETTE.get(key, "#000000"))
                e = eff.get(key, b)
                rows.append({"key": key, "label": label, "hex": str(e),
                             "changed": isinstance(custom_map, dict) and key in custom_map and str(e).lower() != str(b).lower()})
            return rows

        preset = conf.get(Config.THEME_PRESET, ThemePalettes.NATIVE)
        base = get_current_theme_base_palette(self)
        eff = resolve_effective_theme_palette(base, conf)
        details = {"preset": preset, "native": preset == ThemePalettes.NATIVE,
                   "mode": get_current_theme_effective_base_mode(self),
                   "colors": color_rows(base, eff, conf.get(Config.THEME_CUSTOM_COLORS, {})),
                   "custom": is_custom_theme_preset_selected(current_key=preset, custom_presets=custom)}
        ppreset = conf.get(Config.PINNED_THEME_PRESET, ThemePalettes.NATIVE)
        pbase = get_current_pinned_theme_base_palette(self)
        pinned = {"preset": ppreset, "native": ppreset == ThemePalettes.NATIVE,
                  "mode": get_current_pinned_theme_effective_base_mode(self),
                  "colors": color_rows(pbase, get_current_pinned_theme_effective_palette(self),
                                       conf.get(Config.PINNED_THEME_CUSTOM_COLORS, {}))}
        details["adapt_warn"] = self._adapt_warn(preset, details["mode"], get_current_theme_base_mode(self), night)
        pinned["adapt_warn"] = self._adapt_warn(ppreset, pinned["mode"], get_current_pinned_theme_base_mode(self), night)
        pmode = get_pinned_theme_mode_from_config(conf)
        mismatch = ""
        if pmode == "linked" and details["mode"] == ThemePalettes.MODE_LIGHT and night:
            mismatch = tr("This theme is light while Anki is dark: the pinned widgets on Anki's main screen will be light too.")
        elif pmode == "linked" and details["mode"] == ThemePalettes.MODE_DARK and not night:
            mismatch = tr("This theme is dark while Anki is light: the pinned widgets on Anki's main screen will be dark too.")
        return {"presets": presets, "details": details, "pinned": pinned, "pinned_mode": pmode, "mismatch": mismatch,
                "data": {"details": self._data_rows(False), "pinned": self._data_rows(True)}}

    @staticmethod
    def _adapt_warn(preset, mode, base, night):
        """The Graph Adaptation Mode against the theme's own mode: a light theme drawn with the dark adaptation (or
        the other way, "Follow Anki" included) keeps its colors, but its cards, borders and grid are made for the
        other background. {text, btn, fix}: the note and the button that puts the theme's own mode back; None when
        they agree (or for Anki's own theme, which always follows Anki)."""
        from ..i18n import tr

        if preset == ThemePalettes.NATIVE or base not in (ThemePalettes.MODE_DARK, ThemePalettes.MODE_LIGHT):
            return None
        dark = night if mode == ThemePalettes.MODE_NATIVE else mode == ThemePalettes.MODE_DARK
        if dark == (base == ThemePalettes.MODE_DARK):
            return None
        if base == ThemePalettes.MODE_LIGHT:
            return {"fix": base, "btn": tr("Use Light Adaptation"),
                    "text": tr("This theme is light but adapts to a dark background: its cards, borders and grid may look off.")}
        return {"fix": base, "btn": tr("Use Dark Adaptation"),
                "text": tr("This theme is dark but adapts to a light background: its cards, borders and grid may look off.")}

    # data colors (stat, card type, button, chart colors): of the Deep Dive theme, or of the pinned widgets' own theme
    def _data_groups(self):
        from ..i18n import tr

        C = Config
        return [
            (tr("Stat Colors"), [(C.COLOR_TIME, tr("Total Time")), (C.COLOR_AVG_TIME, tr("Time/Card")),
                                 (C.COLOR_REVIEWS, tr("Reviews")), (C.COLOR_RETENTION, tr("Retention")),
                                 (C.COLOR_STREAK, tr("Streak")), (C.COLOR_ACTIVE_DAYS, tr("Active Days"))]),
            (tr("Card Type Colors"), [(C.COLOR_MATURE, tr("Mature")), (C.COLOR_YOUNG, tr("Young")),
                                      (C.COLOR_LEARN, tr("Learning")), (C.COLOR_RELEARN, tr("Relearning")),
                                      (C.COLOR_CRAM, tr("Filtered")), (C.COLOR_NEW, tr("New")),
                                      (C.COLOR_SUSPENDED, tr("Suspended")), (C.COLOR_BURIED, tr("Buried"))]),
            (tr("Button Colors (Again / Hard / Good / Easy)"), [(C.COLOR_AGAIN, tr("Again")), (C.COLOR_HARD, tr("Hard")),
                                                                 (C.COLOR_GOOD, tr("Good")), (C.COLOR_EASY, tr("Easy"))]),
            (tr("Chart Colors"), [(C.COLOR_BAR, tr("Bar / Line")), (C.COLOR_FUTURE_DUE, tr("Future Due")),
                                  (C.COLOR_BACKLOG, tr("Backlog")), (C.COLOR_DELETED, tr("Deleted")),
                                  (C.HEATMAP_COLOR, tr("Heatmap")), (C.COLOR_GRADIENT_LOW, tr("Gradient Low")),
                                  (C.COLOR_GRADIENT_HIGH, tr("Gradient High"))]),
        ]

    def _data_baseline(self, pinned):
        from ..details.ui.config.theme.data_color_ops import get_data_color_baseline
        from ..details.logic.theme.preset_helpers import get_custom_theme_presets

        conf = self.addon_config.config
        if not pinned:
            return get_data_color_baseline(conf)
        key = conf.get(Config.PINNED_THEME_PRESET, ThemePalettes.NATIVE)
        entry = get_custom_theme_presets(conf).get(key, {})
        if isinstance(entry, dict) and isinstance(entry.get("data_colors"), dict):
            return {**COLOR_DEFAULTS, **entry["data_colors"]}
        return ThemePalettes.get_preset_data_colors(key)

    def _data_current(self, key, pinned):
        from ..const.theme.color_resolver import get_color

        conf = self.addon_config.config
        base = self._data_baseline(pinned).get(key, COLOR_DEFAULTS.get(key, "#888888"))
        if pinned:
            return str(get_color(conf, key, "pinned"))
        v = conf.get(key, base)
        return v if isinstance(v, str) and v.strip() else base

    def _data_rows(self, pinned):
        base = self._data_baseline(pinned)
        out = []
        for title, rows in self._data_groups():
            items = []
            for key, label in rows:
                cur = self._data_current(key, pinned)
                b = str(base.get(key, "") or "")
                items.append({"key": key, "label": label, "hex": cur, "changed": bool(b) and cur.lower() != b.lower()})
            out.append({"title": title, "rows": items})
        return out

    def _backdrop_state(self):
        from ..details.ui.theme.backdrop import BACKDROP_PRESETS, get_backdrop_settings, glow_colors, matching_preset
        from ..details.ui.theme.design_overrides import _colors
        from ..details.logic.theme.palette import get_theme_palette
        from ..details.ui.theme.theme_mode import get_theme_effective_is_dark

        conf = self.addon_config.config
        s = get_backdrop_settings(conf)
        try:
            accent = _colors(get_theme_effective_is_dark(conf), get_theme_palette(conf))["accent"]
        except Exception:
            accent = "#3b82f6"
        c1, _c2 = glow_colors(accent, s)
        return {"settings": s, "preset": matching_preset(s), "presets": ["off"] + list(BACKDROP_PRESETS.keys()),
                "color": c1, "auto": not s.get("color1")}

    # ---- General ----
    def _set(self, key, value):
        allowed = _general_keys()
        if key not in allowed and key != "pinned_off":
            raise ValueError(f"unknown setting {key!r}")
        ac = self.addon_config
        conf = ac.config
        C = Config

        def keep(k, v):
            try:
                ac.set_value(k, v)
            except Exception:
                log_swallowed()

        if key == "pinned_off":
            from ..config import set_pinned_widgets_disabled

            set_pinned_widgets_disabled(bool(value))
            return self._general_state()
        default = allowed[key]
        if isinstance(default, bool):
            value = bool(value)
        elif isinstance(default, int):
            try:
                value = int(value)
            except (TypeError, ValueError):
                value = default
        elif value is None:
            value = default
        else:
            value = str(value)
        if key in (C.OPEN_SHORTCUT, C.DETAILS_TABLE_DRAWER_SHORTCUT):
            value = _norm_keys(value)
        if key == C.STATS_PRECISION:
            value = max(0, min(4, value))
        if key == C.GLOBAL_ROW_HEIGHT:
            value = max(10, min(200, value))
        if key in (C.PINNED_MARGIN_SIDE, C.PINNED_MARGIN_TOP, C.PINNED_MARGIN_BOTTOM, C.PINNED_SECTION_SPACING):
            value = max(0, min(200, value))
        if key == C.TOOLBAR_BUTTON_TEXT:
            value = value[:40]
        conf[key] = value

        if key == C.LANGUAGE:
            keep(key, value)
        elif key in (C.USE_THOUSANDS_SEPARATOR, C.SHOW_CHART_HELP):
            self._host_call("update_dashboard_visibility")
        elif key == C.ADAPTIVE_CHART_BINNING:
            keep(key, value)
            self._refresh_binning_live()
        elif key == C.CHART_BINNING_SCALE:
            conf[key] = max(50, min(200, value))
            self._bin_timer.start()
        elif key == C.DETAILS_TABLE_SHOW:
            try:
                ac.write_config_vals({key: value})
            except Exception:
                log_swallowed()
        elif key == C.DETAILS_TABLE_DRAWER_AUTO_CLOSE:
            try:
                ac.write_config_vals({key: value})
            except Exception:
                log_swallowed()
        elif key == C.DETAILS_TABLE_DRAWER_SHORTCUT:
            try:
                ac.write_config_vals({key: value})
            except Exception:
                log_swallowed()
        elif key in (C.SHOW_EMPTY_CHARTS, C.DEEP_DIVE_CHARTS_COLLAPSIBLE, C.DEEP_DIVE_FILL_HEIGHT,
                     C.DEEP_DIVE_SHARED_ROW_HEIGHT):
            keep(key, value)
        elif key in (C.CHART_LINE_OPACITY, C.CHART_TOTAL_LINE, C.CHART_BAR_GRADIENT, C.CHART_SHOW_GRID):
            self._repaint_charts()
        elif key == C.TABLE_ZEBRA:
            pass
        elif key == C.TOOLBAR_BUTTON_STYLE:
            conf[C.SHOW_TOP_TOOLBAR_BUTTON] = value != C.TOOLBAR_STYLE_NONE
        elif key in (C.PINNED_POSITION_TOP, C.PINNED_POSITION_TOP_DECK):
            self.save_global_config(key, value)
        elif key == C.PINNED_CHARTS_COLLAPSIBLE:
            keep(key, value)
        elif key == C.PINNED_CARD_LABELS:
            self.save_global_config(key, value)
        elif key == C.PINNED_EMPTY_HINT:
            self.save_global_config(key, value)
            try:
                from ..details.widgets.pinned.main_menu.manager import MainMenuWidgetManager

                if MainMenuWidgetManager.instance_exists():
                    pm = MainMenuWidgetManager.instance()
                    pm.refresh()
            except Exception:
                log_swallowed()
        elif key in (C.PINNED_MARGIN_SIDE, C.PINNED_MARGIN_TOP, C.PINNED_MARGIN_BOTTOM, C.PINNED_SECTION_SPACING):
            keep(key, value)
        return self._general_state()

    def _host_call(self, name):
        fn = getattr(self.parent_dialog, name, None)
        if callable(fn):
            try:
                fn()
            except Exception:
                log_swallowed()

    def _repaint_charts(self):
        try:
            from ..details.widgets.chart_utils import drawing as _drawing

            _drawing._STYLE_CACHE[0] = 0.0
        except Exception:
            log_swallowed()
        try:
            from .live_preview import chart_style_changed

            chart_style_changed(self.addon_config.config)
        except Exception:
            log_swallowed()

    def _refresh_binning_live(self):
        try:
            from ..details.ui.config.shared.binning_live_refresh import refresh_binning_live

            refresh_binning_live(self)
        except Exception:
            log_swallowed()

    def _apply_binning_scale(self):
        conf = self.addon_config.config
        try:
            self.addon_config.write_config_vals({Config.CHART_BINNING_SCALE: conf.get(Config.CHART_BINNING_SCALE, 100)})
        except Exception:
            log_swallowed()
        self._refresh_binning_live()

    def save_global_config(self, key, value):
        """A setting that the pinned widgets show live (as the Qt dialog's save_global_config)."""
        self.addon_config.config[key] = value
        self._refresh_live_data_colors(source=f"config:{key}")
        self._host_call("update_dashboard_visibility")

    def _refresh_live_data_colors(self, source=None, emit_theme_runtime=True):
        try:
            from ..details.ui.config.theme.runtime_apply import refresh_live_data_colors_runtime

            refresh_live_data_colors_runtime(self, source=source, emit_theme_runtime=emit_theme_runtime)
        except Exception:
            log_swallowed()

    # ---- Time Spans ----
    def _span(self, action, index=None, key=None, value=None):
        from ..details.logic.tabs import DEFAULT_DETAILS_TABS
        from ..details.logic.spans.tab_mutations import append_new_tab, remove_tab, set_tab_field

        tabs = self.tabs_data
        if action == "set":
            allowed = {"enabled", "title", "range", "custom_type", "days", "start_date", "end_date", "to_today",
                       "use_decimal"}
            if key not in allowed:
                raise ValueError(f"unknown span field {key!r}")
            if key == "days":
                try:
                    value = max(1, min(9999, int(value)))
                except (TypeError, ValueError):
                    value = 7
            if key == "to_today":
                set_tab_field(tabs, int(index), "to_today", bool(value))
                if value:
                    set_tab_field(tabs, int(index), "end_date", "")
            else:
                set_tab_field(tabs, int(index), key, value)
        elif action == "add":
            append_new_tab(tabs)
        elif action == "remove":
            remove_tab(tabs, int(index), min_count=1)
        elif action == "move":
            i, j = int(index), int(value)
            if 0 <= i < len(tabs) and 0 <= j < len(tabs):
                tabs.insert(j, tabs.pop(i))
        elif action == "reset":
            self.tabs_data = copy.deepcopy(DEFAULT_DETAILS_TABS)
        return self._spans_state()

    def _columns(self, keys=None, counts=None, reset=False):
        from ..details.logic.tabs.columns import (
            DEFAULT_COLUMNS,
            DEFAULT_SHOW_COUNTS,
            KEYS,
            apply_to_spans,
            set_table_columns,
        )

        if reset:
            keys, counts = list(DEFAULT_COLUMNS), DEFAULT_SHOW_COUNTS
        keys = [k for k in (keys or []) if k in KEYS]
        conf = self.addon_config.config
        set_table_columns(conf, keys, bool(counts))
        apply_to_spans(self.tabs_data, keys, bool(counts))
        return self._spans_state()

    # ---- Colors: themes ----
    # (the theme helpers of the Qt dialog call these back: nothing to redraw here, the page gets the new state)
    def _refresh_theme_color_controls(self):
        pass

    _refresh_theme_base_mode_control = _refresh_pinned_theme_color_controls = _refresh_theme_color_controls
    _refresh_pinned_theme_base_mode_control = _refresh_data_color_controls = _refresh_theme_color_controls

    def _apply_theme_change(self):
        from ..details.ui.config.theme.runtime_apply import apply_theme_change

        apply_theme_change(self)

    def _apply_pinned_theme_runtime(self, source="pinned_theme_change"):
        from ..details.ui.config.theme.runtime_apply import apply_pinned_theme_runtime

        apply_pinned_theme_runtime(self, source)

    def _theme_action(self, action, key=None, mode=None, name=None, pinned=False):
        from ..details.logic.theme import pinned_theme_state, theme_state
        from ..details.ui.config.theme.data_color_ops import get_current_data_colors
        from ..details.ui.config.theme.pinned_mode_controls import set_pinned_theme_mode_in_config
        from ..details.logic.theme.preset_helpers import (
            get_custom_theme_presets,
            is_builtin_theme_preset_key,
            resolve_effective_theme_palette,
        )
        from ..details.logic.theme.preset_mutations import (
            delete_selected_custom_theme_preset,
            save_new_custom_theme_preset,
            select_theme_preset,
            update_selected_custom_theme_preset,
        )

        conf = self.addon_config.config
        if action == "preset" and not pinned:
            select_theme_preset(conf, key)
            entry = get_custom_theme_presets(conf).get(key, {})
            if isinstance(entry, dict) and isinstance(entry.get("data_colors"), dict):
                colors = {**COLOR_DEFAULTS, **entry["data_colors"]}
            else:
                colors = ThemePalettes.get_preset_data_colors(key)
            for k, v in colors.items():
                conf[k] = v
            self._apply_theme_change()
        elif action == "preset" and pinned:
            conf[Config.PINNED_THEME_PRESET] = key
            conf[Config.PINNED_THEME_IS_CUSTOM] = False
            conf[Config.PINNED_THEME_CUSTOM_COLORS] = {}
            conf[Config.PINNED_THEME_CUSTOM_BASE_MODE] = None
            self._apply_theme_change()
        elif action == "mode" and not pinned:
            theme_state.on_theme_base_mode_changed(self, mode)
        elif action == "mode" and pinned:
            pinned_theme_state.on_pinned_theme_base_mode_changed(self, mode)
        elif action == "reset_color":
            if pinned:
                base = pinned_theme_state.get_current_pinned_theme_base_palette(self)
                pinned_theme_state.set_pinned_theme_override_color(self, key, base.get(key, "#000000"))
            else:
                base = theme_state.get_current_theme_base_palette(self)
                theme_state.set_theme_override_color(self, key, base.get(key, "#000000"))
        elif action == "pinned_mode":
            set_pinned_theme_mode_in_config(self, mode)
            try:
                self.addon_config.write_config()
            except Exception:
                log_swallowed()
            self._apply_pinned_theme_runtime(source="pinned_theme_mode")
        elif action in ("save_preset", "update_preset", "delete_preset"):
            current = conf.get(Config.THEME_PRESET, ThemePalettes.NATIVE)
            custom = conf.get(Config.THEME_CUSTOM_PRESETS, {})
            if not isinstance(custom, dict):
                custom = {}
                conf[Config.THEME_CUSTOM_PRESETS] = custom
            palette = resolve_effective_theme_palette(theme_state.get_current_theme_base_palette(self), conf)
            base_mode = theme_state.get_current_theme_effective_base_mode(self)
            if action == "save_preset":
                name = str(name or "").strip()
                if not name:
                    raise ValueError("empty preset name")
                save_new_custom_theme_preset(conf, custom, name=name, palette=palette, base_mode=base_mode,
                                             data_colors=get_current_data_colors(conf))
            elif is_builtin_theme_preset_key(current) or current not in custom:
                raise ValueError("not a custom preset")
            elif action == "update_preset":
                update_selected_custom_theme_preset(conf, current, custom, palette=palette, base_mode=base_mode,
                                                    data_colors=get_current_data_colors(conf))
            else:
                delete_selected_custom_theme_preset(conf, custom, current)
            self._apply_theme_change()
        else:
            raise ValueError(f"unknown theme action {action!r}")
        return self._colors_state()

    # ---- Colors: data colors ----
    def _set_data_color(self, key, value, pinned):
        conf = self.addon_config.config
        if not pinned:
            conf[key] = value
        else:
            custom = conf.get(Config.PINNED_THEME_CUSTOM_COLORS, {})
            if not isinstance(custom, dict):
                custom = {}
            base = self._data_baseline(True).get(key, COLOR_DEFAULTS.get(key, "#888888"))
            if str(value).lower() == str(base).lower():
                custom.pop(key, None)
            else:
                custom[key] = value
            conf[Config.PINNED_THEME_CUSTOM_COLORS] = custom
            has_mode = conf.get(Config.PINNED_THEME_CUSTOM_BASE_MODE, None) is not None
            conf[Config.PINNED_THEME_IS_CUSTOM] = bool(custom) or has_mode

    def _data_changed(self, source):
        try:
            self.addon_config.write_config()
        except Exception:
            log_swallowed()
        self._refresh_live_data_colors(source=source)
        self._host_call("update_dashboard_visibility")

    def _data_color(self, action, key=None, pinned=False):
        pinned = bool(pinned) and self._pinned_separate()
        if action == "reset":
            if key not in COLOR_DEFAULTS:
                raise ValueError(f"unknown color {key!r}")
            self._set_data_color(key, self._data_baseline(pinned).get(key, "#888888"), pinned)
            self._data_changed(f"config:{key}")
        elif action == "reset_all":
            for k, v in self._data_baseline(pinned).items():
                if k in COLOR_DEFAULTS:
                    self._set_data_color(k, v, pinned)
            self._data_changed("data_color_reset")
        return self._colors_state()

    def _pinned_separate(self):
        conf = self.addon_config.config
        return bool(conf.get(Config.PINNED_USE_ACTIVE_THEME, False)) and bool(conf.get(Config.PINNED_USE_SEPARATE_THEME, False))

    # ---- Colors: window background ----
    def _backdrop(self, action, key=None, value=None):
        from ..details.ui.theme.backdrop import BACKDROP_DEFAULTS, BACKDROP_KEY, BACKDROP_PRESETS, get_backdrop_settings

        conf = self.addon_config.config
        s = get_backdrop_settings(conf)
        if action == "preset":
            if key == "off":
                s["enabled"] = False
            elif key in BACKDROP_PRESETS:
                s.update(BACKDROP_PRESETS[key])
                s["enabled"] = True
        elif action == "slider" and key in ("tone", "glow", "glow2", "depth", "grain"):
            s[key] = max(0, min(100, int(value)))
            s["enabled"] = True
        elif action == "auto_color":
            s["color1"] = ""
            s["enabled"] = True
        elif action == "reset":
            s = dict(BACKDROP_DEFAULTS)
        conf[BACKDROP_KEY] = dict(s)
        self._bd_timer.start()
        return self._backdrop_state()

    def _apply_backdrop(self):
        try:
            from ..details.ui.theme.backdrop import refresh_backdrop_settings

            refresh_backdrop_settings(self.parent_dialog)
        except Exception:
            log_swallowed()
        self.refresh_styles()

    # ---- the color picker (Qt's, shown live as the color changes) ----
    def _pick(self, what, key, pinned):
        from ..details.ui.config.shared.color_picker import pick_color_live
        from ..i18n import tr

        conf = self.addon_config.config
        pinned = bool(pinned) and self._pinned_separate()
        if what == "theme":
            from ..details.logic.theme import pinned_theme_state, theme_state
            from ..details.logic.theme.preset_helpers import resolve_effective_theme_palette

            if pinned:
                cur = pinned_theme_state.get_current_pinned_theme_effective_palette(self).get(key, "#000000")

                def apply(h):
                    pinned_theme_state.set_pinned_theme_override_color(self, key, h)
                    self._push_state()
            else:
                cur = resolve_effective_theme_palette(theme_state.get_current_theme_base_palette(self), conf).get(key, "#000000")

                def apply(h):
                    theme_state.set_theme_override_color(self, key, h)
                    self._push_state()
            pick_color_live(self, cur, tr("Pick Color"), apply)
        elif what == "data":
            if key not in COLOR_DEFAULTS:
                return

            def apply(h):
                self._set_data_color(key, h, pinned)
                self._data_changed(f"config:{key}")
                self._push_state()
            pick_color_live(self, self._data_current(key, pinned), tr("Pick Color"), apply)
        elif what == "glow":
            from ..details.ui.theme.backdrop import BACKDROP_KEY, get_backdrop_settings

            def apply(h):
                s = get_backdrop_settings(conf)
                s["color1"] = h
                s["enabled"] = True
                conf[BACKDROP_KEY] = dict(s)
                self._bd_timer.start()
                self._push_state()
            pick_color_live(self, self._backdrop_state()["color"], tr("Glow color"), apply)
        elif what == "deck":
            from aqt.qt import QColorDialog

            cur = self._colors.get(str(key))
            start = QColor(cur) if cur and QColor(cur).isValid() else QColor("#ffffff")
            color = QColorDialog.getColor(start, self, tr("Pick Deck Color"))
            if color.isValid():
                self._colors[str(key)] = color.name()
                self.addon_config.config[Config.DECK_COLORS] = dict(self._colors)
                if hasattr(self.parent_dialog, "bridge"):
                    self.parent_dialog.bridge.push("table_reload")
                self.bridge.push("color_picked", {"key": str(key), "color": color.name()})

    # ---- Decks ----
    def _decks_set(self, excluded=None, colors=None, dates=None):
        if excluded is not None:
            self._excluded = [x if x == "deleted" else int(x) for x in excluded]
        if colors is not None:
            self._colors = {str(k): v for k, v in colors.items() if isinstance(v, str) and QColor(v).isValid()}
            self.addon_config.config[Config.DECK_COLORS] = dict(self._colors)
            if hasattr(self.parent_dialog, "bridge"):
                self.parent_dialog.bridge.push("table_reload")
        if dates is not None:
            self._dates = list(dates)
        return True

    # ---- Profiles, developer tools ----
    def _profiles(self, action="list", name=None):
        from ..config import ConfigManager, copy_profile_settings, profile_config_files
        from ..i18n import tr

        target = ConfigManager(mw)
        files = [f for f in profile_config_files(mw, target._config_path) if f[2]]
        names = [f[0] for f in files]
        if action == "list":
            return names
        if name not in names:
            raise ValueError("unknown profile")
        if not copy_profile_settings(mw, files[names.index(name)][1], target):
            return {"ok": False, "message": tr("The settings of {name} could not be read.", name=name)}
        # this window's copy is not saved over them; the Deep Dive window closes (it shows the old settings)
        self._close_all(tr("Deep Dive: settings of {name} copied. Reopen the Deep Dive window.", name=name))
        return {"ok": True}

    def _share(self, action="", code="", shareable=True):
        from aqt.qt import QApplication, QFileDialog
        from aqt.utils import tooltip

        from ..config import (
            ConfigManager,
            apply_imported_settings,
            decode_imported_settings,
            encode_share_code,
            export_settings_dict,
        )
        from ..i18n import tr

        if action == "copy_code":
            try:
                text = encode_share_code(self.addon_config.config)
                QApplication.clipboard().setText(text)
                return {"ok": True, "message": tr("Share code copied to clipboard ({n} chars).", n=len(text))}
            except Exception as e:
                log_error(f"share copy_code: {e!r}")
                return {"ok": False, "message": tr("Could not build share code.")}

        if action == "import_code":
            try:
                data, is_share = decode_imported_settings(code)
                target = ConfigManager(mw)
                if not apply_imported_settings(target, data, shareable=is_share):
                    return {"ok": False, "message": tr("Could not apply imported settings.")}
                self._close_all(tr("Deep Dive: settings imported. Reopen the Deep Dive window."))
                return {"ok": True}
            except ValueError as e:
                return {"ok": False, "message": str(e)}
            except Exception as e:
                log_error(f"share import_code: {e!r}")
                return {"ok": False, "message": tr("Could not import settings.")}

        if action == "export_file":
            def run_export():
                path, _ = QFileDialog.getSaveFileName(
                    self, tr("Export Deep Dive Settings"), "deep_dive_config.json", "JSON (*.json)"
                )
                if not path:
                    return
                try:
                    payload = export_settings_dict(self.addon_config.config, shareable=bool(shareable))
                    with open(path, "w", encoding="utf-8") as fh:
                        json.dump(payload, fh, indent=2, ensure_ascii=False)
                    tooltip(tr("Deep Dive: settings exported."))
                except Exception as e:
                    log_error(f"share export_file: {e!r}")
                    tooltip(tr("Could not export settings."))

            return self._later(run_export)

        if action == "import_file":
            def run_import():
                path, _ = QFileDialog.getOpenFileName(
                    self, tr("Import Deep Dive Settings"), "", "JSON (*.json);;All Files (*)"
                )
                if not path:
                    return
                try:
                    with open(path, "r", encoding="utf-8") as fh:
                        raw = fh.read()
                    data, is_share = decode_imported_settings(raw)
                    target = ConfigManager(mw)
                    if apply_imported_settings(target, data, shareable=is_share):
                        self._close_all(tr("Deep Dive: settings imported. Reopen the Deep Dive window."))
                except Exception as e:
                    log_error(f"share import_file: {e!r}")
                    tooltip(tr("Could not import settings: invalid file."))

            return self._later(run_import)

        return {"ok": False, "message": "unknown action"}

    def _close_all(self, message):
        from aqt.utils import tooltip

        self._cancel_restored = True
        host = self.parent_dialog

        def close():
            self.reject()
            try:
                if hasattr(host, "_skip_state_save"):
                    host._skip_state_save = True
                if hasattr(host, "isVisible") and host.isVisible() and hasattr(host, "webview"):
                    host.close()
            except Exception:
                log_swallowed()
            try:
                from . import pinned as _pinned

                _pinned.refresh_block()
            except Exception:
                log_swallowed()
            tooltip(message, period=4000)

        QTimer.singleShot(0, close)

    def _dev(self, action):
        from ..config import is_dev_build
        from ..i18n import tr

        if not is_dev_build():
            raise ValueError("not a dev build")
        from aqt.utils import tooltip

        from .. import dev_mode

        if action == "reset_profile":
            dev_mode.reset_profile()
            self._close_all(tr("Deep Dive: settings of this profile reset. Reopen the Deep Dive window."))
        elif action == "reset_everything":
            dev_mode.reset_everything()
            self._close_all(tr("Deep Dive: settings of all profiles reset. Reopen the Deep Dive window."))
        elif action == "data_folder":
            dev_mode.open_data_folder()
        elif action == "rate_banner":
            from ..details.ui.details_dialog.rate_prompt import preview_next_open

            preview_next_open()
            tooltip(tr("Deep Dive: the rating banner shows the next time the Deep Dive window opens."), parent=self)
        elif action == "reset_tips":
            dev_mode.reset_tips()
            tooltip(tr("Deep Dive: the guided tour shows again at the next Anki start."), parent=self)
        return True

    @staticmethod
    def _open_link(name):
        if name == "translations":
            from ..details.ui.details_dialog import links

            links.open_link(links.TRANSLATIONS_URL)
        return True

    # ---- Save / Cancel ----
    def _save(self):
        from ..details.ui.config.dialogs.deck_config_dialog import apply_deck_options

        conf = self.addon_config.config
        try:
            apply_deck_options(conf, (list(self._excluded), dict(self._colors), list(self._dates)))
        except Exception:
            log_swallowed()
        # (writes the whole config, the global settings with the spans)
        self.parent_dialog.save_tabs_config(self.tabs_data)
        try:
            from .. import startup

            startup.apply_shortcut()
        except Exception:
            log_swallowed()
        mw.reset()
        try:
            mw.toolbar.draw()
        except Exception:
            log_swallowed()
        self._cancel_restored = True
        self.accept()

    def _restore(self):
        """Cancel: the config as it was when Settings opened, and the open windows shown from it again."""
        if self._cancel_restored:
            return
        self._cancel_restored = True
        conf = self.addon_config.config
        conf.clear()
        conf.update(copy.deepcopy(self._initial_config))
        self.tabs_data = copy.deepcopy(self._initial_tabs)
        try:
            self.addon_config.write_config()
        except Exception:
            log_swallowed()
        try:
            from ..config import set_pinned_widgets_disabled

            set_pinned_widgets_disabled(self._initial_pinned_off)
        except Exception:
            log_swallowed()
        self._apply_pinned_theme_runtime(source="settings_cancel_restore")
        self._refresh_live_data_colors(source="settings_cancel_restore", emit_theme_runtime=False)
        self._host_call("update_dashboard_visibility")
        self._host_call("refresh_styles")
        self._refresh_binning_live()
        self._repaint_charts()
        try:
            from ..details.ui.theme.backdrop import refresh_backdrop_settings

            refresh_backdrop_settings(self.parent_dialog)
        except Exception:
            log_swallowed()

    def reject(self):
        self._restore()
        super().reject()

    def done(self, result):
        from ..config import set_live_config_override

        set_live_config_override(None)
        try:
            self.bridge.close()
        except Exception:
            pass
        try:
            self.webview.cleanup()
        except Exception:
            pass
        if self in _OPEN:
            _OPEN.remove(self)
        super().done(result)

    def keyPressEvent(self, event):
        # Escape belongs to the page (a confirmation, a form): Settings closes from its buttons or the window's X
        if event.key() == Qt.Key.Key_Escape:
            return
        super().keyPressEvent(event)


def open_settings_window(host, start_tab=None):
    """Settings for the window host (see WebSettingsDialog). Returns True when saved."""
    existing = find_open()
    if existing is not None:
        existing.show_tab(start_tab)
        existing.raise_()
        existing.activateWindow()
        return False
    dlg = WebSettingsDialog(host, start_tab=start_tab)
    try:
        return bool(dlg.exec())
    finally:
        dlg.deleteLater()


