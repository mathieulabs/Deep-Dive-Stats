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
from .....logic.stat_cards import DECK_STATE_FIELDS, HISTORY_DERIVED_FIELDS, STAT_VALUE_FIELD_BINDINGS
animations_enabled = lambda *_a, **_k: False
from .....logic.tabs import DEFAULT_DETAILS_TABS
from .....logic.logger import log_swallowed
from ......i18n import tr, tr_n, tr_name


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
                return tr("Custom dates: {start} to {end}", start=start, end=end)
            if start and tab.get("to_today"):
                return tr("Custom dates: {start} to today", start=start)
            return tr("Custom absolute range")
        days = int(tab.get("days", 7) or 7)
        return tr_n("Custom relative range ({n} day)", "Custom relative range ({n} days)", days)
    return tr("Project time span: {name}", name=tr_name(str(tab.get("title", "") or "").strip()))


def get_available_span_tokens(cfg=None):
    tabs = _tabs_config_from_source(cfg)
    entries = []
    added_ranges = set()
    for tab in tabs:
        label = str(tab.get("title", "") or "").strip()
        range_val = tab.get("range")
        if not label or range_val is None:
            continue
        # A default tab name is suggested translated; both names work in a template.
        if range_val == Period.CUSTOM:
            entries.append((tr_name(label), _span_description(tab)))
            continue
        if range_val in added_ranges:
            continue
        added_ranges.add(range_val)
        entries.append((tr_name(label), _span_description(tab)))
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
        spec = (
            int(range_val),
            int(tab.get("days", 7) or 7),
            str(tab.get("custom_type", "relative") or "relative"),
            str(tab.get("start_date", "") or ""),
            str(tab.get("end_date", "") or ""),
        )
        lookup[label.lower()] = spec
        lookup.setdefault(tr_name(label).lower(), spec)
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
    tokens = [("current", tr("Current widget deck")), ("all", tr("All decks")), ("deleted", tr("Deleted cards"))]
    try:
        decks = list(mw.col.decks.all_names_and_ids() or [])
        tokens.extend((str(d.name), tr("Deck {name}", name=d.name)) for d in decks if getattr(d, "name", None))
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
                value = tr("{value}s", value=0)
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


# safe_html: an allow-list (what the editor writes), not a list of what to take out: anything else is left out.
_SAFE_TAGS = frozenset({
    "p", "div", "span", "br", "hr", "b", "strong", "i", "em", "u", "s", "strike", "del", "ins", "sub", "sup",
    "small", "big", "font", "center", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "li", "blockquote", "pre",
    "code", "table", "thead", "tbody", "tfoot", "tr", "td", "th", "caption", "col", "colgroup",
})
_VOID_TAGS = frozenset({"br", "hr", "col"})
_SAFE_ATTRS = frozenset({
    "style", "align", "dir", "color", "face", "size", "start", "type", "value", "colspan", "rowspan", "valign",
    "width", "height", "bgcolor", "border", "cellspacing", "cellpadding",
})
# left out with all they hold (their words are not text to show: code, a picture, a frame...)
_DROPPED_WITH_CONTENT = frozenset({
    "script", "style", "iframe", "object", "embed", "applet", "svg", "math", "template", "noscript", "noembed",
    "noframes", "frame", "frameset", "textarea", "select", "title", "head", "xmp", "plaintext", "audio", "video",
})
# a style's declaration that could load something or run something (or hide it behind CSS escapes)
_UNSAFE_CSS_RE = re.compile(r"url\s*\(|image-set|image\s*\(|expression|@import|javascript:|behavior|binding|\\",
                            re.IGNORECASE)


def _safe_style(value):
    value = re.sub(r"/\*.*?\*/", "", value, flags=re.DOTALL)
    kept = [d.strip() for d in value.split(";") if d.strip() and not _UNSAFE_CSS_RE.search(d)]
    return "; ".join(kept)


def safe_html(text):
    """A text's sentence as the web pages show it: the editor's formatting kept (titles, lists, lines, alignment,
    sizes, colors), nothing that runs, loads or leaves the page. Only the tags and attributes the editor writes are
    kept; a link is its words only, a picture, a script, an SVG or a frame is left out."""
    from html.parser import HTMLParser

    out = []
    skip = []  # the dropped-with-content tags open

    class _Clean(HTMLParser):
        def handle_starttag(self, tag, attrs):
            self._tag(tag, attrs, closed=False)

        def handle_startendtag(self, tag, attrs):
            self._tag(tag, attrs, closed=True)

        def _tag(self, tag, attrs, closed):
            tag = tag.lower()
            if tag in _DROPPED_WITH_CONTENT:
                if not closed:
                    skip.append(tag)
                return
            if skip or tag not in _SAFE_TAGS:
                return
            parts = []
            for name, value in attrs:
                name = (name or "").lower()
                if name not in _SAFE_ATTRS or value is None:
                    continue
                if name == "style":
                    value = _safe_style(value)
                    if not value:
                        continue
                parts.append(f' {name}="{html.escape(value, quote=True)}"')
            out.append(f"<{tag}{''.join(parts)}" + (" />" if tag in _VOID_TAGS else ">"))
            if closed and tag not in _VOID_TAGS:
                out.append(f"</{tag}>")

        def handle_endtag(self, tag):
            tag = tag.lower()
            if skip:
                if tag == skip[-1]:
                    skip.pop()
                return
            if tag in _SAFE_TAGS and tag not in _VOID_TAGS:
                out.append(f"</{tag}>")

        def handle_data(self, data):
            if not skip:
                out.append(html.escape(data, quote=False))

    try:
        parser = _Clean(convert_charrefs=True)
        parser.feed(str(text or ""))
        parser.close()
    except Exception:
        log_swallowed()
        return html.escape(re.sub(r"<[^>]*>", "", str(text or "")), quote=False)
    return "".join(out)


def shown_template(template):
    """The template as shown: the default one of new profiles in the interface language."""
    from ......const.config import TEXT_WIDGET_DEFAULT_SENTENCE, TEXT_WIDGET_DEFAULT_TEMPLATE

    if template == TEXT_WIDGET_DEFAULT_TEMPLATE:
        return template.replace(TEXT_WIDGET_DEFAULT_SENTENCE, tr_name(TEXT_WIDGET_DEFAULT_SENTENCE))
    return template


def _update_text_label(label, widget_def, deck_id, cache=None, fail_if_not_cached=False, cfg=None):
    if cfg is None:
        cfg = _addon_config()

    template = shown_template(widget_def.get("template", ""))
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
