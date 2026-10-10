# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from datetime import datetime
import re

from aqt.qt import (
    QPixmap,
    QPainter,
    QFileDialog,
    QColor,
    QFont,
    QRect,
    Qt,
    QTableWidget,
    QScrollBar,
    QPushButton,
    QCheckBox,
    QLabel,
    QPoint,
    QGraphicsDropShadowEffect,
    QRectF,
    QLinearGradient,
    QPen,
    QBrush,
)
from aqt.theme import theme_manager
from aqt.utils import showInfo, showCritical
from ..logger import log_swallowed
# Export layout constants (all in virtual pixels, before 2x scale)
_SCALE = 2.0
_PAD = 32
_HEADER_H = 74
_FOOTER_H = 0
_AFTER_HEADER_PAD = 8
_BETWEEN_GAP = 18
_BEFORE_FOOTER_PAD = 24

# Internal helpers: theme, context, drawing

def _theme(dialog):
    """Colors of the theme the Deep Dive is showing, as QColors.

    Taken from the add-on palette, not the dialog's QPalette, which can hold stale
    values.
    """
    dark = bool(theme_manager.get_night_mode())
    tpal = None
    try:
        from ...ui.theme import get_theme_palette, get_theme_effective_is_dark

        conf = dialog.addon_config.config
        dark = bool(get_theme_effective_is_dark(conf))
        tpal = get_theme_palette(conf, is_dark=dark)
    except Exception:
        tpal = None

    if isinstance(tpal, dict) and tpal.get("bg_root"):
        bg = QColor(tpal["bg_root"])
        fg = QColor(tpal.get("text_primary", "#f4f4f5" if dark else "#18181b"))
        accent = QColor(tpal.get("accent", "#60a5fa" if dark else "#2563eb"))
        try:
            from ...widgets.chart_utils.theme import ensure_contrast

            accent = ensure_contrast(accent, bg, 3.0)
        except Exception:
            log_swallowed()
    else:
        pal = dialog.palette()
        bg = pal.color(dialog.backgroundRole())
        fg = pal.color(dialog.foregroundRole())
        accent = QColor("#60a5fa") if dark else QColor("#2563eb")
    r, g, b = fg.red(), fg.green(), fg.blue()
    return dict(
        bg      = bg,
        fg      = fg,
        accent  = accent,
        muted   = QColor(r, g, b, 115),
        divider = QColor(r, g, b, 28),
        sect_bg = QColor(r, g, b, 11 if dark else 7),
        dark    = dark,
    )


def _period_label(period):
    """Convert a Period integer constant to a readable string."""
    from ....const import Period
    labels = {
        Period.TOTAL:        "All Time",
        Period.TODAY:        "Today",
        Period.YESTERDAY:    "Yesterday",
        Period.WEEK:         "Past Week",
        Period.TWO_WEEKS:    "Past 2 Weeks",
        Period.MONTH:        "Past Month",
        Period.THREE_MONTHS: "Past 3 Months",
        Period.YEAR:         "Past Year",
        Period.LAST_YEAR:    "Last Year",
        Period.CUSTOM:       "Custom",
    }
    return labels.get(period, str(period))


def _clean_deck_name(name):
    """Strip HTML entities and tree-hierarchy prefix characters from a deck name."""
    import html
    name = html.unescape(name)                          # &nbsp; to space, etc.
    name = re.sub(r'^[\s\u00a0├└│─·\-]+', '', name)   # leading tree chars
    return name.strip()


def _context(dialog):
    """Return (title, subtitle_parts) for the export header.
    subtitle_parts is a list of (label, value) tuples.
    """
    mgr = getattr(dialog, 'deep_dive_manager', None)
    if mgr:
        deck   = _clean_deck_name(getattr(mgr, 'last_title', None) or "Collection")
        period = getattr(mgr, 'last_history_range', None)
        if period is None:
            period = getattr(mgr, 'last_period_range', None)
        parts = [("Deck", deck)]
        if period is not None:   # Period.WEEK = 0, so `if period` would skip it
            parts.append(("Time Range", _period_label(period)))
    else:
        view = "Deck" if dialog.view_mode == 'deck' else "Time Range"
        idx  = dialog.tab_widget.currentIndex()
        ctx  = dialog.tab_widget.tabText(idx) if idx >= 0 else ""
        parts = [(view, ctx)] if ctx else []
    return "Deep Dive Stats", parts


