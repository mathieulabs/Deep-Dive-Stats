# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from ...const import Config
from ...i18n import num

def fmt_num(val, prec=None):
    """
    Formats a number with a thousands separator based on user preference, the way the
    interface language writes it ("1,234.5" in English, "1 234,5" in French).
    """
    return num(_fmt_num_en(val, prec))


def _fmt_num_en(val, prec=None):
    """fmt_num() the English way, before num()."""
    if not isinstance(val, (int, float)):
        return str(val)

    try:
        from ...config import read_config_value
        use_sep = read_config_value(Config.USE_THOUSANDS_SEPARATOR, True)
    except Exception:
        use_sep = True

    if use_sep:
        if isinstance(val, int):
            return f"{val:,}"
        else:
            if prec is None:
                i = int(round(float(val)))
                if abs(float(val) - i) < 1e-6:
                    return f"{i:,}"
                return f"{val:,.1f}"
            return f"{val:,.{prec}f}"

    if isinstance(val, float):
        if prec is None:
            i = int(round(float(val)))
            if abs(float(val) - i) < 1e-6:
                return str(i)
            p = 1
        else:
            p = prec
        return f"{val:.{p}f}"

    return str(val)


def fmt_num_trim_zeros(val, prec=1):
    """
    Format a number at the given precision, then trim useless trailing zeros.
    Examples (prec=1): 17.0 -> "17", 17.1 -> "17.1", 1,234.0 -> "1,234"
    """
    s = str(_fmt_num_en(val, prec))
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return num(s)


# Trend arrows (up/down %, or points for retention) always use one decimal, whatever
# the Decimal Precision setting is.
TREND_PRECISION = 1


def stats_precision(default=2):
    """Decimal places for stats numbers (the Decimal Precision setting), kept in 0..4."""
    try:
        from ...config import read_config_value
        return max(0, min(4, int(read_config_value(Config.STATS_PRECISION, default))))
    except Exception:
        return default


def fmt_percent_or_na(numer, denom, prec=None):
    """Format percentage from numerator/denominator or return N/A when denominator is empty."""
    if prec is None:
        prec = stats_precision()
    try:
        d = float(denom or 0)
    except Exception:
        d = 0.0
    if d <= 0.0:
        return "N/A"
    try:
        n = float(numer or 0)
    except Exception:
        n = 0.0
    return num(f"{(n / d) * 100:.{int(prec)}f}%")

