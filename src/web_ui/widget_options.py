# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
"""A widget's settings as a schema of options, with no Qt: what the web settings page (widget_settings.py) draws
for a chart or a stat card, and how each option is read from and written to the configs.

The configs are the ones the settings dialog edits (details/ui/config WidgetSettingsDialog), held by `holder`:
  - widget_def: the widget's definition (its own options: Graph Opacity, the lines, the tooltip...);
  - local_config: its own style (the same dict as widget_def for a pinned widget);
  - global_config: the shared style (the whole config, or the Deep Dive grid's compact style dict);
  - addon_config: where the style options go (local_config with "Own style" on, else global_config);
  - theme_config: the whole config (the Chart Style values a chart follows).
WidgetOptions reads them as the dialog's controls do when it opens, keeps the values the page changes, and writes
them back as its apply_live_changes does (every option at once, after each change). Save, Cancel and the live
preview stay with the caller.

What needs the add-on's other modules (Qt ones) comes in `env`:
  web_glass       the web pinned widgets' Blur and Shadow sliders shown (web_glass.web_preview_on)
  total_curve     the chart draws a running total: a Total Line of its own (chart_section.has_total_curve)
  tooltip_fields  [(id, English label)] of the chart's tooltip lines, or None
  metrics         [(stat key, label)] of the stat card's Metric menu (pinned stat cards)
  time_fields     the stat keys that are a time (a Time unit menu)
  time_units      [(value, English label)] of that menu
  default_label   fn(stat_key) -> the widget's default name, translated
  colors          True when the widget has a Colors section (drawn by the page)

The heatmap's settings are all in the shared heatmap style (Heatmap_* keys of addon_config: no "Own style"), its
tooltip lines too (Heatmap_Tooltip_Hidden). Its palette is an option of its own kind, "palette": the one chosen
and the user's saved gradients (heatmap/palettes.py), each change written at once as the dialog does.

The Range Buttons (the charts with range radio buttons) are an option of their own kind, "ranges": a list of rows
{pick, n, u} (a preset value, or "__custom__" with a number n and, for the FSRS charts, a unit u "d" / "p"). As
in the dialog, they are only written on Save (before_save): a chart rebuilt with other buttons at each change
would lose its place.
"""

from __future__ import annotations

from ..const.config import Config
from ..i18n import tr, tr_name, upper

# Types the schema draws. The other one (the text widget) keeps the Qt dialog's controls, mirrored
# (widget_settings._Mirror).
RANGE_BUTTON_TYPES = ("future_due", "stability", "review_intervals", "interval_load", "lapse_distribution",
                      "review_distribution", "learning_steps", "time_distribution", "interval_history",
                      "stability_history")
_NOT_YET = ("text_label", "unknown", "")
_CUSTOM = "__custom__"  # a Range Button's own value (range_button_row._CUSTOM)

_AUTO_BLUR = 14  # px: a saved -1 (the former "Auto") is this one (web_glass._AUTO_BLUR)
_OPACITY_DEFAULTS = {"card_counts": 100, "distribution": 100, "retention": 100}
_SHARED_PREFIXES = ("Pinned_", "Facecards_", "Heatmap_", "Dashboard_", "Text_")


def supported(wtype):
    return str(wtype or "") not in _NOT_YET


def _ranges_lib(rkind):
    """(choices [(value, English label)], the default values, normalize(values)) of a kind of Range Buttons:
    "days" (Future Due, days ahead, -1 = all) or "fsrs" (mode strings: "d200", "p85", "95_percent", "all"...)."""
    if rkind == "days":
        from ..details.widgets.common import future_due_filters as f

        return ([(d, lab) for d, lab, _s in f.FUTURE_DUE_DAY_CHOICES], f.FUTURE_DUE_DEFAULT_DAYS,
                f.normalize_future_due_days)
    from ..details.widgets.common import fsrs_filters as f

    return [(m, lab) for m, lab, _s in f.FSRS_FILTER_CHOICES], f.FSRS_FILTER_MODES, f.normalize_fsrs_filter_modes


def _ranges_nmax(rkind, unit):
    return 99 if (rkind == "fsrs" and unit == "p") else (8999 if rkind == "days" else 9999)


def _range_row(rkind, value, presets):
    """A saved value as the row the page shows: the preset, else Custom with its number (a preset keeps its number
    too, so that "Custom..." starts from it)."""
    if rkind == "days":
        n = _int(value, 30)
        return {"pick": value if value in presets else _CUSTOM, "n": n if n > 0 else 30, "u": "d"}
    from ..details.widgets.common.fsrs_filters import canonical_fsrs_mode, parse_fsrs_mode

    value = canonical_fsrs_mode(value)
    kind, n = parse_fsrs_mode(value) or ("days", 30)
    return {"pick": value if value in presets else _CUSTOM, "n": n if n > 0 else 30,
            "u": "p" if kind == "percent" else "d"}


def _share_ranges(modes):
    """The Range Buttons the distribution charts share (fsrs_filters.shared_fsrs_filter_modes): saved once the
    dialog has saved its own config (written after it, the key would be dropped). Always stored, the defaults too:
    a chart's older list of its own never shows again."""
    from aqt.qt import QTimer

    def write():
        try:
            from ..config import addon_config

            addon_config().write_config_vals({Config.SHARED_FILTER_MODES: modes})
        except Exception:
            from ..details.logic.logger import log_swallowed

            log_swallowed()

    QTimer.singleShot(0, write)


def _range_value(rkind, row):
    """A row's value, as the chart reads it."""
    if row["pick"] != _CUSTOM:
        return row["pick"]
    n = max(1, min(_ranges_nmax(rkind, row["u"]), _int(row["n"], 30)))
    return n if rkind == "days" else f"{row['u']}{n}"


