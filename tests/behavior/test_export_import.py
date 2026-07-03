from __future__ import annotations

import unittest
from datetime import date

from health_monitor.application.service import HealthMonitorService
from health_monitor.domain.nutrients import Nutrients
from health_monitor.lookup.estimates import NutritionEstimate, StaticFoodEstimator


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

    def test_export_import_preserves_agent_tool_call_audit_trail(self) -> None:
        source = HealthMonitorService(
            estimator=StaticFoodEstimator(
                {
                    "kfc double crunch combo": NutritionEstimate(
                        phrase="kfc double crunch combo",
                        food_name="KFC Double Crunch combo",
                        nutrients_per_100g=Nutrients(260, 11, 24, 13),
                        source="fixture_model_estimate",
                        confidence=0.42,
                        notes="Fixture estimate for a regional restaurant meal.",
                    )
                }
            )
        )
        household = source.create_household(name="Casa")
        person = source.create_person(
            household_id=household.id,
            name="Gabriel",
            timezone="America/Sao_Paulo",
        )
        proposal = source.propose_text_meal(
            person_id=person.id,
            logged_at_local="2026-07-01T20:00:00",
            text="300g KFC Double Crunch combo",
            agent_settings={"external_lookup": True},
        )

        exported = source.export_data()
        target = HealthMonitorService()
        target.import_data(exported)
        restored_calls = target.agent_tool_calls_for_run(proposal.source_agent_run_id or "")

        self.assertIn("agent_tool_calls", exported["data"])
        self.assertEqual(
            [(call.tool_name, call.status) for call in restored_calls],
            [
                ("resolve_food_reference", "failed"),
                ("lookup_external_food", "completed"),
                ("estimate_food", "completed"),
            ],
        )
        self.assertEqual(restored_calls[-1].agent_run_id, proposal.source_agent_run_id)

    def test_export_import_preserves_agent_chat_turns(self) -> None:
        source = HealthMonitorService()
        household = source.create_household(name="Casa")
        person = source.create_person(
            household_id=household.id,
            name="Gabriel",
            timezone="America/Sao_Paulo",
        )
        response = source.chat(
            person_id=person.id,
            message="Pode explicar meu diário?",
            today=date(2026, 7, 2),
        )

        exported = source.export_data()
        target = HealthMonitorService()
        imported = target.import_data(exported)
        restored_turns = target.chat_turns_for_person(person.id)

        self.assertIn("agent_chat_turns", exported["data"])
        self.assertEqual(imported["agent_chat_turns"], 1)
        self.assertEqual(len(restored_turns), 1)
        self.assertEqual(restored_turns[0].agent_run_id, response.run_id)
        self.assertEqual(restored_turns[0].user_message, "Pode explicar meu diário?")
        self.assertEqual(restored_turns[0].assistant_message, response.message)
        self.assertEqual(restored_turns[0].behavior_label, response.behavior_label)

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

    def test_export_import_preserves_superseded_clarification_link(self) -> None:
        source = HealthMonitorService()
        household = source.create_household(name="Casa")
        person = source.create_person(
            household_id=household.id,
            name="Gabriel",
            timezone="America/Sao_Paulo",
        )
        source.create_food_with_version(
            household_id=household.id,
            name="Iogurte Natural",
            brand="Batavo",
            version_label="natural",
            nutrients_per_100g=Nutrients(80, 5, 9, 2),
            source="label_scan",
            aliases=["iogurte"],
        )
        _, protein = source.create_food_with_version(
            household_id=household.id,
            name="Iogurte Protein",
            brand="Batavo",
            version_label="protein",
            nutrients_per_100g=Nutrients(70, 10, 6, 1),
            source="label_scan",
            aliases=["iogurte"],
        )
        clarification = source.propose_text_meal(
            person_id=person.id,
            logged_at_local="2026-07-02T10:00:00",
            text="100g iogurte",
            agent_settings={"external_lookup": False},
        )
        resolved = source.resolve_text_meal_food_clarification(
            proposal_id=clarification.id,
            unresolved_index=0,
            food_version_id=protein.id,
        )

        exported = source.export_data()
        target = HealthMonitorService()
        target.import_data(exported)
        restored = target.get_proposal(clarification.id)

        self.assertEqual(restored.status, "superseded")
        self.assertEqual(restored.payload["superseded_by_proposal_id"], resolved.id)

    def test_import_refuses_to_overwrite_non_empty_service(self) -> None:
        source, _ = self.build_populated_service()
        exported = source.export_data()
        target = HealthMonitorService()
        target.create_household(name="Existing")

        with self.assertRaisesRegex(ValueError, "import target must be empty"):
            target.import_data(exported)


if __name__ == "__main__":
    unittest.main()
