# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Right click and drag and drop on the time span tabs of the Details window."""
from aqt.qt import QAction, QEvent, QObject, QTimer

from ..logic.logger import log_swallowed
from .shared.menu import StyledMenu


def _is_time_view(dialog):
    return getattr(dialog, "view_mode", "time") == "time"


def _span_title(tab, idx):
    return str(tab.get("title") or tab.get("range") or f"Span {idx + 1}")


def _reload(dialog, keep_range):
    dialog.target_time_span = keep_range
    dialog._saved_time_tab = 0
    if keep_range is not None:
        for i, t in enumerate(dialog.get_active_tabs_config()):
            if str(t.get("range")) == str(keep_range):
                dialog._saved_time_tab = i
                break
    dialog.invalidate_view_switch_cache()
    dialog.load_tabs()


def _current_range(dialog):
    active = dialog.get_active_tabs_config()
    idx = dialog.tab_widget.currentIndex()
    if 0 <= idx < len(active):
        return active[idx].get("range")
    return None


def add_time_span_actions(menu, dialog):
    if not _is_time_view(dialog):
        return
    tabs = dialog.get_tabs_config()
    if not tabs:
        return
    menu.addSeparator()
    sub = menu.addMenu("Time Spans")
    enabled_count = sum(1 for t in tabs if t.get("enabled", True))
    for i, tab in enumerate(tabs):
        on = tab.get("enabled", True)
        action = QAction(_span_title(tab, i), dialog)
        action.setCheckable(True)
        action.setChecked(on)
        # The last visible span cannot be hidden.
        action.setEnabled(not (on and enabled_count <= 1))

        def toggle(checked, idx=i):
            data = dialog.get_tabs_config()
            if not checked and sum(1 for t in data if t.get("enabled", True)) <= 1:
                return
            keep = _current_range(dialog)
            data[idx]["enabled"] = bool(checked)
            dialog.save_tabs_config(data)
            if not checked and keep is not None and str(data[idx].get("range")) == str(keep):
                keep = None
            _reload(dialog, keep)

        action.triggered.connect(toggle)
        sub.addAction(action)


def _show_menu(dialog, global_pos):
    menu = StyledMenu(dialog)
    add_time_span_actions(menu, dialog)
    if menu.isEmpty():
        return
    menu.exec(global_pos)


def _apply_tab_order(dialog):
    bar = dialog.tab_widget.tabBar()
    order = [bar.tabData(i) for i in range(bar.count())]
    if any(not isinstance(v, int) for v in order):
        return
    if order == sorted(order):
        return
    full = dialog.get_tabs_config()
    if any(v >= len(full) for v in order):
        return
    slots = sorted(order)
    new_full = list(full)
    for slot, src in zip(slots, order):
        new_full[slot] = full[src]
    keep = _current_range(dialog)
    dialog.save_tabs_config(new_full)
    _reload(dialog, keep)


class _TabFilter(QObject):
    def __init__(self, dialog):
        super().__init__(dialog)
        self._dialog = dialog
        self._dragging = False

    def eventFilter(self, obj, event):
        try:
            d = self._dialog
            if not _is_time_view(d):
                return False
            et = event.type()
            if et == QEvent.Type.ContextMenu:
                _show_menu(d, event.globalPos())
                return True
            if obj is d.tab_widget.tabBar():
                if et == QEvent.Type.MouseButtonPress:
                    self._dragging = True
                elif et == QEvent.Type.MouseButtonRelease and self._dragging:
                    self._dragging = False
                    QTimer.singleShot(0, lambda: _apply_tab_order(d))
        except RuntimeError:
            pass  # the window is being destroyed: its tab bar still sends a few events
        except Exception:
            log_swallowed()
        return False


def install_time_tab_features(dialog):
    tw = dialog.tab_widget
    bar = tw.tabBar()
    full = dialog.get_tabs_config()
    enabled_idx = [i for i, t in enumerate(full) if t.get("enabled", True)]
    for pos in range(bar.count()):
        if pos < len(enabled_idx):
            bar.setTabData(pos, enabled_idx[pos])
    bar.setMovable(_is_time_view(dialog))
    if getattr(tw, "_dd_time_filter", None) is None:
        flt = _TabFilter(dialog)
        tw._dd_time_filter = flt
        tw.installEventFilter(flt)
        bar.installEventFilter(flt)
