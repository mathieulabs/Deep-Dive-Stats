# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Short guided tour of the pinned widgets on Anki's main screen.

It starts once by itself, the first time pinned widgets are on screen (also after an
update, for those who already had the add-on), and again from the Deep Dive menu. Each
step lights up the part of the screen it talks about; the tour waits for Next, Back or
Skip (or Esc) and never closes by itself. Steps whose target is not on screen are skipped.

The first steps show what the screen can become: other widgets, other layouts, other
colors, a text widget. They do it for real, by saving a demo layout, and put the user's own
settings file back, byte for byte, when the demo steps are left or the tour ends. A copy of
that file is kept in user_files until then, so a crash in the middle of the demo is undone
at the next start."""

import json
import os
import time
import weakref

from aqt.qt import (
    QApplication,
    QColor,
    QEvent,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPainter,
    QPainterPath,
    QPen,
    QPoint,
    QPushButton,
    QRect,
    QPointF,
    QRectF,
    QTimer,
    QVBoxLayout,
    QWidget,
    Qt,
)

from ...animations.effect_guard import effect_nested
from ...logic.logger import log_info, log_swallowed
from ...logic.user_state import load_state, save_state, state_path
from ....i18n import tr, tr_name
from ....qss import set_qss

_KEY = "guided_tour"
_FIRST_DELAY_MS = 2500
_RETRY_MS = 4000
_MAX_TRIES = 40

_done = None
_pinned = weakref.WeakSet()
_tour = None
_scheduled = False
_tries = 0
_restored = False


# -- state ---------------------------------------------------------------------------

def is_running():
    """Whether the tour is on screen (the hover helpers stay hidden meanwhile)."""
    return _tour is not None


def _load():
    return load_state("tips.json")


def _save(state):
    save_state("tips.json", state)


def _is_done():
    global _done
    if _done is None:
        _done = bool(_load().get(_KEY))
    return _done


def _mark_done():
    global _done
    _done = True
    state = _load()
    if not state.get(_KEY):
        state[_KEY] = True
        _save(state)


# -- targets -------------------------------------------------------------------------

def _visible(w):
    try:
        return w is not None and w.isVisible() and w.width() > 20 and w.height() > 20
    except RuntimeError:
        return False


def _pinned_off():
    try:
        from ....config import pinned_widgets_disabled
        return pinned_widgets_disabled()
    except Exception:
        return False


def _pinned_widgets():
    # Only the widgets shown now: in the pinned area of the screen (not one still a window
    # of its own while being built, nor one kept from an earlier layout until it is
    # deleted: the light took those in on a layout's first showing).
    overlay = None
    try:
        from ..pinned.main_menu.manager import MainMenuWidgetManager
        if MainMenuWidgetManager.instance_exists():
            overlay = MainMenuWidgetManager.instance()._overlay
    except Exception:
        overlay = None
    out = []
    for w in list(_pinned):
        try:
            if not _visible(w) or w.isWindow():
                continue
            if overlay is not None and not overlay.isAncestorOf(w):
                continue
            out.append(w)
        except RuntimeError:
            continue
    return out


def _is_chart(w):
    return getattr(w, "_dd_more_button", None) is not None and type(w).__name__ != "StatCardWidget"


def _rect_in(win, w):
    return QRect(w.mapTo(win, QPoint(0, 0)), w.size())


def _target_chart(win):
    charts = [w for w in _pinned_widgets() if _is_chart(w)]
    return _rect_in(win, charts[0]) if charts else None


def _pick_zoom_chart():
    """The chart the zoom step drags on: Activity first (one bar per day, the drag zone
    maps right onto the days), else the first chart that zooms."""
    found = [
        c for w in _pinned_widgets() for c in w.findChildren(QWidget)
        if hasattr(c, "set_zoom_range") and type(c).__name__ != "HeatmapWidget" and _visible(c)
    ]
    found.sort(key=lambda c: 0 if type(c).__name__.startswith("Activity") else 1)
    return found[0] if found else None


def _target_zoom(win):
    c = _pick_zoom_chart()
    if c is None:
        return None
    w = next((w for w in _pinned_widgets() if w.isAncestorOf(c)), None)
    return _rect_in(win, w if w is not None else c)


def _target_all(win):
    rects = [_rect_in(win, w) for w in _pinned_widgets()]
    if not rects:
        return None
    r = rects[0]
    for x in rects[1:]:
        r = r.united(x)
    return r


def _scene_loading(anims=True):
    """True while a pinned widget still waits for its data (it can still change size)."""
    try:
        from ..pinned.main_menu.manager import MainMenuWidgetManager
        if MainMenuWidgetManager.instance()._pending_updates:
            return True
    except Exception:
        pass
    from aqt.qt import QAbstractAnimation
    for w in list(_pinned):
        try:
            if not w.isVisible():
                continue
            if getattr(w, "_is_loading", False):
                return True
            # A chart still drawing itself in (its data just came): wait for its final look.
            for c in (w.findChildren(QWidget) if anims else ()):
                anim = getattr(c, "animation", None) if getattr(c, "_is_chart_anim_target", False) else None
                if anim is not None and anim.state() == QAbstractAnimation.State.Running:
                    return True
        except RuntimeError:
            continue  # already deleted
    return False


def _scene_built():
    """True once the pinned area shows exactly the widgets of the settings now in force: a
    rebuild can come a little after the settings change, and until then the old widgets
    stand still (and looked settled: the light then went around the old layout)."""
    try:
        from ..pinned import WidgetRegistry
        from ..pinned.main_menu.manager import MainMenuWidgetManager
        m = MainMenuWidgetManager.instance()
        wanted = {d.get("id") for d in WidgetRegistry.get_all()
                  if m._widget_allowed_in_context(d, m._current_deck_id)}
    except Exception:
        return True
    shown = {getattr(w, "widget_id", None) for w in _pinned_widgets()}
    shown.discard(None)
    return not wanted or shown == wanted


def _menu_target():
    """The widget the right-click step uses: the calendar when it is pinned (the one
    people least expect a menu on), else the first chart."""
    charts = [w for w in _pinned_widgets() if _is_chart(w)]
    return next((w for w in charts if _is_heatmap(w)), charts[0] if charts else None)


# The widgets the add step pins for a moment, by scene ("add:chart", "add:stat").
_add_demo_pins = {}
# The id of the widget whose menu the add step shows at this moment (the light goes on it).
_add_menu_widget = [None]


def _add_anchor(which):
    """The widget the add step opens its menu on: a chart (not the calendar) to add a chart,
    a stat card to add a stat card. Add Widget puts the new one right after it."""
    ws = _pinned_widgets()
    if which == "stat":
        stat = next((w for w in ws if type(w).__name__ == "StatCardWidget"), None)
        if stat is not None:
            return stat
    return _span_widget() or next((w for w in ws if _is_chart(w) and not _is_heatmap(w)), None) or _menu_target()


def _added_widget():
    """The widget the add step just pinned (its scene is shown), or None."""
    scene = _demo["scene"] or ""
    pin = _add_demo_pins.get(scene[4:]) if scene.startswith("add:") else None
    if pin is None:
        return None
    return next((w for w in _pinned_widgets() if getattr(w, "widget_id", None) == pin["id"]), None)


def _target_add(win):
    """The add step's light: the widget just added while it shows, else the one whose menu
    opens."""
    w = _added_widget()
    if w is not None:
        return _rect_in(win, w)
    # By id: the screen is rebuilt between the two menus (the added widget shown, then
    # taken away), so the widget objects of the first build are gone.
    wid = _add_menu_widget[0]
    if wid == "plus":
        rect = getattr(_tour, "_plus_rect", None)  # the "+" at the end of a line
        return QRect(rect).adjusted(-6, -6, 6, 6) if rect is not None else None
    w = next((x for x in _pinned_widgets() if wid and getattr(x, "widget_id", None) == wid), None)
    if w is not None:
        return _rect_in(win, w)
    w = _add_anchor("chart")
    return _rect_in(win, w) if w is not None else None


def _add_choices():
    """A chart and a stat card the user has not pinned yet (Retention and Streak first),
    for the add step: (chart type, stat key), each None if there is no such one."""
    from ..pinned.main_menu.ui.add_widget_menu import CHARTS, STAT_GROUPS
    from ...ui import Config
    from ..pinned import WidgetRegistry

    pins = WidgetRegistry.get_all()
    types = {d.get("type") for d in pins}
    stats = {d.get("stat_key") for d in pins if d.get("type") == "stat_card"}
    order = ["retention", "hourly", "future_due", "added", "difficulty", "stability"]
    order += [t for t, _l in CHARTS if t not in order and t != "heatmap"]
    chart = next((t for t in order if t not in types), None)
    keys = []
    for group, attrs in STAT_GROUPS:
        for a in attrs:
            k = getattr(Config, a, None)
            if k is not None:
                keys.append(k)
    first = [getattr(Config, "DASH_SHOW_STREAK", None), getattr(Config, "DASH_SHOW_REVIEWS_PER_DAY", None),
             getattr(Config, "DASH_SHOW_RET_ALL", None)]
    stat = next((k for k in first + keys if k and k not in stats), None)
    return chart, stat


def _target_menu_widget(win):
    w = _menu_target()
    return _rect_in(win, w) if w is not None else None


def _is_heatmap(w):
    return type(w).__name__ == "HeatmapWidget" or any(
        type(c).__name__ == "HeatmapWidget" for c in w.findChildren(QWidget)
    )


def _drag_pair():
    """Two charts side by side (not the calendar) for the move demo: Activity and Card
    Counts when they are there."""
    charts = [w for w in _pinned_widgets() if _is_chart(w) and not _is_heatmap(w)]
    if len(charts) < 2:
        return None
    win = charts[0].window()
    rows = {}
    for w in charts:
        rows.setdefault(round(w.mapTo(win, QPoint(0, 0)).y() / 20), []).append(w)
    for row in sorted(rows):
        same = sorted(rows[row], key=lambda w: w.mapTo(win, QPoint(0, 0)).x())
        if len(same) >= 2:
            return same[0], same[1]
    return charts[0], charts[1]


def _rounded_grab(w):
    """A picture of a widget with its round corners: grab() fills the corners square."""
    import re
    from aqt.qt import QPixmap
    pm = w.grab()
    radius = 14
    try:
        found = re.findall(r"border-radius:\s*(\d+)px", w.styleSheet() or "")
        if found:
            radius = int(found[0])
    except Exception:
        pass
    out = QPixmap(pm.size())
    out.setDevicePixelRatio(pm.devicePixelRatio())
    out.fill(Qt.GlobalColor.transparent)
    p = QPainter(out)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    clip = QPainterPath()
    dpr = max(1.0, pm.devicePixelRatio())
    clip.addRoundedRect(QRectF(0, 0, pm.width() / dpr, pm.height() / dpr), radius, radius)
    p.setClipPath(clip)
    p.drawPixmap(0, 0, pm)
    p.end()
    return out


def _target_menu(win):
    from aqt.qt import QMenuBar
    try:
        for bar in win.findChildren(QMenuBar):
            if bar.isNativeMenuBar() or not bar.isVisible():
                continue
            for act in bar.actions():
                if "Deep Dive" in act.text().replace("&", ""):
                    g = bar.actionGeometry(act)
                    if g.isValid() and g.width() > 0:
                        return QRect(bar.mapTo(win, g.topLeft()), g.size())
    except RuntimeError:
        pass
    return None


def _span_widget():
    """The chart whose time span the span step changes: Activity when it is pinned."""
    charts = [w for w in _pinned_widgets() if _is_chart(w) and not _is_heatmap(w)]
    # Charts over time first: their look changes with the span (card counts would not).
    for names in (("ActivityChart", "ActivityStackedChart"), ("RetentionChart",), ("AddedChartWidget",)):
        for w in charts:
            if any(type(c).__name__ in names for c in w.findChildren(QWidget)):
                return w
    return charts[0] if charts else None


def _span_chip(w):
    """The labels of the chart (card_chips), when its period label shows (else the
    right-click menu is used)."""
    chips = getattr(w, "_dd_card_chips", None)
    try:
        if chips is not None and chips.widget_def and chips.span.isVisible() and chips.span.label:
            return chips
    except RuntimeError:
        pass
    return None


def _span_shown_widget():
    """The chart the span step changes, as it is now."""
    ws = [w for w in _pinned_widgets() if _span_id and getattr(w, "widget_id", None) == _span_id[0]]
    return ws[0] if ws else None


def _span_choices(w):
    """The time spans the span step goes through: past month, year and everything when its
    Time Span menu has them (it lists the user's own tabs), the one shown now left out."""
    from ..pinned import WidgetRegistry

    current = next((d.get("time_span") for d in WidgetRegistry.get_all() if d.get("id") == getattr(w, "widget_id", None)), None)
    values = _menu_span_values(w)
    return [v for v in (2, 3, -1, 8, 0) if v in values and v != current][:3]


def _menu_span_values(w):
    """The time spans listed in the widget's Time Span menu."""
    from aqt.qt import QMenu
    captured = []
    had_own = "exec" in QMenu.__dict__
    saved = QMenu.__dict__.get("exec")

    def restore():
        if had_own:
            setattr(QMenu, "exec", saved)
        elif "exec" in QMenu.__dict__:
            delattr(QMenu, "exec")

    def fake_exec(self, *a, **k):
        captured.append(self)
        return None

    try:
        from ..pinned.main_menu.manager import MainMenuWidgetManager
        QMenu.exec = fake_exec
        try:
            MainMenuWidgetManager.instance()._show_context_menu(w, w.widget_id, QPoint(30, 20))
        finally:
            restore()
        if not captured:
            return []
        top = captured[0]
        values = []
        for a in top.actions():
            if a.menu() is not None and a.text().replace("&", "") == tr("Time Span"):
                for b in a.menu().actions():
                    if b.isCheckable() and isinstance(b.data(), int):
                        values.append(b.data())
        top.deleteLater()
        return values
    except Exception:
        restore()
        log_swallowed()
        return []


def _target_span(win):
    ws = [w for w in _pinned_widgets() if _span_id and getattr(w, "widget_id", None) == _span_id[0]]
    return _rect_in(win, ws[0]) if ws else _target_chart(win)


def _target_text(win):
    texts = [w for w in _pinned_widgets() if getattr(w, "wtype", None) == "text_label"]
    return _rect_in(win, texts[0]) if texts else _target_all(win)


def _steps():
    """(demo scene or None, target, text, live action or None) of each step."""
    add = tr("Add Widget...").rstrip(".…")
    return [
        (None, _target_all, tr("Here are a few ways to set up this screen."), None),
        (_LAYOUT_SCENES[0], _target_all, tr(
            "Any chart or stat from the Deep Dive window can go here, as many as you like, in any order."
        ), "layouts"),
        (None, _target_add, tr(
            "To add one, click the + that shows at the end of a line (or between two lines), or right "
            "click a widget and choose {add}. In the Deep Dive window, the pin next to a chart's title "
            "puts it here.", add=add,
        ), "add"),
        (_theme_scenes()[0], _target_all, tr(
            "You can change the colors too: one theme for every widget, or a color per chart or stat "
            "(right click, then its color or {settings}).", settings=tr("Settings"),
        ), "themes"),
        (_TEXT_SCENES[0], _target_text, tr(
            "The text widget lets you write your own sentence with live stats in it, like today's reviews, "
            "your streak or your retention. Right click, then {edit}.", edit=tr("Edit Text and Settings...").rstrip(".…"),
        ), "texts"),
        (None, _target_menu_widget, tr("Right click a widget (or click ⋯) for all its options."), "menu"),
        (None, _target_span, tr(
            "Each widget can have its own deck and time span. Click the label next to a chart's title, "
            "or right click, then {decks} or {span}.",
            decks=tr("Select Decks...").rstrip(".…"), span=tr("Time Span"),
        ), "spans"),
        (None, _target_zoom, tr(
            "Drag across a chart to zoom in (or Ctrl + mouse wheel). The ↺ button goes back to the full view."
        ), "zoom"),
        (None, _target_all, tr(
            "Drag a widget onto another line, or between two lines to start a new one. Use the ⠿ handle "
            "on the left of a line to move the whole line, and drag the space between two lines to resize it."
        ), "swap"),
    ]


_BASE_LAYOUT_SCENES = ("layout1", "layout2", "layout3", "layout4", "layout5", "layout6")
# The all years heatmap (no space between the years): only shown with at least
# _YEARS_SCENE_MIN_YEARS calendar years of reviews, or it would look like the year view.
_YEARS_SCENE = "layout7"
_YEARS_SCENE_MIN_YEARS = 2
_YEARS_SCENE_FOLD = 3  # the older years folded: the example stays about as tall as the others
_LAYOUT_SCENES = list(_BASE_LAYOUT_SCENES)


def _review_years():
    """Calendar years with reviews in the open collection (0 when it cannot tell)."""
    try:
        from ..charts.heatmap.years_ops import collection_review_years

        return collection_review_years()
    except Exception:
        log_swallowed()
        return 0


def _refresh_layout_scenes():
    """The layouts the tour shows, for this collection (see _YEARS_SCENE)."""
    scenes = list(_BASE_LAYOUT_SCENES)
    if _review_years() >= _YEARS_SCENE_MIN_YEARS:
        # Third: most people do not watch the layouts until the last one.
        scenes.insert(2, _YEARS_SCENE)
    _LAYOUT_SCENES[:] = scenes


# Room left under the light for the examples that grow (pixels): the card does not move.
_CARD_SLACK = {"texts": 48}
# Height of the tallest layout of the layouts step, per window size: measured while the
# first step is read, so the card can sit right under it and stay there.
_layout_heights = {}
# Tallest layout seen so far, per window size: used while not all of them are measured.
_layout_partial = {}
_span_id = []
_drag_demo_id = []  # the chart the drag step moves (to a new line, to a new box)
_drag_demo_end = ["top"]  # where its new box goes: the side away from the tour's card
_drag_demo_box = []  # [box key, "top" | "bottom"]: the whole box the drag step moves
_drag_demo_swap = []  # [left id, right id]: the two charts the drag step swaps once


def _cycle_scenes(action):
    """The scenes a step goes through by itself."""
    if action == "themes":
        return _theme_scenes()
    if action == "layouts":
        return list(_LAYOUT_SCENES)
    if action == "texts":
        return list(_TEXT_SCENES)
    return []


def _theme_scenes():
    """Themes of the add-on shown in the colors step, light or dark like Anki."""
    try:
        from aqt.theme import theme_manager
        dark = bool(theme_manager.night_mode)
    except Exception:
        dark = True
    if dark:
        names = ("dark_pro", "gruvbox", "deep_ocean", "catppuccin", "void", "github", "midnight")  # github: Slate
    else:
        names = ("sunset_light", "lavender", "rose", "coral", "gruvbox_light", "solarized", "mint", "modern_light")
    return [f"theme:{n}" for n in names]


# -- demo layouts --------------------------------------------------------------------

_BACKUP_NAME = "tour_backup.json"
_demo = {"path": None, "text": None, "scene": None}


def _backup_path():
    return state_path(_BACKUP_NAME)


def _config_manager():
    from ....config import ConfigManager
    from aqt import mw
    return ConfigManager(mw)


def _write_config_text(path, text):
    from ....config import _write_file_atomic, reload_live_managers
    _write_file_atomic(path, text)
    reload_live_managers()


def _refresh_pinned():
    try:
        from ..pinned.main_menu.manager import MainMenuWidgetManager
        m = MainMenuWidgetManager.instance()
        m._last_state = None
        m._last_widget_set = None
        m.refresh(clear_cache=False)
    except Exception:
        log_swallowed()
    try:
        from ..pinned.main_menu.manager import MainMenuWidgetManager
        MainMenuWidgetManager.instance()._on_theme_change()
    except Exception:
        log_swallowed()
    try:
        # Charts kept across the rebuild keep their colors: repaint them with the new ones.
        from aqt import mw
        from ...ui.config.theme.runtime_refresh import refresh_live_data_colors
        refresh_live_data_colors(parent_dialog=mw, addon_config=_config_manager(), source="guided_tour")
    except Exception:
        log_swallowed()


def _refresh_pinned_span():
    """After a period change of the span step: the same refresh as a real one (see
    context_actions.update_span_bulk), so the chart is updated in place and animates to
    the new period instead of being built again."""
    try:
        from ..pinned.main_menu.manager import MainMenuWidgetManager

        m = MainMenuWidgetManager.instance()
        m._last_state = None
        m.refresh()
    except Exception:
        log_swallowed()


def _stat(stat_key, **extra):
    from ..stats_cards.logic.model import get_stat_card_name
    d = {"id": f"tour-{stat_key}", "type": "stat_card", "label": get_stat_card_name(stat_key), "stat_key": stat_key}
    d.update(extra)
    return d


def _chart(wtype, **extra):
    from ...ui.config.widgets.label_defaults import DEFAULT_LABELS
    d = {"id": f"tour-{wtype}", "type": wtype, "label": DEFAULT_LABELS.get(wtype, wtype), "stat_key": None}
    d.update(extra)
    return d


def _demo_text_templates():
    """A few things the text widget can show (its variables are filled in live)."""
    center = '<p align="center">'
    return [
        center + '<span style=" font-size:15pt; font-weight:700;">' + tr("{reviews:Today} reviews today")
        + '</span><br/><span style=" font-size:11pt;">'
        + tr("Streak: {streak} days · young retention: {ret_young}") + "</span></p>",
        center + '<span style=" font-size:26pt; font-weight:800;">{streak}</span><br/>'
        + '<span style=" font-size:11pt;">' + tr("days in a row") + "</span></p>",
        center + '<span style=" font-size:13pt;">' + tr("This week: {reviews:week} reviews in {total_time:week}")
        + "</span></p>",
        '<p><span style=" font-size:12pt; font-weight:600;">'
        + tr("{cards_mature} mature cards · mature retention {ret_mat}") + "</span></p>",
        center + '<span style=" font-size:24pt; font-weight:800;">{reviews:month}</span><br/>'
        + '<span style=" font-size:11pt;">' + tr("reviews this month") + "</span></p>",
        center + '<span style=" font-size:12pt;">'
        + tr("{cards_total} cards · {active_days} active days") + "</span></p>",
    ]


_TEXT_SCENES = ("text1", "text2", "text3", "text4", "text5", "text6")


def _scene_config(name, base):
    """The settings of a demo scene, made from the user's own (base)."""
    from ...ui import Config

    cfg = json.loads(json.dumps(base))
    pins = list(cfg.get(Config.PINNED_WIDGETS) or [])
    if name.startswith("layout"):
        # The examples have their own boxes: the spaces changed by hand in the user's
        # layout (Config.PINNED_GAPS) would land on them anywhere. The usual spaces there.
        cfg[Config.PINNED_GAPS] = {}
    if name == "layout1":
        cfg[Config.PINNED_WIDGETS] = [
            _stat("Dash_Show_Due_Today"), _stat("Dash_Show_Reviews_Per_Day"),
            _stat("Dash_Show_Ret_Young"), _stat("Dash_Show_Longest_Streak"),
            _chart("future_due", time_span=2), _chart("hourly", time_span=2), _chart("distribution", time_span=2),
        ]
    elif name == "layout2":
        cfg[Config.PINNED_WIDGETS] = [
            _chart("heatmap", heatmap_mode="continuous", chart_box=1),
            _stat("Dash_Show_Cards_Total"), _stat("Dash_Show_Cards_Mature"),
            _stat("Dash_Show_Active_Days", time_span=-1), _stat("Dash_Show_Best_Day"),
            _chart("added", time_span=3), _chart("review_intervals"), _chart("card_counts", time_span=-1),
        ]
    elif name == "layout3":
        cfg[Config.PINNED_WIDGETS] = [
            _stat("Dash_Show_Time", time_span=-1), _stat("Dash_Show_Time_Per_Day"),
            _stat("Dash_Show_Avg_Time"), _stat("Dash_Show_Ret_True"),
            _chart("activity", time_span=3, show_time_axis=True, show_breakdown=True),
            _chart("retention", time_span=8, fit_to_data=True),
        ]
    elif name == "layout4":
        cfg[Config.PINNED_WIDGETS] = [
            _stat("Dash_Show_Cards_New"), _stat("Dash_Show_Cards_Learning"),
            _stat("Dash_Show_Cards_Young"), _stat("Dash_Show_Cards_Mature"),
            _chart("card_counts", time_span=-1), _chart("stability"),
            _chart("difficulty"), _chart("retrievability"),
        ]
    elif name == "layout5":
        cfg[Config.PINNED_WIDGETS] = [
            _stat("Dash_Show_Streak"), _stat("Dash_Show_Longest_Streak"),
            _stat("Dash_Show_Active_Days", time_span=-1), _stat("Dash_Show_Days_Learned"),
            _chart("heatmap", heatmap_mode="year", chart_box=1),
            _chart("activity", time_span=1, show_breakdown=False),
        ]
    elif name == _YEARS_SCENE:
        # Every year at once, one under the other with no space: the all years view and its
        # right-click option. The older years folded, so the example stays short.
        cfg[Config.HEATMAP_YEARS_NO_GAP] = True
        cfg[Config.HEATMAP_YEARS_FOLD] = _YEARS_SCENE_FOLD
        cfg[Config.PINNED_WIDGETS] = [
            _stat("Dash_Show_Reviews", time_span=-1), _stat("Dash_Show_Active_Days", time_span=-1),
            _stat("Dash_Show_Longest_Streak"), _stat("Dash_Show_Days_Learned"),
            _chart("heatmap", heatmap_mode="years", chart_box=1),
        ]
    elif name == "layout6":
        cfg[Config.PINNED_WIDGETS] = [
            _stat("Dash_Show_Again"), _stat("Dash_Show_Lapses"),
            _stat("Dash_Show_Avg_Retrievability"), _stat("Dash_Show_Backlog"),
            _chart("distribution", time_span=-1), _chart("hourly", time_span=-1),
            _chart("future_due", time_span=3),
        ]
    elif name.startswith("span:") and _span_id:
        value = int(name.split(":", 1)[1])
        new_pins = []
        for w in pins:
            w = dict(w)
            if w.get("id") == _span_id[0]:
                w["time_span"] = value
                # A new token, as a real period change sets: the chart animates to it.
                w["_timespan_token"] = int(time.time() * 1000)
            new_pins.append(w)
        cfg[Config.PINNED_WIDGETS] = new_pins
    elif name.startswith("add:") and name[4:] in _add_demo_pins:
        # The add step: the widget picked in the menu, right after the one whose menu opened
        # (as Add Widget does).
        from ..pinned.store.registry import place_after

        pin = dict(_add_demo_pins[name[4:]])
        cfg[Config.PINNED_WIDGETS] = place_after(pins, pin, pin.pop("_after", None))
    elif name.startswith("theme:"):
        # One of the add-on's themes for the pinned widgets alone (their own theme).
        cfg.update({
            Config.PINNED_USE_ACTIVE_THEME: True,
            Config.PINNED_USE_SEPARATE_THEME: True,
            Config.PINNED_THEME_PRESET: name.split(":", 1)[1],
            Config.PINNED_THEME_IS_CUSTOM: False,
            Config.PINNED_THEME_CUSTOM_COLORS: {},
            Config.PINNED_THEME_CUSTOM_BASE_MODE: None,
        })
    elif name in ("drag:newline", "drag:newbox") and _drag_demo_id:
        cfg[Config.PINNED_WIDGETS] = _dragged_pins(name, pins, cfg)
    elif name == "drag:movebox" and _drag_demo_box:
        _move_demo_box(cfg)
    elif name == "drag:swap" and len(_drag_demo_swap) == 2:
        ids = [w.get("id") for w in pins]
        if all(i in ids for i in _drag_demo_swap):
            ia, ib = ids.index(_drag_demo_swap[0]), ids.index(_drag_demo_swap[1])
            pins = list(pins)
            pins[ia], pins[ib] = pins[ib], pins[ia]
            cfg[Config.PINNED_WIDGETS] = pins
    elif name.startswith("text"):
        template = _demo_text_templates()[int(name[4:] or 1) - 1]
        text = [w for w in pins if w.get("type") == "text_label"]
        if text:
            new_pins = []
            for w in pins:
                w = dict(w)
                if w.get("id") == text[0].get("id"):
                    w["template"] = template
                new_pins.append(w)
        else:
            new_pins = [{"id": "tour-text", "type": "text_label", "label": "Text Widget", "stat_key": None,
                         "template": template, "chart_box": 1, "text_box": 0}] + pins
        cfg[Config.PINNED_WIDGETS] = new_pins
    if name.startswith("layout"):
        # Own ids per layout: a widget of one layout is never reused, half updated, by the
        # next one (the same chart with another span or toggle showed the old one's state).
        for w in cfg[Config.PINNED_WIDGETS]:
            w["id"] = f"{w['id']}-{name}"
    return cfg


def _chart_box(w):
    try:
        return max(0, int(w.get("chart_box", 0) or 0))
    except (TypeError, ValueError):
        return 0


def _row(w):
    try:
        return max(0, int(w.get("row_num", 0) or 0))
    except (TypeError, ValueError):
        return 0


def _is_chart_def(w):
    return w.get("type") not in ("stat_card", "text_label")


def _dragged_pins(name, pins, cfg):
    """The drag step's results: the chart dropped between its line and the next one (alone
    on a new line there), or above all the boxes (alone in a new box at the top)."""
    from ...ui import Config
    from ..pinned.main_menu.block_order import charts_section_key, normalize_block_order

    wid = _drag_demo_id[0]
    cur = next((w for w in pins if w.get("id") == wid), None)
    if cur is None:
        return pins
    box, row = _chart_box(cur), _row(cur)
    out = []
    if name == "drag:newline":
        for w in pins:
            w = dict(w)
            if w.get("id") == wid:
                w["row_num"] = row + 1
                w.pop("col_offset", None)
            elif _is_chart_def(w) and _chart_box(w) == box and _row(w) > row:
                w["row_num"] = _row(w) + 1
            out.append(w)
        return out
    used = [_chart_box(w) for w in pins if _is_chart_def(w)]
    new_id = (max(used) + 1) if used else 1
    for w in pins:
        w = dict(w)
        if w.get("id") == wid:
            w["chart_box"] = new_id
            w.pop("row_num", None)
            w.pop("col_offset", None)
        out.append(w)

    def boxes(kind):
        if kind == "stat":
            return sorted({int(w.get("stat_box", 0) or 0) for w in out if w.get("type") == "stat_card"})
        if kind == "text":
            return sorted({int(w.get("text_box", w.get("chart_box", 0)) or 0) for w in out if w.get("type") == "text_label"})
        return sorted({_chart_box(w) for w in out if _is_chart_def(w)})

    order = normalize_block_order(
        cfg.get(Config.PINNED_BLOCK_ORDER), stats_boxes=boxes("stat"), chart_boxes=boxes("chart"),
        text_boxes=boxes("text"),
    )
    key = charts_section_key(new_id)
    order = [k for k in order if k != key]
    cfg[Config.PINNED_BLOCK_ORDER] = order + [key] if _drag_demo_end[0] == "bottom" else [key] + order
    return out


def _move_demo_box(cfg):
    """The drag step's whole-box move: that box first or last."""
    from ...ui import Config
    from ..pinned.main_menu.block_order import normalize_block_order

    pins = cfg.get(Config.PINNED_WIDGETS) or []
    order = normalize_block_order(
        cfg.get(Config.PINNED_BLOCK_ORDER),
        stats_boxes=sorted({int(w.get("stat_box", 0) or 0) for w in pins if w.get("type") == "stat_card"}),
        chart_boxes=sorted({_chart_box(w) for w in pins if _is_chart_def(w)}),
        text_boxes=sorted({int(w.get("text_box", w.get("chart_box", 0)) or 0) for w in pins if w.get("type") == "text_label"}),
    )
    key, where = _drag_demo_box
    order = [k for k in order if k != key]
    cfg[Config.PINNED_BLOCK_ORDER] = order + [key] if where == "bottom" else [key] + order


def _apply_scene(name):
    """Show a demo scene (None: the user's own settings again). False when not possible."""
    if name == _demo["scene"]:
        return True
    try:
        if _demo["text"] is None:
            if name is None:
                return True
            cm = _config_manager()
            path = cm._config_path
            with open(path, encoding="utf-8") as f:
                text = f.read()
            json.loads(text)  # only a readable file is used as the base
            with open(_backup_path(), "w", encoding="utf-8") as f:
                json.dump({"path": path, "text": text}, f)
            _demo["path"], _demo["text"] = path, text
        if name is None:
            _write_config_text(_demo["path"], _demo["text"])
        else:
            cfg = _scene_config(name, json.loads(_demo["text"]))
            _write_config_text(_demo["path"], json.dumps(cfg, indent=4, ensure_ascii=False))
        _demo["scene"] = name
        if name is not None and name.startswith("span:"):
            _refresh_pinned_span()
        else:
            _refresh_pinned()
        return True
    except Exception:
        log_swallowed()
        return False


def _end_demo():
    """Put the user's settings back and forget the copy."""
    if _demo["text"] is not None:
        try:
            if _demo["scene"] is not None:
                _write_config_text(_demo["path"], _demo["text"])
                _refresh_pinned()
        except Exception:
            log_swallowed()
    _demo.update(path=None, text=None, scene=None)
    try:
        os.remove(_backup_path())
    except FileNotFoundError:
        pass
    except Exception:
        log_swallowed()


def end_for_profile_close(*_args):
    """The profile closes (profile switch, Anki quits) during the tour: the user's own
    settings go back to their file at once, before the next profile or a later start reads
    it, and the tour goes away. No rebuild: the screen is going away."""
    global _tour
    tour, _tour = _tour, None
    if _demo["text"] is not None:
        try:
            if _demo["scene"] is not None:
                _write_config_text(_demo["path"], _demo["text"])
            _demo.update(path=None, text=None, scene=None)
            os.remove(_backup_path())
        except FileNotFoundError:
            pass
        except Exception:
            log_swallowed()
    if tour is not None:
        try:
            tour._top_timer.stop()
            tour._action_timer.stop()
            tour._win.removeEventFilter(tour)
            tour.hide()
            tour.deleteLater()
        except RuntimeError:
            pass
        except Exception:
            log_swallowed()


def restore_after_crash():
    """A demo that did not end (Anki closed or crashed during it): put the settings back."""
    if _tour is not None or _demo["text"] is not None:
        return
    path = _backup_path()
    if not os.path.exists(path):
        return
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if data.get("path") and isinstance(data.get("text"), str):
            json.loads(data["text"])
            _write_config_text(data["path"], data["text"])
            QTimer.singleShot(0, _refresh_pinned)
        os.remove(path)
    except Exception:
        log_swallowed()


def _menu_picture(widget, names=None):
    """Pictures of the widget's real right-click menu (built, not shown): as it opens, then
    with its settings entry under the mouse. Returns (plain, highlighted, entry rect)."""
    from aqt.qt import QMenu
    captured = []
    # The class's own entry, put back as it was: QMenu.exec read from the class is an
    # unbound function, and putting that back would break every menu afterwards.
    had_own = "exec" in QMenu.__dict__
    saved = QMenu.__dict__.get("exec")

    def restore():
        if had_own:
            setattr(QMenu, "exec", saved)
        elif "exec" in QMenu.__dict__:
            delattr(QMenu, "exec")

    def fake_exec(self, *a, **k):
        captured.append(self)
        return None

    try:
        from ..pinned.main_menu.manager import MainMenuWidgetManager
        QMenu.exec = fake_exec
        try:
            MainMenuWidgetManager.instance()._show_context_menu(widget, widget.widget_id, QPoint(30, 20))
        finally:
            restore()
        if not captured:
            return None
        menu = captured[0]
        menu.ensurePolished()
        menu.adjustSize()
        plain = menu.grab()
        if names is None:
            names = {tr("Settings"), tr("Edit Text and Settings...")}
        act = next((x for x in menu.actions() if x.text() in names), None)
        lit, rect = plain, None
        if act is not None:
            menu.setActiveAction(act)
            lit = menu.grab()
            rect = menu.actionGeometry(act)
        menu.deleteLater()
        return plain, lit, rect
    except Exception:
        restore()
        log_swallowed()
        return None


def _cascade_pictures(widget, path):
    """Pictures of the widget's real right-click menu and its submenus along a path of
    entries (built, never shown): [(picture with the entry lit, entry rect)] per level.
    An entry that is not found is the level's first plain one."""
    from aqt.qt import QMenu
    captured = []
    had_own = "exec" in QMenu.__dict__
    saved = QMenu.__dict__.get("exec")

    def restore():
        if had_own:
            setattr(QMenu, "exec", saved)
        elif "exec" in QMenu.__dict__:
            delattr(QMenu, "exec")

    def fake_exec(self, *a, **k):
        captured.append(self)
        return None

    try:
        from ..pinned.main_menu.manager import MainMenuWidgetManager
        QMenu.exec = fake_exec
        try:
            MainMenuWidgetManager.instance()._show_context_menu(widget, widget.widget_id, QPoint(30, 20))
        finally:
            restore()
        if not captured:
            return []
        top = menu = captured[0]
        levels = []
        for name in path:
            if menu is None:
                break
            menu.ensurePolished()
            menu.adjustSize()
            acts = [a for a in menu.actions() if a.isVisible() and not a.isSeparator()]
            if callable(name):
                act = next((a for a in acts if name(a)), None)
            else:
                act = next((a for a in acts if a.text().replace("&", "") == name), None)
            if act is None:
                act = next((a for a in acts if a.menu() is None), None)
            if act is None:
                break
            menu.setActiveAction(act)
            levels.append((menu.grab(), menu.actionGeometry(act)))
            menu = act.menu()
        top.deleteLater()
        return levels
    except Exception:
        restore()
        log_swallowed()
        return []


def _pointer_pixmap():
    """A plain arrow pointer, white with a dark edge (reads on any background)."""
    from aqt.qt import QPixmap, QPolygonF, QPointF
    pm = QPixmap(20, 26)
    pm.fill(QColor(0, 0, 0, 0))
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    poly = QPolygonF([QPointF(1, 1), QPointF(1, 20), QPointF(6, 15), QPointF(10, 24),
                      QPointF(13, 23), QPointF(9, 14), QPointF(16, 14)])
    pen = QPen(QColor(20, 20, 20))
    pen.setWidthF(1.4)
    p.setPen(pen)
    p.setBrush(QColor(255, 255, 255))
    p.drawPolygon(poly)
    p.end()
    return pm


def _settings_picture(widget):
    """A picture of the widget's settings window (built, never shown)."""
    try:
        from ...ui.config import WidgetSettingsDialog
        from ....config import set_live_config_override
        from ..pinned import WidgetRegistry
        from ..pinned.main_menu.manager import MainMenuWidgetManager

        wdef = next((d for d in WidgetRegistry.get_all() if d.get("id") == widget.widget_id), None)
        if wdef is None:
            return None
        cfg = MainMenuWidgetManager.instance()._get_config_manager().config
        dlg = WidgetSettingsDialog(dict(wdef), parent=widget, global_config=cfg)
        try:
            dlg.resize(560, 620)
            dlg.ensurePolished()
            return dlg.grab()
        finally:
            set_live_config_override(None)
            dlg.deleteLater()
    except Exception:
        log_swallowed()
        return None


# -- overlay -------------------------------------------------------------------------

class _StepDots(QWidget):
    """A dot per step of the tour: the current one long and colored, the seen ones filled,
    the others as rings. A click on a dot goes to that step."""

    D, GAP, CUR = 7, 6, 16

    def __init__(self, parent, accent, on_pick):
        super().__init__(parent)
        self._accent = QColor(accent)
        self._on_pick = on_pick
        self._i, self._n = 0, 1
        self._hover = -1
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_state(self, i, n):
        self._i, self._n = i, max(1, n)
        w = (self._n - 1) * (self.D + self.GAP) + self.CUR
        self.setFixedSize(w + 2, self.D + 6)
        self.update()

    def _rects(self):
        x, out = 1, []
        y = (self.height() - self.D) / 2.0
        for k in range(self._n):
            w = self.CUR if k == self._i else self.D
            out.append(QRectF(x, y, w, self.D))
            x += w + self.GAP
        return out

    def _at(self, pos):
        for k, r in enumerate(self._rects()):
            if r.adjusted(-3, -4, 3, 4).contains(QPointF(pos)):
                return k
        return -1

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        for k, r in enumerate(self._rects()):
            radius = self.D / 2.0
            if k == self._i:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(self._accent)
            elif k < self._i:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(255, 255, 255, 200 if k == self._hover else 140))
            else:
                pen = QPen(QColor(255, 255, 255, 220 if k == self._hover else 110))
                pen.setWidthF(1.2)
                p.setPen(pen)
                p.setBrush(QColor(255, 255, 255, 40) if k == self._hover else Qt.BrushStyle.NoBrush)
                r = r.adjusted(0.6, 0.6, -0.6, -0.6)
            p.drawRoundedRect(r, radius, radius)
        p.end()

    def mouseMoveEvent(self, event):
        k = self._at(event.position())
        if k != self._hover:
            self._hover = k
            self.setToolTip(tr("Quick tour · {step}/{total}", step=k + 1, total=self._n) if k >= 0 else "")
            self.update()

    def leaveEvent(self, event):
        self._hover = -1
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        k = self._at(event.position())
        if k >= 0 and k != self._i:
            self._on_pick(k)
        event.accept()


