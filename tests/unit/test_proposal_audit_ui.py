from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MAIN_TS = ROOT / "web" / "src" / "main.ts"
STYLES = ROOT / "web" / "src" / "styles.css"


class ProposalAuditUiTest(unittest.TestCase):
    def test_proposal_review_shows_lifecycle_audit_fields(self) -> None:
        source = MAIN_TS.read_text(encoding="utf-8")
        styles = STYLES.read_text(encoding="utf-8")

        self.assertIn("created_at: string;", source)
        self.assertIn("confirmed_at: string | null;", source)
        self.assertIn("rejected_at: string | null;", source)
        self.assertIn("renderProposalAudit(state.proposal)", source)
        self.assertIn("type AgentToolCall", source)
        self.assertIn("tool_calls: AgentToolCall[];", source)
        self.assertIn("renderAgentToolTrace(state.proposal)", source)
        self.assertIn("function renderAgentToolTrace", source)
        self.assertIn("superseded_by_proposal_id", source)
        self.assertIn("proposal-load-related", source)
        self.assertIn(".audit-list", styles)
        self.assertIn(".tool-call-list", styles)
        self.assertIn(".tool-status-failed", styles)

    def test_terminal_proposals_do_not_offer_reject_action(self) -> None:
        source = MAIN_TS.read_text(encoding="utf-8")

        self.assertIn('const canReject = state.proposal.status === "draft" || state.proposal.status === "needs_clarification";', source)
        self.assertIn("canReject ? `<button id=\"reject-proposal\"", source)


if __name__ == "__main__":
    unittest.main()
