from __future__ import annotations

import inspect
import unittest

from health_monitor.application.service import HealthMonitorService


class AgentFirstChatSurfaceTest(unittest.TestCase):
    def test_chat_does_not_route_through_legacy_text_parsers(self) -> None:
        source = inspect.getsource(HealthMonitorService.chat)

        self.assertIn("_agent_context_message", source)
        self.assertIn("_try_pydantic_ai_chat", source)
        self.assertNotIn("propose_text_meal", source)
        self.assertNotIn("parse_text_meal", source)
        self.assertNotIn("parse_chat_", source)
        self.assertNotIn("text_looks_like", source)

    def test_service_has_no_chat_parser_heuristic_symbols(self) -> None:
        members = set(dir(HealthMonitorService))

        self.assertFalse({name for name in members if name.startswith("parse_chat_")})
        self.assertFalse({name for name in members if name.startswith("text_looks_like")})


if __name__ == "__main__":
    unittest.main()
