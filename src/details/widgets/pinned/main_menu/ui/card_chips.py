# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""The period and deck labels of a pinned card ("Past Month", "Japanese"), drawn by the web block (pinned.js):
their text, and the menus a click on them opens (the period, the decks). Both can be turned off (Settings > Pinned
Widgets, or "Hide these labels")."""

from ..imports import Config, Period, mw
from ... import DeckMultiSelectDialog, WidgetRegistry
from .....ui import StyledMenu, get_svg_icon
from .....logic.logger import log_swallowed
from ......i18n import N_, tr, tr_n, tr_name


# Charts whose data has no period (counts, forecasts, the calendar has its own buttons).
from ....charts.more_charts import NO_SPAN_TYPES as _MORE_NO_SPAN

NO_SPAN_TYPES = (
    "card_counts", "heatmap", "future_due", "review_intervals",
    "stability", "difficulty", "retrievability", *_MORE_NO_SPAN,
)


def has_time_span(widget_def):
    if not isinstance(widget_def, dict) or widget_def.get("type") in NO_SPAN_TYPES:
        return False
    return widget_def.get("stat_key") not in (Config.DASH_SHOW_STREAK, Config.DEEP_DIVE_SHOW_STREAK)


def _explicit_decks(widget_def):
    deck_ids = widget_def.get("deck_ids")
    if deck_ids:
        return list(deck_ids)
    did = widget_def.get("deck_id")
    if isinstance(did, int) and did != 0:
        return [did]
    return None


def deck_text(manager, widget_def):
    """The deck(s) the widget reads, or "" when it follows the current deck."""
    decks = _explicit_decks(widget_def)
    if not decks:
        return ""
    from ...widget_factory.utils import _resolve_deck_ids

    context = getattr(manager, "_current_deck_id", None)
    resolved = _resolve_deck_ids(decks, context)
    if resolved == context:
        return ""
    if isinstance(resolved, list) and len(resolved) == 1:
        resolved = resolved[0]
    if resolved == -1 or resolved == "deleted":
        return tr_name(N_("Deleted Cards"))
    if isinstance(resolved, int):
        try:
            return mw.col.decks.name(resolved).split("::")[-1]
        except Exception:
            return ""
    return tr_n("{n} deck", "{n} decks", len(resolved))


# -- Actions shared with the right-click menu --------------------------------------------

def _latest(widget_def):
    """The widget's saved definition now: a menu can be built from one read before a change
    (a period picked a moment ago, its screen not rebuilt yet)."""
    wid = widget_def.get("id")
    return next((d for d in WidgetRegistry.get_all() if d.get("id") == wid), widget_def)


def set_span(manager, widget_def, span, days=None):
    updates = {"time_span": span}
    if days is not None:
        updates["custom_days"] = days
    manager._update_span_bulk(widget_def["id"], updates)


def apply_span_to_all(manager, widget_def):
    """Give every widget that has a period the period of this one."""
    norm = manager._normalized_widget_def(_latest(widget_def))
    span = norm.get("time_span", Period.TOTAL)
    days = norm.get("custom_days") if span == Period.CUSTOM else None
    import time

    token = int(time.time() * 1000)
    WidgetRegistry.update_many({
        d["id"]: {"time_span": span, "custom_days": days, "_timespan_token": token}
        for d in WidgetRegistry.get_all()
        if has_time_span(d) and d.get("id")
    })
    manager.refresh()


def fill_span_menu(menu, manager, widget, widget_def):
    """The period list of a widget: its periods, then new period, apply to all."""
    from .....ui.shared.span_menu import populate_span_menu

    widget_def = _latest(widget_def)
    populate_span_menu(
        menu,
        widget_def.get("time_span", Period.TOTAL),
        widget_def.get("custom_days", None),
        lambda v, d=None: set_span(manager, widget_def, v, d),
        manager._config_manager,
        on_manage_callback=manager._open_time_span_settings,
    )
    if sum(1 for d in WidgetRegistry.get_all() if has_time_span(d)) > 1:
        all_act = menu.addAction(tr("Apply to all widgets"))
        all_act.setIcon(get_svg_icon("copy", size=14, context_ref=menu))
        all_act.triggered.connect(lambda _=False: apply_span_to_all(manager, widget_def))


def choose_decks(manager, widget, widget_def):
    """The deck picker of a widget (with its filter field)."""
    widget_def = _latest(widget_def)
    current = widget_def.get("deck_ids", None)
    if current is None and "deck_id" in widget_def:
        old = widget_def["deck_id"]
        current = None if old in (None, 0, "0") else [int(old)]
    dialog = DeckMultiSelectDialog(current, parent=widget)
    if dialog.exec():
        WidgetRegistry.update_settings_bulk(widget_def["id"], {
            "deck_ids": dialog.selected_deck_ids,
            "deck_id": None,
        })
        manager.refresh()


def themed_menu(parent, manager):
    """A menu in the pinned widgets' theme (the right-click menu, the period list)."""
    menu = StyledMenu(parent)
    menu.setProperty("deepdivestats_theme_context", "pinned")
    menu.setProperty("deepdivestats_ignore_forced_dark_theme", True)
    try:
        cfg = (manager._config_manager.config or {}) if getattr(manager, "_config_manager", None) else {}
        menu.setProperty("deepdivestats_config_override", dict(cfg))
        menu._apply_theme_style()
    except Exception:
        log_swallowed()
    return menu


# -- The labels ---------------------------------------------------------------------------


def _set_labels(manager, on):
    try:
        manager._config_manager.set_value(Config.PINNED_CARD_LABELS, bool(on))
    except Exception:
        log_swallowed()


def hide_card_labels(manager):
    """Turn the labels off, with a note saying where they come back (and Undo)."""
    _set_labels(manager, False)
    try:
        from .undo_toast import show_undo_toast

        show_undo_toast(tr("Labels hidden. Settings > Pinned Widgets shows them again."),
                        lambda: _set_labels(manager, True))
    except Exception:
        log_swallowed()
