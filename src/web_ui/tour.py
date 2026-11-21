# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""The guided tour of the pinned widgets, on the web block (pinned.js draws it: DDP.tour).

The steps, texts and demo scenes come from details/widgets/common/guided_tour.py, which also does the work on
the settings: a demo scene is the user's settings file with another layout, theme or text, and the file goes back
byte for byte when the demo steps are left or the tour ends. The block is built again in place for each scene
(pinned.refresh_block).

It starts by itself once, the first time the block shows on the deck list, and again from the menu."""

import time

from aqt import mw
from aqt.qt import QTimer

from ..details.logic.logger import log_swallowed
from ..details.widgets.common import guided_tour as gt

def _timed(name):
    """A dev trace of how long a tour call held Anki's main thread (the page waits, and its frames with it)."""
    import functools
    import time

    def wrap(fn):
        @functools.wraps(fn)
        def run(*a, **k):
            t0 = time.perf_counter()
            try:
                return fn(*a, **k)
            finally:
                from .trace import trace

                trace(f"TOUR py {name} {1000 * (time.perf_counter() - t0):.0f} ms")
        return run
    return wrap


_state = {"running": False, "scheduled": False, "tries": 0, "patched": False}


def payload():
    from ..i18n import tr

    touch = gt._touch_texts()
    steps = []
    for scene, target, text, action in gt._steps():
        steps.append({"scene": scene, "target": target, "text": text, "action": action,
                      "touch_text": touch.get(action), "cycle": gt._cycle_scenes(action)})
    return {"steps": steps, "labels": {"title": tr("Quick tour"), "next": tr("Next"), "done": tr("Done"),
                                       "back": tr("Back"), "skip": tr("Skip"),
                                       "newline": tr("New line"), "movehere": tr("Move here")}}


def _refresh():
    """A scene written by the Qt tour's code: the web block shows it (its own refresh rebuilt the Qt overlay).
    After the answer to the page: the block built again has a new token, an answer sent after it was dropped
    (the tour waited for it forever)."""
    from . import pinned

    QTimer.singleShot(0, pinned.refresh_block)


def _patch():
    if _state["patched"]:
        return
    _state["patched"] = True
    native, native_span = gt._refresh_pinned, gt._refresh_pinned_span

    def refresh():
        from . import pinned

        (_refresh if pinned.enabled() else native)()

    def refresh_span():
        from . import pinned

        (_refresh if pinned.enabled() else native_span)()

    gt._refresh_pinned, gt._refresh_pinned_span = refresh, refresh_span


def install():
    _patch()
    gt.restore_after_crash()
    from aqt import gui_hooks

    gui_hooks.state_did_change.append(lambda new_state, _old: new_state == "deckBrowser" or stop())


def stop():
    """The tour ends when its screen is left (the Deep Dive window opened over it, a deck or a review opened): it ran
    on behind, with its hidden gallery and settings pages and its animations - on a phone, the Deep Dive window on top
    of it took the app over the 1024 open files Anki's media server can take (it stops, the pages lose their files)."""
    if not _state["running"]:
        return
    from . import pinned

    try:
        pinned.eval_block("DDP.tourClose && DDP.tourClose()")
    except Exception:
        log_swallowed()
    h_end()  # at once, the page gone or not (its own tour_end, if it answers, finds it ended)


def running():
    return _state["running"]


def start(force=False):
    """The tour on the deck list (force: from the menu, even if it was seen)."""
    from . import pinned

    if force:
        _state["running"] = False  # from the menu: a tour left half way (its page gone) starts over
    if _state["running"] or (not force and gt._is_done()):
        return False
    if getattr(mw, "state", None) != "deckBrowser":
        mw.moveToState("deckBrowser")
        QTimer.singleShot(1200, lambda: start(force))
        return True
    try:
        gt._refresh_layout_scenes()
        _state["running"] = True
        gt._mark_done()
        gt._pause_warmup(True)
        _watch_windows(True)
        prewarm()
        pinned.eval_block("DDP.tour && DDP.tour(%s)" % pinned.json_for_page(payload()))
        return True
    except Exception:
        _state["running"] = False
        log_swallowed()
        return False


