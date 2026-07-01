from __future__ import annotations

from dataclasses import dataclass

from health_monitor.domain.foods import FoodCatalog, FoodVersion


@dataclass(frozen=True)
class FoodResolution:
    food_id: str
    food_version_id: str
    reason: str
    confidence: float
    needs_clarification: bool = False


class FoodResolver:
    def __init__(self, catalog: FoodCatalog) -> None:
        self.catalog = catalog

    def resolve_phrase(self, phrase: str, *, person_id: str | None = None) -> FoodResolution | None:
        normalized = phrase.casefold().strip()
        best_alias = None
        for alias in self.catalog.aliases.values():
            if alias.phrase.casefold().strip() != normalized:
                continue
            if alias.person_id is not None and alias.person_id != person_id:
                continue
            if best_alias is None or alias.confidence > best_alias.confidence:
                best_alias = alias

        if best_alias is None:
            return None

        version: FoodVersion = self.catalog.get_default_version(best_alias.food_id)
        return FoodResolution(
            food_id=best_alias.food_id,
            food_version_id=version.id,
            reason="alias_default_version",
            confidence=best_alias.confidence,
        )

    def resolve_barcode(self, barcode: str) -> FoodResolution | None:
        association = self.catalog.resolve_barcode(barcode)
        if association is None:
            return None
        return FoodResolution(
            food_id=association.food_id,
            food_version_id=association.food_version_id,
            reason="confirmed_barcode_association",
            confidence=association.confidence,
        )

