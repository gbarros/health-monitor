from __future__ import annotations

import unittest
from datetime import datetime

from health_monitor.application.service import (
    parse_chat_weight_entry,
    parse_text_meal_amendment,
    parse_text_meal_items,
    remove_chat_weight_lines,
    text_looks_like_chat_meal_log,
    text_looks_like_meal_amendment,
)

NOON = datetime(2026, 7, 3, 12, 0)


class ParseChatWeightEntryTest(unittest.TestCase):
    def test_weigh_in_shapes_from_real_usage(self) -> None:
        cases = {
            "amanheci com 96,3kg": 96.3,
            "Novo peso: 97.2kg": 97.2,
            "hoje me pesei e estou com 95.5 kgs": 95.5,
            "Dia 5: 97,7 kg ao acordar": 97.7,
            "pesei 98 hoje cedo": 98.0,
            "meu peso é 96": 96.0,
            "Bom dia! 18 de junho - 96.4kgs": 96.4,
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(parse_chat_weight_entry(text), expected)

    def test_questions_and_non_weigh_ins_are_ignored(self) -> None:
        cases = (
            "qual era meu peso em 2025?",
            "meu peso está estável há 30 dias?",
            "quanto de proteina tem 100g de arroz? peso seco",
            "consegue calcular meu peso alvo de 90kg?",
            "Almoço: 74g arroz, 139g feijão",
            "usei 250g de carne para 1 kg de feijão",
            "a meta é manter o peso até dezembro",
        )
        for text in cases:
            with self.subTest(text=text):
                self.assertIsNone(parse_chat_weight_entry(text))

    def test_remove_chat_weight_lines_keeps_the_meal(self) -> None:
        text = "Bom dia! amanheci com 96,4kg\nCafé da manhã:\n100g de ovos mexidos"
        self.assertEqual(
            remove_chat_weight_lines(text),
            "Café da manhã:\n100g de ovos mexidos",
        )


class MealAmendmentClassifierTest(unittest.TestCase):
    def test_meal_heading_always_means_new_meal(self) -> None:
        cases = (
            "Almoço:\n74g arroz\n139g feijão\n113g sobrecoxa\n-33g ossos e pele",
            "Janta:\n100g de frango cozido\n-20g de ossos",
            "Café da manhã: 100g de ovos mexidos",
            "Lanche: 120g de iogurte caseiro",
        )
        for text in cases:
            with self.subTest(text=text):
                self.assertFalse(text_looks_like_meal_amendment(text))
                self.assertTrue(text_looks_like_chat_meal_log(text))

    def test_amendment_shapes_from_real_usage(self) -> None:
        cases = (
            "Ah, esqueci de incluir 100g de manga",
            "esqueci as duas fatias de pão",
            "tinha esquecido de anexar 30g de farofa",
            "adicione 113g de manga",
            "subtrai 68g de peixe",
            "-33g de ossos",
            "inclua 60ml? não, 60g de concentrado",
            "faltou 1 ovo frito",
        )
        for text in cases:
            with self.subTest(text=text):
                self.assertTrue(text_looks_like_meal_amendment(text))

    def test_plain_questions_are_not_meal_logs(self) -> None:
        cases = (
            "quanto ainda tenho hoje?",
            "como está o dia?",
            "qual pizza encaixa melhor no meu dia?",
        )
        for text in cases:
            with self.subTest(text=text):
                self.assertFalse(text_looks_like_chat_meal_log(text))


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
