from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal


LogLevel = Literal["debug", "info", "warn", "error"]

SECRET_KEYS = {"api_key", "authorization", "cookie", "password", "token"}


@dataclass(frozen=True)
class NexusLogEvent:
    service: str
    level: LogLevel
    event: str
    payload: dict[str, Any] = field(default_factory=dict)
    entity_type: str | None = None
    entity_id: str | None = None
    request_id: str | None = None
    session_id: str | None = None
    job_id: str | None = None
    ts: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def as_dict(self) -> dict[str, Any]:
        assert_safe_payload(self.payload)
        body: dict[str, Any] = {
            "ts": self.ts.isoformat().replace("+00:00", "Z"),
            "service": self.service,
            "level": self.level,
            "event": self.event,
            "payload": self.payload,
        }
        for key in ("entity_type", "entity_id", "request_id", "session_id", "job_id"):
            value = getattr(self, key)
            if value is not None:
                body[key] = value
        return body


def assert_safe_payload(payload: dict[str, Any]) -> None:
    for key in payload:
        normalized = key.casefold()
        if normalized in SECRET_KEYS or normalized.endswith("_token") or normalized.endswith("_secret"):
            raise ValueError(f"unsafe log payload key: {key}")

