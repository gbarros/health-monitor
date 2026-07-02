from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from typing import Protocol

from health_monitor.domain.nutrients import Nutrients


@dataclass(frozen=True)
class NutritionEstimate:
    phrase: str
    food_name: str
    nutrients_per_100g: Nutrients
    source: str
    confidence: float
    notes: str


class FoodEstimator(Protocol):
    def estimate(self, phrase: str) -> NutritionEstimate | None:
        pass


class StaticFoodEstimator:
    def __init__(self, estimates: dict[str, NutritionEstimate]) -> None:
        self.estimates = {key.casefold().strip(): value for key, value in estimates.items()}

    def estimate(self, phrase: str) -> NutritionEstimate | None:
        return self.estimates.get(phrase.casefold().strip())


class OllamaFoodEstimator:
    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:11434",
        model: str = "llama3.1",
        timeout_seconds: float = 30,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds

    def estimate(self, phrase: str) -> NutritionEstimate | None:
        prompt = (
            "Return only compact JSON: {\"food_name\":string,\"calories_kcal\":number,"
            "\"protein_g\":number,\"carbs_g\":number,\"fat_g\":number,"
            "\"fiber_g\":number,\"sodium_mg\":number,\"confidence\":number,\"notes\":string}. "
            f"Nutrition per 100g for {phrase}."
        )
        body = json.dumps(
            {
                "model": self.model,
                "prompt": prompt,
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
        return parse_ollama_estimate_payload(payload, phrase=phrase, model=self.model)


def parse_ollama_estimate_payload(
    payload: dict[str, object],
    *,
    phrase: str,
    model: str,
) -> NutritionEstimate | None:
    try:
        raw_response = payload.get("response") or payload.get("thinking")
        if not raw_response:
            return None
        estimate = json.loads(raw_response)
        nutrition = (
            estimate.get("nutrition_100g")
            or estimate.get("nutrition")
            or estimate.get("per_100g")
            or estimate
        )
        return NutritionEstimate(
            phrase=phrase,
            food_name=str(
                estimate.get("food_name")
                or estimate.get("food")
                or estimate.get("name")
                or phrase
            ),
            nutrients_per_100g=Nutrients(
                calories_kcal=read_float(nutrition, "calories_kcal", "calories", "kcal"),
                protein_g=read_float(nutrition, "protein_g", "protein"),
                carbs_g=read_float(nutrition, "carbs_g", "carbs", "carbohydrates"),
                fat_g=read_float(nutrition, "fat_g", "fat"),
                fiber_g=read_float(nutrition, "fiber_g", "fiber"),
                sodium_mg=read_float(nutrition, "sodium_mg", "sodium"),
            ),
            source=f"ollama:{model}",
            confidence=float(estimate.get("confidence", 0.35)),
            notes=str(
                estimate.get("notes")
                or estimate.get("data_source_notes")
                or "Ollama model estimate"
            ),
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None


def read_float(payload: dict[str, object], *keys: str) -> float:
    for key in keys:
        value = payload.get(key)
        if value is not None:
            return float(value)
    return 0
