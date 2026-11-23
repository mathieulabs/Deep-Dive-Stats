# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from __future__ import annotations

import copy
import json
import os
import pickle
import re
import threading
import time
import weakref
from typing import Any

from aqt import AnkiQt

from .const import CURRENT_VERSION, Config
from .const.addon_dir import addon_removed

# path -> ((mtime_ns, size), pickled dict). See _load_file_config().
_FILE_CONFIG_CACHE: dict[str, tuple] = {}
_NORMALIZED_CONFIG_CACHE: dict[str, tuple] = {}
_PEEK_CACHE: dict[str, tuple] = {}
_PEEK_RECHECK_S = 0.5
_PATH_CACHE: dict = {}
# Config managers that are kept alive (open windows). See reload_live_managers().
_LIVE_MANAGERS: weakref.WeakSet = weakref.WeakSet()
_LIVE_LOCK = threading.Lock()


def _live_managers() -> list:
    with _LIVE_LOCK:
        return list(_LIVE_MANAGERS)

_PINNED_OFF_FLAG_NAME = "pinned_disabled.flag"


def _pinned_off_flag_path() -> str:
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "user_files", _PINNED_OFF_FLAG_NAME)


def pinned_widgets_disabled() -> bool:
    """Escape hatch for conflicts with other add-ons: a flag file read before anything else loads."""
    return os.path.exists(_pinned_off_flag_path())


def set_pinned_widgets_disabled(disabled: bool) -> None:
    flag = _pinned_off_flag_path()
    if addon_removed():
        return
    if disabled:
        os.makedirs(os.path.dirname(flag), exist_ok=True)
        with open(flag, "w", encoding="utf-8") as handle:
            handle.write("delete this file to turn the pinned widgets back on\n")
    else:
        try:
            os.remove(flag)
        except OSError:
            pass


_DEV_BUILD = []


def is_dev_build() -> bool:
    """True when running from a source checkout (it has dev_tools/); the packaged add-on does not.
    Checked on disk once a session. DD_AS_USER=1: the checkout runs as a user's install (no traces, no coverage, no
    startup sampling, the pages cached, no "(dev)" label), to see the add-on as users get it."""
    if not _DEV_BUILD:
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        _DEV_BUILD.append(os.path.isdir(os.path.join(root, "dev_tools")) and not os.environ.get("DD_AS_USER"))
    return _DEV_BUILD[0]


def dev_label(name: str) -> str:
    """The name shown in the interface, with " (dev)" added in a source checkout so it
    can be told apart from an installed release. DD_NO_DEV_LABEL=1 leaves it out (demo recordings)."""
    return f"{name} (dev)" if is_dev_build() and not os.environ.get("DD_NO_DEV_LABEL") else name


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
    for manager in _live_managers():
        try:
            manager._config_path = manager._build_config_path()
            fresh = manager._read_config()
            manager.config.clear()
            manager.config.update(fresh)
        except Exception:
            from .details.logic.logger import log_swallowed

            log_swallowed()


_BOX_INTENSITY_KEYS = (
    Config.PINNED_GLASS_INTENSITY,
    Config.TEXT_WIDGET_GLASS_INTENSITY,
    Config.HEATMAP_GLASS_INTENSITY,
)


def _drop_old_default_heights(normalized):
    """Once: the old defaults gave Difficulty, Retrievability and Added a fixed height of 200
    px. With the heights that follow the card width, that kept the last row of Deep Dive
    flat while the others grew. Only that exact default value is dropped."""
    dd = normalized.get(Config.DEEP_DIVE_WIDGET_SETTINGS)
    if not isinstance(dd, dict):
        return
    dd = dict(dd)
    for key in ("difficulty_g", "retrievability_g", "added_g"):
        entry = dd.get(key)
        if isinstance(entry, dict) and entry.get("height") == 200:
            entry = dict(entry)
            entry.pop("height", None)
            dd[key] = entry
    normalized[Config.DEEP_DIVE_WIDGET_SETTINGS] = dd


