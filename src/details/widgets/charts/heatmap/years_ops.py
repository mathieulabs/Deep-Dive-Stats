# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
""""Years" view: every year with reviews, one year grid per row, the newest on top.

Past the "years before folding" setting (DEFAULT_FOLD), the older ones are folded under a
"+ N older years" row that unfolds them (and folds them back), with the mode transition's
animation. In a card of fixed height (Deep Dive: years_fit_height), the cells shrink to fit
the card, down to MIN_FIT_CELL; past that the wheel scrolls the years inside the card.
The button next to YRS takes out the space between the years (years_no_gap).

Each row is the grid of the year view (53 weeks x 7 days, same cells, colors and
settings), moved down by one row per year. One color scale for all the years, so they
compare at a glance. The functions here give where every day is drawn; the drawing,
transitions, hover and clicks of the widget use them for this view.
"""
from datetime import datetime, timedelta

from aqt.qt import QRectF

from .legend import format_threshold, legend_height
from .metrics import component_value, components, entry_counts

FIRST_YEAR = 2006  # Anki's first year: nothing older is looked at
DEFAULT_FOLD = 3  # years shown before the older ones are folded (setting; 0: never fold)
MIN_FIT_CELL = 6.0  # px: smallest cell when fitting a card's height; past that, scrolling
YEAR_GAP_STEPS = 1.0  # space between two years, in cell steps
WEEKS = 53
# Measures whose yearly figure is the sum of the days (the others are worked out from sums).
_SUMMED = {"reviews", "correct", "failed", "types"}


_REVIEW_YEARS_CACHE = {}  # id(collection): (time, first year, last year)
_REVIEW_YEARS_TTL = 300.0


def collection_review_years():
    """Calendar years the open collection's reviews span (first to last review; 0 if none).
    The query goes through Anki's backend (about 10 ms) and every heatmap build asked it
    twice: kept a few minutes per collection (the span only changes with a new year's first
    review or old reviews deleted)."""
    try:
        import time
        from aqt import mw

        col = mw.col
        key = id(col)
        now = time.monotonic()
        cached = _REVIEW_YEARS_CACHE.get(key)
        if cached is None or now - cached[0] > _REVIEW_YEARS_TTL:
            lo, hi = col.db.first("select min(id), max(id) from revlog") or (None, None)
            if not lo or not hi:
                cached = (now, 0, 0)
            else:
                cached = (now, datetime.fromtimestamp(lo / 1000.0).year, datetime.fromtimestamp(hi / 1000.0).year)
            _REVIEW_YEARS_CACHE.clear()
            _REVIEW_YEARS_CACHE[key] = cached
        _t, first, last = cached
        if not first:
            return 0
        return last - first + 1
    except Exception:
        return 0


def years_mode_available(min_years=2):
    """The all years view (YRS) is offered from two calendar years of reviews in the whole
    collection (not the deck shown, or the button would come and go between decks). With
    one year it is the year view without its arrows."""
    return collection_review_years() >= min_years


def is_years(widget):
    return getattr(widget, "view_mode", "") == "years"


def _years_info(widget):
    """(years shown, newest first; {year: total}) for the current data and metric."""
    data = widget.data or {}
    last = int(widget.end_date.year)
    key = (id(data), len(data), last, str(getattr(widget, "metric", "")))
    cached = widget.__dict__.get("_years_info_cache")
    if cached is not None and cached[0] == key:
        return cached[1]
    totals = {}
    first = last
    for d_str, entry in data.items():
        try:
            y = int(str(d_str)[:4])
        except (TypeError, ValueError):
            continue
        if y < FIRST_YEAR or y > last or not entry:
            continue
        past, _future = entry_counts(widget, entry)
        if past > 0:
            totals[y] = totals.get(y, 0) + past
            first = min(first, y)
    info = (list(range(last, first - 1, -1)), totals)
    widget.__dict__["_years_info_cache"] = (key, info)
    return info


def all_years(widget):
    return _years_info(widget)[0]


