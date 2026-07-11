from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from health_monitor.api.http_api import HttpApi
from health_monitor.application.service import HealthMonitorService
from health_monitor.observability.client_events import ClientEventStore
from tests.unit.frontend_helpers import read_web_file


def event(event_id: str = "event-1", name: str = "client.attachment.picker_opened") -> dict[str, object]:
    return {
        "id": event_id,
        "client_ts": "2026-07-09T22:00:00Z",
        "session_id": "session-phone",
        "page_id": "page-one",
        "sequence": 1,
        "event": name,
        "level": "info",
        "route": "/chat",
        "visibility": "visible",
        "online": True,
        "payload": {"operation_id": "picker-1", "file_count": 1, "total_bytes": 1234},
    }


class ClientTelemetryTest(unittest.TestCase):
    def test_client_events_are_durable_searchable_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = ClientEventStore(Path(directory) / "client-events.jsonl")
            api = HttpApi(HealthMonitorService(), client_event_store=store)

            first = api.handle("POST", "/api/client-events/batch", {"events": [event()]})
            duplicate = api.handle("POST", "/api/client-events/batch", {"events": [event()]})
            listed = api.handle(
                "GET",
                "/api/client-events?session_id=session-phone&event=client.attachment.picker_opened",
                None,
            )

            self.assertEqual(first.status_code, 202)
            self.assertEqual(duplicate.status_code, 202)
            self.assertEqual(len(listed.body), 1)
            self.assertEqual(listed.body[0]["payload"]["total_bytes"], 1234)
            self.assertTrue((Path(directory) / "client-events.jsonl").exists())

    def test_sensitive_payload_fields_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = ClientEventStore(Path(directory) / "client-events.jsonl")
            api = HttpApi(HealthMonitorService(), client_event_store=store)
            unsafe = event()
            unsafe["payload"] = {"message_text": "private meal details"}

            response = api.handle("POST", "/api/client-events/batch", {"events": [unsafe]})

            self.assertEqual(response.status_code, 400)
            self.assertFalse((Path(directory) / "client-events.jsonl").exists())

    def test_client_buffers_locally_and_instruments_upload_boundaries(self) -> None:
        telemetry = read_web_file("clientTelemetry.ts")
        attachment = read_web_file("components/assistant-ui/attachment.tsx")
        runtime = read_web_file("hooks/useAgentRuntime.ts")
        main = read_web_file("main.tsx")

        self.assertIn("health-monitor.client-events.v1", telemetry)
        self.assertIn("keepalive: true", telemetry)
        self.assertIn("client.lifecycle.visibility", telemetry)
        self.assertIn("client.error.unhandled_rejection", telemetry)
        self.assertIn("client.attachment.selection_returned", attachment)
        self.assertIn("client.attachment.conversion_started", runtime)
        self.assertIn("filename: attachment.file.name", runtime)
        self.assertIn("capturedAt: fileCaptureTime", runtime)
        self.assertIn("client.upload.completed", runtime)
        self.assertIn("client.chat.run_completed", runtime)
        self.assertIn("lastMessage.attachments.flatMap", runtime)
        self.assertIn("parts: uploadableParts", runtime)
        self.assertIn("attachment_container_count", runtime)
        self.assertIn("installClientTelemetry()", main)
        self.assertIn("ClientErrorBoundary", main)


if __name__ == "__main__":
    unittest.main()
