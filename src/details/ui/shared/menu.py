# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QMenu, Qt
from ..theme.menu_style import apply_menu_theme_style
from ...widgets.chart_utils.theme import ThemeContext, resolve_widget_theme_context

class StyledMenu(QMenu):
    def __init__(self, title_or_parent=None, parent=None, is_submenu=False):
        self.is_submenu = is_submenu
        if isinstance(title_or_parent, str):
            super().__init__(title_or_parent, parent)
        else:
            super().__init__(title_or_parent)
        
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.FramelessWindowHint | Qt.WindowType.NoDropShadowWindowHint)
        
        self._apply_theme_style()

    def addMenu(self, *args):
        """Override to make sure submenus are also StyledMenus and compact."""
        if len(args) > 0 and isinstance(args[-1], str):
            title = args[-1]
            icon = args[0] if len(args) > 1 else None
            
            # Submenus are compact: they usually have no icons
            sub = StyledMenu(title, self, is_submenu=True)
            # Propagate theme context hints to submenus.
            for key in ("deepdivestats_theme_context", "deepdivestats_ignore_forced_dark_theme"):
                val = self.property(key)
                if val is not None:
                    sub.setProperty(key, val)
            if icon:
                sub.setIcon(icon)
            
            super().addMenu(sub) 
            return sub
            
        return super().addMenu(*args)

    def _resolve_theme_context(self):
        return resolve_widget_theme_context(self, default=ThemeContext.DETAILS).value

    def _apply_theme_style(self):
        apply_menu_theme_style(
            self,
            context=self._resolve_theme_context(),
            is_submenu=self.is_submenu,
        )
        
    def mouseReleaseEvent(self, event):
        action = self.actionAt(event.pos())
        if action and action.isCheckable():
            action.trigger()
            return
        super().mouseReleaseEvent(event)
