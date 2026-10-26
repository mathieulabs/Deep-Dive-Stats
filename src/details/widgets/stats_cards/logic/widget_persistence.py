# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from ....ui import Config
from ....logic.logger import log_swallowed
from .own_color import card_color_key, own_card_color, valid_color, with_dashboard_card_color


def _own_holders(widget):
    """The widgets holding the card's own colors on screen (the card, its pinned box),
    innermost first."""
    from .....const.theme.color_resolver import OWN_COLORS_ATTR

    holders, w = [], widget
    for _depth in range(64):
        if w is None:
            break
        if isinstance(getattr(w, OWN_COLORS_ATTR, None), dict):
            holders.append(w)
        w = w.parentWidget()
    return holders


def set_card_color(widget, color, *, conf=None, write_updates_fn=None, refresh_fn=None):
    """The color the card menu picked. With own colors on it is the card's own color, else
    the shared color of its stat (Settings > Colors), which changes everywhere it is used.
    color None turns the card's own colors off (back to the shared color)."""
    from ...chart_utils.own_colors import apply_own_colors

    key = card_color_key(widget)
    if not key:
        return
    color = valid_color(color)
    holders = _own_holders(widget)
    if color is not None and not holders:
        _set_shared_color(widget, key, color)
        return

    own = None if color is None else {key: color}
    if getattr(widget, "is_pinned", False):
        if widget.widget_id:
            from ...pinned import WidgetRegistry

            WidgetRegistry.update_setting(widget.widget_id, "own_colors", own)
    elif getattr(widget, "config_key", None):
        if not isinstance(conf, dict):
            conf = widget.addon_config if isinstance(getattr(widget, "addon_config", None), dict) else {}
        updates = {Config.DASH_STAT_COLORS: with_dashboard_card_color(conf, widget.config_key, color)}
        conf.update(updates)
        if isinstance(getattr(widget, "addon_config", None), dict) and widget.addon_config is not conf:
            widget.addon_config.update(updates)
        if write_updates_fn is not None:
            write_updates_fn(updates)
    apply_own_colors(holders[0] if holders else widget, own)
    if refresh_fn is not None:
        refresh_fn()


def _set_shared_color(widget, key, color):
    from ....ui.config.widgets.widget_colors import shared_updates, write_shared_color

    pinned = bool(getattr(widget, "is_pinned", False))
    extra = (widget.addon_config,) if isinstance(getattr(widget, "addon_config", None), dict) else ()
    write_shared_color(lambda conf: shared_updates(conf, key, color, pinned), extra_confs=extra)


def card_has_own_color(widget):
    return own_card_color(widget) is not None


def pick_card_color(widget, *, read_config_fn=None, write_updates_fn=None, refresh_fn=None):
    from aqt.qt import QColor, QColorDialog

    chosen = QColorDialog.getColor(QColor(widget.base_color), widget, "Pick Stat Color")
    if not chosen.isValid():
        return
    conf = None
    if callable(read_config_fn):
        try:
            conf = read_config_fn()
        except Exception:
            log_swallowed()
    set_card_color(widget, chosen.name(), conf=conf, write_updates_fn=write_updates_fn, refresh_fn=refresh_fn)


def persist_lock_state(widget, *, read_meta_fn=None, write_config_fn=None):
    if read_meta_fn is None or write_config_fn is None:
        return
    try:
        meta = read_meta_fn()
        conf = meta.get("config", {})
        unlocked_list = conf.get("UNLOCKED_EFFECTS", [])
        card_id = widget.widget_id or widget.config_key
        if not card_id:
            return

        is_locked = widget._effect._locked
        if not is_locked and card_id not in unlocked_list:
            unlocked_list.append(card_id)
        elif is_locked and card_id in unlocked_list:
            unlocked_list.remove(card_id)

        conf["UNLOCKED_EFFECTS"] = unlocked_list
        write_config_fn(conf)
    except Exception:
        log_swallowed()
