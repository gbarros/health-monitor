from __future__ import annotations

import base64
import copy
import json
from contextlib import closing
from typing import Any, Callable


ConnectFactory = Callable[[], Any]


class PostgresStateRepository:
    def __init__(
        self,
        database_url: str,
        *,
        connect_factory: ConnectFactory | None = None,
    ) -> None:
        self.database_url = database_url
        self.connect_factory = connect_factory
        self._ensure_schema()

    def load(self) -> dict[str, Any] | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT snapshot_json FROM app_state WHERE id = %s",
                (1,),
            ).fetchone()
            if row is None:
                return None
            snapshot = coerce_json_object(row[0])
            attachment_rows = connection.execute(
                """
                SELECT
                    id,
                    household_id,
                    created_by_person_id,
                    object_type,
                    mime_type,
                    byte_size,
                    sha256,
                    content,
                    filename,
                    storage_status,
                    retention_policy,
                    linked_record_type,
                    linked_record_id,
                    created_at
                FROM attachment_objects
                ORDER BY created_at, id
                """
            ).fetchall()
        if attachment_rows:
            snapshot["attachment_objects"] = [
                attachment_row_to_snapshot(row) for row in attachment_rows
            ]
        return snapshot

    def save(self, snapshot: dict[str, Any]) -> None:
        snapshot_json, attachment_rows = split_snapshot_for_postgres(snapshot)
        with closing(self._connect()) as connection:
            with connection:
                connection.execute(
                    """
                    INSERT INTO app_state (id, snapshot_json, updated_at)
                    VALUES (%s, %s::jsonb, CURRENT_TIMESTAMP)
                    ON CONFLICT(id) DO UPDATE SET
                        snapshot_json = excluded.snapshot_json,
                        updated_at = excluded.updated_at
                    """,
                    (1, json.dumps(snapshot_json, sort_keys=True, separators=(",", ":"))),
                )
                if attachment_rows:
                    attachment_ids = [row["id"] for row in attachment_rows]
                    connection.execute(
                        "DELETE FROM attachment_objects WHERE NOT (id = ANY(%s))",
                        (attachment_ids,),
                    )
                else:
                    connection.execute("DELETE FROM attachment_objects")
                for row in attachment_rows:
                    connection.execute(
                        """
                        INSERT INTO attachment_objects (
                            id,
                            household_id,
                            created_by_person_id,
                            object_type,
                            mime_type,
                            byte_size,
                            sha256,
                            content,
                            filename,
                            storage_status,
                            retention_policy,
                            linked_record_type,
                            linked_record_id,
                            created_at
                        )
                        VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                        )
                        ON CONFLICT(id) DO UPDATE SET
                            household_id = excluded.household_id,
                            created_by_person_id = excluded.created_by_person_id,
                            object_type = excluded.object_type,
                            mime_type = excluded.mime_type,
                            byte_size = excluded.byte_size,
                            sha256 = excluded.sha256,
                            content = excluded.content,
                            filename = excluded.filename,
                            storage_status = excluded.storage_status,
                            retention_policy = excluded.retention_policy,
                            linked_record_type = excluded.linked_record_type,
                            linked_record_id = excluded.linked_record_id,
                            created_at = excluded.created_at
                        """,
                        (
                            row["id"],
                            row["household_id"],
                            row["created_by_person_id"],
                            row["object_type"],
                            row["mime_type"],
                            row["byte_size"],
                            row["sha256"],
                            row["content"],
                            row["filename"],
                            row["storage_status"],
                            row["retention_policy"],
                            row["linked_record_type"],
                            row["linked_record_id"],
                            row["created_at"],
                        ),
                    )

    def _ensure_schema(self) -> None:
        with closing(self._connect()) as connection:
            with connection:
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS app_state (
                        id integer PRIMARY KEY CHECK (id = 1),
                        snapshot_json jsonb NOT NULL,
                        updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS attachment_objects (
                        id text PRIMARY KEY,
                        household_id text NOT NULL,
                        created_by_person_id text NOT NULL,
                        object_type text NOT NULL,
                        mime_type text NOT NULL,
                        byte_size integer NOT NULL,
                        sha256 text NOT NULL,
                        content bytea NOT NULL,
                        filename text,
                        storage_status text NOT NULL,
                        retention_policy text NOT NULL,
                        linked_record_type text,
                        linked_record_id text,
                        created_at timestamptz NOT NULL
                    )
                    """
                )
                connection.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_attachment_objects_linked_record
                    ON attachment_objects (linked_record_type, linked_record_id)
                    """
                )

    def _connect(self) -> Any:
        if self.connect_factory is not None:
            return self.connect_factory()
        try:
            import psycopg
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "psycopg is required for PERSISTENCE_BACKEND=postgres"
            ) from exc
        return psycopg.connect(self.database_url)


def split_snapshot_for_postgres(
    snapshot: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    snapshot_json = copy.deepcopy(snapshot)
    attachments = snapshot_json.get("attachment_objects", [])
    rows = [attachment_snapshot_to_row(attachment) for attachment in attachments]
    for attachment in attachments:
        attachment.pop("content_base64", None)
    return snapshot_json, rows


def attachment_snapshot_to_row(attachment: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": attachment["id"],
        "household_id": attachment["household_id"],
        "created_by_person_id": attachment["created_by_person_id"],
        "object_type": attachment["object_type"],
        "mime_type": attachment["mime_type"],
        "byte_size": int(attachment["byte_size"]),
        "sha256": attachment["sha256"],
        "content": base64.b64decode(attachment["content_base64"]),
        "filename": attachment.get("filename"),
        "storage_status": attachment.get("storage_status", "stored"),
        "retention_policy": attachment.get("retention_policy", "keep"),
        "linked_record_type": attachment.get("linked_record_type"),
        "linked_record_id": attachment.get("linked_record_id"),
        "created_at": attachment["created_at"],
    }


def attachment_row_to_snapshot(row: Any) -> dict[str, Any]:
    return {
        "id": row[0],
        "household_id": row[1],
        "created_by_person_id": row[2],
        "object_type": row[3],
        "mime_type": row[4],
        "byte_size": int(row[5]),
        "sha256": row[6],
        "content_base64": base64.b64encode(bytes(row[7])).decode("ascii"),
        "filename": row[8],
        "storage_status": row[9],
        "retention_policy": row[10],
        "linked_record_type": row[11],
        "linked_record_id": row[12],
        "created_at": row[13].isoformat()
        if hasattr(row[13], "isoformat")
        else str(row[13]),
    }


def coerce_json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        return dict(json.loads(value))
    return dict(value)
