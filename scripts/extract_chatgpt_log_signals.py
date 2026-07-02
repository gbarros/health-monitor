#!/usr/bin/env python3
"""Extract high-level product signals from a private ChatGPT/Canvas HTML log."""

from __future__ import annotations

import argparse
import collections
import html.parser
import json
import re
from pathlib import Path


CAPTURE_TAGS = {
    "h1",
    "h2",
    "h3",
    "h4",
    "p",
    "li",
    "blockquote",
    "th",
    "td",
}


CATEGORIES: dict[str, list[str]] = {
    "date_or_day": [
        r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b",
        r"\b(?:segunda|terça|terca|quarta|quinta|sexta|sábado|sabado|domingo)\b",
        r"\b(?:janeiro|fevereiro|março|marco|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)\b",
    ],
    "macro_or_calorie": [
        r"\bkcal\b",
        r"\bcalorias?\b",
        r"\bprote[ií]na\b",
        r"\bcarbo(?:idrato)?s?\b",
        r"\bgordura\b",
    ],
    "micronutrient": [
        r"\bmicronutriente",
        r"\bfibra\b",
        r"\bs[oó]dio\b",
        r"\bpot[aá]ssio\b",
        r"\bc[aá]lcio\b",
        r"\bferro\b",
        r"\bvitamina\b",
    ],
    "weight_or_goal": [
        r"\bpeso\b",
        r"\bkg\b",
        r"\bmeta\b",
        r"\bd[eé]ficit\b",
        r"\bperda de peso\b",
    ],
    "label_or_table": [
        r"\br[oó]tulo\b",
        r"\btabela\b",
        r"\bnutricional\b",
        r"\bpor[cç][aã]o\b",
        r"\bpor 100 ?g\b",
        r"\bporção\b",
    ],
    "food_alias_candidate": [
        r"\biogurte\b",
        r"\bbatavo\b",
        r"\bleite\b",
        r"\bproteico\b",
        r"\bqueijo\b",
        r"\bovo\b",
        r"\bfrango\b",
        r"\bp[aã]o\b",
    ],
    "correction_or_revision": [
        r"\bcorrig",
        r"\bcorre[cç][aã]o\b",
        r"\bajust",
        r"\berrad",
        r"\bna verdade\b",
        r"\brecalcular\b",
    ],
    "restaurant_or_external_lookup": [
        r"\bkfc\b",
        r"\bdouble crunch\b",
        r"\bmcdonald",
        r"\bburger\b",
        r"\bcombo\b",
        r"\bifood\b",
        r"\brestaurante\b",
    ],
    "recipe_or_batch": [
        r"\breceita\b",
        r"\brendimento\b",
        r"\bpreparo\b",
        r"\blasanh",
        r"\bmarmita\b",
        r"\bcongel",
    ],
    "review_or_pattern": [
        r"\brevis[aã]o\b",
        r"\bsemana\b",
        r"\btend[eê]ncia\b",
        r"\bpadr[aã]o\b",
        r"\bconsist[eê]ncia\b",
        r"\bsocial\b",
    ],
    "uncertainty": [
        r"\bestimad",
        r"\baproximad",
        r"\bconfian[cç]a\b",
        r"\btalvez\b",
        r"\bprov[aá]vel\b",
        r"\bn[aã]o sei\b",
    ],
}


