# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Add a widget at a precise spot of the main screen: the "+" of the web block (pinned.js) near the
end of a line, between two lines or two boxes, and the empty block's "Add a widget". The gallery
opens; each widget picked goes at that spot, the next ones right after it."""

from .....logic import pinned_layout as _layout
from .....logic.pinned_layout import box_of, family, row_of


def _box_fields(fam, box, row=None):
    fields = {_layout.BOX_KEY[fam]: _layout.box_value(fam, box)}
    if row is not None:
        fields["row_num"] = row or None
    return {k: v for k, v in fields.items() if v is not None}


def _config_manager(manager):
    cm = getattr(manager, "_config_manager", None)
    if cm is not None and hasattr(cm, "write_config_vals"):
        return cm
    from aqt import mw
    from ......config import ConfigManager

    return ConfigManager(mw)


def _refresh(manager):
    manager.refresh(clear_cache=False)


def add_at(manager, target, choice):
    """Pin choice (an add_widget_menu.Choice) at target (see find_target; or {"kind":
    "after", "id", "family", "box", "row"} from the right-click menu), or at the end
    without one). Returns the new widget's id (None when nothing was added)."""
    from .add_widget_menu import pin_new

    if choice.widget_type == "text_label" and choice.template is None:
        return None  # (its sentence is written in the gallery page's text editor first)
    fam = choice.family
    defs = _layout.defs()
    kind = (target or {}).get("kind")
    if kind in ("end", "newline", "after") and target["family"] != fam:
        # Another kind of widget than the line: a new box of its own, right below.
        keys = _layout.section_order(defs, _config_manager(manager).config or {})
        here = _layout.KEY_FN[target["family"]](target["box"])
        index = keys.index(here) + 1 if here in keys else len(keys)
        target, kind = {"kind": "newbox", "keys": keys, "index": index}, "newbox"

    if kind == "after":
        # Right after the widget right clicked (see WidgetRegistry.add).
        new_id = pin_new(manager, choice, after_id=target["id"], refresh=False)
    elif kind == "end":
        mates = [d["id"] for d in defs if family(d) == fam and box_of(d) == target["box"] and row_of(d) == target["row"]]
        new_id = pin_new(manager, choice, after_id=mates[-1] if mates else None, refresh=False)
    elif kind == "newline":
        new_id = pin_new(manager, choice, fields=_box_fields(fam, target["box"], target["row"]), refresh=False)
        if new_id:
            _layout.new_line(new_id, target["box"], target["row"])
            _refresh(manager)
            return new_id
    elif kind == "newbox":
        used = [box_of(d) for d in defs if family(d) == fam]
        box = (max(used) + 1) if used else 1
        new_key = _layout.KEY_FN[fam](box)
        keys, index = target["keys"], target["index"]
        order = _layout.section_order(defs, _config_manager(manager).config or {})
        if index < len(keys) and keys[index] in order:
            order.insert(order.index(keys[index]), new_key)
        elif keys and keys[-1] in order:
            order.insert(order.index(keys[-1]) + 1, new_key)
        else:
            order.append(new_key)
        from .....ui import Config

        _config_manager(manager).write_config_vals({Config.PINNED_BLOCK_ORDER: order})
        new_id = pin_new(manager, choice, fields=_box_fields(fam, box), refresh=False)
    else:
        new_id = pin_new(manager, choice, refresh=False)
    _refresh(manager)
    return new_id


def _after(new_id, fallback):
    """The spot right after the widget new_id (the next one added from the same gallery
    goes there, so they stay in the order picked), or fallback when it is not found."""
    from ... import WidgetRegistry

    d = next((d for d in WidgetRegistry.get_all() if d.get("id") == new_id), None) if new_id else None
    if d is None:
        return fallback
    return {"kind": "after", "id": new_id, "family": family(d), "box": box_of(d), "row": row_of(d)}


def open_gallery_at(manager, target):
    from ......web_ui.gallery_web import open_widget_gallery

    import copy

    from ... import WidgetRegistry
    from .....ui import Config

    # The widgets and the order of the boxes as they were: Cancel puts them back.
    cfg = WidgetRegistry._config()
    before = (copy.deepcopy(cfg.get(Config.PINNED_WIDGETS, [])), copy.deepcopy(cfg.get(Config.PINNED_BLOCK_ORDER)),
              copy.deepcopy(cfg.get(Config.PINNED_GAPS)))
    spot = {"target": target, "added": 0, "removed": 0}

    def add(choice):
        # The gallery stays open: each widget goes right after the one added before it.
        new_id = add_at(manager, spot["target"], choice)
        spot["target"] = _after(new_id, spot["target"])
        if new_id:
            spot["added"] += 1
        return new_id

    def remove(new_id):
        WidgetRegistry.remove(new_id)
        spot["removed"] += 1
        _refresh(manager)

    def reset():
        # The default widgets, order and spacing; the new ones go at the end then.
        cfg = WidgetRegistry._config()
        cfg[Config.PINNED_WIDGETS] = copy.deepcopy(Config.DEFAULT_CONFIG[Config.PINNED_WIDGETS])
        cfg.pop(Config.PINNED_BLOCK_ORDER, None)
        cfg.pop(Config.PINNED_GAPS, None)
        WidgetRegistry._write(cfg)
        spot["target"] = None
        spot["removed"] += 1
        _refresh(manager)

    done = open_widget_gallery(manager, add, family=(target or {}).get("family"),
                               where=(target or {}).get("kind"), on_remove=remove, on_reset=reset)
    if not done and (spot["added"] or spot["removed"]):
        cfg = WidgetRegistry._config()
        cfg[Config.PINNED_WIDGETS] = before[0]
        for key, val in ((Config.PINNED_BLOCK_ORDER, before[1]), (Config.PINNED_GAPS, before[2])):
            if val is None:
                cfg.pop(key, None)
            else:
                cfg[key] = val
        WidgetRegistry._write(cfg)
        _refresh(manager)
