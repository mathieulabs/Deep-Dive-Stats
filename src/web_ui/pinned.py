# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Pinned widgets drawn by a web block inside Anki's own pages (deck list, deck overview, Congratulations).

The page draws them itself, with the same chart modules as the Deep Dive window.

Page -> Python: the same "dd:{id, cmd, args}" messages as the window (bridge.py), received through
webview_did_receive_js_message for the deck list and the overview, answered by DDP.__resolve with the
page's token (a page rebuilt by Anki never gets the answers meant for the one before).
"""

import json
import os
import re
import time
import uuid

from aqt import gui_hooks, mw

from ..details.logic.logger import log_error, log_warn
from . import providers
from .theme import build_theme
from .trace import dev_flag, is_dev, page_log, trace

_WEB_DIR = "src/web_ui/web"
_JS = ["dd-core.js", "stats.js", "charts/activity.js", "charts/dots.js", "charts/hover.js", "charts/zoom_camera.js", "charts/discrete.js",
       "charts/hourly.js", "charts/buttons.js", "charts/pie.js", "charts/retention.js", "charts/heatmap.js",
       "charts/extras.js", "charts/curves.js", "app.js", "pinned.js"]
_state = {"installed": False, "css": None, "css_mtime": None}
# What each widget showed last (its data, its stat cards, its text): a page Anki rebuilds (another deck, a refresh)
# starts from it at once, then glides to the new data.
_PREV = {}
# The value each stat card showed last, wherever it was: the deck list and a deck often show other sets of cards, and
# the cards they share roll from the value seen on the screen before (pinned.js statsBox)
_LAST_STAT = {}
_COLLAPSED_PINNED = set()
# The block's intro (fade in, charts' opening animations) is for its first time on screen since Anki started. Anki
# often builds the deck list again right after starting (profile loaded, sync done): that page plays the intro too
# until the page says it played (intro_done), else its charts came from their last picture, drawn still.
_INTRO = {"done": False, "since": None, "skel": False}  # skel: the block shown as its skeleton (charts held)
_INTRO_MAX_S = 5.0  # never longer (a page that did not report): returns to the main screen stay instant
# Anki's sync on opening ends with the deck list built again (~0.7 s after sync_did_finish): the first page holds
# its intro (stays hidden) while it runs, so the intro plays once, on the page built after it (intro_hold)
_SYNC = {"running": False, "ended": None}
_SYNC_TAIL_S = 1.5
_KEEP = ("t", "s", "n")  # kept on disk: texts, stat cards and natural heights (small), so Anki's first page lays
                         # the block out as it was (else the line of text started 200 px tall and the charts moved up)


def _prev_path():
    return os.path.join(_addon_dir(), "user_files", "web_pinned_prev.json")


def _load_prev():
    try:
        with open(_prev_path(), "r", encoding="utf-8") as f:
            raw = json.load(f)
        for k, v in (raw or {}).items():
            kind, _, key = k.partition("|")
            if kind in _KEEP and (kind, key) not in _PREV:
                _PREV[(kind, key)] = v
    except FileNotFoundError:
        pass
    except Exception as e:
        log_warn(f"web pinned prev load: {e!r}", tag="WEB")


def _save_prev_soon():
    t = _state.get("prev_timer")
    if t is None:
        from aqt.qt import QTimer

        t = _state["prev_timer"] = QTimer(mw)
        t.setSingleShot(True)
        t.timeout.connect(_save_prev)
    t.start(1500)


def _save_prev():
    try:
        out = {f"{k[0]}|{k[1]}": v for k, v in list(_PREV.items()) if k[0] in _KEEP}
        os.makedirs(os.path.dirname(_prev_path()), exist_ok=True)
        tmp = _prev_path() + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False)
        os.replace(tmp, _prev_path())
    except Exception as e:
        log_warn(f"web pinned prev save: {e!r}", tag="WEB")


def _addon_dir():
    from ..const.addon_dir import ADDON_DIR

    return ADDON_DIR


def enabled():
    """The web block draws the pinned widgets (not when Settings > Pinned Widgets > "Disable Pinned Widgets" is on)."""
    from ..config import pinned_widgets_disabled

    return not pinned_widgets_disabled()


def _redraw():
    try:
        if getattr(mw, "col", None) is None:
            return
        if mw.state == "deckBrowser":
            mw.deckBrowser.refresh()
        elif mw.state == "overview":
            mw.overview.refresh()
    except Exception as e:
        log_error(f"web pinned redraw: {e!r}")


def _page():
    """(deck, is the deck list) of the page shown, or None on another screen."""
    try:
        if mw.state == "deckBrowser":
            return None, True
        if mw.state == "overview":
            return int(mw.col.decks.selected()), False
    except Exception:
        pass
    return "none", None


def json_for_page(value):
    return json.dumps(value).replace("</", "<\\/")


def eval_block(js):
    """Run js in the page that shows the block (deck list or overview)."""
    deck, browser = _page()
    if browser is None:
        return
    (mw.deckBrowser.web if browser else mw.overview.web).eval(js)


def refresh_block():
    """The settings changed (a menu, a dialog, a drop on the page...): the block is built again in place, from what
    each widget shows now, without reloading Anki's page."""
    deck, browser = _page()
    if browser is None or not enabled():
        return
    _state.pop("pv", None)
    try:
        boot = _boot(deck, browser, uuid.uuid4().hex[:12])
        if not boot["widgets"]:
            _redraw()  # the last widget gone: the page again (the "Add a widget" card, or nothing)
            return
        web = mw.deckBrowser.web if browser else mw.overview.web
        # a page without the block (the "Add a widget" card, nothing pinned): built again with it
        web.eval("if (window.DDP && document.getElementById('ddp-root')) DDP.reboot(%s); else pycmd('ddp_empty:redraw');"
                 % json.dumps(boot).replace("</", "<\\/"))
    except Exception as e:
        log_error(f"web pinned refresh: {e!r}")


def _on_config_saved(_saved=None):
    if not enabled() or _state.get("refresh_pending"):
        return
    if time.monotonic() < _state.get("quiet", 0):
        return
    _state["refresh_pending"] = True

    def go():
        _state["refresh_pending"] = False
        refresh_block()

    try:
        import threading

        from aqt.qt import QTimer

        if threading.current_thread() is threading.main_thread():
            QTimer.singleShot(0, go)  # coalesce synchronous writes in the same tick with 0ms delay
        else:
            mw.taskman.run_on_main(lambda: QTimer.singleShot(0, go))
    except Exception:
        _state["refresh_pending"] = False


def install():
    if _state["installed"]:
        return
    try:
        from .. import config as _config_mod

        listeners = getattr(_config_mod, "SAVE_LISTENERS", None)
        if listeners is not None and _on_config_saved not in listeners:
            listeners.append(_on_config_saved)
        _state["listening"] = listeners is not None
    except Exception as e:
        log_warn(f"web pinned config listener: {e!r}", tag="WEB")
    try:
        mw.addonManager.setWebExports(__name__, _WEB_DIR + "/.*")
    except Exception as e:
        log_error(f"web pinned exports: {e!r}")
    _patch_update_styles()
    _load_prev()
    try:
        from . import tour

        tour.install()
    except Exception as e:
        log_warn(f"web pinned tour: {e!r}", tag="WEB")
    gui_hooks.deck_browser_will_render_content.append(_on_browser)
    gui_hooks.overview_will_render_content.append(_on_overview)
    gui_hooks.webview_did_receive_js_message.append(_on_message)
    gui_hooks.webview_did_inject_style_into_page.append(_on_congrats)
    if hasattr(gui_hooks, "theme_did_change"):
        gui_hooks.theme_did_change.append(lambda: enabled() and refresh_block())
    if hasattr(gui_hooks, "sync_will_start") and hasattr(gui_hooks, "sync_did_finish"):
        gui_hooks.sync_will_start.append(_on_sync_start)
        gui_hooks.sync_did_finish.append(_on_sync_end)
    _state["installed"] = True


def _on_sync_start():
    _SYNC["running"] = True


def _on_sync_end():
    _SYNC["running"] = False
    _SYNC["ended"] = time.monotonic()


