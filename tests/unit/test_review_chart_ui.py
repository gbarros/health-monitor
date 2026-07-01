from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "web"


class ReviewChartUiTest(unittest.TestCase):
    def test_review_surface_renders_macro_and_weight_charts(self) -> None:
        source = (WEB / "src" / "main.ts").read_text(encoding="utf-8")

        self.assertIn("function renderMacroChart", source)
        self.assertIn("function renderWeightTrendChart", source)
        self.assertIn('aria-label="Daily calories compared with calorie target"', source)
        self.assertIn('aria-label="Weight entries over time"', source)
        self.assertIn("week.daily_targets", source)
        self.assertIn("trend.entries", source)

    def test_chart_styles_are_responsive_and_not_color_only(self) -> None:
        styles = (WEB / "src" / "styles.css").read_text(encoding="utf-8")

        self.assertIn(".chart-grid", styles)
        self.assertIn(".chart-legend", styles)
        self.assertIn(".legend-box.actual", styles)
        self.assertIn(".legend-line", styles)
        self.assertIn(".weight-chart polyline", styles)
        self.assertIn(".chart-grid,", styles)


if __name__ == "__main__":
    unittest.main()
