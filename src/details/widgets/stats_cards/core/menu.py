# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt import mw
from aqt.qt import QAction, Qt

from ....ui import StyledMenu, get_svg_icon
from ..logic.model import get_dashboard_local_stat_style
from ..logic.widget_persistence import card_has_own_color


def _find_clicked_card(container, event, stat_card_cls):
    child = container.childAt(event.pos())
    if not child:
        return None
    p = child
    while p and p != container:
        if isinstance(p, stat_card_cls):
            return p
        p = p.parentWidget()
    return None


def _open_dashboard_card_settings(container, card):
    if not card or getattr(card, "is_pinned", False):
        return
    try:
        from ....ui.config import WidgetSettingsDialog
    except Exception:
        return

    active_conf = None
    for c in container.cards:
        conf = getattr(c, "addon_config", None)
        if isinstance(conf, dict):
            active_conf = conf
            break
    if not isinstance(active_conf, dict):
        try:
            from ....ui import ConfigManager

            active_conf = ConfigManager(mw).config
        except Exception:
            addon = mw.addonManager.addonFromModule(__name__)
            active_conf = mw.addonManager.addonMeta(addon).get("config", {})

    local_style = get_dashboard_local_stat_style(active_conf, card.config_key)
    widget_def = {
        "id": f"dashboard_{card.config_key}",
        "type": "stat_card",
        "label": card.display_name,
        "stat_key": card.config_key,
    }
    dialog = WidgetSettingsDialog(
        widget_def,
        parent=container,
        global_config=active_conf,
        local_config=local_style,
        theme_config=active_conf,
    )
    dialog.exec()


def _pin_card(card):
    from ...pinned import WidgetRegistry
    from ...pinned.main_menu.manager import MainMenuWidgetManager

    WidgetRegistry.add("stat_card", card.display_name, stat_key=card.config_key, deck_id=None, time_span=card.time_span)
    MainMenuWidgetManager.instance().refresh()


def _add_row_move_actions(menu, container, clicked_card):
    card_key = clicked_card.config_key
    if clicked_card.is_pinned and clicked_card.widget_id:
        from ...pinned import WidgetRegistry as _WR
        from ...pinned.main_menu.manager import MainMenuWidgetManager as _MMM

        _wdef = next((d for d in _WR.get_all() if d.get("id") == clicked_card.widget_id), None)
        _row_num = int(_wdef.get("row_num", 0)) if _wdef else 0
        menu.addSeparator()
        _down_act = QAction("Move to next line", menu)

        def _do_down(_=None, wid=clicked_card.widget_id, rn=_row_num):
            _WR.update_setting(wid, "row_num", rn + 1)
            if _MMM.instance_exists():
                _MMM.instance()._last_state = None
                _MMM.instance()._last_widget_set = None
                _MMM.instance().refresh(clear_cache=False)

        _down_act.triggered.connect(_do_down)
        menu.addAction(_down_act)
        if _row_num > 0:
            _up_act = QAction("Move up a line", menu)

            def _do_up(_=None, wid=clicked_card.widget_id, rn=_row_num):
                new_rn = rn - 1
                _WR.update_setting(wid, "row_num", new_rn if new_rn > 0 else None)
                if _MMM.instance_exists():
                    _MMM.instance()._last_state = None
                    _MMM.instance()._last_widget_set = None
                    _MMM.instance().refresh(clear_cache=False)

            _up_act.triggered.connect(_do_up)
            menu.addAction(_up_act)
        return

    if not clicked_card.is_pinned and card_key and container._row_num_change_fn:
        _row_num = container._row_num_fn(card_key) if container._row_num_fn else 0
        menu.addSeparator()
        _down_act = QAction("Move to next line", menu)
        _down_act.triggered.connect(lambda _=None, k=card_key: container._row_num_change_fn(k, +1))
        menu.addAction(_down_act)
        if _row_num > 0:
            _up_act = QAction("Move up a line", menu)
            _up_act.triggered.connect(lambda _=None, k=card_key: container._row_num_change_fn(k, -1))
            menu.addAction(_up_act)


