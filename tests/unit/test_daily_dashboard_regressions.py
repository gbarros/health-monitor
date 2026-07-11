from __future__ import annotations

import unittest

from tests.unit.frontend_helpers import read_web_file


class DailyDashboardRegressionTest(unittest.TestCase):
    def test_day_navigation_uses_profile_timezone_boundary(self) -> None:
        app = read_web_file("App.tsx")
        day_card = read_web_file("components/DayCard.tsx")

        self.assertIn("todayForActivePerson", app)
        self.assertIn("today={todayForActivePerson}", app)
        self.assertIn("max={today}", day_card)
        self.assertIn("disabled={day >= today}", day_card)
        self.assertNotIn("new Date().toISOString().slice(0, 10)", day_card)

    def test_mobile_chat_keeps_the_budget_visible(self) -> None:
        app = read_web_file("App.tsx")
        styles = read_web_file("styles.css")

        self.assertIn("kcal restantes", app)
        self.assertIn("Prot: faltam", app)
        self.assertIn(".chat-top .day-summary-strip", styles)
        self.assertIn(".chat-top .quick-action-row", styles)

    def test_week_visuals_do_not_invent_zero_values(self) -> None:
        week_card = read_web_file("components/WeekCard.tsx")

        self.assertIn("value > 0 ?", week_card)
        self.assertIn("segment.grams * segment.kcalPerGram", week_card)
        self.assertIn("segment.grams > 0 ?", week_card)

    def test_day_card_does_not_create_a_nested_scroll_region(self) -> None:
        styles = read_web_file("styles.css")
        day_card_blocks = styles.split(".day-card {")[1:]

        self.assertTrue(day_card_blocks)
        for block in day_card_blocks:
            declaration = block.split("}", 1)[0]
            self.assertNotIn("overflow-y", declaration)
            self.assertNotIn("max-height", declaration)


if __name__ == "__main__":
    unittest.main()
