# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Builder for the 'text_label' pinned widget type."""

import html
import re

from aqt import mw

from ..utils import _addon_config
from . import Config, Period
from .stat_card import _build_stat_values_map
from .time_units import apply_time_unit as _apply_time_unit
from ....chart_utils.formatting import fmt_num
from ....stats_cards.logic.constants import ANIM_DISABLED_DURATION_MS, ROLL_ANIM_DURATION_MS
from ....stats_cards.logic.model import DECK_STATE_FIELDS, HISTORY_DERIVED_FIELDS, STAT_VALUE_FIELD_BINDINGS
from .....animations.motion import animations_enabled
from .....logic.tabs import DEFAULT_DETAILS_TABS
from .....logic.logger import log_swallowed


_CONFIG_KEY_TO_FIELD: dict = {}
for _field, _dd_key, _dash_key in STAT_VALUE_FIELD_BINDINGS:
    if _dd_key:
        _CONFIG_KEY_TO_FIELD[_dd_key] = _field
    _CONFIG_KEY_TO_FIELD[_dash_key] = _field

AVAILABLE_VARS: tuple = tuple(field for field, *_ in STAT_VALUE_FIELD_BINDINGS)


DECK_OVERRIDE_SYMBOL = "@"

# A trailing "~" marks a variable whose changes do not fade the text: {reviews~}.
_TEMPLATE_RE = re.compile(
    r"\{(?P<var>\w+)(?::(?P<span>[^@}|]+?))?(?:@(?P<deck>[^}|]+?))?(?:\|(?P<unit>[^}]+?))?(?P<static>~)?\}"
)

# Time unit override: {total_time|min} (see time_units.py).


def _normalize_template_markup(template):
    text = str(template or "")
    if not text:
        return ""

    normalized = html.unescape(text).strip()
    if not normalized.startswith("<") and "</p>" in normalized:
        first_close = normalized.find("</p>")
        prefix = normalized[:first_close]
        suffix = normalized[first_close + 4 :]
        if suffix.startswith("</p>"):
            suffix = suffix[4:]
        normalized = f"<p>{prefix}</p>{suffix}"
    return normalized


def _stat_values_by_field(stat_values_config_keyed):
    if not stat_values_config_keyed:
        return {}
    out = {}
    for config_key, value in stat_values_config_keyed.items():
        field = _CONFIG_KEY_TO_FIELD.get(config_key)
        if field and field not in out:
            out[field] = value
    return out


def _config_dict(cfg=None):
    if cfg is None:
        cfg = _addon_config()
    if isinstance(cfg, dict):
        return cfg
    return getattr(cfg, "config", {}) or {}


def _tabs_config_from_source(cfg=None):
    conf = _config_dict(cfg)
    return conf.get(Config.DETAILS_TABS_DATA, DEFAULT_DETAILS_TABS.copy())


def _span_description(tab: dict) -> str:
    range_val = tab.get("range")
    if range_val == Period.CUSTOM:
        custom_type = str(tab.get("custom_type", "relative") or "relative")
        if custom_type == "absolute":
            start = str(tab.get("start_date", "") or "")
            end = str(tab.get("end_date", "") or "")
            if start and end:
                return f"Custom dates: {start} to {end}"
            if start and tab.get("to_today"):
                return f"Custom dates: {start} to today"
            return "Custom absolute range"
        days = int(tab.get("days", 7) or 7)
        return f"Custom relative range ({days} days)"
    return f"Project time span: {str(tab.get('title', '') or '').strip()}"


def get_available_span_tokens(cfg=None):
    tabs = _tabs_config_from_source(cfg)
    entries = []
    added_ranges = set()
    for tab in tabs:
        label = str(tab.get("title", "") or "").strip()
        range_val = tab.get("range")
        if not label or range_val is None:
            continue
        if range_val == Period.CUSTOM:
            entries.append((label, _span_description(tab)))
            continue
        if range_val in added_ranges:
            continue
        added_ranges.add(range_val)
        entries.append((label, _span_description(tab)))
    return entries


