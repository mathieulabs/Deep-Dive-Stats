# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors

import copy
import json
import os
import pickle
import re
import time
import weakref
from typing import Any

from aqt import AnkiQt

from .const import CURRENT_VERSION, Config

# path -> ((mtime_ns, size), pickled dict). See _load_file_config().
_FILE_CONFIG_CACHE: dict[str, tuple] = {}
_NORMALIZED_CONFIG_CACHE: dict[str, tuple] = {}
_PEEK_CACHE: dict[str, tuple] = {}
_PEEK_RECHECK_S = 0.5
_PATH_CACHE: dict = {}
# Config managers that are kept alive (open windows). See reload_live_managers().
_LIVE_MANAGERS: weakref.WeakSet = weakref.WeakSet()

_PINNED_OFF_FLAG_NAME = "pinned_disabled.flag"


def _pinned_off_flag_path() -> str:
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "user_files", _PINNED_OFF_FLAG_NAME)


def pinned_widgets_disabled() -> bool:
    """Escape hatch for conflicts with other add-ons: a flag file read before anything else loads."""
    return os.path.exists(_pinned_off_flag_path())


def set_pinned_widgets_disabled(disabled: bool) -> None:
    flag = _pinned_off_flag_path()
    if disabled:
        os.makedirs(os.path.dirname(flag), exist_ok=True)
        with open(flag, "w", encoding="utf-8") as handle:
            handle.write("delete this file to turn the pinned widgets back on\n")
    else:
        try:
            os.remove(flag)
        except OSError:
            pass


def is_dev_build() -> bool:
    """True when running from a source checkout (it has dev_tools/); the packaged add-on does not."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.isdir(os.path.join(root, "dev_tools"))


def dev_label(name: str) -> str:
    """The name shown in the interface, with " (dev)" added in a source checkout so it
    can be told apart from an installed release."""
    return f"{name} (dev)" if is_dev_build() else name


def clear_config_caches() -> None:
    _PATH_CACHE.clear()
    _FILE_CONFIG_CACHE.clear()
    _NORMALIZED_CONFIG_CACHE.clear()
    _PEEK_CACHE.clear()


def reload_live_managers() -> None:
    """Point every long-lived config manager at the active config file and re-read it.

    Needed when the saved settings are deleted, so open windows do not keep using
    the values they already loaded.
    """
    clear_config_caches()
    for manager in list(_LIVE_MANAGERS):
        try:
            manager._config_path = manager._build_config_path()
            fresh = manager._read_config()
            manager.config.clear()
            manager.config.update(fresh)
        except Exception:
            pass


def _write_file_atomic(path: str, payload: str) -> None:
    """Write through a temp file, then swap it in. On Windows the swap can fail for a moment when
    the target is open elsewhere (antivirus, indexer, another save), so retry briefly and, as a last
    resort, write the target directly."""
    tmp_path = f"{path}.{os.getpid()}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as handle:
        handle.write(payload)
    last_error = None
    for attempt in range(8):
        try:
            os.replace(tmp_path, path)
            return
        except PermissionError as error:
            last_error = error
            time.sleep(0.02 * (attempt + 1))
    try:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(payload)
    except OSError:
        raise last_error
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


class ConfigManager:

    """Reads and writes the add-on config, one JSON file per Anki profile."""

    def __init__(self, mw: AnkiQt):
        self.mw = mw
        profile_name = getattr(getattr(self.mw, "pm", None), "name", None)
        paths = _PATH_CACHE.get(profile_name)
        if paths is None:
            addon = self.mw.addonManager.addonFromModule(__name__)
            self._addon = addon
            paths = (addon, self._build_config_path())
            _PATH_CACHE[profile_name] = paths
        self._addon, self._config_path = paths

        self.config = self._read_config()
        _LIVE_MANAGERS.add(self)

    def write_config(self):
        """Save the current values."""
        self._save_config(self.config)

    def set_value(self, key: str, val):
        """Save one value."""
        self.write_config_vals({key: val})

    def write_config_vals(self, updates: dict):
        """Apply several updates on top of the file's latest content, then save."""
        config = self._load_live_config()
        for key, val in updates.items():
            config[key] = val
            self.config[key] = val
        self._save_config(config)

    def _build_config_path(self) -> str:
        addon_dir = os.path.join(self.mw.addonManager.addonsFolder(), self._addon)
        profile_name = getattr(getattr(self.mw, "pm", None), "name", None) or "default"
        safe_profile = re.sub(r"[^A-Za-z0-9._-]+", "_", str(profile_name)).strip("._-") or "default"
        return os.path.join(addon_dir, "user_files", "config", f"{safe_profile}.json")

    def _load_file_config(self) -> dict[str, Any] | None:
        # Config managers are created often (number formatting, theme lookups). The parsed file
        # is cached by mtime/size and a copy is handed out, so callers can still mutate it.
        path = self._config_path
        try:
            st = os.stat(path)
        except OSError:
            return None
        sig = (st.st_mtime_ns, st.st_size)
        cached = _FILE_CONFIG_CACHE.get(path)
        if cached is not None and cached[0] == sig:
            return pickle.loads(cached[1])
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except Exception:
            return None
        if not isinstance(data, dict):
            return None
        try:
            _FILE_CONFIG_CACHE[path] = (sig, pickle.dumps(data, protocol=pickle.HIGHEST_PROTOCOL))
        except Exception:
            _FILE_CONFIG_CACHE.pop(path, None)
        return data

    def _save_config(self, config: dict[str, Any]) -> None:
        normalized = self._normalize_config(dict(config))
        os.makedirs(os.path.dirname(self._config_path), exist_ok=True)
        _FILE_CONFIG_CACHE.pop(self._config_path, None)
        _NORMALIZED_CONFIG_CACHE.pop(self._config_path, None)
        payload = json.dumps(normalized, indent=4, ensure_ascii=False)
        _write_file_atomic(self._config_path, payload)
        _FILE_CONFIG_CACHE.pop(self._config_path, None)
        _NORMALIZED_CONFIG_CACHE.pop(self._config_path, None)
        _PEEK_CACHE.pop(self._config_path, None)
        self._sync_pins_to_live_managers(normalized)

    def _sync_pins_to_live_managers(self, saved: dict[str, Any]) -> None:
        # Other open managers (Deep Dive, settings dialogs) hold their own copy of the config.
        # If they kept an older pinned list or time span list, their next save would put it
        # back on disk and pins or time spans would vanish.
        for key in (Config.PINNED_WIDGETS, Config.DETAILS_TABS_DATA):
            value = saved.get(key)
            if value is None:
                continue
            for manager in list(_LIVE_MANAGERS):
                if manager is self or getattr(manager, "_config_path", None) != self._config_path:
                    continue
                try:
                    manager.config[key] = copy.deepcopy(value)
                except Exception:
                    pass

    def _normalize_config(self, config: dict[str, Any]) -> dict[str, Any]:
        # Deep copy so appending to a profile's list never changes the shared default.
        normalized = copy.deepcopy(Config.DEFAULT_CONFIG)
        normalized.update(config)
        normalized[Config.VERSION] = CURRENT_VERSION
        return normalized

    def _load_live_config(self) -> dict[str, Any]:
        path = self._config_path
        try:
            st = os.stat(path)
            sig = (st.st_mtime_ns, st.st_size)
        except OSError:
            sig = None
        if sig is not None:
            cached = _NORMALIZED_CONFIG_CACHE.get(path)
            if cached is not None and cached[0] == sig:
                return pickle.loads(cached[1])
        file_config = self._load_file_config()
        if file_config is not None:
            normalized = self._normalize_config(file_config)
            if sig is not None:
                try:
                    _NORMALIZED_CONFIG_CACHE[path] = (
                        sig,
                        pickle.dumps(normalized, protocol=pickle.HIGHEST_PROTOCOL),
                    )
                except Exception:
                    _NORMALIZED_CONFIG_CACHE.pop(path, None)
            return normalized

        # No file for this profile yet: start from the defaults.
        normalized = self._normalize_config({})
        self._save_config(normalized)
        return normalized

    def _read_config(self):
        return self._load_live_config()



