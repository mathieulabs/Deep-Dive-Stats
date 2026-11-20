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

from aqt.qt import QPoint, QRect, QTimer, QWidget

from ...logic.logger import log_swallowed
from ...logic.user_state import load_state, save_state, state_path
from ....i18n import tr

_KEY = "guided_tour"
_FIRST_DELAY_MS = 2500
_RETRY_MS = 4000
_MAX_TRIES = 150  # 10 minutes: a first cache build of a big collection can take that long

_done = None
_pinned = weakref.WeakSet()
_tour = None


# -- state ---------------------------------------------------------------------------


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


def _span_widget():
    """The chart whose time span the span step changes: Activity when it is pinned."""
    charts = [w for w in _pinned_widgets() if _is_chart(w) and not _is_heatmap(w)]
    # Charts over time first: their look changes with the span (card counts would not).
    for names in (("ActivityChart", "ActivityStackedChart"), ("RetentionChart",), ("AddedChartWidget",)):
        for w in charts:
            if any(type(c).__name__ in names for c in w.findChildren(QWidget)):
                return w
    return charts[0] if charts else None


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
        ) + " " + tr(
            "Over a background image, the boxes can be see-through and blurred too: lower Background Opacity and "
            "raise Background Blur in {settings}.", settings=tr("Settings"),
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


def _touch_texts():
    """The texts of the steps that name a mouse gesture, for a touch screen (Kioku), by step action: hold where the
    mouse right clicks, pinch where it drags or scrolls, the "+ Add Widget" button where the end of line + shows."""
    settings = tr("Settings")
    return {
        "add": tr(
            "To add one, tap {button} under your widgets, or hold a widget and choose {add}. In the Deep Dive "
            "window, the pin next to a chart's title puts it here.",
            button="+ " + tr("Add Widget"), add=tr("Add Widget...").rstrip(".…"),
        ),
        "themes": tr(
            "You can change the colors too: one theme for every widget, or a color per chart or stat "
            "(hold it, then its color or {settings}).", settings=settings,
        ) + " " + tr(
            "Over a background image, the boxes can be see-through and blurred too: lower Background Opacity and "
            "raise Background Blur in {settings}.", settings=settings,
        ),
        "texts": tr(
            "The text widget lets you write your own sentence with live stats in it, like today's reviews, "
            "your streak or your retention. Hold it, then {edit}.", edit=tr("Edit Text and Settings...").rstrip(".…"),
        ),
        "menu": tr("Hold a widget (or tap ⋯) for all its options."),
        "spans": tr(
            "Each widget can have its own deck and time span. Tap the label next to a chart's title, "
            "or hold the widget, then {decks} or {span}.",
            decks=tr("Select Decks...").rstrip(".…"), span=tr("Time Span"),
        ),
        "zoom": tr(
            "Pinch a chart with two fingers to zoom in, or use + and − under it. The ↺ button goes back to the "
            "full view."
        ),
        "swap": tr(
            "Hold a widget, then drag it onto another line, or between two lines to start a new one. Hold it near "
            "its right or bottom edge to resize it."
        ),
    }


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
        m.refresh()
    except Exception:
        log_swallowed()


def _stat(stat_key, **extra):
    from ...logic.stat_cards import get_stat_card_name
    d = {"id": f"tour-{stat_key}", "type": "stat_card", "label": get_stat_card_name(stat_key), "stat_key": stat_key}
    d.update(extra)
    return d


def _chart(wtype, **extra):
    from ...ui.config.widgets.label_defaults import DEFAULT_LABELS
    d = {"id": f"tour-{wtype}", "type": wtype, "label": DEFAULT_LABELS.get(wtype, wtype), "stat_key": None}
    d.update(extra)
    return d


def _demo_text_templates():
    """A few things the text widget can show, its variables filled in live: a small table of colored numbers,
    titles, lists, lines, colors, sizes, italic... then two plain sentences."""
    center = '<p align="center">'
    blue, green, orange, purple, teal = "#3b82f6", "#16a34a", "#ea8a2e", "#8b5cf6", "#0ea5a4"

    def big(value, color, size=24):
        return f'<span style="font-size:{size}pt; font-weight:800; color:{color};">{value}</span>'

    def bold(value, color):
        return f'<b style="color:{color};">{value}</b>'

    def small(text, size=10):
        return f'<span style="font-size:{size}pt; opacity:0.7;">{text}</span>'

    def caps(text):  # a small title in capitals, spaced out
        return (f'{center}<span style="font-size:10pt; font-weight:700; letter-spacing:2px; text-transform:uppercase; '
                f'opacity:0.65;">{text}</span></p>')

    def title(tag, text, size, align=' align="center"'):
        return f'<{tag}{align}><span style="font-size:{size}pt; font-weight:700;">{text}</span></{tag}>'

    def cell(value, color, label):
        return (f'<td align="center" style="padding:2px 16px;">{big(value, color)}<br/>{small(label)}</td>')

    def row(dot, label, value, first=False):
        line = "" if first else " border-top:1px solid rgba(128,128,128,0.25);"
        return (f'<tr><td style="padding:5px 22px 5px 0; font-size:12pt;{line}"><span style="color:{dot};">●</span> '
                f'{label}</td><td align="right" style="padding:5px 0; font-size:13pt; font-weight:700;{line}">'
                f'{value}</td></tr>')

    def item(text):
        return f'<li style="font-size:12.5pt; margin:2px 0;">{text}</li>'

    table = '<table align="center" style="border-collapse:collapse; margin:4px auto;">'
    return [
        # today at a glance: three numbers side by side in a small table
        caps(tr("Today")) + table + "<tr>"
        + cell("{reviews:Today}", blue, tr("reviews")) + cell("{total_time:Today}", green, tr("studied"))
        + cell("{due_today}", orange, tr("due")) + "</tr></table>",
        # a title over a table with colored dots, the numbers to the right
        title("h3", tr("Retention"), 16, "") + '<table style="border-collapse:collapse;">'
        + row(green, tr("Young cards"), "{ret_young}", first=True) + row(blue, tr("Mature cards"), "{ret_mat}")
        + row(purple, tr("All cards"), "{ret_all}") + "</table>",
        # a week's report: a title, a line, a list of colored numbers
        title("h2", tr("This week"), 18) + "<hr />" + "<ul>"
        + item(tr("{n} reviews", n=bold("{reviews:week}", blue)))
        + item(tr("{n} of study", n=bold("{total_time:week}", green)))
        + item(tr("{n} reviews a day on average", n=bold("{reviews_per_day:week}", orange))) + "</ul>",
        # a streak badge: a big colored number, a line, the record underneath
        center + '<span style="font-size:28pt;">🔥</span> ' + big("{streak}", orange, 30)
        + f'<br/><span style="font-size:12pt; font-weight:600;">{tr("days in a row")}</span></p><hr />'
        + center + small(tr("Longest streak") + ": <b>{longest_streak}</b> · " + tr("Active days") + ": <b>{active_days}</b>", 10.5)
        + "</p>",
        # the collection: a numbered list in the colors of the card states
        title("h3", tr("Cards"), 16) + "<ol>"
        + item(bold("{cards_new}", blue) + " " + tr("New")) + item(bold("{cards_learning}", orange) + " " + tr("Learning"))
        + item(bold("{cards_young}", teal) + " " + tr("Young")) + item(bold("{cards_mature}", green) + " " + tr("Mature"))
        + "</ol>" + center + small("<u>" + tr("{n} in all", n="{cards_total}") + "</u>", 11) + "</p>",
        # and two sentences as they were: sizes of their own
        center + '<span style=" font-size:15pt; font-weight:700;">' + tr("{reviews:Today} reviews today")
        + '</span><br/><span style=" font-size:11pt;">'
        + tr("Streak: {streak} days · young retention: {ret_young}") + "</span></p>",
        center + '<span style=" font-size:24pt; font-weight:800;">{reviews:month}</span><br/>'
        + '<span style=" font-size:11pt;">' + tr("reviews this month") + "</span></p>",
    ]


_TEXT_SCENES = tuple(f"text{i}" for i in range(1, 8))  # one per _demo_text_templates()


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
        from ...logic.widget_registry import place_after

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
            Config.HEATMAP_PALETTE: "",
        })
        # Clear temporary per-widget palette/color overrides so the heatmap and charts follow the demo theme
        cleaned = []
        for w in pins:
            w = dict(w)
            w.pop(Config.HEATMAP_PALETTE, None)
            w.pop("own_colors", None)
            cleaned.append(w)
        cfg[Config.PINNED_WIDGETS] = cleaned
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
        # next one (otherwise the same chart with another span or toggle shows the old one's state).
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
    from ...logic.pinned_layout import charts_section_key, normalize_block_order

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
    from ...logic.pinned_layout import normalize_block_order

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


# -- overlay -------------------------------------------------------------------------


# -- starting ------------------------------------------------------------------------


def _cache_busy():
    """The history cache is still being built in the background (a first install): its
    work there slows the whole interface (the animations of the tour stutter, the widgets
    change size as their data comes), so the tour waits for it."""
    try:
        from ...logic.history_cache import GlobalHistoryCache

        cache = getattr(GlobalHistoryCache, "_instance", None)
        if cache is None:
            return True
        # Not the warmup of every deck that follows (minutes on a big collection): it
        # waits while the tour plays (see _pause_warmup), the decks shown load on demand.
        return bool(not cache.is_initialized or cache._is_initializing or getattr(cache, "_fsrs_pending", False))
    except Exception:
        return False


def _pause_warmup(on):
    """The background warmup of every deck stands still while the tour plays: its work
    slows the interface (the animations stutter)."""
    try:
        from ...logic.history_cache import GlobalHistoryCache

        cache = getattr(GlobalHistoryCache, "_instance", None)
        if cache is not None:
            cache._warmup_paused = bool(on)
    except Exception:
        log_swallowed()


