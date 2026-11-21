# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""After an update without a restart, the code still in memory can lazily import a module the update
removed. The page commands catch that error here and ask once for a restart, instead of failing quietly.

Everything this needs is imported at the top: this module must not depend on files a later update may remove.
"""

from aqt import mw
from aqt.utils import showInfo

from ..details.logic.logger import log_warn
from ..i18n import tr

_PACKAGE = __name__.split(".")[0]
_shown = [False]


def is_stale_import(error):
    """A module of this add-on is gone from disk (the add-on was updated while Anki ran)."""
    name = getattr(error, "name", None) or ""
    return isinstance(error, ModuleNotFoundError) and (name == _PACKAGE or name.startswith(_PACKAGE + "."))


def ask_restart(error):
    """Once a session: tell the user to restart Anki. Safe to call from any thread."""
    if _shown[0]:
        return
    _shown[0] = True
    log_warn(f"stale import after an update: {error!r}", tag="WEB")

    def _show():
        try:
            showInfo(tr("Deep Dive Stats was updated. Please restart Anki to finish the update. Until then, some features may show errors."), parent=mw)
        except Exception as e:
            log_warn(f"restart notice: {e!r}", tag="WEB")

    try:
        mw.taskman.run_on_main(_show)
    except Exception as e:
        log_warn(f"restart notice: {e!r}", tag="WEB")
