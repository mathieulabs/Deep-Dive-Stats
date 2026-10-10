# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import (
    Qt, QTableWidget, QCursor, QFont, QFontMetrics
)
import re
from ...widgets.stats_cards import (
    apply_dashboard_stat_values,
    clear_dashboard_stat_values,
)
from ...logic.refresh import queue_ui_callback
from .trend import on_trend_toggled as on_trend_toggled_impl
from .toggles import (
    on_retention_spark_toggled as on_retention_spark_toggled_impl,
    on_visual_buttons_toggled as on_visual_buttons_toggled_impl,
    on_visual_option_toggled as on_visual_option_toggled_impl,
)
from ...logic.logger import log_swallowed

DELETED_TAB_DID = "__deleted_cards__"



def _schedule_deferred_table_resize(dialog, table, index, *, attempts=3, delay_ms=80):
    """Retry adaptive table sizing once the selected tab is actually visible."""
    if table is None or attempts <= 0:
        return

    token = int(getattr(table, "_deferred_resize_token", 0)) + 1
    table._deferred_resize_token = token

    def _retry(remaining=attempts, expected_token=token):
        try:
            if getattr(table, "_deferred_resize_token", None) != expected_token:
                return
            if index != dialog.tab_widget.currentIndex():
                return
            if getattr(table, "_has_been_resized", False):
                return
            if dialog.auto_resize_window(table, resize_window=False):
                table._has_been_resized = True
                return
            if remaining > 1:
                queue_ui_callback(
                    lambda: _retry(remaining - 1, expected_token),
                    delay_ms=delay_ms,
                    owner=dialog,
                    reason="dialog.on_tab_changed.deferred_table_resize.retry",
                )
        except Exception:
            log_swallowed()

    queue_ui_callback(
        lambda: _retry(attempts, token),
        delay_ms=delay_ms,
        owner=dialog,
        reason="dialog.on_tab_changed.deferred_table_resize",
    )


def _is_click_on_folder_handle(table, item):
    """Determine if a global cursor position is over the folder toggle area (icon+text) or whitespace."""
    text = item.text()
    if "▸" not in text and "▾" not in text:
        return False
        
    pos = table.mapFromGlobal(QCursor.pos())
    cell_rect = table.visualItemRect(item)
    click_x = pos.x() - cell_rect.x()
    
    prefix_match = re.search(r"<span style='font-family:Consolas, monospace; color:#606060;'>(.*?)</span>([▸▾])", text)
    if not prefix_match:
        prefix_match = re.search(
            r"<span style='font-family:Consolas, monospace; color:[^;]+;'>(.*?)</span>([^<\s])",
            text,
        )
    if prefix_match:
        prefix_html = prefix_match.group(1)
        icon = prefix_match.group(2)
        prefix_text = prefix_html.replace("&nbsp;", " ") + icon + " "
        
        f_c = QFont("Consolas", table.font().pointSize())
        if not f_c.exactMatch(): f_c = QFont("monospace", table.font().pointSize())
        fm_c = QFontMetrics(f_c)
        
        name_part = text.split("</span>")[-1]
        clean_name = re.sub('<[^<]+?>', '', name_part).strip()
        f_m = QFont(table.font())
        if "<b>" in name_part: f_m.setBold(True)
        fm_m = QFontMetrics(f_m)
        
        content_width = fm_c.horizontalAdvance(prefix_text) + fm_m.horizontalAdvance(clean_name) + 12 # 12px buffer
        return click_x <= content_width
    
    return click_x <= 100 # Simple fallback

def _selected_deck_dids(dialog, table):
    """Deck ids behind the selected rows.

    Returns "total" when the Total row is selected (it already covers everything).
    Otherwise a list of deck ids, plus the "deleted" token for the Deleted Cards row.
    Decks already covered by a selected parent are dropped, and a folder row without
    a deck of its own stands for its sub-decks.
    """
    tab_stats = dialog.tab_stats.get(dialog.tab_widget.currentIndex()) or {}
    results = tab_stats.get("results", [])
    by_name = {r.get("full_name"): r for r in results}
    names = []
    deleted = False
    for idx in table.selectionModel().selectedRows():
        if table.isRowHidden(idx.row()):
            continue
        item = table.item(idx.row(), 0)
        name = item.data(Qt.ItemDataRole.UserRole) if item else None
        r = by_name.get(name)
        if r is None:
            continue
        if r.get("is_total_row"):
            return "total"
        if r.get("is_deleted"):
            deleted = True
            continue
        names.append(name)
    kept = [n for n in names if not any(n != o and n.startswith(o + "::") for o in names)]
    dids = []
    for n in kept:
        did = by_name[n].get("did")
        if did is not None:
            dids.append(did)
            continue
        for r in results:
            rn = r.get("full_name") or ""
            if rn.startswith(n + "::") and r.get("did") is not None and r.get("leaf_did") == r.get("did"):
                dids.append(r["did"])
    dids = list(dict.fromkeys(dids))
    if deleted:
        dids.append("deleted")
    return dids


