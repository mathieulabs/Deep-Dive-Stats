# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from enum import Enum
import inspect
import weakref

from aqt.qt import QColor, QObject
from aqt.theme import theme_manager
# Import directly from the defining modules (config.Config, const.ThemePalettes) rather than the
# details.ui aggregator: it imports ui.theme.menu_style, which imports back into this module, a
# circular import.
from ....config import Config
from ....const import ThemePalettes
from ...logic.logger import log_swallowed



def _rel_luminance(c):
    def f(v):
        v = v / 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(c.red()) + 0.7152 * f(c.green()) + 0.0722 * f(c.blue())


def _contrast_ratio(a, b):
    la, lb = _rel_luminance(a), _rel_luminance(b)
    if la < lb:
        la, lb = lb, la
    return (la + 0.05) / (lb + 0.05)


def ensure_contrast(color, bg, min_ratio=3.3):
    """Nudge `color` lighter or darker (keeping its hue) until it reaches
    `min_ratio` contrast against `bg`; used so theme lines stay visible."""
    c = QColor(color)
    if not c.isValid():
        return c
    if _contrast_ratio(c, bg) >= min_ratio:
        return c
    go_dark = _rel_luminance(bg) > 0.4
    for _ in range(40):
        h, s, l, a = c.getHsl()
        l = max(0, l - 6) if go_dark else min(255, l + 6)
        c.setHsl(max(h, 0), s, l, a)
        if _contrast_ratio(c, bg) >= min_ratio or l in (0, 255):
            break
    return c


class ThemeContext(str, Enum):
    DETAILS = "details"
    PINNED = "pinned"
    AUTO = "auto"


def coerce_theme_context(context, default=ThemeContext.DETAILS):
    """Normalize arbitrary context input to ThemeContext."""
    if isinstance(context, ThemeContext):
        return context
    sval = str(context or "").strip().lower()
    if sval == ThemeContext.PINNED.value:
        return ThemeContext.PINNED
    if sval == ThemeContext.DETAILS.value:
        return ThemeContext.DETAILS
    return default


def apply_theme_context(widget, context=ThemeContext.DETAILS, include_children=False):
    """Attach runtime theme-context properties to a widget subtree."""
    if widget is None:
        return
    ctx = coerce_theme_context(context, default=ThemeContext.DETAILS)
    ignore_forced = (ctx == ThemeContext.PINNED)
    targets = [widget]
    if include_children and hasattr(widget, "findChildren"):
        try:
            targets.extend(widget.findChildren(QObject))
        except Exception:
            log_swallowed()
    for obj in targets:
        try:
            obj.setProperty("deepdivestats_theme_context", ctx.value)
            obj.setProperty("deepdivestats_ignore_forced_dark_theme", ignore_forced)
        except Exception:
            continue


def resolve_widget_theme_context(widget, default=ThemeContext.DETAILS):
    """Resolve explicit theme context from widget ancestry with a safe default."""
    if widget is None:
        return coerce_theme_context(default, default=ThemeContext.DETAILS)
    explicit = _widget_context(widget)
    if explicit is not None:
        return explicit
    return coerce_theme_context(default, default=ThemeContext.DETAILS)


def _theme_mode_to_is_dark(mode, native_dark):
    normalized = _normalize_theme_mode(mode) or "native"
    if normalized == "dark":
        return True
    if normalized == "light":
        return False
    return bool(native_dark)


def _resolve_base_mode_for_preset(conf, preset_key):
    if preset_key in ThemePalettes.PRESET_BASE_MODES:
        return ThemePalettes.PRESET_BASE_MODES[preset_key]
    custom_presets = conf.get(Config.THEME_CUSTOM_PRESETS, {}) or {}
    entry = custom_presets.get(preset_key)
    if isinstance(entry, dict):
        if "base_mode" in entry:
            return _normalize_theme_mode(entry.get("base_mode")) or ThemePalettes.MODE_NATIVE
        return ThemePalettes.MODE_DARK
    return ThemePalettes.MODE_DARK


