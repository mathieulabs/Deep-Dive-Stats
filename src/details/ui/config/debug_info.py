# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Debug info to paste in a bug report: versions, the settings that change how dates and
colors are computed, the add-ons, the latest errors of the debug log (copied as logged)
and the latest Anki crashes that went through this add-on. Nothing is read from the
collection for it."""

import os
import re
import time
from datetime import datetime

from ...logic.logger import DeepDiveLogger, log_swallowed
from ....i18n import tr

_ENTRY_START = re.compile(r"^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\] \[")
MAX_ERRORS = 5
MAX_ERROR_CHARS = 1500
MAX_CRASHES = 2
MAX_CRASH_CHARS = 2500
# Anki's crash.log only grows; reading its end is enough for the latest crashes.
_CRASH_LOG_TAIL_BYTES = 512 * 1024
# How Python starts a crash dump (faulthandler) on Windows, macOS and Linux.
_CRASH_START = re.compile(r"^(Windows fatal exception|Fatal Python error)")


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


def _crash_frames_only(block, markers):
    """The crash line, the stack of the thread that crashed, then the other stacks that go
    through this add-on. Idle threads and the long list of loaded modules are dropped."""
    head, current, others, stack = [], [], [], None
    for line in block.splitlines():
        if line.startswith("Extension modules:"):
            break
        if line.startswith(("Thread 0x", "Current thread 0x")):
            stack = [line]
            (current if line.startswith("Current") else others).append(stack)
        elif stack is not None:
            if line.strip():
                stack.append(line)
        elif line.strip():
            head.append(line)
    ours = [st for st in others if any(m in line for line in st for m in markers)]
    parts = ["\n".join(head)] + ["\n".join(st) for st in current + ours]
    return "\n\n".join(p for p in parts if p).strip()


def recent_crashes(limit=MAX_CRASHES):
    """The last `limit` crashes in Anki's crash.log whose stack goes through this add-on.

    Anki writes the Python stack of every thread there when it dies (faulthandler). The
    file has no dates, so the time it was last written is shown instead.
    """
    from aqt import mw

    path = os.path.join(mw.pm.base, "crash.log")
    if not os.path.exists(path):
        return [], None
    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END)
        size = f.tell()
        f.seek(max(0, size - _CRASH_LOG_TAIL_BYTES))
        text = f.read().decode("utf-8", errors="replace")
    blocks, current = [], None
    for line in text.splitlines():
        if _CRASH_START.match(line):
            if current is not None:
                blocks.append(current)
            current = [line]
        elif current is not None:
            current.append(line)
    if current is not None:
        blocks.append(current)
    folder = __name__.split(".", 1)[0]
    markers = (f"addons21\\{folder}\\", f"addons21/{folder}/")
    ours = ["\n".join(b) for b in blocks if any(m in line for line in b for m in markers)]
    out = []
    for block in ours[-limit:]:
        block = DeepDiveLogger._redact(_crash_frames_only(block, markers))
        if len(block) > MAX_CRASH_CHARS:
            block = block[:MAX_CRASH_CHARS] + "\n[...]"
        out.append(block)
    written = time.strftime("%Y-%m-%d %H:%M", time.localtime(os.path.getmtime(path)))
    return out, written


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
        crashes, written = recent_crashes()
        body = "None"
        if crashes:
            body = f"crash.log last written {written}\n\n" + "\n\n".join(crashes)
        parts.append(_section("Latest crashes with Deep Dive in the stack", body))
    except Exception:
        log_swallowed()
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
        tooltip(tr("Debug info copied: paste it in your report."), parent=parent)
    except Exception:
        log_swallowed()
        tooltip(tr("Could not build the debug info."), parent=parent)