def _move_box_intensities_to_even_scale(saved, normalized):
    """Once: box intensities saved with the old slider take the value that gives the same
    look on the new one. Only values the profile saved are converted (the defaults are
    already on the new scale). The text widget still at its old default (20, nearly
    invisible) gets the new default, like the charts."""
    from .const.glass_scale import box_value_from_old

    def convert(src, dst):
        for key in _BOX_INTENSITY_KEYS:
            if key not in src or not isinstance(src.get(key), (int, float)):
                continue
            if key == Config.TEXT_WIDGET_GLASS_INTENSITY and src[key] == 20 and dst is normalized:
                dst[key] = Config.DEFAULT_CONFIG[key]
            else:
                dst[key] = box_value_from_old(src[key])

    try:
        convert(saved, normalized)
        grid = saved.get(Config.DEEP_DIVE_GRID_STYLE)
        if isinstance(grid, dict):
            normalized[Config.DEEP_DIVE_GRID_STYLE] = new_grid = dict(grid)
            convert(grid, new_grid)
        pins = saved.get(Config.PINNED_WIDGETS)
        if isinstance(pins, list):
            new_pins = []
            for w in pins:
                if isinstance(w, dict) and any(k in w for k in _BOX_INTENSITY_KEYS):
                    w = dict(w)
                    convert(dict(w), w)
                new_pins.append(w)
            normalized[Config.PINNED_WIDGETS] = new_pins
        dd = saved.get(Config.DEEP_DIVE_WIDGET_SETTINGS)
        if isinstance(dd, dict):
            new_dd = {}
            for wid, w in dd.items():
                if isinstance(w, dict) and any(k in w for k in _BOX_INTENSITY_KEYS):
                    w = dict(w)
                    convert(dict(w), w)
                new_dd[wid] = w
            normalized[Config.DEEP_DIVE_WIDGET_SETTINGS] = new_dd
    except Exception:
        from .details.logic.logger import log_swallowed

        log_swallowed()


def _write_file_atomic(path: str, payload: str) -> None:
    """Write through a temp file, then swap it in. On Windows the swap can fail for a moment when
    the target is open elsewhere (antivirus, indexer, another save), so retry briefly and, as a last
    resort, write the target directly. Nothing is written while Anki replaces the add-on
    (see const.addon_dir)."""
    if addon_removed():
        return
    import threading

    tmp_path = f"{path}.{os.getpid()}.{threading.get_ident()}.tmp"
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


