from __future__ import annotations

import base64
import json
import urllib.request
from dataclasses import dataclass
from typing import Protocol


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
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds

    def extract(
        self,
        *,
        image_bytes: bytes,
        mime_type: str,
        filename: str | None = None,
    ) -> LabelTextExtraction | None:
        prompt = (
            "Read this nutrition facts label or Brazilian tabela nutricional. "
            "Return only JSON with keys text, confidence, warnings. The text value must be "
            "line-oriented key/value text using labels like Produto, Marca, Porcao, "
            "Valor energetico, Proteinas, Carboidratos, Gorduras totais, Fibra alimentar, "
            "Sodio, Codigo de barras when visible. Preserve numbers and units."
        )
        body = json.dumps(
            {
                "model": self.model,
                "prompt": prompt,
                "images": [base64.b64encode(image_bytes).decode("ascii")],
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
        try:
            raw_response = payload.get("response") or payload.get("thinking")
            if not raw_response:
                return None
            parsed = json.loads(raw_response)
            text = str(parsed.get("text") or parsed.get("ocr_text") or "").strip()
            if not text:
                return None
            warnings = parsed.get("warnings", ())
            if isinstance(warnings, str):
                warning_items = (warnings,)
            else:
                warning_items = tuple(str(item) for item in warnings)
            return LabelTextExtraction(
                text=text,
                source=f"ollama_vision:{self.model}",
                confidence=float(parsed.get("confidence", 0.45)),
                warnings=warning_items,
            )
        except (TypeError, ValueError, json.JSONDecodeError):
            return None
