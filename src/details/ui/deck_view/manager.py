# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QTableWidget, QLabel
from ...logic.refresh import queue_ui_callback
from .. import Config
from ...widgets import HorizontalScrollTable
from ..theme.icons import get_svg_icon
from .table_fill import fill_deck_table
from .tree import build_deck_tree
from .visibility import (
    on_tab_expand_clicked as on_tab_expand_clicked_impl,
    prioritize_deck_tab as prioritize_deck_tab_impl,
    refresh_deck_tab_visibility as refresh_deck_tab_visibility_impl,
)
from aqt.qt import QPushButton
from ....qss import set_qss
from ...logic.logger import log_swallowed

DELETED_TAB_DID = "__deleted_cards__"


def show_loading_placeholder(tab_widget):
    """A deck tab opened before its stats arrived would be an empty page: say it is loading."""
    from aqt.qt import Qt

    if tab_widget is None or tab_widget.findChild(QTableWidget) is not None:
        return
    if tab_widget.findChild(QLabel, "deck_tab_loading") is not None:
        return
    label = QLabel("Loading\u2026", tab_widget)
    label.setObjectName("deck_tab_loading")
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setEnabled(False)  # greyed with the theme's own disabled colour
    tab_widget.layout().addWidget(label)


def clear_loading_placeholder(tab_widget):
    label = tab_widget.findChild(QLabel, "deck_tab_loading") if tab_widget is not None else None
    if label is not None:
        label.hide()
        label.deleteLater()

def _is_deck_tab_visible(dialog, full_name, tab_name, deck_id):
    """Compute initial deck-tab visibility without a second full refresh pass."""
    text = dialog.search_bar.text().lower() if hasattr(dialog, "search_bar") else ""

    visible = True
    parts = full_name.split("::") if full_name else []
    for j in range(1, len(parts)):
        ancestor = "::".join(parts[:j])
        if ancestor not in dialog.expanded_decks:
            visible = False
            break

    if text:
        did_str = str(deck_id or "").lower()
        if text not in tab_name.lower() and text not in did_str:
            visible = False

    return visible

def _refresh_deck_tab_header_styles(dialog):
    """Align deck-tab header label colors with the main QTabBar style."""
    from ..theme import get_theme_palette
    from ..theme import get_theme_effective_is_dark
    is_dark = get_theme_effective_is_dark(dialog.addon_config.config)
    pal = get_theme_palette(dialog.addon_config.config) or {}
    text_secondary = pal.get("text_secondary", "#a1a1aa" if is_dark else "#71717a")
    selected_color = pal.get("text_primary", "#f4f4f5") if is_dark else pal.get("accent", "#3b82f6")
    selected_idx = dialog.tab_widget.currentIndex()
    bar = dialog.tab_widget.tabBar()

    for i in range(dialog.tab_widget.count()):
        container = bar.tabButton(i, bar.ButtonPosition.LeftSide)
        if not container:
            continue
        label = container.findChild(QLabel, "deck_tab_label")
        if not label:
            continue
        is_selected = (i == selected_idx)
        color = selected_color if is_selected else text_secondary
        weight = 700 if is_selected else 600
        set_qss(label,
            f"background: transparent; border: none; padding: 0px 4px; color: {color}; font-weight: {weight};"
        )
        btn = container.findChild(QPushButton)
        if btn:
            tab_w = dialog.tab_widget.widget(i)
            full_name = tab_w.property("full_name") if tab_w else ""
            is_expanded = bool(full_name in dialog.expanded_decks)
            btn.setIcon(get_svg_icon("chevron-down" if is_expanded else "chevron-right"))

def _add_folder_tab_buttons(dialog, tab_index, full_path):
    """No left folder triangle on deck tabs."""
    tab_bar = dialog.tab_widget.tabBar()
    tab_bar.setTabButton(tab_index, tab_bar.ButtonPosition.LeftSide, None)
    tab_bar.setTabButton(tab_index, tab_bar.ButtonPosition.RightSide, None)

def stash_deck_tabs_for_restore(dialog):
    """Detach current Deck View tabs so they can be restored without rebuilding."""
    tw = dialog.tab_widget
    if tw.count() == 0:
        return
    cache = getattr(dialog, "_deck_view_cache", None) or {}
    entries = []
    current_idx = tw.currentIndex()
    current_tab = tw.widget(current_idx) if current_idx >= 0 else None
    selected_deck_id = current_tab.property("deck_id") if current_tab else None

    while tw.count() > 0:
        w = tw.widget(0)
        title = tw.tabText(0)
        visible = tw.isTabVisible(0)
        full_name = w.property("full_name") if w else title
        is_folder = bool(w.property("is_folder")) if w else False
        depth = int(w.property("depth") or 0) if w else 0
        deck_id = w.property("deck_id") if w else None
        tw.removeTab(0)
        if w is not None:
            w.setParent(None)
        entries.append({
            "widget": w,
            "title": title,
            "visible": visible,
            "deck_id": deck_id,
            "full_name": full_name,
            "is_folder": is_folder,
            "depth": depth,
        })

    cache["ui_tabs"] = entries
    cache["selected_deck_id"] = selected_deck_id
    dialog._deck_view_cache = cache

