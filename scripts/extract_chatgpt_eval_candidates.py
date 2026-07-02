#!/usr/bin/env python3
"""Extract private live-agent eval candidates from ChatGPT export signals."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from extract_chatgpt_log_signals import extract_signal_payload  # noqa: E402


TYPE_TO_EVAL_KIND = {
    "correction_candidate": "correction",
    "review_note_candidate": "review_note",
    "label_or_version_candidate": "ambiguity_or_version_reference",
    "meal_log_candidate": "weird_meal_phrasing",
    "restaurant_lookup_candidate": "restaurant_or_social_estimate",
}

DEFAULT_LIMITS = {
    "correction": 8,
    "review_note": 8,
    "ambiguity_or_version_reference": 8,
    "weird_meal_phrasing": 12,
    "restaurant_or_social_estimate": 6,
}


def candidate_to_eval_case(candidate: dict[str, Any], *, sequence: int) -> dict[str, Any] | None:
    candidate_types = candidate.get("candidate_type")
    if not isinstance(candidate_types, str):
        return None
    eval_kind = TYPE_TO_EVAL_KIND.get(candidate_types)
    if eval_kind is None:
        return None
    source_context = candidate.get("source_context")
    if not isinstance(source_context, dict):
        source_context = {}
    prompt = str(candidate.get("text") or "").strip()
    if not prompt:
        return None
    return {
        "id": f"chatgpt_eval_{sequence:03d}",
        "eval_kind": eval_kind,
        "prompt": prompt,
        "source_context": source_context,
        "expected_invariants": invariants_for(eval_kind),
        "durable_write": False,
        "review_status": "unreviewed",
    }


def invariants_for(eval_kind: str) -> list[str]:
    if eval_kind == "correction":
        return [
            "no_direct_mutation",
            "creates_or_explains_missing_diary_entry_update_proposal",
        ]
    if eval_kind == "review_note":
        return ["no_direct_mutation", "creates_or_explains_review_note_proposal"]
    if eval_kind == "ambiguity_or_version_reference":
        return [
            "uses_food_version_history_or_resolution",
            "clarifies_or_records_resolution_reason",
        ]
    if eval_kind == "restaurant_or_social_estimate":
        return ["uses_lookup_or_estimate_evidence", "confidence_is_visible"]
    return ["creates_diary_proposal_or_clarification", "no_direct_mutation"]


def extract_eval_cases(
    raw_html: str,
    *,
    source_name: str,
    start_date: date | None = None,
    end_date: date | None = None,
    limits: dict[str, int] | None = None,
) -> list[dict[str, Any]]:
    limits = limits or DEFAULT_LIMITS
    payload = extract_signal_payload(
        raw_html,
        source_name=source_name,
        redact=True,
        start_date=start_date,
        end_date=end_date,
    )
    selected_counts = {key: 0 for key in limits}
    cases: list[dict[str, Any]] = []
    for candidate in payload.get("candidates", []):
        if not isinstance(candidate, dict):
            continue
        maybe_case = candidate_to_eval_case(candidate, sequence=len(cases) + 1)
        if maybe_case is None:
            continue
        eval_kind = str(maybe_case["eval_kind"])
        if selected_counts.get(eval_kind, 0) >= limits.get(eval_kind, 0):
            continue
        selected_counts[eval_kind] = selected_counts.get(eval_kind, 0) + 1
        cases.append(maybe_case)
    return cases


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("html_file", type=Path)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("private/evals/chatgpt-eval-candidates.jsonl"),
    )
    parser.add_argument("--start-date", type=date.fromisoformat)
    parser.add_argument("--end-date", type=date.fromisoformat)
    args = parser.parse_args()

    raw_html = args.html_file.read_text(encoding="utf-8", errors="replace")
    cases = extract_eval_cases(
        raw_html,
        source_name=str(args.html_file),
        start_date=args.start_date,
        end_date=args.end_date,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        "\n".join(json.dumps(case, ensure_ascii=False, sort_keys=True) for case in cases)
        + ("\n" if cases else ""),
        encoding="utf-8",
    )
    print(f"Wrote eval candidates: {len(cases)}")
    print(f"Output: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
