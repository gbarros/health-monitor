from __future__ import annotations

import unittest

from health_monitor.domain.proposals import CreateDiaryEntriesProposal


class ProposalModelTest(unittest.TestCase):
    def test_created_at_is_generated_per_proposal(self) -> None:
        first = CreateDiaryEntriesProposal(id="proposal_1", person_id="person_1", entries=())
        second = CreateDiaryEntriesProposal(id="proposal_2", person_id="person_1", entries=())

        self.assertIsNot(first.created_at, second.created_at)

    def test_audit_timestamps_start_empty(self) -> None:
        proposal = CreateDiaryEntriesProposal(id="proposal_1", person_id="person_1", entries=())

        self.assertIsNone(proposal.confirmed_at)
        self.assertIsNone(proposal.rejected_at)


if __name__ == "__main__":
    unittest.main()
