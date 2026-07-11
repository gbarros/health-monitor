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


@dataclass(frozen=True)
class ImageInspection:
    description: str
    image_type: str
    observations: tuple[str, ...]
    visible_text: str | None
    ocr_recommended: bool
    source: str
    confidence: float
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ImageSetInspection:
    description: str
    image_type: str
    images: tuple[dict[str, object], ...]
    chronological_attachment_order: tuple[int, ...]
    steps: tuple[dict[str, object], ...]
    questions: tuple[str, ...]
    ocr_recommended: bool
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


class ImageAnalyzer(Protocol):
    def inspect(
        self,
        *,
        image_bytes: bytes,
        mime_type: str,
        filename: str | None = None,
    ) -> ImageInspection | None:
        pass

    def inspect_many(
        self,
        *,
        images: list[tuple[bytes, str, str | None]],
        context_text: str = "",
    ) -> ImageSetInspection | None:
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


class StaticImageAnalyzer:
    def __init__(
        self,
        inspection: ImageInspection | None,
        set_inspection: ImageSetInspection | None = None,
    ) -> None:
        self.inspection = inspection
        self.set_inspection = set_inspection

    def inspect(
        self,
        *,
        image_bytes: bytes,
        mime_type: str,
        filename: str | None = None,
    ) -> ImageInspection | None:
        return self.inspection

    def inspect_many(
        self,
        *,
        images: list[tuple[bytes, str, str | None]],
        context_text: str = "",
    ) -> ImageSetInspection | None:
        return self.set_inspection


