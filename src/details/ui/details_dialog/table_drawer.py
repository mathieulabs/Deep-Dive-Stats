# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Table drawer: the table is secondary to the Deep Dive charts.

With the drawer on (and the Deep Dive open) the charts keep the whole window. The
table is lifted out of the splitter and slides over the charts from the right edge
(side-by-side) or the bottom (stacked), so the charts never resize or relayout. A slim
bar at the bottom of the charts opens it; the open table covers that bar and carries its
own close button in the tab row, which sits at the bottom of the table.
Choosing a deck in the table closes it.
"""
from aqt.qt import (
    QAbstractAnimation,
    QAction,
    QApplication,
    QCheckBox,
    QEasingCurve,
    QEvent,
    QFrame,
    QHBoxLayout,
    QKeySequence,
    QLabel,
    QMenu,
    QColor,
    QObject,
    QPainterPath,
    QPushButton,
    QRect,
    QRectF,
    QRegion,
    QTabWidget,
    QTimer,
    QToolButton,
    QVariantAnimation,
    QShortcut,
    QSizePolicy,
    QWidget,
    Qt,
)

from .. import Config
from ...animations.motion import animations_enabled
from ...logic.logger import log_swallowed
from ...widgets.chart_utils.theme import get_theme_colors
from ..theme.icons import get_svg_icon

BAR_HEIGHT = 30
_BAR_GAP = 8
_ANIM_MS = 220
_SIDE_FRACTION = 0.5
_SIDE_MIN = 380
_STRIP_W = 24
_RADIUS = 12
_STACK_FRACTION = 0.55
_STACK_MIN = 220
_CONTENT_MIN = 130  # smallest table that fits its content
_CONTENT_PAD = 16
_CLOSE_DRAG = 40  # px dragged past the smallest size to close the table


def engaged(dialog):
    return bool(getattr(dialog, "_drawer_engaged", False))


def is_open(dialog):
    return engaged(dialog) and bool(getattr(dialog, "_drawer_open", False))


class _BoxFilter(QObject):
    """Keep the open table glued to the charts area when it resizes."""

    def __init__(self, dialog):
        super().__init__(dialog)
        self._dialog = dialog

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Resize and engaged(self._dialog):
            _place(self._dialog, getattr(self._dialog, "_drawer_p", 0.0))
        return False


def _auto_close_on(dialog):
    try:
        return bool(dialog.addon_config.config.get(Config.DETAILS_TABLE_DRAWER_AUTO_CLOSE, True))
    except Exception:
        return True


def _sync_auto_cbs(dialog, value):
    for cb in (getattr(dialog, "table_drawer_auto_cb", None), getattr(dialog, "table_drawer_auto_cb2", None)):
        if cb is not None and cb.isChecked() != bool(value):
            cb.blockSignals(True)
            cb.setChecked(bool(value))
            cb.blockSignals(False)


def set_auto_close(dialog, value):
    dialog.addon_config.config[Config.DETAILS_TABLE_DRAWER_AUTO_CLOSE] = bool(value)
    try:
        dialog.addon_config.write_config_vals({Config.DETAILS_TABLE_DRAWER_AUTO_CLOSE: bool(value)})
    except Exception:
        log_swallowed()
    _sync_auto_cbs(dialog, value)


def install(dialog):
    # Stacked layout: a slim bar at the bottom of the charts area, with the auto-close switch
    # on it. It sits inside that area (in a reserved margin) so the open table can cover it.
    bar = QFrame(dialog.expanded_container)
    bar.setObjectName("table_drawer_bar")
    bar.setFixedHeight(BAR_HEIGHT + _BAR_GAP)
    row = QHBoxLayout(bar)
    row.setContentsMargins(0, _BAR_GAP, 8, 0)
    row.setSpacing(6)
    btn = QPushButton("", parent=bar)
    btn.setObjectName("table_drawer_btn")
    btn.setFlat(True)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    btn.setToolTip("Show or hide the table")
    btn.clicked.connect(lambda: toggle(dialog))
    row.addWidget(btn, 1)
    cb = QCheckBox("Auto-close", parent=bar)
    cb.setToolTip("Close the table after you pick a deck in it")
    cb.setChecked(_auto_close_on(dialog))
    cb.toggled.connect(lambda v: set_auto_close(dialog, v))
    row.addWidget(cb, 0)
    bar.setStyleSheet(
        "QPushButton#table_drawer_btn { text-align: left; border: none; "
        "border-top: 1px solid rgba(128,128,128,0.25); padding: 0 10px; }"
        "QPushButton#table_drawer_btn:hover { background: rgba(128,128,128,0.12); }"
    )
    bar.setVisible(False)
    dialog.table_drawer_bar = bar
    dialog.table_drawer_btn = btn
    dialog.table_drawer_auto_cb = cb
    dialog._drawer_reserved = 0

    # The open table's tab row (at its bottom) carries a Hide button on the left and the
    # auto-close switch on the right; the bar is covered while the table is open.
    hider = QWidget(dialog.tab_widget)
    hider.setObjectName("table_drawer_hider")
    hrow = QHBoxLayout(hider)
    hrow.setContentsMargins(8, 0, 0, 0)
    hide_btn = QToolButton(hider)
    hide_btn.setObjectName("table_drawer_hide")
    hide_btn.setText("Hide")
    hide_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
    hide_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    hide_btn.setToolTip("Hide the table (Esc)")
    hide_btn.clicked.connect(lambda: toggle(dialog, False))
    hrow.addWidget(hide_btn, 0, Qt.AlignmentFlag.AlignVCenter)
    hider.hide()
    dialog.table_drawer_hider = hider
    dialog.table_drawer_hide_btn = hide_btn

    closer = QWidget(dialog.tab_widget)
    closer.setObjectName("table_drawer_closer")
    crow = QHBoxLayout(closer)
    crow.setContentsMargins(0, 0, 10, 0)
    crow.setSpacing(6)
    cb2 = QCheckBox("Auto-close", parent=closer)
    cb2.setToolTip("Close the table after you pick a deck in it")
    cb2.setChecked(_auto_close_on(dialog))
    cb2.toggled.connect(lambda v: set_auto_close(dialog, v))
    crow.addWidget(cb2, 0, Qt.AlignmentFlag.AlignVCenter)
    closer.hide()
    dialog.table_drawer_closer = closer
    dialog.table_drawer_auto_cb2 = cb2
    dialog._drawer_closer_on = False

    # Side-by-side layout: a thin strip on the right edge of the charts, moving with the table.
    strip = QPushButton("", parent=dialog.expanded_container)
    strip.setObjectName("table_drawer_strip")
    strip.setFlat(True)
    strip.setCursor(Qt.CursorShape.PointingHandCursor)
    strip.setToolTip("Show or hide the table (right-click: auto-close)")
    strip.setStyleSheet(
        "QPushButton#table_drawer_strip { border: none; border-left: 1px solid rgba(128,128,128,0.25); "
        "background: rgba(128,128,128,0.06); }"
        "QPushButton#table_drawer_strip:hover { background: rgba(128,128,128,0.18); }"
    )
    strip.clicked.connect(lambda: toggle(dialog))
    strip.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    strip.customContextMenuRequested.connect(lambda pos: _strip_menu(dialog, strip, pos))
    strip.setVisible(False)
    dialog.table_drawer_strip = strip
    dialog._drawer_ui_key = None
    dialog._refresh_drawer_bar = lambda: _update_bar(dialog)
    try:
        saved = dialog.addon_config.config.get(Config.DETAILS_TABLE_DRAWER_SIZES, [0, 0]) or [0, 0]
        dialog._drawer_sizes = {"side": int(saved[0] or 0) or None, "stack": int(saved[1] or 0) or None}
    except Exception:
        dialog._drawer_sizes = {"side": None, "stack": None}
    # Esc closes the open table (only active while it is open, so Esc otherwise behaves as before).
    esc = QShortcut(QKeySequence(Qt.Key.Key_Escape), dialog)
    esc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
    esc.setEnabled(False)
    esc.activated.connect(lambda: toggle(dialog, False))
    dialog._drawer_esc = esc
    # T opens or closes the table and puts the cursor in the deck search.
    key_t = QShortcut(QKeySequence(_shortcut_text(dialog)), dialog)
    key_t.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
    key_t.activated.connect(lambda: _key_toggle(dialog))
    dialog._drawer_key = key_t
    dialog._drawer_outside = _OutsideClick(dialog)
    dialog._drawer_tabclick = _EmptyTabClick(dialog)
    dialog.tab_widget.tabBar().installEventFilter(dialog._drawer_tabclick)
    closer.installEventFilter(dialog._drawer_tabclick)
    hider.installEventFilter(dialog._drawer_tabclick)
    try:
        dialog.tab_widget.currentChanged.connect(lambda _i: _update_bar(dialog))
    except Exception:
        log_swallowed()
    sync(dialog)


def _shortcut_text(dialog):
    try:
        return str(dialog.addon_config.config.get(Config.DETAILS_TABLE_DRAWER_SHORTCUT, "T") or "")
    except Exception:
        return "T"


def apply_shortcut(dialog, text):
    """Settings changed the key that opens and closes the table (empty: no shortcut)."""
    key = getattr(dialog, "_drawer_key", None)
    if key is not None:
        key.setKey(QKeySequence(str(text or "")))


def _key_toggle(dialog):
    if not engaged(dialog):
        return
    toggle(dialog)
    if dialog._drawer_open:
        try:
            dialog.search_bar.setFocus()
            dialog.search_bar.selectAll()
        except Exception:
            log_swallowed()


def _strip_menu(dialog, strip, pos):
    menu = QMenu(strip)
    act = QAction("Auto-close after picking", menu)
    act.setCheckable(True)
    act.setChecked(_auto_close_on(dialog))
    act.toggled.connect(lambda v: set_auto_close(dialog, v))
    menu.addAction(act)
    menu.exec(strip.mapToGlobal(pos))


def _deep_dive_active(dialog):
    box = getattr(dialog, "layout_toggle_container", None)
    return bool(box is not None and box.isVisible())


def _should_engage(dialog):
    return getattr(dialog, "layout_state", 1) != 0 and _deep_dive_active(dialog)


def _is_side(dialog):
    return dialog.layout_splitter.orientation() == Qt.Orientation.Horizontal


def _set_buttons(dialog):
    for i, btn in enumerate(getattr(dialog, "layout_btns", [])):
        btn.setChecked(i == dialog.layout_state)


def _full_charts(dialog):
    sp = dialog.layout_splitter
    total = sum(sp.sizes()) or ((sp.width() if _is_side(dialog) else sp.height()) - sp.handleWidth())
    if total > 0:
        sp.blockSignals(True)
        sp.setSizes([total, 0])
        sp.blockSignals(False)


def _style_edge(edge, side):
    """The edge only needs the resize cursor; the card outline is drawn by the backing frame."""
    if edge is None or getattr(edge, "_side", None) == side:
        return
    edge._side = side
    edge.setCursor(Qt.CursorShape.SizeHorCursor if side else Qt.CursorShape.SizeVerCursor)
    edge.setStyleSheet("background: transparent;")


def _round_leading_corners(table, side):
    """Round the table's leading corners; the trailing side sits outside the charts area."""
    w, h = table.width(), table.height()
    key = (w, h, side)
    if getattr(table, "_drawer_mask_key", None) == key:
        return
    table._drawer_mask_key = key
    extra = 2 * _RADIUS
    path = QPainterPath()
    path.addRoundedRect(
        QRectF(0, 0, w + (extra if side else 0), h + (0 if side else extra)), _RADIUS - 1, _RADIUS - 1
    )
    table.setMask(QRegion(path.toFillPolygon().toPolygon()))


