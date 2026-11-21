# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Widgets saved by name (a pinned widget's right click, Save Widget As...).

Each is {"sid", "name", "def"}: the widget's definition as it was (its type, options, look, title, size, period, a
text's sentence), without where it was (its id, its box and line) nor its decks: added again from the gallery's My
Widgets, it follows the deck shown, as a new widget. Removing the widget keeps it; only Delete in the gallery does.
"""

import copy
import uuid

from aqt import mw

from ...config import Config, ConfigManager

# where the widget was, not what it is
_PLACE = {"id", "chart_box", "stat_box", "text_box", "row_num", "deck_id", "deck_ids"}


def _cfg():
    return ConfigManager(mw)


def all_saved():
    """[{sid, name, def}], oldest first (a list as stored; entries without a definition left out)."""
    out = _cfg().config.get(Config.PINNED_SAVED_WIDGETS) or []
    return [e for e in out if isinstance(e, dict) and isinstance(e.get("def"), dict) and e.get("def", {}).get("type")]


def _store(items):
    _cfg().write_config_vals({Config.PINNED_SAVED_WIDGETS: items})


def get(sid):
    return next((e for e in all_saved() if e.get("sid") == sid), None)


def clean_def(d):
    """The definition kept: d without its place, its decks and the add-on's own working keys (a leading "_")."""
    return {k: copy.deepcopy(v) for k, v in (d or {}).items() if k not in _PLACE and not str(k).startswith("_")}


def save(d, name):
    """Save d under name; one of that name already there is replaced (same place in the list).
    Returns (sid, replaced)."""
    name = str(name).strip()
    items = list(all_saved())
    entry = {"name": name, "def": clean_def(d)}
    for i, e in enumerate(items):
        if str(e.get("name", "")).strip().casefold() == name.casefold():
            entry["sid"] = e.get("sid") or str(uuid.uuid4())
            items[i] = entry
            _store(items)
            return entry["sid"], True
    entry["sid"] = str(uuid.uuid4())
    items.append(entry)
    _store(items)
    return entry["sid"], False


def rename(sid, name):
    name = str(name).strip()
    if not name:
        return False
    items = list(all_saved())
    for e in items:
        if e.get("sid") == sid:
            e["name"] = name
            _store(items)
            return True
    return False


def delete(sid):
    items = list(all_saved())
    kept = [e for e in items if e.get("sid") != sid]
    if len(kept) == len(items):
        return False
    _store(kept)
    return True