def _mix_hex(a, b):
    try:
        ra, rb = int(a.lstrip("#")[:6], 16), int(b.lstrip("#")[:6], 16)
    except ValueError:
        return b
    return "#%02x%02x%02x" % tuple(((ra >> s & 255) + (rb >> s & 255)) // 2 for s in (16, 8, 0))


def _stop_label(i, n):
    """A gradient's color i of n: Low, Middle (1, 2...), High."""
    if i == 0:
        return tr("Low")
    if i == n - 1:
        return tr("High")
    return tr("Middle") if n == 3 else "%s %d" % (tr("Middle"), i)


def _opt(oid, kind, label, store, **kw):
    o = {"id": oid, "kind": kind, "label": label, "store": store}
    o.update(kw)
    return o


def _int(v, default=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        try:
            return int(float(v))
        except (TypeError, ValueError):
            return int(default)


class WidgetOptions:
    def __init__(self, holder, env=None):
        self.h = holder
        self.env = dict(env or {})
        self.type = str(getattr(holder, "type", "") or "")
        self.dashboard = bool(getattr(holder, "is_dashboard_context", False))
        self.values = {}
        self.groups = self._schema()
        self._by_id = {o["id"]: o for g in self.groups for o in g["items"]}
        self.load()

    # ---- the schema ----
    def _key(self, facecard_key, dashboard_key):
        return dashboard_key if self.dashboard else facecard_key

    def _schema(self):
        groups = [] if self.type == "heatmap" else [{"id": "own", "title": None, "items": [
            _opt("own_style", "switch", tr("Own style for this widget"), "unlink"),
        ]}]
        general = [_opt("label", "text", tr("Display Label:"), "session", ph=tr("Empty = no title"))]
        if self.type == "stat_card" and not self.dashboard:
            general.append(_opt("stat_key", "select", tr("Metric:"), "session"))
            general.append(_opt("time_unit", "select", tr("Time unit:"), "session",
                                tip=tr("Auto: minutes under 1 hour, hours above (as before).\nOr force seconds, minutes, hours or days.")))
        groups.append({"id": "general", "title": tr("General"), "items": general})
        if self.type == "stat_card":
            groups += self._stat_card_groups()
        elif self.type == "heatmap":
            groups += self._heatmap_groups()
        else:
            groups += self._chart_groups()
        return groups

    def _heatmap_groups(self):
        """The heatmap dialog's sections (heatmap_section.py), in its order. Reset to Defaults: the pinned heatmap
        takes the config's defaults (heatmap_reset.reset_heatmap_pinned), the Deep Dive one a few values of its own
        (reset_heatmap_grid), the others left as they are."""
        D, C = Config.DEFAULT_CONFIG, Config
        grid = bool(getattr(self.h, "is_grid", False))

        def sw(oid, label, key, default, pinned_reset=None, grid_reset=None, **kw):
            r = grid_reset if grid else (D.get(key, default) if pinned_reset is None else pinned_reset)
            if r is not None:
                kw["reset"] = r
            return _opt(oid, "switch", label, "conf", key=key, default=default, **kw)

        def sl(oid, label, key, default, lo, hi, suffix="", pinned_reset=None, grid_reset=None, **kw):
            r = grid_reset if grid else (D.get(key, default) if pinned_reset is None else pinned_reset)
            if r is not None:
                kw["reset"] = r
            return _opt(oid, "slider", label, "conf", key=key, default=default, min=lo, max=hi, suffix=suffix, **kw)

        legend_tip = tr("Color legend under the heatmap, with the value each color starts at.")
        if grid:
            layout = [sw("hm_hide_labels", tr("Hide Labels"), C.HEATMAP_HIDE_LABELS, False, grid_reset=True),
                      sw("hm_legend", tr("Show Legend"), C.HEATMAP_SHOW_LEGEND, True, grid_reset=True, tip=legend_tip)]
        else:
            nav = D.get(C.HEATMAP_NAV_POS, "top_right")
            layout = [
                sl("hm_scale", tr("Overall Scale"), C.HEATMAP_SCALE, 100, 50, 200, "%", pinned_reset=D.get(C.HEATMAP_SCALE, 78)),
                _opt("hm_nav", "select", tr("Navigation Position:"), "conf", key=C.HEATMAP_NAV_POS, default="top_right",
                     reset=nav, opts=[["top_right", tr("Top Right")], ["top_left", tr("Top Left")],
                                      ["bottom_right", tr("Bottom Right")], ["bottom_left", tr("Bottom Left")]]),
                sl("hm_rounding", tr("Corner Radius"), C.HEATMAP_ROUNDING, 30, 0, 100, "%"),
                sw("hm_hide_title", tr("Hide Title"), C.HEATMAP_HIDE_TITLE, True),
                sw("hm_hide_labels", tr("Hide Labels"), C.HEATMAP_HIDE_LABELS, False),
                sw("hm_legend", tr("Show Legend"), C.HEATMAP_SHOW_LEGEND, True, tip=legend_tip),
            ]
        layout += [
            sw("hm_monday", tr("Start Week on Monday"), C.HEATMAP_MONDAY_FIRST, False, grid_reset=False),
            sw("hm_future", tr("Show Future Reviews"), C.HEATMAP_SHOW_FUTURE, True, grid_reset=True),
            sw("hm_tinted", tr("Tint Future Reviews"), C.HEATMAP_TINTED_FUTURE, False, grid_reset=False),
            sw("hm_browser", tr("Click to open Browser"), C.HEATMAP_CLICK_BROWSER, True, grid_reset=True,
               tip=tr("Open the Anki Browser for cards reviewed on the clicked day.")),
        ]

        web = bool(self.env.get("web_glass"))
        blur, shadow = self._glass_sliders(C.HEATMAP_GLASS_BLUR, C.HEATMAP_GLASS_SHADOW)
        for o in blur + shadow:
            o["needs"] = None
        box = [
            sw("hm_glass", tr("Show Background Box"), C.HEATMAP_SHOW_GLASS, False, grid_reset=False),
            sl("hm_int", tr("Background Opacity") if web else tr("Intensity"), C.HEATMAP_GLASS_INTENSITY,
               D[C.HEATMAP_GLASS_INTENSITY], 0, 100, "%", grid_reset=0, needs="hm_glass"),
            *blur,
            sl("hm_border", tr("Border Opacity"), C.HEATMAP_GLASS_BORDER, 0, 0, 100, "%", grid_reset=0, needs="hm_glass"),
            *shadow,
        ]
        groups = [{"id": "box", "title": tr("Background Box Style"), "items": box}]
        # the Colors section: the heatmap's color (the page's), then its other color choices
        groups.append({"id": "colors", "title": tr("Colors"), "items": [
            sw("multi_hue", tr("Multicolor Intensity"), C.HEATMAP_MULTI_HUE_INTENSITY, False, grid_reset=False),
            _opt("palette", "palette", tr("Palette"), "palette"),
        ]})
        groups.append({"id": "layout", "title": tr("Layout && appearance").replace("&&", "&"), "items": layout})

        fields = self.env.get("tooltip_fields")
        if fields:
            groups.append({"id": "tooltip", "title": tr("Tooltip Lines"), "items": [
                _opt("tip:" + str(fid), "switch", tr_name(label), "hm_tooltip", field=str(fid),
                     **({} if grid else {"reset": str(fid) not in set(D.get(C.HEATMAP_TOOLTIP_HIDDEN) or [])}))
                for fid, label in fields
            ]})

        groups.append({"id": "intensity", "title": tr("Opacity && Intensity").replace("&&", "&"), "items": [
            sl("hm_empty", tr("Empty Opacity"), C.HEATMAP_EMPTY_OPACITY, 15, 0, 100, "%", grid_reset=50),
            sl("hm_filled", tr("Filled Opacity"), C.HEATMAP_FILLED_OPACITY, 100, 0, 100, "%", grid_reset=100),
            sl("hm_vibrance", tr("Saturation"), C.HEATMAP_VIBRANCE, 100, 50, 200, "%", grid_reset=100),
            sl("hm_curve", tr("Intensity Curve"), C.HEATMAP_INTENSITY_CURVE, 100, 50, 200, "%", grid_reset=100),
            sw("hm_invert", tr("Invert Intensity"), C.HEATMAP_INVERT_INTENSITY, False, grid_reset=False),
            sl("hm_levels", tr("Color Levels"), C.HEATMAP_COLOR_LEVELS, 20, 2, 30, grid_reset=20),
        ]})
        if not grid:
            groups.append({"id": "modes", "title": tr("Mode Visibility"), "items": [
                sw("hm_cont", tr("Show continuous mode (infinite)"), C.HEATMAP_SHOW_CONTINUOUS_MODE, True),
                sw("hm_365", tr("Show 365-day mode (365)"), C.HEATMAP_SHOW_365_MODE, True),
                sw("hm_year", tr("Show year mode (Y)"), C.HEATMAP_SHOW_YEAR_MODE, True),
                sw("hm_years", tr("Show all years mode (YRS)"), C.HEATMAP_SHOW_YEARS_MODE, True),
            ]})
        groups.append({"id": "years", "title": tr("All Years Mode"), "items": [
            sl("hm_fold", tr("Years shown before the older ones fold (0: all)"), C.HEATMAP_YEARS_FOLD, 3, 0, 20),
        ]})
        return groups

    def _glass_sliders(self, blur_key, shadow_key):
        if not self.env.get("web_glass"):
            return [], []
        blur = _opt("blur", "slider", tr("Background Blur"), "conf", key=blur_key,
                    default=Config.DEFAULT_CONFIG.get(blur_key, 0), min=0, max=40, suffix=" px",
                    tip=tr("Blur what is behind the box (frosted glass), seen over a background image. 0 px: no blur."),
                    reset=_AUTO_BLUR)
        shadow = _opt("shadow", "slider", tr("Shadow"), "conf", key=shadow_key, default=0, min=0, max=100, suffix="%",
                      tip=tr("A soft shadow under the box: it seems to float over the background."), reset=0)
        return [blur], [shadow]

    def _chart_groups(self):
        D = Config.DEFAULT_CONFIG
        web = bool(self.env.get("web_glass"))
        blur, shadow = self._glass_sliders(Config.PINNED_GLASS_BLUR, Config.PINNED_GLASS_SHADOW)
        if getattr(self.h, "is_grid", False):
            grid = D.get(Config.DEEP_DIVE_GRID_STYLE, {}) or {}
            reset_int, reset_border = grid.get(Config.PINNED_GLASS_INTENSITY, 4), grid.get(Config.PINNED_GLASS_BORDER, 50)
        else:
            reset_int, reset_border = D[Config.PINNED_GLASS_INTENSITY], D.get(Config.PINNED_GLASS_BORDER, 34)
        hover_default = bool(D.get(Config.PINNED_HOVER_BORDER, False))
        box = [
            _opt("glass", "switch", tr("Show Background Box"), "conf", key=Config.PINNED_GLASS, default=True, reset=True),
            _opt("intensity", "slider", tr("Background Opacity") if web else tr("Background Intensity"), "conf",
                 key=Config.PINNED_GLASS_INTENSITY, default=D[Config.PINNED_GLASS_INTENSITY], min=0, max=100,
                 suffix="%", reset=reset_int,
                 tip=tr("How much the box covers what is behind it: 0% see-through, 100% solid.") if web else None),
            *blur,
            _opt("border", "slider", tr("Border Opacity"), "conf", key=Config.PINNED_GLASS_BORDER, default=50,
                 min=0, max=100, suffix="%", reset=reset_border),
            *shadow,
            _opt("hover", "switch", tr("Show Hover Border"), "conf", key=Config.PINNED_HOVER_BORDER,
                 default=hover_default, reset=hover_default, tip=tr("Brighten the box border when the mouse is over it.")),
        ]
        groups = [{"id": "box", "title": tr("Background Box Settings"), "items": box}]
        if self.env.get("colors"):
            groups.append({"id": "colors", "title": tr("Colors"), "items": []})  # (the page's)

        look = [_opt("chart_opacity", "slider", tr("Graph Opacity"), "def", key="chart_opacity",
                     default=_OPACITY_DEFAULTS.get(self.type, 100), min=0, max=100, suffix="%",
                     reset=_OPACITY_DEFAULTS.get(self.type, 100))]
        if self.type == "activity":
            look += [
                _opt("show_average", "switch", tr("Show Average Line"), "def_only", key="show_average", default=True, reset=True),
                _opt("show_cumulative", "switch", tr("Show Cumulative Line"), "def_only", key="show_cumulative",
                     default=True, reset=True),
            ]
        if self.type in ("card_counts", "todays_retention"):
            look += [
                _opt("show_legend", "switch", tr("Show Legend"), "def", key="show_legend", default=True, reset=True,
                     tip=tr("The list of card types with their counts, on the right of the donut. Off keeps only the donut.")),
                _opt("legend_mode", "select", tr("Legend Layout"), "legend_mode", key="legend_mode", default="auto",
                     reset="auto", opts=[["auto", tr("Auto")], ["always", tr("Always next to the donut")],
                                         ["hover", tr("On hover")]],
                     tip=tr("Auto: the legend sits next to the donut when there is room to read it, "
                            "otherwise the donut takes the whole space and a list icon shows the legend on hover.")),
                _opt("legend_pct", "switch", tr("Show Percentages"), "def", key="legend_pct", default=False, reset=False,
                     tip=tr("Each count's share of the total, beside it in the legend.")),
            ]
        if self.type not in ("card_counts", "distribution"):
            look.append(_opt("line_opacity", "slider", tr("Total / Average Lines"), "follow", key="line_opacity",
                             conf_key=Config.CHART_LINE_OPACITY, fallback=80, min=0, max=200, suffix="%"))
            if self.env.get("total_curve"):
                look.append(_opt("total_line", "slider", tr("Total Line"), "follow_total", key="total_line",
                                 min=0, max=100, suffix="%",
                                 tip=tr("A line over the edge of the Total area. 0% = no line (Anki's look), 100% = a clear line.")))
            look.append(_opt("bar_gradient", "slider", tr("Bar Gradient"), "follow", key="bar_gradient",
                             conf_key=Config.CHART_BAR_GRADIENT, fallback=43, min=0, max=100, suffix="%"))
            look.append(_opt("show_grid", "switch", tr("Grid Lines"), "follow_flag", key="show_grid",
                             conf_key=Config.CHART_SHOW_GRID,
                             tip=tr("Horizontal guide lines behind this chart. Off keeps only the baseline.")))
        groups.append({"id": "look", "title": tr("Chart Appearance"), "items": look})

        fields = self.env.get("tooltip_fields")
        if fields:
            groups.append({"id": "tooltip", "title": tr("Tooltip Lines"), "items": [
                _opt("tip:" + str(fid), "switch", tr_name(label), "tooltip", field=str(fid), reset=True)
                for fid, label in fields
            ]})
        if self.type in RANGE_BUTTON_TYPES:
            days = self.type == "future_due"
            tip = tr("Pick different values, or Custom. They are shown in order, 'all' last.")
            if not days:
                tip += " " + tr("Shared by every chart with these buttons, in the Deep Dive and on the main screen.")
            groups.append({"id": "ranges", "title": tr("Range Buttons"),
                           "tip": tip,
                           "items": [_opt("ranges", "ranges", tr("Range Buttons"), "ranges",
                                          key="radio_ranges" if days else "filter_modes",
                                          rkind="days" if days else "fsrs")]})
        return groups

    def _stat_card_groups(self):
        D = Config.DEFAULT_CONFIG
        k = self._key

        def conf(oid, kind, label, fk, dk, default, fallback, **kw):
            key = k(fk, dk)
            return _opt(oid, kind, label, "conf", key=key, default=default, reset=D.get(key, fallback), **kw)

        layout = [
            conf("scale", "slider", tr("Visual Scale"), Config.FACECARDS_SCALE, Config.DASHBOARD_SCALE, 100, 100,
                 min=50, max=150, suffix="%"),
            conf("title_size", "slider", tr("Title Size"), Config.FACECARDS_TITLE_SIZE, Config.DASHBOARD_TITLE_SIZE,
                 100, 100, min=70, max=160, suffix="%"),
            _opt("title_color", "color", tr("Title Color"), "conf", key=k(Config.FACECARDS_TITLE_COLOR, Config.DASHBOARD_TITLE_COLOR),
                 default="", reset="", reset_tip=tr("Back to the theme color")),
            conf("hover_effect", "switch", tr("Show Hover Border"), Config.FACECARDS_HOVER_EFFECT,
                 Config.DASHBOARD_HOVER_EFFECT, True, True),
            conf("inline_stats", "switch", tr("Title + Value on same line"), Config.FACECARDS_INLINE_STATS,
                 Config.DASHBOARD_INLINE_STATS, False, False),
            _opt("show_icons", "select", tr("Icon"), "conf", key=k(Config.FACECARDS_SHOW_ICONS, Config.DASHBOARD_SHOW_ICONS),
                 default="inline",
                 reset=D.get(k(Config.FACECARDS_SHOW_ICONS, Config.DASHBOARD_SHOW_ICONS), "inline"),
                 opts=[["off", tr("Off")], ["inline", tr("Next to title")], ["watermark", tr("Watermark")]]),
            _opt("icon_pos", "select", tr("Icon Position"), "conf", key=k(Config.FACECARDS_ICON_POS, Config.DASHBOARD_ICON_POS),
                 default="tl", reset=D.get(k(Config.FACECARDS_ICON_POS, Config.DASHBOARD_ICON_POS), "tl"),
                 opts=[["tl", tr("Top Left")], ["tr", tr("Top Right")], ["bl", tr("Bottom Left")], ["br", tr("Bottom Right")]]),
        ]
        blur, shadow = ([], []) if self.dashboard else self._glass_sliders(Config.FACECARDS_GLASS_BLUR, Config.FACECARDS_GLASS_SHADOW)
        box = [
            conf("glass", "switch", tr("Show Background Box"), Config.FACECARDS_SHOW_GLASS, Config.DASHBOARD_SHOW_GLASS,
                 True, True),
            conf("intensity", "slider", tr("Intensity"), Config.FACECARDS_GLASS_INTENSITY,
                 Config.DASHBOARD_GLASS_INTENSITY, 5, 5, min=0, max=100, suffix="%", needs="glass"),
            *blur,
            conf("border", "slider", tr("Border Opacity"), Config.FACECARDS_GLASS_BORDER, Config.DASHBOARD_GLASS_BORDER,
                 50, 50, min=0, max=100, suffix="%", needs="glass"),
            *shadow,
        ]
        shadows = [
            conf("title_shadow", "slider", tr("Title Shadow"), Config.FACECARDS_TITLE_SHADOW_INTENSITY,
                 Config.DASHBOARD_TITLE_SHADOW_INTENSITY, 40, 0, min=0, max=100, suffix="%"),
            conf("stat_shadow", "slider", tr("Value Shadow"), Config.FACECARDS_STAT_SHADOW_INTENSITY,
                 Config.DASHBOARD_STAT_SHADOW_INTENSITY, 60, 0, min=0, max=100, suffix="%"),
        ]
        groups = [{"id": "box", "title": tr("Background Box Style"), "items": box}]
        if self.env.get("colors"):
            groups.append({"id": "colors", "title": tr("Colors"), "items": []})
        groups.append({"id": "layout", "title": tr("Card Layout && Size").replace("&&", "&"), "items": layout})
        groups.append({"id": "shadows", "title": tr("Text Shadows"), "items": shadows})
        return groups

    # ---- reading ----
    def _globals(self, o):
        """(shown when the widget has none of its own, compared with to keep none) of a Chart Style option."""
        conf = self.h.addon_config
        if o["store"] == "follow":
            top = getattr(self.h, "theme_config", None)
            fallback = top.get(o["conf_key"], o["fallback"]) if isinstance(top, dict) else o["fallback"]
            return _int(conf.get(o["conf_key"], fallback), o["fallback"]), _int(conf.get(o["conf_key"], 100), 100)
        if o["store"] == "follow_flag":
            v = bool(conf.get(o["conf_key"], True))
            return v, v
        v = self.total_line_global()
        return v, v

    def total_line_global(self):
        for conf in (getattr(self.h, "addon_config", None), getattr(self.h, "theme_config", None)):
            v = conf.get(Config.CHART_TOTAL_LINE) if isinstance(conf, dict) else None
            if v is not None:
                try:
                    return int(v)
                except (TypeError, ValueError):
                    pass
        return 0

    def _read(self, o):
        st = o["store"]
        wd = self.h.widget_def
        if st == "unlink":
            return bool(self.h.is_unlinked)
        if st == "conf":
            v = self.h.addon_config.get(o["key"], o.get("default"))
            if o["id"] == "blur":
                v = 0 if v is None else _int(v)
                return _AUTO_BLUR if v < 0 else v
            if o["id"] == "show_icons":
                return "off" if v in (False, "", "off", None) else ("watermark" if v == "watermark" else "inline")
            if o["id"] == "icon_pos":
                return v if v in ("tl", "tr", "bl", "br") else "tl"
            if o["kind"] == "color":
                return str(v or "")
        elif st in ("def", "def_only", "legend_mode"):
            v = wd.get(o["key"], o.get("default"))
        elif st in ("follow", "follow_total", "follow_flag"):
            v = wd.get(o["key"], self._globals(o)[0])
        elif st == "tooltip":
            return o["field"] not in set(wd.get("tooltip_hidden") or [])
        elif st == "hm_tooltip":
            return o["field"] not in set(self.h.addon_config.get(Config.HEATMAP_TOOLTIP_HIDDEN) or [])
        elif st == "palette":
            from ..details.widgets.charts.heatmap.palettes import customs_of, palette_of

            conf = self.h.addon_config
            customs = customs_of(conf.get)
            return {"key": palette_of(conf.get, customs), "customs": customs}
        elif st == "session":
            return self._read_session(o["id"])
        elif st == "ranges":
            choices, _default, normalize = _ranges_lib(o["rkind"])
            presets = [v for v, _l in choices]
            cur = wd.get(o["key"])
            if o["rkind"] == "fsrs":  # the list the charts share
                from ..details.widgets.common.fsrs_filters import shared_fsrs_filter_modes

                cur = shared_fsrs_filter_modes() or cur
            return [_range_row(o["rkind"], v, presets) for v in normalize(cur)]
        else:
            v = None
        return self._cast(o, v)

    def _read_session(self, oid):
        wd = self.h.widget_def
        if oid == "label":
            return tr_name(wd.get("label", ""))
        if oid == "stat_key":
            keys = [m for m, _l in self.env.get("metrics") or ()]
            cur = wd.get("stat_key")
            return cur if cur in keys else (keys[0] if keys else cur)
        if oid == "time_unit":
            units = [u for u, _l in self.env.get("time_units") or ()]
            cur = wd.get("time_unit", "auto")
            return cur if cur in units else (units[0] if units else "auto")
        return None

    @staticmethod
    def _cast(o, v):
        if o["kind"] == "switch":
            return bool(v)
        if o["kind"] == "slider":
            return max(o["min"], min(o["max"], _int(v, o.get("default", o["min"]) or 0)))
        return v

    def load(self, session_too=True):
        """The values as the dialog's controls show them (refresh_ui_values)."""
        for o in self._by_id.values():
            if o["store"] == "session" and not session_too:
                continue
            self.values[o["id"]] = self._read(o)

    # ---- writing ----
    def set(self, oid, value):
        o = self._by_id.get(oid)
        if o is None:
            return False
        if o["store"] == "unlink":
            self.set_unlinked(bool(value))
            return True
        if o["store"] == "palette":
            if not self._palette_set(value):
                return False
            self.apply()
            return True
        if o["store"] == "ranges":
            rows = self._ranges_in(o, value)
            if rows is None:
                return False
            self.values[oid] = rows  # (written on Save)
            return True
        if o["kind"] == "select" and o.get("opts") is not None:
            if value not in [v for v, _l in o["opts"]]:
                return False
        self.values[oid] = self._cast(o, value) if o["kind"] in ("switch", "slider") else value
        if o["store"] != "session" or (oid == "label" and self.dashboard):
            self.apply()
        return True

    # ---- the heatmap's palette ----
    def _palette(self):
        return self.values.get("palette") or {"key": "", "customs": []}

    def _palette_current(self):
        from ..details.widgets.charts.heatmap.palettes import CUSTOM

        p = self._palette()
        return next((g for g in p["customs"] if CUSTOM + g["id"] == p["key"]), None)

    def _palette_set(self, value):
        """{"pick": a palette's key} or {"name": the chosen gradient's new name}."""
        from ..details.widgets.charts.heatmap.palettes import CUSTOM, KEYS

        if not isinstance(value, dict):
            return False
        p = self._palette()
        if "pick" in value:
            key = str(value.get("pick") or "")
            if key not in KEYS and not any(CUSTOM + g["id"] == key for g in p["customs"]):
                return False
            p["key"] = key
            return True
        if "name" in value:
            g, name = self._palette_current(), str(value.get("name") or "").strip()
            if g is None or not name:
                return False
            g["name"] = name
            return True
        return False

    def palette_new(self, base_color=None, dark=False):
        """A new gradient of the user's, from the palette shown, chosen at once (the dialog's New gradient)."""
        from ..details.widgets.charts.heatmap.palettes import CUSTOM, new_id, seed_colors

        p = self._palette()
        pid = new_id(p["customs"])
        p["customs"].append({"id": pid, "name": tr("Gradient {number}", number=pid),
                             "colors": seed_colors(p["key"], p["customs"], base_color, dark=dark)})
        p["key"] = CUSTOM + pid
        self.apply()

    def palette_delete(self):
        g = self._palette_current()
        if g is None:
            return
        p = self._palette()
        p["customs"] = [x for x in p["customs"] if x is not g]
        p["key"] = ""
        self.apply()

    def palette_stops(self, more):
        """A color more (between the last two: the highest stays the highest) or less (the last before it)."""
        from ..details.widgets.charts.heatmap.palettes import MAX_COLORS, MIN_COLORS

        g = self._palette_current()
        if g is None:
            return
        cols = g["colors"]
        if more and len(cols) < MAX_COLORS:
            cols.insert(len(cols) - 1, _mix_hex(cols[-2], cols[-1]))
        elif not more and len(cols) > MIN_COLORS:
            cols.pop(len(cols) - 2)
        self.apply()

    def palette_color(self, i, color):
        g = self._palette_current()
        if g is not None and 0 <= int(i) < len(g["colors"]) and color:
            g["colors"][int(i)] = str(color)
            self.apply()

    def palette_colors(self):
        g = self._palette_current()
        return list(g["colors"]) if g else []

    def _palette_state(self):
        from ..details.widgets.charts.heatmap.palettes import CUSTOM, MAX_COLORS, MIN_COLORS, PALETTES

        p, g = self._palette(), self._palette_current()
        out = {"v": p["key"],
               "opts": [[k, tr_name(lab)] for k, lab in PALETTES] + [[CUSTOM + c["id"], c["name"]] for c in p["customs"]],
               "new": tr("New gradient"),
               "new_tip": tr("A new gradient of your own, saved with the others (starts from the one shown)"),
               "grad": None}
        if g is not None:
            n = len(g["colors"])
            out["grad"] = {
                "name": g["name"], "name_label": tr("Name"), "del": tr("Delete"),
                "colors": [{"label": _stop_label(i, n), "color": c} for i, c in enumerate(g["colors"])],
                "add": n < MAX_COLORS, "rem": n > MIN_COLORS, "add_tip": tr("Add color"), "rem_tip": tr("Remove color"),
                "strip_tip": tr("Low") + " \u2192 " + tr("High"),
            }
        return out

    @staticmethod
    def _ranges_in(o, value):
        """The page's rows, checked: 2 to 8 of them, a known preset or Custom, a number in range."""
        from ..details.widgets.common.future_due_filters import MAX_BUTTONS, MIN_BUTTONS

        if not isinstance(value, (list, tuple)) or not MIN_BUTTONS <= len(value) <= MAX_BUTTONS:
            return None
        presets = [v for v, _l in _ranges_lib(o["rkind"])[0]]
        rows = []
        for r in value:
            if not isinstance(r, dict):
                return None
            pick = next((p for p in presets if str(p) == str(r.get("pick"))), _CUSTOM)
            unit = "p" if (o["rkind"] == "fsrs" and r.get("u") == "p") else "d"
            n = max(1, min(_ranges_nmax(o["rkind"], unit), _int(r.get("n"), 30)))
            rows.append({"pick": pick, "n": n, "u": unit})
        return rows

    def _save_ranges(self):
        """The Range Buttons into the widget (the dialog's Save): a value picked twice kept once; fewer than 2
        buttons, or the defaults, store nothing (the chart shows the defaults)."""
        wd, local = self.h.widget_def, self.h.local_config
        both = (wd,) if local is wd else (wd, local)
        for o in self._by_id.values():
            if o["store"] != "ranges":
                continue
            _choices, default, normalize = _ranges_lib(o["rkind"])
            vals = [_range_value(o["rkind"], r) for r in self.values.get(o["id"]) or ()]
            if o["rkind"] == "fsrs":
                from ..details.widgets.common.fsrs_filters import canonical_fsrs_mode

                vals = [canonical_fsrs_mode(v) for v in vals]
            vals = list(dict.fromkeys(vals))
            norm = normalize(vals)
            if o["rkind"] == "fsrs":
                _share_ranges(list(norm))
            for d in both:
                if len(vals) < 2 or tuple(norm) == tuple(default):
                    d.pop(o["key"], None)
                else:
                    d[o["key"]] = list(norm)

    def set_unlinked(self, on):
        """Own style on / off (the dialog's toggle_unlink): the style options read from the other config."""
        h = self.h
        h.is_unlinked = bool(on)
        if h.is_unlinked:
            h.addon_config = h.local_config
            for key, v in h.global_config.items():
                if key not in h.local_config and isinstance(key, str) and key.startswith(_SHARED_PREFIXES):
                    h.local_config[key] = v
        else:
            h.addon_config = h.global_config
        self.load(session_too=False)
        self.apply()

    def apply(self):
        """Every option into the configs (the dialog's apply_live_changes)."""
        h, conf, wd, local = self.h, self.h.addon_config, self.h.widget_def, self.h.local_config
        both = (wd,) if local is wd else (wd, local)
        hidden = []
        for o in self._by_id.values():
            st, v = o["store"], self.values.get(o["id"])
            if st == "conf":
                conf[o["key"]] = v
            elif st == "def_only":
                wd[o["key"]] = v
            elif st == "def":
                for d in both:
                    d[o["key"]] = v
            elif st == "legend_mode":
                for d in both:
                    if v == "auto":
                        d.pop(o["key"], None)
                    else:
                        d[o["key"]] = v
            elif st in ("follow", "follow_total", "follow_flag"):
                same = v == self._globals(o)[1]
                for d in both:
                    if same:
                        d.pop(o["key"], None)
                    else:
                        d[o["key"]] = v
            elif st == "tooltip" and not v:
                hidden.append(o["field"])
            elif st == "palette" and isinstance(v, dict):
                conf[Config.HEATMAP_PALETTE] = v["key"] or ""
                conf[Config.HEATMAP_CUSTOM_PALETTES] = [dict(g, colors=list(g["colors"])) for g in v["customs"]]
        if any(o["store"] == "hm_tooltip" for o in self._by_id.values()):
            conf[Config.HEATMAP_TOOLTIP_HIDDEN] = [o["field"] for o in self._by_id.values()
                                                   if o["store"] == "hm_tooltip" and not self.values.get(o["id"])]
        if any(o["store"] == "tooltip" for o in self._by_id.values()):
            for d in both:
                if hidden:
                    d["tooltip_hidden"] = list(hidden)
                else:
                    d.pop("tooltip_hidden", None)
        if self.type == "stat_card":
            if self.dashboard:
                # the card's own name in the Deep Dive: kept in the config's labels map (live, as the dialog does)
                labels_conf = h.global_config if isinstance(h.global_config, dict) else conf
                labels = labels_conf.get(Config.DASH_STAT_LABELS, {})
                if not isinstance(labels, dict):
                    labels = {}
                stat_key = wd.get("stat_key")
                if stat_key:
                    text = str(self.values.get("label") or "").strip()
                    if text and text != self.default_label().strip():
                        labels[str(stat_key)] = text
                    else:
                        labels.pop(str(stat_key), None)
                    labels_conf[Config.DASH_STAT_LABELS] = labels
            else:
                for d in both:
                    d["label"] = self.label_to_save()
                    if "stat_key" in self.values:
                        d["stat_key"] = self.values["stat_key"]
                    if "time_unit" in self.values:
                        d["time_unit"] = self.values["time_unit"]

    def reset(self):
        """Reset to Defaults: the style and the chart's options (not its name)."""
        for o in self._by_id.values():
            st = o["store"]
            if "reset" in o:
                self.values[o["id"]] = o["reset"]
            elif st == "follow":
                self.values[o["id"]] = _int(self.h.addon_config.get(o["conf_key"], o["fallback"]), o["fallback"])
            elif st in ("follow_total", "follow_flag"):
                self.values[o["id"]] = self._globals(o)[0]
            elif st == "palette":
                self._palette()["key"] = ""  # back to the chosen color; the saved gradients stay
            elif st == "ranges":
                choices, default, _n = _ranges_lib(o["rkind"])
                presets = [v for v, _l in choices]
                self.values[o["id"]] = [_range_row(o["rkind"], v, presets) for v in default]
        self.apply()

    def reset_label(self):
        self.values["label"] = self.default_label()
        self.apply()

    def default_label(self):
        fn = self.env.get("default_label")
        key = self.values.get("stat_key", self.h.widget_def.get("stat_key"))
        try:
            return str(fn(key)) if fn else ""
        except Exception:
            return ""

    def label_to_save(self):
        """Unchanged shown text keeps the saved value (an English default name stays English), else the text."""
        text = str(self.values.get("label") or "")
        saved = self.h.widget_def.get("label", "")
        if isinstance(saved, str) and text == tr_name(saved):
            return saved
        return text

    def before_save(self):
        """What the dialog's save_and_close puts in local_config before it saves (persist_widget_settings)."""
        h = self.h
        h.local_config["use_custom_style"] = bool(h.is_unlinked)
        h.local_config["label"] = self.label_to_save()
        if "stat_key" in self.values:
            h.local_config["stat_key"] = self.values["stat_key"]
        if "time_unit" in self.values:
            h.local_config["time_unit"] = self.values["time_unit"]
        for key in self.env.get("behavior_keys") or ():
            if key in h.widget_def:
                h.local_config[key] = h.widget_def[key]
        self._save_ranges()
        self.apply()

    # ---- the page's state ----
    def _shown(self, o):
        if o["id"] == "time_unit":
            return self.values.get("stat_key") in set(self.env.get("time_fields") or ())
        return True

    def _enabled(self, o):
        if o["id"] == "legend_mode":
            return bool(self.values.get("show_legend", True))
        if o["id"] == "multi_hue":
            return not self._palette()["key"]  # (it only changes the chosen color's shades)
        if o["id"] == "icon_pos":
            return self.values.get("show_icons") == "watermark"
        need = o.get("needs")
        return bool(self.values.get(need, True)) if need else True

    def _choices(self, o):
        if o["id"] == "stat_key":
            return [[m, str(lab)] for m, lab in self.env.get("metrics") or ()]
        if o["id"] == "time_unit":
            return [[u, tr_name(lab)] for u, lab in self.env.get("time_units") or ()]
        return o.get("opts") or []

    def state(self, color_of=None):
        """The groups as the page draws them. color_of(option) -> (shown hex, is default) for a color option."""
        out = []
        for g in self.groups:
            items = []
            for o in g["items"]:
                if not self._shown(o):
                    continue
                n = {"key": o["id"], "kind": o["kind"], "label": o["label"], "tip": o.get("tip") or "",
                     "v": self.values.get(o["id"]), "en": self._enabled(o)}
                if o["kind"] == "slider":
                    n.update(min=o["min"], max=o["max"], step=1, suffix=o.get("suffix", ""))
                elif o["kind"] == "select":
                    n["opts"] = self._choices(o)
                elif o["kind"] == "text":
                    n["ph"] = o.get("ph", "")
                    if o["id"] == "label":
                        cur = upper(str(n["v"] or "").strip())
                        n["reset"] = bool(cur) and cur != upper(self.default_label())
                        n["reset_tip"] = tr("Reset to Default")
                elif o["kind"] == "color":
                    hex_, is_default = color_of(o) if color_of else (n["v"] or "#888888", not n["v"])
                    n.update(color=hex_, reset=not is_default, reset_tip=o.get("reset_tip", ""))
                elif o["kind"] == "ranges":
                    n.update(self._ranges_state(o))
                elif o["kind"] == "palette":
                    n.update(self._palette_state())
                items.append(n)
                if o["id"] == "own_style":
                    items.append({"key": "own_style_hint", "kind": "note", "text": self.unlink_hint()})
            out.append({"id": g["id"], "title": g["title"], "tip": g.get("tip") or "", "items": items})
        return out

    @staticmethod
    def _ranges_state(o):
        from ..details.widgets.common.future_due_filters import MAX_BUTTONS, MIN_BUTTONS

        rk = o["rkind"]
        choices = _ranges_lib(rk)[0]
        return {
            "rkind": rk, "min": MIN_BUTTONS, "max": MAX_BUTTONS,
            "opts": [[v, tr_name(lab)] for v, lab in choices] + [[_CUSTOM, tr("Custom...")]],
            "units": [["d", tr("days")], ["p", "%"]], "day_unit": tr("day(s)"),
            "nmax": {"d": _ranges_nmax(rk, "d"), "p": _ranges_nmax(rk, "p")},
            "btn": [tr("Button {number}:", number=i + 1) for i in range(MAX_BUTTONS)],
            "add": tr("+ Add Button"), "remove": tr("Remove this button"),
        }

    def unlink_hint(self):
        if self.h.is_unlinked:
            return tr("This widget has its own style: the changes below only apply to it.")
        return tr("The style below (box, border, opacity) is shared by all widgets: a change here "
                  "applies to all of them. The title and the options of this widget stay its own.")