def _panel_size(dialog, r):
    """Width (side-by-side) or height (stacked) of the open table, saved size first."""
    saved = getattr(dialog, "_drawer_sizes", {})
    if _is_side(dialog):
        w = saved.get("side") or max(int(r.width() * _SIDE_FRACTION), _SIDE_MIN)
        return min(max(int(w), _SIDE_MIN), max(_SIDE_MIN, r.width() - 120))
    if saved.get("stack"):
        h = saved["stack"]
        return min(max(int(h), _STACK_MIN), max(_STACK_MIN, r.height() - 80))
    h = max(int(r.height() * _STACK_FRACTION), _STACK_MIN)
    h = min(max(int(h), _STACK_MIN), max(_STACK_MIN, r.height() - 80))
    # Not resized by the user yet: a table with few rows only takes the room it needs.
    content = _content_height(dialog)
    if content:
        h = min(h, max(content, _CONTENT_MIN))
    return h


def _content_height(dialog):
    """Height the current table needs (tab row, header and all rows), or 0 if unknown."""
    try:
        from aqt.qt import QTableWidget

        tabs = dialog.tab_widget
        tab = tabs.widget(tabs.currentIndex())
        table = tab.findChild(QTableWidget) if tab is not None else None
        if table is None or table.rowCount() == 0:
            return 0
        rows = sum(table.rowHeight(i) for i in range(table.rowCount()) if not table.isRowHidden(i))
        header = table.horizontalHeader().height() if not table.horizontalHeader().isHidden() else 0
        return int(tabs.tabBar().sizeHint().height() + header + rows + 2 * table.frameWidth() + _CONTENT_PAD)
    except Exception:
        log_swallowed()
        return 0