def _open_selection_merged(dialog, table):
    """Open one Deep Dive on all selected rows when several rows are selected."""
    if not isinstance(table, QTableWidget):
        return False
    if len(table.selectionModel().selectedRows()) < 2:
        return False
    dids = _selected_deck_dids(dialog, table)
    idx = dialog.tab_widget.currentIndex()
    tabs_config = dialog.get_active_tabs_config()
    if 0 <= idx < len(tabs_config):
        dialog.target_time_span = tabs_config[idx].get("range", None)
    if dids == "total":
        dialog.target_deck_id = "[[TOTAL]]"
        dialog.deep_dive_manager.open_deep_dive("[[TOTAL]]", "Total", period_range=dialog.target_time_span)
        return True
    if len(dids) == 1:
        # A parent and its sub-decks were selected: the parent alone covers them all.
        tab_stats = dialog.tab_stats.get(idx) or {}
        row = next((r for r in tab_stats.get("results", []) if r.get("did") == dids[0]), None)
        if row is None:
            return False
        name = row.get("full_name")
        dialog.target_deck_id = name
        dialog.deep_dive_manager.open_deep_dive(name, re.sub(r"<[^<]+?>", "", row.get("display_name") or name), period_range=dialog.target_time_span)
        return True
    if len(dids) < 2:
        return False
    dialog.target_deck_id = dids
    dialog.deep_dive_manager.open_deep_dive(dids, f"{len(dids)} decks", period_range=dialog.target_time_span)
    return True


def on_cell_double_clicked(dialog, row, col):
    """Handle double click on table cell to expand chart or open Deep-Dive."""
    sender_table = dialog.sender()
    if not sender_table: return
    
    # If the dialog is in Full Table mode, switch to Split View immediately
    if hasattr(dialog, 'layout_state') and dialog.layout_state == 0:
        dialog.switch_layout(1)

    name_item = sender_table.item(row, 0)
    if not name_item: return

    if dialog.view_mode == 'time' and _open_selection_merged(dialog, sender_table):
        return
    
    # If double-clicking the folder TEXT/ICON area, don't open Deep Dive
    # This prevents the "opening anyway" issue when users double-click to toggle
    if col == 0 and _is_click_on_folder_handle(sender_table, name_item):
        return

    title = name_item.text()
    identifier = name_item.data(Qt.ItemDataRole.UserRole)
    
    if identifier is None:
        clean_title = re.sub('<[^<]+?>', '', title).strip()
        dialog.deep_dive_manager.open_deep_dive(clean_title, clean_title)
        return

    clean_title = re.sub('<[^<]+?>', '', title).strip()
    
    if dialog.view_mode == 'time':
        dialog.target_deck_id = identifier
        current_idx = dialog.tab_widget.currentIndex()
        if current_idx >= 0:
             tabs_config = dialog.get_active_tabs_config()
             if current_idx < len(tabs_config):
                 dialog.target_time_span = tabs_config[current_idx].get("range", None)
                 
        dialog.deep_dive_manager.open_deep_dive(identifier, clean_title, period_range=dialog.target_time_span)
    else:
        dialog.target_time_span = identifier
        current_idx = dialog.tab_widget.currentIndex()
        deck_name = dialog.tab_widget.tabText(current_idx)
        
        w = dialog.tab_widget.widget(current_idx)
        if w:
            raw_deck_id = w.property("deck_id")
            dialog.target_deck_id = None if raw_deck_id == DELETED_TAB_DID else raw_deck_id
            
        dialog.deep_dive_manager.open_deep_dive(dialog.target_deck_id, f"{deck_name} ({clean_title})", period_range=identifier)

def on_cell_clicked(dialog, row, col):
    """Handle single click on table cell to open Deep-Dive or toggle hierarchy."""
    if col != 0:
        on_cell_double_clicked(dialog, row, col)
        return
        
    table = dialog.sender()
    if not isinstance(table, QTableWidget):
        return
        
    item = table.item(row, col)
    if not item:
        return
        
    full_path = item.data(Qt.ItemDataRole.UserRole)
    if full_path is None:
        return
        
    if dialog.view_mode == 'time':
        dialog.target_deck_id = full_path
    else:
        dialog.target_time_span = full_path
        
    # Targeted Toggle vs Deep-Dive within the "Deck" column
    if _is_click_on_folder_handle(table, item):
        pass
    else:
        on_cell_double_clicked(dialog, row, col)
        return
        
    if full_path in dialog.expanded_decks:
        dialog.expanded_decks.remove(full_path)
        is_expanded = False
    else:
        dialog.expanded_decks.add(full_path)
        is_expanded = True
        
    from ..deck_view.visibility import persist_expanded_decks
    persist_expanded_decks(dialog)
        
    if dialog.view_mode == 'time':
        for i in range(dialog.tab_widget.count()):
            tab = dialog.tab_widget.widget(i)
            tab_table = tab.findChild(QTableWidget)
            if not tab_table: continue
            
            for r in range(tab_table.rowCount()):
                r_item = tab_table.item(r, 0)
                if not r_item: continue
                r_path = r_item.data(Qt.ItemDataRole.UserRole)
                if not r_path: continue
                
                if r_path == full_path:
                    curr_text = r_item.text()
                    if is_expanded and "▸" in curr_text:
                        r_item.setText(curr_text.replace("▸", "▾", 1))
                    elif not is_expanded and "▾" in curr_text:
                        r_item.setText(curr_text.replace("▾", "▸", 1))
                
                # A row is visible if all its ancestors are expanded
                parts = r_path.split("::")
                ancestors = ["::".join(parts[:j]) for j in range(1, len(parts))]
                
                should_hide = False
                for ancestor in ancestors:
                    if ancestor not in dialog.expanded_decks:
                        should_hide = True
                        break
                
                if tab_table.isRowHidden(r) != should_hide:
                    tab_table.setRowHidden(r, should_hide)
    else:
        dialog.load_deck_view(reason="deck_hierarchy_toggle", force=True)

