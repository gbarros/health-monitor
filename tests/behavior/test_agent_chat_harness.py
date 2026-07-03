from __future__ import annotations

import unittest
from datetime import date

from health_monitor.application.service import HealthMonitorService, ModelUnavailableError
from health_monitor.domain.nutrients import Nutrients


class AgentChatHarnessTest(unittest.TestCase):
    def make_service_with_food(self) -> tuple[HealthMonitorService, str, str]:
        service = HealthMonitorService(model_health_checker=lambda: False)
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
            nutrients_per_100g=Nutrients(130, 2.7, 28, 0.3),
            source="reference",
            aliases=["arroz"],
        )
        service.create_food_with_version(
            household_id=household.id,
            name="Frango",
            brand=None,
            version_label="grelhado",
            nutrients_per_100g=Nutrients(165, 31, 0, 3.6),
            source="reference",
            aliases=["frango"],
        )
        return service, household.id, person.id

    def test_model_backed_chat_does_not_process_when_model_is_unavailable(self) -> None:
        service, _, person_id = self.make_service_with_food()

        with self.assertRaises(ModelUnavailableError) as caught:
            service.chat(
                person_id=person_id,
                message="Almoço:\n150g arroz",
                today=date(2026, 7, 2),
                agent_settings={"agent_runtime": "pydantic-ai", "model_profile": "test-model"},
            )

        self.assertEqual(caught.exception.replay_message, "Almoço:\n150g arroz")
        self.assertEqual(service.proposals.proposals, {})
        self.assertEqual(service.chat_turns_for_person(person_id), ())
        self.assertEqual(service.day_summary(person_id, date(2026, 7, 2)).totals, Nutrients())

    def test_chat_weigh_in_is_not_deterministically_logged_when_model_is_unavailable(self) -> None:
        service, _, person_id = self.make_service_with_food()

        with self.assertRaises(ModelUnavailableError):
            service.chat(
                person_id=person_id,
                message="amanheci com 96,3kg",
                today=date(2026, 7, 2),
                agent_settings={"agent_runtime": "pydantic-ai", "model_profile": "test-model"},
            )

        self.assertEqual(service.weight_trend(person_id=person_id).entries, ())

    def test_structured_meal_tool_path_drafts_without_diary_mutation(self) -> None:
        service, _, person_id = self.make_service_with_food()

        proposal = service.draft_structured_meal_proposal(
            person_id=person_id,
            day=date(2026, 7, 2),
            time_text="12:30",
            meal_type="lunch",
            items=[
                {"phrase": "arroz", "quantity_g": 150},
                {"phrase": "frango", "quantity_g": 113},
            ],
            agent_settings={"external_lookup": False},
            source_text="model extracted structured lunch",
        )

        self.assertEqual(proposal.status, "draft")
        self.assertEqual(proposal.proposal_type, "diary_entries")
        self.assertEqual([entry.meal_type for entry in proposal.entries], ["lunch", "lunch"])
        self.assertEqual([entry.quantity_g for entry in proposal.entries], [150, 113])
        self.assertEqual(proposal.totals.rounded(), Nutrients(381.45, 39.08, 42, 4.52))
        self.assertEqual(service.day_summary(person_id, date(2026, 7, 2)).totals, Nutrients())

    def test_structured_amendment_supersedes_open_meal_proposal(self) -> None:
        service, _, person_id = self.make_service_with_food()
        original = service.draft_structured_meal_proposal(
            person_id=person_id,
            day=date(2026, 7, 2),
            time_text="12:30",
            meal_type="lunch",
            items=[{"phrase": "arroz", "quantity_g": 150}],
            agent_settings={"external_lookup": False},
            source_text="model extracted rice",
        )

        amended = service.amend_structured_meal_proposal(
            proposal_id=original.id,
            person_id=person_id,
            add=[{"phrase": "frango", "quantity_g": 113}],
            set_quantity=[{"phrase": "arroz", "quantity_g": 100}],
            agent_settings={"external_lookup": False},
            source_text="model extracted amendment",
        )

        self.assertEqual(service.get_proposal(original.id).status, "superseded")
        self.assertEqual(amended.status, "draft")
        self.assertEqual(amended.payload["amended_from_proposal_id"], original.id)
        self.assertEqual([entry.quantity_g for entry in amended.entries], [100, 113])

    def test_structured_review_note_is_proposal_gated(self) -> None:
        service, _, person_id = self.make_service_with_food()

        proposal = service.draft_review_note_proposal(
            person_id=person_id,
            title="Review note 2026-07-01 to 2026-07-07",
            body="Social dinners made adherence harder than weekday meals.",
            starts_on=date(2026, 7, 1),
            ends_on=date(2026, 7, 7),
        )

        self.assertEqual(proposal.proposal_type, "review_note")
        self.assertEqual(service.review_notes_for_person(person_id), ())

        applied = service.confirm_proposal(proposal.id)
        notes = service.review_notes_for_person(person_id)

        self.assertEqual(applied.status, "applied")
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0].starts_on, date(2026, 7, 1))
        self.assertIn("Social dinners", notes[0].body)


if __name__ == "__main__":
    unittest.main()