def _restore_deck_view_from_cache(dialog, cache):
    from .loader import restore_deck_view_from_cache

    return restore_deck_view_from_cache(
        dialog,
        cache,
        add_folder_tab_buttons_fn=_add_folder_tab_buttons,
        is_deck_tab_visible_fn=_is_deck_tab_visible,
        refresh_deck_tab_header_styles_fn=_refresh_deck_tab_header_styles,
        populate_deck_tab_fn=populate_deck_tab,
        on_tab_expand_clicked_fn=on_tab_expand_clicked,
    )


def load_deck_view(dialog, prefer_cached=False):
    from .loader import load_deck_view as _load

    return _load(
        dialog,
        prefer_cached=prefer_cached,
        restore_deck_view_from_cache_fn=_restore_deck_view_from_cache,
        build_deck_tree_fn=build_deck_tree,
        add_folder_tab_buttons_fn=_add_folder_tab_buttons,
        is_deck_tab_visible_fn=_is_deck_tab_visible,
        populate_deck_tab_fn=populate_deck_tab,
        on_tab_expand_clicked_fn=on_tab_expand_clicked,
        refresh_deck_tab_header_styles_fn=_refresh_deck_tab_header_styles,
        deleted_tab_did=DELETED_TAB_DID,
    )

def prioritize_deck_tab(dialog, index):
    return prioritize_deck_tab_impl(dialog, index)


def on_tab_expand_clicked(dialog, index, full_path):
    return on_tab_expand_clicked_impl(dialog, index, full_path, _refresh_deck_tab_header_styles)


def refresh_deck_tab_visibility(dialog):
    return refresh_deck_tab_visibility_impl(dialog)


def populate_deck_tab(dialog, index, do_resize=True, from_tab_change=False):
    """Fill a skeleton deck tab with its pre-fetched data."""
    if index < 0: return

    tab_widget = dialog.tab_widget.widget(index)
    if not tab_widget: return

    deck_id = tab_widget.property("deck_id")
    has_data = (deck_id in getattr(dialog, 'deck_view_data', {}))

    if index in getattr(dialog, '_deck_tabs_populated', set()):
        return

    if has_data:
        clear_loading_placeholder(tab_widget)

    if not has_data:
        stats_list = []
    else:
        stats_list = dialog.deck_view_data[deck_id]

    table = tab_widget.findChild(QTableWidget)
    if not table:
        table = HorizontalScrollTable()

        from ...logic.tabs import get_tabs_config
        tabs_config = [t for t in get_tabs_config(dialog.addon_config) if t.get("enabled", True)]
        first_tab = tabs_config[0] if tabs_config else {}

        row_height = dialog.addon_config.config.get(Config.GLOBAL_ROW_HEIGHT, 30)

        from ..table import setup_table_for_deck_view
        setup_table_for_deck_view(dialog, table,
                                  show_time=first_tab.get("show_time", True),
                                  show_reviews=first_tab.get("show_reviews", True),
                                  show_retention=first_tab.get("show_retention", True),
                                  show_retention_young=first_tab.get("show_retention_young", True),
                                  show_retention_mature=first_tab.get("show_retention_mature", True),
                                  show_avg_time=first_tab.get("show_avg_time", True),
                                  show_streak=first_tab.get("show_streak", False),
                                  show_longest_streak=first_tab.get("show_longest_streak", True),
                                  show_buttons_dist=first_tab.get("show_buttons_dist", False),
                                  row_height=row_height,
                                  show_active_days=first_tab.get("show_active_days", True),
                                  show_forecast=first_tab.get("show_forecast", True))

        tab_widget.layout().addWidget(table)
        table.cellDoubleClicked.connect(dialog.on_cell_double_clicked)
        table.cellClicked.connect(dialog.on_cell_clicked)

    _fill_deck_table(dialog, table, stats_list, deck_id, index, do_resize=do_resize)

    if not hasattr(dialog, '_deck_tabs_populated'): dialog._deck_tabs_populated = set()

    # Only mark as populated if there was data
    if has_data:
        dialog._deck_tabs_populated.add(index)

    if index == dialog.tab_widget.currentIndex():
        # A plain update: forcing the repaint and running the event loop here also ran
        # the Deep Dive build steps queued meanwhile, all in one freeze.
        table.viewport().update()

        if not from_tab_change and hasattr(dialog, 'on_tab_changed'):
            dialog.on_tab_changed(index)

        # First deck tab can be populated before the widget is fully visible.
        # Retry a little later to avoid "squashed" columns on initial open.
        if do_resize and not getattr(table, "_has_been_resized", False):
            def _retry_resize():
                try:
                    if index != dialog.tab_widget.currentIndex():
                        return
                    if dialog.auto_resize_window(table, resize_window=False):
                        table._has_been_resized = True
                except Exception:
                    log_swallowed()
            queue_ui_callback(
                _retry_resize,
                delay_ms=120,
                owner=dialog,
                reason="deck_view.deferred_resize",
            )

def _fill_deck_table(dialog, table, stats_list, deck_id, tab_index, do_resize=True):
    return fill_deck_table(
        dialog,
        table,
        stats_list,
        deck_id,
        tab_index,
        do_resize=do_resize,
        deleted_tab_did=DELETED_TAB_DID,
    )


