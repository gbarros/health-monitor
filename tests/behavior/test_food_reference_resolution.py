from __future__ import annotations

import unittest

from health_monitor.domain.food_resolution import FoodResolver
from health_monitor.domain.foods import Food, FoodAlias, FoodCatalog, FoodVersion
from health_monitor.domain.nutrients import Nutrients


class FoodReferenceResolutionBehaviorTest(unittest.TestCase):
    def test_natural_phrase_resolves_to_default_version_without_exposing_version_label(self) -> None:
        catalog = FoodCatalog()
        catalog.add_food(Food(id="food_milk", household_id="household_1", name="Leite proteico"))
        catalog.add_version(
            FoodVersion(
                id="milk_label_v1",
                food_id="food_milk",
                label="Label from first scan",
                source="label_scan",
                nutrients_per_100g=Nutrients(calories_kcal=62, protein_g=6.2),
            ),
            make_default=True,
        )
        catalog.add_alias(
            FoodAlias(
                id="alias_1",
                household_id="household_1",
                person_id="person_1",
                phrase="o leite mais proteico",
                food_id="food_milk",
                confidence=0.95,
            )
        )

        resolution = FoodResolver(catalog).resolve_phrase(
            "o leite mais proteico", person_id="person_1"
        )

        self.assertIsNotNone(resolution)
        assert resolution is not None
        self.assertEqual(resolution.food_id, "food_milk")
        self.assertEqual(resolution.food_version_id, "milk_label_v1")
        self.assertEqual(resolution.reason, "alias_default_version")


if __name__ == "__main__":
    unittest.main()

