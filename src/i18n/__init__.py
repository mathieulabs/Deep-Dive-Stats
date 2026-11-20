# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""Translations of the interface.

The English text in the code is the key: tr("Show Legend") returns the translation from
src/i18n/<language>.json, or the English text when there is none. Placeholders use
str.format names, which must be the same in every language:

    tr("Exported to:\\n{path}", path=path)
    tr_n("{n} card", "{n} cards", count)

Texts defined at import time (tables of names) are marked with N_() and translated where
they are shown with tr_name(), since the language is only known once Anki is set up.
tr_name() also takes names saved in the settings: the add-on's default names (stored in
English) are translated, a name the user typed is kept as is.

The language follows Anki unless the user picks one in Settings > General. A change takes
effect after restarting Anki, like Anki's own language setting.

dev_tools/check_translations.py lists missing, unused and inconsistent translations.
"""

import json
import os
import re

AUTO = "auto"
ENGLISH = "en"
# Language code -> name shown in the settings, in that language. A code is the base
# language ("de"), or language_REGION when the region changes the words ("pt_BR").
LANGUAGES = {
    "de": "Deutsch",
    "es": "Español",
    "fr": "Français",
    "it": "Italiano",
    "pl": "Polski",
    "pt_BR": "Português (Brasil)",
    "ru": "Русский",
    "tr": "Türkçe",
    "ja": "日本語",
    "ko": "한국어",
    "zh_CN": "简体中文",
}

# How many plural forms each language has, in the order of its plural_index() rule.
# Every other language has two: [one, other].
PLURAL_FORMS = {"ja": 1, "ko": 1, "zh_CN": 1, "pl": 3, "ru": 3}

_DIR = os.path.dirname(os.path.abspath(__file__))
_state = {"lang": None, "catalog": {}}


def N_(text):
    """Mark a text for translation without translating it yet (import-time tables)."""
    return text


def _language_setting():
    try:
        from ..config import read_config_dict
        from ..const import Config

        return str(read_config_dict().get(Config.LANGUAGE, AUTO) or AUTO)
    except Exception:
        return AUTO


def _anki_language():
    try:
        import anki.lang

        return str(anki.lang.current_lang or "")
    except Exception:
        return ""


def resolve_language(setting=None):
    """The language code the interface uses for this setting ("en" when not translated)."""
    setting = _language_setting() if setting is None else setting
    code = _anki_language() if setting == AUTO else setting
    return match_language(code)


def match_language(code):
    """The translation for a language code like Anki's ("pt_BR", "de_DE", "zh-CN"):
    the same code, else the same language ("de_DE" -> "de", "pt_PT" -> "pt_BR"),
    else English."""
    parts = str(code or "").replace("-", "_").split("_")
    base = parts[0].lower()
    full = f"{base}_{parts[1].upper()}" if len(parts) > 1 and parts[1] else base
    if full in LANGUAGES:
        return full
    if base in LANGUAGES:
        return base
    for known in LANGUAGES:
        if known.split("_")[0] == base:
            return known
    return ENGLISH


def _load_catalog(code):
    if code == ENGLISH:
        return {}
    try:
        with open(os.path.join(_DIR, f"{code}.json"), encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    return {k: v for k, v in data.items() if not k.startswith("@")}


def _profile_ready():
    try:
        from aqt import mw

        return bool(mw is not None and getattr(mw, "pm", None) is not None and mw.pm.name)
    except Exception:
        return False


def language():
    """The active language code. Fixed once a profile is open (see the module docstring)."""
    if _state["lang"] is not None:
        return _state["lang"]
    code = resolve_language()
    if _profile_ready():
        _state["lang"] = code
        _state["catalog"] = _load_catalog(code)
        return code
    # Before a profile is open the language setting cannot be read yet: answer without
    # keeping it, so the first call after the profile opens decides.
    return code


def _catalog():
    language()
    if _state["lang"] is None:
        return _load_catalog(resolve_language())
    return _state["catalog"]


def reset():
    """Forget the active language (profile switch)."""
    _state["lang"] = None
    _state["catalog"] = {}
    _QSS_CACHE.clear()


def _format(text, kwargs):
    if not kwargs:
        return text
    try:
        return text.format(**kwargs)
    except (KeyError, IndexError, ValueError):
        return text


def tr(text, **kwargs):
    """The text in the interface language, with {placeholders} filled from kwargs."""
    value = _catalog().get(text)
    if not isinstance(value, str) or not value:
        value = text
    return _format(value, kwargs)


def plural_forms(code):
    return PLURAL_FORMS.get(code, 2)


def plural_index(code, n):
    """Which plural form a language uses for the count n (see PLURAL_FORMS)."""
    try:
        n = abs(float(n))
    except (TypeError, ValueError):
        return plural_forms(code) - 1
    forms = plural_forms(code)
    if forms == 1:
        return 0
    if code == "fr" or code == "pt_BR":
        return 0 if n < 2 else 1
    if forms == 3:
        if n != int(n):
            return 1  # "1,5 карточки", "1,5 karty": the same form as 2 to 4
        i = int(n)
        if code == "ru" and i % 10 == 1 and i % 100 != 11:
            return 0
        if code == "pl" and i == 1:
            return 0
        if 2 <= i % 10 <= 4 and not 12 <= i % 100 <= 14:
            return 1
        return 2
    return 0 if n == 1 else 1


def tr_n(singular, plural, n, **kwargs):
    """The form of the text for the count n, which is also available as {n}."""
    kwargs.setdefault("n", n)
    code = language()
    value = _catalog().get(singular)
    if isinstance(value, list) and len(value) == plural_forms(code) and all(value):
        text = value[plural_index(code, n)]
    else:
        text = singular if plural_index(ENGLISH, n) == 0 else plural
    return _format(text, kwargs)


# Languages written without capital letters. The add-on's small captions (stat card
# titles, chart and table headers) are upper case with letter spacing; in these languages
# that does nothing for legibility, so the captions are drawn larger without the spacing,
# and units follow the number with no space ("12分", "3시간").
_NO_CASE = {"ja", "ko", "zh_CN"}
_QSS_CACHE = {}
_QSS_LETTER_SPACING = re.compile(r"letter-spacing\s*:\s*[0-9.]+px")
_QSS_SMALL_FONT = re.compile(r"font-size\s*:\s*([0-9.]+)(px|pt)")


def uses_case():
    return language() not in _NO_CASE


def caption_scale():
    """How much larger the small captions are drawn in the interface language."""
    return 1.0 if uses_case() else 1.2


def unit_sep():
    """Text between a number and its unit ("3 h", "3시간")."""
    return " " if uses_case() else ""


def adapt_qss(sheet):
    """A style sheet for the interface language: in languages without capitals, no letter
    spacing and small font sizes 20 % larger (the add-on's captions are 9 to 11 px)."""
    if not sheet or uses_case():
        return sheet
    cached = _QSS_CACHE.get(sheet)
    if cached is not None:
        return cached

    def _size(match):
        value, unit = float(match.group(1)), match.group(2)
        if (unit == "px" and value <= 11) or (unit == "pt" and value <= 8.5):
            value = round(value * 1.2, 1)
            text = f"{value:g}"
            return f"font-size: {text}{unit}"
        return match.group(0)

    out = _QSS_SMALL_FONT.sub(_size, _QSS_LETTER_SPACING.sub("letter-spacing: 0px", sheet))
    if _state["lang"] is not None:  # the language is known for good (profile open)
        if len(_QSS_CACHE) > 2000:
            _QSS_CACHE.clear()
        _QSS_CACHE[sheet] = out
    return out


def upper(text):
    """Upper case in the interface language (Turkish: i -> İ)."""
    if not isinstance(text, str):
        return text
    if language() == "tr":
        text = text.replace("i", "İ")
    return text.upper()


def tr_name(value):
    """A name that is not written in the call: from an N_() table, or saved in the settings.
    Translated when the catalog has it, kept as is otherwise (a name the user typed)."""
    if not isinstance(value, str) or not value:
        return value
    translated = _catalog().get(value)
    return translated if isinstance(translated, str) and translated else value


_MONTHS = (
    N_("Jan"), N_("Feb"), N_("Mar"), N_("Apr"), N_("May"), N_("Jun"),
    N_("Jul"), N_("Aug"), N_("Sep"), N_("Oct"), N_("Nov"), N_("Dec"),
)
_WEEKDAYS = (N_("Mon"), N_("Tue"), N_("Wed"), N_("Thu"), N_("Fri"), N_("Sat"), N_("Sun"))


def month_short(month):
    """Short month name, month from 1 (January) to 12."""
    return tr_name(_MONTHS[(int(month) - 1) % 12])


def weekday_short(weekday):
    """Short day name, weekday from 0 (Monday) to 6 (Sunday) like date.weekday()."""
    return tr_name(_WEEKDAYS[int(weekday) % 7])


_WEEKDAYS_LONG = (N_("Monday"), N_("Tuesday"), N_("Wednesday"), N_("Thursday"), N_("Friday"), N_("Saturday"),
                  N_("Sunday"))


def weekday_long(weekday):
    """Full day name, weekday from 0 (Monday) to 6 (Sunday) like date.weekday()."""
    return tr_name(_WEEKDAYS_LONG[int(weekday) % 7])


# Numbers. The code formats them the English way ("1,234.5", "70.54%"), like Python does,
# and num() writes them the way the language does where they are shown. The thousands
# separator is only there when the Thousands Separator setting is on, in every language.
_NBSP, _NNBSP = "\u00a0", "\u202f"
# Language code -> (decimal mark, thousands separator, percent with {} for the number).
# Languages not listed write numbers the English way.
_NUMBER_STYLE = {
    "de": (",", ".", "{}" + _NBSP + "%"),
    "es": (",", ".", "{}" + _NBSP + "%"),
    "fr": (",", _NNBSP, "{}" + _NNBSP + "%"),
    "it": (",", ".", "{}%"),
    "pl": (",", _NBSP, "{}%"),
    "pt_BR": (",", ".", "{}%"),
    "ru": (",", _NBSP, "{}" + _NBSP + "%"),
    "tr": (",", ".", "%{}"),
}
_EN_NUMBER = re.compile(r"(?<![\w.,#])(\d{1,3}(?:,\d{3})+(?![\d,])|\d+)(\.\d+)?(%?)")


def _number_style():
    return _NUMBER_STYLE.get(language())


def num(text):
    """A number (or a short text with numbers) formatted the English way, in the interface
    language: "1,234.5" -> "1 234,5", "70.54%" -> "70,54 %" in French. Times ("14:30")
    and dates are left alone. Not for HTML: style values like "0.5" would change too.
    Only once on a text: "1,234" in French is already a decimal number."""
    if not isinstance(text, str):
        text = str(text)
    style = _number_style()
    if style is None:
        return text
    decimal, thousands, percent = style

    def _one(match):
        whole, frac, sign = match.group(1), match.group(2) or "", match.group(3)
        out = whole.replace(",", thousands) + (decimal + frac[1:] if frac else "")
        return percent.format(out) if sign else out

    return _EN_NUMBER.sub(_one, text)


_DECKS_TITLE = re.compile(r"(\d+) decks")


def deck_title(title):
    """A Deep Dive / table title for display. The add-on keeps these in English because
    they also identify the row ("Total", "Collection", "Deleted Cards", "3 decks");
    a deck name is shown as is."""
    if not isinstance(title, str):
        return title
    match = _DECKS_TITLE.fullmatch(title.strip())
    if match:
        return tr_n("{n} deck", "{n} decks", int(match.group(1)))
    if title in (N_("Total"), N_("Collection"), N_("Deleted Cards")):
        return tr_name(title)
    return title


# Languages that write the day of the month without a leading zero ("3月5日").
_UNPADDED_DAY = {"ja", "ko", "zh_CN"}


def _day_text(day):
    day = int(day)
    return str(day) if language() in _UNPADDED_DAY else f"{day:02d}"


def format_date(day, time_text=None):
    """'Mar 05, 2026' (or 'Mar 05, 14:30' with time_text) in the interface language."""
    month = month_short(day.month)
    if time_text is not None:
        return tr("{month} {day}, {time}", month=month, day=_day_text(day.day), time=time_text)
    return tr("{month} {day}, {year}", month=month, day=_day_text(day.day), year=day.year)


# ---- the web pages (web_ui/web/*.js) -------------------------------------------------------------------------
# Their texts are English; the pages translate them (DD.t, and every text node of their own elements, dd-core.js
# DD.setI18n). They get the whole catalog of the language: the scripts' own texts, and the default English names
# Python sends them (stat cards, series, menus...), translated the way tr_name does: a text that is exactly an
# English entry is shown translated, a text the user wrote stays as it is.
def web_catalog():
    """{English: translation} of the current language for the web pages ({} in English)."""
    code = language()
    if code == ENGLISH:
        return {}
    out = {k: v for k, v in _catalog().items() if not k.startswith("@") and v and isinstance(v, (str, list))}
    out["@lang"] = code  # the plural rule (DD.tn) and the languages without capitals
    out["@unpadded"] = code in _UNPADDED_DAY  # dates: "Mar 5" rather than "Mar 05" (DD.localizeDates)
    return out
