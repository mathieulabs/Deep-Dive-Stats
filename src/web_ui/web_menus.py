# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""The main screen's menus shown by the page (app.js DD.menu) instead of Qt's.

The menus stay built by the native code (context_menu.PinnedContextMenu for the right click, card_chips for the
period label): it fills a menu that is never shown, read here into the page's entries ([key, label, checked,
icon, mode, submenu, disabled], app.js menu). A click in the page comes back as the key: its action is triggered.

The menu is kept (alive, hidden) until the next one: its actions are what the clicks trigger.
"""

from __future__ import annotations

import html
import itertools
import json
import time

from aqt import mw
from aqt.qt import QTimer

from ..details.logic.logger import log_error, log_swallowed, log_warn

_m = {"menu": None, "acts": {}, "wid": None, "at": None, "seq": itertools.count(1), "icons": {}, "picked": 0.0}


# ---- a native menu as the page's entries --------------------------------------------------------------------------
def _icon_url(icon):
    """A QIcon as a PNG data URL (16 px, sharp on a 2x screen), or None."""
    try:
        if icon is None or icon.isNull():
            return None
        key = icon.cacheKey()
        got = _m["icons"].get(key)
        if got is None:
            from .tour import _data_url

            pm = icon.pixmap(32, 32)
            got = _data_url(pm) if not pm.isNull() else ""
            if len(_m["icons"]) > 200:
                _m["icons"].clear()
            _m["icons"][key] = got
        return got or None
    except Exception:
        log_swallowed()
        return None


def _label(text):
    # Qt's mnemonics ("&&" is a "&"), then safe in the page's innerHTML
    t = str(text or "").replace("&&", "\0").replace("&", "").replace("\0", "&")
    return html.escape(t)


def entries(menu):
    """The page's entries of this QMenu (its actions registered under their keys)."""
    from aqt.qt import QPushButton, QWidgetAction

    out = []
    for act in menu.actions():
        try:
            if not act.isVisible():
                continue
            if act.isSeparator():
                out.append("sep")
                continue
            sub = act.menu()
            if sub is not None:
                inner = entries(sub)
                if inner:
                    key = "m%d" % next(_m["seq"])
                    out.append([key, _label(act.text() or sub.title()), None, _icon_url(act.icon()), None, inner, not act.isEnabled()])
                continue
            if isinstance(act, QWidgetAction):
                # context_menu._add_persistent_action: a button in a row, the menu staying open (Position)
                w = act.defaultWidget()
                for btn in (w.findChildren(QPushButton) if w is not None else []):
                    if not btn.isVisibleTo(w) and btn.isHidden():
                        continue
                    key = "b%d" % next(_m["seq"])
                    _m["acts"][key] = btn
                    out.append([key, _label(btn.text()), None, _icon_url(btn.icon()), True, None, not btn.isEnabled()])
                continue
            key = "a%d" % next(_m["seq"])
            _m["acts"][key] = act
            checked = act.isChecked() if act.isCheckable() else None
            mode = None
            if act.isCheckable():
                g = act.actionGroup()
                mode = "radio" if (g is not None and g.isExclusive()) else True  # StyledMenu: stays open
            out.append([key, _label(act.text()), checked, _icon_url(act.icon()), mode, None, not act.isEnabled()])
        except RuntimeError:
            continue
    while out and out[-1] == "sep":
        out.pop()
    return out


def _keep(menu, wid):
    old = _m["menu"]
    if old is not None and old is not menu:
        try:
            old.deleteLater()
        except RuntimeError:
            pass
    _m["menu"], _m["wid"] = menu, wid


def _answer(menu, wid, open_title=None):
    """{items, open}: open, the key of the submenu to show at once (the Position list reopened after a move)."""
    _m["acts"] = {}
    _keep(menu, wid)
    items = entries(menu)
    key = None
    if open_title:
        key = next((it[0] for it in items if isinstance(it, list) and it[5] and html.unescape(it[1]) == open_title), None)
    return {"items": items, "open": key}