def maybe_first_start():
    """The block is on the deck list: the first time, the tour comes once the screen has settled (and the history
    cache is built: its work in the background makes the animations stutter)."""
    if _state["scheduled"] or _state["running"] or gt._is_done():
        return
    _state["scheduled"] = True

    def attempt():
        _state["scheduled"] = False
        if _state["running"] or gt._is_done():
            return
        ready = (getattr(mw, "state", None) == "deckBrowser" and mw.isActiveWindow() and not gt._cache_busy())
        if ready:
            start()
            return
        _state["tries"] += 1
        if _state["tries"] < gt._MAX_TRIES:
            _state["scheduled"] = True
            QTimer.singleShot(gt._RETRY_MS, attempt)

    QTimer.singleShot(gt._FIRST_DELAY_MS, attempt)


# ---- page -> Python ----------------------------------------------------------------------------
@_timed("scene")
def h_scene(name=None, _wid=None):
    """A demo scene of the step shown (None: the user's own settings)."""
    import time

    from . import pinned

    pinned._state["quiet"] = time.monotonic() + 0.4  # the settings file written: the tour's own refresh builds it once
    return bool(gt._apply_scene(name))


def h_end(_wid=None):
    _state["running"] = False
    _watch_windows(False)
    _drop_gallery()
    _drop_settings()
    gt._pause_warmup(False)
    gt._end_demo()
    return True


# ---- pictures of the menus (web_menus' entries drawn as a Qt menu, never shown), as the Qt tour shows them ----
def _data_url(pm):
    from aqt.qt import QBuffer, QByteArray, QIODevice

    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    pm.save(buf, "PNG")
    return "data:image/png;base64," + bytes(ba.toBase64()).decode("ascii")


def _pictures(menu, act):
    """{plain, lit, w, h, entry}: the menu as it opens, then with act under the mouse (CSS pixels)."""
    _offscreen(menu)
    menu.ensurePolished()
    menu.adjustSize()
    plain = menu.grab()
    lit, entry = plain, None
    if act is not None:
        menu.setActiveAction(act)
        lit = menu.grab()
        g = menu.actionGeometry(act)
        entry = [g.x(), g.y(), g.width(), g.height()]
    dpr = max(1.0, plain.devicePixelRatio())
    out = {"plain": _data_url(plain), "lit": _data_url(lit), "w": plain.width() / dpr, "h": plain.height() / dpr,
           "entry": entry}
    menu.deleteLater()
    return out


# the page's icon names (app.js ICONS) as the Qt icons of the pictures
_QT_ICONS = {"external": "external-link", "maximize": "maximize", "plus": "plus", "gear": "settings",
             "filetext": "file-text", "help": "help-circle", "calendar": "calendar", "zoom": "zoom-in",
             "layers": "layers", "eye": "eye", "trash": "trash-2", "copy": "copy"}


def _qmenu(items, menu=None):
    """A Qt menu of the page's entries (web_menus), for its picture: in the pinned widgets' theme. The entries'
    keys are in the actions' data."""
    import html

    from ..details.ui import StyledMenu, get_svg_icon
    from ..details.widgets.pinned.main_menu.manager import MainMenuWidgetManager

    top = menu is None
    if top:
        menu = StyledMenu(None)
        menu.setProperty("deepdivestats_theme_context", "pinned")
        menu.setProperty("deepdivestats_ignore_forced_dark_theme", True)
        try:
            m = MainMenuWidgetManager.instance()
            menu.setProperty("deepdivestats_config_override", dict(m._get_config_manager().config or {}))
            menu._apply_theme_style()
        except Exception:
            log_swallowed()
    for it in items:
        if it == "sep":
            menu.addSeparator()
            continue
        key, label, checked, icon, _mode, sub, disabled = it
        label = html.unescape(label).replace("&", "&&")
        if sub is not None:
            act = menu.addMenu(label).menuAction()
            _qmenu(sub, act.menu())
        else:
            act = menu.addAction(label)
            if checked is not None:
                act.setCheckable(True)
                act.setChecked(bool(checked))
        if icon in _QT_ICONS:
            act.setIcon(get_svg_icon(_QT_ICONS[icon], size=16, context_ref=menu))
        act.setData(key)
        act.setEnabled(not disabled)
    return menu


