from __future__ import annotations

import unittest

from tests.unit.frontend_helpers import read_web_file


class FoodFilterUiTest(unittest.TestCase):
    def test_phase_one_replaces_food_library_filter_forms_with_chat_quick_actions(self) -> None:
        quick_actions = read_web_file("components/ModesAndTemplates.tsx")
        app = read_web_file("App.tsx")

        self.assertIn("QuickActionRow", quick_actions)
        self.assertIn("Registrar refeição", quick_actions)
        self.assertIn("Receita/lote", quick_actions)
        self.assertIn("Escanear rótulo", quick_actions)
        self.assertIn("<QuickActionRow", app)
        self.assertNotIn("food-filter", app)


if __name__ == "__main__":
    unittest.main()
