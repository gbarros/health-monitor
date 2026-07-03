from __future__ import annotations

import unittest

from tests.unit.frontend_helpers import read_web_file


class MicronutrientUiTest(unittest.TestCase):
    def test_fiber_and_sodium_remain_in_goal_and_nutrient_models(self) -> None:
        types = read_web_file("types.ts")
        api = read_web_file("api.ts")
        app = read_web_file("App.tsx")
        day_card = read_web_file("components/DayCard.tsx")

        self.assertIn("fiber_g?: number", types)
        self.assertIn("sodium_mg?: number", types)
        self.assertIn("fiber_g: 30", app)
        self.assertIn("sodium_mg: 2300", app)
        self.assertIn("/api/agent/onboarding-proposal", api)
        self.assertIn("Fibra", day_card)
        self.assertIn("fiber_g", day_card)


if __name__ == "__main__":
    unittest.main()