# ---- the right-click menu ----------------------------------------------------------------------------------------
def _built(build):
    """The StyledMenu that build() would show (its exec / popup caught), or None."""
    from ..details.ui.shared.menu import StyledMenu

    got = []
    saved = {k: StyledMenu.__dict__.get(k) for k in ("exec", "popup")}

    def catch(self, *_a, **_k):
        got.append(self)
        return None

    StyledMenu.exec = catch
    StyledMenu.popup = catch
    try:
        build()
    finally:
        for k, v in saved.items():
            if v is None:
                try:
                    delattr(StyledMenu, k)
                except AttributeError:
                    pass
            else:
                setattr(StyledMenu, k, v)
    return got[-1] if got else None


# ---- a chart's own options (its header's options icon: pinned.js ownOpt) -------------------------------------------
# PinnedContextMenu.show: after Time Span, the decks and View..., the entries of this chart alone (Legend Layout,
# Show Average, Series, Show as %, Show Trend...), then the ones of every chart or of the main screen; Adaptive
# Binning is this chart's, among those
_GLOBAL = ("Show Bottom Stats (Global)", "Show Stats (Global)", "Axis Animation", "Position", "Remove from main menu",
           "Reset Size")


def own_items(items):
    """The page's entries of the right click that change this chart alone (none when View... is not found)."""
    from ..i18n import tr, tr_name

    names = [None if it == "sep" else html.unescape(str(it[1])) for it in items]
    view = tr("View...")
    if view not in names:
        return []
    stops, keep = {tr_name(t) for t in _GLOBAL}, tr("Adaptive Binning")
    out, on = [], True
    for it, name in list(zip(items, names))[names.index(view) + 1:]:
        if name in stops:
            on = False
        if on or name == keep:
            out.append(it)
    # no separator first, last or twice
    clean = []
    for it in out:
        if it == "sep" and (not clean or clean[-1] == "sep"):
            continue
        clean.append(it)
    while clean and clean[-1] == "sep":
        clean.pop()
    return clean


def context(wid, own=False, count=False):
    """The right-click menu of a pinned widget: {items, open}, or None. own: only this chart's own entries; count:
    their number, {n} (the menu not kept: one shown stays usable)."""
    from aqt.qt import QPoint

    from . import pinned as P

    try:
        from ..details.widgets.pinned.main_menu.manager import MainMenuWidgetManager

        d = P._def_of(wid)
        if d is None:
            return None
        m = MainMenuWidgetManager.instance()
        m._config_manager = m._get_config_manager(force_refresh=True)
        cm = m._context_menu
        _hook_reopen(cm)
        px = P._proxy(d)
        with P._web_menu(m, wid):
            menu = _built(lambda: _ORIG_SHOW["fn"](px, d, QPoint(0, 0), fixed_global_pos=QPoint(0, 0)))
            if menu is None:
                return None
            if count:
                acts = dict(_m["acts"])
                n = sum(1 for it in own_items(entries(menu)) if it != "sep")
                _m["acts"] = acts
                if d.get("own_n") != n:  # kept: the next main screens draw its icon or not from the start
                    try:
                        from ..details.logic.widget_registry import WidgetRegistry

                        WidgetRegistry.update_setting(wid, "own_n", n)
                    except Exception as e:
                        log_warn(f"own options count not kept: {e!r}", tag="WEB")
                try:
                    menu.deleteLater()
                except RuntimeError:
                    pass
                return {"n": n}
            out = _answer(menu, wid)
            if own:
                out["items"] = own_items(out["items"])
            return out
    except Exception as e:
        log_error(f"web pinned menu: {e!r}")
        return None


_ORIG_SHOW = {"fn": None, "cm": None}


