from __future__ import annotations

import unittest

from tests.unit.frontend_helpers import read_web_file


class DynamicDateUiTest(unittest.TestCase):
    def test_app_uses_person_timezone_day_for_read_surfaces_and_chat(self) -> None:
        app = read_web_file("App.tsx")
        api = read_web_file("api.ts")
        day_card = read_web_file("components/DayCard.tsx")

        self.assertIn("todayIsoForTimezone(activePerson?.timezone)", app)
        self.assertIn("selectedDay", app)
        self.assertIn("today={selectedDay}", app)
        self.assertIn("day={selectedDay}", app)
        self.assertIn("loadDaySummary(personId, day)", day_card)
        self.assertIn("loadActiveGoal(personId, day)", day_card)
        self.assertIn("today: input.today", api)
        self.assertNotIn('const today = "2026-07-01"', app)


if __name__ == "__main__":
    unittest.main()
