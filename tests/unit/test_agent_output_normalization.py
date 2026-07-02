from __future__ import annotations

import unittest

from health_monitor.agent.runtime import (
    AgentAnswerOutput,
    AgentProposalDraftOutput,
    normalize_agent_runtime_output,
)


class AgentOutputNormalizationTest(unittest.TestCase):
    def test_normalizes_json_answer_payload(self) -> None:
        response = normalize_agent_runtime_output(
            '{"output_type":"answer","message":"Day summary grounded in diary.","confidence":0.81,'
            '"citations":[{"record_type":"diary_entry","record_id":"entry_1"}]}'
        )

        self.assertEqual(response.output_type, "answer")
        self.assertEqual(response.behavior_label, "pydantic_ai_answer")
        self.assertEqual(response.confidence, 0.81)
        self.assertEqual(response.citations, ({"record_type": "diary_entry", "record_id": "entry_1"},))

    def test_normalizes_proposal_payload(self) -> None:
        response = normalize_agent_runtime_output(
            {
                "output_type": "proposal_draft",
                "proposal_id": "proposal_1",
                "summary": "Draft ready",
            }
        )

        self.assertEqual(response.behavior_label, "proposal_draft")
        self.assertEqual(response.proposal_id, "proposal_1")
        self.assertEqual(response.message, "Draft ready")

    def test_normalizes_structured_dataclass_outputs(self) -> None:
        answer = normalize_agent_runtime_output(AgentAnswerOutput(message="Answer"))
        proposal = normalize_agent_runtime_output(
            AgentProposalDraftOutput(
                proposal_id="proposal_2",
                proposal_type="diary_entries",
                proposal_status="draft",
                summary="Draft",
            )
        )

        self.assertEqual(answer.message, "Answer")
        self.assertEqual(proposal.proposal_id, "proposal_2")


if __name__ == "__main__":
    unittest.main()
