from __future__ import annotations

import unittest
from datetime import datetime

from health_monitor.application.service import (
    parse_text_meal_amendment,
    parse_text_meal_items,
)

NOON = datetime(2026, 7, 3, 12, 0)


class ParseTextMealItemsTest(unittest.TestCase):
    def test_slash_separated_items(self) -> None:
        _, items = parse_text_meal_items(
            "Almoço: 74g arroz / 139g feijão preto / 113g sobrecoxa",
            default_logged_at=NOON,
        )
        self.assertEqual([item.phrase for item in items], ["arroz", "feijão preto", "sobrecoxa"])
        self.assertEqual([item.quantity_g for item in items], [74.0, 139.0, 113.0])

    def test_discount_line_applies_to_preceding_item(self) -> None:
        _, items = parse_text_meal_items(
            "Almoço:\n74g arroz\n113g sobrecoxa\n-33g ossos e pele",
            default_logged_at=NOON,
        )
        self.assertEqual(len(items), 2)
        self.assertEqual(items[1].phrase, "sobrecoxa")
        self.assertEqual(items[1].quantity_g, 80.0)
        self.assertEqual(items[1].evidence["quantity_discount_g"], 33.0)

    def test_discount_without_preceding_item_raises(self) -> None:
        with self.assertRaises(ValueError):
            parse_text_meal_items("-33g ossos e pele", default_logged_at=NOON)

    def test_discount_larger_than_item_raises(self) -> None:
        with self.assertRaises(ValueError):
            parse_text_meal_items(
                "Almoço:\n30g sobrecoxa\n-33g ossos", default_logged_at=NOON
            )


class ParseTextMealAmendmentTest(unittest.TestCase):
    def test_forgot_to_include_grammar(self) -> None:
        additions, removals = parse_text_meal_amendment("Ah, esqueci de incluir 100g de manga")
        self.assertEqual(additions, "100g manga")
        self.assertEqual(removals, [])

    def test_faltou_incluir_grammar(self) -> None:
        additions, removals = parse_text_meal_amendment("faltou incluir 30g de farofa")
        self.assertEqual(additions, "30g farofa")
        self.assertEqual(removals, [])

    def test_subtraction_verbs(self) -> None:
        additions, removals = parse_text_meal_amendment("subtrai 68g de peixe")
        self.assertEqual(additions, "")
        self.assertEqual(len(removals), 1)
        self.assertEqual(removals[0].phrase, "peixe")
        self.assertEqual(removals[0].quantity_g, 68.0)

    def test_leading_dash_removal(self) -> None:
        _, removals = parse_text_meal_amendment("-33g ossos e pele")
        self.assertEqual(len(removals), 1)
        self.assertEqual(removals[0].quantity_g, 33.0)

    def test_slash_separated_amendment(self) -> None:
        additions, removals = parse_text_meal_amendment(
            "adicione 100g de manga / subtrai 30g de arroz"
        )
        self.assertEqual(additions, "100g manga")
        self.assertEqual(len(removals), 1)
        self.assertEqual(removals[0].phrase, "arroz")


if __name__ == "__main__":
    unittest.main()
