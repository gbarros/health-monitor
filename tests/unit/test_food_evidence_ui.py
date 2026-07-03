from __future__ import annotations

import unittest

from tests.unit.frontend_helpers import read_web_file


class FoodEvidenceUiTest(unittest.TestCase):
    def test_chat_composer_accepts_attachments_for_agent_ocr_paths(self) -> None:
        chat = read_web_file("components/ChatInterface.tsx")
        runtime = read_web_file("hooks/useAgentRuntime.ts")
        api = read_web_file("api.ts")

        self.assertIn("allowAttachments: true", chat)
        self.assertIn("SimpleImageAttachmentAdapter", runtime)
        self.assertIn("SimpleTextAttachmentAdapter", runtime)
        self.assertIn("uploadMessageAttachments", runtime)
        self.assertIn("uploadDataUrlAttachment", runtime)
        self.assertIn("/api/attachments", api)

    def test_label_scan_quick_action_routes_to_attachment_backed_label_endpoint(self) -> None:
        quick_actions = read_web_file("components/ModesAndTemplates.tsx")
        app = read_web_file("App.tsx")
        runtime = read_web_file("hooks/useAgentRuntime.ts")
        api = read_web_file("api.ts")

        self.assertIn("Escanear rótulo", quick_actions)
        self.assertIn("Código de barras", app)
        self.assertIn("draftLabelScan", app)
        self.assertIn("sendAgentChat", runtime)
        self.assertIn("attachmentIds", runtime)
        self.assertIn("/api/agent/chat", api)
        self.assertIn("attachment_ids", api)


if __name__ == "__main__":
    unittest.main()
