from __future__ import annotations

import unittest

from tests.unit.frontend_helpers import ROOT, read_web_file


class MicronutrientUiTest(unittest.TestCase):
    def test_fiber_and_sodium_remain_in_goal_and_nutrient_models(self) -> None:
        types = read_web_file("types.ts")
        tools = (ROOT / "src" / "health_monitor" / "agent" / "tools.py").read_text(encoding="utf-8")
        app = read_web_file("App.tsx")
        day_card = read_web_file("components/DayCard.tsx")

        self.assertIn("fiber_g?: number", types)
        self.assertIn("sodium_mg?: number", types)
        self.assertIn("draft_onboarding_proposal", tools)
        self.assertIn("targets=targets", tools)
        self.assertIn("Fibra", day_card)
        self.assertIn("fiber_g", day_card)


if __name__ == "__main__":
    unittest.main()
