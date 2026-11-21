# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""The colors of a widget's settings (charts, heatmap and stat cards; the page draws them: web_ui/widget_settings.py
_Colors).

They are the data colors the widget uses. By default they are the shared colors of
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

from ... import Config
from ....logic.logger import log_swallowed
from .....i18n import N_

OWN_KEY = "own_colors"

_BAR = (Config.COLOR_BAR, N_("Bars"))
_CARD_TYPES = (
    (Config.COLOR_MATURE, N_("Mature")),
    (Config.COLOR_YOUNG, N_("Young")),
    (Config.COLOR_LEARN, N_("Learning")),
    (Config.COLOR_RELEARN, N_("Relearning")),
    (Config.COLOR_CRAM, N_("Filtered")),
)
_GRADIENT = ((Config.COLOR_GRADIENT_LOW, N_("Low end")), (Config.COLOR_GRADIENT_HIGH, N_("High end")))

WIDGET_COLOR_KEYS = {
    "activity": (_BAR, *_CARD_TYPES),
    "retention": (
        (Config.COLOR_RETENTION, N_("All")),
        (Config.COLOR_YOUNG, N_("Young")),
        (Config.COLOR_MATURE, N_("Mature")),
        (Config.COLOR_CRAM, N_("True")),
    ),
    "added": (_BAR,),
    "hourly": (_BAR,),
    "review_intervals": (_BAR,),
    "stability": (_BAR,),
    "distribution": (
        (Config.COLOR_AGAIN, N_("Again")),
        (Config.COLOR_HARD, N_("Hard")),
        (Config.COLOR_GOOD, N_("Good")),
        (Config.COLOR_EASY, N_("Easy")),
    ),
    "card_counts": (
        (Config.COLOR_NEW, N_("New")),
        (Config.COLOR_LEARN, N_("Learning")),
        (Config.COLOR_RELEARN, N_("Relearning")),
        (Config.COLOR_YOUNG, N_("Young")),
        (Config.COLOR_MATURE, N_("Mature")),
        (Config.COLOR_SUSPENDED, N_("Suspended")),
        (Config.COLOR_BURIED, N_("Buried")),
        (Config.COLOR_DELETED, N_("Deleted")),
    ),
    # (Learning / Young / Mature: its "Breakdown by Type".)
    "future_due": ((Config.COLOR_FUTURE_DUE, N_("Due")), (Config.COLOR_BACKLOG, N_("Backlog")),
                   (Config.COLOR_LEARN, N_("Learning")), (Config.COLOR_YOUNG, N_("Young")),
                   (Config.COLOR_MATURE, N_("Mature")), (Config.COLOR_GOOD, N_("Predicted pass")),
                   (Config.COLOR_AGAIN, N_("Predicted fail"))),
    "difficulty": _GRADIENT,
    "retrievability": _GRADIENT,
    "heatmap": ((Config.HEATMAP_COLOR, N_("Activity")),),
    # The charts added on demand (charts.more_charts).
    "ratings": (
        (Config.COLOR_AGAIN, N_("Again")),
        (Config.COLOR_HARD, N_("Hard")),
        (Config.COLOR_GOOD, N_("Good")),
        (Config.COLOR_EASY, N_("Easy")),
    ),
    "introduced": (
        (Config.COLOR_LEARN, N_("Introduced")),
        (Config.COLOR_RELEARN, N_("Re-introduced")),
        (Config.COLOR_AGAIN, N_("Again")),
        (Config.COLOR_HARD, N_("Hard")),
        (Config.COLOR_GOOD, N_("Good")),
        (Config.COLOR_EASY, N_("Easy")),
    ),
    "todays_retention": (
        (Config.COLOR_GOOD, N_("Passed")),
        (Config.COLOR_AGAIN, N_("Failed")),
    ),
    "introduced_load": (
        (Config.COLOR_MATURE, N_("Mature")),
        (Config.COLOR_YOUNG, N_("Young")),
    ),
    "resets": (
        (Config.COLOR_MATURE, N_("Mature")),
        (Config.COLOR_YOUNG, N_("Young")),
        (Config.COLOR_LEARN, N_("Learning")),
    ),
    "stability_trend": (_BAR,),
    "memorised": (_BAR,),
    "load_trend": (
        (Config.COLOR_MATURE, N_("Mature")),
        (Config.COLOR_YOUNG, N_("Young")),
    ),
    "answer_time": (
        (Config.COLOR_AGAIN, N_("Again")),
        (Config.COLOR_HARD, N_("Hard")),
        (Config.COLOR_GOOD, N_("Good")),
        (Config.COLOR_EASY, N_("Easy")),
        (Config.COLOR_LEARN, N_("Learning")),
        (Config.COLOR_YOUNG, N_("Young")),
        (Config.COLOR_MATURE, N_("Mature")),
    ),
    "interval_ratings": (
        (Config.COLOR_AGAIN, N_("Again")),
        (Config.COLOR_HARD, N_("Hard")),
        (Config.COLOR_GOOD, N_("Good")),
        (Config.COLOR_EASY, N_("Easy")),
    ),
    "fsrs_calibration": (
        (Config.COLOR_AGAIN, N_("Failed")),
        (Config.COLOR_GOOD, N_("Passed")),
    ),
    "forgetting_curve": (
        (Config.COLOR_AGAIN, N_("Failed")),
        (Config.COLOR_GOOD, N_("Passed")),
    ),
    "fsrs_fatigue": (_BAR,),
    "future_retention": (
        (Config.COLOR_AGAIN, N_("Predicted fail")),
        (Config.COLOR_GOOD, N_("Predicted pass")),
    ),
    "leech_detector": ((Config.COLOR_AGAIN, N_("Cards")),),
    "stability_increase": ((Config.COLOR_GOOD, N_("Cards")),),
    "rating_fatigue": (
        (Config.COLOR_AGAIN, N_("Again")),
        (Config.COLOR_HARD, N_("Hard")),
        (Config.COLOR_GOOD, N_("Good")),
        (Config.COLOR_EASY, N_("Easy")),
    ),
    "sibling_ratings": (
        (Config.COLOR_AGAIN, N_("Again")),
        (Config.COLOR_HARD, N_("Hard")),
        (Config.COLOR_GOOD, N_("Good")),
        (Config.COLOR_EASY, N_("Easy")),
    ),
    "review_speed": (_BAR,),
    "forgotten": ((Config.COLOR_MATURE, N_("Mature")), (Config.COLOR_YOUNG, N_("Young"))),
    "interval_load": (_BAR,),
    "due_today": ((Config.COLOR_LEARN, N_("Learning")), (Config.COLOR_RELEARN, N_("Relearning"))),
    "lapse_distribution": (_BAR,),
    "review_distribution": (_BAR,),
    "learning_steps": (_BAR,),
    "time_distribution": (_BAR,),
    "interval_history": (_BAR,),
    "stability_history": (_BAR,),
    "difficulty_history": _GRADIENT,
    "week_hours": ((Config.HEATMAP_COLOR, N_("Activity")),),
    "sxr_heatmap": ((Config.HEATMAP_COLOR, N_("Cards")),),
    "bw_matrix": ((Config.COLOR_EASY, N_("More than predicted")), (Config.COLOR_AGAIN, N_("Less than predicted"))),
    "card_states": (_BAR, (Config.COLOR_NEW, N_("New")), (Config.COLOR_LEARN, N_("Learning")),
                    (Config.COLOR_RELEARN, N_("Relearning")), (Config.COLOR_YOUNG, N_("Young")),
                    (Config.COLOR_MATURE, N_("Mature"))),
}

_SHARED_TIP = N_("Shared with Settings > Colors: a color changed here changes everywhere it is used.")
_OWN_TIP = N_("Own colors: these colors are for this widget only, the others keep the shared ones.")


def color_keys_for(dialog):
    if dialog.type == "stat_card":
        from ....widgets.stats_cards.logic.own_color import card_color_key

        key = card_color_key(_StatRef(dialog))
        return ((key, N_("Value")),) if key else ()
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
    """The widget's card on screen: the dialog's parent (none for a Deep Dive stat card: the page shows its colors)."""
    if dialog.type == "stat_card" and dialog.is_dashboard_context:
        return None
    return dialog.parent()


def sync_own_colors(dialog):
    """Show the widget with the own colors the dialog has (also after Cancel)."""
    if not color_keys_for(dialog):
        return
    from ....widgets.chart_utils.own_colors import apply_own_colors

    try:
        apply_own_colors(_live_target(dialog), _own_colors(dialog))
    except Exception:
        log_swallowed()


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
