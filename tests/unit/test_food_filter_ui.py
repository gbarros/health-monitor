from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MAIN_TS = ROOT / "web" / "src" / "main.ts"


class FoodFilterUiTest(unittest.TestCase):
    def test_food_library_and_manual_log_share_filter_state(self) -> None:
        source = MAIN_TS.read_text(encoding="utf-8")

        self.assertIn("foodFilter: string;", source)
        self.assertIn('foodFilter: ""', source)
        self.assertIn("filteredFoods()", source)
        self.assertIn("matchesFoodFilter", source)

    def test_filter_controls_are_rendered_and_bound(self) -> None:
        source = MAIN_TS.read_text(encoding="utf-8")

        self.assertIn('class="food-filter"', source)
        self.assertIn('type="search"', source)
        self.assertIn("onFoodFilterInput", source)
        self.assertIn('querySelectorAll<HTMLInputElement>(".food-filter")', source)

    def test_manual_log_uses_filtered_food_options(self) -> None:
        source = MAIN_TS.read_text(encoding="utf-8")

        self.assertIn("const filtered = filteredFoods();", source)
        self.assertIn("filtered.length", source)
        self.assertIn('No saved foods match this filter.', source)


if __name__ == "__main__":
    unittest.main()
