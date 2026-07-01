from __future__ import annotations

import time

from health_monitor.application.service import BackgroundJob, HealthMonitorService
from health_monitor.server import build_service


def process_available_job(service: HealthMonitorService) -> BackgroundJob | None:
    return service.process_next_job()


def run(interval_seconds: int = 30, *, once: bool = False) -> None:
    service = build_service()
    print("health-monitor worker started")
    while True:
        job = process_available_job(service)
        if job is not None:
            print(f"job {job.id} {job.status}")
        if once:
            return
        time.sleep(interval_seconds)