def _menu_of(id, names):
    """The widget's right-click menu, with the first entry named in names lit."""
    from . import pinned, web_menus

    d = pinned._def_of(id)
    if d is None:
        return None
    items = web_menus._clean(web_menus.context_menu(d).items)
    menu = _qmenu(items)
    act = next((a for a in menu.actions() if a.text().replace("&&", "&") in names), None)
    return _pictures(menu, act)


@_timed("menu pictures")
def h_menu(id=None, _wid=None):
    """The widget's right-click menu, with its Settings entry lit, and the size of its settings window's picture
    (guided_tour._menu_widget), taken meanwhile (h_settings)."""
    from ..i18n import tr

    out = _menu_of(id, {tr("Settings"), tr("Edit Text and Settings...")})
    if out is not None:
        out["settings"] = _settings_picture(id)
    return out


# ---- the settings window's picture (guided_tour._settings_picture): its web page (widget_settings.WebWidgetSettings)
# built off screen, never shown, its picture taken once the page is drawn
_SET_SIZE = (560, 620)
_set = {"page": None, "id": None, "shot": None, "gen": 0}


def _settings_picture(id):
    """Starts the picture of the widget's settings window; {w, h}: the size it will have (the step places it
    ahead), None when there is none (a type the option schema does not draw)."""
    _drop_settings()
    try:
        from ..config import addon_config, set_live_config_override
        from ..details.logic.widget_registry import WidgetRegistry
        from .widget_settings import WebWidgetSettings, _open

        wdef = next((d for d in WidgetRegistry.get_all() if d.get("id") == id), None)
        if wdef is None:
            return None
        ses = _open(dict(wdef), None, global_config=addon_config().config)
        set_live_config_override(None)  # only read: the charts keep reading the saved config
        if ses is None:
            return None
        page = WebWidgetSettings(ses.state, schema=ses.schema)
    except Exception:
        log_swallowed()
        return None
    _offscreen(page)
    page.resize(*_SET_SIZE)
    page.show()
    _set["gen"] += 1
    _set.update(page=page, id=id, shot=None)
    _settings_shot(page, _set["gen"], time.monotonic() + 10)
    return {"w": _SET_SIZE[0], "h": _SET_SIZE[1]}


def _settings_shot(page, gen, deadline):
    """The page's picture once it has drawn its options (asked again every 120 ms until then, or the deadline)."""
    from .trace import trace

    def gone():
        return _set["page"] is not page or _set["gen"] != gen

    def check():
        if not gone():
            try:
                page.webview.evalWithCallback("!!document.querySelector('.dws-app')", got)
            except RuntimeError:
                pass

    def got(ok):
        if gone():
            return
        if not ok:
            if time.monotonic() > deadline:
                trace("TOUR py settings: page not drawn in time")
                return _drop_settings(keep_shot=True)
            QTimer.singleShot(120, check)
            return
        QTimer.singleShot(250, take)  # its fonts and a frame or two to reach the hidden view

    def take():
        if gone():
            return
        try:
            pm = page.webview.grab()
            if not pm.isNull():
                dpr = max(1.0, pm.devicePixelRatio())
                _set["shot"] = {"pic": _data_url(pm), "w": pm.width() / dpr, "h": pm.height() / dpr}
                trace("TOUR py settings: picture taken")
        except RuntimeError:
            return
        except Exception:
            log_swallowed()
        _drop_settings(keep_shot=True)

    check()


