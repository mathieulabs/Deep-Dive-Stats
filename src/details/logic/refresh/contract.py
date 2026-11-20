# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Guarded UI callbacks.

- timer callbacks that skip deleted Qt objects
- a narrow entry point for the common Deep Dive refresh calls
"""

from aqt.qt import QTimer

from ..logger import log_debug
from ..logger import log_swallowed


def is_qt_object_alive(obj):
    """Best-effort Qt object liveness check."""
    if obj is None:
        return False
    try:
        if hasattr(obj, "metaObject"):
            obj.metaObject()
    except RuntimeError:
        return False
    except Exception:
        log_swallowed()
    return True


def invoke_callback_safe(callback, owner=None, reason=None):
    """Invoke callback while guarding deleted QObject/bound-method owners."""
    if callback is None:
        return False

    bound_owner = getattr(callback, "__self__", None)
    guard_owner = owner if owner is not None else bound_owner

    if guard_owner is not None and not is_qt_object_alive(guard_owner):
        return False
    if bound_owner is not None and not is_qt_object_alive(bound_owner):
        return False

    try:
        callback()
        return True
    except RuntimeError as err:
        # Common Qt race: wrapped object already deleted.
        if "deleted" in str(err).lower():
            if reason:
                log_debug(f"[REFRESH] skipped deleted-object callback: {reason}", tag="REFRESH")
            return False
        raise


def queue_ui_callback(callback, delay_ms=0, owner=None, reason=None):
    """Schedule a guarded callback on Qt event loop."""
    ms = max(0, int(delay_ms or 0))
    QTimer.singleShot(ms, lambda: invoke_callback_safe(callback, owner=owner, reason=reason))


