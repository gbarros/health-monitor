from __future__ import annotations

import unittest
from datetime import datetime, timezone

from health_monitor.domain.food_resolution import FoodResolver
from health_monitor.domain.foods import BarcodeAssociation, Food, FoodCatalog, FoodVersion
from health_monitor.domain.nutrients import Nutrients


class BarcodeAssociationBehaviorTest(unittest.TestCase):
    def test_label_scan_with_barcode_creates_future_local_resolution(self) -> None:
        catalog = FoodCatalog()
        catalog.add_food(Food(id="food_milk", household_id="household_1", name="Leite proteico"))
        catalog.add_version(
            FoodVersion(
                id="milk_high_protein_label",
                food_id="food_milk",
                label="High protein milk label",
                source="label_scan",
                nutrients_per_100g=Nutrients(calories_kcal=62, protein_g=6.2, carbs_g=5),
            ),
            make_default=True,
        )
        catalog.associate_barcode(
            BarcodeAssociation(
                id="barcode_assoc_1",
                household_id="household_1",
                barcode="7891000000000",
                food_id="food_milk",
                food_version_id="milk_high_protein_label",
                source="label_scan_with_barcode",
                confirmed_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
            )
        )

        resolution = FoodResolver(catalog).resolve_barcode("7891000000000")

        self.assertIsNotNone(resolution)
        assert resolution is not None
        self.assertEqual(resolution.reason, "confirmed_barcode_association")
        self.assertEqual(resolution.food_id, "food_milk")
        self.assertEqual(resolution.food_version_id, "milk_high_protein_label")


if __name__ == "__main__":
    unittest.main()

