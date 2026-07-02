from __future__ import annotations

import unittest

from health_monitor.application.service import parse_nutrition_label_text


class NutritionLabelParserTest(unittest.TestCase):
    def test_parses_ocr_markdown_table_with_inferred_product_and_serving(self) -> None:
        parsed = parse_nutrition_label_text(
            "\n".join(
                [
                    "HAMBURGUER CONGELADO DE BOVINO",
                    "HAMBURGUER",
                    "Lote: L9928 9TAB.805",
                    "Data de Validade: 02/07/2026",
                    "Tara da Embalagem: 0,031 Kg 7908421 700666",
                    "INFORMAÇÃO NUTRICIONAL",
                    "Porçãoes por emb: cerca de 2 Porção: 80g (1/2 un)",
                    "| | 100g | 80g | %VD | | 100g | 80g | %VD |",
                    "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
                    "| Valor energético (Kcal) | 233 | 186 | 9 | Gordura totais (g) | 16,7 | 13,4 | 21 |",
                    "| Carboidratos (g) | 0 | 0 | 0 | Gordura saturadas (g) | 6,7 | 5,4 | 27 |",
                    "| Fibras alimentares (g) | 0 | 0 | 0 |",
                    "| Proteinas (g) | 20,6 | 16,4 | 33 | Sódio (mg) | 40 | 32 | 2 |",
                ]
            )
        )

        self.assertEqual(parsed.food_name, "HAMBURGUER CONGELADO DE BOVINO")
        self.assertEqual(parsed.serving_size_g, 80)
        self.assertAlmostEqual(parsed.nutrients_per_100g.calories_kcal, 232.5)
        self.assertAlmostEqual(parsed.nutrients_per_100g.protein_g, 20.5)
        self.assertAlmostEqual(parsed.nutrients_per_100g.carbs_g, 0)
        self.assertAlmostEqual(parsed.nutrients_per_100g.fat_g, 16.75)
        self.assertAlmostEqual(parsed.nutrients_per_100g.fiber_g, 0)
        self.assertAlmostEqual(parsed.nutrients_per_100g.sodium_mg, 40)


if __name__ == "__main__":
    unittest.main()
