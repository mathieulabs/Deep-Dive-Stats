# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""The pinned widgets on Onigiri's main screen.

Onigiri replaces Anki's deck list with its own widget grid, and only runs the
``deck_browser_will_render_content`` hooks placed in that grid. The web block
(web_ui/pinned.py) is the interface that draws the pinned widgets, so this
module places its hook there once, and keeps the cell tall enough for it:
Onigiri cells are a fixed row height and clip what does not fit, while its
settings grid stops at four rows (too short for a full pinned layout).

Onigiri is found by its shape, not by its folder name (which differs between a
release and a development copy): the module ending in ``.core.config`` that
exposes the config entry points used here.
"""

import math
import sys

from aqt import mw
from aqt.qt import QTimer

from ..details.logic.logger import log_info, log_swallowed

# Onigiri's grid: 15 px between two rows (rendering/onigiri_renderer.py).
_ROW_GAP = 15


def _find_onigiri():
    """The loaded Onigiri config module, or None (its shape, not its name)."""
    for name, module in list(sys.modules.items()):
        if module is None or not name.endswith(".core.config"):
            continue
        if not all(
            hasattr(module, attribute)
            for attribute in (
                "get_config",
                "get_config_readonly",
                "write_config",
                "_place_external_widgets",
            )
        ):
            continue
        return module
    return None


def hook_id() -> str:
    """The id Onigiri gives the web block's hook (module + function)."""
    from . import pinned

    function = pinned._on_browser
    return f"{function.__module__}.{function.__name__}"


def _web_block_active() -> bool:
    try:
        from . import pinned

        return bool(pinned.enabled())
    except Exception:
        return False


def _addon_name() -> str:
    try:
        return mw.addonManager.addonName(__name__.split(".")[0]) or "Deep Dive Stats"
    except Exception:
        return "Deep Dive Stats"


def _conf_int(key) -> int:
    try:
        return max(0, int(float(mw.col.conf.get(key, 0))))
    except Exception:
        return 0


def _row_height(config) -> int:
    """Height of one Onigiri grid row (widget height + its margins)."""
    layout = config.get("onigiriWidgetLayout") or {}
    try:
        height = int(layout.get("widget_height", 150))
    except (TypeError, ValueError):
        height = 150
    height = max(120, min(320, height))
    return (
        height
        + _conf_int("modern_menu_widget_margin_top")
        + _conf_int("modern_menu_widget_margin_bottom")
    )


def _layout(config):
    return config.setdefault("externalWidgetLayout", {})


def _refresh():
    try:
        if getattr(mw, "col", None) is None or mw.state != "deckBrowser":
            return
        mw.deckBrowser.refresh()
    except Exception:
        log_swallowed()


def _native_hook_id() -> str:
    """The deck-list hook id the old Qt overlay registered in Onigiri, the one the web block replaces."""
    try:
        from ..details.widgets.pinned.main_menu.manager import ONIGIRI_HOOK_ID

        return ONIGIRI_HOOK_ID
    except Exception:
        return ""


def _is_placed() -> bool:
    module = _find_onigiri()
    if module is None:
        return False
    try:
        config = module.get_config_readonly()
        grid = (config.get("externalWidgetLayout") or {}).get("grid") or {}
        return hook_id() in grid
    except Exception:
        return False


def _sync_width(entry, columns) -> bool:
    """Keep the block full width when the grid gains columns.

    The block is a full-width block: an entry still one column wide was placed
    before the span was known (or by hand), and an entry at four columns was
    full width in a four-column grid (Onigiri's widest widget is four columns).
    A deliberate two or three column choice is left alone.
    """
    if not isinstance(entry, dict) or columns < 1:
        return False
    try:
        span = int(entry.get("column_span") or 1)
    except (TypeError, ValueError):
        span = 1
    if span == columns:
        return False
    if span == 1 or span >= 4:
        entry["column_span"] = columns
        return True
    return False


