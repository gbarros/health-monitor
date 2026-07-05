from __future__ import annotations

import unittest

from health_monitor.application.service import HealthMonitorService
from health_monitor.domain.nutrients import Nutrients


class FoodNameResolutionBehaviorTest(unittest.TestCase):
    def test_exact_food_name_resolves_to_default_version(self) -> None:
        service = HealthMonitorService()
        household = service.create_household(name="Casa")
        person = service.create_person(
            household_id=household.id,
            name="Gabriel",
            timezone="America/Sao_Paulo",
        )
        _, version = service.create_food_with_version(
            household_id=household.id,
            name="Queijo Minas",
            brand=None,
            version_label="current",
            nutrients_per_100g=Nutrients(315, 23, 2.6, 23.5),
            source="label_scan",
            aliases=["queijo"],
        )

        resolution = service.resolve_food_reference(
            household_id=household.id,
            person_id=person.id,
            phrase="Queijo Minas",
        )

        self.assertEqual(resolution.food_version_id, version.id)
        self.assertEqual(resolution.reason, "exact_food_name")


if __name__ == "__main__":
    unittest.main()
