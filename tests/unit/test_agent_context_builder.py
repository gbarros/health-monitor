from __future__ import annotations

import unittest
from datetime import date, datetime, timedelta, timezone

from health_monitor.application.service import AgentChatTurn, HealthMonitorService
from health_monitor.domain.nutrients import Nutrients


class AgentContextBuilderTest(unittest.TestCase):
    def test_builds_pruned_multi_turn_context_for_model_chat(self) -> None:
        service = HealthMonitorService()
        household = service.create_household(name="Casa")
        person = service.create_person(
            household_id=household.id,
            name="Gabriel",
            timezone="America/Sao_Paulo",
            activity_level="moderate",
        )
        service.create_goal_profile(
            person_id=person.id,
            starts_on=date(2026, 7, 1),
            targets=Nutrients(calories_kcal=2000, protein_g=150, carbs_g=200, fat_g=60),
            notes="cut leve",
        )
        _, version = service.create_food_with_version(
            household_id=household.id,
            name="Iogurte",
            brand="Teste",
            version_label="rótulo",
            nutrients_per_100g=Nutrients(calories_kcal=80, protein_g=10, carbs_g=7, fat_g=1),
            source="label_scan",
        )
        today = date(2026, 7, 14)
        for offset in range(14):
            day = today - timedelta(days=offset)
            service.log_diary_entry(
                person_id=person.id,
                logged_at_local=f"{day.isoformat()}T09:00:00",
                food_version_id=version.id,
                quantity_g=100 + offset,
                source="manual",
            )
        proposal = service.draft_range_estimate_proposal(
            person_id=person.id,
            day=today,
            label="almoço fora",
            low_kcal=600,
            high_kcal=900,
            meal_type="lunch",
        )
        for index in range(12):
            turn = AgentChatTurn(
                id=f"turn-{index}",
                person_id=person.id,
                agent_run_id=f"run-{index}",
                user_message=f"user {index}",
                assistant_message=f"assistant {index}",
                behavior_label="answer_question",
                created_at=datetime(2026, 7, 14, index, tzinfo=timezone.utc),
            )
            service.chat_turns[turn.id] = turn

        context = service._build_agent_context(person.id, today)

        self.assertEqual(context["person"]["name"], "Gabriel")
        self.assertEqual(context["active_goal"]["targets"]["calories_kcal"], 2000)
        self.assertEqual([turn["user"] for turn in context["recent_chat_turns"]], [f"user {index}" for index in range(2, 12)])
        self.assertEqual(context["open_proposals"][0]["id"], proposal.id)
        self.assertEqual(len(context["day_summaries"]), 14)
        self.assertIn("foods", context["day_summaries"][0])
        self.assertNotIn("meals", context["day_summaries"][0])
        self.assertIn("meals", context["day_summaries"][-1])
        self.assertEqual(context["day_summaries"][-1]["entries_count"], 1)
        prompt = service._agent_context_message(person.id, today, "almoço foi arroz e feijão")
        self.assertTrue(prompt.startswith("Agent context JSON:\n"))
        self.assertIn("User message:\nalmoço foi arroz e feijão", prompt)


if __name__ == "__main__":
    unittest.main()
