# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
import time

from aqt.qt import (
    QFrame, QVBoxLayout, QGridLayout, QLabel, QSizePolicy,
    Qt, QColor, QPropertyAnimation, QEasingCurve, QFontMetrics, QTimer,
    pyqtProperty, QPalette, QEvent, QPainter,
)


class _ColorLabel(QLabel):
    """QLabel that re-applies a forced WindowText color on every PaletteChange.

    Anki sets its theme with QApplication.setPalette(), which resets the effective
    WindowText color of every widget, and a QSS 'color:' on the widget itself does
    not reliably win in Qt6. So the palette color is re-applied each time.
    """

    _forced_color: str = ""
    _setting_palette: bool = False

    def force_color(self, color: str):
        self._forced_color = color or ""
        self._apply_forced_palette()

    def _apply_forced_palette(self):
        if not self._forced_color or self._setting_palette:
            return
        self._setting_palette = True
        pal = self.palette()
        pal.setColor(QPalette.ColorGroup.All, QPalette.ColorRole.WindowText, QColor(self._forced_color))
        self.setPalette(pal)
        self._setting_palette = False

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QEvent.Type.PaletteChange, QEvent.Type.StyleChange):
            self._apply_forced_palette()


class _TitleLabel(_ColorLabel):
    """Card title that ends with "..." when the card is too narrow, instead of being cut."""

    def paintEvent(self, event):
        text = self.text()
        rect = self.contentsRect()
        fm = self.fontMetrics()
        if not text or fm.horizontalAdvance(text) <= rect.width():
            return super().paintEvent(event)
        shown = fm.elidedText(text, Qt.TextElideMode.ElideRight, rect.width())
        p = QPainter(self)
        self.style().drawItemText(
            p, rect, int(self.alignment().value), self.palette(), self.isEnabled(), shown, self.foregroundRole()
        )
        p.end()
from ...chart_utils import is_night_mode
from ...chart_utils.formatting import fmt_num
from ....animations.hover_effect import StatCardEffect
from ....animations.motion import animations_enabled
from ..ui.style import (
    title_label_style,
    value_label_style,
    theme_title_color,
)
from ..ui.sizing import (
    ideal_measure_font_sizes,
)
from ..ui.value_roll import (
    parse_roll_value,
    is_na_like,
    time_unit_kind,
    convert_time_value,
)
from ..ui.widget_modes import (
    title_size_multiplier,
    apply_inline_layout_mode,
    set_title_visible as set_widget_title_visible,
    set_centered as set_widget_centered,
)
from ..logic.widget_updates import (
    refresh_theme as refresh_theme_impl,
    update_val as update_val_impl,
    request_container_refresh as request_container_refresh_impl,
)
from ..logic.widget_persistence import (
    pick_card_color as pick_card_color_impl,
    set_card_color as set_card_color_impl,
    persist_lock_state as persist_lock_state_impl,
)
from ..logic.config_io import (
    addon_config as load_addon_config,
    addon_meta as load_addon_meta,
    write_addon_config,
    write_addon_config_vals,
)
from ..logic.card_dnd import handle_mouse_press, handle_mouse_move, handle_mouse_release
from ..ui.card_visibility import set_card_opacity
from .....qss import set_qss
from ..ui.card_style_runtime import paint_hover_effect, apply_visual_style as apply_visual_style_impl
from ..logic.constants import (
    ROLL_ANIM_DURATION_MS,
    ANIM_DISABLED_DURATION_MS,
    ROLL_LAYOUT_REFRESH_THROTTLE_S,
)