class _EdgeHandle(QFrame):
    """The table's leading edge: drag it to resize the open table."""

    def __init__(self, parent, dialog):
        super().__init__(parent)
        self._dialog = dialog
        self._dragging = False

    def mousePressEvent(self, event):
        anim = getattr(self._dialog, "_drawer_anim", None)
        if anim is not None and anim.state() == QAbstractAnimation.State.Running:
            # Still sliding: a drag now would fight the slide (and the closing slide hides
            # this handle while the mouse holds it).
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._close_on_release = False
            # Closing by dragging keeps the size the table had before the drag.
            self._size_before = dict(getattr(self._dialog, "_drawer_sizes", {}) or {})
            event.accept()

    def mouseMoveEvent(self, event):
        if not self._dragging:
            return
        d = self._dialog
        box = d.expanded_container
        pos = box.mapFromGlobal(event.globalPosition().toPoint())
        r = box.rect()
        if _is_side(d):
            size, floor = r.width() - pos.x(), _SIDE_MIN
        else:
            size, floor = r.height() - pos.y() - int(getattr(d, "_drawer_reserved", 0)), _STACK_MIN
        # Dragged well past the smallest size: the table closes when the mouse is released.
        self._close_on_release = size < floor - _CLOSE_DRAG
        d._drawer_sizes["side" if _is_side(d) else "stack"] = max(size, floor)
        _place(d, 1.0)
        event.accept()

    def mouseReleaseEvent(self, event):
        if self._dragging:
            self._dragging = False
            event.accept()
            if getattr(self, "_close_on_release", False):
                self._close_on_release = False
                d = self._dialog
                d._drawer_sizes = dict(getattr(self, "_size_before", None) or d._drawer_sizes)
                # Close once the release is fully handled: the slide hides and re-stacks
                # widgets, this one included, which should not happen inside its own event.
                QTimer.singleShot(0, lambda: _open_overlay(d, False) if engaged(d) else None)
                return
            _save_sizes(self._dialog)