def _builtin_span_specs():
    return {
        "total": (Period.TOTAL, 7, "relative", "", ""),
        "week": (Period.WEEK, 7, "relative", "", ""),
        "past week": (Period.WEEK, 7, "relative", "", ""),
        "2w": (Period.TWO_WEEKS, 7, "relative", "", ""),
        "2 weeks": (Period.TWO_WEEKS, 7, "relative", "", ""),
        "two weeks": (Period.TWO_WEEKS, 7, "relative", "", ""),
        "past 2 weeks": (Period.TWO_WEEKS, 7, "relative", "", ""),
        "month": (Period.MONTH, 7, "relative", "", ""),
        "past month": (Period.MONTH, 7, "relative", "", ""),
        "3m": (Period.THREE_MONTHS, 7, "relative", "", ""),
        "3 months": (Period.THREE_MONTHS, 7, "relative", "", ""),
        "three months": (Period.THREE_MONTHS, 7, "relative", "", ""),
        "past 3 months": (Period.THREE_MONTHS, 7, "relative", "", ""),
        "year": (Period.YEAR, 7, "relative", "", ""),
        "past year": (Period.YEAR, 7, "relative", "", ""),
        "today": (Period.TODAY, 7, "relative", "", ""),
        "yesterday": (Period.YESTERDAY, 7, "relative", "", ""),
        "last year": (Period.LAST_YEAR, 7, "relative", "", ""),
    }


def _span_lookup(cfg=None):
    lookup = dict(_builtin_span_specs())
    for tab in _tabs_config_from_source(cfg):
        label = str(tab.get("title", "") or "").strip()
        range_val = tab.get("range")
        if not label or range_val is None:
            continue
        lookup[label.lower()] = (
            int(range_val),
            int(tab.get("days", 7) or 7),
            str(tab.get("custom_type", "relative") or "relative"),
            str(tab.get("start_date", "") or ""),
            str(tab.get("end_date", "") or ""),
        )
    return lookup


def _resolve_span_spec(
    span_token,
    default_span,
    default_days,
    cfg=None,
    *,
    default_custom_type="relative",
    default_start_date_str="",
    default_end_date_str="",
):
    token = str(span_token or "").strip()
    if not token:
        return (
            int(default_span),
            int(default_days or 7),
            str(default_custom_type or "relative"),
            str(default_start_date_str or ""),
            str(default_end_date_str or ""),
        )
    return _span_lookup(cfg).get(token.lower())


def get_available_deck_override_tokens():
    tokens = [("current", "Current widget deck"), ("all", "All decks"), ("deleted", "Deleted cards")]
    try:
        decks = list(mw.col.decks.all_names_and_ids() or [])
        tokens.extend((str(d.name), f"Deck {d.name}") for d in decks if getattr(d, "name", None))
    except Exception:
        log_swallowed()
    return tokens


_UNKNOWN_DECK = object()  # an @deck token that matches no deck ("all" resolves to None: all decks)


def _resolve_deck_token(deck_token, default_deck_id):
    token = str(deck_token or "").strip()
    if not token:
        return default_deck_id

    lowered = token.lower()
    if lowered == "current":
        return default_deck_id
    if lowered == "all":
        return None
    if lowered == "deleted":
        return -1

    try:
        decks = list(mw.col.decks.all_names_and_ids() or [])
        for deck in decks:
            name = str(getattr(deck, "name", "") or "")
            if name == token or name.lower() == lowered:
                return int(deck.id)
    except Exception:
        log_swallowed()
    return _UNKNOWN_DECK


def _render_runtime_payload(payload, values=None):
    if not payload:
        return ""
    template = str(payload.get("template", "") or "")
    entries = list(payload.get("entries", []) or [])
    replacements = values if values is not None else [str(entry.get("value", "")) for entry in entries]
    idx = 0

    def _replacer(m):
        nonlocal idx
        if idx >= len(replacements):
            return m.group(0)
        out = str(replacements[idx])
        idx += 1
        return out

    return _TEMPLATE_RE.sub(_replacer, template)


