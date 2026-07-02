from __future__ import annotations

import unittest
from unittest.mock import patch

from health_monitor.config import AppConfig
from health_monitor.smoke import check_ollama_readiness


class OllamaSmokeTest(unittest.TestCase):
    def test_detects_missing_required_models(self) -> None:
        config = AppConfig(
            agent_runtime="deterministic",
            model_provider="deterministic",
            ollama_base_url="http://ollama.local:11434",
            ollama_model="ornith:9b",
            ocr_model="glm-ocr:latest",
            label_text_extractor="ollama",
            live_model_name="ornith:9b",
        )

        with patch("health_monitor.smoke.list_ollama_models", return_value={"ornith:9b"}):
            result = check_ollama_readiness(config)

        self.assertFalse(result.ok)
        self.assertIn("missing_models: glm-ocr:latest", result.checks)

    def test_skips_ocr_model_when_label_extractor_is_disabled(self) -> None:
        config = AppConfig(
            agent_runtime="deterministic",
            model_provider="deterministic",
            ollama_base_url="http://ollama.local:11434",
            ollama_model="ornith:9b",
            ocr_model="missing-ocr",
            label_text_extractor="none",
            live_model_name="ornith:9b",
        )

        with patch("health_monitor.smoke.list_ollama_models", return_value={"ornith:9b"}):
            result = check_ollama_readiness(config)

        self.assertTrue(result.ok)
        self.assertIn("models_present: ornith:9b", result.checks)

    def test_runs_live_service_smoke_for_pydantic_ollama_runtime(self) -> None:
        config = AppConfig(
            agent_runtime="pydantic-ai",
            model_provider="ollama",
            ollama_base_url="http://ollama.local:11434",
            ollama_model="ornith:9b",
            ocr_model="ornith:9b",
            label_text_extractor="none",
            live_model_name="ornith:9b",
        )

        with (
            patch("health_monitor.smoke.list_ollama_models", return_value={"ornith:9b"}),
            patch("health_monitor.smoke.run_live_service_smoke") as service_smoke,
        ):
            result = check_ollama_readiness(config)

        self.assertTrue(result.ok)
        service_smoke.assert_called_once_with(config)
        self.assertIn("live_service_smoke: ok", result.checks)


if __name__ == "__main__":
    unittest.main()