def resolve_details_theme_mode_from_config(conf):
    """Resolve details theme mode from config: native/dark/light."""
    cfg = conf if isinstance(conf, dict) else {}
    preset_key = cfg.get(Config.THEME_PRESET, ThemePalettes.NATIVE)
    mode = _resolve_base_mode_for_preset(cfg, preset_key)
    if cfg.get(Config.THEME_IS_CUSTOM, False):
        raw_override = cfg.get(Config.THEME_CUSTOM_BASE_MODE, None)
        if raw_override is not None:
            mode = _normalize_theme_mode(raw_override) or ThemePalettes.MODE_NATIVE
    return _normalize_theme_mode(mode) or ThemePalettes.MODE_NATIVE


def resolve_theme_runtime_state(conf, context=ThemeContext.DETAILS, native_dark=None):
    """Authoritative runtime theme state for details/pinned contexts."""
    cfg = conf if isinstance(conf, dict) else {}
    ctx = coerce_theme_context(context, default=ThemeContext.DETAILS)
    if native_dark is None:
        try:
            native_dark = bool(theme_manager.get_night_mode()) if theme_manager else False
        except Exception:
            native_dark = False

    details_mode = resolve_details_theme_mode_from_config(cfg)
    details_preset = cfg.get(Config.THEME_PRESET, ThemePalettes.NATIVE)

    if ctx == ThemeContext.DETAILS:
        return {
            "context": ThemeContext.DETAILS.value,
            "mode": details_mode,
            "is_dark": _theme_mode_to_is_dark(details_mode, native_dark),
            "preset": details_preset,
            "use_active_theme": True,
            "use_separate_theme": False,
        }

    use_active = bool(cfg.get(Config.PINNED_USE_ACTIVE_THEME, False))
    use_separate = bool(cfg.get(Config.PINNED_USE_SEPARATE_THEME, False))
    pinned_preset = cfg.get(Config.PINNED_THEME_PRESET, ThemePalettes.NATIVE)

    if not use_active:
        return {
            "context": ThemeContext.PINNED.value,
            "mode": ThemePalettes.MODE_NATIVE,
            "is_dark": bool(native_dark),
            "preset": ThemePalettes.NATIVE,
            "use_active_theme": False,
            "use_separate_theme": False,
        }

    if use_separate:
        pinned_mode = _resolve_base_mode_for_preset(cfg, pinned_preset)
        if bool(cfg.get(Config.PINNED_THEME_IS_CUSTOM, False)):
            raw_pinned_mode = cfg.get(Config.PINNED_THEME_CUSTOM_BASE_MODE, None)
            if raw_pinned_mode is not None:
                pinned_mode = _normalize_theme_mode(raw_pinned_mode) or ThemePalettes.MODE_NATIVE
        pinned_mode = _normalize_theme_mode(pinned_mode) or ThemePalettes.MODE_NATIVE
        return {
            "context": ThemeContext.PINNED.value,
            "mode": pinned_mode,
            "is_dark": _theme_mode_to_is_dark(pinned_mode, native_dark),
            "preset": pinned_preset,
            "use_active_theme": True,
            "use_separate_theme": True,
        }

    return {
        "context": ThemeContext.PINNED.value,
        "mode": details_mode,
        "is_dark": _theme_mode_to_is_dark(details_mode, native_dark),
        "preset": details_preset,
        "use_active_theme": True,
        "use_separate_theme": False,
    }


def _iter_widget_ancestors(widget):
    w = widget
    while w is not None:
        yield w
        w = w.parentWidget() if hasattr(w, "parentWidget") else None


def _normalize_theme_mode(mode):
    if mode is None:
        return None
    sval = str(mode).strip().lower()
    if sval == "dark":
        return "dark"
    if sval == "light":
        return "light"
    if sval in ("native", "auto", ""):
        return "native"
    return None


def _widget_forced_mode(widget):
    try:
        for w in _iter_widget_ancestors(widget):
            mode = _normalize_theme_mode(w.property("deepdivestats_forced_theme_mode"))
            if mode in ("dark", "light"):
                return mode
            if bool(w.property("deepdivestats_force_dark_theme")):
                return "dark"
    except Exception:
        log_swallowed()
    return None


