from __future__ import annotations

import unittest
from datetime import date as real_date
from unittest.mock import patch

from health_monitor.application.service import HealthMonitorService
from health_monitor.domain.nutrients import Nutrients


class OnboardingProfileSetupBehaviorTest(unittest.TestCase):
    def test_profile_setup_goal_stays_active_on_drafted_day_when_confirmed_later(self) -> None:
        service = HealthMonitorService()
        proposal = service.draft_onboarding_proposal(
            session_id="session-1",
            household_name="Casa",
            household_id=None,
            person={
                "name": "Gabriel",
                "timezone": "America/Sao_Paulo",
                "activity_level": "moderate",
            },
            targets={
                "calories_kcal": 2000,
                "protein_g": 150,
                "carbs_g": 180,
                "fat_g": 70,
            },
            notes="Setup inicial",
            source_text="conversa livre",
            starts_on=real_date(2026, 7, 3),
        )

        class LaterDate(real_date):
            @classmethod
            def today(cls) -> real_date:
                return cls(2026, 7, 5)

        with patch("health_monitor.application.service.date", LaterDate):
            applied = service.confirm_proposal(proposal.id)

        drafted_day = real_date.fromisoformat(proposal.payload["starts_on"])
        goal = service.active_goal_profile(
            person_id=applied.payload["created_person_id"],
            day=drafted_day,
        )

        self.assertIsNotNone(goal)
        assert goal is not None
        self.assertEqual(goal.starts_on, drafted_day)
        self.assertEqual(goal.targets, Nutrients(2000, 150, 180, 70))


if __name__ == "__main__":
    unittest.main()