# Called after each save of the config (the web pinned block builds itself again: web_ui/pinned.py).
SAVE_LISTENERS = []


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
        with _LIVE_LOCK:
            _LIVE_MANAGERS.add(self)

    def write_config(self):
        """Save the current values."""
        self._save_config(self.config)

    def set_value(self, key: str, val, notify: bool = True):
        """Save one value."""
        self.write_config_vals({key: val}, notify=notify)

    def write_config_vals(self, updates: dict, notify: bool = True):
        """Apply several updates on top of the file's latest content, then save."""
        config = self._load_live_config()
        for key, val in updates.items():
            config[key] = val
            self.config[key] = val
        self._save_config(config, notify=notify)
        # the other open managers (Deep Dive, Settings) take these values too: their next full save
        # (write_config, a theme change...) would otherwise put their older copy back on disk
        with _LIVE_LOCK:
            managers = list(_LIVE_MANAGERS)
        for manager in managers:
            if manager is self or getattr(manager, "_config_path", None) != self._config_path:
                continue
            try:
                for key, val in updates.items():
                    manager.config[key] = copy.deepcopy(val)
            except Exception:
                from .details.logic.logger import log_swallowed

                log_swallowed()

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

    def _save_config(self, config: dict[str, Any], notify: bool = True) -> None:
        normalized = self._normalize_config(dict(config))
        if addon_removed():
            return
        os.makedirs(os.path.dirname(self._config_path), exist_ok=True)
        _FILE_CONFIG_CACHE.pop(self._config_path, None)
        _NORMALIZED_CONFIG_CACHE.pop(self._config_path, None)
        payload = json.dumps(normalized, indent=4, ensure_ascii=False)
        _write_file_atomic(self._config_path, payload)
        _FILE_CONFIG_CACHE.pop(self._config_path, None)
        _NORMALIZED_CONFIG_CACHE.pop(self._config_path, None)
        _PEEK_CACHE.pop(self._config_path, None)
        self._sync_pins_to_live_managers(normalized)
        if notify:
            for listener in list(SAVE_LISTENERS):
                try:
                    listener(normalized)
                except Exception:
                    from .details.logic.logger import log_swallowed

                    log_swallowed()

    def _sync_pins_to_live_managers(self, saved: dict[str, Any]) -> None:
        # Other open managers (Deep Dive, settings dialogs) hold their own copy of the config.
        # If they kept an older pinned list, time span list or table column list, their next save would put it
        # back on disk and pins, time spans or columns would vanish.
        # Deep Dive's charts too: a chart removed from its menu (a manager of its own) came back when the gallery,
        # holding the window's older list, saved or cancelled.
        for key in (Config.PINNED_WIDGETS, Config.DETAILS_TABS_DATA, Config.TABLE_COLUMNS, Config.TABLE_SHOW_COUNTS):
            value = saved.get(key)
            if value is None:
                continue
            for manager in _live_managers():
                if manager is self or getattr(manager, "_config_path", None) != self._config_path:
                    continue
                try:
                    manager.config[key] = copy.deepcopy(value)
                except Exception:
                    from .details.logic.logger import log_swallowed

                    log_swallowed()
        for key in (Config.DEEP_DIVE_EXTRA_CHARTS, Config.DEEP_DIVE_HIDDEN_CHARTS, Config.DEEP_DIVE_CHART_ORDER,
                    Config.DEEP_DIVE_TEXT_WIDGETS, Config.DEEP_DIVE_WIDGET_SETTINGS, Config.SHARED_FILTER_MODES):
            for manager in _live_managers():
                if manager is self or getattr(manager, "_config_path", None) != self._config_path:
                    continue
                try:
                    if key in saved:
                        manager.config[key] = copy.deepcopy(saved[key])
                    else:  # taken off (a reset of the order)
                        manager.config.pop(key, None)
                except Exception:
                    from .details.logic.logger import log_swallowed

                    log_swallowed()

    def _normalize_config(self, config: dict[str, Any]) -> dict[str, Any]:
        # Deep copy so appending to a profile's list never changes the shared default.
        normalized = copy.deepcopy(Config.DEFAULT_CONFIG)
        normalized.update(config)
        normalized[Config.VERSION] = CURRENT_VERSION
        saved = config
        if not normalized.get(Config.PINNED_GLASS_DEFAULT_RAISED):
            # Once: the old default box intensity (24) left pinned charts almost see-through
            # over a background image. A value still at that default takes the newer one
            # (70 on the old scale, converted just below).
            if config.get(Config.PINNED_GLASS_INTENSITY) == 24:
                saved = dict(config)
                saved[Config.PINNED_GLASS_INTENSITY] = 70
                normalized[Config.PINNED_GLASS_INTENSITY] = 70
            normalized[Config.PINNED_GLASS_DEFAULT_RAISED] = True
        if not normalized.get(Config.GLASS_SCALE_EVEN):
            _move_box_intensities_to_even_scale(saved, normalized)
            normalized[Config.GLASS_SCALE_EVEN] = True
        # (The web block's new defaults - no border lit on hover for the pinned charts, the "Auto" glass blur - are
        # for new profiles only: a profile that has the add-on already keeps what it had, its hover border and its
        # blur, until the user changes them in Settings.)
        if not normalized.get(Config.DEEP_DIVE_DEFAULT_HEIGHTS_DROPPED):
            _drop_old_default_heights(normalized)
            normalized[Config.DEEP_DIVE_DEFAULT_HEIGHTS_DROPPED] = True
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

        # No file for this profile yet: a new profile starts from the settings of the profile used last (its look,
        # charts, widgets, layout), without what belongs to that profile's own collection (decks, excluded dates);
        # with no other profile, from the defaults.
        start = {}
        if getattr(getattr(self.mw, "pm", None), "name", None):
            try:
                src = _last_used_profile_config(self.mw, self._config_path)
                if src is not None:
                    path, data, renamed = src
                    start = copy.deepcopy(data) if renamed else deck_free_settings(data)
                    try:
                        from .details.logic.logger import log_info

                        log_info(f"new profile: settings copied from {os.path.basename(path)}"
                                 f"{' (renamed profile: as they were)' if renamed else ' (decks left out)'}", tag="CONFIG")
                    except Exception:
                        pass
            except Exception:
                start = {}
        normalized = self._normalize_config(start)
        self._save_config(normalized)
        return normalized

    def _read_config(self):
        return self._load_live_config()



# ---- settings shared between profiles -------------------------------------------------------------------------
# Each Anki profile keeps its own settings file. A new profile starts from the profile used last, and Settings >
# General can copy another profile's settings: everything but what belongs to that profile's collection.

def _safe_profile(name) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", str(name or "default")).strip("._-") or "default"


