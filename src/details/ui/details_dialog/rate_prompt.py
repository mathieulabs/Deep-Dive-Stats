# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""A one-line banner in the Deep Dive window asking people who use the add-on to rate it.

It only shows after RATE_MIN_DAYS days and RATE_MIN_OPENS openings of the window, then
again RATE_GAPS_DAYS later (30, then 90 days), so three times at most. A showing only
counts once the banner stayed on screen RATE_SEEN_MS, or "Later" was clicked. "Rate" and "Don't ask again" end it for good. The state is shared by all
profiles and survives updates (user_files).
"""

import json
import os
import time

from aqt.qt import QColor, QFrame, QHBoxLayout, QLabel, QPushButton, QSize, QSizePolicy, Qt, QTimer, QWidget

from ...logic.logger import log_swallowed
from ....qss import set_qss
from ..theme.icons import get_svg_icon
from ...widgets.chart_utils.theme import relative_luminance
from . import links

RATE_MIN_DAYS = 14
RATE_MIN_OPENS = 10
RATE_GAPS_DAYS = (30, 90)
RATE_MAX_SHOWS = len(RATE_GAPS_DAYS) + 1
RATE_SEEN_MS = 12000

_DAY = 86400


def _state_path():
    addon_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
    return os.path.join(addon_dir, "user_files", "rate_prompt.json")


def _load():
    try:
        with open(_state_path(), encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
    except Exception:
        log_swallowed()
        return {}


def _save(state):
    try:
        path = _state_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f)
        os.replace(tmp, path)
    except Exception:
        log_swallowed()


def _should_show(state, now):
    if state.get("preview"):
        return True
    if state.get("done") or state.get("shows", 0) >= RATE_MAX_SHOWS:
        return False
    return (
        state.get("opens", 0) >= RATE_MIN_OPENS
        and now - state.get("first_seen", now) >= RATE_MIN_DAYS * _DAY
        and now >= state.get("snooze_until", 0)
    )


def mark_rated():
    """The rating page was opened from the toolbar: no need to ask anymore."""
    state = _load()
    state["done"] = True
    _save(state)


def preview_next_open():
    """Developer tool: show the banner the next time the Deep Dive window opens."""
    state = _load()
    state["preview"] = True
    _save(state)


def on_open(dialog):
    """Count an opening of the Deep Dive window (new or reused) and show the banner when due."""
    old = getattr(dialog, "rate_banner", None)
    dialog.rate_banner = None
    if old is not None:
        _remove(old)  # left over from the last time this window was open
    now = time.time()
    state = _load()
    state.setdefault("first_seen", now)
    state["opens"] = state.get("opens", 0) + 1
    show = _should_show(state, now)
    preview = bool(state.pop("preview", None)) if show else False
    _save(state)
    if show:
        row = _build_banner(dialog)
        row.setProperty("rate_preview", preview)
        dialog.rate_banner = row
        # Just above the toolbar, the window's last row.
        layout = dialog.main_layout
        layout.insertWidget(max(0, layout.count() - 1), row)
        # Closing the window soon after opening it doesn't use up a showing.
        QTimer.singleShot(RATE_SEEN_MS, lambda: _count_if_seen(row))


def _count_if_seen(row):
    try:
        if row.isVisible():
            _count_show(row)
    except RuntimeError:
        pass  # banner already deleted


def _count_show(row):
    if row.property("rate_counted") or row.property("rate_preview"):
        return
    row.setProperty("rate_counted", True)
    state = _load()
    shows = state.get("shows", 0) + 1
    state["shows"] = shows
    if shows <= len(RATE_GAPS_DAYS):
        state["snooze_until"] = time.time() + RATE_GAPS_DAYS[shows - 1] * _DAY
    _save(state)


def _remove(banner):
    try:
        banner.hide()
        parent = banner.parentWidget()
        if parent is not None and parent.layout() is not None:
            parent.layout().removeWidget(banner)
        banner.deleteLater()
    except RuntimeError:
        pass


def _finish(row, done):
    if not done:
        _count_show(row)  # an explicit "Later" counts even before RATE_SEEN_MS
    else:
        state = _load()
        state["done"] = True
        _save(state)
    _remove(row)


def _build_banner(dialog):
    from ..theme import get_theme_effective_is_dark, get_theme_palette

    conf = dialog.addon_config.config
    is_dark = get_theme_effective_is_dark(conf)
    pal = get_theme_palette(conf, is_dark) or {}

    accent = pal.get("accent", "#58a6ff")
    # White on the accent, unless a custom theme made the accent too light for it.
    on_accent = "#18181b" if relative_luminance(QColor(accent)) > 0.5 else "#ffffff"

    # A compact pill centred above the toolbar, not a bar across the whole window.
    row = QWidget(dialog)
    row.setObjectName("rate_banner_row")
    set_qss(row, "QWidget#rate_banner_row { background: transparent; }")
    row_lay = QHBoxLayout(row)
    row_lay.setContentsMargins(0, 0, 0, 0)
    row_lay.addStretch(1)
    banner = QFrame(row)
    banner.setObjectName("rate_banner")
    banner.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
    row_lay.addWidget(banner)
    row_lay.addStretch(1)

    lay = QHBoxLayout(banner)
    lay.setContentsMargins(16, 6, 7, 6)
    lay.setSpacing(6)

    icon = QLabel(banner)
    icon.setObjectName("rate_banner_icon")
    icon.setPixmap(get_svg_icon("thumbs-up", color=accent, size=18).pixmap(QSize(18, 18)))
    lay.addWidget(icon)
    lay.addSpacing(5)

    text = QLabel("Enjoying Deep Dive Stats? A rating on AnkiWeb helps others find it :)", banner)
    text.setObjectName("rate_banner_text")
    lay.addWidget(text)
    lay.addSpacing(16)

    buttons = (
        ("rate_banner_rate", "Rate", True),
        ("rate_banner_later", "Later", False),
        ("rate_banner_never", "Don't ask again", False),
    )
    for name, label, primary in buttons:
        btn = QPushButton(label, banner)
        btn.setObjectName(name)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.setAutoDefault(False)
        btn.setProperty("rate_primary", primary)
        if primary:
            btn.setIcon(get_svg_icon("thumbs-up", color=on_accent, size=16))
            btn.setIconSize(QSize(16, 16))
        lay.addWidget(btn)

    def on_rate():
        links.open_link(links.RATE_URL)
        _finish(row, True)

    banner.findChild(QPushButton, "rate_banner_rate").clicked.connect(on_rate)
    banner.findChild(QPushButton, "rate_banner_later").clicked.connect(lambda: _finish(row, False))
    banner.findChild(QPushButton, "rate_banner_never").clicked.connect(lambda: _finish(row, True))

    surface = pal.get("bg_surface", "#3a3a3a")
    border = pal.get("border_strong", "#555555")
    text_col = pal.get("text_primary", "#ffffff")
    muted = pal.get("text_secondary", "#d7d7d7")
    accent_hover = pal.get("accent_hover", accent)
    hover = "rgba(255,255,255,0.08)" if is_dark else "rgba(0,0,0,0.06)"
    set_qss(banner, f"""
        QFrame#rate_banner {{
            background: {surface};
            border: 1px solid {border};
            border-radius: 19px;
        }}
        QLabel#rate_banner_icon {{
            background: transparent;
            border: none;
        }}
        QLabel#rate_banner_text {{
            background: transparent;
            border: none;
            color: {text_col};
            font-size: 14px;
        }}
        QFrame#rate_banner QPushButton {{
            background: transparent;
            border: none;
            border-radius: 13px;
            color: {muted};
            font-size: 14px;
            padding: 5px 13px;
            min-width: 0px;
        }}
        QFrame#rate_banner QPushButton:hover {{
            background: {hover};
            color: {text_col};
        }}
        QFrame#rate_banner QPushButton[rate_primary="true"] {{
            background: {accent};
            color: {on_accent};
            font-weight: 600;
        }}
        QFrame#rate_banner QPushButton[rate_primary="true"]:hover {{
            background: {accent_hover};
        }}
    """)
    return row
