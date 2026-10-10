# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QColor, QFontMetrics, Qt

from .. import Config, Period, format_hours
from ...logic.logger import log_swallowed
from ...widgets import SegmentedBarWidget
from ...widgets.chart_utils.formatting import fmt_num, stats_precision
from ..table import add_table_item
from ..table.retention_visual import retention_bar, retention_visual_on
from ....qss import set_qss


def _days_text(n):
    return f"{fmt_num(n)} day" if n == 1 else f"{fmt_num(n)} days"


def fill_deck_table(dialog, table, stats_list, deck_id, tab_index, do_resize=True, deleted_tab_did="__deleted_cards__"):
    """Populate a deck-view table with already-fetched range stats."""
    try:
        from ...logic.tabs import get_tabs_config
        from ..table import get_trend_html as get_trend_table

        tabs_config = [t for t in get_tabs_config(dialog.addon_config) if t.get("enabled", True)]
        first_tab = tabs_config[0] if tabs_config else {}

        use_decimal = first_tab.get("use_decimal", True)
        hrs_unit = first_tab.get("hrs_unit", "hrs")
        min_unit = first_tab.get("min_unit", "min")
        show_time = first_tab.get("show_time", True)
        show_reviews = first_tab.get("show_reviews", True)
        show_retention = first_tab.get("show_retention", True)
        show_retention_young = first_tab.get("show_retention_young", True)
        show_retention_mature = first_tab.get("show_retention_mature", True)
        show_avg_time = first_tab.get("show_avg_time", True)
        show_counts = first_tab.get("show_counts", True)
        show_buttons_dist = first_tab.get("show_buttons_dist", False)
        show_active_days = first_tab.get("show_active_days", True)
        show_longest_streak = first_tab.get("show_longest_streak", True)
        show_streak = first_tab.get("show_streak", False)
        show_forecast = first_tab.get("show_forecast", True)

        show_trends = dialog.trend_toggle.isChecked() if hasattr(dialog, "trend_toggle") else False
        deck_colors = dialog.addon_config.config.get(Config.DECK_COLORS, {})
        fm = QFontMetrics(table.font())

        table.setRowCount(len(stats_list))

        try:
            from .. import Config as _Cfg, get_chart_color as _gcc

            _dv_color_good = _gcc(_Cfg.COLOR_GOOD)
            _dv_color_bad = _gcc(_Cfg.COLOR_AGAIN)
        except Exception:
            _dv_color_good = "#4CAF50"
            _dv_color_bad = "#F44336"

        def get_trend_html(curr, prev, bigger_is_better=True, points=False):
            return get_trend_table(curr, prev, show_trends, bigger_is_better, color_good=_dv_color_good, color_bad=_dv_color_bad, points=points)

        def add_data_item(row, col, text, color=None, tooltip="", bold=False, sort_value=None):
            return add_table_item(table, row, col, text, color, tooltip, bold, sort_value)

        is_collection = deck_id == "collection"
        is_deleted_tab = deck_id == deleted_tab_did
        results = []
        time_trend_nonempty = 0
        buttons_row_required_max = 0

        for row, data in enumerate(stats_list):
            res = data["res"]
            prev_res = data["prev_res"]
            range_type = data["range_type"]
            title = data["title"]
            limit = data.get("limit", 20)
            remaining_new = data.get("remaining_new", 0)
            is_total_row = range_type == Period.TOTAL

            row_color = None
            if is_total_row:
                if "total" in deck_colors:
                    c = QColor(deck_colors["total"])
                    if c.isValid():
                        c.setAlpha(50)
                        row_color = c
            elif not is_collection:
                key = "deleted" if is_deleted_tab else (str(deck_id) if deck_id is not None else "deleted")
                if key in deck_colors:
                    c = QColor(deck_colors[key])
                    if c.isValid():
                        c.setAlpha(50)
                        row_color = c

            if res is None:
                res = [0] * 12
            time_ms = res[1] or 0
            reviews = res[2] or 0
            passed = res[3] or 0
            pass_young = res[4] or 0
            rev_young = res[5] or 0
            pass_mat = res[6] or 0
            rev_mat = res[7] or 0
            again = res[8] or 0
            hard = res[9] or 0
            good = res[10] or 0
            easy = res[11] or 0
            active_days = data.get("active_days", 0)

            if prev_res is None:
                prev_res = [0] * 12
            prev_time_ms = prev_res[1] or 0
            prev_reviews = prev_res[2] or 0
            prev_passed = prev_res[3] or 0
            prev_pass_young = prev_res[4] or 0
            prev_rev_young = prev_res[5] or 0
            prev_pass_mat = prev_res[6] or 0
            prev_rev_mat = prev_res[7] or 0

            col = 0
            if not is_total_row and reviews == 0 and time_ms == 0:
                table.setRowHidden(row, True)
            else:
                table.setRowHidden(row, False)

            it = add_data_item(row, col, title, row_color, bold=is_total_row)
            it.setData(Qt.ItemDataRole.UserRole, range_type)
            col += 1

            if show_time:
                time_trend = get_trend_html(time_ms / 3600000, prev_time_ms / 3600000)
                if time_trend:
                    time_trend_nonempty += 1
                time_text = f"{format_hours(time_ms/3600000, use_decimal=use_decimal, hrs_text=hrs_unit, min_text=min_unit)}{time_trend}"
                it = add_data_item(row, col, time_text, row_color, bold=is_total_row, sort_value=time_ms)
                it.setData(Qt.ItemDataRole.UserRole, range_type)
                col += 1

            if show_reviews:
                rev_trend = get_trend_html(reviews, prev_reviews)
                rev_text = f"{fmt_num(reviews)}{rev_trend}"
                add_data_item(row, col, rev_text, row_color, bold=is_total_row, sort_value=reviews)
                col += 1

            if show_retention and retention_visual_on("all") and reviews > 0:
                add_data_item(row, col, "", row_color, sort_value=passed / reviews * 100)
                table.setCellWidget(row, col, retention_bar(passed, reviews, background=row_color.name() if row_color else None))
                col += 1
            elif show_retention:
                if reviews > 0:
                    ret = (passed / reviews * 100)
                    prev_ret = (prev_passed / prev_reviews * 100) if prev_reviews > 0 else 0
                    ret_trend = get_trend_html(ret, prev_ret, points=True)
                    failed = reviews - passed
                    text_fmt = "0%" if ret == 0 else f"{ret:.{stats_precision()}f}%"
                    if show_counts:
                        text = f"{'<b>' if is_total_row else ''}{text_fmt}{'</b>' if is_total_row else ''} (<span style='color:{_dv_color_good}'>{fmt_num(passed)}</span>/<span style='color:{_dv_color_bad}'>{fmt_num(failed)}</span>){ret_trend}"
                    else:
                        text = f"{text_fmt}{ret_trend}"
                    add_data_item(row, col, text, row_color, tooltip=f"Pass: {fmt_num(passed)} / Fail: {fmt_num(failed)}", bold=is_total_row, sort_value=ret)
                else:
                    add_data_item(row, col, "N/A", row_color)
                col += 1

            if show_retention_young and retention_visual_on("young") and rev_young > 0:
                add_data_item(row, col, "", row_color, sort_value=pass_young / rev_young * 100)
                table.setCellWidget(row, col, retention_bar(pass_young, rev_young, background=row_color.name() if row_color else None))
                col += 1
            elif show_retention_young:
                ret = (pass_young / rev_young * 100) if rev_young > 0 else 0
                prev_ret = (prev_pass_young / prev_rev_young * 100) if prev_rev_young > 0 else 0
                ret_trend = get_trend_html(ret, prev_ret, points=True)
                text_ret = "0%" if ret == 0 else f"{ret:.{stats_precision()}f}%"
                if rev_young > 0:
                    if show_counts:
                        failed = rev_young - pass_young
                        text = f"{'<b>' if is_total_row else ''}{text_ret}{'</b>' if is_total_row else ''} (<span style='color:{_dv_color_good}'>{fmt_num(pass_young)}</span>/<span style='color:{_dv_color_bad}'>{fmt_num(failed)}</span>){ret_trend}"
                    else:
                        text = f"{text_ret}{ret_trend}"
                else:
                    text = "N/A"
                add_data_item(row, col, text, row_color, tooltip=f"Pass: {fmt_num(pass_young)} / Fail: {fmt_num(rev_young - pass_young)}" if rev_young > 0 else "", bold=is_total_row, sort_value=ret)
                col += 1

            if show_retention_mature and retention_visual_on("mature") and rev_mat > 0:
                add_data_item(row, col, "", row_color, sort_value=pass_mat / rev_mat * 100)
                table.setCellWidget(row, col, retention_bar(pass_mat, rev_mat, background=row_color.name() if row_color else None))
                col += 1
            elif show_retention_mature:
                ret = (pass_mat / rev_mat * 100) if rev_mat > 0 else 0
                prev_ret = (prev_pass_mat / prev_rev_mat * 100) if prev_rev_mat > 0 else 0
                ret_trend = get_trend_html(ret, prev_ret, points=True)
                text_ret = "0%" if ret == 0 else f"{ret:.{stats_precision()}f}%"
                if rev_mat > 0:
                    if show_counts:
                        failed = rev_mat - pass_mat
                        text = f"{'<b>' if is_total_row else ''}{text_ret}{'</b>' if is_total_row else ''} (<span style='color:{_dv_color_good}'>{fmt_num(pass_mat)}</span>/<span style='color:{_dv_color_bad}'>{fmt_num(failed)}</span>){ret_trend}"
                    else:
                        text = f"{text_ret}{ret_trend}"
                else:
                    text = "N/A"
                add_data_item(row, col, text, row_color, tooltip=f"Pass: {fmt_num(pass_mat)} / Fail: {fmt_num(rev_mat - pass_mat)}" if rev_mat > 0 else "", bold=is_total_row, sort_value=ret)
                col += 1

            if show_buttons_dist:
                show_buttons_visual = dialog.addon_config.config.get(Config.SHOW_BUTTONS_DIST_VISUAL, True)
                counts = [again, hard, good, easy]
                if show_buttons_visual:
                    add_data_item(row, col, "", row_color)
                    bar = SegmentedBarWidget(counts, animate=False)
                    if row_color:
                        set_qss(bar, f"background-color: {row_color.name()};")
                    table.setCellWidget(row, col, bar)
                else:
                    cols_c = ["#F44336", "#FF9800", "#4CAF50", "#2196F3"]
                    html = "<table style='border-collapse: collapse;'><tr>"
                    row_required_w = 22
                    for i, c in enumerate(counts):
                        v = (c if show_counts else (c / reviews * 100)) if reviews > 0 else 0
                        display_text = fmt_num(v) if show_counts else f"{v:.{stats_precision()}f}%"
                        basis_text = display_text if show_counts else "100.00%"
                        ts = f"{'<b>' if is_total_row else ''}{display_text}{'</b>' if is_total_row else ''}"
                        cell_w = max(44, fm.horizontalAdvance(basis_text) + 24)
                        row_required_w += cell_w
                        html += f"<td align='center' width='{cell_w}'><span style='color:{cols_c[i]}'>{ts}</span></td>"
                        if i < 3:
                            row_required_w += 10
                            html += "<td width='10' align='center'><span style='color:#808080'>|</span></td>"
                    html += "</tr></table>"
                    if row_required_w > buttons_row_required_max:
                        buttons_row_required_max = row_required_w
                    add_data_item(row, col, html, row_color)
                col += 1

            if show_avg_time:
                avg = (time_ms / 1000 / reviews) if reviews > 0 else 0
                prev_avg = (prev_time_ms / 1000 / prev_reviews) if prev_reviews > 0 else 0
                avg_trend = get_trend_html(avg, prev_avg, bigger_is_better=False)
                text = f"{fmt_num(avg, stats_precision())}s{avg_trend}" if reviews > 0 else "N/A"
                add_data_item(row, col, text, row_color, bold=is_total_row, sort_value=avg)
                col += 1

            if show_longest_streak or show_streak:
                cur_s = data.get("streak_current", 0)
                long_s = data.get("streak_longest", 0)
                if show_longest_streak:
                    if is_total_row:
                        add_data_item(row, col, _days_text(long_s), row_color, bold=True, sort_value=long_s)
                    else:
                        add_data_item(row, col, "-", row_color, sort_value=0)
                    col += 1
                if show_streak:
                    if is_total_row:
                        add_data_item(row, col, _days_text(cur_s), row_color, bold=True, sort_value=cur_s)
                    else:
                        add_data_item(row, col, "-", row_color, sort_value=0)
                    col += 1

            if show_active_days:
                add_data_item(row, col, fmt_num(active_days), row_color, bold=is_total_row, sort_value=active_days)
                col += 1

            if show_forecast:
                if is_total_row:
                    m_days = data.get("max_days")
                    if m_days is not None:
                        days_left = int(m_days)
                        f_text = _days_text(days_left)
                        tooltip = f"Slowest component bottleneck | Rem: {remaining_new}"
                    elif limit > 0:
                        remaining_new_val = remaining_new if remaining_new is not None else 0
                        days_left = int(remaining_new_val / limit)
                        f_text = _days_text(days_left)
                        tooltip = f"Theory: {limit} new/day | Rem: {remaining_new_val}"
                    else:
                        f_text = "-"
                        tooltip = f"New cards disabled | Rem: {remaining_new}"
                    add_data_item(row, col, f_text, row_color, tooltip=tooltip, bold=True)
                else:
                    add_data_item(row, col, "-", row_color, sort_value=0)
                col += 1

            results.append(
                {
                    "range_type": range_type,
                    "title": title,
                    "reviews": reviews,
                    "passed": passed,
                    "pass_young": pass_young,
                    "rev_young": rev_young,
                    "pass_mat": pass_mat,
                    "rev_mat": rev_mat,
                    "again": again,
                    "hard": hard,
                    "good": good,
                    "easy": easy,
                    "time_ms": time_ms,
                    "active_days": active_days,
                    "is_total_row": is_total_row,
                    "row_color": row_color,
                    "did": None if (is_collection or is_deleted_tab) else deck_id,
                    "streak_current": data.get("streak_current", 0),
                    "streak_longest": data.get("streak_longest", 0),
                }
            )

        table.setVerticalHeaderLabels(["" for _ in range(table.rowCount())])

        dash_stats = {
            "total_time": "0h",
            "reviews": "0",
            "ret_all": "N/A",
            "ret_young": "N/A",
            "ret_mat": "N/A",
            "streak": "0",
            "active_days": "0",
            "longest_streak": "N/A",
            "ret_true": "N/A",
            "rev_young": "0",
            "rev_mature": "0",
            "again": "0",
            "results": results,
            "did": None if (is_collection or is_deleted_tab) else deck_id,
            "is_collection": is_collection,
        }
        total_data = next((r for r in results if r["range_type"] == Period.TOTAL), None)
        if total_data:
            dash_stats["total_time"] = format_hours(total_data["time_ms"] / 3600000, use_decimal=use_decimal, hrs_text=hrs_unit, min_text=min_unit)
            dash_stats["reviews"] = fmt_num(total_data["reviews"])
            dash_stats["ret_all"] = f"{total_data['passed'] / total_data['reviews'] * 100:.{stats_precision()}f}%" if total_data["reviews"] > 0 else "N/A"
            dash_stats["ret_young"] = f"{total_data['pass_young'] / total_data['rev_young'] * 100:.{stats_precision()}f}%" if total_data["rev_young"] > 0 else "N/A"
            dash_stats["ret_mat"] = f"{total_data['pass_mat'] / total_data['rev_mat'] * 100:.{stats_precision()}f}%" if total_data["rev_mat"] > 0 else "N/A"
            dash_stats["active_days"] = fmt_num(total_data["active_days"])
            dash_stats["streak"] = fmt_num(total_data.get("streak_current", 0))
            dash_stats["longest_streak"] = fmt_num(total_data.get("streak_longest", 0))
            true_rev = total_data["rev_young"] + total_data["rev_mat"]
            dash_stats["ret_true"] = f"{(total_data['pass_young'] + total_data['pass_mat']) / true_rev * 100:.{stats_precision()}f}%" if true_rev > 0 else "N/A"
            dash_stats["rev_young"] = fmt_num(total_data["rev_young"])
            dash_stats["rev_mature"] = fmt_num(total_data["rev_mat"])
            dash_stats["again"] = fmt_num(total_data["again"])

        dialog.tab_stats[tab_index] = dash_stats
        getattr(dialog, "_refresh_drawer_bar", lambda: None)()
        if show_buttons_dist:
            show_buttons_visual = bool(dialog.addon_config.config.get(Config.SHOW_BUTTONS_DIST_VISUAL, True))
            for c in range(table.columnCount()):
                h = table.horizontalHeaderItem(c)
                if h and h.text() == "Buttons":
                    prev_w = table.columnWidth(c)
                    if not show_buttons_visual:
                        table.resizeColumnToContents(c)
                        size_hint_w = table.sizeHintForColumn(c)
                        applied_w = max(170, size_hint_w + 12)
                        table.setColumnWidth(c, applied_w)
                    else:
                        table.setColumnWidth(c, max(140, prev_w))
                    break

        target_span = getattr(dialog, "target_time_span", None)
        if target_span is not None:
            for r in range(table.rowCount()):
                item = table.item(r, 0)
                if item and str(item.data(Qt.ItemDataRole.UserRole)) == str(target_span):
                    table.selectRow(r)
                    break

        if do_resize:
            from ..details_dialog import auto_resize_window

            if auto_resize_window(dialog, table, resize_window=False):
                table._has_been_resized = True
        elif stats_list:
            table._has_been_resized = False

    except Exception:

        log_swallowed()


