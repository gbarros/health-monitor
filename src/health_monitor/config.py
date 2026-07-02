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
    food_estimator: str = "ollama"
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "gemma4:e4b"
    label_text_extractor: str = "ollama"
    ollama_vision_model: str = "llava"
    openfoodfacts_enabled: bool = True


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
        food_estimator=os.environ.get("FOOD_ESTIMATOR", "ollama"),
        ollama_base_url=os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
        ollama_model=os.environ.get(
            "OLLAMA_MODEL",
            os.environ.get("DEFAULT_MODEL_PROFILE", "gemma4:e4b"),
        ),
        label_text_extractor=os.environ.get("LABEL_TEXT_EXTRACTOR", "ollama"),
        ollama_vision_model=os.environ.get(
            "OLLAMA_VISION_MODEL",
            os.environ.get("OLLAMA_MODEL", "llava"),
        ),
        openfoodfacts_enabled=os.environ.get("OPENFOODFACTS_ENABLED", "true").casefold()
        in {"1", "true", "yes", "on"},
    )
