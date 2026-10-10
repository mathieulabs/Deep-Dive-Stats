# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Reusable rich-text editor widget for the text_label pinned widget type."""
from __future__ import annotations

import html
import re

from aqt.theme import theme_manager
from aqt.qt import (
    QBrush,
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
    QShortcut,
    QTimer,
    QTextCharFormat,
    QTextCursor,
    QTextEdit,
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


def extract_html_body(editor: QTextEdit) -> str:
    full = editor.toHtml()
    match = re.search(r"<body[^>]*>(.*?)</body>", full, re.DOTALL | re.IGNORECASE)
    if not match:
        return editor.toPlainText()
    body = _normalize_template_markup(match.group(1).strip())
    para_match = None
    if body.lower().count("<p") == 1:
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
    VARIABLE_DESCRIPTIONS = {
        "total_time": "Formatted total study time",
        "reviews": "Number of reviews",
        "ret_all": "Overall retention",
        "ret_young": "Young-card retention",
        "ret_mat": "Mature-card retention",
        "streak": "Current streak",
        "active_days": "Active days count",
        "days_learned": "Share of days studied",
        "longest_streak": "Longest streak",
        "reviews_per_day": "Average reviews per day",
        "time_per_day": "Average study time per day",
        "ret_true": "True retention (young and mature)",
        "rev_young": "Young reviews",
        "rev_mature": "Mature reviews",
        "again": "Again count",
        "best_day": "Most reviews in one day",
        "cards_total": "Total cards",
        "cards_new": "New cards",
        "cards_learning": "Learning and relearning cards",
        "cards_young": "Young cards",
        "cards_mature": "Mature cards",
        "cards_suspended": "Suspended cards",
        "cards_buried": "Buried cards",
        "cards_deleted": "Deleted cards",
        "due_today": "Cards due today",
        "backlog": "Overdue cards",
        "avg_retrievability": "Average retrievability (FSRS)",
        "avg_stability": "Average stability (FSRS)",
        "lapses": "Failed review answers (young and mature)",
    }
    DECK_OVERRIDE_ORDER = ("current", "all", "deleted")

    def __init__(self, parent=None, theme_config=None):
        super().__init__(parent)
        self._theme_config = theme_config
        self._completion_mode = None
        self._completion_editor_prefix = ""
        self._completion_all_entries = []
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
        self._completion_search.setPlaceholderText("Filter suggestions...")
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
        self.setMinimumHeight(110)
        self.setMaximumHeight(190)
        self.setPlaceholderText("{reviews} cards in {total_time}")
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

    def keyPressEvent(self, event):
        key = event.key()

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
                action = menu.addAction(f"Animate changes of {{{hit.group('var')}}}")
                action.setCheckable(True)
                action.setChecked(not is_static)
                action.setToolTip("When off, the text does not fade when this value changes.")

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
            return [("s", "Seconds"), ("min", "Minutes"), ("h", "Hours"), ("d", "Days")]
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
        return [(token, self.VARIABLE_DESCRIPTIONS.get(token, token)) for token in AVAILABLE_VARS]

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
        self._completion_all_entries = entries
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
        self._completion_search.setPlaceholderText("Filter suggestions..." if mode != "deck" else "Filter decks...")
        self._refresh_completion_list()
        self._apply_popup_style()
        self._completion_popup.show()
        self._completion_popup.raise_()
        self._reposition_completion_popup()
        QTimer.singleShot(0, self._finalize_completion_popup_position)

    def _hide_completion(self) -> None:
        self._completion_mode = None
        self._completion_editor_prefix = ""
        self._completion_all_entries = []
        self._completion_search.blockSignals(True)
        self._completion_search.clear()
        self._completion_search.blockSignals(False)
        self._completion_search.hide()
        self._completion_popup.hide()

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

        frame_layout.addWidget(self._build_toolbar())
        self._editor = self._build_editor()
        frame_layout.addWidget(self._editor)

        root.addWidget(frame)
        root.addWidget(self._build_hint())

    def _build_toolbar(self) -> QWidget:
        container = QWidget(self)
        container.setObjectName("textLabelToolbar")
        row = QHBoxLayout(container)
        row.setContentsMargins(8, 8, 8, 8)
        row.setSpacing(6)

        def make_button(text="", *, checkable=True, tooltip="", object_name="textLabelToolButton"):
            button = QToolButton(container)
            button.setObjectName(object_name)
            button.setCheckable(checkable)
            button.setText(text)
            button.setToolTip(tooltip)
            button.setFixedSize(self.BUTTON_SIZE, self.BUTTON_SIZE)
            return button

        self._bold_btn = make_button("B", tooltip="Bold (Ctrl+B)")
        bold_font = self._bold_btn.font()
        bold_font.setBold(True)
        self._bold_btn.setFont(bold_font)

        self._italic_btn = make_button("I", tooltip="Italic (Ctrl+I)")
        italic_font = self._italic_btn.font()
        italic_font.setItalic(True)
        self._italic_btn.setFont(italic_font)

        self._underline_btn = make_button("U", tooltip="Underline (Ctrl+U)")
        underline_font = self._underline_btn.font()
        underline_font.setUnderline(True)
        self._underline_btn.setFont(underline_font)

        self._strike_btn = make_button("S", tooltip="Strikethrough")
        strike_font = self._strike_btn.font()
        strike_font.setStrikeOut(True)
        self._strike_btn.setFont(strike_font)
        self._shadow_btn = make_button("Sh", tooltip="Shadow / outline")
        self._shadow_btn.setFixedWidth(34)
        for button in (self._bold_btn, self._italic_btn, self._underline_btn, self._strike_btn, self._shadow_btn):
            row.addWidget(button)

        row.addWidget(self._build_toolbar_separator())

        self._font_combo = QFontComboBox(container)
        self._font_combo.setObjectName("textLabelFontCombo")
        self._font_combo.setFixedHeight(self.BUTTON_SIZE)
        self._font_combo.setMinimumWidth(160)
        self._font_combo.setToolTip("Font family")
        row.addWidget(self._font_combo)

        self._size_combo = QComboBox(container)
        self._size_combo.setObjectName("textLabelSizeCombo")
        self._size_combo.setFixedHeight(self.BUTTON_SIZE)
        self._size_combo.setFixedWidth(72)
        self._size_combo.setEditable(True)
        self._size_combo.setToolTip("Font size")
        for size in (8, 9, 10, 11, 12, 14, 16, 18, 20, 24, 28, 32, 36, 48, 72):
            self._size_combo.addItem(str(size), size)
        self._size_combo.setCurrentText("12")
        row.addWidget(self._size_combo)

        row.addWidget(self._build_toolbar_separator())

        self._placeholder_btn = make_button("{}", checkable=False, tooltip="Insert a live-value placeholder")
        self._placeholder_btn.setFixedWidth(36)
        row.addWidget(self._placeholder_btn)

        self._color_btn = make_button(checkable=False, tooltip="Text color", object_name="textLabelIconButton")
        self._reset_color_btn = make_button("Clear", checkable=False, tooltip="Clear text color", object_name="textLabelToolButton")
        self._reset_color_btn.setFixedWidth(52)
        row.addWidget(self._color_btn)
        row.addWidget(self._reset_color_btn)
        row.addStretch()
        return container

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

        editor.cursorPositionChanged.connect(self._sync_toolbar)
        editor.currentCharFormatChanged.connect(self._sync_toolbar)

        QShortcut(QKeySequence.StandardKey.Bold, editor, activated=self._bold_btn.toggle)
        QShortcut(QKeySequence.StandardKey.Italic, editor, activated=self._italic_btn.toggle)
        QShortcut(QKeySequence.StandardKey.Underline, editor, activated=self._underline_btn.toggle)
        return editor

    def _build_hint(self) -> QLabel:
        vars_text = "  ".join(f"{{{token}}}" for token in AVAILABLE_VARS)
        spans_text = "  ".join(token for token, _desc in get_available_span_tokens(self._theme_config))
        label = QLabel(
            "Type <code>{</code> to insert a variable, then use <code>:</code> inside the placeholder "
            "for a time span override and <code>@</code> for a deck override.<br>"
            f"<b>Variables</b>: {vars_text}<br>"
            f"<b>Time spans</b>: {spans_text} &nbsp;&nbsp;<i>Examples</i>: "
            "<code>{reviews:year}</code> &middot; <code>{reviews@current}</code> &middot; "
            "<code>{reviews:month@My Deck}</code><br>"
            "Use <code>|</code> to pick the unit of a duration "
            "(<code>s</code>, <code>min</code>, <code>h</code>, <code>d</code>): "
            "<code>{total_time|min}</code> &middot; <code>{avg_time|s}</code> &middot; "
            "<code>{time_per_day:month|min}</code><br>"
            "Add <code>~</code> before the closing brace so the text does not fade when that value "
            "changes: <code>{reviews~}</code> &middot; <code>{reviews:week|min~}</code>. "
            "Right click a variable to switch it."
        )
        label.setObjectName("textLabelHintLabel")
        label.setWordWrap(True)
        return label

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
        color = QColorDialog.getColor(QColor(self._current_color), self, "Text color")
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
            """
        )
        self._editor.set_theme_config(self._theme_config)
        self._refresh_toolbar_icons()
