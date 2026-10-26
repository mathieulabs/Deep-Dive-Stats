# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors

"""Layout edit mode for pinned widgets.

While the mode is on, every pinned card gets a dashed outline and a small handle
bar (themed like the pinned area). The bar has the quick moves (line up/down,
shift left/right), a menu for the structural moves (put on a new line, put in a
new box, move to the neighbouring box) and a Done button. Small cards only show
the menu button.

Model recap: a widget lives in a box (stat_box / chart_box / text_box), and in
that box on a line (row_num, 0 = first). Widgets with the same line number share
a line. Boxes are ordered by Pinned_Block_Order ("charts:0", "charts:1", ...).
"""

from aqt import mw
from aqt.qt import (
    QAction,
    QColor,
    QEvent,
    QFrame,
    QHBoxLayout,
    QLabel,
    QObject,
    QPainter,
    QPen,
    QRectF,
    Qt,
    QToolButton,
    sip,
)

from ..imports import Config, ConfigManager
from ..block_order import (
    BLOCK_CHARTS,
    BLOCK_STATS,
    BLOCK_TEXTS,
    charts_section_key,
    normalize_block_order,
    parse_section_key,
    stats_section_key,
    texts_section_key,
)
from ... import WidgetRegistry
from ......qss import set_qss
from .....logic.logger import log_swallowed

BAR_NAME = "pinned_edit_bar"
FRAME_NAME = "pinned_edit_frame"
COMPACT_WIDTH = 230
COMPACT_HEIGHT = 110

_FAMILY = {
    "stat": (BLOCK_STATS, stats_section_key, "stat_box"),
    "chart": (BLOCK_CHARTS, charts_section_key, "chart_box"),
    "text": (BLOCK_TEXTS, texts_section_key, "text_box"),
}


# state
def is_edit_mode(manager):
    return bool(getattr(manager, "_layout_edit_mode", False))


def _sync_escape_shortcut(manager, enabled):
    shortcut = getattr(manager, "_edit_escape_shortcut", None)
    if not enabled:
        if shortcut is not None:
            try:
                shortcut.setEnabled(False)
                shortcut.setParent(None)
                shortcut.deleteLater()
            except Exception:
                log_swallowed()
        manager._edit_escape_shortcut = None
        return
    if shortcut is not None:
        return
    try:
        from aqt.qt import QKeySequence, QShortcut

        overlay = getattr(manager, "_overlay", None)
        if overlay is None:
            return
        shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), overlay)
        shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        shortcut.activated.connect(lambda: set_edit_mode(manager, False))
        manager._edit_escape_shortcut = shortcut
    except Exception:
        log_swallowed()


def set_edit_mode(manager, enabled):
    manager._layout_edit_mode = bool(enabled)
    _sync_escape_shortcut(manager, bool(enabled))
    apply_edit_mode(manager)


# model helpers
def _nonneg(value):
    try:
        return max(0, int(value or 0))
    except Exception:
        return 0


def _family(widget_def):
    wtype = widget_def.get("type")
    if wtype == "stat_card":
        return "stat"
    if wtype == "text_label":
        return "text"
    return "chart"


def _box_of(widget_def):
    fam = _family(widget_def)
    if fam == "text":
        return _nonneg(widget_def.get("text_box", widget_def.get("chart_box", 0)))
    return _nonneg(widget_def.get(_FAMILY[fam][2], 0))


def _row_of(widget_def):
    return _nonneg(widget_def.get("row_num", 0))


def _defs():
    return list(WidgetRegistry.get_all())


def _def_by_id(widget_id):
    for d in _defs():
        if d.get("id") == widget_id:
            return d
    return None


def _group(defs, fam, box):
    return [d for d in defs if _family(d) == fam and _box_of(d) == box]


