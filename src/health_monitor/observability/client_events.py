from __future__ import annotations

import json
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


EVENT_NAME = re.compile(r"^[a-z0-9_.-]{1,96}$")
BLOCKED_PAYLOAD_PARTS = {
    "authorization",
    "base64",
    "content",
    "cookie",
    "data_url",
    "filename",
    "message",
    "password",
    "secret",
    "text",
    "token",
}


class ClientEventStore:
    """Append-only, privacy-filtered client diagnostics with idempotent ingestion."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()
        self._known_ids: set[str] | None = None

    def append_many(self, events: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized = [normalize_client_event(event) for event in events]
        if len(normalized) > 100:
            raise ValueError("client event batch cannot exceed 100 events")
        if not normalized:
            return []

        with self._lock:
            known_ids = self._load_known_ids()
            accepted = [event for event in normalized if event["id"] not in known_ids]
            if not accepted:
                return []
            self.path.parent.mkdir(parents=True, exist_ok=True)
            received_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            with self.path.open("a", encoding="utf-8") as file:
                for event in accepted:
                    stored = {**event, "server_received_at": received_at}
                    file.write(json.dumps(stored, ensure_ascii=False, separators=(",", ":")) + "\n")
                    known_ids.add(event["id"])
            return accepted

    def search(
        self,
        *,
        event: str | None = None,
        session_id: str | None = None,
        page_id: str | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        safe_limit = max(1, min(limit, 1000))
        if not self.path.exists():
            return []
        with self._lock:
            lines = self.path.read_text(encoding="utf-8").splitlines()
        matches: list[dict[str, Any]] = []
        for line in reversed(lines):
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event and item.get("event") != event:
                continue
            if session_id and item.get("session_id") != session_id:
                continue
            if page_id and item.get("page_id") != page_id:
                continue
            matches.append(item)
            if len(matches) >= safe_limit:
                break
        return matches

    def _load_known_ids(self) -> set[str]:
        if self._known_ids is not None:
            return self._known_ids
        known: set[str] = set()
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(item.get("id"), str):
                    known.add(item["id"])
        self._known_ids = known
        return known


def normalize_client_event(event: dict[str, Any]) -> dict[str, Any]:
    event_id = require_string(event, "id", 128)
    event_name = require_string(event, "event", 96)
    if not EVENT_NAME.fullmatch(event_name):
        raise ValueError("invalid client event name")
    level = str(event.get("level", "info"))
    if level not in {"debug", "info", "warn", "error"}:
        raise ValueError("invalid client event level")
    payload = event.get("payload", {})
    if not isinstance(payload, dict):
        raise ValueError("client event payload must be an object")
    safe_payload = sanitize_payload(payload)
    return {
        "id": event_id,
        "client_ts": require_string(event, "client_ts", 64),
        "session_id": require_string(event, "session_id", 128),
        "page_id": require_string(event, "page_id", 128),
        "sequence": int(event.get("sequence", 0)),
        "event": event_name,
        "level": level,
        "route": str(event.get("route", ""))[:256],
        "visibility": str(event.get("visibility", "unknown"))[:32],
        "online": bool(event.get("online", True)),
        "payload": safe_payload,
    }


def sanitize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if len(payload) > 32:
        raise ValueError("client event payload has too many fields")
    safe: dict[str, Any] = {}
    for key, value in payload.items():
        normalized_key = str(key).casefold()
        if any(part in normalized_key for part in BLOCKED_PAYLOAD_PARTS):
            raise ValueError(f"unsafe client event payload key: {key}")
        safe[str(key)[:64]] = sanitize_value(value)
    return safe


def sanitize_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value[:512]
    if isinstance(value, list):
        return [sanitize_value(item) for item in value[:32]]
    if isinstance(value, dict):
        return sanitize_payload(value)
    return str(value)[:512]


def require_string(event: dict[str, Any], key: str, max_length: int) -> str:
    value = event.get(key)
    if not isinstance(value, str) or not value or len(value) > max_length:
        raise ValueError(f"invalid client event {key}")
    return value
