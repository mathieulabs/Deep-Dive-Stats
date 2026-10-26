# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""The "Colors" section of a widget's settings dialog (charts, heatmap and stat cards),
placed right under General.

It lists the data colors the widget uses. By default they are the shared colors of
Settings > Colors: a color changed here changes everywhere it is used, at once and outside
the dialog's Save/Cancel, like in Settings > Colors. Opened from a pinned widget with the
separate pinned theme on, the pinned colors are edited instead.

With "Own colors" ticked the widget keeps colors of its own (chart_utils/own_colors.py):
those follow Save/Cancel like the widget's other settings. A pinned widget and a Deep Dive
chart keep them in their definition ("own_colors"), a Deep Dive stat card in
Config.DASH_STAT_COLORS.
"""

from __future__ import annotations

from aqt import mw
from aqt.qt import QCheckBox, QColor, QColorDialog, QGroupBox, QHBoxLayout, QLabel, QPushButton, Qt, QVBoxLayout

from ... import Config
from ...theme.icons import get_svg_icon
from .....qss import set_qss
from ....logic.logger import log_swallowed

OWN_KEY = "own_colors"

_BAR = (Config.COLOR_BAR, "Bars")
_CARD_TYPES = (
    (Config.COLOR_MATURE, "Mature"),
    (Config.COLOR_YOUNG, "Young"),
    (Config.COLOR_LEARN, "Learning"),
    (Config.COLOR_RELEARN, "Relearning"),
    (Config.COLOR_CRAM, "Filtered"),
)
_GRADIENT = ((Config.COLOR_GRADIENT_LOW, "Low end"), (Config.COLOR_GRADIENT_HIGH, "High end"))

WIDGET_COLOR_KEYS = {
    "activity": (_BAR, *_CARD_TYPES),
    "retention": (
        (Config.COLOR_RETENTION, "All"),
        (Config.COLOR_YOUNG, "Young"),
        (Config.COLOR_MATURE, "Mature"),
        (Config.COLOR_CRAM, "True"),
    ),
    "added": (_BAR,),
    "hourly": (_BAR,),
    "review_intervals": (_BAR,),
    "stability": (_BAR,),
    "distribution": (
        (Config.COLOR_AGAIN, "Again"),
        (Config.COLOR_HARD, "Hard"),
        (Config.COLOR_GOOD, "Good"),
        (Config.COLOR_EASY, "Easy"),
    ),
    "card_counts": (
        (Config.COLOR_NEW, "New"),
        (Config.COLOR_LEARN, "Learning"),
        (Config.COLOR_RELEARN, "Relearning"),
        (Config.COLOR_YOUNG, "Young"),
        (Config.COLOR_MATURE, "Mature"),
        (Config.COLOR_SUSPENDED, "Suspended"),
        (Config.COLOR_BURIED, "Buried"),
        (Config.COLOR_DELETED, "Deleted"),
    ),
    "future_due": ((Config.COLOR_FUTURE_DUE, "Due"), (Config.COLOR_BACKLOG, "Backlog")),
    "difficulty": _GRADIENT,
    "retrievability": _GRADIENT,
    "heatmap": ((Config.HEATMAP_COLOR, "Activity"),),
}

_SHARED_TIP = "Shared with Settings > Colors: a color changed here changes everywhere it is used."
_OWN_TIP = "Own colors: these colors are for this widget only, the others keep the shared ones."


def color_keys_for(dialog):
    if dialog.type == "stat_card":
        from ....widgets.stats_cards.logic.own_color import card_color_key

        key = card_color_key(_StatRef(dialog))
        return ((key, "Value"),) if key else ()
    return WIDGET_COLOR_KEYS.get(dialog.type, ())


class _StatRef:
    """What card_color_key needs, from the dialog (the card may not be on screen)."""

    def __init__(self, dialog):
        self.stat_type = None
        self.config_key = dialog.widget_def.get("stat_key")


# Shared colors

def _is_full(conf):
    """True for a whole add-on config, False for a compact style dict (Deep Dive grid)."""
    return isinstance(conf, dict) and (Config.PINNED_WIDGETS in conf or Config.THEME_PRESET in conf)


def _full_config(dialog):
    for conf in (getattr(dialog, "theme_config", None), dialog.global_config):
        if _is_full(conf):
            return conf
    from .....config import ConfigManager

    return ConfigManager(mw).config


def pinned_separate_theme(conf):
    """True when pinned widgets use a theme of their own (and so their own data colors)."""
    return bool(conf.get(Config.PINNED_USE_ACTIVE_THEME, False)) and bool(conf.get(Config.PINNED_USE_SEPARATE_THEME, False))


def pinned_theme_baseline(conf):
    """The data colors of the separate pinned theme's preset."""
    from .....const.theme.data_colors import COLOR_DEFAULTS
    from ... import ThemePalettes

    preset_key = conf.get(Config.PINNED_THEME_PRESET, ThemePalettes.NATIVE)
    custom_presets = conf.get(Config.THEME_CUSTOM_PRESETS, {})
    entry = custom_presets.get(preset_key, {}) if isinstance(custom_presets, dict) else {}
    if isinstance(entry, dict) and isinstance(entry.get("data_colors"), dict):
        return {**COLOR_DEFAULTS, **entry["data_colors"]}
    return ThemePalettes.get_preset_data_colors(preset_key)