def _scoped(line):
    """A rule of dd.css for every element of its page (buttons, inputs, scrollbars, *): kept to the block. In Anki's
    page it reset Anki's own buttons (Study Now lost its padding and border)."""
    m = re.match(r"^([^{]+)\{", line)
    if not m:
        return line
    sel = m.group(1)
    parts = [p.strip() for p in sel.split(",")]
    def bare(p):
        q = re.sub(r"^:root:root\s+", "", p)
        return q == "*" or bool(re.match(r"^(button|input|select)\b", q)) or q.startswith("::-webkit")
    if not any(bare(p) for p in parts):
        return line
    out = []
    for p in parts:
        if not bare(p):
            out.append(p)
            continue
        root = ":root:root " if p.startswith(":root:root") else ""
        q = re.sub(r"^:root:root\s+", "", p)
        out.append(root + ":where(#ddp-root) " + q)  # :where(): the rule keeps its own weight (the block's classes still win)
        if q == "*":
            out.append(":where(#ddp-root)")
    return ",".join(out) + line[len(sel):]


def _css():
    """dd.css without its rules for the whole page (html / body): the block lives in Anki's page."""
    if _state["css"] is not None and not is_dev():
        return _state["css"]  # a release's files do not change while Anki runs
    path = os.path.join(_addon_dir(), _WEB_DIR, "dd.css")
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        mtime = None
    if _state["css"] is None or _state["css_mtime"] != mtime:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.read().split("\n")
        keep = [_scoped(ln) for ln in lines if not re.match(r"^(html\s*,\s*body|body|html)\s*\{", ln)]
        _state["css"], _state["css_mtime"] = "\n".join(keep), mtime
    return _state["css"]


def _js():
    """The scripts in one inline block (read again only when a file changed): no file fetched while the page
    loads, and the same text each time, which the browser compiles once (its in-memory code cache)."""
    if _state.get("js") is not None and not is_dev():
        return _state["js"]
    base = os.path.join(_addon_dir(), _WEB_DIR)
    stamp = []
    for n in _JS:
        try:
            stamp.append(os.path.getmtime(os.path.join(base, n)))
        except OSError:
            stamp.append(0)
    if _state.get("js") is None or _state.get("js_stamp") != stamp:
        parts = []
        for n in _JS:
            with open(os.path.join(base, n), "r", encoding="utf-8") as f:
                parts.append(f.read())
        _state["js"] = "\n;\n".join(parts).replace("</script", "<\\/script")
        _state["js_stamp"] = stamp
    return _state["js"]


def _conf():
    return providers._cfg().config


def _defs(deck_id, is_browser):
    from ..details.widgets.pinned.main_menu.ui.widget_defs import normalized_widget_def, widget_allowed_in_context
    from ..details.logic.widget_registry import WidgetRegistry

    out = []
    for d in WidgetRegistry.get_all() or []:
        if not isinstance(d, dict) or not d.get("id"):
            continue
        if not widget_allowed_in_context(d, deck_id, is_browser):
            continue
        out.append(normalized_widget_def(d))
    return out


def _block_order(defs):
    from ..const.config import Config
    from ..details.logic.pinned_layout import normalize_block_order

    stat_boxes, chart_boxes, text_boxes = [], [], []
    for d in defs:
        t = d.get("type")
        if t == "stat_card":
            stat_boxes.append(int(d.get("stat_box", 0) or 0))
        elif t == "text_label":
            text_boxes.append(int(d.get("text_box", d.get("chart_box", 0)) or 0))
        else:
            chart_boxes.append(int(d.get("chart_box", 0) or 0))
    return normalize_block_order(_conf().get(Config.PINNED_BLOCK_ORDER), stat_boxes or [0], chart_boxes or [0], text_boxes)


def _collapsed_ids():
    return sorted(str(i) for i in _COLLAPSED_PINNED)


_BOX_MIGRATED = "Web_Box_Opacity_Migrated"


def _migrate_box_opacity():
    """Once: the boxes' background slider is now the box's real opacity (theme.pinned_box). On a dark theme a saved
    value already gave about that opacity (box_glass_k walks the old curve evenly); on a light theme the old
    box never went under 80 %: a saved value is moved to the opacity it showed, so the boxes look as before."""
    from ..const.config import Config
    from ..const.glass_scale import box_glass_k

    cfg = providers._cfg()
    conf = cfg.config
    if conf.get(_BOX_MIGRATED):
        return
    moved, vals = [], {}
    try:
        from ..details.widgets.pinned.widget_factory.utils import _theme_vars

        light = not _theme_vars("pinned")["is_dark"]
    except Exception:
        light = False
    if light:
        for key in (Config.PINNED_GLASS_INTENSITY, Config.TEXT_WIDGET_GLASS_INTENSITY, Config.HEATMAP_GLASS_INTENSITY):
            v = conf.get(key)
            if v is None or v == Config.DEFAULT_CONFIG.get(key):
                continue  # the new default (a profile made by this version): already an opacity
            try:
                vals[key] = conf[key] = int(round(100 * min(1.0, 0.8 + box_glass_k(v))))
                moved.append(f"{key} {v} -> {conf[key]}")
            except (TypeError, ValueError):
                pass
        # the widgets with their own style (their Settings' "own" box: the same keys on their entry)
        try:
            from ..details.logic.widget_registry import WidgetRegistry

            ups = {}
            for d in WidgetRegistry.get_all() or []:
                if not isinstance(d, dict) or not d.get("id") or not d.get("use_custom_style"):
                    continue
                u = {}
                for key in (Config.PINNED_GLASS_INTENSITY, Config.TEXT_WIDGET_GLASS_INTENSITY, Config.HEATMAP_GLASS_INTENSITY):
                    v = d.get(key)
                    if v is None:
                        continue
                    try:
                        u[key] = int(round(100 * min(1.0, 0.8 + box_glass_k(v))))
                    except (TypeError, ValueError):
                        pass
                if u:
                    ups[d["id"]] = u
                    moved.append(f"widget {d['id']}: {u}")
            if ups:
                WidgetRegistry.update_many(ups)
        except Exception as e:
            log_warn(f"web pinned box opacity (own styles): {e!r}", tag="WEB")
    conf[_BOX_MIGRATED] = vals[_BOX_MIGRATED] = True
    try:
        # only these keys, over the file as it is (the widgets' list was just written by the registry)
        cfg.write_config_vals(vals)
        trace("box opacity: " + (", ".join(moved) if moved else ("dark theme, values kept" if not light else "nothing to move")))
    except Exception as e:
        log_warn(f"web pinned box opacity: {e!r}", tag="WEB")


def _web_i18n():
    try:
        from ..i18n import web_catalog

        return web_catalog()
    except Exception:
        return {}