def _widget_ignore_force_dark(widget) -> bool:
    try:
        for w in _iter_widget_ancestors(widget):
            if bool(w.property("deepdivestats_ignore_forced_dark_theme")):
                return True
    except Exception:
        log_swallowed()
    return False


def _widget_context(widget):
    try:
        for w in _iter_widget_ancestors(widget):
            raw = w.property("deepdivestats_theme_context")
            if not raw:
                continue
            sval = str(raw).strip().lower()
            if sval == ThemeContext.PINNED.value:
                return ThemeContext.PINNED
            if sval == ThemeContext.DETAILS.value:
                return ThemeContext.DETAILS
    except Exception:
        log_swallowed()
    return None


def _load_live_addon_config():
    try:
        from aqt import mw
    except Exception:
        return {}

    try:
        # shared read-only config (callers here only read it, and copy
        # before deriving a modified dict).
        from ....config import read_config_dict

        conf = read_config_dict()
        if isinstance(conf, dict):
            return conf
    except Exception:
        log_swallowed()

    try:
        addon = mw.addonManager.addonFromModule(__name__)
        meta = mw.addonManager.addonMeta(addon)
        conf = meta.get("config", {}) if isinstance(meta, dict) else {}
        return conf if isinstance(conf, dict) else {}
    except Exception:
        return {}