def _hook_reopen(cm):
    """PinnedContextMenu.show calls itself again after a move (Position: the menu reopened where it was, its list
    open): here the page shows it again, with the list open (a native menu would come up instead)."""
    if _ORIG_SHOW["cm"] is cm:
        return
    orig = type(cm).show.__get__(cm)
    _ORIG_SHOW["fn"], _ORIG_SHOW["cm"] = orig, cm

    def show(widget, widget_def, pos, *, fixed_global_pos=None, reopen_position_menu=False):
        from . import pinned as P

        wid = (widget_def or {}).get("id") if isinstance(widget_def, dict) else None
        # only the menu reopening itself right after a click of the page's (the tour's pictures call show too)
        if wid is None or wid != _m["wid"] or time.monotonic() - _m["picked"] > 2.0:
            return orig(widget, widget_def, pos, fixed_global_pos=fixed_global_pos,
                        reopen_position_menu=reopen_position_menu)
        _m["picked"] = 0.0
        try:
            from ..details.widgets.pinned.main_menu.manager import MainMenuWidgetManager
            from ..i18n import tr

            m = MainMenuWidgetManager.instance()
            with P._web_menu(m, wid):
                menu = _built(lambda: orig(P._proxy(widget_def), widget_def, pos, fixed_global_pos=fixed_global_pos))
            if menu is None:
                return None
            out = _answer(menu, wid, tr("Position") if reopen_position_menu else None)
            _push("again", out)
        except Exception as e:
            log_error(f"web pinned menu again: {e!r}")
        return None

    cm.show = show


# ---- the period label's list -------------------------------------------------------------------------------------
def span(wid):
    """The period list of a card's label (card_chips.fill_span_menu, then Hide these labels): {items}, or None."""
    from . import pinned as P

    try:
        from ..details.widgets.pinned.main_menu.manager import MainMenuWidgetManager
        from ..details.widgets.pinned.main_menu.ui.card_chips import fill_span_menu, hide_card_labels, themed_menu
        from ..i18n import tr

        d = P._def_of(wid)
        if d is None:
            return None
        m = MainMenuWidgetManager.instance()
        m._config_manager = m._get_config_manager(force_refresh=True)
        px = P._proxy(d)
        menu = themed_menu(px, m)
        fill_span_menu(menu, m, px, d)
        menu.addSeparator()
        hide = menu.addAction(tr("Hide these labels"))
        hide.triggered.connect(lambda _=False: hide_card_labels(m))
        return _answer(menu, wid)
    except Exception as e:
        log_error(f"web pinned span menu: {e!r}")
        return None


# ---- a click in the page -----------------------------------------------------------------------------------------
def pick(key, on=None):
    """The entry clicked: its action triggered (an entry that keeps the menu open, now; else once the page's call
    has its answer, a window it opens being modal). The main screen rebuilt if the settings changed."""
    from aqt.qt import QPushButton

    from . import pinned as P

    act = _m["acts"].get(str(key))
    if act is None:
        return False
    stays = isinstance(act, QPushButton)
    try:
        stays = stays or act.isCheckable()
    except RuntimeError:
        return False
    seen = {"c": P._config_snapshot()}
    wid = _m["wid"]
    _m["picked"] = time.monotonic()

    def run():
        try:
            from ..details.widgets.pinned.main_menu.manager import MainMenuWidgetManager

            with P._web_menu(MainMenuWidgetManager.instance(), wid):
                if isinstance(act, QPushButton):
                    act.click()
                else:
                    if act.isCheckable() and on is not None and act.isChecked() == bool(on):
                        act.setChecked(not bool(on))  # (the page ticked it already: the action ticks it itself)
                    act.trigger()
        except RuntimeError:
            return
        except Exception as e:
            log_error(f"web pinned menu pick: {e!r}")
        if not stays:
            P.preview_styles()  # a settings window opened from the menu and cancelled: the saved looks again
        _check(seen)

    if stays:
        run()
    else:
        QTimer.singleShot(0, run)
    return True


def _check(seen):
    from . import pinned as P

    def check():
        if P._state.get("listening"):
            return  # the config listener rebuilds the block (refresh_block)
        now = P._config_snapshot()
        if now != seen["c"]:
            seen["c"] = now
            P.refresh_block()

    check()
    for ms in (400, 1500):
        QTimer.singleShot(ms, check)


def _push(what, payload):
    try:
        web = mw.web
        web.eval("window.DDP && DDP.menuAgain && DDP.menuAgain(%s)" % json.dumps(payload).replace("</", "<\\/"))
    except Exception:
        log_swallowed()
