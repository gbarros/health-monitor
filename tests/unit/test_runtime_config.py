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
        }
        with patch.dict(os.environ, env, clear=True):
            config = load_config()

        self.assertEqual(config.agent_runtime, "pydantic-ai")
        self.assertTrue(config.usda_enabled)
        self.assertEqual(config.usda_api_key, "test-usda-key")


if __name__ == "__main__":
    unittest.main()
