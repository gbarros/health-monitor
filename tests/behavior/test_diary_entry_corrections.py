from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from health_monitor.application.service import HealthMonitorService
from health_monitor.domain.nutrients import Nutrients
from health_monitor.persistence.sqlite_state import SQLiteStateRepository


class DiaryEntryCorrectionsTest(unittest.TestCase):
    def make_logged_entry(self, service: HealthMonitorService) -> tuple[str, str, str]:
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
        entry = service.log_diary_entry(
            person_id=person.id,
            logged_at_local="2026-07-01T10:00:00",
            food_version_id=version.id,
            quantity_g=100,
            source="manual",
        )
        return person.id, version.id, entry.id

    def test_quantity_and_meal_type_correction_updates_summary_totals(self) -> None:
        service = HealthMonitorService()
        person_id, _, entry_id = self.make_logged_entry(service)

        updated = service.update_diary_entry(
            entry_id=entry_id,
            quantity_g=50,
            meal_type="snack",
        )
        summary = service.day_summary(person_id, updated.logged_at.date())

        self.assertEqual(updated.quantity_g, 50)
        self.assertEqual(updated.meal_type, "snack")
        self.assertEqual(summary.totals.rounded(), Nutrients(157.5, 11.5, 1.3, 11.75))
        self.assertNotIn("breakfast", summary.meals)
        self.assertEqual(summary.meals["snack"][0].id, entry_id)

    def test_delete_and_restore_are_reversible_for_day_summary(self) -> None:
        service = HealthMonitorService()
        person_id, _, entry_id = self.make_logged_entry(service)

        deleted = service.delete_diary_entry(entry_id)
        after_delete = service.day_summary(person_id, deleted.logged_at.date())
        restored = service.restore_diary_entry(entry_id)
        after_restore = service.day_summary(person_id, restored.logged_at.date())

        self.assertIsNotNone(deleted.deleted_at)
        self.assertEqual(after_delete.totals, Nutrients())
        self.assertEqual(restored.deleted_at, None)
        self.assertEqual(after_restore.totals.rounded(), Nutrients(315, 23, 2.6, 23.5))

    def test_deleted_entry_state_survives_restart(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "health-monitor.sqlite3"
            first = HealthMonitorService(repository=SQLiteStateRepository(db_path))
            person_id, _, entry_id = self.make_logged_entry(first)
            first.delete_diary_entry(entry_id)

            second = HealthMonitorService(repository=SQLiteStateRepository(db_path))
            summary = second.day_summary(person_id, second.diary.entries[entry_id].logged_at.date())
            restored = second.restore_diary_entry(entry_id)

            self.assertEqual(summary.totals, Nutrients())
            self.assertIsNone(restored.deleted_at)


if __name__ == "__main__":
    unittest.main()
