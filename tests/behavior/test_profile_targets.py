from __future__ import annotations

import unittest
from datetime import date

from health_monitor.application.service import HealthMonitorService
from health_monitor.domain.nutrients import Nutrients


class ProfileTargetsTest(unittest.TestCase):
    def test_household_supports_multiple_people_with_profile_metadata(self) -> None:
        service = HealthMonitorService()
        household = service.create_household(name="Casa")

        gabriel = service.create_person(
            household_id=household.id,
            name="Gabriel",
            timezone="America/Sao_Paulo",
            birth_date=date(1990, 5, 4),
            sex="male",
            height_cm=180,
            activity_level="moderate",
        )
        partner = service.create_person(
            household_id=household.id,
            name="Partner",
            timezone="America/Sao_Paulo",
            birth_date=date(1992, 8, 10),
            sex="female",
            height_cm=165,
            activity_level="light",
        )

        people = service.people_for_household(household.id)

        self.assertEqual([person.id for person in people], [gabriel.id, partner.id])
        self.assertEqual(gabriel.height_cm, 180)
        self.assertEqual(partner.activity_level, "light")

    def test_goal_targets_are_historical_and_do_not_rewrite_diary_totals(self) -> None:
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
            logged_at_local="2026-07-05T10:00:00",
            food_version_id=version.id,
            quantity_g=100,
            source="manual",
        )
        service.create_goal_profile(
            person_id=person.id,
            starts_on=date(2026, 7, 1),
            targets=Nutrients(2000, 150, 180, 70),
            notes="initial plan",
        )
        service.create_goal_profile(
            person_id=person.id,
            starts_on=date(2026, 7, 10),
            targets=Nutrients(1800, 160, 130, 60),
            notes="cut adjustment",
        )

        before_change = service.day_summary(person.id, date(2026, 7, 5))
        after_change = service.day_summary(person.id, date(2026, 7, 11))
        week = service.week_summary(
            person_id=person.id,
            start=date(2026, 7, 5),
            end=date(2026, 7, 11),
        )

        self.assertEqual(before_change.totals.rounded(), Nutrients(315, 23, 2.6, 23.5))
        self.assertEqual(before_change.target, Nutrients(2000, 150, 180, 70))
        self.assertEqual(after_change.target, Nutrients(1800, 160, 130, 60))
        self.assertEqual(week.daily_targets[date(2026, 7, 5)], Nutrients(2000, 150, 180, 70))
        self.assertEqual(week.daily_targets[date(2026, 7, 11)], Nutrients(1800, 160, 130, 60))
        self.assertEqual(week.totals.rounded(), Nutrients(315, 23, 2.6, 23.5))


if __name__ == "__main__":
    unittest.main()
