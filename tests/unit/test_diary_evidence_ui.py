from __future__ import annotations

import unittest

from tests.unit.frontend_helpers import read_web_file


class DiaryEvidenceUiTest(unittest.TestCase):
    def test_day_card_entries_show_evidence_status_and_confidence(self) -> None:
        types = read_web_file("types.ts")
        day_card = read_web_file("components/DayCard.tsx")
        styles = read_web_file("styles.css")

        self.assertIn("evidence_status: string", types)
        self.assertIn("confidence: number", types)
        self.assertIn("confidenceLabel", day_card)
        self.assertIn("confidence-badge", day_card)
        self.assertIn("entry.confidence", day_card)
        self.assertIn(".confidence-badge", styles)


if __name__ == "__main__":
    unittest.main()