def _write_updates(updates_by_id):
    """Apply {widget_id: {key: value}} in one config write (None removes a key)."""
    if not updates_by_id:
        return
    cfg = WidgetRegistry._config()
    widgets = cfg.get(Config.PINNED_WIDGETS, [])
    for w in widgets:
        upd = updates_by_id.get(w.get("id"))
        if not upd:
            continue
        for key, value in upd.items():
            if value is None:
                w.pop(key, None)
            else:
                w[key] = value
    cfg[Config.PINNED_WIDGETS] = widgets
    WidgetRegistry._write(cfg)


def _config_manager(manager):
    cm = getattr(manager, "_config_manager", None)
    if cm is not None and hasattr(cm, "write_config_vals"):
        return cm
    return ConfigManager(mw)


def _section_order(manager, defs):
    cm = _config_manager(manager)
    stat_boxes = sorted({_box_of(d) for d in defs if _family(d) == "stat"})
    chart_boxes = sorted({_box_of(d) for d in defs if _family(d) == "chart"})
    text_boxes = sorted({_box_of(d) for d in defs if _family(d) == "text"})
    return normalize_block_order(
        (cm.config or {}).get(Config.PINNED_BLOCK_ORDER, None),
        stats_boxes=stat_boxes,
        chart_boxes=chart_boxes,
        text_boxes=text_boxes,
    )


def _refresh(manager):
    manager._last_state = None
    manager._last_widget_set = None
    manager.refresh(clear_cache=False)


def describe_position(widget_def, defs=None):
    defs = defs if defs is not None else _defs()
    fam = _family(widget_def)
    box = _box_of(widget_def)
    rows = sorted({_row_of(d) for d in _group(defs, fam, box)})
    line = rows.index(_row_of(widget_def)) + 1 if _row_of(widget_def) in rows else 1
    boxes = sorted({_box_of(d) for d in defs if _family(d) == fam})
    box_idx = boxes.index(box) + 1 if box in boxes else 1
    return f"Line {line} · Box {box_idx}"


# operations
def move_row(manager, widget_id, delta):
    cur = _def_by_id(widget_id) or {}
    row = _row_of(cur)
    new_row = max(0, row + int(delta))
    if new_row == row:
        return
    _write_updates({widget_id: {"row_num": new_row if new_row > 0 else None}})
    _refresh(manager)


def _tell(card, text):
    try:
        from aqt.qt import QCursor, QToolTip

        QToolTip.showText(QCursor.pos(), text, card)
    except Exception:
        log_swallowed()


def _relayout(live):
    parent = live.parentWidget()
    if parent is not None and parent.layout() is not None:
        parent.layout().invalidate()
        parent.layout().activate()
        parent.updateGeometry()
        parent.update()


def shift_column(manager, widget_id, delta):
    cur = _def_by_id(widget_id) or {}
    col = int(cur.get("col_offset", 0) or 0)
    new_col = col + int(delta)
    live = (getattr(manager, "_active_widgets", None) or {}).get(widget_id)
    if live is not None and hasattr(live.parentWidget() and live.parentWidget().layout(), "set_animate_moves"):
        # Try the shift without animation first: when the line is full the card
        # cannot move, and saving the offset anyway would only look broken.
        try:
            layout = live.parentWidget().layout()
            old_geo = live.geometry()
            layout.set_animate_moves(False)
            live._col_offset = int(new_col)
            _relayout(live)
            # Layout rounding can nudge a full line by a pixel or two: not a real move.
            moved = abs(live.geometry().x() - old_geo.x()) >= 20
            if not moved:
                live._col_offset = int(col)
                _relayout(live)
                _tell(live, "No room to shift on this line")
                return
            live.setGeometry(old_geo)
            # Enable move animations before the final relayout so the card glides.
            manager._schedule_chart_reflow_animation()
            _relayout(live)
            manager.sync_overlay()
        except Exception:
            log_swallowed()
    elif live is not None:
        live._col_offset = int(new_col)
    _write_updates({widget_id: {"col_offset": None if new_col == 0 else new_col}})
    _refresh(manager)


