# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import (
    QComboBox,
    QColor,
    QLineEdit,
    QPainter,
    QPainterPath,
    QRectF,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    Qt,
    QVBoxLayout,
    QWidget,
)

from ... import ThemePalettes
from .....qss import set_qss


def get_builtin_theme_defs():
    return [
        (ThemePalettes.NATIVE, "Anki Native"),
        (ThemePalettes.CHARCOAL, "Charcoal"),
        (ThemePalettes.DEEP_OCEAN, "Deep Ocean"),
        (ThemePalettes.NORD, "Nord"),
        (ThemePalettes.GITHUB, "Slate"),
        (ThemePalettes.MIDNIGHT, "Midnight"),
        (ThemePalettes.DARK_PRO, "Dark Pro"),
        (ThemePalettes.DARK_OCEAN, "Dark Ocean"),
        (ThemePalettes.DEFAULT_DARK, "Default Dark"),
        (ThemePalettes.DARK_PURPLE, "Dark Purple"),
        (ThemePalettes.DRACULA, "Dracula"),
        (ThemePalettes.CATPPUCCIN, "Catppuccin"),
        (ThemePalettes.TOKYO_NIGHT, "Tokyo Night"),
        (ThemePalettes.GRUVBOX, "Gruvbox"),
        (ThemePalettes.MONOKAI, "Monokai"),
        (ThemePalettes.ONE_DARK, "One Dark"),
        (ThemePalettes.AYU_DARK, "Ayu Dark"),
        (ThemePalettes.ROSE_PINE, "Rosé Pine"),
        (ThemePalettes.AURORA, "Aurora"),
        (ThemePalettes.EMBER, "Ember"),
        (ThemePalettes.DEEP_SPACE, "Deep Space"),
        (ThemePalettes.NEON, "Neon"),
        (ThemePalettes.COFFEE, "Coffee"),
        (ThemePalettes.SYNTHWAVE, "Synthwave"),
        (ThemePalettes.ABYSS, "Abyss"),
        (ThemePalettes.BLOOD_MOON, "Blood Moon"),
        (ThemePalettes.TOXIC, "Toxic"),
        (ThemePalettes.STEAMPUNK, "Steampunk"),
        (ThemePalettes.VOID, "Void"),
        (ThemePalettes.VAPORWAVE, "Vaporwave"),
        (ThemePalettes.MATRIX, "Matrix"),
        (ThemePalettes.CYBER_GOLD, "Cyber Gold"),
        (ThemePalettes.AMETHYST, "Amethyst"),
        (ThemePalettes.ABSINTHE, "Absinthe"),
        (ThemePalettes.MODERN_LIGHT, "Modern Light"),
        (ThemePalettes.NATURE_LIGHT, "Nature Light"),
        (ThemePalettes.OCEAN_LIGHT, "Ocean Light"),
        (ThemePalettes.SUNSET_LIGHT, "Sunset Light"),
        (ThemePalettes.LAVENDER, "Lavender"),
        (ThemePalettes.MINT, "Mint"),
        (ThemePalettes.PEACH, "Peach"),
        (ThemePalettes.SOLARIZED, "Solarized"),
        (ThemePalettes.ROSE, "Rose"),
        (ThemePalettes.GRUVBOX_LIGHT, "Gruvbox Light"),
        (ThemePalettes.EVERFOREST_LIGHT, "Everforest Light"),
        (ThemePalettes.PARCHMENT, "Parchment"),
        (ThemePalettes.CHERRY_BLOSSOM, "Cherry Blossom"),
        (ThemePalettes.COTTON_CANDY, "Cotton Candy"),
        (ThemePalettes.DUSK, "Dusk"),
        (ThemePalettes.CORAL, "Coral"),
        (ThemePalettes.LEMON_SORBET, "Lemon Sorbet"),
        (ThemePalettes.GLACIER, "Glacier"),
        (ThemePalettes.CHAMPAGNE, "Champagne"),
    ]


def get_theme_color_keys():
    return [
        ("bg_root", "Window Background"),
        ("bg_surface", "Surface / Tab"),
        ("bg_element", "Element / Button"),
        ("text_primary", "Main Text"),
        ("text_secondary", "Secondary Text"),
        ("accent", "Accent"),
        ("accent_hover", "Accent Hover"),
        ("border_strong", "Border Strong"),
        ("border_subtle", "Border Subtle"),
        ("total_line", "Total / Avg"),
    ]