def _draw_header(p, W, title, subtitle_parts, t):
    """Header row: logo + title on the left, vertically centered; the
    Deck / Time Range pills right-aligned on the same row with the export
    date under them. On a narrow export the pills move under the title."""
    import os as _os
    assets = _os.path.join(_os.path.dirname(__file__), '..', '..', '..', 'assets')
    row_cy = 32          # vertical center of the header row (virtual px)
    logo_h = 34
    logo_pix = QPixmap(_os.path.join(assets, 'logo_nobg.png'))
    if logo_pix.isNull():
        logo_pix = QPixmap(_os.path.join(assets, 'logo.png'))
    if not logo_pix.isNull():
        logo_w = int(round(logo_h * logo_pix.width() / max(1, logo_pix.height())))
        p.save()
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.drawPixmap(QRect(_PAD, row_cy - logo_h // 2, logo_w, logo_h), logo_pix)
        p.restore()
    else:
        logo_w = 4
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(t['accent'])
        p.drawRoundedRect(_PAD, row_cy - 18, 4, 36, 2, 2)
    text_x = _PAD + logo_w + 12

    # Title
    f = QFont()
    f.setPointSize(15)
    f.setBold(True)
    f.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 102)
    p.setFont(f)
    title_w = p.fontMetrics().horizontalAdvance(title)
    title_h = 28

    # Pills (measured first, to decide where they go)
    f_lbl = QFont()
    f_lbl.setPointSize(8)
    f_val = QFont()
    f_val.setPointSize(8)
    f_val.setBold(True)
    pill_h = 20
    gap = 8
    pills = []
    for lbl, val in subtitle_parts:
        lbl_text = lbl + ":"
        p.setFont(f_lbl)
        lbl_w = p.fontMetrics().horizontalAdvance(lbl_text)
        p.setFont(f_val)
        val_w = p.fontMetrics().horizontalAdvance(val)
        pills.append((lbl_text, val, lbl_w, val_w, 10 + lbl_w + 6 + val_w + 10))
    pills_w = sum(pw for *_r, pw in pills) + gap * max(0, len(pills) - 1)

    date_txt = "Exported · " + datetime.now().strftime("%B %d, %Y  %H:%M")
    f3 = QFont()
    f3.setPointSize(8)
    p.setFont(f3)
    date_w = p.fontMetrics().horizontalAdvance(date_txt)
    date_h = 14

    right_w = max(pills_w, date_w)
    side_by_side = text_x + title_w + 32 + right_w <= W - _PAD

    if side_by_side:
        title_y = row_cy - title_h // 2
        block_h = (pill_h + 5 + date_h) if pills else date_h
        block_top = row_cy - block_h // 2
        pill_y = block_top
        x = W - _PAD - pills_w
        date_y = block_top + (pill_h + 5 if pills else 0)
    else:
        # Narrow: title on top, pills under it, date under the pills on the right.
        title_y = 8
        pill_y = 40
        x = text_x
        date_y = 8

    # Draw title
    p.setFont(f)
    title_rect = QRect(text_x, title_y, W - text_x - _PAD, title_h)
    head, _sp, tail = title.partition(" ")
    if tail and head == "Anki":
        head_txt = head + " "
        head_w = p.fontMetrics().horizontalAdvance(head_txt)
        p.setPen(t['fg'])
        p.drawText(QRect(title_rect.x(), title_rect.y(), head_w + 2, title_rect.height()),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, head_txt)
        p.setPen(t['accent'])
        p.drawText(QRect(title_rect.x() + head_w, title_rect.y(), title_rect.width() - head_w, title_rect.height()),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, tail)
    else:
        p.setPen(t['accent'])
        p.drawText(title_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, title)

    # Draw pills
    for lbl_text, val, lbl_w, val_w, pill_w in pills:
        p.save()
        p.setPen(Qt.PenStyle.NoPen)
        fill = QColor(t['fg'])
        fill.setAlphaF(0.07)
        p.setBrush(fill)
        p.drawRoundedRect(QRectF(x, pill_y, pill_w, pill_h), pill_h / 2, pill_h / 2)
        p.restore()
        p.setFont(f_lbl)
        p.setPen(t['muted'])
        p.drawText(QRect(int(x + 10), pill_y, lbl_w + 2, pill_h),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, lbl_text)
        p.setFont(f_val)
        p.setPen(t['fg'])
        p.drawText(QRect(int(x + 10 + lbl_w + 6), pill_y, val_w + 2, pill_h),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, val)
        x += pill_w + gap

    # Export date: muted text colour at a strength that stays readable on every theme.
    date_col = QColor(t['muted'])
    date_col.setAlphaF(0.62)
    p.setFont(f3)
    p.setPen(date_col)
    p.drawText(
        QRect(_PAD, date_y, W - _PAD * 2, date_h),
        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        date_txt,
    )

    grad = QLinearGradient(_PAD, 0, W - _PAD, 0)
    c0 = QColor(t['accent']); c0.setAlphaF(0.85)
    c1 = QColor(t['divider']); c1.setAlphaF(0.9)
    c2 = QColor(t['divider']); c2.setAlphaF(0.0)
    grad.setColorAt(0.0, c0); grad.setColorAt(0.12, c1); grad.setColorAt(1.0, c2)
    p.setPen(QPen(QBrush(grad), 1.5))
    p.drawLine(_PAD, _HEADER_H - 10, W - _PAD, _HEADER_H - 10)



def _save_as_pdf(path, pix, logical_w, logical_h):
    """Render *pix* (a 2× QPixmap) to a PDF whose page matches the logical dimensions."""
    try:
        from PyQt6.QtGui import QPdfWriter, QPageSize
        from PyQt6.QtCore import QSizeF, QMarginsF
    except ImportError:
        from PyQt5.QtGui import QPdfWriter, QPageSize
        from PyQt5.QtCore import QSizeF, QMarginsF
    dpi = 96
    w_mm = logical_w * 25.4 / dpi
    h_mm = logical_h * 25.4 / dpi
    writer = QPdfWriter(path)
    writer.setResolution(dpi)
    writer.setPageSize(QPageSize(QSizeF(w_mm, h_mm), QPageSize.Unit.Millimeter))
    writer.setPageMargins(QMarginsF(0, 0, 0, 0))
    pdf_p = QPainter(writer)
    pdf_p.drawPixmap(0, 0, writer.width(), writer.height(), pix)
    pdf_p.end()


def _activate_layouts(widget):
    """Activate every layout in the widget tree so geometry is up to date before render().

    Calls the base-class method directly because some Python layouts shadow
    QWidget.layout() with an attribute of the same name.
    """
    from aqt.qt import QWidget as _QWidget
    _get_layout = _QWidget.layout   # unbound C++ method: bypasses attr shadowing
    for w in [widget] + list(widget.findChildren(_QWidget)):
        try:
            lay = _get_layout(w)
            if lay:
                lay.activate()
        except Exception:
            log_swallowed()


def _clear_label_effects(widget):
    """Remove QGraphicsEffect from every QLabel inside *widget* so render() draws them.
    Returns a list of (label, opacity) tuples for _restore_label_effects().
    QWidget::render() silently skips children that have a QGraphicsEffect applied.
    """
    saved = []
    for lbl in widget.findChildren(QLabel):
        eff = lbl.graphicsEffect()
        if eff is not None:
            opacity = getattr(lbl, '_last_shadow_opacity', 0.0)
            lbl.setGraphicsEffect(None)      # Qt deletes old eff's C++ object here
            lbl._last_shadow_opacity = -1    # reset cache so restoration can re-apply
            saved.append((lbl, opacity))
    return saved


def _restore_label_effects(saved):
    """Recreate drop-shadow effects that were cleared by _clear_label_effects()."""
    for lbl, opacity in saved:
        if opacity > 0.01:
            try:
                shadow = QGraphicsDropShadowEffect()
                shadow.setBlurRadius(4)
                shadow.setOffset(0, 1)
                shadow.setColor(QColor(0, 0, 0, int(255 * opacity)))
                lbl.setGraphicsEffect(shadow)
                lbl._last_shadow_opacity = opacity
            except Exception:
                log_swallowed()


def _hide_controls(widget):
    """Collapse the interactive controls inside widget so layouts reclaim their space before render().

    Returns the saved state for _restore_controls(): ('widget', w, old_min, old_max)
    or ('margin', lay, old_margins) items.
    """
    from aqt.qt import QSize, QWidget as _QWidget
    saved = []
    zero = QSize(0, 0)

    for w in widget.findChildren(QPushButton):
        if w.isVisible():
            saved.append(('widget', w, w.minimumSize(), w.maximumSize()))
            w.setMinimumSize(zero)
            w.setMaximumSize(zero)
    for w in widget.findChildren(QCheckBox):
        if w.isVisible():
            saved.append(('widget', w, w.minimumSize(), w.maximumSize()))
            w.setMinimumSize(zero)
            w.setMaximumSize(zero)

    # Chart titles elide when the live header is crowded by its toggles; with
    # those hidden the title can have its full width in the export.
    try:
        from ...widgets.common.chart_header import ElidedTitleLabel

        for lbl in widget.findChildren(ElidedTitleLabel):
            if lbl.isVisible():
                saved.append(('widget', lbl, lbl.minimumSize(), lbl.maximumSize()))
                lbl.setMinimumWidth(lbl.sizeHint().width())
    except Exception:
        log_swallowed()

    # Heatmap mode separators ("|") only make sense next to the buttons.
    for lbl in widget.findChildren(QLabel):
        if lbl.isVisible() and (lbl.text() or "").strip() == "|":
            saved.append(('widget', lbl, lbl.minimumSize(), lbl.maximumSize()))
            lbl.setMinimumSize(zero)
            lbl.setMaximumSize(zero)

    # Add a small left indent to section header labels to compensate for the
    # hidden collapse arrow, so the title doesn't sit flush against the edge.
    _get_layout = _QWidget.layout
    seen = set()
    for lbl in widget.findChildren(QLabel):
        if lbl.objectName() == "pinned_header":
            parent = lbl.parentWidget()
            if parent and id(parent) not in seen:
                try:
                    lay = _get_layout(parent)
                    if lay:
                        m = lay.contentsMargins()
                        saved.append(('margin', lay, m))
                        lay.setContentsMargins(8, m.top(), m.right(), m.bottom())
                        seen.add(id(parent))
                except Exception:
                    log_swallowed()

    # Force every layout in the subtree to recalculate NOW, before render()
    _activate_layouts(widget)
    return saved


def _restore_controls(saved):
    from aqt.qt import QSize
    big = QSize(16777215, 16777215)
    for item in saved:
        if item[0] == 'widget':
            _, w, old_min, old_max = item
            # Restore max first so Qt doesn't clamp min against the zero max
            w.setMaximumSize(old_max if old_max.isValid() and old_max != QSize(0, 0) else big)
            w.setMinimumSize(old_min)
            w.show()
        elif item[0] == 'margin':
            _, lay, old_margins = item
            lay.setContentsMargins(old_margins)



def _finish_chart_animations(sections):
    """Put every chart of the exported sections in its final state.

    A chart that was never scrolled into view still sits at progress 0 (its opening animation
    has not played) and would be drawn empty. One that is mid-animation would be drawn half way.
    """
    try:
        from ...animations.chart_policy import collect_chart_animation_targets
    except Exception:
        log_swallowed()
        return
    for sec in sections:
        widget = sec.get('widget')
        if widget is None:
            continue
        try:
            charts = collect_chart_animation_targets(widget)
        except Exception:
            log_swallowed()
            continue
        for chart in charts:
            try:
                anim = getattr(chart, 'animation', None)
                if anim is not None:
                    anim.stop()
                if hasattr(chart, '_progress'):
                    chart._progress = 1.0
                chart._initial_animation_done = True
                finish_mode = getattr(chart, '_on_mode_transition_finished', None)
                if callable(finish_mode) and getattr(chart, '_mode_transition_active', False):
                    finish_mode()
            except Exception:
                log_swallowed()
        try:
            from ...widgets.charts.activity.review_dots import ReviewDotsChart

            for dots in widget.findChildren(ReviewDotsChart):
                dots.finish_intro()
        except Exception:
            log_swallowed()


def _stat_card_grid(dashboard, content_w, gap=10):
    """Grid layout for the visible stat cards of *dashboard* that fits
    *content_w* while keeping the cards close to their on-screen size.
    Returns None when there is nothing to lay out."""
    import math
    try:
        from ...widgets.stats_cards import StatCardWidget
    except Exception:
        return None
    cards = [w for w in dashboard.findChildren(StatCardWidget) if w.isVisible() and w.width() > 0]
    if len(cards) < 2:
        return None
    cards.sort(key=lambda w: (w.mapTo(dashboard, QPoint(0, 0)).y(), w.mapTo(dashboard, QPoint(0, 0)).x()))
    n = len(cards)
    card_w = max(w.width() for w in cards)
    card_h = max(w.height() for w in cards)
    best = None
    for cols in range(1, n + 1):
        s = (content_w - gap * (cols - 1)) / float(cols * card_w)
        if s <= 0:
            continue
        rows = math.ceil(n / cols)
        empty = rows * cols - n
        # Closest to the on-screen size, few empty slots, never above 1.3x.
        score = abs(math.log(s)) + 0.08 * empty + (10.0 if s > 1.3 else 0.0)
        if best is None or score < best[0]:
            best = (score, cols, s, rows)
    _score, cols, s, rows = best
    cell_w = (content_w - gap * (cols - 1)) / float(cols)
    cell_h = card_h * s
    return {
        '_cards': cards, '_cols': cols, '_cs': s,
        '_cell_w': cell_w, '_cell_h': cell_h, '_gap': gap,
        '_grid_h': int(math.ceil(rows * cell_h + (rows - 1) * gap)),
    }


def export_visual(dialog, mode):
    """Export as an image. The table may sit closed in the drawer, so lay it out first."""
    restore = None
    if mode in ("table", "full"):
        try:
            from ...ui.details_dialog.table_drawer import export_prepare

            restore = export_prepare(dialog)
        except Exception:
            restore = None
    try:
        return _export_visual_impl(dialog, mode)
    finally:
        if restore is not None:
            try:
                restore()
            except Exception:
                log_swallowed()


def _export_visual_impl(dialog, mode):
    """Build and save a high-resolution PNG.

    mode is "deep_dive" (charts panel), "table" (stat cards and table) or "full"
    (stat cards, charts if open, and table).
    """
    _dashboard_effects_saved = []
    sc = None
    try:
        t = _theme(dialog)
        title, subtitle_parts = _context(dialog)
        sections = []   # list of dicts describing what to render

        is_dd_open = (
            hasattr(dialog, 'expanded_container')
            and dialog.expanded_container.isVisible()
        )

        # Dashboard, shown at the top in table, full and deep_dive modes
        if mode in ("table", "full", "deep_dive"):
            if hasattr(dialog, 'dashboard_frame'):
                db = dialog.dashboard_frame
                if db.height() > 0:
                    # Clear graphics effects on labels so render() draws them correctly.
                    _dashboard_effects_saved = _clear_label_effects(db)
                    sections.append(dict(
                        kind='widget', label='Summary',
                        widget=db, w=db.width(), h=db.height(),
                    ))

        # Deep Dive charts, full scrollable height
        _sc_orig_w = None
        _sc_orig_h = None
        if mode == "deep_dive" or (mode == "full" and is_dd_open):
            viewport = None
            if hasattr(dialog, 'expanded_scroll'):
                sc = dialog.expanded_scroll.widget()
                viewport = dialog.expanded_scroll.viewport()

            if sc and viewport and viewport.width() > 20 and viewport.height() > 20:
                # Deep Dive and Full View: export the whole content height (every visible section),
                # not just the part on screen, so lower charts are not cut.
                export_h = sc.height()
                try:
                    max_bottom_sc = 0
                    ddm = getattr(dialog, "deep_dive_manager", None)
                    wrappers = getattr(ddm, "section_wrappers", {}) if ddm else {}
                    for wrapper in wrappers.values():
                        if not wrapper or not wrapper.isVisible():
                            continue
                        if wrapper.width() <= 1 or wrapper.height() <= 1:
                            continue
                        b = wrapper.y() + wrapper.height()
                        if b > max_bottom_sc:
                            max_bottom_sc = b
                    if max_bottom_sc > 0:
                        export_h = max(20, min(sc.height(), max_bottom_sc + 8))
                except Exception:
                    export_h = sc.height()

                sections.append(dict(
                    kind='widget', label='Deep Dive Charts',
                    widget=sc, w=sc.width(), h=export_h,
                ))
            elif mode == "deep_dive":
                showInfo(
                    "No Deep Dive is currently open.\n\n"
                    "Click on any row in the statistics table to open the "
                    "Deep Dive, then export."
                )
                return

        # Statistics table, all rows (not just the visible ones)
        if mode in ("table", "full"):
            tab = dialog.tab_widget.currentWidget()
            if tab:
                tbl = tab.findChild(QTableWidget)
                if tbl and tbl.rowCount() > 0:
                    tbl_w = (tbl.horizontalHeader().length()
                             + tbl.verticalHeader().width() + 2)
                    tbl_h = (tbl.verticalHeader().length()
                             + tbl.horizontalHeader().height() + 2)
                    tab_name = dialog.tab_widget.tabText(
                        dialog.tab_widget.currentIndex()
                    )
                    sections.append(dict(
                        kind='table', label=f'Statistics - {tab_name}',
                        widget=tbl, w=tbl_w, h=tbl_h,
                    ))

        if not sections:
            showInfo("Nothing to export. Load some data first.")
            return

        # Canvas width: the Deep Dive width when the mode includes it, so dashboard and
        # table scale to the same extent. Table-only mode uses the widest section.
        dd_sec = next((s for s in sections if s['label'] == 'Deep Dive Charts'), None)
        if dd_sec:
            content_w = dd_sec['w']
        else:
            content_w = max(s['w'] for s in sections)

        # Give every section a render scale so they share content_w. sec['w'] and
        # sec['h'] keep the natural pixel size, sec['_rscale'] is the QPainter scale.
        for sec in sections:
            sec['_rscale'] = content_w / sec['w'] if sec['w'] else 1.0
            sec['_rh'] = int(sec['h'] * sec['_rscale'])

        # When the stat card strip would shrink a lot to fit the content width (Full
        # View), lay the cards out in a grid so they keep about their on-screen size.
        for sec in sections:
            if sec['label'] == 'Summary' and sec['_rscale'] < 0.8:
                grid = _stat_card_grid(sec['widget'], content_w)
                if grid:
                    sec['kind'] = 'cards'
                    sec.update(grid)
                    sec['_rh'] = grid['_grid_h']

        _finish_chart_animations(sections)

        total_w   = content_w + _PAD * 2
        sections_h = (sum(s['_rh'] for s in sections)
                      + max(0, len(sections) - 1) * _BETWEEN_GAP)
        total_h   = (_HEADER_H + _AFTER_HEADER_PAD
                     + sections_h
                     + _BEFORE_FOOTER_PAD + _FOOTER_H)

        # High-resolution pixmap
        pix = QPixmap(int(total_w * _SCALE), int(total_h * _SCALE))
        pix.fill(t['bg'])

        # Chart caches record vectors instead of screen-resolution bitmaps
        # while exporting, so axis text is as sharp as everything else.
        from ...widgets.charts.common.cache_dpr import set_exporting
        set_exporting(True)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.scale(_SCALE, _SCALE)

        _draw_header(p, total_w, title, subtitle_parts, t)

        # Render each section
        y = _HEADER_H + _AFTER_HEADER_PAD
        for i, sec in enumerate(sections):
            widget = sec['widget']
            hidden = _hide_controls(widget)

            rscale = sec.get('_rscale', 1.0)
            rh     = sec.get('_rh', sec['h'])
            set_exporting(True, scale=_SCALE * rscale)

            if sec['kind'] == 'cards':
                cards, cols, s = sec['_cards'], sec['_cols'], sec['_cs']
                cell_w, cell_h, gap = sec['_cell_w'], sec['_cell_h'], sec['_gap']
                set_exporting(True, scale=_SCALE * s)
                n = len(cards)
                for idx, card in enumerate(cards):
                    r, c = divmod(idx, cols)
                    in_row = min(cols, n - r * cols)
                    # Center a shorter last row.
                    row_off = (cols - in_row) * (cell_w + gap) / 2.0
                    cx = row_off + c * (cell_w + gap) + (cell_w - card.width() * s) / 2.0
                    cy = r * (cell_h + gap)
                    p.save()
                    p.translate(_PAD + cx, y + cy)
                    p.scale(s, s)
                    card.render(p)
                    p.restore()

            elif sec['kind'] == 'table':
                tbl   = widget
                tbl_w = sec['w']
                tbl_h = sec['h']

                # Expand table to its full content size so every row is rendered
                old_hp = tbl.horizontalScrollBarPolicy()
                old_vp = tbl.verticalScrollBarPolicy()
                tbl.setFixedSize(tbl_w, tbl_h)
                tbl.setHorizontalScrollBarPolicy(
                    Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
                tbl.setVerticalScrollBarPolicy(
                    Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
                for sb in tbl.findChildren(QScrollBar):
                    sb.hide()

                p.save()
                p.translate(_PAD, y)
                if rscale != 1.0:
                    p.scale(rscale, rscale)
                tbl.render(p)
                p.restore()

                tbl.setMinimumSize(0, 0)
                tbl.setMaximumSize(16777215, 16777215)
                tbl.setHorizontalScrollBarPolicy(old_hp)
                tbl.setVerticalScrollBarPolicy(old_vp)
                tbl.updateGeometry()
                if tbl.parentWidget():
                    tbl.parentWidget().update()

            else:
                # Render scroll-area content and the dashboard directly at natural size, with no
                # viewport clipping. Strip left/right layout margins so all sections share the same
                # left edge (the dashboard has an 8px left margin).
                from aqt.qt import QWidget as _QW
                wlay = _QW.layout(widget)
                orig_margins = wlay.contentsMargins() if wlay else None
                if orig_margins and (orig_margins.left() > 0 or orig_margins.right() > 0):
                    wlay.setContentsMargins(0, orig_margins.top(), 0, orig_margins.bottom())
                    _activate_layouts(widget)

                p.save()
                p.translate(_PAD, y)
                if rscale != 1.0:
                    p.scale(rscale, rscale)
                    p.setClipRect(0, 0, sec['w'], sec['h'])
                else:
                    p.setClipRect(0, 0, sec['w'], sec['h'])
                crop_y = int(sec.get('crop_y', 0) or 0)
                if crop_y > 0:
                    p.translate(0, -crop_y)
                widget.render(p)
                p.restore()

                if orig_margins and (orig_margins.left() > 0 or orig_margins.right() > 0):
                    wlay.setContentsMargins(orig_margins)

            _restore_controls(hidden)
            y += rh
            if i < len(sections) - 1:
                y += _BETWEEN_GAP

        p.end()
        set_exporting(False)

        if _sc_orig_w is not None and sc is not None:
            sc.resize(_sc_orig_w, _sc_orig_h if _sc_orig_h else sc.height())
            dialog.expanded_scroll.setWidgetResizable(True)
            _activate_layouts(sc)

        _restore_label_effects(_dashboard_effects_saved)

        # Save dialog
        import os
        suffix = {"deep_dive": "DeepDive", "table": "Table", "full": "FullView"}
        fn = (f"DeepDiveStats_{suffix.get(mode, mode)}_"
              f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        start_dir = os.path.join(desktop if os.path.isdir(desktop) else os.path.expanduser("~"), fn)
        path, sel_filter = QFileDialog.getSaveFileName(
            dialog, "Save Export", start_dir,
            "PNG Image (*.png);;PDF Document (*.pdf);;JPEG Image (*.jpg)",
        )
        if path:
            low = path.lower()
            if 'pdf' in sel_filter.lower() or low.endswith('.pdf'):
                if not low.endswith('.pdf'):
                    path += '.pdf'
                _save_as_pdf(path, pix, total_w, total_h)
                ok = True
            else:
                # The chosen filter decides the format when the name has no (or an unrelated)
                # extension, since QPixmap.save() would otherwise fail silently.
                jpeg = 'jpeg' in sel_filter.lower() or 'jpg' in sel_filter.lower()
                if not low.endswith(('.png', '.jpg', '.jpeg')):
                    path += '.jpg' if jpeg else '.png'
                ok = pix.save(path, quality=95) if path.lower().endswith(('.jpg', '.jpeg')) else pix.save(path)
            if ok:
                showInfo(f"Saved to:\n{path}")
            else:
                showCritical(f"Could not save the export to:\n{path}")

    except Exception as e:
        import traceback
        try:
            from ...widgets.charts.common.cache_dpr import set_exporting as _se
            _se(False)
        except Exception:
            log_swallowed()
        if _sc_orig_w is not None and sc is not None:
            try:
                sc.resize(_sc_orig_w, _sc_orig_h if _sc_orig_h else sc.height())
                dialog.expanded_scroll.setWidgetResizable(True)
                _activate_layouts(sc)
            except Exception:
                log_swallowed()
        _restore_label_effects(_dashboard_effects_saved)
        showCritical(f"Export failed:\n{str(e)}\n\n{traceback.format_exc()}")


_export = export_visual