def _build_runtime_payload(
    template,
    deck_id,
    default_span,
    default_days,
    *,
    cache=None,
    fail_if_not_cached=False,
    cfg=None,
    default_custom_type="relative",
    default_start_date_str="",
    default_end_date_str="",
):
    if not template:
        return {"template": "", "entries": [], "resolved": ""}
    template = _normalize_template_markup(template)

    if cfg is None:
        cfg = _addon_config()

    requests_needed: set = set()
    raw_matches = []
    for m in _TEMPLATE_RE.finditer(template):
        span_token = m.group("span")
        deck_token = m.group("deck")
        span_spec = _resolve_span_spec(
            span_token,
            default_span,
            default_days,
            cfg=cfg,
            default_custom_type=default_custom_type,
            default_start_date_str=default_start_date_str,
            default_end_date_str=default_end_date_str,
        )
        resolved_deck = _resolve_deck_token(deck_token, deck_id) if deck_token else deck_id
        if isinstance(resolved_deck, list):
            # Several decks picked for the widget: the selection is a list, used as a key below.
            resolved_deck = tuple(resolved_deck)
        raw_matches.append((m, span_spec, resolved_deck))
        if span_spec is None or resolved_deck is _UNKNOWN_DECK:
            continue
        span, days, custom_type, start_date_str, end_date_str = span_spec
        requests_needed.add((resolved_deck, span, days, custom_type, start_date_str, end_date_str))

    with_day_stats = any(m.group("var") in HISTORY_DERIVED_FIELDS for m, _s, _d in raw_matches)
    with_deck_state = any(m.group("var") in DECK_STATE_FIELDS for m, _s, _d in raw_matches)
    stat_maps: dict = {}
    raw_maps: dict = {}
    for resolved_deck, span, days, custom_type, start_date_str, end_date_str in requests_needed:
        raw = _build_stat_values_map(
            list(resolved_deck) if isinstance(resolved_deck, tuple) else resolved_deck,
            span,
            days,
            cache=cache,
            fail_if_not_cached=fail_if_not_cached,
            cfg=cfg,
            custom_type=custom_type,
            start_date_str=start_date_str,
            end_date_str=end_date_str,
            with_day_stats=with_day_stats,
            with_deck_state=with_deck_state,
        )
        if raw is None:
            return None
        stat_maps[(resolved_deck, span, days, custom_type, start_date_str, end_date_str)] = _stat_values_by_field(raw)
        raw_maps[(resolved_deck, span, days, custom_type, start_date_str, end_date_str)] = raw

    entries = []
    for m, span_spec, resolved_deck in raw_matches:
        var = m.group("var")
        span_token = m.group("span")
        deck_token = m.group("deck")
        if span_spec is None or resolved_deck is _UNKNOWN_DECK:
            value = m.group(0)
        else:
            span, days, custom_type, start_date_str, end_date_str = span_spec
            values = stat_maps.get((resolved_deck, span, days, custom_type, start_date_str, end_date_str), {})
            value = str(values[var]) if var in values else m.group(0)
            if m.group("unit") and var in values:
                _raw = raw_maps.get((resolved_deck, span, days, custom_type, start_date_str, end_date_str), {})
                _conv = _apply_time_unit(var, m.group("unit"), _raw, int(cfg.config.get(Config.STATS_PRECISION, 2)))
                if _conv is not None:
                    value = _conv
            if var == "avg_time" and value == "N/A":
                # No review yet: a sentence like "({avg_time}/card)" reads "(0s/card)", as in
                # Anki's own line, not "(N/A/card)".
                value = "0s"
        entries.append(
            {
                "raw": m.group(0),
                "var": var,
                "span": str(span_token or ""),
                "deck": str(deck_token or ""),
                "value": str(value),
                "static": bool(m.group("static")),
            }
        )

    payload = {"template": template, "entries": entries}
    payload["resolved"] = _render_runtime_payload(payload)
    return payload


def _only_static_changes(old_payload, new_payload):
    """True when every variable whose value changed is marked static ({var~})."""
    if str(old_payload.get("template", "")) != str(new_payload.get("template", "")):
        return False
    old_entries = list(old_payload.get("entries", []) or [])
    new_entries = list(new_payload.get("entries", []) or [])
    if len(old_entries) != len(new_entries):
        return False
    changed = [n for o, n in zip(old_entries, new_entries) if str(o.get("value")) != str(n.get("value"))]
    return bool(changed) and all(n.get("static") for n in changed)


def _format_roll_value(kind, value, decimals, prefix, suffix):
    if kind == "percent":
        return f"{value:.{decimals}f}%"
    if decimals > 0:
        number_text = f"{value:,.{decimals}f}"
    else:
        number_text = fmt_num(int(round(value)))
    return f"{prefix}{number_text}{suffix}"