def _boot(deck_id, is_browser, token):
    from ..const.config import Config

    try:
        _migrate_box_opacity()
    except Exception as e:
        log_warn(f"web pinned box opacity: {e!r}", tag="WEB")

    try:  # every box is one line (rebuild_overlay_inner does the same before building)
        from ..details.widgets.pinned.main_menu.one_line_boxes import split_lines_into_boxes

        split_lines_into_boxes()
    except Exception as e:
        log_warn(f"web pinned split lines: {e!r}", tag="WEB")
    from ..details.widgets.pinned.main_menu.runtime.overlay_margins import (
        DEFAULT_BOTTOM, DEFAULT_SIDE, DEFAULT_TOP, _clamped, gap_px, section_gap_default,
    )

    conf = _conf()
    defs = _defs(deck_id, is_browser)
    from ..details.logic.search_filter import normalize_query, resolve_search
    for d in defs:
        sq = normalize_query(d.get("search_query"))
        if sq:
            resolve_search(sq)
    order = _block_order(defs)
    widgets = []
    for d in defs:
        t = d.get("type")
        sq = normalize_query(d.get("search_query"))
        w = {k: d.get(k) for k in ("id", "type", "label", "width", "height", "chart_box", "stat_box", "text_box",
                                    "stat_key", "col_span", "col_offset", "row_num")}
        w["title"] = _title(d)
        w["search_query"] = sq
        w["span"] = [d.get("time_span", -1), d.get("custom_days") or 0, d.get("deck_ids") or d.get("deck_id"),
                     d.get("time_unit"), d.get("own_colors"), d.get("use_custom_style"), sq]
        if t not in ("stat_card", "text_label"):
            w["options"] = providers.widget_options(t, own=d)
            # the number of its own options, counted at a hover (web_menus.context): its options icon is drawn
            # only when it has some, from the start (Distribution showed one, gone at the first hover)
            if d.get("own_n") is not None:
                w["own_n"] = d.get("own_n")
            w["chips"] = [_span_label(d), _deck_label(d)] if conf.get(Config.PINNED_CARD_LABELS, True) else ["", ""]
        if _PREV.get(("n", d["id"])) is not None:
            w["nat"] = _PREV[("n", d["id"])]
        prev = _PREV.get(("t" if t == "text_label" else "d", d["id"]))
        if prev is not None and t != "stat_card":
            w["pre"] = prev
        if t != "stat_card":
            try:
                w["look"] = _card_look(conf, t, d)
            except Exception as e:
                log_warn(f"web pinned look {t}: {e!r}", tag="WEB")
        widgets.append(w)
    gap = section_gap_default(conf)
    # the block's first time on screen since Anki started: it fades in (pinned.js DDP.start)
    now = time.monotonic()
    if _INTRO["since"] is None:
        _INTRO["since"] = now
    first = not _INTRO["done"] and now - _INTRO["since"] < _INTRO_MAX_S
    if first:
        for w in widgets:
            if w.get("type") not in ("stat_card", "text_label"):
                w.pop("pre", None)  # its opening animation, not its last picture
    return {
        "token": token, "deck": deck_id, "browser": bool(is_browser), "first": first, "built": now, "skel": bool(first and _INTRO["skel"]),
        "i18n": _web_i18n(), "anim": providers.anim_settings("pinned"),
        "theme": build_theme("pinned"), "settings": {"bin_scale": 100},
        "widgets": widgets, "order": order,
        "pre_stats": {k[1]: v for k, v in list(_PREV.items()) if k[0] == "s"},
        "stat_last": dict(_LAST_STAT),
        "unlinked": dict(_UNLINKED),
        "margins": [_clamped(conf, Config.PINNED_MARGIN_TOP, DEFAULT_TOP), _clamped(conf, Config.PINNED_MARGIN_SIDE, DEFAULT_SIDE),
                    _clamped(conf, Config.PINNED_MARGIN_BOTTOM, DEFAULT_BOTTOM)],
        "gaps": {k: gap_px(conf, "box:" + k, gap) for k in order}, "gap": gap,
        "show_stats": bool(conf.get(Config.DEEP_DIVE_PINNED_SHOW_STATS, True)),
        "show_bottom_stats": bool(conf.get(Config.DEEP_DIVE_PINNED_SHOW_BOTTOM_STATS, False)),
        "collapsible": bool(conf.get(Config.PINNED_CHARTS_COLLAPSIBLE, False)),
        "collapsed": _collapsed_ids() if conf.get(Config.PINNED_CHARTS_COLLAPSIBLE, False) else [],
        "stat_fx": _stat_fx(conf),
        "heatmap_title": not bool(conf.get(Config.HEATMAP_HIDE_TITLE, True)),
        "heatmap_nav": str(conf.get(Config.HEATMAP_NAV_POS, "top_right") or "top_right"),
        "recent_searches": [str(q) for q in (conf.get("Deep_Dive_Recent_Searches") or []) if str(q or "").strip()][:8],
    }


# ---- the card around a widget: widget_factory/styler.apply_style (glass, surface, border) ----------------
def _card_look(conf, wtype, own):
    """CSS of a pinned card, computed as styler.apply_style does for charts, text widgets and the heatmap."""
    from ..const.config import Config

    c = dict(conf)
    if own.get("use_custom_style", False):
        c.update(own)
    d = Config.DEFAULT_CONFIG
    hover_border = True
    blur_key, shadow_key = Config.PINNED_GLASS_BLUR, Config.PINNED_GLASS_SHADOW
    if wtype == "text_label":
        blur_key, shadow_key = Config.TEXT_WIDGET_GLASS_BLUR, Config.TEXT_WIDGET_GLASS_SHADOW
        glass = c.get(Config.TEXT_WIDGET_SHOW_GLASS, True)
        intensity = c.get(Config.TEXT_WIDGET_GLASS_INTENSITY, d[Config.TEXT_WIDGET_GLASS_INTENSITY])
        border_pct = c.get(Config.TEXT_WIDGET_GLASS_BORDER, 50)
        hover_border = c.get(Config.TEXT_WIDGET_HOVER_BORDER, True)
    elif wtype == "heatmap":
        blur_key, shadow_key = Config.HEATMAP_GLASS_BLUR, Config.HEATMAP_GLASS_SHADOW
        glass = c.get(Config.HEATMAP_SHOW_GLASS, False)
        intensity = c.get(Config.HEATMAP_GLASS_INTENSITY, d[Config.HEATMAP_GLASS_INTENSITY])
        border_pct = c.get(Config.HEATMAP_GLASS_BORDER, 0)
    else:
        glass = c.get(Config.PINNED_GLASS, True)
        intensity = c.get(Config.PINNED_GLASS_INTENSITY, d[Config.PINNED_GLASS_INTENSITY])
        border_pct = c.get(Config.PINNED_GLASS_BORDER, 50)
        hover_border = c.get(Config.PINNED_HOVER_BORDER, False)
    if not glass:
        return {"glass": False, "bg": "transparent", "border": "none", "hover": "none", "radius": 14, "pad": [0, 0, 0, 0]}
    from .theme import pinned_box

    look = pinned_box(intensity, border_pct, hover_border)
    surface, border, hover = look["bg"], look["border"], look["hover"]
    # _wrap's layout: (6, 3 or 2, 6, 6), then (10, 6, 10, 6) with the glass
    blur, shadow = _glass_fx(c, blur_key, shadow_key)
    if look.get("anki_bg") is not None:  # Anki's panel colour (theme.pinned_box), the computed one as fallback
        surface = f"color-mix(in srgb, var(--canvas-elevated, {look.get('anki_fallback', '#363636')}) {look['anki_bg']}%, transparent)"
    return {"glass": True, "bg": surface, "border": border, "hover": hover, "radius": 14, "pad": [6, 10, 6, 10],
            "blur": blur, "shadow": shadow}


def _glass_fx(c, blur_key, shadow_key):
    """(blur px 0-40, shadow % 0-100) of a box: the web glass settings (config widgets/web_glass.py).
    A blur of -1 is "Auto": the page blurs only over a background image (pinned.js autoBlur)."""
    from ..const.config import Config

    out = []
    for key, low, top in ((blur_key, -1, 40), (shadow_key, 0, 100)):
        try:
            out.append(max(low, min(top, int(c.get(key, Config.DEFAULT_CONFIG.get(key, 0)) or 0))))
        except (TypeError, ValueError):
            out.append(0)
    return out[0], out[1]


_RENAMED = {("todays_retention", "Today's Retention"): "First Answer Retention"}


def _title(d):
    """WidgetFactory.create's label: the saved one or the type's name, translated; an emptied one = no header."""
    from ..i18n import tr_name

    t = d.get("type")
    lab = d.get("label")
    if t == "text_label" or (lab is not None and not str(lab).strip()):
        return None
    if lab:
        # a chart renamed since it was pinned: its old name (the label saved then) shows the new one
        lab = _RENAMED.get((t, str(lab)), lab)
        return tr_name(lab)
    names = {"activity": "Activity", "retention": "Retention", "heatmap": "Heatmap", "added": "Added",
             "distribution": "Distribution", "card_counts": "Card Counts", "hourly": "Hourly Breakdown",
             "future_due": "Future Due", "review_intervals": "Review Intervals", "stability": "Card Stability",
             "difficulty": "Card Difficulty", "retrievability": "Card Retrievability"}
    try:
        from ..details.widgets.charts.more_charts import CHARTS

        names.update({m.widget_type: m.label for m in CHARTS})
    except Exception:
        pass
    return tr_name(names.get(t) or t.replace("_", " ").title())


def _stat_fx(conf):
    from ..const.config import Config

    if not conf.get(Config.FACECARDS_SHOW_GLASS, True):
        return {"blur": 0, "shadow": 0}
    blur, shadow = _glass_fx(conf, Config.FACECARDS_GLASS_BLUR, Config.FACECARDS_GLASS_SHADOW)
    return {"blur": blur, "shadow": shadow}


def preview_styles(config_manager=None, conf=None, own=None, edit=None):
    """The settings dialogs show their changes live (update_styles(config_manager=its copy)): the boxes of the page
    take the looks of that copy at once, the block being built again only when the dialog saves.
    edit: {widget id: its definition in the dialog}, the chart settings being edited (Chart Appearance).
    Drawn once the change in progress is over (next turn of the event loop, the last call wins): a theme picked in
    Settings came here before the theme manager was synced with it, and the main screen showed the theme before."""
    from aqt.qt import QTimer

    first = _state.get("pv_args") is None
    _state["pv_args"] = (config_manager, conf, own, edit)
    if first:
        QTimer.singleShot(0, _preview_now)


def _preview_now():
    args = _state.pop("pv_args", None)
    if args is not None:
        _preview_styles_now(*args)


