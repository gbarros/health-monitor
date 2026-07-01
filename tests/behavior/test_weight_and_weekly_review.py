from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from health_monitor.application.service import HealthMonitorService
from health_monitor.domain.nutrients import Nutrients
from health_monitor.persistence.sqlite_state import SQLiteStateRepository


class WeightAndWeeklyReviewTest(unittest.TestCase):
    def test_weight_trend_and_weekly_macro_summary_are_deterministic(self) -> None:
        service = HealthMonitorService()
        household = service.create_household(name="Casa")
        person = service.create_person(
            household_id=household.id,
            name="Gabriel",
            timezone="America/Sao_Paulo",
        )
        _, version = service.create_food_with_version(
            household_id=household.id,
            name="Queijo Minas",
            brand=None,
            version_label="current",
            nutrients_per_100g=Nutrients(315, 23, 2.6, 23.5),
            source="label_scan",
            aliases=["queijo"],
        )
        service.log_diary_entry(
            person_id=person.id,
            logged_at_local="2026-07-01T10:00:00",
            food_version_id=version.id,
            quantity_g=100,
            source="manual",
        )
        service.log_diary_entry(
            person_id=person.id,
            logged_at_local="2026-07-02T10:00:00",
            food_version_id=version.id,
            quantity_g=50,
            source="manual",
        )
        service.log_weight(
            person_id=person.id,
            measured_at_local="2026-07-01T08:00:00",
            weight_kg=91.2,
            note="start",
            source="manual",
        )
        service.log_weight(
            person_id=person.id,
            measured_at_local="2026-07-07T08:00:00",
            weight_kg=90.4,
            note="week end",
            source="manual",
        )

        trend = service.weight_trend(person_id=person.id)
        week = service.week_summary(
            person_id=person.id,
            start=date(2026, 7, 1),
            end=date(2026, 7, 7),
        )

        self.assertEqual(trend.delta_kg, -0.8)
        self.assertEqual(trend.entries[0].weight_kg, 91.2)
        self.assertEqual(trend.entries[-1].weight_kg, 90.4)
        self.assertEqual(week.totals.rounded(), Nutrients(472.5, 34.5, 3.9, 35.25))
        self.assertEqual(week.daily[date(2026, 7, 1)].calories_kcal, 315)
        self.assertEqual(week.daily[date(2026, 7, 2)].calories_kcal, 157.5)
        self.assertEqual(week.weight_delta_kg, -0.8)

    def test_weight_and_weekly_review_survive_restart(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "health-monitor.sqlite3"
            first = HealthMonitorService(repository=SQLiteStateRepository(db_path))
            household = first.create_household(name="Casa")
            person = first.create_person(
                household_id=household.id,
                name="Gabriel",
                timezone="America/Sao_Paulo",
            )
            _, version = first.create_food_with_version(
                household_id=household.id,
                name="Queijo Minas",
                brand=None,
                version_label="current",
                nutrients_per_100g=Nutrients(315, 23, 2.6, 23.5),
                source="label_scan",
                aliases=["queijo"],
            )
            first.log_diary_entry(
                person_id=person.id,
                logged_at_local="2026-07-01T10:00:00",
                food_version_id=version.id,
                quantity_g=100,
                source="manual",
            )
            first.log_weight(
                person_id=person.id,
                measured_at_local="2026-07-01T08:00:00",
                weight_kg=91.2,
                note=None,
                source="manual",
            )

            second = HealthMonitorService(repository=SQLiteStateRepository(db_path))
            trend = second.weight_trend(person_id=person.id)
            week = second.week_summary(
                person_id=person.id,
                start=date(2026, 7, 1),
                end=date(2026, 7, 7),
            )

            self.assertEqual(trend.entries[0].weight_kg, 91.2)
            self.assertEqual(week.totals.rounded(), Nutrients(315, 23, 2.6, 23.5))


if __name__ == "__main__":
    unittest.main()
