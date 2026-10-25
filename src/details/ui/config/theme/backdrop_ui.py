# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Settings > Colors > "Window Background": controls for the window backdrop
(see ui/theme/backdrop.py).

Changes apply live to the open window and the preview. Save keeps them, Cancel
rolls them back with the other settings.
"""

from __future__ import annotations

from aqt.qt import (
    QColor,
    QColorDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPainter,
    QPainterPath,
    QPen,
    QPushButton,
    QRectF,
    QSizePolicy,
    Qt,
    QTimer,
    QVBoxLayout,
    QWidget,
)

from ...theme.backdrop import (
    BACKDROP_DEFAULTS,
    BACKDROP_KEY,
    BACKDROP_PRESETS,
    get_backdrop_filter,
    get_backdrop_settings,
    matching_preset,
    refresh_backdrop_settings,
    glow_colors,
    render_backdrop,
)
from ...theme.design_overrides import _colors
from ...theme.palette import get_theme_palette
from ...theme.theme_mode import get_theme_effective_is_dark
from ..widgets.components import SettingsSlider
from .ui_helpers import apply_base_mode_button_styles
from ....logic.logger import log_swallowed


def _theme_colors(stats_dialog):
    """(bg, accent, is_dark) as currently used by the stats window."""
    flt = get_backdrop_filter(stats_dialog)
    if flt is not None and flt.colors:
        return flt.colors[0], flt.colors[1], flt.is_dark
    conf = stats_dialog.addon_config.config
    is_dark = get_theme_effective_is_dark(conf)
    c = _colors(is_dark, get_theme_palette(conf))
    return c["bg"], c["accent"], is_dark


class BackdropPreview(QWidget):
    """Miniature of the stats window: backdrop + two glass cards."""

    def __init__(self, stats_dialog, parent=None):
        super().__init__(parent)
        self._stats = stats_dialog
        self.setMinimumHeight(118)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def paintEvent(self, _event):
        bg, accent, dark = _theme_colors(self._stats)
        s = get_backdrop_settings(self._stats.addon_config.config)
        w, h = self.width(), self.height()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        frame = QRectF(0.5, 0.5, w - 1, h - 1)
        clip = QPainterPath()
        clip.addRoundedRect(frame, 10, 10)
        p.setClipPath(clip)

        if s["enabled"]:
            p.drawPixmap(0, 0, render_backdrop(w, h, self.devicePixelRatioF(), bg, accent, dark, s))
        else:
            p.fillRect(self.rect(), QColor(bg))

        # Two mini cards, styled like the Deep Dive glass cards.
        gap, pad_x, top = 10, 12, 30
        card_w = (w - 2 * pad_x - gap) / 2
        card_h = h - top - 12
        acc = QColor(accent)
        for i in range(2):
            r = QRectF(pad_x + i * (card_w + gap), top, card_w, card_h)
            if dark:
                fill = QColor(255, 255, 255, 12)
                pen = QColor(255, 255, 255, 18)
            else:
                fill = QColor(255, 255, 255, 240)
                pen = QColor(0, 0, 0, 22)
            p.setPen(QPen(pen, 1))
            p.setBrush(fill)
            p.drawRoundedRect(r, 9, 9)
            # bars
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(acc)
            n = 12
            bw = (r.width() - 20) / n
            heights = (0.5, 0.7, 0.4, 0.8, 0.55, 0.9, 0.35, 0.6, 0.75, 0.45, 0.85, 0.65)
            for j in range(n):
                hh = (r.height() - 22) * heights[(j + i * 5) % n]
                p.drawRoundedRect(
                    QRectF(r.left() + 10 + j * bw + 1.5, r.bottom() - 8 - hh, bw - 3, hh), 1.5, 1.5
                )

        # Fake title
        title = QColor("#ffffff" if dark else "#18181b")
        p.setPen(title)
        f = p.font()
        f.setBold(True)
        f.setPointSizeF(max(7.0, f.pointSizeF() * 0.85))
        p.setFont(f)
        p.drawText(QRectF(pad_x, 6, w, 20), Qt.AlignmentFlag.AlignVCenter, "Deep Dive")

        p.setClipping(False)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(128, 128, 128, 70), 1))
        p.drawRoundedRect(frame, 10, 10)
        p.end()


class _GlowColorButton(QPushButton):
    """Swatch + "Auto"/hex label. Click opens a color picker."""

    def __init__(self, stats_dialog, key, title, parent=None):
        super().__init__(parent)
        self._stats = stats_dialog
        self._key = key  # "color1" / "color2"
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumWidth(150)
        self.setToolTip("Click to pick a color. 'Auto' uses your theme's accent color.")

    def current_color(self):
        _bg, accent, _dark = _theme_colors(self._stats)
        s = get_backdrop_settings(self._stats.addon_config.config)
        c1, c2 = glow_colors(accent, s)
        return c1 if self._key == "color1" else c2

    def is_auto(self):
        s = get_backdrop_settings(self._stats.addon_config.config)
        return not s[self._key]

    def refresh(self):
        self.setText("     " + ("Auto" if self.is_auto() else self.current_color().upper()))
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor(128, 128, 128, 140), 1))
        p.setBrush(QColor(self.current_color()))
        d = 14
        p.drawEllipse(QRectF(10, (self.height() - d) / 2, d, d))
        p.end()


_SLIDERS = (
    ("tone", "Background tone", 0, 100, "%", "How much deeper than the theme color the window background is."),
    ("glow", "Glow", 0, 100, "%", "Soft light at the top of the window."),
)

_PRESET_BUTTONS = (
    ("off", "Off"),
    ("clean", "Clean"),
    ("subtle", "Subtle"),
    ("balanced", "Balanced"),
    ("vivid", "Vivid"),
)


def build_backdrop_group(dialog) -> QGroupBox:
    """Build the group and wire it to the settings dialog's stats window."""
    stats = dialog.parent_dialog
    cfg = stats.addon_config.config

    group = QGroupBox("Window Background")
    lay = QVBoxLayout(group)
    lay.setContentsMargins(10, 10, 10, 10)
    lay.setSpacing(8)

    hint = QLabel(
        "Background of the Deep Dive window. Pick a style, then adjust if you want. "
        "Changes preview live."
    )
    hint.setObjectName("theme_info_label")
    hint.setWordWrap(True)
    lay.addWidget(hint)

    # Style presets
    preset_row = QHBoxLayout()
    preset_row.setSpacing(6)
    preset_row.addWidget(QLabel("Style:"))
    buttons = {}
    for key, text in _PRESET_BUTTONS:
        btn = QPushButton(text)
        btn.setCheckable(True)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        buttons[key] = btn
        preset_row.addWidget(btn)
    custom_lbl = QLabel("Custom")
    custom_lbl.setObjectName("theme_info_label")
    preset_row.addWidget(custom_lbl)
    preset_row.addStretch()
    reset_btn = QPushButton("Reset")
    reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    reset_btn.setToolTip("Back to the default look (Clean).")
    preset_row.addWidget(reset_btn)
    lay.addLayout(preset_row)

    preview = BackdropPreview(stats)
    lay.addWidget(preview)

    # Glow colors
    color_row = QHBoxLayout()
    color_row.setSpacing(6)
    color_lbl = QLabel("Glow color:")
    color_lbl.setMinimumWidth(120)
    color_row.addWidget(color_lbl)
    color_btns = {}
    auto_btns = {}
    for key, title in (("color1", "Color"),):
        cb = _GlowColorButton(stats, key, title)
        ab = QPushButton("Auto")
        ab.setCursor(Qt.CursorShape.PointingHandCursor)
        ab.setToolTip("Go back to the theme's accent color.")
        color_btns[key] = cb
        auto_btns[key] = ab
        color_row.addWidget(cb)
        color_row.addWidget(ab)
        color_row.addSpacing(8)
    color_row.addStretch()
    lay.addLayout(color_row)

    sliders = {}
    for key, label, lo, hi, suffix, tip in _SLIDERS:
        sl = SettingsSlider(label, BACKDROP_DEFAULTS[key], lo, hi, suffix=suffix, label_min_width=120)
        sl.setToolTip(tip)
        sliders[key] = sl
        lay.addWidget(sl)

    # Theme changes elsewhere in Settings repaint the preview and color buttons.
    flt = get_backdrop_filter(stats)
    if flt is not None:
        flt.add_listener(preview)
        for cb in color_btns.values():
            flt.add_listener(cb)

    apply_timer = QTimer(group)
    apply_timer.setSingleShot(True)
    apply_timer.setInterval(15)

    def sync_controls():
        s = get_backdrop_settings(cfg)
        for key, sl in sliders.items():
            # Sliders stay usable when the effect is Off: moving one turns it back on.
            sl.setValue(s[key])
        preset = matching_preset(s)
        for key, btn in buttons.items():
            btn.setChecked(key == preset)
        custom_lbl.setVisible(preset is None)
        try:
            apply_base_mode_button_styles(buttons, dialog._get_current_theme_effective_palette())
        except Exception:
            log_swallowed()
        for key, cb in color_btns.items():
            cb.refresh()
            auto_btns[key].setVisible(not cb.is_auto())
        preview.update()

    def apply_now():
        refresh_backdrop_settings(stats)
        sync_controls()

    apply_timer.timeout.connect(apply_now)

    def store(new_settings):
        cfg[BACKDROP_KEY] = dict(new_settings)
        apply_timer.start()

    def on_slider(key, value):
        s = get_backdrop_settings(cfg)
        s[key] = int(value)
        s["enabled"] = True
        store(s)

    def on_preset(key):
        s = get_backdrop_settings(cfg)
        if key == "off":
            s["enabled"] = False
        else:
            s.update(BACKDROP_PRESETS[key])
            s["enabled"] = True
        store(s)

    def on_reset():
        store(dict(BACKDROP_DEFAULTS))

    for key, sl in sliders.items():
        sl.slider.valueChanged.connect(lambda v, k=key: on_slider(k, v))
    for key, btn in buttons.items():
        btn.clicked.connect(lambda _c=False, k=key: on_preset(k))
    reset_btn.clicked.connect(on_reset)

    def set_color(key, hex_or_empty):
        s = get_backdrop_settings(cfg)
        s[key] = hex_or_empty
        s["enabled"] = True
        store(s)

    def pick_color(key):
        btn = color_btns[key]
        before = get_backdrop_settings(cfg)[key]
        picker = QColorDialog(QColor(btn.current_color()), dialog)
        picker.setWindowTitle("Glow color")
        # Live preview while choosing; Cancel puts the previous color back.
        picker.currentColorChanged.connect(lambda c, k=key: set_color(k, c.name()))
        if picker.exec():
            set_color(key, picker.selectedColor().name())
        else:
            set_color(key, before)

    for key in color_btns:
        color_btns[key].clicked.connect(lambda _c=False, k=key: pick_color(k))
        auto_btns[key].clicked.connect(lambda _c=False, k=key: set_color(k, ""))

    # Cancel restores the config snapshot; repaint the window from it.
    dialog.rejected.connect(lambda: refresh_backdrop_settings(stats))

    sync_controls()
    dialog._backdrop_sync_controls = sync_controls
    return group
