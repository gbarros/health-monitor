from __future__ import annotations

import unittest

from tests.unit.frontend_helpers import read_web_file


class FoodEvidenceUiTest(unittest.TestCase):
    def test_chat_composer_accepts_attachments_for_agent_ocr_paths(self) -> None:
        chat = read_web_file("components/ChatInterface.tsx")
        runtime = read_web_file("hooks/useAgentRuntime.ts")
        api = read_web_file("api.ts")

        self.assertIn("allowAttachments = true", chat)
        self.assertIn("ThreadUIConfigContext.Provider value={{ placeholder, allowAttachments }}", chat)
        self.assertIn("SimpleImageAttachmentAdapter", runtime)
        self.assertIn("SimpleTextAttachmentAdapter", runtime)
        self.assertIn("uploadMessageAttachments", runtime)
        self.assertIn("uploadDataUrlAttachment", runtime)
        self.assertIn("/api/attachments", api)

    def test_label_scan_quick_action_sends_attachment_backed_chat_intent(self) -> None:
        quick_actions = read_web_file("components/ModesAndTemplates.tsx")
        app = read_web_file("App.tsx")
        runtime = read_web_file("hooks/useAgentRuntime.ts")
        api = read_web_file("api.ts")

        self.assertIn("Escanear rótulo", quick_actions)
        self.assertIn("Código de barras", app)
        self.assertIn('intent: "label_scan"', app)
        self.assertIn("sendAgentChat", app)
        self.assertIn("streamAgentChat", runtime)
        self.assertIn("attachmentIds", runtime)
        self.assertIn("/api/agent/chat", api)
        self.assertIn("/api/agent/chat/stream", api)
        self.assertIn("parseSseEvent", api)
        self.assertIn("AgentChatStreamEvent", api)
        self.assertIn('"run_started"', api)
        self.assertIn("events.push(event)", api)
        self.assertIn("toolProgressLines", runtime)
        self.assertIn("Ferramentas consultadas", runtime)
        self.assertIn("intent: input.intent", api)
        self.assertIn("attachment_ids", api)

    def test_log_food_mode_is_prompt_builder_chat_intent(self) -> None:
        quick_actions = read_web_file("components/ModesAndTemplates.tsx")
        app = read_web_file("App.tsx")

        self.assertIn("Registrar alimento", quick_actions)
        self.assertIn("onLogFoodClick", quick_actions)
        self.assertIn("LogFoodModal", app)
        self.assertIn("Porção consumida", app)
        self.assertIn("Fotos do alimento ou rótulo", app)
        self.assertIn("setFiles(Array.from", app)
        self.assertIn('intent: "log_food"', app)
        self.assertIn("files: input.files", app)
        self.assertIn("sendAgentChat", app)
        self.assertNotIn('setText(template)', quick_actions)

    def test_repeat_meal_mode_is_prompt_builder_chat_intent(self) -> None:
        app = read_web_file("App.tsx")
        api = read_web_file("api.ts")

        self.assertIn("RepeatMealModal", app)
        self.assertIn('intent: "repeat_meal"', app)
        self.assertNotIn("/api/diary/repeat", api)


if __name__ == "__main__":
    unittest.main()
