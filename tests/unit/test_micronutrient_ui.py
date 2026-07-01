from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MAIN_TS = ROOT / "web" / "src" / "main.ts"


class MicronutrientUiTest(unittest.TestCase):
    def test_today_and_review_surfaces_show_fiber_and_sodium(self) -> None:
        source = MAIN_TS.read_text(encoding="utf-8")

        self.assertIn('metric("Fiber"', source)
        self.assertIn('metric("Sodium"', source)
        self.assertIn("totals.fiber_g", source)
        self.assertIn("totals.sodium_mg", source)
        self.assertIn("averages.fiber_g", source)
        self.assertIn("averages.sodium_mg", source)

    def test_manual_food_forms_accept_fiber_and_sodium(self) -> None:
        source = MAIN_TS.read_text(encoding="utf-8")

        self.assertIn('name="fiber_g"', source)
        self.assertIn('name="sodium_mg"', source)
        self.assertIn('fiber_g: numberField(form, "fiber_g")', source)
        self.assertIn('sodium_mg: numberField(form, "sodium_mg")', source)


if __name__ == "__main__":
    unittest.main()
