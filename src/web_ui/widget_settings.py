# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""A widget's settings (a chart, a stat card, the heatmap) as a web page (web/widget_settings.js).

Drawn in one of two ways:
  - from the widget type's option schema (widget_options.py, no Qt): the charts, the heatmap and the stat cards.
    No Qt dialog: a WidgetSettingsState (details/logic) sorts out which configs the settings live in (shared, its
    own, the theme's) and keeps their Cancel backup; the page's changes go into these configs, the live preview
    follows (live_preview.py), Save writes them as the Qt dialog does (persist_widget_settings), Cancel puts the
    backup back;
  - for the type not converted yet (the text widget): the Qt dialog is built, never shown, and its exec() opens
    this page, a mirror of its controls (_Mirror) read from its layouts, each change handed back to the Qt control
    it stands for.

The text widget's sentence is written in the web text editor (web/text_editor.js).
"""

from __future__ import annotations

import base64
import json
import os
import re

from aqt import mw
from aqt.qt import (
    QBuffer,
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QIODevice,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTimer,
    QVBoxLayout,
    Qt,
)

from ..details.logic.logger import log_swallowed, log_warn
from .bridge import Bridge
from .trace import dev_flag, page_log

_WEB_DIR = "src/web_ui/web"
_CSS = ["dd.css", "settings.css"]
_JS = ["dd-core.js", "settings.js", "text_editor.js", "widget_settings.js"]

_state = {"installed": False}


def install():
    """widget_settings_dialog() opens the schema's page, WidgetSettingsDialog.exec() the mirror (while the web
    interface is on)."""
    if _state["installed"]:
        return
    try:
        from ..details.ui.config.dialogs import widget_settings as qt_settings
        from ..details.ui.config.dialogs.widget_settings import WidgetSettingsDialog
    except Exception as e:
        log_warn(f"web widget settings: {e!r}", tag="WEB")
        return
    qt_settings._opener = _open
    orig_exec = WidgetSettingsDialog.exec

    def exec(self):
        try:
            return run(self)
        except Exception as e:
            log_warn(f"web widget settings failed, Qt dialog instead: {e!r}", tag="WEB")
        return orig_exec(self)

    WidgetSettingsDialog.exec = exec
    _state["installed"] = True


def run(dlg):
    """Shows dlg (a WidgetSettingsDialog, never shown itself) as the web page; returns what dlg.exec() would."""
    from ..details.ui.config.dialogs.widget_settings import WidgetSettingsDialog

    focus, WidgetSettingsDialog.focus_next = WidgetSettingsDialog.focus_next, None
    page = WebWidgetSettings(dlg, focus=focus)
    dlg._web_open = True  # (live_preview: the dialog counts as open)
    try:
        page.exec()
    finally:
        dlg._web_open = False
        page.deleteLater()
    return dlg.result()


def _open(widget_def, parent=None, **kw):
    """A widget's settings drawn from the option schema, without a Qt dialog; None for the Qt dialog (a type not
    converted yet)."""
    from .widget_options import supported

    if not supported((widget_def or {}).get("type")):
        return None
    from ..details.logic.widget_settings_state import WidgetSettingsState

    state = WidgetSettingsState(widget_def, parent, **kw)
    schema = _schema_for(state)
    if schema[0] is None:
        state.close()
        return None
    return _Session(state, schema)


class _Session:
    """What a WidgetSettingsDialog is to its callers (exec(), then deleteLater()), for the schema's page."""

    def __init__(self, state, schema):
        self.state, self.schema, self._result = state, schema, 0

    def exec(self):
        from ..details.ui.config.dialogs.widget_settings import WidgetSettingsDialog

        focus, WidgetSettingsDialog.focus_next = WidgetSettingsDialog.focus_next, None
        page = WebWidgetSettings(self.state, focus=focus, schema=self.schema)
        self.state._web_open = True  # (live_preview: the settings count as open)
        try:
            self._result = int(page.exec())
        finally:
            self.state._web_open = False
            self.state.close()
            page.deleteLater()
        return self._result

    def result(self):
        return self._result

    def deleteLater(self):
        pass


