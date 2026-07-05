from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from health_monitor.application.service import HealthMonitorService
from health_monitor.domain.nutrients import Nutrients
from health_monitor.persistence.sqlite_state import SQLiteStateRepository


class PersistentApplicationStateTest(unittest.TestCase):
    def test_diary_food_alias_and_barcode_survive_service_restart(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "health-monitor.sqlite3"
            first = HealthMonitorService(repository=SQLiteStateRepository(db_path))
            household = first.create_household(name="Casa")
            person = first.create_person(
                household_id=household.id,
                name="Gabriel",
                timezone="America/Sao_Paulo",
            )
            _, version = first.create_food_with_version(
                household_id=household.id,
                name="Leite Proteico",
                brand="Piracanjuba",
                version_label="15g protein label",
                nutrients_per_100g=Nutrients(calories_kcal=62, protein_g=6.2, carbs_g=4.8, fat_g=1.5),
                source="label_scan",
                aliases=["o leite mais proteico"],
                barcode="7892000000000",
            )
            first.log_diary_entry(
                person_id=person.id,
                logged_at_local="2026-07-01T10:00:00",
                food_version_id=version.id,
                quantity_g=200,
                source="manual",
            )

            second = HealthMonitorService(repository=SQLiteStateRepository(db_path))
            summary = second.day_summary(person_id=person.id, day=date(2026, 7, 1))
            by_alias = second.resolve_food_reference(
                household_id=household.id,
                person_id=person.id,
                phrase="o leite mais proteico",
            )
            by_barcode = second.resolve_food_reference(
                household_id=household.id,
                person_id=person.id,
                barcode="7892000000000",
            )

            self.assertEqual(summary.totals.rounded(), Nutrients(124, 12.4, 9.6, 3))
            self.assertEqual(summary.meals["breakfast"][0].food_name, "Leite Proteico")
            self.assertEqual(by_alias.food_version_id, version.id)
            self.assertEqual(by_barcode.food_version_id, version.id)

    def test_food_library_can_be_reloaded_after_service_restart(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "health-monitor.sqlite3"
            first = HealthMonitorService(repository=SQLiteStateRepository(db_path))
            household = first.create_household(name="Casa")
            person = first.create_person(
                household_id=household.id,
                name="Gabriel",
                timezone="America/Sao_Paulo",
            )
            _, version = first.create_food_with_version(
                household_id=household.id,
                name="Leite Proteico",
                brand="Piracanjuba",
                version_label="15g protein label",
                nutrients_per_100g=Nutrients(calories_kcal=62, protein_g=6.2, carbs_g=4.8, fat_g=1.5),
                source="label_scan",
                aliases=["o leite mais proteico"],
                barcode="7892000000000",
            )

            second = HealthMonitorService(repository=SQLiteStateRepository(db_path))
            foods = second.list_food_versions(
                household_id=household.id,
                person_id=person.id,
                query="proteico",
            )

            self.assertEqual(len(foods), 1)
            self.assertEqual(foods[0][0].name, "Leite Proteico")
            self.assertEqual(foods[0][1].id, version.id)

    def test_draft_proposal_can_be_confirmed_after_service_restart(self) -> None:
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
                nutrients_per_100g=Nutrients(calories_kcal=315, protein_g=23, carbs_g=2.6, fat_g=23.5),
                source="label_scan",
                aliases=["queijo"],
            )
            proposal = first.draft_structured_meal_proposal(
                person_id=person.id,
                day=date(2026, 7, 1),
                time_text="10:00",
                items=[{"phrase": "queijo", "quantity_g": 100}],
                agent_settings={"model_profile": "ollama-local"},
            )

            second = HealthMonitorService(repository=SQLiteStateRepository(db_path))
            before = second.day_summary(person_id=person.id, day=date(2026, 7, 1))
            applied = second.confirm_proposal(proposal.id)
            third = HealthMonitorService(repository=SQLiteStateRepository(db_path))
            after = third.day_summary(person_id=person.id, day=date(2026, 7, 1))

            self.assertEqual(before.totals, Nutrients())
            self.assertEqual(applied.status, "applied")
            self.assertEqual(after.totals.rounded(), Nutrients(315, 23, 2.6, 23.5))


if __name__ == "__main__":
    unittest.main()
