# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors

from aqt.qt import QLabel, QWidget, QColor, QCheckBox, QRadioButton, QDialog

from ..imports import Config, get_color
from ...widget_factory.factory import WidgetFactory
from .....logic.logger import log_swallowed
from ......const.theme.color_resolver import own_color_for


_STYLE_TOKEN_ATTR = "_deepdivestats_styles_token"


def _styles_token(cfg):
    """Config + light/dark mode: everything update_styles() reads besides
    the widgets themselves. None when it can't be computed."""
    try:
        from ....chart_utils.theme import theme_config_signature

        return theme_config_signature(cfg)
    except Exception:
        return None


def _styled_targets(manager):
    targets = [manager._overlay]
    targets.extend((getattr(manager, "_active_widgets", None) or {}).values())
    return targets


def update_styles_after_rebuild(manager):
    """Restyle after a rebuild.

    A deck switch reuses the same widgets and config, so the full restyle (every
    stylesheet and chart color refresh) is skipped when the overlay and all live
    widgets already have this config and light/dark mode. A new widget, a config
    change or a theme switch still gets the full pass.
    """
    if not manager._overlay or not hasattr(manager, "_main_layout") or not manager._main_layout:
        return
    try:
        from ..ui.edit_mode import apply_edit_mode

        apply_edit_mode(manager)
    except Exception:
        log_swallowed()
    try:
        # Live config (not the manager's cached copy): chart colour refreshes
        # inside update_styles() read the live config too.
        from ......config import read_config_dict

        token = _styles_token(read_config_dict())
        if token is not None and all(
            getattr(w, _STYLE_TOKEN_ATTR, None) == token for w in _styled_targets(manager)
        ):
            manager._resize_overlay()
            return
    except Exception:
        log_swallowed()
    update_styles(manager)


def update_styles(manager, config_manager=None):
    if not manager._overlay or not hasattr(manager, "_main_layout") or not manager._main_layout:
        return

    if config_manager is not None and hasattr(config_manager, "set_value"):
        # Lightweight stand-ins (e.g. the settings dialog's live config view) must
        # not replace the real manager: later writes would fail on them.
        manager._config_manager = config_manager
    cm = config_manager if config_manager else manager._get_config_manager()
    cfg = cm.config
    try:
        from ..ui.edit_mode import apply_edit_mode

        apply_edit_mode(manager, cfg)
    except Exception:
        log_swallowed()

    for i in range(manager._main_layout.count()):
        item = manager._main_layout.itemAt(i)
        widget = item.widget()
        if not widget:
            continue

        from ....stats_cards import StatCardsContainer, RowGroupedStatContainer

        if isinstance(widget, (StatCardsContainer, RowGroupedStatContainer)):
            from .runtime_widget_updates import zoomed_scale

            widget.set_scale(zoomed_scale(manager, cfg.get(Config.FACECARDS_SCALE, 100)))
            for card in getattr(widget, "cards", []):
                card.set_centered(True)
                if hasattr(card, "refresh_theme"):
                    card.refresh_theme(cfg)
            continue

        found_cards = widget.findChildren(QWidget, "pinned_widget_card")
        found_cards += widget.findChildren(QWidget, "StatCard")

        if widget.objectName() in ("pinned_widget_card", "StatCard"):
            found_cards.append(widget)

        _defs_by_id = {
            d.get("id"): d
            for d in (cfg.get(Config.PINNED_WIDGETS, []) or [])
            if isinstance(d, dict)
        }
        for inner_card in found_cards:
            if hasattr(inner_card, "refresh_theme"):
                _card_def = _defs_by_id.get(getattr(inner_card, "widget_id", None))
                if _card_def is not None:
                    from ....stats_cards import resolve_effective_stat_card_config

                    inner_card.refresh_theme(resolve_effective_stat_card_config(cfg, _card_def))
                else:
                    inner_card.refresh_theme(cfg)

            from ....charts.heatmap import HeatmapWidget

            hm = inner_card.findChild(HeatmapWidget)
            if not hm and isinstance(inner_card, HeatmapWidget):
                hm = inner_card

            if hm:
                from .runtime_widget_updates import zoomed_scale

                hm.set_scale(zoomed_scale(manager, cfg.get(Config.HEATMAP_SCALE, 100)))
                opacity = cfg.get(Config.HEATMAP_EMPTY_OPACITY, 15)
                hm.set_empty_opacity(opacity)
                hm.set_empty_white(cfg.get(Config.HEATMAP_EMPTY_WHITE, False))

                hide_title = cfg.get(Config.HEATMAP_HIDE_TITLE, True)
                header_label = inner_card.findChild(QLabel, "pinned_header")
                if header_label:
                    header_label.setVisible(not hide_title and bool(header_label.text().strip()))

                hm.set_hide_labels(cfg.get(Config.HEATMAP_HIDE_LABELS, True))
                hm.set_show_legend(cfg.get(Config.HEATMAP_SHOW_LEGEND, True))
                hm.set_rounding(cfg.get(Config.HEATMAP_ROUNDING, 20))
                hm.set_monday_first(cfg.get(Config.HEATMAP_MONDAY_FIRST, True))
                hm.set_tinted_future(cfg.get(Config.HEATMAP_TINTED_FUTURE, False))
                hm.set_show_future(cfg.get(Config.HEATMAP_SHOW_FUTURE, True))
                hm.set_multi_hue_intensity(cfg.get(Config.HEATMAP_MULTI_HUE_INTENSITY, False))
                hm.set_metric(cfg.get(Config.HEATMAP_METRIC, "reviews"))
                hm.set_invert_intensity(cfg.get(Config.HEATMAP_INVERT_INTENSITY, False))

                hm.base_color = QColor(own_color_for(hm, Config.HEATMAP_COLOR) or get_color(cfg, Config.HEATMAP_COLOR, "pinned"))
                hm._update_levels()

            from ....stats_cards import StatCardWidget

            # Stat cards have their own style pipeline. Avoid double styling.
            if not isinstance(inner_card, StatCardWidget):
                WidgetFactory.apply_style(inner_card, config_manager=cm)
                if hasattr(inner_card, "_update_collapse_icon"):
                    inner_card._update_collapse_icon()

    for w in manager._overlay.findChildren(QWidget):
        if hasattr(w, "refresh_data_colors"):
            try:
                w.refresh_data_colors()
                w.update()
            except Exception:
                log_swallowed()

    # Some theme flows refresh styles without emitting the internal theme signal.
    # Re-apply control styles here so legend toggles stay in sync immediately.
    try:
        from ...widget_factory.utils import _apply_checkbox_style, _apply_radio_style

        for cb in (w for w in manager._overlay.findChildren(QCheckBox) if not isinstance(w.window(), QDialog)):
            try:
                _apply_checkbox_style(cb)
            except Exception:
                log_swallowed()
        for rb in (w for w in manager._overlay.findChildren(QRadioButton) if not isinstance(w.window(), QDialog)):
            try:
                _apply_radio_style(rb)
            except Exception:
                log_swallowed()
    except Exception:
        log_swallowed()

    try:
        from ......config import read_config_dict

        token = _styles_token(read_config_dict())
    except Exception:
        token = None
    for w in _styled_targets(manager):
        try:
            setattr(w, _STYLE_TOKEN_ATTR, token)
        except Exception:
            log_swallowed()

    manager._resize_overlay()