def fold_after(widget):
    """Years shown before folding the older ones (0: never fold)."""
    try:
        return max(0, int(getattr(widget, "years_fold", DEFAULT_FOLD)))
    except (TypeError, ValueError):
        return DEFAULT_FOLD


def can_fold(widget):
    # One year more than the setting is simply shown: a fold for a single year saves nothing.
    n = fold_after(widget)
    return n > 0 and len(all_years(widget)) > n + 1


def is_expanded(widget):
    return bool(getattr(widget, "_years_expanded", False))


def hidden_years(widget):
    """How many older years are folded (0 when all show)."""
    if not can_fold(widget) or is_expanded(widget):
        return 0
    return len(all_years(widget)) - fold_after(widget)


def years_shown(widget):
    years = all_years(widget)
    return years if hidden_years(widget) == 0 else years[:fold_after(widget)]


def scale_date_strings(widget):
    """Days the color scale is worked out from: those of every year, shown or folded, so
    unfolding the older years does not change the colors of the others."""
    years = all_years(widget)
    if not years:
        return []
    lo, hi = str(years[-1]), str(years[0])
    return [d for d in (widget.data or {}) if lo <= str(d)[:4] <= hi]


def toggle_text(widget):
    from .....i18n import tr

    n = hidden_years(widget)
    if n:
        return tr("+ {count} older years", count=n)
    return tr("Show fewer years")


def _year_sums(widget):
    """{year: {"reviews", "passed", "time_ms", "comps": [sum per measure of the metric]}}."""
    data = widget.data or {}
    metric = str(getattr(widget, "metric", "reviews"))
    key = (id(data), len(data), int(widget.end_date.year), metric)
    cached = widget.__dict__.get("_year_sums_cache")
    if cached is not None and cached[0] == key:
        return cached[1]
    comps = components(metric)
    out = {}
    for d_str, entry in data.items():
        if not isinstance(entry, dict):
            continue
        try:
            y = int(str(d_str)[:4])
        except (TypeError, ValueError):
            continue
        acc = out.get(y)
        if acc is None:
            acc = out[y] = {"reviews": 0.0, "passed": 0.0, "time_ms": 0.0, "comps": [0.0] * len(comps)}
        acc["reviews"] += float(entry.get("reviews", 0) or 0)
        acc["passed"] += float(entry.get("passed", 0) or 0)
        acc["time_ms"] += float(entry.get("time_ms", 0) or 0)
        for i, comp in enumerate(comps):
            if comp[0] in _SUMMED:
                acc["comps"][i] += component_value(comp, entry)
    widget.__dict__["_year_sums_cache"] = (key, out)
    return out


def _count_text(v):
    if v >= 100000:
        return f"{v / 1000.0:.0f}k"
    if v >= 1000:
        return f"{v / 1000.0:.1f}k"
    return str(int(round(v)))


def year_total_lines(widget, year):
    """The year's figure for each measure of the heatmap, in its unit: a sum for counts and
    time, the year's own rate for retention and average time (from the year's sums)."""
    from .....i18n import num

    acc = _year_sums(widget).get(year)
    if not acc:
        return []
    reviews, passed, time_ms = acc["reviews"], acc["passed"], acc["time_ms"]
    lines = []
    for i, comp in enumerate(components(getattr(widget, "metric", "reviews"))):
        key = comp[0]
        text = ""
        if key in _SUMMED:
            v = acc["comps"][i]
            text = _count_text(v) if v > 0 else ""
        elif key == "time":
            text = format_threshold("time", time_ms) if time_ms > 0 else ""
        elif key == "retention":
            text = num(f"{passed / reviews * 100.0:.1f}%") if reviews > 0 else ""
        elif key == "avg_time":
            text = format_threshold("avg_time", time_ms / reviews) if reviews > 0 else ""
        if text:
            lines.append(text)
    return lines


def fits_height(widget):
    """The card has a height of its own (Deep Dive): the years fit into it."""
    return bool(getattr(widget, "years_fit_height", False))


