from __future__ import annotations

import unittest
from datetime import date

from health_monitor.application.service import HealthMonitorService


class ReviewNotesTest(unittest.TestCase):
    def make_service(self) -> tuple[HealthMonitorService, str]:
        service = HealthMonitorService()
        household = service.create_household(name="Casa")
        person = service.create_person(
            household_id=household.id,
            name="Gabriel",
            timezone="America/Sao_Paulo",
        )
        return service, person.id

    def test_chat_drafts_review_note_without_mutating_until_confirmation(self) -> None:
        service, person_id = self.make_service()

        response = service.chat(
            person_id=person_id,
            message=(
                "Save review note for 2026-07-01 to 2026-07-07: "
                "Social dinners made adherence harder than weekday meals."
            ),
            today=date(2026, 7, 8),
            agent_settings={"model_profile": "deterministic-test"},
        )

        self.assertEqual(response.behavior_label, "draft_review_note")
        self.assertEqual(service.review_notes_for_person(person_id), ())

        proposal = service.get_proposal(response.proposal_id or "")
        self.assertEqual(proposal.proposal_type, "review_note")
        self.assertEqual(proposal.payload["starts_on"], "2026-07-01")
        self.assertEqual(proposal.payload["ends_on"], "2026-07-07")
        self.assertIn("Social dinners", proposal.payload["body"])
        tool_calls = service.agent_tool_calls_for_run(response.run_id)
        self.assertEqual(
            [(call.tool_name, call.status) for call in tool_calls],
            [("draft_review_note", "completed")],
        )
        self.assertEqual(tool_calls[0].source_record_ids, (proposal.id,))
        self.assertIn("2026-07-01 to 2026-07-07", tool_calls[0].input_summary)

        applied = service.confirm_proposal(proposal.id)
        notes = service.review_notes_for_person(person_id)

        self.assertEqual(applied.status, "applied")
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0].starts_on, date(2026, 7, 1))
        self.assertEqual(notes[0].ends_on, date(2026, 7, 7))
        self.assertEqual(notes[0].source, "agent_chat")
        self.assertEqual(notes[0].source_proposal_id, proposal.id)
        self.assertEqual(notes[0].source_agent_run_id, response.run_id)
        self.assertIn("Social dinners", notes[0].body)

    def test_review_notes_survive_export_import(self) -> None:
        source, person_id = self.make_service()
        response = source.chat(
            person_id=person_id,
            message="Save review note: Need to watch weekend snacks.",
            today=date(2026, 7, 8),
        )
        source.confirm_proposal(response.proposal_id or "")

        exported = source.export_data()
        target = HealthMonitorService()
        imported = target.import_data(exported)
        notes = target.review_notes_for_person(person_id)

        self.assertEqual(imported["review_notes"], 1)
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0].starts_on, None)
        self.assertIn("weekend snacks", notes[0].body)


if __name__ == "__main__":
    unittest.main()
