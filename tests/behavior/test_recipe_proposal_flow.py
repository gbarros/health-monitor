from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from health_monitor.application.service import HealthMonitorService
from health_monitor.domain.nutrients import Nutrients
from health_monitor.persistence.sqlite_state import SQLiteStateRepository


RECIPE_TEXT = """
Recipe: Batch breakfast mix
Yield: 1000 g
Ingredients:
500g queijo
500g banana
"""


class RecipeProposalFlowTest(unittest.TestCase):
    def make_service_with_ingredients(self) -> tuple[HealthMonitorService, str, str]:
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
        return service, household.id, person.id

    def test_recipe_with_yield_creates_reusable_food_version_after_confirmation(self) -> None:
        service, household_id, person_id = self.make_service_with_ingredients()

        proposal = service.propose_recipe(
            household_id=household_id,
            person_id=person_id,
            recipe_text=RECIPE_TEXT,
        )

        self.assertEqual(proposal.proposal_type, "recipe_food_version")
        self.assertEqual(proposal.status, "draft")
        self.assertEqual(proposal.payload["food_name"], "Batch breakfast mix")
        self.assertEqual(proposal.payload["yield_g"], 1000)
        self.assertEqual(
            proposal.payload["nutrients_per_100g"],
            {
                "calories_kcal": 202,
                "protein_g": 12.05,
                "carbs_g": 12.7,
                "fat_g": 11.9,
                "fiber_g": 0,
                "sodium_mg": 0,
            },
        )
        self.assertIsNone(service.resolver.resolve_phrase("batch breakfast mix", person_id=person_id))

        applied = service.confirm_proposal(proposal.id)
        resolution = service.resolve_food_reference(
            household_id=household_id,
            person_id=person_id,
            phrase="batch breakfast mix",
        )

        self.assertEqual(applied.status, "applied")
        self.assertEqual(len(applied.applied_record_ids), 2)
        self.assertEqual(resolution.food_version_id, applied.applied_record_ids[1])

    def test_recipe_missing_yield_creates_draft_without_reusable_food_version(self) -> None:
        service, household_id, person_id = self.make_service_with_ingredients()

        proposal = service.propose_recipe(
            household_id=household_id,
            person_id=person_id,
            recipe_text="Recipe: No yield\nIngredients:\n500g queijo",
        )
        applied = service.confirm_proposal(proposal.id)

        self.assertEqual(proposal.proposal_type, "recipe_draft")
        self.assertEqual(proposal.payload["food_name"], "No yield")
        self.assertEqual(proposal.payload["yield_g"], None)
        self.assertEqual(proposal.payload["precise_logging_enabled"], False)
        self.assertEqual(proposal.payload["missing_fields"], ["yield_g"])
        self.assertEqual(applied.status, "applied")
        self.assertEqual(applied.applied_record_ids, ())
        self.assertIsNone(service.resolver.resolve_phrase("no yield", person_id=person_id))

    def test_recipe_update_creates_new_default_version_without_rewriting_old_logs(self) -> None:
        service, household_id, person_id = self.make_service_with_ingredients()
        first = service.propose_recipe(
            household_id=household_id,
            person_id=person_id,
            recipe_text=RECIPE_TEXT,
        )
        first_applied = service.confirm_proposal(first.id)
        first_version_id = first_applied.applied_record_ids[1]
        service.log_diary_entry(
            person_id=person_id,
            logged_at_local="2026-07-01T10:00:00",
            food_version_id=first_version_id,
            quantity_g=100,
            source="manual",
        )

        second = service.propose_recipe(
            household_id=household_id,
            person_id=person_id,
            recipe_text="\n".join(
                [
                    "Recipe: Batch breakfast mix",
                    "Yield: 800 g",
                    "Ingredients:",
                    "500g queijo",
                    "500g banana",
                ]
            ),
        )
        second_applied = service.confirm_proposal(second.id)
        second_version_id = second_applied.applied_record_ids[1]
        resolved = service.resolve_food_reference(
            household_id=household_id,
            person_id=person_id,
            phrase="batch breakfast mix",
        )
        old_day = service.day_summary(person_id, date(2026, 7, 1))

        self.assertEqual(second_applied.applied_record_ids[0], first_applied.applied_record_ids[0])
        self.assertNotEqual(second_version_id, first_version_id)
        self.assertEqual(resolved.food_version_id, second_version_id)
        self.assertEqual(old_day.totals.rounded(), Nutrients(202, 12.05, 12.7, 11.9))

    def test_pending_recipe_proposal_survives_restart_and_can_be_confirmed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "health-monitor.sqlite3"
            first = HealthMonitorService(repository=SQLiteStateRepository(db_path))
            household = first.create_household(name="Casa")
            person = first.create_person(
                household_id=household.id,
                name="Gabriel",
                timezone="America/Sao_Paulo",
            )
            first.create_food_with_version(
                household_id=household.id,
                name="Queijo Minas",
                brand=None,
                version_label="current",
                nutrients_per_100g=Nutrients(315, 23, 2.6, 23.5),
                source="label_scan",
                aliases=["queijo"],
            )
            first.create_food_with_version(
                household_id=household.id,
                name="Banana",
                brand=None,
                version_label="generic",
                nutrients_per_100g=Nutrients(89, 1.1, 22.8, 0.3),
                source="reference",
                aliases=["banana"],
            )
            proposal = first.propose_recipe(
                household_id=household.id,
                person_id=person.id,
                recipe_text=RECIPE_TEXT,
            )

            second = HealthMonitorService(repository=SQLiteStateRepository(db_path))
            restored = second.get_proposal(proposal.id)
            applied = second.confirm_proposal(restored.id)

            self.assertEqual(restored.proposal_type, "recipe_food_version")
            self.assertEqual(applied.status, "applied")


if __name__ == "__main__":
    unittest.main()
