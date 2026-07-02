from __future__ import annotations

import unittest
from datetime import date

from health_monitor.application.service import HealthMonitorService
from health_monitor.domain.nutrients import Nutrients


class ExportImportTest(unittest.TestCase):
    def build_populated_service(self) -> tuple[HealthMonitorService, str]:
        service = HealthMonitorService()
        household = service.create_household(name="Casa")
        person = service.create_person(
            household_id=household.id,
            name="Gabriel",
            timezone="America/Sao_Paulo",
            height_cm=180,
        )
        service.create_goal_profile(
            person_id=person.id,
            starts_on=date(2026, 7, 1),
            targets=Nutrients(2000, 150, 180, 70),
            notes="initial",
        )
        _, version = service.create_food_with_version(
            household_id=household.id,
            name="Queijo Minas",
            brand=None,
            version_label="current",
            nutrients_per_100g=Nutrients(315, 23, 2.6, 23.5),
            source="label_scan",
            aliases=["queijo"],
            barcode="7891000000000",
        )
        service.log_diary_entry(
            person_id=person.id,
            logged_at_local="2026-07-01T10:00:00",
            food_version_id=version.id,
            quantity_g=50,
            source="manual",
        )
        service.log_weight(
            person_id=person.id,
            measured_at_local="2026-07-01T08:00:00",
            weight_kg=91.2,
            note="start",
            source="manual",
        )
        return service, person.id

    def build_service_with_recipe(self) -> tuple[HealthMonitorService, str, str]:
        service = HealthMonitorService()
        household = service.create_household(name="Casa")
        person = service.create_person(
            household_id=household.id,
            name="Gabriel",
            timezone="America/Sao_Paulo",
        )
        service.create_food_with_version(
            household_id=household.id,
            name="Queijo Minas",
            brand=None,
            version_label="current",
            nutrients_per_100g=Nutrients(315, 23, 2.6, 23.5),
            source="label_scan",
            aliases=["queijo"],
        )
        service.create_food_with_version(
            household_id=household.id,
            name="Banana",
            brand=None,
            version_label="generic",
            nutrients_per_100g=Nutrients(89, 1.1, 22.8, 0.3),
            source="reference",
            aliases=["banana"],
        )
        proposal = service.propose_recipe(
            household_id=household.id,
            person_id=person.id,
            recipe_text="\n".join(
                [
                    "Recipe: Batch breakfast mix",
                    "Yield: 1000 g",
                    "Ingredients:",
                    "500g queijo",
                    "500g banana",
                ]
            ),
        )
        applied = service.confirm_proposal(proposal.id)
        return service, person.id, applied.applied_record_ids[1]

    def test_export_contains_required_structured_record_types(self) -> None:
        service, _ = self.build_populated_service()

        exported = service.export_data()

        self.assertEqual(exported["format"], "health-monitor.snapshot")
        self.assertEqual(exported["version"], 1)
        for key in (
            "households",
            "people",
            "goal_profiles",
            "foods",
            "food_versions",
            "food_aliases",
            "barcode_associations",
            "diary_entries",
            "weight_entries",
            "proposals",
            "attachment_objects",
        ):
            self.assertIn(key, exported["data"])
        self.assertEqual(exported["data"]["people"][0]["height_cm"], 180)
        self.assertEqual(exported["data"]["goal_profiles"][0]["targets"]["protein_g"], 150)

    def test_export_import_preserves_recipe_version_metadata(self) -> None:
        source, _, recipe_food_version_id = self.build_service_with_recipe()

        exported = source.export_data()
        target = HealthMonitorService()
        imported = target.import_data(exported)
        restored = target.recipe_version_for_food_version(recipe_food_version_id)

        self.assertIn("recipe_versions", exported["data"])
        self.assertEqual(imported["recipe_versions"], 1)
        self.assertIsNotNone(restored)
        assert restored is not None
        self.assertEqual(restored.name, "Batch breakfast mix")
        self.assertEqual(restored.yield_g, 1000)
        self.assertEqual(
            [ingredient.food_name for ingredient in restored.ingredients],
            ["Queijo Minas", "Banana"],
        )
        self.assertEqual(
            [ingredient.food_version_id for ingredient in restored.ingredients],
            ["food_version_1", "food_version_2"],
        )

    def test_import_reconstructs_records_into_empty_service(self) -> None:
        source, person_id = self.build_populated_service()
        exported = source.export_data()

        target = HealthMonitorService()
        target.import_data(exported)
        summary = target.day_summary(person_id, date(2026, 7, 1))

        self.assertEqual(summary.totals.rounded(), Nutrients(157.5, 11.5, 1.3, 11.75))
        self.assertEqual(summary.target, Nutrients(2000, 150, 180, 70))
        self.assertEqual(len(target.catalog.barcode_associations), 1)

    def test_export_import_preserves_proposal_audit_timestamps(self) -> None:
        source, person_id = self.build_populated_service()
        proposal = source.propose_text_meal(
            person_id=person_id,
            logged_at_local="2026-07-02T10:00:00",
            text="50g queijo",
            agent_settings={"external_lookup": False},
        )
        applied = source.confirm_proposal(proposal.id)

        exported = source.export_data()
        target = HealthMonitorService()
        target.import_data(exported)
        restored = target.get_proposal(proposal.id)

        self.assertIsNotNone(applied.confirmed_at)
        self.assertEqual(
            restored.confirmed_at.isoformat() if restored.confirmed_at is not None else None,
            applied.confirmed_at.isoformat() if applied.confirmed_at is not None else None,
        )
        self.assertIsNone(restored.rejected_at)

    def test_import_refuses_to_overwrite_non_empty_service(self) -> None:
        source, _ = self.build_populated_service()
        exported = source.export_data()
        target = HealthMonitorService()
        target.create_household(name="Existing")

        with self.assertRaisesRegex(ValueError, "import target must be empty"):
            target.import_data(exported)


if __name__ == "__main__":
    unittest.main()
