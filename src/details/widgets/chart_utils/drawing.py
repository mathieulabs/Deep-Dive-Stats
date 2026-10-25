# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
import time
from aqt.qt import QPainter, QPainterPath, QPointF, QRect, QRectF, Qt, QPen, QColor, QFontMetrics
from .theme import get_theme_colors, is_night_mode
from .geometry import ChartGeometry
from .formatting import fmt_num
from ...logic.logger import log_swallowed


# [last read time, line opacity %, bar gradient %, show grid]
_STYLE_CACHE = [0.0, 80, 43, True]


def chart_style(widget=None):
    """Return (line_opacity_pct, bar_gradient_pct): the chart's own setting if it
    has one, else the global one.

    Re-read at most once a second, so painting stays cheap and settings changes
    show up quickly.
    """
    import time

    now = time.monotonic()
    if now - _STYLE_CACHE[0] > 1.0:
        _STYLE_CACHE[0] = now
        try:
            from .theme import _load_live_addon_config

            conf = _load_live_addon_config() or {}
            _STYLE_CACHE[1] = max(0, min(200, int(conf.get("Chart_Line_Opacity", 80))))
            _STYLE_CACHE[2] = max(0, min(100, int(conf.get("Chart_Bar_Gradient", 43))))
            _STYLE_CACHE[3] = bool(conf.get("Chart_Show_Grid", True))
        except Exception:
            log_swallowed()
    line, grad = _STYLE_CACHE[1], _STYLE_CACHE[2]
    own_line = getattr(widget, "line_opacity_pct", None)
    own_grad = getattr(widget, "bar_gradient_pct", None)
    if own_line is not None:
        line = max(0, min(200, int(own_line)))
    if own_grad is not None:
        grad = max(0, min(100, int(own_grad)))
    return line, grad


def _own_flag(widget, attr, fallback):
    """Per-chart override (set from the chart's own settings) or the global value."""
    own = getattr(widget, attr, None) if widget is not None else None
    return fallback if own is None else bool(own)


def chart_axes_style(widget=None):
    """(show_grid,): the chart's own "Grid Lines" setting when it has one,
    otherwise Settings > General > Chart Style. A tuple so it can sit in
    the charts' scaffold cache keys."""
    chart_style()  # refreshes the shared cache
    return (_own_flag(widget, "show_grid_flag", _STYLE_CACHE[3]),)


def scale_line_alpha(alpha, widget=None) -> int:
    """Scale a line/area alpha by the "Total / Average lines" setting."""
    return max(0, min(255, int(round(float(alpha) * chart_style(widget)[0] / 100.0))))


def get_hover_marker_outline_color(widget, *, prefer_pinned_contrast=False):
    """Resolve a theme-aware hover marker outline color."""
    if prefer_pinned_contrast and widget is not None:
        try:
            if bool(widget.property("pinned_widget")):
                return QColor(Qt.GlobalColor.white if is_night_mode(widget) else Qt.GlobalColor.black)
        except Exception:
            log_swallowed()
    t_colors = get_theme_colors(widget)
    return QColor(t_colors.get("border", t_colors.get("text_primary", t_colors.get("text"))))


def get_hover_guide_pen(widget, width=1.0):
    """Return a theme-aware dashed pen for the vertical hover guide line."""
    t_colors = get_theme_colors(widget)
    is_dark = bool(t_colors.get("is_dark", False))
    line_col = QColor(t_colors.get("text_secondary", t_colors.get("text")))
    line_col.setAlpha(100 if is_dark else 85)
    return QPen(line_col, float(width), Qt.PenStyle.DashLine)

def axis_text_color(t_colors, factor=1.0, fade=1.0, widget=None):
    """Axis numbers and dates: the secondary text color, slightly faded, so
    the data stays the brightest thing in the chart."""
    # factor: how quiet this axis is; fade: animation alpha 0-1.
    is_dark = bool(t_colors.get("is_dark", False))
    fade = max(0.0, min(1.0, float(fade)))
    col = QColor(t_colors.get("text_secondary", t_colors.get("text")))
    col.setAlpha(max(0, min(255, int(round((175 if is_dark else 215) * factor * fade)))))
    return col


def _grid_pen(grid_col, baseline=False):
    """Solid hairline grid (reads cleaner than dots); the baseline a bit stronger."""
    col = QColor(grid_col)
    col.setAlpha(min(255, int(round(col.alpha() * (2.6 if baseline else 1.5)))))
    pen = QPen(col, 1)
    pen.setCosmetic(True)
    return pen


