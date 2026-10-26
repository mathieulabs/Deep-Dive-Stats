# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors

from aqt import mw
from aqt.qt import (
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QPoint,
    QPushButton,
    QSize,
    QSizePolicy,
    QSpacerItem,
    Qt,
    QVBoxLayout,
    QWidget,
)

from .. import Config
from ..theme.icons import get_svg_icon
from ..theme import get_theme_effective_is_dark, get_theme_palette
from ..theme.color_utils import hex_to_rgba
from .dashboard import setup_dashboard_and_overlays
from ..shared.menu import StyledMenu
from .visual_menu import populate_visual_menu


from ....qss import set_qss

def layout_button_icons(side):
    """Icons of the three layout buttons. The arrows point where the table goes: with the
    table on the right, left grows it and right hides it; with the table at the bottom, up
    and down."""
    if side:
        return ("chevron-left", "columns", "chevron-right")
    return ("chevron-up", "rows", "chevron-down")


def setup_dialog_ui(dialog):
    dialog.main_layout = QVBoxLayout(dialog)
    dialog.main_layout.setContentsMargins(14, 10, 14, 10)
    dialog.main_layout.setSpacing(8)

    top_bar = QHBoxLayout()
    top_bar.setContentsMargins(10, 5, 10, 5)
    top_bar.setSpacing(10)
    is_deck_view = dialog.view_mode != 'time'
    dialog.view_toggle_btn = QPushButton("  View by Deck" if not is_deck_view else "  View by Time", parent=dialog)
    dialog.view_toggle_btn.setIcon(get_svg_icon("activity" if not is_deck_view else "calendar", size=16))
    dialog.view_toggle_btn.setIconSize(QSize(16, 16))
    dialog.view_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    dialog.view_toggle_btn.clicked.connect(dialog.toggle_view)
    dialog.view_toggle_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    dialog.view_toggle_btn.setAutoDefault(False)
    dialog.view_toggle_btn.setDefault(False)
    dialog.view_toggle_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    dialog.visual_toggle = QPushButton(" Visuals", parent=dialog)
    dialog.visual_toggle.setIcon(get_svg_icon("bar-chart-2"))
    dialog.visual_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
    dialog.visual_toggle.setToolTip("Choose which columns are shown as a visual")
    visual_menu = StyledMenu(dialog)
    # The menu outlives theme changes: restyle it each time it opens.
    visual_menu.aboutToShow.connect(visual_menu._apply_theme_style)
    dialog._visual_actions = populate_visual_menu(dialog, visual_menu)
    dialog.visual_toggle.setMenu(visual_menu)
    dialog.visual_toggle.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    conf = dialog.addon_config.config
    palette = get_theme_palette(conf) or {}
    is_dark = get_theme_effective_is_dark(conf)

    dialog.settings_btn = QPushButton("  Settings", parent=dialog)
    dialog.settings_btn.setIcon(get_svg_icon("settings", size=16))
    dialog.settings_btn.setIconSize(QSize(16, 16))
    dialog.settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    dialog.settings_btn.clicked.connect(dialog.open_settings)
    dialog.settings_btn.setProperty("class", "toolbar_btn")
    dialog.settings_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    dialog.deck_opts_btn = QPushButton("  Deck Options", parent=dialog)
    dialog.deck_opts_btn.setIcon(get_svg_icon("palette", size=16))
    dialog.deck_opts_btn.setIconSize(QSize(16, 16))
    dialog.deck_opts_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    dialog.deck_opts_btn.clicked.connect(dialog.open_deck_options)
    dialog.deck_opts_btn.setProperty("class", "toolbar_btn")
    dialog.deck_opts_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    dialog.export_btn = QPushButton("  Export", parent=dialog)
    dialog.export_btn.setIcon(get_svg_icon("save", size=16))
    dialog.export_btn.setIconSize(QSize(16, 16))
    dialog.export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    dialog.export_btn.setProperty("class", "toolbar_btn")
    set_qss(dialog.export_btn, "QPushButton::menu-indicator { image: none; width: 0px; height: 0px; subcontrol-position: right; border: none; }")
    dialog.export_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    setup_dashboard_and_overlays(dialog)

    dialog.trend_toggle = QPushButton("  Trends", parent=dialog)
    dialog.trend_toggle.setIcon(get_svg_icon("trending-up", size=16))
    dialog.trend_toggle.setIconSize(QSize(16, 16))
    dialog.trend_toggle.setCheckable(True)
    dialog.trend_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
    dialog.trend_toggle.setProperty("class", "toolbar_btn")
    dialog.trend_toggle.setChecked(dialog.addon_config.config.get(Config.SHOW_TRENDS, False))
    dialog.trend_toggle.clicked.connect(dialog.on_trend_toggled)
    dialog.trend_toggle.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    dialog.view_toggle_btn.setProperty("class", "toolbar_btn")

    dialog.visual_toggle.setProperty("class", "toolbar_btn")

    search_layout = QHBoxLayout()
    search_layout.setSpacing(8)

    search_container = QWidget(dialog)
    search_container.setMinimumWidth(100) # Allow shrinking further
    search_container.setMaximumWidth(400) # But don't grow too much
    search_container_layout = QHBoxLayout(search_container)
    search_container_layout.setContentsMargins(0, 0, 0, 0)
    search_container_layout.setSpacing(0)

    dialog.search_bar = QLineEdit(parent=search_container)
    dialog.search_bar.setPlaceholderText("Search decks...")
    dialog.search_bar.setProperty("class", "search_bar")
    dialog.search_bar.setMinimumWidth(40)
    dialog.search_bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    dialog.search_bar.textChanged.connect(dialog._on_search_text_changed)

    dialog.search_clear_btn = QPushButton(parent=dialog.search_bar)
    icon_col = palette.get("text_secondary", "#a1a1aa")
    dialog.search_clear_btn.setIcon(get_svg_icon("x", color=icon_col, size=14))
    dialog.search_clear_btn.setIconSize(QSize(14, 14))
    dialog.search_clear_btn.setFixedSize(18, 18)
    dialog.search_clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    dialog.search_clear_btn.setVisible(False)
    dialog.search_clear_btn.setProperty("class", "search_clear_btn")

    def on_search_text_changed(text):
        dialog.search_clear_btn.setVisible(bool(text))
        dialog._on_search_text_changed(text)

    def clear_search():
        dialog.search_bar.clear()

    dialog.search_bar.textChanged.disconnect()
    dialog.search_bar.textChanged.connect(on_search_text_changed)
    dialog.search_clear_btn.clicked.connect(clear_search)

    dialog.span_select_btn = QPushButton("  Time Span", parent=dialog)
    dialog.span_select_btn.setIcon(get_svg_icon("calendar", size=16))
    dialog.span_select_btn.setIconSize(QSize(16, 16))
    dialog.span_select_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    dialog.span_select_btn.setProperty("class", "toolbar_btn")
    dialog.span_select_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    dialog.span_select_btn.setVisible(False) # Only visible when Deep Dive is active

    def on_span_select_clicked():
        from .. import Period
        from ..shared.span_menu import populate_span_menu
        from ..shared.menu import StyledMenu

        manager = dialog.deep_dive_manager
        current_span = getattr(manager, 'last_period_range', Period.TOTAL)
        if current_span is None: current_span = Period.TOTAL

        current_idx = dialog.tab_widget.currentIndex()
        _active_tabs = dialog.get_active_tabs_config()
        tab_config = _active_tabs[current_idx] if 0 <= current_idx < len(_active_tabs) else {}
        current_days = tab_config.get("custom_days", 7)

        menu = StyledMenu(dialog)

        def on_update_span(v, d=None):
            # Same logic as context menu, but trigger a full dashboard rebuild using the existing manager state
            deck_id = getattr(manager, 'last_deck_identifier', None)
            title = getattr(manager, 'last_title', "Details")
            manager.open_deep_dive(deck_id, title, period_range=v)

        from ..shared.zoom_span import create_span_from_zoom, find_zoomed_chart

        zoomed = find_zoomed_chart(dialog.expanded_container)

        def on_zoom_span(chart=zoomed):
            code = create_span_from_zoom(chart, dialog.addon_config, parent=dialog)
            if code is not None:
                on_update_span(code)

        populate_span_menu(
            menu,
            current_span,
            current_days,
            on_update_span,
            dialog.addon_config,
            on_manage_callback=lambda: dialog.open_settings(start_tab="Time Span"),
            on_zoom_callback=on_zoom_span if zoomed is not None else None,
        )

        menu.exec(dialog.span_select_btn.mapToGlobal(QPoint(0, -menu.sizeHint().height())))

    dialog.span_select_btn.clicked.connect(on_span_select_clicked)

    dialog.deck_select_btn = QPushButton("  Deck", parent=dialog)
    dialog.deck_select_btn.setIcon(get_svg_icon("layers", size=16))
    dialog.deck_select_btn.setIconSize(QSize(16, 16))
    dialog.deck_select_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    dialog.deck_select_btn.setProperty("class", "toolbar_btn")
    dialog.deck_select_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    dialog.deck_select_btn.setVisible(False) # Only visible when Deep Dive is active

    def on_deck_select_clicked():
        from ...widgets.pinned import DeckSelectorDialog
        manager = dialog.deep_dive_manager
        current_deck_id = getattr(manager, 'last_deck_identifier', None)

        # Provide "0" (Collection) but not "Adaptive" (None) directly as we want an absolute selection here
        sel_dialog = DeckSelectorDialog(current_deck_id, parent=dialog, show_adaptive=False, is_deep_dive=True)
        if sel_dialog.exec():
            new_did = sel_dialog.selected_deck_id

            period_range = getattr(manager, 'last_period_range', None)

            if new_did in [0, "0", None]:
                new_title = "Collection"
            else:
                try:
                    all_decks = mw.col.decks.all_names_and_ids()
                    new_title = next((d.name for d in all_decks if str(d.id) == str(new_did)), str(new_did))
                    new_title = new_title.split("::")[-1]
                except Exception:
                    new_title = str(new_did)

            manager.open_deep_dive(new_did, new_title, period_range=period_range)

    dialog.deck_select_btn.clicked.connect(on_deck_select_clicked)

    search_container_layout.addWidget(dialog.search_bar)

    dialog.search_clear_btn.setParent(dialog.search_bar)

    def update_clear_btn_pos():
        h = dialog.search_bar.height()
        w = dialog.search_bar.width()
        y = (h - 18) // 2
        dialog.search_clear_btn.move(w - 26, y)

    def on_search_resize(event):
        QLineEdit.resizeEvent(dialog.search_bar, event)
        update_clear_btn_pos()

    dialog.search_bar.resizeEvent = on_search_resize
    update_clear_btn_pos()

    search_layout.addWidget(dialog.view_toggle_btn)

    dialog.layout_btns = []
    is_dark = get_theme_effective_is_dark(conf)
    bg_btn = "rgba(255, 255, 255, 0.05)" if is_dark else "rgba(0, 0, 0, 0.03)"
    border_clr = "rgba(255, 255, 255, 0.1)" if is_dark else "rgba(0, 0, 0, 0.1)"

    bg_btn = palette.get("bg_element", bg_btn)
    border_clr = palette.get("border_subtle", border_clr)

    dialog.layout_toggle_container = QFrame(dialog)
    dialog.layout_toggle_container.setObjectName("layout_toggle_container")
    dialog.layout_toggle_container.setVisible(False) # Hidden by default

    container_border = "#52525b" if is_dark else "#d4d4d8"
    container_border = palette.get("border_strong", container_border)
    set_qss(dialog.layout_toggle_container, f"""
        QFrame#layout_toggle_container {{ 
            background: transparent; 
            border: 1px solid {container_border}; 
            border-radius: 8px;
        }}
    """)
    layout_inner = QHBoxLayout(dialog.layout_toggle_container)
    layout_inner.setContentsMargins(2, 2, 2, 2)
    layout_inner.setSpacing(0)

    btn_bg_start = "#27272a" if is_dark else "#f4f4f5"
    btn_bg_end = "#18181b" if is_dark else "#e4e4e7"
    btn_hover_start = "#3f3f46" if is_dark else "#e4e4e7"
    btn_hover_end = "#27272a" if is_dark else "#d4d4d8"
    btn_border = "#52525b" if is_dark else "#d4d4d8"

    # Palette overrides
    btn_bg_start = palette.get("bg_surface", btn_bg_start)
    btn_bg_end = palette.get("bg_root", btn_bg_end)
    btn_hover_start = palette.get("bg_element", btn_hover_start)
    btn_hover_end = palette.get("bg_surface", btn_hover_end)
    btn_border = palette.get("border_strong", btn_border)

    # Three states: the table alone, the charts with the table drawer open, the charts alone.
    for i, (icon_name, tooltip) in enumerate(zip(
        layout_button_icons(dialog.side_view),
        ("Full Table", "Charts with table drawer", "Full Deep Dive"),
    )):
        btn = QPushButton("", parent=dialog.layout_toggle_container)
        btn.setIcon(get_svg_icon(icon_name, size=16))
        btn.setProperty("icon_name", icon_name)
        btn.setIconSize(QSize(16, 16))
        btn.setCheckable(True)
        btn.setFixedSize(30, 24)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setToolTip(tooltip)
        btn.setFlat(True)
        btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        _acc = palette.get("accent", "#3b82f6")
        _acc_a1 = hex_to_rgba(_acc, 0.10)
        _acc_a2 = hex_to_rgba(_acc, 0.20 if is_dark else 0.12)
        _acc_a15 = hex_to_rgba(_acc, 0.15)
        style = f"""
            QPushButton {{
                background: transparent;
                border: 1px solid transparent;
                border-radius: 0px;
                padding: 0px;
            }}
            QPushButton:hover {{
                background: {_acc_a1};
                border: 1px solid transparent;
            }}
            QPushButton:checked {{
                background-color: {_acc_a2};
                border: 1px solid {_acc};
            }}
            QPushButton:checked:hover {{
                background-color: {_acc_a2};
                border: 1px solid {_acc};
            }}
            QPushButton:pressed {{
                background: {_acc_a15};
                border: 1px solid transparent;
            }}
        """

        if i == 0: style += "QPushButton { border-top-left-radius: 7px; border-bottom-left-radius: 7px; }"
        if i == 1: style += f"QPushButton {{ border-left: 1px solid {border_clr}; border-right: 1px solid {border_clr}; }}"
        if i == 2: style += "QPushButton { border-top-right-radius: 7px; border-bottom-right-radius: 7px; }"

        set_qss(btn, style)
        btn.clicked.connect(lambda checked, idx=i: dialog.switch_layout(idx))
        layout_inner.addWidget(btn)
        dialog.layout_btns.append(btn)

    search_layout.addWidget(dialog.deck_select_btn)
    search_layout.addWidget(dialog.span_select_btn)
    search_layout.addWidget(dialog.layout_toggle_container)
    search_layout.addSpacing(10)

    top_bar.addLayout(search_layout)

    top_bar.addSpacerItem(QSpacerItem(40, 10, QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Minimum))

    top_bar.addSpacing(12)

    dialog.overflow_btn = QPushButton("", parent=dialog)
    dialog.overflow_btn.setIcon(get_svg_icon("chevron-down"))
    dialog.overflow_btn.setIconSize(QSize(20, 20))
    dialog.overflow_btn.setFixedSize(30, 30)
    dialog.overflow_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    dialog.overflow_btn.setToolTip("More Options")
    dialog.overflow_btn.setProperty("class", "toolbar_btn")
    set_qss(dialog.overflow_btn, "QPushButton { min-width: 30px; padding: 0; } QPushButton::menu-indicator { image: none; width: 0px; }")
    dialog.overflow_btn.setVisible(False)

    dialog.right_button_container = QWidget(dialog)
    set_qss(dialog.right_button_container, "background: transparent;")
    dialog.right_button_layout = QHBoxLayout(dialog.right_button_container)
    dialog.right_button_layout.setContentsMargins(0, 0, 0, 0)
    dialog.right_button_layout.setSpacing(8)

    dialog.right_button_layout.addWidget(search_container) # Search on the right, left of visual
    dialog.right_button_layout.addSpacing(4)
    dialog.right_button_layout.addWidget(dialog.visual_toggle)
    dialog.right_button_layout.addWidget(dialog.trend_toggle)
    dialog.right_button_layout.addWidget(dialog.export_btn)
    dialog.right_button_layout.addWidget(dialog.deck_opts_btn)
    dialog.right_button_layout.addWidget(dialog.settings_btn)

    from . import links as _links
    for _attr, _icon, _tip, _url_name in (
        ("support_btn", "heart", "Support on Ko-fi", "SUPPORT_URL"),
        ("rate_btn", "thumbs-up", "Rate this add-on", "RATE_URL"),
        ("github_btn", "github", "GitHub", "GITHUB_URL"),
    ):
        if not getattr(_links, _url_name):
            continue  # no URL set: no button
        _btn = QPushButton("", parent=dialog)
        _btn.setIcon(get_svg_icon(_icon, size=16))
        _btn.setIconSize(QSize(16, 16))
        _btn.setFixedSize(30, 30)
        _btn.setCursor(Qt.CursorShape.PointingHandCursor)
        _btn.setToolTip(_tip)
        _btn.setProperty("class", "toolbar_btn")
        set_qss(_btn, "QPushButton { min-width: 30px; padding: 0; }")
        _btn.clicked.connect(lambda _=False, _n=_url_name: _links.open_link(getattr(_links, _n)))
        if _attr == "rate_btn":
            from .rate_prompt import mark_rated
            _btn.clicked.connect(lambda _=False: mark_rated())
        setattr(dialog, _attr, _btn)
        dialog.right_button_layout.addWidget(_btn)

    top_bar.addWidget(dialog.right_button_container)
    top_bar.addWidget(dialog.overflow_btn)

    toolbar_container = QFrame(dialog)
    toolbar_container.setObjectName("toolbar_shell")
    toolbar_layout = QVBoxLayout(toolbar_container)
    toolbar_layout.setContentsMargins(0, 0, 0, 0)
    toolbar_layout.setSpacing(0)

    toolbar_widget = QWidget(toolbar_container)
    set_qss(toolbar_widget, "QWidget { background-color: transparent; }")
    toolbar_widget.setLayout(top_bar)
    toolbar_layout.addWidget(toolbar_widget)

    set_qss(toolbar_container, """
        QFrame#toolbar_shell {
            background-color: transparent;
            border: none;
            border-radius: 0px;
            margin: 0px;
        }
        QFrame#toolbar_shell QWidget {
            background: transparent;
        }
    """)

    # Grid layout so the toolbar overlays the content: content at (0,0), toolbar at (0,0) on top.
    dialog.main_layout.addWidget(toolbar_container)