class BlockParser(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[tuple[str, str]] = []
        self._stack: list[dict[str, object]] = []
        self._hidden = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {name: value or "" for name, value in attrs}
        is_hidden = tag in {"script", "style", "noscript"}
        is_hidden = is_hidden or attr_map.get("aria-hidden") == "true"
        is_hidden = is_hidden or "display:none" in attr_map.get("style", "")
        if is_hidden:
            self._hidden += 1
        self._stack.append(
            {
                "tag": tag,
                "hidden": is_hidden,
                "capture": tag in CAPTURE_TAGS,
                "text": [],
            }
        )

    def handle_endtag(self, tag: str) -> None:
        if not self._stack:
            return
        frame = self._stack.pop()
        if frame["hidden"] and self._hidden:
            self._hidden -= 1
        if frame["tag"] != tag:
            return
        if frame["capture"]:
            text = normalize_text(" ".join(frame["text"]))  # type: ignore[arg-type]
            if text:
                self.blocks.append((str(frame["tag"]), text))

    def handle_data(self, data: str) -> None:
        if self._hidden:
            return
        text = normalize_text(data)
        if not text:
            return
        for frame in reversed(self._stack):
            if frame["capture"]:
                frame["text"].append(text)  # type: ignore[union-attr]
                return


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def compile_categories() -> dict[str, list[re.Pattern[str]]]:
    return {
        category: [re.compile(pattern, re.IGNORECASE) for pattern in patterns]
        for category, patterns in CATEGORIES.items()
    }


def classify(text: str, compiled: dict[str, list[re.Pattern[str]]]) -> set[str]:
    return {
        category
        for category, patterns in compiled.items()
        if any(pattern.search(text) for pattern in patterns)
    }


def candidate_types_for(categories: set[str]) -> tuple[str, ...]:
    candidate_types: list[str] = []
    if "macro_or_calorie" in categories and (
        "food_alias_candidate" in categories or "date_or_day" in categories
    ):
        candidate_types.append("meal_log_candidate")
    if "food_alias_candidate" in categories:
        candidate_types.append("food_alias_candidate")
    if "correction_or_revision" in categories:
        candidate_types.append("correction_candidate")
    if "label_or_table" in categories:
        candidate_types.append("label_or_version_candidate")
    if "restaurant_or_external_lookup" in categories:
        candidate_types.append("restaurant_lookup_candidate")
    if "recipe_or_batch" in categories:
        candidate_types.append("recipe_candidate")
    if "review_or_pattern" in categories:
        candidate_types.append("review_note_candidate")
    if "micronutrient" in categories:
        candidate_types.append("micronutrient_side_quest_candidate")
    return tuple(candidate_types)


def redact_text(value: str) -> str:
    redacted = re.sub(r"\b\d{8,14}\b", "[barcode]", value)
    redacted = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[email]", redacted)
    return redacted


def extract_signal_payload(
    raw_html: str,
    *,
    source_name: str,
    redact: bool = True,
) -> dict[str, object]:
    block_parser = BlockParser()
    block_parser.feed(raw_html)
    compiled = compile_categories()
    candidates: list[dict[str, object]] = []

    for index, (tag, text) in enumerate(block_parser.blocks, start=1):
        categories = classify(text, compiled)
        candidate_types = candidate_types_for(categories)
        if not candidate_types:
            continue
        safe_text = redact_text(text) if redact else text
        for candidate_type in candidate_types:
            candidates.append(
                {
                    "id": f"chatgpt_signal_{len(candidates) + 1}",
                    "candidate_type": candidate_type,
                    "text": safe_text,
                    "categories": sorted(categories),
                    "source_context": {
                        "source_name": source_name,
                        "html_block_index": index,
                        "html_tag": tag,
                    },
                    "durable_write": False,
                }
            )

    return {
        "format": "health-monitor.chatgpt-signals",
        "version": 1,
        "source_name": source_name,
        "redacted": redact,
        "durable_write_policy": "proposals_or_fixtures_only",
        "candidates": candidates,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("html_file", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--snippets-out", type=Path)
    parser.add_argument("--snippets-per-category", type=int, default=8)
    parser.add_argument("--redact", action=argparse.BooleanOptionalAction, default=True)
    args = parser.parse_args()

    raw = args.html_file.read_text(encoding="utf-8", errors="replace")
    block_parser = BlockParser()
    block_parser.feed(raw)

    compiled = compile_categories()
    category_counts: collections.Counter[str] = collections.Counter()
    tag_counts: collections.Counter[str] = collections.Counter()
    cooccurrence_counts: collections.Counter[tuple[str, str]] = collections.Counter()
    snippets: dict[str, list[str]] = collections.defaultdict(list)

    for tag, text in block_parser.blocks:
        tag_counts[tag] += 1
        categories = classify(text, compiled)
        for category in categories:
            category_counts[category] += 1
            if len(snippets[category]) < args.snippets_per_category:
                snippets[category].append(text)
        for left in categories:
            for right in categories:
                if left < right:
                    cooccurrence_counts[(left, right)] += 1

    print(f"File: {args.html_file}")
    print(f"Blocks: {len(block_parser.blocks)}")
    print("\nBlock tags")
    for tag, count in tag_counts.most_common():
        print(f"- {tag}: {count}")

    print("\nSignal categories")
    for category, count in category_counts.most_common():
        print(f"- {category}: {count}")

    print("\nTop co-occurrences")
    for (left, right), count in cooccurrence_counts.most_common(20):
        print(f"- {left} + {right}: {count}")

    if args.snippets_out:
        args.snippets_out.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            "# ChatGPT Log Signal Snippets",
            "",
            "Private local file. Do not commit.",
            "",
        ]
        for category in sorted(snippets):
            lines.append(f"## {category}")
            lines.append("")
            for snippet in snippets[category]:
                lines.append(f"- {snippet}")
            lines.append("")
        args.snippets_out.write_text("\n".join(lines), encoding="utf-8")
        print(f"\nWrote snippets: {args.snippets_out}")

    if args.out:
        payload = extract_signal_payload(
            raw,
            source_name=str(args.html_file),
            redact=args.redact,
        )
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Wrote signal JSON: {args.out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