class _Tour(QWidget):
    PAD = 6

    def __init__(self, win):
        super().__init__(win)
        self._win = win
        self.setObjectName("dd_guided_tour")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        demo_ok = bool(_pinned_widgets()) and not _pinned_off()
        sw = _span_widget()
        _span_id[:] = [sw.widget_id] if sw is not None and getattr(sw, "widget_id", None) else []
        self._steps = [
            s for s in _steps()
            if (s[0] is not None and demo_ok) or (s[0] is None and s[1](win) is not None)
        ]
        self._i = 0
        self._busy = False
        self._grow = None
        self._cover = None
        self._ghosts = []
        self._hidden = []
        self._ghost_anim = None
        self._zoomed = None
        self._theme_i = 0
        self._action_timer = QTimer(self)
        self._action_timer.timeout.connect(self._on_action_timer)
        # Widgets rebuilt under the tour come up above it: put the shade back over them at
        # once, not at the next step of the tour (they would show bright for a moment).
        self._top_timer = QTimer(self)
        self._top_timer.setInterval(30)
        self._top_timer.timeout.connect(self._keep_on_top)
        self._hole_from = None
        self._hole_to = None
        from aqt.qt import QVariantAnimation, QEasingCurve
        self._hole_anim = QVariantAnimation(self)
        self._hole_anim.setStartValue(0.0)
        self._hole_anim.setEndValue(1.0)
        self._hole_anim.setDuration(180)
        self._hole_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._hole_anim.valueChanged.connect(self._on_hole_anim)
        self._hole = None
        accent = QApplication.palette().highlight().color()
        self._accent = accent if accent.isValid() else QColor("#58a6ff")

        self._card = QFrame(self)
        self._card.setObjectName("dd_tour_card")
        # Dark card with light text: reads the same on every theme.
        set_qss(self._card,
            "QFrame#dd_tour_card { background: rgba(32, 33, 38, 245); border: 1px solid rgba(255, 255, 255, 45);"
            " border-radius: 10px; }"
            "QLabel { color: #f2f2f2; background: transparent; }"
            "QLabel#dd_tour_count { color: #a8a8a8; font-size: 11px; }"
            "QPushButton { color: #e8e8e8; background: rgba(255, 255, 255, 18); border: 1px solid rgba(255, 255, 255, 40);"
            " border-radius: 6px; padding: 4px 12px; }"
            "QPushButton:hover { background: rgba(255, 255, 255, 34); }"
            "QPushButton#dd_tour_skip { background: transparent; border: none; color: #a8a8a8; padding: 4px 6px; }"
            "QPushButton#dd_tour_skip:hover { color: #ffffff; }"
            f"QPushButton#dd_tour_next {{ background: {self._accent.name()}; border: none; color: "
            f"{'#18181b' if self._accent.lightnessF() > 0.6 else '#ffffff'}; font-weight: 600; }}")
        lay = QVBoxLayout(self._card)
        lay.setContentsMargins(14, 12, 14, 10)
        lay.setSpacing(8)
        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        self._count = QLabel(tr("Quick tour"), self._card)
        self._count.setObjectName("dd_tour_count")
        head.addWidget(self._count)
        head.addStretch(1)
        # One dot per step: where the tour is, how much is left, and a click goes there.
        self._dots = _StepDots(self._card, self._accent, self._jump)
        head.addWidget(self._dots)
        lay.addLayout(head)
        self._text = QLabel(self._card)
        self._text.setWordWrap(True)
        self._text.setFixedWidth(330)
        set_qss(self._text, "font-size: 13px;")
        lay.addWidget(self._text)
        row = QHBoxLayout()
        row.setSpacing(6)
        self._skip = QPushButton(tr("Skip"), self._card)
        self._skip.setObjectName("dd_tour_skip")
        self._back = QPushButton(tr("Back"), self._card)
        self._next = QPushButton(self._card)
        self._next.setObjectName("dd_tour_next")
        for b in (self._skip, self._back, self._next):
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._skip.clicked.connect(self.close_tour)
        self._back.clicked.connect(lambda: self._go(self._i - 1))
        self._next.clicked.connect(lambda: self._go(self._i + 1))
        row.addWidget(self._back)
        row.addStretch(1)
        row.addWidget(self._skip)
        row.addWidget(self._next)
        lay.addLayout(row)

        win.installEventFilter(self)

    def has_steps(self):
        return bool(self._steps)

    def _set_hole(self, rect):
        """Move the light to rect, gliding from where it is."""
        if self._hole is None or rect is None or self._hole == rect:
            self._hole_anim.stop()
            self._hole = rect
            self.update()
            return
        self._hole_from, self._hole_to = QRect(self._hole), QRect(rect)
        self._hole_anim.stop()
        self._hole_anim.start()

    def _on_hole_anim(self, value):
        try:
            t = float(value)
            a, b = self._hole_from, self._hole_to
            if a is None or b is None:
                return
            self._hole = QRect(
                round(a.x() + (b.x() - a.x()) * t), round(a.y() + (b.y() - a.y()) * t),
                round(a.width() + (b.width() - a.width()) * t), round(a.height() + (b.height() - a.height()) * t),
            )
            self.update()
        except RuntimeError:
            pass

    def start(self):
        self._prev_focus = QApplication.focusWidget()
        self._top_timer.start()
        self.setGeometry(self._win.rect())
        self.show()
        self.raise_()
        self.setFocus()
        self._go(0)
        if self._steps and self._steps[0][0] is None and "layouts" in [s[3] for s in self._steps]:
            QTimer.singleShot(400, self._measure_layouts)

    def _measure_layouts(self, k=-1, tries=0, last=None, tallest=0):
        """While the first step is read (the screen kept as a picture): build each layout of
        the layouts step once and keep the tallest height, then put the user's back."""
        try:
            if _tour is not self or self._i != 0:
                return
            if self._busy:
                if k == -1 and tries < 20:  # the first card is still coming in
                    QTimer.singleShot(150, lambda: self._measure_layouts(-1, tries + 1))
                return
            size = (self.width(), self.height())
            if k == -1:
                if size in _layout_heights:
                    return
                self._measuring = True
                self._intro_measuring = True
                self._freeze()
                k, tries, last = 0, 0, None
                _apply_scene(_LAYOUT_SCENES[0])
            elif not getattr(self, "_measuring", False):
                return
            r = _target_all(self._win)
            # Also until its charts have their data: the first time the step shows each
            # layout, its data is then ready (no chart drawing itself in late).
            settled = (r is not None and last is not None and r == last and tries >= 2
                       and _scene_built() and not _scene_loading(anims=False))
            # Next already clicked: the person waits, so a slow layout is not waited for long.
            cap = 12 if getattr(self, "_pending_go", None) is not None else 40
            if not (settled or tries >= cap):
                QTimer.singleShot(60, lambda: self._measure_layouts(k, tries + 1, r, tallest))
                return
            if k < len(_LAYOUT_SCENES):
                if r is not None:
                    tallest = max(tallest, r.height() + 2 * self.PAD)
                    _layout_partial[size] = max(_layout_partial.get(size, 0), tallest)
                k += 1
                _apply_scene(_LAYOUT_SCENES[k] if k < len(_LAYOUT_SCENES) else None)
                QTimer.singleShot(60, lambda: self._measure_layouts(k, 0, None, tallest))
                return
            _layout_heights[size] = tallest
            self._measuring = False
            self._intro_measuring = False
            pending, self._pending_go = getattr(self, "_pending_go", None), None
            if pending is not None:
                # Next was clicked meanwhile: go on from the picture (the user's own layout
                # is back underneath), no flash of the layouts that were measured.
                self._go(pending)
                return
            self._thaw(move_card=False)
        except Exception:
            self._measuring = False
            self._intro_measuring = False
            log_swallowed()

    def _go(self, i):
        if self._busy:
            return
        if getattr(self, "_changing", False):
            # An example is being swapped in: let it finish first, then go (two rebuilds
            # on top of each other made everything crawl).
            self._pending_go = i
            return
        # The layouts are being measured behind the picture of the first step: Next does not
        # wait for it (it made the first Next slow). The measuring stops, the picture stays,
        # and the step's own scene is built under it (one demo layout may be half built).
        interrupted = bool(getattr(self, "_intro_measuring", False) and getattr(self, "_measuring", False))
        self._intro_measuring = False
        if i >= len(self._steps):
            self.close_tour()
            return
        self._gen = getattr(self, "_gen", 0) + 1
        self._measuring = False
        # Interrupted measuring: the picture over the screen stays. Taken away, it uncovered
        # the layout being measured (the all years one...) and the new picture showed it.
        self._stop_action(keep_cover=interrupted)
        self._grow = None
        self._menu_shots = None
        self._add_frames = None
        self._drop_gallery()
        self._i = max(0, i)
        scene, _target, text, _action = self._steps[self._i]
        # The card's new text shows when the card is at its new place (with the new light),
        # not before, while the screen still shows the last step.
        self._card_next = (
            self._i,
            text,
            self._i > 0,
            tr("Done") if self._i == len(self._steps) - 1 else tr("Next"),
        )
        cycling = _demo["scene"] in _cycle_scenes(_action)
        # Layouts not measured yet (Next clicked right away): no measuring now, the card
        # goes under the tallest seen so far and slides down if needed (see _place, _thaw).
        if (scene != _demo["scene"] and not cycling) or interrupted:
            # The widgets are rebuilt for the scene: the light moves to them as soon as they
            # are in place (no blank moment: the card and the old light stay meanwhile).
            self._busy = True
            for b in (self._back, self._next):
                b.setEnabled(False)
            if self._cover is None:
                self._freeze()
            self._card_waiting(True)
            _apply_scene(scene)
            self._wait_scene(0, None)
            return
        self._apply_card_text()
        self._place()
        self._start_action()

    def _card_waiting(self, on):
        """The card fades a little while the next step gets ready: the click was taken."""
        try:
            from aqt.qt import QGraphicsOpacityEffect
            if on:
                eff = QGraphicsOpacityEffect(self._card)
                eff.setOpacity(0.55)
                self._card.setGraphicsEffect(eff)
            elif self._card.graphicsEffect() is not None:
                self._card.setGraphicsEffect(None)
        except RuntimeError:
            pass

    def _jump(self, k):
        """A dot was clicked: go to that step (once the current change is done)."""
        if not self._busy:
            self._go(k)

    def _apply_card_text(self):
        self._card_waiting(False)
        pending, self._card_next = getattr(self, "_card_next", None), None
        if pending is None:
            return
        index, text, back, nxt = pending
        self._dots.set_state(index, len(self._steps))
        self._text.setText(text)
        self._fit_text()
        self._back.setVisible(back)
        self._next.setText(nxt)

    def _fit_text(self):
        """The card's text always shows whole and no taller: its height measured from the
        wrapped text with the label's own font (the layout's guess came out cut on some
        screens, and Qt's own height-for-width too tall on others)."""
        try:
            from aqt.qt import QFontMetrics
            self._text.ensurePolished()
            fm = QFontMetrics(self._text.font())
            box = fm.boundingRect(QRect(0, 0, self._text.width(), 100000),
                                  int(Qt.TextFlag.TextWordWrap), self._text.text())
            self._text.setFixedHeight(max(fm.height(), box.height()) + 2)
            self._card.adjustSize()
        except RuntimeError:
            pass

    def _wait_scene(self, tries, last):
        """Poll until the rebuilt widgets stop moving, then light them up."""
        try:
            self._keep_on_top()
            r = self._steps[self._i][1](self._win)
            settled = (r is not None and last is not None and r == last and tries >= 2
                       and _scene_built() and not _scene_loading(anims=False))
            if settled or tries >= 30:
                self._busy = False
                for b in (self._back, self._next):
                    b.setEnabled(True)
                self._thaw()
                self._start_action()
                return
            QTimer.singleShot(60, lambda: self._wait_scene(tries + 1, r))
        except RuntimeError:
            pass

    def _freeze(self):
        """Keep showing the screen as it is (a picture over everything but the card) while
        the widgets are rebuilt underneath: the new ones and their light then show together."""
        try:
            self._thaw_now()
            pm = self._win.grab()
            cover = QLabel(self)
            cover.setPixmap(pm)
            cover.setScaledContents(True)
            cover.setGeometry(self.rect())
            cover.show()
            self._cover = cover
            self._card.raise_()
        except Exception:
            log_swallowed()

    def _thaw(self, move_card=True):
        """The widgets are in place: light them up at once and fade the old picture away."""
        if move_card:
            self._apply_card_text()
        self._place(move_card=move_card, instant=True)
        if not move_card and self._hole is not None and self._card.geometry().intersects(self._hole):
            # An example grew over the card: it only slides down, never sideways, and stays
            # where it is if there is no room (it then goes over the bottom edge a little).
            card, h = self._card.geometry(), self._hole
            y = min(h.bottom() + 12, self.height() - card.height() - 8)
            if y > card.y():
                self._card.move(card.x(), y)
            self._card.raise_()
        self._show_span_badge()
        cover, self._cover = self._cover, None
        if cover is None:
            return
        try:
            from aqt.qt import QGraphicsOpacityEffect, QPropertyAnimation
            eff = QGraphicsOpacityEffect(cover)
            cover.setGraphicsEffect(eff)
            anim = QPropertyAnimation(eff, b"opacity", cover)
            anim.setStartValue(1.0)
            anim.setEndValue(0.0)
            anim.setDuration(200)
            anim.finished.connect(cover.deleteLater)
            anim.start()
        except Exception:
            cover.deleteLater()

    def _show_span_badge(self):
        """On the span step: the time span the chart now shows, in a tag on it."""
        old = getattr(self, "_badge", None)
        if old is not None:
            try:
                old.hide()
                old.deleteLater()
            except RuntimeError:
                pass
            self._badge = None
        scene = _demo["scene"] or ""
        if self._steps[self._i][3] != "spans" or not scene.startswith("span:") or self._hole is None:
            return
        try:
            from ...ui import Period
            value = int(scene.split(":", 1)[1])
            badge = QLabel(tr("Time span: {span}", span=tr_name(Period.LABEL.get(value, ""))), self)
            set_qss(badge, f"QLabel {{ background: {self._accent.name()}; color: "
                           f"{'#18181b' if self._accent.lightnessF() > 0.6 else '#ffffff'};"
                           " border-radius: 9px; padding: 3px 10px; font-weight: 600; font-size: 12px; }")
            badge.adjustSize()
            h = self._hole
            # On the left of the light: the menu pictures open on its right.
            badge.move(h.left() + 6, max(4, h.top() - badge.height() - 6))
            badge.show()
            self._badge = badge
        except Exception:
            log_swallowed()

    def _thaw_now(self):
        cover, self._cover = getattr(self, "_cover", None), None
        if cover is not None:
            try:
                cover.hide()
                cover.deleteLater()
            except RuntimeError:
                pass

    def _follow(self, tries, last, gen=None):
        """After a scene changed by itself: move the light once the widgets stop moving."""
        try:
            if gen is None:
                gen = getattr(self, "_gen", 0)
            if gen != getattr(self, "_gen", 0) or _tour is not self:
                self._changing = False
                return
            self._keep_on_top()
            r = self._steps[self._i][1](self._win)
            if (r is not None and last is not None and r == last and tries >= 2
                    and _scene_built() and not _scene_loading(anims=False)) or tries >= 40:
                if r is not None and self._steps[self._i][3] == "layouts":
                    size = (self.width(), self.height())
                    _layout_partial[size] = max(_layout_partial.get(size, 0), r.height() + 2 * self.PAD)
                self._thaw(move_card=False)
                self._changing = False
                pending, self._pending_go = getattr(self, "_pending_go", None), None
                if pending is not None:
                    QTimer.singleShot(0, lambda: self._go(pending))
                return
            QTimer.singleShot(60, lambda: self._follow(tries + 1, r, gen))
        except RuntimeError:
            self._changing = False

    def _keep_on_top(self):
        self._ticks = getattr(self, "_ticks", 0) + 1
        if self._ticks % 8 == 0:
            self._watch_target()
        try:
            self.raise_()
            self._card.raise_()
            for g in self._ghosts:
                g.raise_()
        except RuntimeError:
            pass

    def _watch_target(self):
        """A widget that changes size after the light was placed (its data came late): the
        light follows it, gliding."""
        try:
            if (self._busy or getattr(self, "_changing", False) or getattr(self, "_measuring", False)
                    or self._cover is not None or self._hole is None
                    or self._hole_anim.state() == self._hole_anim.State.Running):
                return
            r = self._steps[self._i][1](self._win)
            if r is None:
                return
            hole = r.adjusted(-self.PAD, -self.PAD, self.PAD, self.PAD)
            if hole != self._hole:
                self._set_hole(hole)
                self._show_span_badge()
        except RuntimeError:
            pass
        except Exception:
            log_swallowed()

    # -- live actions: what the step shows by itself ----------------------------------

    def _start_action(self):
        action = self._steps[self._i][3]
        if action == "swap":
            self._drag_token = getattr(self, "_drag_token", 0) + 1
            pair = _drag_pair()
            _drag_demo_id[:] = [pair[1].widget_id] if pair and getattr(pair[1], "widget_id", None) else []
            token = self._drag_token
            QTimer.singleShot(250, lambda: self._drag_sequence(token, 0))
            return
        if action in ("add", "spans"):
            self._add_i = 0
            _add_menu_widget[0] = None
            QTimer.singleShot(200, self._add_demo)
            return
        if action in ("menu", "edit"):
            self._menu_i = 0
            QTimer.singleShot(200, self._menu_demo)
            self._action_timer.start(900)
            return
        if action in ("themes", "layouts", "texts"):
            scenes = _cycle_scenes(action)
            self._theme_i = scenes.index(_demo["scene"]) if _demo["scene"] in scenes else 0
            self._action_timer.start(1500)
        elif action == "zoom":
            QTimer.singleShot(500, self._zoom_demo)
            self._action_timer.start(4600)

    def _edit_layout(self, on, follow=False):
        """The real layout edit mode, on for the edit step (its buttons can't be clicked
        under the tour), then off again unless it was already on."""
        try:
            from ..pinned.main_menu.manager import MainMenuWidgetManager
            from ..pinned.main_menu.ui.edit_mode import is_edit_mode, set_edit_mode
            m = MainMenuWidgetManager.instance()
            if on:
                if is_edit_mode(m):
                    return
                set_edit_mode(m, True)
                self._edit_was_off = True
                # Esc stays the tour's: the edit mode's own Esc shortcut would take it.
                sc = getattr(m, "_edit_escape_shortcut", None)
                if sc is not None:
                    sc.setEnabled(False)
                self._follow(0, None)
            elif getattr(self, "_edit_was_off", False):
                self._edit_was_off = False
                set_edit_mode(m, False)
                if follow:
                    self._follow(0, None)
        except Exception:
            log_swallowed()

    def _stop_action(self, keep_cover=False):
        self._drag_token = getattr(self, "_drag_token", 0) + 1
        self._gap_demo_reset()
        self._edit_layout(False)
        self._action_timer.stop()
        if not keep_cover:
            self._thaw_now()
        badge = getattr(self, "_badge", None)
        if badge is not None:
            try:
                badge.hide()
                badge.deleteLater()
            except RuntimeError:
                pass
            self._badge = None
        self._zoom_reset()
        if self._ghost_anim is not None:
            try:
                self._ghost_anim.stop()
            except RuntimeError:
                pass
            self._ghost_anim = None
        for g in self._ghosts:
            try:
                g.hide()
                g.deleteLater()
            except RuntimeError:
                pass
        self._ghosts = []
        for w in self._hidden:
            try:
                w.setGraphicsEffect(None)
            except RuntimeError:
                pass
        self._hidden = []

    def _on_action_timer(self):
        if _tour is not self:
            # The tour was closed while an example was being swapped in (its end restarted
            # the timer): never put a demo layout back over the user's own.
            self._action_timer.stop()
            return
        action = self._steps[self._i][3] if 0 <= self._i < len(self._steps) else None
        if action in ("themes", "layouts", "texts"):
            scenes = _cycle_scenes(action)
            self._theme_i = (self._theme_i + 1) % len(scenes)
            self._changing = True
            self._freeze()
            _apply_scene(scenes[self._theme_i])
            self._follow(0, None)
        elif action == "zoom":
            self._zoom_demo()
        elif action in ("menu", "edit"):
            self._menu_i += 1
            self._menu_demo()
        elif action in ("add", "spans"):
            self._add_demo()

    def _cascade_place(self, w, levels):
        """Where the pictures of a menu and its submenus go: [(rect, picture, pointer)]."""
        r = _rect_in(self._win, w)
        W, H = self.width(), self.height()
        placed = []
        for i, (pm, entry) in enumerate(levels):
            dpr = max(1.0, pm.devicePixelRatio())
            pw, ph = int(pm.width() / dpr), int(pm.height() / dpr)
            if i == 0:
                # Where a right click near the top right of the widget opens it.
                x, y = r.right() - 30, r.top() + 24
                if x + pw > W - 8:
                    x = r.right() - 30 - pw
            else:
                # Beside the entry that opens it, as Qt puts a submenu.
                prev, pentry = placed[-1][0], levels[i - 1][1]
                x, y = prev.right() - 2, prev.top() + pentry.top() - 4
            y = max(8, min(y, H - ph - 8))
            placed.append((QRect(x, y, pw, ph), pm, entry))
        if not placed:
            return []
        # All the menus side by side, each one fully seen: the whole cascade goes left as
        # much as needed (a submenu put back over its parent hid it).
        shift = max(0, max(r_.right() for r_, _pm, _e in placed) - (W - 8))
        shift = min(shift, max(0, placed[0][0].left() - 8))
        return [(r_.translated(-shift, 0), pm, QPoint(r_.left() - shift + e.center().x(), r_.top() + e.center().y()))
                for r_, pm, e in placed]

    @staticmethod
    def _cascade_frames(placed, scene, last_ms=900, scene_ms=2600):
        """The menu as it opens, then one more level each time with the pointer on its
        entry, then the click (the scene that shows its effect)."""
        frames = [([(placed[0][1], placed[0][0])], None, 650)]
        for k in range(len(placed)):
            last = k == len(placed) - 1
            frames.append(([(pm, rect) for rect, pm, _pt in placed[:k + 1]], placed[k][2], last_ms if last else 650))
        frames.append((scene, None, scene_ms))
        return frames

    def _add_frames_for(self, w):
        """The add step's pictures, worked out once: along the way to a chart, then to a
        stat card, each time followed by the widget showing up."""
        if getattr(self, "_add_frames", None) is not None:
            return self._add_frames
        from ..pinned.main_menu.ui.add_widget_menu import CHARTS, default_span
        from ..stats_cards.logic.model import get_stat_card_name

        add = tr("Add Widget...")
        chart_type, stat_key = _add_choices()
        paths = []
        _add_demo_pins.clear()
        if chart_type is not None:
            label = dict(CHARTS)[chart_type]
            paths.append(("chart", None))
            pin = {"id": "tour-add-chart", "type": chart_type, "label": label, "stat_key": None}
            if default_span(chart_type) is not None:
                pin["time_span"] = default_span(chart_type)
            _add_demo_pins["chart"] = pin
        if stat_key is not None:
            paths.append(("stat", None))
            _add_demo_pins["stat"] = {"id": "tour-add-stat", "type": "stat_card",
                                      "label": get_stat_card_name(stat_key), "stat_key": stat_key}
            if default_span("stat_card", stat_key) is not None:
                _add_demo_pins["stat"]["time_span"] = default_span("stat_card", stat_key)
        frames = []
        self._add_frame_widgets = []
        self._gallery_rect = None
        for which, _path in paths:
            anchor = _add_anchor(which) or w
            if anchor is None:
                continue
            if which in _add_demo_pins and getattr(anchor, "widget_id", None):
                _add_demo_pins[which]["_after"] = anchor.widget_id
            # The two ways in turn: the right-click menu for the chart, the "+" at the end of
            # a line for the stat card.
            more = self._plus_frames(anchor, which) if which == "stat" else None
            if more:
                frames += more
                # The light on the "+" (still there under the gallery, as the widget whose
                # menu opened), then on the widget added.
                self._add_frame_widgets += ["plus"] * 3 + [getattr(anchor, "widget_id", None)]
                continue
            levels = _cascade_pictures(anchor, [add])
            if len(levels) != 1 or self._tour_gallery() is None:
                continue
            # The menu opens, the pointer goes to "Add Widget...", the gallery opens on the
            # widget's tab with the pointer on it, then the widget shows up.
            more = self._cascade_frames(self._cascade_place(anchor, levels), None)[:-1]
            more.append((lambda which=which: self._gallery_frame(which), None, 1900))
            more.append(("add:" + which, None, 2600))
            frames += more
            self._add_frame_widgets += [getattr(anchor, "widget_id", None)] * len(more)
        self._add_frames = frames
        return frames

    def _plus_frames(self, anchor, which):
        """The add step by the "+": the pointer goes to the end of the anchor's line, the
        "+" shows there, a click, the gallery, the widget shows up at the end of that line.
        None when the line or the "+" cannot be placed (then the right-click menu is shown).
        The "+" is placed when each frame shows: the screen may have moved since the frames
        were made (a widget added and taken away by the step, another scene before)."""
        wid = getattr(anchor, "widget_id", None)
        if self._tour_gallery() is None or self._plus_spot(wid, which) is None:
            return None

        def on_plus():
            spot = self._plus_spot(wid, which)
            if spot is None:
                return [], None
            rect, pm = spot
            return [(pm, rect)], QPoint(rect.left() + 9, rect.top() + 9)

        def gallery():
            pics, point = self._gallery_frame(which, "end")
            rect = getattr(self, "_plus_rect", None)
            pm = getattr(self, "_plus_pm", None)
            if pics and rect is not None and pm is not None:
                pics = [(pm, rect)] + pics  # the "+" stays under the gallery
            return pics, point

        # The first frame shows nothing: the user's own screen may still be coming back
        # behind its picture (after the chart added just before). Then the "+" with the
        # pointer on it, the click, the gallery.
        return [
            ([], None, 500),
            (on_plus, None, 1100),
            (gallery, None, 1900),
            ("add:" + which, None, 2600),
        ]

    def _plus_spot(self, wid, which):
        """(rect in the window, picture) of the "+" at the end of the line of the widget
        wid, as the screen is now, or None. Sets where the widget added goes."""
        self._plus_rect = None
        try:
            from ..pinned import WidgetRegistry
            from ..pinned.main_menu.manager import MainMenuWidgetManager
            from ..pinned.main_menu.ui.add_here import _Plus, _lines, _SIZE
            from ..pinned.main_menu.ui.drag_move import box_of, family, row_of

            manager = MainMenuWidgetManager.instance()
            overlay = getattr(manager, "_overlay", None)
            defs = WidgetRegistry.get_all()
            d = next((x for x in defs if wid and x.get("id") == wid), None)
            if overlay is None or d is None:
                return None
            key = (family(d), box_of(d), row_of(d))
            line = _lines(manager, overlay).get(key)
            if line is None:
                return None
            # Where the real one shows (add_here.find_target).
            x = min(line.right() + 6, overlay.width() - _SIZE - 2)
            y = line.center().y() - _SIZE // 2
            at = overlay.mapTo(self._win, QPoint(x, y))
            pm = getattr(self, "_plus_pm", None)
            if pm is None:
                plus = _Plus(overlay, lambda _t: None)
                plus.resize(_SIZE, _SIZE)
                pm = self._plus_pm = plus.grab()
                plus.deleteLater()
            mates = [x["id"] for x in defs if (family(x), box_of(x), row_of(x)) == key
                     and not str(x.get("id", "")).startswith("tour-add-")]
            if which in _add_demo_pins and mates:
                _add_demo_pins[which]["_after"] = mates[-1]  # the end of the line
            rect = QRect(at.x(), at.y(), _SIZE, _SIZE)
            self._plus_rect = rect
            return rect, pm
        except RuntimeError:
            return None
        except Exception:
            log_swallowed()
            return None

    def _tour_gallery(self):
        """The widget gallery of the add step: built once, never on screen, filled with its
        previews while the menu pictures show."""
        g = getattr(self, "_gallery", None)
        if g is not None:
            return g
        try:
            from ..pinned.main_menu.manager import MainMenuWidgetManager
            from ..pinned.main_menu.ui.widget_gallery import WidgetGallery

            g = WidgetGallery(MainMenuWidgetManager.instance(), self._win, where="after")
            g.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
            for pin in _add_demo_pins.values():
                tile = g.tile_for(lambda c, p=pin: c.widget_type == p["type"] and c.stat_key == p.get("stat_key"))
                if tile is not None:
                    g.prioritize(tile)
            g.show()
            self._gallery = g
            return g
        except Exception:
            log_swallowed()
            return None

    def _drop_gallery(self):
        g = getattr(self, "_gallery", None)
        self._gallery = None
        if g is not None:
            try:
                g.done(0)
                g.deleteLater()
            except RuntimeError:
                pass

    def _gallery_place(self, g):
        """Where the gallery picture goes: centered, at most 70 % of the window."""
        W, H = self.width(), self.height()
        scale = min(1.0, (W * 0.7) / max(1, g.width()), (H * 0.7) / max(1, g.height()))
        w, h = int(g.width() * scale), int(g.height() * scale)
        return QRect((W - w) // 2, (H - h) // 2, w, h), scale

    def _gallery_frame(self, which, where="after"):
        """A picture of the gallery on the tab of the widget added, the pointer on it.
        where: how it was opened ("after": the right-click menu, "end": the "+")."""
        g = self._tour_gallery()
        pin = _add_demo_pins.get(which)
        if g is None or pin is None:
            return [], None
        try:
            g.set_where(where)
            tile = g.tile_for(lambda c: c.widget_type == pin["type"] and c.stat_key == pin.get("stat_key"))
            if tile is None:
                return [], None
            g.layout().activate()
            g.go_to(which)
            g._scroll.ensureWidgetVisible(tile, 0, 40)
            tile.set_hover(True)
            pm = g.grab()
            center = tile.mapTo(g, tile.rect().center())
            tile.set_hover(False)
            rect, scale = self._gallery_place(g)
            self._gallery_rect = rect
            point = QPoint(rect.left() + int(center.x() * scale), rect.top() + int(center.y() * scale))
            return [(pm, rect)], point
        except RuntimeError:
            return [], None

    def _span_frames_for(self, w):
        """The span step's frames: for each time span, the menu down to it (built when it
        shows, so the tick is on the span shown at that moment), then the chart with it."""
        if getattr(self, "_add_frames", None) is not None:
            return self._add_frames
        values = _span_choices(w)
        frames = []
        for v in values:
            def build(k, v=v):
                # The chart as it is now (each period shown rebuilds it).
                now = _span_shown_widget() or w
                chip = _span_chip(now)
                if chip is not None:
                    # The label next to the title: a click on it, its period list, the period.
                    return self._chip_menu_frame(now, chip, v, k)
                levels = _cascade_pictures(w, [tr("Time Span"), lambda a, v=v: a.data() == v])
                placed = self._cascade_place(w, levels) if len(levels) == 2 else []
                if not placed:
                    return [], None
                f = self._cascade_frames(placed, None)
                return f[k][0], f[k][1]
            frames += [(lambda b=build: b(0), None, 650), (lambda b=build: b(1), None, 650),
                       (lambda b=build: b(2), None, 900), (f"span:{v}", None, 2200)]
        if frames:
            # Where the pictures go, for the card (the same size for every span).
            pics, _pt = frames[2][0]()
            self._cascade_rects = [rect for _pm, rect in pics]
        self._add_frames = frames
        return frames

    def _chip_menu_frame(self, w, chip, value, k):
        """Frame k of the period label (chip: the chart's card_chips): 0 the pointer on the
        label, 1 its period list open, 2 the pointer on the period. Pictures of the real
        list, placed as it opens (above the label when there is room, else under it)."""
        try:
            label = chip.span
            pointer = _rect_in(self._win, label).center()
            if k == 0:
                return [], pointer
            from ..pinned.main_menu.manager import MainMenuWidgetManager
            from ..pinned.main_menu.ui.card_chips import fill_span_menu, themed_menu

            manager = MainMenuWidgetManager.instance()
            menu = themed_menu(w, manager)
            fill_span_menu(menu, manager, w, chip.widget_def)
            menu.ensurePolished()
            menu.adjustSize()
            act = next((a for a in menu.actions() if a.data() == value), None)
            if act is None:
                menu.deleteLater()
                return [], None
            if k == 2:
                menu.setActiveAction(act)
            pm = menu.grab()
            entry = menu.actionGeometry(act)
            menu.deleteLater()
            dpr = max(1.0, pm.devicePixelRatio())
            pw, ph = int(pm.width() / dpr), int(pm.height() / dpr)
            cr = _rect_in(self._win, label)
            x = min(max(8, cr.left()), self.width() - pw - 8)
            y = cr.top() - ph - 2 if cr.top() - ph - 2 >= 8 else cr.bottom() + 2
            rect = QRect(x, y, pw, ph)
            if k == 1:
                return [(pm, rect)], pointer
            return [(pm, rect)], QPoint(x + entry.center().x(), y + entry.center().y())
        except RuntimeError:
            return [], None
        except Exception:
            log_swallowed()
            return [], None

    def _add_area(self):
        """All the room the step's menu pictures take (worked out on the step's first
        placing, so the card goes clear of them at once, not after a jump)."""
        action = self._steps[self._i][3] if 0 <= self._i < len(self._steps) else None
        frames = getattr(self, "_add_frames", None)
        if frames is None:
            frames = self._demo_frames(action)
        if action == "spans":
            rects = getattr(self, "_cascade_rects", None) or []
        else:
            rects = [rect for pics, _pt, _ms in frames or () if isinstance(pics, list) for _pm, rect in pics]
            g = getattr(self, "_gallery", None)
            if action == "add" and g is not None:
                rects.append(self._gallery_place(g)[0])
            if action == "add" and getattr(self, "_plus_rect", None) is not None:
                rects.append(self._plus_rect)
        area = None
        for rect in rects:
            area = rect if area is None else area.united(rect)
        return area

    def _demo_frames(self, action):
        if action == "add":
            w = _add_anchor("chart")
            return self._add_frames_for(w) if w is not None else None
        if action == "spans":
            w = _span_shown_widget()
            return self._span_frames_for(w) if w is not None else None
        return None

    def _add_demo(self):
        """The real right-click menu opens, then its submenus one by one, the mouse on the
        entry each time (pictures only, nothing can be clicked), then what the click does."""
        if _tour is not self or not (0 <= self._i < len(self._steps)):
            return
        action = self._steps[self._i][3]
        if action not in ("add", "spans"):
            return
        for g in self._ghosts:
            try:
                g.hide()
                g.deleteLater()
            except RuntimeError:
                pass
        self._ghosts = []
        try:
            frames = self._demo_frames(action)
            if not frames:
                return
            k = self._add_i % len(frames)
            pics, point, ms = frames[k]
            self._add_i += 1
            if action == "add":
                anchors = getattr(self, "_add_frame_widgets", None) or []
                _add_menu_widget[0] = anchors[k] if k < len(anchors) else None
            if callable(pics):
                pics, point = pics()
            scene = pics if isinstance(pics, str) else None
            mine = (_demo["scene"] or "").startswith(("add:", "span:"))
            if (scene is not None and scene != _demo["scene"]) or (action == "add" and scene is None and mine):
                if scene is not None and scene.startswith("span:"):
                    # Another period on the same chart: it is updated in place and animates
                    # to it, as after a real click; no picture over the screen meanwhile.
                    _apply_scene(scene)
                    self._show_span_badge()
                else:
                    # Show what the click does, or put the user's own back: the screen waits
                    # behind its picture while it is rebuilt, then the light goes to it.
                    self._changing = True
                    self._freeze()
                    _apply_scene(scene)
                    self._follow(0, None)
            self._action_timer.start(ms)
            if scene is not None:
                return
            for pm, rect in pics:
                label = QLabel(self)
                label.setPixmap(pm)
                label.setScaledContents(True)
                label.setGeometry(rect)
                label.show()
                self._ghosts.append(label)
            if point is not None:
                cursor = QLabel(self)
                cursor.setPixmap(_pointer_pixmap())
                cursor.resize(20, 26)
                cursor.move(point)
                cursor.show()
                self._ghosts.append(cursor)
            self._keep_on_top()
            area = self._add_area()
            if area is not None:
                self._card_clear_of(area)
        except Exception:
            log_swallowed()

    def _menu_demo(self):
        """The widget's real right-click menu opens, the mouse goes to its settings entry,
        then its settings window shows: pictures only, nothing can be clicked."""
        if self._steps[self._i][3] not in ("menu", "edit"):
            return
        w = self._menu_widget()
        if w is None or not self._menu_shots:
            return
        kind = self._menu_shots[self._menu_i % len(self._menu_shots)][0]
        if self._steps[self._i][3] == "edit":
            # Edit layout on for a moment (after the click on it), off again for the menu.
            self._edit_layout(kind == "edit", follow=True)
        for g in self._ghosts:
            try:
                g.hide()
                g.deleteLater()
            except RuntimeError:
                pass
        self._ghosts = []
        if kind == "edit":
            self._action_timer.setInterval(3600)
            return
        try:
            kind, pm, entry = self._menu_shots[self._menu_i % len(self._menu_shots)]
            x, y, wv, hv, scale = self._menu_geometry(w, kind, pm)
            label = QLabel(self)
            label.setPixmap(pm)
            label.setScaledContents(True)
            label.setGeometry(x, y, wv, hv)
            label.show()
            self._ghosts.append(label)
            if entry is not None:
                # A mouse pointer on the settings entry.
                cursor = QLabel(self)
                cursor.setPixmap(_pointer_pixmap())
                cursor.resize(20, 26)
                cursor.move(x + int(entry.center().x() * scale), y + int(entry.center().y() * scale))
                cursor.show()
                self._ghosts.append(cursor)
            self._keep_on_top()
            self._card_clear_of(label.geometry())
            # The settings window stays longer: there is more to look at.
            self._action_timer.setInterval(1900 if kind == "settings" else 850)
        except Exception:
            log_swallowed()

    def _menu_widget(self):
        """The chart the menu step shows, with its pictures taken once."""
        w = _menu_target()
        if w is None:
            return None
        if self._menu_shots is None:
            if self._steps[self._i][3] == "edit":
                # The edit step: the menu, the mouse on Edit layout, then the real mode.
                menu = _menu_picture(w, {tr("Edit layout")})
                self._menu_shots = []
                if menu:
                    self._menu_shots += [("menu", menu[0], None), ("menu", menu[1], menu[2])]
                self._menu_shots.append(("edit", None, None))
                return w
            menu = _menu_picture(w)
            settings = _settings_picture(w)
            self._menu_shots = []
            if menu:
                self._menu_shots += [("menu", menu[0], None), ("menu", menu[1], menu[2])]
            if settings is not None:
                self._menu_shots.append(("settings", settings, None))
        return w

    def _menu_geometry(self, w, kind, pm):
        """Where a picture of the menu step goes: x, y, width, height, scale."""
        dpr = max(1.0, pm.devicePixelRatio())
        size = pm.size() / dpr
        scale = 1.0
        r = _rect_in(self._win, w)
        if kind == "settings":
            scale = min(1.0, 0.62 * self.height() / max(1, size.height()), 0.42 * self.width() / max(1, size.width()))
            # Beside the widget, a bit smaller if needed; a wide widget (the calendar) leaves
            # no room, then it goes at the right edge, over the widget's right end only.
            room_r = self.width() - 8 - (r.right() + 12)
            room_l = r.left() - 12 - 8
            room = max(room_r, room_l)
            fits = room >= 0.6 * size.width() * scale
            if fits:
                scale = min(scale, room / max(1, size.width()))
        wv, hv = int(size.width() * scale), int(size.height() * scale)
        if kind == "menu":
            # Where a right click near the top right of the widget opens it.
            x, y = r.right() - 30, r.top() + 24
            if x + wv > self.width() - 8:
                x = r.right() - 30 - wv
        else:
            if fits:
                x = r.right() + 12 if room_r >= room_l else r.left() - 12 - wv
            else:
                x = self.width() - wv - 8
            y = r.top()
        x = max(8, min(x, self.width() - wv - 8))
        y = max(8, min(y, self.height() - hv - 8))
        return x, y, wv, hv, scale

    def _menu_area(self):
        """All the room the menu step's pictures take, or None."""
        w = self._menu_widget()
        if w is None or not self._menu_shots:
            return None
        area = None
        for kind, pm, _entry in self._menu_shots:
            if pm is None:
                continue
            x, y, wv, hv, _s = self._menu_geometry(w, kind, pm)
            r = QRect(x, y, wv, hv)
            area = r if area is None else area.united(r)
        return area

    def _card_clear_of(self, rect):
        """Move the card off a picture shown next to the light."""
        card = self._card.geometry()
        if not card.intersects(rect):
            return
        cw, ch = card.width(), card.height()
        W, H = self.width(), self.height()
        running = self._hole_anim.state() == self._hole_anim.State.Running
        h = self._hole_to if running and self._hole_to is not None else self._hole
        spots = []
        if h is not None:
            # Beside the light, on the side away from the picture, then under / over it.
            if rect.center().x() >= h.center().x():
                spots += [(h.left() - cw - 12, h.top()), (rect.left() - cw - 12, h.bottom() + 12),
                          (rect.left() - cw - 12, h.top() - ch - 12)]
            else:
                spots += [(h.right() + 12, h.top()), (rect.right() + 12, h.bottom() + 12),
                          (rect.right() + 12, h.top() - ch - 12)]
            for y in (h.bottom() + 12, h.top() - 12 - ch):
                for x in (h.left(), h.right() - cw, (W - cw) // 2):
                    spots.append((x, y))
        for x, y in spots:
            cand = QRect(max(8, min(x, W - cw - 8)), max(8, min(y, H - ch - 8)), cw, ch)
            if not cand.intersects(rect):
                self._card.move(cand.topLeft())
                self._card.raise_()
                return

    def _drag_alive(self, token):
        return (_tour is self and token == getattr(self, "_drag_token", 0)
                and 0 <= self._i < len(self._steps) and self._steps[self._i][3] == "swap")

    def _drag_sequence(self, token, k):
        """What dragging does, one after the other, again and again: two widgets trade
        places, one goes on a new line, one goes in a new box."""
        if not self._drag_alive(token):
            return
        # The quick swap first, then what else a drag does; then all again.
        # (a new line is a box of its own: the "newbox" one)
        demos = ("swap", "newbox", "movebox", "gap")
        kind = demos[k % len(demos)]
        nxt = lambda: QTimer.singleShot(150, lambda: self._drag_sequence(token, k + 1))
        if kind == "swap":
            self._swap_demo(on_done=nxt, token=token)
        elif kind == "gap":
            self._gap_demo(token, nxt)
        else:
            self._drop_demo(kind, token, nxt)

    def _hole_follow(self):
        """The light right on the step's target at once (no glide): for a target that grows
        and shrinks step by step, a glide behind it each time lags."""
        try:
            r = self._steps[self._i][1](self._win)
            if r is None:
                return
            self._hole_anim.stop()
            self._hole = r.adjusted(-self.PAD, -self.PAD, self.PAD, self.PAD)
            self.update()
        except RuntimeError:
            pass
        except Exception:
            log_swallowed()

    def _gap_demo_reset(self):
        """Put back the space the gap demo changed (only on screen: nothing is saved)."""
        state, self._gap_state = getattr(self, "_gap_state", None), None
        if state is None:
            return
        hov, key, had, orig = state
        try:
            hov.bar._start = None
            hov.set_size(key, orig if had else None, save=False)
            hov.hide_label()
            hov.bar.hide()
            hov._overlay.update_mask()
        except RuntimeError:
            pass
        except Exception:
            log_swallowed()

    def _gap_demo(self, token, on_done):
        """The mouse rests in a space between two lines (or two boxes), its small grip
        shows, and the space is dragged bigger, then back: what dragging a space does. The
        real space changes on screen for a moment; nothing is saved."""
        from aqt.qt import QEasingCurve, QPropertyAnimation
        from ...ui import Config

        try:
            from ..pinned.main_menu.manager import MainMenuWidgetManager
            from ..pinned.main_menu.ui.gap_handle import _grab_rect, _spaces

            m = MainMenuWidgetManager.instance()
            ov = m._overlay
            hov = getattr(ov, "_dd_gap_hover", None)
            spaces = _spaces(m, ov) if hov is not None else []
        except Exception:
            log_swallowed()
            spaces = []
        card = self._card.geometry().adjusted(-10, -10, 10, 10)

        def tour_rect(r):
            return QRect(ov.mapTo(self._win, r.topLeft()), r.size())

        # A space between two lines first, else between two boxes; never under the card.
        pick = None
        for prefer in ("line:", "box:"):
            for key, space, default in spaces:
                if key.startswith(prefer) and not tour_rect(_grab_rect(space)).intersects(card):
                    pick = (key, space, default)
                    break
            if pick:
                break
        if pick is None:
            on_done()
            return
        key, space, default = pick
        conf = (m._config_manager.config.get(Config.PINNED_GAPS) or {})
        had, orig = key in conf, hov.size_of(key, default)
        self._gap_state = (hov, key, had, orig)
        self._clear_ghosts()
        x_local = max(40, min(space.width() - 40, space.width() // 3))
        spot = QPoint(space.left() + x_local, space.center().y())
        pointer = QLabel(self)
        pointer.setPixmap(_pointer_pixmap())
        pointer.resize(20, 26)
        start = ov.mapTo(self._win, spot + QPoint(60, 70))
        pointer.move(start)
        pointer.show()
        self._ghosts.append(pointer)
        anim = QPropertyAnimation(pointer, b"pos", self)
        anim.setStartValue(start)
        anim.setEndValue(ov.mapTo(self._win, spot))
        anim.setDuration(450)
        anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        anim.start()
        self._ghost_anim = anim
        self._keep_on_top()
        grow = 70  # well seen: the boxes below clearly move down

        def alive():
            return self._drag_alive(token) and getattr(self, "_gap_state", None) is not None

        def show_grip():
            if not alive():
                return
            bar = hov.bar
            bar.pill_x = x_local
            hov._put(key, space, default)
            QTimer.singleShot(350, lambda: step(0, 1))

        def step(i, sign, n=14):
            # The space grows (sign 1) or goes back (sign -1), the pointer holding it.
            if not alive():
                return
            bar = hov.bar
            bar._start = (0, orig)
            t = i / float(n)
            ease = t * t * (3 - 2 * t)
            done = ease if sign > 0 else 1 - ease
            size = orig + int(round(grow * done / 2.0)) * 2
            hov.set_size(key, size, save=False)
            self._hole_follow()
            if not bar.isVisible():
                return
            g = bar.geometry()
            pointer.move(ov.mapTo(self._win, QPoint(g.left() + x_local, g.center().y())))
            self._keep_on_top()
            if i < n:
                QTimer.singleShot(35, lambda: step(i + 1, sign, n))
            elif sign > 0:
                QTimer.singleShot(900, lambda: step(0, -1, n))
            else:
                QTimer.singleShot(250, finish)

        def finish():
            if not self._drag_alive(token):
                return
            self._gap_demo_reset()
            self._hole_follow()
            self._clear_ghosts()
            QTimer.singleShot(400, on_done)

        QTimer.singleShot(450 + 350, show_grip)

    def _clear_ghosts(self):
        if self._ghost_anim is not None:
            try:
                self._ghost_anim.stop()
            except RuntimeError:
                pass
            self._ghost_anim = None
        for g in self._ghosts:
            try:
                g.hide()
                g.deleteLater()
            except RuntimeError:
                pass
        self._ghosts = []
        for w in self._hidden:
            try:
                w.setGraphicsEffect(None)
            except RuntimeError:
                pass
        self._hidden = []

    def _drop_target(self, kind, w):
        """(where the dragged copy goes, the bar to show) in tour coordinates, or None."""
        area = _target_all(self._win)
        if area is None:
            return None
        if kind == "newbox":
            # Above all the boxes, or below them when the card is up there.
            below = self._card.geometry().center().y() < area.center().y()
            _drag_demo_end[0] = "bottom" if below else "top"
            y = area.bottom() + 14 if below else area.top() - 14
            return QPoint(area.center().x(), y), QRect(area.left(), y - 2, area.width(), 4)
        try:
            from ..pinned.main_menu.manager import MainMenuWidgetManager
            m = MainMenuWidgetManager.instance()
            for box in (getattr(m, "_chart_boxes", None) or {}).values():
                rows = [rw for rw, ml in box.get("rows", []) if ml.count() > 0 and rw.isVisible()]
                for a, b in zip(rows, rows[1:]):
                    if a.isAncestorOf(w):
                        ra, rb = _rect_in(self._win, a), _rect_in(self._win, b)
                        y = (ra.bottom() + rb.top()) // 2
                        return QPoint(ra.center().x(), y), QRect(ra.left(), y - 2, ra.width(), 4)
                # Its line is the last one of its box: dropped near the bottom of it (inside
                # the box), a new line below, when it is not alone on its line.
                pairs = [(rw, ml) for rw, ml in box.get("rows", []) if ml.count() > 0 and rw.isVisible()]
                if pairs and pairs[-1][0].isAncestorOf(w) and pairs[-1][1].count() > 1:
                    ra = _rect_in(self._win, pairs[-1][0])
                    y = ra.bottom() - 10
                    return QPoint(ra.center().x(), y), QRect(ra.left(), y - 2, ra.width(), 4)
        except Exception:
            log_swallowed()
        return None

    def _box_target(self):
        """The whole box the drag step moves (the one nearest the tour's card goes to the
        other end), and (where its copy goes, the bar): (widget, found) or (None, None)."""
        try:
            from ..pinned.main_menu.manager import MainMenuWidgetManager
            from ..pinned.main_menu.ui.drag_layout import _sections
            sections = _sections(MainMenuWidgetManager.instance())
        except Exception:
            log_swallowed()
            return None, None
        area = _target_all(self._win)
        if len(sections) < 2 or area is None:
            return None, None
        # The stat cards' box (several cards: clearly a whole box moving), else a graphs box;
        # never a text box (often one widget alone).
        pick = next((s for s in sections if s[0].startswith("stats")), None) or next(
            (s for s in sections if s[0].startswith("charts")), sections[0])
        key, w, _r = pick
        idx = [s[0] for s in sections].index(key)
        if idx == 0:
            below = True
        elif idx == len(sections) - 1:
            below = False
        else:
            below = self._card.geometry().center().y() < area.center().y()
        _drag_demo_box[:] = [key, "bottom" if below else "top"]
        y = area.bottom() + 14 if below else area.top() - 14
        return w, (QPoint(area.center().x(), y), QRect(area.left(), y - 2, area.width(), 4))

    def _drop_demo(self, kind, token, on_done):
        """A copy of a chart is carried to a gap, the gap's bar shows, it is dropped: the
        real layout changes (a new line / a new box there), then goes back."""
        from aqt.qt import QGraphicsOpacityEffect

        if kind == "movebox":
            w, found = self._box_target()
        else:
            w = next((x for x in _pinned_widgets() if _drag_demo_id and getattr(x, "widget_id", None) == _drag_demo_id[0]), None)
            found = self._drop_target(kind, w) if w is not None else None
        if found is None:
            on_done()
            return
        point, bar = found
        try:
            self._clear_ghosts()
            start = _rect_in(self._win, w)
            ghost = QLabel(self)
            ghost.setPixmap(_rounded_grab(w))
            ghost.setScaledContents(True)
            ghost.setGeometry(start)
            ghost.show()
            self._ghosts.append(ghost)
            if w.graphicsEffect() is None and not effect_nested(w):  # see effect_guard
                eff = QGraphicsOpacityEffect(w)
                eff.setOpacity(0.25)  # its place stays visible, faded
                w.setGraphicsEffect(eff)
                self._hidden.append(w)
            if kind == "movebox":
                # Taken by its handle, on its left.
                from ..pinned.main_menu.manager import MainMenuWidgetManager
                from ..pinned.main_menu.ui.section_handle import _Grip, _content_rect
                grip = _Grip(MainMenuWidgetManager.instance(), self)
                content = _content_rect(self._win, w) or start
                grip.move(max(0, content.left() - grip.width() - 6), content.top() + 2)
                grip.show()
                self._ghosts.append(grip)
                grab = grip.geometry().center()
            else:
                grab = start.topLeft() + QPoint(70, 14)  # by its title
            # Carried at a smaller size, centered on the gap, the mouse holding it.
            scale = 0.45 if kind == "movebox" else 0.6
            end = QRect(0, 0, int(start.width() * scale), int(start.height() * scale))
            end.moveCenter(point)
            off = grab - start.topLeft()
            grab_end = end.topLeft() + QPoint(int(off.x() * scale), int(off.y() * scale))
            self._ghost_anim = self._carry(ghost, start, end, grab, grab_end, 450, pause=350)
            self._keep_on_top()
        except Exception:
            log_swallowed()
            on_done()
            return

        def show_bar():
            if not self._drag_alive(token):
                return
            try:
                from ..pinned.main_menu.ui.drag_layout import _GapMarker
                marker = _GapMarker(self)
                marker.show_bar(bar, {"newline": tr("New line"), "newbox": tr("New line")}.get(kind, tr("Move here")))
                self._ghosts.append(marker)
                self._keep_on_top()
            except Exception:
                log_swallowed()
            QTimer.singleShot(450, drop)

        def drop():
            if not self._drag_alive(token):
                return
            self._changing = True
            self._freeze()  # the copy and the bar stay on the picture until the new layout fades in
            self._clear_ghosts()
            _apply_scene("drag:" + kind)
            self._follow(0, None)
            QTimer.singleShot(1600, back)

        def back():
            if not self._drag_alive(token):
                return
            if getattr(self, "_changing", False):
                QTimer.singleShot(100, back)
                return
            self._changing = True
            self._freeze()
            _apply_scene(None)
            self._follow(0, None)
            QTimer.singleShot(600, done)

        def done():
            if self._drag_alive(token):
                on_done()

        QTimer.singleShot(850, show_bar)

    def _carry(self, ghost, start, end, grab, grab_end, duration, pause=0):
        """Move a copy from start to end with a mouse pointer holding it (at grab): the
        pointer shows first, then both move together. Returns the running animation."""
        from aqt.qt import (
            QEasingCurve, QParallelAnimationGroup, QPauseAnimation, QPropertyAnimation,
            QSequentialAnimationGroup,
        )
        pointer = QLabel(self)
        pointer.setPixmap(_pointer_pixmap())
        pointer.resize(20, 26)
        pointer.move(grab)
        pointer.show()
        self._ghosts.append(pointer)
        seq = QSequentialAnimationGroup(self)
        if pause:
            seq.addAnimation(QPauseAnimation(pause, seq))
        par = QParallelAnimationGroup(seq)
        for target, prop, a, b in ((ghost, b"geometry", start, end), (pointer, b"pos", grab, grab_end)):
            anim = QPropertyAnimation(target, prop, par)
            anim.setStartValue(a)
            anim.setEndValue(b)
            anim.setDuration(duration)
            anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
            par.addAnimation(anim)
        seq.addAnimation(par)
        seq.start()
        return seq

    def _swap_demo(self, on_done=None, token=None, pair=None):
        """Two charts side by side trade places, stay there a moment, then go back: what
        dragging one onto the other does. Copies move; the real widgets are not touched."""
        if self._steps[self._i][3] != "swap" or self._ghosts:
            return
        from aqt.qt import (
            QEasingCurve, QGraphicsOpacityEffect, QParallelAnimationGroup, QPauseAnimation,
            QPropertyAnimation, QSequentialAnimationGroup,
        )
        pair = pair or _drag_pair()
        if not pair:
            if on_done is not None:
                on_done()
            return
        try:
            a, b = pair  # a is on the left
            ra, rb = _rect_in(self._win, a), _rect_in(self._win, b)
            # Where each one ends up once swapped: b starts where a started, a follows b
            # with the same gap (they keep their own sizes).
            gap = rb.left() - ra.right() - 1
            nb = QRect(ra.left(), rb.top(), rb.width(), rb.height())
            na = QRect(ra.left() + rb.width() + gap, ra.top(), ra.width(), ra.height())
            moves = []
            for w, start, end in ((a, ra, na), (b, rb, nb)):
                ghost = QLabel(self)
                ghost.setPixmap(_rounded_grab(w))
                ghost.setScaledContents(True)
                ghost.setGeometry(start)
                ghost.show()
                self._ghosts.append(ghost)
                if w.graphicsEffect() is None and not effect_nested(w):
                    eff = QGraphicsOpacityEffect(w)
                    eff.setOpacity(0.0)  # hidden under its copy, no relayout
                    w.setGraphicsEffect(eff)
                    self._hidden.append(w)
                moves.append((ghost, start, end))
            if on_done is not None:
                # In the drag step: one way only, the right one taken by the mouse onto the
                # left one; then the real layout takes the new order and the step goes on.
                _drag_demo_swap[:] = [getattr(a, "widget_id", None), getattr(b, "widget_id", None)]
                (ga, sa, ea), (gb, sb, eb) = moves
                grab = sb.topLeft() + QPoint(70, 14)
                seq = self._carry(gb, sb, eb, grab, eb.topLeft() + QPoint(70, 14), 500, pause=350)
                slide = QPropertyAnimation(ga, b"geometry", self)
                slide.setStartValue(sa)
                slide.setEndValue(ea)
                slide.setDuration(500)
                slide.setEasingCurve(QEasingCurve.Type.InOutCubic)
                QTimer.singleShot(350, slide.start)

                def _swapped():
                    if token is not None and not self._drag_alive(token):
                        return
                    self._changing = True
                    self._freeze()
                    self._clear_ghosts()
                    _apply_scene("drag:swap")
                    self._follow(0, None)
                    QTimer.singleShot(450, lambda: self._drag_alive(token) and on_done())

                seq.finished.connect(_swapped)
                self._ghost_anim = seq
                self._keep_on_top()
                return
            seq = QSequentialAnimationGroup(self)
            seq.addAnimation(QPauseAnimation(500, seq))
            for forward in (True, False):
                par = QParallelAnimationGroup(seq)
                for ghost, start, end in moves:
                    anim = QPropertyAnimation(ghost, b"geometry", par)
                    anim.setStartValue(start if forward else end)
                    anim.setEndValue(end if forward else start)
                    anim.setDuration(550)
                    anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
                    par.addAnimation(anim)
                seq.addAnimation(par)
                seq.addAnimation(QPauseAnimation(1300, seq))
            seq.setLoopCount(-1)
            seq.start()
            self._ghost_anim = seq
            self._keep_on_top()
        except Exception:
            log_swallowed()

    def _zoom_chart(self):
        return _pick_zoom_chart()

    def _zoom_demo(self):
        """A mouse drags over a part of a chart (its real selection zone shows), lets go,
        and the chart zooms on it; then back to the full view."""
        if self._steps[self._i][3] != "zoom":
            return
        c = self._zoom_chart()
        if c is None:
            return
        try:
            n = int(getattr(c, "_full_length", 0) or 0)
            if n < 6:
                return
            self._zoom_reset()
            self._zoom_token = getattr(self, "_zoom_token", 0) + 1
            token = self._zoom_token
            y = c.height() * 0.55
            xa, xb = c.width() * 0.42, c.width() * 0.72
            pointer = QLabel(self)
            pointer.setPixmap(_pointer_pixmap())
            pointer.resize(20, 26)
            self._ghosts.append(pointer)

            def at(x):
                p = c.mapTo(self._win, QPoint(int(x), int(y)))
                pointer.move(p.x() - 1, p.y() - 1)
                pointer.show()
                pointer.raise_()

            def send(kind, x, button):
                from aqt.qt import QMouseEvent, QPointF
                local = QPointF(x, y)
                event = QMouseEvent(kind, local, QPointF(c.mapToGlobal(local.toPoint())), button,
                                    Qt.MouseButton.LeftButton if kind != QEvent.Type.MouseButtonRelease
                                    else Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier)
                # Straight to the chart's own handlers: the click filters (open the
                # browser, move the widget) never see these.
                if kind == QEvent.Type.MouseButtonPress:
                    c.mousePressEvent(event)
                elif kind == QEvent.Type.MouseMove:
                    c.mouseMoveEvent(event)
                else:
                    c.mouseReleaseEvent(event)

            def alive():
                return (token == self._zoom_token and _tour is self
                        and self._steps[self._i][3] == "zoom")

            def step(k):
                try:
                    if not alive():
                        return
                    if k == 0:
                        at(xa)
                        return QTimer.singleShot(200, lambda: step(1))
                    if k == 1:
                        self._zoomed = c
                        send(QEvent.Type.MouseButtonPress, xa, Qt.MouseButton.LeftButton)
                        return QTimer.singleShot(40, lambda: step(2))
                    moves = 10
                    if k < 2 + moves:
                        x = xa + (xb - xa) * (k - 1) / moves
                        at(x)
                        send(QEvent.Type.MouseMove, x, Qt.MouseButton.NoButton)
                        return QTimer.singleShot(30, lambda: step(k + 1))
                    if k == 2 + moves:
                        return QTimer.singleShot(150, lambda: step(k + 1))
                    send(QEvent.Type.MouseButtonRelease, xb, Qt.MouseButton.LeftButton)
                    pointer.hide()
                    if not getattr(c, "_is_zoomed", False):
                        # This chart did not take the zone: zoom on the same part directly.
                        from ..chart_utils.zoom_camera import camera_zoom
                        a, b = int(n * 0.42), max(int(n * 0.42) + 3, int(n * 0.72))
                        with camera_zoom(c):
                            c.set_zoom_range(a, min(n, b))
                    QTimer.singleShot(1900, lambda: alive() and self._zoom_reset())
                except RuntimeError:
                    pass
                except Exception:
                    log_swallowed()

            step(0)
        except Exception:
            log_swallowed()

    def _zoom_reset(self):
        c, self._zoomed = self._zoomed, None
        if c is None:
            return
        try:
            if getattr(c, "_selecting", False):
                c._selecting = False
                c.update()
            if getattr(c, "_is_zoomed", False):
                c.reset_zoom()
        except RuntimeError:
            pass
        except Exception:
            log_swallowed()

    def _place(self, target_fn=None, move_card=True, instant=False):
        if target_fn is None:
            target_fn = self._steps[self._i][1]
        r = target_fn(self._win)
        hole = r.adjusted(-self.PAD, -self.PAD, self.PAD, self.PAD) if r is not None else None
        if instant:
            self._hole_anim.stop()
            self._hole = hole
        else:
            self._set_hole(hole)
        if not move_card:
            self._card.raise_()
            self.update()
            return
        self._card.adjustSize()
        cw, ch = self._card.width(), self._card.height()
        W, H = self.width(), self.height()
        h = self._hole_to if self._hole_anim.state() == self._hole_anim.State.Running else self._hole
        if h is None:
            x, y = (W - cw) // 2, (H - ch) // 2
        else:
            x = h.center().x() - cw // 2
            # Steps whose examples change size: the card goes where every example leaves it
            # room, so it stays put the whole time (the layouts at the bottom of the window).
            action = self._steps[self._i][3]
            slack = _CARD_SLACK.get(action, 0)
            if action == "layouts":
                # Not all measured (Next clicked right away): under the tallest seen so far,
                # the card then slides down if a taller one comes (see _thaw).
                tallest = _layout_heights.get((W, H)) or _layout_partial.get((W, H))
                slack = 0 if tallest is None else max(0, tallest - h.height())
            if h.bottom() + 12 + ch <= H - 8:
                y = min(h.bottom() + 12 + slack, H - ch - 8)
            elif h.top() - 12 - ch >= 8:
                y = h.top() - 12 - ch
            else:
                # A big target (all the widgets): the card goes over its lower part.
                y = min(H - ch - 8, max(8, h.bottom() - ch - 12))
        self._card.move(max(8, min(x, W - cw - 8)), max(8, min(y, H - ch - 8)))
        if self._steps[self._i][3] in ("menu", "edit", "add", "spans"):
            try:
                area = self._menu_area() if self._steps[self._i][3] in ("menu", "edit") else self._add_area()
                if area is not None:
                    self._card_clear_of(area)
            except Exception:
                log_swallowed()
        self._card.raise_()
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        shade = QPainterPath()
        shade.addRect(QRectF(self.rect()))
        if self._hole is not None:
            hole = QPainterPath()
            hole.addRoundedRect(QRectF(self._hole), 12, 12)
            shade = shade.subtracted(hole)
        p.fillPath(shade, QColor(0, 0, 0, 150))
        if self._hole is not None:
            pen = QPen(self._accent)
            pen.setWidthF(2.0)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(QRectF(self._hole).adjusted(1, 1, -1, -1), 12, 12)
        p.end()

    # Clicks on the shaded part do nothing: the tour waits for its buttons.
    def mousePressEvent(self, event):
        event.accept()

    def wheelEvent(self, event):
        event.accept()

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.close_tour()
        elif self._busy:
            event.accept()
        elif key in (Qt.Key.Key_Right, Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self._go(self._i + 1)
        elif key == Qt.Key.Key_Left and self._i > 0:
            self._go(self._i - 1)
        else:
            event.accept()

    def eventFilter(self, obj, event):
        if obj is self._win and event.type() == QEvent.Type.Resize:
            try:
                self.setGeometry(self._win.rect())
                QTimer.singleShot(0, self._place)
            except RuntimeError:
                pass
        return False

    def close_tour(self):
        global _tour
        try:
            self._win.removeEventFilter(self)
        except RuntimeError:
            pass
        self._top_timer.stop()
        self._measuring = False
        self._intro_measuring = False
        self._pending_go = None
        self._stop_action()
        self._drop_gallery()
        _end_demo()
        _tour = None
        try:
            QTimer.singleShot(300, lambda w=self._win: _Toast(w))
        except Exception:
            log_swallowed()
        # Give the focus back before hiding: otherwise Qt hands it to the next widget as a
        # Tab would, and the deck list shows its first "+" as selected.
        # The widget that had it may be gone (a pinned widget rebuilt by a demo): then the
        # page gets it, as after a click.
        target = None
        try:
            prev = getattr(self, "_prev_focus", None)
            if prev is not None and prev is not self and prev.isVisible():
                target = prev
        except RuntimeError:
            target = None
        if target is None:
            target = getattr(self._win, "web", None) or self._win
        try:
            self.clearFocus()
            target.setFocus(Qt.FocusReason.OtherFocusReason)
        except RuntimeError:
            pass
        self.hide()
        self.deleteLater()


class _Toast(QFrame):
    """A short note after the tour, pointing at the Deep Dive menu. It covers nothing and
    lets every click through."""

    def __init__(self, win):
        super().__init__(win)
        self.setObjectName("dd_tour_toast")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        set_qss(self,
            "QFrame#dd_tour_toast { background: rgba(32, 33, 38, 240); border: 1px solid rgba(255, 255, 255, 45);"
            " border-radius: 8px; }"
            "QLabel { color: #f2f2f2; background: transparent; font-size: 12px; }")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 8)
        lab = QLabel(tr("You can see this tour again from the Deep Dive menu: {entry}.", entry=tr("Guided Tour")))
        lab.setWordWrap(True)
        lab.setMaximumWidth(320)
        lay.addWidget(lab)
        self.adjustSize()
        r = _target_menu(win)
        if r is not None:
            self.move(max(8, min(r.left(), win.width() - self.width() - 8)), r.bottom() + 6)
        else:
            self.move(max(8, (win.width() - self.width()) // 2), 8)
        self.show()
        self.raise_()
        QTimer.singleShot(5000, self._close)

    def _close(self):
        try:
            self.hide()
            self.deleteLater()
        except RuntimeError:
            pass


# -- starting ------------------------------------------------------------------------

def _main_window():
    try:
        from aqt import mw
        return mw
    except Exception:
        return None


def start_tour(force=False):
    """Show the tour now (force: from the menu, even if it was seen)."""
    global _tour
    win = _main_window()
    if win is None or _tour is not None:
        return False
    if not force and _is_done():
        return False
    try:
        # The layouts depend on the collection (the all years one needs a few years of
        # reviews): heights measured for another list do not hold.
        before = list(_LAYOUT_SCENES)
        _refresh_layout_scenes()
        if list(_LAYOUT_SCENES) != before:
            _layout_heights.clear()
            _layout_partial.clear()
        tour = _Tour(win)
        if not tour.has_steps():
            tour.deleteLater()
            return False
        _mark_done()
        _tour = tour
        tour.start()
        return True
    except Exception:
        log_swallowed()
        return False


def start_from_menu():
    """Menu entry: back to the main screen (where the pinned widgets are), then the tour."""
    win = _main_window()
    if win is None:
        return
    try:
        if getattr(win, "state", None) != "deckBrowser":
            win.moveToState("deckBrowser")
            QTimer.singleShot(1500, lambda: start_tour(force=True))
            return
    except Exception:
        log_swallowed()
    start_tour(force=True)


def _ready(win):
    try:
        return (
            getattr(win, "state", None) == "deckBrowser"
            and win.isActiveWindow()
            and QApplication.activeModalWidget() is None
            and QApplication.activePopupWidget() is None
            and bool(_pinned_widgets())
            and _pinned_placed()
        )
    except RuntimeError:
        return False


def _pinned_placed():
    """The pinned area has its place in the page (the page told where): before that, its
    widgets can be built but not drawn where they show."""
    try:
        from ..pinned.main_menu.manager import MainMenuWidgetManager
        if not MainMenuWidgetManager.instance_exists():
            return False
        manager = MainMenuWidgetManager.instance()
        overlay = getattr(manager, "_overlay", None)
        return (overlay is not None and overlay.isVisible()
                and getattr(manager, "_last_placeholder_css_rect", None) is not None)
    except RuntimeError:
        return False


def _try_first_start():
    global _scheduled, _tries
    _scheduled = False
    if _is_done() or _tour is not None:
        return
    win = _main_window()
    if win is not None and _ready(win):
        log_info(f"First start: {len(_pinned_widgets())} pinned widgets shown.", tag="TOUR")
        start_tour()
        return
    _tries += 1
    if _tries < _MAX_TRIES:
        _scheduled = True
        QTimer.singleShot(_RETRY_MS, _try_first_start)


def attach_guided_tour(widget):
    """A pinned widget was built: remember it (the tour points at it) and, the first time,
    plan the tour once the screen has settled."""
    global _scheduled, _restored
    if widget is None:
        return
    if not _restored:
        _restored = True
        restore_after_crash()
    try:
        _pinned.add(widget)
    except TypeError:
        return
    if not _scheduled and not _is_done():
        _scheduled = True
        QTimer.singleShot(_FIRST_DELAY_MS, _try_first_start)
