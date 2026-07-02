from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MAIN_TS = ROOT / "web" / "src" / "main.ts"


class FoodContextUiTest(unittest.TestCase):
    def test_food_labels_show_default_and_last_used_context(self) -> None:
        source = MAIN_TS.read_text(encoding="utf-8")

        self.assertIn("is_default: boolean;", source)
        self.assertIn("last_used_at: string | null;", source)
        self.assertIn("foodContextLabel(item)", source)
        self.assertIn("function foodContextLabel", source)
        self.assertIn("current default", source)
        self.assertIn("last used", source)


if __name__ == "__main__":
    unittest.main()