def _save_sizes(dialog):
    s = dialog._drawer_sizes
    try:
        dialog.addon_config.write_config_vals(
            {Config.DETAILS_TABLE_DRAWER_SIZES: [int(s.get("side") or 0), int(s.get("stack") or 0)]}
        )
    except Exception:
        log_swallowed()


class _EmptyTabClick(QObject):
    """A click on the empty part of the table's tab row closes the table."""

    def __init__(self, dialog):
        super().__init__(dialog)
        self._dialog = dialog

    def eventFilter(self, obj, event):
        try:
            if event.type() != QEvent.Type.MouseButtonRelease or not is_open(self._dialog):
                return False
            if event.button() != Qt.MouseButton.LeftButton:
                return False
            bar = self._dialog.tab_widget.tabBar()
            if obj is bar:
                if bar.tabAt(event.position().toPoint()) >= 0:
                    return False
            elif obj not in (self._dialog.table_drawer_closer, self._dialog.table_drawer_hider):
                return False
            if obj is not bar:
                child = obj.childAt(event.position().toPoint())
                if child is not None:
                    return False
            _open_overlay(self._dialog, False)
        except Exception:
            log_swallowed()
        return False


class _OutsideClick(QObject):
    """While the table is open, a click on the charts closes it (the click still goes through)."""

    def __init__(self, dialog):
        super().__init__(dialog)
        self._dialog = dialog

    def eventFilter(self, obj, event):
        try:
            if event.type() != QEvent.Type.MouseButtonPress:
                return False
            d = self._dialog
            if not is_open(d) or QApplication.activePopupWidget() is not None:
                return False
            gp = event.globalPosition().toPoint()
            box = d.expanded_container
            if not box.isVisible() or not box.rect().contains(box.mapFromGlobal(gp)):
                return False
            for w in (d.tab_widget, d.table_drawer_strip, d._drawer_edge):
                if w is not None and w.isVisible() and w.rect().contains(w.mapFromGlobal(gp)):
                    return False
            _open_overlay(d, False, remember=False)
        except Exception:
            log_swallowed()
        return False


def _reserve(dialog, on):
    """Keep room for the bar at the bottom of the charts area (stacked layout only).

    The room is a fixed margin of that area, so the charts never move when the table opens.
    """
    want = (BAR_HEIGHT + _BAR_GAP) if on else 0
    have = int(getattr(dialog, "_drawer_reserved", 0))
    if want == have:
        return
    lay = dialog.expanded_layout
    left, top, right, bottom = lay.getContentsMargins()
    lay.setContentsMargins(left, top, right, max(0, bottom - have + want))
    dialog._drawer_reserved = want


def _set_tabs_bottom(dialog, bottom):
    """Stacked layout: the tab row sits at the bottom, right where the closed bar is."""
    pos = QTabWidget.TabPosition.South if bottom else QTabWidget.TabPosition.North
    if dialog.tab_widget.tabPosition() != pos:
        dialog.tab_widget.setTabPosition(pos)


def _rgba(color, alpha):
    c = QColor(color)
    return f"rgba({c.red()},{c.green()},{c.blue()},{alpha})"


def _style_tab_row(dialog):
    """The Hide button uses the same look as the tab bar's own small buttons."""
    try:
        pal = get_theme_colors(dialog)
        text = QColor(pal.get("text"))
        muted = QColor(pal.get("text_secondary") or pal.get("text"))
        accent = QColor(pal.get("accent"))
        border = QColor(pal.get("border"))
    except Exception:
        log_swallowed()
        return
    hide = (
        "QToolButton#table_drawer_hide {"
        f" color: {muted.name()}; background: transparent; font-weight: 600;"
        f" border: 1px solid {_rgba(border, 0.7)}; border-radius: 6px; padding: 4px 12px 4px 8px; }}"
        "QToolButton#table_drawer_hide:hover {"
        f" color: {text.name()}; background: {_rgba(muted, 0.12)}; border-color: {accent.name()}; }}"
        "QToolButton#table_drawer_hide:pressed {"
        f" background: {_rgba(accent, 0.18)}; border-color: {accent.name()}; }}"
    )
    btn = getattr(dialog, "table_drawer_hide_btn", None)
    if btn is not None and btn.styleSheet() != hide:
        btn.setStyleSheet(hide)