def can_move_down(widget_def, defs=None):
    """Down is pointless when the widget is alone on the last line of its box."""
    defs = defs if defs is not None else _defs()
    group = _group(defs, _family(widget_def), _box_of(widget_def))
    mates = [d for d in group if d.get("id") != widget_def.get("id") and _row_of(d) == _row_of(widget_def)]
    if mates:
        return True
    return any(_row_of(d) > _row_of(widget_def) for d in group)


def can_new_line(widget_def, defs=None):
    """A new line only makes sense when the widget currently shares its line."""
    defs = defs if defs is not None else _defs()
    mates = [
        d
        for d in _group(defs, _family(widget_def), _box_of(widget_def))
        if d.get("id") != widget_def.get("id") and _row_of(d) == _row_of(widget_def)
    ]
    return bool(mates)


def put_on_new_line(manager, widget_id, below):
    defs = _defs()
    cur = next((d for d in defs if d.get("id") == widget_id), None)
    if cur is None or not can_new_line(cur, defs):
        return
    row = _row_of(cur)
    updates = {}
    for other in _group(defs, _family(cur), _box_of(cur)):
        if other.get("id") == widget_id:
            continue
        r = _row_of(other)
        if (below and r > row) or ((not below) and r >= row):
            updates[other["id"]] = {"row_num": r + 1}
    updates[widget_id] = {"row_num": (row + 1) if below else (row if row > 0 else None), "col_offset": None}
    _write_updates(updates)
    _refresh(manager)


def can_new_box(widget_def, defs=None):
    defs = defs if defs is not None else _defs()
    mates = [
        d
        for d in _group(defs, _family(widget_def), _box_of(widget_def))
        if d.get("id") != widget_def.get("id")
    ]
    return bool(mates)


def _set_box_updates(fam, box, row):
    key = _FAMILY[fam][2]
    if fam == "text":
        box_value = int(box)
    else:
        box_value = None if int(box) == 0 else int(box)
    return {key: box_value, "row_num": row if row else None, "col_offset": None}


def put_in_new_box(manager, widget_id, below):
    defs = _defs()
    cur = next((d for d in defs if d.get("id") == widget_id), None)
    if cur is None or not can_new_box(cur, defs):
        return
    fam = _family(cur)
    _, key_fn, _ = _FAMILY[fam]
    cur_key = key_fn(_box_of(cur))
    order = _section_order(manager, defs)
    if cur_key not in order:
        order.append(cur_key)
    idx = order.index(cur_key)
    used = [_box_of(d) for d in defs if _family(d) == fam]
    new_id = (max(used) + 1) if used else 1
    new_key = key_fn(new_id)
    order.insert(idx + 1 if below else idx, new_key)
    _config_manager(manager).write_config_vals({Config.PINNED_BLOCK_ORDER: order})
    _write_updates({widget_id: _set_box_updates(fam, new_id, 0)})
    _refresh(manager)


def _neighbour_box(manager, widget_def, defs, step):
    fam = _family(widget_def)
    base, key_fn, _ = _FAMILY[fam]
    order = _section_order(manager, defs)
    cur_key = key_fn(_box_of(widget_def))
    if cur_key not in order:
        return None
    idx = order.index(cur_key)
    rng = range(idx + 1, len(order)) if step > 0 else range(idx - 1, -1, -1)
    for i in rng:
        b, box = parse_section_key(order[i])
        if b == base:
            return _nonneg(box)
    return None


def can_move_box(manager, widget_def, step, defs=None):
    defs = defs if defs is not None else _defs()
    return _neighbour_box(manager, widget_def, defs, step) is not None


def move_to_neighbour_box(manager, widget_id, step):
    defs = _defs()
    cur = next((d for d in defs if d.get("id") == widget_id), None)
    if cur is None:
        return
    target = _neighbour_box(manager, cur, defs, step)
    if target is None:
        return
    fam = _family(cur)
    group = _group(defs, fam, target)
    row = (max(_row_of(d) for d in group) + 1) if group else 0
    _write_updates({widget_id: _set_box_updates(fam, target, row)})
    _refresh(manager)


