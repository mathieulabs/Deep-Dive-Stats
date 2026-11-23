# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""The widget gallery (Add Widget, Add Chart, the Deep Dive's Charts and Stat Cards) as a web page (web/gallery_page.js).

Its content and what a click does are gallery_model.GalleryModel (no window); this module is the window and the page's
handlers. The previews are the charts and stat cards themselves, drawn in their tiles by the pinned widgets' own modules
(their data read here, off the UI thread for the charts, as the pinned page's).

open_widget_gallery opens it to add widgets to the main screen, open_manage_gallery to pick the Deep Dive's charts
and stat cards.
"""

from __future__ import annotations

import os

from aqt import mw
from aqt.qt import QDialog, QKeySequence, QShortcut, Qt, QTimer, QVBoxLayout

from ..details.logic.logger import log_swallowed
from .bridge import Bridge
from .gallery_model import GalleryModel, only_missing
from .trace import dev_flag, page_log, trace

_WEB_DIR = "src/web_ui/web"
_CSS = ["dd.css", "settings.css"]
_JS = ["dd-core.js", "stats.js", "charts/activity.js", "charts/dots.js", "charts/hover.js", "charts/zoom_camera.js", "charts/discrete.js",
       "charts/hourly.js", "charts/buttons.js", "charts/pie.js", "charts/retention.js", "charts/heatmap.js",
       "charts/extras.js", "charts/curves.js", "app.js", "settings.js", "deck_picker.js", "text_editor.js", "gallery_page.js"]
CHART_DRAW = (440, 269)  # a chart is drawn at a widget's size, then shrunk into its tile (its text keeps its proportions)


def open_widget_gallery(manager, on_pick, family=None, where=None, only=None, taken=None, parent=None,
                        on_remove=None, on_reset=None):
    """The gallery at the categories of family ("chart", "stat" or "text"; where: the kind of spot the widget goes
    to, for the line under the title). on_pick(Choice) -> id runs for each widget clicked: it is added at once and the
    gallery stays open, to add several; on_remove(id) when one is clicked again. True when closed with Done (Cancel:
    the caller undoes them). parent: the window it opens over (Anki's by default)."""
    model = GalleryModel(manager, family=family, where=where, only=only, taken=taken, on_add=on_pick,
                         on_remove=on_remove, on_reset=on_reset, context="pinned")
    return bool(_run(model, parent))


def open_manage_gallery(manager, parent, charts, charts_shown, stats, stats_shown, family=None, on_toggle=None,
                        on_reset=None, texts=None, on_add_text=None, on_remove_text=None):
    """The gallery as the manager of a set of widgets (Deep Dive): every chart type of charts and stat card key of
    stats, the shown ones checked; a click checks or unchecks one and on_toggle(choice, checked) applies it at once.
    texts: how many texts it has, the Text tile then adding one (on_add_text) or taking one off (on_remove_text).
    (chart types, stat card keys) checked once closed with Done, else None (Cancel: the caller undoes the changes)."""
    model = GalleryModel(manager, family=family, only=charts, taken=charts_shown, stats=stats, stats_taken=stats_shown,
                         toggle=True, on_toggle=on_toggle, on_reset=on_reset, context="details", texts=texts,
                         on_add_text=on_add_text, on_remove_text=on_remove_text)
    return model.marked() if _run(model, parent) else None


def _run(model, parent):
    page = WebGallery(model, parent or mw)
    try:
        return page.exec()
    finally:
        page.deleteLater()


def _url(addon, name):
    from urllib.parse import quote

    return f"/_addons/{quote(addon)}/{_WEB_DIR}/{name}"


class WebGallery(QDialog):
    def __init__(self, model, parent):
        try:
            host = parent.window() if parent is not None else mw
        except Exception:
            host = mw
        super().__init__(host)
        self.model = model
        self.theme = self._theme()
        self.setWindowTitle(model.title())
        from ..window_icon import addon_icon
        addon_icon(self)
        screen = (host.screen() if hasattr(host, "screen") else None) or mw.screen() or mw.app.primaryScreen()
        geom = screen.availableGeometry()
        from .win_size import size_window
        size_window(self, geom, (min(1010, int(geom.width() * 0.94)), min(740, int(geom.height() * 0.88))),
                    (min(640, geom.width() - 40), min(420, geom.height() - 40)))
        # maximize from the title bar (or a double-click on it); F11 shows it full screen, F11 or Esc leaves
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowMaximizeButtonHint)
        fs = QShortcut(QKeySequence(Qt.Key.Key_F11), self)
        fs.setContext(Qt.ShortcutContext.WindowShortcut)
        fs.activated.connect(self._toggle_full_screen)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        from aqt.webview import AnkiWebView

        mw.addonManager.setWebExports(__name__, _WEB_DIR + "/.*")
        self._addon = mw.addonManager.addonFromModule(__name__)
        self.webview = AnkiWebView(parent=self, title="deep_dive_gallery_page")
        lay.addWidget(self.webview)
        self.bridge = Bridge(self.webview, self)
        for name, fn in (("init", self._init), ("gal_pick", self._pick), ("gal_minus", self._minus),
                         ("gal_missing", self._missing), ("gal_span", self._span), ("gal_decks", self._decks),
                         ("gal_reset", self._reset), ("gal_done", self.accept), ("gal_cancel", self.reject),
                         ("gal_stats", self._stats), ("decks_tree", self._decks_tree), ("te_data", self._te_data),
                         ("gal_rename", self._rename_saved), ("gal_delete", self._delete_saved)):
            self.bridge.register(name, fn)
        self.bridge.register("gal_charts", self._charts, background=True)
        self._load()

    def _load(self):
        base = os.path.join(os.path.dirname(__file__), "web")
        try:
            q = "?v=" + str(int(max(os.path.getmtime(os.path.join(base, n)) for n in _CSS + _JS)))
        except Exception:
            q = ""
        self.webview.stdHtml('<div id="dds-root"></div><script>' + dev_flag() + 'DD.galleryPageBoot && DD.galleryPageBoot();</script>',
                             css=[_url(self._addon, n) + q for n in _CSS],
                             js=[_url(self._addon, n) + q for n in _JS])

    def _theme(self):
        from .theme import build_theme

        theme = build_theme(self.model.context)
        theme["backdrop"] = {"enabled": False, "flat": theme["css"]["bg"]}
        return theme

    # -- the page's state -----------------------------------------------------------------------

    def _init(self):
        from ..i18n import web_catalog

        try:
            i18n = web_catalog()
        except Exception:
            i18n = {}
        try:
            from . import providers

            anim = providers.anim_settings(self.model.context)
        except Exception:
            anim = None
        trace(f"GALLERY page: {len(self.model.tiles)} tiles ({self.model.context})")
        return {"state": self._state(), "theme": self.theme, "i18n": i18n, "anim": anim,
                "family": self.model.family, "chart_draw": list(CHART_DRAW)}

    def _tile(self, t):
        pw, ph = self.model.inner(t)
        return {"id": t.id, "name": t.name, "family": t.family, "show_name": t.show_name, "w": t.pic[0], "h": t.pic[1],
                "pw": pw, "ph": ph, "pinned": t.pinned, "count": t.count, "marks": t.marks, "search": t.search,
                "text": t.text, "tip": self.model.tip(t), "type": t.choice.widget_type, "saved": bool(t.saved_id),
                "preset": t.preset}

    def _span_options(self):
        """[[value, name]]: the default period, then the tabs' periods (as the period menu)."""
        from ..const import Period
        from ..details.logic.tabs import get_tabs_config
        from ..i18n import N_, tr, tr_name

        out = [["", tr("Default Period")]]
        seen = set()
        try:
            for tab in get_tabs_config(getattr(self.model.manager, "_config_manager", None)):
                r = tab.get("range")
                if r is None:
                    continue
                days = tab.get("days") if r == Period.CUSTOM else None
                if r != Period.CUSTOM and r in seen:
                    continue
                seen.add(r)
                out.append([f"{int(r)}:{'' if days is None else int(days)}", tr_name(tab.get("title") or N_("Stats"))])
        except Exception:
            log_swallowed()
        return out

    def _span_value(self):
        s = self.model.span
        return "" if s is None else f"{int(s[0])}:{'' if s[1] is None else int(s[1])}"

    def _state(self):
        from ..details.widgets.stats_cards.ui.style import CARD_CORNER_RADIUS_PX
        from ..i18n import tr, upper

        m = self.model
        foot = {"cancel": tr("Cancel"), "done": tr("Done") if (m.toggle or m._on_add is not None) else None,
                "reset": None, "add": None}
        if m.can_choose_span():
            foot["add"] = {"label": tr("Added with:"), "span": self._span_value(), "spans": self._span_options(),
                           "span_tip": tr("The period of the widgets added from here (a widget without a period keeps none)."),
                           "deck": m.deck_name(), "deck_ids": [str(i) for i in (m.deck_ids or [])],
                           "deck_tip": tr("The decks of the widgets added from here. By default they follow the deck shown.")}
        if m._on_reset is not None:
            if m.toggle:
                foot["reset"] = {"text": tr("Reset to Default"),
                                 "tip": tr("The default charts and stat cards, in their default order and size.")}
            else:
                foot["reset"] = {"text": tr("Reset Layout"),
                                 "tip": tr("The default widgets of the main screen, in their default order and spacing.")}
        return {
            "title": m.title(), "where": m.where_text(), "toggle": m.toggle, "missing": bool(only_missing["on"]),
            "seg": [tr("All"), tr("Not shown") if m.toggle else tr("Not added")],
            "search": tr("Search widgets..."), "stat_group": tr("Stat cards"),
            "empty": tr("No widget found."), "all_added": tr("Everything is already added."),
            "sections": [{"key": s["key"], "family": s["family"], "title": s["title"], "head": upper(s["title"]),
                          "hint": s.get("hint"), "tiles": [self._tile(t) for t in s["tiles"]]} for s in m.sections],
            "save_text": any(s["key"] == "saved" for s in m.sections),
            "foot": foot, "view": self._span_value() + "|" + ",".join(foot["add"]["deck_ids"] if foot["add"] else []),
            "stat_radius": CARD_CORNER_RADIUS_PX, "cancel_text": tr("Cancel"),
        }

    def _push(self):
        if self.result() or not self.isVisible():
            return
        try:
            self.bridge.push("gal_state", self._state())
        except Exception as e:
            page_log(f"gallery push: {e!r}")

    # -- previews -----------------------------------------------------------------------------

    def _deck(self):
        return getattr(self.model.manager, "_current_deck_id", None)

    def _charts(self, ids=None):
        """Off the UI thread: {tile id: {type, data, options}} of these charts."""
        from .gallery_pics import chart_data

        out = {}
        for tid in ids or []:
            t = self.model.tiles.get(str(tid))
            if t is None or t.family != "chart":
                continue
            try:
                data, opts = chart_data(self.model.preview_def(t), self._deck())
                out[t.id] = {"type": t.choice.widget_type, "data": data, "options": opts}
            except Exception as e:
                page_log(f"gallery chart {t.choice.widget_type}: {e!r}")
        return out

    def _stats(self, ids=None):
        """{tile id: stat card spec} of these stat cards (UI thread)."""
        from .gallery_pics import stat_card_spec

        out = {}
        for tid in ids or []:
            t = self.model.tiles.get(str(tid))
            if t is None or t.family != "stat":
                continue
            try:
                out[t.id] = stat_card_spec(t.choice.stat_key, self.model.preview_def(t), self._deck(), t.pic)
            except Exception as e:
                page_log(f"gallery stat {t.choice.stat_key}: {e!r}")
        return out

    # -- what the page asks -------------------------------------------------------------------

    def _later(self, fn):
        """After the page's call has its answer: fn may open a window of its own that waits (the text's sentence)."""

        def go():
            try:
                if fn() == "close":
                    self.accept()
                    return
            except Exception:
                log_swallowed()
            self._to_front()
            self._push()

        QTimer.singleShot(0, go)
        return True

    def _to_front(self):
        # the main screen rebuilt behind it: this window stays in front
        try:
            self.raise_()
            self.activateWindow()
        except RuntimeError:
            pass

    def _pick(self, id, template=None, view=None, save_name=None):
        # template: a text's sentence, written in the page's text editor; view: 'bars' / 'pie' from the preview toggle;
        # save_name: that text also saved in My Widgets
        return self._later(lambda: self.model.pick(id, template, view=view, save_name=save_name))

    def _rename_saved(self, id):
        """My Widgets: a saved widget's new name, asked here."""
        t = self.model.tiles.get(str(id))
        if t is None or not t.saved_id:
            return False

        def go():
            from ..details.ui.shared.number_dialog import ask_text
            from ..i18n import tr

            name = ask_text(tr("Rename Saved Widget"), tr("Its name in Add Widget:"), t.name,
                            parent=self)
            if name:
                self.model.rename_saved(id, name)

        return self._later(go)

    def _delete_saved(self, id):
        """My Widgets: a saved widget deleted, once confirmed (the widgets added from it stay)."""
        t = self.model.tiles.get(str(id))
        if t is None or not t.saved_id:
            return False

        def go():
            from aqt.utils import askUser

            from ..i18n import tr

            if askUser(tr("Delete the saved widget \"{name}\"? The widgets already added from it stay.", name=t.name),
                       parent=self, defaultno=True, title=tr("Delete Saved Widget")):
                self.model.delete_saved(id)

        return self._later(go)

    def _te_data(self):
        from .text_editor import editor_data

        return editor_data(getattr(self.model.manager, "_config_manager", None))

    def _minus(self, id):
        return self._later(lambda: self.model.remove_one(id))

    def _missing(self, on=False):
        only_missing["on"] = bool(on)
        return True

    def _span(self, value=""):
        span = None
        if value:
            r, _, d = str(value).partition(":")
            span = (int(r), int(d) if d else None)
        self.model.set_span(span)
        return self._state()

    def _decks(self, ids=None):
        from .deck_picker import from_page

        self.model.set_decks(from_page(ids))
        return self._state()

    def _decks_tree(self):
        from .deck_picker import deck_tree

        return deck_tree()  # (the page adds the deleted cards' row itself)

    def _reset(self, confirmed=False):
        q = self.model.reset_question()
        if q and not confirmed:
            from ..i18n import tr

            return {"ask": q, "ok": tr("Reset Layout")}
        return self._later(self.model.reset)

    def _toggle_full_screen(self):
        if self.isFullScreen():
            # back to how it was before: maximized or its normal size
            self.showMaximized() if getattr(self, "_was_max", False) else self.showNormal()
        else:
            self._was_max = self.isMaximized()
            self.showFullScreen()

    def keyPressEvent(self, event):
        # Esc leaves full screen first; the next one closes the window as usual
        if event.key() == Qt.Key.Key_Escape and self.isFullScreen():
            self._toggle_full_screen()
            event.accept()
            return
        super().keyPressEvent(event)

    def done(self, result):
        try:
            self.bridge.close()
        except Exception:
            pass
        try:
            self.webview.cleanup()
        except Exception:
            pass
        super().done(result)