def _gap_factor(widget):
    """Space between two years, in cell sizes (a cell step is 1.25 cells, a spacing 0.25)."""
    return 0.25 if getattr(widget, "years_no_gap", False) else YEAR_GAP_STEPS * 1.25


def toggle_in_legend(widget):
    """The "+ N older years" text goes on the legend's line (left of it) when the legend is
    shown: one line less under the grid. Without a legend it has a line of its own."""
    return can_fold(widget) and legend_height(widget) > 0


def _toggle_height(widget):
    """Height of the "+ N older years" line of its own (0 when there is none)."""
    if not can_fold(widget) or toggle_in_legend(widget):
        return 0.0
    return 22.0 * max(0.8, float(widget.scale))


def _bottom_reserve(widget):
    return 10 * float(widget.scale) + legend_height(widget)


def _fit(widget, width, n, height=None):
    """(cell size, spacing, label space, top margin, drawing width) for n years."""
    s = float(widget.scale)
    label_space = 50.0 * s  # the year labels show even when the other labels are hidden
    margin_top = (22.0 * s) if not widget.hide_labels else (6.0 * s)
    avail = width - 4
    per_cell_w = WEEKS * 1.25 - 0.25
    if fits_height(widget) and height:
        target = 14.0 * s
        cell_w = (avail - label_space) / per_cell_w if avail > label_space else target
        fixed = margin_top + _toggle_height(widget) + _bottom_reserve(widget)
        per_cell_h = n * (7 * 1.25 - 0.25) + max(0, n - 1) * _gap_factor(widget)
        # Every year shown fits the card.
        cell_all = (height - fixed) / per_cell_h if per_cell_h > 0 else target
        # One year as big as the year view makes it in this card (the card's width, or its
        # height for 7 rows): the view fills the card like the other modes, and the wheel
        # scrolls to the other years when they do not all fit.
        cell_year = (height - margin_top - _bottom_reserve(widget)) / (7 * 1.25 - 0.25)
        cell = max(cell_all, cell_year)
        cell = min(cell_w, max(MIN_FIT_CELL, cell))
        cell = max(1.0, cell)
        spacing = cell * 0.25
        return cell, spacing, label_space, margin_top, label_space + WEEKS * (cell + spacing) - spacing
    # Same cell size however many years show: unfolding the older years adds rows under
    # the others (the page scrolls), it does not shrink the ones already on screen.
    cell = 14.0 * s
    spacing = cell * 0.25
    total_w = label_space + WEEKS * (cell + spacing) - spacing
    if total_w > avail and avail > 50:
        r = avail / total_w
        cell *= r
        spacing *= r
        label_space *= r
        margin_top *= r
        total_w = avail
    return cell, spacing, label_space, margin_top, total_w


def _grid_height(widget, n, cell):
    step, spacing = cell * 1.25, cell * 0.25
    return n * (7 * step - spacing) + max(0, n - 1) * _gap_factor(widget) * cell


def content_height(widget, width):
    """Height the view needs at this width (grid, fold row, bottom padding and legend)."""
    n = max(1, len(years_shown(widget)))
    cell, _spacing, _label, margin_top, _w = _fit(widget, width, n)
    return int(margin_top + _grid_height(widget, n, cell) + _toggle_height(widget) + _bottom_reserve(widget))


def year_grid_start(widget, year):
    start = datetime(year, 1, 1)
    wd = start.weekday()
    dow = wd if widget.monday_first else (wd + 1) % 7
    return start - timedelta(days=dow)


_BAR_ROOM = 10.0  # right edge kept for the scroll bar (6 px from the edge, 4 px wide)


