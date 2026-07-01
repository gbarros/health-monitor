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


if __name__ == "__main__":
    unittest.main()
