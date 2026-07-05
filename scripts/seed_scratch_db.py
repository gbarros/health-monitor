from __future__ import annotations

import argparse
from datetime import date, timedelta
from pathlib import Path

from health_monitor.application.service import HealthMonitorService
from health_monitor.domain.nutrients import Nutrients
from health_monitor.persistence.sqlite_state import SQLiteStateRepository


def build_seed_service(sqlite_path: Path, *, overwrite: bool) -> HealthMonitorService:
    if sqlite_path.exists():
        if not overwrite:
            raise SystemExit(f"refusing to overwrite existing scratch db: {sqlite_path}")
        sqlite_path.unlink()
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    return HealthMonitorService(repository=SQLiteStateRepository(sqlite_path))


def seed(sqlite_path: Path, *, overwrite: bool, today: date) -> None:
    service = build_seed_service(sqlite_path, overwrite=overwrite)
    household = service.create_household(name="Casa Scratch")
    person = service.create_person(
        household_id=household.id,
        name="Gabriel",
        timezone="America/Sao_Paulo",
        activity_level="moderate",
        height_cm=180,
    )
    service.create_goal_profile(
        person_id=person.id,
        starts_on=today,
        targets=Nutrients(2000, 150, 180, 70, fiber_g=30, sodium_mg=2300),
        notes="Scratch walkthrough goal",
    )
    _, cheese = service.create_food_with_version(
        household_id=household.id,
        name="Queijo Minas",
        brand=None,
        version_label="current",
        nutrients_per_100g=Nutrients(315, 23, 2.6, 23.5),
        source="label_scan",
        aliases=["queijo"],
    )
    _, egg = service.create_food_with_version(
        household_id=household.id,
        name="Ovo",
        brand=None,
        version_label="large egg",
        nutrients_per_100g=Nutrients(155, 13, 1.1, 11),
        source="reference",
        aliases=["ovo", "ovos"],
        serving_size_g=50,
    )
    service.create_food_with_version(
        household_id=household.id,
        name="Arroz",
        brand=None,
        version_label="cozido",
        nutrients_per_100g=Nutrients(130, 2.7, 28, 0.3),
        source="reference",
        aliases=["arroz"],
    )
    service.create_food_with_version(
        household_id=household.id,
        name="Feijão",
        brand=None,
        version_label="cozido",
        nutrients_per_100g=Nutrients(76, 4.8, 13.6, 0.5),
        source="reference",
        aliases=["feijao", "feijão"],
    )
    service.create_food_with_version(
        household_id=household.id,
        name="Iogurte Batavo",
        brand="Batavo",
        version_label="protein label",
        nutrients_per_100g=Nutrients(70, 10, 6, 1),
        source="label_scan",
        aliases=["iogurte batavo", "iogurte"],
        barcode="7891000000000",
    )
    service.log_diary_entry(
        person_id=person.id,
        logged_at_local=f"{(today - timedelta(days=1)).isoformat()}T09:00:00",
        food_version_id=cheese.id,
        quantity_g=50,
        source="seed",
        meal_type="breakfast",
    )
    service.log_diary_entry(
        person_id=person.id,
        logged_at_local=f"{(today - timedelta(days=1)).isoformat()}T09:05:00",
        food_version_id=egg.id,
        quantity_g=100,
        source="seed",
        meal_type="breakfast",
    )
    print(f"Seeded scratch db at {sqlite_path}")
    print(f"household_id={household.id}")
    print(f"person_id={person.id}")
    print(f"goal_starts_on={today.isoformat()}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed a scratch SQLite DB for live walkthroughs.")
    parser.add_argument("--sqlite-path", required=True, type=Path)
    parser.add_argument("--today", default=date.today().isoformat())
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    seed(
        args.sqlite_path,
        overwrite=args.overwrite,
        today=date.fromisoformat(args.today),
    )


if __name__ == "__main__":
    main()