def layout(widget):
    """dict: cell, spacing, step, start_x, start_y, label_space, bottom, blocks, toggle,
    viewport_bottom (cells under it are hidden), scroll, max_scroll.
    blocks: [(year, grid start date, top y of its row)], newest first."""
    years = years_shown(widget)
    key = (
        widget.width(), widget.height(), getattr(widget, "_height_anim", None), round(float(widget.scale), 4), bool(widget.hide_labels),
        tuple(years), legend_height(widget), bool(widget.grid_mode), bool(widget.monday_first),
        can_fold(widget), hidden_years(widget), bool(getattr(widget, "years_no_gap", False)),
        fits_height(widget), round(float(getattr(widget, "_years_scroll", 0.0)), 1),
        getattr(widget, "_hold_min_height", None) is not None,
    )
    cached = widget.__dict__.get("_years_layout_cache")
    if cached is not None and cached[0] == key:
        return cached[1]
    n = max(1, len(years))
    from .settings import layout_height

    H = float(layout_height(widget))
    toggle_h = _toggle_height(widget)
    viewport_bottom = H - _bottom_reserve(widget) if fits_height(widget) else H
    room = 0.0
    for _attempt in range(2):
        cell, spacing, label_space, margin_top, total_w = _fit(
            widget, widget.width() - room, n, H if fits_height(widget) else None)
        content_h = margin_top + _grid_height(widget, n, cell) + toggle_h
        max_scroll = max(0.0, content_h - viewport_bottom) if fits_height(widget) else 0.0
        if max_scroll <= 0 or room:
            break
        # The years scroll: keep the right edge free for the bar (draw_scrollbar), so it
        # does not go over the last weeks.
        room = _BAR_ROOM
    step = cell + spacing
    gap = _gap_factor(widget) * cell
    start_x = max(0.0, (widget.width() - room - total_w) / 2.0) + label_space
    scroll = min(max_scroll, max(0.0, float(getattr(widget, "_years_scroll", 0.0))))
    widget._years_scroll = scroll
    start_y = margin_top - scroll
    holding = getattr(widget, "_hold_min_height", None) is not None
    if widget.grid_mode and not holding and content_h + _bottom_reserve(widget) < H:
        start_y += (H - content_h - _bottom_reserve(widget)) / 2.0
    blocks = []
    y = start_y
    for yr in years:
        blocks.append((yr, year_grid_start(widget, yr), y))
        y += 7 * step - spacing + gap
    grid_bottom = (blocks[-1][2] + 7 * step - spacing) if blocks else start_y
    toggle = None
    if toggle_h > 0:
        # Under the last row, from the year labels' left edge.
        toggle = QRectF(start_x - label_space, grid_bottom + 4.0 * float(widget.scale),
                        label_space + WEEKS * step - spacing, toggle_h - 4.0 * float(widget.scale))
    elif toggle_in_legend(widget):
        # On the legend's line (where legend.paint_legend puts it), left of the legend.
        lh = float(legend_height(widget))
        legend_top = min(H - lh, min(grid_bottom, viewport_bottom) + 10 * float(widget.scale))
        toggle = QRectF(start_x - label_space, legend_top, 200.0 * max(0.8, float(widget.scale)), lh)
    lay = {
        "cell": cell, "spacing": spacing, "step": step, "start_x": start_x, "start_y": start_y,
        "label_space": label_space, "blocks": blocks, "toggle": toggle,
        "bottom": min(grid_bottom + toggle_h, viewport_bottom),
        "viewport_bottom": viewport_bottom, "scroll": scroll, "max_scroll": max_scroll,
    }
    widget.__dict__["_years_layout_cache"] = (key, lay)
    return lay


def row_tops(widget):
    """{year: top of its row} as laid out now."""
    return {yr: y0 for yr, _gs, y0 in layout(widget)["blocks"]}


def scroll_by(widget, wheel_delta):
    """Scroll the years for a wheel turn. False when there is nothing to scroll that way
    (the card shows everything, or the end is reached): the page scrolls instead."""
    lay = layout(widget)
    if lay["max_scroll"] <= 0 or not wheel_delta:
        return False
    old = lay["scroll"]
    new = min(lay["max_scroll"], max(0.0, old - (wheel_delta / 120.0) * lay["step"] * 3.0))
    if abs(new - old) < 0.5:
        return False
    widget._years_scroll = new
    return True