def reset_position(manager, widget_id):
    _write_updates({widget_id: {"row_num": None, "col_offset": None}})
    live = (getattr(manager, "_active_widgets", None) or {}).get(widget_id)
    if live is not None:
        try:
            live._col_offset = 0
        except Exception:
            log_swallowed()
    _refresh(manager)


# theme
_DARK_COLORS = {
    "surface": "#27272a",
    "element": "#3f3f46",
    "text": "#f4f4f5",
    "muted": "#a1a1aa",
    "accent": "#71717a",
    "border": "#52525b",
    "ok": "#22c55e",
}
_LIGHT_COLORS = {
    "surface": "#f5f5f5",
    "element": "#e4e4e7",
    "text": "#18181b",
    "muted": "#71717a",
    "accent": "#3b82f6",
    "border": "#a1a1aa",
    "ok": "#16a34a",
}


def _colors(manager, cfg=None):
    is_dark = True
    try:
        from ....chart_utils.theme import is_night_mode, ThemeContext

        is_dark = bool(is_night_mode(ThemeContext.PINNED))
    except Exception:
        log_swallowed()
    out = dict(_DARK_COLORS if is_dark else _LIGHT_COLORS)
    try:
        from ....chart_utils.theme import ThemeContext, get_context_theme_config
        from .....ui.theme import get_theme_palette

        base = cfg if isinstance(cfg, dict) else (_config_manager(manager).config or {})
        # is_dark matters for the native theme: without it there is no palette at all
        # and the bar stayed dark on Anki's light mode.
        palette = get_theme_palette(get_context_theme_config(ThemeContext.PINNED, base), is_dark=is_dark) or {}
        mapping = {
            "surface": "bg_surface",
            "element": "bg_element",
            "text": "text_primary",
            "muted": "text_secondary",
            "accent": "accent",
            "border": "border_strong",
            "ok": "success",
        }
        for k, pk in mapping.items():
            if palette.get(pk):
                out[k] = str(palette[pk])
    except Exception:
        log_swallowed()
    return out


def _hover_bg(c):
    """Tint of the text colour: clearly visible on both light and dark bars."""
    col = QColor(c["text"])
    return f"rgba({col.red()},{col.green()},{col.blue()},0.16)"


def _bar_qss(c):
    return (
        f"QFrame#{BAR_NAME} {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 8px; }}"
        f"QFrame#{BAR_NAME} QToolButton {{ background: transparent; color: {c['text']}; border: none;"
        " border-radius: 5px; font-size: 12px; min-width: 20px; max-width: 20px;"
        " min-height: 20px; max-height: 20px; padding: 0; }"
        f"QFrame#{BAR_NAME} QToolButton:hover {{ background: {_hover_bg(c)}; }}"
        f"QFrame#{BAR_NAME} QToolButton#pinned_edit_done {{ color: {c['ok']}; }}"
        f"QFrame#{BAR_NAME} QLabel#pinned_edit_pos {{ color: {c['muted']}; font-size: 11px; padding: 0 4px; background: transparent; }}"
    )


# widgets
class _OutlineFrame(QFrame):
    """Dashed outline over the card; ignores the mouse so dragging still works."""

    def __init__(self, card, color):
        super().__init__(card)
        self.setObjectName(FRAME_NAME)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self._color = QColor(color)

    def set_color(self, color):
        self._color = QColor(color)
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(self._color, 1.2, Qt.PenStyle.DashLine)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(self.rect()).adjusted(1.5, 1.5, -1.5, -1.5), 8, 8)
        p.end()


