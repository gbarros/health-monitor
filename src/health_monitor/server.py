from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from health_monitor.api.http_api import HttpApi
from health_monitor.application.service import HealthMonitorService
from health_monitor.config import load_config
from health_monitor.lookup.estimates import OllamaFoodEstimator
from health_monitor.lookup.foods import OpenFoodFactsLookupProvider
from health_monitor.persistence.sqlite_state import SQLiteStateRepository


def build_api() -> HttpApi:
    config = load_config()
    if config.persistence_backend != "sqlite":
        raise ValueError(f"unsupported persistence backend: {config.persistence_backend}")
    repository = SQLiteStateRepository(config.sqlite_path)
    estimator = None
    if config.food_estimator == "ollama":
        estimator = OllamaFoodEstimator(
            base_url=config.ollama_base_url,
            model=config.ollama_model,
        )
    elif config.food_estimator != "none":
        raise ValueError(f"unsupported food estimator: {config.food_estimator}")
    food_lookup_provider = OpenFoodFactsLookupProvider() if config.openfoodfacts_enabled else None
    return HttpApi(
        HealthMonitorService(
            repository=repository,
            estimator=estimator,
            food_lookup_provider=food_lookup_provider,
        )
    )


class HealthMonitorRequestHandler(BaseHTTPRequestHandler):
    api = build_api()

    def do_GET(self) -> None:
        self._handle_request(None)

    def do_POST(self) -> None:
        self._handle_request(self._read_json_body())

    def do_PATCH(self) -> None:
        self._handle_request(self._read_json_body())

    def do_DELETE(self) -> None:
        self._handle_request(None)

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _handle_request(self, body: dict[str, Any] | None) -> None:
        response = self.api.handle(self.command, self.path, body)
        payload = json.dumps(response.body, ensure_ascii=False).encode("utf-8")
        self.send_response(response.status_code)
        self.send_header("content-type", "application/json; charset=utf-8")
        self.send_header("content-length", str(len(payload)))
        self.send_header("access-control-allow-origin", "*")
        self.end_headers()
        self.wfile.write(payload)

    def _read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("content-length", "0"))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        if not raw:
            return {}
        return json.loads(raw)


def run(host: str = "127.0.0.1", port: int = 8765) -> None:
    server = ThreadingHTTPServer((host, port), HealthMonitorRequestHandler)
    print(f"health-monitor api listening on http://{host}:{port}")
    server.serve_forever()