# While a settings dialog is open it edits an in-memory config that is only saved on accept.
# Readers going through read_config_dict() must see those unsaved edits, otherwise a live
# change is overwritten with the old value read back from disk.
_LIVE_CONFIG_OVERRIDE: list = [None]


def set_live_config_override(config):
    _LIVE_CONFIG_OVERRIDE[0] = config if isinstance(config, dict) else None


def read_config_dict():
    """Shared, read-only view of the live config (same content as
    ConfigManager(mw).config), reused while the config file is
    unchanged. Callers must NOT mutate it; copy first if needed."""
    override = _LIVE_CONFIG_OVERRIDE[0]
    if override is not None:
        return override
    from aqt import mw as _mw

    profile_name = getattr(getattr(_mw, "pm", None), "name", None)
    paths = _PATH_CACHE.get(profile_name)
    if paths is not None:
        path = paths[1]
        entry = _PEEK_CACHE.get(path)
        if entry is not None and time.monotonic() - entry[2] < _PEEK_RECHECK_S:
            # Painting asks for config values many times per frame (number format,
            # theme). Saves from this add-on drop the entry, so only a change made
            # outside it waits for the next check.
            return entry[1]
        try:
            st = os.stat(path)
            sig = (st.st_mtime_ns, st.st_size)
        except OSError:
            sig = None
        if sig is not None and entry is not None and entry[0] == sig:
            _PEEK_CACHE[path] = (sig, entry[1], time.monotonic())
            return entry[1]
    mgr = ConfigManager(_mw)
    path = mgr._config_path
    try:
        st = os.stat(path)
        _PEEK_CACHE[path] = ((st.st_mtime_ns, st.st_size), mgr.config, time.monotonic())
    except OSError:
        pass
    return mgr.config


def read_config_value(key, default=None):
    """Fast read-only access to one live config value (see read_config_dict)."""
    try:
        return read_config_dict().get(key, default)
    except Exception:
        return default
