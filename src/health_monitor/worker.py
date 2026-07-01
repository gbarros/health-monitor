from __future__ import annotations

import time


def run(interval_seconds: int = 30) -> None:
    print("health-monitor worker started")
    while True:
        time.sleep(interval_seconds)
