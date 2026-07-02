from __future__ import annotations

import os
import unittest
import urllib.error
import urllib.request

from health_monitor.application.service import HealthMonitorService
from health_monitor.domain.nutrients import Nutrients


def live_model_enabled() -> bool:
    return os.environ.get("LIVE_MODEL_TESTS", "false").casefold() in {"1", "true", "yes", "on"}


@unittest.skipUnless(live_model_enabled(), "set LIVE_MODEL_TESTS=true to run local Ollama/PydanticAI checks")
class LiveModelAgentTest(unittest.TestCase):
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
        model = os.environ.get("LIVE_MODEL_NAME", "ornith:9b")
        service = HealthMonitorService(
            agent_runtime="pydantic-ai",
            model_provider="ollama",
            agent_model=model,
            ollama_base_url=os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
        )
        household = service.create_household(name="Casa")
        person = service.create_person(
            household_id=household.id,
            name="Gabriel",
            timezone="America/Sao_Paulo",
        )
        _, version = service.create_food_with_version(
            household_id=household.id,
            name="Queijo Minas",
            brand=None,
            version_label="current",
            nutrients_per_100g=Nutrients(315, 23, 2.6, 23.5, sodium_mg=620),
            source="label_scan",
            aliases=["queijo"],
        )
        service.log_diary_entry(
            person_id=person.id,
            logged_at_local="2026-07-02T10:00:00",
            food_version_id=version.id,
            quantity_g=100,
            source="manual",
        )
        return service, person.id

    def test_live_model_answers_seeded_structured_question(self) -> None:
        service, person_id = self.make_service()

        response = service.chat(
            person_id=person_id,
            message="Use structured app data to answer: what is my largest logged contributor?",
            today=__import__("datetime").date(2026, 7, 2),
        )

        run = service.get_agent_run(response.run_id)
        self.assertEqual(run.runtime, "pydantic-ai")
        self.assertEqual(run.model_name, os.environ.get("LIVE_MODEL_NAME", "ornith:9b"))
        self.assertEqual(run.status, "answered")
        self.assertIsNone(run.fallback_reason)
        self.assertTrue(response.message.strip())

    def test_live_model_text_meal_drafts_without_mutation(self) -> None:
        service, person_id = self.make_service()

        proposal = service.propose_text_meal(
            person_id=person_id,
            logged_at_local="2026-07-02T12:00:00",
            text="50g queijo",
        )

        run = service.get_agent_run(proposal.source_agent_run_id or "")
        self.assertEqual(run.runtime, "pydantic-ai")
        self.assertEqual(run.status, "proposal_created")
        self.assertIsNone(run.fallback_reason)
        self.assertEqual(proposal.status, "draft")
        self.assertEqual(service.day_summary(person_id, proposal.entries[0].logged_at.date()).totals.rounded().calories_kcal, 315)


if __name__ == "__main__":
    unittest.main()
