from __future__ import annotations

import unittest

from tests.unit.frontend_helpers import read_web_file


class FrontendErrorFeedbackTest(unittest.TestCase):
    def test_async_errors_surface_as_accessible_toasts_or_inline_errors(self) -> None:
        app = read_web_file("App.tsx")
        styles = read_web_file("styles.css")

        self.assertIn("onRuntimeError", app)
        self.assertIn("setToast", app)
        self.assertIn('role="status"', app)
        self.assertIn('aria-live="polite"', app)
        self.assertIn("form-error", app)
        self.assertIn(".form-error", styles)
        self.assertIn(".toast", styles)


if __name__ == "__main__":
    unittest.main()
