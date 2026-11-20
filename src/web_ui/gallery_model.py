# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""The widget gallery's content and what its clicks do, without any window (the web page, gallery_web.py, shows it).

Every chart, stat card and the text widget, by category; how many of each the main screen has (or which ones the
Deep Dive shows, when it manages its own); the period and decks the widgets are added with. A click adds one more
(the main screen), checks or unchecks one (the Deep Dive), or adds a text; the "−" takes one off. The caller's
callbacks do the changes at once, and undo them on Cancel.
"""

from __future__ import annotations

from collections import Counter

from ..i18n import N_

# "Not added" chosen last time (kept while Anki runs, for the next opening).
only_missing = {"on": False}

WHERE = {
    None: N_("At the end"),
    "after": N_("After the right-clicked widget"),
    "end": N_("At the end of the line"),
    "newline": N_("On a new line"),
    "newbox": N_("In a new box"),
}

# Shown size of a tile's preview (the name under a chart's), as the Qt gallery's
CHART_PIC = (236, 148)
STAT_PIC = (172, 80)
TEXT_PIC = (236, 80)
CHART_INSET = (10, 8)  # room inside a chart's frame: its axis labels do not touch it


class Tile:
    def __init__(self, tid, choice, name, family, search, pic, show_name=True, pinned=False, count=None):
        self.id = tid
        self.choice = choice
        self.name = name
        self.family = family
        self.search = search.lower()
        self.pic = pic
        self.show_name = show_name
        self.pinned = bool(pinned)
        # How many are on the main screen (its gallery); the Deep Dive's manager only marks.
        self.count = int(count) if count is not None else (1 if pinned else 0)
        self.text = None
        self.marks = False

    def set_count(self, n):
        self.count = max(0, int(n))
        self.pinned = self.count > 0


class GalleryModel:
    """See the module. The arguments are the Qt gallery's (WidgetGallery)."""

    def __init__(self, manager, family=None, where=None, only=None, taken=None, stats=None, stats_taken=None,
                 toggle=False, on_toggle=None, on_add=None, on_remove=None, on_reset=None, context="pinned",
                 texts=None, on_add_text=None, on_remove_text=None):
        self.manager = manager
        self.family = family
        self.where = where
        self.context = context
        self.toggle = bool(toggle)
        self._only = set(only) if only is not None else None
        self._taken = set(taken) if taken is not None else None
        self._stats = set(stats) if stats is not None else None
        self._stats_taken = set(stats_taken) if stats_taken is not None else None
        self._texts = texts
        self._on_toggle = on_toggle
        self._on_add = on_add
        self._on_remove = on_remove
        self._on_reset = on_reset
        self._on_add_text = on_add_text
        self._on_remove_text = on_remove_text
        self._added = {}  # tile id: [ids of the widgets it added, last one last]
        self.span = None  # (time_span, custom_days) of the widgets added; None: each one's default
        self.deck_ids = None  # None: the deck shown
        self.choice = None  # the one picked (a gallery without on_add closes on it)
        self.sections = []  # [{"key", "family", "title", "tiles": [Tile]}]
        self.tiles = {}
        self._build()

    # -- content ----------------------------------------------------------------------------

    def title(self):
        from ..i18n import tr

        if self.toggle:
            return tr("Charts, Stat Cards and Texts") if self._texts is not None else tr("Charts and Stat Cards")
        return tr("Add Chart") if self._only is not None else tr("Add Widget")

    def where_text(self):
        from ..i18n import tr_name

        return "" if self.toggle else tr_name(WHERE.get(self.where, WHERE[None]))

    def _section(self, key, family, title):
        tiles = []
        self.sections.append({"key": key, "family": family, "title": title, "tiles": tiles})
        return tiles

    def _tile(self, tiles, *args, **kw):
        t = Tile(str(len(self.tiles)), *args, **kw)
        t.marks = self.toggle and t.family != "text"
        tiles.append(t)
        self.tiles[t.id] = t
        return t

    def _registry(self):
        from ..details.logic.widget_registry import WidgetRegistry

        return WidgetRegistry.get_all()

    def _counts(self):
        return Counter(("stat_card", d.get("stat_key")) if d.get("type") == "stat_card" else (d.get("type"), None)
                       for d in self._registry())

    def _build(self):
        from ..const import Config
        from ..details.widgets.pinned.main_menu.ui.add_widget_menu import STAT_GROUPS, Choice, chart_groups
        from ..details.logic.stat_cards import get_stat_card_default_title, get_stat_card_name
        from ..i18n import N_, tr, tr_name

        pins = self._registry()
        types = {d.get("type") for d in pins}
        stats = {d.get("stat_key") for d in pins if d.get("type") == "stat_card"}
        counts = None if self.toggle or self._taken is not None else self._counts()
        if self._taken is not None:
            types = self._taken
        for i, (group, charts) in enumerate(chart_groups()):
            charts = [c for c in charts if self._only is None or c[0] in self._only]
            if not charts:
                continue
            tiles = self._section("charts" if i == 0 else f"charts:{group}", "chart", tr_name(group))
            for wtype, label in charts:
                name = tr_name(label)
                self._tile(tiles, Choice(wtype, label), name, "chart", f"{name} {tr_name(group)} {tr('Chart')} {label}",  # (its English name found too)
                           CHART_PIC, pinned=wtype in types, count=counts[(wtype, None)] if counts is not None else None)
        if self._only is not None and self._stats is None:
            return
        if self._stats_taken is not None:
            stats = self._stats_taken
        for group, attrs in STAT_GROUPS:
            keys = [getattr(Config, attr, None) for attr in attrs]
            keys = [k for k in keys if k is not None and (self._stats is None or k in self._stats)]
            if not keys:
                continue
            tiles = self._section(f"stats:{group}", "stat", tr_name(group))
            for key in keys:
                title = get_stat_card_default_title(key)
                self._tile(tiles, Choice("stat_card", get_stat_card_name(key), stat_key=key), title, "stat",
                           f"{title} {tr_name(group)} {tr('Stat card')} {get_stat_card_name(key)}", STAT_PIC, show_name=False,
                           pinned=key in stats, count=counts[("stat_card", key)] if counts is not None else None)
        if self.toggle and self._texts is None:
            return
        tiles = self._section("text", "text", tr("Text"))
        count = self._texts if self.toggle else (counts[("text_label", None)] if counts is not None else None)
        t = self._tile(tiles, Choice("text_label", N_("Text Widget")), tr("Text Widget"), "text",
                       f"{tr('Text Widget')} {tr('Text')}", TEXT_PIC, show_name=False, count=count)
        t.text = tr("Write your own sentence, with live stats in it.")

    def inner(self, t):
        """The size a tile's preview is drawn at (inside its frame for a chart)."""
        w, h = t.pic
        if t.family == "chart":
            return w - 2 * CHART_INSET[0], h - 2 * CHART_INSET[1]
        return w, h

    def tip(self, t):
        """[what the chart shows, what a click does]."""
        from ..i18n import tr

        if t.marks:
            action = tr("Shown in Deep Dive: click to remove it") if t.pinned else tr("Click to add it to Deep Dive")
        else:
            action = tr("Click to add another. − removes one.") if t.count else tr("Click to add it")
        about = ""
        if t.choice.stat_key is None:
            try:
                from ..details.widgets.common.chart_help import help_text

                about = help_text(t.choice.widget_type) or ""
            except Exception:
                pass
        return [about, action]

    # -- the period and decks of the widgets added -------------------------------------------

    def can_choose_span(self):
        return not self.toggle


    def deck_name(self):
        from aqt import mw

        from ..i18n import N_, tr, tr_n, tr_name

        ids = list(self.deck_ids or [])
        if not ids:
            return tr("Current Deck")
        if ids == ["deleted"]:
            return tr_name(N_("Deleted Cards"))
        if len(ids) == 1:
            try:
                return mw.col.decks.name(int(ids[0])).split("::")[-1]
            except Exception:
                pass
        return tr_n("{n} deck", "{n} decks", len(ids))

    def set_span(self, span):
        """True when it changed (the previews are drawn again)."""
        if span is not None:
            try:
                span = (int(span[0]), span[1])
            except (TypeError, ValueError, IndexError):
                return False
        if span == self.span:
            return False
        self.span = span
        return True

    def set_decks(self, ids):
        ids = list(ids) if ids else None
        if ids == self.deck_ids:
            return False
        self.deck_ids = ids
        return True

    def fields_for(self, choice):
        """(time_span or None for the default, custom_days, deck_ids) a widget is added with."""
        from ..details.widgets.pinned.main_menu.ui.card_chips import has_time_span

        span, days = self.span if self.span is not None else (None, None)
        if span is not None and not has_time_span({"type": choice.widget_type, "stat_key": choice.stat_key}):
            span, days = None, None
        return span, days, (list(self.deck_ids) if self.deck_ids else None)

    def preview_def(self, t):
        """The widget's definition as it will be added (its default period, or the one chosen)."""
        from ..details.widgets.pinned.main_menu.ui.add_widget_menu import default_span

        choice = t.choice
        d = {"id": f"dd_gallery:{choice.widget_type}:{choice.stat_key or ''}", "type": choice.widget_type,
             "label": choice.label, "stat_key": choice.stat_key}
        span, days, deck_ids = self.fields_for(choice)
        if span is None:
            span = default_span(choice.widget_type, choice.stat_key)
        if span is not None:
            d["time_span"] = span
            if days is not None:
                d["custom_days"] = days
        if deck_ids:
            d["deck_ids"] = list(deck_ids)
        try:
            from ..details.widgets.pinned.main_menu.ui.widget_defs import normalized_widget_def

            return normalized_widget_def(d)
        except Exception:
            return d

    # -- clicks -------------------------------------------------------------------------------

    def _apply_view(self, wtype, view, wid=None):
        if view not in ("pie", "bars"):
            return
        key = "bars_view" if wtype == "card_counts" else "pie_view"
        val = (view == "bars") if wtype == "card_counts" else (view == "pie")
        try:
            if wid:
                from ..details.logic.widget_registry import WidgetRegistry

                WidgetRegistry.update_settings_bulk(wid, {key: val})
            else:
                from ..config import addon_config as _addon_config
                from ..const.config import Config

                cfg = _addon_config()
                dd = dict(cfg.config.get(Config.DEEP_DIVE_WIDGET_SETTINGS) or {})
                sec = dict(dd.get(wtype) or {})
                sec[key] = val
                dd[wtype] = sec
                cfg.write_config_vals({Config.DEEP_DIVE_WIDGET_SETTINGS: dd})
        except Exception:
            from ..details.logic.logger import log_swallowed

            log_swallowed()

    def pick(self, tid, template=None, view=None):
        """A tile clicked. "close" when the gallery closes on it (no on_add). template: the text widget's sentence,
        written in the gallery page's text editor (None: the Qt editor asks it)."""
        t = self.tiles.get(str(tid))
        if t is None:
            return None
        if self.toggle and t.family == "text":
            add = self._on_add_text
            new_id = None if add is None else (add() if template is None else add(template))
            if new_id:
                self._added.setdefault(t.id, []).append(new_id)
                t.set_count(t.count + 1)
            return None
        if self.toggle:
            t.pinned = not t.pinned
            if t.pinned and view:
                self._apply_view(t.choice.widget_type, view)
            if self._on_toggle is not None:
                self._on_toggle(t.choice, t.pinned)
            return None
        self.choice = t.choice
        if self._on_add is None:
            return "close"
        t.choice.time_span, t.choice.custom_days, t.choice.deck_ids = self.fields_for(t.choice)
        if t.family == "text" and template is not None:
            t.choice.template = template
        try:
            new_id = self._on_add(t.choice)
        finally:
            if t.family == "text" and template is not None:
                t.choice.template = None
        if new_id:
            if view:
                self._apply_view(t.choice.widget_type, view, wid=new_id)
            self._added.setdefault(t.id, []).append(new_id)
            t.set_count(t.count + 1)
        return None

    def remove_one(self, tid):
        """The "−": the last one added from here, else the last of its kind."""
        t = self.tiles.get(str(tid))
        if t is None or t.count <= 0:
            return
        ids = self._added.get(t.id) or []
        if self.toggle and t.family == "text":
            if self._on_remove_text is not None and self._on_remove_text(ids.pop() if ids else None):
                t.set_count(t.count - 1)
            return
        if self._on_remove is None:
            return
        if ids:
            wid = ids.pop()
        else:
            mine = [d.get("id") for d in self._registry()
                    if d.get("type") == t.choice.widget_type
                    and (t.choice.widget_type != "stat_card" or d.get("stat_key") == t.choice.stat_key)]
            wid = mine[-1] if mine else None
        if not wid:
            return
        self._on_remove(wid)
        t.set_count(t.count - 1)

    def reset_question(self):
        """The question asked before Reset (the main screen's: it removes the widgets there), or None."""
        from ..i18n import tr

        if self.toggle:
            return None
        return tr("Put back the default widgets of the main screen, in their default order? "
                  "The widgets there now are removed.")

    def reset(self):
        if self._on_reset is None:
            return
        if not self.toggle:
            self._on_reset()
            counts = self._counts()
            self._added = {}
            for t in self.tiles.values():
                c = t.choice
                t.set_count(counts[("stat_card", c.stat_key) if c.widget_type == "stat_card" else (c.widget_type, None)])
            return
        charts, stats = self._on_reset()
        charts, stats = set(charts), set(stats)
        for t in self.tiles.values():
            if t.family == "chart":
                t.pinned = t.choice.widget_type in charts
            elif t.family == "stat":
                t.pinned = t.choice.stat_key in stats

    def marked(self):
        """(chart types, stat card keys) checked (the Deep Dive's)."""
        charts, stats = set(), set()
        for t in self.tiles.values():
            if t.pinned and t.family == "stat":
                stats.add(t.choice.stat_key)
            elif t.pinned and t.family == "chart":
                charts.add(t.choice.widget_type)
        return charts, stats
