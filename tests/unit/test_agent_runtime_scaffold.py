from __future__ import annotations

import unittest
from datetime import date

from health_monitor.agent.runtime import (
    AgentAnswerOutput,
    AgentClarificationRequestOutput,
    AgentDeps,
    AgentLookupEstimateExplanation,
    AgentProposalDraftOutput,
    normalize_ollama_base_url,
)
from health_monitor.application.service import HealthMonitorService


class AgentRuntimeScaffoldTest(unittest.TestCase):
    def test_agent_deps_capture_runtime_context_without_api_keys(self) -> None:
        service = HealthMonitorService(agent_runtime="pydantic-ai", agent_model="qwen3")
        household = service.create_household(name="Casa")
        person = service.create_person(
            household_id=household.id,
            name="Gabriel",
            timezone="America/Sao_Paulo",
        )

        deps = AgentDeps(
            service=service,
            person_id=person.id,
            household_id=household.id,
            today=date(2026, 7, 2),
            settings={"agent_runtime": "pydantic-ai", "model_name": "qwen3"},
            source_config={"openfoodfacts_enabled": True},
        )

        self.assertEqual(deps.person_id, person.id)
        self.assertNotIn("api_key", deps.source_config)

    def test_ollama_base_url_is_normalized_for_pydantic_ai_provider(self) -> None:
        self.assertEqual(
            normalize_ollama_base_url("http://localhost:11434"),
            "http://localhost:11434/v1",
        )
        self.assertEqual(
            normalize_ollama_base_url("https://ollama.com/v1"),
            "https://ollama.com/v1",
        )

    def test_structured_output_contracts_are_explicit(self) -> None:
        answer = AgentAnswerOutput(message="Grounded answer")
        proposal = AgentProposalDraftOutput(
            proposal_id="proposal_1",
            proposal_type="diary_entry_update",
            proposal_status="draft",
            summary="Draft correction",
        )
        clarification = AgentClarificationRequestOutput(
            question="Which yogurt?",
            missing_fields=("food_version_id",),
        )
        lookup = AgentLookupEstimateExplanation(
            source_name="Open Food Facts",
            source_type="external_database",
            source_id="789",
            confidence=0.72,
        )

        self.assertEqual(answer.message, "Grounded answer")
        self.assertFalse(proposal.mutation_applied)
        self.assertEqual(clarification.missing_fields, ("food_version_id",))
        self.assertEqual(lookup.source_name, "Open Food Facts")


if __name__ == "__main__":
    unittest.main()