def shared_baseline(conf, key, pinned):
    """The shared color `key` before any change: the theme's own one."""
    from .....const.theme.data_colors import COLOR_DEFAULTS

    if pinned and pinned_separate_theme(conf):
        base = pinned_theme_baseline(conf)
    else:
        from ..theme.data_color_ops import get_data_color_baseline

        base = get_data_color_baseline(conf)
    return base.get(key, COLOR_DEFAULTS.get(key, "#888888"))


def shared_current(conf, key, pinned):
    from .....const.theme.color_resolver import get_color

    return get_color(conf, key, "pinned" if pinned else None)


def shared_updates(conf, key, color_hex, pinned):
    """The config changes that set the shared color `key` in `conf`. A pinned widget with
    the separate pinned theme on changes the pinned colors, like the heatmap color."""
    if not (pinned and pinned_separate_theme(conf)):
        return {key: color_hex}
    custom = conf.get(Config.PINNED_THEME_CUSTOM_COLORS, {})
    custom = dict(custom) if isinstance(custom, dict) else {}
    if str(color_hex).lower() == str(shared_baseline(conf, key, True)).lower():
        custom.pop(key, None)
    else:
        custom[key] = color_hex
    has_mode = conf.get(Config.PINNED_THEME_CUSTOM_BASE_MODE, None) is not None
    return {Config.PINNED_THEME_CUSTOM_COLORS: custom, Config.PINNED_THEME_IS_CUSTOM: bool(custom) or has_mode}


def _pinned(dialog):
    return bool(getattr(dialog, "is_pinned_mode", False))


def _shared_baseline(dialog, key):
    return shared_baseline(_full_config(dialog), key, _pinned(dialog))


def _shared_current(dialog, key):
    return shared_current(_full_config(dialog), key, _pinned(dialog))


def write_shared_color(updates_for, *, extra_confs=(), self_widget=None, live_conf=None, after_override=None):
    """Save a shared color change and show it everywhere.

    updates_for(conf) gives the config changes for one config dict. They are saved on top of
    the file's latest content, then applied to every config already loaded in memory and to
    `extra_confs` (a dialog's copies and its Cancel backup, so neither Save nor Cancel puts
    the old color back)."""
    from .....config import ConfigManager, _LIVE_MANAGERS, set_live_config_override

    saved = ConfigManager(mw)
    saved.write_config_vals(updates_for(saved.config))
    seen = set()
    for conf in [m.config for m in list(_LIVE_MANAGERS)] + list(extra_confs):
        if not _is_full(conf) or id(conf) in seen:
            continue
        seen.add(id(conf))
        conf.update(updates_for(conf))

    # Charts read the config a settings dialog shows them; in the Deep Dive that is a
    # compact style dict without colors, so give them the whole config while they repaint.
    if live_conf is not None:
        set_live_config_override(live_conf)
    try:
        from ..theme.runtime_refresh import refresh_live_data_colors

        refresh_live_data_colors(parent_dialog=mw, addon_config=saved, self_widget=self_widget, source="widget_color")
    except Exception:
        log_swallowed()
    finally:
        if live_conf is not None:
            set_live_config_override(after_override)


