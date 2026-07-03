from __future__ import annotations

import unittest

from tests.unit.frontend_helpers import read_web_file


class ProposalAuditUiTest(unittest.TestCase):
    def test_phase_one_keeps_proposal_writes_confirmation_gated(self) -> None:
        app = read_web_file("App.tsx")
        proposal_card = read_web_file("components/ProposalCard.tsx")
        types = read_web_file("types.ts")

        self.assertIn("created_at?: string", types)
        self.assertIn("confirmed_at?: string", types)
        self.assertIn("rejected_at?: string", types)
        self.assertIn("function DraftProposalDock", app)
        self.assertIn("confirmProposal(proposal.id)", app)
        self.assertIn("rejectProposal(proposal.id)", app)
        self.assertIn("Confirmar", proposal_card)
        self.assertIn("Rejeitar", proposal_card)

    def test_terminal_proposals_are_not_selected_as_active_drafts(self) -> None:
        app = read_web_file("App.tsx")

        self.assertIn('["draft", "needs_clarification"].includes(proposal.status)', app)


if __name__ == "__main__":
    unittest.main()
