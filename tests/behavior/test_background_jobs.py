from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from health_monitor.application.service import HealthMonitorService
from health_monitor.domain.nutrients import Nutrients
from health_monitor.persistence.sqlite_state import SQLiteStateRepository
from health_monitor.worker import process_available_job


class BackgroundJobsTest(unittest.TestCase):
    def test_legacy_mode_jobs_are_rejected(self) -> None:
        service = HealthMonitorService()

        with self.assertRaisesRegex(ValueError, "unsupported job type: agent_text_meal"):
            service.enqueue_job(job_type="agent_text_meal", payload={})

    def test_pending_job_survives_restart_and_can_be_processed_by_worker_service(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "health-monitor.sqlite3"
            first = HealthMonitorService(repository=SQLiteStateRepository(db_path))
            household = first.create_household(name="Casa")
            person = first.create_person(
                household_id=household.id,
                name="Gabriel",
                timezone="America/Sao_Paulo",
            )
            queued = first.enqueue_job(
                job_type="agent_chat",
                payload={
                    "person_id": person.id,
                    "message": "Pode resumir meu dia?",
                    "today": "2026-07-01",
                },
            )

            worker_service = HealthMonitorService(repository=SQLiteStateRepository(db_path))
            restored = worker_service.get_job(queued.id)
            processed = worker_service.process_next_job()

            third = HealthMonitorService(repository=SQLiteStateRepository(db_path))
            persisted = third.get_job(queued.id)
            turn = third.chat_turns_for_person(person.id)[0]

            self.assertEqual(restored.status, "pending")
            self.assertEqual(processed.id, queued.id)
            self.assertEqual(persisted.status, "succeeded")
            self.assertEqual(persisted.result["chat_turn_id"], turn.id)

    def test_client_request_id_makes_job_enqueue_idempotent(self) -> None:
        service = HealthMonitorService()
        first = service.enqueue_job(
            job_type="agent_chat",
            payload={"person_id": "person_1", "message": "first"},
            client_request_id="offline-item-1",
        )
        second = service.enqueue_job(
            job_type="agent_chat",
            payload={"person_id": "person_1", "message": "duplicate retry"},
            client_request_id="offline-item-1",
        )

        self.assertEqual(second.id, first.id)
        self.assertEqual(second.client_request_id, "offline-item-1")
        self.assertEqual(second.payload["message"], "first")
        self.assertEqual(len(service.list_jobs(person_id="person_1")), 1)

    def test_worker_helper_processes_one_pending_job(self) -> None:
        service = HealthMonitorService()
        household = service.create_household(name="Casa")
        person = service.create_person(
            household_id=household.id,
            name="Gabriel",
            timezone="America/Sao_Paulo",
        )
        queued = service.enqueue_job(
            job_type="agent_chat",
            payload={
                "person_id": person.id,
                "message": "Pode resumir meu dia?",
                "today": "2026-07-01",
            },
        )

        processed = process_available_job(service)

        self.assertEqual(processed.id, queued.id)
        self.assertEqual(processed.status, "succeeded")
        self.assertIsNone(process_available_job(service))

    def test_agent_chat_job_processes_into_saved_chat_turn(self) -> None:
        service = HealthMonitorService()
        household = service.create_household(name="Casa")
        person = service.create_person(
            household_id=household.id,
            name="Gabriel",
            timezone="America/Sao_Paulo",
        )
        _, version = service.create_food_with_version(
            household_id=household.id,
            name="Queijo Minas",
            brand=None,
            version_label="current",
            nutrients_per_100g=Nutrients(calories_kcal=315, protein_g=23, carbs_g=2.6, fat_g=23.5),
            source="label_scan",
            aliases=["queijo"],
        )
        service.log_diary_entry(
            person_id=person.id,
            logged_at_local="2026-07-01T10:00:00",
            food_version_id=version.id,
            quantity_g=100,
            source="manual",
        )
        service.enqueue_job(
            job_type="agent_chat",
            payload={
                "person_id": person.id,
                "message": "Pode explicar meu diário?",
                "today": "2026-07-01",
            },
        )

        processed = service.process_next_job()
        turns = service.chat_turns_for_person(person.id)

        self.assertIsNotNone(processed)
        assert processed is not None
        self.assertEqual(processed.status, "succeeded")
        self.assertEqual(processed.result["behavior_label"], "answer_question")
        self.assertEqual(processed.result["chat_turn_id"], turns[0].id)
        self.assertEqual(processed.result["run_id"], turns[0].agent_run_id)
        self.assertEqual(turns[0].user_message, "Pode explicar meu diário?")


if __name__ == "__main__":
    unittest.main()