def _style_auto_close(dialog):
    """The Auto-close switches follow the window theme (the app theme can differ from it)."""
    try:
        from ...widgets.common.pill_toggles import pill_checkbox_qss
        from ...widgets.chart_utils.theme import resolve_theme_runtime_state, ThemeContext

        pal = get_theme_colors(dialog)
        runtime = resolve_theme_runtime_state(dialog.addon_config.config, ThemeContext.DETAILS)
        is_dark = bool(runtime.get("is_dark", bool(pal.get("is_dark"))))
        muted = QColor(pal.get("text_secondary") or pal.get("text"))
        accent = QColor(pal.get("accent"))
        qss = pill_checkbox_qss(
            muted.name(),
            f"rgba({accent.red()},{accent.green()},{accent.blue()},180)",
            is_dark,
            extra_css="font-size: 12px; padding: 4px 11px; border-radius: 12px;",
        )
    except Exception:
        log_swallowed()
        return
    for name in ("table_drawer_auto_cb", "table_drawer_auto_cb2"):
        cb = getattr(dialog, name, None)
        if cb is not None and cb.styleSheet() != qss:
            cb.setStyleSheet(qss)


def _set_closer(dialog, show):
    """Show the close button in the table's tab row (corner widget), or take it out."""
    if show == bool(getattr(dialog, "_drawer_closer_on", False)):
        return
    dialog._drawer_closer_on = show
    tabs = dialog.tab_widget
    for widget, corner in (
        (dialog.table_drawer_hider, Qt.Corner.BottomLeftCorner),
        (dialog.table_drawer_closer, Qt.Corner.BottomRightCorner),
    ):
        tabs.setCornerWidget(widget if show else None, corner)
        widget.setVisible(show)
    _fit_corners(dialog)


def _fit_corners(dialog):
    """Qt puts the corner widgets at the top of the tab row with their own height. Give them
    the row's height so the Hide button and the Auto-close switch sit on its middle."""
    if not getattr(dialog, "_drawer_closer_on", False):
        return
    try:
        bar = dialog.tab_widget.tabBar()
        h = max(bar.height(), bar.sizeHint().height())
    except Exception:
        log_swallowed()
        return
    for widget in (dialog.table_drawer_hider, dialog.table_drawer_closer):
        if h > 0 and widget.height() != h:
            widget.setFixedHeight(h)


def _place(dialog, p):
    """Put the table at progress p (0 hidden, 1 fully open) over the charts area."""
    table = dialog.tab_widget
    edge = getattr(dialog, "_drawer_edge", None)
    backing = getattr(dialog, "_drawer_backing", None)
    strip = getattr(dialog, "table_drawer_strip", None)
    box = dialog.expanded_container
    r = box.rect()
    dialog._drawer_p = p
    _style_edge(edge, _is_side(dialog))
    if _is_side(dialog):
        w = min(_panel_size(dialog, r), r.width())
        x = r.width() - int(w * p)
        rect = QRect(x, 0, w, r.height())
        edge_rect = QRect(x - 2, 0, 5, r.height())
        outer = QRect(x, 0, w + 2 * _RADIUS, r.height())
        if strip is not None:
            strip.setGeometry(QRect(x - _STRIP_W, 0, _STRIP_W, r.height()))
    else:
        # The open table also covers the bar's room, so it is that much taller.
        reserved = int(getattr(dialog, "_drawer_reserved", 0))
        h = min(_panel_size(dialog, r) + reserved, r.height())
        y = r.height() - int(h * p)
        rect = QRect(0, y, r.width(), h)
        edge_rect = QRect(0, y - 2, r.width(), 5)
        outer = QRect(0, y, r.width(), h + 2 * _RADIUS)
    bar = getattr(dialog, "table_drawer_bar", None)
    if bar is not None and not _is_side(dialog):
        bh = BAR_HEIGHT + _BAR_GAP
        bar.setGeometry(QRect(0, r.height() - bh, r.width(), bh))
    inner = rect.adjusted(1, 1, -1, -1)
    _fit_corners(dialog)
    mover = getattr(dialog, "_drawer_snap", None) or table
    if mover.geometry() != inner:
        mover.setGeometry(inner)
    _round_leading_corners(mover, _is_side(dialog))
    if edge is not None:
        edge.setGeometry(edge_rect)
    if backing is not None:
        backing.setGeometry(outer)


