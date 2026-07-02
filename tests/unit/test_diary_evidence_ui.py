from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MAIN_TS = ROOT / "web" / "src" / "main.ts"
STYLES = ROOT / "web" / "src" / "styles.css"


class DiaryEvidenceUiTest(unittest.TestCase):
    def test_day_entries_show_evidence_status_and_confidence(self) -> None:
        source = MAIN_TS.read_text(encoding="utf-8")
        styles = STYLES.read_text(encoding="utf-8")

        self.assertIn("evidence_status: string;", source)
        self.assertIn("confidence: number;", source)
        self.assertIn("evidenceBadge(entry)", source)
        self.assertIn("function evidenceBadge", source)
        self.assertIn("entry.confidence", source)
        self.assertIn(".evidence-badge", styles)


if __name__ == "__main__":
    unittest.main()
