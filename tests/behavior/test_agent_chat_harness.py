from __future__ import annotations

import unittest
from datetime import date

from health_monitor.application.service import HealthMonitorService
from health_monitor.domain.nutrients import Nutrients


class AgentChatHarnessTest(unittest.TestCase):
    def make_service_with_entry(self) -> tuple[HealthMonitorService, str, str]:
        service = HealthMonitorService(model_health_checker=lambda: True)
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
        tool_calls = service.agent_tool_calls_for_run(response.run_id)
        self.assertEqual(
            [(call.tool_name, call.status) for call in tool_calls],
            [("summarize_day", "completed")],
        )
        self.assertIn("2026-07-01", tool_calls[0].input_summary)
        self.assertIn("315", tool_calls[0].output_summary)
        self.assertEqual(tool_calls[0].source_record_ids, (entry_id,))

    def test_chat_turn_is_stored_separately_from_durable_nutrition_records(self) -> None:
        service, person_id, entry_id = self.make_service_with_entry()

        response = service.chat(
            person_id=person_id,
            message="Why was 2026-07-01 high in calories?",
            today=date(2026, 7, 2),
        )
        turns = service.chat_turns_for_person(person_id)

        self.assertEqual(len(turns), 1)
        self.assertEqual(turns[0].agent_run_id, response.run_id)
        self.assertEqual(turns[0].user_message, "Why was 2026-07-01 high in calories?")
        self.assertEqual(turns[0].assistant_message, response.message)
        self.assertEqual(turns[0].behavior_label, "explain_day")
        self.assertEqual(turns[0].proposal_id, None)
        self.assertIn(
            {"record_type": "diary_entry", "record_id": entry_id},
            turns[0].citations,
        )
        self.assertEqual(service.day_summary(person_id, date(2026, 7, 1)).totals.rounded(), Nutrients(315, 23, 2.6, 23.5))

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
        tool_calls = service.agent_tool_calls_for_run(response.run_id)
        self.assertEqual(
            [(call.tool_name, call.status) for call in tool_calls],
            [("summarize_day", "completed")],
        )
        self.assertIn("0 entries", tool_calls[0].output_summary)

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
        tool_calls = service.agent_tool_calls_for_run(response.run_id)
        self.assertEqual(
            [(call.tool_name, call.status) for call in tool_calls],
            [
                ("find_diary_entries", "completed"),
                ("draft_diary_correction", "completed"),
            ],
        )
        self.assertEqual(tool_calls[0].source_record_ids, (entry_id,))
        self.assertEqual(tool_calls[1].source_record_ids, (entry_id, proposal.id))

        applied = service.confirm_proposal(proposal.id)
        after = service.day_summary(person_id, date(2026, 7, 1))

        self.assertEqual(applied.status, "applied")
        self.assertEqual(after.totals.rounded(), Nutrients(157.5, 11.5, 1.3, 11.75))

    def test_chat_routes_meal_log_to_text_meal_proposal(self) -> None:
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
            nutrients_per_100g=Nutrients(130, 2.7, 28, 0.3),
            source="reference",
            aliases=["arroz"],
        )

        response = service.chat(
            person_id=person.id,
            message="Almoço:\n150g arroz",
            today=date(2026, 7, 2),
            agent_settings={"external_lookup": False},
        )
        proposal = service.get_proposal(response.proposal_id or "")

        self.assertEqual(response.behavior_label, "draft_text_meal")
        self.assertEqual(proposal.status, "draft")
        self.assertEqual(proposal.entries[0].meal_type, "lunch")
        self.assertEqual(proposal.entries[0].quantity_g, 150)
        self.assertEqual(service.day_summary(person.id, date(2026, 7, 2)).totals, Nutrients())

    def test_chat_routes_follow_up_meal_patch_to_open_proposal(self) -> None:
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
        first = service.chat(
            person_id=person.id,
            message="Almoço:\n150g arroz",
            today=date(2026, 7, 2),
            agent_settings={"external_lookup": False},
        )

        second = service.chat(
            person_id=person.id,
            message="esqueci 113g de frango",
            today=date(2026, 7, 2),
            agent_settings={"external_lookup": False},
        )
        original = service.get_proposal(first.proposal_id or "")
        amended = service.get_proposal(second.proposal_id or "")

        self.assertEqual(original.status, "superseded")
        self.assertEqual(second.behavior_label, "draft_text_meal")
        self.assertEqual(len(amended.entries), 2)
        self.assertEqual(amended.payload["amended_from_proposal_id"], original.id)

    def test_chat_routes_party_kcal_range_and_refinement_to_midpoint_entry(self) -> None:
        service = HealthMonitorService()
        household = service.create_household(name="Casa")
        person = service.create_person(
            household_id=household.id,
            name="Gabriel",
            timezone="America/Sao_Paulo",
        )

        first = service.chat(
            person_id=person.id,
            message="Festa: 800-1200 kcal",
            today=date(2026, 7, 2),
        )
        refined = service.chat(
            person_id=person.id,
            message="Festa: 900-1100 kcal",
            today=date(2026, 7, 2),
        )
        first_proposal = service.get_proposal(first.proposal_id or "")
        refined_proposal = service.get_proposal(refined.proposal_id or "")

        self.assertEqual(first.behavior_label, "draft_range_estimate")
        self.assertEqual(refined.behavior_label, "draft_range_estimate")
        self.assertEqual(first_proposal.status, "superseded")
        self.assertEqual(refined_proposal.status, "draft")
        self.assertEqual(refined_proposal.payload["amended_from_proposal_id"], first_proposal.id)
        self.assertEqual(
            refined_proposal.payload["estimate_range"],
            {"low_kcal": 900.0, "high_kcal": 1100.0, "midpoint_kcal": 1000.0},
        )
        self.assertEqual(refined_proposal.totals.rounded(), Nutrients(1000))
        self.assertEqual(service.day_summary(person.id, date(2026, 7, 2)).totals, Nutrients())

        applied = service.confirm_proposal(refined_proposal.id)
        summary = service.day_summary(person.id, date(2026, 7, 2))
        entry = summary.meals["lunch"][0]

        self.assertEqual(applied.status, "applied")
        self.assertEqual(summary.totals.rounded(), Nutrients(1000))
        self.assertEqual(entry.food_name, "Festa")
        self.assertEqual(entry.evidence_status, "range_estimate")
        self.assertEqual(entry.confidence, 0.45)

    def test_chat_routes_weight_message_to_weight_entry(self) -> None:
        service = HealthMonitorService()
        household = service.create_household(name="Casa")
        person = service.create_person(
            household_id=household.id,
            name="Gabriel",
            timezone="America/Sao_Paulo",
        )

        response = service.chat(
            person_id=person.id,
            message="amanheci com 96,3kgs",
            today=date(2026, 7, 2),
        )
        trend = service.weight_trend(person_id=person.id)

        self.assertEqual(response.behavior_label, "log_weight")
        self.assertIsNone(response.proposal_id)
        self.assertEqual(trend.latest_kg, 96.3)
        self.assertIn("96.3 kg", response.message)

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
        first_weight = service.log_weight(
            person_id=person_id,
            measured_at_local="2026-07-01T08:00:00",
            weight_kg=91.2,
            note="start",
            source="manual",
        )
        second_weight = service.log_weight(
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
        tool_calls = service.agent_tool_calls_for_run(response.run_id)
        self.assertEqual(
            [(call.tool_name, call.status) for call in tool_calls],
            [("summarize_week", "completed")],
        )
        self.assertIn("2026-07-01 to 2026-07-07", tool_calls[0].input_summary)
        self.assertEqual(
            set(tool_calls[0].source_record_ids),
            {first_entry_id, second.id, first_weight.id, second_weight.id},
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
        tool_calls = service.agent_tool_calls_for_run(response.run_id)
        self.assertEqual(
            [(call.tool_name, call.status) for call in tool_calls],
            [("analyze_micronutrients", "completed")],
        )
        self.assertEqual(tool_calls[0].source_record_ids, (entry_id,))

    def test_chat_can_draft_goal_profile_update_without_immediate_mutation(self) -> None:
        service, person_id, _ = self.make_service_with_entry()
        service.create_goal_profile(
            person_id=person_id,
            starts_on=date(2026, 7, 1),
            targets=Nutrients(2000, 150, 180, 70, 30, 2300),
            notes="initial",
        )

        response = service.chat(
            person_id=person_id,
            message="Change my goal calories to 1800, protein to 160g, carbs to 140g, fat to 60g, fiber to 35g, sodium to 2100mg starting 2026-07-10",
            today=date(2026, 7, 2),
        )

        self.assertEqual(response.behavior_label, "draft_goal_profile")
        self.assertIsNotNone(response.proposal_id)
        proposal = service.get_proposal(response.proposal_id or "")
        self.assertEqual(proposal.proposal_type, "goal_profile")
        self.assertEqual(proposal.status, "draft")
        self.assertEqual(
            service.active_goal_profile(person_id=person_id, day=date(2026, 7, 10)).targets.calories_kcal,
            2000,
        )

        service.confirm_proposal(proposal.id)

        updated = service.active_goal_profile(person_id=person_id, day=date(2026, 7, 10))
        self.assertIsNotNone(updated)
        self.assertEqual(updated.targets.rounded(), Nutrients(1800, 160, 140, 60, 35, 2100))

    def test_chat_can_draft_profile_update_without_immediate_mutation(self) -> None:
        service, person_id, _ = self.make_service_with_entry()

        response = service.chat(
            person_id=person_id,
            message="Update my profile height to 181 cm",
            today=date(2026, 7, 2),
        )

        self.assertEqual(response.behavior_label, "draft_profile_update")
        self.assertIsNotNone(response.proposal_id)
        proposal = service.get_proposal(response.proposal_id or "")
        self.assertEqual(proposal.proposal_type, "profile_update")
        self.assertEqual(proposal.payload["height_cm"], 181)
        self.assertIsNone(service.people[person_id].height_cm)

        service.confirm_proposal(proposal.id)

        self.assertEqual(service.people[person_id].height_cm, 181)

    def test_chat_explains_profile_and_goal_changes_are_proposal_gated(self) -> None:
        service, person_id, _ = self.make_service_with_entry()

        response = service.chat(
            person_id=person_id,
            message="Can you alter my profile and goals?",
            today=date(2026, 7, 2),
            agent_settings={"agent_runtime": "pydantic-ai", "model_profile": "qwen3.6:latest"},
        )

        self.assertEqual(response.behavior_label, "answer_profile_goal_capabilities")
        self.assertIsNone(response.proposal_id)
        self.assertIn("proposal", response.message.casefold())
        self.assertIn("profile", response.message.casefold())
        self.assertIn("goal", response.message.casefold())

    def test_chat_answers_whether_new_food_label_is_default_and_used(self) -> None:
        service = HealthMonitorService()
        household = service.create_household(name="Casa")
        person = service.create_person(
            household_id=household.id,
            name="Gabriel",
            timezone="America/Sao_Paulo",
        )
        _, old_version = service.create_food_with_version(
            household_id=household.id,
            name="Iogurte Batavo Protein",
            brand="Batavo",
            version_label="old label",
            nutrients_per_100g=Nutrients(80, 8, 7, 2),
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
            set_as_default=True,
        )
        applied = service.confirm_proposal(proposal.id)
        new_version_id = applied.applied_record_ids[1]
        new_entry = service.log_diary_entry(
            person_id=person.id,
            logged_at_local="2026-07-02T10:00:00",
            food_version_id=new_version_id,
            quantity_g=170,
            source="manual",
        )

        response = service.chat(
            person_id=person.id,
            message="Did we start using the new Iogurte Batavo label?",
            today=date(2026, 7, 3),
        )

        self.assertEqual(response.behavior_label, "explain_food_version_use")
        self.assertIn("current default", response.message.casefold())
        self.assertIn("2026-07-02", response.message)
        self.assertIn("old label", response.message)
        self.assertIn("label scan", response.message)
        self.assertIn(
            {"record_type": "food_version", "record_id": old_version.id},
            response.citations,
        )
        self.assertIn(
            {"record_type": "food_version", "record_id": new_version_id},
            response.citations,
        )
        self.assertIn(
            {"record_type": "diary_entry", "record_id": old_entry.id},
            response.citations,
        )
        self.assertIn(
            {"record_type": "diary_entry", "record_id": new_entry.id},
            response.citations,
        )
        tool_calls = service.agent_tool_calls_for_run(response.run_id)
        self.assertEqual(
            [(call.tool_name, call.status) for call in tool_calls],
            [("inspect_food_version_usage", "completed")],
        )
        self.assertEqual(
            set(tool_calls[0].source_record_ids),
            {old_version.id, new_version_id, old_entry.id, new_entry.id},
        )


if __name__ == "__main__":
    unittest.main()
