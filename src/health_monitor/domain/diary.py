from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from health_monitor.domain.foods import FoodCatalog
from health_monitor.domain.nutrients import Nutrients, ZERO_NUTRIENTS


@dataclass(frozen=True)
class DiaryEntry:
    id: str
    person_id: str
    logged_at: datetime
    meal_type: str
    food_version_id: str
    quantity_g: float
    source: str
    deleted_at: datetime | None = None


class Diary:
    def __init__(self, catalog: FoodCatalog) -> None:
        self.catalog = catalog
        self.entries: dict[str, DiaryEntry] = {}

    def add_entry(self, entry: DiaryEntry) -> DiaryEntry:
        self.catalog.get_version(entry.food_version_id)
        self.entries[entry.id] = entry
        return entry

    def update_entry(
        self,
        entry_id: str,
        *,
        logged_at: datetime | None = None,
        meal_type: str | None = None,
        food_version_id: str | None = None,
        quantity_g: float | None = None,
    ) -> DiaryEntry:
        entry = self.entries[entry_id]
        if entry.deleted_at is not None:
            raise ValueError("cannot update deleted diary entry")
        next_food_version_id = food_version_id or entry.food_version_id
        self.catalog.get_version(next_food_version_id)
        if quantity_g is not None and quantity_g <= 0:
            raise ValueError("quantity_g must be positive")
        updated = DiaryEntry(
            id=entry.id,
            person_id=entry.person_id,
            logged_at=logged_at or entry.logged_at,
            meal_type=meal_type or entry.meal_type,
            food_version_id=next_food_version_id,
            quantity_g=float(quantity_g) if quantity_g is not None else entry.quantity_g,
            source=entry.source,
            deleted_at=entry.deleted_at,
        )
        self.entries[entry_id] = updated
        return updated

    def delete_entry(self, entry_id: str, *, deleted_at: datetime) -> DiaryEntry:
        entry = self.entries[entry_id]
        deleted = DiaryEntry(
            id=entry.id,
            person_id=entry.person_id,
            logged_at=entry.logged_at,
            meal_type=entry.meal_type,
            food_version_id=entry.food_version_id,
            quantity_g=entry.quantity_g,
            source=entry.source,
            deleted_at=deleted_at,
        )
        self.entries[entry_id] = deleted
        return deleted

    def restore_entry(self, entry_id: str) -> DiaryEntry:
        entry = self.entries[entry_id]
        restored = DiaryEntry(
            id=entry.id,
            person_id=entry.person_id,
            logged_at=entry.logged_at,
            meal_type=entry.meal_type,
            food_version_id=entry.food_version_id,
            quantity_g=entry.quantity_g,
            source=entry.source,
            deleted_at=None,
        )
        self.entries[entry_id] = restored
        return restored

    def entries_for_day(self, person_id: str, day: date) -> list[DiaryEntry]:
        return [
            entry
            for entry in self.entries.values()
            if entry.person_id == person_id
            and entry.logged_at.date() == day
            and entry.deleted_at is None
        ]

    def totals_for_day(self, person_id: str, day: date) -> Nutrients:
        total = ZERO_NUTRIENTS
        for entry in self.entries_for_day(person_id, day):
            version = self.catalog.get_version(entry.food_version_id)
            total += version.nutrients_per_100g.scale(entry.quantity_g / 100)
        return total
