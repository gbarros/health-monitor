from __future__ import annotations

import json
import unittest

from health_monitor.lookup.labels import (
    parse_ollama_image_inspection_payload,
    parse_ollama_image_set_payload,
)


class ImageAnalysisTest(unittest.TestCase):
    def test_parses_plate_inspection_without_forcing_ocr(self) -> None:
        result = parse_ollama_image_inspection_payload(
            {
                "response": json.dumps(
                    {
                        "description": "Prato com arroz, feijão, salada e frango.",
                        "image_type": "food_plate",
                        "observations": ["arroz", "feijão", "frango"],
                        "visible_text": None,
                        "ocr_recommended": False,
                        "confidence": 0.82,
                        "warnings": ["quantidades não são visíveis"],
                    }
                )
            },
            model="gemma4:26b",
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.image_type, "food_plate")
        self.assertFalse(result.ocr_recommended)
        self.assertEqual(result.source, "ollama_vision:gemma4:26b")

    def test_marks_table_for_follow_up_ocr(self) -> None:
        result = parse_ollama_image_inspection_payload(
            {
                "response": json.dumps(
                    {
                        "description": "Tabela nutricional no verso de uma embalagem.",
                        "image_type": "nutrition_label",
                        "observations": ["há colunas e valores por porção"],
                        "visible_text": "INFORMAÇÃO NUTRICIONAL",
                        "ocr_recommended": "true",
                        "confidence": 0.91,
                        "warnings": [],
                    }
                )
            },
            model="qwen3.6:vision",
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertTrue(result.ocr_recommended)
        self.assertEqual(result.visible_text, "INFORMAÇÃO NUTRICIONAL")

    def test_parses_fenced_cloud_multi_image_result(self) -> None:
        result = parse_ollama_image_set_payload(
            {
                "message": {
                    "content": """```json
{"description":"Three-step tared meal weighing","image_type":"meal_weighing_sequence","images":[],"chronological_attachment_order":[3,2,1],"steps":[{"attachment_index":3,"food":"cooked pumpkin","alternatives":["sweet potato"],"displayed_weight":149,"unit":"g","confidence":0.82,"inedible_mass":"none"},{"attachment_index":2,"food":"cooked beetroot","alternatives":[],"displayed_weight":132,"unit":"g","confidence":0.95,"inedible_mass":"none"},{"attachment_index":1,"food":"roasted meat","alternatives":["chicken","pork"],"displayed_weight":194,"unit":"g","confidence":0.7,"inedible_mass":"possible"}],"questions":["O alimento laranja é abóbora ou batata-doce?","A carne é frango?"],"ocr_recommended":false,"confidence":0.88,"warnings":[]}
```"""
                }
            },
            model="qwen3.5:397b-cloud",
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.chronological_attachment_order, (3, 2, 1))
        self.assertEqual([step["displayed_weight"] for step in result.steps], [149, 132, 194])
        self.assertIn("O alimento laranja é abóbora ou batata-doce?", result.questions)
        self.assertTrue(any("inclui osso" in question for question in result.questions))
        self.assertEqual(result.source, "ollama_vision:qwen3.5:397b-cloud")


if __name__ == "__main__":
    unittest.main()
