from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Protocol

from health_monitor.domain.nutrients import Nutrients


@dataclass(frozen=True)
class FoodLookupCandidate:
    source_type: str
    source_name: str
    source_id: str
    product_name: str
    brand: str | None
    barcode: str | None
    nutrients_per_100g: Nutrients
    serving_size_g: float | None
    confidence: float
    warnings: tuple[str, ...] = ()
    source_url: str | None = None
    food_id: str | None = None
    food_version_id: str | None = None
    id: str = ""


class FoodLookupProvider(Protocol):
    def lookup(
        self,
        *,
        phrase: str | None = None,
        barcode: str | None = None,
    ) -> list[FoodLookupCandidate]:
        pass


class StaticFoodLookupProvider:
    def __init__(self, candidates: list[FoodLookupCandidate]) -> None:
        self.candidates = candidates

    def lookup(
        self,
        *,
        phrase: str | None = None,
        barcode: str | None = None,
    ) -> list[FoodLookupCandidate]:
        normalized_phrase = phrase.casefold().strip() if phrase else None
        results: list[FoodLookupCandidate] = []
        for candidate in self.candidates:
            if barcode and candidate.barcode != barcode:
                continue
            if normalized_phrase and normalized_phrase not in candidate.product_name.casefold():
                continue
            results.append(candidate)
        return results


class OpenFoodFactsLookupProvider:
    def __init__(
        self,
        *,
        base_url: str = "https://world.openfoodfacts.org",
        user_agent: str = "health-monitor/0.1 private household app",
        timeout_seconds: float = 8,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.user_agent = user_agent
        self.timeout_seconds = timeout_seconds

    def lookup(
        self,
        *,
        phrase: str | None = None,
        barcode: str | None = None,
    ) -> list[FoodLookupCandidate]:
        if barcode:
            return self._lookup_barcode(barcode)
        if phrase:
            return self._lookup_phrase(phrase)
        return []

    def _lookup_barcode(self, barcode: str) -> list[FoodLookupCandidate]:
        payload = self._get_json(f"{self.base_url}/api/v2/product/{barcode}.json")
        if not payload or payload.get("status") != 1:
            return []
        candidate = self._candidate_from_product(payload.get("product") or {}, source_id=barcode)
        return [candidate] if candidate is not None else []

    def _lookup_phrase(self, phrase: str) -> list[FoodLookupCandidate]:
        query = urllib.parse.urlencode(
            {
                "search_terms": phrase,
                "countries_tags_en": "Brazil",
                "page_size": 5,
                "json": 1,
            }
        )
        payload = self._get_json(f"{self.base_url}/cgi/search.pl?{query}")
        products = payload.get("products", []) if payload else []
        candidates = [
            candidate
            for product in products
            if (candidate := self._candidate_from_product(product, source_id=str(product.get("code") or "")))
            is not None
        ]
        return candidates

    def _get_json(self, url: str) -> dict[str, object] | None:
        request = urllib.request.Request(url, headers={"user-agent": self.user_agent})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def _candidate_from_product(
        self,
        product: dict[str, object],
        *,
        source_id: str,
    ) -> FoodLookupCandidate | None:
        nutriments = product.get("nutriments")
        if not isinstance(nutriments, dict):
            return None
        name = str(product.get("product_name") or product.get("generic_name") or "").strip()
        if not name:
            return None
        barcode = str(product.get("code") or source_id or "").strip() or None
        serving_size_g = parse_serving_size_g(str(product.get("serving_size") or ""))
        return FoodLookupCandidate(
            source_type="external_database",
            source_name="Open Food Facts",
            source_id=source_id,
            source_url=f"{self.base_url}/product/{barcode}" if barcode else self.base_url,
            product_name=name,
            brand=str(product.get("brands") or "").strip() or None,
            barcode=barcode,
            serving_size_g=serving_size_g,
            nutrients_per_100g=Nutrients(
                calories_kcal=read_nutriment(nutriments, "energy-kcal_100g", "energy-kcal"),
                protein_g=read_nutriment(nutriments, "proteins_100g", "proteins"),
                carbs_g=read_nutriment(nutriments, "carbohydrates_100g", "carbohydrates"),
                fat_g=read_nutriment(nutriments, "fat_100g", "fat"),
                fiber_g=read_nutriment(nutriments, "fiber_100g", "fiber"),
                sodium_mg=read_nutriment(nutriments, "sodium_100g", "sodium") * 1000,
            ),
            confidence=0.72,
            warnings=("Open Food Facts is user-contributed; verify label before relying on it.",),
        )


def read_nutriment(payload: dict[str, object], *keys: str) -> float:
    for key in keys:
        value = payload.get(key)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                return 0
    return 0


def parse_serving_size_g(value: str) -> float | None:
    match = re.search(r"(\d+(?:[,.]\d+)?)\s*g\b", value, re.I)
    if match is None:
        return None
    return float(match.group(1).replace(",", "."))