class AutoSizeRichLabel:
    """Mixin: makes a QLabel auto-size its height to fit rich text content."""

    def _build_text_document(self):
        from aqt.qt import QTextDocument

        # Before the widget is shown it may not be polished: font() is then the app
        # default, not the stylesheet font, so the text is measured too small and the
        # label wraps and cuts off the second line.
        try:
            self.ensurePolished()
        except Exception:
            log_swallowed()
        doc = QTextDocument()
        doc.setDefaultFont(self.font())
        doc.setDocumentMargin(0)
        text = getattr(self, "_measurement_text", None)
        if text is None:
            text = self.text()
        if text.strip().startswith("<"):
            doc.setHtml(text)
        else:
            doc.setPlainText(text)
        return doc

    def hasHeightForWidth(self):
        return True

    def preferredTextWidth(self):
        from aqt.qt import QLabel, Qt

        measurement_text = getattr(self, "_measurement_text", None)
        if measurement_text is None:
            measurement_text = self.text() or " "

        candidates = []
        try:
            self.ensurePolished()
        except Exception:
            log_swallowed()

        try:
            probe = QLabel()
            probe.setFont(self.font())
            probe.setTextFormat(Qt.TextFormat.RichText)
            probe.setAlignment(self.alignment())
            probe.setContentsMargins(self.contentsMargins())
            probe.setWordWrap(False)
            probe.setText(measurement_text)
            candidates.append(float(probe.sizeHint().width()))
            candidates.append(float(probe.minimumSizeHint().width()))
        except Exception:
            log_swallowed()

        doc = self._build_text_document()
        try:
            doc.setTextWidth(1000000)
        except Exception:
            log_swallowed()
        doc.adjustSize()
        try:
            candidates.append(float(doc.idealWidth()))
        except Exception:
            log_swallowed()
        try:
            candidates.append(float(doc.size().width()))
        except Exception:
            log_swallowed()

        ideal = int(max(candidates) if candidates else 0) + 10
        return max(96, min(ideal, 4096))

    def heightForWidth(self, width):
        margins = self.contentsMargins()
        doc = self._build_text_document()
        doc.setTextWidth(max(width - margins.left() - margins.right(), 1))
        h = int(doc.size().height()) + margins.top() + margins.bottom()
        # Also ask QLabel itself: it lays the text out the way it is painted, so
        # the box is never shorter than what is drawn (no clipped last line).
        try:
            native_h = int(super().heightForWidth(int(width)))
        except Exception:
            native_h = -1
        return max(h, native_h, 20)

    def sizeHint(self):
        from aqt.qt import QSize

        w = self.width() if self.width() > 10 else self.preferredTextWidth()
        return QSize(w, self.heightForWidth(w))

    def minimumSizeHint(self):
        return self.sizeHint()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.updateGeometry()