def _drop_settings(keep_shot=False):
    """The hidden settings page goes (never closed through Cancel: nothing to restore, nothing saved)."""
    page, _set["page"] = _set["page"], None
    if not keep_shot:
        _set["shot"] = None
        _set["id"] = None
    if page is not None:
        try:
            page.deleteLater()
        except RuntimeError:
            pass


def h_settings(id=None, _wid=None):
    """The settings window's picture {pic, w, h} started by h_menu; None while it is not taken yet."""
    return _set["shot"] if _set["id"] == id else None


# ---- the add step (guided_tour._add_frames_for): the right-click menu to Add Widget... and the gallery for a
# chart, the "+" at the end of the stat line and the gallery for a stat card, each followed by the widget added
_add = {"gallery": None, "shots": {}, "gen": 0}


@_timed("add (menu picture, gallery)")
def h_add(chart=None, stat=None, _wid=None):
    """The pins the step shows (after chart / at the end of the stat line, stat: the id of its last card), the
    chart's menu with Add Widget... lit, and the gallery's size (filled with its previews meanwhile)."""
    from ..details.widgets.pinned.main_menu.ui.add_widget_menu import CHARTS, default_span
    from ..details.logic.stat_cards import get_stat_card_name
    from ..i18n import tr

    chart_type, stat_key = gt._add_choices()
    gt._add_demo_pins.clear()
    out = {"chart": None, "stat": False}
    if chart_type is not None and chart:
        pin = {"id": "tour-add-chart", "type": chart_type, "label": dict(CHARTS)[chart_type], "stat_key": None}
        if default_span(chart_type) is not None:
            pin["time_span"] = default_span(chart_type)
        menu = _menu_of(chart, {tr("Add Widget...")})
        if menu is not None and menu.get("entry"):
            gt._add_demo_pins["chart"] = dict(pin, _after=chart)
            out["chart"] = menu
    if stat_key is not None and stat:
        pin = {"id": "tour-add-stat", "type": "stat_card", "label": get_stat_card_name(stat_key), "stat_key": stat_key}
        if default_span("stat_card", stat_key) is not None:
            pin["time_span"] = default_span("stat_card", stat_key)
        gt._add_demo_pins["stat"] = dict(pin, _after=stat)
        out["stat"] = True
    g = _gallery()
    if g is None:
        return None
    out["gallery"] = [g.width(), g.height()]
    # its pictures for these pins, taken from now on (the ones of other pins dropped)
    _add["gen"] += 1
    _add["shots"] = {}
    _shots(g, [w for w in ("chart", "stat") if w in gt._add_demo_pins], time.monotonic() + 12, _add["gen"])
    return out


def _gallery():
    """The widget gallery of the add step: the web gallery (gallery_web.WebGallery), built once, never on screen.
    Its pictures for the demo pins are taken as soon as its page is up (_shots), so h_gallery answers at once."""
    g = _add["gallery"]
    if g is not None:
        return g
    try:
        from ..details.widgets.pinned.main_menu.manager import MainMenuWidgetManager
        from .gallery_model import GalleryModel
        from .gallery_web import WebGallery

        g = WebGallery(GalleryModel(MainMenuWidgetManager.instance(), where="after", context="pinned"), mw)
        _offscreen(g)
        g.show()
        _add["gallery"] = g
        _add["shots"] = {}
        from .trace import trace

        trace(f"TOUR py web gallery built: geometry={g.geometry().getRect()}")
        return g
    except Exception:
        log_swallowed()
        return None


