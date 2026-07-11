from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class ChatNavigationResilienceTest(unittest.TestCase):
    def test_chat_workspace_stays_mounted_between_top_level_views(self) -> None:
        app = (ROOT / "web/src/App.tsx").read_text()
        styles = (ROOT / "web/src/styles.css").read_text()

        self.assertIn('className="chat-view-host" hidden={activeView !== "chat"}', app)
        self.assertIn(".chat-view-host", styles)
        self.assertIn("height: 100%", styles)

    def test_chat_run_is_not_restarted_when_only_the_route_changes(self) -> None:
        app = (ROOT / "web/src/App.tsx").read_text()

        key_line = 'key={`${selectedPersonId}-${chatReloadKey}-${activeSessionId ?? "none"}`}'
        self.assertIn(key_line, app)
        self.assertNotIn("activeView}-${selectedPersonId", app)


if __name__ == "__main__":
    unittest.main()
