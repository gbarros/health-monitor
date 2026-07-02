from __future__ import annotations

import json
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
    output_type: str = "answer"
    confidence: float | None = None


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


def normalize_agent_runtime_output(raw_output: Any) -> AgentRuntimeResponse:
    payload = runtime_output_payload(raw_output)
    if isinstance(payload, AgentRuntimeResponse):
        return payload
    if isinstance(payload, AgentAnswerOutput):
        return AgentRuntimeResponse(
            message=payload.message,
            citations=payload.citations,
            output_type="answer",
            confidence=payload.confidence,
        )
    if isinstance(payload, AgentProposalDraftOutput):
        return AgentRuntimeResponse(
            message=payload.summary,
            behavior_label="proposal_draft",
            proposal_id=payload.proposal_id,
            output_type="proposal_draft",
        )
    if isinstance(payload, AgentClarificationRequestOutput):
        return AgentRuntimeResponse(
            message=payload.question,
            behavior_label="clarification_request",
            proposal_id=payload.proposal_id,
            output_type="clarification_request",
        )
    if isinstance(payload, AgentLookupEstimateExplanation):
        return AgentRuntimeResponse(
            message=(
                f"{payload.source_name} {payload.source_type} estimate "
                f"{payload.source_id} with {payload.confidence:.0%} confidence."
            ),
            behavior_label="lookup_explanation",
            output_type="lookup_explanation",
            confidence=payload.confidence,
        )
    if isinstance(payload, dict):
        output_type = str(payload.get("output_type") or payload.get("type") or "answer")
        proposal_id = _optional_str(payload.get("proposal_id"))
        message = _message_from_payload(payload, output_type=output_type)
        return AgentRuntimeResponse(
            message=message,
            behavior_label=_behavior_label_for(output_type, proposal_id=proposal_id),
            citations=_citations_from_payload(payload.get("citations")),
            proposal_id=proposal_id,
            output_type=output_type,
            confidence=_optional_float(payload.get("confidence")),
        )
    return AgentRuntimeResponse(message=str(payload))


def runtime_output_payload(raw_output: Any) -> Any:
    if isinstance(raw_output, str):
        stripped = raw_output.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            try:
                return json.loads(stripped)
            except json.JSONDecodeError:
                return raw_output
    if hasattr(raw_output, "__dict__") and not isinstance(raw_output, type):
        values = {
            key: value
            for key, value in vars(raw_output).items()
            if not key.startswith("_")
        }
        if values:
            return values
    return raw_output


def _message_from_payload(payload: dict[str, Any], *, output_type: str) -> str:
    for key in ("message", "answer", "summary", "question", "explanation"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    if output_type == "proposal_draft" and payload.get("proposal_id"):
        return f"Draft proposal {payload['proposal_id']} is ready for review."
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _behavior_label_for(output_type: str, *, proposal_id: str | None) -> str:
    if proposal_id is not None:
        return "proposal_draft"
    if output_type in {"clarification", "clarification_request"}:
        return "clarification_request"
    if output_type in {"lookup", "lookup_explanation", "estimate"}:
        return "lookup_explanation"
    return "pydantic_ai_answer"


def _citations_from_payload(value: Any) -> tuple[dict[str, str], ...]:
    if not isinstance(value, list):
        return ()
    citations: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        citations.append({str(key): str(val) for key, val in item.items()})
    return tuple(citations)


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


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
        result = self._run(
            deps=deps,
            message=message,
            task_instructions=(
                "Return a concise answer. Prefer JSON with output_type='answer', "
                "message, citations, and confidence when possible."
            ),
        )
        return normalize_agent_runtime_output(result.output)

    def draft_text_meal(
        self,
        *,
        deps: AgentDeps,
        logged_at_local: str,
        text: str,
    ) -> AgentRuntimeResponse:
        result = self._run(
            deps=deps,
            message=(
                "Validate that this is a meal logging request, then rely on the "
                "draft_text_meal_proposal tool for the actual draft. Do not apply "
                f"records. logged_at_local={logged_at_local!r}; text={text!r}"
            ),
            task_instructions=(
                "Return JSON. If the request should be drafted, output_type must be "
                "'proposal_draft'. If required details are missing, output_type must "
                "be 'clarification_request'."
            ),
        )
        _ = normalize_agent_runtime_output(result.output)
        from health_monitor.agent.tools import NutritionAgentTools

        proposal = NutritionAgentTools().draft_text_meal_proposal(
            deps,
            logged_at_local=logged_at_local,
            text=text,
        )
        return AgentRuntimeResponse(
            message=proposal["summary"],
            behavior_label="proposal_draft",
            proposal_id=str(proposal["proposal_id"]),
            output_type="proposal_draft",
        )

    def _run(self, *, deps: AgentDeps, message: str, task_instructions: str) -> Any:
        try:
            from pydantic_ai import Agent, RunContext
            from pydantic_ai.models.ollama import OllamaModel
            from pydantic_ai.providers.ollama import OllamaProvider
        except ImportError as exc:
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
                "Keep answers concise and cite uncertainty. "
                f"{task_instructions}"
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
        return agent.run_sync(prompt, deps=deps)
