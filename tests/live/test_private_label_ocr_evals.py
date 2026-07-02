from __future__ import annotations

import json
import os
import unicodedata
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from health_monitor.application.service import HealthMonitorService
from health_monitor.lookup.labels import OllamaLabelTextExtractor


def private_ocr_enabled() -> bool:
    return os.environ.get("PRIVATE_OCR_EVALS", "false").casefold() in {
        "1",
        "true",
        "yes",
        "on",
    }


def eval_dir() -> Path:
    return Path(os.environ.get("PRIVATE_OCR_EVAL_DIR", "private/ocr-evals"))


@unittest.skipUnless(private_ocr_enabled(), "set PRIVATE_OCR_EVALS=true to run private label OCR evals")
class PrivateLabelOCREvalTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        base_url = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
        try:
            urllib.request.urlopen(f"{base_url}/api/tags", timeout=2).read()
        except (OSError, urllib.error.URLError) as exc:
            raise unittest.SkipTest(f"Ollama is not reachable at {base_url}") from exc
        if not eval_dir().exists():
            raise unittest.SkipTest(f"private OCR eval dir does not exist: {eval_dir()}")

    def test_private_label_images_extract_proposal_grade_text(self) -> None:
        cases = load_private_cases(eval_dir())
        if not cases:
            raise unittest.SkipTest(f"no private OCR eval JSON files found in {eval_dir()}")
        extractor = OllamaLabelTextExtractor(
            base_url=os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
            model=os.environ.get("OCR_MODEL", os.environ.get("OLLAMA_OCR_MODEL", "glm-ocr:latest")),
            timeout_seconds=float(os.environ.get("PRIVATE_OCR_TIMEOUT_SECONDS", "90")),
        )
        for case in cases:
            with self.subTest(case=case["id"]):
                image_path = Path(str(case["image_path"]))
                content = image_path.read_bytes()
                extraction = extractor.extract(
                    image_bytes=content,
                    mime_type=str(case.get("mime_type") or "image/jpeg"),
                    filename=image_path.name,
                )
                self.assertIsNotNone(extraction)
                assert extraction is not None
                self.assertGreaterEqual(extraction.confidence, float(case.get("min_confidence", 0.35)))
                normalized_text = normalize_text_for_assertion(extraction.text)
                for needle in case.get("expected_text_contains", []):
                    self.assertIn(normalize_text_for_assertion(str(needle)), normalized_text)
                service = HealthMonitorService()
                household = service.create_household(name="OCR Eval")
                person = service.create_person(
                    household_id=household.id,
                    name="Gabriel",
                    timezone="America/Sao_Paulo",
                )
                attachment = service.create_attachment(
                    household_id=household.id,
                    person_id=person.id,
                    object_type="nutrition_label_image",
                    mime_type=str(case.get("mime_type") or "image/jpeg"),
                    content=content,
                    filename=image_path.name,
                )
                proposal = service.propose_label_scan(
                    household_id=household.id,
                    person_id=person.id,
                    table_text=extraction.text,
                    barcode=case.get("barcode"),
                    attachment_id=attachment.id,
                )
                self.assertEqual(proposal.proposal_type, "food_version_from_label")
                self.assertEqual(proposal.status, "draft")
                self.assertIn("nutrients_per_100g", proposal.payload)


def load_private_cases(directory: Path) -> list[dict[str, object]]:
    cases: list[dict[str, object]] = []
    for path in sorted(directory.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            payload.setdefault("id", path.stem)
            image_path = Path(str(payload["image_path"]))
            if not image_path.is_absolute():
                payload["image_path"] = str((path.parent / image_path).resolve())
            cases.append(payload)
    return cases


def normalize_text_for_assertion(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(char for char in decomposed if not unicodedata.combining(char)).casefold()


if __name__ == "__main__":
    unittest.main()
