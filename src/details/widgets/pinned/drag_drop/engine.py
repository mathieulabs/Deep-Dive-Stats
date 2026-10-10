# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QWidget
from .. import WidgetRegistry
from ....ui import ConfigManager

class ReorderEngine:
    """
    Central logic for finding target positions and shifting widgets in layouts.
    """
    
    @staticmethod
    def _drag_id_from_widget(widget):
        """Return a stable DnD identifier for both pinned and dashboard cards."""
        if not widget:
            return None
        return getattr(widget, "widget_id", None) or getattr(widget, "config_key", None)

    @staticmethod
    def get_linear_target_index(layout, drop_pos, exclude_id, index_offset=0, vertical=False):
        """
        Finds the insertion index in a linear (H/V) layout.
        """
        other_items = []
        for i in range(layout.count()):
            item = layout.itemAt(i)
            w = item.widget()
            if w and ReorderEngine._drag_id_from_widget(w) != exclude_id:
                other_items.append(item)
        
        target_idx = len(other_items)
        for i, item in enumerate(other_items):
            rect = item.geometry()
            if vertical:
                if drop_pos.y() < rect.center().y():
                    target_idx = i
                    break
            else:
                if drop_pos.x() < rect.center().x():
                    target_idx = i
                    break
        
        return target_idx + index_offset

    @staticmethod
    def get_grid_target_index(layout, drop_pos, exclude_id):
        """
        Finds the insertion index in a multi-row (Masonry) layout.
        """
        other_items = []
        for i in range(layout.count()):
            item = layout.itemAt(i)
            w = item.widget()
            if w and ReorderEngine._drag_id_from_widget(w) != exclude_id:
                other_items.append(item)
        
        target_idx = len(other_items)
        for i, item in enumerate(other_items):
            rect = item.geometry()
            # Threshold: if cursor is above the item's bottom and to the left of its center
            if drop_pos.y() < rect.bottom():
                if drop_pos.y() < rect.top() or drop_pos.x() < rect.center().x():
                    target_idx = i
                    break
        return target_idx

    @staticmethod
    def shift_in_layout(layout, widget, target_idx):
        """
        Moves a widget to a new index in the layout if necessary.
        """
        if not widget: return False
        source_idx = layout.indexOf(widget)
        if source_idx == -1:
            target_id = ReorderEngine._drag_id_from_widget(widget)
            if target_id:
                for i in range(layout.count()):
                    w = layout.itemAt(i).widget()
                    if w and ReorderEngine._drag_id_from_widget(w) == target_id:
                        source_idx = i
                        break
        
        if source_idx != -1 and source_idx != target_idx:
            layout.removeWidget(widget)
            layout.insertWidget(target_idx, widget)
            return True
        return False

    @staticmethod
    def get_source_widget(layout, widget_id):
        """Finds the widget with the given ID in the layout (case-insensitive)."""
        if not widget_id: return None
        search_id = widget_id.lower()
        for i in range(layout.count()):
            w = layout.itemAt(i).widget()
            if w:
                wid = ReorderEngine._drag_id_from_widget(w)
                if wid and wid.lower() == search_id:
                    return w
                for child in w.findChildren(QWidget):
                    cid = ReorderEngine._drag_id_from_widget(child)
                    if cid and cid.lower() == search_id:
                        return w
        return None

    @staticmethod
    def sync_internal_list(layout, current_list):
        """Returns a new list ordered according to the layout's widgets."""
        new_list = []
        for i in range(layout.count()):
            w = layout.itemAt(i).widget()
            if w and w in current_list:
                new_list.append(w)
        return new_list

    @staticmethod
    def persist_reorder(layout, widget_type_group=None, manager=None):
        """
        Reads the current layout order and updates the WidgetRegistry.
        If widget_type_group is provided (e.g. 'stat_card'), it preserves the 
        relative position of other widget types.
        """
        all_pinned = WidgetRegistry.get_all()
        
        new_layout_ids = []
        for i in range(layout.count()):
            w = layout.itemAt(i).widget()
            wid = ReorderEngine._drag_id_from_widget(w)
            if wid:
                new_layout_ids.append(wid)
        
        if not widget_type_group:
            WidgetRegistry.reorder(new_layout_ids)
            return

        if widget_type_group == "deep_dive_chart":
            # Persist order specifically for Deep Dive
            VALID_CHARTS = [
                "activity", "retention", "heatmap", "future_due", "distribution", 
                "hourly", "card_counts", "review_intervals", "stability", 
                "difficulty", "retrievability", "added"
            ]
            final_order = [wid for wid in new_layout_ids if wid in VALID_CHARTS]
            for vc in VALID_CHARTS:
                if vc not in final_order:
                    final_order.append(vc)
            
            if manager:
                from ....ui import Config
                manager.addon_config.set_value(Config.DEEP_DIVE_CHART_ORDER, final_order)
            else:
                from aqt import mw
                from ....ui import Config
                ConfigManager(mw).set_value(Config.DEEP_DIVE_CHART_ORDER, final_order)
            return

        # Scoped reorder (pinned widgets): the layout only holds the widgets shown in
        # the current context. Put them back into the registry slots they already
        # occupy, in their new order, and leave every other widget where it is.
        all_ids = [w["id"] for w in all_pinned]
        layout_set = set(new_layout_ids)
        ordered_iter = iter([wid for wid in new_layout_ids if wid in set(all_ids)])
        final_ids = [next(ordered_iter) if wid in layout_set else wid for wid in all_ids]

        WidgetRegistry.reorder(final_ids)