class _Positioner(QObject):
    """Keeps the outline and the bar in place on their card."""

    def __init__(self, card, bar, outline):
        super().__init__(card)
        self._card = card
        self._bar = bar
        self._outline = outline
        card.installEventFilter(self)
        self.place()

    def place(self):
        if sip.isdeleted(self._outline) or sip.isdeleted(self._bar):
            # Edit mode ended: the outline and the bar are gone, so is the need to place them.
            self._card.removeEventFilter(self)
            self.deleteLater()
            return
        try:
            self._outline.setGeometry(self._card.rect())
            self._outline.raise_()
            self._bar.adjustSize()
            x = max(2, self._card.width() - self._bar.width() - 5)
            self._bar.move(x, 4)
            self._bar.raise_()
        except Exception:
            log_swallowed()

    def eventFilter(self, obj, event):
        etype = event.type()
        if etype == QEvent.Type.Resize and getattr(self._bar, "_colors", None):
            # A card that became small (or large) switches between the full and compact bar.
            _style_bar(self._bar, self._bar._colors, self._card)
        if etype in (QEvent.Type.Resize, QEvent.Type.Show, QEvent.Type.LayoutRequest):
            self.place()
        return False


def _tool_button(parent, text, tooltip, callback, name=None):
    btn = QToolButton(parent)
    btn.setText(text)
    btn.setToolTip(tooltip)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setAutoRaise(True)
    if name:
        btn.setObjectName(name)
    btn.clicked.connect(lambda _=False: callback(btn))
    return btn


def _show_menu(manager, card, widget_id, button):
    from .....ui import StyledMenu

    defs = _defs()
    cur = next((d for d in defs if d.get("id") == widget_id), None)
    if cur is None:
        return
    menu = StyledMenu(card)
    menu.setProperty("deepdivestats_theme_context", "pinned")
    menu.setProperty("deepdivestats_ignore_forced_dark_theme", True)
    try:
        menu.setProperty("deepdivestats_config_override", dict(_config_manager(manager).config or {}))
        menu._apply_theme_style()
    except Exception:
        log_swallowed()

    def add(text, fn, enabled=True, tip=None):
        act = QAction(text, menu)
        act.setEnabled(bool(enabled))
        if tip:
            act.setToolTip(tip)
        act.triggered.connect(lambda _=False: fn())
        menu.addAction(act)
        return act

    head = QAction(describe_position(cur, defs), menu)
    head.setEnabled(False)
    menu.addAction(head)
    menu.addSeparator()

    new_line_ok = can_new_line(cur, defs)
    share_tip = "Available when this widget shares its line with another one"
    add("\u2191  Line: move up", lambda: move_row(manager, widget_id, -1), _row_of(cur) > 0)
    add("\u2193  Line: move down", lambda: move_row(manager, widget_id, 1), can_move_down(cur, defs))
    add("\uff0b  Line: put alone on a new line above", lambda: put_on_new_line(manager, widget_id, False), new_line_ok, share_tip)
    add("\uff0b  Line: put alone on a new line below", lambda: put_on_new_line(manager, widget_id, True), new_line_ok, share_tip)
    if _family(cur) != "stat":
        menu.addSeparator()
        add("\u2190  Shift left on the line", lambda: shift_column(manager, widget_id, -1))
        add("\u2192  Shift right on the line", lambda: shift_column(manager, widget_id, 1))
    menu.addSeparator()
    new_box_ok = can_new_box(cur, defs)
    box_tip = "Available when this box has other widgets"
    add("\u25a3  Box: put in a new box above", lambda: put_in_new_box(manager, widget_id, False), new_box_ok, box_tip)
    add("\u25a3  Box: put in a new box below", lambda: put_in_new_box(manager, widget_id, True), new_box_ok, box_tip)
    add("\u25a3  Box: move to the previous box", lambda: move_to_neighbour_box(manager, widget_id, -1), can_move_box(manager, cur, -1, defs))
    add("\u25a3  Box: move to the next box", lambda: move_to_neighbour_box(manager, widget_id, 1), can_move_box(manager, cur, 1, defs))
    menu.addSeparator()
    add(
        "↺  Reset position",
        lambda: reset_position(manager, widget_id),
        _row_of(cur) != 0 or int(cur.get("col_offset", 0) or 0) != 0,
    )
    add("\u2713  Done editing layout (Esc)", lambda: set_edit_mode(manager, False))
    menu.exec(button.mapToGlobal(button.rect().bottomLeft()))