def _preview_styles_now(config_manager=None, conf=None, own=None, edit=None):
    deck, browser = _page()
    if browser is None or not enabled():
        return
    try:
        if conf is None:
            conf = dict(getattr(config_manager, "config", None) or _conf())
        looks, opts = {}, {}
        for d in _defs(deck, browser):
            if d.get("type") != "stat_card":
                if own and d["id"] in own:
                    d = dict(d, **own[d["id"]])  # the widget's own style, being edited
                looks[d["id"]] = _card_look(conf, d.get("type"), d)
                if d.get("type") != "text_label":
                    # its options drawn at once (setOptions): the heatmap's colors, opacities, scale...; a chart's
                    # opacity, average / total lines, gradient, grid, from the shared Chart Style or its own dialog
                    if edit and d["id"] in edit:
                        d = dict(d, **edit[d["id"]])
                    try:
                        opts[d["id"]] = providers.widget_options(d.get("type"), d, conf)
                    except Exception:
                        pass
        _state["pv"] = (conf, own, edit)
        payload = {"opts": opts, "looks": looks, "stat_fx": _stat_fx(conf), "theme": build_theme("pinned", conf), "stats": True}
        try:  # dev trace: what the live preview gives the boxes (blur / opacity read from the dialog's copy)
            sig = sorted({(lk.get("blur"), lk.get("bg")) for lk in looks.values() if lk.get("glass")})
            if sig != _state.get("pv_sig"):
                _state["pv_sig"] = sig
                trace(f"PREVIEW boxes blur/bg {sig[:4]} stat cards {payload['stat_fx']}")
        except Exception:
            pass
        web = mw.deckBrowser.web if browser else mw.overview.web
        web.eval("window.DDP && DDP.restyle && DDP.restyle(%s)" % json.dumps(payload))
    except Exception as e:
        log_warn(f"web pinned preview: {e!r}", tag="WEB")


def _patch_update_styles():
    """MainMenuWidgetManager.update_styles (called after a settings change) restyles the page's boxes."""
    try:
        from ..details.widgets.pinned.main_menu.manager import MainMenuWidgetManager

        if getattr(MainMenuWidgetManager.update_styles, "_ddp_web", False):
            return
        orig = MainMenuWidgetManager.update_styles

        def update_styles(self, config_manager=None):
            if enabled():
                preview_styles(config_manager)
                return None
            return orig(self, config_manager=config_manager)

        update_styles._ddp_web = True
        MainMenuWidgetManager.update_styles = update_styles
    except Exception as e:
        log_warn(f"web pinned styles: {e!r}", tag="WEB")


def _span_label(d):
    """The period's name as the period menu lists it."""
    from ..details.widgets.pinned.main_menu.ui.card_chips import has_time_span
    from ..const import Period
    from ..i18n import N_, tr_n, tr_name

    if not has_time_span(d):
        return ""
    span, days = d.get("time_span", Period.TOTAL), d.get("custom_days")
    try:
        span = int(span)
    except (TypeError, ValueError):
        return ""
    try:
        from ..details.logic.tabs import get_tabs_config

        for tab in get_tabs_config(providers._cfg()):
            if tab.get("range") != span or (span == Period.CUSTOM and tab.get("days") != days):
                continue
            return tr_name(tab.get("title") or N_("Stats"))
    except Exception:
        pass
    if span == Period.CUSTOM and days:
        return tr_n("{n} day", "{n} days", int(days))
    label = Period.LABEL.get(span)
    return tr_name(label) if label else ""


def _deck_label(d):
    """card_chips.deck_text: the deck(s) the widget reads, "" when it follows the current deck."""
    try:
        from ..details.widgets.pinned.main_menu.ui.card_chips import deck_text

        class _M:
            pass

        return deck_text(_M(), d) or ""
    except Exception:
        return ""


_HIDE_STUDIED = """
(function(){
  function rm(){ var s = document.getElementById('studiedToday'); if (s){ s.remove(); return true; } return false; }
  if (rm()) return; var n = 0; (function again(){ if (rm() || n++ > 20) return; setTimeout(again, 100); })();
  new MutationObserver(rm).observe(document.body, {childList: true, subtree: true});
})();
"""


def _block(deck_id, is_browser):
    token = uuid.uuid4().hex[:12]
    t0 = time.perf_counter()
    _state.pop("pv", None)
    boot = _boot(deck_id, is_browser, token)
    if not boot["widgets"]:
        return _empty_hint(is_browser)
    try:  # Anki built its page again during the tour: the tour comes back on the new page
        from . import tour

        if tour.running() and is_browser:
            boot["tour"] = tour.payload()
    except Exception as e:
        log_warn(f"web pinned tour: {e!r}", tag="WEB")
    scripts = f"<script>{_js()}</script>"
    hide = f"<script>{_HIDE_STUDIED}</script>" if is_browser and _conf().get("Pinned_Position_Top", True) else ""
    m_top = 15 if is_browser else 0
    boot_js = json.dumps(boot).replace("</", "<\\/")
    html = (
        f'<style>{_css()}</style>'
        f'<div id="ddp-root" style="width:100%;box-sizing:border-box;margin-top:{m_top}px;margin-bottom:10px"></div>'
        f"{scripts}{hide}"
        f"<script>{dev_flag()}DDP.start({boot_js});</script>"
    )
    trace(f"web pinned block: {len(boot['widgets'])} widgets, {1000 * (time.perf_counter() - t0):.0f} ms")
    return html


