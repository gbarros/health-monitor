from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MAIN_TS = ROOT / "web" / "src" / "main.ts"


class DynamicDateUiTest(unittest.TestCase):
    def test_app_uses_selected_day_instead_of_hardcoded_today(self) -> None:
        source = MAIN_TS.read_text(encoding="utf-8")

        self.assertIn("selectedDay: string;", source)
        self.assertIn("selectedDay: localDateInputValue(new Date())", source)
        self.assertNotIn('const today = "2026-07-01"', source)
        self.assertIn("state.selectedDay", source)

    def test_day_picker_refreshes_person_scoped_read_surfaces(self) -> None:
        source = MAIN_TS.read_text(encoding="utf-8")

        self.assertIn('id="selected-day"', source)
        self.assertIn("onSelectedDayChange", source)
        self.assertIn("await refreshAllReadSurfaces();", source)

    def test_summary_and_review_requests_use_selected_day_and_week_range(self) -> None:
        source = MAIN_TS.read_text(encoding="utf-8")

        self.assertIn("day=${state.selectedDay}", source)
        self.assertIn("weekRangeForDay(state.selectedDay)", source)
        self.assertIn("start=${weekRange.start}&end=${weekRange.end}", source)
        self.assertNotIn("start=2026-07-01&end=2026-07-07", source)

    def test_default_form_datetimes_use_selected_day(self) -> None:
        source = MAIN_TS.read_text(encoding="utf-8")

        self.assertIn('defaultDateTime("10:00")', source)
        self.assertIn('defaultDateTime("16:00")', source)
        self.assertIn('defaultDateTime("08:00")', source)
        self.assertIn('logged_at_local: `${state.selectedDay}T10:00:00`', source)
        self.assertIn("today: state.selectedDay", source)


if __name__ == "__main__":
    unittest.main()
