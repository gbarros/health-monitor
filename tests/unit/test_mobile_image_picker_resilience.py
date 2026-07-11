from __future__ import annotations

import json
import unittest

from tests.unit.frontend_helpers import WEB_PUBLIC, read_web_file


class MobileImagePickerResilienceTest(unittest.TestCase):
    def test_installed_app_relaunches_into_chat(self) -> None:
        manifest = json.loads((WEB_PUBLIC / "manifest.webmanifest").read_text(encoding="utf-8"))

        self.assertEqual(manifest["start_url"], "/chat")

    def test_phone_preview_has_api_proxy_without_dev_hmr(self) -> None:
        config = (WEB_PUBLIC.parent / "vite.config.ts").read_text(encoding="utf-8")

        self.assertIn("preview:", config)
        self.assertIn('port: 5173', config)
        self.assertIn('const apiProxyTarget = `http://127.0.0.1:${apiProxyPort}`', config)
        self.assertIn('"/api": apiProxy', config)
        self.assertIn("proxyTimeout: 10 * 60 * 1000", config)

    def test_composer_uses_a_native_file_input_and_restores_text(self) -> None:
        chat = read_web_file("components/ChatInterface.tsx")
        attachment = read_web_file("components/assistant-ui/attachment.tsx")

        self.assertIn("ComposerDraftPersistence", chat)
        self.assertIn("health-monitor.composer-draft", chat)
        self.assertIn('type="file"', attachment)
        self.assertIn('aria-label="Anexar foto ou arquivo"', attachment)
        self.assertNotIn("inputRef.current?.click()", attachment)
        self.assertNotIn("URL.createObjectURL", attachment)
        self.assertNotIn("<AvatarImage", attachment)
        self.assertIn("aui-attachment-tile-image-icon", attachment)
        self.assertIn("<TooltipProvider", attachment)
        self.assertIn("<Tooltip>", attachment)
        self.assertNotIn("indexedDB", chat)

    def test_image_mini_forms_restore_their_open_flow_and_text(self) -> None:
        app = read_web_file("App.tsx")

        self.assertIn("readActiveImageFlow(personId)", app)
        self.assertIn('restoredImageFlow === "log_food"', app)
        self.assertIn('restoredImageFlow === "label_scan"', app)
        self.assertIn("readJsonDraft", app)
        self.assertIn("imageFlowFormDraftKey", app)


if __name__ == "__main__":
    unittest.main()
