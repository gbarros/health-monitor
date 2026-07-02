from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MAIN_TS = ROOT / "web" / "src" / "main.ts"


class AgentSettingsUiTest(unittest.TestCase):
    def test_chat_form_and_log_adapter_enable_research_lookup(self) -> None:
        source = MAIN_TS.read_text(encoding="utf-8")

        self.assertIn('input name="research_lookup" type="checkbox" checked', source)
        self.assertIn('research_lookup: form.get("research_lookup") === "on"', source)
        self.assertGreaterEqual(source.count("research_lookup: true"), 2)


if __name__ == "__main__":
    unittest.main()
