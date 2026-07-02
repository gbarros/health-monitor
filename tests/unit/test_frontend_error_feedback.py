from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MAIN_TS = ROOT / "web" / "src" / "main.ts"
STYLES = ROOT / "web" / "src" / "styles.css"


class FrontendErrorFeedbackTest(unittest.TestCase):
    def test_async_actions_are_bound_through_error_boundary(self) -> None:
        source = MAIN_TS.read_text(encoding="utf-8")

        self.assertIn("function safeAsync", source)
        self.assertIn("function reportUiError", source)
        self.assertIn('addEventListener("submit", safeAsync(onSetup))', source)
        self.assertIn('addEventListener("click", safeAsync(confirmProposal))', source)

    def test_error_banner_is_accessible_and_distinct_from_success_notice(self) -> None:
        source = MAIN_TS.read_text(encoding="utf-8")
        styles = STYLES.read_text(encoding="utf-8")

        self.assertIn("errorMessage: string | null;", source)
        self.assertIn('role="alert"', source)
        self.assertIn('class="notice notice-error"', source)
        self.assertIn(".notice-error", styles)
        self.assertIn("border-color: #b42318", styles)


if __name__ == "__main__":
    unittest.main()
