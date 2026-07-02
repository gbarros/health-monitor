from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


def load_module():
    path = Path(__file__).parents[2] / "scripts" / "update_chatgpt_image_classification.py"
    spec = importlib.util.spec_from_file_location("update_chatgpt_image_classification", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ChatGPTImageClassificationTest(unittest.TestCase):
    def test_updates_selected_assets_only(self) -> None:
        module = load_module()
        manifest = {
            "assets": [
                {"id": "chatgpt_image_001", "review_classification": "unreviewed"},
                {"id": "chatgpt_image_002", "review_classification": "unreviewed"},
            ]
        }

        changed = module.update_manifest(
            manifest,
            asset_ids={"chatgpt_image_002"},
            classification="nutrition_label",
        )

        self.assertEqual(changed, 1)
        self.assertEqual(manifest["assets"][0]["review_classification"], "unreviewed")
        self.assertEqual(manifest["assets"][1]["review_classification"], "nutrition_label")

    def test_rejects_unknown_classification(self) -> None:
        module = load_module()
        with self.assertRaisesRegex(ValueError, "unsupported classification"):
            module.update_manifest(
                {"assets": []},
                asset_ids={"chatgpt_image_001"},
                classification="private_label",
            )


if __name__ == "__main__":
    unittest.main()