def show_stat_cards_container_menu(container, event, stat_card_cls):
    child = container.childAt(event.pos())
    if child:
        p = child
        while p and p != container:
            if p.contextMenuPolicy() == Qt.ContextMenuPolicy.CustomContextMenu:
                return
            p = p.parentWidget()

    if not container.cards:
        return

    menu = StyledMenu(container)
    clicked_card = _find_clicked_card(container, event, stat_card_cls)

    if clicked_card and clicked_card.stat_type:
        shown_name = str(clicked_card.display_name).replace("&", "&&")  # not a shortcut
        color_action = menu.addAction(f"Change {shown_name} Color...")
        color_action.setIcon(get_svg_icon("palette", size=16))
        color_action.triggered.connect(clicked_card._pick_color)
        if card_has_own_color(clicked_card):
            reset_action = menu.addAction(f"Use Shared {shown_name} Color")
            reset_action.setIcon(get_svg_icon("rotate-ccw", size=16))
            reset_action.triggered.connect(clicked_card._reset_color)

        pin_action = menu.addAction(f"Pin {shown_name}")
        pin_action.setIcon(get_svg_icon("push-pin", size=16))
        pin_action.triggered.connect(lambda _, c=clicked_card: _pin_card(c))
        menu.addSeparator()

        if clicked_card.is_pinned:
            deck_act = QAction("Select Decks...", menu)
            deck_act.setIcon(get_svg_icon("layers", size=16))

            def on_deck_select():
                from ...pinned import DeckMultiSelectDialog, WidgetRegistry
                from ...pinned.main_menu.manager import MainMenuWidgetManager

                all_defs = WidgetRegistry.get_all()
                widget_def = None
                for d in all_defs:
                    if d.get("id") == clicked_card.widget_id or (
                        d.get("type") == "stat_card" and d.get("stat_key") == clicked_card.config_key
                    ):
                        widget_def = d
                        break
                if widget_def is None:
                    return

                current_ids = widget_def.get("deck_ids", None)
                if current_ids is None and "deck_id" in widget_def:
                    old_did = widget_def["deck_id"]
                    if old_did is None or old_did == 0 or str(old_did) == "0":
                        current_ids = None  # all decks: everything checked
                    else:
                        current_ids = [int(old_did)]
                dialog = DeckMultiSelectDialog(current_ids, parent=container)
                if not dialog.exec():
                    return
                WidgetRegistry.update_settings_bulk(widget_def["id"], {
                    "deck_ids": dialog.selected_deck_ids,
                    "deck_id": None,
                })
                if MainMenuWidgetManager.instance_exists():
                    MainMenuWidgetManager.instance().refresh()

            deck_act.triggered.connect(on_deck_select)
            menu.addAction(deck_act)
            menu.addSeparator()
        else:
            settings_action = QAction("Settings", menu)
            settings_action.setIcon(get_svg_icon("settings", size=16))
            settings_action.triggered.connect(lambda: _open_dashboard_card_settings(container, clicked_card))
            menu.addAction(settings_action)
            menu.addSeparator()

    def toggle_vis(checked, c):
        c.setVisible(checked)
        c.setHidden(not checked)
        if container._on_visibility_changed:
            container._on_visibility_changed(c.config_key, checked)
        container.resizeEvent(None)
        container.update()
        from ...pinned.main_menu.manager import MainMenuWidgetManager

        if MainMenuWidgetManager.instance_exists():
            MainMenuWidgetManager.instance().refresh()

    def make_vis_action(parent, c, text):
        act = QAction(text, parent)
        act.setCheckable(True)
        act.setChecked(c.isVisible())
        act.triggered.connect(lambda checked, c=c: toggle_vis(checked, c))
        return act

    from ...pinned.main_menu.ui.add_widget_menu import stat_groups_by_key
    from .menu_search import MenuSearch

    cards = [c for c in container.cards if isinstance(c, stat_card_cls) and c.config_key]
    group_names, group_of = stat_groups_by_key()
    buckets = {name: [] for name in group_names}
    buckets["Other"] = []
    for c in cards:
        buckets[group_of.get(c.config_key, "Other")].append(c)

    search = MenuSearch(menu)
    for name, members in buckets.items():
        if not members:
            continue
        shown = sum(1 for c in members if c.isVisible())
        sub = menu.addMenu(f"{name} ({shown}/{len(members)})")
        for c in members:
            sub.addAction(make_vis_action(sub, c, c.display_name))
        search.add_group(sub)
    for c in cards:
        search.add_result(c.display_name, make_vis_action(menu, c, c.display_name))
    search.finish()

    if clicked_card:
        _add_row_move_actions(menu, container, clicked_card)

    menu.exec(event.globalPos())

