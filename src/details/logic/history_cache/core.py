# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from .shared import (
    QObject,
    QTimer,
    log_debug,
    log_error,
    log_info,
    mw,
    os,
    pyqtSignal,
    threading,
)
from concurrent.futures import ThreadPoolExecutor
from ....const.addon_dir import addon_removed
from ..logger import log_swallowed


# The all-decks entry has two names: None and this one (the tables and Deep Dive use it).
TOTAL_ALIAS = "[[TOTAL]]"


class DeckCache(dict):
    """{deck key: {range: context}}, the all-decks entry kept once: "[[TOTAL]]" reads and
    writes the entry of None (they held the same data twice)."""

    __slots__ = ()

    @staticmethod
    def _key(key):
        return None if key == TOTAL_ALIAS else key

    def __init__(self, data=None):
        super().__init__()
        if data:
            self.update(data)

    def update(self, data=(), **kw):
        items = dict(data, **kw)
        for key, value in items.items():
            if key == TOTAL_ALIAS and None in items:
                continue  # an older cache: both entries, the same data
            dict.__setitem__(self, self._key(key), value)

    def __getitem__(self, key):
        return dict.__getitem__(self, self._key(key))

    def __setitem__(self, key, value):
        dict.__setitem__(self, self._key(key), value)

    def __delitem__(self, key):
        dict.__delitem__(self, self._key(key))

    def __contains__(self, key):
        return dict.__contains__(self, self._key(key))

    def get(self, key, default=None):
        return dict.get(self, self._key(key), default)

    def setdefault(self, key, default=None):
        return dict.setdefault(self, self._key(key), default)

    def pop(self, key, *default):
        return dict.pop(self, self._key(key), *default)


class GlobalHistoryCacheCore:
    """Singleton cache that stores aggregated history for all decks.
    Populated once at startup and updated incrementally.
    """
    _instance = None
    _lock = threading.Lock()

    class _SignalProxy(QObject):
        context_updated = pyqtSignal()
        invoke_on_main = pyqtSignal(object)

    def __new__(cls):
        if cls._instance is None:
            cls._instance = object.__new__(cls)

            # Use a proxy for signals to avoid QObject singleton inheritance issues
            cls._instance.signals = cls._SignalProxy()
            cls._instance.signals.invoke_on_main.connect(lambda callback: callback())

            cls._instance.cache = {}  # {deck_id: {range_type: context}}
            cls._instance.hier_map = {}  # {parent_did: [leaf_did, ...]}, kept for FSRS aggregation
            cls._instance.is_initialized = False
            cls._instance.last_max_rev_id = 0
            cls._instance.last_max_card_id = 0
            cls._instance.last_logical_date = None
            cls._instance._is_refreshing = False
            cls._instance._is_initializing = False
            cls._instance._init_callbacks = []
            cls._instance._init_deferred_hook_installed = False
            cls._instance._save_timer = None
            cls._instance._last_profile = None  # Track last profile to detect real switches
            cls._instance._deferred_warmup_timer = None
            cls._instance._deferred_warmup_in_progress = False
            # The FSRS part of a first build, still running in the background.
            cls._instance._fsrs_pending = False
            cls._instance._deferred_warmup_priority = []
            cls._instance._hier_cache_data = None
            cls._instance._hier_cache_invalidated = False
            cls._instance._hier_prewarm_scheduled = False
            cls._instance._context_update_pending = False
            cls._instance._context_update_delay_ms = 70
            # Hint consumed by the UI layer to refresh widgets in place instead of rebuilding overlays after some background merges.
            cls._instance._pending_partial_widget_refresh = None
            # Dedicated lane for review-return refresh jobs so they do not queue behind generic background work.
            cls._instance._priority_refresh_executor = ThreadPoolExecutor(
                max_workers=1,
                thread_name_prefix="ThreadPoolExecutor-review_refresh",
            )

            # Background rollover/sync poller (every 60s)
            cls._instance._poll_timer = QTimer(cls._instance.signals)
            cls._instance._poll_timer.timeout.connect(cls._instance._check_incremental_update)
            cls._instance._poll_timer.start(60000)
            cls._instance._context_update_timer = QTimer(cls._instance.signals)
            cls._instance._context_update_timer.setSingleShot(True)
            cls._instance._context_update_timer.timeout.connect(cls._instance._flush_context_updated)

            from aqt import gui_hooks
            gui_hooks.profile_did_open.append(cls._instance._on_profile_switch)
            # A .colpkg import reloads the collection without reopening the profile.
            gui_hooks.collection_did_load.append(cls._instance._on_collection_loaded)

        return cls._instance

    @property
    def cache(self):
        return self._deck_cache

    @cache.setter
    def cache(self, value):
        self._deck_cache = value if isinstance(value, DeckCache) else DeckCache(value or {})

    @staticmethod
    def _get_addon_path():
        # Walk up 5 levels: core.py -> history_cache -> logic -> details -> src -> addon root
        addon_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)
        )))))
        return addon_path

    @property
    def target_dir(self):
        # user_files survives add-on updates (the add-on folder itself is replaced).
        from .global_cache import GlobalHistoryCache
        addon_path = GlobalHistoryCache._get_addon_path()
        cache_dir = os.path.join(addon_path, "user_files", "cache")
        # If a plain FILE (not dir) exists at that path, remove it
        if os.path.exists(cache_dir) and not os.path.isdir(cache_dir):
            os.remove(cache_dir)
        if not os.path.exists(cache_dir) and not addon_removed():
            os.makedirs(cache_dir, exist_ok=True)
            GlobalHistoryCacheCore._migrate_old_cache_dir(addon_path, cache_dir)
        return cache_dir

    @staticmethod
    def _migrate_old_cache_dir(addon_path, cache_dir):
        """Move the cache files an older version kept next to the code into user_files/cache."""
        old_dir = os.path.join(addon_path, "cache")
        if not os.path.isdir(old_dir):
            return
        try:
            for name in os.listdir(old_dir):
                if name.endswith(".pkl"):
                    os.replace(os.path.join(old_dir, name), os.path.join(cache_dir, name))
            if not os.listdir(old_dir):
                os.rmdir(old_dir)
        except Exception:
            log_swallowed()

    @property
    def profile_cache_name(self):
        try:
            profile = mw.pm.name if (hasattr(mw, "pm") and mw.pm and mw.pm.name) else "default"
        except Exception:
            profile = "default"
        clean_name = "".join([c for c in profile if c.isalnum() or c in (' ', '.', '_', '-')]).strip()
        return f"{clean_name}.pkl"

    @property
    def cache_file(self):
        return os.path.join(self.target_dir, self.profile_cache_name)

    @staticmethod
    def _run_callbacks(callbacks):
        for cb in callbacks:
            try:
                cb()
            except Exception as e:
                log_error(f"init callback failed: {e}", tag="CACHE")

    def _pop_init_callbacks(self):
        with self._lock:
            callbacks = list(getattr(self, "_init_callbacks", []))
            self._init_callbacks = []
            return callbacks

    def _log(self, message, level="INFO"):
        if str(level).upper() == "DEBUG":
            log_debug(message, tag="CACHE")
        else:
            log_info(message, tag="CACHE")

    def _emit_context_updated_coalesced(self):
        """Coalesce bursts of context_updated emissions into one UI tick."""
        self._context_update_pending = True
        if self._context_update_timer.isActive():
            return
        self._context_update_timer.start(self._context_update_delay_ms)

    def _flush_context_updated(self):
        if not self._context_update_pending:
            return
        self._context_update_pending = False
        self.signals.context_updated.emit()


