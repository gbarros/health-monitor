#!/usr/bin/env python3
"""Inspect a large exported ChatGPT/Canvas HTML log without dumping content."""

from __future__ import annotations

import argparse
import collections
import html.parser
import re
from pathlib import Path


KEYWORDS = [
    "kcal",
    "calorias",
    "proteina",
    "proteína",
    "carbo",
    "carboidrato",
    "gordura",
    "fibra",
    "sodio",
    "sódio",
    "micronutriente",
    "peso",
    "meta",
    "revisao",
    "revisão",
    "iogurte",
    "leite",
    "queijo",
    "frango",
    "ovo",
    "kfc",
    "batavo",
]


DATE_PATTERNS = [
    re.compile(r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b"),
    re.compile(
        r"\b(?:segunda|terça|terca|quarta|quinta|sexta|sábado|sabado|domingo)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:janeiro|fevereiro|março|marco|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)\b",
        re.IGNORECASE,
    ),
]


class StructureParser(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tag_counts: collections.Counter[str] = collections.Counter()
        self.attr_counts: collections.Counter[str] = collections.Counter()
        self.class_counts: collections.Counter[str] = collections.Counter()
        self.text_chunks: list[str] = []
        self._hidden_stack: list[bool] = []
        self._in_hidden = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tag_counts[tag] += 1
        attr_map = {name: value or "" for name, value in attrs}
        for name, value in attrs:
            self.attr_counts[name] += 1
            if name == "class" and value:
                for class_name in value.split():
                    self.class_counts[class_name] += 1
        is_hidden = False
        if tag in {"script", "style", "noscript"}:
            is_hidden = True
        if attr_map.get("aria-hidden") == "true" or "display:none" in attr_map.get("style", ""):
            is_hidden = True
        self._hidden_stack.append(is_hidden)
        if is_hidden:
            self._in_hidden += 1

    def handle_endtag(self, tag: str) -> None:
        if self._hidden_stack and self._hidden_stack.pop() and self._in_hidden:
            self._in_hidden -= 1

    def handle_data(self, data: str) -> None:
        if self._in_hidden:
            return
        text = normalize_text(data)
        if len(text) >= 3:
            self.text_chunks.append(text)


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def print_counter(title: str, counter: collections.Counter[str], limit: int) -> None:
    print(f"\n{title}")
    for key, count in counter.most_common(limit):
        print(f"- {key}: {count}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("html_file", type=Path)
    parser.add_argument("--top", type=int, default=20)
    args = parser.parse_args()

    source = args.html_file
    raw = source.read_text(encoding="utf-8", errors="replace")

    inspector = StructureParser()
    inspector.feed(raw)

    full_text = "\n".join(inspector.text_chunks)
    lowered = full_text.lower()
    keyword_counts = collections.Counter({keyword: lowered.count(keyword.lower()) for keyword in KEYWORDS})
    date_hits = sum(any(pattern.search(chunk) for pattern in DATE_PATTERNS) for chunk in inspector.text_chunks)

    chunk_lengths = [len(chunk) for chunk in inspector.text_chunks]
    chunk_lengths.sort()
    p50 = chunk_lengths[len(chunk_lengths) // 2] if chunk_lengths else 0
    p95 = chunk_lengths[int(len(chunk_lengths) * 0.95)] if chunk_lengths else 0

    print(f"File: {source}")
    print(f"Size bytes: {source.stat().st_size}")
    print(f"HTML chars: {len(raw)}")
    print(f"Text chunks: {len(inspector.text_chunks)}")
    print(f"Text chars: {len(full_text)}")
    print(f"Median chunk chars: {p50}")
    print(f"P95 chunk chars: {p95}")
    print(f"Chunks with date-like text: {date_hits}")

    print_counter("Top tags", inspector.tag_counts, args.top)
    print_counter("Top attributes", inspector.attr_counts, args.top)
    print_counter("Top classes", inspector.class_counts, args.top)
    print_counter("Keyword counts", keyword_counts, args.top)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
