# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""A widget's settings window: the web page (web_ui/widget_settings.py), set here as the opener by the web
interface at startup (details/ does not import web_ui)."""

from ....logic.logger import log_swallowed, log_warn

_opener = None
# Set just before opening one (a chart's "Edit Buttons..."): the part of the window to show first ("range_btn":
# the Range Buttons). Used once.
focus_next = None


class _Nothing:
    """No window for this widget (a type the settings do not know): exec() answers "not saved"."""

    def exec(self):
        return 0

    def result(self):
        return 0

    def deleteLater(self):
        pass


def widget_settings_dialog(widget_def, parent=None, global_config=None, local_config=None, theme_config=None):
    """A widget's settings, to exec() (True once saved), then deleteLater()."""
    kw = dict(global_config=global_config, local_config=local_config, theme_config=theme_config)
    if _opener is not None:
        try:
            got = _opener(widget_def, parent, **kw)
        except Exception:
            log_swallowed()
            got = None
        if got is not None:
            return got
    log_warn(f"no settings window for a widget of type {(widget_def or {}).get('type')!r}")
    return _Nothing()