def _is_compact(card):
    return card.width() < COMPACT_WIDTH or card.height() < COMPACT_HEIGHT


def _build_bar(manager, card, widget_id, colors):
    bar = QFrame(card)
    bar.setObjectName(BAR_NAME)
    bar.setCursor(Qt.CursorShape.ArrowCursor)
    lay = QHBoxLayout(bar)
    lay.setContentsMargins(2, 2, 2, 2)
    lay.setSpacing(1)
    pos_label = QLabel("", bar)
    pos_label.setObjectName("pinned_edit_pos")
    lay.addWidget(pos_label)
    quick = [
        _tool_button(bar, "↑", "Move up a line", lambda _b: move_row(manager, widget_id, -1)),
        _tool_button(bar, "↓", "Move down a line", lambda _b: move_row(manager, widget_id, 1)),
        _tool_button(bar, "←", "Shift left", lambda _b: shift_column(manager, widget_id, -1)),
        _tool_button(bar, "→", "Shift right", lambda _b: shift_column(manager, widget_id, 1)),
    ]
    for b in quick:
        lay.addWidget(b)
    lay.addWidget(
        _tool_button(
            bar,
            "…",
            "New line, new box, other box, reset",
            lambda b: _show_menu(manager, card, widget_id, b),
            name="pinned_edit_more",
        )
    )
    done = _tool_button(bar, "✓", "Done editing layout", lambda _b: set_edit_mode(manager, False), name="pinned_edit_done")
    lay.addWidget(done)
    bar._quick_buttons = quick
    bar._pos_label = pos_label
    bar._shift_buttons = quick[2:]
    bar._done_button = done
    outline = _OutlineFrame(card, colors["muted"])
    bar._outline = outline
    bar._positioner = _Positioner(card, bar, outline)
    return bar


def _style_bar(bar, colors, card):
    token = (tuple(sorted(colors.items())), _is_compact(card))
    if getattr(bar, "_style_token", None) == token:
        return
    bar._style_token = token
    bar._colors = colors
    set_qss(bar, _bar_qss(colors))
    bar._outline.set_color(colors["muted"])
    compact = _is_compact(card)
    for b in bar._quick_buttons:
        b.setVisible(not compact)
    for b in bar._shift_buttons:
        # Stat cards live in a container that has no per-card column shift.
        b.setVisible((not compact) and not getattr(bar, "_is_stat", False))
    bar._pos_label.setVisible(not compact)
    bar._done_button.setVisible(not compact)
    bar._positioner.place()


def apply_edit_mode(manager, cfg=None):
    """Show, restyle or hide the edit handles on every live pinned card."""
    enabled = is_edit_mode(manager)
    colors = _colors(manager, cfg) if enabled else None
    all_defs = _defs() if enabled else []
    defs_by_id = {d.get("id"): d for d in all_defs}
    known = set(defs_by_id)
    for widget_id, card in list((getattr(manager, "_active_widgets", None) or {}).items()):
        try:
            if card is None or sip.isdeleted(card):
                continue
            existing = card.findChild(QFrame, BAR_NAME, Qt.FindChildOption.FindDirectChildrenOnly)
            if not enabled or widget_id not in known:
                if existing is not None:
                    outline = getattr(existing, "_outline", None)
                    for w in (existing, outline):
                        if w is not None:
                            w.hide()
                            w.setParent(None)
                            w.deleteLater()
                continue
            if existing is None:
                existing = _build_bar(manager, card, widget_id, colors)
            wdef = defs_by_id.get(widget_id) or {}
            existing._is_stat = _family(wdef) == "stat"
            existing._pos_label.setText(describe_position(wdef, all_defs).replace("Line ", "L").replace(" \u00b7 Box ", " \u00b7 B"))
            existing._pos_label.setToolTip(describe_position(wdef, all_defs))
            existing._style_token = None
            existing.show()
            existing._outline.show()
            _style_bar(existing, colors, card)
        except Exception:
            log_swallowed()
