# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from ...ui import Config
from ....i18n import num, tr, tr_n

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
        from ....config import read_config_value
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


def fmt_num_compact(val, prec=1):
    """
    Format a number without useless trailing .0 for integral floats.
    Examples: 243.0 -> "243", 48.6 -> "48.6"
    """
    if not isinstance(val, (int, float)):
        return str(val)
    try:
        f = float(val)
        i = int(round(f))
        # Many chart tick values come from float math and can land on values like
        # 0.999999999 / 1.000000001; treat these as integral to avoid "1.0" noise.
        if abs(f - i) < 1e-6:
            return fmt_num(i)
        return fmt_num(f, prec)
    except Exception:
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


def format_metric_value(value, value_mode="reviews", with_unit=True, per_day=False, axis=False, compact=True):
    """Format chart metric values in reviews/time mode with shared rules."""
    mode = str(value_mode or "reviews").strip().lower()
    v = float(value or 0.0)
    if mode != "time":
        as_int = int(round(v))
        is_integral = abs(v - as_int) < 1e-9
        num = fmt_num(as_int) if is_integral else fmt_num(v)
        if axis or (not with_unit):
            out = num
        else:
            out = tr_n("{count} review", "{count} reviews", as_int if is_integral else v, count=num)
        if per_day and not axis:
            out = tr("{value}/day", value=out)
        return out

    if axis:
        if v <= 0.0:
            return "0"
        if v < 1.0:
            # Under a minute, seconds: at one decimal of a minute the ticks of a short
            # session all read "0.1m" or "0m".
            secs = v * 60.0
            return tr("{value}s", value=fmt_num_trim_zeros(secs, 0 if secs >= 10 else 1))
        if v < 60.0:
            return tr("{value}m", value=fmt_num_trim_zeros(v, 1))
        h = v / 60.0
        return tr("{value}h", value=fmt_num_trim_zeros(h, 1 if h < 10 else 0))

    if v <= 0.0:
        out = tr("{value} min", value=0) if with_unit else "0"
    elif v < 60.0:
        out = tr("{value} min", value=fmt_num_trim_zeros(v, 1)) if with_unit else fmt_num_trim_zeros(v, 1)
    else:
        h = v / 60.0
        h_text = fmt_num_trim_zeros(h, (1 if h < 10 else 0) if compact else 2)
        out = tr("{value} h", value=h_text) if with_unit else h_text
    if per_day:
        out = tr("{value}/day", value=out)
    return out


def format_metric_axis_value_for_mode(mode, value):
    """Format axis labels for a specific metric mode."""
    return format_metric_value(value, value_mode=mode, with_unit=False, axis=True)


# Trend arrows (up/down %, or points for retention) always use one decimal, whatever
# the Decimal Precision setting is.
TREND_PRECISION = 1


def stats_precision(default=2):
    """Decimal places for stats numbers (the Decimal Precision setting), kept in 0..4."""
    try:
        from ....config import read_config_value
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

