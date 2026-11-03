# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Stores the pinned widget definitions in the add-on config.

Each widget is a dict: id (uuid), type ("activity", "retention", "added",
"distribution", "card_counts", "heatmap" or "stat_card"), label, and stat_key
(config key, only for stat_card).
"""

import copy
import uuid
from aqt import mw

from ....ui import Config, ConfigManager
from ....logic import log_info
from ....logic.logger import log_swallowed


def _family(widget_type):
    if widget_type == "stat_card":
        return "stat"
    if widget_type == "text_label":
        return "text"
    return "chart"


def place_after(widgets, entry, after_id):
    """widgets with entry put right after the widget after_id, on its line, when both are of
    the same kind (charts, stat cards, texts: each kind has its own areas). Otherwise, or
    without after_id, at the end."""
    anchor_i = next((i for i, w in enumerate(widgets) if after_id and w.get("id") == after_id), None)
    if anchor_i is None or _family(widgets[anchor_i].get("type")) != _family(entry.get("type")):
        return list(widgets) + [entry]
    anchor = widgets[anchor_i]
    entry = dict(entry)
    for key in ("chart_box", "stat_box", "text_box", "row_num"):
        if anchor.get(key) is not None:
            entry[key] = anchor[key]
    return list(widgets[:anchor_i + 1]) + [entry] + list(widgets[anchor_i + 1:])


class WidgetRegistry:
    """Read / write pinned-widget definitions to the addon config."""
    _last_seen_count = None

    @staticmethod
    def _config():
        """Return the live addon config dict."""
        manager = ConfigManager(mw)
        cfg = dict(manager.config)
        try:
            widgets = cfg.get(Config.PINNED_WIDGETS, [])
            count = len(widgets) if isinstance(widgets, list) else 0
            if WidgetRegistry._last_seen_count != count:
                WidgetRegistry._last_seen_count = count
                profile = getattr(getattr(mw, "pm", None), "name", "default")
                log_info(
                    f"registry load: pinned_count={count} profile={profile} config_path={getattr(manager, '_config_path', '?')}",
                    tag="PINNED",
                )
        except Exception:
            log_swallowed()
        return cfg

    @staticmethod
    def _write(config):
        manager = ConfigManager(mw)
        manager.config = dict(config or {})
        manager.write_config()

    @staticmethod
    def get_all():
        cfg = WidgetRegistry._config()
        widgets = cfg.get(Config.PINNED_WIDGETS, [])
        return widgets

    @staticmethod
    def is_pinned(widget_type, stat_key=None, deck_id=None, time_span=None):
        """Check if a widget is pinned with specific context."""

        for w in WidgetRegistry.get_all():
            if w.get("type") != widget_type: continue

            if widget_type == 'stat_card' and w.get("stat_key") != stat_key:
                continue

            # Use strict equality for context to allow multiple pins of same type but diff context
            w_did = w.get("deck_id")
            w_span = w.get("time_span")

            if w_did is not None: w_did = int(w_did)
            if deck_id is not None: deck_id = int(deck_id)

            if w_did != deck_id: continue

            if w_span is not None: w_span = int(w_span)
            if time_span is not None: time_span = int(time_span)

            if w_span != time_span: continue

            return True

        return False

    @staticmethod
    def add(widget_type, label, stat_key=None, deck_id=None, time_span=None, after_id=None, **extra_fields):
        """Pin a new widget with optional context. Extra keyword args are stored verbatim.
        after_id: put it right after that widget (see place_after), else at the end."""
        cfg = WidgetRegistry._config()
        widgets = cfg.get(Config.PINNED_WIDGETS, [])
        new_id = str(uuid.uuid4())

        entry = {
            "id": new_id,
            "type": widget_type,
            "label": label,
            "stat_key": stat_key,
        }
        if deck_id is not None: entry["deck_id"] = int(deck_id)
        if time_span is not None: entry["time_span"] = int(time_span)
        entry.update(extra_fields)

        widgets = place_after(widgets, entry, after_id)
        cfg[Config.PINNED_WIDGETS] = widgets
        WidgetRegistry._write(cfg)
        return new_id

    @staticmethod
    def remove(widget_id):
        cfg = WidgetRegistry._config()
        widgets = cfg.get(Config.PINNED_WIDGETS, [])
        new_widgets = [w for w in widgets if w["id"] != widget_id]

        cfg[Config.PINNED_WIDGETS] = new_widgets
        WidgetRegistry._write(cfg)

    @staticmethod
    def removal_snapshot(widget_id):
        """What restore() needs to put a widget back after remove(): its definition, its
        place in the list and the order of the boxes. None if there is no such widget."""
        cfg = WidgetRegistry._config()
        widgets = cfg.get(Config.PINNED_WIDGETS, [])
        for index, entry in enumerate(widgets):
            if entry.get("id") == widget_id:
                return {
                    "entry": copy.deepcopy(entry),
                    "index": index,
                    "block_order": copy.deepcopy(cfg.get(Config.PINNED_BLOCK_ORDER)),
                }
        return None

    @staticmethod
    def restore(snapshot):
        """Put back a widget removed after removal_snapshot(), at its old place. The box order
        comes back too when a box left with the widget (its only one)."""
        cfg = WidgetRegistry._config()
        widgets = list(cfg.get(Config.PINNED_WIDGETS, []))
        entry = snapshot["entry"]
        if any(w.get("id") == entry.get("id") for w in widgets):
            return False
        widgets.insert(min(int(snapshot["index"]), len(widgets)), copy.deepcopy(entry))
        cfg[Config.PINNED_WIDGETS] = widgets
        old_order = snapshot.get("block_order")
        now_order = cfg.get(Config.PINNED_BLOCK_ORDER)
        if isinstance(old_order, list) and isinstance(now_order, list) and set(old_order) - set(now_order):
            cfg[Config.PINNED_BLOCK_ORDER] = copy.deepcopy(old_order)
        WidgetRegistry._write(cfg)
        return True

    @staticmethod
    def update_setting(widget_id, key, value):
        """Update a generic setting for a widget. Pass value=None to remove key."""
        WidgetRegistry.update_settings_bulk(widget_id, {key: value})

    @staticmethod
    def update_settings_bulk(widget_id, updates):
        """Update multiple settings for a widget at once."""
        cfg = WidgetRegistry._config()
        widgets = cfg.get(Config.PINNED_WIDGETS, [])
        changed = False
        for w in widgets:
            if w["id"] == widget_id:
                for key, value in updates.items():
                    if value is None:
                        if key in w:
                            del w[key]
                            changed = True
                    else:
                        w[key] = value
                        changed = True
                break

        if changed:
            cfg[Config.PINNED_WIDGETS] = widgets
            WidgetRegistry._write(cfg)

    @staticmethod
    def update_many(updates_by_id):
        """update_settings_bulk for several widgets, written once."""
        cfg = WidgetRegistry._config()
        widgets = cfg.get(Config.PINNED_WIDGETS, [])
        changed = False
        for w in widgets:
            updates = updates_by_id.get(w.get("id"))
            for key, value in (updates or {}).items():
                if value is None:
                    if key in w:
                        del w[key]
                        changed = True
                elif w.get(key) != value:
                    w[key] = value
                    changed = True
        if changed:
            cfg[Config.PINNED_WIDGETS] = widgets
            WidgetRegistry._write(cfg)

    @staticmethod
    def reorder(ordered_ids):
        cfg = WidgetRegistry._config()
        widgets = cfg.get(Config.PINNED_WIDGETS, [])

        widget_map = {w["id"]: w for w in widgets}

        reordered = []
        for wid in ordered_ids:
            if wid in widget_map:
                reordered.append(widget_map[wid])

        rem_ids = set(widget_map.keys()) - set(ordered_ids)
        for wid in widgets:
            if wid["id"] in rem_ids:
                reordered.append(wid)

        cfg[Config.PINNED_WIDGETS] = reordered
        WidgetRegistry._write(cfg)