def _engage(dialog):
    sp = dialog.layout_splitter
    table = dialog.tab_widget
    box = dialog.expanded_container
    placeholder = QWidget()
    placeholder.setMaximumSize(0, 0)
    sp.replaceWidget(1, placeholder)
    table.setParent(box)
    backing = QFrame(box)
    backing.hide()
    edge = _EdgeHandle(box, dialog)
    edge.setCursor(Qt.CursorShape.SizeHorCursor if _is_side(dialog) else Qt.CursorShape.SizeVerCursor)
    edge.setStyleSheet(
        "background: transparent; border-left: 1px solid rgba(128,128,128,0.4);"
        if _is_side(dialog)
        else "background: transparent; border-top: 1px solid rgba(128,128,128,0.4);"
    )
    edge.hide()
    table.hide()
    dialog._drawer_placeholder = placeholder
    dialog._drawer_edge = edge
    dialog._drawer_backing = backing
    dialog._drawer_back_style = None  # the new frame has no style yet
    dialog._drawer_engaged = True
    dialog._drawer_open = False
    dialog._drawer_p = 0.0
    try:
        dialog.tab_widget.currentChanged.connect(lambda _i, d=dialog: _on_tab_changed(d))
    except Exception:
        log_swallowed()
    _ICONS.clear()
    dialog._drawer_ui_key = None
    dialog.layout_state = 2
    flt = _BoxFilter(dialog)
    box.installEventFilter(flt)
    dialog._drawer_filter = flt
    try:
        sp.handle(1).setEnabled(False)
    except Exception:
        log_swallowed()
    _full_charts(dialog)
    _set_buttons(dialog)
    try:
        if dialog.addon_config.config.get(Config.DETAILS_TABLE_DRAWER_OPEN, False):
            _open_overlay(dialog, True, instant=True, remember=False)
    except Exception:
        log_swallowed()


def _watch_content(dialog, on):
    """While open, follow the table's content (a deck, a view or a filter changed its rows)."""
    timer = getattr(dialog, "_drawer_content_timer", None)
    if not on:
        if timer is not None:
            timer.stop()
        return
    if timer is None:
        timer = QTimer(dialog)
        timer.setInterval(200)

        def _tick(d=dialog):
            try:
                if not engaged(d) or not getattr(d, "_drawer_open", False):
                    return
                anim = getattr(d, "_drawer_anim", None)
                if anim is not None and anim.state() == QAbstractAnimation.State.Running:
                    return
                key = (_content_height(d), d.tab_widget.currentIndex())
                if key != getattr(d, "_drawer_content_key", None):
                    d._drawer_content_key = key
                    _place(d, 1.0)
                    _fit_current_table(d)
                    _raise_drawer(d)
            except Exception:
                log_swallowed()

        timer.timeout.connect(_tick)
        dialog._drawer_content_timer = timer
    dialog._drawer_content_key = None
    timer.start()


def _raise_drawer(dialog):
    backing = getattr(dialog, "_drawer_backing", None)
    edge = getattr(dialog, "_drawer_edge", None)
    if backing is not None:
        backing.raise_()
    dialog.tab_widget.raise_()
    if edge is not None:
        edge.raise_()
    strip = getattr(dialog, "table_drawer_strip", None)
    if strip is not None:
        strip.raise_()


def _on_tab_changed(dialog):
    """Another table may need a different height."""
    if not engaged(dialog) or not getattr(dialog, "_drawer_open", False):
        return
    if getattr(dialog, "_drawer_anim", None) is not None and dialog._drawer_anim.state() == QAbstractAnimation.State.Running:
        return
    QTimer.singleShot(0, lambda: _place(dialog, float(getattr(dialog, "_drawer_p", 1.0))) if engaged(dialog) else None)


def _disengage(dialog):
    _watch_content(dialog, False)
    try:
        dialog._drawer_esc.setEnabled(False)
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(dialog._drawer_outside)
    except Exception:
        log_swallowed()
    anim = getattr(dialog, "_drawer_anim", None)
    if anim is not None:
        try:
            anim.finished.disconnect()
        except Exception:
            log_swallowed()
        anim.stop()
        anim.deleteLater()
        dialog._drawer_anim = None
    _drop_snapshot(dialog)
    sp = dialog.layout_splitter
    table = dialog.tab_widget
    table.hide()
    table.clearMask()
    table._drawer_mask_key = None
    table.setGraphicsEffect(None)
    backing = getattr(dialog, "_drawer_backing", None)
    if backing is not None:
        backing.hide()
        backing.deleteLater()
    dialog._drawer_backing = None
    strip = getattr(dialog, "table_drawer_strip", None)
    if strip is not None:
        strip.hide()
    edge = getattr(dialog, "_drawer_edge", None)
    if edge is not None:
        edge.hide()
        edge.deleteLater()
    dialog._drawer_edge = None
    try:
        dialog.expanded_container.removeEventFilter(dialog._drawer_filter)
    except Exception:
        log_swallowed()
    _set_tabs_bottom(dialog, False)
    sp.replaceWidget(1, table)
    table.show()
    ph = getattr(dialog, "_drawer_placeholder", None)
    if ph is not None:
        ph.hide()
        ph.deleteLater()
    dialog._drawer_placeholder = None
    dialog._drawer_engaged = False
    dialog._drawer_open = False
    try:
        sp.handle(1).setEnabled(True)
    except Exception:
        log_swallowed()


