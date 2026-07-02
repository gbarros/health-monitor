from __future__ import annotations

import os
import unittest

from health_monitor.application.service import HealthMonitorService


def cloud_evals_enabled() -> bool:
    return os.environ.get("CLOUD_MODEL_CALLS_ENABLED", "false").casefold() in {
        "1",
        "true",
        "yes",
        "on",
    }


@unittest.skipUnless(cloud_evals_enabled(), "set CLOUD_MODEL_CALLS_ENABLED=true to run cloud model evals")
class CloudModelEvalTest(unittest.TestCase):
    def test_cloud_model_runtime_is_opt_in_and_records_model_name(self) -> None:
        try:
            import pydantic_ai  # noqa: F401
        except ImportError as exc:
            raise unittest.SkipTest("pydantic_ai is not installed in this Python environment") from exc

        service = HealthMonitorService(
            agent_runtime="pydantic-ai",
            model_provider="ollama",
            agent_model=os.environ.get("CLOUD_MODEL_NAME", "glm-5.2:cloud"),
            ollama_base_url=os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
        )
        household = service.create_household(name="Casa")
        person = service.create_person(
            household_id=household.id,
            name="Gabriel",
            timezone="America/Sao_Paulo",
        )

        response = service.chat(
            person_id=person.id,
            message="Answer in one short sentence: are writes proposal-gated in this app?",
            today=__import__("datetime").date(2026, 7, 2),
        )

        run = service.get_agent_run(response.run_id)
        self.assertEqual(run.model_name, os.environ.get("CLOUD_MODEL_NAME", "glm-5.2:cloud"))
        self.assertTrue(response.message.strip())


if __name__ == "__main__":
    unittest.main()
