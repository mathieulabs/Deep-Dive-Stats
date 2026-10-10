# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import (
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QStyle,
    QApplication,
    QTextDocument,
    Qt,
    QRect,
    QColor,
)

class HTMLDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        options = QStyleOptionViewItem(option)
        self.initStyleOption(options, index)
        if hasattr(QStyle, "StateFlag") and hasattr(QStyle.StateFlag, "State_HasFocus"):
             options.state &= ~QStyle.StateFlag.State_HasFocus
        elif hasattr(QStyle, "State_HasFocus"):
             options.state &= ~QStyle.State_HasFocus

        style = QApplication.style() if options.widget is None else options.widget.style()

        if options.state & QStyle.StateFlag.State_Selected:
            painter.save()
            # Translucent tint of the theme's selection color: the row stays readable
            # (red and green figures keep their contrast) and an accent bar marks its start.
            sel = QColor(options.palette.highlight().color())
            tint = QColor(sel)
            tint.setAlpha(38)  # quiet tint; the accent bar does the marking
            painter.fillRect(options.rect, tint)
            if index.column() == 0:
                painter.fillRect(QRect(options.rect.left(), options.rect.top(), 3, options.rect.height()), sel)
            painter.restore()
        else:
            bg_brush = index.data(Qt.ItemDataRole.BackgroundRole)
            if bg_brush:
                painter.save()
                painter.fillRect(options.rect, bg_brush)
                painter.restore()

        # Resolve text color from active palette/theme first, then apply it as the
        # default HTML color so plain text in rich cells follows the current theme.
        text_color = options.palette.text().color().name()

        available_width = options.rect.width() - 4
        # Rows are repainted on every frame the window animates: build each document once.
        cache = self.__dict__.setdefault("_doc_cache", {})
        key = (options.text, text_color, options.font.key(), available_width)
        doc = cache.get(key)
        if doc is None:
            doc = QTextDocument()
            doc.setDefaultFont(options.font)
            elided_html = self._elide_html(options.text, options.font, available_width)
            doc.setDefaultStyleSheet(f"body, div, span, td {{ color: {text_color}; }}")
            themed_html = f"<div style=\"color:{text_color};\">{elided_html}</div>"
            doc.setHtml(themed_html)
            if len(cache) > 1500:
                cache.clear()
            cache[key] = doc
        
        painter.save()
        painter.setClipRect(options.rect)
        
        options.text = "" # Don't let base DrawControl draw text
        # The tinted selection was already painted above; keep the style from
        # painting its own opaque highlight on top of it.
        options.state &= ~QStyle.StateFlag.State_Selected
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, options, painter, options.widget)
        
        painter.translate(options.rect.left(), options.rect.top())
        
        content_height = doc.size().height()
        dy = (options.rect.height() - content_height) / 2
        if dy < 0: dy = 0
        
        painter.translate(0, dy)
        
        painter.setPen(options.palette.text().color())

        doc.drawContents(painter)
        
        painter.restore()

    def _elide_html(self, html, font, width):
        if not html: return html
        doc = QTextDocument()
        doc.setDefaultFont(font)
        doc.setHtml(html)
        
        if doc.idealWidth() <= width:
            return html
            
        import re
        parts = re.split(r'(<[^>]+>)', html)
        
        # In decks: <span...>prefix</span>iconName
        for i in range(len(parts)-1, -1, -1):
            p = parts[i]
            if not p.startswith('<') and len(p.strip()) > 1:
                original = p
                # Simple loop is fine for typically short strings.
                for length in range(len(original)-1, 0, -1):
                    parts[i] = original[:length] + "..."
                    doc.setHtml("".join(parts))
                    if doc.idealWidth() <= width:
                        return "".join(parts)
                parts[i] = "..."
                break
        
        return html

    def sizeHint(self, option, index):
        options = QStyleOptionViewItem(option)
        self.initStyleOption(options, index)
        
        doc = QTextDocument()
        doc.setHtml(options.text)
        doc.setDefaultFont(options.font)
        
        return doc.size().toSize()