def _fit_current_table(dialog):
    """The table was hidden while loading, so its columns were never sized. Do it now it is visible."""
    try:
        from aqt.qt import QTableWidget

        tab = dialog.tab_widget.widget(dialog.tab_widget.currentIndex())
        table = tab.findChild(QTableWidget) if tab is not None else None
        if table is None:
            return
        if not getattr(table, "_has_been_resized", False):
            if dialog.auto_resize_window(table, resize_window=False):
                table._has_been_resized = True
        key = (table.viewport().width(), table.rowCount(), table.columnCount())
        if getattr(table, "_drawer_fit_key", None) != key:
            table._drawer_fit_key = key
            table.doItemsLayout()
    except Exception:
        log_swallowed()


def export_prepare(dialog):
    """Make the current table ready to be drawn into an export; returns a function that undoes it.

    A table closed in the drawer is hidden and may never have been sized, so show it
    (off-screen, clipped by the charts area), size its columns, then hide it again.
    """
    table = dialog.tab_widget
    if not engaged(dialog):
        return lambda: None
    was_hidden = table.isHidden()
    # The rounded-corner mask would clip the render; _place puts it back afterwards.
    table.clearMask()
    table._drawer_mask_key = None
    if was_hidden:
        _place(dialog, 0.0)
        table.show()
        table.clearMask()
        table._drawer_mask_key = None
    _fit_current_table(dialog)

    def _restore():
        if was_hidden:
            table.hide()
        _place(dialog, getattr(dialog, "_drawer_p", 0.0))

    return _restore


def _drop_snapshot(dialog):
    snap = getattr(dialog, "_drawer_snap", None)
    if snap is not None:
        snap.hide()
        snap.deleteLater()
    dialog._drawer_snap = None


def _settle_size(dialog):
    """Size the columns and rows first, then place the open table, so it opens at its final height."""
    table = dialog.tab_widget
    if table.isHidden():
        _place(dialog, 1.0)
        table.show()
    _fit_current_table(dialog)
    _place(dialog, 1.0)
    _fit_current_table(dialog)


def _make_snapshot(dialog):
    """A picture of the table at its final size. Sliding a picture is cheap; sliding the
    live table would repaint every cell on every frame."""
    table = dialog.tab_widget
    _settle_size(dialog)
    try:
        pix = table.grab()
    except Exception:
        log_swallowed()
        return None
    snap = QLabel(dialog.expanded_container)
    snap.setStyleSheet("border: 0; padding: 0; margin: 0; background: transparent;")
    snap.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
    snap.setPixmap(pix)
    snap.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
    dialog._drawer_snap = snap
    table.hide()
    return snap


def _set_outside_filter(dialog, on):
    app = QApplication.instance()
    if app is None:
        return
    if on:
        app.installEventFilter(dialog._drawer_outside)
    else:
        app.removeEventFilter(dialog._drawer_outside)


def _open_overlay(dialog, open_, instant=False, remember=True):
    if not engaged(dialog) or open_ == bool(dialog._drawer_open):
        return
    table = dialog.tab_widget
    edge = dialog._drawer_edge
    dialog._drawer_open = open_
    dialog.layout_state = 1 if open_ else 2
    _set_buttons(dialog)
    dialog._drawer_esc.setEnabled(open_)
    # The click-outside filter sees every event of the app, so keep it off while sliding.
    _set_outside_filter(dialog, False)
    if remember:
        # Writing the config is disk work: do it after the slide has started, not before.
        QTimer.singleShot(0, lambda: _remember_open(dialog, open_))
    backing = dialog._drawer_backing
    try:
        style = (
            f"background: {get_theme_colors(dialog)['bg'].name()}; "
            f"border: 1px solid rgba(128,128,128,0.4); border-radius: {_RADIUS}px;"
        )
        if getattr(dialog, "_drawer_back_style", None) != style:
            dialog._drawer_back_style = style
            backing.setStyleSheet(style)
    except Exception:
        log_swallowed()

    anim = getattr(dialog, "_drawer_anim", None)
    if anim is not None:
        # Disconnect first: stop() can emit finished, which would run the old close step.
        try:
            anim.finished.disconnect()
        except Exception:
            log_swallowed()
        anim.stop()
        anim.deleteLater()
        dialog._drawer_anim = None
    _drop_snapshot(dialog)

    start = float(getattr(dialog, "_drawer_p", 0.0))
    end = 1.0 if open_ else 0.0

    def _raise_all():
        backing.raise_()
        snap = getattr(dialog, "_drawer_snap", None)
        (snap if snap is not None else table).raise_()
        edge.raise_()
        dialog.table_drawer_strip.raise_()

    def _finish():
        _drop_snapshot(dialog)
        if open_:
            _place(dialog, 1.0)
            table.show()
            _raise_all()
            _set_outside_filter(dialog, True)
            _watch_content(dialog, True)
        else:
            _watch_content(dialog, False)
            _place(dialog, 0.0)
            table.hide()
            edge.hide()
            backing.hide()
        _update_bar(dialog)

    animated = not instant and animations_enabled("pinned")
    if not animated:
        if open_:
            _settle_size(dialog)
            _place(dialog, start)
            backing.show()
            table.show()
            edge.show()
            _raise_all()
        _finish()
        return

    snap = _make_snapshot(dialog)
    if snap is None:  # could not take the picture: open without the slide
        if open_:
            backing.show()
            edge.show()
            table.show()
        _finish()
        return
    _place(dialog, start)
    backing.show()
    edge.show()
    snap.show()
    _raise_all()
    anim = QVariantAnimation(dialog)
    anim.setDuration(_ANIM_MS)
    anim.setStartValue(start)
    anim.setEndValue(end)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)
    anim.valueChanged.connect(lambda v: _place(dialog, float(v)))
    anim.finished.connect(_finish)
    dialog._drawer_anim = anim
    anim.start()
    _update_bar(dialog)


