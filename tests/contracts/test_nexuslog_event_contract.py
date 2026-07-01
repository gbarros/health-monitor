from __future__ import annotations

import unittest

from health_monitor.observability.nexuslog import NexusLogEvent


class NexusLogEventContractTest(unittest.TestCase):
    def test_event_shape_contains_required_fields_and_correlations(self) -> None:
        event = NexusLogEvent(
            service="health-monitor-api",
            level="info",
            event="proposal.applied",
            entity_type="proposal",
            entity_id="proposal_1",
            request_id="req_1",
            session_id="sess_1",
            job_id="job_1",
            payload={
                "message": "Proposal applied",
                "proposal_id": "proposal_1",
                "person_id": "person_1",
                "duration_ms": 42,
            },
        ).as_dict()

        self.assertIn("ts", event)
        self.assertEqual(event["service"], "health-monitor-api")
        self.assertEqual(event["level"], "info")
        self.assertEqual(event["event"], "proposal.applied")
        self.assertEqual(event["entity_type"], "proposal")
        self.assertEqual(event["entity_id"], "proposal_1")
        self.assertEqual(event["request_id"], "req_1")
        self.assertEqual(event["payload"]["person_id"], "person_1")

    def test_event_payload_rejects_secret_like_keys(self) -> None:
        event = NexusLogEvent(
            service="health-monitor-api",
            level="info",
            event="agent.run.started",
            payload={"api_key": "should-not-log"},
        )

        with self.assertRaises(ValueError):
            event.as_dict()


if __name__ == "__main__":
    unittest.main()

