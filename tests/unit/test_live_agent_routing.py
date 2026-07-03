from __future__ import annotations

import unittest
from unittest.mock import patch

from health_monitor.agent.runtime import AgentRuntimeResponse, PydanticAIUnavailable
from health_monitor.application.service import HealthMonitorService
from health_monitor.domain.nutrients import Nutrients


class FakeDraftingAgent:
    def __init__(self, *, model_name: str, ollama_base_url: str) -> None:
        self.model_name = model_name
        self.ollama_base_url = ollama_base_url

    def draft_text_meal(self, *, deps, logged_at_local: str, text: str) -> AgentRuntimeResponse:
        proposal = deps.service.propose_text_meal(
            person_id=deps.person_id,
            logged_at_local=logged_at_local,
            text=text,
            agent_settings={**deps.settings, "agent_runtime": "deterministic"},
        )
        return AgentRuntimeResponse(
            message=proposal.summary,
            behavior_label="proposal_draft",
            proposal_id=proposal.id,
            output_type="proposal_draft",
        )


class FailingAgent:
    def __init__(self, *, model_name: str, ollama_base_url: str) -> None:
        pass

    def draft_text_meal(self, *, deps, logged_at_local: str, text: str) -> AgentRuntimeResponse:
        raise PydanticAIUnavailable("missing dependency")


class LiveAgentRoutingTest(unittest.TestCase):
    def make_service(self, *, require_model: bool = True) -> tuple[HealthMonitorService, str]:
        service = HealthMonitorService(
            agent_runtime="pydantic-ai",
            agent_model="ornith:9b",
            require_model=require_model,
            model_health_checker=lambda: True,
        )
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
            nutrients_per_100g=Nutrients(315, 23, 2.6, 23.5, sodium_mg=620),
            source="label_scan",
            aliases=["queijo"],
        )
        return service, person.id

    def test_pydantic_text_meal_path_links_live_run_to_proposal(self) -> None:
        service, person_id = self.make_service()

        with patch("health_monitor.application.service.PydanticAINutritionAgent", FakeDraftingAgent):
            proposal = service.propose_text_meal(
                person_id=person_id,
                logged_at_local="2026-07-02T10:00:00",
                text="50g queijo",
            )

        run = service.get_agent_run(proposal.source_agent_run_id or "")
        self.assertEqual(run.runtime, "pydantic-ai")
        self.assertEqual(run.model_name, "ornith:9b")
        self.assertEqual(run.status, "proposal_created")
        self.assertEqual(run.proposal_id, proposal.id)
        self.assertIsNone(run.fallback_reason)
        self.assertEqual(proposal.payload["live_agent_orchestration"]["model_name"], "ornith:9b")
        self.assertTrue(proposal.payload["live_agent_orchestration"]["deterministic_source_agent_run_id"])
        self.assertEqual(service.day_summary(person_id, proposal.entries[0].logged_at.date()).totals, Nutrients())

    def test_pydantic_text_meal_failure_records_fallback_reason(self) -> None:
        # Deterministic fallback only exists when require_model is disabled.
        service, person_id = self.make_service(require_model=False)

        with patch("health_monitor.application.service.PydanticAINutritionAgent", FailingAgent):
            proposal = service.propose_text_meal(
                person_id=person_id,
                logged_at_local="2026-07-02T10:00:00",
                text="50g queijo",
            )

        run = service.get_agent_run(proposal.source_agent_run_id or "")
        self.assertEqual(run.runtime, "pydantic-ai")
        self.assertEqual(run.status, "proposal_created")
        self.assertIn("pydantic_ai unavailable", run.fallback_reason or "")
        self.assertEqual(run.tool_loop_count, 2)


if __name__ == "__main__":
    unittest.main()
