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


class Diary:
    def __init__(self, catalog: FoodCatalog) -> None:
        self.catalog = catalog
        self.entries: dict[str, DiaryEntry] = {}

    def add_entry(self, entry: DiaryEntry) -> DiaryEntry:
        self.catalog.get_version(entry.food_version_id)
        self.entries[entry.id] = entry
        return entry

    def entries_for_day(self, person_id: str, day: date) -> list[DiaryEntry]:
        return [
            entry
            for entry in self.entries.values()
            if entry.person_id == person_id and entry.logged_at.date() == day
        ]

    def totals_for_day(self, person_id: str, day: date) -> Nutrients:
        total = ZERO_NUTRIENTS
        for entry in self.entries_for_day(person_id, day):
            version = self.catalog.get_version(entry.food_version_id)
            total += version.nutrients_per_100g.scale(entry.quantity_g / 100)
        return total

