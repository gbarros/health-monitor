from __future__ import annotations

import unittest

from tests.unit.frontend_helpers import read_web_file


class ReviewChartUiTest(unittest.TestCase):
    def test_desktop_phase_one_reserves_week_view_without_fake_chart_data(self) -> None:
        app = read_web_file("App.tsx")
        styles = read_web_file("styles.css")

        self.assertIn("desktop-read-column", app)
        self.assertIn("week-placeholder", app)
        self.assertIn("Visão semanal entra na fase 5.", app)
        self.assertIn(".desktop-read-column", styles)
        self.assertIn(".week-placeholder", styles)
        self.assertNotIn("renderMacroChart", app)
        self.assertNotIn("renderWeightTrendChart", app)


if __name__ == "__main__":
    unittest.main()
