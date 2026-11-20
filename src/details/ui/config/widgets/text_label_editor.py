# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Reusable rich-text editor widget for the text_label pinned widget type."""
from __future__ import annotations

import html
import re

from aqt.theme import theme_manager
from aqt.qt import (
    QAbstractItemView,
    QApplication,
    QBrush,
    QEvent,
    QColor,
    QColorDialog,
    QComboBox,
    QFont,
    QFontComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QKeySequence,
    QMenu,
    QShortcut,
    QTimer,
    QTextBlockFormat,
    QTextCharFormat,
    QTextCursor,
    QTextDocument,
    QTextDocumentFragment,
    QTextEdit,
    QTextFormat,
    QTextLength,
    QTextListFormat,
    QToolButton,
    QPen,
    QSyntaxHighlighter,
    Qt,
    QVBoxLayout,
    QWidget,
)

from ...theme import get_theme_effective_is_dark, get_theme_palette
from ...theme.icons import get_svg_icon
from ....widgets.pinned.widget_factory.builders.text_label import (
    AVAILABLE_VARS,
    DECK_OVERRIDE_SYMBOL,
    _TEMPLATE_RE,
    get_available_span_tokens,
    get_available_deck_override_tokens,
)
from .....qss import set_qss
from ....logic.logger import log_swallowed
from .....i18n import tr, N_, tr_name
from .....web_ui.text_editor import VARIABLE_DESCRIPTIONS


def extract_html_body(editor: QTextEdit) -> str:
    full = editor.toHtml()
    match = re.search(r"<body[^>]*>(.*?)</body>", full, re.DOTALL | re.IGNORECASE)
    if not match:
        return editor.toPlainText()
    body = _normalize_template_markup(match.group(1).strip())
    para_match = None
    # one paragraph: its words only, unless it is centered / right aligned (the <p> carries that)
    if body.lower().count("<p") == 1 and not re.search(r"<p[^>]*\balign=", body, re.IGNORECASE):
        para_match = re.match(r"^<p[^>]*>(.*)</p>\s*$", body, re.DOTALL | re.IGNORECASE)
    return para_match.group(1).strip() if para_match else body


def load_template_into_editor(editor: QTextEdit, template: str) -> None:
    template = _normalize_template_markup(template)
    if template.strip().startswith("<") or re.search(r"</?(?:p|span|br|strong|em|u|s|div)\b", template, re.IGNORECASE):
        editor.setHtml(template)
    else:
        editor.setPlainText(template)


def _normalize_template_markup(template: str) -> str:
    text = str(template or "")
    if not text:
        return ""

    normalized = html.unescape(text)
    stripped = normalized.strip()

    if not stripped.startswith("<") and "</p>" in stripped:
        first_close = stripped.find("</p>")
        prefix = stripped[:first_close]
        suffix = stripped[first_close + 4:]
        if suffix.startswith("</p>"):
            suffix = suffix[4:]
        stripped = f"<p>{prefix}</p>{suffix}"

    return stripped


# the help under the editor: unfolded or not, as it was last left (for the session)
_HELP_OPEN = [True]

# ---- Markdown in the text editor: typed (turned into formatting as it is typed) or pasted ----
HEADING_SIZES = {1: 22, 2: 18, 3: 15}  # point sizes of the titles (the editor's normal text: 12)
NORMAL_SIZE = 12
_MD_INLINE = (
    (re.compile(r"\*\*([^*\n]+)\*\*$"), "bold"),
    (re.compile(r"(?<![*\w])\*([^*\s][^*\n]*)\*$"), "italic"),  # not the first star of a closing "**"
    (re.compile(r"~~([^~\n]+)~~$"), "strike"),
)
_MD_BLOCK = re.compile(r"(#{1,3}|[-*+]|1[.)])")
_MD_RULE = re.compile(r"(?:-{3,}|\*{3,}|_{3,})")
_MD_PASTED = re.compile(r"(?m)^(?:#{1,6} |[-*+] |\d+[.)] |> |(?:-{3,}|\*{3,})\s*$)|\*\*[^*\n]+\*\*|~~[^~\n]+~~")


def looks_like_markdown(text: str) -> bool:
    return bool(_MD_PASTED.search(text or ""))


def _hex_to_rgba(hex_color: str, alpha: float) -> str:
    color = QColor(hex_color)
    if not color.isValid():
        return hex_color
    return f"rgba({color.red()}, {color.green()}, {color.blue()}, {max(0.0, min(1.0, alpha)):.3f})"


def _resolve_theme_tokens(theme_config=None) -> dict:
    try:
        is_dark = get_theme_effective_is_dark(theme_config or {})
    except Exception:
        is_dark = bool(theme_manager.get_night_mode())

    if is_dark:
        tokens = {
            "is_dark": True,
            "bg_root": "#18181b",
            "bg_surface": "#27272a",
            "bg_input": "#3f3f46",
            "border_subtle": "#3f3f46",
            "border_strong": "#52525b",
            "text_primary": "#f4f4f5",
            "text_secondary": "#a1a1aa",
            "accent": "#60a5fa",
            "accent_hover": "#3b82f6",
        }
    else:
        tokens = {
            "is_dark": False,
            "bg_root": "#ffffff",
            "bg_surface": "#f4f4f5",
            "bg_input": "#ffffff",
            "border_subtle": "#e4e4e7",
            "border_strong": "#d4d4d8",
            "text_primary": "#18181b",
            "text_secondary": "#71717a",
            "accent": "#3b82f6",
            "accent_hover": "#2563eb",
        }

    try:
        palette = get_theme_palette(theme_config or {}) or {}
    except Exception:
        palette = {}

    tokens["bg_root"] = palette.get("bg_root", tokens["bg_root"])
    tokens["bg_surface"] = palette.get("bg_surface", tokens["bg_surface"])
    tokens["bg_input"] = palette.get("bg_element", tokens["bg_input"])
    tokens["border_subtle"] = palette.get("border_subtle", tokens["border_subtle"])
    tokens["border_strong"] = palette.get("border_strong", tokens["border_strong"])
    tokens["text_primary"] = palette.get("text_primary", tokens["text_primary"])
    tokens["text_secondary"] = palette.get("text_secondary", tokens["text_secondary"])
    tokens["accent"] = palette.get("accent", tokens["accent"])
    tokens["accent_hover"] = palette.get("accent_hover", tokens["accent_hover"])
    return tokens


class _PlaceholderHighlighter(QSyntaxHighlighter):
    """Highlights {variable:span@deck} placeholders in the editor.

    Unknown variable names get a red wavy underline. Display only: the saved HTML
    is unchanged.
    """

    def __init__(self, document, theme_config=None):
        super().__init__(document)
        self._known = set(AVAILABLE_VARS)
        self._ok_fmt = QTextCharFormat()
        self._bad_fmt = QTextCharFormat()
        self.set_theme_config(theme_config, rehighlight=False)

    def set_theme_config(self, theme_config, rehighlight=True):
        tokens = _resolve_theme_tokens(theme_config)
        accent = QColor(tokens["accent"])
        tint = QColor(accent)
        tint.setAlphaF(0.30 if tokens.get("is_dark") else 0.18)
        ok = QTextCharFormat()
        ok.setBackground(QBrush(tint))
        bad = QTextCharFormat()
        bad.setUnderlineStyle(QTextCharFormat.UnderlineStyle.WaveUnderline)
        bad.setUnderlineColor(QColor("#ef4444"))
        self._ok_fmt = ok
        self._bad_fmt = bad
        if rehighlight:
            self.rehighlight()

    def highlightBlock(self, text):
        for match in _TEMPLATE_RE.finditer(text or ""):
            start, end = match.start(), match.end()
            fmt = self._ok_fmt if match.group("var") in self._known else self._bad_fmt
            self.setFormat(start, end - start, fmt)


