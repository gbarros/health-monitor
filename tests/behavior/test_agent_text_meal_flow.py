from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from health_monitor.application.service import HealthMonitorService
from health_monitor.domain.nutrients import Nutrients
from health_monitor.persistence.sqlite_state import SQLiteStateRepository


class AgentTextMealFlowTest(unittest.TestCase):
    def test_structured_meal_creates_audited_proposal_without_mutation(self) -> None:
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

        proposal = service.draft_structured_meal_proposal(
            person_id=person.id,
            day=date(2026, 7, 1),
            time_text="10:00",
            items=[
                {"phrase": "queijo", "quantity_g": 50, "source_text": "50g queijo"},
                {"phrase": "ovo", "quantity_g": 100, "source_text": "2 ovos"},
            ],
            agent_settings={
                "model_profile": "ollama-local",
                "effort": "medium",
                "max_tool_loops": 4,
                "external_lookup": False,
            },
            source_text="10am, 50g queijo, 2 ovos",
        )
        run = service.get_agent_run(proposal.source_agent_run_id or "")

        self.assertEqual(proposal.status, "draft")
        self.assertEqual(proposal.summary, "2 diary entries drafted from structured meal items")
        self.assertEqual(len(proposal.entries), 2)
        self.assertEqual(proposal.entries[0].quantity_g, 50)
        self.assertEqual(proposal.entries[1].quantity_g, 100)
        self.assertEqual(proposal.totals.rounded(), Nutrients(312.5, 24.5, 2.4, 22.75))
        self.assertEqual(run.input_text, "10am, 50g queijo, 2 ovos")
        self.assertEqual(run.settings["model_profile"], "ollama-local")
        self.assertEqual(run.settings["agent_runtime"], "deterministic")
        self.assertEqual(run.settings["model_provider"], "deterministic")
        self.assertEqual(run.status, "proposal_created")
        self.assertEqual(service.day_summary(person.id, date(2026, 7, 1)).totals, Nutrients())

        service.confirm_proposal(proposal.id)

        self.assertEqual(
            service.day_summary(person.id, date(2026, 7, 1)).totals.rounded(),
            Nutrients(312.5, 24.5, 2.4, 22.75),
        )

    def test_draft_meal_entry_can_be_edited_before_confirmation(self) -> None:
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
        proposal = service.draft_structured_meal_proposal(
            person_id=person.id,
            day=date(2026, 7, 1),
            time_text="10:00",
            items=[{"phrase": "queijo", "quantity_g": 100}],
            agent_settings={"external_lookup": False},
        )

        edited = service.update_proposal_entry(
            proposal_id=proposal.id,
            entry_id=proposal.entries[0].id,
            quantity_g=50,
            meal_type="snack",
        )
        applied = service.confirm_proposal(edited.id)
        summary = service.day_summary(person.id, date(2026, 7, 1))

        self.assertEqual(edited.entries[0].quantity_g, 50)
        self.assertEqual(edited.entries[0].meal_type, "snack")
        self.assertEqual(edited.totals.rounded(), Nutrients(157.5, 11.5, 1.3, 11.75))
        self.assertEqual(applied.applied_record_ids, (proposal.entries[0].id,))
        self.assertEqual(summary.totals.rounded(), Nutrients(157.5, 11.5, 1.3, 11.75))
        self.assertEqual(summary.meals["snack"][0].quantity_g, 50)

    def test_draft_meal_entry_food_match_can_be_replaced_before_confirmation(self) -> None:
        service = HealthMonitorService()
        household = service.create_household(name="Casa")
        person = service.create_person(
            household_id=household.id,
            name="Gabriel",
            timezone="America/Sao_Paulo",
        )
        _, regular = service.create_food_with_version(
            household_id=household.id,
            name="Leite integral",
            brand=None,
            version_label="regular",
            nutrients_per_100g=Nutrients(calories_kcal=61, protein_g=3.2, carbs_g=4.8, fat_g=3.3),
            source="reference",
            aliases=["leite"],
        )
        _, protein = service.create_food_with_version(
            household_id=household.id,
            name="Leite mais proteico",
            brand=None,
            version_label="extra protein",
            nutrients_per_100g=Nutrients(calories_kcal=50, protein_g=10, carbs_g=4, fat_g=0.5),
            source="label_scan",
            aliases=["leite proteico"],
        )
        proposal = service.draft_structured_meal_proposal(
            person_id=person.id,
            day=date(2026, 7, 1),
            time_text="10:00",
            items=[{"phrase": "leite", "quantity_g": 100}],
            agent_settings={"external_lookup": False},
        )

        edited = service.update_proposal_entry(
            proposal_id=proposal.id,
            entry_id=proposal.entries[0].id,
            food_version_id=protein.id,
        )
        applied = service.confirm_proposal(edited.id)
        summary = service.day_summary(person.id, date(2026, 7, 1))

        self.assertEqual(proposal.entries[0].food_version_id, regular.id)
        self.assertEqual(edited.entries[0].food_version_id, protein.id)
        self.assertEqual(edited.totals.rounded(), Nutrients(50, 10, 4, 0.5))
        self.assertEqual(edited.evidence[0]["food_version_id"], protein.id)
        self.assertEqual(applied.applied_record_ids, (proposal.entries[0].id,))
        self.assertEqual(summary.meals["breakfast"][0].food_name, "Leite mais proteico")
        self.assertEqual(summary.totals.rounded(), Nutrients(50, 10, 4, 0.5))

    def test_structured_meal_amendment_supersedes_original(self) -> None:
        service = HealthMonitorService()
        household = service.create_household(name="Casa")
        person = service.create_person(
            household_id=household.id,
            name="Gabriel",
            timezone="America/Sao_Paulo",
        )
        service.create_food_with_version(
            household_id=household.id,
            name="Arroz",
            brand=None,
            version_label="cozido",
            nutrients_per_100g=Nutrients(calories_kcal=130, protein_g=2.7, carbs_g=28, fat_g=0.3),
            source="reference",
            aliases=["arroz"],
        )
        service.create_food_with_version(
            household_id=household.id,
            name="Feijão",
            brand=None,
            version_label="cozido",
            nutrients_per_100g=Nutrients(calories_kcal=76, protein_g=4.8, carbs_g=13.6, fat_g=0.5),
            source="reference",
            aliases=["feijao", "feijão"],
        )
        service.create_food_with_version(
            household_id=household.id,
            name="Frango",
            brand=None,
            version_label="grelhado",
            nutrients_per_100g=Nutrients(calories_kcal=165, protein_g=31, carbs_g=0, fat_g=3.6),
            source="reference",
            aliases=["frango"],
        )

        original = service.draft_structured_meal_proposal(
            person_id=person.id,
            day=date(2026, 7, 1),
            time_text="12:00",
            meal_type="lunch",
            items=[
                {"phrase": "arroz", "quantity_g": 150},
                {"phrase": "feijão", "quantity_g": 100},
            ],
            agent_settings={"external_lookup": False},
        )
        amended = service.amend_structured_meal_proposal(
            proposal_id=original.id,
            person_id=person.id,
            add=[{"phrase": "frango", "quantity_g": 113}],
            agent_settings={"external_lookup": False},
            source_text="esqueci 113g de frango",
        )
        superseded = service.get_proposal(original.id)
        applied = service.confirm_proposal(amended.id)
        summary = service.day_summary(person.id, date(2026, 7, 1))

        self.assertEqual(superseded.status, "superseded")
        self.assertEqual(superseded.payload["superseded_by_proposal_id"], amended.id)
        self.assertEqual(amended.status, "draft")
        self.assertEqual(amended.payload["amended_from_proposal_id"], original.id)
        self.assertEqual(len(amended.entries), 3)
        self.assertEqual([entry.quantity_g for entry in amended.entries], [150, 100, 113])
        self.assertEqual(applied.status, "applied")
        self.assertEqual(len(summary.meals["lunch"]), 3)
        self.assertEqual(summary.meals["lunch"][2].food_name, "Frango")

    def test_structured_meal_amendment_can_subtract_from_open_draft(self) -> None:
        service = HealthMonitorService()
        household = service.create_household(name="Casa")
        person = service.create_person(
            household_id=household.id,
            name="Gabriel",
            timezone="America/Sao_Paulo",
        )
        service.create_food_with_version(
            household_id=household.id,
            name="Frango",
            brand=None,
            version_label="grelhado",
            nutrients_per_100g=Nutrients(calories_kcal=165, protein_g=31, carbs_g=0, fat_g=3.6),
            source="reference",
            aliases=["frango"],
        )
        original = service.draft_structured_meal_proposal(
            person_id=person.id,
            day=date(2026, 7, 1),
            time_text="12:00",
            items=[{"phrase": "frango", "quantity_g": 200}],
            agent_settings={"external_lookup": False},
        )

        amended = service.amend_structured_meal_proposal(
            proposal_id=original.id,
            person_id=person.id,
            remove=[{"phrase": "frango", "quantity_g": 50}],
            agent_settings={"external_lookup": False},
            source_text="-50g frango",
        )

        self.assertEqual(service.get_proposal(original.id).status, "superseded")
        self.assertEqual(len(amended.entries), 1)
        self.assertEqual(amended.entries[0].quantity_g, 150)
        self.assertEqual(
            amended.totals.rounded(),
            Nutrients(calories_kcal=247.5, protein_g=46.5, carbs_g=0, fat_g=5.4),
        )

    def test_repeat_meal_service_wrapper_copies_structured_entries_as_proposal(self) -> None:
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
        service.log_diary_entry(
            person_id=person.id,
            logged_at_local="2026-07-01T08:00:00",
            food_version_id=cheese.id,
            quantity_g=50,
            source="manual",
            meal_type="breakfast",
        )

        proposal = service.repeat_meal(
            person_id=person.id,
            source_day=date(2026, 7, 1),
            meal_type="breakfast",
            logged_at_local="2026-07-02T08:00:00",
        )

        self.assertEqual(proposal.status, "draft")
        self.assertEqual(proposal.entries[0].food_version_id, cheese.id)
        self.assertEqual(proposal.entries[0].quantity_g, 50)
        self.assertEqual(proposal.entries[0].meal_type, "breakfast")

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
            proposal = first.draft_structured_meal_proposal(
                person_id=person.id,
                day=date(2026, 7, 1),
                time_text="10:00",
                items=[{"phrase": "queijo", "quantity_g": 100}],
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
