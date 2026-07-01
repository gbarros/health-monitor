#!/usr/bin/env python3
"""Extract high-level product signals from a private ChatGPT/Canvas HTML log."""

from __future__ import annotations

import argparse
import collections
import html.parser
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("html_file", type=Path)
    parser.add_argument("--snippets-out", type=Path)
    parser.add_argument("--snippets-per-category", type=int, default=8)
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

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
