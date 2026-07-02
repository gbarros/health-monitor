from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Protocol, TextIO


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


class NexusLogSink(Protocol):
    def emit(self, event: NexusLogEvent) -> None:
        """Emit one event."""


class NoopNexusLogSink:
    def emit(self, event: NexusLogEvent) -> None:
        return


class JsonLineNexusLogSink:
    def __init__(self, stream: TextIO) -> None:
        self.stream = stream

    def emit(self, event: NexusLogEvent) -> None:
        self.stream.write(json.dumps(event.as_dict(), ensure_ascii=False) + "\n")
        self.stream.flush()


class JsonlFileNexusLogSink:
    def __init__(self, path: Path) -> None:
        self.path = path

    def emit(self, event: NexusLogEvent) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(event.as_dict(), ensure_ascii=False) + "\n")


def build_nexuslog_sink(
    *,
    mode: str,
    jsonl_path: Path | None = None,
    stream: TextIO | None = None,
) -> NexusLogSink:
    normalized = mode.casefold().strip()
    if normalized in {"disabled", "none", "off"}:
        return NoopNexusLogSink()
    if normalized == "stdout":
        return JsonLineNexusLogSink(stream or sys.stdout)
    if normalized == "jsonl":
        return JsonlFileNexusLogSink(jsonl_path or Path("var/nexuslog-events/health-monitor.jsonl"))
    raise ValueError(f"unsupported NexusLog mode: {mode}")


def assert_safe_payload(payload: dict[str, Any]) -> None:
    for key in payload:
        normalized = key.casefold()
        if normalized in SECRET_KEYS or normalized.endswith("_token") or normalized.endswith("_secret"):
            raise ValueError(f"unsafe log payload key: {key}")
