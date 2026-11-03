# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from ....ui import Config
from ....logic.logger import log_swallowed
from .own_color import card_color_key, own_card_color, valid_color, with_dashboard_card_color
from .....i18n import tr


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
    """The color the card menu picked: this card's own color. The shared color of the stat
    is not touched: it is also the color of other cards and of charts (the Young retention
    card has the Young color of every chart), it is set in Settings > Colors.
    color None turns the card's own color off (back to the shared one)."""
    from ...chart_utils.own_colors import apply_own_colors

    key = card_color_key(widget)
    if not key:
        return
    color = valid_color(color)
    holders = _own_holders(widget)
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


def card_has_own_color(widget):
    return own_card_color(widget) is not None


def pick_card_color(widget, *, read_config_fn=None, write_updates_fn=None, refresh_fn=None):
    from aqt.qt import QColor, QColorDialog

    picker = QColorDialog(QColor(widget.base_color), widget)
    picker.setWindowTitle(tr("Pick Color"))
    try:
        # In the theme of the window the card is in, like the pickers of the settings
        # (those take it from their dialog; a card's window does not style a dialog).
        from ...chart_utils.theme import settings_dialog_qss_for
        from .....qss import set_qss

        set_qss(picker, settings_dialog_qss_for(widget))
    except Exception:
        log_swallowed()
    if not picker.exec():
        picker.deleteLater()
        return
    chosen = picker.selectedColor()
    picker.deleteLater()
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
