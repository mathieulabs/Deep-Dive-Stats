# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
import zlib

from .shared import mw, os, pickle, time
from ....const.addon_dir import addon_removed
from ..logger import log_swallowed
from .exclusion import exclusion_signature

# Start of a compressed cache file (a plain pickle starts with 0x80).
_ZLIB_MAGIC = b"DDZ1"


def _drop_zero_hours(cache):
    """An older cache: each day kept its 24 hours, also the ones without reviews."""
    for ctxs in cache.values():
        for ctx in (ctxs or {}).values():
            for day in (ctx.get("reviews") or []) if isinstance(ctx, dict) else []:
                hours = day.get("hourly") if isinstance(day, dict) else None
                if isinstance(hours, dict):
                    day["hourly"] = {h: v for h, v in hours.items() if v.get("total") or v.get("correct")}


class StorageMixin:
    @staticmethod
    def clear():
        from .global_cache import GlobalHistoryCache
        if GlobalHistoryCache._instance:
            GlobalHistoryCache._instance.cache.clear()
            # Clearing the data does not necessarily mean is_initialized = False, but an empty cache is effectively uninitialized.
            GlobalHistoryCache._instance.is_initialized = False

    def _save_to_disk(self):
        """Save the current cache state to a binary file with debouncing and async handling."""
        if self._save_timer:
            self._save_timer.stop()
            self._save_timer = None

        from aqt.qt import QTimer
        self._save_timer = QTimer()
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._do_save_async)
        self._save_timer.start(500)

    def _do_save_async(self):
        """Pickle and write the cache in a background thread.

        The snapshot is taken under the cache lock, so the file never holds a
        half-merged state. It is written to a temp file and swapped in, so a crash
        mid-write cannot leave a truncated cache.
        """
        cache_file = self.cache_file
        crt = self._collection_crt()

        def worker():
            with self._lock:
                data = {
                    "crt": crt,
                    "cache": dict(self.cache),  # a plain dict on disk
                    "hier_map": self.hier_map,
                    "last_max_rev_id": self.last_max_rev_id,
                    "last_max_card_id": self.last_max_card_id,
                    "last_logical_date": getattr(self, "last_logical_date", None),
                    "version": 17,  # 17: each day keeps only its hours with reviews, the all-decks entry once; 16: young/mature retention counted like Anki (interval >= 1 day or review type); 15: rollover after local time
                    "excluded": exclusion_signature(),
                }
                payload = pickle.dumps(data, protocol=pickle.HIGHEST_PROTOCOL)
            # Compressed on disk (about 10x smaller: the rows of the days repeat a lot), out of
            # the lock; zlib lets the interface run meanwhile.
            payload = _ZLIB_MAGIC + zlib.compress(payload, 6)
            if addon_removed():
                return False
            tmp_path = cache_file + ".tmp"
            try:
                with open(tmp_path, "wb") as f:
                    f.write(payload)
                    f.flush()
                    try:
                        os.fsync(f.fileno())
                    except Exception:
                        log_swallowed()
                os.replace(tmp_path, cache_file)
            except OSError:
                # A full disk: no half-written file left behind (the old cache stays).
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
                raise
            return True

        def on_done(future):
            try:
                if future.result():
                    self._log(f"Saved cache to {cache_file}", level="DEBUG")
            except Exception as e:
                # Usually a warmup touching a context while it was being pickled:
                # try once more a bit later instead of keeping an old file.
                self._log(f"Failed to save to disk in background: {e}")
                retries = int(getattr(self, "_save_retry_count", 0) or 0)
                if retries < 3:
                    self._save_retry_count = retries + 1
                    self._save_to_disk()
                return
            self._save_retry_count = 0

        try:
            mw.taskman.run_in_background(worker, on_done=on_done)
        except Exception as e:
            self._log(f"Failed to initiate background save: {e}")

    @staticmethod
    def _collection_crt():
        """Creation time of the open collection: identifies it across restores and imports."""
        try:
            return int(mw.col.db.scalar("select crt from col") or 0) or None
        except Exception:
            return None

    def _disk_cache_matches_collection(self, data):
        """False when the saved cache was built from another collection (backup restore, .colpkg import)."""
        try:
            saved_crt = data.get("crt")
            current_crt = self._collection_crt()
            if saved_crt and current_crt and int(saved_crt) != int(current_crt):
                return False
            # The newest review and card the cache knows must still exist in the collection.
            rev_id = int(data.get("last_max_rev_id", 0) or 0)
            if rev_id and mw.col.db.scalar("select 1 from revlog where id = ?", rev_id) is None:
                return False
            card_id = int(data.get("last_max_card_id", 0) or 0)
            if card_id and mw.col.db.scalar("select 1 from cards where id = ?", card_id) is None:
                return False
        except Exception:
            log_swallowed()
        return True

    def _load_from_disk(self):
        """Load the cache state from a binary file."""
        load_path = self.cache_file
        if not os.path.exists(load_path):
            self._log(f"Cache file not found at {self.cache_file}")
            return False

        try:
            _load_start = time.time()
            with open(load_path, "rb") as f:
                raw = f.read()
            plain = not raw.startswith(_ZLIB_MAGIC)
            if not plain:
                raw = zlib.decompress(raw[len(_ZLIB_MAGIC):])
            data = pickle.loads(raw)  # an older file: plain pickle
            del raw

            if not isinstance(data, dict) or data.get("version", 0) < 16:
                self._log("Cache file validation failed or old version. Forcing rebuild.")
                return False

            if data.get("excluded", []) != exclusion_signature():
                self._log("Excluded decks changed since the cache was saved. Forcing rebuild.")
                return False

            if not self._disk_cache_matches_collection(data):
                self._log("Saved cache belongs to another collection (restore or import). Forcing rebuild.")
                return False

            self.cache = data.get("cache", {})  # (an older file: its "[[TOTAL]]" copy dropped)
            if data.get("version", 0) < 17:
                _drop_zero_hours(self.cache)
            self.hier_map = data.get("hier_map", {})
            self.last_max_rev_id = data.get("last_max_rev_id", 0)
            self.last_max_card_id = data.get("last_max_card_id", 0)
            # last_logical_date is safe in memory, but restoring it across launches can force
            # a full rebuild on the first periodic tick when the saved value is stale.
            self.last_logical_date = None
            elapsed = time.time() - _load_start
            self._log(f"Loaded from disk in {elapsed:.2f}s. Max rev_id: {self.last_max_rev_id}, Max card_id: {self.last_max_card_id}")
            if plain or data.get("version", 0) < 17:
                # A file of an older version: written again compressed, once, a little
                # after startup (not while Anki opens).
                from aqt.qt import QTimer

                QTimer.singleShot(20000, self._save_to_disk)
            return True
        except Exception as e:
            self._log(f"Failed to load from disk: {e}")
            import traceback
            self._log(traceback.format_exc())
            if os.path.exists(load_path):
                os.remove(load_path)
            return False

    @staticmethod
    def clear_all_cache(callback=None):
        """Deletes all cache files and resets in-memory state."""
        from .global_cache import GlobalHistoryCache
        instance = GlobalHistoryCache()
        target_dir = instance.target_dir

        instance.cache = {}
        instance.hier_map = {}
        instance.last_max_rev_id = 0
        instance.last_max_card_id = 0
        instance.is_initialized = False

        try:
            import os
            for filename in os.listdir(target_dir):
                if filename.endswith(".pkl"):
                    file_path = os.path.join(target_dir, filename)
                    try:
                        os.remove(file_path)
                    except Exception:
                        log_swallowed()
            instance._log("All cache files cleared successfully.")
        except Exception as e:
            instance._log(f"Error clearing cache files: {e}")

        GlobalHistoryCache.init_async(callback=callback)


