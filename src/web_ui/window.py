# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""The Deep Dive window: a page drawn by web/app.js, its data and settings served by Python (bridge.py)."""

import json
import os
import sys
import time
from urllib.parse import quote

from aqt import mw
from aqt.qt import QDialog, QLabel, Qt, QTimer, QVBoxLayout

from ..details.logic.logger import log_error, log_warn
from . import providers
from .bridge import Bridge
from .text_editor import editor_data as text_editor_data

# Demo recordings only (dev_tools/demo_collection/record): DD_RECORD_PRELOAD=1 reads every chart's data a few seconds
# after Anki starts and keeps it, and the window opens with all of it (no chart loading on the video)
RECORD_PRELOAD = bool(os.environ.get("DD_RECORD_PRELOAD"))
from .theme import build_theme
from .trace import dev_flag, is_dev, trace

_WEB_DIR = "src/web_ui/web"
_CSS = ["dd.css"]
_JS = ["dd-core.js", "stats.js", "charts/activity.js", "charts/dots.js", "charts/hover.js", "charts/zoom_camera.js", "charts/discrete.js", "charts/hourly.js", "charts/buttons.js", "charts/pie.js", "charts/retention.js", "charts/heatmap.js", "charts/extras.js", "charts/curves.js", "charts/text.js", "table.js", "dialogs.js", "text_editor.js", "dd-tour.js", "app.js"]


def _url(addon, name):
    return f"/_addons/{quote(addon)}/{_WEB_DIR}/{name}"


def _web_i18n():
    try:
        from ..i18n import web_catalog

        return web_catalog()
    except Exception:
        return {}


def _script_json(value):
    from .bridge import _js

    return _js(value).replace("</", "<\\/")


