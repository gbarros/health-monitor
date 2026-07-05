from __future__ import annotations

import unittest
from datetime import date
from typing import Any
from unittest.mock import patch

from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from health_monitor.agent.runtime import AgentDeps, AgentRuntimeResponse, PydanticAINutritionAgent, PydanticAIUnavailable
from health_monitor.application.service import HealthMonitorService
from health_monitor.domain.nutrients import Nutrients


class FakeDraftingAgent:
    def __init__(self, *, model_name: str, ollama_base_url: str) -> None:
        self.model_name = model_name
        self.ollama_base_url = ollama_base_url

    def answer(self, *, deps, message: str) -> AgentRuntimeResponse:
        proposal = deps.service.draft_structured_meal_proposal(
            person_id=deps.person_id,
            day=deps.today,
            time_text="10:00",
            meal_type="breakfast",
            items=[{"phrase": "queijo", "quantity_g": 50}],
            source_text=message,
            agent_settings=deps.settings,
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

    def answer(self, *, deps, message: str) -> AgentRuntimeResponse:
        raise PydanticAIUnavailable("missing dependency")


class FakeOnboardingAgent:
    last_deps_household_id: str | None = None
    last_message: str | None = None

    def __init__(self, *, model_name: str, ollama_base_url: str) -> None:
        self.model_name = model_name
        self.ollama_base_url = ollama_base_url

    def onboarding(self, *, deps, message: str, session_id: str) -> AgentRuntimeResponse:
        FakeOnboardingAgent.last_deps_household_id = deps.household_id
        FakeOnboardingAgent.last_message = message
        proposal = deps.service.draft_onboarding_proposal(
            session_id=session_id,
            household_name="Casa",
            household_id=None,
            person={"name": "Gabriel", "timezone": "America/Sao_Paulo"},
            targets={"calories_kcal": 2000, "protein_g": 150},
            source_text=message,
        )
        return AgentRuntimeResponse(
            message="Revisei seus dados e deixei uma proposta inicial pronta.",
            behavior_label="proposal_draft",
            proposal_id=proposal.id,
            output_type="proposal_draft",
        )


class LiveAgentRoutingTest(unittest.TestCase):
    def make_service(self, *, require_model: bool = True) -> tuple[HealthMonitorService, str, str]:
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
        return service, person.id, household.id

    def test_function_model_chat_harness_calls_real_draft_meal_tool(self) -> None:
        service, person_id, household_id = self.make_service()
        requested_tools: list[str] = []

        def scripted_model(messages: list[Any], agent_info: AgentInfo) -> ModelResponse:
            requested_tools[:] = [tool.name for tool in agent_info.function_tools]
            proposal_id = proposal_id_from_tool_returns(messages, "draft_meal_proposal")
            if proposal_id is None:
                return ModelResponse(
                    parts=[
                        ToolCallPart(
                            "draft_meal_proposal",
                            {
                                "items": [{"phrase": "queijo", "quantity_g": 50}],
                                "day": "2026-07-02",
                                "time": "10:00",
                                "meal_type": "breakfast",
                                "source_text": "Café: 50g queijo",
                            },
                        )
                    ]
                )
            return ModelResponse(
                parts=[
                    TextPart(
                        (
                            '{"output_type":"proposal_draft",'
                            f'"proposal_id":"{proposal_id}",'
                            '"summary":"Proposta de café pronta."}'
                        )
                    )
                ]
            )

        agent = PydanticAINutritionAgent(
            model_name="function-test",
            ollama_base_url="http://127.0.0.1:11434",
            model=FunctionModel(scripted_model),
        )

        response = agent.answer(
            deps=AgentDeps(
                service=service,
                person_id=person_id,
                household_id=household_id,
                today=date(2026, 7, 2),
                settings={"agent_runtime": "pydantic-ai"},
                source_config={
                    "openfoodfacts_enabled": False,
                    "research_lookup_enabled": False,
                    "ocr_enabled": False,
                },
            ),
            message="Café: 50g queijo",
        )

        self.assertIn("draft_meal_proposal", requested_tools)
        self.assertEqual(response.proposal_id, "proposal_1")
        self.assertEqual(response.behavior_label, "proposal_draft")
        proposal = service.get_proposal(response.proposal_id or "")
        self.assertEqual(proposal.entries[0].quantity_g, 50)
        self.assertEqual(proposal.entries[0].meal_type, "breakfast")

    def test_function_model_chat_harness_can_ask_clarifying_question_without_proposal(self) -> None:
        service, person_id, household_id = self.make_service()
        requested_tools: list[str] = []

        def scripted_model(_: list[Any], agent_info: AgentInfo) -> ModelResponse:
            requested_tools[:] = [tool.name for tool in agent_info.function_tools]
            return ModelResponse(
                parts=[
                    TextPart(
                        (
                            '{"output_type":"clarification_request",'
                            '"question":"Quantos gramas de queijo você comeu?",'
                            '"missing_fields":["quantity_g"]}'
                        )
                    )
                ]
            )

        response = scripted_agent_answer(
            service=service,
            person_id=person_id,
            household_id=household_id,
            scripted_model=scripted_model,
            message="Comi queijo.",
        )

        self.assertIn("draft_meal_proposal", requested_tools)
        self.assertEqual(response.behavior_label, "clarification_request")
        self.assertEqual(response.message, "Quantos gramas de queijo você comeu?")
        self.assertIsNone(response.proposal_id)
        self.assertEqual(service.proposals.proposals, {})

    def test_function_model_chat_harness_calls_real_amend_meal_tool(self) -> None:
        service, person_id, household_id = self.make_service()
        original = service.draft_structured_meal_proposal(
            person_id=person_id,
            day=date(2026, 7, 2),
            time_text="12:30",
            meal_type="lunch",
            items=[{"phrase": "arroz", "quantity_g": 150}],
            agent_settings={"external_lookup": False},
            source_text="model extracted rice",
        )
        requested_tools: list[str] = []

        def scripted_model(messages: list[Any], agent_info: AgentInfo) -> ModelResponse:
            requested_tools[:] = [tool.name for tool in agent_info.function_tools]
            proposal_id = proposal_id_from_tool_returns(messages, "amend_meal_proposal")
            if proposal_id is None:
                return ModelResponse(
                    parts=[
                        ToolCallPart(
                            "amend_meal_proposal",
                            {
                                "proposal_id": original.id,
                                "add": [{"phrase": "frango", "quantity_g": 113}],
                                "remove": [],
                                "set_quantity": [{"phrase": "arroz", "quantity_g": 100}],
                                "source_text": "Esqueci o frango e eram 100g de arroz.",
                            },
                        )
                    ]
                )
            return ModelResponse(
                parts=[
                    TextPart(
                        (
                            '{"output_type":"proposal_draft",'
                            f'"proposal_id":"{proposal_id}",'
                            '"summary":"Atualizei a proposta do almoço."}'
                        )
                    )
                ]
            )

        response = scripted_agent_answer(
            service=service,
            person_id=person_id,
            household_id=household_id,
            scripted_model=scripted_model,
            message="Esqueci o frango e eram 100g de arroz.",
        )

        self.assertIn("amend_meal_proposal", requested_tools)
        self.assertEqual(response.proposal_id, "proposal_2")
        amended = service.get_proposal(response.proposal_id or "")
        self.assertEqual(service.get_proposal(original.id).status, "superseded")
        self.assertEqual(amended.payload["amended_from_proposal_id"], original.id)
        self.assertEqual([entry.quantity_g for entry in amended.entries], [100, 113])

    def test_pydantic_chat_path_links_live_run_to_structured_meal_proposal(self) -> None:
        service, person_id, _ = self.make_service()

        with patch("health_monitor.application.service.PydanticAINutritionAgent", FakeDraftingAgent):
            response = service.chat(
                person_id=person_id,
                today=date(2026, 7, 2),
                message="Café: 50g queijo",
            )

        self.assertIsNotNone(response.proposal_id)
        proposal = service.get_proposal(response.proposal_id or "")
        run = service.get_agent_run(response.run_id)
        self.assertEqual(run.runtime, "pydantic-ai")
        self.assertEqual(run.model_name, "ornith:9b")
        self.assertEqual(run.status, "proposal_created")
        self.assertEqual(run.proposal_id, proposal.id)
        self.assertIsNone(run.fallback_reason)
        self.assertEqual(proposal.source_agent_run_id, response.run_id)
        self.assertEqual(proposal.payload["live_agent_orchestration"]["model_name"], "ornith:9b")
        self.assertTrue(proposal.payload["live_agent_orchestration"]["tool_source_agent_run_id"])
        self.assertEqual(proposal.entries[0].quantity_g, 50)
        self.assertEqual(service.day_summary(person_id, proposal.entries[0].logged_at.date()).totals, Nutrients())

    def test_pydantic_chat_failure_records_fallback_reason_without_deterministic_proposal(self) -> None:
        # Deterministic fallback only exists when require_model is disabled.
        service, person_id, _ = self.make_service(require_model=False)

        with patch("health_monitor.application.service.PydanticAINutritionAgent", FailingAgent):
            response = service.chat(
                person_id=person_id,
                today=date(2026, 7, 2),
                message="50g queijo",
            )

        run = service.get_agent_run(response.run_id)
        self.assertEqual(run.runtime, "pydantic-ai")
        self.assertEqual(run.status, "answered")
        self.assertIn("pydantic_ai unavailable", run.fallback_reason or "")
        self.assertIsNone(response.proposal_id)
        self.assertEqual(service.proposals.proposals, {})

    def test_pydantic_onboarding_chat_can_create_profile_setup_proposal(self) -> None:
        service = HealthMonitorService(
            agent_runtime="pydantic-ai",
            agent_model="ornith:9b",
            require_model=True,
            model_health_checker=lambda: True,
        )

        with patch("health_monitor.application.service.PydanticAINutritionAgent", FakeOnboardingAgent):
            turn = service.onboarding_chat(
                session_id="session-1",
                message="Oi, sou Gabriel. Quero 2000 kcal e 150g de proteína.",
            )

        self.assertEqual(turn.proposal_id, "proposal_1")
        self.assertEqual(turn.assistant_message, "Revisei seus dados e deixei uma proposta inicial pronta.")
        proposal = service.get_proposal(turn.proposal_id or "")
        self.assertEqual(proposal.proposal_type, "profile_setup")
        self.assertEqual(proposal.payload["person"]["timezone"], "America/Sao_Paulo")
        self.assertEqual(service.onboarding_turns_for_session("session-1"), (turn,))

    def test_new_household_onboarding_does_not_pass_placeholder_household_id(self) -> None:
        service = HealthMonitorService(
            agent_runtime="pydantic-ai",
            agent_model="ornith:9b",
            require_model=True,
            model_health_checker=lambda: True,
        )
        FakeOnboardingAgent.last_deps_household_id = None
        FakeOnboardingAgent.last_message = None

        with patch("health_monitor.application.service.PydanticAINutritionAgent", FakeOnboardingAgent):
            first = service.onboarding_chat(
                session_id="session-2",
                message="Meu nome é Gabriel.",
            )
            second = service.onboarding_chat(
                session_id="session-2",
                message="Quero 2000 kcal e 150g de proteína.",
            )

        self.assertEqual(FakeOnboardingAgent.last_deps_household_id, "")
        self.assertIn("Meu nome é Gabriel", FakeOnboardingAgent.last_message or "")
        self.assertIn("Quero 2000 kcal", FakeOnboardingAgent.last_message or "")
        self.assertEqual(first.household_id, None)
        self.assertEqual(second.proposal_id, "proposal_2")

    def test_scripted_onboarding_agent_drafts_new_household_through_deps(self) -> None:
        service = HealthMonitorService()
        requested_tools: list[str] = []
        prompts: list[str] = []

        def scripted_model(messages: list[Any], agent_info: AgentInfo) -> ModelResponse:
            requested_tools[:] = [tool.name for tool in agent_info.function_tools]
            prompts.append(repr(messages))
            proposal_id = proposal_id_from_tool_returns(messages, "draft_onboarding_proposal")
            if proposal_id is None:
                return ModelResponse(
                    parts=[
                        ToolCallPart(
                            "draft_onboarding_proposal",
                            {
                                "session_id": "session-3",
                                "household_name": "Casa",
                                "household_id": None,
                                "person": {"name": "Gabriel", "timezone": "America/Sao_Paulo"},
                                "targets": {"calories_kcal": 2000, "protein_g": 150},
                                "source_text": "Meu nome é Gabriel. Quero 2000 kcal e 150g de proteína.",
                            },
                        )
                    ]
                )
            return ModelResponse(
                parts=[
                    TextPart(
                        (
                            '{"output_type":"proposal_draft",'
                            f'"proposal_id":"{proposal_id}",'
                            '"summary":"Proposta inicial pronta."}'
                        )
                    )
                ]
            )

        agent = PydanticAINutritionAgent(
            model_name="function-test",
            ollama_base_url="http://127.0.0.1:11434",
            model=FunctionModel(scripted_model),
        )
        response = agent.onboarding(
            deps=AgentDeps(
                service=service,
                person_id="onboarding:session-3",
                household_id="",
                today=date(2026, 7, 2),
                settings={"agent_runtime": "pydantic-ai"},
                source_config={},
            ),
            session_id="session-3",
            message=(
                "No existing household id.\n"
                "Prior onboarding turns:\n"
                "User: Meu nome é Gabriel.\n"
                "Assistant: Qual sua meta?\n"
                "Current user message: Quero 2000 kcal e 150g de proteína."
            ),
        )

        self.assertIn("draft_onboarding_proposal", requested_tools)
        self.assertNotIn("onboarding-household:", "".join(prompts))
        self.assertIn("Meu nome é Gabriel", "".join(prompts))
        self.assertEqual(response.proposal_id, "proposal_1")
        proposal = service.get_proposal(response.proposal_id or "")
        self.assertIsNone(proposal.payload["household_id"])
        self.assertEqual(proposal.payload["household_name"], "Casa")


def scripted_agent_answer(
    *,
    service: HealthMonitorService,
    person_id: str,
    household_id: str,
    scripted_model: Any,
    message: str,
) -> AgentRuntimeResponse:
    agent = PydanticAINutritionAgent(
        model_name="function-test",
        ollama_base_url="http://127.0.0.1:11434",
        model=FunctionModel(scripted_model),
    )
    return agent.answer(
        deps=AgentDeps(
            service=service,
            person_id=person_id,
            household_id=household_id,
            today=date(2026, 7, 2),
            settings={"agent_runtime": "pydantic-ai", "external_lookup": False},
            source_config={
                "openfoodfacts_enabled": False,
                "research_lookup_enabled": False,
                "ocr_enabled": False,
            },
        ),
        message=message,
    )


def proposal_id_from_tool_returns(messages: list[Any], tool_name: str) -> str | None:
    for message in reversed(messages):
        if not isinstance(message, ModelRequest):
            continue
        for part in message.parts:
            if not isinstance(part, ToolReturnPart) or part.tool_name != tool_name:
                continue
            content = part.content
            if isinstance(content, dict) and isinstance(content.get("proposal_id"), str):
                return content["proposal_id"]
    return None


if __name__ == "__main__":
    unittest.main()
