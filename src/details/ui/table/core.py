# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import Qt, QTableWidgetItem
from ...widgets.chart_utils.formatting import fmt_num, stats_precision, TREND_PRECISION
from .header_menu import show_header_menu as show_header_menu_impl

class SortableTableWidgetItem(QTableWidgetItem):
    PIN_TOP = True

    def __init__(self, text, sort_value=None):
        super().__init__(text)
        self.sort_value = sort_value if sort_value is not None else text

    def __lt__(self, other):
        if not isinstance(other, QTableWidgetItem):
            return super().__lt__(other)
        
        is_self_total = self.data(Qt.ItemDataRole.UserRole) == "[[TOTAL]]"
        is_other_total = other.data(Qt.ItemDataRole.UserRole) == "[[TOTAL]]"
        
        if is_self_total or is_other_total:
            table = self.tableWidget()
            if table:
                order = table.horizontalHeader().sortIndicatorOrder()
                is_asc = (order == Qt.SortOrder.AscendingOrder)
                pin_top = SortableTableWidgetItem.PIN_TOP
                
                if is_self_total:
                    return is_asc if pin_top else not is_asc
                if is_other_total:
                    return not is_asc if pin_top else is_asc
            else:
                if is_self_total: return False 
                if is_other_total: return True
            
        sv = self.sort_value
        ov = getattr(other, 'sort_value', other.text())
        
        try:
            return float(sv) < float(ov)
        except (ValueError, TypeError):
            return str(sv).lower() < str(ov).lower()

def get_trend_html(curr, prev, show_trends, bigger_is_better=True, color_good="#4CAF50", color_bad="#F44336", points=False):
    if not show_trends or prev <= 0: return ""
    # points=True: gap in percentage points (for values that are already a %, like retention)
    diff = (curr - prev) if points else ((curr - prev) / prev) * 100
    if abs(diff) < 0.1: return ""
    color = color_good if (diff > 0) == bigger_is_better else color_bad
    symbol = "▲" if diff > 0 else "▼"
    if points:
        return f' <small style="color:{color}; font-weight:bold;">{symbol}{abs(diff):.{TREND_PRECISION}f} pts</small>'
    return f' <small style="color:{color}; font-weight:bold;">{symbol}{abs(diff):.{TREND_PRECISION}f}%</small>'

def get_dist_text(count, total, show_counts):
    if total > 0:
        v = count if show_counts else (count / total * 100)
        return f"{fmt_num(v)}" if show_counts else f"{v:.{stats_precision()}f}%"
    return "0" if show_counts else "0%"

def add_table_item(table, row, col, text, color=None, tooltip="", bold=False, sort_value=None):
    # When toggling visual widgets -> text: remove old widget to avoid overlap.
    table.removeCellWidget(row, col)
    it = SortableTableWidgetItem(text, sort_value=sort_value)
    if color: it.setBackground(color)
    if tooltip: it.setToolTip(tooltip)
    if bold:
        f = it.font()
        f.setBold(True)
        it.setFont(f)
    if text and (len(text) > 0 and (text[0].isdigit() or text == "N/A" or text == "-" or str(text).startswith("<"))):
        it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
    table.setItem(row, col, it)
    return it

def filter_table(dialog, text):
    from .filtering import filter_table as _impl

    return _impl(dialog, text)

def show_header_menu(dialog, pos, table, header):
    return show_header_menu_impl(dialog, pos, table, header)

def setup_table(
    dialog,
    table,
    show_time,
    show_reviews,
    show_retention,
    show_retention_young,
    show_retention_mature,
    show_avg_time,
    show_streak=False,
    show_longest_streak=False,
    show_buttons_dist=False,
    row_height=30,
    show_active_days=True,
    show_forecast=True,
):
    from .time_setup import setup_table as _impl

    return _impl(
        dialog=dialog,
        table=table,
        show_time=show_time,
        show_reviews=show_reviews,
        show_retention=show_retention,
        show_retention_young=show_retention_young,
        show_retention_mature=show_retention_mature,
        show_avg_time=show_avg_time,
        show_streak=show_streak,
        show_longest_streak=show_longest_streak,
        show_buttons_dist=show_buttons_dist,
        row_height=row_height,
        show_active_days=show_active_days,
        show_forecast=show_forecast,
        show_header_menu_fn=show_header_menu,
    )

def populate_table(
    table,
    results,
    totals,
    expanded_decks,
    deck_colors,
    range_type,
    show_time,
    show_reviews,
    show_retention,
    show_retention_young,
    show_retention_mature,
    show_buttons_dist,
    show_avg_time,
    show_streak,
    show_longest_streak,
    show_active_days,
    show_forecast,
    show_trends,
    show_counts,
    show_buttons_visual,
    show_retention_sparkline,
    use_decimal,
    hrs_unit,
    min_unit,
    tree_data,
    bin_labels,
    start_ms,
    end_ms,
    sort_col=1,
    sort_order=Qt.SortOrder.DescendingOrder,
    pin_top=True,
):
    from .populate import populate_table as _impl

    return _impl(
        table,
        results,
        totals,
        expanded_decks,
        deck_colors,
        range_type,
        show_time,
        show_reviews,
        show_retention,
        show_retention_young,
        show_retention_mature,
        show_buttons_dist,
        show_avg_time,
        show_streak,
        show_longest_streak,
        show_active_days,
        show_forecast,
        show_trends,
        show_counts,
        show_buttons_visual,
        show_retention_sparkline,
        use_decimal,
        hrs_unit,
        min_unit,
        tree_data,
        bin_labels,
        start_ms,
        end_ms,
        sort_col=sort_col,
        sort_order=sort_order,
        pin_top=pin_top,
    )

def setup_table_for_deck_view(
    dialog,
    table,
    show_time,
    show_reviews,
    show_retention,
    show_retention_young,
    show_retention_mature,
    show_avg_time,
    show_buttons_dist=False,
    show_streak=False,
    show_longest_streak=False,
    row_height=30,
    show_active_days=True,
    show_forecast=True,
):
    from .deck_setup import setup_table_for_deck_view as _impl

    return _impl(
        dialog=dialog,
        table=table,
        show_time=show_time,
        show_reviews=show_reviews,
        show_retention=show_retention,
        show_retention_young=show_retention_young,
        show_retention_mature=show_retention_mature,
        show_avg_time=show_avg_time,
        show_buttons_dist=show_buttons_dist,
        show_streak=show_streak,
        show_longest_streak=show_longest_streak,
        row_height=row_height,
        show_active_days=show_active_days,
        show_forecast=show_forecast,
        show_header_menu_fn=show_header_menu,
    )