def _url(addon, name):
    from urllib.parse import quote

    return f"/_addons/{quote(addon)}/{_WEB_DIR}/{name}"


def _plain(text):
    """A Qt label's text as shown: "&&" is one "&", a lone "&" marks a shortcut."""
    return re.sub(r"&(.)", r"\1", str(text or "")).strip()


_BG = re.compile(r"background(?:-color)?\s*:\s*(#[0-9a-fA-F]{3,8}|rgba?\([^)]*\)|[a-zA-Z]+)\s*;")
_GRAD = re.compile(r"qlineargradient\(([^)]*)\)")


def _swatch_color(w):
    m = _BG.search(w.styleSheet() or "")
    return m.group(1) if m and m.group(1).lower() not in ("transparent", "none") else None


def _strip_css(w):
    """A gradient strip (a QLabel styled with a qlineargradient) as a CSS linear-gradient."""
    m = _GRAD.search(w.styleSheet() or "")
    if not m:
        return None
    stops = re.findall(r"stop:\s*([0-9.]+)\s+(#[0-9a-fA-F]{3,8}|rgba?\([^)]*\))", m.group(1))
    if not stops:
        return None
    return "linear-gradient(90deg, %s)" % ", ".join(f"{c} {float(p) * 100:g}%" for p, c in stops)


def _picture(w):
    sh = w.sizeHint()
    if sh.width() <= 0 or sh.height() <= 0:
        return None  # an empty widget
    try:
        if w.width() < 4 or w.height() < 4:
            w.resize(w.sizeHint())
        pm = w.grab()
        buf = QBuffer()
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        pm.save(buf, "PNG")
        dpr = max(1.0, pm.devicePixelRatio())
        return {"src": "data:image/png;base64," + base64.b64encode(bytes(buf.data())).decode("ascii"),
                "w": pm.width() / dpr, "h": pm.height() / dpr}
    except Exception:
        log_swallowed()
        return None


