from __future__ import annotations

import unittest
from datetime import date

from health_monitor.application.service import HealthMonitorService
from health_monitor.domain.nutrients import Nutrients


class DailyDriverApplicationSliceTest(unittest.TestCase):
    def test_household_person_food_diary_and_summary_flow(self) -> None:
        service = HealthMonitorService()
        household = service.create_household(name="Casa")
        person = service.create_person(
            household_id=household.id,
            name="Gabriel",
            timezone="America/Sao_Paulo",
        )
        food, version = service.create_food_with_version(
            household_id=household.id,
            name="Iogurte Batavo",
            brand="Batavo",
            version_label="Protein label",
            nutrients_per_100g=Nutrients(calories_kcal=80, protein_g=10, carbs_g=7, fat_g=1),
            source="label_scan",
            aliases=["iogurte batavo", "o iogurte dessa semana"],
            barcode="7891000000000",
        )

        entry = service.log_diary_entry(
            person_id=person.id,
            logged_at_local="2026-07-01T10:00:00",
            food_version_id=version.id,
            quantity_g=150,
            source="manual",
        )
        summary = service.day_summary(person_id=person.id, day=date(2026, 7, 1))

        self.assertEqual(food.default_version_id, version.id)
        self.assertEqual(entry.meal_type, "breakfast")
        self.assertEqual(summary.person_id, person.id)
        self.assertEqual(summary.day, date(2026, 7, 1))
        self.assertEqual(summary.totals.rounded(), Nutrients(120, 15, 10.5, 1.5))
        self.assertEqual(summary.meals["breakfast"][0].food_name, "Iogurte Batavo")
        self.assertEqual(summary.meals["breakfast"][0].quantity_g, 150)

    def test_barcode_and_alias_resolution_reuse_local_food_version(self) -> None:
        service = HealthMonitorService()
        household = service.create_household(name="Casa")
        person = service.create_person(
            household_id=household.id,
            name="Gabriel",
            timezone="America/Sao_Paulo",
        )
        _, version = service.create_food_with_version(
            household_id=household.id,
            name="Leite Proteico",
            brand="Piracanjuba",
            version_label="15g protein label",
            nutrients_per_100g=Nutrients(calories_kcal=62, protein_g=6.2, carbs_g=4.8, fat_g=1.5),
            source="label_scan",
            aliases=["o leite mais proteico"],
            barcode="7892000000000",
        )

        by_alias = service.resolve_food_reference(
            household_id=household.id,
            phrase="o leite mais proteico",
            person_id=person.id,
        )
        by_barcode = service.resolve_food_reference(
            household_id=household.id,
            barcode="7892000000000",
            person_id=person.id,
        )

        self.assertEqual(by_alias.food_version_id, version.id)
        self.assertEqual(by_alias.reason, "alias_default_version")
        self.assertEqual(by_barcode.food_version_id, version.id)
        self.assertEqual(by_barcode.reason, "confirmed_barcode_association")

    def test_ambiguous_alias_resolution_prefers_recently_logged_food(self) -> None:
        service = HealthMonitorService()
        household = service.create_household(name="Casa")
        person = service.create_person(
            household_id=household.id,
            name="Gabriel",
            timezone="America/Sao_Paulo",
        )
        _, old_yogurt = service.create_food_with_version(
            household_id=household.id,
            name="Iogurte Natural",
            brand="Batavo",
            version_label="natural label",
            nutrients_per_100g=Nutrients(calories_kcal=80, protein_g=5, carbs_g=9, fat_g=2),
            source="label_scan",
            aliases=["iogurte"],
        )
        _, protein_yogurt = service.create_food_with_version(
            household_id=household.id,
            name="Iogurte Protein",
            brand="Batavo",
            version_label="protein label",
            nutrients_per_100g=Nutrients(calories_kcal=70, protein_g=10, carbs_g=6, fat_g=1),
            source="label_scan",
            aliases=["iogurte"],
        )
        service.log_diary_entry(
            person_id=person.id,
            logged_at_local="2026-07-01T10:00:00",
            food_version_id=old_yogurt.id,
            quantity_g=100,
            source="manual",
        )
        service.log_diary_entry(
            person_id=person.id,
            logged_at_local="2026-07-03T10:00:00",
            food_version_id=protein_yogurt.id,
            quantity_g=100,
            source="manual",
        )

        resolution = service.resolve_food_reference(
            household_id=household.id,
            person_id=person.id,
            phrase="iogurte",
        )

        self.assertEqual(resolution.food_version_id, protein_yogurt.id)
        self.assertEqual(resolution.reason, "alias_recently_logged_version")

    def test_text_meal_logging_creates_proposal_before_diary_mutation(self) -> None:
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
            nutrients_per_100g=Nutrients(calories_kcal=315, protein_g=23, carbs_g=2.6, fat_g=23.5),
            source="label_scan",
            aliases=["queijo"],
        )

        proposal = service.propose_text_meal(
            person_id=person.id,
            logged_at_local="2026-07-01T10:00:00",
            text="100g queijo",
            agent_settings={"model_profile": "ollama-local", "max_tool_loops": 4},
        )

        self.assertEqual(proposal.status, "draft")
        self.assertEqual(proposal.entries[0].food_version_id, version.id)
        self.assertEqual(proposal.entries[0].quantity_g, 100)
        self.assertEqual(service.day_summary(person.id, date(2026, 7, 1)).totals, Nutrients())

        applied = service.confirm_proposal(proposal.id)

        self.assertEqual(applied.status, "applied")
        self.assertEqual(
            service.day_summary(person.id, date(2026, 7, 1)).totals.rounded(),
            Nutrients(315, 23, 2.6, 23.5),
        )

    def test_quick_custom_food_can_be_created_and_logged_in_one_flow(self) -> None:
        service = HealthMonitorService()
        household = service.create_household(name="Casa")
        person = service.create_person(
            household_id=household.id,
            name="Gabriel",
            timezone="America/Sao_Paulo",
        )

        food, version, entry = service.create_custom_food_and_log_entry(
            household_id=household.id,
            person_id=person.id,
            name="Pao de queijo caseiro",
            brand=None,
            version_label="quick custom",
            nutrients_per_100g=Nutrients(
                calories_kcal=280,
                protein_g=7,
                carbs_g=35,
                fat_g=12,
                fiber_g=3,
                sodium_mg=400,
            ),
            logged_at_local="2026-07-01T16:00:00",
            quantity_g=80,
            aliases=["pao de queijo"],
        )
        summary = service.day_summary(person.id, date(2026, 7, 1))
        resolved = service.resolve_food_reference(
            household_id=household.id,
            person_id=person.id,
            phrase="pao de queijo",
        )

        self.assertEqual(food.default_version_id, version.id)
        self.assertEqual(entry.food_version_id, version.id)
        self.assertEqual(entry.meal_type, "snack")
        self.assertEqual(entry.source, "manual_quick_custom")
        self.assertEqual(summary.totals.rounded(), Nutrients(224, 5.6, 28, 9.6, 2.4, 320))
        self.assertEqual(resolved.food_version_id, version.id)

    def test_manual_log_can_use_known_serving_size(self) -> None:
        service = HealthMonitorService()
        household = service.create_household(name="Casa")
        person = service.create_person(
            household_id=household.id,
            name="Gabriel",
            timezone="America/Sao_Paulo",
        )
        _, egg = service.create_food_with_version(
            household_id=household.id,
            name="Ovo",
            brand=None,
            version_label="large egg",
            nutrients_per_100g=Nutrients(calories_kcal=155, protein_g=13, carbs_g=1.1, fat_g=11),
            source="reference",
            aliases=["ovo"],
            serving_size_g=50,
        )

        entry = service.log_diary_entry(
            person_id=person.id,
            logged_at_local="2026-07-01T09:00:00",
            food_version_id=egg.id,
            serving_count=2,
            source="manual",
        )
        summary = service.day_summary(person.id, date(2026, 7, 1))

        self.assertEqual(entry.quantity_g, 100)
        self.assertEqual(summary.totals.rounded(), Nutrients(155, 13, 1.1, 11))

    def test_manual_serving_log_requires_serving_size(self) -> None:
        service = HealthMonitorService()
        household = service.create_household(name="Casa")
        person = service.create_person(
            household_id=household.id,
            name="Gabriel",
            timezone="America/Sao_Paulo",
        )
        _, cheese = service.create_food_with_version(
            household_id=household.id,
            name="Queijo Minas",
            brand=None,
            version_label="current",
            nutrients_per_100g=Nutrients(calories_kcal=315, protein_g=23, carbs_g=2.6, fat_g=23.5),
            source="label_scan",
            aliases=["queijo"],
        )

        with self.assertRaisesRegex(ValueError, "serving_size_g is required"):
            service.log_diary_entry(
                person_id=person.id,
                logged_at_local="2026-07-01T09:00:00",
                food_version_id=cheese.id,
                serving_count=1,
                source="manual",
            )

    def test_archived_food_leaves_history_but_stops_future_resolution(self) -> None:
        service = HealthMonitorService()
        household = service.create_household(name="Casa")
        person = service.create_person(
            household_id=household.id,
            name="Gabriel",
            timezone="America/Sao_Paulo",
        )
        food, version = service.create_food_with_version(
            household_id=household.id,
            name="Iogurte antigo",
            brand="Batavo",
            version_label="old label",
            nutrients_per_100g=Nutrients(calories_kcal=80, protein_g=5, carbs_g=9, fat_g=2),
            source="label_scan",
            aliases=["iogurte antigo"],
            barcode="7891000000000",
        )
        service.log_diary_entry(
            person_id=person.id,
            logged_at_local="2026-07-01T10:00:00",
            food_version_id=version.id,
            quantity_g=100,
            source="manual",
        )

        archived = service.archive_food(food.id)
        summary = service.day_summary(person.id, date(2026, 7, 1))
        listed = service.list_food_versions(household_id=household.id, person_id=person.id)

        self.assertTrue(archived.archived)
        self.assertEqual(summary.meals["breakfast"][0].food_name, "Iogurte antigo")
        self.assertEqual(summary.totals.rounded(), Nutrients(80, 5, 9, 2))
        self.assertEqual(listed, ())
        with self.assertRaisesRegex(ValueError, "food reference could not be resolved"):
            service.resolve_food_reference(
                household_id=household.id,
                person_id=person.id,
                phrase="iogurte antigo",
            )
        with self.assertRaisesRegex(ValueError, "food reference could not be resolved"):
            service.resolve_food_reference(
                household_id=household.id,
                person_id=person.id,
                barcode="7891000000000",
            )


if __name__ == "__main__":
    unittest.main()
