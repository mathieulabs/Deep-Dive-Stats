# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Debug info to paste in a bug report: versions, the settings that change how dates and
colors are computed, the add-ons, and the latest errors of the debug log (copied as
logged). Nothing is read from the collection for it."""

import os
import re
import time
from datetime import datetime

from ...logic.logger import DeepDiveLogger, log_swallowed

_ENTRY_START = re.compile(r"^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\] \[")
MAX_ERRORS = 5
MAX_ERROR_CHARS = 1500


def _section(title, body):
    return f"==={title}===\n{body.strip()}\n"


def _addon_line():
    from aqt import mw
    from ....const import CURRENT_VERSION

    folder = __name__.split(".", 1)[0]
    try:
        meta = mw.addonManager.addon_meta(folder)
        installed = time.strftime("%Y-%m-%d %H:%M", time.localtime(meta.installed_at)) if meta.installed_at else "source"
    except Exception:
        installed = "?"
    return f"Deep Dive Stats [{folder}] installed {installed}, config format {CURRENT_VERSION}"


def _settings_lines():
    from aqt import mw
    from aqt.qt import QGuiApplication
    from ....config import ConfigManager
    from ....const import Config
    from ....utils import rollover_hour

    lines = []
    offset = datetime.now().astimezone().utcoffset()
    minutes = int(offset.total_seconds() // 60) if offset is not None else 0
    lines.append(f"Next day starts at: {rollover_hour()}h | UTC offset: {minutes:+d} min")
    try:
        conf = ConfigManager(mw).config
        pinned = conf.get(Config.PINNED_WIDGETS, []) or []
        types = sorted({str(w.get("type")) for w in pinned if isinstance(w, dict)})
        lines.append(f"Theme: {conf.get(Config.THEME_PRESET, '?')} | Pinned widgets: {len(pinned)} ({', '.join(types)})")
        lines.append(f"Excluded decks: {len(conf.get(Config.EXCLUDED_DECKS, []) or [])}")
    except Exception:
        log_swallowed()
    try:
        screen = QGuiApplication.primaryScreen()
        lines.append(f"Anki UI size: {mw.pm.uiScale()} | Screen scale: {screen.devicePixelRatio() if screen else '?'}")
    except Exception:
        log_swallowed()
    return lines


def recent_errors(limit=MAX_ERRORS):
    """The last `limit` ERROR entries of the debug log, each with its traceback."""
    DeepDiveLogger.flush()
    path = DeepDiveLogger._get_log_file()
    if not os.path.exists(path):
        return []
    entries, current = [], None
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if _ENTRY_START.match(line):
                if current is not None:
                    entries.append(current)
                current = line if "[ERROR]" in line[:40] else None
            elif current is not None:
                current += line
    if current is not None:
        entries.append(current)
    out = []
    for entry in entries[-limit:]:
        entry = entry.strip()
        if len(entry) > MAX_ERROR_CHARS:
            entry = entry[:MAX_ERROR_CHARS] + "\n[...]"
        out.append(entry)
    return out


def build_debug_info():
    from aqt.errors import addon_debug_info
    from aqt.utils import supportText

    parts = [_section("Deep Dive Stats", "\n".join([_addon_line(), *_settings_lines()]))]
    parts.append(_section("Anki", supportText()))
    errors = []
    try:
        errors = recent_errors()
    except Exception:
        log_swallowed()
    parts.append(_section("Latest errors", "\n\n".join(errors) if errors else "None"))
    try:
        parts.append(addon_debug_info().strip() + "\n")
    except Exception:
        log_swallowed()
    return "\n".join(parts)


def copy_debug_info(parent=None):
    from aqt.qt import QApplication
    from aqt.utils import tooltip

    try:
        QApplication.clipboard().setText(build_debug_info())
        tooltip("Debug info copied: paste it in your report.", parent=parent)
    except Exception:
        log_swallowed()
        tooltip("Could not build the debug info.", parent=parent)