def _shots(g, todo, deadline, gen):
    """The gallery's picture for each of todo ("chart", "stat"): the demo pin's tile lit as under the mouse, in view,
    its preview drawn, the line under the title saying where it goes (guided_tour._gallery_frame). One at a time:
    the page is asked again every 120 ms until the tile is ready (or the deadline passes: no picture)."""
    import json

    from .trace import trace

    def gone():
        return _add["gallery"] is not g or _add["gen"] != gen

    if gone():
        return
    if not todo:
        try:
            g.webview.eval("DD.galleryTour && DD.galleryTour(null)")
        except RuntimeError:
            pass
        return
    which, pin = todo[0], gt._add_demo_pins.get(todo[0])
    tid = None
    if pin is not None:
        tid = next((t.id for t in g.model.tiles.values()
                    if t.choice.widget_type == pin["type"] and t.choice.stat_key == pin.get("stat_key")), None)
    if tid is None:
        trace(f"TOUR py gallery {which}: no tile")
        return _shots(g, todo[1:], deadline, gen)
    g.model.where = "after" if which == "chart" else "end"
    js = "DD.galleryTour ? DD.galleryTour(%s, %s) : null" % (json.dumps(tid), json.dumps(g.model.where_text()))

    def again():
        if not gone():
            try:
                g.webview.evalWithCallback(js, got)
            except RuntimeError:
                pass

    def got(r):
        if gone():
            return
        if isinstance(r, dict) and r.get("missing"):
            trace(f"TOUR py gallery {which}: tile {tid} not on the page")
            return _shots(g, todo[1:], deadline, gen)
        if not (isinstance(r, dict) and r.get("ready")):
            if time.monotonic() > deadline:
                trace(f"TOUR py gallery {which}: not ready in time")
                return _shots(g, todo[1:], deadline, gen)
            QTimer.singleShot(120, again)
            return
        # its preview fading in, then a frame or two for it to reach the hidden view
        QTimer.singleShot(int(r.get("fade") or 0) + 90, lambda: None if gone() else g.webview.evalWithCallback(js, take))

    def take(r):
        if gone():
            return
        try:
            pm = g.webview.grab()
            if isinstance(r, dict) and not pm.isNull():
                _add["shots"][which] = {"pic": _data_url(pm),
                                        "w": int(r.get("vw") or g.webview.width()),
                                        "h": int(r.get("vh") or g.webview.height()),
                                        "x": int(r.get("x") or 0), "y": int(r.get("y") or 0)}
                trace(f"TOUR py gallery {which}: picture taken")
        except RuntimeError:
            return
        except Exception:
            log_swallowed()
        _shots(g, todo[1:], deadline, gen)

    again()


_watch = {"filter": None}


def _watch_windows(on):
    """Dev: every window Anki shows while the tour runs, in debug.log (what it is, where, and the code that showed it)
    - something flashing on screen for an instant."""
    from ..config import is_dev_build

    if not is_dev_build():
        return
    from aqt.qt import QApplication, QEvent, QObject

    app = QApplication.instance()
    if not on:
        f, _watch["filter"] = _watch["filter"], None
        if f is not None:
            app.removeEventFilter(f)
        return
    if _watch["filter"] is not None:
        return

    class _Watch(QObject):
        def eventFilter(self, obj, ev):
            try:
                if ev.type() in (QEvent.Type.Show, QEvent.Type.WinIdChange) and obj.isWidgetType() and obj.isWindow():
                    import traceback

                    from aqt.qt import Qt

                    from .trace import trace

                    where = " < ".join(f"{fr.name}:{fr.lineno}" for fr in traceback.extract_stack()[-9:-1][::-1])
                    trace(f"TOUR py window {'shown' if ev.type() == QEvent.Type.Show else 'made native'}: "
                          f"{type(obj).__name__} '{obj.objectName()}' geo={obj.geometry().getRect()} "
                          f"offscreen={obj.testAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)} "
                          f"opacity={obj.windowOpacity():.1f} from {where}")
            except Exception:
                pass
            return False

    _watch["filter"] = _Watch(app)
    app.installEventFilter(_watch["filter"])


