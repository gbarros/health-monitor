from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from datetime import date

from health_monitor.application.service import HealthMonitorService
from health_monitor.config import AppConfig
from health_monitor.domain.nutrients import Nutrients


@dataclass(frozen=True)
class SmokeResult:
    ok: bool
    checks: tuple[str, ...]


def list_ollama_models(base_url: str, *, timeout_seconds: float = 5) -> set[str]:
    with urllib.request.urlopen(f"{base_url.rstrip('/')}/api/tags", timeout=timeout_seconds) as response:
        payload = json.loads(response.read().decode("utf-8"))
    models: set[str] = set()
    for item in payload.get("models", []):
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        model = item.get("model")
        if isinstance(name, str):
            models.add(name)
        if isinstance(model, str):
            models.add(model)
    return models


def check_ollama_readiness(config: AppConfig, *, timeout_seconds: float = 5) -> SmokeResult:
    checks: list[str] = []
    try:
        models = list_ollama_models(config.ollama_base_url, timeout_seconds=timeout_seconds)
    except OSError as exc:
        return SmokeResult(False, (f"ollama_unreachable: {exc}",))
    checks.append(f"ollama_reachable: {config.ollama_base_url}")

    required = {config.ollama_model, config.live_model_name}
    if config.label_text_extractor == "ollama":
        required.add(config.ocr_model)
    missing = sorted(model for model in required if model and model not in models)
    if missing:
        checks.append(f"missing_models: {', '.join(missing)}")
        return SmokeResult(False, tuple(checks))
    checks.append(f"models_present: {', '.join(sorted(required))}")

    if config.agent_runtime == "pydantic-ai" or config.model_provider == "ollama":
        try:
            run_live_service_smoke(config)
        except Exception as exc:
            checks.append(f"live_service_smoke_failed: {exc}")
            return SmokeResult(False, tuple(checks))
        checks.append("live_service_smoke: ok")

    return SmokeResult(True, tuple(checks))


def run_live_service_smoke(config: AppConfig) -> None:
    service = HealthMonitorService(
        agent_runtime="pydantic-ai",
        model_provider="ollama",
        agent_model=config.live_model_name,
        ollama_base_url=config.ollama_base_url,
    )
    household = service.create_household(name="Smoke")
    person = service.create_person(
        household_id=household.id,
        name="Smoke User",
        timezone="America/Sao_Paulo",
    )
    _, version = service.create_food_with_version(
        household_id=household.id,
        name="Queijo Minas",
        brand=None,
        version_label="smoke",
        nutrients_per_100g=Nutrients(315, 23, 2.6, 23.5, sodium_mg=620),
        source="smoke",
        aliases=["queijo"],
    )
    service.log_diary_entry(
        person_id=person.id,
        logged_at_local="2026-07-02T10:00:00",
        food_version_id=version.id,
        quantity_g=100,
        source="smoke",
    )
    response = service.chat(
        person_id=person.id,
        message="Use only app data. What food contributed most calories today?",
        today=date(2026, 7, 2),
    )
    run = service.get_agent_run(response.run_id)
    if run.runtime != "pydantic-ai" or run.fallback_reason is not None:
        raise RuntimeError(
            f"unexpected runtime={run.runtime!r} fallback={run.fallback_reason!r}"
        )
    proposal = service.propose_text_meal(
        person_id=person.id,
        logged_at_local="2026-07-02T12:00:00",
        text="50g queijo",
    )
    proposal_run = service.get_agent_run(proposal.source_agent_run_id or "")
    if proposal.status != "draft" or proposal_run.fallback_reason is not None:
        raise RuntimeError(
            f"unexpected proposal={proposal.status!r} fallback={proposal_run.fallback_reason!r}"
        )
