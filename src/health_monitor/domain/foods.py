from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from health_monitor.domain.nutrients import Nutrients


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class Food:
    id: str
    household_id: str
    name: str
    brand: str | None = None
    default_version_id: str | None = None
    archived: bool = False


@dataclass(frozen=True)
class FoodVersion:
    id: str
    food_id: str
    label: str
    nutrients_per_100g: Nutrients
    source: str
    serving_size_g: float | None = None
    confidence: float = 1.0
    created_at: datetime = field(default_factory=utc_now)
    archived: bool = False


@dataclass(frozen=True)
class FoodAlias:
    id: str
    household_id: str
    phrase: str
    food_id: str
    person_id: str | None = None
    confidence: float = 1.0


@dataclass(frozen=True)
class BarcodeAssociation:
    id: str
    household_id: str
    barcode: str
    food_id: str
    food_version_id: str
    source: str
    confidence: float = 1.0
    confirmed_at: datetime | None = None
    archived: bool = False


class FoodCatalog:
    def __init__(self) -> None:
        self.foods: dict[str, Food] = {}
        self.versions: dict[str, FoodVersion] = {}
        self.aliases: dict[str, FoodAlias] = {}
        self.barcode_associations: dict[str, BarcodeAssociation] = {}

    def add_food(self, food: Food) -> Food:
        self.foods[food.id] = food
        return food

    def add_version(self, version: FoodVersion, *, make_default: bool = False) -> FoodVersion:
        if version.food_id not in self.foods:
            raise ValueError(f"unknown food_id: {version.food_id}")
        self.versions[version.id] = version
        if make_default:
            self.set_default_version(version.food_id, version.id)
        return version

    def set_default_version(self, food_id: str, version_id: str) -> None:
        food = self.foods[food_id]
        if self.versions[version_id].food_id != food_id:
            raise ValueError("version does not belong to food")
        self.foods[food_id] = Food(
            id=food.id,
            household_id=food.household_id,
            name=food.name,
            brand=food.brand,
            default_version_id=version_id,
            archived=food.archived,
        )

    def add_alias(self, alias: FoodAlias) -> FoodAlias:
        if alias.food_id not in self.foods:
            raise ValueError(f"unknown food_id: {alias.food_id}")
        self.aliases[alias.id] = alias
        return alias

    def associate_barcode(self, association: BarcodeAssociation) -> BarcodeAssociation:
        if association.food_id not in self.foods:
            raise ValueError(f"unknown food_id: {association.food_id}")
        if association.food_version_id not in self.versions:
            raise ValueError(f"unknown food_version_id: {association.food_version_id}")
        self.barcode_associations[association.barcode] = association
        return association

    def resolve_barcode(self, barcode: str) -> BarcodeAssociation | None:
        association = self.barcode_associations.get(barcode)
        if association is None or association.archived:
            return None
        return association

    def get_version(self, version_id: str) -> FoodVersion:
        return self.versions[version_id]

    def get_default_version(self, food_id: str) -> FoodVersion:
        food = self.foods[food_id]
        if food.default_version_id is None:
            raise ValueError(f"food has no default version: {food_id}")
        return self.versions[food.default_version_id]

    def archive_food(self, food_id: str) -> Food:
        food = self.foods[food_id]
        archived = Food(
            id=food.id,
            household_id=food.household_id,
            name=food.name,
            brand=food.brand,
            default_version_id=food.default_version_id,
            archived=True,
        )
        self.foods[food_id] = archived
        return archived