def profile_config_files(mw, exclude_path=None):
    """[(profile name or file name, path, still an Anki profile)] of the other profiles' settings files, the most
    recently used first."""
    folder = os.path.join(mw.addonManager.addonsFolder(), mw.addonManager.addonFromModule(__name__), "user_files", "config")
    try:
        names = [n for n in os.listdir(folder) if n.endswith(".json")]
    except OSError:
        return []
    try:
        profiles = {_safe_profile(p): p for p in (mw.pm.profiles() or [])}
    except Exception:
        profiles = {}
    out = []
    for n in names:
        path = os.path.join(folder, n)
        if exclude_path and os.path.normcase(os.path.abspath(path)) == os.path.normcase(os.path.abspath(exclude_path)):
            continue
        stem = n[:-5]
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            continue
        out.append((profiles.get(stem, stem), path, stem in profiles, mtime))
    out.sort(key=lambda x: -x[3])
    return [(a, b, c) for a, b, c, _m in out]


def _read_json(path):
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def _last_used_profile_config(mw, target_path):
    """(path, settings, renamed) of the profile used last, or None. Its settings file is the one saved last among
    the profiles Anki has. A file saved in the last minutes whose profile is no longer in Anki is this profile
    under its former name (renamed in Anki's profile manager): its settings are for this collection, kept whole.
    The file made before any profile was open ("default") and the files of deleted profiles are not used."""
    files = profile_config_files(mw, target_path)
    now = time.time()
    for _name, path, is_profile in files:
        if not is_profile:
            stem = os.path.basename(path)[:-5]
            try:
                recent = now - os.path.getmtime(path) < 600
            except OSError:
                recent = False
            if stem == "default" or not recent:
                continue
        data = _read_json(path)
        if data:
            return path, data, not is_profile
    return None


# what belongs to a profile's own collection: decks (their ids and names), the excluded study dates, the deck shown
_COLLECTION_KEYS = (
    Config.EXCLUDED_DECKS, Config.EXCLUDED_DATES, Config.DECK_COLORS,
    Config.DETAILS_DEEP_DIVE_IDENTIFIER, Config.DETAILS_DEEP_DIVE_TITLE, Config.DETAILS_DECK_TAB_INDEX,
    Config.DETAILS_EXPANDED_DECKS, Config.DETAILS_EXPANDED_DECKS_SET,
)


def deck_free_settings(data: dict) -> dict:
    """A profile's settings without what belongs to its collection: those keys back to their defaults, the pinned
    widgets following the deck shown (a widget shown only on some decks of that collection is left out)."""
    out = copy.deepcopy(data)
    for key in _COLLECTION_KEYS:
        if key in Config.DEFAULT_CONFIG:
            out[key] = copy.deepcopy(Config.DEFAULT_CONFIG[key])
        else:
            out.pop(key, None)
    out.pop("Deep_Dive_Recent_Searches", None)
    widgets = []
    for w in out.get(Config.PINNED_WIDGETS) or []:
        if not isinstance(w, dict):
            continue
        w = dict(w)
        w.pop("search_query", None)
        views = w.get("view_dids")
        if views:
            if "main_menu" not in views:
                continue  # only on some decks of the other collection
            w["view_dids"] = ["main_menu"]
        for key in ("deck_id", "deck_ids"):
            v = w.get(key)
            numeric = (isinstance(v, (int, float)) and not isinstance(v, bool)) or (
                isinstance(v, (list, tuple)) and any(isinstance(x, (int, float)) or (isinstance(x, str) and x.isdigit()) for x in v))
            if numeric or (isinstance(v, str) and v.isdigit()):
                w.pop(key, None)  # that collection's decks: the widget follows the deck shown
        widgets.append(w)
    if Config.PINNED_WIDGETS in out:
        out[Config.PINNED_WIDGETS] = widgets
    return out


def copy_profile_settings(mw, source_path, target: "ConfigManager") -> bool:
    """Settings > General > Copy settings from another profile: everything of the source but its collection's own
    settings, which this profile keeps."""
    data = _read_json(source_path)
    if not data:
        return False
    new = deck_free_settings(data)
    for key in _COLLECTION_KEYS:
        if key in target.config:
            new[key] = copy.deepcopy(target.config[key])
    normalized = target._normalize_config(new)
    target._save_config(normalized)
    # every live copy of this profile's settings takes them (one writing its old copy back later undid the copy)
    for manager in _live_managers() + [target]:
        if getattr(manager, "_config_path", None) == target._config_path:
            try:
                manager.config.clear()
                manager.config.update(copy.deepcopy(normalized))
            except Exception:
                from .details.logic.logger import log_swallowed

                log_swallowed()
    return True