class OllamaImageAnalyzer:
    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:11434",
        model: str = "kimi-k2.6:cloud",
        timeout_seconds: float = 90,
        max_attempts: int = 1,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_attempts = max(1, max_attempts)

    def inspect(
        self,
        *,
        image_bytes: bytes,
        mime_type: str,
        filename: str | None = None,
    ) -> ImageInspection | None:
        prompt = (
            "Inspect this image for a private nutrition assistant. Determine whether it is a "
            "food plate, packaged food, nutrition label/table, receipt/menu, body measurement, "
            "or another scene. Describe only visible evidence; do not invent weights or exact "
            "ingredients. Return only JSON with keys description, image_type, observations "
            "(array of short strings), visible_text (string or null), ocr_recommended (boolean), "
            "confidence (0 to 1), and warnings. Set ocr_recommended=true when exact text, numbers, "
            "a label, table, barcode, menu, or receipt would materially help."
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
            inspection = parse_ollama_image_inspection_payload(payload, model=self.model)
            if inspection is not None:
                return inspection
        return None

    def inspect_many(
        self,
        *,
        images: list[tuple[bytes, str, str | None]],
        context_text: str = "",
    ) -> ImageSetInspection | None:
        if not images:
            return None
        prompt = (
            "You are the specialist multimodal submodel for a private health and nutrition assistant. "
            "Return structured visual evidence to a separate local reasoning agent. Do not answer the "
            "user directly, calculate nutrition, or propose an app write. Analyze all attached images "
            "collectively. "
            "Attachment indexes are 1-based in supplied order. Use the user context when interpreting "
            "relationships between images, but distinguish visible evidence from inference. Do not assume "
            "multiple images form a sequence. Classify the image set. Only when the original user message "
            "or visible evidence indicates a meal or weighing sequence, infer chronological order using "
            "the supplied ordering metadata and foods that "
            "appear or disappear; read the active scale unit indicator rather than the capacity label; "
            "identify each newly added food conservatively; include alternatives when uncertain; and flag "
            "bones, skin, pits, packaging, or other inedible mass. Do not calculate nutrition or convert "
            "units. For labels, tables, receipts, or exact text, set ocr_recommended=true. Return exactly "
            "one compact JSON object, without markdown, with keys: description, image_type, images, "
            "chronological_attachment_order, steps, questions, ocr_recommended, confidence, warnings. "
            "Each images item has attachment_index, visible_foods, scale_value, scale_unit, confidence. "
            "Each steps item has attachment_index, food, alternatives, displayed_weight, unit, confidence, "
            "inedible_mass, caveat. If any food has plausible alternatives or confidence below 0.9, add a "
            "targeted confirmation question. "
            f"Handoff context from the local reasoning agent:\n{context_text.strip() or 'No additional context.'}"
        )
        encoded_images = [base64.b64encode(item[0]).decode("ascii") for item in images]
        body = json.dumps(
            {
                "model": self.model,
                "messages": [
                    {"role": "user", "content": prompt, "images": encoded_images}
                ],
                "stream": False,
                "format": "json",
                "think": False,
                "options": {"temperature": 0, "num_predict": 2000},
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=body,
            headers={"content-type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except OSError as exc:
            raise RuntimeError(
                f"vision model {self.model} image-set request failed: "
                f"{type(exc).__name__}: {exc}"
            ) from exc
        return parse_ollama_image_set_payload(payload, model=self.model)


class OllamaLabelTextExtractor:
    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:11434",
        model: str = "glm-ocr:latest",
        timeout_seconds: float = 45,
        max_attempts: int = 1,
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
            source=f"ollama_ocr:{model}",
            confidence=read_confidence(parsed.get("confidence", 0.45)),
            warnings=warning_items,
        )
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


def parse_ollama_image_inspection_payload(
    payload: dict[str, object],
    *,
    model: str,
) -> ImageInspection | None:
    try:
        raw_response = payload.get("response") or payload.get("thinking")
        if not raw_response:
            return None
        parsed = json.loads(strip_json_fence(str(raw_response)))
        if not isinstance(parsed, dict):
            return None
        description = str(parsed.get("description") or "").strip()
        if not description:
            return None
        raw_observations = parsed.get("observations", ())
        observations = (
            (str(raw_observations).strip(),)
            if isinstance(raw_observations, str)
            else tuple(str(item).strip() for item in raw_observations if str(item).strip())
            if isinstance(raw_observations, list | tuple)
            else ()
        )
        raw_warnings = parsed.get("warnings", ())
        warnings = (
            (str(raw_warnings).strip(),)
            if isinstance(raw_warnings, str) and str(raw_warnings).strip()
            else tuple(str(item).strip() for item in raw_warnings if str(item).strip())
            if isinstance(raw_warnings, list | tuple)
            else ()
        )
        visible_text = str(parsed.get("visible_text") or "").strip() or None
        return ImageInspection(
            description=description,
            image_type=str(parsed.get("image_type") or "other").strip() or "other",
            observations=observations,
            visible_text=visible_text,
            ocr_recommended=read_bool(parsed.get("ocr_recommended", False)),
            source=f"ollama_vision:{model}",
            confidence=read_confidence(parsed.get("confidence", 0.45)),
            warnings=warnings,
        )
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


def parse_ollama_image_set_payload(
    payload: dict[str, object],
    *,
    model: str,
) -> ImageSetInspection | None:
    try:
        message = payload.get("message")
        raw_response = (
            message.get("content")
            if isinstance(message, dict)
            else payload.get("response") or payload.get("thinking")
        )
        if not raw_response:
            return None
        parsed = json.loads(strip_json_fence(str(raw_response)))
        if not isinstance(parsed, dict):
            return None
        raw_images = parsed.get("images", ())
        raw_steps = parsed.get("steps", parsed.get("inferred_additions", ()))
        images = tuple(dict(item) for item in raw_images if isinstance(item, dict))
        steps = tuple(dict(item) for item in raw_steps if isinstance(item, dict))
        raw_order = parsed.get("chronological_attachment_order", ())
        order = tuple(int(item) for item in raw_order) if isinstance(raw_order, list) else ()
        raw_questions = parsed.get("questions", ())
        questions = (
            (str(raw_questions).strip(),)
            if isinstance(raw_questions, str) and raw_questions.strip()
            else tuple(str(item).strip() for item in raw_questions if str(item).strip())
            if isinstance(raw_questions, list)
            else ()
        )
        synthesized_questions = list(questions)
        for step in steps:
            attachment_index = step.get("attachment_index", "?")
            food = str(step.get("food") or "alimento").strip()
            alternatives = step.get("alternatives", ())
            alternative_names = (
                [str(item).strip() for item in alternatives if str(item).strip()]
                if isinstance(alternatives, list)
                else []
            )
            confidence = read_confidence(step.get("confidence", 0.6))
            if alternative_names:
                synthesized_questions.append(
                    f"Confirme o alimento da foto {attachment_index}: {food} ou "
                    f"{', '.join(alternative_names)}?"
                )
            elif confidence < 0.9:
                synthesized_questions.append(
                    f"Confirme se o alimento da foto {attachment_index} é {food}."
                )
            inedible_mass = str(step.get("inedible_mass") or "").casefold()
            if inedible_mass in {"possible", "likely", "possível", "provável"}:
                synthesized_questions.append(
                    f"O peso da foto {attachment_index} inclui osso, pele ou outra parte não comestível?"
                )
        questions = tuple(dict.fromkeys(synthesized_questions))
        raw_warnings = parsed.get("warnings", ())
        warnings = (
            (str(raw_warnings).strip(),)
            if isinstance(raw_warnings, str) and raw_warnings.strip()
            else tuple(str(item).strip() for item in raw_warnings if str(item).strip())
            if isinstance(raw_warnings, list)
            else ()
        )
        description = str(parsed.get("description") or "").strip()
        if not description and steps:
            description = f"Related image set with {len(steps)} inferred steps."
        if not description:
            return None
        return ImageSetInspection(
            description=description,
            image_type=str(parsed.get("image_type") or "other").strip() or "other",
            images=images,
            chronological_attachment_order=order,
            steps=steps,
            questions=questions,
            ocr_recommended=read_bool(parsed.get("ocr_recommended", False)),
            source=f"ollama_vision:{model}",
            confidence=read_confidence(parsed.get("confidence", 0.6)),
            warnings=warnings,
        )
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


def read_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().casefold() in {"1", "true", "yes", "on"}


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