class _Mirror:
    """The Qt dialog's controls as a tree of plain dicts (the page draws it), each control under an id the page sends
    back with a change."""

    def __init__(self, dlg):
        self.dlg = dlg
        self.ids = {}

    def _id(self, w):
        key = str(id(w))
        self.ids[key] = w
        return key

    def tree(self):
        self.ids = {}
        d = self.dlg
        items = self._layout(d.content_layout)
        foot = []
        for name, role in (("reset_btn", "reset"), ("cancel_btn", "cancel"), ("ok_btn", "save")):
            b = getattr(d, name, None)
            if b is not None and not b.isHidden():
                foot.append({"id": self._id(b), "text": _plain(b.text()), "role": role, "en": b.isEnabled()})
        return {"items": items, "foot": foot, "title": d.windowTitle()}

    def _layout(self, lay):
        out = []
        if lay is None:
            return out
        if isinstance(lay, QFormLayout):
            for r in range(lay.rowCount()):
                row = []
                for role in (QFormLayout.ItemRole.LabelRole, QFormLayout.ItemRole.FieldRole, QFormLayout.ItemRole.SpanningRole):
                    it = lay.itemAt(r, role)
                    if it is None:
                        continue
                    row += self._item(it)
                if any(n.get("t") != "label" for n in row):
                    out.append({"t": "row", "items": row})
            return out
        for i in range(lay.count()):
            out += self._item(lay.itemAt(i))
        return out

    def _item(self, it):
        w = it.widget()
        if w is not None:
            n = self._widget(w)
            return [n] if n else []
        sub = it.layout()
        if sub is None:
            return []  # a spacer, a stretch
        items = self._layout(sub)
        if not items:
            return []
        if sub.metaObject().className() == "QHBoxLayout":
            return [{"t": "row", "items": items}]
        return items

    def _widget(self, w):
        if w.isHidden():
            return None
        tip = w.toolTip() or ""
        en = w.isEnabled()
        if hasattr(w, "get_template") and hasattr(w, "set_template"):  # the text widget's TextLabelEditor
            from ..details.widgets.pinned.widget_factory.builders.text_label import shown_template

            return {"t": "texteditor", "id": self._id(w), "v": shown_template(self.dlg.widget_def.get("template") or "")}
        if isinstance(w, QGroupBox):
            items = self._layout(w.layout())
            if not items:
                return None
            return {"t": "group", "id": self._id(w), "title": _plain(w.title()), "tip": tip, "items": items}
        if hasattr(w, "slider") and hasattr(w, "spin") and hasattr(w, "label"):  # SettingsSlider
            s = w.slider
            return {"t": "slider", "id": self._id(w), "label": _plain(w.label.text()), "v": s.value(), "min": s.minimum(),
                    "max": s.maximum(), "step": max(1, s.singleStep()), "suffix": w.spin.suffix(),
                    "en": en and s.isEnabled(), "tip": tip}
        if isinstance(w, QCheckBox):
            return {"t": "check", "id": self._id(w), "label": _plain(w.text()), "on": w.isChecked(), "en": en, "tip": tip}
        if isinstance(w, QComboBox):
            opts = [[i, w.itemText(i)] for i in range(w.count()) if w.itemText(i) or w.itemData(i) is not None]
            return {"t": "combo", "id": self._id(w), "opts": opts, "i": w.currentIndex(), "en": en, "tip": tip}
        if isinstance(w, QLineEdit):
            return {"t": "text", "id": self._id(w), "v": w.text(), "ph": w.placeholderText(), "en": en, "tip": tip}
        if isinstance(w, QSpinBox):
            return {"t": "num", "id": self._id(w), "v": w.value(), "min": w.minimum(), "max": w.maximum(),
                    "suffix": w.suffix(), "en": en, "tip": tip}
        if isinstance(w, QPushButton):
            text = _plain(w.text())
            if text:
                return {"t": "button", "id": self._id(w), "text": text, "en": en, "tip": tip}
            color = _swatch_color(w)
            if color and w.icon().isNull():
                return {"t": "swatch", "id": self._id(w), "color": color, "en": en, "tip": tip}
            return {"t": "icon", "id": self._id(w), "icon": self._icon_name(w), "en": en, "tip": tip}
        if isinstance(w, QLabel):
            css = _strip_css(w)
            if css:
                return {"t": "strip", "css": css, "tip": tip}
            text = _plain(w.text()) if w.textFormat() != Qt.TextFormat.RichText else w.text()
            if not text:
                return None
            return {"t": "label", "text": text, "wrap": w.wordWrap(), "tip": tip}
        lay = w.layout()
        if lay is not None:
            items = self._layout(lay)
            if not items:
                return None
            if lay.metaObject().className() == "QHBoxLayout":
                return {"t": "row", "items": items}
            return {"t": "box", "items": items}
        pic = _picture(w)
        return dict(pic, t="pic") if pic else None

    @staticmethod
    def _icon_name(w):
        from ..i18n import tr

        if w.objectName() == "range_btn_remove":
            return "x"
        tip = w.toolTip()
        if tip == tr("Remove color"):
            return "minus"
        if tip == tr("Add color"):
            return "plus"
        return "reset"


def _schema_env(dlg):
    """What widget_options.WidgetOptions needs from the add-on's other (Qt) modules, for this dialog."""
    from types import SimpleNamespace

    from ..const.config import Config
    from ..details.ui.config.widgets.chart_section import has_total_curve
    from ..details.ui.config.widgets.label_defaults import get_default_label
    from ..details.ui.config.widgets.persistence_keys import WIDGET_BEHAVIOR_KEYS
    from ..details.ui.config.widgets.web_glass import web_preview_on
    from ..details.ui.config.widgets.widget_colors import color_keys_for
    from ..details.widgets.chart_utils.tooltip_fields import CHART_TOOLTIP_FIELDS, HEATMAP_TOOLTIP_FIELDS

    wtype = dlg.type
    env = {
        "web_glass": web_preview_on(dlg),
        "total_curve": has_total_curve(wtype),
        "tooltip_fields": list((HEATMAP_TOOLTIP_FIELDS if wtype == "heatmap" else CHART_TOOLTIP_FIELDS.get(wtype)) or ())
        or None,
        "behavior_keys": WIDGET_BEHAVIOR_KEYS,
        "colors": bool(color_keys_for(dlg)),
        # (a stand-in for the dialog: its Metric menu is the page's)
        "default_label": lambda stat_key: get_default_label(
            SimpleNamespace(type=wtype, widget_def=dict(dlg.widget_def, stat_key=stat_key))),
    }
    if wtype == "stat_card" and not dlg.is_dashboard_context:
        from ..details.widgets.pinned.widget_factory.builders.stat_card import TIME_STAT_FIELDS
        from ..details.widgets.pinned.widget_factory.builders.time_units import UNIT_CHOICES
        from ..details.logic.stat_cards import get_stat_card_default_title

        env["metrics"] = [(k, get_stat_card_default_title(k)) for k in Config.DEFAULT_CONFIG if k.startswith("Dash_Show_")]
        env["time_fields"] = set(TIME_STAT_FIELDS)
        env["time_units"] = list(UNIT_CHOICES)
    return env


