# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QTimer

from ...chart_utils import is_night_mode
from ...chart_utils.formatting import fmt_num
from ..ui.style import theme_title_color, resolve_visual_profile, resolve_adaptive_text_colors, value_contrast_reference
from ....logic.logger import log_swallowed
from .own_color import own_card_color


def _color_key(value):
    if value is None:
        return None
    if isinstance(value, str):
        return value
    try:
        return value.name()
    except Exception:
        try:
            return str(value)
        except Exception:
            return repr(value)


def request_container_refresh(widget):
    p = widget.parentWidget()
    while p:
        if hasattr(p, "trigger_layout_update"):
            p.trigger_layout_update()
            break
        if hasattr(p, "update_layout"):
            try:
                p.update_layout(p.width())
            except Exception:
                p.update_layout()
            break
        p = p.parentWidget()


def refresh_theme(widget, conf=None, *, load_config_fn=None):
    if conf:
        widget.addon_config = conf
    elif widget.addon_config is None and load_config_fn is not None:
        widget.addon_config = load_config_fn()

    active_conf = widget.addon_config or {}

    # For pinned widgets resolve is_dark from the live conf: addonMeta() is only updated on save, not during live preview.
    if widget.is_pinned and active_conf:
        try:
            from ...chart_utils.theme import resolve_theme_runtime_state, ThemeContext
            from aqt.theme import theme_manager as _tm
            _native = bool(_tm.get_night_mode()) if _tm else False
            _runtime = resolve_theme_runtime_state(active_conf, ThemeContext.PINNED, native_dark=_native)
            is_dark = bool(_runtime.get("is_dark", _native))
        except Exception:
            is_dark = is_night_mode(widget)
    else:
        is_dark = is_night_mode(widget)

    title_col = theme_title_color(is_dark, widget)
    widget.title_col = title_col

    if widget.stat_type:
        from ....ui import get_color

        color_ctx = "pinned" if widget.is_pinned else widget
        widget.base_color = get_color(active_conf, widget.stat_type, color_ctx)
    elif widget.is_pinned and getattr(widget, "config_key", None):
        # Pinned stat cards get their colour from the stat they show, not a stat type,
        # so a theme preview has to look it up again here.
        from ....ui import STAT_KEY_TO_COLOR_KEY, get_color

        color_key = STAT_KEY_TO_COLOR_KEY.get(widget.config_key)
        if color_key:
            widget.base_color = get_color(active_conf, color_key, "pinned")
    own = own_card_color(widget)
    if own:
        widget.base_color = own

    widget._apply_inline_layout_mode()
    profile = resolve_visual_profile(active_conf, widget.is_pinned)
    show_glass = bool(profile["show_glass"])
    glass_int = float(profile["glass_int"])

    val_col, adaptive_title = resolve_adaptive_text_colors(
        widget.base_color,
        title_col,
        is_dark=is_dark,
        show_glass=show_glass,
        glass_int=glass_int,
    )
    try:
        from ...chart_utils.theme import ensure_contrast
        from aqt.qt import QColor as _QC

        # Stat values must stay readable on the card, whatever the theme/colour:
        # checked against the card's own tinted colour, not a plain reference.
        ref = value_contrast_reference(widget.base_color, is_dark, glass_int)
        val_col = ensure_contrast(_QC(val_col), ref, 3.0).name()
    except Exception:
        log_swallowed()
    refresh_key = (
        bool(is_dark),
        _color_key(widget.base_color),
        str(adaptive_title),
        str(val_col),
        bool(show_glass),
        float(glass_int),
        bool(getattr(widget, "_inline_mode_active", False)),
        bool(profile["hover_effect"]),
        # Everything apply_visual_style() reads must be part of the key, or
        # changing it in the settings has no visible effect until a restart.
        float(profile["border_alpha_pct"]),
        float(profile["title_shadow"]),
        float(profile["stat_shadow"]),
    )
    if getattr(widget, "_last_theme_refresh_key", None) == refresh_key:
        return
    widget._last_theme_refresh_key = refresh_key
    widget.apply_visual_style()
    widget.update_style_params(val_col, adaptive_title)
    widget.update()


def update_val(
    widget,
    value,
    color=None,
    title=None,
    subtitle=None,
    deck_id=None,
    refresh=True,
    *,
    refresh_theme_fn=None,
    request_refresh_fn=None,
):
    old_loading = widget._is_loading
    widget._is_loading = (value == "...")
    if color and own_card_color(widget):
        color = own_card_color(widget)
    previous_color = _color_key(getattr(widget, "base_color", None))
    next_color = _color_key(color) if color is not None else previous_color

    if color:
        widget.base_color = color

    if old_loading != widget._is_loading or previous_color != next_color:
        if refresh_theme_fn is not None:
            refresh_theme_fn()

    old_val = widget.value_lbl.text()
    old_title = widget.display_name

    rolled = False
    if widget._roll_active and value == old_val:
        rolled = True
    elif widget._roll_active and value == widget._roll_target_text:
        rolled = True
    elif widget._roll_active and value == widget._roll_origin_text:
        rolled = True
    elif not widget._is_loading:
        rolled = widget._start_value_roll(old_val, value)

    if not rolled:
        widget._roll_anim.stop()
        widget._roll_active = False
        widget._roll_target_text = value
        widget.value_lbl.setText(value)

    if title:
        widget.display_name = title
        widget.title_lbl.setText(title.upper())
        widget.set_title_visible(True)
    elif title is not None:
        widget.title_lbl.setText("")
        widget.set_title_visible(False)

    if deck_id is not None:
        widget.deck_id = deck_id

    if subtitle is not None and widget.sub_lbl:
        if isinstance(subtitle, (int, float)):
            subtitle = fmt_num(subtitle)
        elif isinstance(subtitle, str) and subtitle.strip().replace("+", "").replace("-", "").replace(",", "").isdigit():
            try:
                num_val = float(subtitle.strip().replace("+", "").replace("-", "").replace(",", ""))
                prefix = "+" if "+" in subtitle else ("-" if "-" in subtitle else "")
                subtitle = f"{prefix} {fmt_num(num_val)}"
            except ValueError:
                pass
        widget.sub_lbl.setText(subtitle)

    widget.update()

    if old_loading != widget._is_loading or value != old_val or title != old_title:
        if refresh and request_refresh_fn is not None:
            QTimer.singleShot(0, request_refresh_fn)