class _ThemeManager:
    def __init__(self):
        self._details_mode = "native"
        self._pinned_use_active_theme = False
        self._pinned_use_separate_theme = False
        self._pinned_theme_preset = ThemePalettes.NATIVE
        self._cache = {}
        self._listeners = []
        self._last_native_dark = None

    def _native_dark(self) -> bool:
        try:
            current = bool(theme_manager.get_night_mode()) if theme_manager else False
        except Exception:
            current = False
        if self._last_native_dark is None:
            self._last_native_dark = current
        elif self._last_native_dark != current:
            self._last_native_dark = current
            self.invalidate_cache()
        return current

    def invalidate_cache(self):
        self._cache.clear()

    def set_details_theme_mode(self, mode):
        mode = _normalize_theme_mode(mode) or "native"
        if self._details_mode != mode:
            self._details_mode = mode
            self.invalidate_cache()

    def is_details_force_dark(self) -> bool:
        return self._details_mode == "dark"

    def set_pinned_use_active_theme(self, enabled: bool):
        enabled = bool(enabled)
        if self._pinned_use_active_theme != enabled:
            self._pinned_use_active_theme = enabled
            self.invalidate_cache()

    def set_pinned_use_separate_theme(self, enabled: bool):
        enabled = bool(enabled)
        if self._pinned_use_separate_theme != enabled:
            self._pinned_use_separate_theme = enabled
            self.invalidate_cache()

    def set_pinned_theme_preset(self, preset_key):
        preset = str(preset_key or "").strip() or ThemePalettes.NATIVE
        if self._pinned_theme_preset != preset:
            self._pinned_theme_preset = preset
            self.invalidate_cache()

    def _normalize_base_mode(self, mode):
        sval = str(mode).strip().lower() if mode is not None else ""
        if sval == ThemePalettes.MODE_DARK:
            return ThemePalettes.MODE_DARK
        if sval == ThemePalettes.MODE_LIGHT:
            return ThemePalettes.MODE_LIGHT
        return ThemePalettes.MODE_NATIVE

    def _resolve_preset_base_mode(self, conf, preset_key):
        if preset_key in ThemePalettes.PRESET_BASE_MODES:
            return ThemePalettes.PRESET_BASE_MODES[preset_key]
        custom_presets = conf.get(Config.THEME_CUSTOM_PRESETS, {}) or {}
        entry = custom_presets.get(preset_key)
        if isinstance(entry, dict):
            if "base_mode" in entry:
                return self._normalize_base_mode(entry.get("base_mode"))
            return ThemePalettes.MODE_DARK
        return ThemePalettes.MODE_DARK

    def _resolve(self, widget_or_context):
        if isinstance(widget_or_context, ThemeContext):
            return widget_or_context, None
        if isinstance(widget_or_context, str):
            sval = widget_or_context.strip().lower()
            if sval == ThemeContext.PINNED.value:
                return ThemeContext.PINNED, None
            if sval == ThemeContext.DETAILS.value:
                return ThemeContext.DETAILS, None

        widget = widget_or_context if hasattr(widget_or_context, "parentWidget") else None
        if widget is None:
            return ThemeContext.DETAILS, None

        explicit = _widget_context(widget)
        if explicit is not None:
            return explicit, widget

        if _widget_ignore_force_dark(widget):
            return ThemeContext.PINNED, widget
        return ThemeContext.DETAILS, widget

    def is_dark(self, widget_or_context=None) -> bool:
        context, widget = self._resolve(widget_or_context)
        native_dark = self._native_dark()
        if context == ThemeContext.PINNED:
            try:
                conf = _load_live_addon_config()
                runtime = resolve_theme_runtime_state(conf, ThemeContext.PINNED, native_dark=native_dark)
                return bool(runtime.get("is_dark", native_dark))
            except Exception:
                return native_dark

        if widget is not None:
            if _widget_ignore_force_dark(widget):
                return native_dark
            forced_mode = _widget_forced_mode(widget)
            if forced_mode == "dark":
                return True
            if forced_mode == "light":
                return False

        if self._details_mode == "dark":
            return True
        if self._details_mode == "light":
            return False
        return native_dark

    def get_palette(self, widget_or_context=None):
        context, widget = self._resolve(widget_or_context)
        native_dark = self._native_dark()
        details_mode = self._details_mode
        widget_mode = _widget_forced_mode(widget) if widget is not None else None
        widget_ignored = bool(widget is not None and _widget_ignore_force_dark(widget))
        key = (context.value, native_dark, details_mode, widget_mode, widget_ignored)
        colors = self._cache.get(key)
        if colors is None:
            is_dark = self.is_dark(widget_or_context)
            text_primary = QColor("#f4f4f5" if is_dark else "#18181b")
            text_secondary = QColor("#d8d8d8" if is_dark else "#8c8c8c")
            bg = QColor("#18181b" if is_dark else "#ffffff")
            border = QColor("#3f3f46" if is_dark else "#d4d4d8")
            accent = QColor("#58a6ff" if is_dark else "#3b82f6")
            theme_palette_applied = False
            _tpal_total_line = None

            if context == ThemeContext.DETAILS:
                try:
                    from ...ui.theme import get_theme_palette, get_theme_effective_is_dark

                    conf = _load_live_addon_config()
                    tpal = get_theme_palette(conf, is_dark=is_dark)
                    if isinstance(tpal, dict):
                        if self._details_mode != "native":
                            is_dark = bool(get_theme_effective_is_dark(conf))
                        text_primary = QColor(tpal.get("text_primary", text_primary.name()))
                        text_secondary = QColor(tpal.get("text_secondary", text_secondary.name()))
                        bg = QColor(tpal.get("bg_root", bg.name()))
                        border = QColor(tpal.get("border_strong", border.name()))
                        accent = QColor(tpal.get("accent", accent.name()))
                        _tpal_total_line = tpal.get("total_line") or None
                        theme_palette_applied = True
                except Exception:
                    log_swallowed()

            # Pinned context: optionally use the active theme palette instead of
            # hardcoded native colors. Controlled by set_pinned_use_active_theme().
            elif context == ThemeContext.PINNED and self._pinned_use_active_theme:
                try:
                    from ...ui.theme import get_theme_palette

                    conf = _load_live_addon_config()
                    runtime = resolve_theme_runtime_state(
                        conf,
                        ThemeContext.PINNED,
                        native_dark=native_dark,
                    )
                    is_dark = bool(runtime.get("is_dark", native_dark))
                    if bool(runtime.get("use_separate_theme", False)):
                        pinned_preset = str(runtime.get("preset") or ThemePalettes.NATIVE)
                        conf_for_pinned = dict(conf)
                        conf_for_pinned[Config.THEME_PRESET] = pinned_preset
                        conf_for_pinned[Config.THEME_IS_CUSTOM] = bool(
                            conf.get(Config.PINNED_THEME_IS_CUSTOM, False)
                        )
                        conf_for_pinned[Config.THEME_CUSTOM_COLORS] = (
                            conf.get(Config.PINNED_THEME_CUSTOM_COLORS, {}) or {}
                        )
                        conf_for_pinned[Config.THEME_CUSTOM_BASE_MODE] = conf.get(
                            Config.PINNED_THEME_CUSTOM_BASE_MODE, None
                        )
                        tpal = get_theme_palette(conf_for_pinned, is_dark=is_dark)
                    else:
                        tpal = get_theme_palette(conf, is_dark=is_dark)
                    if isinstance(tpal, dict):
                        text_primary = QColor(tpal.get("text_primary", text_primary.name()))
                        text_secondary = QColor(tpal.get("text_secondary", text_secondary.name()))
                        bg = QColor(tpal.get("bg_root", bg.name()))
                        border = QColor(tpal.get("border_strong", border.name()))
                        accent = QColor(tpal.get("accent", accent.name()))
                        _tpal_total_line = tpal.get("total_line") or None
                        theme_palette_applied = True
                except Exception:
                    log_swallowed()

            if theme_palette_applied:
                try:
                    text_secondary = ensure_contrast(text_secondary, bg, 4.0)
                    accent = ensure_contrast(accent, bg, 3.0)
                except Exception:
                    log_swallowed()

            grid = QColor(text_secondary)
            grid.setAlpha(12 if is_dark else 10)
            bg_hover = QColor(text_primary)
            bg_hover.setAlpha(15 if is_dark else 10)

            # total_line: explicit palette key when available, else text_secondary for
            # custom themes, accent fallback for native/pinned.
            if theme_palette_applied:
                if _tpal_total_line:
                    total_line = QColor(_tpal_total_line)
                    if not total_line.isValid():
                        total_line = QColor(text_secondary)
                else:
                    # Prefer accent as a visible default when the palette doesn't define
                    # an explicit total_line color.
                    total_line = QColor(accent) if accent is not None else QColor(text_secondary)
            else:
                total_line = QColor(accent) if accent is not None else QColor("#ffffff" if is_dark else "#000000")

            try:
                total_line = ensure_contrast(total_line, bg, 3.3)
            except Exception:
                log_swallowed()

            colors = {
                "text": text_secondary.name(),
                "text_primary": text_primary.name(),
                "text_secondary": text_secondary.name(),
                "grid": (grid.red(), grid.green(), grid.blue(), grid.alpha()),
                "bg": bg.name(),
                "border": border.name(),
                "accent": accent.name(),
                "bg_hover": (bg_hover.red(), bg_hover.green(), bg_hover.blue(), bg_hover.alpha()),
                "total_line": total_line.name(),
                "is_dark": bool(is_dark),
                # True when an add-on theme palette is active (not Anki native).
                "themed": bool(theme_palette_applied),
            }
            self._cache[key] = colors
        return {
            "text": QColor(colors["text"]),
            "text_primary": QColor(colors["text_primary"]),
            "text_secondary": QColor(colors["text_secondary"]),
            "grid": QColor(*colors["grid"]),
            "bg": QColor(colors["bg"]),
            "border": QColor(colors["border"]),
            "accent": QColor(colors["accent"]),
            "bg_hover": QColor(*colors["bg_hover"]),
            "total_line": QColor(colors["total_line"]),
            "is_dark": bool(colors["is_dark"]),
            "themed": bool(colors.get("themed", False)),
        }

    def subscribe(self, callback):
        try:
            ref = weakref.WeakMethod(callback)
        except TypeError:
            ref = callback
        self._listeners.append(ref)
        return callback

    def unsubscribe(self, callback):
        kept = []
        for ref in self._listeners:
            if isinstance(ref, weakref.WeakMethod):
                cb = ref()
                if cb is None:
                    continue
                if cb == callback:
                    continue
                kept.append(ref)
            else:
                if ref == callback:
                    continue
                kept.append(ref)
        self._listeners = kept

    def emit_theme_changed(self, source=None):
        self.invalidate_cache()
        kept = []
        for ref in self._listeners:
            if isinstance(ref, weakref.WeakMethod):
                cb = ref()
                if cb is None:
                    continue
                kept.append(ref)
            else:
                cb = ref
                kept.append(ref)
            try:
                try:
                    takes_source = bool(inspect.signature(cb).parameters)
                except (TypeError, ValueError):
                    takes_source = True
                if takes_source:
                    cb(source)
                else:
                    cb()
            except Exception:
                log_swallowed()
        self._listeners = kept


