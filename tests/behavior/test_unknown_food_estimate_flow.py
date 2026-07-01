from __future__ import annotations

import unittest
from datetime import date

from health_monitor.application.service import HealthMonitorService
from health_monitor.domain.nutrients import Nutrients
from health_monitor.lookup.estimates import NutritionEstimate, StaticFoodEstimator


class UnknownFoodEstimateFlowTest(unittest.TestCase):
    def test_unknown_food_estimate_is_proposed_before_any_mutation(self) -> None:
        service = HealthMonitorService(
            estimator=StaticFoodEstimator(
                {
                    "kfc double crunch combo": NutritionEstimate(
                        phrase="kfc double crunch combo",
                        food_name="KFC Double Crunch combo",
                        nutrients_per_100g=Nutrients(
                            calories_kcal=260,
                            protein_g=11,
                            carbs_g=24,
                            fat_g=13,
                        ),
                        source="fixture_model_estimate",
                        confidence=0.42,
                        notes="Fixture estimate for a regional restaurant meal.",
                    )
                }
            )
        )
        household = service.create_household(name="Casa")
        person = service.create_person(
            household_id=household.id,
            name="Gabriel",
            timezone="America/Sao_Paulo",
        )

        proposal = service.propose_text_meal(
            person_id=person.id,
            logged_at_local="2026-07-01T20:00:00",
            text="300g KFC Double Crunch combo",
            agent_settings={"model_profile": "ollama-local", "external_lookup": True},
        )

        self.assertEqual(proposal.proposal_type, "diary_entries_with_estimates")
        self.assertEqual(proposal.status, "draft")
        self.assertEqual(proposal.entries[0].quantity_g, 300)
        self.assertEqual(proposal.totals.rounded(), Nutrients(780, 33, 72, 39))
        self.assertEqual(proposal.evidence[0]["source_type"], "model_estimate")
        self.assertEqual(proposal.evidence[0]["confidence"], 0.42)
        self.assertEqual(service.day_summary(person.id, date(2026, 7, 1)).totals, Nutrients())
        self.assertIsNone(service.resolver.resolve_phrase("kfc double crunch combo", person_id=person.id))

    def test_confirming_unknown_food_estimate_creates_reusable_food_and_diary_entry(self) -> None:
        service = HealthMonitorService(
            estimator=StaticFoodEstimator(
                {
                    "kfc double crunch combo": NutritionEstimate(
                        phrase="kfc double crunch combo",
                        food_name="KFC Double Crunch combo",
                        nutrients_per_100g=Nutrients(260, 11, 24, 13),
                        source="fixture_model_estimate",
                        confidence=0.42,
                        notes="Fixture estimate for a regional restaurant meal.",
                    )
                }
            )
        )
        household = service.create_household(name="Casa")
        person = service.create_person(
            household_id=household.id,
            name="Gabriel",
            timezone="America/Sao_Paulo",
        )
        proposal = service.propose_text_meal(
            person_id=person.id,
            logged_at_local="2026-07-01T20:00:00",
            text="300g KFC Double Crunch combo",
            agent_settings={"external_lookup": True},
        )

        applied = service.confirm_proposal(proposal.id)
        summary = service.day_summary(person.id, date(2026, 7, 1))
        resolution = service.resolve_food_reference(
            household_id=household.id,
            person_id=person.id,
            phrase="kfc double crunch combo",
        )

        self.assertEqual(applied.status, "applied")
        self.assertEqual(len(applied.applied_record_ids), 3)
        self.assertEqual(summary.totals.rounded(), Nutrients(780, 33, 72, 39))
        self.assertEqual(resolution.food_version_id, proposal.entries[0].food_version_id)

    def test_rejecting_unknown_food_estimate_does_not_create_reusable_food(self) -> None:
        service = HealthMonitorService(
            estimator=StaticFoodEstimator(
                {
                    "kfc double crunch combo": NutritionEstimate(
                        phrase="kfc double crunch combo",
                        food_name="KFC Double Crunch combo",
                        nutrients_per_100g=Nutrients(260, 11, 24, 13),
                        source="fixture_model_estimate",
                        confidence=0.42,
                        notes="Fixture estimate for a regional restaurant meal.",
                    )
                }
            )
        )
        household = service.create_household(name="Casa")
        person = service.create_person(
            household_id=household.id,
            name="Gabriel",
            timezone="America/Sao_Paulo",
        )
        proposal = service.propose_text_meal(
            person_id=person.id,
            logged_at_local="2026-07-01T20:00:00",
            text="300g KFC Double Crunch combo",
            agent_settings={"external_lookup": True},
        )

        service.reject_proposal(proposal.id)

        self.assertIsNone(service.resolver.resolve_phrase("kfc double crunch combo", person_id=person.id))
        self.assertEqual(service.day_summary(person.id, date(2026, 7, 1)).totals, Nutrients())


if __name__ == "__main__":
    unittest.main()
