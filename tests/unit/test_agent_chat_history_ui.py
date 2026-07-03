from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MAIN_TS = ROOT / "web" / "src" / "main.ts"
STYLES = ROOT / "web" / "src" / "styles.css"


class AgentChatHistoryUiTest(unittest.TestCase):
    def test_agent_chat_history_is_fetched_and_rendered(self) -> None:
        source = MAIN_TS.read_text(encoding="utf-8")
        styles = STYLES.read_text(encoding="utf-8")

        self.assertIn("type AgentChatTurn", source)
        self.assertIn("chatHistory: AgentChatTurn[];", source)
        self.assertIn("function workAgentMessages()", source)
        self.assertIn('<agent-chat id="work-agent-chat"></agent-chat>', source)
        self.assertIn("workAgentChat.data = workAgentState()", source)
        self.assertIn("/api/agent/chat-history?person_id=", source)
        self.assertIn("state.chatHistory = await apiGet<AgentChatTurn[]>", source)
        self.assertIn(".chat-answer", styles)


if __name__ == "__main__":
    unittest.main()
