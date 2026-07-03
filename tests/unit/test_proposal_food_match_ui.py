from __future__ import annotations

import unittest

from tests.unit.frontend_helpers import read_web_file


class ProposalFoodMatchUiTest(unittest.TestCase):
    def test_confirming_or_rejecting_proposals_invalidates_day_card_read_models(self) -> None:
        app = read_web_file("App.tsx")
        query_keys = read_web_file("queryKeys.ts")

        self.assertIn("invalidateDailyReadModels", app)
        self.assertIn("queryKeys.daySummary(selectedPersonId, selectedDay)", app)
        self.assertIn("queryKeys.activeGoal(selectedPersonId, selectedDay)", app)
        self.assertIn("queryKeys.weightTrend(selectedPersonId)", app)
        self.assertIn("daySummary", query_keys)
        self.assertIn("activeGoal", query_keys)
        self.assertIn("weightTrend", query_keys)


if __name__ == "__main__":
    unittest.main()
