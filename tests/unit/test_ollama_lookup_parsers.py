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
