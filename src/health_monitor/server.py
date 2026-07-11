from __future__ import annotations

import json
from importlib import import_module
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from health_monitor.api.http_api import HttpApi, HttpStreamResponse
from health_monitor.application.service import HealthMonitorService
from health_monitor.config import load_config
from health_monitor.lookup.estimates import OllamaFoodEstimator
from health_monitor.lookup.foods import (
    CompositeFoodLookupProvider,
    OpenFoodFactsLookupProvider,
    USDAFoodDataCentralLookupProvider,
)
from health_monitor.lookup.labels import OllamaImageAnalyzer, OllamaLabelTextExtractor
from health_monitor.observability.nexuslog import NexusLogEvent, build_nexuslog_sink
from health_monitor.observability.client_events import ClientEventStore
from health_monitor.persistence.postgres_state import PostgresStateRepository
from health_monitor.persistence.sqlite_state import SQLiteStateRepository


def build_api() -> HttpApi:
    config = load_config()
    return HttpApi(
        build_service(config),
        event_sink=build_nexuslog_sink(
            mode=config.nexuslog_mode,
            jsonl_path=config.nexuslog_jsonl_path,
        ),
        client_event_store=ClientEventStore(config.client_event_log_path),
    )


def build_service(config: Any | None = None) -> HealthMonitorService:
    config = config or load_config()
    if config.persistence_backend == "sqlite":
        repository = SQLiteStateRepository(config.sqlite_path)
    elif config.persistence_backend == "postgres":
        repository = PostgresStateRepository(config.database_url)
    else:
        raise ValueError(f"unsupported persistence backend: {config.persistence_backend}")
    estimator = None
    if config.food_estimator == "ollama":
        estimator = OllamaFoodEstimator(
            base_url=config.ollama_base_url,
            model=config.ollama_model,
        )
    elif config.food_estimator != "none":
        raise ValueError(f"unsupported food estimator: {config.food_estimator}")
    label_text_extractor = None
    if config.label_text_extractor == "ollama":
        label_text_extractor = OllamaLabelTextExtractor(
            base_url=config.ollama_base_url,
            model=config.ocr_model,
        )
    elif config.label_text_extractor != "none":
        raise ValueError(f"unsupported label text extractor: {config.label_text_extractor}")
    image_analyzer = None
    if config.image_analyzer == "ollama":
        image_analyzer = OllamaImageAnalyzer(
            base_url=config.ollama_base_url,
            model=config.vision_model,
        )
    elif config.image_analyzer != "none":
        raise ValueError(f"unsupported image analyzer: {config.image_analyzer}")
    lookup_providers = []
    if config.openfoodfacts_enabled:
        lookup_providers.append(OpenFoodFactsLookupProvider())
    if config.usda_enabled:
        lookup_providers.append(
            USDAFoodDataCentralLookupProvider(api_key=config.usda_api_key)
        )
    food_lookup_provider = (
        CompositeFoodLookupProvider(lookup_providers)
        if len(lookup_providers) > 1
        else lookup_providers[0]
        if lookup_providers
        else None
    )
    return HealthMonitorService(
        repository=repository,
        estimator=estimator,
        food_lookup_provider=food_lookup_provider,
        label_text_extractor=label_text_extractor,
        image_analyzer=image_analyzer,
        agent_runtime=config.agent_runtime,
        model_provider=config.model_provider,
        agent_model=config.ollama_model,
        ollama_base_url=config.ollama_base_url,
        require_model=config.require_model,
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
        if isinstance(response, HttpStreamResponse):
            self.send_response(response.status_code)
            self.send_header("content-type", "text/event-stream; charset=utf-8")
            self.send_header("cache-control", "no-cache")
            self.send_header("access-control-allow-origin", "*")
            self.end_headers()
            for event in response.iter_events():
                payload = json.dumps(event["data"], ensure_ascii=False).encode("utf-8")
                self.wfile.write(f"event: {event['event']}\n".encode("utf-8"))
                self.wfile.write(b"data: ")
                self.wfile.write(payload)
                self.wfile.write(b"\n\n")
                # SSE is only useful when each stage reaches the client now;
                # Android Chrome otherwise receives the whole run at the end.
                self.wfile.flush()
                self.wfile.flush()
            return
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
    config = load_config()
    pydantic_ai_available = False
    if config.agent_runtime == "pydantic-ai":
        try:
            import_module("pydantic_ai")
        except Exception:
            pydantic_ai_available = False
        else:
            pydantic_ai_available = True
    sink = build_nexuslog_sink(
        mode=config.nexuslog_mode,
        jsonl_path=config.nexuslog_jsonl_path,
    )
    server = ThreadingHTTPServer((host, port), HealthMonitorRequestHandler)
    sink.emit(
        NexusLogEvent(
            service="health-monitor-api",
            level="info",
            event="api.started",
            payload={
                "host": host,
                "port": port,
                "persistence_backend": config.persistence_backend,
                "agent_runtime": config.agent_runtime,
                "model_provider": config.model_provider,
                "model_name": config.ollama_model,
                "ollama_base_url": config.ollama_base_url,
                "pydantic_ai_imported": pydantic_ai_available,
            },
        )
    )
    server.serve_forever()
