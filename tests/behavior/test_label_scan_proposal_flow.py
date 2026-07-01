from __future__ import annotations

import tempfile
import unittest
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
