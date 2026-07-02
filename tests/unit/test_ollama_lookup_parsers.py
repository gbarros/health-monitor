from __future__ import annotations

import json
import unittest

from health_monitor.lookup.estimates import parse_ollama_estimate_payload
from health_monitor.lookup.labels import parse_ollama_label_payload


class OllamaLookupParserTest(unittest.TestCase):
    def test_estimate_parser_accepts_strict_json_with_fiber_and_sodium(self) -> None:
        payload = {
            "response": json.dumps(
                {
                    "food_name": "KFC Double Crunch combo",
                    "calories_kcal": 260,
                    "protein_g": 11,
                    "carbs_g": 24,
                    "fat_g": 13,
                    "fiber_g": 2,
                    "sodium_mg": 820,
                    "confidence": 0.42,
                    "notes": "Regional restaurant estimate.",
                }
            )
        }

        estimate = parse_ollama_estimate_payload(
            payload,
            phrase="kfc double crunch combo",
            model="qwen3",
        )

        self.assertIsNotNone(estimate)
        assert estimate is not None
        self.assertEqual(estimate.food_name, "KFC Double Crunch combo")
        self.assertEqual(estimate.nutrients_per_100g.fiber_g, 2)
        self.assertEqual(estimate.nutrients_per_100g.sodium_mg, 820)
        self.assertEqual(estimate.source, "ollama:qwen3")

    def test_estimate_parser_returns_none_for_malformed_model_output(self) -> None:
        self.assertIsNone(
            parse_ollama_estimate_payload(
                {"response": "not json"},
                phrase="unknown food",
                model="qwen3",
            )
        )

    def test_label_parser_accepts_brazilian_label_ocr_json(self) -> None:
        payload = {
            "response": json.dumps(
                {
                    "text": "\n".join(
                        [
                            "Produto: Iogurte Batavo Protein",
                            "Porcao: 170 g",
                            "Valor energetico: 120 kcal",
                            "Codigo de barras: 7891000000000",
                        ]
                    ),
                    "confidence": 0.88,
                    "warnings": ["review sodium manually"],
                }
            )
        }

        extraction = parse_ollama_label_payload(payload, model="llava")

        self.assertIsNotNone(extraction)
        assert extraction is not None
        self.assertEqual(extraction.source, "ollama_vision:llava")
        self.assertEqual(extraction.confidence, 0.88)
        self.assertIn("Codigo de barras", extraction.text)
        self.assertEqual(extraction.warnings, ("review sodium manually",))

    def test_label_parser_returns_none_for_empty_text(self) -> None:
        self.assertIsNone(
            parse_ollama_label_payload(
                {"response": json.dumps({"text": "", "confidence": 0.2})},
                model="llava",
            )
        )

    def test_label_parser_accepts_table_json_from_thinking_field(self) -> None:
        extraction = parse_ollama_label_payload(
            {
                "response": "",
                "thinking": json.dumps(
                    {
                        "table": [
                            {
                                "row1_cell_0": "",
                                "row1_cell_1": "100 ml",
                                "row1_cell_2": "250 ml",
                            },
                            {
                                "row2_cell_0": "Valor energético (kcal)",
                                "row2_cell_1": "70",
                                "row2_cell_2": "174",
                            },
                            {
                                "row3_cell_0": "Proteínas (g)",
                                "row3_cell_1": "9,2",
                                "row3_cell_2": "23",
                            },
                        ]
                    }
                ),
            },
            model="qwen3.5:latest",
        )

        self.assertIsNotNone(extraction)
        assert extraction is not None
        self.assertIn("Valor energético", extraction.text)
        self.assertIn("Proteínas", extraction.text)

    def test_label_parser_accepts_qwen35_irregular_ocr_shapes(self) -> None:
        embedded = parse_ollama_label_payload(
            {
                "response": "",
                "thinking": json.dumps(
                    {
                        "text": json.dumps(
                            [
                                {"Porcao": "50 g"},
                                {"Valor energetico": "126 kcal"},
                                {"Proteinas": "4.2 g"},
                            ]
                        ),
                        "confidence": [0.97],
                        "warnings": [],
                    }
                ),
            },
            model="qwen3.5:latest",
        )
        text_content = parse_ollama_label_payload(
            {
                "response": "",
                "thinking": json.dumps(
                    {
                        "text_content": "Porção: 250 ml Valor energético 70 Proteínas 9,2",
                    }
                ),
            },
            model="qwen3.5:latest",
        )

        self.assertIsNotNone(embedded)
        self.assertIsNotNone(text_content)
        assert embedded is not None
        assert text_content is not None
        self.assertEqual(embedded.confidence, 0.97)
        self.assertIn("Valor energetico: 126 kcal", embedded.text)
        self.assertIn("Proteínas", text_content.text)

    def test_label_parser_flattens_nested_ocr_dicts(self) -> None:
        extraction = parse_ollama_label_payload(
            {
                "response": "",
                "thinking": json.dumps(
                    {
                        "Serving Size (Porção)": "250 ml",
                        "Nutritional Information per Serving": {
                            "Calories (Valor energético)": "174 kcal",
                            "Proteins (Proteínas)": "23 g",
                            "Salt/Sodium (Sódio)": "337 mg",
                        },
                    }
                ),
            },
            model="qwen3.5:latest",
        )

        self.assertIsNotNone(extraction)
        assert extraction is not None
        self.assertIn("Valor energético", extraction.text)
        self.assertIn("Proteínas", extraction.text)

    def test_parsers_accept_fenced_json_model_output(self) -> None:
        estimate = parse_ollama_estimate_payload(
            {
                "response": "```json\n"
                + json.dumps(
                    {
                        "food_name": "Arroz branco",
                        "calories_kcal": 130,
                        "protein_g": 2.7,
                        "carbs_g": 28,
                        "fat_g": 0.3,
                        "fiber_g": 0.4,
                        "sodium_mg": 1,
                        "confidence": 0.5,
                        "notes": "generic estimate",
                    }
                )
                + "\n```"
            },
            phrase="arroz",
            model="ornith:9b",
        )
        label = parse_ollama_label_payload(
            {
                "response": "```\n"
                + json.dumps(
                    {
                        "text": "Produto: Leite proteico\nProteinas: 20 g",
                        "confidence": 0.7,
                        "warnings": "sodium not visible",
                    }
                )
                + "\n```"
            },
            model="llava",
        )

        self.assertIsNotNone(estimate)
        self.assertIsNotNone(label)
        assert estimate is not None
        assert label is not None
        self.assertEqual(estimate.food_name, "Arroz branco")
        self.assertEqual(label.warnings, ("sodium not visible",))


if __name__ == "__main__":
    unittest.main()
