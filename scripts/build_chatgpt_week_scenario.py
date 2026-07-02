#!/usr/bin/env python3
"""Build an anonymized week replay scenario from private ChatGPT export signals."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from extract_chatgpt_eval_candidates import extract_eval_cases  # noqa: E402


DEFAULT_START = date(2026, 7, 6)


def redact_text(value: str) -> str:
    redacted = re.sub(r"\b\d{8,14}\b", "[barcode]", value)
    redacted = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[email]", redacted)
    redacted = re.sub(r"\b(?:Gabriel|Ana)\b", "[person]", redacted, flags=re.IGNORECASE)
    return redacted.strip()


def normalized_day(index: int, *, start: date = DEFAULT_START) -> str:
    return (start + timedelta(days=index)).isoformat()


def load_image_refs(manifest_path: Path | None, *, limit: int = 2) -> list[str]:
    if manifest_path is None or not manifest_path.exists():
        return []
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    base = manifest_path.parent
    assets = manifest.get("assets", [])
    preferred = [
        asset
        for asset in assets
        if asset.get("review_classification") in {"nutrition_label", "unreviewed"}
    ]
    refs: list[str] = []
    for asset in preferred[:limit]:
        filename = asset.get("filename")
        if isinstance(filename, str):
            refs.append(str(base / filename))
    return refs


def first_prompt(cases: list[dict[str, Any]], kind: str, fallback: str) -> str:
    for case in cases:
        if case.get("eval_kind") == kind:
            prompt = str(case.get("prompt") or "").strip()
            if prompt:
                return redact_text(prompt)[:260]
    return fallback


def build_scenario(
    raw_html: str,
    *,
    source_name: str,
    image_refs: list[str] | None = None,
    start: date = DEFAULT_START,
) -> dict[str, Any]:
    cases = extract_eval_cases(raw_html, source_name=source_name)
    image_refs = image_refs or []
    label_image = image_refs[0] if image_refs else None
    return {
        "format": "health-monitor.week-replay",
        "version": 1,
        "source": "chatgpt-export-derived",
        "anonymized": True,
        "start_day": start.isoformat(),
        "household": "Casa Week Replay",
        "profiles": ["Person A", "Person B"],
        "actions": [
            {"type": "setup_household", "day": normalized_day(0, start=start)},
            {
                "type": "label_scan",
                "day": normalized_day(0, start=start),
                "barcode": "7891000000000",
                "table_text": "Produto: semanaqueijo\nMarca: Synthetic\nPorcao: 100 g\nValor energetico: 315 kcal\nProteinas: 23 g\nCarboidratos: 3 g\nGorduras totais: 24 g",
                "image": label_image,
                "quantity_g": 100,
            },
            {"type": "confirm_latest_proposal", "day": normalized_day(0, start=start)},
            {
                "type": "text_meal",
                "day": normalized_day(1, start=start),
                "text": first_prompt(cases, "weird_meal_phrasing", "10am 80g semanaqueijo"),
            },
            {"type": "confirm_latest_proposal", "day": normalized_day(1, start=start)},
            {
                "type": "recipe",
                "day": normalized_day(2, start=start),
                "recipe_text": "Recipe: Replay breakfast batch\nYield: 1000 g\nIngredients:\n1000g semanaqueijo",
                "quantity_g": 120,
            },
            {"type": "confirm_latest_proposal", "day": normalized_day(2, start=start)},
            {
                "type": "chat_question",
                "day": normalized_day(3, start=start),
                "message": first_prompt(
                    cases,
                    "restaurant_or_social_estimate",
                    "Estimate a KFC Double Crunch combo in Brazil and explain confidence.",
                ),
            },
            {
                "type": "correction_request",
                "day": normalized_day(4, start=start),
                "message": first_prompt(cases, "correction", "Na verdade, corrigir o queijo para 50g."),
            },
            {
                "type": "review_note_request",
                "day": normalized_day(5, start=start),
                "message": first_prompt(cases, "review_note", "Create a review note about weekly consistency."),
            },
            {"type": "switch_profile", "day": normalized_day(5, start=start), "profile": "Person B"},
            {"type": "text_meal", "day": normalized_day(5, start=start), "text": "8am 170g iogurte proteico"},
            {"type": "switch_profile", "day": normalized_day(6, start=start), "profile": "Person A"},
            {"type": "weight_entry", "day": normalized_day(6, start=start), "weight_kg": 91.0},
            {"type": "expect_day_totals", "day": normalized_day(6, start=start)},
        ],
    }


def validate_image_refs(scenario: dict[str, Any]) -> None:
    for action in scenario.get("actions", []):
        image = action.get("image") if isinstance(action, dict) else None
        if image and not Path(str(image)).exists():
            raise FileNotFoundError(str(image))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("html_file", type=Path)
    parser.add_argument("--image-manifest", type=Path)
    parser.add_argument("--out", type=Path, default=Path("private/e2e/chatgpt-week-scenario.json"))
    parser.add_argument("--start-day", type=date.fromisoformat, default=DEFAULT_START)
    args = parser.parse_args()

    raw_html = args.html_file.read_text(encoding="utf-8", errors="replace")
    scenario = build_scenario(
        raw_html,
        source_name=str(args.html_file),
        image_refs=load_image_refs(args.image_manifest),
        start=args.start_day,
    )
    validate_image_refs(scenario)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(scenario, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote week replay scenario: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