def on_tab_changed(dialog, index):
    """Handle tab change and adjust window width to fit current tab content."""
    if index < 0: return
    
    from ..table import filter_table
    
    if dialog.view_mode == 'deck':
        from ..deck_view import (
            _refresh_deck_tab_header_styles,
            populate_deck_tab,
            prioritize_deck_tab,
        )
        prioritize_deck_tab(dialog, index)
        tab = dialog.tab_widget.widget(index)
        deck_id = tab.property("deck_id") if tab else None
        if deck_id in getattr(dialog, 'deck_view_data', {}):
            populate_deck_tab(dialog, index, do_resize=True, from_tab_change=True)
        else:
            from ..deck_view.manager import show_loading_placeholder
            show_loading_placeholder(tab)
        _refresh_deck_tab_header_styles(dialog)
    elif dialog.view_mode == 'time':
        from ...logic.tabs import prioritize_time_tab, populate_time_tab
        prioritize_time_tab(dialog, index)
        populate_time_tab(dialog, index, do_resize=True)

    if index in dialog.tab_stats:
         tab = dialog.tab_widget.widget(index)
         table = tab.findChild(QTableWidget)
         if table:
             # Only resize window and columns once per tab to avoid UI lag/flicker
             if not getattr(table, '_has_been_resized', False):
                 if dialog.auto_resize_window(table, resize_window=False):
                     table._has_been_resized = True
                 else:
                     _schedule_deferred_table_resize(dialog, table, index)
                 
             if hasattr(dialog, 'search_bar') and dialog.view_mode == 'time':
                 filter_table(dialog, dialog.search_bar.text())
                 
             if hasattr(dialog, '_last_horizontal_scroll'):
                 table.horizontalScrollBar().setValue(dialog._last_horizontal_scroll)

             # Cell widgets (bars, sparklines) otherwise move to their column on Qt's delayed
             # layout pass, so they visibly jump after every tab switch.
             if table.isVisible():
                 try:
                     table.doItemsLayout()
                 except Exception:
                     log_swallowed()
    
    # Do not overwrite the dashboard stats from the tab while Deep Dive charts are active and visible (layout_state > 0)
    if hasattr(dialog, 'layout_state') and dialog.layout_state > 0:
        return

    stats = dialog.tab_stats.get(index, {})
    if stats:
        apply_dashboard_stat_values(dialog, stats, refresh=True)
    else:
        clear_dashboard_stat_values(dialog, "-", refresh=True)

def on_trend_toggled(dialog, checked):
    return on_trend_toggled_impl(dialog, checked)

def on_search_text_changed(dialog, text):
    from ..table import filter_table
    if dialog.view_mode == 'time':
        filter_table(dialog, text)
    else:
        from ..deck_view import refresh_deck_tab_visibility
        refresh_deck_tab_visibility(dialog)

def filter_deck_tabs(dialog, text):
    """Filter deck tabs based on search text."""
    text = text.lower()
    visible_indices = []
    current_idx = dialog.tab_widget.currentIndex()
    
    for i in range(dialog.tab_widget.count()):
        tab_name = dialog.tab_widget.tabText(i).lower()
        tab_widget = dialog.tab_widget.widget(i)
        deck_id = str(tab_widget.property("deck_id") or "").lower()
        
        is_visible = (text in tab_name) or (text in deck_id)
        dialog.tab_widget.setTabVisible(i, is_visible)
        if is_visible:
            visible_indices.append(i)
            
    # If the current tab became hidden, switch to the first available visible tab
    if current_idx >= 0 and not dialog.tab_widget.isTabVisible(current_idx):
        if visible_indices:
            next_idx = next((idx for idx in visible_indices if idx > current_idx), visible_indices[0])
            dialog.tab_widget.setCurrentIndex(next_idx)

def on_visual_buttons_toggled(dialog, state):
    return on_visual_buttons_toggled_impl(dialog, state)

def on_visual_option_toggled(dialog, key, value):
    return on_visual_option_toggled_impl(dialog, key, value)

def on_retention_spark_toggled(dialog, state):
    return on_retention_spark_toggled_impl(dialog, state)

