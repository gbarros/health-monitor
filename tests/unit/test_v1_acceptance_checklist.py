from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CHECKLIST = ROOT / "docs" / "v1-acceptance-checklist.md"


class V1AcceptanceChecklistTest(unittest.TestCase):
    def test_checklist_maps_all_scoped_features_to_evidence(self) -> None:
        source = CHECKLIST.read_text(encoding="utf-8")

        for index in range(1, 20):
            self.assertIn(f"F-{index:03d}", source)
        self.assertIn("Evidence", source)
        self.assertIn("Remaining", source)
        self.assertIn("PydanticAI/Ollama runtime", source)
        self.assertIn("ChatGPT history evidence tooling", source)


if __name__ == "__main__":
    unittest.main()
