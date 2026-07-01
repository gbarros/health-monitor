from __future__ import annotations

import unittest

from health_monitor.persistence.postgres_state import (
    attachment_row_to_snapshot,
    split_snapshot_for_postgres,
)


class PostgresStateTest(unittest.TestCase):
    def test_attachment_content_is_stored_as_separate_blob_row(self) -> None:
        snapshot = {
            "version": 1,
            "households": [],
            "attachment_objects": [
                {
                    "id": "attachment_1",
                    "household_id": "household_1",
                    "created_by_person_id": "person_1",
                    "object_type": "nutrition_label_image",
                    "mime_type": "image/png",
                    "byte_size": 16,
                    "sha256": "abc123",
                    "content_base64": "ZmFrZS1sYWJlbC1pbWFnZQ==",
                    "filename": "label.png",
                    "storage_status": "stored",
                    "retention_policy": "keep",
                    "linked_record_type": "food_version",
                    "linked_record_id": "food_version_1",
                    "created_at": "2026-07-01T12:00:00+00:00",
                }
            ],
        }

        app_state, rows = split_snapshot_for_postgres(snapshot)

        self.assertNotIn("content_base64", app_state["attachment_objects"][0])
        self.assertEqual(rows[0]["content"], b"fake-label-image")
        self.assertEqual(
            snapshot["attachment_objects"][0]["content_base64"],
            "ZmFrZS1sYWJlbC1pbWFnZQ==",
        )

    def test_attachment_blob_row_restores_snapshot_shape(self) -> None:
        restored = attachment_row_to_snapshot(
            (
                "attachment_1",
                "household_1",
                "person_1",
                "nutrition_label_image",
                "image/png",
                16,
                "abc123",
                b"fake-label-image",
                "label.png",
                "stored",
                "keep",
                "food_version",
                "food_version_1",
                "2026-07-01T12:00:00+00:00",
            )
        )

        self.assertEqual(restored["content_base64"], "ZmFrZS1sYWJlbC1pbWFnZQ==")
        self.assertEqual(restored["linked_record_type"], "food_version")


if __name__ == "__main__":
    unittest.main()
