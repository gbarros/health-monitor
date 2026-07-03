from __future__ import annotations

import unittest

from tests.unit.frontend_helpers import read_web_file


class BackgroundJobUiTest(unittest.TestCase):
    def test_activity_and_history_rails_are_removed_for_chat_first_shell(self) -> None:
        app = read_web_file("App.tsx")
        styles = read_web_file("styles.css")

        self.assertNotIn("ActivityPanel", app)
        self.assertNotIn("HistoryPanel", app)
        self.assertIn("toast", app)
        self.assertIn('role="status"', app)
        self.assertIn(".toast", styles)

    def test_chat_loading_state_does_not_reset_thread_until_history_loaded(self) -> None:
        app = read_web_file("App.tsx")
        styles = read_web_file("styles.css")

        self.assertIn("chatHistoryQuery.isSuccess", app)
        self.assertIn("Carregando conversa", app)
        self.assertIn(".chat-loading", styles)


if __name__ == "__main__":
    unittest.main()
