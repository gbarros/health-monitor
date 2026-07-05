from __future__ import annotations

import json
import re
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

    def extract_label_text_from_attachment(self, *, attachment_id: str) -> dict[str, Any]:
        pass

    def propose_profile_update(
        self,
        *,
        person_id: str,
        changes: dict[str, Any],
        source_text: str,
        source_agent_run_id: str | None = None,
    ) -> Any:
        pass

    def propose_goal_profile_update(
        self,
        *,
        person_id: str,
        starts_on: date,
        targets: Any,
        notes: str | None,
        source_text: str,
        source_agent_run_id: str | None = None,
    ) -> Any:
        pass

    def draft_structured_meal_proposal(
        self,
        *,
        person_id: str,
        items: Any,
        day: date,
        time_text: str | None = None,
        meal_type: str | None = None,
        agent_settings: dict[str, Any] | None = None,
        source_text: str = "",
    ) -> Any:
        pass

    def amend_structured_meal_proposal(
        self,
        *,
        proposal_id: str,
        person_id: str,
        add: Any = (),
        remove: Any = (),
        set_quantity: Any = (),
        agent_settings: dict[str, Any] | None = None,
        source_text: str = "",
    ) -> Any:
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
        message = _message_from_payload(payload, output_type=output_type)
        proposal_id = _optional_str(payload.get("proposal_id")) or _proposal_id_from_text(message)
        message = _message_from_payload(payload, output_type=output_type)
        return AgentRuntimeResponse(
            message=message,
            behavior_label=_behavior_label_for(output_type, proposal_id=proposal_id),
            citations=_citations_from_payload(payload.get("citations")),
            proposal_id=proposal_id,
            output_type=output_type,
            confidence=_optional_float(payload.get("confidence")),
        )
    if isinstance(payload, str):
        proposal_id = _proposal_id_from_text(payload)
        return AgentRuntimeResponse(
            message=payload,
            behavior_label="proposal_draft" if proposal_id is not None else "pydantic_ai_answer",
            proposal_id=proposal_id,
            output_type="proposal_draft" if proposal_id is not None else "answer",
        )
    return AgentRuntimeResponse(message=str(payload), behavior_label="pydantic_ai_answer")


def runtime_output_payload(raw_output: Any) -> Any:
    if isinstance(raw_output, str):
        stripped = raw_output.strip()
        if stripped.startswith("```"):
            lines = stripped.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            stripped = "\n".join(lines).strip()
        if stripped.startswith("{"):
            try:
                return json.loads(stripped)
            except json.JSONDecodeError:
                try:
                    parsed, _ = json.JSONDecoder().raw_decode(stripped)
                    return parsed
                except json.JSONDecodeError:
                    return raw_output
        if stripped.startswith("["):
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


def _proposal_id_from_text(value: str) -> str | None:
    match = re.search(r"\bproposal_\d+\b", value)
    if match is None:
        return None
    return match.group(0)


def _looks_like_proposal_request(message: str) -> bool:
    text = message.casefold()
    if re.search(r"\b\d+(?:[.,]\d+)?\s*g\b", text):
        return True
    keywords = (
        "café",
        "cafe",
        "almoço",
        "almoco",
        "jantar",
        "lanche",
        "change ",
        "save review note",
        "review note",
        "comi",
        "corrig",
        "peso",
    )
    return any(keyword in text for keyword in keywords)


def _detect_meal_type(message: str) -> str | None:
    text = message.casefold()
    if "café" in text or "cafe" in text:
        return "breakfast"
    if "almoço" in text or "almoco" in text:
        return "lunch"
    if "jantar" in text:
        return "dinner"
    if "lanche" in text:
        return "snack"
    return None


