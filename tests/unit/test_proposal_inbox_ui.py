from __future__ import annotations

import unittest

from tests.unit.frontend_helpers import read_web_file


class ProposalInboxUiTest(unittest.TestCase):
    def test_proposals_are_person_scoped_and_not_rendered_as_a_right_rail(self) -> None:
        app = read_web_file("App.tsx")
        api = read_web_file("api.ts")

        self.assertIn("loadProposals(selectedPersonId", app)
        self.assertIn("queryKeys.proposals(selectedPersonId)", app)
        self.assertIn("upsertProposal", app)
        self.assertIn("/api/proposals?person_id=", api)
        self.assertNotIn("proposal-inbox", app)
        self.assertNotIn("ProposalPanel", app)


if __name__ == "__main__":
    unittest.main()
