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
        self.assertIn("days: 30", week_card)
        self.assertIn("CalorieTrendLine", week_card)
        self.assertIn("MacroSplit", week_card)
        self.assertIn("RollingStatTile", week_card)
        self.assertIn(".page-grid", styles)
        self.assertIn(".week-card", styles)
        self.assertIn(".macro-split", styles)
        self.assertIn(".calorie-trend", styles)
        self.assertNotIn("renderMacroChart", app)
        self.assertNotIn("renderWeightTrendChart", app)

    def test_data_page_includes_weight_rows_for_range_export(self) -> None:
        app = read_web_file("App.tsx")

        self.assertIn("loadWeightTrend", app)
        self.assertIn("updateWeightEntry", app)
        self.assertIn('title="Pesos"', app)
        self.assertIn("weightEntryRow", app)
        self.assertIn("WeightInlineEditor", app)
        self.assertIn("queryKeys.weightTrend(personId)", app)

    def test_data_page_includes_food_version_rows_for_export(self) -> None:
        app = read_web_file("App.tsx")

        self.assertIn("loadFoods", app)
        self.assertIn('title="Alimentos e versões"', app)
        self.assertIn("foodVersionRow", app)
        self.assertIn("queryKeys.foods(householdId, personId)", app)

    def test_data_page_diary_rows_are_editable_and_deletable(self) -> None:
        app = read_web_file("App.tsx")

        self.assertIn("deleteDiaryEntry", app)
        self.assertIn("updateDiaryEntry", app)
        self.assertIn("DiaryEntryInlineEditor", app)
        self.assertIn('"Ações"', app)
        self.assertIn("onEntryDeleted(entry.id)", app)
        self.assertIn("onDataChanged={invalidateDailyReadModels}", app)


if __name__ == "__main__":
    unittest.main()
