from __future__ import annotations

import argparse

from health_monitor.server import run
from health_monitor.worker import run as run_worker


def main() -> None:
    parser = argparse.ArgumentParser(prog="health-monitor")
    subparsers = parser.add_subparsers(dest="command")
    api_parser = subparsers.add_parser("api")
    api_parser.add_argument("--host", default="127.0.0.1")
    api_parser.add_argument("--port", default=8765, type=int)
    worker_parser = subparsers.add_parser("worker")
    worker_parser.add_argument("--interval-seconds", default=30, type=int)
    worker_parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    if args.command == "api":
        run(host=args.host, port=args.port)
        return
    if args.command == "worker":
        run_worker(interval_seconds=args.interval_seconds, once=args.once)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
