from __future__ import annotations

import unittest

from tests.unit.frontend_helpers import read_web_file


class AgentSettingsUiTest(unittest.TestCase):
    def test_agent_settings_are_kept_in_a_drawer_with_live_model_defaults(self) -> None:
        app = read_web_file("App.tsx")
        manual_inputs = read_web_file("components/ManualInputs.tsx")
        api = read_web_file("api.ts")

        self.assertIn("settingsOpen", app)
        self.assertIn('aria-label="Ajustes do agente"', app)
        self.assertIn("<ContextPanel", app)
        self.assertIn("agent_runtime", manual_inputs)
        self.assertIn("model_profile", manual_inputs)
        self.assertIn('agent_runtime: "pydantic-ai"', api)
        self.assertIn('model_profile: "qwen3.6:latest"', api)
        self.assertIn("research_lookup: true", api)


if __name__ == "__main__":
    unittest.main()
