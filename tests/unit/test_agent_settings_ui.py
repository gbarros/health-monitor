from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MAIN_TS = ROOT / "web" / "src" / "main.ts"


class AgentSettingsUiTest(unittest.TestCase):
    def test_text_meal_and_chat_expose_research_lookup_toggle(self) -> None:
        source = MAIN_TS.read_text(encoding="utf-8")

        self.assertIn('input name="research_lookup" type="checkbox" checked', source)
        self.assertIn('research_lookup: form.get("research_lookup") === "on"', source)
        self.assertGreaterEqual(source.count('name="research_lookup"'), 2)


if __name__ == "__main__":
    unittest.main()
