from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MAIN_TS = ROOT / "web" / "src" / "main.ts"


class ProposalFoodMatchUiTest(unittest.TestCase):
    def test_draft_proposal_entry_can_select_food_version(self) -> None:
        source = MAIN_TS.read_text(encoding="utf-8")

        self.assertIn("function proposalFoodOptions", source)
        self.assertIn('name="food_version_id"', source)
        self.assertIn("proposalFoodOptions(entry)", source)
        self.assertIn('food_version_id: requiredText(form, "food_version_id")', source)


if __name__ == "__main__":
    unittest.main()
