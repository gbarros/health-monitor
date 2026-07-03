from __future__ import annotations

import unittest

from tests.unit.frontend_helpers import read_web_file


class FoodContextUiTest(unittest.TestCase):
    def test_day_card_renders_human_food_names_and_version_context(self) -> None:
        types = read_web_file("types.ts")
        day_card = read_web_file("components/DayCard.tsx")

        self.assertIn("food_name: string", types)
        self.assertIn("food_version_label: string", types)
        self.assertIn("brand?: string", types)
        self.assertIn("entry.food_name", day_card)
        self.assertIn("entry.food_version_label", day_card)
        self.assertIn("entry.brand", day_card)


if __name__ == "__main__":
    unittest.main()
