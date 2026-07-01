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
            agent_settings={
                "model_profile": "deterministic-test",
                "effort": "medium",
                "max_tool_loops": 4,
            },
        )
        run = service.get_agent_run(response.run_id)

        self.assertEqual(response.behavior_label, "explain_day")
        self.assertEqual(run.settings["effort"], "medium")
        self.assertEqual(run.settings["max_tool_loops"], 4)
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

    def test_week_question_is_grounded_in_week_summary_and_record_citations(self) -> None:
        service, person_id, first_entry_id = self.make_service_with_entry()
        version_id = service.diary.entries[first_entry_id].food_version_id
        second = service.log_diary_entry(
            person_id=person_id,
            logged_at_local="2026-07-02T10:00:00",
            food_version_id=version_id,
            quantity_g=50,
            source="manual",
        )
        service.create_goal_profile(
            person_id=person_id,
            starts_on=date(2026, 7, 1),
            targets=Nutrients(2000, 150, 180, 70),
        )
        service.log_weight(
            person_id=person_id,
            measured_at_local="2026-07-01T08:00:00",
            weight_kg=91.2,
            note="start",
            source="manual",
        )
        service.log_weight(
            person_id=person_id,
            measured_at_local="2026-07-07T08:00:00",
            weight_kg=90.4,
            note="week end",
            source="manual",
        )

        response = service.chat(
            person_id=person_id,
            message="Explain the week 2026-07-01 to 2026-07-07",
            today=date(2026, 7, 8),
        )

        self.assertEqual(response.behavior_label, "explain_week")
        self.assertIn("472.5 kcal", response.message)
        self.assertIn("67.5 kcal/day", response.message)
        self.assertIn("highest calorie day was 2026-07-01", response.message)
        self.assertIn("Weight changed -0.8 kg", response.message)
        self.assertIn(
            {"record_type": "diary_entry", "record_id": first_entry_id},
            response.citations,
        )
        self.assertIn(
            {"record_type": "diary_entry", "record_id": second.id},
            response.citations,
        )

    def test_micronutrient_question_states_uncertainty_and_data_needed(self) -> None:
        service, person_id, entry_id = self.make_service_with_entry()

        response = service.chat(
            person_id=person_id,
            message="What micronutrients look consistently low this week?",
            today=date(2026, 7, 2),
        )

        self.assertEqual(response.behavior_label, "micronutrient_analysis")
        self.assertIn("limited", response.message.casefold())
        self.assertIn("fiber", response.message.casefold())
        self.assertIn("sodium", response.message.casefold())
        self.assertIn("vitamins and minerals are not stored", response.message.casefold())
        self.assertIn("not a diagnosis", response.message.casefold())
        self.assertIn("attach labels", response.message.casefold())
        self.assertIn(
            {"record_type": "diary_entry", "record_id": entry_id},
            response.citations,
        )


if __name__ == "__main__":
    unittest.main()
