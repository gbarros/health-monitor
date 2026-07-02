from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


def load_module():
    scripts_dir = Path(__file__).parents[2] / "scripts"
    sys.path.insert(0, str(scripts_dir))
    path = scripts_dir / "extract_chatgpt_eval_candidates.py"
    spec = importlib.util.spec_from_file_location("extract_chatgpt_eval_candidates", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ChatGPTEvalCandidateExtractionTest(unittest.TestCase):
    def test_extracts_redacted_eval_candidates_by_kind(self) -> None:
        module = load_module()
        raw_html = """
        <html><body>
          <p>2026-07-01</p>
          <p>Na verdade, corrigir queijo para 50g.</p>
          <p>Revisao da semana: social foi o maior problema.</p>
          <p>Iogurte Batavo nova tabela nutricional porcao 170 g codigo 7891000000000.</p>
          <p>10am 100g queijo 315 kcal proteina 23g.</p>
          <p>KFC Double Crunch combo no Brasil estimado.</p>
        </body></html>
        """

        cases = module.extract_eval_cases(raw_html, source_name="private/export.html")
        kinds = {case["eval_kind"] for case in cases}

        self.assertIn("correction", kinds)
        self.assertIn("review_note", kinds)
        self.assertIn("ambiguity_or_version_reference", kinds)
        self.assertIn("weird_meal_phrasing", kinds)
        self.assertIn("restaurant_or_social_estimate", kinds)
        self.assertTrue(all(case["durable_write"] is False for case in cases))
        self.assertTrue(any("[barcode]" in case["prompt"] for case in cases))
        correction = next(case for case in cases if case["eval_kind"] == "correction")
        self.assertIn("no_direct_mutation", correction["expected_invariants"])


if __name__ == "__main__":
    unittest.main()
