from __future__ import annotations

import unittest

from tests.unit.frontend_helpers import read_web_file


class ReviewChartUiTest(unittest.TestCase):
    def test_desktop_phase_five_uses_real_week_summary_card_without_fake_chart_data(self) -> None:
        app = read_web_file("App.tsx")
        week_card = read_web_file("components/WeekCard.tsx")
        styles = read_web_file("styles.css")

        self.assertIn('activeView === "panel"', app)
        self.assertIn("page-grid", app)
        self.assertIn("<WeekCard", app)
        self.assertIn("loadWeekSummary", week_card)
        self.assertIn("/api/summaries/week", read_web_file("api.ts"))
        self.assertIn(".page-grid", styles)
        self.assertIn(".week-card", styles)
        self.assertNotIn("renderMacroChart", app)
        self.assertNotIn("renderWeightTrendChart", app)


if __name__ == "__main__":
    unittest.main()