def draw_scrollbar(widget, painter):
    """A thin bar on the right edge while the years scroll (like an overlay scrollbar)."""
    lay = layout(widget)
    if lay["max_scroll"] <= 0:
        return
    from aqt.qt import QColor, Qt

    top, bottom = 2.0, lay["viewport_bottom"] - 2.0
    track = max(10.0, bottom - top)
    visible = track / (track + lay["max_scroll"])
    h = max(18.0, track * visible)
    y = top + (track - h) * (lay["scroll"] / lay["max_scroll"])
    try:
        from ...chart_utils import get_theme_colors

        col = QColor(get_theme_colors(widget)["text"])
    except Exception:
        col = QColor(widget.palette().color(widget.foregroundRole()))
    col.setAlpha(90)
    painter.save()
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(col)
    painter.drawRoundedRect(QRectF(widget.width() - 6.0, y, 4.0, h), 2.0, 2.0)
    painter.restore()


def top_geometry(widget):
    """(cell, spacing, start_x, start_y, label_space) of the top row, like the year view's
    geometry: what the legend, the nav alignment and the caches read."""
    lay = layout(widget)
    return (lay["cell"], lay["spacing"], lay["start_x"], lay["start_y"], lay["label_space"])


def geometry_token(widget):
    """Key of the cached pictures: the layout, and the year totals the labels show."""
    lay = layout(widget)
    totals = tuple(tuple(year_total_lines(widget, yr)) for yr, _gs, _y in lay["blocks"])
    return (tuple(round(float(v), 2) for v in top_geometry(widget))
            + (len(lay["blocks"]), hidden_years(widget), can_fold(widget), round(lay["scroll"], 1))
            # Each row's top: the space between years moves them with the top row unchanged,
            # and a cached grid kept from the other spacing showed a row of empty cells.
            + tuple(round(float(y0), 1) for _yr, _gs, y0 in lay["blocks"]) + totals)


def iter_cells(widget):
    """(date, QRectF) of every day shown."""
    lay = layout(widget)
    cell, step, start_x = lay["cell"], lay["step"], lay["start_x"]
    for yr, gs, y0 in lay["blocks"]:
        for week in range(WEEKS):
            x = start_x + week * step
            for day in range(7):
                d = gs + timedelta(weeks=week, days=day)
                if d.year != yr:
                    continue
                yield d, QRectF(x, y0 + day * step, cell, cell)


def toggle_hit(widget, pos):
    """True when pos (a QPointF) is on the "+ N older years" row."""
    if pos is None:
        return False
    lay = layout(widget)
    rect = lay.get("toggle")
    if rect is None or (pos.y() > lay["viewport_bottom"] and not toggle_in_legend(widget)):
        return False
    x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
    # Only the text's half: the rest of the row stays plain background.
    return x <= pos.x() <= x + min(w, 220.0 * float(widget.scale)) and y <= pos.y() <= y + h


def hit_test(widget, mx, my, strict=False):
    """(date, rect) of the day under (mx, my), or None. strict: the gaps between cells miss."""
    lay = layout(widget)
    cell, step, start_x = lay["cell"], lay["step"], lay["start_x"]
    if mx < start_x or my < 0 or my > lay["viewport_bottom"]:
        return None
    week = int((mx - start_x) / step)
    if week < 0 or week >= WEEKS:
        return None
    if strict and (mx - start_x) % step > cell:
        return None
    for yr, gs, y0 in lay["blocks"]:
        if y0 <= my < y0 + 7 * step:
            day = int((my - y0) / step)
            if day > 6 or (strict and (my - y0) % step > cell):
                return None
            d = gs + timedelta(weeks=week, days=day)
            if d.year != yr:
                return None
            return d, QRectF(start_x + week * step, y0 + day * step, cell, cell)
    return None


