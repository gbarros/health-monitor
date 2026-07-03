from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MAIN_TS = ROOT / "web" / "src" / "main.ts"


class AgentSettingsUiTest(unittest.TestCase):
    def test_component_backed_agent_paths_enable_research_lookup(self) -> None:
        source = MAIN_TS.read_text(encoding="utf-8")

        self.assertIn("function submitAgentChatFromComponent", source)
        self.assertIn("workAgentChat.data = workAgentState()", source)
        self.assertGreaterEqual(source.count("research_lookup: true"), 2)


if __name__ == "__main__":
    unittest.main()
