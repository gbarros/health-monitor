from __future__ import annotations

import unittest

from tests.unit.frontend_helpers import read_web_file


class ReviewChartUiTest(unittest.TestCase):
    def test_desktop_phase_five_uses_real_week_summary_card_without_fake_chart_data(self) -> None:
        app = read_web_file("App.tsx")
        week_card = read_web_file("components/WeekCard.tsx")
        styles = read_web_file("styles.css")

        self.assertIn('pathname === "/panel"', app)
        self.assertIn("NavLink", app)
        self.assertIn("page-grid", app)
        self.assertIn("<WeekCard", app)
        self.assertIn("loadWeekSummary", week_card)
        self.assertIn("/api/summaries/week", read_web_file("api.ts"))
        self.assertIn(".page-grid", styles)
        self.assertIn(".week-card", styles)
        self.assertNotIn("renderMacroChart", app)
        self.assertNotIn("renderWeightTrendChart", app)

    def test_data_page_includes_weight_rows_for_range_export(self) -> None:
        app = read_web_file("App.tsx")

        self.assertIn("loadWeightTrend", app)
        self.assertIn('title="Pesos"', app)
        self.assertIn("weightEntryRow", app)
        self.assertIn("queryKeys.weightTrend(personId)", app)


if __name__ == "__main__":
    unittest.main()