def _empty_hint(is_browser):
    """Nothing pinned at all (empty_hint.py): a discreet dashed "+ Add a widget" card on the main screen, its "x"
    hiding it for good (Settings > Pinned Widgets brings it back). Not for widgets only hidden on this deck."""
    from ..const.config import Config
    from ..details.logic.widget_registry import WidgetRegistry
    from ..i18n import tr

    try:
        if not is_browser or not _conf().get(Config.PINNED_EMPTY_HINT, True) or WidgetRegistry.get_all():
            return ""
        dark = bool(build_theme("pinned")["is_dark"])
    except Exception:
        return ""
    line = "rgba(255,255,255,.24)" if dark else "rgba(0,0,0,.22)"
    fg = "rgba(235,235,240,.85)" if dark else "rgba(30,32,38,.8)"
    hov = "rgba(255,255,255,.07)" if dark else "rgba(0,0,0,.05)"
    esc = lambda t: (t.replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;"))
    return (
        f'<style>#ddp-empty button{{background:transparent;border:0;color:{fg};cursor:pointer;border-radius:6px}}'
        f'#ddp-empty button:hover{{background:{hov}}}</style>'
        f'<div id="ddp-empty" style="position:relative;max-width:420px;height:64px;margin:15px auto 10px;box-sizing:border-box;'
        f'border:1.4px dashed {line};border-radius:10px;display:flex;align-items:center;justify-content:center">'
        f'<button onclick="pycmd(\'ddp_empty:add\')" style="font-size:14px;font-weight:600;padding:8px 16px">+&nbsp;&nbsp;{esc(tr("Add a widget"))}</button>'
        f'<button title="{esc(tr("Hide (Settings > Pinned Widgets shows it again)"))}" onclick="pycmd(\'ddp_empty:hide\')" '
        f'style="position:absolute;top:4px;right:6px;font-size:15px;padding:0 6px">&times;</button></div>'
    )


def _on_empty_hint(what):
    from ..const.config import Config

    try:
        if what == "add":
            from ..details.widgets.pinned.main_menu.ui.add_here import open_gallery_at

            open_gallery_at(_manager(), None)
        elif what == "hide":
            providers._cfg().write_config_vals({Config.PINNED_EMPTY_HINT: False})
            _redraw()
        elif what == "redraw":
            _redraw()
    except Exception as e:
        log_warn(f"web pinned empty hint: {e!r}", tag="WEB")


def _on_browser(_browser, content):
    if not enabled():
        return
    try:
        from . import startup_probe

        startup_probe.mark("deck list: pinned block asked")
        block = startup_probe.timed("deck list: pinned block built", _block, None, True)
        if _conf().get("Pinned_Position_Top", True):
            content.stats = block + content.stats
        else:
            content.stats = content.stats + block
    except Exception as e:
        log_error(f"web pinned (deck list): {e!r}")


def _on_overview(overview, content):
    if not enabled():
        return
    try:
        did = int(overview.mw.col.decks.selected())
        block = _block(did, False)
        if _conf().get("Pinned_Position_Top_Deck", False):
            content.table = block + content.table
        else:
            content.table = content.table + block
    except Exception as e:
        log_error(f"web pinned (overview): {e!r}")


def _on_congrats(webview):
    """The deck is finished: Anki shows its "Congratulations" page (a page of its own, no overview hook). The block
    goes just before the message."""
    if not enabled():
        return
    try:
        url = webview.page().url()
        if url.isEmpty() or "congrats" not in url.toDisplayString().lower() or mw.state != "overview":
            return
        did = int(mw.col.decks.selected())
        token = uuid.uuid4().hex[:12]
        _state.pop("pv", None)
        boot = _boot(did, False, token)
        if not boot["widgets"]:
            return
        place = """
(function(){
  var old = document.getElementById('ddp-root'); if (old) old.remove();
  var st = document.getElementById('ddp-style');
  if (!st){ st = document.createElement('style'); st.id = 'ddp-style'; st.textContent = %s; document.head.appendChild(st); }
  var root = document.createElement('div'); root.id = 'ddp-root';
  root.style.cssText = 'width:100%%;box-sizing:border-box;margin-top:0;margin-bottom:10px';
  function go(){
    if (!window.DDP){ var sc = document.createElement('script'); sc.textContent = %s; document.head.appendChild(sc); }  // global scope
    DDP.start(%s);
  }
  // put in once the page has loaded, before Anki's message is drawn: 15 px down, full width above the message
  root.style.marginTop = '15px';
  var t = document.querySelector('table'); if (t) t.after(root); else document.body.prepend(root);
  go();
})();
""" % (json.dumps(_css()), json.dumps(_js()), json.dumps(boot).replace("</", "<\\/"))
        webview.eval(place)
        trace(f"web pinned block (congrats): {len(boot['widgets'])} widgets")
    except Exception as e:
        log_error(f"web pinned (congrats): {e!r}")


# ---- page -> Python --------------------------------------------------------------------------------
def _def_of(wid):
    from ..details.widgets.pinned.main_menu.ui.widget_defs import normalized_widget_def
    from ..details.logic.widget_registry import WidgetRegistry

    for d in WidgetRegistry.get_all() or []:
        if isinstance(d, dict) and d.get("id") == wid:
            return normalized_widget_def(d)
    return None


def _deck_of(d, page_deck):
    """The deck the widget reads (deck_ids, else deck_id, else the page's)."""
    from ..details.widgets.pinned.widget_factory.utils import _resolve_deck_ids

    if "deck_ids" in d:
        return _resolve_deck_ids(d["deck_ids"], page_deck)
    if "deck_id" in d:
        return d["deck_id"]
    return page_deck


def _h_data(id=None, deck=None, at=None, span=None):
    """at: the day a Time Machine's slider picked; span: temporary override (e.g. -1 when zooming out past a widget's span)."""
    from ..details.logic.search_filter import search_scope

    d = _def_of(id)
    if d is None:
        return None
    t = d.get("type")
    use_span = -1 if t == "heatmap" else (int(span) if span is not None else int(d.get("time_span", -1)))
    opts = providers.widget_options(t, own=d)
    sq = str(d.get("search_query") or "").strip()
    with search_scope(sq):
        if at:
            return providers.fetch(t, _deck_of(d, deck), use_span, dict(opts or {}, at=str(at)), own=d)
        out = providers.fetch(t, _deck_of(d, deck), use_span, opts, own=d)
    if span is None:
        _PREV[("d", id)] = out
    return out


def _h_stats(ids=None, deck=None):
    """The stat cards of one box, each with its own deck and period (pinned stat_card builder values)."""
    cfg = providers._cfg()
    pv = _state.get("pv")  # a settings dialog showing its changes live: its copy of the settings
    conf = pv[0] if pv else cfg.config
    own = (pv[1] if pv else None) or {}
    edit = (pv[2] if pv and len(pv) > 2 else None) or {}
    entries = []
    for wid in ids or []:
        d = _def_of(wid)
        if d is None:
            continue
        if wid in edit:
            d = dict(d, **edit[wid])
        if wid in own:
            d = dict(d, **own[wid])
        entries.append((wid, d))
    out = stat_spec(entries, deck, conf)
    _stats_again_when_built()
    if pv:
        return out
    for c in out.get("cards") or []:
        _LAST_STAT[c["key"]] = c["value"]
    if _PREV.get(("s", ",".join(ids or []))) != out:
        _PREV[("s", ",".join(ids or []))] = out
        _save_prev_soon()
    return out


def _stats_again_when_built():
    """Stat cards asked while the history cache is still being built (first start, after Clear Cache or an
    import) got empty values: the page asks for them again once it is built (they are answered on the UI
    thread, so they cannot wait for it as the charts' data does)."""
    try:
        from ..details.logic.history_cache import GlobalHistoryCache

        if GlobalHistoryCache().is_initialized or _state.get("stats_wait"):
            return
        _state["stats_wait"] = True

        def again():
            _state["stats_wait"] = False
            eval_block("document.querySelectorAll('.dd-sc-host').forEach(function(h){"
                       " if (h.parentNode && h.parentNode._ddpStats) h.parentNode._ddpStats(); });")

        GlobalHistoryCache.init_async(again)
    except Exception as e:
        _state["stats_wait"] = False
        log_warn(f"pinned stats: could not wait for the cache: {e!r}")


def stat_spec(entries, deck, conf=None):
    """The stat cards of entries [(id, widget def)] as the page draws them (DD.stats compact spec); also the
    gallery's previews (web_ui.gallery_pics)."""
    from ..const.config import Config
    from ..const.theme.color_resolver import get_color
    from ..details.ui import STAT_KEY_TO_COLOR_KEY
    from ..details.widgets.chart_utils.own_colors import clean_own_colors
    from ..details.widgets.pinned.widget_factory.builders.stat_card import TIME_STAT_FIELDS, _build_stat_values_map
    from ..details.widgets.pinned.widget_factory.builders.time_units import apply_time_unit
    from ..details.widgets.stats_cards import get_stat_card_info
    from ..details.widgets.stats_cards.ui.sizing import compact_typography, scale_ratio_from_percent
    from ..i18n import tr_name

    cfg = providers._cfg()
    conf = conf if conf is not None else cfg.config
    colors = conf.get(Config.DASH_STAT_COLORS) or {}
    prec = int(conf.get(Config.STATS_PRECISION, 2))
    maps = {}
    cards = []
    scale = scale_ratio_from_percent(conf.get(Config.FACECARDS_SCALE, 100))
    from ..details.logic.search_filter import normalize_query, search_scope

    for wid, d in entries:
        key = d.get("stat_key")
        did, span = _deck_of(d, deck), int(d.get("time_span", -1))
        days = int(d.get("custom_days") or 7)
        sq = normalize_query(d.get("search_query"))
        mkey = (tuple(did) if isinstance(did, list) else did, span, days, sq)
        if mkey not in maps:
            with search_scope(sq):
                maps[mkey] = _build_stat_values_map(did, span, days, cfg=cfg, with_day_stats=True, with_deck_state=True) or {}
        title, fallback = get_stat_card_info(key)
        color_key = STAT_KEY_TO_COLOR_KEY.get(key)
        own_col = (clean_own_colors(d.get("own_colors")) or {}).get(color_key)
        color = own_col or colors.get(key) or (get_color(conf, color_key, "pinned") if color_key else fallback)
        raw_lbl = d.get("label")
        label = (tr_name(raw_lbl) if str(raw_lbl).strip() else "") if raw_lbl is not None else title
        stat_vals = maps[mkey]
        raw_val = stat_vals.get(key, "...")
        field = TIME_STAT_FIELDS.get(key)
        unit = d.get("time_unit")
        if field and unit and unit != "auto":
            converted = apply_time_unit(field, unit, stat_vals, prec)
            if converted is not None:
                raw_val = converted
        value = str(raw_val)
        own_style = bool(d.get("use_custom_style", False))
        cconf = dict(conf, **d) if own_style else conf  # its own Settings over the shared ones (styler.apply_style)
        cscale = scale_ratio_from_percent(cconf.get(Config.FACECARDS_SCALE, 100)) if own_style else scale
        # its width is measured by the page (stats.js idealW: StatCardWidget.get_ideal_width at its scale "s")
        cards.append({"key": wid, "stat_key": key, "label": label, "value": value, "s": cscale,
                      "color": color, "row": 0, "own_color": bool(colors.get(key)), "style": _stat_own_style(conf, d),
                      "tm": _title_mult(cconf) if own_style else None})
    k = compact_typography(scale)
    out = {"compact": {"h": k["targ_h"], "val": k["val_fs"], "title": k["title_fs"], "hm": k["h_margin"], "tm": _title_mult(conf)},
            "cards": cards,
            "unlocked": list(conf.get("UNLOCKED_EFFECTS") or []),
            "hover_effect": bool(conf.get(Config.FACECARDS_HOVER_EFFECT, True))}
    return out


def _stat_own_style(conf, d):
    """A pinned stat card with its own style (its Settings: Facecards_* keys on its entry)."""
    if not d.get("use_custom_style", False):
        return None
    try:
        from .theme import stat_style
        from ..details.widgets.chart_utils.theme import ThemeContext, get_theme_colors

        t = get_theme_colors(ThemeContext.PINNED)
        return stat_style(dict(conf, **d), t, bool(t["is_dark"]), pinned=True)
    except Exception:
        return None


def _title_mult(conf):
    """The title size multiplier of a pinned card (widget_modes.title_size_multiplier, without building a card)."""
    from ..const.config import Config
    from ..i18n import caption_scale

    try:
        raw = float(conf.get(Config.FACECARDS_TITLE_SIZE, 100))
    except Exception:
        raw = 100.0
    return max(0.5, min(2.0, raw / 100.0)) * caption_scale()


def _h_text(id=None, deck=None):
    from ..details.widgets.pinned.widget_factory.builders.text_label import _build_runtime_payload, safe_html, shown_template

    d = _def_of(id)
    if d is None:
        return ""
    pv = _state.get("pv")
    edit = (pv[2] if pv and len(pv) > 2 else None) or {}
    if id in edit:
        d = dict(d, **edit[id])
    # the default sentence in the interface language, a sentence the user wrote as it is
    payload = _build_runtime_payload(
        shown_template(d.get("template") or ""),
        _deck_of(d, deck),
        int(d.get("time_span", -1)),
        int(d.get("custom_days") or 7),
        cfg=providers._cfg(),
        default_custom_type=d.get("custom_type", "relative"),
        default_start_date_str=d.get("start_date", ""),
        default_end_date_str=d.get("end_date", ""),
    )
    out = safe_html((payload or {}).get("resolved") or "")
    if not pv and _PREV.get(("t", id)) != out:
        _PREV[("t", id)] = out
        mw.taskman.run_on_main(_save_prev_soon)
    return out


def _h_menu(id=None, x=0, y=0, deck=None, zoom=None, own=False, count=False, _wid=None):
    """The right-click menu of a pinned widget, shown by the page: {items, open} (web_menus: the native menu's
    entries, never shown itself). own: its entries that change this chart alone (its header's options icon);
    count: their number only, {n}."""
    from . import web_menus

    if zoom is not None:
        _state["zoom_ids"] = list(zoom or [])
    res = web_menus.context(id, own=bool(own), count=bool(count))
    if not own and not count and isinstance(res, dict) and isinstance(res.get("items"), list):
        d = _def_of(id)
        if d is not None and d.get("type") != "text_label":
            import html as _html
            from ..details.logic.search_filter import normalize_query

            sq = normalize_query(d.get("search_query"))
            short_q = (sq[:22] + "\u2026") if len(sq) > 23 else sq
            lbl = _html.escape(f"Search Filter: {short_q}") if sq else "Search Filter..."
            entry = ["__search_filter", lbl, bool(sq) if sq else None, "filter", None, None, False]
            items = list(res["items"])
            # Place near the top (right after Select Decks / Time Span, before the first separator if any)
            idx = next((i for i, it in enumerate(items) if it == "sep"), len(items))
            items.insert(idx, entry)
            res = dict(res, items=items, wid=id, search_query=sq)
    return res


def _h_set_search_filter(id=None, query=""):
    """Validate and save a per-widget Anki search query on a pinned chart or stat card."""
    from ..const.config import Config
    from ..details.logic.search_filter import normalize_query, resolve_search

    q = normalize_query(query)
    cids = None
    if q:
        cids, err = resolve_search(q)
        if err is not None:
            return {"ok": False, "query": q, "error": err}

    cfg = providers._cfg()
    conf = cfg.config
    raw = list(conf.get(Config.PINNED_WIDGETS) or [])
    changed = False
    for item in raw:
        if isinstance(item, dict) and item.get("id") == id:
            if q:
                item["search_query"] = q
            else:
                item.pop("search_query", None)
            changed = True
            break
    recent = [str(x) for x in (conf.get("Deep_Dive_Recent_Searches") or []) if str(x or "").strip()][:8]
    if q:
        recent = ([q] + [x for x in recent if x != q])[:8]
        conf["Deep_Dive_Recent_Searches"] = recent
    if changed:
        _PREV.pop(("d", id), None)
        conf[Config.PINNED_WIDGETS] = raw
        cfg.write_config()
    return {"ok": True, "query": q, "count": len(cids) if cids is not None else None, "recent": recent}


def _h_pin_past(id=None, _wid=None):
    """View on a Past Day (a chart's options icon): its Time Machine pinned right after it (pinning.pin_past)."""
    from ..details.logic.pinning import pin_past

    return pin_past(id)


def _h_widget_settings(id=None, _wid=None):
    """The widget's settings window, as its right click's Settings: a header menu's "Edit Buttons..." (discrete.js).
    Opened once the page's call has its answer (the window is modal); the main screen rebuilt if it changed."""
    from aqt.qt import QTimer

    from . import web_menus

    d = _def_of(id or _wid)
    if d is None:
        return False
    seen = {"c": _config_snapshot()}

    def run():
        try:
            from ..details.widgets.pinned.main_menu.manager import MainMenuWidgetManager

            m = MainMenuWidgetManager.instance()
            with _web_menu(m, d.get("id")):
                m._open_widget_settings(_proxy(d), d)
        except RuntimeError:
            return
        except Exception as e:
            log_error(f"web pinned widget settings: {e!r}")
        preview_styles()  # cancelled: the saved looks again
        web_menus._check(seen)

    QTimer.singleShot(0, run)
    return True


def _h_menu_pick(key=None, on=None, _wid=None):
    """An entry of a menu the page shows (web_menus) clicked."""
    from . import web_menus

    return web_menus.pick(key, on)


# Zoom link of the page's charts (the menu asks pinned/zoom_link.py, patched by _web_menu): the charts left out of it
_UNLINKED = {}


def _push_unlinked():
    try:
        deck, browser = _page()
        if browser is None:
            return
        web = mw.deckBrowser.web if browser else mw.overview.web
        web.eval("window.DDP && DDP.setUnlinked && DDP.setUnlinked(%s)" % json.dumps(_UNLINKED))
    except Exception:
        pass


class _web_menu:
    """While the native menu is open: its "Fullscreen" shows the page's card fullscreen, and its zoom link entries
    read and change the page's charts (the stand-in card has no chart of its own)."""

    def __init__(self, manager, wid):
        self.m, self.wid = manager, wid

    def __enter__(self):
        from ..details.widgets.pinned import zoom_link as zl

        self.zl, self.saved = zl, {k: getattr(zl, k) for k in ("has_charts", "counts", "is_linked", "set_linked", "set_all_linked")}
        ids, wid = list(_state.get("zoom_ids") or []), self.wid

        def set_linked(_w, v):
            if v:
                _UNLINKED.pop(wid, None)
            else:
                _UNLINKED[wid] = True
            _push_unlinked()

        def set_all(_m, v):
            for i in ids:
                if v:
                    _UNLINKED.pop(i, None)
                else:
                    _UNLINKED[i] = True
            _push_unlinked()

        zl.has_charts = lambda _w: wid in ids
        zl.counts = lambda _m: (sum(1 for i in ids if i not in _UNLINKED), sum(1 for i in ids if i in _UNLINKED))
        zl.is_linked = lambda _w: wid not in _UNLINKED
        zl.set_linked = set_linked
        zl.set_all_linked = set_all
        cm = self.m._context_menu
        self.fs = cm.__dict__.get("_open_fullscreen")

        def fullscreen(_w):
            deck, browser = _page()
            web = mw.deckBrowser.web if browser else mw.overview.web
            web.eval("window.DDP && DDP.fullscreen(%s)" % json.dumps(wid))

        cm._open_fullscreen = fullscreen
        # "About This Chart": the explanation shown by the page, where the menu was (a Qt popup would be anchored on
        # the hidden stand-in card: nothing would show)
        from ..details.widgets.common import chart_help as ch

        self.ch, self.help = ch, ch.add_help_action

        def add_help(menu, chart_type, _anchor, _orig=ch.add_help_action):
            act = _orig(menu, chart_type, _anchor)
            if act is not None:
                try:
                    act.triggered.disconnect()
                except (TypeError, RuntimeError):
                    pass

                def show(_=False):
                    deck, browser = _page()
                    web = mw.deckBrowser.web if browser else mw.overview.web
                    web.eval("window.DDP && DDP.showHelp && DDP.showHelp(%s)" % json.dumps(wid))

                act.triggered.connect(show)
            return act

        ch.add_help_action = add_help
        return self

    def __exit__(self, *_exc):
        for k, v in self.saved.items():
            setattr(self.zl, k, v)
        self.ch.add_help_action = self.help
        cm = self.m._context_menu
        if self.fs is None:
            cm.__dict__.pop("_open_fullscreen", None)
        else:
            cm._open_fullscreen = self.fs
        return False


def _h_chip(id=None, which="span", x=0, y=0, top=None, deck=None, _wid=None):
    """A click on the period / deck label of a card: the period list, shown by the page ({items}, web_menus), or
    the deck dialog (card_chips)."""
    from aqt.qt import QTimer

    if which != "deck":
        from . import web_menus

        return web_menus.span(id)
    QTimer.singleShot(0, lambda: _show_chip(id, which, float(x or 0), float(y or 0), None if top is None else float(top)))
    return True


def _show_chip(wid, which, x, y, top=None):
    from aqt.qt import QPoint, QTimer

    try:
        from ..details.widgets.pinned.main_menu.manager import MainMenuWidgetManager
        from ..details.widgets.pinned.main_menu.ui.card_chips import choose_decks, fill_span_menu, hide_card_labels, themed_menu
        from ..i18n import tr

        d = _def_of(wid)
        if d is None:
            return
        m = MainMenuWidgetManager.instance()
        m._config_manager = m._get_config_manager(force_refresh=True)
        web = mw.web
        seen = {"c": _config_snapshot()}
        px = _proxy(d)
        if which == "deck":
            choose_decks(m, px, d)
        else:
            zoom = float(web.zoomFactor() or 1.0)
            menu = themed_menu(px, m)
            fill_span_menu(menu, m, px, d)
            menu.addSeparator()
            hide = menu.addAction(tr("Hide these labels"))
            hide.triggered.connect(lambda _=False: hide_card_labels(m))
            # above the label when the screen has room there (the menu then covers the title
            # row and the cards above, not the chart), else under it
            at = web.mapToGlobal(QPoint(int(round(x * zoom)), int(round(y * zoom))))
            if top is not None:
                try:
                    up = web.mapToGlobal(QPoint(int(round(x * zoom)), int(round(top * zoom)))).y() - menu.sizeHint().height() - 2
                    screen = web.screen().availableGeometry() if web.screen() is not None else None
                    if screen is not None and up >= screen.top():
                        at = QPoint(at.x(), up)
                except RuntimeError:
                    pass
            menu.exec(at)

        def check():
            if _state.get("listening"):
                return  # the config listener rebuilds the block (refresh_block)
            now = _config_snapshot()
            if now != seen["c"]:
                seen["c"] = now
                refresh_block()

        check()
        for ms in (400, 1500):
            QTimer.singleShot(ms, check)
    except Exception as e:
        log_error(f"web pinned chip: {e!r}")


def _proxy(d):
    """A hidden stand-in for the native card the menu and the settings dialog act on (they style it, give it
    margins, look for its charts): with the web view itself in its place they styled the whole page."""
    from aqt.qt import QFrame

    p = _state.get("proxy")
    try:
        if p is not None:
            p.isHidden()
    except RuntimeError:
        p = None
    if p is None:
        p = QFrame(mw)
        p.setObjectName("pinned_widget_card")
        p.hide()
        _state["proxy"] = p
    p.widget_id = d.get("id")
    p.wtype = d.get("type")
    p.inner_widget = None
    p.setStyleSheet("")
    return p


def _config_snapshot():
    try:
        from ..config import ConfigManager

        return json.dumps(ConfigManager(mw).config, sort_keys=True, default=str)
    except Exception:
        return None


# ---- what the chart modules save: on the pinned widget's own definition (the pinned builders' keys) ----
_KEYS = {"breakdown_enabled": "show_breakdown", "visibility": "visible_series"}


def _save(wid, key, value):
    from ..details.logic.widget_registry import WidgetRegistry

    if wid:
        _state["quiet"] = time.monotonic() + 0.6  # saved by the page itself: it shows it already
        WidgetRegistry.update_setting(wid, key, value)
        _PREV.pop(("d", wid), None) if key in ("heatmap_mode",) else None
    return True


def _h_set_setting(section=None, key=None, value=None, _wid=None):
    return _save(_wid, _KEYS.get(key, key), value)


def _h_pie_separate(on=False, _wid=None):
    return _save(_wid, "separate_suspended", bool(on))


def _window_static(name):
    from .window import WebDeepDiveDialog

    return getattr(WebDeepDiveDialog, name)


def _h_set_heatmap(name=None, value=None, _wid=None):
    _state["quiet"] = time.monotonic() + 0.6  # the page shows it already (its own animation)
    return _window_static("_set_heatmap")(name, value)


def _h_open_day(date=None, deck=None, _wid=None):
    d = _def_of(_wid) if _wid else None
    return _window_static("_open_day")(date, _deck_of(d, deck) if d else deck)


def _h_browse(_wid=None, deck=None, span=None, **spec):
    d = _def_of(_wid) if _wid else None
    if d is not None:
        deck, span = _deck_of(d, deck), int(d.get("time_span", -1))
    return _window_static("_browse")(deck=deck, span=-1 if span is None else span, **spec)


# ---- layout changes made on the page (drag, resize, spaces, "+"), written by the pinned layout code ----
def _manager():
    from ..details.widgets.pinned.main_menu.manager import MainMenuWidgetManager

    m = MainMenuWidgetManager.instance()
    m._config_manager = m._get_config_manager(force_refresh=True)
    return m


def _h_drop(cross=None, _wid=None):
    """A drop on the page (moved, reordered, alone on a new line or in a new box, a box moved):
    details/logic/pinned_layout writes it, the config listener then builds the block again."""
    from ..details.logic import pinned_layout

    try:
        pinned_layout.apply(dict(cross or {}))
    except Exception as e:
        log_error(f"web pinned drop: {e!r}")
        return False
    return True


def _h_resize(id=None, w=None, h=None, _wid=None):
    """A card resized from its edge on the page: its width, and its height without the bottom stats."""
    from ..const.config import Config
    from ..details.widgets.chart_utils.geometry import ChartGeometry
    from ..details.logic.widget_registry import WidgetRegistry

    d = _def_of(id)
    if d is None:
        return False
    updates = {"width": max(1, int(round(float(w))))} if w is not None else {}
    if h is not None:
        conf = _conf()
        h = float(h)
        if conf.get(Config.DEEP_DIVE_PINNED_SHOW_BOTTOM_STATS, False) and conf.get(Config.DEEP_DIVE_PINNED_SHOW_STATS, True):
            h -= ChartGeometry.STATS_EXTRA_HEIGHT.get(d.get("type"), 0)
        updates["height"] = max(50, int(round(h)))
    if updates:
        WidgetRegistry.update_settings_bulk(id, updates)
    return True


def _h_gap(key=None, px=None, _wid=None):
    """gap_handle: the space under a box (None: back to the default)."""
    from ..const.config import Config
    from ..config import ConfigManager

    cm = ConfigManager(mw)
    gaps = dict(cm.config.get(Config.PINNED_GAPS) or {})
    if px is None:
        gaps.pop("box:" + str(key), None)
    else:
        gaps["box:" + str(key)] = max(0, min(200, int(px)))
    cm.set_value(Config.PINNED_GAPS, gaps)
    return True


def _h_add_here(target=None, _wid=None):
    from aqt.qt import QTimer

    def go():
        try:
            from ..details.widgets.pinned.main_menu.ui.add_here import open_gallery_at

            open_gallery_at(_manager(), dict(target or {}))
        except Exception as e:
            log_error(f"web pinned add here: {e!r}")

    QTimer.singleShot(0, go)
    return True


def _h_adaptive(id=None, first=None, last=None, deck=None, _wid=None):
    """The 10-minute rows of the zoomed days for one widget (providers.adaptive, as the window)."""
    d = _def_of(id)
    if d is None:
        return None
    t = d.get("type")
    r = providers.adaptive(_deck_of(d, deck), int(d.get("time_span", -1)), first, last, source=t) or {}
    if not r.get("bounds") or (r.get("added_only") and t != "added"):
        return None
    return {"data": r.get(t), "bounds": r.get("bounds"), "times": r.get("times")}


def _h_review_events(id=None, t0=0, t1=0, deck=None, _wid=None):
    """One dot per review (review_dots): the reviews of the widget's deck between t0 and t1 (ms)."""
    d = _def_of(id)
    if d is None:
        return None
    return providers.review_events(_deck_of(d, deck), t0, t1)


def _h_chart_help(wtype=None, _wid=None):
    from ..details.widgets.common.chart_help import help_text

    return help_text(wtype)


def _h_natural(id=None, h=None, _wid=None):
    if _PREV.get(("n", id)) != h:
        _PREV[("n", id)] = h
        _save_prev_soon()
    return True


def _h_open_card(cid=None, _wid=None):
    return _window_static("_open_card")(cid)


def _h_collapse(id=None, on=False):
    """A card folded / unfolded on the page: remembered for the session."""
    (_COLLAPSED_PINNED.add if on else _COLLAPSED_PINNED.discard)(id)
    return True


def _h_intro_done(_wid=None):
    """The page played the block's intro: the pages built after it show at once, as they were."""
    _INTRO["done"] = True
    return True


def _h_intro_skel(_wid=None):
    """The held page shows the block's skeleton (cards, titles, texts, stat cards; the charts wait): the next page
    starts from it, without fading the cards in again."""
    _INTRO["skel"] = True
    return True


def _h_intro_hold(built=None, _wid=None):
    """Asked by the first page before its intro: True while Anki's sync on opening runs, or has just ended after
    the page was built (built: its boot's time), the deck list about to be built again."""
    if _INTRO["done"]:
        return False
    if _SYNC["running"]:
        return True
    ended = _SYNC["ended"]
    try:
        before = built is not None and float(built) < ended
    except (TypeError, ValueError):
        before = False
    return bool(ended is not None and before and time.monotonic() - ended < _SYNC_TAIL_S)


def _h_onigiri_fit(h=0, _wid=None):
    """Onigiri's main screen: the block's height changed, its cell follows (onigiri.fit)."""
    from . import onigiri

    return onigiri.fit(h)


def _h_onigiri_relayout(_wid=None):
    from . import onigiri

    onigiri.relayout()
    return True


def _h_hello(_wid=None):
    """The page's bridge is up: on the deck list, the first time, the guided tour comes after a while."""
    try:
        if enabled() and getattr(mw, "state", None) == "deckBrowser":
            from . import tour

            tour.maybe_first_start()
    except Exception as e:
        log_warn(f"web pinned tour: {e!r}", tag="WEB")
    return True


def _h_tour_scene(name=None, _wid=None):
    from . import tour

    return tour.h_scene(name)


def _h_tour_end(_wid=None):
    from . import tour

    return tour.h_end()


def _h_tour_menu(id=None, _wid=None):
    from . import tour

    return tour.h_menu(id)


def _h_tour_settings(id=None, _wid=None):
    from . import tour

    return tour.h_settings(id)


def _h_tour_add(chart=None, stat=None, _wid=None):
    from . import tour

    return tour.h_add(chart, stat)


def _h_tour_gallery(which=None, _wid=None):
    from . import tour

    return tour.h_gallery(which)


def _h_stat_lock(key=None, locked=True, _wid=None):
    """Click on a pinned stat card: its glow border stays (locked) or shows on hover only. Kept in
    UNLOCKED_EFFECTS by the pinned widget's id, so it stays after the page is built again (another deck)."""
    from ..config import addon_config as _addon_config

    cfg = _addon_config()
    lst = [x for x in (cfg.config.get("UNLOCKED_EFFECTS") or []) if x != key]
    if not locked and key:
        lst.append(str(key))
    _state["quiet"] = time.monotonic() + 0.6  # the page shows it already
    cfg.set_value("UNLOCKED_EFFECTS", lst)
    # the stat cards' last pictures (shown at once on the next page) carry the locks too, otherwise the other page (a deck's
    # overview) comes up with the border as it was before the click, then takes it away
    for k, v in list(_PREV.items()):
        if k[0] == "s" and isinstance(v, dict):
            _PREV[k] = dict(v, unlocked=list(lst))
    return True


def _h_tour_drag(swap=None, move=None, end=None, box=None, _wid=None):
    from . import tour

    return tour.h_drag(swap, move, end, box)


def _h_tour_span(id=None, _wid=None):
    from . import tour

    return tour.h_span(id)


_HANDLERS = {"hello": (_h_hello, False), "intro_done": (_h_intro_done, False), "intro_hold": (_h_intro_hold, False), "intro_skel": (_h_intro_skel, False), "tour_scene": (_h_tour_scene, False), "tour_settings": (_h_tour_settings, False), "tour_end": (_h_tour_end, False),
             "tour_menu": (_h_tour_menu, False), "tour_span": (_h_tour_span, False), "tour_add": (_h_tour_add, False), "tour_drag": (_h_tour_drag, False), "stat_lock": (_h_stat_lock, False), "tour_gallery": (_h_tour_gallery, False), "menu_pick": (_h_menu_pick, False), "widget_settings": (_h_widget_settings, False),
             "review_events": (_h_review_events, True), "data": (_h_data, True), "stats": (_h_stats, False), "text": (_h_text, True), "menu": (_h_menu, False), "pin_past": (_h_pin_past, False),
             "set_setting": (_h_set_setting, False), "pie_separate": (_h_pie_separate, False), "set_heatmap": (_h_set_heatmap, False),
             "open_day": (_h_open_day, False), "browse": (_h_browse, False), "open_card": (_h_open_card, False),
             "natural": (_h_natural, False), "chip": (_h_chip, False), "drop": (_h_drop, False),
             "resize": (_h_resize, False), "gap": (_h_gap, False), "add_here": (_h_add_here, False),
             "adaptive": (_h_adaptive, True), "chart_help": (_h_chart_help, False), "collapse": (_h_collapse, False), "onigiri_fit": (_h_onigiri_fit, False), "onigiri_relayout": (_h_onigiri_relayout, False),
             "set_search_filter": (_h_set_search_filter, False)}


def _on_message(handled, message, context):
    """Messages of the pinned block only: a "dd:" request carrying the page's token (the Deep Dive window's
    own requests have none and go on to its bridge), or a log line sent while the deck list / overview shows."""
    if isinstance(message, str) and message.startswith("ddp_probe:"):
        page_log(message[10:300])
        return (True, None)
    if isinstance(message, str) and message.startswith("ddp_empty:"):
        _on_empty_hint(message[10:])
        return (True, None)
    if not isinstance(message, str) or not (message.startswith("dd:") or message.startswith("dd_log:")):
        return handled
    web = getattr(context, "web", None)
    if message.startswith("dd_log:"):
        if web is not None and web is getattr(mw, "web", None):
            page_log(message[7:])
            return (True, None)
        return handled
    try:
        req = json.loads(message[3:])
    except Exception:
        return handled
    args = req.get("args") or {}
    if not isinstance(args, dict) or "_token" not in args:
        return handled
    if web is None:
        web = mw.web
    rid, cmd = req.get("id"), req.get("cmd")
    token = args.pop("_token", "")
    def answer(ok, payload):
        try:
            web.eval("window.DDP && DDP.__resolve(%s, %s, %s, %s)" % (json.dumps(token), json.dumps(rid), "true" if ok else "false", json.dumps(payload)))
        except Exception as e:
            log_warn(f"web pinned answer {cmd!r}: {e!r}", tag="WEB")

    entry = _HANDLERS.get(cmd)
    if entry is None:
        answer(False, f"unknown command {cmd!r}")
        return (True, None)
    fn, background = entry
    from . import startup_probe as _probe

    if background:
        _t0 = time.perf_counter()

        def done(fut):
            if _probe._s["on"]:
                _probe._log(f"t={_probe._ms():.0f}ms pinned {cmd} (background) answered after {(time.perf_counter() - _t0) * 1000:.0f}ms")
            try:
                answer(True, fut.result())
            except Exception as e:
                log_error(f"web pinned {cmd!r}: {e!r}")
                answer(False, repr(e))

        from .ui_share import ui_first

        mw.taskman.run_in_background(lambda: ui_first(fn, **args), on_done=done)
    else:
        try:
            answer(True, _probe.timed(f"pinned {cmd}", fn, **args))
        except Exception as e:
            log_error(f"web pinned {cmd!r}: {e!r}")
            answer(False, repr(e))
    return (True, None)