class StatCardWidget(QFrame):
    def __init__(self, title, value, subtitle="", icon=None, color="#8ab4f8", parent=None, config_key=None, deck_id=None, time_span=None, is_pinned=False, widget_id=None, addon_config=None, stat_type=None):
        super().__init__(parent)
        # Set the final object name before the first stylesheet pass.
        # If renamed later, Qt can keep a stale style until next polish/refresh.
        self.setObjectName("pinned_widget_card" if is_pinned else "StatCard")
        self.widget_id = widget_id
        self.config_key = config_key
        self.display_name = title
        self.deck_id = deck_id
        self.time_span = time_span
        self.is_pinned = is_pinned
        self.stat_type = stat_type

        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.addon_config = addon_config if addon_config is not None else load_addon_config(__name__)

        if stat_type:
            from ....ui import get_color
            color_ctx = "pinned" if self.is_pinned else self
            self.base_color = get_color(self.addon_config, stat_type, color_ctx)
        else:
            self.base_color = color

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 2, 12, 6)
        self.main_layout = layout

        title_col = theme_title_color(is_night_mode(self), self)
        self.title_col = title_col

        layout.addStretch()
        self._content_grid = QGridLayout()
        self._content_grid.setContentsMargins(0, 0, 0, 0)
        self._content_grid.setHorizontalSpacing(0)
        self._content_grid.setVerticalSpacing(2)

        display_title = f"{icon}  {title.upper()}" if icon else title.upper()
        self.title_lbl = _TitleLabel(display_title, parent=self)
        self.title_lbl.setObjectName("StatCardTitle")
        set_qss(self.title_lbl, title_label_style(0))
        self.title_lbl.setMinimumWidth(1)
        self.title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_lbl)

        self.value_lbl = _ColorLabel(value, parent=self)
        self.value_lbl.setObjectName("StatCardValue")
        set_qss(self.value_lbl, value_label_style(False))
        self.value_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.value_lbl.setMinimumWidth(1)
        self._content_grid.addWidget(self.title_lbl, 0, 0)
        self._content_grid.addWidget(self.value_lbl, 1, 0)
        layout.addLayout(self._content_grid)

        self._roll_progress = 1.0
        self._roll_active = False
        self._roll_start = 0.0
        self._roll_end = 0.0
        self._roll_kind = None
        self._roll_decimals = 0
        self._roll_prefix = ""
        self._roll_suffix = ""
        self._roll_target_text = ""
        self._roll_origin_text = ""
        self._roll_anim = QPropertyAnimation(self, b"rollProgress")
        roll_scope = "pinned" if bool(self.is_pinned) else "details"
        self._roll_anim.setDuration(ROLL_ANIM_DURATION_MS if animations_enabled(roll_scope) else ANIM_DISABLED_DURATION_MS)
        self._roll_anim.setStartValue(0.0)
        self._roll_anim.setEndValue(1.0)
        self._roll_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._roll_anim.finished.connect(self._finish_value_roll)
        self._roll_width_progress = 1.0
        self._roll_width_active = False
        self._roll_width_start = 0.0
        self._roll_width_end = 0.0
        self._roll_width_override = None
        self._roll_width_scale = 1.0
        self._roll_width_anim = QPropertyAnimation(self, b"rollWidthProgress")
        self._roll_width_anim.setDuration(ROLL_ANIM_DURATION_MS if animations_enabled(roll_scope) else ANIM_DISABLED_DURATION_MS)
        self._roll_width_anim.setStartValue(0.0)
        self._roll_width_anim.setEndValue(1.0)
        self._roll_width_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._roll_width_anim.finished.connect(self._finish_roll_width)
        self._last_roll_layout_refresh_ts = 0.0

        self.sub_lbl = None
        if subtitle:
            self.sub_lbl = _ColorLabel(subtitle, parent=self)
            self.sub_lbl.setObjectName("StatCardSubtitle")
            self.sub_lbl.setVisible(False)
            set_qss(self.sub_lbl, "font-weight: 400;")
            layout.addWidget(self.sub_lbl)

        layout.addStretch()
        self._inline_mode_active = None
        self._apply_inline_layout_mode()

        self._val_font = self.value_lbl.font()
        self._title_font = self.title_lbl.font()
        if self.sub_lbl:
            self._sub_font = self.sub_lbl.font()

        self._is_ghost = False
        self._is_loading = (value == "...")

        self.set_font_sizes(6.5, 4.5, 5.25, 4)

        # Generalized Fire/Glow effect: default fallback value is set first,
        # then update_style_params() applies the real configured opacity.
        self._effect = StatCardEffect(self)
        self._max_effect_opacity = 0.5
        self.apply_visual_style()
        self.update_style_params(self.base_color, self.title_col)

        # Unlocked effects are read from the config (locked by default)
        unlocked_list = self.addon_config.get("UNLOCKED_EFFECTS", [])
        card_id = self.widget_id or self.config_key
        if card_id and card_id not in unlocked_list:
            self._effect.toggle_lock()

    @pyqtProperty(float)
    def rollProgress(self):
        return self._roll_progress

    @rollProgress.setter
    def rollProgress(self, val):
        self._roll_progress = float(val)
        if not self._roll_active:
            return
        t = max(0.0, min(1.0, self._roll_progress))
        curr = self._roll_start + ((self._roll_end - self._roll_start) * t)
        if self._roll_kind == "percent":
            txt = f"{curr:.{self._roll_decimals}f}%"
        else:
            if self._roll_decimals > 0:
                txt = f"{curr:,.{self._roll_decimals}f}"
            else:
                txt = fmt_num(int(round(curr)))
            txt = f"{self._roll_prefix}{txt}{self._roll_suffix}"
        self.value_lbl.setText(txt)

    @pyqtProperty(float)
    def rollWidthProgress(self):
        return self._roll_width_progress

    @rollWidthProgress.setter
    def rollWidthProgress(self, val):
        self._roll_width_progress = float(val)
        if not self._roll_width_active:
            return
        t = max(0.0, min(1.0, self._roll_width_progress))
        self._roll_width_override = self._roll_width_start + (
            (self._roll_width_end - self._roll_width_start) * t
        )
        self._schedule_roll_layout_refresh()

    def _active_layout_scale(self) -> float:
        p = self.parentWidget()
        while p:
            scale = getattr(p, "_scale", None)
            if scale is not None:
                try:
                    return max(0.1, float(scale))
                except Exception:
                    return 1.0
            p = p.parentWidget() if hasattr(p, "parentWidget") else None
        return 1.0

    def _ideal_width_for_value_text(self, value_text, scale=1.0) -> int:
        sizes = ideal_measure_font_sizes(
            self.is_pinned,
            scale=scale,
            title_multiplier=self._title_size_multiplier(),
        )

        val_f = self.value_lbl.font()
        val_f.setPointSizeF(sizes["value_fs"])
        fm_val = QFontMetrics(val_f)

        title_f = self.title_lbl.font()
        title_f.setPointSizeF(sizes["title_fs"])
        fm_title = QFontMetrics(title_f)

        w_val = fm_val.horizontalAdvance(value_text or "")
        w_title = fm_title.horizontalAdvance(self.title_lbl.text())

        if bool(getattr(self, "_inline_mode_active", False)):
            return int(w_title + w_val + (34 * scale))
        return int(max(w_val, w_title) + (24 * scale) + 10)

    def _schedule_roll_layout_refresh(self, force=False) -> None:
        if not self.is_pinned:
            return
        now = time.perf_counter()
        if force or (now - self._last_roll_layout_refresh_ts) >= ROLL_LAYOUT_REFRESH_THROTTLE_S:
            self._last_roll_layout_refresh_ts = now
            self._request_container_refresh()

    def _start_roll_width_animation(self, old_text, new_text) -> None:
        if not self.is_pinned:
            self._roll_width_anim.stop()
            self._roll_width_active = False
            self._roll_width_override = None
            return
        scale = self._active_layout_scale()
        start_width = self._ideal_width_for_value_text(old_text, scale=scale)
        end_width = self._ideal_width_for_value_text(new_text, scale=scale)
        if abs(start_width - end_width) <= 1:
            self._roll_width_anim.stop()
            self._roll_width_active = False
            self._roll_width_override = None
            self._schedule_roll_layout_refresh(force=True)
            return
        self._roll_width_anim.stop()
        self._roll_width_active = True
        self._roll_width_start = float(start_width)
        self._roll_width_end = float(end_width)
        self._roll_width_scale = float(scale)
        self._roll_width_progress = 0.0
        self._roll_width_override = float(start_width)
        self._last_roll_layout_refresh_ts = 0.0
        self._schedule_roll_layout_refresh(force=True)
        self._roll_width_anim.start()
        roll_scope = "pinned" if bool(self.is_pinned) else "details"
        if not animations_enabled(roll_scope):
            self._finish_roll_width()

    def _finish_roll_width(self):
        self._roll_width_active = False
        self._roll_width_override = None
        self._schedule_roll_layout_refresh(force=True)

    def _start_value_roll(self, old_text, new_text):
        if self.isHidden():
            # Switched-off dashboard cards still get new values; nobody sees them roll.
            return False
        old_spec = parse_roll_value(old_text)
        new_spec = parse_roll_value(new_text)
        # Special case for retention-like values that can become "N/A":
        # animate through 0% instead of jumping.
        if (not old_spec or not new_spec):
            old_na = is_na_like(old_text)
            new_na = is_na_like(new_text)
            if old_spec and new_na and old_spec[0] == "percent":
                kind, _v, dec, prefix, suffix = old_spec
                new_spec = (kind, 0.0, dec, prefix, suffix or "%")
            elif new_spec and old_na and new_spec[0] == "percent":
                kind, _v, dec, prefix, suffix = new_spec
                old_spec = (kind, 0.0, dec, prefix, suffix or "%")

        if not old_spec or not new_spec:
            return False
        old_kind, old_val, _old_dec, old_prefix, old_suffix = old_spec
        new_kind, new_val, new_dec, new_prefix, new_suffix = new_spec
        if old_kind != new_kind:
            return False
        if old_prefix != new_prefix or old_suffix != new_suffix:
            # Allow roll across time unit switches (e.g. "150.06 h" <-> "0 min")
            # by normalizing both sides to a single display unit.
            old_tu = time_unit_kind(old_suffix)
            new_tu = time_unit_kind(new_suffix)
            if old_kind == "number" and old_prefix == new_prefix and old_tu and new_tu:
                canonical = "hour" if ("hour" in (old_tu, new_tu)) else "minute"
                old_val = convert_time_value(old_val, old_tu, canonical)
                new_val = convert_time_value(new_val, new_tu, canonical)
                old_suffix = " h" if canonical == "hour" else " min"
                new_suffix = old_suffix
                new_dec = max(_old_dec, new_dec, 2 if canonical == "hour" else 0)
            else:
                return False
        if abs(old_val - new_val) < 1e-9:
            return False

        self._roll_anim.stop()
        self._roll_active = True
        self._roll_start = old_val
        self._roll_end = new_val
        self._roll_kind = new_kind
        self._roll_decimals = new_dec
        self._roll_prefix = new_prefix
        self._roll_suffix = new_suffix
        self._roll_progress = 0.0
        self._roll_target_text = new_text
        self._roll_origin_text = old_text
        self._start_roll_width_animation(old_text, new_text)
        self._roll_anim.start()
        roll_scope = "pinned" if bool(self.is_pinned) else "details"
        if not animations_enabled(roll_scope):
            self._finish_value_roll()
        return True

    def _finish_value_roll(self):
        self._roll_active = False
        if self._roll_target_text:
            self.value_lbl.setText(self._roll_target_text)
        # Re-apply responsive sizing from the true final text after interpolation.
        if not self._roll_width_active:
            QTimer.singleShot(0, self._request_container_refresh)

    def _title_size_multiplier(self):
        return title_size_multiplier(self)

    def _apply_inline_layout_mode(self):
        apply_inline_layout_mode(self)

    def set_title_visible(self, visible: bool):
        set_widget_title_visible(self, visible)

    def enterEvent(self, event):
        if getattr(self, "hover_effect_enabled", True):
            self._effect.start()
            self.update()  # locked glow: repaint for the hover boost
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._effect.stop()
        self.update()
        super().leaveEvent(event)

    def contextMenuEvent(self, event):
        """Let parent container handle context menu for unified experience."""
        event.ignore()

    def _pick_color(self):
        """Pick the card's color: its own one when it has own colors, else the shared one
        of its stat (see logic/widget_persistence.set_card_color)."""
        pick_card_color_impl(
            self,
            read_config_fn=lambda: self.addon_config,
            write_updates_fn=lambda updates: write_addon_config_vals(__name__, updates),
            refresh_fn=self.refresh_theme,
        )

    def _reset_color(self):
        """Back to the shared color of the stat."""
        set_card_color_impl(
            self,
            None,
            conf=self.addon_config,
            write_updates_fn=lambda updates: write_addon_config_vals(__name__, updates),
            refresh_fn=self.refresh_theme,
        )

    def paintEvent(self, event):
        super().paintEvent(event)
        paint_hover_effect(self)

    def apply_visual_style(self):
        apply_visual_style_impl(self)

    def update_style_params(self, color, title_col):
        """Set label text colors via _ColorLabel.force_color (palette-based, PaletteChange-resistant)."""
        params = (color, title_col)
        if getattr(self, "_last_color_params", None) == params:
            return
        self._last_color_params = params
        self.value_lbl.force_color(color)
        self.title_lbl.force_color(title_col)
        if self.sub_lbl:
            self.sub_lbl.force_color(title_col)

    def refresh_theme(self, conf=None):
        refresh_theme_impl(self, conf=conf, load_config_fn=lambda: load_addon_config(__name__))

    def set_font_sizes(self, val_fs, title_fs, sub_fs, h_margin=18):
        """Externally set font sizes for synchronization (using floats for smoothness)."""
        title_fs = float(title_fs) * self._title_size_multiplier()
        params = (float(val_fs), float(title_fs), float(sub_fs), int(h_margin))
        if getattr(self, "_last_font_params", None) == params:
            return
        self._last_font_params = params

        self._val_font.setPointSizeF(float(val_fs))
        self.value_lbl.setFont(self._val_font)

        self._title_font.setPointSizeF(float(title_fs))
        self.title_lbl.setFont(self._title_font)

        if self.sub_lbl:
            self._sub_font.setPointSizeF(float(sub_fs))
            self.sub_lbl.setFont(self._sub_font)

        self.main_layout.setContentsMargins(int(h_margin), 6, int(h_margin), 6)

    def shown_value(self):
        """The value the card shows, or the one it is rolling to (the label holds an
        in-between number during the roll)."""
        if self._roll_active and self._roll_target_text:
            return self._roll_target_text
        return self.value_lbl.text()

    def update_val(self, value, color=None, title=None, subtitle=None, deck_id=None, refresh=True):
        update_val_impl(
            self,
            value,
            color=color,
            title=title,
            subtitle=subtitle,
            deck_id=deck_id,
            refresh=refresh,
            refresh_theme_fn=self.refresh_theme,
            request_refresh_fn=self._request_container_refresh,
        )

    def _request_container_refresh(self):
        request_container_refresh_impl(self)

    def set_centered(self, centered: bool = True):
        """Alignment: centered (usually pinned) or left (usually dashboard)."""
        set_widget_centered(self, centered)

    def mousePressEvent(self, event):
        handle_mouse_press(self, event)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not handle_mouse_move(self, event):
            return super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        handle_mouse_release(self, event)
        super().mouseReleaseEvent(event)

    def _persist_lock_state(self):
        """Save the current lock state to config without overwriting other settings."""
        persist_lock_state_impl(
            self,
            read_meta_fn=lambda: load_addon_meta(__name__),
            write_config_fn=lambda conf: write_addon_config(__name__, conf),
        )

    def setOpacity(self, opacity):
        set_card_opacity(self, opacity)

    def get_height_ideal_width(self, scale=1.0):
        """Width this card would want with a typical value: the dashboard height is
        computed from it, so it does not change with the values."""
        return self._ideal_width_for_value_text("0.00%", scale=scale)

    def get_ideal_width(self, scale=1.0):
        """Calculates the width this card PREFERS at max font size."""
        natural_width = self._ideal_width_for_value_text(self.value_lbl.text(), scale=scale)
        if self._roll_width_override is not None and abs(float(scale) - float(self._roll_width_scale)) < 0.001:
            return int(max(round(float(self._roll_width_override)), natural_width))
        return natural_width
