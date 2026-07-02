from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ROOT / "compose.yaml"
DOCKERFILE_API = ROOT / "Dockerfile.api"


class ComposeRuntimeTest(unittest.TestCase):
    def test_api_and_worker_wait_for_postgres_health(self) -> None:
        source = COMPOSE.read_text(encoding="utf-8")

        self.assertIn("healthcheck:", source)
        self.assertIn("pg_isready", source)
        self.assertIn("condition: service_healthy", source)

    def test_web_waits_for_api_health(self) -> None:
        source = COMPOSE.read_text(encoding="utf-8")

        self.assertIn("/api/health", source)
        self.assertIn("urllib.request.urlopen", source)
        self.assertIn("api:\n        condition: service_healthy", source)

    def test_api_and_worker_restart_after_transient_startup_failures(self) -> None:
        source = COMPOSE.read_text(encoding="utf-8")

        self.assertGreaterEqual(source.count("restart: unless-stopped"), 2)

    def test_api_and_worker_can_emit_nexuslog_jsonl_events(self) -> None:
        source = COMPOSE.read_text(encoding="utf-8")

        self.assertIn("NEXUSLOG_MODE", source)
        self.assertGreaterEqual(source.count("NEXUSLOG_JSONL_PATH"), 2)

    def test_local_stack_defaults_to_pydantic_ai_runtime_with_optional_usda(self) -> None:
        source = COMPOSE.read_text(encoding="utf-8")

        self.assertGreaterEqual(source.count("AGENT_RUNTIME: ${AGENT_RUNTIME:-pydantic-ai}"), 2)
        self.assertGreaterEqual(source.count("USDA_ENABLED: ${USDA_ENABLED:-false}"), 2)
        self.assertGreaterEqual(source.count("USDA_API_KEY: ${USDA_API_KEY:-}"), 2)

    def test_api_image_installs_pydantic_ai_runtime_dependency(self) -> None:
        source = DOCKERFILE_API.read_text(encoding="utf-8")

        self.assertIn('"pydantic-ai>=0.7"', source)


if __name__ == "__main__":
    unittest.main()
