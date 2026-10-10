# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
import time
import os
import pickle
import threading
from datetime import datetime, timedelta

from aqt import mw
from aqt.qt import QObject, pyqtSignal, QTimer

from .. import Config, Period
from ..logger import log_debug, log_error, log_info  # re-exported to the history_cache modules
from ..history_provider import HistoryProvider
from ..data.core.time_utils import get_time_range_ms