_SHARE_STRIP_KEYS = (
    Config.LANGUAGE,
    Config.DETAILS_DEEP_DIVE_IDENTIFIER,
    Config.DETAILS_DEEP_DIVE_TITLE,
    Config.DETAILS_DEEP_DIVE_PERIOD_RANGE,
    Config.DETAILS_DECK_TAB_INDEX,
    Config.DETAILS_TIME_TAB_INDEX,
    Config.DETAILS_LAYOUT_STATE,
    Config.DETAILS_TABLE_DRAWER_SIZES,
    Config.DETAILS_TABLE_DRAWER_OPEN,
)
_SHARE_PREFIX = "DDCFG1:"


def export_settings_dict(source: dict, shareable: bool = True) -> dict:
    """Build a portable JSON export dict (all themes, presets, layouts, widgets, animations).
    When shareable=True, strips profile-specific decks, deck colors, excluded dates, language and transient UI state."""
    payload = deck_free_settings(source) if shareable else copy.deepcopy(source)
    if shareable:
        for k in _SHARE_STRIP_KEYS:
            payload.pop(k, None)
    return {"deep_dive_config": 1, "shareable": bool(shareable), "settings": payload}


def encode_share_code(source: dict) -> str:
    """Compress a shareable config into a compact copy-pasteable string (DDCFG1:...)."""
    import base64
    import zlib

    raw = json.dumps(export_settings_dict(source, shareable=True), separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return _SHARE_PREFIX + base64.urlsafe_b64encode(zlib.compress(raw, 9)).decode("ascii")


def decode_imported_settings(raw: str) -> tuple[dict, bool]:
    """Parse either a DDCFG1:... share code, a JSON export file, or a raw profile JSON.
    Returns (settings_dict, shareable). Raises ValueError if invalid."""
    import base64
    import zlib

    text = str(raw or "").strip()
    if not text:
        raise ValueError("Empty config")
    if text.startswith(_SHARE_PREFIX):
        try:
            blob = base64.urlsafe_b64decode(text[len(_SHARE_PREFIX):].strip().encode("ascii"))
            obj = json.loads(zlib.decompress(blob).decode("utf-8"))
        except Exception as e:
            raise ValueError("Invalid share code") from e
    else:
        try:
            obj = json.loads(text)
        except Exception as e:
            raise ValueError("Invalid JSON") from e
    if not isinstance(obj, dict):
        raise ValueError("Invalid config format")
    if "deep_dive_config" in obj and isinstance(obj.get("settings"), dict):
        data = obj["settings"]
        shareable = bool(obj.get("shareable", True))
    else:
        data = obj
        shareable = True
    if not any(k in Config.DEFAULT_CONFIG for k in data):
        raise ValueError("Not a Deep Dive Stats config")
    return data, shareable


def apply_imported_settings(target: "ConfigManager", data: dict, shareable: bool = True) -> bool:
    """Apply imported settings to target, preserving collection-specific keys & language when shareable=True
    and merging custom theme presets / heatmap palettes so existing user presets are kept."""
    if not isinstance(data, dict):
        return False
    new = deck_free_settings(data) if shareable else copy.deepcopy(data)
    if shareable:
        for key in tuple(_COLLECTION_KEYS) + _SHARE_STRIP_KEYS:
            if key in target.config:
                new[key] = copy.deepcopy(target.config[key])
    # Merge custom presets & heatmap palettes so importing doesn't wipe out the user's own presets
    for merge_key in (Config.THEME_CUSTOM_PRESETS, Config.HEATMAP_CUSTOM_PALETTES):
        old_val = target.config.get(merge_key)
        imp_val = new.get(merge_key)
        if isinstance(old_val, dict) and isinstance(imp_val, dict):
            merged = copy.deepcopy(old_val)
            merged.update(copy.deepcopy(imp_val))
            new[merge_key] = merged
        elif isinstance(old_val, list) and isinstance(imp_val, list):
            seen = {json.dumps(x, sort_keys=True) for x in imp_val}
            merged = copy.deepcopy(imp_val) + [copy.deepcopy(x) for x in old_val if json.dumps(x, sort_keys=True) not in seen]
            new[merge_key] = merged
    normalized = target._normalize_config(new)
    target._save_config(normalized)
    for manager in _live_managers() + [target]:
        if getattr(manager, "_config_path", None) == target._config_path:
            try:
                manager.config.clear()
                manager.config.update(copy.deepcopy(normalized))
            except Exception:
                from .details.logic.logger import log_swallowed

                log_swallowed()
    return True


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


def addon_config() -> ConfigManager:
    """The add-on's settings for the open profile (Anki's main window)."""
    from aqt import mw

    return ConfigManager(mw)