_THEME_MANAGER = _ThemeManager()


def get_theme_manager():
    return _THEME_MANAGER


def get_palette(widget_or_context=None):
    return _THEME_MANAGER.get_palette(widget_or_context)


def is_night_mode(widget_or_context=None):
    return _THEME_MANAGER.is_dark(widget_or_context)


def get_theme_colors(widget_or_context=None):
    return get_palette(widget_or_context)


def is_details_context(widget_or_context=None):
    """Return True if the widget is in the Details (non-pinned) theme context."""
    ctx, _ = _THEME_MANAGER._resolve(widget_or_context)
    return ctx != ThemeContext.PINNED


def subscribe_theme_changed(callback):
    return _THEME_MANAGER.subscribe(callback)


def unsubscribe_theme_changed(callback):
    _THEME_MANAGER.unsubscribe(callback)


def emit_theme_changed(source=None):
    _THEME_MANAGER.emit_theme_changed(source=source)


def set_pinned_use_active_theme(enabled: bool):
    _THEME_MANAGER.set_pinned_use_active_theme(enabled)


def set_pinned_use_separate_theme(enabled: bool):
    _THEME_MANAGER.set_pinned_use_separate_theme(enabled)


def set_pinned_theme_preset(preset_key):
    _THEME_MANAGER.set_pinned_theme_preset(preset_key)


