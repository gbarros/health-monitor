from __future__ import annotations

import time

from health_monitor.application.service import BackgroundJob, HealthMonitorService
from health_monitor.config import load_config
from health_monitor.observability.nexuslog import NexusLogEvent, NexusLogSink, build_nexuslog_sink
from health_monitor.server import build_service


def process_available_job(
    service: HealthMonitorService,
    *,
    event_sink: NexusLogSink | None = None,
) -> BackgroundJob | None:
    job = service.process_next_job()
    if job is not None and event_sink is not None:
        event_sink.emit(
            NexusLogEvent(
                service="health-monitor-worker",
                level="info" if job.status == "succeeded" else "warn",
                event="job.processed",
                entity_type="job",
                entity_id=job.id,
                job_id=job.id,
                payload={
                    "job_type": job.job_type,
                    "status": job.status,
                    "attempts": job.attempts,
                    "has_error": job.last_error is not None,
                },
            )
        )
    return job


def run(interval_seconds: int = 30, *, once: bool = False) -> None:
    config = load_config()
    event_sink = build_nexuslog_sink(
        mode=config.nexuslog_mode,
        jsonl_path=config.nexuslog_jsonl_path,
    )
    service = build_service(config)
    event_sink.emit(
        NexusLogEvent(
            service="health-monitor-worker",
            level="info",
            event="worker.started",
            payload={
                "interval_seconds": interval_seconds,
                "persistence_backend": config.persistence_backend,
            },
        )
    )
    while True:
        process_available_job(service, event_sink=event_sink)
        if once:
            return
        time.sleep(interval_seconds)
