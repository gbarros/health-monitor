from __future__ import annotations

import unittest

from tests.unit.frontend_helpers import read_web_file


class AgentChatHistoryUiTest(unittest.TestCase):
    def test_agent_chat_history_hydrates_assistant_ui_thread(self) -> None:
        app = read_web_file("App.tsx")
        runtime = read_web_file("hooks/useAgentRuntime.ts")
        api = read_web_file("api.ts")

        self.assertIn("loadChatHistory", app)
        self.assertIn("queryKeys.chatHistory(selectedPersonId)", app)
        self.assertIn("initialMessages = useMemo<ThreadMessageLike[]>", app)
        self.assertIn("turn.user_message", app)
        self.assertIn("turn.assistant_message", app)
        self.assertIn("/api/agent/chat-history?person_id=", api)
        self.assertIn("initialMessages", runtime)
        self.assertIn("useLocalRuntime(adapter", runtime)


if __name__ == "__main__":
    unittest.main()
