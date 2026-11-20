# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from datetime import datetime
import re

from aqt.qt import (
    QPixmap,
    QPainter,
    QColor,
    QFont,
    QRect,
    Qt,
    QRectF,
    QLinearGradient,
    QPen,
    QBrush,
)
from aqt.theme import theme_manager
from ..logger import log_swallowed
from ....i18n import tr, format_date
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


def _clean_deck_name(name):
    """Strip HTML entities and tree-hierarchy prefix characters from a deck name."""
    import html
    name = html.unescape(name)                          # &nbsp; to space, etc.
    name = re.sub(r'^[\s\u00a0├└│─·\-]+', '', name)   # leading tree chars
    return name.strip()


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

    now = datetime.now()
    date_txt = tr("Exported · {date}", date=format_date(now, now.strftime("%H:%M")))
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


