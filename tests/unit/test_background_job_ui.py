from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MAIN_TS = ROOT / "web" / "src" / "main.ts"
STYLES = ROOT / "web" / "src" / "styles.css"


class BackgroundJobUiTest(unittest.TestCase):
    def test_frontend_polls_until_background_jobs_settle(self) -> None:
        source = MAIN_TS.read_text(encoding="utf-8")
        styles = STYLES.read_text(encoding="utf-8")

        self.assertIn("let jobPollTimer", source)
        self.assertIn("function syncJobPolling", source)
        self.assertIn("function hasActiveJobs", source)
        self.assertIn("window.setInterval", source)
        self.assertIn("window.clearInterval", source)
        self.assertIn("syncJobPolling();", source)
        self.assertIn("job-status-active", source)
        self.assertIn(".job-status-active", styles)

    def test_completed_chat_jobs_can_open_saved_chat_turn(self) -> None:
        source = MAIN_TS.read_text(encoding="utf-8")

        self.assertIn('typeof job.result.chat_turn_id === "string"', source)
        self.assertIn("job-open-chat", source)
        self.assertIn("onJobOpenChat", source)
        self.assertIn("state.chatHistory.find((turn) => turn.id === chatTurnId)", source)


if __name__ == "__main__":
    unittest.main()