class TemplateTextEdit(QTextEdit):
    SEARCH_FIELD_THRESHOLD = 9
    VARIABLE_DESCRIPTIONS = VARIABLE_DESCRIPTIONS  # (web_ui/text_editor.py, shared with the web editor)
    DECK_OVERRIDE_ORDER = ("current", "all", "deleted")

    def __init__(self, parent=None, theme_config=None):
        super().__init__(parent)
        self._theme_config = theme_config
        self._completion_mode = None
        self._completion_editor_prefix = ""
        self._completion_popup = QFrame(
            self,
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.NoDropShadowWindowHint,
        )
        self._completion_popup.setObjectName("textLabelSuggestionPopup")
        self._completion_popup.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._completion_popup.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self._completion_popup.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        popup_layout = QVBoxLayout(self._completion_popup)
        popup_layout.setContentsMargins(0, 0, 0, 0)
        popup_layout.setSpacing(0)

        self._completion_surface = QFrame(self._completion_popup)
        self._completion_surface.setObjectName("textLabelSuggestionSurface")
        surface_layout = QVBoxLayout(self._completion_surface)
        surface_layout.setContentsMargins(6, 6, 6, 6)
        surface_layout.setSpacing(6)

        self._completion_search = QLineEdit(self._completion_surface)
        self._completion_search.setObjectName("textLabelSuggestionSearch")
        self._completion_search.setPlaceholderText(tr("Filter suggestions..."))
        self._completion_search.setClearButtonEnabled(True)
        self._completion_search.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self._completion_search.textChanged.connect(self._refresh_completion_list)
        self._completion_search.hide()
        surface_layout.addWidget(self._completion_search)

        self._completion_list = QListWidget(self._completion_surface)
        self._completion_list.setObjectName("textLabelSuggestionList")
        self._completion_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._completion_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._completion_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self._completion_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._completion_list.itemClicked.connect(self._accept_completion)
        self._completion_list.itemActivated.connect(self._accept_completion)
        surface_layout.addWidget(self._completion_list)
        popup_layout.addWidget(self._completion_surface)

        self.setAcceptRichText(True)
        self.setMinimumHeight(110)  # no maximum: the room the help leaves when hidden is the text's
        self.setPlaceholderText(tr("{reviews} cards in {total_time}"))
        self.setObjectName("textLabelTextEdit")

        self._placeholder_highlighter = _PlaceholderHighlighter(self.document(), theme_config)

        self.cursorPositionChanged.connect(self._refresh_completion_context)
        self.document().contentsChanged.connect(self._refresh_completion_context)
        self.verticalScrollBar().valueChanged.connect(self._reposition_completion_popup)
        self.horizontalScrollBar().valueChanged.connect(self._reposition_completion_popup)

    def set_theme_config(self, theme_config) -> None:
        self._theme_config = theme_config
        self._apply_popup_style()
        try:
            self._placeholder_highlighter.set_theme_config(theme_config)
        except Exception:
            log_swallowed()

    def insert_template_placeholder(self) -> None:
        cursor = self.textCursor()
        if cursor.hasSelection():
            cursor.insertText("{" + cursor.selectedText() + "}")
            self.setTextCursor(cursor)
            self._hide_completion()
            return

        cursor.insertText("{}")
        cursor.movePosition(QTextCursor.MoveOperation.Left)
        self.setTextCursor(cursor)
        self._show_completion("variable", "")

    # ---- paragraphs: titles, lists, alignment, lines (the toolbar's second row and the Markdown typed) ----
    def _blocks(self, cursor=None):
        """The blocks of the selection (or the one of the cursor)."""
        c = cursor or self.textCursor()
        doc = self.document()
        block, last = doc.findBlock(c.selectionStart()), doc.findBlock(c.selectionEnd())
        out = [block]
        while block.isValid() and block != last:
            block = block.next()
            out.append(block)
        return out

    @staticmethod
    def _title_format(level: int) -> QTextCharFormat:
        fmt = QTextCharFormat()
        fmt.setFontWeight(QFont.Weight.Bold if level else QFont.Weight.Normal)
        fmt.setFontPointSize(HEADING_SIZES.get(level, NORMAL_SIZE))
        return fmt

    def set_heading(self, level: int, cursor=None) -> None:
        """Title 1 to 3 (0: normal text) for the paragraphs of the selection: bold, larger, an <hN> in the page."""
        c = cursor or self.textCursor()
        c.beginEditBlock()
        for block in self._blocks(c):
            bc = QTextCursor(block)
            bf = block.blockFormat()
            bf.setHeadingLevel(level)
            bc.setBlockFormat(bf)
            bc.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)
            bc.mergeCharFormat(self._title_format(level))
        c.endEditBlock()
        self.mergeCurrentCharFormat(self._title_format(level))  # what is typed next is in the title's style

    def toggle_list(self, style, cursor=None, force=False) -> None:
        """A bulleted or numbered list for the paragraphs of the selection; clicked again: back to paragraphs."""
        c = cursor or self.textCursor()
        current = c.currentList()
        c.beginEditBlock()
        if current is not None and current.format().style() == style and not force:
            for block in self._blocks(c):
                lst = block.textList()
                if lst is not None:
                    lst.remove(block)
                    bf = block.blockFormat()
                    bf.setIndent(0)
                    QTextCursor(block).setBlockFormat(bf)
        elif current is not None:
            fmt = current.format()
            fmt.setStyle(style)
            current.setFormat(fmt)
        else:
            fmt = QTextListFormat()
            fmt.setStyle(style)
            c.createList(fmt)
        c.endEditBlock()

    def insert_rule(self, cursor=None) -> None:
        """A horizontal line (<hr> in the page) as its own paragraph, the cursor in a new paragraph under it."""
        c = cursor or self.textCursor()
        c.beginEditBlock()
        if c.block().text().strip():
            c.movePosition(QTextCursor.MoveOperation.EndOfBlock)
            c.insertBlock(QTextBlockFormat(), self._title_format(0))
        rule = QTextBlockFormat()
        rule.setProperty(QTextFormat.Property.BlockTrailingHorizontalRulerWidth,
                         QTextLength(QTextLength.Type.PercentageLength, 100))
        c.setBlockFormat(rule)
        c.insertBlock(QTextBlockFormat(), self._title_format(0))
        c.endEditBlock()
        self.setTextCursor(c)

    def _markdown_after_char(self, typed: str) -> bool:
        """Markdown as it is typed: "# " to "### " a title, "- " / "* " a bulleted list, "1. " a numbered list,
        **bold**, *italic*, ~~strike~~. Ctrl+Z gives the characters back."""
        c = self.textCursor()
        if c.hasSelection() or not typed or self._current_placeholder_context() is not None:
            return False
        block = c.block()
        before = block.text()[: c.positionInBlock()]
        if typed == " ":
            m = _MD_BLOCK.fullmatch(before[:-1])
            if not m or block.textList() is not None:
                return False
            token = m.group(1)
            c.beginEditBlock()
            c.movePosition(QTextCursor.MoveOperation.StartOfBlock)
            c.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor, len(before))
            c.removeSelectedText()
            if token.startswith("#"):
                self.set_heading(len(token), c)
            elif token[0] in "-*+":
                self.toggle_list(QTextListFormat.Style.ListDisc, c, force=True)
            else:
                self.toggle_list(QTextListFormat.Style.ListDecimal, c, force=True)
            c.endEditBlock()
            return True
        if typed not in "*~":
            return False
        for rx, kind in _MD_INLINE:
            m = rx.search(before)
            if not m:
                continue
            base = QTextCharFormat(self.currentCharFormat())
            fmt = QTextCharFormat(base)
            if kind == "bold":
                fmt.setFontWeight(QFont.Weight.Bold)
            elif kind == "italic":
                fmt.setFontItalic(True)
            else:
                fmt.setFontStrikeOut(True)
            end = c.position()
            c.beginEditBlock()
            c.setPosition(end - len(m.group(0)))
            c.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
            c.removeSelectedText()
            c.insertText(m.group(1), fmt)
            c.endEditBlock()
            self.setTextCursor(c)
            self.setCurrentCharFormat(base)  # what follows is not bold / italic / struck
            return True
        return False

    def _paragraph_keys(self, event) -> bool:
        """Enter: "---" becomes a line; an empty list item leaves the list; after a title, normal text again."""
        if event.key() not in (Qt.Key.Key_Return, Qt.Key.Key_Enter) or event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            return False
        c = self.textCursor()
        if c.hasSelection():
            return False
        block = c.block()
        if _MD_RULE.fullmatch(block.text().strip()) and c.atBlockEnd():
            c.beginEditBlock()
            c.movePosition(QTextCursor.MoveOperation.StartOfBlock)
            c.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)
            c.removeSelectedText()
            c.endEditBlock()
            self.insert_rule(c)
            return True
        if block.textList() is not None and not block.text().strip():
            self.toggle_list(block.textList().format().style(), c)
            return True
        if block.blockFormat().headingLevel() and c.atBlockEnd():
            c.beginEditBlock()
            bf = QTextBlockFormat(block.blockFormat())
            bf.setHeadingLevel(0)
            c.insertBlock(bf, self._title_format(0))
            c.endEditBlock()
            self.setTextCursor(c)
            self.setCurrentCharFormat(self._title_format(0))
            return True
        return False

    def insertFromMimeData(self, source):
        """Markdown pasted (titles, lists, **bold**...): pasted formatted, as Qt reads Markdown."""
        try:
            if source.hasText() and not source.hasHtml() and looks_like_markdown(source.text()):
                doc = QTextDocument()
                doc.setMarkdown(source.text())
                self.textCursor().insertFragment(QTextDocumentFragment(doc))
                self.ensureCursorVisible()
                return
        except Exception:
            log_swallowed()
        super().insertFromMimeData(source)

    def keyPressEvent(self, event):
        key = event.key()

        if not self._completion_popup.isVisible() and self._paragraph_keys(event):
            return

        if self._completion_popup.isVisible():
            if key in (Qt.Key.Key_Down, Qt.Key.Key_Up, Qt.Key.Key_PageDown, Qt.Key.Key_PageUp):
                self._move_completion_selection(key)
                return
            if key == Qt.Key.Key_Tab:
                self._accept_current_completion()
                return
            if key == Qt.Key.Key_Escape:
                self._hide_completion()
                return

        if key == Qt.Key.Key_BraceRight and self._char_after_cursor() == "}":
            cursor = self.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.Right)
            self.setTextCursor(cursor)
            self._hide_completion()
            return

        if key == Qt.Key.Key_BraceLeft and not (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            self.insert_template_placeholder()
            return

        if key == Qt.Key.Key_Colon and self._can_start_span_completion():
            cursor = self.textCursor()
            if self._char_after_cursor() == "}":
                cursor.insertText(":")
            else:
                cursor.insertText(":}")
                cursor.movePosition(QTextCursor.MoveOperation.Left)
            self.setTextCursor(cursor)
            self._show_completion("span", "")
            return

        if event.text() == "|" and self._can_start_unit_completion():
            cursor = self.textCursor()
            if self._char_after_cursor() == "}":
                cursor.insertText("|")
            else:
                cursor.insertText("|}")
                cursor.movePosition(QTextCursor.MoveOperation.Left)
            self.setTextCursor(cursor)
            self._show_completion("unit", "")
            return

        if event.text() == DECK_OVERRIDE_SYMBOL and self._can_start_deck_completion():
            cursor = self.textCursor()
            if self._char_after_cursor() == "}":
                cursor.insertText(DECK_OVERRIDE_SYMBOL)
            else:
                cursor.insertText(f"{DECK_OVERRIDE_SYMBOL}}}")
                cursor.movePosition(QTextCursor.MoveOperation.Left)
            self.setTextCursor(cursor)
            self._show_completion("deck", "")
            return

        if key == Qt.Key.Key_Backspace and self._handle_auto_pair_backspace():
            return

        super().keyPressEvent(event)
        try:
            if not (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
                self._markdown_after_char(event.text())
        except Exception:
            log_swallowed()
        self._refresh_completion_context()

    def contextMenuEvent(self, event):
        menu = self.createStandardContextMenu()
        try:
            pos = self.cursorForPosition(event.pos()).position()
            text = self.toPlainText()
            hit = None
            for m in _TEMPLATE_RE.finditer(text):
                if m.start() <= pos <= m.end():
                    hit = m
                    break
            if hit is not None:
                is_static = bool(hit.group("static"))
                menu.addSeparator()
                action = menu.addAction(tr("Animate changes of {name}", name="{" + hit.group("var") + "}"))
                action.setCheckable(True)
                action.setChecked(not is_static)
                action.setToolTip(tr("When off, the text does not fade when this value changes."))

                def toggle(_checked, m=hit, static=is_static):
                    raw = m.group(0)
                    new_raw = raw[:-2] + "}" if static else raw[:-1] + "~}"
                    cursor = self.textCursor()
                    cursor.setPosition(m.start())
                    cursor.setPosition(m.end(), QTextCursor.MoveMode.KeepAnchor)
                    cursor.insertText(new_raw)
                    self.setTextCursor(cursor)

                action.triggered.connect(toggle)
        except Exception:
            log_swallowed()
        menu.exec(event.globalPos())
        menu.deleteLater()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reposition_completion_popup()

    def hideEvent(self, event):
        self._hide_completion()
        super().hideEvent(event)

    def _handle_auto_pair_backspace(self) -> bool:
        cursor = self.textCursor()
        if cursor.hasSelection():
            return False
        pos = cursor.position()
        text = self.toPlainText()
        if pos <= 0 or pos >= len(text):
            return False
        prev_char = text[pos - 1]
        next_char = text[pos]
        if (prev_char, next_char) not in {("{", "}"), (":", "}")}:
            return False

        cursor.beginEditBlock()
        cursor.deletePreviousChar()
        cursor.deleteChar()
        cursor.endEditBlock()
        self.setTextCursor(cursor)
        self._hide_completion()
        return True

    def _can_start_span_completion(self) -> bool:
        ctx = self._current_placeholder_context()
        return bool(ctx and ctx["mode"] == "variable" and ctx["prefix"])

    def _can_start_unit_completion(self) -> bool:
        ctx = self._current_placeholder_context()
        return bool(ctx and ctx["mode"] in ("variable", "span", "deck") and ctx["prefix"])

    def _can_start_deck_completion(self) -> bool:
        ctx = self._current_placeholder_context()
        return bool(ctx and ctx["mode"] in ("variable", "span") and ctx["prefix"])

    def _current_placeholder_context(self) -> dict | None:
        text = self.toPlainText()
        pos = self.textCursor().position()
        open_pos = text.rfind("{", 0, pos)
        close_pos = text.rfind("}", 0, pos)
        if open_pos < 0 or close_pos > open_pos:
            return None

        next_close = text.find("}", open_pos + 1)
        if next_close != -1 and pos > next_close:
            return None

        inner = text[open_pos + 1:pos]
        if any(ch in inner for ch in "\n\r\t{}"):
            return None

        if "|" in inner:
            before_unit, unit_prefix = inner.split("|", 1)
            if not re.fullmatch(r"[A-Za-z0-9_]+(?::[^\n\r\t{}@|]*)?(?:@[^\n\r\t{}|]*)?", before_unit):
                return None
            if any(ch in unit_prefix for ch in "\n\r\t{}|@"):
                return None
            unit_start = open_pos + 2 + len(before_unit)
            unit_end = text.find("}", unit_start)
            if unit_end == -1:
                unit_end = pos
            return {
                "mode": "unit",
                "prefix": unit_prefix,
                "anchor": unit_start,
                "replace_end": unit_end,
            }

        if DECK_OVERRIDE_SYMBOL in inner:
            before_deck, deck_prefix = inner.split(DECK_OVERRIDE_SYMBOL, 1)
            if ":" in before_deck:
                var_part, span_part = before_deck.split(":", 1)
                if not var_part or not re.fullmatch(r"[A-Za-z0-9_]+", var_part):
                    return None
                if any(ch in span_part for ch in "\n\r\t{}@"):
                    return None
            elif not re.fullmatch(r"[A-Za-z0-9_]+", before_deck):
                return None

            deck_start = open_pos + 2 + len(before_deck)
            deck_end = text.find("}", deck_start)
            if deck_end == -1:
                deck_end = pos
            return {
                "mode": "deck",
                "prefix": deck_prefix,
                "anchor": deck_start,
                "replace_end": deck_end,
            }

        if ":" in inner:
            var_part, span_prefix = inner.split(":", 1)
            if not var_part or not re.fullmatch(r"[A-Za-z0-9_]+", var_part):
                return None
            if any(ch in span_prefix for ch in "\n\r\t{}@"):
                return None
            span_start = open_pos + 2 + len(var_part)
            next_sep_candidates = [idx for idx in (text.find(DECK_OVERRIDE_SYMBOL, span_start), text.find("}", span_start)) if idx != -1]
            span_end = min(next_sep_candidates) if next_sep_candidates else pos
            if span_end == -1:
                span_end = pos
            return {
                "mode": "span",
                "prefix": span_prefix,
                "anchor": span_start,
                "replace_end": span_end,
            }

        if not re.fullmatch(r"[A-Za-z0-9_]*", inner):
            return None
        var_start = open_pos + 1
        next_sep_candidates = [idx for idx in (text.find(":", var_start), text.find("}", var_start)) if idx != -1]
        var_end = min(next_sep_candidates) if next_sep_candidates else pos
        return {
            "mode": "variable",
            "prefix": inner,
            "anchor": var_start,
            "replace_end": var_end,
        }

    def _refresh_completion_context(self, *_args) -> None:
        ctx = self._current_placeholder_context()
        if not ctx:
            self._hide_completion()
            return
        self._show_completion(ctx["mode"], ctx["prefix"])

    def _completion_entries(self, mode: str) -> list[tuple[str, str]]:
        if mode == "span":
            return get_available_span_tokens(self._theme_config)
        if mode == "unit":
            return [("s", tr("Seconds")), ("min", tr("Minutes")), ("h", tr("Hours")), ("d", tr("Days"))]
        if mode == "deck":
            entries = get_available_deck_override_tokens()
            ordered = []
            rest = []
            for token, description in entries:
                if token in self.DECK_OVERRIDE_ORDER:
                    ordered.append((token, description))
                else:
                    rest.append((token, description))
            return ordered + rest
        return [(token, tr_name(self.VARIABLE_DESCRIPTIONS.get(token, token))) for token in AVAILABLE_VARS]

    def _filter_completion_entries(self, mode: str, prefix: str) -> list[tuple[str, str]]:
        entries = self._completion_entries(mode)
        if not prefix:
            return entries

        prefix_lower = prefix.lower()
        exact = []
        starts = []
        contains = []
        rest = []
        for token, description in entries:
            haystack = f"{token} {description}".lower()
            token_lower = token.lower()
            if token_lower == prefix_lower:
                exact.append((token, description))
            elif token_lower.startswith(prefix_lower):
                starts.append((token, description))
            elif prefix_lower in haystack:
                contains.append((token, description))
            else:
                rest.append((token, description))
        return exact + starts + contains + rest

    def _apply_search_filter(self, entries: list[tuple[str, str]], search_text: str) -> list[tuple[str, str]]:
        query = str(search_text or "").strip().lower()
        if not query:
            return entries
        starts = []
        contains = []
        for token, description in entries:
            haystack = f"{token} {description}".lower()
            if token.lower().startswith(query):
                starts.append((token, description))
            elif query in haystack:
                contains.append((token, description))
        return starts + contains

    def _refresh_completion_list(self) -> None:
        base_entries = self._filter_completion_entries(self._completion_mode, self._completion_editor_prefix)
        entries = self._apply_search_filter(base_entries, self._completion_search.text())
        self._completion_list.clear()
        for token, description in entries:
            item = QListWidgetItem(f"{token}  -  {description}")
            item.setData(Qt.ItemDataRole.UserRole, token)
            item.setToolTip(description)
            self._completion_list.addItem(item)
        if entries:
            self._completion_list.setCurrentRow(0)
        self._resize_completion_popup()
        self._reposition_completion_popup()

    def _show_completion(self, mode: str, prefix: str) -> None:
        entries = self._filter_completion_entries(mode, prefix)
        if not entries:
            self._hide_completion()
            return

        if self._completion_mode != mode or self._completion_editor_prefix != prefix:
            self._completion_search.blockSignals(True)
            self._completion_search.clear()
            self._completion_search.blockSignals(False)

        self._completion_mode = mode
        self._completion_editor_prefix = prefix
        show_search = len(entries) >= self.SEARCH_FIELD_THRESHOLD
        self._completion_search.setVisible(show_search)
        self._completion_search.setPlaceholderText(tr("Filter suggestions...") if mode != "deck" else tr("Filter decks..."))
        self._refresh_completion_list()
        self._apply_popup_style()
        self._completion_popup.show()
        self._completion_popup.raise_()
        self._watch_while_open(True)
        self._reposition_completion_popup()
        QTimer.singleShot(0, self._finalize_completion_popup_position)

    def _hide_completion(self) -> None:
        self._completion_mode = None
        self._completion_editor_prefix = ""
        self._completion_search.blockSignals(True)
        self._completion_search.clear()
        self._completion_search.blockSignals(False)
        self._completion_search.hide()
        self._completion_popup.hide()
        self._watch_while_open(False)

    def _watch_while_open(self, on: bool) -> None:
        """While the list is open: the mouse wheel over it scrolls it even though it never
        takes the focus (the editor keeps it), and it follows the window when that moves."""
        if on == getattr(self, "_watching", False):
            return
        app = QApplication.instance()
        if app is None:
            return
        self._watching = on
        if on:
            app.installEventFilter(self)
        else:
            app.removeEventFilter(self)

    def eventFilter(self, obj, event):
        if getattr(self, "_watching", False) and isinstance(obj, QWidget):
            try:
                kind = event.type()
                popup = self._completion_popup
                if kind == QEvent.Type.Wheel and popup.isVisible():
                    if obj is not popup and not popup.isAncestorOf(obj):
                        if popup.frameGeometry().contains(event.globalPosition().toPoint()):
                            self._scroll_completion(event.angleDelta().y())
                            return True
                elif kind in (QEvent.Type.Move, QEvent.Type.Resize) and obj is self.window():
                    QTimer.singleShot(0, self._reposition_completion_popup)
            except RuntimeError:
                pass
        return super().eventFilter(obj, event)

    def _scroll_completion(self, delta_y: int) -> None:
        bar = self._completion_list.verticalScrollBar()
        lines = QApplication.wheelScrollLines() * delta_y / 120.0
        if self._completion_list.verticalScrollMode() == QAbstractItemView.ScrollMode.ScrollPerPixel:
            lines *= max(1, self._completion_list.sizeHintForRow(0))
        bar.setValue(bar.value() - int(round(lines)))

    def _finalize_completion_popup_position(self) -> None:
        if not self._completion_popup.isVisible():
            return
        self._resize_completion_popup()
        self._reposition_completion_popup()

    def _resize_completion_popup(self) -> None:
        count = self._completion_list.count()
        search_h = self._completion_search.sizeHint().height() + 6 if self._completion_search.isVisible() else 0
        if count <= 0:
            self._completion_popup.resize(340, max(54, search_h + 18))
            return
        row_height = max(28, self._completion_list.sizeHintForRow(0))
        height = min(260, (row_height * count) + 12 + search_h)
        self._completion_popup.resize(340, height)

    def _reposition_completion_popup(self, *_args) -> None:
        if not self._completion_popup.isVisible():
            return
        rect = self.cursorRect()
        global_pos = self.viewport().mapToGlobal(rect.bottomLeft())
        popup_w = self._completion_popup.width()
        popup_h = self._completion_popup.height()
        screen = self.window().screen() if self.window() else None
        if screen is None:
            screen = self.screen()
        geo = screen.availableGeometry() if screen is not None else None

        x = global_pos.x()
        y = global_pos.y() + 6
        if geo is not None:
            if x + popup_w > geo.right() - 8:
                x = max(geo.left() + 8, geo.right() - popup_w - 8)
            if y + popup_h > geo.bottom() - 8:
                y = max(geo.top() + 8, self.viewport().mapToGlobal(rect.topLeft()).y() - popup_h - 6)

        self._completion_popup.move(x, y)

    def _move_completion_selection(self, key) -> None:
        count = self._completion_list.count()
        if count <= 0:
            return
        row = max(0, self._completion_list.currentRow())
        if key == Qt.Key.Key_PageDown:
            row += 6
        elif key == Qt.Key.Key_PageUp:
            row -= 6
        elif key == Qt.Key.Key_Down:
            row += 1
        elif key == Qt.Key.Key_Up:
            row -= 1
        row = max(0, min(count - 1, row))
        self._completion_list.setCurrentRow(row)

    def _accept_current_completion(self) -> None:
        item = self._completion_list.currentItem()
        if item is not None:
            self._accept_completion(item)

    def _accept_completion(self, item) -> None:
        token = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        if not token:
            return

        ctx = self._current_placeholder_context()
        if not ctx or ctx["mode"] != self._completion_mode:
            self._hide_completion()
            return

        cursor = self.textCursor()
        cursor.beginEditBlock()
        cursor.setPosition(ctx["anchor"])
        cursor.setPosition(ctx.get("replace_end", self.textCursor().position()), QTextCursor.MoveMode.KeepAnchor)
        cursor.insertText(str(token))

        next_char = self._char_at_position(cursor.position())
        if ctx["mode"] in ("span", "deck", "unit"):
            if next_char == "}":
                cursor.movePosition(QTextCursor.MoveOperation.Right)
            else:
                cursor.insertText("}")

        self.setTextCursor(cursor)
        cursor.endEditBlock()
        self._hide_completion()

    def _char_at_position(self, pos: int) -> str:
        text = self.toPlainText()
        if 0 <= pos < len(text):
            return text[pos]
        return ""

    def _char_after_cursor(self) -> str:
        return self._char_at_position(self.textCursor().position())

    def _apply_popup_style(self) -> None:
        tokens = _resolve_theme_tokens(self._theme_config)
        accent_soft = _hex_to_rgba(tokens["accent"], 0.14)
        accent_border = _hex_to_rgba(tokens["accent"], 0.38)
        set_qss(self._completion_popup,
            f"""
            QFrame#textLabelSuggestionPopup {{
                background: transparent;
                border: none;
            }}
            QFrame#textLabelSuggestionSurface {{
                background: {tokens["bg_surface"]};
                border: 1px solid {tokens["border_strong"]};
                border-radius: 10px;
            }}
            QListWidget#textLabelSuggestionList {{
                background: {tokens["bg_surface"]};
                border: none;
                outline: 0;
                color: {tokens["text_primary"]};
                border-radius: 8px;
            }}
            QLineEdit#textLabelSuggestionSearch {{
                background: {tokens["bg_input"]};
                color: {tokens["text_primary"]};
                border: 1px solid {tokens["border_strong"]};
                border-radius: 7px;
                padding: 6px 9px;
                selection-background-color: {tokens["accent"]};
            }}
            QLineEdit#textLabelSuggestionSearch:focus {{
                border-color: {tokens["accent"]};
            }}
            QListWidget#textLabelSuggestionList::item {{
                padding: 7px 10px;
                margin: 1px 0;
                border-radius: 6px;
                color: {tokens["text_secondary"]};
            }}
            QListWidget#textLabelSuggestionList::item:selected {{
                background: {accent_soft};
                color: {tokens["text_primary"]};
                border: 1px solid {accent_border};
            }}
            QListWidget#textLabelSuggestionList::item:hover:!selected {{
                background: {tokens["bg_input"]};
                color: {tokens["text_primary"]};
            }}
            """
        )


class TextLabelEditor(QWidget):
    BUTTON_SIZE = 28

    def __init__(self, parent=None, theme_config=None):
        super().__init__(parent)
        self._theme_config = theme_config
        self._current_color = "#ffffff"
        self._setup_ui()
        self._apply_theme_styles()

    def get_template(self) -> str:
        return extract_html_body(self._editor)

    def set_template(self, template: str) -> None:
        self._editor.blockSignals(True)
        load_template_into_editor(self._editor, template)
        self._editor.blockSignals(False)
        self._editor._hide_completion()
        self._sync_toolbar()

    @property
    def editor(self) -> QTextEdit:
        return self._editor

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        frame = QFrame(self)
        frame.setObjectName("textLabelEditorFrame")
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(10, 10, 10, 10)
        frame_layout.setSpacing(8)

        from aqt.qt import QSizePolicy

        toolbar = self._build_toolbar()
        toolbar.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)  # its two rows, never taller
        frame_layout.addWidget(toolbar)
        self._editor = self._build_editor()
        frame_layout.addWidget(self._editor, 1)

        root.addWidget(frame, 1)
        root.addWidget(self._build_hint())

    def _build_toolbar(self) -> QWidget:
        container = QWidget(self)
        container.setObjectName("textLabelToolbar")
        rows = QVBoxLayout(container)
        rows.setContentsMargins(8, 8, 8, 8)
        rows.setSpacing(6)
        row = QHBoxLayout()
        row.setSpacing(6)
        rows.addLayout(row)

        def make_button(text="", *, checkable=True, tooltip="", object_name="textLabelToolButton"):
            button = QToolButton(container)
            button.setObjectName(object_name)
            button.setCheckable(checkable)
            button.setText(text)
            button.setToolTip(tooltip)
            button.setFixedSize(self.BUTTON_SIZE, self.BUTTON_SIZE)
            return button

        self._bold_btn = make_button("B", tooltip=tr("Bold (Ctrl+B)"))
        bold_font = self._bold_btn.font()
        bold_font.setBold(True)
        self._bold_btn.setFont(bold_font)

        self._italic_btn = make_button("I", tooltip=tr("Italic (Ctrl+I)"))
        italic_font = self._italic_btn.font()
        italic_font.setItalic(True)
        self._italic_btn.setFont(italic_font)

        self._underline_btn = make_button("U", tooltip=tr("Underline (Ctrl+U)"))
        underline_font = self._underline_btn.font()
        underline_font.setUnderline(True)
        self._underline_btn.setFont(underline_font)

        self._strike_btn = make_button("S", tooltip=tr("Strikethrough"))
        strike_font = self._strike_btn.font()
        strike_font.setStrikeOut(True)
        self._strike_btn.setFont(strike_font)
        self._shadow_btn = make_button("Sh", tooltip=tr("Shadow / outline"))
        self._shadow_btn.setFixedWidth(34)
        for button in (self._bold_btn, self._italic_btn, self._underline_btn, self._strike_btn, self._shadow_btn):
            row.addWidget(button)

        row.addWidget(self._build_toolbar_separator())

        self._font_combo = QFontComboBox(container)
        self._font_combo.setObjectName("textLabelFontCombo")
        self._font_combo.setFixedHeight(self.BUTTON_SIZE)
        self._font_combo.setMinimumWidth(160)
        self._font_combo.setToolTip(tr("Font family"))
        row.addWidget(self._font_combo)

        self._size_combo = QComboBox(container)
        self._size_combo.setObjectName("textLabelSizeCombo")
        self._size_combo.setFixedHeight(self.BUTTON_SIZE)
        self._size_combo.setFixedWidth(72)
        self._size_combo.setEditable(True)
        self._size_combo.setToolTip(tr("Font size"))
        for size in (8, 9, 10, 11, 12, 14, 16, 18, 20, 24, 28, 32, 36, 48, 72):
            self._size_combo.addItem(str(size), size)
        self._size_combo.setCurrentText("12")
        row.addWidget(self._size_combo)

        row.addWidget(self._build_toolbar_separator())

        self._placeholder_btn = make_button("{}", checkable=False, tooltip=tr("Insert a live-value placeholder"))
        self._placeholder_btn.setFixedWidth(36)
        row.addWidget(self._placeholder_btn)

        self._color_btn = make_button(checkable=False, tooltip=tr("Text color"), object_name="textLabelIconButton")
        self._reset_color_btn = make_button(tr("Clear"), checkable=False, tooltip=tr("Clear text color"), object_name="textLabelToolButton")
        self._reset_color_btn.setFixedWidth(52)
        row.addWidget(self._color_btn)
        row.addWidget(self._reset_color_btn)
        row.addStretch()

        # second row: the paragraphs (titles, lists, alignment, a line); Markdown typed does the same (# , - , 1. , ---)
        row2 = QHBoxLayout()
        row2.setSpacing(6)
        rows.addLayout(row2)
        self._heading_btn = QToolButton(container)
        self._heading_btn.setObjectName("textLabelToolButton")
        self._heading_btn.setFixedHeight(self.BUTTON_SIZE)
        self._heading_btn.setMinimumWidth(104)
        self._heading_btn.setToolTip(tr("Paragraph style (or type # , ## , ### then a space)"))
        self._heading_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        heading_menu = QMenu(self._heading_btn)
        for level, label in ((0, N_("Normal text")), (1, N_("Title 1")), (2, N_("Title 2")), (3, N_("Title 3"))):
            act = heading_menu.addAction(tr_name(label))
            act.triggered.connect(lambda _c=False, n=level: self._set_heading(n))
        self._heading_btn.setMenu(heading_menu)
        self._heading_btn.setText(tr("Normal text"))
        row2.addWidget(self._heading_btn)
        row2.addWidget(self._build_toolbar_separator())

        self._bullets_btn = make_button(tooltip=tr("Bulleted list (or type - then a space)"), object_name="textLabelToolButton")
        self._numbers_btn = make_button(tooltip=tr("Numbered list (or type 1. then a space)"), object_name="textLabelToolButton")
        row2.addWidget(self._bullets_btn)
        row2.addWidget(self._numbers_btn)
        row2.addWidget(self._build_toolbar_separator())

        self._align_btns = {}
        for flag, tip in ((Qt.AlignmentFlag.AlignLeft, N_("Align left")), (Qt.AlignmentFlag.AlignHCenter, N_("Center")),
                          (Qt.AlignmentFlag.AlignRight, N_("Align right"))):
            btn = make_button(tooltip=tr_name(tip), object_name="textLabelToolButton")
            btn.clicked.connect(lambda _c=False, f=flag: self._set_alignment(f))
            self._align_btns[flag] = btn
            row2.addWidget(btn)
        row2.addWidget(self._build_toolbar_separator())

        self._rule_btn = make_button(checkable=False, tooltip=tr("Horizontal line (or type --- then Enter)"),
                                     object_name="textLabelToolButton")
        row2.addWidget(self._rule_btn)
        row2.addStretch()
        return container

    def _set_heading(self, level: int) -> None:
        self._editor.set_heading(level)
        self._editor.setFocus()
        self._sync_toolbar()

    def _toggle_list(self, style) -> None:
        self._editor.toggle_list(style)
        self._editor.setFocus()
        self._sync_toolbar()

    def _set_alignment(self, flag) -> None:
        self._editor.setAlignment(flag)
        self._editor.setFocus()
        self._sync_toolbar()

    def _insert_rule(self) -> None:
        self._editor.insert_rule()
        self._editor.setFocus()

    def _build_toolbar_separator(self) -> QFrame:
        sep = QFrame(self)
        sep.setObjectName("textLabelToolbarSeparator")
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFixedHeight(self.BUTTON_SIZE)
        return sep

    def _build_editor(self) -> TemplateTextEdit:
        editor = TemplateTextEdit(self, theme_config=self._theme_config)
        editor.setFrameShape(QFrame.Shape.NoFrame)

        self._bold_btn.toggled.connect(self._toggle_bold)
        self._italic_btn.toggled.connect(self._toggle_italic)
        self._underline_btn.toggled.connect(self._toggle_underline)
        self._strike_btn.toggled.connect(self._toggle_strike)
        self._shadow_btn.toggled.connect(self._toggle_shadow)
        self._font_combo.currentFontChanged.connect(self._on_font_family_changed)
        self._size_combo.currentTextChanged.connect(self._on_size_changed)
        self._placeholder_btn.clicked.connect(editor.insert_template_placeholder)
        self._color_btn.clicked.connect(self._pick_color)
        self._reset_color_btn.clicked.connect(self._reset_color)
        self._bullets_btn.clicked.connect(lambda: self._toggle_list(QTextListFormat.Style.ListDisc))
        self._numbers_btn.clicked.connect(lambda: self._toggle_list(QTextListFormat.Style.ListDecimal))
        self._rule_btn.clicked.connect(self._insert_rule)

        editor.cursorPositionChanged.connect(self._sync_toolbar)
        editor.currentCharFormatChanged.connect(self._sync_toolbar)

        QShortcut(QKeySequence.StandardKey.Bold, editor, activated=self._bold_btn.toggle)
        QShortcut(QKeySequence.StandardKey.Italic, editor, activated=self._italic_btn.toggle)
        QShortcut(QKeySequence.StandardKey.Underline, editor, activated=self._underline_btn.toggle)
        return editor

    def _build_hint(self) -> QWidget:
        """The help under the editor (a variable, its time span and deck, the variables, a duration's unit, "~", the
        Markdown), in a box open at first; "Hide help" folds it away, "Help" brings it back, as it was left."""
        def code(text):
            return f"<code>{text}</code>"

        dot = " &middot; "
        box = QWidget(self)
        lay = QVBoxLayout(box)
        lay.setContentsMargins(2, 0, 2, 0)
        lay.setSpacing(4)

        top = QHBoxLayout()
        top.addStretch(1)
        toggle = QToolButton(box)
        toggle.setObjectName("textLabelHelpButton")
        toggle.setCheckable(True)
        toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        top.addWidget(toggle, 0, Qt.AlignmentFlag.AlignTop)
        lay.addLayout(top)

        vars_text = " ".join(code(f"{{{token}}}") for token in AVAILABLE_VARS)
        spans_text = dot.join(token for token, _desc in get_available_span_tokens(self._theme_config))

        def part(text):
            return f'<p style="margin:0 0 7px 0;">{text}</p>'

        body = QLabel(
            part(tr("Type {open} to insert a variable, then use {colon} inside the placeholder for a time "
                    "span override and {at} for a deck override.", open=code("{"), colon=code(":"), at=code("@")))
            + part(tr("<b>Variables</b>: {list}", list=vars_text))
            + part(tr("<b>Time spans</b>: {list}", list=spans_text) + "<br>"
                   + tr("<i>Examples</i>: {list}", list=dot.join(
                       code(t) for t in ("{reviews:year}", "{reviews@current}", "{reviews:month@My Deck}"))))
            + part(tr("Use {bar} to pick the unit of a duration ({units}): {examples}",
                      bar=code("|"), units=", ".join(code(u) for u in ("s", "min", "h", "d")),
                      examples=dot.join(code(t) for t in ("{total_time|min}", "{avg_time|s}", "{time_per_day:month|min}"))))
            + part(tr("Add {tilde} before the closing brace so the text does not fade when that value "
                      "changes: {examples}. Right click a variable to switch it.",
                      tilde=code("~"), examples=dot.join(code(t) for t in ("{reviews~}", "{reviews:week|min~}"))))
            + part(tr("<b>Markdown</b> turns into formatting as you type it (Ctrl+Z gives the characters back): {examples}",
                      examples=dot.join(code(html.escape(t)) for t in
                                        ("# ", "## ", "- ", "1. ", "**bold**", "*italic*", "~~strike~~", "---")))),
            box)
        body.setObjectName("textLabelHelpBody")
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(body)

        def show(on):
            _HELP_OPEN[0] = bool(on)
            body.setVisible(bool(on))
            toggle.setText(tr("Hide help") + " ▴" if on else tr("Help") + " ▾")

        toggle.setChecked(_HELP_OPEN[0])
        show(_HELP_OPEN[0])
        toggle.toggled.connect(show)
        return box

    def _merge(self, fmt: QTextCharFormat) -> None:
        self._editor.mergeCurrentCharFormat(fmt)

    def _toggle_bold(self, checked: bool) -> None:
        fmt = QTextCharFormat()
        fmt.setFontWeight(QFont.Weight.Bold if checked else QFont.Weight.Normal)
        self._merge(fmt)

    def _toggle_italic(self, checked: bool) -> None:
        fmt = QTextCharFormat()
        fmt.setFontItalic(checked)
        self._merge(fmt)

    def _toggle_underline(self, checked: bool) -> None:
        fmt = QTextCharFormat()
        fmt.setFontUnderline(checked)
        self._merge(fmt)

    def _toggle_strike(self, checked: bool) -> None:
        fmt = QTextCharFormat()
        fmt.setFontStrikeOut(checked)
        self._merge(fmt)

    def _shadow_pen_for_format(self, fmt: QTextCharFormat | None = None) -> QPen:
        if fmt is None:
            fmt = self._editor.currentCharFormat()

        fg = fmt.foreground()
        if fg.style() != Qt.BrushStyle.NoBrush and fg.color().isValid():
            base = fg.color()
        else:
            base = QColor(_resolve_theme_tokens(self._theme_config)["text_primary"])

        shadow = QColor("#000000" if base.lightness() >= 150 else "#ffffff")
        shadow.setAlpha(140)
        return QPen(shadow, 1.15)

    def _has_shadow(self, fmt: QTextCharFormat | None = None) -> bool:
        if fmt is None:
            fmt = self._editor.currentCharFormat()
        try:
            pen = fmt.textOutline()
        except Exception:
            return False
        return bool(pen.style() != Qt.PenStyle.NoPen and pen.color().isValid() and pen.widthF() > 0)

    def _toggle_shadow(self, checked: bool) -> None:
        fmt = QTextCharFormat()
        if checked:
            fmt.setTextOutline(self._shadow_pen_for_format())
        else:
            fmt.setTextOutline(QPen(Qt.PenStyle.NoPen))
        self._merge(fmt)

    def _on_font_family_changed(self, font: QFont) -> None:
        current = self._editor.currentFont()
        current.setFamily(font.family())
        self._editor.setCurrentFont(current)

    def _on_size_changed(self, text: str) -> None:
        try:
            point_size = float(text)
        except ValueError:
            return
        if point_size <= 0:
            return
        fmt = QTextCharFormat()
        fmt.setFontPointSize(point_size)
        self._merge(fmt)

    def _pick_color(self) -> None:
        color = QColorDialog.getColor(QColor(self._current_color), self, tr("Text color"))
        if not color.isValid():
            return
        self._apply_color_indicator(color.name())
        fmt = QTextCharFormat()
        fmt.setForeground(color)
        if self._has_shadow():
            fmt.setTextOutline(self._shadow_pen_for_format(fmt))
        self._merge(fmt)

    def _reset_color(self) -> None:
        fmt = QTextCharFormat()
        fmt.setForeground(QBrush(Qt.BrushStyle.NoBrush))
        if self._has_shadow():
            fmt.setTextOutline(self._shadow_pen_for_format(fmt))
        self._editor.textCursor().mergeCharFormat(fmt)
        self._merge(fmt)
        self._apply_color_indicator(self._get_default_icon_color())

    def _apply_color_indicator(self, hex_color: str) -> None:
        self._current_color = hex_color
        self._refresh_toolbar_icons()

    def _get_default_icon_color(self) -> str:
        return _resolve_theme_tokens(self._theme_config)["text_secondary"]

    def _refresh_toolbar_icons(self) -> None:
        icon_color = self._current_color or self._get_default_icon_color()
        self._color_btn.setIcon(get_svg_icon("palette", color=icon_color, size=14, context_ref=self))
        self._color_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        plain = _resolve_theme_tokens(self._theme_config)["text_primary"]
        for btn, name in ((self._bullets_btn, "list"), (self._numbers_btn, "list-ordered"), (self._rule_btn, "separator"),
                          (self._align_btns[Qt.AlignmentFlag.AlignLeft], "align-left"),
                          (self._align_btns[Qt.AlignmentFlag.AlignHCenter], "align-center"),
                          (self._align_btns[Qt.AlignmentFlag.AlignRight], "align-right")):
            btn.setIcon(get_svg_icon(name, color=plain, size=16, context_ref=self))
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self._reset_color_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)

    def _sync_toolbar(self, *_args) -> None:
        fmt = self._editor.currentCharFormat()
        states = (
            (self._bold_btn, lambda f: f.fontWeight() >= QFont.Weight.Bold),
            (self._italic_btn, lambda f: f.fontItalic()),
            (self._underline_btn, lambda f: f.fontUnderline()),
            (self._strike_btn, lambda f: f.fontStrikeOut()),
            (self._shadow_btn, self._has_shadow),
        )
        for button, resolver in states:
            button.blockSignals(True)
            button.setChecked(resolver(fmt))
            button.blockSignals(False)

        families = fmt.fontFamilies()
        if families:
            self._font_combo.blockSignals(True)
            self._font_combo.setCurrentFont(QFont(families[0]))
            self._font_combo.blockSignals(False)

        point_size = fmt.fontPointSize()
        if point_size > 0:
            self._size_combo.blockSignals(True)
            self._size_combo.setCurrentText(str(int(point_size)))
            self._size_combo.blockSignals(False)

        fg = fmt.foreground()
        if fg.style() != Qt.BrushStyle.NoBrush and fg.color().isValid():
            self._apply_color_indicator(fg.color().name())
        else:
            self._apply_color_indicator(self._get_default_icon_color())

        # the paragraph's own buttons: its title level, its list, its alignment
        cursor = self._editor.textCursor()
        level = cursor.blockFormat().headingLevel()
        self._heading_btn.setText(tr_name({1: "Title 1", 2: "Title 2", 3: "Title 3"}.get(level, "Normal text")))
        lst = cursor.currentList()
        style = lst.format().style() if lst is not None else None
        for btn, on in ((self._bullets_btn, style == QTextListFormat.Style.ListDisc),
                        (self._numbers_btn, style == QTextListFormat.Style.ListDecimal)):
            btn.blockSignals(True)
            btn.setChecked(on)
            btn.blockSignals(False)
        align = self._editor.alignment()
        current = (Qt.AlignmentFlag.AlignHCenter if align & Qt.AlignmentFlag.AlignHCenter
                   else Qt.AlignmentFlag.AlignRight if align & Qt.AlignmentFlag.AlignRight else Qt.AlignmentFlag.AlignLeft)
        for flag, btn in self._align_btns.items():
            btn.blockSignals(True)
            btn.setChecked(flag == current)
            btn.blockSignals(False)

    def _apply_theme_styles(self) -> None:
        tokens = _resolve_theme_tokens(self._theme_config)
        accent_soft = _hex_to_rgba(tokens["accent"], 0.14)
        accent_strong = _hex_to_rgba(tokens["accent"], 0.28)
        subtle_fill = _hex_to_rgba(tokens["text_secondary"], 0.08 if tokens["is_dark"] else 0.05)

        set_qss(self,
            f"""
            QFrame#textLabelEditorFrame {{
                background: {tokens["bg_surface"]};
                border: 1px solid {tokens["border_subtle"]};
                border-radius: 10px;
            }}
            QWidget#textLabelToolbar {{
                background: {tokens["bg_root"]};
                border: 1px solid {tokens["border_subtle"]};
                border-radius: 10px;
            }}
            QFrame#textLabelToolbarSeparator {{
                color: {tokens["border_subtle"]};
                background: {tokens["border_subtle"]};
                max-width: 1px;
                min-width: 1px;
                border: none;
            }}
            QToolButton#textLabelToolButton,
            QToolButton#textLabelIconButton {{
                background: transparent;
                border: 1px solid transparent;
                border-radius: 8px;
                color: {tokens["text_primary"]};
                padding: 0;
            }}
            QToolButton#textLabelToolButton:hover,
            QToolButton#textLabelIconButton:hover {{
                background: {subtle_fill};
                border-color: {tokens["border_subtle"]};
            }}
            QToolButton#textLabelToolButton:checked {{
                background: {accent_soft};
                border-color: {accent_strong};
                color: {tokens["text_primary"]};
            }}
            QTextEdit#textLabelTextEdit {{
                background: {tokens["bg_input"]};
                color: {tokens["text_primary"]};
                border: 1px solid {tokens["border_strong"]};
                border-radius: 10px;
                padding: 10px 12px;
                selection-background-color: {tokens["accent"]};
            }}
            QTextEdit#textLabelTextEdit:focus {{
                border-color: {tokens["accent"]};
            }}
            QLabel#textLabelHintLabel {{
                color: {tokens["text_secondary"]};
                font-size: 11px;
                line-height: 1.4;
            }}
            QLabel#textLabelHelpBody {{
                color: {tokens["text_secondary"]};
                font-size: 11px;
                background: {subtle_fill};
                border: 1px solid {tokens["border_subtle"]};
                border-radius: 8px;
                padding: 9px 11px 2px 11px;
            }}
            QToolButton#textLabelHelpButton {{
                background: transparent;
                border: none;
                color: {tokens["accent"]};
                font-size: 11px;
                font-weight: 600;
                padding: 0 2px;
            }}
            QToolButton#textLabelHelpButton:hover {{
                text-decoration: underline;
            }}
            """
        )
        self._editor.set_theme_config(self._theme_config)
        self._refresh_toolbar_icons()