_LAST_SYNCED_THEME_SIGNATURE = [None]


def theme_config_signature(conf):
    """Everything a theme refresh can depend on: the add-on config and
    Anki's own light/dark mode. None if it can't be computed."""
    try:
        import json
        from aqt.theme import theme_manager as _anki_theme_manager

        return (
            bool(getattr(_anki_theme_manager, "night_mode", False)),
            json.dumps(_canonical(_style_relevant(conf)), default=str),
        )
    except Exception:
        return None


# Pure navigation/window state: which deck/period the Deep Dive shows, tab
# and splitter positions. Changing these never changes how anything looks.
_NON_STYLE_KEYS = frozenset((
    Config.DETAILS_DEEP_DIVE_IDENTIFIER,
    Config.DETAILS_DEEP_DIVE_TITLE,
    Config.DETAILS_DEEP_DIVE_PERIOD_RANGE,
    Config.DETAILS_LAYOUT_STATE,
    Config.DETAILS_TABLE_DRAWER_AUTO_CLOSE,
    Config.DETAILS_TABLE_DRAWER_SHORTCUT,
    Config.DEEP_DIVE_FILL_HEIGHT,
    Config.DETAILS_TABLE_DRAWER_OPEN,
    Config.DETAILS_TABLE_DRAWER_SIZES,
    Config.DETAILS_TIME_TAB_INDEX,
    Config.DETAILS_DECK_TAB_INDEX,
))


def _style_relevant(conf):
    if not isinstance(conf, dict):
        return {}
    return {k: v for k, v in conf.items() if k not in _NON_STYLE_KEYS}


def _canonical(obj):
    # Config dicts can hold int and str keys side by side (runtime-added
    # entries), which json.dumps(sort_keys=True) refuses to sort.
    if isinstance(obj, dict):
        return [[str(k), _canonical(v)] for k, v in sorted(obj.items(), key=lambda kv: str(kv[0]))]
    if isinstance(obj, (list, tuple)):
        return [_canonical(v) for v in obj]
    return obj