def _schema_for(dlg):
    """(WidgetOptions, _Colors) for a type drawn from its schema, else (None, None): the mirror."""
    from .widget_options import WidgetOptions, supported

    if not supported(getattr(dlg, "type", None)):
        return None, None
    try:
        env = _schema_env(dlg)
        opts = WidgetOptions(dlg, env)
        return opts, (_Colors(dlg) if env.get("colors") else None)
    except Exception as e:
        log_warn(f"widget settings schema ({dlg.type}): {e!r}, the mirror instead", tag="WEB")
        return None, None


class _Colors:
    """The Colors section (widget_colors.py's logic): the shared colors of Settings > Colors, changed at once, or with
    "Own colors" on, colors kept by this widget (Save / Cancel as its other settings)."""

    def __init__(self, dlg):
        from ..details.ui.config.widgets import widget_colors as wc

        self.dlg, self.wc = dlg, wc
        self.keys = list(wc.color_keys_for(dlg))
        self.own = wc._own_colors(dlg) is not None

    def current(self, key):
        own = (self.wc._own_colors(self.dlg) or {}).get(key) if self.own else None
        return own or self.wc._shared_current(self.dlg, key)

    def is_default(self, key):
        if self.own:
            return (self.wc._own_colors(self.dlg) or {}).get(key) is None
        return str(self.wc._shared_current(self.dlg, key)).lower() == str(self.wc._shared_baseline(self.dlg, key)).lower()

    def set(self, key, color):
        if self.own:
            colors = dict(self.wc._own_colors(self.dlg) or {})
            colors[key] = color
            self.wc._store_own_colors(self.dlg, colors)
        else:
            self.wc.set_shared_color(self.dlg, key, color)

    def reset(self, key):
        if self.own:
            colors = dict(self.wc._own_colors(self.dlg) or {})
            colors.pop(key, None)
            self.wc._store_own_colors(self.dlg, colors)
        else:
            self.wc.set_shared_color(self.dlg, key, self.wc._shared_baseline(self.dlg, key))

    def set_own(self, on):
        # on starts with no own color set (the widget looks the same); off drops them
        self.own = bool(on)
        self.wc._store_own_colors(self.dlg, {} if self.own else None)

    def tip(self):
        from ..i18n import tr_name

        return tr_name(self.wc._OWN_TIP if self.own else self.wc._SHARED_TIP)

    def items(self):
        from ..i18n import tr, tr_name

        out = [{"key": "own_colors", "kind": "switch", "label": tr("Own colors (this widget only)"), "v": self.own,
                "en": True, "tip": tr("Off: the shared colors of Settings > Colors. On: colors for this widget only.")}]
        for key, label in self.keys:
            out.append({"key": "color:" + key, "kind": "color", "label": tr_name(label), "en": True, "tip": "",
                        "color": self.current(key), "reset": not self.is_default(key),
                        "reset_tip": tr("Back to the shared color")})
        return out


