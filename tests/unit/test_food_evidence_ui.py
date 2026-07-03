from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MAIN_TS = ROOT / "web" / "src" / "main.ts"
AGENT_CHAT_TS = ROOT / "packages" / "agent-chat-ui" / "src" / "components" / "agent-chat.ts"


class FoodEvidenceUiTest(unittest.TestCase):
    def test_food_library_renders_version_attachment_evidence(self) -> None:
        source = MAIN_TS.read_text(encoding="utf-8")

        self.assertIn("attachments: AttachmentObject[];", source)
        self.assertIn("foodEvidenceLabel(item.attachments)", source)
        self.assertIn("function foodEvidenceLabel", source)
        self.assertIn("attachment.filename", source)
        self.assertIn("label evidence", source)

    def test_label_scan_ui_accepts_multiple_camera_photos_and_barcode_scan(self) -> None:
        source = MAIN_TS.read_text(encoding="utf-8")
        component = AGENT_CHAT_TS.read_text(encoding="utf-8")

        self.assertIn('accept: "image/*"', source)
        self.assertIn("multiple: true", source)
        self.assertIn('name="attachments"', component)
        self.assertIn('type="file"', component)
        self.assertIn('accept="${this.escapeAttribute(composer.accept)}"', component)
        self.assertIn('${composer.multiple ? "multiple" : ""}', component)
        self.assertIn("uploadOptionalAttachments", source)
        self.assertIn("attachment_ids", source)
        self.assertIn("BarcodeDetector", source)
        self.assertIn("getUserMedia", source)
        self.assertIn("agent-chat:composer-action", source)
        self.assertIn('id: "scan-code"', source)

    def test_chat_ui_can_attach_images_for_agent_ocr(self) -> None:
        source = MAIN_TS.read_text(encoding="utf-8")
        component = AGENT_CHAT_TS.read_text(encoding="utf-8")

        self.assertIn("allowAttachments: state.logMode === \"chat\" || state.logMode === \"label\"", source)
        self.assertIn("allowAttachments: true", source)
        self.assertIn('name="attachments"', component)
        self.assertIn("Attached image ids for OCR", source)
        self.assertIn("appendAttachmentIdsToMessage", source)


if __name__ == "__main__":
    unittest.main()