def _make_text_label_widget(text, parent=None):
    """Create the display QLabel with auto-height and rich text support."""
    from aqt.qt import (
        QLabel,
        Qt,
        QSizePolicy,
        QEasingCurve,
        QPropertyAnimation,
        QTimer,
        QGraphicsOpacityEffect,
        pyqtProperty,
    )

    class _RichLabel(AutoSizeRichLabel, QLabel):
        def __init__(self, parent=None):
            super().__init__(parent)
            self._runtime_payload = None
            self._pending_payload = None
            self._roll_entries = []
            self._roll_progress = 1.0
            self._roll_active = False
            self._fade_progress = 1.0
            self._fade_active = False
            self._fade_swapped_text = False
            self._fade_payload = None
            self._measurement_text = None
            self._fade_effect = QGraphicsOpacityEffect(self)
            self._fade_effect.setOpacity(1.0)
            self.setGraphicsEffect(self._fade_effect)
            self._roll_anim = QPropertyAnimation(self, b"rollProgress")
            self._roll_anim.setDuration(ROLL_ANIM_DURATION_MS if animations_enabled("pinned") else ANIM_DISABLED_DURATION_MS)
            self._roll_anim.setStartValue(0.0)
            self._roll_anim.setEndValue(1.0)
            self._roll_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
            self._roll_anim.finished.connect(self._finish_payload_roll)
            self._fade_anim = QPropertyAnimation(self, b"fadeProgress")
            self._fade_anim.setDuration(ROLL_ANIM_DURATION_MS if animations_enabled("pinned") else ANIM_DISABLED_DURATION_MS)
            self._fade_anim.setStartValue(0.0)
            self._fade_anim.setEndValue(1.0)
            self._fade_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
            self._fade_anim.finished.connect(self._finish_payload_fade)

        @pyqtProperty(float)
        def rollProgress(self):
            return self._roll_progress

        @rollProgress.setter
        def rollProgress(self, value):
            self._roll_progress = float(value)
            if self._roll_active:
                self._apply_roll_progress(self._roll_progress)

        @pyqtProperty(float)
        def fadeProgress(self):
            return self._fade_progress

        @fadeProgress.setter
        def fadeProgress(self, value):
            self._fade_progress = float(value)
            if self._fade_active:
                self._apply_fade_progress(self._fade_progress)

        def setText(self, text):
            super().setText(text)
            # Roll animation frames change the digits only; the box is refitted on
            # the final text (setText is called again when the roll ends).
            if not getattr(self, "_roll_active", False):
                self._schedule_wrapper_refit()

        def _schedule_wrapper_refit(self):
            if getattr(self, "_refit_pending", False):
                return
            self._refit_pending = True
            QTimer.singleShot(0, self._refit_wrapper)

        def _refit_wrapper(self):
            # The card around the label has a fixed size computed from the text. Any text
            # change (live edit, new values, font or theme change) must resize it, or the
            # text wraps and gets cut off or leaves empty space.
            self._refit_pending = False
            try:
                card = self.parentWidget()
                while card is not None and card.objectName() != "pinned_widget_card":
                    card = card.parentWidget()
                if card is not None and hasattr(card, "refit_text_label"):
                    card.refit_text_label()
            except RuntimeError:
                pass

        def changeEvent(self, event):
            super().changeEvent(event)
            try:
                from aqt.qt import QEvent

                if event.type() in (QEvent.Type.FontChange, QEvent.Type.StyleChange):
                    self._schedule_wrapper_refit()
            except Exception:
                log_swallowed()

        def setResolvedPayload(self, payload, animate=True):
            payload = payload or {"template": "", "entries": [], "resolved": ""}
            final_text = str(payload.get("resolved", "") or " ")
            self._measurement_text = final_text

            if animate and self._start_payload_fade(payload):
                self.updateGeometry()
                return

            self._roll_anim.stop()
            self._fade_anim.stop()
            self._roll_active = False
            self._fade_active = False
            self._fade_payload = None
            self._fade_swapped_text = False
            self._fade_effect.setOpacity(1.0)
            self._roll_entries = []
            self._pending_payload = None
            self._runtime_payload = payload
            self.setText(final_text)
            self.updateGeometry()
            QTimer.singleShot(0, self.updateGeometry)

        def _start_payload_fade(self, new_payload):
            old_payload = getattr(self, "_runtime_payload", None)
            if not old_payload:
                return False
            old_text = str(old_payload.get("resolved", "") or " ")
            new_text = str(new_payload.get("resolved", "") or " ")
            if old_text == new_text:
                return False
            if _only_static_changes(old_payload, new_payload):
                return False

            self._roll_anim.stop()
            self._roll_active = False
            self._pending_payload = None
            self._roll_entries = []

            self._fade_anim.stop()
            self._fade_payload = new_payload
            self._fade_active = True
            self._fade_swapped_text = False
            self._fade_progress = 0.0
            self.setText(old_text)
            self._apply_fade_progress(0.0)
            self._fade_anim.start()
            if not animations_enabled("pinned"):
                self._finish_payload_fade()
            return True

        def _apply_fade_progress(self, progress):
            if not self._fade_active or not self._fade_payload:
                return
            t = max(0.0, min(1.0, float(progress)))
            if (not self._fade_swapped_text) and t >= 0.5:
                self._fade_swapped_text = True
                self.setText(str(self._fade_payload.get("resolved", "") or " "))
            if t < 0.5:
                opacity = 1.0 - (0.55 * (t * 2.0))
            else:
                opacity = 0.45 + (0.55 * ((t - 0.5) * 2.0))
            self._fade_effect.setOpacity(max(0.0, min(1.0, float(opacity))))

        def _finish_payload_fade(self):
            self._fade_active = False
            payload = self._fade_payload or self._runtime_payload or {"template": "", "entries": [], "resolved": ""}
            self._fade_payload = None
            self._fade_swapped_text = False
            self._runtime_payload = payload
            self._fade_effect.setOpacity(1.0)
            final_text = str(payload.get("resolved", "") or " ")
            self._measurement_text = final_text
            self.setText(final_text)
            self.updateGeometry()
            QTimer.singleShot(0, self.updateGeometry)

        def _apply_roll_progress(self, progress):
            if not self._pending_payload:
                return
            t = max(0.0, min(1.0, float(progress)))
            values = []
            for entry in self._roll_entries:
                if entry.get("mode") != "roll":
                    values.append(str(entry.get("text", "")))
                    continue
                curr = float(entry["start"]) + ((float(entry["end"]) - float(entry["start"])) * t)
                values.append(
                    _format_roll_value(
                        entry["kind"],
                        curr,
                        entry["decimals"],
                        entry["prefix"],
                        entry["suffix"],
                    )
                )
            rendered_text = _render_runtime_payload(self._pending_payload, values=values) or " "
            self.setText(rendered_text)
            self.updateGeometry()

        def _finish_payload_roll(self):
            self._roll_active = False
            payload = self._pending_payload or self._runtime_payload or {"template": "", "entries": [], "resolved": ""}
            self._pending_payload = None
            self._runtime_payload = payload
            self._roll_entries = []
            final_text = str(payload.get("resolved", "") or " ")
            self._measurement_text = final_text
            self.setText(final_text)
            self.updateGeometry()
            QTimer.singleShot(0, self.updateGeometry)

    label = _RichLabel(parent)
    label.setWordWrap(True)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setTextFormat(Qt.TextFormat.RichText)
    label.setObjectName("pinned_text_label_inner")
    label.setContentsMargins(4, 4, 4, 4)

    sp = label.sizePolicy()
    sp.setHeightForWidth(True)
    sp.setVerticalPolicy(QSizePolicy.Policy.Preferred)
    label.setSizePolicy(sp)

    label.setText(text or " ")
    label._measurement_text = text or " "
    return label


