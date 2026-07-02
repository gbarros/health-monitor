from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppConfig:
    persistence_backend: str = "sqlite"
    sqlite_path: Path = Path("data/local/health-monitor.sqlite3")
    database_url: str = "postgresql://health_monitor:health_monitor@127.0.0.1:5432/health_monitor"
    log_format: str = "text"
    nexuslog_mode: str = "stdout"
    nexuslog_jsonl_path: Path = Path("var/nexuslog-events/health-monitor.jsonl")
    agent_runtime: str = "deterministic"
    model_provider: str = "deterministic"
    food_estimator: str = "ollama"
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "gemma4:e4b"
    label_text_extractor: str = "ollama"
    ocr_model: str = "glm-ocr:latest"
    openfoodfacts_enabled: bool = True
    usda_enabled: bool = False
    usda_api_key: str | None = None
    research_lookup_enabled: bool = False
    live_model_tests: bool = False
    live_model_name: str = "ornith:9b"
    cloud_model_calls_enabled: bool = False
    cloud_model_name: str = "glm-5.2:cloud"


def load_config() -> AppConfig:
    return AppConfig(
        persistence_backend=os.environ.get("PERSISTENCE_BACKEND", "sqlite"),
        sqlite_path=Path(
            os.environ.get("SQLITE_PATH", "data/local/health-monitor.sqlite3")
        ),
        database_url=os.environ.get(
            "DATABASE_URL",
            "postgresql://health_monitor:health_monitor@127.0.0.1:5432/health_monitor",
        ),
        log_format=os.environ.get("LOG_FORMAT", "text"),
        nexuslog_mode=os.environ.get("NEXUSLOG_MODE", "stdout"),
        nexuslog_jsonl_path=Path(
            os.environ.get("NEXUSLOG_JSONL_PATH", "var/nexuslog-events/health-monitor.jsonl")
        ),
        agent_runtime=os.environ.get("AGENT_RUNTIME", "deterministic"),
        model_provider=os.environ.get("MODEL_PROVIDER", "deterministic"),
        food_estimator=os.environ.get("FOOD_ESTIMATOR", "ollama"),
        ollama_base_url=os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
        ollama_model=os.environ.get(
            "OLLAMA_MODEL",
            os.environ.get("DEFAULT_MODEL_PROFILE", "gemma4:e4b"),
        ),
        label_text_extractor=os.environ.get("LABEL_TEXT_EXTRACTOR", "ollama"),
        ocr_model=os.environ.get("OCR_MODEL", os.environ.get("OLLAMA_OCR_MODEL", "glm-ocr:latest")),
        openfoodfacts_enabled=os.environ.get("OPENFOODFACTS_ENABLED", "true").casefold()
        in {"1", "true", "yes", "on"},
        usda_enabled=os.environ.get("USDA_ENABLED", "false").casefold()
        in {"1", "true", "yes", "on"},
        usda_api_key=os.environ.get("USDA_API_KEY") or None,
        research_lookup_enabled=os.environ.get("RESEARCH_LOOKUP_ENABLED", "false").casefold()
        in {"1", "true", "yes", "on"},
        live_model_tests=os.environ.get("LIVE_MODEL_TESTS", "false").casefold()
        in {"1", "true", "yes", "on"},
        live_model_name=os.environ.get("LIVE_MODEL_NAME", "ornith:9b"),
        cloud_model_calls_enabled=os.environ.get(
            "CLOUD_MODEL_CALLS_ENABLED", "false"
        ).casefold()
        in {"1", "true", "yes", "on"},
        cloud_model_name=os.environ.get("CLOUD_MODEL_NAME", "glm-5.2:cloud"),
    )
