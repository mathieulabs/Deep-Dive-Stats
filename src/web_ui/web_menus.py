# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""The main screen's menus, built as the page's entries (app.js DD.menu): a pinned widget's right click, its chart's
own options (its header's options icon) and the period list of a card's label.

An entry is [key, label, checked, icon, mode, submenu, disabled] or "sep" (app.js menu). Each key is kept with
what a click on it does until the next menu: the page sends the key back (pick), its action runs here.
"""

from __future__ import annotations

import html
import json

from aqt import mw
from aqt.qt import QTimer

from ..const import Period
from ..const.config import Config
from ..details.logic.logger import log_error, log_swallowed, log_warn
from ..i18n import N_, tr, tr_name

_m = {"acts": {}, "parent": {}, "items": [], "wid": None, "build": None, "own": False}


class _Menu:
    """Entries being built: items (the menu's), own (its chart's own entries), acts {key: fn(on)}."""

    def __init__(self):
        self.items, self.own, self.acts, self.parent = [], [], {}, {}
        self._n = 0
        self._own = False

    def _key(self):
        self._n += 1
        return "k%d" % self._n

    def _put(self, into, entry, own=None):
        into.append(entry)
        if into is self.items and (self._own if own is None else own):
            self.own.append(entry)

    def sep(self, into=None):
        self._put(self.items if into is None else into, "sep")

    def act(self, label, fn, icon=None, into=None, disabled=False, own=None, key=None):
        """An entry that closes the menu; fn() runs once it has closed."""
        k = key or self._key()
        self.acts[k] = (lambda _on, f=fn: f(), False)
        self._put(self.items if into is None else into, [k, html.escape(label), None, icon, None, None, bool(disabled)], own)
        return k

    def check(self, label, on, fn, into=None, disabled=False, own=None):
        """A tick that keeps the menu open; fn(checked)."""
        k = self._key()
        self.acts[k] = (lambda v, f=fn: f(bool(v)), True)
        self._put(self.items if into is None else into, [k, html.escape(label), bool(on), None, True, None, bool(disabled)], own)
        return k

    def radio(self, choices, now, fn, into):
        """One of a choice ([(value, label)]), the menu kept open; fn(value)."""
        for value, label in choices:
            k = self._key()
            self.acts[k] = (lambda _on, f=fn, v=value: f(v), True)
            into.append([k, html.escape(label), value == now, None, "radio", None, False])

    def note(self, label, into):
        """A line of text (a hint, a heading), never clicked."""
        into.append([self._key(), html.escape(label), None, None, None, None, True])

    def sub(self, label, icon=None, into=None, disabled=False, own=None):
        """A submenu: its list, to fill."""
        k, inner = self._key(), []
        self._put(self.items if into is None else into, [k, html.escape(label), None, icon, None, inner, bool(disabled)], own)
        return inner

    def own_on(self, on):
        self._own = on

    def done(self):
        # each entry's top submenu, for the menu shown again with it open (_again)
        def walk(items, top):
            for it in items:
                if isinstance(it, list):
                    self.parent[it[0]] = top
                    if it[5]:
                        walk(it[5], top or it[0])

        walk(self.items, None)
        return self


def _clean(items):
    """No separator first, last or twice in a row."""
    out = []
    for it in items:
        if it == "sep" and (not out or out[-1] == "sep"):
            continue
        out.append(it)
    while out and out[-1] == "sep":
        out.pop()
    return out


# ---- what the entries do ------------------------------------------------------------------------------------------
def _manager():
    from ..details.widgets.pinned.main_menu.manager import MainMenuWidgetManager

    m = MainMenuWidgetManager.instance()
    m._config_manager = m._get_config_manager(force_refresh=True)
    return m


def _write(m, key, value):
    m._config_manager.set_value(key, value)


def _page_eval(js):
    from . import pinned as P

    try:
        _deck, browser = P._page()
        web = mw.deckBrowser.web if browser else mw.overview.web
        web.eval(js)
    except Exception:
        log_swallowed()


def _open_details(m, d):
    """The Deep Dive on the deck(s) and period this widget shows."""
    try:
        from ..details.widgets.pinned.widget_factory.utils import _resolve_deck_ids
        from ..startup import open_details_for

        context_deck = getattr(m, "_current_deck_id", None)
        if "deck_ids" in d:
            deck = _resolve_deck_ids(d["deck_ids"], context_deck)
        elif "deck_id" in d:
            deck = d["deck_id"]
        else:
            deck = context_deck
        if isinstance(deck, str):
            deck = None
        span = m._normalized_widget_def(d).get("time_span")
        if span == Period.CUSTOM or d.get("type") == "text_label":
            span = None
        open_details_for(deck, span)
    except Exception:
        log_swallowed()


def _view(m, d):
    from ..details.logic.widget_registry import WidgetRegistry
    from ..details.widgets.pinned import PinnedViewSelectorDialog
    from . import pinned as P

    dialog = PinnedViewSelectorDialog(d.get("view_dids", None), parent=P._proxy(d))
    if dialog.exec():
        WidgetRegistry.update_setting(d["id"], "view_dids", dialog.selected_values)
        m.refresh()


def _zoom_link(wid, on, all_ids=None):
    """The page's charts zoomed together or not (pinned._UNLINKED: the ones left out)."""
    from . import pinned as P

    for i in (all_ids if all_ids is not None else [wid]):
        if on:
            P._UNLINKED.pop(i, None)
        else:
            P._UNLINKED[i] = True
    P._push_unlinked()


# ---- the period list ----------------------------------------------------------------------------------------------
def _spans(m):
    """[(label, value, days)]: the user's time spans (Settings > Time Span), each period once."""
    from ..details.logic.tabs import get_tabs_config

    out, seen = [], set()
    for tab in get_tabs_config(m._config_manager):
        r = tab.get("range")
        if r is None:
            continue
        days = tab.get("days") if r == Period.CUSTOM else None
        if r != Period.CUSTOM:
            if r in seen:
                continue
            seen.add(r)
        out.append((tr_name(tab.get("title") or N_("Stats")), int(r), days))
    return out


def _fill_spans(mn, m, d, into):
    """A widget's periods, then Add New Time Span and Apply to all widgets (card_chips: what they change)."""
    from ..details.logic.widget_registry import WidgetRegistry
    from ..details.widgets.pinned.main_menu.ui.card_chips import _latest, apply_span_to_all, has_time_span, set_span

    d = _latest(d)
    now, now_days = int(d.get("time_span", Period.TOTAL)), d.get("custom_days", None)
    spans, shown = _spans(m), False
    for label, value, days in spans:
        on = now == value and (value != Period.CUSTOM or days is None or now_days == days)
        shown = shown or on
        k = "s:%d:%s" % (value, "" if days is None else days)  # (the guided tour finds a period by it)
        mn.acts[k] = (lambda _on, v=value, n=days: set_span(m, d, v, n), True)
        into.append([k, html.escape(label), on, None, "radio", None, False])
    if not shown and has_time_span(d):
        # the widget's own period, not among the user's time spans (Past 3 Months, a span taken out of the
        # settings since): listed too, checked, else the menu showed none of its periods as the current one
        from . import pinned as P

        label = P._span_label(d)
        if label:
            days = now_days if now == Period.CUSTOM else None
            k = "s:%d:%s" % (now, "" if days is None else days)
            mn.acts[k] = (lambda _on, v=now, n=days: set_span(m, d, v, n), True)
            into.append([k, html.escape(label), True, None, "radio", None, False])
    mn.sep(into)
    mn.act(tr("Add New Time Span"), m._open_time_span_settings, icon="plus", into=into)
    if sum(1 for x in WidgetRegistry.get_all() if has_time_span(x)) > 1:
        mn.act(tr("Apply to all widgets"), lambda: apply_span_to_all(m, d), icon="copy", into=into)


def span_menu(d):
    """The period list of a card's label, then Hide these labels."""
    from ..details.widgets.pinned.main_menu.ui.card_chips import hide_card_labels

    m = _manager()
    mn = _Menu()
    _fill_spans(mn, m, d, mn.items)
    mn.sep()
    mn.act(tr("Hide these labels"), lambda: hide_card_labels(m))
    return mn.done()


# ---- the right click ----------------------------------------------------------------------------------------------
_AVERAGE = ("activity", "added", "retention")
_CUMULATIVE = ("activity", "added", "future_due", "review_intervals", "stability")
_TREND = ("activity", "added", "ratings", "review_speed", "forgotten", "resets", "introduced", "introduced_load",
          "load_trend", "stability_trend", "memorised", "card_states", "future_retention", "answer_time",
          "interval_ratings", "rating_fatigue", "fsrs_fatigue", "sibling_ratings")
_STATS = ("activity", "added", "hourly", "future_due", "review_intervals", "stability", "difficulty",
          "retrievability", "retention")
_BINNING = ("activity", "added", "retention", "future_due", "review_intervals", "stability", "difficulty",
            "retrievability")


def _hidden_parts(mn, m, d, choices, key, title, into):
    """A submenu of the parts a chart shows (choices [(key, label)]), the hidden ones saved under key; one stays on."""
    hidden = {k for k in (d.get(key) or []) if k in {c for c, _ in choices}}
    sub = mn.sub(title, into=into)
    for part, label in choices:
        shown = part not in hidden

        def toggle(on, p=part):
            new = (hidden - {p}) if on else (hidden | {p})
            m._update_setting(d["id"], key, [c for c, _ in choices if c in new] or None)

        mn.check(tr_name(label), shown, toggle, into=sub, disabled=shown and len(choices) - len(hidden) <= 1)


def _stat_card(mn, m, d, cfg):
    from ..details.logic.stat_cards import active_day_twin
    from ..details.logic.widget_registry import WidgetRegistry

    twin = active_day_twin(d.get("stat_key"))
    if twin:
        # each click follows the box (checked: the active-days card), not the card the menu was opened on
        every_day, active = (d.get("stat_key"), twin[0]) if not twin[1] else (twin[0], d.get("stat_key"))

        def swap(on):
            WidgetRegistry.update_setting(d["id"], "stat_key", active if on else every_day)
            m.refresh(clear_cache=False)

        mn.check(tr("Active days only"), twin[1], swap)

    def global_(key):
        def put(v):
            _write(m, key, v)
            m.refresh(clear_cache=False)
        return put

    # how the stat cards' numbers change (one setting for every stat card, also in Settings > General > Animations)
    sub = mn.sub(tr("Number Animation"))
    mn.radio((("count", tr("Numbers count")), ("roll", tr("Digits roll"))),
             "roll" if cfg.get(Config.STAT_NUM_ANIM) == "roll" else "count", global_(Config.STAT_NUM_ANIM), sub)

    # the icon's style and place: this card's own with its own style, else every card's
    own = bool(d.get("use_custom_style", False))

    def of(key, default):
        return d.get(key) if (own and key in d) else cfg.get(key, default)

    def put(key):
        def put_(v):
            if own:
                WidgetRegistry.update_setting(d["id"], key, v)
            else:
                _write(m, key, v)
            m.refresh(clear_cache=False)
        return put_

    raw = of(Config.FACECARDS_SHOW_ICONS, "inline")
    ico = "off" if raw in (False, "", "off", None) else ("watermark" if raw == "watermark" else "inline")
    sub = mn.sub(tr("Icon"))
    mn.radio((("off", tr("Off")), ("inline", tr("Next to title")), ("watermark", tr("Watermark"))), ico,
             put(Config.FACECARDS_SHOW_ICONS), sub)
    mn.sep(sub)
    pos = of(Config.FACECARDS_ICON_POS, "tl")
    where = mn.sub(tr("Position"), into=sub, disabled=ico != "watermark")
    mn.radio((("tl", tr("Top Left")), ("tr", tr("Top Right")), ("bl", tr("Bottom Left")), ("br", tr("Bottom Right"))),
             pos if pos in ("tl", "tr", "bl", "br") else "tl", put(Config.FACECARDS_ICON_POS), where)


def _heatmap(mn, m, d, cfg):
    from ..const.theme.color_resolver import get_color
    from ..details.widgets.charts.heatmap.metrics import METRICS, TYPE_KEYS, TYPE_METRICS, build_metric, metric_parts
    from ..details.widgets.charts.heatmap.palettes import CUSTOM, PALETTES, customs_of, palette_of, seed_colors

    def put(key):
        def put_(v):
            _write(m, key, v)
            m.refresh(clear_cache=False)
        return put_

    pal = palette_of(cfg.get)

    def pick_color():
        from ..details.ui.config.shared.color_picker import pick_color_live
        from ..details.widgets.charts.heatmap.palettes import colors_of
        from .pinned import eval_block

        cur = get_color(cfg, Config.HEATMAP_COLOR, "pinned")
        pal_colors, mine_ = colors_of(cfg.get), customs_of(cfg.get)

        def show(h, p=""):  # the main screen's heatmaps redrawn as the color changes
            try:
                eval_block("window.DDP&&DDP.heatmapPalette&&DDP.heatmapPalette(%s)" % json.dumps(
                    {"color": h, "palette": p, "palette_colors": pal_colors if p else None, "custom_palettes": mine_}))
            except Exception:
                log_swallowed()

        chosen = pick_color_live(mw, cur, tr("Pick Color"), show)
        if not chosen:
            if pal:  # cancelled: the palette shown again (the picker put the color back)
                show(cur, pal)
            return
        # the pinned theme's own colors are read only when both are on (color_resolver)
        if cfg.get(Config.PINNED_USE_ACTIVE_THEME, False) and cfg.get(Config.PINNED_USE_SEPARATE_THEME, False):
            custom = dict(cfg.get(Config.PINNED_THEME_CUSTOM_COLORS, {}) or {})
            custom[Config.HEATMAP_COLOR] = chosen
            _write(m, Config.PINNED_THEME_CUSTOM_COLORS, custom)
            _write(m, Config.PINNED_THEME_IS_CUSTOM, True)
        else:
            _write(m, Config.HEATMAP_COLOR, chosen)
        if pal:
            _write(m, Config.HEATMAP_PALETTE, "")
        m.refresh(clear_cache=False)

    mn.act(tr("Color..."), pick_color, icon=get_color(cfg, Config.HEATMAP_COLOR, "pinned"))

    # the levels' palette; the user's own gradients after a line
    mine = customs_of(cfg.get)
    sub = mn.sub(tr("Palette"))
    mn.radio([(k, tr_name(label)) for k, label in PALETTES], pal, put(Config.HEATMAP_PALETTE), sub)
    if mine:
        mn.sep(sub)
        mn.radio([(CUSTOM + p["id"], p["name"]) for p in mine], pal, put(Config.HEATMAP_PALETTE), sub)

    def gradient(new):
        from ..details.ui.config.dialogs.heatmap_gradient import edit_gradient
        from ..details.ui.theme import get_theme_effective_is_dark

        seed = None
        if new:
            seed = seed_colors(pal, mine, get_color(cfg, Config.HEATMAP_COLOR, "pinned"),
                               dark=get_theme_effective_is_dark(cfg))
        edit_gradient(mw, cfg, lambda k, v: _write(m, k, v), lambda: m.refresh(clear_cache=False), new=new, seed=seed)

    mn.sep(sub)
    mn.act(tr("New gradient..."), lambda: gradient(True), into=sub)
    if pal.startswith(CUSTOM):
        mn.act(tr("Edit gradient..."), lambda: gradient(False), into=sub)
    # only the chosen color's shades
    mn.check(tr("Multicolor Intensity"), cfg.get(Config.HEATMAP_MULTI_HUE_INTENSITY, False),
             put(Config.HEATMAP_MULTI_HUE_INTENSITY), disabled=pal != "")

    # what the cells show: several measures can be checked (each scaled on its own, the cells their average)
    chosen = set(metric_parts(cfg.get(Config.HEATMAP_METRIC, "reviews")) or ["reviews"])
    sub = mn.sub(tr("Heatmap Shows"))

    def choose(parts):
        put(Config.HEATMAP_METRIC)(build_metric(parts))

    mn.note(tr("Check several to combine them"), sub)
    for key, label in METRICS:
        mn.check(tr_name(label), key in chosen, lambda _on, k=key: choose(chosen ^ {k}), into=sub)
    mn.sep(sub)
    mn.note(tr("Card types"), sub)
    mn.check(tr("All card types"), not (chosen & set(TYPE_KEYS)), lambda _on: choose(chosen - set(TYPE_KEYS)), into=sub)
    for key, label in TYPE_METRICS:
        mn.check(tr_name(label), key in chosen, lambda _on, k=key: choose(chosen ^ {k}), into=sub)
    mn.check(tr("Invert Intensity"), bool(cfg.get(Config.HEATMAP_INVERT_INTENSITY, False)),
             put(Config.HEATMAP_INVERT_INTENSITY))
    # this card's own: the year in two rows or the month grid when it is narrow (heatmap.js narrowOn)
    mn.check(tr("Adapt the year to narrow cards"), bool(d.get("narrow_layout", True)),
             lambda on: m._update_setting(d["id"], "narrow_layout", on))


def _chart(mn, m, d):
    """The entries of this chart alone (Legend Layout, Show Average, Series, Show as %, Show Trend...)."""
    from ..details.logic.data.transforms.activity_series import REVIEW_TYPE_CHOICES
    from ..details.logic.metrics.future_due import resolve_breakdown
    from ..details.widgets.charts.more_charts import AVERAGE_TYPES, CUMULATIVE_TYPES, PERCENT_TYPES

    wtype, wid = d.get("type"), d["id"]

    def setting(key):
        return lambda v: m._update_setting(wid, key, v)

    def toggle(label, key, default):
        mn.check(label, bool(d.get(key, default)), setting(key))

    if wtype in ("card_counts", "todays_retention"):
        mn.sep()
        sub = mn.sub(tr("Legend Layout"))
        mn.radio([(k, tr_name(n)) for k, n in (("auto", "Auto"), ("always", "Always next to the donut"),
                                               ("hover", "On hover"))],
                 d.get("legend_mode") or "auto", setting("legend_mode"), sub)

    if wtype == "todays_retention":
        mn.sep()
        sub = mn.sub(tr("Cards"))
        mn.radio([(k, tr_name(n)) for k, n in (("all", "All"), ("learn", "Learning"), ("young", "Young"),
                                               ("mature", "Mature"))],
                 d.get("card_type") or "all", setting("card_type"), sub)
        mn.check(tr("Show Change from Period Before"), d.get("show_change", True) is not False, setting("show_change"))
        try:
            fsrs = bool(mw.col.get_config("fsrs", False))
        except Exception:
            fsrs = False
        if fsrs:
            mn.check(tr("Show FSRS Target"), d.get("show_target", True) is not False, setting("show_target"))

    averages, cumulative = (*_AVERAGE, *AVERAGE_TYPES), (*_CUMULATIVE, *CUMULATIVE_TYPES)
    breakdown = resolve_breakdown(d.get("breakdown"), d.get("show_breakdown", False)) if wtype == "future_due" else None
    no_split = wtype == "card_states" and not d.get("alt_view", True)
    has_pct = ((wtype in PERCENT_TYPES and not no_split) or breakdown == "result"
               or (wtype == "activity" and d.get("show_breakdown", True)))
    has_trend = wtype in _TREND
    if wtype not in averages and wtype not in cumulative and breakdown != "type" and not has_pct and not has_trend:
        return
    mn.sep()
    if wtype in averages:
        toggle(tr("Show Average"), "show_average", True)
        toggle(tr("Average on active days"), "avg_on_active_days", True)
        if wtype == "retention":
            toggle(tr("Within data limit"), "fit_to_data", False)
            sub = mn.sub(tr("Review Bars"))
            bars = bool(d.get("review_bars", True))
            mn.check(tr("Show Bars"), bars, setting("review_bars"), into=sub)
            mn.check(tr("Show Count Axis"), bool(d.get("review_axis", False)), setting("review_axis"), into=sub,
                     disabled=not bars)
            toggle(tr("Rounded Look"), "rounded", True)
            now = int(d.get("min_reviews", 0) or 0)

            def ask_min():
                from ..details.ui.shared.number_dialog import ask_number

                value = ask_number(tr("Min Reviews"), tr("Hide points with fewer reviews than this (0 = show all):"), now,
                                   parent=mw)
                if value is not None:
                    m._update_setting(wid, "min_reviews", value)

            mn.act(tr("Min Reviews per Point: {value}...", value=now if now else tr("Off")), ask_min)
    if wtype == "activity":
        _hidden_parts(mn, m, d, REVIEW_TYPE_CHOICES, "hidden_review_types", tr("Review Types"), mn.items)
    if wtype in cumulative:
        toggle(tr("Show Total (Cumulative)"), "show_cumulative", True)
    # Series: the parts of the bars shown (Future Due by type); Show as %: each bar as the shares of its parts
    if breakdown == "type":
        _hidden_parts(mn, m, d, [("mature", "Mature"), ("young", "Young"), ("learn", "Learning")], "hidden_series",
                      tr("Series"), mn.items)
    if has_pct:
        toggle(tr("Show as %"), "show_percent", False)
    # Show Trend: a line through the bars, its slope in the header (web: extras.js TREND_UNIT)
    if has_trend:
        toggle(tr("Show Trend"), "show_trend", wtype not in ("activity", "added"))


def _save_as(d):
    """The widget saved by name (saved_widgets), its title or its chart's name offered."""
    from ..details.logic.widget_registry import WidgetRegistry

    wid = d.get("id")
    now = next((w for w in WidgetRegistry.get_all() if w.get("id") == wid), None) or d
    _ask_and_save(now, mw)


def _ask_and_save(defn, parent):
    """defn saved under the name asked (its title or its chart's name offered), told in a tooltip."""
    from aqt.utils import tooltip

    from ..details.logic import saved_widgets
    from ..details.ui.shared.number_dialog import ask_text
    from . import pinned as P

    try:
        offered = P._title(defn) or tr("Text Widget")
    except Exception:
        offered = tr("Text Widget") if defn.get("type") == "text_label" else str(defn.get("type") or "")
    name = ask_text(tr("Save Widget"), tr("Its name in Add Widget:"), offered, ok_text=tr("Save"),
                    parent=parent)
    if not name:
        return False
    _sid, replaced = saved_widgets.save(defn, name)
    tooltip(tr("Saved widget replaced: {name}", name=name) if replaced
            else tr("Saved in Add Widget: {name}", name=name), parent=parent)
    return True


# Deep Dive's chart settings that are about its own grid or window, not the chart (left out of a saved widget)
_DD_PLACE = {"col_span", "height", "height_scale", "time_span_idx", "label", "narrow_layout", "use_custom_style"}
# Deep Dive's names of a setting the pinned widgets keep under another one (pinned._KEYS)
_DD_TO_PINNED = {"breakdown_enabled": "show_breakdown", "visibility": "visible_series"}


def deep_dive_def(kind, wtype=None, key=None, label=None, wid=None, span=-1):
    """The definition a Deep Dive chart, stat card or text would have as a pinned widget, with its settings as the
    Deep Dive shows them (the pinned charts read the same names); None when it has none (a chart that cannot be
    pinned, a text gone)."""
    import copy

    from ..const.config import Config
    from ..config import addon_config as _addon_config

    if kind == "text":
        from . import providers

        t = providers.text_widgets().get(str(wid or ""))
        return None if t is None else {"type": "text_label", "label": "", "template": t.get("template") or ""}
    if kind == "stat":
        from ..details.logic.stat_cards import stat_card_label_to_save

        return {"type": "stat_card", "label": stat_card_label_to_save(str(key), str(label or key)),
                "stat_key": str(key), "time_span": int(span)}
    from ..details.logic.pinning import pin_info

    info = pin_info(str(wtype or ""))
    if info is None:
        return None
    root = _addon_config().config.get(Config.DEEP_DIVE_WIDGET_SETTINGS) or {}
    sets = root.get(f"{wtype}_g")
    if not isinstance(sets, dict):
        sets = root.get(wtype) if isinstance(root.get(wtype), dict) else {}
    out = {"type": info[0], "label": info[1], "time_span": int(span)}
    mgr = root.get("manager_g") or root.get("manager") or {}
    for k in ("show_average", "avg_on_active_days", "show_cumulative"):  # the header gear menu's shared choices
        if k in mgr:
            out[k] = copy.deepcopy(mgr[k])
    for k, v in sets.items():
        if k in _DD_PLACE or str(k).startswith("_"):
            continue
        out[_DD_TO_PINNED.get(k, k)] = copy.deepcopy(v)
    return out


def save_from_deep_dive(parent=None, **what):
    """Deep Dive's Save Widget As...: its chart, stat card or text saved by name, as the main screen's are."""
    defn = deep_dive_def(**what)
    if defn is None:
        from aqt.utils import tooltip

        tooltip(tr("This widget cannot be saved"), parent=parent or mw)
        return False
    return _ask_and_save(defn, parent or mw)


def context_menu(d):
    """A pinned widget's right-click menu, its chart's own entries marked (own)."""
    from ..details.widgets.charts.more_charts import TYPES as MORE_TYPES
    from ..details.widgets.common.chart_help import help_text
    from ..details.widgets.pinned.main_menu.ui.add_here import open_gallery_at
    from ..details.widgets.pinned.main_menu.ui.card_chips import choose_decks, has_time_span
    from . import pinned as P

    m = _manager()
    cfg = m._config_manager.config or {}
    wtype, wid = d.get("type"), d["id"]
    mn = _Menu()

    mn.act(tr("Open Details Window"), lambda: _open_details(m, d), icon="external")
    if wtype not in ("stat_card", "text_label"):
        mn.act(tr("Fullscreen"), lambda: _page_eval("window.DDP && DDP.fullscreen(%s)" % json.dumps(wid)),
               icon="maximize")

    # Add Widget...: the gallery, the widget picked going right after this one (or in a new box below it)
    from ..details.logic.pinned_layout import box_of, family, row_of

    target = {"kind": "after", "id": wid, "family": family(d), "box": box_of(d), "row": row_of(d)}
    mn.act(tr("Add Widget..."), lambda: open_gallery_at(m, target), icon="plus")
    mn.sep()
    is_text = wtype == "text_label"
    mn.act(tr("Edit Text and Settings...") if is_text else tr("Settings"),
           lambda: m._open_widget_settings(P._proxy(d), d), icon="filetext" if is_text else "gear")
    # Save Widget As...: kept by name, with all its settings, to add again from Add Widget (My Widgets)
    mn.act(tr("Save Widget As..."), lambda: _save_as(d), icon="save")
    if help_text(wtype):
        # the explanation shown by the page, where the menu was
        mn.act(tr("About This Chart"), lambda: _page_eval("window.DDP && DDP.showHelp && DDP.showHelp(%s)" % json.dumps(wid)),
               icon="help")
    mn.sep()

    if has_time_span(d):
        _fill_spans(mn, m, d, mn.sub(tr("Time Span"), icon="calendar"))
    ids = list(P._state.get("zoom_ids") or [])
    if wid in ids:
        linked = [i for i in ids if i not in P._UNLINKED]
        mine = wid not in P._UNLINKED
        mn.act(tr("Disconnect zoom") if mine else tr("Reconnect zoom"), lambda: _zoom_link(wid, not mine), icon="zoom")
        if len(ids) >= 2:
            if len(linked) >= 2 or (len(linked) == 1 and not mine):
                mn.act(tr("Disconnect all charts' zoom"), lambda: _zoom_link(wid, False, ids))
            if len(ids) > len(linked):
                mn.act(tr("Reconnect all charts' zoom"), lambda: _zoom_link(wid, True, ids))
    mn.act(tr("Select Decks..."), lambda: choose_decks(m, P._proxy(d), d), icon="layers")
    mn.act(tr("View..."), lambda: _view(m, d), icon="eye")

    if wtype == "stat_card":
        _stat_card(mn, m, d, cfg)
    mn.own_on(True)
    _chart(mn, m, d)
    if wtype == "heatmap":
        mn.sep()
        _heatmap(mn, m, d, cfg)
    mn.own_on(False)

    stats = (*_STATS, *MORE_TYPES)
    if wtype in stats:
        mn.sep()
        mn.check(tr("Show Bottom Stats (Global)"), cfg.get(Config.DEEP_DIVE_PINNED_SHOW_BOTTOM_STATS, False),
                 m._toggle_global_bottom_stats)
        mn.check(tr("Show Stats (Global)"), cfg.get(Config.DEEP_DIVE_PINNED_SHOW_STATS, True),
                 m._toggle_global_show_stats)
    if wtype in (*_BINNING, *MORE_TYPES) and wtype not in ("due_today", "week_hours"):  # 24 bars, a grid, every day
        mn.sep()
        over = d.get("binning_override", None)
        mn.check(tr("Adaptive Binning"), cfg.get(Config.ADAPTIVE_CHART_BINNING, True) if over is None else over,
                 lambda on: m._update_setting(wid, "binning_override", on), own=True)
    # the charts' axis animation (one setting for every chart, also in Settings > General > Animations)
    if wtype in stats or wtype == "distribution":
        sub = mn.sub(tr("Axis Animation"))

        def axis(v):
            _write(m, Config.CHART_AXIS_ANIM, v)
            m.refresh(clear_cache=False)

        mn.radio((("count", tr("Numbers count")), ("slide", tr("Ticks slide"))),
                 "count" if cfg.get(Config.CHART_AXIS_ANIM) == "count" else "slide", axis, sub)

    mn.sep()
    mn.act(tr("Remove from main menu"), lambda: m._unpin(wid), icon="trash")
    if d.get("width") or d.get("height"):
        mn.sep()
        mn.act(tr("Reset Size"), lambda: m._reset_widget_size(wid), icon="maximize")
    return mn.done()


# ---- the page's calls ---------------------------------------------------------------------------------------------
def _keep(mn, wid, build, own=False):
    _m.update(acts=mn.acts, parent=mn.parent, items=mn.items, wid=wid, build=build, own=own)


def context(wid, own=False, count=False):
    """The right-click menu of a pinned widget: {items, open}, or None. own: only its chart's own entries; count:
    their number, {n} (the menu not kept: one shown stays usable)."""
    from . import pinned as P

    try:
        d = P._def_of(wid)
        if d is None:
            return None
        mn = context_menu(d)
        own_items = _clean(mn.own)
        if count:
            n = sum(1 for it in own_items if it != "sep")
            if d.get("own_n") != n:  # kept: the next main screens draw its icon or not from the start
                try:
                    from ..details.logic.widget_registry import WidgetRegistry

                    WidgetRegistry.update_setting(wid, "own_n", n)
                except Exception as e:
                    log_warn(f"own options count not kept: {e!r}", tag="WEB")
            return {"n": n}
        _keep(mn, wid, lambda: context_menu(P._def_of(wid) or d), own=bool(own))
        return {"items": own_items if own else _clean(mn.items), "open": None}
    except Exception as e:
        log_error(f"web pinned menu: {e!r}")
        return None


def span(wid):
    """The period list of a card's label: {items}, or None."""
    from . import pinned as P

    try:
        d = P._def_of(wid)
        if d is None:
            return None
        mn = span_menu(d)
        _keep(mn, wid, lambda: span_menu(P._def_of(wid) or d))
        return {"items": _clean(mn.items), "open": None}
    except Exception as e:
        log_error(f"web pinned span menu: {e!r}")
        return None


def _ticks(items, out=None):
    """{key: (checked, disabled)} of every entry."""
    out = {} if out is None else out
    for it in items:
        if isinstance(it, list):
            out[it[0]] = (it[2], it[6])
            if it[5]:
                _ticks(it[5], out)
    return out


def pick(key, on=None):
    """The entry clicked: its action run (an entry that keeps the menu open, now; else once the page's call has its
    answer, a window it opens being modal). The main screen rebuilt if the settings changed."""
    from . import pinned as P

    got = _m["acts"].get(str(key))
    if got is None:
        return False
    fn, stays = got
    seen = {"c": P._config_snapshot()}

    def run():
        try:
            fn(on)
        except Exception as e:
            log_error(f"web pinned menu pick: {e!r}")
        if stays:
            _again(str(key), on)
        else:
            P.preview_styles()  # a settings window opened from the menu and cancelled: the saved looks again
        _check(seen)

    if stays:
        run()
    else:
        QTimer.singleShot(0, run)
    return True


def _again(key, on):
    """An entry that keeps the menu open may change other entries (All card types and the types, the last review
    type kept on): when the menu built again differs from what the page shows, it is shown again, the submenu of
    the entry open."""
    if _m["build"] is None:
        return
    shown = _ticks(_m["items"])
    if key in shown and on is not None:
        shown[key] = (bool(on), shown[key][1])
    try:
        mn = _m["build"]()
    except Exception as e:
        log_error(f"web pinned menu again: {e!r}")
        return
    old_flat = list(_flat(_m["items"]))
    new_flat = list(_flat(mn.items))
    radio = any(it[0] == key and it[4] == "radio" for it in old_flat)  # (the page moved the tick itself)
    same_shape = ([it[0] for it in old_flat] == [it[0] for it in new_flat]
                  and [bool(it[3]) for it in old_flat] == [bool(it[3]) for it in new_flat])
    _m.update(acts=mn.acts, parent=mn.parent, items=mn.items)
    if same_shape and (radio or _ticks(mn.items) == shown):
        return
    _push({"items": _clean(mn.own if _m["own"] else mn.items), "open": mn.parent.get(key)})


def _flat(items):
    for it in items:
        if isinstance(it, list):
            yield it
            if it[5]:
                yield from _flat(it[5])


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


def _push(payload):
    try:
        mw.web.eval("window.DDP && DDP.menuAgain && DDP.menuAgain(%s)" % json.dumps(payload).replace("</", "<\\/"))
    except Exception:
        log_swallowed()
