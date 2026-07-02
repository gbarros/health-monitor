from __future__ import annotations

import base64
import json
import urllib.request
from dataclasses import dataclass
from typing import Protocol

from health_monitor.lookup.estimates import strip_json_fence


@dataclass(frozen=True)
class LabelTextExtraction:
    text: str
    source: str
    confidence: float
    warnings: tuple[str, ...] = ()


class LabelTextExtractor(Protocol):
    def extract(
        self,
        *,
        image_bytes: bytes,
        mime_type: str,
        filename: str | None = None,
    ) -> LabelTextExtraction | None:
        pass


class StaticLabelTextExtractor:
    def __init__(self, extraction: LabelTextExtraction | None) -> None:
        self.extraction = extraction

    def extract(
        self,
        *,
        image_bytes: bytes,
        mime_type: str,
        filename: str | None = None,
    ) -> LabelTextExtraction | None:
        return self.extraction


class OllamaLabelTextExtractor:
    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:11434",
        model: str = "llava",
        timeout_seconds: float = 60,
        max_attempts: int = 2,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_attempts = max(1, max_attempts)

    def extract(
        self,
        *,
        image_bytes: bytes,
        mime_type: str,
        filename: str | None = None,
    ) -> LabelTextExtraction | None:
        prompt = (
            "Text Recognition: Read this nutrition facts label or Brazilian tabela nutricional. "
            "Return only JSON with keys text, confidence, warnings. The text value must be "
            "line-oriented key/value text using labels like Produto, Marca, Porcao, "
            "Valor energetico, Proteinas, Carboidratos, Gorduras totais, Fibra alimentar, "
            "Sodio, Codigo de barras when visible. Preserve numbers and units."
        )
        image_base64 = base64.b64encode(image_bytes).decode("ascii")
        for _ in range(self.max_attempts):
            body = json.dumps(
                {
                    "model": self.model,
                    "prompt": prompt,
                    "images": [image_base64],
                    "stream": False,
                    "format": "json",
                }
            ).encode("utf-8")
            request = urllib.request.Request(
                f"{self.base_url}/api/generate",
                data=body,
                headers={"content-type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                    payload = json.loads(response.read().decode("utf-8"))
            except OSError:
                return None
            extraction = parse_ollama_label_payload(payload, model=self.model)
            if extraction is not None:
                return extraction
        return None


def parse_ollama_label_payload(
    payload: dict[str, object],
    *,
    model: str,
) -> LabelTextExtraction | None:
    try:
        raw_response = payload.get("response") or payload.get("thinking")
        if not raw_response:
            return None
        parsed = json.loads(strip_json_fence(str(raw_response)))
        text = extract_label_text(parsed)
        if not text:
            return None
        warnings = parsed.get("warnings", ())
        if isinstance(warnings, str):
            warning_items = (warnings,)
        else:
            warning_items = tuple(str(item) for item in warnings)
        return LabelTextExtraction(
            text=text,
            source=f"ollama_vision:{model}",
            confidence=read_confidence(parsed.get("confidence", 0.45)),
            warnings=warning_items,
        )
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


def extract_label_text(parsed: object) -> str:
    if not isinstance(parsed, dict):
        return ""
    text = str(
        parsed.get("text") or parsed.get("ocr_text") or parsed.get("text_content") or ""
    ).strip()
    if text:
        normalized = text_from_embedded_json(text)
        return normalized or text
    table = parsed.get("table")
    if isinstance(table, list):
        lines: list[str] = []
        for row in table:
            if not isinstance(row, dict):
                continue
            cells = [
                str(value).strip()
                for key, value in sorted(row.items())
                if key.startswith("row") and str(value).strip()
            ]
            if cells:
                lines.append(" | ".join(cells))
        return "\n".join(lines).strip()
    return flatten_ocr_object(parsed)


def text_from_embedded_json(value: str) -> str:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return ""
    if isinstance(parsed, list):
        lines: list[str] = []
        for item in parsed:
            if isinstance(item, dict):
                preferred = item.get("text_content_text") or item.get("content")
                if preferred:
                    lines.append(str(preferred).strip())
                    continue
                for key, cell in item.items():
                    if key in {"box_2d", "bbox_2d", "line_numbers", "level"}:
                        continue
                    if str(cell).strip():
                        lines.append(f"{key}: {cell}")
            elif str(item).strip():
                lines.append(str(item).strip())
        return "\n".join(lines).strip()
    if isinstance(parsed, dict):
        return "\n".join(
            f"{key}: {cell}" for key, cell in parsed.items() if str(cell).strip()
        ).strip()
    return ""


def flatten_ocr_object(value: object, *, prefix: str = "") -> str:
    lines: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"confidence", "warnings"}:
                continue
            label = f"{prefix} {key}".strip()
            if isinstance(child, dict | list):
                nested = flatten_ocr_object(child, prefix=label)
                if nested:
                    lines.append(nested)
            elif str(child).strip():
                lines.append(f"{label}: {child}")
    elif isinstance(value, list):
        for child in value:
            nested = flatten_ocr_object(child, prefix=prefix)
            if nested:
                lines.append(nested)
    return "\n".join(lines).strip()


def read_confidence(value: object) -> float:
    if isinstance(value, list) and value:
        return float(value[0])
    return float(value)