def build_theme_cards_container(object_name):
    container = QWidget()
    container.setObjectName(object_name)
    grid = QGridLayout(container)
    grid.setSpacing(8)
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setColumnStretch(0, 1)
    grid.setColumnStretch(1, 1)
    grid.setColumnStretch(2, 1)
    set_qss(container, f"QWidget#{object_name} {{ background: transparent; border: none; }}")
    return container, grid


def build_theme_base_mode_selector(parent_widget, on_mode_clicked):
    row = QHBoxLayout()
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(8)

    label = QLabel("Graph Adaptation Mode:")
    row.addWidget(label)

    selector = QWidget()
    selector_lay = QHBoxLayout(selector)
    selector_lay.setContentsMargins(0, 0, 0, 0)
    selector_lay.setSpacing(6)

    buttons = {}
    for text, mode in (
        ("Follow Anki", ThemePalettes.MODE_NATIVE),
        ("Dark", ThemePalettes.MODE_DARK),
        ("Light", ThemePalettes.MODE_LIGHT),
    ):
        btn = QPushButton(text, parent=selector)
        btn.setCheckable(True)
        btn.setAutoExclusive(True)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(lambda _checked=False, m=mode: on_mode_clicked(m))
        buttons[mode] = btn
        selector_lay.addWidget(btn)
    row.addWidget(selector, 1)
    return row, label, selector, buttons


def build_pinned_theme_mode_group(on_mode_changed):
    pinned_mode_group = QGroupBox("Pinned Theme Mode")
    pinned_mode_layout = QFormLayout(pinned_mode_group)
    pinned_mode_layout.setContentsMargins(10, 10, 10, 10)
    pinned_mode_layout.setSpacing(6)

    combo = QComboBox()
    combo.addItem("Use Native (Anki)", "native")
    combo.addItem("Use Details Theme", "linked")
    combo.addItem("Use Separate Pinned Theme", "separate")
    combo.setToolTip("Choose how pinned widgets pick their theme.")
    combo.currentIndexChanged.connect(on_mode_changed)
    pinned_mode_layout.addRow("Pinned Theme:", combo)

    hint = QLabel("")
    hint.setObjectName("theme_info_label")
    hint.setWordWrap(True)
    pinned_mode_layout.addRow(hint)
    return pinned_mode_group, combo, hint


def add_data_color_group(parent_layout, title, rows, make_color_button):
    group = QGroupBox(title)
    layout = QGridLayout(group)
    layout.setSpacing(8)
    layout.setContentsMargins(10, 10, 10, 10)
    layout.setColumnStretch(0, 2)
    layout.setColumnStretch(1, 3)
    layout.setColumnStretch(2, 2)
    layout.setColumnStretch(3, 3)

    for i, (key, label) in enumerate(rows):
        row_i, col_pair = divmod(i, 2)
        base_col = col_pair * 2
        layout.addWidget(QLabel(label), row_i, base_col)
        layout.addWidget(make_color_button(key), row_i, base_col + 1)

    parent_layout.addWidget(group)
    return group


def clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        child_layout = item.layout()
        if widget is not None:
            widget.hide()
            widget.deleteLater()
        elif child_layout is not None:
            clear_layout(child_layout)


def apply_theme_card_style(card, is_selected, palette):
    bg = palette.get("bg_surface", "#27272a")
    accent = palette.get("accent", "#58a6ff")
    border_color = accent if is_selected else palette.get("border_strong", "#444444")
    border_width = "2px" if is_selected else "1px"
    text_color = palette.get("text_primary", "#ffffff")

    set_qss(card, 
        f"""
        QFrame#theme_preset_card {{
            background: {bg};
            border: {border_width} solid {border_color};
            border-radius: 12px;
        }}
        QLabel#theme_card_name {{
            color: {text_color};
            font-weight: 600;
            font-size: 12px;
            border: none;
            background: transparent;
        }}
        QLabel#theme_card_check {{
            color: {accent};
            font-weight: 700;
            border: none;
            background: transparent;
        }}
        """
    )


def apply_base_mode_button_styles(buttons, palette):
    text_primary = palette.get("text_primary", "#f4f4f5")
    text_secondary = palette.get("text_secondary", "#a1a1aa")
    bg_surface = palette.get("bg_surface", "#27272a")
    border_subtle = palette.get("border_subtle", "#3f3f46")
    border_strong = palette.get("border_strong", "#52525b")
    accent = palette.get("accent", "#58a6ff")

    acc = QColor(accent)
    acc_bg = f"rgba({acc.red()}, {acc.green()}, {acc.blue()}, 40)"
    for _mode, btn in buttons.items():
        if btn.isChecked():
            set_qss(btn, 
                f"""
                QPushButton {{
                    background: {acc_bg};
                    color: {text_primary};
                    border: 1px solid {accent};
                    border-radius: 6px;
                    padding: 5px 10px;
                    font-weight: 600;
                }}
                """
            )
        else:
            set_qss(btn, 
                f"""
                QPushButton {{
                    background: {bg_surface};
                    color: {text_secondary};
                    border: 1px solid {border_subtle};
                    border-radius: 6px;
                    padding: 5px 10px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    border: 1px solid {border_strong};
                    color: {text_primary};
                }}
                """
            )