def _remember_open(dialog, open_):
    if bool(getattr(dialog, "_drawer_open", False)) != bool(open_):
        return  # toggled again in the meantime; the later call saves its own state
    try:
        dialog.addon_config.write_config_vals({Config.DETAILS_TABLE_DRAWER_OPEN: bool(open_)})
    except Exception:
        log_swallowed()


def handle_layout_state(dialog, state, update_sizes=True):
    """Called first by apply_layout_state. True means the drawer handled it."""
    if not engaged(dialog):
        return False
    if state == 0:
        return False
    if state is None:
        _full_charts(dialog)
        return True
    _open_overlay(dialog, state == 1)
    return True


def sync(dialog):
    """Engage or release the drawer, and keep the bar's label and arrow current."""
    bar = getattr(dialog, "table_drawer_bar", None)
    if bar is None:
        return
    want = _should_engage(dialog)
    try:
        if want and not engaged(dialog):
            _engage(dialog)
        elif not want and engaged(dialog):
            _disengage(dialog)
    except Exception:
        log_swallowed()
    _update_bar(dialog)
    if engaged(dialog):
        _place(dialog, getattr(dialog, "_drawer_p", 0.0))


def _update_bar(dialog):
    """Refresh the bar or side strip. Only touches widgets when something changed."""
    bar = getattr(dialog, "table_drawer_bar", None)
    strip = getattr(dialog, "table_drawer_strip", None)
    if bar is None or strip is None:
        return
    want = engaged(dialog)
    side = want and _is_side(dialog)
    opened = bool(getattr(dialog, "_drawer_open", False)) and want
    try:
        title = dialog.tab_widget.tabText(dialog.tab_widget.currentIndex())
    except Exception:
        title = ""
    summary = ""
    if not opened:
        try:
            st = dialog.tab_stats.get(dialog.tab_widget.currentIndex()) or {}
            bits = []
            if st.get("reviews"):
                bits.append(f"{st['reviews']} reviews")
            if st.get("ret_all") and st.get("ret_all") != "N/A":
                bits.append(str(st["ret_all"]))
            summary = "  \u00b7  ".join(bits)
        except Exception:
            summary = ""
    _style_auto_close(dialog)
    if want and not side:
        _style_tab_row(dialog)
    key = (want, side, opened, title, summary)
    if key == getattr(dialog, "_drawer_ui_key", None):
        return
    dialog._drawer_ui_key = key
    stacked = want and not side
    _set_tabs_bottom(dialog, stacked)
    _reserve(dialog, stacked)
    bar.setVisible(stacked)
    strip.setVisible(side)
    _set_closer(dialog, stacked)
    if not want:
        return
    if side:
        strip.setIcon(_icon("chevron-right" if opened else "chevron-left"))
        return
    # Doubled "&": the button would read it as a keyboard shortcut.
    label = "  Table: " + title.replace("&", "&&") if title else "  Table"
    if summary:
        label += "  \u00b7  " + summary
    dialog.table_drawer_btn.setText(label)
    dialog.table_drawer_btn.setIcon(_icon("chevron-down" if opened else "chevron-up"))
    dialog.table_drawer_hide_btn.setIcon(_icon("chevron-down"))
    _sync_auto_cbs(dialog, _auto_close_on(dialog))


_ICONS = {}


def _icon(name):
    ic = _ICONS.get(name)
    if ic is None:
        try:
            ic = get_svg_icon(name)
        except Exception:
            log_swallowed()
            return get_svg_icon("chevron-down")
        _ICONS[name] = ic
    return ic


def toggle(dialog, open_=None):
    """Open or close the table."""
    if engaged(dialog):
        _open_overlay(dialog, (not dialog._drawer_open) if open_ is None else bool(open_))
        return
    # Not engaged: the table fills the window. With the Deep Dive open, bring the charts back.
    if _deep_dive_active(dialog) and open_ is not False:
        dialog.switch_layout(1)


def collapse_after_pick(dialog):
    """A deck was chosen in the table: give the window back to the charts."""
    # Instant: the deck is about to load, an animation would fight it for the main thread.
    if _auto_close_on(dialog) and is_open(dialog) and dialog.isVisible():
        _open_overlay(dialog, False, instant=True, remember=False)