def theme_already_synced(conf):
    """True when listeners were last synced/notified with this exact
    config and light/dark mode, i.e. a new broadcast would be a no-op."""
    sig = theme_config_signature(conf)
    return sig is not None and sig == _LAST_SYNCED_THEME_SIGNATURE[0]


def sync_theme_manager_from_config(conf, emit=False, source=None):
    """Sync theme manager runtime state from a config dict."""
    cfg = conf if isinstance(conf, dict) else {}
    _LAST_SYNCED_THEME_SIGNATURE[0] = theme_config_signature(cfg)
    _THEME_MANAGER.set_details_theme_mode(resolve_details_theme_mode_from_config(cfg))
    _THEME_MANAGER.set_pinned_use_active_theme(bool(cfg.get(Config.PINNED_USE_ACTIVE_THEME, False)))
    _THEME_MANAGER.set_pinned_use_separate_theme(bool(cfg.get(Config.PINNED_USE_SEPARATE_THEME, False)))
    _THEME_MANAGER.set_pinned_theme_preset(cfg.get(Config.PINNED_THEME_PRESET, ThemePalettes.NATIVE))
    if emit:
        _THEME_MANAGER.emit_theme_changed(source=source or "theme_sync")
    return _THEME_MANAGER


def _theme_runtime_state():
    m = _THEME_MANAGER
    return (
        m._details_mode,
        m._pinned_use_active_theme,
        m._pinned_use_separate_theme,
        m._pinned_theme_preset,
    )


def sync_theme_manager_and_notify(conf, source=None):
    """Sync the runtime theme state and notify live widgets if it changed.

    A silent sync at startup can come after widgets were built with the native
    state, so without a broadcast they keep the native accent.
    """
    before = _theme_runtime_state()
    sync_theme_manager_from_config(conf, emit=False)
    if _theme_runtime_state() != before:
        _THEME_MANAGER.emit_theme_changed(source=source or "theme_sync_changed")
    return _THEME_MANAGER


def get_text_col(widget_or_context=None):
    return QColor(get_theme_colors(widget_or_context)["text"])


def get_context_theme_config(widget_or_context=None, conf=None, default=ThemeContext.DETAILS):
    """Config dict whose main theme keys hold the theme a context really uses.

    Settings-style dialogs and menus read the main theme keys. Pinned widgets can
    have their own theme (or none), so a dialog opened from them gets a copy of
    the config with the pinned theme put in those keys.
    """
    if not isinstance(conf, dict):
        conf = _load_live_addon_config() or {}
    if isinstance(widget_or_context, (ThemeContext, str)) or widget_or_context is None:
        ctx = coerce_theme_context(widget_or_context, default=default)
    else:
        ctx = resolve_widget_theme_context(widget_or_context, default=default)
    if ctx != ThemeContext.PINNED:
        return conf
    runtime = resolve_theme_runtime_state(conf, ThemeContext.PINNED)
    out = dict(conf)
    if not runtime.get("use_active_theme", False):
        out[Config.THEME_PRESET] = ThemePalettes.NATIVE
        out[Config.THEME_IS_CUSTOM] = False
    elif runtime.get("use_separate_theme", False):
        out[Config.THEME_PRESET] = str(runtime.get("preset") or ThemePalettes.NATIVE)
        out[Config.THEME_IS_CUSTOM] = bool(conf.get(Config.PINNED_THEME_IS_CUSTOM, False))
        out[Config.THEME_CUSTOM_COLORS] = conf.get(Config.PINNED_THEME_CUSTOM_COLORS, {}) or {}
        out[Config.THEME_CUSTOM_BASE_MODE] = conf.get(Config.PINNED_THEME_CUSTOM_BASE_MODE, None)
    return out


def settings_dialog_qss_for(widget_or_context=None, conf=None, default=ThemeContext.DETAILS):
    """Settings dialog stylesheet in the theme of the given widget or context."""
    from ...ui.theme import get_settings_dialog_style

    return get_settings_dialog_style(
        bool(theme_manager.get_night_mode()),
        get_context_theme_config(widget_or_context, conf, default) or None,
    )
