from __future__ import annotations

import unittest
from datetime import date

from health_monitor.application.service import HealthMonitorService
from health_monitor.domain.nutrients import Nutrients


class AgentChatHarnessTest(unittest.TestCase):
    def make_service_with_entry(self) -> tuple[HealthMonitorService, str, str]:
        service = HealthMonitorService()
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
        return service, person.id, entry.id

    def test_day_question_is_grounded_in_summary_and_entry_citations(self) -> None:
        service, person_id, entry_id = self.make_service_with_entry()

        response = service.chat(
            person_id=person_id,
            message="Why was 2026-07-01 high in calories?",
            today=date(2026, 7, 2),
            agent_settings={"model_profile": "deterministic-test"},
        )

        self.assertEqual(response.behavior_label, "explain_day")
        self.assertIn("315", response.message)
        self.assertIn("Queijo Minas", response.message)
        self.assertEqual(response.proposal_id, None)
        self.assertIn(
            {"record_type": "diary_entry", "record_id": entry_id},
            response.citations,
        )

    def test_chat_says_when_requested_day_has_insufficient_data(self) -> None:
        service = HealthMonitorService()
        household = service.create_household(name="Casa")
        person = service.create_person(
            household_id=household.id,
            name="Gabriel",
            timezone="America/Sao_Paulo",
        )

        response = service.chat(
            person_id=person.id,
            message="Why was 2026-07-01 high in calories?",
            today=date(2026, 7, 2),
        )

        self.assertEqual(response.behavior_label, "answer_question")
        self.assertIn("not enough diary data", response.message.casefold())
        self.assertEqual(response.citations, ())

    def test_chat_correction_drafts_proposal_without_mutating_until_confirmation(self) -> None:
        service, person_id, entry_id = self.make_service_with_entry()

        response = service.chat(
            person_id=person_id,
            message="Change queijo on 2026-07-01 to 50g",
            today=date(2026, 7, 2),
        )
        before = service.day_summary(person_id, date(2026, 7, 1))
        proposal = service.get_proposal(response.proposal_id or "")

        self.assertEqual(response.behavior_label, "draft_diary_correction")
        self.assertEqual(proposal.proposal_type, "diary_entry_update")
        self.assertEqual(proposal.payload["entry_id"], entry_id)
        self.assertEqual(proposal.payload["quantity_g"], 50)
        self.assertEqual(before.totals.rounded(), Nutrients(315, 23, 2.6, 23.5))

        applied = service.confirm_proposal(proposal.id)
        after = service.day_summary(person_id, date(2026, 7, 1))

        self.assertEqual(applied.status, "applied")
        self.assertEqual(after.totals.rounded(), Nutrients(157.5, 11.5, 1.3, 11.75))


if __name__ == "__main__":
    unittest.main()