def set_shared_color(dialog, key, color_hex):
    write_shared_color(
        lambda conf: shared_updates(conf, key, color_hex, _pinned(dialog)),
        extra_confs=(dialog.global_config, getattr(dialog, "theme_config", None), getattr(dialog, "_backup_global", None)),
        self_widget=dialog,
        live_conf=_full_config(dialog),
        after_override=dialog.live_config(),
    )


# Own colors (this widget only)

def _own_colors(dialog):
    """{color key: hex} when own colors are on, else None."""
    from ....widgets.chart_utils.own_colors import clean_own_colors

    if dialog.type == "stat_card" and dialog.is_dashboard_context:
        from ....widgets.stats_cards.logic.own_color import dashboard_card_color

        color = dashboard_card_color(dialog.global_config, str(dialog.widget_def.get("stat_key") or ""))
        keys = color_keys_for(dialog)
        return {keys[0][0]: color} if color and keys else None
    return clean_own_colors(dialog.widget_def.get(OWN_KEY))


def _store_own_colors(dialog, colors):
    """Keep the own colors in the dialog's config (Save keeps them, Cancel drops them) and
    show them on the widget now. None turns own colors off."""
    if dialog.type == "stat_card" and dialog.is_dashboard_context:
        from ....widgets.stats_cards.logic.own_color import with_dashboard_card_color

        keys = color_keys_for(dialog)
        color = (colors or {}).get(keys[0][0]) if keys else None
        dialog.global_config[Config.DASH_STAT_COLORS] = with_dashboard_card_color(
            dialog.global_config, str(dialog.widget_def.get("stat_key") or ""), color
        )
    else:
        for conf in _def_configs(dialog):
            if colors is None:
                conf.pop(OWN_KEY, None)
            else:
                conf[OWN_KEY] = dict(colors)
    sync_own_colors(dialog)


def _def_configs(dialog):
    confs = [dialog.widget_def]
    if isinstance(dialog.local_config, dict) and dialog.local_config is not dialog.widget_def:
        confs.append(dialog.local_config)
    return confs


def cancel_own_colors(dialog):
    """Cancel: the widget's own colors as they were when the dialog opened."""
    if not color_keys_for(dialog):
        return
    if not (dialog.type == "stat_card" and dialog.is_dashboard_context):  # else in global_config, restored already
        backup = getattr(dialog, "_own_colors_backup", None)
        for conf in _def_configs(dialog):
            if backup is None:
                conf.pop(OWN_KEY, None)
            else:
                conf[OWN_KEY] = dict(backup)
    sync_own_colors(dialog)


def _live_target(dialog):
    """The widget's card on screen: the dialog's parent, or for a Deep Dive stat card the
    card itself inside its row."""
    target = dialog.parent()
    if target is None or not (dialog.type == "stat_card" and dialog.is_dashboard_context):
        return target
    from ....widgets.stats_cards import StatCardWidget

    key = dialog.widget_def.get("stat_key")
    for card in target.findChildren(StatCardWidget):
        if getattr(card, "config_key", None) == key:
            return card
    return None


def sync_own_colors(dialog):
    """Show the widget with the own colors the dialog has (also after Cancel)."""
    if not color_keys_for(dialog):
        return
    from ....widgets.chart_utils.own_colors import apply_own_colors

    try:
        apply_own_colors(_live_target(dialog), _own_colors(dialog))
    except Exception:
        log_swallowed()


# The section

