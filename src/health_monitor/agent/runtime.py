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

        model = OllamaModel(
            self.model_name,
            provider=OllamaProvider(base_url=self.ollama_base_url),
        )
        agent = Agent(
            model,
            deps_type=AgentDeps,
            instructions=(
                "You are a private household nutrition assistant. Use tools to inspect "
                "structured app data. Do not claim to mutate diary records directly. "
                "If asked to change data, explain that the app must use a confirmation "
                "proposal. Keep answers concise and cite uncertainty."
            ),
        )

        @agent.tool
        async def day_totals(ctx: RunContext[AgentDeps], iso_day: str) -> dict[str, Any]:
            """Return deterministic diary totals for one ISO date."""
            day = date.fromisoformat(iso_day)
            summary = ctx.deps.service.day_summary(ctx.deps.person_id, day)
            return {
                "day": summary.day.isoformat(),
                "totals": summary.totals.rounded().__dict__,
                "meals": {
                    meal: [
                        {
                            "entry_id": entry.id,
                            "food_name": entry.food_name,
                            "quantity_g": entry.quantity_g,
                            "calories_kcal": entry.nutrients.rounded().calories_kcal,
                        }
                        for entry in entries
                    ]
                    for meal, entries in summary.meals.items()
                },
            }

        @agent.tool
        async def weight_trend(ctx: RunContext[AgentDeps]) -> dict[str, Any]:
            """Return deterministic weight trend for the active person."""
            trend = ctx.deps.service.weight_trend(person_id=ctx.deps.person_id)
            return {
                "latest_kg": trend.latest_kg,
                "delta_kg": trend.delta_kg,
                "entries": [
                    {
                        "id": entry.id,
                        "measured_at": entry.measured_at.isoformat(),
                        "weight_kg": entry.weight_kg,
                    }
                    for entry in trend.entries
                ],
            }

        prompt = (
            f"Today is {deps.today.isoformat()}. Active person id is {deps.person_id}. "
            f"User message: {message}"
        )
        result = agent.run_sync(prompt, deps=deps)
        return AgentRuntimeResponse(
            message=str(result.output),
            behavior_label="pydantic_ai_answer",
        )
