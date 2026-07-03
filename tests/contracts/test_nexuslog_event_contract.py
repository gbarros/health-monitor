from __future__ import annotations

import unittest
from io import StringIO

from health_monitor.api.http_api import HttpApi
from health_monitor.application.service import HealthMonitorService
from health_monitor.observability.nexuslog import JsonLineNexusLogSink, NexusLogEvent
from health_monitor.worker import process_available_job


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

    def test_jsonline_sink_writes_nexuslog_compatible_event(self) -> None:
        stream = StringIO()
        sink = JsonLineNexusLogSink(stream)

        sink.emit(
            NexusLogEvent(
                service="health-monitor-api",
                level="info",
                event="api.request.completed",
                payload={"method": "GET", "path": "/api/health", "status_code": 200},
            )
        )

        line = stream.getvalue().strip()
        self.assertIn('"event": "api.request.completed"', line)
        self.assertIn('"status_code": 200', line)

    def test_http_api_emits_sanitized_request_job_agent_and_proposal_events(self) -> None:
        sink = RecordingSink()
        api = HttpApi(HealthMonitorService(), event_sink=sink)

        household = api.handle("POST", "/api/households", {"name": "Casa"}).body
        person = api.handle(
            "POST",
            "/api/people",
            {
                "household_id": household["id"],
                "name": "Gabriel",
                "timezone": "America/Sao_Paulo",
            },
        ).body
        food = api.handle(
            "POST",
            "/api/foods",
            {
                "household_id": household["id"],
                "name": "Queijo Minas",
                "brand": None,
                "version_label": "current",
                "source": "label_scan",
                "nutrients_per_100g": {
                    "calories_kcal": 315,
                    "protein_g": 23,
                    "carbs_g": 2.6,
                    "fat_g": 23.5,
                },
                "aliases": ["queijo"],
            },
        ).body
        proposal = api.service.propose_text_meal(
            person_id=person["id"],
            logged_at_local="2026-07-01T10:00:00",
            text="100g queijo",
            agent_settings={"model_profile": "deterministic-test"},
        )
        api.handle("POST", f"/api/proposals/{proposal.id}/confirm", {})
        api.handle(
            "POST",
            "/api/agent/chat",
            {
                "person_id": person["id"],
                "message": "Pode resumir meu diário?",
                "today": "2026-07-01",
                "agent_settings": {"model_profile": "deterministic-test"},
            },
        )
        api.handle(
            "POST",
            "/api/jobs",
            {
                "job_type": "agent_chat",
                "payload": {
                    "person_id": person["id"],
                    "message": "Pode resumir meu diário amanhã?",
                    "today": "2026-07-02",
                    "agent_settings": {"model_profile": "deterministic-test"},
                },
            },
        )
        api.handle(
            "GET",
            f"/api/lookups/foods?household_id={household['id']}&person_id={person['id']}&phrase=queijo",
            None,
        )

        event_names = [event["event"] for event in sink.events]
        self.assertIn("api.request.completed", event_names)
        self.assertIn("agent.run.completed", event_names)
        self.assertIn("proposal.applied", event_names)
        self.assertIn("food.created", event_names)
        self.assertIn("job.enqueued", event_names)
        self.assertIn("lookup.completed", event_names)

        serialized = repr(sink.events)
        self.assertNotIn("100g queijo", serialized)
        self.assertNotIn("Pode resumir meu diário amanhã?", serialized)
        self.assertIn(food["food"]["id"], serialized)

    def test_worker_processing_emits_job_processed_event(self) -> None:
        sink = RecordingSink()
        service = HealthMonitorService()
        household = service.create_household(name="Casa")
        person = service.create_person(
            household_id=household.id,
            name="Gabriel",
            timezone="America/Sao_Paulo",
        )
        service.enqueue_job(
            job_type="agent_chat",
            payload={
                "person_id": person.id,
                "message": "Pode resumir meu diário?",
                "today": "2026-07-01",
                "agent_settings": {"model_profile": "deterministic-test"},
            },
        )

        job = process_available_job(service, event_sink=sink)

        self.assertIsNotNone(job)
        self.assertEqual(job.status, "succeeded")
        self.assertEqual(sink.events[-1]["event"], "job.processed")
        self.assertEqual(sink.events[-1]["job_id"], job.id)
        self.assertEqual(sink.events[-1]["payload"]["status"], "succeeded")


class RecordingSink:
    def __init__(self) -> None:
        self.events: list[dict[str, object]] = []

    def emit(self, event: NexusLogEvent) -> None:
        self.events.append(event.as_dict())


if __name__ == "__main__":
    unittest.main()
