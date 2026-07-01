from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any, Protocol


class StateRepository(Protocol):
    def load(self) -> dict[str, Any] | None:
        pass

    def save(self, snapshot: dict[str, Any]) -> None:
        pass


class SQLiteStateRepository:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def load(self) -> dict[str, Any] | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT snapshot_json FROM app_state WHERE id = 1"
            ).fetchone()
        if row is None:
            return None
        return json.loads(row[0])

    def save(self, snapshot: dict[str, Any]) -> None:
        payload = json.dumps(snapshot, sort_keys=True, separators=(",", ":"))
        with closing(self._connect()) as connection:
            with connection:
                connection.execute(
                    """
                    INSERT INTO app_state (id, snapshot_json, updated_at)
                    VALUES (1, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(id) DO UPDATE SET
                        snapshot_json = excluded.snapshot_json,
                        updated_at = excluded.updated_at
                    """,
                    (payload,),
                )

    def _ensure_schema(self) -> None:
        with closing(self._connect()) as connection:
            with connection:
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS app_state (
                        id INTEGER PRIMARY KEY CHECK (id = 1),
                        snapshot_json TEXT NOT NULL,
                        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)
