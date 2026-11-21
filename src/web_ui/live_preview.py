# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Live preview of a widget's settings (web_ui/widget_settings.py) in the web pages.

The settings apply each change at once to the configs they edit; after each change (_schedule):
  - the pinned block (web_ui/pinned.py) takes the boxes' new looks;
  - the web Deep Dive window that opened the dialog takes the new theme and reads its charts again
    (its config object is the one the dialog edits).
Nothing is saved here: Cancel puts the old values back and the pages follow."""

from aqt import mw
from aqt.qt import QTimer

from ..details.logic.logger import log_warn

_state = {"dlg": None, "timer": None}


def _schedule(dlg, cancelled=False):
    _state["dlg"], _state["cancelled"] = dlg, cancelled
    t = _state["timer"]
    if t is None:
        t = _state["timer"] = QTimer(mw)
        t.setSingleShot(True)
        t.timeout.connect(_run)
    t.start(40)


def chart_style_changed(conf):
    """Settings > General > Chart Style moved (Total / Average Lines, Total Line, Bar Gradient...): the web charts
    take it at once, once for a burst of slider steps, from the dialog's config not saved yet."""
    _state["style_conf"] = conf
    t = _state.get("style_timer")
    if t is None:
        t = _state["style_timer"] = QTimer(mw)
        t.setSingleShot(True)
        t.timeout.connect(_run_style)
    t.start(40)


def _run_style():
    conf = _state.get("style_conf")
    if not isinstance(conf, dict):
        return
    try:
        from . import pinned

        if pinned.enabled():
            pinned.preview_styles(conf=dict(conf))
    except Exception as e:
        log_warn(f"live preview (chart style, pinned): {e!r}", tag="WEB")
    try:
        from aqt.qt import QApplication

        from .window import WebDeepDiveDialog

        for w in QApplication.topLevelWidgets():
            if isinstance(w, WebDeepDiveDialog) and w.isVisible():
                w.preview_live()
    except Exception as e:
        log_warn(f"live preview (chart style, window): {e!r}", tag="WEB")


def _web_window(dlg):
    from .window import WebDeepDiveDialog

    w = dlg
    for _ in range(12):
        try:
            w = w.parent()
        except Exception:
            return None
        if w is None:
            return None
        if isinstance(w, WebDeepDiveDialog):
            return w
    return None


def _run():
    dlg = _state.get("dlg")
    if dlg is None:
        return
    try:
        from . import pinned

        if pinned.enabled() and not getattr(dlg, "is_grid", False) and not getattr(dlg, "is_dashboard_context", False):
            conf = dict(pinned._conf())
            own = None
            if getattr(dlg, "is_unlinked", False):
                wid = (dlg.widget_def or {}).get("id")
                if wid:
                    own = {wid: dict(dlg.local_config or {}, use_custom_style=True)}
            elif isinstance(getattr(dlg, "global_config", None), dict):
                conf.update(dlg.global_config)
            # the widget's own settings being edited (Chart Appearance: opacity, average / total lines, gradient,
            # grid...): its chart takes them at once too; Cancel gives the saved ones back
            wid = (dlg.widget_def or {}).get("id")
            edit = {wid: dict(dlg.widget_def)} if wid and not _state.get("cancelled") else None
            pinned.preview_styles(conf=conf, own=own, edit=edit)
    except Exception as e:
        log_warn(f"live preview (pinned): {e!r}", tag="WEB")
    try:
        win = _web_window(dlg)
        if win is not None:
            # a chart's own dialog (its id "<type>_g"): the chart reads what the dialog has so far (providers)
            from . import providers

            wid = str((dlg.widget_def or {}).get("id") or "")
            try:
                # closed (Save) before this step came: its settings are saved, read from there
                shown = bool(getattr(dlg, "_web_open", False))
            except RuntimeError:
                shown = False
            if shown and getattr(dlg, "is_grid", False) and wid.endswith("_g") and not _state.get("cancelled"):
                providers._LIVE["own"] = {wid[:-2]: dict(dlg.widget_def)}
            else:
                providers._LIVE["own"] = None
            if shown and getattr(dlg, "is_dashboard_context", False) and not _state.get("cancelled"):
                sk = (dlg.widget_def or {}).get("stat_key")
                if sk and isinstance(getattr(dlg, "local_config", None), dict) and isinstance(getattr(dlg, "global_config", None), dict):
                    from ..const import Config

                    styles = dlg.global_config.setdefault(Config.DASH_STAT_STYLES, {})
                    if getattr(dlg, "is_unlinked", False):
                        styles[str(sk)] = dict(dlg.local_config, use_custom_style=True)
                    elif str(sk) in styles and isinstance(styles[str(sk)], dict):
                        styles[str(sk)] = dict(styles[str(sk)], use_custom_style=False)
            win.preview_live()
    except Exception as e:
        log_warn(f"live preview (window): {e!r}", tag="WEB")
