from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MAIN_TS = ROOT / "web" / "src" / "main.ts"


class FoodEvidenceUiTest(unittest.TestCase):
    def test_food_library_renders_version_attachment_evidence(self) -> None:
        source = MAIN_TS.read_text(encoding="utf-8")

        self.assertIn("attachments: AttachmentObject[];", source)
        self.assertIn("foodEvidenceLabel(item.attachments)", source)
        self.assertIn("function foodEvidenceLabel", source)
        self.assertIn("attachment.filename", source)
        self.assertIn("label evidence", source)


if __name__ == "__main__":
    unittest.main()
