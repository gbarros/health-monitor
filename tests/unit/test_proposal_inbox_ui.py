from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MAIN_TS = ROOT / "web" / "src" / "main.ts"
STYLES = ROOT / "web" / "src" / "styles.css"


class ProposalInboxUiTest(unittest.TestCase):
    def test_proposal_inbox_lists_recent_person_scoped_proposals(self) -> None:
        source = MAIN_TS.read_text(encoding="utf-8")
        styles = STYLES.read_text(encoding="utf-8")

        self.assertIn("proposalQueue: Proposal[];", source)
        self.assertIn("renderProposalInbox()", source)
        self.assertIn("refreshProposals", source)
        self.assertIn("/api/proposals?person_id=", source)
        self.assertIn("proposal-open", source)
        self.assertIn(".proposal-inbox-list", styles)

    def test_profile_switch_clears_proposal_inbox(self) -> None:
        source = MAIN_TS.read_text(encoding="utf-8")

        self.assertIn("state.proposalQueue = [];", source)


if __name__ == "__main__":
    unittest.main()
