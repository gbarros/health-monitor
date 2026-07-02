from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from health_monitor.application.service import HealthMonitorService
from health_monitor.domain.nutrients import Nutrients
from health_monitor.persistence.sqlite_state import SQLiteStateRepository
from health_monitor.worker import process_available_job


class BackgroundJobsTest(unittest.TestCase):
    def test_text_meal_job_processes_into_draft_proposal_without_diary_mutation(self) -> None:
        service = HealthMonitorService()
        household = service.create_household(name="Casa")
        person = service.create_person(
            household_id=household.id,
            name="Gabriel",
            timezone="America/Sao_Paulo",
        )
        service.create_food_with_version(
            household_id=household.id,
            name="Queijo Minas",
            brand=None,
            version_label="current",
            nutrients_per_100g=Nutrients(calories_kcal=315, protein_g=23, carbs_g=2.6, fat_g=23.5),
            source="label_scan",
            aliases=["queijo"],
        )
        job = service.enqueue_job(
            job_type="agent_text_meal",
            payload={
                "person_id": person.id,
                "logged_at_local": "2026-07-01T10:00:00",
                "text": "100g queijo",
                "agent_settings": {"model_profile": "ollama-local"},
            },
        )

        processed = service.process_next_job()
        summary = service.day_summary(person_id=person.id, day=date(2026, 7, 1))
        proposal = service.get_proposal(processed.result["proposal_id"])

        self.assertEqual(job.status, "pending")
        self.assertEqual(processed.status, "succeeded")
        self.assertEqual(processed.attempts, 1)
        self.assertEqual(processed.result["proposal_type"], "diary_entries")
        self.assertEqual(proposal.status, "draft")
        self.assertEqual(summary.totals, Nutrients())

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
            first.create_food_with_version(
                household_id=household.id,
                name="Queijo Minas",
                brand=None,
                version_label="current",
                nutrients_per_100g=Nutrients(calories_kcal=315, protein_g=23, carbs_g=2.6, fat_g=23.5),
                source="label_scan",
                aliases=["queijo"],
            )
            queued = first.enqueue_job(
                job_type="agent_text_meal",
                payload={
                    "person_id": person.id,
                    "logged_at_local": "2026-07-01T10:00:00",
                    "text": "100g queijo",
                },
            )

            worker_service = HealthMonitorService(repository=SQLiteStateRepository(db_path))
            restored = worker_service.get_job(queued.id)
            processed = worker_service.process_next_job()

            third = HealthMonitorService(repository=SQLiteStateRepository(db_path))
            persisted = third.get_job(queued.id)
            proposal = third.get_proposal(persisted.result["proposal_id"])

            self.assertEqual(restored.status, "pending")
            self.assertEqual(processed.id, queued.id)
            self.assertEqual(persisted.status, "succeeded")
            self.assertEqual(proposal.summary, "1 diary entries drafted from text meal")

    def test_worker_helper_processes_one_pending_job(self) -> None:
        service = HealthMonitorService()
        household = service.create_household(name="Casa")
        person = service.create_person(
            household_id=household.id,
            name="Gabriel",
            timezone="America/Sao_Paulo",
        )
        service.create_food_with_version(
            household_id=household.id,
            name="Queijo Minas",
            brand=None,
            version_label="current",
            nutrients_per_100g=Nutrients(calories_kcal=315, protein_g=23, carbs_g=2.6, fat_g=23.5),
            source="label_scan",
            aliases=["queijo"],
        )
        queued = service.enqueue_job(
            job_type="agent_text_meal",
            payload={
                "person_id": person.id,
                "logged_at_local": "2026-07-01T10:00:00",
                "text": "100g queijo",
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
                "message": "Why was 2026-07-01 high in calories?",
                "today": "2026-07-01",
            },
        )

        processed = service.process_next_job()
        turns = service.chat_turns_for_person(person.id)

        self.assertIsNotNone(processed)
        assert processed is not None
        self.assertEqual(processed.status, "succeeded")
        self.assertEqual(processed.result["behavior_label"], "explain_day")
        self.assertEqual(processed.result["chat_turn_id"], turns[0].id)
        self.assertEqual(processed.result["run_id"], turns[0].agent_run_id)
        self.assertIn("315", turns[0].assistant_message)


if __name__ == "__main__":
    unittest.main()
