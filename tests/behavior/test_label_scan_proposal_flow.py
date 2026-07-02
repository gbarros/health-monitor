from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from health_monitor.application.service import HealthMonitorService
from health_monitor.domain.nutrients import Nutrients
from health_monitor.persistence.sqlite_state import SQLiteStateRepository


LABEL_TEXT = """
Produto: Iogurte Batavo Protein
Marca: Batavo
Porcao: 170 g
Valor energetico: 120 kcal
Proteinas: 15 g
Carboidratos: 10 g
Gorduras totais: 2 g
Codigo de barras: 7891000000000
"""


class LabelScanProposalFlowTest(unittest.TestCase):
    def test_label_table_creates_food_version_proposal_before_library_mutation(self) -> None:
        service = HealthMonitorService()
        household = service.create_household(name="Casa")
        person = service.create_person(
            household_id=household.id,
            name="Gabriel",
            timezone="America/Sao_Paulo",
        )

        proposal = service.propose_label_scan(
            household_id=household.id,
            person_id=person.id,
            table_text=LABEL_TEXT,
            set_as_default=True,
        )

        self.assertEqual(proposal.status, "draft")
        self.assertEqual(proposal.proposal_type, "food_version_from_label")
        self.assertEqual(proposal.payload["food_name"], "Iogurte Batavo Protein")
        self.assertEqual(proposal.payload["brand"], "Batavo")
        self.assertEqual(proposal.payload["barcode"], "7891000000000")
        self.assertEqual(
            proposal.payload["nutrients_per_100g"],
            {
                "calories_kcal": 70.59,
                "protein_g": 8.82,
                "carbs_g": 5.88,
                "fat_g": 1.18,
                "fiber_g": 0,
                "sodium_mg": 0,
            },
        )
        self.assertIsNone(service.resolver.resolve_barcode("7891000000000"))

        applied = service.confirm_proposal(proposal.id)
        resolution = service.resolve_food_reference(
            household_id=household.id,
            person_id=person.id,
            barcode="7891000000000",
        )

        self.assertEqual(applied.status, "applied")
        self.assertEqual(len(applied.applied_record_ids), 3)
        self.assertEqual(resolution.reason, "confirmed_barcode_association")

    def test_applied_label_proposal_cannot_be_confirmed_again(self) -> None:
        service = HealthMonitorService()
        household = service.create_household(name="Casa")
        person = service.create_person(
            household_id=household.id,
            name="Gabriel",
            timezone="America/Sao_Paulo",
        )
        proposal = service.propose_label_scan(
            household_id=household.id,
            person_id=person.id,
            table_text=LABEL_TEXT,
            set_as_default=True,
        )

        applied = service.confirm_proposal(proposal.id)

        with self.assertRaisesRegex(ValueError, "already applied"):
            service.confirm_proposal(proposal.id)
        with self.assertRaisesRegex(ValueError, "cannot reject applied proposal"):
            service.reject_proposal(proposal.id)
        self.assertEqual(service.get_proposal(proposal.id), applied)
        self.assertEqual(
            len(service.list_food_versions(household_id=household.id, person_id=person.id)),
            1,
        )

    def test_separate_barcode_scan_is_associated_with_label_proposal(self) -> None:
        service = HealthMonitorService()
        household = service.create_household(name="Casa")
        person = service.create_person(
            household_id=household.id,
            name="Gabriel",
            timezone="America/Sao_Paulo",
        )

        proposal = service.propose_label_scan(
            household_id=household.id,
            person_id=person.id,
            table_text="\n".join(
                [
                    "Produto: Iogurte Batavo Protein",
                    "Marca: Batavo",
                    "Porcao: 170 g",
                    "Valor energetico: 120 kcal",
                    "Proteinas: 15 g",
                    "Carboidratos: 10 g",
                    "Gorduras totais: 2 g",
                ]
            ),
            barcode="7891000000000",
            set_as_default=True,
        )
        applied = service.confirm_proposal(proposal.id)
        resolution = service.resolve_food_reference(
            household_id=household.id,
            person_id=person.id,
            barcode="7891000000000",
        )

        self.assertEqual(proposal.payload["barcode"], "7891000000000")
        self.assertEqual(applied.applied_record_ids[1], resolution.food_version_id)

    def test_label_scan_can_save_food_and_log_portion_after_confirmation(self) -> None:
        service = HealthMonitorService()
        household = service.create_household(name="Casa")
        person = service.create_person(
            household_id=household.id,
            name="Gabriel",
            timezone="America/Sao_Paulo",
        )

        proposal = service.propose_label_scan(
            household_id=household.id,
            person_id=person.id,
            table_text=LABEL_TEXT,
            logged_at_local="2026-07-01T10:00:00",
            quantity_g=170,
            set_as_default=True,
        )
        before = service.day_summary(person.id, date(2026, 7, 1))
        applied = service.confirm_proposal(proposal.id)
        after = service.day_summary(person.id, date(2026, 7, 1))
        entry_id = applied.applied_record_ids[-1]
        entry = service.diary.entries[entry_id]

        self.assertEqual(len(proposal.entries), 1)
        self.assertEqual(proposal.entries[0].quantity_g, 170)
        self.assertEqual(before.totals.calories_kcal, 0)
        self.assertEqual(entry.food_version_id, applied.applied_record_ids[1])
        self.assertEqual(entry.source, "label_scan")
        self.assertEqual(after.totals.rounded(), Nutrients(120, 14.99, 10, 2.01))

    def test_new_label_for_existing_food_creates_new_default_version_without_rewriting_history(self) -> None:
        service = HealthMonitorService()
        household = service.create_household(name="Casa")
        person = service.create_person(
            household_id=household.id,
            name="Gabriel",
            timezone="America/Sao_Paulo",
        )
        food, old_version = service.create_food_with_version(
            household_id=household.id,
            name="Iogurte Batavo Protein",
            brand="Batavo",
            version_label="old label",
            nutrients_per_100g=Nutrients(calories_kcal=80, protein_g=8, carbs_g=7, fat_g=2),
            source="label_scan",
            aliases=["iogurte batavo"],
        )
        old_entry = service.log_diary_entry(
            person_id=person.id,
            logged_at_local="2026-07-01T10:00:00",
            food_version_id=old_version.id,
            quantity_g=100,
            source="manual",
        )

        proposal = service.propose_label_scan(
            household_id=household.id,
            person_id=person.id,
            table_text=LABEL_TEXT,
            set_as_default=True,
        )
        applied = service.confirm_proposal(proposal.id)
        updated_food = service.catalog.foods[food.id]
        new_version = service.catalog.get_version(applied.applied_record_ids[1])
        old_day = service.day_summary(person.id, date(2026, 7, 1))
        resolved = service.resolve_food_reference(
            household_id=household.id,
            person_id=person.id,
            phrase="iogurte batavo",
        )

        self.assertEqual(applied.applied_record_ids[0], food.id)
        self.assertEqual(new_version.food_id, food.id)
        self.assertNotEqual(new_version.id, old_version.id)
        self.assertEqual(updated_food.default_version_id, new_version.id)
        self.assertEqual(service.diary.entries[old_entry.id].food_version_id, old_version.id)
        self.assertEqual(old_day.totals.rounded(), Nutrients(80, 8, 7, 2))
        self.assertEqual(resolved.food_version_id, new_version.id)

    def test_pending_label_proposal_survives_restart_and_can_be_confirmed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "health-monitor.sqlite3"
            first = HealthMonitorService(repository=SQLiteStateRepository(db_path))
            household = first.create_household(name="Casa")
            person = first.create_person(
                household_id=household.id,
                name="Gabriel",
                timezone="America/Sao_Paulo",
            )
            proposal = first.propose_label_scan(
                household_id=household.id,
                person_id=person.id,
                table_text=LABEL_TEXT,
                set_as_default=True,
            )

            second = HealthMonitorService(repository=SQLiteStateRepository(db_path))
            restored = second.get_proposal(proposal.id)
            applied = second.confirm_proposal(restored.id)
            resolution = second.resolve_food_reference(
                household_id=household.id,
                person_id=person.id,
                barcode="7891000000000",
            )

            self.assertEqual(restored.payload["serving_size_g"], 170)
            self.assertEqual(applied.status, "applied")
            self.assertEqual(resolution.food_version_id, applied.applied_record_ids[1])


if __name__ == "__main__":
    unittest.main()
