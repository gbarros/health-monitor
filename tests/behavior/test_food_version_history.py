from __future__ import annotations

import unittest
from datetime import datetime, timezone

from health_monitor.domain.diary import Diary, DiaryEntry
from health_monitor.domain.foods import Food, FoodCatalog, FoodVersion
from health_monitor.domain.nutrients import Nutrients


class FoodVersionHistoryBehaviorTest(unittest.TestCase):
    def test_new_food_version_does_not_rewrite_historical_diary_entry(self) -> None:
        catalog = FoodCatalog()
        catalog.add_food(Food(id="food_yogurt", household_id="household_1", name="Iogurte"))
        catalog.add_version(
            FoodVersion(
                id="yogurt_label_june",
                food_id="food_yogurt",
                label="June label",
                source="label_scan",
                nutrients_per_100g=Nutrients(calories_kcal=80, protein_g=5),
            ),
            make_default=True,
        )

        diary = Diary(catalog)
        diary.add_entry(
            DiaryEntry(
                id="entry_1",
                person_id="person_1",
                logged_at=datetime(2026, 7, 1, 8, 0, tzinfo=timezone.utc),
                meal_type="breakfast",
                food_version_id="yogurt_label_june",
                quantity_g=100,
                source="manual",
            )
        )

        catalog.add_version(
            FoodVersion(
                id="yogurt_label_july",
                food_id="food_yogurt",
                label="July label",
                source="label_scan",
                nutrients_per_100g=Nutrients(calories_kcal=95, protein_g=8),
            ),
            make_default=True,
        )

        totals = diary.totals_for_day("person_1", datetime(2026, 7, 1).date())

        self.assertEqual(totals.calories_kcal, 80)
        self.assertEqual(totals.protein_g, 5)
        self.assertEqual(diary.entries["entry_1"].food_version_id, "yogurt_label_june")
        self.assertEqual(catalog.get_default_version("food_yogurt").id, "yogurt_label_july")


if __name__ == "__main__":
    unittest.main()

