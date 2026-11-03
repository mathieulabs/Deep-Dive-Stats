# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Where the add-on lives, and whether it is still there.

When Anki updates or reinstalls the add-on while it runs, it moves user_files aside, deletes
the add-on folder and creates it again. A file written by the running code in between
creates the folder back, and Anki then stops with "file already exists": the update fails
and the add-on is gone. So nothing is written once the add-on's own files are gone.
"""

import os

ADDON_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def addon_removed() -> bool:
    """True while Anki is replacing or deleting the add-on folder (nothing may be written)."""
    return not os.path.exists(os.path.join(ADDON_DIR, "__init__.py"))
