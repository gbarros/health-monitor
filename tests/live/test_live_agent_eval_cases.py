from __future__ import annotations

import json
import os
import unittest
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

from health_monitor.application.service import HealthMonitorService
from health_monitor.domain.nutrients import Nutrients
from health_monitor.lookup.estimates import NutritionEstimate, StaticFoodEstimator
from health_monitor.lookup.foods import FoodLookupCandidate, StaticFoodLookupProvider


def live_model_enabled() -> bool:
    return os.environ.get("LIVE_MODEL_TESTS", "false").casefold() in {"1", "true", "yes", "on"}


def load_cases() -> list[dict[str, object]]:
    case_path = Path(__file__).parent / "evals" / "core_agent_cases.jsonl"
    cases: list[dict[str, object]] = []
    for line in case_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            cases.append(json.loads(line))
    return cases


@unittest.skipUnless(live_model_enabled(), "set LIVE_MODEL_TESTS=true to run local live-agent evals")
class LiveAgentEvalCasesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        try:
            import pydantic_ai  # noqa: F401
        except ImportError as exc:
            raise unittest.SkipTest("pydantic_ai is not installed in this Python environment") from exc
        base_url = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
        try:
            urllib.request.urlopen(f"{base_url}/api/tags", timeout=2).read()
        except (OSError, urllib.error.URLError) as exc:
            raise unittest.SkipTest(f"Ollama is not reachable at {base_url}") from exc

    def make_service(self) -> tuple[HealthMonitorService, str]:
        service = HealthMonitorService(
            agent_runtime="pydantic-ai",
            model_provider="ollama",
            agent_model=os.environ.get("LIVE_MODEL_NAME", "ornith:9b"),
            ollama_base_url=os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
            estimator=StaticFoodEstimator(
                {
                    "kfc double crunch combo": NutritionEstimate(
                        phrase="kfc double crunch combo",
                        food_name="KFC Double Crunch combo",
                        nutrients_per_100g=Nutrients(260, 11, 24, 13, fiber_g=2, sodium_mg=820),
                        source="fixture_estimate",
                        confidence=0.42,
                        notes="Regional restaurant estimate fixture.",
                    )
                }
            ),
            food_lookup_provider=StaticFoodLookupProvider([]),
            research_lookup_provider=StaticFoodLookupProvider(
                [
                    FoodLookupCandidate(
                        source_type="research_agent",
                        source_name="Controlled research fixture",
                        source_id="research:kfc-double-crunch-br",
                        product_name="KFC Double Crunch combo",
                        brand="KFC",
                        barcode=None,
                        nutrients_per_100g=Nutrients(260, 11, 24, 13, fiber_g=2, sodium_mg=820),
                        serving_size_g=520,
                        confidence=0.48,
                        warnings=("fixture research estimate",),
                        research_prompt="Search nutritional references for KFC Double Crunch combo in Brazil.",
                    )
                ]
            ),
        )
        household = service.create_household(name="Casa")
        person = service.create_person(
            household_id=household.id,
            name="Gabriel",
            timezone="America/Sao_Paulo",
        )
        _, cheese = service.create_food_with_version(
            household_id=household.id,
            name="Queijo Minas",
            brand=None,
            version_label="current",
            nutrients_per_100g=Nutrients(315, 23, 2.6, 23.5, sodium_mg=620),
            source="label_scan",
            aliases=["queijo"],
        )
        yogurt_food, old_yogurt = service.create_food_with_version(
            household_id=household.id,
            name="Iogurte Batavo",
            brand="Batavo",
            version_label="old label",
            nutrients_per_100g=Nutrients(80, 8, 10, 1),
            source="label_scan",
            aliases=["iogurte batavo"],
        )
        service.create_food_with_version(
            household_id=household.id,
            name="Iogurte Batavo",
            brand="Batavo",
            version_label="new label",
            nutrients_per_100g=Nutrients(120, 15, 10, 2),
            source="label_scan",
            aliases=["iogurte novo"],
            food_id=yogurt_food.id,
        )
        service.log_diary_entry(
            person_id=person.id,
            logged_at_local="2026-07-02T10:00:00",
            food_version_id=cheese.id,
            quantity_g=100,
            source="manual",
        )
        service.log_diary_entry(
            person_id=person.id,
            logged_at_local="2026-07-01T10:00:00",
            food_version_id=old_yogurt.id,
            quantity_g=170,
            source="manual",
        )
        return service, person.id

    def test_core_live_agent_eval_cases(self) -> None:
        for case in load_cases():
            with self.subTest(case=case["id"]):
                service, person_id = self.make_service()
                result = run_case(service, person_id, case)
                assert_invariants(self, service, person_id, result, case["expected_invariants"])


def run_case(
    service: HealthMonitorService,
    person_id: str,
    case: dict[str, object],
) -> dict[str, object]:
    prompt = str(case["prompt"])
    eval_kind = str(case["eval_kind"])
    if eval_kind in {"weird_meal_phrasing", "restaurant_or_social_estimate"}:
        proposal = service.propose_text_meal(
            person_id=person_id,
            logged_at_local="2026-07-02T12:00:00",
            text=prompt,
            agent_settings={"research_lookup": True},
        )
        return {"proposal": proposal, "run": service.get_agent_run(proposal.source_agent_run_id or "")}
    response = service.chat(
        person_id=person_id,
        message=prompt,
        today=date(2026, 7, 2),
    )
    proposal = service.get_proposal(response.proposal_id) if response.proposal_id else None
    return {"response": response, "proposal": proposal, "run": service.get_agent_run(response.run_id)}


def assert_invariants(
    test: unittest.TestCase,
    service: HealthMonitorService,
    person_id: str,
    result: dict[str, object],
    invariants: object,
) -> None:
    names = [str(item) for item in invariants] if isinstance(invariants, list) else []
    proposal = result.get("proposal")
    run = result["run"]
    if "no_direct_mutation" in names:
        test.assertEqual(
            service.day_summary(person_id, date(2026, 7, 2)).totals.rounded().calories_kcal,
            315,
        )
    if "creates_diary_entry_update_proposal" in names:
        test.assertIsNotNone(proposal)
        test.assertEqual(proposal.proposal_type, "diary_entry_update")
    if "creates_review_note_proposal" in names:
        test.assertIsNotNone(proposal)
        test.assertEqual(proposal.proposal_type, "review_note")
        test.assertEqual(service.review_notes_for_person(person_id), ())
    if "answers_food_version_history" in names:
        response = result["response"]
        test.assertIn("label", response.message.casefold())
    if "creates_diary_proposal_or_clarification" in names:
        test.assertIsNotNone(proposal)
        test.assertIn(proposal.status, {"draft", "needs_clarification"})
    if "confidence_is_visible" in names and proposal is not None:
        evidence = proposal.evidence[0] if proposal.evidence else {}
        test.assertIn("confidence", evidence)
    test.assertIn(getattr(run, "status"), {"answered", "proposal_created", "needs_clarification"})


if __name__ == "__main__":
    unittest.main()