class WebDeepDiveDialog(QDialog):
    def __init__(self, parent=None):
        self._t_open = time.perf_counter()
        self._open_perf = {}
        super().__init__(None)  # no Qt parent: a taskbar button of its own
        # one config object for this window: the settings dialog edits it live (theme preview)
        from ..config import addon_config as _addon_config
        self.addon_config = _addon_config()
        try:
            from ..config import dev_label
            self.setWindowTitle(dev_label("Deep Dive Stats"))
        except Exception:
            self.setWindowTitle("Deep Dive Stats")
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowMinMaxButtonsHint | Qt.WindowType.WindowCloseButtonHint)
        try:
            from ..window_icon import addon_icon

            addon_icon(self)
        except Exception:
            pass
        # 85 % of the screen, with a minimum.
        screen = mw.screen() or mw.app.primaryScreen()
        geom = screen.availableGeometry()
        from .win_size import size_window

        size_window(self, geom, (int(geom.width() * 0.85), int(geom.height() * 0.85)),
                    (min(850, geom.width() - 40), min(600, geom.height() - 40)))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.webview = None
        try:
            from aqt.webview import AnkiWebView

            addon = mw.addonManager.addonFromModule(__name__)
            mw.addonManager.setWebExports(__name__, _WEB_DIR + "/.*")
            self.webview = AnkiWebView(parent=self, title="deep_dive_web")
            if not hasattr(self.webview, "_disable_zoom"):
                self.webview._disable_zoom = False
            layout.addWidget(self.webview)
            try:
                self.webview.loadFinished.connect(self._on_page_loaded)
            except Exception:
                self._page_ok = True
            self.bridge = Bridge(self.webview, self)
            self._register_handlers(self.bridge)
            self._addon = addon
            self._base_color()
            self._load_page()
            self._dev_watch()
            self._watch_theme()
        except Exception as e:
            log_error(f"web window: {e!r}")
            layout.addWidget(QLabel(f"The web view could not start: {e!r}"))

    def _register_handlers(self, bridge):
        """What the page can ask of Python (the window's page, and the hidden page an export draws at 2x)."""
        bridge.register("data", self._data, background=True)
        bridge.register("open_day", self._open_day)
        bridge.register("open_settings", lambda start_tab=None: self._later(lambda: self._open_settings(start_tab)))
        bridge.register("deck_action", lambda did, action: self._later(lambda: self._deck_action(did, action)))
        bridge.register("open_link", self._open_link)
        bridge.register("set_trends", self._set_trends)
        bridge.register("set_visual", self._set_visual)
        bridge.register("export_csv", lambda header, rows, title="": self._later(lambda: self._export_csv(header, rows, title)))
        bridge.register("set_export_stats", lambda on=True: self._set_export_stats(on))
        bridge.register("export_image", lambda kind="full", title=None, period=None: self._later(lambda: self._export_image(kind, title, period)))
        bridge.register("table", lambda tab=0, sort=None, deck=None, expanded=None: providers._plain(providers.table(tab, sort, expanded=expanded, deck=deck)), background=True)
        bridge.register("table_tab_order", self._table_tab_order)
        bridge.register("set_view_mode", self._set_view_mode)
        bridge.register("set_expanded", self._set_expanded)
        bridge.register("set_table_columns", self._set_table_columns)
        bridge.register("set_table_total_bottom", lambda on=True: (self.addon_config.set_value("Table_Total_Bottom", bool(on)), True)[1])
        bridge.register("set_drawer", self._set_drawer)
        bridge.register("drawer", self._drawer)
        bridge.register("set_grid_cols", self._set_grid_cols)
        bridge.register("chart_order", self._chart_order)
        bridge.register("stat_layout", self._stat_layout)
        bridge.register("stat_hide", self._stat_hide)
        bridge.register("stat_lock", self._stat_lock)
        bridge.register("global_option", lambda name, value=None: self._global_option(name, value))
        bridge.register("stat_color", self._stat_color)
        bridge.register("stat_icon", self._stat_icon)
        bridge.register("stat_pin", self._stat_pin)
        bridge.register("stat_swap", self._stat_swap)
        bridge.register("set_card_size", self._set_card_size)
        bridge.register("reset_card_size", self._reset_card_size)
        bridge.register("open_gallery", lambda family="chart": self._later(lambda: self._open_gallery(family)))
        bridge.register("chart_catalog", self._chart_catalog)
        bridge.register("add_chart", self._add_chart)
        bridge.register("widgets_now", self._widgets_now)
        bridge.register("widget_opts", self._widget_opts)
        bridge.register("set_scope", self._set_scope)
        bridge.register("set_setting", self._set_setting)
        bridge.register("pie_separate", self._pie_separate)
        bridge.register("pin_chart", self._pin_chart)
        # Save Widget As...: a chart, stat card or text kept by name for Add Widget (My Widgets), as on the main screen
        bridge.register("save_widget", lambda **what: self._later(lambda: self._save_widget(what)))
        bridge.register("set_heatmap", self._set_heatmap)
        bridge.register("pick_heatmap_color", lambda: self._later(self._pick_heatmap_color))
        bridge.register("edit_gradient", lambda new=False, color=None: self._later(lambda: self._edit_gradient(new, color)))
        bridge.register("set_show_stats", self._set_show_stats)
        bridge.register("span_from_zoom", lambda first, last, name=None: self._span_from_zoom(first, last, name))
        bridge.register("span_name", self._span_name)
        bridge.register("zoom_stats", lambda deck=None, span=-1, first=None, last=None, bounds=None, query="", types=None: self._with_search(query, lambda: providers.zoom_stats(deck or None, span, first, last, bounds, types=types)), background=True)
        bridge.register("review_events", lambda deck=None, t0=0, t1=0, query="": self._with_search(query, lambda: providers.review_events(deck or None, t0, t1)), background=True)
        bridge.register("open_card", self._open_card)
        bridge.register("stat_settings", lambda key=None, label=None: self._later(lambda: self._stat_settings(key, label)))
        bridge.register("ask_int", self._ask_int)
        bridge.register("browse", self._browse)
        bridge.register("rate_action", self._rate_action)
        bridge.register("adaptive", lambda deck=None, span=-1, first=None, last=None, source="activity", query="", types=None: self._with_search(query, lambda: providers.adaptive(deck or None, span, first, last, source, types)), background=True)
        bridge.register("chart_help", self._chart_help)
        bridge.register("widget_settings", lambda wtype, deck=None: self._later(lambda: self._widget_settings(wtype, deck)))
        bridge.register("remove_chart", self._remove_chart)
        bridge.register("restore_chart", self._restore_chart)
        bridge.register("show_past", self._show_past)
        bridge.register("text_get", self._text_get)
        bridge.register("text_set", self._edit_text)
        bridge.register("te_data", lambda: text_editor_data(self.addon_config))
        bridge.register("remove_text", self._remove_text)
        bridge.register("restore_text", self._restore_text)
        bridge.register("resolve_search", self._resolve_search)
        bridge.register("dd_tour_done", self._dd_tour_done)
        bridge.register("dd_tour_gallery_prep", self._dd_tour_gallery_prep)
        bridge.register("dd_tour_gallery", self._dd_tour_gallery)
        bridge.register("stats", lambda deck, span, query="": self._with_search(query, lambda: providers.stats(deck or None, span)), background=True)

    def _watch_theme(self):
        """Light / dark / theme changes (the add-on's theme manager and Anki's theme_did_change): the page gets
        the new theme and redraws in it."""
        from aqt import gui_hooks

        from ..details.widgets.chart_utils.theme import subscribe_theme_changed, unsubscribe_theme_changed

        self._theme_tm = None

        def later(*_a):
            from aqt.qt import QTimer

            if self._theme_tm is None:
                self._theme_tm = QTimer(self)
                self._theme_tm.setSingleShot(True)
                self._theme_tm.timeout.connect(self._push_theme)
            self._theme_tm.start(60)  # one push for a burst of changes

        self._theme_cb = later
        try:
            subscribe_theme_changed(later)
        except Exception as e:
            log_error(f"web theme subscribe: {e!r}")
        if hasattr(gui_hooks, "theme_did_change"):
            gui_hooks.theme_did_change.append(later)

        def unhook(*_a):
            try:
                unsubscribe_theme_changed(later)
            except Exception:
                pass
            try:
                gui_hooks.theme_did_change.remove(later)
            except Exception:
                pass

        self.destroyed.connect(unhook)
        self._unhook_theme = unhook

    def dispose(self):
        """Release bridge, webview, theme hooks, and any active offscreen export when discarding this window."""
        if getattr(self, "_exporting", False):
            try:
                self._export_end(finish=False)
            except Exception:
                pass
        unhook = getattr(self, "_unhook_theme", None)
        if unhook:
            self._unhook_theme = None
            try:
                unhook()
            except Exception:
                pass
        try:
            self.bridge.close()
        except Exception:
            pass
        try:
            self.webview.cleanup()
        except Exception:
            pass

    def closeEvent(self, event):
        if getattr(self, "_exporting", False):
            try:
                self._export_end(finish=False)
            except Exception:
                pass
        super().closeEvent(event)

    # ---- the parent the add-on's settings dialog talks to: a theme or color picked
    # there, even before Save (live preview), restyles this window at once ----
    def refresh_styles(self):
        from ..details.widgets.chart_utils.theme import get_theme_manager, sync_theme_manager_from_config, theme_already_synced

        conf = self.addon_config.config
        needs = not theme_already_synced(conf)
        sync_theme_manager_from_config(conf, emit=False)
        try:
            get_theme_manager().invalidate_cache()
        except Exception:
            pass
        self._push_theme()
        # stat card colors and the charts' data colors read again (live preview), without animating them
        self.update_dashboard_visibility(quiet=True)
        if needs:  # the other live widgets (pinned charts) too
            sync_theme_manager_from_config(conf, emit=True, source="apply_styles")

    def update_dashboard_visibility(self, quiet=False):
        """A setting that changes what the window shows (stat cards, colors): the page reads it again, once for a burst.
        quiet: only colors changed (a theme): the charts take the data read again at once, not animated (a burst is
        quiet only when all its changes are)."""
        from aqt.qt import QTimer

        if getattr(self, "_vis_tm", None) is None:
            self._vis_tm = QTimer(self)
            self._vis_tm.setSingleShot(True)
            self._vis_tm.timeout.connect(
                lambda: (self._push_theme(), self.bridge.push("refresh", {"quiet": True} if self._vis_quiet else None)))
        self._vis_quiet = bool(quiet) and (getattr(self, "_vis_quiet", True) if self._vis_tm.isActive() else True)
        self._vis_tm.start(150)

    # ---- the opening animations start once the window is shown and the page loaded (DD.go) ----
    def _go_check(self):
        if getattr(self, "_page_ok", False) and getattr(self, "_shown_ok", False) and not getattr(self, "_went", False):
            from aqt.qt import QTimer

            self._went = True
            t_open = getattr(self, "_t_open", None)
            if t_open is not None:
                op = getattr(self, "_open_perf", {}) or {}
                since_open = 1000 * (time.perf_counter() - t_open)
                trace(
                    f"PERFTRACE dd_open ready={since_open:.0f}ms boot={op.get('boot_ms', 0):.0f}ms"
                    f" ser={op.get('ser_ms', 0):.1f}ms html={op.get('html_ms', 0):.1f}ms"
                    f" boot_kb={op.get('boot_kb', 0):.1f}"
                )
            # a few frames for the first paint of the window, then every chart starts together
            QTimer.singleShot(120, lambda: self.webview.eval("window.DD && DD.go && DD.go()"))

    def _on_page_loaded(self, ok=True):
        self._page_ok = True
        self._went = False
        if getattr(self, "_veiled", False):
            from aqt.qt import QTimer

            QTimer.singleShot(60, self._unveil)  # (a few frames for the page's first paint)
        self._go_check()
        self._rate_flush()
        # Safety net: if a script failed to load (e.g. transient HTTP/cache error), reload once with a fresh cache-buster
        if self.webview is not None and getattr(self, "_load_retries", 0) < 2:
            def _check_boot(ready):
                if ready or self.webview is None or getattr(self, "_disposed", False):
                    return
                retries = getattr(self, "_load_retries", 0) + 1
                self._load_retries = retries
                log_warn(f"web window: DD.start missing after load, retrying ({retries}/2)")
                self._load_page(bust=str(int(time.time() * 1000)))

            try:
                self.webview.evalWithCallback("Boolean(window.DD && typeof DD.start === 'function')", _check_boot)
            except Exception:
                pass

    # ---- opened, the window stays see-through until its page has painted (shown at once, it was an empty window
    # for half a second while the page loaded); never longer than 1.5 s ----
    def show_when_ready(self):
        from aqt.qt import QTimer

        if self.webview is None or getattr(self, "_page_ok", False):
            self.show()
            return
        self._veiled = True
        try:
            self.setWindowOpacity(0.0)
        except Exception:
            self._veiled = False
        self.show()
        if self._veiled:
            QTimer.singleShot(1500, self._unveil)

    def _unveil(self):
        if not getattr(self, "_veiled", False):
            return
        self._veiled = False
        try:
            self.setWindowOpacity(1.0)
            self.raise_()
            self.activateWindow()
        except RuntimeError:
            pass

    def resizeEvent(self, event):
        self._rz_trace()
        super().resizeEvent(event)
        self._rz_pump()
        try:
            from ..details.ui.dialog.screen_fit import on_resize

            on_resize(self)
        except Exception:
            pass

    def _rz_trace(self):
        """Dev trace (RESIZETRACE): Qt's resize events of one burst (until 400 ms of quiet), one line at its end: the
        sizes, the gaps between events (a long one: the UI thread was held), the Python background commands running
        (they hold the GIL), and the epoch clock to line it up with the page's own RESIZETRACE lines."""
        if not is_dev():
            return
        try:
            now = time.perf_counter()
            b = getattr(self, "_rz", None)
            size = f"{self.width()}x{self.height()}"
            busy = [f"{c} {1000 * (now - t):.0f}ms" for c, t in getattr(self.bridge, "_inflight", {}).values()]
            if b is None:
                b = self._rz = {"t0": now, "clock": int(time.time() * 1000), "last": now, "n": 0, "gaps": [], "sizes": [size],
                                "busy0": busy, "busy": set()}
                timer = self._rz_timer = QTimer(self)
                timer.setSingleShot(True)
                timer.timeout.connect(self._rz_end)
            else:
                b["gaps"].append(1000 * (now - b["last"]))
                if b["sizes"][-1] != size:
                    b["sizes"].append(size)
            b["n"] += 1
            b["last"] = now
            b["busy"].update(c.split(" ")[0] for c in busy)
            self._rz_timer.start(400)
        except Exception:
            pass

    def _rz_pump(self):
        """While a window edge is dragged, Windows runs its own loop that serves the mouse first: the web view's work
        (Chromium runs on this thread, through Qt's posted events and timers) got a turn only every ~400 ms, so the page
        learned its new size late and the new area showed an old picture (RESIZETRACE: 150 resize events in Qt, 6 in
        the page). Its pending work runs here at each resize, the user's input left out; never nested."""
        if getattr(self, "_rz_pumping", False):
            return
        self._rz_pumping = True
        try:
            from aqt.qt import QApplication, QEventLoop

            t0 = time.perf_counter()
            QApplication.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents, 8)
            b = getattr(self, "_rz", None)
            if b is not None:
                b["pump"] = b.get("pump", 0.0) + 1000 * (time.perf_counter() - t0)
        except Exception:
            pass
        finally:
            self._rz_pumping = False

    def _rz_end(self):
        b, self._rz = getattr(self, "_rz", None), None
        if not b:
            return
        g = sorted(b["gaps"])
        sizes = b["sizes"] if len(b["sizes"]) <= 6 else b["sizes"][:3] + ["..."] + b["sizes"][-2:]
        trace(f"RESIZETRACE qt burst at clock {b['clock']} dur={1000 * (b['last'] - b['t0']):.0f}ms events={b['n']} "
              f"sizes {' -> '.join(sizes)} | gap median={g[len(g) // 2] if g else 0:.0f}ms max={g[-1] if g else 0:.0f}ms "
              f"over50={sum(1 for x in g if x > 50)} | pump {b.get('pump', 0.0):.0f}ms | python busy at start [{', '.join(b['busy0'])}] during [{', '.join(sorted(b['busy']))}]")

    def changeEvent(self, event):
        super().changeEvent(event)
        try:
            from ..details.ui.dialog.screen_fit import on_change

            on_change(self, event)
        except Exception:
            pass

    def showEvent(self, event):
        super().showEvent(event)
        self._shown_ok = True
        if not getattr(self, "_fit_connected", False):
            try:
                from ..details.ui.dialog.screen_fit import install as _fit_install

                _fit_install(self)
            except Exception as e:
                log_warn(f"[web] screen_fit install: {e}")
        from .win_size import follow_safe_area

        follow_safe_area(self)
        self._go_check()
        self._rate_check()

    # ---- the rating banner (details_dialog/rate_prompt.py): each opening counts, the banner shows when it is due ----
    def _rate_check(self):
        try:
            from ..details.ui.details_dialog.rate_prompt import window_opened

            self._rate_pending = window_opened()
            self._rate_flush()
        except Exception as e:
            log_error(f"rate prompt: {e!r}")

    def _rate_flush(self):
        pend = getattr(self, "_rate_pending", None)
        if pend and getattr(self, "_page_ok", False):
            self._rate_pending = None
            self.webview.eval("window.DD && DD.showRate && DD.showRate(%s)" % json.dumps(pend))

    @staticmethod
    def _rate_action(action=None, preview=False, counted=False):
        """Rate / Later / Don't ask again / seen for a while."""
        from ..details.ui.details_dialog import links
        from ..details.ui.details_dialog.rate_prompt import count_show, mark_rated

        if action == "rate":
            links.open_link(links.RATE_URL)
        if action in ("rate", "never"):
            mark_rated()
        elif action in ("later", "seen") and not preview and not counted:
            count_show()
        return True

    def _dialog_host(self):
        """What the settings dialogs are opened on: a hidden child of this window. Their live preview styles
        the Qt widget they were opened on (style sheet, margins): given the window itself, it moved the page."""
        from aqt.qt import QFrame

        host = getattr(self, "_dlg_host", None)
        try:
            if host is not None:
                host.isHidden()
        except RuntimeError:
            host = None
        if host is None:
            host = self._dlg_host = QFrame(self)
            host.setObjectName("dd_web_dialog_host")
            host.hide()
        host.setStyleSheet("")
        return host

    def preview_live(self):
        """A settings dialog changed something (live_preview.py): the theme and the charts again, now."""
        self._push_theme()
        try:
            self.bridge.push("refresh")
        except Exception:
            pass

    def _push_theme(self):
        try:
            import json

            from ..details.widgets.chart_utils.theme import get_theme_manager, sync_theme_manager_from_config

            conf = self.addon_config.config
            # the theme state and its cached palettes follow the config and Anki's light / dark mode now
            sync_theme_manager_from_config(conf, emit=False)
            get_theme_manager().invalidate_cache()
            theme = build_theme("details", conf)
            # the stacked charts' series colours (Answer Time, Forgotten...): they come with their data, read again
            # a moment later; sent here, every chart repaints in the same frame
            from . import extras_providers

            types = [w["type"] for w in providers.default_widgets()]
            theme["series"] = extras_providers.series_colors(types)
            theme["paint"] = extras_providers.paint_colors(types)  # the other colours of their data
            self._base_color(theme)
            self.webview.eval("DD.setTheme(%s)" % json.dumps(theme))
        except Exception as e:
            log_error(f"web theme push: {e!r}")

    def open_scope(self, deck, span=None):
        """Another deck (0: the whole collection, -1: deleted cards) and period, the window already open."""
        self.webview.eval("DD.openScope && DD.openScope(%s, %s)" % (json.dumps(deck), json.dumps(span)))

    def _base_color(self, theme=None):
        """The view's and the window's own color: the page's background. While the window is resized the page is
        drawn again a little later; meanwhile the new room showed what was there before (the old, larger picture of
        the page, or of other windows), now this color."""
        try:
            from aqt.qt import QColor, QPalette

            if theme is None:
                theme = build_theme("details", self.addon_config.config)
            col = QColor((theme.get("css") or {}).get("bg") or "#1e1e1e")
            if not col.isValid():
                return
            self.webview.page().setBackgroundColor(col)
            txt = QColor((theme.get("css") or {}).get("text") or ("#e8e8ee" if theme.get("is_dark") else "#1e1e24"))
            # On Android (Kioku), Kioku's native top bar renders white title/status text over the dialog's
            # window palette, so keep the outer dialog dark on light themes while the webview stays themed.
            dlg_col = QColor("#18181b") if (sys.platform == "android" and not theme.get("is_dark")) else col
            for w, c in ((self, dlg_col), (self.webview, col)):
                pal = w.palette()
                pal.setColor(QPalette.ColorRole.Window, c)
                pal.setColor(QPalette.ColorRole.Base, c)
                if txt.isValid():
                    pal.setColor(QPalette.ColorRole.WindowText, txt)
                    pal.setColor(QPalette.ColorRole.Text, txt)
                w.setPalette(pal)
                w.setAutoFillBackground(True)
        except Exception as e:
            log_error(f"web base color: {e!r}")

    def _load_page(self, bust=""):
        if not bust:
            # the files' last change in the address: the webview's HTTP cache (kept on disk) served old scripts after
            # an update of the add-on, until Anki's cache was cleared
            import os

            try:
                bust = str(int(max(os.path.getmtime(f) for f in self._web_files())))
            except Exception:
                bust = ""
        q = ("?v=" + bust) if bust else ""
        tb0 = time.perf_counter()
        boot_data = self._boot()
        tb1 = time.perf_counter()
        boot_js = _script_json(boot_data)
        tb2 = time.perf_counter()
        self.webview.stdHtml(
            '<div id="dd-root"></div><script>%sDD.start(%s);</script>' % (dev_flag(), boot_js),
            css=[_url(self._addon, name) + q for name in _CSS],
            js=[_url(self._addon, name) + q for name in _JS],
            context=self,
        )
        tb3 = time.perf_counter()
        self._open_perf = {
            "boot_ms": 1000 * (tb1 - tb0),
            "ser_ms": 1000 * (tb2 - tb1),
            "html_ms": 1000 * (tb3 - tb2),
            "boot_kb": len(boot_js) / 1024.0,
        }

    def _web_files(self):
        import os

        base = os.path.join(os.path.dirname(__file__), "web")
        return [os.path.join(base, n) for n in _CSS + _JS]

    def _dev_watch(self):
        """Dev mode (a file user_files/web_dev_reload exists): reload the page when a web file changes."""
        import os

        flag = os.path.join(os.path.dirname(__file__), "..", "..", "user_files", "web_dev_reload")
        if not is_dev() or not os.path.exists(flag):
            return

        def stamp():
            out = []
            for f in self._web_files():
                try:
                    out.append(os.path.getmtime(f))
                except OSError:
                    out.append(0)
            return out

        # The files' dates are read on a thread of their own: read on Anki's UI thread each second, while a chart's
        # data was computed in the background each read waited its turn for Python's lock (~5 ms a file, 25 files),
        # and the window stalled 100-190 ms. The UI thread only looks at what the thread found
        import threading

        self._dev_stamp = stamp()
        self._dev_seen = self._dev_stamp
        stop = threading.Event()

        def watch():
            while not stop.wait(1.0):
                self._dev_seen = stamp()

        threading.Thread(target=watch, name="dd-web-dev-watch", daemon=True).start()
        self.destroyed.connect(lambda *_: stop.set())
        self._dev_timer = QTimer(self)

        def tick():
            cur = self._dev_seen
            if cur != self._dev_stamp:
                self._dev_stamp = cur
                self._load_page(str(int(max(cur) * 1000)))

        self._dev_timer.timeout.connect(tick)
        self._dev_timer.start(1000)

    @staticmethod
    def _set_setting(section, key, value):
        """A card's setting changed in the page: stored where the normal window stores it."""
        import copy

        from ..const.config import Config
        from ..config import addon_config as _addon_config

        cfg = _addon_config()
        conf = cfg.config
        root = conf.setdefault(Config.DEEP_DIVE_WIDGET_SETTINGS, {})
        mode_key = f"{section}_g"
        if mode_key not in root:
            root[mode_key] = copy.deepcopy(root.get(section, {}))
        root[mode_key][key] = value
        cfg.write_config()
        return True

    @staticmethod
    def _set_view_mode(mode):
        from ..const.config import Config
        from ..config import addon_config as _addon_config

        _addon_config().set_value(Config.DETAILS_VIEW_MODE, "deck" if mode == "deck" else "time", notify=False)
        return True

    @staticmethod
    def _span_name(first, last):
        """The name 'Set zoom as time span' proposes (the zoomed days), or None when they are not dates."""
        from ..details.ui.shared.zoom_span import _default_name, _parse

        d0, d1 = _parse(first), _parse(last)
        if not d0 or not d1:
            return None
        return _default_name(min(d0, d1), max(d0, d1))

    def _span_from_zoom(self, first, last, name=None):
        """'Set zoom as time span': saves the zoomed days as a time span named name (the page asked it; asked here
        when it did not); returns its code and the new span list."""
        import copy

        from ..details.logic.data.core import abs_period
        from ..details.logic.tabs import DEFAULT_DETAILS_TABS, get_tabs_config, save_tabs_config
        from ..details.ui.shared.zoom_span import _default_name, _parse, _unique_title, ask_span_name

        d0, d1 = _parse(first), _parse(last)
        if not d0 or not d1:
            return None
        if d1 < d0:
            d0, d1 = d1, d0
        name = (str(name).strip() if name else "") or ask_span_name(_default_name(d0, d1), self)
        if not name:
            return None
        cfg = self.addon_config
        code = abs_period.encode(d0, d1)
        tabs = copy.deepcopy(get_tabs_config(cfg))
        if not any(t.get("range") == code for t in tabs):
            tab = copy.deepcopy(DEFAULT_DETAILS_TABS[0])
            tab["title"] = _unique_title(tabs, name)
            tab["range"] = code
            tabs.append(tab)
            save_tabs_config(cfg, tabs)
        return {"code": code, "spans": self._spans()}

    @staticmethod
    def _set_show_stats(value, bottom=None):
        from ..const.config import Config
        from ..config import addon_config as _addon_config

        _addon_config().set_value(Config.DEEP_DIVE_SHOW_STATS, bool(value))
        if bottom is not None:
            _addon_config().set_value(Config.DEEP_DIVE_SHOW_BOTTOM_STATS, bool(bottom))
        return True

    @staticmethod
    def _show_bottom_stats():
        from ..const.config import Config
        from ..config import addon_config as _addon_config

        return bool(_addon_config().config.get(Config.DEEP_DIVE_SHOW_BOTTOM_STATS, False))

    @staticmethod
    def _show_stats():
        from ..const.config import Config
        from ..config import addon_config as _addon_config

        return bool(_addon_config().config.get(Config.DEEP_DIVE_SHOW_STATS, True))

    @staticmethod
    def _set_heatmap(name, value):
        """The heatmap options of its right-click menu (global, like the normal window)."""
        from ..const.config import Config
        from ..config import addon_config as _addon_config

        if name == "palette":
            from ..details.widgets.charts.heatmap.palettes import CUSTOM, KEYS, customs_of

            conf = _addon_config().config
            if value not in KEYS and not any(CUSTOM + p["id"] == value for p in customs_of(conf.get)):
                return False
        key = {"multi_hue": Config.HEATMAP_MULTI_HUE_INTENSITY, "metric": Config.HEATMAP_METRIC,
               "palette": Config.HEATMAP_PALETTE,
               "invert": Config.HEATMAP_INVERT_INTENSITY, "years_no_gap": Config.HEATMAP_YEARS_NO_GAP,
               "month_grid": Config.HEATMAP_MONTH_GRID, "narrow_view": Config.HEATMAP_NARROW_VIEW}.get(name)
        if key is None:
            return False
        if name == "narrow_view" and value not in ("scroll", "split", "grid", "fit"):
            return False
        _addon_config().set_value(key, value)
        return True

    def _pick_heatmap_color(self):
        """The heatmap's right-click Color...: live color picker (switches Palette to Chosen color if a preset was active)."""
        from ..config import addon_config as _addon_config
        from ..const.config import Config
        from ..const.theme.color_resolver import get_color
        from ..details.ui.config.shared.color_picker import pick_color_live
        from ..details.widgets.charts.heatmap.palettes import colors_of, customs_of, palette_of
        from ..i18n import tr

        cfg = _addon_config()
        conf = cfg.config
        orig_pal = palette_of(conf.get)
        orig_pal_colors = colors_of(conf.get)
        cur = get_color(conf, Config.HEATMAP_COLOR, "details")

        def apply(h, pal=""):
            self.bridge.push("heatmap_palette", {"color": h, "palette": pal,
                                                 "palette_colors": orig_pal_colors if pal else None,
                                                 "custom_palettes": customs_of(conf.get)})

        chosen = pick_color_live(self._dialog_host(), cur, tr("Pick Color"), lambda h: apply(h, ""))
        if chosen:
            conf[Config.HEATMAP_COLOR] = chosen
            if orig_pal:
                conf[Config.HEATMAP_PALETTE] = ""
            cfg.write_config()
            apply(chosen, "")
            try:
                from . import pinned as _pinned

                _pinned.refresh_block()
            except Exception:
                pass
        elif orig_pal:
            apply(cur, orig_pal)

    def _edit_gradient(self, new=False, color=None):
        """The heatmap's Palette > New gradient... / Edit gradient...: the gradient's window; each change goes to the
        page at once (heatmap_palette)."""
        from ..details.ui.config.dialogs.heatmap_gradient import edit_gradient
        from ..details.ui.theme import get_theme_effective_is_dark
        from ..details.widgets.charts.heatmap.palettes import colors_of, customs_of, palette_of, seed_colors
        from ..config import addon_config as _addon_config

        cfg = _addon_config()
        conf = cfg.config
        seed = None
        if new:
            seed = seed_colors(palette_of(conf.get), customs_of(conf.get), color, dark=get_theme_effective_is_dark(conf))

        def push():
            c = cfg.config
            self.bridge.push("heatmap_palette", {"palette": palette_of(c.get), "palette_colors": colors_of(c.get),
                                                 "custom_palettes": customs_of(c.get)})

        edit_gradient(self._dialog_host(), conf, cfg.set_value, push, new=bool(new), seed=seed)

    @staticmethod
    def _pin_chart(wtype, span=-1):
        """Pin a chart to the main screen (the normal window's 'Pin ... to main menu')."""
        from ..details.logic.pinning import pin_chart

        return pin_chart(wtype, int(span))

    def _widget_settings(self, wtype, deck=None):
        """The native settings dialog of one chart; the cards are rebuilt after it (only when OK was pressed)."""
        import copy
        from types import SimpleNamespace

        from ..const.config import Config
        from ..details.ui.deep_dive.runtime import widget_settings_runtime as wsr

        cfg = self.addon_config
        mgr = SimpleNamespace(addon_config=cfg, last_row_data={"did": deck or None}, last_deck_identifier=deck or None,
                              last_history_range=-1, dialog=self)
        mgr._get_dd_widget_setting = lambda s, k, d=None: wsr.get_dd_widget_setting(mgr, s, k, d)
        mgr._apply_dd_widget_setting_live = lambda *a, **k: False
        mgr._populate_dashboard = lambda: None
        mgr._update_dd_widget_setting = lambda s, k, v, replace_all=False, refresh=True, write=True: wsr.update_dd_widget_setting(
            mgr, s, k, v, replace_all=replace_all, refresh=False, write=write)
        before = copy.deepcopy(cfg.config.get(Config.DEEP_DIVE_WIDGET_SETTINGS, {}))
        try:
            wsr.open_dd_widget_settings(mgr, wtype, self._dialog_host())
        finally:
            providers._LIVE["own"] = None  # its live preview ends: the saved settings again
        if cfg.config.get(Config.DEEP_DIVE_WIDGET_SETTINGS, {}) != before:
            self.bridge.push("rebuild")

    @staticmethod
    def _chart_help(wtype):
        from ..details.widgets.common.chart_help import help_text

        return help_text(wtype)

    @staticmethod
    def _chart_mgr():
        from types import SimpleNamespace

        from ..config import addon_config as _addon_config

        return SimpleNamespace(addon_config=_addon_config())

    def _remove_chart(self, wtype):
        """Take a chart off Deep Dive; returns the index it had, for Undo."""
        from ..details.ui.deep_dive import extra_charts as ec

        mgr = self._chart_mgr()
        if wtype in ec.base_types():
            if wtype not in ec.hidden_types(mgr):
                ec._save_hidden(mgr, ec.hidden_types(mgr) + [wtype])
            return None
        types = ec.extra_types(mgr)
        if wtype not in types:
            return None
        i = types.index(wtype)
        ec._save(mgr, [t for t in types if t != wtype])
        return i

    def _restore_chart(self, wtype, index=None):
        from ..details.ui.deep_dive import extra_charts as ec

        ec._show(self._chart_mgr(), wtype, index)
        return True

    def _show_past(self, wtype, after=None, order=None):
        """View on a Past Day: a chart's Time Machine shown, right after it (order: the types the window shows)."""
        from ..details.ui.deep_dive import extra_charts as ec

        ec._show(self._chart_mgr(), wtype)
        shown = [str(t) for t in (order or []) if str(t) != wtype]
        shown.insert(shown.index(after) + 1 if after in shown else len(shown), wtype)
        self._chart_order(shown)
        return True

    # ---- the Deep Dive's texts (providers.text_data): a sentence of one's own with the pinned text widget's
    # variables, read for the deck and period shown; added and taken off in the gallery (Add / Remove, its Text
    # tile), edited and removed from their own right-click menu too ----
    @staticmethod
    def _save_texts(texts, shown_order=None):
        """The texts saved, then the order of what the window shows (the texts placed in it)."""
        from ..const.config import Config
        from ..config import addon_config as _addon_config

        _addon_config().set_value(Config.DEEP_DIVE_TEXT_WIDGETS, texts)
        if shown_order is not None:
            WebDeepDiveDialog._chart_order(shown_order)

    @staticmethod
    def _texts_now():
        return {k: dict(v) for k, v in providers.text_widgets().items()}

    def _add_text(self, template):
        """The gallery's Text tile: its sentence (written in the gallery page's text editor), the text put at the
        end. Its id."""
        import secrets

        texts = self._texts_now()
        wid = "text:" + secrets.token_hex(3)  # never the id of a text removed (its size stayed saved)
        while wid in texts:
            wid = "text:" + secrets.token_hex(3)
        texts[wid] = {"template": template}
        shown = [w["type"] for w in providers.default_widgets()] + [wid]
        self._save_texts(texts, shown)
        return wid

    def _text_get(self, wid):
        """A text's sentence, for the page's text editor (None: no such text)."""
        texts = self._texts_now()
        return {"template": texts[wid].get("template") or ""} if wid in texts else None

    def _edit_text(self, wid, template=None):
        """A text's new sentence, from the page's text editor."""
        texts = self._texts_now()
        if wid not in texts or template is None:
            return
        texts[wid]["template"] = template
        self._save_texts(texts)
        self.bridge.push("text_changed", {"id": wid})

    def _remove_text(self, wid):
        """A text off Deep Dive; returns what Undo needs to put it back at its place."""
        texts = self._texts_now()
        if wid not in texts:
            return None
        shown = [w["type"] for w in providers.default_widgets()]
        index = shown.index(wid) if wid in shown else len(shown)
        gone = texts.pop(wid)
        self._save_texts(texts)
        return {"template": gone.get("template") or "", "index": index}

    def _restore_text(self, wid, template="", index=None):
        texts = self._texts_now()
        texts[wid] = {"template": template or ""}
        shown = [w["type"] for w in providers.default_widgets() if w["type"] != wid]
        shown.insert(len(shown) if index is None else max(0, min(int(index), len(shown))), wid)
        self._save_texts(texts, shown)
        return True

    # --- what the normal window's dialogs ask of their parent window ---

    def get_tabs_config(self):
        from ..details.logic.tabs import get_tabs_config

        return get_tabs_config(self.addon_config)

    # (no update_dashboard_visibility / refresh_styles stubs here: the real ones are above, for the settings dialog's
    # live preview; stubs left here replaced them, and the window followed a theme change only through its theme
    # subscription, which at times stopped)

    def save_tabs_config(self, tabs_data=None, *a, **k):
        if tabs_data is not None:
            from ..details.logic.tabs import save_tabs_config
            save_tabs_config(self.addon_config, tabs_data)

    def _save_widget(self, what):
        from .web_menus import save_from_deep_dive

        save_from_deep_dive(parent=self, **what)

    def _later(self, fn):
        QTimer.singleShot(0, fn)
        return True

    def _sync_config(self):
        """Re-read disk config into self.addon_config so Settings dialogs never see stale values from static handlers."""
        try:
            fresh = self.addon_config._read_config()
            if isinstance(fresh, dict):
                self.addon_config.config.clear()
                self.addon_config.config.update(fresh)
        except Exception:
            pass

    def _open_settings(self, start_tab=None):
        from .settings import open_settings_window

        self._sync_config()
        # while it is open the page reads this window's config (its live preview: theme, colors, stat cards)
        providers._LIVE["cfg"] = self.addon_config
        try:
            open_settings_window(self, start_tab)
        finally:
            providers._LIVE["cfg"] = None
        self._push_theme()
        self.bridge.push("refresh")

    def _deck_action(self, did, action):
        """A table deck's right-click menu: its color (or reset), left out of the stats, or the Settings' Decks tab."""
        from ..const.config import Config
        from ..i18n import tr

        if action == "settings":
            self._open_settings("Decks")
            return
        if did in ("total", "deleted"):
            key = did
            excl_val = "deleted" if did == "deleted" else None
        else:
            try:
                excl_val = int(did)
                key = str(excl_val)
            except (TypeError, ValueError):
                return
        self._sync_config()
        conf = self.addon_config.config
        if action == "color":
            from aqt.qt import QColor, QColorDialog, Qt

            colors = dict(conf.get(Config.DECK_COLORS, {}) or {})
            cur = colors.get(key)
            color = QColorDialog.getColor(QColor(cur) if cur else Qt.GlobalColor.white, self, tr("Pick Deck Color"))
            if not color.isValid():
                return
            colors[key] = color.name()
            conf[Config.DECK_COLORS] = colors
            self.addon_config.write_config()
            self.bridge.push("table_reload")
            return
        elif action == "reset_color":
            colors = dict(conf.get(Config.DECK_COLORS, {}) or {})
            if key not in colors:
                return
            colors.pop(key, None)
            conf[Config.DECK_COLORS] = colors
            self.addon_config.write_config()
            self.bridge.push("table_reload")
            return
        elif action == "exclude":
            if excl_val is None:
                return
            from ..details.ui.config.dialogs.deck_config_dialog import clear_stat_caches

            excluded = list(conf.get(Config.EXCLUDED_DECKS, []) or [])
            if excl_val in excluded:
                return
            conf[Config.EXCLUDED_DECKS] = excluded + [excl_val]
            clear_stat_caches()
        else:
            return
        self.addon_config.write_config()
        self.bridge.push("refresh")

    @staticmethod
    def _open_link(name):
        from ..details.ui.details_dialog import links

        links.open_link({"support": links.SUPPORT_URL, "rate": links.RATE_URL, "github": links.GITHUB_URL}.get(name))
        if name == "rate":  # the rating page opened from the toolbar: no need to ask anymore
            from ..details.ui.details_dialog.rate_prompt import mark_rated

            mark_rated()
        return True

    @staticmethod
    def _trends():
        from ..const.config import Config
        from ..config import addon_config as _addon_config

        return bool(_addon_config().config.get(Config.SHOW_TRENDS, False))

    def _save_path(self, title, name, filt):
        import os

        from aqt.qt import QFileDialog

        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        start = os.path.join(desktop if os.path.isdir(desktop) else os.path.expanduser("~"), name)
        path, _ = QFileDialog.getSaveFileName(self, title, start, filt)
        return path

    def _export_csv(self, header, rows, title=""):
        """Export Data (CSV): the table as shown (visible columns and rows, same file format as the normal window)."""
        import csv
        from datetime import datetime

        from aqt.utils import showCritical, showInfo

        from ..i18n import tr

        clean = "".join(c if c.isalnum() else "_" for c in (title or "Total"))
        path = self._save_path(tr("Export CSV"), f"Anki_Stats_{clean}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                               tr("CSV Files (*.csv)"))
        if not path:
            return
        if not path.lower().endswith(".csv"):
            path += ".csv"
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                out = csv.writer(f)
                out.writerow(header)
                for r in rows:
                    out.writerow(r)
            showInfo(tr("Exported to:\n{path}", path=path))
        except Exception as e:
            log_error(f"web csv export: {e!r}")
            showCritical(tr("CSV export failed:\n{error}", error=e))

    @staticmethod
    def _export_stats_on():
        from ..config import addon_config as _addon_config

        return bool(_addon_config().config.get("Export_Include_Stats", True))

    @staticmethod
    def _set_export_stats(on=True):
        """The Export menu's "Include Stat Cards" (every kind of image export)."""
        from ..config import addon_config as _addon_config

        _addon_config().set_value("Export_Include_Stats", bool(on))
        return True

    def _export_progress(self, done=None, total=None):
        """The window shows the export going on (and takes no click meanwhile): its pieces are drawn one by one in
        a hidden view, each after the page scrolled and painted there."""
        try:
            if done is None:
                self.webview.eval("DD.exportProgress && DD.exportProgress(null)")
            else:
                self.webview.eval("DD.exportProgress && DD.exportProgress(%d, %d)" % (int(done), int(total or 0)))
        except Exception:
            pass

    def _export_image(self, kind="full", title=None, period=None):
        """Export Deep Dive / Table + Dashboard / Full View like logic/export/visual.py: the export header, the stat
        cards, every chart (whole height) and every table row, at the same width, saved as PNG, PDF or JPEG.
        The page is drawn again in a hidden view at twice the resolution (pieces of the window's own screen,
        enlarged to that, came out blurred), with the window's deck, period,
        view and table; it scrolls itself there and is taken in pieces (DD.exportBegin / exportShot / exportRect).
        If that view cannot be made, the window's own page is used as before."""
        if getattr(self, "_exporting", False):
            return False
        self._exporting = True
        self._exp = {"kind": kind, "title": title or "", "period": period or "", "pieces": [], "n": 0, "i": 0,
                     "view": self.webview, "z": 1.0, "hidden": None, "stats": self._export_stats_on(),
                     "t0": time.monotonic()}
        self._export_progress(0, 0)

        def got_state(st):
            try:
                self._export_offscreen(st or {})
            except Exception as e:
                log_error(f"web export (hidden view): {e!r}")
                self._export_start()

        self.webview.evalWithCallback("DD.exportState ? DD.exportState() : null", got_state)
        return True

    def _export_offscreen(self, st):
        from aqt.qt import QTimer, Qt
        from aqt.webview import AnkiWebView

        from .bridge import Bridge

        w_css, h_css = float(st.get("w") or 0), float(st.get("h") or 0)
        if w_css < 50 or h_css < 50:
            raise ValueError("no page size")
        dpr = float(self.webview.devicePixelRatioF() or 1.0)
        z = max(1.0, 2.0 / dpr)  # 2 pixels per page pixel
        view = AnkiWebView(parent=None, title="deep_dive_export")
        view.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        view.resize(int(round(w_css * z)), int(round(h_css * z)))
        view.show()
        bridge = Bridge(view, self)
        self._register_handlers(bridge)
        self._exp.update({"hidden": (view, bridge), "z": z})
        override = (st.get("deck"), st.get("span")) if ("deck" in st or "span" in st) else None
        boot = self._boot(full=True, override_scope=override, query=str(st.get("search") or ""))
        boot["export"] = True
        boot["export_state"] = st
        tries = {"n": 0, "started": False}

        def ready(ok):
            if tries["started"] or not getattr(self, "_exporting", False):
                return
            if ok or tries["n"] > 60:
                tries["started"] = True
                trace(f"export: hidden page ready={bool(ok)} after {tries['n']} checks, page {w_css:.0f}x{h_css:.0f} at x{z:.2f} (screen x{dpr:.2f})")
                self._exp["view"] = view

                # a table with many columns scrolls sideways: the page is made as wide as it first (every column in
                # the picture; the charts of a Full View are then as wide too, the picture is that much wider)
                def widen(over):
                    try:
                        over = min(float(over or 0), 12000.0 - w_css)  # a sane limit (a picture ~24000 px wide)
                    except (TypeError, ValueError):
                        over = 0
                    if over > 1 and getattr(self, "_exporting", False):
                        trace(f"export: table {over:.0f} px wider than the page: page made {w_css + over:.0f} px wide")
                        view.resize(int(round((w_css + over + 2) * z)), int(round(h_css * z)))
                        QTimer.singleShot(60, lambda: view.eval("DD.exportNudge && DD.exportNudge();"))
                        QTimer.singleShot(600, self._export_start)  # laid out and the charts drawn at the new width
                        return
                    self._export_start()

                view.evalWithCallback("DD.exportOverflow ? DD.exportOverflow(%s) : 0" % json.dumps(self._exp["kind"]), widen)
                return
            tries["n"] += 1
            QTimer.singleShot(150, lambda: view.evalWithCallback("DD.exportReady ? DD.exportReady() : false", ready))

        def loaded(_ok=True):
            try:
                view.setZoomFactor(z)
            except Exception:
                pass
            # the zoom changes the page's pixel ratio: the charts are drawn again for it, then it is ready
            QTimer.singleShot(60, lambda: view.eval("DD.go && DD.go(); DD.exportNudge && DD.exportNudge();"))
            QTimer.singleShot(300, lambda: ready(False))

        try:
            view.loadFinished.connect(lambda ok: QTimer.singleShot(30, loaded))
        except Exception:
            QTimer.singleShot(1500, loaded)
        q = ""
        try:
            import os

            q = "?v=" + str(int(max(os.path.getmtime(f) for f in self._web_files())))
        except Exception:
            pass
        view.setZoomFactor(z)
        view.stdHtml(
            '<div id="dd-root"></div><script>%sDD.start(%s);</script>' % (dev_flag(), _script_json(boot)),
            css=[_url(self._addon, name) + q for name in _CSS],
            js=[_url(self._addon, name) + q for name in _JS],
            context=self,
        )

    def _export_start(self):
        view = self._exp["view"]

        def started(n):
            self._exp["n"] = int(n or 0)
            if not self._exp["n"]:
                self._export_end()
                from aqt.utils import showInfo
                from ..i18n import tr

                showInfo(tr("Nothing to export. Load some data first."))
                return
            self._export_next()

        # the page's background: the export's own (flat), so the pieces sit on it without the window's shaded backdrop
        bg = ""
        try:
            from ..details.logic.export import visual as V

            c = V._theme(self).get("bg")
            bg = c.name() if hasattr(c, "name") else str(c or "")
        except Exception:
            pass
        view.evalWithCallback("DD.exportBegin(%s, %s, %s)" % (json.dumps(self._exp["kind"]), json.dumps(bg),
                                                               json.dumps(bool(self._exp.get("stats", True)))), started)

    def _export_next(self):
        from aqt.qt import QTimer

        i = self._exp["i"]
        if i >= self._exp["n"]:
            self._export_end(finish=True)
            return
        view = self._exp["view"]
        self._export_progress(i, self._exp["n"])
        view.eval("DD.exportShot(%d)" % i)
        # the piece is taken once the page says it is painted (scrolled, its charts and rows drawn: two frames with
        # nothing moving), at most 700 ms after (it waited 220 ms for every piece)
        t0 = time.monotonic()

        def poll(ready=False):
            if not getattr(self, "_exporting", False):
                return
            if ready or time.monotonic() - t0 > 0.7:
                QTimer.singleShot(30, lambda: view.evalWithCallback("DD.exportRect(%d)" % i, self._export_take))
                return
            QTimer.singleShot(30, lambda: view.evalWithCallback("DD.exportShotReady ? DD.exportShotReady(%d) : true" % i, poll))

        QTimer.singleShot(40, lambda: view.evalWithCallback("DD.exportShotReady ? DD.exportShotReady(%d) : true" % i, poll))

    def _export_take(self, rect):
        try:
            if rect and rect.get("h", 0) > 0.5:
                from aqt.qt import QRect

                pix = self._exp["view"].grab()
                dpr = pix.devicePixelRatio() or 1.0
                k = dpr * float(self._exp.get("z") or 1.0)  # page pixels -> pixels of the picture (the zoom included)
                r = QRect(int(round(rect["x"] * k)), int(round(rect["y"] * k)), int(round(rect["w"] * k)), int(round(rect["h"] * k)))
                piece = pix.copy(r)
                piece.setDevicePixelRatio(k)
                if self._exp["i"] == 0:
                    trace(f"export: first piece {piece.width()}x{piece.height()} px for {rect['w']:.0f}x{rect['h']:.0f} page px (x{k:.2f}), view {'hidden' if self._exp.get('hidden') else 'window'}")
                self._exp["pieces"].append((rect["sec"], piece, float(rect["w"]), float(rect["h"])))
        except Exception as e:
            log_error(f"web export piece: {e!r}")
        self._exp["i"] += 1
        self._export_next()

    def _export_end(self, finish=False):
        self._export_progress(None)
        try:
            trace(f"export: {self._exp.get('n')} pieces in {time.monotonic() - self._exp.get('t0', time.monotonic()):.1f} s")
        except Exception:
            pass
        try:
            self._exp["view"].eval("DD.exportEnd()")
        except Exception:
            pass
        finally:
            self._exporting = False
            hidden = self._exp.get("hidden")
            if hidden:
                view, bridge = hidden
                self._exp["hidden"] = None
                try:
                    bridge.close()
                    view.hide()
                    view.cleanup()
                    view.deleteLater()
                except Exception:
                    pass
        if finish:
            try:
                self._export_compose()
            except Exception as e:
                import traceback

                from aqt.utils import showCritical
                from ..i18n import tr

                log_error(f"web export: {e!r}")
                showCritical(tr("Export failed:\n{error}", error=e) + f"\n\n{traceback.format_exc()}")

    def _export_compose(self):
        import os

        from aqt.qt import QFileDialog, QPainter, QPixmap, QRectF
        from aqt.utils import showCritical, showInfo

        from ..details.logic.export import visual as V
        from ..i18n import deck_title, tr

        # the pieces of each part stacked (logical px of the page)
        secs = []
        for sec, piece, w, h in self._exp["pieces"]:
            if not secs or secs[-1]["sec"] != sec:
                secs.append({"sec": sec, "pieces": [], "w": w, "h": 0.0})
            secs[-1]["pieces"].append((piece, w, h))
            secs[-1]["w"] = max(secs[-1]["w"], w)
            secs[-1]["h"] += h
        if not secs:
            showInfo(tr("Nothing to export. Load some data first."))
            return
        charts = next((s for s in secs if s["sec"] == "charts"), None)
        content_w = charts["w"] if charts else max(s["w"] for s in secs)
        for s in secs:
            s["k"] = content_w / s["w"] if s["w"] else 1.0
            s["rh"] = s["h"] * s["k"]
        total_w = int(round(content_w + V._PAD * 2))  # whole pixels: the header's QRect takes ints
        total_h = (V._HEADER_H + V._AFTER_HEADER_PAD + sum(s["rh"] for s in secs)
                   + max(0, len(secs) - 1) * V._BETWEEN_GAP + V._BEFORE_FOOTER_PAD + V._FOOTER_H)
        t = V._theme(self)
        pix = QPixmap(int(total_w * V._SCALE), int(total_h * V._SCALE))
        pix.fill(t["bg"])
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.scale(V._SCALE, V._SCALE)
        parts = [(tr("Deck"), deck_title(V._clean_deck_name(self._exp["title"] or "Collection")))]
        if self._exp["period"]:
            parts.append((tr("Time Range"), self._exp["period"]))
        V._draw_header(p, total_w, "Deep Dive Stats", parts, t)
        y = V._HEADER_H + V._AFTER_HEADER_PAD
        for i, s in enumerate(secs):
            yy = y
            for piece, w, h in s["pieces"]:
                p.drawPixmap(QRectF(V._PAD, yy, w * s["k"], h * s["k"]), piece, QRectF(0, 0, piece.width(), piece.height()))
                yy += h * s["k"]
            y += s["rh"] + (V._BETWEEN_GAP if i < len(secs) - 1 else 0)
        p.end()

        suffix = {"deep_dive": "DeepDive", "table": "Table", "full": "FullView"}
        from datetime import datetime

        fn = f"DeepDiveStats_{suffix.get(self._exp['kind'], self._exp['kind'])}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        start_dir = os.path.join(desktop if os.path.isdir(desktop) else os.path.expanduser("~"), fn)
        path, sel_filter = QFileDialog.getSaveFileName(
            self, tr("Save Export"), start_dir, tr("PNG Image (*.png);;PDF Document (*.pdf);;JPEG Image (*.jpg)"))
        if not path:
            return
        low = path.lower()
        if "pdf" in sel_filter.lower() or low.endswith(".pdf"):
            if not low.endswith(".pdf"):
                path += ".pdf"
            ok = bool(V._save_as_pdf(path, pix, total_w, total_h))
        else:
            jpeg = "jpeg" in sel_filter.lower() or "jpg" in sel_filter.lower()
            if not low.endswith((".png", ".jpg", ".jpeg")):
                path += ".jpg" if jpeg else ".png"
            ok = pix.save(path, quality=95) if path.lower().endswith((".jpg", ".jpeg")) else pix.save(path)
        if ok:
            showInfo(tr("Saved to:\n{path}", path=path))
        else:
            showCritical(tr("Could not save the export to:\n{path}", path=path))

    @staticmethod
    def _set_visual(which, on):
        """Visuals menu: a table column drawn as a bar (True) or as text."""
        from ..const.config import Config
        from ..config import addon_config as _addon_config

        key = {"buttons": Config.SHOW_BUTTONS_DIST_VISUAL, "all": Config.RETENTION_VISUAL_ALL,
               "young": Config.RETENTION_VISUAL_YOUNG, "mature": Config.RETENTION_VISUAL_MATURE}[which]
        cfg = _addon_config()
        cfg.config[key] = bool(on)
        cfg.write_config()
        return True

    @staticmethod
    def _set_trends(on):
        from ..const.config import Config
        from ..config import addon_config as _addon_config

        cfg = _addon_config()
        cfg.config[Config.SHOW_TRENDS] = bool(on)
        cfg.write_config()
        return True

    @staticmethod
    def _pie_separate(on):
        """Card Counts' "Sep. Susp." pill (charts._build_card_counts_section: PIE_CHART_SEPARATE_SUSPENDED)."""
        from ..const.config import Config
        from ..config import addon_config as _addon_config

        _addon_config().set_value(Config.PIE_CHART_SEPARATE_SUSPENDED, bool(on))
        return True

    @staticmethod
    def _set_table_columns(keys=None, counts=None, reset=False):
        """Columns added or removed from the table header's menu: one list for every time span (Settings > Time
        Span shows the same). reset: the default columns."""
        from ..details.logic.tabs.columns import DEFAULT_COLUMNS, DEFAULT_SHOW_COUNTS, set_table_columns
        from ..config import addon_config as _addon_config

        if reset:
            keys, counts = list(DEFAULT_COLUMNS), DEFAULT_SHOW_COUNTS
        cfg = _addon_config()
        cfg.write_config_vals(set_table_columns(cfg.config, keys, counts))
        return True

    @staticmethod
    def _set_expanded(names):
        """Decks opened or closed in the table: stored like the normal window does."""
        from ..const.config import Config
        from ..config import addon_config as _addon_config

        cfg = _addon_config()
        cfg.write_config_vals({
            Config.DETAILS_EXPANDED_DECKS: list(names or []),
            Config.DETAILS_EXPANDED_DECKS_SET: True,  # an empty list now means "all closed" (visibility.persist_expanded_decks)
        }, notify=False)
        return True

    @staticmethod
    def _open_day(date, deck=None):
        """A click on a heatmap day: the cards reviewed (or due) that day, in the Browser."""
        from ..details.logic.interactions import HeatmapInteractions

        HeatmapInteractions.open_browser_for_date(str(date)[:10], (deck if isinstance(deck, list) else int(deck)) if deck else None)
        return True

    def _boot(self, full=False, override_scope=None, query=""):
        """full: every chart's data (an export's hidden page); else the first ones only, ~300 ms of them (the
        window opens at once; the page asks the rest in the background, app.js lateData)."""
        deck, span = self._initial_scope()
        if override_scope is not None:
            o_deck, o_span = override_scope
            if o_deck is not None:
                deck = o_deck
            if o_span is not None:
                try:
                    span = int(o_span)
                except (TypeError, ValueError):
                    pass
        widgets = providers.default_widgets()
        from .deck_picker import DEFAULT_DECK, hidden_default

        decks = [[int(d.id), d.name] for d in mw.col.decks.all_names_and_ids(include_filtered=False)]
        if hidden_default():  # Anki's empty Default deck: left out, as in Anki's deck list
            decks = [d for d in decks if d[0] != DEFAULT_DECK]
        t0 = time.perf_counter()
        data = self._data(widgets, deck, span, budget_ms=None if (full or RECORD_PRELOAD) else 180, query=query)
        trace(f"first data {1000 * (time.perf_counter() - t0):.0f} ms")
        drawer = self._drawer()
        view_mode = self._view_mode()
        table0 = self._table0(view_mode, deck) if (full or drawer.get("open")) else None
        stats_data = self._with_search(query, lambda: providers.stats(deck, span)) if query else providers.stats(deck, span)
        return {
            "theme": build_theme("details"), "widgets": widgets, "deck": deck, "span": span,
            "decks": decks, "data": data, "settings": {"bin_scale": 100},
            "stats": stats_data, "deck_title": self._deck_title(deck),
            "trends": self._trends(), "spans": self._spans(),
            "view_mode": view_mode, "show_stats": self._show_stats(), "show_bottom_stats": self._show_bottom_stats(), "drawer": drawer, "table": table0, "grid_cols": self._grid_cols(),
            "sizes": self._sizes(), "globals": self._globals(), "layout": self._layout_opts(), "i18n": _web_i18n(),
            "export_stats": self._export_stats_on(), "anim": providers.anim_settings("details"),
            "recent_searches": self._recent_searches(),
            "tour_seen": bool(full or self._dd_tour_seen()),
            "chart_help": {w["type"]: self._chart_help(w["type"]) for w in widgets if isinstance(w, dict) and w.get("type")},
        }

    @staticmethod
    def _chart_order(order=None):
        """The charts dragged: their new order (Deep_Dive_Chart_Order); hidden ones stay at the end."""
        from ..const.config import Config
        from ..config import addon_config as _addon_config

        cfg = _addon_config()
        conf = cfg.config
        shown = [str(t) for t in (order or [])]
        rest = [t for t in (conf.get(Config.DEEP_DIVE_CHART_ORDER) or []) if t not in shown]
        cfg.set_value(Config.DEEP_DIVE_CHART_ORDER, shown + rest)
        return True

    @staticmethod
    def _stat_layout(order=None, rows=None):
        """The stat cards dragged: their order and the line of each (Dash_Stat_Order / Dash_Stat_Row_Nums)."""
        from ..const.config import Config
        from ..config import addon_config as _addon_config

        cfg = _addon_config()
        conf = cfg.config
        shown = [str(k) for k in (order or [])]
        full = list(conf.get(Config.DASH_STAT_ORDER) or [])
        it = iter(shown)
        slots = set(shown)
        merged = []
        for k in full:
            merged.append(next(it) if k in slots else k)
        merged += [k for k in it]
        conf[Config.DASH_STAT_ORDER] = merged
        conf[Config.DASH_STAT_ROW_NUMS] = {str(k): int(v) for k, v in (rows or {}).items() if int(v) > 0}
        cfg.write_config()
        return True

    @staticmethod
    def _globals():
        """The header gear menu ("Chart Options") of the normal window: its global choices."""
        from ..const.config import Config
        from ..config import addon_config as _addon_config

        conf = _addon_config().config
        root = conf.get(Config.DEEP_DIVE_WIDGET_SETTINGS) or {}
        m = root.get("manager_g") or root.get("manager") or {}
        return {
            "show_average": bool(m.get("show_average", True)), "avg_on_active_days": bool(m.get("avg_on_active_days", True)),
            "show_cumulative": bool(m.get("show_cumulative", True)), "sync_zoom": bool(m.get("sync_zoom", True)),
            "binning": bool(conf.get(Config.ADAPTIVE_CHART_BINNING, True)),
        }

    def _global_option(self, name, value=None):
        from ..const.config import Config
        from ..config import addon_config as _addon_config

        cfg = _addon_config()
        if name in ("show_average", "avg_on_active_days", "sync_zoom"):
            self._set_setting("manager", name, bool(value))
        elif name == "show_cumulative":
            self._set_setting("manager", name, bool(value))
            for section in ("activity", "added", "hourly", "future_due", "review_intervals", "stability"):
                self._set_setting(section, "show_cumulative", bool(value))
        elif name == "binning":
            cfg.config[Config.ADAPTIVE_CHART_BINNING] = bool(value)
            for section in ("activity", "retention", "added", "future_due", "review_intervals", "stability", "difficulty", "retrievability",
                            "interval_load", "lapse_distribution", "review_distribution", "learning_steps", "time_distribution", "interval_history", "stability_history", "difficulty_history", "ratings", "review_speed",
                            "forgotten", "resets", "introduced", "introduced_load", "answer_time", "interval_ratings", "rating_fatigue", "sibling_ratings", "card_states", "load_trend", "stability_trend", "memorised", "fsrs_calibration", "forgetting_curve", "fsrs_fatigue", "leech_detector", "stability_increase", "custom_bar", "future_retention"):
                self._set_setting(section, "binning_override", None)
            cfg.write_config()  # the page redraws its charts itself (toggle_global_binning)
        elif name == "axis_anim":
            cfg.config[Config.CHART_AXIS_ANIM] = "slide" if value == "slide" else "count"
            cfg.write_config()  # the page redraws its charts itself; the pinned ones take it with their next theme
        elif name == "num_anim":
            cfg.config[Config.STAT_NUM_ANIM] = "roll" if value == "roll" else "count"
            cfg.write_config()  # the page takes it at once; the pinned cards with their next theme
        elif name == "reset_layout":
            conf = cfg.config
            conf.pop(Config.DEEP_DIVE_CHART_ORDER, None)
            settings = conf.get(Config.DEEP_DIVE_WIDGET_SETTINGS) or {}
            for sec in settings.values():
                if isinstance(sec, dict):
                    sec.pop("height", None)
                    sec.pop("height_scale", None)
                    if "col_span" in sec:
                        sec["col_span"] = 1
            cfg.write_config()
            self._later(self._load_page)
        return True

    @staticmethod
    def _browse(deck=None, span=-1, kind=None, label=None, hour=None, query=None, pie=None, revs=None, leech=None, sinc=None):
        """A click on a chart: its cards in Anki's browser (chart_utils.browser_click._target)."""
        from ..details.logic.interactions import browser_search as bs
        from ..details.widgets.chart_utils.browser_click import _PIE_QUERIES
        from ..i18n import tr

        # several decks picked together in the table: a list of deck ids (and "deleted")
        deck = None if deck in (None, 0) else (deck if isinstance(deck, list) else int(deck))
        if isinstance(revs, dict):
            # the answers behind a cell, a bar or a slice of a chart of reviews (browser_search.reviews_sql)
            bs.open_reviews(revs, int(span), deck)
        elif leech is not None:
            # Leech Detector: the cards of the bars [lo, hi) (5% bins of their odds, fsrs_history.leech_odds)
            from ..details.logic.metrics import fsrs_history

            lo, hi = int(leech[0]), int(leech[1])
            _counts, where = fsrs_history.leech_odds(fsrs_history.deck_cards(providers._cfg(), deck, deck == -1))
            cids = [str(c) for b, c in where if lo <= b < hi]
            if cids:
                bs.open_query("cid:" + ",".join(cids), None)
        elif sinc is not None:
            # Stability Increase Factor: the cards of the bars [lo, hi) (logic.metrics.sinc.binned)
            from ..details.logic.metrics import sinc as _sinc

            lo, hi = int(sinc[0]), int(sinc[1])
            b = _sinc.binned(_sinc.factors(providers._cfg(), deck, deck == -1))
            cids = [str(c) for c, i in (b[2].items() if b else ()) if lo <= i < hi]
            if cids:
                bs.open_query("cid:" + ",".join(cids), None)
        elif pie is not None:
            if pie == "deleted":
                bs._tip(tr("Deleted cards cannot be shown in the browser"))
            elif _PIE_QUERIES.get(pie):
                bs.open_query(_PIE_QUERIES[pie], deck)
        elif hour is not None:
            bs.open_cards_for_hour(int(hour), int(span), deck)
        elif query:
            bs.open_query(str(query), deck)
        elif label is not None:
            bs.open_cards_for_label(kind or "reviewed", str(label), deck) or bs._tip(tr("No date for this bar"))
        return True

    def _ask_int(self, title="", label="", value=0, min=0, max=10000):
        """A number asked with QInputDialog.getInt; None when cancelled."""
        from aqt.qt import QInputDialog

        from ..i18n import tr_name

        v, ok = QInputDialog.getInt(self, tr_name(title), tr_name(label), int(value or 0), int(min), int(max))
        return int(v) if ok else None

    def _stat_settings(self, key=None, label=None):
        """Right click on a stat card > Settings (stats_cards.core.menu._open_dashboard_card_settings)."""
        from ..details.ui.config import widget_settings_dialog
        from ..details.logic.stat_cards import get_dashboard_local_stat_style

        self._sync_config()
        conf = self.addon_config.config
        widget_def = {"id": f"dashboard_{key}", "type": "stat_card", "label": label or key, "stat_key": key}
        dlg = widget_settings_dialog(widget_def, parent=self._dialog_host(), global_config=conf,
                                   local_config=get_dashboard_local_stat_style(conf, key), theme_config=conf)
        providers._LIVE["cfg"] = self.addon_config
        try:
            dlg.exec()
        finally:
            providers._LIVE["cfg"] = None
        self._push_theme()
        self.bridge.push("refresh")
        return True

    @staticmethod
    def _open_card(cid=None):
        """Click on a review dot: the card in the browser (review_dots.mouseReleaseEvent)."""
        from ..details.logic.interactions import browser_search

        browser_search.open_card(int(cid))
        return True

    @staticmethod
    def _stat_lock(key=None, locked=True):
        """Click on a stat card: its glow border stays on (locked) or only shows on hover (UNLOCKED_EFFECTS)."""
        from ..config import addon_config as _addon_config

        cfg = _addon_config()
        lst = [x for x in (cfg.config.get("UNLOCKED_EFFECTS") or []) if x != key]
        if not locked:
            lst.append(str(key))
        cfg.set_value("UNLOCKED_EFFECTS", lst)
        return True

    @staticmethod
    def _stat_hide(key=None, show=False):
        from ..config import addon_config as _addon_config

        cfg = _addon_config()
        cfg.set_value(str(key), bool(show))
        return True

    @staticmethod
    def _stat_swap(key=None):
        """Right-click "Active days only": the card becomes its twin (Reviews/Day <-> Reviews/Active Day), at the same
        place, with the same line, name (when renamed), color and look."""
        from ..const.config import Config
        from ..config import addon_config as _addon_config
        from ..details.logic.stat_cards import active_day_twin

        twin = active_day_twin(str(key))
        if not twin:
            return False
        to = twin[0]
        cfg = _addon_config()
        conf = cfg.config
        order = [k for k in (conf.get(Config.DASH_STAT_ORDER) or []) if k != to]
        order = [to if k == key else k for k in order]
        if to not in order:
            order.append(to)
        vals = {key: False, to: True, Config.DASH_STAT_ORDER: order}
        for per_card in (Config.DASH_STAT_ROW_NUMS, Config.DASH_STAT_LABELS, Config.DASH_STAT_STYLES, Config.DASH_STAT_COLORS):
            d = dict(conf.get(per_card) or {})
            if key in d:
                d[to] = d.pop(key)
                vals[per_card] = d
        cfg.write_config_vals(vals)
        return True

    @staticmethod
    def _stat_color(key=None, color=None):
        """A card's own color (None: back to the shared color of the stat)."""
        from ..const.config import Config
        from ..config import addon_config as _addon_config

        cfg = _addon_config()
        colors = dict(cfg.config.get(Config.DASH_STAT_COLORS) or {})
        if color:
            colors[str(key)] = str(color)
        else:
            colors.pop(str(key), None)
        cfg.set_value(Config.DASH_STAT_COLORS, colors)
        return True

    def _stat_icon(self, key=None, mode=None, pos=None):
        """Stat card right-click Icon mode ('off'|'inline'|'corner'|'watermark') and/or position ('tl'|'tr'|'bl'|'br')."""
        from ..const.config import Config

        cfg = self.addon_config
        styles = dict(cfg.config.get(Config.DASH_STAT_STYLES) or {})
        entry = dict(styles.get(str(key)) or {}) if key else {}
        own = bool(key and entry.get("use_custom_style"))
        changed = False
        if mode in ("off", "inline", "watermark"):
            if own:
                entry[Config.DASHBOARD_SHOW_ICONS] = mode
            else:
                cfg.set_value(Config.DASHBOARD_SHOW_ICONS, mode)
            changed = True
        if pos in ("tl", "tr", "bl", "br"):
            if own:
                entry[Config.DASHBOARD_ICON_POS] = pos
            else:
                cfg.set_value(Config.DASHBOARD_ICON_POS, pos)
            changed = True
        if not changed:
            return False
        if own:
            styles[str(key)] = entry
            cfg.set_value(Config.DASH_STAT_STYLES, styles)
        self._push_theme()
        return True

    @staticmethod
    def _stat_pin(key=None, label=None, span=-1):
        from ..details.logic.widget_registry import WidgetRegistry
        from ..details.widgets.pinned.main_menu.manager import MainMenuWidgetManager
        from ..details.logic.stat_cards import stat_card_label_to_save

        WidgetRegistry.add("stat_card", stat_card_label_to_save(str(key), str(label or key)),
                           stat_key=str(key), deck_id=None, time_span=int(span))
        if MainMenuWidgetManager.instance_exists():
            MainMenuWidgetManager.instance().refresh()
        return True

    @staticmethod
    def _sizes():
        """Card sizes set by hand: {"scale": shared height factor or None, "spans": {type: columns}}."""
        from ..const.config import Config
        from ..config import addon_config as _addon_config

        root = _addon_config().config.get(Config.DEEP_DIVE_WIDGET_SETTINGS) or {}
        scale = (root.get("_grid") or {}).get("height_scale")
        spans = {}
        for key, v in root.items():
            if key == "_grid" or not isinstance(v, dict):
                continue
            base = key[:-2] if key.endswith("_g") else key
            try:
                n = int(v.get("col_span") or 1)
            except (TypeError, ValueError):
                n = 1
            if n > 1 and (key.endswith("_g") or base not in spans):
                spans[base] = n
        return {"scale": scale, "spans": spans}

    @staticmethod
    def _set_card_size(type=None, col_span=None, scale=None):
        """A card resized in the page: same keys as the normal window (_grid.height_scale, <type>.col_span)."""
        from ..const.config import Config
        from ..config import addon_config as _addon_config

        cfg = _addon_config()
        root = cfg.config.setdefault(Config.DEEP_DIVE_WIDGET_SETTINGS, {})
        if scale is not None:
            root.setdefault("_grid", {})["height_scale"] = float(scale)
        if type and col_span is not None:
            for key in (type, f"{type}_g"):
                if key == type or key in root:
                    root.setdefault(key, {})["col_span"] = int(col_span)
        cfg.write_config()
        return True

    @staticmethod
    def _reset_card_size():
        from ..const.config import Config
        from ..config import addon_config as _addon_config

        cfg = _addon_config()
        root = cfg.config.get(Config.DEEP_DIVE_WIDGET_SETTINGS) or {}
        for v in root.values():
            if isinstance(v, dict):
                v.pop("height", None)
                v.pop("height_scale", None)
                if "col_span" in v:
                    v["col_span"] = 1
        cfg.write_config()
        return True

    @staticmethod
    def _drawer():
        """The table drawer's remembered state (same config keys as the normal window)."""
        from ..const.config import Config
        from ..config import addon_config as _addon_config

        conf = _addon_config().config
        sizes = conf.get(Config.DETAILS_TABLE_DRAWER_SIZES) or [0, 0]
        return {
            "open": bool(conf.get(Config.DETAILS_TABLE_DRAWER_OPEN, False)),
            "auto_close": bool(conf.get(Config.DETAILS_TABLE_DRAWER_AUTO_CLOSE, True)),
            "stack": int(sizes[1]) if len(sizes) > 1 else 0,
            "shortcut": str(conf.get(Config.DETAILS_TABLE_DRAWER_SHORTCUT, "T") or ""),
            "show": bool(conf.get(Config.DETAILS_TABLE_SHOW, True)),
        }

    @staticmethod
    def _set_scope(deck=None, span=None):
        """The deck and period shown are remembered like the normal window does."""
        import time as _time

        from ..const.config import Config

        providers.LAST_SCOPE[0] = _time.monotonic()
        from ..config import addon_config as _addon_config

        vals = {}
        if deck is not None and not isinstance(deck, list):  # several decks together: not remembered (one deck is)
            vals[Config.DETAILS_DEEP_DIVE_IDENTIFIER] = int(deck) if deck else "[[TOTAL]]"
        if span is not None:
            vals[Config.DETAILS_DEEP_DIVE_PERIOD_RANGE] = int(span)
        if vals:
            _addon_config().write_config_vals(vals, notify=False)
        return True

    def _widget_opts(self):
        """Every chart's options and the grid's layout settings now (a Settings dialog saved: Chart Style, Collapsible
        Charts, Fill Height, Same Height for All Rows), without its data."""
        return {"options": {w["id"]: w.get("options") for w in providers.default_widgets()}, "layout": self._layout_opts(),
                "anim": providers.anim_settings("details")}

    @staticmethod
    def _layout_opts():
        """Settings > General > Deep Dive: chevrons on the charts, the rows filling the window, one height for all."""
        from ..const.config import Config
        from ..config import addon_config as _addon_config

        c = _addon_config().config
        return {"collapsible": bool(c.get(Config.DEEP_DIVE_CHARTS_COLLAPSIBLE, True)),
                "fill": bool(c.get(Config.DEEP_DIVE_FILL_HEIGHT, True)),
                "shared": bool(c.get(Config.DEEP_DIVE_SHARED_ROW_HEIGHT, False))}

    def _widgets_now(self, deck=None, span=-1):
        """The charts shown now (after the gallery changed them) with their data."""
        widgets = providers.default_widgets()
        return {"widgets": widgets, "data": self._data(widgets, deck, span), "stats": providers.stats(deck or None, span)}

    def _chart_catalog(self):
        """Every chart the gallery offers: [{type, name (shown), en (English), group, shown}] (Find chart's suggestions)."""
        from types import SimpleNamespace

        from ..details.ui.deep_dive import extra_charts as ec
        from ..details.widgets.pinned.main_menu.ui.add_widget_menu import chart_groups
        from ..i18n import tr_name

        shown = set(ec.shown_charts(SimpleNamespace(addon_config=self.addon_config)))
        return [{"type": wtype, "name": tr_name(label), "en": str(label), "group": tr_name(group), "shown": wtype in shown}
                for group, charts in chart_groups() for wtype, label in charts]

    def _add_chart(self, type=None):
        """A chart put in Deep Dive from Find chart's suggestions (as the gallery adds it), shown at once."""
        from types import SimpleNamespace

        from ..details.ui.deep_dive import extra_charts as ec

        mgr = SimpleNamespace(addon_config=self.addon_config)
        if not type or type in ec.shown_charts(mgr):
            return False
        ec._show(mgr, type)
        self.bridge.push("rebuild")
        return True

    def _open_gallery(self, family="chart"):
        """The Charts button: the same gallery as the normal window (add / remove charts and stat cards)."""
        import copy
        from types import SimpleNamespace

        from ..const.config import Config
        from ..details.ui.deep_dive import extra_charts as ec
        from ..details.widgets.charts.more_charts import CHARTS
        from ..details.widgets.pinned.main_menu.manager import MainMenuWidgetManager
        from .gallery_web import open_manage_gallery

        self._sync_config()
        cfg = self.addon_config
        mgr = SimpleNamespace(addon_config=cfg)
        conf = cfg.config
        keys = [k for k in (conf.get(Config.DASH_STAT_ORDER) or [])]

        def card_shown(k):
            return bool(conf.get(k, True))

        snap = {
            "hidden": ec.hidden_types(mgr), "extra": ec.extra_types(mgr),
            "cards": {k: card_shown(k) for k in keys},
            "order": copy.deepcopy(conf.get(Config.DEEP_DIVE_CHART_ORDER)),
            "sizes": copy.deepcopy(conf.get(Config.DEEP_DIVE_WIDGET_SETTINGS)),
            "stat_order": copy.deepcopy(conf.get(Config.DASH_STAT_ORDER)),
            "stat_rows": copy.deepcopy(conf.get(Config.DASH_STAT_ROW_NUMS)),
            "texts": copy.deepcopy(conf.get(Config.DEEP_DIVE_TEXT_WIDGETS)),
        }

        def set_card(k, on):
            cfg.set_value(k, bool(on))
            if on:  # a card put back goes at the end
                order = [x for x in (conf.get(Config.DASH_STAT_ORDER) or []) if x != k] + [k]
                cfg.set_value(Config.DASH_STAT_ORDER, order)

        def set_chart(wtype, on):
            if on:
                ec._show(mgr, wtype)
            elif wtype in ec.base_types():
                if wtype not in ec.hidden_types(mgr):
                    ec._save_hidden(mgr, ec.hidden_types(mgr) + [wtype])
            else:
                ec._save(mgr, [t for t in ec.extra_types(mgr) if t != wtype])

        # each change shows at once in the window behind the gallery (live preview)
        from aqt.qt import QTimer

        live = {"t": None}

        def show_now():
            if live["t"] is None:
                live["t"] = QTimer(self)
                live["t"].setSingleShot(True)
                live["t"].timeout.connect(lambda: self.bridge.push("rebuild"))
            live["t"].start(60)  # a burst of clicks rebuilds once

        def toggle(choice, on):
            if choice.family == "stat":
                set_card(choice.stat_key, on)
            elif choice.family == "chart":
                set_chart(choice.widget_type, on)
            show_now()

        def reset():
            for k in keys:
                default = bool(Config.DEFAULT_CONFIG.get(k, True))
                if default != card_shown(k):
                    cfg.set_value(k, default)
            ec._save_hidden(mgr, [])
            ec._save(mgr, [])
            conf.pop(Config.DEEP_DIVE_CHART_ORDER, None)
            # the stat cards' order and lines too
            import copy as _copy

            conf[Config.DASH_STAT_ORDER] = _copy.deepcopy(Config.DEFAULT_CONFIG.get(Config.DASH_STAT_ORDER, []))
            conf[Config.DASH_STAT_ROW_NUMS] = {}
            settings = conf.get(Config.DEEP_DIVE_WIDGET_SETTINGS) or {}
            for section in settings.values():
                if isinstance(section, dict):
                    section.pop("height", None)
                    section.pop("height_scale", None)
                    if "col_span" in section:
                        section["col_span"] = 1
            cfg.write_config()
            show_now()
            return ec.shown_charts(mgr), [k for k in keys if card_shown(k)]

        # the Text tile: a click writes a new text (the editor over the gallery), its "−" takes one off
        def add_text(template):
            wid = self._add_text(template)
            if wid:
                show_now()
            return wid

        def remove_text(wid=None):
            texts = self._texts_now()
            if wid not in texts:  # not one added from here: the last text shown
                mine = [w["type"] for w in providers.default_widgets() if providers.is_text(w["type"])]
                wid = mine[-1] if mine else None
            if wid is None or self._remove_text(wid) is None:
                return False
            show_now()
            return True

        result = open_manage_gallery(
            MainMenuWidgetManager.instance(), self,
            charts=ec.base_types() + [m.widget_type for m in CHARTS],
            charts_shown=ec.shown_charts(mgr),
            stats=keys, stats_shown=[k for k in keys if card_shown(k)],
            family=family, on_toggle=toggle, on_reset=reset,
            texts=len(self._texts_now()), on_add_text=add_text, on_remove_text=remove_text,
        )
        if result is None:  # Cancel: everything back as it was
            for k, v in snap["cards"].items():
                if card_shown(k) != v:
                    cfg.set_value(k, v)
            ec._save_hidden(mgr, snap["hidden"])
            ec._save(mgr, snap["extra"])
            for key, value in ((Config.DEEP_DIVE_CHART_ORDER, snap["order"]), (Config.DEEP_DIVE_WIDGET_SETTINGS, snap["sizes"]),
                               (Config.DASH_STAT_ORDER, snap["stat_order"]), (Config.DASH_STAT_ROW_NUMS, snap["stat_rows"]),
                               (Config.DEEP_DIVE_TEXT_WIDGETS, snap["texts"])):
                if value is None:
                    conf.pop(key, None)
                else:
                    conf[key] = value
            cfg.write_config()
        self.bridge.push("rebuild")

    @staticmethod
    def _grid_cols():
        from ..const.config import Config
        from ..config import addon_config as _addon_config

        try:
            return int(_addon_config().config.get(Config.DEEP_DIVE_GRID_COLUMNS, 3))
        except Exception:
            return 3

    @staticmethod
    def _set_grid_cols(cols):
        from ..const.config import Config
        from ..config import addon_config as _addon_config

        cfg = _addon_config()
        cfg.config[Config.DEEP_DIVE_GRID_COLUMNS] = int(cols)
        cfg.write_config_vals({Config.DEEP_DIVE_GRID_COLUMNS: int(cols)})
        return True

    @staticmethod
    def _view_mode():
        from ..const.config import Config
        from ..config import addon_config as _addon_config

        return _addon_config().config.get(Config.DETAILS_VIEW_MODE, "time")

    @staticmethod
    def _table0(view_mode="time", deck=None):
        """The table the window opens with, in the view it was left in (View by Deck: the open deck's periods; it
        opened by time, then switched). None with the table turned off (Show Table): it is not loaded."""
        try:
            from ..const.config import Config
            from ..config import addon_config as _addon_config

            if not _addon_config().config.get(Config.DETAILS_TABLE_SHOW, True):
                return None
            if view_mode == "deck":
                deck_key = "collection" if (not deck or isinstance(deck, list)) else ("__deleted_cards__" if deck == -1 else str(deck))
                return providers._plain(providers.table(0, deck=deck_key))
            return providers._plain(providers.table(0, None))
        except Exception as e:
            log_error(f"web table boot: {e!r}")
            return None

    @staticmethod
    def _set_drawer(open=None, auto_close=None, size=None):
        from ..const.config import Config
        from ..config import addon_config as _addon_config

        cfg = _addon_config()
        vals = {}
        if open is not None:
            vals[Config.DETAILS_TABLE_DRAWER_OPEN] = bool(open)
        if auto_close is not None:
            vals[Config.DETAILS_TABLE_DRAWER_AUTO_CLOSE] = bool(auto_close)
        if size is not None:
            cur = list(cfg.config.get(Config.DETAILS_TABLE_DRAWER_SIZES) or [0, 0])
            while len(cur) < 2:
                cur.append(0)
            cur[1] = int(size)
            vals[Config.DETAILS_TABLE_DRAWER_SIZES] = cur
        if vals:
            cfg.write_config_vals(vals, notify=False)
        return True

    @staticmethod
    def _spans():
        """The Time Span menu entries: the user's enabled-or-not tabs, like populate_span_menu."""
        from ..const import Period
        from ..details.logic.tabs import get_tabs_config
        from ..config import addon_config as _addon_config
        from ..i18n import N_, tr_name

        out, seen = [], set()
        for tab in get_tabs_config(_addon_config()):
            r = tab.get("range")
            if r is None:
                continue
            days = tab.get("days") if r == Period.CUSTOM else None
            if r != Period.CUSTOM:
                if r in seen:
                    continue
                seen.add(r)
            out.append([tr_name(tab.get("title") or N_("Stats")), int(r), days])
        return out

    @staticmethod
    def _initial_scope():
        """Deck and period the normal window opened with last (same config keys)."""
        from ..const.config import Config
        from ..config import addon_config as _addon_config

        conf = _addon_config().config
        deck, span = None, conf.get(Config.DETAILS_DEEP_DIVE_PERIOD_RANGE)
        ident = conf.get(Config.DETAILS_DEEP_DIVE_IDENTIFIER)
        if ident in ("[[TOTAL]]", "Deleted Cards"):
            deck = 0 if ident == "[[TOTAL]]" else -1
        else:
            try:
                deck = int(ident)
                if mw.col.decks.get(deck, default=False) is None:
                    deck = None
                elif deck == 1:  # Anki's Default deck left empty: all decks, rather than empty charts
                    from .deck_picker import hidden_default

                    if hidden_default():
                        deck = None
            except Exception:
                deck = None
        if deck is None:
            deck = int(mw.col.decks.selected())
            try:
                # An empty selected deck (Default after an import): all decks, rather than empty charts.
                ids = list(mw.col.decks.deck_and_child_ids(deck))
                if not mw.col.db.scalar(f"select 1 from cards where did in ({','.join(map(str, ids))}) limit 1"):
                    deck = 0
            except Exception:
                pass
        try:
            span = int(span)
        except (TypeError, ValueError):
            span = -1
        return deck, span

    @staticmethod
    def _table_tab_order(order=None):
        """A time tab of the table dragged to another place: the enabled time spans in their new order (positions in
        the old one), saved as the normal window's movable tabs do (time_spans._apply_tab_order: the disabled ones
        keep their slots)."""
        from ..details.logic.tabs import get_tabs_config, save_tabs_config
        from ..config import addon_config as _addon_config

        cfg = _addon_config()
        full = get_tabs_config(cfg)
        enabled = [i for i, t in enumerate(full) if t.get("enabled", True)]
        try:
            order = [int(x) for x in (order or [])]
        except (TypeError, ValueError):
            return False
        if sorted(order) != list(range(len(enabled))):
            return False
        new_full = list(full)
        for slot, src in zip(enabled, (enabled[i] for i in order)):
            new_full[slot] = full[src]
        save_tabs_config(cfg, new_full)
        return True

    @staticmethod
    def _deck_title(deck):
        # the same titles as the page gives when the deck is changed there (app.js), not Anki's "[no deck]"
        if isinstance(deck, list):
            return f"{len(deck)} decks" if len(deck) != 1 else WebDeepDiveDialog._deck_title(deck[0])
        if deck == 0:
            return "Total"
        if deck == -1:
            return "Deleted Cards"
        try:
            return mw.col.decks.name(deck).split("::")[-1]
        except Exception:
            return ""

    @staticmethod
    def _dd_tour_seen():
        try:
            from ..details.logic.user_state import load_state
            return bool(load_state("tips.json").get("deep_dive_tour"))
        except Exception:
            return False

    @staticmethod
    def _dd_tour_done():
        try:
            from ..details.logic.user_state import load_state, save_state
            st = load_state("tips.json")
            st["deep_dive_tour"] = True
            save_state("tips.json", st)
        except Exception:
            pass
        return True

    def _dd_tour_gallery_prep(self):
        """Capture an offscreen screenshot of Deep Dive's Add / Remove gallery for step 2 of the tour."""
        if getattr(self, "_dd_tour_shot", None) is not None or getattr(self, "_dd_tour_busy", False):
            return True
        self._dd_tour_busy = True
        try:
            from types import SimpleNamespace
            from ..const.config import Config
            from ..details.ui.deep_dive import extra_charts as ec
            from ..details.widgets.charts.more_charts import CHARTS
            from ..details.widgets.pinned.main_menu.manager import MainMenuWidgetManager
            from .gallery_model import GalleryModel
            from .gallery_web import WebGallery
            from .tour import _data_url, _offscreen

            cfg = self.addon_config
            conf = cfg.config
            mgr = SimpleNamespace(addon_config=cfg)
            keys = [k for k in (conf.get(Config.DASH_STAT_ORDER) or [])]
            shown_stats = [k for k in keys if bool(conf.get(k, True))]
            all_charts = ec.base_types() + [m.widget_type for m in CHARTS]
            shown_charts = list(ec.shown_charts(mgr))
            model = GalleryModel(
                MainMenuWidgetManager.instance(), family="chart", only=all_charts, taken=shown_charts,
                stats=keys, stats_taken=shown_stats, toggle=True, context="details",
            )
            g = WebGallery(model, self)
            self._dd_tour_gal = g  # keep alive until finish()
            _offscreen(g)
            g.show()
            chart_tid = next((t.id for t in g.model.tiles.values() if t.choice.widget_type == "forgetting_curve"), None)
            if chart_tid is None:
                chart_tid = next((t.id for t in g.model.tiles.values() if t.choice.widget_type not in ("stat_card", "text_label")), None)
            stat_tid = next((t.id for t in g.model.tiles.values() if t.choice.widget_type == "stat_card"), None)
            todo = [(k, tid) for k, tid in (("chart", chart_tid), ("stat", stat_tid)) if tid is not None]
            shots = {}
            deadline = time.monotonic() + 12.0

            def finish():
                self._dd_tour_busy = False
                if shots:
                    self._dd_tour_shot = shots
                gal = getattr(self, "_dd_tour_gal", None)
                self._dd_tour_gal = None
                if gal is not None:
                    try:
                        gal.done(0)
                        gal.deleteLater()
                    except RuntimeError:
                        pass

            def run_next(idx):
                if idx >= len(todo):
                    finish()
                    return
                kind, tid = todo[idx]
                js = f"DD.galleryTour ? DD.galleryTour({json.dumps(tid)}, null) : null"

                def check():
                    try:
                        g.webview.evalWithCallback(js, got)
                    except RuntimeError:
                        finish()

                def got(r):
                    if not (isinstance(r, dict) and r.get("ready")):
                        if time.monotonic() > deadline:
                            run_next(idx + 1)
                            return
                        QTimer.singleShot(120, check)
                        return
                    QTimer.singleShot(int(r.get("fade") or 0) + 120, lambda: g.webview.evalWithCallback(js, take))

                def take(r):
                    try:
                        pm = g.webview.grab()
                        if isinstance(r, dict) and not pm.isNull():
                            shots[kind] = {
                                "pic": _data_url(pm),
                                "w": int(r.get("vw") or g.webview.width()),
                                "h": int(r.get("vh") or g.webview.height()),
                                "x": int(r.get("x") or 0),
                                "y": int(r.get("y") or 0),
                            }
                            self._dd_tour_shot = dict(shots)
                    except Exception:
                        pass
                    run_next(idx + 1)

                QTimer.singleShot(120, check)

            run_next(0)
        except Exception as e:
            self._dd_tour_busy = False
            log_warn(f"dd tour gallery prep: {e!r}", tag="WEB")
        return True

    def _dd_tour_gallery(self):
        return getattr(self, "_dd_tour_shot", None)

    @staticmethod
    def _with_search(query, fn):
        from ..details.logic.search_filter import search_scope

        with search_scope(query):
            return fn()

    def _recent_searches(self):
        raw = self.addon_config.config.get("Deep_Dive_Recent_Searches") or []
        return [str(q) for q in raw if str(q or "").strip()][:8]

    def _resolve_search(self, query="", save=True):
        """Main-thread Anki search query validation + card ID resolution."""
        from ..details.logic.search_filter import normalize_query, resolve_search

        q = normalize_query(query)
        if not q:
            return {"ok": True, "query": "", "count": None, "recent": self._recent_searches()}
        cids, err = resolve_search(q)
        if err is not None:
            return {"ok": False, "query": q, "error": err, "recent": self._recent_searches()}
        recent = self._recent_searches()
        if save:
            recent = [q] + [x for x in recent if x != q]
            recent = recent[:8]
            try:
                self.addon_config.set_value("Deep_Dive_Recent_Searches", recent, notify=False)
            except Exception:
                pass
        return {"ok": True, "query": q, "count": len(cids or ()), "recent": recent}

    @staticmethod
    def _data(widgets, deck, span, budget_ms=None, query=""):
        """budget_ms: stop once that much time is spent (the caller asks again for the rest), so
        the UI thread is never held long; what is already known (memo) costs next to nothing."""
        import time as _tb
        from ..details.logic.search_filter import normalize_query, search_scope

        _start = _tb.perf_counter()
        deck = deck or None  # 0 = the Total row: whole collection
        q = normalize_query(query)
        out = {}
        cache = {}
        times = []
        from ..details.logic.logger import log_warn as _lw
        from ..config import addon_config as _addon_config
        try:
            fp = repr(sorted(_addon_config().config.items(), key=lambda kv: str(kv[0])))
        except Exception:
            fp = str(_tb.monotonic())  # unknown config state: never reuse
        with search_scope(q):
            for w in widgets:
                if budget_ms and out and 1000 * (_tb.perf_counter() - _start) > float(budget_ms):
                    break
                key = (w["type"], json.dumps(w.get("options") or {}, sort_keys=True))
                if key not in cache:  # same chart type and options: computed once
                    _t0 = _tb.perf_counter()
                    val, hit = providers._memo(("w", w["type"], deck, span, key[1], fp, q),
                                               lambda w=w: providers.fetch(w["type"], deck, span, w.get("options")), ttl=1e9 if RECORD_PRELOAD else 120.0)
                    ms = 1000 * (_tb.perf_counter() - _t0)
                    if ms > 15:
                        _lw(f"data {w['type']} {ms:.0f}ms ({'memo' if hit else 'computed'})", tag="WEB")
                    times.append((ms, w["type"], hit))
                    cache[key] = val
                out[w["id"]] = cache[key]
        # dev trace: a slow call, the time its charts took (each under 15 ms is not written above) against its whole
        total = 1000 * (_tb.perf_counter() - _start)
        if total >= 20:
            times.sort(reverse=True)
            top = ", ".join(f"{t} {m:.0f}ms" + ("(memo)" if h else "") for m, t, h in times[:8])
            trace(f"PERFTRACE data_call total={total:.0f}ms charts={len(out)}/{len(widgets)}"
                  f" sum={sum(m for m, _, _ in times):.0f}ms computed={sum(1 for _, _, h in times if not h)}"
                  f" | slowest: {top}")
        return out


def preload_for_record():
    """DD_RECORD_PRELOAD: every chart's data read and kept in the background, for the window's next opening."""
    from .ui_share import ui_first

    def run():
        t0 = time.perf_counter()
        deck, span = WebDeepDiveDialog._initial_scope()
        WebDeepDiveDialog._data(providers.default_widgets(), deck, span)
        return 1000 * (time.perf_counter() - t0)

    def done(fut):
        try:
            log_warn(f"record preload: every chart's data read in {fut.result():.0f} ms", tag="WEB")
        except Exception as e:
            log_warn(f"record preload: {e!r}", tag="WEB")

    mw.taskman.run_in_background(lambda: ui_first(run), on_done=done)