def draw_grid_and_axes(
    painter: QPainter,
    width,
    height,
    margin_left,
    margin_top,
    margin_right,
    margin_bottom,
    max_val,
    grid_lines=4,
    max_cumulative=None,
    value_formatter=None,
    cumulative_value_formatter=None,
    widget=None,
    min_val=0,
    draw_lines=True,
    draw_labels=True,
):
    t_colors = get_theme_colors(widget)
    text_col = axis_text_color(t_colors, widget=widget)
    grid_col = t_colors["grid"]
    show_grid = chart_axes_style(widget)[0]

    avail_h = height - margin_top - margin_bottom

    font = painter.font()
    font.setPointSize(9)
    painter.setFont(font)

    for i in range(grid_lines + 1):
        y_ratio = i / grid_lines
        y_pos = margin_top + (avail_h * (1 - y_ratio))

        if draw_lines and (i == 0 or show_grid):  # "Grid lines" off keeps only the baseline
            painter.setPen(_grid_pen(grid_col, baseline=(i == 0)))
            y_line = int(y_pos) + 0.5  # crisp 1px line
            painter.drawLine(QPointF(margin_left, y_line), QPointF(width - margin_right, y_line))

        if not draw_labels:
            continue
        val = min_val + (max_val - min_val) * y_ratio
        painter.setPen(text_col)
        if callable(value_formatter):
            label_text = str(value_formatter(val))
        else:
            label_text = fmt_num(int(val)) if val >= 10 else fmt_num(val)
        if i == 0 and val == 0: label_text = "0"

        label_rect = QRect(0, int(y_pos) - 10, int(margin_left - 8), 20)
        painter.drawText(label_rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, label_text)

    # Right Y-Axis labels (cumulative): draw once after grid/left-axis pass.
    if max_cumulative is not None:
        draw_right_axis_labels(
            painter,
            width,
            height,
            margin_right,
            margin_top,
            margin_bottom,
            max_cumulative,
            grid_lines,
            widget=widget,
            value_formatter=cumulative_value_formatter,
        )

def draw_right_axis_labels(
    painter: QPainter,
    width,
    height,
    margin_right,
    margin_top,
    margin_bottom,
    max_cumulative,
    grid_lines=4,
    suffix="",
    value_formatter=None,
    widget=None,
):
    """Draw only the right-axis labels (totals). Called last to make sure they are on top."""
    if max_cumulative is None: return

    t_colors = get_theme_colors(widget)
    # Secondary (cumulative) scale: one step quieter than the left axis.
    text_col = axis_text_color(t_colors, 0.8, widget=widget)
    avail_h = height - margin_top - margin_bottom

    font = painter.font()
    font.setPointSize(9)
    painter.setFont(font)

    for i in range(grid_lines + 1):
        y_ratio = i / grid_lines
        y_pos = margin_top + (avail_h * (1 - y_ratio))

        val_cum = max_cumulative * y_ratio
        if callable(value_formatter):
            label_text = str(value_formatter(val_cum))
        else:
            label_text = f"{fmt_num(int(val_cum))}{suffix}"
        label_rect_right = QRect(int(width - margin_right), int(y_pos) - 10, int(margin_right - 4), 20)
        painter.setPen(text_col)
        painter.drawText(label_rect_right, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, label_text)