def draw_labels(widget, painter, month_short, motion=None):
    """Year (and its total) left of each row; the months above the top row.

    motion: (old top of each year's row, eased progress) while the years move (fold, gap):
    each label slides from its old row to its new one, and the years that come or go fade.
    Fading two still pictures instead blurred the text through the whole move."""
    from aqt.qt import QFont, Qt

    lay = layout(widget)
    cell, step, start_x, label_space = lay["cell"], lay["step"], lay["start_x"], lay["label_space"]
    s = float(widget.scale)
    base = painter.font()
    if not widget.hide_labels and lay["blocks"]:
        f = QFont(base)
        f.setPointSize(max(6, min(8, int(cell * 0.7))))
        painter.setFont(f)
        yr, gs, y0 = lay["blocks"][0]
        seen = set()
        for week in range(WEEKS):
            for day in range(7):
                d = gs + timedelta(weeks=week, days=day)
                if d.year != yr or d.month in seen:
                    continue
                seen.add(d.month)
                painter.drawText(
                    QRectF(start_x + week * step, y0 - 16 * s, 50 * s, 15 * s),
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom,
                    month_short(d.month),
                )
    year_font = QFont(base)
    year_font.setPointSizeF(max(7.0, min(10.0, cell * 0.72)))
    year_font.setBold(True)
    total_font = QFont(base)
    total_font.setPointSizeF(max(7.5, min(9.5, cell * 0.7)))
    total_font.setBold(True)
    x = start_x - label_space + 2 * s
    w = label_space - 6 * s
    rows = [(yr, y0, 1.0) for yr, _gs, y0 in lay["blocks"]]
    if motion is not None:
        old_tops, tt = motion
        rows = []
        for yr, _gs, y0 in lay["blocks"]:
            if yr in old_tops:
                rows.append((yr, old_tops[yr] + (y0 - old_tops[yr]) * tt, 1.0))
            else:
                rows.append((yr, y0, tt))
        shown = {yr for yr, _gs, _y in lay["blocks"]}
        rows += [(yr, y, 1.0 - tt) for yr, y in old_tops.items() if yr not in shown]
    for yr, y0, alpha in rows:
        if alpha <= 0.01:
            continue
        painter.save()
        painter.setOpacity(painter.opacity() * alpha)
        painter.setFont(year_font)
        painter.drawText(QRectF(x, y0, w, 2.0 * step), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, str(yr))
        lines = year_total_lines(widget, yr)
        if lines:
            # One line per measure, under the year, as many as the row's height holds.
            painter.setFont(total_font)
            painter.save()
            painter.setOpacity(painter.opacity() * 0.8)
            line_h = max(1.4 * step, painter.fontMetrics().height() + 1.0)
            row_bottom = y0 + 7 * step - lay["spacing"]
            ty = y0 + 1.7 * step
            for text in lines:
                if ty + line_h * 0.8 > row_bottom:
                    break
                painter.drawText(QRectF(x, ty, w, line_h), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, text)
                ty += line_h
            painter.restore()
        painter.restore()
    toggle = lay.get("toggle")
    if toggle is not None and not toggle_in_legend(widget):
        f = QFont(base)
        f.setPointSizeF(max(7.0, 8.5 * min(1.0, max(0.85, s))))
        f.setBold(True)
        painter.setFont(f)
        painter.save()
        painter.setOpacity(painter.opacity() * 0.75)
        painter.drawText(toggle, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, toggle_text(widget))
        painter.restore()
    painter.setFont(base)


def draw_toggle_in_legend(widget, painter, top, h):
    """The "+ N older years" text on the legend's line, at the legend's (moving) top."""
    if not toggle_in_legend(widget):
        return
    from aqt.qt import QFont, Qt

    rect = layout(widget).get("toggle")
    if rect is None:
        return
    s = float(widget.scale)
    painter.save()
    f = QFont(painter.font())
    f.setPointSizeF(max(7.0, 8.5 * min(1.0, max(0.85, s))))
    f.setBold(True)
    painter.setFont(f)
    try:
        from ...chart_utils import get_theme_colors

        painter.setPen(get_theme_colors(widget)["text"])
    except Exception:
        pass
    painter.setOpacity(painter.opacity() * 0.75)
    painter.drawText(QRectF(rect.x(), top, rect.width(), h), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                     toggle_text(widget))
    painter.restore()
