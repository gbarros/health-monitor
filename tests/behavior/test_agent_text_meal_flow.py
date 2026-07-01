from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from health_monitor.application.service import HealthMonitorService
from health_monitor.domain.nutrients import Nutrients
from health_monitor.persistence.sqlite_state import SQLiteStateRepository


class AgentTextMealFlowTest(unittest.TestCase):
    def test_multi_item_text_meal_creates_audited_proposal_without_mutation(self) -> None:
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
            nutrients_per_100g=Nutrients(calories_kcal=315, protein_g=23, carbs_g=2.6, fat_g=23.5),
            source="label_scan",
            aliases=["queijo"],
        )
        service.create_food_with_version(
            household_id=household.id,
            name="Ovo",
            brand=None,
            version_label="large egg",
            nutrients_per_100g=Nutrients(calories_kcal=155, protein_g=13, carbs_g=1.1, fat_g=11),
            source="reference",
            aliases=["ovo", "ovos"],
            serving_size_g=50,
        )

        proposal = service.propose_text_meal(
            person_id=person.id,
            logged_at_local="2026-07-01T09:00:00",
            text="10am, 50g queijo, 2 ovos",
            agent_settings={
                "model_profile": "ollama-local",
                "effort": "medium",
                "max_tool_loops": 4,
                "external_lookup": False,
            },
        )
        run = service.get_agent_run(proposal.source_agent_run_id or "")

        self.assertEqual(proposal.status, "draft")
        self.assertEqual(proposal.summary, "2 diary entries drafted from text meal")
        self.assertEqual(len(proposal.entries), 2)
        self.assertEqual(proposal.entries[0].quantity_g, 50)
        self.assertEqual(proposal.entries[1].quantity_g, 100)
        self.assertEqual(proposal.totals.rounded(), Nutrients(312.5, 24.5, 2.4, 22.75))
        self.assertEqual(run.input_text, "10am, 50g queijo, 2 ovos")
        self.assertEqual(run.settings["model_profile"], "ollama-local")
        self.assertEqual(run.status, "proposal_created")
        self.assertEqual(service.day_summary(person.id, date(2026, 7, 1)).totals, Nutrients())

        service.confirm_proposal(proposal.id)

        self.assertEqual(
            service.day_summary(person.id, date(2026, 7, 1)).totals.rounded(),
            Nutrients(312.5, 24.5, 2.4, 22.75),
        )

    def test_agent_run_and_pending_proposal_survive_restart(self) -> None:
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
                nutrients_per_100g=Nutrients(
                    calories_kcal=315,
                    protein_g=23,
                    carbs_g=2.6,
                    fat_g=23.5,
                ),
                source="label_scan",
                aliases=["queijo"],
            )
            proposal = first.propose_text_meal(
                person_id=person.id,
                logged_at_local="2026-07-01T10:00:00",
                text="100g queijo",
                agent_settings={"model_profile": "ollama-local"},
            )

            second = HealthMonitorService(repository=SQLiteStateRepository(db_path))
            run = second.get_agent_run(proposal.source_agent_run_id or "")
            restored = second.get_proposal(proposal.id)

            self.assertEqual(run.proposal_id, proposal.id)
            self.assertEqual(restored.totals.rounded(), Nutrients(315, 23, 2.6, 23.5))
            self.assertEqual(restored.status, "draft")


if __name__ == "__main__":
    unittest.main()
