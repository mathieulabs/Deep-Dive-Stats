# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors

from aqt.qt import QColor, QFontMetrics, QTableWidgetItem, Qt

from .. import format_hours
from ...widgets import SegmentedBarWidget
from ...logic.data.core.forecast import forecast_days
from .retention_visual import retention_bar, retention_visual_on
from ...widgets.chart_utils.formatting import fmt_num, stats_precision
from ...widgets.chart_utils.theme import get_theme_colors
from ....qss import set_qss


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
    from .core import SortableTableWidgetItem, get_dist_text, get_trend_html

    SortableTableWidgetItem.PIN_TOP = pin_top

    try:
        from .. import Config as _Cfg, get_chart_color as _gcc
        _color_good = _gcc(_Cfg.COLOR_GOOD)
        _color_bad  = _gcc(_Cfg.COLOR_AGAIN)
        _color_hard = _gcc(_Cfg.COLOR_HARD)
        _color_easy = _gcc(_Cfg.COLOR_EASY)
    except Exception:
        _color_good = "#4CAF50"
        _color_bad  = "#F44336"
        _color_hard = "#FF9800"
        _color_easy = "#2196F3"
    updates_were_enabled = table.updatesEnabled()
    sorting_was_enabled = table.isSortingEnabled()
    table.setUpdatesEnabled(False)
    table.setSortingEnabled(False)

    # If sorting is requested, we re-flatten the tree_data hierarchically
    if sort_col is not None and tree_data:
        # Copy entries once and keep child lookups O(1) instead of rescanning the whole tree.
        tree_data = {k: dict(v) for k, v in tree_data.items()}
        children_map = {}
        for path, info in tree_data.items():
            children_map.setdefault(info.get("parent"), []).append(path)

        header_text = table.horizontalHeaderItem(sort_col).text() if table.horizontalHeaderItem(sort_col) else ""

        def get_val(d):
            if header_text == "Deck": return d.get("display_name", d.get("full_name", "")).lower()
            if header_text == "Time": return d.get("time_ms", 0)
            if header_text == "Reviews": return d.get("reviews", 0)
            if header_text == "Retention":
                r = d.get("reviews", 0)
                return (d.get("passed", 0) / r * 100) if r > 0 else -1
            if header_text == "Ret. Young":
                r = d.get("rev_young", 0)
                return (d.get("pass_young", 0) / r * 100) if r > 0 else -1
            if header_text == "Ret. Mature":
                r = d.get("rev_mat", 0)
                return (d.get("pass_mat", 0) / r * 100) if r > 0 else -1
            if header_text == "Avg Time":
                r = d.get("reviews", 0)
                return (d.get("time_ms", 0) / r) if r > 0 else 0
            if header_text == "Longest Streak": return d.get("streak_longest", 0)
            if header_text == "Streak": return d.get("streak_current", 0)
            if header_text == "Active Days": return d.get("active_days", 0)
            if header_text == "Forecast":
                days = None if d.get("is_deleted") else forecast_days(d.get("new_limit", 0), d.get("max_days"), d.get("remaining_new", 0))
                return -1 if days is None else days
            return 0

        reverse = (sort_order == Qt.SortOrder.DescendingOrder)

        new_results = []

        def add_children_sorted(parent_path, prefix):
            children = list(children_map.get(parent_path, ()))
            children.sort(key=lambda p: get_val(tree_data[p]), reverse=reverse)

            count = len(children)
            for i, child_path in enumerate(children):
                is_last = (i == count - 1)
                curr_prefix = "└── " if is_last else "├── "
                child_prefix_add = "    " if is_last else "│   "
                tree_data[child_path]["tree_prefix"] = prefix + curr_prefix
                new_results.append(tree_data[child_path])
                add_children_sorted(child_path, prefix + child_prefix_add)

        roots = list(children_map.get(None, ()))
        roots.sort(key=lambda p: get_val(tree_data[p]), reverse=reverse)
        for root in roots:
            tree_data[root]["tree_prefix"] = ""
            new_results.append(tree_data[root])
            add_children_sorted(root, "")

        results = new_results

    table.setRowCount(len(results) + 1) # +1 for Total row
    total_row_idx = 0 if pin_top else len(results)

    cols_widths = [0, 0, 0, 0]
    fm = QFontMetrics(table.font())
    trend_html_cache = {}
    dist_text_cache = {}
    fmt_num_cache = {}
    formatted_time_cache = {}
    days_text_cache = {}
    retention_text_cache = {}

    def get_trend_html_local(curr, prev, bigger_is_better=True, points=False):
        key = (curr, prev, bigger_is_better, points)
        cached = trend_html_cache.get(key)
        if cached is not None:
            return cached
        cached = get_trend_html(curr, prev, show_trends, bigger_is_better,
                                color_good=_color_good, color_bad=_color_bad, points=points)
        trend_html_cache[key] = cached
        return cached

    def get_dist_text_local(count, total):
        key = (count, total, show_counts)
        cached = dist_text_cache.get(key)
        if cached is not None:
            return cached
        cached = get_dist_text(count, total, show_counts)
        dist_text_cache[key] = cached
        return cached

    def fmt_num_local(value):
        cached = fmt_num_cache.get(value)
        if cached is not None:
            return cached
        cached = fmt_num(value)
        fmt_num_cache[value] = cached
        return cached

    def formatted_time_local(hours_value):
        key = (hours_value, use_decimal, hrs_unit, min_unit)
        cached = formatted_time_cache.get(key)
        if cached is not None:
            return cached
        cached = format_hours(hours_value, use_decimal=use_decimal, hrs_text=hrs_unit, min_text=min_unit)
        formatted_time_cache[key] = cached
        return cached

    def days_text_local(days_value):
        days_int = int(days_value)
        cached = days_text_cache.get(days_int)
        if cached is not None:
            return cached
        cached = f"{days_int} days"
        days_text_cache[days_int] = cached
        return cached

    def get_retention_text_parts(passed, rev_count, prev_pass, prev_rev):
        key = (passed, rev_count, prev_pass, prev_rev, show_counts, show_trends)
        cached = retention_text_cache.get(key)
        if cached is not None:
            return cached

        if rev_count <= 0:
            cached = ("N/A", "", -1, "")
            retention_text_cache[key] = cached
            return cached

        ret = (passed / rev_count * 100)
        text = "0%" if ret == 0 else f"{ret:.{stats_precision()}f}%"
        prev_ret = (prev_pass / prev_rev * 100) if (prev_rev or 0) > 0 else 0
        trend = get_trend_html_local(ret, prev_ret, points=True)
        tooltip = f"Pass: {passed} / Fail: {rev_count - passed}"

        if show_counts:
            failed = rev_count - passed
            text += (
                f" (<span style='color:{_color_good}'>{fmt_num_local(passed)}</span>/"
                f"<span style='color:{_color_bad}'>{fmt_num_local(failed)}</span>)"
            )

        cached = (text, trend, ret, tooltip)
        retention_text_cache[key] = cached
        return cached

    if show_buttons_dist and not show_buttons_visual:
        for res in results:
            reviews = res["reviews"]
            c_again = res["again"]
            c_hard = res["hard"]
            c_good = res["good"]
            c_easy = res["easy"]

            texts = [
                get_dist_text_local(c_again, reviews),
                get_dist_text_local(c_hard, reviews),
                get_dist_text_local(c_good, reviews),
                get_dist_text_local(c_easy, reviews)
            ]
            for i, txt in enumerate(texts):
                basis_txt = "100.00%" if not show_counts else txt
                w = fm.horizontalAdvance(basis_txt)
                if w > cols_widths[i]: cols_widths[i] = w

        t_texts = [
            get_dist_text_local(totals["again"], totals["rev"]),
            get_dist_text_local(totals["hard"], totals["rev"]),
            get_dist_text_local(totals["good"], totals["rev"]),
            get_dist_text_local(totals["easy"], totals["rev"])
        ]
        for i, txt in enumerate(t_texts):
            basis_txt = "100.00%" if not show_counts else txt
            w = fm.horizontalAdvance(basis_txt)
            if w > cols_widths[i]: cols_widths[i] = w

        cols_widths = [w + 20 for w in cols_widths]

    def add_data_item(row, col, text, color=None, tooltip="", sort_value=None):
        it = SortableTableWidgetItem(text, sort_value=sort_value)
        if color:
            it.setBackground(color)
        if tooltip:
            it.setToolTip(tooltip)
        it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        set_item(row, col, it)
        return it

    _table_theme = get_theme_colors(table)
    _ts = _table_theme.get("text_secondary")
    tree_prefix_color = (_ts.name() if _ts and hasattr(_ts, "name") else None) or (
        "#71717a" if _table_theme.get("is_dark") else "#606060"
    )
    deck_colors_map = deck_colors or {}
    qcolor_cache = {}
    row_color_cache = {}
    hidden_state_cache = {}
    expanded_decks_set = expanded_decks if isinstance(expanded_decks, set) else set(expanded_decks or [])
    set_row_hidden = table.setRowHidden
    set_item = table.setItem
    set_cell_widget = table.setCellWidget
    def resolve_row_color(data):
        did = data.get("did")
        is_deleted = data.get("is_deleted", False)
        cache_key = ("deleted" if is_deleted else did if did else "folder")
        if cache_key in row_color_cache:
            return row_color_cache[cache_key]

        row_color = None
        color_key = None
        if not is_deleted:
            if did and str(did) in deck_colors_map:
                color_key = str(did)
            elif not did and "folder" in deck_colors_map:
                color_key = "folder"

        if color_key is not None:
            row_color = qcolor_cache.get(color_key)
            if row_color is None:
                c = QColor(deck_colors_map[color_key])
                if c.isValid():
                    c.setAlpha(50)
                    row_color = c
                qcolor_cache[color_key] = row_color

        row_color_cache[cache_key] = row_color
        return row_color

    def is_result_hidden(data):
        full_name = data["full_name"]
        cached = hidden_state_cache.get(full_name)
        if cached is not None:
            return cached

        parent_path = data.get("parent")
        is_hidden = False
        if parent_path:
            curr_p = parent_path
            while curr_p:
                if curr_p not in expanded_decks_set:
                    is_hidden = True
                    break
                p_info = tree_data.get(curr_p)
                curr_p = p_info.get("parent") if p_info else None

        if not is_hidden and data["reviews"] == 0 and data["time_ms"] == 0:
            is_hidden = True

        hidden_state_cache[full_name] = is_hidden
        return is_hidden

    for row_idx, data in enumerate(results):
        row = (row_idx + 1) if pin_top else row_idx
        full_name = data["full_name"]
        display_name = data.get("display_name", data["full_name"])
        has_children = data.get("has_children", False)
        tree_prefix = data.get("tree_prefix", "")

        is_hidden = is_result_hidden(data)
        time_ms = data["time_ms"]
        reviews = data["reviews"]
        set_row_hidden(row, is_hidden)

        time_hours = time_ms / 1000 / 60 / 60
        row_color = resolve_row_color(data)

        col = 0
        icon = ""
        tree_prefix_html = tree_prefix.replace(" ", "&nbsp;")
        if has_children:
            icon = "▾ " if full_name in expanded_decks else "▸ "

        name_text = f"<span style='font-family:Consolas, monospace; color:{tree_prefix_color};'>{tree_prefix_html}</span>{icon}{display_name}"

        if has_children:
            name_text = f"<b>{name_text}</b>"

        item = SortableTableWidgetItem(name_text, sort_value=display_name)

        if row_color:
            item.setBackground(row_color)

        item.setData(Qt.ItemDataRole.UserRole, full_name)
        # Mark row as empty if it has 0 data for this period (used by filter_table)
        item.setData(Qt.ItemDataRole.UserRole + 1, reviews == 0 and time_ms == 0)
        set_item(row, col, item)
        col += 1

        if show_time:
            time_val = formatted_time_local(time_hours)
            time_trend = get_trend_html_local(time_hours, (data.get("prev_time_ms", 0)/3600000))
            it = add_data_item(row, col, f"{time_val}{time_trend}", row_color, sort_value=time_hours)
            it.setData(Qt.ItemDataRole.UserRole, range_type)
            col += 1

        if show_reviews:
            rev_trend = get_trend_html_local(reviews, data.get("prev_reviews", 0))
            add_data_item(row, col, f"{fmt_num_local(reviews)}{rev_trend}", row_color, sort_value=reviews)
            col += 1

        def add_retention_cell(key_suffix, passed, rev, prev_pass, prev_rev, col):
            rev_count = rev if rev else 0
            if rev_count > 0 and retention_visual_on(key_suffix):
                add_data_item(row, col, "", row_color, sort_value=passed / rev_count * 100)
                set_cell_widget(
                    row, col,
                    retention_bar(passed, rev_count, parent=table, background=row_color.name() if row_color else None),
                )
            elif rev_count > 0:
                text, trend, ret, tooltip = get_retention_text_parts(
                    passed, rev_count, prev_pass, prev_rev
                )
                if table.cellWidget(row, col) is not None:
                    table.removeCellWidget(row, col)
                add_data_item(row, col, f"{text}{trend}", row_color, tooltip=tooltip, sort_value=ret)
            else:
                add_data_item(row, col, "N/A", row_color, sort_value=-1)

        if show_retention:
            add_retention_cell("all", data["passed"], reviews, data.get("prev_passed",0), data.get("prev_reviews",0), col)
            col += 1

        if show_retention_young:
            add_retention_cell("young", data["pass_young"], data["rev_young"], data.get("prev_pass_young",0), data.get("prev_rev_young",0), col)
            col += 1

        if show_retention_mature:
            add_retention_cell("mature", data["pass_mat"], data["rev_mat"], data.get("prev_pass_mat",0), data.get("prev_rev_mat",0), col)
            col += 1

        if show_buttons_dist:
            if show_buttons_visual:
                counts = [data["again"], data["hard"], data["good"], data["easy"]]
                seg_widget = SegmentedBarWidget(counts, parent=table, animate=False)
                add_data_item(row, col, "", row_color)
                set_cell_widget(row, col, seg_widget)
            else:
                existing = table.cellWidget(row, col)
                if existing is not None:
                    table.removeCellWidget(row, col)
                cols_c = [_color_bad, _color_hard, _color_good, _color_easy]
                counts = [data["again"], data["hard"], data["good"], data["easy"]]
                html = "<table style='border-collapse: collapse;'><tr>"
                for i, count in enumerate(counts):
                    text = get_dist_text_local(count, reviews)
                    val_str = f"<span style='color:{cols_c[i]}'>{text}</span>"
                    html += f"<td align='center' width='{cols_widths[i]}'>{val_str}</td>"
                    if i < 3: html += "<td width='10' align='center'><span style='color:#808080'>|</span></td>"
                html += "</tr></table>"
                item = QTableWidgetItem(html)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if row_color: item.setBackground(row_color)
                set_item(row, col, item)
            col += 1

        if show_avg_time:
            if reviews > 0:
                avg_secs = (time_ms / 1000) / reviews
                prev_time = data.get("prev_time_ms", 0)
                prev_rev = data.get("prev_reviews", 0)
                prev_avg = (prev_time / 1000) / prev_rev if prev_rev > 0 else 0
                avg_trend = get_trend_html_local(avg_secs, prev_avg, bigger_is_better=False)
                add_data_item(row, col, f"{avg_secs:.{stats_precision()}f}s{avg_trend}", row_color, sort_value=avg_secs)
            else:
                add_data_item(row, col, "N/A", row_color, sort_value=-1)
            col += 1

        c_s = data.get("streak_current", None)
        l_s = data.get("streak_longest", None)

        if show_longest_streak:
             if isinstance(l_s, (int, float)):
                 add_data_item(row, col, days_text_local(l_s), row_color, sort_value=l_s)
             else:
                 add_data_item(row, col, "-", row_color, sort_value=-1)
             col += 1

        if show_streak:
             if isinstance(c_s, (int, float)):
                 txt = days_text_local(c_s)
                 it = add_data_item(row, col, txt, row_color, sort_value=c_s)
                 if c_s >= 365: it.setForeground(QColor("#FFD700"))
                 elif c_s >= 30: it.setForeground(QColor("#52c41a"))
             else:
                 add_data_item(row, col, "-", row_color, sort_value=-1)
             col += 1

        if show_active_days:
            add_data_item(row, col, fmt_num_local(data["active_days"]), row_color, sort_value=data["active_days"])
            col += 1

        if show_forecast:
            rem_new = data.get("remaining_new", 0)
            target_rate = data.get("new_limit", 0)
            days_left = None if data.get("is_deleted") else forecast_days(target_rate, data.get("max_days"), rem_new)
            if days_left is None:
                ft = "-"
                tooltip = f"New cards off | New cards left: {rem_new}"
            else:
                ft = days_text_local(days_left)
                tooltip = f"{target_rate} new/day | New cards left: {rem_new}"

            add_data_item(row, col, ft, row_color, tooltip, sort_value=-1 if days_left is None else days_left)
            col += 1

            col += 1

    def set_total_item(col, text, tooltip="", bg=None, sort_value=None):
        if not bg:
             if "total" in deck_colors:
                 c = QColor(deck_colors["total"])
                 if c.isValid():
                     c.setAlpha(50)
                     bg = c

        it = SortableTableWidgetItem(text, sort_value=sort_value)
        f = it.font()
        f.setBold(True)
        it.setFont(f)
        it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if tooltip: it.setToolTip(tooltip)
        if bg: it.setBackground(bg)
        it.setData(Qt.ItemDataRole.UserRole, "[[TOTAL]]")
        # When toggling visual widgets -> text on total row.
        table.removeCellWidget(total_row_idx, col)
        table.setItem(total_row_idx, col, it)
        return it

    set_total_item(0, "Total")

    col = 1
    if show_time:
        t_time_val = formatted_time_local(totals["time"])
        t_time_trend = get_trend_html_local(totals["time"], totals["prev_time"])
        set_total_item(col, f"{t_time_val}{t_time_trend}", sort_value=totals["time"])
        col += 1

    if show_reviews:
        t_rev_trend = get_trend_html_local(totals["rev"], totals["prev_rev"])
        set_total_item(col, f"{fmt_num_local(totals['rev'])}{t_rev_trend}", sort_value=totals['rev'])
        col += 1

    def add_total_retention(key, passed, rev, prev_pass, prev_rev):
        nonlocal col
        if rev > 0 and retention_visual_on(key):
            ret = (passed / rev * 100)
            set_total_item(col, "", sort_value=ret)
            total_bar_bg = None
            if "total" in deck_colors:
                c = QColor(deck_colors["total"])
                if c.isValid():
                    c.setAlpha(50)
                    total_bar_bg = c.name()
            table.setCellWidget(total_row_idx, col, retention_bar(passed, rev, parent=table, background=total_bar_bg))
        elif rev > 0:
            ret = (passed / rev * 100)
            text = "0%" if ret == 0 else f"{ret:.{stats_precision()}f}%"
            prev_ret = (prev_pass / prev_rev * 100) if prev_rev > 0 else 0
            trend = get_trend_html_local(ret, prev_ret, points=True)
            if show_counts:
                    failed = rev - passed
                    text_bold = "0%" if ret == 0 else f"{ret:.{stats_precision()}f}%"
                    text = f"<b>{text_bold}</b> (<span style='color:{_color_good}'>{fmt_num_local(passed)}</span>/<span style='color:{_color_bad}'>{fmt_num_local(failed)}</span>)"
            set_total_item(col, f"{text}{trend}", tooltip=f"Total Pass: {fmt_num_local(passed)} / Fail: {fmt_num_local(rev - passed)}" if rev > 0 else "", sort_value=ret)
        else:
            set_total_item(col, "N/A", sort_value=-1)
        col += 1

    if show_retention:
        add_total_retention("all", totals["pass"], totals["rev"], totals["prev_pass"], totals["prev_rev"])
    if show_retention_young:
        add_total_retention("young", totals["pass_young"], totals["rev_young"], totals["prev_pass_young"], totals["prev_rev_young"])
    if show_retention_mature:
        add_total_retention("mature", totals["pass_mat"], totals["rev_mat"], totals["prev_pass_mat"], totals["prev_rev_mat"])

    if show_buttons_dist:
        if show_buttons_visual:
             counts = [totals["again"], totals["hard"], totals["good"], totals["easy"]]
             seg_widget = SegmentedBarWidget(counts, parent=table, animate=False)

             row_bg = None
             if "total" in deck_colors:
                 c = QColor(deck_colors["total"])
                 if c.isValid(): c.setAlpha(50); row_bg = c
             if row_bg: set_qss(seg_widget, f"background-color: {row_bg.name()};")
             set_total_item(col, "")
             table.setCellWidget(total_row_idx, col, seg_widget)
        else:
             cols_c = [_color_bad, _color_hard, _color_good, _color_easy]
             html = "<table style='border-collapse: collapse;'><tr>"
             for i, txt in enumerate(t_texts):
                 val_str = f"<span style='color:{cols_c[i]}'><b>{txt}</b></span>"
                 html += f"<td align='center' width='{cols_widths[i]}'>{val_str}</td>"
                 if i < 3: html += "<td width='10' align='center'><span style='color:#808080'>|</span></td>"
             html += "</tr></table>"
             set_total_item(col, html)
        col += 1

    if show_avg_time:
        if totals["rev"] > 0:
             avg_sec = (totals["time"] * 3600) / totals["rev"]
             prev_avg = (totals["prev_time"] * 3600) / totals["prev_rev"] if totals["prev_rev"] > 0 else 0
             trend = get_trend_html_local(avg_sec, prev_avg, bigger_is_better=False)
             set_total_item(col, f"{avg_sec:.{stats_precision()}f}s{trend}", sort_value=avg_sec)
        else:
             set_total_item(col, "N/A", sort_value=-1)
        col += 1

    if show_longest_streak:
        l_s = totals.get('streak_longest', None)
        if isinstance(l_s, (int, float)):
            set_total_item(col, days_text_local(l_s), sort_value=l_s)
        else:
            set_total_item(col, "-", sort_value=-1)
        col += 1
    if show_streak:
        c_s = totals.get('streak_current', None)
        if isinstance(c_s, (int, float)):
            txt = days_text_local(c_s)
            it = set_total_item(col, txt, sort_value=c_s)
            if c_s >= 365: it.setForeground(QColor("#FFD700"))
            elif c_s >= 30: it.setForeground(QColor("#52c41a"))
        else:
            set_total_item(col, "-", sort_value=-1)
        col += 1
    if show_active_days:
        set_total_item(col, fmt_num_local(totals.get("active_days", 0)), sort_value=totals.get("active_days", 0))
        col += 1
    if show_forecast:
        t_rem = totals["remaining"]
        days_left = forecast_days(totals.get("limit", 0), totals["max_days"], t_rem)
        if days_left is None:
            ft = "-"
            tooltip = f"New cards off | New cards left: {t_rem}"
        else:
            ft = days_text_local(days_left)
            tooltip = f"Slowest deck | New cards left: {t_rem}"
        set_total_item(col, ft, tooltip, sort_value=-1 if days_left is None else days_left)
        col += 1

        col += 1

    if show_buttons_dist:
        buttons_col = None
        for c in range(table.columnCount()):
            h = table.horizontalHeaderItem(c)
            if h and h.text() == "Buttons":
                buttons_col = c
                break
        if buttons_col is not None:
            prev_w = table.columnWidth(buttons_col)
            if not show_buttons_visual:
                # Cells + 3 separators + margins.
                wanted = int(sum(cols_widths) + 30 + 22)
                applied_w = max(170, wanted)
                table.setColumnWidth(buttons_col, applied_w)
            else:
                applied_w = max(140, prev_w)
                table.setColumnWidth(buttons_col, applied_w)

    table.setVerticalHeaderLabels(["" for _ in range(table.rowCount())])
    table.setUpdatesEnabled(updates_were_enabled)
    table.setSortingEnabled(sorting_was_enabled)
    table.viewport().update()