def _draw_x_axis_labels_core(
    painter: QPainter,
    labels,
    width,
    height,
    margin_left,
    margin_right,
    margin_bottom,
    alpha=255,
    widget=None,
):
    if not labels:
        return

    t_colors = get_theme_colors(widget)
    text_col = axis_text_color(t_colors, fade=float(alpha) / 255.0, widget=widget)
    painter.setPen(text_col)

    avail_w = width - margin_left - margin_right
    n = len(labels)

    # Start and end labels: their rects are used later for the overlap check.
    start_rect = QRect(int(margin_left), int(height - margin_bottom), 200, 20)
    end_rect = QRect(int(width - margin_right - 200), int(height - margin_bottom), 200, 20)

    painter.drawText(start_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, str(labels[0]))

    painter.drawText(end_rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, str(labels[-1]))

    # Real bounding boxes for overlap check (approximate width based on text length)
    fm = painter.fontMetrics()
    start_w = fm.horizontalAdvance(str(labels[0]))
    end_w = fm.horizontalAdvance(str(labels[-1]))

    start_box = QRect(int(margin_left), int(height - margin_bottom), int(start_w + 15), 20)
    end_box = QRect(int(width - margin_right - end_w - 15), int(height - margin_bottom), int(end_w + 15), 20)

    if n > 2:
        target_count = max(1, width // 120)
        if target_count > 2:
            step = n // (target_count - 1)
            if step > 0:
                for i in range(step, n - step//2, step):
                    if i >= n - 1: break

                    x_center = margin_left + (i * (avail_w / (n - 1 if n > 1 else 1)))
                    label_str = str(labels[i])
                    label_w = fm.horizontalAdvance(label_str)

                    label_box = QRect(int(x_center - label_w/2 - 5), int(height - margin_bottom), int(label_w + 10), 20)

                    if label_box.intersects(start_box) or label_box.intersects(end_box):
                        continue

                    painter.drawText(label_box, Qt.AlignmentFlag.AlignCenter, label_str)


def draw_x_axis_labels(
    painter: QPainter,
    labels,
    width,
    height,
    margin_left,
    margin_right,
    margin_bottom,
    old_labels=None,
    progress=1.0,
    widget=None,
):
    if not labels:
        return

    # Animate when visible label content changes (not only edges).
    if old_labels:
        old_norm = [str(v).strip() for v in old_labels]
        new_norm = [str(v).strip() for v in labels]
        p = max(0.0, min(1.0, float(progress)))
        if old_norm != new_norm:
            if p <= 0.0:
                _draw_x_axis_labels_core(
                    painter, old_labels, width, height, margin_left, margin_right, margin_bottom, alpha=255, widget=widget
                )
                return
            if p >= 1.0:
                _draw_x_axis_labels_core(
                    painter, labels, width, height, margin_left, margin_right, margin_bottom, alpha=255, widget=widget
                )
                return

            # Old labels fade out first, new ones fade in after, so the two sets never overlap.
            old_alpha = int(round(max(0.0, 1.0 - 2.0 * p) * 255))
            new_alpha = int(round(max(0.0, 2.0 * p - 1.0) * 255))
            if old_alpha > 0:
                _draw_x_axis_labels_core(
                    painter, old_labels, width, height, margin_left, margin_right,
                    margin_bottom, alpha=old_alpha, widget=widget,
                )
            if new_alpha > 0:
                _draw_x_axis_labels_core(
                    painter, labels, width, height, margin_left, margin_right,
                    margin_bottom, alpha=new_alpha, widget=widget,
                )
            return

    _draw_x_axis_labels_core(
        painter, labels, width, height, margin_left, margin_right, margin_bottom, alpha=255, widget=widget
    )

def draw_cumulative_line_and_area(
    painter: QPainter,
    path: QPainterPath,
    fill_path: QPainterPath = None,
    widget=None,
):
    """Draw a standardized cumulative/total line and optional filled area underneath."""
    pal = get_theme_colors(widget)
    is_dark = pal["is_dark"]
    # Neutral grey like Anki's own graphs: a discreet line plus a soft area underneath,
    # so the bars stay the main thing and the accent colour doesn't tint the background.
    base = QColor(pal.get("text_secondary", pal["total_line"]))
    if fill_path is not None and not fill_path.isEmpty():
        # Soft vertical fade (strongest under the line, gone at the baseline) instead of
        # a flat tint over the whole plot, which read as a bluish glow in dark mode.
        from aqt.qt import QLinearGradient

        br = fill_path.boundingRect()
        grad = QLinearGradient(0, br.top(), 0, br.bottom())
        top_a = scale_line_alpha(52 if is_dark else 38, widget)
        top_col = QColor(base)
        top_col.setAlpha(top_a)
        mid_col = QColor(base)
        mid_col.setAlpha(int(top_a * 0.3))
        bot_col = QColor(base)
        bot_col.setAlpha(0)
        grad.setColorAt(0.0, top_col)
        grad.setColorAt(0.55, mid_col)  # eased falloff instead of a linear wash
        grad.setColorAt(1.0, bot_col)
        painter.fillPath(fill_path, grad)

    tl = total_line_params(pal, widget)
    strokes_total_line(painter, path, pal, tl["color"], is_dark, alpha=tl["alpha"], width=tl["width"], widget=widget)


def total_line_params(pal, widget=None):
    """Modern total-line look, shared by every chart (incl. ones that draw
    their own line, like Hourly Breakdown): fine line, light halo."""
    is_dark = bool(pal.get("is_dark"))
    # The line crosses the bars, so it uses the main text colour (strongest
    # contrast with the theme) on a background-coloured outline: a grey line
    # disappeared over bars of the same lightness in many themes.
    return {
        "color": QColor(pal.get("text_primary", pal.get("text", pal.get("total_line")))),
        "width": 1.3,
        "alpha": scale_line_alpha(215, widget),
        "halo": _halo_color(pal, is_dark),
        "halo_alpha": scale_line_alpha(150, widget),
        "halo_width": 3.4,
    }


def _halo_color(pal, is_dark):
    """Ring/halo color matching the (deeper) window background."""
    bg = QColor(pal.get("bg", QColor("#000000" if is_dark else "#ffffff")))
    return bg.darker(160) if is_dark else bg


def stroke_average_line(painter, x1, x2, y, color, *, widget=None, hovered=False, alpha_factor=1.0):
    """Draw the average line as short dashes in a lighter shade of the series color.

    Each dash sits on a dash of the background color, so it stays visible over bars
    of the same color.
    """
    a = max(0.0, min(1.0, float(alpha_factor or 0.0)))
    if a <= 0.001:
        return
    from aqt.qt import QPointF

    pal = get_theme_colors(widget)
    is_dark = bool(pal.get("is_dark"))
    p1, p2 = QPointF(float(x1), float(y)), QPointF(float(x2), float(y))
    small = widget is not None and getattr(widget, "height", lambda: 999)() < 200
    width = (1.3 if hovered else 0.9) if small else (1.5 if hovered else 1.1)
    dash_px, gap_px = (2.5, 2.5) if small else (3.0, 3.0)
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    halo = _halo_color(pal, is_dark)
    halo.setAlpha(int(round(90 * a)))
    painter.setPen(_dash_pen(halo, width + 1.2, dash_px, gap_px))
    painter.drawLine(p1, p2)
    line_col = QColor(color).lighter(135) if is_dark else QColor(color).darker(125)
    line_col.setAlpha(scale_line_alpha((235 if hovered else 175) * a, widget))
    painter.setPen(_dash_pen(line_col, width, dash_px, gap_px))
    painter.drawLine(p1, p2)
    painter.restore()


def _dash_pen(color, width, dash_px, gap_px):
    """Dashes of a fixed length in pixels (Qt dash patterns are in pen widths)."""
    pen = QPen(color, width)
    pen.setCapStyle(Qt.PenCapStyle.FlatCap)
    w = max(0.1, float(width))
    pen.setDashPattern([dash_px / w, gap_px / w])
    return pen


def strokes_total_line(painter, path, pal, base, is_dark, alpha=None, width=1.6, widget=None):
    """Total/cumulative line with a thin background-coloured halo underneath so
    it stays readable over bars of a similar colour."""
    halo = _halo_color(pal, is_dark)
    halo.setAlpha(scale_line_alpha(150, widget))
    halo_pen = QPen(halo, width + 2.1)
    halo_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    halo_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.strokePath(path, halo_pen)
    line_col = QColor(base)
    line_col.setAlpha(scale_line_alpha(alpha if alpha is not None else (150 if is_dark else 145), widget))
    pen = QPen(line_col, width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.strokePath(path, pen)


def draw_rich_stats_text(painter: QPainter, rect: QRectF, text: str, align: Qt.AlignmentFlag):
    """Draw text bolding parts before each ':' (handles joined stats with ' · ')."""
    if ":" not in text:
        painter.drawText(rect, align, text)
        return

    sep = " · "
    segments = text.split(sep)

    normal_font = painter.font()
    normal_font.setBold(False)
    bold_font = painter.font()
    bold_font.setBold(True)

    fm_normal = painter.fontMetrics()
    fm_bold = QFontMetrics(bold_font)

    draw_parts = [] # List of (text, is_bold, width)
    total_w = 0

    for i, seg in enumerate(segments):
        if ":" in seg:
            label, value = seg.split(":", 1)
            label += ":"

            l_w = fm_bold.horizontalAdvance(label)
            v_w = fm_normal.horizontalAdvance(value)

            draw_parts.append((label, True, l_w))
            draw_parts.append((value, False, v_w))
            total_w += l_w + v_w
        else:
            w = fm_normal.horizontalAdvance(seg)
            draw_parts.append((seg, False, w))
            total_w += w

        if i < len(segments) - 1:
            sep_w = fm_normal.horizontalAdvance(sep)
            draw_parts.append((sep, False, sep_w))
            total_w += sep_w

    x = rect.x()
    if align & Qt.AlignmentFlag.AlignHCenter:
        x += (rect.width() - total_w) / 2
    elif align & Qt.AlignmentFlag.AlignRight:
        x += rect.width() - total_w

    y = rect.y() + (rect.height() + fm_normal.ascent() - fm_normal.descent()) / 2

    current_x = x
    for p_text, is_bold, p_w in draw_parts:
        painter.setFont(bold_font if is_bold else normal_font)
        painter.drawText(int(current_x), int(y), p_text)
        current_x += p_w


def draw_wrapped_bottom_stats(
    painter: QPainter,
    stats,
    *,
    plot_w,
    height,
    margin_left,
    margin_bottom,
    widget=None,
):
    """Draw centered wrapped chart stats in the bottom area."""
    if not stats:
        return
    painter.setPen(get_theme_colors(widget).get("text", QColor("#ffffff" if is_night_mode(widget) else "#000000")))
    font = painter.font()
    font.setPixelSize(13)
    painter.setFont(font)
    fm = painter.fontMetrics()

    draw_lines = ChartGeometry.wrap_stats_text(stats, plot_w, fm)
    line_h = 18
    total_text_h = len(draw_lines) * line_h
    avail_stats_h = margin_bottom - 30
    y_start = height - margin_bottom + 30 + (avail_stats_h - total_text_h) // 2

    for i, text in enumerate(draw_lines):
        t_rect = QRectF(margin_left, y_start + (i * line_h), plot_w, line_h)
        draw_rich_stats_text(painter, t_rect, text, Qt.AlignmentFlag.AlignCenter)

_DARK_CACHE = {}  # id(widget) -> (time, value): hundreds of bars per paint ask the same thing


def _bar_is_dark(painter, widget=None) -> bool:
    try:
        key = id(widget) if widget is not None else id(painter.device())
        now = time.perf_counter()
        hit = _DARK_CACHE.get(key)
        if hit is not None and now - hit[0] < 0.05:
            return hit[1]
        if widget is not None:
            val = bool(is_night_mode(widget))
        else:
            dev = painter.device()
            from aqt.qt import QWidget
            val = bool(is_night_mode(dev if isinstance(dev, QWidget) else None))
        if len(_DARK_CACHE) > 64:
            _DARK_CACHE.clear()
        _DARK_CACHE[key] = (now, val)
        return val
    except Exception:
        return False


def bar_fade_factor(width, height):
    """0..1: how much of the vertical bar fade to use for a bar of this size."""
    def smooth(x):
        x = max(0.0, min(1.0, x))
        return x * x * (3.0 - 2.0 * x)

    return smooth((width - 2.0) / 4.0) * smooth((height - 2.0) / 8.0)


def draw_bar_rect(painter, rect, radius=1.8, fade=True, widget=None):
    """Bar with softly rounded top corners; plain rect for thin or flat bars
    (hundreds of bars stay cheap)."""
    w = rect.width()
    h = rect.height()
    r = min(float(radius), w * 0.25, h)
    # Soft vertical fade: full colour at the top, a bit lighter at the base. It fades in
    # with the bar size (no fade on hair-thin bars) instead of switching on at a fixed
    # size, so bars growing during a zoom do not change shade at once.
    base = None
    _fill = False
    try:
        size_k = bar_fade_factor(w, h)
        base = painter.brush().color()
        if fade and base.alpha() > 0 and size_k > 0.01:
            from aqt.qt import QLinearGradient

            top = QColor(base)
            bot = QColor(base)
            k = chart_style(widget)[1] / 100.0 * size_k  # 0 = flat bars, 1 = full gradient
            if _bar_is_dark(painter, widget):
                # Dark background: lighter at the top, a deeper shade of the same hue at the
                # base. Fading to transparent would look muddy on the dark card, so the color
                # stays saturated.
                top = top.lighter(100 + int(round(14 * k)))
                top.setAlpha(base.alpha())
                bot = bot.darker(100 + int(round(30 * k)))
                bot.setAlpha(max(30, int(base.alpha() * (1.0 - 0.12 * k))))
            else:
                bot.setAlpha(max(30, int(base.alpha() * (1.0 - 0.38 * k))))
            g = QLinearGradient(0, rect.y(), 0, rect.y() + h)
            g.setColorAt(0.0, top)
            g.setColorAt(1.0, bot)
            painter.setBrush(g)
            _fill = True
    except Exception:
        _fill = False
    if w < 4.0 or r < 1.0:
        painter.drawRect(rect)
        if _fill:
            painter.setBrush(base)
        return
    x = rect.x()
    y = rect.y()
    path = QPainterPath()
    path.moveTo(x, y + h)
    path.lineTo(x, y + r)
    path.quadTo(x, y, x + r, y)
    path.lineTo(x + w - r, y)
    path.quadTo(x + w, y, x + w, y + r)
    path.lineTo(x + w, y + h)
    path.closeSubpath()
    painter.drawPath(path)
    if _fill:
        painter.setBrush(base)
