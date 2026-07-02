from __future__ import annotations

import base64
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


def load_module():
    path = Path(__file__).parents[2] / "scripts" / "extract_chatgpt_image_assets.py"
    spec = importlib.util.spec_from_file_location("extract_chatgpt_image_assets", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def tiny_jpeg(width: int = 32, height: int = 24) -> bytes:
    return (
        b"\xff\xd8"
        b"\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
        b"\xff\xc0\x00\x11\x08"
        + height.to_bytes(2, "big")
        + width.to_bytes(2, "big")
        + b"\x03\x01\x11\x00\x02\x11\x00\x03\x11\x00"
        b"\xff\xd9"
    )


class ChatGPTImageAssetExtractionTest(unittest.TestCase):
    def test_extracts_data_images_to_private_manifest_shape(self) -> None:
        module = load_module()
        encoded = base64.b64encode(tiny_jpeg()).decode("ascii")
        raw_html = (
            "<html><body><p>Produto Iogurte codigo 7891000000000 user@test.com</p>"
            f'<img src="data:image/jpeg;base64,{encoded}" />'
            "<p>Proteinas 15 g</p></body></html>"
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "chatgpt-assets"
            assets = module.extract_assets(raw_html, output_dir=output_dir)
            payload = module.manifest_payload(
                assets,
                source=Path("private/export.html"),
                output_dir=output_dir,
            )

            self.assertEqual(len(assets), 1)
            self.assertEqual(assets[0].width_px, 32)
            self.assertEqual(assets[0].height_px, 24)
            self.assertTrue((output_dir / assets[0].filename).exists())
            self.assertIn("[barcode]", assets[0].nearby_text_redacted)
            self.assertIn("[email]", assets[0].nearby_text_redacted)
            self.assertEqual(payload["format"], "health-monitor.chatgpt-image-assets")
            self.assertEqual(payload["assets"][0]["review_classification"], "unreviewed")


if __name__ == "__main__":
    unittest.main()