def ensure_placed() -> bool:
    """Put the web block's hook in Onigiri's grid, unless the user decided otherwise.

    Archiving the tile is how Onigiri says "not on the main screen": it is left
    alone. The old Qt overlay's hook, left in the grids of users who had it, is
    cleared so the two never show as identical tiles.
    Returns True when the grid was changed.
    """
    module = _find_onigiri()
    if module is None or not _web_block_active():
        return False
    try:
        config = module.get_config()
        widget_id = hook_id()
        layout = _layout(config)
        grid = layout.setdefault("grid", {})
        archive = layout.setdefault("archive", {})

        changed = False
        stale = _native_hook_id()
        if stale and stale != widget_id:
            if grid.pop(stale, None) is not None:
                changed = True
            if archive.pop(stale, None) is not None:
                changed = True

        if widget_id in archive:
            if changed:
                module.write_config(config)
            return changed

        try:
            columns = int((config.get("onigiriWidgetLayout") or {}).get("column_count", 4))
        except (TypeError, ValueError):
            columns = 4

        entry = grid.get(widget_id)
        if isinstance(entry, dict):
            if _sync_width(entry, columns):
                changed = True
            if changed:
                module.write_config(config)
            return changed

        if columns < 1:
            return changed
        # Position 0 is where external add-ons usually land: Onigiri moves a
        # conflicting external entry to the first free run of cells on read.
        grid[widget_id] = {
            "grid_position": 0,
            "row_span": 2,
            "column_span": columns,
            "display_name": _addon_name(),
        }
        module.write_config(config)
        log_info(f"placed in Onigiri's grid: {widget_id}", tag="PINNED")
        _refresh()
        return True

    except Exception:
        log_swallowed()
        return False


def sync_height(pixels):
    """Grow or shrink the cell to the block's real height.

    Onigiri sizes a cell in whole rows (and clips the rest), so the row span is
    what the block measured divided by that row height. Only a real change is
    written, so a redraw does not rewrite the settings in a loop.
    Returns the cell's new size ({"rows", "cols"}) when it changed, else False.
    """
    module = _find_onigiri()
    if module is None or not _web_block_active():
        return False
    try:
        pixels = float(pixels)
    except (TypeError, ValueError):
        return False
    if pixels <= 0:
        return False
    try:
        config = module.get_config()
        widget_id = hook_id()
        grid = (config.get("externalWidgetLayout") or {}).get("grid") or {}
        entry = grid.get(widget_id)
        if not isinstance(entry, dict):
            return False
        try:
            columns = int((config.get("onigiriWidgetLayout") or {}).get("column_count", 4))
        except (TypeError, ValueError):
            columns = 4
        changed = _sync_width(entry, columns)
        # a cell of n rows is n rows and n - 1 gaps; Onigiri's tile margins (Layout Items) come out of it
        margins = _conf_int("modern_menu_widget_margin_top") + _conf_int("modern_menu_widget_margin_bottom")
        row = max(1, _row_height(config)) + _ROW_GAP
        span = max(2, int(math.ceil((pixels + margins + _ROW_GAP) / row)))
        if int(entry.get("row_span") or 0) != span:
            entry["row_span"] = span
            changed = True
        if not changed:
            return False
        module.write_config(config)
        try:
            cols = max(1, min(columns, int(entry.get("column_span") or 1)))
        except (TypeError, ValueError):
            cols = columns
        return {"rows": span, "cols": cols}
    except Exception:
        log_swallowed()
        return False


def fit(height):
    """The block's height, measured by the page whenever it changes (pinned.js
    onigiriFit: widgets added, folded, resized, the window resized; a redraw of
    the deck list does not happen for those). The cell's new size, or False."""
    if getattr(mw, "state", None) != "deckBrowser" or not _is_placed():
        return False
    return sync_height(height)


def relayout():
    """The grown cell runs into another tile: Onigiri places it again on read."""
    _refresh()


def on_profile_did_open():
    """The profile (and so Onigiri's settings file) is open: place, once."""
    QTimer.singleShot(0, ensure_placed)
