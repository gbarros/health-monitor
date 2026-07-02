from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol


class PydanticAIUnavailable(RuntimeError):
    pass


class HealthMonitorServiceProtocol(Protocol):
    def day_summary(self, person_id: str, day: date) -> Any:
        pass

    def week_summary(self, *, person_id: str, start: date, end: date) -> Any:
        pass

    def weight_trend(
        self,
        *,
        person_id: str,
        start: date | None = None,
        end: date | None = None,
    ) -> Any:
        pass

    def resolve_food_reference(
        self,
        *,
        household_id: str,
        person_id: str,
        phrase: str | None = None,
        barcode: str | None = None,
    ) -> Any:
        pass

    def lookup_food_candidates(
        self,
        *,
        household_id: str,
        person_id: str,
        phrase: str | None = None,
        barcode: str | None = None,
    ) -> Any:
        pass

    def propose_text_meal(
        self,
        *,
        person_id: str,
        logged_at_local: str,
        text: str,
        agent_settings: dict[str, Any] | None = None,
    ) -> Any:
        pass

    def chat(
        self,
        *,
        person_id: str,
        message: str,
        today: date,
        agent_settings: dict[str, Any] | None = None,
    ) -> Any:
        pass

    def get_proposal(self, proposal_id: str) -> Any:
        pass


@dataclass(frozen=True)
class AgentDeps:
    service: HealthMonitorServiceProtocol
    person_id: str
    household_id: str
    today: date
    settings: dict[str, Any]
    source_config: dict[str, Any]


@dataclass(frozen=True)
class AgentRuntimeResponse:
    message: str
    behavior_label: str = "answer_question"
    citations: tuple[dict[str, str], ...] = ()
    proposal_id: str | None = None


@dataclass(frozen=True)
class AgentAnswerOutput:
    message: str
    citations: tuple[dict[str, str], ...] = ()
    confidence: float | None = None


@dataclass(frozen=True)
class AgentProposalDraftOutput:
    proposal_id: str
    proposal_type: str
    proposal_status: str
    summary: str
    mutation_applied: bool = False


@dataclass(frozen=True)
class AgentClarificationRequestOutput:
    question: str
    missing_fields: tuple[str, ...]
    proposal_id: str | None = None


@dataclass(frozen=True)
class AgentLookupEstimateExplanation:
    source_name: str
    source_type: str
    source_id: str
    confidence: float
    warnings: tuple[str, ...] = ()


def normalize_ollama_base_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if normalized.endswith("/v1"):
        return normalized
    return f"{normalized}/v1"


class PydanticAINutritionAgent:
    def __init__(
        self,
        *,
        model_name: str,
        ollama_base_url: str,
    ) -> None:
        self.model_name = model_name
        self.ollama_base_url = normalize_ollama_base_url(ollama_base_url)

    def answer(self, *, deps: AgentDeps, message: str) -> AgentRuntimeResponse:
        try:
            from pydantic_ai import Agent, RunContext
            from pydantic_ai.models.ollama import OllamaModel
            from pydantic_ai.providers.ollama import OllamaProvider
        except ModuleNotFoundError as exc:
            raise PydanticAIUnavailable("pydantic_ai is not installed") from exc

        from health_monitor.agent.tools import NutritionAgentTools

        tools = NutritionAgentTools()
        model = OllamaModel(
            self.model_name,
            provider=OllamaProvider(base_url=self.ollama_base_url),
        )
        agent = Agent(
            model,
            deps_type=AgentDeps,
            instructions=(
                "You are a private household nutrition assistant. Use tools to inspect "
                "structured app data. Read tools can inspect diary, week summaries, "
                "weight trend, food resolution, lookup candidates, and food version "
                "history. Draft tools may create proposals, but they must not claim "
                "that diary entries or review notes were applied. If asked to change "
                "data, draft a proposal and explain that the user must confirm it. "
                "Keep answers concise and cite uncertainty."
            ),
        )

        @agent.tool
        async def day_summary(ctx: RunContext[AgentDeps], iso_day: str) -> dict[str, Any]:
            """Return deterministic diary entries, totals, targets, and citations for one ISO date."""
            return tools.day_summary(ctx.deps, iso_day)

        @agent.tool
        async def week_summary(
            ctx: RunContext[AgentDeps],
            start_iso: str,
            end_iso: str,
        ) -> dict[str, Any]:
            """Return deterministic daily and weekly totals for an ISO date range."""
            return tools.week_summary(ctx.deps, start_iso, end_iso)

        @agent.tool
        async def weight_trend(ctx: RunContext[AgentDeps]) -> dict[str, Any]:
            """Return deterministic weight trend for the active person."""
            return tools.weight_trend(ctx.deps)

        @agent.tool
        async def resolve_food(
            ctx: RunContext[AgentDeps],
            phrase: str | None = None,
            barcode: str | None = None,
        ) -> dict[str, Any]:
            """Resolve a natural food phrase or barcode to a specific local food version."""
            return tools.food_resolution(ctx.deps, phrase=phrase, barcode=barcode)

        @agent.tool
        async def lookup_food(
            ctx: RunContext[AgentDeps],
            phrase: str | None = None,
            barcode: str | None = None,
        ) -> dict[str, Any]:
            """Return local and configured external food lookup candidates."""
            return tools.food_lookup(ctx.deps, phrase=phrase, barcode=barcode)

        @agent.tool
        async def food_version_history(ctx: RunContext[AgentDeps], phrase: str) -> dict[str, Any]:
            """Inspect matching local food versions, defaults, and recent diary usage."""
            return tools.food_version_history(ctx.deps, phrase=phrase)

        @agent.tool
        async def draft_text_meal_proposal(
            ctx: RunContext[AgentDeps],
            logged_at_local: str,
            text: str,
        ) -> dict[str, Any]:
            """Draft a meal logging proposal without applying diary records."""
            return tools.draft_text_meal_proposal(
                ctx.deps,
                logged_at_local=logged_at_local,
                text=text,
            )

        @agent.tool
        async def draft_diary_correction_proposal(
            ctx: RunContext[AgentDeps],
            message: str,
        ) -> dict[str, Any]:
            """Draft a diary correction proposal without applying it."""
            return tools.draft_diary_correction_proposal(ctx.deps, message=message)

        @agent.tool
        async def draft_review_note_proposal(
            ctx: RunContext[AgentDeps],
            message: str,
        ) -> dict[str, Any]:
            """Draft a review note proposal without saving a review note."""
            return tools.draft_review_note_proposal(ctx.deps, message=message)

        prompt = (
            f"Today is {deps.today.isoformat()}. Active person id is {deps.person_id}. "
            f"User message: {message}"
        )
        result = agent.run_sync(prompt, deps=deps)
        return AgentRuntimeResponse(
            message=str(result.output),
            behavior_label="pydantic_ai_answer",
        )