class _ThemePreview(QWidget):
    """Mini window drawn with the preset colours: surface card with title/text
    lines, a stat chip, bars + trend line, and the key colour dots."""

    _BARS = (0.35, 0.55, 0.42, 0.8, 0.6, 0.95, 0.7, 0.85)

    def __init__(self, palette, parent=None):
        super().__init__(parent)
        self._p = palette
        self.setFixedHeight(66)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def _c(self, key, default, alpha=None):
        c = QColor(self._p.get(key, default))
        if alpha is not None:
            c.setAlphaF(alpha)
        return c

    def paintEvent(self, _e):
        qp = QPainter(self)
        qp.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        outer = QPainterPath()
        outer.addRoundedRect(r, 8, 8)
        qp.fillPath(outer, self._c("bg_root", "#222222"))
        qp.setClipPath(outer)

        card = r.adjusted(5, 5, -5, -5)
        cp = QPainterPath()
        cp.addRoundedRect(card, 6, 6)
        qp.fillPath(cp, self._c("bg_surface", "#2a2a2a"))
        qp.setPen(self._c("border_subtle", "#444444", 0.9))
        qp.setBrush(Qt.BrushStyle.NoBrush)
        qp.drawPath(cp)

        qp.setPen(Qt.PenStyle.NoPen)
        x0 = card.left() + 7
        qp.setBrush(self._c("text_primary", "#ffffff"))
        qp.drawRoundedRect(QRectF(x0, card.top() + 7, 30, 3.5), 1.7, 1.7)
        qp.setBrush(self._c("text_secondary", "#aaaaaa", 0.8))
        qp.drawRoundedRect(QRectF(x0, card.top() + 14, 20, 2.5), 1.2, 1.2)
        chip = QRectF(x0, card.top() + 22, 30, 15)
        qp.setBrush(self._c("bg_element", "#333333"))
        qp.drawRoundedRect(chip, 4, 4)
        qp.setBrush(self._c("accent", "#58a6ff"))
        qp.drawRoundedRect(QRectF(chip.left() + 4, chip.top() + 4, 14, 3.5), 1.7, 1.7)
        qp.setBrush(self._c("text_secondary", "#aaaaaa", 0.7))
        qp.drawRoundedRect(QRectF(chip.left() + 4, chip.top() + 10, 9, 2), 1, 1)

        cx = x0 + 40
        cw = card.right() - 7 - cx
        ch = card.height() - 14
        base = card.bottom() - 7
        gl = self._c("border_subtle", "#444444", 0.6)
        qp.setPen(gl)
        qp.drawLine(int(cx), int(base - ch * 0.5), int(cx + cw), int(base - ch * 0.5))
        qp.setPen(Qt.PenStyle.NoPen)
        n = len(self._BARS)
        step = cw / n
        accent = self._c("accent", "#58a6ff")
        for k, v in enumerate(self._BARS):
            c = QColor(accent)
            c.setAlphaF(0.5 + 0.5 * v)
            qp.setBrush(c)
            bh = ch * v
            qp.drawRoundedRect(QRectF(cx + k * step + step * 0.14, base - bh, step * 0.72, bh), 1.4, 1.4)
        pen = qp.pen()
        pen.setColor(self._c("total_line", "#cccccc"))
        pen.setWidthF(1.5)
        qp.setPen(pen)
        qp.setBrush(Qt.BrushStyle.NoBrush)
        lp = QPainterPath()
        for k, v in enumerate((0.3, 0.45, 0.4, 0.62, 0.55, 0.8, 0.72, 0.85)):
            x = cx + k * step + step / 2
            y = base - ch * v
            lp.moveTo(x, y) if k == 0 else lp.lineTo(x, y)
        qp.drawPath(lp)
        qp.end()


def _is_dark_palette(palette):
    try:
        return QColor(palette.get("bg_root", "#222222")).lightness() < 128
    except Exception:
        return True


