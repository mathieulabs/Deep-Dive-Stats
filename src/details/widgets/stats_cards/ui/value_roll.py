# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
import re

from .....i18n import english_number, tr, tr_name


def parse_roll_value(text):
    if not isinstance(text, str):
        return None
    raw = english_number(text.strip())
    if not raw or raw in ("N/A", "...", tr("N/A")):
        return None

    m_pct = re.match(r"^([+-]?\d[\d,]*)(?:\.(\d+))?%$", raw)
    if m_pct:
        int_part, dec_part = m_pct.groups()
        val = float((int_part.replace(",", "")) + (("." + dec_part) if dec_part else ""))
        return ("percent", val, len(dec_part or ""), "", "%")

    m_num = re.match(r"^([^0-9+\-]*)([+-]?)(\d[\d,]*)(?:\.(\d+))?([^0-9]*)$", raw)
    if m_num:
        prefix, sign, int_part, dec_part, suffix = m_num.groups()
        val = float((sign or "") + int_part.replace(",", "") + (("." + dec_part) if dec_part else ""))
        return ("number", val, len(dec_part or ""), prefix or "", suffix or "")
    return None


def is_na_like(text):
    if not isinstance(text, str):
        return False
    return text.strip().lower() in {"n/a", "na", "...", "", tr("N/A").lower()}


def time_unit_kind(suffix):
    s = (suffix or "").strip().lower().replace(".", "")
    if s in {"h", "hr", "hrs", "hour", "hours"} or s == tr_name("h").lower().replace(".", ""):
        return "hour"
    if s in {"m", "min", "mins", "minute", "minutes"} or s == tr_name("min").lower().replace(".", ""):
        return "minute"
    return None


def convert_time_value(value, from_kind, to_kind):
    if from_kind == to_kind:
        return value
    if from_kind == "hour" and to_kind == "minute":
        return value * 60.0
    if from_kind == "minute" and to_kind == "hour":
        return value / 60.0
    return value
