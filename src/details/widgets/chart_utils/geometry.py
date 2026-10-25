# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Deep Dive Stats contributors
from aqt.qt import QFontMetrics

class ChartGeometry:
    MARGIN_LEFT = 35
    MARGIN_TOP = 10
    MARGIN_BOTTOM = 30
    DEFAULT_MARGIN_RIGHT = 20

    STATS_EXTRA_HEIGHT = {
        "future_due": 90,
        "review_intervals": 70,
        "stability": 70,
        "difficulty": 70,
        "retrievability": 90,
        "activity": 70,
        "retention": 70,
        "added": 70,
        "hourly": 50,
        "card_counts": 0, # Pie charts don't have bottom stats
        "heatmap": 0
    }

    @staticmethod
    def wrap_stats_text(stats, plot_w, font_metrics):
        """
        Takes a list of stat strings and intelligently wraps them into multiple lines
        based on available plot_w using the provided font_metrics.
        Returns a list of strings (each representing a line).
        """
        if not stats:
            return []

        joined_text = " · ".join(stats)
        if font_metrics.horizontalAdvance(joined_text) <= plot_w:
            return [joined_text]

        lines = []
        current_line = []

        for stat in stats:
            test_line = current_line + [stat]
            test_text = " · ".join(test_line)
            if font_metrics.horizontalAdvance(test_text) <= plot_w:
                current_line.append(stat)
            else:
                if current_line:
                    lines.append(" · ".join(current_line))
                    current_line = [stat]
                else:
                    lines.append(stat)
                    current_line = []

        if current_line:
            lines.append(" · ".join(current_line))

        return lines

    @staticmethod
    def calculate_stats_margin(stats, plot_w, font_metrics):
        """Calculate required bottom margin for stats based on wrapping."""
        if not stats:
            return ChartGeometry.MARGIN_BOTTOM

        from aqt.qt import QFontMetrics, QApplication
        font = QApplication.font()
        font.setPixelSize(13)
        actual_fm = QFontMetrics(font)

        wrapped_lines = ChartGeometry.wrap_stats_text(stats, plot_w, actual_fm)
        line_count = len(wrapped_lines)

        # Base MARGIN_BOTTOM (30) + line height (18 per line) + padding
        # 1 line -> ~63px, 2 lines -> ~81px, 3 lines -> ~99px
        return ChartGeometry.MARGIN_BOTTOM + (line_count * 18) + 15

    @staticmethod
    def calculate_dynamic_right_margin(
        font_metrics: QFontMetrics,
        values,
        is_cumulative=False,
        value_formatter=None,
        grid_lines=4,
    ):
        if not is_cumulative:
            return ChartGeometry.DEFAULT_MARGIN_RIGHT

        max_val = 0
        run_sum = 0
        for v in values:
            if isinstance(v, (int, float)):
                run_sum += v
            elif isinstance(v, (list, tuple)) and len(v) >= 2:
                run_sum += v[1]
            if run_sum > max_val: max_val = run_sum

        # Reserve space from actual axis tick labels, not only from raw integer max,
        # so formatted time labels (e.g. "5.3m", "12h") never get clipped.
        labels = []
        safe_lines = max(1, int(grid_lines or 4))
        for i in range(safe_lines + 1):
            val = float(max_val) * (i / safe_lines)
            if callable(value_formatter):
                labels.append(str(value_formatter(val)))
            else:
                labels.append(f"{int(val):,}")

        max_text_w = max((font_metrics.horizontalAdvance(lbl) for lbl in labels), default=0)
        # Keep labels readable but reduce the visual gap between plot and right-axis totals.
        return max(ChartGeometry.DEFAULT_MARGIN_RIGHT, int(max_text_w) + 10)

    @staticmethod
    def calculate_dynamic_left_margin(font_metrics: QFontMetrics, max_val, min_val=0, value_formatter=None, grid_lines=4):
        """Calculate left margin based on the widest Y-axis label that will actually be drawn."""
        if callable(value_formatter):
            safe_lines = max(1, int(grid_lines or 4))
            labels = [str(value_formatter(min_val + (max_val - min_val) * (i / safe_lines))) for i in range(safe_lines + 1)]
        else:
            labels = [f"{int(max_val)}" if max_val >= 10 else f"{max_val:.1f}"]
            if min_val > 0:
                labels.append(f"{int(min_val)}" if min_val >= 10 else f"{min_val:.1f}")
        width = max((font_metrics.horizontalAdvance(lbl) for lbl in labels), default=0)
        return max(ChartGeometry.MARGIN_LEFT, width + 12)