class WebWidgetSettings(QDialog):
    """The page, over dlg: the hidden Qt dialog (the mirror) or a WidgetSettingsState (schema: the option schema,
    drawn from it)."""

    def __init__(self, dlg, focus=None, schema=None):
        host = dlg.parent()
        try:
            host = host.window() if host is not None else mw
        except Exception:
            host = mw
        super().__init__(host)
        self.dlg = dlg
        self.qt = isinstance(dlg, QDialog)
        self.mirror = _Mirror(dlg) if self.qt else None
        self.opts, self.colors = schema if schema is not None else _schema_for(dlg)
        self._focus = focus
        self._last = None
        self._cancelling = False
        self.setWindowTitle(self._title())
        from ..window_icon import addon_icon

        addon_icon(self)
        screen = (host.screen() if hasattr(host, "screen") else None) or mw.screen() or mw.app.primaryScreen()
        geom = screen.availableGeometry()
        from .win_size import size_window

        size_window(self, geom, (min(600, int(geom.width() * 0.9)), min(820, int(geom.height() * 0.86))),
                    (min(420, geom.width() - 40), min(360, geom.height() - 40)))
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        from aqt.webview import AnkiWebView

        mw.addonManager.setWebExports(__name__, _WEB_DIR + "/.*")
        self._addon = mw.addonManager.addonFromModule(__name__)
        self.webview = AnkiWebView(parent=self, title="deep_dive_widget_settings")
        lay.addWidget(self.webview)
        self.bridge = Bridge(self.webview, self)
        for name, fn in (("init", self._init), ("ws_set", self._set), ("ws_click", self._click),
                         ("wo_set", self._opt_set), ("wo_do", self._opt_do),
                         ("ws_text", self._text), ("te_data", self._te_data)):
            self.bridge.register(name, fn)
        # a change the dialog finishes a moment later (its live update timer, a control shown after it): sent then
        self._push_timer = QTimer(self)
        self._push_timer.setSingleShot(True)
        self._push_timer.setInterval(120)
        self._push_timer.timeout.connect(self._push)
        if self.qt:
            dlg.finished.connect(self._dialog_finished)
        self._load()

    def _load(self):
        base = os.path.join(os.path.dirname(__file__), "web")
        try:
            q = "?v=" + str(int(max(os.path.getmtime(os.path.join(base, n)) for n in _CSS + _JS)))
        except Exception:
            q = ""
        self.webview.stdHtml('<div id="dds-root"></div><script>' + dev_flag() + 'DD.widgetSettingsBoot && DD.widgetSettingsBoot();</script>',
                             css=[_url(self._addon, n) + q for n in _CSS],
                             js=[_url(self._addon, n) + q for n in _JS])

    def _title(self):
        return self.dlg.windowTitle() if self.qt else self.dlg.title()

    def showEvent(self, event):
        super().showEvent(event)
        if not self.qt:
            return
        # the dialog's own windows (the color picker, a question) open over this one
        try:
            self.dlg.setGeometry(self.geometry())
        except Exception:
            pass

    def _theme(self):
        from .theme import build_theme

        d = self.dlg
        conf = getattr(d, "theme_config", None)
        if not isinstance(conf, dict):
            conf = None
        if not getattr(d, "is_pinned_mode", False):
            return build_theme("details", conf)
        theme = build_theme("pinned", conf)
        # the window backdrop is the Deep Dive theme's (theme.backdrop_spec): with a pinned theme of its own (light
        # over a dark Deep Dive, or the other way) the pinned text would sit over the other theme's background
        theme["backdrop"] = {"enabled": False, "flat": theme["css"]["bg"]}
        return theme

    def _init(self):
        from ..i18n import web_catalog

        try:
            i18n = web_catalog()
        except Exception:
            i18n = {}
        state = self._state()
        focus = None
        if self.opts is not None:
            # (the schema's groups: "Edit Buttons..." opens on the Range Buttons)
            focus = {"range_btn": "ranges"}.get(self._focus)
        else:
            target = getattr(self.dlg, f"{self._focus}_group", None) if self._focus else None
            if target is not None:
                focus = self.mirror._id(target)
        return {"state": state, "theme": self._theme(), "i18n": i18n, "focus": focus}

    def _state(self):
        st = self._tree()
        self._last = json.dumps(st, sort_keys=True)
        return st

    def _tree(self):
        return self._schema_state() if self.opts is not None else self.mirror.tree()

    def _push(self):
        if (self.qt and self.dlg.result()) or not self.isVisible():
            return
        try:
            st = self._tree()
            js = json.dumps(st, sort_keys=True)
            if js != self._last:
                self._last = js
                self.bridge.push("ws_state", st)
        except Exception as e:
            page_log(f"widget settings push: {e!r}")

    def _set(self, id, value=None):
        w = self.mirror.ids.get(str(id)) if self.mirror else None
        if w is None:
            return self._state()
        try:
            if hasattr(w, "slider") and hasattr(w, "spin"):
                w.slider.setValue(int(value))  # (not w.setValue: it holds the signals the live preview listens to)
            elif isinstance(w, QCheckBox):
                w.setChecked(bool(value))
            elif isinstance(w, QComboBox):
                w.setCurrentIndex(int(value))
            elif isinstance(w, QLineEdit):
                w.setText(str(value or ""))
            elif isinstance(w, QSpinBox):
                w.setValue(int(value))
        except Exception:
            log_swallowed()
        self._push_timer.start()
        return self._state()

    # ---- the text widget's sentence (the web text editor, in place of the dialog's TextLabelEditor) ----
    def _te_data(self):
        from .text_editor import editor_data

        d = self.dlg  # (the time spans: the config the Qt editor reads them from)
        return editor_data(getattr(d, "theme_config", None) or getattr(d, "addon_config", None))

    def _text(self, value=""):
        from .text_editor import keep_default

        d = self.dlg
        if not hasattr(self, "_text_stored"):
            self._text_stored = d.widget_def.get("template", "")
        template = keep_default(str(value or ""), self._text_stored)
        d.widget_def["template"] = template
        d.local_config["template"] = template
        try:
            d._trigger_live_update()
        except Exception:
            log_swallowed()
        return True

    def _click(self, id):
        w = self.mirror.ids.get(str(id)) if self.mirror else None
        if isinstance(w, QPushButton) and w.isEnabled():
            # later: a click can open a window of its own (the color picker), which waits for its answer
            QTimer.singleShot(0, w.click)
            QTimer.singleShot(0, self._push_timer.start)
        return True

    # ---- the page drawn from the option schema (widget_options.py) ----
    def _color_of(self, o):
        """(shown color, is the default) of a color option of the schema: a stat card's Title Color."""
        from aqt.qt import QColor

        from ..details.ui.config.widgets.widget_colors import auto_title_color

        v = str(self.opts.values.get(o["id"]) or "")
        if v and QColor(v).isValid():
            return v, False
        try:
            return auto_title_color(self.dlg), True
        except Exception:
            return "#888888", True

    def _schema_state(self):
        from ..i18n import tr

        groups = self.opts.state(self._color_of)
        if self.colors is not None:
            for g in groups:
                if g["id"] == "colors":
                    g["items"] = self.colors.items() + g["items"]  # (the heatmap's palette after its color)
                    g["tip"] = self.colors.tip()
        foot = [{"id": "reset", "text": tr("Reset to Defaults"), "role": "reset", "en": True},
                {"id": "cancel", "text": tr("Cancel"), "role": "cancel", "en": True},
                {"id": "save", "text": tr("Save"), "role": "save", "en": True}]
        return {"schema": True, "groups": groups, "foot": foot, "title": self._title()}

    def _preview(self):
        """The widget shows the dialog's configs as they are now (what the dialog's apply_live_changes starts)."""
        try:
            from . import live_preview

            live_preview._schedule(self.dlg)
        except Exception:
            log_swallowed()

    def _opt_set(self, key, value=None):
        key = str(key)
        try:
            if key == "own_colors" and self.colors is not None:
                self.colors.set_own(bool(value))
            elif self.opts.set(key, value):
                pass
            else:
                return self._state()
        except Exception:
            log_swallowed()
        self._preview()
        return self._state()

    def _opt_do(self, act, key=None):
        """A button of the page: reset_label, pick / reset_color (a color option), reset, cancel, save."""
        key = str(key or "")
        if act in ("pick", "cancel", "save", "hm_del"):
            # later: the color picker waits for its answer, Save and Cancel close the window
            QTimer.singleShot(0, lambda: self._opt_later(act, key))
            return True
        try:
            if act == "reset_label":
                self.opts.reset_label()
            elif act == "reset":
                self.opts.reset()
            elif act == "hm_new":
                self.opts.palette_new(*self._heatmap_base())
            elif act in ("hm_add", "hm_rem"):
                self.opts.palette_stops(act == "hm_add")
            elif act == "reset_color":
                if key.startswith("color:") and self.colors is not None:
                    self.colors.reset(key[6:])
                else:
                    self.opts.set(key, "")
        except Exception:
            log_swallowed()
        self._preview()
        return self._state()

    def _opt_later(self, act, key):
        if act == "cancel":
            self.reject()
            return
        if act == "save":
            self._save()
            return
        from ..details.ui.config.shared.color_picker import pick_color_live
        from ..i18n import tr

        if act == "hm_del":
            self._heatmap_delete()
            return
        if key.startswith("hmc:"):
            # a color of the chosen gradient
            i = int(key[4:]) if key[4:].isdigit() else -1
            cols = self.opts.palette_colors()
            if not 0 <= i < len(cols):
                return
            current = cols[i]

            def live(hex_):
                self.opts.palette_color(i, hex_)
                self._preview()
                self._push()
        elif key.startswith("color:") and self.colors is not None:
            ckey = key[6:]
            current = self.colors.current(ckey)

            def live(hex_):
                self.colors.set(ckey, hex_)
                self._preview()
                self._push()
        elif key in self.opts.values:
            o = next((o for g in self.opts.groups for o in g["items"] if o["id"] == key), None)
            if o is None:
                return
            current = self._color_of(o)[0]

            def live(hex_):
                self.opts.set(key, hex_)
                self._preview()
                self._push()
        else:
            return
        try:
            pick_color_live(self, current, tr("Pick Color"), live)
        except Exception:
            log_swallowed()
        self._push()

    def _heatmap_base(self):
        """(the heatmap's color, a dark theme): what a new gradient starts from when the chosen color is shown."""
        from ..const.config import Config
        from ..const.theme.color_resolver import get_color
        from ..details.ui.theme import get_theme_effective_is_dark

        conf = self.dlg.addon_config
        try:
            return get_color(conf, Config.HEATMAP_COLOR, "details"), bool(get_theme_effective_is_dark(conf))
        except Exception:
            log_swallowed()
            return None, False

    def _heatmap_delete(self):
        from aqt.utils import askUser

        from ..i18n import tr

        g = self.opts._palette_current()
        if g is None or not askUser(tr("Delete the gradient {name}?", name=g["name"]), parent=self):
            return
        self.opts.palette_delete()
        self._preview()
        self._push()

    def _save(self):
        """The dialog's save_and_close, from the schema's values (its own controls never changed)."""
        from ..details.ui.config.widgets.save_persistence import persist_widget_settings

        try:
            self.opts.before_save()
            persist_widget_settings(self.dlg)
        except Exception as e:
            log_warn(f"widget settings save: {e!r}", tag="WEB")
        self._cancelling = True
        if self.qt:
            self.dlg.accept()  # (its finished signal closes this window)
        else:
            self.done(1)
        self._preview()

    def _dialog_finished(self, result):
        self.dlg._web_open = False
        self._cancelling = True
        self.done(int(result))

    def reject(self):
        # the window's X or Escape: as the dialog's Cancel (its finished signal then closes this window)
        if not self._cancelling:
            self._cancelling = True
            if not self.qt:
                self._cancel_state()
            else:
                try:
                    self.dlg.reject()
                    return
                except Exception:
                    log_swallowed()
        super().reject()

    def _cancel_state(self):
        """Cancel without the Qt dialog: the configs and own colors as they were, the widgets shown with them."""
        from ..details.logic import widget_settings_state
        from . import live_preview

        try:
            widget_settings_state.restore(self.dlg)
            from ..details.ui.config.widgets.widget_colors import cancel_own_colors

            cancel_own_colors(self.dlg)
        except Exception:
            log_swallowed()
        try:
            live_preview._schedule(self.dlg, cancelled=True)
        except Exception:
            log_swallowed()

    def done(self, result):
        try:
            self.bridge.close()
        except Exception:
            pass
        super().done(result)