def _build_text_label(widget_def, deck_id, cache=None, parent=None, cfg=None):
    if cfg is None:
        cfg = _addon_config()

    template = widget_def.get("template", "")
    span = widget_def.get("time_span", Period.TOTAL)
    days = widget_def.get("custom_days", 7)
    custom_type = widget_def.get("custom_type", "relative")
    start_date_str = widget_def.get("start_date", "")
    end_date_str = widget_def.get("end_date", "")

    payload = _build_runtime_payload(
        template,
        deck_id,
        span,
        days,
        cache=cache,
        cfg=cfg,
        default_custom_type=custom_type,
        default_start_date_str=start_date_str,
        default_end_date_str=end_date_str,
    )
    text = (payload or {}).get("resolved", "") if payload is not None else ""

    label = _make_text_label_widget(text, parent)
    if hasattr(label, "setResolvedPayload"):
        label.setResolvedPayload(payload or {"template": "", "entries": [], "resolved": text}, animate=False)
    return label


def _update_text_label(label, widget_def, deck_id, cache=None, fail_if_not_cached=False, cfg=None):
    if cfg is None:
        cfg = _addon_config()

    template = widget_def.get("template", "")
    span = widget_def.get("time_span", Period.TOTAL)
    days = widget_def.get("custom_days", 7)
    custom_type = widget_def.get("custom_type", "relative")
    start_date_str = widget_def.get("start_date", "")
    end_date_str = widget_def.get("end_date", "")

    payload = _build_runtime_payload(
        template,
        deck_id,
        span,
        days,
        cache=cache,
        fail_if_not_cached=fail_if_not_cached,
        cfg=cfg,
        default_custom_type=custom_type,
        default_start_date_str=start_date_str,
        default_end_date_str=end_date_str,
    )
    if payload is None:
        return False

    text = payload.get("resolved", "")

    if hasattr(label, "setResolvedPayload"):
        label.setResolvedPayload(payload, animate=False)
        label.updateGeometry()
        return True
    if hasattr(label, "setText"):
        label.setText(text or " ")
        label.updateGeometry()
        return True
    return False
