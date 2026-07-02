from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


def load_module():
    scripts_dir = Path(__file__).parents[2] / "scripts"
    sys.path.insert(0, str(scripts_dir))
    path = scripts_dir / "build_chatgpt_week_scenario.py"
    spec = importlib.util.spec_from_file_location("build_chatgpt_week_scenario", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ChatGPTWeekScenarioBuilderTest(unittest.TestCase):
    def test_builds_anonymized_week_with_normalized_dates(self) -> None:
        module = load_module()
        raw_html = """
        <html><body>
          <p>Gabriel 10am 100g queijo 315 kcal proteina 23g.</p>
          <p>Na verdade, corrigir queijo para 50g.</p>
          <p>Revisao da semana: social foi o maior problema.</p>
          <p>KFC Double Crunch combo no Brasil estimado.</p>
        </body></html>
        """

        scenario = module.build_scenario(raw_html, source_name="private/export.html")
        days = [action["day"] for action in scenario["actions"] if "day" in action]

        self.assertEqual(scenario["format"], "health-monitor.week-replay")
        self.assertTrue(scenario["anonymized"])
        self.assertEqual(days[0], "2026-07-06")
        self.assertEqual(days[-1], "2026-07-12")
        self.assertIn("correction_request", {action["type"] for action in scenario["actions"]})
        self.assertNotIn("Gabriel", json.dumps(scenario, ensure_ascii=False))

    def test_loads_and_validates_image_refs_from_manifest(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            image_dir = root / "images"
            image_dir.mkdir()
            image = image_dir / "label.jpg"
            image.write_bytes(b"fake image")
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "assets": [
                            {
                                "filename": "images/label.jpg",
                                "review_classification": "nutrition_label",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            refs = module.load_image_refs(manifest)
            scenario = module.build_scenario(
                "<html><body><p>10am queijo 315 kcal</p></body></html>",
                source_name="private/export.html",
                image_refs=refs,
            )

            self.assertEqual(refs, [str(image)])
            module.validate_image_refs(scenario)


if __name__ == "__main__":
    unittest.main()
