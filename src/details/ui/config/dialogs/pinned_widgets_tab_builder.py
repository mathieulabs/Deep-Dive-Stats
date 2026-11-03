# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from __future__ import annotations

from aqt.qt import QCheckBox, QFormLayout, QGroupBox, QLabel, QSpinBox, QVBoxLayout, QWidget

from ... import Config
from ....logic.logger import log_swallowed
from .....i18n import tr
from .....qss import set_qss


def build_pinned_widgets_section(dialog, parent_layout) -> None:
    group_pinned_gen = QGroupBox(tr("Pinned Widgets"))
    layout_pinned_gen = QVBoxLayout(group_pinned_gen)

    # The settings of each widget are not here: say where they are.
    each = QLabel(tr(
        "Each widget also has its own settings (title, deck, time span, style): right click it, then {settings}.",
        settings=tr("Settings"),
    ))
    each.setWordWrap(True)
    set_qss(each, "color: rgba(127,127,127,0.95);")
    layout_pinned_gen.addWidget(each)

    dialog.pinned_pos_top_cb = QCheckBox(tr("Main Menu: Above Stats Line"))
    dialog.pinned_pos_top_cb.setToolTip(
        tr("Displays pinned widgets above Anki's study summary (Studied X cards...).")
    )
    dialog.pinned_pos_top_cb.stateChanged.connect(
        lambda s: dialog.save_global_config(Config.PINNED_POSITION_TOP, bool(s))
    )
    layout_pinned_gen.addWidget(dialog.pinned_pos_top_cb)

    dialog.pinned_pos_top_deck_cb = QCheckBox(tr("Deck View: Above Study Button"))
    dialog.pinned_pos_top_deck_cb.setToolTip(
        tr("Displays pinned widgets above the 'Study Now' button in the deck overview.")
    )
    dialog.pinned_pos_top_deck_cb.stateChanged.connect(
        lambda s: dialog.save_global_config(Config.PINNED_POSITION_TOP_DECK, bool(s))
    )
    layout_pinned_gen.addWidget(dialog.pinned_pos_top_deck_cb)

    dialog.pinned_collapsible_cb = QCheckBox(tr("Collapsible Charts"))
    dialog.pinned_collapsible_cb.setToolTip(
        tr("Adds an arrow to each pinned chart so it can be folded to its title, like in the Deep Dive. "
        "Folded charts reopen when Anki restarts.")
    )

    def _collapsible_toggled(state):
        cfg = dialog.parent_dialog.addon_config
        cfg.config[Config.PINNED_CHARTS_COLLAPSIBLE] = bool(state)
        try:
            cfg.set_value(Config.PINNED_CHARTS_COLLAPSIBLE, bool(state))
        except Exception:
            log_swallowed()
        try:
            from ....widgets.pinned.widget_factory.wrapper import refresh_pinned_collapsible

            refresh_pinned_collapsible()
        except Exception:
            log_swallowed()

    dialog.pinned_collapsible_cb.stateChanged.connect(_collapsible_toggled)
    layout_pinned_gen.addWidget(dialog.pinned_collapsible_cb)

    dialog.pinned_card_labels_cb = QCheckBox(tr("Period and deck labels next to the charts' titles"))
    dialog.pinned_card_labels_cb.setToolTip(
        tr("A label such as \"Past Month\" by each chart's title; a click on it changes the period or the deck.")
    )

    def _card_labels_toggled(state):
        dialog.save_global_config(Config.PINNED_CARD_LABELS, bool(state))
        try:
            from ....widgets.pinned.main_menu.manager import MainMenuWidgetManager
            from ....widgets.pinned.main_menu.ui.card_chips import refresh_card_labels

            if MainMenuWidgetManager.instance_exists():
                pm = MainMenuWidgetManager.instance()
                cm = getattr(pm, "_config_manager", None)
                if cm is not None and isinstance(cm.config, dict):
                    cm.config[Config.PINNED_CARD_LABELS] = bool(state)
                refresh_card_labels(pm)
        except Exception:
            log_swallowed()

    dialog.pinned_card_labels_cb.stateChanged.connect(_card_labels_toggled)
    layout_pinned_gen.addWidget(dialog.pinned_card_labels_cb)

    dialog.pinned_empty_hint_cb = QCheckBox(tr("Show \"Add a widget\" when nothing is pinned"))
    dialog.pinned_empty_hint_cb.setToolTip(
        tr("With no widget left on the main screen, a small card there opens the widget gallery.")
    )

    def _empty_hint_toggled(state):
        dialog.save_global_config(Config.PINNED_EMPTY_HINT, bool(state))
        try:
            from ....widgets.pinned.main_menu.manager import MainMenuWidgetManager

            if MainMenuWidgetManager.instance_exists():
                pm = MainMenuWidgetManager.instance()
                pm._last_state = None
                pm.refresh()
        except Exception:
            log_swallowed()

    dialog.pinned_empty_hint_cb.stateChanged.connect(_empty_hint_toggled)
    layout_pinned_gen.addWidget(dialog.pinned_empty_hint_cb)

    from .....config import pinned_widgets_disabled, set_pinned_widgets_disabled

    dialog.pinned_off_check = QCheckBox(tr("Disable Pinned Widgets (restart Anki)"))
    dialog.pinned_off_check.setToolTip(
        tr("Turns off the widgets pinned on Anki's main screen. Use it if they clash with another "
        "add-on. Takes effect after restarting Anki.")
    )
    dialog.pinned_off_check.setChecked(pinned_widgets_disabled())

    def _on_pinned_off_toggled(checked):
        set_pinned_widgets_disabled(bool(checked))
        from aqt.utils import tooltip

        tooltip(tr("Restart Anki to apply."), parent=dialog)

    dialog.pinned_off_check.toggled.connect(_on_pinned_off_toggled)
    layout_pinned_gen.addWidget(dialog.pinned_off_check)

    margins_form_host = QWidget()
    margins_form = QFormLayout(margins_form_host)
    margins_form.setContentsMargins(0, 4, 0, 0)

    def _margin_spin(attr, key, label, tip):
        spin = QSpinBox()
        spin.setRange(0, 200)
        spin.setSuffix(' px')
        spin.setToolTip(tip)

        def _changed(value, _key=key):
            cfg = dialog.parent_dialog.addon_config
            cfg.config[_key] = int(value)
            try:
                cfg.set_value(_key, int(value))
            except Exception:
                log_swallowed()
            from ....widgets.pinned.main_menu.runtime.overlay_margins import refresh_overlay_margins

            refresh_overlay_margins()

        spin.valueChanged.connect(_changed)
        setattr(dialog, attr, spin)
        margins_form.addRow(label, spin)

    _margin_spin(
        "pinned_margin_side_spin", Config.PINNED_MARGIN_SIDE, tr("Side Margin:"),
        tr("Empty space on the left and on the right of the pinned widgets (same on both sides)."),
    )
    _margin_spin(
        "pinned_margin_top_spin", Config.PINNED_MARGIN_TOP, tr("Top Margin:"),
        tr("Empty space above the pinned widgets."),
    )
    _margin_spin(
        "pinned_margin_bottom_spin", Config.PINNED_MARGIN_BOTTOM, tr("Bottom Margin:"),
        tr("Empty space below the pinned widgets."),
    )
    _margin_spin(
        "pinned_section_spacing_spin", Config.PINNED_SECTION_SPACING, tr("Space Between Lines:"),
        tr("Empty space between two lines of widgets, by default. Each one can also be changed by dragging it."),
    )
    layout_pinned_gen.addWidget(margins_form_host)

    parent_layout.addWidget(group_pinned_gen)