def _offscreen(w):
    """A window built only for its picture: never on screen (Windows showed a frame of it for an instant, at the top
    left, when it was made a window): not shown, fully transparent, far off any screen."""
    from aqt.qt import Qt

    w.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    try:
        w.setWindowOpacity(0.0)
    except Exception:
        pass
    w.move(-30000, -30000)


def _drop_gallery():
    g, _add["gallery"] = _add["gallery"], None
    _add["shots"] = {}
    if g is not None:
        try:
            g.done(0)
            g.deleteLater()
        except RuntimeError:
            pass


@_timed("gallery picture")
def h_gallery(which=None, _wid=None):
    """The gallery on the tab of the widget added, its tile under the mouse (guided_tour._gallery_frame):
    {pic, w, h, x, y} with the tile's center in the gallery, taken ahead (_shots); None while it is not."""
    if _add["gallery"] is None or gt._add_demo_pins.get(which) is None:
        return None
    shot = _add["shots"].get(which)
    if shot is None:
        from .trace import trace

        trace(f"TOUR py gallery {which}: asked before its picture was ready")
    return shot


@_timed("span pictures")
def h_span(id=None, _wid=None):
    """The period list of the chart's label, for each period the step goes through (past month, year, all, when
    the list has them and the chart does not show it now): [{value, plain, lit, w, h, entry}]."""
    from . import pinned, web_menus

    d = pinned._def_of(id)
    if d is None:
        return []
    gt._span_id[:] = [id]  # the chart the "span:" scenes change
    items = web_menus._clean(web_menus.span_menu(d).items)

    def value(it):  # a period's key: "s:<value>:<days>" (web_menus._fill_spans)
        k = it[0] if isinstance(it, list) else ""
        return int(k.split(":")[1]) if k.startswith("s:") else None

    values = [value(it) for it in items if value(it) is not None]
    current = d.get("time_span")
    out = []
    for v in [v for v in (2, 3, -1, 8, 0) if v in values and v != current][:3]:
        menu = _qmenu(items)
        act = next((a for a in menu.actions() if isinstance(a.data(), str) and a.data().startswith("s:%d:" % v)), None)
        out.append(dict(_pictures(menu, act), value=v, badge=_span_badge(v)))
    return out


def _span_badge(v):
    """guided_tour._show_span_badge: the period the chart now shows, in a tag on it."""
    try:
        from ..const import Period
        from ..i18n import tr, tr_name

        return tr("Time span: {span}", span=tr_name(Period.LABEL.get(v, "")))
    except Exception:
        log_swallowed()
        return ""


def h_drag(swap=None, move=None, end=None, box=None, _wid=None):
    """What the drag step's next scene shows (guided_tour._drag_demo_*): the two charts swapped, the chart moved to
    a new box (end: "top" or "bottom"), the whole box moved ([key, "top" | "bottom"])."""
    if swap is not None:
        gt._drag_demo_swap[:] = list(swap)
    if move is not None:
        gt._drag_demo_id[:] = [move]
    if end is not None:
        gt._drag_demo_end[0] = end
    if box is not None:
        gt._drag_demo_box[:] = list(box)
    return True


def prewarm():
    """The data of the demo layouts read in the background while the first step is read: the first showing of a
    layout no longer waits for its charts' history to be sliced."""
    from . import pinned, providers

    def work():
        try:
            base = dict(pinned._conf())
            for name in list(gt._LAYOUT_SCENES):
                cfg = gt._scene_config(name, base)
                for d in cfg.get("Pinned_Widgets") or []:
                    t = d.get("type")
                    if t in (None, "stat_card", "text_label"):
                        continue
                    span = -1 if t == "heatmap" else int(d.get("time_span", -1))
                    providers.fetch(t, pinned._deck_of(d, None), span, providers.widget_options(t, own=d, conf=cfg))
        except Exception:
            log_swallowed()

    mw.taskman.run_in_background(work)