def _color_row(dialog, box, label, current_fn, is_default_fn, set_fn, reset_fn, reset_tip):
    """label, a swatch to pick a color and a button back to the default one. Returns
    (swatch, show): show() repaints the row from current_fn / is_default_fn."""
    row = QHBoxLayout()
    row.addWidget(QLabel(label))
    row.addStretch()
    swatch = QPushButton()
    swatch.setFixedSize(28, 22)
    swatch.setCursor(Qt.CursorShape.PointingHandCursor)
    swatch.setToolTip("Click to pick a color")
    reset = QPushButton()
    reset.setIcon(get_svg_icon("rotate-ccw", size=13, context_ref=dialog))
    reset.setFixedSize(22, 22)
    reset.setCursor(Qt.CursorShape.PointingHandCursor)
    reset.setToolTip(reset_tip)
    set_qss(reset, "QPushButton { background: transparent; border: none; } QPushButton:hover { background: rgba(128,128,128,0.18); border-radius: 4px; }")

    def show():
        set_qss(swatch, f"background-color: {current_fn()}; border: 1px solid rgba(128,128,128,0.45); border-radius: 4px;")
        reset.setVisible(not is_default_fn())

    def pick(_checked=False):
        chosen = QColorDialog.getColor(QColor(current_fn()), dialog, "Pick Color")
        if chosen.isValid():
            set_fn(chosen.name())
            show()

    def back(_checked=False):
        reset_fn()
        show()

    swatch.clicked.connect(pick)
    reset.clicked.connect(back)
    show()
    row.addWidget(swatch)
    row.addWidget(reset)
    box.addLayout(row)
    return swatch, show


def build_widget_color_section(dialog):
    """The Colors group (not yet in the dialog), or None when the widget has no colors."""
    keys = color_keys_for(dialog)
    if not keys:
        return None
    from ....widgets.chart_utils.own_colors import clean_own_colors

    dialog._own_colors_backup = clean_own_colors(dialog.widget_def.get(OWN_KEY))
    group = QGroupBox("Colors")
    box = QVBoxLayout(group)
    own_cb = QCheckBox("Own colors (this widget only)")
    own_cb.setToolTip("Off: the shared colors of Settings > Colors. On: colors for this widget only.")
    own_cb.setChecked(_own_colors(dialog) is not None)
    box.addWidget(own_cb)
    dialog.own_colors_cb = own_cb
    dialog.widget_color_buttons = {}
    shows = []

    def is_own():
        return own_cb.isChecked()

    def current(key):
        own = (_own_colors(dialog) or {}).get(key) if is_own() else None
        return own or _shared_current(dialog, key)

    def is_default(key):
        if is_own():
            return (_own_colors(dialog) or {}).get(key) is None
        return str(_shared_current(dialog, key)).lower() == str(_shared_baseline(dialog, key)).lower()

    def set_color(key, color):
        if is_own():
            colors = dict(_own_colors(dialog) or {})
            colors[key] = color
            _store_own_colors(dialog, colors)
        else:
            set_shared_color(dialog, key, color)

    def reset_color(key):
        if is_own():
            colors = dict(_own_colors(dialog) or {})
            colors.pop(key, None)
            _store_own_colors(dialog, colors)
        else:
            set_shared_color(dialog, key, _shared_baseline(dialog, key))

    for key, label in keys:
        swatch, show = _color_row(
            dialog,
            box,
            label,
            current_fn=lambda key=key: current(key),
            is_default_fn=lambda key=key: is_default(key),
            set_fn=lambda color, key=key: set_color(key, color),
            reset_fn=lambda key=key: reset_color(key),
            reset_tip="Back to the shared color",
        )
        dialog.widget_color_buttons[key] = swatch
        shows.append(show)

    def refresh():
        group.setToolTip(_OWN_TIP if is_own() else _SHARED_TIP)
        for show in shows:
            show()

    def on_own_toggled(checked):
        # On starts with no own color set (the widget looks the same); off drops them.
        _store_own_colors(dialog, {} if checked else None)
        refresh()

    own_cb.toggled.connect(on_own_toggled)
    dialog._refresh_widget_colors = refresh
    refresh()
    return group


def auto_title_color(dialog):
    """The title color a stat card gets from the theme (what an unset Title Color shows)."""
    from ....widgets.chart_utils import is_night_mode
    from ....widgets.chart_utils.theme import get_theme_colors

    ref = _live_target(dialog) or dialog
    try:
        tc = get_theme_colors(ref)
        if tc.get("themed"):
            return tc["text_secondary"].name()
    except Exception:
        log_swallowed()
    return "#a1a1aa" if is_night_mode(ref) else "#71717a"
