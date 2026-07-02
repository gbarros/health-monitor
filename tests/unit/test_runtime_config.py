from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from health_monitor.config import load_config


class RuntimeConfigTest(unittest.TestCase):
    def test_agent_runtime_and_usda_flags_are_loaded_from_environment(self) -> None:
        env = {
            **os.environ,
            "AGENT_RUNTIME": "pydantic-ai",
            "USDA_ENABLED": "true",
            "USDA_API_KEY": "test-usda-key",
            "RESEARCH_LOOKUP_ENABLED": "true",
            "LIVE_MODEL_TESTS": "true",
            "LIVE_MODEL_NAME": "ornith:9b",
            "OCR_MODEL": "glm-ocr:latest",
            "CLOUD_MODEL_CALLS_ENABLED": "true",
            "CLOUD_MODEL_NAME": "glm-5.2:cloud",
        }
        with patch.dict(os.environ, env, clear=True):
            config = load_config()

        self.assertEqual(config.agent_runtime, "pydantic-ai")
        self.assertTrue(config.usda_enabled)
        self.assertEqual(config.usda_api_key, "test-usda-key")
        self.assertTrue(config.research_lookup_enabled)
        self.assertTrue(config.live_model_tests)
        self.assertEqual(config.live_model_name, "ornith:9b")
        self.assertEqual(config.ocr_model, "glm-ocr:latest")
        self.assertTrue(config.cloud_model_calls_enabled)
        self.assertEqual(config.cloud_model_name, "glm-5.2:cloud")


if __name__ == "__main__":
    unittest.main()