def make_theme_card(preset_key, preset_name, current_preset, palette, on_click, parent_widget=None, is_custom=False):
    is_selected = (preset_key == current_preset)

    card = QFrame(parent_widget)
    card.setObjectName("theme_preset_card")
    card.setCursor(Qt.CursorShape.PointingHandCursor)
    card.setFixedHeight(118)
    card.setProperty("theme_name", preset_name)
    card.setProperty("theme_dark", _is_dark_palette(palette))
    card.setProperty("theme_custom", bool(is_custom))
    card.setToolTip(preset_name)

    card_layout = QVBoxLayout(card)
    card_layout.setContentsMargins(8, 8, 8, 7)
    card_layout.setSpacing(6)

    card_layout.addWidget(_ThemePreview(palette, card))

    top_row = QHBoxLayout()
    top_row.setSpacing(4)
    top_row.setContentsMargins(2, 0, 2, 0)
    name_lbl = QLabel(preset_name, parent=card)
    name_lbl.setObjectName("theme_card_name")
    top_row.addWidget(name_lbl)
    top_row.addStretch()
    check_lbl = QLabel("\u2713", parent=card)
    check_lbl.setObjectName("theme_card_check")
    check_lbl.setVisible(is_selected)
    top_row.addWidget(check_lbl)
    card_layout.addLayout(top_row)

    apply_theme_card_style(card, is_selected, palette)

    def on_press(event):
        if event.button() == Qt.MouseButton.LeftButton:
            on_click(preset_key)

    card.mousePressEvent = on_press
    return card


def build_theme_filter_bar(on_changed):
    """Search box + All/Dark/Light/Custom chips. Returns (layout, state dict)."""
    state = {"mode": "all", "text": ""}
    row = QHBoxLayout()
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(6)
    search = QLineEdit()
    search.setPlaceholderText("Search themes...")
    search.setClearButtonEnabled(True)
    row.addWidget(search, 1)
    chips = {}
    for mode, label in (("all", "All"), ("dark", "Dark"), ("light", "Light"), ("custom", "Custom")):
        b = QPushButton(label)
        b.setCheckable(True)
        b.setChecked(mode == "all")
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setObjectName("theme_chip")
        set_qss(b, "QPushButton#theme_chip { padding: 5px 14px; border-radius: 14px; }")
        chips[mode] = b
        row.addWidget(b)

    def pick(mode):
        state["mode"] = mode
        for m, btn in chips.items():
            btn.blockSignals(True)
            btn.setChecked(m == mode)
            btn.blockSignals(False)
        on_changed()

    for m, btn in chips.items():
        btn.clicked.connect(lambda _c=False, mm=m: pick(mm))

    def on_text(t):
        state["text"] = t.strip().lower()
        on_changed()

    search.textChanged.connect(on_text)
    return row, state


def apply_theme_card_filter(grid, cards, state, columns=3):
    """Show only matching cards and re-pack them in the grid."""
    mode = state.get("mode", "all")
    text = state.get("text", "")
    while grid.count():
        grid.takeAt(0)
    shown = 0
    for card in cards.values():
        name = str(card.property("theme_name") or "").lower()
        ok = (not text or text in name)
        if ok and mode == "dark":
            ok = bool(card.property("theme_dark"))
        elif ok and mode == "light":
            ok = not bool(card.property("theme_dark"))
        elif ok and mode == "custom":
            ok = bool(card.property("theme_custom"))
        card.setVisible(ok)
        if ok:
            r, c = divmod(shown, int(columns))
            grid.addWidget(card, r, c)
            shown += 1
    return shown


def build_theme_card_defs(builtin_defs, custom_presets):
    defs = list(builtin_defs or [])
    for key, entry in (custom_presets or {}).items():
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name", key))
        defs.append((key, name))
    return defs


def rebuild_theme_cards_grid(*, grid, card_container, current_preset, card_defs, make_card, on_click, columns=3):
    cards = {}
    clear_layout(grid)
    for i, (preset_key, preset_name) in enumerate(card_defs):
        card = make_card(
            preset_key,
            preset_name,
            current_preset,
            on_click=on_click,
            parent_widget=card_container,
        )
        cards[preset_key] = card
        row, col = divmod(i, int(columns))
        grid.addWidget(card, row, col)
    return cards


def set_theme_color_button_hex(btn, hex_label, hex_val):
    if btn:
        set_qss(btn, 
            f"background-color: {hex_val}; border: 1px solid rgba(128,128,128,0.45); border-radius: 4px;"
        )
    if hex_label:
        hex_label.setText(str(hex_val).upper())