def _simple_quantified_meal_items(message: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for quantity_text, phrase in re.findall(r"([+-]?\d+(?:[.,]\d+)?)\s*g\s+([^/\n,]+)", message, flags=re.IGNORECASE):
        try:
            quantity_g = float(quantity_text.replace(",", "."))
        except ValueError:
            continue
        phrase_text = phrase.strip(" .:;-").strip()
        if quantity_g <= 0 or not phrase_text:
            continue
        items.append({"phrase": phrase_text, "quantity_g": quantity_g})
    return items


def _simple_quantified_meal_response(deps: AgentDeps, message: str) -> AgentRuntimeResponse | None:
    items = _simple_quantified_meal_items(message)
    if not items:
        return None
    proposal = deps.service.draft_structured_meal_proposal(
        person_id=deps.person_id,
        items=items,
        day=deps.today,
        time_text=None,
        meal_type=_detect_meal_type(message),
        agent_settings=deps.settings,
        source_text=message,
    )
    return AgentRuntimeResponse(
        message=proposal.summary,
        behavior_label="proposal_draft",
        proposal_id=proposal.id,
        output_type="proposal_draft",
    )


class PydanticAINutritionAgent:
    def __init__(
        self,
        *,
        model_name: str,
        ollama_base_url: str,
        model: Any | None = None,
    ) -> None:
        self.model_name = model_name
        self.ollama_base_url = normalize_ollama_base_url(ollama_base_url)
        self.model = model

    def answer(self, *, deps: AgentDeps, message: str) -> AgentRuntimeResponse:
        result = self._run(
            deps=deps,
            message=message,
            task_instructions=(
                "Return a concise answer. If the user is asking to log food, amend a meal, "
                "repeat a meal, log a weight, draft a recipe, or otherwise change app data, "
                "you must call the corresponding tool instead of describing the action in prose. "
                "If the user asks to change a logged food quantity on a specific day, call "
                "draft_diary_correction_proposal. If the user asks to save a review note, call "
                "draft_review_note_proposal. If the user gives a restaurant or social meal that "
                "cannot be resolved to a local food, use lookup or estimate tools and then call "
                "draft_range_estimate; do not stop at a prose calorie estimate. A message like "
                "'100g KFC Double Crunch combo' must end with a drafted estimate proposal, not "
                "just an answer. For free-form meal logs with colloquial time phrases or "
                "multiple foods, still draft the meal from the best structured items you can infer. "
                "If the message includes both a vague and exact quantity for the same food, prefer "
                "the exact gram amount. If the message includes discarded or non-edible mass such "
                "as '-33g ossos', omit that from logged foods instead of blocking the draft. "
                "Never claim that you drafted a proposal unless a draft tool actually returned "
                "a proposal_id in this run. A bare message like '50g queijo' is a food logging "
                "request, not a question. Prefer JSON with output_type='answer', message, "
                "citations, and confidence when possible; after drafting, return output_type="
                "'proposal_draft' with the created proposal_id."
            ),
        )
        response = normalize_agent_runtime_output(result.output)
        if response.proposal_id is None:
            deterministic_meal = _simple_quantified_meal_response(deps, message)
            if deterministic_meal is not None:
                return deterministic_meal
        if response.proposal_id is None and _looks_like_proposal_request(message):
            retry = self._run(
                deps=deps,
                message=message,
                task_instructions=(
                    "The previous attempt answered in prose without creating the required draft. "
                    "This message requires a proposal tool call or a clarification_request. "
                    "Do not answer in prose alone. If the request is actionable, call the "
                    "relevant draft or amend tool and then finish with the created proposal_id. "
                    "If required details are missing, finish with output_type='clarification_request'."
                ),
            )
            return normalize_agent_runtime_output(retry.output)
        return response

    def onboarding(self, *, deps: AgentDeps, message: str, session_id: str) -> AgentRuntimeResponse:
        result = self._run(
            deps=deps,
            message=(
                f"Onboarding session id: {session_id}\n"
                f"Existing household id, when present: {deps.household_id}\n"
                f"User message: {message}"
            ),
            task_instructions=(
                "You are onboarding a new household member. Ask concise follow-up questions "
                "until household name or household id, person name, timezone, and initial targets "
                "are clear. When enough information is available, call draft_onboarding_proposal "
                "with structured person and target fields. If an existing household id is present, "
                "pass that household_id to the tool instead of inventing a household name. Return "
                "JSON with output_type='answer' for questions or output_type='proposal_draft' and "
                "proposal_id after drafting."
            ),
        )
        return normalize_agent_runtime_output(result.output)

    def _run(self, *, deps: AgentDeps, message: str, task_instructions: str) -> Any:
        try:
            from pydantic_ai import Agent
            from pydantic_ai.models.ollama import OllamaModel
            from pydantic_ai.output import ToolOutput
            from pydantic_ai.providers.ollama import OllamaProvider
            from pydantic_ai.usage import UsageLimits
        except ImportError as exc:
            raise PydanticAIUnavailable("pydantic_ai is not installed") from exc

        from health_monitor.agent.tools import NutritionAgentTools

        tools = NutritionAgentTools()
        model = self.model or OllamaModel(
            self.model_name,
            provider=OllamaProvider(base_url=self.ollama_base_url),
            settings={"timeout": 20, "temperature": 0},
        )
        agent = Agent(
            model,
            deps_type=AgentDeps,
            instructions=(
                "You are a private household nutrition assistant. Use tools to inspect "
                "structured app data. Read tools can inspect diary, week summaries, "
                "weight trend, food resolution, lookup candidates, and food version "
                "history, and can run targeted OCR on attachment ids when image text "
                "is needed. For food logging, extract structured items yourself and "
                "call draft_meal_proposal or amend_meal_proposal; do not route raw user "
                "text through deterministic parsers. When using search or resolve tools, "
                "pass only the food phrase, never quantities or units. For meal drafts, "
                "each item should look like {'phrase': 'queijo', 'quantity_g': 50}. "
                "Draft tools may create proposals, but they must not claim "
                "that diary entries, profile fields, goal targets, or review notes were "
                "applied. If asked to change data, draft a proposal and explain that "
                "the user must confirm it. Never say you drafted something unless you actually "
                "called a draft tool and received a proposal id. When you are ready to respond, "
                "call the finish tool exactly once with the final response payload. "
                "Keep answers concise and cite uncertainty. "
                f"{task_instructions}"
            ),
        )

        @agent.tool
        async def day_summary(ctx, iso_day: str) -> dict[str, Any]:
            """Return deterministic diary entries, totals, targets, and citations for one ISO date."""
            return tools.day_summary(ctx.deps, iso_day)

        @agent.tool
        async def week_summary(
            ctx,
            start_iso: str,
            end_iso: str,
        ) -> dict[str, Any]:
            """Return deterministic daily and weekly totals for an ISO date range."""
            return tools.week_summary(ctx.deps, start_iso, end_iso)

        @agent.tool
        async def weight_trend(ctx) -> dict[str, Any]:
            """Return deterministic weight trend for the active person."""
            return tools.weight_trend(ctx.deps)

        @agent.tool
        async def resolve_food(
            ctx,
            phrase: str | None = None,
            barcode: str | None = None,
        ) -> dict[str, Any]:
            """Resolve a food phrase only, without grams or units, or a barcode to a specific local food version."""
            return tools.food_resolution(ctx.deps, phrase=phrase, barcode=barcode)

        @agent.tool
        async def lookup_food(
            ctx,
            phrase: str | None = None,
            barcode: str | None = None,
        ) -> dict[str, Any]:
            """Return local and configured external food lookup candidates."""
            return tools.food_lookup(ctx.deps, phrase=phrase, barcode=barcode)

        @agent.tool
        async def search_foods(ctx, query: str) -> dict[str, Any]:
            """Search local foods by user-facing name, brand, or alias."""
            return tools.search_foods(ctx.deps, query=query)

        @agent.tool
        async def get_food_details(ctx, phrase: str) -> dict[str, Any]:
            """Return local food versions, default version, and latest diary usage for a phrase."""
            return tools.get_food_details(ctx.deps, phrase=phrase)

        @agent.tool
        async def list_open_proposals(ctx) -> dict[str, Any]:
            """List draft or clarification proposals that can be confirmed, rejected, or amended."""
            return tools.list_open_proposals(ctx.deps)

        @agent.tool
        async def food_version_history(ctx, phrase: str) -> dict[str, Any]:
            """Inspect matching local food versions, defaults, and recent diary usage."""
            return tools.food_version_history(ctx.deps, phrase=phrase)

        @agent.tool
        async def extract_label_text_from_attachment(ctx, attachment_id: str) -> dict[str, Any]:
            """Run the configured targeted OCR model over one uploaded label image attachment."""
            return tools.extract_label_text_from_attachment(ctx.deps, attachment_id=attachment_id)

        @agent.tool
        async def draft_meal_proposal(
            ctx,
            items: list[dict[str, Any]],
            day: str,
            time: str | None = None,
            meal_type: str | None = None,
            source_text: str = "",
        ) -> dict[str, Any]:
            """Draft a meal proposal from structured items like {'phrase': 'queijo', 'quantity_g': 50}."""
            return tools.draft_meal_proposal(
                ctx.deps,
                items=items,
                day=day,
                time=time,
                meal_type=meal_type,
                source_text=source_text,
            )

        @agent.tool
        async def amend_meal_proposal(
            ctx,
            proposal_id: str,
            add: list[dict[str, Any]] | None = None,
            remove: list[dict[str, Any]] | None = None,
            set_quantity: list[dict[str, Any]] | None = None,
            source_text: str = "",
        ) -> dict[str, Any]:
            """Amend an open meal proposal using structured add/remove/set_quantity instructions."""
            return tools.amend_meal_proposal(
                ctx.deps,
                proposal_id=proposal_id,
                add=add,
                remove=remove,
                set_quantity=set_quantity,
                source_text=source_text,
            )

        @agent.tool
        async def log_weight(ctx, weight_kg: float, measured_at: str | None = None) -> dict[str, Any]:
            """Log a weight measurement directly; measured_at is optional local ISO datetime."""
            return tools.log_weight(ctx.deps, weight_kg=weight_kg, measured_at=measured_at)

        @agent.tool
        async def repeat_meal(ctx, source_day: str, meal_type: str, target_time: str | None = None) -> dict[str, Any]:
            """Draft a proposal copying one meal type from source_day to today."""
            return tools.repeat_meal(ctx.deps, source_day=source_day, meal_type=meal_type, target_time=target_time)

        @agent.tool
        async def draft_range_estimate(
            ctx,
            label: str,
            low_kcal: float,
            high_kcal: float,
            meal_type: str | None = None,
            day: str | None = None,
        ) -> dict[str, Any]:
            """Draft a midpoint calorie-range estimate proposal."""
            return tools.draft_range_estimate(
                ctx.deps,
                label=label,
                low_kcal=low_kcal,
                high_kcal=high_kcal,
                meal_type=meal_type,
                day=day,
            )

        @agent.tool
        async def draft_recipe_proposal(
            ctx,
            name: str,
            ingredients: list[dict[str, Any]],
            total_cooked_weight_g: float,
            aliases: list[str] | None = None,
            quantity_g: float | None = None,
            meal_type: str | None = None,
        ) -> dict[str, Any]:
            """Draft a recipe/lote proposal from structured ingredients."""
            return tools.draft_recipe_proposal(
                ctx.deps,
                name=name,
                aliases=aliases,
                ingredients=ingredients,
                total_cooked_weight_g=total_cooked_weight_g,
                quantity_g=quantity_g,
                meal_type=meal_type,
            )

        @agent.tool
        async def draft_diary_correction_proposal(
            ctx,
            quantity_g: float,
            entry_id: str | None = None,
            day: str | None = None,
            phrase: str | None = None,
            source_text: str = "",
        ) -> dict[str, Any]:
            """Draft a diary correction proposal without applying it."""
            return tools.draft_diary_correction_proposal(
                ctx.deps,
                quantity_g=quantity_g,
                entry_id=entry_id,
                day=day,
                phrase=phrase,
                source_text=source_text,
            )

        @agent.tool
        async def draft_review_note_proposal(
            ctx,
            body: str,
            title: str | None = None,
            starts_on: str | None = None,
            ends_on: str | None = None,
            source_text: str = "",
        ) -> dict[str, Any]:
            """Draft a review note proposal without saving a review note."""
            return tools.draft_review_note_proposal(
                ctx.deps,
                body=body,
                title=title,
                starts_on=starts_on,
                ends_on=ends_on,
                source_text=source_text,
            )

        @agent.tool
        async def draft_profile_update_proposal(
            ctx,
            changes: dict[str, Any],
            source_text: str,
        ) -> dict[str, Any]:
            """Draft a profile update proposal without changing the profile."""
            return tools.draft_profile_update_proposal(
                ctx.deps,
                changes=changes,
                source_text=source_text,
            )

        @agent.tool
        async def draft_goal_profile_proposal(
            ctx,
            starts_on: str,
            calories_kcal: float,
            protein_g: float,
            carbs_g: float,
            fat_g: float,
            fiber_g: float,
            sodium_mg: float,
            notes: str | None = None,
            source_text: str = "",
        ) -> dict[str, Any]:
            """Draft a dated macro target proposal without changing active targets."""
            return tools.draft_goal_profile_proposal(
                ctx.deps,
                starts_on=starts_on,
                calories_kcal=calories_kcal,
                protein_g=protein_g,
                carbs_g=carbs_g,
                fat_g=fat_g,
                fiber_g=fiber_g,
                sodium_mg=sodium_mg,
                notes=notes,
                source_text=source_text,
            )

        @agent.tool
        async def draft_onboarding_proposal(
            ctx,
            session_id: str,
            person: dict[str, Any],
            targets: dict[str, Any],
            household_name: str | None = None,
            household_id: str | None = None,
            notes: str | None = None,
            source_text: str = "",
        ) -> dict[str, Any]:
            """Draft the initial household/person/goal setup proposal for onboarding."""
            return tools.draft_onboarding_proposal(
                ctx.deps,
                session_id=session_id,
                household_name=household_name,
                household_id=household_id,
                starts_on=deps.today.isoformat(),
                person=person,
                targets=targets,
                notes=notes,
                source_text=source_text,
            )

        prompt = (
            f"Today is {deps.today.isoformat()}. Active person id is {deps.person_id}. "
            f"User message: {message}"
        )
        return agent.run_sync(
            prompt,
            deps=deps,
            output_type=[ToolOutput(AgentRuntimeResponse, name="finish"), str],
            usage_limits=UsageLimits(request_limit=8, tool_calls_limit=8),
        )
